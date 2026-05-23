from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.crud import v2_crud


class AnalysisAdapter:
    """Adapter to read analysis results from v2 tables for quant strategies."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_analysis_signals(self, codes: list[str]) -> dict[str, dict]:
        """Get latest analysis results for given stock codes."""
        all_analyses = await v2_crud.get_latest_analysis(self._session, limit=500)
        code_set = set(codes)

        result = {}
        for analysis in all_analyses:
            code = analysis.get("stock_code", "")
            if code in code_set and code not in result:
                result[code] = {
                    "text_score": float(analysis.get("text_score", 0) or 0),
                    "market_score": float(analysis.get("market_score", 0) or 0),
                    "integrated_score": float(analysis.get("integrated_score", 0) or 0),
                    "behavior_label": analysis.get("behavior_label", ""),
                    "decision": analysis.get("decision", ""),
                }
        return result

    async def get_popularity_data(self, codes: list[str], trade_date: date | None = None) -> dict[str, dict]:
        """Get popularity ranking data for given stock codes."""
        all_snapshots = await v2_crud.get_latest_popularity_snapshot(self._session)
        code_set = set(codes)

        result = {}
        for snap in all_snapshots:
            code = snap.get("stock_code", "")
            if code in code_set and code not in result:
                result[code] = {
                    "rank": snap.get("popularity_rank", 999),
                    "score": float(snap.get("popularity_score", 0) or 0),
                    "is_new_entry": snap.get("is_new_entry", False),
                    "rank_change": snap.get("rank_change", 0) or 0,
                }
        return result

    async def get_latest_popularity_codes(self, limit: int = 200) -> list[str]:
        """Get latest popularity ranking stock codes."""
        snapshots = await v2_crud.get_latest_popularity_snapshot(self._session)
        return [s["stock_code"] for s in snapshots[:limit]]
