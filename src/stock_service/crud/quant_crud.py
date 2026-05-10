from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.db.models.quant_models import (
    BacktestResult,
    PositionAccount,
    StockBasic,
    StockDaily,
    StockIndicator,
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


async def list_backtest_results(session: AsyncSession, strategy_id: int) -> list[dict]:
    result = await session.execute(
        select(BacktestResult)
        .where(BacktestResult.strategy_id == strategy_id)
        .order_by(BacktestResult.created_at.desc())
    )
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


__all__ = [
    "get_stock_basic_by_code",
    "list_stock_basic",
    "get_stock_daily",
    "get_stock_indicator",
    "list_strategy_picks",
    "list_backtest_results",
    "list_trade_orders",
    "get_positions",
]
