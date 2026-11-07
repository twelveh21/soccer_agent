"""验证不同证据源在进入模型前被压缩，并保留引用目录。"""

from __future__ import annotations

from agent_base.research_evidence_context import build_citation_catalog, build_research_evidence_context


def local_evidence() -> dict[str, object]:
    """构造最小本地战术知识证据，避免测试依赖磁盘内容。"""
    # 模拟 Retriever 的统一输出形状，测试的是上下文边界而不是关键词算法。
    return {
        "source": "local_tactical_foundations",
        "data": {
            "knowledge_scope": "稳定概念",
            "passages": [{
                "citation_id": "local-foundation:pressing-and-counterpress",
                "title": "压迫与反抢",
                "summary": "压迫引导低价值传球。",
                "text": "x" * 1200,
                "limitations": "不证明具体比赛事实。",
            }],
        },
        "warnings": [],
    }


def test_context_truncates_long_local_text() -> None:
    """模型上下文应限制长条目，而 State 中原始证据可继续完整保存。"""
    # 上下文压缩是成本控制，不是数据删除，因此只检查返回摘要的长度。
    context = build_research_evidence_context([local_evidence()], max_text_length=80)
    assert len(context[0]["passages"][0]["text"]) == 80
    assert context[0]["passages"][0]["citation_id"].startswith("local-foundation:")


def test_catalog_marks_local_foundation() -> None:
    """最终回答的引用目录必须标明本地条目属于概念框架。"""
    # 防止 Finalizer 把本地知识条目伪装成新闻、官方公告或比赛事实来源。
    catalog = build_citation_catalog([local_evidence()])
    assert catalog[0]["label"] == "本地战术框架：压迫与反抢"
