# 会话摘要与上下文压缩记录

更新时间：2026-05-24
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

- 真实模型调用默认不再设置内部硬超时；只有显式传入 `--timeout` 时才启用。Codex 进度提示的上下文容量标注已改为 `258K`。
- `chat`：唯一推荐主入口，Director Agent 连续对话并调度 research、outline 和写作子工作流。
- `research/retrieval`：搜索原始资料，生成通用 `retrieval_context`，并继续生成兼容旧流程的参考简报、原作事实、来源列表和不确定点。
- 本地小说知识库优先 RAG：可通过 `AI_NOVELIST_LOCAL_CORPUS_DIR` 或 `chat --local-corpus-dir` 指定 `.txt/.md` 语料目录，research 本地命中时不调用 mock/web。
- `outline`：交互式大纲共创流程，支持方向、生成、审稿、修订、版本比较、查看、锁定和保存。
- Director 交互转译增强：所有用户输入仍先进入 Director；Director prompt 现在包含最近编辑意见和待确认项，并能把“答案 + 接收/接受/同意”的多项确认合并成下游可执行约束。新一轮 turn 会清掉上一次残留的 `error`，避免历史超时在后续成功回复里反复出现；`quit/exit/退出/stop` 现在会在进入决策前直接结束当前 turn，避免被 outline 阶段继续消费。最近补了一条更泛化的引导式问句识别，像“目前我该做什么 / 接下来怎么办 / 下一步呢” 会优先引导用户继续对话，而不是硬推大纲阶段。
- `compose`：一次性完整多 Agent 创作图。
- 单步 Agent 命令：`plan-outline`、`plan-chapters`、`write-chapter`、`review`。`worldbuilding` 已并入 outline 的 `worldbuilding` 阶段。
- Phase 6+7：新增章节卡与场景卡管线，DirectorService 支持 `plan_chapter` 和 `plan_scenes`，旧 `plan-chapters` CLI 保持兼容。

### 世界观大纲框架修复：已完成

能力：

- 新增 `src/ai_novelist/worldbuilding_framework.py`，提供 33 项完整世界大纲框架、18 项精简框架、渲染、结构校验和兜底补节。
- `graph_outline.py` 的 `worldbuilding` 阶段改为世界架构、规则力量、社会权力、剧情服务四个角色，并在 role/synthesizer prompt 中注入 `WORLD_OUTLINE_FRAMEWORK`。
- 世界观输出规则要求从 `## 一、世界核心设定` 到 `## 三十三、结局后的世界格局` 依次输出，禁止退回“世界运行原则/关键边界/冲突资源/代价红线”四段式摘要。
- 生成后执行结构校验；缺失或顺序异常时调用一次 `worldbuilding_structure_repair`，失败后才追加明确兜底占位。
- `state.worldbuilding`、`outline/worldbuilding.md`、`outline_stages/worldbuilding.md` 和根目录 `worldbuilding.md` 同步保存完整 33 项版；后续阶段使用专用摘要和 stage memory 保留关键 canon。

验证：

- `.venv/bin/python -m pytest tests/test_worldbuilding_framework.py tests/test_outline_collaboration.py tests/test_outline_stage_controls.py`：61 passed。
- `.venv/bin/python -m pytest`：305 passed。
- `.venv/bin/python tests/smoke_outline_collaboration.py`：outline collaboration smoke ok。

### Author Craft Layer v1.0：已完成

能力：

- 本地作者语料索引：`index-corpus` 生成 manifest、works、chapters、scenes、chunks、quality_report。
- 构思方法提炼：`extract-craft --mock` 生成 work/chapter/scene/genre profiles，不保存长原文。
- 阶段检索与简报：`craft-brief` 和 AuthorCraftResolver 按 purpose、Pacing Target、craft_mode 生成 StageCraftBrief。
- 工作流接入：outline stage、chapter planning、scene design、drafting、review、revision 自动注入“作者构思参考”。
- 防复刻：draft/revision/finalize 保存后可生成 similarity report；strict 模式 high risk 会进入修订状态。
- 项目记忆：finalize 后生成 `projects/<project>/craft/project_craft_memory.json`，后续检索优先使用本项目方法。
- CLI/配置：新增 `AI_NOVELIST_AUTHOR_CORPUS_DIR`、`AI_NOVELIST_CORPUS_INDEX_DIR`、`AI_NOVELIST_CRAFT_MODE`、`AI_NOVELIST_CRAFT_MAX_CHARS` 等配置。

验证：

- `.venv/bin/python -m pytest`：288 passed。
- `.venv/bin/python tests/smoke_author_craft_mock.py`：1 passed。
- CLI 手工验证：`index-corpus`、`extract-craft --mock`、`craft-profiles`、`craft-brief` 均成功。

### 人物关系蓝图整改：已完成

能力：

- 新增 `src/ai_novelist/characters_framework.py`，提供 14 项完整人物关系蓝图、full/compact 标题清单、结构校验、摘要、stage memory 和兜底补节，并在 prompt 中显式注入 A/B/C/D 级角色提示、关系卡 / 认知进度 / 秘密 / 阵营 schema 线索。
- `graph_outline.py` 在 `characters` 阶段接入专用 framework prompt、结构修复和 artifact summary/memory，角色/合成 prompt 统一注入关系信息差、世界观继承和关系约束。
- `outline/stage_contracts.py`、`outline/renderers.py`、`outline/question_filter.py` 以及 `adapters/codex_cli.py` 已同步改造，`characters` 阶段现在以关系演化、秘密揭露、阵营继承和最多 4 个确认问题为核心。
- `tests/` 已补充人物关系框架与 outline 协作的覆盖，确保提示词和标题顺序都按新蓝图输出。

验证：

- `python3 -m py_compile src/ai_novelist/characters_framework.py src/ai_novelist/outline/stage_contracts.py src/ai_novelist/outline/renderers.py src/ai_novelist/outline/question_filter.py src/ai_novelist/graph_outline.py src/ai_novelist/adapters/codex_cli.py tests/test_characters_framework.py tests/test_outline_collaboration.py`：通过。
- 轻量导入检查：人物关系框架标题校验通过，`characters` 阶段合成提示词包含 `## 人物关系稿`、`## 十三、待确认问题` 和关系蓝图约束，问题过滤上限为 4。
- 当前环境缺少可用的 `.venv` 和 `pytest`，因此未运行完整 pytest / smoke 套件。

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
  |-- worldbuilding -> generate_outline -> review_outline -> human_feedback -> END
  |-- generate_outline -> review_outline -> human_feedback -> END
  |-- review_outline -> human_feedback -> END
  |-- revise_outline -> compare_versions -> review_outline -> human_feedback -> END
  |-- show_outline -> END
  |-- show_status -> END
  |-- persist_outline -> END
  `-- stop -> END
```

多轮循环由 CLI/chat 的下一轮用户输入驱动，避免单次 graph invoke 内无限自动修订。

### Chapter Planning 图

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

输出 `chapters/chapter_XXX/chapter_card.md`，同步 `state.current_chapter_card` 并注册 `chapter_card` artifact。

### Scene Design 图

```text
load_chapter_card
  -> scene_breakdown_agent
  -> conflict_check_agent
  -> scene_synthesizer
  -> validate_scene_cards
  -> save_scene_cards
```

输出 `chapters/chapter_XXX/scene_cards.md`，同步 `state.current_scene_cards` 并注册 `scene_cards` artifact。缺少章节卡时返回提示，不自动补齐。

### Director Chat 图

```text
director
  |-- ask_user -> END
  |-- worldbuilding / plan_chapters / write_chapter / review / revise_chapter -> run_selected_agent -> END
  |-- propose_directions / generate_outline / review_outline / revise_outline / compare_versions -> run_selected_outline_agent -> END
  |-- show_outline / show_status / persist_outputs -> END
  `-- stop -> END
```

### Compose 图

```text
worldbuilding
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
- `src/ai_novelist/graph_chapter_plan.py`
- `src/ai_novelist/graph_scene.py`
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
- `tests/test_worldbuilding_framework.py`
- `tests/test_outline_collaboration.py`
- `tests/test_graph_writer.py`
- `tests/test_graph_chapter_plan.py`
- `tests/test_graph_scene.py`
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
- `active_graph`
- `active_stage`
- `active_chapter`
- `current_chapter_card`
- `current_scene_cards`

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
规划第 1 章
规划第 1 章场景
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
# 128 passed
.venv/bin/python tests/smoke_outline_collaboration.py
# outline collaboration smoke ok
.venv/bin/python tests/smoke_phase2_chat.py
# phase2 chat smoke ok
.venv/bin/python tests/smoke_phase2.py
# phase2 smoke ok
```

当前验证结果：全量 `.venv/bin/python -m pytest` 为 `134 passed`；新增 Phase 6+7 相关回归 `tests/test_graph_chapter_plan.py tests/test_graph_scene.py tests/test_director_service.py tests/test_graph_writer.py` 为 `46 passed`。

## 8. 设计决策

- 用户只和 Director 交互，Director 负责把口语化反馈、多个待确认项的回答和确认词转译为明确的 `instruction`、`task_args` 与 `locked_constraints` 后再调度子 Agent。
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
- 飞书长连接单聊入口已接入，群聊 @、交互卡片、Webhook 和后台队列仍未实现。
- research 默认不联网；配置 SerpAPI、Tavily 或 Exa 后可使用真实搜索。
- 本地 RAG 首版无向量库、索引缓存、增量更新、证据分层 prompt 强化或任务级深度检索。
- 通用检索上下文只复用已有 `/research` 结果，不会主动补搜或按任务刷新。
- 无数据库、队列、权限、多用户隔离或并发锁。
- 真实模式每个 Agent 单独调用一次模型。
- `chat` 的 `persist_outputs` 只保存已有产物，不会自动补齐缺失产物。
- Phase 8 Drafting Graph 未实现；章节卡和场景卡暂作为后续正文生成前置产物，旧正文生成路径不读取它们。
- `plan_scenes` 缺章节卡时只提示先生成章节卡，不自动调用 `plan_chapter`。
- `compose` 不批量生成多章。
- Claude Code Adapter 未实现。

## 10. 本地 RAG 后续安排

仅文档计划，尚未在代码中实现：

- V3 证据质量与 Prompt 强化：在 `retrieval_context_synthesizer.md`、规则 fallback 和 `reference_brief` 中明确区分本地原文证据、网络摘要和 mock 测试资料；本地 chunk 位置应进入输出。
- V4 索引缓存：为本地语料增加基于 `relative_path + mtime_ns + size + chunk 配置` 的缓存，首版优先进程内缓存，必要时再落盘。
- V5 检索质量增强：整理 BM25 近似策略，增加标题/文件名/章节名权重，支持 chunk 参数配置，并评估是否需要向量检索。
- V6 任务级深度检索：抽象 `RetrievalService`，让 writer/worldbuilding/review 可按任务补充检索，但必须限制查询数和注入规模，保持未配置本地语料时行为不变。

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


## 16. 本轮更新：六阶段大纲共创

- 将新项目大纲入口改为六阶段共创：方向定位 -> 世界观设定 -> 人物关系 -> 故事流程 -> 总大纲草案 -> 审稿锁定。
- 新增阶段状态字段与 `projects/<project>/outline_stages/<stage>.md`，每阶段保存角色短评和 Director 汇总；最终第 6 阶段确认后才写 `outline.md`。
- `chat`、`outline`、`plan-outline`、`compose` 不再在新项目上静默生成完整大纲；`compose` 会先推进当前大纲阶段并停止。
- `--auto-approve` 只确认当前已有阶段产物，不会一次性跑完整六阶段。
- Mock adapter 增加阶段角色与阶段汇总输出，测试可确定地覆盖阶段推进。
- 保留旧项目兼容：已有 `outline` 且 `outline.md` 已保存时，`compose` 可继续章节写作；已有草案仍可“查看大纲/保存大纲”。

验证：

```bash
.venv/bin/python -m pytest
.venv/bin/python tests/smoke_outline_collaboration.py
.venv/bin/python tests/smoke_phase2_chat.py
```

结果：全量 `78 passed`；`outline collaboration smoke ok`；`phase2 chat smoke ok`。


## 17. 本轮更新：飞书长连接最小闭环

- 新增 `ai-novelist feishu` 子命令，启动飞书官方 `lark-oapi` 长连接机器人。
- 新增可选依赖 `feishu = ["lark-oapi>=1.6.5"]`，运行时通过 `AI_NOVELIST_FEISHU_APP_ID` 和 `AI_NOVELIST_FEISHU_APP_SECRET` 配置应用凭据。
- 新增 `src/ai_novelist/feishu/`：`FeishuBotService` 负责文本处理，`FeishuSessionStore` 负责 `open_id -> project_id` 映射，`runner` 负责 SDK 长连接与文本回复。
- 第一版支持单聊文本、`/project` 查看当前项目、`/project <project_id>` 切换或创建项目；会话映射保存到 `projects/.feishu_sessions.json`。
- 普通飞书消息统一调用 `DirectorService.handle_turn(..., channel="feishu")`，确认选项用纯文本编号渲染，产物路径追加到回复末尾。
- 按用户选择，飞书优先于 RAG V3/V4 推进；本轮不做群聊 @、交互卡片、Webhook、后台队列或多用户权限。
- README 和 IMPLEMENTATION_PLAN 已同步飞书运行方式、配置、边界和测试覆盖。
- README 已补充飞书开放平台配置步骤：创建企业自建应用、添加机器人能力、订阅 `im.message.receive_v1`、选择长连接事件接收、配置本地环境变量并启动机器人。

验证：

```bash
.venv/bin/python -m pytest tests/test_feishu_integration.py
.venv/bin/ai-novelist --help
.venv/bin/ai-novelist feishu --help
```

结果：飞书单元测试 `7 passed`；全量 `.venv/bin/python -m pytest` 为 `85 passed`；`smoke_outline_collaboration.py` 与 `smoke_phase2_chat.py` 均通过；两个 help 命令可正常显示，其中 `feishu --help` 首次在默认沙箱触发 bwrap 错误，已用提权重跑通过。


## 18. 本轮修复：CLI 搜索提供方 API Key 读取

- 修复 `ai-novelist chat --search-provider exa` 未读取 `EXA_API_KEY` 的问题。
- `config.search_api_key(provider)` 现在可按显式 provider 读取 `SERPAPI_API_KEY`、`TAVILY_API_KEY` 或 `EXA_API_KEY`，再回退到 `AI_NOVELIST_SEARCH_API_KEY`。
- `make_search_backend` 在 CLI 显式传入 `--search-provider` 时，会按该 provider 重新解析 API Key，不再只依赖 `AI_NOVELIST_SEARCH_PROVIDER`。
- README 和 IMPLEMENTATION_PLAN 已补充 `--search-provider exa` 与 `EXA_API_KEY` 的说明。

验证：

```bash
.venv/bin/python -m pytest tests/test_research_workflow.py tests/test_search_backend.py
```

结果：`28 passed`。


## 19. 本轮修复：飞书重复回复去重

- 排查当前机器只运行了一个 `ai-novelist feishu` 进程，重复回复更可能来自飞书长连接事件重投递。
- 新增 `RecentMessageDeduper`，在长连接处理器内按飞书 `message_id` 做进程内最近消息去重。
- 同一 `message_id` 重复到达时直接忽略，不再再次调用 `DirectorService` 或回复飞书。
- 当前仍未实现跨进程去重；如果同时启动多个机器人进程，仍可能重复回复。

验证：

```bash
.venv/bin/python -m pytest tests/test_feishu_integration.py
```

## 20. 本轮修复：查看世界观误路由

- 问题：用户在六阶段共创中输入“查看世界观”时，Director 可能返回 `show_reference`，导致已有世界观草案不展示，只提示没有参考简报或大纲。
- 修复：`detect_outline_stage_request` 现在识别“世界观”本身，并修正故事流程、审稿锁定的阶段枚举名。
- 兼容：若世界观正文已存在于 `state.worldbuilding`，但尚未落为 `outline_stages/worldbuilding.md`，展示阶段时会回退输出该正文。
- 验证：`.venv/bin/python -m pytest tests/test_director_service.py`，结果 `10 passed`。

## 21. 本轮修复：确定世界观仍显示方向定位

- 问题：某些对话会把世界观生成成普通 `worldbuilding` 产物，写入 `state.worldbuilding`，但没有同步 `outline_stage=worldbuilding` 和阶段产物，导致用户说“确定世界观”时仍被提示处于方向定位。
- 修复：新增确定性阶段确认逻辑；“确定世界观/确认世界观/锁定世界观”等会按 `worldbuilding` 阶段确认执行。
- 兼容：确认世界观时若缺少 `outline_stage_artifacts["worldbuilding"]`，自动由已有 `state.worldbuilding` 补建并落盘；同时锁定此前已有阶段。
- 验证：`.venv/bin/python -m pytest tests/test_director_service.py tests/test_outline_collaboration.py`，结果 `23 passed`。

## 22. 本轮修复：开始修订导致人物关系细节丢失

- 问题：飞书返回确认选项后，用户回复“开始修订”没有被识别为确认词，系统重新进入 Director 判断，导致原始详细要求被覆盖为“开始修订”，人物关系阶段没有收到“魔宗圣女、剑宗天才少女”的具体约束。
- 修复：`is_confirmation` 现在接受“开始修订”等表达，待确认决策会沿用上一轮 `original_user_text` 执行。
- 项目修补：已将两名持续登场女性关系线写入 `projects/重生魔门/outline_stages/characters.md`，分别承担魔门内部高位试探与正道外部审判功能。
- 验证：`.venv/bin/python -m pytest tests/test_director_service.py`，结果 `11 passed`。

## 23. 本轮调整：确认流程去特殊词化

- 问题：频繁弹出 1/2 确认菜单会打断大纲共创；用户回复“开始修订”等自然表达时，容易触发二次意图判断并丢失上一轮详细要求。
- 调整：大纲阶段的普通修订类任务直接执行，不再要求确认菜单。
- 调整：已有 pending decision 时，除明确取消外，用户回复都会执行原 pending 决策，并保留原始详细请求；非标准确认回复会作为补充确认文本记录。
- 验证：`.venv/bin/python -m pytest tests/test_director_service.py tests/test_outline_collaboration.py`，结果 `25 passed`。

## 24. 本轮调整：候选项展示语义修正

- 问题：人物关系等阶段产物中会出现“候选项 A/B/C”和“推荐选择”，但系统没有真正进入逐项选择流程，用户容易以为漏掉了选择步骤。
- 调整：非方向阶段的汇总 prompt 改为输出“已采用设定”和“仍需确认的问题”，不再把分析过程伪装成菜单。
- 验证：`.venv/bin/python -m pytest tests/test_outline_collaboration.py tests/test_director_service.py`，结果 `26 passed`。

## 25. 本轮调整：仍需确认的问题不再只写在 Markdown 里

- 问题：阶段产物写了“仍需确认的问题”，但系统没有真正把这些问题作为待回答事项追问用户。
- 调整：生成阶段产物后会解析确认问题，并写入 `pending_questions/pending_question`；回复中也会直接列出问题，用户可逐条回答。
- 验证：`.venv/bin/python -m pytest tests/test_outline_collaboration.py tests/test_director_service.py`，结果 `27 passed`。

## 26. 本轮调整：六阶段大纲连续上下文

- 问题：六阶段大纲虽然按方向定位、世界观、人物关系、故事流程、总大纲草案、审稿锁定推进，但后续阶段主要依赖锁定阶段摘要，容易吃不到前序已生成内容或当前阶段草案，导致设定割裂。
- 调整：阶段角色 prompt 和阶段汇总 prompt 均注入“前序已保存阶段内容”和“当前阶段已有内容”，后续阶段必须基于已保存阶段继续深化。
- 调整：为每个阶段加入连续性要求，明确世界观、人物、流程、总纲和审稿锁定分别应如何承接前序阶段。
- 调整：方向定位阶段改为输出单一 `## 方向定位稿`，不再拆成“一句话方向 / 方向命令 / 不许跑偏”，让第一阶段更轻、更像写作基准。
- 调整：方向定位稿必须覆盖全书开篇切入、中期升级和后期终局，避免只生成开篇故事方向。
- 验证：`.venv/bin/python -m pytest tests/test_outline_collaboration.py tests/test_director_service.py`，结果 `31 passed`；全量 `.venv/bin/python -m pytest`，结果 `105 passed`。

## 27. 本轮更新：全量工作流 Phase 0-3 基础设施

- 按 `plan.md` 的首批实施计划完成 Phase 0-3，小步兼容，不替换现有 `chat`、`outline`、`compose` 和 writer 路径。
- 基线验证通过：`.venv/bin/python -m pytest` 为 `105 passed`，`smoke_outline_collaboration.py` 与 `smoke_phase2_chat.py` 均通过。
- 发现 `.venv` editable 安装指向旧目录 `/home/ubuntu/1.project/ai-novelist`，已用 `.venv/bin/python -m pip install -e . --no-build-isolation` 修正到当前仓库。首次不带 `--no-build-isolation` 因沙箱网络/索引无法获取 `setuptools>=68` 失败。
- 新增 Artifact Registry：`src/ai_novelist/artifacts.py` 与 `tests/test_artifacts.py`，支持空加载、Markdown/JSON 产物保存、latest 查询和版本递增。
- 新增 NovelBible：`src/ai_novelist/bible.py` 与 `tests/test_bible.py`，支持空加载、JSON/Markdown 保存、Markdown 渲染、保守合并和冲突 warning。
- 新增 ContextBuilder：`src/ai_novelist/context_builder.py` 与 `tests/test_context_builder.py`，支持按任务目的组装上下文、读取 Bible/artifact/reference/chapter summary，并保证锁定约束优先保留。
- `NovelState` 增加后续章节管线需要的轻量字段，`LocalStore` 增加 artifact registry 和 novel bible 路径方法；旧 `state.json` 保持兼容。

当前限制：

- 新基础设施目前是旁路能力，尚未被现有 graph 默认使用。
- 后续应从 Bible Graph、Chapter Planning Graph 和 Scene Graph 开始逐步接入，仍需保持 mock 和旧 CLI 兼容。

验证：

```bash
.venv/bin/python -m pytest tests/test_artifacts.py tests/test_local_store.py
.venv/bin/python -m pytest tests/test_bible.py tests/test_state.py
.venv/bin/python -m pytest tests/test_context_builder.py
```

最终验证：`.venv/bin/python -m pytest` 为 `121 passed`；`.venv/bin/python tests/smoke_outline_collaboration.py` 输出 `outline collaboration smoke ok`；`.venv/bin/python tests/smoke_phase2_chat.py` 输出 `phase2 chat smoke ok`。



## 28. 本轮更新：Phase 4 八阶段大纲与 Artifact 注册

- 按计划只实现 Phase 4，未改动 `plan.md`，未接入 Bible Graph 或新章节写作管线。
- 大纲阶段扩展为八阶段：方向定位、故事概念、世界观设定、人物关系、故事流程、分卷大纲、章节大纲、审稿锁定。
- 旧 `outline_draft` 状态和旧 artifact 会在加载/运行时兼容到 `volume_outline`。
- 每个阶段产物现在同时写入 `outline_stages/<stage>.md` 与 `outline/<stage>.md`，并注册到 `artifacts.json`，供后续全量工作流读取。
- Mock adapter 已覆盖新增阶段，测试可在 `--mock` 下稳定推进到最终 `done`。
- 最终 `outline.md` 仍只在审稿锁定确认后生成，并按八阶段顺序合并。

验证：

```bash
.venv/bin/python -m pytest
# 122 passed
.venv/bin/python tests/smoke_outline_collaboration.py
# outline collaboration smoke ok
.venv/bin/python tests/smoke_phase2_chat.py
# phase2 chat smoke ok
.venv/bin/python tests/smoke_phase2.py
# phase2 smoke ok
```


## 29. 本轮更新：Phase 5 Bible Graph 与 Director 操作

- 新增 Bible Graph，可从八阶段大纲产物初始化/更新 `novel_bible.json` 和 `novel_bible.md`。
- `review_lock` 确认后自动初始化小说圣经，并注册 `novel_bible` artifact。
- DirectorService 支持 `init_bible`、`update_bible`、`show_bible`；用户可输入“查看小说圣经”或“更新小说圣经”。
- Mock adapter 增加稳定 Bible updates 输出，测试不依赖真实模型。
- 冲突检测结果暂不阻塞流程，会进入开放问题和 Agent 报告。
- 修复 Bible dataclass 缺省字段反序列化，避免 `default_factory` 字段缺失时污染 state。

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


## 30. 本轮更新：Phase 8-10 章节创作闭环

- 新增 Drafting Graph、Review Graph、Revision Graph，打通“章节卡/场景卡 -> 正文草稿 -> 多编辑审稿 -> 定向修订”的 mock 可验证闭环。
- `write_chapter` 现在会自动补齐缺失章节卡和场景卡，并生成 `chapters/chapter_XXX/draft_v1.md`，同时写旧兼容路径 `chapters/chapter_XXX.md`。
- 审稿新增 `review_chapter` 动作，旧 `review` 仍可作为 alias；审稿输出 `review_v1.md`、`review_v1.json` 和旧兼容 `chapter_XXX_review.md`。
- 修订读取 `review_v1.json` 生成 `revision_plan_v1.md` 和 `draft_v2.md`；达到 `max_revisions` 时停止自动修订。
- `compose --mock --auto-approve` 仍可跑通，mock 下首次审稿要求修订，修订后再次审稿通过。
- 新增 prompts 和 mock responses，确保 `STATUS`、`QUALITY_SCORE` 以及审稿 JSON 字段稳定可解析。
- 新增测试：`tests/test_graph_drafting.py`、`tests/test_graph_review.py`、`tests/test_graph_revision.py`、`tests/smoke_chapter_pipeline_mock.py`；同步更新旧 writer 测试以适配 `review_chapter` 和 draft_v1 持久化。

验证已完成：

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

剩余限制：

- 本轮不实现定稿、章节摘要、Bible 写回和导出。
- 固定版本文件重复运行会被覆盖，版本历史以 artifact registry 为准。
- 大文本仍同时保存在 `state.json` 的当前字段和 Markdown/JSON artifact 中，后续内容变大时应改为摘要加路径。


## 31. 本轮更新：Phase 11-13 定稿、导出与完整工作流

- 新增 Finalize Graph，定稿章节后保存 `final.md`、生成 `summary.md`，并把章节摘要、时间线、伏笔和开放问题写回 NovelBible。
- 新增 Export Graph，按章节号收集所有 `final.md`，生成 `exports/manuscript.md`、`exports/volume_001.md` 和 `exports/novel_bible.md`。
- DirectorService 支持 `finalize_chapter`、`export_project`，并能确定性识别“写/审稿/修订/定稿/导出”章节主流程命令。
- CLI 新增 `finalize-chapter` 和 `export`；README 已记录完整章节闭环和产物路径。
- 新增 prompts：`chapter_summarizer.md`、`final_bible_update_extractor.md`；mock adapter 提供稳定章节摘要和 Bible updates。
- 新增测试：`tests/test_finalize_chapter.py`、`tests/test_graph_export.py`、`tests/test_director_prerequisites.py`、`tests/smoke_bible_update_mock.py`、`tests/smoke_full_workflow_mock.py`。

验证已完成：

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

剩余限制：

- 导出目前只生成 Markdown。
- `final.md`、`summary.md` 和 exports 重复运行会覆盖固定路径，历史版本以 artifact registry 为准。
- 全书多卷拆分仍使用单卷 `volume_001.md`，后续可基于大纲卷信息扩展。

## 32. 本轮更新：Chat 长任务进度可见性

- 新增统一进度辅助 `progress.py`，各图通过可选 `progress` 参数输出阶段事件，默认 no-op 保持旧调用兼容。
- `DirectorService` 在执行写章、审稿、修订、定稿、导出、章节卡、场景卡等长任务前输出执行计划，让 CLI 立即显示下一步会做什么。
- 章节卡、场景卡、正文草稿、审稿、修订、定稿和导出图均补充阶段级提示；`write_chapter` 自动补齐章节卡/场景卡时会继续透传子图进度。
- 本轮不展示模型私有推理链，也不改成流式 adapter；Codex/DeepSeek 仍等待完整模型响应，但用户可看到工作流进度。
- 新增回归测试覆盖 Drafting Graph 进度事件和 Director 写章执行计划。

验证：

```bash
.venv/bin/python -m pytest tests/test_graph_drafting.py tests/test_graph_review.py tests/test_graph_revision.py tests/test_finalize_chapter.py tests/test_graph_export.py tests/test_director_service.py
# 28 passed
.venv/bin/python -m pytest
# 150 passed
.venv/bin/python tests/smoke_full_workflow_mock.py
# full workflow mock smoke passed
```

剩余限制：

- 真实 token 流式输出尚未实现。
- 大纲阶段角色 Agent、多编辑审稿 Agent 仍串行执行，后续可在不破坏产物顺序的前提下评估并行化。

## 33. 本轮更新：DeepSeek Agent Thinking 策略

- 新增 `AgentCallOptions`，adapter 的 `complete` 接口可接收 `options=None`，旧调用保持兼容。
- DeepSeek 根据 `options.agent` 或 prompt 第一行 `AGENT:` 自动选择 thinking 策略；未知 Agent 默认 `enabled-medium`。
- DeepSeek 轻量 Agent 使用 thinking disabled 并保留 `temperature`；综合、规划、写作和汇总类 Agent 使用 thinking enabled + `reasoning_effort=medium`，不发送 `temperature`。DeepSeek 官方会把 `medium` 映射为 `high`，项目内部仍以 medium 表达策略意图。
- 当前没有 Agent 默认使用 `enabled-high`；保留策略表用于后续显式提升。
- Codex CLI adapter 只兼容新 options 参数，忽略 options，不新增 reasoning 配置，mock 输出保持不变。
- DeepSeek 返回 `reasoning_content` 时仍只取 `message.content`。

验证：

```bash
.venv/bin/python -m pytest tests/test_deepseek_adapter.py tests/test_codex_adapter.py
# 17 passed
.venv/bin/python -m pytest
# 160 passed
```


## 34. 本轮更新：大纲阶段 Director 判断与进度可见性

- 优化 `options_ready` 大纲阶段的 Director 判断：简单确认直接推进，具体补充或编号回答会重跑当前阶段，查看请求只展示阶段，用户把剩余问题交给系统裁量时会锁定当前阶段并推进。
- 新增默认裁量摘要记录，随阶段锁定写入 artifact 和锁定约束，避免待确认问题把流程卡死。
- Director prompt 现在显式提供 active workflow、当前 outline stage/status、pending questions 和最新输入，并声明阶段动作语义。
- 大纲图新增可选 progress 回调；阶段生成会显示角色 Agent、汇总 Agent 和保存产物，阶段推进会显示锁定、进入下一阶段、最终合并和 Bible 更新。
- CLI outline、plan-outline、compose 入口以及 chat/飞书服务执行 outline 阶段时都会透传同一进度输出。
- 新增回归测试覆盖系统裁量推进、具体人物补充、编号回答、查看当前阶段、简单确认，以及大纲阶段生成/推进进度事件。

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

- 本轮不新增 CLI 参数，也不做终端动画进度条。
- 真实模型的具体裁量仍依赖当前阶段产物；默认裁量摘要只记录推进依据，不展开成新的长篇设定。

## 35. 本轮更新：State 瘦身与上下文记忆

- `state.json` 改为轻量保存：大纲阶段 artifact 不再长期保存完整 `synthesis` 或 `role_reviews`，只保留路径、摘要、阶段记忆、状态和待确认问题。
- 保存旧项目时会自动把旧 `synthesis` 迁到 `outline/<stage>.md` / `outline_stages/<stage>.md`，因此 `projects/test_chat4` 这类大 state 不需要手工改 JSON。
- 新增 `project_memory.md`，分为不可压缩种子设定、阶段记忆、滚动对话摘要；种子设定保留原始创意和用户锁定约束。
- 阶段 prompt 和 Director 上下文优先读取阶段记忆/摘要，避免完整阶段正文、角色短评和陈旧长回复重复进入上下文。
- 角色短评默认不写入用户可见阶段 Markdown，改存 `outline/debug/<stage>_role_reviews.md` 作为调试产物。
- 消息保存收敛为最近 12 条短消息，长 assistant 内容会截断。
- 编号回答识别支持 `1可以2伏笔3结局阶段再设计` 这类紧凑输入，并映射为待确认问题答案。

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

- 阶段记忆由规则抽取，暂未引入独立记忆压缩 Agent。
- `rolling_dialogue_summary` 已预留字段，当前仍以最近短消息生成默认滚动摘要。

## 36. 本轮更新：阶段确认闭环与 Agent 调用信息

- 修复 `projects/test_chat4` 中“确定进入下一阶段”被误判为当前阶段修改意见的问题；现在由 Director 主脑判断阶段迁移意图，并要求明确包含进入/推进下一阶段语义。
- 确认推进时，如果当前阶段仍有待确认问题，会在锁定前由系统按当前阶段产物自行闭环，写入 `default_discretion_summary`、阶段记忆和锁定约束，并清空当前阶段待确认项；若用户写了“不要进入下一阶段/先不推进”，则保留在当前阶段。
- 该逻辑适用于故事流程及其后的分卷大纲、章节大纲、审稿锁定等阶段，避免带着上一阶段未决问题进入后续流程。
- Agent 进度打印增加模型和 effort 信息；DeepSeek 根据 Agent thinking 策略显示 `disabled-medium` / `medium` / `high`，Codex 显示 CLI 默认，mock 显示 `n/a`。

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

## 37. 本轮更新：Agent 进度耗时与简化模型打印

- Agent 进度中的模型信息从 `model=..., effort=...` 简化为 `模型/effort`。
- Agent 完成消息增加耗时，例如 `deepseek-v4-pro/disabled-medium/12.3s`。
- 大纲阶段角色 Agent、汇总 Agent，以及章节卡、场景卡、正文、审稿、修订、定稿相关 Agent 的进度输出已接入耗时统计。

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


## 38. 本轮更新：DirectorService 统一对话入口

- 所有自然语言对话入口现在先进入 `DirectorService`：`build_chat_graph()`、`build_outline_collaboration_graph()` 和 `select_chat_graph()` 的公开兼容路径不再提前按关键词分流。
- 大纲共创的直接入口仍保留 `.invoke()` 兼容形状，但内部委托服务层主脑，再由服务层执行阶段节点。
- 修复 `接下来我该做什么？`、`下一步呢？`、`现在怎么办？` 在 `options_ready` 阶段被当作修改反馈导致重跑 Agent 的问题。
- 阶段锁定约束、紧凑编号回答、已有最终大纲保存等旧入口语义已迁入服务层处理。

验证：

```bash
.venv/bin/python -m pytest
# 179 passed
.venv/bin/python tests/smoke_outline_collaboration.py
# outline collaboration smoke ok
.venv/bin/python tests/smoke_phase2_chat.py
# phase2 chat smoke ok
```

## 39. 本轮更新：阶段临时约束不再污染对话

- CLI 不再在每轮对话后打印 `锁定约束`，用户对话只显示主脑回复和相关产物提示。
- 阶段待确认回答、系统默认裁量和闭环摘要不再写入全局 `locked_constraints`；它们只在当前阶段生成/锁定时生效。
- 服务层会清理旧项目中已经持久化的阶段临时约束，避免长篇控制信息继续污染后续主脑 prompt。

验证：

```bash
.venv/bin/python -m pytest
# 179 passed
.venv/bin/python tests/smoke_outline_collaboration.py
# outline collaboration smoke ok
.venv/bin/python tests/smoke_phase2_chat.py
# phase2 chat smoke ok
```

## 40. 本轮修复：Chat 全量 Director 优先与写操作确认门

- 修复大纲阶段输入会被 `deterministic_outline_stage_decision()` 提前接管的问题；`DirectorService._decide()` 现在正常路径优先调用 LLM Director prompt，确定性规则只作为模型失败 fallback。
- 新增 `chat` 动作：普通聊天、偏好讨论或非执行性问题只返回 Director 回复，不触发工作流、不弹确认。
- 新增统一写操作确认门：research、大纲生成/修订/推进、章节卡/场景卡、写章、审稿、修订、定稿、导出、保存、小说圣经更新等 mutating action 都会先返回 `1. 确认执行 / 2. 取消`。
- 大纲阶段修订不再免确认；例如“加入魔宗圣女与剑宗天才少女”会先保存 pending decision，用户回复 `1` 后才进入 `[OutlineStage]` 重跑阶段 Agent。
- Mock Director 补齐小说圣经、阶段查看、阶段待确认回答、阶段推进和普通聊天识别，保证 mock 测试覆盖新路由。

验证：

```bash
.venv/bin/python -m pytest tests/test_director_service.py
# 28 passed
.venv/bin/python -m pytest tests/test_director_service.py tests/test_graph_writer.py
# 52 passed
.venv/bin/python -m pytest
# 181 passed
.venv/bin/python tests/smoke_phase2_chat.py
# phase2 chat smoke ok
```



## 41. 本轮修复：大纲阶段临时回修后恢复原阶段

- 修复用户在第 5 阶段等后续阶段要求回到第 1 阶段修改时，系统误重跑当前阶段或推进到下一阶段的问题。
- 新增阶段目标识别：支持“第1阶段”“第一阶段”“方向定位阶段”“回到方向”“重修世界观”等说法。
- 新增临时回修执行路径：确认后临时切到目标阶段重跑 Agent；若目标阶段早于当前阶段，则重写后自动重新锁定，再恢复原当前阶段、原状态和原待确认问题。
- 本轮不做级联重跑：回修早期阶段后，第 2-4 阶段不会自动废弃或重跑；后续阶段继续修改时会读取更新后的阶段记忆。
- 新增回归测试覆盖 CLI 确认流、阶段编号识别和 outline 直入口。

验证：

```bash
.venv/bin/python -m pytest tests/test_director_service.py tests/test_outline_collaboration.py
# 61 passed
.venv/bin/python -m pytest
# 185 passed
.venv/bin/python tests/smoke_outline_collaboration.py
# outline collaboration smoke ok
```

## 42. 本轮更新：多 Agent 性能、上下文与持久化治理

- 新增 `agent_metrics.py`，所有接入的 Agent 调用会写入 `projects/<project>/debug/agent_runs.jsonl`，记录 prompt/output 字符数、估算 token、耗时、模型信息、状态和上下文来源，不写完整 prompt/output。
- 新增 `scripts/show_agent_metrics.py`，支持按 `prompt_chars`、`output_chars`、`elapsed_ms` 查看最重调用。
- 新增 `ContextProfile` / `ContextBundle` / `ContextSource`，`build_context(...)` 仍兼容旧调用；review 上下文不再包含完整章节草稿，避免 `Review Context` 和 `Chapter Draft` 重复。
- 新增 `output_contracts.py`，review editor 和 synthesizer 输出会被归一化为短 JSON；非 JSON 输出会 fallback 成短结构。
- Review Graph 改为 `load_review_context -> review_editors -> review_synthesizer -> decide -> save`；五个 editor 在 `AI_NOVELIST_PARALLEL_AGENTS=1` 时并行，默认仍按顺序执行。
- Outline 同一阶段的 role Agent 可并行执行，role_reviews 仍按 `STAGE_ROLES[stage]` 原顺序写回；阶段之间和汇总 Agent 保持串行。
- Chapter Planning 的 goal/conflict/hook Agent 可并行执行；三者只读取同一份章节上下文，不再读取彼此报告，synthesizer 负责汇总。
- `project_memory.md` 增加 sha256 digest 去重；ArtifactRecord 增加 `sha256` 和 `chars`，相同内容不重复注册；已保存到文件的大字段在 `state.json` 中只保留摘要。
- Review editor、chapter planning 子 Agent 和 outline role prompt 已加入输出预算，要求不复述上下文、不输出长篇分析。

验证：

```bash
.venv/bin/python -m pytest tests/test_agent_metrics.py tests/test_agent_parallel.py tests/test_context_builder.py tests/test_output_contracts.py tests/test_graph_review.py tests/test_graph_chapter_plan.py tests/test_outline_collaboration.py tests/test_artifacts.py tests/test_local_store.py
# 62 passed
```

剩余限制：

- 并行默认关闭；真实模型/API 并行可能受本机资源、账号配额或服务端速率限制影响。
- 当前只并行互不依赖的局部 Agent；synthesizer、阶段推进、定稿、导出等依赖前置结果的节点仍串行。
- ContextProfile 首版为规则预算和字符级裁剪，尚未引入语义压缩 Agent。

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


## 43. 本轮更新：Agent 完成行显示上下文长度与估算 token

- 大纲阶段 role Agent 和汇总 Agent 的完成行在现有 `模型/effort/耗时` 后追加 `ctx=<estimated_prompt_tokens>/<model_context_capacity> | tok≈<estimated_total_tokens>`。
- 只显示数值，不打印上下文正文、source manifest 或其他调试明细。
- `AgentJobResult` 现在携带 prompt/output 字符数与估算 token；`agent_runs.jsonl` trace 新增 `estimated_output_tokens`。
- 真实 provider usage、token 聚合统计脚本和更多 Agent 路径接入已列入 `docs/IMPLEMENTATION_PLAN.md` 后续待办。

验证：

```bash
.venv/bin/python -m pytest tests/test_progress.py tests/test_agent_parallel.py tests/test_agent_metrics.py tests/test_outline_collaboration.py
# 36 passed
.venv/bin/python -m pytest
# 201 passed
```


## 44. 本轮修复：大纲角色 Agent 上下文区分

- 修复大纲同阶段三个 role Agent 只靠 `ROLE` 行区分、进度里上下文/token 容易显示相同的问题。
- `build_outline_stage_role_prompt()` 现在注入“角色专属关注点”，同一阶段共享阶段记忆；当前精简后的故事概念阶段仅保留故事概念 Agent，其他多角色阶段仍会收到不同任务上下文。
- 新增回归测试，确认角色专属关注点会让指定角色 prompt 与通用 fallback prompt 区分开。

验证：

```bash
.venv/bin/python -m pytest tests/test_outline_collaboration.py tests/test_progress.py
# 33 passed
.venv/bin/python -m pytest
# 202 passed
```

## 45. 本轮修复：Direction 阶段发散过度

- 修复 direction 阶段输出被包装成 `# 方向定位` + `## 方向控制稿` + `## 方向定位稿` 的嵌套标题问题；现在 direction 阶段 Markdown 只保留 `## 方向定位稿`。
- Direction role prompt 和 synthesizer prompt 明确只产出宏观方向原则，禁止提前展开世界观规则、组织流程、制度条款、申请表、审批、考评、备案、绩效、具体人物关系细则、具体剧情桥段、章节安排和专有名词清单。
- 新增 `sanitize_direction_stage_output()`，保存 direction synthesis 前清理重复标题，并将常见过细机制词替换为抽象原则。
- Mock direction 输出改为 8 条短方向原则，覆盖类型定位、主角行动原则、核心爽点、核心冲突、情绪基调、主题边界、反转原则和禁区。
- 新增回归测试覆盖 direction 标题唯一性、制度化词过滤，以及宏观方向信息保留。

验证：

```bash
.venv/bin/python -m pytest tests/test_outline_collaboration.py
# 33 passed
.venv/bin/python -m pytest
# 203 passed
```

## 46. 本轮更新：Outline 共享 Prompt 边界整改

- 按 `00_INDEX.md` 推荐顺序执行 `08_outline_stage_shared_role_prompt.md` 与 `09_outline_stage_shared_synthesizer_prompt.md`。
- 新增 stage-specific boundary，所有大纲阶段 role prompt 都会注入允许/禁止内容，并明确不越权生成其他阶段产物或无依据 canon。
- Role prompt 输出预算从每类最多 3 条/总 600 字收紧为每类最多 2 条/总 500 字。
- Synthesizer prompt 改为按 stage 输出不同结构：故事概念稿、世界观设定稿、人物关系稿、故事流程稿、分卷大纲稿、章节大纲稿、审稿锁定稿等。
- 非 direction 阶段 formatter 现在避免重复包 `## Director 汇总`，如果 synthesis 已有 Markdown 标题则直接使用。
- 新增回归测试覆盖所有 stage boundary、不同 synthesizer 结构和非 direction 标题去重。

验证：

```bash
.venv/bin/python -m pytest tests/test_outline_collaboration.py
# 36 passed
.venv/bin/python -m pytest
# 206 passed
```

## 47. 本轮更新：Concept 阶段专项边界整改

- 完整读取并执行 `01_outline_stage_concept.md`。
- 故事概念阶段 prompt 现在只允许故事钩子、一句话概念、主角欲望、核心冲突、主要悬念、叙事承诺、主题问题、反转原则和待后续展开。
- 明确禁止 concept 阶段提前生成世界规则清单、组织流程、人物关系细则、人物亲密机制、章节列表、第1章、第一卷、分卷结构、申请表、审批、备案、绩效和 KPI。
- Synthesizer 固定输出 `## 故事概念稿` 下的 5-7 条短句，每条不超过 90 中文字符。
- 新增回归测试覆盖 concept 核心信息保留和过细内容禁区。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 1 passed
.venv/bin/python -m pytest tests/test_outline_collaboration.py
# 37 passed
.venv/bin/python -m pytest
# 207 passed
```

## 48. 本轮更新：Worldbuilding 阶段专项边界整改

- 完整读取并执行 `02_outline_stage_worldbuilding.md`。
- 世界观阶段 prompt 现在只允许世界运行原则、力量/技术边界、阵营结构、资源与代价、冲突来源和可渐进揭露的秘密。
- 默认禁止申请表、申请、审批、备案、考评、绩效、KPI、表格化制度、无关规则清单和未被用户要求的猎奇机制。
- 当用户原始输入或锁定产物明确包含受控词时，prompt 会允许保留该词，但要求改写为服务主线冲突的世界运行原则。
- Synthesizer 结构改为 `世界运行原则 / 关键边界 / 冲突资源 / 代价红线 / 仍需确认的问题`，并限制 6-8 条原则、每条不超过 100 中文字符、最多 3 个冲突资源点。
- 新增回归测试覆盖默认行政化机制禁区和用户明确指定“绩效”时的保留边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 1 passed
.venv/bin/python -m pytest tests/test_outline_collaboration.py
# 39 passed
.venv/bin/python -m pytest
# 209 passed
```

## 49. 本轮更新：Characters 阶段专项边界整改

- 完整读取并执行 `03_outline_stage_characters.md`。
- 人物关系阶段 prompt 现在只允许主角缺陷与欲望、关键人物目标、动机、关系张力、阵营位置、阵营冲突、背叛/信任风险、成长矛盾和人物弧光。
- 默认禁止亲密行为、双修审批、道侣绩效、道侣流程、暧昧规则、福利场景、擦边机制、恋爱系统表格和无主线功能的人设细节。
- 用户原始输入或锁定产物明确包含相关词时，prompt 只允许把它们改写为目标、动机、阵营位置或主线冲突功能。
- Synthesizer 固定输出 3-5 个主要人物，每人使用 `人物 / 目标 / 与主线冲突的功能 / 关系张力 / 弧光风险`，每字段不超过 60 中文字符。
- 新增回归测试覆盖人物冲突功能要求和亲密/福利机制禁区。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 1 passed
.venv/bin/python -m pytest tests/test_outline_collaboration.py
# 41 passed
.venv/bin/python -m pytest
# 211 passed
```

## 50. 本轮更新：Story Flow 阶段专项边界整改

- 完整读取并执行 `04_outline_stage_story_flow.md`。
- 故事流程阶段 prompt 明确“流程”只指叙事流程，不是组织流程、制度流程或行政流程。
- 允许输出主线阶段、阶段目标、关键转折、信息释放节奏、伏笔布置与回收方向、失败代价和高潮方向。
- 禁止完整章节正文、细场景动作、未确立新规则、新增世界观 canon、突然新增人物关系、行政流程、办理、审批、备案、绩效和申请表。
- Synthesizer 固定为三幕或四段结构，每段最多 4 个要点，每点不超过 90 中文字符，并要求阶段目标、转折、伏笔回收和代价。
- 新增回归测试覆盖 story_flow 的叙事流程边界和禁区。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 1 passed
.venv/bin/python -m pytest tests/test_outline_collaboration.py
# 42 passed
.venv/bin/python -m pytest
# 212 passed
```

## 51. 本轮更新：Volume Outline 阶段专项边界整改

- 完整读取并执行 `05_outline_stage_volume_outline.md`。
- 分卷大纲阶段 prompt 现在只允许卷名、卷目标、卷内主要矛盾、卷级高潮事件、失败/胜利代价、主角能力或认知变化和卷间钩子。
- 明确禁止逐章细纲、第1章、第2章、章节列表、场景列表、细场景动作、正文片段、新世界观规则、新人物系统和过细制度机制。
- Synthesizer 固定规划 3-5 卷，每卷使用 `卷名 / 卷目标 / 卷内主要矛盾 / 高潮事件 / 失败或胜利代价 / 卷间钩子`，每字段不超过 80 中文字符。
- 新增回归测试覆盖分卷只做卷级结构，并要求每卷包含目标、高潮、代价和卷间钩子。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 1 passed
.venv/bin/python -m pytest tests/test_outline_collaboration.py
# 43 passed
.venv/bin/python -m pytest
# 213 passed
```

## 52. 本轮更新：Chapter Outline 阶段专项边界整改

- 完整读取并执行 `06_outline_stage_chapter_outline.md`。
- 章节大纲阶段 prompt 现在只允许章节编号、章节目标、主要冲突、信息增量、人物状态变化、结尾钩子和连续性提醒。
- 明确禁止正式正文、对白、中文引号对白、完整场景卡、细场景调度、未确立新规则、新人物关系、额外世界观机制、审批、制度和亲密机制。
- Synthesizer 固定首批输出 8-12 章或沿用已有计划，每章使用 `章节编号 / 章节目标 / 主要冲突 / 信息增量 / 人物状态变化 / 结尾钩子 / 连续性提醒`，每字段不超过 60 中文字符。
- 新增回归测试覆盖每章目标、冲突、信息增量、钩子要求，以及正文/对白/场景卡禁区。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 1 passed
.venv/bin/python -m pytest tests/test_outline_collaboration.py
# 44 passed
.venv/bin/python -m pytest
# 214 passed
```

## 53. 本轮更新：Review Lock 阶段专项边界整改

- 完整读取并执行 `07_outline_stage_review_lock.md`。
- 审稿锁定阶段 prompt 现在只允许一致性问题、阶段承接检查、锁定约束、待确认问题、风险标注、进入章节卡前的准备条件和锁定建议。
- 明确禁止新增世界规则、新增 canon、重写人物关系、重写剧情流程、生成章节卡、生成正文和二次创作。
- Synthesizer 改为 STATUS-first，包含 `STATUS: pass|revise|stop`，问题最多 8 条，每条不超过 90 中文字符。
- 新增回归测试覆盖 STATUS 可解析结论和不新增 canon/章节卡/正文禁区。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 1 passed
.venv/bin/python -m pytest tests/test_outline_collaboration.py
# 45 passed
.venv/bin/python -m pytest
# 215 passed
```

## 54. 本轮更新：Direction Proposer Prompt 整改

- 完整读取并执行 `10_direction_proposer.md`。
- `direction_proposer.md` 现在明确三个方向只是候选路线，未确认前不是小说圣经、稳定 canon 或锁定设定。
- Prompt 要求不违反 `locked_constraints`，且未选方案不会进入稳定设定。
- 默认禁止具体世界规则、组织流程、亲密机制、章节剧情、审批、备案、绩效、申请表和 KPI。
- 输出预算固定为 3 个方向、每方向 6 个字段、每字段不超过 60 中文字符，建议选择不超过 120 中文字符。
- 新增回归测试覆盖候选方向语义和过细机制禁区。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 2 passed
.venv/bin/python -m pytest tests/test_graph_writer.py tests/test_outline_collaboration.py
# 69 passed
.venv/bin/python -m pytest
# 216 passed
```

## 55. 本轮更新：World Builder Prompt 整改

- 完整读取并执行 `11_world_builder.md`。
- `world_builder.md` 现在把世界规则限制为 3-5 条与主线冲突直接相关的运行原则，每条不超过 100 中文字符。
- 每条原则必须包含“如何制造冲突/代价”和适用边界。
- 具体机制必须来自用户原话、锁定大纲或已有小说圣经；信息不足时标注待确认，不补造 canon。
- 默认禁止行政流程、审批、备案、绩效、申请表、KPI 和考评等细则。
- 可持续写作素材最多 5 个，且必须说明剧情功能。
- 新增回归测试覆盖规则数量、冲突/代价字段和清单式设定禁区。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 3 passed
.venv/bin/python -m pytest tests/test_graph_writer.py tests/test_outline_collaboration.py
# 69 passed
.venv/bin/python -m pytest
# 217 passed
```

## 56. 本轮更新：Outline Planner Prompt 整改

- 完整读取并执行 `12_outline_planner.md`。
- `outline_planner.md` 现在明确只整合已有创意、世界观和 `locked_constraints`，不得为填满三幕/四段结构补造 canon。
- 缺少依据时必须写“待确认”，不新增世界观大规则、人物关系机制、组织流程、章节正文或场景动作。
- 默认禁止审批、备案、绩效、申请表、KPI 和考评等未输入机制。
- 输出预算为整体不超过 1800 中文字符、每幕/每段最多 4 条、伏笔最多 5 个。
- 新增回归测试覆盖待确认字段、预算和正文/机制禁区。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 4 passed
.venv/bin/python -m pytest tests/test_graph_writer.py tests/test_outline_collaboration.py
# 69 passed
.venv/bin/python -m pytest
# 218 passed
```

## 57. 本轮更新：Outline Editor Prompt 整改

- 完整读取并执行 `13_outline_editor.md`。
- `outline_editor.md` 现在明确只审稿，不重写大纲，不新增 canon。
- 保持 `STATUS: pass|revise|stop` 和 `QUALITY_SCORE: 0-100` 可解析。
- 主要问题和修改建议均限制最多 5 条、每条不超过 80 中文字符。
- 修改建议必须指向已有大纲位置、锁定约束冲突或明确缺口。
- 新增回归测试覆盖状态字段、预算和不新增设定边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 5 passed
.venv/bin/python -m pytest tests/test_graph_writer.py tests/test_outline_collaboration.py
# 69 passed
.venv/bin/python -m pytest
# 219 passed
```

## 58. 本轮更新：Outline Reviser Prompt 整改

- 完整读取并执行 `14_outline_reviser.md`。
- `outline_reviser.md` 现在默认做最小必要修订，不重写完整大纲。
- 修订只回应 `revision_instruction`、用户修订意见和编辑意见覆盖的区块。
- `locked_constraints` 必须原样保留；未被修订指令覆盖的内容保持原意与顺序。
- 禁止新增无关 canon、无依据大改、重写锁定约束和扩写正文。
- 输出预算为变更项最多 8 条、每条不超过 100 中文字符、待确认最多 3 条。
- 新增回归测试覆盖最小修订、修订摘要和锁定约束边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 6 passed
.venv/bin/python -m pytest tests/test_graph_writer.py tests/test_outline_collaboration.py
# 69 passed
.venv/bin/python -m pytest
# 220 passed
```

## 59. 本轮更新：Chapter Planner Prompt 整改

- 完整读取并执行 `15_chapter_planner.md`。
- `chapter_planner.md` 现在区分当前章节模式和全书章节拆分模式。
- 当前章节模式只输出当前章节写作输入，不建议全书章节数量，不重写全书章节结构。
- 禁止新增全局世界观 canon、人物关系机制、场景卡正文、正式正文和无关章节扩写。
- 当前章细纲限制不超过 900 中文字符，场景顺序最多 5 个。
- 新增回归测试覆盖模式区分和当前章规划边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 7 passed
.venv/bin/python -m pytest tests/test_graph_chapter_plan.py tests/test_graph_scene.py
# 7 passed
.venv/bin/python -m pytest
# 221 passed
```

## 60. 本轮更新：Chapter Goal Agent Prompt 整改

- 完整读取并执行 `16_chapter_goal_agent.md`。
- `chapter_goal_agent.md` 现在要求所有目标和信息增量来自章节大纲、章节卡、小说圣经、锁定约束或已有 canon。
- 禁止为了补齐目标新增世界观规则、人物关系、反派、组织或其他 canon。
- JSON schema 增加 `evidence` 和 `source_hint`，每条 goal 必须有来源依据。
- 依据不足时写入 `open_questions`，不自行补造。
- 新增回归测试覆盖 JSON schema、依据字段和 no-new-canon 边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 8 passed
.venv/bin/python -m pytest tests/test_graph_chapter_plan.py tests/test_graph_scene.py
# 7 passed
.venv/bin/python -m pytest
# 222 passed
```

## 61. 本轮更新：Chapter Conflict Agent Prompt 整改

- 完整读取并执行 `17_chapter_conflict_agent.md`。
- `chapter_conflict_agent.md` 现在只允许识别、提炼和排序已有冲突。
- 禁止新增反派、新组织、新世界规则、新长期代价机制、审批/制度机制或无依据设定。
- 每条 conflict 必须包含 `source_hint`，可追溯到章节大纲、章节卡、小说圣经、锁定约束或已有 canon。
- 冲突不足时只能输出 `minimal_fix_suggestions` 或 `open_questions`。
- 新增回归测试覆盖 JSON schema、source_hint 和 no-new-conflict-source 边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 9 passed
.venv/bin/python -m pytest tests/test_graph_chapter_plan.py tests/test_graph_scene.py
# 7 passed
.venv/bin/python -m pytest
# 223 passed
```

## 62. 本轮更新：Chapter Hook Agent Prompt 整改

- 完整读取并执行 `18_chapter_hook_agent.md`。
- `chapter_hook_agent.md` 现在要求钩子必须来自已有伏笔、当前章节目标或已规划信息差。
- 禁止新增全局真相、未规划大反转、新世界规则、新角色关系或正文段落。
- 每个 hook 必须包含 `source_hint` 和 `reveal_level`，其中 `reveal_level` 只能是 `hint|partial|none`。
- 需要保留的信息写入 `do_not_reveal`，避免提前泄露后续真相。
- 新增回归测试覆盖 reveal_level、source_hint 和 no-spoiler/no-new-canon 边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 10 passed
.venv/bin/python -m pytest tests/test_graph_chapter_plan.py tests/test_graph_scene.py
# 7 passed
.venv/bin/python -m pytest
# 224 passed
```

## 63. 本轮更新：Chapter Card Synthesizer Prompt 整改

- 完整读取并执行 `19_chapter_card_synthesizer.md`。
- `chapter_card_synthesizer.md` 现在只整合当前章节必需信息，不扩写全书设定。
- 参考资料、role reports、检索内容或临时建议不能直接写成 canon。
- 未确认参考事实或来源不明内容必须标记为“待确认”。
- 场景列表限制 2-5 个，只给功能，不写正文、对白或细场景动作。
- 输出预算为每节不超过 120 中文字符、整体不超过 1200 中文字符。
- 新增回归测试覆盖待确认、场景数量和 no-new-canon 边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 11 passed
.venv/bin/python -m pytest tests/test_graph_chapter_plan.py tests/test_graph_scene.py
# 7 passed
.venv/bin/python -m pytest
# 225 passed
```

## 64. 本轮更新：Scene Breakdown Agent Prompt 整改

- 完整读取并执行 `20_scene_breakdown_agent.md`。
- `scene_breakdown_agent.md` 现在明确只能拆分 Chapter Card，不能改变章节目标、关键冲突、结尾钩子或 canon。
- 禁止新增全局世界观、新世界规则、长期人物关系或章节目标之外的副线。
- 输出改为 JSON，`scenes` 必须 2-5 个，每个场景包含 `purpose/info_delta/turn/entry_state/exit_state`。
- 禁止正文、对白和细场景动作；信息不足进入 `open_questions`。
- 新增回归测试覆盖场景数量、JSON 字段和 no-new-canon 边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 12 passed
.venv/bin/python -m pytest tests/test_graph_scene.py tests/test_graph_chapter_plan.py
# 7 passed
.venv/bin/python -m pytest
# 226 passed
```

## 65. 本轮更新：Scene Conflict Check Agent Prompt 整改

- 完整读取并执行 `21_scene_conflict_check_agent.md`。
- `scene_conflict_check_agent.md` 现在只输出 JSON，不输出 Markdown。
- 只检查已有场景拆分中的冲突重复、动机断裂、信息泄露、连续性违背或 Chapter Card 不一致。
- 禁止新增场景、新人物关系、新世界规则、新 canon、大幅重写或正文。
- `issues` 最多 5 个，每个 `minimal_fix` 不超过 80 中文字符；必须补信息时写入 `needs_confirmation`。
- 新增回归测试覆盖 JSON 输出、最小修正和 no-new-canon 边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 13 passed
.venv/bin/python -m pytest tests/test_graph_scene.py tests/test_graph_chapter_plan.py
# 7 passed
.venv/bin/python -m pytest
# 227 passed
```

## 66. 本轮更新：Scene Synthesizer Prompt 整改

- 完整读取并执行 `22_scene_synthesizer.md`。
- `scene_synthesizer.md` 现在只输出 JSON，`scenes` 必须 2-5 个。
- 场景字段必须从章节卡、场景拆分报告、冲突检查报告和已有 canon 继承。
- 必须补充的小细节标记 `detail_scope: scene-local`，且不得写入小说圣经。
- 禁止新增全局地点、组织、规则、未规划人物、无依据感情机制、正文和对白。
- 每场固定 9 个核心字段，每字段不超过 60 中文字符，并带 `source_hint`。
- 新增回归测试覆盖字段继承、scene-local 标记和 no-new-canon 边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 14 passed
.venv/bin/python -m pytest tests/test_graph_scene.py tests/test_graph_chapter_plan.py
# 7 passed
.venv/bin/python -m pytest
# 228 passed
```

## 67. 本轮更新：Chapter Writer Prompt 整改

- 完整读取并执行 `23_chapter_writer.md`。
- `chapter_writer.md` 现在要求严格按章节卡和场景卡顺序写正文。
- 禁止新增 canon、全局设定、世界观规则、未规划角色/组织、人物关系机制、改变场景顺序或提前泄露后续真相。
- 允许新增仅限场景级感官细节、动作细节、环境压力和过渡句，且不写入小说圣经。
- 输出只包含 Markdown 正文，不输出分析、说明、摘要、计划或自检。
- 新增回归测试覆盖 scene-card guard、no-new-canon 和正文-only 边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 15 passed
.venv/bin/python -m pytest tests/test_graph_drafting.py tests/test_graph_writer.py
# 27 passed
.venv/bin/python -m pytest
# 229 passed
```

## 68. 本轮更新：Atmosphere Enhancer Prompt 整改

- 完整读取并执行 `24_atmosphere_enhancer.md`。
- `atmosphere_enhancer.md` 现在只允许增强环境细节、感官描写、情绪递进和危险感表达。
- 禁止新增事件、规则、人物、组织、怪物、剧情转折或新 canon。
- 禁止改变场景顺序、人物行动结果、信息释放顺序或结尾钩子。
- 事实缺口不补造；输出完整稿时修改范围仍只限描写层。
- 新增回归测试覆盖 no-new-facts guard 和描写层边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 16 passed
.venv/bin/python -m pytest tests/test_graph_drafting.py tests/test_graph_writer.py
# 27 passed
.venv/bin/python -m pytest
# 230 passed
```

## 69. 本轮更新：Dialogue Enhancer Prompt 整改

- 完整读取并执行 `25_dialogue_enhancer.md`。
- `dialogue_enhancer.md` 现在要求对白只能表达已知事实、当前场景情绪和已建立的人物动机。
- 禁止通过对白新增 canon、秘密、世界规则、后续伏笔或未规划信息。
- 禁止提前揭示后续真相、改变人物关系状态、添加新承诺、新誓言、新设定或新动机。
- 新增对白不得引入新的事实信息。
- 新增回归测试覆盖对白 no-new-canon 和 no-spoiler 边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 17 passed
.venv/bin/python -m pytest tests/test_graph_drafting.py tests/test_graph_writer.py
# 27 passed
.venv/bin/python -m pytest
# 231 passed
```

## 70. 本轮更新：Hook Enhancer Prompt 整改

- 完整读取并执行 `26_hook_enhancer.md`。
- `hook_enhancer.md` 现在要求所有钩子必须来自章节卡、场景卡、已有伏笔或当前草稿中已存在的信息差。
- 禁止新增全局真相、大反转、新敌人、新组织、新世界规则或无依据异常。
- 禁止改变结尾事件、结尾事实、人物状态或场景顺序。
- 不得泄露后续真相；保留信息只做暗示或留白。
- 新增回归测试覆盖 source-bound guard 和 no-new-twist/no-spoiler 边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 18 passed
.venv/bin/python -m pytest tests/test_graph_drafting.py tests/test_graph_writer.py
# 27 passed
.venv/bin/python -m pytest
# 232 passed
```

## 71. 本轮更新：Style Normalizer Prompt 整改

- 完整读取并执行 `27_style_normalizer.md`。
- `style_normalizer.md` 现在增加“事实冻结规则”。
- 只允许语言层调整：视角一致性、节奏、语气、格式和冗余说明压缩。
- 要求内容事实差异为零。
- 禁止改写剧情事实、信息释放、人物状态、关系状态、伏笔、场景顺序或结尾钩子。
- 禁止增删情节、增删世界观、添加新 canon 或删除关键信息。
- 新增回归测试覆盖事实冻结和钩子/人物状态不变边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 19 passed
.venv/bin/python -m pytest tests/test_graph_drafting.py tests/test_graph_writer.py
# 27 passed
.venv/bin/python -m pytest
# 233 passed
```

## 72. 本轮更新：Legacy Editor Prompt 整改

- 完整读取并执行 `28_editor.md`。
- `editor.md` 保留 `STATUS: pass|revise|stop` 和 `QUALITY_SCORE: 0-100` 可解析结构。
- 明确只审稿，不重写正文，不新增 canon。
- 修改建议必须能映射到现有章节卡、场景卡或草稿位置。
- 主要问题最多 6 条，修改建议 3-6 条，每条不超过 90 中文字符。
- 禁止发明新设定、新角色、新世界规则或新剧情。
- 新增回归测试覆盖状态字段、预算和可路由建议边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 20 passed
.venv/bin/python -m pytest tests/test_graph_review.py tests/test_graph_drafting.py tests/test_graph_writer.py
# 32 passed
.venv/bin/python -m pytest
# 234 passed
```

## 73. 本轮更新：Continuity Editor Prompt 整改

- 完整读取并执行 `29_continuity_editor.md`。
- `continuity_editor.md` 现在明确连续性修复优先删除、澄清已有信息、调整表述或改序。
- 禁止通过新增设定补洞，禁止新增世界规则、新人物、新伏笔或新章节事件。
- 新增设定需求只能进入 `needs_confirmation`，不能进入 `rewrite_tasks`。
- 保持 JSON 输出和预算：`top_issues<=5`、`rewrite_tasks<=5`、`keep<=3`、每字符串不超过 80 中文字符。
- 新增回归测试覆盖最小修复和 no-new-canon 补洞边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 21 passed
.venv/bin/python -m pytest tests/test_graph_review.py tests/test_graph_revision.py tests/test_output_contracts.py
# 9 passed
.venv/bin/python -m pytest
# 235 passed
```

## 74. 本轮更新：Structure Editor Prompt 整改

- 完整读取并执行 `30_structure_editor.md`。
- `structure_editor.md` 现在要求建议必须指向已有场景、章节卡、场景卡或草稿位置。
- 修复优先重排、压缩、强化已有场景目标、冲突递进、转折、信息释放和结尾钩子。
- 禁止新增全局反转、新场景群、新人物、新组织、新世界规则或新 canon。
- 缺失信息写入 `needs_confirmation`，不建议大幅重写整章。
- 新增回归测试覆盖现有场景定位和 no-new-canon 边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 22 passed
.venv/bin/python -m pytest tests/test_graph_review.py tests/test_graph_revision.py tests/test_output_contracts.py
# 9 passed
.venv/bin/python -m pytest
# 236 passed
```

## 75. 本轮更新：Character Arc Editor Prompt 整改

- 完整读取并执行 `31_character_arc_editor.md`。
- `character_arc_editor.md` 现在只修当前章节已有选择、代价、情绪转折和人物状态连续性。
- 禁止通过新增身世、感情机制、恋爱机制、长期承诺、亲密规则、新阵营关系或新关系 canon 来解释动机。
- 修复建议必须指向已有场景、章节卡、场景卡或草稿位置。
- 保持 JSON 输出和预算。
- 新增回归测试覆盖当前章人物选择修复和 no-new-relationship-canon 边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 23 passed
.venv/bin/python -m pytest tests/test_graph_review.py tests/test_graph_revision.py tests/test_output_contracts.py
# 9 passed
.venv/bin/python -m pytest
# 237 passed
```


## 76. 本轮更新：Style Editor Prompt 整改

- 完整读取并执行 `32_style_editor.md`。
- `style_editor.md` 现在明确只诊断语言和叙述问题。
- 修复建议只能是删减说明、改写语气、调整节奏、统一视角或压缩解释比例。
- 禁止新增设定、改剧情、改类型定位、重写正文或输出长篇示范段落。
- 禁止改变事实、信息释放、人物状态、伏笔或结尾钩子。
- 风格目标不明确时写入 `needs_confirmation`，不得重设类型方向。
- 新增回归测试覆盖语言层修复和 no-fact/type-change 边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 24 passed
.venv/bin/python -m pytest tests/test_graph_review.py tests/test_graph_revision.py tests/test_output_contracts.py
# 9 passed
.venv/bin/python -m pytest
# 238 passed
```


## 77. 本轮更新：Simulated Reader Prompt 整改

- 完整读取并执行 `33_simulated_reader.md`。
- `simulated_reader.md` 现在只能表达阅读体验缺口和困惑。
- 允许反馈吸引力、困惑点、拖沓处、最想继续看的既有线索和保留项。
- `rewrite_tasks` 必须转化为澄清已有内容、强化已有线索、压缩拖沓段落或保留有效吸引点。
- 禁止新增剧情走向、新人物关系、新世界机制、CP 福利或长评式扩写。
- 新增回归测试覆盖模拟读者反馈不新增剧情和 rewrite_tasks 只处理已有内容。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 25 passed
.venv/bin/python -m pytest tests/test_graph_review.py tests/test_graph_revision.py tests/test_output_contracts.py
# 9 passed
.venv/bin/python -m pytest
# 239 passed
```


## 78. 本轮更新：Review Synthesizer Prompt 整改

- 完整读取并执行 `34_review_synthesizer.md`。
- `review_synthesizer.md` 现在只汇总上游 editor JSON 和 simulated_reader JSON 中已提出的问题。
- 禁止新增上游未提出的问题、风险、新设定任务或剧情方案。
- 禁止扩写长任务、重写正文，合并时不得改变原意。
- `rewrite_tasks` 必须去重，并按阻塞程度和修复优先级排序。
- 同步收紧 `graph_review.py` prompt contract 与 `normalize_review_synthesis` 运行时预算：blocking_issues<=3、issues<=6、rewrite_tasks<=8、每项<=90 中文字符。
- 新增回归测试覆盖来源约束、预算和数组/字数归一化。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 26 passed
.venv/bin/python -m pytest tests/test_graph_review.py tests/test_graph_revision.py tests/test_output_contracts.py
# 10 passed
.venv/bin/python -m pytest
# 241 passed
```


## 79. 本轮更新：Revision Planner Prompt 整改

- 完整读取并执行 `35_revision_planner.md`。
- `revision_planner.md` 现在输出严格 JSON，顶层结构为 `revision_plan_v1`。
- 每个 task 必须来源于 `review_v1.json` 的 blocking_issues、issues 或 rewrite_tasks，并包含 `source`。
- 禁止新增剧情、世界观、人物关系，或未在 review 中出现的大改。
- 只输出定向修订目标、涉及场景、保留内容、禁止触碰约束和待确认项。
- mock revision plan 同步改为 JSON-first，并保持修订流程可识别的 `revision_plan_v1` 标记。
- 新增回归测试覆盖 JSON 可解析、任务数量和 review 溯源。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 27 passed
.venv/bin/python -m pytest tests/test_graph_review.py tests/test_graph_revision.py tests/test_output_contracts.py
# 10 passed
.venv/bin/python -m pytest
# 242 passed
```


## 80. 本轮更新：Targeted Reviser Prompt 整改

- 完整读取并执行 `36_targeted_reviser.md`。
- `targeted_reviser.md` 现在增加“最小编辑规则”。
- 只改 `revision_plan_v1.tasks` 指定的问题区域。
- 未涉及段落必须保持原意、叙事顺序、信息释放和人物状态。
- 允许输出完整 `draft_v2` Markdown 正文，但修改范围必须受 revision_plan 限制。
- 禁止全章大改、重排无关段落、改动未列入任务的段落或新增 canon。
- 新增回归测试覆盖 minimal edit guard 和 no-unrelated-rewrite 边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 28 passed
.venv/bin/python -m pytest tests/test_graph_review.py tests/test_graph_revision.py tests/test_output_contracts.py
# 10 passed
.venv/bin/python -m pytest
# 243 passed
```


## 81. 本轮更新：Revision Self Check Prompt 整改

- 完整读取并执行 `37_revision_self_check.md`。
- `revision_self_check.md` 现在输出严格 JSON。
- 输出字段限定为 `tasks_status`、`new_risks`、`decision`。
- 每个 revision_plan_v1 task 对应一个完成状态；新风险最多 5 条且只标记不扩写方案。
- 禁止提出新增剧情建议、重写正文、新设定、新世界观或 revision_plan_v1 外的新修订任务。
- mock revision self check 同步改为可解析 JSON。
- 新增回归测试覆盖 JSON 可解析、自检状态和 no-new-creation 边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 29 passed
.venv/bin/python -m pytest tests/test_graph_review.py tests/test_graph_revision.py tests/test_output_contracts.py
# 10 passed
.venv/bin/python -m pytest
# 244 passed
```


## 82. 本轮更新：Version Comparator Prompt 整改

- 完整读取并执行 `38_version_comparator.md`。
- `version_comparator.md` 现在只比较旧版和新版差异，不创作第三版大纲。
- 采用建议必须基于用户偏好、locked_constraints 和差异风险。
- 禁止新增第三版大纲、新设定、详细改写方案或正文。
- 输出预算限制为每节最多 3 条、每条不超过 80 中文字符。
- mock version comparison 同步改为短条目形式。
- 新增回归测试覆盖 no-third-version 和预算边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 30 passed
.venv/bin/python -m pytest tests/test_graph_review.py tests/test_graph_revision.py tests/test_output_contracts.py
# 10 passed
.venv/bin/python -m pytest
# 245 passed
```


## 83. 本轮更新：Bible Conflict Checker Prompt 整改

- 完整读取并执行 `39_bible_conflict_checker.md`。
- `bible_conflict_checker.md` 现在保持严格 JSON，并要求 conflict 包含 `type`、`name`、`current`、`incoming`、`severity`、`blocking`。
- 禁止 Markdown、长解释、新设定和自动合并方案。
- 输出预算限制为 conflicts<=10、字符串字段<=120 中文字符。
- `detect_bible_conflicts` 同步输出完整字段，并限制数量和字符串长度。
- 新增回归测试覆盖空冲突、字段完整、severity/blocking 和 no-auto-merge 边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 31 passed
.venv/bin/python -m pytest tests/test_graph_bible.py tests/test_finalize_chapter.py tests/test_director_service.py tests/test_research_workflow.py tests/test_search_backend.py tests/test_bible.py
# 72 passed
.venv/bin/python -m pytest
# 247 passed
```


## 84. 本轮更新：Bible Update Extractor Prompt 整改

- 完整读取并执行 `40_bible_update_extractor.md`。
- `bible_update_extractor.md` 现在只提取已经确认的 stable canon。
- 禁止把临时讨论、候选方向、未确认设定、review 建议或模型自行补全写入正式字段。
- 候选方案、临时建议、未确认问题和依据不足内容必须进入 `open_questions`。
- 正式数组项必须包含 `source_hint` 或 `evidence`。
- 输出预算限制为每类最多 8 项、open_questions 最多 8 条、字符串<=120 中文字符。
- mock bible update extractor 同步为代表性正式项增加 `source_hint`。
- 新增回归测试覆盖 stable canon、open_questions 和 source_hint 边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 32 passed
.venv/bin/python -m pytest tests/test_graph_bible.py tests/test_finalize_chapter.py tests/test_director_service.py tests/test_research_workflow.py tests/test_search_backend.py tests/test_bible.py
# 72 passed
.venv/bin/python -m pytest
# 248 passed
```


## 85. 本轮更新：Bible Update Synthesizer Prompt 整改

- 完整读取并执行 `41_bible_update_synthesizer.md`。
- `bible_update_synthesizer.md` 现在使用“已写入 / 未写入 / 待确认”三分结构。
- “已写入”只能包含已确认并实际写入小说圣经的稳定设定。
- conflict、blocking conflict、open_questions、候选方案和未确认内容必须进入“待确认”。
- 被过滤、因冲突阻塞或依据不足的内容进入“未写入”。
- 禁止补写新设定、把冲突当成已确认或输出长篇解释。
- 输出预算限制为每节最多 5 条、每条不超过 90 中文字符。
- 新增回归测试覆盖三分结构和 no-conflict-as-canon 边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 33 passed
.venv/bin/python -m pytest tests/test_graph_bible.py tests/test_finalize_chapter.py tests/test_director_service.py tests/test_research_workflow.py tests/test_search_backend.py tests/test_bible.py
# 72 passed
.venv/bin/python -m pytest
# 249 passed
```


## 86. 本轮更新：Final Bible Update Extractor Prompt 整改

- 完整读取并执行 `42_final_bible_update_extractor.md`。
- `final_bible_update_extractor.md` 现在只提取定稿章节中明确发生的事实、状态变化和显性线索。
- 禁止从修辞、比喻、氛围、情绪描写或象征物推断世界规则。
- 禁止输出 world_rules、project 或 concept，避免从单章定稿隐含推断全局 canon。
- 禁止覆盖旧设定为空、加入未发生事件、未来预测或读者评价。
- 结构化条目必须包含 `source_hint`；chapter_summaries 限制为每章 80-180 中文字符。
- mock final bible updates 与 fallback_bible_updates 同步增加 `source_hint`。
- 新增回归测试覆盖 explicit-facts-only、no-world-rule-inference 和 source_hint 边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 34 passed
.venv/bin/python -m pytest tests/test_graph_bible.py tests/test_finalize_chapter.py tests/test_director_service.py tests/test_research_workflow.py tests/test_search_backend.py tests/test_bible.py
# 72 passed
.venv/bin/python -m pytest
# 250 passed
```


## 87. 本轮更新：Chapter Summarizer Prompt 整改

- 完整读取并执行 `43_chapter_summarizer.md`。
- `chapter_summarizer.md` 现在只记录本章已发生事实、人物状态变化、关键线索和章末钩子。
- 禁止加入未在正文出现的新设定、推断未明说动机或把读者猜测写成事实。
- 禁止预测后续剧情，禁止“可能”“似乎暗示后续会”等预测表达。
- 禁止输出读者评价、优缺点分析或写作建议。
- `normalize_summary` 和 `fallback_chapter_summary` 上限收紧为 180 字。
- 新增回归测试覆盖 facts-only、no-prediction 和长度上限。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 35 passed
.venv/bin/python -m pytest tests/test_graph_bible.py tests/test_finalize_chapter.py tests/test_director_service.py tests/test_research_workflow.py tests/test_search_backend.py tests/test_bible.py
# 72 passed
.venv/bin/python -m pytest
# 251 passed
```


## 88. 本轮更新：Director Prompt 整改

- 完整读取并执行 `44_director.md`。
- `director.md` 现在增加 Director 硬约束，只做路由、澄清、提炼用户约束和安排下一步。
- 禁止生成阶段产物、长篇大纲、世界观正文、章节正文或替子 Agent 创作。
- 禁止在一次用户请求中静默推进多个大纲阶段。
- 禁止把模型推测、候选方案或未确认信息写入 `locked_constraints`。
- `task_args` 限定为用户原意、明确章节号、明确阶段名和必要执行参数。
- `DirectorDecision.from_dict` 同步执行 user_message<=120 和 next_steps<=3 预算。
- 新增回归测试覆盖路由边界和预算执行。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 36 passed
.venv/bin/python -m pytest tests/test_graph_bible.py tests/test_finalize_chapter.py tests/test_director_service.py tests/test_research_workflow.py tests/test_search_backend.py tests/test_bible.py
# 73 passed
.venv/bin/python -m pytest
# 253 passed
```


## 89. 本轮更新：Research Intent Prompt 整改

- 完整读取并执行 `45_research_intent.md`。
- `research_intent.md` 现在明确只有用户提到同人、原作、作者、作品名、书名号、查资料、网络调研或 `/research` 时才 NEED_RESEARCH=yes。
- 增加原创题材反例：修仙文、原创月球城市悬疑、赛博仙侠、克苏鲁风格故事等不触发调研。
- 禁止把量词、类型词、题材词当成作品名。
- 明确“想写一本 X 类型小说”表示原创类型偏好，不把 X 当作品名。
- REASON 限制为不超过 60 中文字符。
- 新增回归测试覆盖原创题材不误判调研。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 37 passed
.venv/bin/python -m pytest tests/test_graph_bible.py tests/test_finalize_chapter.py tests/test_director_service.py tests/test_research_workflow.py tests/test_search_backend.py tests/test_bible.py
# 73 passed
.venv/bin/python -m pytest
# 254 passed
```


## 90. 本轮更新：Retrieval Context Synthesizer Prompt 整改

- 完整读取并执行 `46_retrieval_context_synthesizer.md`。
- `retrieval_context_synthesizer.md` 现在只基于给定搜索结果整理来源事实、可用线索和使用边界。
- 禁止生成大纲、世界观设定、章节正文或写作方案。
- 禁止编造搜索结果之外的事实，禁止无来源事实。
- “可用事实”每条必须带 `source_id`，对应原始搜索结果编号。
- “创作相关线索”必须保持素材性质，不能转成 canon、正史或硬设定。
- mock 和 fallback retrieval context 同步输出 `[source_id: N]` 与 stable canon 使用边界。
- 新增回归测试覆盖 source_id 和 no-canon 边界。

验证：

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py
# 38 passed
.venv/bin/python -m pytest tests/test_graph_bible.py tests/test_finalize_chapter.py tests/test_director_service.py tests/test_research_workflow.py tests/test_search_backend.py tests/test_bible.py
# 73 passed
.venv/bin/python -m pytest
# 255 passed
```

## 45. 本轮调整：大纲阶段角色配置精简

- `graph_outline.STAGE_ROLES` 按新的大纲共创配置精简：方向定位保留类型定位和主题卖点；故事概念仅保留故事概念；世界观保留规则架构和原作/检索一致性；故事流程保留主线结构、节奏悬念和伏笔三个角色。
- 同步移除已删除角色的专属关注点，新增伏笔 Agent 关注点，避免运行时继续生成旧角色 prompt。
- 更新 outline collaboration 回归测试，使进度事件和并行 role_reviews 顺序断言匹配新的角色列表。

验证：

```bash
.venv/bin/python -m pytest tests/test_outline_collaboration.py tests/test_prompt_loader.py
# 83 passed
```

## 91. 本轮更新：执行 `plan.md` Phase 1（节奏改造最小版）

代码改动：

- `src/ai_novelist/graph_chapter_plan.py`：章节卡必需小节改为节奏字段优先，取消“关键冲突/结尾钩子”必填。
- `src/ai_novelist/prompts/chapter_card_synthesizer.md`：新增 Synthesizer Rule（采纳/拒绝/延后建议）与条件项约束。
- `src/ai_novelist/prompts/scene_synthesizer.md`：新增“张力来源不等于冲突”约束。
- `src/ai_novelist/prompts/hook_enhancer.md`：新增“软收束章节不得硬钩子”和“禁止升级项”约束。
- `src/ai_novelist/prompts/review_synthesizer.md`：新增 P0/P1/P2/P3 分级规则。
- `src/ai_novelist/adapters/codex_cli.py`：mock 章节卡补齐节奏字段与采纳/拒绝/延后建议示例。
- `tests/test_prompt_loader.py`：新增对应 prompt 约束断言。

测试结果：

```bash
.venv/bin/python -m pytest tests/test_graph_chapter_plan.py tests/test_graph_review.py tests/test_prompt_loader.py -k "scene_synthesizer or hook_enhancer or review_synthesizer"
# 4 passed

.venv/bin/python -m pytest tests/test_graph_chapter_plan.py tests/test_prompt_loader.py tests/test_graph_review.py
# 46 passed, 1 failed
# 失败项：tests/test_prompt_loader.py::test_world_builder_prompt_limits_rules_to_conflict_principles
# 说明：该断言与本次节奏改造无关，为既有 world_builder prompt 文案不一致。
```

已知限制：

- 尚未进入 Phase 2（`PacingTarget` 结构、动态选择 Agent、动态校验字段）。
- 审稿与修订的结构化分流（blocking/pacing_safe/backlog/rejected）尚未改造，预计在 Phase 4。

## 92. 本轮更新：按 `plan.md` 完成 Phase 2-5

### 代码改动

- 新增 `src/ai_novelist/pacing.py`，提供 `PacingTarget`、章节卡解析、动态 Agent 选择、动态字段要求与 hook 条件。
- `graph_chapter_plan.py`：新增 `load_pacing_target_node`，章节规划改为节奏驱动动态 Agent 路由与动态章节卡校验。
- `graph_scene.py`：场景卡字段校验改为基于节奏目标动态必填。
- `graph_drafting.py`：固定 hook 强化改为节奏感知增强；低强度章走 `restraint_polisher + emotional_resonance_polisher`。
- `graph_review.py`：新增 `pacing_guard_editor`；审稿结构新增 `blocking_fixes/pacing_safe_fixes/backlog_suggestions/rejected_suggestions`。
- `graph_revision.py`：修订计划输入过滤为 `blocking_fixes + pacing_safe_fixes`，并写入 `pacing_self_check`。
- `graph_finalize.py` + `local_store.py`：新增 `pacing_report.json` 持久化与 state 回写。
- `output_contracts.py`：审稿汇总归一化支持新增四类字段。
- `codex_cli.py`、`deepseek.py`：新增节奏相关 Agent 适配。
- 新增 prompts：`chapter_pacing_agent`、`restraint_agent`、`ending_resonance_agent`、`restraint_polisher`、`emotional_resonance_polisher`、`pacing_guard_editor`。

### 测试变更

- 新增 `tests/test_pacing_target.py`，覆盖动态路由与动态字段规则。
- 更新 `test_graph_chapter_plan.py`、`test_graph_drafting.py`、`test_graph_review.py`、`test_finalize_chapter.py`、`test_output_contracts.py` 以匹配节奏改造后行为。

### 验证结果

```bash
.venv/bin/python -m pytest
# 263 passed

.venv/bin/python tests/smoke_chapter_pipeline_mock.py
# chapter pipeline mock smoke passed
```

### 已知限制

- Director 读取最近 3 章节奏并主动给“升压/降压建议”的策略还未深度接入决策提示词；当前已具备 `pacing_report.json` 与 state 数据基础。

## 93. 本轮更新：执行 `plan.md` 全阶段（七阶段重构 + 三层治理）

- 完成大纲共创链路七阶段重构：`direction -> worldbuilding -> characters -> story_flow -> volume_outline -> chapter_outline -> review_lock`。
- 活跃流程移除 `concept`，保留 legacy 兼容迁移：旧项目 `concept` 自动回流到 `direction/worldbuilding`，旧 artifact 保留为参考。
- 新增 `src/ai_novelist/outline/` 六个模块：`stage_contracts/source_ledger/stage_guard/question_filter/renderers/legacy_migration`。
- `graph_outline` 全链路接入：
  - contract 驱动 prompt。
  - guard 统一治理（越权/无来源 canon/公式句/抽象机制语言）。
  - 确认问题过滤，避免模型自造选项菜单。
- 修复 Director 锁阶段 bug：`persist_outputs` 不再先改 `outline_stage`，始终锁当前阶段后推进。
- 旧 standalone `world_builder.md` 路线已移除；worldbuilding 只保留在 outline 阶段。
- mock 输出同步到七阶段与新世界观结构，移除旧 worldbuilding 模板与公式化绝对因果句。

测试结果：

```bash
.venv/bin/python -m pytest tests/test_outline_stage_controls.py
# 9 passed

.venv/bin/python -m pytest tests/test_outline_collaboration.py
# 45 passed

.venv/bin/python -m pytest tests/test_director_service.py tests/test_graph_writer.py tests/smoke_outline_collaboration.py tests/smoke_phase2_chat.py
# 56 passed

.venv/bin/python -m pytest
# 297 passed
```

新增测试：

- `tests/test_outline_stage_controls.py`（stage contracts/guard/filter/legacy/director bug 回归）。

说明：

- 由于会话环境中 `apply_patch` 工具触发沙箱 `bwrap loopback` 错误，本轮改动通过提权脚本化编辑完成，并在每一步后执行语法检查与全量回归验证。



## 94. 本轮更新：开放成人色情/福利/亲密内容

- 按用户偏好调整创作边界：系统不再默认压制成人角色之间的色情、福利、亲密和擦边张力。
- 人物关系阶段允许成人亲密张力与情色/福利关系功能；仍要求服务人物目标、权力关系、诱惑、背叛、占有欲或主线冲突。
- 正文写作允许在已规划成人亲密/色情/福利场景中增强身体距离、触感、欲望拉扯和氛围描写。
- 场景卡、人物弧光编辑和模拟读者 prompt 同步改为继承、修复和反馈既有成人亲密内容，而不是把它当作默认禁区。
- 保留底线：不支持未成年性化、非自愿亲密、剥削性内容；不把成人内容写成无来源全局 canon 或行政审批/绩效表格。

验证：

    .venv/bin/python -m pytest tests/test_prompt_loader.py tests/test_outline_collaboration.py tests/test_outline_stage_controls.py
    # 92 passed


## 95. 本轮修复：回答待确认问题不再弹确认菜单

- 问题：用户回答 Director 的待确认问题，例如 回到刚入门，系统可能把它包装为可执行动作并显示 确认执行/取消，造成追问和确认菜单混在一起。
- 修复：大纲阶段存在 pending_questions 时，编号回答和短文本回答会在模型调用前被确定性识别为 answer_pending_questions。
- 修复：answer_pending_questions 的 revise_outline 在 CLI 中直接执行，不再二次确认。
- 保留：普通大改、跨阶段重修、进入下一阶段仍按原确认流程处理。

验证：

    .venv/bin/python -m pytest tests/test_director_service.py
    # 33 passed


## 96. 本轮收尾：移除旧 worldbuild 对外动作残留

- graph_outline.py 的可路由动作集合移除旧 `worldbuild`，统一使用 `worldbuilding` 进入 outline 世界观阶段。
- README 和 writer chat 回归测试命名同步为 `worldbuilding`。
- 旧 standalone `world_builder.md` prompt 已保持删除状态，prompt loader 回归测试继续断言该 prompt 不存在。

验证：

    .venv/bin/python -m pytest tests/test_prompt_loader.py tests/test_graph_writer.py tests/smoke_phase2.py tests/smoke_phase2_chat.py
    # 32 passed（pytest 收集测试；两个 smoke 脚本另行执行）

    .venv/bin/python tests/smoke_phase2.py
    # phase2 smoke ok

    .venv/bin/python tests/smoke_phase2_chat.py
    # phase2 chat smoke ok

    .venv/bin/python -m pytest
    # 284 passed
