from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.api.dependencies import get_current_user, get_session
from stock_service.crud import quant_crud
from stock_service.quant.application.sim_trading_engine import SimTradingEngine
from stock_service.quant.schemas import SimAccountCreate, TradeRequest
from stock_service.schemas.responses import ApiResponse

router = APIRouter(prefix="/api/quant/sim", tags=["quant-sim"])


@router.get("/accounts", response_model=ApiResponse)
async def list_accounts(
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):
    accounts = await quant_crud.list_sim_accounts(session, current_user.id)
    return ApiResponse(code=0, msg="ok", data=accounts)


@router.post("/accounts", response_model=ApiResponse)
async def create_account(
    req: SimAccountCreate,
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):
    engine = SimTradingEngine(session)
    account = await engine.create_account(
        user_id=current_user.id,
        account_name=req.account_name,
        initial_capital=req.initial_capital,
        strategy_id=req.strategy_id,
        config=req.config,
    )
    return ApiResponse(code=0, msg="ok", data=account)


@router.get("/accounts/{account_id}", response_model=ApiResponse)
async def get_account(
    account_id: int,
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):
    engine = SimTradingEngine(session)
    if not await engine.verify_ownership(current_user.id, account_id):
        raise HTTPException(403, "Not your account")
    account = await quant_crud.get_sim_account(session, account_id)
    return ApiResponse(code=0, msg="ok", data=account)


@router.delete("/accounts/{account_id}", response_model=ApiResponse)
async def delete_account(
    account_id: int,
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):
    engine = SimTradingEngine(session)
    if not await engine.verify_ownership(current_user.id, account_id):
        raise HTTPException(403, "Not your account")
    ok = await quant_crud.delete_sim_account(session, account_id)
    if not ok:
        raise HTTPException(404, "Account not found")
    return ApiResponse(code=0, msg="ok")


@router.get("/accounts/{account_id}/positions", response_model=ApiResponse)
async def get_positions(
    account_id: int,
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):
    engine = SimTradingEngine(session)
    if not await engine.verify_ownership(current_user.id, account_id):
        raise HTTPException(403, "Not your account")
    positions = await quant_crud.get_positions(session, account_id)
    return ApiResponse(code=0, msg="ok", data=positions)


@router.get("/accounts/{account_id}/orders", response_model=ApiResponse)
async def get_orders(
    account_id: int,
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):
    engine = SimTradingEngine(session)
    if not await engine.verify_ownership(current_user.id, account_id):
        raise HTTPException(403, "Not your account")
    orders = await quant_crud.list_trade_orders(session, account_id)
    return ApiResponse(code=0, msg="ok", data=orders)


@router.post("/trade", response_model=ApiResponse)
async def execute_trade(
    req: TradeRequest,
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):
    engine = SimTradingEngine(session)
    if not await engine.verify_ownership(current_user.id, req.account_id):
        raise HTTPException(403, "Not your account")

    try:
        if req.side == "buy":
            result = await engine.buy(req.account_id, req.code, req.quantity)
        else:
            result = await engine.sell(req.account_id, req.code, req.quantity)
        return ApiResponse(code=0, msg="ok", data=result)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/settlement", response_model=ApiResponse)
async def daily_settlement(
    account_id: int,
    trade_date: str,
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):
    engine = SimTradingEngine(session)
    if not await engine.verify_ownership(current_user.id, account_id):
        raise HTTPException(403, "Not your account")

    dt = date_type.fromisoformat(trade_date)
    triggered = await engine.daily_settlement(account_id, dt)
    return ApiResponse(code=0, msg="ok", data={"stop_loss_triggered": triggered})
