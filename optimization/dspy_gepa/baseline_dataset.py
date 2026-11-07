"""不调用模型的最小优化题集和固定答案执行器。"""
from __future__ import annotations
from optimization.dspy_gepa.contracts import AnswerExecutor, OptimizationCase

OPTIMIZATION_CASES = (
    OptimizationCase("pressing-framework", "高位逼抢的核心原则是什么？", True, True, True),
    OptimizationCase("match-fact-boundary", "阿森纳上一场比赛是否一直采用高位逼抢？", False, True, True),
)

class FixedBaselineExecutor(AnswerExecutor):
    """固定答案执行器，用于验证评测/报告流程，不消耗模型调用。"""
    def answer(self, question: str, instruction: str) -> str:
        """返回固定基线答案。

        参数：question 是评测问题；instruction 为兼容未来真实执行器保留。
        实现逻辑：按问题关键词返回稳定答案，使 CI 可验证评分逻辑。
        """
        if "核心原则" in question:
            return "高位逼抢依赖整体协同、封锁传球路线和丢球后快速反抢（local-foundation:pressing-and-counterpress#1）。局限是：具体比赛中的执行仍需结合事件数据和视频核验。"
        return "现有材料证据不足，无法确认阿森纳在某场具体比赛中是否始终采用高位逼抢；仍需核验赛程、阵容、事件数据和视频。"
