"""
Confidence thresholds for automated decisions.

Below threshold → fall back to existing logic or escalate to LLM.
These should be tuned empirically against real execution data.
"""

ROUTING_CONFIDENCE = 0.75
QA_CONFIDENCE = 0.85
REPAIR_CONFIDENCE = 0.80
DIFFICULTY_CONFIDENCE = 0.70
EMPLOYEE_ROUTING_CONFIDENCE = 0.75
HUMAN_REVIEW_CONFIDENCE = 0.80
