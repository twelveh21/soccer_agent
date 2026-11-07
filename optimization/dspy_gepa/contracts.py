"""DSPy / GEPA 优化阶段共享的数据模型。"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class OptimizationCase:
    """一条用于比较 Prompt / Agent 策略的固定研究题。"""
    case_id: str
    question: str
    requires_tactical_citation: bool
    requires_limitations: bool
    forbids_unverified_realtime_claims: bool

@dataclass(frozen=True)
class MetricFeedback:
    """GEPA 可消费的分数、分项指标和文字反馈。"""
    score: float
    objective_scores: dict[str, float]
    feedback: str

@dataclass(frozen=True)
class CandidateEvaluation:
    """一次候选 Prompt 在单个题目上的输出与评分结果。"""
    candidate_name: str
    case_id: str
    answer: str
    metric: MetricFeedback

class AnswerExecutor(Protocol):
    """可替换的回答执行器协议，供基线和未来 DSPy 程序共用。"""
    def answer(self, question: str, instruction: str) -> str:
        """根据问题和候选指令生成回答。

        参数：question 是评测问题；instruction 是候选 Solver 指令。
        实现逻辑：协议只规定形状，具体实现可调用固定样本、现有 Agent 或 DSPy 模块。
        """
