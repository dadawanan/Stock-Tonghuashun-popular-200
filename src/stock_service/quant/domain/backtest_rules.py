from dataclasses import dataclass, field


@dataclass
class BacktestConfig:
    initial_capital: float = 1_000_000.0
    commission_rate: float = 0.0003
    stamp_tax: float = 0.001
    slippage: float = 0.002
    max_position_pct: float = 0.2
    max_holdings: int = 10
    t_plus_1: bool = True

    # 止损配置
    stop_loss_pct: float = -0.08          # 固定止损 -8%
    trailing_stop_pct: float = 0.0        # 移动止损 (0=禁用)
    atr_stop_multiplier: float = 0.0      # ATR 止损倍数 (0=禁用)

    # 止盈配置
    take_profit_pct: float = 0.0          # 固定止盈 (0=禁用)
    trailing_take_profit_pct: float = 0.0 # 移动止盈 (0=禁用)

    # 账户级风控
    max_drawdown_pct: float = -0.20       # 最大回撤 -20% 暂停交易


@dataclass
class Position:
    code: str
    quantity: int
    avg_price: float
    available_quantity: int
    market_value: float
    pnl: float
    pnl_pct: float
    highest_price: float = 0.0    # 持仓期间最高价（用于移动止损）
    lowest_price: float = 0.0     # 持仓期间最低价（用于移动止盈）


class BacktestRules:
    """Backtest trading rules engine."""

    def calculate_buy_cost(
        self, price: float, quantity: int, config: BacktestConfig
    ) -> float:
        price = float(price)
        actual_price = price * (1 + config.slippage)
        amount = actual_price * quantity
        commission = max(amount * config.commission_rate, 5)
        return amount + commission

    def calculate_sell_revenue(
        self, price: float, quantity: int, config: BacktestConfig
    ) -> float:
        price = float(price)
        actual_price = price * (1 - config.slippage)
        amount = actual_price * quantity
        commission = max(amount * config.commission_rate, 5)
        stamp = amount * config.stamp_tax
        return amount - commission - stamp

    def check_position_limit(
        self,
        current_holdings: int,
        total_value: float,
        buy_amount: float,
        config: BacktestConfig,
    ) -> tuple[bool, str]:
        if current_holdings >= config.max_holdings:
            return False, "持仓数量已达上限"
        if total_value > 0 and buy_amount / total_value > config.max_position_pct:
            return False, "单只股票仓位超过限制"
        return True, ""

    def check_stop_loss(
        self, position: Position, current_price: float, config: BacktestConfig
    ) -> tuple[bool, str]:
        """检查止损条件

        Returns:
            (是否触发止损, 触发原因)
        """
        pnl_pct = (current_price - position.avg_price) / position.avg_price

        # 1. 固定止损
        if config.stop_loss_pct < 0 and pnl_pct <= config.stop_loss_pct:
            return True, f"固定止损({config.stop_loss_pct:.0%})"

        # 2. 移动止损（从最高点回撤）
        if config.trailing_stop_pct > 0 and position.highest_price > 0:
            drop_from_high = (current_price - position.highest_price) / position.highest_price
            if drop_from_high <= -config.trailing_stop_pct:
                return True, f"移动止损(从最高{position.highest_price:.2f}回撤{config.trailing_stop_pct:.0%})"

        return False, ""

    def check_take_profit(
        self, position: Position, current_price: float, config: BacktestConfig
    ) -> tuple[bool, str]:
        """检查止盈条件

        Returns:
            (是否触发止盈, 触发原因)
        """
        pnl_pct = (current_price - position.avg_price) / position.avg_price

        # 1. 固定止盈
        if config.take_profit_pct > 0 and pnl_pct >= config.take_profit_pct:
            return True, f"固定止盈({config.take_profit_pct:.0%})"

        # 2. 移动止盈（从最低点反弹）
        if config.trailing_take_profit_pct > 0 and position.lowest_price > 0:
            rise_from_low = (current_price - position.lowest_price) / position.lowest_price
            if rise_from_low >= config.trailing_take_profit_pct:
                return True, f"移动止盈(从最低{position.lowest_price:.2f}反弹{config.trailing_take_profit_pct:.0%})"

        return False, ""

    def check_account_drawdown(
        self, total_assets: float, peak_assets: float, config: BacktestConfig
    ) -> tuple[bool, str]:
        """检查账户级最大回撤

        Returns:
            (是否触发回撤限制, 原因)
        """
        if peak_assets <= 0:
            return False, ""
        drawdown = (total_assets - peak_assets) / peak_assets
        if drawdown <= config.max_drawdown_pct:
            return True, f"账户回撤{drawdown:.1%}超过限制{config.max_drawdown_pct:.0%}"
        return False, ""

    def update_available_quantity(self, positions: dict[str, Position]) -> None:
        for pos in positions.values():
            pos.available_quantity = pos.quantity
