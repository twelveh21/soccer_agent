"""研究 Critic 结构化决定的本地契约测试。"""

import sys
from pathlib import Path

from pydantic import ValidationError

# 直接执行本测试文件时，将项目根目录加入导入路径以找到 agent_base 包。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent_base.research_review import ResearchReview


def check_research_review_contract() -> None:
    """验证 Critic 决定可解析，未知 verdict 会在进入路由前被拒绝。"""
    # 此测试只验证数据契约，不调用模型，保证循环路由的基础行为可离线回归。
    review = ResearchReview.model_validate(
        {
            "verdict": "gather_more",
            "rationale": "草案描述了边路宽度，但缺少具体比赛案例支撑其效果。",
            "issues": [
                {
                    "category": "evidence",
                    "detail": "没有可追溯来源说明该机制在哪场比赛中形成机会。",
                    "required_action": "补充至少一篇战术报道或赛后分析中的具体比赛案例。",
                }
            ],
            "final_answer_limitations": ["当前没有逐帧视频数据，不能做视频级结论。"],
        }
    )
    assert review.verdict == "gather_more"
    assert review.issues[0].category == "evidence"

    invalid_review = review.model_dump()
    invalid_review["verdict"] = "keep_trying"
    try:
        ResearchReview.model_validate(invalid_review)
    except ValidationError:
        pass
    else:
        raise AssertionError("未知 verdict 不应进入 LangGraph 条件路由。")


def main() -> None:
    """作为独立脚本运行 Critic 结构化契约测试。"""
    # 保持测试入口和其他契约测试一致，便于直接执行和理解。
    check_research_review_contract()
    print("研究 Critic 结构化契约测试通过")


if __name__ == "__main__":
    main()
