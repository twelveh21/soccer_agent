"""生成足球 Agent 全量骨架说明文档，仅用于项目文档构建。"""

from __future__ import annotations

import os
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


OUTPUT_PATH = Path(
    os.getenv(
        "SOCCER_AGENT_ARCHITECTURE_DOC_PATH",
        str(Path.home() / "Desktop" / "足球Agent全量架构与骨架说明.docx"),
    )
)


def set_cell_shading(cell: object, fill: str) -> None:
    """为表格单元格写入底色，增强表头与正文的可读性。"""
    # python-docx 没有高层单元格底色 API，因此在这里一次性封装底层 XML 细节。
    tc_pr = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    tc_pr.append(shading)


def set_cell_margins(cell: object, top: int = 100, start: int = 130, bottom: int = 100, end: int = 130) -> None:
    """增加单元格内边距，避免文字紧贴边框。"""
    # Word 的单元格边距单位是 twips；这里统一封装，保持所有表格的呼吸感一致。
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    margins = tc_pr.first_child_found_in("w:tcMar")
    if margins is None:
        margins = OxmlElement("w:tcMar")
        tc_pr.append(margins)
    for side, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = margins.find(qn(f"w:{side}"))
        if node is None:
            node = OxmlElement(f"w:{side}")
            margins.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def configure_run(run: object, size: float = 10.5, bold: bool = False, color: str = "000000") -> None:
    """统一设置中文正文的字体、字号、粗细和颜色。"""
    # 同时指定 eastAsia 字体，保证中文在 Word 和 LibreOffice 中保持一致。
    run.font.name = "Microsoft YaHei"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    run.font.size = Pt(size)
    run.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)


def remove_paragraph_borders(paragraph: object) -> None:
    """移除内置 Title 样式可能携带的主题色底边框。"""
    # Word 的某些 Title 样式会自动显示蓝线；标题仍保留 Title 样式，但视觉上只使用留白和字重。
    p_pr = paragraph._p.get_or_add_pPr()
    borders = p_pr.find(qn("w:pBdr"))
    if borders is not None:
        p_pr.remove(borders)


def add_paragraph(document: Document, text: str, *, bold_lead: str | None = None) -> None:
    """加入一段可读性优先的正文，可选加粗引导语。"""
    # 分开 lead 和正文，读者能快速扫描“结论、原因、做法、作用”等信息。
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(7)
    paragraph.paragraph_format.line_spacing = 1.38
    if bold_lead:
        lead = paragraph.add_run(bold_lead)
        configure_run(lead, bold=True)
    body = paragraph.add_run(text)
    configure_run(body)


def add_heading(document: Document, text: str, level: int) -> None:
    """加入黑色分级标题并设置自然留白。"""
    # 统一使用内置 Heading 样式，Word 可自动识别结构，后续也可生成目录。
    paragraph = document.add_heading(text, level=level)
    paragraph.paragraph_format.space_before = Pt(14 if level == 1 else 9)
    paragraph.paragraph_format.space_after = Pt(7)
    for run in paragraph.runs:
        configure_run(run, 15 if level == 1 else 12, bold=True)


def add_table(document: Document, headers: list[str], rows: list[list[str]], widths: list[float]) -> None:
    """加入带深色表头、内边距和交替行底色的说明表。"""
    # 表格只放便于横向比较的字段，长篇逻辑仍使用段落说明。
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.autofit = False
    header_cells = table.rows[0].cells
    for index, text in enumerate(headers):
        header_cells[index].width = Cm(widths[index])
        set_cell_shading(header_cells[index], "1F4E78")
        set_cell_margins(header_cells[index])
        paragraph = header_cells[index].paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = paragraph.add_run(text)
        configure_run(run, 9.5, bold=True, color="FFFFFF")
    for row_index, row in enumerate(rows):
        cells = table.add_row().cells
        for index, text in enumerate(row):
            cells[index].width = Cm(widths[index])
            set_cell_margins(cells[index])
            if row_index % 2 == 1:
                set_cell_shading(cells[index], "F3F7FA")
            paragraph = cells[index].paragraphs[0]
            paragraph.paragraph_format.line_spacing = 1.18
            run = paragraph.add_run(text)
            configure_run(run, 9.2)
    document.add_paragraph().paragraph_format.space_after = Pt(2)


def add_module_section(document: Document, title: str, status: str, purpose: str, why: str, how: str, role: str, paths: str) -> None:
    """按同一模板解释一个技术模块，便于初学时建立全局地图。"""
    # 固定“是什么、为什么、怎么做、在系统中的作用”顺序，避免只罗列名词。
    add_heading(document, title, 2)
    add_paragraph(document, f"{status}。{purpose}", bold_lead="当前状态：")
    add_paragraph(document, why, bold_lead="为什么需要它：")
    add_paragraph(document, how, bold_lead="骨架如何设计：")
    add_paragraph(document, role, bold_lead="在整体 Agent 中的作用：")
    add_paragraph(document, paths, bold_lead="代码入口：")


def build_document() -> None:
    """组装并保存完整说明文档。"""
    # 文档是架构说明而非项目宣传，因此每项能力都标明实现状态，避免未来简历表述失真。
    document = Document()
    section = document.sections[0]
    section.top_margin = Cm(2.2)
    section.bottom_margin = Cm(2.1)
    section.left_margin = Cm(2.25)
    section.right_margin = Cm(2.25)

    styles = document.styles
    styles["Normal"].font.name = "Microsoft YaHei"
    styles["Normal"]._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    styles["Normal"].font.size = Pt(10.5)
    title_style_borders = styles["Title"]._element.pPr.find(qn("w:pBdr"))
    if title_style_borders is not None:
        styles["Title"]._element.pPr.remove(title_style_borders)

    title = document.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    remove_paragraph_borders(title)
    title_run = title.add_run("足球 Agent 全量架构与骨架说明")
    configure_run(title_run, 22, bold=True)
    subtitle = document.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle_run = subtitle.add_run("面向实时足球信息与可解释战术研究的多 Agent 学习项目")
    configure_run(subtitle_run, 11, color="555555")
    subtitle.paragraph_format.space_after = Pt(18)

    add_paragraph(document, "这份文档说明足球 Agent 当前的完整可运行版本：每个模块解决什么问题、为什么要这样拆分、一次请求怎样流动、怎样本地验证，以及在面试中应如何准确讲述。它不把外部供应商能力说成项目能力：实时事实仍由 API 和网页证据取得，视觉能力需要用户上传图片和配置视觉模型后才会启用。")

    add_heading(document, "一 当前完成结论", 1)
    add_paragraph(document, "当前完成的是可运行的单机服务化 Agent：LangGraph 主工作流、实时数据工具、异步请求、SQLite 检查点、运行记录、本地战术 RAG、输入护栏、离线评测、FastAPI、SSE、显式 Memory/Note 和 Docker 部署均已有真实代码。Redis、PostgreSQL、第三方观测平台和视觉模型没有被伪装为已接入：它们是可替换的下一阶段基础设施，而不是本版本必须依赖的功能。")
    add_table(document, ["状态", "含义", "本项目示例"], [
        ["implemented", "已有可运行逻辑，并已有测试或运行入口。", "LangGraph 路由、研究循环、异步足球数据、SQLite 运行记录。"],
        ["partially implemented", "基础实现已存在，但距离完整生产能力仍有差距。", "离线工作流评测、运行观测、模型网关。"],
        ["service ready", "可通过 HTTP/SSE 调用，且不复制 Agent 业务逻辑。", "FastAPI、SSE、显式 Memory/Note、Docker 健康检查。"],
        ["extension point", "有明确替换边界，但本版本不依赖外部中间件。", "Redis/PostgreSQL、Langfuse、视觉模型、生产集群。"],
    ], [3.2, 6.0, 7.2])

    add_heading(document, "二 全局运行逻辑", 1)
    add_paragraph(document, "系统先根据问题性质选择低成本且适合的数据路径。赛程、积分榜、名单等结构化问题优先走足球数据工具；实时新闻、伤停、转会等时效信息走网页检索和证据整理；需要解释原因、比较打法或形成研究结论的战术问题才进入多 Agent 研究闭环。这个分层避免让强模型和复杂工作流处理本可直接查询的简单事实。")
    add_table(document, ["阶段", "主要动作", "输出到下一阶段的内容"], [
        ["分类", "识别基础数据、实时信息或战术研究。", "route，决定后续节点。"],
        ["资料获取", "调用 API、网页检索或未来 RAG，并发收集材料。", "可追溯 evidence。"],
        ["研究求解", "Planner 拆任务；Solver 只能基于证据写草案。", "结构化计划与 draft。"],
        ["审阅循环", "Critic 返回 pass、gather_more 或 replan，且受轮次限制。", "review 与安全 warnings。"],
        ["核验与交付", "检查新鲜度、来源和冲突；Finalizer 生成用户答案。", "final_answer、run_id、运行轨迹。"],
    ], [3.0, 7.2, 6.2])

    add_module_section(document, "三 LangGraph 编排与状态管理", "implemented", "LangGraph 是整个系统的流程控制器，当前主图位于 agent_base/agent.py。", "多 Agent 项目最容易出问题的不是某个模型回答不好，而是角色之间传递了什么、何时进入循环、何时必须停止。LangGraph 把这些控制逻辑显式写成节点、状态和边。", "SoccerAgentState 已迁入 graph/state.py，保存 question、input_policy、route、plan、evidence、review、draft、research_attempt 等共享状态。条件边将 classify 的结果送到不同路径；Critic 后的条件边根据 verdict 决定验证、补资料或重新规划。", "它是所有技术模块的总调度层。工具、RAG、缓存和 API 都不应自行改变流程，只能把结果返回给 Graph，由 Graph 决定下一步。", "已运行：agent_base/agent.py、agent_base/graph/state.py。")

    add_module_section(document, "四 多 Agent 研究闭环", "implemented 与 scaffolded", "Planner、Collector、Solver、Critic、Finalizer 形成职责分离的研究团队。", "单一 Agent 往往一边想、一边查、一边下结论，难以检查它是否漏查资料或虚构事实。分角色不是为了展示数量，而是让每个角色有明确的输入、输出和可评测职责。", "Planner 输出 Pydantic 校验的研究计划；Collector 按计划并发取得证据；Solver 没有工具权限，只使用 State 中材料；Critic 输出固定 verdict；Finalizer 根据草案、审阅和质量报告写最终答案。新增 agents/roles.py 统一角色请求和结果模型，后续把实际角色逐步迁入。", "该闭环是项目最重要的简历亮点：既能展示 Plan and Solve，也能展示有上限的 Reflection 和 Replan，而非无限循环的演示型多 Agent。", "已有：agent_base/research_plan.py、research_review.py、research_evidence_collector.py、agent.py；骨架：agent_base/agents/。")

    add_module_section(document, "五 模型网关与成本控制", "partially implemented", "模型网关让不同角色按复杂度选择不同模型，并把模型选择从业务代码中抽离。", "分类、规划和审阅通常需要较快较便宜的模型，复杂综合推理可使用更强的 Solver。若每个节点都用大模型，会提升成本与延迟，也不利于切换供应商。", "现有 ModelGateway 按 role 从环境变量选模型。未来应把 Prompt 版本、调用 Token、延迟、重试和估算费用写入遥测事件；prompts/prompt_registry.py 已建立 Prompt 元数据入口。", "它把模型视为可替换的基础设施：Graph 只声明角色，网关决定使用哪个兼容 OpenAI API 的模型与降级策略。", "已有：agent_base/model_gateway.py；骨架：agent_base/prompts/、infrastructure/observability/。")

    add_module_section(document, "六 工具调用 异步与实时足球数据", "implemented", "工具层负责查询赛程、积分榜、名单、球员资料与网页实时信息，并以统一证据格式返回。", "实时数据不应由模型记忆回答。异步请求、超时、重试、退避和缓存则保证多个资料请求不会串行卡住，也降低对第三方 API 的压力。", "tool/ 下将 LangChain Tool、HTTP Client、业务 Service 和 shared 公共模型分离。客户端处理认证、请求和重试；Service 处理业务组合；LangChain Tool 给模型选择；Evidence Quality 做来源、新鲜度和冲突检查。", "它是 Agent 的“眼睛”，为研究闭环提供可引用事实。后续 Tavily MCP 或其他 MCP 工具可作为新的适配器加入，而不改变 Solver 的证据消费方式。", "已有：tool/clients、tool/services、tool/langchain_tools、tool/shared。")

    add_module_section(document, "七 战术 RAG 知识库", "partially implemented", "战术知识库用于保存并检索相对稳定的足球战术基础框架；当前已有完整可运行的本地 RAG V1，后续再扩展为文章级向量 RAG。", "战术解释常需要跨多篇资料综合，不能只依赖实时 API；但 RAG 不适合分钟级比分和临场伤停，因此它与实时数据工具必须分工。", "seed/tactical_foundations.json 保存原始知识。foundation_ingestion.py 对资料进行 Pydantic 校验和句子级切块，生成 indexes/tactical_foundation_chunks.json。hybrid_tactical_retriever.py 依据标签、标题和正文的不同权重检索切块；local_tactical_retriever.py 将结果包装成 Evidence Envelope。Collector 在 Planner 要求 tactical_rag 时会并发调用它，evaluation/run_tactical_retrieval_evals.py 验证关键问题能命中正确概念。", "它让 Solver 能先理解稳定的战术框架，再结合网页或比赛资料解释具体案例；它绝不应单独证明某场比赛发生了什么。", "已运行：knowledge_base/seed、ingestion、indexes、retrieval、evaluation/run_tactical_retrieval_evals.py；后续：文章导入、向量检索、重排、文章级引用。")

    add_module_section(document, "八 记忆与笔记", "implemented", "记忆层保存用户明确要求保存的偏好、项目笔记或一次性事件，不保存普通聊天和未经核实结论。", "记忆最常见的风险不是技术难，而是自动保存造成隐私泄漏、旧结论污染新回答。因此先实现用户显式确认、作用域隔离和可删除，而不是让模型自行判断什么值得记住。", "memory/contracts.py 约束 scope 与 kind；sqlite_memory_store.py 以短连接保存记录、按 session 或 project 作用域读取、按稳定 ID 删除。FastAPI 的 POST /v1/memories 要求 explicit_consent=true，Agent 正常问答不会自动调用它。", "它让用户能主动保存研究笔记和偏好，又不会让这些笔记冒充实时足球证据。未来替换为 MCP 或共享记忆服务时只需保持同一契约。", "已运行：memory/contracts.py、memory/sqlite_memory_store.py、service/app.py。")

    add_module_section(document, "九 安全护栏与 Human in the Loop", "partially implemented", "安全层在工具调用、外部网页材料、循环次数和高风险操作前给出 allow、require_human 或 deny。", "网页和检索资料属于不可信外部输入，可能包含诱导模型忽略规则的文本。另一个真实风险是 Critic 不断要求补资料，导致调用失控。", "input_policy.py 已在 Graph 起点执行：空输入、超长输入或明显试图覆盖系统规则的请求，不会进入模型或工具节点。workflow_routing.py 已有研究循环上限。后续再增加工具参数白名单、网页 Prompt Injection 隔离、费用预算，并用 LangGraph interrupt 向用户追问。", "它不负责提升答案文采，而负责把 Agent 从“会跑”变成“可控”。这是面试中能体现工程意识的能力。", "已运行：agent_base/guardrails/input_policy.py、workflow_routing.py；后续：Human in the Loop。")

    add_module_section(document, "十 数据库 缓存与状态持久化", "implemented 与 scaffolded", "SQLite 当前承担会话检查点、工具缓存和运行记录；后期 PostgreSQL 与 Redis 承担服务化后的持久化、缓存、限流和任务状态。", "CLI 阶段 SQLite 足够简单且便于学习。多用户 API 阶段需要更稳定的并发、数据隔离和跨实例共享状态，才有必要引入 PostgreSQL、Redis。", "infrastructure/storage/contracts.py 约束运行仓储读法，cache/contracts.py 约束带 TTL 的缓存读写。未来实现 Redis/PostgreSQL adapter 时不能改变上层 Graph 或 API 的调用方式。", "它让系统可以恢复工作流、避免重复请求、追踪任务，并保持从单机学习项目向服务化项目的演进路径。", "已有：data/、agent_base/run_observability.py、tool/shared/sqlite_cache.py；骨架：infrastructure/storage、cache。")

    add_module_section(document, "十一 观测 日志与成本", "partially implemented", "运行记录层通过 run_id 保存节点名、状态、耗时和安全元数据，未来扩展到 Trace、指标与成本分析。", "多 Agent 出错时，如果只看到最终报错，无法知道是 Planner、工具、网络还是 Critic 循环的问题。观测数据也是评测“正确但昂贵”与“质量更高但慢”的基础。", "现有 RunRecorder 以 SQLite 保存安全摘要，不保存原问题、完整模型回答或 API Key。runtime_report.py 能把记录转成开发者可读的路径、节点顺序、Solver 轮次与失败点。新增 TraceEvent 契约后，可以将同一数据接入 Langfuse 或 OpenTelemetry。", "它为调试、质量对比、成本治理和简历中的可观测性实践提供依据。", "已运行：agent_base/run_observability.py、runtime_report.py；骨架：infrastructure/observability/。")

    add_module_section(document, "十二 Agent 评测与对比实验", "partially implemented", "评测层不只判断答案像不像，还判断路由、计划、工具选择、循环次数、引用和成本是否满足预期。", "Agent 的一次演示成功不能证明稳定性。把问题、预期路由、允许工具和关键事实写入数据集，才能在修改 Prompt、模型或工具后做回归验证。", "agent_base/evals 已有离线路由和研究循环契约测试。新增 EvaluationResult 统一每个评测器输出；datasets、evaluators、experiments 分别承载题集、打分规则和单 Agent/多 Agent 的可重复对比。", "它让项目从“能运行的 Agent Demo”升级为“可量化迭代的 Agent 系统”。", "已有：agent_base/evals/、tests/test_workflow_evals.py；骨架：evaluation/。")

    add_module_section(document, "十三 FastAPI SSE 与服务化", "implemented", "服务层将 CLI 包装为 HTTP API，并通过 SSE 安全地发送研究开始、最终答案或错误事件。", "CLI 适合学习和调试，但实习项目通常需要展示服务接口、请求校验、异步执行和前后端可消费的响应。SSE 适合聊天式网页：浏览器建立一个普通 HTTP 连接，就能连续接收事件。", "service/app.py 提供 GET /health、POST /v1/research、POST /v1/research/stream 与 Memory API。路由只创建 SoccerResearchTeam 并调用 aanswer，绝不复制 Planner、Collector 或 Graph。sse.py 把受 Pydantic 限制的事件编码为 SSE 文本；健康检查不导入模型，容器可以在没有 API Key 时完成进程存活探针。", "它把 Agent 核心转化为可以被网页或其他服务调用的产品能力，同时保持核心业务完全不依赖 Web 框架。", "已运行：service/app.py、service/api/schemas.py、service/streaming/events.py、service/streaming/sse.py。")

    add_module_section(document, "十四 多模态战术分析", "scaffolded", "多模态模块后期读取阵型图、战术板和比赛截图，生成带置信度和局限的视觉证据。", "这项能力和足球场景天然匹配，但视频理解的成本、版权、标注和评测难度都更高，因此必须排在文字与 RAG 闭环稳定之后。", "VisualInput 仅保存受控存储引用和用户说明；VisualEvidence 将观察、置信度和限制分开。视觉结果进入 Collector 的 evidence，再由 Solver 与文字资料综合，不能直接跳过证据链得出结论。", "它为未来展示多模态 Agent 能力预留通道，同时避免第一阶段被视频工程拖偏。", "骨架：multimodal/contracts.py。")

    add_module_section(document, "十五 Docker 与部署", "implemented", "容器化层将 FastAPI 服务和 SQLite 数据卷封装为可复现的本地部署单元。", "部署环境差异会让“本机能跑”的项目难以复现。Docker Compose 是中小团队常见的本地集成方式，也能让面试展示更完整。", "Dockerfile 从 Python slim 镜像安装 requirements，以 PYTHONPATH=/app 启动 uvicorn。docker-compose.yml 通过 env_file 注入密钥、不把 .env COPY 到镜像、把 data 映射为命名卷，并通过 /health 做服务健康检查。", "它让项目具有从源码到可启动服务的交付闭环。Redis 和 PostgreSQL 是未来横向扩容时替换 SQLite 的选项，不是为了简历强行加入的空容器。", "已运行配置：Dockerfile、docker-compose.yml、.dockerignore。")

    add_heading(document, "十六 从一个问题到一个答案的数据流", 1)
    add_paragraph(document, "这一节是理解项目的核心。不要把 Agent 想成一个会自动完成一切的黑盒。它本质上是一组函数与模型调用，按照 Graph 规定的顺序读写同一份 State。State 就像比赛中的战术板：每一个节点都能看见当前局面，但只能在自己职责范围内修改少数字段。")
    add_table(document, ["顺序", "节点读取什么", "节点写入什么", "用大白话解释"], [
        ["1", "question", "input_policy 或 answer_draft", "先检查问题是否为空、过长或要求覆盖规则。不合格就直接提示用户，不花模型或 API 钱。"],
        ["2", "question", "route", "判断这是查事实、查近期消息，还是需要深入研究。"],
        ["3A", "question", "evidence、answer_draft", "基础问题查询结构化数据，必要时降级到网页资料。"],
        ["3B", "question", "evidence、answer_draft", "实时问题先找网页证据，再由模型只根据证据整理答案。"],
        ["3C", "question、plan、review", "Planner、Collector、Solver、Critic 协作，解决需要解释原因的复杂战术问题。"],
        ["4", "evidence", "verification、warnings", "检查证据来源、新鲜度与矛盾，避免只因模型说得流畅就相信它。"],
        ["5", "draft、review、verification", "final_answer", "将已经审阅过的材料写成用户真正看到的回答，并说明限制。"],
    ], [1.2, 4.0, 4.0, 6.0])
    add_paragraph(document, "以问题“阿森纳为什么能限制对方中场推进”为例：输入关口放行后，分类器看到“为什么”和“限制”这类研究信号，会写入 route=research。Planner 再把大问题拆为阵型与压迫职责、比赛事件或赛后报告、对手中场推进结果等子问题。Collector 根据计划取得网页或结构化资料，把结果放进 collected_evidence。Solver 只读这些材料写草案；Critic 判断草案是否有足够证据；最后才由 Finalizer 写给用户。")

    add_heading(document, "十七 State 字段逐项解释", 1)
    add_paragraph(document, "初学 LangGraph 最容易困惑的是：为什么要保存这么多字段？答案是每个字段都在减少一个具体混乱。它们不是为了显得复杂，而是为了让后续节点不需要猜测前一步做了什么。")
    add_table(document, ["字段", "谁写入", "谁读取", "它解决的混乱"], [
        ["question", "初始状态", "所有节点", "让所有角色围绕同一个用户问题工作。"],
        ["input_policy", "validate_input", "条件边、finalize", "把输入是否可继续处理变成明确数据，而不是散落的 if 判断。"],
        ["route", "classify", "分类条件边、finalize", "决定该走省钱的简单路径，还是复杂研究路径。"],
        ["evidence", "Tool、Collector、Solver", "verify、Finalizer", "保存全部可追溯材料；列表 reducer 会把多轮证据追加而非覆盖。"],
        ["plan", "Planner", "Collector、Solver、Critic", "让资料收集和回答都围绕明确子问题，不变成随意搜索。"],
        ["collected_evidence", "Collector", "Solver、Critic", "表示本轮专门为研究取得的材料，避免 Solver 混淆历史杂项。"],
        ["draft", "Solver", "Critic、Finalizer", "把“分析草案”和最终答案分开，给审阅留出位置。"],
        ["review", "Critic", "条件边、Planner、Collector、Solver", "把“哪里不够、下一步干什么”变成机器能路由的数据。"],
        ["research_attempt", "Solver", "Critic、路由器", "为反思循环设硬上限，避免无限检索和无限花费。"],
        ["warnings / verification", "多个节点", "Finalizer", "把不确定性和证据冲突带到最终回答，不让它们悄悄消失。"],
    ], [3.2, 3.0, 3.6, 5.4])

    add_heading(document, "十八 先读哪几个文件才能真正掌握项目", 1)
    add_paragraph(document, "建议不要从工具客户端或数据库表开始读。先把主流程读懂，再回头看每个节点调用的功能。下面的顺序可以让你在较短时间内讲清架构。")
    add_table(document, ["阅读顺序", "文件", "阅读时只回答一个问题"], [
        ["第一步", "agent_base/graph/state.py", "一次请求在系统里要携带哪些信息？每个字段为什么存在？"],
        ["第二步", "agent_base/workflow_routing.py", "三类问题如何分流？Critic 何时允许循环，何时强制结束？"],
        ["第三步", "agent_base/agent.py 的 build_soccer_graph", "哪些是节点，哪些是普通边，哪些是条件边？"],
        ["第四步", "research_plan.py 与 research_review.py", "Planner 和 Critic 为什么必须输出结构化 JSON，而不是一段自然语言？"],
        ["第五步", "research_evidence_collector.py", "Collector 如何根据计划并发取证，失败时为什么不直接让整个任务崩掉？"],
        ["第六步", "model_gateway.py", "为什么不同角色不必使用同一个模型？模型配置为什么不能散落在节点中？"],
        ["第七步", "run_observability.py 与 runtime_report.py", "run_id 怎样帮助你看到真实执行路径，而不泄漏用户隐私？"],
        ["第八步", "tool/ 与 tests/", "资料具体怎样取得、缓存、验证；修改后如何验证没有破坏旧路径？"],
    ], [1.7, 6.4, 7.1])
    add_paragraph(document, "如果面试官问“为什么 Solver 没有工具”，你应回答：Collector 的职责是按计划取证，Solver 的职责是基于 State 中的已记录证据做推理。这样可以审计 Solver 到底依据了什么，Critic 能区分资料不足与推理错误，也能阻止 Solver 在生成文本时偷偷进行无法追踪的检索。")

    add_heading(document, "十九 已完成边界与尚未完成边界", 1)
    add_paragraph(document, "现在可以说核心工作流已完成：输入检查、三路分类、基础数据与实时信息路径、研究路径的 Planner—Collector—Solver—Critic—Finalizer、证据核验、循环上限、SQLite 检查点、运行记录、本地战术基础知识检索与离线工作流测试都已经有运行代码。核心图不是一张文档里的箭头，而是 build_soccer_graph 注册的实际 LangGraph。")
    add_paragraph(document, "本版本已经有完整的单机产品闭环，但不应假装是生产集群：本地战术库只覆盖项目维护的基础概念和可解释检索；尚未接入的是文章级真实战术语料、向量检索与重排、Redis/PostgreSQL、Langfuse 或 OpenTelemetry、LangGraph interrupt 追问流程和真实视觉模型。它们是下一阶段的扩展方向。知道这条边界，才是你真正掌握项目而不是背项目。")

    # 验收表需要整块阅读，主动换页避免表头与主要行被拆到不同页面。
    document.add_page_break()
    add_heading(document, "二十 后续开发顺序与验收标准", 1)
    add_table(document, ["优先级", "下一步要做什么", "为什么先做", "验收标准"], [
        ["P0", "真实跑通一次战术问题的 Planner Collector Solver Critic 闭环。", "先证明现有核心设计在真实模型与真实资料上可用。", "产生 run_id；能查看节点轨迹；答案含证据边界；Critic 循环不超过 2 次。"],
        ["P0", "建立真实战术评测小集与基线。", "没有基线就无法判断 Critic 或 RAG 是否真的改善质量。", "至少覆盖路由、计划、工具、引用、限制说明五类断言。"],
        ["P1", "把本地基础概念库扩展为文章级战术 RAG。", "当前已能检索基础框架，下一步才是导入文章、切块、向量检索与重排。", "资料可导入、检索、重排；回答可回链到 chunk 和原文。"],
        ["P1", "接入 Langfuse 或 OpenTelemetry，并补模型成本统计。", "为迭代提供延迟、失败和成本证据。", "一次研究可查看完整 trace、模型调用和工具耗时。"],
        ["P2", "FastAPI SSE、Redis、PostgreSQL 与 Docker Compose。", "核心能力稳定后再做服务化，避免过早堆基础设施。", "服务可启动、可流式查看进度、可恢复任务、可缓存。"],
        ["P3", "Human in the loop、安全策略与多模态。", "能力较强但依赖前面稳定的证据链、服务层和评测。", "高风险问题可暂停追问；视觉证据可标明置信度和局限。"],
    ], [1.6, 4.2, 5.1, 5.5])

    add_heading(document, "二十一 面试表达边界", 1)
    add_paragraph(document, "目前可以明确说：项目已使用 LangGraph 构建基础数据、实时信息与深度研究三条路径；研究路径包含结构化 Planner、异步证据收集、无工具 Solver、结构化 Critic、受上限的 Replan；已有 SQLite 检查点、运行记录、模型网关、缓存与离线工作流评测。")
    add_paragraph(document, "在后续能力真正接入前，应该说：已为 RAG、Redis、PostgreSQL、FastAPI/SSE、可观测平台、安全护栏和多模态建立可扩展的模块边界、数据契约与验收方案；不要说“已部署 Redis”“已实现多模态视频分析”或“已上线 RAG”。这种诚实且具体的表述，反而更容易经受面试追问。")

    add_heading(document, "二十二 本地战术知识怎样进入最终回答", 1)
    add_paragraph(document, "RAG 是 Retrieval Augmented Generation 的缩写，中文常译为“检索增强生成”。不要把它理解为重新训练模型。它的意思是：模型准备回答前，系统先从资料库找出与问题相关的内容，再把这些内容作为额外上下文交给模型。模型本身没有永久记住这些笔记；它是在本次回答里读到了它们。")
    add_table(document, ["阶段", "当前项目里的文件", "发生了什么", "为什么不能省略"], [
        ["保存知识", "knowledge_base/seed/tactical_foundations.json", "用结构化 JSON 保存作者维护的战术基础笔记，每条有标题、标签、正文和限制。", "知识可被审查、修改和扩充，不依赖模型记忆。"],
        ["检索知识", "local_tactical_retriever.py", "从用户问题抽取“高位压迫、肋部、出球”等概念词，按标题、标签、正文匹配并评分。", "只把相关条目交给模型，避免把整个资料库塞入上下文。"],
        ["包装证据", "build_tool_success 与 Collector", "把条目包装为统一 Evidence Envelope，保留 source、freshness、warnings 和 citation_id。", "本地知识、网页和数据 API 才能被同一套质量与审阅流程处理。"],
        ["压缩上下文", "research_evidence_context.py", "State 保留原始证据；给模型时只取限制长度的摘要、引用 ID 和局限。", "控制 Token 成本，也让 Finalizer 不需要阅读无关网页长文。"],
        ["引用交付", "build_citation_catalog 与 Finalizer", "Finalizer 收到可展示引用目录，并被提示将本地资料标为“战术框架”。", "防止模型把基础概念伪装成某场比赛的新闻或官方事实。"],
    ], [2.4, 4.6, 5.5, 4.0])
    add_paragraph(document, "当前的检索器为什么先用关键词而不是向量？因为资料只有少量基础条目，关键词规则足够透明：你能清楚看到“高位压迫”为什么命中“压迫与反抢”。等将来导入大量战术文章、赛后报告和用户材料时，才需要 Embedding 向量检索解决同义表达、长文语义和规模问题；到那时仍可保持同样的 Evidence Envelope 和 citation_id，不必重写 Agent 流程。")
    add_paragraph(document, "边界：本地笔记只能解释“高位压迫通常如何封锁线路”，不能证明某支球队在某场比赛确实这样做；具体判断仍需比赛报告、事件数据、录像观察或可靠媒体来源。")

    add_heading(document, "二十三 如何自己维护本地战术知识库", 1)
    add_paragraph(document, "现在这套 RAG V1 已经不需要你每次修改代码才能加知识。你应维护的是 seed/tactical_foundations.json 中的原始条目，而不是 indexes 目录下的索引文件。每条条目至少要有稳定 id、标题、标签、摘要、正文和限制。限制不是可有可无的备注，它告诉 Agent 这条资料不能被用于证明什么。")
    add_table(document, ["你要做的动作", "实际操作", "系统内部发生什么", "你应该检查什么"], [
        ["新增一条概念", "在 seed/tactical_foundations.json 增加结构化 JSON 条目。", "Pydantic 会检查 id、标题、标签、正文和限制是否完整。", "id 不重复；标签是用户可能会问到的概念词；正文是自己的清晰表述。"],
        ["重建索引", "运行 scripts/build_tactical_foundation_index.py。", "系统读取原始条目、按句子切块，写出 indexes/tactical_foundation_chunks.json。", "只修改 seed；不要手改 indexes，因为它是可重复生成的派生文件。"],
        ["验证资料", "运行 tests/test_foundation_ingestion.py。", "检查重复 id、空正文、切块规则和每条资料是否产生检索块。", "资料没有静默丢失；切块没有异常超长。"],
        ["验证检索", "运行 evaluation/run_tactical_retrieval_evals.py。", "用固定问题检查首个命中文档是否正确。", "新增或改写标签后，旧问题仍能找到正确基础概念。"],
    ], [2.5, 4.4, 5.6, 4.0])
    add_paragraph(document, "当前所谓“混合检索”并不神秘：同一个概念如果出现在标签中，得分最高；出现在标题中，得分其次；只出现在正文中，得分较低。它把人工标注和文本内容结合起来，比只搜标题更稳，也比一开始引入难调试的向量数据库更适合小型基础知识库。将来资料变成数百篇文章后，才把这一层替换为关键词检索加 Embedding 向量检索加 reranker；上层 Collector、Solver 和引用格式不需要推倒重来。")

    add_heading(document, "二十四 本次服务化补全 你应如何理解和讲述", 1)
    add_paragraph(document, "这一节专门解释本次补上的能力。它们不是为了把项目堆得复杂，而是让已有的 Agent 核心能被别人实际使用、被你自己测试、并能在面试中从接口到部署讲清楚。")
    add_table(document, ["模块", "你实际写了什么", "为什么这样做", "面试时可以怎样说"], [
        ["FastAPI", "service/app.py 把研究请求变成 POST /v1/research，并调用 SoccerResearchTeam.aanswer。", "API 层只做 HTTP 校验和错误转换，业务图仍只有一份，避免 CLI 与网页答案逻辑分叉。", "我把 LangGraph 核心与 Web 框架隔离，FastAPI 只是适配层。"],
        ["SSE", "POST /v1/research/stream 返回 event: run_started、final 或 error。", "SSE 是服务器单向推送，聊天页面能先显示“正在研究”，再接收答案，不需要 WebSocket。", "我先提供安全的任务级事件；后续可把 LangGraph astream_events 映射为更细粒度节点事件。"],
        ["Memory Note", "SQLite Store 有 save、按 scope 查询、delete；API 要求 explicit_consent。", "记忆的正确性和隐私边界比“自动记住一切”更重要，用户必须能撤回。", "我区分会话与项目范围，且不把 Memory 当作实时事实来源。"],
        ["Docker", "Dockerfile、Compose、.dockerignore、健康检查和 data 卷。", "开发者换电脑或部署时，启动命令和依赖保持一致；密钥不写入镜像。", "我用 env_file 注入配置，用 health endpoint 做存活检查，用卷持久化 SQLite 数据。"],
    ], [2.6, 5.0, 4.8, 4.2])
    add_paragraph(document, "实际调用顺序是：前端或 curl 发送 JSON 请求，FastAPI 的 ResearchRequest 校验 question 和 session_id，路由延迟创建 SoccerResearchTeam，Team 创建 run_id 并运行异步 LangGraph，Graph 在 SQLite 中保存检查点和运行事件，最后 API 将 final_answer 封装成 ResearchResponse。流式接口的区别仅在于：它先返回一个 HTTP 流，再在任务结束时发送 final 事件；核心研究逻辑完全相同。")
    add_paragraph(document, "Memory 的调用顺序是：用户在界面点击“保存笔记”并确认，客户端提交 explicit_consent=true，API 校验 scope、kind 和内容长度，Store 写入 SQLite。用户要求删除时，前端调用 DELETE /v1/memories/{memory_id}，系统只删除该 ID。注意，当前 Memory 尚未自动注入 Agent Prompt，这是刻意的：先保证保存、隔离和删除正确，再决定哪些已授权偏好值得作为回答上下文。")

    for sec in document.sections:
        footer = sec.footer.paragraphs[0]
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = footer.add_run("Soccer Agent Architecture Guide")
        configure_run(run, 8, color="777777")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    document.save(OUTPUT_PATH)


if __name__ == "__main__":
    build_document()
