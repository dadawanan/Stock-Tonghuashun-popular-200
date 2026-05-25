from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.crud import v2_crud
from stock_service.infrastructure.providers.eastmoney_provider import normalize_stock_code
from stock_service.infrastructure.providers.ths_provider import fetch_top_200_popularity


def standardize_popularity_frame(raw_df: pd.DataFrame) -> pd.DataFrame:
    if raw_df is None or raw_df.empty:
        return pd.DataFrame(columns=["stock_code", "stock_name", "source_latest_price", "source_pct_change", "popularity_rank", "popularity_score", "market_code"])
    result = raw_df.copy()
    rename_map: dict[str, str] = {}
    for column in result.columns:
        if column == "股票代码":
            rename_map[column] = "stock_code"
        elif column == "股票简称":
            rename_map[column] = "stock_name"
        elif column == "最新价":
            rename_map[column] = "source_latest_price"
        elif column == "最新涨跌幅":
            rename_map[column] = "source_pct_change"
        elif column.startswith("个股热度排名["):
            rename_map[column] = "popularity_rank"
        elif column.startswith("个股热度["):
            rename_map[column] = "popularity_score"
        elif column == "market_code":
            rename_map[column] = "market_code"
    result = result.rename(columns=rename_map)
    if "stock_code" not in result.columns or "stock_name" not in result.columns:
        raise ValueError(f"人气榜数据缺少必要字段，当前列为: {list(result.columns)}")
    keep_columns = [c for c in ["stock_code", "stock_name", "source_latest_price", "source_pct_change", "popularity_rank", "popularity_score", "market_code"] if c in result.columns]
    result = result[keep_columns].copy()
    result["stock_code"] = result["stock_code"].map(normalize_stock_code)
    result["stock_name"] = result["stock_name"].fillna("").astype(str).str.strip()
    for column in ["source_latest_price", "source_pct_change", "popularity_rank", "popularity_score"]:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.drop_duplicates(subset=["stock_code"]).reset_index(drop=True)


def build_stock_rows(stocks_df: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {
            "stock_code": row["stock_code"],
            "stock_name": row["stock_name"],
            "source_latest_price": pd.to_numeric(row.get("source_latest_price"), errors="coerce") if pd.notna(row.get("source_latest_price")) else None,
            "source_pct_change": pd.to_numeric(row.get("source_pct_change"), errors="coerce") if pd.notna(row.get("source_pct_change")) else None,
            "market_code": (
                None
                if (mc := row.get("market_code")) is None or pd.isna(mc)
                else mc
            ),
        }
        for _, row in stocks_df.iterrows()
    ]


def _popularity_signature_from_rows(rows: list[dict[str, Any]]) -> tuple[tuple[str, int | None], ...]:
    pairs = []
    for row in rows:
        pairs.append(
            (
                normalize_stock_code(row["stock_code"]),
                int(row["popularity_rank"]) if row.get("popularity_rank") is not None else None,
            )
        )
    return tuple(sorted(pairs))


def _popularity_signature_from_frame(stocks_df: pd.DataFrame) -> tuple[tuple[str, int | None], ...]:
    pairs = []
    for _, row in stocks_df.iterrows():
        pairs.append(
            (
                normalize_stock_code(row["stock_code"]),
                int(row["popularity_rank"]) if pd.notna(row.get("popularity_rank")) else None,
            )
        )
    return tuple(sorted(pairs))


async def find_latest_distinct_snapshot_rows(
    session: AsyncSession,
    *,
    current_signature: tuple[tuple[str, int | None], ...] | None = None,
    search_limit: int = 10,
) -> list[dict[str, Any]]:
    snapshot_times = await v2_crud.get_latest_popularity_snapshot_times(session, limit=search_limit)
    for snapshot_time in snapshot_times:
        rows = await v2_crud.get_popularity_snapshot_by_time(session, snapshot_time)
        if not rows:
            continue
        if current_signature is not None and _popularity_signature_from_rows(rows) == current_signature:
            continue
        return rows
    return []


async def get_latest_distinct_snapshots(
    session: AsyncSession,
    *,
    limit: int = 2,
    search_limit: int = 10,
) -> list[tuple[object, list[dict[str, Any]]]]:
    snapshot_times = await v2_crud.get_latest_popularity_snapshot_times(session, limit=search_limit)
    snapshots: list[tuple[object, list[dict[str, Any]]]] = []
    seen_signatures: set[tuple[tuple[str, int | None], ...]] = set()
    for snapshot_time in snapshot_times:
        rows = await v2_crud.get_popularity_snapshot_by_time(session, snapshot_time)
        if not rows:
            continue
        signature = _popularity_signature_from_rows(rows)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        snapshots.append((snapshot_time, rows))
        if len(snapshots) >= limit:
            break
    return snapshots


def compare_stock_sets(previous_rows: list[dict[str, Any]], current_rows: list[dict[str, Any]]) -> dict[str, Any]:
    previous_map = {normalize_stock_code(row["stock_code"]): row for row in previous_rows}
    current_map = {normalize_stock_code(row["stock_code"]): row for row in current_rows}
    new_entries: list[dict[str, Any]] = []
    dropped_entries: list[dict[str, Any]] = []
    rank_changes: list[dict[str, Any]] = []
    for stock_code, row in current_map.items():
        previous = previous_map.get(stock_code)
        current_rank = row.get("popularity_rank") or row.get("current_rank")
        previous_rank = previous.get("popularity_rank") if previous else None
        rank_change = int(previous_rank) - int(current_rank) if previous_rank is not None and current_rank is not None else None
        record = {"stock_code": stock_code, "stock_name": row.get("stock_name"), "current_rank": current_rank, "previous_rank": previous_rank, "rank_change": rank_change}
        if previous is None:
            new_entries.append(record)
        else:
            rank_changes.append(record)
    for stock_code, row in previous_map.items():
        if stock_code not in current_map:
            dropped_entries.append({"stock_code": stock_code, "stock_name": row.get("stock_name"), "previous_rank": row.get("popularity_rank")})
    new_entries.sort(key=lambda item: (item["current_rank"] is None, item["current_rank"], item["stock_code"]))
    dropped_entries.sort(key=lambda item: (item["previous_rank"] is None, item["previous_rank"], item["stock_code"]))
    rank_changes.sort(key=lambda item: (item["current_rank"] is None, item["current_rank"], item["stock_code"]))
    return {"new_entries": new_entries, "dropped_entries": dropped_entries, "rank_changes": rank_changes}


def build_popularity_rows(stocks_df: pd.DataFrame, previous_rows: list[dict[str, Any]], *, run_id: int, trade_date: object, snapshot_time: object) -> list[dict[str, Any]]:
    previous_map = {normalize_stock_code(row["stock_code"]): row for row in previous_rows}
    rows: list[dict[str, Any]] = []
    for _, row in stocks_df.iterrows():
        stock_code = row["stock_code"]
        previous = previous_map.get(stock_code)
        current_rank = int(row["popularity_rank"]) if pd.notna(row.get("popularity_rank")) else None
        previous_rank = previous.get("popularity_rank") if previous else None
        rank_change = int(previous_rank) - current_rank if previous_rank is not None and current_rank is not None else None
        rows.append({
            "run_id": run_id,
            "trade_date": trade_date,
            "snapshot_time": snapshot_time,
            "source": "ths_pywencai",
            "stock_code": stock_code,
            "stock_name": row["stock_name"],
            "popularity_rank": current_rank,
            "popularity_score": float(row["popularity_score"]) if pd.notna(row.get("popularity_score")) else None,
            "latest_price": float(row["source_latest_price"]) if pd.notna(row.get("source_latest_price")) else None,
            "latest_pct_change": float(row["source_pct_change"]) if pd.notna(row.get("source_pct_change")) else None,
            "is_new_entry": previous is None,
            "previous_rank": previous_rank,
            "rank_change": rank_change,
        })
    return rows


async def fetch_popularity_stock_pool() -> pd.DataFrame:
    return standardize_popularity_frame(fetch_top_200_popularity())


async def run_popularity_pipeline(session: AsyncSession) -> dict[str, Any]:
    stocks_df = await fetch_popularity_stock_pool()
    if stocks_df.empty:
        raise ValueError("未获取到同花顺人气前200数据")
    now = pd.Timestamp.now(tz="Asia/Shanghai")
    trade_date = now.date()
    current_signature = _popularity_signature_from_frame(stocks_df)
    previous_rows = await find_latest_distinct_snapshot_rows(
        session,
        current_signature=current_signature,
    )
    run_id = await v2_crud.create_pipeline_run(session, run_type="fetch", source="ths_pywencai", trade_date=trade_date, snapshot_time=now.to_pydatetime())
    stock_rows = build_stock_rows(stocks_df)
    stock_count = await v2_crud.upsert_stocks(session, stock_rows)
    await session.flush()  # 确保 stock_master 记录先写入，避免外键冲突
    popularity_rows = build_popularity_rows(stocks_df, previous_rows, run_id=run_id, trade_date=trade_date, snapshot_time=now.to_pydatetime())
    await v2_crud.insert_popularity_batch(session, popularity_rows)
    comparison = compare_stock_sets(previous_rows, popularity_rows)
    await v2_crud.complete_pipeline_run(session, run_id, status="success", stock_count=stock_count)
    return {"run_id": run_id, "trade_date": trade_date.isoformat(), "snapshot_time": now.isoformat(), "stock_count": stock_count, "new_entry_count": len(comparison["new_entries"]), "data": popularity_rows, "comparison": comparison}
