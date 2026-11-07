"""把不同来源的原始 Evidence Envelope 转成 Solver 与 Finalizer 可安全消费的研究上下文。"""

from __future__ import annotations

from typing import Any


def local_foundation_items(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    """从本地战术基础知识证据中取出可引用的 passages。"""
    # 只识别明确来源，避免将网页搜索结果误解析为本地概念笔记。
    if evidence.get("source") != "local_tactical_foundations":
        return []
    data = evidence.get("data", {})
    passages = data.get("passages", []) if isinstance(data, dict) else []
    return [item for item in passages if isinstance(item, dict)]


def build_citation_catalog(evidences: list[dict[str, Any]]) -> list[dict[str, str]]:
    """提取最终回答可展示的本地知识与网页资料引用目录。"""
    # 引用目录只保存标题、ID 和 URL 等展示字段，不把长网页正文或模型草案重复塞进 Finalizer。
    catalog: list[dict[str, str]] = []
    for evidence in evidences:
        for passage in local_foundation_items(evidence):
            catalog.append(
                {
                    "citation_id": str(passage.get("citation_id", "")),
                    "label": f"本地战术框架：{passage.get('title', '未命名条目')}",
                    "url": "",
                }
            )
        if evidence.get("source") == "Tavily web search":
            results = evidence.get("data", {}).get("results", [])
            for index, result in enumerate(results[:3], start=1):
                if isinstance(result, dict) and result.get("url"):
                    catalog.append(
                        {
                            "citation_id": f"web:{index}",
                            "label": str(result.get("title") or "网页资料"),
                            "url": str(result["url"]),
                        }
                    )
    return catalog


def build_research_evidence_context(
    evidences: list[dict[str, Any]],
    *,
    max_local_passages: int = 4,
    max_web_results: int = 3,
    max_text_length: int = 900,
) -> list[dict[str, Any]]:
    """压缩证据为模型上下文，保留结论所需字段并限制长文本带来的成本。"""
    # Collector 的原始结果可保留在 State；模型上下文只取必要摘要，避免网页正文无限增长。
    context: list[dict[str, Any]] = []
    for evidence in evidences:
        source = evidence.get("source", "unknown")
        if source == "local_tactical_foundations":
            passages = local_foundation_items(evidence)[:max_local_passages]
            context.append(
                {
                    "source": source,
                    "knowledge_scope": evidence.get("data", {}).get("knowledge_scope"),
                    "passages": [
                        {
                            "citation_id": item.get("citation_id"),
                            "title": item.get("title"),
                            "summary": item.get("summary"),
                            "text": str(item.get("text", ""))[:max_text_length],
                            "limitations": item.get("limitations"),
                        }
                        for item in passages
                    ],
                    "warnings": evidence.get("warnings", []),
                }
            )
            continue
        if source == "Tavily web search":
            results = evidence.get("data", {}).get("results", [])[:max_web_results]
            context.append(
                {
                    "source": source,
                    "results": [
                        {
                            "title": item.get("title"),
                            "url": item.get("url"),
                            "published_date": item.get("published_date"),
                            "content": str(item.get("content", ""))[:max_text_length],
                        }
                        for item in results
                        if isinstance(item, dict)
                    ],
                    "warnings": evidence.get("warnings", []),
                }
            )
            continue
        context.append(evidence)
    return context
