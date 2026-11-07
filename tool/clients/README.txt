clients：外部 API 通信层

async_football_data_client.py 封装 football-data.org 的异步请求能力：
- SQLite TTL 缓存。
- HTTP 超时。
- 429 和 5xx 的有限重试与指数退避。
- Semaphore 并发限制。
- HTTP Client 生命周期管理。

本目录不负责“用户要查什么”，只负责可靠地向外部服务请求数据。

async_tavily_search_client.py 封装 Tavily 网页搜索的异步请求能力，具备相同的
缓存、超时、重试和并发限制策略。
