from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd
import yaml

from stock_service.domain.services.stock_utils import normalize_stock_code


# ── 加载配置 ──

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "analysis_rules.yaml"

with open(_CONFIG_PATH, encoding="utf-8") as f:
    _CONFIG = yaml.safe_load(f)

# 从配置中读取
WEIGHTS = _CONFIG["weights"]
POSITIVE_WORDS: list[str] = _CONFIG["positive_words"]
NEGATIVE_WORDS: list[str] = _CONFIG["negative_words"]
KEYWORD_HIT_SCORE: float = _CONFIG["keyword_hit_score"]
SENTIMENT_THRESHOLDS = _CONFIG["sentiment_thresholds"]
DURATION_KEYWORDS: list[str] = _CONFIG["duration_keywords"]
FACT_SUPPORT_KEYWORDS: list[str] = _CONFIG["fact_support_keywords"]
EVENT_PATTERNS: dict[str, dict] = _CONFIG["event_patterns"]
MARKET_BEHAVIOR = _CONFIG["market_behavior"]
DECISION_RULES = _CONFIG["decision_rules"]


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
    sentiment_score = event_score + positive_hits * KEYWORD_HIT_SCORE - negative_hits * KEYWORD_HIT_SCORE
    if sentiment_score >= SENTIMENT_THRESHOLDS["strong_positive"]:
        sentiment_strength = "强"
    elif sentiment_score >= SENTIMENT_THRESHOLDS["medium_positive"]:
        sentiment_strength = "中"
    elif sentiment_score <= SENTIMENT_THRESHOLDS["strong_negative"]:
        sentiment_strength = "强"
    elif sentiment_score <= SENTIMENT_THRESHOLDS["medium_negative"]:
        sentiment_strength = "中"
    else:
        sentiment_strength = "弱"
    duration_tag = "长期" if any(word in text for word in DURATION_KEYWORDS) else "短期"
    fact_support = "较强" if any(word in text for word in FACT_SUPPORT_KEYWORDS) else "一般"
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
    return pd.Series(non_null).mode().iloc[0] if non_null else "未知"


def summarize_strength(values: list[object]) -> str:
    order = {"弱": 1, "中": 2, "强": 3}
    non_null = [str(v) for v in values if pd.notna(v)]
    return max(non_null, key=lambda item: order.get(item, 0)) if non_null else "未知"


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


def aggregate_news(news_df: pd.DataFrame) -> pd.DataFrame:
    if news_df.empty:
        return pd.DataFrame(columns=["stock_code", "event_types", "text_event_label", "text_score", "sentiment_strength", "duration_tag", "fact_support", "bullish_logic", "bearish_logic", "news_count"])
    work_df = news_df.copy()
    work_df["stock_code"] = work_df["stock_code"].map(normalize_stock_code)
    work_df["combined_text"] = (work_df["title"].fillna("").astype(str) + " " + work_df["content"].fillna("").astype(str)).str.strip()
    rows: list[dict[str, object]] = []
    for _, row in work_df.iterrows():
        event = analyze_text_event(str(row["combined_text"]))
        rows.append({
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
    analyzed_df = pd.DataFrame(rows)
    result = analyzed_df.groupby("stock_code", as_index=False).agg(
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
    result["text_score"] = result["text_score"].round(2)
    return result


def analyze_news_records(news_df: pd.DataFrame) -> pd.DataFrame:
    if news_df.empty:
        return pd.DataFrame(columns=["article_id", "stock_code", "event_type", "event_label", "event_score", "sentiment_score", "sentiment_strength", "duration_tag", "fact_support", "bullish_logic", "bearish_logic", "analysis_json"])
    work_df = news_df.copy()
    work_df["stock_code"] = work_df["stock_code"].map(normalize_stock_code)
    work_df["combined_text"] = (work_df["title"].fillna("").astype(str) + " " + work_df["content"].fillna("").astype(str)).str.strip()
    rows: list[dict[str, object]] = []
    for _, row in work_df.iterrows():
        event = analyze_text_event(str(row["combined_text"]))
        rows.append({
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
            "analysis_json": event.__dict__,
        })
    return pd.DataFrame(rows)


def analyze_market_behavior(market_df: pd.DataFrame) -> pd.DataFrame:
    if market_df.empty:
        return pd.DataFrame(columns=["stock_code", "price_volume_signal", "fund_flow_signal", "behavior_label", "market_score"])
    work_df = market_df.copy()
    work_df["stock_code"] = work_df["stock_code"].map(normalize_stock_code)
    for column in ["pct_change", "volume_ratio", "turnover_rate", "amplitude", "main_net_inflow", "relative_strength_vs_index"]:
        work_df[column] = pd.to_numeric(work_df[column], errors="coerce")

    cfg = MARKET_BEHAVIOR
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

        ar = cfg["active_rise"]
        if pd.notna(pct_change) and pd.notna(volume_ratio) and pd.notna(relative_strength) and pct_change > ar["pct_change_min"] and volume_ratio > ar["volume_ratio_min"] and relative_strength > ar["relative_strength_min"]:
            price_volume_signal = "主动性上涨"
            score += ar["score"]
        else:
            pr = cfg["passive_rise"]
            if pd.notna(pct_change) and pd.notna(relative_strength) and pct_change > pr["pct_change_min"] and relative_strength <= pr["relative_strength_max"]:
                price_volume_signal = "被动性跟涨"
                score += pr["score"]

        hs = cfg["high_volume_stagnation"]
        if pd.notna(turnover_rate) and pd.notna(pct_change) and turnover_rate > hs["turnover_rate_min"] and pct_change < hs["pct_change_max"]:
            price_volume_signal = "高位巨量滞涨"
            score += hs["score"]

        ff = cfg["fund_flow"]
        if pd.notna(main_net_inflow) and main_net_inflow > 0:
            fund_flow_signal = "主力净流入"
            score += ff["inflow_score"]
        elif pd.notna(main_net_inflow) and main_net_inflow < 0:
            fund_flow_signal = "主力净流出"
            score += ff["outflow_score"]

        beh = cfg["behaviors"]
        if pd.notna(pct_change) and pd.notna(main_net_inflow) and pct_change < beh["short_cover"]["pct_change_max"] and main_net_inflow > 0:
            behavior_label = "空头回补"
            score += beh["short_cover"]["score"]
        elif pd.notna(pct_change) and pd.notna(main_net_inflow) and pct_change > beh["profit_taking"]["pct_change_min"] and main_net_inflow < 0:
            behavior_label = "获利回吐"
            score += beh["profit_taking"]["score"]
        elif pd.notna(pct_change) and pd.notna(main_net_inflow) and pct_change < beh["short_dominant"]["pct_change_max"] and main_net_inflow < 0:
            behavior_label = "做空主导"
            score += beh["short_dominant"]["score"]
        elif pd.notna(pct_change) and pd.notna(main_net_inflow) and pct_change > beh["long_dominant"]["pct_change_min"] and main_net_inflow > 0:
            behavior_label = "做多主导"
            score += beh["long_dominant"]["score"]

        rows.append({"stock_code": row["stock_code"], "price_volume_signal": price_volume_signal, "fund_flow_signal": fund_flow_signal, "behavior_label": behavior_label, "market_score": round(score, 2)})
    return pd.DataFrame(rows)


def synthesize_decision(row: pd.Series) -> str:
    text_label = row.get("text_event_label", "中性")
    market_behavior = row.get("behavior_label", "中性")
    fund_signal = row.get("fund_flow_signal", "资金观望")
    integrated_score = row.get("integrated_score", 0)

    dr = DECISION_RULES
    if text_label == "利好" and fund_signal == "主力净流入" and market_behavior in {"做多主导", "中性"}:
        return "大概率真利好，人气上升有资金支撑"
    if text_label == "利好" and fund_signal == "主力净流出":
        return "警惕利好出尽，主力可能借机兑现"
    if text_label == "利空" and market_behavior == "空头回补":
        return "可能属于利空出尽，存在资金抄底迹象"
    if text_label == "利空" and market_behavior == "做空主导":
        return "偏真利空，资金面仍在恶化"
    if integrated_score >= dr["strong_buy"]["min_integrated_score"]:
        return dr["strong_buy"]["message"]
    if integrated_score <= dr["strong_sell"]["max_integrated_score"]:
        return dr["strong_sell"]["message"]
    return "信号分歧，等待更多确认"
