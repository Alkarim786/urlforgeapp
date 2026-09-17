"""Tests for URL shortening, validation, Base62 encoding, and metadata retrieval."""

import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.utils.short_code import (
    BASE62_ALPHABET,
    decode_base62,
    encode_base62,
    generate_random_short_code,
)


# ==========================================
# Unit Tests: Base62 Utilities
# ==========================================

def test_base62_encoding_decoding_roundtrip():
    """Verify bi-directional correctness of Base62 encoding and decoding."""
    test_numbers = [0, 1, 61, 62, 63, 1000, 3521614606208, 999999999999]
    for num in test_numbers:
        encoded = encode_base62(num)
        decoded = decode_base62(encoded)
        assert decoded == num, f"Roundtrip failed for {num}: got {decoded} via {encoded}"


def test_base62_character_set():
    """Verify that generated random short codes strictly use Base62 characters."""
    code = generate_random_short_code(length=7)
    assert len(code) == 7
    for char in code:
        assert char in BASE62_ALPHABET


def test_base62_negative_input_raises_error():
    """Negative integers must raise ValueError."""
    with pytest.raises(ValueError):
        encode_base62(-5)


def test_base62_invalid_decode_character():
    """Invalid characters (e.g. $, @, !, emojis) must be rejected during decoding."""
    with pytest.raises(ValueError):
        decode_base62("abc$123")


# ==========================================
# Integration Tests: URL API Endpoints
# ==========================================

@pytest.mark.asyncio
async def test_create_short_url_success():
    """POST /api/v1/urls with valid URL returns 201 Created with Location header."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        long_url = "https://example.com/engineering/high-concurrency-systems"
        response = await client.post("/api/v1/urls", json={"url": long_url})

        assert response.status_code == 201
        data = response.json()
        assert "short_code" in data
        assert len(data["short_code"]) == 7
        assert "short_url" in data
        assert data["short_code"] in data["short_url"]
        assert data["original_url"] == long_url
        assert "created_at" in data

        # Check HTTP Location header
        assert response.headers.get("Location") == data["short_url"]


@pytest.mark.asyncio
async def test_create_short_url_with_custom_alias():
    """Clients can specify a valid custom alias if available."""
    unique_alias = f"alias-{uuid.uuid4().hex[:8]}"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "url": "https://fastapi.tiangolo.com",
            "custom_alias": unique_alias,
        }
        response = await client.post("/api/v1/urls", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["short_code"] == unique_alias
        assert data["short_url"].endswith(f"/{unique_alias}")


@pytest.mark.asyncio
async def test_duplicate_custom_alias_returns_409_conflict():
    """Re-using an allocated custom alias must return 409 Conflict."""
    unique_alias = f"dup-{uuid.uuid4().hex[:8]}"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "url": "https://python.org",
            "custom_alias": unique_alias,
        }
        # First creation succeeds
        res1 = await client.post("/api/v1/urls", json=payload)
        assert res1.status_code == 201

        # Second creation with identical alias must conflict
        res2 = await client.post("/api/v1/urls", json=payload)
        assert res2.status_code == 409
        assert "already in use" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_url_schemes_rejected():
    """Non-HTTP/HTTPS schemes (ftp://, javascript:, data:) must be rejected with 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        invalid_schemes = [
            "ftp://ftp.example.com/files",
            "javascript:alert(document.cookie)",
            "file:///etc/passwd",
        ]
        for bad_url in invalid_schemes:
            response = await client.post("/api/v1/urls", json={"url": bad_url})
            assert response.status_code == 422, f"Failed to reject: {bad_url}"


@pytest.mark.asyncio
async def test_malformed_url_rejected():
    """Non-URL strings must return 422 Unprocessable Entity."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/urls", json={"url": "not-a-valid-url-at-all"})
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_url_metadata_success():
    """GET /api/v1/urls/{short_code} returns metadata for an active link."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create URL
        long_url = "https://redis.io/documentation"
        res = await client.post("/api/v1/urls", json={"url": long_url})
        assert res.status_code == 201
        code = res.json()["short_code"]

        # 2. Query metadata
        meta_res = await client.get(f"/api/v1/urls/{code}")
        assert meta_res.status_code == 200
        meta = meta_res.json()
        assert meta["short_code"] == code
        assert meta["original_url"] == long_url
        assert meta["click_count"] == 0
        assert "created_at" in meta


@pytest.mark.asyncio
async def test_get_url_metadata_not_found():
    """GET /api/v1/urls/{short_code} with non-existent code returns 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/urls/nonExistent99")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
