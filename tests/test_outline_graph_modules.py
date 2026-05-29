from pathlib import Path

from ai_novelist import graph_outline
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore
from ai_novelist.outline_graph.artifact_io import summarize_stage_text
from ai_novelist.outline_graph.prompts import (
    outline_stage_boundary_prompt,
    stage_continuity_requirement,
)
from ai_novelist.outline_graph.review_lock import (
    extract_review_lock_issue_buckets,
    review_lock_blocking_issues,
    review_lock_issue_lines,
)
from ai_novelist.outline_graph.routing import (
    detect_stage_reference,
    is_lock_request,
    next_outline_stage,
)


def test_review_lock_helpers_parse_blocking_and_detail_issues() -> None:
    markdown = """
## 审稿锁定
BLOCKING:
- 人物动机缺失
DETAIL:
- 道具名称需统一
"""
    buckets = extract_review_lock_issue_buckets(markdown)

    assert review_lock_blocking_issues(buckets) == ["人物动机缺失"]
    assert "道具名称需统一" in review_lock_issue_lines(buckets)


def test_routing_helpers_detect_lock_and_stage_reference() -> None:
    assert is_lock_request("锁定世界观并进入下一阶段")
    assert detect_stage_reference("请修订人物阶段") == "characters"
    assert next_outline_stage("characters") == "story_flow"


def test_prompt_helpers_return_stage_specific_rules() -> None:
    assert "完整小说世界大纲" in outline_stage_boundary_prompt("worldbuilding")
    assert "世界观规则" in stage_continuity_requirement("characters")


def test_artifact_io_summary_compacts_markdown() -> None:
    text = "# 标题\n\n" + "内容" * 500
    summary = summarize_stage_text(text, max_chars=30)
    assert len(summary) <= 33
    assert "\n" not in summary


def test_graph_outline_light_revision_chapter_path_resolves_moved_prompt_helper(tmp_path) -> None:
    state = NovelState(
        project_id="runtime-imports",
        title="Runtime Imports",
        user_request="请轻修订当前章纲",
        director_intent="revise",
    )
    store = LocalStore(tmp_path)
    artifact = {"stage": "chapter_outline", "synthesis": "## 第 1 卷章节大纲\n\n- 第 1 章：开端"}

    assert graph_outline.should_lightly_revise_outline_stage(state, "chapter_outline", artifact, store)


def test_graph_outline_revision_prompt_resolves_moved_prompt_helpers() -> None:
    state = NovelState(
        project_id="runtime-imports",
        title="Runtime Imports",
        user_request="调整人物关系动机",
        director_intent="revise",
    )

    prompt = graph_outline.build_outline_stage_revision_prompt(
        state=state,
        stage="characters",
        current_markdown="## 人物关系稿\n\n- 主角与导师存在信任裂痕。",
    )

    assert "世界观规则" in prompt
    assert "STAGE_BOUNDARY" in prompt


def test_graph_outline_chapter_volume_helpers_remain_runtime_globals() -> None:
    assert graph_outline.chapter_outline_has_next_volume({"current_volume_index": 1, "total_volumes": 2})
    assert callable(graph_outline.normalize_generated_volume_outline)
    assert callable(graph_outline.merge_chapter_outline_volumes)


def test_outline_graph_no_longer_loads_deleted_director_prompt():
    source = Path("src/ai_novelist/graph_outline.py").read_text(encoding="utf-8")
    deleted_helpers = [
        'load_prompt("director")',
        "def build_outline_director_prompt",
        "def parse_outline_director_output",
        "def normalize_outline_director_action",
        "def outline_show_outline_node",
        "def outline_show_status_node",
    ]
    for helper in deleted_helpers:
        assert helper not in source


def test_outline_routing_no_longer_exports_director_only_routes():
    source = Path("src/ai_novelist/outline_graph/routing.py").read_text(encoding="utf-8")
    assert "route_after_outline_director" not in source
    assert "stage_action_from_director" not in source
    assert "should_defer_stage_confirmation_to_director" not in source
