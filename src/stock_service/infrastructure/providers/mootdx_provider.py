from __future__ import annotations

from typing import Any

from stock_service.infrastructure.providers.stock_code import code_digits, normalize_stock_code


class MootdxUnavailableError(RuntimeError):
    pass


_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    try:
        from mootdx.quotes import Quotes
    except Exception as exc:  # pragma: no cover - optional dependency
        raise MootdxUnavailableError("mootdx 未安装或不可用") from exc
    _client = Quotes.factory(market="std")
    return _client


def _record_to_dict(record: Any) -> dict[str, Any]:
    if hasattr(record, "to_dict"):
        return record.to_dict()
    if isinstance(record, dict):
        return dict(record)
    return {
        key: getattr(record, key)
        for key in dir(record)
        if not key.startswith("_") and not callable(getattr(record, key))
    }


def fetch_quote(stock_code: str) -> dict[str, Any]:
    normalized = normalize_stock_code(stock_code)
    client = _get_client()
    quotes = client.quotes(symbol=[code_digits(normalized)])
    if quotes is None:
        raise RuntimeError(f"mootdx 行情为空: {normalized}")
    if hasattr(quotes, "to_dict"):
        records = quotes.to_dict(orient="records")
    elif isinstance(quotes, list):
        records = [_record_to_dict(item) for item in quotes]
    else:
        records = [_record_to_dict(quotes)]
    if not records:
        raise RuntimeError(f"mootdx 行情为空: {normalized}")

    target_digits = code_digits(normalized)
    record = next(
        (
            item for item in records
            if str(item.get("code") or item.get("symbol") or "").strip() == target_digits
        ),
        records[0],
    )
    return {
        "stock_code": normalized,
        "stock_name": record.get("name"),
        "latest_price": record.get("price"),
        "open_price": record.get("open"),
        "high_price": record.get("high"),
        "low_price": record.get("low"),
        "prev_close": record.get("last_close"),
        "volume": record.get("vol"),
        "amount": record.get("amount"),
        "source": "mootdx",
    }


__all__ = ["MootdxUnavailableError", "fetch_quote"]
