from __future__ import annotations


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


def code_digits(stock_code: str) -> str:
    return normalize_stock_code(stock_code).split(".")[0]
