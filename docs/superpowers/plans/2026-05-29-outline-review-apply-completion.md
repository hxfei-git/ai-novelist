# Outline Review Apply Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make outline overall-review apply stay on the review page, show an in-place applying/completed state, and prevent duplicate application of the same review run.

**Architecture:** Persist applied metadata on the existing outline review report, then let the latest-review API expose that state after refresh. The frontend treats `review.applied === true` or `review.status === 'applied'` as terminal for the current run, disables duplicate apply, hides stale decision controls, and keeps the outline review workspace active while refreshing project/stage metadata in the background.

**Tech Stack:** Python 3.11, pytest, FastAPI SSE route helpers, React 19, TypeScript, Vite, lucide-react icons, CSS.

---

## File Structure

- Modify `src/ai_novelist/web/outline_service.py`: add file-only report rewrite helper and applied-state marker for persisted outline review reports.
- Modify `src/ai_novelist/web/outline_actions.py`: make `apply_outline_review()` idempotent for already-applied reports and mark reports applied after successful writes.
- Modify `web/frontend/src/types.ts`: expose optional applied metadata on `OutlineReview`.
- Modify `web/frontend/src/main.tsx`: keep the outline review view active after apply, optimistically mark current report applied, and refresh project/stage/latest-review data without navigation.
- Modify `web/frontend/src/workspaces/review.tsx`: render applying spinner, terminal "采纳完成" state, disabled apply button, and hidden decision table for applied reports.
- Modify `web/frontend/src/styles.css`: add spinner and completion banner styles.
- Modify `tests/test_web_service.py`: cover applied report persistence and idempotent reapply behavior.
- Modify `tests/test_frontend_review_tabs_structure.py`: cover frontend orchestration and review workspace source structure.
- Modify `docs/IMPLEMENTATION_PLAN.md` and `docs/SESSION_SUMMARY.md`: record the behavior change, verification commands, and residual browser-level risk.

## Task 1: Backend Applied State And Idempotent Apply

**Files:**
- Modify: `tests/test_web_service.py`
- Modify: `src/ai_novelist/web/outline_service.py`
- Modify: `src/ai_novelist/web/outline_actions.py`

- [x] **Step 1: Add backend RED tests**

In `tests/test_web_service.py`, add this adapter below `CapturingOutlineReviewAdapter`:

```python
class CountingOutlineApplyAdapter(AgentAdapter):
    def __init__(self) -> None:
        self.reviser_calls = 0

    def complete(self, prompt: str, workspace: Path, options: AgentCallOptions | None = None) -> str:
        if "outline_reviser" in prompt:
            self.reviser_calls += 1
            return "# 最终锁定总大纲\n\n## 方向定位\n幂等采纳后的大纲。"
        return "{}"
```

In `tests/test_web_service.py`, add these tests after `test_outline_review_roundtrip_and_apply_updates_outline`:

```python
def test_outline_review_apply_marks_latest_report_applied(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline = "# 最终锁定总大纲\n\n## 方向定位\n旧稿。"
    store.save_state(state)

    report = service.review_outline(store, OutlineReviewAdapter(), "web-demo", "请检查总纲")
    applied = service.apply_outline_review(store, OutlineReviewAdapter(), "web-demo", report["run_id"])
    latest = service.latest_outline_review_report(store, "web-demo")

    assert applied["applied"] is True
    assert latest["run_id"] == report["run_id"]
    assert latest["status"] == "applied"
    assert latest["applied"] is True
    assert latest["applied_at"]
    assert latest["applied_path"] == "outline.md"
    assert "direction" in latest["updated_stages"]
    assert isinstance(latest["skipped_stages"], list)


def test_apply_outline_review_is_idempotent_after_report_applied(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline = "# 最终锁定总大纲\n\n## 方向定位\n旧稿。"
    store.save_state(state)

    report = service.review_outline(store, OutlineReviewAdapter(), "web-demo", "请检查总纲")
    adapter = CountingOutlineApplyAdapter()

    first = service.apply_outline_review(store, adapter, "web-demo", report["run_id"])
    second = service.apply_outline_review(store, adapter, "web-demo", report["run_id"])

    assert first["applied"] is True
    assert second["applied"] is True
    assert second["already_applied"] is True
    assert second["status"] == "applied"
    assert second["applied_at"]
    assert second["applied_path"] == "outline.md"
    assert second["updated_stages"] == first["updated_stages"]
    assert adapter.reviser_calls == 1
```

- [x] **Step 2: Run backend RED tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_outline_review_apply_marks_latest_report_applied tests/test_web_service.py::test_apply_outline_review_is_idempotent_after_report_applied -q
```

Expected: both tests fail because latest reports are not marked `applied`, `already_applied` is absent, and the second apply still invokes the revision flow.

- [x] **Step 3: Add report file rewrite helpers**

In `src/ai_novelist/web/outline_service.py`, replace the body of `write_outline_review_report()` with a call to a new file-only helper, and add `mark_outline_review_applied()` immediately below it:

```python
def _write_outline_review_report_files(store: LocalStore, project_id: str, report: dict[str, Any]) -> tuple[Path, Path]:
    run_id = str(report.get("run_id") or "").strip()
    if not run_id:
        raise LocalStoreError("Outline review run_id is required")
    report_path, markdown_path = outline_review_report_paths(store, project_id, run_id)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_outline_review_markdown(report), encoding="utf-8")
    return report_path, markdown_path


def write_outline_review_report(store: LocalStore, state: NovelState, report: dict[str, Any]) -> tuple[Path, Path]:
    report_path, markdown_path = _write_outline_review_report_files(store, state.project_id, report)
    register_artifact(
        store.project_dir(state.project_id),
        ArtifactRecord(
            id="",
            type="outline_review",
            path=report_path.relative_to(store.project_dir(state.project_id)).as_posix(),
            source_agent="outline_editor",
            graph="outline",
            stage="outline_review",
            summary=str(report.get("summary") or "").strip(),
            metadata={
                "markdown_path": markdown_path.relative_to(store.project_dir(state.project_id)).as_posix(),
                "decision": str(report.get("decision") or ""),
            },
        ),
    )
    return report_path, markdown_path


def mark_outline_review_applied(
    store: LocalStore,
    state: NovelState,
    report: dict[str, Any],
    *,
    path: Path,
    updated_stages: list[str] | None = None,
    skipped_stages: list[str] | None = None,
) -> dict[str, Any]:
    applied_report = dict(report)
    applied_report.update(
        {
            "status": "applied",
            "applied": True,
            "applied_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "applied_path": path.relative_to(store.project_dir(state.project_id)).as_posix(),
            "updated_stages": list(updated_stages or []),
            "skipped_stages": list(skipped_stages or []),
        }
    )
    _write_outline_review_report_files(store, state.project_id, applied_report)
    return applied_report
```

- [x] **Step 4: Make outline review apply idempotent**

In `src/ai_novelist/web/outline_actions.py`, add `mark_outline_review_applied` to the existing `ai_novelist.web.outline_service` import list.

In `apply_outline_review()`, after `state = store.load_state(project_id)` and before reading `source_outline`, add this early return:

```python
    if report.get("applied") is True or str(report.get("status") or "").strip().lower() == "applied":
        updated_stages = report.get("updated_stages")
        skipped_stages = report.get("skipped_stages")
        return {
            "project_id": project_id,
            "run_id": run_id,
            "applied": True,
            "already_applied": True,
            "path": str(
                report.get("applied_path")
                or store.outline_path(project_id).relative_to(store.project_dir(project_id)).as_posix()
            ),
            "version_count": len(state.outline_versions),
            "updated_stages": [str(item) for item in updated_stages] if isinstance(updated_stages, list) else [],
            "skipped_stages": [str(item) for item in skipped_stages] if isinstance(skipped_stages, list) else [],
        }
```

In the `decision == "pass" and selected_issue_ids is None and decisions is None` branch, after `store.save_state(state)` and before `return`, add:

```python
        applied_report = mark_outline_review_applied(
            store,
            state,
            report,
            path=store.outline_path(project_id),
        )
```

Then include the applied metadata in that branch's return payload:

```python
            "status": applied_report.get("status"),
            "updated_stages": applied_report.get("updated_stages", []),
            "skipped_stages": applied_report.get("skipped_stages", []),
```

In the normal revision branch, after `store.save_state(compared)` and before the final `emit()`, add:

```python
    applied_report = mark_outline_review_applied(
        store,
        compared,
        report,
        path=store.outline_path(project_id),
        updated_stages=updated_stages,
        skipped_stages=skipped_stages,
    )
```

Then include the applied status in the final return payload:

```python
        "status": applied_report.get("status"),
```

- [x] **Step 5: Run backend target tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_outline_review_apply_marks_latest_report_applied tests/test_web_service.py::test_apply_outline_review_is_idempotent_after_report_applied tests/test_web_service.py::test_apply_outline_review_uses_recommended_custom_and_skip_decisions tests/test_web_service.py::test_apply_outline_review_rejects_empty_custom_decision tests/test_web_app.py::test_outline_review_apply_route_accepts_decisions -q
```

Expected: all selected backend/API tests pass.

- [x] **Step 6: Update backend docs and commit backend change**

Run:

```bash
git add src/ai_novelist/web/outline_service.py src/ai_novelist/web/outline_actions.py tests/test_web_service.py docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md docs/superpowers/plans/2026-05-29-outline-review-apply-completion.md
git commit -m "fix: mark outline review apply complete"
```


Backend Task 1 status: completed on 2026-05-29 with a follow-up spec correction. RED failed for missing persisted `applied` status and duplicate `already_applied`; follow-up RED failed for missing `applied_at`/`applied_path` on apply responses. Target backend/API verification passed with 5 selected tests. The backend commits include code, tests, and docs per repository policy.

## Task 2: Frontend Review Completion State

**Files:**
- Modify: `tests/test_frontend_review_tabs_structure.py`
- Modify: `web/frontend/src/types.ts`
- Modify: `web/frontend/src/main.tsx`
- Modify: `web/frontend/src/workspaces/review.tsx`
- Modify: `web/frontend/src/styles.css`

- [x] **Step 1: Add frontend RED tests**

In `tests/test_frontend_review_tabs_structure.py`, replace `test_outline_review_apply_refreshes_updated_stage_after_success()` with:

```python
def test_outline_review_apply_stays_on_review_after_success() -> None:
    source = read_main()
    api_source = read_api()
    stream_block = api_source[api_source.index("async function streamAction"):]
    apply_block = source[source.index("async function applyOutlineReview"):source.index("function dismissOutlineReview")]

    assert "let donePayload" in stream_block
    assert "eventLine?.slice(7) === 'done'" in stream_block
    assert "return donePayload" in stream_block
    assert "await streamAction" in apply_block
    assert "setOutlineReview((currentReview)" in apply_block
    assert "status: 'applied'" in apply_block
    assert "applied: true" in apply_block
    assert "await loadProjectState()" in apply_block
    assert "await refreshStages()" in apply_block
    assert "await loadLatestOutlineReview()" in apply_block
    assert "showBackgroundError(refreshError)" in apply_block
    assert "setOutlineStageView('edit')" not in apply_block
    assert "setActiveStage(targetStage)" not in apply_block
    assert "setTopSection('outline')" not in apply_block
```

Add these tests near `test_outline_review_uses_three_choice_decision_board()`:

```python
def test_outline_review_type_exposes_applied_metadata() -> None:
    source = read_types()

    assert "applied?: boolean" in source
    assert "applied_at?: string" in source
    assert "applied_path?: string" in source
    assert "updated_stages?: string[]" in source
    assert "skipped_stages?: string[]" in source


def test_outline_review_workspace_renders_apply_completion_state() -> None:
    source = read_workspace("review.tsx")

    assert "LoaderCircle" in source
    assert "const reviewApplied" in source
    assert "review?.applied === true" in source
    assert "review?.status === 'applied'" in source
    assert "采纳完成" in source
    assert "正在采纳" in source
    assert "spin-icon" in source
    assert "review-complete" in source
    assert "!reviewApplied && (review?.repair_suggestions || []).length > 0" in source
    assert "disabled={running || applying || reviewApplied || review?.decision === 'stop'}" in source


def test_outline_review_apply_spinner_styles_exist() -> None:
    styles = read_styles()

    assert "@keyframes review-spin" in styles
    assert ".spin-icon" in styles
    assert ".review-complete" in styles
    assert ".apply-loading" in styles
```

- [x] **Step 2: Run frontend RED tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py::test_outline_review_apply_stays_on_review_after_success tests/test_frontend_review_tabs_structure.py::test_outline_review_type_exposes_applied_metadata tests/test_frontend_review_tabs_structure.py::test_outline_review_workspace_renders_apply_completion_state tests/test_frontend_review_tabs_structure.py::test_outline_review_apply_spinner_styles_exist -q
```

Expected: tests fail because the frontend still navigates to edit view, `OutlineReview` lacks applied metadata, and the workspace has no terminal completion UI.

- [x] **Step 3: Extend the OutlineReview type**

In `web/frontend/src/types.ts`, update `OutlineReview` to include optional applied metadata:

```ts
export type OutlineReview = {
  project_id: string;
  run_id: string;
  created_at: string;
  status: string;
  applied?: boolean;
  applied_at?: string;
  applied_path?: string;
  updated_stages?: string[];
  skipped_stages?: string[];
  decision: string;
  score: number;
  summary: string;
  notes: string;
  revision_instruction: string;
  source_outline_summary: string;
  source_outline: string;
  repair_suggestions?: OutlineReviewSuggestion[];
};
```

- [x] **Step 4: Keep apply flow on the review view**

In `web/frontend/src/main.tsx`, replace the success body inside `applyOutlineReview()` with this logic:

```ts
      await streamAction(
        `/api/projects/${projectId}/outline/review/${outlineReview.run_id}/apply`,
        { decisions },
        (line) => pushLog(line),
      );
      setOutlineReview((currentReview) => (
        currentReview?.run_id === outlineReview.run_id ? { ...currentReview, status: 'applied', applied: true } : currentReview
      ));
      try {
        await loadProjectState();
        await refreshStages();
        await loadLatestOutlineReview();
      } catch (refreshError) {
        showBackgroundError(refreshError);
      }
      pushLog({ label: '大纲审查应用', model: '', elapsed: '', tokens: '', context: '', status: 'completed' });
```

Remove the old `applyResult`, `updatedStages`, `targetStage`, `setTopSection('outline')`, `setActiveStage(targetStage)`, `setOutlineStageView('edit')`, and `loadStage(targetStage)` logic from this function.

- [x] **Step 5: Render applying and applied states**

In `web/frontend/src/workspaces/review.tsx`, change the import line to:

```ts
import { Check, ListChecks, LoaderCircle, X } from 'lucide-react';
```

Inside `OutlineReviewWorkspace`, after `const hasReview = Boolean(review);`, add:

```ts
  const reviewApplied = review?.applied === true || review?.status === 'applied';
```

Update the review buttons to:

```tsx
            <div className="review-buttons">
              <button onClick={onDismiss} disabled={running || applying || reviewApplied}><X size={16} />不采纳</button>
              <button onClick={onApply} disabled={running || applying || reviewApplied || review?.decision === 'stop'}>
                {applying ? <LoaderCircle className="spin-icon" size={16} /> : <Check size={16} />}
                {applying ? '正在采纳' : reviewApplied ? '采纳完成' : '采纳选中项'}
              </button>
            </div>
```

After the `<small>参考大纲：{review?.source_outline_summary}</small>` line, add:

```tsx
          {reviewApplied && (
            <div className="review-complete">
              <Check size={16} />
              <span>采纳完成</span>
            </div>
          )}
```

Change the repair decision table condition to:

```tsx
          {!reviewApplied && (review?.repair_suggestions || []).length > 0 && (
```

Change the applying loading line at the bottom of the component to:

```tsx
      {applying && <div className="loading apply-loading"><LoaderCircle className="spin-icon" size={16} />正在采纳...</div>}
```

- [x] **Step 6: Add spinner and completion styles**

In `web/frontend/src/styles.css`, add these rules near the existing review styles:

```css
.apply-loading { display: inline-flex; align-items: center; gap: 8px; }
.review-complete { display: inline-flex; align-items: center; gap: 8px; width: fit-content; padding: 8px 10px; border: 1px solid #bbf7d0; border-radius: 6px; background: #f0fdf4; color: #166534; font-weight: 700; }
.spin-icon { animation: review-spin 1s linear infinite; }
@keyframes review-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
```

- [x] **Step 7: Run frontend target tests and build**

Run:

```bash
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py::test_outline_review_apply_stays_on_review_after_success tests/test_frontend_review_tabs_structure.py::test_outline_review_type_exposes_applied_metadata tests/test_frontend_review_tabs_structure.py::test_outline_review_workspace_renders_apply_completion_state tests/test_frontend_review_tabs_structure.py::test_outline_review_apply_spinner_styles_exist -q
npm --prefix web/frontend run build
```

Expected: the selected frontend structure tests pass, and the Vite build passes with only the known Vite CJS Node API deprecation warning if that warning appears.

- [x] **Step 8: Commit frontend change with docs**

Run:

```bash
git add web/frontend/src/types.ts web/frontend/src/main.tsx web/frontend/src/workspaces/review.tsx web/frontend/src/styles.css tests/test_frontend_review_tabs_structure.py docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md docs/superpowers/plans/2026-05-29-outline-review-apply-completion.md
git commit -m "fix: keep outline review apply in place"
```

## Task 3: Documentation And Final Verification

**Files:**
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [x] **Step 1: Run affected backend and frontend suites**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_frontend_review_tabs_structure.py -q
```

Expected: affected Web service, route, and frontend structure tests pass.

- [x] **Step 2: Run full persistence-safe pytest suite**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected: full pytest suite passes because the backend change updates persisted review report behavior.

- [x] **Step 3: Run frontend build**

Run:

```bash
npm --prefix web/frontend run build
```

Expected: frontend build passes with only the known Vite CJS Node API deprecation warning if that warning appears.

- [x] **Step 4: Update implementation plan documentation**

In `docs/IMPLEMENTATION_PLAN.md`, add this entry before `## Verification Policy`:

```markdown
### Phase 6f: Outline Review Apply Completion
- Files changed: outline review apply service/actions, Web frontend review workspace, frontend/backend regression tests, docs, and the Superpowers implementation plan.
- Behavior changed: applying selected outline overall-review suggestions now persists an applied report state, returns idempotent success for duplicate apply calls, keeps the browser on the "大纲总体审查" view, shows an applying spinner, and renders "采纳完成" instead of stale selectable issues after success.
- Verification: `.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_frontend_review_tabs_structure.py -q` passed; `.venv/bin/python -m pytest -q` passed; `npm --prefix web/frontend run build` passed with the known Vite CJS Node API deprecation warning if present.
- Remaining risk: coverage is service/source/build level; no browser-level click test was added for the long-running apply spinner.
- Next entry point: add browser-level review-apply interaction coverage if this UI flow regresses again.
```

Also add this plan file to the `## Current Reference Documents` list:

```markdown
- `docs/superpowers/plans/2026-05-29-outline-review-apply-completion.md`
```

- [x] **Step 5: Update session summary documentation**

In `docs/SESSION_SUMMARY.md`, add this entry above `## Remaining Risk`:

```markdown
### Follow-up: Outline Review Apply Completion
- Files changed: `src/ai_novelist/web/outline_service.py`, `src/ai_novelist/web/outline_actions.py`, `web/frontend/src/types.ts`, `web/frontend/src/main.tsx`, `web/frontend/src/workspaces/review.tsx`, `web/frontend/src/styles.css`, tests, docs, and `docs/superpowers/plans/2026-05-29-outline-review-apply-completion.md`.
- Behavior changed: outline overall-review apply now marks the persisted review report as applied, duplicate apply requests for the same run return idempotent success without rerunning revision, and the frontend stays on the "大纲总体审查" view with an applying spinner followed by "采纳完成".
- Verification: targeted RED tests failed before implementation for missing applied report state and review-page completion UI; affected-suite verification passed with `.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_frontend_review_tabs_structure.py -q`; full pytest passed with `.venv/bin/python -m pytest -q`; frontend build passed with `npm --prefix web/frontend run build`.
- Remaining risk: no live browser/SSE click test was added; source-structure tests verify the state handling and TypeScript build verifies the component compiles.
```

- [x] **Step 6: Run diff and status checks**

Run:

```bash
git diff --check
git status --short
```

Expected: `git diff --check` has no output. `git status --short` shows only the documentation files changed in this task.

- [x] **Step 7: Commit documentation change**

Run:

```bash
git add docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md docs/superpowers/plans/2026-05-29-outline-review-apply-completion.md
git commit -m "docs: record outline review apply completion"
```

- [x] **Step 8: Confirm final clean state**

Run:

```bash
git status --short
```

Expected: no output.

### Final Review Fix: Concurrent Duplicate Apply Guard
- [x] Added `test_apply_outline_review_concurrent_duplicate_waits_for_applied_report` to reproduce concurrent duplicate apply calls entering `outline_reviser` twice before persisted applied metadata exists.
- [x] Added a process-local apply lock keyed by `(project_id, run_id)` around report load, applied check, revision, state write, and report mark-applied write.
- [x] RED result: focused concurrency test failed with `assert 2 == 1` for `adapter.reviser_calls` before the lock.
- [x] GREEN result: focused server-side duplicate-apply tests passed with `.venv/bin/python -m pytest tests/test_web_service.py::test_apply_outline_review_concurrent_duplicate_waits_for_applied_report tests/test_web_service.py::test_apply_outline_review_is_idempotent_after_report_applied tests/test_web_service.py::test_outline_review_apply_marks_latest_report_applied -q`.
- [x] Final verification after the concurrency guard passed with `.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_frontend_review_tabs_structure.py -q` -> 125 passed in 1.33s; `.venv/bin/python -m pytest -q` -> 276 passed in 2.30s; `npm --prefix web/frontend run build` passed with the known Vite CJS Node API deprecation warning.

