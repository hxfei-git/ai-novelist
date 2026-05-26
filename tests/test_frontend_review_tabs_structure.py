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


def test_outline_workspace_uses_secondary_review_tab() -> None:
    source = read_main()

    assert_union_type_includes(source, "OutlineView", "edit", "review")
    assert 'aria-label="大纲视图"' in source
    assert "outlineView === 'edit'" in source
    assert "outlineView === 'review'" in source
    assert "setOutlineView('edit')" in source
    assert "setOutlineView('review')" in source

    edit_start = source.index("{outlineView === 'edit' &&")
    review_start = source.index("{outlineView === 'review' &&")
    edit_block = source[edit_start:review_start]

    assert "runOutlineReview" not in edit_block
    assert "大纲总体审查" not in edit_block


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
