# Progress Order And Model Metrics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Web progress panel show newest entries first and include model plus elapsed time in model-cost rows.

**Architecture:** Keep the file-backed progress log contract and current structured `ProgressEvent` flow. Extend the backend event parser to preserve a compact `model` field and parse elapsed time from both slash-separated and pipe-separated metadata. Reverse only the rendered list in the frontend so persisted logs remain in chronological append order.

**Tech Stack:** Python 3.12 service tests with `pytest`; React/TypeScript source structure checks; existing Vite frontend build.

---

### Task 1: Backend Progress Event Metrics

**Files:**
- Modify: `src/ai_novelist/web/project_service.py`
- Test: `tests/test_web_service.py`

- [ ] **Step 1: Write the failing backend tests**

Add a test asserting that `build_progress_event()` returns `model` and `elapsed` from pipe-separated metadata:

```python
def test_progress_event_includes_model_and_elapsed_from_pipe_metadata() -> None:
    event = service.build_progress_event(
        "OutlineStage",
        "已完成正在汇总「世界观设定」阶段产物（deepseek-v4-pro | medium | 12.4s | ctx=4K/1M | tok≈8.1K）",
    )

    assert event == {
        "key": "OutlineStage",
        "label": "正在汇总「世界观设定」阶段产物",
        "model": "deepseek-v4-pro",
        "elapsed": "12.4s",
        "tokens": "tok≈8.1K",
        "context": "ctx=4K/1M",
        "status": "completed",
    }
```

Update the existing structured progress log test fixture to include `"model": "deepseek-v4-pro"` in an event, proving persistence accepts the new field.

Add a boundary test proving model parsing stays blank when a legacy metric row has no model:

```python
def test_progress_event_without_model_does_not_use_context_capacity_as_model() -> None:
    event = service.build_progress_event(
        "OutlineStage",
        "已完成加载上下文（12.4s/ctx=4K/258K/tok≈8.1K）",
    )

    assert event["model"] == ""
    assert event["context"] == "ctx=4K/258K"
```

- [ ] **Step 2: Run backend tests and confirm RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_progress_event_includes_model_and_elapsed_from_pipe_metadata tests/test_web_service.py::test_progress_event_without_model_does_not_use_context_capacity_as_model tests/test_web_service.py::test_project_progress_log_accepts_legacy_strings_and_structured_events -q
```

Expected: the new parser test fails because `model` is not returned yet.

- [ ] **Step 3: Implement backend parsing**

In `normalize_progress_log_items()`, include `model` in the preserved event keys.

In `build_progress_event()`, parse metadata inside the trailing Chinese parentheses, split it on `|` first and `/` second, and use only the first non-metric metadata part as the model, and return:

```python
"model": model_value,
"elapsed": elapsed_value,
```

Keep existing `tokens`, `context`, `key`, `label`, and `status` behavior.

- [ ] **Step 4: Run backend tests and confirm GREEN**

Run the same backend command. Expected: all backend tests pass.

### Task 2: Frontend Progress Rendering

**Files:**
- Modify: `web/frontend/src/types.ts`
- Modify: `web/frontend/src/main.tsx`
- Test: `tests/test_frontend_review_tabs_structure.py`

- [ ] **Step 1: Write the failing frontend structure tests**

Add assertions that:

```python
assert "model: string;" in read_types()
assert "const visibleLog = [...log].reverse()" in read_main()
assert "[item.status, item.model, item.elapsed, item.tokens, item.context].filter(Boolean).join(' · ')" in read_main()
```

- [ ] **Step 2: Run frontend structure tests and confirm RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py::test_progress_panel_merges_rows_by_key_and_renders_completion_metrics -q
```

Expected: fails because `model` and `visibleLog` are not present.

- [ ] **Step 3: Implement frontend rendering**

Add `model: string;` to `ProgressEvent`.

In `main.tsx`, derive `const visibleLog = [...log].reverse();` before the JSX return and render `visibleLog.map(...)` instead of `log.map(...)`.

Render structured metadata in this order:

```tsx
<span>{[item.status, item.model, item.elapsed, item.tokens, item.context].filter(Boolean).join(' · ')}</span>
```

- [ ] **Step 4: Run frontend structure tests and confirm GREEN**

Run the same frontend structure command. Expected: pass.

### Task 3: Docs, Build, And Commit

**Files:**
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Update required docs**

Record the changed progress panel behavior, the new `model` progress-event field, the parser compatibility with `/` and `|` metadata, and the verification commands.

- [ ] **Step 2: Run final verification**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_progress_event_includes_model_and_elapsed_from_pipe_metadata tests/test_web_service.py::test_progress_event_without_model_does_not_use_context_capacity_as_model tests/test_web_service.py::test_project_progress_log_accepts_legacy_strings_and_structured_events tests/test_frontend_review_tabs_structure.py::test_progress_panel_merges_rows_by_key_and_renders_completion_metrics -q
npm --prefix web/frontend run build
git diff --check
```

Expected: tests pass, frontend build exits 0, and whitespace check has no output.

- [ ] **Step 3: Commit**

Run:

```bash
git add src/ai_novelist/web/project_service.py web/frontend/src/types.ts web/frontend/src/main.tsx tests/test_web_service.py tests/test_frontend_review_tabs_structure.py docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md docs/superpowers/plans/2026-05-29-progress-order-and-model-metrics.md
git commit -m "fix: show newest progress metrics first"
```
