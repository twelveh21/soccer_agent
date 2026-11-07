# Soccer Agent 体验包

这是本地运行版本，用于演示足球数据查询、战术研究、独立对话、文件材料解析和本地战术知识库。

## 快速启动

1. 安装 Python 3.13。
2. 将 `.env.example` 复制为 `.env`，填写自己的 DashScope、football-data.org、Tavily Key。
3. 安装依赖：`python -m pip install -r agent_base/requirements.txt`
4. 启动：`python -m uvicorn service.app:app --host 127.0.0.1 --port 8000 --reload`
5. 在浏览器打开 `http://127.0.0.1:8000/`。

## Docker 启动

配置 `.env` 后运行：`docker compose up --build`。

## 使用边界

- 不要分享 `.env`，它含有个人 API Key。
- 当前版本适合本地演示和小范围体验，不提供账号登录、公共 HTTPS、访问限流或多租户隔离。
- 图片分析需要账户具有视觉模型权限；文本、Markdown 和 PDF 提取不依赖视觉模型。
