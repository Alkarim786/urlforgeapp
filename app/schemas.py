"""Pydantic schemas for request validation and response serialization.

Follows strict input validation principles:
- Only HTTP and HTTPS schemes are permitted (rejects javascript:, data:, file:, etc.)
- Length bounds prevent buffer and memory denial-of-service (max 2048 chars)
- Custom alias constraints ensure URL-safe tokens
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class URLCreateRequest(BaseModel):
    """Schema for incoming URL shortening requests."""

    url: HttpUrl = Field(
        ...,
        description="The long destination URL to shorten. Must be valid HTTP or HTTPS.",
        examples=["https://example.com/deep/resource/path?query=1"],
    )
    custom_alias: Optional[str] = Field(
        None,
        min_length=4,
        max_length=16,
        description="Optional custom short code alias requested by client.",
        examples=["my-custom-link"],
    )

    @field_validator("url")
    @classmethod
    def validate_url_scheme(cls, v: HttpUrl) -> HttpUrl:
        """Enforce strict HTTP/HTTPS protocol schemes to defend against SSRF and script injection."""
        scheme = v.scheme.lower()
        if scheme not in ("http", "https"):
            raise ValueError(f"Scheme '{scheme}' is not allowed. Only 'http' and 'https' are supported.")
        if len(str(v)) > 2048:
            raise ValueError("URL exceeds maximum permitted length of 2048 characters.")
        return v

    @field_validator("custom_alias")
    @classmethod
    def validate_custom_alias(cls, v: Optional[str]) -> Optional[str]:
        """Validate that custom alias contains only URL-safe alphanumeric characters and hyphens."""
        if v is None:
            return v
        v_clean = v.strip()
        if not v_clean:
            return None
        if not v_clean.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Custom alias must contain only alphanumeric characters, hyphens, or underscores.")
        return v_clean


class URLCreateResponse(BaseModel):
    """Schema returned after a short URL is successfully generated."""

    short_code: str = Field(..., description="The unique short identifier token.")
    short_url: str = Field(..., description="The full, clickable shortened URL.")
    original_url: str = Field(..., description="The original long destination URL.")
    created_at: datetime = Field(..., description="Creation timestamp in UTC.")

    model_config = ConfigDict(from_attributes=True)


class URLMetadataResponse(BaseModel):
    """Schema returned when querying URL details and metadata."""

    short_code: str
    original_url: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    click_count: int = 0
    last_accessed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
