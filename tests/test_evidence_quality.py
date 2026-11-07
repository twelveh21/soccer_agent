"""证据质量层的新鲜度、来源排序和冲突检测测试。"""

import sys
from pathlib import Path

# 直接执行本测试文件时，将项目根目录加入导入路径以找到 tool 包。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tool.shared.evidence_quality import assess_evidence_bundle, source_rank


def check_source_rank_and_conflicts() -> None:
    """验证官方来源优先，并能识别同一事实的不同结构化值。"""
    # 两条证据给同一比赛的开球时间不同值，结构化 API 应比普通网页结果优先。
    evidences = [
        {
            "ok": True,
            "source": "football-data.org",
            "retrieved_at": "2026-10-31T10:00:00Z",
            "data": {
                "claims": [
                    {"claim_key": "fixture:arsenal-liverpool:kickoff", "value": "2026-11-01T16:30:00Z"}
                ]
            },
        },
        {
            "ok": True,
            "source": "Tavily web search",
            "retrieved_at": "2026-10-31T10:01:00Z",
            "data": {
                "claims": [
                    {
                        "claim_key": "fixture:arsenal-liverpool:kickoff",
                        "value": "2026-11-01T17:30:00Z",
                        "source_url": "https://example.com/match-preview",
                    }
                ],
                "results": [{"url": "https://example.com/match-preview"}],
            },
        },
    ]
    report = assess_evidence_bundle(evidences)
    assert source_rank("football-data.org") < source_rank("Tavily web search", "https://example.com")
    assert len(report["conflicts"]) == 1
    assert report["conflicts"][0]["preferred_candidate"]["source"] == "football-data.org"


def main() -> None:
    """执行证据质量层测试。"""
    # 本测试完全基于内存中的模拟证据，不访问外部 API。
    check_source_rank_and_conflicts()
    print("证据质量层测试通过")


if __name__ == "__main__":
    main()
