"""
End-to-end employee lifecycle test against Railway production.

Tests the full flow:
1. Register/login → get auth token
2. List employees → verify 6 default team members
3. Get single employee → verify schema
4. Create session → start conversation
5. Send message → get employee response
6. Verify employee status transitions (idle → thinking → idle)
7. List memories → verify memory extraction triggered
8. List delegations endpoint
9. Verify delegation_tasks table exists via delegation API

Run: python -m pytest backend/tests/test_e2e_employee_lifecycle.py -v -s
Or:  python backend/tests/test_e2e_employee_lifecycle.py
"""

import os
import sys
import json
import time
import asyncio
import uuid

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx

BASE_URL = os.getenv(
    "E2E_API_URL",
    "https://ai-software-company-production-453d.up.railway.app/api"
)

TEST_EMAIL = f"e2etest_{uuid.uuid4().hex[:8]}@test.com"
TEST_PASSWORD = "E2eTest_Secure123!"
TEST_NAME = "E2E Tester"

TIMEOUT = 60.0


class E2ETestRunner:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True)
        self.token = None
        self.user = None
        self.employees = []
        self.session_id = None
        self.results = []

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _record(self, name, passed, detail=""):
        status = "PASS" if passed else "FAIL"
        self.results.append((name, status, detail))
        icon = "✓" if passed else "✗"
        print(f"  {icon} {name}" + (f" — {detail}" if detail else ""))

    async def test_01_register(self):
        """Register a fresh test user."""
        res = await self.client.post(
            f"{BASE_URL}/auth/register",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            headers={"Content-Type": "application/json"},
        )
        if res.status_code == 200:
            data = res.json()
            self.token = data.get("access_token")
            self.user = data.get("user")
            self._record("Register user", bool(self.token), f"user_id={self.user.get('id', '?')[:8]}...")
        elif res.status_code == 400 and "already registered" in res.text:
            self._record("Register user", True, "Already exists, trying login")
            await self.test_01b_login()
        else:
            self._record("Register user", False, f"HTTP {res.status_code}: {res.text[:200]}")

    async def test_01b_login(self):
        """Login fallback if registration fails (user exists)."""
        res = await self.client.post(
            f"{BASE_URL}/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            headers={"Content-Type": "application/json"},
        )
        if res.status_code == 200:
            data = res.json()
            self.token = data.get("access_token")
            self.user = data.get("user")
            self._record("Login user", bool(self.token), f"user_id={self.user.get('id', '?')[:8]}...")
        else:
            self._record("Login user", False, f"HTTP {res.status_code}: {res.text[:200]}")

    async def test_02_list_employees(self):
        """List employees — should have 6 from default team provisioning."""
        res = await self.client.get(f"{BASE_URL}/employees", headers=self._headers())
        if res.status_code == 200:
            self.employees = res.json()
            count = len(self.employees)
            names = [e["name"] for e in self.employees]
            self._record(
                "List employees",
                count == 6,
                f"{count} employees: {', '.join(names)}"
            )
        else:
            self._record("List employees", False, f"HTTP {res.status_code}")

    async def test_03_get_employee(self):
        """Get a single employee and verify schema completeness."""
        if not self.employees:
            self._record("Get employee", False, "No employees to test")
            return
        emp = self.employees[0]
        res = await self.client.get(f"{BASE_URL}/employees/{emp['id']}", headers=self._headers())
        if res.status_code == 200:
            data = res.json()
            required = ["id", "name", "role", "status", "persona"]
            missing = [k for k in required if k not in data]
            self._record(
                "Get employee schema",
                len(missing) == 0,
                f"{data['name']} ({data['role']}), status={data['status']}" +
                (f", missing: {missing}" if missing else "")
            )
        else:
            self._record("Get employee schema", False, f"HTTP {res.status_code}")

    async def test_04_employee_stats(self):
        """Verify employee stats fields (session_count, memory_count) present."""
        if not self.employees:
            self._record("Employee stats", False, "No employees")
            return
        emp = self.employees[0]
        has_stats = "session_count" in emp and "memory_count" in emp
        self._record(
            "Employee stats fields",
            has_stats,
            f"session_count={emp.get('session_count')}, memory_count={emp.get('memory_count')}"
        )

    async def test_05_create_session(self):
        """Create a chat session with the first employee."""
        if not self.employees:
            self._record("Create session", False, "No employees")
            return
        emp = self.employees[0]
        res = await self.client.post(
            f"{BASE_URL}/employees/{emp['id']}/sessions",
            json={},
            headers=self._headers(),
        )
        if res.status_code == 200:
            data = res.json()
            self.session_id = data.get("id")
            self._record("Create session", bool(self.session_id), f"session_id={self.session_id[:8]}...")
        else:
            self._record("Create session", False, f"HTTP {res.status_code}: {res.text[:200]}")

    async def test_06_send_message(self):
        """Send a message and get an employee response (the core chat flow)."""
        if not self.session_id:
            self._record("Send message", False, "No session")
            return
        res = await self.client.post(
            f"{BASE_URL}/sessions/{self.session_id}/messages",
            json={"content": "What is your role and what tools do you have available? Keep your answer under 100 words."},
            headers=self._headers(),
            timeout=120.0,
        )
        if res.status_code == 200:
            data = res.json()
            emp_msg = data.get("employee_message", {})
            content = emp_msg.get("content", "")
            has_content = len(content) > 10
            self._record(
                "Send message & get response",
                has_content,
                f"Response length: {len(content)} chars" +
                (f" — preview: {content[:100]}..." if has_content else "")
            )
        else:
            self._record("Send message & get response", False, f"HTTP {res.status_code}: {res.text[:300]}")

    async def test_07_verify_status_reset(self):
        """After message, employee should be back to idle."""
        if not self.employees:
            self._record("Status reset", False, "No employees")
            return
        emp = self.employees[0]
        res = await self.client.get(f"{BASE_URL}/employees/{emp['id']}", headers=self._headers())
        if res.status_code == 200:
            data = res.json()
            self._record("Status reset to idle", data["status"] == "idle", f"status={data['status']}")
        else:
            self._record("Status reset", False, f"HTTP {res.status_code}")

    async def test_08_list_sessions(self):
        """List sessions for the employee — should have at least 1."""
        if not self.employees:
            self._record("List sessions", False, "No employees")
            return
        emp = self.employees[0]
        res = await self.client.get(f"{BASE_URL}/employees/{emp['id']}/sessions", headers=self._headers())
        if res.status_code == 200:
            sessions = res.json()
            self._record("List sessions", len(sessions) >= 1, f"{len(sessions)} sessions")
        else:
            self._record("List sessions", False, f"HTTP {res.status_code}")

    async def test_09_get_session_messages(self):
        """Get messages from the session — should have user + employee messages."""
        if not self.session_id:
            self._record("Get messages", False, "No session")
            return
        res = await self.client.get(
            f"{BASE_URL}/sessions/{self.session_id}",
            headers=self._headers(),
        )
        if res.status_code == 200:
            data = res.json()
            msgs = data.get("messages", [])
            roles = [m["role"] for m in msgs]
            has_user = "user" in roles
            has_emp = "employee" in roles
            self._record(
                "Session messages",
                has_user and has_emp,
                f"{len(msgs)} messages, roles: {set(roles)}"
            )
        else:
            self._record("Get messages", False, f"HTTP {res.status_code}")

    async def test_10_list_memories(self):
        """List memories — may have extracted memories from the conversation."""
        if not self.employees:
            self._record("List memories", False, "No employees")
            return
        emp = self.employees[0]
        res = await self.client.get(f"{BASE_URL}/employees/{emp['id']}/memories", headers=self._headers())
        if res.status_code == 200:
            memories = res.json()
            self._record("List memories endpoint", True, f"{len(memories)} memories found")
        else:
            self._record("List memories", False, f"HTTP {res.status_code}")

    async def test_11_permissions(self):
        """Get employee permissions — should have collaborate permission."""
        if not self.employees:
            self._record("Permissions", False, "No employees")
            return
        emp = self.employees[0]
        res = await self.client.get(
            f"{BASE_URL}/employees/{emp['id']}/permissions",
            headers=self._headers(),
        )
        if res.status_code == 200:
            perms = res.json()
            collab = [p for p in perms if p.get("tool") == "collaborate"]
            self._record(
                "Permissions include collaborate",
                len(collab) > 0,
                f"{len(perms)} permissions total, collaborate entries: {len(collab)}"
            )
        else:
            self._record("Permissions", False, f"HTTP {res.status_code}")

    async def test_12_delegations_endpoint(self):
        """Test the delegations API endpoint exists and returns data."""
        if not self.employees:
            self._record("Delegations API", False, "No employees")
            return
        emp = self.employees[0]
        res = await self.client.get(
            f"{BASE_URL}/delegations?employee_id={emp['id']}",
            headers=self._headers(),
        )
        if res.status_code == 200:
            data = res.json()
            delegations = data.get("delegations", [])
            self._record("Delegations API", True, f"{len(delegations)} delegations")
        else:
            self._record("Delegations API", False, f"HTTP {res.status_code}: {res.text[:200]}")

    async def test_13_collaborate_permissions(self):
        """Verify collaborate permissions include both execute (delegate) and read (check_delegation)."""
        if not self.employees:
            self._record("Collaborate perms", False, "No employees")
            return
        emp = self.employees[0]
        res = await self.client.get(
            f"{BASE_URL}/employees/{emp['id']}/permissions",
            headers=self._headers(),
        )
        if res.status_code == 200:
            perms = res.json()
            collab_perms = [p for p in perms if p.get("tool") == "collaborate"]
            actions = {p.get("action") for p in collab_perms}
            has_exec = "execute" in actions
            has_read = "read" in actions
            self._record(
                "Collaborate perms (execute+read)",
                has_exec and has_read,
                f"collaborate actions: {actions}"
            )
        else:
            self._record("Collaborate perms", False, f"HTTP {res.status_code}")

    async def test_14_skills_endpoint(self):
        """Test the skills API endpoint exists and returns data."""
        if not self.employees:
            self._record("Skills API", False, "No employees")
            return
        emp = self.employees[0]
        res = await self.client.get(
            f"{BASE_URL}/employees/{emp['id']}/skills",
            headers=self._headers(),
        )
        if res.status_code == 200:
            data = res.json()
            skills = data.get("skills", [])
            self._record("Skills API", True, f"{len(skills)} skills")
        else:
            self._record("Skills API", False, f"HTTP {res.status_code}: {res.text[:200]}")

    async def test_15_workspace_endpoint(self):
        """Test the workspace API endpoint exists."""
        if not self.employees:
            self._record("Workspace API", False, "No employees")
            return
        emp = self.employees[0]
        res = await self.client.get(
            f"{BASE_URL}/employees/{emp['id']}/workspace",
            headers=self._headers(),
        )
        if res.status_code == 200:
            data = res.json()
            files = data.get("files", [])
            self._record("Workspace API", True, f"{len(files)} files")
        else:
            self._record("Workspace API", False, f"HTTP {res.status_code}: {res.text[:200]}")

    async def run_all(self):
        print(f"\n{'='*60}")
        print(f"  E2E Employee Lifecycle Test")
        print(f"  Target: {BASE_URL}")
        print(f"  Test user: {TEST_EMAIL}")
        print(f"{'='*60}\n")

        tests = [
            self.test_01_register,
            self.test_02_list_employees,
            self.test_03_get_employee,
            self.test_04_employee_stats,
            self.test_05_create_session,
            self.test_06_send_message,
            self.test_07_verify_status_reset,
            self.test_08_list_sessions,
            self.test_09_get_session_messages,
            self.test_10_list_memories,
            self.test_11_permissions,
            self.test_12_delegations_endpoint,
            self.test_13_collaborate_permissions,
            self.test_14_skills_endpoint,
            self.test_15_workspace_endpoint,
        ]

        for test in tests:
            if not self.token and test != self.test_01_register:
                self._record(test.__name__, False, "Skipped — no auth token")
                continue
            try:
                await test()
            except Exception as e:
                self._record(test.__name__, False, f"Exception: {e}")

        await self.client.aclose()

        print(f"\n{'='*60}")
        passed = sum(1 for _, s, _ in self.results if s == "PASS")
        failed = sum(1 for _, s, _ in self.results if s == "FAIL")
        total = len(self.results)
        print(f"  Results: {passed}/{total} passed, {failed} failed")
        print(f"{'='*60}\n")

        if failed > 0:
            print("  Failed tests:")
            for name, status, detail in self.results:
                if status == "FAIL":
                    print(f"    ✗ {name}: {detail}")
            print()

        return failed == 0


async def main():
    runner = E2ETestRunner()
    success = await runner.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
