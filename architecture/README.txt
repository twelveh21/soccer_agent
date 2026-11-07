项目架构总览

本目录保存跨模块架构说明与演进约束，而不放业务代码。

当前主链路：agent_base/agent.py。
未来模块通过各自的 contracts.py（契约）与主链路连接，避免把 API、RAG、缓存或服务代码直接耦合进 LangGraph 节点。

实现状态约定：
- implemented：已有可运行实现。
- scaffolded：接口、数据模型、测试入口已建立，具体适配器待接入。
- planned：仅在文档中规划，尚未建立代码。
