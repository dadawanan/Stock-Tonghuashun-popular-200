"""
定时任务调度器 - 自动触发人气榜数据采集和分析

触发时间：
- 每个交易日 9:25 (开盘前)
- 每个交易日 14:30 (下午盘)

功能：
1. 采集人气榜 Top 200 数据
2. 检测新增股票并抓取新闻/行情
3. 运行分析流水线
4. 对有策略的模拟账户自动执行交易

使用方法：
    python -m stock_service.scheduler
"""

import asyncio
import logging
import signal
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from stock_service.application.services.analysis_service import run_and_store
from stock_service.application.services.market_data_service import run_fetch_pipeline_for_rows
from stock_service.application.services.popularity_service import run_popularity_pipeline
from stock_service.crud import quant_crud
from stock_service.db.database import AsyncSessionFactory
from stock_service.quant.infrastructure.analysis_adapter import AnalysisAdapter
from stock_service.quant.application.sim_trading_engine import SimTradingEngine
from stock_service.quant.application.strategy_engine import (
    BreakoutStrategy,
    FundFlowStrategy,
    GridStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    MultiFactorStrategy,
    PopularityStrategy,
    SentimentStrategy,
    StrategyEngine,
    StrategyContext,
    TechnicalStrategy,
    VolumePriceStrategy,
)
from stock_service.quant.domain.strategy_interface import Signal, SignalType

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scheduler")

# 初始化策略引擎
strategy_engine = StrategyEngine()
strategy_engine.register("popularity", PopularityStrategy())
strategy_engine.register("sentiment", SentimentStrategy())
strategy_engine.register("technical", TechnicalStrategy())
strategy_engine.register("multi_factor", MultiFactorStrategy())
strategy_engine.register("volume_price", VolumePriceStrategy())
strategy_engine.register("momentum", MomentumStrategy())
strategy_engine.register("mean_reversion", MeanReversionStrategy())
strategy_engine.register("fund_flow", FundFlowStrategy())
strategy_engine.register("breakout", BreakoutStrategy())
strategy_engine.register("grid", GridStrategy())


def is_trading_day() -> bool:
    """检查今天是否是交易日（周一到周五）"""
    return datetime.now().weekday() < 5


def is_trading_time(target_time: time) -> bool:
    """检查当前时间是否接近目标时间（±2分钟）"""
    now = datetime.now().time()
    # 允许2分钟的误差
    target_minutes = target_time.hour * 60 + target_time.minute
    now_minutes = now.hour * 60 + now.minute
    return abs(now_minutes - target_minutes) <= 2


def is_trading_time_full() -> tuple[bool, str]:
    """检查当前是否在交易时间内（完整交易时段）"""
    now = datetime.now()

    if now.weekday() >= 5:
        return False, "周末"

    current_time = now.time()

    # 上午盘：9:30 - 11:30
    if time(9, 30) <= current_time <= time(11, 30):
        return True, "上午盘"
    # 下午盘：13:00 - 15:00
    elif time(13, 0) <= current_time <= time(15, 0):
        return True, "下午盘"
    else:
        return False, "非交易时间"


async def run_pipeline() -> None:
    """执行完整的人气榜流水线"""
    logger.info("开始执行人气榜流水线...")
    try:
        async with AsyncSessionFactory() as session:
            popularity_result = await run_popularity_pipeline(session)
            new_entries = popularity_result["comparison"]["new_entries"]
            logger.info(
                f"[popularity] 获取 {popularity_result['stock_count']} 只股票，"
                f"新增 {popularity_result['new_entry_count']} 只"
            )

            if new_entries:
                await run_fetch_pipeline_for_rows(
                    session, new_entries, run_type="fetch", source="ths_new_entries"
                )
                await run_and_store(
                    session, stock_codes=[row["stock_code"] for row in new_entries]
                )

            await session.commit()
            logger.info("人气榜流水线执行完成")

            # 更新人气榜股票的日线数据
            await update_popularity_daily_data()

            # 计算技术指标
            from stock_service.application.services.market_data_service import compute_and_store_indicators
            async with AsyncSessionFactory() as session:
                indicator_count = await compute_and_store_indicators(session)
                await session.commit()
                logger.info(f"[indicators] 计算了 {indicator_count} 只股票的技术指标")

            # 自动执行模拟盘交易
            await auto_trade_for_accounts(session, new_entries)

    except Exception as e:
        logger.error(f"流水线执行失败: {e}", exc_info=True)


async def update_popularity_daily_data() -> None:
    """更新人气榜股票的日线数据和指标"""
    import asyncio
    import pandas as pd
    from sqlalchemy import text

    try:
        async with AsyncSessionFactory() as session:
            # 获取最新人气榜股票中缺少日线数据的
            result = await session.execute(text("""
                SELECT DISTINCT ps.stock_code
                FROM popularity_snapshot ps
                WHERE ps.trade_date = (SELECT MAX(trade_date) FROM popularity_snapshot)
                AND ps.stock_code NOT IN (
                    SELECT DISTINCT code FROM stock_daily
                    WHERE trade_date >= NOW() - INTERVAL '3 days'
                )
                ORDER BY ps.stock_code
                LIMIT 200
            """))
            codes = [row[0] for row in result.fetchall()]

        if not codes:
            logger.info("[daily-data] 所有人气榜股票数据已是最新")
            return

        logger.info(f"[daily-data] 需要更新 {len(codes)} 只股票的日线数据")

        end_date = date.today()
        start_date = end_date - timedelta(days=365)

        total_rows = 0
        consecutive_failures = 0
        for code in codes:
            try:
                from stock_service.infrastructure.providers.tencent_provider import fetch_kline_tx
                df = await asyncio.to_thread(
                    fetch_kline_tx, code,
                    start_date.strftime("%Y%m%d"),
                    end_date.strftime("%Y%m%d"),
                )
                if df.empty:
                    continue

                df["code"] = code
                df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
                records = df[["code", "trade_date", "open", "high", "low", "close", "volume"]].to_dict("records")
                for row in records:
                    row["amount"] = 0

                async with AsyncSessionFactory() as session:
                    await quant_crud.batch_upsert_stock_daily(session, records)
                    await session.commit()

                total_rows += len(records)
                consecutive_failures = 0
                await asyncio.sleep(0.3)
            except Exception as e:
                consecutive_failures += 1
                logger.warning(f"[daily-data] {code} 失败({consecutive_failures}): {e}")
                if consecutive_failures >= 3:
                    logger.error(f"[daily-data] 连续失败 {consecutive_failures} 次，停止执行")
                    break

        logger.info(f"[daily-data] 完成: {total_rows} 行数据")

    except Exception as e:
        logger.error(f"[daily-data] 失败: {e}", exc_info=True)


async def auto_trade_for_accounts(session, new_entries: list[dict]) -> None:
    """对有策略的模拟账户自动执行交易（支持多策略共识）"""
    try:
        # 获取所有有策略的活跃账户
        accounts = await quant_crud.list_all_active_accounts_with_strategy(session)

        if not accounts:
            logger.info("[auto-trade] 没有配置策略的模拟账户，跳过自动交易")
            return

        logger.info(f"[auto-trade] 发现 {len(accounts)} 个配置了策略的模拟账户")

        for account in accounts:
            account_id = account["id"]
            account_name = account.get("account_name", f"账户{account_id}")
            strategies = account.get("strategies", [])

            if not strategies:
                continue

            strategy_names = [s["type"] for s in strategies]
            logger.info(f"[auto-trade] 处理账户「{account_name}」(策略: {', '.join(strategy_names)})")

            try:
                # 获取最新人气榜数据
                popularity_data = await quant_crud.get_latest_popularity_data(session)

                stock_codes = [entry["stock_code"] for entry in new_entries]

                # 填充策略上下文数据（行情、指标、分析结果）
                market_data: dict[str, dict] = {}
                indicators: dict[str, dict] = {}
                trade_date = datetime.now().date()

                for code in stock_codes:
                    daily = await quant_crud.get_stock_daily(
                        session, code, start_date=trade_date, end_date=trade_date,
                    )
                    if daily:
                        market_data[code] = {
                            k: float(v) if isinstance(v, Decimal) else v
                            for k, v in daily[0].items()
                        }

                    ind = await quant_crud.get_stock_indicator(
                        session, code, trade_date=trade_date,
                    )
                    if ind:
                        indicators[code] = {
                            k: float(v) for k, v in ind.items()
                            if isinstance(v, (int, float, Decimal)) and k not in ("id",)
                        }

                adapter = AnalysisAdapter(session)
                analysis = await adapter.get_analysis_signals(stock_codes)

                # 构建策略上下文
                context = StrategyContext(
                    trade_date=trade_date,
                    market_data=market_data,
                    indicators=indicators,
                    analysis=analysis,
                    popularity=popularity_data,
                    positions={},
                )

                # 运行所有策略，收集信号
                all_signals: dict[str, dict[str, list]] = {}  # code -> {buy: [...], sell: [...]}

                for strat_info in strategies:
                    strat_type = strat_info["type"]
                    strat_params = strat_info.get("params") or {}

                    strategy = strategy_engine._strategies.get(strat_type)
                    if not strategy:
                        logger.warning(f"[auto-trade] 未找到策略: {strat_type}")
                        continue

                    strategy.set_params(strat_params)
                    signals = await strategy.generate_signals(stock_codes, context)

                    for signal in signals:
                        if signal.code not in all_signals:
                            all_signals[signal.code] = {"buy": [], "sell": []}
                        direction = signal.signal_type.value
                        all_signals[signal.code][direction].append(signal)

                # 多策略共识：只有所有策略都同意同一方向时才执行
                consensus_signals = []
                for code, directions in all_signals.items():
                    total_strategies = len(strategies)

                    # 检查买入共识
                    buy_count = len(directions["buy"])
                    if buy_count == total_strategies:
                        # 所有策略都发出买入信号
                        avg_score = sum(s.score for s in directions["buy"]) / buy_count
                        reasons = [s.reason for s in directions["buy"]]
                        consensus_signals.append(Signal(
                            code=code,
                            signal_type=SignalType.BUY,
                            score=avg_score,
                            reason=f"多策略共识买入: {'; '.join(reasons)}",
                        ))

                    # 检查卖出共识
                    sell_count = len(directions["sell"])
                    if sell_count == total_strategies:
                        avg_score = sum(s.score for s in directions["sell"]) / sell_count
                        reasons = [s.reason for s in directions["sell"]]
                        consensus_signals.append(Signal(
                            code=code,
                            signal_type=SignalType.SELL,
                            score=avg_score,
                            reason=f"多策略共识卖出: {'; '.join(reasons)}",
                        ))

                if not consensus_signals:
                    logger.info(f"[auto-trade] 账户「{account_name}」无共识信号")
                    continue

                logger.info(f"[auto-trade] 账户「{account_name}」生成 {len(consensus_signals)} 个共识信号")

                # 获取价格并准备交易数据
                from stock_service.infrastructure.providers.tencent_provider import fetch_realtime_price
                account_config = account.get("config") or {}
                max_position_pct = account_config.get("max_position_pct", 0.2)

                # 检查是否在交易时间内
                from stock_service.quant.domain.trading_calendar import is_trading_time as check_trading_time
                trading, reason = check_trading_time()
                if not trading:
                    # 非交易时间 → 创建挂单，等开盘后自动成交
                    logger.info(f"[auto-trade] 非交易时间（{reason}），创建挂单")
                    for signal in consensus_signals:
                        try:
                            current_price = await asyncio.to_thread(fetch_realtime_price, signal.code)
                            if not current_price or current_price <= 0:
                                logger.warning(f"[auto-trade] 无法获取 {signal.code} 的价格，跳过挂单")
                                continue

                            if signal.signal_type == SignalType.BUY:
                                total_assets = float(account.get("total_assets", 0))
                                max_amount = total_assets * max_position_pct * signal.score
                                quantity = int(max_amount / current_price / 100) * 100
                                if quantity < 100:
                                    logger.info(f"[auto-trade] {signal.code} 计算数量不足100股，跳过挂单")
                                    continue
                            elif signal.signal_type == SignalType.SELL:
                                position = await quant_crud.get_position(session, account_id, signal.code)
                                if not position or position.get("available_quantity", 0) <= 0:
                                    continue
                                quantity = position["available_quantity"]
                            else:
                                continue

                            await quant_crud.create_pending_order(session, {
                                "account_id": account_id,
                                "code": signal.code,
                                "side": signal.signal_type.value,
                                "target_price": Decimal(str(round(current_price, 4))),
                                "quantity": quantity,
                                "status": "pending",
                                "note": signal.reason,
                            })
                            logger.info(
                                f"[auto-trade] 挂单: {signal.signal_type.value} {signal.code} "
                                f"{quantity}股 @ {current_price:.2f} - {signal.reason}"
                            )
                        except Exception as e:
                            logger.error(f"[auto-trade] 创建挂单失败 {signal.code}: {e}")
                else:
                    # 交易时间内 → 直接执行
                    sim_engine = SimTradingEngine(session)
                    for signal in consensus_signals:
                        try:
                            if signal.signal_type == SignalType.BUY:
                                current_price = await asyncio.to_thread(fetch_realtime_price, signal.code)
                                if not current_price or current_price <= 0:
                                    logger.warning(f"[auto-trade] 无法获取 {signal.code} 的价格")
                                    continue

                                total_assets = float(account.get("total_assets", 0))
                                max_amount = total_assets * max_position_pct * signal.score
                                quantity = int(max_amount / current_price / 100) * 100
                                if quantity < 100:
                                    logger.info(f"[auto-trade] {signal.code} 计算数量不足100股，跳过")
                                    continue

                                result = await sim_engine.buy(
                                    account_id, signal.code, quantity, current_price
                                )
                                logger.info(
                                    f"[auto-trade] 买入 {signal.code} {quantity}股 "
                                    f"@ {current_price:.2f} - {signal.reason}"
                                )

                            elif signal.signal_type == SignalType.SELL:
                                position = await quant_crud.get_position(session, account_id, signal.code)
                                if position and position.get("available_quantity", 0) > 0:
                                    current_price = await asyncio.to_thread(fetch_realtime_price, signal.code)
                                    if current_price and current_price > 0:
                                        result = await sim_engine.sell(
                                            account_id, signal.code,
                                            position["available_quantity"],
                                            current_price
                                        )
                                        logger.info(
                                            f"[auto-trade] 卖出 {signal.code} "
                                            f"{position['available_quantity']}股 "
                                            f"@ {current_price:.2f} - {signal.reason}"
                                        )
                        except Exception as e:
                            logger.error(f"[auto-trade] 交易失败 {signal.code}: {e}")

                await session.commit()

            except Exception as e:
                logger.error(
                    f"[auto-trade] 账户「{account_name}」处理失败: {e}",
                    exc_info=True
                )

    except Exception as e:
        logger.error(f"[auto-trade] 自动交易执行失败: {e}", exc_info=True)


async def check_pending_orders() -> None:
    """检查挂单是否可以成交"""
    try:
        async with AsyncSessionFactory() as session:
            pending_orders = await quant_crud.list_all_pending_orders(session)

            if not pending_orders:
                return

            logger.info(f"[pending-orders] 检查 {len(pending_orders)} 个挂单")

            for order in pending_orders:
                try:
                    # 获取实时价格（新浪）
                    from stock_service.infrastructure.providers.tencent_provider import fetch_realtime_price
                    current_price = await asyncio.to_thread(fetch_realtime_price, order["code"])

                    if not current_price or current_price <= 0:
                        continue

                    # 判断是否成交
                    from stock_service.quant.domain.pending_order import should_fill_order
                    if should_fill_order(order, current_price):
                        # 执行成交
                        sim_engine = SimTradingEngine(session)

                        if order["side"] == "buy":
                            await sim_engine.buy(
                                order["account_id"],
                                order["code"],
                                order["quantity"],
                                current_price,
                            )
                        elif order["side"] == "sell":
                            await sim_engine.sell(
                                order["account_id"],
                                order["code"],
                                order["quantity"],
                                current_price,
                            )

                        # 更新挂单状态
                        await quant_crud.update_pending_order(session, order["id"], {
                            "status": "filled",
                            "filled_at": datetime.now(),
                            "filled_price": current_price,
                        })

                        logger.info(
                            f"[pending-orders] 挂单成交: {order['side']} {order['code']} "
                            f"{order['quantity']}股 @ {current_price:.2f} "
                            f"(目标价: {float(order['target_price']):.2f})"
                        )

                        await session.commit()

                except Exception as e:
                    logger.error(
                        f"[pending-orders] 处理挂单失败 #{order['id']}: {e}"
                    )

    except Exception as e:
        logger.error(f"[pending-orders] 检查挂单失败: {e}", exc_info=True)


async def run_daily_settlement() -> None:
    """对所有活跃模拟账户执行每日结算"""
    try:
        async with AsyncSessionFactory() as session:
            accounts = await quant_crud.list_all_active_sim_accounts(session)

            if not accounts:
                logger.info("[settlement] 没有活跃的模拟账户")
                return

            logger.info(f"[settlement] 开始对 {len(accounts)} 个账户执行每日结算")

            from stock_service.quant.application.sim_trading_engine import SimTradingEngine
            sim_engine = SimTradingEngine(session)

            today = datetime.now().date()
            success_count = 0

            for account in accounts:
                try:
                    triggered = await sim_engine.daily_settlement(account["id"], today)
                    success_count += 1
                    if triggered:
                        logger.info(
                            f"[settlement] 账户「{account.get('account_name', account['id'])}」"
                            f"触发止损: {triggered}"
                        )

                    # 收盘后取消当天未成交的挂单
                    cancelled = await quant_crud.cancel_all_pending_orders(
                        session, account["id"]
                    )
                    if cancelled:
                        logger.info(
                            f"[settlement] 账户「{account.get('account_name', account['id'])}」"
                            f"取消 {cancelled} 个未成交挂单"
                        )
                except Exception as e:
                    logger.error(
                        f"[settlement] 账户 #{account['id']} 结算失败: {e}"
                    )

            await session.commit()
            logger.info(f"[settlement] 每日结算完成: {success_count}/{len(accounts)} 成功")

    except Exception as e:
        logger.error(f"[settlement] 每日结算执行失败: {e}", exc_info=True)


async def scheduler_loop() -> None:
    """调度器主循环"""
    # 定义触发时间
    trigger_times = [
        time(9, 25),   # 开盘前 - 采集人气榜
        time(14, 30),  # 下午盘 - 采集人气榜
        time(15, 5),   # 收盘后 - 每日结算
    ]

    # 记录今天已触发的时间，避免重复执行
    triggered_today: set[str] = set()
    current_date = datetime.now().date()
    last_pending_check = datetime.now()

    logger.info("调度器已启动")
    logger.info(f"触发时间: {', '.join(t.strftime('%H:%M') for t in trigger_times)}")
    logger.info("仅在交易日（周一至周五）执行")
    logger.info("挂单检查: 交易时间内每60秒检查一次")

    while True:
        now = datetime.now()
        today = now.date()

        # 日期变更，重置触发记录
        if today != current_date:
            triggered_today.clear()
            current_date = today

        # 检查是否是交易日
        if is_trading_day():
            for trigger_time in trigger_times:
                time_key = trigger_time.strftime("%H:%M")

                # 检查是否到了触发时间且今天还没触发过
                if time_key not in triggered_today and is_trading_time(trigger_time):
                    triggered_today.add(time_key)

                    # 15:05 执行每日结算，其他时间执行人气榜采集
                    if trigger_time.hour == 15:
                        logger.info(f"触发时间 {time_key} 到达，执行每日结算...")
                        await run_daily_settlement()
                    else:
                        logger.info(f"触发时间 {time_key} 到达，执行人气榜采集...")
                        await run_pipeline()

            # 交易时间内每60秒检查挂单
            trading, _ = is_trading_time_full()
            if trading and (now - last_pending_check).total_seconds() >= 60:
                last_pending_check = now
                await check_pending_orders()

        # 每10秒检查一次
        await asyncio.sleep(10)


def handle_signal(signum, frame):
    """处理退出信号"""
    logger.info("收到退出信号，正在停止...")
    sys.exit(0)


def main() -> None:
    """主入口"""
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    logger.info("=" * 50)
    logger.info("人气榜定时采集调度器")
    logger.info("=" * 50)

    try:
        asyncio.run(scheduler_loop())
    except KeyboardInterrupt:
        logger.info("调度器已停止")


if __name__ == "__main__":
    main()
