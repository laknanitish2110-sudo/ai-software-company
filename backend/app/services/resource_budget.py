"""
Project Resource Budget Manager (P4.4)

Tracks and enforces per-project execution limits (LLM calls, E2B microVM executions, repair attempts).
Fails closed with ResourceBudgetExceededError before invoking expensive external operations.
"""

import threading
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


import asyncio
from app.services.redis_coordinator import redis_coordinator


class ResourceBudgetManager:
    """
    Manager for tracking per-project resource budgets via Redis coordination.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._budgets: Dict[str, Dict[str, int]] = {}

    def _get_project_counters(self, project_id: str) -> Dict[str, int]:
        if project_id not in self._budgets:
            self._budgets[project_id] = {
                "llm_calls": 0,
                "e2b_executions": 0,
                "repair_attempts": 0,
            }
        return self._budgets[project_id]

    def check_llm_budget(self, project_id: str, max_limit: Optional[int] = None):
        limit = max_limit if max_limit is not None else MAX_LLM_CALLS_PER_PROJECT
        with self._lock:
            counters = self._get_project_counters(project_id)
            if counters["llm_calls"] >= limit:
                msg = f"RESOURCE_BUDGET_EXCEEDED: Project {project_id} reached max LLM calls limit ({counters['llm_calls']}/{limit})."
                logger.warning(msg)
                raise ResourceBudgetExceededError(msg)

    def record_llm_call(self, project_id: str):
        with self._lock:
            counters = self._get_project_counters(project_id)
            counters["llm_calls"] += 1

    def check_e2b_budget(self, project_id: str, max_limit: Optional[int] = None):
        limit = max_limit if max_limit is not None else MAX_E2B_EXECUTIONS_PER_PROJECT
        with self._lock:
            counters = self._get_project_counters(project_id)
            if counters["e2b_executions"] >= limit:
                msg = f"RESOURCE_BUDGET_EXCEEDED: Project {project_id} reached max E2B executions limit ({counters['e2b_executions']}/{limit})."
                logger.warning(msg)
                raise ResourceBudgetExceededError(msg)

    def record_e2b_execution(self, project_id: str):
        with self._lock:
            counters = self._get_project_counters(project_id)
            counters["e2b_executions"] += 1

    def check_repair_budget(self, project_id: str, max_limit: Optional[int] = None):
        limit = max_limit if max_limit is not None else MAX_REPAIR_ATTEMPTS_HARD_LIMIT
        with self._lock:
            counters = self._get_project_counters(project_id)
            if counters["repair_attempts"] >= limit:
                msg = f"RESOURCE_BUDGET_EXCEEDED: Project {project_id} reached max repair attempts ceiling ({counters['repair_attempts']}/{limit})."
                logger.warning(msg)
                raise ResourceBudgetExceededError(msg)

    def record_repair_attempt(self, project_id: str):
        with self._lock:
            counters = self._get_project_counters(project_id)
            counters["repair_attempts"] += 1

    def get_budget_status(self, project_id: str) -> Dict[str, Any]:
        with self._lock:
            counters = dict(self._get_project_counters(project_id))
            status = "OK"
            if (
                counters["llm_calls"] >= MAX_LLM_CALLS_PER_PROJECT
                or counters["e2b_executions"] >= MAX_E2B_EXECUTIONS_PER_PROJECT
                or counters["repair_attempts"] >= MAX_REPAIR_ATTEMPTS_HARD_LIMIT
            ):
                status = "RESOURCE_BUDGET_EXCEEDED"

            return {
                "project_id": project_id,
                "llm_calls": counters["llm_calls"],
                "e2b_executions": counters["e2b_executions"],
                "repair_attempts": counters["repair_attempts"],
                "max_llm_calls": MAX_LLM_CALLS_PER_PROJECT,
                "max_e2b_executions": MAX_E2B_EXECUTIONS_PER_PROJECT,
                "max_repair_attempts": MAX_REPAIR_ATTEMPTS_HARD_LIMIT,
                "budget_status": status,
            }

    def reset_project(self, project_id: str):
        with self._lock:
            self._budgets.pop(project_id, None)
            redis_coordinator.reset_in_memory()


# Global singleton instance
resource_budget = ResourceBudgetManager()
