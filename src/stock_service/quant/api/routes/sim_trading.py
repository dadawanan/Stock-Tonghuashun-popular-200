from datetime import date as date_type
from decimal import Decimal

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


@router.put("/accounts/{account_id}", response_model=ApiResponse)
async def update_account(
    account_id: int,
    data: dict,
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):
    """Update sim account (e.g., strategy_id, strategy_ids)"""
    engine = SimTradingEngine(session)
    if not await engine.verify_ownership(current_user.id, account_id):
        raise HTTPException(403, "Not your account")

    # Only allow updating certain fields
    allowed = {"strategy_id", "strategy_ids", "account_name"}
    update_data = {k: v for k, v in data.items() if k in allowed}
    if not update_data:
        raise HTTPException(400, "No valid fields to update")

    account = await quant_crud.update_sim_account(session, account_id, update_data)
    if not account:
        raise HTTPException(404, "Account not found")
    return ApiResponse(code=0, msg="ok", data=account)


@router.post("/accounts/{account_id}/resume", response_model=ApiResponse)
async def resume_account(
    account_id: int,
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):
    """恢复被暂停的账户（将 drawdown_halt 改回 active）"""
    engine = SimTradingEngine(session)
    if not await engine.verify_ownership(current_user.id, account_id):
        raise HTTPException(403, "Not your account")

    account = await quant_crud.get_sim_account(session, account_id)
    if not account:
        raise HTTPException(404, "Account not found")
    if account["status"] == "active":
        return ApiResponse(code=0, msg="账户已是活跃状态")
    if account["status"] != "drawdown_halt":
        raise HTTPException(400, f"当前状态 '{account['status']}' 不支持恢复，仅支持从 drawdown_halt 恢复")

    # 将 peak_assets 重置为当前 total_assets，避免恢复后立即再次触发回撤
    total_assets = float(account.get("total_assets", 0))
    await quant_crud.update_sim_account(session, account_id, {
        "status": "active",
        "peak_assets": Decimal(str(round(total_assets, 2))),
    })
    return ApiResponse(code=0, msg="账户已恢复")


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


@router.get("/accounts/{account_id}/daily-assets", response_model=ApiResponse)
async def get_daily_assets(
    account_id: int,
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):
    """获取账户每日资产变化"""
    engine = SimTradingEngine(session)
    if not await engine.verify_ownership(current_user.id, account_id):
        raise HTTPException(403, "Not your account")

    snapshots = await quant_crud.get_position_snapshots(session, account_id)
    # 按日期聚合
    daily = {}
    for snap in snapshots:
        d = str(snap.get("trade_date", ""))
        if d not in daily:
            daily[d] = {"trade_date": d, "market_value": 0, "pnl": 0}
        daily[d]["market_value"] += float(snap.get("market_value", 0) or 0)
        daily[d]["pnl"] += float(snap.get("pnl", 0) or 0)

    result = sorted(daily.values(), key=lambda x: x["trade_date"])
    return ApiResponse(code=0, msg="ok", data=result)


@router.get("/accounts/{account_id}/trade-analysis", response_model=ApiResponse)
async def get_trade_analysis(
    account_id: int,
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):
    """获取账户交易分析统计"""
    engine = SimTradingEngine(session)
    if not await engine.verify_ownership(current_user.id, account_id):
        raise HTTPException(403, "Not your account")

    orders = await quant_crud.list_trade_orders(session, account_id)

    # 计算交易统计
    sell_orders = [o for o in orders if o.get("side") == "sell"]
    buy_orders = [o for o in orders if o.get("side") == "buy"]

    wins = [o for o in sell_orders if float(o.get("pnl", 0) or 0) > 0]
    losses = [o for o in sell_orders if float(o.get("pnl", 0) or 0) < 0]

    total_pnl = sum(float(o.get("pnl", 0) or 0) for o in sell_orders)
    avg_win = sum(float(o.get("pnl", 0) or 0) for o in wins) / len(wins) if wins else 0
    avg_loss = sum(float(o.get("pnl", 0) or 0) for o in losses) / len(losses) if losses else 0

    # 计算平均持仓天数（简化：用订单时间差估算）
    from datetime import datetime as _dt
    holding_days = []
    for buy in buy_orders:
        # 找对应的卖出
        for sell in sell_orders:
            if sell.get("code") == buy.get("code") and sell.get("created_at", "") > buy.get("created_at", ""):
                buy_time = buy.get("created_at")
                sell_time = sell.get("created_at")
                if buy_time and sell_time:
                    try:
                        # created_at 可能是 datetime 对象或字符串
                        if isinstance(buy_time, _dt):
                            bt = buy_time
                        else:
                            bt = _dt.fromisoformat(str(buy_time).replace("Z", "+00:00"))
                        if isinstance(sell_time, _dt):
                            st = sell_time
                        else:
                            st = _dt.fromisoformat(str(sell_time).replace("Z", "+00:00"))
                        holding_days.append((st - bt).days)
                    except (ValueError, TypeError):
                        pass
                break

    avg_holding = sum(holding_days) / len(holding_days) if holding_days else 0

    # 计算最大连续亏损
    max_consecutive_losses = 0
    current_losses = 0
    for o in sell_orders:
        if float(o.get("pnl", 0) or 0) < 0:
            current_losses += 1
            max_consecutive_losses = max(max_consecutive_losses, current_losses)
        else:
            current_losses = 0

    analysis = {
        "total_trades": len(orders),
        "buy_count": len(buy_orders),
        "sell_count": len(sell_orders),
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": len(wins) / len(sell_orders) if sell_orders else 0,
        "total_pnl": round(total_pnl, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_loss_ratio": round(abs(avg_win / avg_loss), 2) if avg_loss != 0 else 0,
        "avg_holding_days": round(avg_holding, 1),
        "max_consecutive_losses": max_consecutive_losses,
    }

    return ApiResponse(code=0, msg="ok", data=analysis)


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
    result = await engine.daily_settlement(account_id, dt)
    return ApiResponse(code=0, msg="ok", data=result)
