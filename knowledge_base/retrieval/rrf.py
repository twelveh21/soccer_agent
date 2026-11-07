"""使用 Reciprocal Rank Fusion 融合多个战术检索通道。"""

from __future__ import annotations

from collections import defaultdict

from knowledge_base.retrieval.contracts import RetrievedPassage


def reciprocal_rank_fusion(
    ranked_lists: list[list[RetrievedPassage]],
    top_k: int = 4,
    rank_constant: int = 60,
) -> list[RetrievedPassage]:
    """把 BM25、向量等多个排序结果融合为一份稳定候选列表。

    参数：ranked_lists 是每个检索器从高到低的结果；top_k 是最终候选数；rank_constant 用于降低单一排名变化的影响。
    实现：同一 citation_id 在多个通道出现时累加 1/(rank_constant + 名次)，再按总分降序输出。
    """
    if top_k < 1:
        raise ValueError("top_k 必须至少为 1。")
    if rank_constant < 1:
        raise ValueError("rank_constant 必须至少为 1。")

    scores: defaultdict[str, float] = defaultdict(float)
    passages: dict[str, RetrievedPassage] = {}
    methods: defaultdict[str, list[str]] = defaultdict(list)
    for ranked_list in ranked_lists:
        for rank, passage in enumerate(ranked_list, start=1):
            scores[passage.citation_id] += 1 / (rank_constant + rank)
            passages[passage.citation_id] = passage
            method = str(passage.metadata.get("retrieval_method", "unknown"))
            if method not in methods[passage.citation_id]:
                methods[passage.citation_id].append(method)

    ordered_ids = sorted(scores, key=scores.get, reverse=True)[:top_k]
    return [
        passages[citation_id].model_copy(
            update={
                "score": round(scores[citation_id], 6),
                "metadata": {
                    **passages[citation_id].metadata,
                    "retrieval_method": "rrf_fusion",
                    "fused_from": methods[citation_id],
                },
            }
        )
        for citation_id in ordered_ids
    ]
