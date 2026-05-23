import pytest
from stock_service.quant.domain.risk_manager import RiskManager
from stock_service.quant.domain.backtest_rules import BacktestConfig, Position


@pytest.fixture
def manager():
    return RiskManager()


@pytest.fixture
def config():
    return BacktestConfig(max_holdings=5, max_position_pct=0.3, stop_loss_pct=-0.08)


class TestFilterSignals:
    def test_reject_buy_when_max_holdings(self, manager, config):
        positions = {f"00000{i}.SZ": Position(f"00000{i}.SZ", 100, 10.0, 100, 1000, 0, 0) for i in range(5)}
        from stock_service.quant.domain.strategy_interface import Signal, SignalType
        signals = [Signal("000006.SZ", SignalType.BUY, 0.8, "test")]
        filtered = manager.filter_signals(signals, positions, total_assets=100000, config=config)
        assert len(filtered) == 0

    def test_allow_buy_when_below_limit(self, manager, config):
        positions = {f"00000{i}.SZ": Position(f"00000{i}.SZ", 100, 10.0, 100, 1000, 0, 0) for i in range(3)}
        from stock_service.quant.domain.strategy_interface import Signal, SignalType
        signals = [Signal("000006.SZ", SignalType.BUY, 0.8, "test")]
        filtered = manager.filter_signals(signals, positions, total_assets=100000, config=config)
        assert len(filtered) == 1

    def test_always_allow_sell_signals(self, manager, config):
        positions = {"000001.SZ": Position("000001.SZ", 100, 10.0, 100, 1000, 0, 0)}
        from stock_service.quant.domain.strategy_interface import Signal, SignalType
        signals = [Signal("000001.SZ", SignalType.SELL, 0.9, "test")]
        filtered = manager.filter_signals(signals, positions, total_assets=100000, config=config)
        assert len(filtered) == 1


class TestCalculateQuantity:
    def test_buy_quantity_rounded_to_100(self, manager, config):
        qty = manager.calculate_buy_quantity(
            price=10.0, available_cash=50000, total_assets=100000, config=config
        )
        assert qty % 100 == 0
        assert qty > 0

    def test_buy_quantity_respects_position_limit(self, manager, config):
        qty = manager.calculate_buy_quantity(
            price=10.0, available_cash=100000, total_assets=100000, config=config
        )
        assert qty <= 3000

    def test_buy_quantity_zero_when_no_cash(self, manager, config):
        qty = manager.calculate_buy_quantity(
            price=10.0, available_cash=0, total_assets=100000, config=config
        )
        assert qty == 0
