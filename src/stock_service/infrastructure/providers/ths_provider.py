from __future__ import annotations

import time

import pandas as pd
from pywencai import wencai as pywencai_wencai

from stock_service.infrastructure.config.settings import settings


def _safe_pywencai_get(*, query: str, cookie: str | None, loop: bool = True) -> pd.DataFrame | None:
    """Avoid pywencai.get() crashing on params=None inside the library."""
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            params = pywencai_wencai.get_robot_data(
                query=query,
                cookie=cookie,
                retry=3,
                sleep=1,
            )
            if not isinstance(params, dict):
                raise RuntimeError("pywencai get_robot_data 返回空响应")

            data = params.get("data") or {}
            url_params = params.get("url_params") or {}
            condition = data.get("condition")
            if condition is None:
                raise RuntimeError("pywencai 未返回查询条件 condition")
            if not url_params:
                raise RuntimeError("pywencai 未返回分页参数 url_params")

            kwargs = {
                "query": query,
                "cookie": cookie,
                **data,
            }
            find = kwargs.get("find")
            if loop and find is None:
                row_count = int(params.get("row_count") or 0)
                if row_count <= 0:
                    return pd.DataFrame()
                return pywencai_wencai.loop_page(loop, row_count, url_params, **kwargs)
            return pywencai_wencai.get_page(url_params, **kwargs)
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(attempt)
    raise RuntimeError(f"同花顺接口空响应或结构异常: {last_error}") from last_error


def fetch_top_200_popularity() -> pd.DataFrame:
    try:
        df = _safe_pywencai_get(
            query=settings.ths_query,
            cookie=settings.ths_cookie or None,
            loop=True,
        )
    except Exception as exc:
        raise RuntimeError(f"同花顺人气榜抓取失败: {exc}") from exc

    if df is None or df.empty:
        return pd.DataFrame()
    return df
