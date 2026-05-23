import pytest
from datetime import date
from stock_service.quant.application.backtest_engine import BacktestEngine


class TestBacktestMetrics:
    def test_calculate_metrics_basic(self):
        engine = BacktestEngine.__new__(BacktestEngine)
        nav_series = [
            {"trade_date": date(2026, 1, 1), "total_assets": 1000000},
            {"trade_date": date(2026, 1, 2), "total_assets": 1010000},
            {"trade_date": date(2026, 1, 3), "total_assets": 1005000},
            {"trade_date": date(2026, 1, 4), "total_assets": 1020000},
        ]
        trades = [
            {"pnl": 10000, "side": "sell"},
            {"pnl": -5000, "side": "sell"},
        ]
        metrics = engine._calculate_metrics(
            nav_series=nav_series,
            trades=trades,
            initial_capital=1000000,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 4),
        )
        assert metrics["total_return"] == 0.02
        assert metrics["win_rate"] == 0.5
        assert metrics["total_trades"] == 2
