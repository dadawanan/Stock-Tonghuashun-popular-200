from __future__ import annotations

import argparse
import asyncio

from data_fetcher import run_fetch_pipeline_for_rows, run_popularity_pipeline
from database import StockDatabase
from stock_analyzer import run_and_store


async def main_async(fetch_only: bool = False) -> None:
    popularity_result = await run_popularity_pipeline()
    new_entries = popularity_result["comparison"]["new_entries"]

    print(
        f"[popularity] 获取 {popularity_result['stock_count']} 只股票，"
        f"新增 {popularity_result['new_entry_count']} 只"
    )

    if not new_entries:
        print("[run-all] 本次榜单没有新增股票")
        return

    await run_fetch_pipeline_for_rows(new_entries, run_type="fetch", source="ths_new_entries")
    if fetch_only:
        return

    db = StockDatabase()
    await db.initialize()
    try:
        await run_and_store(db, stock_codes=[row["stock_code"] for row in new_entries])
    finally:
        await db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch THS top200, detect new entries, then analyze them.")
    parser.add_argument("--fetch-only", action="store_true", help="Only fetch popularity/news/market data.")
    args = parser.parse_args()
    asyncio.run(main_async(fetch_only=args.fetch_only))


if __name__ == "__main__":
    main()
