"""离线基线运行器：在真正调用 GEPA 前确定可复现的起点分数。"""
from __future__ import annotations
from statistics import fmean
from typing import Any
from optimization.dspy_gepa.contracts import AnswerExecutor, CandidateEvaluation, OptimizationCase
from optimization.dspy_gepa.metric import evaluate_football_answer

def evaluate_candidate(candidate_name: str, instruction: str, cases: tuple[OptimizationCase, ...], executor: AnswerExecutor) -> list[CandidateEvaluation]:
    """用固定题集评估一个 Prompt / Solver 指令候选。

    参数：candidate_name 是候选名；instruction 是提示词；cases 是固定题；executor 是回答执行器。
    实现逻辑：逐题生成答案并调用统一 metric，不在本函数中强制调用模型，便于零成本基线和 DSPy 复用。
    """
    evaluations: list[CandidateEvaluation] = []
    for case in cases:
        answer = executor.answer(case.question, instruction)
        evaluations.append(CandidateEvaluation(candidate_name, case.case_id, answer, evaluate_football_answer(case, answer)))
    return evaluations

def summarize_candidate(evaluations: list[CandidateEvaluation]) -> dict[str, Any]:
    """把逐题评分汇总为未来 GEPA 候选可比较的报告。

    参数：evaluations 是同一候选的逐题结果。
    实现逻辑：计算平均总分和分项均分，并保留每题文字反馈；空列表直接报错避免误判。
    """
    if not evaluations: raise ValueError("至少需要一条评测结果才能生成基线报告。")
    names = sorted({name for item in evaluations for name in item.metric.objective_scores})
    return {"candidate_name": evaluations[0].candidate_name, "mean_score": round(fmean(item.metric.score for item in evaluations), 4), "mean_objectives": {name: round(fmean(item.metric.objective_scores[name] for item in evaluations), 4) for name in names}, "cases": [{"case_id": item.case_id, "score": item.metric.score, "objectives": item.metric.objective_scores, "feedback": item.metric.feedback} for item in evaluations]}
