"""Analytics API endpoint router."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.schemas import AnalyticsSummaryResponse
from app.services.analytics_service import AnalyticsService, get_analytics_service

router = APIRouter(prefix="/api/v1/urls", tags=["Analytics"])


@router.get(
    "/{short_code}/analytics",
    response_model=AnalyticsSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Fetch analytics and click traffic breakdown",
    description="Returns aggregate click metrics, top referrers, browser breakdown, and recent events for a given short code.",
)
async def get_url_analytics(
    short_code: str,
    session: AsyncSession = Depends(get_db_session),
    service: AnalyticsService = Depends(get_analytics_service),
) -> AnalyticsSummaryResponse:
    """Retrieve detailed click statistics and traffic demographics for a short code."""
    result = await service.get_analytics(short_code, session=session)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Short code '{short_code}' was not found or has expired.",
        )
    return result
