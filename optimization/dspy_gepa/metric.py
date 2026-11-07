"""足球 Agent 的确定性评分与 GEPA 文字反馈。"""
from __future__ import annotations
from optimization.dspy_gepa.contracts import MetricFeedback, OptimizationCase

def evaluate_football_answer(case: OptimizationCase, answer: str) -> MetricFeedback:
    """评估回答的引用边界、局限披露和实时事实克制程度。

    参数：case 定义该题约束；answer 是候选策略输出。
    实现逻辑：三项规则分别评分并生成失败原因；GEPA 后续同时使用总分和 feedback 文本优化指令。
    """
    normalized = answer.lower(); objectives: dict[str, float] = {}; feedback: list[str] = []
    if case.requires_tactical_citation:
        ok = "local-foundation:" in normalized; objectives["citation"] = float(ok)
        feedback.append("已提供本地战术引用。" if ok else "缺少 local-foundation 战术引用，不能把概念解释伪装成来源充分的结论。")
    else: objectives["citation"] = 1.0
    if case.requires_limitations:
        ok = any(marker in answer for marker in ("局限", "无法确认", "需核验", "不确定", "证据不足")); objectives["limitations"] = float(ok)
        feedback.append("已披露证据边界。" if ok else "缺少局限或待核验信息，需明确区分概念解释与具体比赛事实。")
    else: objectives["limitations"] = 1.0
    if case.forbids_unverified_realtime_claims:
        unsupported = any(marker in answer for marker in ("刚刚查询", "已查询官方", "实时数据显示", "今日确认")); objectives["fact_boundary"] = float(not unsupported)
        feedback.append("未声称未核验实时事实。" if not unsupported else "出现未附来源的实时事实承诺，应降级为待核验表述或补充证据。")
    else: objectives["fact_boundary"] = 1.0
    return MetricFeedback(round(sum(objectives.values()) / len(objectives), 4), objectives, " ".join(feedback))
