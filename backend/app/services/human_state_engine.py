"""
Human-State Engine for AI-Co agents.

Maintains a continuous model of human interaction state across dimensions
(frustration, confusion, engagement, urgency, arousal, valence, confidence),
tracks trajectories, generates interaction policies, and measures outcomes.

Architecture:
  Signals → State Estimation → Trajectory → Policy Engine → Agent Adaptation → Outcome

This is the orchestration/intelligence layer — perception models are pluggable upstream.
"""

import time
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger(__name__)

DIMENSIONS = ["frustration", "confusion", "engagement", "urgency", "arousal", "valence", "confidence"]

SMOOTHING_ALPHA = 0.3
TRAJECTORY_WINDOW = 3
TRAJECTORY_THRESHOLD = 0.08


@dataclass
class HumanState:
    frustration: float = 0.0
    confusion: float = 0.0
    engagement: float = 0.5
    urgency: float = 0.0
    arousal: float = 0.3
    valence: float = 0.0
    confidence: float = 0.5
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {d: getattr(self, d) for d in DIMENSIONS}

    @classmethod
    def from_dict(cls, data: dict) -> "HumanState":
        return cls(**{k: data.get(k, 0.0) for k in DIMENSIONS},
                   timestamp=data.get("timestamp", time.time()))


@dataclass
class Trajectory:
    frustration: str = "stable"
    confusion: str = "stable"
    engagement: str = "stable"
    urgency: str = "stable"
    arousal: str = "stable"
    valence: str = "stable"
    confidence: str = "stable"

    def to_dict(self) -> dict:
        return {d: getattr(self, d) for d in DIMENSIONS}


@dataclass
class InteractionPolicy:
    verbosity: str = "medium"
    tone: str = "neutral"
    question_count: int = 1
    explanation_mode: str = "detailed"
    pacing: str = "normal"
    alert_level: str = "none"

    def to_dict(self) -> dict:
        return asdict(self)


class HumanStateEngine:
    """
    Maintains per-session human interaction state, computes trajectories,
    and generates agent adaptation policies.
    """

    def __init__(self):
        self._sessions: dict[str, list[HumanState]] = {}

    def _get_history(self, session_id: str) -> list[HumanState]:
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        return self._sessions[session_id]

    def update_state(self, session_id: str, signals: dict) -> dict:
        """
        Accept raw signals, smooth them against prior state, compute
        trajectory and policy. Returns the full analysis result.
        """
        history = self._get_history(session_id)
        raw = HumanState(**{d: _clamp(signals.get(d, 0.0), d) for d in DIMENSIONS})

        if history:
            prev = history[-1]
            smoothed = HumanState(**{
                d: _ema(getattr(prev, d), getattr(raw, d)) for d in DIMENSIONS
            })
        else:
            smoothed = raw

        history.append(smoothed)
        if len(history) > 50:
            history[:] = history[-50:]

        trajectory = self._compute_trajectory(history)
        policy = self._compute_policy(smoothed, trajectory)
        overall_risk = self._compute_risk(smoothed, trajectory)

        return {
            "state": smoothed.to_dict(),
            "trajectory": trajectory.to_dict(),
            "policy": policy.to_dict(),
            "risk_score": round(overall_risk, 3),
            "snapshot_index": len(history) - 1,
        }

    def get_current_state(self, session_id: str) -> Optional[dict]:
        history = self._get_history(session_id)
        if not history:
            return None
        latest = history[-1]
        trajectory = self._compute_trajectory(history)
        return {"state": latest.to_dict(), "trajectory": trajectory.to_dict()}

    def measure_outcome(self, session_id: str, before_index: int) -> Optional[dict]:
        """
        Compare state at before_index to current state. Returns deltas
        and a qualitative outcome label.
        """
        history = self._get_history(session_id)
        if before_index < 0 or before_index >= len(history) or len(history) < 2:
            return None

        before = history[before_index]
        after = history[-1]

        deltas = {}
        for d in DIMENSIONS:
            deltas[d] = round(getattr(after, d) - getattr(before, d), 4)

        positive_signals = (
            deltas.get("frustration", 0) < -0.05
            or deltas.get("confusion", 0) < -0.05
            or deltas.get("engagement", 0) > 0.05
            or deltas.get("confidence", 0) > 0.05
        )
        negative_signals = (
            deltas.get("frustration", 0) > 0.1
            or deltas.get("engagement", 0) < -0.1
        )

        if positive_signals and not negative_signals:
            outcome = "positive_transition"
        elif negative_signals and not positive_signals:
            outcome = "negative_transition"
        elif positive_signals and negative_signals:
            outcome = "mixed_transition"
        else:
            outcome = "neutral"

        return {
            "before": before.to_dict(),
            "after": after.to_dict(),
            "deltas": deltas,
            "outcome": outcome,
            "turns_elapsed": len(history) - 1 - before_index,
        }

    def clear_session(self, session_id: str):
        self._sessions.pop(session_id, None)

    def _compute_trajectory(self, history: list[HumanState]) -> Trajectory:
        window = history[-TRAJECTORY_WINDOW:] if len(history) >= TRAJECTORY_WINDOW else history
        if len(window) < 2:
            return Trajectory()

        trends = {}
        for d in DIMENSIONS:
            first = getattr(window[0], d)
            last = getattr(window[-1], d)
            diff = last - first
            if diff > TRAJECTORY_THRESHOLD:
                trends[d] = "rising"
            elif diff < -TRAJECTORY_THRESHOLD:
                trends[d] = "falling"
            else:
                trends[d] = "stable"
        return Trajectory(**trends)

    def _compute_policy(self, state: HumanState, trajectory: Trajectory) -> InteractionPolicy:
        policy = InteractionPolicy()

        if state.frustration > 0.7 or trajectory.frustration == "rising":
            policy.tone = "calm"
            policy.verbosity = "low"
            policy.pacing = "slow"

        if state.confusion > 0.6:
            policy.explanation_mode = "diagnostic"
            policy.question_count = 1

        if state.engagement < 0.3 and trajectory.engagement == "falling":
            policy.verbosity = "low"
            policy.tone = "energetic"

        if state.urgency > 0.7:
            policy.verbosity = "low"
            policy.explanation_mode = "summary"
            policy.pacing = "normal"

        if state.frustration > 0.8 and state.confusion > 0.6:
            policy.alert_level = "high"
            policy.question_count = 1
            policy.explanation_mode = "diagnostic"
            policy.verbosity = "low"
            policy.tone = "calm"
            policy.pacing = "slow"

        if state.engagement > 0.7 and state.frustration < 0.3:
            policy.verbosity = "medium"
            policy.explanation_mode = "detailed"
            policy.tone = "neutral"

        return policy

    def _compute_risk(self, state: HumanState, trajectory: Trajectory) -> float:
        risk = 0.0
        risk += state.frustration * 0.35
        risk += (1.0 - state.engagement) * 0.25
        risk += state.confusion * 0.20
        risk += state.urgency * 0.10
        risk += (1.0 - max(0, state.valence + 1) / 2) * 0.10

        if trajectory.frustration == "rising":
            risk += 0.1
        if trajectory.engagement == "falling":
            risk += 0.08
        return min(risk, 1.0)


def _clamp(value: float, dimension: str) -> float:
    if dimension == "valence":
        return max(-1.0, min(1.0, value))
    return max(0.0, min(1.0, value))


def _ema(prev: float, curr: float) -> float:
    return round(SMOOTHING_ALPHA * curr + (1 - SMOOTHING_ALPHA) * prev, 4)


# Singleton
human_state_engine = HumanStateEngine()


async def analyze_text_signals(text: str, context: dict = None) -> dict:
    """
    Estimate human state dimensions from text content.
    This is the built-in text-based perception layer.
    External providers (Hume, audio models) can supplement or replace this.
    """
    text_lower = text.lower()
    signals = {
        "frustration": 0.0,
        "confusion": 0.0,
        "engagement": 0.5,
        "urgency": 0.0,
        "arousal": 0.3,
        "valence": 0.0,
        "confidence": 0.5,
    }

    frustration_markers = [
        "not working", "broken", "doesn't work", "still broken", "again",
        "tried everything", "keeps failing", "waste of time", "useless",
        "already tried", "nothing works", "so frustrated", "fed up",
        "why can't", "come on", "seriously", "ridiculous",
    ]
    confusion_markers = [
        "don't understand", "confused", "what do you mean", "makes no sense",
        "unclear", "lost", "huh", "wait what", "i'm not sure",
        "can you explain", "doesn't make sense", "what?",
    ]
    urgency_markers = [
        "asap", "urgent", "deadline", "right now", "immediately",
        "critical", "emergency", "hurry", "quickly", "time sensitive",
    ]
    positive_markers = [
        "thanks", "great", "perfect", "awesome", "works", "got it",
        "makes sense", "helpful", "excellent", "nice", "love it",
    ]
    disengagement_markers = [
        "nevermind", "forget it", "whatever", "fine", "ok whatever",
        "i'll figure it out", "don't bother",
    ]

    for marker in frustration_markers:
        if marker in text_lower:
            signals["frustration"] = min(signals["frustration"] + 0.25, 1.0)
            signals["arousal"] = min(signals["arousal"] + 0.15, 1.0)
            signals["valence"] = max(signals["valence"] - 0.2, -1.0)

    for marker in confusion_markers:
        if marker in text_lower:
            signals["confusion"] = min(signals["confusion"] + 0.3, 1.0)
            signals["confidence"] = max(signals["confidence"] - 0.15, 0.0)

    for marker in urgency_markers:
        if marker in text_lower:
            signals["urgency"] = min(signals["urgency"] + 0.3, 1.0)
            signals["arousal"] = min(signals["arousal"] + 0.1, 1.0)

    for marker in positive_markers:
        if marker in text_lower:
            signals["valence"] = min(signals["valence"] + 0.25, 1.0)
            signals["engagement"] = min(signals["engagement"] + 0.1, 1.0)
            signals["frustration"] = max(signals["frustration"] - 0.1, 0.0)

    for marker in disengagement_markers:
        if marker in text_lower:
            signals["engagement"] = max(signals["engagement"] - 0.3, 0.0)
            signals["frustration"] = min(signals["frustration"] + 0.15, 1.0)

    if text.isupper() and len(text) > 5:
        signals["frustration"] = min(signals["frustration"] + 0.2, 1.0)
        signals["arousal"] = min(signals["arousal"] + 0.2, 1.0)

    exclamation_count = text.count("!")
    question_count = text.count("?")
    if exclamation_count > 2:
        signals["arousal"] = min(signals["arousal"] + 0.15, 1.0)
    if question_count > 2:
        signals["confusion"] = min(signals["confusion"] + 0.1, 1.0)

    word_count = len(text.split())
    if word_count < 5:
        signals["engagement"] = max(signals["engagement"] - 0.1, 0.0)
    elif word_count > 50:
        signals["engagement"] = min(signals["engagement"] + 0.15, 1.0)

    return signals
