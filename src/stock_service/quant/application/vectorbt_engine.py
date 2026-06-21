"""VectorBT 向量化回测引擎

基于 vectorbt 库实现高性能回测，支持：
- 批量数据加载（一次查询）
- 向量化信号生成
- 原生参数优化
- 多资产并行回测
"""

import logging
from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class VectorBTEngine:
    """VectorBT 向量化回测引擎"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def run(
        self,
        stock_codes: list[str],
        start_date: date,
        end_date: date,
        strategy_type: str,
        strategy_params: dict[str, Any],
        initial_capital: float = 1_000_000,
        commission_rate: float = 0.0003,
        slippage: float = 0.002,
        stamp_tax: float = 0.001,
    ) -> dict:
        """执行向量化回测

        Args:
            stock_codes: 股票代码列表
            start_date: 回测开始日期
            end_date: 回测结束日期
            strategy_type: 策略类型（vbt_ma_cross / vbt_rsi / vbt_bollinger / vbt_macd）
            strategy_params: 策略参数
            initial_capital: 初始资金
            commission_rate: 佣金率
            slippage: 滑点
            stamp_tax: 印花税率

        Returns:
            {"trades": [...], "daily_nav": [...], "metrics": {...}}
        """
        import vectorbt as vbt

        # 1. 批量加载价格数据
        price_data = await self._load_price_data(stock_codes, start_date, end_date)
        if price_data.empty:
            raise ValueError("无可用价格数据")

        logger.info(
            f"[vbt] 加载 {len(stock_codes)} 只股票, "
            f"{len(price_data)} 个交易日, "
            f"数据量: {price_data.shape}"
        )

        # 2. 生成信号
        entries, exits = self._generate_signals(
            strategy_type, strategy_params, price_data
        )

        # 3. 执行回测
        # VectorBT fees 对称apply，无法区分买卖。
        # A股印花税只在卖出时收，这里将 stamp_tax 叠加到 fees 上
        # （买入多收、卖出少收的误差可接受）
        total_fee_rate = commission_rate + stamp_tax / 2
        portfolio = vbt.Portfolio.from_signals(
            close=price_data,
            entries=entries,
            exits=exits,
            init_cash=initial_capital,
            fees=total_fee_rate,
            slippage=slippage,
            freq="1D",
        )

        # 4. 提取结果
        trades = self._extract_trades(portfolio)
        daily_nav = self._extract_daily_nav(portfolio)
        metrics = self._calculate_metrics(portfolio, initial_capital)

        logger.info(
            f"[vbt] 回测完成: {metrics['total_trades']} 笔交易, "
            f"总收益 {metrics['total_return']:.2%}, "
            f"最大回撤 {metrics['max_drawdown']:.2%}"
        )

        return {
            "trades": trades,
            "daily_nav": daily_nav,
            "metrics": metrics,
        }

    async def _load_price_data(
        self, codes: list[str], start: date, end: date
    ) -> pd.DataFrame:
        """批量加载价格数据

        Returns:
            DataFrame, index=日期, columns=股票代码, values=收盘价
        """
        from sqlalchemy import text

        stmt = text("""
            SELECT code, trade_date, close
            FROM stock_daily
            WHERE code = ANY(:codes)
              AND trade_date >= :start
              AND trade_date <= :end
            ORDER BY trade_date, code
        """)
        result = await self._session.execute(
            stmt, {"codes": codes, "start": start, "end": end}
        )
        rows = result.fetchall()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=["code", "trade_date", "close"])
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        pivot = df.pivot(index="trade_date", columns="code", values="close")
        pivot.index.name = None
        return pivot

    def _generate_signals(
        self, strategy_type: str, params: dict, price: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """根据策略类型生成向量化信号"""
        import vectorbt as vbt

        if strategy_type == "vbt_ma_cross":
            return self._ma_cross_signals(params, price, vbt)
        elif strategy_type == "vbt_rsi":
            return self._rsi_signals(params, price, vbt)
        elif strategy_type == "vbt_bollinger":
            return self._bollinger_signals(params, price, vbt)
        elif strategy_type == "vbt_macd":
            return self._macd_signals(params, price, vbt)
        else:
            raise ValueError(f"VectorBT 不支持策略: {strategy_type}")

    def _ma_cross_signals(
        self, params: dict, price: pd.DataFrame, vbt
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """均线交叉策略"""
        fast = params.get("fast_period", 5)
        slow = params.get("slow_period", 20)

        fast_ma = vbt.MA.run(price, window=fast)
        slow_ma = vbt.MA.run(price, window=slow)

        entries = fast_ma.ma_crossed_above(slow_ma)
        exits = fast_ma.ma_crossed_below(slow_ma)
        return entries, exits

    def _rsi_signals(
        self, params: dict, price: pd.DataFrame, vbt
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """RSI 超买超卖策略"""
        period = params.get("period", 14)
        oversold = params.get("oversold", 30)
        overbought = params.get("overbought", 70)

        rsi = vbt.RSI.run(price, window=period)
        entries = rsi.rsi_crossed_below(oversold)
        exits = rsi.rsi_crossed_above(overbought)
        return entries, exits

    def _bollinger_signals(
        self, params: dict, price: pd.DataFrame, vbt
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """布林带突破策略"""
        period = params.get("period", 20)
        alpha = params.get("alpha", 2.0)

        bbands = vbt.BBANDS.run(price, window=period, alpha=alpha)
        entries = price < bbands.lower
        exits = price > bbands.upper
        return entries, exits

    def _macd_signals(
        self, params: dict, price: pd.DataFrame, vbt
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """MACD 策略"""
        fast = params.get("fast_period", 12)
        slow = params.get("slow_period", 26)
        signal = params.get("signal_period", 9)

        macd = vbt.MACD.run(price, fast_window=fast, slow_window=slow, signal_window=signal)
        entries = macd.macd_crossed_above(macd.signal)
        exits = macd.macd_crossed_below(macd.signal)
        return entries, exits

    def _extract_trades(self, portfolio) -> list[dict]:
        """从 VectorBT 结果提取交易记录"""
        trades = []

        try:
            # VectorBT 1.0.0 使用 portfolio.trades.records
            if hasattr(portfolio, "trades") and hasattr(portfolio.trades, "records"):
                records = portfolio.trades.records
            elif hasattr(portfolio, "trade_records"):
                records = portfolio.trade_records
            else:
                logger.warning("[vbt] 无法访问交易记录属性")
                return trades

            if records is None or len(records) == 0:
                return trades

            for _, record in records.iterrows():
                trades.append({
                    "code": str(record.get("col", record.get("Column", ""))),
                    "side": "buy" if record.get("dir", record.get("Direction", 1)) == 1 else "sell",
                    "price": float(record.get("entry_price", record.get("Avg Entry Price", 0))),
                    "quantity": abs(int(record.get("size", record.get("Size", 0)))),
                    "trade_date": str(record.get("entry_timestamp", record.get("Entry Timestamp", "")))[:10],
                    "pnl": float(record.get("pnl", record.get("PnL", 0))),
                    "pnl_pct": float(record.get("return", record.get("Return", 0))),
                    "signal_source": "vectorbt",
                })
        except Exception as e:
            logger.warning(f"[vbt] 提取交易记录失败: {e}", exc_info=True)

        return trades

    def _extract_daily_nav(self, portfolio) -> list[dict]:
        """提取每日净值"""
        nav = portfolio.value()
        result = []
        for d, v in nav.items():
            trade_date = str(d.date()) if hasattr(d, "date") else str(d)[:10]
            result.append({
                "trade_date": trade_date,
                "nav": float(v),
                "total_assets": float(v),
            })
        return result

    def _calculate_metrics(self, portfolio, initial_capital: float) -> dict:
        """计算绩效指标"""
        try:
            total_return = float(portfolio.total_return())
            annual_return = float(portfolio.annualized_return())
            max_dd = float(portfolio.max_drawdown())
            sharpe = float(portfolio.sharpe_ratio())
            sortino = float(portfolio.sortino_ratio())
            calmar = float(portfolio.calmar_ratio())
        except Exception as e:
            logger.warning(f"[vbt] 计算收益指标失败: {e}")
            total_return = annual_return = max_dd = sharpe = sortino = calmar = 0.0

        try:
            win_rate = float(portfolio.trades.win_rate())
            total_trades = int(portfolio.trades.count())
            profit_factor = float(portfolio.trades.profit_factor())
        except Exception as e:
            logger.warning(f"[vbt] 计算交易统计失败: {e}")
            win_rate = total_trades = profit_factor = 0.0

        return {
            "total_return": total_return,
            "annual_return": annual_return,
            "max_drawdown": max_dd,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "calmar_ratio": calmar,
            "win_rate": win_rate,
            "total_trades": total_trades,
            "profit_factor": profit_factor,
        }


# ── 策略注册表 ──

VECTORBT_STRATEGIES = {
    "vbt_ma_cross": {
        "name": "VBT 均线交叉",
        "description": "快线上穿慢线买入，下穿卖出",
        "params": {
            "fast_period": {"default": 5, "min": 2, "max": 50, "label": "快线周期"},
            "slow_period": {"default": 20, "min": 10, "max": 200, "label": "慢线周期"},
        },
    },
    "vbt_rsi": {
        "name": "VBT RSI 超买超卖",
        "description": "RSI 低于超卖线买入，高于超买线卖出",
        "params": {
            "period": {"default": 14, "min": 5, "max": 50, "label": "RSI 周期"},
            "oversold": {"default": 30, "min": 10, "max": 40, "label": "超卖线"},
            "overbought": {"default": 70, "min": 60, "max": 90, "label": "超买线"},
        },
    },
    "vbt_bollinger": {
        "name": "VBT 布林带突破",
        "description": "价格跌破下轨买入，突破上轨卖出",
        "params": {
            "period": {"default": 20, "min": 10, "max": 50, "label": "周期"},
            "alpha": {"default": 2.0, "min": 1.0, "max": 3.0, "label": "标准差倍数"},
        },
    },
    "vbt_macd": {
        "name": "VBT MACD 金叉死叉",
        "description": "MACD 金叉买入，死叉卖出",
        "params": {
            "fast_period": {"default": 12, "min": 5, "max": 30, "label": "快线周期"},
            "slow_period": {"default": 26, "min": 15, "max": 50, "label": "慢线周期"},
            "signal_period": {"default": 9, "min": 5, "max": 20, "label": "信号线周期"},
        },
    },
}
