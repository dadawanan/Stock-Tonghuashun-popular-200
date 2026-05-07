from __future__ import annotations

from typing import Any

from stock_service.infrastructure.db.database_utils import to_json_text
from stock_service.infrastructure.db.repositories.base import BaseRepository


class PopularityRepository(BaseRepository):
    async def insert_popularity_batch(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        values = [
            (
                row.get("run_id"),
                row["trade_date"],
                row["snapshot_time"],
                row.get("source", "ths_pywencai"),
                row["stock_code"],
                row["stock_name"],
                row["popularity_rank"],
                row.get("popularity_score"),
                row.get("latest_price"),
                row.get("latest_pct_change"),
                row.get("is_new_entry", False),
                row.get("previous_rank"),
                row.get("rank_change"),
                to_json_text(row.get("raw_payload")),
            )
            for row in rows
        ]
        async with self.pool.acquire() as conn:
            await conn.executemany(
                """INSERT INTO popularity_snapshot
                   (run_id, trade_date, snapshot_time, source, stock_code, stock_name, popularity_rank,
                    popularity_score, latest_price, latest_pct_change, is_new_entry, previous_rank, rank_change, raw_payload)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                   ON CONFLICT (trade_date, snapshot_time, stock_code, source) DO NOTHING""",
                values,
            )
        return len(values)

    async def get_latest_popularity_snapshot(self) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT ps.*
                   FROM popularity_snapshot ps
                   JOIN (
                       SELECT stock_code, MAX(snapshot_time) AS latest_snapshot
                       FROM popularity_snapshot
                       GROUP BY stock_code
                   ) latest
                     ON ps.stock_code = latest.stock_code
                    AND ps.snapshot_time = latest.latest_snapshot
                   ORDER BY ps.popularity_rank ASC NULLS LAST"""
            )
        return self.rows_to_dicts(rows)

    async def get_latest_popularity_snapshot_times(self, limit: int = 2) -> list[object]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT snapshot_time
                   FROM (
                       SELECT DISTINCT snapshot_time
                       FROM popularity_snapshot
                       ORDER BY snapshot_time DESC
                       LIMIT $1
                   ) ranked
                   ORDER BY snapshot_time DESC""",
                limit,
            )
        return [row["snapshot_time"] for row in rows]

    async def get_popularity_snapshot_by_time(self, snapshot_time: object) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT *
                   FROM popularity_snapshot
                   WHERE snapshot_time = $1
                   ORDER BY popularity_rank ASC, stock_code ASC""",
                snapshot_time,
            )
        return self.rows_to_dicts(rows)

    async def get_latest_new_entries(self) -> list[dict[str, Any]]:
        snapshot_times = await self.get_latest_popularity_snapshot_times(limit=1)
        if not snapshot_times:
            return []
        latest_snapshot_time = snapshot_times[0]
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT *
                   FROM popularity_snapshot
                   WHERE snapshot_time = $1
                     AND is_new_entry = TRUE
                   ORDER BY popularity_rank ASC, stock_code ASC""",
                latest_snapshot_time,
            )
        return self.rows_to_dicts(rows)

