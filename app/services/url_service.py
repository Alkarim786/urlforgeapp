"""URL business logic service layer backed by PostgreSQL and Redis.

Architecture:
- Asynchronous PostgreSQL persistence via SQLAlchemy 2.0 AsyncSession.
- Resilient Cache-Aside caching via Redis with automated fallback.
- ACID database unique constraint enforcement with collision retry loop.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db_session, get_session_factory
from app.models import URLModel
from app.schemas import URLCreateRequest, URLCreateResponse, URLMetadataResponse
from app.services.cache_service import CacheService, get_cache_service
from app.utils.short_code import generate_random_short_code

logger = logging.getLogger("urlforge.service")


class DuplicateAliasError(Exception):
    """Raised when a requested custom alias is already allocated."""
    pass


class CollisionRetryExhaustedError(Exception):
    """Raised if the generator cannot produce an unallocated code within retry limits."""
    pass


class URLService:
    """Service managing URL shortening lifecycle, PostgreSQL persistence, and Redis caching."""

    def __init__(
        self,
        session: Optional[AsyncSession] = None,
        cache: Optional[CacheService] = None,
    ):
        self._session = session
        self._cache = cache or get_cache_service()
        self._settings = get_settings()

    async def _get_or_create_session(self) -> AsyncSession:
        """Return the injected session or instantiate a new session from factory."""
        if self._session is not None:
            return self._session
        factory = get_session_factory()
        return factory()

    async def create_short_url(
        self,
        request: URLCreateRequest,
        session: Optional[AsyncSession] = None,
        base_url: Optional[str] = None,
    ) -> URLCreateResponse:
        """Create a shortened URL, persisting to PostgreSQL and priming Redis cache."""
        active_session = session or self._session
        should_close = False
        if active_session is None:
            active_session = await self._get_or_create_session()
            should_close = True

        original_url_str = str(request.url)
        app_base = (base_url or self._settings.APP_URL).rstrip("/")

        try:
            # 1. Custom Alias requested
            if request.custom_alias:
                alias = request.custom_alias
                record = URLModel(
                    short_code=alias,
                    original_url=original_url_str,
                )
                active_session.add(record)
                try:
                    await active_session.commit()
                    await active_session.refresh(record)
                except IntegrityError as err:
                    await active_session.rollback()
                    raise DuplicateAliasError(f"Custom alias '{alias}' is already in use.") from err

                # Prime Redis cache
                await self._cache.set(f"url:{alias}", original_url_str)

                return URLCreateResponse(
                    short_code=alias,
                    short_url=f"{app_base}/{alias}",
                    original_url=original_url_str,
                    created_at=record.created_at,
                )

            # 2. Automated Generation with Database Collision Retry Loop
            max_retries = self._settings.MAX_COLLISION_RETRIES
            code_len = self._settings.DEFAULT_SHORT_CODE_LENGTH

            for attempt in range(1, max_retries + 1):
                candidate_code = generate_random_short_code(length=code_len)
                record = URLModel(
                    short_code=candidate_code,
                    original_url=original_url_str,
                )
                active_session.add(record)
                try:
                    await active_session.commit()
                    await active_session.refresh(record)

                    # Successfully persisted to PostgreSQL -> Prime Redis
                    await self._cache.set(f"url:{candidate_code}", original_url_str)

                    return URLCreateResponse(
                        short_code=candidate_code,
                        short_url=f"{app_base}/{candidate_code}",
                        original_url=original_url_str,
                        created_at=record.created_at,
                    )
                except IntegrityError:
                    # Database UNIQUE constraint caught a collision!
                    await active_session.rollback()
                    logger.warning(
                        "Collision detected for short_code '%s' on attempt %d/%d; retrying...",
                        candidate_code,
                        attempt,
                        max_retries,
                    )
                    continue

            raise CollisionRetryExhaustedError(
                f"Failed to generate a unique short code after {max_retries} attempts."
            )
        finally:
            if should_close:
                await active_session.close()

    async def get_url_record(
        self,
        short_code: str,
        session: Optional[AsyncSession] = None,
    ) -> Optional[URLModel]:
        """Retrieve URL database model by short code."""
        active_session = session or self._session
        should_close = False
        if active_session is None:
            active_session = await self._get_or_create_session()
            should_close = True

        try:
            stmt = select(URLModel).where(URLModel.short_code == short_code)
            result = await active_session.execute(stmt)
            return result.scalar_one_or_none()
        finally:
            if should_close:
                await active_session.close()

    async def get_destination_url(
        self,
        short_code: str,
        session: Optional[AsyncSession] = None,
    ) -> Optional[str]:
        """Resolve destination URL using Cache-Aside pattern (Redis -> PostgreSQL -> Redis)."""
        # 1. Check Redis Cache
        cached_url = await self._cache.get(f"url:{short_code}")
        if cached_url:
            return cached_url

        # 2. Cache Miss -> Query PostgreSQL
        record = await self.get_url_record(short_code, session=session)
        if not record:
            return None

        # Check expiration if set
        if record.expires_at and record.expires_at < datetime.now(timezone.utc):
            return None

        # 3. Populate Redis Cache
        await self._cache.set(f"url:{short_code}", record.original_url)
        return record.original_url

    async def record_click(
        self,
        short_code: str,
        session: Optional[AsyncSession] = None,
    ) -> None:
        """Atomically increment the click count and update last_accessed_at."""
        active_session = session or self._session
        should_close = False
        if active_session is None:
            active_session = await self._get_or_create_session()
            should_close = True

        try:
            stmt = (
                update(URLModel)
                .where(URLModel.short_code == short_code)
                .values(
                    click_count=URLModel.click_count + 1,
                    last_accessed_at=datetime.now(timezone.utc),
                )
            )
            await active_session.execute(stmt)
            await active_session.commit()
        except Exception as err:
            logger.warning("Failed to increment click count for '%s': %s", short_code, err)
            await active_session.rollback()
        finally:
            if should_close:
                await active_session.close()

    async def get_metadata(
        self,
        short_code: str,
        session: Optional[AsyncSession] = None,
    ) -> Optional[URLMetadataResponse]:
        """Retrieve URL metadata view."""
        record = await self.get_url_record(short_code, session=session)
        if not record:
            return None

        return URLMetadataResponse(
            short_code=record.short_code,
            original_url=record.original_url,
            created_at=record.created_at,
            expires_at=record.expires_at,
            click_count=record.click_count,
            last_accessed_at=record.last_accessed_at,
        )


def get_url_service() -> URLService:
    """Dependency injection provider for URLService."""
    return URLService(cache=get_cache_service())
