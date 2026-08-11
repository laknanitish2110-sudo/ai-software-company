import json
import re
import asyncio
import time
import logging
from openai import OpenAI

from app.core.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, SMART_MODEL, MODEL_MAP, FALLBACK_MAP
from app.core.database import (
    get_project,
    get_project_outputs,
    get_memory,
    save_agent_output,
    set_memory,
    get_conversation,
    save_conversation,
)
from app.agents.prompts import (
    CEO_SYSTEM_PROMPT,
    BA_SYSTEM_PROMPT,
    RESEARCHER_SYSTEM_PROMPT,
    ARCHITECT_SYSTEM_PROMPT,
    ENGINEER_SYSTEM_PROMPT,
    PPT_SYSTEM_PROMPT,
    CROSS_REVIEW_PROMPT,
    REVIEW_CRITERIA,
)
from app.models.schemas import AgentRole
from app.services.web_search import research_topic
from app.services.webhook import send_research_data

logger = logging.getLogger(__name__)

client = OpenAI(
    base_url=OPENROUTER_BASE_URL,
    api_key=OPENROUTER_API_KEY,
)

SYSTEM_PROMPTS = {
    AgentRole.CEO: CEO_SYSTEM_PROMPT,
    AgentRole.BUSINESS_ANALYST: BA_SYSTEM_PROMPT,
    AgentRole.RESEARCHER: RESEARCHER_SYSTEM_PROMPT,
    AgentRole.ARCHITECT: ARCHITECT_SYSTEM_PROMPT,
    AgentRole.ENGINEER: ENGINEER_SYSTEM_PROMPT,
    AgentRole.PPT: PPT_SYSTEM_PROMPT,
}

ROLE_LABELS = {
    AgentRole.CEO: "CEO / Project Manager",
    AgentRole.BUSINESS_ANALYST: "Business Analyst",
    AgentRole.RESEARCHER: "Research Engineer",
    AgentRole.ARCHITECT: "Solution Architect",
    AgentRole.ENGINEER: "Software Engineer",
    AgentRole.PPT: "Presentation & Documentation Specialist",
}

AGENT_TIMEOUTS = {
    AgentRole.CEO: 90,
    AgentRole.BUSINESS_ANALYST: 150,
    AgentRole.RESEARCHER: 180,
    AgentRole.ARCHITECT: 120,
    AgentRole.ENGINEER: 360,
    AgentRole.PPT: 150,
}

MAX_RETRIES = 3
RETRY_DELAYS = [2, 4, 8]


def _repair_json(raw: str) -> str:
    text = raw.strip()

    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    if "```json" in text:
        match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            text = match.group(1)

    if "```" in text:
        match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            text = match.group(1)

    text = re.sub(r',\s*([}\]])', r'\1', text)
    text = re.sub(r':\s*undefined', ': null', text)

    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    return text


async def _llm_call_single(
    model: str,
    messages: list[dict],
    max_tokens: int,
    timeout: int,
    stream_callback=None,
) -> str:
    if stream_callback:
        collected = []
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
            stream=True,
            timeout=timeout,
        )
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                collected.append(token)
                await stream_callback(token)
        return "".join(collected)
    else:
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
            timeout=timeout,
        )
        return response.choices[0].message.content.strip()


async def _llm_call_with_retry(
    model: str,
    messages: list[dict],
    max_tokens: int,
    timeout: int,
    stream_callback=None,
    fallback_model: str | None = None,
) -> tuple[str, str]:
    """Returns (response_text, model_used)."""
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            text = await _llm_call_single(model, messages, max_tokens, timeout, stream_callback)
            return text, model
        except Exception as e:
            last_error = e
            logger.warning(f"LLM call attempt {attempt + 1}/{MAX_RETRIES} failed ({model}): {e}")
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[attempt]
                logger.info(f"Retrying in {delay}s...")
                await asyncio.sleep(delay)

    if fallback_model and fallback_model != model:
        logger.warning(f"Primary model {model} exhausted — failing over to {fallback_model}")
        for attempt in range(MAX_RETRIES):
            try:
                text = await _llm_call_single(fallback_model, messages, max_tokens, timeout, stream_callback)
                return text, fallback_model
            except Exception as e:
                last_error = e
                logger.warning(f"Fallback attempt {attempt + 1}/{MAX_RETRIES} failed ({fallback_model}): {e}")
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[attempt]
                    await asyncio.sleep(delay)

    raise RuntimeError(f"LLM call failed after all retries (primary: {model}, fallback: {fallback_model}): {last_error}")


def _build_context(project: dict, outputs: list[dict], memory: dict) -> str:
    parts = [
        f"## Problem Statement\n{project['problem_statement']}",
    ]

    role_order = ["ceo", "business_analyst", "researcher", "architect", "engineer"]
    for role in role_order:
        for output in outputs:
            if output["role"] == role and output["status"] == "approved":
                label = ROLE_LABELS.get(AgentRole(role), role)
                parts.append(f"## {label}'s Approved Output\n```json\n{json.dumps(output['content'], indent=2)}\n```")

    workflow_recs = memory.pop("workflow_recommendations", None)
    if workflow_recs:
        try:
            recs = json.loads(workflow_recs) if isinstance(workflow_recs, str) else workflow_recs
            wf_parts = [f"## Existing n8n Workflow Library Analysis\n**{recs.get('summary', '')}**"]
            if recs.get("reusable"):
                wf_parts.append("### Reusable Workflows (use directly)")
                for w in recs["reusable"]:
                    wf_parts.append(f"- **{w['name']}** ({w['category']}) — integrations: {w['integrations']} | relevance: {w['score']:.0%}")
            if recs.get("modifiable"):
                wf_parts.append("### Modifiable Workflows (adapt for this problem)")
                for w in recs["modifiable"]:
                    wf_parts.append(f"- **{w['name']}** ({w['category']}) — integrations: {w['integrations']} | relevance: {w['score']:.0%}")
            if recs.get("inspiration"):
                wf_parts.append("### Inspiration Workflows (patterns to learn from)")
                for w in recs["inspiration"]:
                    wf_parts.append(f"- {w['name']} ({w['category']})")
            if recs.get("categories_matched"):
                wf_parts.append(f"\n**Matched categories:** {', '.join(recs['categories_matched'])}")
            if recs.get("sih_themes_matched"):
                wf_parts.append(f"**SIH themes:** {', '.join(recs['sih_themes_matched'])}")
            parts.append("\n".join(wf_parts))
        except Exception:
            pass

    filtered_memory = {k: v for k, v in memory.items() if k != "workflow_recommendations"}
    if filtered_memory:
        parts.append(f"## Shared Project Memory\n```json\n{json.dumps(filtered_memory, indent=2)}\n```")

    return "\n\n".join(parts)


async def run_agent(project_id: str, role: AgentRole, progress_callback=None, stream_callback=None) -> dict:
    project = await get_project(project_id)
    if not project:
        raise ValueError(f"Project {project_id} not found")

    outputs = await get_project_outputs(project_id)
    memory = await get_memory(project_id)

    context = _build_context(project, outputs, memory)
    system_prompt = SYSTEM_PROMPTS[role]

    if progress_callback:
        await progress_callback(f"{ROLE_LABELS[role]} is analyzing the project...")

    extra_context = ""
    if role == AgentRole.RESEARCHER:
        try:
            web_results, raw_results, sources = research_topic(project["problem_statement"])
            extra_context = f"\n\n## Live Web Research\nThe following are REAL search results from the internet. Use these to provide accurate, up-to-date information:\n\n{web_results}"
            if raw_results:
                await set_memory(project_id, "research_raw_data", json.dumps(raw_results), "researcher")
                await set_memory(project_id, "research_sources", json.dumps(sources), "researcher")
                await set_memory(project_id, "research_result_count", str(len(raw_results)), "researcher")
                try:
                    await send_research_data(project_id, raw_results, sources)
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Web search failed, continuing without: {e}")
            extra_context = "\n\n## Web Research\nWeb search unavailable — use your training knowledge instead."

    user_message = f"""Here is the current project context:

{context}{extra_context}

Now produce your deliverable. Respond ONLY with valid JSON. No markdown fences, no explanation outside the JSON."""

    max_tokens = 16000 if role == AgentRole.ENGINEER else 4096
    agent_model = MODEL_MAP.get(role.value, SMART_MODEL)
    fallback = FALLBACK_MAP.get(role.value)
    timeout = AGENT_TIMEOUTS.get(role, 120)

    start_time = time.time()

    raw_text, model_used = await _llm_call_with_retry(
        model=agent_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=max_tokens,
        timeout=timeout,
        stream_callback=stream_callback,
        fallback_model=fallback,
    )

    elapsed = round(time.time() - start_time, 1)
    used_fallback = model_used != agent_model
    if used_fallback:
        logger.warning(f"{ROLE_LABELS[role]} used FALLBACK model {model_used} (primary {agent_model} failed)")
    logger.info(f"{ROLE_LABELS[role]} completed in {elapsed}s using {model_used}")

    await set_memory(project_id, f"introspection_{role.value}", json.dumps({
        "model": model_used,
        "primary_model": agent_model,
        "used_fallback": used_fallback,
        "elapsed_seconds": elapsed,
        "max_tokens": max_tokens,
        "timeout": timeout,
        "context_length": len(user_message),
    }), role.value)

    repaired = _repair_json(raw_text)

    try:
        content = json.loads(repaired)
    except json.JSONDecodeError:
        content = {"raw_response": raw_text, "_parse_error": "Agent did not return valid JSON"}

    output = await save_agent_output(project_id, role.value, content)

    output["_timing"] = {"elapsed_seconds": elapsed, "model": model_used, "used_fallback": used_fallback}

    summary_key = f"{role.value}_summary"
    if isinstance(content, dict):
        summary = content.get("project_name") or content.get("problem_analysis") or content.get("recommended_approach") or content.get("architecture_overview") or "Completed"
        if isinstance(summary, str) and len(summary) > 200:
            summary = summary[:200] + "..."
        await set_memory(project_id, summary_key, str(summary), role.value)

    return output


REVIEW_MATRIX: dict[AgentRole, AgentRole] = {
    AgentRole.BUSINESS_ANALYST: AgentRole.CEO,
    AgentRole.RESEARCHER: AgentRole.BUSINESS_ANALYST,
    AgentRole.ARCHITECT: AgentRole.RESEARCHER,
    AgentRole.ENGINEER: AgentRole.ARCHITECT,
    AgentRole.PPT: AgentRole.ENGINEER,
}


async def cross_review(project_id: str, reviewed_role: AgentRole, output_content: dict) -> dict | None:
    reviewer_role = REVIEW_MATRIX.get(reviewed_role)
    if not reviewer_role:
        return None

    reviewer_label = ROLE_LABELS[reviewer_role]
    reviewed_label = ROLE_LABELS[reviewed_role]

    output_json = json.dumps(output_content, indent=2)
    if len(output_json) > 8000:
        output_json = output_json[:8000] + "\n... (truncated for review)"

    role_criteria = REVIEW_CRITERIA.get(reviewed_role.value, "")

    review_prompt = CROSS_REVIEW_PROMPT.format(
        reviewer_label=reviewer_label,
        reviewed_label=reviewed_label,
        output_json=output_json,
        role_criteria=role_criteria,
    )

    review_model = MODEL_MAP.get("cross_review", SMART_MODEL)
    review_fallback = FALLBACK_MAP.get("cross_review")

    try:
        raw_text, _ = await _llm_call_with_retry(
            model=review_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPTS[reviewer_role]},
                {"role": "user", "content": review_prompt},
            ],
            max_tokens=1024,
            timeout=60,
            fallback_model=review_fallback,
        )
    except Exception as e:
        logger.warning(f"Cross-review failed (non-critical), skipping: {e}")
        return None

    repaired = _repair_json(raw_text)

    try:
        review_data = json.loads(repaired)
    except json.JSONDecodeError:
        review_data = {"overall_assessment": raw_text, "strengths": [], "concerns": [], "suggestions": [], "team_note": ""}

    review_data["reviewer"] = reviewer_role.value
    review_data["reviewer_label"] = reviewer_label
    review_data["reviewed"] = reviewed_role.value

    await set_memory(
        project_id,
        f"peer_review_{reviewed_role.value}",
        json.dumps(review_data),
        reviewer_role.value,
    )

    return review_data


async def call_employee(project_id: str, role: AgentRole, message: str) -> str:
    project = await get_project(project_id)
    if not project:
        raise ValueError(f"Project {project_id} not found")

    outputs = await get_project_outputs(project_id)
    memory = await get_memory(project_id)
    context = _build_context(project, outputs, memory)

    conversation = await get_conversation(project_id, role.value)
    conversation.append({"role": "user", "content": message})

    role_extra = ""
    if role == AgentRole.ENGINEER:
        role_extra = """

ITERATION MODE: The Founder is asking you to modify the existing code.
When they ask for changes:
1. Identify which file(s) need to change
2. Provide the COMPLETE updated file content for each changed file
3. Format each file update as:
   === FILE: path/to/file.ext ===
   <complete file content here>
   === END FILE ===
4. Explain what you changed and why

This is pair programming. Be precise. Give complete files, not snippets."""

    system_prompt = f"""{SYSTEM_PROMPTS[role]}

You are in a direct conversation with the Founder. Answer their questions based on your expertise and the project context below.
Be specific, helpful, and concise. You have full access to the project state.
{role_extra}

{context}"""

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend([{"role": m["role"], "content": m["content"]} for m in conversation])

    chat_model = MODEL_MAP.get(role.value, SMART_MODEL)
    chat_fallback = FALLBACK_MAP.get(role.value)

    raw_text, _ = await _llm_call_with_retry(
        model=chat_model,
        messages=messages,
        max_tokens=4096,
        timeout=AGENT_TIMEOUTS.get(role, 120),
        fallback_model=chat_fallback,
    )

    conversation.append({"role": "assistant", "content": raw_text})
    await save_conversation(project_id, role.value, conversation)

    return raw_text
