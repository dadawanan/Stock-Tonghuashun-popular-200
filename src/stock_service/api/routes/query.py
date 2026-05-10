from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.api.dependencies import get_session
from stock_service.crud import v2_crud
from stock_service.schemas.responses import ApiResponse


logger = logging.getLogger("stock-api")
router = APIRouter(tags=["query"])


@router.get("/api/stocks", response_model=ApiResponse)
async def api_stocks(session: AsyncSession = Depends(get_session)) -> ApiResponse:
    try:
        return ApiResponse(data=await v2_crud.get_all_stocks(session))
    except Exception as exc:
        logger.exception("查询 stocks 失败")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/news/{stock_code}", response_model=ApiResponse)
async def api_news(
    stock_code: str,
    limit: int = Query(default=20, le=100),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    try:
        return ApiResponse(data=await v2_crud.get_news_by_stock(session, stock_code, limit=limit))
    except Exception as exc:
        logger.exception("查询 news 失败")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/analysis", response_model=ApiResponse)
async def api_analysis(
    limit: int = Query(default=200, le=500),
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    try:
        return ApiResponse(data=await v2_crud.get_latest_analysis(session, limit=limit))
    except Exception as exc:
        logger.exception("查询 analysis 失败")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/analysis/{stock_code}", response_model=ApiResponse)
async def api_analysis_by_stock(
    stock_code: str,
    session: AsyncSession = Depends(get_session),
) -> ApiResponse:
    try:
        row = await v2_crud.get_analysis_by_stock(session, stock_code)
        if row is None:
            raise HTTPException(status_code=404, detail=f"未找到 {stock_code} 的分析结果")
        return ApiResponse(data=row)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("查询 analysis by stock 失败")
        raise HTTPException(status_code=500, detail=str(exc))
