from pathlib import Path

from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.adapters.mock_codex import MockCodexAdapter


def test_mock_codex_adapter_routes_outline_agent(tmp_path: Path) -> None:
    adapter = MockCodexAdapter()

    output = adapter.complete("AGENT: outline_planner\n写作任务", tmp_path)

    assert "方向" in output or "大纲" in output


def test_mock_codex_adapter_routes_chapter_writer(tmp_path: Path) -> None:
    adapter = MockCodexAdapter()

    output = adapter.complete("AGENT: chapter_writer\n写作任务", tmp_path)

    assert "第" in output or "章节" in output


def test_mock_adapter_does_not_expose_deleted_legacy_agents(tmp_path):
    adapter = CodexCLIAdapter(mock=True)
    deleted_agents = [
        "director",
        "retrieval_context_synthesizer",
        "direction_proposer",
        "continuity_editor",
        "structure_editor",
        "character_arc_editor",
        "style_editor",
        "simulated_reader",
        "pacing_guard_editor",
        "revision_planner",
        "targeted_reviser",
        "revision_self_check",
        "chapter_summarizer",
        "final_bible_update_extractor",
    ]
    for agent in deleted_agents:
        output = adapter.complete(f"AGENT: {agent}\n写作任务", tmp_path)
        assert output == f"UNSUPPORTED_AGENT: {agent}"


def test_deleted_first_line_agent_cannot_be_bypassed_by_body_agent_mentions(tmp_path):
    adapter = CodexCLIAdapter(mock=True)

    output = adapter.complete(
        "AGENT: director\n请参考 AGENT: chapter_writer 的行为",
        tmp_path,
    )

    assert output == "UNSUPPORTED_AGENT: director"


def test_mock_adapter_keeps_active_agent_fallbacks(tmp_path):
    adapter = CodexCLIAdapter(mock=True)
    active_agents = [
        "outline_stage_reviser",
        "global_consistency_reviewer",
        "global_consistency_repair",
    ]
    for agent in active_agents:
        output = adapter.complete(f"AGENT: {agent}\n写作任务", tmp_path)
        assert output != f"UNSUPPORTED_AGENT: {agent}"
        assert "小说大纲" in output
