import logging
import statistics
from collections.abc import Callable
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.crud import quant_crud
from stock_service.quant.application.strategy_engine import StrategyEngine
from stock_service.quant.domain.backtest_rules import (
    BacktestConfig, BacktestRules, Position,
)
from stock_service.quant.domain.risk_manager import RiskManager
from stock_service.quant.domain.strategy_interface import (
    SignalType, StrategyContext,
)
from stock_service.quant.infrastructure.analysis_adapter import AnalysisAdapter

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Backtesting engine - runs strategies against historical data."""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._rules = BacktestRules()
        self._risk = RiskManager()

    async def run(
        self,
        strategy_id: int,
        stock_codes: list[str],
        start_date: date,
        end_date: date,
        config: BacktestConfig,
        strategy_engine: StrategyEngine,
        progress_cb: Callable[[int, int, str], None] | None = None,
    ) -> dict:
        """Run backtest and return results.

        Args:
            progress_cb: Optional callback ``(current, total, message)`` invoked
                after each trading date to report progress.
        """
        strategy = await quant_crud.get_strategy(self._session, strategy_id)
        if not strategy:
            raise ValueError(f"Strategy {strategy_id} not found")

        strategy_name = strategy["type"]
        strategy_engine._strategies[strategy_name].set_params(strategy.get("params") or {})

        analysis_adapter = AnalysisAdapter(self._session)

        cash = config.initial_capital
        positions: dict[str, Position] = {}
        nav_series: list[dict] = []
        trades: list[dict] = []
        peak_assets = config.initial_capital  # 用于账户级回撤计算

        trading_dates = await self._get_trading_dates(
            stock_codes[0] if stock_codes else None, start_date, end_date
        )

        # Fetch benchmark data for comparison
        benchmark_data = await quant_crud.get_benchmark_daily(
            self._session, start_date, end_date
        )
        benchmark_prices = {
            r["trade_date"]: float(r["close"]) for r in benchmark_data
        }
        benchmark_start_price = next(iter(benchmark_prices.values()), None) if benchmark_prices else None

        drawdown_warn_count = 0
        drawdown_first_date = None

        for trade_date in trading_dates:
            self._rules.update_available_quantity(positions)

            context = await self._build_context(
                stock_codes, trade_date, positions, analysis_adapter
            )

            signals = await strategy_engine.run_strategy(
                strategy_name, stock_codes, context
            )

            filtered = self._risk.filter_signals(
                signals, positions, cash + sum(
                    p.market_value for p in positions.values()
                ), config
            )

            for signal in filtered:
                market_data = context.market_data.get(signal.code, {})
                price = market_data.get("close", 0)
                if price <= 0:
                    continue

                if signal.signal_type == SignalType.BUY:
                    total_assets = cash + sum(p.market_value for p in positions.values())
                    atr_value = context.indicators.get(signal.code, {}).get("atr")
                    qty = self._risk.calculate_buy_quantity(
                        price, cash, total_assets, config, atr_value=atr_value
                    )
                    if qty <= 0:
                        continue

                    cost = self._rules.calculate_buy_cost(price, qty, config)
                    if cost > cash:
                        continue

                    cash -= cost
                    positions[signal.code] = Position(
                        code=signal.code, quantity=qty, avg_price=price,
                        available_quantity=0,
                        market_value=price * qty,
                        pnl=0, pnl_pct=0,
                        highest_price=price, lowest_price=price,
                    )
                    trades.append({
                        "code": signal.code, "side": "buy",
                        "price": price, "quantity": qty,
                        "trade_date": trade_date,
                        "pnl": 0, "signal_source": strategy_name,
                    })

                elif signal.signal_type == SignalType.SELL:
                    pos = positions.get(signal.code)
                    if not pos or pos.available_quantity <= 0:
                        continue

                    revenue = self._rules.calculate_sell_revenue(
                        price, pos.quantity, config
                    )
                    pnl = revenue - (pos.avg_price * pos.quantity)
                    cash += revenue
                    del positions[signal.code]
                    trades.append({
                        "code": signal.code, "side": "sell",
                        "price": price, "quantity": pos.quantity,
                        "trade_date": trade_date,
                        "pnl": round(pnl, 2), "signal_source": strategy_name,
                    })

            # 更新持仓市值、最高/最低价、检查止盈止损
            codes_to_sell = []
            for code, pos in positions.items():
                price = context.market_data.get(code, {}).get("close", pos.avg_price)
                pos.market_value = price * pos.quantity
                pos.pnl = (price - pos.avg_price) * pos.quantity
                pos.pnl_pct = (price - pos.avg_price) / pos.avg_price if pos.avg_price else 0

                # 更新最高/最低价
                if price > pos.highest_price:
                    pos.highest_price = price
                if price < pos.lowest_price or pos.lowest_price == 0:
                    pos.lowest_price = price

                # 检查止损（传入 ATR 值）
                atr_value = context.indicators.get(code, {}).get("atr")
                stop_triggered, stop_reason = self._rules.check_stop_loss(pos, price, config, atr_value=atr_value)
                if stop_triggered and pos.available_quantity > 0:
                    codes_to_sell.append((code, stop_reason))

                # 检查止盈
                tp_triggered, tp_reason = self._rules.check_take_profit(pos, price, config)
                if tp_triggered and pos.available_quantity > 0:
                    codes_to_sell.append((code, tp_reason))

            # 执行止盈止损卖出
            for code, reason in codes_to_sell:
                if code not in positions:
                    continue
                pos = positions[code]
                price = context.market_data.get(code, {}).get("close", pos.avg_price)
                revenue = self._rules.calculate_sell_revenue(price, pos.quantity, config)
                pnl = revenue - (pos.avg_price * pos.quantity)
                cash += revenue
                del positions[code]
                trades.append({
                    "code": code, "side": "sell",
                    "price": price, "quantity": pos.quantity,
                    "trade_date": trade_date,
                    "pnl": round(pnl, 2), "signal_source": f"auto:{reason}",
                })

            # 检查账户级回撤
            total_assets = cash + sum(p.market_value for p in positions.values())
            if total_assets > peak_assets:
                peak_assets = total_assets
            drawdown_ok, _ = self._rules.check_account_drawdown(
                total_assets, peak_assets, config
            )
            if not drawdown_ok:
                drawdown_warn_count += 1
                if drawdown_warn_count == 1:
                    drawdown_pct = (total_assets - peak_assets) / peak_assets if peak_assets > 0 else 0
                    logger.warning(
                        f"账户回撤限制触发: 日期={trade_date}, "
                        f"总资产={total_assets:,.0f}, 峰值={peak_assets:,.0f}, "
                        f"回撤={drawdown_pct:.1%}, 限制={config.max_drawdown_pct:.0%}"
                    )
                    drawdown_first_date = trade_date

            position_value = sum(p.market_value for p in positions.values())
            total_assets = cash + position_value

            # Calculate benchmark NAV
            benchmark_nav = None
            if benchmark_start_price and benchmark_start_price > 0:
                bench_price = benchmark_prices.get(trade_date)
                if bench_price:
                    benchmark_nav = bench_price / benchmark_start_price

            nav_series.append({
                "trade_date": trade_date,
                "nav": total_assets / config.initial_capital,
                "total_assets": total_assets,
                "cash": cash,
                "position_value": position_value,
                "benchmark_nav": benchmark_nav,
            })

            if progress_cb:
                progress_cb(
                    len(nav_series), len(trading_dates),
                    f"Processing {trade_date}",
                )

        if drawdown_warn_count > 1:
            logger.warning(
                f"账户回撤限制共触发 {drawdown_warn_count} 个交易日 "
                f"(首次: {drawdown_first_date}, 末次: {trade_date})"
            )

        metrics = self._calculate_metrics(
            nav_series, trades, config.initial_capital, start_date, end_date
        )

        backtest_result = await quant_crud.create_backtest_result(self._session, {
            "strategy_id": strategy_id,
            "start_date": start_date,
            "end_date": end_date,
            "total_return": metrics.get("total_return"),
            "annual_return": metrics.get("annual_return"),
            "max_drawdown": metrics.get("max_drawdown"),
            "max_drawdown_days": metrics.get("max_drawdown_days"),
            "sharpe": metrics.get("sharpe_ratio"),
            "sortino": metrics.get("sortino_ratio"),
            "calmar": metrics.get("calmar_ratio"),
            "alpha": metrics.get("alpha"),
            "beta": metrics.get("beta"),
            "information_ratio": metrics.get("information_ratio"),
            "win_rate": metrics.get("win_rate"),
            "total_trades": metrics.get("total_trades"),
        })

        for trade in trades:
            trade["backtest_id"] = backtest_result["id"]
        await quant_crud.batch_insert_backtest_trades(self._session, trades)

        for nav in nav_series:
            nav["backtest_id"] = backtest_result["id"]
        await quant_crud.batch_insert_backtest_nav(self._session, nav_series)

        return {
            "backtest_id": backtest_result["id"],
            "metrics": metrics,
            "trade_count": len(trades),
            "nav_count": len(nav_series),
        }

    async def _get_trading_dates(
        self, code: str | None, start_date: date, end_date: date
    ) -> list[date]:
        if not code:
            return []
        rows = await quant_crud.get_stock_daily(
            self._session, code, start_date=start_date, end_date=end_date
        )
        return sorted(set(r["trade_date"] for r in rows))

    async def _build_context(
        self, stock_codes: list[str], trade_date: date,
        positions: dict[str, Position], analysis_adapter: AnalysisAdapter,
    ) -> StrategyContext:
        market_data: dict[str, dict] = {}
        indicators: dict[str, dict] = {}
        for code in stock_codes:
            daily = await quant_crud.get_stock_daily(
                self._session, code, start_date=trade_date, end_date=trade_date
            )
            if daily:
                market_data[code] = {
                    k: float(v) if isinstance(v, Decimal) else v
                    for k, v in daily[0].items()
                }

            ind = await quant_crud.get_stock_indicator(
                self._session, code, trade_date=trade_date
            )
            if ind:
                indicators[code] = {
                    k: float(v) for k, v in ind.items()
                    if isinstance(v, (int, float, Decimal)) and k not in ("id",)
                }

        analysis = await analysis_adapter.get_analysis_signals(stock_codes)
        popularity = await analysis_adapter.get_popularity_data(stock_codes, trade_date)

        from stock_service.quant.domain.market_regime import detect_market_regime
        market_regime = await detect_market_regime(self._session)

        return StrategyContext(
            trade_date=trade_date,
            market_data=market_data,
            indicators=indicators,
            analysis=analysis,
            popularity=popularity,
            positions={c: {"quantity": p.quantity, "avg_price": p.avg_price} for c, p in positions.items()},
            market_regime=market_regime,
        )

    def _calculate_metrics(
        self, nav_series: list[dict], trades: list[dict],
        initial_capital: float, start_date: date, end_date: date,
    ) -> dict:
        if not nav_series:
            return {}

        final_assets = nav_series[-1]["total_assets"]
        total_return = (final_assets - initial_capital) / initial_capital

        # ── 最大回撤 + 回撤持续时间 ──
        peak = initial_capital
        max_dd = 0
        dd_start = None
        max_dd_days = 0
        current_dd_days = 0
        for nav in nav_series:
            ta = nav["total_assets"]
            if ta > peak:
                peak = ta
                if current_dd_days > max_dd_days:
                    max_dd_days = current_dd_days
                current_dd_days = 0
            else:
                current_dd_days += 1
            dd = (peak - ta) / peak
            if dd > max_dd:
                max_dd = dd
        if current_dd_days > max_dd_days:
            max_dd_days = current_dd_days

        # ── 胜率 ──
        sell_trades = [t for t in trades if t["side"] == "sell"]
        wins = len([t for t in sell_trades if t.get("pnl", 0) > 0])
        win_rate = wins / len(sell_trades) if sell_trades else 0

        days = (end_date - start_date).days
        annual_return = ((1 + total_return) ** (365 / max(days, 1))) - 1 if days > 0 else 0

        # ── 日收益率序列 ──
        returns = []
        benchmark_returns = []
        if len(nav_series) > 1:
            for i in range(1, len(nav_series)):
                prev = nav_series[i - 1]["total_assets"]
                curr = nav_series[i]["total_assets"]
                returns.append((curr - prev) / prev if prev else 0)
                # 基准收益率
                b_prev = nav_series[i - 1].get("benchmark_nav")
                b_curr = nav_series[i].get("benchmark_nav")
                if b_prev and b_curr and b_prev > 0:
                    benchmark_returns.append((b_curr - b_prev) / b_prev)
                else:
                    benchmark_returns.append(0)

        # ── Sharpe 比率 ──
        if returns:
            mean_ret = statistics.mean(returns)
            std_ret = statistics.stdev(returns) if len(returns) > 1 else 1
            sharpe = (mean_ret * 252 - 0.03) / (std_ret * (252 ** 0.5)) if std_ret > 0 else 0
        else:
            sharpe = 0

        # ── Sortino 比率（只惩罚下行波动）──
        if returns:
            downside = [r for r in returns if r < 0]
            downside_std = statistics.stdev(downside) if len(downside) > 1 else (statistics.mean(downside) if downside else 0)
            downside_std_annual = abs(downside_std) * (252 ** 0.5)
            sortino = (annual_return - 0.03) / downside_std_annual if downside_std_annual > 0 else 0
        else:
            sortino = 0

        # ── Calmar 比率（收益/最大回撤）──
        calmar = annual_return / max_dd if max_dd > 0 else 0

        # ── Alpha / Beta（相对基准）──
        alpha = 0.0
        beta = 0.0
        if returns and benchmark_returns and len(returns) == len(benchmark_returns):
            mean_port = statistics.mean(returns)
            mean_bench = statistics.mean(benchmark_returns)
            # Beta = Cov(port, bench) / Var(bench)
            bench_var = statistics.variance(benchmark_returns) if len(benchmark_returns) > 1 else 0
            if bench_var > 0:
                covariance = sum((r - mean_port) * (b - mean_bench) for r, b in zip(returns, benchmark_returns)) / len(returns)
                beta = covariance / bench_var
                # Alpha = 年化超额收益
                alpha = annual_return - (0.03 + beta * (mean_bench * 252 - 0.03))

        # ── 信息比率（超额收益/跟踪误差）──
        info_ratio = 0.0
        if returns and benchmark_returns and len(returns) == len(benchmark_returns):
            excess = [r - b for r, b in zip(returns, benchmark_returns)]
            tracking_error = statistics.stdev(excess) * (252 ** 0.5) if len(excess) > 1 else 0
            if tracking_error > 0:
                info_ratio = (annual_return - statistics.mean(benchmark_returns) * 252) / tracking_error

        # ── 月度收益分解 ──
        monthly_returns: dict[str, float] = {}
        if nav_series:
            month_start_assets: dict[str, float] = {}
            for nav in nav_series:
                month_key = nav["trade_date"].strftime("%Y-%m") if hasattr(nav["trade_date"], "strftime") else str(nav["trade_date"])[:7]  # "2026-05"
                if month_key not in month_start_assets:
                    month_start_assets[month_key] = nav["total_assets"]
            month_keys = sorted(month_start_assets.keys())
            for i, mk in enumerate(month_keys):
                start_a = month_start_assets[mk]
                # 找这个月最后一天的 assets
                end_a = start_a
                for nav in nav_series:
                    nav_month = nav["trade_date"].strftime("%Y-%m") if hasattr(nav["trade_date"], "strftime") else str(nav["trade_date"])[:7]
                    if nav_month == mk:
                        end_a = nav["total_assets"]
                monthly_returns[mk] = round((end_a - start_a) / start_a, 4) if start_a > 0 else 0

        return {
            "total_return": round(total_return, 4),
            "annual_return": round(annual_return, 4),
            "max_drawdown": round(max_dd, 4),
            "max_drawdown_days": max_dd_days,
            "sharpe_ratio": round(sharpe, 4),
            "sortino_ratio": round(sortino, 4),
            "calmar_ratio": round(calmar, 4),
            "alpha": round(alpha, 4),
            "beta": round(beta, 4),
            "information_ratio": round(info_ratio, 4),
            "win_rate": round(win_rate, 4),
            "total_trades": len(trades),
            "monthly_returns": monthly_returns,
        }
