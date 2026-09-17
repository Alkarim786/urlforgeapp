"""Tests for Phase 9: Idempotency (Idempotency-Key).

Validates:
- Standard non-idempotent URL creation
- Safe replay of identical POST requests matching the same Idempotency-Key
- Header 'Idempotency-Replay: true' on duplicate submissions
- Prevention of duplicate database row creation on replay
- HTTP 422 Unprocessable Entity when same key is used with mismatched payloads
"""

import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from app.database import get_session_factory
from app.main import app
from app.models import URLModel


@pytest.mark.asyncio
async def test_idempotent_url_creation_and_replay():
    """Verify that repeating a request with the same Idempotency-Key replays without duplicates."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        idempotency_key = f"key-{uuid.uuid4().hex}"
        payload = {"url": "https://fastapi.tiangolo.com/tutorial/"}
        headers = {"Idempotency-Key": idempotency_key}

        # 1. First execution
        res1 = await client.post("/api/v1/urls", json=payload, headers=headers)
        assert res1.status_code == 201
        data1 = res1.json()
        assert "short_code" in data1
        assert "Idempotency-Replay" not in res1.headers

        # Count DB records matching this short code
        factory = get_session_factory()
        async with factory() as session:
            count_stmt = select(func.count(URLModel.id)).where(URLModel.short_code == data1["short_code"])
            count_res = await session.execute(count_stmt)
            count_before = count_res.scalar_one()
            assert count_before == 1

        # 2. Replay with identical payload and key
        res2 = await client.post("/api/v1/urls", json=payload, headers=headers)
        assert res2.status_code == 200 or res2.status_code == 201
        data2 = res2.json()

        # Must return exact same response and flag replay
        assert data2["short_code"] == data1["short_code"]
        assert data2["short_url"] == data1["short_url"]
        assert res2.headers.get("Idempotency-Replay") == "true"

        # Verify no duplicate database row was inserted
        async with factory() as session:
            count_stmt = select(func.count(URLModel.id)).where(URLModel.short_code == data1["short_code"])
            count_res = await session.execute(count_stmt)
            count_after = count_res.scalar_one()
            assert count_after == 1


@pytest.mark.asyncio
async def test_idempotency_key_payload_mismatch_rejected():
    """Verify that reusing an Idempotency-Key with different payload fails with 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        idempotency_key = f"mismatch-{uuid.uuid4().hex}"
        headers = {"Idempotency-Key": idempotency_key}

        # First request
        res1 = await client.post(
            "/api/v1/urls",
            json={"url": "https://docs.python.org/3/"},
            headers=headers,
        )
        assert res1.status_code == 201

        # Second request with same key but different URL
        res2 = await client.post(
            "/api/v1/urls",
            json={"url": "https://docs.pytest.org/en/latest/"},
            headers=headers,
        )
        assert res2.status_code == 422
        assert "different request payload" in res2.json()["detail"]
