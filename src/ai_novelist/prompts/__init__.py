"""Prompt loading utilities."""

from __future__ import annotations

from importlib import resources


class PromptNotFoundError(RuntimeError):
    """Raised when a prompt template is missing."""


AUTHOR_CRAFT_POLICY_PROMPTS = {
    "director",
    "direction_proposer",
    "outline_planner",
    "outline_stage_reviser",
    "chapter_goal_agent",
    "chapter_conflict_agent",
    "chapter_hook_agent",
    "chapter_card_synthesizer",
    "scene_breakdown_agent",
    "scene_conflict_check_agent",
    "scene_synthesizer",
    "chapter_writer",
    "dialogue_enhancer",
    "atmosphere_enhancer",
    "hook_enhancer",
    "style_normalizer",
    "continuity_editor",
    "structure_editor",
    "character_arc_editor",
    "style_editor",
    "simulated_reader",
    "review_synthesizer",
    "revision_planner",
    "targeted_reviser",
    "revision_self_check",
    "pacing_guard_editor",
    "restraint_polisher",
    "emotional_resonance_polisher",
}


def load_prompt(name: str) -> str:
    prompt_file = f"{name}.md"
    try:
        text = resources.files(__package__).joinpath(prompt_file).read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PromptNotFoundError(f"Prompt not found: {prompt_file}") from exc
    if name in AUTHOR_CRAFT_POLICY_PROMPTS:
        policy = load_author_craft_policy()
        if "Author Craft Policy" not in text:
            text = f"{text.rstrip()}\n\n{policy}"
    return text


def load_author_craft_policy() -> str:
    try:
        return resources.files(__package__).joinpath("partials", "author_craft_policy.md").read_text(encoding="utf-8").rstrip()
    except FileNotFoundError:
        return ""
