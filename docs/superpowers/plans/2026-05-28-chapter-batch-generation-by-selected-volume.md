# Chapter Batch Generation by Selected Volume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simplify chapter-body batch generation so the user selects a volume first, then only enters a generation count that is capped to the remaining chapters in that volume.

**Architecture:** Keep the existing volume batch graph and file-backed project model, but add a small workspace summary contract that reports total, generated, remaining, and next chapter numbers for the selected volume. The frontend should consume that summary to render a single `生成数量` control and to clamp the batch request before submit. The graph still writes the same chapter artifacts and manifests; only the entry contract and UI surface change.

**Tech Stack:** Python 3.11+, FastAPI, pytest, React + TypeScript, Vite

---

### Task 1: Add volume batch summary and capped batch request semantics on the backend

**Files:**
- Modify: `src/ai_novelist/web/service.py`
- Modify: `src/ai_novelist/web/app.py`
- Test: `tests/test_web_service.py`
- Test: `tests/test_web_app.py`

- [ ] **Step 1: Write the failing tests**

Add a summary test that proves the backend can describe the selected volume without any user-entered chapter range:

```python
def test_chapter_batch_workspace_payload_reports_remaining_counts(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["chapter_outline"] = {
        "stage": "chapter_outline",
        "status": "locked",
        "metadata": {
            "total_volumes": 2,
            "current_volume_index": 2,
            "completed_volumes": [1],
            "volume_statuses": {"2": "locked"},
        },
    }
    store.save_outline_artifact(
        state,
        "chapter_outline",
        "## 第二卷：推进\n\n"
        + "\n".join(f"### 第 {chapter} 章：标题 {chapter}" for chapter in range(4, 24))
        + "\n",
    )
    for chapter in (4, 5, 6):
        state.active_chapter = chapter
        state.current_chapter = chapter
        state.chapter_draft = f"# 第 {chapter} 章\n\n正文 {chapter}"
        store.save_chapter_draft(state, version=1)

    payload = service.chapter_batch_workspace_payload(store, "web-demo", volume=2)

    assert payload["volume_index"] == 2
    assert payload["total_chapters"] == 20
    assert payload["generated_chapters"] == 3
    assert payload["remaining_chapters"] == 17
    assert payload["next_chapter_number"] == 7
```

Add a generation test that proves the service clamps the requested count to the remaining chapters and passes only the remaining chapter numbers to the graph:

```python
def test_generate_chapter_batch_uses_requested_count_and_first_missing_chapter(monkeypatch, tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    captured: dict[str, object] = {}

    class FakeGraph:
        def invoke(self, data: dict) -> dict:
            captured.update(data["director_task_args"])
            return data

    monkeypatch.setattr(service, "build_volume_write_graph", lambda adapter, store, progress=None: FakeGraph())

    state.outline_stage_artifacts["chapter_outline"] = {
        "stage": "chapter_outline",
        "status": "locked",
        "metadata": {
            "total_volumes": 2,
            "current_volume_index": 2,
            "completed_volumes": [1],
            "volume_statuses": {"2": "locked"},
        },
    }
    store.save_outline_artifact(
        state,
        "chapter_outline",
        "## 第二卷：推进\n\n"
        + "\n".join(f"### 第 {chapter} 章：标题 {chapter}" for chapter in range(4, 24))
        + "\n",
    )
    for chapter in (4, 5, 6):
        state.active_chapter = chapter
        state.current_chapter = chapter
        state.chapter_draft = f"# 第 {chapter} 章\n\n正文 {chapter}"
        store.save_chapter_draft(state, version=1)

    service.generate_chapter_batch(store, DummyAdapter(), "web-demo", volume=2, requested_count=50)

    assert captured["volume"] == 2
    assert captured["chapters"] == ",".join(str(chapter) for chapter in range(7, 24))
```

Add a route test that proves the API accepts `requested_count` and still returns streaming output:

```python
def test_web_app_exposes_chapter_batch_workspace_route(tmp_path) -> None:
    app = web_app.make_app(Settings(projects_dir=tmp_path), mock=True)
    routes = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/api/projects/{project_id}/chapters/workspace" in routes
```

- [ ] **Step 2: Run the targeted backend tests and confirm the failures**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py -k "chapter_batch or generate_chapter_batch" -q
```

Expected: the new assertions fail because the summary payload and `requested_count` flow do not exist yet.

- [ ] **Step 3: Implement the backend contract**

Implement a small summary helper in `src/ai_novelist/web/service.py` that:

- loads the selected volume from the chapter-outline metadata
- counts total chapters from the selected volume's chapter outline slice
- counts generated chapters from `list_chapters(store, project_id, volume=volume)`
- computes the next missing chapter number in ascending order
- returns `volume_index`, `volume_label`, `total_chapters`, `generated_chapters`, `remaining_chapters`, and `next_chapter_number`

Update `generate_chapter_batch(...)` so it accepts `requested_count` as the primary input, clamps it to the remaining chapter count, and converts the selected missing chapter numbers into the `chapters` override string that `graph_volume_write.prepare_volume_batch_node()` already understands.

Add `GET /api/projects/{project_id}/chapters/workspace` in `src/ai_novelist/web/app.py` so the frontend can fetch the summary and the volume-scoped chapter list in one request. Update the batch-generation route so it reads `requested_count` from the request body, keeps `volume` as the selected-context value, and continues to stream SSE progress.

- [ ] **Step 4: Re-run the backend tests**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py -q
```

Expected: the new backend tests pass and the existing web route tests remain green.

- [ ] **Step 5: Commit the backend slice**

```bash
git add src/ai_novelist/web/service.py src/ai_novelist/web/app.py tests/test_web_service.py tests/test_web_app.py
git commit -m "feat: cap chapter batch generation by remaining volume chapters"
```

### Task 2: Rework the chapter-body batch panel to show volume stats and a single quantity input

**Files:**
- Modify: `web/frontend/src/main.tsx`
- Modify: `web/frontend/src/styles.css`
- Test: `tests/test_frontend_review_tabs_structure.py`

- [ ] **Step 1: Write the failing frontend structure test**

Add a structural assertion around the `章节批量生成` block so the batch panel is forced to render stats instead of the old input trio:

```python
def test_chapter_batch_panel_uses_volume_summary_and_single_quantity_input() -> None:
    source = read_main()
    batch_block = source[source.index("chapterView === 'batch'") : source.index("chapterView === 'list'")]

    assert "总章数" in batch_block
    assert "已生成章数" in batch_block
    assert "剩余章数" in batch_block
    assert "生成数量" in batch_block
    assert "卷号" not in batch_block
    assert "章节范围" not in batch_block
    assert "并发数" not in batch_block
    assert "Math.min(requestedCount, remainingChapters)" in source
```

- [ ] **Step 2: Run the frontend structure test and confirm it fails**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py -k chapter_batch_panel -q
```

Expected: the test fails because the batch panel still renders the old three-field form.

- [ ] **Step 3: Implement the new batch panel**

Update `web/frontend/src/main.tsx` so the chapter workspace batch view:

- reads the selected volume context from the existing volume navigation
- shows the current volume name, total chapters, generated chapters, and remaining chapters
- keeps only one editable numeric field named `生成数量`
- disables the submit button when remaining chapters is zero
- clamps the submitted generation count with `Math.min(requestedCount, remainingChapters)`
- sends `requested_count` to `/api/projects/${projectId}/chapters/generate-batch`
- refreshes the selected volume after completion without asking the user for a volume number

If layout spacing needs adjustment, keep it in `web/frontend/src/styles.css` and do not add new card surfaces.

- [ ] **Step 4: Rebuild the frontend and re-run the structural test**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py -q
npm --prefix web/frontend run build
```

Expected: the structure test passes and the frontend build completes successfully.

- [ ] **Step 5: Commit the frontend slice**

```bash
git add web/frontend/src/main.tsx web/frontend/src/styles.css tests/test_frontend_review_tabs_structure.py
git commit -m "feat: simplify chapter batch generation controls"
```

### Task 3: Update implementation docs and finish with the focused verification run

**Files:**
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Record the new batch-generation behavior in the docs**

Append a short implementation note to `docs/IMPLEMENTATION_PLAN.md` that describes the selected-volume batch summary, the `生成数量` input, and the `requested_count` clamping rule.

Append a matching result note to `docs/SESSION_SUMMARY.md` that records:

- the files changed
- the targeted tests that were run
- the remaining risk, if any, around interpreting chapter totals from the volume outline

- [ ] **Step 2: Run the final verification set**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_frontend_review_tabs_structure.py -q
npm --prefix web/frontend run build
```

Expected: the backend tests pass, the frontend structure test passes, and the frontend build completes.

- [ ] **Step 3: Commit the docs slice**

```bash
git add docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "docs: record chapter batch generation redesign"
```

## Coverage Check

- Spec goal about hiding `卷号`, `章节范围`, and `并发数`: Task 2.
- Spec goal about showing total/generated/remaining counts: Task 1 and Task 2.
- Spec goal about clamping input to remaining chapters: Task 1 and Task 2.
- Spec goal about starting from the first missing chapter: Task 1.
- Spec goal about keeping `生成数量` as concurrency upper bound: Task 1.
- Spec goal about updating docs: Task 3.

