from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.db.database import AsyncSessionFactory
from stock_service.infrastructure.db.database import StockDatabase


_db: StockDatabase | None = None


async def get_db() -> StockDatabase:
    global _db
    if _db is None or _db.pool is None:
        raise RuntimeError("数据库未初始化，请等待服务启动完成")
    return _db


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def lifespan(_: object):
    global _db
    _db = StockDatabase()
    await _db.initialize()
    yield
    await _db.close()
