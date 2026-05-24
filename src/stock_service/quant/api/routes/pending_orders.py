"""挂单管理 API"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.api.dependencies import get_current_user, get_session
from stock_service.crud import quant_crud
from stock_service.quant.application.sim_trading_engine import SimTradingEngine
from stock_service.schemas.responses import ApiResponse

router = APIRouter(prefix="/api/quant/pending-orders", tags=["quant-pending-orders"])


@router.get("/", response_model=ApiResponse)
async def list_orders(
    account_id: int,
    status: str | None = "pending",
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """获取账户的挂单列表"""
    engine = SimTradingEngine(session)
    if not await engine.verify_ownership(current_user.id, account_id):
        raise HTTPException(403, "Not your account")

    orders = await quant_crud.list_pending_orders(session, account_id, status)
    return ApiResponse(code=0, msg="ok", data=orders)


@router.post("/", response_model=ApiResponse)
async def create_order(
    account_id: int,
    code: str,
    side: str,
    target_price: float,
    quantity: int,
    note: str | None = None,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """创建挂单"""
    if side not in ("buy", "sell"):
        raise HTTPException(400, "side must be 'buy' or 'sell'")
    if target_price <= 0:
        raise HTTPException(400, "target_price must be positive")
    if quantity < 100 or quantity % 100 != 0:
        raise HTTPException(400, "quantity must be multiple of 100")

    engine = SimTradingEngine(session)
    if not await engine.verify_ownership(current_user.id, account_id):
        raise HTTPException(403, "Not your account")

    # 验证卖出时有足够持仓
    if side == "sell":
        position = await quant_crud.get_position(session, account_id, code)
        if not position or position.get("available_quantity", 0) < quantity:
            raise HTTPException(400, "Insufficient position for sell order")

    order = await quant_crud.create_pending_order(session, {
        "account_id": account_id,
        "code": code,
        "side": side,
        "target_price": target_price,
        "quantity": quantity,
        "note": note,
    })
    return ApiResponse(code=0, msg="ok", data=order)


@router.delete("/{order_id}", response_model=ApiResponse)
async def cancel_order(
    order_id: int,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """取消挂单"""
    order = await quant_crud.get_pending_order(session, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    engine = SimTradingEngine(session)
    if not await engine.verify_ownership(current_user.id, order["account_id"]):
        raise HTTPException(403, "Not your account")

    ok = await quant_crud.cancel_pending_order(session, order_id)
    if not ok:
        raise HTTPException(400, "Order cannot be cancelled")
    return ApiResponse(code=0, msg="ok")


@router.post("/cancel-all", response_model=ApiResponse)
async def cancel_all_orders(
    account_id: int,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(get_current_user),
):
    """取消账户所有挂单"""
    engine = SimTradingEngine(session)
    if not await engine.verify_ownership(current_user.id, account_id):
        raise HTTPException(403, "Not your account")

    count = await quant_crud.cancel_all_pending_orders(session, account_id)
    return ApiResponse(code=0, msg="ok", data={"cancelled": count})
