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
                "logprobs": True,
                "top_logprobs": 5,
            },
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
    latency = (time.monotonic() - start) * 1000

    choice_data = data.get("choices", [{}])[0]
    raw = choice_data.get("message", {}).get("content", "").strip().lower()

    # Match response to known options with quality scoring
    matched = None
    match_quality = "none"
    for key in options:
        if raw == key.lower():
            matched = key
            match_quality = "exact"
            break
        if key.lower() in raw and len(raw) < len(key) * 3:
            matched = key
            match_quality = "substring"

    if not matched:
        matched = list(options.keys())[0] if options else raw
        match_quality = "fallback"

    # Compute confidence from logprobs if available, else from match quality
    confidence = _jeff_confidence(choice_data, match_quality)

    # Build probability distribution from logprobs or match quality
    probs = {}
    if match_quality == "exact":
        probs = {k: (0.05 / max(len(options) - 1, 1)) for k in options}
        probs[matched] = confidence
    elif match_quality == "substring":
        probs = {k: (0.1 / max(len(options) - 1, 1)) for k in options}
        probs[matched] = confidence
    else:
        probs = {k: (1.0 / max(len(options), 1)) for k in options}

    return DecisionResult(
        choice=matched,
        probabilities=probs,
        confidence=confidence,
        latency_ms=latency,
        backend="jeff",
    )


def _jeff_confidence(choice_data: dict, match_quality: str) -> float:
    """Derive confidence from logprobs when available, else from match quality."""
    import math
    logprobs_data = choice_data.get("logprobs")
    if logprobs_data and logprobs_data.get("content"):
        token_logprobs = [t.get("logprob", -1.0) for t in logprobs_data["content"] if "logprob" in t]
        if token_logprobs:
            avg_logprob = sum(token_logprobs) / len(token_logprobs)
            raw_conf = math.exp(avg_logprob)
            return round(min(max(raw_conf, 0.1), 0.99), 3)

    quality_scores = {"exact": 0.88, "substring": 0.78, "fallback": 0.45, "none": 0.3}
    return quality_scores.get(match_quality, 0.5)


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
    """Make multiple decisions against the same state in parallel."""
    import asyncio
    names = list(questions.keys())
    coros = [decide(state, questions[n]) for n in names]
    results_list = await asyncio.gather(*coros, return_exceptions=True)
    results = {}
    for name, result in zip(names, results_list):
        if isinstance(result, Exception):
            logger.warning(f"decide_multi failed for '{name}': {result}")
            results[name] = _rule_based_fallback(state, questions[name])
        else:
            results[name] = result
    return results
