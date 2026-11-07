"""从项目自带的战术基础笔记中检索可供研究流程引用的概念证据。"""

from __future__ import annotations

from typing import Any

from tool.shared.data_models import build_tool_success
from knowledge_base.retrieval.advanced_tactical_retriever import retrieve_advanced_tactical_knowledge


def retrieve_tactical_foundations(query: str, top_k: int = 4) -> list[dict[str, Any]]:
    """返回最相关的本地战术概念条目，并保留可展示给用户的引用标识。"""
    # 不命中时返回空列表而非硬凑资料，避免 Solver 把不相关的基础概念当成比赛证据。
    # 底层检索器负责切块、加载索引和评分；本层只处理 Agent 所需 Evidence Envelope 字段。
    ranked = retrieve_advanced_tactical_knowledge(query, top_k=top_k)
    passages = []
    for item in ranked:
        passages.append(
            {
                "citation_id": item.citation_id,
                "title": item.metadata.get("title", "未命名战术资料"),
                "text": item.text,
                "summary": item.metadata.get("summary", ""),
                "limitations": item.metadata.get("limitations", ""),
                "score": item.score,
                "metadata": {
                    "chunk_id": item.citation_id,
                    "tags": item.metadata.get("tags", []),
                    "source_type": "curated_local_foundation",
                    "retrieval_method": item.metadata.get("retrieval_method"),
                },
            }
        )
    return passages


def search_local_tactical_knowledge(query: str, top_k: int = 4) -> dict[str, Any]:
    """按统一 Evidence Envelope 返回本地战术基础知识，供 Collector 与 Solver 消费。"""
    # local_foundations 是概念框架来源，不应被解释为某场比赛或当前球队状态的事实来源。
    passages = retrieve_tactical_foundations(query, top_k=top_k)
    warnings = [
        "本地战术基础笔记只用于解释稳定概念；具体比赛结论仍需结合实时资料、比赛报告或用户材料。"
    ]
    if not passages:
        warnings.append("本地基础知识库没有检索到与该问题直接匹配的概念条目。")
    return build_tool_success(
        source="local_tactical_foundations",
        data={
            "query": query,
            "passages": passages,
            "knowledge_scope": "足球战术基础框架，不包含实时球队或单场比赛事实。",
        },
        freshness="historical",
        confidence="medium",
        warnings=warnings,
    )
