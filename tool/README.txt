tool：足球 Agent 的工具层

本目录按职责拆分：
- langchain_tools：直接注册给 LangChain Agent 的 Tool Calling 函数。
- clients：与外部服务通信的 HTTP 客户端，负责认证、缓存、重试和限流。
- services：组合多个客户端请求形成业务能力，未来可直接被 LangGraph 节点调用。
- shared：所有工具复用的数据结构、SQLite 缓存等基础组件。

__init__.py 使 tool 成为 Python 包。
