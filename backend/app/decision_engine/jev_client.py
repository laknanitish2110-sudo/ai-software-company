"""
Jev/Jeff decision model client.

Supports two backends:
1. Jev API (TypeSafe managed API) — set JEV_API_KEY
2. Jeff local (open-weight Qwen3-4B LoRA) — set JEFF_ENDPOINT

Falls back to a rule-based engine when neither is configured,
so the decision layer works without external dependencies.
"""

import os
import json
import logging
import time
from typing import Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

JEV_API_KEY = os.getenv("JEV_API_KEY", "")
JEV_API_URL = os.getenv("JEV_API_URL", "https://api.typesafe.ai/v1/decide")
JEFF_ENDPOINT = os.getenv("JEFF_ENDPOINT", "")


@dataclass
class DecisionResult:
    choice: str
    probabilities: dict[str, float]
    confidence: float
    latency_ms: float
    backend: str

    def above_threshold(self, threshold: float) -> bool:
        return self.confidence >= threshold


async def _call_jev_api(state: str, question: dict) -> DecisionResult:
    """Call the TypeSafe Jev managed API."""
    import httpx
    start = time.monotonic()
    payload = {"state": state, "questions": [question]}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            JEV_API_URL,
            json=payload,
            headers={"Authorization": f"Bearer {JEV_API_KEY}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
    latency = (time.monotonic() - start) * 1000

    answer = data.get("answers", [{}])[0]
    return DecisionResult(
        choice=answer.get("choice", ""),
        probabilities=answer.get("probabilities", {}),
        confidence=answer.get("confidence", 0.0),
        latency_ms=latency,
        backend="jev",
    )


async def _call_jeff_endpoint(state: str, question: dict) -> DecisionResult:
    """Call a self-hosted Jeff model endpoint (OpenAI-compatible)."""
    import httpx
    start = time.monotonic()

    options = question.get("criteria", {})
    option_text = "\n".join(f"- {k}: {v}" for k, v in options.items())
    prompt = f"""STATE:\n{state}\n\nQUESTION:\n{question.get('instructions', '')}\n\nOPTIONS:\n{option_text}\n\nRespond with ONLY the chosen option name."""

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            JEFF_ENDPOINT,
            json={
                "model": os.getenv("JEFF_MODEL", "jeff-1"),
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 50,
                "temperature": 0.1,
            },
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
    latency = (time.monotonic() - start) * 1000

    raw = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip().lower()
    matched = None
    for key in options:
        if key.lower() in raw:
            matched = key
            break
    if not matched:
        matched = list(options.keys())[0] if options else raw

    return DecisionResult(
        choice=matched,
        probabilities={matched: 0.8},
        confidence=0.7,
        latency_ms=latency,
        backend="jeff",
    )


def _rule_based_fallback(state: str, question: dict) -> DecisionResult:
    """Deterministic fallback when no Jev/Jeff backend is configured."""
    start = time.monotonic()
    options = question.get("criteria", {})
    default = question.get("default", "")

    if not default and options:
        default = list(options.keys())[0]

    probs = {k: (0.8 if k == default else 0.2 / max(len(options) - 1, 1)) for k in options}
    latency = (time.monotonic() - start) * 1000

    return DecisionResult(
        choice=default,
        probabilities=probs,
        confidence=0.5,
        latency_ms=latency,
        backend="rules",
    )


async def decide(state: str, question: dict) -> DecisionResult:
    """
    Make a structured decision. Tries Jev API first, then Jeff endpoint,
    then falls back to rule-based logic.
    """
    if JEV_API_KEY:
        try:
            return await _call_jev_api(state, question)
        except Exception as e:
            logger.warning(f"Jev API failed, falling back: {e}")

    if JEFF_ENDPOINT:
        try:
            return await _call_jeff_endpoint(state, question)
        except Exception as e:
            logger.warning(f"Jeff endpoint failed, falling back: {e}")

    return _rule_based_fallback(state, question)


async def decide_multi(state: str, questions: dict[str, dict]) -> dict[str, DecisionResult]:
    """Make multiple decisions against the same state."""
    results = {}
    for name, question in questions.items():
        results[name] = await decide(state, question)
    return results
