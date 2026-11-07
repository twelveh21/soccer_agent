"""对 RRF 初步召回的少量战术资料进行轻量重排。"""

from __future__ import annotations

from collections import Counter

from knowledge_base.retrieval.bm25_tactical_retriever import tokenize_for_bm25
from knowledge_base.retrieval.contracts import RetrievedPassage


def score_query_passage_overlap(query: str, passage: RetrievedPassage) -> float:
    """计算问题与候选资料的二次相关度分数。

    参数：query 是用户问题；passage 是 RRF 已召回的候选证据。
    实现：标题和标签的词命中权重高于正文，避免通用长文本仅靠大量词汇偶然排到前面。
    """
    query_terms = set(tokenize_for_bm25(query))
    if not query_terms:
        return 0.0
    title_terms = set(tokenize_for_bm25(str(passage.metadata.get("title", ""))))
    tag_terms = set(tokenize_for_bm25(" ".join(map(str, passage.metadata.get("tags", [])))))
    body_counts = Counter(tokenize_for_bm25(passage.text))
    title_hits = len(query_terms & title_terms)
    tag_hits = len(query_terms & tag_terms)
    body_hits = sum(min(body_counts[term], 2) for term in query_terms)
    return title_hits * 3 + tag_hits * 4 + body_hits


def rerank_passages(
    query: str,
    passages: list[RetrievedPassage],
    top_k: int = 4,
) -> list[RetrievedPassage]:
    """重排已融合的少量候选，并保留原有证据和引用字段。

    参数：query 是用户问题；passages 是 RRF 结果；top_k 是最终返回数量。
    实现：以二次相关度为主、RRF 分数为次级排序键，输出 metadata 标明 reranker 已参与。
    """
    if top_k < 1:
        raise ValueError("top_k 必须至少为 1。")
    scored = [
        (score_query_passage_overlap(query, passage), passage)
        for passage in passages
    ]
    scored.sort(key=lambda item: (item[0], item[1].score), reverse=True)
    return [
        passage.model_copy(
            update={
                "score": round(score, 6),
                "metadata": {
                    **passage.metadata,
                    "retrieval_method": "lightweight_reranker",
                    "reranked_from": passage.metadata.get("retrieval_method"),
                },
            }
        )
        for score, passage in scored[:top_k]
    ]
