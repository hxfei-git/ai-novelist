"""Resolve, persist, and register Stage Craft Briefs for graph nodes."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from ai_novelist.artifacts import save_json_artifact, save_markdown_artifact
from ai_novelist.corpus.craft_brief import build_stage_craft_brief
from ai_novelist.corpus.craft_query_planner import plan_craft_query
from ai_novelist.corpus.craft_retriever import retrieve_craft_context
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


def resolve_author_craft(
    state: NovelState,
    store: LocalStore,
    purpose: str,
    chapter: int | None = None,
    stage: str | None = None,
    adapter=None,
    max_chars: int | None = None,
) -> NovelState:
    del adapter
    mode = (state.craft_mode or state.craft_options.get("craft_mode") or os.getenv("AI_NOVELIST_CRAFT_MODE", "off")).strip().lower()
    if mode not in {"assist", "strict"}:
        return state
    try:
        options = dict(state.craft_options or {})
        if "corpus_index_dir" not in options:
            options["corpus_index_dir"] = os.getenv("AI_NOVELIST_CORPUS_INDEX_DIR", "corpus_index")
        if max_chars is None:
            max_chars = int(options.get("craft_max_chars") or os.getenv("AI_NOVELIST_CRAFT_MAX_CHARS", "3000"))
        if mode == "strict":
            max_chars = min(max_chars or 4500, 4500)
        index_dir = Path(str(options.get("corpus_index_dir") or "corpus_index")).expanduser()
        if not index_dir.exists():
            state.director_task_args["craft_warning"] = f"Author Craft index not found: {index_dir}"
            return state
        state.craft_mode = mode
        state.craft_options = options
        query = plan_craft_query(
            state,
            store,
            purpose,
            chapter=chapter or state.active_chapter or state.current_chapter,
            stage=stage,
            pacing_target=state.director_task_args.get("pacing_target"),
        )
        context = retrieve_craft_context(index_dir, query, max_notes=query.max_notes)
        if not context.selected_notes:
            state.director_task_args["craft_warning"] = "No Author Craft profiles matched current stage"
            return state
        brief = build_stage_craft_brief(
            context,
            query.pacing_target,
            max_chars=max_chars or 3000,
            project_id=state.project_id,
            craft_mode=mode,
        )
        relative_brief = store.stage_craft_brief_relative_path(purpose, chapter, stage)
        relative_sources = store.stage_craft_sources_relative_path(purpose, chapter, stage)
        project_dir = store.project_dir(state.project_id)
        brief_record = save_markdown_artifact(
            project_dir,
            relative_brief,
            brief.content,
            "stage_craft_brief",
            chapter=chapter,
            stage=purpose if not stage else f"{purpose}:{stage}",
            source_agent="author_craft_resolver",
            graph=state.active_graph or purpose,
            summary=f"{purpose} / {len(brief.source_note_ids)} craft notes",
        )
        sources_record = save_json_artifact(
            project_dir,
            relative_sources,
            brief.to_sources_dict(),
            "stage_craft_sources",
            chapter=chapter,
            stage=purpose if not stage else f"{purpose}:{stage}",
            source_agent="author_craft_resolver",
            graph=state.active_graph or purpose,
            summary=f"{len(brief.source_evidence)} craft sources",
        )
        state.active_craft_brief_path = brief_record.path
        state.craft_profile_ids = brief.source_profile_ids[-20:]
        state.craft_sources = [item.to_dict() for item in brief.source_evidence[:20]]
        state.craft_context_digest = brief.digest
        state.craft_updated_at = datetime.now(UTC).isoformat(timespec="seconds")
        state.project_craft_memory_path = str(store.project_craft_memory_path(state.project_id))
        state.director_task_args["stage_craft_brief_path"] = brief_record.path
        state.director_task_args["stage_craft_sources_path"] = sources_record.path
        return state
    except Exception as exc:
        state.director_task_args["craft_warning"] = f"Author Craft resolver skipped: {exc}"
        return state
