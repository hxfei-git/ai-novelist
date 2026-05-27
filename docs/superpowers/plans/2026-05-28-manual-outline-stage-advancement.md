# Manual Outline Stage Advancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make outline and chapter-outline locks stop at the current stage or volume until the user manually chooses the next generation action.

**Architecture:** Keep the existing lock endpoint and `advance_outline_stage_node()` entry point, but change successful non-final lock branches so they save and return instead of advancing and invoking generation. Remove the duplicate chapter-outline volume selector from the right workspace while preserving left-sidebar navigation.

**Tech Stack:** Python 3.11+, pytest, FastAPI service layer, React/TypeScript, Vite.

---

### Task 1: Backend Lock Behavior

**Files:**
- Modify: `tests/test_web_service.py`
- Modify: `src/ai_novelist/graph_outline.py`

- [ ] **Step 1: Write failing backend tests**

Add tests that prove ordinary stage locks and chapter-outline volume locks do not auto-run the next generation.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_web_service.py::test_lock_outline_stage_stays_on_current_stage_without_auto_generation tests/test_web_service.py::test_lock_chapter_outline_volume_does_not_auto_generate_next_volume -q`

Expected: fail because current implementation advances and calls generation.

- [ ] **Step 3: Implement minimal backend change**

In `advance_outline_stage_node()`, replace successful non-final next-stage generation with a save-and-return lock result. In the chapter-outline selected-volume path, remove the next-volume generation directive and save the locked current volume.

- [ ] **Step 4: Run focused backend tests and verify GREEN**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_web_service.py::test_lock_outline_stage_stays_on_current_stage_without_auto_generation tests/test_web_service.py::test_lock_chapter_outline_volume_does_not_auto_generate_next_volume -q`

Expected: both pass.

### Task 2: Frontend Duplicate Volume Navigation

**Files:**
- Modify: `tests/test_frontend_review_tabs_structure.py`
- Modify: `web/frontend/src/main.tsx`
- Modify if needed: `web/frontend/src/styles.css`

- [ ] **Step 1: Write failing frontend structural test**

Add a source-structure test that extracts the `topSection === 'chapter-outline'` workspace and asserts the right-side `chapter-outline-layout` block does not contain `volume-list`, while the sidebar volume navigation remains present elsewhere.

- [ ] **Step 2: Run focused frontend test and verify RED**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py::test_chapter_outline_workspace_uses_single_left_volume_navigation -q`

Expected: fail because the right workspace still contains `volume-list`.

- [ ] **Step 3: Remove duplicate right-side volume list**

Delete the inner `<div className="chapter-list volume-list">...</div>` from the chapter-outline workspace and simplify the layout wrapper to a single content container.

- [ ] **Step 4: Run focused frontend test and verify GREEN**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py::test_chapter_outline_workspace_uses_single_left_volume_navigation -q`

Expected: pass.

### Task 3: Documentation, Verification, Commit

**Files:**
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Update docs**

Record the manual advancement behavior, the single chapter-outline volume navigation, and test scope.

- [ ] **Step 2: Run focused verification**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_web_service.py tests/test_frontend_review_tabs_structure.py -q`

Run: `npm --prefix web/frontend run build`

Expected: focused tests pass and frontend build succeeds.

- [ ] **Step 3: Commit**

Commit code, tests, and docs with: `git commit -m "feat: require manual outline stage advancement"`
