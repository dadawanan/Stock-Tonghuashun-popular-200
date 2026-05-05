from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from database import StockDatabase


EVENT_PATTERNS: dict[str, dict[str, object]] = {
    "major_order": {
        "keywords": ["中标", "大单", "订单", "签约", "拿下项目", "合作框架"],
        "event_label": "利好",
        "event_score": 2.0,
        "bullish_logic": "订单或合同提升收入预期，说明业务拓展被市场验证。",
        "bearish_logic": "若订单兑现周期过长，短期业绩和现金流未必立刻改善。",
    },
    "policy_support": {
        "keywords": ["政策支持", "补贴", "纳入目录", "战略合作", "产业扶持"],
        "event_label": "利好",
        "event_score": 1.5,
        "bullish_logic": "政策或产业资源倾斜有利于估值抬升。",
        "bearish_logic": "政策催化若缺少基本面落地，容易变成情绪交易。",
    },
    "earnings_growth": {
        "keywords": ["业绩增长", "净利润增长", "扭亏", "预增", "超预期"],
        "event_label": "利好",
        "event_score": 2.0,
        "bullish_logic": "财务指标改善通常更容易获得持续性资金认可。",
        "bearish_logic": "若增长来自非经常性收益，持续性会被打折。",
    },
    "technology_breakthrough": {
        "keywords": ["新品发布", "技术突破", "专利", "量产", "发布会"],
        "event_label": "中性偏多",
        "event_score": 1.0,
        "bullish_logic": "技术领先可能打开新市场空间。",
        "bearish_logic": "研发投入和商业化周期可能压制短期利润。",
    },
    "management_risk": {
        "keywords": ["被查", "调查", "立案", "违规", "诉讼", "减持"],
        "event_label": "利空",
        "event_score": -2.0,
        "bullish_logic": "若风险已被充分定价，后续可能迎来情绪修复。",
        "bearish_logic": "治理风险会削弱市场信任并压制估值。",
    },
    "supply_chain_risk": {
        "keywords": ["火灾", "停产", "事故", "召回", "供应中断", "断供"],
        "event_label": "利空",
        "event_score": -1.5,
        "bullish_logic": "若影响范围有限，错杀后可能出现修复。",
        "bearish_logic": "供应链扰动可能传导到产能、交付和盈利。",
    },
}

POSITIVE_WORDS = ["增长", "提升", "超预期", "创新高", "强劲", "加速", "回暖", "改善"]
NEGATIVE_WORDS = ["下滑", "亏损", "承压", "风险", "恶化", "减值", "滞涨", "波动"]


@dataclass
class EventAnalysis:
    event_type: str
    event_label: str
    event_score: float
    sentiment_score: float
    sentiment_strength: str
    duration_tag: str
    fact_support: str
    bullish_logic: str
    bearish_logic: str


def normalize_stock_code(value: object) -> str:
    text = str(value).strip()
    if "." in text:
        return text.upper()
    if text.isdigit() and len(text) == 6:
        suffix = ".SH" if text.startswith(("6", "9")) else ".SZ"
        return f"{text}{suffix}"
    return text.upper()


def analyze_text_event(text: str) -> EventAnalysis:
    text = text or ""
    event_type = "other"
    event_label = "中性"
    event_score = 0.0
    bullish_logic = "暂无明显看多逻辑。"
    bearish_logic = "暂无明显看空逻辑。"

    for candidate, config in EVENT_PATTERNS.items():
        if any(keyword in text for keyword in config["keywords"]):
            event_type = candidate
            event_label = str(config["event_label"])
            event_score = float(config["event_score"])
            bullish_logic = str(config["bullish_logic"])
            bearish_logic = str(config["bearish_logic"])
            break

    positive_hits = sum(keyword in text for keyword in POSITIVE_WORDS)
    negative_hits = sum(keyword in text for keyword in NEGATIVE_WORDS)
    sentiment_score = event_score + positive_hits * 0.4 - negative_hits * 0.4

    if sentiment_score >= 1.8:
        sentiment_strength = "强"
    elif sentiment_score >= 0.6:
        sentiment_strength = "中"
    elif sentiment_score <= -1.8:
        sentiment_strength = "强"
    elif sentiment_score <= -0.6:
        sentiment_strength = "中"
    else:
        sentiment_strength = "弱"

    duration_tag = "长期" if any(word in text for word in ["战略", "产能", "订单", "业绩", "量产"]) else "短期"
    fact_support = "较强" if any(word in text for word in ["公告", "财报", "中标", "合同", "数据"]) else "一般"

    return EventAnalysis(
        event_type=event_type,
        event_label=event_label,
        event_score=event_score,
        sentiment_score=round(sentiment_score, 2),
        sentiment_strength=sentiment_strength,
        duration_tag=duration_tag,
        fact_support=fact_support,
        bullish_logic=bullish_logic,
        bearish_logic=bearish_logic,
    )


def aggregate_news(news_df: pd.DataFrame) -> pd.DataFrame:
    if news_df.empty:
        return pd.DataFrame(
            columns=[
                "stock_code", "event_types", "text_event_label", "text_score",
                "sentiment_strength", "duration_tag", "fact_support",
                "bullish_logic", "bearish_logic", "news_count",
            ]
        )

    work_df = news_df.copy()
    work_df["stock_code"] = work_df["stock_code"].map(normalize_stock_code)
    work_df["combined_text"] = (
        work_df["title"].fillna("").astype(str) + " " + work_df["content"].fillna("").astype(str)
    ).str.strip()

    analysis_rows: list[dict[str, object]] = []
    for _, row in work_df.iterrows():
        event = analyze_text_event(str(row["combined_text"]))
        analysis_rows.append({
            "stock_code": row["stock_code"],
            "event_type": event.event_type,
            "event_label": event.event_label,
            "event_score": event.event_score,
            "sentiment_score": event.sentiment_score,
            "sentiment_strength": event.sentiment_strength,
            "duration_tag": event.duration_tag,
            "fact_support": event.fact_support,
            "bullish_logic": event.bullish_logic,
            "bearish_logic": event.bearish_logic,
        })

    analyzed_df = pd.DataFrame(analysis_rows)
    if analyzed_df.empty:
        return pd.DataFrame()

    result = (
        analyzed_df.groupby("stock_code", as_index=False)
        .agg(
            event_types=("event_type", lambda x: " | ".join(sorted(set(str(v) for v in x if v)))),
            text_event_label=("event_label", lambda x: summarize_labels(list(x))),
            text_score=("sentiment_score", "mean"),
            sentiment_strength=("sentiment_strength", lambda x: summarize_strength(list(x))),
            duration_tag=("duration_tag", lambda x: summarize_majority(list(x))),
            fact_support=("fact_support", lambda x: summarize_majority(list(x))),
            bullish_logic=("bullish_logic", lambda x: " | ".join(unique_keep_order(x))),
            bearish_logic=("bearish_logic", lambda x: " | ".join(unique_keep_order(x))),
            news_count=("event_type", "count"),
        )
    )
    result["text_score"] = result["text_score"].round(2)
    return result


def analyze_news_records(news_df: pd.DataFrame) -> pd.DataFrame:
    if news_df.empty:
        return pd.DataFrame(
            columns=[
                "article_id",
                "stock_code",
                "event_type",
                "event_label",
                "event_score",
                "sentiment_score",
                "sentiment_strength",
                "duration_tag",
                "fact_support",
                "bullish_logic",
                "bearish_logic",
                "analysis_json",
            ]
        )

    work_df = news_df.copy()
    work_df["stock_code"] = work_df["stock_code"].map(normalize_stock_code)
    work_df["combined_text"] = (
        work_df["title"].fillna("").astype(str) + " " + work_df["content"].fillna("").astype(str)
    ).str.strip()

    rows: list[dict[str, object]] = []
    for _, row in work_df.iterrows():
        event = analyze_text_event(str(row["combined_text"]))
        rows.append(
            {
                "article_id": row.get("id"),
                "stock_code": row["stock_code"],
                "event_type": event.event_type,
                "event_label": event.event_label,
                "event_score": event.event_score,
                "sentiment_score": event.sentiment_score,
                "sentiment_strength": event.sentiment_strength,
                "duration_tag": event.duration_tag,
                "fact_support": event.fact_support,
                "bullish_logic": event.bullish_logic,
                "bearish_logic": event.bearish_logic,
                "analysis_json": {
                    "event_type": event.event_type,
                    "event_label": event.event_label,
                    "event_score": event.event_score,
                    "sentiment_score": event.sentiment_score,
                    "sentiment_strength": event.sentiment_strength,
                    "duration_tag": event.duration_tag,
                    "fact_support": event.fact_support,
                    "bullish_logic": event.bullish_logic,
                    "bearish_logic": event.bearish_logic,
                },
            }
        )
    return pd.DataFrame(rows)


def unique_keep_order(values: Iterable[object]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        if text not in seen:
            seen.add(text)
            result.append(text)
    return result


def summarize_majority(values: list[object]) -> str:
    non_null = [str(v) for v in values if pd.notna(v)]
    if not non_null:
        return "未知"
    return pd.Series(non_null).mode().iloc[0]


def summarize_strength(values: list[object]) -> str:
    order = {"弱": 1, "中": 2, "强": 3}
    non_null = [str(v) for v in values if pd.notna(v)]
    if not non_null:
        return "未知"
    return max(non_null, key=lambda item: order.get(item, 0))


def summarize_labels(values: list[object]) -> str:
    non_null = [str(v) for v in values if pd.notna(v)]
    if not non_null:
        return "中性"
    positive = sum(label in {"利好", "中性偏多"} for label in non_null)
    negative = sum(label == "利空" for label in non_null)
    if positive > negative:
        return "利好"
    if negative > positive:
        return "利空"
    return "中性"


def analyze_market_behavior(market_df: pd.DataFrame) -> pd.DataFrame:
    if market_df.empty:
        return pd.DataFrame(
            columns=[
                "stock_code", "price_volume_signal", "fund_flow_signal",
                "behavior_label", "market_score",
            ]
        )

    work_df = market_df.copy()
    work_df["stock_code"] = work_df["stock_code"].map(normalize_stock_code)

    numeric_columns = [
        "pct_change", "volume_ratio", "turnover_rate", "amplitude",
        "main_net_inflow", "relative_strength_vs_index",
    ]
    for column in numeric_columns:
        work_df[column] = pd.to_numeric(work_df[column], errors="coerce")

    rows: list[dict[str, object]] = []
    for _, row in work_df.iterrows():
        score = 0.0
        price_volume_signal = "数据不足"
        fund_flow_signal = "资金观望"
        behavior_label = "中性"
        pct_change = row["pct_change"]
        volume_ratio = row["volume_ratio"]
        turnover_rate = row["turnover_rate"]
        main_net_inflow = row["main_net_inflow"]
        relative_strength = row["relative_strength_vs_index"]

        if pd.notna(pct_change) and pd.notna(volume_ratio) and pd.notna(relative_strength):
            price_volume_signal = "普通波动"

        if (pd.notna(pct_change) and pd.notna(volume_ratio) and pd.notna(relative_strength)
                and pct_change > 3 and volume_ratio > 1.5 and relative_strength > 1):
            price_volume_signal = "主动性上涨"
            score += 2.0
        elif pd.notna(pct_change) and pd.notna(relative_strength) and pct_change > 0 and relative_strength <= 0.5:
            price_volume_signal = "被动性跟涨"
            score += 0.5

        if pd.notna(turnover_rate) and pd.notna(pct_change) and turnover_rate > 20 and pct_change < 1:
            price_volume_signal = "高位巨量滞涨"
            score -= 1.5

        if pd.notna(main_net_inflow) and main_net_inflow > 0:
            fund_flow_signal = "主力净流入"
            score += 1.5
        elif pd.notna(main_net_inflow) and main_net_inflow < 0:
            fund_flow_signal = "主力净流出"
            score -= 1.5

        if pd.notna(pct_change) and pd.notna(main_net_inflow) and pct_change < -3 and main_net_inflow > 0:
            behavior_label = "空头回补"
            score += 1.0
        elif pd.notna(pct_change) and pd.notna(main_net_inflow) and pct_change > 3 and main_net_inflow < 0:
            behavior_label = "获利回吐"
            score -= 1.0
        elif pd.notna(pct_change) and pd.notna(main_net_inflow) and pct_change < -3 and main_net_inflow < 0:
            behavior_label = "做空主导"
            score -= 2.0
        elif pd.notna(pct_change) and pd.notna(main_net_inflow) and pct_change > 3 and main_net_inflow > 0:
            behavior_label = "做多主导"
            score += 2.0

        rows.append({
            "stock_code": row["stock_code"],
            "price_volume_signal": price_volume_signal,
            "fund_flow_signal": fund_flow_signal,
            "behavior_label": behavior_label,
            "market_score": round(score, 2),
        })

    return pd.DataFrame(rows)


def synthesize_decision(row: pd.Series) -> str:
    text_label = row.get("text_event_label", "中性")
    market_behavior = row.get("behavior_label", "中性")
    fund_signal = row.get("fund_flow_signal", "资金观望")

    if text_label == "利好" and fund_signal == "主力净流入" and market_behavior in {"做多主导", "中性"}:
        return "大概率真利好，人气上升有资金支撑"
    if text_label == "利好" and fund_signal == "主力净流出":
        return "警惕利好出尽，主力可能借机兑现"
    if text_label == "利空" and market_behavior == "空头回补":
        return "可能属于利空出尽，存在资金抄底迹象"
    if text_label == "利空" and market_behavior == "做空主导":
        return "偏真利空，资金面仍在恶化"
    if row.get("integrated_score", 0) >= 2.5:
        return "偏强，建议纳入重点观察"
    if row.get("integrated_score", 0) <= -1.5:
        return "偏弱，建议谨慎"
    return "信号分歧，等待更多确认"


async def run_analysis(
    db: StockDatabase,
    stock_codes: list[str] | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    stocks = await db.get_all_stocks()
    if not stocks:
        raise ValueError("数据库中没有股票数据，请先运行 data_fetcher.py")

    base_df = pd.DataFrame(stocks)
    news_df = pd.DataFrame(await db.get_all_news())
    market_df = pd.DataFrame(await db.get_market_data())

    if stock_codes:
        normalized_codes = {normalize_stock_code(code) for code in stock_codes}
        base_df = base_df[base_df["stock_code"].isin(normalized_codes)].copy()
        if not news_df.empty:
            news_df = news_df[news_df["stock_code"].map(normalize_stock_code).isin(normalized_codes)].copy()
        if not market_df.empty:
            market_df = market_df[market_df["stock_code"].map(normalize_stock_code).isin(normalized_codes)].copy()

    if base_df.empty:
        raise ValueError("待分析股票列表为空，无法执行分析")

    news_analysis_df = analyze_news_records(news_df)
    news_result = aggregate_news(news_df)
    market_result = analyze_market_behavior(market_df)

    result = base_df.merge(news_result, on="stock_code", how="left").merge(market_result, on="stock_code", how="left")

    result["text_score"] = pd.to_numeric(result["text_score"], errors="coerce").fillna(0.0)
    result["market_score"] = pd.to_numeric(result["market_score"], errors="coerce").fillna(0.0)
    result["integrated_score"] = (result["text_score"] * 0.55 + result["market_score"] * 0.45).round(2)
    result["decision"] = result.apply(synthesize_decision, axis=1)

    fill_columns = [
        "event_types", "text_event_label", "sentiment_strength", "duration_tag",
        "fact_support", "bullish_logic", "bearish_logic",
        "price_volume_signal", "fund_flow_signal", "behavior_label",
    ]
    for column in fill_columns:
        result[column] = result[column].fillna("暂无数据")
    result["news_count"] = pd.to_numeric(result["news_count"], errors="coerce").fillna(0).astype(int)

    result = result.sort_values(["integrated_score", "news_count"], ascending=[False, False])
    result.attrs["news_analysis_rows"] = news_analysis_df.to_dict("records")
    result.attrs["latest_trade_date"] = market_df["trade_date"].dropna().max() if "trade_date" in market_df.columns and not market_df.empty else None
    result.attrs["latest_snapshot_time"] = market_df["snapshot_time"].dropna().max() if "snapshot_time" in market_df.columns and not market_df.empty else None
    return result.to_dict("records"), result.attrs


async def run_and_store(db: StockDatabase, stock_codes: list[str] | None = None) -> None:
    run_id = await db.create_pipeline_run(run_type="analyze", source="rule")
    try:
        results, meta = await run_analysis(db, stock_codes=stock_codes)
        news_analysis_rows = meta.get("news_analysis_rows", [])
        article_ids = [row["article_id"] for row in news_analysis_rows if row.get("article_id") is not None]
        if news_analysis_rows:
            await db.replace_news_analysis_batch(run_id, news_analysis_rows, article_ids)

        trade_date = meta.get("latest_trade_date")
        snapshot_time = meta.get("latest_snapshot_time")
        for row in results:
            row["run_id"] = run_id
            row["trade_date"] = trade_date
            row["snapshot_time"] = snapshot_time
            row["reasoning_json"] = {
                "text_event_label": row.get("text_event_label"),
                "fund_flow_signal": row.get("fund_flow_signal"),
                "behavior_label": row.get("behavior_label"),
                "decision": row.get("decision"),
            }

        count = await db.insert_stock_analysis_batch(results)
        await db.complete_pipeline_run(
            run_id,
            status="success",
            analysis_count=count,
        )
        print(f"[analysis] 写入 {count} 条分析结果")
    except Exception as exc:
        await db.complete_pipeline_run(run_id, status="failed", error_message=str(exc))
        raise


def build_parser() -> None:
    pass
