# AI Novelist

AI Novelist 是一个本地 CLI 版“智能小说作家助手”，基于 Python、LangGraph，并支持 Codex CLI 或 DeepSeek API 作为模型入口。当前已完成阶段 1 和阶段 2：可以通过一次性 `compose` 工作流生成小说设定与章节，也可以通过 `chat` 进入 Director Agent 连续对话模式，由主编 Agent 判断用户意图并调度子 Agent。

## 环境

```bash
cd /home/ubuntu/1.project/ai-novelist
.venv/bin/ai-novelist --help
```

关键依赖已安装在 `.venv`：

- Python 3.12.3
- langgraph 1.2.0
- pytest 9.0.3

`--mock` 不调用真实模型，适合快速验证；去掉 `--mock` 会按模型提供方配置调用 Codex CLI 或 DeepSeek API。


## 模型提供方配置

默认真实模式仍调用 Codex CLI。也可以切换为 DeepSeek API：

```bash
export AI_NOVELIST_MODEL_PROVIDER=deepseek
export DEEPSEEK_API_KEY="你的 DeepSeek API Key"
export AI_NOVELIST_DEEPSEEK_MODEL=deepseek-chat
```

然后正常运行：

```bash
.venv/bin/ai-novelist chat --project real-chat --timeout 180
```

也可以单次指定提供方：

```bash
.venv/bin/ai-novelist chat --project real-chat --provider deepseek --model deepseek-chat
```

相关环境变量：

- `AI_NOVELIST_MODEL_PROVIDER`：`codex` 或 `deepseek`，默认 `codex`。
- `DEEPSEEK_API_KEY`：DeepSeek API Key，不要提交到仓库。
- `AI_NOVELIST_DEEPSEEK_MODEL`：DeepSeek 模型名，默认 `deepseek-chat`。
- `AI_NOVELIST_DEEPSEEK_BASE_URL`：默认 `https://api.deepseek.com`。
- `AI_NOVELIST_CODEX_BIN`、`AI_NOVELIST_CODEX_TIMEOUT`：Codex CLI 路径与超时。

## 推荐入口：Director Chat

`chat` 是交互式主编 Agent 模式。用户连续输入自然语言，Director Agent 判断意图，并调度世界观、大纲、章节写手、编辑等子 Agent。

启动 mock 对话：

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

真实模式：

```bash
.venv/bin/ai-novelist chat --project real-chat --timeout 180
```

Director 可路由动作：

- `ask_user`：追问缺失信息。
- `worldbuild`：调度世界观 Agent。
- `plan_outline`：调度大纲 Agent。
- `plan_chapters`：调度章节细纲 Agent。
- `write_chapter`：调度章节写手 Agent。
- `review`：调度编辑 Agent。
- `revise_chapter`：按编辑意见重写章节。
- `persist_outputs`：保存当前已有产物。
- `show_status`：展示当前项目状态。
- `stop`：结束对话。

## 一次性 Compose 工作流

如果你希望从创意一次性推进到章节草稿和编辑审稿，用 `compose`：

```bash
.venv/bin/ai-novelist compose \
  --project demo-compose \
  --idea "一个失忆工程师在月球城市追查自己的小说手稿" \
  --chapter 1 \
  --mock \
  --auto-approve
```

工作流：

```text
worldbuild -> plan_outline -> plan_chapters -> write_chapter -> editor_review
  -> pass: human_review -> persist_outputs
  -> revise 且未超过 max_revisions: rewrite_chapter -> editor_review
  -> stop / revise 超限: END
```

默认 `--max-revisions 1`。mock 会模拟“编辑首次要求修改，重写后通过”。

真实 Codex 模式：

```bash
.venv/bin/ai-novelist compose \
  --project real-compose \
  --idea "一个失忆工程师在月球城市追查自己的小说手稿" \
  --chapter 1 \
  --timeout 180
```

## 单步命令

这些命令保留用于单独重跑某个 Agent：

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

人工审核输入：

- `approve`：确认并保存。
- `revise`：标记待修改，不保存当前产物。
- `stop`：停止当前步骤。

## 产物位置

```text
projects/<project>/state.json
projects/<project>/worldbuilding.md
projects/<project>/outline.md
projects/<project>/chapter_plan.md
projects/<project>/chapters/chapter_001.md
projects/<project>/chapters/chapter_001_review.md
```

查看项目状态：

```bash
.venv/bin/ai-novelist show --project demo-compose
```

## 真实 Codex 前置检查

```bash
codex doctor
```

真实模式会多次调用 `codex exec`，耗时明显长于 mock。`--timeout` 是每次 Codex 调用的最长等待秒数。

## 验证

```bash
.venv/bin/python -m pytest
.venv/bin/python tests/smoke_phase2.py
.venv/bin/python tests/smoke_phase2_compose.py
.venv/bin/python tests/smoke_phase2_chat.py
```

当前已验证：`18 passed`。

## 当前限制

- 当前是本地 CLI，不是飞书或 Web 服务。
- 真实模式每个 Agent 独立调用一次 Codex CLI，没有流式 token 展示。
- `compose` 只处理指定章节，不批量生成多章。
- `chat` 是单轮图循环驱动，保存时只保存当前已有产物，不会强制补齐缺失产物。
- 没有数据库、队列、多用户权限、并发锁或 Claude Code Adapter。
