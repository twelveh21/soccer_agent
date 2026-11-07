"""模型网关的角色选择、参数传递和缓存测试。"""

import sys
from pathlib import Path
from typing import Any

# 直接执行本测试文件时，将项目根目录加入导入路径以找到 agent_base 包。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_base.model_gateway import ModelGateway


def check_model_gateway_profiles_and_cache() -> None:
    """验证轻量角色、指定覆盖、超时重试和客户端缓存都符合预期。"""
    # 假工厂只记录参数，保证测试不会发起真实模型请求或需要真实 API Key。
    created: list[dict[str, Any]] = []

    def fake_model_factory(**kwargs: Any) -> dict[str, Any]:
        """记录网关传入的模型配置，并返回可比较的假模型对象。"""
        # 返回同一份参数有助于断言网关没有泄漏或改写关键调用配置。
        created.append(kwargs)
        return kwargs

    gateway = ModelGateway(
        base_url="https://example.test/v1",
        api_key="test-key",
        primary_model="strong-model",
        lightweight_model="fast-model",
        timeout_seconds=12,
        max_retries=2,
        role_model_overrides={"solver": "solver-model"},
        model_factory=fake_model_factory,
    )

    assert gateway.profile_for("planner").model_name == "fast-model"
    assert gateway.profile_for("finalizer").model_name == "strong-model"
    assert gateway.profile_for("solver").model_name == "solver-model"

    first_planner = gateway.get_model("planner")
    second_planner = gateway.get_model("planner")
    assert first_planner is second_planner
    assert len(created) == 1
    assert created[0]["timeout"] == 12
    assert created[0]["max_retries"] == 2
    assert created[0]["api_key"] == "test-key"
    assert "test-key" not in str(gateway.describe_profiles())


def main() -> None:
    """作为独立脚本运行模型网关测试。"""
    # 单独测试模型网关可防止配置修改时才在真实 Agent 调用中暴露问题。
    check_model_gateway_profiles_and_cache()
    print("模型网关测试通过")


if __name__ == "__main__":
    main()
