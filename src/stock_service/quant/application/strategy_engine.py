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


class TechnicalStrategy(BaseStrategy):
    """Generate signals based on technical indicators."""

    def __init__(self, params: dict | None = None):
        self._params = params or {
            "ma_short": 5,
            "ma_long": 20,
            "rsi_overbought": 70,
            "rsi_oversold": 30,
        }

    @property
    def name(self) -> str:
        return "技术面策略"

    @property
    def strategy_type(self) -> str:
        return "technical"

    def get_params(self) -> dict:
        return self._params.copy()

    def set_params(self, params: dict) -> None:
        self._params.update(params)

    async def generate_signals(
        self, stock_codes: list[str], context: StrategyContext
    ) -> list[Signal]:
        signals = []
        for code in stock_codes:
            ind = context.indicators.get(code)
            if not ind:
                continue

            ma_short = ind.get(f"ma{self._params['ma_short']}")
            ma_long = ind.get(f"ma{self._params['ma_long']}")
            rsi = ind.get("rsi")
            macd = ind.get("macd")
            macd_signal = ind.get("macd_signal")

            reasons = []
            score = 0.0

            if ma_short and ma_long:
                if ma_short > ma_long:
                    score += 0.3
                    reasons.append(f"MA{self._params['ma_short']}上穿MA{self._params['ma_long']}")
                else:
                    score -= 0.3
                    reasons.append(f"MA{self._params['ma_short']}下穿MA{self._params['ma_long']}")

            if rsi is not None:
                if rsi <= self._params["rsi_oversold"]:
                    score += 0.3
                    reasons.append(f"RSI超卖({rsi:.1f})")
                elif rsi >= self._params["rsi_overbought"]:
                    score -= 0.3
                    reasons.append(f"RSI超买({rsi:.1f})")

            if macd is not None and macd_signal is not None:
                if macd > macd_signal:
                    score += 0.2
                    reasons.append("MACD金叉")
                else:
                    score -= 0.2
                    reasons.append("MACD死叉")

            if score > 0.3:
                signals.append(Signal(
                    code=code, signal_type=SignalType.BUY,
                    score=min(1.0, score), reason="; ".join(reasons),
                ))
            elif score < -0.3:
                signals.append(Signal(
                    code=code, signal_type=SignalType.SELL,
                    score=min(1.0, abs(score)), reason="; ".join(reasons),
                ))

        return signals


class MultiFactorStrategy(BaseStrategy):
    """Combine multiple signal sources with configurable weights."""

    def __init__(self, params: dict | None = None):
        self._params = params or {
            "weights": {
                "popularity": 0.25,
                "sentiment": 0.35,
                "technical": 0.40,
            },
            "buy_threshold": 0.6,
            "sell_threshold": -0.4,
        }
        self._sub_strategies = {
            "popularity": PopularityStrategy(),
            "sentiment": SentimentStrategy(),
            "technical": TechnicalStrategy(),
        }

    @property
    def name(self) -> str:
        return "多因子策略"

    @property
    def strategy_type(self) -> str:
        return "multi_factor"

    def get_params(self) -> dict:
        return self._params.copy()

    def set_params(self, params: dict) -> None:
        self._params.update(params)
        if "weights" in params:
            self._params["weights"] = params["weights"]

    async def generate_signals(
        self, stock_codes: list[str], context: StrategyContext
    ) -> list[Signal]:
        sub_signals: dict[str, dict[str, float]] = {}
        sub_reasons: dict[str, dict[str, str]] = {}

        for factor_name, strategy in self._sub_strategies.items():
            signals = await strategy.generate_signals(stock_codes, context)
            for sig in signals:
                if sig.code not in sub_signals:
                    sub_signals[sig.code] = {}
                    sub_reasons[sig.code] = {}
                direction = 1.0 if sig.signal_type == SignalType.BUY else -1.0
                sub_signals[sig.code][factor_name] = direction * sig.score
                sub_reasons[sig.code][factor_name] = sig.reason

        weights = self._params["weights"]
        results = []
        for code, factor_scores in sub_signals.items():
            combined = sum(
                factor_scores.get(factor, 0) * weight
                for factor, weight in weights.items()
            )
            if combined >= self._params["buy_threshold"]:
                reasons = [sub_reasons[code].get(f, "") for f in weights if f in sub_reasons.get(code, {})]
                results.append(Signal(
                    code=code, signal_type=SignalType.BUY,
                    score=min(1.0, combined),
                    reason=f"多因子综合分{combined:.2f}: " + "; ".join(filter(None, reasons)),
                ))
            elif combined <= self._params["sell_threshold"]:
                reasons = [sub_reasons[code].get(f, "") for f in weights if f in sub_reasons.get(code, {})]
                results.append(Signal(
                    code=code, signal_type=SignalType.SELL,
                    score=min(1.0, abs(combined)),
                    reason=f"多因子综合分{combined:.2f}: " + "; ".join(filter(None, reasons)),
                ))

        return results
