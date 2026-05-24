"""新浪行情数据提供者"""

import logging

import pandas as pd
import requests

logger = logging.getLogger(__name__)

SINA_QUOTE_URL = "https://hq.sinajs.cn/list="
HEADERS = {"Referer": "https://finance.sina.com.cn"}


def fetch_realtime_price(code: str) -> float | None:
    """获取实时价格（新浪）

    Args:
        code: 股票代码，如 000001.SZ

    Returns:
        当前价格，失败返回 None
    """
    symbol = code.split(".")[0]
    market = code.split(".")[1].lower() if "." in code else ""

    if market == "sh":
        sina_code = f"sh{symbol}"
    elif market == "sz":
        sina_code = f"sz{symbol}"
    else:
        logger.warning(f"未知市场: {code}")
        return None

    url = f"{SINA_QUOTE_URL}{sina_code}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=5)
        data = resp.text.split('"')[1]
        if data:
            fields = data.split(",")
            # fields[3] 是当前价格
            price = float(fields[3])
            if price > 0:
                return price
    except Exception as e:
        logger.warning(f"获取 {code} 实时价格失败: {e}")

    return None


def fetch_realtime_quote(code: str) -> dict | None:
    """获取实时行情（新浪）

    Returns:
        包含 price, open, high, low, volume, amount 的字典
    """
    symbol = code.split(".")[0]
    market = code.split(".")[1].lower() if "." in code else ""

    if market == "sh":
        sina_code = f"sh{symbol}"
    elif market == "sz":
        sina_code = f"sz{symbol}"
    else:
        return None

    url = f"{SINA_QUOTE_URL}{sina_code}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=5)
        data = resp.text.split('"')[1]
        if data:
            fields = data.split(",")
            return {
                "code": code,
                "name": fields[0],
                "open": float(fields[1]),
                "prev_close": float(fields[2]),
                "price": float(fields[3]),
                "high": float(fields[4]),
                "low": float(fields[5]),
                "volume": int(float(fields[8])),  # 成交量（股）
                "amount": float(fields[9]),  # 成交额（元）
            }
    except Exception as e:
        logger.warning(f"获取 {code} 实时行情失败: {e}")

    return None


def fetch_kline_sina(code: str, start: str, end: str) -> pd.DataFrame:
    """获取日K线数据（通过akshare的新浪接口）

    Args:
        code: 股票代码，如 000001.SZ
        start: 开始日期，格式 YYYYMMDD
        end: 结束日期，格式 YYYYMMDD

    Returns:
        DataFrame with columns: trade_date, open, high, low, close, volume
    """
    import akshare as ak

    symbol = code.split(".")[0]
    market = code.split(".")[1].lower() if "." in code else ""

    if market == "sh":
        sina_code = f"sh{symbol}"
    elif market == "sz":
        sina_code = f"sz{symbol}"
    else:
        return pd.DataFrame()

    try:
        df = ak.stock_zh_a_daily(symbol=sina_code, start_date=start, end_date=end, adjust="qfq")
        if df.empty:
            return pd.DataFrame()

        df = df.rename(columns={"date": "trade_date"})
        df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
        return df[["trade_date", "open", "high", "low", "close", "volume"]]
    except Exception as e:
        logger.warning(f"获取 {code} 日线数据失败: {e}")
        return pd.DataFrame()
