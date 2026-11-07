"""验证本地战术基础知识可被检索，并保留边界说明。"""

from __future__ import annotations

from knowledge_base.retrieval.local_tactical_retriever import search_local_tactical_knowledge


def test_pressing_query_returns_pressing_foundation() -> None:
    """压迫问题应优先命中压迫与反抢概念，而不是无关条目。"""
    # 这是基础检索质量的最小回归测试，未来换向量库时也应保留同类案例。
    result = search_local_tactical_knowledge("高位压迫如何封锁中场传球线路？")
    passages = result["data"]["passages"]
    assert result["ok"] is True
    assert passages
    assert passages[0]["citation_id"].startswith("local-foundation:pressing-and-counterpress#")


def test_local_foundations_explain_their_boundary() -> None:
    """本地概念资料必须提示它不能证明具体比赛事实。"""
    # 防止未来改动时，基础框架资料被错误包装成实时或单场比赛数据。
    result = search_local_tactical_knowledge("阿森纳如何前场逼抢？")
    assert result["freshness"] == "historical"
    assert any("具体比赛结论" in warning for warning in result["warnings"])
