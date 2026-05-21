# AI Novelist 当前架构与实施计划

## 1. 当前状态

AI Novelist 当前是本地 CLI 版智能小说作家助手，基于 Python、LangGraph、Codex CLI，并支持 DeepSeek API 作为可选模型提供方。

当前推荐使用方式已经收敛为一个主入口：`ai-novelist chat`。Director Agent 作为主脑管理项目上下文，并根据用户输入调度 research、outline collaboration、章节写作、编辑审稿和保存等子工作流。

已完成：

- 阶段 1：最小 LangGraph + 模型适配器 + 本地存储。
- 阶段 2：compose 多 Agent 小说创作图。
- 阶段 2 增强：Director Agent chat 主入口。
- Research/检索增强：chat 可先搜索原始资料，生成通用 `retrieval_context`，并继续产出兼容旧流程的参考简报和来源列表。
- 本地小说知识库优先 RAG：chat 可配置本地 `.txt/.md` 语料目录，research 优先检索本地语料；本地无命中时回退 mock 或真实联网搜索。
- 大纲共创增强：outline collaboration graph，支持方向提案、生成、审稿、用户反馈、修订、版本比较、锁定约束、查看正文和保存。
- mock 模式：不依赖外部模型即可端到端验证。
- 真实模式：Codex CLI 或 DeepSeek API。

未完成：

- 阶段 3 飞书机器人入口。
- 真实联网搜索后端已实现：`WebSearchBackend` 支持 SerpAPI、Tavily、Exa；默认仍是 mock，需要 API Key 才会联网。
- 通用检索上下文已实现：`retrieval_context` 会注入 outline 和 writer prompts，但不会自动触发额外搜索。
- 后台任务队列、数据库、多用户存储、并发锁。
- Claude Code Adapter。
- 多章节批量自动续写。
- Web UI。

## 2. 总体架构

```text
用户
  |
  v
本地 CLI: ai-novelist
  |-- chat: 唯一推荐主入口，Director 管理上下文并调度子工作流
  |-- outline: 保留为大纲共创调试/兼容入口，共享同一 state
  |-- compose: 一次性多 Agent 创作
  |-- worldbuild / plan-outline / plan-chapters / write-chapter / review: 单 Agent 兼容命令
  |-- init
  `-- show
  |
  v
模型适配层
  |-- AgentAdapter
  |-- CodexCLIAdapter
  `-- DeepSeekAdapter
  |
  v
Research / Retrieval 层
  |-- SearchResult: title / url / snippet / source / metadata
  |-- SearchBackend.search(query, limit=5)  # 只负责原始搜索结果
  |-- MockSearchBackend
  |-- WebSearchBackend: SerpAPI / Tavily / Exa
  |-- LocalRAGSearchBackend: 递归读取本地 .txt/.md，固定窗口切片并关键词打分
  |-- LocalFirstSearchBackend: 本地命中即返回；本地无命中、目录不存在或为空时回退 fallback
  `-- retrieval_context_synthesizer.md: LLM 整理通用检索上下文，失败时规则 fallback
  |
  v
LangGraph 编排层
  |-- graph_minimal.py
  |     `-- 保留阶段 1 最小图
  |
  |-- graph_research.py
  |     detect_research_need
  |       -> build_research_queries
  |       -> search_sources
  |       -> synthesize_reference_brief
  |       -> save_research_result
  |       -> ask_user_confirm
  |
  |-- graph_outline.py
  |     director
  |       -> ask_user / propose_directions / worldbuild / generate_outline
  |       -> review_outline / revise_outline / compare_versions
  |       -> show_outline / show_status / persist_outline / END
  |
  `-- graph_writer.py
        |-- build_writer_graph: 单 Agent 兼容图
        |-- build_composer_graph: 完整 compose 图
        `-- build_chat_graph: Director 单轮对话图，可进入 outline workflow
  |
  v
Prompt 模板层
  |-- director.md
  |-- direction_proposer.md
  |-- outline_planner.md
  |-- outline_editor.md
  |-- outline_reviser.md
  |-- version_comparator.md
  |-- world_builder.md
  |-- chapter_planner.md
  |-- chapter_writer.md
  `-- editor.md
  |
  v
本地文件存储
  `-- projects/<project>/
        |-- state.json
        |-- reference_brief.md
        |-- research_sources.json
        |-- worldbuilding.md
        |-- outline.md
        |-- chapter_plan.md
        `-- chapters/
```

## 3. Chat 主入口调度

`run_chat_command` 每轮加载同一个项目的 `state.json`，根据状态和用户输入选择子图：

```text
用户输入
  -> 写入 state.user_request + messages
  -> 如果需要 research: build_research_graph(search_backend, store, adapter=adapter)
  -> 否则如果 state.active_workflow == "outline": build_outline_collaboration_graph
  -> 否则: build_chat_graph
  -> 打印 Director 消息、阶段日志和产物正文
  -> 保存 state.json
```

research 优先条件：

- 用户输入 `/research xxx`。
- 用户输入包含“同人 / 原作 / 参考网络 / 查一下 / 调研 / research / 小说名”。
- 用户提出“写某某同人”且当前没有 `reference_brief`。
- 对已存在 `reference_brief` 的项目，不重复强制 research，除非用户显式 `/research xxx`。

outline workflow 条件：

- `state.active_workflow == "outline"` 时，普通创作反馈继续进入 `build_outline_collaboration_graph`。
- “查看状态 / status / 项目状态”仍走项目状态摘要，不被 outline graph 截获。

## 4. Research 流程

```text
START
  -> detect_research_need
  -> build_research_queries
  -> search_sources
  -> synthesize_retrieval_context
  -> synthesize_reference_brief
  -> save_research_result
  -> ask_user_confirm
  -> END
```

输出与持久化：

- `state.retrieval_query`
- `state.retrieval_context`
- `state.retrieval_sources`
- `state.reference_brief`
- `state.canon_facts`
- `state.research_sources`
- `state.research_uncertainties`
- `projects/<project>/reference_brief.md`
- `projects/<project>/research_sources.json`

本地 RAG 配置：

- 环境变量：`AI_NOVELIST_LOCAL_CORPUS_DIR=/path/to/corpus`。
- CLI 参数：`ai-novelist chat --project demo --local-corpus-dir /path/to/corpus`。
- 当前仅 `chat` research 入口接收 CLI 参数；未配置时保持原 mock/web 行为。
- 本地结果 `source=local_corpus`，URL 形如 `local://corpus/<relative_path>#chunk=<id>`，metadata 保留 `file_path`、`relative_path`、`chapter_name`、`chunk_id`、`start_offset`、`end_offset` 和 `score`。

运行体验：

```text
[Research] 正在识别需要调研的原作信息...
[Search] 正在搜索：...
```

research 完成后：

- `director_action = "research"`
- `active_workflow = "outline"`
- `current_stage = "confirm_reference_brief"`
- 展示参考简报和来源，要求用户确认或修正原作设定。

## 5. 大纲共创流程

`outline` 子图可由 chat 自动进入，也可通过 `outline` 命令单独调试。

```text
START
  -> director
  -> route_after_outline_director
      -> ask_user -> END
      -> propose_directions -> human_feedback -> END
      -> worldbuild -> generate_outline -> review_outline -> human_feedback -> END
      -> generate_outline -> review_outline -> human_feedback -> END
      -> review_outline -> human_feedback -> END
      -> revise_outline -> compare_versions -> review_outline -> human_feedback -> END
      -> show_outline -> END
      -> show_status -> END
      -> persist_outline -> END
      -> stop -> END
```

关键行为：

- 新小说创意不会直接生成完整大纲，优先方向提案或追问。
- `review_outline` 返回 `revise` 时不会自动保存，只写入审稿状态和修订建议。
- `revise_outline` 会写入新版本，并调用 `compare_versions`。
- `show_outline` 展示 `state.outline` 正文。
- `persist_outline` 保存 `outline.md`，并清空 `active_workflow`，`current_stage` 进入 `chapter_plan`。
- 用户明确 `stop / 退出 / 结束` 会清空 `active_workflow/current_stage`。

outline prompt 已注入 retrieval/research 上下文：

- `retrieval_query`
- `retrieval_context`
- `retrieval_sources`
- `reference_brief`
- `canon_facts`
- `research_uncertainties`

writer prompt（worldbuild、plan_outline、plan_chapters、write_chapter、review）也会注入通用检索上下文，复用已有 `/research` 搜索结果。

如果存在原作不确定点，prompt 要求先确认，不得擅自补完原作设定。

## 6. Compose 图

```text
worldbuild
  -> plan_outline
  -> plan_chapters
  -> write_chapter
  -> editor_review
       -> pass: human_review -> persist_outputs -> END
       -> revise 且 revision_count < max_revisions: rewrite_chapter -> editor_review
       -> revise 超限或 stop: END
```

compose 仍保留一次性自动推进能力，适合快速 smoke 或批处理式验证；推荐日常创作从 `chat` 入口进入。

## 7. 状态字段

`NovelState.from_dict/to_dict` 保持旧 `state.json` 向后兼容。

核心创作字段：

- `idea`
- `worldbuilding`
- `outline`
- `chapter_plan`
- `chapter_draft`
- `editor_notes`

工作流字段：

- `active_workflow`
- `current_stage`
- `active_artifact`
- `active_task`
- `director_action`
- `director_intent`
- `director_message`
- `next_action`
- `review_status`

大纲共创字段：

- `revision_instruction`
- `locked_constraints`
- `style_preferences`
- `outline_versions`
- `selected_outline_version`
- `pending_questions`
- `open_decisions`
- `last_user_feedback`

research 字段：

- `reference_brief`
- `canon_facts`
- `research_sources`
- `research_uncertainties`

chat 历史字段：

- `messages`
- `user_request`
- `pending_question`

## 8. 使用方式

推荐入口：

```bash
.venv/bin/ai-novelist chat --project demo-chat --mock
```

示例对话：

```text
我想写一个月球城市失忆工程师的悬疑科幻
给我三个不同方向
选择方向 1，强化主角罪感
查看大纲
保存大纲
写第 1 章
让编辑审稿
保存当前结果
查看状态
退出
```

research 示例：

```text
/research 苟在初圣
写苟在初圣同人
查一下原作设定再写大纲
```

本地语料优先示例：

```bash
AI_NOVELIST_LOCAL_CORPUS_DIR=/data/novels .venv/bin/ai-novelist chat --project demo-chat --mock
.venv/bin/ai-novelist chat --project demo-chat --mock --local-corpus-dir /data/novels
```

兼容调试入口：

```bash
.venv/bin/ai-novelist outline --project demo-outline --idea "一个失忆工程师在月球城市追查自己的小说手稿" --mock
.venv/bin/ai-novelist compose --project demo-compose --idea "一个失忆工程师在月球城市追查自己的小说手稿" --chapter 1 --mock --auto-approve
```

## 9. 测试覆盖

- `tests/test_graph_minimal.py`：阶段 1 最小图。
- `tests/test_graph_writer.py`：单 Agent、compose、chat、Director 路由、chat 主入口 workflow。
- `tests/test_outline_collaboration.py`：大纲 approve、revise、lock、variant、旧 state 兼容、chat 路由到大纲修订。
- `tests/test_research_workflow.py`：research 触发、mock 搜索、参考简报持久化、research 后进入 outline、本地优先后端配置和回退。
- `tests/test_search_backend.py`：WebSearchBackend、本地 `.txt/.md` 检索、切片 metadata、关键词排序、本地优先 fallback。
- `tests/smoke_outline_collaboration.py`：大纲生成、修订、保存 smoke。
- `tests/smoke_phase2_compose.py`：compose smoke。
- `tests/smoke_phase2_chat.py`：chat smoke。

验收命令：

```bash
.venv/bin/python -m pytest
.venv/bin/python tests/smoke_outline_collaboration.py
.venv/bin/python tests/smoke_phase2.py
.venv/bin/python tests/smoke_phase2_compose.py
.venv/bin/python tests/smoke_phase2_chat.py
```

当前已验证：`65 passed`。本轮目标测试 `tests/test_search_backend.py tests/test_research_workflow.py` 为 `24 passed`。

## 10. 当前限制

- 仍是本地 CLI，不是长期运行服务。
- research 未配置本地语料时默认只有 mock 搜索；真实搜索需要配置 `AI_NOVELIST_SEARCH_PROVIDER` 和 API Key。
- 本地 RAG 首版是轻量关键词/BM25 近似检索，没有向量检索、索引缓存、文件变更监听或任务级深度检索。
- 当前不会基于大纲自动搜索，也不会为每个 worldbuild/write/review 任务自动搜索；只消费已有检索上下文。
- chat/outline 的多轮共创由 CLI 循环驱动，不是后台会话服务。
- 真实模式每个 Agent 独立调用一次模型，没有流式 token 展示。
- `persist_outputs` 只保存当前已有产物，不会自动补齐缺失产物。
- `compose` 只围绕指定章节运行，不批量生成多章。
- 本地文件存储没有并发锁。
- 没有飞书、数据库、队列、Web UI、多租户权限或 Claude Code Adapter。

## 11. 本地 RAG 后续推进计划

当前本地 RAG 已完成 V0-V2 的最小闭环：配置本地 `.txt/.md` 语料目录、按 chunk 检索、metadata 持久化、本地命中优先、未命中回退 mock/web。后续按以下阶段推进。

### V3：证据质量与 Prompt 强化

目标：让下游 Agent 明确区分本地原文证据、网络摘要和 mock 测试资料。

计划：

- 在 `retrieval_context_synthesizer.md` 中增加证据层级要求：`local_corpus` 优先，web 仅补充，mock 仅测试。
- 在 `build_retrieval_context_prompt` 中注入本地 metadata 摘要，包括 `relative_path`、`chunk_id`、offset 和 score。
- 在规则 fallback 的 `retrieval_context` 中增加“证据层级 / 使用边界”段落。
- 在 `reference_brief` 中保留本地 chunk 位置，便于用户回查原文。
- 增加测试：本地结果进入 prompt 时必须标记为本地原文证据，mock/web 不得被标成原文证据。

验收标准：

- `/research` 本地命中后，`reference_brief.md` 和 `retrieval_context` 能直接看到本地文件位置。
- outline/writer prompt 中本地证据优先级明确，不会把 mock 当真实资料。

### V4：索引缓存与性能边界

目标：避免每轮 research 全量读取和切片大目录。

计划：

- 为 `LocalRAGSearchBackend` 增加轻量索引缓存。
- 缓存键基于 `relative_path`、`mtime_ns`、`size`、`chunk_size`、`chunk_overlap`。
- 首版优先做进程内缓存；如 CLI 多轮 chat 性能仍不足，再落盘到项目或语料目录旁的 JSON 索引。
- 目录不存在、空目录、文件删除、文件修改时自动失效。
- 增加测试：重复查询复用索引，文件修改后重建索引。

验收标准：

- 同一 chat 会话内重复 `/research` 不重复读取未变化文件。
- 文件内容变化后能检索到新内容。

### V5：检索质量增强

目标：提升本地语料命中质量，减少关键词误召回。

计划：

- 把现有简化关键词打分整理成更明确的 BM25 近似策略。
- 增加标题、文件名、章节名权重。
- 支持可配置 chunk 大小和 overlap，优先通过环境变量，CLI 参数再按需要增加。
- 增加“本地结果不足时混合 web”的策略开关，默认仍保持本地命中即优先，避免破坏当前行为。
- 评估是否引入向量检索；除非本地关键词检索明显不够，否则不新增依赖。

验收标准：

- 同一查询下更相关 chunk 排在前面。
- 常见中文单字不会触发本地误命中。
- 默认行为与现有本地优先策略兼容。

### V6：任务级深度检索

目标：让本地知识库从 research 前置资料升级为创作全过程记忆。

计划：

- 先抽象 `RetrievalService`，把 CLI 中 search backend 构造、查询生成、结果格式化和 graph 调用解耦。
- 在 writer 任务中按任务类型生成检索 query：worldbuild 查设定，plan_chapters 查剧情线，write_chapter 查角色/地点/前文，review 查连续性。
- 避免每个 Agent 自动无界补搜；每个任务设定最大查询数和最大注入 token。
- 将任务级检索结果写入 state 的通用 retrieval 字段或新增任务级临时字段，具体实现前再定 schema。
- 增加测试：writer prompt 能拿到任务相关本地片段，且未配置本地语料时行为不变。

验收标准：

- `write-chapter` 能按当前章节需求检索本地设定/前文。
- 未配置本地 RAG 时，现有 compose/chat/writer 流程保持兼容。

### 与阶段 3 飞书接入的关系

本地 RAG 的 V3-V6 不阻塞飞书入口，但 V6 的 `RetrievalService` 与飞书 service 层复用价值高。推荐顺序是先完成 V3-V4，随后抽 service 层，再决定 V5/V6 与飞书阶段的优先级。

## 12. 阶段 3 后续计划

```text
飞书用户
  -> 飞书机器人 / Webhook
  -> 会话映射与消息去重
  -> 调用现有 chat 主入口
  -> 后台执行 research / outline / writing 长任务
  -> 飞书消息回复摘要和审核入口
```

下一步应先抽出 service 层，把 CLI 循环中对 `LocalStore`、graph invoke、search backend 和用户输入归一化的逻辑复用给飞书入口。


## 13. Research 意图管理改造

已完成：

- 新增 research 专用意图 prompt：`src/ai_novelist/prompts/research_intent.md`。
- chat 顶层路由先通过 Director prompt 识别 ACTION，`research` 会进入 research graph；规则路由保留为模型异常兜底。
- research 工作流在搜索前先通过模型提取结构化字段：`NEED_RESEARCH`、`QUERY`、`WORK_TITLE`、`AUTHOR`、`INTENT`。
- 原 `extract_research_query` 保留为兜底，避免 mock、模型异常或输出格式异常时 research 中断。
- 测试覆盖复杂同人输入，避免把“一本/一部/同人小说”等泛词当作搜索词。

当前边界：

- 当前仍保留 `should_use_research_graph` 作为 Director 调用失败时的兜底。
- 后续可继续减少 outline/chat 的前置规则分支，让所有顶层路由共享同一份 Director 决策结果，避免重复调用模型。


## 14. Project Context / Director 记忆增强

已完成：

- 启动 `chat` 时展示当前项目状态，避免用户进入会话后不知道已有参考资料和产物。
- Director prompt 注入参考信息摘要，让每轮意图判断都能看到已检索内容，而不只是“参考简报：已有”。
- 增加 `show_reference` 动作，专门展示参考简报、检索查询、关键事实、不确定点和来源。
- `select_chat_graph` 对“当前获取的信息/参考简报/检索信息”等请求优先走 chat graph，避免 outline graph 把请求误解为只看大纲。

后续可做：

- 把项目上下文摘要持久化为独立 `project_context.md`，由每次 research/outline/write/review 后增量更新。
- 缓存顶层 Director 决策，避免 `select_chat_graph` 和 chat graph 内部重复调用模型。
- 将参考信息展示改成更结构化的“事实 / 不确定点 / 来源 / 下一步建议”固定格式。


## 15. DirectorService 主脑服务重构

已完成：

- 新增 `src/ai_novelist/director_service.py`，提供 `DirectorService.handle_turn(project_id, user_text, channel)`，返回 `immediate_message`、`started_task`、`final_message`、`artifact_paths`、`requires_followup`，为 CLI 和未来飞书入口共用。
- `chat` 主循环改为只调用 `DirectorService`，不再先由 `select_chat_graph` 关键字分流；旧分流函数暂保留给兼容测试和兜底代码。
- Director 决策优先解析 JSON，兼容旧 `ACTION/MESSAGE` 字段格式；结构化字段包含 `requires_confirmation`、`confidence`、`task_args` 和 `next_steps`。
- 增加分级确认：状态/参考/大纲/退出直接执行；research、生成/修订/审查大纲、写章、审稿、保存等动作先缓存到 `pending_director_decision`，用户确认后复用同一决策执行。
- `NovelState` 增加 `director_task_args` 与 `pending_director_decision`，用于跨轮保存结构化参数和待确认计划。
- `LocalStore` 增加 `project_context_path/load_project_context/save_project_context`；服务层在任务执行后刷新 `project_context.md`，记录项目目标、已检索事实、不确定点、产物状态、待确认事项和建议下一步。
- research 查询优先使用 Director 给出的 `research_query/work_title/author`，`research_intent.md` 和规则抽取退为缺参兜底。

当前边界：

- 飞书 webhook、鉴权、消息去重和后台队列未实现；本轮只完成异步友好服务返回对象。
- 旧 `build_chat_graph` 与 outline/research graph 仍保留，服务层通过现有节点调度，后续可继续收敛重复 Director 逻辑。


## 16. 确认选择模型

已完成：

- `DirectorTurnResult` 增加 `choices`，用于表达可交互选项；当前确认场景返回 `confirm/确认执行/1` 与 `cancel/取消/2`。
- CLI `chat` 在收到 `choices` 时渲染编号菜单，用户可输入 `1` 确认、`2` 取消，同时继续兼容“确认/取消/yes/no”等文本。
- 该结构可直接映射到未来飞书按钮或卡片 action，不需要重新解析自然语言确认。
