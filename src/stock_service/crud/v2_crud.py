from datetime import datetime
from typing import Sequence

from sqlalchemy import func, select, text
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

_STOCK_MASTER_FIELDS = {c.name for c in StockMaster.__table__.columns}


def _rows_to_dicts(rows: Sequence) -> list[dict]:
    return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]


def _derive_stock_fields(stock_code: str, stock_name: str) -> dict:
    parts = stock_code.split(".")
    code_digits = parts[0]
    market = parts[1] if len(parts) > 1 else "SZ"
    is_st = "ST" in stock_name.upper()
    return {"market": market, "code_digits": code_digits, "is_st": is_st}


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
    result = await session.execute(
        select(StockMaster).where(StockMaster.status == "active").order_by(StockMaster.stock_code)
    )
    return _rows_to_dicts(result.scalars().all())


async def upsert_stocks(session: AsyncSession, rows: list[dict]) -> int:
    count = 0
    for r in rows:
        stock_code = r["stock_code"]
        existing = await session.get(StockMaster, stock_code)
        derived = _derive_stock_fields(stock_code, str(r.get("stock_name", "")))
        if existing:
            existing.stock_name = r.get("stock_name", existing.stock_name)
            existing.market = derived["market"]
            existing.market_code = str(r["market_code"]) if r.get("market_code") is not None else existing.market_code
            existing.code_digits = derived["code_digits"]
            existing.is_st = derived["is_st"]
        else:
            model_fields = {k: v for k, v in r.items() if k in _STOCK_MASTER_FIELDS}
            model_fields.setdefault("market", derived["market"])
            model_fields.setdefault("code_digits", derived["code_digits"])
            model_fields.setdefault("is_st", derived["is_st"])
            model_fields["market_code"] = str(model_fields["market_code"]) if model_fields.get("market_code") is not None else None
            session.add(StockMaster(**model_fields))
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


async def get_all_news(session: AsyncSession, *, limit_per_stock: int = 20) -> list[dict]:
    sub = (
        select(
            NewsArticle.id,
            func.row_number()
            .over(
                partition_by=NewsArticle.stock_code,
                order_by=[NewsArticle.published_at.desc().nullslast(), NewsArticle.fetched_at.desc(), NewsArticle.id.desc()],
            )
            .label("rn"),
        )
        .subquery()
    )
    result = await session.execute(
        select(NewsArticle)
        .join(sub, NewsArticle.id == sub.c.id)
        .where(sub.c.rn <= limit_per_stock)
        .order_by(NewsArticle.stock_code, NewsArticle.published_at.desc().nullslast())
    )
    return _rows_to_dicts(result.scalars().all())


async def insert_news_batch(session: AsyncSession, rows: list[dict]) -> int:
    if not rows:
        return 0

    stock_codes = list({r["stock_code"] for r in rows})
    urls = [r["url"] for r in rows if r.get("url")]
    hashes = [r["content_hash"] for r in rows if r.get("content_hash")]

    existing_urls: set[str] = set()
    existing_hashes: set[str] = set()

    if urls:
        result = await session.execute(
            select(NewsArticle.url).where(
                NewsArticle.stock_code.in_(stock_codes),
                NewsArticle.url.in_(urls),
            )
        )
        existing_urls = {row[0] for row in result.all()}

    if hashes:
        result = await session.execute(
            select(NewsArticle.content_hash).where(
                NewsArticle.stock_code.in_(stock_codes),
                NewsArticle.content_hash.in_(hashes),
            )
        )
        existing_hashes = {row[0] for row in result.all()}

    new_rows = [
        r for r in rows
        if r.get("url") not in existing_urls and r.get("content_hash") not in existing_hashes
    ]
    for r in new_rows:
        session.add(NewsArticle(**r))
    return len(new_rows)


# ── MarketSnapshot ──


async def get_market_data(session: AsyncSession) -> list[dict]:
    sub = (
        select(
            MarketSnapshot.stock_code,
            func.max(MarketSnapshot.snapshot_time).label("max_time"),
        )
        .group_by(MarketSnapshot.stock_code)
        .subquery()
    )
    result = await session.execute(
        select(MarketSnapshot)
        .join(
            sub,
            (MarketSnapshot.stock_code == sub.c.stock_code) & (MarketSnapshot.snapshot_time == sub.c.max_time),
        )
        .order_by(MarketSnapshot.stock_code)
    )
    rows = result.scalars().all()
    # If multiple rows share the same max snapshot_time per stock, pick the latest id
    seen: dict[str, dict] = {}
    for r in rows:
        d = _rows_to_dicts([r])[0]
        key = d["stock_code"]
        if key not in seen or (r.id or 0) > (seen[key].get("id") or 0):
            seen[key] = d
    return list(seen.values())


async def insert_market_batch(session: AsyncSession, rows: list[dict]) -> None:
    for r in rows:
        session.add(MarketSnapshot(**r))


# ── NewsAnalysis ──


async def replace_news_analysis_batch(session: AsyncSession, run_id: int, rows: list[dict], article_ids: list[int]) -> int:
    if article_ids:
        result = await session.execute(
            select(NewsAnalysis).where(NewsAnalysis.article_id.in_(article_ids))
        )
        for r in result.scalars().all():
            await session.delete(r)
        await session.flush()

    seen: set[tuple] = set()
    deduped: list[dict] = []
    for r in rows:
        r["run_id"] = run_id
        key = (r["article_id"], r.get("analyzer_type"), r.get("model_name"), r.get("prompt_version"))
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    for r in deduped:
        session.add(NewsAnalysis(**r))
    return len(deduped)


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
    "insert_news_batch",
    "get_market_data",
    "insert_market_batch",
    "replace_news_analysis_batch",
    "get_latest_analysis",
    "get_analysis_by_stock",
    "insert_stock_analysis_batch",
]
