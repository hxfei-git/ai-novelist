# AI Novelist 当前架构与实施计划

## 1. 当前状态

AI Novelist 当前是本地 CLI 版智能小说作家助手，基于 Python、LangGraph、Codex CLI，并支持 DeepSeek API 作为可选模型提供方。

当前推荐使用方式已经收敛为一个主入口：`ai-novelist chat`。Director Agent 作为主脑管理项目上下文，并根据用户输入调度 research、outline collaboration、章节写作、编辑审稿和保存等子工作流。

已完成：

- 阶段 1：最小 LangGraph + 模型适配器 + 本地存储。
- 阶段 2：compose 多 Agent 小说创作图。
- 阶段 2 增强：Director Agent chat 主入口。
- Research/检索增强：chat 可先搜索原始资料，生成通用 `retrieval_context`，并继续产出兼容旧流程的参考简报和来源列表。
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
  |-- SearchResult: title / url / snippet / source
  |-- SearchBackend.search(query, limit=5)  # 只负责原始搜索结果
  |-- MockSearchBackend
  |-- WebSearchBackend: SerpAPI / Tavily / Exa
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

兼容调试入口：

```bash
.venv/bin/ai-novelist outline --project demo-outline --idea "一个失忆工程师在月球城市追查自己的小说手稿" --mock
.venv/bin/ai-novelist compose --project demo-compose --idea "一个失忆工程师在月球城市追查自己的小说手稿" --chapter 1 --mock --auto-approve
```

## 9. 测试覆盖

- `tests/test_graph_minimal.py`：阶段 1 最小图。
- `tests/test_graph_writer.py`：单 Agent、compose、chat、Director 路由、chat 主入口 workflow。
- `tests/test_outline_collaboration.py`：大纲 approve、revise、lock、variant、旧 state 兼容、chat 路由到大纲修订。
- `tests/test_research_workflow.py`：research 触发、mock 搜索、参考简报持久化、research 后进入 outline。
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

当前已验证：`55 passed`，并通过 `smoke_outline_collaboration.py`、`smoke_phase2_chat.py`。

## 10. 当前限制

- 仍是本地 CLI，不是长期运行服务。
- research 默认只有 mock 搜索；真实搜索需要配置 `AI_NOVELIST_SEARCH_PROVIDER` 和 API Key。
- 当前不会基于大纲自动搜索，也不会为每个 worldbuild/write/review 任务自动搜索；只消费已有检索上下文。
- chat/outline 的多轮共创由 CLI 循环驱动，不是后台会话服务。
- 真实模式每个 Agent 独立调用一次模型，没有流式 token 展示。
- `persist_outputs` 只保存当前已有产物，不会自动补齐缺失产物。
- `compose` 只围绕指定章节运行，不批量生成多章。
- 本地文件存储没有并发锁。
- 没有飞书、数据库、队列、Web UI、多租户权限或 Claude Code Adapter。

## 11. 阶段 3 后续计划

```text
飞书用户
  -> 飞书机器人 / Webhook
  -> 会话映射与消息去重
  -> 调用现有 chat 主入口
  -> 后台执行 research / outline / writing 长任务
  -> 飞书消息回复摘要和审核入口
```

下一步应先抽出 service 层，把 CLI 循环中对 `LocalStore`、graph invoke、search backend 和用户输入归一化的逻辑复用给飞书入口。
