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
- `research`：通过 `MockSearchBackend` 生成参考简报、原作事实、来源列表和不确定点。
- `outline`：交互式大纲共创流程，支持方向、生成、审稿、修订、版本比较、查看、锁定和保存。
- `compose`：一次性完整多 Agent 创作图。
- 单步 Agent 命令：`worldbuild`、`plan-outline`、`plan-chapters`、`write-chapter`、`review`。

## 3. 最新架构摘要

```text
chat 主入口
  -> 写入 state.user_request + messages
  -> research 需求: build_research_graph
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
  -> synthesize_reference_brief
  -> save_research_result
  -> ask_user_confirm
  -> END
```

输出：

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
- `src/ai_novelist/research/search_backend.py`
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
.venv/bin/python -m pytest
.venv/bin/python tests/smoke_outline_collaboration.py
.venv/bin/python tests/smoke_phase2_chat.py
```

当前验证结果：`43 passed`，`smoke_outline_collaboration.py` 通过，`smoke_phase2_chat.py` 通过。

## 8. 设计决策

- `chat` 是唯一推荐主入口，`outline` 和单步命令保留为兼容/调试能力。
- Director 不直接替代子 Agent，只判断意图、提炼指令、记录约束并调度节点。
- research 在大纲前执行，避免把已有小说/IP/专有名词当普通题材生成错误同人设定。
- research 当前使用 mock 搜索，真实联网搜索留给 `WebSearchBackend` 后续实现。
- 大纲共创循环跨多轮用户输入推进，而不是单次 invoke 无限循环。
- 当前不引入数据库、队列、FastAPI 或飞书依赖。

## 9. 当前限制

- 本地 CLI，不是服务端。
- 飞书未接入。
- research 目前不联网，只有 mock 后端。
- 无数据库、队列、权限、多用户隔离或并发锁。
- 真实模式每个 Agent 单独调用一次模型。
- `chat` 的 `persist_outputs` 只保存已有产物，不会自动补齐缺失产物。
- `compose` 不批量生成多章。
- Claude Code Adapter 未实现。

## 10. 后续恢复上下文

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
