"""Health and readiness check probes.

Provides deep service health verification for orchestration, load balancers,
and monitoring probes (e.g., Kubernetes liveness/readiness, Docker healthchecks).
Monitors database and Redis connection health.
"""

from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter, Response, status
from sqlalchemy import text
from app.config import get_settings
from app.database import get_session_factory
from app.services.cache_service import get_cache_service

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check probe",
    response_description="Service status and subsystem operational metadata",
)
async def health_check(response: Response) -> Dict[str, Any]:
    """Return application and component health information."""
    settings = get_settings()

    # Check Database connection
    db_status = "unknown"
    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception as err:
        db_status = f"unhealthy: {err}"

    # Check Redis connection
    redis_status = "unknown"
    try:
        cache = get_cache_service()
        pong = await cache.ping()
        redis_status = "connected" if pong else "disconnected"
    except Exception as err:
        redis_status = f"unhealthy: {err}"

    overall_ok = db_status == "connected" and redis_status == "connected"
    if not overall_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if overall_ok else "degraded",
        "service": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.3.0",
        "components": {
            "database": db_status,
            "cache": redis_status,
        },
    }
