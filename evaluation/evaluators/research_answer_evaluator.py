"""对研究答案执行无需额外模型的证据边界评测。"""

from __future__ import annotations

from evaluation.evaluators.contracts import EvaluationResult


def evaluate_research_answer(case_id: str, answer: str, *, requires_local_citation: bool, requires_limitations: bool) -> list[EvaluationResult]:
    """检查回答是否在要求处保留本地引用和不确定性说明。"""
    # 这是确定性守门评测，不把“文笔好”误判为“证据链合格”。
    normalized = answer.lower()
    citation_ok = (not requires_local_citation) or "local-foundation:" in normalized
    limitation_markers = ("局限", "无法确认", "需核验", "不确定", "证据不足")
    limitation_ok = (not requires_limitations) or any(marker in answer for marker in limitation_markers)
    return [
        EvaluationResult(evaluator_name="citation_presence", case_id=case_id, status="skip" if not requires_local_citation else ("pass" if citation_ok else "fail"), score=1.0 if citation_ok else 0.0, reason="本用例不要求本地战术框架引用。" if not requires_local_citation else ("本地战术框架引用存在。" if citation_ok else "缺少 local-foundation 引用。")),
        EvaluationResult(evaluator_name="limitation_disclosure", case_id=case_id, status="pass" if limitation_ok else "fail", score=1.0 if limitation_ok else 0.0, reason="已披露证据边界。" if limitation_ok else "缺少不确定性或局限说明。"),
    ]
