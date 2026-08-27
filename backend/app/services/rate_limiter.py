"""
In-Process / Single-Instance Sliding Window Rate Limiter Service (V1)

ARCHITECTURE LIMITATION & SECURITY NOTICE:
--------------------------------------------------------------------------------
This rate limiter uses a thread-safe in-process sliding window algorithm suitable
for single-instance deployment/prototyping.

WARNING: This implementation is NOT suitable for multi-instance / horizontally-scaled
deployments (e.g. Kubernetes, multiple Uvicorn workers). For production horizontal
scaling, this service MUST be updated to use a shared distributed cache store such
as Redis (e.g., Redis fixed-window or token-bucket).
--------------------------------------------------------------------------------
"""

import time
import threading
import asyncio
from typing import Dict, List, Tuple, Optional
import logging

from app.core.config import (
    MAX_PROJECTS_PER_WINDOW,
    MAX_PROJECT_RUNS_PER_WINDOW,
    RATE_LIMIT_WINDOW_SECONDS
)

logger = logging.getLogger(__name__)


from app.services.redis_coordinator import redis_coordinator

class UserRateLimiter:
    """
    Tracks request timestamps per user_id and enforces sliding window rate limits via Redis.
    """
    def check_rate_limit(
        self,
        user_id: str,
        action: str = "run",
        window_seconds: Optional[int] = None,
        limit: Optional[int] = None,
        max_limit: Optional[int] = None
    ) -> Tuple[bool, int]:
        """
        Checks if user_id can perform action via Redis coordination.
        Returns: (allowed: bool, retry_after_seconds: int)
        """
        lim = limit or max_limit
        if redis_coordinator._client is None:
            return redis_coordinator._in_memory_fallback.check_rate_limit(user_id, action, lim, window_seconds)
        else:
            try:
                loop = asyncio.get_running_loop()
                return redis_coordinator._in_memory_fallback.check_rate_limit(user_id, action, lim, window_seconds)
            except RuntimeError:
                return asyncio.run(redis_coordinator.check_rate_limit(user_id, action, lim, window_seconds))

    def reset_user(self, user_id: str):
        """Reset rate limit history for test isolation."""
        redis_coordinator.reset_in_memory()


# Global singleton instance
rate_limiter = UserRateLimiter()
