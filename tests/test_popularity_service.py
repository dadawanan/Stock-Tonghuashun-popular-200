from __future__ import annotations

import pandas as pd

from stock_service.application.services.popularity_service import (
    _popularity_signature_from_frame,
    _popularity_signature_from_rows,
)


def test_popularity_signatures_match_for_same_ranking() -> None:
    stocks_df = pd.DataFrame(
        [
            {"stock_code": "600584.SH", "popularity_rank": 1},
            {"stock_code": "002156.SZ", "popularity_rank": 2},
            {"stock_code": "000725.SZ", "popularity_rank": 3},
        ]
    )
    snapshot_rows = [
        {"stock_code": "000725.SZ", "popularity_rank": 3},
        {"stock_code": "600584.SH", "popularity_rank": 1},
        {"stock_code": "002156.SZ", "popularity_rank": 2},
    ]

    assert _popularity_signature_from_frame(stocks_df) == _popularity_signature_from_rows(snapshot_rows)


def test_popularity_signatures_differ_when_ranking_changes() -> None:
    stocks_df = pd.DataFrame(
        [
            {"stock_code": "600584.SH", "popularity_rank": 1},
            {"stock_code": "002156.SZ", "popularity_rank": 2},
        ]
    )
    snapshot_rows = [
        {"stock_code": "600584.SH", "popularity_rank": 2},
        {"stock_code": "002156.SZ", "popularity_rank": 1},
    ]

    assert _popularity_signature_from_frame(stocks_df) != _popularity_signature_from_rows(snapshot_rows)
