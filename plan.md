# AI Novelist 全量小说智能体工作流开发计划

版本：v1.0  
日期：2026-05-22  
目标仓库：`hxfei-git/ai-novelist`  
目标执行者：Codex CLI  
目标模式：渐进式改造，不推倒重来，不破坏现有 `chat`、`outline`、`compose`、`--mock` 工作流。

---

## 0. 给 Codex CLI 的执行说明

请按本计划逐阶段开发。每个阶段都应尽量形成一次独立提交，阶段之间不要跳跃实现。除非某阶段明确要求，否则不要一次性重写整个项目。

开发时必须遵守以下约束：

1. 保留现有项目结构：运行时代码在 `src/ai_novelist/`，prompt 在 `src/ai_novelist/prompts/`，测试在 `tests/`，项目产物在 `projects/<project>/`。
2. 保留 `DirectorService` 作为统一入口；不要让用户直接和底层 Agent 对话。
3. 保留 `chat` 作为推荐入口；`outline`、`compose`、`plan-chapters`、`write-chapter`、`review` 等命令继续兼容。
4. 所有新功能必须支持 `--mock`，测试默认使用 mock，不依赖真实 Codex、DeepSeek 或外部搜索服务。
5. 每个阶段完成后必须更新：
   - `docs/IMPLEMENTATION_PLAN.md`
   - `docs/SESSION_SUMMARY.md`
6. 每个阶段至少运行：
   ```bash
   .venv/bin/python -m pytest
   ```
   若阶段涉及端到端工作流，还要运行对应 smoke 脚本。
7. 所有新增状态字段都必须兼容旧 `state.json`，不能因为旧项目缺少新字段而崩溃。
8. 大文本不要无限塞入 `state.json`。`state.json` 保存索引、摘要、状态、路径；Markdown/JSON 产物保存到文件。
9. 不要引入数据库、向量库、后台队列、Web UI，除非本计划后续阶段明确要求。第一轮目标是稳定的本地文件系统工作流。
10. 不要把所有 Agent 的历史消息全文传给下一个 Agent。Agent 间通过 `NovelState + Artifact Registry + NovelBible + ContextBuilder` 共享知识。

---

## 1. 总目标

将当前 AI Novelist 从：

```text
DirectorService
  -> Research Graph
  -> Outline Collaboration Graph
  -> Writer/Compose Graph
  -> LocalStore / NovelState
```

升级为：

```text
DirectorService
  -> Intent Router
  -> Research Graph
  -> Story Bible Graph
  -> Outline Collaboration Graph
  -> Chapter Planning Graph
  -> Scene Design Graph
  -> Drafting Graph
  -> Review Graph
  -> Revision Graph
  -> Finalize / Continuity Update Graph
  -> Export Graph
  -> LocalStore / Artifact Registry / NovelBible / NovelState
```

核心升级点：

1. 新增 `Artifact Registry`：统一记录所有阶段产物、路径、版本、来源 Agent。
2. 新增 `NovelBible`：维护小说长期知识，包括项目定位、故事核心、世界规则、人物卡、时间线、伏笔表、章节摘要、风格指南。
3. 新增 `ContextBuilder`：让每个 Agent 按任务读取必要上下文，避免把全部历史对话塞进 prompt。
4. 扩展 `Outline Graph`：从六阶段升级为完整大纲协作阶段。
5. 拆分 `Writer Graph`：将章节创作拆为章节卡、场景卡、正文草稿、多编辑审稿、修订、定稿、小说圣经更新。
6. 强化 `DirectorService`：支持前置条件自动补齐，例如用户直接说“写第 1 章”时自动生成缺失的 chapter card 和 scene cards。
7. 建立可测试的端到端 mock 流程：从一句创意到大纲锁定、写第 1 章、审稿、修订、定稿、导出。

---

## 2. 非目标

本轮开发不要做以下事情：

1. 不要把所有 workflow 合成一个巨型 LangGraph。
2. 不要让 Agent 自由 handoff 给另一个 Agent；由 `DirectorService` 和 graph 条件边显式调度。
3. 不要接入复杂数据库；继续用本地 JSON + Markdown。
4. 不要引入向量数据库；如果需要长期语义检索，作为后续版本。
5. 不要做前端 UI。
6. 不要重写模型 adapter；继续复用现有 Codex CLI / DeepSeek / mock adapter。
7. 不要让测试依赖真实模型、真实搜索 API、真实飞书环境。

---

## 3. 当前架构理解

当前项目已有基础能力：

```text
src/ai_novelist/
  cli.py
  config.py
  director_service.py
  state.py
  graph_research.py
  graph_outline.py
  graph_writer.py
  graph_minimal.py
  adapters/
  feishu/
  prompts/
  research/
  storage/

tests/
  test_*.py
  smoke_*.py
```

当前主入口：

```bash
.venv/bin/ai-novelist chat --project demo-chat --mock
```

当前推荐交互路径：

```text
用户
  -> DirectorService.handle_turn()
  -> 读取 NovelState
  -> 判断用户意图
  -> 调用 research / outline / writer / compose 相关节点或图
  -> 保存 state.json
```

当前状态流转原则可以保留：

```text
用户只和 Director 对话
Director 选择图
图调用专业 Agent
专业 Agent 产物写回 NovelState / LocalStore
NovelState 成为下一轮上下文
```

本计划不是推翻现有设计，而是补齐“长期知识管理、章节创作闭环、结构化产物版本管理”。

---

## 4. 最终目标架构

### 4.1 逻辑架构

```text
CLI / Feishu / Future API
  -> DirectorService
      -> intent detection
      -> prerequisite resolver
      -> graph dispatcher
      -> state persistence
      -> user-facing response builder

Graphs:
  graph_research.py
  graph_outline.py
  graph_bible.py
  graph_chapter_plan.py
  graph_scene.py
  graph_drafting.py
  graph_review.py
  graph_revision.py
  graph_export.py
  graph_writer.py        # compatibility wrapper; gradually becomes thin

Knowledge / Storage:
  NovelState             # short state, current workflow status, summaries, paths
  Artifact Registry      # artifact metadata, paths, versions
  NovelBible             # long-term novel knowledge
  LocalStore             # local filesystem persistence
  ContextBuilder         # task-specific context assembly
```

### 4.2 知识流

```text
Agent 输出结构化 artifact
  -> Artifact Registry 记录路径、版本、来源
  -> NovelBible 吸收稳定设定和长期知识
  -> ContextBuilder 按任务读取必要知识
  -> 下一个 Agent 基于筛选后的上下文工作
```

不要使用：

```text
Agent A 的全部对话历史 -> Agent B
```

应使用：

```text
Agent A 的阶段产物 -> Artifact Registry / NovelBible -> ContextBuilder -> Agent B
```

### 4.3 推荐主线流程

```text
用户创意
  -> optional Research Graph
  -> Outline Collaboration Graph
      direction
      -> concept
      -> worldbuilding
      -> characters
      -> story_flow
      -> volume_outline
      -> chapter_outline
      -> review_lock
  -> Bible Graph 初始化小说圣经
  -> Chapter Planning Graph 生成章节卡
  -> Scene Graph 生成场景卡
  -> Drafting Graph 写正文草稿
  -> Review Graph 多编辑审稿
  -> Revision Graph 修订
  -> Finalize / Bible Update Graph 定稿并更新圣经
  -> Export Graph 导出整卷/整本
```

---

## 5. 全局设计原则

### 5.1 Director 只调度，不亲自创作

`DirectorService` 负责：

```text
理解用户意图
选择子图
检查前置条件
调用 graph
保存 state
返回用户可读摘要
```

`DirectorService` 不应直接生成大量小说内容。

### 5.2 Graph 是业务能力，不是所有流程的大一统容器

不要创建一个 `graph_full_novel.py` 包含所有节点。推荐多个可独立测试的子图：

```text
graph_bible.py
图负责小说圣经初始化和更新

graph_chapter_plan.py
图负责章节卡

graph_scene.py
图负责场景卡

graph_drafting.py
图负责正文草稿
```

`DirectorService` 负责编排它们。

### 5.3 Agent 输出要结构化

Agent 可以输出 Markdown，但内部最好同时支持结构化 JSON 或带固定小节的 Markdown。

建议所有 review 类输出包含：

```text
decision: pass / revise / stop
score: 0-100
issues: list
rewrite_tasks: list
blocking_issues: list
```

### 5.4 `state.json` 不保存全部大文本

`state.json` 可以保存：

```text
当前阶段
当前章节
最新产物摘要
最新产物路径
计数器
少量必要字段
```

大文本保存到：

```text
projects/<project>/outline/*.md
projects/<project>/chapters/chapter_001/*.md
projects/<project>/novel_bible.md
projects/<project>/novel_bible.json
```

### 5.5 prompt 统一通过 ContextBuilder 获取上下文

不要在每个 graph 节点里手动拼接大量上下文。新增 `context_builder.py` 后，逐步让 graph 使用：

```python
context = build_context(
    state=state,
    store=store,
    purpose="drafting",
    chapter=state.active_chapter,
    max_chars=12000,
)
```

### 5.6 永远保留 mock 模式

新增 graph、prompt、state 字段都必须支持 mock。mock 输出需要稳定，以保证 `pytest` 和 smoke 测试可重复。

---

## 6. 目标目录结构

最终建议结构：

```text
src/ai_novelist/
  __init__.py
  cli.py
  config.py
  director_service.py
  state.py

  artifacts.py
  bible.py
  context_builder.py

  graph_research.py
  graph_outline.py
  graph_bible.py
  graph_chapter_plan.py
  graph_scene.py
  graph_drafting.py
  graph_review.py
  graph_revision.py
  graph_export.py
  graph_writer.py              # compatibility wrapper
  graph_minimal.py

  adapters/
  feishu/
  prompts/
    director.md

    outline_stage_synthesizer.md
    outline_direction_type_agent.md
    outline_direction_theme_agent.md
    outline_direction_risk_agent.md
    outline_concept_agent.md
    outline_concept_conflict_agent.md
    outline_concept_theme_agent.md
    outline_concept_twist_agent.md
    outline_worldbuilding_rule_agent.md
    outline_worldbuilding_faction_agent.md
    outline_worldbuilding_consistency_agent.md
    outline_characters_protagonist_agent.md
    outline_characters_relationship_agent.md
    outline_characters_antagonist_agent.md
    outline_story_flow_structure_agent.md
    outline_story_flow_pacing_agent.md
    outline_story_flow_foreshadowing_agent.md
    outline_volume_agent.md
    outline_chapter_agent.md
    outline_review_lock_agent.md

    chapter_goal_agent.md
    chapter_conflict_agent.md
    chapter_hook_agent.md
    chapter_card_synthesizer.md

    scene_breakdown_agent.md
    scene_conflict_check_agent.md
    scene_synthesizer.md

    chapter_writer.md
    dialogue_enhancer.md
    atmosphere_enhancer.md
    hook_enhancer.md
    style_normalizer.md

    continuity_editor.md
    structure_editor.md
    character_arc_editor.md
    style_editor.md
    simulated_reader.md
    review_synthesizer.md

    revision_planner.md
    targeted_reviser.md
    revision_self_check.md

    bible_update_extractor.md
    bible_conflict_checker.md
    bible_update_synthesizer.md

  research/
  storage/

tests/
  test_artifacts.py
  test_bible.py
  test_context_builder.py
  test_graph_bible.py
  test_graph_chapter_plan.py
  test_graph_scene.py
  test_graph_drafting.py
  test_graph_review.py
  test_graph_revision.py
  test_finalize_chapter.py
  test_graph_export.py
  test_director_prerequisites.py
  smoke_full_workflow_mock.py
  smoke_chapter_pipeline_mock.py
  smoke_bible_update_mock.py
```

---

## 7. 项目产物目录结构

目标产物结构：

```text
projects/<project>/
  state.json
  project_context.md
  artifacts.json
  novel_bible.json
  novel_bible.md

  briefs/
    project_brief.md
    reference_brief.md
    story_concept.md

  outline/
    direction.md
    concept.md
    worldbuilding.md
    characters.md
    story_flow.md
    volume_outline.md
    chapter_outline.md
    review_lock.md

  chapters/
    chapter_001/
      chapter_card.md
      scene_cards.md
      draft_v1.md
      review_v1.md
      review_v1.json
      revision_plan_v1.md
      draft_v2.md
      final.md
      summary.md

    chapter_002/
      chapter_card.md
      scene_cards.md
      draft_v1.md
      review_v1.md
      review_v1.json
      final.md
      summary.md

  exports/
    manuscript.md
    volume_001.md
    novel_bible.md
```

兼容旧产物：

```text
projects/<project>/worldbuilding.md
projects/<project>/outline.md
projects/<project>/chapter_plan.md
projects/<project>/chapters/chapter_001.md
projects/<project>/chapters/chapter_001_review.md
```

旧路径不要立即删除。新路径和旧路径可并存，必要时旧命令写入旧路径，新 pipeline 写入新路径，同时在保存时同步一份兼容产物。

---

## 8. 数据结构设计

### 8.1 ArtifactRecord

新增文件：

```text
src/ai_novelist/artifacts.py
```

建议定义：

```python
from dataclasses import dataclass, field, asdict
from typing import Any, Literal

ArtifactType = Literal[
    "project_brief",
    "reference_brief",
    "story_concept",
    "direction",
    "worldbuilding",
    "characters",
    "story_flow",
    "volume_outline",
    "chapter_outline",
    "review_lock",
    "chapter_card",
    "scene_cards",
    "chapter_draft",
    "review_report",
    "revision_plan",
    "final_chapter",
    "chapter_summary",
    "novel_bible",
    "export",
]

@dataclass
class ArtifactRecord:
    id: str
    type: str
    path: str
    version: int = 1
    source_agent: str = ""
    graph: str = ""
    stage: str = ""
    chapter: int | None = None
    created_at: str = ""
    updated_at: str = ""
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
```

必要函数：

```python
def load_artifacts(project_dir: Path) -> list[ArtifactRecord]: ...
def save_artifacts(project_dir: Path, records: list[ArtifactRecord]) -> None: ...
def register_artifact(project_dir: Path, record: ArtifactRecord) -> ArtifactRecord: ...
def get_latest_artifact(project_dir: Path, artifact_type: str, chapter: int | None = None, stage: str | None = None) -> ArtifactRecord | None: ...
def save_markdown_artifact(project_dir: Path, relative_path: str, content: str, artifact_type: str, **kwargs) -> ArtifactRecord: ...
def save_json_artifact(project_dir: Path, relative_path: str, data: dict[str, Any], artifact_type: str, **kwargs) -> ArtifactRecord: ...
def load_artifact_text(project_dir: Path, record_or_path: ArtifactRecord | str) -> str: ...
```

### 8.2 NovelBible

新增文件：

```text
src/ai_novelist/bible.py
```

建议定义：

```python
from dataclasses import dataclass, field, asdict
from typing import Any, Literal

@dataclass
class ProjectBrief:
    title: str = ""
    genre: str = ""
    subgenre: str = ""
    target_reader: str = ""
    core_experience: str = ""
    tone_keywords: list[str] = field(default_factory=list)
    locked_constraints: list[str] = field(default_factory=list)

@dataclass
class StoryConcept:
    logline: str = ""
    premise: str = ""
    core_conflict: str = ""
    theme: str = ""
    central_question: str = ""
    ending_direction: str = ""

@dataclass
class WorldRule:
    name: str
    description: str
    limitation: str = ""
    cost: str = ""
    source_stage: str = ""

@dataclass
class CharacterCard:
    name: str
    role: str
    identity: str = ""
    external_goal: str = ""
    internal_need: str = ""
    flaw: str = ""
    fear: str = ""
    secret: str = ""
    arc: str = ""
    voice: str = ""
    relationships: list[str] = field(default_factory=list)
    status: str = "active"

@dataclass
class PlotThread:
    name: str
    description: str
    status: Literal["open", "active", "resolved"] = "open"
    related_chapters: list[int] = field(default_factory=list)

@dataclass
class ForeshadowingItem:
    id: str
    setup_chapter: int | None = None
    setup_text: str = ""
    payoff_chapter: int | None = None
    payoff_text: str = ""
    status: Literal["planned", "setup", "paid_off", "dropped"] = "planned"

@dataclass
class TimelineEvent:
    id: str
    order: int
    chapter: int | None = None
    event: str = ""
    characters: list[str] = field(default_factory=list)
    location: str = ""

@dataclass
class NovelBible:
    project: ProjectBrief = field(default_factory=ProjectBrief)
    concept: StoryConcept = field(default_factory=StoryConcept)
    world_rules: list[WorldRule] = field(default_factory=list)
    factions: list[dict[str, Any]] = field(default_factory=list)
    characters: list[CharacterCard] = field(default_factory=list)
    plot_threads: list[PlotThread] = field(default_factory=list)
    timeline: list[TimelineEvent] = field(default_factory=list)
    foreshadowing: list[ForeshadowingItem] = field(default_factory=list)
    style_guide: dict[str, Any] = field(default_factory=dict)
    chapter_summaries: dict[str, str] = field(default_factory=dict)
    open_questions: list[str] = field(default_factory=list)
    version: int = 1
```

必要函数：

```python
def bible_to_dict(bible: NovelBible) -> dict[str, Any]: ...
def bible_from_dict(data: dict[str, Any]) -> NovelBible: ...
def load_bible(project_dir: Path) -> NovelBible: ...
def save_bible(project_dir: Path, bible: NovelBible) -> None: ...
def render_bible_markdown(bible: NovelBible) -> str: ...
def merge_bible_updates(bible: NovelBible, updates: dict[str, Any]) -> NovelBible: ...
def detect_bible_conflicts(bible: NovelBible, updates: dict[str, Any]) -> list[dict[str, Any]]: ...
```

### 8.3 NovelState 扩展

修改文件：

```text
src/ai_novelist/state.py
```

新增字段建议：

```python
bible_version: int = 0
bible_updated_at: str = ""
active_graph: str = ""
active_stage: str = ""
active_chapter: int = 1
active_scene: str = ""

project_brief: str = ""
story_concept: str = ""
characters: str = ""
story_flow: str = ""
volume_outline: str = ""
chapter_outline: str = ""

current_chapter_card: str = ""
current_scene_cards: str = ""
current_review_report: str = ""
current_revision_plan: str = ""
current_final_chapter: str = ""

chapter_summaries: dict[str, str] = field(default_factory=dict)
artifact_registry: list[dict[str, Any]] = field(default_factory=list)

open_threads: list[str] = field(default_factory=list)
resolved_threads: list[str] = field(default_factory=list)
foreshadowing_registry: list[dict[str, Any]] = field(default_factory=list)
timeline_events: list[dict[str, Any]] = field(default_factory=list)
character_states: dict[str, Any] = field(default_factory=dict)

last_context_digest: str = ""
last_agent_reports: list[dict[str, Any]] = field(default_factory=list)
```

兼容要求：

1. 旧 `state.json` 没有这些字段时正常加载。
2. `from_dict` / `model_validate` / dataclass 初始化逻辑应提供默认值。
3. `state.json` 不应保存完整 `novel_bible.md` 正文，只保存版本、摘要、路径。

---

## 9. ContextBuilder 设计

新增文件：

```text
src/ai_novelist/context_builder.py
```

### 9.1 核心函数

```python
def build_context(
    state: NovelState,
    store: LocalStore,
    purpose: str,
    chapter: int | None = None,
    stage: str | None = None,
    max_chars: int = 12000,
) -> str:
    ...
```

### 9.2 支持的 purpose

```text
director
research
outline_stage
worldbuilding
characters
story_flow
chapter_planning
scene_design
drafting
dialogue_enhancement
review
review_continuity
review_structure
review_character
review_style
simulated_reader
revision
bible_update
export
```

### 9.3 上下文优先级

```text
用户当前请求
> locked_constraints
> novel_bible
> 当前任务 artifact
> project_context
> reference_brief / canon_facts
> 当前章节前文摘要
> 历史 messages 摘要
```

### 9.4 输出格式

`build_context` 返回 Markdown 字符串：

```text
# Task Context

## 用户当前请求
...

## 当前任务
...

## 锁定约束
...

## 项目简报
...

## 故事核心
...

## 世界观规则
...

## 人物卡
...

## 当前大纲相关片段
...

## 当前章节相关信息
...

## 已写前文摘要
...

## 参考资料
...

## 不确定点
...

## 输出要求
...
```

### 9.5 上下文策略表

建议内部实现：

```python
CONTEXT_POLICY = {
    "drafting": [
        "current_user_request",
        "locked_constraints",
        "project_brief",
        "story_concept",
        "style_guide",
        "world_rules",
        "characters",
        "current_chapter_card",
        "current_scene_cards",
        "previous_chapter_summary",
        "relevant_foreshadowing",
    ],
    "review": [
        "locked_constraints",
        "novel_bible_full_or_summary",
        "chapter_card",
        "scene_cards",
        "current_draft",
        "timeline",
        "foreshadowing",
    ],
    "revision": [
        "locked_constraints",
        "current_draft",
        "review_report",
        "revision_plan",
        "chapter_card",
        "scene_cards",
    ],
}
```

### 9.6 截断策略

实现 `truncate_sections`：

```python
def truncate_sections(sections: list[tuple[str, str]], max_chars: int) -> str:
    ...
```

规则：

1. `locked_constraints` 永不截断，除非超过极端长度。
2. 当前章节卡、场景卡优先保留。
3. `reference_brief` 可截断。
4. 历史 messages 只保留摘要或最近少量内容。
5. 截断时标记：`[已截断，完整内容见 artifact path]`。

---

## 10. Graph 设计规格

### 10.1 graph_research.py

保留现有实现。未来只做小改：

输入：

```text
用户研究需求
已有 reference_brief
本地语料 / search backend
```

输出：

```text
reference_brief.md
research_sources.json
state.reference_brief
state.canon_facts
state.research_uncertainties
state.research_sources
```

改造点：

1. research 结果注册到 Artifact Registry。
2. `reference_brief.md` 兼容旧路径，同时可放入 `briefs/reference_brief.md`。
3. ContextBuilder 可读取 research 结果。

### 10.2 graph_outline.py

升级阶段：

```text
direction
-> concept
-> worldbuilding
-> characters
-> story_flow
-> volume_outline
-> chapter_outline
-> review_lock
-> done
```

每个阶段内部：

```text
current stage context
  -> 3-4 个阶段角色 Agent
  -> outline_stage_synthesizer
  -> save stage artifact
  -> register artifact
  -> optionally update bible
  -> ask user confirm / advance
```

阶段产物：

```text
outline/direction.md
outline/concept.md
outline/worldbuilding.md
outline/characters.md
outline/story_flow.md
outline/volume_outline.md
outline/chapter_outline.md
outline/review_lock.md
```

兼容要求：

1. 旧 `outline_draft` 阶段读取时不要崩溃。
2. 可以迁移到 `volume_outline`，或在旧状态完成后继续 `chapter_outline`。
3. `outline.md` 仍然保存一个总合并版。

### 10.3 graph_bible.py

新增。

节点：

```text
load_bible
  -> extract_bible_updates
  -> detect_bible_conflicts
  -> apply_bible_updates
  -> save_bible
  -> summarize_bible_update
  -> END
```

输入：

```text
state
artifact registry
outline stage artifacts
chapter final / chapter summary
review reports
```

输出：

```text
novel_bible.json
novel_bible.md
state.bible_version
state.bible_updated_at
state.chapter_summaries
state.timeline_events
state.foreshadowing_registry
state.character_states
```

触发时机：

1. `review_lock` 完成后初始化圣经。
2. 每个 outline stage 完成后可轻量更新。
3. 章节 `finalize_chapter` 后更新章节摘要、时间线、伏笔、人物状态。
4. 用户显式输入“更新小说圣经”时运行。

### 10.4 graph_chapter_plan.py

新增。

节点：

```text
select_chapter
  -> load_chapter_context
  -> chapter_goal_agent
  -> chapter_conflict_agent
  -> chapter_hook_agent
  -> chapter_card_synthesizer
  -> validate_chapter_card
  -> save_chapter_card
  -> END
```

输出：

```text
chapters/chapter_XXX/chapter_card.md
state.current_chapter_card
ArtifactType: chapter_card
```

章节卡格式：

```text
# 第 N 章：标题

## 本章目标
## 本章视角人物
## 入场状态
## 主要冲突
## 关键事件
## 新增信息
## 伏笔设置
## 伏笔回收
## 人物变化
## 情绪曲线
## 结尾钩子
## 禁止事项
## 预计字数
```

### 10.5 graph_scene.py

新增。

节点：

```text
load_chapter_card
  -> scene_breakdown_agent
  -> conflict_check_agent
  -> scene_synthesizer
  -> validate_scene_cards
  -> save_scene_cards
  -> END
```

输出：

```text
chapters/chapter_XXX/scene_cards.md
state.current_scene_cards
ArtifactType: scene_cards
```

场景卡格式：

```text
# Scene 1：场景名

## 地点
## 出场人物
## 场景目的
## 人物目标
## 冲突对象
## 入场信息
## 关键信息揭示
## 情绪变化
## 场景转折
## 退出状态
## 与下一场景的连接
```

### 10.6 graph_drafting.py

新增。

节点：

```text
load_drafting_context
  -> draft_scene_batch
  -> merge_scenes
  -> dialogue_enhance
  -> atmosphere_enhance
  -> hook_enhance
  -> style_normalize
  -> save_draft
  -> END
```

输入：

```text
NovelBible
chapter_card
scene_cards
style_guide
locked_constraints
previous_chapter_summary
```

输出：

```text
chapters/chapter_XXX/draft_v1.md
state.chapter_draft
ArtifactType: chapter_draft
```

兼容：

1. 旧 `write_chapter` action 调用新 `graph_drafting.py`。
2. 可同步写旧路径 `chapters/chapter_001.md`，避免旧测试失败。

### 10.7 graph_review.py

新增。

节点：

```text
load_review_context
  -> continuity_review_agent
  -> structure_review_agent
  -> character_arc_review_agent
  -> style_review_agent
  -> simulated_reader_agent
  -> review_synthesizer
  -> decide_pass_or_revise
  -> save_review_report
  -> END
```

输出 Markdown：

```text
chapters/chapter_XXX/review_v1.md
```

输出 JSON：

```text
chapters/chapter_XXX/review_v1.json
```

JSON 格式：

```json
{
  "decision": "revise",
  "score": 78,
  "blocking_issues": [],
  "issues": [
    {
      "type": "continuity",
      "severity": "medium",
      "location": "scene_2",
      "problem": "主角在上一章不知道 X，但本章直接说出 X。",
      "suggestion": "改为让配角提供线索，或在上一章补一个发现过程。"
    }
  ],
  "rewrite_tasks": [
    {
      "target": "scene_2",
      "instruction": "重写主角获得线索的过程，避免无来源信息。"
    }
  ]
}
```

状态更新：

```text
state.editor_notes
state.editor_decision
state.quality_score
state.current_review_report
```

### 10.8 graph_revision.py

新增。

节点：

```text
load_revision_context
  -> build_revision_plan
  -> revise_targeted_sections
  -> merge_revision
  -> revision_self_check
  -> save_revised_draft
  -> maybe_review_again
  -> END
```

输出：

```text
chapters/chapter_XXX/revision_plan_v1.md
chapters/chapter_XXX/draft_v2.md
state.current_revision_plan
state.chapter_draft
```

注意：

1. 默认局部修订，不要整章重写。
2. 如果 `review_report` 指示 blocking issue，可允许整章重写。
3. `revision_count >= max_revisions` 时停止，并让 Director 提示用户确认。

### 10.9 finalize / continuity update

可放在 `graph_bible.py` 或新增 `graph_continuity.py`。第一版建议放在 `graph_bible.py`，减少模块数量。

流程：

```text
load_latest_passed_draft
  -> save_final_chapter
  -> summarize_chapter
  -> extract_bible_updates_from_final
  -> update_timeline
  -> update_foreshadowing
  -> update_character_states
  -> save_bible
  -> END
```

输出：

```text
chapters/chapter_XXX/final.md
chapters/chapter_XXX/summary.md
novel_bible.json
novel_bible.md
state.current_final_chapter
state.chapter_summaries
```

### 10.10 graph_export.py

新增。

节点：

```text
collect_final_chapters
  -> normalize_format
  -> build_manuscript
  -> build_volume
  -> copy_bible_export
  -> save_export
  -> END
```

输出：

```text
exports/manuscript.md
exports/volume_001.md
exports/novel_bible.md
```

---

## 11. DirectorService 改造

### 11.1 新增 action

当前 actions 保留，同时新增：

```python
DIRECTOR_ACTIONS = {
    "ask_user",
    "research",

    "init_bible",
    "update_bible",
    "show_bible",

    "continue_outline",
    "generate_direction",
    "generate_concept",
    "generate_worldbuilding",
    "generate_characters",
    "generate_story_flow",
    "generate_volume_outline",
    "generate_chapter_outline",
    "review_lock_outline",

    "plan_chapter",
    "plan_scenes",
    "write_chapter",

    "review_chapter",
    "revise_chapter",
    "finalize_chapter",

    "show_status",
    "show_outline",
    "show_reference",
    "show_chapter",
    "show_review",

    "export_project",
    "persist_outputs",
    "stop",
}
```

### 11.2 action aliases

```python
ACTION_ALIASES = {
    "worldbuild": "generate_worldbuilding",
    "generate_outline": "continue_outline",
    "review_outline": "continue_outline",
    "revise_outline": "continue_outline",
    "plan_chapters": "plan_chapter",
    "review": "review_chapter",
}
```

### 11.3 前置条件解析

新增函数：

```python
def resolve_prerequisites(state: NovelState, action: str) -> list[str]:
    ...
```

规则：

```python
PREREQUISITES = {
    "write_chapter": [
        "ensure_bible",
        "ensure_chapter_card",
        "ensure_scene_cards",
    ],
    "review_chapter": [
        "ensure_chapter_draft",
    ],
    "revise_chapter": [
        "ensure_review_report",
    ],
    "finalize_chapter": [
        "ensure_review_passed_or_user_confirmed",
    ],
    "export_project": [
        "ensure_at_least_one_final_chapter",
    ],
}
```

示例：用户输入“写第 1 章”时：

```text
Director detects action = write_chapter, chapter = 1
  -> if no novel_bible: run graph_bible init if possible, else ask to finish outline
  -> if no chapter_card: run graph_chapter_plan
  -> if no scene_cards: run graph_scene
  -> run graph_drafting
```

### 11.4 用户可见返回

Director 返回用户时不要展示全部内部产物。推荐格式：

```text
已完成：第 1 章草稿

生成产物：
- 章节卡：chapters/chapter_001/chapter_card.md
- 场景卡：chapters/chapter_001/scene_cards.md
- 草稿：chapters/chapter_001/draft_v1.md

摘要：
...

下一步建议：让编辑审稿 / 修改某段 / 定稿
```

---

## 12. Prompt 输出规范

所有新增 prompt 建议统一包含：

```text
你是 <agent role>。
你只能基于 Task Context 工作，不要擅自改动锁定约束。
如果发现冲突，请输出“冲突报告”，不要自行覆盖设定。
输出必须使用指定 Markdown 小节。
不要解释你是 AI。
不要输出与任务无关的内容。
```

### 12.1 review_synthesizer prompt 必须要求 JSON block

示例：

```text
请先输出人类可读审稿报告，再输出一个 ```json 代码块。
JSON 必须包含：decision, score, blocking_issues, issues, rewrite_tasks。
decision 只能是 pass/revise/stop。
score 必须是 0-100 的整数。
```

代码应能从模型输出中提取 JSON；如果提取失败，mock/真实模式都要降级生成一个保守 review JSON。

### 12.2 bible_update_extractor prompt

要求输出：

```json
{
  "project": {},
  "concept": {},
  "world_rules": [],
  "factions": [],
  "characters": [],
  "plot_threads": [],
  "timeline": [],
  "foreshadowing": [],
  "style_guide": {},
  "chapter_summaries": {},
  "open_questions": []
}
```

不要让 prompt 直接覆盖整个 Bible，只提取 updates，由代码层 merge。

---

## 13. 开发阶段总览

建议按以下顺序执行：

```text
Phase 0  Baseline inventory and docs
Phase 1  Artifact Registry
Phase 2  Novel Bible
Phase 3  ContextBuilder
Phase 4  Expand Outline Graph
Phase 5  Bible Graph
Phase 6  Chapter Planning Graph
Phase 7  Scene Design Graph
Phase 8  Drafting Graph
Phase 9  Review Graph
Phase 10 Revision Graph
Phase 11 Finalize Chapter + Bible Update
Phase 12 Export Graph
Phase 13 Director UX + full smoke workflow
```

每个阶段都应：

1. 修改代码。
2. 增加/更新测试。
3. 更新 docs。
4. 运行测试。
5. 在 `docs/SESSION_SUMMARY.md` 记录测试结果和未完成限制。

---

## 14. Phase 0：Baseline inventory and docs

### 目标

在正式改造前，确认当前测试通过，并把本开发计划加入文档。

### 修改文件

```text
docs/IMPLEMENTATION_PLAN.md
docs/SESSION_SUMMARY.md
```

### 任务

1. 运行：
   ```bash
   .venv/bin/python -m pytest
   .venv/bin/python tests/smoke_outline_collaboration.py
   .venv/bin/python tests/smoke_phase2_chat.py
   ```
2. 若 smoke 脚本不存在或名称变化，记录实际可用脚本。
3. 将本计划摘要写入 `docs/IMPLEMENTATION_PLAN.md`。
4. 在 `docs/SESSION_SUMMARY.md` 记录 baseline 测试结果。

### 验收标准

1. 当前测试结果被记录。
2. 没有功能代码改动，或只有文档改动。
3. docs 明确后续阶段目标。

### 建议提交信息

```text
docs: add full workflow implementation roadmap
```

### Codex CLI 提示词

```text
请先做 Phase 0：不要改业务代码。阅读当前 README、AGENTS.md、docs 目录和 tests 目录，运行现有 pytest 和相关 smoke 脚本。把全量小说智能体工作流升级计划摘要写入 docs/IMPLEMENTATION_PLAN.md，并在 docs/SESSION_SUMMARY.md 记录 baseline 测试结果、当前可用 smoke 脚本和后续阶段。保持现有功能不变。
```

---

## 15. Phase 1：Artifact Registry

### 目标

建立统一产物注册表，后续所有 graph 都能保存和查找产物。

### 新增文件

```text
src/ai_novelist/artifacts.py
tests/test_artifacts.py
```

### 修改文件

```text
src/ai_novelist/storage/*
src/ai_novelist/state.py  # 如需存 artifact_registry 简要索引
docs/IMPLEMENTATION_PLAN.md
docs/SESSION_SUMMARY.md
```

### 实现任务

1. 新增 `ArtifactRecord` dataclass。
2. 实现：
   ```python
   load_artifacts
   save_artifacts
   register_artifact
   get_latest_artifact
   save_markdown_artifact
   save_json_artifact
   load_artifact_text
   ```
3. `artifacts.json` 保存到：
   ```text
   projects/<project>/artifacts.json
   ```
4. 如果 `LocalStore` 有项目路径方法，新增：
   ```python
   artifact_registry_path(project_id)
   ```
   或按现有 store 风格实现。
5. 写入时自动创建父目录。
6. 重复注册同类型/同章节/同阶段产物时 version 自动 +1。
7. 不要破坏现有 `persist_outputs`。
8. 单元测试覆盖：
   - 空 registry 加载。
   - markdown artifact 保存。
   - json artifact 保存。
   - latest artifact 查询。
   - version 递增。

### 验收标准

1. `tests/test_artifacts.py` 通过。
2. `.venv/bin/python -m pytest` 通过。
3. 旧命令仍能运行。
4. docs 更新。

### 建议提交信息

```text
feat: add artifact registry for generated novel assets
```

### Codex CLI 提示词

```text
请实现 Phase 1：新增 Artifact Registry。新增 src/ai_novelist/artifacts.py，定义 ArtifactRecord，并实现 load_artifacts、save_artifacts、register_artifact、get_latest_artifact、save_markdown_artifact、save_json_artifact、load_artifact_text。registry 保存到 projects/<project>/artifacts.json。按现有 LocalStore 风格增加路径辅助方法。新增 tests/test_artifacts.py 覆盖空加载、保存 markdown/json、latest 查询、version 递增。不要破坏现有 CLI 和测试。更新 docs/IMPLEMENTATION_PLAN.md 和 docs/SESSION_SUMMARY.md，运行 .venv/bin/python -m pytest。
```

---

## 16. Phase 2：Novel Bible

### 目标

建立小说圣经数据结构和文件保存能力。

### 新增文件

```text
src/ai_novelist/bible.py
tests/test_bible.py
```

### 修改文件

```text
src/ai_novelist/storage/*
src/ai_novelist/state.py
docs/IMPLEMENTATION_PLAN.md
docs/SESSION_SUMMARY.md
```

### 实现任务

1. 新增 dataclass：
   ```text
   ProjectBrief
   StoryConcept
   WorldRule
   CharacterCard
   PlotThread
   ForeshadowingItem
   TimelineEvent
   NovelBible
   ```
2. 实现：
   ```python
   bible_to_dict
   bible_from_dict
   load_bible
   save_bible
   render_bible_markdown
   merge_bible_updates
   detect_bible_conflicts
   ```
3. 保存路径：
   ```text
   projects/<project>/novel_bible.json
   projects/<project>/novel_bible.md
   ```
4. `load_bible` 在文件不存在时返回空 `NovelBible()`。
5. `save_bible` 同时保存 JSON 和 Markdown。
6. `merge_bible_updates` 第一版可以简单合并：
   - project/concept/style_guide 覆盖非空字段。
   - world_rules/characters/timeline/foreshadowing 按 name/id 去重追加或更新。
   - chapter_summaries 合并 dict。
7. `detect_bible_conflicts` 第一版可做简单检查：
   - 同名人物不同 role。
   - 同名 world_rule 描述明显不同。
   - 章节摘要覆盖旧摘要时记录 warning。

### 验收标准

1. 能保存和加载 `novel_bible.json`。
2. 能渲染 `novel_bible.md`。
3. 空项目不会崩溃。
4. `.venv/bin/python -m pytest` 通过。

### 建议提交信息

```text
feat: add novel bible data model and persistence
```

### Codex CLI 提示词

```text
请实现 Phase 2：新增小说圣经模块。新增 src/ai_novelist/bible.py，定义 ProjectBrief、StoryConcept、WorldRule、CharacterCard、PlotThread、ForeshadowingItem、TimelineEvent、NovelBible 等 dataclass，并实现 bible_to_dict、bible_from_dict、load_bible、save_bible、render_bible_markdown、merge_bible_updates、detect_bible_conflicts。保存到 projects/<project>/novel_bible.json 和 novel_bible.md。新增 tests/test_bible.py。保证旧 state.json 兼容，更新 docs 并运行 pytest。
```

---

## 17. Phase 3：ContextBuilder

### 目标

新增统一上下文构建器，避免各 graph 节点手拼上下文。

### 新增文件

```text
src/ai_novelist/context_builder.py
tests/test_context_builder.py
```

### 修改文件

```text
docs/IMPLEMENTATION_PLAN.md
docs/SESSION_SUMMARY.md
```

第一阶段先不大规模改 graph，只实现和测试 ContextBuilder。

### 实现任务

1. 实现 `build_context`。
2. 支持 purpose：
   ```text
   director
   outline_stage
   chapter_planning
   scene_design
   drafting
   review
   revision
   bible_update
   export
   ```
3. 实现 section builder：
   ```python
   build_locked_constraints_section
   build_project_brief_section
   build_bible_section
   build_artifact_section
   build_reference_section
   build_chapter_section
   build_messages_summary_section
   truncate_sections
   ```
4. 从 LocalStore 读取：
   - `novel_bible.md`
   - artifact registry 中的相关产物
   - `reference_brief.md`
   - chapter 文件
5. `max_chars` 生效。
6. 截断要保留必要小节标题。
7. 测试覆盖：
   - drafting context 包含 chapter_card 和 scene_cards。
   - review context 包含 draft。
   - locked constraints 优先保留。
   - max_chars 限制有效。

### 验收标准

1. `tests/test_context_builder.py` 通过。
2. 不影响旧 graph。
3. docs 记录上下文策略。

### 建议提交信息

```text
feat: add task-specific context builder
```

### Codex CLI 提示词

```text
请实现 Phase 3：新增统一 ContextBuilder。新增 src/ai_novelist/context_builder.py，提供 build_context(state, store, purpose, chapter=None, stage=None, max_chars=12000)，支持 director、outline_stage、chapter_planning、scene_design、drafting、review、revision、bible_update、export 等 purpose。上下文优先级为当前请求、locked_constraints、NovelBible、当前 artifact、project_context、reference_brief、章节摘要、messages 摘要。实现 truncate_sections。新增 tests/test_context_builder.py，先不要大规模改现有 graph。更新 docs 并运行 pytest。
```

---

## 18. Phase 4：扩展 Outline Graph

### 目标

将当前六阶段大纲协作升级为完整大纲阶段。

### 修改文件

```text
src/ai_novelist/graph_outline.py
src/ai_novelist/state.py
src/ai_novelist/prompts/*.md
tests/test_graph_outline*.py
tests/smoke_outline_collaboration.py
docs/IMPLEMENTATION_PLAN.md
docs/SESSION_SUMMARY.md
```

### 阶段列表

```python
OUTLINE_STAGES = [
    "direction",
    "concept",
    "worldbuilding",
    "characters",
    "story_flow",
    "volume_outline",
    "chapter_outline",
    "review_lock",
    "done",
]
```

### 兼容旧阶段

如果旧 state 中存在：

```text
outline_draft
```

兼容策略：

```python
if stage == "outline_draft":
    stage = "volume_outline"
```

或保留旧阶段读取，但后续推进到 `chapter_outline`。

### 每阶段角色 Agent

#### direction

```text
类型定位 Agent
主题卖点 Agent
风险编辑 Agent
```

#### concept

```text
故事概念 Agent
核心冲突 Agent
主题表达 Agent
反转机制 Agent
```

#### worldbuilding

```text
规则架构 Agent
势力资源 Agent
代价限制 Agent
原作/检索一致性 Agent
```

#### characters

```text
主角弧光 Agent
关系冲突 Agent
反派/势力 Agent
角色声音 Agent
```

#### story_flow

```text
主线结构 Agent
节奏悬念 Agent
伏笔代价 Agent
副线设计 Agent
```

#### volume_outline

```text
分卷策划 Agent
卷内高潮 Agent
卷间钩子 Agent
```

#### chapter_outline

```text
章节拆分 Agent
章节钩子 Agent
章节可执行性 Agent
连续性编辑 Agent
```

#### review_lock

```text
总编辑 Agent
约束审计 Agent
章节准备 Agent
```

### 输出产物

每阶段保存：

```text
projects/<project>/outline/<stage>.md
```

同时更新：

```text
state.outline_stage_artifacts[stage]
```

并注册 Artifact。

### 总大纲兼容

`review_lock` 后生成或更新：

```text
projects/<project>/outline.md
```

内容为各阶段合并版。

### 测试要求

1. mock 下从 `direction` 推进到 `done`。
2. 每阶段有 artifact。
3. 旧 `outline_draft` state 能加载和推进。
4. `smoke_outline_collaboration.py` 更新并通过。

### 验收标准

1. 用户在 chat 中继续大纲流程不报错。
2. `outline` 命令仍可调试大纲流程。
3. `outline.md` 仍生成。
4. `.venv/bin/python -m pytest` 通过。

### 建议提交信息

```text
feat: expand outline collaboration stages
```

### Codex CLI 提示词

```text
请实现 Phase 4：扩展 outline collaboration graph。将阶段升级为 direction、concept、worldbuilding、characters、story_flow、volume_outline、chapter_outline、review_lock、done。保持旧 outline_draft 状态兼容。为新增阶段配置角色 Agent 和 mock 输出。每阶段保存到 projects/<project>/outline/<stage>.md，写入 state.outline_stage_artifacts，并注册 artifact。review_lock 后更新 outline.md 合并版。更新相关 prompt、测试和 smoke_outline_collaboration.py。更新 docs，运行 pytest 和 outline smoke。
```

---

## 19. Phase 5：Bible Graph

### 目标

让系统能基于 outline 和章节产物初始化/更新小说圣经。

### 新增文件

```text
src/ai_novelist/graph_bible.py
tests/test_graph_bible.py
```

### 修改文件

```text
src/ai_novelist/director_service.py
src/ai_novelist/prompts/bible_update_extractor.md
src/ai_novelist/prompts/bible_conflict_checker.md
src/ai_novelist/prompts/bible_update_synthesizer.md
docs/IMPLEMENTATION_PLAN.md
docs/SESSION_SUMMARY.md
```

### 实现任务

1. 新增 graph 节点：
   ```text
   load_bible
   extract_bible_updates
   detect_bible_conflicts
   apply_bible_updates
   save_bible
   summarize_bible_update
   ```
2. mock 模式下从 `outline_stage_artifacts` 生成简化 Bible。
3. 真实模式下调用 prompt 从 outline/章节产物中提取 updates。
4. `review_lock` 完成后自动运行 `init_bible`。
5. Director 新增 action：
   ```text
   init_bible
   update_bible
   show_bible
   ```
6. 用户输入“查看小说圣经”时返回 `novel_bible.md` 摘要。
7. 保存 `novel_bible.json` 和 `novel_bible.md`。
8. 注册 `novel_bible` artifact。

### 测试要求

1. 无 bible 文件时可初始化。
2. 有 outline artifacts 时生成 bible。
3. show_bible 返回可读摘要。
4. 冲突检测不会阻塞 mock 主流程。

### 验收标准

1. 大纲锁定后有：
   ```text
   projects/<project>/novel_bible.json
   projects/<project>/novel_bible.md
   ```
2. `chat --mock` 中输入“查看小说圣经”能返回内容。
3. `.venv/bin/python -m pytest` 通过。

### 建议提交信息

```text
feat: add novel bible graph and director actions
```

### Codex CLI 提示词

```text
请实现 Phase 5：新增 graph_bible.py。节点包括 load_bible、extract_bible_updates、detect_bible_conflicts、apply_bible_updates、save_bible、summarize_bible_update。mock 模式可从 outline_stage_artifacts 生成简化 NovelBible。review_lock 完成后自动 init/update Bible。DirectorService 新增 init_bible、update_bible、show_bible action，用户输入“查看小说圣经”可展示摘要。保存 novel_bible.json 和 novel_bible.md，并注册 artifact。新增 tests/test_graph_bible.py，更新 docs，运行 pytest。
```

---

## 20. Phase 6：Chapter Planning Graph

### 目标

从总大纲/章节大纲/小说圣经生成可直接执行的章节卡。

### 新增文件

```text
src/ai_novelist/graph_chapter_plan.py
src/ai_novelist/prompts/chapter_goal_agent.md
src/ai_novelist/prompts/chapter_conflict_agent.md
src/ai_novelist/prompts/chapter_hook_agent.md
src/ai_novelist/prompts/chapter_card_synthesizer.md
tests/test_graph_chapter_plan.py
```

### 修改文件

```text
src/ai_novelist/director_service.py
src/ai_novelist/graph_writer.py  # compatibility wrapper if needed
src/ai_novelist/state.py
docs/IMPLEMENTATION_PLAN.md
docs/SESSION_SUMMARY.md
```

### 实现任务

1. 新增 graph：
   ```text
   select_chapter
   load_chapter_context
   chapter_goal_agent
   chapter_conflict_agent
   chapter_hook_agent
   chapter_card_synthesizer
   validate_chapter_card
   save_chapter_card
   ```
2. 输入章节号：
   - 从用户输入解析。
   - 没有则默认 `state.active_chapter`。
3. 使用 `ContextBuilder(purpose="chapter_planning")`。
4. 保存：
   ```text
   chapters/chapter_XXX/chapter_card.md
   ```
5. 写入：
   ```text
   state.current_chapter_card
   state.active_chapter
   ```
6. 注册 artifact。
7. Director 新增：
   ```text
   plan_chapter
   ```
8. 兼容旧：
   ```text
   plan_chapters -> plan_chapter
   ```

### 测试要求

1. mock 下能生成第 1 章 chapter_card。
2. chapter_card 包含必需小节。
3. artifact registry 有记录。
4. 旧 `plan_chapters` action 不报错。

### 验收标准

1. 用户输入“规划第 1 章”生成章节卡。
2. 文件路径正确。
3. pytest 通过。

### 建议提交信息

```text
feat: add chapter planning graph
```

### Codex CLI 提示词

```text
请实现 Phase 6：新增 graph_chapter_plan.py。该图读取 NovelBible、chapter_outline、locked_constraints、reference_brief，通过 ContextBuilder 生成章节卡，保存到 chapters/chapter_XXX/chapter_card.md，写入 state.current_chapter_card 和 active_chapter，并注册 artifact。DirectorService 增加 plan_chapter action，旧 plan_chapters action 作为 alias。新增 prompts 和 tests/test_graph_chapter_plan.py。更新 docs，运行 pytest。
```

---

## 21. Phase 7：Scene Design Graph

### 目标

将章节卡拆成可写作的场景卡，避免正文写散。

### 新增文件

```text
src/ai_novelist/graph_scene.py
src/ai_novelist/prompts/scene_breakdown_agent.md
src/ai_novelist/prompts/scene_conflict_check_agent.md
src/ai_novelist/prompts/scene_synthesizer.md
tests/test_graph_scene.py
```

### 修改文件

```text
src/ai_novelist/director_service.py
src/ai_novelist/state.py
docs/IMPLEMENTATION_PLAN.md
docs/SESSION_SUMMARY.md
```

### 实现任务

1. 新增 graph：
   ```text
   load_chapter_card
   scene_breakdown_agent
   conflict_check_agent
   scene_synthesizer
   validate_scene_cards
   save_scene_cards
   ```
2. 输入：
   ```text
   current_chapter_card
   novel_bible
   style_guide
   locked_constraints
   ```
3. 使用 `ContextBuilder(purpose="scene_design")`。
4. 保存：
   ```text
   chapters/chapter_XXX/scene_cards.md
   ```
5. 写入：
   ```text
   state.current_scene_cards
   ```
6. 注册 artifact。
7. Director 新增：
   ```text
   plan_scenes
   ```

### 验收标准

1. mock 下 scene_cards 至少包含 2 个场景。
2. 每个场景包含：地点、人物、目的、冲突、信息揭示、情绪变化、转折、退出状态。
3. pytest 通过。

### 建议提交信息

```text
feat: add scene design graph
```

### Codex CLI 提示词

```text
请实现 Phase 7：新增 graph_scene.py。该图基于 chapter_card 和 NovelBible 生成 scene_cards.md，每个场景必须包含地点、出场人物、场景目的、人物目标、冲突对象、关键信息、情绪变化、场景转折、退出状态。保存到 chapters/chapter_XXX/scene_cards.md，写入 state.current_scene_cards，并注册 artifact。DirectorService 新增 plan_scenes action。新增 prompts 和 tests/test_graph_scene.py。更新 docs，运行 pytest。
```

---

## 22. Phase 8：Drafting Graph

### 目标

将章节正文写作升级为基于章节卡和场景卡的多节点草稿流程。

### 新增文件

```text
src/ai_novelist/graph_drafting.py
src/ai_novelist/prompts/chapter_writer.md
src/ai_novelist/prompts/dialogue_enhancer.md
src/ai_novelist/prompts/atmosphere_enhancer.md
src/ai_novelist/prompts/hook_enhancer.md
src/ai_novelist/prompts/style_normalizer.md
tests/test_graph_drafting.py
tests/smoke_chapter_pipeline_mock.py
```

### 修改文件

```text
src/ai_novelist/director_service.py
src/ai_novelist/graph_writer.py
src/ai_novelist/state.py
docs/IMPLEMENTATION_PLAN.md
docs/SESSION_SUMMARY.md
```

### 实现任务

1. 新增 graph：
   ```text
   load_drafting_context
   draft_scene_batch
   merge_scenes
   dialogue_enhance
   atmosphere_enhance
   hook_enhance
   style_normalize
   save_draft
   ```
2. `write_chapter` 前置检查：
   - 无 chapter_card：自动运行 `graph_chapter_plan`。
   - 无 scene_cards：自动运行 `graph_scene`。
3. 使用 `ContextBuilder(purpose="drafting")`。
4. 保存：
   ```text
   chapters/chapter_XXX/draft_v1.md
   ```
5. 兼容旧路径：
   ```text
   chapters/chapter_001.md
   ```
   可同步写入。
6. 写入：
   ```text
   state.chapter_draft
   ```
7. 注册 artifact。
8. 修改旧 `graph_writer.py` 中的写作路径，尽量变成 wrapper。

### 验收标准

1. 用户直接输入“写第 1 章”时，如果缺少 chapter_card 和 scene_cards，系统自动补齐。
2. 生成 draft_v1.md。
3. 旧 `write-chapter` 命令仍可用。
4. `smoke_chapter_pipeline_mock.py` 通过。
5. pytest 通过。

### 建议提交信息

```text
feat: add drafting graph with chapter and scene prerequisites
```

### Codex CLI 提示词

```text
请实现 Phase 8：新增 graph_drafting.py，并让旧 write_chapter 路径调用它。Drafting Graph 包含 load_drafting_context、draft_scene_batch、merge_scenes、dialogue_enhance、atmosphere_enhance、hook_enhance、style_normalize、save_draft。write_chapter 如果缺 chapter_card 则先调用 graph_chapter_plan，如果缺 scene_cards 则先调用 graph_scene。保存 draft_v1.md，并兼容旧 chapters/chapter_001.md 路径。写入 state.chapter_draft，注册 artifact。新增 tests/test_graph_drafting.py 和 smoke_chapter_pipeline_mock.py。更新 docs，运行 pytest 和 smoke。
```

---

## 23. Phase 9：Review Graph

### 目标

将单一编辑审稿升级为多编辑审稿，并输出结构化 review report。

### 新增文件

```text
src/ai_novelist/graph_review.py
src/ai_novelist/prompts/continuity_editor.md
src/ai_novelist/prompts/structure_editor.md
src/ai_novelist/prompts/character_arc_editor.md
src/ai_novelist/prompts/style_editor.md
src/ai_novelist/prompts/simulated_reader.md
src/ai_novelist/prompts/review_synthesizer.md
tests/test_graph_review.py
```

### 修改文件

```text
src/ai_novelist/director_service.py
src/ai_novelist/graph_writer.py
src/ai_novelist/state.py
docs/IMPLEMENTATION_PLAN.md
docs/SESSION_SUMMARY.md
```

### 实现任务

1. 新增 graph：
   ```text
   load_review_context
   continuity_review_agent
   structure_review_agent
   character_arc_review_agent
   style_review_agent
   simulated_reader_agent
   review_synthesizer
   decide_pass_or_revise
   save_review_report
   ```
2. 使用 `ContextBuilder(purpose="review")`。
3. 保存：
   ```text
   chapters/chapter_XXX/review_v1.md
   chapters/chapter_XXX/review_v1.json
   ```
4. JSON 必须包含：
   ```text
   decision
   score
   blocking_issues
   issues
   rewrite_tasks
   ```
5. 写入：
   ```text
   state.editor_notes
   state.editor_decision
   state.quality_score
   state.current_review_report
   ```
6. 注册 artifact。
7. Director 新增/映射：
   ```text
   review_chapter
   review -> review_chapter
   ```

### 验收标准

1. mock 下首次 review 可稳定返回 revise 或 pass，按现有测试需要调整。
2. review JSON 可被解析。
3. 旧 `review` action 不报错。
4. pytest 通过。

### 建议提交信息

```text
feat: add multi-editor chapter review graph
```

### Codex CLI 提示词

```text
请实现 Phase 9：新增 graph_review.py，并替代旧 editor review 路径。Review Graph 包含 continuity_review_agent、structure_review_agent、character_arc_review_agent、style_review_agent、simulated_reader_agent、review_synthesizer、decide_pass_or_revise、save_review_report。输出 review_v1.md 和 review_v1.json，JSON 包含 decision、score、blocking_issues、issues、rewrite_tasks。写入 state.editor_notes、state.editor_decision、state.quality_score、state.current_review_report，并注册 artifact。DirectorService 中 review_chapter 和旧 review action 调用该 graph。新增 tests/test_graph_review.py，更新 docs，运行 pytest。
```

---

## 24. Phase 10：Revision Graph

### 目标

让审稿意见驱动局部修订，而不是盲目整章重写。

### 新增文件

```text
src/ai_novelist/graph_revision.py
src/ai_novelist/prompts/revision_planner.md
src/ai_novelist/prompts/targeted_reviser.md
src/ai_novelist/prompts/revision_self_check.md
tests/test_graph_revision.py
```

### 修改文件

```text
src/ai_novelist/director_service.py
src/ai_novelist/graph_writer.py
src/ai_novelist/state.py
docs/IMPLEMENTATION_PLAN.md
docs/SESSION_SUMMARY.md
```

### 实现任务

1. 新增 graph：
   ```text
   load_revision_context
   build_revision_plan
   revise_targeted_sections
   merge_revision
   revision_self_check
   save_revised_draft
   maybe_review_again
   ```
2. 读取：
   ```text
   review_v1.json
   state.editor_notes
   state.chapter_draft
   chapter_card
   scene_cards
   ```
3. 保存：
   ```text
   chapters/chapter_XXX/revision_plan_v1.md
   chapters/chapter_XXX/draft_v2.md
   ```
4. 写入：
   ```text
   state.current_revision_plan
   state.chapter_draft
   state.revision_count += 1
   ```
5. 超过 `max_revisions` 停止并提示用户确认。
6. 注册 artifact。

### 验收标准

1. 有 review_report 时生成 revision_plan。
2. 有 rewrite_tasks 时 draft_v2 包含修订结果。
3. revision_count 正确增加。
4. pytest 通过。

### 建议提交信息

```text
feat: add targeted revision graph
```

### Codex CLI 提示词

```text
请实现 Phase 10：新增 graph_revision.py。该图读取 review_report.json 或 state.editor_notes，生成 revision_plan_v1.md，根据 rewrite_tasks 执行 targeted_reviser，保存 draft_v2.md，revision_count + 1。若 revision_count >= max_revisions，则停止并让 Director 提示用户确认。写入 state.current_revision_plan 和 state.chapter_draft，注册 artifact。DirectorService 中 revise_chapter action 调用该 graph。新增 tests/test_graph_revision.py，更新 docs，运行 pytest。
```

---

## 25. Phase 11：Finalize Chapter + Bible Update

### 目标

章节通过审稿或用户确认后定稿，并把本章事实写回小说圣经。

### 新增/修改文件

```text
src/ai_novelist/graph_bible.py
src/ai_novelist/director_service.py
src/ai_novelist/state.py
tests/test_finalize_chapter.py
tests/smoke_bible_update_mock.py
docs/IMPLEMENTATION_PLAN.md
docs/SESSION_SUMMARY.md
```

### 实现任务

1. 新增流程函数或 graph 节点：
   ```text
   load_latest_draft
   save_final_chapter
   summarize_chapter
   extract_bible_updates_from_final
   update_bible
   save_chapter_summary
   ```
2. 保存：
   ```text
   chapters/chapter_XXX/final.md
   chapters/chapter_XXX/summary.md
   ```
3. 更新 NovelBible：
   ```text
   chapter_summaries
   timeline
   foreshadowing
   character states
   open questions
   ```
4. 更新 state：
   ```text
   state.current_final_chapter
   state.chapter_summaries[str(chapter)]
   state.bible_version
   state.bible_updated_at
   ```
5. 注册 artifact：
   ```text
   final_chapter
   chapter_summary
   novel_bible
   ```
6. Director 新增：
   ```text
   finalize_chapter
   ```
7. 用户输入“定稿第 1 章”可触发。

### 验收标准

1. 定稿后 `final.md` 存在。
2. `summary.md` 存在。
3. NovelBible 更新章节摘要。
4. 下一章 ContextBuilder 能读取上一章摘要。
5. pytest 和 smoke 通过。

### 建议提交信息

```text
feat: finalize chapters and update novel bible
```

### Codex CLI 提示词

```text
请实现 Phase 11：实现 finalize_chapter 流程。若 editor_decision == pass 或用户明确要求定稿，则保存 chapters/chapter_XXX/final.md，生成 summary.md，并调用 graph_bible 更新 timeline、chapter_summaries、character_states、foreshadowing、open_questions。更新 state.current_final_chapter、state.chapter_summaries、bible_version、bible_updated_at，注册 final_chapter、chapter_summary、novel_bible artifacts。DirectorService 新增 finalize_chapter action，用户输入“定稿第 1 章”可触发。新增 tests/test_finalize_chapter.py 和 smoke_bible_update_mock.py。更新 docs，运行 pytest 和 smoke。
```

---

## 26. Phase 12：Export Graph

### 目标

支持导出整卷、整本、小说圣经。

### 新增文件

```text
src/ai_novelist/graph_export.py
tests/test_graph_export.py
```

### 修改文件

```text
src/ai_novelist/director_service.py
src/ai_novelist/cli.py  # 可选，如果要加单步命令
src/ai_novelist/state.py
docs/IMPLEMENTATION_PLAN.md
docs/SESSION_SUMMARY.md
```

### 实现任务

1. 新增 graph：
   ```text
   collect_final_chapters
   normalize_format
   build_manuscript
   build_volume
   copy_bible_export
   save_export
   ```
2. 收集：
   ```text
   chapters/chapter_*/final.md
   ```
3. 按章节号排序。
4. 输出：
   ```text
   exports/manuscript.md
   exports/volume_001.md
   exports/novel_bible.md
   ```
5. Director 新增：
   ```text
   export_project
   ```
6. 用户输入“导出小说”可触发。
7. 如果没有 final 章节，返回明确提示，不崩溃。

### 验收标准

1. 至少一个 final 章节时可导出 manuscript。
2. 没有 final 章节时给提示。
3. pytest 通过。

### 建议提交信息

```text
feat: add manuscript export graph
```

### Codex CLI 提示词

```text
请实现 Phase 12：新增 graph_export.py。该图收集 chapters/chapter_*/final.md，按章节号排序，生成 exports/manuscript.md、exports/volume_001.md，并复制/导出 exports/novel_bible.md。DirectorService 新增 export_project action，用户输入“导出小说”可触发。没有 final 章节时返回明确提示。新增 tests/test_graph_export.py。更新 docs，运行 pytest。
```

---

## 27. Phase 13：Director UX + Full Smoke Workflow

### 目标

把所有新增 graph 串成用户可用的自然语言主流程。

### 新增文件

```text
tests/test_director_prerequisites.py
tests/smoke_full_workflow_mock.py
```

### 修改文件

```text
src/ai_novelist/director_service.py
src/ai_novelist/prompts/director.md
src/ai_novelist/cli.py  # 如需更新 help 文案
README.md
docs/IMPLEMENTATION_PLAN.md
docs/SESSION_SUMMARY.md
```

### 实现任务

1. 完善意图识别：
   ```text
   查看小说圣经 -> show_bible
   更新小说圣经 -> update_bible
   规划第 N 章 -> plan_chapter
   拆第 N 章场景 -> plan_scenes
   写第 N 章 -> write_chapter
   审稿第 N 章 -> review_chapter
   修订第 N 章 -> revise_chapter
   定稿第 N 章 -> finalize_chapter
   导出小说 -> export_project
   ```
2. 完善 `resolve_prerequisites`。
3. 完善用户可见回复：
   - 完成了什么。
   - 生成了哪些产物。
   - 当前状态是什么。
   - 下一步建议是什么。
4. 新增完整 mock smoke：
   ```text
   启动 chat mock
   输入创意
   推进 outline 到 review_lock
   查看 bible
   写第 1 章
   审稿
   修订
   定稿
   导出
   检查关键文件存在
   ```
5. README 更新新能力和产物路径。

### 验收标准

1. `.venv/bin/python -m pytest` 通过。
2. `.venv/bin/python tests/smoke_full_workflow_mock.py` 通过。
3. README 有新工作流说明。
4. 旧 smoke 仍通过，或若更新了路径，文档明确记录原因。

### 建议提交信息

```text
feat: connect full novel workflow through director chat
```

### Codex CLI 提示词

```text
请实现 Phase 13：完善 Director UX 和完整 mock 工作流。更新 DirectorService 和 director prompt，使自然语言命令可路由到 show_bible、update_bible、plan_chapter、plan_scenes、write_chapter、review_chapter、revise_chapter、finalize_chapter、export_project。实现/完善 resolve_prerequisites，让“写第 1 章”可自动补齐 Bible、章节卡、场景卡。新增 tests/test_director_prerequisites.py 和 smoke_full_workflow_mock.py，覆盖从创意、大纲、小说圣经、写章、审稿、修订、定稿到导出的流程。更新 README 和 docs，运行 pytest 和 smoke。
```

---

## 28. 兼容性要求清单

改造完成后，以下命令应继续可用：

```bash
.venv/bin/ai-novelist --help
.venv/bin/ai-novelist chat --project demo-chat --mock
.venv/bin/ai-novelist outline --project demo-outline --idea "小说创意" --mock --auto-approve
.venv/bin/ai-novelist compose --project demo-compose --idea "小说创意" --chapter 1 --mock --auto-approve
.venv/bin/ai-novelist plan-chapters --project demo --mock --auto-approve
.venv/bin/ai-novelist write-chapter --project demo --chapter 1 --mock --auto-approve
.venv/bin/ai-novelist review --project demo --chapter 1 --mock --auto-approve
.venv/bin/ai-novelist show --project demo
```

新增能力可先只通过 `chat` 支持，不一定要马上做单步命令。但如果实现成本低，可以新增：

```bash
.venv/bin/ai-novelist show-bible --project demo
.venv/bin/ai-novelist plan-scenes --project demo --chapter 1 --mock --auto-approve
.venv/bin/ai-novelist finalize-chapter --project demo --chapter 1 --mock --auto-approve
.venv/bin/ai-novelist export --project demo
```

---

## 29. 全局测试计划

### 29.1 Unit tests

必须逐步新增：

```text
tests/test_artifacts.py
tests/test_bible.py
tests/test_context_builder.py
tests/test_graph_bible.py
tests/test_graph_chapter_plan.py
tests/test_graph_scene.py
tests/test_graph_drafting.py
tests/test_graph_review.py
tests/test_graph_revision.py
tests/test_finalize_chapter.py
tests/test_graph_export.py
tests/test_director_prerequisites.py
```

### 29.2 Smoke tests

新增：

```text
tests/smoke_chapter_pipeline_mock.py
tests/smoke_bible_update_mock.py
tests/smoke_full_workflow_mock.py
```

### 29.3 必测场景

1. 从旧 `state.json` 加载，不崩溃。
2. Artifact Registry 空加载，不崩溃。
3. NovelBible 空加载，不崩溃。
4. Outline 从新项目推进到 `done`。
5. `review_lock` 后生成 Bible。
6. 用户直接说“写第 1 章”，自动生成 chapter_card、scene_cards、draft。
7. Review 输出 JSON。
8. Revision 读取 rewrite_tasks，生成 draft_v2。
9. Finalize 保存 final.md 和 summary.md，并更新 Bible。
10. Export 生成 manuscript.md。
11. `--mock` 全流程稳定。
12. 旧 CLI 命令仍可用。

### 29.4 每阶段运行命令

基础：

```bash
.venv/bin/python -m pytest
```

涉及 outline：

```bash
.venv/bin/python tests/smoke_outline_collaboration.py
```

涉及 chat：

```bash
.venv/bin/python tests/smoke_phase2_chat.py
```

涉及章节 pipeline：

```bash
.venv/bin/python tests/smoke_chapter_pipeline_mock.py
```

最终：

```bash
.venv/bin/python tests/smoke_full_workflow_mock.py
```

---

## 30. Mock 输出设计

mock 模式要稳定，不要随机。

建议 mock 内容模板：

### chapter_card mock

```text
# 第 1 章：失忆工程师醒来

## 本章目标
展示主角处境，抛出核心谜团。

## 本章视角人物
主角

## 入场状态
主角在陌生地点醒来，缺失关键记忆。

## 主要冲突
主角想查明自己身份，但外部系统阻止他接触档案。

## 关键事件
1. 主角醒来。
2. 发现异常证据。
3. 遭遇第一个阻碍。

## 新增信息
主角与核心谜团有关。

## 伏笔设置
主角随身物品中出现未知标记。

## 伏笔回收
暂无。

## 人物变化
从迷茫转为主动追查。

## 情绪曲线
困惑 -> 紧张 -> 决心。

## 结尾钩子
主角收到来自“自己”的警告。

## 禁止事项
不得推翻已锁定世界观。

## 预计字数
3000
```

### scene_cards mock

```text
# Scene 1：醒来
...

# Scene 2：调查
...

# Scene 3：警告
...
```

### review JSON mock

```json
{
  "decision": "revise",
  "score": 78,
  "blocking_issues": [],
  "issues": [
    {
      "type": "structure",
      "severity": "medium",
      "location": "Scene 2",
      "problem": "调查过程略快。",
      "suggestion": "增加一个阻碍，让线索获得更有代价。"
    }
  ],
  "rewrite_tasks": [
    {
      "target": "Scene 2",
      "instruction": "增加一次失败尝试，再让主角通过代价获得线索。"
    }
  ]
}
```

---

## 31. 常见风险与处理方案

### 风险 1：state.json 变得过大

处理：

```text
大文本写文件；state 只保存摘要、路径、当前状态。
```

### 风险 2：Agent 上下文污染

处理：

```text
所有 Agent 使用 ContextBuilder，不直接读取全部 messages。
```

### 风险 3：旧测试大量失败

处理：

```text
优先保留旧字段和旧路径。
graph_writer.py 先做 wrapper，不急着删除旧逻辑。
旧 action 通过 alias 映射到新 action。
```

### 风险 4：review JSON 解析失败

处理：

```text
实现 fallback：若无法提取 JSON，则创建保守 review_report：decision=revise，score=60，issues 包含解析失败提示。
```

### 风险 5：Bible merge 误覆盖设定

处理：

```text
merge 层只合并非空字段。
锁定约束不可覆盖。
冲突写入 open_questions 或 conflict report，不直接覆盖。
```

### 风险 6：自动前置步骤导致用户困惑

处理：

```text
Director 返回时说明自动完成了哪些前置步骤，例如“检测到缺少场景卡，已先生成场景卡，再写正文”。
```

---

## 32. Definition of Done

整个全量工作流改造完成的标准：

1. `chat --mock` 能完成：
   ```text
   创意 -> 大纲 -> 小说圣经 -> 第 1 章章节卡 -> 场景卡 -> 草稿 -> 审稿 -> 修订 -> 定稿 -> 导出
   ```
2. 新增产物存在：
   ```text
   artifacts.json
   novel_bible.json
   novel_bible.md
   outline/*.md
   chapters/chapter_001/chapter_card.md
   chapters/chapter_001/scene_cards.md
   chapters/chapter_001/draft_v1.md
   chapters/chapter_001/review_v1.json
   chapters/chapter_001/final.md
   exports/manuscript.md
   ```
3. 旧入口不破坏：
   ```text
   chat
   outline
   compose
   plan-chapters
   write-chapter
   review
   show
   ```
4. 测试通过：
   ```bash
   .venv/bin/python -m pytest
   .venv/bin/python tests/smoke_full_workflow_mock.py
   ```
5. docs 更新完整。
6. 不依赖真实模型也能完成 mock 全流程。
7. 真实模型模式继续沿用现有 provider/adapters，不新增强依赖。

---

## 33. 最终用户体验示例

用户：

```text
我想写一个月球城市失忆工程师的悬疑科幻
```

Director：

```text
进入大纲共创 direction 阶段，生成类型定位、主题卖点和风险建议。
```

用户：

```text
选择方向 1，强化主角罪感，继续
```

Director 自动推进：

```text
concept -> worldbuilding -> characters -> story_flow -> volume_outline -> chapter_outline -> review_lock
```

用户：

```text
查看小说圣经
```

Director：

```text
展示 novel_bible.md 摘要。
```

用户：

```text
写第 1 章
```

Director：

```text
检测到第 1 章缺少章节卡，已生成 chapter_card.md。
检测到第 1 章缺少场景卡，已生成 scene_cards.md。
已生成 draft_v1.md。
```

用户：

```text
让编辑审稿
```

Director：

```text
多编辑审稿完成，decision=revise，score=78。
生成 review_v1.md 和 review_v1.json。
```

用户：

```text
修订
```

Director：

```text
根据 rewrite_tasks 生成 revision_plan_v1.md，并完成 draft_v2.md。
```

用户：

```text
定稿第 1 章
```

Director：

```text
保存 final.md，生成 summary.md，并更新 novel_bible。
```

用户：

```text
导出小说
```

Director：

```text
生成 exports/manuscript.md。
```

---

## 34. 一句话架构总结

```text
LangGraph 负责流程和状态流转；
DirectorService 负责统一调度和用户交互；
NovelState 负责短期运行状态；
Artifact Registry 负责产物版本；
NovelBible 负责长期创作知识；
ContextBuilder 负责让每个 Agent 精准获取所需知识；
各专业 Graph 负责可测试、可复用的创作能力。
```

