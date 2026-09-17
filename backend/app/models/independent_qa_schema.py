"""
Independent QA Schema Models (FIND-01)

Pydantic models for the independent QA verification pipeline.
These models represent structured assertions synthesized from BA/Architect contracts
and executed independently of Engineer-authored tests.

IMPORTANT: IQA artifacts are strictly transient — never persisted to
current_files, final_files, agent_outputs, ZIP, or GitHub exports.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class QAAssertion(BaseModel):
    """Single structured assertion derived from a BA/Architect requirement."""
    requirement_id: str = ""
    requirement_text: str = ""
    method: str = "GET"
    path: str = "/"
    request_body: Optional[Dict[str, Any]] = None
    expected_status: int = 200
    required_response_fields: List[str] = Field(default_factory=list)
    description: str = ""


class QAAssertionResult(BaseModel):
    """Result of executing a single QA assertion."""
    assertion: QAAssertion = Field(default_factory=QAAssertion)
    passed: bool = False
    actual_status: Optional[int] = None
    actual_response: Optional[Dict[str, Any]] = None
    error: str = ""


class IndependentQAResult(BaseModel):
    """Aggregate result of all independent QA assertions."""
    status: str = "UNAVAILABLE"  # PASS, FAIL, UNAVAILABLE, ERROR
    assertions_total: int = 0
    assertions_passed: int = 0
    assertions_failed: int = 0
    results: List[QAAssertionResult] = Field(default_factory=list)
    coverage_ratio: float = 0.0
    reason: str = ""
    requirements_count: int = 0
