from __future__ import annotations

from typing import Any

from stock_service.infrastructure.db.database_utils import to_json_text
from stock_service.infrastructure.db.repositories.base import BaseRepository


class AnalysisRepository(BaseRepository):
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
        return self.rows_to_dicts(rows)

