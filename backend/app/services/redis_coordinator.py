"""
Shared Redis Coordination Service (P4.7-B / P4.7-D / P4.8.3)

Handles distributed execution locks, lock renewal heartbeats, atomic sliding-window rate limiting,
atomic Lua project resource budget accounting, Pub/Sub WebSocket event broadcasting, and
fail-closed distributed cancellation signaling.

Production policy: Requires valid REDIS_URL in production (fail-closed).
Development policy: Provides in-memory mock fallback when REDIS_URL is unconfigured in development.
"""

import os
import json
import time
import uuid
import logging
import asyncio
import inspect
from typing import Optional, Tuple, Dict, Any, AsyncGenerator

from app.core.config import REDIS_URL, get_environment, RATE_LIMIT_WINDOW_SECONDS, MAX_PROJECTS_PER_WINDOW, MAX_PROJECT_RUNS_PER_WINDOW

logger = logging.getLogger(__name__)


class RedisUnavailableError(Exception):
    """Raised when Redis coordination is required in production but unavailable."""
    pass


class LockLostError(Exception):
    """Raised when active execution lock renewal fails (lock lost or token mismatch)."""
    pass


class InMemoryCoordinator:
    """In-memory mock fallback for offline local development & unit testing."""
    def __init__(self):
        self._locks: Dict[str, Tuple[str, float]] = {}  # key -> (token, expire_ts)
        self._rate_limits: Dict[str, list[float]] = {}
        self._budgets: Dict[str, Dict[str, int]] = {}
        self._subscribers: Dict[str, list[asyncio.Queue]] = {}
        self._cancellation_flags: Dict[str, float] = {}  # exec_id -> expire_ts

    def _clean(self):
        now = time.time()
        expired_locks = [k for k, (_, exp) in self._locks.items() if exp < now]
        for k in expired_locks:
            self._locks.pop(k, None)
        expired_cancels = [k for k, exp in self._cancellation_flags.items() if exp < now]
        for k in expired_cancels:
            self._cancellation_flags.pop(k, None)

    async def acquire_lock(self, project_id: str, ttl_seconds: int = 60) -> Optional[str]:
        self._clean()
        key = f"lock:execution:{project_id}"
        if key in self._locks:
            return None
        token = uuid.uuid4().hex
        self._locks[key] = (token, time.time() + ttl_seconds)
        return token

    async def renew_lock(self, project_id: str, token: str, ttl_seconds: int = 60) -> bool:
        self._clean()
        key = f"lock:execution:{project_id}"
        if key in self._locks:
            current_token, _ = self._locks[key]
            if current_token == token:
                self._locks[key] = (token, time.time() + ttl_seconds)
                return True
        return False

    async def release_lock(self, project_id: str, token: str) -> bool:
        self._clean()
        key = f"lock:execution:{project_id}"
        if key in self._locks:
            current_token, _ = self._locks[key]
            if current_token == token:
                self._locks.pop(key, None)
                return True
        return False

    def check_rate_limit(self, user_id: str, action: str = "run", limit: Optional[int] = None, window_seconds: Optional[int] = None) -> Tuple[bool, int]:
        window = window_seconds or RATE_LIMIT_WINDOW_SECONDS
        lim = limit if limit is not None else (MAX_PROJECTS_PER_WINDOW if action == "create" else MAX_PROJECT_RUNS_PER_WINDOW)
        key = f"ratelimit:{user_id}:{action}"
        
        now = time.time()
        history = self._rate_limits.get(key, [])
        valid_history = [ts for ts in history if ts > now - window]
        self._rate_limits[key] = valid_history

        if len(valid_history) >= lim:
            oldest_ts = valid_history[0]
            retry_after = max(1, int(window - (now - oldest_ts)))
            return False, retry_after

        valid_history.append(now)
        self._rate_limits[key] = valid_history
        return True, 0

    async def consume_budget(self, project_id: str, resource_type: str, max_limit: int, amount: int = 1) -> Tuple[bool, int]:
        proj_dict = self._budgets.setdefault(project_id, {})
        current = proj_dict.get(resource_type, 0)
        if current + amount > max_limit:
            return False, current
        new_val = current + amount
        proj_dict[resource_type] = new_val
        return True, new_val

    async def set_cancellation_flag(self, execution_id: str, ttl_seconds: int = 3600) -> bool:
        self._clean()
        self._cancellation_flags[execution_id] = time.time() + ttl_seconds
        return True

    def is_cancelled(self, execution_id: str) -> bool:
        self._clean()
        return execution_id in self._cancellation_flags

    async def publish_event(self, project_id: str, event_type: str, data: dict):
        channel = f"ws:project:{project_id}"
        queues = self._subscribers.get(channel, [])
        payload = json.dumps({"type": event_type, "project_id": project_id, "data": data})
        for q in list(queues):
            try:
                q.put_nowait(payload)
            except Exception:
                pass

    async def subscribe_events(self, project_id: str) -> AsyncGenerator[str, None]:
        channel = f"ws:project:{project_id}"
        q = asyncio.Queue()
        subscribers = self._subscribers.setdefault(channel, [])
        subscribers.append(q)
        try:
            while True:
                msg = await q.get()
                yield msg
        finally:
            if q in subscribers:
                subscribers.remove(q)

    def reset(self):
        self._locks.clear()
        self._rate_limits.clear()
        self._budgets.clear()
        self._subscribers.clear()
        self._cancellation_flags.clear()


class AwaitableBool:
    """Helper wrapper allowing cancellation checks to be both awaited asynchronously and evaluated as boolean."""
    def __init__(self, coro_func, sync_func):
        self._coro_func = coro_func
        self._sync_func = sync_func
        self._coro = None

    def __await__(self):
        if self._coro is None:
            self._coro = self._coro_func()
        return self._coro.__await__()

    def __bool__(self):
        if self._coro is not None:
            self._coro.close()
            self._coro = None
        return bool(self._sync_func())


class RedisCoordinator:
    """
    Provider-independent Redis Coordination Service with Distributed Locks, Heartbeats, Budget Lua Scripts, and Cancellation Flags.
    Hardened for Production Async Execution & Fail-Closed Behavior (P4.8.3).
    """
    _LUA_RELEASE_LOCK = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
    """

    _LUA_RENEW_LOCK = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("PEXPIRE", KEYS[1], tonumber(ARGV[2]))
        else
            return 0
        end
    """

    _LUA_RATE_LIMIT = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local window = tonumber(ARGV[2])
        local limit = tonumber(ARGV[3])
        local clear_before = now - window

        redis.call('ZREMRANGEBYSCORE', key, '-inf', clear_before)
        local count = redis.call('ZCARD', key)

        if count < limit then
            redis.call('ZADD', key, now, now)
            redis.call('EXPIRE', key, math.ceil(window))
            return {1, 0}
        else
            local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
            local retry_after = 1
            if #oldest > 1 then
                retry_after = math.max(1, math.ceil(window - (now - tonumber(oldest[2]))))
            end
            return {0, retry_after}
        end
    """

    _LUA_CONSUME_BUDGET = """
        local key = KEYS[1]
        local field = ARGV[1]
        local limit = tonumber(ARGV[2])
        local amount = tonumber(ARGV[3]) or 1

        local current = tonumber(redis.call("HGET", key, field) or "0")
        if current + amount <= limit then
            local new_val = redis.call("HINCRBY", key, field, amount)
            return {1, new_val}
        else
            return {0, current}
        end
    """

    def __init__(self):
        self._client = None
        self._in_memory_fallback = InMemoryCoordinator()

    async def _get_client(self):
        env = get_environment()
        if not REDIS_URL:
            if env == "production":
                raise RedisUnavailableError("Security Violation: REDIS_URL is unconfigured. Redis coordination is strictly required in production.")
            return None

        if self._client is None:
            import redis.asyncio as aioredis
            try:
                self._client = aioredis.from_url(REDIS_URL, decode_responses=True)
                await self._client.ping()
            except Exception as e:
                logger.error(f"Redis connection error: {e}")
                if env == "production":
                    raise RedisUnavailableError(f"Production Redis connection failed: {e}")
                return None
        return self._client

    async def acquire_lock(self, project_id: str, ttl_seconds: int = 60) -> Optional[str]:
        """Atomically acquires an execution lock with token and TTL."""
        client = await self._get_client()
        if client is None:
            return await self._in_memory_fallback.acquire_lock(project_id, ttl_seconds)

        key = f"lock:execution:{project_id}"
        token = uuid.uuid4().hex
        ttl_ms = int(ttl_seconds * 1000)
        try:
            acquired = await client.set(key, token, nx=True, px=ttl_ms)
            return token if acquired else None
        except Exception as e:
            if get_environment() == "production":
                raise RedisUnavailableError(f"Production Redis error during acquire_lock: {e}")
            logger.warning(f"Redis acquire_lock error: {e}")
            return await self._in_memory_fallback.acquire_lock(project_id, ttl_seconds)

    async def renew_lock(self, project_id: str, token: str, ttl_seconds: int = 60) -> bool:
        """Atomically renews lock TTL if token ownership matches via Lua script."""
        client = await self._get_client()
        if client is None:
            return await self._in_memory_fallback.renew_lock(project_id, token, ttl_seconds)

        key = f"lock:execution:{project_id}"
        ttl_ms = int(ttl_seconds * 1000)
        try:
            res = await client.eval(self._LUA_RENEW_LOCK, 1, key, token, str(ttl_ms))
            return bool(res)
        except Exception as e:
            if get_environment() == "production":
                raise RedisUnavailableError(f"Production Redis error during renew_lock: {e}")
            logger.warning(f"Redis renew_lock error: {e}")
            return await self._in_memory_fallback.renew_lock(project_id, token, ttl_seconds)

    async def release_lock(self, project_id: str, token: str) -> bool:
        """Safely releases execution lock using token verification via Lua script."""
        client = await self._get_client()
        if client is None:
            return await self._in_memory_fallback.release_lock(project_id, token)

        key = f"lock:execution:{project_id}"
        try:
            res = await client.eval(self._LUA_RELEASE_LOCK, 1, key, token)
            return bool(res)
        except Exception as e:
            if get_environment() == "production":
                raise RedisUnavailableError(f"Production Redis error during release_lock: {e}")
            logger.warning(f"Redis release_lock error: {e}")
            return await self._in_memory_fallback.release_lock(project_id, token)

    async def check_rate_limit_async(self, user_id: str, action: str = "run", limit: Optional[int] = None, window_seconds: Optional[int] = None) -> Tuple[bool, int]:
        """Async sliding window rate limit check."""
        client = await self._get_client()
        if client is None:
            return self._in_memory_fallback.check_rate_limit(user_id, action, limit, window_seconds)

        window = window_seconds or RATE_LIMIT_WINDOW_SECONDS
        lim = limit if limit is not None else (MAX_PROJECTS_PER_WINDOW if action == "create" else MAX_PROJECT_RUNS_PER_WINDOW)
        key = f"ratelimit:{user_id}:{action}"
        now = time.time()

        try:
            res = await client.eval(self._LUA_RATE_LIMIT, 1, key, str(now), str(window), str(lim))
            return bool(res[0]), int(res[1])
        except Exception as e:
            if get_environment() == "production":
                raise RedisUnavailableError(f"Production Redis error during check_rate_limit: {e}")
            logger.warning(f"Redis check_rate_limit error: {e}")
            return self._in_memory_fallback.check_rate_limit(user_id, action, limit, window_seconds)

    def check_rate_limit(self, user_id: str, action: str = "run", limit: Optional[int] = None, window_seconds: Optional[int] = None) -> Tuple[bool, int]:
        """Synchronous sliding window rate limit check interface."""
        env = get_environment()
        if not REDIS_URL or self._client is None:
            if env == "production":
                raise RedisUnavailableError("Security Violation: REDIS_URL is unconfigured. Redis coordination is strictly required in production.")
            return self._in_memory_fallback.check_rate_limit(user_id, action, limit, window_seconds)

        window = window_seconds or RATE_LIMIT_WINDOW_SECONDS
        lim = limit if limit is not None else (MAX_PROJECTS_PER_WINDOW if action == "create" else MAX_PROJECT_RUNS_PER_WINDOW)
        key = f"ratelimit:{user_id}:{action}"
        now = time.time()

        try:
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    if env == "production":
                        raise RedisUnavailableError("Production Redis error: Synchronous rate limit check cannot block an active asyncio event loop. Use 'await rate_limiter.check_rate_limit()' or 'await redis_coordinator.check_rate_limit_async()' instead.")
                    return self._in_memory_fallback.check_rate_limit(user_id, action, limit, window_seconds)
            except RuntimeError:
                pass
            return asyncio.run(self.check_rate_limit_async(user_id, action, limit, window_seconds))
        except RedisUnavailableError:
            raise
        except Exception as e:
            if env == "production":
                raise RedisUnavailableError(f"Production Redis error during check_rate_limit: {e}")
            return self._in_memory_fallback.check_rate_limit(user_id, action, limit, window_seconds)

    async def consume_budget(self, project_id: str, resource_type: str, max_limit: int, amount: int = 1) -> Tuple[bool, int]:
        """Atomic budget check and increment via Lua script."""
        client = await self._get_client()
        if client is None:
            return await self._in_memory_fallback.consume_budget(project_id, resource_type, max_limit, amount)

        key = f"budget:{project_id}"
        try:
            res = await client.eval(self._LUA_CONSUME_BUDGET, 1, key, resource_type, str(max_limit), str(amount))
            allowed = bool(res[0])
            val = int(res[1])
            return allowed, val
        except Exception as e:
            if get_environment() == "production":
                raise RedisUnavailableError(f"Production Redis error during consume_budget: {e}")
            logger.warning(f"Redis consume_budget error: {e}")
            return await self._in_memory_fallback.consume_budget(project_id, resource_type, max_limit, amount)

    async def set_cancellation_flag(self, execution_id: str, ttl_seconds: int = 3600) -> bool:
        """Sets Redis cancellation flag cancel:execution:{execution_id}."""
        client = await self._get_client()
        if client is None:
            return await self._in_memory_fallback.set_cancellation_flag(execution_id, ttl_seconds)

        key = f"cancel:execution:{execution_id}"
        try:
            await client.set(key, "true", ex=ttl_seconds)
            return True
        except Exception as e:
            if get_environment() == "production":
                raise RedisUnavailableError(f"Production Redis error during set_cancellation_flag: {e}")
            logger.warning(f"Redis set_cancellation_flag error: {e}")
            return await self._in_memory_fallback.set_cancellation_flag(execution_id, ttl_seconds)

    async def is_cancelled_async(self, execution_id: str) -> bool:
        """Asynchronously checks if cancellation flag is set for execution_id in Redis."""
        client = await self._get_client()
        if client is None:
            return self._in_memory_fallback.is_cancelled(execution_id)

        key = f"cancel:execution:{execution_id}"
        try:
            res = await client.get(key)
            return bool(res)
        except Exception as e:
            if get_environment() == "production":
                raise RedisUnavailableError(f"Production Redis error during is_cancelled_async: {e}")
            logger.warning(f"Redis connection error in is_cancelled_async: {e}")
            return self._in_memory_fallback.is_cancelled(execution_id)

    def _is_cancelled_sync(self, execution_id: str) -> bool:
        """Synchronous fallback check for is_cancelled."""
        env = get_environment()
        if not REDIS_URL or self._client is None:
            if env == "production":
                raise RedisUnavailableError("Security Violation: REDIS_URL is unconfigured. Redis coordination is strictly required in production.")
            return self._in_memory_fallback.is_cancelled(execution_id)

        key = f"cancel:execution:{execution_id}"
        try:
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    if env == "production":
                        raise RedisUnavailableError("Production Redis error: Synchronous cancellation check cannot block an active asyncio event loop. Use 'await redis_coordinator.is_cancelled(execution_id)' instead.")
                    return self._in_memory_fallback.is_cancelled(execution_id)
            except RuntimeError:
                pass
            return asyncio.run(self.is_cancelled_async(execution_id))
        except RedisUnavailableError:
            raise
        except Exception as e:
            if env == "production":
                raise RedisUnavailableError(f"Production Redis error during is_cancelled: {e}")
            logger.warning(f"Redis connection error in is_cancelled: {e}")
            return self._in_memory_fallback.is_cancelled(execution_id)

    def is_cancelled(self, execution_id: str):
        """
        Hybrid cancellation check interface.
        Supports both 'if await redis_coordinator.is_cancelled(exec_id):' and 'if redis_coordinator.is_cancelled(exec_id):'.
        """
        return AwaitableBool(
            coro_func=lambda: self.is_cancelled_async(execution_id),
            sync_func=lambda: self._is_cancelled_sync(execution_id)
        )

    async def publish_event(self, project_id: str, event_type: str, data: dict):
        """Publishes JSON event payload to Redis Pub/Sub channel ws:project:{project_id}."""
        client = await self._get_client()
        if client is None:
            return await self._in_memory_fallback.publish_event(project_id, event_type, data)

        channel = f"ws:project:{project_id}"
        payload = json.dumps({"type": event_type, "project_id": project_id, "data": data})
        try:
            await client.publish(channel, payload)
        except Exception as e:
            if get_environment() == "production":
                raise RedisUnavailableError(f"Production Redis error during publish_event: {e}")
            logger.warning(f"Redis publish_event error: {e}")
            return await self._in_memory_fallback.publish_event(project_id, event_type, data)

    async def subscribe_events(self, project_id: str) -> AsyncGenerator[str, None]:
        """Subscribes to Redis Pub/Sub channel ws:project:{project_id} yielding messages."""
        client = await self._get_client()
        if client is None:
            async for msg in self._in_memory_fallback.subscribe_events(project_id):
                yield msg
            return

        import redis.asyncio as aioredis
        pubsub = client.pubsub()
        channel = f"ws:project:{project_id}"
        try:
            await pubsub.subscribe(channel)
            async for message in pubsub.listen():
                if message and message.get("type") == "message":
                    yield message.get("data")
        except Exception as e:
            if get_environment() == "production":
                raise RedisUnavailableError(f"Production Redis error during subscribe_events: {e}")
            logger.warning(f"Redis subscribe_events error: {e}")
            async for msg in self._in_memory_fallback.subscribe_events(project_id):
                yield msg
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
            except Exception:
                pass

    async def ping(self) -> bool:
        client = await self._get_client()
        if client is None:
            return False
        try:
            return await client.ping()
        except Exception:
            return False

    async def close(self):
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None

    def reset_in_memory(self):
        """Helper for resetting unit testing fallback state."""
        self._in_memory_fallback.reset()


class LockHeartbeat:
    """
    Periodic background heartbeat runner for active distributed execution lock renewal.
    """
    def __init__(self, project_id: str, token: str, ttl_seconds: int = 60, interval_seconds: int = 15):
        self.project_id = project_id
        self.token = token
        self.ttl_seconds = ttl_seconds
        self.interval_seconds = interval_seconds
        self._task: Optional[asyncio.Task] = None
        self._stopped = False
        self.failed = False

    async def _loop(self):
        try:
            while not self._stopped:
                await asyncio.sleep(self.interval_seconds)
                if self._stopped:
                    break
                renewed = await redis_coordinator.renew_lock(self.project_id, self.token, self.ttl_seconds)
                if not renewed:
                    self.failed = True
                    logger.critical(f"Lock renewal failed for project {self.project_id}! Lock lost or token invalidated.")
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.failed = True
            logger.critical(f"Lock renewal error for project {self.project_id}: {e}")

    def start(self):
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self._stopped = True
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


# Global singleton instance
redis_coordinator = RedisCoordinator()
