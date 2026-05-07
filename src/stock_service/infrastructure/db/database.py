from __future__ import annotations

import logging
from pathlib import Path

import asyncpg

from stock_service.infrastructure.config.settings import DATABASE_CONFIG
from stock_service.infrastructure.db.database_utils import to_json_text
from stock_service.infrastructure.db.repositories.analysis import AnalysisRepository
from stock_service.infrastructure.db.repositories.market import MarketRepository
from stock_service.infrastructure.db.repositories.news import NewsRepository
from stock_service.infrastructure.db.repositories.pipeline import PipelineRunRepository
from stock_service.infrastructure.db.repositories.popularity import PopularityRepository
from stock_service.infrastructure.db.repositories.stock import StockRepository


_SCHEMA_FILE = Path(__file__).resolve().parents[4] / "schema_v2.sql"

logger = logging.getLogger(__name__)


class StockDatabase:
    def __init__(self, pool: asyncpg.Pool | None = None):
        self.pool: asyncpg.Pool | None = pool
        self.pipeline_runs: PipelineRunRepository | None = None
        self.stocks: StockRepository | None = None
        self.popularity: PopularityRepository | None = None
        self.news: NewsRepository | None = None
        self.market: MarketRepository | None = None
        self.analysis: AnalysisRepository | None = None

    def _bind_repositories(self) -> None:
        self.pipeline_runs = PipelineRunRepository(self.pool)
        self.stocks = StockRepository(self.pool)
        self.popularity = PopularityRepository(self.pool)
        self.news = NewsRepository(self.pool)
        self.market = MarketRepository(self.pool)
        self.analysis = AnalysisRepository(self.pool)

    async def initialize(self) -> None:
        if self.pool:
            self._bind_repositories()
            return
        pool_kw: dict = {
            "host": DATABASE_CONFIG["host"],
            "port": DATABASE_CONFIG["port"],
            "database": DATABASE_CONFIG["database"],
            "user": DATABASE_CONFIG["user"],
            "password": DATABASE_CONFIG["password"],
            "min_size": 2,
            "max_size": 10,
            "timeout": DATABASE_CONFIG["timeout"],
        }
        ssl_val = DATABASE_CONFIG.get("ssl")
        if ssl_val is not None:
            pool_kw["ssl"] = ssl_val
        target = f"{pool_kw['host']}:{pool_kw['port']}/{pool_kw['database']}"
        try:
            self.pool = await asyncpg.create_pool(**pool_kw)
        except TimeoutError as exc:
            logger.exception("PostgreSQL 连接超时: %s", target)
            raise RuntimeError(
                f"连接 PostgreSQL 超时（{target}）。"
                "常见原因：云数据库安全组/防火墙未放行你当前公网 IP；"
                "主机或端口填错；云上实例要求 SSL 时在 .env 设置 DB_SSL=require。"
                "修改 .env 后请执行：pm2 restart stock-api --update-env"
            ) from exc
        except OSError as exc:
            logger.exception("PostgreSQL 连接失败: %s", target)
            raise RuntimeError(
                f"无法访问 PostgreSQL（{target}）：{exc}。"
                "请检查网络、VPN、DB_HOST/DB_PORT。"
            ) from exc
        await self._ensure_schema()
        self._bind_repositories()

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
            self.pool = None
        self.pipeline_runs = None
        self.stocks = None
        self.popularity = None
        self.news = None
        self.market = None
        self.analysis = None

    async def _ensure_schema(self) -> None:
        async with self.pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='stock_master')"
            )
        if exists or not _SCHEMA_FILE.exists():
            return
        async with self.pool.acquire() as conn:
            await conn.execute(_SCHEMA_FILE.read_text(encoding="utf-8"))

    async def create_pipeline_run(self, *args, **kwargs):
        return await self.pipeline_runs.create_pipeline_run(*args, **kwargs)

    async def complete_pipeline_run(self, *args, **kwargs):
        return await self.pipeline_runs.complete_pipeline_run(*args, **kwargs)

    async def upsert_stocks(self, *args, **kwargs):
        return await self.stocks.upsert_stocks(*args, **kwargs)

    async def get_all_stocks(self, *args, **kwargs):
        return await self.stocks.get_all_stocks(*args, **kwargs)

    async def insert_popularity_batch(self, *args, **kwargs):
        return await self.popularity.insert_popularity_batch(*args, **kwargs)

    async def get_latest_popularity_snapshot(self, *args, **kwargs):
        return await self.popularity.get_latest_popularity_snapshot(*args, **kwargs)

    async def get_latest_popularity_snapshot_times(self, *args, **kwargs):
        return await self.popularity.get_latest_popularity_snapshot_times(*args, **kwargs)

    async def get_popularity_snapshot_by_time(self, *args, **kwargs):
        return await self.popularity.get_popularity_snapshot_by_time(*args, **kwargs)

    async def get_latest_new_entries(self, *args, **kwargs):
        return await self.popularity.get_latest_new_entries(*args, **kwargs)

    async def insert_news_batch(self, *args, **kwargs):
        return await self.news.insert_news_batch(*args, **kwargs)

    async def get_news_by_stock(self, *args, **kwargs):
        return await self.news.get_news_by_stock(*args, **kwargs)

    async def get_all_news(self, *args, **kwargs):
        return await self.news.get_all_news(*args, **kwargs)

    async def insert_market_batch(self, *args, **kwargs):
        return await self.market.insert_market_batch(*args, **kwargs)

    async def get_market_data(self, *args, **kwargs):
        return await self.market.get_market_data(*args, **kwargs)

    async def replace_news_analysis_batch(self, *args, **kwargs):
        return await self.analysis.replace_news_analysis_batch(*args, **kwargs)

    async def insert_stock_analysis_batch(self, *args, **kwargs):
        return await self.analysis.insert_stock_analysis_batch(*args, **kwargs)

    async def get_latest_analysis(self, *args, **kwargs):
        return await self.analysis.get_latest_analysis(*args, **kwargs)

