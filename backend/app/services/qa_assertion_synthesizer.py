"""
QA Assertion Synthesizer (FIND-01)

Deterministic pipeline: BA/Architect contracts → structured QAAssertion objects.
Uses keyword matching and structured field extraction — no LLM call.

Pipeline: BA functional_requirements + Architect api_structure → QAAssertion list
"""

import re
import logging
from typing import Dict, List, Tuple, Optional

from app.models.independent_qa_schema import QAAssertion
from app.models.execution_schema import ExecutionPlan, HealthCheckSpec

logger = logging.getLogger(__name__)

# Keyword → HTTP method mapping (deterministic, rule-based)
CRUD_PATTERNS = {
    "create": "POST",
    "add": "POST",
    "register": "POST",
    "submit": "POST",
    "signup": "POST",
    "sign up": "POST",
    "login": "POST",
    "log in": "POST",
    "upload": "POST",
    "send": "POST",
    "list": "GET",
    "get": "GET",
    "view": "GET",
    "retrieve": "GET",
    "fetch": "GET",
    "search": "GET",
    "display": "GET",
    "show": "GET",
    "read": "GET",
    "browse": "GET",
    "update": "PUT",
    "edit": "PUT",
    "modify": "PUT",
    "change": "PUT",
    "delete": "DELETE",
    "remove": "DELETE",
}

# Expected status codes per method
METHOD_STATUS = {
    "GET": 200,
    "POST": 201,
    "PUT": 200,
    "PATCH": 200,
    "DELETE": 200,
}

# Common resource nouns → API path fragments (deterministic pattern matching)
RESOURCE_PATTERNS = [
    (r'\b(tasks?)\b', '/tasks'),
    (r'\b(users?)\b', '/users'),
    (r'\b(items?)\b', '/items'),
    (r'\b(products?)\b', '/products'),
    (r'\b(orders?)\b', '/orders'),
    (r'\b(messages?)\b', '/messages'),
    (r'\b(posts?)\b', '/posts'),
    (r'\b(comments?)\b', '/comments'),
    (r'\b(projects?)\b', '/projects'),
    (r'\b(documents?)\b', '/documents'),
    (r'\b(files?)\b', '/files'),
    (r'\b(notes?)\b', '/notes'),
    (r'\b(events?)\b', '/events'),
    (r'\b(customers?)\b', '/customers'),
    (r'\b(reports?)\b', '/reports'),
    (r'\b(agents?)\b', '/agents'),
    (r'\b(workflows?)\b', '/workflows'),
    (r'\b(conversations?)\b', '/conversations'),
    (r'\b(sessions?)\b', '/sessions'),
    (r'\b(tickets?)\b', '/tickets'),
    (r'\b(articles?)\b', '/articles'),
    (r'\b(categories?)\b', '/categories'),
    (r'\b(tags?)\b', '/tags'),
    (r'\b(contacts?)\b', '/contacts'),
    (r'\b(invoices?)\b', '/invoices'),
    (r'\b(payments?)\b', '/payments'),
    (r'\b(reviews?)\b', '/reviews'),
    (r'\b(bookings?)\b', '/bookings'),
    (r'\b(appointments?)\b', '/appointments'),
    (r'\b(notifications?)\b', '/notifications'),
]


def synthesize_assertions(
    ba_output: dict,
    architect_output: dict,
    plan: ExecutionPlan
) -> Tuple[List[QAAssertion], str]:
    """
    Deterministic assertion synthesis from BA/Architect contracts.

    Returns:
        Tuple of (assertions_list, unavailable_reason_if_empty)
    """
    # 1. Check project is API-capable
    if not plan.executable:
        return [], "Non-executable project type (e.g., n8n workflow). No API endpoints to test."

    if not plan.commands.health_check:
        return [], "No health check configured. Cannot determine API server port."

    if plan.project_type in ("n8n",):
        return [], f"Project type '{plan.project_type}' does not support REST API validation."

    assertions: List[QAAssertion] = []
    seen_keys: set = set()  # (method, path) dedup

    # 2. Extract assertions from Architect API design (highest fidelity source)
    api_endpoints = (
        architect_output.get("api_structure")
        or architect_output.get("api_design")
        or []
    )
    if isinstance(api_endpoints, list):
        for idx, ep in enumerate(api_endpoints, start=1):
            if not isinstance(ep, dict):
                continue
            method = str(ep.get("method", "GET")).upper()
            path = ep.get("path", "")
            if not path:
                continue

            key = (method, path)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            # Extract expected response fields from response shape
            resp_shape = ep.get("response_shape") or ep.get("response") or {}
            required_fields: List[str] = []
            if isinstance(resp_shape, dict):
                required_fields = list(resp_shape.keys())[:5]

            expected_status = int(
                ep.get("expected_status", METHOD_STATUS.get(method, 200))
            )

            assertions.append(QAAssertion(
                requirement_id=f"ARCH-API-{idx}",
                requirement_text=ep.get("purpose", ep.get("description", f"{method} {path}")),
                method=method,
                path=path,
                expected_status=expected_status,
                required_response_fields=required_fields,
                description=f"Architect endpoint: {method} {path}",
            ))

    # 3. Extract assertions from BA functional requirements (keyword matching)
    func_reqs = ba_output.get("functional_requirements") or []
    if isinstance(func_reqs, list):
        for idx, req in enumerate(func_reqs, start=1):
            req_text = ""
            if isinstance(req, str):
                req_text = req
            elif isinstance(req, dict):
                req_text = (
                    req.get("description")
                    or req.get("text")
                    or req.get("requirement")
                    or str(req)
                )

            if not req_text:
                continue

            lower = req_text.lower()

            # Find CRUD operation via keyword matching
            method = None
            for keyword, http_method in CRUD_PATTERNS.items():
                if keyword in lower:
                    method = http_method
                    break

            if not method:
                continue  # Not an API-testable requirement

            # Find resource path via regex matching
            path = None
            for pattern, api_path in RESOURCE_PATTERNS:
                if re.search(pattern, lower):
                    path = api_path
                    break

            if not path:
                continue  # Can't determine API path

            key = (method, path)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            expected_status = METHOD_STATUS.get(method, 200)

            assertions.append(QAAssertion(
                requirement_id=f"FR-{idx}",
                requirement_text=req_text,
                method=method,
                path=path,
                expected_status=expected_status,
                description=f"BA requirement: {req_text[:100]}",
            ))

    if not assertions:
        return [], "No API-testable requirements found in BA/Architect output."

    logger.info(f"Synthesized {len(assertions)} independent QA assertions.")
    return assertions, ""
