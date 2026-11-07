"""带预算与人工确认门槛的 DSPy / GEPA 离线优化运行器。"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import dspy

from optimization.dspy_gepa.baseline_dataset import OPTIMIZATION_CASES
from optimization.dspy_gepa.contracts import MetricFeedback, OptimizationCase
from optimization.dspy_gepa.metric import evaluate_football_answer
from optimization.dspy_gepa.program import DEFAULT_SOLVER_INSTRUCTION, SoccerSolverProgram


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_DIR = PROJECT_ROOT / "artifacts" / "gepa_candidates"


def build_qwen_lm(model_name: str | None = None, temperature: float = 0.2) -> dspy.LM:
    """创建使用现有 DashScope OpenAI 兼容地址的 DSPy 模型客户端。

    参数：model_name 可覆盖环境变量模型名；temperature 控制生成随机性。
    实现逻辑：读取既有 DASHSCOPE 配置，转换为 LiteLLM 的 openai/ 模型命名；不在代码中写入 Key。
    """
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    base_url = os.getenv("DASHSCOPE_BASE_URL", "").strip()
    selected_model = model_name or os.getenv("SOCCER_AGENT_MODEL", "qwen3.5-plus")
    if not api_key or not base_url:
        raise RuntimeError("运行 GEPA 前需要配置 DASHSCOPE_API_KEY 和 DASHSCOPE_BASE_URL。")
    return dspy.LM(f"openai/{selected_model}", api_key=api_key, api_base=base_url, temperature=temperature, max_tokens=1600)


def build_dspy_examples(cases: tuple[OptimizationCase, ...] = OPTIMIZATION_CASES) -> list[dspy.Example]:
    """把项目固定题集转换为 DSPy 的训练/验证样例。

    参数：cases 是项目定义的足球质量评测题。
    实现逻辑：question/evidence 是 Solver 输入；质量约束作为 gold 元数据保留给 metric，不泄漏给 Solver。
    """
    return [
        dspy.Example(
            question=case.question,
            evidence="当前只有稳定战术知识；没有该场比赛的实时事件数据。",
            case_id=case.case_id,
            requires_tactical_citation=case.requires_tactical_citation,
            requires_limitations=case.requires_limitations,
            forbids_unverified_realtime_claims=case.forbids_unverified_realtime_claims,
        ).with_inputs("question", "evidence")
        for case in cases
    ]


def football_gepa_metric(gold: dspy.Example, pred: dspy.Prediction, trace: Any = None, **_: Any) -> dspy.Prediction:
    """把项目 Metric 转换为 GEPA 所需的 score + feedback 协议。

    参数：gold 是带质量约束的评测题；pred 是当前候选 Solver 输出；trace 由 DSPy 传入以支持反思。
    实现逻辑：复用项目已有确定性评分逻辑，返回 GEPA 能读取的总分、分项分数和中文失败反馈。
    """
    case = OptimizationCase(
        case_id=gold.case_id,
        question=gold.question,
        requires_tactical_citation=gold.requires_tactical_citation,
        requires_limitations=gold.requires_limitations,
        forbids_unverified_realtime_claims=gold.forbids_unverified_realtime_claims,
    )
    feedback: MetricFeedback = evaluate_football_answer(case, str(pred.answer))
    return dspy.Prediction(score=feedback.score, objective_scores=feedback.objective_scores, feedback=feedback.feedback)


def optimize_solver(max_metric_calls: int, output_dir: Path = CANDIDATE_DIR) -> Path:
    """在固定预算内运行 GEPA，并保存待人工确认的候选 Solver 指令。

    参数：max_metric_calls 是评测调用硬上限；output_dir 是候选报告的保存目录。
    实现逻辑：同一 Qwen 客户端分别承担 Solver 和 reflection；GEPA 只优化离线 student，完成后保存新旧指令、配置和统计，不自动改线上 Prompt。
    """
    if not 8 <= max_metric_calls <= 80:
        raise ValueError("max_metric_calls 必须在 8 到 80 之间，避免无上限消耗模型额度。")
    solver_lm = build_qwen_lm(temperature=0.1)
    reflection_lm = build_qwen_lm(temperature=0.4)
    examples = build_dspy_examples()
    student = SoccerSolverProgram()
    optimizer = dspy.GEPA(
        metric=football_gepa_metric,
        reflection_lm=reflection_lm,
        max_metric_calls=max_metric_calls,
        candidate_selection_strategy="pareto",
        track_stats=True,
        track_best_outputs=True,
        seed=42,
    )
    with dspy.context(lm=solver_lm):
        optimized = optimizer.compile(student, trainset=examples, valset=examples)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"gepa_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    report = {
        "status": "pending_human_approval",
        "baseline_instruction": DEFAULT_SOLVER_INSTRUCTION,
        "candidate_instruction": optimized.instruction_text(),
        "max_metric_calls": max_metric_calls,
        "case_ids": [case.case_id for case in OPTIMIZATION_CASES],
        "detailed_results": str(getattr(optimized, "detailed_results", ""))[:12000],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path
