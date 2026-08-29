import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("OPENROUTER_API_KEY", "test-key-placeholder")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("TAVILY_API_KEY", "")
os.environ.setdefault("N8N_WEBHOOK_URL", "")
os.environ.setdefault("JWT_SECRET", "test_jwt_secret_key_445566")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("SANDBOX_MODE", "local_dev")
os.environ.setdefault("DATABASE_URL", "")

import app.core.config as cfg_mod

# Force a fresh temp DB path at import time so unittest.TestCase.setUpClass
# calls to init_db() use a clean file with the full schema.
_test_db_dir = tempfile.mkdtemp(prefix="ai_sw_test_")
_test_db_path = os.path.join(_test_db_dir, "test.db")
cfg_mod.DATABASE_PATH = _test_db_path
cfg_mod.DATABASE_URL = ""

import pytest
import pytest_asyncio

import app.core.database as db_mod


@pytest_asyncio.fixture(autouse=True)
async def _init_test_db(tmp_path):
    """Create a fresh temp-file SQLite DB for every pytest-native async test."""
    db_file = str(tmp_path / "test.db")
    cfg_mod.DATABASE_PATH = db_file
    cfg_mod.DATABASE_URL = ""
    db_mod._pg_pool = None
    await db_mod.init_db()
    yield
    cfg_mod.DATABASE_PATH = _test_db_path
    if os.path.exists(db_file):
        os.unlink(db_file)
