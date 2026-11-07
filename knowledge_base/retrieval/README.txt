高级 RAG：检索层

本文件夹把战术资料转换为 Agent 可使用、可引用的 Evidence，而不是让模型直接背诵文档。

- `local_tactical_retriever.py`：旧的轻量标签/标题/正文加权检索，适合快速理解与回归测试。
- `bm25_tactical_retriever.py`：标准 BM25 关键词检索。它会根据“词在当前资料里的稀有程度、出现次数、资料长度”评分，适合术语明确的战术问题。
- `vector_tactical_retriever.py`：本地稀疏向量基线，用余弦相似度比较问题与知识块；当前不调用外部 embedding API，方便离线开发与测试。
- `rrf.py`：RRF 融合器。它不直接比较两种不同分数，而是根据各自排名融合候选。
- `advanced_tactical_retriever.py`：高级检索统一入口，负责运行 BM25 与向量通道并得到最终候选。
- `reranker.py`：只对 RRF 已选出的少量候选做二次排序，当前为本地可解释基线；未来可替换为 cross-encoder 或 LLM reranker。
- `contracts.py`：检索请求和证据片段的共同格式；上层不需要知道底层是 BM25、向量库还是未来的 reranker。

当前阶段已完成 BM25、离线稀疏向量基线、RRF、轻量 reranker 和引用校验。稀疏向量与轻量 reranker 都是本地开发基线，不能假装等同于真实 embedding 或 cross-encoder；后续可在不改 Agent 上层代码的前提下替换为 DashScope 或本地模型。引用校验位于 `knowledge_base/citations/validator.py`：回答中写出的 citation_id 必须属于本轮 Evidence，否则会返回未知引用清单给 Critic/服务层处理。
