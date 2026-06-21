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
            # 卖出条件
            "sell_rank_rise": 30,           # 排名上升多少位卖出（过热）
            "sell_rank_exit": 100,          # 排名跌出多少位卖出（退出热门）
            "sell_profit_pct": 0.10,        # 盈利多少比例卖出（止盈）
            "sell_loss_pct": -0.05,         # 亏损多少比例卖出（止损，比固定止损更灵活）
            "sell_hold_days": 10,           # 持有超过多少天且不赚钱就卖出
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
            pos = context.positions.get(code)

            # ── 持仓股的卖出逻辑 ──
            if pos:
                rank = pop.get("rank", 999) if pop else 999
                avg_price = pos.get("avg_price", 0)
                current_price = pos.get("current_price", 0) or context.market_data.get(code, {}).get("close", 0)

                if avg_price > 0 and current_price > 0:
                    pnl_pct = (current_price - avg_price) / avg_price

                    # 1. 止盈：盈利达到阈值
                    if pnl_pct >= self._params["sell_profit_pct"]:
                        signals.append(Signal(
                            code=code, signal_type=SignalType.SELL,
                            score=min(1.0, 0.5 + pnl_pct),
                            reason=f"止盈卖出: 盈利{pnl_pct:.1%}，目标{self._params['sell_profit_pct']:.0%}",
                        ))
                        continue

                    # 2. 止损：亏损达到阈值
                    if pnl_pct <= self._params["sell_loss_pct"]:
                        signals.append(Signal(
                            code=code, signal_type=SignalType.SELL,
                            score=min(1.0, 0.5 + abs(pnl_pct)),
                            reason=f"止损卖出: 亏损{pnl_pct:.1%}，阈值{self._params['sell_loss_pct']:.0%}",
                        ))
                        continue

                    # 3. 退出热门：排名跌出阈值
                    if rank > self._params["sell_rank_exit"]:
                        signals.append(Signal(
                            code=code, signal_type=SignalType.SELL,
                            score=0.6,
                            reason=f"退出热门: 排名{rank}已跌出Top{self._params['sell_rank_exit']}",
                        ))
                        continue

                # 不在热门榜了也要卖出
                if not pop or pop.get("rank", 999) > self._params["top_n"]:
                    signals.append(Signal(
                        code=code, signal_type=SignalType.SELL,
                        score=0.5,
                        reason=f"不再热门: 排名{pop.get('rank', 'N/A') if pop else 'N/A'}",
                    ))
                    continue

            # ── 买入逻辑（仅对非持仓股）──
            if not pop:
                continue

            rank = pop.get("rank", 999)
            if rank > self._params["top_n"]:
                continue

            # 已持仓的不重复买入
            if code in context.positions:
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

        return signals


class SentimentStrategy(BaseStrategy):
    """Generate signals based on text/market analysis scores."""

    def __init__(self, params: dict | None = None):
        self._params = params or {
            "text_weight": 0.55,
            "market_weight": 0.45,
            "buy_threshold": 2.0,
            "sell_threshold": -1.5,
            # 卖出条件
            "sell_profit_pct": 0.10,        # 盈利多少比例卖出
            "sell_loss_pct": -0.05,         # 亏损多少比例卖出
            "sell_score_drop": 0.5,         # 情绪分下降多少卖出
            "max_holdings": 10,             # 最大持仓数
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
            pos = context.positions.get(code)

            # ── 持仓股的卖出逻辑 ──
            if pos:
                avg_price = pos.get("avg_price", 0)
                current_price = pos.get("current_price", 0) or context.market_data.get(code, {}).get("close", 0)

                if avg_price > 0 and current_price > 0:
                    pnl_pct = (current_price - avg_price) / avg_price

                    # 1. 止盈：盈利达到阈值
                    if pnl_pct >= self._params["sell_profit_pct"]:
                        signals.append(Signal(
                            code=code, signal_type=SignalType.SELL,
                            score=min(1.0, 0.5 + pnl_pct),
                            reason=f"止盈卖出: 盈利{pnl_pct:.1%}",
                        ))
                        continue

                    # 2. 止损：亏损达到阈值
                    if pnl_pct <= self._params["sell_loss_pct"]:
                        signals.append(Signal(
                            code=code, signal_type=SignalType.SELL,
                            score=min(1.0, 0.5 + abs(pnl_pct)),
                            reason=f"止损卖出: 亏损{pnl_pct:.1%}",
                        ))
                        continue

                # 3. 情绪恶化卖出
                if analysis:
                    text_score = analysis.get("text_score", 0) or 0
                    market_score = analysis.get("market_score", 0) or 0
                    integrated = (
                        text_score * self._params["text_weight"]
                        + market_score * self._params["market_weight"]
                    )
                    if integrated <= self._params["sell_threshold"]:
                        signals.append(Signal(
                            code=code, signal_type=SignalType.SELL,
                            score=min(1.0, abs(integrated) / 5.0),
                            reason=f"情绪恶化: 综合分{integrated:.2f} <= {self._params['sell_threshold']}",
                        ))
                        continue

            # ── 买入逻辑（仅对非持仓股）──
            if not analysis:
                continue

            # 已持仓的不重复买入
            if code in context.positions:
                continue

            # 持仓数量限制
            if len(context.positions) >= self._params["max_holdings"]:
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

        return signals


class TechnicalStrategy(BaseStrategy):
    """Generate signals based on technical indicators."""

    def __init__(self, params: dict | None = None):
        self._params = params or {
            "ma_short": 5,
            "ma_long": 20,
            "rsi_overbought": 70,
            "rsi_oversold": 30,
            "buy_threshold": 0.3,
            "sell_threshold": -0.3,
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

            buy_threshold = self._params.get("buy_threshold", 0.3)
            sell_threshold = self._params.get("sell_threshold", -0.3)

            # 市场环境调整：熊市收紧买入、牛市放宽
            from stock_service.quant.domain.strategy_interface import MarketRegime
            regime = context.market_regime
            if regime == MarketRegime.BEAR:
                buy_threshold *= 1.5  # 熊市买入门槛提高 50%
            elif regime == MarketRegime.BULL:
                buy_threshold *= 0.8  # 牛市买入门槛降低 20%

            if score > buy_threshold:
                env_tag = f"[{regime.value}]" if regime != MarketRegime.SIDEWAYS else ""
                signals.append(Signal(
                    code=code, signal_type=SignalType.BUY,
                    score=min(1.0, score), reason=f"{env_tag}" + "; ".join(reasons) if reasons else "",
                ))
            elif score < sell_threshold:
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


class VolumePriceStrategy(BaseStrategy):
    """量价策略：基于成交量和价格的关系生成信号"""

    def __init__(self, params: dict | None = None):
        self._params = params or {
            "volume_ratio_threshold": 1.5,  # 放量倍数阈值
            "price_change_threshold": 2.0,   # 涨跌幅阈值(%)
            "buy_threshold": 0.3,
            "sell_threshold": -0.3,
        }

    @property
    def name(self) -> str:
        return "量价策略"

    @property
    def strategy_type(self) -> str:
        return "volume_price"

    def get_params(self) -> dict:
        return self._params.copy()

    def set_params(self, params: dict) -> None:
        self._params.update(params)

    async def generate_signals(
        self, stock_codes: list[str], context: StrategyContext
    ) -> list[Signal]:
        signals = []
        for code in stock_codes:
            market = context.market_data.get(code, {})
            if not market:
                continue

            pct_change = market.get("pct_change", 0) or 0
            volume_ratio = market.get("volume_ratio", 1) or 1

            score = 0.0
            reasons = []

            # 放量上涨 = 买入信号
            if volume_ratio >= self._params["volume_ratio_threshold"]:
                if pct_change >= self._params["price_change_threshold"]:
                    score += 0.5
                    reasons.append(f"放量上涨(量比{volume_ratio:.1f}, 涨{pct_change:.1f}%)")
                elif pct_change <= -self._params["price_change_threshold"]:
                    score -= 0.5
                    reasons.append(f"放量下跌(量比{volume_ratio:.1f}, 跌{pct_change:.1f}%)")
            # 缩量横盘 = 观望
            elif volume_ratio < 0.8 and abs(pct_change) < 1:
                score = 0
                reasons.append("缩量横盘，观望")

            if score >= self._params["buy_threshold"]:
                signals.append(Signal(
                    code=code, signal_type=SignalType.BUY,
                    score=min(1.0, score), reason="; ".join(reasons),
                ))
            elif score <= self._params["sell_threshold"]:
                signals.append(Signal(
                    code=code, signal_type=SignalType.SELL,
                    score=min(1.0, abs(score)), reason="; ".join(reasons),
                ))

        return signals


class MomentumStrategy(BaseStrategy):
    """动量策略：基于价格动量生成信号"""

    def __init__(self, params: dict | None = None):
        self._params = params or {
            "lookback_days": 5,           # 回看天数
            "momentum_threshold": 3.0,    # 动量阈值(%)
            "buy_threshold": 0.3,
            "sell_threshold": -0.3,
        }

    @property
    def name(self) -> str:
        return "动量策略"

    @property
    def strategy_type(self) -> str:
        return "momentum"

    def get_params(self) -> dict:
        return self._params.copy()

    def set_params(self, params: dict) -> None:
        self._params.update(params)

    async def generate_signals(
        self, stock_codes: list[str], context: StrategyContext
    ) -> list[Signal]:
        signals = []
        for code in stock_codes:
            market = context.market_data.get(code, {})
            if not market:
                continue

            pct_change = market.get("pct_change", 0) or 0

            score = 0.0
            reasons = []

            # 强势动量 = 买入
            if pct_change >= self._params["momentum_threshold"]:
                score = min(1.0, pct_change / 10)
                reasons.append(f"强势动量(涨幅{pct_change:.1f}%)")
            # 弱势动量 = 卖出
            elif pct_change <= -self._params["momentum_threshold"]:
                score = -min(1.0, abs(pct_change) / 10)
                reasons.append(f"弱势动量(跌幅{pct_change:.1f}%)")

            # 市场环境调整
            from stock_service.quant.domain.strategy_interface import MarketRegime
            buy_threshold = self._params["buy_threshold"]
            sell_threshold = self._params["sell_threshold"]
            if context.market_regime == MarketRegime.BEAR:
                buy_threshold *= 1.5
                sell_threshold *= 0.8

            if score >= buy_threshold:
                signals.append(Signal(
                    code=code, signal_type=SignalType.BUY,
                    score=min(1.0, score), reason="; ".join(reasons),
                ))
            elif score <= sell_threshold:
                signals.append(Signal(
                    code=code, signal_type=SignalType.SELL,
                    score=min(1.0, abs(score)), reason="; ".join(reasons),
                ))

        return signals


class MeanReversionStrategy(BaseStrategy):
    """均值回归策略：价格偏离均线过多时反向操作"""

    def __init__(self, params: dict | None = None):
        self._params = params or {
            "deviation_threshold": 5.0,  # 偏离均线阈值(%)
            "ma_period": 20,             # 均线周期
            "buy_threshold": 0.3,
            "sell_threshold": -0.3,
        }

    @property
    def name(self) -> str:
        return "均值回归策略"

    @property
    def strategy_type(self) -> str:
        return "mean_reversion"

    def get_params(self) -> dict:
        return self._params.copy()

    def set_params(self, params: dict) -> None:
        self._params.update(params)

    async def generate_signals(
        self, stock_codes: list[str], context: StrategyContext
    ) -> list[Signal]:
        signals = []
        for code in stock_codes:
            market = context.market_data.get(code, {})
            ind = context.indicators.get(code, {})
            if not market or not ind:
                continue

            close = market.get("close", 0) or 0
            ma = ind.get(f"ma{self._params['ma_period']}", 0) or 0

            if not close or not ma or ma == 0:
                continue

            deviation = (close - ma) / ma * 100

            score = 0.0
            reasons = []

            # 价格远低于均线 = 超卖买入
            if deviation <= -self._params["deviation_threshold"]:
                score = min(1.0, abs(deviation) / 20)
                reasons.append(f"价格低于MA{self._params['ma_period']} {abs(deviation):.1f}%，超卖")
            # 价格远高于均线 = 超买卖出
            elif deviation >= self._params["deviation_threshold"]:
                score = -min(1.0, deviation / 20)
                reasons.append(f"价格高于MA{self._params['ma_period']} {deviation:.1f}%，超买")

            if score >= self._params["buy_threshold"]:
                signals.append(Signal(
                    code=code, signal_type=SignalType.BUY,
                    score=min(1.0, score), reason="; ".join(reasons),
                ))
            elif score <= self._params["sell_threshold"]:
                signals.append(Signal(
                    code=code, signal_type=SignalType.SELL,
                    score=min(1.0, abs(score)), reason="; ".join(reasons),
                ))

        return signals


class FundFlowStrategy(BaseStrategy):
    """资金流策略：基于主力资金净流入生成信号"""

    def __init__(self, params: dict | None = None):
        self._params = params or {
            "inflow_threshold": 1000000,   # 净流入阈值(元)
            "outflow_threshold": -1000000, # 净流出阈值(元)
            "buy_threshold": 0.3,
            "sell_threshold": -0.3,
        }

    @property
    def name(self) -> str:
        return "资金流策略"

    @property
    def strategy_type(self) -> str:
        return "fund_flow"

    def get_params(self) -> dict:
        return self._params.copy()

    def set_params(self, params: dict) -> None:
        self._params.update(params)

    async def generate_signals(
        self, stock_codes: list[str], context: StrategyContext
    ) -> list[Signal]:
        signals = []
        for code in stock_codes:
            market = context.market_data.get(code, {})
            if not market:
                continue

            main_net_inflow = market.get("main_net_inflow", 0) or 0

            score = 0.0
            reasons = []

            if main_net_inflow >= self._params["inflow_threshold"]:
                score = min(1.0, main_net_inflow / 10000000)
                reasons.append(f"主力净流入{main_net_inflow/10000:.0f}万")
            elif main_net_inflow <= self._params["outflow_threshold"]:
                score = -min(1.0, abs(main_net_inflow) / 10000000)
                reasons.append(f"主力净流出{abs(main_net_inflow)/10000:.0f}万")

            if score >= self._params["buy_threshold"]:
                signals.append(Signal(
                    code=code, signal_type=SignalType.BUY,
                    score=min(1.0, score), reason="; ".join(reasons),
                ))
            elif score <= self._params["sell_threshold"]:
                signals.append(Signal(
                    code=code, signal_type=SignalType.SELL,
                    score=min(1.0, abs(score)), reason="; ".join(reasons),
                ))

        return signals


class BreakoutStrategy(BaseStrategy):
    """突破策略：价格突破N日高点买入，跌破N日低点卖出"""

    def __init__(self, params: dict | None = None):
        self._params = params or {
            "lookback_days": 20,       # 回看天数
            "breakout_pct": 1.0,       # 突破幅度(%)
            "buy_threshold": 0.3,
            "sell_threshold": -0.3,
        }

    @property
    def name(self) -> str:
        return "突破策略"

    @property
    def strategy_type(self) -> str:
        return "breakout"

    def get_params(self) -> dict:
        return self._params.copy()

    def set_params(self, params: dict) -> None:
        self._params.update(params)

    async def generate_signals(
        self, stock_codes: list[str], context: StrategyContext
    ) -> list[Signal]:
        signals = []
        for code in stock_codes:
            market = context.market_data.get(code, {})
            ind = context.indicators.get(code, {})
            if not market or not ind:
                continue

            close = market.get("close", 0) or 0
            high = market.get("high", 0) or 0
            low = market.get("low", 0) or 0

            # 使用 BOLL 指标的上下轨作为支撑/阻力
            boll_upper = ind.get("boll_upper", 0) or 0
            boll_lower = ind.get("boll_lower", 0) or 0

            if not close or not boll_upper or not boll_lower:
                continue

            score = 0.0
            reasons = []

            # 突破上轨 = 强势突破
            if close > boll_upper:
                score = min(1.0, (close - boll_upper) / boll_upper * 10)
                reasons.append(f"突破布林上轨({boll_upper:.2f})")
            # 跌破下轨 = 弱势跌破
            elif close < boll_lower:
                score = -min(1.0, (boll_lower - close) / boll_lower * 10)
                reasons.append(f"跌破布林下轨({boll_lower:.2f})")

            if score >= self._params["buy_threshold"]:
                signals.append(Signal(
                    code=code, signal_type=SignalType.BUY,
                    score=min(1.0, score), reason="; ".join(reasons),
                ))
            elif score <= self._params["sell_threshold"]:
                signals.append(Signal(
                    code=code, signal_type=SignalType.SELL,
                    score=min(1.0, abs(score)), reason="; ".join(reasons),
                ))

        return signals


class GridStrategy(BaseStrategy):
    """网格策略：在设定价格区间内，每跌一格买，每涨一格卖"""

    def __init__(self, params: dict | None = None):
        self._params = params or {
            "grid_pct": 3.0,          # 网格大小(%)
            "upper_limit": 20.0,      # 上限偏离(%)
            "lower_limit": -20.0,     # 下限偏离(%)
            "buy_threshold": 0.3,
            "sell_threshold": -0.3,
        }

    @property
    def name(self) -> str:
        return "网格策略"

    @property
    def strategy_type(self) -> str:
        return "grid"

    def get_params(self) -> dict:
        return self._params.copy()

    def set_params(self, params: dict) -> None:
        self._params.update(params)

    async def generate_signals(
        self, stock_codes: list[str], context: StrategyContext
    ) -> list[Signal]:
        signals = []
        for code in stock_codes:
            market = context.market_data.get(code, {})
            ind = context.indicators.get(code, {})
            if not market or not ind:
                continue

            close = market.get("close", 0) or 0
            ma20 = ind.get("ma20", 0) or 0

            if not close or not ma20 or ma20 == 0:
                continue

            # 计算相对于均线的偏离度
            deviation = (close - ma20) / ma20 * 100
            grid_pct = self._params["grid_pct"]

            score = 0.0
            reasons = []

            # 偏离度在某个网格位置
            grid_position = deviation / grid_pct

            # 在下方网格区域 = 买入
            if deviation <= self._params["lower_limit"]:
                score = min(1.0, abs(deviation) / 30)
                reasons.append(f"网格底部区域(偏离{deviation:.1f}%)")
            elif deviation < 0 and abs(deviation) >= grid_pct:
                score = min(0.7, abs(deviation) / 30)
                reasons.append(f"网格下方区域(偏离{deviation:.1f}%)")
            # 在上方网格区域 = 卖出
            elif deviation >= self._params["upper_limit"]:
                score = -min(1.0, deviation / 30)
                reasons.append(f"网格顶部区域(偏离{deviation:.1f}%)")
            elif deviation > 0 and deviation >= grid_pct:
                score = -min(0.7, deviation / 30)
                reasons.append(f"网格上方区域(偏离{deviation:.1f}%)")

            if score >= self._params["buy_threshold"]:
                signals.append(Signal(
                    code=code, signal_type=SignalType.BUY,
                    score=min(1.0, score), reason="; ".join(reasons),
                ))
            elif score <= self._params["sell_threshold"]:
                signals.append(Signal(
                    code=code, signal_type=SignalType.SELL,
                    score=min(1.0, abs(score)), reason="; ".join(reasons),
                ))

        return signals


# ── Global engine instance with all built-in strategies registered ──

engine = StrategyEngine()
engine.register("popularity", PopularityStrategy())
engine.register("sentiment", SentimentStrategy())
engine.register("technical", TechnicalStrategy())
engine.register("multi_factor", MultiFactorStrategy())
engine.register("volume_price", VolumePriceStrategy())
engine.register("momentum", MomentumStrategy())
engine.register("mean_reversion", MeanReversionStrategy())
engine.register("fund_flow", FundFlowStrategy())
engine.register("breakout", BreakoutStrategy())
engine.register("grid", GridStrategy())
