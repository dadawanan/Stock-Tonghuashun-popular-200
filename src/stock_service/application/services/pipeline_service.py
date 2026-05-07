from __future__ import annotations

from stock_service.application.services.analysis_service import run_analysis, store_analysis_results
from stock_service.application.services.market_data_service import run_fetch_pipeline_for_rows
from stock_service.application.services.popularity_service import run_popularity_pipeline
from stock_service.infrastructure.db.database import StockDatabase


async def run_all_pipeline(db: StockDatabase) -> dict:
    fetch_popularity_result = await run_popularity_pipeline()
    new_entries = fetch_popularity_result["comparison"]["new_entries"]
    if not new_entries:
        return {
            "popularity": fetch_popularity_result,
            "analysis": {"result_count": 0, "stocks": [], "message": "本次榜单没有新增股票"},
        }
    fetch_result = await run_fetch_pipeline_for_rows(new_entries, run_type="fetch", source="ths_new_entries")
    stock_codes = [row["stock_code"] for row in new_entries]
    results, meta = await run_analysis(db, stock_codes=stock_codes)
    count = await store_analysis_results(db, results, meta, run_type="run_all", source="rule")
    return {
        "popularity": fetch_popularity_result,
        "analysis": {"result_count": count, "fetch_result": fetch_result, "stocks": stock_codes, "results": results},
    }

