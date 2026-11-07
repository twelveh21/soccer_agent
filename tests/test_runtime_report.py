"""验证运行复盘报告只基于安全元数据计算轨迹结论。"""

from __future__ import annotations

from agent_base.runtime_report import build_run_report, format_run_report


def test_build_research_run_report() -> None:
    """研究路径应统计 Solver 实际执行次数，而不是猜测模型循环次数。"""
    # 这里使用最小假摘要，证明报告层不需要访问真实模型、数据库或用户原文。
    summary = {
        "run_id": "demo-run",
        "status": "success",
        "error_type": None,
        "node_duration_ms": 72.5,
        "events": [
            {"node_name": "validate_input", "status": "success", "details": {}},
            {"node_name": "classify", "status": "success", "details": {"route": "research"}},
            {"node_name": "solve_research", "status": "success", "details": {}},
            {"node_name": "reflect_research", "status": "success", "details": {}},
            {"node_name": "solve_research", "status": "success", "details": {}},
        ],
    }
    report = build_run_report(summary)
    assert report["route"] == "research"
    assert report["research_attempts"] == 2
    assert "Solver 轮次：2" in format_run_report(report)


def test_missing_run_report_is_explicit() -> None:
    """不存在的 run_id 应被明确标记，而不是返回模糊的空字典。"""
    # 调用者可据此向 CLI 或网页显示“找不到运行记录”的正常提示。
    assert build_run_report(None)["found"] is False
