from __future__ import annotations

import time
from typing import Any

from stock_service.infrastructure.config.settings import settings
from stock_service.infrastructure.providers.akshare_provider import (
    fetch_latest_fund_flow as fetch_latest_fund_flow_akshare,
    fetch_news_rows as fetch_news_rows_akshare,
)
from stock_service.infrastructure.providers.stock_code import normalize_stock_code
from stock_service.infrastructure.providers.tencent_provider import (
    benchmark_pct_change as benchmark_pct_change_tencent,
    fetch_quote as fetch_quote_tencent,
)

QUOTE_PROVIDER_ORDER = settings.market_quote_providers or ("tencent",)
_QUOTE_CACHE_TTL_SECONDS = 3.0
_BENCHMARK_CACHE_TTL_SECONDS = 30.0
_quote_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_benchmark_cache: dict[str, tuple[float, float]] = {}


def _cache_get(cache: dict[str, tuple[float, Any]], key: str, ttl: float) -> Any | None:
    now = time.time()
    cached = cache.get(key)
    if not cached:
        return None
    ts, value = cached
    if now - ts > ttl:
        cache.pop(key, None)
        return None
    return value


def _cache_put(cache: dict[str, tuple[float, Any]], key: str, value: Any) -> Any:
    cache[key] = (time.time(), value)
    return value


def _try_quote_provider(provider_name: str, stock_code: str) -> dict[str, Any]:
    if provider_name == "tencent":
        return fetch_quote_tencent(stock_code)
    raise RuntimeError(f"未知行情源: {provider_name}")


def fetch_quote(stock_code: str) -> dict[str, Any]:
    normalized = normalize_stock_code(stock_code)
    cached = _cache_get(_quote_cache, normalized, _QUOTE_CACHE_TTL_SECONDS)
    if cached is not None:
        return cached

    errors: list[str] = []
    for provider_name in QUOTE_PROVIDER_ORDER:
        try:
            quote = _try_quote_provider(provider_name, normalized)
            if quote.get("latest_price") is None:
                raise RuntimeError(f"{provider_name} latest_price 为空")
            return _cache_put(_quote_cache, normalized, quote)
        except Exception as exc:
            errors.append(f"{provider_name}: {exc}")
    raise RuntimeError(f"所有行情源均失败: {normalized} :: {' | '.join(errors)}")


def fetch_stock_name(stock_code: str) -> str | None:
    quote = fetch_quote(stock_code)
    return quote.get("stock_name")


def benchmark_pct_change(stock_code: str) -> float:
    normalized = normalize_stock_code(stock_code)
    cached = _cache_get(_benchmark_cache, normalized, _BENCHMARK_CACHE_TTL_SECONDS)
    if cached is not None:
        return cached

    for provider in (benchmark_pct_change_tencent,):
        try:
            value = float(provider(normalized))
            return _cache_put(_benchmark_cache, normalized, value)
        except Exception:
            continue
    return 0.0


def fetch_latest_fund_flow(stock_code: str) -> dict[str, Any]:
    return fetch_latest_fund_flow_akshare(stock_code)


def fetch_news_rows(stock_code: str, stock_name: str, max_news_per_stock: int = 20) -> list[dict[str, Any]]:
    return fetch_news_rows_akshare(stock_code, stock_name, max_news_per_stock)


__all__ = [
    "QUOTE_PROVIDER_ORDER",
    "benchmark_pct_change",
    "fetch_latest_fund_flow",
    "fetch_news_rows",
    "fetch_quote",
    "fetch_stock_name",
]
