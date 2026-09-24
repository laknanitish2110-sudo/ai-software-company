"""
Intelligent memory engine for persistent AI employees.

Handles:
1. Automatic memory extraction — after each conversation turn, extracts
   facts worth remembering without the user saying "remember"
2. Session summarization — compresses long conversations into episodic
   memory when sessions end or get too long
"""

import json
import logging
import asyncio
from typing import Optional

from app.core.database import (
    create_memory, get_session_messages, update_session,
    create_skill, list_skills, retrieve_skills_for_context, record_skill_usage,
)

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Analyze this conversation between a user and an AI employee. Extract any facts worth remembering for future conversations.

Focus on:
- Decisions made (technical choices, preferences, direction)
- User preferences (style, tools, workflows they like)
- Project context (goals, constraints, deadlines, stakeholders)
- Technical facts (stack, architecture, APIs, credentials references)
- Corrections (things the user corrected or clarified)

Return a JSON array of memories to save. Each memory should have:
- "content": the fact to remember (1-2 sentences, self-contained)
- "type": one of "semantic" (facts/knowledge), "preference" (user preferences), "episodic" (what happened), "procedural" (how to do things)
- "importance": 0.0 to 1.0 (1.0 = critical decision, 0.3 = minor detail)
- "tags": array of 1-3 short keyword tags

If nothing is worth remembering, return an empty array: []

Only extract genuinely useful facts. Do NOT extract:
- Generic greetings or small talk
- Things the AI said (only user-originated info)
- Obvious facts that don't need remembering
- Anything already covered by the system prompt

Conversation:
USER: {user_message}
EMPLOYEE: {employee_response}

Return ONLY the JSON array, no other text."""

SUMMARY_PROMPT = """Summarize this conversation between a user and an AI employee named {employee_name} ({employee_role}).

Create a concise summary that captures:
1. What was discussed (main topics)
2. What was decided or accomplished
3. What's still open or pending
4. Any important context for future conversations

Keep it under 200 words. Write in past tense, third person.

Conversation:
{conversation}

Summary:"""


async def extract_memories_from_turn(
    employee_id: str,
    user_message: str,
    employee_response: str,
    session_id: str,
) -> list[dict]:
    """Extract memorable facts from a single conversation turn. Runs as background task."""
    if len(user_message) < 15 and len(employee_response) < 50:
        return []

    try:
        from app.agents.engine import call_llm_with_fallback

        prompt = EXTRACTION_PROMPT.format(
            user_message=user_message[:2000],
            employee_response=employee_response[:2000],
        )

        result = await call_llm_with_fallback(
            messages=[{"role": "user", "content": prompt}],
            role="fixer",
            temperature=0.1,
            max_tokens=1024,
        )
        text = result if isinstance(result, str) else result[0]

        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        memories = json.loads(text)
        if not isinstance(memories, list):
            return []

        created = []
        for mem in memories:
            if not isinstance(mem, dict) or not mem.get("content"):
                continue
            importance = min(max(float(mem.get("importance", 0.5)), 0.1), 1.0)
            if importance < 0.3:
                continue
            saved = await create_memory(
                employee_id=employee_id,
                mem_type=mem.get("type", "semantic"),
                content=mem["content"],
                source="auto_extraction",
                source_id=session_id,
                confidence=0.7,
                importance=importance,
                tags=mem.get("tags"),
            )
            created.append(saved)

        if created:
            logger.info(f"Auto-extracted {len(created)} memories for employee {employee_id}")
        return created

    except json.JSONDecodeError:
        logger.debug(f"Memory extraction returned non-JSON for employee {employee_id}")
        return []
    except Exception as e:
        logger.warning(f"Memory extraction failed for employee {employee_id}: {e}")
        return []


async def summarize_session(
    session_id: str,
    employee_id: str,
    employee_name: str,
    employee_role: str,
) -> Optional[str]:
    """Summarize a session's conversation and store as episodic memory."""
    try:
        messages = await get_session_messages(session_id, limit=100)
        if not messages:
            return None

        conversation_parts = []
        for msg in messages:
            if msg["role"] == "user":
                conversation_parts.append(f"USER: {msg['content']}")
            elif msg["role"] == "employee":
                conversation_parts.append(f"{employee_name.upper()}: {msg['content']}")

        if len(conversation_parts) < 2:
            return None

        conversation_text = "\n".join(conversation_parts)
        if len(conversation_text) > 6000:
            conversation_text = conversation_text[:6000] + "\n...(truncated)"

        from app.agents.engine import call_llm_with_fallback

        prompt = SUMMARY_PROMPT.format(
            employee_name=employee_name,
            employee_role=employee_role,
            conversation=conversation_text,
        )

        result = await call_llm_with_fallback(
            messages=[{"role": "user", "content": prompt}],
            role="fixer",
            temperature=0.2,
            max_tokens=512,
        )
        summary = result if isinstance(result, str) else result[0]
        summary = summary.strip()

        if not summary:
            return None

        await update_session(session_id, {"summary": summary})

        await create_memory(
            employee_id=employee_id,
            mem_type="episodic",
            content=f"Session summary: {summary}",
            source="session_summary",
            source_id=session_id,
            confidence=0.9,
            importance=0.6,
            tags=["session", "summary"],
        )

        logger.info(f"Summarized session {session_id} for employee {employee_id}")
        return summary

    except Exception as e:
        logger.warning(f"Session summarization failed for {session_id}: {e}")
        return None


def schedule_memory_extraction(
    employee_id: str,
    user_message: str,
    employee_response: str,
    session_id: str,
):
    """Fire-and-forget: schedule memory extraction as a background task."""
    asyncio.create_task(
        extract_memories_from_turn(employee_id, user_message, employee_response, session_id)
    )


def schedule_skill_extraction(employee_id: str, messages: list[dict]):
    """Fire-and-forget: schedule skill extraction as a background task."""
    if len(messages) >= 6:
        asyncio.create_task(extract_skills_from_conversation(employee_id, messages))


def schedule_session_summary(
    session_id: str,
    employee_id: str,
    employee_name: str,
    employee_role: str,
):
    """Fire-and-forget: schedule session summarization as a background task."""
    asyncio.create_task(
        summarize_session(session_id, employee_id, employee_name, employee_role)
    )


# ---------------------------------------------------------------------------
# Memory consolidation: dedup, conflict resolution, freshness decay
# ---------------------------------------------------------------------------

CONSOLIDATION_PROMPT = """You are a memory consolidation system. Given a group of similar memories belonging to one AI employee, decide how to consolidate them.

For each group, choose one action:
- "merge": combine into a single better memory (provide merged content)
- "keep_newest": the newest memory supersedes older ones
- "keep_highest": the highest-confidence memory is correct, deactivate others
- "conflict": they contradict each other — keep the most recent one, note the conflict

Return a JSON array of actions. Each action:
{
  "action": "merge" | "keep_newest" | "keep_highest" | "conflict",
  "keep_id": "id of the memory to keep (or best candidate for merge base)",
  "deactivate_ids": ["ids to deactivate"],
  "merged_content": "new merged text (only for merge action)",
  "reason": "short explanation"
}

Memories to consolidate:
{memory_groups}

Return ONLY the JSON array."""


async def apply_freshness_decay(employee_id: str) -> int:
    """Decay confidence of old, unaccessed memories. Returns count of decayed memories."""
    from app.core.database import get_db, now_iso
    from datetime import datetime, timezone, timedelta

    db = await get_db()
    try:
        now = datetime.now(timezone.utc)
        decay_threshold = (now - timedelta(days=14)).isoformat()

        cursor = await db.execute(
            """SELECT id, confidence, last_accessed, created_at, importance
               FROM memories
               WHERE employee_id = ? AND is_active = 1
               AND (last_accessed < ? OR (last_accessed IS NULL AND created_at < ?))""",
            (employee_id, decay_threshold, decay_threshold),
        )
        rows = await cursor.fetchall()

        decayed = 0
        now_str = now_iso()
        for r in rows:
            last = r.get("last_accessed") or r["created_at"]
            try:
                last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue

            days_stale = (now - last_dt).days
            if days_stale < 14:
                continue

            decay_factor = max(0.95 ** (days_stale // 7), 0.3)
            new_confidence = round(r["confidence"] * decay_factor, 3)

            if new_confidence < 0.2 and r["importance"] < 0.5:
                await db.execute(
                    "UPDATE memories SET is_active = 0, confidence = ? WHERE id = ?",
                    (new_confidence, r["id"]),
                )
            elif new_confidence != r["confidence"]:
                await db.execute(
                    "UPDATE memories SET confidence = ? WHERE id = ?",
                    (new_confidence, r["id"]),
                )
            decayed += 1

        if decayed:
            await db.commit()
        logger.info(f"Freshness decay: {decayed} memories processed for employee {employee_id}")
        return decayed
    finally:
        await db.close()


def _text_similarity(a: str, b: str) -> float:
    """Quick word-overlap similarity (Jaccard) for grouping candidates."""
    wa = set(a.lower().split())
    wb = set(b.lower().split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


async def find_duplicate_groups(employee_id: str, threshold: float = 0.45) -> list[list[dict]]:
    """Find groups of memories that are likely duplicates based on text similarity."""
    from app.core.database import list_memories

    all_memories = await list_memories(employee_id, limit=200)
    if len(all_memories) < 2:
        return []

    used = set()
    groups = []
    for i, a in enumerate(all_memories):
        if a["id"] in used:
            continue
        group = [a]
        for j in range(i + 1, len(all_memories)):
            b = all_memories[j]
            if b["id"] in used:
                continue
            if a["type"] != b["type"]:
                continue
            sim = _text_similarity(a["content"], b["content"])
            if sim >= threshold:
                group.append(b)
                used.add(b["id"])
        if len(group) > 1:
            groups.append(group)
            used.add(a["id"])

    return groups


async def consolidate_memories(employee_id: str) -> dict:
    """Run full memory consolidation: dedup, conflict resolution, freshness decay."""
    from app.core.database import update_memory, deactivate_memory

    result = {"decayed": 0, "merged": 0, "deactivated": 0, "groups_processed": 0}

    result["decayed"] = await apply_freshness_decay(employee_id)

    groups = await find_duplicate_groups(employee_id)
    if not groups:
        logger.info(f"Consolidation for {employee_id}: no duplicate groups found")
        return result

    memory_groups_text = ""
    for i, group in enumerate(groups[:5]):
        memory_groups_text += f"\nGroup {i+1}:\n"
        for m in group:
            memory_groups_text += (
                f"  - id={m['id']}, type={m['type']}, confidence={m.get('confidence', 0.8)}, "
                f"importance={m.get('importance', 0.5)}, created={m.get('created_at', '?')}\n"
                f"    content: {m['content']}\n"
            )

    try:
        from app.agents.engine import call_llm_with_fallback

        prompt = CONSOLIDATION_PROMPT.format(memory_groups=memory_groups_text)
        llm_result = await call_llm_with_fallback(
            messages=[{"role": "user", "content": prompt}],
            role="fixer",
            temperature=0.1,
            max_tokens=1024,
        )
        text = llm_result if isinstance(llm_result, str) else llm_result[0]
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        actions = json.loads(text)
        if not isinstance(actions, list):
            actions = []

        for action in actions:
            act_type = action.get("action")
            keep_id = action.get("keep_id")
            deact_ids = action.get("deactivate_ids", [])

            for did in deact_ids:
                if did != keep_id:
                    await deactivate_memory(did)
                    result["deactivated"] += 1

            if act_type == "merge" and keep_id and action.get("merged_content"):
                await update_memory(keep_id, {
                    "content": action["merged_content"],
                    "confidence": min(1.0, 0.85),
                })
                result["merged"] += 1

            elif act_type == "conflict" and keep_id:
                await update_memory(keep_id, {"confidence": 0.9})
                result["merged"] += 1

            result["groups_processed"] += 1

    except json.JSONDecodeError:
        logger.debug(f"Consolidation LLM returned non-JSON for {employee_id}")
    except Exception as e:
        logger.warning(f"Consolidation LLM failed for {employee_id}: {e}")

    logger.info(
        f"Consolidation for {employee_id}: "
        f"{result['groups_processed']} groups, {result['merged']} merged, "
        f"{result['deactivated']} deactivated, {result['decayed']} decayed"
    )
    return result


_consolidation_task: Optional[asyncio.Task] = None


async def _consolidation_loop():
    """Background loop that periodically consolidates memories for all employees."""
    logger.info("Memory consolidation worker started")
    while True:
        try:
            from app.core.database import get_db
            db = await get_db()
            try:
                cursor = await db.execute("SELECT DISTINCT id FROM employees WHERE status != 'archived'")
                emp_rows = await cursor.fetchall()
            finally:
                await db.close()

            for row in emp_rows:
                try:
                    await consolidate_memories(row["id"])
                except Exception as e:
                    logger.warning(f"Consolidation failed for {row['id']}: {e}")
                await asyncio.sleep(1)

        except Exception as e:
            logger.warning(f"Consolidation loop error: {e}")

        await asyncio.sleep(3600)


def start_consolidation_worker():
    """Start the background memory consolidation worker. Runs every hour."""
    global _consolidation_task
    if _consolidation_task and not _consolidation_task.done():
        return
    _consolidation_task = asyncio.create_task(_consolidation_loop())
    logger.info("Memory consolidation worker task created")


def stop_consolidation_worker():
    """Stop the background memory consolidation worker."""
    global _consolidation_task
    if _consolidation_task and not _consolidation_task.done():
        _consolidation_task.cancel()
        _consolidation_task = None


# --- Skill Learning ---

SKILL_EXTRACTION_PROMPT = """Analyze this conversation between a user and an AI employee. Identify any repeatable procedures the employee executed successfully that should be saved as a learned skill.

A skill is worth saving when:
- The employee performed a multi-step procedure that produced a good result
- The user confirmed or accepted the result (no corrections needed)
- The procedure could be reused for similar future requests

For each skill found, return a JSON object with:
- "name": short name for the skill (2-5 words)
- "description": one-line summary of what it does
- "trigger_pattern": what kind of user request would trigger this skill (a regex-like description)
- "procedure": step-by-step instructions the employee followed
- "examples": array of 1-2 example user prompts that would trigger this

If no skill is worth saving, return an empty array: []

Only extract clear, repeatable procedures. Do NOT extract:
- General knowledge or facts (those belong in memory)
- One-off creative responses
- Simple Q&A answers

Conversation:
{conversation}

Return ONLY a JSON array, no other text."""


async def extract_skills_from_conversation(
    employee_id: str,
    messages: list[dict],
    llm_caller=None,
) -> list[dict]:
    if not messages or len(messages) < 4:
        return []

    conversation_text = "\n".join(
        f"{m.get('role', 'unknown').upper()}: {m.get('content', '')}"
        for m in messages[-20:]
    )

    prompt = SKILL_EXTRACTION_PROMPT.format(conversation=conversation_text)

    if llm_caller is None:
        from app.services.llm_engine import call_llm_with_fallback
        llm_caller = call_llm_with_fallback

    try:
        response = await llm_caller(
            messages=[{"role": "user", "content": prompt}],
            role="researcher",
        )

        raw = response.get("content", "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        skills_data = json.loads(raw)
        if not isinstance(skills_data, list):
            return []

        existing = await list_skills(employee_id, active_only=True)
        existing_names = {s["name"].lower() for s in existing}

        saved = []
        for s in skills_data:
            name = s.get("name", "").strip()
            if not name or name.lower() in existing_names:
                continue
            skill = await create_skill(
                employee_id=employee_id,
                name=name,
                description=s.get("description", ""),
                procedure=s.get("procedure", ""),
                trigger_pattern=s.get("trigger_pattern"),
                examples=s.get("examples"),
            )
            saved.append(skill)
            existing_names.add(name.lower())

        if saved:
            logger.info(f"Extracted {len(saved)} skills for employee {employee_id}")
        return saved

    except Exception as e:
        logger.warning(f"Skill extraction failed for {employee_id}: {e}")
        return []


async def get_relevant_skills(employee_id: str, user_message: str) -> str:
    skills = await retrieve_skills_for_context(employee_id, query=user_message, limit=3)
    if not skills:
        return ""

    lines = ["\n## Learned Skills (use these procedures when relevant)"]
    for s in skills:
        lines.append(f"\n### {s['name']}")
        lines.append(f"Trigger: {s.get('trigger_pattern', 'N/A')}")
        lines.append(f"Procedure: {s['procedure']}")
        if s.get("examples"):
            examples = s["examples"] if isinstance(s["examples"], list) else [s["examples"]]
            lines.append(f"Examples: {', '.join(examples)}")
    return "\n".join(lines)
