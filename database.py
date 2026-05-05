from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any

import asyncpg

from db_config import DATABASE_CONFIG


_SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "schema_v2.sql")


def to_json_text(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


class StockDatabase:
    def __init__(self, pool: asyncpg.Pool | None = None):
        self.pool: asyncpg.Pool | None = pool

    async def initialize(self) -> None:
        if self.pool:
            return
        self.pool = await asyncpg.create_pool(
            host=DATABASE_CONFIG["host"],
            port=DATABASE_CONFIG["port"],
            database=DATABASE_CONFIG["database"],
            user=DATABASE_CONFIG["user"],
            password=DATABASE_CONFIG["password"],
            min_size=2,
            max_size=10,
        )
        await self._ensure_schema()

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def _ensure_schema(self) -> None:
        async with self.pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='stock_master')"
            )
        if exists:
            return
        schema_path = Path(_SCHEMA_FILE)
        if not schema_path.exists():
            return
        async with self.pool.acquire() as conn:
            await conn.execute(schema_path.read_text(encoding="utf-8"))

    # ------------------------------------------------------
    # Pipeline run
    # ------------------------------------------------------
    async def create_pipeline_run(
        self,
        run_type: str,
        source: str | None = None,
        trade_date: object | None = None,
        snapshot_time: object | None = None,
        status: str = "running",
    ) -> int:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """INSERT INTO pipeline_run (run_type, source, trade_date, snapshot_time, status)
                   VALUES ($1, $2, $3, $4, $5)
                   RETURNING id""",
                run_type,
                source,
                trade_date,
                snapshot_time,
                status,
            )

    async def complete_pipeline_run(
        self,
        run_id: int,
        status: str,
        stock_count: int = 0,
        news_count: int = 0,
        market_count: int = 0,
        analysis_count: int = 0,
        error_message: str | None = None,
    ) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """UPDATE pipeline_run
                   SET status = $2,
                       stock_count = $3,
                       news_count = $4,
                       market_count = $5,
                       analysis_count = $6,
                       error_message = $7,
                       finished_at = NOW(),
                       updated_at = NOW()
                   WHERE id = $1""",
                run_id,
                status,
                stock_count,
                news_count,
                market_count,
                analysis_count,
                error_message,
            )

    # ------------------------------------------------------
    # Stock master
    # ------------------------------------------------------
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
        return [dict(row) for row in rows]

    # ------------------------------------------------------
    # Popularity snapshot
    # ------------------------------------------------------
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
        return [dict(row) for row in rows]

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
        return [dict(row) for row in rows]

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
        return [dict(row) for row in rows]

    # ------------------------------------------------------
    # News
    # ------------------------------------------------------
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
        return [dict(row) for row in rows]

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
        return [dict(row) for row in rows]

    # ------------------------------------------------------
    # Market snapshot
    # ------------------------------------------------------
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
        return [dict(row) for row in rows]

    # ------------------------------------------------------
    # Analysis
    # ------------------------------------------------------
    async def replace_news_analysis_batch(
        self,
        run_id: int,
        rows: list[dict[str, Any]],
        article_ids: list[int],
    ) -> int:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                if article_ids:
                    await conn.execute(
                        "DELETE FROM news_analysis WHERE article_id = ANY($1::bigint[]) AND analyzer_type = 'rule'",
                        article_ids,
                    )
                if not rows:
                    return 0
                values = [
                    (
                        run_id,
                        row["article_id"],
                        row["stock_code"],
                        row.get("analyzer_type", "rule"),
                        row.get("model_name"),
                        row.get("model_version"),
                        row.get("prompt_version"),
                        row.get("event_type"),
                        row.get("event_label", "中性"),
                        row.get("event_score"),
                        row.get("sentiment_score"),
                        row.get("sentiment_strength"),
                        row.get("duration_tag"),
                        row.get("fact_support"),
                        row.get("impact_scope"),
                        row.get("impact_direction"),
                        row.get("impact_path"),
                        row.get("bullish_logic"),
                        row.get("bearish_logic"),
                        to_json_text(row.get("extracted_entities")),
                        to_json_text(row.get("analysis_json")),
                    )
                    for row in rows
                ]
                await conn.executemany(
                    """INSERT INTO news_analysis
                       (run_id, article_id, stock_code, analyzer_type, model_name, model_version, prompt_version,
                        event_type, event_label, event_score, sentiment_score, sentiment_strength, duration_tag,
                        fact_support, impact_scope, impact_direction, impact_path, bullish_logic, bearish_logic,
                        extracted_entities, analysis_json)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21)""",
                    values,
                )
        return len(rows)

    async def insert_stock_analysis_batch(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        values = [
            (
                row.get("run_id"),
                row["stock_code"],
                row.get("stock_name"),
                row.get("trade_date"),
                row.get("snapshot_time"),
                row.get("event_types"),
                row.get("text_event_label", "中性"),
                row.get("text_score"),
                row.get("sentiment_strength"),
                row.get("duration_tag"),
                row.get("fact_support"),
                row.get("bullish_logic"),
                row.get("bearish_logic"),
                row.get("news_count", 0),
                row.get("price_volume_signal", "数据不足"),
                row.get("fund_flow_signal", "资金观望"),
                row.get("behavior_label", "中性"),
                row.get("market_score"),
                row.get("integrated_score"),
                row.get("decision"),
                to_json_text(row.get("reasoning_json")),
            )
            for row in rows
        ]
        async with self.pool.acquire() as conn:
            await conn.executemany(
                """INSERT INTO stock_analysis_snapshot
                   (run_id, stock_code, stock_name, trade_date, snapshot_time, event_types, text_event_label,
                    text_score, sentiment_strength, duration_tag, fact_support, bullish_logic, bearish_logic,
                    news_count, price_volume_signal, fund_flow_signal, behavior_label, market_score,
                    integrated_score, decision, reasoning_json)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21)""",
                values,
            )
        return len(values)

    async def get_latest_analysis(self, limit: int = 200) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT *
                   FROM stock_analysis_snapshot
                   ORDER BY analyzed_at DESC, id DESC
                   LIMIT $1""",
                limit,
            )
        return [dict(row) for row in rows]
