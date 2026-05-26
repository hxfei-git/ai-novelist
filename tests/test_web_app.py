from __future__ import annotations

import types

from ai_novelist.cli import build_parser
from ai_novelist.config import Settings
from ai_novelist.web import app as web_app


def test_web_parser_accepts_provider_model_and_timeout() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "web",
            "--provider",
            "deepseek",
            "--model",
            "deepseek-chat",
            "--timeout",
            "180",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ]
    )

    assert args.provider == "deepseek"
    assert args.model == "deepseek-chat"
    assert args.timeout == 180


def test_run_web_command_passes_generation_defaults(monkeypatch, tmp_path) -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "web",
            "--provider",
            "deepseek",
            "--model",
            "deepseek-chat",
            "--timeout",
            "180",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ]
    )
    captured = {}

    def fake_make_app(settings, *, mock=False, provider=None, model=None, timeout=None):
        captured["settings"] = settings
        captured["mock"] = mock
        captured["provider"] = provider
        captured["model"] = model
        captured["timeout"] = timeout
        return object()

    fake_uvicorn = types.SimpleNamespace(run=lambda app, host, port: captured.update({"host": host, "port": port}))

    monkeypatch.setattr(web_app, "make_app", fake_make_app)
    monkeypatch.setitem(__import__("sys").modules, "uvicorn", fake_uvicorn)

    result = web_app.run_web_command(args, Settings(projects_dir=tmp_path))

    assert result == 0
    assert captured["provider"] == "deepseek"
    assert captured["model"] == "deepseek-chat"
    assert captured["timeout"] == 180
    assert captured["mock"] is False
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 8000
