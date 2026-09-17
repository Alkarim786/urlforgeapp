"""Edge cases, boundary conditions, and cache invalidation tests for Phase 10.

Validates:
- Complex destination URLs (ports, complex query params, anchors)
- Maximum URL length constraint (2048 characters allowed, >2048 rejected)
- Full lifecycle: Create -> Cache hit -> Delete -> Cache eviction -> 404 verification
- Deleting non-existent short code yields 404
- Custom alias validation boundaries (min 4, max 16, invalid symbols)
"""

import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_complex_url_with_query_and_port():
    """Verify URLs with non-standard ports and complex query parameters are preserved without truncation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        complex_url = "https://sub.domain.example.org:8443/api/v2/items?filter=active&sort=desc&tag=c%2B%2B#section-header"
        alias = f"cplx_{uuid.uuid4().hex[:6]}"

        create_res = await client.post(
            "/api/v1/urls",
            json={"url": complex_url, "custom_alias": alias},
        )
        assert create_res.status_code == 201

        # Retrieve metadata
        meta_res = await client.get(f"/api/v1/urls/{alias}")
        assert meta_res.status_code == 200
        assert meta_res.json()["original_url"] == complex_url

        # Check redirect target
        redir_res = await client.get(f"/{alias}", follow_redirects=False)
        assert redir_res.status_code == 307
        assert redir_res.headers["location"] == complex_url


@pytest.mark.asyncio
async def test_max_url_length_boundary():
    """Verify URL length boundary (allows up to 2048, rejects over 2048)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        base_prefix = "https://example.com/search?q="
        padding = "a" * (2048 - len(base_prefix))
        valid_long_url = base_prefix + padding
        assert len(valid_long_url) == 2048

        # Exactly 2048 chars should succeed
        res_ok = await client.post(
            "/api/v1/urls",
            json={"url": valid_long_url},
        )
        assert res_ok.status_code == 201

        # 2049 chars must be rejected with 422
        invalid_oversized_url = valid_long_url + "x"
        res_fail = await client.post(
            "/api/v1/urls",
            json={"url": invalid_oversized_url},
        )
        assert res_fail.status_code == 422


@pytest.mark.asyncio
async def test_delete_url_and_cache_eviction():
    """Verify DELETE /api/v1/urls/{short_code} removes record and purges Redis cache."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        alias = f"del_{uuid.uuid4().hex[:6]}"
        target = "https://kernel.org/"

        # 1. Create short code
        create_res = await client.post(
            "/api/v1/urls",
            json={"url": target, "custom_alias": alias},
        )
        assert create_res.status_code == 201

        # 2. Hit redirect to prime Redis cache
        redir1 = await client.get(f"/{alias}", follow_redirects=False)
        assert redir1.status_code == 307

        # 3. Delete the short code
        del_res = await client.delete(f"/api/v1/urls/{alias}")
        assert del_res.status_code == 204

        # 4. Subsequent redirect must be 404 (evicted from Redis and PostgreSQL)
        redir2 = await client.get(f"/{alias}", follow_redirects=False)
        assert redir2.status_code == 404

        # 5. Metadata query must be 404
        meta_res = await client.get(f"/api/v1/urls/{alias}")
        assert meta_res.status_code == 404

        # 6. Deleting already deleted code must return 404
        del_again = await client.delete(f"/api/v1/urls/{alias}")
        assert del_again.status_code == 404


@pytest.mark.asyncio
async def test_custom_alias_length_and_character_boundaries():
    """Verify custom alias rules: min 4 chars, max 16 chars, only alphanumeric / hyphens / underscores."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Too short (<4 chars)
        res_short = await client.post(
            "/api/v1/urls",
            json={"url": "https://python.org", "custom_alias": "abc"},
        )
        assert res_short.status_code == 422

        # Too long (>16 chars)
        res_long = await client.post(
            "/api/v1/urls",
            json={"url": "https://python.org", "custom_alias": "a" * 17},
        )
        assert res_long.status_code == 422

        # Invalid characters (e.g. spaces or dollar signs)
        res_invalid = await client.post(
            "/api/v1/urls",
            json={"url": "https://python.org", "custom_alias": "bad$alias"},
        )
        assert res_invalid.status_code == 422
