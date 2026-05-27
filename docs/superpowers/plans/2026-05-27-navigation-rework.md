# Navigation Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the Web UI into three top-level navigation areas, split generate/revise/lock into separate actions for every outline stage, and make lockability a backend-driven state instead of a frontend guess.

**Architecture:** Keep the existing file-backed project model and outline workflow, but expand the Web payloads so each stage exposes explicit action state. Split the frontend into three top-level workspaces (`大纲`, `章节大纲`, `章节正文`) and route all stage buttons through backend-reported `can_generate`, `can_revise`, and `can_lock` flags. Treat `chapter_outline` as a dedicated volume-based workspace, using the existing chapter-outline metadata helpers to render per-volume navigation and lock status.

**Tech Stack:** Python 3.11+, FastAPI, file-backed `LocalStore`, React + TypeScript + Vite, pytest.

---

## File Structure

- Modify `src/ai_novelist/web/service.py`: extend outline payloads with explicit action state, add chapter-outline workspace payload helpers, and keep lockability decisions on the server.
- Modify `src/ai_novelist/web/app.py`: expose explicit generate / revise / lock routes where needed and surface backend refusal reasons as HTTP/SSE responses.
- Modify `src/ai_novelist/outline/chapter_outline_structure.py`: expose volume-oriented helpers for the chapter-outline workspace payload and selected-volume rendering.
- Modify `web/frontend/src/main.tsx`: replace the current two-column outline/chapters navigation with three top-level workspaces, split generate/revise buttons, and render backend-driven lock state.
- Modify `web/frontend/src/styles.css`: restyle the top-level navigation, independent action bar, lock-state badge, and volume list layout.
- Modify `tests/test_web_service.py`: cover action-state payloads, lock gating, and chapter-outline workspace payload shape.
- Modify `tests/test_web_app.py`: cover route registration for the explicit action endpoints.
- Modify `tests/test_frontend_review_tabs_structure.py`: update structure assertions for the new top-level navigation and separated actions.
- Modify `tests/test_outline_stage_controls.py`: cover the backend-driven lockability semantics for outline stages.
- Modify `tests/test_graph_chapter_plan.py`: add coverage that chapter outline selection still feeds chapter planning correctly after the navigation split.
- Modify `tests/test_outline_collaboration.py`: keep the existing outline-stage migration and stage lifecycle assertions aligned with the new stage/action split.
- Modify `docs/IMPLEMENTATION_PLAN.md` and `docs/SESSION_SUMMARY.md`: required project documentation updates for the code change.

Note: this worktree already contains unrelated edits in `src/ai_novelist/web/service.py` and `tests/test_web_service.py`. Inspect those files before patching and preserve any existing user changes.

---

### Task 1: Define Backend Action State and Lockability Contracts

**Files:**
- Modify: `src/ai_novelist/web/service.py`
- Modify: `src/ai_novelist/web/app.py`
- Modify: `tests/test_web_service.py`
- Modify: `tests/test_web_app.py`

- [ ] **Step 1: Write the failing backend contract tests**

Add tests that assert the Web service now exposes explicit action state and lockability. Use the existing `LocalStore` fixture patterns already present in `tests/test_web_service.py`.

```python
def test_outline_stage_payload_includes_action_state(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage = "worldbuilding"
    state.outline_stage_artifacts["worldbuilding"] = {
        "stage": "worldbuilding",
        "label": "世界观设定",
        "status": "options_ready",
        "summary": "世界观草案。",
        "pending_questions": ["地理边界是否锁定？"],
    }
    store.save_state(state)

    payload = service.outline_stage_payload(store, state, "worldbuilding")

    assert payload["stage"] == "worldbuilding"
    assert payload["action_state"]["can_generate"] is True
    assert payload["action_state"]["can_revise"] is True
    assert payload["action_state"]["can_lock"] is False
    assert payload["action_state"]["lock_reason"] == "仍有待确认问题"
```

Add a second test that forces a locked stage and expects `can_lock=True` plus a ready reason.

```python
def test_outline_stage_payload_marks_locked_stage_as_lockable(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage = "characters"
    state.outline_stage_artifacts["characters"] = {
        "stage": "characters",
        "label": "人物关系",
        "status": "locked",
        "summary": "人物关系已锁定。",
        "pending_questions": [],
        "locked_at": "2026-05-27T12:00:00+00:00",
    }
    store.save_state(state)

    payload = service.outline_stage_payload(store, state, "characters")

    assert payload["action_state"]["can_lock"] is True
    assert payload["action_state"]["lock_reason"] == ""
```

Add a chapter-outline-specific test that asserts the payload is volume-oriented rather than a plain stage text payload.

```python
def test_chapter_outline_workspace_payload_includes_volume_navigation(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["volume_outline"] = {
        "stage": "volume_outline",
        "label": "分卷大纲",
        "status": "locked",
        "summary": "三卷结构。",
        "metadata": {"total_volumes": 3, "current_volume_index": 2, "completed_volumes": [1]},
    }
    state.outline_stage_artifacts["chapter_outline"] = {
        "stage": "chapter_outline",
        "label": "章节大纲",
        "status": "options_ready",
        "summary": "第二卷章节大纲草案。",
        "metadata": {
            "total_volumes": 3,
            "current_volume_index": 2,
            "completed_volumes": [1],
            "volume_statuses": {"1": "locked", "2": "options_ready", "3": "collecting"},
        },
    }
    store.save_state(state)

    payload = service.chapter_outline_workspace_payload(store, "web-demo")

    assert payload["current_volume_index"] == 2
    assert len(payload["volume_specs"]) == 3
    assert payload["selected_volume"]["index"] == 2
    assert payload["selected_volume"]["can_lock"] is False
```

Add route registration tests in `tests/test_web_app.py` that verify the explicit generate / revise / lock endpoints exist for outline stages and chapter-outline volumes, and that the route names are not collapsed into one generic action path.

- [ ] **Step 2: Run the backend contract tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_web_service.py::test_outline_stage_payload_includes_action_state \
  tests/test_web_service.py::test_outline_stage_payload_marks_locked_stage_as_lockable \
  tests/test_web_service.py::test_chapter_outline_workspace_payload_includes_volume_navigation \
  tests/test_web_app.py -q
```

Expected: fail because `action_state`, `chapter_outline_workspace_payload`, or the explicit endpoints do not yet exist.

- [ ] **Step 3: Implement the backend contract**

Update `src/ai_novelist/web/service.py` around the existing outline payload helpers.

Add a small action-state builder that is pure and easy to test:

```python
def build_outline_action_state(status: str, pending_questions: list[str], locked_at: str = "") -> dict[str, Any]:
    can_generate = status != "locked"
    can_revise = status in {"options_ready", "revision_requested", "locked"}
    can_lock = status == "locked" or (status == "options_ready" and not pending_questions and bool(locked_at))
    if status == "locked":
        lock_reason = ""
    elif pending_questions:
        lock_reason = f"仍有 {len(pending_questions)} 个待确认问题"
    else:
        lock_reason = "后端尚未确认锁定条件"
    return {
        "can_generate": can_generate,
        "can_revise": can_revise,
        "can_lock": can_lock,
        "lock_reason": lock_reason,
    }
```

Add a helper for the chapter-outline workspace payload by reusing `chapter_outline_metadata_from_artifact()` and `current_volume_spec()` from `src/ai_novelist/outline/chapter_outline_structure.py`.

```python
def chapter_outline_workspace_payload(store: LocalStore, project_id: str) -> dict[str, Any]:
    state = store.load_state(project_id)
    volume_artifact = state.outline_stage_artifacts.get("volume_outline")
    chapter_artifact = state.outline_stage_artifacts.get("chapter_outline")
    volume_outline = str(volume_artifact.get("synthesis") or volume_artifact.get("summary") or "") if isinstance(volume_artifact, dict) else ""
    metadata = chapter_outline_metadata_from_artifact(chapter_artifact if isinstance(chapter_artifact, dict) else None, volume_outline)
    selected = current_volume_spec(metadata)
    selected_content = extract_chapter_outline_slice(store.load_outline_artifact(project_id, "chapter_outline"), selected.index)
    return {
        "current_volume_index": metadata["current_volume_index"],
        "total_volumes": metadata["total_volumes"],
        "completed_volumes": metadata["completed_volumes"],
        "volume_specs": metadata["volume_specs"],
        "volume_statuses": metadata["volume_statuses"],
        "selected_volume": {
            "index": selected.index,
            "label": selected.label,
            "name": selected.name,
            "status": metadata["volume_statuses"].get(str(selected.index), "collecting"),
            "summary": summarize_text(selected_content),
            "content": selected_content,
            "can_generate": metadata["volume_statuses"].get(str(selected.index), "collecting") != "locked",
            "can_revise": metadata["volume_statuses"].get(str(selected.index), "collecting") in {"options_ready", "revision_requested", "locked"},
            "can_lock": metadata["volume_statuses"].get(str(selected.index), "collecting") == "locked",
            "lock_reason": "",
        },
    }
```

Wire `outline_stage_payload()` so it returns `action_state` for every ordinary outline stage, and ensure `outline_stage_list()` still hides `review_lock` from the general outline sidebar.

If the backend currently only exposes `generate` and `lock`, add a dedicated `revise` route beside them in `src/ai_novelist/web/app.py`, and dispatch it through a new service helper that reuses `run_outline_stage_node()` with revision intent rather than lock intent.

- [ ] **Step 4: Run the backend tests and confirm the new contracts pass**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_web_service.py::test_outline_stage_payload_includes_action_state \
  tests/test_web_service.py::test_outline_stage_payload_marks_locked_stage_as_lockable \
  tests/test_web_service.py::test_chapter_outline_workspace_payload_includes_volume_navigation \
  tests/test_web_app.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the backend contract**

```bash
git add src/ai_novelist/web/service.py src/ai_novelist/web/app.py tests/test_web_service.py tests/test_web_app.py
git commit -m "feat: expose outline action state"
```

---

### Task 2: Split the Frontend into Three Top-Level Workspaces

**Files:**
- Modify: `web/frontend/src/main.tsx`
- Modify: `web/frontend/src/styles.css`
- Test: `tests/test_frontend_review_tabs_structure.py`

- [ ] **Step 1: Write the failing navigation structure tests**

Update `tests/test_frontend_review_tabs_structure.py` so it asserts the new top-level navigation and the absence of the old two-way split.

```python
def test_top_navigation_has_three_workspaces() -> None:
    source = read_main()

    assert "topSection === 'outline'" in source
    assert "topSection === 'chapter-outline'" in source
    assert "topSection === 'chapters'" in source
    assert "setTopSection('outline')" in source
    assert "setTopSection('chapter-outline')" in source
    assert "setTopSection('chapters')" in source
    assert "大纲" in source
    assert "章节大纲" in source
    assert "章节正文" in source


def test_outline_workspace_no_longer_renders_review_tabs_inline() -> None:
    source = read_main()
    assert "outlineView === 'review'" not in source
    assert "章节大纲" not in source[source.index("topSection === 'outline'"):source.index("topSection === 'chapters'")]
```

Add a style check for the new action strip and lock badge:

```python
def test_stage_action_strip_and_lock_badge_have_distinct_styles() -> None:
    styles = read_styles()

    assert ".stage-action-bar" in styles
    assert ".stage-action-group" in styles
    assert ".lock-badge" in styles
```

- [ ] **Step 2: Run the frontend structure tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py -q
```

Expected: fail because the new top-level navigation and style hooks do not exist yet.

- [ ] **Step 3: Implement the three-workspace shell**

Refactor `web/frontend/src/main.tsx` so the top-level workspace state becomes:

```ts
type TopSection = 'outline' | 'chapter-outline' | 'chapters';
```

Replace the current `outlineView` / `chapterView` split with:

- `outlineStageView` for stage editing vs outline review inside the `大纲` workspace.
- `chapterOutlineView` for the volume navigator and current-volume editor inside the `章节大纲` workspace.
- `chapterView` stays as batch/list/review inside the `章节正文` workspace.

Keep the left sidebar as the project and navigation rail, but change the top buttons to three tabs. The `章节大纲` tab should render a dedicated work area instead of an inline stage tab inside `大纲`.

Add a shared stage action bar component pattern inside `main.tsx` or extracted local helpers so every outline stage shows:

- current status
- separate `生成` button
- separate `修订` button
- separate `锁定` button
- `lock_reason`

Use the backend `action_state` flags to enable or disable each button. Do not infer lockability from local text.

Rework the outline workspace so the `chapter_outline` item disappears from the ordinary stage list and appears only in the new `章节大纲` top-level workspace.

For `章节大纲`, render:

- a dynamic volume list on the left
- the selected volume title and status on the right
- independent `生成 / 修订 / 锁定` buttons for the selected volume
- the backend-provided `lock_reason`

Keep `章节正文` unchanged except for its top-level entry point and any shared shell layout updates needed by the new top navigation.

- [ ] **Step 4: Run the frontend structure tests and confirm the shell change passes**

Run:

```bash
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the shell refactor**

```bash
git add web/frontend/src/main.tsx web/frontend/src/styles.css tests/test_frontend_review_tabs_structure.py
git commit -m "feat: split outline workspaces"
```

---

### Task 3: Implement Chapter-Outline Volume Navigation and Per-Volume Locking

**Files:**
- Modify: `src/ai_novelist/outline/chapter_outline_structure.py`
- Modify: `src/ai_novelist/web/service.py`
- Modify: `web/frontend/src/main.tsx`
- Test: `tests/test_graph_chapter_plan.py`
- Test: `tests/test_outline_collaboration.py`

- [ ] **Step 1: Write the failing volume-navigation tests**

Add a service-level test that the selected chapter-outline volume is derived from metadata and that the selected slice matches the current volume.

```python
def test_chapter_outline_workspace_selects_current_volume_slice(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["volume_outline"] = {
        "stage": "volume_outline",
        "label": "分卷大纲",
        "status": "locked",
        "summary": "三卷结构。",
        "metadata": {"total_volumes": 3, "current_volume_index": 2, "completed_volumes": [1]},
    }
    state.outline_stage_artifacts["chapter_outline"] = {
        "stage": "chapter_outline",
        "label": "章节大纲",
        "status": "options_ready",
        "summary": "第二卷章节大纲草案。",
        "metadata": {
            "total_volumes": 3,
            "current_volume_index": 2,
            "completed_volumes": [1],
            "volume_statuses": {"1": "locked", "2": "options_ready", "3": "collecting"},
            "volume_contents": {"2": "### 第二卷\n\n#### 卷内章节总体规划\n- ..."},
        },
    }
    store.save_state(state)

    payload = service.chapter_outline_workspace_payload(store, "web-demo")

    assert payload["selected_volume"]["index"] == 2
    assert "第二卷" in payload["selected_volume"]["content"]
```

Add a graph-level test that chapter planning still reads the selected chapter-outline slice after the navigation split.

```python
def test_collect_chapter_outline_returns_selected_volume_slice(tmp_path):
    store = LocalStore(tmp_path)
    state = make_ready_state(store)
    state.current_chapter = 2
    state.active_chapter = 2
    state.outline_stage_artifacts["chapter_outline"] = {
        "stage": "chapter_outline",
        "label": "章节大纲",
        "synthesis": "### 第一卷\n\n#### 第 2 章：失效编号\n- 本章只属于第二章。",
        "metadata": {"total_volumes": 1, "current_volume_index": 1, "completed_volumes": []},
    }
    store.save_outline_artifact(state, "chapter_outline", "### 第一卷\n\n#### 第 2 章：失效编号\n- 本章只属于第二章。")
    store.save_state(state)

    selected = collect_chapter_outline(state, store)

    assert "第 2 章：失效编号" in selected
```

Extend outline collaboration coverage to assert that `chapter_outline` remains a locked stage in the workflow, but is no longer rendered inside the general outline sidebar.

- [ ] **Step 2: Run the volume-navigation tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_graph_chapter_plan.py::test_collect_chapter_outline_returns_target_chapter_slice tests/test_outline_collaboration.py::test_outline_stage_view_can_show_story_flow -q
```

Expected: fail until the chapter-outline workspace returns the right volume slice and the frontend reads it.

- [ ] **Step 3: Implement the chapter-outline workspace**

In `src/ai_novelist/outline/chapter_outline_structure.py`, add a small helper that resolves the selected volume index from metadata and a helper that packages the current volume into a frontend-ready object. Reuse the existing `extract_volume_specs()`, `current_volume_spec()`, and `extract_chapter_outline_slice()` functions instead of inventing a parallel parser.

In `src/ai_novelist/web/service.py`, make the chapter-outline payload return:

- `volume_specs`
- `current_volume_index`
- `completed_volumes`
- `volume_statuses`
- `selected_volume`

Ensure `selected_volume` includes the backend decision fields:

- `can_generate`
- `can_revise`
- `can_lock`
- `lock_reason`

If the selected volume is not lockable, compute a human-readable reason from the metadata and pending-question state. The frontend should only display the string.

In `web/frontend/src/main.tsx`, render the chapter list as the dynamic volume navigator:

- each volume button shows its label and state
- selecting a volume loads that volume’s slice
- `生成` and `修订` are distinct buttons
- `锁定` is disabled when `can_lock` is false
- the selected volume’s lock reason is visible beside the buttons

Do not move `chapter_outline` back into the ordinary outline sidebar.

- [ ] **Step 4: Run the chapter-outline tests and confirm the volume workspace passes**

Run:

```bash
.venv/bin/python -m pytest tests/test_graph_chapter_plan.py tests/test_outline_collaboration.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the chapter-outline work**

```bash
git add src/ai_novelist/outline/chapter_outline_structure.py src/ai_novelist/web/service.py web/frontend/src/main.tsx tests/test_graph_chapter_plan.py tests/test_outline_collaboration.py
git commit -m "feat: add chapter outline volume workspace"
```

---

### Task 4: Update Documentation and Final Verification

**Files:**
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`
- Test: `tests/test_web_service.py`
- Test: `tests/test_frontend_review_tabs_structure.py`
- Test: `tests/test_outline_stage_controls.py`

- [ ] **Step 1: Write the documentation update tests and checks**

Before finalizing docs, re-run the structure and backend tests that cover the new navigation, action state, and lockability behavior.

```bash
.venv/bin/python -m pytest \
  tests/test_web_service.py \
  tests/test_frontend_review_tabs_structure.py \
  tests/test_outline_stage_controls.py \
  -q
```

Expected: PASS once the code changes are complete.

- [ ] **Step 2: Update the project documentation**

Add a short implementation note to `docs/IMPLEMENTATION_PLAN.md` describing:

- three top-level workspaces
- explicit generate / revise / lock actions
- backend-driven lockability
- dedicated chapter-outline volume workspace

Add a matching note to `docs/SESSION_SUMMARY.md` with:

- what changed
- which files were touched
- which tests were run
- any remaining follow-up work

- [ ] **Step 3: Run the full targeted verification suite**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_web_service.py \
  tests/test_web_app.py \
  tests/test_frontend_review_tabs_structure.py \
  tests/test_outline_stage_controls.py \
  tests/test_graph_chapter_plan.py \
  tests/test_outline_collaboration.py \
  -q
```

Expected: PASS.

- [ ] **Step 4: Commit the docs and final code**

```bash
git add docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "docs: record navigation rework implementation"
```

---

## Review Checklist

Before handing off the implementation, verify:

- `chapter_outline` no longer appears in the ordinary outline sidebar.
- The top-level navigation has exactly three workspaces.
- Every outline stage renders separate `生成`, `修订`, and `锁定` controls.
- `锁定` is disabled when backend state says the stage or volume is not lockable.
- The chapter-outline workspace uses volume metadata instead of a flat stage list.
- The docs mention the new structure and the verification commands that were run.

