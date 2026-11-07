services：足球业务组合层

async_basic_data_service.py 将多个底层 API 请求组合为可直接使用的业务能力。

当前能力：
- get_competition_overview：并发获取一个赛事的积分榜和球队列表；允许部分失败，并返回统一数据格式、warnings 与可核验 claims。
- search_current_football_info：异步检索伤停、转会和新闻等网页证据，并将结果转换为统一来源化格式。

后续 LangGraph 节点会调用这一层，而不是直接了解 HTTP Endpoint 细节。
