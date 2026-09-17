"""Prometheus metrics exporter route."""

from fastapi import APIRouter, Response, status
from app.utils.observability import metrics_registry

router = APIRouter(tags=["Observability"])


@router.get(
    "/metrics",
    status_code=status.HTTP_200_OK,
    summary="Prometheus Metrics",
    description="Prometheus text-format metrics exporter for platform observability and Grafana scraping.",
    response_class=Response,
)
async def get_metrics() -> Response:
    """Return standard Prometheus text metrics."""
    body = metrics_registry.generate_metrics_text()
    return Response(
        content=body,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
