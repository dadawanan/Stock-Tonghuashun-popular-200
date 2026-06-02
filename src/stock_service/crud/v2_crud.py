from datetime import datetime
from decimal import Decimal
from typing import Any, Sequence

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from stock_service.crud.utils import _rows_to_dicts
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
from stock_service.domain.services.stock_utils import normalize_stock_code

_STOCK_MASTER_FIELDS = {c.name for c in StockMaster.__table__.columns}


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
    """使用 PostgreSQL ON CONFLICT DO UPDATE 批量 upsert stock_master，返回新增行数。"""
    if not rows:
        return 0

    # 1. 内存去重：防止 rows 内部自带重复的 stock_code 导致 Postgres 报错
    seen_codes: set[str] = set()
    unique_rows: list[dict] = []
    for r in rows:
        code = r.get("stock_code")
        if code and code not in seen_codes:
            seen_codes.add(code)
            unique_rows.append(r)

    # 2. 预计算衍生字段 + 清洗字段，一次性构建所有 values
    value_rows: list[dict] = []
    all_codes: list[str] = []

    for r in unique_rows:
        stock_code = r["stock_code"]
        all_codes.append(stock_code)

        derived = _derive_stock_fields(stock_code, str(r.get("stock_name", "")))
        model_fields = {k: v for k, v in r.items() if k in _STOCK_MASTER_FIELDS}
        model_fields["market"] = derived["market"]
        model_fields["code_digits"] = derived["code_digits"]
        model_fields["is_st"] = derived["is_st"]
        model_fields["market_code"] = str(model_fields["market_code"]) if model_fields.get("market_code") is not None else None
        model_fields.setdefault("status", "active")
        value_rows.append(model_fields)

    # 3. 先查询已存在的 stock_code，用于统计新增数量
    existing_result = await session.execute(
        select(StockMaster.stock_code).where(StockMaster.stock_code.in_(all_codes))
    )
    existing_set = {row[0] for row in existing_result.all()}

    # 4. 构建并执行批量 Upsert 语句
    stmt = pg_insert(StockMaster).values(value_rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["stock_code"],
        set_={
            "stock_name": stmt.excluded.stock_name,
            "market": stmt.excluded.market,
            "market_code": stmt.excluded.market_code,
            "code_digits": stmt.excluded.code_digits,
            "is_st": stmt.excluded.is_st,
            "updated_at": func.now(),
        },
    )
    await session.execute(stmt)

    # 5. 计算真正新增的行数
    return sum(1 for c in all_codes if c not in existing_set)


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

    # 1. batch 内部去重（按两个唯一约束）
    seen_url: set[tuple[str, str]] = set()
    seen_hash: set[tuple[str, str]] = set()
    deduped: list[dict] = []
    for r in rows:
        url_key = (r["stock_code"], r.get("url") or "")
        hash_key = (r["stock_code"], r.get("content_hash") or "")
        if url_key in seen_url or hash_key in seen_hash:
            continue
        seen_url.add(url_key)
        seen_hash.add(hash_key)
        deduped.append(r)

    # 2. 查库过滤已存在的记录（no_autoflush 防止 pending 对象被提前 flush）
    stock_codes = list({r["stock_code"] for r in deduped})
    urls = [r["url"] for r in deduped if r.get("url")]
    hashes = [r["content_hash"] for r in deduped if r.get("content_hash")]

    existing_urls: set[tuple[str, str]] = set()
    existing_hashes: set[tuple[str, str]] = set()

    with session.no_autoflush:
        if urls:
            result = await session.execute(
                select(NewsArticle.stock_code, NewsArticle.url).where(
                    NewsArticle.stock_code.in_(stock_codes),
                    NewsArticle.url.in_(urls),
                )
            )
            existing_urls = {(row[0], row[1]) for row in result.all()}

        if hashes:
            result = await session.execute(
                select(NewsArticle.stock_code, NewsArticle.content_hash).where(
                    NewsArticle.stock_code.in_(stock_codes),
                    NewsArticle.content_hash.in_(hashes),
                )
            )
            existing_hashes = {(row[0], row[1]) for row in result.all()}

    new_rows = [
        r for r in deduped
        if (r["stock_code"], r.get("url") or "") not in existing_urls
        and (r["stock_code"], r.get("content_hash") or "") not in existing_hashes
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


async def get_latest_market_snapshot(session: AsyncSession) -> dict[str, dict]:
    """获取最新 market_snapshot，返回 {stock_code: {...}} 格式"""
    sub = select(func.max(MarketSnapshot.snapshot_time)).scalar_subquery()
    result = await session.execute(
        select(MarketSnapshot).where(MarketSnapshot.snapshot_time == sub)
    )
    data = {}
    for row in result.scalars().all():
        d = _rows_to_dicts([row])[0]
        data[d["stock_code"]] = {
            "pct_change": float(d.get("pct_change") or 0),
            "volume_ratio": float(d.get("volume_ratio") or 0),
            "main_net_inflow": float(d.get("main_net_inflow") or 0),
            "turnover_rate": float(d.get("turnover_rate") or 0),
            "amplitude": float(d.get("amplitude") or 0),
            "latest_price": float(d.get("latest_price") or 0),
        }
    return data


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


def _num_or_none(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)  # type: ignore[arg-type]


async def _attach_latest_popularity_fields(session: AsyncSession, rows: list[dict]) -> None:
    """Augment analysis rows with fields from the latest popularity_snapshot (same snapshot_time as /api/popularity/latest)."""
    if not rows:
        return
    max_time_result = await session.execute(select(func.max(PopularitySnapshot.snapshot_time)))
    max_time: datetime | None = max_time_result.scalar_one_or_none()
    if max_time is None:
        empty = {
            "popularity_rank": None,
            "popularity_score": None,
            "popularity_previous_rank": None,
            "popularity_rank_change": None,
            "popularity_snapshot_time": None,
        }
        for r in rows:
            r.update(empty)
        return

    result = await session.execute(select(PopularitySnapshot).where(PopularitySnapshot.snapshot_time == max_time))
    pop_by_norm: dict[str, dict[str, Any]] = {}
    for p in _rows_to_dicts(result.scalars().all()):
        pop_by_norm[normalize_stock_code(p["stock_code"])] = p

    snap_iso = max_time.isoformat()
    empty_missing = {
        "popularity_rank": None,
        "popularity_score": None,
        "popularity_previous_rank": None,
        "popularity_rank_change": None,
        "popularity_snapshot_time": snap_iso,
    }
    for r in rows:
        pop = pop_by_norm.get(normalize_stock_code(r["stock_code"]))
        if pop is None:
            r.update(empty_missing)
            continue
        r["popularity_rank"] = pop.get("popularity_rank")
        r["popularity_score"] = _num_or_none(pop.get("popularity_score"))
        r["popularity_previous_rank"] = pop.get("previous_rank")
        r["popularity_rank_change"] = pop.get("rank_change")
        r["popularity_snapshot_time"] = snap_iso


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
        .order_by(StockAnalysisSnapshot.analyzed_at.desc().nullslast())
        .limit(limit)
    )
    rows = _rows_to_dicts(result.scalars().all())
    await _attach_latest_popularity_fields(session, rows)
    return rows


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
    rows = _rows_to_dicts([row])
    await _attach_latest_popularity_fields(session, rows)
    return rows[0]


_SNAPSHOT_COLS = {c.key for c in StockAnalysisSnapshot.__table__.columns}


async def insert_stock_analysis_batch(session: AsyncSession, rows: list[dict]) -> int:
    for r in rows:
        session.add(StockAnalysisSnapshot(**{k: v for k, v in r.items() if k in _SNAPSHOT_COLS}))
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
