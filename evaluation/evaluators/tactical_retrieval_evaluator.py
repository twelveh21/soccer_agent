"""对本地战术知识检索进行可重复的文档命中评测。"""

from __future__ import annotations

from knowledge_base.retrieval.local_tactical_retriever import search_local_tactical_knowledge


def evaluate_tactical_retrieval_case(case_id: str, query: str, expected_document_id: str) -> dict[str, object]:
    """判断一条查询的首个检索结果是否命中预期概念文档。"""
    # 该评测不评价模型文笔，只验证 RAG 的第一步“找对资料”是否稳定。
    result = search_local_tactical_knowledge(query, top_k=1)
    passages = result["data"]["passages"]
    actual = passages[0]["metadata"]["chunk_id"].split("#", 1)[0] if passages else None
    return {
        "case_id": case_id,
        "status": "pass" if actual == expected_document_id else "fail",
        "expected_document_id": expected_document_id,
        "actual_document_id": actual,
    }
