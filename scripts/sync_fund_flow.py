#!/usr/bin/env python3
"""
资金流向同步脚本（Playwright 版）
使用 Playwright 从东方财富网页抓取资金流向数据
"""

import asyncio
import json
from datetime import datetime, date
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("❌ 请先安装 playwright: pip install playwright && playwright install chromium")
    exit(1)

try:
    import asyncpg
except ImportError:
    print("❌ 请先安装 asyncpg: pip install asyncpg")
    exit(1)


# 数据库配置
DB_CONFIG = {
    "host": "101.35.255.200",
    "port": 55443,
    "database": "stock_db",
    "user": "postgresql",
    "password": "3C3TaF3t8HFtfTtPZBUK",
}

# 数据目录
DATA_DIR = Path(__file__).parent / "fund_flow_data"


async def scrape_fund_flow_with_playwright(stock_codes: list[dict]) -> dict:
    """使用 Playwright 从东方财富网页抓取资金流向"""
    results = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        for item in stock_codes:
            code = item["code"]
            name = item["name"]

            try:
                digits = code.split('.')[0]
                url = f"https://data.eastmoney.com/zjlx/{digits}.html"

                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(1.5)

                # 从页面提取资金数据
                data = await page.evaluate("""() => {
                    const result = {};
                    const body = document.body.innerText || '';

                    // 提取主力净流入
                    const patterns = [
                        ['main_net_inflow', /主力净流入[：:]*\\s*([\\d,.+-]+\\s*[万亿]?)/i],
                        ['main_net_inflow_ratio', /主力净占比[：:]*\\s*([\\d,.+-]+%?)/i],
                    ];

                    for (const [key, regex] of patterns) {
                        const match = body.match(regex);
                        if (match) result[key] = match[1].trim();
                    }

                    return result;
                }""")

                # 解析数据
                main_inflow_str = data.get('main_net_inflow', '0')
                ratio_str = data.get('main_net_inflow_ratio', '0')

                main_inflow = parse_amount(main_inflow_str)
                ratio = parse_percent(ratio_str)

                results[code] = {
                    "stock_code": code,
                    "stock_name": name,
                    "main_net_inflow": main_inflow,
                    "main_net_inflow_ratio": ratio,
                    "fund_flow_date": date.today().isoformat(),
                    "source": "eastmoney_web",
                }

                print(f"  ✅ {name}({code}): 主力净流入 {main_inflow/10000:.0f}万 ({ratio:.2f}%)")

            except Exception as e:
                print(f"  ❌ {name}({code}): {e}")
                results[code] = {
                    "stock_code": code,
                    "stock_name": name,
                    "main_net_inflow": 0,
                    "main_net_inflow_ratio": 0,
                    "fund_flow_date": date.today().isoformat(),
                    "source": "eastmoney_web",
                    "error": str(e),
                }

            await asyncio.sleep(0.5)

        await browser.close()

    return results


def parse_amount(text: str) -> float:
    """解析金额"""
    if not text:
        return 0.0

    text = text.replace(',', '').replace(' ', '')
    sign = 1
    if '-' in text:
        sign = -1
        text = text.replace('-', '')
    elif '+' in text:
        text = text.replace('+', '')

    import re
    num_match = re.search(r'([\d.]+)', text)
    if not num_match:
        return 0.0

    num = float(num_match.group(1))
    if '亿' in text:
        num *= 100000000
    elif '万' in text:
        num *= 10000

    return sign * num


def parse_percent(text: str) -> float:
    """解析百分比"""
    if not text:
        return 0.0
    text = text.replace('%', '').replace(' ', '')
    import re
    match = re.search(r'([+-]?[\d.]+)', text)
    return float(match.group(1)) if match else 0.0


async def save_to_database(fund_data: dict):
    """保存到数据库"""
    pool = await asyncpg.create_pool(**DB_CONFIG, min_size=2, max_size=5)

    try:
        today = date.today()
        updated = 0

        for code, data in fund_data.items():
            if "main_net_inflow" not in data or "error" in data:
                continue

            try:
                # 先尝试更新
                query = """
                    UPDATE market_snapshot
                    SET main_net_inflow = $1,
                        main_net_inflow_ratio = $2,
                        fund_flow_date = $3
                    WHERE stock_code = $4
                    AND trade_date = $5
                """
                result = await pool.execute(
                    query,
                    data["main_net_inflow"],
                    data.get("main_net_inflow_ratio", 0),
                    today,
                    code,
                    today,
                )

                # 如果没有更新，尝试插入（忽略外键约束错误）
                if result == "UPDATE 0":
                    try:
                        insert_query = """
                            INSERT INTO market_snapshot
                            (stock_code, stock_name, trade_date, main_net_inflow, main_net_inflow_ratio, fund_flow_date, source)
                            VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """
                        await pool.execute(
                            insert_query,
                            code,
                            data.get("stock_name", ""),
                            today,
                            data["main_net_inflow"],
                            data.get("main_net_inflow_ratio", 0),
                            today,
                            "eastmoney_web",
                        )
                    except asyncpg.ForeignKeyViolationError:
                        # 股票代码不在 stock_master 中，跳过
                        pass

                updated += 1

            except Exception as e:
                print(f"  ❌ 更新 {code} 失败: {e}")

        return updated

    finally:
        await pool.close()


async def main():
    """主函数"""
    print("=" * 60)
    print("📊 资金流向数据同步 (Playwright 版)")
    print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    DATA_DIR.mkdir(exist_ok=True)

    # 热门股票列表
    hot_stocks = [
        {"code": "000001.SZ", "name": "平安银行"},
        {"code": "600036.SH", "name": "招商银行"},
        {"code": "000858.SZ", "name": "五粮液"},
        {"code": "601318.SH", "name": "中国平安"},
        {"code": "000333.SZ", "name": "美的集团"},
        {"code": "000725.SZ", "name": "京东方A"},
        {"code": "600519.SH", "name": "贵州茅台"},
        {"code": "002415.SZ", "name": "海康威视"},
        {"code": "600031.SH", "name": "三一重工"},
        {"code": "000063.SZ", "name": "中兴通讯"},
    ]

    print(f"\n📋 需要抓取 {len(hot_stocks)} 只股票的资金数据")

    # 抓取数据
    print("\n🌐 从东方财富网页抓取资金流向...")
    fund_data = await scrape_fund_flow_with_playwright(hot_stocks)

    # 保存到本地文件
    today = datetime.now().strftime('%Y%m%d')
    output_file = DATA_DIR / f"fund_flow_{today}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(fund_data, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n💾 本地保存: {output_file}")

    # 保存到数据库
    print("\n💾 更新数据库...")
    updated = await save_to_database(fund_data)
    print(f"   ✅ 更新了 {updated} 条记录")

    print("\n" + "=" * 60)
    print("✅ 同步完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
