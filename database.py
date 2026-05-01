NEW_FILE_CODE
import asyncpg
from typing import List, Dict, Any, Optional
from datetime import datetime
from db_config import DATABASE_CONFIG


class StockDatabase:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(self):
        """初始化数据库连接池"""
        self.pool = await asyncpg.create_pool(
            host=DATABASE_CONFIG['host'],
            port=DATABASE_CONFIG['port'],
            database=DATABASE_CONFIG['database'],
            user=DATABASE_CONFIG['user'],
            password=DATABASE_CONFIG['password'],
            min_size=5,
            max_size=20
        )

    async def close(self):
        """关闭数据库连接池"""
        if self.pool:
            await self.pool.close()

    async def insert_stock(self, stock_code: str, stock_name: str, 
                          source_latest_price: Optional[float] = None,
                          source_pct_change: Optional[float] = None) -> int:
        """插入股票信息"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                """INSERT INTO stocks (stock_code, stock_name, source_latest_price, source_pct_change)
                   VALUES ($1, $2, $3, $4)
                   ON CONFLICT (stock_code, created_at) DO NOTHING
                   RETURNING id""",
                stock_code, stock_name, source_latest_price, source_pct_change
            )
            return result

    async def insert_news(self, news_list: List[Dict[str, Any]]) -> int:
        """批量插入新闻数据"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                count = 0
                for news in news_list:
                    await conn.execute(
                        """INSERT INTO news_data 
                           (stock_code, stock_name, keyword, title, content, published_at, source, url)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                        news.get('stock_code'),
                        news.get('stock_name'),
                        news.get('keyword'),
                        news.get('title'),
                        news.get('content'),
                        news.get('published_at'),
                        news.get('source'),
                        news.get('url')
                    )
                    count += 1
                return count

    async def insert_market_data(self, market_list: List[Dict[str, Any]]) -> int:
        """批量插入市场数据"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                count = 0
                for data in market_list:
                    await conn.execute(
                        """INSERT INTO market_data 
                           (stock_code, stock_name, latest_price, pct_change, change_amount,
                            open_price, high_price, low_price, prev_close, volume, amount,
                            volume_ratio, turnover_rate, amplitude, main_net_inflow,
                            main_net_inflow_ratio, fund_flow_date, benchmark_pct_change,
                            relative_strength_vs_index)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)""",
                        data.get('stock_code'),
                        data.get('stock_name'),
                        data.get('latest_price'),
                        data.get('pct_change'),
                        data.get('change_amount'),
                        data.get('open_price'),
                        data.get('high_price'),
                        data.get('low_price'),
                        data.get('prev_close'),
                        data.get('volume'),
                        data.get('amount'),
                        data.get('volume_ratio'),
                        data.get('turnover_rate'),
                        data.get('amplitude'),
                        data.get('main_net_inflow'),
                        data.get('main_net_inflow_ratio'),
                        data.get('fund_flow_date'),
                        data.get('benchmark_pct_change'),
                        data.get('relative_strength_vs_index')
                    )
                    count += 1
                return count

    async def insert_news_analysis(self, analysis_list: List[Dict[str, Any]]) -> int:
        """批量插入新闻分析结果"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                count = 0
                for analysis in analysis_list:
                    await conn.execute(
                        """INSERT INTO news_analysis 
                           (stock_code, event_types, text_event_label, text_score,
                            sentiment_strength, duration_tag, fact_support,
                            bullish_logic, bearish_logic, news_count)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                        analysis.get('stock_code'),
                        analysis.get('event_types'),
                        analysis.get('text_event_label'),
                        analysis.get('text_score'),
                        analysis.get('sentiment_strength'),
                        analysis.get('duration_tag'),
                        analysis.get('fact_support'),
                        analysis.get('bullish_logic'),
                        analysis.get('bearish_logic'),
                        analysis.get('news_count', 0)
                    )
                    count += 1
                return count

    async def insert_market_analysis(self, analysis_list: List[Dict[str, Any]]) -> int:
        """批量插入市场分析结果"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                count = 0
                for analysis in analysis_list:
                    await conn.execute(
                        """INSERT INTO market_analysis 
                           (stock_code, price_volume_signal, fund_flow_signal,
                            behavior_label, market_score)
                           VALUES ($1, $2, $3, $4, $5)""",
                        analysis.get('stock_code'),
                        analysis.get('price_volume_signal'),
                        analysis.get('fund_flow_signal'),
                        analysis.get('behavior_label'),
                        analysis.get('market_score')
                    )
                    count += 1
                return count

    async def insert_analysis_result(self, result_list: List[Dict[str, Any]]) -> int:
        """批量插入综合分析结果"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                count = 0
                for result in result_list:
                    await conn.execute(
                        """INSERT INTO analysis_result 
                           (stock_code, stock_name, event_types, text_event_label,
                            text_score, sentiment_strength, duration_tag, fact_support,
                            bullish_logic, bearish_logic, news_count,
                            price_volume_signal, fund_flow_signal, behavior_label,
                            market_score, integrated_score, decision)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)""",
                        result.get('stock_code'),
                        result.get('stock_name'),
                        result.get('event_types'),
                        result.get('text_event_label'),
                        result.get('text_score'),
                        result.get('sentiment_strength'),
                        result.get('duration_tag'),
                        result.get('fact_support'),
                        result.get('bullish_logic'),
                        result.get('bearish_logic'),
                        result.get('news_count', 0),
                        result.get('price_volume_signal'),
                        result.get('fund_flow_signal'),
                        result.get('behavior_label'),
                        result.get('market_score'),
                        result.get('integrated_score'),
                        result.get('decision')
                    )
                    count += 1
                return count

    async def get_latest_stocks(self, limit: int = 200) -> List[Dict[str, Any]]:
        """获取最新的股票列表"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT stock_code, stock_name, source_latest_price, source_pct_change
                   FROM stocks
                   ORDER BY created_at DESC
                   LIMIT $1""",
                limit
            )
            return [dict(row) for row in rows]

    async def get_news_by_stock(self, stock_code: str, limit: int = 20) -> List[Dict[str, Any]]:
        """获取指定股票的新闻"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT * FROM news_data
                   WHERE stock_code = $1
                   ORDER BY published_at DESC
                   LIMIT $2""",
                stock_code, limit
            )
            return [dict(row) for row in rows]

    async def get_market_data_by_stock(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """获取指定股票的市场数据"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT * FROM market_data
                   WHERE stock_code = $1
                   ORDER BY fetched_at DESC
                   LIMIT 1""",
                stock_code
            )
            return dict(row) if row else None

    async def clear_old_data(self, days: int = 30):
        """清理旧数据"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """DELETE FROM analysis_result WHERE created_at < NOW() - INTERVAL '$1 days'""",
                days
            )
            await conn.execute(
                """DELETE FROM news_analysis WHERE analyzed_at < NOW() - INTERVAL '$1 days'""",
                days
            )
            await conn.execute(
                """DELETE FROM market_analysis WHERE analyzed_at < NOW() - INTERVAL '$1 days'""",
                days
            )
            await conn.execute(
                """DELETE FROM news_data WHERE fetched_at < NOW() - INTERVAL '$1 days'""",
                days
            )
            await conn.execute(
                """DELETE FROM market_data WHERE fetched_at < NOW() - INTERVAL '$1 days'""",
                days
            )