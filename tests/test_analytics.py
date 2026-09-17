"""Integration and Unit Tests for Phase 7: Analytics & Click Tracking.

Validates:
- GET /api/v1/urls/{short_code}/analytics
- Aggregation of total clicks and unique visitors (privacy-preserving IP hash)
- Breakdown of top referrers
- Breakdown of browser families
- Recent event timeline
- 404 handling for unknown short codes
"""

import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.services.analytics_service import AnalyticsService, get_analytics_service


@pytest.mark.asyncio
async def test_analytics_initial_state():
    """Verify that a freshly created short URL starts with 0 clicks and empty breakdowns."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        alias = f"an_{uuid.uuid4().hex[:6]}"
        target = "https://example.com/fresh-link"

        create_res = await client.post(
            "/api/v1/urls",
            json={"url": target, "custom_alias": alias},
        )
        assert create_res.status_code == 201

        analytics_res = await client.get(f"/api/v1/urls/{alias}/analytics")
        assert analytics_res.status_code == 200
        data = analytics_res.json()

        assert data["short_code"] == alias
        assert data["original_url"] == target
        assert data["total_clicks"] == 0
        assert data["unique_visitors"] == 0
        assert len(data["referrers"]) == 0
        assert len(data["browsers"]) == 0
        assert len(data["recent_events"]) == 0


@pytest.mark.asyncio
async def test_analytics_click_logging_and_aggregation():
    """Verify that logging clicks aggregates referrers, browsers, and unique visitors."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        alias = f"click_{uuid.uuid4().hex[:6]}"
        target = "https://news.ycombinator.com"

        create_res = await client.post(
            "/api/v1/urls",
            json={"url": target, "custom_alias": alias},
        )
        assert create_res.status_code == 201

        # Simulate 2 clicks directly via AnalyticsService with distinct referrers & browsers
        analytics_svc = get_analytics_service()

        # Direct log 1: Chrome from GitHub
        await analytics_svc.log_click(
            short_code=alias,
            referrer="https://github.com",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
            client_ip="192.168.1.100",
        )

        # Direct log 2: Firefox from Twitter
        await analytics_svc.log_click(
            short_code=alias,
            referrer="https://t.co",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/115.0",
            client_ip="192.168.1.101",
        )

        # Trigger redirect to increment click count
        await client.get(f"/{alias}", follow_redirects=False)

        # Fetch aggregated analytics
        res = await client.get(f"/api/v1/urls/{alias}/analytics")
        assert res.status_code == 200
        stats = res.json()

        assert stats["short_code"] == alias
        assert stats["total_clicks"] >= 1
        assert stats["unique_visitors"] >= 1

        # Verify referrers present
        referrer_labels = [r["label"] for r in stats["referrers"]]
        assert any("github" in r or "t.co" in r for r in referrer_labels)

        # Verify browsers categorized
        browser_labels = [b["label"] for b in stats["browsers"]]
        assert any("Chrome" in b or "Firefox" in b for b in browser_labels)

        # Verify recent events
        assert len(stats["recent_events"]) >= 1


@pytest.mark.asyncio
async def test_analytics_not_found():
    """Verify that querying analytics for a non-existent code returns 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/urls/non_existent_code_xyz/analytics")
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()
