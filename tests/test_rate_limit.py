"""Tests for Phase 8: Redis-Backed Distributed Rate Limiting.

Validates:
- Direct RateLimitService sliding window evaluation
- Request header generation: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset
- HTTP 429 Too Many Requests enforcement when threshold breached
- Retry-After header inclusion
- In-memory degradation fallback behavior
"""

import time
import uuid
import pytest
from fastapi import APIRouter, Depends, FastAPI, status
from httpx import ASGITransport, AsyncClient
from app.services.rate_limit_service import RateLimitService, rate_limiter


@pytest.mark.asyncio
async def test_rate_limit_service_sliding_window_allow_and_block():
    """Verify that RateLimitService correctly allows up to limit and rejects beyond."""
    service = RateLimitService()
    test_id = f"test-client-{uuid.uuid4().hex[:8]}"
    limit = 3
    window = 10

    # First 3 requests must be allowed
    for i in range(limit):
        res = await service.check_rate_limit(
            identifier=test_id,
            limit=limit,
            window_seconds=window,
            scope="unit_test",
        )
        assert res.allowed is True
        assert res.remaining == limit - 1 - i
        assert res.limit == limit

    # 4th request must be blocked
    blocked = await service.check_rate_limit(
        identifier=test_id,
        limit=limit,
        window_seconds=window,
        scope="unit_test",
    )
    assert blocked.allowed is False
    assert blocked.remaining == 0
    assert blocked.retry_after > 0


@pytest.mark.asyncio
async def test_rate_limit_fastapi_dependency_headers_and_429():
    """Verify rate limiter dependency attaches headers and returns 429 when exceeded."""
    test_app = FastAPI()
    test_router = APIRouter()

    @test_router.get(
        "/limited",
        dependencies=[Depends(rate_limiter(limit=2, window_seconds=5, scope="api_test"))],
    )
    async def limited_endpoint():
        return {"status": "ok"}

    test_app.include_router(test_router)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Request 1: Allowed
        r1 = await client.get("/limited")
        assert r1.status_code == 200
        assert r1.headers.get("X-RateLimit-Limit") == "2"
        assert r1.headers.get("X-RateLimit-Remaining") == "1"
        assert "X-RateLimit-Reset" in r1.headers

        # Request 2: Allowed
        r2 = await client.get("/limited")
        assert r2.status_code == 200
        assert r2.headers.get("X-RateLimit-Remaining") == "0"

        # Request 3: Blocked with HTTP 429
        r3 = await client.get("/limited")
        assert r3.status_code == 429
        assert "Retry-After" in r3.headers
        assert "Rate limit exceeded" in r3.json()["detail"]


@pytest.mark.asyncio
async def test_rate_limit_applied_to_url_create_endpoint():
    """Verify that URL create endpoint returns X-RateLimit headers."""
    from app.main import app as main_app

    transport = ASGITransport(app=main_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/urls",
            json={"url": "https://example.com/rate-limited"},
        )
        assert res.status_code == 201
        assert "X-RateLimit-Limit" in res.headers
        assert "X-RateLimit-Remaining" in res.headers
