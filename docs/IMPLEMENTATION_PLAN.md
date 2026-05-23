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
- Director 交互增强：用户始终只和 Director 对话；每轮 chat 自然语言输入优先调用 LLM Director prompt 做意图判断，确定性规则只作为模型失败兜底；Director 会把口语化、多项确认和“接收/接受/同意”等回复转译为下游 Agent 可执行的 `instruction` 与 `locked_constraints`。
- Director 确认门增强：`chat/ask_user/show_* /stop` 直接返回；research、大纲修订/推进、章节规划、写作、审稿、修订、定稿、导出、保存、小说圣经更新等写操作都会先返回 1/2 确认选项，用户确认后才执行工作流。
- mock 模式：不依赖外部模型即可端到端验证。
- 真实模式：Codex CLI 或 DeepSeek API。
- 阶段 3 飞书长连接机器人最小闭环：支持飞书单聊文本、`/project` 项目切换、纯文本确认选项和同步调用 DirectorService。
- 阶段 6+7 章节卡与场景卡管线：新增 Chapter Planning Graph 和 Scene Design Graph，可从锁定大纲/NovelBible 生成 `chapter_card.md`，再拆成 `scene_cards.md`。

未完成：
- 真实联网搜索后端已实现：`WebSearchBackend` 支持 SerpAPI、Tavily、Exa；默认仍是 mock，需要 API Key 才会联网。
- 通用检索上下文已实现：`retrieval_context` 会注入 outline 和 writer prompts，但不会自动触发额外搜索。
- 后台任务队列、数据库、多用户存储、并发锁。
- Claude Code Adapter。
- 多章节批量自动续写。
- Web UI。

### Author Craft Layer v1.0 已接入

本次已按 `plan.md` 完成 Author Craft Layer 的端到端 v1：

- 新增 `src/ai_novelist/corpus/`，包含 encoding、ingest、chunker、index、craft schema、mock extractor、query planner、retriever、brief、resolver、similarity guard 和 project memory。
- 新增 `index-corpus`、`extract-craft`、`craft-status`、`craft-profiles`、`craft-brief`、`craft-similarity-check` CLI。
- `chat`、`feishu`、`compose`、`write-chapter`、`review`、`finalize-chapter` 等生成入口支持 Author Craft 参数；`--local-corpus-dir` research 语义保持不变。
- Outline Stage、Chapter Planning、Scene Design、Drafting、Review、Revision 在构建上下文或阶段 prompt 前调用 AuthorCraftResolver；Drafting、Revision、Finalize 保存后运行 Similarity Guard；Finalize 后沉淀 Project Craft Memory。
- ContextBuilder 新增“作者构思参考”小节，位于锁定约束之后。
- State 只保存 craft 轻量字段，StageCraftBrief、sources、similarity report 和 project memory 作为项目 artifact 保存。
- Prompt loader 对核心创作 prompt 自动追加 `author_craft_policy.md`，统一声明不复刻、不模仿、Pacing Target 优先。

当前 v1 边界：

- 不引入数据库、向量库或 fine-tuning。
- `extract-craft` 默认使用稳定规则提炼；真实模型提炼 prompt 已提供，后续可替换 extractor 实现。
- StageCraftBrief 不注入长原文，只注入方法、适用条件、避免事项和来源摘要。

## 2. 总体架构

```text
用户
  |
  v
本地 CLI: ai-novelist
  |-- chat: 唯一推荐主入口，Director 管理上下文并调度子工作流
  |-- feishu: 飞书长连接单聊入口，复用 DirectorService
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
  |-- graph_chapter_plan.py
  |     select_chapter -> load_chapter_context
  |       -> chapter_goal_agent -> chapter_conflict_agent -> chapter_hook_agent
  |       -> chapter_card_synthesizer -> validate_chapter_card -> save_chapter_card
  |
  |-- graph_scene.py
  |     load_chapter_card -> scene_breakdown_agent -> conflict_check_agent
  |       -> scene_synthesizer -> validate_scene_cards -> save_scene_cards
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
              |-- chapter_001.md                 # 旧正文路径
              `-- chapter_001/
                    |-- chapter_card.md
                    `-- scene_cards.md
```

## 3. Chat 主入口调度

用户侧所有直接交互都应先进入 Director。Director 负责理解自然语言、合并上下文中的待确认项，并把用户反馈转译为下游 Agent 能直接执行的 `task_args/instruction/locked_constraints`；用户不需要、也不应直接按其他 prompts 的格式和子 Agent 对话。正常路径下 `DirectorService._decide()` 优先调用 LLM Director prompt，`deterministic_*_decision` 只在模型调用失败时作为 fallback，避免大纲阶段修订、章节规划等输入绕过主脑。

Director 支持 `chat` 直接动作：当用户只是聊天、讨论偏好或表达感受时，Director 只回复用户，不触发工作流、不写产物、不弹确认。所有会改变状态或产物的动作统一走 pending decision：先展示“确认执行 / 取消”两个选项；用户回复 `1` 或确认词后才执行原决策，回复 `2` 或取消词则清空待执行决策。

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

当上一轮编辑意见包含多个待确认问题时，Director prompt 会带入最近编辑意见正文；若用户用“答案 + 接收/接受/同意”回复，Director 会按顺序把明确答案和接受项写入锁定约束，再触发大纲修订确认。

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

## 6A. 章节卡与场景卡流程

Phase 6+7 已新增两条为后续 Drafting Graph 准备的规划管线，旧 `write_chapter` 正文生成路径不变。

Chapter Planning Graph：

```text
select_chapter
  -> load_chapter_context
  -> chapter_goal_agent
  -> chapter_conflict_agent
  -> chapter_hook_agent
  -> chapter_card_synthesizer
  -> validate_chapter_card
  -> save_chapter_card
```

关键行为：

- 使用 `build_context(..., purpose="chapter_planning")` 读取锁定约束、NovelBible、章节大纲 artifact、项目上下文和参考资料。
- 保存到 `projects/<project>/chapters/chapter_XXX/chapter_card.md`。
- 更新 `state.current_chapter_card`、`state.active_chapter`、`state.active_graph="chapter_plan"`、`state.active_stage="chapter_card"`。
- 注册 artifact：`type="chapter_card"`、`graph="chapter_plan"`、`stage="chapter_card"`、`chapter=N`、`source_agent="chapter_card_synthesizer"`。

Scene Design Graph：

```text
load_chapter_card
  -> scene_breakdown_agent
  -> conflict_check_agent
  -> scene_synthesizer
  -> validate_scene_cards
  -> save_scene_cards
```

关键行为：

- 使用 `build_context(..., purpose="scene_design")` 读取章节卡、NovelBible、锁定约束、项目上下文和参考资料。
- 保存到 `projects/<project>/chapters/chapter_XXX/scene_cards.md`。
- 更新 `state.current_scene_cards`、`state.active_chapter`、`state.active_graph="scene"`、`state.active_stage="scene_cards"`。
- 注册 artifact：`type="scene_cards"`、`graph="scene"`、`stage="scene_cards"`、`chapter=N`、`source_agent="scene_synthesizer"`。
- 缺少章节卡时返回可读提示，要求先运行章节卡规划；当前不会自动补齐章节卡。

Director 新增动作：

- `plan_chapter`：用户说“规划第 N 章 / 生成第 N 章章节卡”时触发。
- `plan_scenes`：用户说“拆第 N 章场景 / 规划第 N 章场景”时触发。
- `plan_chapters` 在 DirectorService 中作为 `plan_chapter` alias 处理；CLI `plan-chapters` 仍保留旧章节细纲行为。

## 7. 状态字段

`NovelState.from_dict/to_dict` 保持旧 `state.json` 向后兼容。

核心创作字段：

- `idea`
- `worldbuilding`
- `outline`
- `chapter_plan`
- `chapter_draft`
- `current_chapter_card`
- `current_scene_cards`
- `editor_notes`

工作流字段：

- `active_workflow`
- `current_stage`
- `active_artifact`
- `active_task`
- `active_graph`
- `active_stage`
- `active_chapter`
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
规划第 1 章
规划第 1 章场景
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
- `tests/test_graph_chapter_plan.py`：章节卡生成、必需小节、状态更新、artifact 注册、`plan_chapters` alias。
- `tests/test_graph_scene.py`：场景卡生成、必需字段、状态更新、artifact 注册、缺章节卡提示。
- `tests/test_outline_collaboration.py`：大纲 approve、revise、lock、variant、旧 state 兼容、chat 路由到大纲修订。
- `tests/test_research_workflow.py`：research 触发、mock 搜索、参考简报持久化、research 后进入 outline、本地优先后端配置和回退。
- `tests/test_search_backend.py`：WebSearchBackend、本地 `.txt/.md` 检索、切片 metadata、关键词排序、本地优先 fallback。
- `tests/test_research_workflow.py` 覆盖 CLI `--search-provider` 与 provider 专用 API Key 的组合，例如 `--search-provider exa` 读取 `EXA_API_KEY`。
- `tests/smoke_outline_collaboration.py`：大纲生成、修订、保存 smoke。
- `tests/smoke_phase2_compose.py`：compose smoke。
- `tests/smoke_phase2_chat.py`：chat smoke。
- `tests/test_feishu_integration.py`：飞书会话映射、`/project` 命令、回复格式化和配置校验。

验收命令：

```bash
.venv/bin/python -m pytest
.venv/bin/python tests/smoke_outline_collaboration.py
.venv/bin/python tests/smoke_phase2.py
.venv/bin/python tests/smoke_phase2_compose.py
.venv/bin/python tests/smoke_phase2_chat.py
```

当前已验证：新增章节/场景管线相关回归 `tests/test_graph_chapter_plan.py tests/test_graph_scene.py tests/test_director_service.py tests/test_graph_writer.py` 为 `46 passed`。

## 10. 当前限制

- 仍是本地 CLI，不是长期运行服务。
- research 未配置本地语料时默认只有 mock 搜索；真实搜索需要配置搜索 provider 和 API Key。CLI 使用 `--search-provider exa` 时会读取 `EXA_API_KEY`，也可用通用 `AI_NOVELIST_SEARCH_API_KEY`。
- 本地 RAG 首版是轻量关键词/BM25 近似检索，没有向量检索、索引缓存、文件变更监听或任务级深度检索。
- 当前不会基于大纲自动搜索，也不会为每个 worldbuild/write/review 任务自动搜索；只消费已有检索上下文。
- chat/outline 的多轮共创由 CLI 循环驱动，不是后台会话服务。
- 真实模式每个 Agent 独立调用一次模型，没有流式 token 展示。
- `persist_outputs` 只保存当前已有产物，不会自动补齐缺失产物。
- `compose` 只围绕指定章节运行，不批量生成多章。
- Phase 8 Drafting Graph 尚未实现；正文草稿仍由旧 `write_chapter` / `compose` writer 路径生成。
- `plan_scenes` 不自动生成缺失章节卡，必须先运行 `plan_chapter`。
- 本地文件存储没有并发锁。
- 飞书入口暂为长连接单聊文本机器人；群聊 @、交互卡片、Webhook、后台队列未实现。
- 没有数据库、队列、Web UI、多租户权限或 Claude Code Adapter。

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

本地 RAG 的 V3-V6 不阻塞飞书入口。当前优先级已调整为先打通飞书长连接链路，再基于真实使用反馈继续推进 V3/V4 证据质量与缓存优化。

## 12. 阶段 3 飞书长连接入口

已完成最小闭环：

```text
飞书单聊用户
  -> lark-oapi 长连接事件
  -> FeishuBotService 文本处理
  -> FeishuSessionStore 映射 open_id 到 project_id
  -> DirectorService.handle_turn(project_id, text, channel="feishu")
  -> LocalStore/state.json/project_context.md
  -> 回复飞书文本消息
```

关键行为：

- CLI 新增 `ai-novelist feishu`，通过 `lark-oapi` 长连接接收飞书消息。
- 可选依赖为 `pip install -e ".[feishu]"`，运行时需要 `AI_NOVELIST_FEISHU_APP_ID` 和 `AI_NOVELIST_FEISHU_APP_SECRET`。
- 第一版只处理单聊文本消息；非文本消息回复“当前只支持文本消息”。
- `/project` 查看当前项目，`/project <project_id>` 切换或创建项目；映射保存在 `projects/.feishu_sessions.json`。
- 普通文本消息复用 `DirectorService`，确认选项渲染为 `1. 确认执行`、`2. 取消`，不接卡片 action。
- 长连接事件按 `message_id` 做进程内最近消息去重，避免飞书事件重投递导致重复回复。
- research、outline、writing 等任务同步执行；长任务期间飞书回复会等待结果。

当前边界：

- 未实现群聊 @、飞书交互卡片、Webhook 回调、后台队列、跨进程消息去重、并发锁和权限隔离。
- `AI_NOVELIST_FEISHU_DOMAIN` 已预留配置字段，当前长连接使用 SDK 默认域。
- 飞书层不得直接调用 graph；后续优化仍应收敛在 DirectorService 或其下游工作流。

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


## 17. 阶段化大纲共创流程

已完成：

- 大纲生成改为固定六阶段：方向定位、世界观设定、人物关系、故事流程、总大纲草案、审稿锁定。
- `NovelState` 新增 `outline_stage`、`outline_stage_status`、`outline_stage_artifacts`、`outline_stage_history`，旧 `state.json` 缺字段时默认从 `direction/collecting` 加载。
- `LocalStore` 新增 `outline_stages/<stage>.md` 路径和保存/读取方法；阶段产物逐阶段落盘，最终 `outline.md` 只在审稿锁定阶段确认后写入。
- `graph_outline` 阶段执行节点按 `STAGE_ROLES[stage]` 调用当前阶段配置的固定角色 `AGENT: outline_stage_role`，再调用 `AGENT: outline_stage_synthesizer` 汇总；不同阶段角色数量可不同。
- 用户反馈默认重跑当前阶段；“确认进入下一阶段/锁定”才推进；“回到世界观/重做人设/查看故事流程”等可切换或展示阶段产物。
- `chat`、`outline`、`plan-outline`、`compose` 入口均遵守阶段化流程；新项目不会再一次性生成完整总大纲。
- `compose` 在没有已保存大纲时只启动/继续当前大纲阶段并停止；已有 `outline.md` 的旧项目仍可继续章节细纲和正文。
- Mock adapter 支持 `outline_stage_role` 与 `outline_stage_synthesizer`，保证阶段测试稳定。

当前边界：

- 阶段产物解析目前以 Markdown 汇总为主，`candidates` 和 `pending questions` 尚未拆成更细结构化字段。
- 旧的一次性 outline 节点仍保留在代码中，主要用于兼容工具函数和旧测试路径；推荐入口已转向阶段节点。
- DirectorService 的确认模型仍会对部分动作要求执行确认；阶段推进本身由明确的“确认进入下一阶段”触发。

验证：

```bash
.venv/bin/python -m pytest
.venv/bin/python tests/smoke_outline_collaboration.py
.venv/bin/python tests/smoke_phase2_chat.py
```

结果：`78 passed`；两个 smoke 均通过。

## 18. 本轮修复：阶段产物查看路由

- 修复 DirectorService 对“查看世界观”的确定性识别：现在会映射到六阶段大纲中的 `worldbuilding` 阶段，而不是误判为参考简报展示。
- 修正阶段名映射键，确保“故事流程”和“审稿锁定”返回有效的阶段枚举 `story_flow`、`review_lock`。
- `show_outline_stage_node` 增加世界观兜底：当 `outline_stages/worldbuilding.md` 尚未生成、但 `state.worldbuilding` 已有正文时，直接展示已有世界观草案。
- 增加 DirectorService 回归测试，覆盖“查看世界观”不会返回“当前还没有参考简报”。

## 19. 本轮修复：世界观确认阶段校准

- 修复“确定世界观”在已有 `state.worldbuilding` 但 `outline_stage` 仍为 `direction` 时被误判为澄清问题的情况。
- DirectorService 现在对“确认/确定/锁定 + 阶段名”做确定性阶段确认，直接锁定对应阶段并推进。
- `advance_outline_stage_node` 增加旧字段兼容：当确认 `worldbuilding` 阶段但阶段产物缺失时，会把 `state.worldbuilding` 转换为 `outline_stage_artifacts["worldbuilding"]` 并保存到 `outline_stages/worldbuilding.md`。
- 阶段跳转确认时会自动锁定此前已有阶段产物，避免方向定位已完成但状态未同步造成最终大纲缺段。

## 20. 本轮修复：确认词保留原始修订意图

- 修复待确认决策中用户回复“开始修订”不被识别为确认的问题。
- `is_confirmation` 新增“开始”“开始修订”“修订”“开始执行”等确认词，避免二次意图判断覆盖上一轮详细修订指令。
- 已补回归测试，确保“开始修订”在待确认场景中按确认执行处理。
- 本轮同时手动修补 `重生魔门` 的人物关系阶段产物，将魔宗圣女与剑宗天才少女两条持续登场关系线写入 `outline_stages/characters.md`。

## 21. 本轮调整：减少大纲阶段确认菜单

- 大纲共创阶段中的普通生成、修订、审查和版本比较不再弹出“1. 确认执行 / 2. 取消”，避免用户反馈被二次确认流程截断。
- 待确认决策改为通用处理：用户明确取消才取消；其他非取消回复会沿用上一轮完整 `original_user_text` 执行，并把回复作为补充确认文本保留，不再依赖不断扩充确认词词典。
- 移除“开始修订”作为特殊确认词的思路，改由 pending decision 的通用规则处理未来类似表达。
- 修复大纲阶段直接执行路径中 `progress=None` 的兜底问题。

## 22. 本轮调整：阶段产物不再伪装成选择菜单

- 非方向阶段的 synthesizer prompt 不再要求输出“候选项或决策”，避免产物中出现 A/B/C 但系统并不等待用户逐项选择的错觉。
- 新格式改为 `Director 汇总 / 已采用设定 / 仍需确认的问题`，其中“仍需确认的问题”只保留真正需要用户补充或拍板的事项。
- 该调整作用于后续新生成或修订的阶段产物；既有 Markdown 不会被自动重写。

## 23. 本轮调整：阶段确认问题进入真实追问状态

- `run_outline_stage_node` 现在会从阶段汇总中的 `仍需确认的问题` / `待确认问题` 小节抽取编号或列表问题。
- 抽取到的问题会写入 `state.pending_questions` 和 `state.pending_question`，并进入 Director 后续上下文，不再只停留在 Markdown 产物中。
- 阶段完成回复会明确列出这些问题，引导用户直接逐条回答；如果没有问题，才回到“继续修改或确认进入下一阶段”。
- 新增测试覆盖确认问题抽取。

## 24. 本轮调整：六阶段大纲连续上下文

- 修复六阶段大纲阶段之间割裂的问题：后续阶段 prompt 不再只读取已锁定阶段，而是读取当前阶段之前所有已生成的阶段产物。
- `build_outline_stage_role_prompt` 和 `build_outline_stage_synthesizer_prompt` 现在都会注入“前序已保存阶段内容”和“当前阶段已有内容”。
- 新增阶段连续性要求：世界观承接方向定位，人物关系承接方向和世界观，故事流程承接方向、世界观代价和人物冲突，总大纲草案整合前四阶段，审稿锁定检查贯通性。
- 当前仍复用 `outline_stage_artifacts` 与 `outline_stages/<stage>.md` 的保存机制，不新增状态字段或迁移。
- 增加测试覆盖世界观、人物关系、故事流程和当前阶段修订 prompt 的上下文注入。
- 方向定位阶段输出简化为单一 `## 方向定位稿`，不再拆成“一句话方向 / 方向命令 / 不许跑偏”，降低第一阶段产物噪声。
- `## 方向定位稿` 必须覆盖全书开篇切入、中期升级和后期终局，避免只定位开篇局面。

## 25. 全量工作流整改 Phase 0-3 基础设施

本轮按 `plan.md` 的首批实施范围小步落地，不替换现有 `chat`、`outline`、`compose`、writer 路径，先补齐后续全量小说工作流需要的基础设施。

已完成：

- Phase 0 基线：重新运行全量 `pytest`、`smoke_outline_collaboration.py`、`smoke_phase2_chat.py`，确认当前行为可回归；同时发现 `.venv` editable 安装曾指向旧目录，并用 `pip install -e . --no-build-isolation` 修正到当前仓库。
- Phase 1 Artifact Registry：新增 `src/ai_novelist/artifacts.py`，提供 `ArtifactRecord`、`load_artifacts`、`save_artifacts`、`register_artifact`、`get_latest_artifact`、`save_markdown_artifact`、`save_json_artifact`、`load_artifact_text`；registry 保存为 `projects/<project>/artifacts.json`。
- Phase 2 Novel Bible：新增 `src/ai_novelist/bible.py`，提供小说圣经 dataclass、JSON/Markdown 保存加载、保守合并和冲突 warning；保存为 `novel_bible.json` 与 `novel_bible.md`。
- Phase 3 ContextBuilder：新增 `src/ai_novelist/context_builder.py`，按 `director/outline_stage/chapter_planning/scene_design/drafting/review/revision/bible_update/export` 等 purpose 组装任务上下文，并支持长度裁剪。
- `LocalStore` 增加 `artifact_registry_path`、`novel_bible_json_path`、`novel_bible_markdown_path` 路径方法。
- `NovelState` 增加轻量索引字段：Bible 版本/更新时间、active graph/stage/chapter/scene、当前章节卡/场景卡/审稿/修订/定稿摘要、章节摘要、artifact registry 简要索引、最近上下文摘要和 Agent 报告。旧 `state.json` 缺字段时仍按默认值加载。

当前边界：

- 新基础设施尚未接管现有 graph；旧路径和旧字段继续作为当前生产路径。
- Phase 5 已接入 `graph_bible.py`，Phase 6+7 已接入章节卡和场景卡；drafting/review/revision/export graph 仍留给后续阶段逐步接入。
- `state.json` 只保存轻量字段；Artifact、Bible 和大文本上下文均保存为独立文件。

验证要求：

```bash
.venv/bin/python -m pytest
.venv/bin/python tests/smoke_outline_collaboration.py
.venv/bin/python tests/smoke_phase2_chat.py
```



## 26. Phase 4：八阶段大纲与 Artifact 注册

本轮只实施 `plan.md` 中的 Phase 4，不接入 Bible Graph 或章节写作新管线。

已完成：

- 大纲共创阶段从六阶段扩展为八阶段：`direction -> concept -> worldbuilding -> characters -> story_flow -> volume_outline -> chapter_outline -> review_lock -> done`。
- `outline_draft` 保留为旧状态兼容值：旧 `state.json` 加载时会规范化为 `volume_outline`；旧 `outline_stage_artifacts["outline_draft"]` 会迁移为 `volume_outline`。
- `graph_outline` 更新阶段标签、角色和连续性要求：新增故事概念、分卷大纲、章节大纲，并让后续阶段显式承接概念、分卷和章节可执行性。
- 阶段产物现在同时保存到旧路径 `outline_stages/<stage>.md` 和新路径 `outline/<stage>.md`。
- 每次阶段产物生成都会注册到 `artifacts.json`，字段为 `type=<stage>`、`stage=<stage>`、`graph="outline"`、`source_agent="outline_stage_synthesizer"`、`path="outline/<stage>.md"`。
- `LocalStore` 增加 `outline_dir(project_id)`、`outline_artifact_path(project_id, stage)` 和 `save_outline_artifact(...)`；旧 `outline_stages` 路径方法继续保留。
- Mock adapter 增加 `concept`、`volume_outline`、`chapter_outline` 阶段稳定输出。
- `review_lock` 确认后仍生成最终 `outline.md`，内容按八阶段顺序合并。

当前边界：

- 新 `outline/<stage>.md` 和 Artifact Registry 已接入阶段保存，但 ContextBuilder、Bible Graph 和后续章节管线尚未默认消费这些产物。
- 旧 `outline_stages/<stage>.md` 继续写入以兼容现有 CLI、测试和历史项目。

验证：

```bash
.venv/bin/python -m pytest
.venv/bin/python tests/smoke_outline_collaboration.py
.venv/bin/python tests/smoke_phase2_chat.py
```


## 27. Phase 5：Bible Graph 与 Director 操作接入

本轮只实施 `plan.md` 中的 Phase 5，不接入 Chapter Planning、Scene 或 Drafting 新管线。

已完成：

- 新增 `src/ai_novelist/graph_bible.py`，提供 `build_bible_graph(adapter, store)`，按 `load_bible -> extract_bible_updates -> detect_bible_conflicts -> apply_bible_updates -> save_bible -> summarize_bible_update` 顺序运行。
- Bible Graph 基于 `NovelState`、Artifact Registry、八阶段 outline artifacts 和 `ContextBuilder(purpose="bible_update")` 初始化/更新 `NovelBible`。
- 新增 prompts：`bible_update_extractor.md`、`bible_conflict_checker.md`、`bible_update_synthesizer.md`；mock adapter 提供稳定 Bible updates JSON。
- 大纲 `review_lock` 完成并生成最终 `outline.md` 后，会自动运行 Bible Graph，生成 `novel_bible.json` 与 `novel_bible.md`。
- DirectorService 新增 `init_bible`、`update_bible`、`show_bible` 动作；“查看小说圣经”展示摘要，“更新小说圣经”基于当前稳定产物运行 Bible Graph。
- 保存 Bible 后注册 `novel_bible` artifact：`path="novel_bible.md"`、`graph="bible"`、`stage="bible_update"`、`source_agent="bible_update_synthesizer"`。
- 修复 `bible_from_dict` 对 `default_factory` 字段的默认值处理，避免旧/部分 JSON 缺字段时写入 dataclasses 内部 sentinel。

当前边界：

- 冲突检测第一版只记录到 `open_questions` 和 `last_agent_reports`，不阻塞 mock 主流程。
- Bible Graph 已可消费 outline artifacts；章节卡和场景卡管线已默认通过 ContextBuilder 消费 Bible，正文管线尚未默认消费这些新产物。
- `state.json` 只保存 Bible 版本、更新时间、轻量 artifact 索引和报告，不保存 Bible 全文。

验证：

```bash
.venv/bin/python -m pytest
# 128 passed
.venv/bin/python tests/smoke_outline_collaboration.py
# outline collaboration smoke ok
.venv/bin/python tests/smoke_phase2_chat.py
# phase2 chat smoke ok
.venv/bin/python tests/smoke_phase2.py
# phase2 smoke ok
```

## 28. Phase 6+7：章节卡与场景卡管线

本轮合并实施 `plan.md` 的 Phase 6 和 Phase 7，不实现 Phase 8 Drafting Graph，不改写旧 `write_chapter` 正文生成路径。

已完成：

- 新增 `src/ai_novelist/graph_chapter_plan.py`，按 `select_chapter -> load_chapter_context -> chapter_goal_agent -> chapter_conflict_agent -> chapter_hook_agent -> chapter_card_synthesizer -> validate_chapter_card -> save_chapter_card` 生成章节卡。
- 新增 `src/ai_novelist/graph_scene.py`，按 `load_chapter_card -> scene_breakdown_agent -> conflict_check_agent -> scene_synthesizer -> validate_scene_cards -> save_scene_cards` 生成场景卡。
- `LocalStore` 新增 `chapter_artifact_dir`、`chapter_card_path`、`scene_cards_path`、`save_chapter_card`、`save_scene_cards`。
- DirectorService 新增 `plan_chapter` 和 `plan_scenes`，并把旧 `plan_chapters` action 规范化为 `plan_chapter`。
- `graph_writer.py` 的旧 chat graph 可路由 `plan_chapter` / `plan_scenes`；旧 CLI `plan-chapters` 仍走原 `chapter_planner` 写入 `chapter_plan.md`。
- 新增 prompts：`chapter_goal_agent.md`、`chapter_conflict_agent.md`、`chapter_hook_agent.md`、`chapter_card_synthesizer.md`、`scene_breakdown_agent.md`、`scene_conflict_check_agent.md`、`scene_synthesizer.md`。
- Mock adapter 增加章节卡和场景卡稳定输出，章节卡包含 8 个必需小节，场景卡至少 2 个场景且每个场景包含 9 类字段。
- 章节卡保存到 `chapters/chapter_XXX/chapter_card.md`，注册 `chapter_card` artifact。
- 场景卡保存到 `chapters/chapter_XXX/scene_cards.md`，注册 `scene_cards` artifact。

当前边界：

- `plan_scenes` 缺少章节卡时只返回提示，不自动调用章节卡规划。
- 旧正文生成和 compose 暂不消费章节卡/场景卡；后续 Phase 8 再接 Drafting Graph。
- `state.json` 当前保存当前章节卡和场景卡正文，后续内容过大时可改为只保存摘要和路径。

验证：

```bash
.venv/bin/python -m pytest
# 134 passed
.venv/bin/python tests/smoke_outline_collaboration.py
.venv/bin/python tests/smoke_phase2_chat.py
.venv/bin/python tests/smoke_phase2.py
.venv/bin/python tests/smoke_phase2_compose.py
```



## 29. Phase 8-10：写章、审稿、修订闭环

本轮合并实施 `plan.md` 的 Phase 8-10，不实现 Phase 11-13 的定稿、Bible 写回、导出或完整 UX smoke；`plan.md` 保持未修改。

已完成：

- 新增 `src/ai_novelist/graph_drafting.py`，按 `load_drafting_context -> draft_scene_batch -> merge_scenes -> dialogue_enhance -> atmosphere_enhance -> hook_enhance -> style_normalize -> save_draft` 生成章节草稿。
- `write_chapter` 会自动补齐前置章节卡和场景卡：缺章节卡时运行 Chapter Planning Graph，缺场景卡时运行 Scene Graph。
- Drafting Graph 使用 `ContextBuilder(purpose="drafting")`，读取章节卡、场景卡、小说圣经、锁定约束、参考资料和前文摘要。
- 草稿保存到 `chapters/chapter_XXX/draft_v1.md`，并同步旧兼容路径 `chapters/chapter_XXX.md`；注册 `chapter_draft` artifact，`graph="drafting"`、`stage="draft"`、`source_agent="style_normalizer"`。
- 新增 `src/ai_novelist/graph_review.py`，按连续性、结构、人物弧光、风格、模拟读者和汇总审稿生成审稿报告。
- 审稿保存到 `chapters/chapter_XXX/review_v1.md` 与 `review_v1.json`，JSON 固定包含 `decision`、`score`、`blocking_issues`、`issues`、`rewrite_tasks`；同步旧 `chapters/chapter_XXX_review.md`。
- `state.editor_notes` 保持旧兼容格式，顶部包含 `STATUS:` 和 `QUALITY_SCORE:`；同时写入 `editor_decision`、`quality_score`、`current_review_report`。
- Review Graph 注册 `review_report` artifact，`graph="review"`、`stage="review"`、`source_agent="review_synthesizer"`。
- 新增 `src/ai_novelist/graph_revision.py`，按 `load_revision_context -> build_revision_plan -> revise_targeted_sections -> merge_revision -> revision_self_check -> save_revised_draft -> maybe_review_again` 生成定向修订。
- Revision Graph 读取最新 `review_v1.json`，缺 JSON 时从 `state.editor_notes` 兜底；达到 `max_revisions` 时停止并给出用户可读提示。
- 修订保存到 `revision_plan_v1.md` 和 `draft_v2.md`，同步旧章节正文路径；写入 `current_revision_plan`、`chapter_draft` 并递增 `revision_count`。
- `graph_writer.py` 中旧 `write_chapter`、`review`、`revise_chapter` 路径改为薄 wrapper，旧 CLI 和 composer 继续可用；Director 新动作 `review_chapter` 已接入，旧 `review` 作为 alias 规范化。
- 新增 drafting、review、revision 所需 prompt，并更新 `chapter_writer.md` 为基于场景卡批量写正文。
- Mock adapter 增加稳定输出：`draft_v1`、`review_v1`、`revision_plan_v1`、`draft_v2`，mock compose 首次审稿返回 `revise`，修订后二次审稿返回 `pass`。

当前边界：

- 重复运行会覆盖固定文件名 `draft_v1.md`、`review_v1.*`、`revision_plan_v1.md`、`draft_v2.md`，artifact registry 仍按版本递增。
- `review_v1.json` 是结构化审稿结果的主来源；`state.current_review_report` 保存 Markdown 报告正文。
- 本阶段不做 final chapter、chapter summary、Bible 写回、导出或完整全书 UX 流程。

验证：

```bash
.venv/bin/python -m pytest tests/test_graph_drafting.py tests/test_graph_review.py tests/test_graph_revision.py tests/test_graph_writer.py
# 30 passed
.venv/bin/python -m pytest
# 140 passed
.venv/bin/python tests/smoke_chapter_pipeline_mock.py
# chapter pipeline mock smoke passed
.venv/bin/python tests/smoke_outline_collaboration.py
# outline collaboration smoke ok
.venv/bin/python tests/smoke_phase2_chat.py
# phase2 chat smoke ok
.venv/bin/python tests/smoke_phase2.py
# phase2 smoke ok
.venv/bin/python tests/smoke_phase2_compose.py
# phase2 compose smoke ok
```


## 30. Phase 11-13：定稿、导出与完整 Director 工作流

本轮一次性实施 `plan.md` 的 Phase 11-13，完成定稿、章节摘要、NovelBible 写回、Markdown 导出和完整 mock 工作流。

已完成：

- 新增 `src/ai_novelist/graph_finalize.py`，按 `load_latest_draft -> save_final_chapter -> summarize_chapter -> save_chapter_summary -> extract_bible_updates_from_final -> update_bible` 定稿章节并更新连续性。
- 定稿读取最新 `final.md` / `draft_v2.md` / `draft_v1.md` / 旧兼容章节路径；审稿通过可定稿，用户明确“定稿第 N 章”也可强制定稿。
- 定稿保存 `chapters/chapter_XXX/final.md` 和 `summary.md`，写入 `state.current_final_chapter`、`state.chapter_summaries[str(chapter)]`，注册 `final_chapter` 和 `chapter_summary` artifacts。
- 定稿后从 final + summary 提取 Bible updates，保守合并到 `novel_bible.json` / `novel_bible.md`，更新 `bible_version`、`bible_updated_at`，注册 `novel_bible` artifact。
- 新增 `src/ai_novelist/graph_export.py`，收集 `chapters/chapter_*/final.md`，按章节号排序生成 `exports/manuscript.md`、`exports/volume_001.md`，并复制 `exports/novel_bible.md`。无 final 章节时返回明确提示，不写空导出。
- DirectorService 新增 `finalize_chapter` 和 `export_project`，并补齐 `write_chapter`、`review_chapter`、`revise_chapter`、`finalize_chapter`、`export_project` 的确定性自然语言路由。
- CLI 新增 `finalize-chapter` 和 `export` 命令；README 已补充章节闭环、定稿、导出命令和产物路径。
- Mock adapter 新增 `chapter_summarizer` 和 `final_bible_update_extractor` 稳定输出，测试不依赖真实模型。

当前边界：

- 导出仅支持 Markdown，不生成 EPUB/PDF。
- 重复定稿会覆盖固定 `final.md` / `summary.md`，artifact registry 继续递增版本。
- Bible 更新继续采用保守 merge，冲突或后续回收点进入 open questions。

验证：

```bash
.venv/bin/python -m pytest
# 148 passed
.venv/bin/python tests/smoke_chapter_pipeline_mock.py
# chapter pipeline mock smoke passed
.venv/bin/python tests/smoke_bible_update_mock.py
# bible update mock smoke passed
.venv/bin/python tests/smoke_full_workflow_mock.py
# full workflow mock smoke passed
.venv/bin/python tests/smoke_outline_collaboration.py
# outline collaboration smoke ok
.venv/bin/python tests/smoke_phase2_chat.py
# phase2 chat smoke ok
.venv/bin/python tests/smoke_phase2.py
# phase2 smoke ok
.venv/bin/python tests/smoke_phase2_compose.py
# phase2 compose smoke ok
```

## 31. Chat 长任务进度可见性优化

本轮按“小步快改”优化 chat 等待体验，不改变核心工作流、不引入后台队列，也不展示模型私有推理链。

已完成：

- 新增 `src/ai_novelist/progress.py`，提供统一 `ProgressFunc`、`emit_progress` 和安全 no-op 兜底。
- `DirectorService` 在真实执行长任务前输出执行计划事件，例如写章会提示将自动补齐章节卡/场景卡。
- `DirectorService` 调用章节卡、场景卡、定稿和导出图时传入进度回调；research 保持既有进度输出。
- `graph_writer.run_agent_task` 将进度回调继续传给 Drafting Graph 和 Review Graph；直接修订、章节卡、场景卡 wrapper 也继续透传。
- Chapter Planning、Scene Design、Drafting、Review、Revision、Finalize、Export 图均增加阶段级进度事件，CLI 会显示 `[Stage] 正在...`。
- Drafting Graph 自动补齐缺失章节卡/场景卡时，会把子图进度继续输出，避免“写第 N 章”长时间无反馈。
- 进度回调异常会被吞掉，不影响实际写作流程。

当前边界：

- 本轮只展示可审计的任务阶段，不展示模型 chain-of-thought。
- Codex CLI 和 DeepSeek 适配器仍是阻塞式完整响应；流式 token 输出留待后续 adapter 接口扩展。
- 大纲阶段角色 Agent 和多编辑审稿仍串行执行；后续可评估并行化，但本轮优先保持行为稳定。

验证：

```bash
.venv/bin/python -m pytest tests/test_graph_drafting.py tests/test_graph_review.py tests/test_graph_revision.py tests/test_finalize_chapter.py tests/test_graph_export.py tests/test_director_service.py
# 28 passed
.venv/bin/python -m pytest
# 150 passed
.venv/bin/python tests/smoke_full_workflow_mock.py
# full workflow mock smoke passed
```


## 32. DeepSeek Agent Thinking 策略

本轮为模型 adapter 增加通用调用元数据和 DeepSeek 内部 thinking 策略，Codex 行为保持不变。

已完成：

- `AgentCallOptions(agent="", task="", stage="")` 成为 adapter 通用可选参数；旧调用无需传入 options。
- `DeepSeekAdapter.complete(prompt, workspace, options=None)` 会优先读取 `options.agent`，否则从 prompt 第一行 `AGENT: xxx` 自动识别 Agent。无 `AGENT:` 的未知任务默认使用 `enabled-medium`，避免质量下降。
- DeepSeek 内部固定三档策略：`disabled-medium`、`enabled-medium`、`enabled-high`；当前没有 Agent 默认分配到 high 档。
- `disabled-medium` 请求发送 `thinking: {"type": "disabled"}` 和 `temperature`，不发送 `reasoning_effort`。
- `enabled-medium` 请求发送 `thinking: {"type": "enabled"}` 和 `reasoning_effort: "medium"`，不发送 `temperature`。DeepSeek 官方会把 `medium` 映射为 `high`，但系统内部仍按 medium 档表达策略意图。
- `enabled-high` 请求发送 `thinking: {"type": "enabled"}` 和 `reasoning_effort: "high"`，不发送 `temperature`；目前保留为空策略表。
- `CodexCLIAdapter.complete(prompt, workspace, options=None)` 接受 options 但忽略它，不新增 `-c` 或任何 reasoning 配置。
- DeepSeek 响应中的 `reasoning_content` 不展示、不保存、不拼接；adapter 仍只返回 `message.content`。

当前默认策略：

- thinking disabled medium：`director`、`research_intent`、`outline_stage_role`、`direction_proposer`、`version_comparator`、`chapter_summarizer`、`dialogue_enhancer`、`atmosphere_enhancer`、`hook_enhancer`、`style_normalizer`、`revision_self_check`、`outline_editor`、`chapter_goal_agent`、`chapter_conflict_agent`、`chapter_hook_agent`、`scene_breakdown_agent`、`scene_conflict_check_agent`、`style_editor`、`simulated_reader`、`bible_update_extractor`。
- thinking enabled medium：`retrieval_context_synthesizer`、`outline_stage_synthesizer`、`outline_planner`、`outline_reviser`、`world_builder`、`chapter_card_synthesizer`、`scene_synthesizer`、`chapter_writer`、`continuity_editor`、`structure_editor`、`character_arc_editor`、`review_synthesizer`、`revision_planner`、`targeted_reviser`、`bible_conflict_checker`、`bible_update_synthesizer`、`final_bible_update_extractor`。
- thinking enabled high：暂无默认 Agent。

验证：

```bash
.venv/bin/python -m pytest tests/test_deepseek_adapter.py tests/test_codex_adapter.py
# 17 passed
.venv/bin/python -m pytest
# 160 passed
```


## 33. 大纲阶段 Director 判断与进度可见性

本轮优化阶段化大纲共创的路由语义，重点解决 `options_ready` 阶段中“继续改当前阶段”与“接受并推进下一阶段”的判断。

已完成：

- `DirectorService` 增加大纲阶段专用确定性分类：查看阶段、极短确认推进、回答待确认问题、提供新修改意见、将剩余问题交由系统裁量并推进。
- Director JSON prompt 增补 `active_workflow`、`outline_stage`、`outline_stage_status`、`pending_questions`、`pending_question` 和最新用户输入，并说明大纲阶段动作语义：`run_current_stage`、`advance_current_stage`、`answer_pending_questions`、`show_stage`、`ask_user`。
- `DirectorDecision.from_dict` 支持把上述语义动作映射到现有执行动作，避免下游图大规模改名。
- 待确认问题不再被视为必须逐项回答的阻塞项；用户可逐条补充，也可明确交给系统按当前建议默认裁量后推进。默认裁量摘要会写入 `locked_constraints`、`director_task_args.default_discretion_summary` 和锁定阶段 artifact。
- `graph_outline` 直接入口同步支持当前阶段查看、默认裁量推进和 JSON Director 输出解析；阶段提示文案从“必须确认”改为“可补充确认”。
- `build_outline_collaboration_graph(adapter, store, progress=None)` 新增可选进度回调；阶段生成会输出准备上下文、3 个角色 Agent、汇总 Agent、保存产物；阶段推进会输出锁定、进入下一阶段、最终合并和 Bible 更新事件。
- CLI `outline`、`plan-outline`、`compose` 路径传入同一 `[Stage] message` 进度回调；`DirectorService`/chat/飞书执行 outline 推进时也透传进度。

验证：

```bash
.venv/bin/python -m pytest tests/test_director_service.py tests/test_outline_collaboration.py tests/test_graph_writer.py
# 67 passed
.venv/bin/python -m pytest
# 167 passed
.venv/bin/python tests/smoke_outline_collaboration.py
# outline collaboration smoke ok
.venv/bin/python tests/smoke_phase2_chat.py
# phase2 chat smoke ok
.venv/bin/python tests/smoke_phase2.py
# phase2 smoke ok
```

剩余限制：

- 阶段角色 Agent 仍串行执行。
- 默认裁量摘要当前记录用户交托意图和待裁量问题，不额外调用模型生成更长解释。

## 34. State 瘦身与项目记忆层

本轮将大纲共创从“完整产物塞进 state.json”调整为“薄 state + Markdown artifact + project_memory.md”。

已完成：

- `NovelState` 新增 `project_memory_version`、`rolling_dialogue_summary`、`outline_stage_summaries`，用于保存轻量阶段摘要和滚动上下文入口。
- `LocalStore.save_state()` 写入轻量版 state：`outline_stage_artifacts` 每阶段只保留 `stage/status/path/summary/stage_memory/pending_questions/updated_at` 等恢复字段；完整 `synthesis` 和 `role_reviews` 不再长期写入 `state.json`。
- 旧 state 自动迁移：保存时若发现旧 artifact 内含完整 `synthesis`，会写入 `outline/<stage>.md` 和 `outline_stages/<stage>.md`，再把 JSON 中的阶段 artifact 压成轻量结构。
- 新增 `project_memory.md`，包含“不可压缩种子设定”“阶段记忆”“滚动对话摘要”。原始创意、锁定约束、风格偏好进入不可压缩种子；阶段记忆来自阶段产物的短条目。
- 角色短评改为调试产物：阶段 Markdown 默认不展示短评；短评另存到 `outline/debug/<stage>_role_reviews.md`。
- 大纲阶段 prompt 的 `previous_stage_context/current_stage_context` 优先使用 `stage_memory/summary`，不再拼接完整阶段正文。DirectorService prompt 也会读取 `project_memory.md` 并用阶段记忆展示当前阶段。
- `messages` 保存时截断为最近 12 条、单条最多约 500 字；`append_message` 同步改为短消息保留，避免长 assistant 回复反复污染上下文。
- 待确认问题回答支持紧凑编号输入，例如 `1可以2伏笔3结局阶段再设计` 会被解析为逐题回答并重跑当前阶段，不再当作普通修改意见。

验证：

```bash
.venv/bin/python -m pytest tests/test_outline_collaboration.py
# 25 passed
.venv/bin/python -m pytest tests/test_director_service.py tests/test_graph_bible.py tests/test_graph_chapter_plan.py
# 28 passed
.venv/bin/python -m pytest
# 171 passed
.venv/bin/python tests/smoke_outline_collaboration.py
# outline collaboration smoke ok
.venv/bin/python tests/smoke_phase2_chat.py
# phase2 chat smoke ok
```

剩余限制：

- 阶段记忆目前用规则抽取生成短条目，没有新增一次模型调用做专门记忆压缩。
- `rolling_dialogue_summary` 字段已预留；当前默认由最近短消息生成 `project_memory.md` 的滚动摘要。

## 35. 阶段确认闭环与 Agent 调用信息

本轮修复阶段共创在 `options_ready` 状态下误把“确定进入下一阶段”识别成修改意见的问题，并补充 Agent 进度打印的模型信息。

已完成：

- 阶段确认不再依赖单个词硬编码；`确定/确认/同意/继续` 单独出现不会触发推进。只有主脑判断用户明确表达“进入下一阶段/推进到下一阶段/锁定当前阶段并继续”等迁移意图时才推进。
- `DirectorService` 和 `graph_outline` 的直接入口同步使用同一确认语义，避免 chat/CLI 路径行为不一致。
- 锁定阶段前会自动闭环当前阶段未决问题：若 artifact 或 state 中仍有 `pending_questions`，系统会生成 `default_discretion_summary`，写入当前阶段 artifact、`stage_memory` 和 `locked_constraints`，并清空当前阶段待确认项，再进入下一阶段。
- 这避免了故事流程、分卷大纲、章节大纲等后续阶段带着上一阶段问题继续滚动污染上下文。
- 新增 `progress.describe_agent_call()` / `with_agent_metadata()`，Agent 进度消息会打印模型与 effort，例如 DeepSeek 会显示 `model=deepseek-v4-pro, effort=medium` 或 `effort=disabled-medium`，mock 显示 `model=mock, effort=n/a`。
- 大纲、章节卡、场景卡、审稿、修订和正文生成流程的 Agent 进度消息已接入模型/effort 信息。

验证：

```bash
.venv/bin/python -m pytest tests/test_outline_collaboration.py tests/test_director_service.py
# 52 passed
.venv/bin/python -m pytest
# 176 passed
.venv/bin/python tests/smoke_outline_collaboration.py
# outline collaboration smoke ok
.venv/bin/python tests/smoke_phase2_chat.py
# phase2 chat smoke ok
```

## 36. Agent 进度耗时与简化模型打印

本轮优化进度输出的可读性和可观测性。

已完成：

- `progress.describe_agent_call()` 从 `model=deepseek-v4-pro, effort=disabled-medium` 简化为 `deepseek-v4-pro/disabled-medium`。
- Agent 完成后会追加耗时，格式为 `deepseek-v4-pro/disabled-medium/12.3s`；mock 为 `mock/n/a/0.0s`，Codex CLI 为 `codex/cli-default/12.3s`。
- 新增 `run_with_progress()`，LangGraph 节点进度会在开始和完成时各输出一次，完成消息包含耗时。
- 新增 `complete_with_timing()`，大纲阶段角色 Agent 和汇总 Agent 在直接阶段节点中也会记录单次调用耗时。
- 大纲、章节卡、场景卡、正文生成、审稿、修订、定稿等已有 Agent 进度输出已接入简化模型/effort/耗时格式。

验证：

```bash
.venv/bin/python -m pytest tests/test_outline_collaboration.py tests/test_graph_drafting.py tests/test_graph_review.py tests/test_graph_revision.py tests/test_graph_chapter_plan.py tests/test_graph_scene.py
# 41 passed
.venv/bin/python -m pytest tests/test_finalize_chapter.py tests/test_outline_collaboration.py
# 31 passed
.venv/bin/python -m pytest
# 176 passed
.venv/bin/python tests/smoke_outline_collaboration.py
# outline collaboration smoke ok
.venv/bin/python tests/smoke_phase2_chat.py
# phase2 chat smoke ok
```


## 37. DirectorService 统一对话入口

本轮将自然语言对话入口统一收敛到 `DirectorService`，避免 chat、outline 直接入口和旧 graph builder 各自做关键词分流。

已完成：

- `build_chat_graph()` 改为 Director-backed wrapper；旧 `.invoke()` 调用仍可用，但会先调用 `DirectorService.handle_turn()`。
- `build_outline_collaboration_graph()` 同样改为 Director-backed wrapper；底层大纲图保留阶段执行节点，不再作为公开入口的第一层自然语言路由。
- `select_chat_graph()` 不再按 research/outline 关键词提前分流，统一返回 chat graph，由服务层主脑决定后续节点。
- `DirectorService` 增加阶段元问题识别：`接下来我该做什么？`、`下一步呢？`、`现在怎么办？` 只返回当前阶段、未决问题和可选操作，不推进、不闭环、不重跑 Agent。
- 收窄大纲阶段反馈判定，只有明确修改、补充、选择、风格调整、编号回答或锁定约束才重跑当前阶段；紧凑编号回答和锁定约束迁入服务层处理。
- 兼容旧 graph `.invoke()` 已预先追加 user message 的模式，`DirectorService` 会避免重复追加同一条用户消息。

验证：

```bash
.venv/bin/python -m pytest
# 179 passed
.venv/bin/python tests/smoke_outline_collaboration.py
# outline collaboration smoke ok
.venv/bin/python tests/smoke_phase2_chat.py
# phase2 chat smoke ok
```

## 38. 阶段临时约束不再污染对话

本轮修复阶段确认/裁量内容在 CLI 中反复显示并进入全局 `locked_constraints` 的问题。

已完成：

- CLI `chat` 和 `outline` 输出不再展示 `锁定约束` 列表，避免对话被内部控制信息淹没。
- 大纲阶段的待确认回答、默认裁量摘要、闭环摘要和“这个设定别改”类阶段反馈不再持久化到全局 `state.locked_constraints`。
- 这些信息仍作为当次 `revision_instruction` 或阶段 artifact 的 `default_discretion_summary` 参与当前阶段生成/锁定；阶段产物生成后不再作为跨阶段全局约束继续滚动。
- `DirectorService` 会在每轮开始清理历史上已污染进 `locked_constraints` 的阶段临时约束，防止旧项目继续把这些长文本带入 prompt。

验证：

```bash
.venv/bin/python -m pytest
# 179 passed
.venv/bin/python tests/smoke_outline_collaboration.py
# outline collaboration smoke ok
.venv/bin/python tests/smoke_phase2_chat.py
# phase2 chat smoke ok
```


## 39. 大纲阶段临时回修与原阶段恢复

本轮修复已进入后续大纲阶段时回修早期阶段会误跑当前/下一阶段的问题。

已完成：

- `DirectorService` 增加大纲阶段回修确定性识别，支持“第1阶段/第一阶段/方向定位阶段/回到方向/重修世界观”等目标定位。
- 当用户在第 5 阶段等后续阶段要求修改第 1 阶段等已锁定早期阶段时，决策写入 `stage`、`return_stage` 和 `auto_relock_target`，确认后临时切到目标阶段执行。
- `run_selected_outline_agent()` 增加临时回修执行路径：保存原阶段和待确认问题，重跑目标阶段，早期目标阶段自动重新标记为 `locked`，然后恢复原当前阶段继续修改。
- 回修不会自动重跑中间阶段，也不会推进下一阶段；后续阶段会在之后生成时读取更新后的早期阶段记忆。
- Director prompt 已补充阶段回修规则，避免把“方向定位术语太生硬”误当成普通当前阶段重跑或重新生成方向提案。

验证：

```bash
.venv/bin/python -m pytest tests/test_director_service.py tests/test_outline_collaboration.py
# 61 passed
.venv/bin/python -m pytest
# 185 passed
.venv/bin/python tests/smoke_outline_collaboration.py
# outline collaboration smoke ok
```

## 34. 多 Agent 性能改造：Metrics、ContextProfile、并行与持久化

本轮按 `plan.md` 的 Phase A-G 完成首版性能与上下文治理改造，目标是不改变用户入口和核心工作流的前提下，降低多 Agent 阶段的上下文膨胀和串行等待成本。

已完成：

- 新增 Agent trace：`complete_with_metrics(...)` 会记录 graph、node、agent、prompt profile、prompt/output 字符数、估算 token、耗时、状态、模型信息和上下文来源，写入 `projects/<project>/debug/agent_runs.jsonl`。
- 新增 `scripts/show_agent_metrics.py`，可按 `prompt_chars`、`output_chars` 或 `elapsed_ms` 查看最重 Agent 调用。
- 新增 ContextProfile：`build_context_bundle(...)` 返回 `ContextBundle(text, sources, total_chars, estimated_tokens, truncated)`，`build_context(...)` 保持旧接口兼容。
- Review 上下文去重：`review_context` 不再包含完整 `chapter_draft`；完整草稿只出现在 editor prompt 的 `## Chapter Draft` 中一次；review synthesizer 不读取完整草稿，只读取五份 compact editor JSON。
- 新增 output contract：review editor 输出归一化为短 JSON，review synthesizer 输出归一化为结构化 JSON；非 JSON 输出会降级为短结构。
- 新增可控并行：`AI_NOVELIST_PARALLEL_AGENTS=1` 时，review 五个 editor、outline 同阶段 role agent、chapter planning 的 goal/conflict/hook agent 会在单节点内部并行执行；默认关闭。
- 并行实现遵守状态写回约束：worker 线程只接收 prompt 快照并调用 adapter；所有结果回到主线程后统一写入 `NovelState` 并保存。
- 持久化优化：`project_memory.md` 使用 `.sha256` digest 避免内容不变时重复写入；ArtifactRecord 增加 `sha256` 和 `chars`，同类型/章节/阶段同 digest 不重复注册；已落盘的大字段在 `state.json` 中保存短摘要。
- Prompt 精简：review editor、chapter planning 子 Agent 和 outline role prompt 增加 OUTPUT_BUDGET，要求不复述上下文、不输出分析过程、限制条数和单条长度。

新增配置：

```bash
AI_NOVELIST_PARALLEL_AGENTS=0|1      # 默认 0
AI_NOVELIST_MAX_PARALLEL_AGENTS=1..8 # 默认 3
```

新增查看命令：

```bash
.venv/bin/python scripts/show_agent_metrics.py --project demo --top prompt_chars
.venv/bin/python scripts/show_agent_metrics.py --project demo --top elapsed_ms
```

当前边界：

- 并行默认关闭，避免真实 Codex CLI 或 API 受本机资源、配额和速率限制影响。
- 不做 LangGraph fan-out；只在单节点内部并行独立 Agent。
- Stage 之间仍串行；outline synthesizer、review synthesizer 和 chapter card synthesizer 仍等待其前置 Agent 全部完成。
- trace 不保存完整 prompt 或完整 output，只记录尺寸、耗时和 manifest。

最终验证补充：

```bash
.venv/bin/python -m pytest
# 200 passed
.venv/bin/python tests/smoke_phase2.py
# phase2 smoke ok
.venv/bin/python tests/smoke_outline_collaboration.py
# outline collaboration smoke ok
.venv/bin/python tests/smoke_phase2_chat.py
# phase2 chat smoke ok
.venv/bin/python tests/smoke_phase2_compose.py
# phase2 compose smoke ok
.venv/bin/python tests/smoke_full_workflow_mock.py
# full workflow mock smoke passed
.venv/bin/ai-novelist compose --project perf-context-mock --idea "一个失忆工程师在月球城市追查自己的小说手稿" --chapter 1 --mock --auto-approve
# 通过；当前新项目 compose 会先推进大纲阶段
.venv/bin/ai-novelist write-chapter --project perf-context-mock --chapter 1 --mock --auto-approve
# 通过
AI_NOVELIST_PARALLEL_AGENTS=1 AI_NOVELIST_MAX_PARALLEL_AGENTS=3 .venv/bin/ai-novelist review --project perf-context-mock --chapter 1 --mock --auto-approve
# 通过，review 返回 revise / 72
.venv/bin/python scripts/show_agent_metrics.py --project perf-context-mock --top prompt_chars
.venv/bin/python scripts/show_agent_metrics.py --project perf-context-mock --top elapsed_ms
# 均可显示 trace 表
```


## 40. Agent 完成行轻量用量显示

目标：在不打印上下文正文、不增加进度噪声的前提下，让长任务执行时能看到每次 Agent 调用的大致上下文长度和 token 消耗。

已完成：

- Agent 完成进度行在现有 `模型/effort/耗时` 后追加轻量用量：`ctx=<estimated_prompt_tokens>/<model_context_capacity> | tok≈<estimated_total_tokens>`。
- `ctx` 表示本次 prompt 估算 token / 模型上下文总容量；`tok≈` 表示 prompt + output 的估算 token，继续使用当前 `estimate_tokens()` 规则。
- 大纲阶段 role Agent 和大纲汇总 Agent 已接入该显示，示例：`deepseek-v4-pro | disabled-medium | 9.9s | ctx=6.2K/1M | tok≈7.1K`。
- 大纲阶段 role Agent 的 prompt 包含“角色专属关注点”，同一阶段不同角色仍共享阶段记忆，但任务关注点和 prompt 长度会按角色区分。
- `agent_runs.jsonl` trace 新增 `estimated_output_tokens`，继续不保存完整 prompt 或 output。

后续待办：

- 扩展 adapter 返回结构，保留 DeepSeek/Codex provider 的真实 usage；没有真实 usage 时继续使用估算值。
- 在 `scripts/show_agent_metrics.py` 增加按 token 汇总、按 graph/node/agent 聚合和单项目总消耗统计。
- 将章节卡、场景卡、正文、审稿、修订、定稿等非大纲路径的 Agent 完成行逐步接入同一轻量用量显示；保持开始行不展示 token，因为输出消耗尚未知。

## 41. Direction 阶段边界收紧

目标：修复 outline 共创中“方向定位 direction 阶段”过度发散到世界观规则、组织流程、制度机制和具体剧情的问题。

已完成：

- Direction role prompt 增加专用边界：只允许类型定位、主角行动原则、核心爽点、核心冲突方向、情绪基调、主题边界、反转原则和禁区。
- Direction synthesizer prompt 改为只输出 `## 方向定位稿` 下的 6-8 条方向原则；每条不超过 80 个中文字符。
- Direction prompt 明确禁止具体世界观规则、宗门/组织流程、制度条款、申请表、审批、考评、备案、绩效、KPI、具体人物关系细则、剧情桥段、章节安排和专有名词清单。
- 新增 `sanitize_direction_stage_output()`，在 direction synthesis 保存前和 formatter 输出时去重标题、把 `## 方向控制稿` 统一为 `## 方向定位稿`，并把常见过细制度词替换为抽象原则。
- `format_stage_markdown()` 对 direction 不再额外添加 `# 方向定位` 或 `## 方向控制稿` 包装，避免嵌套标题。
- Mock direction 输出改为 8 条宏观方向原则，覆盖类型、行动原则、爽点、冲突、情绪、主题、反转和禁区。

当前边界：

- Sanitizer 是本地规则后处理，可清理常见制度化词和重复标题，但不能理解所有真实模型可能生成的隐性具体设定；主要约束仍由 prompt 边界承担。
- 用户原话明确包含的词不会被 sanitizer 强制替换，避免误删用户有意指定的设定方向。

## 42. Outline 共享 Prompt 边界整改

目标：按 `00_INDEX.md` 推荐顺序先执行 `08_outline_stage_shared_role_prompt.md` 和 `09_outline_stage_shared_synthesizer_prompt.md`，给八阶段大纲共创建立共享边界。

已完成：

- `build_outline_stage_role_prompt()` 改为通过 `outline_stage_boundary_prompt(stage)` 注入 stage-specific 允许/禁止内容。
- 所有 outline stage 的 role prompt 都包含 `STAGE_BOUNDARY`，明确只处理本阶段职责，不越权生成完整大纲、世界观、章节正文或无依据 canon。
- Role 输出预算收紧为 opportunities/risks/suggestions 各最多 2 条、每条不超过 80 中文字符、总输出不超过 500 中文字符。
- `build_outline_stage_synthesizer_prompt()` 改为通过 `outline_stage_synthesizer_output_rule(stage)` 选择阶段专属结构，避免非 direction 阶段都套同一份 `Director 汇总` 模板。
- 非 direction synthesizer 增加通用边界：不输出候选菜单式 A/B/C、不跨阶段扩写、不新增无依据 canon、总长 1200-1800 中文字符、确认问题最多 3 条。
- `format_stage_markdown()` 对非 direction 阶段会识别 synthesis 自带 Markdown 标题，避免生成 `## Director 汇总` + 阶段标题的重复标题。

当前边界：

- 本轮只完成共享 role/synthesizer prompt 边界；`01-07` 各具体 outline 阶段的专项细化仍可继续按索引逐个执行。
- 共享边界不改变现有 graph 接口、状态字段或产物路径。

## 43. Concept 阶段专项边界整改

目标：执行 `01_outline_stage_concept.md`，让 outline 共创的故事概念阶段只锁定故事核心概念，避免提前生成世界观、人物关系细则、章节列表或制度化机制。

已完成：

- `concept` stage boundary 收紧为只允许故事钩子、一句话概念、主角欲望、核心冲突、主要悬念、叙事承诺、主题问题、反转原则和待后续阶段展开的确认点。
- `concept` forbidden 明确加入世界规则清单、组织流程、人物亲密机制、章节列表、第1章、第一卷、分卷结构、申请表、审批、备案、绩效和 KPI。
- `concept` synthesizer 固定输出 `## 故事概念稿`，只写 5-7 条短句，每条不超过 90 中文字符，并必须覆盖一句话概念、主角欲望、核心冲突、叙事承诺、反转原则和待后续展开。
- 新增 prompt 回归测试，确认 concept prompt 保留核心冲突、主角欲望和反转原则，同时包含过细内容禁区。

当前边界：

- 本阶段只做故事核心概念，不产出世界观规则、人物关系机制、章节/分卷安排或制度细则。
- 待后续展开只能作为交给世界观、人物或流程阶段处理的方向标记。

## 44. Worldbuilding 阶段专项边界整改

目标：执行 `02_outline_stage_worldbuilding.md`，让 outline 共创的世界观阶段只建立可支撑剧情的运行原则，避免默认扩写行政流程、审批机制、KPI、备案、绩效和申请表。

已完成：

- `worldbuilding` stage boundary 改为允许世界运行原则、力量/技术边界、阵营结构、资源与代价、冲突来源和可渐进揭露的秘密。
- 禁止项明确加入过细行政流程、表格化制度、申请表、申请、审批、备案、考评、绩效、KPI、无关规则清单和未被用户要求的猎奇机制。
- 新增 `worldbuilding_overfine_terms_guard()`：默认要求改写行政化词；当用户原始输入或已锁定产物明确包含这些词时，允许保留但只能作为服务主线冲突的运行原则。
- Worldbuilding synthesizer 输出结构改为 `世界运行原则 / 关键边界 / 冲突资源 / 代价红线 / 仍需确认的问题`，其中运行原则为 6-8 条、每条不超过 100 中文字符，冲突资源最多 3 个。
- 新增回归测试覆盖默认禁用行政化机制，以及用户明确要求“绩效”时不误删但限制为主线原则。

当前边界：

- 世界观阶段不再输出规则清单式百科或表格制度；所有规则都必须说明冲突或代价功能。
- 用户明确要求的行政化词只作为类型设定或主线压力保留，不展开为流程文档。

## 45. Characters 阶段专项边界整改

目标：执行 `03_outline_stage_characters.md`，让人物关系阶段只输出服务主线的人物目标、动机、关系张力、阵营位置和成长矛盾，禁止发明脱离主线的亲密机制或福利场景。

已完成：

- `characters` stage boundary 改为允许主角缺陷与欲望、关键人物目标、动机、关系张力、阵营位置、阵营冲突、背叛/信任风险、成长矛盾和人物弧光。
- 禁止项明确加入福利场景、擦边机制、亲密行为规则、亲密行为、双修审批、道侣流程、道侣绩效、暧昧规则、恋爱系统表格和无主线功能的人设细节。
- 新增 `characters_relationship_guard()`：默认禁止亲密/道侣/福利类机制；当用户原始输入或锁定产物明确包含时，只能保留为目标、动机、阵营位置或主线冲突功能。
- Characters synthesizer 固定输出主要人物 3-5 个，每人使用 `人物 / 目标 / 与主线冲突的功能 / 关系张力 / 弧光风险` 字段，每字段不超过 60 中文字符。
- 新增回归测试覆盖亲密机制禁区、用户明确指定时的保留边界，以及每个角色必须有主线功能或冲突功能。

当前边界：

- 人物关系阶段只做人物的主线作用与冲突张力，不生成福利场景、亲密行为流程或恋爱系统。
- 无主线功能的人设细节必须删除或改写为冲突功能。

## 46. Story Flow 阶段专项边界整改

目标：执行 `04_outline_stage_story_flow.md`，让故事流程阶段只规划主线推进、阶段转折、信息节奏、伏笔和代价，不写正文、不新增全局 canon，也不把“流程”误写成行政或制度流程。

已完成：

- `story_flow` stage boundary 明确“流程”只表示叙事流程，允许主线阶段、阶段目标、关键转折、信息释放节奏、伏笔布置与回收方向、失败代价和高潮方向。
- 禁止项加入完整章节正文、细场景动作、未确立新世界规则、新增世界观 canon、突然新增人物关系、人物长期关系机制、无依据专有名词、行政流程、办理、审批、备案、绩效和申请表。
- Story flow synthesizer 固定使用三幕或四段结构，每段最多 4 个要点，每点不超过 90 中文字符。
- 每段必须覆盖阶段目标、关键转折、信息释放、伏笔布置/回收方向、失败代价和高潮方向。
- 新增回归测试覆盖叙事流程语义、必要结构项和行政流程/正文/new canon 禁区。

当前边界：

- Story flow 只处理叙事结构和信息节奏，不生成章节正文、场景动作、世界新规则或人物关系机制。
- 行政流程词即使出现在角色短评里，也应被改写为叙事压力或代价，而不是制度细节。

## 47. Volume Outline 阶段专项边界整改

目标：执行 `05_outline_stage_volume_outline.md`，让分卷大纲阶段只做卷级结构，不展开逐章细纲、场景动作或新增 canon。

已完成：

- `volume_outline` stage boundary 改为允许卷名、卷目标、卷内主要矛盾、卷级高潮事件、失败/胜利代价、主角能力或认知变化和卷间钩子。
- 禁止项加入逐章细纲、第1章、第2章、章节列表、场景列表、细场景动作、正文片段、新世界观规则、新人物系统和过细制度机制。
- Volume synthesizer 固定规划 3-5 卷，每卷使用 `卷名 / 卷目标 / 卷内主要矛盾 / 高潮事件 / 失败或胜利代价 / 卷间钩子` 字段，每字段不超过 80 中文字符。
- 每卷必须包含目标、高潮、代价和卷间钩子，并说明主角能力或认知变化如何推进全书核心谜团或主题。
- 新增回归测试覆盖卷级结构、逐章细纲禁区和每卷必要字段。

当前边界：

- 分卷阶段不拆章节、不列场景、不写正文，只安排卷级目标和卷间推进。
- 不允许借分卷阶段新增世界规则、人物系统或制度机制。

## 48. Chapter Outline 阶段专项边界整改

目标：执行 `06_outline_stage_chapter_outline.md`，让章节大纲阶段只做章节级目标、冲突、信息增量、钩子和连续性，不提前写场景卡、正文或新增全局设定。

已完成：

- `chapter_outline` stage boundary 改为允许章节编号、章节目标、主要冲突、信息增量、人物状态变化、结尾钩子和连续性提醒。
- 禁止项加入正式正文、对白、中文引号对白、完整场景卡、细场景调度、未确立新规则、新人物关系、额外世界观机制、审批、制度和亲密机制。
- Chapter outline synthesizer 固定首批输出 8-12 章或沿用已有计划，每章使用 `章节编号 / 章节目标 / 主要冲突 / 信息增量 / 人物状态变化 / 结尾钩子 / 连续性提醒` 字段，每字段不超过 60 中文字符。
- 每章必须包含目标、冲突、信息增量和钩子；信息增量只能来自前序已确立设定、分卷目标和故事流程。
- 新增回归测试覆盖章节级字段、正文/对白/场景卡禁区和无依据机制禁区。

当前边界：

- 章节大纲阶段不生成场景卡、正式正文或对白，只输出可进入章节卡前的章节级规划。
- 不允许用新规则、新人物关系或制度/亲密机制填充章节信息增量。

## 49. Review Lock 阶段专项边界整改

目标：执行 `07_outline_stage_review_lock.md`，让审稿锁定阶段只做一致性检查、风险标注、锁定建议和进入章节阶段的准备，不做二次创作或新增 canon。

已完成：

- `review_lock` stage boundary 改为允许一致性问题、阶段承接检查、锁定约束、待确认问题、风险标注、进入章节卡前的准备条件和锁定建议。
- 禁止项加入新增世界规则、新增 canon、重写人物关系、重写剧情流程、生成章节卡、生成正文、候选菜单和二次创作。
- Review lock synthesizer 改为 STATUS-first，要求输出 `STATUS: pass|revise|stop`，并在正文中只能列一致性检查、锁定建议和禁止事项自检。
- 问题最多 8 条，每条不超过 90 中文字符；修复建议必须短，只能指向前序阶段需确认或最小修正。
- 新增回归测试覆盖 STATUS 可解析字段、问题预算和不新增 canon/不生成章节卡正文禁区。

当前边界：

- 审稿锁定阶段只判断是否可锁定，不重写大纲、不补写新设定、不生成章节卡或正文。
- 输出结论必须可被下游解析为 pass、revise 或 stop。

## 50. Direction Proposer Prompt 整改

目标：执行 `10_direction_proposer.md`，让创作方向提案保持候选语义，不把未选方向写成稳定 canon，也不在候选里发明过细机制。

已完成：

- `direction_proposer.md` 明确三个方向仅供选择，未被用户确认前不是小说圣经、稳定 canon 或锁定设定。
- Prompt 要求不得违反 `locked_constraints`，候选与锁定约束冲突时必须改写候选。
- 每个方向只写宏观路线差异，禁止默认生成具体世界规则、组织流程、亲密机制或章节剧情。
- 输出固定为 3 个方向，每个方向 6 个字段，每字段不超过 60 中文字符；建议选择不超过 120 中文字符。
- 新增 prompt loader 回归测试，覆盖候选语义、稳定 canon 禁止、预算和审批/备案/绩效/申请表等过细机制禁区。

当前边界：

- Direction proposer 只给路线候选；未选方向不会进入稳定设定。
- 用户原文明确要求的具体机制只能作为候选风险或风格边界，不得写成已采纳设定。

## 51. World Builder Prompt 整改

目标：执行 `11_world_builder.md`，将世界观生成从“硬规则清单”和设定堆料改为能驱动主线冲突的稳定运行原则。

已完成：

- `world_builder.md` 将世界规则改为 3-5 条与主线冲突直接相关的运行原则，每条不超过 100 中文字符。
- 每条运行原则必须包含 `原则 / 如何制造冲突/代价 / 适用边界`，否则不写。
- 具体机制必须来自用户原话、锁定大纲或已有小说圣经；信息不足时标注待确认，不补造 canon。
- 默认禁止行政流程、审批、备案、绩效、申请表、KPI、考评等细则。
- 可持续写作素材最多 5 个，且每个地点、组织、物件、传闻、仪式或案件必须说明剧情功能。
- 新增 prompt loader 回归测试，确认不再出现“至少 5 条硬规则”，并覆盖冲突/代价字段和制度词禁区。

当前边界：

- World builder 只输出主线相关运行原则，不输出说明书式规则清单。
- 无剧情功能的专有名词、组织、物件和仪式不得堆叠。

## 52. Outline Planner Prompt 整改

目标：执行 `12_outline_planner.md`，让总大纲只整合已有创意、世界观和锁定约束，不为填满结构补造 canon。

已完成：

- `outline_planner.md` 明确总大纲只整合已有创意、世界观和 `locked_constraints`。
- 缺少世界规则、人物关系、动机或结局依据时必须写“待确认”，不得自创。
- 默认禁止新增世界观大规则、人物关系机制、组织流程、章节正文、场景动作和审批/备案/绩效/申请表/KPI 等机制。
- 输出预算限制为整体不超过 1800 中文字符、每幕/每段最多 4 条、伏笔最多 5 个。
- 输出结构新增 `待确认` 段，并明确章节钩子策略只写策略不写正文。
- 新增 prompt loader 回归测试覆盖待确认、预算和禁止补造 canon 边界。

当前边界：

- Outline planner 是整合器，不是设定发明器。
- 信息缺口进入待确认，不用新规则或新关系填补。

## 53. Outline Editor Prompt 整改

目标：执行 `13_outline_editor.md`，让大纲审稿只给可路由问题和短修复建议，保持 `STATUS` / `QUALITY_SCORE` 可解析，不重写大纲或新增设定。

已完成：

- `outline_editor.md` 明确只审稿，不重写大纲，不新增 canon。
- 保留并强调首部可解析字段 `STATUS: pass|revise|stop` 与 `QUALITY_SCORE: 0-100`。
- 修改建议必须指向已有大纲位置、锁定约束冲突或明确缺口；缺信息写待确认。
- 禁止完整重写大纲、新增世界观、人物关系新机制、章节正文和长篇分析过程。
- 输出预算限制为主要问题最多 5 条、修改建议最多 5 条、每条不超过 80 中文字符，锁定约束检查最多 3 条。
- 新增 prompt loader 回归测试覆盖状态字段、预算和审稿边界。

当前边界：

- Outline editor 只产出审稿判断和可路由修复建议。
- 建议不能变成替代大纲或新的稳定设定。

## 54. Outline Reviser Prompt 整改

目标：执行 `14_outline_reviser.md`，将大纲修订从默认完整重写改为最小必要修订，只回应用户修订意见和编辑意见。

已完成：

- `outline_reviser.md` 明确默认不重写完整大纲，只修订 `revision_instruction`、用户修订意见和编辑意见覆盖的区块。
- `locked_constraints` 必须原样保留，不得改写、弱化或替换。
- 未被修订指令覆盖的世界观、人物关系、主线结构和伏笔保持原意与顺序。
- 禁止新增与 `revision_instruction` 无关的 canon、无依据大改、重写锁定约束和扩写正文。
- 只有调用方明确要求完整大纲时才输出完整稿，且需要标注变更处。
- 输出预算限制为变更项最多 8 条、每条不超过 100 中文字符、待确认最多 3 条。
- 新增 prompt loader 回归测试覆盖最小修订、锁定约束原样保留、修订摘要和禁止项。

当前边界：

- Outline reviser 是局部修订器，不是重新规划器。
- 未涉及内容保持原意与顺序；锁定约束按原文保留。

## 55. Chapter Planner Prompt 整改

目标：执行 `15_chapter_planner.md`，区分全书章节拆分和当前章节规划，避免当前章节任务重写全书章节数量。

已完成：

- `chapter_planner.md` 增加模式判断：当前章节模式只输出当前章节写作输入；全书章节拆分模式仅在用户明确要求时输出章节总览。
- 当前章节模式明确不建议全书章节数量，不重写全书章节结构。
- 当前章节允许输出章节目标、阻碍、冲突升级、信息增量、人物变化、结尾钩子和继承约束。
- 禁止新增全局世界观 canon、人物关系机制、无依据设定、场景卡正文、正式正文和无关章节扩写。
- 输出预算限制为当前章细纲不超过 900 中文字符，场景顺序最多 5 个。
- 新增 prompt loader 回归测试覆盖两种模式、当前章边界和预算。

当前边界：

- 当前章节任务不会改写全书章节数。
- 场景顺序只作为当前章功能提示，不生成场景卡或正文。

## 56. Chapter Goal Agent Prompt 整改

目标：执行 `16_chapter_goal_agent.md`，保留章节目标 Agent 的局部判断能力，同时要求所有目标和信息增量有来源依据，不新增 canon。

已完成：

- `chapter_goal_agent.md` 明确所有目标和信息增量必须来自章节大纲、已有章节卡、小说圣经、锁定约束或已有 canon。
- 禁止为了补齐目标新增世界观规则、人物关系、反派、组织或其他 canon。
- 依据不足时写入 `open_questions`，不自行补造。
- JSON schema 增加 `evidence` 与 `source_hint` 字段，每条 goal 必须包含依据。
- 输出仍为 JSON，`goals` 最多 5 条，每条字段内容不超过 80 中文字符。
- 新增 prompt loader 回归测试覆盖 JSON schema、依据字段和 no-new-canon 边界。

当前边界：

- Chapter goal agent 只提炼当前章目标和信息增量。
- 没有证据的目标进入 open_questions，不变成新设定。

## 57. Chapter Conflict Agent Prompt 整改

目标：执行 `17_chapter_conflict_agent.md`，让章节冲突 Agent 只检查和提炼已有冲突，不为了增强冲突新增反派、组织、规则或长期代价机制。

已完成：

- `chapter_conflict_agent.md` 明确只能基于已有章节大纲、章节卡、小说圣经、锁定约束和 Task Context 提炼冲突。
- 禁止新增反派、新组织、新世界规则、新长期代价机制、审批/制度机制或无依据设定。
- 冲突不足时只能写入 `open_questions` 或 `minimal_fix_suggestions`，建议强化已有冲突。
- JSON schema 增加 `conflicts`、`minimal_fix_suggestions`、`open_questions`，每条 conflict 必须包含 `source_hint`。
- 输出仍为 JSON，`conflicts` 最多 5 条，每条字段内容不超过 80 中文字符。
- 新增 prompt loader 回归测试覆盖 source_hint 和 no-new-conflict-source 边界。

当前边界：

- Chapter conflict agent 只排序和诊断已有冲突。
- 冲突不足时提出最小强化建议或问题，不发明新敌人和新规则。

## 58. Chapter Hook Agent Prompt 整改

目标：执行 `18_chapter_hook_agent.md`，让章节钩子只服务当前章节和已规划伏笔，不新增 canon 或提前泄露后续真相。

已完成：

- `chapter_hook_agent.md` 明确钩子必须来自已有伏笔、当前章节目标或已规划信息差。
- 禁止新增全局真相、未规划大反转、新世界规则、新角色关系或无依据 canon。
- 不得提前泄露后续真相；需要保留的信息写入 `do_not_reveal`。
- JSON schema 增加 `hooks`、`do_not_reveal`、`open_questions`，每个 hook 必须包含 `source_hint` 和 `reveal_level`。
- `reveal_level` 只能是 `hint|partial|none`，`hooks` 最多 5 条，每条字段内容不超过 80 中文字符。
- 新增 prompt loader 回归测试覆盖 reveal_level、source_hint、禁止泄露和 no-new-canon 边界。

当前边界：

- Chapter hook agent 只设计当前章悬念呈现方式。
- 钩子不创造新真相，只选择已有伏笔的揭露层级。

## 59. Chapter Card Synthesizer Prompt 整改

目标：执行 `19_chapter_card_synthesizer.md`，让章节卡只整合当前章节必需信息，避免把参考资料或临时建议直接写成 canon。

已完成：

- `chapter_card_synthesizer.md` 明确只整合当前章节必需信息，不扩写全书设定。
- 参考资料、role reports、检索内容或临时建议不能直接写成 canon。
- 新增设定、未确认参考事实或来源不明内容必须标记为“待确认”。
- 禁止新增全局设定、吸收未确认参考资料、写正式正文和扩写无关角色关系。
- 场景列表只给场景功能，限制 2-5 个，不写正文、对白或细场景动作。
- 输出预算为每节不超过 120 中文字符、整体不超过 1200 中文字符。
- 新增 prompt loader 回归测试覆盖待确认、场景数量、预算和 no-new-canon 边界。

当前边界：

- Chapter card 是当前章执行卡，不是小说圣经更新。
- 未确认资料留在待确认，不转为稳定设定。

## 60. Scene Breakdown Agent Prompt 整改

目标：执行 `20_scene_breakdown_agent.md`，让场景拆分只把 Chapter Card 拆成可写场景，不改变章节目标和 canon。

已完成：

- `scene_breakdown_agent.md` 明确只能拆分 Chapter Card，不能改变章节目标、关键冲突、结尾钩子或 canon。
- 禁止新增全局世界观、新世界规则、长期人物关系或章节目标之外的副线。
- 禁止正文、对白、心理独白段落和细场景动作。
- 输出改为 JSON，`scenes` 必须 2-5 个。
- 每个场景包含 `purpose/info_delta/turn/entry_state/exit_state`，字段内容不超过 120 中文字符。
- Chapter Card 信息不足时写入 `open_questions`，不补造设定。
- 新增 prompt loader 回归测试覆盖 JSON schema、场景数量和 no-new-canon 边界。

当前边界：

- Scene breakdown 只做结构拆分，不写正文或对白。
- 场景不得引入章节卡之外的新设定或长期关系。

## 61. Scene Conflict Check Agent Prompt 整改

目标：执行 `21_scene_conflict_check_agent.md`，让场景冲突检查只检查已有场景卡问题，输出 JSON，并给最小修正建议。

已完成：

- `scene_conflict_check_agent.md` 改为 JSON-only，不输出 Markdown。
- 只检查冲突重复、动机断裂、信息提前泄露、连续性违背或与 Chapter Card 不一致。
- 禁止新增场景、新人物关系、新世界规则、新 canon、大幅重写或正文。
- 修正建议必须保持场景数量、章节目标和已确立 canon 不变。
- `issues` 最多 5 个，每个建议不超过 80 中文字符；必须补信息时写入 `needs_confirmation`。
- 新增 prompt loader 回归测试覆盖 JSON 输出、issue 数量、最小修正和 no-new-canon 边界。

当前边界：

- Scene conflict check 只做校验和最小修正。
- 不通过新增场景或新增设定解决问题。

## 62. Scene Synthesizer Prompt 整改

目标：执行 `22_scene_synthesizer.md`，让场景卡字段从章节卡和拆分报告继承，必要小细节标记为 scene-local，不改变 canon。

已完成：

- `scene_synthesizer.md` 改为 JSON-only，`scenes` 必须 2-5 个。
- 场景字段必须从章节卡、场景拆分报告、冲突检查报告和已有 canon 继承。
- 地点、出场人物、冲突对象优先来自章节卡和已有 canon。
- 必须补充的小细节标记 `detail_scope: scene-local`，不得写入小说圣经。
- 禁止新增全局地点、组织、规则、未规划人物、无依据感情机制、正文和对白。
- 每场固定 9 个核心字段，每字段不超过 60 中文字符，并带 `source_hint`。
- 新增 prompt loader 回归测试覆盖字段继承、scene-local 标记、字段长度和 no-new-canon 边界。

当前边界：

- Scene synthesizer 只把当前章计划整理成场景卡。
- 小细节只能是场景局部，不升级为小说圣经设定。

## 63. Chapter Writer Prompt 整改

目标：执行 `23_chapter_writer.md`，让正文写手严格按章节卡和场景卡写作，新增细节只限场景表现，不污染 canon。

已完成：

- `chapter_writer.md` 明确必须严格基于章节卡和场景卡生成章节草稿。
- 必须按场景卡顺序推进正文，保留关键冲突、人物变化、结尾钩子和连续性约束。
- 禁止新增 canon、全局设定、世界观规则、未规划角色/组织、人物关系机制、未规划反转或提前泄露后续真相。
- 允许新增内容仅限场景级感官细节、动作细节、环境压力和过渡句，且不写入小说圣经。
- 输出只包含 Markdown 正文，不输出分析、说明、摘要、变更记录、写作计划或自检。
- 无调用方字数配置时建议 2500-4500 中文字。
- 新增 prompt loader 回归测试覆盖 scene-card guard、no-new-canon 和正文-only 输出边界。

当前边界：

- Chapter writer 负责实现卡片，不负责重新规划故事。
- 场景表现细节可以写，事实和 canon 不可改。

## 64. Atmosphere Enhancer Prompt 整改

目标：执行 `24_atmosphere_enhancer.md`，让氛围增强只处理描写密度、环境压力和情绪递进，不改变事实、结构或场景顺序。

已完成：

- `atmosphere_enhancer.md` 增加“描写层编辑边界”。
- 允许增强环境细节、感官描写、情绪递进和危险感表达。
- 禁止新增事件、规则、人物、组织、怪物、剧情转折或新 canon。
- 禁止改变场景顺序、人物行动结果、信息释放顺序或结尾钩子。
- 禁止新增超过原场景事实的剧情动作；事实缺口不补造。
- 输出可为完整修订稿，但修改范围只限描写层，不输出分析或变更记录。
- 新增 prompt loader 回归测试覆盖 no-new-facts guard 和描写层边界。

当前边界：

- Atmosphere enhancer 是语言和氛围增强器，不是剧情扩写器。
- 事实、结构、结尾钩子和 canon 保持冻结。

## 65. Dialogue Enhancer Prompt 整改

目标：执行 `25_dialogue_enhancer.md`，让对白增强只强化已有对白张力和人物声音，不通过台词新增事实、关系状态或信息释放。

已完成：

- `dialogue_enhancer.md` 明确对白只能表达已知事实、当前场景情绪和已建立的人物动机。
- 禁止通过对白新增 canon、秘密、世界规则、后续伏笔或未规划信息。
- 禁止提前揭示后续真相、改变人物关系状态、添加新承诺、新誓言、新设定或新动机。
- 允许删改冗余对白、强化潜台词和语气差异，但不能改变事实含义。
- 输出可为完整修订稿，但新增对白不得引入新的事实信息，不输出分析或变更记录。
- 新增 prompt loader 回归测试覆盖不通过对白新增 canon 和不提前泄露真相边界。

当前边界：

- Dialogue enhancer 是语言与人物声音增强器，不是信息释放改写器。
- 台词不能承担新增设定或新伏笔。

## 66. Hook Enhancer Prompt 整改

目标：执行 `26_hook_enhancer.md`，让钩子增强只强化已有开场异常、中段转折和结尾悬念，不新增核心真相或改变结尾事实。

已完成：

- `hook_enhancer.md` 明确所有钩子必须来自章节卡、场景卡、已有伏笔或当前草稿中已存在的信息差。
- 允许强化既有异常的呈现方式、转折句、悬念力度和信息留白。
- 禁止新增全局真相、大反转、新敌人、新组织、新世界规则或无依据异常。
- 禁止改变结尾事件、结尾事实、人物状态或场景顺序。
- 禁止泄露后续真相；需要保留的信息只做暗示或留白。
- 输出可为完整修订稿，但新增钩子必须可追溯到章节卡/场景卡已有伏笔。
- 新增 prompt loader 回归测试覆盖 source-bound guard 和 no-new-twist 边界。

当前边界：

- Hook enhancer 只调整悬念呈现强度。
- 新钩子不能脱离已有伏笔来源，也不能改写结尾事实。

## 67. Style Normalizer Prompt 整改

目标：执行 `27_style_normalizer.md`，让风格统一只做语言层调整，不改变事实、伏笔、人物状态和场景顺序。

已完成：

- `style_normalizer.md` 增加“事实冻结规则”。
- 允许范围限定为视角一致性、节奏、语气、格式和冗余说明压缩。
- 要求内容事实差异为零。
- 禁止改写剧情事实、信息释放、人物状态、关系状态、伏笔、场景顺序或结尾钩子。
- 禁止增删情节、增删世界观、添加新 canon 或删除关键信息。
- 冗余句如果承载线索，只能压缩表达，不能删除线索。
- 新增 prompt loader 回归测试覆盖事实冻结、钩子和人物状态不变边界。

当前边界：

- Style normalizer 是语言格式处理器，不是剧情修订器。
- 正文事实、伏笔、人物状态、场景顺序和结尾钩子保持冻结。

## 68. Legacy Editor Prompt 整改

目标：执行 `28_editor.md`，让 legacy editor 只输出可路由、可执行、短建议，不重写正文或新增 canon。

已完成：

- `editor.md` 保留兼容 Markdown 结构和可解析 `STATUS` / `QUALITY_SCORE`。
- 明确只审稿，不重写正文，不新增 canon。
- 修改建议必须能映射到现有章节卡、场景卡或草稿位置。
- 禁止与细纲无关的大改建议，禁止发明新设定、新角色、新世界规则或新剧情。
- 输出预算限制为主要问题最多 6 条、修改建议 3-6 条、每条不超过 90 中文字符，连续性风险最多 4 条。
- 新增 prompt loader 回归测试覆盖可解析状态、预算和可路由建议边界。

当前边界：

- Editor 只诊断和路由修复，不生成替代正文。
- 审稿建议必须指向已有章节卡、场景卡或草稿位置。

## 69. Continuity Editor Prompt 整改

目标：执行 `29_continuity_editor.md`，防止连续性编辑通过新增设定补洞，优先使用删减、改序和澄清已有信息。

已完成：

- `continuity_editor.md` 明确连续性修复优先使用删除、澄清已有信息、调整表述、改序或保持既有设定。
- 禁止通过新增设定补洞。
- 禁止新增世界规则、新人物、新伏笔、新章节事件或长篇分析。
- 只有 review_synthesizer 明确标记需要用户确认时，新增设定需求才能进入 `needs_confirmation`，不能进入 `rewrite_tasks`。
- 保留 JSON 输出结构，新增 `needs_confirmation` 字段。
- 输出预算保持 `top_issues<=5`、`rewrite_tasks<=5`、`keep<=3`、每字符串不超过 80 中文字符。
- 新增 prompt loader 回归测试覆盖最小修复和 no-new-canon 补洞边界。

当前边界：

- Continuity editor 只修连续性，不创造新设定。
- 需要新增信息的情况必须转为待确认。

## 70. Structure Editor Prompt 整改

目标：执行 `30_structure_editor.md`，让结构编辑优先调整已有场景目标、顺序、转折和钩子，不新增大剧情或全局设定。

已完成：

- `structure_editor.md` 明确结构建议必须指向已有场景、章节卡、场景卡或草稿位置。
- 修复优先重排、压缩、强化已有场景目标、冲突递进、转折、信息释放和结尾钩子。
- 禁止新增全局反转、新场景群、新人物、新组织、新世界规则或新 canon。
- 禁止建议大幅重写整章；缺失信息写入 `needs_confirmation`。
- 保留 JSON 输出和既有预算：top_issues<=5、rewrite_tasks<=5、keep<=3、每字符串不超过 80 中文字符。
- 新增 prompt loader 回归测试覆盖现有场景定位和 no-new-canon 边界。

当前边界：

- Structure editor 调整现有结构，不发明新剧情。
- 结构问题通过重排、压缩和强化解决。

## 71. Character Arc Editor Prompt 整改

目标：执行 `31_character_arc_editor.md`，让人物弧光编辑只修当前章人物目标、选择、代价和情绪，不通过新增关系 canon 解释动机。

已完成：

- `character_arc_editor.md` 明确只修当前章节已有选择、代价、情绪转折和人物状态连续性。
- 禁止通过新增身世、感情机制、恋爱机制、长期承诺、亲密规则、新阵营关系或新关系 canon 来解释动机。
- 禁止新增未规划人物背景或改变关系状态。
- 修复建议必须指向已有场景、章节卡、场景卡或草稿位置。
- 保留 JSON 输出和既有预算：top_issues<=5、rewrite_tasks<=5、keep<=3、每字符串不超过 80 中文字符。
- 新增 prompt loader 回归测试覆盖当前章人物选择修复和 no-new-relationship-canon 边界。

当前边界：

- Character arc editor 只处理当前章人物选择和情绪连贯性。
- 不用新增身世、亲密机制或阵营关系补人物动机。


## 72. Style Editor Prompt 整改

目标：执行 `32_style_editor.md`，让风格编辑只诊断语言和叙述问题，不改变类型定位、剧情事实或世界观。

已完成：

- `style_editor.md` 明确只诊断语言和叙述问题。
- 修复建议限定为删减说明、改写语气、调整节奏、统一视角或压缩解释比例。
- 禁止新增设定、改剧情、改类型定位、重写正文或输出长篇示范段落。
- 禁止改变事实、信息释放、人物状态、伏笔或结尾钩子。
- 风格目标不明确时写入 `needs_confirmation`，不得重设类型方向。
- 保留 JSON 输出和既有预算：top_issues<=5、rewrite_tasks<=5、keep<=3、每字符串不超过 80 中文字符。
- 新增 prompt loader 回归测试覆盖语言层诊断和 no-fact/type-change 边界。

当前边界：

- Style editor 是语言与叙述诊断器，不是剧情或类型方向编辑器。
- 风格问题只能转化为语言层最小修复任务。


## 73. Simulated Reader Prompt 整改

目标：执行 `33_simulated_reader.md`，让模拟读者只表达阅读体验缺口和困惑，不提出新增剧情、CP 或世界机制。

已完成：

- `simulated_reader.md` 明确只能表达阅读体验缺口和困惑。
- 允许反馈吸引力不足、困惑点、拖沓处、最想继续看的既有线索和应保留内容。
- `rewrite_tasks` 必须转化为澄清已有内容、强化已有线索、压缩拖沓段落或保留有效吸引点。
- 禁止新增剧情走向、新人物关系、新世界机制、CP 福利或长评式扩写。
- 禁止使用“新增一个”“安排一个”“让他们恋爱”等方式提出新内容。
- 保留 JSON 输出和既有预算：top_issues<=5、rewrite_tasks<=5、keep<=3、每字符串不超过 80 中文字符。
- 新增 prompt loader 回归测试覆盖读者反馈 no-new-story 边界。

当前边界：

- Simulated reader 是体验反馈器，不是创作方案生成器。
- 读者任务只能指向已有内容的澄清、强化或压缩。


## 74. Review Synthesizer Prompt 整改

目标：执行 `34_review_synthesizer.md`，让审稿汇总只汇总上游 editor JSON 的阻塞问题和高优先级任务，不新增问题或扩写任务。

已完成：

- `review_synthesizer.md` 明确只汇总上游 editor JSON 和 simulated_reader JSON 中已提出的问题。
- 禁止新增上游未提出的问题、风险、新设定任务或剧情方案。
- 禁止扩写长任务、重写正文，合并时不得改变原意。
- `rewrite_tasks` 必须去重，并按阻塞程度和修复优先级排序。
- `graph_review.py` 的 review_synthesizer prompt contract 同步收紧为 blocking_issues<=3、issues<=6、rewrite_tasks<=8、每项<=90 中文字符。
- `output_contracts.normalize_review_synthesis` 同步执行相同数组和字数上限。
- 新增 prompt loader、graph review 和 output contract 回归测试覆盖来源约束、预算和可解析 JSON 归一化。

当前边界：

- Review synthesizer 只做上游审稿 JSON 的优先级汇总。
- 汇总不能创造新问题，也不能把短建议扩写成新修订方案。


## 75. Revision Planner Prompt 整改

目标：执行 `35_revision_planner.md`，让修订计划只把 `review_v1.json` 转成可执行任务，不新增 review 外剧情方案。

已完成：

- `revision_planner.md` 改为严格 JSON 输出，顶层结构为 `revision_plan_v1`。
- 每个 task 必须来源于 `review_v1.json` 的 blocking_issues、issues 或 rewrite_tasks，并包含 `source`。
- 禁止新增剧情、世界观、人物关系，或未在 review 中出现的大改。
- 只允许输出定向修订目标、涉及场景、保留内容、禁止触碰约束和待确认项。
- review 信息不足时写入 `open_questions`，不得补造任务。
- mock revision plan 同步改为 JSON-first，并保留 `revision_plan_v1` 标记以兼容修订流程。
- 新增 prompt loader 和 graph revision 回归测试覆盖任务数量、JSON 可解析和 review 溯源。

当前边界：

- Revision planner 是 review JSON 到任务清单的转换器。
- 修订计划中的任务必须可追溯到 review_v1.json。


## 76. Targeted Reviser Prompt 整改

目标：执行 `36_targeted_reviser.md`，让定向修订只改 `revision_plan_v1` 指定区域，未涉及段落保持原意和顺序。

已完成：

- `targeted_reviser.md` 增加“最小编辑规则”。
- 明确只改 `revision_plan_v1.tasks` 指定的问题区域。
- 未涉及段落必须保持原意、叙事顺序、信息释放和人物状态。
- 允许输出完整 `draft_v2` Markdown 正文，但修改范围必须受 revision_plan 限制。
- 禁止全章大改、重排无关段落或改动未列入任务的段落。
- 禁止新增世界观、新 canon、新人物关系、新伏笔或未在修订计划中要求的剧情。
- 要求保留 `revision_plan_v1.keep` 和 `do_not_touch` 中列出的内容。
- 新增 prompt loader 回归测试覆盖 minimal edit guard 和 no-unrelated-rewrite 边界。

当前边界：

- Targeted reviser 可输出完整稿，但不是全章重写器。
- 修订范围必须受 revision_plan_v1 指定任务约束。


## 77. Revision Self Check Prompt 整改

目标：执行 `37_revision_self_check.md`，让修订自检只检查 revision_plan 是否完成，发现新问题只标记，不扩写方案。

已完成：

- `revision_self_check.md` 改为严格 JSON 输出。
- 输出字段限定为 `tasks_status`、`new_risks`、`decision`。
- 每个 revision_plan_v1 task 对应一个完成状态：done、partial 或 missing。
- 新风险只标记，不扩写修复方案；`new_risks` 最多 5 条。
- 禁止提出新增剧情建议、重写正文、新设定、新世界观或 revision_plan_v1 外的新修订任务。
- mock revision self check 同步改为可解析 JSON。
- 新增 prompt loader 和 graph revision 回归测试覆盖 JSON 可解析、自检状态和 no-new-creation 边界。

当前边界：

- Revision self check 是任务完成核验器，不是二次审稿或创作规划器。
- 新问题只能进入风险标记，并通过 decision 返回 review_again。


## 78. Version Comparator Prompt 整改

目标：执行 `38_version_comparator.md`，让版本比较只比较旧版和新版差异，给出采用建议，不生成第三版。

已完成：

- `version_comparator.md` 明确只比较差异，不创作第三版大纲。
- 采用建议必须基于用户偏好、locked_constraints 和差异风险。
- 禁止新增第三版大纲、新设定、详细改写方案或正文。
- 禁止建议“改成全新版”或展开长方案。
- 输出保留核心变化、人物变化、冲突变化、风格变化、风险变化和是否建议采用新版。
- 输出预算限制为每节最多 3 条、每条不超过 80 中文字符。
- mock version comparison 同步改为短条目形式。
- 新增 prompt loader 回归测试覆盖 no-third-version 和每节预算边界。

当前边界：

- Version comparator 是差异分析器，不是新版创作器。
- 采用建议只能基于已有版本差异、用户偏好和锁定约束。


## 79. Bible Conflict Checker Prompt 整改

目标：执行 `39_bible_conflict_checker.md`，让小说圣经冲突检查可路由，包含严重度和是否阻塞写入。

已完成：

- `bible_conflict_checker.md` 保持严格 JSON 输出。
- conflict 字段扩展为 `type`、`name`、`current`、`incoming`、`severity`、`blocking`。
- `severity` 限定为 low、medium、high；high 必须 blocking=true。
- 禁止 Markdown、长解释、新设定和自动合并方案。
- 输出预算限制为 conflicts<=10、字符串字段<=120 中文字符。
- `detect_bible_conflicts` 同步输出完整字段，并限制冲突数量和字符串长度。
- 新增 prompt loader 和 bible 回归测试覆盖空冲突、字段完整、severity/blocking 和 no-auto-merge 边界。

当前边界：

- Bible conflict checker 只识别冲突，不合并 canon。
- blocking=true 的冲突用于阻止错误 stable canon 自动写入。


## 80. Bible Update Extractor Prompt 整改

目标：执行 `40_bible_update_extractor.md`，让小说圣经更新提取器只提取稳定事实，候选和未确认内容进入 open_questions。

已完成：

- `bible_update_extractor.md` 明确只提取已经确认的 stable canon。
- 禁止把临时讨论、候选方向、未确认设定、review 建议或模型自行补全写入正式字段。
- 候选方案、临时建议、未确认问题和依据不足内容必须进入 `open_questions`。
- 正式数组项必须包含 `source_hint` 或 `evidence`。
- project、concept、style_guide 的非空更新也必须来自上下文明确表述。
- 输出预算限制为每类最多 8 项、open_questions 最多 8 条、字符串<=120 中文字符。
- mock bible update extractor 同步为代表性正式项增加 `source_hint`。
- 新增 prompt loader 回归测试覆盖 stable canon、open_questions 和 source_hint 边界。

当前边界：

- Bible update extractor 只提取可追溯的稳定 canon。
- 未确认和候选内容不能进入正式圣经字段。


## 81. Bible Update Synthesizer Prompt 整改

目标：执行 `41_bible_update_synthesizer.md`，让小说圣经更新摘要明确区分已写入、未写入和待确认内容。

已完成：

- `bible_update_synthesizer.md` 改为“已写入 / 未写入 / 待确认”三分结构。
- “已写入”只能包含已确认并实际写入小说圣经的稳定设定。
- conflict、blocking conflict、open_questions、候选方案和未确认内容必须进入“待确认”。
- 被过滤、因冲突阻塞或依据不足的内容进入“未写入”，并说明短原因。
- 禁止补写新设定、把冲突当成已确认或输出长篇解释。
- 输出预算限制为每节最多 5 条、每条不超过 90 中文字符。
- mock bible update synthesizer 同步输出三分结构。
- 新增 prompt loader 回归测试覆盖三分结构和 no-conflict-as-canon 边界。

当前边界：

- Bible update synthesizer 只汇总写入状态，不创造 canon。
- 冲突和待确认项不能被表述成已写入稳定设定。


## 82. Final Bible Update Extractor Prompt 整改

目标：执行 `42_final_bible_update_extractor.md`，让定稿章节提取器只从定稿章节和摘要中提取明确发生事实，不从修辞隐含推断世界规则。

已完成：

- `final_bible_update_extractor.md` 明确只提取定稿章节中明确发生的事实、状态变化和显性线索。
- 禁止从修辞、比喻、氛围、情绪描写或象征物推断世界规则。
- 禁止输出 world_rules、project 或 concept，避免从单章定稿隐含推断全局 canon。
- 禁止覆盖旧设定为空、加入未发生事件、未来预测或读者评价。
- timeline、foreshadowing、characters、plot_threads 中每项必须包含 `source_hint`。
- chapter_summaries 限制为每章 80-180 中文字符。
- mock final bible updates 与 fallback_bible_updates 同步为结构化条目增加 `source_hint`。
- 新增 prompt loader 和 finalize 回归测试覆盖 explicit-facts-only、no-world-rule-inference 和 source_hint 边界。

当前边界：

- Final bible update extractor 只记录定稿已发生事实。
- 单章修辞、氛围和隐喻不能升级为小说圣经世界规则。


## 83. Chapter Summarizer Prompt 整改

目标：执行 `43_chapter_summarizer.md`，让章节摘要只记录已发生事实、明确状态变化和显性线索，不预测后续。

已完成：

- `chapter_summarizer.md` 明确只记录本章已发生事实、人物状态变化、关键线索和章末钩子。
- 禁止加入未在正文出现的新设定。
- 禁止推断未明说动机，禁止把读者猜测写成事实。
- 禁止预测后续剧情，禁止“可能”“似乎暗示后续会”等预测表达。
- 禁止输出读者评价、优缺点分析或写作建议。
- 输出预算保持 80-180 字，只输出摘要正文。
- `normalize_summary` 和 `fallback_chapter_summary` 上限收紧为 180 字。
- 新增 prompt loader 和 finalize 回归测试覆盖 facts-only、no-prediction 和长度上限。

当前边界：

- Chapter summarizer 只记录本章可验证连续性事实。
- 摘要不能承担预测、评价或新设定写入功能。


## 84. Director Prompt 整改

目标：执行 `44_director.md`，让 Director 只做路由、澄清和提炼用户约束，不生成阶段产物或自动越阶段。

已完成：

- `director.md` 增加 Director 硬约束。
- 明确 Director 只做路由、澄清、提炼用户约束和安排下一步。
- 禁止生成阶段产物、长篇大纲、世界观正文、章节正文或替子 Agent 创作。
- 禁止在一次用户请求中静默推进多个大纲阶段。
- 禁止把模型推测、候选方案或未确认信息写入 `locked_constraints`。
- `task_args` 限定为用户原意、明确章节号、明确阶段名和必要执行参数。
- 输出预算要求 user_message<=120 中文字符、next_steps<=3。
- `DirectorDecision.from_dict` 同步执行 user_message 和 next_steps 预算。
- 新增 prompt loader 和 director_service 回归测试覆盖路由边界和预算执行。

当前边界：

- Director 是调度和约束提炼层，不是创作执行层。
- 多阶段推进必须由用户明确确认，不能静默连续执行。


## 85. Research Intent Prompt 整改

目标：执行 `45_research_intent.md`，让调研意图提取器严格区分原创题材、同人/原作和网络调研需求。

已完成：

- `research_intent.md` 明确只有用户提到同人、原作、作者、作品名、书名号、查资料、网络调研或 `/research` 时才 NEED_RESEARCH=yes。
- 增加原创题材反例：修仙文、原创月球城市悬疑、赛博仙侠、克苏鲁风格故事等不触发调研。
- 禁止把量词、类型词、题材词当成作品名。
- 明确“想写一本 X 类型小说”表示原创类型偏好，不把 X 当作品名。
- 固定输出字段保持 NEED_RESEARCH、QUERY、WORK_TITLE、AUTHOR、INTENT、REASON。
- REASON 限制为不超过 60 中文字符。
- 新增 prompt loader 和 research_workflow 回归测试覆盖原创题材不误判调研。

当前边界：

- Research intent 只识别调研需求，不给创作建议。
- 原创题材词不能被当作已有作品名。


## 86. Retrieval Context Synthesizer Prompt 整改

目标：执行 `46_retrieval_context_synthesizer.md`，让检索上下文只整理来源事实、可用线索和使用边界，不创作、不 canon 化。

已完成：

- `retrieval_context_synthesizer.md` 明确只基于给定搜索结果整理来源事实、可用线索和使用边界。
- 禁止生成大纲、世界观设定、章节正文或写作方案。
- 禁止编造搜索结果之外的事实，禁止无来源事实。
- “可用事实”每条必须带 `source_id`，对应原始搜索结果编号。
- “创作相关线索”必须保持素材性质，不能转成 canon、正史或硬设定。
- 禁止把二手资料、搜索摘要、论坛猜测直接当原作正史。
- 输出预算限制为每节最多 6 条。
- mock 和 fallback retrieval context 同步输出 `[source_id: N]` 与 stable canon 使用边界。
- 新增 prompt loader 和 research_workflow 回归测试覆盖 source_id 和 no-canon 边界。

当前边界：

- Retrieval context synthesizer 是事实简报整理器，不是创作器。
- 检索线索只有被用户确认后才可进入创作约束或 stable canon。

## 87. 节奏改造 Phase 1（Prompt + 章节卡 Schema）

目标：执行 `plan.md` 的 Phase 1，用最小代码变更先把章节卡与提示词对齐“节奏目标优先”。

已完成：

- `graph_chapter_plan.CHAPTER_CARD_SECTIONS` 改为节奏字段优先：新增 `本章功能/目标强度/张力来源/结尾方式/禁止升级项/延后信息`，并取消“关键冲突/结尾钩子”必填。
- `chapter_card_synthesizer.md` 增加 Synthesizer Rule：必须显式输出 `采纳建议/拒绝建议/延后建议`，并声明“关键冲突/结尾钩子”为条件项。
- `scene_synthesizer.md` 增加约束：`张力来源不等于冲突`，允许沉默、误解、信息不对称等低强度张力。
- `hook_enhancer.md` 增加节奏护栏：当章节为软收束/余波/过渡时不得新增硬钩子；必须遵守“禁止升级项”。
- `review_synthesizer.md` 增加 P0/P1/P2/P3 分级规则（保持现有 JSON 字段不变）。
- mock 输出同步到新章节卡结构：`CodexCLIAdapter._mock_chapter_card` 增加节奏字段与采纳/拒绝/延后建议示例。

当前边界：

- 这是 Phase 1 最小落地，尚未引入动态路由和 `PacingTarget` 数据结构（Phase 2）。
- 运行时仍会执行既有 Agent 编排，但输出侧已被节奏字段约束。

## 88. 节奏改造 Phase 2-5（完整落地）

目标：按 `plan.md` 持续完成 Phase 2~5，把节奏目标从 Prompt 约束升级为运行时约束。

### Phase 2：PacingTarget + 动态章节规划

已完成：
- 新增 `src/ai_novelist/pacing.py`：`PacingTarget`、章节卡字段解析、强度/钩子推断、动态字段规则与 Agent 选择规则。
- `graph_chapter_plan.py` 新增 `load_pacing_target_node`，先推断章节节奏目标再跑章节规划。
- `run_chapter_planning_agents_node` 改为动态选择：
  - 低强度章：`restraint_agent` 替代 `chapter_conflict_agent`。
  - 软/无钩子章：`ending_resonance_agent` 替代 `chapter_hook_agent`。
- `validate_chapter_card_node` 改为动态必填校验：强度与钩子强度决定是否必须出现“关键冲突/结尾钩子”。

### Phase 3：场景规划与写作增强防升压

已完成：
- `graph_scene.py` 校验逻辑改为基于 `PacingTarget` 的动态场景字段校验（低强度章不强制冲突对象/场景转折）。
- `graph_drafting.py` 把固定 `hook_enhance` 改为 `pacing_aware_enhance_node`：
  - 允许升压时执行 `hook_enhancer`。
  - 低强度章改走 `restraint_polisher` + `emotional_resonance_polisher`。
- 新增对应 prompts：`restraint_polisher.md`、`emotional_resonance_polisher.md`。

### Phase 4：审稿/修订节奏守门

已完成：
- `graph_review.py` 新增 `pacing_guard_editor` 参与并行审稿。
- `review_synthesizer` 输出与归一化扩展为：
  - `blocking_fixes`
  - `pacing_safe_fixes`
  - `backlog_suggestions`
  - `rejected_suggestions`
- `graph_revision.py` 改为只使用 `blocking_fixes + pacing_safe_fixes`，并显式忽略 backlog/rejected。
- `revision_self_check` 结果额外抽取 `pacing_self_check` 到 state。

### Phase 5：Finalize 节奏回写

已完成：
- `graph_finalize.py` 新增 `build_pacing_report`。
- 每章定稿后写出 `chapters/chapter_xxx/pacing_report.json`（通过 `LocalStore.pacing_report_path`）。
- `state.director_task_args["pacing_report"]` 回写目标/实际强度、钩子强度和偏差。

### 适配与基础设施同步

- `codex_cli` mock 适配新增 Agent：`chapter_pacing_agent/restraint_agent/ending_resonance_agent/restraint_polisher/emotional_resonance_polisher/pacing_guard_editor`。
- `deepseek` Agent 思考策略清单同步加入上述新 Agent。
- 新增 prompts：
  - `chapter_pacing_agent.md`
  - `restraint_agent.md`
  - `ending_resonance_agent.md`
  - `restraint_polisher.md`
  - `emotional_resonance_polisher.md`
  - `pacing_guard_editor.md`

### 验证

```bash
.venv/bin/python -m pytest
# 263 passed

.venv/bin/python tests/smoke_chapter_pipeline_mock.py
# chapter pipeline mock smoke passed
```

当前边界：
- Phase 5 的“最近三章自动升压/降压建议”已具备数据基础（`pacing_report.json`），但 Director 的主动策略推荐仍是下一步可增强点。

## 89. 大纲共创链路重构 v3（七阶段 + 三层门）

目标：按 `plan.md` 完整落地七阶段大纲共创重构，移除活跃 `concept` 阶段，建立 Stage Contract + Source Ledger + Quality Gate 的泛化治理体系。

已完成：

- 新增 `src/ai_novelist/outline/`：
  - `stage_contracts.py`：定义 7 个 active stage 合约（保留 `concept` legacy alias 到 `direction`）。
  - `legacy_migration.py`：旧项目 `concept` 与 `outline_draft` 兼容迁移。
  - `source_ledger.py`：来源账本与具体 canon 启发式检测。
  - `stage_guard.py`：阶段越权、无来源 canon、公式绝对因果、抽象机制语言检测与改写降级。
  - `question_filter.py`：过滤模型自造二选一确认问题。
  - `renderers.py`：阶段输出规则统一渲染。
- `graph_outline.py`：
  - `OUTLINE_STAGES` 切换为七阶段，`STAGE_ROLES` 删除 `concept`。
  - `detect_stage_reference` 将“故事概念/核心概念/一句话故事”映射到 `direction`。
  - `ensure_outline_stage`/legacy 逻辑改为复用新模块。
  - `run_outline_stage_node` 接入 `guard_stage_output` + `filter_stage_confirmation_questions`。
  - `outline_stage_synthesizer_output_rule` 改为委托 `build_stage_output_rule`，移除旧世界观模板结构（`世界运行原则/关键边界/冲突资源/代价红线`）。
  - `sanitize_direction_stage_output` 改为委托统一质量门并做标题/行政词兜底清洗。
  - 最终锁定文案改为七阶段；最终合并按 active stages 排序，并兼容追加“旧版故事概念参考”。
- `director_service.py`：修复 `persist_outputs` 高风险逻辑，不再根据 `task_args.stage` 覆盖当前阶段后再锁定；始终锁当前阶段再推进。
- `context_builder.py`：previous stage memory 顺序改为七阶段。
- `prompts/world_builder.md`：
  - 移除“禁止词表中心”策略，改为分类质量规则。
  - 输出改为题材自适应结构：`世界一句话/题材核心结构/主角所在组织或生活圈/势力资源与日常压力/可持续写作素材/待确认事项/自检`。
- `prompts/director.md`：阶段说明改为七阶段，并声明 concept 兼容映射到 direction。
- `adapters/codex_cli.py` mock：
  - outline stage mock 改为七阶段结构。
  - 移除活跃 concept 输出。
  - 世界观 mock 改为新结构，移除公式化绝对因果写法。

测试与回归：

- 新增 `tests/test_outline_stage_controls.py`，覆盖：
  - active stages 去 concept。
  - stage contract 可用性。
  - 方向阶段具体代价降级。
  - 用户显式代价保留。
  - 公式化句式模式检测。
  - 世界观抽象机制语言清洗。
  - 确认问题过滤。
  - legacy concept 迁移。
  - `persist_outputs` 锁当前阶段 bug 回归。
- 更新 `tests/test_outline_collaboration.py`、`tests/test_director_service.py`、`tests/test_graph_writer.py`、`tests/test_prompt_loader.py`、相关 smoke 断言到七阶段与新模板。
- 全量验证：

```bash
.venv/bin/python -m pytest
# 297 passed
```

当前边界：

- `concept` 仅保留 legacy artifact 兼容，不参与 active flow。
- 质量门仍为启发式，后续可继续细化来源匹配与句式改写策略。

