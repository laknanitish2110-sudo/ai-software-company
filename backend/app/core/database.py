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
from datetime import datetime, timezone
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
            if pg_sql.strip().upper().startswith("SELECT"):
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
                    created_at TEXT NOT NULL
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
            """)
        else:
            # PostgreSQL DDL
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id VARCHAR(255) PRIMARY KEY,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
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
    finally:
        await db.close()

    try:
        from app.services.startup_recovery import recover_orphaned_executions
        await recover_orphaned_executions(stale_threshold_seconds=30)
    except Exception as rec_err:
        logger.warning(f"Startup crash recovery notice: {rec_err}")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:16]


# --- USER DATABASE FUNCTIONS ---

async def create_user(email: str, password_hash: str) -> dict:
    db = await get_db()
    try:
        user_id = new_id()
        ts = now_iso()
        norm_email = email.strip().lower()
        await db.execute(
            "INSERT INTO users (id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (user_id, norm_email, password_hash, ts),
        )
        await db.commit()
        return {"id": user_id, "email": norm_email, "created_at": ts}
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
        
        await db.execute("DELETE FROM shared_memory WHERE project_id = ?", (project_id,))
        await db.execute("DELETE FROM conversations WHERE project_id = ?", (project_id,))
        await db.execute("DELETE FROM agent_outputs WHERE project_id = ?", (project_id,))
        await db.execute("DELETE FROM executions WHERE project_id = ?", (project_id,))
        await db.execute("DELETE FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id))
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


async def query_domain_learnings(keywords: list[str], exclude_project_id: str | None = None, limit: int = 10) -> list[dict]:
    db = await get_db()
    try:
        conditions = []
        params = []
        for kw in keywords:
            conditions.append("(LOWER(domain) LIKE ? OR LOWER(title) LIKE ? OR LOWER(content) LIKE ?)")
            pattern = f"%{kw.lower()}%"
            params.extend([pattern, pattern, pattern])
        where = " OR ".join(conditions) if conditions else "1=1"
        if exclude_project_id:
            where = f"({where}) AND project_id != ?"
            params.append(exclude_project_id)
        cursor = await db.execute(
            f"SELECT * FROM domain_learnings WHERE {where} ORDER BY created_at DESC LIMIT ?",
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
