"""策略参数优化器 - 网格搜索 + 滚动前进优化"""

import asyncio
import itertools
import logging
from datetime import date, timedelta
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.crud import quant_crud
from stock_service.quant.application.backtest_engine import BacktestEngine
from stock_service.quant.application.strategy_engine import engine as _default_engine
from stock_service.quant.domain.backtest_rules import BacktestConfig

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardWindow:
    """单个滚动窗口的结果"""
    window_id: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    best_params: dict
    train_metrics: dict
    test_metrics: dict


@dataclass
class WalkForwardResult:
    """滚动前进优化的汇总结果"""
    windows: list[WalkForwardWindow]
    avg_test_metrics: dict  # 各窗口 test_metrics 的平均值
    best_params_per_window: list[dict]
    stability_score: float  # 参数稳定性（0-1，越高越好）


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

    async def walk_forward(
        self,
        strategy_id: int,
        param_grid: dict[str, list],
        stock_codes: list[str],
        start_date: date,
        end_date: date,
        train_days: int = 180,
        test_days: int = 60,
        step_days: int = 60,
        config: BacktestConfig | None = None,
        strategy_engine=None,
        metric: str = "sharpe_ratio",
    ) -> WalkForwardResult:
        """滚动前进优化（Walk-Forward Optimization）

        将历史数据分成多个滚动窗口，每个窗口包含训练期和测试期。
        在训练期用网格搜索找最优参数，在测试期验证这些参数的效果。
        最终取各窗口测试结果的平均值作为策略评价。

        Args:
            strategy_id: 策略 ID
            param_grid: 参数网格
            stock_codes: 股票代码列表
            start_date: 总起始日期
            end_date: 总结束日期
            train_days: 训练窗口天数（默认 180 天）
            test_days: 测试窗口天数（默认 60 天）
            step_days: 每次滚动步长（默认 60 天）
            config: 回测配置
            strategy_engine: 策略引擎
            metric: 优化目标指标

        Returns:
            WalkForwardResult 包含各窗口结果和汇总指标
        """
        if config is None:
            config = BacktestConfig()
        if strategy_engine is None:
            strategy_engine = _default_engine

        # 生成滚动窗口
        windows: list[tuple[date, date, date, date]] = []  # (train_start, train_end, test_start, test_end)
        current = start_date
        while True:
            train_start = current
            train_end = train_start + timedelta(days=train_days)
            test_start = train_end + timedelta(days=1)
            test_end = test_start + timedelta(days=test_days)

            if test_end > end_date:
                break

            windows.append((train_start, train_end, test_start, test_end))
            current += timedelta(days=step_days)

        if not windows:
            raise ValueError(
                f"无法生成滚动窗口：日期范围 {start_date}~{end_date} "
                f"不足 {train_days}+{test_days} 天"
            )

        logger.info(
            f"Walk-forward: {len(windows)} 个窗口, "
            f"训练{train_days}天 + 测试{test_days}天, 步长{step_days}天"
        )

        # 获取策略信息
        strategy = await quant_crud.get_strategy(self._session, strategy_id)
        if not strategy:
            raise ValueError(f"Strategy {strategy_id} not found")
        strategy_type = strategy["type"]
        base_params = strategy.get("params") or {}

        # 生成参数组合
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combinations = list(itertools.product(*param_values))

        window_results: list[WalkForwardWindow] = []

        for wi, (train_start, train_end, test_start, test_end) in enumerate(windows):
            logger.info(
                f"窗口 {wi+1}/{len(windows)}: "
                f"训练 {train_start}~{train_end}, 测试 {test_start}~{test_end}"
            )

            # ── 训练期：网格搜索找最优参数 ──
            best_score = -999 if metric != "max_drawdown" else 999
            best_params = base_params.copy()
            best_train_metrics: dict = {}

            for combo in combinations:
                params = base_params.copy()
                for name, value in zip(param_names, combo):
                    params[name] = value

                try:
                    strategy_engine._strategies[strategy_type].set_params(params)
                    engine = BacktestEngine(self._session)
                    result = await engine.run(
                        strategy_id=strategy_id,
                        stock_codes=stock_codes,
                        start_date=train_start,
                        end_date=train_end,
                        config=config,
                        strategy_engine=strategy_engine,
                    )
                    metrics = result.get("metrics", {})
                    score = metrics.get(metric, 0)

                    is_better = (
                        (metric == "max_drawdown" and abs(score) < abs(best_score))
                        or (metric != "max_drawdown" and score > best_score)
                    )
                    if is_better:
                        best_score = score
                        best_params = params.copy()
                        best_train_metrics = metrics

                except Exception as e:
                    logger.debug(f"训练期回测失败: {e}")

            # ── 测试期：用最优参数验证 ──
            logger.info(f"窗口 {wi+1} 最优参数: {best_params}")
            strategy_engine._strategies[strategy_type].set_params(best_params)

            try:
                engine = BacktestEngine(self._session)
                test_result = await engine.run(
                    strategy_id=strategy_id,
                    stock_codes=stock_codes,
                    start_date=test_start,
                    end_date=test_end,
                    config=config,
                    strategy_engine=strategy_engine,
                )
                test_metrics = test_result.get("metrics", {})
            except Exception as e:
                logger.warning(f"窗口 {wi+1} 测试期回测失败: {e}")
                test_metrics = {}

            window_results.append(WalkForwardWindow(
                window_id=wi + 1,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                best_params=best_params,
                train_metrics=best_train_metrics,
                test_metrics=test_metrics,
            ))

        # ── 汇总 ──
        # 计算测试期平均指标
        metric_keys = ["total_return", "annual_return", "max_drawdown", "sharpe_ratio", "sortino_ratio", "win_rate"]
        avg_metrics: dict[str, float] = {}
        valid_windows = [w for w in window_results if w.test_metrics]
        if valid_windows:
            for key in metric_keys:
                values = [w.test_metrics.get(key, 0) for w in valid_windows]
                avg_metrics[f"avg_{key}"] = round(sum(values) / len(values), 4)

        # 参数稳定性：各窗口最优参数的一致性
        if len(window_results) > 1:
            param_stability_scores = []
            for name in param_names:
                values = [w.best_params.get(name) for w in window_results]
                unique_ratio = len(set(values)) / len(values)
                param_stability_scores.append(1.0 - unique_ratio)
            stability = round(sum(param_stability_scores) / len(param_stability_scores), 4) if param_stability_scores else 0
        else:
            stability = 1.0

        result = WalkForwardResult(
            windows=window_results,
            avg_test_metrics=avg_metrics,
            best_params_per_window=[w.best_params for w in window_results],
            stability_score=stability,
        )

        logger.info(
            f"Walk-forward 完成: {len(valid_windows)} 个有效窗口, "
            f"平均测试 {metric}={avg_metrics.get(f'avg_{metric}', 'N/A')}, "
            f"参数稳定性={stability}"
        )

        return result
