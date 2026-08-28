"""
P4.8.5 — Production JWT Secret Hardening Verification Test Suite

Verifies:
1. Production mode with missing JWT_SECRET fails closed with ValueError.
2. Production mode with default/insecure JWT_SECRET fails closed with ValueError.
3. Production mode with valid, strong JWT_SECRET is accepted.
4. Development mode with no JWT_SECRET preserves fallback behavior.
5. End-to-end JWT token creation, decoding, and authentication lifecycle works cleanly.
"""

import os
import sys
import asyncio
import unittest
from unittest.mock import patch

from app.core.config import get_jwt_secret, validate_jwt_config, DEFAULT_DEV_JWT_SECRET
from app.core.auth import create_access_token, decode_access_token, hash_password, verify_password


class TestP485JWTHardening(unittest.TestCase):

    def setUp(self):
        # Reset environment before each test
        os.environ["ENVIRONMENT"] = "development"
        if "JWT_SECRET" in os.environ:
            del os.environ["JWT_SECRET"]

    def test_1_production_missing_jwt_secret_fails_closed(self):
        """1. Production + missing/empty/whitespace JWT_SECRET -> startup/config failure."""
        for empty_val in ["", "   ", "\t\n"]:
            with patch.dict(os.environ, {"ENVIRONMENT": "production", "JWT_SECRET": empty_val}):
                with self.assertRaises(ValueError) as ctx:
                    validate_jwt_config()
                self.assertIn("JWT_SECRET is required in production", str(ctx.exception))
                if empty_val.strip():
                    self.assertNotIn(empty_val, str(ctx.exception))
        print("[PASS] Test 1 (Production Missing/Empty JWT Secret Fails Closed) PASSED.")

    def test_2_production_default_insecure_jwt_secret_fails_closed(self):
        """2. Production + default/insecure JWT_SECRET -> failure without secret leakage."""
        insecure_keys = [
            DEFAULT_DEV_JWT_SECRET,
            "change_me",
            "123456",
            "short_secret"  # < 16 chars
        ]
        for key in insecure_keys:
            with patch.dict(os.environ, {"ENVIRONMENT": "production", "JWT_SECRET": key}):
                with self.assertRaises(ValueError) as ctx:
                    validate_jwt_config()
                self.assertIn("insecure or short key", str(ctx.exception))
                # Ensure custom secret value itself is never leaked in the exception message
                self.assertNotIn(key, str(ctx.exception))
        print("[PASS] Test 2 (Production Insecure/Default Secret Rejected Without Leakage) PASSED.")

    def test_3_production_valid_strong_jwt_secret_accepted(self):
        """3. Production + valid strong JWT_SECRET -> accepted."""
        strong_secret = "prod_super_secret_jwt_key_32_chars_long_abcdef!!"
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "JWT_SECRET": strong_secret}):
            secret = get_jwt_secret()
            self.assertEqual(secret, strong_secret)
            # Should not raise exception
            validate_jwt_config()
        print("[PASS] Test 3 (Production Valid Strong Secret Accepted) PASSED.")

    def test_4_development_missing_secret_fallback_preserved(self):
        """4. Development + no JWT_SECRET -> existing dev fallback behavior preserved."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=True):
            secret = get_jwt_secret()
            self.assertEqual(secret, DEFAULT_DEV_JWT_SECRET)
            # Should not raise exception
            validate_jwt_config()
        print("[PASS] Test 4 (Development Mode Fallback Preserved) PASSED.")

    def test_5_jwt_lifecycle_and_auth_integrity(self):
        """5. Verify end-to-end JWT lifecycle (token creation & decoding) works with valid key."""
        strong_secret = "integration_test_secret_key_1234567890_abc"
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "JWT_SECRET": strong_secret}):
            payload_data = {"sub": "user_p485_101", "email": "test@example.com"}
            token = create_access_token(payload_data)
            decoded = decode_access_token(token)
            
            self.assertIsNotNone(decoded)
            self.assertEqual(decoded["sub"], "user_p485_101")
            self.assertEqual(decoded["email"], "test@example.com")
        print("[PASS] Test 5 (JWT Lifecycle & Token Auth Integrity Verified) PASSED.")

    def test_6_production_startup_lifespan_simulation_passes_with_valid_secret(self):
        """6. Production startup simulation passes validate_jwt_config and validate_sandbox_config with valid secrets."""
        strong_secret = "railway_production_valid_jwt_secret_key_99887766"
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "JWT_SECRET": strong_secret, "SANDBOX_MODE": "e2b_required"}):
            from app.core.config import validate_sandbox_config
            validate_sandbox_config()
            validate_jwt_config()
            self.assertEqual(get_jwt_secret(), strong_secret)
        print("[PASS] Test 6 (Production Startup Simulation Passed) PASSED.")


if __name__ == "__main__":
    unittest.main()
