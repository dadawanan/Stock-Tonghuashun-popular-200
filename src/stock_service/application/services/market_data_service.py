from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pandas as pd

from stock_service.application.services.popularity_service import build_stock_rows
from stock_service.infrastructure.db.database import StockDatabase
from stock_service.infrastructure.providers.eastmoney_provider import benchmark_pct_change, fetch_latest_fund_flow, fetch_news_rows, fetch_quote, normalize_stock_code


def read_stock_pool(stocks_file: Path) -> pd.DataFrame:
    stocks_df = pd.read_csv(stocks_file, encoding="utf-8-sig")
    code_col = "股票代码" if "股票代码" in stocks_df.columns else stocks_df.columns[0]
    name_col = "股票简称" if "股票简称" in stocks_df.columns else stocks_df.columns[1]
    result = stocks_df.rename(columns={code_col: "stock_code", name_col: "stock_name"})
    if "最新价" in result.columns:
        result = result.rename(columns={"最新价": "source_latest_price"})
    if "最新涨跌幅" in result.columns:
        result = result.rename(columns={"最新涨跌幅": "source_pct_change"})
    result["stock_code"] = result["stock_code"].map(normalize_stock_code)
    return result.drop_duplicates(subset=["stock_code"]).reset_index(drop=True)


async def fetch_news_to_db(db: StockDatabase, stocks_df: pd.DataFrame, run_id: int, max_news_per_stock: int = 20) -> int:
    news_rows: list[dict[str, Any]] = []
    for _, row in stocks_df.iterrows():
        try:
            for item in fetch_news_rows(row["stock_code"], row["stock_name"], max_news_per_stock=max_news_per_stock):
                item["run_id"] = run_id
                news_rows.append(item)
        except Exception as exc:
            print(f"[news] {row['stock_code']} 获取失败: {exc}")
        time.sleep(0.3)
    if not news_rows:
        return 0
    count = await db.insert_news_batch(news_rows)
    print(f"[news] 写入 {count} 条新闻记录")
    return count


async def fetch_market_to_db(db: StockDatabase, stocks_df: pd.DataFrame, run_id: int) -> int:
    market_rows: list[dict[str, Any]] = []
    for _, row in stocks_df.iterrows():
        stock_code = row["stock_code"]
        source_latest_price = pd.to_numeric(row.get("source_latest_price"), errors="coerce")
        source_pct_change = pd.to_numeric(row.get("source_pct_change"), errors="coerce")
        quote: dict[str, Any] = {
            "latest_price": None if pd.isna(source_latest_price) else float(source_latest_price),
            "pct_change": None if pd.isna(source_pct_change) else float(source_pct_change),
            "change_amount": None, "open_price": None, "high_price": None, "low_price": None,
            "prev_close": None, "volume": None, "amount": None, "volume_ratio": None,
            "turnover_rate": None, "amplitude": None,
        }
        if quote["latest_price"] is None or quote["pct_change"] is None:
            try:
                quote.update({k: v for k, v in fetch_quote(stock_code).items() if k in quote and v is not None})
            except Exception as exc:
                print(f"[market] {stock_code} 实时行情接口失败: {exc}")
        try:
            fund_flow = fetch_latest_fund_flow(stock_code)
        except Exception as exc:
            print(f"[market] {stock_code} 资金流获取失败: {exc}")
            fund_flow = {"flow_date": None, "main_net_inflow": 0.0, "main_net_inflow_ratio": 0.0}
        benchmark_pct = None
        relative_strength = None
        try:
            benchmark_pct = benchmark_pct_change(stock_code)
            if quote.get("pct_change") is not None:
                relative_strength = round(quote["pct_change"] - benchmark_pct, 4)
        except Exception:
            pass
        market_rows.append({
            "run_id": run_id,
            "stock_code": stock_code,
            "stock_name": row["stock_name"],
            "trade_date": fund_flow.get("flow_date"),
            "snapshot_time": pd.Timestamp.now(tz="Asia/Shanghai").to_pydatetime(),
            **quote,
            "main_net_inflow": fund_flow.get("main_net_inflow", 0.0),
            "main_net_inflow_ratio": fund_flow.get("main_net_inflow_ratio", 0.0),
            "fund_flow_date": fund_flow.get("flow_date"),
            "benchmark_code": "AUTO",
            "benchmark_name": "AUTO",
            "benchmark_pct_change": benchmark_pct,
            "relative_strength_vs_index": relative_strength,
            "source_latest_price": quote.get("latest_price"),
            "source_pct_change": quote.get("pct_change"),
        })
        time.sleep(0.2)
    if not market_rows:
        return 0
    count = await db.insert_market_batch(market_rows)
    print(f"[market] 写入 {count} 条行情记录")
    return count


async def run_fetch_pipeline_for_rows(stock_rows: list[dict[str, Any]], *, run_type: str = "fetch", source: str = "ths_pywencai") -> dict[str, Any]:
    db = StockDatabase()
    await db.initialize()
    run_id: int | None = None
    try:
        stocks_df = pd.DataFrame(stock_rows)
        if stocks_df.empty:
            raise ValueError("待抓取股票列表为空")
        now = pd.Timestamp.now(tz="Asia/Shanghai")
        trade_date = now.date()
        run_id = await db.create_pipeline_run(run_type=run_type, source=source, trade_date=trade_date, snapshot_time=now.to_pydatetime())
        normalized_rows = build_stock_rows(stocks_df)
        stock_count = await db.upsert_stocks(normalized_rows)
        news_count = await fetch_news_to_db(db, stocks_df, run_id=run_id)
        market_count = await fetch_market_to_db(db, stocks_df, run_id=run_id)
        await db.complete_pipeline_run(run_id, status="success", stock_count=stock_count, news_count=news_count, market_count=market_count)
        return {"run_id": run_id, "stock_count": stock_count, "news_count": news_count, "market_count": market_count}
    except Exception as exc:
        if run_id is not None:
            await db.complete_pipeline_run(run_id, status="failed", error_message=str(exc))
        raise
    finally:
        await db.close()

