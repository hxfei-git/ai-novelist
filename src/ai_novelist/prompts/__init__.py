"""Prompt loading utilities."""

from __future__ import annotations

from importlib import resources

from ai_novelist.prompts.registry import PROMPT_REGISTRY


class PromptNotFoundError(RuntimeError):
    """Raised when a prompt template is missing."""


AUTHOR_CRAFT_POLICY_PROMPTS = {
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
    "direct_chapter_writer",
    "chapter_auto_reviser",
    "volume_consistency_checker",
    "volume_blocker_reviser",
    "human_feedback_reviser",
    "dialogue_enhancer",
    "atmosphere_enhancer",
    "hook_enhancer",
    "style_normalizer",
    "restraint_polisher",
    "emotional_resonance_polisher",
}


def load_prompt(name: str) -> str:
    if name not in PROMPT_REGISTRY:
        raise PromptNotFoundError(f"Prompt is not registered: {name}.md")
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
