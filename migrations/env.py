import asyncio
import logging
import os
import sys
from logging.config import fileConfig
from pathlib import Path
from urllib.parse import quote_plus, urlparse, urlunparse

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

logger = logging.getLogger("alembic.env")

# 1. Force Project Root Path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

# 2. Load .env BEFORE importing settings or database
load_dotenv(dotenv_path=BASE_DIR / ".env")

# Import models and settings AFTER env is loaded
from src.config import settings
from src.database import Base, build_connect_args

try:
    import src.chat.model
except ImportError as e:
    logger.warning(f"Could not import src.chat.model: {e}")

try:
    import src.quiz.quiz_model
except ImportError as e:
    logger.warning(f"Could not import src.quiz.quiz_model: {e}")

try:
    import src.user.user_model
except ImportError as e:
    logger.warning(f"Could not import src.user.user_model: {e}")

try:
    import src.question.question_model
except ImportError as e:
    logger.warning(f"Could not import src.question.question_model: {e}")

# Alembic Config object
config = context.config

# Setup database URL dynamically from settings
raw_url = str(settings.DATABASE_URL)

# DEBUG PRINT: Verify exact hostname being passed to asyncpg
parsed = urlparse(raw_url)
print("PARSED HOSTNAME:", parsed.hostname)
print("PARSED USERNAME:", parsed.username)

if raw_url:
    # 1. Ensure correct async driver prefix
    if raw_url.startswith("postgresql://"):
        raw_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # 2. Safely re-encode password special characters if unescaped by Pydantic
    if parsed.password and parsed.hostname:
        safe_password = quote_plus(parsed.password)
        # Reconstruct clean netloc without breaking host parsing
        netloc = f"{parsed.username}:{safe_password}@{parsed.hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"
        
        parsed_tuple = parsed._replace(netloc=netloc)
        raw_url = urlunparse(parsed_tuple)

    # 3. Escape '%' for Alembic's ConfigParser interpolation
    escaped_db_url = raw_url.replace("%", "%%")

    config.set_main_option("sqlalchemy.url", escaped_db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations using the provided connection context."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with an async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=build_connect_args(str(settings.DATABASE_URL)),
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()