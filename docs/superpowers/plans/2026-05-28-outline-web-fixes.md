# Outline Web Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix outline-stage pending-question looping, progress-log row updates, and outline review apply persistence so each manual review runs against the latest saved baseline.

**Architecture:** Keep the source of truth in the backend. The outline stage loop stays in `graph_outline.py` and `web/service.py`, the progress log normalization stays in `progress.py` plus the Web client, and review apply writes a new baseline back to the same stage files that the Web UI reads. The frontend should only refresh and render what the backend now returns.

**Tech Stack:** Python 3.11+, pytest, FastAPI, TypeScript, React, existing file-backed `LocalStore`.

---

### Task 1: Make outline pending questions loop until none remain

**Files:**
- Modify: `src/ai_novelist/web/service.py`
- Modify: `src/ai_novelist/graph_outline.py`
- Test: `tests/test_web_service.py`

- [ ] **Step 1: Write the failing test**

Add a Web service test that simulates a stage with one round of pending questions, submits answers, and verifies that the refreshed payload still exposes a second round when the reviser returns more questions:

```python
def test_submit_stage_pending_answers_can_return_another_round(monkeypatch, tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage = "direction"
    state.outline_stage_artifacts["direction"] = {
        "stage": "direction",
        "status": "options_ready",
        "pending_questions": ["主角动机是否保留灰色地带？"],
    }
    store.save_state(state)

    def fake_run(data: dict, adapter: AgentAdapter, local_store: LocalStore, progress=None) -> dict:
        result = dict(data)
        result["outline_stage_artifacts"]["direction"]["pending_questions"] = [
            "故事基调是否更偏悬疑？"
        ]
        return result

    monkeypatch.setattr(service, "run_outline_stage_node", fake_run)

    result = service.submit_stage_pending_answers(
        store,
        DummyAdapter(),
        "web-demo",
        "direction",
        answers=[{"question": "主角动机是否保留灰色地带？", "answer": "保留灰色地带", "selected_option_id": "accept"}],
    )
    assert result.outline_stage_artifacts["direction"]["pending_questions"] == ["故事基调是否更偏悬疑？"]
```

Add a second test that verifies the lock becomes available once the refreshed payload has no remaining questions.

- [ ] **Step 2: Run the test and verify it fails**

Run: `.venv/bin/python -m pytest tests/test_web_service.py::test_submit_stage_pending_answers_can_return_another_round -v`

Expected: FAIL because the submit path currently stops after the first round.

- [ ] **Step 3: Implement the looping behavior**

Update `submit_stage_pending_answers()` so it:

1. normalizes the submitted answers into the existing revision instruction,
2. reruns the active stage,
3. reloads the stage payload from the updated artifact/state,
4. returns the refreshed stage state instead of treating submit as terminal.

If the active stage still has pending questions after rerun, leave `outline_stage_status` as `options_ready` and keep `pending_questions` populated.

```python
result = run_outline_stage_node(state.to_dict(), adapter, store, progress or (lambda _stage, _message: None))
refreshed = NovelState.from_dict(result)
return refreshed
```

In `graph_outline.py`, keep the existing pending-question extraction pipeline intact, but make sure the code path that finalizes a stage does not collapse extra questions into a single synthetic prompt when there are still real questions to ask.

- [ ] **Step 4: Run the targeted tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_submit_stage_pending_answers_can_return_another_round -v
.venv/bin/python -m pytest tests/test_web_service.py::test_outline_stage_payload_includes_action_state -v
```

Expected: both pass.

- [ ] **Step 5: Commit**

```bash
git add src/ai_novelist/web/service.py src/ai_novelist/graph_outline.py tests/test_web_service.py
git commit -m "fix: loop outline pending questions"
```

### Task 2: Merge progress rows and show elapsed time plus token metrics

**Files:**
- Modify: `src/ai_novelist/progress.py`
- Modify: `src/ai_novelist/web/service.py`
- Modify: `web/frontend/src/main.tsx`
- Modify: `web/frontend/src/styles.css`
- Test: `tests/test_web_service.py`
- Test: `tests/test_web_app.py`
- Test: `tests/test_frontend_review_tabs_structure.py`

- [ ] **Step 1: Write the failing test**

Add a backend test that asserts the SSE parser emits a stable identifier and keeps the final metrics on the same logical event:

```python
def test_progress_event_includes_key_and_completion_metrics() -> None:
    event = service.build_progress_event("OutlineStage", "正在审查（12.4s/ctx=4K/258K/tok≈8.1K）")
    assert event["key"] == "OutlineStage"
    assert event["label"] == "正在审查"
    assert event["elapsed"] == "12.4s"
    assert event["tokens"] == "tok≈8.1K"
    assert event["context"] == "ctx=4K/258K"
```

Add a frontend structure test that asserts the progress row rendering code uses `status`, `elapsed`, `tokens`, and `context` on the same row rather than only showing the raw status string.

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_progress_event_includes_key_and_completion_metrics -v
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py::test_right_progress_has_fixed_scroll_area -v
```

Expected: the new progress metrics test fails first, and the frontend test still reflects the old status-only rendering.

- [ ] **Step 3: Implement the merged-row behavior**

In `progress.py`, keep `completion_progress_message()` as the completion formatter, but make sure the data returned to the Web client can be matched back to the same task row. If the backend can expose an explicit `key` for an event, include it in the structured payload; otherwise keep the label as the compatibility identifier.

In `web/frontend/src/main.tsx`, change `pushLog()` so it replaces an existing row with the same key/label instead of always prepending. Introduce a small helper like this:

```ts
function upsertProgressItem(items: ProgressItem[], message: ProgressItem) {
  const next = items.filter((item) => (item.key || item.label) !== (message.key || message.label))
  return [message, ...next].slice(0, maxLogItems)
}

setLog((items) => {
  const next = upsertProgressItem(items, message)
  void saveProjectProgressLog(next)
  return next
})
```

Render the completed row with the compact metrics string:

```ts
<span>{[item.status, item.elapsed, item.tokens, item.context].filter(Boolean).join(' · ')}</span>
```

Keep the existing sidebar layout and scroll container, only change the row update and display logic.

- [ ] **Step 4: Run the targeted tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_frontend_review_tabs_structure.py -v
```

Expected: the progress parsing and frontend structure checks pass.

- [ ] **Step 5: Commit**

```bash
git add src/ai_novelist/progress.py src/ai_novelist/web/service.py web/frontend/src/main.tsx web/frontend/src/styles.css tests/test_web_service.py tests/test_web_app.py tests/test_frontend_review_tabs_structure.py
git commit -m "fix: merge web progress rows"
```

### Task 3: Persist outline review apply as a new saved baseline

**Files:**
- Modify: `src/ai_novelist/web/service.py`
- Modify: `src/ai_novelist/graph_outline.py`
- Test: `tests/test_web_service.py`
- Test: `tests/test_web_app.py`

- [ ] **Step 1: Write the failing test**

Add a Web service test that runs outline review apply with selected issue ids, then reloads the project and verifies both the stage artifact and root outline reflect the saved revision:

```python
def test_apply_outline_review_updates_stage_files_and_baseline(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline = "# 最终锁定总大纲

## 方向定位
旧内容。"
    state.outline_stage_artifacts["direction"] = {
        "stage": "direction",
        "status": "options_ready",
        "summary": "旧方向",
        "path": "outline/direction.md",
    }
    store.save_state(state)
    run_id = "20260528010101-deadbeef"
    store.write_outline_review_report("web-demo", run_id, {"source_outline": state.outline, "decision": "revise", "repair_suggestions": [{"id": "issue-1", "chapter": 1}]})

    result = service.apply_outline_review(store, DummyAdapter(), "web-demo", run_id, selected_issue_ids=["issue-1"])
    reloaded = store.load_state("web-demo")
    assert "updated_stages" in result
    assert reloaded.outline_review_applied_run_id == run_id
    assert "已补强结尾收束" in store.load_outline_artifact("web-demo", "direction")
    assert "已补强结尾收束" in store.outline_path("web-demo").read_text(encoding="utf-8")
```

Add a follow-up test that calls `review_outline()` again after apply and asserts the new `source_outline` comes from the updated saved baseline, not from the old review report.

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_apply_outline_review_updates_stage_files_and_baseline -v
.venv/bin/python -m pytest tests/test_web_service.py::test_review_outline_uses_latest_saved_baseline_after_apply -v
```

Expected: fail until the apply path writes back the revised stage files and the next review uses the refreshed baseline.

- [ ] **Step 3: Implement the write-back and baseline refresh**

Update `apply_outline_review()` so it:

1. builds the revision instruction from selected issues only,
2. applies the revision,
3. splits the revised outline back into the affected stage source files where the content can be mapped safely,
4. updates `state.outline_stage_artifacts` and `state.outline`,
5. saves both the stage files and the combined `outline.md`,
6. returns `updated_stages`, `skipped_stages`, and the saved baseline summary.

Do not automatically start another review. `review_outline()` should continue to run only when the user clicks the review button again, and it must build `source_outline` from the currently saved baseline after apply.

If a stage section cannot be mapped safely, add it to `skipped_stages` and still report the successful saves explicitly.

- [ ] **Step 4: Run the targeted tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_frontend_review_tabs_structure.py -v
```

Expected: the outline apply and manual re-review baseline tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/ai_novelist/web/service.py src/ai_novelist/graph_outline.py tests/test_web_service.py tests/test_web_app.py
git commit -m "fix: persist outline review baseline"
```

### Task 4: Full regression check and docs sync

**Files:**
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`
- Test: `tests/test_web_service.py`
- Test: `tests/test_web_app.py`
- Test: `tests/test_frontend_review_tabs_structure.py`

- [ ] **Step 1: Run the focused regression suite**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_frontend_review_tabs_structure.py -v
```

Expected: all outline Web, progress, and review baseline tests pass.

- [ ] **Step 2: Run the broader Python suite**

Run:

```bash
.venv/bin/python -m pytest
```

Expected: the project test suite remains green.

- [ ] **Step 3: Update the docs**

Add a short implementation note to `docs/IMPLEMENTATION_PLAN.md` describing the new pending-question loop, merged progress rows, and outline review baseline refresh. Add the test result summary and any residual limitations to `docs/SESSION_SUMMARY.md`.

- [ ] **Step 4: Commit**

```bash
git add docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "docs: record outline web fixes"
```
