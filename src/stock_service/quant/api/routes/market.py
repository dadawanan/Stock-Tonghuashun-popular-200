"""实时行情 API"""

import asyncio

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.api.dependencies import get_current_user, get_session
from stock_service.infrastructure.providers.tencent_provider import fetch_realtime_price
from stock_service.schemas.responses import ApiResponse

router = APIRouter(prefix="/api/quant/market", tags=["quant-market"])


@router.get("/prices", response_model=ApiResponse)
async def get_realtime_prices(
    codes: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """获取多只股票的实时价格

    Args:
        codes: 股票代码，逗号分隔，如 "000001.SZ,000725.SZ"
    """
    code_list = [c.strip() for c in codes.split(",") if c.strip()]

    prices = {}
    for code in code_list:
        try:
            price = await asyncio.to_thread(fetch_realtime_price, code)
            prices[code] = price
        except Exception:
            prices[code] = None

    return ApiResponse(code=0, msg="ok", data=prices)
