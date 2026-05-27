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
    codex_timeout_seconds: int | None = None
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-v4-pro"
    deepseek_base_url: str = "https://api.deepseek.com"
    search_provider: str = "mock"
    search_api_key: str = ""
    search_base_url: str = ""
    search_timeout_seconds: int = 20
    local_corpus_dir: str = ""
    author_corpus_dir: str = ""
    corpus_index_dir: str = "corpus_index"
    craft_mode: str = "off"
    craft_max_chars: int = 3000
    craft_similarity_guard: bool = True
    craft_extract_mock: bool = False


def load_settings() -> Settings:
    codex_timeout = os.getenv("AI_NOVELIST_CODEX_TIMEOUT", "").strip()
    return Settings(
        projects_dir=Path(os.getenv("AI_NOVELIST_PROJECTS_DIR", "projects")),
        model_provider=os.getenv("AI_NOVELIST_MODEL_PROVIDER", "codex").strip().lower(),
        codex_bin=os.getenv("AI_NOVELIST_CODEX_BIN", "codex"),
        codex_timeout_seconds=int(codex_timeout) if codex_timeout else None,
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        deepseek_model=os.getenv("AI_NOVELIST_DEEPSEEK_MODEL", "deepseek-v4-pro"),
        deepseek_base_url=os.getenv("AI_NOVELIST_DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        search_provider=os.getenv("AI_NOVELIST_SEARCH_PROVIDER", "mock").strip().lower(),
        search_api_key=search_api_key(os.getenv("AI_NOVELIST_SEARCH_PROVIDER", "mock")),
        search_base_url=os.getenv("AI_NOVELIST_SEARCH_BASE_URL", "").strip(),
        search_timeout_seconds=int(os.getenv("AI_NOVELIST_SEARCH_TIMEOUT", "20")),
        local_corpus_dir=os.getenv("AI_NOVELIST_LOCAL_CORPUS_DIR", "").strip(),
        author_corpus_dir=os.getenv("AI_NOVELIST_AUTHOR_CORPUS_DIR", "").strip(),
        corpus_index_dir=os.getenv("AI_NOVELIST_CORPUS_INDEX_DIR", "corpus_index").strip(),
        craft_mode=os.getenv("AI_NOVELIST_CRAFT_MODE", "off").strip().lower(),
        craft_max_chars=int(os.getenv("AI_NOVELIST_CRAFT_MAX_CHARS", "3000")),
        craft_similarity_guard=parse_bool(os.getenv("AI_NOVELIST_CRAFT_SIMILARITY_GUARD", "true")),
        craft_extract_mock=parse_bool(os.getenv("AI_NOVELIST_CRAFT_EXTRACT_MOCK", "false")),
    )


def search_api_key(provider: str | None = None) -> str:
    provider = (provider or os.getenv("AI_NOVELIST_SEARCH_PROVIDER", "mock")).strip().lower()
    if provider == "serpapi":
        return os.getenv("SERPAPI_API_KEY", "") or os.getenv("AI_NOVELIST_SEARCH_API_KEY", "")
    if provider == "tavily":
        return os.getenv("TAVILY_API_KEY", "") or os.getenv("AI_NOVELIST_SEARCH_API_KEY", "")
    if provider == "exa":
        return os.getenv("EXA_API_KEY", "") or os.getenv("AI_NOVELIST_SEARCH_API_KEY", "")
    return os.getenv("AI_NOVELIST_SEARCH_API_KEY", "")

def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}
