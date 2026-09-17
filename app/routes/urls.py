"""URL API endpoints for URLForge.

Handles:
- POST /api/v1/urls (Shorten long URL, persist to PostgreSQL, cache in Redis)
- GET /api/v1/urls/{short_code} (Retrieve URL metadata)
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db_session
from app.schemas import URLCreateRequest, URLCreateResponse, URLMetadataResponse
from app.services.idempotency_service import IdempotencyService, get_idempotency_service
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
    idempotency_service: IdempotencyService = Depends(get_idempotency_service),
) -> URLCreateResponse:
    """Create short URL mapping and return 201 Created with Location header.

    Supports optional 'Idempotency-Key' header to guarantee safe network retries.
    """
    base_url = str(request.base_url).rstrip("/")
    idempotency_key = request.headers.get("idempotency-key")

    payload_hash = None
    if idempotency_key:
        payload_hash = idempotency_service.compute_payload_hash(payload.model_dump())
        cached_data = await idempotency_service.get_saved_response(idempotency_key, payload_hash)
        if cached_data:
            response.headers["Idempotency-Replay"] = "true"
            response.headers["Location"] = cached_data["short_url"]
            return URLCreateResponse(**cached_data)

    try:
        result = await service.create_short_url(payload, session=session, base_url=base_url)
        response.headers["Location"] = result.short_url

        if idempotency_key and payload_hash:
            await idempotency_service.store_response(
                key=idempotency_key,
                payload_hash=payload_hash,
                response_data=result.model_dump(),
            )

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


@router.delete(
    "/{short_code}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a shortened URL",
    description="Deletes short code from PostgreSQL database and evicts from Redis cache.",
)
async def delete_url(
    short_code: str,
    session: AsyncSession = Depends(get_db_session),
    service: URLService = Depends(get_url_service),
) -> None:
    """Delete short URL mapping."""
    deleted = await service.delete_url(short_code, session=session)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Short code '{short_code}' was not found.",
        )

