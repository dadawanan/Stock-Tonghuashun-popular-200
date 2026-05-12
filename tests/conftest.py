"""测试公共 fixtures。

重要（曾与生产共用库会导致 users 被清空）：
- pytest **绝不**连接与应用 `.env` 里相同的 ``DB_NAME``。
- 默认库名为 **`stock_db_test`**（可用 ``TEST_DB_NAME`` 覆盖）。
- 可选 ``TEST_DB_HOST`` / ``TEST_DB_PORT`` / ``TEST_DB_USER`` / ``TEST_DB_PASSWORD``：
  未设置或为空时，分别沿用应用库的 ``DB_*`` 配置（仅换库名）。
  可在 ``.env`` 或 shell 中配置，与 ``DB_*`` 写法相同。
- 请先创建测试库并同步 schema，例如::

      psql -U postgres -c 'CREATE DATABASE stock_db_test;'
      psql -U postgres -d stock_db_test -f schema_v2.sql

"""
from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from urllib.parse import quote_plus

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from stock_service.db.models.v2_models import RefreshToken, User
from stock_service.infrastructure.config.settings import DATABASE_CONFIG, settings

_RESOLVED_TEST_DB_NAME: str | None = None


def _resolved_test_db_name() -> str:
    """解析 pytest 使用的库名；若与应用 DB_NAME 相同则立即中止 pytest。"""
    global _RESOLVED_TEST_DB_NAME
    if _RESOLVED_TEST_DB_NAME is not None:
        return _RESOLVED_TEST_DB_NAME

    raw_name = os.getenv("TEST_DB_NAME", "stock_db_test").strip()
    test_db = raw_name or "stock_db_test"

    if test_db == settings.db_name:
        pytest.exit(
            "pytest 已中止：TEST_DB_NAME 与应用的 DB_NAME 相同，继续运行会清空 users / refresh_tokens。\n"
            "请创建独立测试库并同步 schema，然后指定 TEST_DB_NAME，例如：\n"
            "  CREATE DATABASE stock_db_test;\n"
            "  psql -d stock_db_test -f schema_v2.sql\n"
            "  TEST_DB_NAME=stock_db_test pytest\n",
            returncode=2,
        )

    _RESOLVED_TEST_DB_NAME = test_db
    return test_db


def pytest_configure(config):
    """在收集用例之前即校验库配置，避免误连生产库。"""
    _test_connection_cfg()


def _test_connection_cfg() -> dict[str, str | int | float | bool | None]:
    """合并 DATABASE_CONFIG 与可选的 TEST_DB_*（主机/端口/账号可与应用库不同）。"""
    cfg: dict[str, str | int | float | bool | None] = dict(DATABASE_CONFIG)
    cfg["database"] = _resolved_test_db_name()

    host = os.getenv("TEST_DB_HOST", "").strip()
    if host:
        cfg["host"] = host

    port_raw = os.getenv("TEST_DB_PORT", "").strip()
    if port_raw:
        cfg["port"] = int(port_raw)

    user = os.getenv("TEST_DB_USER", "").strip()
    if user:
        cfg["user"] = user

    if "TEST_DB_PASSWORD" in os.environ:
        cfg["password"] = os.environ["TEST_DB_PASSWORD"]

    return cfg


def _get_test_database_url() -> str:
    """构建 pytest 专用库的连接串（与应用 DB_NAME 必须不同）。"""
    cfg = _test_connection_cfg()
    user = quote_plus(str(cfg["user"]))
    password = quote_plus(str(cfg["password"]))
    host = cfg["host"]
    port = cfg["port"]
    db = cfg["database"]
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


def _make_test_engine():
    """每次调用创建新的测试引擎，使用 NullPool 避免跨事件循环的连接池问题。"""
    return create_async_engine(_get_test_database_url(), echo=False, poolclass=NullPool)


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

    # 清理测试数据（仅针对 TEST_DB_NAME 对应的库）
    async with factory() as session:
        await session.execute(delete(RefreshToken))
        await session.execute(delete(User))
        await session.commit()

    await engine.dispose()
