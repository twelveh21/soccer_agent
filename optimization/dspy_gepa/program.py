"""将足球 Solver 包装为可被 DSPy / GEPA 优化的程序。"""
from __future__ import annotations

import dspy


DEFAULT_SOLVER_INSTRUCTION = """你是证据驱动的足球研究助手。只基于给定证据作答；战术概念需给出引用，具体比赛事实证据不足时必须说明局限和仍需核验的信息。不得编造实时数据或来源。"""


class SoccerSolverSignature(dspy.Signature):
    """DSPy 声明 Solver 的输入输出字段，而非手工拼接聊天字符串。"""

    question: str = dspy.InputField(desc="用户提出的足球研究问题")
    evidence: str = dspy.InputField(desc="Collector 已收集、允许 Solver 使用的证据摘要")
    answer: str = dspy.OutputField(desc="带证据边界的中文研究回答")


class SoccerSolverProgram(dspy.Module):
    """一个可优化的 Solver 模块；GEPA 改的是其 Signature 指令文本。"""

    def __init__(self, instruction: str = DEFAULT_SOLVER_INSTRUCTION) -> None:
        """创建带初始指令的 DSPy Solver。

        参数：instruction 是当前待评测/待优化的 Solver 工作指令。
        实现逻辑：with_instructions 把自然语言指令绑定到 Signature；ChainOfThought 负责实际调用配置好的模型。
        """
        super().__init__()
        self.solve = dspy.ChainOfThought(SoccerSolverSignature.with_instructions(instruction))

    def forward(self, question: str, evidence: str) -> dspy.Prediction:
        """让 Solver 根据问题和已有证据输出答案。

        参数：question 为评测题或真实研究问题；evidence 为 Collector 已收集的材料摘要。
        实现逻辑：Solver 不接工具、不自行检索；这保持与 LangGraph 原有“Solver 只消费 Evidence”的边界一致。
        """
        return self.solve(question=question, evidence=evidence)

    def instruction_text(self) -> str:
        """读取当前候选程序实际使用的指令文本。

        参数：无。
        实现逻辑：GEPA compile 后会返回带新 Signature 的程序；读取该字段用于人工审阅和保存候选版本。
        """
        return self.solve.predict.signature.instructions
