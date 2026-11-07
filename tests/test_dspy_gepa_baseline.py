"""验证评测驱动优化的基线逻辑，不调用外部模型。"""
from optimization.dspy_gepa.baseline import evaluate_candidate, summarize_candidate
from optimization.dspy_gepa.baseline_dataset import FixedBaselineExecutor, OPTIMIZATION_CASES
from optimization.dspy_gepa.metric import evaluate_football_answer

def test_fixed_baseline_is_reproducible() -> None:
    """固定基线应稳定通过当前质量守门项。

    参数：无。
    实现逻辑：执行零模型基线，确保未来优化有可复现对照组。
    """
    assert summarize_candidate(evaluate_candidate("baseline", "ignored", OPTIMIZATION_CASES, FixedBaselineExecutor()))["mean_score"] == 1.0

def test_metric_returns_actionable_feedback() -> None:
    """缺少引用/局限的回答应返回低分和具体反馈。

    参数：无。
    实现逻辑：保证 GEPA 不只看到一个数字，还能理解该修复什么。
    """
    feedback = evaluate_football_answer(OPTIMIZATION_CASES[0], "高位逼抢就是一直向前跑。")
    assert feedback.score < 1.0 and "缺少" in feedback.feedback
