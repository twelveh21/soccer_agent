"""研究回答评测的最小离线样例。"""

from __future__ import annotations

RESEARCH_ANSWER_CASES = (
    {"case_id": "local-framework-needs-citation", "answer": "战术框架显示压迫需要协同（local-foundation:pressing-and-counterpress#1）。具体比赛执行仍需核验。", "requires_local_citation": True, "requires_limitations": True},
    {"case_id": "fact-boundary-needs-disclosure", "answer": "现有资料证据不足，无法确认该队在该场比赛是否持续高位压迫。", "requires_local_citation": False, "requires_limitations": True},
)
