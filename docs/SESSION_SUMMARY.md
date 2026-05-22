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
- Director 交互转译增强：所有用户输入仍先进入 Director；Director prompt 现在包含最近编辑意见和待确认项，并能把“答案 + 接收/接受/同意”的多项确认合并成下游可执行约束。
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

当前验证结果：`75 passed`。本轮新增验证：`tests/test_director_service.py` 为 `6 passed`，覆盖多项确认转译和“接收/接受”确认词。

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

- 问题：某些对话会把世界观生成成普通 `worldbuild` 产物，写入 `state.worldbuilding`，但没有同步 `outline_stage=worldbuilding` 和阶段产物，导致用户说“确定世界观”时仍被提示处于方向定位。
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

