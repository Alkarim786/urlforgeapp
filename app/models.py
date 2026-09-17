"""SQLAlchemy 2.0 declarative database models."""

from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class URLModel(Base):
    """Represents a shortened URL record and its access metadata."""

    __tablename__ = "urls"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        doc="Surrogate primary key integer.",
    )
    short_code: Mapped[str] = mapped_column(
        String(16),
        unique=True,
        index=True,
        nullable=False,
        doc="Unique Base62 alphanumeric short code token.",
    )
    original_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Destination URL (HTTP or HTTPS).",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Timestamp of creation in UTC.",
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        doc="Optional link expiration timestamp in UTC.",
    )
    click_count: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
        doc="Cumulative total redirects served.",
    )
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp of the most recent redirect request.",
    )

    __table_args__ = (
        Index("ix_urls_short_code", "short_code", unique=True),
        Index("ix_urls_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<URLModel id={self.id} short_code={self.short_code} clicks={self.click_count}>"
