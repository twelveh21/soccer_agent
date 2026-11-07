"""Celery 应用配置：定义 Redis 队列地址、结果存储与任务发现位置。"""

from __future__ import annotations

import os
from pathlib import Path

from celery import Celery
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def required_setting(name: str) -> str:
    """读取 Worker 必需配置。

    参数：
    - name：环境变量名称，例如 CELERY_BROKER_URL。

    实现逻辑：缺失时立即失败，避免 Worker 看似启动但没有连接到正确 Redis 队列。
    """
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Worker 缺少 {name}，请检查 .env 配置。")
    return value


celery_app = Celery(
    "soccer_agent",
    broker=required_setting("CELERY_BROKER_URL"),
    backend=required_setting("CELERY_RESULT_BACKEND"),
    include=["worker.tasks"],
)

# JSON 让任务参数可读、可跨进程传输；task_track_started 让 Celery 记录任务已被 Worker 取走。
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_time_limit=15 * 60,
)
