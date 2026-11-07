# 足球 Agent 架构

## 运行时主链路

`用户问题 -> classify -> 基础数据 / 实时信息 / 战术研究 -> verify_evidence -> finalize`

战术研究子图：

`plan_research -> collect_research_evidence -> solve_research -> reflect_research`

Critic 只返回 `pass`、`gather_more` 或 `replan`。工作流以最大轮次强制收口，不能无限循环。

## 分层原则

1. Graph 只负责状态转移和角色编排。
2. Tool / RAG 只负责取得可追溯的证据。
3. Solver 只消费 State 中证据，不私自检索。
4. Guardrail 在高风险操作前做策略判断。
5. Observability 记录安全元数据，不记录密钥、原始网页内容或完整私密问题。
6. API 层只适配 HTTP/SSE，不重写研究业务逻辑。

## 演进顺序

先真实验证 Planner Collector Solver Critic 闭环，再接入战术 RAG 与真实评测；最后服务化、Redis/PostgreSQL、Docker 和多模态。
