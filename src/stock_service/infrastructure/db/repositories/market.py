from __future__ import annotations

from typing import Any

from stock_service.infrastructure.db.database_utils import to_json_text
from stock_service.infrastructure.db.repositories.base import BaseRepository


class MarketRepository(BaseRepository):
    async def insert_market_batch(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        values = [
            (
                row.get("run_id"),
                row["stock_code"],
                row.get("stock_name"),
                row.get("trade_date"),
                row.get("snapshot_time"),
                row.get("source", "eastmoney"),
                row.get("latest_price"),
                row.get("pct_change"),
                row.get("change_amount"),
                row.get("open_price"),
                row.get("high_price"),
                row.get("low_price"),
                row.get("prev_close"),
                row.get("volume"),
                row.get("amount"),
                row.get("volume_ratio"),
                row.get("turnover_rate"),
                row.get("amplitude"),
                row.get("main_net_inflow"),
                row.get("main_net_inflow_ratio"),
                row.get("fund_flow_date"),
                row.get("benchmark_code"),
                row.get("benchmark_name"),
                row.get("benchmark_pct_change"),
                row.get("relative_strength_vs_index"),
                row.get("source_latest_price"),
                row.get("source_pct_change"),
                to_json_text(row.get("raw_payload")),
            )
            for row in rows
        ]
        async with self.pool.acquire() as conn:
            await conn.executemany(
                """INSERT INTO market_snapshot
                   (run_id, stock_code, stock_name, trade_date, snapshot_time, source, latest_price, pct_change,
                    change_amount, open_price, high_price, low_price, prev_close, volume, amount, volume_ratio,
                    turnover_rate, amplitude, main_net_inflow, main_net_inflow_ratio, fund_flow_date, benchmark_code,
                    benchmark_name, benchmark_pct_change, relative_strength_vs_index, source_latest_price,
                    source_pct_change, raw_payload)
                   VALUES ($1,$2,$3,$4,COALESCE($5, NOW()),$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,
                           $19,$20,$21,$22,$23,$24,$25,$26,$27,$28)""",
                values,
            )
        return len(values)

    async def get_market_data(self) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT DISTINCT ON (stock_code) *
                   FROM market_snapshot
                   ORDER BY stock_code, snapshot_time DESC, id DESC"""
            )
        return self.rows_to_dicts(rows)

