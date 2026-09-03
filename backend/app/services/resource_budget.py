"""
Project Resource Budget Manager (P4.4)

Tracks and enforces per-project execution limits (LLM calls, E2B microVM executions, repair attempts).
Fails closed with ResourceBudgetExceededError before invoking expensive external operations.
Uses Redis for durable, cross-restart budget tracking; falls back to in-memory for dev.
"""

import logging
from typing import Dict, Any, Optional

from app.core.config import (
    MAX_LLM_CALLS_PER_PROJECT,
    MAX_E2B_EXECUTIONS_PER_PROJECT,
    MAX_REPAIR_ATTEMPTS_HARD_LIMIT
)

logger = logging.getLogger(__name__)


class ResourceBudgetExceededError(Exception):
    """Raised when a project exceeds its assigned resource budget limits."""
    pass


from app.services.redis_coordinator import redis_coordinator


class ResourceBudgetManager:
    """
    Manager for tracking per-project resource budgets via Redis coordination.
    Falls back to in-memory counters when Redis is unavailable (dev mode).
    """

    async def check_llm_budget(self, project_id: str, max_limit: Optional[int] = None):
        limit = max_limit if max_limit is not None else MAX_LLM_CALLS_PER_PROJECT
        allowed, current = await redis_coordinator.consume_budget(project_id, "llm_calls", limit, amount=0)
        if not allowed:
            raise ResourceBudgetExceededError(
                f"RESOURCE_BUDGET_EXCEEDED: Project {project_id} reached max LLM calls limit ({current}/{limit})."
            )

    async def record_llm_call(self, project_id: str):
        await redis_coordinator.consume_budget(project_id, "llm_calls", MAX_LLM_CALLS_PER_PROJECT, amount=1)

    async def check_e2b_budget(self, project_id: str, max_limit: Optional[int] = None):
        limit = max_limit if max_limit is not None else MAX_E2B_EXECUTIONS_PER_PROJECT
        allowed, current = await redis_coordinator.consume_budget(project_id, "e2b_executions", limit, amount=0)
        if not allowed:
            raise ResourceBudgetExceededError(
                f"RESOURCE_BUDGET_EXCEEDED: Project {project_id} reached max E2B executions limit ({current}/{limit})."
            )

    async def record_e2b_execution(self, project_id: str):
        await redis_coordinator.consume_budget(project_id, "e2b_executions", MAX_E2B_EXECUTIONS_PER_PROJECT, amount=1)

    async def check_repair_budget(self, project_id: str, max_limit: Optional[int] = None):
        limit = max_limit if max_limit is not None else MAX_REPAIR_ATTEMPTS_HARD_LIMIT
        allowed, current = await redis_coordinator.consume_budget(project_id, "repair_attempts", limit, amount=0)
        if not allowed:
            raise ResourceBudgetExceededError(
                f"RESOURCE_BUDGET_EXCEEDED: Project {project_id} reached max repair attempts ceiling ({current}/{limit})."
            )

    async def record_repair_attempt(self, project_id: str):
        await redis_coordinator.consume_budget(project_id, "repair_attempts", MAX_REPAIR_ATTEMPTS_HARD_LIMIT, amount=1)

    async def get_budget_status(self, project_id: str) -> Dict[str, Any]:
        llm = 0
        e2b = 0
        repair = 0
        try:
            _, llm = await redis_coordinator.consume_budget(project_id, "llm_calls", MAX_LLM_CALLS_PER_PROJECT, amount=0)
            _, e2b = await redis_coordinator.consume_budget(project_id, "e2b_executions", MAX_E2B_EXECUTIONS_PER_PROJECT, amount=0)
            _, repair = await redis_coordinator.consume_budget(project_id, "repair_attempts", MAX_REPAIR_ATTEMPTS_HARD_LIMIT, amount=0)
        except Exception:
            pass

        status = "OK"
        if (
            llm >= MAX_LLM_CALLS_PER_PROJECT
            or e2b >= MAX_E2B_EXECUTIONS_PER_PROJECT
            or repair >= MAX_REPAIR_ATTEMPTS_HARD_LIMIT
        ):
            status = "RESOURCE_BUDGET_EXCEEDED"

        return {
            "project_id": project_id,
            "llm_calls": llm,
            "e2b_executions": e2b,
            "repair_attempts": repair,
            "max_llm_calls": MAX_LLM_CALLS_PER_PROJECT,
            "max_e2b_executions": MAX_E2B_EXECUTIONS_PER_PROJECT,
            "max_repair_attempts": MAX_REPAIR_ATTEMPTS_HARD_LIMIT,
            "budget_status": status,
        }

    def reset_project(self, project_id: str):
        redis_coordinator.reset_in_memory()


# Global singleton instance
resource_budget = ResourceBudgetManager()
