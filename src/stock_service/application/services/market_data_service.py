from __future__ import annotations

import asyncio
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.application.services.popularity_service import build_stock_rows
from stock_service.crud import v2_crud
from stock_service.infrastructure.config.settings import settings
from stock_service.infrastructure.providers.market_data_hub import (
    benchmark_pct_change,
    fetch_latest_fund_flow,
    fetch_news_rows,
    fetch_quote,
)
from stock_service.infrastructure.providers.stock_code import normalize_stock_code

_MARKET_FETCH_SEM = asyncio.Semaphore(settings.market_fetch_concurrency)
_NEWS_FETCH_SEM = asyncio.Semaphore(settings.news_fetch_concurrency)


def _format_fetch_error(exc: BaseException, *, max_depth: int = 5) -> str:
    """打印异常链，便于看到 raise ... from 里的根因（含 HTTP 状态与响应片段）。"""
    parts: list[str] = [str(exc)]
    cur: BaseException | None = exc
    for _ in range(max_depth):
        nxt = cur.__cause__ if cur is not None else None
        if nxt is None:
            break
        chunk = f"{type(nxt).__name__}: {nxt}"
        resp = getattr(nxt, "response", None)
        if resp is not None:
            try:
                preview = (resp.text or "").replace("\r", " ").replace("\n", " ")
                if len(preview) > 280:
                    preview = preview[:277] + "..."
                chunk += f" | status={resp.status_code} body_preview={preview!r}"
            except Exception:
                chunk += f" | status={getattr(resp, 'status_code', '?')}"
        parts.append(f"<= {chunk}")
        cur = nxt
    return " || ".join(parts)


def _to_optional_db_date(value: Any) -> date | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.date()


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


async def _fetch_one_stock_news(stock_code: str, stock_name: str, run_id: int, max_news_per_stock: int) -> list[dict[str, Any]]:
    async with _NEWS_FETCH_SEM:
        items = await asyncio.to_thread(fetch_news_rows, stock_code, stock_name, max_news_per_stock)
        for item in items:
            item["run_id"] = run_id
        return items


async def fetch_news_to_db(session: AsyncSession, stocks_df: pd.DataFrame, run_id: int, max_news_per_stock: int = 20) -> int:
    tasks = [
        _fetch_one_stock_news(row["stock_code"], row["stock_name"], run_id, max_news_per_stock)
        for _, row in stocks_df.iterrows()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    news_rows: list[dict[str, Any]] = []
    for result, (_, stock_row) in zip(results, stocks_df.iterrows()):
        if isinstance(result, Exception):
            print(f"[news] {stock_row['stock_code']} 获取失败: {result}")
        else:
            news_rows.extend(result)
    if not news_rows:
        return 0
    inserted = await v2_crud.insert_news_batch(session, news_rows)
    print(f"[news] 写入 {inserted} 条新闻记录 (跳过 {len(news_rows) - inserted} 条重复)")
    return inserted


async def _fetch_one_stock_market(stock_code: str, stock_name: str, source_latest_price: Any, source_pct_change: Any) -> dict[str, Any]:
    async with _MARKET_FETCH_SEM:
        def _sync() -> dict[str, Any]:
            quote: dict[str, Any] = {
                "latest_price": None,
                "pct_change": None,
                "change_amount": None,
                "open_price": None,
                "high_price": None,
                "low_price": None,
                "prev_close": None,
                "volume": None,
                "amount": None,
                "volume_ratio": None,
                "turnover_rate": None,
                "amplitude": None,
                "source": None,
            }
            try:
                quote.update(
                    {
                        k: v
                        for k, v in fetch_quote(stock_code).items()
                        if k in quote and v is not None
                    }
                )
            except Exception as exc:
                print(f"[market] {stock_code} 实时行情接口失败: {_format_fetch_error(exc)}")
            if quote["latest_price"] is None and not pd.isna(source_latest_price):
                quote["latest_price"] = float(source_latest_price)
            if quote["pct_change"] is None and not pd.isna(source_pct_change):
                quote["pct_change"] = float(source_pct_change)
            try:
                fund_flow = fetch_latest_fund_flow(stock_code)
            except Exception as exc:
                print(f"[market] {stock_code} 资金流获取失败: {_format_fetch_error(exc)}")
                fund_flow = {
                    "flow_date": None,
                    "main_net_inflow": 0.0,
                    "main_net_inflow_ratio": 0.0,
                }
            flow_date = _to_optional_db_date(fund_flow.get("flow_date"))
            benchmark_pct = None
            relative_strength = None
            try:
                benchmark_pct = benchmark_pct_change(stock_code)
                if quote.get("pct_change") is not None:
                    relative_strength = round(quote["pct_change"] - benchmark_pct, 4)
            except Exception:
                pass
            return {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "trade_date": flow_date,
                **quote,
                "source": quote.get("source") or "mixed",
                "main_net_inflow": fund_flow.get("main_net_inflow", 0.0),
                "main_net_inflow_ratio": fund_flow.get("main_net_inflow_ratio", 0.0),
                "fund_flow_date": flow_date,
                "benchmark_code": "AUTO",
                "benchmark_name": "AUTO",
                "benchmark_pct_change": benchmark_pct,
                "relative_strength_vs_index": relative_strength,
                "source_latest_price": quote.get("latest_price"),
                "source_pct_change": quote.get("pct_change"),
            }
        return await asyncio.to_thread(_sync)


async def fetch_market_to_db(session: AsyncSession, stocks_df: pd.DataFrame, run_id: int) -> int:
    tasks = [
        _fetch_one_stock_market(
            row["stock_code"], row["stock_name"],
            pd.to_numeric(row.get("source_latest_price"), errors="coerce"),
            pd.to_numeric(row.get("source_pct_change"), errors="coerce"),
        )
        for _, row in stocks_df.iterrows()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    now = pd.Timestamp.now(tz="Asia/Shanghai").to_pydatetime()
    market_rows: list[dict[str, Any]] = []
    for result, (_, stock_row) in zip(results, stocks_df.iterrows()):
        if isinstance(result, Exception):
            print(f"[market] {stock_row['stock_code']} 获取失败: {result}")
        else:
            result["run_id"] = run_id
            result["snapshot_time"] = now
            market_rows.append(result)
    if not market_rows:
        return 0
    await v2_crud.insert_market_batch(session, market_rows)
    print(f"[market] 写入 {len(market_rows)} 条行情记录")
    return len(market_rows)


async def compute_and_store_indicators(session: AsyncSession, stock_codes: list[str] | None = None) -> int:
    """从 stock_daily 计算技术指标（ma5/ma20/rsi/macd）并写入 stock_indicator 表"""
    from sqlalchemy import text

    from stock_service.crud import quant_crud
    from stock_service.quant.domain.indicators import TechnicalIndicators

    # 获取有 stock_daily 数据的股票
    if not stock_codes:
        result = await session.execute(text(
            "SELECT DISTINCT code FROM stock_daily ORDER BY code"
        ))
        stock_codes = [row[0] for row in result.fetchall()]

    total = 0
    for code in stock_codes:
        rows = await quant_crud.get_stock_daily(session, code)
        if len(rows) < 26:  # MACD 需要至少 26 天数据
            continue

        df = pd.DataFrame(rows).sort_values("trade_date")
        close = df["close"].astype(float)

        ma5 = TechnicalIndicators.ma(close, 5)
        ma20 = TechnicalIndicators.ma(close, 20)
        rsi = TechnicalIndicators.rsi(close)
        macd_line, _, _ = TechnicalIndicators.macd(close)

        # 只写最新一条指标
        last = df.iloc[-1]
        indicator_row = {
            "code": code,
            "trade_date": last["trade_date"],
            "ma5": round(float(ma5.iloc[-1]), 4) if pd.notna(ma5.iloc[-1]) else None,
            "ma20": round(float(ma20.iloc[-1]), 4) if pd.notna(ma20.iloc[-1]) else None,
            "rsi": round(float(rsi.iloc[-1]), 4) if pd.notna(rsi.iloc[-1]) else None,
            "macd": round(float(macd_line.iloc[-1]), 4) if pd.notna(macd_line.iloc[-1]) else None,
        }
        await quant_crud.batch_upsert_stock_indicator(session, [indicator_row])
        total += 1

    await session.flush()
    print(f"[indicators] 计算了 {total} 只股票的技术指标")
    return total


async def run_fetch_pipeline_for_rows(session: AsyncSession, stock_rows: list[dict[str, Any]], *, run_type: str = "fetch", source: str = "ths_pywencai") -> dict[str, Any]:
    stocks_df = pd.DataFrame(stock_rows)
    if stocks_df.empty:
        raise ValueError("待抓取股票列表为空")
    now = pd.Timestamp.now(tz="Asia/Shanghai")
    trade_date = now.date()
    run_id = await v2_crud.create_pipeline_run(session, run_type=run_type, source=source, trade_date=trade_date, snapshot_time=now.to_pydatetime())
    normalized_rows = build_stock_rows(stocks_df)
    stock_count = await v2_crud.upsert_stocks(session, normalized_rows)
    await session.flush()  # 确保 stock_master 记录先写入，避免外键冲突
    news_count, market_count = await asyncio.gather(
        fetch_news_to_db(session, stocks_df, run_id=run_id),
        fetch_market_to_db(session, stocks_df, run_id=run_id),
    )
    await v2_crud.complete_pipeline_run(session, run_id, status="success", stock_count=stock_count, news_count=news_count, market_count=market_count)
    return {"run_id": run_id, "stock_count": stock_count, "news_count": news_count, "market_count": market_count}
