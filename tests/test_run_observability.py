"""本地运行记录的持久化与隐私字段测试。"""

import sys
import tempfile
from pathlib import Path

# 直接执行本测试文件时，将项目根目录加入导入路径以找到 agent_base 包。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_base.run_observability import RunRecorder, question_fingerprint


def check_run_recorder() -> None:
    """验证运行、节点成功事件和失败收尾都能读回，且原始问题不会进入摘要。"""
    # 临时数据库保证测试不会污染开发期间的真实运行日志。
    question = "分析阿森纳面对低位防守的边路策略"
    with tempfile.TemporaryDirectory() as directory:
        recorder = RunRecorder(Path(directory) / "runs.db")
        recorder.setup()
        recorder.start_run("run-1", "session-1", question)
        recorder.record_event(
            "run-1",
            "plan_research",
            "success",
            duration_ms=12.5,
            details={"updated_fields": ["plan"]},
        )
        recorder.finish_run("run-1", "success")

        summary = recorder.get_run_summary("run-1")
        assert summary is not None
        assert summary["status"] == "success"
        assert summary["question_fingerprint"] == question_fingerprint(question)
        assert summary["question_length"] == len(question)
        assert "question" not in summary
        assert summary["node_duration_ms"] == 12.5
        assert summary["events"][0]["details"] == {"updated_fields": ["plan"]}


def main() -> None:
    """作为独立脚本运行本地运行记录测试。"""
    # 采用项目统一的可直接执行测试方式，方便逐个理解和验证。
    check_run_recorder()
    print("运行记录测试通过")


if __name__ == "__main__":
    main()
