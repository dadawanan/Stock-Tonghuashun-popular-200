from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.db.models.quant_models import (
    BacktestDailyNav,
    BacktestResult,
    BacktestTrade,
    FeedbackLog,
    PositionAccount,
    PositionDailySnapshot,
    SimAccount,
    StockBasic,
    StockDaily,
    StockIndicator,
    Strategy,
    StrategyPick,
    TradeOrder,
)


def _rows_to_dicts(rows) -> list[dict]:
    return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]


# ── StockBasic ──


async def get_stock_basic_by_code(session: AsyncSession, code: str) -> dict | None:
    result = await session.execute(select(StockBasic).where(StockBasic.code == code))
    row = result.scalars().first()
    if row is None:
        return None
    return _rows_to_dicts([row])[0]


async def list_stock_basic(session: AsyncSession, *, market: str | None = None) -> list[dict]:
    stmt = select(StockBasic)
    if market:
        stmt = stmt.where(StockBasic.market == market)
    result = await session.execute(stmt.order_by(StockBasic.code))
    return _rows_to_dicts(result.scalars().all())


# ── StockDaily ──


async def get_stock_daily(
    session: AsyncSession, code: str, *, start_date: date | None = None, end_date: date | None = None
) -> list[dict]:
    stmt = select(StockDaily).where(StockDaily.code == code)
    if start_date:
        stmt = stmt.where(StockDaily.trade_date >= start_date)
    if end_date:
        stmt = stmt.where(StockDaily.trade_date <= end_date)
    result = await session.execute(stmt.order_by(StockDaily.trade_date.desc()))
    return _rows_to_dicts(result.scalars().all())


# ── StockIndicator ──


async def get_stock_indicator(session: AsyncSession, code: str, *, trade_date: date | None = None) -> dict | None:
    stmt = select(StockIndicator).where(StockIndicator.code == code)
    if trade_date:
        stmt = stmt.where(StockIndicator.trade_date == trade_date)
    stmt = stmt.order_by(StockIndicator.trade_date.desc()).limit(1)
    result = await session.execute(stmt)
    row = result.scalars().first()
    if row is None:
        return None
    return _rows_to_dicts([row])[0]


# ── StrategyPick ──


async def list_strategy_picks(session: AsyncSession, strategy_id: int) -> list[dict]:
    result = await session.execute(
        select(StrategyPick)
        .where(StrategyPick.strategy_id == strategy_id)
        .order_by(StrategyPick.trade_date.desc())
    )
    return _rows_to_dicts(result.scalars().all())


# ── BacktestResult ──


async def list_backtest_results(
    session: AsyncSession, strategy_id: int | None = None
) -> list[dict]:
    stmt = select(BacktestResult)
    if strategy_id is not None:
        stmt = stmt.where(BacktestResult.strategy_id == strategy_id)
    result = await session.execute(stmt.order_by(BacktestResult.created_at.desc()))
    return _rows_to_dicts(result.scalars().all())


# ── TradeOrder ──


async def list_trade_orders(session: AsyncSession, account_id: int) -> list[dict]:
    result = await session.execute(
        select(TradeOrder)
        .where(TradeOrder.account_id == account_id)
        .order_by(TradeOrder.created_at.desc())
    )
    return _rows_to_dicts(result.scalars().all())


# ── PositionAccount ──


async def get_positions(session: AsyncSession, account_id: int) -> list[dict]:
    result = await session.execute(
        select(PositionAccount).where(PositionAccount.account_id == account_id)
    )
    return _rows_to_dicts(result.scalars().all())


# ── Strategy ──


async def create_strategy(session: AsyncSession, data: dict) -> dict:
    strategy = Strategy(**data)
    session.add(strategy)
    await session.flush()
    return _rows_to_dicts([strategy])[0]


async def get_strategy(session: AsyncSession, strategy_id: int) -> dict | None:
    result = await session.execute(select(Strategy).where(Strategy.id == strategy_id))
    row = result.scalars().first()
    return _rows_to_dicts([row])[0] if row else None


async def list_strategies(session: AsyncSession, *, active_only: bool = True) -> list[dict]:
    stmt = select(Strategy)
    if active_only:
        stmt = stmt.where(Strategy.is_active == True)
    result = await session.execute(stmt.order_by(Strategy.id))
    return _rows_to_dicts(result.scalars().all())


_STRATEGY_ALLOWED = {"name", "type", "params", "description", "is_active"}


async def update_strategy(session: AsyncSession, strategy_id: int, data: dict) -> dict | None:
    strategy = await session.get(Strategy, strategy_id)
    if not strategy:
        return None
    for key, value in data.items():
        if key in _STRATEGY_ALLOWED:
            setattr(strategy, key, value)
    await session.flush()
    return _rows_to_dicts([strategy])[0]


async def delete_strategy(session: AsyncSession, strategy_id: int) -> bool:
    strategy = await session.get(Strategy, strategy_id)
    if not strategy:
        return False
    strategy.is_active = False
    await session.flush()
    return True


# ── BacktestResult (extended) ──


async def create_backtest_result(session: AsyncSession, data: dict) -> dict:
    result = BacktestResult(**data)
    session.add(result)
    await session.flush()
    return _rows_to_dicts([result])[0]


async def get_backtest_result(session: AsyncSession, backtest_id: int) -> dict | None:
    result = await session.execute(select(BacktestResult).where(BacktestResult.id == backtest_id))
    row = result.scalars().first()
    return _rows_to_dicts([row])[0] if row else None


# ── BacktestTrade ──


async def batch_insert_backtest_trades(session: AsyncSession, trades: list[dict]) -> int:
    if not trades:
        return 0
    for trade in trades:
        session.add(BacktestTrade(**trade))
    await session.flush()
    return len(trades)


async def get_backtest_trades(
    session: AsyncSession, backtest_id: int
) -> list[dict]:
    result = await session.execute(
        select(BacktestTrade)
        .where(BacktestTrade.backtest_id == backtest_id)
        .order_by(BacktestTrade.trade_date)
    )
    return _rows_to_dicts(result.scalars().all())


# ── BacktestDailyNav ──


async def batch_insert_backtest_nav(session: AsyncSession, navs: list[dict]) -> int:
    if not navs:
        return 0
    for nav in navs:
        session.add(BacktestDailyNav(**nav))
    await session.flush()
    return len(navs)


async def get_backtest_nav(
    session: AsyncSession, backtest_id: int
) -> list[dict]:
    result = await session.execute(
        select(BacktestDailyNav)
        .where(BacktestDailyNav.backtest_id == backtest_id)
        .order_by(BacktestDailyNav.trade_date)
    )
    return _rows_to_dicts(result.scalars().all())


# ── SimAccount ──


async def create_sim_account(session: AsyncSession, data: dict) -> dict:
    account = SimAccount(**data)
    session.add(account)
    await session.flush()
    return _rows_to_dicts([account])[0]


async def get_sim_account(session: AsyncSession, account_id: int) -> dict | None:
    result = await session.execute(select(SimAccount).where(SimAccount.id == account_id))
    row = result.scalars().first()
    return _rows_to_dicts([row])[0] if row else None


async def list_sim_accounts(session: AsyncSession, user_id: int) -> list[dict]:
    result = await session.execute(
        select(SimAccount)
        .where(SimAccount.user_id == user_id, SimAccount.status == "active")
        .order_by(SimAccount.id)
    )
    return _rows_to_dicts(result.scalars().all())


_SIM_ACCOUNT_ALLOWED = {"account_name", "current_capital", "total_assets", "status", "strategy_id", "config"}


async def update_sim_account(session: AsyncSession, account_id: int, data: dict) -> dict | None:
    account = await session.get(SimAccount, account_id)
    if not account:
        return None
    for key, value in data.items():
        if key in _SIM_ACCOUNT_ALLOWED:
            setattr(account, key, value)
    await session.flush()
    return _rows_to_dicts([account])[0]


# ── PositionDailySnapshot ──


async def batch_insert_position_snapshots(session: AsyncSession, snapshots: list[dict]) -> int:
    if not snapshots:
        return 0
    for snap in snapshots:
        session.add(PositionDailySnapshot(**snap))
    await session.flush()
    return len(snapshots)


# ── FeedbackLog ──


async def create_feedback_log(session: AsyncSession, data: dict) -> dict:
    log = FeedbackLog(**data)
    session.add(log)
    await session.flush()
    return _rows_to_dicts([log])[0]


async def list_feedback_logs(
    session: AsyncSession, backtest_id: int
) -> list[dict]:
    result = await session.execute(
        select(FeedbackLog)
        .where(FeedbackLog.backtest_id == backtest_id)
        .order_by(FeedbackLog.created_at.desc())
    )
    return _rows_to_dicts(result.scalars().all())


__all__ = [
    "get_stock_basic_by_code",
    "list_stock_basic",
    "get_stock_daily",
    "get_stock_indicator",
    "list_strategy_picks",
    "list_backtest_results",
    "list_trade_orders",
    "get_positions",
    "create_strategy",
    "get_strategy",
    "list_strategies",
    "update_strategy",
    "delete_strategy",
    "create_backtest_result",
    "get_backtest_result",
    "batch_insert_backtest_trades",
    "get_backtest_trades",
    "batch_insert_backtest_nav",
    "get_backtest_nav",
    "create_sim_account",
    "get_sim_account",
    "list_sim_accounts",
    "update_sim_account",
    "batch_insert_position_snapshots",
    "create_feedback_log",
    "list_feedback_logs",
]
