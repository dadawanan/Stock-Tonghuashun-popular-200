"""兼容层：保留旧接口名，底层改走腾讯财经。"""

import logging

import pandas as pd

from stock_service.infrastructure.providers.tencent_provider import (
    fetch_kline_tx,
    fetch_realtime_price as fetch_realtime_price_tx,
    fetch_realtime_quote as fetch_realtime_quote_tx,
)

logger = logging.getLogger(__name__)


def fetch_realtime_price(code: str) -> float | None:
    """获取实时价格（腾讯兼容实现）"""
    try:
        return fetch_realtime_price_tx(code)
    except Exception as e:
        logger.warning(f"获取 {code} 实时价格失败: {e}")
        return None



def fetch_realtime_quote(code: str) -> dict | None:
    """获取实时行情（腾讯兼容实现）"""
    try:
        return fetch_realtime_quote_tx(code)
    except Exception as e:
        logger.warning(f"获取 {code} 实时行情失败: {e}")
    return None


def fetch_kline_sina(code: str, start: str, end: str) -> pd.DataFrame:
    """获取日K线数据（腾讯兼容实现）"""
    try:
        df = fetch_kline_tx(code, start, end)
        if df.empty:
            return pd.DataFrame()
        return df[["trade_date", "open", "high", "low", "close", "volume"]]
    except Exception as e:
        logger.warning(f"获取 {code} 日线数据失败: {e}")
        return pd.DataFrame()
