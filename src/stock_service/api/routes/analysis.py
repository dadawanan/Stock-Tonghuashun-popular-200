from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from stock_service.api.dependencies import get_db
from stock_service.application.services.analysis_service import run_analysis, store_analysis_results
from stock_service.application.services.market_data_service import run_fetch_pipeline_for_rows
from stock_service.application.services.pipeline_service import run_all_pipeline
from stock_service.domain.services.analysis_rules import normalize_stock_code
from stock_service.infrastructure.providers.eastmoney_provider import fetch_quote
from stock_service.schemas.responses import ApiResponse


logger = logging.getLogger("stock-api")
router = APIRouter(tags=["analysis"])


async def _fetch_then_analyze(stock_rows: list[dict[str, Any]], *, fetch_source: str) -> ApiResponse:
    """先按行抓取新闻/行情并 upsert，再对给定股票代码集合做规则分析并入库。"""
    db = await get_db()
    fetch_result = await run_fetch_pipeline_for_rows(stock_rows, run_type="fetch", source=fetch_source)
    stock_codes = [normalize_stock_code(row["stock_code"]) for row in stock_rows]
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


@router.post("/api/analyze", response_model=ApiResponse)
async def api_analyze(
    stock_code: Annotated[
        str | None,
        Query(description="可选。传入则仅抓取并分析该股票；不传则分析最近一次榜单新增股票（与原行为一致）"),
    ] = None,
) -> ApiResponse:
    trimmed = (stock_code or "").strip()
    if not trimmed:
        return await api_analyze_new_entries()
    try:
        normalized = normalize_stock_code(trimmed)
        db = await get_db()
        stocks = await db.get_all_stocks()
        match = next((s for s in stocks if normalize_stock_code(s["stock_code"]) == normalized), None)
        stock_name = str((match or {}).get("stock_name") or "").strip()
        if not stock_name:
            try:
                stock_name = str(fetch_quote(normalized).get("stock_name") or "").strip()
            except Exception:
                stock_name = ""
        row: dict[str, Any] = {
            "stock_code": normalized,
            "stock_name": stock_name,
            "source_latest_price": None,
            "source_pct_change": None,
            "market_code": (match or {}).get("market_code"),
        }
        return await _fetch_then_analyze([row], fetch_source="single_stock")
    except Exception as exc:
        logger.exception("analyze 单股失败 stock_code=%s", trimmed)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/analyze/new-entries", response_model=ApiResponse)
async def api_analyze_new_entries() -> ApiResponse:
    try:
        db = await get_db()
        new_entries = await db.get_latest_new_entries()
        if not new_entries:
            return ApiResponse(data={"result_count": 0, "stocks": [], "message": "最近一次榜单没有新增股票"})
        return await _fetch_then_analyze(new_entries, fetch_source="ths_new_entries")
    except Exception as exc:
        logger.exception("analyze new entries 失败")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/run-all", response_model=ApiResponse)
async def api_run_all() -> ApiResponse:
    try:
        db = await get_db()
        return ApiResponse(data=await run_all_pipeline(db))
    except Exception as exc:
        logger.exception("run-all 失败")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
