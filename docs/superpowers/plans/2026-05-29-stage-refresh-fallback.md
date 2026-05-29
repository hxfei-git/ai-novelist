# Stage Refresh Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep generated outline-stage content visible when post-generation refresh has a transient browser fetch failure.

**Architecture:** Preserve the existing backend save and SSE progress flow. Change the frontend so `loadStage()` keeps existing content while a refresh is pending, and so `runStage()` treats transient refresh failures after a successful stream as background refresh noise instead of appending `error: Failed to fetch` to the project progress log.

**Tech Stack:** React/TypeScript frontend, Python source-structure tests, Vite build.

---

### Task 1: Frontend Refresh Fallback

**Files:**
- Modify: `web/frontend/src/main.tsx`
- Test: `tests/test_frontend_review_tabs_structure.py`

- [ ] **Step 1: Write failing structure tests**

Add tests that assert `loadStage()` does not call `setContent('')` before the request completes, and that `runStage()` wraps `refreshStages()` plus `loadStage(activeStage)` in a nested `try/catch` that calls `showBackgroundError(refreshError)`.

- [ ] **Step 2: Verify RED**

Run `.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py::test_stage_load_preserves_existing_content_while_refreshing tests/test_frontend_review_tabs_structure.py::test_run_stage_does_not_log_transient_post_stream_refresh_failure -q`.

Expected: fail because current code clears content before fetching and logs post-stream refresh failures through `showError`.

- [ ] **Step 3: Implement minimal frontend fix**

Remove pre-request content clearing from `loadStage()`. In `runStage()`, keep `streamAction()` inside the user-action `try/catch`, then wrap `refreshStages()` and `loadStage(activeStage)` in an inner `try/catch` that calls `showBackgroundError(refreshError)`.

- [ ] **Step 4: Verify GREEN**

Run the targeted tests, then `tests/test_frontend_review_tabs_structure.py`, frontend build, and `git diff --check`.

### Task 2: Docs, Local Log Cleanup, And Commit

**Files:**
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`
- Create: `docs/superpowers/plans/2026-05-29-stage-refresh-fallback.md`

- [ ] **Step 1: Remove stale generated `error: Failed to fetch` from `projects/demo-web/web_progress_log.json`**
- [ ] **Step 2: Update required docs with root cause, behavior, verification, and residual risk**
- [ ] **Step 3: Commit code, tests, and docs**
