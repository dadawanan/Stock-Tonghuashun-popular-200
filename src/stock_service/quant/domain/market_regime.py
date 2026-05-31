"""市场环境识别：基于沪深300 MA50/MA200 判断牛/熊/震荡"""

import logging

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from stock_service.crud import quant_crud
from stock_service.quant.domain.indicators import TechnicalIndicators
from stock_service.quant.domain.strategy_interface import MarketRegime

logger = logging.getLogger(__name__)

# 沪深300指数代码
CSI300_CODE = "000300.SH"


async def detect_market_regime(
    session: AsyncSession,
    index_code: str = CSI300_CODE,
) -> MarketRegime:
    """基于指数的 MA50/MA200 判断当前市场环境

    判断规则：
    - MA50 > MA200 * 1.02 → 牛市（趋势明确向上）
    - MA50 < MA200 * 0.98 → 熊市（趋势明确向下）
    - 其他 → 震荡

    Returns:
        MarketRegime 枚举值
    """
    # 获取指数历史数据（至少 200 天）
    rows = await quant_crud.get_stock_daily(session, index_code)
    if len(rows) < 200:
        logger.warning(f"[regime] {index_code} 数据不足 200 天（{len(rows)} 天），默认震荡")
        return MarketRegime.SIDEWAYS

    df = pd.DataFrame(rows).sort_values("trade_date")
    close = df["close"].astype(float)

    ma50 = TechnicalIndicators.ma(close, 50)
    ma200 = TechnicalIndicators.ma(close, 200)

    latest_ma50 = float(ma50.iloc[-1]) if pd.notna(ma50.iloc[-1]) else 0
    latest_ma200 = float(ma200.iloc[-1]) if pd.notna(ma200.iloc[-1]) else 0

    if latest_ma200 == 0:
        return MarketRegime.SIDEWAYS

    ratio = latest_ma50 / latest_ma200

    if ratio > 1.02:
        regime = MarketRegime.BULL
    elif ratio < 0.98:
        regime = MarketRegime.BEAR
    else:
        regime = MarketRegime.SIDEWAYS

    logger.info(f"[regime] {index_code} MA50={latest_ma50:.2f} MA200={latest_ma200:.2f} ratio={ratio:.4f} → {regime.value}")
    return regime
