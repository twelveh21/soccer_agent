Prompt 版本层

未来把 Planner、Solver、Critic 等提示词从 agent.py 移入本目录，并为每个提示词维护版本号、适用模型和回归评测结果。
当前运行中的 Prompt 仍在 agent_base/agent.py；prompt_registry.py 是迁移前的统一元数据入口。
