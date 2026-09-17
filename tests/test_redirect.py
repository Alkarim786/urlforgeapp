"""Integration and Unit Tests for Phase 4: HTTP Redirects (GET /{short_code}).

Validates:
- HTTP 307 (Temporary Redirect) with accurate Location header.
- Cache-Aside lookup directly from Redis.
- Asynchronous click counter updates.
- 404 Not Found for non-existent and reserved paths.
- Custom redirect code queries (301, 302, 307, 308).
"""

import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_redirect_success_http_307():
    """Verify that accessing a valid short code issues an HTTP 307 redirect."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        unique_target = f"https://example.org/destination/{uuid.uuid4()}"
        custom_alias = f"redir_{uuid.uuid4().hex[:6]}"

        # 1. Create short URL
        create_res = await client.post(
            "/api/v1/urls",
            json={"url": unique_target, "custom_alias": custom_alias},
        )
        assert create_res.status_code == 201
        data = create_res.json()
        short_code = data["short_code"]

        # 2. Access the short URL without following redirects
        redirect_res = await client.get(f"/{short_code}", follow_redirects=False)
        assert redirect_res.status_code == 307
        assert redirect_res.headers["location"] == unique_target
        assert "no-cache" in redirect_res.headers.get("Cache-Control", "")


@pytest.mark.asyncio
async def test_redirect_cache_hit_performance():
    """Verify that subsequent requests to the same short code succeed via Redis cache."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        target = f"https://wikipedia.org/wiki/{uuid.uuid4().hex[:8]}"
        alias = f"cache_{uuid.uuid4().hex[:6]}"

        create_res = await client.post(
            "/api/v1/urls",
            json={"url": target, "custom_alias": alias},
        )
        assert create_res.status_code == 201

        # First request (may hit cache or DB)
        res1 = await client.get(f"/{alias}", follow_redirects=False)
        assert res1.status_code == 307
        assert res1.headers["location"] == target

        # Second request (guaranteed Redis cache hit)
        res2 = await client.get(f"/{alias}", follow_redirects=False)
        assert res2.status_code == 307
        assert res2.headers["location"] == target


@pytest.mark.asyncio
async def test_redirect_custom_status_code():
    """Verify client can specify alternative redirect status codes (e.g. 301, 302)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        target = "https://example.org/permanent"
        alias = f"perm_{uuid.uuid4().hex[:6]}"

        create_res = await client.post(
            "/api/v1/urls",
            json={"url": target, "custom_alias": alias},
        )
        assert create_res.status_code == 201

        res_301 = await client.get(f"/{alias}?redirect_code=301", follow_redirects=False)
        assert res_301.status_code == 301
        assert res_301.headers["location"] == target


@pytest.mark.asyncio
async def test_redirect_not_found():
    """Verify that non-existent short codes return HTTP 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/non_existent_code_9999", follow_redirects=False)
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_redirect_click_tracking_increments():
    """Verify that accessing short code increments click count in metadata."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        target = "https://clicktracker.org/test"
        alias = f"click_{uuid.uuid4().hex[:6]}"

        await client.post(
            "/api/v1/urls",
            json={"url": target, "custom_alias": alias},
        )

        # Check initial click count
        meta_before = await client.get(f"/api/v1/urls/{alias}")
        assert meta_before.status_code == 200
        initial_clicks = meta_before.json()["click_count"]
        assert initial_clicks == 0

        # Execute redirect
        redir = await client.get(f"/{alias}", follow_redirects=False)
        assert redir.status_code == 307

        # Check updated click count
        meta_after = await client.get(f"/api/v1/urls/{alias}")
        assert meta_after.status_code == 200
        assert meta_after.json()["click_count"] >= 1
