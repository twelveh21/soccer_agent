"""足球 Agent 的 FastAPI 服务入口，复用既有 LangGraph 核心。"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import Depends, File, FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from memory.contracts import MemoryRecord
from memory.sqlite_memory_store import SqliteMemoryStore
from service.api.schemas import HumanResumeRequest, ResearchRequest, ResearchResponse
from service.api.routes.auth import router as auth_router
from service.api.routes.observability import router as observability_router
from service.api.schemas import (
    BackgroundTaskResponse,
    ConversationMessageResponse,
    DemoTaskRequest,
    DocumentDetailResponse,
    DocumentImportResponse,
    ResearchRunDetailResponse,
)
from service.streaming.events import ResearchStreamEvent
from service.streaming.sse import encode_sse
from multimodal.contracts import VisualInput
from multimodal.evidence_context import build_user_material_context
from multimodal.vision_service import IMAGE_TYPES, MAX_UPLOAD_BYTES, TEXT_TYPES, UploadAnalysisError, analyze_image, extract_text_content, validate_upload_content
from knowledge_base.learning.source_registry import list_authoritative_sources
from agent_base.model_gateway import ModelGateway
from infrastructure.database.repositories.research_runs import ResearchRunRepository
from infrastructure.database.repositories.conversations import ConversationRepository
from infrastructure.database.repositories.background_tasks import BackgroundTaskRepository
from infrastructure.database.repositories.documents import DocumentRepository
from infrastructure.database.repositories.users import UserSnapshot
from infrastructure.database.session import build_session_factory
from infrastructure.cache.rate_limiter import check_fixed_window_limit
from infrastructure.cache.redis_client import close_redis_client, ping_redis
from service.auth.dependencies import get_current_user
from service.auth.permissions import require_roles
from service.auth.roles import ROLE_ADMIN, ROLE_EDITOR
from infrastructure.observability.tracing import add_current_span_attributes, configure_telemetry, current_trace_id, get_tracer

app = FastAPI(title="Soccer Agent API", version="1.0.0")
app.include_router(auth_router)
app.include_router(observability_router)
configure_telemetry(app)
memory_store = SqliteMemoryStore(PROJECT_ROOT / "data" / "soccer_memory.db")
WEB_UI_PATH = PROJECT_ROOT / "frontend" / "index.html"
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
# 网页演示先默认使用稳定的基础回答。复杂 Planner 研究可在流程稳定后显式开启。
ENABLE_RESEARCH_WORKFLOW = os.getenv("SOCCER_AGENT_ENABLE_RESEARCH", "false").lower() == "true"
# 基础模式只初始化模型网关，不导入会创建 Graph、Tool Agent 与 SQLite Checkpointer 的 agent.py。
basic_model_gateway = ModelGateway.from_env()
# Repository 负责数据库读写；路由只编排 HTTP 与 Agent 流程，不直接写 SQL。
research_run_repository = ResearchRunRepository(build_session_factory())
conversation_repository = ConversationRepository(build_session_factory())
background_task_repository = BackgroundTaskRepository(build_session_factory())
document_repository = DocumentRepository(build_session_factory())
# 交互式研究尚在 FastAPI 进程内执行；用 run_id 保存 Task 引用，避免浏览器断开时取消研究。
# 多实例生产部署时会迁移为 Celery / Temporal 等可跨进程恢复的执行器。
active_research_tasks: dict[str, asyncio.Task[ResearchResponse]] = {}
# Human-in-the-loop 的 Graph 句柄需保留到用户补充后恢复；Temporal 接入后可替换为跨进程工作流句柄。
pending_human_teams: dict[str, tuple[object, str]] = {}


@app.middleware("http")
async def attach_trace_id(request, call_next):
    """把当前 OpenTelemetry Trace ID 返回给调用方，方便关联网页报错与后端轨迹。

    参数：
    - request：当前 HTTP 请求；中间件不读取其正文，避免干扰上传和 SSE。
    - call_next：FastAPI 提供的下一个处理函数。

    实现逻辑：先交给后续路由和自动插桩执行，再从当前 Span 读取 trace_id 写入响应头；
    无追踪上下文时静默省略，不影响普通接口。
    """
    response = await call_next(request)
    trace_id = current_trace_id()
    if trace_id:
        response.headers["X-Trace-Id"] = trace_id
    return response


@app.on_event("shutdown")
async def close_infrastructure_clients() -> None:
    """在 FastAPI 进程结束时关闭 Redis 连接池。

    参数：无。

    实现逻辑：调用 Redis 连接层的关闭函数；PostgreSQL Engine 由进程结束回收，后续可在此扩展显式关闭。
    """
    await close_redis_client()


class SaveMemoryRequest(BaseModel):
    """前端在用户明确点击保存后提交的笔记或偏好。"""
    # explicit_consent 防止客户端把普通对话悄悄变成长时记忆。
    session_id: str = Field(min_length=1, max_length=128)
    scope: str
    kind: str
    content: str = Field(min_length=1, max_length=2000)
    explicit_consent: bool = False


def get_team(session_id: str | None):
    """延迟导入 Agent，保证健康检查不依赖模型密钥或 LangGraph 初始化。"""
    # API 模块本身可被测试；真实请求才加载模型网关和 Graph 运行时。
    from agent_base.agent import SoccerResearchTeam
    return SoccerResearchTeam(session_id=session_id)


async def basic_fallback_answer(question: str) -> str:
    """复杂研究链路异常时提供稳定的基础回答，保证网页不会只返回报错。"""
    # 该降级路径不调用 Planner、RAG 或网页工具，专门隔离结构化流程的失败影响。
    # 它不能声称查询过实时来源，因此提示词要求明确区分通用解释与待核验事实。
    prompt = (
        "你是足球助手。请用清晰、简短的中文回答用户问题，控制在 180 字以内。"
        "当前只能提供通用足球知识或基于问题的分析，不得假装已经查询实时赛程、伤停、转会或比赛数据。"
        "若问题需要具体比赛事实，请明确说明需要进一步查询官方或实时来源。\n\n"
        f"用户问题：{question}"
    )
    response = await asyncio.to_thread(
        basic_model_gateway.get_model("basic_query").invoke,
        [{"role": "user", "content": prompt}],
    )
    content = getattr(response, "content", response)
    return content if isinstance(content, str) else str(content)


def local_basic_answer(question: str) -> str:
    """网页基础模式的即时回答，不依赖模型或外部服务。"""
    # 先保证演示入口随时可用；复杂 Agent 与实时工具恢复后再由路由切换过去。
    lowered = question.lower()
    tactical_markers = ("战术", "分析", "阵型", "逼抢", "压迫", "出球", "打法")
    if any(marker in lowered for marker in tactical_markers):
        return (
            "基础战术分析：阿森纳通常强调控球、边路与肋部的联动，以及丢球后的快速反抢。"
            "进攻时，中场会寻找前场接应点，边后卫和边锋通过不同站位拉开宽度；防守时则尽量在前场限制对手向中路推进。"
            "要分析某一场比赛，还需要对手、日期、阵容和比赛片段等具体材料。"
        )
    return (
        f"已收到你的问题：“{question}”。当前网页运行在基础稳定模式，"
        "可以先提供通用足球说明；赛程、伤停、转会、首发等实时事实需要后续接入数据工具后再核验。"
    )


@app.get("/health")
async def health() -> dict[str, str]:
    """提供无需模型和外部 API 的容器健康检查。"""
    # 健康检查只验证服务进程活着，不能假装外部供应商一定正常。
    return {"status": "ok", "service": "soccer-agent"}


@app.get("/health/infrastructure")
async def infrastructure_health() -> dict[str, str]:
    """检查 Redis 这一可选基础服务是否可连接。

    参数：无。

    实现逻辑：Redis PING 成功则返回 ok；失败只报告 degraded，不影响基础 /health 和普通页面可用。
    """
    try:
        await ping_redis()
    except Exception:
        return {"status": "degraded", "redis": "unavailable"}
    return {"status": "ok", "redis": "available"}


@app.get("/", include_in_schema=False)
async def web_ui() -> FileResponse:
    """返回用户实际使用的聊天页面，而不是暴露开发接口文档。"""
    # 页面与 API 同域运行，因此浏览器可直接调用 /v1/research，不需要额外配置跨域规则。
    return FileResponse(WEB_UI_PATH)


@app.get("/v1/tactical-library")
async def tactical_library() -> dict[str, object]:
    """展示系统会优先检索的公开战术学习来源与使用边界。"""
    # 只返回资料源目录；实际研究时再按问题检索，避免无差别下载文章正文。
    return {"sources": list_authoritative_sources(), "notice": "来源用于战术框架学习，具体比赛事实仍需独立核验。"}


async def prepare_research_request(request: ResearchRequest) -> tuple[str, str, str]:
    """创建一项可追踪的研究任务，并保存用户问题。

    参数：
    - request：网页或 API 客户端提交的研究请求。

    实现逻辑：先做限流，再解析匿名会话、创建或获取 conversation，随后写入用户消息和
    status=running 的 research_run。返回的三个 ID 会被普通接口和 SSE 接口共同使用。
    """
    # 未登录阶段先使用浏览器 session_id；未传时由服务端生成一次性匿名 ID，后续 JWT 会替代它。
    client_session_id = request.session_id or f"anonymous-{uuid4().hex}"
    rate_limit = await check_fixed_window_limit(
        "research",
        client_session_id,
        limit=8,
        window_seconds=60,
    )
    if not rate_limit.allowed:
        raise HTTPException(
            status_code=429,
            detail="请求过于频繁，请稍后再试。",
            headers={"Retry-After": str(rate_limit.retry_after_seconds)},
        )
    conversation_id = await asyncio.to_thread(
        conversation_repository.get_or_create,
        client_session_id,
        request.question[:18],
    )
    # 先保存用户消息和 running 任务，即使浏览器中途断开也能留下可追踪记录。
    await asyncio.to_thread(conversation_repository.append_message, conversation_id, "user", request.question)
    database_run_id = await asyncio.to_thread(research_run_repository.create, request.question, conversation_id)
    # 将业务 run_id 写入当前请求 Span，之后能从 HTTP Trace 直接定位到 PostgreSQL 研究记录。
    add_current_span_attributes(research_run_id=database_run_id, conversation_id=conversation_id)
    return client_session_id, conversation_id, database_run_id


async def execute_research_request(
    request: ResearchRequest,
    client_session_id: str,
    conversation_id: str,
    database_run_id: str,
) -> ResearchResponse:
    """执行已创建的研究任务，并把最终结果写回数据库。

    参数：
    - request：原始问题和可选上传材料摘要。
    - client_session_id：匿名浏览器会话 ID，用于隔离 Agent 上下文。
    - conversation_id：PostgreSQL 对话 ID，用于保存助手回答。
    - database_run_id：已处于 running 状态的研究任务 ID。

    实现逻辑：根据配置走基础稳定回答或 LangGraph 研究流程；无论成功、降级或失败，
    都更新同一条 research_runs 记录，保证前端可按 run_id 恢复结果。
    """
    question = request.question
    if request.attachment_context:
        question += "\n\n【用户上传材料的已解析观察】\n" + request.attachment_context + "\n请将其视为用户材料，说明其局限，不要把它当作已核验的实时事实。"
    if not ENABLE_RESEARCH_WORKFLOW:
        # 先保证基础产品体验：普通对话不等待模型、工具或复杂工作流。
        answer = local_basic_answer(question)
        await asyncio.to_thread(
            research_run_repository.mark_success,
            database_run_id,
            answer,
            "local_basic",
            {"mode": "local_basic", "used_agent_workflow": False},
        )
        await asyncio.to_thread(conversation_repository.append_message, conversation_id, "assistant", answer)
        return ResearchResponse(
            run_id=database_run_id,
            status="success",
            answer=answer,
            limitations=["当前网页运行在基础稳定模式，未调用实时数据与复杂研究工作流；具体赛程、伤停和比赛事实需后续核验。"],
        )

    team = get_team(client_session_id)
    # 业务 Span 不记录问题正文，只记录 run_id、路由和是否降级，便于定位慢任务且保护用户输入。
    with get_tracer().start_as_current_span("soccer.agent.workflow") as workflow_span:
        workflow_span.set_attribute("soccer.research_run_id", database_run_id)
        workflow_span.set_attribute("soccer.workflow_enabled", True)
        try:
            agent_result = await team.aanswer(question)
            from agent_base.human_loop import HumanInputRequired
            if isinstance(agent_result, HumanInputRequired):
                prompt = agent_result.question
                pending_human_teams[database_run_id] = (team, conversation_id)
                await asyncio.to_thread(
                    research_run_repository.mark_waiting_input,
                    database_run_id,
                    prompt,
                    {"mode": "human_in_the_loop", "missing_fields": agent_result.missing_fields, "reason": agent_result.reason},
                )
                return ResearchResponse(
                    run_id=database_run_id,
                    status="needs_input",
                    answer=prompt,
                    limitations=[agent_result.reason],
                )
            answer = agent_result
            limitations = ["回答依据当前可取得的数据与证据；实时信息请以来源时间为准。"]
            report = team.last_run_report() or {}
            route = report.get("route")
            evidence_summary = {
                "agent_run_id": team.last_run_id,
                "route": route,
                "node_sequence": report.get("node_sequence", []),
                "research_attempts": report.get("research_attempts", 0),
            }
            # 模型调用摘要来自既有运行报告；只记录统计数，不记录 prompt、completion 正文或密钥。
            model_calls = report.get("model_calls", [])
            input_tokens = sum(int(call.get("input_tokens") or 0) for call in model_calls)
            output_tokens = sum(int(call.get("output_tokens") or 0) for call in model_calls)
            model_duration_ms = float(report.get("model_duration_ms") or 0)
            estimated_cost_usd = report.get("estimated_cost_usd")
            workflow_span.set_attribute("soccer.model.call_count", len(model_calls))
            workflow_span.set_attribute("soccer.model.input_tokens", input_tokens)
            workflow_span.set_attribute("soccer.model.output_tokens", output_tokens)
            workflow_span.set_attribute("soccer.model.duration_ms", model_duration_ms)
            if estimated_cost_usd is not None:
                workflow_span.set_attribute("soccer.model.estimated_cost_usd", float(estimated_cost_usd))
        except Exception as workflow_error:
            # Planner 或第三方工具异常时仍保持基本问答可用，避免复杂能力拖垮产品入口。
            workflow_span.record_exception(workflow_error)
            try:
                answer = await basic_fallback_answer(question)
            except Exception as fallback_error:
                await asyncio.to_thread(
                    research_run_repository.mark_failed,
                    database_run_id,
                    "足球研究与基础降级回答均未完成。",
                )
                raise HTTPException(status_code=502, detail="足球研究与基础回答均暂时不可用，请稍后重试。") from fallback_error
            limitations = ["当前研究工作流未完成，以下为未调用实时数据工具的基础回答；实时事实请另行核验。"]
            route = "fallback"
            evidence_summary = {"mode": "fallback", "used_agent_workflow": False}
            workflow_span.set_attribute("soccer.degraded", True)
        workflow_span.set_attribute("soccer.route", route or "unknown")
    await asyncio.to_thread(
        research_run_repository.mark_success,
        database_run_id,
        answer,
        route,
        evidence_summary,
    )
    await asyncio.to_thread(conversation_repository.append_message, conversation_id, "assistant", answer)
    return ResearchResponse(
        run_id=database_run_id, status="success", answer=answer,
        limitations=limitations,
    )


@app.post("/v1/research", response_model=ResearchResponse)
async def research(request: ResearchRequest) -> ResearchResponse:
    """以非流式方式完成一次足球研究请求。

    参数：
    - request：研究问题、会话 ID 与可选上传材料摘要。

    实现逻辑：先调用准备函数落库获得稳定 run_id，再调用执行函数完成 Agent 工作流；
    两个步骤拆开后，SSE 能在真正开始研究前就把 run_id 交给浏览器。
    """
    client_session_id, conversation_id, database_run_id = await prepare_research_request(request)
    return await execute_research_request(request, client_session_id, conversation_id, database_run_id)


@app.post("/v1/research-runs/{run_id}/resume", response_model=ResearchResponse)
async def resume_research(run_id: str, request: HumanResumeRequest) -> ResearchResponse:
    """接收用户补充并从同一 LangGraph checkpoint 恢复暂停研究。

    参数：run_id 是等待补充的 PostgreSQL 研究任务 ID；request 含用户补充文本。
    实现：读取进程内保留的团队句柄后调用 aresume；成功时更新原任务和对话，仍需补充时维持 needs_input。
    """
    pending = pending_human_teams.get(run_id)
    if pending is None:
        raise HTTPException(status_code=409, detail="该暂停任务无法在当前服务进程恢复，请重新提交研究问题。")
    team, conversation_id = pending
    agent_result = await team.aresume(request.clarification)
    from agent_base.human_loop import HumanInputRequired
    if isinstance(agent_result, HumanInputRequired):
        await asyncio.to_thread(research_run_repository.mark_waiting_input, run_id, agent_result.question, {"mode": "human_in_the_loop", "missing_fields": agent_result.missing_fields, "reason": agent_result.reason})
        return ResearchResponse(run_id=run_id, status="needs_input", answer=agent_result.question, limitations=[agent_result.reason])
    pending_human_teams.pop(run_id, None)
    report = team.last_run_report() or {}
    await asyncio.to_thread(research_run_repository.mark_success, run_id, agent_result, report.get("route"), {"agent_run_id": team.last_run_id, "node_sequence": report.get("node_sequence", [])})
    await asyncio.to_thread(conversation_repository.append_message, conversation_id, "assistant", agent_result)
    return ResearchResponse(run_id=run_id, status="success", answer=agent_result, limitations=["回答依据用户补充后的证据范围；具体比赛事实仍需结合来源核验。"])


@app.get("/v1/research-runs/{run_id}", response_model=ResearchRunDetailResponse)
async def get_research_run(run_id: str) -> ResearchRunDetailResponse:
    """按任务 ID 查询已写入 PostgreSQL 的研究状态和结果。

    参数：
    - run_id：创建研究请求时返回的 PostgreSQL 任务 ID。

    实现逻辑：把同步数据库读取放进线程，避免阻塞 FastAPI 的异步事件循环；查不到返回 404。
    """
    record = await asyncio.to_thread(research_run_repository.get, run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="未找到该研究任务。")
    return ResearchRunDetailResponse(**record.__dict__)


@app.get("/v1/conversations/{client_session_id}/messages", response_model=list[ConversationMessageResponse])
async def get_conversation_messages(client_session_id: str) -> list[ConversationMessageResponse]:
    """按浏览器 session_id 读取 PostgreSQL 中保存的对话历史。

    参数：
    - client_session_id：前端创建新对话时保存的 ID。

    实现逻辑：使用 Repository 查询消息快照；当前用于匿名本地会话，JWT 接入后会追加用户权限校验。
    """
    messages = await asyncio.to_thread(conversation_repository.list_messages, client_session_id)
    return [ConversationMessageResponse(**message.__dict__) for message in messages]


@app.post("/v1/background-tasks/demo", response_model=BackgroundTaskResponse, status_code=202)
async def create_demo_background_task(
    request: DemoTaskRequest,
    current_user: UserSnapshot = Depends(require_roles(ROLE_ADMIN)),
) -> BackgroundTaskResponse:
    """创建一项演示后台任务，验证完整队列链路。

    参数：
    - request.message：传给 Worker 的短文本。
    - current_user：已通过 JWT 与 admin 角色检查的调用者。

    实现逻辑：只有 admin 可创建运维演示任务；通过后写 queued 记录并投递 Celery，返回 202 表示已接收、尚未保证完成。
    """
    task_id = await asyncio.to_thread(
        background_task_repository.create,
        "demo_echo",
        {"message": request.message},
    )
    try:
        from worker.tasks import demo_echo_task

        demo_echo_task.delay(task_id, request.message)
    except Exception as error:
        await asyncio.to_thread(background_task_repository.mark_failed, task_id, "任务未能投递到队列。")
        raise HTTPException(status_code=503, detail="后台任务队列暂时不可用。") from error
    return BackgroundTaskResponse(task_id=task_id, task_type="demo_echo", status="queued")


@app.get("/v1/background-tasks/{task_id}", response_model=BackgroundTaskResponse)
async def get_background_task(task_id: str) -> BackgroundTaskResponse:
    """查询一项后台任务的数据库状态。

    参数：
    - task_id：创建任务接口返回的数据库任务 ID。

    实现逻辑：从 PostgreSQL 读取任务快照；查不到时返回 HTTP 404，前端可据此停止轮询。
    """
    record = await asyncio.to_thread(background_task_repository.get, task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="未找到该后台任务。")
    return BackgroundTaskResponse(
        task_id=record.task_id,
        task_type=record.task_type,
        status=record.status,
        result=record.result,
        error_message=record.error_message,
        attempt_count=record.attempt_count,
    )


async def research_events(request: ResearchRequest) -> AsyncIterator[str]:
    """生成一轮研究的 SSE 进度和最终结果。

    参数：
    - request：前端传入的问题、匿名会话 ID 与可选上传材料摘要。

    实现逻辑：先创建 PostgreSQL 任务并立即回传真实 run_id，再创建独立异步任务执行
    研究。浏览器断开只会停止观看 SSE，不会取消被 ``asyncio.shield`` 保护的研究任务；
    前端刷新后可调用研究状态接口恢复最终结果。
    """
    try:
        client_session_id, conversation_id, database_run_id = await prepare_research_request(request)
    except HTTPException as error:
        message = error.detail if isinstance(error.detail, str) else "研究请求暂时无法创建。"
        yield encode_sse(ResearchStreamEvent(event="error", run_id=uuid4().hex, data={"message": message}))
        return

    # create_task 将执行权从 HTTP 流中分离；done callback 用于释放进程内引用，避免内存持续增长。
    task = asyncio.create_task(
        execute_research_request(request, client_session_id, conversation_id, database_run_id),
        name=f"research-{database_run_id}",
    )
    active_research_tasks[database_run_id] = task
    task.add_done_callback(lambda _: active_research_tasks.pop(database_run_id, None))
    yield encode_sse(
        ResearchStreamEvent(
            event="run_started",
            run_id=database_run_id,
            data={"message": "研究任务已创建，可在断线后恢复结果。"},
        )
    )
    await asyncio.sleep(0)
    yield encode_sse(
        ResearchStreamEvent(
            event="progress",
            run_id=database_run_id,
            data={"message": "研究任务已启动，正在整理可用资料。"},
        )
    )
    try:
        # shield 阻止客户端关闭 SSE 时把取消信号传递给真正的 Agent 任务。
        result = await asyncio.shield(task)
        event_name = "needs_human" if result.status == "needs_input" else "final"
        yield encode_sse(
            ResearchStreamEvent(
                event=event_name,
                run_id=result.run_id,
                data={
                    "answer": result.answer,
                    "status": result.status,
                    "limitations": result.limitations,
                },
            )
        )
    except HTTPException as error:
        # HTTPException 的 detail 面向用户，适合转换为安全的 SSE 错误文案。
        message = error.detail if isinstance(error.detail, str) else "研究请求暂时无法完成。"
        yield encode_sse(ResearchStreamEvent(event="error", run_id=database_run_id, data={"message": message}))
    except Exception:
        # 不把内部堆栈、提示词或第三方响应原样发送给浏览器。
        yield encode_sse(
            ResearchStreamEvent(
                event="error",
                run_id=database_run_id,
                data={"message": "足球研究暂时无法完成，请稍后重试。"},
            )
        )


@app.post("/v1/research/stream")
async def stream_research(request: ResearchRequest) -> StreamingResponse:
    """以 Server-Sent Events 发送安全的研究进度与最终答案。

    参数：
    - request：研究请求；结构与普通 ``/v1/research`` 接口保持一致。

    实现逻辑：返回不缓冲的 HTTP 文本流；浏览器会在每收到一帧事件时更新等待提示，
    最后一帧才包含完整答案。SSE 仅用于服务端到网页的单向进度推送。
    """
    # Cache-Control 与 X-Accel-Buffering 共同避免代理/浏览器攒到结束才一次性显示事件。
    return StreamingResponse(
        research_events(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/v1/uploads/analyze")
async def upload_and_analyze(file: UploadFile = File(...)) -> dict[str, object]:
    """安全保存用户上传材料，并返回文本提取或视觉模型的可审阅观察。"""
    # 上传材料需由用户后续主动附带到问题中；系统不会自动作为长期记忆保存。
    content_type = file.content_type or "application/octet-stream"
    if content_type not in IMAGE_TYPES | TEXT_TYPES:
        raise HTTPException(status_code=415, detail="仅支持 PNG、JPG、WebP、TXT、Markdown 和 PDF。")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文件不能为空，且大小不能超过 8 MB。")
    try:
        validate_upload_content(content, content_type)
    except UploadAnalysisError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    input_id = uuid4().hex
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "upload").suffix.lower()[:10]
    storage_path = UPLOAD_DIR / f"{input_id}{suffix}"
    storage_path.write_bytes(content)
    input_item = VisualInput(input_id=input_id, kind="tactical_diagram", storage_ref=str(storage_path), user_claimed_context=None)
    try:
        if content_type in IMAGE_TYPES:
            evidence = await analyze_image(input_item, content, content_type)
        else:
            extracted = extract_text_content(content, content_type).strip()
            if not extracted:
                raise UploadAnalysisError("未能从该文本或 PDF 中提取可读内容。")
            evidence = {"input_id": input_id, "observations": [extracted], "confidence": 0.8, "limitations": ["文本提取来自用户上传材料，尚未经过外部来源核验。"]}
    except UploadAnalysisError as error:
        storage_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(error)) from error
    evidence_payload = evidence.model_dump() if hasattr(evidence, "model_dump") else evidence
    return {
        "upload_id": input_id,
        "filename": file.filename,
        "content_type": content_type,
        "evidence": evidence_payload,
        "attachment_context": build_user_material_context(evidence_payload, file.filename or "未命名文件"),
    }


@app.post("/v1/documents/import", response_model=DocumentImportResponse, status_code=202)
async def import_tactical_document(
    file: UploadFile = File(...),
    current_user: UserSnapshot = Depends(require_roles(ROLE_EDITOR, ROLE_ADMIN)),
) -> DocumentImportResponse:
    """提交 TXT、Markdown 或 PDF 到后台资料导入队列。

    参数：
    - file：用户上传的战术资料；只支持可提取文本的 TXT、Markdown、PDF。
    - current_user：已通过 JWT 和 editor/admin 角色检查的资料维护者。

    实现逻辑：FastAPI 只验证并保存原文件、创建 documents 和 background_tasks 记录，
    然后投递 Celery；文本提取、切块和入库全部由 Worker 在后台完成。普通 user 不能把资料写入共享知识库。
    """
    content_type = file.content_type or "application/octet-stream"
    if content_type not in TEXT_TYPES:
        raise HTTPException(status_code=415, detail="资料导入仅支持 TXT、Markdown 和 PDF。")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文件不能为空，且大小不能超过 8 MB。")

    input_id = uuid4().hex
    suffix = Path(file.filename or "document").suffix.lower()[:10]
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    storage_key = f"uploads/{input_id}{suffix}"
    (PROJECT_ROOT / "data" / storage_key).write_bytes(content)
    document_id = await asyncio.to_thread(
        document_repository.create,
        file.filename or "untitled",
        content_type,
        storage_key,
        current_user.user_id,
    )
    task_id = await asyncio.to_thread(
        background_task_repository.create,
        "document_ingestion",
        {"document_id": document_id},
    )
    try:
        from worker.tasks import ingest_document_task

        ingest_document_task.delay(task_id, document_id)
    except Exception as error:
        await asyncio.to_thread(document_repository.mark_failed, document_id, "资料导入任务未能投递。")
        await asyncio.to_thread(background_task_repository.mark_failed, task_id, "资料导入任务未能投递。")
        raise HTTPException(status_code=503, detail="后台资料导入队列暂时不可用。") from error
    return DocumentImportResponse(document_id=document_id, task_id=task_id, document_status="queued", task_status="queued")


@app.get("/v1/documents/{document_id}", response_model=DocumentDetailResponse)
async def get_document_import_status(
    document_id: str,
    current_user: UserSnapshot = Depends(get_current_user),
) -> DocumentDetailResponse:
    """查询一份资料的后台导入状态。

    参数：
    - document_id：提交导入接口返回的文档 ID。
    - current_user：已登录用户；当前共享资料库允许所有登录用户查看导入状态。

    实现逻辑：从 PostgreSQL 读取导入状态、切块数量和元数据；后续前端可轮询或通过 SSE 展示进度。
    """
    document = await asyncio.to_thread(document_repository.get, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="未找到该资料文档。")
    return DocumentDetailResponse(
        document_id=document.document_id,
        filename=document.filename,
        content_type=document.content_type,
        ingest_status=document.ingest_status,
        chunk_count=document.chunk_count,
        metadata=document.metadata_json,
    )


@app.post("/v1/memories", response_model=MemoryRecord)
async def save_memory(request: SaveMemoryRequest) -> MemoryRecord:
    """仅在用户明确同意后保存一条偏好、笔记或事件记忆。"""
    # Agent 不会自动调用此接口，明确同意是保存的必要条件。
    if not request.explicit_consent:
        raise HTTPException(status_code=400, detail="必须由用户明确确认后才能保存记忆。")
    try:
        record = MemoryRecord(memory_id=uuid4().hex, scope=request.scope, kind=request.kind, content=request.content)
    except Exception as error:
        raise HTTPException(status_code=422, detail="记忆类型或范围不合法。") from error
    return memory_store.save(record, session_id=request.session_id)


@app.get("/v1/memories/{session_id}", response_model=list[MemoryRecord])
async def list_memories(session_id: str) -> list[MemoryRecord]:
    """读取当前会话可见的记忆和项目笔记。"""
    # 这里按作用域过滤，不返回其他用户的 session 级记录。
    return memory_store.list_for_session(session_id)


@app.delete("/v1/memories/{memory_id}")
async def delete_memory(memory_id: str) -> dict[str, bool]:
    """删除用户指定的一条已保存记忆。"""
    # 删除结果显式返回，方便前端在用户撤回保存时更新状态。
    return {"deleted": memory_store.delete(memory_id)}
