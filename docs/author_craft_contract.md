# Author Craft Contract

Author Craft Layer 只学习本地小说库中的构思方法，不复刻原文，不模仿具体作者表达，不搬运人物、设定或情节。

## 允许进入 Prompt 的内容

- CraftProfile 中抽象出的结构策略、冲突组织、场景推进、信息释放、节奏控制和修订策略。
- StageCraftBrief 中经过筛选和压缩的当前阶段参考方法。
- CraftEvidence 的 source id、位置标签和分析摘要。

## 禁止进入 Prompt 的内容

- 本地小说长原文。
- RetrievalChunk 的完整 text。
- 可复刻的连续段落或句式。
- 要求模型贴近某个具体作者表达的指令。

## 优先级

```text
用户明确要求
  > 锁定约束 locked_constraints
  > Novel Bible / 项目已定设定
  > Pacing Target / 节奏目标
  > 当前章节卡 / 场景卡 / 审稿任务
  > Project Craft Memory / 本项目已形成的方法
  > External Author Craft / 外部小说库构思参考
  > 大模型自由发挥
```

如果作者构思参考与 Pacing Target、小说圣经或锁定约束冲突，必须放弃该参考方法。
