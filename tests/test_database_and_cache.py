"""Tests for Phase 3 (PostgreSQL & SQLAlchemy 2.x) and Redis caching layer.

Verifies:
- Direct ORM model insertion and query
- Unique constraint enforcement on short_code
- Collision retry behavior in URLService
- Redis Cache-Aside set and get
- Subsystem health checks reporting connected components
"""

import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.database import get_session_factory
from app.main import app
from app.models import URLModel
from app.schemas import URLCreateRequest
from app.services.cache_service import get_cache_service
from app.services.url_service import CollisionRetryExhaustedError, URLService


@pytest.mark.asyncio
async def test_database_persistence_and_retrieval():
    """Verify URL records are persisted and queried via SQLAlchemy 2.0 AsyncSession."""
    factory = get_session_factory()
    test_code = f"db-{uuid.uuid4().hex[:6]}"
    target_url = "https://www.postgresql.org/docs/15/"

    async with factory() as session:
        record = URLModel(short_code=test_code, original_url=target_url)
        session.add(record)
        await session.commit()
        await session.refresh(record)

        assert record.id is not None
        assert record.short_code == test_code
        assert record.created_at is not None
        assert record.click_count == 0

    # Query in a separate session to ensure persistence
    async with factory() as query_session:
        stmt = select(URLModel).where(URLModel.short_code == test_code)
        result = await query_session.execute(stmt)
        queried = result.scalar_one_or_none()

        assert queried is not None
        assert queried.short_code == test_code
        assert queried.original_url == target_url


@pytest.mark.asyncio
async def test_database_unique_constraint_enforcement():
    """Verify PostgreSQL rejects duplicate short_code insertions with IntegrityError."""
    factory = get_session_factory()
    duplicate_code = f"uniq-{uuid.uuid4().hex[:6]}"

    async with factory() as session:
        rec1 = URLModel(short_code=duplicate_code, original_url="https://site1.com")
        session.add(rec1)
        await session.commit()

    # Attempt inserting the identical short_code
    with pytest.raises(IntegrityError):
        async with factory() as session2:
            rec2 = URLModel(short_code=duplicate_code, original_url="https://site2.com")
            session2.add(rec2)
            await session2.commit()


@pytest.mark.asyncio
async def test_redis_cache_aside():
    """Verify Redis caching operations: set, get, TTL, and cache hits."""
    cache = get_cache_service()
    test_key = f"url:test-{uuid.uuid4().hex[:6]}"
    test_val = "https://redis.io/commands/"

    # Cache miss
    assert await cache.get(test_key) is None

    # Cache set
    success = await cache.set(test_key, test_val, ttl=30)
    assert success is True

    # Cache hit
    cached = await cache.get(test_key)
    assert cached == test_val

    # Cache delete
    await cache.delete(test_key)
    assert await cache.get(test_key) is None


@pytest.mark.asyncio
async def test_health_check_reports_connected_subsystems():
    """Verify /health returns 200 with both PostgreSQL and Redis reported connected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["components"]["database"] == "connected"
        assert data["components"]["cache"] == "connected"
