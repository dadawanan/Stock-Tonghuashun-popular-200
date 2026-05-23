from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.crud import v2_crud


class AnalysisAdapter:
    """Adapter to read analysis results from v2 tables for quant strategies."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_analysis_signals(self, codes: list[str]) -> dict[str, dict]:
        """Get latest analysis results for given stock codes."""
        result = {}
        for code in codes:
            analysis = await v2_crud.get_latest_stock_analysis(self._session, code)
            if analysis:
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
        result = {}
        for code in codes:
            snapshot = await v2_crud.get_latest_popularity_by_code(self._session, code)
            if snapshot:
                result[code] = {
                    "rank": snapshot.get("popularity_rank", 999),
                    "score": float(snapshot.get("popularity_score", 0) or 0),
                    "is_new_entry": snapshot.get("is_new_entry", False),
                    "rank_change": snapshot.get("rank_change", 0) or 0,
                }
        return result

    async def get_latest_popularity_codes(self, limit: int = 200) -> list[str]:
        """Get latest popularity ranking stock codes."""
        snapshots = await v2_crud.get_latest_popularity(self._session, limit=limit)
        return [s["stock_code"] for s in snapshots]
