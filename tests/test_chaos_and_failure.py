"""Chaos Engineering and Graceful Degradation Failure Tests for Phase 14.

Validates system resilience under failure conditions:
1. Complete Redis Outage:
   - Health check gracefully reports 'degraded' status (HTTP 503) with 'disconnected' Redis.
   - URL creation still succeeds via direct PostgreSQL persistence (CacheService absorbs error).
   - URL redirects still succeed via PostgreSQL fallback query.
   - Rate limiting falls back to local in-memory sliding window.
2. Database Offline with Cache Warm:
   - When database connections fail or drop, cached URLs in Redis are served
     with zero user-facing downtime (HTTP 307 maintained).
3. Rate Limiter Resilience:
   - Rate limiting gracefully switches to in-memory tracking during Redis disruptions.
"""

from unittest.mock import AsyncMock, patch
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.exc import OperationalError
from app.main import app
from app.services.cache_service import get_cache_service
from app.services.rate_limit_service import get_rate_limit_service


@pytest.mark.asyncio
async def test_chaos_redis_outage_health_check_degraded():
    """Verify health endpoint reports degraded status when Redis experiences an outage."""
    transport = ASGITransport(app=app)
    cache = get_cache_service()

    with patch.object(cache, "ping", new=AsyncMock(return_value=False)):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/health")
            # In orchestration/k8s probes, degraded status sets 503
            assert res.status_code == 503
            data = res.json()
            assert data["status"] == "degraded"
            assert data["components"]["cache"] == "disconnected"
            assert data["components"]["database"] == "connected"


@pytest.mark.asyncio
async def test_chaos_redis_outage_url_creation_and_redirect_fallback():
    """Verify that URL creation and redirect resolution remain functional during a total Redis outage."""
    transport = ASGITransport(app=app)
    cache = get_cache_service()
    alias = f"chaos_{uuid.uuid4().hex[:6]}"
    target_url = "https://www.kernel.org/pub/linux/kernel/"

    # Simulate Redis throwing connection errors on client socket acquisition
    with patch.object(cache, "get_client", side_effect=RedisConnectionError("Redis connection refused")):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. URL creation succeeds despite Redis failure (falls through safely)
            create_res = await client.post(
                "/api/v1/urls",
                json={"url": target_url, "custom_alias": alias},
            )
            assert create_res.status_code == 201

            # 2. URL redirect succeeds by falling back to PostgreSQL read
            redir_res = await client.get(f"/{alias}", follow_redirects=False)
            assert redir_res.status_code == 307
            assert redir_res.headers["location"] == target_url


@pytest.mark.asyncio
async def test_chaos_database_outage_with_cache_hit():
    """Verify that if PostgreSQL goes offline, warmed Redis cache serves redirects without user interruption."""
    transport = ASGITransport(app=app)
    alias = f"cached_{uuid.uuid4().hex[:6]}"
    target = "https://www.python.org/downloads/"

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create URL and warm the Redis cache
        create_res = await client.post(
            "/api/v1/urls",
            json={"url": target, "custom_alias": alias},
        )
        assert create_res.status_code == 201

        # Prime cache
        prime_res = await client.get(f"/{alias}", follow_redirects=False)
        assert prime_res.status_code == 307

        # Simulate Database session failure
        with patch("app.services.url_service.URLService.get_url_record", new=AsyncMock(side_effect=OperationalError("DB Connection Lost", {}, None))):
            # Redirect must still succeed because destination is resolved directly from Redis
            cached_res = await client.get(f"/{alias}", follow_redirects=False)
            assert cached_res.status_code == 307
            assert cached_res.headers["location"] == target


@pytest.mark.asyncio
async def test_chaos_rate_limiter_in_memory_fallback():
    """Verify rate limiter automatically fails over to in-memory sliding window if Redis is offline."""
    rate_service = get_rate_limit_service()

    with patch.object(rate_service._cache, "get_client", side_effect=RedisConnectionError("Redis is unreachable")):
        # Should succeed using in-memory window
        result = await rate_service.check_rate_limit(
            identifier="chaos_test_ip",
            limit=5,
            window_seconds=60,
            scope="chaos",
        )
        assert result.allowed is True
        assert result.remaining == 4
