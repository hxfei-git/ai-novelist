from __future__ import annotations

from pathlib import Path

from ai_novelist.config import load_settings


def test_deepseek_default_model_is_consistent(monkeypatch) -> None:
    monkeypatch.delenv("AI_NOVELIST_DEEPSEEK_MODEL", raising=False)

    settings = load_settings()
    script = Path("scripts/run_web.sh").read_text(encoding="utf-8")

    assert settings.deepseek_model == "deepseek-v4-pro"
    assert 'MODEL="${AI_NOVELIST_DEEPSEEK_MODEL:-deepseek-v4-pro}"' in script
