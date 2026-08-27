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
        if self.backend_type == "sqlite":
            await self.conn.close()

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
        
        # Dialect adjustments
        sql = sql.replace("ON CONFLICT DO NOTHING", "ON CONFLICT (project_id, agent_role) DO NOTHING")
        return sql


async def get_db() -> DBWrapper:
    pool = await get_pg_pool()
    if pool is not None:
        conn = await pool.acquire()
        return DBWrapper("postgres", conn)
    else:
        db = await aiosqlite.connect(DATABASE_PATH)
        db.row_factory = aiosqlite.Row
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
    return uuid.uuid4().hex[:12]


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
        cursor = await db.execute("SELECT id, email, created_at FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return row
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
