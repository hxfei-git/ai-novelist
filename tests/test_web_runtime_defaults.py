from __future__ import annotations

from pathlib import Path

from ai_novelist.config import load_settings


LOAD_SETTINGS_ENV_VARS = (
    "AI_NOVELIST_PROJECTS_DIR",
    "AI_NOVELIST_MODEL_PROVIDER",
    "AI_NOVELIST_CODEX_BIN",
    "AI_NOVELIST_CODEX_TIMEOUT",
    "DEEPSEEK_API_KEY",
    "AI_NOVELIST_DEEPSEEK_MODEL",
    "AI_NOVELIST_DEEPSEEK_REASONING_EFFORT",
    "AI_NOVELIST_DEEPSEEK_BASE_URL",
    "AI_NOVELIST_SEARCH_PROVIDER",
    "AI_NOVELIST_SEARCH_API_KEY",
    "AI_NOVELIST_SEARCH_BASE_URL",
    "AI_NOVELIST_SEARCH_TIMEOUT",
    "AI_NOVELIST_LOCAL_CORPUS_DIR",
    "AI_NOVELIST_AUTHOR_CORPUS_DIR",
    "AI_NOVELIST_CORPUS_INDEX_DIR",
    "AI_NOVELIST_CRAFT_MODE",
    "AI_NOVELIST_CRAFT_MAX_CHARS",
    "AI_NOVELIST_CRAFT_SIMILARITY_GUARD",
    "AI_NOVELIST_CRAFT_EXTRACT_MOCK",
    "SERPAPI_API_KEY",
    "TAVILY_API_KEY",
    "EXA_API_KEY",
)


def test_deepseek_default_model_is_consistent(monkeypatch) -> None:
    for env_var in LOAD_SETTINGS_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)

    settings = load_settings()
    script = Path("scripts/run_web.sh").read_text(encoding="utf-8")

    assert settings.deepseek_model == "deepseek-v4-flash"
    assert settings.deepseek_reasoning_effort == "low"
    assert "AI_NOVELIST_DEEPSEEK_MODEL:-deepseek-v4-flash" in script
    assert 'export AI_NOVELIST_DEEPSEEK_REASONING_EFFORT="${AI_NOVELIST_DEEPSEEK_REASONING_EFFORT:-low}"' in script


def test_deepseek_reasoning_effort_comes_from_environment(monkeypatch) -> None:
    for env_var in LOAD_SETTINGS_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)
    monkeypatch.setenv("AI_NOVELIST_DEEPSEEK_REASONING_EFFORT", "HIGH")

    settings = load_settings()

    assert settings.deepseek_reasoning_effort == "high"
