from __future__ import annotations

from stock_service.infrastructure.db.repositories.base import BaseRepository


class PipelineRunRepository(BaseRepository):
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

