from __future__ import annotations

import argparse
from pathlib import Path

from data_fetcher import generate_market_data, generate_news_data, read_stock_pool
from stock_analyzer import run_analysis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze newly added THS popularity stocks.")
    parser.add_argument(
        "--stocks",
        default="新增股票.csv",
        help="CSV file for newly added popularity stocks.",
    )
    parser.add_argument(
        "--news",
        default="news_data.csv",
        help="CSV file for stock news and announcements.",
    )
    parser.add_argument(
        "--market",
        default="market_data.csv",
        help="CSV file for quantitative market signals.",
    )
    parser.add_argument(
        "--output",
        default="analysis_result.csv",
        help="Output CSV file for the final integrated analysis.",
    )
    parser.add_argument(
        "--fetch-real-data",
        action="store_true",
        help="Fetch real news_data.csv and market_data.csv before analysis.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.fetch_real_data:
        stocks_df = read_stock_pool(Path(args.stocks))
        generate_news_data(stocks_df, Path(args.news))
        generate_market_data(stocks_df, Path(args.market))
    result = run_analysis(
        stocks_file=Path(args.stocks),
        news_file=Path(args.news),
        market_file=Path(args.market),
        output_file=Path(args.output),
    )
    print(f"分析完成，输出文件: {result}")


if __name__ == "__main__":
    main()
