# Author Craft Layer

Author Craft Layer 把用户本地 `.txt/.md` 小说库离线提炼为可检索的创作方法库，并在章节规划、场景规划、正文写作、审稿和修订阶段注入 StageCraftBrief。

## 基本流程

```bash
.venv/bin/ai-novelist index-corpus --corpus-dir tests/fixtures/corpus --index-dir /tmp/ai_novelist_corpus_index
.venv/bin/ai-novelist extract-craft --index-dir /tmp/ai_novelist_corpus_index --mock
.venv/bin/ai-novelist craft-brief --project demo --purpose chapter_planning --chapter 1 --corpus-index-dir /tmp/ai_novelist_corpus_index --craft-mode assist
```

`craft_mode` 支持：

- `off`：不检索、不注入作者构思参考。
- `assist`：注入简短 StageCraftBrief，仅作为参考。
- `strict`：注入更完整 brief，并在相似度高风险时要求修订。

## 产物

- `corpus_index/*.jsonl`：全局语料索引。
- `corpus_index/craft_profiles/`：work/chapter/scene/genre profiles。
- `projects/<project>/craft/stage_briefs/*.md`：阶段构思参考。
- `projects/<project>/craft/stage_sources/*.json`：阶段来源摘要。
- `projects/<project>/craft/similarity_reports/*.json`：防复刻检查报告。
- `projects/<project>/craft/project_craft_memory.json`：本项目沉淀的方法记忆。
