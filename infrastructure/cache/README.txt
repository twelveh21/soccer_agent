Redis 缓存与短期状态层

本目录的职责：
- redis_client.py：统一创建、复用和关闭 Redis 异步连接。
- contracts.py：定义缓存实现应具备的最小 get/set 接口。

当前阶段只完成 Redis 服务和连接层。
下一阶段将把实时足球数据写入带 TTL 的 Redis 缓存，并加入 API 限流。
Redis 不保存正式用户资料、长期聊天历史或唯一事实来源；这些仍属于 PostgreSQL。
