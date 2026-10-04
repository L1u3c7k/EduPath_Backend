import ssl
from typing import Any, AsyncGenerator

import certifi
import redis.asyncio as aioredis
from fastapi import HTTPException, Request, status
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.config import settings


def build_connect_args(database_url: str) -> dict[str, Any]:
    """
    Build database connection arguments.

    Supabase:
    - Uses SSL.
    - Disables hostname/certificate verification to avoid
      Windows SSL inspection / pooler certificate issues.
    - Disables prepared-statement caching for the transaction
      pooler on port 6543.

    Local PostgreSQL:
    - Uses the default connection settings.
    """
    parsed = make_url(database_url)

    host = parsed.host or ""

    args: dict[str, Any] = {}

    if "supabase" in host:
        ssl_context = ssl.create_default_context(
            cafile=certifi.where()
        )

        # Windows SSL inspection / some Supabase pooler
        # certificate chains can fail strict verification.
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        args["ssl"] = ssl_context

        # Supabase transaction pooler does not support
        # prepared statements.
        if parsed.port == 6543:
            args["statement_cache_size"] = 0

    return args


# ============================================================
# REDIS DEPENDENCY
# ============================================================

async def get_redis(request: Request) -> aioredis.Redis:
    """
    Return the Redis client initialized in FastAPI app.state.

    The Redis client itself is created during application startup
    in src/main.py:

        app.state.redis = aioredis.Redis(...)

    Quiz routes receive this client through:

        Depends(get_redis)
    """

    redis_instance = getattr(
        request.app.state,
        "redis",
        None,
    )

    if redis_instance is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis client is not initialized or failed to connect.",
        )

    return redis_instance


# ============================================================
# DATABASE ENGINE
# ============================================================

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
    connect_args=build_connect_args(
        settings.DATABASE_URL
    ),
)


# ============================================================
# ASYNC SESSION
# ============================================================

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


# ============================================================
# SQLALCHEMY BASE
# ============================================================

class Base(DeclarativeBase):
    pass


# ============================================================
# DATABASE DEPENDENCY
# ============================================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide an AsyncSession to FastAPI routes.

    The session is automatically closed when the request finishes.
    """

    async with AsyncSessionLocal() as db:
        yield db