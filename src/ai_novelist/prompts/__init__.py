"""Prompt loading utilities."""

from __future__ import annotations

from importlib import resources


class PromptNotFoundError(RuntimeError):
    """Raised when a prompt template is missing."""


def load_prompt(name: str) -> str:
    prompt_file = f"{name}.md"
    try:
        return resources.files(__package__).joinpath(prompt_file).read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PromptNotFoundError(f"Prompt not found: {prompt_file}") from exc
