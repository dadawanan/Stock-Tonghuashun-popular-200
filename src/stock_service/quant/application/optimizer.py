"""策略参数优化器 - 网格搜索"""

import asyncio
import itertools
import logging
from datetime import date
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.crud import quant_crud
from stock_service.quant.application.backtest_engine import BacktestEngine
from stock_service.quant.application.strategy_engine import engine as _default_engine
from stock_service.quant.domain.backtest_rules import BacktestConfig

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    params: dict
    metrics: dict
    backtest_id: int


class ParameterOptimizer:
    """Grid search optimizer for strategy parameters."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def grid_search(
        self,
        strategy_id: int,
        param_grid: dict[str, list],
        stock_codes: list[str],
        start_date: date,
        end_date: date,
        config: BacktestConfig | None = None,
        strategy_engine: StrategyEngine | None = None,
        metric: str = "sharpe_ratio",  # Optimization target
        top_n: int = 5,  # Return top N results
    ) -> list[OptimizationResult]:
        """Run grid search over parameter combinations.

        Args:
            strategy_id: Strategy to optimize
            param_grid: Dict of param_name -> list of values to try
            stock_codes: Stocks to backtest on
            start_date: Backtest start date
            end_date: Backtest end date
            config: Backtest config (uses defaults if None)
            strategy_engine: Strategy engine instance
            metric: Metric to optimize (sharpe_ratio, total_return, win_rate, max_drawdown)
            top_n: Number of top results to return

        Returns:
            List of OptimizationResult sorted by metric (best first)
        """
        if config is None:
            config = BacktestConfig()
        if strategy_engine is None:
            strategy_engine = _default_engine

        # Get strategy info
        strategy = await quant_crud.get_strategy(self._session, strategy_id)
        if not strategy:
            raise ValueError(f"Strategy {strategy_id} not found")

        strategy_type = strategy["type"]
        base_params = strategy.get("params") or {}

        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combinations = list(itertools.product(*param_values))

        logger.info(
            f"Starting grid search: {len(combinations)} combinations "
            f"for strategy '{strategy_type}'"
        )

        results = []
        for i, combo in enumerate(combinations):
            params = base_params.copy()
            for name, value in zip(param_names, combo):
                params[name] = value

            logger.info(f"[{i+1}/{len(combinations)}] Testing params: {dict(zip(param_names, combo))}")

            try:
                # Update strategy params
                strategy_engine._strategies[strategy_type].set_params(params)

                # Run backtest
                engine = BacktestEngine(self._session)
                backtest_result = await engine.run(
                    strategy_id=strategy_id,
                    stock_codes=stock_codes,
                    start_date=start_date,
                    end_date=end_date,
                    config=config,
                    strategy_engine=strategy_engine,
                )

                metrics = backtest_result.get("metrics", {})
                backtest_id = backtest_result.get("backtest_id", 0)

                results.append(OptimizationResult(
                    params=dict(zip(param_names, combo)),
                    metrics=metrics,
                    backtest_id=backtest_id,
                ))

            except Exception as e:
                logger.warning(f"Backtest failed for params {dict(zip(param_names, combo))}: {e}")

        # Sort by metric
        if metric == "max_drawdown":
            # For drawdown, lower absolute value is better
            results.sort(key=lambda r: abs(r.metrics.get(metric, 999)))
        else:
            results.sort(key=lambda r: r.metrics.get(metric, -999), reverse=True)

        # Return top N
        top_results = results[:top_n]

        logger.info(
            f"Grid search complete. Best {metric}: {top_results[0].metrics.get(metric, 'N/A') if top_results else 'N/A'}"
        )

        return top_results

    async def suggest_params(
        self, strategy_type: str
    ) -> dict[str, list]:
        """Suggest parameter ranges for grid search based on strategy type."""

        if strategy_type == "popularity":
            return {
                "top_n": [30, 50, 100],
                "rank_drop_threshold": [-10, -20, -30],
                "new_entry_score_boost": [1.0, 1.2, 1.5],
            }
        elif strategy_type == "sentiment":
            return {
                "buy_threshold": [1.5, 2.0, 2.5, 3.0],
                "sell_threshold": [-2.0, -1.5, -1.0],
                "text_weight": [0.4, 0.55, 0.7],
            }
        elif strategy_type == "technical":
            return {
                "ma_short": [5, 10],
                "ma_long": [20, 30],
                "rsi_oversold": [25, 30, 35],
                "rsi_overbought": [65, 70, 75],
                "buy_threshold": [0.2, 0.3, 0.4],
                "sell_threshold": [-0.4, -0.3, -0.2],
            }
        elif strategy_type == "multi_factor":
            return {
                "buy_threshold": [0.5, 0.6, 0.7],
                "sell_threshold": [-0.5, -0.4, -0.3],
            }
        else:
            return {}
