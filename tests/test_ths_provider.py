from __future__ import annotations

import pandas as pd
import pytest

from stock_service.infrastructure.providers import ths_provider


def test_fetch_top_200_popularity_reports_empty_upstream_response(monkeypatch: pytest.MonkeyPatch):
    def fake_get_robot_data(**kwargs):
        return None

    monkeypatch.setattr(ths_provider.pywencai_wencai, "get_robot_data", fake_get_robot_data)

    with pytest.raises(RuntimeError, match="同花顺人气榜抓取失败: 同花顺接口空响应或结构异常"):
        ths_provider.fetch_top_200_popularity()


def test_fetch_top_200_popularity_returns_empty_dataframe_when_row_count_is_zero(monkeypatch: pytest.MonkeyPatch):
    def fake_get_robot_data(**kwargs):
        return {
            "data": {"condition": "mock-condition"},
            "url_params": {"foo": "bar"},
            "row_count": 0,
        }

    monkeypatch.setattr(ths_provider.pywencai_wencai, "get_robot_data", fake_get_robot_data)

    result = ths_provider.fetch_top_200_popularity()

    assert isinstance(result, pd.DataFrame)
    assert result.empty
