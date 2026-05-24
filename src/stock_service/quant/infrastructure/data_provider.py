import logging
from datetime import date, timedelta

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.crud import quant_crud

logger = logging.getLogger(__name__)


class QuantDataProvider:
    """Unified data provider for quant module."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def fetch_daily_kline(
        self, code: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """Fetch daily kline data from DB, return as DataFrame."""
        rows = await quant_crud.get_stock_daily(
            self._session, code, start_date=start_date, end_date=end_date
        )
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        return df.sort_values("trade_date").reset_index(drop=True)

    async def fetch_kline_for_indicators(
        self, code: str, trade_date: date, lookback_days: int = 365
    ) -> pd.DataFrame:
        """Fetch enough history for indicator calculation."""
        start = trade_date - timedelta(days=lookback_days)
        return await self.fetch_daily_kline(code, start, trade_date)

    async def import_csv(self, file_path: str) -> int:
        """Import daily kline data from CSV file."""
        df = pd.read_csv(file_path)
        required_cols = {"code", "trade_date", "open", "high", "low", "close", "volume"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"CSV missing columns: {missing}")

        records = df.to_dict("records")
        for row in records:
            row["trade_date"] = pd.to_datetime(row["trade_date"]).date()
        return await quant_crud.batch_upsert_stock_daily(self._session, records)

    async def get_indicators(self, code: str, trade_date: date) -> dict:
        """Get pre-computed indicators from stock_indicator table."""
        row = await quant_crud.get_stock_indicator(
            self._session, code, trade_date=trade_date
        )
        if not row:
            return {}
        return {
            "ma5": float(row["ma5"]) if row.get("ma5") else None,
            "ma20": float(row["ma20"]) if row.get("ma20") else None,
            "rsi": float(row["rsi"]) if row.get("rsi") else None,
            "macd": float(row["macd"]) if row.get("macd") else None,
        }

    async def batch_import_from_akshare(
        self, codes: list[str], start_date: date, end_date: date
    ) -> int:
        """Fetch and import daily data from akshare for multiple stocks."""
        import asyncio
        import akshare as ak

        total = 0
        for code in codes:
            try:
                symbol = code.split(".")[0]
                df = await asyncio.to_thread(
                    ak.stock_zh_a_hist,
                    symbol=symbol,
                    period="daily",
                    start_date=start_date.strftime("%Y%m%d"),
                    end_date=end_date.strftime("%Y%m%d"),
                    adjust="qfq",
                )
                if df.empty:
                    continue

                df = df.rename(columns={
                    "日期": "trade_date", "开盘": "open", "最高": "high",
                    "最低": "low", "收盘": "close", "成交量": "volume",
                    "成交额": "amount",
                })
                df["code"] = code
                df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date

                records = df[["code", "trade_date", "open", "high", "low", "close", "volume", "amount"]].to_dict("records")
                await quant_crud.batch_upsert_stock_daily(self._session, records)
                total += len(records)
            except Exception as e:
                logger.warning(f"Failed to fetch {code}: {e}")

        return total
