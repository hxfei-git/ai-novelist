# Corpus Format

Author Craft corpus 支持本地 `.txt` 和 `.md` 文件。可选 sidecar 元数据文件命名为 `<novel>.meta.json` 或 `<novel.txt>.meta.json`。

```json
{
  "title": "示例小说A",
  "author": "mock_author",
  "genre": ["悬疑", "科幻"],
  "permission": "user_provided"
}
```

索引输出：

- `manifest.json`：文件指纹、mtime、size 和状态。
- `works.jsonl`：作品级元数据。
- `chapters.jsonl`：章节边界。
- `scenes.jsonl`：场景边界。
- `chunks.jsonl`：检索用 chunk，包含原文 text，但只保存在本地索引中。
- `quality_report.md`：索引质量摘要。
- `errors.jsonl`：失败文件。

运行时 StageCraftBrief 不读取或注入 `chunks.jsonl` 中的长原文。
