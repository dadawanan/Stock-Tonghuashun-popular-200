from __future__ import annotations

from typing import Any

from stock_service.infrastructure.db.database_utils import to_json_text
from stock_service.infrastructure.db.repositories.base import BaseRepository


class NewsRepository(BaseRepository):
    async def insert_news_batch(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        values = [
            (
                row.get("run_id"),
                row["stock_code"],
                row.get("stock_name"),
                row.get("source"),
                row.get("keyword"),
                row["title"],
                row.get("content"),
                row.get("summary"),
                row.get("url"),
                row.get("published_at"),
                row.get("fetched_at"),
                to_json_text(row.get("raw_payload")),
                row.get("content_hash"),
            )
            for row in rows
        ]
        async with self.pool.acquire() as conn:
            await conn.executemany(
                """INSERT INTO news_article
                   (run_id, stock_code, stock_name, source, keyword, title, content, summary, url,
                    published_at, fetched_at, raw_payload, content_hash)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,COALESCE($11, NOW()),$12,$13)
                   ON CONFLICT DO NOTHING""",
                values,
            )
        return len(values)

    async def get_news_by_stock(self, stock_code: str, limit: int = 20) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT *
                   FROM news_article
                   WHERE stock_code = $1
                   ORDER BY published_at DESC NULLS LAST, fetched_at DESC
                   LIMIT $2""",
                stock_code,
                limit,
            )
        return self.rows_to_dicts(rows)

    async def get_all_news(self, limit_per_stock: int = 20) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT *
                   FROM (
                       SELECT na.*,
                              ROW_NUMBER() OVER (
                                  PARTITION BY stock_code
                                  ORDER BY published_at DESC NULLS LAST, fetched_at DESC, id DESC
                              ) AS rn
                       FROM news_article na
                   ) ranked
                   WHERE rn <= $1
                   ORDER BY stock_code, published_at DESC NULLS LAST, fetched_at DESC""",
                limit_per_stock,
            )
        return self.rows_to_dicts(rows)

