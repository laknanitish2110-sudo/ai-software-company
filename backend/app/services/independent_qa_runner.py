"""
Independent QA Runner (FIND-01)

Executes structured QA assertions against a running application via HTTP.
Assertions are executed independently of Engineer-authored tests.

Results are strictly transient — never persisted to canonical files,
agent_outputs, ZIP, or GitHub exports.

Supports two execution modes:
- Local: httpx-based HTTP requests to localhost
- E2B: curl-based commands inside the E2B sandbox
"""

import json
import logging
from typing import List, Optional

import httpx

from app.models.independent_qa_schema import (
    QAAssertion,
    QAAssertionResult,
    IndependentQAResult,
)

logger = logging.getLogger(__name__)


async def execute_assertions_http(
    assertions: List[QAAssertion],
    host: str = "127.0.0.1",
    port: int = 3000,
    timeout: int = 5,
) -> IndependentQAResult:
    """
    Execute IQA assertions via httpx against a running application.
    Used by LocalSubprocessSandboxRunner while the server is alive.
    """
    if not assertions:
        return IndependentQAResult(
            status="UNAVAILABLE",
            reason="No assertions to execute.",
        )

    results: List[QAAssertionResult] = []
    base_url = f"http://{host}:{port}"

    async with httpx.AsyncClient(timeout=timeout) as client:
        for assertion in assertions:
            url = f"{base_url}{assertion.path}"
            result = QAAssertionResult(assertion=assertion)

            try:
                if assertion.method == "GET":
                    resp = await client.get(url)
                elif assertion.method == "POST":
                    resp = await client.post(url, json=assertion.request_body or {})
                elif assertion.method == "PUT":
                    resp = await client.put(url, json=assertion.request_body or {})
                elif assertion.method == "PATCH":
                    resp = await client.patch(url, json=assertion.request_body or {})
                elif assertion.method == "DELETE":
                    resp = await client.delete(url)
                else:
                    result.error = f"Unsupported HTTP method: {assertion.method}"
                    results.append(result)
                    continue

                result.actual_status = resp.status_code

                # Check status code
                status_ok = resp.status_code == assertion.expected_status

                # Check required response fields
                fields_ok = True
                if assertion.required_response_fields and status_ok:
                    try:
                        body = resp.json()
                        result.actual_response = (
                            body if isinstance(body, dict) else {"_raw": body}
                        )
                        for field in assertion.required_response_fields:
                            if isinstance(body, dict) and field not in body:
                                fields_ok = False
                                result.error += f"Missing response field: {field}. "
                            elif (
                                isinstance(body, list)
                                and body
                                and isinstance(body[0], dict)
                                and field not in body[0]
                            ):
                                fields_ok = False
                                result.error += (
                                    f"Missing field in array item: {field}. "
                                )
                    except Exception:
                        fields_ok = False
                        result.error += "Response is not valid JSON. "

                result.passed = status_ok and fields_ok
                if not status_ok:
                    result.error = (
                        f"Expected status {assertion.expected_status}, "
                        f"got {resp.status_code}. " + result.error
                    )

            except httpx.TimeoutException:
                result.error = f"Request timed out after {timeout}s"
            except httpx.ConnectError:
                result.error = f"Connection refused to {url}"
            except Exception as e:
                result.error = f"HTTP request error: {str(e)}"

            results.append(result)

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total = len(results)
    all_passed = failed == 0 and total > 0

    return IndependentQAResult(
        status="PASS" if all_passed else "FAIL",
        assertions_total=total,
        assertions_passed=passed,
        assertions_failed=failed,
        results=results,
        coverage_ratio=passed / total if total > 0 else 0.0,
        reason=(
            "All independent QA assertions passed."
            if all_passed
            else f"{failed}/{total} assertion(s) failed."
        ),
        requirements_count=total,
    )


def build_e2b_iqa_script(port: int) -> str:
    """
    Build a Python script that executes IQA assertions inside an E2B sandbox.
    Uses only stdlib (urllib) — no external dependencies required.
    Reads assertions from /tmp/.forgeai_iqa_assertions.json, outputs JSON results.
    """
    return """import json, urllib.request, urllib.error
assertions = json.loads(open('/tmp/.forgeai_iqa_assertions.json').read())
results = []
for a in assertions:
    try:
        url = "http://localhost:PORT_PLACEHOLDER" + a["path"]
        req = urllib.request.Request(url, method=a["method"])
        if a.get("request_body") and a["method"] in ("POST", "PUT", "PATCH"):
            req.data = json.dumps(a["request_body"]).encode("utf-8")
            req.add_header("Content-Type", "application/json")
        try:
            resp = urllib.request.urlopen(req, timeout=5)
            status = resp.status
        except urllib.error.HTTPError as he:
            status = he.code
        passed = status == a["expected_status"]
        err = "" if passed else "Expected %d, got %d" % (a["expected_status"], status)
        results.append({"passed": passed, "actual_status": status, "requirement_id": a.get("requirement_id", ""), "error": err})
    except Exception as e:
        results.append({"passed": False, "actual_status": None, "requirement_id": a.get("requirement_id", ""), "error": str(e)})
print(json.dumps(results))
""".replace("PORT_PLACEHOLDER", str(port))
