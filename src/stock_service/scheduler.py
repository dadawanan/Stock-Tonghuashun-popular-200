"""
定时任务调度器 - 自动触发人气榜数据采集和分析

触发时间：
- 每个交易日 9:25 (开盘前)
- 每个交易日 14:30 (下午盘)

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
from stock_service.db.database import AsyncSessionFactory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scheduler")


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

    except Exception as e:
        logger.error(f"流水线执行失败: {e}", exc_info=True)


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
