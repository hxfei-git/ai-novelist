# Outline Save Progress Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure outline-stage save progress rows are completed after the artifact and state are written.

**Architecture:** Keep the existing SSE progress contract and frontend row merging. Update `graph_outline.py` so save steps are wrapped with the existing `run_with_progress()` helper, producing a matching completed event for the same `OutlineStage` key.

**Tech Stack:** Python 3.12, pytest, existing Web progress parsing tests.

---

### Task 1: Add Save Completion Regression

**Files:**
- Modify: `tests/test_web_service.py`
- Modify: `src/ai_novelist/graph_outline.py`

- [ ] **Step 1: Write failing test**

Add a Web service test that runs a light revision and captures progress events. Assert that the save message is followed by a completed save event with the same stage key.

- [ ] **Step 2: Verify RED**

Run `.venv/bin/python -m pytest tests/test_web_service.py::test_revise_outline_stage_completes_save_progress -q`. Expected: fail because only the running save event is emitted.

- [ ] **Step 3: Implement minimal fix**

Replace outline-stage save progress start-only emits with `run_with_progress(progress, "OutlineStage", save_message, save_fn)` so successful saves emit `已完成保存...` and failures emit `执行失败...`.

- [ ] **Step 4: Verify GREEN**

Run the same targeted test, then the affected Web tests.

### Task 2: Docs And Commit

**Files:**
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`
- Create: `docs/superpowers/plans/2026-05-29-outline-save-progress-completion.md`

- [ ] **Step 1: Save this plan under docs**
- [ ] **Step 2: Update required docs with behavior and verification**
- [ ] **Step 3: Run final verification and commit**
