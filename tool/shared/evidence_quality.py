"""统一评估足球 Agent 证据的新鲜度、来源优先级和结构化事实冲突。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any


def parse_iso_time(value: str | None) -> datetime | None:
    """解析 ISO 时间字符串；格式缺失或无效时返回 None。"""
    # 外部来源时间格式不稳定，验证层不能因单条坏时间戳而中断整个 Agent。
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def source_rank(source: str, url: str | None = None) -> int:
    """返回来源可靠性排序，数值越小代表越优先。"""
    # 结构化官方数据优先；网页中优先官方赛事/俱乐部，再是权威媒体，其他来源排后。
    if source == "football-data.org":
        return 0
    hostname = (url or "").lower()
    official_domains = (
        "premierleague.com", "uefa.com", "fifa.com", "thefa.com", "fcbarcelona.com",
        "realmadrid.com", "arsenal.com", "mancity.com", "liverpoolfc.com", "mlssoccer.com",
        "the-afc.com", "csl-china.com",
    )
    trusted_media_domains = ("bbc.com", "reuters.com", "apnews.com", "theathletic.com")
    if any(domain in hostname for domain in official_domains):
        return 1
    if any(domain in hostname for domain in trusted_media_domains):
        return 2
    if source == "Tavily web search":
        return 3
    return 4


def freshness_warning(evidence: dict[str, Any], now: datetime) -> str | None:
    """检查证据的查询时间是否过旧，并返回必要的风险提示。"""
    # retrieved_at 是我们实际拿到资料的时间，比网页发布时间更适合判断缓存是否陈旧。
    retrieved_at = parse_iso_time(evidence.get("retrieved_at"))
    if retrieved_at is None:
        return f"来源 {evidence.get('source', '未知')} 缺少可解析的 retrieved_at。"
    age = now - retrieved_at.astimezone(timezone.utc)
    if age > timedelta(hours=24):
        return f"来源 {evidence.get('source', '未知')} 的查询结果已超过 24 小时，可能过期。"
    return None


def extract_claims(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    """读取统一约定的 data.claims，供跨来源事实冲突检测使用。"""
    # claims 是后续工具逐步补充的可比较事实，例如同一比赛的开球时间或同一球员的所属球队。
    data = evidence.get("data", {})
    claims = data.get("claims", []) if isinstance(data, dict) else []
    valid_claims = []
    for claim in claims:
        if isinstance(claim, dict) and claim.get("claim_key") and "value" in claim:
            valid_claims.append(claim)
    return valid_claims


def detect_claim_conflicts(evidences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """找出相同 claim_key 下出现不同 value 的结构化事实冲突。"""
    # 不比较自由文本新闻标题；只有来源明确提供的 claims 才能自动判定冲突。
    grouped_claims: dict[str, list[dict[str, Any]]] = {}
    for evidence in evidences:
        for claim in extract_claims(evidence):
            item = {
                "value": claim["value"],
                "source": evidence.get("source", "未知"),
                "source_url": claim.get("source_url") or evidence.get("source_url"),
                "source_rank": source_rank(
                    evidence.get("source", "未知"),
                    claim.get("source_url") or evidence.get("source_url"),
                ),
            }
            grouped_claims.setdefault(claim["claim_key"], []).append(item)

    conflicts = []
    for claim_key, items in grouped_claims.items():
        unique_values = {json.dumps(item["value"], ensure_ascii=False, sort_keys=True) for item in items}
        if len(unique_values) > 1:
            ranked_items = sorted(items, key=lambda item: item["source_rank"])
            conflicts.append(
                {
                    "claim_key": claim_key,
                    "candidates": ranked_items,
                    "preferred_candidate": ranked_items[0],
                }
            )
    return conflicts


def assess_evidence_bundle(evidences: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总证据质量，输出可供 LangGraph 路由和最终回答使用的验证报告。"""
    # 统一在这里生成 warnings，避免每个 Node 都自行解释来源可靠性和时间风险。
    now = datetime.now(timezone.utc)
    warnings: list[str] = []
    # 研究草案等中间文本没有统一来源字段，不应被误当成可验证的外部证据。
    usable_evidence = [
        item for item in evidences if item.get("ok", True) and item.get("source")
    ]

    for evidence in usable_evidence:
        warning = freshness_warning(evidence, now)
        if warning:
            warnings.append(warning)

        if evidence.get("source") == "Tavily web search":
            results = evidence.get("data", {}).get("results", [])
            if not results:
                warnings.append("网页搜索未返回可引用结果。")

    conflicts = detect_claim_conflicts(usable_evidence)
    if conflicts:
        warnings.append("检测到不同来源对同一结构化事实给出不同值，最终回答应明确说明冲突。")

    return {
        "evidence_count": len(evidences),
        "usable_evidence_count": len(usable_evidence),
        "conflicts": conflicts,
        "warnings": warnings,
    }
