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
from datetime import datetime, time

from stock_service.application.services.analysis_service import run_and_store
from stock_service.application.services.market_data_service import run_fetch_pipeline_for_rows
from stock_service.application.services.popularity_service import run_popularity_pipeline
from stock_service.crud import quant_crud
from stock_service.db.database import AsyncSessionFactory
from stock_service.quant.application.sim_trading_engine import SimTradingEngine
from stock_service.quant.application.strategy_engine import (
    MultiFactorStrategy,
    PopularityStrategy,
    SentimentStrategy,
    StrategyEngine,
    StrategyContext,
    TechnicalStrategy,
)

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

            # 自动执行模拟盘交易
            await auto_trade_for_accounts(session, new_entries)

    except Exception as e:
        logger.error(f"流水线执行失败: {e}", exc_info=True)


async def auto_trade_for_accounts(session, new_entries: list[dict]) -> None:
    """对有策略的模拟账户自动执行交易"""
    try:
        # 获取所有有策略的活跃账户
        accounts = await quant_crud.list_all_active_accounts_with_strategy(session)

        if not accounts:
            logger.info("[auto-trade] 没有配置策略的模拟账户，跳过自动交易")
            return

        logger.info(f"[auto-trade] 发现 {len(accounts)} 个配置了策略的模拟账户")

        for account in accounts:
            account_id = account["id"]
            strategy_type = account.get("strategy_type")
            strategy_params = account.get("strategy_params") or {}
            account_name = account.get("account_name", f"账户{account_id}")

            if not strategy_type:
                continue

            logger.info(f"[auto-trade] 处理账户「{account_name}」(策略: {strategy_type})")

            try:
                # 获取最新人气榜数据
                popularity_data = await quant_crud.get_latest_popularity_data(session)

                # 构建策略上下文
                context = StrategyContext(
                    trade_date=datetime.now().date(),
                    market_data={},
                    indicators={},
                    analysis={},
                    popularity=popularity_data,
                    positions={},
                )

                # 运行策略生成信号
                strategy = strategy_engine._strategies.get(strategy_type)
                if not strategy:
                    logger.warning(f"[auto-trade] 未找到策略: {strategy_type}")
                    continue

                strategy.set_params(strategy_params)
                stock_codes = [entry["stock_code"] for entry in new_entries]
                signals = await strategy.generate_signals(stock_codes, context)

                if not signals:
                    logger.info(f"[auto-trade] 账户「{account_name}」无交易信号")
                    continue

                logger.info(f"[auto-trade] 账户「{account_name}」生成 {len(signals)} 个信号")

                # 执行交易
                sim_engine = SimTradingEngine(session)
                for signal in signals:
                    try:
                        if signal.signal_type.value == "buy":
                            result = await sim_engine.buy(
                                account_id, signal.code, 100  # 默认买入100股
                            )
                            logger.info(
                                f"[auto-trade] 买入 {signal.code} 100股 - {signal.reason}"
                            )
                        elif signal.signal_type.value == "sell":
                            # 检查是否有持仓
                            position = await quant_crud.get_position(
                                session, account_id, signal.code
                            )
                            if position and position["available_quantity"] > 0:
                                result = await sim_engine.sell(
                                    account_id, signal.code,
                                    position["available_quantity"]
                                )
                                logger.info(
                                    f"[auto-trade] 卖出 {signal.code} "
                                    f"{position['available_quantity']}股 - {signal.reason}"
                                )
                    except Exception as e:
                        logger.error(
                            f"[auto-trade] 交易失败 {signal.code}: {e}"
                        )

                await session.commit()

            except Exception as e:
                logger.error(
                    f"[auto-trade] 账户「{account_name}」处理失败: {e}",
                    exc_info=True
                )

    except Exception as e:
        logger.error(f"[auto-trade] 自动交易执行失败: {e}", exc_info=True)


async def scheduler_loop() -> None:
    """调度器主循环"""
    # 定义触发时间
    trigger_times = [
        time(9, 25),   # 开盘前
        time(14, 30),  # 下午盘
    ]

    # 记录今天已触发的时间，避免重复执行
    triggered_today: set[str] = set()
    current_date = datetime.now().date()

    logger.info("调度器已启动")
    logger.info(f"触发时间: {', '.join(t.strftime('%H:%M') for t in trigger_times)}")
    logger.info("仅在交易日（周一至周五）执行")

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
                    logger.info(f"触发时间 {time_key} 到达，开始执行...")
                    triggered_today.add(time_key)
                    await run_pipeline()

        # 每30秒检查一次
        await asyncio.sleep(30)


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
