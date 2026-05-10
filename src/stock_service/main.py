from __future__ import annotations

import argparse
import asyncio

from stock_service.application.services.analysis_service import run_and_store
from stock_service.application.services.market_data_service import run_fetch_pipeline_for_rows
from stock_service.application.services.popularity_service import run_popularity_pipeline
from stock_service.db.database import AsyncSessionFactory


async def main_async(fetch_only: bool = False) -> None:
    async with AsyncSessionFactory() as session:
        try:
            popularity_result = await run_popularity_pipeline(session)
            new_entries = popularity_result["comparison"]["new_entries"]
            print(f"[popularity] 获取 {popularity_result['stock_count']} 只股票，新增 {popularity_result['new_entry_count']} 只")
            if not new_entries:
                print("[run-all] 本次榜单没有新增股票")
                return
            await run_fetch_pipeline_for_rows(session, new_entries, run_type="fetch", source="ths_new_entries")
            if fetch_only:
                return
            await run_and_store(session, stock_codes=[row["stock_code"] for row in new_entries])
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch THS top200, detect new entries, then analyze them.")
    parser.add_argument("--fetch-only", action="store_true", help="Only fetch popularity/news/market data.")
    args = parser.parse_args()
    asyncio.run(main_async(fetch_only=args.fetch_only))


if __name__ == "__main__":
    main()
