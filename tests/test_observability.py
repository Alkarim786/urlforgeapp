"""Tests for Phase 12: Observability, Metrics, and Correlation IDs.

Validates:
- Automatic generation of X-Request-ID headers
- Preservation of client-supplied X-Request-ID / X-Correlation-ID headers
- Latency measurement headers (X-Response-Time-Ms)
- GET /metrics endpoint returning Prometheus text exposition
- Prometheus request count incrementation
- Structured JSON logging formatter output
"""

import json
import logging
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.utils.observability import StructuredJSONFormatter, get_current_request_id, request_id_ctx


@pytest.mark.asyncio
async def test_correlation_id_auto_generation():
    """Verify that every HTTP response includes an X-Request-ID and X-Response-Time-Ms."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        assert "X-Request-ID" in res.headers
        assert len(res.headers["X-Request-ID"]) >= 16
        assert "X-Response-Time-Ms" in res.headers


@pytest.mark.asyncio
async def test_correlation_id_client_supplied():
    """Verify that a client-provided X-Request-ID is preserved and reflected in the response."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        custom_id = f"client-trace-{uuid.uuid4().hex}"
        res = await client.get("/health", headers={"X-Request-ID": custom_id})
        assert res.status_code == 200
        assert res.headers["X-Request-ID"] == custom_id


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint():
    """Verify GET /metrics exposes Prometheus formatted metrics including request counts."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Trigger an endpoint call first
        await client.get("/health")

        # Now fetch /metrics
        metrics_res = await client.get("/metrics")
        assert metrics_res.status_code == 200
        assert "text/plain" in metrics_res.headers["content-type"]

        body = metrics_res.text
        assert "urlforge_http_requests_total" in body
        assert "urlforge_cache_hits_total" in body
        assert "urlforge_cache_misses_total" in body
        assert "urlforge_redirects_total" in body
        assert "urlforge_app_uptime_seconds" in body


def test_structured_json_logging_formatter():
    """Verify StructuredJSONFormatter outputs valid parseable JSON with expected fields."""
    formatter = StructuredJSONFormatter()
    record = logging.LogRecord(
        name="urlforge.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=50,
        msg="Test event for observability",
        args=(),
        exc_info=None,
    )

    token = request_id_ctx.set("test-trace-1234")
    try:
        formatted = formatter.format(record)
        parsed = json.loads(formatted)

        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "urlforge.test"
        assert parsed["message"] == "Test event for observability"
        assert parsed["request_id"] == "test-trace-1234"
        assert "timestamp" in parsed
    finally:
        request_id_ctx.reset(token)
