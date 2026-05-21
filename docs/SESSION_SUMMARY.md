# 会话摘要与上下文压缩记录

更新时间：2026-05-20
项目路径：`/home/ubuntu/1.project/ai-novelist`

## 1. 项目目标

构建一个 Linux 环境下的智能小说作家助手：

- 使用 LangGraph 编排多 Agent 创作流程。
- 使用 Codex CLI 作为默认模型执行入口。
- 支持本地 CLI、mock 验证、真实 Codex 模式。
- 后续阶段接入飞书，让用户通过飞书对话控制创作流程。

## 2. 当前完成状态

### 阶段 1：已完成

能力：

- `init`：创建本地项目。
- `outline`：最小 LangGraph 流程生成大纲。
- `show`：显示项目状态。
- mock 和真实 Codex 模式。
- 本地文件存储。

关键修复：

- 真实 Codex 模式曾因 stdin 未关闭而卡住，已在 `subprocess.run(..., input="")` 修复。
- Codex JSONL 的最终文本在 `item.text`，已补充解析。

### 阶段 2：已完成本地版

能力：

- `compose`：一次性完整多 Agent 创作图。
- 单步 Agent 命令：`worldbuild`、`plan-outline`、`plan-chapters`、`write-chapter`、`review`。
- `chat`：Director Agent 连续对话模式。
- mock 模式可完整跑通 compose 和 chat。

## 3. 当前架构摘要

```text
CLI
  |-- outline -> graph_minimal
  |-- compose -> build_composer_graph
  |-- chat -> build_chat_graph，每轮用户输入调用一次
  `-- 单步命令 -> build_writer_graph

CodexCLIAdapter
  |-- mock: 根据 AGENT 标记返回模拟输出
  `-- real: codex exec --json --skip-git-repo-check

LocalStore
  `-- projects/<project>/state.json + Markdown 产物
```

## 4. 关键图

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

### Director Chat 图

```text
director
  |-- ask_user -> END
  |-- worldbuild / plan_outline / plan_chapters / write_chapter / review / revise_chapter
  |      -> run_selected_agent -> END
  |-- persist_outputs -> persist_available_outputs -> END
  |-- show_status -> show_status_node -> END
  `-- stop -> END
```

## 5. 关键文件

源码：

- `src/ai_novelist/cli.py`
- `src/ai_novelist/state.py`
- `src/ai_novelist/graph_minimal.py`
- `src/ai_novelist/graph_writer.py`
- `src/ai_novelist/adapters/base.py`
- `src/ai_novelist/adapters/codex_cli.py`
- `src/ai_novelist/storage/local_store.py`
- `src/ai_novelist/prompts/director.md`
- `src/ai_novelist/prompts/world_builder.md`
- `src/ai_novelist/prompts/outline_planner.md`
- `src/ai_novelist/prompts/chapter_planner.md`
- `src/ai_novelist/prompts/chapter_writer.md`
- `src/ai_novelist/prompts/editor.md`

文档：

- `README.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `docs/SESSION_SUMMARY.md`

测试：

- `tests/test_codex_adapter.py`
- `tests/test_graph_minimal.py`
- `tests/test_graph_writer.py`
- `tests/test_local_store.py`
- `tests/test_prompt_loader.py`
- `tests/test_state.py`
- `tests/smoke_phase1.py`
- `tests/smoke_phase2.py`
- `tests/smoke_phase2_compose.py`
- `tests/smoke_phase2_chat.py`

## 6. 状态字段

`NovelState` 保持旧 `state.json` 向后兼容。

创作字段：

- `idea`
- `worldbuilding`
- `outline`
- `chapter_plan`
- `current_chapter`
- `chapter_draft`
- `editor_notes`

流程字段：

- `review_status`
- `editor_decision`
- `revision_count`
- `max_revisions`
- `quality_score`
- `next_action`
- `error`

对话字段：

- `messages`
- `user_request`
- `director_action`
- `director_message`
- `pending_question`
- `active_task`

## 7. 常用命令

Director chat：

```bash
.venv/bin/ai-novelist chat --project demo-chat --mock
```

Compose：

```bash
.venv/bin/ai-novelist compose \
  --project demo-compose \
  --idea "一个失忆工程师在月球城市追查自己的小说手稿" \
  --chapter 1 \
  --mock \
  --auto-approve
```

真实模式前检查：

```bash
codex doctor
```

验证：

```bash
.venv/bin/python -m pytest
.venv/bin/python tests/smoke_phase2.py
.venv/bin/python tests/smoke_phase2_compose.py
.venv/bin/python tests/smoke_phase2_chat.py
```

当前验证结果：`18 passed`。

## 8. 设计决策

- 保留旧单步命令，新增 `compose` 和 `chat`，不破坏兼容性。
- Director 不直接生成长篇正文，只判断意图并调度子 Agent。
- `chat` 使用 CLI 循环，每轮调用一次 `build_chat_graph`。
- `compose` 使用一个完整 LangGraph 自动推进流程。
- mock 输出模拟真实流程，不只是占位文本。
- 自动修订由 `max_revisions` 限制，默认 1。
- 当前不引入数据库、队列、FastAPI 或飞书依赖。

## 9. 当前限制

- 本地 CLI，不是服务端。
- 飞书未接入。
- 无数据库、队列、权限、多用户隔离或并发锁。
- 真实模式每个 Agent 单独调用一次 Codex CLI。
- `chat` 的 `persist_outputs` 只保存已有产物，不会自动补齐缺失产物。
- `compose` 不批量生成多章。
- Claude Code Adapter 未实现。

## 10. 后续恢复上下文

建议先读：

```bash
sed -n '1,260p' docs/SESSION_SUMMARY.md
sed -n '1,320p' docs/IMPLEMENTATION_PLAN.md
sed -n '1,360p' src/ai_novelist/graph_writer.py
sed -n '1,320p' src/ai_novelist/cli.py
```

然后跑：

```bash
.venv/bin/python -m pytest
.venv/bin/python tests/smoke_phase2_chat.py
```

## 11. 下一步建议

1. 把 CLI 中的业务流程抽到 service 层，便于飞书复用。
2. 给真实模式增加阶段进度输出。
3. 实现项目级文件锁。
4. 开始阶段 3：飞书 webhook、签名校验、消息去重、会话映射、后台任务。
