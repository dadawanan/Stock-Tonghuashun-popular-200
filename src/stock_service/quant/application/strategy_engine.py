from datetime import date
import logging

from stock_service.quant.domain.strategy_interface import (
    BaseStrategy, Signal, SignalType, StrategyContext,
)

logger = logging.getLogger(__name__)


class StrategyEngine:
    """Strategy dispatcher - manages and runs strategies."""

    def __init__(self):
        self._strategies: dict[str, BaseStrategy] = {}

    def register(self, name: str, strategy: BaseStrategy) -> None:
        self._strategies[name] = strategy

    def list_strategies(self) -> list[str]:
        return list(self._strategies.keys())

    async def run_strategy(
        self,
        strategy_name: str,
        stock_codes: list[str],
        context: StrategyContext,
    ) -> list[Signal]:
        strategy = self._strategies.get(strategy_name)
        if not strategy:
            raise ValueError(f"Strategy '{strategy_name}' not found")
        return await strategy.generate_signals(stock_codes, context)

    async def run_all(
        self,
        stock_codes: list[str],
        context: StrategyContext,
    ) -> dict[str, list[Signal]]:
        results = {}
        for name, strategy in self._strategies.items():
            try:
                results[name] = await strategy.generate_signals(stock_codes, context)
            except Exception as e:
                logger.error(f"Strategy {name} failed: {e}")
                results[name] = []
        return results


class PopularityStrategy(BaseStrategy):
    """Generate signals based on THS popularity ranking changes."""

    def __init__(self, params: dict | None = None):
        self._params = params or {
            "top_n": 50,
            "new_entry_score_boost": 1.2,
            "rank_drop_threshold": -20,
        }

    @property
    def name(self) -> str:
        return "人气榜策略"

    @property
    def strategy_type(self) -> str:
        return "popularity"

    def get_params(self) -> dict:
        return self._params.copy()

    def set_params(self, params: dict) -> None:
        self._params.update(params)

    async def generate_signals(
        self, stock_codes: list[str], context: StrategyContext
    ) -> list[Signal]:
        signals = []
        for code in stock_codes:
            pop = context.popularity.get(code)
            if not pop:
                continue

            rank = pop.get("rank", 999)
            if rank > self._params["top_n"]:
                continue

            is_new = pop.get("is_new_entry", False)
            rank_change = pop.get("rank_change", 0)

            if is_new:
                signals.append(Signal(
                    code=code, signal_type=SignalType.BUY,
                    score=min(1.0, 0.8 * self._params["new_entry_score_boost"]),
                    reason=f"新进入人气榜第{rank}名",
                ))
            elif rank_change <= self._params["rank_drop_threshold"]:
                signals.append(Signal(
                    code=code, signal_type=SignalType.BUY,
                    score=0.7,
                    reason=f"人气排名大幅下降{rank_change}位至第{rank}名",
                ))
            elif rank_change >= 30:
                signals.append(Signal(
                    code=code, signal_type=SignalType.SELL,
                    score=0.6,
                    reason=f"人气排名大幅上升{rank_change}位至第{rank}名，可能过热",
                ))

        return signals


class SentimentStrategy(BaseStrategy):
    """Generate signals based on text/market analysis scores."""

    def __init__(self, params: dict | None = None):
        self._params = params or {
            "text_weight": 0.55,
            "market_weight": 0.45,
            "buy_threshold": 2.0,
            "sell_threshold": -1.5,
        }

    @property
    def name(self) -> str:
        return "情绪驱动策略"

    @property
    def strategy_type(self) -> str:
        return "sentiment"

    def get_params(self) -> dict:
        return self._params.copy()

    def set_params(self, params: dict) -> None:
        self._params.update(params)

    async def generate_signals(
        self, stock_codes: list[str], context: StrategyContext
    ) -> list[Signal]:
        signals = []
        for code in stock_codes:
            analysis = context.analysis.get(code)
            if not analysis:
                continue

            text_score = analysis.get("text_score", 0) or 0
            market_score = analysis.get("market_score", 0) or 0
            integrated = (
                text_score * self._params["text_weight"]
                + market_score * self._params["market_weight"]
            )

            if integrated >= self._params["buy_threshold"]:
                signals.append(Signal(
                    code=code, signal_type=SignalType.BUY,
                    score=min(1.0, integrated / 5.0),
                    reason=f"综合情绪分 {integrated:.2f} >= {self._params['buy_threshold']}",
                ))
            elif integrated <= self._params["sell_threshold"]:
                signals.append(Signal(
                    code=code, signal_type=SignalType.SELL,
                    score=min(1.0, abs(integrated) / 5.0),
                    reason=f"综合情绪分 {integrated:.2f} <= {self._params['sell_threshold']}",
                ))

        return signals
