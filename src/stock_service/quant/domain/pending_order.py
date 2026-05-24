"""挂单管理 - 限价单"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class OrderStatus(Enum):
    PENDING = "pending"      # 等待成交
    FILLED = "filled"        # 已成交
    CANCELLED = "cancelled"  # 已取消
    EXPIRED = "expired"      # 已过期


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class PendingOrder:
    id: int
    account_id: int
    code: str
    stock_name: str | None
    side: str
    target_price: float
    quantity: int
    status: str
    created_at: datetime
    filled_at: datetime | None
    filled_price: float | None
    note: str | None


def should_fill_order(
    order: dict,
    current_price: float,
    current_time: datetime | None = None,
) -> bool:
    """判断挂单是否应该成交

    买入单：当前价 <= 目标价（低于目标价可以买入）
    卖出单：当前价 >= 目标价（高于目标价可以卖出）
    """
    side = order.get("side")
    target_price = float(order.get("target_price", 0))

    if side == "buy":
        return current_price <= target_price
    elif side == "sell":
        return current_price >= target_price

    return False
