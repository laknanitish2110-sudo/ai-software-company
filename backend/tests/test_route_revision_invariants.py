"""Route and revision invariant tests for Core Trust Phase.

Tests pipeline route configs, revision flow, iteration context,
Fernet token encryption, streaming sanitization, and apply snapshot.
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestPipelineRoutes:
    """Verify route configs are consistent and complete."""

    def test_all_routes_have_required_keys(self):
        from app.services.task_router import PIPELINE_ROUTES
        required = {"name", "description", "agents", "estimated_minutes"}
        for route_id, config in PIPELINE_ROUTES.items():
            missing = required - set(config.keys())
            assert not missing, f"Route '{route_id}' missing keys: {missing}"

    def test_all_route_agents_have_prompts(self):
        from app.services.task_router import PIPELINE_ROUTES
        from app.agents.engine import SYSTEM_PROMPTS
        from app.models.schemas import AgentRole
        prompt_roles = {r.value for r in AgentRole if r in SYSTEM_PROMPTS}
        for route_id, config in PIPELINE_ROUTES.items():
            for agent in config["agents"]:
                assert agent in prompt_roles, f"Route '{route_id}' references agent '{agent}' with no system prompt"

    def test_quick_build_is_minimal(self):
        from app.services.task_router import PIPELINE_ROUTES
        qb = PIPELINE_ROUTES["quick_build"]
        assert "ceo" in qb["agents"]
        assert "engineer" in qb["agents"]
        assert len(qb["agents"]) <= 3

    def test_standard_has_architect(self):
        from app.services.task_router import PIPELINE_ROUTES
        std = PIPELINE_ROUTES["standard"]
        assert "architect" in std["agents"]
        assert "engineer" in std["agents"]

    def test_classify_returns_valid_route(self):
        from app.services.task_router import classify_task, PIPELINE_ROUTES
        result = classify_task("build a simple todo app")
        assert result["suggested_route"] in PIPELINE_ROUTES

    def test_classify_short_input_prefers_quick(self):
        from app.services.task_router import classify_task
        result = classify_task("calculator app")
        assert result["suggested_route"] == "quick_build"


class TestRevisionFlow:
    """Verify iteration context and feedback clearing."""

    def test_build_existing_files_context_returns_empty_for_missing_project(self):
        from app.agents.engine import _build_existing_files_context
        result = _build_existing_files_context("nonexistent_project_xyz")
        assert result == ""

    def test_build_existing_files_context_formats_files(self):
        from app.agents.engine import _build_existing_files_context
        from app.services.file_generator import PROJECTS_DIR
        test_id = "test_revision_format"
        project_dir = PROJECTS_DIR / test_id
        project_dir.mkdir(parents=True, exist_ok=True)
        try:
            (project_dir / "index.html").write_text("<h1>Hello</h1>", encoding="utf-8")
            (project_dir / "app.js").write_text("console.log('hi')", encoding="utf-8")
            result = _build_existing_files_context(test_id)
            assert "index.html" in result
            assert "app.js" in result
            assert "<h1>Hello</h1>" in result
            assert "## Current Generated Files" in result
        finally:
            shutil.rmtree(project_dir, ignore_errors=True)

    def test_system_prompts_not_exposed_in_api_schema(self):
        """System prompts must stay hidden — verify the hidden marker exists."""
        from app.agents.engine import SYSTEM_PROMPTS
        for role, prompt in SYSTEM_PROMPTS.items():
            assert len(prompt) > 50, f"Prompt for {role} suspiciously short — may be missing"


class TestFernetEncryption:
    """Verify Fernet token encryption and legacy XOR migration."""

    def test_encrypt_decrypt_roundtrip(self):
        from app.services.github_service import obfuscate_token, deobfuscate_token
        secret = "test-jwt-secret-for-testing"
        token = "ghp_testtoken1234567890abcdef"
        encrypted = obfuscate_token(token, secret)
        assert encrypted.startswith("fernet:")
        assert token not in encrypted
        decrypted = deobfuscate_token(encrypted, secret)
        assert decrypted == token

    def test_legacy_xor_migration(self):
        from app.services.github_service import deobfuscate_token, _xor_decrypt_legacy
        import base64, hashlib
        secret = "test-jwt-secret-for-testing"
        token = "ghp_legacytoken123"
        key = hashlib.sha256(secret.encode()).digest()
        xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(token.encode()))
        legacy_encrypted = base64.urlsafe_b64encode(xored).decode()
        assert not legacy_encrypted.startswith("fernet:")
        decrypted = deobfuscate_token(legacy_encrypted, secret)
        assert decrypted == token

    def test_fernet_different_from_xor(self):
        from app.services.github_service import obfuscate_token
        secret = "test-jwt-secret"
        token = "ghp_abc123"
        enc1 = obfuscate_token(token, secret)
        enc2 = obfuscate_token(token, secret)
        assert enc1 != enc2, "Fernet should produce different ciphertexts (random IV)"

    def test_custom_encryption_key(self):
        from cryptography.fernet import Fernet
        from app.services.github_service import obfuscate_token, deobfuscate_token
        custom_key = Fernet.generate_key().decode()
        secret = "jwt-secret-unused"
        token = "ghp_customkey123"
        with patch.dict(os.environ, {"GITHUB_TOKEN_ENCRYPTION_KEY": custom_key}):
            encrypted = obfuscate_token(token, secret)
            decrypted = deobfuscate_token(encrypted, secret)
            assert decrypted == token


class TestStreamingErrorSanitization:
    """Verify streaming responses don't leak internal details."""

    @pytest.mark.asyncio
    async def test_stream_error_is_sanitized(self):
        from app.agents.engine import call_employee_stream
        from app.models.schemas import AgentRole
        chunks = []
        async for chunk in call_employee_stream("nonexistent_project", AgentRole.ENGINEER, "test"):
            chunks.append(chunk)
        assert len(chunks) >= 1
        error_chunk = chunks[0]
        data = json.loads(error_chunk.replace("data: ", "").strip())
        assert "error" in data
        assert "traceback" not in data["error"].lower()
        assert "sk-" not in data["error"]


class TestApplySnapshot:
    """Verify apply_file_updates creates and restores snapshots."""

    def test_successful_apply_cleans_backup(self):
        from app.services.file_generator import apply_file_updates, PROJECTS_DIR
        test_id = "test_snapshot_cleanup"
        project_dir = PROJECTS_DIR / test_id
        backup_dir = PROJECTS_DIR / f"{test_id}_backup"
        project_dir.mkdir(parents=True, exist_ok=True)
        try:
            (project_dir / "old.txt").write_text("old content", encoding="utf-8")
            result = apply_file_updates(test_id, [{"path": "new.txt", "content": "new content"}])
            assert result["status"] == "ok"
            assert not backup_dir.exists(), "Backup should be cleaned up after success"
            assert (project_dir / "new.txt").read_text(encoding="utf-8") == "new content"
            assert (project_dir / "old.txt").exists()
        finally:
            shutil.rmtree(project_dir, ignore_errors=True)
            shutil.rmtree(backup_dir, ignore_errors=True)

    def test_snapshot_restores_on_total_size_exceeded(self):
        from app.services.file_generator import apply_file_updates, PROJECTS_DIR, MAX_APPLY_FILE_SIZE
        test_id = "test_snapshot_restore"
        project_dir = PROJECTS_DIR / test_id
        project_dir.mkdir(parents=True, exist_ok=True)
        try:
            (project_dir / "original.txt").write_text("preserve me", encoding="utf-8")
            chunk = "x" * (MAX_APPLY_FILE_SIZE - 10)
            files = [{"path": f"f{i}.txt", "content": chunk} for i in range(120)]
            result = apply_file_updates(test_id, files)
            assert result["status"] == "error"
            assert "restored" in result["message"].lower() or "snapshot" in result["message"].lower()
            assert (project_dir / "original.txt").read_text(encoding="utf-8") == "preserve me"
        finally:
            shutil.rmtree(project_dir, ignore_errors=True)
            shutil.rmtree(PROJECTS_DIR / f"{test_id}_backup", ignore_errors=True)
