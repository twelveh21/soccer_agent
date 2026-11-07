"""足球 Agent 的模型网关：集中管理角色模型、超时、重试与配置审计。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping

from langchain.chat_models import init_chat_model


ModelRole = Literal[
    "basic_query",
    "current_info",
    "planner",
    "solver",
    "critic",
    "finalizer",
]
LIGHTWEIGHT_ROLES: frozenset[ModelRole] = frozenset({"current_info", "planner", "critic"})


@dataclass(frozen=True)
class ModelProfile:
    """一个 Agent 角色调用模型时使用的可审计配置。"""

    role: ModelRole
    model_name: str
    timeout_seconds: float
    max_retries: int


class ModelGateway:
    """按 Agent 角色创建并缓存聊天模型，避免模型参数分散在各节点中。"""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        primary_model: str,
        lightweight_model: str | None,
        timeout_seconds: float,
        max_retries: int,
        enable_thinking: bool,
        role_model_overrides: Mapping[ModelRole, str] | None = None,
        model_factory: Callable[..., Any] = init_chat_model,
    ) -> None:
        """保存不含业务逻辑的模型配置，并允许测试注入假的模型工厂。"""
        # API Key 只保存在内存配置中；describe_profiles 永远不会返回它。
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.primary_model = primary_model
        self.lightweight_model = lightweight_model or primary_model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        # 足球助手是交互式产品；默认关闭模型冗长的隐藏推理，避免一个问题在多个
        # Agent 节点上重复等待。需要研究型推理时可通过环境变量重新开启。
        self.enable_thinking = enable_thinking
        self.role_model_overrides = dict(role_model_overrides or {})
        self.model_factory = model_factory
        self._models: dict[ModelRole, Any] = {}

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "ModelGateway":
        """从环境变量读取网关配置，并在缺失必填项时尽早报错。"""
        # 允许传入字典使配置解析可离线测试，正式运行时默认读取 os.environ。
        env = environ or os.environ
        base_url = env.get("DASHSCOPE_BASE_URL")
        api_key = env.get("DASHSCOPE_API_KEY")
        if not base_url or not api_key:
            raise RuntimeError("缺少 DASHSCOPE_BASE_URL 或 DASHSCOPE_API_KEY，请检查 .env 文件。")

        primary_model = env.get("SOCCER_AGENT_MODEL", "qwen3.5-35b-a3b")
        lightweight_model = env.get("SOCCER_AGENT_LIGHT_MODEL")
        try:
            timeout_seconds = float(env.get("SOCCER_AGENT_MODEL_TIMEOUT_SECONDS", "25"))
            max_retries = int(env.get("SOCCER_AGENT_MODEL_MAX_RETRIES", "1"))
        except ValueError as error:
            raise RuntimeError("模型超时和重试次数必须是数字，请检查 .env 文件。") from error
        if timeout_seconds <= 0 or max_retries < 0:
            raise RuntimeError("模型超时必须大于 0，重试次数不能小于 0。")
        enable_thinking = env.get("SOCCER_AGENT_ENABLE_THINKING", "false").lower() in {"1", "true", "yes"}

        overrides: dict[ModelRole, str] = {}
        for role in ("basic_query", "current_info", "planner", "solver", "critic", "finalizer"):
            value = env.get(f"SOCCER_AGENT_{role.upper()}_MODEL")
            if value:
                overrides[role] = value
        return cls(
            base_url=base_url,
            api_key=api_key,
            primary_model=primary_model,
            lightweight_model=lightweight_model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            enable_thinking=enable_thinking,
            role_model_overrides=overrides,
        )

    def profile_for(self, role: ModelRole) -> ModelProfile:
        """计算某个角色应该使用哪一个模型及其调用预算。"""
        # 默认让 Planner、Critic 和资料整理使用轻量模型；复杂 Solver 与 Finalizer 保持主模型。
        default_model = self.lightweight_model if role in LIGHTWEIGHT_ROLES else self.primary_model
        return ModelProfile(
            role=role,
            model_name=self.role_model_overrides.get(role, default_model),
            timeout_seconds=self.timeout_seconds,
            max_retries=self.max_retries,
        )

    def get_model(self, role: ModelRole) -> Any:
        """按角色延迟创建并在进程内复用模型客户端。"""
        # 缓存避免同一角色重复初始化 HTTP 客户端，也保证同角色调用配置保持一致。
        if role not in self._models:
            profile = self.profile_for(role)
            self._models[role] = self.model_factory(
                model=profile.model_name,
                model_provider="openai",
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=profile.timeout_seconds,
                max_retries=profile.max_retries,
                # DashScope OpenAI 兼容接口支持该扩展字段。关闭后仍会正常生成
                # 回答，但不会先输出耗时很长的 reasoning_content。
                extra_body={"enable_thinking": self.enable_thinking},
            )
        return self._models[role]

    def describe_profiles(self) -> list[dict[str, str | float | int]]:
        """返回不含密钥的角色配置，供启动日志、调试和后续成本审计使用。"""
        # 输出仅包含角色、模型名、超时和重试次数，可安全写入运行日志。
        return [
            {
                "role": profile.role,
                "model_name": profile.model_name,
                "timeout_seconds": profile.timeout_seconds,
                "max_retries": profile.max_retries,
                "enable_thinking": self.enable_thinking,
            }
            for profile in (self.profile_for(role) for role in (
                "basic_query", "current_info", "planner", "solver", "critic", "finalizer"
            ))
        ]
