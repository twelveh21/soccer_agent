"""验证 RAG 重排与引用可追溯性校验。"""

from __future__ import annotations

from knowledge_base.citations.validator import remove_unknown_citations, validate_answer_citations, validate_citation_ids
from knowledge_base.retrieval.advanced_tactical_retriever import retrieve_advanced_tactical_knowledge


def test_advanced_retrieval_finishes_with_reranker() -> None:
    """高级检索的最终结果应明确经过 reranker，而不是只停在 RRF。"""
    # 检索链路标签可让运行记录和面试演示说明实际走过哪些阶段。
    passages = retrieve_advanced_tactical_knowledge("高位压迫后的反抢", top_k=2)
    assert passages
    assert passages[0].metadata["retrieval_method"] == "lightweight_reranker"
    assert passages[0].metadata["reranked_from"] == "rrf_fusion"


def test_citation_validator_accepts_only_retrieved_citations() -> None:
    """回答只能引用本轮检索资料，未知引用必须被报告。"""
    # 这阻止模型凭空写出看似专业、但实际上无法回溯的来源编号。
    passages = retrieve_advanced_tactical_knowledge("高位压迫", top_k=2)
    known_id = passages[0].citation_id
    result = validate_answer_citations(
        f"压迫需要协同 [{known_id}]，另见 [local-foundation:invented-source#0]。",
        passages,
    )
    assert result.cited_ids == [known_id, "local-foundation:invented-source#0"]
    assert result.unknown_ids == ["local-foundation:invented-source#0"]
    assert result.is_valid is False


def test_generic_citation_validation_supports_the_finalizer_catalog() -> None:
    """Finalizer 使用的引用目录也应识别并清理未知引用。"""
    # 此处模拟网页和本地资料共同存在时，Finalizer 只允许输出目录里的 ID。
    result = validate_citation_ids(
        "资料见 web:1 和 local-foundation:unknown#0。",
        {"web:1"},
    )
    assert result.unknown_ids == ["local-foundation:unknown#0"]
    assert "未验证引用" in remove_unknown_citations("资料见 local-foundation:unknown#0。", result.unknown_ids)
