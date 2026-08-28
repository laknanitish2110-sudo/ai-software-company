"""
P4.9.3 — POST /api/projects Endpoint Hardening Regression Test Suite

Verifies:
1. Unhandled RedisUnavailableError in production returns HTTP 503 REDIS_UNAVAILABLE instead of HTTP 500.
2. Valid production POST /api/projects request creates project and returns HTTP 200 with project schema.
3. Rate-limited request returns HTTP 429 RATE_LIMITED cleanly.
"""

import os
import sys
import unittest
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient
from app.main import app
from app.core.auth import create_access_token
from app.services.redis_coordinator import redis_coordinator
from app.core.database import create_user


class TestP493CreateProjectHardening(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        self.strong_secret = "test_p493_production_secret_key_1234567890"

    def _get_auth_headers(self, email="p493@example.com"):
        import asyncio
        try:
            user_rec = asyncio.run(create_user(email, "pbkdf2:salt:hash"))
            user_id = user_rec["id"]
        except Exception:
            from app.core.database import get_user_by_email
            user_rec = asyncio.run(get_user_by_email(email))
            user_id = user_rec["id"]
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "JWT_SECRET": self.strong_secret}):
            token = create_access_token({"sub": user_id, "email": email})
        return {"Authorization": f"Bearer {token}"}

    def test_1_production_unconfigured_redis_returns_503_redis_unavailable(self):
        """1. Unconfigured REDIS_URL in production returns 503 REDIS_UNAVAILABLE, NOT 500."""
        headers = self._get_auth_headers("p493_1@example.com")
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "JWT_SECRET": self.strong_secret, "REDIS_URL": ""}):
            with patch.object(redis_coordinator, "_client", None):
                resp = self.client.post("/api/projects", json={
                    "problem_statement": "Build a task manager web app",
                    "auto_approve": True
                }, headers=headers)
                
                self.assertEqual(resp.status_code, 503)
                data = resp.json()
                self.assertEqual(data.get("error"), "REDIS_UNAVAILABLE")
                self.assertIn("REDIS_URL is unconfigured", data.get("message", ""))
        print("[PASS] Test 1 (Production Unconfigured Redis Returns HTTP 503) PASSED.")

    def test_2_production_valid_setup_returns_200_and_creates_project(self):
        """2. Valid production setup returns HTTP 200 with created project object."""
        headers = self._get_auth_headers("p493_2@example.com")
        mock_client = AsyncMock()
        mock_client.eval.return_value = [1, 1]  # allowed, val
        mock_client.set.return_value = True
        mock_client.get.return_value = None

        with patch.dict(os.environ, {"ENVIRONMENT": "production", "JWT_SECRET": self.strong_secret, "REDIS_URL": "redis://localhost:6379/0"}):
            with patch.object(redis_coordinator, "_get_client", return_value=mock_client):
                resp = self.client.post("/api/projects", json={
                    "problem_statement": "Build a task manager web app",
                    "auto_approve": True
                }, headers=headers)

                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertIn("id", data)
                self.assertEqual(data.get("problem_statement"), "Build a task manager web app")
                self.assertEqual(data.get("status"), "created")
        print("[PASS] Test 2 (Production Valid Setup Returns HTTP 200) PASSED.")

    def test_3_rate_limited_request_returns_429(self):
        """3. Rate-limited project creation request returns HTTP 429 RATE_LIMITED."""
        headers = self._get_auth_headers("p493_3@example.com")
        mock_client = AsyncMock()
        mock_client.eval.return_value = [0, 11]  # disallowed, val

        with patch.dict(os.environ, {"ENVIRONMENT": "production", "JWT_SECRET": self.strong_secret, "REDIS_URL": "redis://localhost:6379/0"}):
            with patch.object(redis_coordinator, "_get_client", return_value=mock_client):
                resp = self.client.post("/api/projects", json={
                    "problem_statement": "Build a task manager web app",
                    "auto_approve": True
                }, headers=headers)

                self.assertEqual(resp.status_code, 429)
                data = resp.json()
                self.assertEqual(data.get("error"), "RATE_LIMITED")
        print("[PASS] Test 3 (Rate-Limited Request Returns HTTP 429) PASSED.")


if __name__ == "__main__":
    unittest.main()
