"""Quality report rendering for corpus indexing."""

from __future__ import annotations

from ai_novelist.corpus.models import CorpusChapter, CorpusScene, CorpusWork, RetrievalChunk


def render_quality_report(
    works: list[CorpusWork],
    chapters: list[CorpusChapter],
    scenes: list[CorpusScene],
    chunks: list[RetrievalChunk],
    errors: list[dict],
) -> str:
    lines = [
        "# Corpus Index Quality Report",
        "",
        f"- works: {len(works)}",
        f"- chapters: {len(chapters)}",
        f"- scenes: {len(scenes)}",
        f"- chunks: {len(chunks)}",
        f"- errors: {len(errors)}",
        "",
        "## Works",
    ]
    for work in works[:50]:
        lines.append(f"- {work.work_id}: {work.title} ({work.char_count} chars)")
    if errors:
        lines.extend(["", "## Errors"])
        for item in errors[:50]:
            lines.append(f"- {item.get('path', '')}: {item.get('error', '')}")
    return "\n".join(lines).rstrip() + "\n"
