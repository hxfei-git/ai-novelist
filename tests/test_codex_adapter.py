import subprocess

import pytest

from ai_novelist.adapters.base import AgentCallOptions
from ai_novelist.adapters.codex_cli import CodexCLIAdapter, CodexCLIError


def test_mock_adapter_returns_outline(tmp_path):
    adapter = CodexCLIAdapter(mock=True)

    result = adapter.complete("用户创意：月球城市", tmp_path)

    assert "# 小说大纲" in result
    assert "月球城市" in result


def test_adapter_accepts_call_options_in_mock_mode(tmp_path):
    adapter = CodexCLIAdapter(mock=True)

    result = adapter.complete(
        "用户创意：月球城市",
        tmp_path,
        options=AgentCallOptions(agent="chapter_writer", task="draft", stage="chapter"),
    )

    assert "# 小说大纲" in result


def test_adapter_command_does_not_add_reasoning_config(monkeypatch, tmp_path):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout='{"message":"final"}\n', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    adapter = CodexCLIAdapter()

    assert adapter.complete(
        "prompt",
        tmp_path,
        options=AgentCallOptions(agent="chapter_writer", task="draft", stage="chapter"),
    ) == "final"
    assert "-c" not in captured["command"]
    assert not any("reasoning" in part for part in captured["command"])


def test_adapter_extracts_json_message(monkeypatch, tmp_path):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout='{"message":"final"}\n', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    adapter = CodexCLIAdapter()

    assert adapter.complete("prompt", tmp_path) == "final"


def test_adapter_raises_on_nonzero(monkeypatch, tmp_path):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 1, stdout="", stderr="failed")

    monkeypatch.setattr(subprocess, "run", fake_run)

    adapter = CodexCLIAdapter()

    with pytest.raises(CodexCLIError):
        adapter.complete("prompt", tmp_path)


def test_adapter_extracts_item_text(monkeypatch, tmp_path):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args[0],
            0,
            stdout='{"type":"item.completed","item":{"type":"agent_message","text":"markdown"}}\n',
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    adapter = CodexCLIAdapter()

    assert adapter.complete("prompt", tmp_path) == "markdown"
