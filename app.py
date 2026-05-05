from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from database import StockDatabase
from data_fetcher import compare_stock_sets, run_fetch_pipeline_for_rows, run_popularity_pipeline
from stock_analyzer import run_analysis

logger = logging.getLogger("stock-api")


# ------------------------------------------------------------------
# Global DB pool (managed by lifespan)
# ------------------------------------------------------------------
_db: Optional[StockDatabase] = None


async def get_db() -> StockDatabase:
    global _db
    if _db is None or _db.pool is None:
        raise RuntimeError("数据库未初始化，请等待服务启动完成")
    return _db


# ------------------------------------------------------------------
# Pydantic models
# ------------------------------------------------------------------
class ApiResponse(BaseModel):
    code: int = 0
    msg: str = ""
    data: Any = None


class FetchResponse(BaseModel):
    news_count: int = 0
    market_count: int = 0


class AnalyzeResponse(BaseModel):
    result_count: int = 0


async def store_analysis_results(
    db: StockDatabase,
    results: list[dict[str, Any]],
    meta: dict[str, Any],
    *,
    run_type: str,
    source: str = "rule",
) -> int:
    run_id = await db.create_pipeline_run(run_type=run_type, source=source)
    try:
        news_analysis_rows = meta.get("news_analysis_rows", [])
        article_ids = [row["article_id"] for row in news_analysis_rows if row.get("article_id") is not None]
        if news_analysis_rows:
            await db.replace_news_analysis_batch(run_id, news_analysis_rows, article_ids)
        for row in results:
            row["run_id"] = run_id
            row["trade_date"] = meta.get("latest_trade_date")
            row["snapshot_time"] = meta.get("latest_snapshot_time")
            row["reasoning_json"] = {
                "text_event_label": row.get("text_event_label"),
                "fund_flow_signal": row.get("fund_flow_signal"),
                "behavior_label": row.get("behavior_label"),
                "decision": row.get("decision"),
            }
        count = await db.insert_stock_analysis_batch(results)
        await db.complete_pipeline_run(run_id, status="success", analysis_count=count)
        return count
    except Exception as exc:
        await db.complete_pipeline_run(run_id, status="failed", error_message=str(exc))
        raise


# ------------------------------------------------------------------
# Lifespan — create / destroy connection pool
# ------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _db
    _db = StockDatabase()
    await _db.initialize()
    logger.info("数据库连接池已建立")
    yield
    await _db.close()
    logger.info("数据库连接池已关闭")


# ------------------------------------------------------------------
# App
# ------------------------------------------------------------------
app = FastAPI(title="Stock Analysis API", lifespan=lifespan)


@app.get("/api/health", response_model=ApiResponse)
async def health():
    try:
        if _db is None or _db.pool is None:
            return ApiResponse(code=1, msg="数据库未初始化", data={"ready": False})
        async with _db.pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return ApiResponse(data={"ready": True})
    except Exception as exc:
        return ApiResponse(code=1, msg=str(exc), data={"ready": False})


# ------------------------------------------------------------------
# Popularity: fetch THS top200 and persist snapshot
# ------------------------------------------------------------------
@app.post("/api/popularity/fetch", response_model=ApiResponse)
async def api_popularity_fetch():
    """抓取同花顺人气前200并保存为榜单快照。"""
    try:
        result = await run_popularity_pipeline()
        return ApiResponse(data=result)
    except Exception as exc:
        logger.exception("popularity fetch 失败")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/popularity/latest", response_model=ApiResponse)
async def api_popularity_latest():
    """获取最近一次同花顺人气前200榜单。"""
    try:
        db = await get_db()
        rows = await db.get_latest_popularity_snapshot()
        return ApiResponse(
            data={
                "snapshot_time": rows[0]["snapshot_time"] if rows else None,
                "count": len(rows),
                "stocks": rows,
            }
        )
    except Exception as exc:
        logger.exception("查询 latest popularity 失败")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/popularity/compare-latest", response_model=ApiResponse)
async def api_popularity_compare_latest():
    """比较最近两次榜单快照，返回新增/掉出/排名变化。"""
    try:
        db = await get_db()
        snapshot_times = await db.get_latest_popularity_snapshot_times(limit=2)
        if len(snapshot_times) < 2:
            raise HTTPException(status_code=400, detail="至少需要两次榜单快照才能比较")

        current_rows = await db.get_popularity_snapshot_by_time(snapshot_times[0])
        previous_rows = await db.get_popularity_snapshot_by_time(snapshot_times[1])
        comparison = compare_stock_sets(previous_rows, current_rows)
        return ApiResponse(
            data={
                "current_snapshot_time": snapshot_times[0],
                "previous_snapshot_time": snapshot_times[1],
                **comparison,
            }
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("compare latest popularity 失败")
        raise HTTPException(status_code=500, detail=str(exc))


# ------------------------------------------------------------------
# Backward compatible fetch endpoint
# ------------------------------------------------------------------
@app.post("/api/fetch", response_model=ApiResponse)
async def api_fetch():
    """兼容旧接口：抓取同花顺人气前200快照。"""
    return await api_popularity_fetch()


# ------------------------------------------------------------------
# Analyze: read from DB → compute → write analysis_result
# ------------------------------------------------------------------
@app.post("/api/analyze", response_model=ApiResponse)
async def api_analyze():
    """兼容旧接口：分析最近一次榜单中的新增股票。"""
    return await api_analyze_new_entries()


@app.post("/api/analyze/new-entries", response_model=ApiResponse)
async def api_analyze_new_entries():
    """对最近一次榜单中的新增股票抓取行情/新闻并执行分析。"""
    try:
        db = await get_db()
        new_entries = await db.get_latest_new_entries()
        if not new_entries:
            return ApiResponse(data={"result_count": 0, "stocks": [], "message": "最近一次榜单没有新增股票"})

        fetch_result = await run_fetch_pipeline_for_rows(new_entries, run_type="fetch", source="ths_new_entries")
        stock_codes = [row["stock_code"] for row in new_entries]
        results, meta = await run_analysis(db, stock_codes=stock_codes)
        count = await store_analysis_results(db, results, meta, run_type="analyze", source="rule")
        logger.info("新增股票分析完成，写入 %d 条结果", count)
        return ApiResponse(
            data={
                "result_count": count,
                "fetch_result": fetch_result,
                "stocks": stock_codes,
                "results": results,
            }
        )
    except Exception as exc:
        logger.exception("analyze new entries 失败")
        raise HTTPException(status_code=500, detail=str(exc))


# ------------------------------------------------------------------
# Run all: fetch + analyze in one call
# ------------------------------------------------------------------
@app.post("/api/run-all", response_model=ApiResponse)
async def api_run_all():
    """一键执行：抓人气前200、比较新增、分析新增股票。"""
    try:
        db = await get_db()
        fetch_popularity_result = await run_popularity_pipeline()
        comparison = fetch_popularity_result["comparison"]
        new_entries = comparison["new_entries"]
        if not new_entries:
            return ApiResponse(
                data={
                    "popularity": fetch_popularity_result,
                    "analysis": {"result_count": 0, "stocks": [], "message": "本次榜单没有新增股票"},
                }
            )

        fetch_result = await run_fetch_pipeline_for_rows(new_entries, run_type="fetch", source="ths_new_entries")
        stock_codes = [row["stock_code"] for row in new_entries]
        results, meta = await run_analysis(db, stock_codes=stock_codes)
        count = await store_analysis_results(db, results, meta, run_type="run_all", source="rule")
        logger.info("完整流程完成，写入 %d 条新增股票分析结果", count)
        return ApiResponse(
            data={
                "popularity": fetch_popularity_result,
                "analysis": {
                    "result_count": count,
                    "fetch_result": fetch_result,
                    "stocks": stock_codes,
                    "results": results,
                },
            }
        )
    except Exception as exc:
        logger.exception("run-all 失败")
        raise HTTPException(status_code=500, detail=str(exc))


# ------------------------------------------------------------------
# Query: stocks
# ------------------------------------------------------------------
@app.get("/api/stocks", response_model=ApiResponse)
async def api_stocks():
    """查询当前股票池。"""
    try:
        db = await get_db()
        stocks = await db.get_all_stocks()
        return ApiResponse(data=stocks)
    except Exception as exc:
        logger.exception("查询 stocks 失败")
        raise HTTPException(status_code=500, detail=str(exc))


# ------------------------------------------------------------------
# Query: news by stock
# ------------------------------------------------------------------
@app.get("/api/news/{stock_code}", response_model=ApiResponse)
async def api_news(stock_code: str, limit: int = Query(default=20, le=100)):
    """查询某只股票的新闻。"""
    try:
        db = await get_db()
        news = await db.get_news_by_stock(stock_code, limit=limit)
        return ApiResponse(data=news)
    except Exception as exc:
        logger.exception("查询 news 失败")
        raise HTTPException(status_code=500, detail=str(exc))


# ------------------------------------------------------------------
# Query: latest analysis results
# ------------------------------------------------------------------
@app.get("/api/analysis", response_model=ApiResponse)
async def api_analysis(limit: int = Query(default=200, le=500)):
    """查询最新分析结果。"""
    try:
        db = await get_db()
        results = await db.get_latest_analysis(limit=limit)
        return ApiResponse(data=results)
    except Exception as exc:
        logger.exception("查询 analysis 失败")
        raise HTTPException(status_code=500, detail=str(exc))


# ------------------------------------------------------------------
# Query: analysis by stock code
# ------------------------------------------------------------------
@app.get("/api/analysis/{stock_code}", response_model=ApiResponse)
async def api_analysis_by_stock(stock_code: str):
    """查询某只股票的最新分析结果。"""
    try:
        db = await get_db()
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM stock_analysis_snapshot WHERE stock_code = $1 ORDER BY analyzed_at DESC LIMIT 1",
                stock_code,
            )
        if row is None:
            raise HTTPException(status_code=404, detail=f"未找到 {stock_code} 的分析结果")
        return ApiResponse(data=dict(row))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("查询 analysis by stock 失败")
        raise HTTPException(status_code=500, detail=str(exc))


# ------------------------------------------------------------------
# Run as CLI entry point too
# ------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    uvicorn.run(app, host="0.0.0.0", port=8000)
