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

## 唯一推荐入口：Director Chat

`chat` 是当前主入口。Director Agent 作为主脑管理项目上下文，并会在同一个项目状态里调度 outline collaboration graph、世界观、章节写手、编辑等子工作流。用户不需要单独运行 `outline` 命令来进入大纲共创。

启动 mock 对话：

```bash
.venv/bin/ai-novelist chat --project demo-chat --mock
```

示例输入：

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

真实模式：

```bash
.venv/bin/ai-novelist chat --project real-chat --timeout 180
```

Director 可路由动作：

- `ask_user`：追问缺失信息。
- `worldbuild`：调度世界观 Agent。
- `generate_outline` / `revise_outline` / `review_outline`：调度交互式大纲共创节点。
- `plan_chapters`：调度章节细纲 Agent。
- `write_chapter`：调度章节写手 Agent。
- `review`：调度编辑 Agent。
- `revise_chapter`：按编辑意见重写章节。
- `persist_outputs`：保存当前已有产物。
- `show_status`：展示当前项目状态。
- `stop`：结束对话。


## Research 参考调研

`chat` 会在用户显式输入 `/research xxx`，或提出同人/原作/调研类需求时，先进入 research 工作流，生成参考简报后再进入大纲共创。`--mock` 会使用 `MockSearchBackend`；真实模式可通过 `WebSearchBackend` 接入 SerpAPI、Tavily 或 Exa。

```text
/research 苟在初圣
写苟在初圣同人
查一下原作设定再写大纲
```


真实搜索配置示例：

```bash
export AI_NOVELIST_SEARCH_PROVIDER=serpapi  # 可选：serpapi / tavily / exa
export SERPAPI_API_KEY="你的 SerpAPI Key"
.venv/bin/ai-novelist chat --project real-research --provider deepseek --timeout 180
```

也可以单次指定搜索提供方：

```bash
.venv/bin/ai-novelist chat --project real-research --search-provider tavily --provider deepseek
```

相关环境变量：

- `AI_NOVELIST_SEARCH_PROVIDER`：`mock`、`serpapi`、`tavily` 或 `exa`，默认 `mock`。
- `SERPAPI_API_KEY`、`TAVILY_API_KEY`、`EXA_API_KEY`：各搜索提供方的专用 API Key。即使通过 `--search-provider exa` 单次指定 provider，也会读取 `EXA_API_KEY`。
- `AI_NOVELIST_SEARCH_API_KEY`：通用搜索 API Key；未设置提供方专用 key 时使用。
- `AI_NOVELIST_SEARCH_BASE_URL`：自定义搜索接口地址，通常不需要设置。
- `AI_NOVELIST_SEARCH_TIMEOUT`：搜索请求超时秒数，默认 `20`。

产物：

```text
projects/<project>/reference_brief.md
projects/<project>/research_sources.json
```

已有 `reference_brief` 时，chat 不会重复强制调研；后续 outline prompt 会带上参考简报、原作事实和不确定点。

## 交互式大纲共创

大纲共创现在优先从 `chat` 进入。`outline` 命令仍保留，用于调试或单独验证 outline collaboration graph；它与 chat 共享同一个 `projects/<project>/state.json`。

```bash
.venv/bin/ai-novelist outline \
  --project demo-outline \
  --idea "一个失忆工程师在月球城市追查自己的小说手稿" \
  --mock
```

可输入：

- `approve`：保存当前大纲到 `outline.md`。
- `revise: 强化主角罪感，第三幕更黑暗`：修订当前大纲、比较版本并再次审稿。
- `variant`：生成 3 个不同创作方向。
- `review`：只调用大纲编辑审查当前版本。
- `lock: 世界观规则不要改`：写入锁定约束，后续修订会保留。
- `stop`：结束本轮共创，保留 `state.json`。

跳过交互并直接保存当前草案：

```bash
.venv/bin/ai-novelist outline \
  --project demo-outline \
  --idea "一个失忆工程师在月球城市追查自己的小说手稿" \
  --mock \
  --auto-approve
```

真实模式同样可用，去掉 `--mock` 并按需设置 `--timeout`、`--provider`、`--model`。

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

## 飞书长连接机器人

飞书入口复用 DirectorService，与 CLI `chat` 使用同一套项目状态和 Agent 编排。第一版使用飞书官方 `lark-oapi` 长连接接收单聊文本消息，不需要公网 Webhook；确认选项以纯文本编号显示。

### 1. 在飞书开放平台创建应用

1. 打开飞书开放平台：<https://open.feishu.cn/>。
2. 进入开发者后台，创建“企业自建应用”。
3. 在应用详情页找到 `App ID` 和 `App Secret`，后续会配置到本地环境变量。
4. 在“添加应用能力”中添加“机器人”能力，并设置机器人名称、头像等基础信息。

### 2. 配置权限和事件

在应用后台配置机器人需要的权限和事件：

- 权限：允许机器人发送消息，通常是 `im:message:send_as_bot`。
- 事件：订阅接收消息事件 `im.message.receive_v1`。
- 事件订阅方式：选择“使用长连接接收事件”。

当前代码走长连接，不需要配置公网 HTTPS Webhook。企业内部应用如果需要审批，请先在飞书后台提交发布或启用应用，再把机器人添加到你的飞书单聊会话里。

### 3. 本地安装和启动

安装可选依赖：

```bash
cd /home/ubuntu/1.project/ai-novelist
.venv/bin/pip install -e ".[feishu]"
```

配置飞书应用凭据：

```bash
export AI_NOVELIST_FEISHU_APP_ID="cli_xxx"
export AI_NOVELIST_FEISHU_APP_SECRET="你的 App Secret"
```

先用 mock 模式启动，验证链路不调用真实模型：

```bash
.venv/bin/ai-novelist feishu --mock
```

真实模型模式可沿用 `chat` 的 `--provider`、`--model`、`--timeout`、`--search-provider` 和 `--local-corpus-dir` 参数，例如：

```bash
.venv/bin/ai-novelist feishu --provider deepseek --model deepseek-chat --timeout 180
```

这个进程需要持续运行；进程停止后，本地程序就不会再接收飞书消息。

### 4. 在飞书里使用

第一版建议先和机器人单聊。可用命令：

```text
/project
/project demo-novel
查看状态
我想写一个月球城市失忆工程师的悬疑科幻
```

`/project` 会查看当前项目；`/project demo-novel` 会切换或创建本地项目 `demo-novel`。会话映射保存在 `projects/.feishu_sessions.json`。没有当前项目时，机器人会先询问小说名，再用小说名创建对应项目目录；发送“换一本”也会进入新项目创建流程。

如果机器人要求确认，会返回纯文本编号：

```text
1. 确认执行
2. 取消
```

回复 `1` 或 `2` 即可。

当前限制：只支持单聊文本；暂不支持群聊 @、飞书交互卡片按钮、Webhook 或后台队列。

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
.venv/bin/python tests/smoke_outline_collaboration.py
```

当前已验证：`.venv/bin/python -m pytest` 为 `85 passed`，并通过 `smoke_outline_collaboration.py`、`smoke_phase2_chat.py`。

## 当前限制

- 当前主要是本地 CLI；飞书入口为长连接单聊机器人，不是 Web 服务。
- 真实模式每个 Agent 独立调用一次 Codex CLI，没有流式 token 展示。
- `compose` 只处理指定章节，不批量生成多章。
- `outline` 的共创循环由 CLI 或 chat 的下一轮用户输入驱动，不是后台常驻会话。
- `chat` 是单轮图循环驱动，保存时只保存当前已有产物，不会强制补齐缺失产物。
- 飞书入口暂不支持群聊 @、交互卡片、Webhook 或后台队列。
- 没有数据库、队列、多用户权限、并发锁或 Claude Code Adapter。
