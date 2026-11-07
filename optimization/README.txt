本目录放评测驱动的离线 Agent 优化实验，不参与在线聊天请求。

第一阶段：固定题集、可解释评分、文字反馈与基线报告。
第二阶段：使用 DSPy / GEPA 在明确模型调用预算内迭代 Solver 指令，比较优化前后的质量、成本和延迟。

运行：python scripts/run_gepa_optimization.py --max-metric-calls 12 --confirm-cost
运行后只会生成 artifacts/gepa_candidates/ 下的 pending_human_approval 候选报告，不会改线上 Prompt。
