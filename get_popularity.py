from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pandas as pd

import pywencai

from database import StockDatabase


def get_top_200_popularity() -> pd.DataFrame:
    """Fetch top 200 popularity stocks from THS via pywencai."""
    query_text = "人气排名前200"

    try:
        df = pywencai.get(
            query=query_text,
            cookie=(
                "other_uid=Ths_iwencai_Xuangu_agsdg2irvmfxm1n8ky28tkie88jpcbek; "
                "cid=68427bc55522fae6a5111dbd92156a501777565240; _clck=6k8vpw%7C2%7Cg5o%7C0%7C0; "
                "u_ukey=A10702B8689642C6BE607730E11E6E4A; u_uver=1.0.0; "
                "u_dpass=7JtSi9YA7SmYS5Vll74m3DDNDkuM%2BVmwKzLJIaxbGUR9nqWYNhRDTmVwYwNuXuYtHi80LrSsTFH9a%2B6rtRvqGg%3D%3D; "
                "u_did=EA7ACB21D3BC466E954A0D9BD56D245A; u_ttype=WEB; "
                "user=MDrN7bCyQXVrOjpOb25lOjUwMDo1MjA4MDM2Mjg6NywxMTExMTExMTExMSw0MDs0NCwxMSw0MDs2LDEsNDA7NSwxLDQwOzEsMTAxLDQwOzIsMSw0MDszLDEsNDA7NSwxLDQwOzgsMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDEsNDA7MTAyLDEsNDA6MjQ6Ojo1MTA4MDM2Mjg6MTc3NzU5NjU0OTo6OjE1ODIxMTcwODA6NjA0ODAwOjA6MTVmZjJkNmZhZTFmY2EyYjQxY2Y2YTZhZjNhOGQ0ODY3OmRlZmF1bHRfNTox; "
                "userid=510803628; u_name=%CD%ED%B0%B2Auk; escapename=%25u665a%25u5b89Auk; "
                "ticket=3853d08a581e56d99ad8bc76ea12a284; user_status=0; "
                "utk=e1101f21d7eb93eb75b8c4ba406060e5; sess_tk=98419724b8fd5da354cfb5678b"
            ),
            loop=True,
        )

        if df is None or df.empty:
            print("未获取到数据，请检查查询条件或Cookie是否有效。")
            return pd.DataFrame()

        print(f"成功获取到 {len(df)} 条数据")
        print(df.head())
        return df

    except Exception as exc:
        print(f"请求发生错误：{exc}")
        return pd.DataFrame()


def save_popularity_csv(df: pd.DataFrame) -> None:
    """Persist the full popularity list to CSV for backward compatibility."""
    old_file = "同花顺人气前200.csv"
    new_stocks_file = f"新增股票{pd.Timestamp.now().strftime('%Y-%m-%d %H-%M-%S')}.csv"

    if os.path.exists(old_file) and not df.empty:
        old_df = pd.read_csv(old_file, encoding="utf-8-sig")

        if len(old_df.columns) > 0 and len(df.columns) > 0:
            first_col_old = old_df.columns[0]
            first_col_new = df.columns[0]

            old_stocks = set(old_df[first_col_old].astype(str))
            new_stocks = set(df[first_col_new].astype(str))

            added_stocks = new_stocks - old_stocks

            if added_stocks:
                added_df = df[df[first_col_new].astype(str).isin(added_stocks)]
                added_df.to_csv(new_stocks_file, index=False, encoding="utf-8-sig")
                print(f"发现 {len(added_stocks)} 只新增股票，已保存到 '{new_stocks_file}'")
                print("新增股票列表：")
                print(added_df)
            else:
                print("没有发现新增股票")
        else:
            print("CSV文件格式异常，无法进行比较")
    elif not os.path.exists(old_file) and not df.empty:
        print(f"'{old_file}' 不存在，将直接保存新数据")

    if not df.empty:
        df.to_csv(old_file, index=False, encoding="utf-8-sig")
        print(f"最新数据已保存到 '{old_file}'")


async def upsert_stocks_from_df(df: pd.DataFrame) -> None:
    """Upsert stock pool into PostgreSQL."""
    if df.empty or len(df.columns) < 2:
        return

    first_col = df.columns[0]
    second_col = df.columns[1] if len(df.columns) > 1 else None

    from data_fetcher import normalize_stock_code

    stock_rows = []
    for _, row in df.iterrows():
        code = str(row[first_col]).strip()
        if not code:
            continue
        normalized = normalize_stock_code(code)
        name = str(row[second_col]).strip() if second_col else ""
        stock_rows.append({"stock_code": normalized, "stock_name": name})

    if not stock_rows:
        return

    db = StockDatabase()
    await db.initialize()
    try:
        await db.upsert_stocks(stock_rows)
        print(f"[popularity] 已入库 {len(stock_rows)} 只股票")
    finally:
        await db.close()


def main() -> None:
    df = get_top_200_popularity()
    if not df.empty:
        save_popularity_csv(df)


async def main_async() -> None:
    df = get_top_200_popularity()
    if not df.empty:
        save_popularity_csv(df)
        await upsert_stocks_from_df(df)


if __name__ == "__main__":
    main()
