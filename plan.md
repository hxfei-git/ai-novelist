# AI Novelist 大纲共创链路重构计划 v3：从未修改仓库出发的 Codex CLI 可执行稿

> 使用方式：把本文整体贴给 Codex CLI。本文假设仓库代码仍是当前 `main` 状态，没有执行过我之前给出的 v1/v2 方案。请 Codex 按本文直接修改代码、提示词、mock、测试和必要文档。不要只做文案替换，也不要只加一个 forbidden phrases 列表。

---

## 0. 你要扮演的角色

你是本仓库 `hxfei-git/ai-novelist` 的代码维护者。你的任务是修复 `chat` 入口中的大纲共创阶段质量问题，尤其是：

1. 方向定位阶段过长、过早写具体代价。
2. `concept` 故事概念阶段与方向定位高度重合，且只有一个 Agent 仍被汇总。
3. 世界观阶段不像世界观，常写成抽象规则、剧情机制、代价说明书。
4. 输出中反复出现公式化绝对因果句，例如“每一次……都会……”“从来不是免费的”“有债必偿”等同类表达。
5. 模型会把用户没提过的设定变成待确认问题，让用户选择模型自造的机制。
6. 现有测试还在固化旧的世界观标题与旧阶段结构。

本次目标不是把用户列举的坏句子逐条硬编码禁止，而是建立可泛化的阶段治理体系。

---

## 1. 当前仓库基线

以当前未改仓库为基准，不要假设前两版计划已经执行。

当前可观察基线：

- README 说明 `chat` 是当前主入口，Director Agent 会在同一项目状态里调度 outline collaboration graph、世界观、章节写手、编辑等子工作流。因此本问题属于主链路治理问题，不是单个输出文案问题。
- `src/ai_novelist/graph_outline.py` 当前活跃阶段仍包含 8 个阶段：`direction`、`concept`、`worldbuilding`、`characters`、`story_flow`、`volume_outline`、`chapter_outline`、`review_lock`。
- `concept` 当前只有 `故事概念 Agent`，但仍走 role agent + synthesizer 的通用阶段汇总流程。
- `worldbuilding` 当前角色偏“规则架构 Agent / 原作或检索一致性 Agent”，输出模板偏“世界运行原则 / 关键边界 / 冲突资源 / 代价红线”。
- `src/ai_novelist/prompts/world_builder.md` 当前也包含“每次选择都会留下后果”这类容易诱导公式句的表达，并维护了“禁止词与高风险表达”词表。
- `tests/test_outline_collaboration.py` 当前仍断言旧世界观标题，例如 `## 世界运行原则`、`## 关键边界`、`## 冲突资源`、`## 代价红线`，这些测试必须改掉，否则会把错误结构继续固化。

---

## 2. 最重要的设计原则

### 2.1 不要把坏例子硬编码成唯一规则

用户列举的坏例子只能作为回归样例，不应作为全部治理策略。

错误做法：

```python
FORBIDDEN = [
    "每一次示弱都是邀请他人掠夺",
    "庇护从来不是免费的",
    "前世记忆有债必偿",
]
```

正确做法：识别这些句子背后的错误类型。

需要识别的错误类型：

1. **阶段越权**：方向阶段提前写世界观代价；世界观阶段提前写剧情流程；人物阶段提前写福利或系统机制。
2. **无来源新设定**：用户没有说、前序未锁定，模型却造出寿元债、羁绊抵押、三宗制衡等具体 canon。
3. **非世界观语言**：把小说世界写成产品规则、编剧机制、数值机制、抽象因果模型。
4. **公式化绝对因果句**：`每一次 / 每次 / 任何 / 一旦 / 凡是 / 只要` + `都会 / 必然 / 必定 / 就会 / 从来 / 永远 / 有债必偿`。
5. **假确认问题**：让用户在模型自造的选项之间选择，例如“前世记忆消耗生命力还是削弱情感纽带”。

### 2.2 区分硬规则与软规则，避免把创作写死

硬规则只约束流程正确性：

- 当前阶段能不能新增具体 canon。
- 具体设定是否有来源。
- 是否越权写了后续阶段。
- 是否把未确认设定写入锁定产物。
- 是否让用户确认模型自造选项。

软规则只约束表达质量：

- 语言不要像产品经理、游戏机制、编剧术语。
- 世界观尽量写成角色能看见、听见、触碰、承受的事物。
- 少用绝对化句式和玄学债务句式。
- 输出不要过长，不要百科堆设定。

不能把以下内容写死：

- 一定是寿元代价或一定不是寿元代价。
- 一定是三宗、一门、一城或几卷几章。
- 所有题材都按仙侠模板输出。
- 所有世界观都必须使用同一组标题。
- 用户明确要求的怪词、黑色幽默或现代制度梗一律删除。

用户显式要求优先。但用户要求的内容也要放在合适阶段，并用小说内部表达承载。

### 2.3 用“三层门”解决问题

本次不要只改 prompt。请建立三层治理：

1. **Stage Contract 阶段契约**：每个阶段定义职责、可新增内容、禁止越权内容、canon policy、建议输出槽位。
2. **Source Ledger 设定来源账本**：具体设定必须来自用户、已锁定阶段、参考简报或当前阶段草案，并标注来源等级。
3. **Quality Gate 质量门**：泛化检测公式句、抽象机制语言、无来源具体设定、假确认问题。

---

## 3. 总体改造结果

### 3.1 新活跃阶段改成 7 个

删除用户可见的独立 `concept` 阶段。新项目活跃阶段为：

```python
ACTIVE_OUTLINE_STAGES = [
    "direction",
    "worldbuilding",
    "characters",
    "story_flow",
    "volume_outline",
    "chapter_outline",
    "review_lock",
]
```

`concept` 不要粗暴删除历史数据，而是作为 legacy 阶段兼容。

### 3.2 `concept` 旧阶段兼容策略

- 新项目不再进入 `concept`。
- `STAGE_LABELS` 可以保留 `concept: "故事概念（旧版）"`，仅用于旧项目显示。
- `STAGE_ROLES` 不再包含 `concept`。
- `OUTLINE_STAGES` 对新流程应等于 7 个 active stages。
- 新增 `LEGACY_OUTLINE_STAGES = {"concept", "outline_draft"}`。
- 若旧 state 的 `outline_stage == "concept"`：
  - 如果 `direction` 已有产物或已锁定，则迁移到 `worldbuilding`。
  - 否则迁移到 `direction`。
- 若旧项目存在 `outline_stage_artifacts["concept"]`：
  - 保留为 legacy artifact，不参与新阶段推进。
  - 最终合并大纲时可作为“旧版故事概念参考”，但不得覆盖新的 `direction`。
- 用户输入“故事概念 / 一句话故事 / 核心概念”时，Director 路由到 `direction`，不是恢复旧 `concept` 阶段。

### 3.3 每个阶段的职责边界

| 阶段 | 核心问题 | 可以新增什么 | 不能新增什么 | 确认问题规则 |
|---|---|---|---|---|
| direction 方向定位 | 这是一个什么故事，读者期待什么 | 类型、主角姿态、核心看点、核心冲突、情绪边界 | 具体代价、门派名、修炼体系、章节桥段、人物小传 | 原则上 0-1 个，只问方向偏好 |
| worldbuilding 世界观 | 这个世界怎样让故事成立 | 力量体系、门派/组织、本门生态、势力理念、日常场景素材 | 章节流程、完整人物小传、结局安排、抽象剧情算法 | 只问影响长期写作的世界缺口 |
| characters 人物关系 | 谁推动冲突，彼此怎样牵制 | 角色目标、秘密、资源、关系张力、主线功能 | 新世界规则、完整剧情流程、福利机制 | 只问角色功能或关系基调 |
| story_flow 故事流程 | 主线怎样推进与升级 | 阶段目标、关键转折、信息释放、伏笔回收方向 | 新门派体系、新人物机制、逐章细纲 | 只问主线走向或终局方向 |
| volume_outline 分卷大纲 | 每卷完成什么变化 | 卷目标、卷矛盾、卷高潮、主角变化、卷间钩子 | 逐章细节、正文场景、临时新 canon | 只问分卷规模或高潮方向 |
| chapter_outline 章节大纲 | 前若干章如何可写 | 章节目标、冲突、信息增量、人物状态变化、钩子 | 正文对白、完整场景卡、新世界规则 | 只问首批章节范围或开篇策略 |
| review_lock 审稿锁定 | 这些设定能否进入写作 | 一致性检查、风险标注、锁定建议 | 新设定、新人物、新剧情重写 | 不问创意题，只问是否锁定或修订 |

---

## 4. 新增模块结构

新增包：

```text
src/ai_novelist/outline/
  __init__.py
  stage_contracts.py
  source_ledger.py
  stage_guard.py
  question_filter.py
  renderers.py
  legacy_migration.py
```

这些模块是建议结构。Codex 可以在保持清晰的前提下调整文件名，但必须实现同等能力，并补测试。

---

## 5. `stage_contracts.py`：阶段契约

新增数据结构：

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

CanonPolicy = Literal[
    "no_new_canon",        # 不允许新增具体 canon，只能写方向原则
    "draft_canon_allowed", # 允许新增草案 canon，但必须能说明来源或用途
    "locked_only",         # 原则上只使用前序已确立设定
    "audit_only",          # 只审计，不新增
]

@dataclass(frozen=True)
class StageSlot:
    key: str
    label: str
    description: str
    required: bool = True
    max_items: int | None = None
    max_chars_per_item: int | None = None

@dataclass(frozen=True)
class StageContract:
    key: str
    label: str
    purpose: str
    canon_policy: CanonPolicy
    allowed_intents: tuple[str, ...]
    forbidden_intents: tuple[str, ...]
    slots: tuple[StageSlot, ...]
    confirmation_policy: str
    max_questions: int = 1
    max_total_chars: int | None = None
```

定义 7 个 active contracts。不要在 contract 中塞固定剧情，只定义语义槽。

### 5.1 direction contract

```python
StageContract(
    key="direction",
    label="方向定位",
    purpose="确定故事类型、主角姿态、读者期待、冲突方向和情绪边界。",
    canon_policy="no_new_canon",
    allowed_intents=(
        "故事类型", "主角行动姿态", "核心看点", "核心冲突方向", "情绪边界", "创作禁区",
    ),
    forbidden_intents=(
        "具体代价形式", "修炼体系", "门派制度", "专有名词清单", "章节桥段", "人物小传",
    ),
    slots=(
        StageSlot("genre", "类型定位", "这是什么类型的故事", True, 1, 60),
        StageSlot("protagonist_stance", "主角姿态", "主角主要如何行动", True, 1, 60),
        StageSlot("reader_payoff", "核心看点", "读者期待的爽点或张力", True, 1, 70),
        StageSlot("central_conflict", "核心冲突", "长期冲突方向", True, 1, 70),
        StageSlot("emotional_boundary", "情绪边界", "作品气质与禁区", True, 1, 70),
    ),
    confirmation_policy="只问方向偏好；不要求确认具体世界机制。",
    max_questions=1,
    max_total_chars=420,
)
```

方向定位允许写：

```text
前世记忆不是万能外挂。
```

方向定位不允许主动写：

```text
每一次动用前世记忆都需付出预支的代价。
前世记忆消耗寿元。
前世记忆会削弱情感纽带。
```

除非用户明确输入这些具体代价，否则方向阶段一律降级为“限制留到世界观或故事流程阶段确认”。

### 5.2 worldbuilding contract

世界观不是“剧情机制说明书”，而是“角色在世界里会实际遇到的规则、组织、资源、场景和压力”。

```python
StageContract(
    key="worldbuilding",
    label="世界观设定",
    purpose="建立支撑故事长期写作的世界内部结构。",
    canon_policy="draft_canon_allowed",
    allowed_intents=(
        "力量或修炼体系", "门派/组织生态", "势力格局与理念", "资源与场景素材", "可持续冲突来源",
    ),
    forbidden_intents=(
        "抽象剧情算法", "代价红线式标题", "人物小传", "章节流程", "结局安排", "产品规则语言",
    ),
    slots=(
        StageSlot("power_system", "力量体系", "修炼/技术/能力如何存在并限制角色", True, 3, 120),
        StageSlot("home_institution", "本门或核心组织", "主角所在门派/组织/城市生态", True, 3, 120),
        StageSlot("factions", "势力与理念", "外部势力、阵营理念或利益冲突", False, 3, 120),
        StageSlot("daily_scenes", "日常场景与素材", "可反复进入章节的地点、任务、仪式、物件", True, 5, 80),
        StageSlot("open_questions", "待确认", "真正影响后续写作的世界缺口", False, 3, 120),
    ),
    confirmation_policy="只问会影响长期写作的世界缺口；不得让用户选择模型自造机制。",
    max_questions=3,
    max_total_chars=1200,
)
```

世界观阶段应尽量写成题材内部表达：

- 仙侠/玄幻：修炼体系、功法、宗门、外门/内门、本门生态、坊市、秘境、执法堂、任务、药园、试炼。
- 科幻：技术基底、城市/空间站制度、机构、资源分配、事故边界、可写场景。
- 都市/悬疑：城市结构、职业生态、关系网络、案件场域、信息流通方式。
- 普通题材：选择 generic profile，不硬套“修炼体系”。

注意：这些是 profile 方向，不是固定模板。validator 只检查语义覆盖，不检查 exact heading。

### 5.3 characters contract

人物阶段不新增世界规则，只建立人物功能。

必须覆盖：

- 主角：目标、缺陷、秘密、资源、底线。
- 关键关系：谁能帮助，谁会牵制，谁会误解，谁可能背叛。
- 反派/对立面：欲望、资源、压迫方式、和主线的关系。
- 每个角色必须有主线功能，不能只是设定装饰。

禁止：

- 福利机制、亲密行为规则、恋爱系统表格。
- 新修炼体系或新门派制度。
- 完整剧情流程。

### 5.4 story_flow contract

故事流程阶段只回答“故事怎样推进”，不新增世界规则。

必须覆盖：

- 开局压力。
- 第一阶段目标与失败风险。
- 中段升级与反转。
- 后段主线冲突显形。
- 终局方向。
- 主要伏笔的布置与回收方向。

禁止：

- 新门派名、新规则名、新系统名。
- 逐章细纲。
- 正文片段。

### 5.5 volume_outline contract

分卷阶段只做卷级结构。

必须覆盖：

- 卷名或卷功能。
- 卷目标。
- 卷内主要矛盾。
- 卷级高潮。
- 主角能力/认知/关系变化。
- 卷间钩子。

禁止：

- 逐章细纲。
- 具体场景动作。
- 临时新增世界规则。

### 5.6 chapter_outline contract

章节大纲阶段只做前若干章可写规划。

必须覆盖：

- 章节编号。
- 章节目标。
- 主要冲突。
- 信息增量。
- 人物状态变化。
- 结尾钩子。
- 连续性提醒。

禁止：

- 正文对白。
- 完整场景卡。
- 新世界规则。

### 5.7 review_lock contract

审稿锁定阶段只做审计。

必须覆盖：

- 阶段承接检查。
- 已锁定 canon 清单。
- 未解决风险。
- 需要回改的阶段。
- 是否可进入章节卡。

禁止：

- 新设定。
- 新人物。
- 新剧情重写。

---

## 6. `source_ledger.py`：设定来源账本

新增来源账本，解决“用户没提却被模型写成 canon”的问题。

### 6.1 来源等级

```python
from dataclasses import dataclass
from enum import Enum

class SourceLevel(str, Enum):
    USER_EXPLICIT = "user_explicit"
    LOCKED_STAGE = "locked_stage"
    REFERENCE_BRIEF = "reference_brief"
    CURRENT_DRAFT = "current_draft"
    MODEL_UNSUPPORTED = "model_unsupported"

@dataclass(frozen=True)
class SourceHit:
    level: SourceLevel
    source: str
    excerpt: str
```

### 6.2 要实现的函数

```python
def build_source_ledger(state: NovelState) -> SourceLedger:
    """收集用户原始输入、最近用户反馈、锁定阶段产物、检索简报、小说圣经。"""

class SourceLedger:
    def has_explicit_source(self, text: str) -> bool: ...
    def find_source(self, text: str) -> SourceHit | None: ...
    def is_user_requested(self, text: str) -> bool: ...
```

实现可以先用保守启发式：

- 将 `state.idea`、`state.user_request`、`state.locked_constraints`、用户消息历史视为用户显式来源。
- 将 `outline_stage_artifacts` 中 `status == "locked"` 的 synthesis、summary、stage_memory 视为锁定来源。
- 将 `reference_brief`、`retrieval_context` 视为参考来源。
- 不要把当前模型刚生成的 role reviews 直接视为已锁定来源。

### 6.3 什么叫“具体 canon”

需要一个启发式函数：

```python
def looks_like_concrete_canon(text: str) -> bool:
    ...
```

它不需要完美，但要能捕捉以下类别：

- 具体代价：寿元、生命力、情感纽带、羁绊、债、魔痕、灵魂、记忆损耗、反噬等。
- 具体组织/地名/体系名：宗、门、堂、阁、司、会、城、院、榜、令、契、册等构成的专名。
- 具体数值规则：次数、阈值、等级、积分、倒计时、不可逆等。
- 具体机制名：以“机制、系统、规则、模型、结构、变量、红线、阈值、抵押”等抽象后缀命名的设定。

注意：这些是类别启发，不是禁止词列表。用户明确要求时允许保留，但要标注来源并放到合适阶段。

---

## 7. `stage_guard.py`：质量门与阶段越权检测

新增统一质量门。方向阶段现有 `sanitize_direction_stage_output` 可以被迁移或委托给它。

### 7.1 数据结构

```python
from dataclasses import dataclass, field

@dataclass
class GuardIssue:
    code: str
    severity: str  # "error" | "warning" | "rewrite"
    message: str
    excerpt: str = ""

@dataclass
class GuardResult:
    text: str
    issues: list[GuardIssue] = field(default_factory=list)
```

### 7.2 入口函数

```python
def guard_stage_output(text: str, stage: str, state: NovelState) -> GuardResult:
    """对阶段产物做非硬编码质量控制。"""
```

内部至少调用：

```python
def detect_stage_overreach(text: str, contract: StageContract) -> list[GuardIssue]: ...
def detect_unsupported_canon(text: str, stage: str, ledger: SourceLedger) -> list[GuardIssue]: ...
def detect_formulaic_causality(text: str) -> list[GuardIssue]: ...
def detect_non_worldbuilding_language(text: str, stage: str) -> list[GuardIssue]: ...
def rewrite_or_demote_issues(text: str, issues: list[GuardIssue], stage: str, ledger: SourceLedger) -> str: ...
```

### 7.3 公式化绝对因果检测

不要只检测“每一次示弱都是邀请他人掠夺”这一句。检测结构：

```python
UNIVERSAL_MARKERS = (
    "每一次", "每次", "任何", "所有", "一旦", "只要", "凡是", "无论",
)
INEVITABILITY_MARKERS = (
    "必然", "必定", "都会", "就会", "从来", "永远", "注定", "有债必偿",
)
```

如果同一句里同时出现 universal marker 和 inevitability marker，视为 `formulaic_absolute_causality`。

这不是硬性删掉所有“每次”。如果用户明确要求这种誓言式或讽刺式表达，可以保留在正文风格中；但大纲阶段产物里默认应改写为更具体、可写的表述。

示例改写策略：

- 原：`每一次示弱都是邀请他人掠夺。`
- 改：`外门弟子一旦暴露软弱，容易被同门盯上资源和任务名额。`

- 原：`庇护从来不是免费的。`
- 改：`强者给出的庇护通常会附带差事、人情或把柄。`

- 原：`前世记忆有债必偿。`
- 改：`前世记忆可能不完整，且会因今生行动改变而失准；是否存在明确代价留待确认。`

重点：改写为“世界内可观察后果”，而不是玄学绝对句。

### 7.4 抽象机制语言检测

不要维护一个无限扩张的词表，而是检测语言形态。

高风险语言形态：

- 以“机制、系统、模型、结构、变量、阈值、红线、优先级、抵押、债务、闭环、反馈”构造设定名。
- “X 即 Y”“X 从来不是 Y”“X 有债必偿”“X 不是免费的”这类口号化标题句。
- “每条边界如何制造冲突 / 代价”如果被模型复述为抽象说明，而非世界内物件、组织、事件、日常压力。

在 `worldbuilding` 阶段，抽象机制语言要改成：

- 组织行为。
- 修炼限制。
- 场景素材。
- 资源分配。
- 人情、任务、把柄、名声、生死风险。

### 7.5 方向阶段具体代价降级

方向阶段 `canon_policy="no_new_canon"`，因此：

- 用户未明确要求的具体代价形式，全部降级为“限制留待世界观或故事流程阶段确认”。
- 如果模型写了寿元、生命力、情感纽带、羁绊债、魔痕、不可逆阈值等，但 ledger 找不到用户来源，必须删除或替换。

替换句建议：

```text
前世记忆不是万能外挂，具体限制留到世界观或故事流程阶段确认。
```

### 7.6 世界观阶段具体设定处理

世界观阶段允许 draft canon，但必须满足其一：

1. 来自用户显式输入。
2. 来自已锁定方向或参考简报。
3. 是为支撑主线必要的草案，并且表述为“可调整草案”或“待确认”。

用户没提“前世记忆代价”时，世界观可以写：

```text
待确认：是否需要为前世记忆设置明确限制；若暂不确认，只按“记忆不完整且会因今生行动改变而失准”处理。
```

不可以直接写：

```text
前世记忆消耗寿元。
前世记忆削弱情感纽带。
前世记忆有债必偿。
```

---

## 8. `question_filter.py`：确认问题过滤

新增函数：

```python
def filter_stage_confirmation_questions(
    stage: str,
    questions: list[str],
    state: NovelState,
    synthesis: str = "",
) -> list[str]:
    ...
```

### 8.1 过滤规则

1. 超出阶段职责的问题删除。
2. 要求用户选择模型自造具体选项的问题删除或改写。
3. 不允许把模型刚生成的机制当成用户需要确认的前提。
4. 每阶段问题数不超过 contract.max_questions。
5. 如果没有真正影响后续写作的缺口，返回空列表。

### 8.2 假确认问题示例

错误：

```text
前世记忆的代价形式更倾向“消耗生命力”还是“削弱情感纽带”？
```

如果用户没有提过这两个选项，改成：

```text
是否需要为前世记忆设置明确限制？如果暂不确认，将按“记忆不完整且会因行动改变而失准”保守处理。
```

或者在方向阶段直接删除，因为方向阶段不应确认世界机制。

错误：

```text
本门更像血煞宗、炼魂宗还是魅影宗？
```

如果这些宗门名是模型自造，改成：

```text
本门气质更偏残酷武力、诡秘术法，还是权谋秩序？
```

这类问题问的是风格方向，不把自造专名变 canon。

---

## 9. `renderers.py`：阶段渲染，不把模板写死

新增渲染层，负责生成 prompt 的输出规则。validator 不应该依赖 exact heading。

### 9.1 题材 profile

新增：

```python
@dataclass(frozen=True)
class GenreProfile:
    key: str
    signals: tuple[str, ...]
    worldbuilding_slots: tuple[StageSlot, ...]
    style_hint: str
```

至少支持：

- `xianxia`：修仙、仙侠、玄幻、魔门、宗门、灵根、筑基、功法、飞升。
- `scifi`：科幻、星舰、月球、火星、AI、工程师、空间站、殖民地。
- `urban_suspense`：都市、刑侦、悬疑、记者、警察、公司、医院、学校。
- `fantasy`：奇幻、骑士、王国、魔法、公会、神明。
- `historical`：古代、朝堂、江湖、王府、县衙、书院。
- `generic`：无法判断时使用通用世界观槽位。

### 9.2 仙侠世界观默认槽位

当 idea 或方向中包含魔门、修炼、宗门等信号时，世界观默认建议槽位为：

```md
## 世界观设定稿

### 修炼与力量体系
### 门派与本门生态
### 势力格局与理念冲突
### 日常场景与可写素材
### 待确认
```

这不是硬模板。Codex 实现时应让 prompt 表达为“默认建议结构，可按题材改名”，测试也不要断言必须完全相同标题，只检查不再出现旧标题，并覆盖语义。

### 9.3 非仙侠世界观槽位示例

科幻默认：

```md
### 技术与生存条件
### 城市/机构生态
### 资源与权限分配
### 日常场景与事故素材
### 待确认
```

都市悬疑默认：

```md
### 城市与职业生态
### 信息流通方式
### 机构与灰色地带
### 案件场景与可写素材
### 待确认
```

通用默认：

```md
### 世界基本样貌
### 角色所在组织或生活圈
### 资源、压力与行动限制
### 可反复使用的场景素材
### 待确认
```

---

## 10. 修改 `graph_outline.py`

### 10.1 阶段列表

把当前：

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
]
```

改为：

```python
ACTIVE_OUTLINE_STAGES = [
    "direction",
    "worldbuilding",
    "characters",
    "story_flow",
    "volume_outline",
    "chapter_outline",
    "review_lock",
]

OUTLINE_STAGES = ACTIVE_OUTLINE_STAGES
LEGACY_OUTLINE_STAGES = {"concept", "outline_draft"}
```

### 10.2 labels

保留 legacy label：

```python
STAGE_LABELS = {
    "direction": "方向定位",
    "concept": "故事概念（旧版）",
    "worldbuilding": "世界观设定",
    ...
}
```

但 `concept` 不得出现在 `OUTLINE_STAGES` 或 `STAGE_ROLES`。

### 10.3 roles

修改：

```python
STAGE_ROLES = {
    "direction": ["类型定位 Agent", "卖点边界 Agent"],
    "worldbuilding": ["题材世界观 Agent", "组织生态 Agent", "可写素材 Agent"],
    "characters": ["主角弧光 Agent", "关系冲突 Agent", "反派/势力 Agent"],
    "story_flow": ["主线结构 Agent", "节奏悬念 Agent", "伏笔 Agent"],
    "volume_outline": ["分卷策划 Agent", "卷内高潮 Agent", "卷间钩子 Agent"],
    "chapter_outline": ["章节拆分 Agent", "章节钩子 Agent", "连续性编辑 Agent"],
    "review_lock": ["总编辑 Agent", "约束审计 Agent", "章节准备 Agent"],
}
```

### 10.4 `ensure_outline_stage`

确保：

- 如果 `state.outline_stage` 不在 active stages：
  - `concept` 按旧阶段策略迁移。
  - `outline_draft` 映射到 `volume_outline`。
  - 其他非法值回到 `direction`。
- 不要让新项目进入 `concept`。

伪代码：

```python
def ensure_outline_stage(state: NovelState) -> None:
    normalize_legacy_outline_artifacts(state)
    if state.outline_stage == "concept":
        direction = state.outline_stage_artifacts.get("direction")
        if isinstance(direction, dict) and direction.get("synthesis"):
            state.outline_stage = "worldbuilding"
        else:
            state.outline_stage = "direction"
    elif state.outline_stage == "outline_draft":
        state.outline_stage = "volume_outline"
    elif state.outline_stage not in OUTLINE_STAGES and state.outline_stage != "done":
        state.outline_stage = "direction"
    if not state.outline_stage_status:
        state.outline_stage_status = "collecting"
```

### 10.5 `run_outline_stage_node`

当前流程中，synthesizer 输出后只对 `direction` 做了特殊 sanitize。改为统一：

```python
result = guard_stage_output(synthesis, stage, state)
synthesis = result.text
questions = extract_stage_confirmation_questions(synthesis)
questions = filter_stage_confirmation_questions(stage, questions, state, synthesis)
```

不要只对 `direction` 清洗。世界观、人物、流程也需要质量门。

### 10.6 `build_outline_stage_role_prompt`

把 `role_focus_instruction`、`outline_stage_boundary_prompt`、`worldbuilding_overfine_terms_guard` 逐步改为读取 `StageContract`。

角色短评 prompt 必须包含：

```text
STAGE_CONTRACT:
- 本阶段目的：...
- 允许新增：...
- 禁止越权：...
- Canon policy：...
- 所有具体设定必须说明来源，不能把自造机制写成已锁定事实。

LANGUAGE_QUALITY:
- 不写公式化绝对因果句。
- 不写产品规则、游戏机制、编剧理论语言。
- 世界观阶段多写角色能看见、听见、触碰、承受的事物。
```

### 10.7 `build_outline_stage_synthesizer_prompt`

改为通过 `renderers.build_stage_output_rule(stage, state)` 生成阶段输出规则。

不要再在 worldbuilding 的 output rule 中输出：

```text
## 世界运行原则
## 关键边界
## 冲突资源
## 代价红线
```

这些只能作为回归测试里的坏样例，不应进入 prompt。

### 10.8 `outline_stage_synthesizer_output_rule`

如果保留该函数，则其内部委托给新 renderer：

```python
def outline_stage_synthesizer_output_rule(stage: str, state: NovelState | None = None) -> str:
    return build_stage_output_rule(stage, state)
```

如果很多测试还直接调用它，可以给 `state=None` 的兼容逻辑，但不要恢复旧 concept/worldbuilding 模板。

### 10.9 `next_outline_stage`、`stage_number`、`finalize_locked_outline`

全部使用 active 7 阶段。

所有用户可见文案从“八阶段”改为“七阶段”或“全部阶段”。

### 10.10 stage reference 检测

如果用户说“故事概念”，映射到 `direction`，并给出内部 intent 为 `concept_request`，不要把 `state.outline_stage` 设为 `concept`。

---

## 11. 修改 `director_service.py`

当前 `persist_outputs` 分支存在一个高风险逻辑：如果 `decision.task_args["stage"]` 指向下一阶段，代码可能先把 `state.outline_stage` 改成 requested stage，再调用 `advance_outline_stage_node`，导致用户确认上一阶段时实际锁定下一阶段。

修复原则：

- `advance_current_stage` / `persist_outputs` 的语义永远是“锁定当前阶段并进入下一阶段”。
- 不要在调用 `advance_outline_stage_node` 前用 `task_args["stage"]` 覆盖 `state.outline_stage`。
- `task_args["stage"]` 只用于 show/revise/switch，不用于 advance 当前阶段。
- 如果模型返回 `task_args.stage == next_outline_stage(state.outline_stage)`，说明它想表达“进入下一阶段”，应忽略该 stage 参数，继续锁定当前阶段。
- 如果模型返回 `task_args.stage` 是早先阶段，且 intent 是修订，则走 revise/switch，不走 persist。

建议修改：

```python
elif decision.action == "persist_outputs":
    if state.active_workflow == "outline" and state.outline_stage != "done" and not state.outline.strip():
        from ai_novelist.graph_outline import advance_outline_stage_node
        # 不要在这里根据 decision.task_args["stage"] 改写 state.outline_stage。
        result_state = NovelState.from_dict(
            advance_outline_stage_node(state.to_dict(), self.adapter, self.store, self.progress or noop_progress)
        )
    else:
        result_state = NovelState.from_dict(persist_available_outputs(state.to_dict(), self.store))
```

为这个 bug 加测试。

---

## 12. 修改 `world_builder.md`

`src/ai_novelist/prompts/world_builder.md` 是独立世界观 Agent 的 prompt，也要和 outline worldbuilding 阶段统一。

### 12.1 删除或改写诱导公式句的表达

把当前类似：

```text
为什么每次选择都会留下后果
```

改为：

```text
说明世界如何让角色的选择产生可被看见、可被追踪、可被后续章节利用的后果。
```

避免诱导“每次/每一次……都会……”句式。

### 12.2 不再以“禁止词与高风险表达”词表作为核心策略

可以保留“语言质量提醒”，但不要让 prompt 变成无限扩展的坏词表。

改成分类说明：

```md
## 语言质量要求

不要把世界观写成产品规则、游戏机制、编剧理论或抽象算法。
高风险写法包括：
- 用“机制/阈值/变量/红线/模型/系统”命名设定。
- 用“每一次/每次/任何/一旦 + 必然/都会/从来/永远”写绝对因果。
- 把情感、人情、庇护、代价写成数学规则或玄学债务。

如果需要表达类似含义，请改写成角色能在世界中实际遇到的组织行为、任务、人情、把柄、伤病、资源损失、名声风险或生死威胁。
```

### 12.3 输出格式改成题材自适应

不要所有题材都输出“主线相关背景边界 / 世界里的压力源 / 禁忌与后果”。

建议输出：

```md
## 世界观设定稿

### 世界一句话

### 题材核心结构
根据题材选择：修炼与力量体系 / 技术与生存条件 / 城市与职业生态 / 世界基本样貌。

### 主角所在组织或生活圈

### 势力、资源与日常压力

### 可持续写作素材

### 待确认事项

### 自检
```

对于仙侠/魔门题材，明确建议写：

- 修炼与力量体系。
- 门派与本门生态。
- 势力格局与理念冲突。
- 日常场景与可写素材。
- 待确认。

---

## 13. 修改 mock 输出

查找 mock adapter 或测试 mock 中关于 outline stage 的输出，确保它不再生成：

- `concept` 阶段。
- `## 世界运行原则`、`## 关键边界`、`## 冲突资源`、`## 代价红线`。
- `每一次...都会...`、`每次...都会...`、`庇护从来不是免费的`、`有债必偿` 等同类绝对因果句。

mock 方向阶段建议输出：

```md
## 方向定位稿
- 类型定位：重生魔门苟道成长，暗线带生死智斗。
- 主角姿态：低调藏锋，优先求生，再守住身边温情。
- 核心看点：用前世经验避险破局，但不写成全知外挂。
- 核心冲突：魔门求生逻辑与守护他人的选择互相撕扯。
- 情绪边界：残酷底色中保留轻松日常和微弱温情。
```

mock 世界观阶段建议输出：

```md
## 世界观设定稿

### 修炼与力量体系
- 外门弟子靠残卷、药材和师承入门，功法来路决定他们能走多远。
- 魔功见效快，但气息难藏，主角越想低调越要避开公开试炼。

### 门派与本门生态
- 本门外门像一座小江湖，执事、长老、弟子之间靠任务、药材和人情牵连。
- 执法堂不主持公道，只维护本门脸面，主角不能靠喊冤解决危机。

### 势力格局与理念冲突
- 魔门讲结果，正道讲名义，两边都可能把底层弟子当成消耗品。

### 日常场景与可写素材
- 功房残卷、药园夜巡、山门黑市、外门小比、执法堂问案。

### 待确认
- 是否需要为前世记忆设置明确限制；若暂不确认，只按“记忆不完整且会因今生行动改变而失准”处理。
```

注意：这只是 mock 样例，不是强制所有真实输出完全照抄。

---

## 14. 测试修改与新增

### 14.1 修改旧测试

修改 `tests/test_outline_collaboration.py`。

删除或替换以下断言：

```python
assert "## 故事概念稿" in concept_prompt
assert "## 世界运行原则" in world_prompt
assert "## 关键边界" in synth_prompt
assert "## 冲突资源" in synth_prompt
assert "## 代价红线" in synth_prompt
assert "6-8 条" in synth_prompt
assert "每条不超过 100 中文字符" in synth_prompt
assert "最多列 3 个阵营或资源冲突点" in synth_prompt
```

替换为：

```python
def test_active_outline_stages_exclude_concept():
    assert "concept" not in OUTLINE_STAGES
    assert OUTLINE_STAGES == [
        "direction",
        "worldbuilding",
        "characters",
        "story_flow",
        "volume_outline",
        "chapter_outline",
        "review_lock",
    ]


def test_worldbuilding_prompt_uses_genre_worldbuilding_slots():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门底层弟子，苟道藏锋")
    prompt = build_outline_stage_synthesizer_prompt(state, "worldbuilding", [])
    assert "世界观设定" in prompt
    assert any(term in prompt for term in ("修炼", "力量体系", "门派", "本门", "组织生态"))
    assert "可写素材" in prompt or "日常场景" in prompt
    for old in ("## 世界运行原则", "## 关键边界", "## 冲突资源", "## 代价红线"):
        assert old not in prompt
```

### 14.2 新增阶段契约测试

新建或扩展测试：

```python
def test_stage_contracts_have_active_stages_only():
    from ai_novelist.outline.stage_contracts import get_stage_contract
    for stage in OUTLINE_STAGES:
        contract = get_stage_contract(stage)
        assert contract.key == stage
        assert contract.purpose
        assert contract.slots
    with pytest.raises(KeyError):
        get_stage_contract("concept")
```

或如果实现选择兼容返回 legacy contract，则断言：

```python
assert get_stage_contract("concept").key == "direction"
```

二者选一，保持实现一致。

### 14.3 新增方向阶段清洗测试

```python
def test_direction_guard_demotes_unsupported_concrete_memory_cost():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门底层弟子，苟道藏锋")
    text = "## 方向定位稿\n- 每一次动用前世记忆都需付出预支的代价，可能消耗生命力。"
    result = guard_stage_output(text, "direction", state)
    assert "每一次" not in result.text
    assert "消耗生命力" not in result.text
    assert "前世记忆不是万能外挂" in result.text or "具体限制留" in result.text


def test_direction_guard_preserves_user_explicit_cost_at_high_level():
    state = NovelState(project_id="demo", title="Demo", idea="主角用前世记忆会消耗寿命")
    text = "## 方向定位稿\n- 前世记忆会消耗寿命，所以主角不能滥用。"
    result = guard_stage_output(text, "direction", state)
    # 用户明确要求时不应无脑删掉，但方向阶段仍应避免细则化。
    assert "寿命" in result.text or "具体限制留" in result.text
```

### 14.4 新增公式化句式测试

```python
@pytest.mark.parametrize("bad", [
    "每一次示弱都是邀请他人掠夺。",
    "每次动用都会招来新的敌人。",
    "凡是求稳必然付出代价。",
    "一旦保护别人就会被世界收债。",
])
def test_formulaic_causality_detection_is_pattern_based(bad):
    issues = detect_formulaic_causality(bad)
    assert any(issue.code == "formulaic_absolute_causality" for issue in issues)
```

这组测试包含用户列举过的，也包含新句式，证明不是硬编码。

### 14.5 新增世界观语言测试

```python
def test_worldbuilding_guard_rejects_abstract_mechanism_language():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门底层弟子")
    text = "## 世界观设定稿\n## 代价红线\n前世记忆有债必偿，情感变量超过阈值会触发羁绊抵押。"
    result = guard_stage_output(text, "worldbuilding", state)
    for bad in ("代价红线", "有债必偿", "情感变量", "阈值", "羁绊抵押"):
        assert bad not in result.text
    assert "待确认" in result.text or "世界" in result.text
```

注意：这里可以把用户列举的词作为 fixture，但实现不能只靠这些词。

### 14.6 新增确认问题过滤测试

```python
def test_question_filter_removes_model_invented_choice_menu():
    state = NovelState(project_id="demo", title="Demo", idea="重生魔门底层弟子，苟道藏锋")
    questions = ["前世记忆的代价形式更倾向消耗生命力还是削弱情感纽带？"]
    filtered = filter_stage_confirmation_questions("worldbuilding", questions, state)
    assert len(filtered) <= 1
    assert not any("消耗生命力" in q and "削弱情感纽带" in q for q in filtered)
    assert filtered == [] or "是否需要为前世记忆设置明确限制" in filtered[0]
```

### 14.7 新增 Director 推进测试

确保确认当前阶段时不会锁错下一阶段。

伪代码：

```python
def test_persist_outputs_advances_current_stage_not_requested_next_stage(tmp_path):
    # 构造 state：active_workflow outline，outline_stage direction，direction artifact 已生成。
    # 模拟 DirectorDecision(action="persist_outputs", task_args={"stage": "worldbuilding"})。
    # 执行 handle_turn 或内部执行函数。
    # 断言 direction 被 locked，state.outline_stage == "worldbuilding"。
    # 断言 worldbuilding 没有被错误标记 locked。
```

### 14.8 新增 legacy concept 测试

```python
def test_legacy_concept_stage_migrates_without_entering_active_flow():
    state = NovelState(project_id="demo", title="Demo", idea="旧项目")
    state.outline_stage = "concept"
    state.outline_stage_artifacts["concept"] = {
        "stage": "concept",
        "label": "故事概念",
        "status": "locked",
        "synthesis": "旧版故事概念。",
    }
    ensure_outline_stage(state)
    assert state.outline_stage in {"direction", "worldbuilding"}
    assert "concept" not in OUTLINE_STAGES
```

### 14.9 smoke 测试

更新 smoke：

```bash
.venv/bin/python -m pytest
.venv/bin/python tests/smoke_phase2_chat.py
.venv/bin/python tests/smoke_outline_collaboration.py
```

如果环境无法执行全部 smoke，至少执行相关单元测试并在最终说明无法执行的原因。

---

## 15. 验收标准

### 15.1 行为验收

1. 新项目开始大纲共创时，第一阶段为 `direction`。
2. 锁定 direction 后，下一个阶段为 `worldbuilding`，中间不出现 `concept`。
3. 旧项目存在 `concept` artifact 不崩溃，但新流程不进入 concept。
4. `STAGE_ROLES` 不包含 `concept`。
5. `stage_number("worldbuilding") == 2`。
6. 最终合并大纲只按 7 个 active stages 排序。
7. 用户确认“进入下一阶段”时，系统锁定当前阶段，而不是先切到下一阶段再锁。
8. `worldbuild` 独立命令和 outline worldbuilding prompt 风格一致，不再鼓励“每次选择都会留下后果”。

### 15.2 质量验收

使用创意：

```text
重生魔门底层弟子，苟道藏锋，守护师姐师妹
```

方向阶段应接近：

```md
## 方向定位稿
- 类型定位：重生魔门苟道成长，暗线带生死智斗。
- 主角姿态：低调藏锋，优先求生，再守住身边温情。
- 核心看点：用前世经验避险破局，但不写成全知外挂。
- 核心冲突：魔门求生逻辑与守护他人的选择互相撕扯。
- 情绪边界：残酷底色中保留轻松日常和微弱温情。
```

方向阶段不应出现：

```text
每一次动用前世记忆都需付出预支的代价
消耗生命力
削弱情感纽带
寿元债
羁绊抵押
不可逆阈值
```

除非这些内容来自用户明确输入。

世界观阶段应接近：

```md
## 世界观设定稿

### 修炼与力量体系
- 外门弟子靠残卷、药材和师承入门，功法来路决定他们能走多远。
- 魔功见效快，但气息难藏，主角越想低调越要避开公开试炼。

### 门派与本门生态
- 本门外门像一座小江湖，执事、长老、弟子之间靠任务、药材和人情牵连。
- 执法堂不主持公道，只维护本门脸面，主角不能靠喊冤解决危机。

### 势力格局与理念冲突
- 魔门讲结果，正道讲名义，两边都可能把底层弟子当成消耗品。

### 日常场景与可写素材
- 功房残卷、药园夜巡、山门黑市、外门小比、执法堂问案。

### 待确认
- 是否需要为前世记忆设置明确限制；若暂不确认，只按“记忆不完整且会因今生行动改变而失准”处理。
```

世界观阶段不应默认出现旧结构：

```text
世界运行原则
关键边界
冲突资源
代价红线
情感变量
寿元债
羁绊抵押
不可逆阈值
```

但请注意：这里的不应出现是验收样例，不是鼓励你只把这些词写进黑名单。真正要通过的是泛化质量门。

---

## 16. 具体提交步骤建议

请按以下顺序实现，降低回归风险。

### Step 1：新增 outline 包与 stage contracts

- 新增 `src/ai_novelist/outline/__init__.py`。
- 新增 `stage_contracts.py`，定义 active stages 和 contracts。
- 修改 `graph_outline.py` 使用 active stages。
- 先跑相关 import 测试。

### Step 2：删除 active concept，保留 legacy

- 从 `OUTLINE_STAGES` 和 `STAGE_ROLES` 删除 `concept`。
- 修改 `ensure_outline_stage`、`detect_stage_reference`、`next_outline_stage`、`stage_number`。
- 新增 legacy migration 测试。

### Step 3：接入 source ledger 与 stage guard

- 新增 `source_ledger.py`。
- 新增 `stage_guard.py`。
- 在 `run_outline_stage_node` 中调用 `guard_stage_output`。
- 让原 `sanitize_direction_stage_output` 委托给 `guard_stage_output`，或保留兼容 wrapper。

### Step 4：接入 question filter

- 新增 `question_filter.py`。
- 在 `extract_stage_confirmation_questions` 后调用 filter。
- 修改 `stage_ready_message`，当没有问题时只要求确认锁定或继续修改。

### Step 5：改世界观 renderer 与 prompts

- 新增 `renderers.py`。
- 修改 `outline_stage_synthesizer_output_rule`。
- 修改 `role_focus_instruction` 或相关边界 prompt。
- 修改 `world_builder.md`。

### Step 6：修复 Director 阶段推进 bug

- 修改 `director_service.py` 的 `persist_outputs` 分支。
- 新增测试防止确认时锁错阶段。

### Step 7：更新 mock 与测试

- 更新 mock 输出。
- 删除旧标题断言。
- 新增上述测试。
- 跑 `pytest`。

---

## 17. 不要做的事情

1. 不要只新增 `FORBIDDEN_PHRASES`。
2. 不要把用户列举的坏句子逐条硬编码为唯一禁止项。
3. 不要为了通过测试把所有题材都锁死成仙侠模板。
4. 不要删除旧项目 `concept` artifact 导致旧 state 崩溃。
5. 不要让 validator 断言 exact heading；应检查语义覆盖。
6. 不要让世界观阶段继续写成“世界运行原则 / 关键边界 / 冲突资源 / 代价红线”。
7. 不要让方向阶段主动发明寿元、情感、羁绊、债务等具体代价。
8. 不要让确认问题继承模型自造选项。
9. 不要把用户明确要求的内容误删；应标注来源并放到合适阶段。
10. 不要只改 prompt，不改测试和 mock。

---

## 18. 最终交付说明格式

修改完成后，请 Codex 输出：

```md
## 修改完成

### 关键改动
- ...

### 新增文件
- ...

### 修改文件
- ...

### 测试结果
- `pytest ...`：通过/失败
- 如果有失败，说明失败原因和下一步。

### 验收样例
- direction 输出摘要：...
- worldbuilding 输出摘要：...
```

不要只回复“已完成”。