import json
import base64
import os
from datetime import datetime, timezone

import httpx

from app.core.config import N8N_WEBHOOK_URL


async def send_webhook(event: str, project_id: str, data: dict):
    if not N8N_WEBHOOK_URL:
        return

    payload = {
        "event": event,
        "project_id": project_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }

    try:
        async with httpx.AsyncClient() as client:
            await client.post(N8N_WEBHOOK_URL, json=payload, timeout=10)
    except Exception:
        pass


async def send_agent_event(
    event: str,
    project_id: str,
    role: str,
    content: dict | None = None,
    review: dict | None = None,
):
    data: dict = {"role": role}

    if content:
        if isinstance(content, dict):
            summary_keys = [
                "project_name", "problem_analysis", "recommended_approach",
                "architecture_overview", "project_structure",
            ]
            summary = {}
            for key in summary_keys:
                if key in content:
                    val = content[key]
                    if isinstance(val, str) and len(val) > 300:
                        val = val[:300] + "..."
                    summary[key] = val
            data["summary"] = summary
        data["full_content"] = content

    if review:
        data["peer_review"] = review

    await send_webhook(event, project_id, data)


async def send_research_data(project_id: str, results: list[dict], sources: list[str]):
    await send_webhook("research_completed", project_id, {
        "result_count": len(results),
        "sources": sources,
        "results": results,
    })


async def send_approval_event(project_id: str, role: str, approved: bool, feedback: str | None = None):
    await send_webhook("founder_decision", project_id, {
        "role": role,
        "approved": approved,
        "feedback": feedback,
    })


async def send_deliverables_ready(project_id: str, project_name: str, deliverables: list[str]):
    await send_webhook("deliverables_ready", project_id, {
        "project_name": project_name,
        "deliverables": deliverables,
    })


async def send_share_request(
    project_id: str,
    share_type: str,
    project_data: dict,
    outputs: list,
    memory: dict,
    file_paths: dict | None = None,
):
    structured = _build_structured_export(project_data, outputs, memory)

    payload: dict = {
        "share_type": share_type,
        "project_name": structured["project_name"],
        "structured_data": structured,
    }

    if file_paths:
        attachments = {}
        for label, path in file_paths.items():
            if path and os.path.exists(path):
                with open(path, "rb") as f:
                    attachments[label] = {
                        "filename": os.path.basename(path),
                        "content_base64": base64.b64encode(f.read()).decode(),
                        "size_bytes": os.path.getsize(path),
                    }
        if attachments:
            payload["attachments"] = attachments

    await send_webhook(f"share_{share_type}", project_id, payload)


def _build_structured_export(project: dict, outputs: list, memory: dict) -> dict:
    def _get_role(role: str):
        for o in reversed(outputs):
            if o["role"] == role:
                return o.get("content", {})
        return {}

    ceo = _get_role("ceo")
    ba = _get_role("business_analyst")
    researcher = _get_role("researcher")
    architect = _get_role("architect")
    engineer = _get_role("engineer")
    ppt = _get_role("ppt")

    def _pick(data, *keys):
        if not isinstance(data, dict):
            return None
        for k in keys:
            v = data.get(k)
            if v and isinstance(v, str):
                return v
        return None

    project_name = (
        _pick(ceo, "project_name", "title")
        or project.get("problem_statement", "Untitled")[:80]
    )

    report = ppt.get("report_data", {}) if isinstance(ppt.get("report_data"), dict) else {}

    return {
        "project_name": project_name,
        "problem_statement": project.get("problem_statement", ""),
        "status": project.get("status", ""),
        "created_at": project.get("created_at", ""),

        "title": project_name,
        "what_it_does": (
            report.get("what_it_does")
            or _pick(ceo, "vision", "executive_summary", "problem_summary")
            or ""
        ),
        "the_problem": (
            report.get("the_problem")
            or _pick(ceo, "problem_analysis", "problem_summary")
            or _pick(ba, "problem_analysis")
            or project.get("problem_statement", "")
        ),
        "what_it_solves": (
            report.get("what_it_solves")
            or _pick(ceo, "recommended_approach", "solution")
            or _pick(ba, "value_proposition", "proposed_solution")
            or ""
        ),
        "future_scope": report.get("future_scope", []),
        "cost_estimate": report.get("cost_estimate", {}),

        "agent_outputs": {
            "ceo": ceo,
            "business_analyst": ba,
            "researcher": researcher,
            "architect": architect,
            "engineer": engineer,
            "ppt": ppt,
        },

        "peer_reviews": {
            role: _safe_json(memory.get(f"peer_review_{role}"))
            for role in ["business_analyst", "researcher", "architect", "engineer"]
            if memory.get(f"peer_review_{role}")
        },

        "research_sources": _safe_json(memory.get("research_sources", "[]")),
    }


def _safe_json(raw):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return str(raw)
