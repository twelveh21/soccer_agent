"""足球 Agent 的本地运行记录：保存工作流轨迹、耗时和失败位置。"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from infrastructure.observability.cost_estimator import estimate_cost_usd


def utc_now_iso() -> str:
    """生成 SQLite 中统一使用的 UTC 时间字符串。"""
    # 运行记录跨不同机器与时区比较时，统一 UTC 可以避免本地时间造成误判。
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def question_fingerprint(question: str) -> str:
    """生成问题摘要指纹，用于关联重复运行而不落库存储原始问题。"""
    # 原始提问可能包含个人偏好或其他私密内容，因此仅记录不可逆的 SHA-256 摘要。
    return hashlib.sha256(question.encode("utf-8")).hexdigest()


class RunRecorder:
    """使用 SQLite 持久化 Agent 运行元数据，供调试与后续评测读取。"""

    def __init__(self, database_path: Path) -> None:
        """保存数据库位置；每次操作独立建连以兼容异步节点和线程池。"""
        # 不共享 sqlite3.Connection，避免 LangGraph 的异步执行和 to_thread 产生线程冲突。
        self.database_path = database_path

    def setup(self) -> None:
        """创建运行与节点事件表；可重复调用而不会覆盖历史记录。"""
        # IF NOT EXISTS 使应用每次启动时都可安全确保表结构存在。
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                connection.executescript(
                    """
                CREATE TABLE IF NOT EXISTS agent_runs (
                    run_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    question_fingerprint TEXT NOT NULL,
                    question_length INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    error_type TEXT
                );

                CREATE TABLE IF NOT EXISTS agent_run_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    node_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    duration_ms REAL,
                    details_json TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES agent_runs(run_id)
                );

                CREATE INDEX IF NOT EXISTS idx_agent_run_events_run_id
                ON agent_run_events(run_id, event_id);

                CREATE TABLE IF NOT EXISTS agent_model_calls (
                    call_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL, role TEXT NOT NULL, model_name TEXT NOT NULL,
                    input_tokens INTEGER, output_tokens INTEGER, duration_ms REAL,
                    estimated_cost_usd REAL, status TEXT NOT NULL, occurred_at TEXT NOT NULL
                );
                    """
                )

    def start_run(self, run_id: str, session_id: str, question: str) -> None:
        """创建一条进行中的运行记录，并只保存问题指纹和长度。"""
        # run_id 是一次执行的唯一标识；同一 session 可以包含多次独立提问与运行。
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                connection.execute(
                    """
                INSERT INTO agent_runs (
                    run_id, session_id, question_fingerprint, question_length, started_at, status
                ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (run_id, session_id, question_fingerprint(question), len(question), utc_now_iso(), "running"),
                )

    def record_event(
        self,
        run_id: str,
        node_name: str,
        status: str,
        *,
        duration_ms: float | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """追加一条节点事件；details 仅保存安全的元数据而非模型或用户原文。"""
        # JSON 让不同节点能按需附加 route、更新字段或异常类型，表结构无需频繁迁移。
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                connection.execute(
                    """
                INSERT INTO agent_run_events (
                    run_id, node_name, status, occurred_at, duration_ms, details_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        node_name,
                        status,
                        utc_now_iso(),
                        duration_ms,
                        json.dumps(details or {}, ensure_ascii=False, sort_keys=True),
                    ),
                )

    def finish_run(self, run_id: str, status: str, error_type: str | None = None) -> None:
        """标记运行已成功、失败或被取消，并保留失败类型供聚合分析。"""
        # 不保存完整异常文本，避免异常中意外带入密钥、用户输入或网页内容。
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                connection.execute(
                    """
                UPDATE agent_runs
                SET finished_at = ?, status = ?, error_type = ?
                WHERE run_id = ?
                    """,
                    (utc_now_iso(), status, error_type, run_id),
                )

    def record_model_call(self, run_id: str, role: str, model_name: str, *, input_tokens: int | None, output_tokens: int | None, duration_ms: float, status: str) -> None:
        """保存一次模型调用的安全计量信息，不保存 Prompt 或回答正文。"""
        # Token 为空时仍保留耗时和角色，适配未返回 usage 的兼容 OpenAI 供应商。
        estimated = estimate_cost_usd(input_tokens or 0, output_tokens or 0) if input_tokens is not None and output_tokens is not None else None
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                connection.execute("INSERT INTO agent_model_calls (run_id, role, model_name, input_tokens, output_tokens, duration_ms, estimated_cost_usd, status, occurred_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (run_id, role, model_name, input_tokens, output_tokens, duration_ms, estimated, status, utc_now_iso()))

    def get_run_summary(self, run_id: str) -> dict[str, Any] | None:
        """读取单次运行的状态、节点事件和总节点耗时，供 CLI、API 或评测使用。"""
        # 先读取主运行记录；不存在时返回 None，调用方可据此区分“无记录”和“空事件”。
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            run_row = connection.execute(
                "SELECT * FROM agent_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if run_row is None:
                return None
            event_rows = connection.execute(
                """
                SELECT node_name, status, occurred_at, duration_ms, details_json
                FROM agent_run_events
                WHERE run_id = ?
                ORDER BY event_id
                """,
                (run_id,),
            ).fetchall()
            model_rows = connection.execute(
                "SELECT role, model_name, input_tokens, output_tokens, duration_ms, estimated_cost_usd, status FROM agent_model_calls WHERE run_id = ? ORDER BY call_id",
                (run_id,),
            ).fetchall()

        events = [
            {
                "node_name": row["node_name"],
                "status": row["status"],
                "occurred_at": row["occurred_at"],
                "duration_ms": row["duration_ms"],
                "details": json.loads(row["details_json"]),
            }
            for row in event_rows
        ]
        return {
            "run_id": run_row["run_id"],
            "session_id": run_row["session_id"],
            "question_fingerprint": run_row["question_fingerprint"],
            "question_length": run_row["question_length"],
            "started_at": run_row["started_at"],
            "finished_at": run_row["finished_at"],
            "status": run_row["status"],
            "error_type": run_row["error_type"],
            "node_duration_ms": round(sum(event["duration_ms"] or 0 for event in events), 2),
            "events": events,
            "model_calls": [dict(row) for row in model_rows],
        }
