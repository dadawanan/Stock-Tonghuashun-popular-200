from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from stock_service.api.dependencies import get_db
from stock_service.schemas.responses import ApiResponse


logger = logging.getLogger("stock-api")
router = APIRouter(tags=["query"])


@router.get("/api/stocks", response_model=ApiResponse)
async def api_stocks() -> ApiResponse:
    try:
        db = await get_db()
        return ApiResponse(data=await db.get_all_stocks())
    except Exception as exc:
        logger.exception("查询 stocks 失败")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/news/{stock_code}", response_model=ApiResponse)
async def api_news(stock_code: str, limit: int = Query(default=20, le=100)) -> ApiResponse:
    try:
        db = await get_db()
        return ApiResponse(data=await db.get_news_by_stock(stock_code, limit=limit))
    except Exception as exc:
        logger.exception("查询 news 失败")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/analysis", response_model=ApiResponse)
async def api_analysis(limit: int = Query(default=200, le=500)) -> ApiResponse:
    try:
        db = await get_db()
        return ApiResponse(data=await db.get_latest_analysis(limit=limit))
    except Exception as exc:
        logger.exception("查询 analysis 失败")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/analysis/{stock_code}", response_model=ApiResponse)
async def api_analysis_by_stock(stock_code: str) -> ApiResponse:
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
