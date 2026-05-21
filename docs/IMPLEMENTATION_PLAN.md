# AI Novelist 当前架构与实施计划

## 1. 当前状态

AI Novelist 当前是本地 CLI 版智能小说作家助手，基于 Python、LangGraph、Codex CLI，并支持 DeepSeek API 作为可选模型提供方。

已完成：

- 阶段 1：最小 LangGraph + 模型适配器 + 本地存储。
- 阶段 2：compose 多 Agent 小说创作图。
- 阶段 2 增强：Director Agent chat 对话模式。
- 大纲共创增强：outline collaboration graph，支持生成、审稿、用户反馈、修订、版本比较、锁定约束和保存。
- mock 模式：不依赖外部模型即可端到端验证。
- 真实模式：Codex CLI 或 DeepSeek API。

未完成：

- 阶段 3 飞书机器人入口。
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
  |-- init
  |-- outline: 大纲共创交互循环
  |-- compose: 一次性多 Agent 创作
  |-- chat: Director Agent 连续对话
  |-- worldbuild / plan-outline / plan-chapters / write-chapter / review
  `-- show
  |
  v
模型适配层
  |-- AgentAdapter
  |-- CodexCLIAdapter
  `-- DeepSeekAdapter
  |
  v
LangGraph 编排层
  |-- graph_minimal.py
  |     `-- 保留阶段 1 最小图
  |
  |-- graph_outline.py
  |     director
  |       -> propose_directions / worldbuild / generate_outline / review_outline / revise_outline
  |       -> compare_versions / persist_outline / show_status / ask_user / END
  |
  `-- graph_writer.py
        |-- build_writer_graph: 单 Agent 兼容图
        |-- build_composer_graph: 完整 compose 图
        `-- build_chat_graph: Director 单轮对话图，可调度 outline 共创节点
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
        |-- worldbuilding.md
        |-- outline.md
        |-- chapter_plan.md
        `-- chapters/
```

## 3. 大纲共创流程

`outline` 命令现在优先使用 `build_outline_collaboration_graph`：

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
      -> persist_outline -> END
      -> show_status -> END
      -> stop -> END
```

说明：

- 图内保留 conditional edge，但不会在同一次 invoke 里无限自动修订。
- “生成 -> 审稿 -> 用户反馈 -> 修订 -> 再审稿 -> 再反馈 -> 保存”的循环由 CLI/chat 的下一轮用户输入驱动。
- `review_outline` 如果返回 `revise`，只写入 `revision_instruction` 和审稿状态，不会自动保存。
- `revise_outline` 会写入新大纲版本，并调用 `compare_versions` 帮用户理解差异。

支持的用户输入：

- `approve`：确认并保存当前大纲。
- `revise: ...`：提炼为 `revision_instruction`，进入修订。
- `variant`：生成 3 个不同创作方向。
- `review`：调用大纲编辑审查。
- `lock: ...`：写入 `locked_constraints`。
- `stop`：结束当前流程但保留 state。

## 4. Compose 图

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

compose 仍保留一次性自动推进能力，适合快速从创意生成到章节草稿和编辑意见。

## 5. Director Chat 图

```text
director
  |-- ask_user -> END
  |-- worldbuild / plan_chapters / write_chapter / review / revise_chapter
  |      -> run_selected_agent -> END
  |-- propose_directions / generate_outline / review_outline / revise_outline / compare_versions
  |      -> run_selected_outline_agent -> END
  |-- persist_outputs -> END
  |-- show_status -> END
  `-- stop -> END
```

Director 输出结构：

```text
ACTION: ask_user|propose_directions|worldbuild|generate_outline|review_outline|revise_outline|compare_versions|plan_chapters|write_chapter|review|revise_chapter|persist_outputs|show_status|stop
TARGET: outline|worldbuilding|chapter|character|style|project|unknown
INTENT: create|revise|review|approve|reject|lock|variant|save|status|stop|answer
MESSAGE: 给用户看的简短回复
INSTRUCTION: 提炼后的用户要求
LOCKED_CONSTRAINTS: 可选，逗号分隔
STYLE_PREFERENCES: 可选，逗号分隔
CHAPTER: 可选章节编号
```

## 6. 状态字段

`NovelState.from_dict/to_dict` 保持旧 `state.json` 向后兼容。新增大纲共创字段：

- `revision_instruction`
- `locked_constraints`
- `style_preferences`
- `outline_versions`
- `selected_outline_version`
- `pending_questions`
- `open_decisions`
- `last_user_feedback`
- `active_artifact`
- `director_intent`

既有 chat 字段仍保留：`messages`、`user_request`、`director_action`、`director_message`、`pending_question`、`active_task`。

## 7. 使用方式

大纲共创 mock：

```bash
.venv/bin/ai-novelist outline   --project demo-outline   --idea "一个失忆工程师在月球城市追查自己的小说手稿"   --mock
```

大纲共创自动保存当前草案：

```bash
.venv/bin/ai-novelist outline   --project demo-outline   --idea "一个失忆工程师在月球城市追查自己的小说手稿"   --mock   --auto-approve
```

Director chat：

```bash
.venv/bin/ai-novelist chat --project demo-chat --mock
```

Compose：

```bash
.venv/bin/ai-novelist compose   --project demo-compose   --idea "一个失忆工程师在月球城市追查自己的小说手稿"   --chapter 1   --mock   --auto-approve
```

## 8. 测试覆盖

- `tests/test_graph_minimal.py`：阶段 1 最小图。
- `tests/test_graph_writer.py`：单 Agent、compose、chat、Director 路由。
- `tests/test_outline_collaboration.py`：大纲 approve、revise、lock、variant、旧 state 兼容、chat 路由到大纲修订。
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
.venv/bin/ai-novelist outline --project demo-outline-collab --idea "一个失忆工程师在月球城市追查自己的小说手稿" --mock --auto-approve
.venv/bin/ai-novelist show --project demo-outline-collab
```

当前已验证：`30 passed`，并通过 `smoke_outline_collaboration.py`、`smoke_phase2_chat.py`、`outline --mock --auto-approve`。

## 9. 当前限制

- 仍是本地 CLI，不是长期运行服务。
- outline/chat 的多轮共创由 CLI 循环驱动，不是后台会话服务。
- 真实模式每个 Agent 独立调用一次模型，没有流式 token 展示。
- `persist_outputs` 只保存当前已有产物，不会自动补齐缺失产物。
- `compose` 只围绕指定章节运行，不批量生成多章。
- 本地文件存储没有并发锁。
- 没有飞书、数据库、队列、Web UI、多租户权限或 Claude Code Adapter。

## 10. 阶段 3 后续计划

```text
飞书用户
  -> 飞书机器人 / Webhook
  -> 会话映射与消息去重
  -> 调用现有 chat / outline / compose 能力
  -> 后台执行长任务
  -> 飞书消息回复摘要和审核入口
```

下一步应先抽出 service 层，把 CLI 循环中对 `LocalStore`、graph invoke 和用户输入归一化的逻辑复用给飞书入口。
