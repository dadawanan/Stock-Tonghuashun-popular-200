from __future__ import annotations

from stock_service.domain.services.stock_utils import (
    code_digits,
    normalize_stock_code,
    stock_market_suffix,
)


def eastmoney_market_prefix(stock_code: str) -> str:
    return {"SH": "1", "SZ": "0", "BJ": "0"}.get(stock_market_suffix(stock_code), "0")


def tencent_symbol(stock_code: str) -> str:
    digits = code_digits(stock_code)
    suffix = stock_market_suffix(stock_code)
    prefix = {"SH": "sh", "SZ": "sz", "BJ": "bj"}.get(suffix, "sz")
    return f"{prefix}{digits}"


def from_tencent_symbol(symbol: str) -> str:
    symbol = symbol.strip().lower()
    if len(symbol) < 3:
        return symbol.upper()
    prefix, digits = symbol[:2], symbol[2:]
    suffix = {"sh": "SH", "sz": "SZ", "bj": "BJ"}.get(prefix)
    if suffix and digits.isdigit():
        return f"{digits}.{suffix}"
    return symbol.upper()
