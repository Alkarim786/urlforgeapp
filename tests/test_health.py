"""Tests for root and health check endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_root_endpoint():
    """Verify GET / returns 200 OK and expected welcoming payload."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert "message" in data
        assert data["health_url"] == "/health"
        assert data["docs_url"] == "/docs"


@pytest.mark.asyncio
async def test_health_endpoint():
    """Verify GET /health returns 200 OK and proper service metadata."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "URLForge"
        assert "timestamp" in data
        assert "environment" in data
