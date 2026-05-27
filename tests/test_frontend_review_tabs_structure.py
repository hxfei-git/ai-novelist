from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_TSX = ROOT / "web" / "frontend" / "src" / "main.tsx"
STYLES_CSS = ROOT / "web" / "frontend" / "src" / "styles.css"


def read_main() -> str:
    return MAIN_TSX.read_text(encoding="utf-8")


def sidebar_source(source: str) -> str:
    sidebar = re.search(r"<aside\b[^>]*className=\"sidebar\"[^>]*>", source)
    assert sidebar is not None

    workspace = re.search(r"<section\b[^>]*className=\"[^\"]*\bworkspace\b", source[sidebar.end() :])
    assert workspace is not None

    start = sidebar.start()
    end = sidebar.end() + workspace.start()
    return source[start:end]


def assert_union_type_includes(source: str, type_name: str, *values: str) -> None:
    union = re.search(rf"\btype\s+{re.escape(type_name)}\s*=\s*(?P<body>[^;]+);", source)
    assert union is not None

    body = union.group("body")
    for value in values:
        assert re.search(rf"['\"]{re.escape(value)}['\"]", body) is not None


def read_styles() -> str:
    return STYLES_CSS.read_text(encoding="utf-8")


def test_review_entries_are_not_sidebar_navigation() -> None:
    sidebar = sidebar_source(read_main())

    assert "章节批量生成" not in sidebar
    assert "已生成章节" not in sidebar
    assert "章节总体审查" not in sidebar
    assert "大纲总体审查" not in sidebar
    assert "总体审查" not in sidebar


def test_top_navigation_has_three_workspaces() -> None:
    source = read_main()

    assert_union_type_includes(source, "TopSection", "outline", "chapter-outline", "chapters")
    assert "topSection === 'outline'" in source
    assert "topSection === 'chapter-outline'" in source
    assert "topSection === 'chapters'" in source
    assert "setTopSection('outline')" in source
    assert "setTopSection('chapter-outline')" in source
    assert "setTopSection('chapters')" in source
    assert "大纲" in source
    assert "章节大纲" in source
    assert "章节正文" in source


def test_outline_workspace_uses_secondary_stage_review_tab() -> None:
    source = read_main()

    assert_union_type_includes(source, "OutlineStageView", "edit", "review")
    assert 'aria-label="大纲视图"' in source
    assert "outlineStageView === 'edit'" in source
    assert "outlineStageView === 'review'" in source
    assert "setOutlineStageView('edit')" in source
    assert "setOutlineStageView('review')" in source
    assert "outlineView === 'review'" not in source

    edit_start = source.index("{outlineStageView === 'edit' &&")
    review_start = source.index("{outlineStageView === 'review' &&")
    edit_block = source[edit_start:review_start]

    assert "runOutlineReview" not in edit_block
    assert "大纲总体审查" not in edit_block


def test_outline_workspace_no_longer_assumes_chapter_outline_is_ordinary_stage() -> None:
    source = read_main()

    assert "item.stage !== 'chapter_outline'" in source
    assert "loadChapterOutlineWorkspace" in source
    assert "outline/stages/${stage}" in source
    load_stage_block = source[source.index("async function loadStage") : source.index("async function saveStage")]
    assert "outline/stages/${stage}" in load_stage_block
    assert "chapter_outline" not in load_stage_block


def test_chapter_outline_workspace_uses_dedicated_volume_routes() -> None:
    source = read_main()

    assert "ChapterOutlineWorkspace" in source
    assert "volume_specs" in source
    assert "selected_volume" in source
    assert "outline/chapter-workspace${query}" in source
    assert "outline/chapter-workspace/volumes/${volumeIndex}/${action}" in source
    assert "runChapterOutlineVolume(action: 'generate' | 'revise' | 'lock')" in source
    assert "章节大纲按卷管理" in source


def test_chapter_workspace_uses_secondary_tabs() -> None:
    source = read_main()

    assert 'aria-label="章节视图"' in source
    assert "chapterView === 'batch'" in source
    assert "chapterView === 'list'" in source
    assert "chapterView === 'review'" in source
    assert "setChapterView('batch')" in source
    assert "setChapterView('list')" in source
    assert "setChapterView('review')" in source

    sidebar = sidebar_source(source)
    assert "setChapterView('batch')" not in sidebar
    assert "setChapterView('list')" not in sidebar
    assert "setChapterView('review')" not in sidebar

def test_outline_review_uses_selectable_suggestion_board() -> None:
    source = read_main()

    assert "selectedOutlineRepairIds" in source
    assert "OutlineRepairSuggestionBoard" in source
    assert "selected_issue_ids" in source
    assert "采纳选中项" in source


def test_right_progress_has_fixed_scroll_area() -> None:
    styles = read_styles()

    assert "height: 100vh" in styles
    assert ".progress-log" in styles
    assert "overflow: auto" in styles
    assert "min-height: 0" in styles


def test_outline_stage_actions_guard_against_double_submit() -> None:
    source = read_main()

    assert "const [stageRunning, setStageRunning] = useState(false)" in source
    assert "const stageRunningRef = useRef(false)" in source
    assert "if (stageRunningRef.current) return;" in source
    assert "stageRunningRef.current = true" in source
    assert "stageRunningRef.current = false" in source
    assert "setStageRunning(true)" in source
    assert "setStageRunning(false)" in source
    assert "disabled={loadingStage || running || !actionState.can_generate}" in source
    assert "disabled={loadingStage || running || !actionState.can_revise}" in source
    assert "disabled={loadingStage || running || !actionState.can_lock}" in source


def test_outline_stage_actions_are_separate_and_backend_driven() -> None:
    source = read_main()

    assert "action_state" in source
    assert "actionState.can_generate" in source
    assert "actionState.can_revise" in source
    assert "actionState.can_lock" in source
    assert "actionState.lock_reason" in source
    assert "onRun('generate')" in source
    assert "onRun('revise')" in source
    assert "onRun('lock')" in source
    assert "async function runStage(action: 'generate' | 'revise' | 'lock')" in source
    assert ">生成</button>" in source
    assert ">修订</button>" in source
    assert ">锁定</button>" in source
    assert "生成/修订" not in source


def test_stage_action_strip_and_lock_badge_have_distinct_styles() -> None:
    styles = read_styles()

    assert ".stage-action-bar" in styles
    assert ".stage-action-group" in styles
    assert ".lock-badge" in styles

def test_frontend_restores_new_project_onboarding_workspace() -> None:
    source = read_main()

    assert "type ProjectState" in source
    assert "const [projectState, setProjectState]" in source
    assert "const [onboardingIdea, setOnboardingIdea]" in source
    assert "needsOnboarding" in source
    assert "onboarding-workspace" in source
    assert "你想写一个什么样的故事" in source
    assert "projects/${projectId}/idea" in source


def test_frontend_progress_log_uses_project_directory_api_not_local_storage() -> None:
    source = read_main()

    assert "projects/${projectId}/progress-log" in source
    assert "localStorage" not in source
    assert "progressLogKey" not in source
