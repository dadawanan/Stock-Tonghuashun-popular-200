import logging
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.crud import quant_crud

logger = logging.getLogger(__name__)


class FeedbackService:
    """Closed-loop feedback: analyze backtest results and suggest optimizations."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def analyze_backtest_insights(self, backtest_id: int) -> dict:
        """Analyze backtest results and extract optimization suggestions."""
        trades = await quant_crud.get_backtest_trades(self._session, backtest_id)
        result = await quant_crud.get_backtest_result(self._session, backtest_id)

        if not result:
            raise ValueError(f"Backtest {backtest_id} not found")

        signal_stats = {}
        for trade in trades:
            source = trade.get("signal_source", "unknown")
            if source not in signal_stats:
                signal_stats[source] = {"wins": 0, "losses": 0, "total_pnl": 0, "trades": 0}

            signal_stats[source]["trades"] += 1
            pnl = float(trade.get("pnl", 0) or 0)
            signal_stats[source]["total_pnl"] += pnl
            if pnl > 0:
                signal_stats[source]["wins"] += 1
            elif pnl < 0:
                signal_stats[source]["losses"] += 1

        for source, stats in signal_stats.items():
            total = stats["wins"] + stats["losses"]
            stats["win_rate"] = round(stats["wins"] / total, 4) if total > 0 else 0
            stats["total_pnl"] = round(stats["total_pnl"], 2)

        suggestions = self._generate_suggestions(signal_stats)

        return {
            "overall": {
                "win_rate": result.get("win_rate"),
                "sharpe": result.get("sharpe"),
                "max_drawdown": result.get("max_drawdown"),
                "annual_return": result.get("annual_return"),
            },
            "by_signal": signal_stats,
            "suggestions": suggestions,
        }

    def _generate_suggestions(self, signal_stats: dict) -> list[str]:
        suggestions = []
        for source, stats in signal_stats.items():
            if stats["trades"] < 5:
                continue
            if stats["win_rate"] > 0.6:
                suggestions.append(
                    f"{source} 信号胜率 {stats['win_rate']:.1%}，"
                    f"建议提高该信号权重"
                )
            elif stats["win_rate"] < 0.4:
                suggestions.append(
                    f"{source} 信号胜率 {stats['win_rate']:.1%}，"
                    f"建议降低该信号权重或优化规则"
                )
        return suggestions

    async def suggest_weight_adjustment(self, backtest_id: int) -> dict:
        """Suggest weight adjustments for multi-factor strategy."""
        insights = await self.analyze_backtest_insights(backtest_id)
        signal_stats = insights["by_signal"]

        if not signal_stats:
            return {"adjustments": {}, "reason": "Insufficient data"}

        valid_sources = {k: v for k, v in signal_stats.items() if v["trades"] >= 3}
        if not valid_sources:
            return {"adjustments": {}, "reason": "Insufficient trades per signal"}

        best = max(valid_sources.items(), key=lambda x: x[1]["win_rate"])
        worst = min(valid_sources.items(), key=lambda x: x[1]["win_rate"])

        adjustments = {}
        reasons = []

        if best[1]["win_rate"] > 0.55:
            adjustments[best[0]] = 0.05
            reasons.append(f"{best[0]} 胜率高({best[1]['win_rate']:.1%})，建议加权")

        if worst[1]["win_rate"] < 0.45:
            adjustments[worst[0]] = -0.05
            reasons.append(f"{worst[0]} 胜率低({worst[1]['win_rate']:.1%})，建议减权")

        return {
            "adjustments": adjustments,
            "reason": "; ".join(reasons) if reasons else "No significant adjustment needed",
            "insights": insights,
        }

    async def log_feedback(
        self, backtest_id: int, strategy_id: int,
        feedback_type: str, before_params: dict,
        after_params: dict, reason: str,
    ) -> dict:
        """Log a feedback action."""
        return await quant_crud.create_feedback_log(self._session, {
            "backtest_id": backtest_id,
            "strategy_id": strategy_id,
            "feedback_type": feedback_type,
            "before_params": before_params,
            "after_params": after_params,
            "reason": reason,
        })
