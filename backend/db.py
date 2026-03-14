import logging
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg

from config import settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db() first.")
    return _pool


async def init_db() -> None:
    global _pool
    logger.info("Connecting to database...")
    _pool = await asyncpg.create_pool(
        settings.database_url,
        min_size=2,
        max_size=10,
    )
    # Run schema migration
    async with _pool.acquire() as conn:
        schema_path = Path(__file__).resolve().parent / "sql" / "schema.sql"
        try:
            with open(schema_path) as f:
                schema_sql = f.read()
            await conn.execute(schema_sql)
            logger.info("Database schema applied successfully")
        except FileNotFoundError:
            logger.warning(f"Schema file {schema_path} not found, skipping migration")


async def close_db() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


@asynccontextmanager
async def db_connection():
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn
