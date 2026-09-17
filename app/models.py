"""SQLAlchemy 2.0 declarative database models."""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
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

    # Relationship to detailed click events
    click_events: Mapped[List["ClickEventModel"]] = relationship(
        "ClickEventModel",
        back_populates="url",
        cascade="all, delete-orphan",
        order_by="desc(ClickEventModel.clicked_at)",
    )

    __table_args__ = (
        Index("ix_urls_short_code", "short_code", unique=True),
        Index("ix_urls_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<URLModel id={self.id} short_code={self.short_code} clicks={self.click_count}>"


class ClickEventModel(Base):
    """Represents an individual redirect click event for analytics."""

    __tablename__ = "click_events"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        doc="Event unique identifier.",
    )
    url_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("urls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Foreign key referencing urls.id.",
    )
    clicked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        doc="Timestamp of redirect in UTC.",
    )
    referrer: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        doc="HTTP Referer header value.",
    )
    user_agent_family: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        doc="Derived browser/client family (e.g., Chrome, Firefox, Safari, Python, Bot).",
    )
    ip_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        doc="Salted SHA-256 hash of client IP for privacy-compliant unique visitor tracking.",
    )

    url: Mapped["URLModel"] = relationship("URLModel", back_populates="click_events")

    __table_args__ = (
        Index("ix_click_events_url_id", "url_id"),
        Index("ix_click_events_clicked_at", "clicked_at"),
    )

    def __repr__(self) -> str:
        return f"<ClickEventModel id={self.id} url_id={self.url_id} at={self.clicked_at}>"

