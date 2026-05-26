#!/usr/bin/env python3
"""手动触发定时任务的测试脚本"""
import asyncio
import logging
import sys

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("test-scheduler")


async def main():
    """手动执行定时任务"""
    from stock_service.scheduler import run_pipeline, run_daily_settlement

    logger.info("=" * 50)
    logger.info("手动触发定时任务测试")
    logger.info("=" * 50)

    # 执行人气榜流水线（9:25 和 14:30 的任务）
    logger.info("执行人气榜流水线...")
    await run_pipeline()

    # 如果需要测试每日结算（15:05 的任务），取消下面的注释
    # logger.info("执行每日结算...")
    # await run_daily_settlement()

    logger.info("=" * 50)
    logger.info("测试完成！")
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
