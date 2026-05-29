"""Explicit prompt registry for retained Web runtime prompts."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources


PROMPT_REGISTRY: frozenset[str] = frozenset(
    {
        "atmosphere_enhancer",
        "bible_conflict_checker",
        "bible_update_extractor",
        "bible_update_synthesizer",
        "chapter_auto_reviser",
        "chapter_card_synthesizer",
        "chapter_conflict_agent",
        "chapter_goal_agent",
        "chapter_hook_agent",
        "chapter_pacing_agent",
        "chapter_planner",
        "chapter_writer",
        "craft_profile_extractor",
        "dialogue_enhancer",
        "direct_chapter_writer",
        "editor",
        "emotional_resonance_polisher",
        "ending_resonance_agent",
        "hook_enhancer",
        "human_feedback_reviser",
        "outline_editor",
        "outline_planner",
        "outline_reviser",
        "outline_stage_reviser",
        "project_craft_memory_extractor",
        "restraint_agent",
        "restraint_polisher",
        "scene_breakdown_agent",
        "scene_conflict_check_agent",
        "scene_synthesizer",
        "stage_craft_brief_synthesizer",
        "style_normalizer",
        "version_comparator",
        "volume_blocker_reviser",
        "volume_consistency_checker",
    }
)

INLINE_AGENT_NAMES: frozenset[str] = frozenset(
    {
        "characters_structure_repair",
        "chapter_outline_structure_repair",
        "global_consistency_repair",
        "global_consistency_reviewer",
        "outline_question_answerer",
        "outline_stage_role",
        "outline_stage_synthesizer",
        "story_flow_structure_repair",
        "volume_outline_structure_repair",
        "worldbuilding_structure_repair",
    }
)


@dataclass(frozen=True)
class PromptRegistryProblems:
    missing_files: list[str]
    orphan_files: list[str]


def prompt_file_names() -> set[str]:
    return {
        path.name.removesuffix(".md")
        for path in resources.files("ai_novelist.prompts").iterdir()
        if path.name.endswith(".md")
    }


def validate_prompt_registry() -> PromptRegistryProblems:
    files = prompt_file_names()
    registry = set(PROMPT_REGISTRY)
    return PromptRegistryProblems(
        missing_files=sorted(registry - files),
        orphan_files=sorted(files - registry),
    )
