import pytest
from stock_service.quant.application.sim_trading_engine import SimTradingEngine


class TestCalculateBuyCost:
    def test_basic_buy_cost(self):
        engine = SimTradingEngine.__new__(SimTradingEngine)
        cost = engine._calculate_buy_cost(10.0, 1000, 0.0003, 0.002)
        expected_price = 10.0 * 1.002
        expected_amount = expected_price * 1000
        expected_commission = max(expected_amount * 0.0003, 5)
        assert abs(cost - (expected_amount + expected_commission)) < 0.01


class TestCalculateSellRevenue:
    def test_basic_sell_revenue(self):
        engine = SimTradingEngine.__new__(SimTradingEngine)
        revenue = engine._calculate_sell_revenue(10.0, 1000, 0.0003, 0.001, 0.002)
        expected_price = 10.0 * 0.998
        expected_amount = expected_price * 1000
        expected_commission = max(expected_amount * 0.0003, 5)
        expected_stamp = expected_amount * 0.001
        assert abs(revenue - (expected_amount - expected_commission - expected_stamp)) < 0.01
