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

from app.core.database import create_memory, get_session_messages, update_session

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
