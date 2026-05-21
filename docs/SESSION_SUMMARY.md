# 会话摘要与上下文压缩记录

更新时间：2026-05-21
项目路径：`/home/ubuntu/1.project/ai-novelist`

## 1. 项目目标

构建一个 Linux 环境下的智能小说作家助手：

- 使用 LangGraph 编排多 Agent 创作流程。
- 使用 Codex CLI 作为默认模型执行入口，并支持 DeepSeek API。
- 支持本地 CLI、mock 验证、真实模型模式。
- 后续阶段接入飞书，让用户通过飞书对话控制创作流程。

## 2. 当前完成状态

### 阶段 1：已完成

能力：`init`、`outline`、`show`、mock/真实模式、本地文件存储。

说明：`graph_minimal.py` 仍保留阶段 1 最小图，但 CLI `outline` 已升级为大纲共创图。

### 阶段 2：已完成本地版

能力：

- `compose`：一次性完整多 Agent 创作图。
- 单步 Agent 命令：`worldbuild`、`plan-outline`、`plan-chapters`、`write-chapter`、`review`。
- `chat`：Director Agent 连续对话模式。
- `outline`：交互式大纲共创流程。

## 3. 最新改造摘要

本轮完成了“大纲阶段从线性生成器升级为多轮共创系统”：

- 新增 `src/ai_novelist/graph_outline.py`。
- 新增 prompts：`direction_proposer.md`、`outline_reviser.md`、`outline_editor.md`、`version_comparator.md`。
- 扩展 `NovelState`：`revision_instruction`、`locked_constraints`、`style_preferences`、`outline_versions`、`selected_outline_version`、`pending_questions`、`open_decisions`、`last_user_feedback`、`active_artifact`、`director_intent`。
- `outline` 命令改为小型交互循环，支持 `approve`、`revise:`、`variant`、`review`、`lock:`、`stop`。
- `chat` 的 Director 解析扩展为结构化字段，能把“大纲太普通，强化主角罪感”路由到 `revise_outline`。
- 修复 Director 字段解析中空字段跨行吞掉下一个字段的问题。
- `outline --project ... --idea ...` 在项目不存在时会自动创建项目。

## 4. 当前关键图

### Outline Collaboration 图

```text
director
  |-- ask_user -> END
  |-- propose_directions -> human_feedback -> END
  |-- worldbuild -> generate_outline -> review_outline -> human_feedback -> END
  |-- generate_outline -> review_outline -> human_feedback -> END
  |-- review_outline -> human_feedback -> END
  |-- revise_outline -> compare_versions -> review_outline -> human_feedback -> END
  |-- persist_outline -> END
  |-- show_status -> END
  `-- stop -> END
```

多轮循环由 CLI/chat 的下一轮用户输入驱动，避免单次 graph invoke 内无限自动修订。

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
  |-- worldbuild / plan_chapters / write_chapter / review / revise_chapter -> run_selected_agent -> END
  |-- propose_directions / generate_outline / review_outline / revise_outline / compare_versions -> run_selected_outline_agent -> END
  |-- persist_outputs -> END
  |-- show_status -> END
  `-- stop -> END
```

## 5. 关键文件

源码：

- `src/ai_novelist/cli.py`
- `src/ai_novelist/state.py`
- `src/ai_novelist/graph_outline.py`
- `src/ai_novelist/graph_writer.py`
- `src/ai_novelist/graph_minimal.py`
- `src/ai_novelist/adapters/codex_cli.py`
- `src/ai_novelist/adapters/deepseek.py`
- `src/ai_novelist/storage/local_store.py`
- `src/ai_novelist/prompts/*.md`

文档：

- `README.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `docs/SESSION_SUMMARY.md`

测试：

- `tests/test_outline_collaboration.py`
- `tests/smoke_outline_collaboration.py`
- `tests/test_graph_writer.py`
- `tests/smoke_phase2_chat.py`
- 既有阶段 1/2 测试全部保留。

## 6. 常用命令

大纲共创：

```bash
.venv/bin/ai-novelist outline --project demo-outline --idea "一个失忆工程师在月球城市追查自己的小说手稿" --mock
```

可输入：`approve`、`revise: 强化主角罪感`、`variant`、`review`、`lock: 世界观规则不要改`、`stop`。

Director chat：

```bash
.venv/bin/ai-novelist chat --project demo-chat --mock
```

Compose：

```bash
.venv/bin/ai-novelist compose --project demo-compose --idea "一个失忆工程师在月球城市追查自己的小说手稿" --chapter 1 --mock --auto-approve
```

真实模式前检查：

```bash
codex doctor
```

验证：

```bash
.venv/bin/python -m pytest
.venv/bin/python tests/smoke_outline_collaboration.py
.venv/bin/python tests/smoke_phase2_chat.py
```

当前验证结果：`30 passed`，`smoke_outline_collaboration.py` 通过，`smoke_phase2_chat.py` 通过，`outline --mock --auto-approve` 通过。

## 7. 设计决策

- 保留旧单步命令，新增/增强 `compose`、`chat`、`outline`，不破坏兼容性。
- Director 不直接替代子 Agent，只判断意图、提炼指令、记录约束并调度节点。
- 大纲共创循环跨多轮用户输入推进，而不是单次 invoke 无限循环。
- mock 输出模拟完整流程，不只是占位文本。
- 当前不引入数据库、队列、FastAPI 或飞书依赖。

## 8. 当前限制

- 本地 CLI，不是服务端。
- 飞书未接入。
- 无数据库、队列、权限、多用户隔离或并发锁。
- 真实模式每个 Agent 单独调用一次模型。
- `chat` 的 `persist_outputs` 只保存已有产物，不会自动补齐缺失产物。
- `compose` 不批量生成多章。
- Claude Code Adapter 未实现。

## 9. 后续恢复上下文

建议先读：

```bash
sed -n '1,260p' docs/SESSION_SUMMARY.md
sed -n '1,320p' docs/IMPLEMENTATION_PLAN.md
sed -n '1,520p' src/ai_novelist/graph_outline.py
sed -n '1,360p' src/ai_novelist/graph_writer.py
sed -n '1,360p' src/ai_novelist/cli.py
```

然后跑：

```bash
.venv/bin/python -m pytest
.venv/bin/python tests/smoke_outline_collaboration.py
```
