"""显式保存的偏好与研究笔记的 SQLite 实现。"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from memory.contracts import MemoryRecord


class SqliteMemoryStore:
    """以 SQLite 保存用户主动写入的记忆，不自动记录普通对话。"""

    def __init__(self, database_path: Path) -> None:
        """保存数据库位置并确保表已存在。"""
        # 每次操作使用短连接，避免 Web 请求和 CLI 同时访问时共享连接状态。
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._setup()

    def _setup(self) -> None:
        """创建可重复初始化的记忆表与查询索引。"""
        # content 不承担足球事实来源职责，真正事实仍应通过 Tool 或 RAG 取得。
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS memories (
                    memory_id TEXT PRIMARY KEY, session_id TEXT, scope TEXT NOT NULL,
                    kind TEXT NOT NULL, content TEXT NOT NULL, metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                    )"""
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_memories_session ON memories(session_id, created_at)"
                )

    def save(self, record: MemoryRecord, *, session_id: str | None = None) -> MemoryRecord:
        """保存一条已由用户明确授权的记忆并返回稳定 ID。"""
        # 调用方必须在 UI/API 层取得明确意图；这里不从问答内容自动抽取记忆。
        stored = record.model_copy(update={"memory_id": record.memory_id or uuid4().hex})
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                connection.execute(
                    "INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (stored.memory_id, session_id, stored.scope, stored.kind, stored.content,
                     stored.model_dump_json(include={"metadata"}),
                     datetime.now(timezone.utc).isoformat()),
                )
        return stored

    def list_for_session(self, session_id: str, *, limit: int = 20) -> list[MemoryRecord]:
        """读取当前会话可见的最近记忆，不跨会话泄漏 private 资料。"""
        # project 范围可被本项目复用；session 范围只对同一个 session 可见。
        with closing(sqlite3.connect(self.database_path)) as connection:
            rows = connection.execute(
                """SELECT memory_id, scope, kind, content, metadata_json FROM memories
                WHERE scope = 'project' OR (scope = 'session' AND session_id = ?)
                ORDER BY created_at DESC LIMIT ?""",
                (session_id, max(1, min(limit, 100))),
            ).fetchall()
        return [MemoryRecord.model_validate({
            "memory_id": row[0], "scope": row[1], "kind": row[2], "content": row[3],
            "metadata": __import__("json").loads(row[4]).get("metadata", {}),
        }) for row in rows]

    def delete(self, memory_id: str) -> bool:
        """按稳定 ID 删除一条记忆，满足用户的撤回权。"""
        # 删除仅影响指定记录，避免宽泛删除损坏其他会话或项目笔记。
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                return connection.execute("DELETE FROM memories WHERE memory_id = ?", (memory_id,)).rowcount > 0
