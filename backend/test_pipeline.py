"""Full pipeline test - creates a project, auto-approves, checks n8n webhooks."""
import asyncio
import json
import sys
import time
import httpx

API = "http://localhost:8000/api"
N8N_API = "https://n8n.srv1867770.hstgr.cloud/api/v1"
N8N_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZDliMmJjNy0wMjI2LTQwYTItOWZhMS04OWY0MTY0NmQzNTciLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMjJkOGU4MWEtNmU1MC00ODFjLWJkODgtNTdkMDYzOWI4OTlmIiwiaWF0IjoxNzg1NTA5OTY4fQ.5PgV6Oahn5eqYVO19dwqpEXyeOOwVWrLcdMHu0exT-s"

PROBLEM = "Smart waste management system for Indian municipalities using IoT sensors and AI"

PIPELINE = ["ceo", "business_analyst", "researcher", "architect", "engineer", "ppt"]
APPROVAL_STATUSES = {
    "ba_review": "business_analyst",
    "research_review": "researcher",
    "architect_review": "architect",
    "engineer_review": "engineer",
}


async def main():
    async with httpx.AsyncClient(timeout=300) as client:
        # 1. Create project
        print(f"\n{'='*60}")
        print(f"PIPELINE TEST: {PROBLEM[:50]}...")
        print(f"{'='*60}\n")

        t0 = time.time()
        print("[1/7] Creating project (CEO agent runs inline)...")
        resp = await client.post(f"{API}/projects", json={"problem_statement": PROBLEM})
        project = resp.json()
        pid = project["id"]
        print(f"  Project ID: {pid}")
        print(f"  CEO completed in {time.time()-t0:.1f}s")

        # 2. Poll and auto-approve each stage
        completed_agents = ["ceo"]
        last_status = ""

        while True:
            await asyncio.sleep(5)
            try:
                resp = await client.get(f"{API}/projects/{pid}")
                state = resp.json()
            except Exception as e:
                print(f"  [poll error: {e}]")
                continue

            status = state["project"]["status"]
            if status != last_status:
                elapsed = time.time() - t0
                print(f"  [{elapsed:.0f}s] Status: {status}")
                last_status = status

            # Auto-approve if pending
            if status in APPROVAL_STATUSES:
                role = APPROVAL_STATUSES[status]
                if role not in completed_agents:
                    completed_agents.append(role)
                    outputs = state.get("outputs", [])
                    pending = [o for o in outputs if o["role"] == role and o["status"] == "pending"]
                    if pending:
                        oid = pending[-1]["id"]
                        print(f"  Auto-approving {role} (output {oid})...")
                        await client.post(
                            f"{API}/projects/{pid}/approve/{oid}",
                            json={"approved": True, "feedback": None},
                        )
                        print(f"  {role} approved! Next agent starting...")

            if status == "completed":
                elapsed = time.time() - t0
                print(f"\n{'='*60}")
                print(f"PIPELINE COMPLETE in {elapsed:.0f}s")
                print(f"{'='*60}")
                break

            if time.time() - t0 > 600:
                print("\nTIMEOUT after 10 minutes")
                break

        # 3. Check deliverables
        print("\n[Deliverables]")
        for endpoint, label in [
            (f"/projects/{pid}/download/pptx", "PPTX"),
            (f"/projects/{pid}/download/docx", "DOCX"),
            (f"/projects/{pid}/download/code", "Code ZIP"),
        ]:
            try:
                resp = await client.head(f"http://localhost:8000/api{endpoint}")
                status = "READY" if resp.status_code == 200 else f"NOT FOUND ({resp.status_code})"
            except Exception:
                status = "ERROR"
            print(f"  {label}: {status}")

        # 4. Check n8n execution history
        print("\n[n8n Webhook Events]")
        try:
            resp = await client.get(
                f"{N8N_API}/executions",
                headers={"X-N8N-API-KEY": N8N_KEY},
                params={"limit": 20},
            )
            execs = resp.json().get("data", [])
            hub_execs = [e for e in execs if "Event Hub" in (e.get("workflowData", {}).get("name", "") if isinstance(e.get("workflowData"), dict) else e.get("workflowName", ""))]
            print(f"  Total Event Hub executions: {len(hub_execs)}")
            for ex in hub_execs[:10]:
                print(f"    [{ex.get('status', '?')}] {ex.get('startedAt', '')[:19]} | mode: {ex.get('mode', '?')}")
        except Exception as e:
            print(f"  Could not fetch: {e}")

        print(f"\nDone. Project ID: {pid}")


if __name__ == "__main__":
    asyncio.run(main())
