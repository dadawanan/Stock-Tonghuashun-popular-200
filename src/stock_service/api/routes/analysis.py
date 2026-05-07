from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from stock_service.api.dependencies import get_db
from stock_service.application.services.analysis_service import run_analysis, store_analysis_results
from stock_service.application.services.market_data_service import run_fetch_pipeline_for_rows
from stock_service.application.services.pipeline_service import run_all_pipeline
from stock_service.schemas.responses import ApiResponse


logger = logging.getLogger("stock-api")
router = APIRouter(tags=["analysis"])


@router.post("/api/analyze", response_model=ApiResponse)
async def api_analyze() -> ApiResponse:
    return await api_analyze_new_entries()


@router.post("/api/analyze/new-entries", response_model=ApiResponse)
async def api_analyze_new_entries() -> ApiResponse:
    try:
        db = await get_db()
        new_entries = await db.get_latest_new_entries()
        if not new_entries:
            return ApiResponse(data={"result_count": 0, "stocks": [], "message": "最近一次榜单没有新增股票"})
        fetch_result = await run_fetch_pipeline_for_rows(new_entries, run_type="fetch", source="ths_new_entries")
        stock_codes = [row["stock_code"] for row in new_entries]
        results, meta = await run_analysis(db, stock_codes=stock_codes)
        count = await store_analysis_results(db, results, meta, run_type="analyze", source="rule")
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


@router.post("/api/run-all", response_model=ApiResponse)
async def api_run_all() -> ApiResponse:
    try:
        db = await get_db()
        return ApiResponse(data=await run_all_pipeline(db))
    except Exception as exc:
        logger.exception("run-all 失败")
        raise HTTPException(status_code=500, detail=str(exc))

