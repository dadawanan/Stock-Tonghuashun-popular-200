"""测试公共 fixtures。"""
from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from stock_service.db.database import DATABASE_URL
from stock_service.db.models.v2_models import RefreshToken, User


def _make_test_engine():
    """每次调用创建新的测试引擎，使用 NullPool 避免跨事件循环的连接池问题。"""
    return create_async_engine(DATABASE_URL, echo=False, poolclass=NullPool)


@pytest.fixture(autouse=True)
async def _override_session():
    """为每个测试覆盖 get_session 依赖，并在测试后清理数据。"""
    from stock_service.api.app import app
    from stock_service.api.dependencies import get_session

    engine = _make_test_engine()
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def _test_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = _test_get_session
    yield
    app.dependency_overrides.clear()

    # 清理测试数据
    async with factory() as session:
        await session.execute(delete(RefreshToken))
        await session.execute(delete(User))
        await session.commit()

    await engine.dispose()
