"""Idempotency management service to ensure safe HTTP retry semantics.

Guarantees that repeated POST requests with an 'Idempotency-Key' header:
1. Return identical results without duplicating side effects or database rows.
2. Flag replays via 'Idempotency-Replay: true' HTTP response header.
3. Detect payload mismatches and reject with HTTP 422.
"""

import hashlib
import json
import logging
from typing import Any, Optional, Tuple
from fastapi import HTTPException, status
from redis.exceptions import RedisError

from app.services.cache_service import CacheService, get_cache_service

logger = logging.getLogger("urlforge.idempotency")

# In-memory fallback for idempotency records if Redis is temporarily offline
_in_memory_idempotency: dict[str, dict[str, Any]] = {}


class IdempotencyService:
    """Provides storage, lookup, and replay for idempotent API mutations."""

    def __init__(self, cache_service: Optional[CacheService] = None):
        self._cache = cache_service or get_cache_service()
        self._ttl_seconds = 86400  # 24-hour replay window

    @staticmethod
    def compute_payload_hash(payload_dict: dict[str, Any]) -> str:
        """Deterministically hash the normalized request payload."""
        serialized = json.dumps(payload_dict, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    async def get_saved_response(
        self,
        key: str,
        current_payload_hash: str,
    ) -> Optional[dict[str, Any]]:
        """Retrieve cached response if key exists.

        Raises HTTPException(422) if the idempotency key is reused with different payload data.
        """
        storage_key = f"idempotency:{key}"
        data_str: Optional[str] = None

        try:
            client = self._cache.get_client()
            data_str = await client.get(storage_key)
        except (RedisError, OSError) as err:
            logger.warning("Redis read failed for idempotency key '%s': %s", key, err)

        if not data_str and storage_key in _in_memory_idempotency:
            record = _in_memory_idempotency[storage_key]
        elif data_str:
            try:
                record = json.loads(data_str)
            except Exception:
                record = None
        else:
            record = None

        if not record:
            return None

        # Verify payload consistency
        saved_hash = record.get("payload_hash")
        if saved_hash and saved_hash != current_payload_hash:
            status_code_422 = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
            raise HTTPException(
                status_code=status_code_422,
                detail="Idempotency key has already been used with a different request payload.",
            )

        return record.get("response_data")

    async def store_response(
        self,
        key: str,
        payload_hash: str,
        response_data: dict[str, Any],
        status_code: int = 201,
    ) -> None:
        """Store the successful response against the idempotency key."""
        storage_key = f"idempotency:{key}"
        record = {
            "payload_hash": payload_hash,
            "status_code": status_code,
            "response_data": response_data,
        }
        serialized = json.dumps(record, default=str)

        try:
            client = self._cache.get_client()
            await client.set(storage_key, serialized, ex=self._ttl_seconds)
        except (RedisError, OSError) as err:
            logger.warning("Redis store failed for idempotency key '%s': %s", key, err)

        # Also populate in-memory fallback
        _in_memory_idempotency[storage_key] = record


def get_idempotency_service() -> IdempotencyService:
    """Dependency provider for IdempotencyService."""
    return IdempotencyService()
