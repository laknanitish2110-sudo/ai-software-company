import os
import sys
import asyncio
import unittest
from fastapi.testclient import TestClient

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app
from app.core.database import init_db, get_db, create_user, create_project, get_project_for_user
from app.core.auth import hash_password, verify_password, create_access_token, decode_access_token


from app.core.database import new_id
from starlette.websockets import WebSocketDisconnect

class TestP41AuthSecurity(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["ENVIRONMENT"] = "development"
        os.environ["SANDBOX_MODE"] = "local_dev"
        asyncio.run(init_db())
        cls.client = TestClient(app)

    def setUp(self):
        os.environ["ENVIRONMENT"] = "development"
        os.environ["SANDBOX_MODE"] = "local_dev"

    def test_01_password_hashing_security(self):
        """Verify passwords are hashed with salt and not stored in plaintext."""
        raw_pw = "SuperSecret123!"
        hashed = hash_password(raw_pw)
        self.assertNotEqual(raw_pw, hashed)
        self.assertTrue(hashed.startswith("pbkdf2:"))
        self.assertTrue(verify_password(raw_pw, hashed))
        self.assertFalse(verify_password("WrongPassword", hashed))
        print("[PASS] 1. Password Hashing & PBKDF2 Verification PASSED.")

    def test_02_jwt_token_lifecycle(self):
        """Verify JWT access token creation and decoding."""
        token = create_access_token({"sub": "user_123", "email": "test@example.com"})
        payload = decode_access_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], "user_123")
        self.assertEqual(payload["email"], "test@example.com")
        
        invalid_payload = decode_access_token("invalid.jwt.token")
        self.assertIsNone(invalid_payload)
        print("[PASS] 2. JWT Token Lifecycle PASSED.")

    def test_03_registration_and_login_endpoints(self):
        """Test registration, duplicate email rejection, login, and /auth/me."""
        email = f"user_{new_id()}@example.com"
        # 1. Register User A
        reg_res = self.client.post("/api/auth/register", json={"email": email, "password": "Password123"})
        self.assertEqual(reg_res.status_code, 200)
        data = reg_res.json()
        self.assertIn("access_token", data)
        token_a = data["access_token"]
        user_a_id = data["user"]["id"]

        # 2. Duplicate registration attempt
        dup_res = self.client.post("/api/auth/register", json={"email": email, "password": "Password123"})
        self.assertEqual(dup_res.status_code, 400)

        # 3. Login User A
        login_res = self.client.post("/api/auth/login", json={"email": email, "password": "Password123"})
        self.assertEqual(login_res.status_code, 200)
        self.assertIn("access_token", login_res.json())

        # 4. Get /auth/me
        me_res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_a}"})
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["user"]["id"], user_a_id)
        print("[PASS] 3. Registration, Login, and /auth/me PASSED.")

    def test_04_idor_and_ownership_enforcement(self):
        """Verify CASES A, B, C, D, E, F: Owner access, IDOR protection, cross-user isolation."""
        email_a = f"owner_{new_id()}@example.com"
        email_b = f"attacker_{new_id()}@example.com"
        # Register User A and User B
        res_a = self.client.post("/api/auth/register", json={"email": email_a, "password": "Password123"})
        token_a = res_a.json()["access_token"]
        user_a_id = res_a.json()["user"]["id"]

        res_b = self.client.post("/api/auth/register", json={"email": email_b, "password": "Password123"})
        token_b = res_b.json()["access_token"]
        user_b_id = res_b.json()["user"]["id"]

        # CASE A: User A creates project -> User A can access it (200 SUCCESS)
        create_res = self.client.post(
            "/api/projects",
            json={"problem_statement": "Build Task API"},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        self.assertEqual(create_res.status_code, 200)
        proj_a = create_res.json()
        proj_a_id = proj_a["id"]
        self.assertEqual(proj_a["user_id"], user_a_id)

        # User A fetches project detail (200)
        get_a_res = self.client.get(f"/api/projects/{proj_a_id}", headers={"Authorization": f"Bearer {token_a}"})
        self.assertEqual(get_a_res.status_code, 200)
        print("[PASS] CASE A (Owner Access Allowed) PASSED.")

        # CASE B: User B attempts to access User A's project -> DENIED (404 Not Found)
        get_b_res = self.client.get(f"/api/projects/{proj_a_id}", headers={"Authorization": f"Bearer {token_b}"})
        self.assertEqual(get_b_res.status_code, 404)
        print("[PASS] CASE B (Cross-User IDOR Access Blocked) PASSED.")

        # CASE C: User B attempts to approve User A's project output -> DENIED (404 Not Found)
        approve_b_res = self.client.post(
            f"/api/projects/{proj_a_id}/approve/out_123",
            json={"approved": True, "feedback": "fake"},
            headers={"Authorization": f"Bearer {token_b}"}
        )
        self.assertEqual(approve_b_res.status_code, 404)
        print("[PASS] CASE C (Cross-User Approval Blocked) PASSED.")

        # CASE D: User B attempts to delete User A's project -> DENIED (404 Not Found)
        del_b_res = self.client.delete(f"/api/projects/{proj_a_id}", headers={"Authorization": f"Bearer {token_b}"})
        self.assertEqual(del_b_res.status_code, 404)
        print("[PASS] CASE D (Cross-User Deletion Blocked) PASSED.")

        # CASE E: Unauthenticated user accesses protected endpoint -> 401 UNAUTHORIZED
        no_auth_res = self.client.get(f"/api/projects/{proj_a_id}")
        self.assertEqual(no_auth_res.status_code, 401)
        print("[PASS] CASE E (Unauthenticated Request Rejected with 401) PASSED.")

        # CASE F: User B attempts to access generated files of User A -> DENIED (404 Not Found)
        files_b_res = self.client.get(f"/api/projects/{proj_a_id}/files", headers={"Authorization": f"Bearer {token_b}"})
        self.assertEqual(files_b_res.status_code, 404)
        
        download_b_res = self.client.get(f"/api/projects/{proj_a_id}/download/code", headers={"Authorization": f"Bearer {token_b}"})
        self.assertEqual(download_b_res.status_code, 404)
        print("[PASS] CASE F (Cross-User Generated File Access Blocked) PASSED.")

        # Cleanup: User A can delete their own project (200)
        del_a_res = self.client.delete(f"/api/projects/{proj_a_id}", headers={"Authorization": f"Bearer {token_a}"})
        self.assertEqual(del_a_res.status_code, 200)

    def test_05_websocket_authorization(self):
        """Verify CASE G: Unauthenticated or unauthorized WebSocket subscriptions are rejected."""
        email_a = f"ws_a_{new_id()}@example.com"
        email_b = f"ws_b_{new_id()}@example.com"
        res_a = self.client.post("/api/auth/register", json={"email": email_a, "password": "Password123"})
        token_a = res_a.json()["access_token"]
        
        res_b = self.client.post("/api/auth/register", json={"email": email_b, "password": "Password123"})
        token_b = res_b.json()["access_token"]

        create_res = self.client.post(
            "/api/projects",
            json={"problem_statement": "WS Test Project"},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        proj_id = create_res.json()["id"]

        # 1. User B attempts WebSocket subscription to User A's project -> REJECTED (code 4003 or closed)
        with self.assertRaises(WebSocketDisconnect) as ctx_b:
            with self.client.websocket_connect(f"/ws/{proj_id}?token={token_b}"):
                pass
        self.assertIn(ctx_b.exception.code, (4003, 1000))

        # 2. Unauthenticated WebSocket subscription -> REJECTED (code 4001 or closed)
        with self.assertRaises(WebSocketDisconnect) as ctx_anon:
            with self.client.websocket_connect(f"/ws/{proj_id}"):
                pass
        self.assertIn(ctx_anon.exception.code, (4001, 1000))

        # 3. User A (Owner) WebSocket subscription -> CONNECTS SUCCESSFULLY
        try:
            with self.client.websocket_connect(f"/ws/{proj_id}?token={token_a}") as websocket:
                websocket.send_json({"type": "ping"})
        except WebSocketDisconnect as e:
            self.assertEqual(e.code, 1000)
        print("[PASS] CASE G (WebSocket Authorization Enforced) PASSED.")


if __name__ == "__main__":
    unittest.main()
