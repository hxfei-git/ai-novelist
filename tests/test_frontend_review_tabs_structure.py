from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_TSX = ROOT / "web" / "frontend" / "src" / "main.tsx"
TYPES_TS = ROOT / "web" / "frontend" / "src" / "types.ts"
API_TS = ROOT / "web" / "frontend" / "src" / "api.ts"
STYLES_CSS = ROOT / "web" / "frontend" / "src" / "styles.css"
PROGRESS_TS = ROOT / "web" / "frontend" / "src" / "progress.ts"
WORKSPACES_DIR = ROOT / "web" / "frontend" / "src" / "workspaces"


def read_main() -> str:
    return MAIN_TSX.read_text(encoding="utf-8")


def read_types() -> str:
    return TYPES_TS.read_text(encoding="utf-8")


def read_api() -> str:
    return API_TS.read_text(encoding="utf-8")


def read_progress() -> str:
    return PROGRESS_TS.read_text(encoding="utf-8")


def read_workspace(name: str) -> str:
    return (WORKSPACES_DIR / name).read_text(encoding="utf-8")


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


def test_review_entries_move_into_sidebar_navigation() -> None:
    sidebar = sidebar_source(read_main())

    assert "章节批量生成" not in sidebar
    assert "已生成章节" not in sidebar
    assert "总体审查" in sidebar
    assert "setOutlineStageView('review')" in sidebar
    assert "setChapterOutlineView('review')" in sidebar
    assert "setChapterView('review')" in sidebar


def test_frontend_workspace_modules_exist_after_split() -> None:
    expected = [
        ROOT / "web" / "frontend" / "src" / "progress.ts",
        ROOT / "web" / "frontend" / "src" / "workspaces" / "review.tsx",
        ROOT / "web" / "frontend" / "src" / "workspaces" / "chapters.tsx",
        ROOT / "web" / "frontend" / "src" / "workspaces" / "outline.tsx",
        ROOT / "web" / "frontend" / "src" / "workspaces" / "chapterOutline.tsx",
        ROOT / "web" / "frontend" / "src" / "workspaces" / "project.tsx",
    ]
    for path in expected:
        assert path.exists(), path


def test_frontend_main_is_smaller_after_workspace_split() -> None:
    source = read_main()
    assert len(source.splitlines()) < 900
    assert "from './progress'" in source
    assert "from './workspaces/review'" in source


def test_top_navigation_has_three_workspaces() -> None:
    source = read_main()

    assert_union_type_includes(read_types(), "TopSection", "outline", "chapter-outline", "chapters")
    assert "topSection === 'outline'" in source
    assert "topSection === 'chapter-outline'" in source
    assert "topSection === 'chapters'" in source
    assert "setTopSection('outline')" in source
    assert "setTopSection('chapter-outline')" in source
    assert "setTopSection('chapters')" in source
    assert "大纲" in source
    assert "章节大纲" in source
    assert "章节正文" in source


def test_outline_workspace_uses_sidebar_review_navigation() -> None:
    source = read_main()

    assert_union_type_includes(read_types(), "OutlineStageView", "edit", "review")
    assert "outlineStageView === 'edit'" in source
    assert "outlineStageView === 'review'" in source
    assert "setOutlineStageView('edit')" in source
    assert "setOutlineStageView('review')" in source
    assert "OutlineReviewWorkspace" in source
    assert "setOutlineStageView('review')" in source

    sidebar = sidebar_source(source)
    assert "setOutlineStageView('review')" in sidebar


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
    assert "chapterOutlineView" in source
    assert "volume_specs" in source
    assert "selected_volume" in source
    assert "outline/chapter-workspace${query}" in source
    assert "outline/chapter-workspace/volumes/${volumeIndex}/${action}" in source
    assert "runChapterOutlineVolume(action: 'generate' | 'revise' | 'lock')" in source
    assert "outline/chapter-review" in source
    assert "setChapterOutlineView('review')" in source


def test_chapter_outline_workspace_uses_single_left_volume_navigation() -> None:
    source = read_main()
    workspace_block = read_workspace("chapterOutline.tsx")
    sidebar = sidebar_source(source)

    assert "(chapterOutlineWorkspace?.volume_specs || []).map" in sidebar
    assert "loadChapterOutlineWorkspace(item.index).catch(showError)" in sidebar
    assert "workspace.selected_volume.content" in workspace_block
    assert 'className="chapter-list volume-list"' not in workspace_block


def test_chapter_workspace_uses_volume_navigation_and_secondary_tabs() -> None:
    source = read_main() + read_workspace("chapters.tsx")

    assert 'aria-label="章节视图"' in source
    assert "chapterView === 'batch'" in source
    assert "chapterView === 'list'" in source
    assert "chapterView === 'review'" in source
    assert "setChapterView('batch')" in source
    assert "setChapterView('list')" in source
    assert "setChapterView('review')" in source

    sidebar = sidebar_source(source)
    assert "setChapterView('batch')" in sidebar
    assert "setChapterView('review')" in sidebar
    assert "volume === item.index" in sidebar


def test_chapter_batch_panel_uses_volume_summary_and_single_quantity_input() -> None:
    source = read_main() + read_workspace("chapters.tsx")
    start = source.index("{chapterView === 'batch' &&")
    end = source.index("{chapterView === 'list' &&", start)
    batch_block = source[start:end]

    assert "总章数" in batch_block
    assert "已生成章数" in batch_block
    assert "剩余章数" in batch_block
    assert "生成数量" in batch_block
    assert "卷号" not in batch_block
    assert "章节范围" not in batch_block
    assert "并发数" not in batch_block
    assert "Math.min(requestedCount, remainingChapters)" in source


def test_create_project_clears_progress_for_new_project_id() -> None:
    source = read_main()
    create_block = re.search(r"async function createProject\(\).*?\n  }", source, re.DOTALL)
    assert create_block is not None
    assert "async function saveProjectProgressLogForProject" in source
    assert "await saveProjectProgressLogForProject(state.project_id, [])" in create_block.group(0)
    assert "await saveProjectProgressLog([])" not in create_block.group(0)


def test_onboarding_save_does_not_prefill_outline_instruction() -> None:
    source = read_main()
    submit_block = re.search(r"async function submitOnboardingIdea\(\).*?\n  }", source, re.DOTALL)
    assert submit_block is not None
    block = submit_block.group(0)

    assert "setInstruction('')" in block
    assert "setInstruction(onboardingIdea.trim())" not in block


def test_background_transient_fetch_errors_are_not_persisted_to_progress_log() -> None:
    source = read_main()
    project_effect = re.search(r"useEffect\(\(\) => \{\n    if \(!projectId\) return;.*?\n  \}, \[projectId\]\);", source, re.DOTALL)
    stage_effect = re.search(r"useEffect\(\(\) => \{\n    if \(!projectId \|\| !activeStage\) return;.*?\n  \}, \[projectId, activeStage\]\);", source, re.DOTALL)

    assert "function showBackgroundError(error: unknown)" in source
    assert "isTransientFetchError(error)" in source
    assert project_effect is not None
    assert stage_effect is not None
    assert ".catch(showBackgroundError)" in project_effect.group(0)
    assert ".catch(showError)" not in project_effect.group(0)
    assert "loadStage(activeStage).catch(showBackgroundError)" in stage_effect.group(0)


def test_chapter_batch_generation_has_running_guard_and_disabled_button() -> None:
    source = read_main() + read_workspace("chapters.tsx")
    generate_block = re.search(r"async function generateBatch\(\).*?\n  }", source, re.DOTALL)
    assert generate_block is not None
    assert "const [chapterBatchRunning, setChapterBatchRunning] = useState(false)" in source
    assert "if (chapterBatchRunning) return;" in generate_block.group(0)
    assert "setChapterBatchRunning(true)" in generate_block.group(0)
    assert "setChapterBatchRunning(false)" in generate_block.group(0)
    assert "disabled={chapterBatchRunning || (chapterBatchWorkspace?.remaining_chapters ?? 0) < 1}" in source


def test_chapter_detail_loading_resets_in_finally_for_current_request() -> None:
    source = read_main()
    load_block = re.search(r"async function loadChapter\(chapter: number\).*?\n  }", source, re.DOTALL)
    assert load_block is not None
    block = load_block.group(0)
    assert "try {" in block
    assert "finally {" in block
    assert "if (token === chapterRequestRef.current && chapter === selectedChapter)" in block
    assert "setLoadingChapter(false)" in block.split("finally", 1)[1]


def test_chapter_batch_generation_reports_errors_and_releases_running_state() -> None:
    source = read_main()
    generate_block = re.search(r"async function generateBatch\(\).*?\n  }", source, re.DOTALL)
    assert generate_block is not None
    block = generate_block.group(0)
    assert "try {" in block
    assert "} catch (error) {" in block
    assert "showError(error)" in block
    assert "} finally {" in block


def test_streaming_workspace_actions_report_errors() -> None:
    source = read_main()
    for function_name in [
        "runStage",
        "runChapterOutlineVolume",
        "generateBatch",
        "runOutlineReview",
        "applyOutlineReview",
        "runChapterOutlineReview",
        "applyChapterOutlineReview",
        "submitPendingQuestions",
        "reviewAll",
    ]:
        block = re.search(rf"async function {function_name}\(.*?\n  }}", source, re.DOTALL)
        assert block is not None, function_name
        assert "} catch (error) {" in block.group(0), function_name
        assert "showError(error)" in block.group(0), function_name


def test_chapter_outline_volume_action_releases_running_flag_in_finally() -> None:
    source = read_main()
    block = re.search(r"async function runChapterOutlineVolume\(.*?\n  }", source, re.DOTALL)
    assert block is not None
    text = block.group(0)
    assert "setChapterOutlineRunning(true)" in text
    assert "setChapterOutlineRunning(false)" in text.split("finally", 1)[1]


def test_outline_review_uses_three_choice_decision_board() -> None:
    source = read_main() + read_workspace("review.tsx")
    apply_block = source[source.index("async function applyOutlineReview"):source.index("function dismissOutlineReview")]

    assert "outlineRepairDecisions" in source
    assert "OutlineRepairDecisionBoard" in source
    assert "推荐修改意见" in source
    assert "暂不修改" in source
    assert "我的意见" in source
    assert "custom_answer" in source
    assert "{ decisions }" in apply_block
    assert "selected_issue_ids" not in apply_block


def test_outline_review_apply_refreshes_updated_stage_after_success() -> None:
    source = read_main()
    api_source = read_api()
    stream_block = api_source[api_source.index("async function streamAction"):]
    apply_block = source[source.index("async function applyOutlineReview"):source.index("function dismissOutlineReview")]

    assert "let donePayload" in stream_block
    assert "eventLine?.slice(7) === 'done'" in stream_block
    assert "return donePayload" in stream_block
    assert "const applyResult = await streamAction" in apply_block
    assert "updated_stages" in apply_block
    assert "setTopSection('outline')" in apply_block
    assert "setActiveStage(targetStage)" in apply_block
    assert "targetStage === activeStage" in apply_block
    assert "await loadStage(targetStage)" in apply_block
    assert "setOutlineStageView('edit')" in apply_block


def test_right_progress_has_fixed_scroll_area() -> None:
    styles = read_styles()

    assert "height: 100vh" in styles
    assert ".progress-log" in styles
    assert "overflow: auto" in styles
    assert "min-height: 0" in styles


def test_outline_stage_actions_guard_against_double_submit() -> None:
    source = read_main() + read_workspace("outline.tsx")

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
    source = read_main() + read_workspace("outline.tsx")

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


def test_outline_stage_actions_clear_instruction_after_completion() -> None:
    source = read_main()

    run_stage = re.search(r"async function runStage\(.*?\n  }", source, re.DOTALL)
    assert run_stage is not None
    assert "setInstruction('');" in run_stage.group(0)
    assert run_stage.group(0).index("setInstruction('');") < run_stage.group(0).index("await refreshStages()")


def test_outline_stage_pending_questions_render_recommended_options() -> None:
    source = read_main() + read_workspace("outline.tsx")

    assert "type PendingQuestionPayload" in read_types()
    assert "outline/stages/${stage}/pending" in source
    assert "function PendingQuestionPanel" in source
    assert "提交确认" in source
    assert "pending/submit" in source
    assert "pendingCustomAnswers" in source
    assert "custom_answer" in source
    assert "请输入你的建议" in source
    submit_pending = re.search(r"async function submitPendingQuestions\(\).*?\n  }", source, re.DOTALL)
    assert submit_pending is not None
    assert "stageRunningRef.current" in submit_pending.group(0)


def test_stage_action_strip_and_lock_badge_have_distinct_styles() -> None:
    styles = read_styles()

    assert ".stage-action-bar" in styles
    assert ".stage-action-group" in styles
    assert ".lock-badge" in styles

def test_frontend_restores_new_project_onboarding_workspace() -> None:
    source = read_main() + read_workspace("project.tsx")

    assert "type ProjectState" in read_types()
    assert "const [projectState, setProjectState]" in source
    assert "const [onboardingIdea, setOnboardingIdea]" in source
    assert "needsOnboarding" in source
    assert "onboarding-workspace" in source
    assert "你想写一个什么样的故事" in source
    assert "projects/${projectId}/idea" in source


def test_progress_panel_renders_structured_metrics_and_keeps_legacy_branch() -> None:
    source = read_main()

    assert "type ProgressEvent" in read_types()
    assert "typeof item === 'string'" in source
    assert "item.elapsed" in source
    assert "item.tokens" in source
    assert "item.context" in source
    assert "latest.summary || '无摘要'" not in source


def test_progress_panel_merges_rows_by_key_and_renders_completion_metrics() -> None:
    source = read_main() + read_progress()

    assert "function upsertProgressItem" in source
    assert "progressItemKey(item)" in source
    assert "(item.key || item.label)" in source or "item.key || item.label" in source
    assert "[item.status, item.elapsed, item.tokens, item.context].filter(Boolean).join(' · ')" in source
    assert "pushLog(message: ProgressItem)" in source
    assert "void saveProjectProgressLog(next)" in source


def test_frontend_progress_log_uses_project_directory_api_not_local_storage() -> None:
    source = read_main()

    assert "projects/${projectId}/progress-log" in source
    assert "localStorage" not in source
    assert "progressLogKey" not in source


def test_frontend_progress_log_appends_new_items_to_the_bottom() -> None:
    source = read_progress()

    assert "return [...next, message].slice(-maxLogItems)" in source
