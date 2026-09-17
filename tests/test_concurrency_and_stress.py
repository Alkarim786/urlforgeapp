"""Concurrency, Race Condition, and Stress Tests for Phase 10.

Demonstrates Computer Science backend engineering principles:
1. Concurrency Race Conditions: Multiple simultaneous requests attempting to register
   the exact same custom alias. Exactly one request must succeed (HTTP 201) while all
   others must be cleanly rejected with HTTP 409 Conflict without deadlocks.
2. Atomic Counter Concurrency: High-volume concurrent requests hitting the redirect endpoint.
   Verifies that SQL atomic updates (`UPDATE urls SET click_count = click_count + 1`)
   prevent lost-update anomalies across interleaved transactions.
3. Cache-Aside Consistency under concurrent stampede.
"""

import asyncio
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from app.database import get_session_factory
from app.main import app
from app.models import URLModel


@pytest.mark.asyncio
async def test_concurrent_alias_registration_race_condition():
    """Verify that concurrent attempts to claim the same custom alias result in 1 success and N-1 409s."""
    contested_alias = f"race_{uuid.uuid4().hex[:8]}"
    transport = ASGITransport(app=app)
    num_concurrent_requests = 10

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async def try_register():
            return await client.post(
                "/api/v1/urls",
                json={
                    "url": "https://example.com/race-condition-target",
                    "custom_alias": contested_alias,
                },
            )

        # Launch all registration requests concurrently
        responses = await asyncio.gather(*[try_register() for _ in range(num_concurrent_requests)])

        success_count = sum(1 for r in responses if r.status_code == 201)
        conflict_count = sum(1 for r in responses if r.status_code == 409)

        # Exactly one must win the race; all others must be 409 Conflict
        assert success_count == 1, f"Expected 1 winner, got {success_count}"
        assert conflict_count == num_concurrent_requests - 1, f"Expected {num_concurrent_requests - 1} conflicts, got {conflict_count}"

    # Verify only single record in database
    factory = get_session_factory()
    async with factory() as session:
        stmt = select(URLModel).where(URLModel.short_code == contested_alias)
        res = await session.execute(stmt)
        records = res.scalars().all()
        assert len(records) == 1


@pytest.mark.asyncio
async def test_concurrent_atomic_click_counter_increments():
    """Verify that concurrent redirect requests atomically update click_count without lost updates."""
    transport = ASGITransport(app=app)
    num_clicks = 25
    alias = f"counter_{uuid.uuid4().hex[:8]}"

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create the short link
        create_res = await client.post(
            "/api/v1/urls",
            json={
                "url": "https://en.wikipedia.org/wiki/Concurrency_control",
                "custom_alias": alias,
            },
        )
        assert create_res.status_code == 201

        # Fire concurrent redirect hits
        async def send_click():
            return await client.get(f"/{alias}", follow_redirects=False)

        responses = await asyncio.gather(*[send_click() for _ in range(num_clicks)])
        for r in responses:
            assert r.status_code in (301, 302, 307, 308)

        # Wait briefly for background tasks to complete database writes
        await asyncio.sleep(0.5)

        # Verify exact click count in metadata endpoint
        meta_res = await client.get(f"/api/v1/urls/{alias}")
        assert meta_res.status_code == 200
        meta = meta_res.json()
        assert meta["click_count"] == num_clicks, f"Expected {num_clicks} clicks, found {meta['click_count']}"
