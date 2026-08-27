"""
Deterministic Data Migration Script: SQLite -> PostgreSQL (P4.7-A)

Migrates all persistent application tables (users, projects, executions, agent_outputs,
conversations, shared_memory) from SQLite to PostgreSQL with row count validation.
"""

import os
import sys
import asyncio
import logging
import aiosqlite
import asyncpg

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.config import DATABASE_PATH, DATABASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration")


async def migrate_data(sqlite_path: str, pg_url: str):
    logger.info(f"Starting migration from SQLite ({sqlite_path}) to PostgreSQL ({pg_url[:30]}...)...")

    if not os.path.exists(sqlite_path):
        logger.warning(f"Source SQLite database path '{sqlite_path}' does not exist. Nothing to migrate.")
        return

    if not pg_url or not (pg_url.startswith("postgresql://") or pg_url.startswith("postgres://")):
        raise ValueError("Target DATABASE_URL must be a valid PostgreSQL connection string.")

    url = pg_url.replace("postgres://", "postgresql://", 1) if pg_url.startswith("postgres://") else pg_url
    
    sqlite_conn = await aiosqlite.connect(sqlite_path)
    sqlite_conn.row_factory = aiosqlite.Row
    pg_conn = await asyncpg.connect(url)

    try:
        tables = ["users", "projects", "executions", "agent_outputs", "conversations", "shared_memory"]
        migration_stats = {}

        for table in tables:
            # Check source count
            cursor = await sqlite_conn.execute(f"SELECT COUNT(*) FROM {table}")
            source_count = (await cursor.fetchone())[0]

            if source_count == 0:
                logger.info(f"Table '{table}': 0 rows in source SQLite. Skipping.")
                migration_stats[table] = (0, 0)
                continue

            # Fetch all rows from SQLite
            cursor = await sqlite_conn.execute(f"SELECT * FROM {table}")
            rows = await cursor.fetchall()
            
            if not rows:
                continue

            columns = list(rows[0].keys())
            col_names = ", ".join(columns)
            placeholders = ", ".join([f"${i+1}" for i in range(len(columns))])

            # Clear existing data in target table if present to prevent primary key conflicts
            await pg_conn.execute(f"DELETE FROM {table}")

            insert_sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

            inserted = 0
            for row in rows:
                vals = [row[c] for c in columns]
                await pg_conn.execute(insert_sql, *vals)
                inserted += 1

            # Verify target count
            target_count = await pg_conn.fetchval(f"SELECT COUNT(*) FROM {table}")
            logger.info(f"Table '{table}': Migrated {target_count}/{source_count} rows successfully.")
            migration_stats[table] = (source_count, target_count)

            assert target_count == source_count, f"Migration count mismatch for table '{table}': expected {source_count}, got {target_count}"

        logger.info("============================================================")
        logger.info("SQLITE TO POSTGRESQL DATA MIGRATION COMPLETED SUCCESSFULLY")
        logger.info("============================================================")
        for tbl, (src, tgt) in migration_stats.items():
            logger.info(f" - {tbl:20s}: {src:5d} SQLite rows -> {tgt:5d} PostgreSQL rows")
        logger.info("============================================================")

    finally:
        await sqlite_conn.close()
        await pg_conn.close()


if __name__ == "__main__":
    db_path = os.getenv("DATABASE_PATH", "company.db")
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        print("Usage: DATABASE_URL='postgresql://user:pass@localhost:5432/dbname' python migrate_sqlite_to_postgres.py")
        sys.exit(1)
    asyncio.run(migrate_data(db_path, db_url))
