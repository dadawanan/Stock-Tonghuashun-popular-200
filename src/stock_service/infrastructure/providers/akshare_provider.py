from __future__ import annotations

import hashlib
import time
from typing import Any

import akshare as ak
import pandas as pd

from stock_service.infrastructure.providers.stock_code import code_digits, normalize_stock_code, stock_market_suffix


def fetch_latest_fund_flow(stock_code: str) -> dict[str, Any]:
    normalized = normalize_stock_code(stock_code)
    digits = code_digits(normalized)
    market = "sh" if stock_market_suffix(normalized) == "SH" else "sz"
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            latest = ak.stock_individual_fund_flow(stock=digits, market=market).tail(1).iloc[0]
            raw_date = latest.get("日期")
            flow_date = None
            if raw_date is not None:
                try:
                    flow_date = None if pd.isna(raw_date) else raw_date
                except TypeError:
                    flow_date = raw_date
            return {
                "flow_date": flow_date,
                "main_net_inflow": float(latest.get("主力净流入-净额", 0.0)),
                "main_net_inflow_ratio": float(latest.get("主力净流入-净占比", 0.0)),
                "source": "akshare",
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
        "关键词": "keyword",
        "新闻标题": "title",
        "新闻内容": "content",
        "发布时间": "published_at",
        "文章来源": "source",
        "新闻链接": "url",
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


__all__ = ["fetch_latest_fund_flow", "fetch_news_rows"]
