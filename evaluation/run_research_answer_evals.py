"""执行研究答案的离线证据边界评测。"""

from __future__ import annotations

from evaluation.datasets.research_answer_cases import RESEARCH_ANSWER_CASES
from evaluation.evaluators.research_answer_evaluator import evaluate_research_answer


def main() -> None:
    """运行固定用例，并在任一守门项失败时以非零状态退出。"""
    # 固定题集可用于 Prompt、模型或 Finalizer 改动后的快速回归。
    results = [result for case in RESEARCH_ANSWER_CASES for result in evaluate_research_answer(**case)]
    for result in results:
        print(f"[{result.status.upper()}] {result.case_id}:{result.evaluator_name} - {result.reason}")
    if any(result.status == "fail" for result in results):
        raise SystemExit(1)
    print(f"研究答案证据评测通过：{len(results)} / {len(results)}")


if __name__ == "__main__":
    main()
