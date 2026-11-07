"""未来服务化使用的集中配置模型。"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeSettings:
    """只保存非敏感运行参数，密钥仍从环境变量按需读取。"""

    # 统一配置入口可以避免 API、Worker 与 CLI 分别硬编码循环、超时等参数。
    environment: str = "development"
    research_max_attempts: int = 2
    request_timeout_seconds: float = 20.0

    @classmethod
    def from_env(cls) -> "RuntimeSettings":
        """从环境变量读入可公开的运行控制项。"""
        # 这里只转换普通参数，绝不把 API Key 读入日志对象或 Pydantic 响应。
        return cls(
            environment=os.getenv("SOCCER_AGENT_ENV", "development"),
            research_max_attempts=int(os.getenv("SOCCER_RESEARCH_MAX_ATTEMPTS", "2")),
            request_timeout_seconds=float(os.getenv("SOCCER_REQUEST_TIMEOUT", "20")),
        )
