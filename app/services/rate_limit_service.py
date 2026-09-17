"""Redis-backed distributed sliding window rate limiter.

Architecture:
- Uses Redis sorted sets (ZSET) to implement an accurate sliding-window rate limit.
- Resilient fallback: Falls back to an in-memory sliding window cache if Redis is unavailable.
- Provides standard X-RateLimit headers and RFC 6585 HTTP 429 Too Many Requests.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Optional
from fastapi import HTTPException, Request, Response, status
from redis.exceptions import RedisError

from app.config import get_settings
from app.services.cache_service import CacheService, get_cache_service

logger = logging.getLogger("urlforge.ratelimit")
settings = get_settings()

# In-memory fallback tracking for when Redis is offline
_in_memory_windows: dict[str, list[float]] = defaultdict(list)


@dataclass
class RateLimitResult:
    """Result of rate limit evaluation."""
    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int
    retry_after: int


class RateLimitService:
    """Sliding-window rate limiter powered by Redis with in-memory degradation."""

    def __init__(self, cache_service: Optional[CacheService] = None):
        self._cache = cache_service or get_cache_service()

    async def check_rate_limit(
        self,
        identifier: str,
        limit: int = 100,
        window_seconds: int = 60,
        scope: str = "general",
    ) -> RateLimitResult:
        """Evaluate if client identifier has exceeded allowed request limit in window."""
        now = time.time()
        window_start = now - window_seconds
        key = f"ratelimit:{scope}:{identifier}"

        # 1. Attempt Redis Sliding Window Evaluation
        try:
            client = self._cache.get_client()
            async with client.pipeline(transaction=True) as pipe:
                # Remove timestamps older than window
                pipe.zremrangebyscore(key, 0, window_start)
                # Count remaining timestamps in window
                pipe.zcard(key)
                results = await pipe.execute()

            current_count = results[1]

            if current_count < limit:
                # Under limit -> record this request
                member = f"{now}:{time.time_ns()}"
                async with client.pipeline(transaction=True) as pipe:
                    pipe.zadd(key, {member: now})
                    pipe.expire(key, window_seconds + 5)
                    await pipe.execute()

                remaining = max(0, limit - current_count - 1)
                return RateLimitResult(
                    allowed=True,
                    limit=limit,
                    remaining=remaining,
                    reset_seconds=window_seconds,
                    retry_after=0,
                )
            else:
                # Over limit -> compute earliest expiry
                oldest_members = await client.zrange(key, 0, 0, withscores=True)
                reset_time = int(oldest_members[0][1] + window_seconds - now) if oldest_members else window_seconds
                retry_after = max(1, reset_time)
                return RateLimitResult(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    reset_seconds=retry_after,
                    retry_after=retry_after,
                )

        except (RedisError, OSError) as err:
            logger.warning("Redis rate limiter failed (%s); falling back to in-memory window.", err)

        # 2. In-Memory Graceful Degradation Fallback
        timestamps = _in_memory_windows[key]
        # Prune old timestamps
        _in_memory_windows[key] = [t for t in timestamps if t > window_start]
        current_in_mem = _in_memory_windows[key]

        if len(current_in_mem) < limit:
            current_in_mem.append(now)
            remaining = max(0, limit - len(current_in_mem))
            return RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=remaining,
                reset_seconds=window_seconds,
                retry_after=0,
            )
        else:
            oldest = current_in_mem[0] if current_in_mem else now
            retry_after = max(1, int(oldest + window_seconds - now))
            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                reset_seconds=retry_after,
                retry_after=retry_after,
            )


def rate_limiter(
    limit: Optional[int] = None,
    window_seconds: int = 60,
    scope: str = "general",
) -> Callable:
    """FastAPI Dependency generating rate limit enforcement with headers."""
    effective_limit = limit or settings.RATE_LIMIT_PER_MINUTE
    service = RateLimitService()

    async def dependency(request: Request, response: Response) -> None:
        client_ip = request.client.host if request.client else "unknown"
        # Extract forward headers if behind proxy
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()

        result = await service.check_rate_limit(
            identifier=client_ip,
            limit=effective_limit,
            window_seconds=window_seconds,
            scope=scope,
        )

        # Attach standard rate limit headers
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset_seconds)

        if not result.allowed:
            response.headers["Retry-After"] = str(result.retry_after)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {result.limit} requests per {window_seconds}s. Retry in {result.retry_after}s.",
                headers={"Retry-After": str(result.retry_after)},
            )

    return dependency


def get_rate_limit_service() -> RateLimitService:
    """Dependency injection provider for RateLimitService."""
    return RateLimitService()

