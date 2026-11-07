"""校验最终回答引用是否来自本轮实际检索到的证据。"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from knowledge_base.retrieval.contracts import RetrievedPassage


_CITATION_PATTERN = re.compile(r"(?:local-foundation|web):[A-Za-z0-9_.:/#?=&-]+")


class CitationValidationResult(BaseModel):
    """记录一次回答引用校验的结果，供 Critic、日志和评测共同使用。"""

    # cited_ids 保留模型实际写出的引用；unknown_ids 是本轮 Evidence 中没有的引用，必须提示或拦截。
    cited_ids: list[str] = Field(default_factory=list)
    unknown_ids: list[str] = Field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """判断回答中的所有引用是否都可回溯到本轮证据。

        参数：无。
        实现：只要 unknown_ids 为空即视为通过；不要求每份证据都被引用。
        """
        return not self.unknown_ids


def extract_citation_ids(answer: str) -> list[str]:
    """从模型回答中提取去重后的本地或网页引用 ID。

    参数：answer 是最终草案或最终回答。
    实现：用统一正则识别已约定的 local-foundation 与 web 前缀，并按出现顺序去重。
    """
    return list(dict.fromkeys(_CITATION_PATTERN.findall(answer)))


def validate_answer_citations(
    answer: str,
    evidence: list[RetrievedPassage],
) -> CitationValidationResult:
    """确认回答引用的每个 ID 都来自此次检索结果。

    参数：answer 是待发布文本；evidence 是本轮给 Solver 的可引用资料。
    实现：先抽取回答内引用，再与 Evidence 的 citation_id 集合做差集，未知项作为风险返回而不静默删除。
    """
    cited_ids = extract_citation_ids(answer)
    known_ids = {passage.citation_id for passage in evidence}
    unknown_ids = [citation_id for citation_id in cited_ids if citation_id not in known_ids]
    return CitationValidationResult(cited_ids=cited_ids, unknown_ids=unknown_ids)


def validate_citation_ids(answer: str, allowed_ids: set[str]) -> CitationValidationResult:
    """按调用方提供的允许引用集合校验回答。

    参数：answer 是待发布文本；allowed_ids 是本轮 Evidence 目录中允许展示的引用 ID。
    实现：复用统一提取规则，适用于本地战术资料和网页资料混合出现的 Finalizer 场景。
    """
    cited_ids = extract_citation_ids(answer)
    unknown_ids = [citation_id for citation_id in cited_ids if citation_id not in allowed_ids]
    return CitationValidationResult(cited_ids=cited_ids, unknown_ids=unknown_ids)


def remove_unknown_citations(answer: str, unknown_ids: list[str]) -> str:
    """从待发布回答中移除无法回溯的引用标识。

    参数：answer 是待发布文本；unknown_ids 是校验发现的未知引用。
    实现：只替换引用 ID 本身，不改写模型的其他表达；调用方仍应补充资料边界提示。
    """
    cleaned_answer = answer
    for citation_id in unknown_ids:
        cleaned_answer = cleaned_answer.replace(citation_id, "未验证引用")
    return cleaned_answer
