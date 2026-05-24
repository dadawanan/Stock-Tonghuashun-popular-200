from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Index as _Index
from sqlalchemy.dialects.postgresql import BIGINT, JSONB, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class StockBasic(Base):
    __tablename__ = "stock_basic"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(VARCHAR(16), nullable=False, unique=True)
    name: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    market: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    industry: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
    list_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        _Index("idx_stock_basic_market", "market"),
    )


class StockDaily(Base):
    __tablename__ = "stock_daily"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(VARCHAR(16), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    high: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    low: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    close: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    volume: Mapped[Optional[int]] = mapped_column(BIGINT)
    amount: Mapped[Optional[int]] = mapped_column(BIGINT)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("code", "trade_date", name="uq_stock_daily_code_date"),
        _Index("idx_stock_daily_code_date", "code", "trade_date"),
    )


class StockIndicator(Base):
    __tablename__ = "stock_indicator"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(VARCHAR(16), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    ma5: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    ma20: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    rsi: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    macd: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("code", "trade_date", name="uq_stock_indicator_code_date"),
        _Index("idx_stock_indicator_code_date", "code", "trade_date"),
    )


class StrategyPick(Base):
    __tablename__ = "strategy_pick"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    strategy_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    code: Mapped[str] = mapped_column(VARCHAR(16), nullable=False)
    score: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (
        _Index("idx_strategy_pick_strategy_date", "strategy_id", "trade_date"),
        _Index("idx_strategy_pick_code", "code"),
    )


class BacktestResult(Base):
    __tablename__ = "backtest_result"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    strategy_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    annual_return: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    max_drawdown: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    sharpe: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    win_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (
        _Index("idx_backtest_result_strategy", "strategy_id", "created_at"),
    )


class TradeOrder(Base):
    __tablename__ = "trade_order"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    code: Mapped[str] = mapped_column(VARCHAR(16), nullable=False)
    side: Mapped[str] = mapped_column(VARCHAR(8), nullable=False)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    quantity: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[Optional[str]] = mapped_column(VARCHAR(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    strategy_id: Mapped[Optional[int]] = mapped_column(BIGINT)
    trade_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    commission: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), default=0)
    slippage: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4), default=0)

    __table_args__ = (
        _Index("idx_trade_order_account_time", "account_id", "created_at"),
        _Index("idx_trade_order_code", "code"),
    )


class PositionAccount(Base):
    __tablename__ = "position_account"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    code: Mapped[str] = mapped_column(VARCHAR(16), nullable=False)
    quantity: Mapped[Optional[int]] = mapped_column(Integer)
    avg_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    available_quantity: Mapped[Optional[int]] = mapped_column(Integer)
    highest_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    lowest_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))

    __table_args__ = (
        UniqueConstraint("account_id", "code", name="uq_position_account"),
        _Index("idx_position_account_id", "account_id"),
    )


class Strategy(Base):
    __tablename__ = "strategy"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    type: Mapped[str] = mapped_column(VARCHAR(32), nullable=False)
    params: Mapped[Optional[dict]] = mapped_column(JSONB)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())


class BacktestTrade(Base):
    __tablename__ = "backtest_trade"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    backtest_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    code: Mapped[str] = mapped_column(VARCHAR(16), nullable=False)
    side: Mapped[str] = mapped_column(VARCHAR(8), nullable=False)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    quantity: Mapped[Optional[int]] = mapped_column(Integer)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    pnl: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    signal_source: Mapped[Optional[str]] = mapped_column(VARCHAR(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (
        _Index("idx_backtest_trade_backtest", "backtest_id", "trade_date"),
    )


class BacktestDailyNav(Base):
    __tablename__ = "backtest_daily_nav"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    backtest_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    nav: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6))
    total_assets: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    cash: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    position_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    benchmark_nav: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (
        UniqueConstraint("backtest_id", "trade_date", name="uq_backtest_daily_nav"),
    )


class SimAccount(Base):
    __tablename__ = "sim_account"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    account_name: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    initial_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=1000000)
    current_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_assets: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    peak_assets: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(VARCHAR(16), default="active")
    strategy_id: Mapped[Optional[int]] = mapped_column(BIGINT)
    strategy_ids: Mapped[Optional[list]] = mapped_column(JSONB)  # 多策略 ID 列表
    config: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (
        _Index("idx_sim_account_user", "user_id"),
    )


class PositionDailySnapshot(Base):
    __tablename__ = "position_daily_snapshot"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    code: Mapped[str] = mapped_column(VARCHAR(16), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Optional[int]] = mapped_column(Integer)
    available_quantity: Mapped[Optional[int]] = mapped_column(Integer)
    avg_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    close_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    market_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    pnl: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    pnl_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (
        UniqueConstraint("account_id", "code", "trade_date", name="uq_position_snapshot"),
    )


class FeedbackLog(Base):
    __tablename__ = "feedback_log"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    backtest_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    strategy_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    feedback_type: Mapped[str] = mapped_column(VARCHAR(32), nullable=False)
    before_params: Mapped[Optional[dict]] = mapped_column(JSONB)
    after_params: Mapped[Optional[dict]] = mapped_column(JSONB)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(VARCHAR(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())


class PendingOrder(Base):
    __tablename__ = "pending_order"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BIGINT, nullable=False)
    code: Mapped[str] = mapped_column(VARCHAR(16), nullable=False)
    side: Mapped[str] = mapped_column(VARCHAR(8), nullable=False)
    target_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(VARCHAR(16), default="pending")
    note: Mapped[Optional[str]] = mapped_column(Text)
    filled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    filled_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=func.now())

    __table_args__ = (
        _Index("idx_pending_order_account", "account_id", "status"),
        _Index("idx_pending_order_status", "status"),
    )


__all__ = [
    "StockBasic",
    "StockDaily",
    "StockIndicator",
    "StrategyPick",
    "BacktestResult",
    "TradeOrder",
    "PositionAccount",
    "Strategy",
    "BacktestTrade",
    "BacktestDailyNav",
    "SimAccount",
    "PositionDailySnapshot",
    "FeedbackLog",
    "PendingOrder",
]
