# AI Novelist `story_flow` 生成整改计划（Codex CLI 执行版）

> 目标：把 `story_flow.md` 从“少量剧情阶段摘要”整改为“可支撑全书规划、分卷大纲、章节大纲的故事流程蓝图”。
>
> 使用方式：在 `ai-novelist` 仓库根目录，把本文件作为 Codex CLI 的执行任务上下文。Codex 需要逐项修改代码、补充测试、运行验证，并在最终汇报中给出变更文件、测试结果和前后对比。

---

## 0. 执行原则

1. **不要只改 Prompt**：当前问题不是单个提示词不够详细，而是 `story_flow` 的阶段契约、角色分工、框架注入、结构校验、后处理修复和测试都不完整。必须系统整改。
2. **不要把 `story_flow` 做成章节大纲**：它应当给 `volume_outline` 和 `chapter_outline` 提供骨架，但本身不直接拆章。
3. **不要硬造未锁定设定**：凡是 `direction`、`worldbuilding`、`characters` 没有锁定的信息，只能写成“候选方向 / 待确认 / 可选方案”，不能伪装成既定正典。
4. **保留现有项目风格**：先阅读现有代码结构、命名习惯、测试风格，再实现。下面给的是目标和建议实现路径，若现有代码有更合适的组织方式，可以在不降低验收标准的前提下调整。
5. **一切以可验证产物为准**：整改完成后，至少要通过单元测试和一次故事流程生成/结构修复的集成式验证。

---

## 1. 当前问题诊断

### 1.1 产物层问题

当前 `demo-chat/outline/story_flow.md` 更像一个短摘要，主要围绕这些小节输出：

- 开局压力
- 中段升级
- 后段冲突显形
- 终局方向
- 伏笔布置与回收方向
- 仍需确认的问题

这会导致以下问题：

1. **主线因果链不完整**：没有明确“故事起点 → 引发事件 → 初始目标 → 阶段性目标升级 → 终局目标”。
2. **阶段功能不清楚**：没有把开局、成长、扩张、转折、高潮、结局各自承担的叙事功能讲清楚。
3. **冲突升级不够**：缺少“个人困境 → 组织/阵营冲突 → 制度/规则冲突 → 终极价值冲突”的升级路径。
4. **人物弧光没有嵌入流程**：`characters` 里即使有人物成长，也没有说明这些变化如何被剧情事件推动。
5. **爽点、情绪、伏笔、反转节奏缺位**：后续分卷和章节生成会缺少连续抓手。
6. **结局路径过早模糊**：没有提前规定终局问题、世界变化、人物归宿和主题落点，中后期容易散。

### 1.2 代码层问题

需要重点检查并整改以下位置：

- `src/ai_novelist/outline/stage_contracts.py`
  - `story_flow` 的 `StageContract` 当前槽位太少。
  - `allowed_intents` 太窄。
  - `max_total_chars` 过低，不足以承载全书级流程蓝图。

- `src/ai_novelist/graph_outline.py`
  - `STAGE_ROLES["story_flow"]` 当前角色覆盖不足，缺少冲突升级、人物弧光、爽点情绪、终局回收等视角。
  - 已有 `worldbuilding`、`characters` 类框架注入思路，但 `story_flow` 缺少同等级框架。
  - 运行阶段有世界观/人物等结构化后处理，但缺少 `story_flow` 专属结构修复。
  - `outline_stage_synthesizer_output_rule` 或同类输出规则没有强制 `story_flow` 必含完整结构。

- `tests/`
  - 需要补充 `story_flow` 合同、框架渲染、结构修复、集成保存等测试。

---

## 2. 目标产物规格

整改后，`outline/story_flow.md` 应当成为“故事流程稿”，默认包含以下 14 个一级内容块。标题可根据项目现有风格加 `##` 或 `###`，但测试建议采用稳定标题，便于结构校验。

### 2.1 必须包含的 14 个模块

1. **故事主线推进**
   - 故事起点
   - 引发事件
   - 主角初始目标
   - 主线任务 / 主线问题
   - 阶段性目标变化
   - 终局目标

2. **故事阶段划分**
   - 开局阶段
   - 成长阶段
   - 扩张阶段
   - 转折阶段
   - 高潮阶段
   - 结局阶段

3. **核心冲突升级路径**
   - 初级冲突
   - 中级冲突
   - 高级冲突
   - 终极冲突
   - 每阶段敌人、升级方式、胜利代价、失败损失、成长推动

4. **关键剧情节点**
   - 开篇钩子
   - 第一次选择
   - 第一次胜利
   - 第一次失败
   - 中段大转折
   - 黑暗时刻
   - 最终觉醒
   - 终局对决
   - 结局回响

5. **人物弧光嵌入流程**
   - 主角起点缺陷、误解、欲望、恐惧
   - 每阶段学会什么、失去什么、改变什么
   - 关键人物如何推动、诱惑、阻止或唤醒主角
   - 关系变化流程
   - 反派与主角镜像关系
   - 终局人物状态

6. **伏笔、悬念与揭示节奏**
   - 核心悬念
   - 阶段性悬念
   - 伏笔布置点
   - 真相揭示顺序
   - 表层真相、第一层反转、第二层反转、深层真相、终极真相

7. **爽点 / 卖点兑现节奏**
   - 开局卖点
   - 阶段性爽点
   - 升级型爽点
   - 情绪释放点
   - 卖点与主线结合方式

8. **情绪节奏与阅读体验**
   - 整体情绪曲线
   - 阶段情绪目标
   - 高低起伏安排
   - 章节 / 分卷节奏参考

9. **世界观展开顺序**
   - 开局展示哪些设定
   - 中期扩展哪些设定
   - 后期揭示哪些底层秘密
   - 设定展示方式
   - 世界观与主角命运的关系

10. **阵营与势力推进**
    - 各阵营登场顺序
    - 阵营关系变化
    - 主角阵营位置变化
    - 阵营冲突如何推动主线

11. **代价与失败机制**
    - 能力代价
    - 选择代价
    - 关系代价
    - 世界代价
    - 必败节点与后果

12. **反转与认知升级**
    - 反转位置
    - 反转类型：身份、阵营、目标、规则、真相、情感
    - 反转后的剧情影响
    - 反转与前文伏笔的对应关系

13. **分卷衔接方向**
    - 每卷承担的故事功能
    - 每卷核心问题
    - 每卷阶段性高潮
    - 卷与卷之间的钩子

14. **结局路径**
    - 主线结局
    - 人物结局
    - 关系结局
    - 世界结局
    - 主题落点
    - 余味 / 续作空间

### 2.2 可选模块

15. **仍需确认的问题**
   - 只记录真正会影响流程设计的待确认项。
   - 不要把已能从前序阶段推导的问题重复问用户。
   - 最多 3 个问题。

---

## 3. 针对当前 demo 故事的流程建议

> 这一节不是要求硬编码进系统，而是给 Codex 在修复 demo 输出和测试用例时参考。若前序正典未锁定，应写成“候选”。

当前 demo 的核心方向大致是：重生到魔门、谨慎苟活、利用前世记忆获得先手感、轻松日常与暗线危机形成反差、保护身边重要人物并慢慢变强。`story_flow` 应将这些卖点转成逐步升级的全书结构。

### 3.1 推荐主线因果链

- **故事起点**：主角重生为魔门底层弟子，表面上只是想避开前世死局、稳住日常，与师姐/师妹维系小院生活。
- **引发事件**：前世记忆中的关键危险提前或变形出现，例如差事分派、药田/矿坑异常、外院清洗、某个师妹命运改变。
- **初始目标**：苟住、避祸、保护眼前人，不主动卷入魔门权力斗争。
- **主线问题**：主角能否在“魔门规则、前世记忆失准、寿元/资源债、正魔阵营暗斗”的夹缝中，保护重要关系并改写死局？
- **目标升级**：
  - 求生避祸
  - 保护小院与亲近之人
  - 夺取局部规则解释权
  - 识破前世记忆背后的更大局
  - 改写吞噬弱者的底层规则
- **终局目标**：不只是活下来，而是在付出代价后建立一种新的选择空间，让主角和重要人物不再只能被宗门/阵营/寿元债推着走。

### 3.2 推荐阶段划分

1. **开局阶段：入魔门与立卖点**
   - 重点：重生先手、谨慎苟活、日常反差、第一次避坑。
   - 需要立即兑现读者期待：主角利用前世记忆规避一次危机，同时发现今世已有细节偏差。

2. **成长阶段：小院、差事与局部副本**
   - 重点：药田、矿坑、外门任务、低阶资源争夺、小反派压迫。
   - 目标：让读者理解魔门生存玩法，看到主角不是无脑爽，而是靠信息差、谨慎选择和关系经营取胜。

3. **扩张阶段：阵营浮现与地图扩大**
   - 重点：外院/内门/圣女/长老/正道势力/地下交易等陆续登场。
   - 目标：把冲突从个人生存升级为组织和阵营结构问题。

4. **转折阶段：前世记忆失准与关系破裂**
   - 重点：一次主角以为必胜的选择失败，导致亲近者受伤、误解或分离。
   - 目标：推翻“只靠前世记忆就能赢”的安全感。

5. **高潮阶段：规则真相与最终选择**
   - 重点：寿元债、宗门资源体系、正魔双方共同掩盖的规则真相显形。
   - 目标：主角必须在复仇/救人/保全自身/改变规则之间做不可兼得的选择。

6. **结局阶段：有限胜利与新秩序余味**
   - 重点：主线问题得到回答，关键关系落定，世界格局改变但不必完美。
   - 目标：回应开头“苟活”的动机，让主角最终从“只想活下去的人”变成“愿意承担代价改变局面的人”。

### 3.3 推荐冲突升级路径

- **初级冲突**：差事、资源、外门欺压、低阶敌人。
- **中级冲突**：执事、内门派系、圣女线、宗门任务、正道追查。
- **高级冲突**：宗门制度、寿元债、资源献祭、前世记忆被操控或不完整。
- **终极冲突**：自由选择 vs 被规则吞噬；保护个人关系 vs 改写世界代价。

### 3.4 推荐反转层级

- **表层真相**：主角以为自己只是重生避祸。
- **第一层反转**：今世危险并非简单复刻前世，敌人和事件顺序发生偏移。
- **第二层反转**：身边重要人物与核心秘密有关，不只是被保护对象。
- **深层真相**：魔门规则与正道秩序可能共享同一套剥削/献祭逻辑。
- **终极真相**：主角的前世记忆本身可能是某种规则漏洞、诱饵或代价的一部分，必须决定是否继续利用它。

---

## 4. 代码整改步骤

### 4.1 建立分支并跑基线

在仓库根目录执行：

```bash
git checkout -b fix/story-flow-framework
python -m compileall src tests
python -m pytest tests/test_outline_stage_controls.py tests/test_outline_collaboration.py tests/test_output_contracts.py
```

记录当前失败/通过情况。如果已有测试失败，不要先大改，先确认失败与本次需求是否相关。

同时查看当前关键文件：

```bash
sed -n '1,260p' src/ai_novelist/outline/stage_contracts.py
sed -n '1,260p' src/ai_novelist/graph_outline.py
grep -R "story_flow" -n src tests | head -80
sed -n '1,220p' demo-chat/outline/story_flow.md
```

---

### 4.2 扩展 `story_flow` 阶段契约

文件：`src/ai_novelist/outline/stage_contracts.py`

找到 `story_flow` 的 `StageContract`，将其改成能承载 14 个核心模块。

#### 4.2.1 建议 intent

将 `allowed_intents` 扩展为：

```python
allowed_intents=(
    "故事起点",
    "引发事件",
    "主线问题",
    "阶段目标",
    "终局目标",
    "阶段划分",
    "冲突升级",
    "关键剧情节点",
    "人物弧光嵌入",
    "关系变化流程",
    "反派镜像",
    "伏笔悬念",
    "揭示节奏",
    "爽点兑现",
    "情绪节奏",
    "世界观展开",
    "阵营推进",
    "失败代价",
    "反转认知",
    "分卷衔接",
    "结局路径",
)
```

如果项目约定 intent 使用更短词，可保留短词，但必须覆盖以上语义。

#### 4.2.2 建议 slots

将 `slots` 扩展为类似以下结构。字段名按项目现有 `StageSlot` 构造函数调整，不要机械复制导致类型错误。

```python
slots=(
    StageSlot(
        "mainline_progression",
        "故事主线推进",
        "说明故事起点、引发事件、主角初始目标、主线问题、阶段性目标升级与终局目标。",
        True,
        6,
        180,
    ),
    StageSlot(
        "stage_map",
        "故事阶段划分",
        "按开局、成长、扩张、转折、高潮、结局说明每阶段功能、核心事件类型、阶段出口。",
        True,
        6,
        220,
    ),
    StageSlot(
        "conflict_escalation",
        "核心冲突升级路径",
        "从个人困境升级到组织/阵营、制度/规则、终极价值矛盾，并标注敌人、代价和成长作用。",
        True,
        4,
        220,
    ),
    StageSlot(
        "key_plot_nodes",
        "关键剧情节点",
        "规划开篇钩子、第一次选择、第一次胜利、第一次失败、中段大转折、黑暗时刻、最终觉醒、终局对决、结局回响。",
        True,
        9,
        160,
    ),
    StageSlot(
        "character_arc_embedding",
        "人物弧光嵌入流程",
        "说明主角缺陷与欲望如何被剧情推动变化，关键人物如何影响主角，重要关系如何变化，反派如何镜像主角。",
        True,
        6,
        220,
    ),
    StageSlot(
        "foreshadowing_reveal_cadence",
        "伏笔、悬念与揭示节奏",
        "定义核心悬念、阶段悬念、伏笔布置点、真相分层揭示顺序与回收方向。",
        True,
        6,
        220,
    ),
    StageSlot(
        "payoff_promise_cadence",
        "爽点 / 卖点兑现节奏",
        "承接 direction 的核心卖点和故事承诺，安排开局卖点、阶段爽点、升级爽点、情绪释放点。",
        True,
        5,
        200,
    ),
    StageSlot(
        "emotional_pacing",
        "情绪节奏与阅读体验",
        "规划整体情绪曲线、阶段情绪目标、高低起伏、缓冲与爆发、分卷节奏倾向。",
        True,
        5,
        200,
    ),
    StageSlot(
        "worldbuilding_reveal_order",
        "世界观展开顺序",
        "说明世界规则、地图、历史、力量体系、底层秘密如何随剧情逐步展示。",
        True,
        5,
        200,
    ),
    StageSlot(
        "faction_progression",
        "阵营与势力推进",
        "规划势力登场顺序、关系变化、主角阵营位置变化、势力冲突如何压迫选择。",
        True,
        5,
        200,
    ),
    StageSlot(
        "cost_failure_mechanism",
        "代价与失败机制",
        "规定能力代价、选择代价、关系代价、世界代价、必败节点与后果。",
        True,
        5,
        200,
    ),
    StageSlot(
        "reversals_cognition",
        "反转与认知升级",
        "规划开局、中段、后期、终局的身份/阵营/目标/规则/真相/情感反转，以及反转后的剧情影响。",
        True,
        5,
        200,
    ),
    StageSlot(
        "volume_bridge_direction",
        "分卷衔接方向",
        "为后续 volume_outline 提供骨架：每卷功能、核心问题、阶段高潮、卷尾钩子。不是章节大纲。",
        True,
        5,
        180,
    ),
    StageSlot(
        "ending_path",
        "结局路径",
        "提前规划主线、人物、关系、世界、主题和余味/续作空间的结局方向。",
        True,
        6,
        200,
    ),
)
```

#### 4.2.3 字数与问题数

- 将 `max_total_chars` 从当前过低值提高到 **6500～9000**，或设为 `None` 后交给输出规则控制。
- `max_questions` 建议为 `3`。
- `confirmation_prompt` 要明确询问“主线阶段、终局方向、核心代价、反转尺度”这类高价值问题，而不是笼统询问。

示例：

```python
confirmation_prompt=(
    "请确认故事流程中的主线目标升级、核心失败代价、关键反转尺度、终局选择是否符合预期；"
    "若有未锁定设定，请标为候选而不是写成正典。"
)
```

---

### 4.3 新增 `story_flow` 框架文件

建议新增文件：`src/ai_novelist/story_flow_framework.py`

目的：像世界观/人物框架一样，将 `story_flow` 的结构要求稳定注入到角色 Agent 和 Synthesizer Prompt 中。

#### 4.3.1 建议实现

```python
"""Framework prompt for the story_flow outline stage."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StoryFlowSection:
    key: str
    heading: str
    purpose: str
    required_points: tuple[str, ...]


STORY_FLOW_SECTIONS: tuple[StoryFlowSection, ...] = (
    StoryFlowSection(
        "mainline_progression",
        "故事主线推进",
        "描述整部小说最核心的因果链。",
        ("故事起点", "引发事件", "主角初始目标", "主线任务 / 主线问题", "阶段性目标变化", "终局目标"),
    ),
    StoryFlowSection(
        "stage_map",
        "故事阶段划分",
        "把整部故事拆成大的流程阶段，而不是直接拆章节。",
        ("开局阶段", "成长阶段", "扩张阶段", "转折阶段", "高潮阶段", "结局阶段"),
    ),
    StoryFlowSection(
        "conflict_escalation",
        "核心冲突升级路径",
        "规划冲突如何越来越大、越来越难、越来越贴近主题。",
        ("初级冲突", "中级冲突", "高级冲突", "终极冲突", "胜利代价", "失败损失"),
    ),
    StoryFlowSection(
        "key_plot_nodes",
        "关键剧情节点",
        "记录全书级别的重要节点。",
        ("开篇钩子", "第一次选择", "第一次胜利", "第一次失败", "中段大转折", "黑暗时刻", "最终觉醒", "终局对决", "结局回响"),
    ),
    StoryFlowSection(
        "character_arc_embedding",
        "人物弧光嵌入流程",
        "说明人物变化如何被剧情事件推动。",
        ("主角起点状态", "成长路径", "关键人物影响", "关系变化流程", "反派镜像", "终局人物状态"),
    ),
    StoryFlowSection(
        "foreshadowing_reveal_cadence",
        "伏笔、悬念与揭示节奏",
        "安排信息释放，避免前期没钩子、后期硬反转。",
        ("核心悬念", "阶段性悬念", "伏笔布置点", "真相揭示顺序", "分层反转"),
    ),
    StoryFlowSection(
        "payoff_promise_cadence",
        "爽点 / 卖点兑现节奏",
        "承接核心卖点和故事承诺，规划持续兑现与升级。",
        ("开局卖点", "阶段性爽点", "升级型爽点", "情绪释放点", "卖点与主线结合"),
    ),
    StoryFlowSection(
        "emotional_pacing",
        "情绪节奏与阅读体验",
        "规划读者情绪，而不只是事件顺序。",
        ("整体情绪曲线", "阶段情绪目标", "高低起伏", "缓冲与爆发", "分卷节奏参考"),
    ),
    StoryFlowSection(
        "worldbuilding_reveal_order",
        "世界观展开顺序",
        "说明静态设定如何逐步进入读者视野。",
        ("开局展示", "中期扩展", "后期揭示", "展示方式", "与主角命运关系"),
    ),
    StoryFlowSection(
        "faction_progression",
        "阵营与势力推进",
        "规划组织、宗门、家族、国家、神明、AI 等势力如何登场和冲突。",
        ("登场顺序", "关系变化", "主角位置变化", "势力冲突推动选择"),
    ),
    StoryFlowSection(
        "cost_failure_mechanism",
        "代价与失败机制",
        "防止主角一路平推，让胜利和成长都有成本。",
        ("能力代价", "选择代价", "关系代价", "世界代价", "失败节点"),
    ),
    StoryFlowSection(
        "reversals_cognition",
        "反转与认知升级",
        "将 concept 中的反转原则落到流程位置。",
        ("反转位置", "反转类型", "反转后影响", "前文伏笔对应"),
    ),
    StoryFlowSection(
        "volume_bridge_direction",
        "分卷衔接方向",
        "为 volume_outline 提供骨架，而不是替代分卷大纲。",
        ("每卷功能", "每卷核心问题", "阶段性高潮", "卷间钩子"),
    ),
    StoryFlowSection(
        "ending_path",
        "结局路径",
        "提前约束终局，避免中后期发散。",
        ("主线结局", "人物结局", "关系结局", "世界结局", "主题落点", "余味 / 续作空间"),
    ),
)


def story_flow_required_headings() -> tuple[str, ...]:
    return tuple(section.heading for section in STORY_FLOW_SECTIONS)


def render_story_flow_framework() -> str:
    lines: list[str] = [
        "【story_flow 阶段强制框架】",
        "本阶段产物是全书级故事流程蓝图，不是章节大纲，也不是分卷细纲。",
        "必须承接 direction、worldbuilding、characters 已锁定内容；未锁定内容只能写为候选/待确认。",
        "必须覆盖以下模块：",
    ]
    for index, section in enumerate(STORY_FLOW_SECTIONS, start=1):
        points = "、".join(section.required_points)
        lines.append(f"{index}. {section.heading}：{section.purpose} 必含：{points}。")
    lines.extend(
        [
            "写作边界：",
            "- 不要直接写章节正文。",
            "- 不要生成逐章列表。",
            "- 不要新增与 worldbuilding 冲突的世界规则。",
            "- 不要新增与 characters 冲突的人物终局。",
            "- 每个模块都要说明它如何推动主线、人物、冲突或阅读体验。",
            "- 缺失信息请标为候选方向或待确认问题。",
        ]
    )
    return "\n".join(lines)
```

如项目已有框架文件命名规范，请按规范调整。

---

### 4.4 将 `story_flow` 框架注入 Prompt

文件：`src/ai_novelist/graph_outline.py`

#### 4.4.1 引入框架函数

在 import 区域增加：

```python
from .story_flow_framework import render_story_flow_framework, story_flow_required_headings
```

根据实际包结构调整相对路径。

#### 4.4.2 新增框架 Prompt 函数

如果现有代码已有 `worldbuilding_framework_prompt(stage)`、`characters_framework_prompt(stage)` 这类函数，新增同类函数：

```python
def story_flow_framework_prompt(stage: str) -> str:
    if stage != "story_flow":
        return ""
    return render_story_flow_framework()
```

#### 4.4.3 注入角色 Agent Prompt

找到 `build_outline_stage_role_prompt`。在已有世界观/人物框架注入处加入：

```python
story_flow_framework = story_flow_framework_prompt(stage)
```

并在 prompt 文本中放入：

```text
{story_flow_framework}
```

放置位置建议：

1. 阶段契约之后；
2. stage boundary 之前或之后均可，但要保证模型能看到；
3. role focus 之前也可以，让角色视角围绕完整框架展开。

#### 4.4.4 注入 Synthesizer Prompt

找到 `build_outline_stage_synthesizer_prompt`。同样加入：

```python
story_flow_framework = story_flow_framework_prompt(stage)
```

并在综合提示中注入。Synthesizer 必须比单个 Agent 更明确地看到完整结构，否则各角色意见可能被压缩成短摘要。

---

### 4.5 扩展 `story_flow` 角色分工

文件：`src/ai_novelist/graph_outline.py`

找到 `STAGE_ROLES` 或同类配置。将 `story_flow` 从少量角色扩展为：

```python
"story_flow": [
    "主线结构 Agent",
    "冲突升级 Agent",
    "人物弧光 Agent",
    "悬念伏笔 Agent",
    "爽点情绪 Agent",
    "终局回收 Agent",
]
```

然后在 `role_focus_instruction` 或同类函数中补充每个角色的职责。

建议文本：

```python
if role == "主线结构 Agent":
    return "重点检查故事起点、引发事件、初始目标、主线问题、目标升级、终局目标是否形成清晰因果链。"
if role == "冲突升级 Agent":
    return "重点检查冲突是否从个人困境升级到组织阵营、制度规则和终极价值矛盾，并记录胜利代价与失败损失。"
if role == "人物弧光 Agent":
    return "重点检查主角和关键人物的变化如何被剧情推动，关系链如何变化，反派是否形成镜像。"
if role == "悬念伏笔 Agent":
    return "重点检查核心悬念、阶段悬念、伏笔布置和真相揭示顺序，避免硬反转。"
if role == "爽点情绪 Agent":
    return "重点检查核心卖点如何在各阶段持续升级兑现，以及紧张、爽感、心疼、燃、满足等情绪节奏。"
if role == "终局回收 Agent":
    return "重点检查终局是否回答主线问题、回收人物关系与伏笔，并为分卷衔接和结局路径提供稳定骨架。"
```

如果现有函数用映射表，按映射表风格实现。

---

### 4.6 更新阶段边界 `OUTLINE_STAGE_BOUNDARIES`

文件：`src/ai_novelist/graph_outline.py`

找到 `OUTLINE_STAGE_BOUNDARIES["story_flow"]` 或同类配置。调整为：

#### 允许内容

- 全书主线因果链
- 故事阶段划分
- 阶段目标升级
- 冲突升级路径
- 关键剧情节点
- 人物弧光嵌入流程
- 关系变化流程
- 伏笔、悬念、揭示节奏
- 爽点/卖点兑现节奏
- 情绪节奏
- 世界观展开顺序
- 阵营与势力推进
- 代价与失败机制
- 反转与认知升级
- 分卷衔接方向
- 结局路径
- 待确认问题

#### 禁止内容

- 直接写章节正文
- 逐章拆解章节清单
- 替代 `volume_outline` 输出完整分卷细纲
- 新增与 `worldbuilding` 冲突的世界规则
- 新增与 `characters` 冲突的人物设定
- 无来源地把候选内容写成已锁定正典
- 只输出模板标题，不填充实际内容

---

### 4.7 强化 Synthesizer 输出规则

搜索：

```bash
grep -R "outline_stage_synthesizer_output_rule" -n src
```

或查找生成阶段最终稿的 Prompt 函数。

增加 `story_flow` 专属规则：

```python
if stage == "story_flow":
    return """
输出必须以 `## 故事流程稿` 开始。
必须包含以下二级标题，且不得遗漏：
1. 故事主线推进
2. 故事阶段划分
3. 核心冲突升级路径
4. 关键剧情节点
5. 人物弧光嵌入流程
6. 伏笔、悬念与揭示节奏
7. 爽点 / 卖点兑现节奏
8. 情绪节奏与阅读体验
9. 世界观展开顺序
10. 阵营与势力推进
11. 代价与失败机制
12. 反转与认知升级
13. 分卷衔接方向
14. 结局路径
可选：仍需确认的问题。

每个必填标题下必须有具体、可执行的内容，不能只有空泛概念。
允许使用简洁表格，但不要输出逐章列表，不要写正文。
必须承接 direction、worldbuilding、characters 已锁定内容；未锁定信息写成候选或待确认。
"""
```

注意：如果项目中用英文 key 或模板系统，请保持项目风格。

---

### 4.8 新增 `story_flow` 结构校验与修复

建议新增文件：`src/ai_novelist/outline/story_flow_structure.py`

目的：即使模型输出偷懒或遗漏，也能在保存前修复为完整结构。

#### 4.8.1 必需功能

实现以下函数：

```python
STORY_FLOW_REQUIRED_HEADINGS: tuple[str, ...]
normalize_heading(text: str) -> str
extract_markdown_sections(text: str) -> dict[str, str]
missing_story_flow_headings(text: str) -> list[str]
has_nonempty_story_flow_section(text: str, heading: str) -> bool
ensure_story_flow_outline_structure(...)
```

#### 4.8.2 校验规则

`story_flow` 合格标准：

1. 含 `## 故事流程稿` 或同级主标题。
2. 14 个必需模块都存在。
3. 每个模块下至少有非空内容。
4. 总体内容不能明显短小，建议中文字符数不低于 2500；实际阈值可按测试和项目设定调整。
5. 不得只复述标题。
6. 不得出现逐章正文。
7. 如果有未知信息，必须出现“候选 / 待确认 / 未锁定”等标记，而不是硬编。

#### 4.8.3 修复策略

建议采用两层修复：

1. **模型修复**：如果缺失模块较多、内容明显过短、结构不完整，调用 LLM 一次，要求按完整框架重写。
2. **确定性兜底**：如果模型修复后仍缺少少量标题，追加保守小节，写明“待确认 / 候选方向”，避免保存不合格结构。

伪代码：

```python
def ensure_story_flow_outline_structure(
    synthesis: str,
    *,
    adapter,
    project_context: str,
    direction_text: str,
    worldbuilding_text: str,
    characters_text: str,
    role_outputs: list[str] | None = None,
) -> str:
    missing = missing_story_flow_headings(synthesis)
    too_short = count_cjk_chars(synthesis) < 2500
    empty_sections = [h for h in STORY_FLOW_REQUIRED_HEADINGS if not has_nonempty_story_flow_section(synthesis, h)]

    if not missing and not too_short and not empty_sections:
        return synthesis

    repair_prompt = build_story_flow_repair_prompt(
        synthesis=synthesis,
        missing=missing,
        empty_sections=empty_sections,
        project_context=project_context,
        direction_text=direction_text,
        worldbuilding_text=worldbuilding_text,
        characters_text=characters_text,
        role_outputs=role_outputs,
    )
    repaired = adapter.complete(repair_prompt)

    if is_valid_story_flow(repaired):
        return repaired

    return append_missing_story_flow_sections(repaired)
```

根据现有 adapter 接口调整调用方式，可能是 `complete_with_metrics` 而不是 `complete`。

#### 4.8.4 修复 Prompt 要点

修复 Prompt 必须强调：

- 这是全书级流程稿，不是章节大纲。
- 必须保留原文中有价值内容。
- 必须承接前序阶段。
- 不得凭空新增硬设定。
- 缺失模块必须补齐。
- 输出完整 Markdown，而不是解释修改理由。

示例核心文本：

```text
你正在修复 story_flow 阶段输出。当前输出结构不完整。
请在不写章节正文、不替代分卷大纲的前提下，重写为完整故事流程稿。
必须包含 14 个标题：...
请承接 direction/worldbuilding/characters 的已锁定内容。
未锁定信息只能写为“候选方向”或“待确认”。
保留当前草稿中有价值的剧情方向。
只输出修复后的 Markdown。
```

---

### 4.9 在运行节点接入结构修复

文件：`src/ai_novelist/graph_outline.py`

找到阶段输出保存前的逻辑，通常在 `run_outline_stage_node` 或同类函数中。当前可能已有：

```python
if stage == "worldbuilding":
    synthesis = ensure_worldbuilding_outline_structure(...)
elif stage == "characters":
    synthesis = ensure_characters_outline_structure(...)
```

增加：

```python
elif stage == "story_flow":
    synthesis = ensure_story_flow_outline_structure(
        synthesis,
        adapter=adapter,
        project_context=project_context,
        direction_text=previous_stage_texts.get("direction", ""),
        worldbuilding_text=previous_stage_texts.get("worldbuilding", ""),
        characters_text=previous_stage_texts.get("characters", ""),
        role_outputs=role_outputs,
    )
```

实际变量名按现有代码调整。关键是：修复必须发生在保存 `outline/story_flow.md` 之前。

---

### 4.10 更新阶段摘要与记忆

检查生成 `stage_memory`、`summary`、`project_memory` 的逻辑。`story_flow` 完整后，后续 `volume_outline` 应能读取到以下关键信息：

- 主线问题
- 阶段划分
- 阶段性目标升级
- 冲突升级路径
- 关键节点
- 主要伏笔与揭示顺序
- 分卷衔接方向
- 结局路径

如果当前摘要只抽取很短内容，需要为 `story_flow` 增加专门摘要提示或摘要规则。

建议摘要格式：

```markdown
## story_flow 摘要
- 主线问题：...
- 目标升级：求生 → ... → 终局目标
- 阶段骨架：开局 / 成长 / 扩张 / 转折 / 高潮 / 结局
- 冲突升级：个人 → 阵营 → 规则 → 终极价值
- 关键转折：...
- 分卷衔接：...
- 结局路径：...
```

---

## 5. 测试计划

### 5.1 新增测试：阶段契约

文件：`tests/test_story_flow_contract.py`

测试点：

1. `story_flow` contract 存在。
2. 必需 slot 数量不少于 14。
3. slot 标题或描述覆盖 14 个模块。
4. `allowed_intents` 覆盖主线、阶段、冲突、人物、伏笔、爽点、情绪、世界观、阵营、代价、反转、分卷、结局。
5. `max_total_chars` 不再是 1200 这种短摘要限制。

示例断言：

```python
def test_story_flow_contract_has_full_framework():
    contract = STAGE_CONTRACTS["story_flow"]
    labels = "\n".join(slot.label for slot in contract.slots)
    for heading in [
        "故事主线推进",
        "故事阶段划分",
        "核心冲突升级路径",
        "关键剧情节点",
        "人物弧光嵌入流程",
        "伏笔、悬念与揭示节奏",
        "爽点",
        "情绪节奏",
        "世界观展开顺序",
        "阵营与势力推进",
        "代价与失败机制",
        "反转与认知升级",
        "分卷衔接方向",
        "结局路径",
    ]:
        assert heading in labels
    assert contract.max_total_chars is None or contract.max_total_chars >= 6500
```

按实际字段名调整。

---

### 5.2 新增测试：框架渲染

文件：`tests/test_story_flow_framework.py`

测试点：

1. `render_story_flow_framework()` 包含 14 个模块。
2. 包含禁止项：不写章节正文、不生成逐章列表、不硬造未锁定设定。
3. `story_flow_required_headings()` 返回 14 个稳定标题。

示例：

```python
def test_story_flow_framework_renders_required_headings():
    text = render_story_flow_framework()
    for heading in story_flow_required_headings():
        assert heading in text
    assert "不是章节大纲" in text
    assert "未锁定" in text
```

---

### 5.3 新增测试：结构修复

文件：`tests/test_story_flow_structure.py`

测试输入使用当前旧格式的短输出，例如：

```markdown
## 故事流程稿
### 开局压力
主角在魔门外院谨慎求生。
### 中段升级
药田和矿坑牵出更大的宗门压力。
### 后段冲突显形
圣女线与寿元债浮出水面。
### 终局方向
主角尝试保护身边人。
### 伏笔布置与回收方向
前世记忆出现偏差。
```

测试点：

1. `missing_story_flow_headings` 能识别缺失模块。
2. `ensure_story_flow_outline_structure` 使用假 adapter 修复后包含 14 个模块。
3. 假 adapter 若仍漏标题，确定性兜底能补齐。
4. 不把候选设定写成强正典。

建议用 stub adapter：

```python
class StubAdapter:
    def complete_with_metrics(self, *args, **kwargs):
        return "...完整 story_flow markdown...", {}
```

按真实 adapter 接口调整。

---

### 5.4 更新现有测试

检查并更新以下测试中可能写死旧结构的断言：

- `tests/test_outline_stage_controls.py`
- `tests/test_outline_collaboration.py`
- `tests/test_output_contracts.py`

如果测试断言 `story_flow` 只有旧 slots 或旧角色，应改为新结构。

---

### 5.5 集成式验证

补充或更新一个集成测试：

1. 使用 mock/stub 模型输出一个不完整的 `story_flow`。
2. 运行 `story_flow` 阶段节点。
3. 断言保存到 `outline/story_flow.md` 的内容包含 14 个模块。
4. 断言 artifact registry 中注册了 `story_flow` 产物。
5. 断言后续阶段上下文能读到 `story_flow` 摘要。

---

## 6. 推荐文件变更清单

预期至少修改或新增这些文件：

```text
src/ai_novelist/outline/stage_contracts.py
src/ai_novelist/story_flow_framework.py
src/ai_novelist/outline/story_flow_structure.py
src/ai_novelist/graph_outline.py
tests/test_story_flow_contract.py
tests/test_story_flow_framework.py
tests/test_story_flow_structure.py
```

可能需要同步修改：

```text
tests/test_outline_stage_controls.py
tests/test_outline_collaboration.py
tests/test_output_contracts.py
```

不要修改：

```text
.env
*.key
用户私密配置
模型 API Key
```

---

## 7. 验收标准

### 7.1 代码验收

执行：

```bash
python -m compileall src tests
python -m pytest tests/test_story_flow_contract.py tests/test_story_flow_framework.py tests/test_story_flow_structure.py
python -m pytest tests/test_outline_stage_controls.py tests/test_outline_collaboration.py tests/test_output_contracts.py
```

全部通过，或者若有与本次变更无关的历史失败，必须在最终汇报中明确说明。

### 7.2 产物验收

生成或修复后的 `outline/story_flow.md` 必须满足：

1. 以 `## 故事流程稿` 或同等标题开始。
2. 包含 14 个必需模块：
   - 故事主线推进
   - 故事阶段划分
   - 核心冲突升级路径
   - 关键剧情节点
   - 人物弧光嵌入流程
   - 伏笔、悬念与揭示节奏
   - 爽点 / 卖点兑现节奏
   - 情绪节奏与阅读体验
   - 世界观展开顺序
   - 阵营与势力推进
   - 代价与失败机制
   - 反转与认知升级
   - 分卷衔接方向
   - 结局路径
3. 每个模块下都有具体内容，不是空标题。
4. 能看出对 `direction` 的核心卖点和故事承诺有承接。
5. 能看出对 `worldbuilding` 的世界规则、地图、势力或力量体系有承接。
6. 能看出对 `characters` 的人物弧光和关系变化有承接。
7. 没有逐章正文。
8. 没有直接替代分卷大纲。
9. 未锁定内容标为候选或待确认。
10. 能为 `volume_outline` 提供分卷骨架。

### 7.3 Demo 验收

如果要重新生成 demo，请不要直接覆盖用户当前产物，先备份：

```bash
cp -R demo-chat demo-chat.before-story-flow-fix
```

然后按项目现有 CLI 流程重新运行或运行 smoke test。完成后检查：

```bash
grep -n "故事主线推进\|故事阶段划分\|核心冲突升级路径\|结局路径" demo-chat/outline/story_flow.md
```

至少确认所有必需标题存在。

---

## 8. Codex 执行流程建议

Codex 执行时请按以下顺序推进：

1. 阅读本计划和相关源码。
2. 跑基线测试并记录结果。
3. 修改 `stage_contracts.py`。
4. 新增 `story_flow_framework.py`。
5. 将框架注入 `graph_outline.py` 的角色 Prompt 和 Synthesizer Prompt。
6. 扩展 `story_flow` 角色分工和 stage boundary。
7. 新增 `story_flow_structure.py` 并接入运行节点。
8. 更新摘要/记忆逻辑，确保后续 `volume_outline` 可以读到故事流程骨架。
9. 新增和更新测试。
10. 运行测试。
11. 如测试失败，优先修实现，不要削弱验收标准。
12. 最终汇报：
    - 修改文件清单
    - 关键设计说明
    - 测试命令和结果
    - `story_flow.md` 前后结构差异
    - 是否有未完成项或风险

---

## 9. 重要实现细节

### 9.1 标题匹配要支持轻微变体

模型可能输出：

- `爽点/卖点兑现节奏`
- `爽点 / 卖点兑现节奏`
- `爽点与卖点兑现节奏`

结构校验应支持常见变体，但最终修复输出建议统一为：

```markdown
## 故事流程稿
### 故事主线推进
### 故事阶段划分
### 核心冲突升级路径
### 关键剧情节点
### 人物弧光嵌入流程
### 伏笔、悬念与揭示节奏
### 爽点 / 卖点兑现节奏
### 情绪节奏与阅读体验
### 世界观展开顺序
### 阵营与势力推进
### 代价与失败机制
### 反转与认知升级
### 分卷衔接方向
### 结局路径
```

### 9.2 不要让字数限制截断完整结构

如果框架完整后输出变长，旧的 `max_total_chars=1200` 一定会伤害质量。建议：

- `story_flow` 单独提高字数上限；
- 或允许 `max_total_chars=None`；
- 或在 Synthesizer 输出规则中控制为“每节 2～6 条要点”，而不是粗暴总字数截断。

### 9.3 角色 Agent 输出可以分工，但 Synthesizer 必须完整

角色 Agent 可以各自聚焦：冲突、人物、悬念、爽点等；但最终 Synthesizer 不能只汇总其中几类意见，必须按 14 模块输出完整稿。

### 9.4 `story_flow` 和 `volume_outline` 的边界

`story_flow` 可以写：

```markdown
第一卷功能：入局与立人设；卷尾钩子：前世记忆首次失准。
```

不应该写：

```markdown
第 1 章：主角醒来。
第 2 章：师姐送药。
第 3 章：外门弟子挑衅。
```

### 9.5 处理未锁定设定

推荐表达：

```markdown
候选方向：若“寿元债”在 worldbuilding 中已锁定，可将其作为中后期规则真相；若未锁定，则暂以“资源代价机制”占位，等待用户确认。
```

不推荐表达：

```markdown
寿元债就是世界底层规则。
```

除非该设定已在前序阶段锁定。

---

## 10. 建议的 `story_flow.md` 输出模板

下面是最终生成时可使用的稳定模板。不要把括号里的说明原样留在成品中；成品应填写具体故事内容。

```markdown
## 故事流程稿

### 故事主线推进
- 故事起点：...
- 引发事件：...
- 主角初始目标：...
- 主线任务 / 主线问题：...
- 阶段性目标变化：...
- 终局目标：...

### 故事阶段划分
| 阶段 | 故事功能 | 核心推进 | 阶段出口 |
| --- | --- | --- | --- |
| 开局阶段 | ... | ... | ... |
| 成长阶段 | ... | ... | ... |
| 扩张阶段 | ... | ... | ... |
| 转折阶段 | ... | ... | ... |
| 高潮阶段 | ... | ... | ... |
| 结局阶段 | ... | ... | ... |

### 核心冲突升级路径
| 层级 | 主要敌人 / 压力 | 冲突升级方式 | 胜利代价 / 失败损失 | 对成长的推动 |
| --- | --- | --- | --- | --- |
| 初级冲突 | ... | ... | ... | ... |
| 中级冲突 | ... | ... | ... | ... |
| 高级冲突 | ... | ... | ... | ... |
| 终极冲突 | ... | ... | ... | ... |

### 关键剧情节点
- 开篇钩子：...
- 第一次选择：...
- 第一次胜利：...
- 第一次失败：...
- 中段大转折：...
- 黑暗时刻：...
- 最终觉醒：...
- 终局对决：...
- 结局回响：...

### 人物弧光嵌入流程
- 主角起点状态：...
- 主角成长路径：...
- 关键人物影响：...
- 关系变化流程：...
- 反派与主角镜像：...
- 终局人物状态：...

### 伏笔、悬念与揭示节奏
- 核心悬念：...
- 阶段性悬念：...
- 伏笔布置点：...
- 真相揭示顺序：...
- 回收方式：...

### 爽点 / 卖点兑现节奏
- 开局卖点：...
- 阶段性爽点：...
- 升级型爽点：...
- 情绪释放点：...
- 与主线结合：...

### 情绪节奏与阅读体验
- 整体情绪曲线：...
- 阶段情绪目标：...
- 高低起伏安排：...
- 缓冲与爆发：...
- 分卷节奏参考：...

### 世界观展开顺序
- 开局展示：...
- 中期扩展：...
- 后期揭示：...
- 展示方式：...
- 与主角命运的关系：...

### 阵营与势力推进
- 登场顺序：...
- 阵营关系变化：...
- 主角阵营位置变化：...
- 阵营冲突推动主线：...

### 代价与失败机制
- 能力代价：...
- 选择代价：...
- 关系代价：...
- 世界代价：...
- 必败节点：...

### 反转与认知升级
- 开局反转：...
- 中段反转：...
- 后期反转：...
- 终局反转：...
- 伏笔对应：...

### 分卷衔接方向
| 卷 | 故事功能 | 核心问题 | 阶段性高潮 | 卷尾钩子 |
| --- | --- | --- | --- | --- |
| 第一卷 | ... | ... | ... | ... |
| 第二卷 | ... | ... | ... | ... |
| 第三卷 | ... | ... | ... | ... |
| 第四卷 | ... | ... | ... | ... |
| 第五卷 | ... | ... | ... | ... |

### 结局路径
- 主线结局：...
- 人物结局：...
- 关系结局：...
- 世界结局：...
- 主题落点：...
- 余味 / 续作空间：...

### 仍需确认的问题
1. ...
2. ...
3. ...
```

---

## 11. 最终交付要求

Codex 完成后，请输出如下汇报：

```markdown
## 完成情况
- 已扩展 story_flow 阶段契约：...
- 已新增 story_flow 框架注入：...
- 已新增结构修复：...
- 已补充测试：...

## 修改文件
- ...

## 测试结果
```bash
python -m compileall src tests
# result ...
python -m pytest ...
# result ...
```

## 产物变化
- 旧 story_flow：仅包含开局/中段/后段/终局/伏笔等短结构。
- 新 story_flow：包含 14 个全书级流程模块，可支撑后续分卷和章节生成。

## 风险与后续
- ...
```

如果有未完成项，必须明确写出原因、影响和下一步，不要隐藏。
