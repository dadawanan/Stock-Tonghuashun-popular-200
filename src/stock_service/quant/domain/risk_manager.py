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
        atr_value: float | None = None,
    ) -> int:
        """计算买入数量

        Args:
            atr_value: 当前股票的 ATR 值。传入后会根据波动率调整仓位：
                       高波动减仓，低波动加仓。目标是让每只股票的风险贡献相同。
        """
        price = float(price)
        if available_cash <= 0 or price <= 0:
            return 0

        position_pct = config.max_position_pct

        # 波动率调整：ATR/价格 = 波动率百分比
        # 目标波动率 = 3%（中等波动），高波动减仓，低波动加仓
        if atr_value and atr_value > 0 and price > 0:
            vol_pct = atr_value / price
            target_vol = 0.03  # 3% 目标波动率
            vol_ratio = target_vol / vol_pct
            # 限制调整范围：0.5x ~ 1.5x，避免极端仓位
            vol_ratio = max(0.5, min(1.5, vol_ratio))
            position_pct *= vol_ratio

        max_amount = min(
            available_cash * 0.99,
            total_assets * position_pct,
        )

        quantity = int(max_amount / price)
        quantity = (quantity // 100) * 100
        return max(quantity, 0)
