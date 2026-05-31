from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class SignalType(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class MarketRegime(Enum):
    """市场环境分类"""
    BULL = "bull"           # 牛市：MA50 > MA200，趋势向上
    BEAR = "bear"           # 熊市：MA50 < MA200，趋势向下
    SIDEWAYS = "sideways"   # 震荡：MA50 ≈ MA200，无明确趋势


@dataclass
class Signal:
    code: str
    signal_type: SignalType
    score: float  # 0-1 signal strength
    reason: str
    target_price: float | None = None
    stop_loss: float | None = None


@dataclass
class StrategyContext:
    """Context passed to strategy for signal generation."""
    trade_date: date
    # Market data: code -> {open, high, low, close, volume, ...}
    market_data: dict[str, dict]
    # Indicators: code -> {ma5, ma20, rsi, macd, ...}
    indicators: dict[str, dict]
    # Analysis results: code -> {text_score, market_score, integrated_score, ...}
    analysis: dict[str, dict]
    # Popularity data: code -> {rank, score, is_new_entry, rank_change}
    popularity: dict[str, dict]
    # Current positions: code -> {quantity, avg_price, ...}
    positions: dict[str, dict]
    # 市场环境（基于沪深300 MA50/MA200）
    market_regime: MarketRegime = MarketRegime.SIDEWAYS


class BaseStrategy(ABC):
    """Abstract base class for all strategies."""

    @abstractmethod
    async def generate_signals(
        self,
        stock_codes: list[str],
        context: StrategyContext,
    ) -> list[Signal]:
        """Generate trading signals for given stocks."""
        pass

    @abstractmethod
    def get_params(self) -> dict:
        """Return current strategy parameters."""
        pass

    @abstractmethod
    def set_params(self, params: dict) -> None:
        """Update strategy parameters."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy display name."""
        pass

    @property
    @abstractmethod
    def strategy_type(self) -> str:
        """Strategy type identifier: popularity/sentiment/technical/multi_factor."""
        pass
