Graph 编排层

现有完整图由 agent_base/agent.py 注册并运行；state.py 是全图唯一的共享状态定义与初始化入口。

节点顺序：validate_input -> classify -> 三条业务路径之一 -> verify_evidence -> finalize。
复杂研究路径额外经过 plan_research -> collect_research_evidence -> solve_research -> reflect_research，并由 Critic 决定验证、补资料或重新规划。

本目录提供稳定导出入口：外部服务只依赖 build_workflow，而不应依赖具体节点文件位置。
