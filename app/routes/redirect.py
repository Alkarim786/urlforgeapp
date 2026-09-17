"""HTTP Redirection Router for URLForge.

Handles:
- GET /{short_code} (Redirect to destination URL with HTTP 307/301/302)
- High-performance Cache-Aside lookup directly from Redis
- Asynchronous click counter incrementation via FastAPI BackgroundTasks
"""

import logging
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.services.analytics_service import AnalyticsService, get_analytics_service
from app.services.url_service import URLService, get_url_service

logger = logging.getLogger("urlforge.redirect")

router = APIRouter(tags=["Redirect"])

RESERVED_PREFIXES = {
    "health",
    "docs",
    "redoc",
    "openapi.json",
    "api",
    "metrics",
    "favicon.ico",
    "robots.txt",
    "static",
}


@router.get(
    "/r/{short_code}",
    response_class=RedirectResponse,
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    include_in_schema=True,
)
@router.get(
    "/{short_code}",
    response_class=RedirectResponse,
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    summary="Redirect short code to destination URL",
    description=(
        "Resolves the short code against Redis cache (falling back to PostgreSQL) "
        "and immediately redirects the client using HTTP 307 Temporary Redirect. "
        "Asynchronously increments the click counter in the background."
    ),
    responses={
        307: {"description": "Redirecting to original long destination URL"},
        301: {"description": "Permanent redirect to original long destination URL"},
        302: {"description": "Found temporary redirect"},
        404: {"description": "Short code does not exist or has expired"},
    },
)
async def redirect_to_long_url(
    short_code: str,
    request: Request,
    background_tasks: BackgroundTasks,
    redirect_code: Optional[int] = Query(
        default=status.HTTP_307_TEMPORARY_REDIRECT,
        description="HTTP redirect status code (301, 302, 307, or 308). Defaults to 307.",
    ),
    session: AsyncSession = Depends(get_db_session),
    service: URLService = Depends(get_url_service),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
) -> RedirectResponse:
    """Redirect client to destination URL and trigger background click recording."""
    clean_code = short_code.strip()

    # Avoid intercepting system routes
    if clean_code.lower() in RESERVED_PREFIXES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Path '{clean_code}' is reserved.",
        )

    # 1. Resolve destination URL (Cache-Aside: Redis -> PG -> Redis)
    destination_url = await service.get_destination_url(clean_code, session=session)
    if not destination_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Short code '{clean_code}' was not found or has expired.",
        )

    # 2. Asynchronously increment click count and detailed analytics in background
    client_ip = request.client.host if request.client else None
    referrer = request.headers.get("referer")
    user_agent = request.headers.get("user-agent")

    background_tasks.add_task(service.record_click, clean_code)
    background_tasks.add_task(
        analytics_service.log_click,
        short_code=clean_code,
        referrer=referrer,
        user_agent=user_agent,
        client_ip=client_ip,
    )

    # 3. Validate requested redirect HTTP code
    valid_redirect_codes = {
        status.HTTP_301_MOVED_PERMANENTLY,
        status.HTTP_302_FOUND,
        status.HTTP_307_TEMPORARY_REDIRECT,
        status.HTTP_308_PERMANENT_REDIRECT,
    }
    http_status = redirect_code if redirect_code in valid_redirect_codes else status.HTTP_307_TEMPORARY_REDIRECT

    # Return redirect response with Cache-Control headers to ensure browser hits server for analytics
    response = RedirectResponse(url=destination_url, status_code=http_status)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
