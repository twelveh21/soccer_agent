"""执行 DSPy / GEPA 前的零成本足球 Agent 基线评测。"""
from __future__ import annotations
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from optimization.dspy_gepa.baseline import evaluate_candidate, summarize_candidate
from optimization.dspy_gepa.baseline_dataset import FixedBaselineExecutor, OPTIMIZATION_CASES

def main() -> None:
    """运行固定基线并输出未来 GEPA 必须超过的分数。

    参数：无。
    实现逻辑：固定执行器不调用模型；未来替换为 DSPy Solver 时报告结构不变，可直接比较。
    """
    results = evaluate_candidate("baseline-fixed-solver", "只基于证据作答，给出引用和证据边界。", OPTIMIZATION_CASES, FixedBaselineExecutor())
    print(json.dumps(summarize_candidate(results), ensure_ascii=False, indent=2))

if __name__ == "__main__": main()
