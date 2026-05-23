import asyncio
import logging
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.crud import quant_crud
from stock_service.infrastructure.providers.eastmoney_provider import fetch_quote
from stock_service.quant.domain.trading_calendar import is_trading_time

logger = logging.getLogger(__name__)


class SimTradingEngine:
    """Simulated trading engine with T+1 and risk management."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_account(
        self, user_id: int, account_name: str,
        initial_capital: float, strategy_id: int | None = None,
        config: dict | None = None,
    ) -> dict:
        default_config = {
            "commission_rate": 0.0003,
            "stamp_tax": 0.001,
            "slippage": 0.002,
            "max_position_pct": 0.2,
            "max_holdings": 10,
            "stop_loss_pct": -0.08,
        }
        if config:
            default_config.update(config)

        return await quant_crud.create_sim_account(self._session, {
            "user_id": user_id,
            "account_name": account_name,
            "initial_capital": Decimal(str(initial_capital)),
            "current_capital": Decimal(str(initial_capital)),
            "total_assets": Decimal(str(initial_capital)),
            "strategy_id": strategy_id,
            "config": default_config,
        })

    async def verify_ownership(self, user_id: int, account_id: int) -> bool:
        account = await quant_crud.get_sim_account(self._session, account_id)
        return account is not None and account["user_id"] == user_id

    async def buy(
        self, account_id: int, code: str, quantity: int,
        price: float | None = None, current_price: float | None = None,
    ) -> dict:
        # Check trading time
        trading, reason = is_trading_time()
        if not trading:
            raise ValueError(f"非交易时间，无法下单：{reason}")

        account = await quant_crud.get_sim_account(self._session, account_id)
        if not account:
            raise ValueError("Account not found")
        if account["status"] != "active":
            raise ValueError("Account is not active")

        # Get real-time price from market
        try:
            quote = await asyncio.to_thread(fetch_quote, code)
            exec_price = quote.get("latest_price")
            if not exec_price:
                raise ValueError(f"无法获取 {code} 的实时价格")
        except Exception as e:
            raise ValueError(f"获取实时价格失败：{e}")

        config = account.get("config") or {}
        cost = self._calculate_buy_cost(
            exec_price, quantity,
            config.get("commission_rate", 0.0003),
            config.get("slippage", 0.002),
        )

        if cost > float(account["current_capital"]):
            raise ValueError(f"Insufficient capital: need {cost}, have {account['current_capital']}")

        new_capital = float(account["current_capital"]) - cost
        await quant_crud.update_sim_account(self._session, account_id, {
            "current_capital": Decimal(str(round(new_capital, 2))),
        })

        existing = await quant_crud.get_position(self._session, account_id, code)
        if existing:
            new_qty = existing["quantity"] + quantity
            new_avg = (
                (float(existing["avg_price"]) * existing["quantity"] + exec_price * quantity)
                / new_qty
            )
            await quant_crud.update_position(self._session, account_id, code, {
                "quantity": new_qty,
                "avg_price": Decimal(str(round(new_avg, 4))),
            })
        else:
            await quant_crud.create_position(self._session, {
                "account_id": account_id,
                "code": code,
                "quantity": quantity,
                "avg_price": Decimal(str(round(exec_price, 4))),
                "available_quantity": 0,
            })

        order = await quant_crud.create_trade_order(self._session, {
            "account_id": account_id,
            "code": code,
            "side": "buy",
            "price": Decimal(str(round(exec_price, 4))),
            "quantity": quantity,
            "status": "filled",
            "commission": Decimal(str(round(cost - exec_price * quantity, 4))),
            "slippage": Decimal("0"),
        })

        await self._update_total_assets(account_id)
        return order

    async def sell(
        self, account_id: int, code: str, quantity: int,
        price: float | None = None, current_price: float | None = None,
    ) -> dict:
        # Check trading time
        trading, reason = is_trading_time()
        if not trading:
            raise ValueError(f"非交易时间，无法下单：{reason}")

        account = await quant_crud.get_sim_account(self._session, account_id)
        if not account:
            raise ValueError("Account not found")

        position = await quant_crud.get_position(self._session, account_id, code)
        if not position:
            raise ValueError(f"No position for {code}")
        if quantity > position["available_quantity"]:
            raise ValueError(
                f"Insufficient available quantity: {position['available_quantity']} (T+1)"
            )

        # Get real-time price from market
        try:
            quote = await asyncio.to_thread(fetch_quote, code)
            exec_price = quote.get("latest_price")
            if not exec_price:
                raise ValueError(f"无法获取 {code} 的实时价格")
        except Exception as e:
            raise ValueError(f"获取实时价格失败：{e}")

        config = account.get("config") or {}
        revenue = self._calculate_sell_revenue(
            exec_price, quantity,
            config.get("commission_rate", 0.0003),
            config.get("stamp_tax", 0.001),
            config.get("slippage", 0.002),
        )

        new_capital = float(account["current_capital"]) + revenue
        await quant_crud.update_sim_account(self._session, account_id, {
            "current_capital": Decimal(str(round(new_capital, 2))),
        })

        pnl = revenue - (float(position["avg_price"]) * quantity)

        new_qty = position["quantity"] - quantity
        if new_qty <= 0:
            await quant_crud.delete_position(self._session, account_id, code)
        else:
            await quant_crud.update_position(self._session, account_id, code, {
                "quantity": new_qty,
                "available_quantity": position["available_quantity"] - quantity,
            })

        order = await quant_crud.create_trade_order(self._session, {
            "account_id": account_id,
            "code": code,
            "side": "sell",
            "price": Decimal(str(round(exec_price, 4))),
            "quantity": quantity,
            "status": "filled",
            "commission": Decimal(str(round(
                exec_price * quantity * config.get("commission_rate", 0.0003), 4
            ))),
        })

        await self._update_total_assets(account_id)
        return {**order, "pnl": round(pnl, 2)}

    async def daily_settlement(self, account_id: int, trade_date: date) -> list[str]:
        positions = await quant_crud.get_positions(self._session, account_id)
        account = await quant_crud.get_sim_account(self._session, account_id)
        config = account.get("config") or {}
        stop_loss_pct = config.get("stop_loss_pct", -0.08)

        snapshots = []
        triggered_stop_loss = []

        for pos in positions:
            await quant_crud.update_position(self._session, account_id, pos["code"], {
                "available_quantity": pos["quantity"],
            })

            daily = await quant_crud.get_stock_daily(
                self._session, pos["code"],
                start_date=trade_date, end_date=trade_date,
            )
            close_price = float(daily[0]["close"]) if daily else float(pos["avg_price"])

            market_value = close_price * pos["quantity"]
            pnl = (close_price - float(pos["avg_price"])) * pos["quantity"]
            pnl_pct = (close_price - float(pos["avg_price"])) / float(pos["avg_price"]) if pos["avg_price"] else 0

            snapshots.append({
                "account_id": account_id,
                "code": pos["code"],
                "trade_date": trade_date,
                "quantity": pos["quantity"],
                "available_quantity": pos["quantity"],
                "avg_price": pos["avg_price"],
                "close_price": Decimal(str(round(close_price, 4))),
                "market_value": Decimal(str(round(market_value, 2))),
                "pnl": Decimal(str(round(pnl, 2))),
                "pnl_pct": Decimal(str(round(pnl_pct, 4))),
            })

            if pnl_pct <= stop_loss_pct:
                triggered_stop_loss.append(pos["code"])

        if snapshots:
            await quant_crud.batch_insert_position_snapshots(self._session, snapshots)

        await self._update_total_assets(account_id)

        return triggered_stop_loss

    async def _update_total_assets(self, account_id: int) -> None:
        account = await quant_crud.get_sim_account(self._session, account_id)
        positions = await quant_crud.get_positions(self._session, account_id)
        position_value = sum(
            float(p.get("avg_price", 0)) * p["quantity"] for p in positions
        )
        total = float(account["current_capital"]) + position_value
        await quant_crud.update_sim_account(self._session, account_id, {
            "total_assets": Decimal(str(round(total, 2))),
        })

    def _calculate_buy_cost(
        self, price: float, quantity: int,
        commission_rate: float, slippage: float,
    ) -> float:
        actual_price = price * (1 + slippage)
        amount = actual_price * quantity
        commission = max(amount * commission_rate, 5)
        return amount + commission

    def _calculate_sell_revenue(
        self, price: float, quantity: int,
        commission_rate: float, stamp_tax: float, slippage: float,
    ) -> float:
        actual_price = price * (1 - slippage)
        amount = actual_price * quantity
        commission = max(amount * commission_rate, 5)
        stamp = amount * stamp_tax
        return amount - commission - stamp
