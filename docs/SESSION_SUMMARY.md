# 会话摘要与上下文压缩记录

更新时间：2026-05-21
项目路径：`/home/ubuntu/1.project/ai-novelist`

## 1. 项目目标

构建一个 Linux 环境下的智能小说作家助手：

- 使用 LangGraph 编排 research、outline、写作、审稿等多 Agent/多工作流。
- 使用 Codex CLI 作为默认模型执行入口，并支持 DeepSeek API。
- 以 `ai-novelist chat` 作为唯一推荐主入口。
- 支持 mock 验证、本地文件存储和后续飞书接入。

## 2. 当前完成状态

### 阶段 1：已完成

能力：`init`、最小 outline 图、`show`、mock/真实模式、本地文件存储。

说明：`graph_minimal.py` 仍保留阶段 1 最小图，但 CLI `outline` 已升级为大纲共创调试/兼容入口。

### 阶段 2：已完成本地版

能力：

- `chat`：唯一推荐主入口，Director Agent 连续对话并调度 research、outline 和写作子工作流。
- `research/retrieval`：搜索原始资料，生成通用 `retrieval_context`，并继续生成兼容旧流程的参考简报、原作事实、来源列表和不确定点。
- 本地小说知识库优先 RAG：可通过 `AI_NOVELIST_LOCAL_CORPUS_DIR` 或 `chat --local-corpus-dir` 指定 `.txt/.md` 语料目录，research 本地命中时不调用 mock/web。
- `outline`：交互式大纲共创流程，支持方向、生成、审稿、修订、版本比较、查看、锁定和保存。
- `compose`：一次性完整多 Agent 创作图。
- 单步 Agent 命令：`worldbuild`、`plan-outline`、`plan-chapters`、`write-chapter`、`review`。

## 3. 最新架构摘要

```text
chat 主入口
  -> 写入 state.user_request + messages
  -> research 需求: build_research_graph(search_backend, store, adapter=adapter)
     search_backend 可为 LocalFirstSearchBackend(LocalRAGSearchBackend, mock/web fallback)
  -> active_workflow == outline: build_outline_collaboration_graph
  -> 其他请求: build_chat_graph
  -> 打印阶段日志、Director 消息和产物正文
  -> 保存 state.json
```

工作流状态通过 `NovelState.active_workflow/current_stage` 管理：

- `active_workflow="research"`：research 执行中。
- research 完成后进入 `active_workflow="outline"`，`current_stage="confirm_reference_brief"`。
- 大纲保存后清空 `active_workflow`，`current_stage="chapter_plan"`。
- 用户明确停止大纲共创时清空 `active_workflow/current_stage`。

## 4. 当前关键图

### Research 图

```text
detect_research_need
  -> build_research_queries
  -> search_sources
  -> synthesize_retrieval_context
  -> synthesize_reference_brief
  -> save_research_result
  -> ask_user_confirm
  -> END
```

本地 RAG 结果：

- `source=local_corpus`
- `url=local://corpus/<relative_path>#chunk=<id>`
- `metadata` 包含 `file_path`、`relative_path`、`chapter_name`、`chunk_id`、`start_offset`、`end_offset`、`score`

输出：

- `retrieval_query`
- `retrieval_context`
- `retrieval_sources`
- `reference_brief`
- `canon_facts`
- `research_sources`
- `research_uncertainties`
- `reference_brief.md`
- `research_sources.json`

### Outline Collaboration 图

```text
director
  |-- ask_user -> END
  |-- propose_directions -> human_feedback -> END
  |-- worldbuild -> generate_outline -> review_outline -> human_feedback -> END
  |-- generate_outline -> review_outline -> human_feedback -> END
  |-- review_outline -> human_feedback -> END
  |-- revise_outline -> compare_versions -> review_outline -> human_feedback -> END
  |-- show_outline -> END
  |-- show_status -> END
  |-- persist_outline -> END
  `-- stop -> END
```

多轮循环由 CLI/chat 的下一轮用户输入驱动，避免单次 graph invoke 内无限自动修订。

### Director Chat 图

```text
director
  |-- ask_user -> END
  |-- worldbuild / plan_chapters / write_chapter / review / revise_chapter -> run_selected_agent -> END
  |-- propose_directions / generate_outline / review_outline / revise_outline / compare_versions -> run_selected_outline_agent -> END
  |-- show_outline / show_status / persist_outputs -> END
  `-- stop -> END
```

### Compose 图

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

## 5. 关键文件

源码：

- `src/ai_novelist/cli.py`
- `src/ai_novelist/state.py`
- `src/ai_novelist/graph_research.py`
- `src/ai_novelist/graph_outline.py`
- `src/ai_novelist/graph_writer.py`
- `src/ai_novelist/graph_minimal.py`
- `src/ai_novelist/research/search_backend.py`：包含 `MockSearchBackend`、`WebSearchBackend`、`LocalRAGSearchBackend`、`LocalFirstSearchBackend`。
- `src/ai_novelist/adapters/codex_cli.py`
- `src/ai_novelist/adapters/deepseek.py`
- `src/ai_novelist/storage/local_store.py`
- `src/ai_novelist/prompts/*.md`

文档：

- `README.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `docs/SESSION_SUMMARY.md`

测试：

- `tests/test_research_workflow.py`
- `tests/test_outline_collaboration.py`
- `tests/test_graph_writer.py`
- `tests/smoke_outline_collaboration.py`
- `tests/smoke_phase2_chat.py`
- 既有阶段 1/2 测试全部保留。

## 6. 状态字段重点

新增或关键字段：

- `active_workflow`
- `current_stage`
- `retrieval_query`
- `retrieval_context`
- `retrieval_sources`
- `reference_brief`
- `canon_facts`
- `research_sources`
- `research_uncertainties`
- `revision_instruction`
- `locked_constraints`
- `style_preferences`
- `outline_versions`
- `messages`
- `user_request`
- `director_action`
- `director_message`

`from_dict/to_dict` 兼容旧 `state.json`，缺字段时使用默认值。

## 7. 常用命令

推荐入口：

```bash
.venv/bin/ai-novelist chat --project demo-chat --mock
.venv/bin/ai-novelist chat --project demo-chat --mock --local-corpus-dir /data/novels
```

示例对话：

```text
/research 苟在初圣
写苟在初圣同人
给我三个不同方向
查看大纲
保存大纲
写第 1 章
让编辑审稿
保存当前结果
```

兼容入口：

```bash
.venv/bin/ai-novelist outline --project demo-outline --idea "一个失忆工程师在月球城市追查自己的小说手稿" --mock
.venv/bin/ai-novelist compose --project demo-compose --idea "一个失忆工程师在月球城市追查自己的小说手稿" --chapter 1 --mock --auto-approve
```

验证：

```bash
.venv/bin/python -m pytest tests/test_search_backend.py tests/test_research_workflow.py
.venv/bin/python -m pytest
.venv/bin/python tests/smoke_outline_collaboration.py
.venv/bin/python tests/smoke_phase2_chat.py
```

当前验证结果：`65 passed`；本轮目标测试 `tests/test_search_backend.py tests/test_research_workflow.py` 为 `24 passed`。

## 8. 设计决策

- `chat` 是唯一推荐主入口，`outline` 和单步命令保留为兼容/调试能力。
- Director 不直接替代子 Agent，只判断意图、提炼指令、记录约束并调度节点。
- research 在大纲前执行，避免把已有小说/IP/专有名词当普通题材生成错误同人设定。
- research 默认使用 mock 搜索；真实联网可通过 `AI_NOVELIST_SEARCH_PROVIDER=serpapi|tavily|exa` 和对应 API Key 启用。
- 配置本地语料目录后，research 先走本地 `.txt/.md` 关键词检索；至少 1 条本地命中即视为证据充足并跳过 fallback。
- SearchBackend 只返回原始搜索结果；LLM 总结由 `retrieval_context_synthesizer.md` 和 research graph 负责，失败时使用规则 fallback。
- outline 和 writer prompts 都消费已有 `retrieval_context`，但当前不会基于大纲或每个写作任务自动搜索。
- 大纲共创循环跨多轮用户输入推进，而不是单次 invoke 无限循环。
- 当前不引入数据库、队列、FastAPI 或飞书依赖。

## 9. 当前限制

- 本地 CLI，不是服务端。
- 飞书未接入。
- research 默认不联网；配置 SerpAPI、Tavily 或 Exa 后可使用真实搜索。
- 本地 RAG 首版无向量库、索引缓存、增量更新、证据分层 prompt 强化或任务级深度检索。
- 通用检索上下文只复用已有 `/research` 结果，不会主动补搜或按任务刷新。
- 无数据库、队列、权限、多用户隔离或并发锁。
- 真实模式每个 Agent 单独调用一次模型。
- `chat` 的 `persist_outputs` 只保存已有产物，不会自动补齐缺失产物。
- `compose` 不批量生成多章。
- Claude Code Adapter 未实现。

## 10. 本地 RAG 后续安排

仅文档计划，尚未在代码中实现：

- V3 证据质量与 Prompt 强化：在 `retrieval_context_synthesizer.md`、规则 fallback 和 `reference_brief` 中明确区分本地原文证据、网络摘要和 mock 测试资料；本地 chunk 位置应进入输出。
- V4 索引缓存：为本地语料增加基于 `relative_path + mtime_ns + size + chunk 配置` 的缓存，首版优先进程内缓存，必要时再落盘。
- V5 检索质量增强：整理 BM25 近似策略，增加标题/文件名/章节名权重，支持 chunk 参数配置，并评估是否需要向量检索。
- V6 任务级深度检索：抽象 `RetrievalService`，让 writer/worldbuild/review 可按任务补充检索，但必须限制查询数和注入规模，保持未配置本地语料时行为不变。

推荐推进顺序：先做 V3-V4，保证证据可靠性和性能；再抽 service 层；最后根据实际语料规模决定 V5/V6 和飞书入口的先后。

## 11. 后续恢复上下文

建议先读：

```bash
sed -n '1,260p' docs/SESSION_SUMMARY.md
sed -n '1,320p' docs/IMPLEMENTATION_PLAN.md
sed -n '1,260p' src/ai_novelist/graph_research.py
sed -n '1,520p' src/ai_novelist/graph_outline.py
sed -n '1,420p' src/ai_novelist/cli.py
```

然后跑：

```bash
.venv/bin/python -m pytest
.venv/bin/python tests/smoke_outline_collaboration.py
```


## 12. 本轮更新：Research 意图 prompt 化

- 新增 `research_intent.md`，在 research 搜索前用 prompt 识别是否需要调研、作品名、作者和最小搜索词。
- chat 顶层路由先调用 Director prompt；当 ACTION=research 时进入 research graph，规则判断只做兜底。
- `graph_research.build_research_queries` 优先调用 adapter 解析 `QUERY/WORK_TITLE/AUTHOR`，失败时才回退到规则抽取。
- 修复“我想写一本同人小说，苟在初圣的同人，作者是初圣”被抽成“一本”的问题；mock adapter 现在也支持 `AGENT: research_intent`。
- 增加回归测试，确认传给搜索后端的 query 是 `苟在初圣`。

验证：

```bash
.venv/bin/python -m pytest tests/test_research_workflow.py tests/test_search_backend.py
```

结果：目标测试 `38 passed`，全量测试见本轮最终验证。


全量验证：`.venv/bin/python -m pytest`，结果 `68 passed`。


## 13. 本轮更新：项目上下文可见性

- chat 启动时会打印项目状态：参考简报、大纲、世界观、章节产物、最近检索和参考简报路径。
- Director prompt 现在注入已获取参考信息摘要，包括检索查询、关键事实、不确定点、参考简报和来源。
- 新增 `show_reference` 动作，用于响应“查看当前获取的信息 / 调研信息 / 参考简报 / 信息或大纲”等请求。
- outline 共创状态下，这类项目上下文请求会回到 chat Director 处理，避免被 `show_outline` 抢走。
- `show_outline` 在没有大纲但已有参考简报时，会展示参考信息并提示下一步生成方向或大纲。

验证：

```bash
.venv/bin/python -m pytest tests/test_graph_writer.py tests/test_research_workflow.py
```

结果：`40 passed`。


## 14. 本轮更新：DirectorService 智能主脑

- 新增 `DirectorService.handle_turn(project_id, user_text, channel)`，CLI `chat` 已改为统一调用服务层。
- Director prompt 改为优先要求 JSON 决策，保留旧字段格式兼容。
- 增加 `pending_director_decision` 和 `director_task_args`，确认后复用上一轮结构化决策，不重新猜意图。
- 新增 `project_context.md` 读写与任务后刷新，记录目标、事实、不确定点、产物状态和下一步建议。
- research 优先使用 Director 提供的 `research_query/work_title/author`，旧 research intent prompt 仅作缺参兜底。
- 新增 `tests/test_director_service.py` 覆盖 JSON 决策解析、确认执行 research、直接查看状态；补充 LocalStore 上下文读写测试。

验证：

```bash
.venv/bin/python -m pytest tests/test_director_service.py tests/test_local_store.py tests/test_research_workflow.py tests/test_graph_writer.py
```

结果：聚焦测试 `45 passed`。

全量验证：`.venv/bin/python -m pytest`，结果 `74 passed`。

Smoke 验证：`.venv/bin/python tests/smoke_phase2_chat.py`，结果 `phase2 chat smoke ok`。


## 15. 本轮更新：CLI/飞书共用确认选项

- `DirectorTurnResult` 新增 `choices` 字段，确认类动作会返回“确认执行”和“取消”两个结构化选项。
- CLI `chat` 会把选项显示成编号菜单；输入 `1` 执行 pending decision，输入 `2` 取消。
- 文本确认仍兼容：`确认/yes` 执行，`取消/no` 放弃。
- 新增测试覆盖编号确认和编号取消。

验证：

```bash
.venv/bin/python -m pytest tests/test_director_service.py tests/test_graph_writer.py tests/test_research_workflow.py
```

结果：`44 passed`。
