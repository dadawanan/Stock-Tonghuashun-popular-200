from stock_service.quant.domain.backtest_rules import BacktestConfig, Position
from stock_service.quant.domain.strategy_interface import Signal, SignalType


class RiskManager:
    """Risk management for trading signals."""

    def filter_signals(
        self,
        signals: list[Signal],
        positions: dict[str, Position],
        total_assets: float,
        config: BacktestConfig,
    ) -> list[Signal]:
        filtered = []
        current_holdings = len(positions)

        for signal in signals:
            if signal.signal_type == SignalType.BUY:
                if current_holdings >= config.max_holdings:
                    continue
                if signal.code in positions:
                    continue
                filtered.append(signal)
                current_holdings += 1
            elif signal.signal_type == SignalType.SELL:
                if signal.code in positions:
                    filtered.append(signal)

        return filtered

    def calculate_buy_quantity(
        self,
        price: float,
        available_cash: float,
        total_assets: float,
        config: BacktestConfig,
    ) -> int:
        price = float(price)
        if available_cash <= 0 or price <= 0:
            return 0

        max_amount = min(
            available_cash * 0.99,
            total_assets * config.max_position_pct,
        )

        quantity = int(max_amount / price)
        quantity = (quantity // 100) * 100
        return max(quantity, 0)
