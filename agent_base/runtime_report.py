"""把安全运行记录转成开发者可读的工作流复盘摘要。"""

from __future__ import annotations

from collections import Counter
from typing import Any


def build_run_report(summary: dict[str, Any] | None) -> dict[str, Any]:
    """从 RunRecorder 摘要提炼路由、节点顺序、失败点和研究循环次数。"""
    # 不读取用户原文或模型回答，只复用 RunRecorder 已允许保存的安全元数据。
    if summary is None:
        return {"found": False, "message": "未找到对应的运行记录。"}

    events = summary.get("events", [])
    route = next(
        (
            event.get("details", {}).get("route")
            for event in events
            if event.get("node_name") == "classify" and event.get("details", {}).get("route")
        ),
        None,
    )
    node_counts = Counter(event.get("node_name", "unknown") for event in events)
    failed_nodes = [event.get("node_name", "unknown") for event in events if event.get("status") == "error"]
    return {
        "found": True,
        "run_id": summary["run_id"],
        "status": summary["status"],
        "route": route,
        "node_sequence": [event.get("node_name", "unknown") for event in events],
        "node_counts": dict(node_counts),
        "research_attempts": node_counts.get("solve_research", 0),
        "failed_nodes": failed_nodes,
        "node_duration_ms": summary.get("node_duration_ms", 0),
        "error_type": summary.get("error_type"),
        "model_calls": summary.get("model_calls", []),
        "model_duration_ms": round(sum(call.get("duration_ms") or 0 for call in summary.get("model_calls", [])), 2),
        "estimated_cost_usd": round(sum(call.get("estimated_cost_usd") or 0 for call in summary.get("model_calls", [])), 8),
    }


def format_run_report(report: dict[str, Any]) -> str:
    """将机器可读报告格式化为 CLI、日志或面试演示可直接展示的文本。"""
    # 单独提供格式化函数，使 API 可以继续使用 JSON，而命令行无需重复拼接字符串。
    if not report["found"]:
        return report["message"]
    route = report["route"] or "未记录"
    nodes = " → ".join(report["node_sequence"]) or "未记录节点"
    failures = "、".join(report["failed_nodes"]) or "无"
    return (
        f"run_id：{report['run_id']}\n"
        f"状态：{report['status']}｜路径：{route}\n"
        f"节点：{nodes}\n"
        f"Solver 轮次：{report['research_attempts']}｜节点总耗时：{report['node_duration_ms']} ms\n"
        f"失败节点：{failures}"
    )
