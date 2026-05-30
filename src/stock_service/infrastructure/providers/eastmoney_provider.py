from __future__ import annotations

import hashlib
import math
import random
import time
from typing import Any

import akshare as ak
import pandas as pd
from curl_cffi import requests as curl_requests

from stock_service.infrastructure.providers.stock_code import (
    code_digits,
    eastmoney_market_prefix as stock_market_prefix,
    normalize_stock_code,
    stock_market_suffix,
)

# 资金流请求限速：全局最小间隔 + 随机抖动
_FUND_FLOW_MIN_INTERVAL = 1.5
_FUND_FLOW_JITTER = 1.0  # 随机 0~1s 抖动
_last_fund_flow_ts: float = 0.0

# 随机 User-Agent 池
_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
]
##  暂时无用

EASTMONEY_QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
}
# f58 为证券简称；缺少则 quote 里 stock_name 恒为空
QUOTE_FIELDS = "f43,f44,f45,f46,f47,f48,f50,f58,f168,f169,f170,f171"
DEFAULT_BENCHMARKS = {
    "SH": [("1.000001", "上证指数"), ("0.399001", "深证成指")],
    "SZ": [("0.399001", "深证成指"), ("1.000001", "上证指数")],
    "BJ": [("0.899050", "北证50"), ("0.399001", "深证成指"), ("1.000001", "上证指数")],
}
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
    """通过东方财富 push2 实时接口获取个股资金流数据。

    接口: http://push2.eastmoney.com/api/qt/stock/fflow/kline/get
    返回 klines 格式: "日期时间,主力净流入,小单净流入,中单净流入,大单净流入,超大单净流入"
    """
    global _last_fund_flow_ts

    normalized = normalize_stock_code(stock_code)
    secid = f"{stock_market_prefix(normalized)}.{code_digits(normalized)}"

    # 限速：最小间隔 + 随机抖动，避免批量请求被封
    elapsed = time.time() - _last_fund_flow_ts
    wait = _FUND_FLOW_MIN_INTERVAL + random.uniform(0, _FUND_FLOW_JITTER) - elapsed
    if wait > 0:
        time.sleep(wait)

    url = "http://push2.eastmoney.com/api/qt/stock/fflow/kline/get"
    params = {
        "lmt": "1",
        "klt": "1",
        "secid": secid,
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
    }

    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            _last_fund_flow_ts = time.time()
            resp = curl_requests.get(
                url,
                params=params,
                headers={
                    "User-Agent": random.choice(_USER_AGENTS),
                    "Referer": "https://quote.eastmoney.com/",
                },
                timeout=15,
                impersonate="chrome124",
            )
            resp.raise_for_status()
            payload = resp.json()

            klines = (payload.get("data") or {}).get("klines") or []
            if not klines:
                raise RuntimeError(f"资金流数据为空: {normalized}")

            # 解析最后一行: "2026-05-28 10:42,-129635837.0,105428867.0,24206977.0,-48623317.0,-81012520.0"
            fields = klines[-1].split(",")
            if len(fields) < 6:
                raise RuntimeError(f"资金流字段不足: {klines[-1]}")

            flow_date = fields[0].split(" ")[0] if " " in fields[0] else fields[0]
            main_net_inflow = float(fields[1])

            # 计算主力净占比：主力净流入 / (主力+小单+中单+大单+超大单 的绝对值之和)
            try:
                abs_sum = sum(abs(float(f)) for f in fields[1:6])
                main_ratio = round(main_net_inflow / abs_sum * 100, 4) if abs_sum > 0 else 0.0
            except (ValueError, ZeroDivisionError):
                main_ratio = 0.0

            return {
                "flow_date": flow_date,
                "main_net_inflow": main_net_inflow,
                "main_net_inflow_ratio": main_ratio,
                "source": "eastmoney_push2",
            }
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(attempt * 2)
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
