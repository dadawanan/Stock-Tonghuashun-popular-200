from __future__ import annotations

import argparse
import math
import time
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd
from curl_cffi import requests as curl_requests


EASTMONEY_QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
}
QUOTE_FIELDS = "f43,f44,f45,f46,f47,f48,f50,f57,f58,f60,f168,f169,f170,f171"
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
    result = result.rename(columns=rename_map)
    keep_columns = [column for column in ["stock_code", "stock_name", "source_latest_price", "source_pct_change"] if column in result.columns]
    result = result[keep_columns].copy()
    result["stock_code"] = result["stock_code"].map(normalize_stock_code)
    return result.drop_duplicates(subset=["stock_code"]).reset_index(drop=True)


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
                url,
                params=params,
                headers=DEFAULT_HEADERS,
                timeout=15,
                impersonate="chrome124",
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001
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
        except Exception:  # noqa: BLE001
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
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(attempt)

    raise RuntimeError(f"资金流获取失败: {normalized}") from last_error


def generate_news_data(stocks_df: pd.DataFrame, output_file: Path, max_news_per_stock: int = 20) -> Path:
    rows: list[dict[str, Any]] = []
    for _, row in stocks_df.iterrows():
        stock_code = row["stock_code"]
        stock_name = row["stock_name"]
        digits = code_digits(stock_code)
        try:
            news_df = ak.stock_news_em(symbol=digits).head(max_news_per_stock)
        except Exception as exc:  # noqa: BLE001
            print(f"[news] {stock_code} 获取失败: {exc}")
            continue

        if news_df.empty:
            print(f"[news] {stock_code} 未抓到新闻")
            continue

        rename_map = {
            "关键词": "keyword",
            "新闻标题": "title",
            "新闻内容": "content",
            "发布时间": "published_at",
            "文章来源": "source",
            "新闻链接": "url",
        }
        news_df = news_df.rename(columns=rename_map)
        for _, news_row in news_df.iterrows():
            rows.append(
                {
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "keyword": news_row.get("keyword", digits),
                    "title": news_row.get("title"),
                    "content": news_row.get("content"),
                    "published_at": news_row.get("published_at"),
                    "source": news_row.get("source"),
                    "url": news_row.get("url"),
                }
            )
        time.sleep(0.3)

    news_output = pd.DataFrame(rows)
    news_output.to_csv(output_file, index=False, encoding="utf-8-sig")
    return output_file


def generate_market_data(stocks_df: pd.DataFrame, output_file: Path) -> Path:
    rows: list[dict[str, Any]] = []

    for _, row in stocks_df.iterrows():
        stock_code = row["stock_code"]
        stock_name = row["stock_name"]
        source_latest_price = pd.to_numeric(row.get("source_latest_price"), errors="coerce")
        source_pct_change = pd.to_numeric(row.get("source_pct_change"), errors="coerce")
        quote: dict[str, Any] = {
            "latest_price": None if pd.isna(source_latest_price) else float(source_latest_price),
            "pct_change": None if pd.isna(source_pct_change) else float(source_pct_change),
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
        }

        if quote.get("latest_price") is None or quote.get("pct_change") is None:
            try:
                quote.update({k: v for k, v in fetch_quote(stock_code).items() if k in quote and v is not None})
            except Exception as exc:  # noqa: BLE001
                print(f"[market] {stock_code} 实时行情接口失败，且榜单无兜底数据: {exc}")

        try:
            fund_flow = fetch_latest_fund_flow(stock_code)
        except Exception as exc:  # noqa: BLE001
            print(f"[market] {stock_code} 资金流获取失败: {exc}")
            fund_flow = {
                "flow_date": None,
                "main_net_inflow": 0.0,
                "main_net_inflow_ratio": 0.0,
            }
        pct_change = quote.get("pct_change")

        rows.append(
            {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "latest_price": quote.get("latest_price"),
                "pct_change": pct_change,
                "change_amount": quote.get("change_amount"),
                "open_price": quote.get("open_price"),
                "high_price": quote.get("high_price"),
                "low_price": quote.get("low_price"),
                "prev_close": quote.get("prev_close"),
                "volume": quote.get("volume"),
                "amount": quote.get("amount"),
                "volume_ratio": quote.get("volume_ratio"),
                "turnover_rate": quote.get("turnover_rate"),
                "amplitude": quote.get("amplitude"),
                "main_net_inflow": fund_flow.get("main_net_inflow", 0.0),
                "main_net_inflow_ratio": fund_flow.get("main_net_inflow_ratio", 0.0),
                "fund_flow_date": fund_flow.get("flow_date"),
                "benchmark_pct_change": None,
                "relative_strength_vs_index": None,
            }
        )
        time.sleep(0.2)

    market_output = pd.DataFrame(rows)
    market_output.to_csv(output_file, index=False, encoding="utf-8-sig")
    return output_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch real news and market data for selected stocks.")
    parser.add_argument("--stocks", default="新增股票.csv", help="Input stock pool CSV.")
    parser.add_argument("--news-output", default="news_data.csv", help="Output CSV for news data.")
    parser.add_argument("--market-output", default="market_data.csv", help="Output CSV for market data.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    stocks_df = read_stock_pool(Path(args.stocks))
    news_path = generate_news_data(stocks_df, Path(args.news_output))
    market_path = generate_market_data(stocks_df, Path(args.market_output))
    print(f"news_data 输出: {news_path}")
    print(f"market_data 输出: {market_path}")


if __name__ == "__main__":
    main()
