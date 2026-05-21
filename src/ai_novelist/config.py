"""Runtime configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    projects_dir: Path = Path("projects")
    model_provider: str = "codex"
    codex_bin: str = "codex"
    codex_timeout_seconds: int = 180
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"


def load_settings() -> Settings:
    return Settings(
        projects_dir=Path(os.getenv("AI_NOVELIST_PROJECTS_DIR", "projects")),
        model_provider=os.getenv("AI_NOVELIST_MODEL_PROVIDER", "codex").strip().lower(),
        codex_bin=os.getenv("AI_NOVELIST_CODEX_BIN", "codex"),
        codex_timeout_seconds=int(os.getenv("AI_NOVELIST_CODEX_TIMEOUT", "180")),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        deepseek_model=os.getenv("AI_NOVELIST_DEEPSEEK_MODEL", "deepseek-chat"),
        deepseek_base_url=os.getenv("AI_NOVELIST_DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
