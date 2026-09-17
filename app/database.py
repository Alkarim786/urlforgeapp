"""Database engine, session factory, and lifecycle management for PostgreSQL.

Uses SQLAlchemy 2.0 async engine with asyncpg.
Includes connection pooling, event loop affinity management for async test suites,
and FastAPI session dependency.
"""

import asyncio
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool
from app.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """Base declarative class for all ORM models."""
    pass


# Global engine and loop tracking
_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None
_engine_loop: Optional[asyncio.AbstractEventLoop] = None


def get_engine() -> AsyncEngine:
    """Lazily initialize and return the async database engine.
    
    Protects against asyncio event loop changes across pytest async test cases.
    """
    global _engine, _session_factory, _engine_loop
    current_loop: Optional[asyncio.AbstractEventLoop] = None
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        pass

    if _engine is None or (_engine_loop is not None and _engine_loop != current_loop):
        _engine_loop = current_loop
        pool_cls = AsyncAdaptedQueuePool if settings.ENVIRONMENT == "production" else NullPool
        
        engine_kwargs = {
            "echo": settings.DEBUG,
            "poolclass": pool_cls,
            "pool_pre_ping": True,
        }
        if pool_cls is AsyncAdaptedQueuePool:
            engine_kwargs["pool_size"] = settings.DATABASE_POOL_SIZE
            engine_kwargs["max_overflow"] = settings.DATABASE_MAX_OVERFLOW
            engine_kwargs["pool_timeout"] = settings.DATABASE_POOL_TIMEOUT

        _engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)
        _session_factory = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the configured async session factory."""
    get_engine()
    assert _session_factory is not None
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an independent, scoped AsyncSession.
    
    Ensures transactions are safely committed or rolled back.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_database_connections():
    """Dispose engine connections on application shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
