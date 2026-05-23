import pytest
from stock_service.quant.domain.backtest_rules import BacktestConfig, BacktestRules


@pytest.fixture
def config():
    return BacktestConfig()


@pytest.fixture
def rules():
    return BacktestRules()


class TestBuyCost:
    def test_buy_cost_includes_commission_and_slippage(self, rules, config):
        cost = rules.calculate_buy_cost(price=10.0, quantity=1000, config=config)
        actual_price = 10.0 * (1 + 0.002)
        amount = actual_price * 1000
        commission = max(amount * 0.0003, 5)
        expected = amount + commission
        assert abs(cost - expected) < 0.01

    def test_buy_cost_minimum_commission(self, rules, config):
        cost = rules.calculate_buy_cost(price=1.0, quantity=100, config=config)
        assert cost > 100


class TestSellRevenue:
    def test_sell_revenue_deducts_fees(self, rules, config):
        revenue = rules.calculate_sell_revenue(price=10.0, quantity=1000, config=config)
        actual_price = 10.0 * (1 - 0.002)
        amount = actual_price * 1000
        commission = max(amount * 0.0003, 5)
        stamp = amount * 0.001
        expected = amount - commission - stamp
        assert abs(revenue - expected) < 0.01


class TestPositionLimit:
    def test_reject_when_max_holdings_reached(self, rules, config):
        ok, msg = rules.check_position_limit(
            current_holdings=10, total_value=1000000,
            buy_amount=100000, config=config
        )
        assert not ok
        assert "持仓数量" in msg

    def test_reject_when_position_too_large(self, rules, config):
        ok, msg = rules.check_position_limit(
            current_holdings=5, total_value=1000000,
            buy_amount=300000, config=config
        )
        assert not ok
        assert "仓位" in msg

    def test_accept_normal_trade(self, rules, config):
        ok, msg = rules.check_position_limit(
            current_holdings=5, total_value=1000000,
            buy_amount=100000, config=config
        )
        assert ok


class TestStopLoss:
    def test_trigger_stop_loss(self, rules, config):
        from stock_service.quant.domain.backtest_rules import Position
        pos = Position(
            code="000001.SZ", quantity=1000, avg_price=10.0,
            available_quantity=1000, market_value=9000, pnl=-1000, pnl_pct=-0.10
        )
        assert rules.check_stop_loss(pos, current_price=9.0, config=config)

    def test_no_stop_loss_within_threshold(self, rules, config):
        from stock_service.quant.domain.backtest_rules import Position
        pos = Position(
            code="000001.SZ", quantity=1000, avg_price=10.0,
            available_quantity=1000, market_value=9500, pnl=-500, pnl_pct=-0.05
        )
        assert not rules.check_stop_loss(pos, current_price=9.5, config=config)
