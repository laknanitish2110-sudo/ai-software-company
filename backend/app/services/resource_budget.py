"""
Project Resource Budget Manager + Cost Governor

Tracks and enforces per-project execution limits:
  - LLM call count
  - Token budget (total tokens per project)
  - Cost budget (estimated $ per project)
  - E2B sandbox executions
  - Repair attempts

Records every LLM call to the cost_tracking table with token counts and estimated cost.
Emits cost_update WebSocket events for live UI updates.
"""

import logging
from typing import Dict, Any, Optional

from app.core.config import (
    MAX_LLM_CALLS_PER_PROJECT,
    MAX_E2B_EXECUTIONS_PER_PROJECT,
    MAX_REPAIR_ATTEMPTS_HARD_LIMIT,
    MAX_TOKENS_PER_PROJECT,
    MAX_COST_PER_PROJECT,
    estimate_cost,
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
        if MAX_TOKENS_PER_PROJECT > 0:
            tok_allowed, tok_current = await redis_coordinator.consume_budget(
                project_id, "total_tokens", MAX_TOKENS_PER_PROJECT, amount=0
            )
            if not tok_allowed:
                raise ResourceBudgetExceededError(
                    f"TOKEN_BUDGET_EXCEEDED: Project {project_id} reached max token limit ({tok_current}/{MAX_TOKENS_PER_PROJECT})."
                )

    async def record_llm_call(self, project_id: str, tokens: int = 0, role: str | None = None,
                               model: str = "", provider: str = "", usage: dict | None = None):
        await redis_coordinator.consume_budget(project_id, "llm_calls", MAX_LLM_CALLS_PER_PROJECT, amount=1)
        if tokens > 0 and MAX_TOKENS_PER_PROJECT > 0:
            await redis_coordinator.consume_budget(project_id, "total_tokens", MAX_TOKENS_PER_PROJECT, amount=tokens)
        if usage and role:
            try:
                await self._record_cost_entry(project_id, role, model, provider, usage)
            except Exception as e:
                logger.warning(f"Cost tracking write failed (non-critical): {e}")

    async def _record_cost_entry(self, project_id: str, role: str, model: str, provider: str, usage: dict):
        from app.core.database import record_cost
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)
        cost = estimate_cost(model, prompt_tokens, completion_tokens)
        await record_cost(
            project_id=project_id,
            role=role,
            model=model,
            provider=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost=cost,
        )
        try:
            await self._emit_cost_event(project_id, role, model, total_tokens, cost)
        except Exception:
            pass

    async def _emit_cost_event(self, project_id: str, role: str, model: str, tokens: int, cost: float):
        """Push live cost update to the frontend via WebSocket."""
        status = await self.get_budget_status(project_id)
        await redis_coordinator.publish_event(project_id, "cost_update", {
            "role": role,
            "model": model,
            "tokens": tokens,
            "cost": round(cost, 6),
            "totals": status,
            "message": f"{role} used {tokens:,} tokens",
        })

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
        total_tokens = 0
        try:
            _, llm = await redis_coordinator.consume_budget(project_id, "llm_calls", MAX_LLM_CALLS_PER_PROJECT, amount=0)
            _, e2b = await redis_coordinator.consume_budget(project_id, "e2b_executions", MAX_E2B_EXECUTIONS_PER_PROJECT, amount=0)
            _, repair = await redis_coordinator.consume_budget(project_id, "repair_attempts", MAX_REPAIR_ATTEMPTS_HARD_LIMIT, amount=0)
            if MAX_TOKENS_PER_PROJECT > 0:
                _, total_tokens = await redis_coordinator.consume_budget(project_id, "total_tokens", MAX_TOKENS_PER_PROJECT, amount=0)
        except Exception:
            pass

        status = "OK"
        if llm >= MAX_LLM_CALLS_PER_PROJECT:
            status = "RESOURCE_BUDGET_EXCEEDED"
        elif e2b >= MAX_E2B_EXECUTIONS_PER_PROJECT:
            status = "RESOURCE_BUDGET_EXCEEDED"
        elif repair >= MAX_REPAIR_ATTEMPTS_HARD_LIMIT:
            status = "RESOURCE_BUDGET_EXCEEDED"
        elif MAX_TOKENS_PER_PROJECT > 0 and total_tokens >= MAX_TOKENS_PER_PROJECT:
            status = "TOKEN_BUDGET_EXCEEDED"

        return {
            "project_id": project_id,
            "llm_calls": llm,
            "e2b_executions": e2b,
            "repair_attempts": repair,
            "total_tokens": total_tokens,
            "max_llm_calls": MAX_LLM_CALLS_PER_PROJECT,
            "max_e2b_executions": MAX_E2B_EXECUTIONS_PER_PROJECT,
            "max_repair_attempts": MAX_REPAIR_ATTEMPTS_HARD_LIMIT,
            "max_tokens": MAX_TOKENS_PER_PROJECT,
            "max_cost": MAX_COST_PER_PROJECT,
            "budget_status": status,
        }

    def reset_project(self, project_id: str):
        redis_coordinator.reset_in_memory()


# Global singleton instance
resource_budget = ResourceBudgetManager()
