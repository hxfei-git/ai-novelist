# AI Novelist `volume_outline` 生成整改计划（Codex CLI 执行版）

> 目标：把 `volume_outline.md` 从“少量分卷摘要”整改为“可支撑章节大纲、章节卡、场景卡和正文生产的卷级蓝图”。
>
> 使用方式：在 `ai-novelist` 仓库根目录，把本文件作为 Codex CLI 的执行任务上下文。Codex 需要逐项修改代码、补充测试、运行验证，并在最终汇报中给出变更文件、测试结果和前后对比。

---

## 0. 背景与问题诊断

本计划基于当前仓库、`demo-chat/outline/volume_outline.md`、`demo-chat/outline/story_flow.md` 和 `chat.log` 的实际输出制定。

当前 `demo-chat/outline/volume_outline.md` 只有以下结构：

- 分卷结构
- 卷目标
- 卷内主要矛盾
- 卷级高潮
- 卷间钩子
- 仍需确认的问题

这导致分卷大纲存在明显缺口：

1. **卷级设定不完整**：没有分卷数量、卷名、副标题、章节范围、字数范围、所处故事阶段、主叙事功能等稳定字段。
2. **单卷缺少一句话概括**：每卷没有清晰说明“这一卷讲什么、核心看点是什么、读者期待是什么”。
3. **剧情推进太粗**：没有开卷状态、入卷事件、前期推进、中段转折、低谷失败、高潮、结尾余波和下卷钩子的过程线。
4. **关键节点缺失**：当前只写高潮，没有每卷开卷事件、受挫、中段反转、重大选择、关键揭示和结尾钩子。
5. **人物推进不足**：缺少主角状态、能力、信念、关系变化、新人物登场、旧人物退场、反派推进、秘密揭示和信息差变化。
6. **世界观释放不足**：没有控制每卷出现的新地点、新势力、新规则、历史背景、力量体系、隐藏真相和保留未知。
7. **爽点/卖点兑现缺位**：没有按题材说明每卷给读者兑现什么期待，例如悬疑揭示、关系拉扯、反转、打脸、升级、情绪爆点。
8. **伏笔与信息差缺位**：缺少“本卷埋什么、揭什么、暂时不说什么”。
9. **情绪节奏缺位**：没有开卷、中段、高潮、结尾的阅读情绪曲线。
10. **开头结尾弱**：没有明确每卷第一场戏、开头钩子、结尾解决什么、留下什么、如何引向下一卷。
11. **前后卷衔接弱**：没有逐卷说明继承上一卷什么后果、解决什么阶段问题、制造什么新问题、下一卷从哪里接起。
12. **约束与弹性边界不足**：没有清晰区分核心约束、可变内容、待确认内容和禁止 AI 擅改的设定，导致卷级规划要么过死、要么过松。

当前 `chat.log` 还能看到：

- `volume_outline` 角色短评 Agent 只有 3 个：`分卷策划 Agent`、`卷内高潮 Agent`、`卷间钩子 Agent`。
- 汇总 Agent 上下文约 3K，输出仍然短，说明问题不是模型上下文不够，而是阶段契约、输出规则和结构修复都不完整。
- 当前 `story_flow.md` 本身也是旧短结构，虽然代码已整改 story_flow 框架，但 demo 旧产物尚未重跑。volume_outline 整改必须兼容两种情况：有完整 story_flow 时深度承接；只有旧短 story_flow 时也能生成完整分卷蓝图，并用“候选/待确认”标注缺口。

---

## 1. 执行原则

1. **不要只改 Prompt**：必须同时整改阶段契约、框架注入、角色分工、输出规则、结构校验、修复兜底、摘要记忆和测试。
2. **不要把 volume_outline 做成章节大纲**：可以给每卷大致章节范围和字数范围，但不能拆第 1 章、第 2 章的逐章细纲。
3. **不要搬运完整 worldbuilding/characters/story_flow**：volume_outline 只取每卷需要释放和推进的部分，不复制全部设定。
4. **不要硬造未确认设定**：凡是 direction、worldbuilding、characters、story_flow 没有明确来源的信息，只能写成“候选方向 / 待确认 / 可选方案”。
5. **每卷要可执行但保留弹性**：分卷大纲应能支撑后续章节大纲，但不必单列“锁定项”作为硬性必填模块；如有必要，只保留轻量的卷级约束备注。
6. **按不同卷型调整重点**：调查型卷、战争型卷、感情推进卷、成长卷、探索卷、终局卷的推进方式可以不同，不要套死单一公式。
7. **以结构可验证为准**：完成后必须有结构校验和集成测试，确保保存的 `outline/volume_outline.md` 包含完整卷级蓝图。
8. **遵守仓库规范**：任何代码变更必须同步更新 `docs/IMPLEMENTATION_PLAN.md` 和 `docs/SESSION_SUMMARY.md`，并创建 git commit。

---

## 2. 目标产物规格

整改后，`outline/volume_outline.md` 应成为“分卷大纲稿”，默认包含以下 14 个核心模块，另可按需附加“仍需确认的问题”和“卷级约束与待确认项（可选）”。建议稳定使用以下 Markdown 标题，方便结构校验。

### 2.1 必须包含的 14 个核心模块

1. **分卷总体规划**
   - 分卷数量
   - 每卷名称
   - 每卷大致章节范围
   - 每卷大致字数范围
   - 每卷在全书中的阶段位置
   - 每卷承担的叙事功能
   - 全书分卷推进逻辑

2. **单卷基础定位**
   - 卷序号
   - 卷名
   - 卷副标题
   - 大致章节范围
   - 大致字数范围
   - 所属故事阶段
   - 本卷主叙事功能
   - 可兼具的副功能

3. **本卷一句话概括**
   - 每卷一句话剧情
   - 每卷核心看点
   - 每卷主要问题
   - 每卷读者期待
   - 每卷阶段性承诺

4. **本卷阶段目标**
   - 主角这一卷想达成什么
   - 主角被迫面对什么
   - 阶段性任务是什么
   - 卷末得到什么
   - 卷末失去什么
   - 成功或失败带来的后果

5. **本卷核心冲突**
   - 人物冲突
   - 规则冲突
   - 环境冲突
   - 内心冲突
   - 关系冲突
   - 阵营冲突
   - 冲突如何逐步升级

6. **本卷剧情推进**
   - 开卷状态
   - 入卷事件
   - 目标建立
   - 前期推进
   - 中段转折
   - 冲突升级
   - 重大选择
   - 低谷或失败
   - 高潮事件
   - 结尾余波
   - 下卷钩子

7. **本卷关键节点**
   - 开卷事件
   - 第一个重要推动事件
   - 第一次明显受挫
   - 中段反转
   - 重大选择
   - 关键揭示
   - 高潮事件
   - 结尾钩子

8. **本卷人物推进**
   - 主角状态变化
   - 主角能力变化
   - 主角信念变化
   - 关键配角作用
   - 重要关系变化
   - 新人物登场
   - 旧人物退场
   - 反派或对手推进
   - 角色秘密揭示进度
   - 人物之间的信息差变化

9. **本卷世界观释放**
   - 新地点
   - 新势力
   - 新规则
   - 历史背景
   - 力量体系推进
   - 社会结构展示
   - 隐藏真相揭示
   - 暂时保留的未知信息

10. **本卷爽点与卖点兑现**
    - 主要爽点
    - 高光场面
    - 能力升级点
    - 打脸/逆转点
    - 情感爆点
    - 悬疑揭示点
    - 大场面
    - 最值得期待的桥段

11. **本卷伏笔、悬念与信息差**
    - 承接前文的伏笔
    - 本卷新增伏笔
    - 本卷揭示的悬念
    - 本卷保留的悬念
    - 本卷制造的误导
    - 人物之间的信息差
    - 读者与主角之间的信息差
    - 为后续卷准备的反转条件

12. **本卷情绪节奏**
    - 开卷情绪
    - 中段情绪
    - 高潮情绪
    - 结尾情绪
    - 本卷整体阅读体验
    - 情绪反差
    - 缓冲段落需求

13. **本卷开头与结尾**
    - 第一场戏
    - 开头钩子
    - 入卷问题
    - 结尾解决了什么
    - 结尾留下了什么
    - 如何引向下一卷

14. **与前后卷的衔接**
    - 继承上一卷的什么问题
    - 延续上一卷的什么后果
    - 本卷解决了哪些阶段问题
    - 本卷制造了哪些新问题
    - 下一卷从哪里接起
    - 本卷在全书主线中的作用

### 2.2 可选模块

15. **仍需确认的问题**
   - 最多 3 个。
   - 只问会影响分卷数量、卷末大事件、关键人物命运、终局方向或不可逆设定的问题。
   - 不要重复问已能从前序阶段推导的问题。

16. **卷级约束与待确认项（可选）**
   - 只有在确实需要提醒后续生成时才保留。
   - 可记录少量关键约束、可调整内容和不确定内容。
   - 不作为默认必填模块，避免把分卷大纲写死。

---

## 3. 推荐输出模板

最终 `volume_outline.md` 建议使用以下稳定结构。模板中的说明不能原样留在成品里，成品必须填写具体故事内容。

```markdown
## 分卷大纲稿

### 分卷总体规划
| 卷 | 卷名 | 章节范围 | 字数范围 | 故事阶段 | 主叙事功能 | 全书推进作用 |
| --- | --- | --- | --- | --- | --- | --- |
| 第一卷 | ... | ... | ... | 开局 / 入局 | ... | ... |
| 第二卷 | ... | ... | ... | 成长 / 扩张 | ... | ... |
| 第三卷 | ... | ... | ... | 转折 / 低谷 | ... | ... |

### 单卷基础定位
| 卷 | 卷名 / 副标题 | 主功能 | 副功能 | 阶段位置 | 弹性说明 |
| --- | --- | --- | --- | --- | --- |
| 第一卷 | ... | ... | ... | ... | ... |

### 本卷一句话概括
- 第一卷：...
- 第二卷：...
- 第三卷：...

### 本卷阶段目标
| 卷 | 主角目标 | 被迫面对 | 卷末得到 | 卷末失去 | 成败后果 |
| --- | --- | --- | --- | --- | --- |

### 本卷核心冲突
| 卷 | 冲突来源 | 升级方式 | 主要压力 | 卷末变化 |
| --- | --- | --- | --- | --- |

### 本卷剧情推进
#### 第一卷：...
- 开卷状态：...
- 入卷事件：...
- 目标建立：...
- 前期推进：...
- 中段转折：...
- 冲突升级：...
- 重大选择：...
- 低谷或失败：...
- 高潮事件：...
- 结尾余波：...
- 下卷钩子：...

#### 第二卷：...
- ...

### 本卷关键节点
| 卷 | 开卷事件 | 首个推动 | 明显受挫 | 中段反转 | 重大选择 | 关键揭示 | 高潮事件 | 结尾钩子 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

### 本卷人物推进
| 卷 | 主角变化 | 关键配角 | 关系变化 | 新登场 / 退场 | 秘密与信息差 |
| --- | --- | --- | --- | --- | --- |

### 本卷世界观释放
| 卷 | 新地点 | 新势力 | 新规则 / 体系 | 揭示内容 | 保留未知 |
| --- | --- | --- | --- | --- | --- |

### 本卷爽点与卖点兑现
| 卷 | 主要爽点 | 高光桥段 | 情感 / 悬疑 / 反转兑现 | 与主线关系 |
| --- | --- | --- | --- | --- |

### 本卷伏笔、悬念与信息差
| 卷 | 承接伏笔 | 新增伏笔 | 本卷揭示 | 本卷保留 | 后续反转准备 |
| --- | --- | --- | --- | --- | --- |

### 本卷情绪节奏
| 卷 | 开卷情绪 | 中段情绪 | 高潮情绪 | 结尾情绪 | 缓冲 / 反差 |
| --- | --- | --- | --- | --- | --- |

### 本卷开头与结尾
| 卷 | 第一场戏 | 开头钩子 | 入卷问题 | 结尾解决 | 结尾遗留 | 下一卷入口 |
| --- | --- | --- | --- | --- | --- | --- |

### 与前后卷的衔接
- 第一卷 -> 第二卷：...
- 第二卷 -> 第三卷：...
- 第三卷 -> 第四卷：...

### 仍需确认的问题
1. ...
2. ...
3. ...

### 卷级约束与待确认项（可选）
#### 第一卷
- 关键约束：...
- 可调整内容：...
- 待确认：...
- 注意：...

#### 第二卷
- ...
```

---

## 4. 针对当前 demo 的方向建议

这一节不是硬编码内容，只用于指导测试、mock 和人工验收。

当前 demo 已有信息大致为：主角重生到幽罗魔宗外门，想低调苟活；外门小院有轻松日常与危险反差；药田、矿坑、丹药、符纸、软资源、人情债构成低阶压力；师妹提供日常温度和牵连风险；圣女线代表更高压的危险同盟；故事流程中后段可能走向边境城、矿脉或近海海市。

推荐分卷应从 `story_flow` 的阶段骨架推导，而不是只写“三卷”。如果用户只说“三卷”，系统也应补齐每卷功能和弹性边界。

### 4.1 三卷版候选

1. **第一卷：外门苟活 / 入局卷**
   - 功能：立人设、立卖点、建立外门规则、展示小院日常与危险反差。
   - 核心问题：主角能否在不暴露前世记忆的前提下活下来，并保护师妹不被卷入外门清洗。
   - 关键推进：药田差事、便宜丹药/符纸、人情债、第一次避坑、第一次留下“知道太多”的痕迹。
   - 卷末变化：主角暂时站稳，但被圣女或更高层注意到。

2. **第二卷：边境承压 / 扩张卷**
   - 功能：扩大地图，连接外门、矿坑、边境城，推动从避祸到处理危险。
   - 核心问题：主角是否还能只靠躲避保护自己和身边人。
   - 关键推进：矿坑名额、边境城任务、圣女试探、前世记忆失准、一次关系受损或任务失败。
   - 卷末变化：主角被迫承认自己已经进入更高层视线，不能再只守小院。

3. **第三卷：同盟代价 / 转折卷**
   - 功能：把危险同盟、资源交易、圣女线和海市/高阶交易压到台前。
   - 核心问题：主角愿意为保护关系和换取后路暴露多少、交换多少、牵连多少。
   - 关键推进：近海海市、情报交易、圣女立场变化、师妹风险升级、同盟代价显形。
   - 卷末变化：主角获得更大资源入口，同时失去完全隐身的可能。

### 4.2 五卷版候选

如果项目目标是更长篇，volume_outline 应允许给出五卷结构，或在“三卷”用户反馈下标明“三卷为当前基准，后续可扩展为五卷”。

1. 第一卷：外门苟活与小院牵连。
2. 第二卷：药田矿坑与外门清洗。
3. 第三卷：边境城承压与圣女试探。
4. 第四卷：近海海市交易与同盟代价。
5. 第五卷：规则真相、师徒旧案和有限胜利。

### 4.3 当前 demo 产物应避免的问题

- 不要只写“来源：已锁定...”作为内容填充。
- 不要把每卷都写成同一种“压力升级”。
- 不要只给卷名，不给卷内过程线。
- 不要把边境城、矿坑、海市写成装饰性地点，必须说明它们如何改变主角目标、关系和世界认知。
- 不要在用户只确认“三卷”时忽略章节范围、字数范围、卷功能、开头结尾和必要的轻量约束备注。

---

## 5. 代码整改步骤

### 5.1 建立分支与跑基线

在仓库根目录执行：

```bash
git checkout -b fix/volume-outline-framework
.venv/bin/python -m compileall src tests
.venv/bin/python -m pytest tests/test_outline_stage_controls.py tests/test_outline_collaboration.py tests/test_output_contracts.py tests/test_graph_writer.py
```

同时查看当前关键文件：

```bash
sed -n '1,420p' src/ai_novelist/outline/stage_contracts.py
sed -n '1,260p' src/ai_novelist/outline/renderers.py
sed -n '1,520p' src/ai_novelist/graph_outline.py
sed -n '200,420p' src/ai_novelist/adapters/codex_cli.py
rg -n "volume_outline|分卷" src tests
sed -n '1,260p' demo-chat/outline/volume_outline.md
sed -n '1,260p' demo-chat/outline/story_flow.md
```

记录基线结果。如果已有测试失败，先确认是否与本次需求相关。

### 5.2 扩展 `volume_outline` 阶段契约

文件：`src/ai_novelist/outline/stage_contracts.py`

将 `volume_outline` 从当前 5 个 slot 扩展为 14 个核心模块，并把轻量约束改为可选。

建议 `allowed_intents` 覆盖：

```python
allowed_intents=(
    "分卷总体规划",
    "单卷基础定位",
    "本卷一句话概括",
    "本卷阶段目标",
    "本卷核心冲突",
    "本卷剧情推进",
    "本卷关键节点",
    "本卷人物推进",
    "本卷世界观释放",
    "本卷爽点与卖点兑现",
    "本卷伏笔悬念与信息差",
    "本卷情绪节奏",
    "本卷开头与结尾",
    "前后卷衔接",
)
```

建议 `forbidden_intents` 覆盖：

```python
forbidden_intents=(
    "逐章细纲",
    "章节正文",
    "完整场景卡",
    "替代 chapter_outline",
    "替代 story_flow 重写全书主线",
    "新增与 worldbuilding 冲突的世界规则",
    "新增与 characters 冲突的人物设定",
    "无来源地把候选内容写成已锁定 canon",
    "只输出卷名和卷目标的短摘要",
)
```

建议 slots：

```python
slots=(
    StageSlot("volume_master_plan", "分卷总体规划", "分卷数量、卷名、章节/字数范围、阶段位置、叙事功能和全书推进逻辑", True, 8, 220),
    StageSlot("volume_positioning", "单卷基础定位", "卷序号、卷名、副标题、范围、所属故事阶段、主功能和副功能", True, 8, 200),
    StageSlot("volume_loglines", "本卷一句话概括", "每卷一句话剧情、核心看点、主要问题、读者期待和阶段性承诺", True, 8, 220),
    StageSlot("volume_goals", "本卷阶段目标", "主角目标、被迫面对、阶段任务、卷末得到/失去和成败后果", True, 8, 220),
    StageSlot("volume_conflicts", "本卷核心冲突", "人物、规则、环境、内心、关系、阵营冲突及升级方式", True, 8, 220),
    StageSlot("volume_plot_progression", "本卷剧情推进", "开卷状态、入卷事件、前期推进、中段转折、低谷、高潮、余波和下卷钩子", True, 8, 260),
    StageSlot("volume_key_nodes", "本卷关键节点", "开卷事件、推动事件、受挫、中段反转、重大选择、关键揭示、高潮和结尾钩子", True, 8, 220),
    StageSlot("volume_character_progression", "本卷人物推进", "主角变化、关键配角、重要关系、新登场/退场、对手推进和信息差变化", True, 8, 220),
    StageSlot("volume_world_reveal", "本卷世界观释放", "新地点、新势力、新规则、历史背景、体系推进、隐藏真相和保留未知", True, 8, 220),
    StageSlot("volume_payoffs", "本卷爽点与卖点兑现", "高光场面、升级、逆转、情感爆点、悬疑揭示、大场面和桥段期待", True, 8, 220),
    StageSlot("volume_foreshadowing", "本卷伏笔、悬念与信息差", "承接伏笔、新增伏笔、揭示、保留、误导、信息差和后续反转条件", True, 8, 220),
    StageSlot("volume_emotional_pacing", "本卷情绪节奏", "开卷、中段、高潮、结尾情绪，整体体验、缓冲和反差", True, 8, 200),
    StageSlot("volume_opening_ending", "本卷开头与结尾", "第一场戏、开头钩子、入卷问题、结尾解决/遗留和下一卷入口", True, 8, 220),
    StageSlot("volume_bridges", "与前后卷的衔接", "继承前卷后果、本卷解决/制造的问题、下一卷接起点和全书作用", True, 8, 220),
    # 可选：若后续仍需轻量约束记录，可单独增加非必填卷级备注模块。
)
```

`max_questions` 建议为 3。

`max_total_chars` 建议提升到 9000～12000，或设为 `None` 并交给输出规则控制。首版可用 `10000`。

`confirmation_policy` 建议改为：

```python
confirmation_policy=(
    "只问会影响分卷数量、卷末大事件、关键人物命运、世界观释放顺序或不可逆设定的问题；"
    "不要让用户在模型自造的细枝末节中选择。"
)
```

### 5.3 新增 `volume_outline` 框架文件

新增文件：`src/ai_novelist/volume_outline_framework.py`

建议结构类似 `story_flow_framework.py`：

- `VolumeOutlineSection`
- `VOLUME_OUTLINE_SECTIONS`
- `volume_outline_required_headings()`
- `full_volume_outline_headings()`
- `render_volume_outline_framework(mode="full")`

必需标题：

```python
(
    "分卷总体规划",
    "单卷基础定位",
    "本卷一句话概括",
    "本卷阶段目标",
    "本卷核心冲突",
    "本卷剧情推进",
    "本卷关键节点",
    "本卷人物推进",
    "本卷世界观释放",
    "本卷爽点与卖点兑现",
    "本卷伏笔、悬念与信息差",
    "本卷情绪节奏",
    "本卷开头与结尾",
    "与前后卷的衔接",
)
```

框架 Prompt 必须声明：

- 本阶段是卷级蓝图，不是章节大纲。
- 必须承接 story_flow 的主线阶段、冲突升级、分卷衔接方向和结局路径。
- 必须承接 worldbuilding 的地点、势力、规则释放顺序。
- 必须承接 characters 的关系变化、秘密揭示和人物命运推进。
- 用户只给“三卷/五卷”时，也要补齐每卷功能和弹性边界。
- 未锁定内容写候选或待确认。

### 5.4 新增 `volume_outline` 结构校验与修复

新增文件：`src/ai_novelist/outline/volume_outline_structure.py`

参考 `story_flow_structure.py` 实现：

必需函数：

```python
VOLUME_OUTLINE_REQUIRED_HEADINGS: tuple[str, ...]
normalize_heading(text: str) -> str
canonical_volume_outline_heading(text: str) -> str | None
extract_markdown_sections(text: str) -> dict[str, str]
missing_volume_outline_headings(text: str) -> list[str]
has_nonempty_volume_outline_section(text: str, heading: str) -> bool
empty_volume_outline_sections(text: str) -> list[str]
validate_volume_outline(text: str, min_chars: int = 900) -> tuple[bool, list[str]]
append_missing_volume_outline_sections(text: str, missing: list[str] | None = None) -> str
split_volume_outline_sections(text: str) -> dict[str, str]
volume_outline_bullets(section_text: str) -> list[str]
summarize_volume_outline(text: str, max_chars: int = 2200) -> str
extract_volume_outline_memory(text: str, max_items: int = 24, max_chars: int = 2200) -> list[str]
```

标题别名需支持常见变体：

- `分卷结构` -> `分卷总体规划`
- `卷目标` / `本卷目标` -> `本卷阶段目标`
- `卷内主要矛盾` -> `本卷核心冲突`
- `卷级高潮` -> `本卷关键节点` 或 `本卷剧情推进`，最终修复要保留原内容并归入合适模块
- `卷间钩子` -> `与前后卷的衔接`
- `伏笔悬念` -> `本卷伏笔、悬念与信息差`
- `爽点卖点` -> `本卷爽点与卖点兑现`

校验规则：

1. 必须含 `## 分卷大纲稿` 或同级主标题。
2. 14 个核心模块都存在。
3. 每个模块下有非空内容。
4. 总中文字符数不低于 900，推荐 2500+。
5. 不得出现明显逐章列表，例如 3 个以上 `第 N 章`。
6. 必须有至少 2 个卷级条目；如果用户指定“三卷”，最好有 3 个卷级条目。
7. 若存在“待确认/候选”，不得把同一内容同时写成已锁定。

确定性兜底：

- 如果模型修复仍缺标题，按 14 个核心模块重建文档，并保留可选补充模块。
- 保留已有旧结构内容，归入对应模块。
- 每个缺失模块写“待补充：结构兜底占位”，并给出当前阶段需要补写的方向。

### 5.5 接入 `graph_outline.py`

#### 5.5.1 扩展角色分工

当前：

```python
"volume_outline": ["分卷策划 Agent", "卷内高潮 Agent", "卷间钩子 Agent"]
```

建议改为：

```python
"volume_outline": [
    "分卷架构 Agent",
    "卷内推进 Agent",
    "人物推进 Agent",
    "世界观释放 Agent",
    "爽点悬念 Agent",
    "衔接约束 Agent",
]
```

#### 5.5.2 更新 `role_focus_instruction`

新增角色职责：

- `分卷架构 Agent`：检查分卷数量、卷名、章节/字数范围、阶段位置、主功能和全书推进逻辑。
- `卷内推进 Agent`：检查每卷开卷状态、入卷事件、中段转折、低谷、高潮、结尾余波是否完整。
- `人物推进 Agent`：检查每卷主角变化、关键配角、关系推进、角色秘密和信息差变化。
- `世界观释放 Agent`：检查每卷新地点、新势力、新规则、历史/体系释放和保留未知是否服务剧情。
- `爽点悬念 Agent`：检查每卷爽点、卖点、情绪爆点、伏笔、悬念、揭示和误导是否持续兑现。
- `衔接约束 Agent`：检查前后卷承接、可选约束和不应擅改内容。

#### 5.5.3 新增框架 Prompt

新增：

```python
def volume_outline_framework_prompt(stage: str) -> str:
    if stage != "volume_outline":
        return ""
    from ai_novelist.volume_outline_framework import render_volume_outline_framework
    return (
        "
VOLUME_OUTLINE_FRAMEWORK:
"
        "你必须按下面的分卷大纲蓝图框架生成。分卷大纲不是章节大纲，"
        "而是覆盖卷级目标、剧情推进、人物推进、世界观释放、爽点悬念、情绪节奏和前后卷衔接的骨架。
"
        f"{render_volume_outline_framework(mode='full')}
"
    )
```

将其注入：

- `build_outline_stage_role_prompt`
- `build_outline_stage_synthesizer_prompt`

注入位置参考 `story_flow_framework_prompt(stage)`。

#### 5.5.4 更新 stage boundary

`OUTLINE_STAGE_BOUNDARIES["volume_outline"]` 改为：

允许：

- 分卷总体规划
- 单卷基础定位
- 本卷一句话概括
- 本卷阶段目标
- 本卷核心冲突
- 本卷剧情推进
- 本卷关键节点
- 本卷人物推进
- 本卷世界观释放
- 本卷爽点与卖点兑现
- 本卷伏笔、悬念与信息差
- 本卷情绪节奏
- 本卷开头与结尾
- 与前后卷的衔接
- 卷级约束与待确认项（可选）

禁止：

- 逐章细纲
- 正文场景
- 完整场景卡
- 替代 chapter_outline
- 替代 story_flow 重写全书主线
- 新增无来源 canon
- 复制完整 worldbuilding 或 characters
- 只输出卷名/卷目标/高潮/钩子的短摘要

#### 5.5.5 更新连续性要求

`stage_continuity_requirement("volume_outline")` 改为：

```text
分卷大纲必须整合 direction、worldbuilding、characters 和 story_flow。
本阶段只做卷级蓝图：分卷数量、卷功能、每卷目标、卷内推进、人物推进、世界观释放、爽点悬念、情绪节奏、开头结尾、前后卷衔接和可选约束备注。
可以给大致章节范围和字数范围，但不得拆成逐章细纲，不得替代 chapter_outline。
```

#### 5.5.6 接入结构修复

在 `run_outline_stage_node` 中，类似 `story_flow`：

```python
elif stage == "volume_outline":
    synthesis = ensure_volume_outline_structure(
        synthesis=synthesis,
        state=state,
        adapter=adapter,
        store=store,
        author_craft=author_craft,
        role_reviews=role_reviews,
    )
```

新增函数 `ensure_volume_outline_structure`，参考 `ensure_story_flow_outline_structure`：

- 调用 `validate_volume_outline`。
- 不合格时构建 `AGENT: volume_outline_structure_repair` prompt。
- repair prompt 强调：保留原文有效内容、承接前序阶段、不写逐章细纲、不硬造 canon、输出完整 Markdown。
- repair 失败后调用 `append_missing_volume_outline_sections`。

#### 5.5.7 更新摘要和 stage memory

`summary` 和 `stage_memory` 对后续 `chapter_outline` 很关键。新增分发：

```python
if stage == "volume_outline":
    from ai_novelist.outline.volume_outline_structure import summarize_volume_outline
    return summarize_volume_outline(synthesis)
```

```python
if stage == "volume_outline":
    from ai_novelist.outline.volume_outline_structure import extract_volume_outline_memory
    return extract_volume_outline_memory(synthesis)
```

摘要优先包含：

- 分卷数量与卷名
- 每卷一句话概括
- 每卷阶段目标
- 每卷关键节点
- 每卷人物推进
- 每卷世界观释放
- 每卷结尾钩子
- 可选约束备注

### 5.6 更新 `outline/renderers.py`

在 `_stage_structure` 中为 `volume_outline` 添加专属输出规则，不再走通用 slots 渲染。

规则要点：

- 必须以 `## 分卷大纲稿` 开始。
- 必须包含 14 个核心 `###` 标题。
- 每个必填标题下必须有具体内容。
- 可以用紧凑表格。
- 可以写大致章节范围和字数范围。
- 禁止逐章列表、正文、场景卡。
- `### 仍需确认的问题` 最多 3 条。

### 5.7 更新 mock adapter

文件：`src/ai_novelist/adapters/codex_cli.py`

新增：

- `if "AGENT: volume_outline_structure_repair" in prompt: return self._mock_full_volume_outline()`
- `_mock_full_volume_outline()`，包含 15 模块。
- `_mock_outline_stage_synthesizer` 的 `volume_outline` 改为 `self._mock_full_volume_outline()`。

mock 内容应覆盖 demo 类型：外门苟活、边境承压、同盟代价，或继续使用月球城市示例也可以，但必须是完整 15 模块。

### 5.8 可选：迁移旧 demo 产物

不建议自动覆盖用户 `demo-chat/outline/volume_outline.md`。

如需人工 demo 验收，先备份：

```bash
cp -R demo-chat demo-chat.before-volume-outline-fix
```

然后重新运行 volume_outline 阶段或 smoke。

---

## 6. 测试计划

### 6.1 新增测试：阶段契约

文件：`tests/test_volume_outline_contract.py`

测试点：

1. `volume_outline` contract 存在。
2. 必需 slot 数量不少于 14。
3. slot label 覆盖 14 个核心模块。
4. allowed_intents 覆盖分卷总体、单卷定位、剧情推进、人物推进、世界观释放、爽点、伏笔、情绪、开头结尾、衔接、可选约束。
5. `max_total_chars` 不再是 1400 这种短摘要限制。

### 6.2 新增测试：框架渲染

文件：`tests/test_volume_outline_framework.py`

测试点：

1. `render_volume_outline_framework()` 包含 14 个核心模块。
2. 包含“不写逐章细纲”、“不替代 chapter_outline”、“未确认信息写候选/待确认”。
3. `volume_outline_required_headings()` 返回稳定标题。

### 6.3 新增测试：结构校验与修复

文件：`tests/test_volume_outline_structure.py`

测试输入使用当前旧短格式：

```markdown
## 分卷大纲稿
### 分卷结构
- 第一卷：外门苟活。
- 第二卷：边境承压。
- 第三卷：同盟代价。
### 卷目标
- 第一卷：活下来。
### 卷内主要矛盾
- 第一卷：低调与护人冲突。
### 卷级高潮
- 第一卷：外门清洗。
### 卷间钩子
- 第一卷到第二卷：矿坑压力。
```

测试点：

1. `missing_volume_outline_headings` 能识别缺失模块。
2. 标题别名能把 `分卷结构` 映射到 `分卷总体规划`。
3. `append_missing_volume_outline_sections` 能补齐 15 模块。
4. `validate_volume_outline` 拒绝逐章列表。
5. `summarize_volume_outline` 和 `extract_volume_outline_memory` 优先提取卷名、目标、节点和衔接。

### 6.4 集成测试

在 `tests/test_volume_outline_structure.py` 或 `tests/test_outline_collaboration.py` 中补一个集成测试：

1. 使用 stub adapter：
   - `outline_stage_role` 返回短评。
   - `outline_stage_synthesizer` 返回旧 5 段短结构。
   - `volume_outline_structure_repair` 返回完整 15 模块。
2. 运行 `run_outline_stage_node`，状态为 `outline_stage="volume_outline"`。
3. 断言：
   - `outline_stage_artifacts["volume_outline"]["synthesis"]` 包含 15 模块。
   - 保存到 `outline/volume_outline.md` 和 `outline_stages/volume_outline.md`。
   - artifact registry 注册 `type="volume_outline"`。
   - summary / stage_memory 包含分卷总体规划、剧情推进或关键节点。

### 6.5 更新现有测试

检查并更新：

- `tests/test_outline_collaboration.py`
- `tests/test_outline_stage_controls.py`
- `tests/test_graph_writer.py`
- `tests/test_output_contracts.py`

特别是旧断言：

- `分卷结构`
- `卷目标`
- `卷级高潮`
- `卷间钩子`

不应只断言旧 5 段结构，应改为断言新 15 模块或新专属输出规则。

---

## 7. 验收标准

### 7.1 代码验收

执行：

```bash
.venv/bin/python -m compileall src tests
.venv/bin/python -m pytest tests/test_volume_outline_contract.py tests/test_volume_outline_framework.py tests/test_volume_outline_structure.py
.venv/bin/python -m pytest tests/test_outline_stage_controls.py tests/test_outline_collaboration.py tests/test_graph_writer.py tests/test_output_contracts.py
.venv/bin/python -m pytest
.venv/bin/python tests/smoke_outline_collaboration.py
```

全部通过，或若存在与本次无关的历史失败，必须在最终汇报中明确说明。

### 7.2 产物验收

生成或修复后的 `outline/volume_outline.md` 必须满足：

1. 以 `## 分卷大纲稿` 或同等标题开始。
2. 包含 14 个核心模块：
   - 分卷总体规划
   - 单卷基础定位
   - 本卷一句话概括
   - 本卷阶段目标
   - 本卷核心冲突
   - 本卷剧情推进
   - 本卷关键节点
   - 本卷人物推进
   - 本卷世界观释放
   - 本卷爽点与卖点兑现
   - 本卷伏笔、悬念与信息差
   - 本卷情绪节奏
   - 本卷开头与结尾
   - 与前后卷的衔接
   - 卷级约束与待确认项（可选）
3. 每个模块都有具体内容，不是空标题。
4. 至少有 2 个卷级条目；用户明确“三卷”时应有 3 个卷级条目。
5. 能看出对 `story_flow` 的阶段骨架、冲突升级和结局路径有承接。
6. 能看出对 `worldbuilding` 的地点、势力、规则或资源体系有承接。
7. 能看出对 `characters` 的人物关系、信息差和角色命运推进有承接。
8. 没有逐章细纲。
9. 没有正文片段或场景卡。
10. 未确认内容标为候选或待确认，必要时才补充轻量约束备注。
11. 能直接为 `chapter_outline` 提供卷级约束。

### 7.3 Demo 验收

如果要重跑 demo，请先备份：

```bash
cp -R demo-chat demo-chat.before-volume-outline-fix
```

重跑后检查：

```bash
grep -n "分卷总体规划\|本卷剧情推进\|本卷人物推进\|本卷世界观释放\|仍需确认" demo-chat/outline/volume_outline.md
```

至少确认所有必需标题存在。

---

## 8. 推荐文件变更清单

预期新增：

```text
src/ai_novelist/volume_outline_framework.py
src/ai_novelist/outline/volume_outline_structure.py
tests/test_volume_outline_contract.py
tests/test_volume_outline_framework.py
tests/test_volume_outline_structure.py
```

预期修改：

```text
src/ai_novelist/outline/stage_contracts.py
src/ai_novelist/outline/renderers.py
src/ai_novelist/graph_outline.py
src/ai_novelist/adapters/codex_cli.py
tests/test_outline_collaboration.py
tests/test_outline_stage_controls.py
tests/test_graph_writer.py
```

必须同步修改：

```text
docs/IMPLEMENTATION_PLAN.md
docs/SESSION_SUMMARY.md
```

不要修改：

```text
.env
*.key
用户私密配置
模型 API Key
```

---

## 9. Codex 执行流程建议

Codex 执行时按以下顺序推进：

1. 阅读本计划、`demo-chat/outline/volume_outline.md`、`demo-chat/outline/story_flow.md`、`chat.log` 和相关源码。
2. 跑基线测试并记录结果。
3. 扩展 `volume_outline` 阶段契约。
4. 新增 `volume_outline_framework.py`。
5. 新增 `outline/volume_outline_structure.py`。
6. 将框架注入 `graph_outline.py` 的角色 Prompt 和 Synthesizer Prompt。
7. 扩展 `volume_outline` 角色分工、角色关注点、stage boundary 和 stage continuity。
8. 在 `run_outline_stage_node` 保存前接入结构修复。
9. 更新摘要和 stage memory，确保 `chapter_outline` 能读取卷级骨架。
10. 更新 `renderers.py` 输出规则。
11. 更新 mock adapter。
12. 新增和更新测试。
13. 更新 `docs/IMPLEMENTATION_PLAN.md` 和 `docs/SESSION_SUMMARY.md`。
14. 运行 compileall、目标测试、全量 pytest 和 smoke。
15. 创建 git commit，例如：

```bash
git add src tests docs

git commit -m "fix: expand volume outline framework"
```

---

## 10. 最终汇报要求

完成后请输出：

```markdown
## 完成情况
- 已扩展 volume_outline 阶段契约：...
- 已新增 volume_outline 框架注入：...
- 已新增结构修复：...
- 已补充测试：...

## 修改文件
- ...

## 测试结果
```bash
.venv/bin/python -m compileall src tests
# result ...
.venv/bin/python -m pytest
# result ...
.venv/bin/python tests/smoke_outline_collaboration.py
# result ...
```

## 产物变化
- 旧 volume_outline：仅包含分卷结构、目标、矛盾、高潮、钩子。
- 新 volume_outline：包含 14 个核心卷级蓝图模块，并可按需附加轻量约束备注，足以支撑章节大纲和后续章节卡生成。

## 风险与后续
- ...
```

如果有未完成项，必须明确说明原因、影响和下一步，不要隐藏。
