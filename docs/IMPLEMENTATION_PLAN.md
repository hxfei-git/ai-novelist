# AI Novelist 当前架构与实施计划

## 1. 当前状态

AI Novelist 当前是本地 CLI 版智能小说作家助手，基于 Python、LangGraph 和 Codex CLI。

已完成：

- 阶段 1：最小 LangGraph + Codex CLI 大纲生成闭环。
- 阶段 2：真正的多 Agent 小说创作工作流。
- 阶段 2 增强：Director Agent 对话模式。
- mock 模式：不依赖外部模型即可端到端验证。
- 真实模式：通过 `codex exec --json --skip-git-repo-check` 调用 Codex CLI。

未完成：

- 阶段 3 飞书机器人入口。
- 后台任务队列。
- 数据库、多用户存储、并发锁。
- Claude Code Adapter。
- 多章节批量自动续写。
- Web UI。

## 2. 总体架构

```text
用户
  |
  v
本地 CLI: ai-novelist
  |-- init
  |-- outline
  |-- compose
  |-- chat
  |-- worldbuild / plan-outline / plan-chapters / write-chapter / review
  `-- show
  |
  v
配置层
  |-- config.py
  |-- AI_NOVELIST_PROJECTS_DIR
  |-- AI_NOVELIST_CODEX_BIN
  `-- AI_NOVELIST_CODEX_TIMEOUT
  |
  v
LangGraph 编排层
  |-- graph_minimal.py
  |     `-- generate_outline -> human_review -> persist_outline
  |
  `-- graph_writer.py
        |-- 单 Agent 兼容图
        |     `-- run_agent -> human_review -> persist -> END
        |
        |-- Compose 多 Agent 图
        |     worldbuild
        |       -> plan_outline
        |       -> plan_chapters
        |       -> write_chapter
        |       -> editor_review
        |            |-- pass -> human_review -> persist_outputs -> END
        |            |-- revise 且 revision_count < max_revisions
        |            |      -> rewrite_chapter -> editor_review
        |            `-- stop / revise 超限 -> END
        |
        `-- Director Chat 图
              director
                |-- ask_user -> END
                |-- run_selected_agent -> END
                |-- persist_outputs -> END
                |-- show_status -> END
                `-- stop -> END
  |
  v
Agent 执行层
  |-- AgentAdapter
  `-- CodexCLIAdapter
        |-- mock=True: 本地模拟 Director 和子 Agent 输出
        `-- mock=False: 调用 codex exec
  |
  v
Prompt 模板层
  |-- director.md
  |-- world_builder.md
  |-- outline_planner.md
  |-- chapter_planner.md
  |-- chapter_writer.md
  `-- editor.md
  |
  v
本地文件存储
  `-- projects/<project>/
        |-- state.json
        |-- worldbuilding.md
        |-- outline.md
        |-- chapter_plan.md
        `-- chapters/
              |-- chapter_001.md
              `-- chapter_001_review.md
```

## 3. 核心模块

### `src/ai_novelist/cli.py`

CLI 入口。负责解析命令、加载项目状态、创建 `CodexCLIAdapter`、构建 LangGraph 图并展示结果。

命令：

- `init`：创建项目。
- `outline`：阶段 1 单步大纲生成。
- `compose`：阶段 2 一次性多 Agent 创作流程。
- `chat`：Director Agent 连续对话模式。
- `worldbuild`、`plan-outline`、`plan-chapters`、`write-chapter`、`review`：兼容单步 Agent 命令。
- `show`：显示项目状态和产物路径。

### `src/ai_novelist/graph_minimal.py`

阶段 1 最小图：

```text
generate_outline -> human_review -> persist_outline -> END
```

### `src/ai_novelist/graph_writer.py`

阶段 2 核心模块。

包含：

- `build_writer_graph`：单 Agent 兼容图。
- `build_composer_graph`：完整 compose 多 Agent 图。
- `build_chat_graph`：Director Agent 单轮对话图。
- `parse_editor_review`：解析 `STATUS` 和 `QUALITY_SCORE`。
- `parse_director_output`：解析 Director 的 `ACTION/MESSAGE/CHAPTER`。

### `src/ai_novelist/state.py`

`NovelState` 是所有图共享的状态对象，并保持旧 `state.json` 向后兼容。

核心创作字段：

- `project_id`
- `title`
- `idea`
- `worldbuilding`
- `outline`
- `chapter_plan`
- `current_chapter`
- `chapter_draft`
- `editor_notes`

流程控制字段：

- `review_status`
- `editor_decision`
- `revision_count`
- `max_revisions`
- `quality_score`
- `next_action`
- `error`

Director 对话字段：

- `messages: list[dict[str, str]]`
- `user_request: str`
- `director_action: str`
- `director_message: str`
- `pending_question: str`
- `active_task: str`

### `src/ai_novelist/adapters/codex_cli.py`

Codex CLI 适配器。

真实命令形态：

```bash
codex exec --json --skip-git-repo-check -C <workspace> <prompt>
```

关键点：

- `subprocess.run(..., input="")` 关闭 stdin，避免非 TTY 环境卡住。
- 解析 Codex JSONL 的 `item.text`。
- mock 根据 prompt 中的 `AGENT:` 返回不同 Agent 输出。
- Director mock 根据用户关键词路由动作。
- Compose mock 模拟一次编辑退回和重写通过。

### `src/ai_novelist/storage/local_store.py`

本地文件存储，负责 `state.json` 和各类 Markdown 产物读写。

## 4. Director Chat 使用方式

```bash
.venv/bin/ai-novelist chat --project demo-chat --mock
```

示例输入：

```text
我想写一个月球城市失忆工程师的悬疑科幻
帮我先设计世界观
大纲太普通，增强主角罪感
写第 1 章
让编辑审稿
保存当前结果
显示当前状态
退出
```

Chat 图是单轮图，由 CLI 循环驱动：

```text
director
  |-- ask_user -> END
  |-- worldbuild / plan_outline / plan_chapters / write_chapter / review / revise_chapter
  |      -> run_selected_agent -> END
  |-- persist_outputs -> persist_available_outputs -> END
  |-- show_status -> show_status_node -> END
  `-- stop -> END
```

Director 输出格式：

```text
ACTION: ask_user|worldbuild|plan_outline|plan_chapters|write_chapter|review|revise_chapter|persist_outputs|show_status|stop
MESSAGE: 给用户看的简短回复
CHAPTER: 可选章节编号
```

## 5. Compose 使用方式

```bash
.venv/bin/ai-novelist compose \
  --project demo-compose \
  --idea "一个失忆工程师在月球城市追查自己的小说手稿" \
  --chapter 1 \
  --mock \
  --auto-approve
```

真实模式：

```bash
.venv/bin/ai-novelist compose \
  --project real-compose \
  --idea "一个失忆工程师在月球城市追查自己的小说手稿" \
  --chapter 1 \
  --timeout 180
```

## 6. 单步命令

```bash
.venv/bin/ai-novelist init --title demo
.venv/bin/ai-novelist outline --project demo --idea "小说创意" --mock --auto-approve
.venv/bin/ai-novelist worldbuild --project demo --mock --auto-approve
.venv/bin/ai-novelist plan-outline --project demo --mock --auto-approve
.venv/bin/ai-novelist plan-chapters --project demo --mock --auto-approve
.venv/bin/ai-novelist write-chapter --project demo --chapter 1 --mock --auto-approve
.venv/bin/ai-novelist review --project demo --chapter 1 --mock --auto-approve
.venv/bin/ai-novelist show --project demo
```

这些命令仍走单 Agent 兼容图，不等同于完整 compose 协作图。

## 7. 验收命令

```bash
.venv/bin/python -m pytest
.venv/bin/python tests/smoke_phase2.py
.venv/bin/python tests/smoke_phase2_compose.py
.venv/bin/python tests/smoke_phase2_chat.py
.venv/bin/ai-novelist compose --project demo-compose --idea "一个失忆工程师在月球城市追查自己的小说手稿" --chapter 1 --mock --auto-approve
.venv/bin/ai-novelist show --project demo-compose
```

当前已验证：`18 passed`。

## 8. 测试覆盖

- `tests/test_codex_adapter.py`：Codex mock、JSONL 解析、错误处理。
- `tests/test_graph_minimal.py`：阶段 1 最小图。
- `tests/test_graph_writer.py`：单 Agent 图、compose 图、chat 图、编辑路由、Director 路由。
- `tests/test_local_store.py`：本地存储。
- `tests/test_prompt_loader.py`：prompt 加载。
- `tests/test_state.py`：状态序列化兼容。
- `tests/smoke_phase1.py`：阶段 1 smoke。
- `tests/smoke_phase2.py`：阶段 2 单 Agent smoke。
- `tests/smoke_phase2_compose.py`：compose smoke。
- `tests/smoke_phase2_chat.py`：Director chat smoke。

## 9. 当前限制

- 本项目仍是本地 CLI，不是长期运行服务。
- 真实模式每个 Agent 独立调用一次 `codex exec`，没有流式 token 展示。
- `chat` 是 CLI 循环驱动的单轮图，不是后台会话服务。
- `persist_outputs` 只保存当前已有产物，不会强制补齐缺失产物。
- `compose` 只围绕指定章节运行，不批量生成多章。
- 本地文件存储没有并发锁。
- 没有数据库、队列、飞书、Web UI 或多租户权限。
- Claude Code Adapter 未实现。

## 10. 阶段 3 后续计划

阶段 3 接入飞书：

```text
飞书用户
  -> 飞书机器人 / Webhook
  -> 命令解析
  -> 调用现有 chat / compose / 单步能力
  -> 后台任务执行
  -> 飞书消息回复摘要和审核入口
```

待实现：

- FastAPI webhook。
- 飞书 challenge 和签名校验。
- 消息去重。
- 用户 ID 到项目 ID 的会话映射。
- 后台任务执行，避免 webhook 超时。
- 飞书中的 `确认/修改/停止/继续` 审核命令。
- 项目级文件锁。
