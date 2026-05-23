from dataclasses import dataclass


@dataclass
class BacktestConfig:
    initial_capital: float = 1_000_000.0
    commission_rate: float = 0.0003
    stamp_tax: float = 0.001
    slippage: float = 0.002
    max_position_pct: float = 0.2
    max_holdings: int = 10
    stop_loss_pct: float = -0.08
    t_plus_1: bool = True


@dataclass
class Position:
    code: str
    quantity: int
    avg_price: float
    available_quantity: int
    market_value: float
    pnl: float
    pnl_pct: float


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
    ) -> bool:
        pnl_pct = (current_price - position.avg_price) / position.avg_price
        return pnl_pct <= config.stop_loss_pct

    def update_available_quantity(self, positions: dict[str, Position]) -> None:
        for pos in positions.values():
            pos.available_quantity = pos.quantity
