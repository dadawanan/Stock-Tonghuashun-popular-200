from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


# ── Strategy ──


class StrategyCreate(BaseModel):
    name: str
    type: Literal[
        "popularity", "sentiment", "technical", "multi_factor",
        "volume_price", "momentum", "mean_reversion",
        "fund_flow", "breakout", "grid",
    ]
    params: dict = {}
    description: str | None = None


class StrategyUpdate(BaseModel):
    name: str | None = None
    params: dict | None = None
    description: str | None = None
    is_active: bool | None = None


class StrategyResponse(BaseModel):
    id: int
    name: str
    type: str
    params: dict | None
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ── Backtest ──


class BacktestRequest(BaseModel):
    strategy_id: int | None = None  # legacy 引擎需要
    start_date: date
    end_date: date
    initial_capital: float = 1_000_000.0
    commission_rate: float = 0.0003
    stamp_tax: float = 0.001
    slippage: float = 0.002
    max_position_pct: float = 0.2
    max_holdings: int = 10
    stop_loss_pct: float = -0.08
    stock_codes: list[str] | None = None
    # VectorBT 支持
    engine: str = "legacy"  # "legacy" | "vectorbt"
    strategy_type: str | None = None  # VectorBT 策略类型 (vbt_ma_cross, vbt_rsi, etc.)
    strategy_params: dict | None = None  # VectorBT 策略参数


class BacktestResponse(BaseModel):
    id: int
    strategy_id: int
    start_date: date
    end_date: date
    total_return: float | None
    annual_return: float | None
    max_drawdown: float | None
    sharpe_ratio: float | None
    win_rate: float | None
    total_trades: int | None
    created_at: datetime


class BacktestTradeResponse(BaseModel):
    code: str
    side: str
    price: float | None
    quantity: int | None
    trade_date: date
    pnl: float | None
    signal_source: str | None


class BacktestNavResponse(BaseModel):
    trade_date: date
    nav: float | None
    total_assets: float | None
    cash: float | None
    position_value: float | None
    benchmark_nav: float | None


# ── Sim Trading ──


class SimAccountCreate(BaseModel):
    account_name: str
    initial_capital: float = 1_000_000.0
    strategy_id: int | None = None
    config: dict | None = None


class SimAccountResponse(BaseModel):
    id: int
    user_id: int
    account_name: str
    initial_capital: float
    current_capital: float
    total_assets: float
    status: str
    strategy_id: int | None
    created_at: datetime


class TradeRequest(BaseModel):
    account_id: int
    code: str
    side: Literal["buy", "sell"]
    quantity: int
    price: float | None = None


class PositionResponse(BaseModel):
    code: str
    quantity: int
    available_quantity: int | None
    avg_price: float
    current_price: float | None
    market_value: float | None
    pnl: float | None
    pnl_pct: float | None


class TradeOrderResponse(BaseModel):
    id: int
    code: str
    side: str
    price: float | None
    quantity: int | None
    status: str | None
    commission: float | None
    pnl: float | None = None
    created_at: datetime


# ── Feedback ──


class FeedbackInsightResponse(BaseModel):
    overall: dict
    by_signal: dict
    suggestions: list[str]


class WeightAdjustmentRequest(BaseModel):
    strategy_id: int
    adjustments: dict[str, float]
    reason: str
