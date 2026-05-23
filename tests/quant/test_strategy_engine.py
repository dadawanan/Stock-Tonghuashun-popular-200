import pytest
from datetime import date
from stock_service.quant.application.strategy_engine import (
    StrategyEngine, PopularityStrategy, SentimentStrategy,
    TechnicalStrategy, MultiFactorStrategy,
)
from stock_service.quant.domain.strategy_interface import (
    SignalType, StrategyContext,
)


@pytest.fixture
def engine():
    eng = StrategyEngine()
    eng.register("popularity", PopularityStrategy())
    eng.register("sentiment", SentimentStrategy())
    return eng


@pytest.fixture
def context():
    return StrategyContext(
        trade_date=date(2026, 5, 23),
        market_data={
            "000001.SZ": {"close": 10.0, "pct_change": 2.0},
        },
        indicators={},
        analysis={
            "000001.SZ": {
                "text_score": 3.0, "market_score": 2.5,
                "integrated_score": 2.775, "behavior_label": "做多主导",
            }
        },
        popularity={
            "000001.SZ": {"rank": 10, "is_new_entry": True, "rank_change": -5}
        },
        positions={},
    )


class TestStrategyEngine:
    def test_registered_strategies(self, engine):
        assert "popularity" in engine.list_strategies()
        assert "sentiment" in engine.list_strategies()

    def test_run_unknown_strategy_raises(self, engine):
        with pytest.raises(ValueError, match="not found"):
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                engine.run_strategy("unknown", [], StrategyContext(
                    trade_date=date.today(), market_data={}, indicators={},
                    analysis={}, popularity={}, positions={},
                ))
            )


class TestPopularityStrategy:
    def test_new_entry_generates_buy_signal(self, context):
        strategy = PopularityStrategy()
        import asyncio
        signals = asyncio.get_event_loop().run_until_complete(
            strategy.generate_signals(["000001.SZ"], context)
        )
        assert len(signals) > 0
        assert signals[0].signal_type == SignalType.BUY


class TestSentimentStrategy:
    def test_high_score_generates_buy_signal(self, context):
        strategy = SentimentStrategy()
        import asyncio
        signals = asyncio.get_event_loop().run_until_complete(
            strategy.generate_signals(["000001.SZ"], context)
        )
        assert len(signals) > 0
        assert signals[0].signal_type == SignalType.BUY


class TestTechnicalStrategy:
    def test_ma_crossover_generates_buy(self):
        strategy = TechnicalStrategy()
        context = StrategyContext(
            trade_date=date(2026, 5, 23),
            market_data={"000001.SZ": {"close": 10.0}},
            indicators={
                "000001.SZ": {
                    "ma5": 10.2, "ma20": 9.8, "rsi": 55.0,
                    "macd": 0.1, "macd_signal": 0.05, "macd_hist": 0.05,
                }
            },
            analysis={}, popularity={}, positions={},
        )
        import asyncio
        signals = asyncio.get_event_loop().run_until_complete(
            strategy.generate_signals(["000001.SZ"], context)
        )
        buy_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        assert len(buy_signals) > 0

    def test_oversold_rsi_generates_buy(self):
        strategy = TechnicalStrategy()
        context = StrategyContext(
            trade_date=date(2026, 5, 23),
            market_data={"000001.SZ": {"close": 10.0}},
            indicators={
                "000001.SZ": {
                    "ma5": 10.5, "ma20": 10.0, "rsi": 25.0,
                    "macd": 0.1, "macd_signal": 0.05, "macd_hist": 0.05,
                }
            },
            analysis={}, popularity={}, positions={},
        )
        import asyncio
        signals = asyncio.get_event_loop().run_until_complete(
            strategy.generate_signals(["000001.SZ"], context)
        )
        buy_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        assert len(buy_signals) > 0


class TestMultiFactorStrategy:
    def test_combined_signals(self):
        strategy = MultiFactorStrategy()
        context = StrategyContext(
            trade_date=date(2026, 5, 23),
            market_data={"000001.SZ": {"close": 10.0}},
            indicators={
                "000001.SZ": {
                    "ma5": 10.2, "ma20": 9.8, "rsi": 55.0,
                    "macd": 0.1, "macd_signal": 0.05,
                }
            },
            analysis={
                "000001.SZ": {"text_score": 3.0, "market_score": 2.0}
            },
            popularity={
                "000001.SZ": {"rank": 10, "is_new_entry": True, "rank_change": 0}
            },
            positions={},
        )
        import asyncio
        signals = asyncio.get_event_loop().run_until_complete(
            strategy.generate_signals(["000001.SZ"], context)
        )
        assert len(signals) > 0
