Agent 角色层

这里按职责定义 Planner、Collector、Solver、Critic、Finalizer。
目前实际实现仍在 agent_base/agent.py 与 research_*.py，避免大迁移破坏现有主链路。
后续逐步将每个角色迁入本目录；roles.py 是它们共享的输入输出契约。
