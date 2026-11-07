"""运行本地战术知识检索回归评测。"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.datasets.tactical_retrieval_cases import TACTICAL_RETRIEVAL_CASES
from evaluation.evaluators.tactical_retrieval_evaluator import evaluate_tactical_retrieval_case


def main() -> None:
    """执行全部 RAG 检索题，并在任一失败时以非零状态结束。"""
    # CLI 输出同时适合作为本地检查和未来 CI 日志，便于观察哪条概念查询发生退化。
    results = [evaluate_tactical_retrieval_case(*case) for case in TACTICAL_RETRIEVAL_CASES]
    for result in results:
        print(f"[{result['status'].upper()}] {result['case_id']}：{result['actual_document_id']}")
    failed = [result for result in results if result["status"] != "pass"]
    if failed:
        raise SystemExit(f"战术检索评测失败：{len(failed)} / {len(results)}")
    print(f"战术检索评测通过：{len(results)} / {len(results)}")


if __name__ == "__main__":
    main()
