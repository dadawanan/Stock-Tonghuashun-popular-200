from __future__ import annotations

from typing import Any

from stock_service.infrastructure.db.repositories.base import BaseRepository


class StockRepository(BaseRepository):
    async def upsert_stocks(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        values = [
            (
                row["stock_code"],
                row["stock_name"],
                row["stock_code"].split(".")[-1] if "." in row["stock_code"] else "SZ",
                str(row["market_code"]) if row.get("market_code") is not None else None,
                row["stock_code"].split(".")[0],
                bool(row.get("is_st", False) or "ST" in str(row["stock_name"]).upper()),
            )
            for row in rows
        ]
        async with self.pool.acquire() as conn:
            await conn.executemany(
                """INSERT INTO stock_master
                   (stock_code, stock_name, market, market_code, code_digits, is_st)
                   VALUES ($1, $2, $3, $4, $5, $6)
                   ON CONFLICT (stock_code) DO UPDATE SET
                       stock_name = EXCLUDED.stock_name,
                       market = EXCLUDED.market,
                       market_code = EXCLUDED.market_code,
                       code_digits = EXCLUDED.code_digits,
                       is_st = EXCLUDED.is_st,
                       updated_at = NOW()""",
                values,
            )
        return len(values)

    async def get_all_stocks(self) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT stock_code, stock_name, market, market_code, code_digits, is_st
                   FROM stock_master
                   WHERE status = 'active'
                   ORDER BY stock_code"""
            )
        return self.rows_to_dicts(rows)

