from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd

from stock_service.domain.services.analysis_rules import aggregate_news, analyze_market_behavior, analyze_news_records, normalize_stock_code, synthesize_decision
from stock_service.infrastructure.db.database import StockDatabase


def _series_max_non_na(series: pd.Series) -> Any:
    """空序列或非数值列上 pandas .max() 会得到 float nan，不能写入 PG DATE/TIMESTAMP。"""
    clean = series.dropna()
    if clean.empty:
        return None
    val = clean.max()
    try:
        if pd.isna(val):
            return None
    except TypeError:
        pass
    return val


def _to_sql_date(val: Any) -> date | None:
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except TypeError:
        pass
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    ts = pd.Timestamp(val)
    return None if pd.isna(ts) else ts.date()


def _to_sql_datetime(val: Any) -> datetime | None:
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except TypeError:
        pass
    if isinstance(val, datetime):
        return val
    ts = pd.Timestamp(val)
    return None if pd.isna(ts) else ts.to_pydatetime()


async def run_analysis(db: StockDatabase, stock_codes: list[str] | None = None) -> tuple[list[dict[str, object]], dict[str, object]]:
    stocks = await db.get_all_stocks()
    if not stocks:
        raise ValueError("数据库中没有股票数据，请先抓取榜单")
    base_df = pd.DataFrame(stocks)
    news_df = pd.DataFrame(await db.get_all_news())
    market_df = pd.DataFrame(await db.get_market_data())
    if stock_codes:
        normalized_codes = {normalize_stock_code(code) for code in stock_codes}
        base_df = base_df[base_df["stock_code"].isin(normalized_codes)].copy()
        if not news_df.empty:
            news_df = news_df[news_df["stock_code"].map(normalize_stock_code).isin(normalized_codes)].copy()
        if not market_df.empty:
            market_df = market_df[market_df["stock_code"].map(normalize_stock_code).isin(normalized_codes)].copy()
    if base_df.empty:
        raise ValueError("待分析股票列表为空，无法执行分析")
    news_analysis_df = analyze_news_records(news_df)
    news_result = aggregate_news(news_df)
    market_result = analyze_market_behavior(market_df)
    result = base_df.merge(news_result, on="stock_code", how="left").merge(market_result, on="stock_code", how="left")
    result["text_score"] = pd.to_numeric(result["text_score"], errors="coerce").fillna(0.0)
    result["market_score"] = pd.to_numeric(result["market_score"], errors="coerce").fillna(0.0)
    result["integrated_score"] = (result["text_score"] * 0.55 + result["market_score"] * 0.45).round(2)
    result["decision"] = result.apply(synthesize_decision, axis=1)
    for column in ["event_types", "text_event_label", "sentiment_strength", "duration_tag", "fact_support", "bullish_logic", "bearish_logic", "price_volume_signal", "fund_flow_signal", "behavior_label"]:
        result[column] = result[column].fillna("暂无数据")
    result["news_count"] = pd.to_numeric(result["news_count"], errors="coerce").fillna(0).astype(int)
    result = result.sort_values(["integrated_score", "news_count"], ascending=[False, False])
    result.attrs["news_analysis_rows"] = news_analysis_df.to_dict("records")
    td_raw = (
        _series_max_non_na(market_df["trade_date"])
        if "trade_date" in market_df.columns and not market_df.empty
        else None
    )
    st_raw = (
        _series_max_non_na(market_df["snapshot_time"])
        if "snapshot_time" in market_df.columns and not market_df.empty
        else None
    )
    result.attrs["latest_trade_date"] = _to_sql_date(td_raw)
    result.attrs["latest_snapshot_time"] = _to_sql_datetime(st_raw)
    return result.to_dict("records"), result.attrs


async def store_analysis_results(db: StockDatabase, results: list[dict[str, Any]], meta: dict[str, Any], *, run_type: str, source: str = "rule") -> int:
    run_id = await db.create_pipeline_run(run_type=run_type, source=source)
    try:
        news_analysis_rows = meta.get("news_analysis_rows", [])
        article_ids = [row["article_id"] for row in news_analysis_rows if row.get("article_id") is not None]
        if news_analysis_rows:
            await db.replace_news_analysis_batch(run_id, news_analysis_rows, article_ids)
        for row in results:
            row["run_id"] = run_id
            row["trade_date"] = meta.get("latest_trade_date")
            row["snapshot_time"] = meta.get("latest_snapshot_time")
            row["reasoning_json"] = {
                "text_event_label": row.get("text_event_label"),
                "fund_flow_signal": row.get("fund_flow_signal"),
                "behavior_label": row.get("behavior_label"),
                "decision": row.get("decision"),
            }
        count = await db.insert_stock_analysis_batch(results)
        await db.complete_pipeline_run(run_id, status="success", analysis_count=count)
        return count
    except Exception as exc:
        await db.complete_pipeline_run(run_id, status="failed", error_message=str(exc))
        raise


async def run_and_store(db: StockDatabase, stock_codes: list[str] | None = None) -> int:
    results, meta = await run_analysis(db, stock_codes=stock_codes)
    count = await store_analysis_results(db, results, meta, run_type="analyze", source="rule")
    print(f"[analysis] 写入 {count} 条分析结果")
    return count

