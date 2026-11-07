evals：足球 Agent 的评测层

workflow_dataset.py：固定的基础数据、实时信息和战术研究问题集。
workflow_contracts.py：评估路由、关键节点顺序、允许节点集合和 Solver 最大轮次。
run_offline_evals.py：零模型费用的路由回归评测入口。

当前是确定性评测基线。后续会在此基础上增加真实运行轨迹评测、证据引用评测与 LLM-as-a-Judge。

research_loop_simulator.py：用预设 Critic verdict 驱动真实的 choose_after_reflection 路由函数，模拟 pass、补证、重规划和达到上限四类研究闭环。它不调用模型或网络，但会生成与 RunRecorder 摘要相同形状的事件数据，再由 workflow_contracts.py 评估节点顺序与 Solver 上限。
