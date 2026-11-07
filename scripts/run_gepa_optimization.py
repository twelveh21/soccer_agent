"""显式确认成本后运行一次 DSPy / GEPA Solver 指令优化。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from optimization.dspy_gepa.gepa_runner import optimize_solver


def main() -> None:
    """解析预算与确认参数，运行后只输出候选文件路径。

    参数：无，命令行参数包括 --max-metric-calls 和 --confirm-cost。
    实现逻辑：没有明确确认时只展示运行说明；确认后才调用模型，产物永远停在 pending_human_approval 状态。
    """
    parser = argparse.ArgumentParser(description="离线运行足球 Solver 的 DSPy / GEPA 指令优化。")
    parser.add_argument("--max-metric-calls", type=int, default=12, help="最多评分调用次数，默认 12。")
    parser.add_argument("--confirm-cost", action="store_true", help="明确确认后才允许发起模型调用。")
    args = parser.parse_args()
    if not args.confirm_cost:
        print(f"未执行模型调用。若确认最多进行 {args.max_metric_calls} 次评分调用，请追加 --confirm-cost。")
        return
    report_path = optimize_solver(args.max_metric_calls)
    print(f"GEPA 已完成，候选未自动上线，请人工审阅：{report_path}")


if __name__ == "__main__":
    main()
