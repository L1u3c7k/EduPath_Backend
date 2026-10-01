import ssl
from typing import Any, AsyncGenerator
import redis.asyncio as aioredis
import certifi
from fastapi import HTTPException, Request, status
from fastapi import Request
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.config import settings


def build_connect_args(database_url: str) -> dict[str, Any]:
    """SSL and pooler options needed for Supabase (and safe locally)."""
    parsed = make_url(database_url)
    host = parsed.host or ""
    args: dict[str, Any] = {}

    if "supabase" in host:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        # Windows SSL inspection / some pooler chains fail strict verify.
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        args["ssl"] = ssl_context
        # Transaction pooler (port 6543) does not support prepared statements.
        if parsed.port == 6543:
            args["statement_cache_size"] = 0

    return args

async def get_redis(request: Request) -> aioredis.Redis:
    redis_instance = getattr(request.app.state, "redis", None)
    if redis_instance is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis client is not initialized or failed to connect."
        )
    return redis_instance

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,  # Validates stale connections automatically
    connect_args=build_connect_args(settings.DATABASE_URL),
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    class_=AsyncSession,
    expire_on_commit=False,  # Prevents unnecessary re-queries after commit
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as db:
        yield db
        # 'async with' automatically handles closing the session safely