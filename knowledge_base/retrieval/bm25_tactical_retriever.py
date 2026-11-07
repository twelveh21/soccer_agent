"""为战术知识库提供可解释的 BM25 关键词检索。"""

from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache

from knowledge_base.ingestion.foundation_ingestion import TacticalChunk
from knowledge_base.retrieval.hybrid_tactical_retriever import load_indexed_chunks, normalize_text
from knowledge_base.retrieval.contracts import RetrievedPassage, RetrievalRequest


def tokenize_for_bm25(text: str) -> list[str]:
    """把中英文战术文本转为 BM25 可比较的词元列表。

    参数：text 是用户问题、标题或知识块正文。
    实现：英文按单词保留；中文同时保留连续中文词串及双字片段，避免未引入中文分词服务时完全无法匹配。
    """
    normalized = normalize_text(text)
    english_terms = re.findall(r"[a-z0-9]+", normalized)
    chinese_sequences = re.findall(r"[\u4e00-\u9fff]{2,}", normalized)
    chinese_bigrams = [
        sequence[index : index + 2]
        for sequence in chinese_sequences
        for index in range(len(sequence) - 1)
    ]
    return english_terms + chinese_sequences + chinese_bigrams


def build_searchable_text(chunk: TacticalChunk) -> str:
    """合并一个知识块的标签、标题和正文，作为 BM25 的检索字段。

    参数：chunk 是已完成校验和切分的战术知识块。
    实现：标签和标题重复一次，使人工标记的核心概念比普通正文获得略高权重，同时不改变原始资料。
    """
    tags = " ".join(chunk.tags)
    return f"{tags} {chunk.title} {chunk.title} {chunk.text}"


class BM25TacticalRetriever:
    """对本地战术切块执行无外部依赖的 BM25 检索。"""

    def __init__(self, chunks: tuple[TacticalChunk, ...], k1: float = 1.5, b: float = 0.75) -> None:
        """预计算文档词频和词元频率，减少每次提问的重复计算。

        参数：chunks 是知识库切块；k1 控制词频增加的饱和速度；b 控制长文本长度归一化强度。
        实现：初始化时只做统计，search 时按 BM25 公式对候选块累加分数。
        """
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.document_terms = [tokenize_for_bm25(build_searchable_text(chunk)) for chunk in chunks]
        self.document_frequencies = Counter(
            term for terms in self.document_terms for term in set(terms)
        )
        self.average_document_length = (
            sum(len(terms) for terms in self.document_terms) / len(self.document_terms)
            if self.document_terms
            else 0.0
        )

    def search(self, request: RetrievalRequest) -> list[RetrievedPassage]:
        """按 BM25 分数返回可引用的战术证据片段。

        参数：request 包含 query、top_k 与预留的 filters。
        实现：逐个查询词计算 IDF，再结合当前文档词频和文本长度累加 BM25 分；零分文档不返回，避免伪造相关性。
        """
        query_terms = tokenize_for_bm25(request.query)
        if not query_terms or not self.chunks or not self.average_document_length:
            return []

        total_documents = len(self.chunks)
        scored_chunks: list[tuple[float, TacticalChunk]] = []
        for chunk, terms in zip(self.chunks, self.document_terms, strict=True):
            term_counts = Counter(terms)
            score = 0.0
            for term in query_terms:
                document_frequency = self.document_frequencies.get(term, 0)
                if not document_frequency:
                    continue
                inverse_document_frequency = math.log(
                    1 + (total_documents - document_frequency + 0.5) / (document_frequency + 0.5)
                )
                term_frequency = term_counts.get(term, 0)
                denominator = term_frequency + self.k1 * (
                    1 - self.b + self.b * len(terms) / self.average_document_length
                )
                if denominator:
                    score += inverse_document_frequency * term_frequency * (self.k1 + 1) / denominator
            if score > 0:
                scored_chunks.append((score, chunk))

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
                    "retrieval_method": "bm25",
                    "limitations": chunk.limitations,
                },
            )
            for score, chunk in scored_chunks[: request.top_k]
        ]


@lru_cache(maxsize=1)
def get_bm25_tactical_retriever() -> BM25TacticalRetriever:
    """复用本地 BM25 索引实例，避免每个请求都重新统计知识库。

    参数：无。
    实现：借助 LRU 缓存将加载后的切块和统计量保留在进程内；更新知识索引后重启服务即可刷新。
    """
    return BM25TacticalRetriever(load_indexed_chunks())


def retrieve_with_bm25(query: str, top_k: int = 4) -> list[RetrievedPassage]:
    """提供给上层 Agent 的简洁 BM25 检索入口。

    参数：query 是足球战术问题；top_k 是最多返回的证据数。
    实现：将普通参数封装为 RetrievalRequest，再委托缓存的检索器处理。
    """
    request = RetrievalRequest(query=query, top_k=top_k)
    return get_bm25_tactical_retriever().search(request)
