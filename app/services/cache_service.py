"""Redis caching service implementing Cache-Aside pattern with resilient fallback.

Provides sub-millisecond key-value operations for active short codes.
Includes graceful degradation: if Redis is unavailable, methods return None/False
rather than crashing the HTTP request pipeline.
"""

import asyncio
import logging
from typing import Optional
import redis.asyncio as aioredis
from redis.exceptions import RedisError
from app.config import get_settings

logger = logging.getLogger("urlforge.cache")
settings = get_settings()


class CacheService:
    """Async Redis client wrapper with automated error handling and fallback."""

    def __init__(self, redis_url: Optional[str] = None):
        self._url = redis_url or settings.REDIS_URL
        self._client: Optional[aioredis.Redis] = None
        self._default_ttl = settings.CACHE_TTL_SECONDS
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def get_client(self) -> aioredis.Redis:
        """Lazily initialize and return Redis client with event loop affinity protection."""
        current_loop: Optional[asyncio.AbstractEventLoop] = None
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if self._client is None or (self._loop is not None and self._loop != current_loop):
            self._loop = current_loop
            self._client = aioredis.from_url(
                self._url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
        return self._client

    async def get(self, key: str) -> Optional[str]:
        """Retrieve cached value. Returns None on cache miss or Redis error."""
        try:
            client = self.get_client()
            return await client.get(key)
        except (RedisError, OSError) as err:
            logger.warning("Redis GET failed for key '%s': %s", key, err)
            return None

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Cache value with expiration in seconds. Returns True on success, False on error."""
        expiry = ttl if ttl is not None else self._default_ttl
        try:
            client = self.get_client()
            if expiry > 0:
                await client.set(key, value, ex=expiry)
            else:
                await client.set(key, value)
            return True
        except (RedisError, OSError) as err:
            logger.warning("Redis SET failed for key '%s': %s", key, err)
            return False

    async def delete(self, key: str) -> bool:
        """Evict key from cache."""
        try:
            client = self.get_client()
            await client.delete(key)
            return True
        except (RedisError, OSError) as err:
            logger.warning("Redis DELETE failed for key '%s': %s", key, err)
            return False

    async def ping(self) -> bool:
        """Check Redis connectivity."""
        try:
            client = self.get_client()
            res = await client.ping()
            return bool(res)
        except Exception:
            return False

    async def close(self):
        """Cleanly close connection pool."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            self._loop = None


# Singleton instance
_cache_service_instance: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """Dependency injection provider for CacheService."""
    global _cache_service_instance
    if _cache_service_instance is None:
        _cache_service_instance = CacheService()
    return _cache_service_instance
