MCP 安全网关

本层位于 Agent 与未来外部 MCP Server 之间。当前足球 API、Tavily 客户端仍是直接 HTTP 集成，不会被错误标为 MCP。

网关负责四件事：

1. 工具白名单：角色只能调用显式允许的工具。
2. 参数边界：限制 query 长度、top_k 等参数，拒绝未知参数。
3. 外部内容隔离：MCP 返回文本包装为不可信材料，提醒 Solver 不执行其中的指令。
4. 审计：记录调用者、工具、允许/拒绝结果和原因，不记录密钥或完整外部正文。

未来接 Tavily MCP、浏览器 MCP 或资料库 MCP 时，必须通过 `McpGateway.execute`，而不是让 Agent 直接获得客户端。
