from __future__ import annotations

import argparse
import hashlib
import math
import time
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd
from curl_cffi import requests as curl_requests

from database import StockDatabase
from get_popularity import get_top_200_popularity


EASTMONEY_QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
}
QUOTE_FIELDS = "f43,f44,f45,f46,f47,f48,f50,f168,f169,f170,f171"
DEFAULT_BENCHMARKS = {
    "SH": [("1.000001", "上证指数"), ("0.399001", "深证成指")],
    "SZ": [("0.399001", "深证成指"), ("1.000001", "上证指数")],
    "BJ": [("0.899050", "北证50"), ("0.399001", "深证成指"), ("1.000001", "上证指数")],
}


def normalize_stock_code(value: object) -> str:
    text = str(value).strip().upper()
    if "." in text:
        return text
    if text.isdigit() and len(text) == 6:
        if text.startswith(("6", "9")):
            return f"{text}.SH"
        if text.startswith("8"):
            return f"{text}.BJ"
        return f"{text}.SZ"
    return text


def stock_market_suffix(stock_code: str) -> str:
    normalized = normalize_stock_code(stock_code)
    if "." in normalized:
        return normalized.split(".")[-1]
    return "SZ"


def stock_market_prefix(stock_code: str) -> str:
    suffix = stock_market_suffix(stock_code)
    return {"SH": "1", "SZ": "0", "BJ": "0"}.get(suffix, "0")


def code_digits(stock_code: str) -> str:
    return normalize_stock_code(stock_code).split(".")[0]


def read_stock_pool(stocks_file: Path) -> pd.DataFrame:
    stocks_df = pd.read_csv(stocks_file, encoding="utf-8-sig")
    code_col = "股票代码" if "股票代码" in stocks_df.columns else stocks_df.columns[0]
    name_col = "股票简称" if "股票简称" in stocks_df.columns else stocks_df.columns[1]
    result = stocks_df.copy()
    rename_map = {code_col: "stock_code", name_col: "stock_name"}
    if "最新价" in result.columns:
        rename_map["最新价"] = "source_latest_price"
    if "最新涨跌幅" in result.columns:
        rename_map["最新涨跌幅"] = "source_pct_change"
    for column in result.columns:
        if column.startswith("个股热度排名["):
            rename_map[column] = "popularity_rank"
        if column.startswith("个股热度["):
            rename_map[column] = "popularity_score"
    if "market_code" in result.columns:
        rename_map["market_code"] = "market_code"
    result = result.rename(columns=rename_map)
    keep_columns = [
        c for c in [
            "stock_code", "stock_name", "source_latest_price", "source_pct_change",
            "popularity_rank", "popularity_score", "market_code",
        ] if c in result.columns
    ]
    result = result[keep_columns].copy()
    result["stock_code"] = result["stock_code"].map(normalize_stock_code)
    return result.drop_duplicates(subset=["stock_code"]).reset_index(drop=True)


def standardize_popularity_frame(raw_df: pd.DataFrame) -> pd.DataFrame:
    if raw_df is None or raw_df.empty:
        return pd.DataFrame(
            columns=[
                "stock_code", "stock_name", "source_latest_price", "source_pct_change",
                "popularity_rank", "popularity_score", "market_code",
            ]
        )

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

    keep_columns = [
        column for column in [
            "stock_code", "stock_name", "source_latest_price", "source_pct_change",
            "popularity_rank", "popularity_score", "market_code",
        ] if column in result.columns
    ]
    result = result[keep_columns].copy()
    result["stock_code"] = result["stock_code"].map(normalize_stock_code)
    result["stock_name"] = result["stock_name"].fillna("").astype(str).str.strip()

    numeric_columns = ["source_latest_price", "source_pct_change", "popularity_rank", "popularity_score"]
    for column in numeric_columns:
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
            "market_code": row.get("market_code"),
        }
        for _, row in stocks_df.iterrows()
    ]


def compare_stock_sets(previous_rows: list[dict[str, Any]], current_rows: list[dict[str, Any]]) -> dict[str, Any]:
    previous_map = {normalize_stock_code(row["stock_code"]): row for row in previous_rows}
    current_map = {normalize_stock_code(row["stock_code"]): row for row in current_rows}

    new_entries: list[dict[str, Any]] = []
    dropped_entries: list[dict[str, Any]] = []
    rank_changes: list[dict[str, Any]] = []

    for stock_code, row in current_map.items():
        previous = previous_map.get(stock_code)
        current_rank = row.get("popularity_rank")
        previous_rank = previous.get("popularity_rank") if previous else None
        rank_change = None
        if previous_rank is not None and current_rank is not None:
            rank_change = int(previous_rank) - int(current_rank)

        record = {
            "stock_code": stock_code,
            "stock_name": row.get("stock_name"),
            "current_rank": current_rank,
            "previous_rank": previous_rank,
            "rank_change": rank_change,
        }
        if previous is None:
            new_entries.append(record)
        else:
            rank_changes.append(record)

    for stock_code, row in previous_map.items():
        if stock_code not in current_map:
            dropped_entries.append(
                {
                    "stock_code": stock_code,
                    "stock_name": row.get("stock_name"),
                    "previous_rank": row.get("popularity_rank"),
                }
            )

    new_entries.sort(key=lambda item: (item["current_rank"] is None, item["current_rank"], item["stock_code"]))
    dropped_entries.sort(key=lambda item: (item["previous_rank"] is None, item["previous_rank"], item["stock_code"]))
    rank_changes.sort(key=lambda item: (item["current_rank"] is None, item["current_rank"], item["stock_code"]))
    return {
        "new_entries": new_entries,
        "dropped_entries": dropped_entries,
        "rank_changes": rank_changes,
    }


def build_popularity_rows(
    stocks_df: pd.DataFrame,
    previous_rows: list[dict[str, Any]],
    *,
    run_id: int,
    trade_date: object,
    snapshot_time: object,
) -> list[dict[str, Any]]:
    previous_map = {normalize_stock_code(row["stock_code"]): row for row in previous_rows}
    popularity_rows: list[dict[str, Any]] = []

    for _, row in stocks_df.iterrows():
        stock_code = row["stock_code"]
        previous = previous_map.get(stock_code)
        current_rank = int(row["popularity_rank"]) if pd.notna(row.get("popularity_rank")) else None
        previous_rank = previous.get("popularity_rank") if previous else None
        rank_change = None
        if previous_rank is not None and current_rank is not None:
            rank_change = int(previous_rank) - current_rank

        popularity_rows.append(
            {
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
            }
        )

    return popularity_rows


async def fetch_popularity_stock_pool() -> pd.DataFrame:
    return standardize_popularity_frame(get_top_200_popularity())


def to_float(value: Any, divisor: float = 1.0) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        return float(value) / divisor
    except (TypeError, ValueError):
        return None


def request_json(url: str, params: dict[str, Any], retries: int = 3, delay: float = 1.0) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = curl_requests.get(
                url, params=params, headers=DEFAULT_HEADERS, timeout=15, impersonate="chrome124",
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(delay * attempt)
    raise RuntimeError(f"请求失败: {url} params={params}") from last_error


def fetch_quote(stock_code: str) -> dict[str, Any]:
    normalized = normalize_stock_code(stock_code)
    secid = f"{stock_market_prefix(normalized)}.{code_digits(normalized)}"
    params = {
        "secid": secid,
        "fields": QUOTE_FIELDS,
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "invt": "2",
        "fltt": "2",
    }
    payload = request_json(EASTMONEY_QUOTE_URL, params=params)
    data = payload.get("data") or {}
    prev_close = to_float(data.get("f60"), 100.0)
    high_price = to_float(data.get("f44"), 100.0)
    low_price = to_float(data.get("f45"), 100.0)
    amplitude = to_float(data.get("f171"), 100.0)
    if amplitude is None and prev_close and high_price is not None and low_price is not None:
        amplitude = round((high_price - low_price) / prev_close * 100, 2)

    return {
        "stock_code": normalized,
        "stock_name": data.get("f58"),
        "latest_price": to_float(data.get("f43"), 100.0),
        "pct_change": to_float(data.get("f170"), 100.0),
        "change_amount": to_float(data.get("f169"), 100.0),
        "open_price": to_float(data.get("f46"), 100.0),
        "high_price": high_price,
        "low_price": low_price,
        "prev_close": prev_close,
        "volume": to_float(data.get("f47"), 1.0),
        "amount": to_float(data.get("f48"), 1.0),
        "volume_ratio": to_float(data.get("f50"), 100.0),
        "turnover_rate": to_float(data.get("f168"), 100.0),
        "amplitude": amplitude,
    }


def fetch_index_pct_change(index_secid: str) -> float:
    payload = request_json(
        EASTMONEY_QUOTE_URL,
        params={
            "secid": index_secid,
            "fields": "f57,f58,f170",
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            "invt": "2",
            "fltt": "2",
        },
    )
    data = payload.get("data") or {}
    pct = to_float(data.get("f170"), 100.0)
    if pct is None:
        raise RuntimeError(f"指数涨跌幅为空: {index_secid}")
    return pct


def benchmark_pct_change(stock_code: str) -> float:
    suffix = stock_market_suffix(stock_code)
    candidates = DEFAULT_BENCHMARKS.get(suffix, DEFAULT_BENCHMARKS["SZ"])
    for secid, _ in candidates:
        try:
            return fetch_index_pct_change(secid)
        except Exception:
            continue
    return 0.0


def fetch_latest_fund_flow(stock_code: str) -> dict[str, Any]:
    normalized = normalize_stock_code(stock_code)
    digits = code_digits(normalized)
    market = "sh" if stock_market_suffix(normalized) == "SH" else "sz"

    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            fund_df = ak.stock_individual_fund_flow(stock=digits, market=market)
            latest = fund_df.tail(1).iloc[0]
            return {
                "flow_date": latest.get("日期"),
                "main_net_inflow": float(latest.get("主力净流入-净额", 0.0)),
                "main_net_inflow_ratio": float(latest.get("主力净流入-净占比", 0.0)),
            }
        except Exception as exc:
            last_error = exc
            time.sleep(attempt)

    raise RuntimeError(f"资金流获取失败: {normalized}") from last_error


async def fetch_news_to_db(db: StockDatabase, stocks_df: pd.DataFrame, run_id: int, max_news_per_stock: int = 20) -> int:
    news_rows: list[dict[str, Any]] = []
    for _, row in stocks_df.iterrows():
        stock_code = row["stock_code"]
        stock_name = row["stock_name"]
        digits = code_digits(stock_code)
        try:
            news_df = ak.stock_news_em(symbol=digits).head(max_news_per_stock)
        except Exception as exc:
            print(f"[news] {stock_code} 获取失败: {exc}")
            continue

        if news_df.empty:
            print(f"[news] {stock_code} 未抓到新闻")
            continue

        rename_map = {
            "关键词": "keyword", "新闻标题": "title", "新闻内容": "content",
            "发布时间": "published_at", "文章来源": "source", "新闻链接": "url",
        }
        news_df = news_df.rename(columns=rename_map)
        for _, news_row in news_df.iterrows():
            title = news_row.get("title")
            content = news_row.get("content")
            published_at = pd.to_datetime(news_row.get("published_at"), errors="coerce")
            content_hash_source = f"{stock_code}|{title}|{published_at}|{content}"
            news_rows.append({
                "run_id": run_id,
                "stock_code": stock_code,
                "stock_name": stock_name,
                "keyword": news_row.get("keyword", digits),
                "title": title,
                "content": content,
                "published_at": published_at.to_pydatetime() if pd.notna(published_at) else None,
                "source": news_row.get("source"),
                "url": news_row.get("url"),
                "content_hash": hashlib.sha256(content_hash_source.encode("utf-8")).hexdigest(),
            })
        time.sleep(0.3)

    if news_rows:
        count = await db.insert_news_batch(news_rows)
        print(f"[news] 写入 {count} 条新闻记录")
        return count
    return 0


async def fetch_market_to_db(db: StockDatabase, stocks_df: pd.DataFrame, run_id: int) -> int:
    market_rows: list[dict[str, Any]] = []

    for _, row in stocks_df.iterrows():
        stock_code = row["stock_code"]
        stock_name = row["stock_name"]
        source_latest_price = pd.to_numeric(row.get("source_latest_price"), errors="coerce")
        source_pct_change = pd.to_numeric(row.get("source_pct_change"), errors="coerce")
        quote: dict[str, Any] = {
            "latest_price": None if pd.isna(source_latest_price) else float(source_latest_price),
            "pct_change": None if pd.isna(source_pct_change) else float(source_pct_change),
            "change_amount": None, "open_price": None, "high_price": None, "low_price": None,
            "prev_close": None, "volume": None, "amount": None,
            "volume_ratio": None, "turnover_rate": None, "amplitude": None,
        }

        if quote.get("latest_price") is None or quote.get("pct_change") is None:
            try:
                quote.update({k: v for k, v in fetch_quote(stock_code).items() if k in quote and v is not None})
            except Exception as exc:
                print(f"[market] {stock_code} 实时行情接口失败，且榜单无兜底数据: {exc}")

        try:
            fund_flow = fetch_latest_fund_flow(stock_code)
        except Exception as exc:
            print(f"[market] {stock_code} 资金流获取失败: {exc}")
            fund_flow = {"flow_date": None, "main_net_inflow": 0.0, "main_net_inflow_ratio": 0.0}

        pct_change = quote.get("pct_change")
        benchmark_pct = None
        relative_strength = None
        try:
            benchmark_pct = benchmark_pct_change(stock_code)
            if pct_change is not None and benchmark_pct is not None:
                relative_strength = round(pct_change - benchmark_pct, 4)
        except Exception:
            pass

        market_rows.append({
            "run_id": run_id,
            "stock_code": stock_code,
            "stock_name": stock_name,
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

    if market_rows:
        count = await db.insert_market_batch(market_rows)
        print(f"[market] 写入 {count} 条行情记录")
        return count
    return 0


async def run_popularity_pipeline() -> dict[str, Any]:
    db = StockDatabase()
    await db.initialize()
    run_id: int | None = None
    try:
        stocks_df = await fetch_popularity_stock_pool()
        if stocks_df.empty:
            raise ValueError("未获取到同花顺人气前200数据")

        now = pd.Timestamp.now(tz="Asia/Shanghai")
        trade_date = now.date()
        previous_times = await db.get_latest_popularity_snapshot_times(limit=1)
        previous_rows = await db.get_popularity_snapshot_by_time(previous_times[0]) if previous_times else []

        run_id = await db.create_pipeline_run(
            run_type="fetch",
            source="ths_pywencai",
            trade_date=trade_date,
            snapshot_time=now.to_pydatetime(),
        )

        stock_rows = build_stock_rows(stocks_df)
        stock_count = await db.upsert_stocks(stock_rows)
        popularity_rows = build_popularity_rows(
            stocks_df,
            previous_rows,
            run_id=run_id,
            trade_date=trade_date,
            snapshot_time=now.to_pydatetime(),
        )
        await db.insert_popularity_batch(popularity_rows)

        comparison = compare_stock_sets(previous_rows, popularity_rows)
        await db.complete_pipeline_run(
            run_id,
            status="success",
            stock_count=stock_count,
        )
        return {
            "run_id": run_id,
            "trade_date": trade_date.isoformat(),
            "snapshot_time": now.isoformat(),
            "stock_count": stock_count,
            "new_entry_count": len(comparison["new_entries"]),
            "data": popularity_rows,
            "comparison": comparison,
        }
    except Exception as exc:
        if run_id is not None:
            await db.complete_pipeline_run(run_id, status="failed", error_message=str(exc))
        raise
    finally:
        await db.close()


async def run_fetch_pipeline_for_rows(
    stock_rows: list[dict[str, Any]],
    *,
    run_type: str = "fetch",
    source: str = "ths_pywencai",
) -> dict[str, Any]:
    db = StockDatabase()
    await db.initialize()
    run_id: int | None = None
    try:
        stocks_df = pd.DataFrame(stock_rows)
        if stocks_df.empty:
            raise ValueError("待抓取股票列表为空")

        now = pd.Timestamp.now(tz="Asia/Shanghai")
        trade_date = now.date()
        run_id = await db.create_pipeline_run(
            run_type=run_type,
            source=source,
            trade_date=trade_date,
            snapshot_time=now.to_pydatetime(),
        )
        normalized_rows = build_stock_rows(stocks_df)
        stock_count = await db.upsert_stocks(normalized_rows)
        news_count = await fetch_news_to_db(db, stocks_df, run_id=run_id)
        market_count = await fetch_market_to_db(db, stocks_df, run_id=run_id)
        await db.complete_pipeline_run(
            run_id,
            status="success",
            stock_count=stock_count,
            news_count=news_count,
            market_count=market_count,
        )
        return {
            "run_id": run_id,
            "stock_count": stock_count,
            "news_count": news_count,
            "market_count": market_count,
        }
    except Exception as exc:
        if run_id is not None:
            await db.complete_pipeline_run(run_id, status="failed", error_message=str(exc))
        raise
    finally:
        await db.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch real news and market data for selected stocks.")
    parser.add_argument("--stocks", default="新增股票.csv", help="Input stock pool CSV.")
    return parser


async def main_async() -> None:
    args = build_parser().parse_args()
    await run_fetch_pipeline(args.stocks)


async def run_fetch_pipeline(stocks_file: str = "新增股票.csv") -> None:
    stocks_df = read_stock_pool(Path(stocks_file))
    await run_fetch_pipeline_for_rows(stocks_df.to_dict("records"))


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
