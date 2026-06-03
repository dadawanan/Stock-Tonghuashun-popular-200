"""Celery tasks for async backtest execution."""

import asyncio
import json
import logging
from datetime import date

from stock_service.celery_app import celery
from stock_service.db.database import AsyncSessionFactory

logger = logging.getLogger(__name__)


# ── Sync DB helpers (safe to call from within an async event loop) ──


def _get_sync_conn():
    """Create a psycopg2 connection from settings. Caller must close."""
    import psycopg2
    from stock_service.infrastructure.config.settings import settings

    return psycopg2.connect(
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        connect_timeout=10,
    )


def _update_progress_sync(task_id: int, current: int, total: int, message: str = "") -> None:
    """Synchronously update task progress. Safe to call from async context."""
    percent = round(current / total * 100, 1) if total > 0 else 0
    progress = json.dumps({"current": current, "total": total, "message": message, "percent": percent})

    conn = _get_sync_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE backtest_task SET progress = %s::jsonb, updated_at = NOW() WHERE id = %s",
                (progress, task_id),
            )
            conn.commit()
    finally:
        conn.close()


def _update_status_sync(task_id: int, status: str) -> None:
    """Synchronously update task status. Only sets started_at for 'running'."""
    conn = _get_sync_conn()
    try:
        with conn.cursor() as cur:
            if status == "running":
                cur.execute(
                    "UPDATE backtest_task SET status = %s, started_at = NOW(), updated_at = NOW() WHERE id = %s",
                    (status, task_id),
                )
            else:
                cur.execute(
                    "UPDATE backtest_task SET status = %s, updated_at = NOW() WHERE id = %s",
                    (status, task_id),
                )
            conn.commit()
    finally:
        conn.close()


def _update_result_sync(task_id: int, result: dict, backtest_ids: list[int] | None = None) -> None:
    """Synchronously update task result on success."""
    conn = _get_sync_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE backtest_task
                   SET status = 'success', result = %s::jsonb, backtest_ids = %s,
                       finished_at = NOW(), updated_at = NOW()
                   WHERE id = %s""",
                (json.dumps(result, default=str), backtest_ids, task_id),
            )
            conn.commit()
    finally:
        conn.close()


def _update_error_sync(task_id: int, error: str) -> None:
    """Synchronously update task on failure."""
    conn = _get_sync_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE backtest_task
                   SET status = 'failed', error = %s,
                       finished_at = NOW(), updated_at = NOW()
                   WHERE id = %s""",
                (error, task_id),
            )
            conn.commit()
    finally:
        conn.close()


def _make_progress_cb(task_id: int):
    """Create a sync progress callback safe to call from async context.

    Errors are logged but NOT raised — a failed progress update should not
    kill the backtest computation.
    """
    def cb(current: int, total: int, message: str = ""):
        try:
            _update_progress_sync(task_id, current, total, message)
        except Exception as exc:
            logger.warning(f"Progress update failed for task {task_id}: {exc}")
    return cb


# ── Async-to-sync bridge ──


def _run_async(coro):
    """Run an async coroutine in a new event loop (Celery workers are sync)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Celery tasks ──


@celery.task(name="quant.run_backtest", bind=True, max_retries=0)
def run_backtest_task(self, task_id: int, params: dict) -> None:
    """Execute a single backtest asynchronously."""
    _update_status_sync(task_id, "running")

    try:
        result = _run_async(_run_backtest(task_id, params))
        _update_result_sync(task_id, result, [result["backtest_id"]])
        logger.info(f"Backtest task {task_id} completed: backtest_id={result['backtest_id']}")
    except Exception as exc:
        logger.error(f"Backtest task {task_id} failed: {exc}", exc_info=True)
        _update_error_sync(task_id, str(exc))


async def _run_backtest(task_id: int, params: dict) -> dict:
    """Async helper for run_backtest_task."""
    from stock_service.quant.application.backtest_engine import BacktestEngine
    from stock_service.quant.application.strategy_engine import engine as strategy_engine
    from stock_service.quant.domain.backtest_rules import BacktestConfig

    async with AsyncSessionFactory() as session:
        engine = BacktestEngine(session)
        config = BacktestConfig(
            initial_capital=params.get("initial_capital", 1_000_000),
            commission_rate=params.get("commission_rate", 0.0003),
            stamp_tax=params.get("stamp_tax", 0.001),
            slippage=params.get("slippage", 0.002),
            max_position_pct=params.get("max_position_pct", 0.2),
            max_holdings=params.get("max_holdings", 10),
            stop_loss_pct=params.get("stop_loss_pct", -0.08),
        )

        result = await engine.run(
            strategy_id=params["strategy_id"],
            stock_codes=params["stock_codes"],
            start_date=date.fromisoformat(params["start_date"]),
            end_date=date.fromisoformat(params["end_date"]),
            config=config,
            strategy_engine=strategy_engine,
            progress_cb=_make_progress_cb(task_id),
        )
        await session.commit()
        return result


@celery.task(name="quant.run_grid_search", bind=True, max_retries=0)
def run_grid_search_task(self, task_id: int, params: dict) -> None:
    """Execute grid search optimization asynchronously."""
    _update_status_sync(task_id, "running")

    try:
        result = _run_async(_run_grid_search(task_id, params))
        backtest_ids = [r["backtest_id"] for r in result if r.get("backtest_id")]
        _update_result_sync(task_id, {"results": result}, backtest_ids)
        logger.info(f"Grid search task {task_id} completed: {len(result)} results")
    except Exception as exc:
        logger.error(f"Grid search task {task_id} failed: {exc}", exc_info=True)
        _update_error_sync(task_id, str(exc))


async def _run_grid_search(task_id: int, params: dict) -> list[dict]:
    """Async helper for run_grid_search_task."""
    from stock_service.quant.application.optimizer import ParameterOptimizer
    from stock_service.quant.domain.backtest_rules import BacktestConfig

    async with AsyncSessionFactory() as session:
        optimizer = ParameterOptimizer(session)
        config = BacktestConfig(initial_capital=params.get("initial_capital", 1_000_000))

        results = await optimizer.grid_search(
            strategy_id=params["strategy_id"],
            param_grid=params["param_grid"],
            stock_codes=params.get("stock_codes") or [],
            start_date=date.fromisoformat(params["start_date"]),
            end_date=date.fromisoformat(params["end_date"]),
            config=config,
            metric=params.get("metric", "sharpe_ratio"),
            top_n=params.get("top_n", 5),
            progress_cb=_make_progress_cb(task_id),
        )
        await session.commit()

        return [
            {"params": r.params, "metrics": r.metrics, "backtest_id": r.backtest_id}
            for r in results
        ]


@celery.task(name="quant.run_walk_forward", bind=True, max_retries=0)
def run_walk_forward_task(self, task_id: int, params: dict) -> None:
    """Execute walk-forward optimization asynchronously."""
    _update_status_sync(task_id, "running")

    try:
        result, backtest_ids = _run_async(_run_walk_forward(task_id, params))
        _update_result_sync(task_id, result, backtest_ids)
        logger.info(f"Walk-forward task {task_id} completed: {len(backtest_ids)} backtest results")
    except Exception as exc:
        logger.error(f"Walk-forward task {task_id} failed: {exc}", exc_info=True)
        _update_error_sync(task_id, str(exc))


async def _run_walk_forward(task_id: int, params: dict) -> tuple[dict, list[int]]:
    """Async helper for run_walk_forward_task.

    Returns (result_dict, backtest_ids) so the caller can store both.
    """
    from stock_service.quant.application.optimizer import ParameterOptimizer
    from stock_service.quant.domain.backtest_rules import BacktestConfig

    async with AsyncSessionFactory() as session:
        optimizer = ParameterOptimizer(session)
        config = BacktestConfig(initial_capital=params.get("initial_capital", 1_000_000))

        result = await optimizer.walk_forward(
            strategy_id=params["strategy_id"],
            param_grid=params["param_grid"],
            stock_codes=params.get("stock_codes") or [],
            start_date=date.fromisoformat(params["start_date"]),
            end_date=date.fromisoformat(params["end_date"]),
            train_days=params.get("train_days", 180),
            test_days=params.get("test_days", 60),
            step_days=params.get("step_days", 60),
            config=config,
            metric=params.get("metric", "sharpe_ratio"),
            progress_cb=_make_progress_cb(task_id),
        )
        await session.commit()

        # Collect all backtest_ids created during walk-forward
        backtest_ids: list[int] = []
        for window in result.windows:
            if window.train_metrics and "backtest_id" in window.train_metrics:
                backtest_ids.append(window.train_metrics["backtest_id"])
            if window.test_metrics and "backtest_id" in window.test_metrics:
                backtest_ids.append(window.test_metrics["backtest_id"])

        result_dict = {
            "windows": [
                {
                    "window_id": w.window_id,
                    "train_period": f"{w.train_start} ~ {w.train_end}",
                    "test_period": f"{w.test_start} ~ {w.test_end}",
                    "best_params": w.best_params,
                    "train_metrics": w.train_metrics,
                    "test_metrics": w.test_metrics,
                }
                for w in result.windows
            ],
            "avg_test_metrics": result.avg_test_metrics,
            "best_params_per_window": result.best_params_per_window,
            "stability_score": result.stability_score,
        }
        return result_dict, backtest_ids
