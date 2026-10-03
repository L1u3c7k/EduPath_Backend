from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from src.config import settings


# 1. Use create_async_engine instead of create_engine
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True, 
    pool_recycle=3600,
    echo=False,
)

# 2. Use async_sessionmaker and specify the class as AsyncSession
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=AsyncSession,  # This tells it to generate async sessions
)

class Base(DeclarativeBase):
    pass

# 3. Update get_db to be an async generator
async def get_db():
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            # Using 'async with' automatically closes the session, 
            # but we catch any exceptions cleanly here.
            await db.close()