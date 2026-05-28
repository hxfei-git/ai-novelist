from pathlib import Path

from ai_novelist.adapters.mock_codex import MockCodexAdapter


def test_mock_codex_adapter_routes_outline_agent(tmp_path: Path) -> None:
    adapter = MockCodexAdapter()

    output = adapter.complete("AGENT: outline_planner\n写作任务", tmp_path)

    assert "方向" in output or "大纲" in output


def test_mock_codex_adapter_routes_chapter_writer(tmp_path: Path) -> None:
    adapter = MockCodexAdapter()

    output = adapter.complete("AGENT: chapter_writer\n写作任务", tmp_path)

    assert "第" in output or "章节" in output
