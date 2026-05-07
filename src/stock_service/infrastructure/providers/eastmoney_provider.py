from __future__ import annotations

import hashlib
import math
import time
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
    return normalized.split(".")[-1] if "." in normalized else "SZ"


def stock_market_prefix(stock_code: str) -> str:
    return {"SH": "1", "SZ": "0", "BJ": "0"}.get(stock_market_suffix(stock_code), "0")


def code_digits(stock_code: str) -> str:
    return normalize_stock_code(stock_code).split(".")[0]


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
    payload = request_json(
        EASTMONEY_QUOTE_URL,
        {
            "secid": secid,
            "fields": QUOTE_FIELDS,
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            "invt": "2",
            "fltt": "2",
        },
    )
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
        {
            "secid": index_secid,
            "fields": "f57,f58,f170",
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            "invt": "2",
            "fltt": "2",
        },
    )
    pct = to_float((payload.get("data") or {}).get("f170"), 100.0)
    if pct is None:
        raise RuntimeError(f"指数涨跌幅为空: {index_secid}")
    return pct


def benchmark_pct_change(stock_code: str) -> float:
    for secid, _ in DEFAULT_BENCHMARKS.get(stock_market_suffix(stock_code), DEFAULT_BENCHMARKS["SZ"]):
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
            latest = ak.stock_individual_fund_flow(stock=digits, market=market).tail(1).iloc[0]
            return {
                "flow_date": latest.get("日期"),
                "main_net_inflow": float(latest.get("主力净流入-净额", 0.0)),
                "main_net_inflow_ratio": float(latest.get("主力净流入-净占比", 0.0)),
            }
        except Exception as exc:
            last_error = exc
            time.sleep(attempt)
    raise RuntimeError(f"资金流获取失败: {normalized}") from last_error


def fetch_news_rows(stock_code: str, stock_name: str, max_news_per_stock: int = 20) -> list[dict[str, Any]]:
    digits = code_digits(stock_code)
    try:
        news_df = ak.stock_news_em(symbol=digits).head(max_news_per_stock)
    except Exception as exc:
        raise RuntimeError(f"{stock_code} 新闻获取失败: {exc}") from exc
    if news_df.empty:
        return []

    rename_map = {
        "关键词": "keyword", "新闻标题": "title", "新闻内容": "content",
        "发布时间": "published_at", "文章来源": "source", "新闻链接": "url",
    }
    news_df = news_df.rename(columns=rename_map)
    rows: list[dict[str, Any]] = []
    for _, news_row in news_df.iterrows():
        title = news_row.get("title")
        content = news_row.get("content")
        published_at = pd.to_datetime(news_row.get("published_at"), errors="coerce")
        content_hash_source = f"{stock_code}|{title}|{published_at}|{content}"
        rows.append(
            {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "keyword": news_row.get("keyword", digits),
                "title": title,
                "content": content,
                "published_at": published_at.to_pydatetime() if pd.notna(published_at) else None,
                "source": news_row.get("source"),
                "url": news_row.get("url"),
                "content_hash": hashlib.sha256(content_hash_source.encode("utf-8")).hexdigest(),
            }
        )
    return rows

