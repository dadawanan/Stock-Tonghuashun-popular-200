from __future__ import annotations

import pandas as pd
import pywencai

from stock_service.infrastructure.config.settings import settings


def fetch_top_200_popularity() -> pd.DataFrame:
    try:
        df = pywencai.get(
            query=settings.ths_query,
            cookie=settings.ths_cookie or None,
            loop=True,
        )
    except Exception as exc:
        raise RuntimeError(f"同花顺人气榜抓取失败: {exc}") from exc

    if df is None or df.empty:
        return pd.DataFrame()
    return df

