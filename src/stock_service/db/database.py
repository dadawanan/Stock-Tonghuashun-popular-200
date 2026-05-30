from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from stock_service.infrastructure.config.settings import DATABASE_CONFIG

logger = logging.getLogger(__name__)

DATABASE_URL = (
    f"postgresql+asyncpg://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}"
    f"@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
)
logger.info(f"数据库连接: {DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}")  # 不打印密码

async_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_timeout=float(DATABASE_CONFIG["timeout"]),
    pool_recycle=1800,
    pool_pre_ping=True,
)

AsyncSessionFactory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

