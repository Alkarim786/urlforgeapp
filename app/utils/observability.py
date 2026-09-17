"""Observability: Correlation IDs, Structured JSON Logging, and Prometheus Metrics."""

import contextvars
import json
import logging
import time
from typing import Any, Optional
import uuid

# Request ID context variable for request-scoped correlation
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def get_current_request_id() -> str:
    """Return the current context request ID or generate a fallback."""
    req_id = request_id_ctx.get()
    return req_id if req_id else "system"


class StructuredJSONFormatter(logging.Formatter):
    """Logging formatter converting LogRecord instances into structured JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", get_current_request_id()),
        }

        # Include exception trace if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include custom extra metadata if passed
        for key, val in record.__dict__.items():
            if key not in logging.LogRecord.__dict__ and key not in log_entry:
                log_entry[key] = str(val)

        return json.dumps(log_entry, default=str)


# ==========================================
# In-Memory Lightweight Prometheus Exporter
# ==========================================
class PrometheusRegistry:
    """Zero-dependency Prometheus metrics collector and text exposition formatter."""

    def __init__(self):
        self._request_counts: dict[tuple[str, str, str], int] = {}
        self._request_durations: dict[str, list[float]] = {}
        self._cache_hits: int = 0
        self._cache_misses: int = 0
        self._redirect_counts: int = 0

    def record_request(self, method: str, path: str, status_code: int, duration_seconds: float) -> None:
        """Record HTTP request status and duration."""
        # Sanitize path to prevent cardinality explosion (e.g. /cplx_123 -> /{short_code})
        norm_path = path
        if path.startswith("/api/v1/urls/") and len(path.split("/")) == 5 and path.endswith("/analytics"):
            norm_path = "/api/v1/urls/{code}/analytics"
        elif path.startswith("/api/v1/urls/") and len(path.split("/")) == 5:
            norm_path = "/api/v1/urls/{code}"
        elif path not in ("/health", "/metrics", "/", "/docs", "/openapi.json", "/api/v1/urls"):
            norm_path = "/{short_code}"

        key = (method.upper(), norm_path, str(status_code))
        self._request_counts[key] = self._request_counts.get(key, 0) + 1

        if norm_path not in self._request_durations:
            self._request_durations[norm_path] = []
        if len(self._request_durations[norm_path]) < 500:  # Keep ring buffer
            self._request_durations[norm_path].append(duration_seconds)

    def record_cache_hit(self) -> None:
        self._cache_hits += 1

    def record_cache_miss(self) -> None:
        self._cache_misses += 1

    def record_redirect(self) -> None:
        self._redirect_counts += 1

    def generate_metrics_text(self) -> str:
        """Render metrics conforming to Prometheus 0.0.4 text format."""
        lines: list[str] = [
            "# HELP urlforge_http_requests_total Total number of HTTP requests processed",
            "# TYPE urlforge_http_requests_total counter",
        ]
        for (m, p, s), count in sorted(self._request_counts.items()):
            lines.append(f'urlforge_http_requests_total{{method="{m}",path="{p}",status="{s}"}} {count}')

        lines.extend([
            "",
            "# HELP urlforge_cache_hits_total Total Redis cache hits",
            "# TYPE urlforge_cache_hits_total counter",
            f"urlforge_cache_hits_total {self._cache_hits}",
            "",
            "# HELP urlforge_cache_misses_total Total Redis cache misses",
            "# TYPE urlforge_cache_misses_total counter",
            f"urlforge_cache_misses_total {self._cache_misses}",
            "",
            "# HELP urlforge_redirects_total Total URL redirects served",
            "# TYPE urlforge_redirects_total counter",
            f"urlforge_redirects_total {self._redirect_counts}",
            "",
            "# HELP urlforge_app_uptime_seconds Uptime indicator",
            "# TYPE urlforge_app_uptime_seconds gauge",
            f"urlforge_app_uptime_seconds {int(time.time())}",
            "",
        ])
        return "\n".join(lines)


# Singleton registry
metrics_registry = PrometheusRegistry()
