import pytest
import pandas as pd
import numpy as np
from stock_service.quant.domain.indicators import TechnicalIndicators


class TestRSI:
    def test_rsi_basic(self):
        prices = pd.Series([100, 102, 101, 103, 105, 104, 106, 108, 107, 110,
                            109, 111, 113, 112, 115, 114, 116, 118, 117, 120])
        rsi = TechnicalIndicators.rsi(prices, period=14)
        last_rsi = rsi.iloc[-1]
        assert 0 <= last_rsi <= 100

    def test_rsi_uptrend(self):
        prices = pd.Series(range(100, 130))
        rsi = TechnicalIndicators.rsi(prices, period=14)
        assert rsi.iloc[-1] > 70

    def test_rsi_downtrend(self):
        prices = pd.Series(range(130, 100, -1))
        rsi = TechnicalIndicators.rsi(prices, period=14)
        assert rsi.iloc[-1] < 30


class TestMACD:
    def test_macd_returns_three_series(self):
        prices = pd.Series(range(100, 150))
        macd_line, signal_line, histogram = TechnicalIndicators.macd(prices)
        assert len(macd_line) == len(prices)
        assert len(signal_line) == len(prices)
        assert len(histogram) == len(prices)

    def test_macd_histogram_is_difference(self):
        prices = pd.Series(range(100, 150))
        macd_line, signal_line, histogram = TechnicalIndicators.macd(prices)
        pd.testing.assert_series_equal(
            histogram, macd_line - signal_line, check_names=False
        )


class TestBollingerBands:
    def test_boll_returns_three_series(self):
        prices = pd.Series(range(100, 130))
        upper, middle, lower = TechnicalIndicators.bollinger_bands(prices)
        assert len(upper) == len(prices)

    def test_middle_is_moving_average(self):
        prices = pd.Series(range(100, 130))
        upper, middle, lower = TechnicalIndicators.bollinger_bands(prices, period=20)
        expected = prices.rolling(20).mean()
        pd.testing.assert_series_equal(middle, expected, check_names=False)

    def test_upper_above_middle_above_lower(self):
        prices = pd.Series(np.random.randn(50).cumsum() + 100)
        upper, middle, lower = TechnicalIndicators.bollinger_bands(prices, period=20)
        valid = middle.dropna().index
        assert (upper[valid] >= middle[valid]).all()
        assert (middle[valid] >= lower[valid]).all()
