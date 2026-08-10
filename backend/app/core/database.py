import aiosqlite
import json
import uuid
from datetime import datetime, timezone

from app.core.config import DATABASE_PATH

DB_PATH = DATABASE_PATH


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                problem_statement TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'created',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
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
                FOREIGN KEY (project_id) REFERENCES projects(id)
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
        await db.commit()
    finally:
        await db.close()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


async def create_project(problem_statement: str) -> dict:
    db = await get_db()
    try:
        project_id = new_id()
        ts = now_iso()
        await db.execute(
            "INSERT INTO projects (id, problem_statement, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (project_id, problem_statement, "created", ts, ts),
        )
        await db.commit()
        return {"id": project_id, "problem_statement": problem_statement, "status": "created", "created_at": ts, "updated_at": ts}
    finally:
        await db.close()


async def get_project(project_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)
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
        await db.execute(
            "INSERT INTO agent_outputs (id, project_id, role, content, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (output_id, project_id, role, json.dumps(content), "pending", ts),
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
            d["content"] = json.loads(d["content"])
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
        d["content"] = json.loads(d["content"])
        return d
    finally:
        await db.close()


async def set_memory(project_id: str, key: str, value: str, updated_by: str):
    db = await get_db()
    try:
        mem_id = new_id()
        ts = now_iso()
        await db.execute(
            """INSERT INTO shared_memory (id, project_id, key, value, updated_by, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(project_id, key) DO UPDATE SET value = ?, updated_by = ?, updated_at = ?""",
            (mem_id, project_id, key, value, updated_by, ts, value, updated_by, ts),
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
        await db.execute(
            """INSERT INTO conversations (id, project_id, agent_role, messages, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT DO NOTHING""",
            (conv_id, project_id, agent_role, json.dumps(messages), ts),
        )
        await db.execute(
            """UPDATE conversations SET messages = ?, updated_at = ?
               WHERE project_id = ? AND agent_role = ?""",
            (json.dumps(messages), ts, project_id, agent_role),
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
        return json.loads(row["messages"])
    finally:
        await db.close()


async def list_projects() -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM projects ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()
