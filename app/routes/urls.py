"""URL API endpoints for URLForge.

Handles:
- POST /api/v1/urls (Shorten long URL, persist to PostgreSQL, cache in Redis)
- GET /api/v1/urls/{short_code} (Retrieve URL metadata)
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db_session
from app.schemas import URLCreateRequest, URLCreateResponse, URLMetadataResponse
from app.services.rate_limit_service import rate_limiter
from app.services.url_service import (
    CollisionRetryExhaustedError,
    DuplicateAliasError,
    URLService,
    get_url_service,
)

router = APIRouter(prefix="/api/v1/urls", tags=["URLs"])


@router.post(
    "",
    response_model=URLCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a shortened URL",
    description=(
        "Accepts a destination URL (HTTP or HTTPS) and returns a unique Base62 "
        "short code and clickable link. Persists to PostgreSQL with collision retry logic and caches to Redis."
    ),
    dependencies=[Depends(rate_limiter(scope="url_create"))],
)
async def create_url(
    payload: URLCreateRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
    service: URLService = Depends(get_url_service),
) -> URLCreateResponse:
    """Create short URL mapping and return 201 Created with Location header."""
    base_url = str(request.base_url).rstrip("/")

    try:
        result = await service.create_short_url(payload, session=session, base_url=base_url)
        response.headers["Location"] = result.short_url
        return result
    except DuplicateAliasError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(err),
        ) from err
    except CollisionRetryExhaustedError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="System was unable to allocate a unique short code. Please retry.",
        ) from err


@router.get(
    "/{short_code}",
    response_model=URLMetadataResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve URL metadata",
    description="Fetch creation timestamp, click statistics, and target destination for a given short code.",
)
async def get_url_metadata(
    short_code: str,
    session: AsyncSession = Depends(get_db_session),
    service: URLService = Depends(get_url_service),
) -> URLMetadataResponse:
    """Query metadata for an existing short code."""
    metadata = await service.get_metadata(short_code, session=session)
    if not metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Short code '{short_code}' was not found or has expired.",
        )
    return metadata
