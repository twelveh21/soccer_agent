"""基于 SQLite 的轻量 TTL 缓存，供外部数据源 Tool 复用。"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from hashlib import sha256
from pathlib import Path
from typing import Any


# 文件已位于 tool/shared 下，因此需要向上两层才能回到项目根目录。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_PATH = PROJECT_ROOT / "data" / "tool_cache.db"


def cache_database_path() -> Path:
    """读取缓存数据库位置，并在未配置时使用项目内默认路径。"""
    # 可用环境变量迁移数据库；默认放到 data 目录，避免与 Agent 会话检查点混在一起。
    configured_path = os.getenv("SOCCER_CACHE_DB_PATH")
    return Path(configured_path) if configured_path else DEFAULT_CACHE_PATH


def make_cache_key(namespace: str, value: dict[str, Any]) -> str:
    """将请求参数稳定地转换为不会泄露 API Key 的缓存键。"""
    # sort_keys 保证相同参数即使传入顺序不同也会生成同一个键。
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(f"{namespace}:{serialized}".encode("utf-8")).hexdigest()


class SqliteTtlCache:
    """提供跨进程持久化的 JSON 缓存，并在读取时自动清理过期项。"""

    def __init__(self, database_path: Path | None = None) -> None:
        """初始化数据库文件位置，并确保缓存表存在。"""
        # 每个读写操作都新建短连接，避免 CLI、测试和未来 Web 服务共享连接时出现线程问题。
        self.database_path = database_path or cache_database_path()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._setup()

    def _connect(self) -> sqlite3.Connection:
        """打开一次 SQLite 连接并启用字典形式的查询结果。"""
        # timeout 让并发请求短暂等待数据库锁，而不是立即报错。
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def _setup(self) -> None:
        """创建缓存表和过期时间索引。"""
        # expires_at 索引让随着缓存增长的过期项清理仍保持高效。
        connection = self._connect()
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tool_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_tool_cache_expires_at ON tool_cache(expires_at)"
            )
            connection.commit()
        finally:
            # Windows 会保留未关闭 SQLite 文件句柄，因此每个短连接都必须显式关闭。
            connection.close()

    def get(self, cache_key: str) -> dict[str, Any] | None:
        """返回未过期缓存；过期、损坏或不存在时返回 None。"""
        # 读取时清理目标过期项，使调用者只需区分“命中”与“未命中”。
        now = time.time()
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT payload, expires_at FROM tool_cache WHERE cache_key = ?", (cache_key,)
            ).fetchone()
            if row is None:
                return None
            if row["expires_at"] <= now:
                connection.execute("DELETE FROM tool_cache WHERE cache_key = ?", (cache_key,))
                connection.commit()
                return None
            try:
                return json.loads(row["payload"])
            except json.JSONDecodeError:
                connection.execute("DELETE FROM tool_cache WHERE cache_key = ?", (cache_key,))
                connection.commit()
                return None
        finally:
            # 显式关闭连接，避免 CLI 和测试环境持续占用缓存数据库文件。
            connection.close()

    def set(self, cache_key: str, payload: dict[str, Any], ttl_seconds: int) -> None:
        """保存 JSON 数据，并以 TTL 决定其自动失效时间。"""
        # TTL 必须为正数，避免因调用方配置错误而写入永不过期或立即过期的数据。
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds 必须大于 0。")
        now = time.time()
        connection = self._connect()
        try:
            connection.execute(
                """
                INSERT INTO tool_cache (cache_key, payload, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload = excluded.payload,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at
                """,
                (cache_key, json.dumps(payload, ensure_ascii=False), now, now + ttl_seconds),
            )
            connection.commit()
        finally:
            # 写入完成立即释放文件句柄，便于 Windows 下的并发工具调用。
            connection.close()

    def clear_expired(self) -> int:
        """删除全部过期记录，并返回本次删除的数量。"""
        # 此方法可在未来定时任务中调用，防止长期运行服务积累无用记录。
        connection = self._connect()
        try:
            cursor = connection.execute("DELETE FROM tool_cache WHERE expires_at <= ?", (time.time(),))
            connection.commit()
            return cursor.rowcount
        finally:
            # 即使删除过程中失败也关闭连接，防止缓存文件锁残留。
            connection.close()
