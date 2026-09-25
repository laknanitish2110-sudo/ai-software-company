"""
Unified Database Abstraction Layer (P4.7-A)

Supports both SQLite (file-backed / local dev) and PostgreSQL (asyncpg / cloud production).
Selected dynamically via DATABASE_URL environment variable:
- postgresql://... or postgres://... -> PostgreSQL via asyncpg
- empty or sqlite://... -> SQLite via aiosqlite
"""

import aiosqlite
import json
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, List, Optional, Dict

from app.core.config import DATABASE_PATH, DATABASE_URL

logger = logging.getLogger(__name__)

_pg_pool = None


async def get_pg_pool():
    global _pg_pool
    if _pg_pool is None and DATABASE_URL and (DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")):
        import asyncpg
        logger.info("Initializing PostgreSQL asyncpg connection pool...")
        # Replace postgresql:// with postgres:// if needed for asyncpg
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        _pg_pool = await asyncpg.create_pool(url, min_size=1, max_size=10)
    return _pg_pool


class DBCursorWrapper:
    """Wrapper normalizing query result rows to dictionary representation across engines."""
    def __init__(self, backend_type: str, cursor_or_rows: Any):
        self.backend_type = backend_type
        self.raw = cursor_or_rows

    async def fetchone(self) -> Optional[Dict[str, Any]]:
        if self.backend_type == "sqlite":
            row = await self.raw.fetchone()
            return dict(row) if row else None
        else:
            if isinstance(self.raw, list):
                return dict(self.raw[0]) if self.raw else None
            return None

    async def fetchall(self) -> List[Dict[str, Any]]:
        if self.backend_type == "sqlite":
            rows = await self.raw.fetchall()
            return [dict(r) for r in rows]
        else:
            if isinstance(self.raw, list):
                return [dict(r) for r in self.raw]
            return []

    @property
    def rowcount(self) -> int:
        if self.backend_type == "sqlite":
            return getattr(self.raw, "rowcount", 0)
        else:
            if isinstance(self.raw, list):
                return len(self.raw)
            elif isinstance(self.raw, str):
                parts = self.raw.strip().split()
                if parts:
                    try:
                        return int(parts[-1])
                    except ValueError:
                        return 0
            return 0


class DBWrapper:
    """Unified Database Connection Wrapper abstracting SQLite & PostgreSQL."""
    def __init__(self, backend_type: str, conn_or_pool: Any):
        self.backend_type = backend_type
        self.conn = conn_or_pool
        self._closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def execute(self, sql: str, params: tuple = ()) -> DBCursorWrapper:
        if self.backend_type == "sqlite":
            cursor = await self.conn.execute(sql, params)
            return DBCursorWrapper("sqlite", cursor)
        else:
            pg_sql = self._to_pg_sql(sql)
            if pg_sql.strip().upper().startswith("SELECT") or "RETURNING" in pg_sql.strip().upper():
                rows = await self.conn.fetch(pg_sql, *params)
                return DBCursorWrapper("postgres", rows)
            else:
                res = await self.conn.execute(pg_sql, *params)
                return DBCursorWrapper("postgres", res)

    async def executescript(self, sql: str):
        if self.backend_type == "sqlite":
            await self.conn.executescript(sql)
        else:
            # PostgreSQL script execution
            statements = [s.strip() for s in sql.split(";") if s.strip()]
            for stmt in statements:
                pg_sql = self._to_pg_sql(stmt)
                await self.conn.execute(pg_sql)

    async def commit(self):
        if self.backend_type == "sqlite":
            await self.conn.commit()

    async def close(self):
        if self._closed:
            return
        self._closed = True
        if self.backend_type == "sqlite" and self.conn:
            await self.conn.close()
            self.conn = None
        elif self.backend_type == "postgres" and self.conn:
            pool = await get_pg_pool()
            if pool is not None:
                await pool.release(self.conn)
            self.conn = None

    def _to_pg_sql(self, sql: str) -> str:
        """Translates SQLite query dialect to PostgreSQL syntax."""
        # Translate INSERT OR IGNORE (SQLite-only) to INSERT ... ON CONFLICT DO NOTHING (PostgreSQL-compatible)
        if "INSERT OR IGNORE INTO" in sql:
            sql = sql.replace("INSERT OR IGNORE INTO", "INSERT INTO")
            if "ON CONFLICT" not in sql:
                # Append ON CONFLICT DO NOTHING before any trailing semicolon
                sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"

        if "?" in sql:
            parts = sql.split("?")
            res = []
            for i, part in enumerate(parts[:-1]):
                res.append(part)
                res.append(f"${i+1}")
            res.append(parts[-1])
            sql = "".join(res)


        return sql


async def get_db() -> DBWrapper:
    pool = await get_pg_pool()
    if pool is not None:
        conn = await pool.acquire()
        return DBWrapper("postgres", conn)
    else:
        db = await aiosqlite.connect(DATABASE_PATH)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
        return DBWrapper("sqlite", db)


async def init_db():
    db = await get_db()
    try:
        if db.backend_type == "sqlite":
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    email_verified INTEGER NOT NULL DEFAULT 0,
                    verification_code TEXT,
                    verification_expires TEXT
                );

                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    problem_statement TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'created',
                    user_id TEXT NOT NULL DEFAULT 'legacy_owner',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS executions (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'QUEUED',
                    attempt INTEGER NOT NULL DEFAULT 1,
                    worker_id TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    last_heartbeat TEXT,
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                );

                CREATE TABLE IF NOT EXISTS agent_outputs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                );

                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    agent_role TEXT NOT NULL,
                    messages TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(id),
                    UNIQUE(project_id, agent_role)
                );

                CREATE TABLE IF NOT EXISTS shared_memory (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(id),
                    UNIQUE(project_id, key)
                );

                CREATE TABLE IF NOT EXISTS share_links (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    token TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                );

                CREATE TABLE IF NOT EXISTS domain_learnings (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                );

                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, key)
                );

                CREATE TABLE IF NOT EXISTS cost_tracking (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    model TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    estimated_cost REAL NOT NULL DEFAULT 0.0,
                    call_type TEXT NOT NULL DEFAULT 'agent',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                );

                CREATE TABLE IF NOT EXISTS execution_events (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    execution_id TEXT,
                    seq INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(id),
                    UNIQUE(project_id, seq)
                );
                CREATE INDEX IF NOT EXISTS idx_exec_events_proj_seq ON execution_events(project_id, seq);

                CREATE TABLE IF NOT EXISTS employee_templates (
                    id TEXT PRIMARY KEY,
                    slug TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    description TEXT,
                    system_prompt TEXT NOT NULL,
                    default_tools TEXT,
                    default_permissions TEXT,
                    version INTEGER NOT NULL DEFAULT 1,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS employees (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    template_id TEXT,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    persona TEXT,
                    avatar_url TEXT,
                    status TEXT NOT NULL DEFAULT 'idle',
                    config TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (template_id) REFERENCES employee_templates(id)
                );
                CREATE INDEX IF NOT EXISTS idx_employees_user ON employees(user_id);

                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    employee_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT,
                    source_id TEXT,
                    confidence REAL NOT NULL DEFAULT 0.8,
                    importance REAL NOT NULL DEFAULT 0.5,
                    tags TEXT,
                    embedding_id TEXT,
                    created_at TEXT NOT NULL,
                    last_accessed TEXT,
                    last_verified TEXT,
                    stale_after TEXT,
                    superseded_by TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY (employee_id) REFERENCES employees(id)
                );
                CREATE INDEX IF NOT EXISTS idx_memories_employee ON memories(employee_id);
                CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(employee_id, type);
                CREATE INDEX IF NOT EXISTS idx_memories_active ON memories(employee_id, is_active);

                CREATE TABLE IF NOT EXISTS employee_skills (
                    id TEXT PRIMARY KEY,
                    employee_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    trigger_pattern TEXT,
                    procedure TEXT NOT NULL,
                    examples TEXT,
                    times_used INTEGER NOT NULL DEFAULT 0,
                    success_rate REAL NOT NULL DEFAULT 1.0,
                    created_at TEXT NOT NULL,
                    last_used TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY (employee_id) REFERENCES employees(id)
                );
                CREATE INDEX IF NOT EXISTS idx_skills_employee ON employee_skills(employee_id);
                CREATE INDEX IF NOT EXISTS idx_skills_active ON employee_skills(employee_id, is_active);

                CREATE TABLE IF NOT EXISTS employee_sessions (
                    id TEXT PRIMARY KEY,
                    employee_id TEXT NOT NULL,
                    project_id TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    summary TEXT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    last_activity TEXT NOT NULL,
                    FOREIGN KEY (employee_id) REFERENCES employees(id),
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_employee ON employee_sessions(employee_id);

                CREATE TABLE IF NOT EXISTS session_messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tool_calls TEXT,
                    tool_results TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES employee_sessions(id)
                );
                CREATE INDEX IF NOT EXISTS idx_messages_session ON session_messages(session_id);

                CREATE TABLE IF NOT EXISTS skills (
                    id TEXT PRIMARY KEY,
                    employee_id TEXT,
                    name TEXT NOT NULL,
                    description TEXT,
                    trigger_when TEXT,
                    steps TEXT NOT NULL,
                    validation TEXT,
                    approval_rules TEXT,
                    source TEXT DEFAULT 'manual',
                    use_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (employee_id) REFERENCES employees(id)
                );

                CREATE TABLE IF NOT EXISTS tool_permissions (
                    id TEXT PRIMARY KEY,
                    employee_id TEXT NOT NULL,
                    tool TEXT NOT NULL,
                    action TEXT NOT NULL,
                    permission TEXT NOT NULL DEFAULT 'ask',
                    granted_by TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (employee_id) REFERENCES employees(id),
                    UNIQUE(employee_id, tool, action)
                );

                CREATE TABLE IF NOT EXISTS delegation_tasks (
                    id TEXT PRIMARY KEY,
                    from_employee_id TEXT NOT NULL,
                    to_employee_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    task TEXT NOT NULL,
                    context TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    result TEXT,
                    project_id TEXT,
                    session_id TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    FOREIGN KEY (from_employee_id) REFERENCES employees(id),
                    FOREIGN KEY (to_employee_id) REFERENCES employees(id)
                );
                CREATE INDEX IF NOT EXISTS idx_delegation_status ON delegation_tasks(status);
                CREATE INDEX IF NOT EXISTS idx_delegation_from ON delegation_tasks(from_employee_id);

                CREATE TABLE IF NOT EXISTS autonomous_executions (
                    id TEXT PRIMARY KEY,
                    employee_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    session_id TEXT,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    state TEXT NOT NULL DEFAULT 'PLANNING',
                    plan TEXT,
                    iteration INTEGER NOT NULL DEFAULT 0,
                    max_iterations INTEGER NOT NULL DEFAULT 25,
                    max_tokens INTEGER NOT NULL DEFAULT 200000,
                    tokens_used INTEGER NOT NULL DEFAULT 0,
                    max_time_seconds INTEGER NOT NULL DEFAULT 600,
                    sandbox_id TEXT,
                    error TEXT,
                    result TEXT,
                    progress TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    FOREIGN KEY (employee_id) REFERENCES employees(id),
                    FOREIGN KEY (session_id) REFERENCES employee_sessions(id)
                );
                CREATE INDEX IF NOT EXISTS idx_auto_exec_employee ON autonomous_executions(employee_id);
                CREATE INDEX IF NOT EXISTS idx_auto_exec_status ON autonomous_executions(status);

                CREATE TABLE IF NOT EXISTS execution_artifacts (
                    id TEXT PRIMARY KEY,
                    execution_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    path TEXT,
                    content TEXT,
                    language TEXT,
                    status TEXT NOT NULL DEFAULT 'draft',
                    metadata TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (execution_id) REFERENCES autonomous_executions(id)
                );
                CREATE INDEX IF NOT EXISTS idx_exec_artifacts ON execution_artifacts(execution_id);

                CREATE TABLE IF NOT EXISTS execution_logs (
                    id TEXT PRIMARY KEY,
                    execution_id TEXT NOT NULL,
                    iteration INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    action TEXT NOT NULL,
                    input_summary TEXT,
                    output_summary TEXT,
                    tokens_used INTEGER NOT NULL DEFAULT 0,
                    duration_ms INTEGER,
                    success INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (execution_id) REFERENCES autonomous_executions(id)
                );
                CREATE INDEX IF NOT EXISTS idx_exec_logs ON execution_logs(execution_id, iteration);

                CREATE TABLE IF NOT EXISTS activity_log (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    employee_id TEXT,
                    employee_name TEXT,
                    event_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    detail TEXT,
                    metadata TEXT,
                    created_at TEXT NOT NULL,
                    seen INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (employee_id) REFERENCES employees(id)
                );
                CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_log(user_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_activity_unseen ON activity_log(user_id, seen);

                CREATE TABLE IF NOT EXISTS decision_log (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    employee_id TEXT,
                    decision_type TEXT NOT NULL,
                    input_context TEXT,
                    options TEXT,
                    selected_choice TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    backend TEXT NOT NULL,
                    latency_ms REAL,
                    created_at TEXT NOT NULL,
                    actual_outcome TEXT,
                    outcome_correct INTEGER,
                    human_override TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_decision_type ON decision_log(decision_type, created_at);
                CREATE INDEX IF NOT EXISTS idx_decision_project ON decision_log(project_id);

                CREATE TABLE IF NOT EXISTS subscriptions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL UNIQUE,
                    stripe_customer_id TEXT,
                    stripe_subscription_id TEXT,
                    plan TEXT NOT NULL DEFAULT 'free',
                    status TEXT NOT NULL DEFAULT 'active',
                    current_period_start TEXT,
                    current_period_end TEXT,
                    cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
                CREATE INDEX IF NOT EXISTS idx_sub_user ON subscriptions(user_id);
                CREATE INDEX IF NOT EXISTS idx_sub_stripe ON subscriptions(stripe_customer_id);

                CREATE TABLE IF NOT EXISTS usage_records (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    record_type TEXT NOT NULL,
                    tokens_input INTEGER NOT NULL DEFAULT 0,
                    tokens_output INTEGER NOT NULL DEFAULT 0,
                    model TEXT,
                    employee_id TEXT,
                    project_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
                CREATE INDEX IF NOT EXISTS idx_usage_user ON usage_records(user_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_usage_type ON usage_records(record_type);

                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    employee_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    task_prompt TEXT NOT NULL,
                    schedule_type TEXT NOT NULL DEFAULT 'once',
                    cron_expression TEXT,
                    next_run_at TEXT,
                    last_run_at TEXT,
                    last_run_status TEXT,
                    last_run_result TEXT,
                    run_count INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (employee_id) REFERENCES employees(id)
                );
                CREATE INDEX IF NOT EXISTS idx_sched_user ON scheduled_tasks(user_id);
                CREATE INDEX IF NOT EXISTS idx_sched_employee ON scheduled_tasks(employee_id);
                CREATE INDEX IF NOT EXISTS idx_sched_next ON scheduled_tasks(next_run_at, is_active);

                CREATE TABLE IF NOT EXISTS memory_embeddings (
                    id TEXT PRIMARY KEY,
                    memory_id TEXT NOT NULL UNIQUE,
                    employee_id TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    model TEXT NOT NULL DEFAULT 'local',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (memory_id) REFERENCES memories(id),
                    FOREIGN KEY (employee_id) REFERENCES employees(id)
                );
                CREATE INDEX IF NOT EXISTS idx_membed_employee ON memory_embeddings(employee_id);
                CREATE INDEX IF NOT EXISTS idx_membed_memory ON memory_embeddings(memory_id);
            """)
        else:
            # PostgreSQL DDL
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id VARCHAR(255) PRIMARY KEY,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    email_verified INTEGER NOT NULL DEFAULT 0,
                    verification_code VARCHAR(10),
                    verification_expires TEXT
                );

                CREATE TABLE IF NOT EXISTS projects (
                    id VARCHAR(255) PRIMARY KEY,
                    problem_statement TEXT NOT NULL,
                    status VARCHAR(255) NOT NULL DEFAULT 'created',
                    user_id VARCHAR(255) NOT NULL DEFAULT 'legacy_owner',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS executions (
                    id VARCHAR(255) PRIMARY KEY,
                    project_id VARCHAR(255) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    user_id VARCHAR(255) NOT NULL,
                    status VARCHAR(255) NOT NULL DEFAULT 'QUEUED',
                    attempt INTEGER NOT NULL DEFAULT 1,
                    worker_id VARCHAR(255),
                    error TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    last_heartbeat TEXT
                );

                CREATE TABLE IF NOT EXISTS agent_outputs (
                    id VARCHAR(255) PRIMARY KEY,
                    project_id VARCHAR(255) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    role VARCHAR(255) NOT NULL,
                    content TEXT NOT NULL,
                    status VARCHAR(255) NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS conversations (
                    id VARCHAR(255) PRIMARY KEY,
                    project_id VARCHAR(255) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    agent_role VARCHAR(255) NOT NULL,
                    messages TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL,
                    CONSTRAINT unq_conv_proj_role UNIQUE(project_id, agent_role)
                );

                CREATE TABLE IF NOT EXISTS shared_memory (
                    id VARCHAR(255) PRIMARY KEY,
                    project_id VARCHAR(255) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    key VARCHAR(255) NOT NULL,
                    value TEXT NOT NULL,
                    updated_by VARCHAR(255) NOT NULL,
                    updated_at TEXT NOT NULL,
                    CONSTRAINT unq_mem_proj_key UNIQUE(project_id, key)
                );

                CREATE TABLE IF NOT EXISTS share_links (
                    id VARCHAR(255) PRIMARY KEY,
                    project_id VARCHAR(255) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    token VARCHAR(255) NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS domain_learnings (
                    id VARCHAR(255) PRIMARY KEY,
                    project_id VARCHAR(255) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    category VARCHAR(255) NOT NULL,
                    domain VARCHAR(255) NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_role VARCHAR(255) NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id VARCHAR(255) NOT NULL,
                    key VARCHAR(255) NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, key)
                );

                CREATE TABLE IF NOT EXISTS cost_tracking (
                    id VARCHAR(255) PRIMARY KEY,
                    project_id VARCHAR(255) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    role VARCHAR(255) NOT NULL,
                    model VARCHAR(512) NOT NULL,
                    provider VARCHAR(255) NOT NULL,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    estimated_cost REAL NOT NULL DEFAULT 0.0,
                    call_type VARCHAR(64) NOT NULL DEFAULT 'agent',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS execution_events (
                    id VARCHAR(255) PRIMARY KEY,
                    project_id VARCHAR(255) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    execution_id VARCHAR(255),
                    seq INTEGER NOT NULL,
                    event_type VARCHAR(255) NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    CONSTRAINT unq_exec_events_proj_seq UNIQUE(project_id, seq)
                );
                CREATE INDEX IF NOT EXISTS idx_exec_events_proj_seq ON execution_events(project_id, seq);

                CREATE TABLE IF NOT EXISTS employee_templates (
                    id VARCHAR(255) PRIMARY KEY,
                    slug VARCHAR(255) NOT NULL UNIQUE,
                    name VARCHAR(255) NOT NULL,
                    role VARCHAR(255) NOT NULL,
                    description TEXT,
                    system_prompt TEXT NOT NULL,
                    default_tools TEXT,
                    default_permissions TEXT,
                    version INTEGER NOT NULL DEFAULT 1,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS employees (
                    id VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    template_id VARCHAR(255) REFERENCES employee_templates(id) ON DELETE SET NULL,
                    name VARCHAR(255) NOT NULL,
                    role VARCHAR(255) NOT NULL,
                    persona TEXT,
                    avatar_url TEXT,
                    status VARCHAR(64) NOT NULL DEFAULT 'idle',
                    config TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_employees_user ON employees(user_id);

                CREATE TABLE IF NOT EXISTS memories (
                    id VARCHAR(255) PRIMARY KEY,
                    employee_id VARCHAR(255) NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
                    type VARCHAR(64) NOT NULL,
                    content TEXT NOT NULL,
                    source VARCHAR(255),
                    source_id VARCHAR(255),
                    confidence REAL NOT NULL DEFAULT 0.8,
                    importance REAL NOT NULL DEFAULT 0.5,
                    tags TEXT,
                    embedding_id VARCHAR(255),
                    created_at TEXT NOT NULL,
                    last_accessed TEXT,
                    last_verified TEXT,
                    stale_after TEXT,
                    superseded_by VARCHAR(255),
                    is_active INTEGER NOT NULL DEFAULT 1
                );
                CREATE INDEX IF NOT EXISTS idx_memories_employee ON memories(employee_id);
                CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(employee_id, type);
                CREATE INDEX IF NOT EXISTS idx_memories_active ON memories(employee_id, is_active);

                CREATE TABLE IF NOT EXISTS employee_skills (
                    id VARCHAR(255) PRIMARY KEY,
                    employee_id VARCHAR(255) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    description TEXT NOT NULL,
                    trigger_pattern TEXT,
                    procedure TEXT NOT NULL,
                    examples TEXT,
                    times_used INTEGER NOT NULL DEFAULT 0,
                    success_rate REAL NOT NULL DEFAULT 1.0,
                    created_at TEXT NOT NULL,
                    last_used TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1
                );
                CREATE INDEX IF NOT EXISTS idx_skills_employee ON employee_skills(employee_id);
                CREATE INDEX IF NOT EXISTS idx_skills_active ON employee_skills(employee_id, is_active);

                CREATE TABLE IF NOT EXISTS employee_sessions (
                    id VARCHAR(255) PRIMARY KEY,
                    employee_id VARCHAR(255) NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
                    project_id VARCHAR(255) REFERENCES projects(id) ON DELETE SET NULL,
                    status VARCHAR(64) NOT NULL DEFAULT 'active',
                    summary TEXT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    last_activity TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_employee ON employee_sessions(employee_id);

                CREATE TABLE IF NOT EXISTS session_messages (
                    id VARCHAR(255) PRIMARY KEY,
                    session_id VARCHAR(255) NOT NULL REFERENCES employee_sessions(id) ON DELETE CASCADE,
                    role VARCHAR(64) NOT NULL,
                    content TEXT NOT NULL,
                    tool_calls TEXT,
                    tool_results TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_messages_session ON session_messages(session_id);

                CREATE TABLE IF NOT EXISTS skills (
                    id VARCHAR(255) PRIMARY KEY,
                    employee_id VARCHAR(255) REFERENCES employees(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    trigger_when TEXT,
                    steps TEXT NOT NULL,
                    validation TEXT,
                    approval_rules TEXT,
                    source VARCHAR(64) DEFAULT 'manual',
                    use_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tool_permissions (
                    id VARCHAR(255) PRIMARY KEY,
                    employee_id VARCHAR(255) NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
                    tool VARCHAR(255) NOT NULL,
                    action VARCHAR(64) NOT NULL,
                    permission VARCHAR(64) NOT NULL DEFAULT 'ask',
                    granted_by VARCHAR(255),
                    updated_at TEXT NOT NULL,
                    CONSTRAINT unq_tool_perm UNIQUE(employee_id, tool, action)
                );

                CREATE TABLE IF NOT EXISTS delegation_tasks (
                    id VARCHAR(255) PRIMARY KEY,
                    from_employee_id VARCHAR(255) NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
                    to_employee_id VARCHAR(255) NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
                    user_id VARCHAR(255) NOT NULL,
                    task TEXT NOT NULL,
                    context TEXT,
                    status VARCHAR(64) NOT NULL DEFAULT 'pending',
                    result TEXT,
                    project_id VARCHAR(255),
                    session_id VARCHAR(255),
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_delegation_status ON delegation_tasks(status);
                CREATE INDEX IF NOT EXISTS idx_delegation_from ON delegation_tasks(from_employee_id);

                CREATE TABLE IF NOT EXISTS autonomous_executions (
                    id VARCHAR(255) PRIMARY KEY,
                    employee_id VARCHAR(255) NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
                    user_id VARCHAR(255) NOT NULL,
                    session_id VARCHAR(255) REFERENCES employee_sessions(id) ON DELETE SET NULL,
                    goal TEXT NOT NULL,
                    status VARCHAR(64) NOT NULL DEFAULT 'pending',
                    state VARCHAR(64) NOT NULL DEFAULT 'PLANNING',
                    plan TEXT,
                    iteration INTEGER NOT NULL DEFAULT 0,
                    max_iterations INTEGER NOT NULL DEFAULT 25,
                    max_tokens INTEGER NOT NULL DEFAULT 200000,
                    tokens_used INTEGER NOT NULL DEFAULT 0,
                    max_time_seconds INTEGER NOT NULL DEFAULT 600,
                    sandbox_id VARCHAR(255),
                    error TEXT,
                    result TEXT,
                    progress TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_auto_exec_employee ON autonomous_executions(employee_id);
                CREATE INDEX IF NOT EXISTS idx_auto_exec_status ON autonomous_executions(status);

                CREATE TABLE IF NOT EXISTS execution_artifacts (
                    id VARCHAR(255) PRIMARY KEY,
                    execution_id VARCHAR(255) NOT NULL REFERENCES autonomous_executions(id) ON DELETE CASCADE,
                    type VARCHAR(64) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    path VARCHAR(512),
                    content TEXT,
                    language VARCHAR(64),
                    status VARCHAR(64) NOT NULL DEFAULT 'draft',
                    metadata TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_exec_artifacts ON execution_artifacts(execution_id);

                CREATE TABLE IF NOT EXISTS execution_logs (
                    id VARCHAR(255) PRIMARY KEY,
                    execution_id VARCHAR(255) NOT NULL REFERENCES autonomous_executions(id) ON DELETE CASCADE,
                    iteration INTEGER NOT NULL,
                    state VARCHAR(64) NOT NULL,
                    action TEXT NOT NULL,
                    input_summary TEXT,
                    output_summary TEXT,
                    tokens_used INTEGER NOT NULL DEFAULT 0,
                    duration_ms INTEGER,
                    success INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_exec_logs ON execution_logs(execution_id, iteration);

                CREATE TABLE IF NOT EXISTS activity_log (
                    id VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    employee_id VARCHAR(255),
                    employee_name VARCHAR(255),
                    event_type VARCHAR(64) NOT NULL,
                    title TEXT NOT NULL,
                    detail TEXT,
                    metadata TEXT,
                    created_at TEXT NOT NULL,
                    seen INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE SET NULL
                );
                CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_log(user_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_activity_unseen ON activity_log(user_id, seen);

                CREATE TABLE IF NOT EXISTS decision_log (
                    id VARCHAR(255) PRIMARY KEY,
                    project_id VARCHAR(255),
                    employee_id VARCHAR(255),
                    decision_type VARCHAR(64) NOT NULL,
                    input_context TEXT,
                    options TEXT,
                    selected_choice VARCHAR(255) NOT NULL,
                    confidence REAL NOT NULL,
                    backend VARCHAR(32) NOT NULL,
                    latency_ms REAL,
                    created_at TEXT NOT NULL,
                    actual_outcome TEXT,
                    outcome_correct INTEGER,
                    human_override TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_decision_type ON decision_log(decision_type, created_at);
                CREATE INDEX IF NOT EXISTS idx_decision_project ON decision_log(project_id);

                CREATE TABLE IF NOT EXISTS subscriptions (
                    id VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
                    stripe_customer_id VARCHAR(255),
                    stripe_subscription_id VARCHAR(255),
                    plan VARCHAR(32) NOT NULL DEFAULT 'free',
                    status VARCHAR(32) NOT NULL DEFAULT 'active',
                    current_period_start TEXT,
                    current_period_end TEXT,
                    cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sub_user ON subscriptions(user_id);
                CREATE INDEX IF NOT EXISTS idx_sub_stripe ON subscriptions(stripe_customer_id);

                CREATE TABLE IF NOT EXISTS usage_records (
                    id VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    record_type VARCHAR(64) NOT NULL,
                    tokens_input INTEGER NOT NULL DEFAULT 0,
                    tokens_output INTEGER NOT NULL DEFAULT 0,
                    model VARCHAR(255),
                    employee_id VARCHAR(255),
                    project_id VARCHAR(255),
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_usage_user ON usage_records(user_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_usage_type ON usage_records(record_type);

                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    id VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    employee_id VARCHAR(255) NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    task_prompt TEXT NOT NULL,
                    schedule_type VARCHAR(32) NOT NULL DEFAULT 'once',
                    cron_expression VARCHAR(128),
                    next_run_at TEXT,
                    last_run_at TEXT,
                    last_run_status VARCHAR(32),
                    last_run_result TEXT,
                    run_count INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sched_user ON scheduled_tasks(user_id);
                CREATE INDEX IF NOT EXISTS idx_sched_employee ON scheduled_tasks(employee_id);
                CREATE INDEX IF NOT EXISTS idx_sched_next ON scheduled_tasks(next_run_at, is_active);

                CREATE TABLE IF NOT EXISTS memory_embeddings (
                    id VARCHAR(255) PRIMARY KEY,
                    memory_id VARCHAR(255) NOT NULL UNIQUE REFERENCES memories(id) ON DELETE CASCADE,
                    employee_id VARCHAR(255) NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
                    embedding TEXT NOT NULL,
                    model VARCHAR(64) NOT NULL DEFAULT 'local',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_membed_employee ON memory_embeddings(employee_id);
                CREATE INDEX IF NOT EXISTS idx_membed_memory ON memory_embeddings(memory_id);
            """)
        await db.commit()

        # Migrate: add user_id to projects if missing (pre-auth databases)
        if db.backend_type == "sqlite":
            cols = [r["name"] for r in await (await db.execute("PRAGMA table_info(projects)")).fetchall()]
            if "user_id" not in cols:
                await db.execute("ALTER TABLE projects ADD COLUMN user_id TEXT NOT NULL DEFAULT 'legacy_owner'")
                await db.commit()
                logger.info("Migration: added user_id column to projects table")
        else:
            await db.execute("""
                DO $$ BEGIN
                    ALTER TABLE projects ADD COLUMN user_id VARCHAR(255) NOT NULL DEFAULT 'legacy_owner';
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
            """)
            await db.commit()

        # Migrate: add OAuth columns to users table
        if db.backend_type == "sqlite":
            user_cols = [r["name"] for r in await (await db.execute("PRAGMA table_info(users)")).fetchall()]
            if "oauth_provider" not in user_cols:
                await db.execute("ALTER TABLE users ADD COLUMN oauth_provider TEXT")
                await db.execute("ALTER TABLE users ADD COLUMN oauth_provider_id TEXT")
                await db.execute("ALTER TABLE users ADD COLUMN display_name TEXT")
                await db.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
                await db.commit()
                logger.info("Migration: added OAuth columns to users table")
        else:
            for col, col_type in [("oauth_provider", "VARCHAR(255)"), ("oauth_provider_id", "VARCHAR(255)"), ("display_name", "VARCHAR(255)"), ("avatar_url", "TEXT")]:
                await db.execute(f"""
                    DO $$ BEGIN
                        ALTER TABLE users ADD COLUMN {col} {col_type};
                    EXCEPTION WHEN duplicate_column THEN NULL;
                    END $$;
                """)
            await db.commit()
        # Migrate: add email verification columns to users table
        if db.backend_type == "sqlite":
            user_cols2 = [r["name"] for r in await (await db.execute("PRAGMA table_info(users)")).fetchall()]
            if "email_verified" not in user_cols2:
                await db.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0")
                await db.execute("ALTER TABLE users ADD COLUMN verification_code TEXT")
                await db.execute("ALTER TABLE users ADD COLUMN verification_expires TEXT")
                await db.execute("UPDATE users SET email_verified = 1 WHERE email_verified = 0")
                await db.commit()
                logger.info("Migration: added email verification columns, grandfathered existing users")
        else:
            for col, col_type, default in [
                ("email_verified", "INTEGER", "0"),
                ("verification_code", "VARCHAR(10)", None),
                ("verification_expires", "TEXT", None),
            ]:
                default_clause = f" DEFAULT {default}" if default else ""
                await db.execute(f"""
                    DO $$ BEGIN
                        ALTER TABLE users ADD COLUMN {col} {col_type}{default_clause};
                    EXCEPTION WHEN duplicate_column THEN NULL;
                    END $$;
                """)
            await db.execute("UPDATE users SET email_verified = 1 WHERE email_verified = 0 AND verification_code IS NULL")
            await db.commit()

        # Migrate: add employee_id to projects table
        if db.backend_type == "sqlite":
            proj_cols = [r["name"] for r in await (await db.execute("PRAGMA table_info(projects)")).fetchall()]
            if "employee_id" not in proj_cols:
                await db.execute("ALTER TABLE projects ADD COLUMN employee_id TEXT")
                await db.commit()
                logger.info("Migration: added employee_id column to projects table")
        else:
            await db.execute("""
                DO $$ BEGIN
                    ALTER TABLE projects ADD COLUMN employee_id VARCHAR(255);
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
            """)
            await db.commit()

        # Migrate: add template_id to employees table
        if db.backend_type == "sqlite":
            emp_cols = [r["name"] for r in await (await db.execute("PRAGMA table_info(employees)")).fetchall()]
            if "template_id" not in emp_cols:
                await db.execute("ALTER TABLE employees ADD COLUMN template_id TEXT")
                await db.commit()
                logger.info("Migration: added template_id column to employees table")
        else:
            await db.execute("""
                DO $$ BEGIN
                    ALTER TABLE employees ADD COLUMN template_id VARCHAR(255);
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
            """)
            await db.commit()

        # Unique index on (user_id, template_id) — must run after migration ensures column exists
        if db.backend_type == "sqlite":
            await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_employees_user_template ON employees(user_id, template_id) WHERE template_id IS NOT NULL")
        else:
            await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_employees_user_template ON employees(user_id, template_id) WHERE template_id IS NOT NULL")
        await db.commit()

        # Performance indexes on frequently queried columns
        index_stmts = [
            "CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_agent_outputs_project_id ON agent_outputs(project_id)",
            "CREATE INDEX IF NOT EXISTS idx_executions_project_id ON executions(project_id)",
            "CREATE INDEX IF NOT EXISTS idx_cost_tracking_project_id ON cost_tracking(project_id)",
            "CREATE INDEX IF NOT EXISTS idx_shared_memory_project_id ON shared_memory(project_id)",
            "CREATE INDEX IF NOT EXISTS idx_domain_learnings_project_id ON domain_learnings(project_id)",
            "CREATE INDEX IF NOT EXISTS idx_share_links_project_id ON share_links(project_id)",
        ]
        for stmt in index_stmts:
            await db.execute(stmt)
        await db.commit()
        logger.info("Database indexes ensured")
    finally:
        await db.close()

    try:
        from app.services.startup_recovery import recover_orphaned_executions
        await recover_orphaned_executions(stale_threshold_seconds=30)
    except Exception as rec_err:
        logger.warning(f"Startup crash recovery notice: {rec_err}")

    try:
        from app.core.default_team import seed_default_templates
        count = await seed_default_templates()
        logger.info(f"Employee template seeding complete: {count} templates")
    except Exception as seed_err:
        logger.warning(f"Employee template seeding notice: {seed_err}")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:16]


# --- USER DATABASE FUNCTIONS ---

async def create_user(email: str, password_hash: str, verification_code: str | None = None, verification_expires: str | None = None) -> dict:
    db = await get_db()
    try:
        user_id = new_id()
        ts = now_iso()
        norm_email = email.strip().lower()
        await db.execute(
            "INSERT INTO users (id, email, password_hash, created_at, email_verified, verification_code, verification_expires) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, norm_email, password_hash, ts, 0, verification_code, verification_expires),
        )
        await db.commit()
        return {"id": user_id, "email": norm_email, "created_at": ts, "email_verified": False}
    finally:
        await db.close()


async def set_user_verified(user_id: str) -> None:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE users SET email_verified = 1, verification_code = NULL, verification_expires = NULL WHERE id = ?",
            (user_id,),
        )
        await db.commit()
    finally:
        await db.close()


async def set_verification_code(user_id: str, code: str, expires: str) -> None:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE users SET verification_code = ?, verification_expires = ? WHERE id = ?",
            (code, expires, user_id),
        )
        await db.commit()
    finally:
        await db.close()


async def get_user_verification(email: str) -> dict | None:
    db = await get_db()
    try:
        norm_email = email.strip().lower()
        cursor = await db.execute(
            "SELECT id, email, email_verified, verification_code, verification_expires FROM users WHERE email = ?",
            (norm_email,),
        )
        row = await cursor.fetchone()
        return row
    finally:
        await db.close()


async def get_user_by_email(email: str) -> dict | None:
    db = await get_db()
    try:
        norm_email = email.strip().lower()
        cursor = await db.execute("SELECT * FROM users WHERE email = ?", (norm_email,))
        row = await cursor.fetchone()
        return row
    finally:
        await db.close()


async def get_user_by_id(user_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, email, created_at, oauth_provider, display_name, avatar_url FROM users WHERE id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row
    finally:
        await db.close()


async def get_user_by_oauth(provider: str, provider_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, email, created_at, oauth_provider, display_name, avatar_url "
            "FROM users WHERE oauth_provider = ? AND oauth_provider_id = ?",
            (provider, provider_id),
        )
        return await cursor.fetchone()
    finally:
        await db.close()


async def create_oauth_user(
    email: str, provider: str, provider_id: str,
    display_name: str | None = None, avatar_url: str | None = None,
) -> dict:
    db = await get_db()
    try:
        user_id = new_id()
        ts = now_iso()
        norm_email = email.strip().lower()
        await db.execute(
            "INSERT INTO users (id, email, password_hash, created_at, "
            "oauth_provider, oauth_provider_id, display_name, avatar_url) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, norm_email, "oauth:no_password", ts,
             provider, provider_id, display_name, avatar_url),
        )
        await db.commit()
        return {
            "id": user_id, "email": norm_email, "created_at": ts,
            "display_name": display_name, "avatar_url": avatar_url,
            "oauth_provider": provider,
        }
    finally:
        await db.close()


async def link_oauth_to_user(
    user_id: str, provider: str, provider_id: str,
    display_name: str | None = None, avatar_url: str | None = None,
):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE users SET oauth_provider = ?, oauth_provider_id = ?, "
            "display_name = COALESCE(?, display_name), "
            "avatar_url = COALESCE(?, avatar_url) WHERE id = ?",
            (provider, provider_id, display_name, avatar_url, user_id),
        )
        await db.commit()
    finally:
        await db.close()


# --- PROJECT DATABASE FUNCTIONS ---

async def create_project(problem_statement: str, user_id: str = "legacy_owner") -> dict:
    db = await get_db()
    try:
        project_id = new_id()
        ts = now_iso()
        await db.execute(
            "INSERT INTO projects (id, problem_statement, status, user_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, problem_statement, "created", user_id, ts, ts),
        )
        await db.commit()
        return {
            "id": project_id,
            "problem_statement": problem_statement,
            "status": "created",
            "user_id": user_id,
            "created_at": ts,
            "updated_at": ts
        }
    finally:
        await db.close()


async def get_project(project_id: str, user_id: str | None = None) -> dict | None:
    db = await get_db()
    try:
        if user_id:
            cursor = await db.execute("SELECT * FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id))
        else:
            cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = await cursor.fetchone()
        return row
    finally:
        await db.close()


async def get_project_for_user(project_id: str, user_id: str) -> dict | None:
    return await get_project(project_id, user_id=user_id)


async def delete_project(project_id: str, user_id: str) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT id FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id))
        if not await cursor.fetchone():
            return False
        
        await db.execute("DELETE FROM execution_events WHERE project_id = ?", (project_id,))
        await db.execute("DELETE FROM shared_memory WHERE project_id = ?", (project_id,))
        await db.execute("DELETE FROM conversations WHERE project_id = ?", (project_id,))
        await db.execute("DELETE FROM agent_outputs WHERE project_id = ?", (project_id,))
        await db.execute("DELETE FROM executions WHERE project_id = ?", (project_id,))
        await db.execute("DELETE FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id))
        await db.commit()
        return True
    finally:
        await db.close()


async def rename_project(project_id: str, user_id: str, new_name: str) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT id FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id))
        if not await cursor.fetchone():
            return False
        await db.execute(
            "UPDATE projects SET problem_statement = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (new_name, now_iso(), project_id, user_id),
        )
        await db.commit()
        return True
    finally:
        await db.close()


async def update_project_status(project_id: str, status: str):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE projects SET status = ?, updated_at = ? WHERE id = ?",
            (status, now_iso(), project_id),
        )
        await db.commit()
    finally:
        await db.close()


async def save_agent_output(project_id: str, role: str, content: dict) -> dict:
    db = await get_db()
    try:
        output_id = new_id()
        ts = now_iso()
        content_str = json.dumps(content) if isinstance(content, dict) else str(content)
        await db.execute(
            "INSERT INTO agent_outputs (id, project_id, role, content, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (output_id, project_id, role, content_str, "pending", ts),
        )
        await db.commit()
        return {"id": output_id, "project_id": project_id, "role": role, "content": content, "status": "pending", "created_at": ts}
    finally:
        await db.close()


async def update_output_status(output_id: str, status: str):
    db = await get_db()
    try:
        await db.execute("UPDATE agent_outputs SET status = ? WHERE id = ?", (status, output_id))
        await db.commit()
    finally:
        await db.close()


async def update_output_status_atomic(
    output_id: str,
    project_id: str,
    new_status: str,
    expected_status: str = "pending",
) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE agent_outputs SET status = ? WHERE id = ? AND project_id = ? AND status = ?",
            (new_status, output_id, project_id, expected_status),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def update_agent_output_content(output_id: str, project_id: str, content: dict) -> bool:
    db = await get_db()
    try:
        content_str = json.dumps(content) if isinstance(content, dict) else str(content)
        cursor = await db.execute(
            "UPDATE agent_outputs SET content = ? WHERE id = ? AND project_id = ?",
            (content_str, output_id, project_id),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def get_project_outputs(project_id: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM agent_outputs WHERE project_id = ? ORDER BY created_at", (project_id,)
        )
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            d = dict(row)
            if isinstance(d.get("content"), str):
                try:
                    d["content"] = json.loads(d["content"])
                except Exception:
                    pass
            results.append(d)
        return results
    finally:
        await db.close()


async def get_latest_output(project_id: str, role: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM agent_outputs WHERE project_id = ? AND role = ? ORDER BY created_at DESC LIMIT 1",
            (project_id, role),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        if isinstance(d.get("content"), str):
            try:
                d["content"] = json.loads(d["content"])
            except Exception:
                pass
        return d
    finally:
        await db.close()


async def set_memory(project_id: str, key: str, value: str, updated_by: str):
    db = await get_db()
    try:
        mem_id = new_id()
        ts = now_iso()
        if db.backend_type == "sqlite":
            await db.execute(
                """INSERT INTO shared_memory (id, project_id, key, value, updated_by, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(project_id, key) DO UPDATE SET value = ?, updated_by = ?, updated_at = ?""",
                (mem_id, project_id, key, value, updated_by, ts, value, updated_by, ts),
            )
        else:
            await db.execute(
                """INSERT INTO shared_memory (id, project_id, key, value, updated_by, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT (project_id, key) DO UPDATE SET value = EXCLUDED.value, updated_by = EXCLUDED.updated_by, updated_at = EXCLUDED.updated_at""",
                (mem_id, project_id, key, value, updated_by, ts),
            )
        await db.commit()
    finally:
        await db.close()


async def get_memory(project_id: str) -> dict[str, str]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT key, value FROM shared_memory WHERE project_id = ?", (project_id,)
        )
        rows = await cursor.fetchall()
        return {row["key"]: row["value"] for row in rows}
    finally:
        await db.close()


async def save_conversation(project_id: str, agent_role: str, messages: list[dict]):
    db = await get_db()
    try:
        conv_id = new_id()
        ts = now_iso()
        msgs_str = json.dumps(messages) if isinstance(messages, list) else str(messages)
        if db.backend_type == "sqlite":
            await db.execute(
                """INSERT INTO conversations (id, project_id, agent_role, messages, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT DO NOTHING""",
                (conv_id, project_id, agent_role, msgs_str, ts),
            )
            await db.execute(
                """UPDATE conversations SET messages = ?, updated_at = ?
                   WHERE project_id = ? AND agent_role = ?""",
                (msgs_str, ts, project_id, agent_role),
            )
        else:
            await db.execute(
                """INSERT INTO conversations (id, project_id, agent_role, messages, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT (project_id, agent_role) DO UPDATE SET messages = EXCLUDED.messages, updated_at = EXCLUDED.updated_at""",
                (conv_id, project_id, agent_role, msgs_str, ts),
            )
        await db.commit()
    finally:
        await db.close()


async def get_conversation(project_id: str, agent_role: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT messages FROM conversations WHERE project_id = ? AND agent_role = ?",
            (project_id, agent_role),
        )
        row = await cursor.fetchone()
        if not row:
            return []
        msgs = row["messages"]
        if isinstance(msgs, str):
            return json.loads(msgs)
        return msgs
    finally:
        await db.close()


async def list_projects(user_id: str | None = None) -> list[dict]:
    db = await get_db()
    try:
        if user_id:
            cursor = await db.execute("SELECT * FROM projects WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        else:
            cursor = await db.execute("SELECT * FROM projects ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return rows
    finally:
        await db.close()


async def create_share_link(project_id: str, token: str) -> dict:
    db = await get_db()
    try:
        link_id = new_id()
        ts = now_iso()
        await db.execute(
            "INSERT INTO share_links (id, project_id, token, created_at) VALUES (?, ?, ?, ?)",
            (link_id, project_id, token, ts),
        )
        await db.commit()
        return {"id": link_id, "project_id": project_id, "token": token, "created_at": ts}
    finally:
        await db.close()


async def get_project_by_share_token(token: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT p.* FROM projects p JOIN share_links sl ON p.id = sl.project_id WHERE sl.token = ?",
            (token,),
        )
        return await cursor.fetchone()
    finally:
        await db.close()


# --- DOMAIN LEARNINGS (cross-project memory) ---

async def save_domain_learning(project_id: str, category: str, domain: str, title: str, content: str, source_role: str) -> dict:
    db = await get_db()
    try:
        learning_id = new_id()
        ts = now_iso()
        await db.execute(
            "INSERT INTO domain_learnings (id, project_id, category, domain, title, content, source_role, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (learning_id, project_id, category, domain, title, content, source_role, ts),
        )
        await db.commit()
        return {"id": learning_id, "project_id": project_id, "category": category, "domain": domain, "title": title, "content": content}
    finally:
        await db.close()


async def query_domain_learnings(keywords: list[str], exclude_project_id: str | None = None, limit: int = 10, user_id: str | None = None) -> list[dict]:
    db = await get_db()
    try:
        conditions = []
        params = []
        for kw in keywords:
            conditions.append("(LOWER(dl.domain) LIKE ? OR LOWER(dl.title) LIKE ? OR LOWER(dl.content) LIKE ?)")
            pattern = f"%{kw.lower()}%"
            params.extend([pattern, pattern, pattern])
        where = " OR ".join(conditions) if conditions else "1=1"
        if exclude_project_id:
            where = f"({where}) AND dl.project_id != ?"
            params.append(exclude_project_id)
        if user_id:
            where = f"({where}) AND p.user_id = ?"
            params.append(user_id)
        cursor = await db.execute(
            f"SELECT dl.* FROM domain_learnings dl JOIN projects p ON dl.project_id = p.id WHERE {where} ORDER BY dl.created_at DESC LIMIT ?",
            (*params, limit),
        )
        return await cursor.fetchall()
    finally:
        await db.close()


async def get_project_learnings(project_id: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM domain_learnings WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        )
        return await cursor.fetchall()
    finally:
        await db.close()


async def set_user_setting(user_id: str, key: str, value: str):
    db = await get_db()
    try:
        ts = now_iso()
        await db.execute(
            "INSERT INTO user_settings (user_id, key, value, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id, key) DO UPDATE SET value = ?, updated_at = ?",
            (user_id, key, value, ts, value, ts),
        )
        await db.commit()
    finally:
        await db.close()


async def get_user_setting(user_id: str, key: str) -> str | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT value FROM user_settings WHERE user_id = ? AND key = ?",
            (user_id, key),
        )
        row = await cursor.fetchone()
        return row["value"] if row else None
    finally:
        await db.close()


# --- COST TRACKING ---

async def record_cost(
    project_id: str,
    role: str,
    model: str,
    provider: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    estimated_cost: float,
    call_type: str = "agent",
) -> dict:
    db = await get_db()
    try:
        cost_id = new_id()
        ts = now_iso()
        await db.execute(
            """INSERT INTO cost_tracking
               (id, project_id, role, model, provider, prompt_tokens, completion_tokens, total_tokens, estimated_cost, call_type, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (cost_id, project_id, role, model, provider, prompt_tokens, completion_tokens, total_tokens, estimated_cost, call_type, ts),
        )
        await db.commit()
        return {
            "id": cost_id, "project_id": project_id, "role": role, "model": model,
            "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
            "total_tokens": total_tokens, "estimated_cost": estimated_cost,
            "call_type": call_type, "created_at": ts,
        }
    finally:
        await db.close()


async def get_project_costs(project_id: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM cost_tracking WHERE project_id = ? ORDER BY created_at ASC",
            (project_id,),
        )
        return await cursor.fetchall()
    finally:
        await db.close()


async def get_project_cost_summary(project_id: str) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT
                 COUNT(*) as total_calls,
                 COALESCE(SUM(prompt_tokens), 0) as total_prompt_tokens,
                 COALESCE(SUM(completion_tokens), 0) as total_completion_tokens,
                 COALESCE(SUM(total_tokens), 0) as total_tokens,
                 COALESCE(SUM(estimated_cost), 0.0) as total_cost
               FROM cost_tracking WHERE project_id = ?""",
            (project_id,),
        )
        summary = await cursor.fetchone()

        cursor2 = await db.execute(
            """SELECT role,
                 COUNT(*) as calls,
                 COALESCE(SUM(prompt_tokens), 0) as prompt_tokens,
                 COALESCE(SUM(completion_tokens), 0) as completion_tokens,
                 COALESCE(SUM(total_tokens), 0) as total_tokens,
                 COALESCE(SUM(estimated_cost), 0.0) as estimated_cost,
                 MAX(model) as model
               FROM cost_tracking WHERE project_id = ?
               GROUP BY role ORDER BY MIN(created_at) ASC""",
            (project_id,),
        )
        per_agent = await cursor2.fetchall()

        return {
            "project_id": project_id,
            "totals": dict(summary) if summary else {},
            "per_agent": [dict(r) for r in per_agent],
        }
    finally:
        await db.close()


async def save_execution_event(project_id: str, execution_id: Optional[str], seq: int, event_type: str, data: dict) -> dict:
    db = await get_db()
    try:
        event_id = new_id()
        ts = now_iso()
        data_json = json.dumps(data)
        if db.backend_type == "sqlite":
            await db.execute(
                """INSERT INTO execution_events (id, project_id, execution_id, seq, event_type, data, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(project_id, seq) DO NOTHING""",
                (event_id, project_id, execution_id or "", seq, event_type, data_json, ts)
            )
        else:
            await db.execute(
                """INSERT INTO execution_events (id, project_id, execution_id, seq, event_type, data, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT (project_id, seq) DO NOTHING""",
                (event_id, project_id, execution_id or "", seq, event_type, data_json, ts)
            )
        await db.commit()
        return {
            "id": event_id,
            "project_id": project_id,
            "execution_id": execution_id or "",
            "seq": seq,
            "event_type": event_type,
            "data": data,
            "created_at": ts
        }
    finally:
        await db.close()


async def get_execution_events_since(project_id: str, last_seq: int = 0) -> List[dict]:
    db = await get_db()
    try:
        cur = await db.execute(
            """SELECT id, project_id, execution_id, seq, event_type, data, created_at
               FROM execution_events
               WHERE project_id = ? AND seq > ?
               ORDER BY seq ASC""",
            (project_id, last_seq)
        )
        rows = await cur.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                if isinstance(d.get("data"), str):
                    d["data"] = json.loads(d["data"])
            except Exception:
                pass
            result.append(d)
        return result
    finally:
        await db.close()


async def claim_and_recover_stale_executions(stale_running_seconds: int = 30, stale_queued_seconds: int = 300) -> List[dict]:
    """
    Atomically claims and recovers stale RUNNING, CANCELLING, and QUEUED executions across PostgreSQL and SQLite.
    Prevents race conditions when multiple recovery workers run concurrently.
    """
    db = await get_db()
    try:
        now = datetime.now(timezone.utc)
        running_cutoff = (now - timedelta(seconds=stale_running_seconds)).isoformat()
        queued_cutoff = (now - timedelta(seconds=stale_queued_seconds)).isoformat()

        claimed = []
        if db.backend_type == "postgres":
            # Intentionally bypasses DBWrapper.execute() to use PostgreSQL-specific
            # FOR UPDATE SKIP LOCKED + subquery + RETURNING — features with no SQLite
            # equivalent. The SQL uses native $N positional placeholders directly.
            sql = """
                UPDATE executions
                SET status = CASE 
                        WHEN status = 'CANCELLING' THEN 'CANCELLED'
                        ELSE 'RECOVERABLE'
                    END,
                    completed_at = $1
                WHERE id IN (
                    SELECT id FROM executions
                    WHERE (status IN ('RUNNING', 'CANCELLING') AND (last_heartbeat IS NULL OR last_heartbeat < $2))
                       OR (status = 'QUEUED' AND created_at < $3)
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING id, project_id, status, user_id;
            """
            rows = await db.conn.fetch(sql, now.isoformat(), running_cutoff, queued_cutoff)
            claimed = [dict(r) for r in rows]
        else:
            cur = await db.execute(
                """SELECT id, project_id, status, user_id FROM executions
                   WHERE (status IN ('RUNNING', 'CANCELLING') AND (last_heartbeat IS NULL OR last_heartbeat < ?))
                      OR (status = 'QUEUED' AND created_at < ?)""",
                (running_cutoff, queued_cutoff)
            )
            rows = await cur.fetchall()
            for r in rows:
                exec_id = r["id"]
                proj_id = r["project_id"]
                st = r["status"]
                new_st = "CANCELLED" if st == "CANCELLING" else "RECOVERABLE"
                await db.execute(
                    "UPDATE executions SET status = ?, completed_at = ? WHERE id = ? AND status = ?",
                    (new_st, now.isoformat(), exec_id, st)
                )
                claimed.append({"id": exec_id, "project_id": proj_id, "status": new_st, "user_id": r["user_id"]})

        if claimed:
            for c in claimed:
                p_id = c["project_id"]
                await db.execute(
                    "UPDATE projects SET status = ?, updated_at = ? WHERE id = ? AND status NOT IN ('completed', 'failed', 'cancelled')",
                    ("failed", now.isoformat(), p_id)
                )
            await db.commit()
        return claimed
    finally:
        await db.close()


# --- EMPLOYEE DATABASE FUNCTIONS ---

async def create_employee(user_id: str, name: str, role: str, persona: str | None = None,
                          avatar_url: str | None = None, config: dict | None = None,
                          template_id: str | None = None) -> dict:
    db = await get_db()
    try:
        eid = new_id()
        ts = now_iso()
        config_json = json.dumps(config) if config else None
        await db.execute(
            """INSERT INTO employees (id, user_id, template_id, name, role, persona, avatar_url, status, config, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'idle', ?, ?, ?)""",
            (eid, user_id, template_id, name, role, persona, avatar_url, config_json, ts, ts),
        )
        await db.commit()
        return {"id": eid, "user_id": user_id, "template_id": template_id, "name": name, "role": role,
                "persona": persona, "avatar_url": avatar_url, "status": "idle", "config": config,
                "created_at": ts, "updated_at": ts}
    finally:
        await db.close()


async def list_employees(user_id: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM employees WHERE user_id = ? AND status != 'archived' ORDER BY created_at ASC",
            (user_id,),
        )
        rows = await cursor.fetchall()
        for r in rows:
            if isinstance(r.get("config"), str):
                try:
                    r["config"] = json.loads(r["config"])
                except Exception:
                    pass
        return rows
    finally:
        await db.close()


async def get_employee_stats(user_id: str) -> dict[str, dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT employee_id, COUNT(*) as session_count, MAX(started_at) as last_active "
            "FROM employee_sessions WHERE employee_id IN "
            "(SELECT id FROM employees WHERE user_id = ?) GROUP BY employee_id",
            (user_id,),
        )
        session_rows = await cursor.fetchall()
        cursor = await db.execute(
            "SELECT employee_id, COUNT(*) as memory_count "
            "FROM memories WHERE employee_id IN "
            "(SELECT id FROM employees WHERE user_id = ?) AND is_active = 1 GROUP BY employee_id",
            (user_id,),
        )
        memory_rows = await cursor.fetchall()

        stats: dict[str, dict] = {}
        for r in session_rows:
            stats[r["employee_id"]] = {"session_count": r["session_count"], "last_active": r["last_active"]}
        for r in memory_rows:
            if r["employee_id"] not in stats:
                stats[r["employee_id"]] = {}
            stats[r["employee_id"]]["memory_count"] = r["memory_count"]
        return stats
    finally:
        await db.close()


async def get_employee(employee_id: str, user_id: str | None = None) -> dict | None:
    db = await get_db()
    try:
        if user_id:
            cursor = await db.execute(
                "SELECT * FROM employees WHERE id = ? AND user_id = ?", (employee_id, user_id))
        else:
            cursor = await db.execute("SELECT * FROM employees WHERE id = ?", (employee_id,))
        row = await cursor.fetchone()
        if row and isinstance(row.get("config"), str):
            try:
                row["config"] = json.loads(row["config"])
            except Exception:
                pass
        return row
    finally:
        await db.close()


async def update_employee(employee_id: str, user_id: str, updates: dict) -> dict | None:
    db = await get_db()
    try:
        allowed = {"name", "role", "persona", "avatar_url", "status", "config"}
        parts, vals = [], []
        for k, v in updates.items():
            if k not in allowed:
                continue
            if k == "config" and isinstance(v, dict):
                v = json.dumps(v)
            parts.append(f"{k} = ?")
            vals.append(v)
        if not parts:
            return await get_employee(employee_id, user_id)
        parts.append("updated_at = ?")
        vals.append(now_iso())
        vals.extend([employee_id, user_id])
        await db.execute(
            f"UPDATE employees SET {', '.join(parts)} WHERE id = ? AND user_id = ?", tuple(vals))
        await db.commit()
        return await get_employee(employee_id, user_id)
    finally:
        await db.close()


async def archive_employee(employee_id: str, user_id: str) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE employees SET status = 'archived', updated_at = ? WHERE id = ? AND user_id = ?",
            (now_iso(), employee_id, user_id))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


# --- EMPLOYEE SESSION FUNCTIONS ---

async def create_employee_session(employee_id: str, project_id: str | None = None) -> dict:
    db = await get_db()
    try:
        sid = new_id()
        ts = now_iso()
        await db.execute(
            """INSERT INTO employee_sessions (id, employee_id, project_id, status, started_at, last_activity)
               VALUES (?, ?, ?, 'active', ?, ?)""",
            (sid, employee_id, project_id, ts, ts),
        )
        await db.commit()
        return {"id": sid, "employee_id": employee_id, "project_id": project_id,
                "status": "active", "summary": None, "started_at": ts, "ended_at": None, "last_activity": ts}
    finally:
        await db.close()


async def list_employee_sessions(employee_id: str, limit: int = 20) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM employee_sessions WHERE employee_id = ? ORDER BY started_at DESC LIMIT ?",
            (employee_id, limit),
        )
        return await cursor.fetchall()
    finally:
        await db.close()


async def get_session(session_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM employee_sessions WHERE id = ?", (session_id,))
        return await cursor.fetchone()
    finally:
        await db.close()


async def update_session(session_id: str, updates: dict) -> None:
    db = await get_db()
    try:
        allowed = {"status", "summary", "ended_at", "last_activity", "project_id"}
        parts, vals = [], []
        for k, v in updates.items():
            if k in allowed:
                parts.append(f"{k} = ?")
                vals.append(v)
        if not parts:
            return
        vals.append(session_id)
        await db.execute(f"UPDATE employee_sessions SET {', '.join(parts)} WHERE id = ?", tuple(vals))
        await db.commit()
    finally:
        await db.close()


async def get_or_create_active_session(employee_id: str) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM employee_sessions WHERE employee_id = ? AND status = 'active' ORDER BY started_at DESC LIMIT 1",
            (employee_id,),
        )
        row = await cursor.fetchone()
        if row:
            return row
    finally:
        await db.close()
    return await create_employee_session(employee_id)


# --- SESSION MESSAGE FUNCTIONS ---

async def add_session_message(session_id: str, role: str, content: str,
                              tool_calls: list | None = None, tool_results: list | None = None) -> dict:
    db = await get_db()
    try:
        mid = new_id()
        ts = now_iso()
        tc_json = json.dumps(tool_calls) if tool_calls else None
        tr_json = json.dumps(tool_results) if tool_results else None
        await db.execute(
            """INSERT INTO session_messages (id, session_id, role, content, tool_calls, tool_results, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (mid, session_id, role, content, tc_json, tr_json, ts),
        )
        await db.execute(
            "UPDATE employee_sessions SET last_activity = ? WHERE id = ?", (ts, session_id))
        await db.commit()
        return {"id": mid, "session_id": session_id, "role": role, "content": content,
                "tool_calls": tool_calls, "tool_results": tool_results, "created_at": ts}
    finally:
        await db.close()


async def get_session_messages(session_id: str, limit: int = 100) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM session_messages WHERE session_id = ? ORDER BY created_at ASC LIMIT ?",
            (session_id, limit),
        )
        rows = await cursor.fetchall()
        for r in rows:
            for field in ("tool_calls", "tool_results"):
                if isinstance(r.get(field), str):
                    try:
                        r[field] = json.loads(r[field])
                    except Exception:
                        pass
        return rows
    finally:
        await db.close()


# --- MEMORY FUNCTIONS ---

async def create_memory(employee_id: str, mem_type: str, content: str,
                        source: str | None = None, source_id: str | None = None,
                        confidence: float = 0.8, importance: float = 0.5,
                        tags: list[str] | None = None, stale_after: str | None = None) -> dict:
    db = await get_db()
    try:
        mid = new_id()
        ts = now_iso()
        tags_json = json.dumps(tags) if tags else None
        await db.execute(
            """INSERT INTO memories (id, employee_id, type, content, source, source_id,
               confidence, importance, tags, created_at, last_accessed, stale_after, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (mid, employee_id, mem_type, content, source, source_id,
             confidence, importance, tags_json, ts, ts, stale_after),
        )
        await db.commit()
        return {"id": mid, "employee_id": employee_id, "type": mem_type, "content": content,
                "source": source, "confidence": confidence, "importance": importance,
                "tags": tags, "created_at": ts, "is_active": True}
    finally:
        await db.close()


async def list_memories(employee_id: str, mem_type: str | None = None,
                        search: str | None = None, limit: int = 50) -> list[dict]:
    db = await get_db()
    try:
        sql = "SELECT * FROM memories WHERE employee_id = ? AND is_active = 1"
        params: list = [employee_id]
        if mem_type:
            sql += " AND type = ?"
            params.append(mem_type)
        if search:
            sql += " AND (content LIKE ? OR tags LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        sql += " ORDER BY importance DESC, created_at DESC LIMIT ?"
        params.append(limit)
        cursor = await db.execute(sql, tuple(params))
        rows = await cursor.fetchall()
        for r in rows:
            if isinstance(r.get("tags"), str):
                try:
                    r["tags"] = json.loads(r["tags"])
                except Exception:
                    pass
        return rows
    finally:
        await db.close()


async def update_memory(memory_id: str, updates: dict) -> dict | None:
    db = await get_db()
    try:
        allowed = {"content", "confidence", "importance", "tags", "stale_after", "is_active", "superseded_by", "last_verified"}
        parts, vals = [], []
        for k, v in updates.items():
            if k not in allowed:
                continue
            if k == "tags" and isinstance(v, list):
                v = json.dumps(v)
            parts.append(f"{k} = ?")
            vals.append(v)
        if not parts:
            return None
        vals.append(memory_id)
        await db.execute(f"UPDATE memories SET {', '.join(parts)} WHERE id = ?", tuple(vals))
        await db.commit()
        cursor = await db.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        row = await cursor.fetchone()
        if row and isinstance(row.get("tags"), str):
            try:
                row["tags"] = json.loads(row["tags"])
            except Exception:
                pass
        return row
    finally:
        await db.close()


async def deactivate_memory(memory_id: str) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE memories SET is_active = 0 WHERE id = ?", (memory_id,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def retrieve_memories_for_context(employee_id: str, query: str | None = None, limit: int = 15) -> list[dict]:
    if query:
        try:
            emb_count_db = await get_db()
            try:
                cursor = await emb_count_db.execute(
                    "SELECT COUNT(*) as cnt FROM memory_embeddings WHERE employee_id = ?",
                    (employee_id,))
                row = await cursor.fetchone()
                has_embeddings = row and row["cnt"] > 0
            finally:
                await emb_count_db.close()

            if has_embeddings:
                from app.core.embeddings import embed_text
                query_vec = embed_text(query)
                semantic_results = await semantic_memory_search(employee_id, query_vec, limit=limit)
                if semantic_results:
                    now = now_iso()
                    db2 = await get_db()
                    try:
                        for sr in semantic_results:
                            await db2.execute("UPDATE memories SET last_accessed = ? WHERE id = ?",
                                              (now, sr["memory_id"]))
                        await db2.commit()
                    finally:
                        await db2.close()
                    return semantic_results
        except Exception:
            pass

    db = await get_db()
    try:
        now = now_iso()
        sql = "SELECT * FROM memories WHERE employee_id = ? AND is_active = 1 AND (stale_after IS NULL OR stale_after > ?)"
        params: list = [employee_id, now]
        if query:
            sql += " AND (content LIKE ? OR tags LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%"])
        sql += " ORDER BY importance DESC, confidence DESC, created_at DESC LIMIT ?"
        params.append(limit)
        cursor = await db.execute(sql, tuple(params))
        rows = await cursor.fetchall()
        for r in rows:
            if isinstance(r.get("tags"), str):
                try:
                    r["tags"] = json.loads(r["tags"])
                except Exception:
                    pass
        if rows:
            mem_ids = [r["id"] for r in rows]
            for mid in mem_ids:
                await db.execute("UPDATE memories SET last_accessed = ? WHERE id = ?", (now, mid))
            await db.commit()
        return rows
    finally:
        await db.close()


# --- SKILL FUNCTIONS ---

async def create_skill(employee_id: str, name: str, description: str,
                       procedure: str, trigger_pattern: str | None = None,
                       examples: list[str] | None = None) -> dict:
    db = await get_db()
    try:
        sid = new_id()
        ts = now_iso()
        examples_json = json.dumps(examples) if examples else None
        await db.execute(
            """INSERT INTO employee_skills (id, employee_id, name, description, trigger_pattern,
               procedure, examples, created_at, is_active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (sid, employee_id, name, description, trigger_pattern, procedure, examples_json, ts),
        )
        await db.commit()
        return {"id": sid, "employee_id": employee_id, "name": name,
                "description": description, "procedure": procedure,
                "trigger_pattern": trigger_pattern, "examples": examples,
                "times_used": 0, "success_rate": 1.0, "created_at": ts, "is_active": True}
    finally:
        await db.close()


async def list_skills(employee_id: str, active_only: bool = True) -> list[dict]:
    db = await get_db()
    try:
        sql = "SELECT * FROM employee_skills WHERE employee_id = ?"
        params: list = [employee_id]
        if active_only:
            sql += " AND is_active = 1"
        sql += " ORDER BY times_used DESC, success_rate DESC"
        cursor = await db.execute(sql, tuple(params))
        rows = await cursor.fetchall()
        for r in rows:
            if isinstance(r.get("examples"), str):
                try:
                    r["examples"] = json.loads(r["examples"])
                except Exception:
                    pass
        return rows
    finally:
        await db.close()


async def get_skill(skill_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM employee_skills WHERE id = ?", (skill_id,))
        row = await cursor.fetchone()
        if row and isinstance(row.get("examples"), str):
            try:
                row["examples"] = json.loads(row["examples"])
            except Exception:
                pass
        return row
    finally:
        await db.close()


async def record_skill_usage(skill_id: str, success: bool = True):
    db = await get_db()
    try:
        skill = await get_skill(skill_id)
        if not skill:
            return
        new_used = skill["times_used"] + 1
        old_rate = skill["success_rate"]
        new_rate = round(((old_rate * skill["times_used"]) + (1.0 if success else 0.0)) / new_used, 3)
        await db.execute(
            "UPDATE employee_skills SET times_used = ?, success_rate = ?, last_used = ? WHERE id = ?",
            (new_used, new_rate, now_iso(), skill_id),
        )
        await db.commit()
    finally:
        await db.close()


async def deactivate_skill(skill_id: str) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "UPDATE employee_skills SET is_active = 0 WHERE id = ?", (skill_id,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def retrieve_skills_for_context(employee_id: str, query: str | None = None, limit: int = 5) -> list[dict]:
    db = await get_db()
    try:
        sql = "SELECT * FROM employee_skills WHERE employee_id = ? AND is_active = 1"
        params: list = [employee_id]
        if query:
            sql += " AND (name LIKE ? OR description LIKE ? OR trigger_pattern LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])
        sql += " ORDER BY times_used DESC, success_rate DESC LIMIT ?"
        params.append(limit)
        cursor = await db.execute(sql, tuple(params))
        rows = await cursor.fetchall()
        for r in rows:
            if isinstance(r.get("examples"), str):
                try:
                    r["examples"] = json.loads(r["examples"])
                except Exception:
                    pass
        if rows:
            ts = now_iso()
            for r in rows:
                await db.execute("UPDATE employee_skills SET last_used = ? WHERE id = ?", (ts, r["id"]))
            await db.commit()
        return rows
    finally:
        await db.close()


# --- TOOL PERMISSION FUNCTIONS ---

DEFAULT_PERMISSIONS = [
    ("github", "read", "allow"), ("github", "write", "ask"), ("github", "delete", "deny"),
    ("e2b", "read", "allow"), ("e2b", "write", "allow"), ("e2b", "execute", "allow"),
    ("terminal", "read", "allow"), ("terminal", "execute", "ask"),
    ("files", "read", "allow"), ("files", "write", "allow"), ("files", "delete", "ask"),
    ("database", "read", "allow"), ("database", "write", "ask"), ("database", "delete", "deny"),
    ("deploy", "read", "allow"), ("deploy", "execute", "deny"),
    ("web_search", "read", "allow"),
    ("notification", "execute", "ask"),
]


async def init_employee_permissions(employee_id: str, granted_by: str) -> None:
    db = await get_db()
    try:
        ts = now_iso()
        for tool, action, perm in DEFAULT_PERMISSIONS:
            pid = new_id()
            await db.execute(
                """INSERT OR IGNORE INTO tool_permissions (id, employee_id, tool, action, permission, granted_by, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (pid, employee_id, tool, action, perm, granted_by, ts),
            )
        await db.commit()
    finally:
        await db.close()


async def get_employee_permissions(employee_id: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM tool_permissions WHERE employee_id = ? ORDER BY tool, action",
            (employee_id,),
        )
        return await cursor.fetchall()
    finally:
        await db.close()


async def update_employee_permission(employee_id: str, tool: str, action: str, permission: str, granted_by: str) -> dict | None:
    db = await get_db()
    try:
        ts = now_iso()
        cursor = await db.execute(
            "UPDATE tool_permissions SET permission = ?, granted_by = ?, updated_at = ? WHERE employee_id = ? AND tool = ? AND action = ?",
            (permission, granted_by, ts, employee_id, tool, action),
        )
        await db.commit()
        if cursor.rowcount == 0:
            pid = new_id()
            await db.execute(
                """INSERT INTO tool_permissions (id, employee_id, tool, action, permission, granted_by, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (pid, employee_id, tool, action, permission, granted_by, ts),
            )
            await db.commit()
        cursor = await db.execute(
            "SELECT * FROM tool_permissions WHERE employee_id = ? AND tool = ? AND action = ?",
            (employee_id, tool, action),
        )
        return await cursor.fetchone()
    finally:
        await db.close()


async def check_permission(employee_id: str, tool: str, action: str) -> str:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT permission FROM tool_permissions WHERE employee_id = ? AND tool = ? AND action = ?",
            (employee_id, tool, action),
        )
        row = await cursor.fetchone()
        return row["permission"] if row else "ask"
    finally:
        await db.close()


# --- EMPLOYEE TEMPLATES ---

async def upsert_template(slug: str, name: str, role: str, description: str,
                           system_prompt: str, default_tools: list[str],
                           default_permissions: list[tuple[str, str, str]],
                           version: int = 1) -> dict:
    db = await get_db()
    try:
        ts = now_iso()
        tools_json = json.dumps(default_tools)
        perms_json = json.dumps(default_permissions)
        cursor = await db.execute("SELECT id, version FROM employee_templates WHERE slug = ?", (slug,))
        existing = await cursor.fetchone()
        if existing:
            if existing["version"] < version:
                await db.execute(
                    """UPDATE employee_templates SET name=?, role=?, description=?, system_prompt=?,
                       default_tools=?, default_permissions=?, version=?, updated_at=? WHERE slug=?""",
                    (name, role, description, system_prompt, tools_json, perms_json, version, ts, slug),
                )
                await db.commit()
            return {"id": existing["id"], "slug": slug, "version": version}
        tid = new_id()
        await db.execute(
            """INSERT INTO employee_templates (id, slug, name, role, description, system_prompt,
               default_tools, default_permissions, version, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (tid, slug, name, role, description, system_prompt, tools_json, perms_json, version, ts, ts),
        )
        await db.commit()
        return {"id": tid, "slug": slug, "version": version}
    finally:
        await db.close()


async def list_templates(active_only: bool = True) -> list[dict]:
    db = await get_db()
    try:
        q = "SELECT * FROM employee_templates"
        if active_only:
            q += " WHERE is_active = 1"
        q += " ORDER BY slug"
        cursor = await db.execute(q)
        rows = await cursor.fetchall()
        for row in rows:
            if row.get("default_tools") and isinstance(row["default_tools"], str):
                row["default_tools"] = json.loads(row["default_tools"])
            if row.get("default_permissions") and isinstance(row["default_permissions"], str):
                row["default_permissions"] = json.loads(row["default_permissions"])
        return rows
    finally:
        await db.close()


async def provision_default_team(user_id: str) -> list[dict]:
    """Idempotent: creates employees from active templates the user doesn't already have."""
    templates = await list_templates(active_only=True)
    if not templates:
        return []

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT template_id FROM employees WHERE user_id = ? AND template_id IS NOT NULL",
            (user_id,),
        )
        existing = {r["template_id"] for r in await cursor.fetchall()}
    finally:
        await db.close()

    created = []
    for tmpl in templates:
        if tmpl["id"] in existing:
            continue
        try:
            emp = await create_employee(
                user_id=user_id,
                name=tmpl["name"],
                role=tmpl["role"],
                persona=tmpl["system_prompt"],
                template_id=tmpl["id"],
            )
            perms = tmpl.get("default_permissions") or []
            if isinstance(perms, str):
                perms = json.loads(perms)
            if perms:
                perm_db = await get_db()
                try:
                    ts = now_iso()
                    for tool, action, perm in perms:
                        pid = new_id()
                        await perm_db.execute(
                            """INSERT OR IGNORE INTO tool_permissions (id, employee_id, tool, action, permission, granted_by, updated_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (pid, emp["id"], tool, action, perm, user_id, ts),
                        )
                    await perm_db.commit()
                finally:
                    await perm_db.close()
            # Seed default skills from template definitions
            try:
                from app.core.default_team import TEMPLATES as SKILL_TEMPLATES
                skill_defs = next(
                    (t.get("default_skills", []) for t in SKILL_TEMPLATES if t["slug"] == tmpl.get("slug")),
                    [],
                )
                for skill in skill_defs:
                    await create_skill(
                        employee_id=emp["id"],
                        name=skill["name"],
                        description=skill["description"],
                        procedure=skill["procedure"],
                        trigger_pattern=skill.get("trigger_pattern"),
                        examples=skill.get("examples"),
                    )
                if skill_defs:
                    logger.info(f"  Seeded {len(skill_defs)} default skills for {tmpl['name']}")
            except Exception as skill_err:
                logger.warning(f"Failed to seed skills for {tmpl['name']}: {skill_err}")

            created.append(emp)
            logger.info(f"Provisioned employee '{tmpl['name']}' ({tmpl['role']}) for user {user_id}")
        except Exception as e:
            logger.warning(f"Failed to provision {tmpl['slug']} for {user_id}: {e}")
    return created


# ─── Delegation tasks ───────────────────────────────────────────

async def create_delegation_task(
    from_employee_id: str, to_employee_id: str, user_id: str,
    task: str, context: str | None = None, project_id: str | None = None,
) -> dict:
    db = await get_db()
    try:
        task_id = new_id()
        ts = now_iso()
        await db.execute(
            """INSERT INTO delegation_tasks
               (id, from_employee_id, to_employee_id, user_id, task, context, status, project_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (task_id, from_employee_id, to_employee_id, user_id, task, context, project_id, ts),
        )
        await db.commit()
        return {"id": task_id, "from_employee_id": from_employee_id, "to_employee_id": to_employee_id,
                "user_id": user_id, "task": task, "context": context, "status": "pending",
                "project_id": project_id, "created_at": ts}
    finally:
        await db.close()


async def update_delegation_task(task_id: str, updates: dict) -> dict | None:
    db = await get_db()
    try:
        sets = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [task_id]
        await db.execute(f"UPDATE delegation_tasks SET {sets} WHERE id = ?", vals)
        await db.commit()
        cursor = await db.execute("SELECT * FROM delegation_tasks WHERE id = ?", (task_id,))
        return await cursor.fetchone()
    finally:
        await db.close()


async def get_delegation_task(task_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM delegation_tasks WHERE id = ?", (task_id,))
        return await cursor.fetchone()
    finally:
        await db.close()


async def list_delegation_tasks(employee_id: str, direction: str = "from", status: str | None = None) -> list[dict]:
    db = await get_db()
    try:
        col = "from_employee_id" if direction == "from" else "to_employee_id"
        query = f"SELECT * FROM delegation_tasks WHERE {col} = ?"
        params: list = [employee_id]
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT 50"
        cursor = await db.execute(query, params)
        return await cursor.fetchall()
    finally:
        await db.close()


async def get_pending_delegation_tasks(limit: int = 10) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM delegation_tasks WHERE status = 'pending' ORDER BY created_at ASC LIMIT ?",
            (limit,),
        )
        return await cursor.fetchall()
    finally:
        await db.close()


# ─── Activity log ──────────────────────────────────────────────

async def log_activity(user_id: str, event_type: str, title: str,
                       employee_id: str | None = None, employee_name: str | None = None,
                       detail: str | None = None, metadata: dict | None = None) -> dict:
    db = await get_db()
    try:
        aid = new_id()
        ts = now_iso()
        meta_json = json.dumps(metadata) if metadata else None
        await db.execute(
            """INSERT INTO activity_log (id, user_id, employee_id, employee_name, event_type, title, detail, metadata, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (aid, user_id, employee_id, employee_name, event_type, title, detail, meta_json, ts),
        )
        await db.commit()
        return {"id": aid, "event_type": event_type, "title": title, "created_at": ts}
    finally:
        await db.close()


async def get_activity_feed(user_id: str, limit: int = 50, unseen_only: bool = False) -> list[dict]:
    db = await get_db()
    try:
        sql = "SELECT * FROM activity_log WHERE user_id = ?"
        params: list = [user_id]
        if unseen_only:
            sql += " AND seen = 0"
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cursor = await db.execute(sql, tuple(params))
        rows = await cursor.fetchall()
        for r in rows:
            if isinstance(r.get("metadata"), str):
                try:
                    r["metadata"] = json.loads(r["metadata"])
                except Exception:
                    pass
        return rows
    finally:
        await db.close()


async def mark_activity_seen(user_id: str, activity_ids: list[str] | None = None):
    db = await get_db()
    try:
        if activity_ids:
            placeholders = ",".join("?" for _ in activity_ids)
            await db.execute(
                f"UPDATE activity_log SET seen = 1 WHERE user_id = ? AND id IN ({placeholders})",
                (user_id, *activity_ids),
            )
        else:
            await db.execute(
                "UPDATE activity_log SET seen = 1 WHERE user_id = ? AND seen = 0",
                (user_id,),
            )
        await db.commit()
    finally:
        await db.close()


async def get_unseen_activity_count(user_id: str) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM activity_log WHERE user_id = ? AND seen = 0",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0
    finally:
        await db.close()


# ── Decision Log ──────────────────────────────────────────────────

async def log_decision(
    decision_type: str,
    selected_choice: str,
    confidence: float,
    backend: str,
    latency_ms: float = 0.0,
    project_id: str = None,
    employee_id: str = None,
    input_context: str = None,
    options: str = None,
) -> str:
    import uuid
    from datetime import datetime, timezone
    db = await get_db()
    try:
        row_id = str(uuid.uuid4())
        await db.execute(
            """INSERT INTO decision_log
               (id, project_id, employee_id, decision_type, input_context, options,
                selected_choice, confidence, backend, latency_ms, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (row_id, project_id, employee_id, decision_type,
             (input_context or "")[:2000], options,
             selected_choice, confidence, backend, latency_ms,
             datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
        return row_id
    finally:
        await db.close()


async def record_decision_outcome(decision_id: str, actual_outcome: str, outcome_correct: bool, human_override: str = None):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE decision_log SET actual_outcome = ?, outcome_correct = ?, human_override = ? WHERE id = ?",
            (actual_outcome, 1 if outcome_correct else 0, human_override, decision_id),
        )
        await db.commit()
    finally:
        await db.close()


async def get_decision_stats(decision_type: str = None, limit: int = 100) -> list[dict]:
    db = await get_db()
    try:
        if decision_type:
            cursor = await db.execute(
                "SELECT * FROM decision_log WHERE decision_type = ? ORDER BY created_at DESC LIMIT ?",
                (decision_type, limit),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM decision_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        return [dict(r) for r in await cursor.fetchall()]
    finally:
        await db.close()


# ── Subscriptions ──────────────────────────────────────────────────

async def get_subscription(user_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM subscriptions WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_subscription_by_stripe_customer(customer_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM subscriptions WHERE stripe_customer_id = ?", (customer_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def upsert_subscription(
    user_id: str,
    plan: str = "free",
    stripe_customer_id: str = None,
    stripe_subscription_id: str = None,
    status: str = "active",
    current_period_start: str = None,
    current_period_end: str = None,
    cancel_at_period_end: bool = False,
) -> dict:
    import uuid
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    db = await get_db()
    try:
        existing = await get_subscription(user_id)
        if existing:
            await db.execute(
                """UPDATE subscriptions SET plan=?, stripe_customer_id=?, stripe_subscription_id=?,
                   status=?, current_period_start=?, current_period_end=?,
                   cancel_at_period_end=?, updated_at=? WHERE user_id=?""",
                (plan, stripe_customer_id, stripe_subscription_id, status,
                 current_period_start, current_period_end,
                 1 if cancel_at_period_end else 0, now, user_id),
            )
        else:
            await db.execute(
                """INSERT INTO subscriptions
                   (id, user_id, stripe_customer_id, stripe_subscription_id, plan, status,
                    current_period_start, current_period_end, cancel_at_period_end, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), user_id, stripe_customer_id, stripe_subscription_id,
                 plan, status, current_period_start, current_period_end,
                 1 if cancel_at_period_end else 0, now, now),
            )
        await db.commit()
        return await get_subscription(user_id)
    finally:
        await db.close()


# ── Usage Records ──────────────────────────────────────────────────

async def record_usage(
    user_id: str,
    record_type: str,
    tokens_input: int = 0,
    tokens_output: int = 0,
    model: str = None,
    employee_id: str = None,
    project_id: str = None,
) -> str:
    import uuid
    from datetime import datetime, timezone
    db = await get_db()
    try:
        row_id = str(uuid.uuid4())
        await db.execute(
            """INSERT INTO usage_records
               (id, user_id, record_type, tokens_input, tokens_output, model, employee_id, project_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (row_id, user_id, record_type, tokens_input, tokens_output,
             model, employee_id, project_id, datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
        return row_id
    finally:
        await db.close()


async def get_usage_summary(user_id: str, days: int = 30) -> dict:
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT record_type,
                      COUNT(*) as count,
                      SUM(tokens_input) as total_input,
                      SUM(tokens_output) as total_output
               FROM usage_records
               WHERE user_id = ? AND created_at >= ?
               GROUP BY record_type""",
            (user_id, cutoff),
        )
        rows = [dict(r) for r in await cursor.fetchall()]
        total_input = sum(r["total_input"] or 0 for r in rows)
        total_output = sum(r["total_output"] or 0 for r in rows)
        return {
            "total_tokens": total_input + total_output,
            "total_input": total_input,
            "total_output": total_output,
            "by_type": rows,
            "period_days": days,
        }
    finally:
        await db.close()


# ─── Scheduled Tasks ─────────────────────────────────────────────

async def create_scheduled_task(
    user_id: str, employee_id: str, name: str, task_prompt: str,
    description: str | None = None, schedule_type: str = "once",
    cron_expression: str | None = None, next_run_at: str | None = None,
) -> dict:
    db = await get_db()
    try:
        tid = new_id()
        ts = now_iso()
        if not next_run_at and schedule_type == "once":
            next_run_at = ts
        await db.execute(
            """INSERT INTO scheduled_tasks
               (id, user_id, employee_id, name, description, task_prompt,
                schedule_type, cron_expression, next_run_at, is_active, run_count, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?)""",
            (tid, user_id, employee_id, name, description, task_prompt,
             schedule_type, cron_expression, next_run_at, ts, ts),
        )
        await db.commit()
        return {"id": tid, "user_id": user_id, "employee_id": employee_id,
                "name": name, "description": description, "task_prompt": task_prompt,
                "schedule_type": schedule_type, "cron_expression": cron_expression,
                "next_run_at": next_run_at, "is_active": True, "run_count": 0,
                "created_at": ts, "updated_at": ts}
    finally:
        await db.close()


async def list_scheduled_tasks(user_id: str, employee_id: str | None = None) -> list[dict]:
    db = await get_db()
    try:
        sql = "SELECT * FROM scheduled_tasks WHERE user_id = ?"
        params: list = [user_id]
        if employee_id:
            sql += " AND employee_id = ?"
            params.append(employee_id)
        sql += " ORDER BY created_at DESC"
        cursor = await db.execute(sql, tuple(params))
        return await cursor.fetchall()
    finally:
        await db.close()


async def get_scheduled_task(task_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,))
        return await cursor.fetchone()
    finally:
        await db.close()


async def update_scheduled_task(task_id: str, updates: dict) -> dict | None:
    db = await get_db()
    try:
        allowed = {"name", "description", "task_prompt", "schedule_type", "cron_expression",
                    "next_run_at", "last_run_at", "last_run_status", "last_run_result",
                    "run_count", "is_active"}
        parts, vals = [], []
        for k, v in updates.items():
            if k not in allowed:
                continue
            parts.append(f"{k} = ?")
            vals.append(v)
        if not parts:
            return await get_scheduled_task(task_id)
        parts.append("updated_at = ?")
        vals.append(now_iso())
        vals.append(task_id)
        await db.execute(f"UPDATE scheduled_tasks SET {', '.join(parts)} WHERE id = ?", vals)
        await db.commit()
        return await get_scheduled_task(task_id)
    finally:
        await db.close()


async def delete_scheduled_task(task_id: str, user_id: str) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM scheduled_tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def get_due_scheduled_tasks(limit: int = 20) -> list[dict]:
    db = await get_db()
    try:
        now = now_iso()
        cursor = await db.execute(
            """SELECT st.*, e.name as employee_name, e.role as employee_role
               FROM scheduled_tasks st
               JOIN employees e ON st.employee_id = e.id
               WHERE st.is_active = 1 AND st.next_run_at IS NOT NULL AND st.next_run_at <= ?
               ORDER BY st.next_run_at ASC LIMIT ?""",
            (now, limit),
        )
        return await cursor.fetchall()
    finally:
        await db.close()


# ─── Memory Embeddings (Semantic Memory) ─────────────────────────

async def store_memory_embedding(memory_id: str, employee_id: str,
                                  embedding: list[float], model: str = "local") -> dict:
    db = await get_db()
    try:
        eid = new_id()
        ts = now_iso()
        embedding_json = json.dumps(embedding)
        await db.execute(
            "DELETE FROM memory_embeddings WHERE memory_id = ?", (memory_id,))
        await db.execute(
            """INSERT INTO memory_embeddings (id, memory_id, employee_id, embedding, model, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (eid, memory_id, employee_id, embedding_json, model, ts),
        )
        await db.commit()
        return {"id": eid, "memory_id": memory_id, "model": model, "created_at": ts}
    finally:
        await db.close()


async def get_memory_embeddings(employee_id: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT me.memory_id, me.embedding, m.content, m.type, m.importance, m.confidence
               FROM memory_embeddings me
               JOIN memories m ON me.memory_id = m.id
               WHERE me.employee_id = ? AND m.is_active = 1
               ORDER BY m.importance DESC""",
            (employee_id,),
        )
        rows = await cursor.fetchall()
        for r in rows:
            if isinstance(r.get("embedding"), str):
                r["embedding"] = json.loads(r["embedding"])
        return rows
    finally:
        await db.close()


async def semantic_memory_search(employee_id: str, query_embedding: list[float],
                                  limit: int = 10) -> list[dict]:
    all_embeddings = await get_memory_embeddings(employee_id)
    if not all_embeddings:
        return []

    def cosine_sim(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = sum(x * x for x in a) ** 0.5
        mag_b = sum(x * x for x in b) ** 0.5
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    scored = []
    for row in all_embeddings:
        emb = row["embedding"]
        if not emb:
            continue
        sim = cosine_sim(query_embedding, emb)
        importance_boost = (row.get("importance") or 0.5) * 0.1
        scored.append({
            "memory_id": row["memory_id"],
            "content": row["content"],
            "type": row["type"],
            "importance": row.get("importance"),
            "confidence": row.get("confidence"),
            "similarity": sim + importance_boost,
        })

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:limit]


# ---------------------------------------------------------------------------
# Autonomous execution CRUD
# ---------------------------------------------------------------------------

async def create_autonomous_execution(
    employee_id: str, user_id: str, goal: str,
    session_id: str | None = None,
    max_iterations: int = 25, max_tokens: int = 200000,
    max_time_seconds: int = 600,
) -> dict:
    db = await get_db()
    try:
        eid = _id()
        ts = now_iso()
        await db.execute(
            """INSERT INTO autonomous_executions
               (id, employee_id, user_id, session_id, goal, status, state,
                max_iterations, max_tokens, max_time_seconds, created_at)
               VALUES (?, ?, ?, ?, ?, 'pending', 'PLANNING', ?, ?, ?, ?)""",
            (eid, employee_id, user_id, session_id, goal,
             max_iterations, max_tokens, max_time_seconds, ts),
        )
        await db.commit()
        return {
            "id": eid, "employee_id": employee_id, "user_id": user_id,
            "session_id": session_id, "goal": goal, "status": "pending",
            "state": "PLANNING", "iteration": 0,
            "max_iterations": max_iterations, "max_tokens": max_tokens,
            "max_time_seconds": max_time_seconds, "tokens_used": 0,
            "created_at": ts,
        }
    finally:
        await db.close()


async def get_autonomous_execution(execution_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM autonomous_executions WHERE id = ?", (execution_id,))
        return await cursor.fetchone()
    finally:
        await db.close()


async def update_autonomous_execution(execution_id: str, updates: dict):
    db = await get_db()
    try:
        parts, vals = [], []
        for k, v in updates.items():
            parts.append(f"{k} = ?")
            vals.append(v)
        if not parts:
            return
        vals.append(execution_id)
        await db.execute(
            f"UPDATE autonomous_executions SET {', '.join(parts)} WHERE id = ?",
            tuple(vals),
        )
        await db.commit()
    finally:
        await db.close()


async def list_autonomous_executions(
    employee_id: str | None = None, user_id: str | None = None,
    status: str | None = None, limit: int = 20,
) -> list[dict]:
    db = await get_db()
    try:
        clauses, params = [], []
        if employee_id:
            clauses.append("employee_id = ?")
            params.append(employee_id)
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        cursor = await db.execute(
            f"SELECT * FROM autonomous_executions {where} ORDER BY created_at DESC LIMIT ?",
            tuple(params),
        )
        return await cursor.fetchall()
    finally:
        await db.close()


async def add_execution_log(
    execution_id: str, iteration: int, state: str, action: str,
    input_summary: str | None = None, output_summary: str | None = None,
    tokens_used: int = 0, duration_ms: int | None = None, success: bool = True,
) -> dict:
    db = await get_db()
    try:
        lid = _id()
        ts = now_iso()
        await db.execute(
            """INSERT INTO execution_logs
               (id, execution_id, iteration, state, action, input_summary,
                output_summary, tokens_used, duration_ms, success, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (lid, execution_id, iteration, state, action,
             input_summary, output_summary, tokens_used, duration_ms,
             1 if success else 0, ts),
        )
        await db.commit()
        return {"id": lid, "execution_id": execution_id, "iteration": iteration,
                "state": state, "action": action}
    finally:
        await db.close()


async def add_execution_artifact(
    execution_id: str, artifact_type: str, title: str,
    path: str | None = None, content: str | None = None,
    language: str | None = None, metadata: str | None = None,
) -> dict:
    db = await get_db()
    try:
        aid = _id()
        ts = now_iso()
        await db.execute(
            """INSERT INTO execution_artifacts
               (id, execution_id, type, title, path, content, language, status, metadata, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?)""",
            (aid, execution_id, artifact_type, title, path, content, language, metadata, ts),
        )
        await db.commit()
        return {"id": aid, "execution_id": execution_id, "type": artifact_type,
                "title": title, "path": path, "status": "draft"}
    finally:
        await db.close()


async def list_execution_artifacts(execution_id: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM execution_artifacts WHERE execution_id = ? ORDER BY created_at",
            (execution_id,),
        )
        return await cursor.fetchall()
    finally:
        await db.close()


async def get_execution_logs(execution_id: str, limit: int = 100) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM execution_logs WHERE execution_id = ? ORDER BY iteration, created_at LIMIT ?",
            (execution_id, limit),
        )
        return await cursor.fetchall()
    finally:
        await db.close()
