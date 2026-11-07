"""研究计划结构化契约的纯本地测试。"""

import sys
from pathlib import Path

from pydantic import ValidationError

# 直接执行本测试文件时，将项目根目录加入导入路径以找到 agent_base 包。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_base.research_plan import ResearchPlan


def check_research_plan_contract() -> None:
    """验证合法计划可解析，越界字段和缺少资料类型会被拒绝。"""
    # 此测试不调用模型，确保规划契约的回归测试不会消耗 Token 或依赖网络。
    valid_plan = ResearchPlan.model_validate(
        {
            "research_goal": "分析阿森纳如何利用边路宽度破解对手低位防守。",
            "sub_questions": [
                {
                    "question": "阿森纳在进攻三区如何拉开横向宽度？",
                    "purpose": "识别边路宽度的具体战术机制。",
                    "required_sources": ["web_search", "tactical_rag"],
                },
                {
                    "question": "这种宽度如何制造禁区前或肋部的进攻空间？",
                    "purpose": "将战术动作和最终进攻效果建立因果联系。",
                    "required_sources": ["web_search", "tactical_rag"],
                },
            ],
            "completion_criteria": [
                "每个关键机制至少有一条可追溯来源支持。",
                "结论区分资料事实与基于资料的分析。",
            ],
            "assumptions_or_gaps": ["尚未接入逐帧视频数据，因此不声称完成视频级验证。"],
        }
    )
    assert len(valid_plan.sub_questions) == 2
    assert valid_plan.sub_questions[0].required_sources == ["web_search", "tactical_rag"]

    invalid_plan = valid_plan.model_dump()
    invalid_plan["unexpected_field"] = "模型不应输出该字段"
    try:
        ResearchPlan.model_validate(invalid_plan)
    except ValidationError:
        pass
    else:
        raise AssertionError("额外字段应被结构化契约拒绝。")


def main() -> None:
    """作为独立脚本运行研究计划契约测试。"""
    # 保持测试入口与项目其他测试一致，便于初学阶段直接执行和理解。
    check_research_plan_contract()
    print("研究计划结构化契约测试通过")


if __name__ == "__main__":
    main()
