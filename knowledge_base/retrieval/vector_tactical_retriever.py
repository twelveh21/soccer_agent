"""战术知识库的本地稀疏向量检索基线。"""

from __future__ import annotations

import math
from collections import Counter
from functools import lru_cache

from knowledge_base.ingestion.foundation_ingestion import TacticalChunk
from knowledge_base.retrieval.bm25_tactical_retriever import build_searchable_text, tokenize_for_bm25
from knowledge_base.retrieval.contracts import RetrievedPassage, RetrievalRequest
from knowledge_base.retrieval.hybrid_tactical_retriever import load_indexed_chunks


def cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
    """计算两个稀疏词向量的余弦相似度。

    参数：left 是查询向量；right 是知识块向量。
    实现：使用共同词元的点积，并除以双方长度；任一向量为空时返回零，避免除零错误。
    """
    if not left or not right:
        return 0.0
    dot_product = sum(weight * right.get(term, 0) for term, weight in left.items())
    left_length = math.sqrt(sum(weight * weight for weight in left.values()))
    right_length = math.sqrt(sum(weight * weight for weight in right.values()))
    return dot_product / (left_length * right_length) if left_length and right_length else 0.0


class SparseVectorTacticalRetriever:
    """将问题和知识块转成词频向量后，以余弦相似度检索。"""

    def __init__(self, chunks: tuple[TacticalChunk, ...]) -> None:
        """为每个知识块生成可复用的稀疏向量。

        参数：chunks 是已校验的本地战术资料切块。
        实现：只在初始化时统计词频，后续每次问题只生成一次查询向量并比较相似度。
        """
        self.chunks = chunks
        self.document_vectors = [Counter(tokenize_for_bm25(build_searchable_text(chunk))) for chunk in chunks]

    def search(self, request: RetrievalRequest) -> list[RetrievedPassage]:
        """找出与问题词向量方向最接近的战术知识块。

        参数：request 提供 query 和 top_k。
        实现：把 query 转为词频向量，逐个计算余弦相似度，仅保留大于零的候选并附上统一引用格式。
        """
        query_vector = Counter(tokenize_for_bm25(request.query))
        scored_chunks = [
            (cosine_similarity(query_vector, vector), chunk)
            for chunk, vector in zip(self.chunks, self.document_vectors, strict=True)
        ]
        scored_chunks = [item for item in scored_chunks if item[0] > 0]
        scored_chunks.sort(key=lambda item: item[0], reverse=True)
        return [
            RetrievedPassage(
                citation_id=f"local-foundation:{chunk.document_id}#{chunk.ordinal}",
                text=chunk.text,
                score=round(score, 6),
                metadata={
                    "title": chunk.title,
                    "tags": chunk.tags,
                    "summary": chunk.summary,
                    "retrieval_method": "sparse_vector_baseline",
                    "limitations": chunk.limitations,
                },
            )
            for score, chunk in scored_chunks[: request.top_k]
        ]


@lru_cache(maxsize=1)
def get_sparse_vector_tactical_retriever() -> SparseVectorTacticalRetriever:
    """缓存向量检索器，避免服务每次请求重新向量化全部知识块。

    参数：无。
    实现：载入本地索引后构造一次 SparseVectorTacticalRetriever，进程运行期间重复复用。
    """
    return SparseVectorTacticalRetriever(load_indexed_chunks())


def retrieve_with_sparse_vector(query: str, top_k: int = 4) -> list[RetrievedPassage]:
    """提供给融合器的本地向量检索入口。

    参数：query 是用户的战术问题；top_k 是候选上限。
    实现：创建统一 RetrievalRequest 后调用缓存检索器，保证和 BM25 输出同一数据格式。
    """
    return get_sparse_vector_tactical_retriever().search(RetrievalRequest(query=query, top_k=top_k))
