"""Analytics and click logging service layer."""

import logging
from typing import Optional
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session, get_session_factory
from app.models import ClickEventModel, URLModel
from app.schemas import AnalyticsSummaryResponse, ClickEventDetail, MetricBreakdown
from app.utils.security import classify_user_agent, hash_ip

logger = logging.getLogger("urlforge.analytics")


class AnalyticsService:
    """Handles event recording and aggregated statistical queries for URL redirects."""

    def __init__(self, session: Optional[AsyncSession] = None):
        self._session = session

    async def log_click(
        self,
        short_code: str,
        referrer: Optional[str] = None,
        user_agent: Optional[str] = None,
        client_ip: Optional[str] = None,
        session: Optional[AsyncSession] = None,
    ) -> None:
        """Record an individual click event asynchronously with privacy hashing."""
        session_factory = get_session_factory()
        async with session_factory() as active_session:
            try:
                # 1. Resolve URL ID
                url_stmt = select(URLModel.id).where(URLModel.short_code == short_code)
                url_res = await active_session.execute(url_stmt)
                url_id = url_res.scalar_one_or_none()

                if not url_id:
                    logger.warning("Could not log click: short_code '%s' not found.", short_code)
                    return

                # 2. Privacy-preserving anonymization
                client_hash = hash_ip(client_ip)
                ua_family = classify_user_agent(user_agent)
                clean_ref = referrer.strip()[:500] if referrer else None

                # 3. Insert click event
                event = ClickEventModel(
                    url_id=url_id,
                    referrer=clean_ref or "Direct / None",
                    user_agent_family=ua_family,
                    ip_hash=client_hash,
                )
                active_session.add(event)
                await active_session.commit()
            except Exception as err:
                logger.error("Failed to log click event for '%s': %s", short_code, err)
                await active_session.rollback()

    async def get_analytics(
        self,
        short_code: str,
        session: Optional[AsyncSession] = None,
    ) -> Optional[AnalyticsSummaryResponse]:
        """Aggregate clicks, unique visitors, referrers, and browser families."""
        active_session = session or self._session
        should_close = False
        if active_session is None:
            session_factory = get_session_factory()
            active_session = session_factory()
            should_close = True

        try:
            # Query URL parent record
            stmt = select(URLModel).where(URLModel.short_code == short_code)
            res = await active_session.execute(stmt)
            url_record = res.scalar_one_or_none()
            if not url_record:
                return None

            # Total clicks
            total_clicks = url_record.click_count

            # Unique visitors
            unique_stmt = (
                select(func.count(func.distinct(ClickEventModel.ip_hash)))
                .where(ClickEventModel.url_id == url_record.id)
            )
            unique_res = await active_session.execute(unique_stmt)
            unique_visitors = unique_res.scalar_one() or (1 if total_clicks > 0 else 0)

            # Referrer breakdown
            ref_stmt = (
                select(ClickEventModel.referrer, func.count(ClickEventModel.id))
                .where(ClickEventModel.url_id == url_record.id)
                .group_by(ClickEventModel.referrer)
                .order_by(desc(func.count(ClickEventModel.id)))
                .limit(5)
            )
            ref_res = await active_session.execute(ref_stmt)
            referrers = []
            for ref, count in ref_res.fetchall():
                pct = round((count / total_clicks * 100), 1) if total_clicks > 0 else 0.0
                referrers.append(MetricBreakdown(label=ref or "Direct", count=count, percentage=pct))

            # Browser / device breakdown
            browser_stmt = (
                select(ClickEventModel.user_agent_family, func.count(ClickEventModel.id))
                .where(ClickEventModel.url_id == url_record.id)
                .group_by(ClickEventModel.user_agent_family)
                .order_by(desc(func.count(ClickEventModel.id)))
                .limit(5)
            )
            browser_res = await active_session.execute(browser_stmt)
            browsers = []
            for b_name, count in browser_res.fetchall():
                pct = round((count / total_clicks * 100), 1) if total_clicks > 0 else 0.0
                browsers.append(MetricBreakdown(label=b_name or "Unknown", count=count, percentage=pct))

            # Recent 10 events
            recent_stmt = (
                select(ClickEventModel)
                .where(ClickEventModel.url_id == url_record.id)
                .order_by(desc(ClickEventModel.clicked_at))
                .limit(10)
            )
            recent_res = await active_session.execute(recent_stmt)
            recent_events = [
                ClickEventDetail(
                    clicked_at=e.clicked_at,
                    referrer=e.referrer,
                    user_agent_family=e.user_agent_family,
                )
                for e in recent_res.scalars().all()
            ]

            return AnalyticsSummaryResponse(
                short_code=url_record.short_code,
                original_url=url_record.original_url,
                total_clicks=total_clicks,
                unique_visitors=unique_visitors,
                created_at=url_record.created_at,
                last_accessed_at=url_record.last_accessed_at,
                referrers=referrers,
                browsers=browsers,
                recent_events=recent_events,
            )
        finally:
            if should_close:
                await active_session.close()


def get_analytics_service() -> AnalyticsService:
    """FastAPI dependency provider for AnalyticsService."""
    return AnalyticsService()
