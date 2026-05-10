from datetime import datetime
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.db.models.v2_models import (
    MarketSnapshot,
    NewsAnalysis,
    NewsArticle,
    PipelineRun,
    PopularitySnapshot,
    StockAnalysisSnapshot,
    StockMaster,
)


def _rows_to_dicts(rows: Sequence) -> list[dict]:
    return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]


# ── PipelineRun ──


async def create_pipeline_run(
    session: AsyncSession,
    *,
    run_type: str,
    source: str = "",
    trade_date: str | None = None,
    snapshot_time: datetime | None = None,
) -> int:
    row = PipelineRun(
        run_type=run_type, source=source, trade_date=trade_date, snapshot_time=snapshot_time
    )
    session.add(row)
    await session.flush()
    return row.id


async def complete_pipeline_run(
    session: AsyncSession,
    run_id: int,
    *,
    status: str = "success",
    stock_count: int = 0,
    news_count: int = 0,
    market_count: int = 0,
    analysis_count: int = 0,
    error_message: str | None = None,
) -> None:
    row = await session.get(PipelineRun, run_id)
    if row is None:
        return
    row.status = status
    row.stock_count = stock_count
    row.news_count = news_count
    row.market_count = market_count
    row.analysis_count = analysis_count
    row.error_message = error_message
    row.finished_at = datetime.now()


# ── StockMaster ──


async def get_all_stocks(session: AsyncSession) -> list[dict]:
    result = await session.execute(select(StockMaster).order_by(StockMaster.stock_code))
    return _rows_to_dicts(result.scalars().all())


async def upsert_stocks(session: AsyncSession, rows: list[dict]) -> int:
    count = 0
    for r in rows:
        existing = await session.get(StockMaster, r["stock_code"])
        if existing:
            for k, v in r.items():
                if k != "stock_code":
                    setattr(existing, k, v)
        else:
            session.add(StockMaster(**r))
            count += 1
    return count


# ── PopularitySnapshot ──


async def get_latest_popularity_snapshot(session: AsyncSession) -> list[dict]:
    sub = select(func.max(PopularitySnapshot.snapshot_time)).scalar_subquery()
    result = await session.execute(
        select(PopularitySnapshot)
        .where(PopularitySnapshot.snapshot_time == sub)
        .order_by(PopularitySnapshot.popularity_rank)
    )
    return _rows_to_dicts(result.scalars().all())


async def get_latest_popularity_snapshot_times(session: AsyncSession, *, limit: int = 2) -> list[datetime]:
    result = await session.execute(
        select(PopularitySnapshot.snapshot_time)
        .distinct()
        .order_by(PopularitySnapshot.snapshot_time.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_popularity_snapshot_by_time(session: AsyncSession, snapshot_time: datetime) -> list[dict]:
    result = await session.execute(
        select(PopularitySnapshot)
        .where(PopularitySnapshot.snapshot_time == snapshot_time)
        .order_by(PopularitySnapshot.popularity_rank)
    )
    return _rows_to_dicts(result.scalars().all())


async def get_latest_new_entries(session: AsyncSession) -> list[dict]:
    sub = select(func.max(PopularitySnapshot.trade_date)).scalar_subquery()
    result = await session.execute(
        select(PopularitySnapshot)
        .where(
            PopularitySnapshot.trade_date == sub,
            PopularitySnapshot.is_new_entry == True,  # noqa: E712
        )
        .order_by(PopularitySnapshot.popularity_rank)
    )
    return _rows_to_dicts(result.scalars().all())


async def insert_popularity_batch(session: AsyncSession, rows: list[dict]) -> None:
    for r in rows:
        session.add(PopularitySnapshot(**r))


# ── NewsArticle ──


async def get_news_by_stock(session: AsyncSession, stock_code: str, *, limit: int = 20) -> list[dict]:
    result = await session.execute(
        select(NewsArticle)
        .where(NewsArticle.stock_code == stock_code)
        .order_by(NewsArticle.published_at.desc())
        .limit(limit)
    )
    return _rows_to_dicts(result.scalars().all())


async def get_all_news(session: AsyncSession) -> list[dict]:
    result = await session.execute(select(NewsArticle))
    return _rows_to_dicts(result.scalars().all())


# ── MarketSnapshot ──


async def get_market_data(session: AsyncSession) -> list[dict]:
    result = await session.execute(select(MarketSnapshot))
    return _rows_to_dicts(result.scalars().all())


# ── NewsAnalysis ──


async def replace_news_analysis_batch(session: AsyncSession, run_id: int, rows: list[dict], article_ids: list[int]) -> None:
    if article_ids:
        await session.execute(
            select(NewsAnalysis).where(NewsAnalysis.article_id.in_(article_ids))
        )
        result = await session.execute(
            select(NewsAnalysis).where(NewsAnalysis.article_id.in_(article_ids))
        )
        existing = {r.article_id: r for r in result.scalars().all()}
        if existing:
            for r in existing.values():
                await session.delete(r)
            await session.flush()
    for r in rows:
        r["run_id"] = run_id
        session.add(NewsAnalysis(**r))


# ── StockAnalysisSnapshot ──


async def get_latest_analysis(session: AsyncSession, *, limit: int = 200) -> list[dict]:
    sub = (
        select(
            StockAnalysisSnapshot.stock_code,
            func.max(StockAnalysisSnapshot.analyzed_at).label("max_at"),
        )
        .group_by(StockAnalysisSnapshot.stock_code)
        .subquery()
    )
    result = await session.execute(
        select(StockAnalysisSnapshot)
        .join(sub, (StockAnalysisSnapshot.stock_code == sub.c.stock_code) & (StockAnalysisSnapshot.analyzed_at == sub.c.max_at))
        .order_by(StockAnalysisSnapshot.integrated_score.desc().nullslast())
        .limit(limit)
    )
    return _rows_to_dicts(result.scalars().all())


async def get_analysis_by_stock(session: AsyncSession, stock_code: str) -> dict | None:
    result = await session.execute(
        select(StockAnalysisSnapshot)
        .where(StockAnalysisSnapshot.stock_code == stock_code)
        .order_by(StockAnalysisSnapshot.analyzed_at.desc())
        .limit(1)
    )
    row = result.scalars().first()
    if row is None:
        return None
    return _rows_to_dicts([row])[0]


async def insert_stock_analysis_batch(session: AsyncSession, rows: list[dict]) -> int:
    for r in rows:
        session.add(StockAnalysisSnapshot(**r))
    return len(rows)


__all__ = [
    "create_pipeline_run",
    "complete_pipeline_run",
    "get_all_stocks",
    "upsert_stocks",
    "get_latest_popularity_snapshot",
    "get_latest_popularity_snapshot_times",
    "get_popularity_snapshot_by_time",
    "get_latest_new_entries",
    "insert_popularity_batch",
    "get_news_by_stock",
    "get_all_news",
    "get_market_data",
    "replace_news_analysis_batch",
    "get_latest_analysis",
    "get_analysis_by_stock",
    "insert_stock_analysis_batch",
]
