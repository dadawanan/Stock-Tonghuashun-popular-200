from __future__ import annotations

from typing import Any

import requests

from stock_service.infrastructure.providers.stock_code import (
    from_tencent_symbol,
    normalize_stock_code,
    tencent_symbol,
)


TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q="
TENCENT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
}
DEFAULT_BENCHMARKS = {
    "SH": ["sh000001", "sh000300"],
    "SZ": ["sz399001", "sz399006", "sh000300"],
    "BJ": ["bj899050", "sz399001", "sh000001"],
}


def _to_float(value: str | None, *, multiplier: float = 1.0) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value) * multiplier
    except (TypeError, ValueError):
        return None


def fetch_quotes(stock_codes: list[str]) -> dict[str, dict[str, Any]]:
    if not stock_codes:
        return {}

    symbols = [tencent_symbol(code) for code in stock_codes]
    response = requests.get(
        TENCENT_QUOTE_URL + ",".join(symbols),
        headers=TENCENT_HEADERS,
        timeout=10,
    )
    response.raise_for_status()
    body = response.content.decode("gbk", errors="ignore")

    result: dict[str, dict[str, Any]] = {}
    for line in body.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue
        raw_key = line.split("=", 1)[0].split("_")[-1].strip()
        values = line.split('"')[1].split("~")
        if len(values) < 53:
            continue
        stock_code = from_tencent_symbol(raw_key)
        result[stock_code] = {
            "stock_code": stock_code,
            "stock_name": values[1],
            "latest_price": _to_float(values[3]),
            "prev_close": _to_float(values[4]),
            "open_price": _to_float(values[5]),
            "change_amount": _to_float(values[31]),
            "pct_change": _to_float(values[32]),
            "high_price": _to_float(values[33]),
            "low_price": _to_float(values[34]),
            "amount": _to_float(values[37], multiplier=10000.0),
            "turnover_rate": _to_float(values[38]),
            "pe_ttm": _to_float(values[39]),
            "amplitude": _to_float(values[43]),
            "market_cap": _to_float(values[44], multiplier=100000000.0),
            "float_market_cap": _to_float(values[45], multiplier=100000000.0),
            "pb": _to_float(values[46]),
            "limit_up": _to_float(values[47]),
            "limit_down": _to_float(values[48]),
            "volume_ratio": _to_float(values[49]),
            "pe_static": _to_float(values[52]),
            "source": "tencent",
        }
    return result


def fetch_quote(stock_code: str) -> dict[str, Any]:
    normalized = normalize_stock_code(stock_code)
    quote = fetch_quotes([normalized]).get(normalized)
    if not quote:
        raise RuntimeError(f"腾讯行情为空: {normalized}")
    return quote


def fetch_index_pct_change(symbol: str) -> float:
    response = requests.get(
        TENCENT_QUOTE_URL + symbol,
        headers=TENCENT_HEADERS,
        timeout=10,
    )
    response.raise_for_status()
    body = response.content.decode("gbk", errors="ignore").strip()
    if "=" not in body or '"' not in body:
        raise RuntimeError(f"腾讯指数行情结构异常: {symbol}")
    values = body.split('"')[1].split("~")
    pct = _to_float(values[32] if len(values) > 32 else None)
    if pct is None:
        raise RuntimeError(f"腾讯指数涨跌幅为空: {symbol}")
    return pct


def benchmark_pct_change(stock_code: str) -> float:
    suffix = normalize_stock_code(stock_code).split(".")[-1]
    for symbol in DEFAULT_BENCHMARKS.get(suffix, DEFAULT_BENCHMARKS["SZ"]):
        try:
            return fetch_index_pct_change(symbol)
        except Exception:
            continue
    return 0.0


def fetch_quote_metrics(stock_code: str) -> dict[str, Any]:
    quote = fetch_quote(stock_code)
    return {
        "stock_code": normalize_stock_code(stock_code),
        "pe_ttm": quote.get("pe_ttm"),
        "pe_static": quote.get("pe_static"),
        "pb": quote.get("pb"),
        "market_cap": quote.get("market_cap"),
        "float_market_cap": quote.get("float_market_cap"),
        "turnover_rate": quote.get("turnover_rate"),
        "limit_up": quote.get("limit_up"),
        "limit_down": quote.get("limit_down"),
        "source": quote.get("source", "tencent"),
    }


__all__ = [
    "benchmark_pct_change",
    "code_digits",
    "fetch_index_pct_change",
    "fetch_quote",
    "fetch_quote_metrics",
    "fetch_quotes",
]
