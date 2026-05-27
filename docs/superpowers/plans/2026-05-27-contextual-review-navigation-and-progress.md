# Contextual Review Navigation and Concise Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the Web UI around contextual stage/volume navigation, add chapter-outline overall review, keep chapter-body review global while navigating bodies by volume, and make new progress entries contain only operational metrics.

**Architecture:** Preserve the existing file-backed `LocalStore`, current outline review implementation, and current global chapter-body review implementation. Extend `web/service.py` with two bounded contracts: structured progress events and volume-oriented review/workspace payloads; expose them in `web/app.py`; then recompose the existing React screen around a shared contextual sidebar model without changing creative graph semantics.

**Tech Stack:** Python 3.11+, FastAPI, file-backed JSON/Markdown artifacts, React + TypeScript + Vite, pytest.

---

## File Structure

- Modify `src/ai_novelist/storage/local_store.py`: add explicit paths for chapter-outline review reports beneath `outline/chapter_reviews/`.
- Modify `src/ai_novelist/web/service.py`: add structured progress event normalization, chapter-outline review/run/apply services, chapter-body volume workspace payloads, and chapter-to-volume fallback handling.
- Modify `src/ai_novelist/web/app.py`: return structured SSE progress events and expose chapter-outline-review and chapter-body-workspace HTTP routes.
- Modify `src/ai_novelist/outline/chapter_outline_structure.py`: expose volume chapter-range parsing helpers used to classify generated chapter bodies.
- Modify `web/frontend/src/main.tsx`: replace review tabs with contextual sidebar selections, add chapter-outline review state/UI, render chapter-body volume workspaces, and consume structured progress events.
- Modify `web/frontend/src/styles.css`: style the separated review sidebar entry, selected-volume workspace, and metric-only progress items.
- Modify `tests/test_web_service.py`: cover progress compatibility, chapter-outline review persistence/application, and chapter-body volume payloads.
- Modify `tests/test_web_app.py`: cover added API routes and sanitized SSE/progress-log payload behavior.
- Modify `tests/test_frontend_review_tabs_structure.py`: assert the new navigation hierarchy and metric-only progress rendering.
- Modify `tests/test_progress.py`: cover safe extraction of display metrics where progress utility behavior is extended.
- Modify `docs/IMPLEMENTATION_PLAN.md` and `docs/SESSION_SUMMARY.md`: update architecture and verification notes in every code-bearing commit as required by repository policy.

Implementation note: `.superpowers/` contains untracked brainstorming previews and must not be staged. Inspect the worktree before every commit and preserve any unrelated user edits.

---

### Task 1: Replace New Web Progress Strings With Structured Display Events

**Files:**
- Modify: `src/ai_novelist/web/service.py:118-152`
- Modify: `src/ai_novelist/web/app.py:63-87,109-122`
- Modify: `web/frontend/src/main.tsx:1-230,242-365,876-882`
- Modify: `web/frontend/src/styles.css:156-162`
- Modify: `tests/test_web_service.py:108-118`
- Modify: `tests/test_web_app.py:67-83`
- Modify: `tests/test_frontend_review_tabs_structure.py:133-142,219-225`
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Write failing service/API tests for legacy compatibility and safe new events**

In `tests/test_web_service.py`, replace the string-only progress expectation with tests that retain existing strings when read and validate new event records:

```python
def test_project_progress_log_accepts_legacy_strings_and_structured_events(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    service.create_project(store, "Progress A", "progress-a")
    legacy = "旧日志中的原始内容不迁移"
    event = {"label": "世界观汇总", "elapsed": "12.4s", "tokens": "tok≈8.1K", "context": "ctx=4K/258K", "status": "completed"}

    service.save_project_progress_log(store, "progress-a", [event, legacy])

    assert service.load_project_progress_log(store, "progress-a") == [event, legacy]


def test_progress_event_drops_generated_message_body_but_retains_metrics() -> None:
    event = service.build_progress_event(
        "OutlineStage",
        "正在汇总「世界观设定」阶段产物（deepseek/12.4s/ctx=4K/258K/tok≈8.1K）",
    )

    assert event == {
        "label": "正在汇总「世界观设定」阶段产物",
        "elapsed": "12.4s",
        "tokens": "tok≈8.1K",
        "context": "ctx=4K/258K",
        "status": "running",
    }
    assert "产物正文" not in json.dumps(event, ensure_ascii=False)
```

In `tests/test_web_app.py`, add an SSE assertion using a monkeypatched service action that emits a message containing metadata and forbidden prose:

```python
def test_sse_progress_returns_metric_event_not_raw_message(monkeypatch, tmp_path) -> None:
    client = TestClient(web_app.make_app(Settings(projects_dir=tmp_path), mock=True))
    client.post("/api/projects", json={"title": "Web Demo", "project_id": "web-demo"})

    def fake_generate(store, adapter, project_id, stage, instruction="", progress=None):
        progress("OutlineStage", "世界观汇总（12.4s/ctx=4K/258K/tok≈8.1K）")
        return store.load_state(project_id)

    monkeypatch.setattr(web_app.service, "generate_outline_stage", fake_generate)
    response = client.post("/api/projects/web-demo/outline/stages/worldbuilding/generate", json={})

    assert '"label": "世界观汇总"' in response.text
    assert '"tokens": "tok≈8.1K"' in response.text
    assert '"message"' not in response.text
```

- [ ] **Step 2: Run the progress contract tests and confirm failure**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_web_service.py::test_project_progress_log_accepts_legacy_strings_and_structured_events \
  tests/test_web_service.py::test_progress_event_drops_generated_message_body_but_retains_metrics \
  tests/test_web_app.py::test_sse_progress_returns_metric_event_not_raw_message -q
```

Expected: FAIL because progress items are normalized to strings and SSE returns `{"stage", "message"}`.

- [ ] **Step 3: Implement structured progress normalization and SSE sanitization**

In `src/ai_novelist/web/service.py`, replace `normalize_progress_log_items()` with a backward-compatible union and add the SSE event builder:

```python
ProgressItem = str | dict[str, str]


def normalize_progress_log_items(items: Iterable[Any]) -> list[ProgressItem]:
    normalized: list[ProgressItem] = []
    for item in items:
        if isinstance(item, str) and item.strip():
            normalized.append(item.strip())
        elif isinstance(item, dict):
            event = {
                key: str(item.get(key) or "").strip()
                for key in ("label", "elapsed", "tokens", "context", "status")
            }
            if event["label"]:
                normalized.append(event)
        if len(normalized) >= MAX_WEB_PROGRESS_LOG_ITEMS:
            break
    return normalized


def build_progress_event(stage: str, message: str) -> dict[str, str]:
    body = str(message or "").strip()
    label = body.split("（", 1)[0].strip() or stage
    elapsed = re.search(r"(?:^|[/（])(\d+(?:\.\d+)?s)(?:[/）]|$)", body)
    tokens = re.search(r"(tok≈[^/）\s]+)", body)
    context = re.search(r"(ctx=[^/）\s]+(?:/[^/）\s]+)?)", body)
    return {
        "label": label,
        "elapsed": elapsed.group(1) if elapsed else "",
        "tokens": tokens.group(1) if tokens else "",
        "context": context.group(1) if context else "",
        "status": "failed" if "失败" in body else "running",
    }
```

Update `load_project_progress_log()` and `save_project_progress_log()` return annotations to `list[ProgressItem]`.

In `src/ai_novelist/web/app.py`, make SSE publish only sanitized progress data:

```python
def progress(stage: str, message: str) -> None:
    queue.put(("progress", service.build_progress_event(stage, message)))
```

- [ ] **Step 4: Update the frontend progress type and remove free-form post-action content logs**

In `web/frontend/src/main.tsx`, add:

```tsx
type ProgressEvent = {
  label: string;
  elapsed: string;
  tokens: string;
  context: string;
  status: string;
};
type ProgressItem = string | ProgressEvent;
```

Change `streamAction()` to parse SSE progress JSON and invoke `onProgress(data as ProgressEvent)`, change `log` to `ProgressItem[]`, and replace action summary logging such as:

```tsx
pushLog(`章节总体审查完成：${latest.summary || '无摘要'}`);
```

with:

```tsx
pushLog({ label: '章节总体审查', elapsed: '', tokens: '', context: '', status: 'completed' });
```

Render structured entries without their source prose:

```tsx
{log.map((item, index) => typeof item === 'string'
  ? <pre key={`${index}-${item}`}>{item}</pre>
  : (
    <div className="progress-item" key={`${index}-${item.label}`}>
      <strong>{item.label}</strong>
      <span>{[item.elapsed, item.tokens, item.context].filter(Boolean).join(' · ') || item.status}</span>
    </div>
  ))}
```

Preserve rendering of legacy strings exactly as required by the approved design.

- [ ] **Step 5: Update frontend structure assertions and required docs**

In `tests/test_frontend_review_tabs_structure.py`, add assertions:

```python
def test_progress_panel_renders_structured_metrics_and_keeps_legacy_branch() -> None:
    source = read_main()

    assert "type ProgressEvent" in source
    assert "typeof item === 'string'" in source
    assert "item.elapsed" in source
    assert "item.tokens" in source
    assert "item.context" in source
    assert "latest.summary || '无摘要'" not in source
```

Update `docs/IMPLEMENTATION_PLAN.md` with the structured web progress-event contract and `docs/SESSION_SUMMARY.md` with the focused test command and compatibility statement that old strings remain readable.

- [ ] **Step 6: Verify and commit the progress contract**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_frontend_review_tabs_structure.py -q
npm --prefix web/frontend run build
git status --short
```

Expected: tests PASS; frontend build PASS; `.superpowers/` remains unstaged.

Commit:

```bash
git add src/ai_novelist/web/service.py src/ai_novelist/web/app.py web/frontend/src/main.tsx web/frontend/src/styles.css tests/test_web_service.py tests/test_web_app.py tests/test_frontend_review_tabs_structure.py docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "feat: sanitize web progress events"
```

---

### Task 2: Add Cross-Volume Chapter-Outline Overall Review

**Files:**
- Modify: `src/ai_novelist/storage/local_store.py:55-70`
- Modify: `src/ai_novelist/web/service.py:258-725,499-559`
- Modify: `src/ai_novelist/web/app.py:160-263`
- Modify: `tests/test_web_service.py:285-423,516-571`
- Modify: `tests/test_web_app.py:30-52`
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Write failing service tests for report persistence and selective volume application**

Add an adapter fixture in `tests/test_web_service.py`:

```python
class ChapterOutlineReviewAdapter(AgentAdapter):
    def complete(self, prompt: str, project_dir: Path) -> str:
        if "chapter_outline_reviewer" in prompt:
            return json.dumps({
                "status": "needs_repair",
                "summary": "第二卷承接不足。",
                "repair_suggestions": [{
                    "id": "volume-2-fix",
                    "volume_index": 2,
                    "severity": "serious",
                    "category": "continuity",
                    "message": "第二卷未承接第一卷线索。",
                    "recommendation": "在第二卷开篇回收失踪名单线索。",
                    "selected": True,
                }],
            }, ensure_ascii=False)
        return "### 第二卷\n\n修订后内容：开篇回收失踪名单线索。\n"
```

Add tests that seed `metadata["volume_contents"]`:

```python
def test_chapter_outline_review_roundtrip_and_selective_apply(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["chapter_outline"] = {
        "stage": "chapter_outline",
        "status": "options_ready",
        "metadata": {
            "total_volumes": 2,
            "volume_contents": {"1": "### 第一卷\n\n保留内容。", "2": "### 第二卷\n\n旧内容。"},
            "volume_statuses": {"1": "locked", "2": "options_ready"},
        },
    }
    store.save_state(state)

    report = service.review_chapter_outline(store, ChapterOutlineReviewAdapter(), "web-demo")
    applied = service.apply_chapter_outline_review(
        store, ChapterOutlineReviewAdapter(), "web-demo", report["run_id"], selected_issue_ids=["volume-2-fix"]
    )
    saved = store.load_state("web-demo")
    contents = saved.outline_stage_artifacts["chapter_outline"]["metadata"]["volume_contents"]

    assert report["repair_suggestions"][0]["volume_index"] == 2
    assert service.latest_chapter_outline_review(store, "web-demo")["run_id"] == report["run_id"]
    assert contents["1"] == "### 第一卷\n\n保留内容。"
    assert "回收失踪名单线索" in contents["2"]
    assert "回收失踪名单线索" in store.load_outline_artifact("web-demo", "chapter_outline")
    assert applied["applied_volumes"] == [2]
```

Also add a stale-source test asserting `apply_chapter_outline_review()` raises `LocalStoreError("章节大纲已变化，请重新审查")` after changing `volume_contents` between review and apply.

- [ ] **Step 2: Run the new chapter-outline review tests and confirm failure**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_web_service.py::test_chapter_outline_review_roundtrip_and_selective_apply \
  tests/test_web_service.py::test_chapter_outline_review_rejects_stale_volume_snapshot -q
```

Expected: FAIL because the dedicated chapter-outline review functions and report paths do not exist.

- [ ] **Step 3: Add report paths and cross-volume review helpers**

In `src/ai_novelist/storage/local_store.py`, add paths matching the approved spec:

```python
def chapter_outline_review_dir(self, project_id: str) -> Path:
    return self.project_dir(project_id) / "outline" / "chapter_reviews"

def chapter_outline_review_report_path(self, project_id: str, run_id: str) -> Path:
    return self.chapter_outline_review_dir(project_id) / run_id / "report.json"

def chapter_outline_review_markdown_path(self, project_id: str, run_id: str) -> Path:
    return self.chapter_outline_review_dir(project_id) / run_id / "report.md"
```

In `src/ai_novelist/web/service.py`, import `merge_chapter_outline_volumes` and add bounded helpers:

```python
def chapter_outline_snapshot(metadata: dict[str, Any]) -> str:
    contents = metadata.get("volume_contents") if isinstance(metadata.get("volume_contents"), dict) else {}
    return hashlib.sha256(json.dumps(contents, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def build_chapter_outline_review_prompt(metadata: dict[str, Any]) -> str:
    return (
        "AGENT: chapter_outline_reviewer\n"
        "请审查所有卷的章节大纲连续性，只输出 JSON。\n"
        "schema: {status, summary, repair_suggestions:[{id, volume_index, severity, category, message, recommendation, selected}]}\n\n"
        + merge_chapter_outline_volumes(metadata)
    )
```

Implement `review_chapter_outline()` to load chapter-outline metadata, call the adapter, normalize suggestions with integer `volume_index`, persist `source_digest`, JSON and Markdown reports, and return the report. Implement `latest_chapter_outline_review()` by reading the lexically latest report directory.

- [ ] **Step 4: Implement explicit apply per affected volume**

Add:

```python
def review_chapter_outline(
    store: LocalStore,
    adapter: AgentAdapter,
    project_id: str,
    progress: ProgressFunc | None = None,
) -> dict[str, Any]:
    emit = progress or (lambda _stage, _message: None)
    state = store.load_state(project_id)
    artifact = dict(state.outline_stage_artifacts.get("chapter_outline") or {})
    metadata = dict(artifact.get("metadata") or {})
    emit("ChapterOutlineReview", "正在审查全部章节大纲卷...")
    output = adapter.complete(build_chapter_outline_review_prompt(metadata), store.project_dir(project_id)).strip()
    report = normalize_chapter_outline_review_output(output)
    report.update({"project_id": project_id, "run_id": datetime.now(UTC).strftime("%Y%m%d%H%M%S"), "source_digest": chapter_outline_snapshot(metadata)})
    write_chapter_outline_review_report(store, project_id, report)
    emit("ChapterOutlineReview", "章节大纲总体审查已保存。")
    return report


def apply_chapter_outline_review(
    store: LocalStore,
    adapter: AgentAdapter,
    project_id: str,
    run_id: str,
    progress: ProgressFunc | None = None,
    selected_issue_ids: list[str] | None = None,
) -> dict[str, Any]:
    state = store.load_state(project_id)
    artifact = dict(state.outline_stage_artifacts.get("chapter_outline") or {})
    metadata = dict(artifact.get("metadata") or {})
    report = load_chapter_outline_review(store, project_id, run_id)
    if chapter_outline_snapshot(metadata) != report["source_digest"]:
        raise LocalStoreError("章节大纲已变化，请重新审查")
    selected = [
        item for item in report["repair_suggestions"]
        if selected_issue_ids is None or item["id"] in selected_issue_ids
    ]
    for volume_index in sorted({int(item["volume_index"]) for item in selected}):
        current = str(metadata["volume_contents"].get(str(volume_index)) or "")
        suggestions = [item for item in selected if int(item["volume_index"]) == volume_index]
        revised = adapter.complete(build_chapter_outline_repair_prompt(volume_index, current, suggestions), store.project_dir(project_id)).strip()
        metadata["volume_contents"][str(volume_index)] = revised.rstrip() + "\n"
    artifact["metadata"] = metadata
    state.outline_stage_artifacts["chapter_outline"] = artifact
    combined = merge_chapter_outline_volumes(metadata)
    store.save_outline_artifact(state, "chapter_outline", combined)
    store.save_outline_stage(state, "chapter_outline", combined)
    store.save_state(state)
    return {"project_id": project_id, "run_id": run_id, "applied_volumes": sorted({int(item["volume_index"]) for item in selected})}
```

Require nonempty `selected_issue_ids` when supplied, as the existing outline/body apply services already do.

- [ ] **Step 5: Expose API routes and test route registration**

In `src/ai_novelist/web/app.py`, add:

```python
@app.get("/api/projects/{project_id}/outline/chapter-workspace/review/latest")
def latest_chapter_outline_review(project_id: str):
    return service.latest_chapter_outline_review(store, project_id)

@app.post("/api/projects/{project_id}/outline/chapter-workspace/review")
def review_chapter_outline(project_id: str, payload: dict[str, Any] | None = None):
    payload = payload or {}
    return StreamingResponse(
        sse_events(lambda progress: service.review_chapter_outline(store, adapter(payload), project_id, progress=progress)),
        media_type="text/event-stream",
    )

@app.post("/api/projects/{project_id}/outline/chapter-workspace/review/{run_id}/apply")
def apply_chapter_outline_review(project_id: str, run_id: str, payload: dict[str, Any] | None = None):
    payload = payload or {}
    return StreamingResponse(
        sse_events(lambda progress: service.apply_chapter_outline_review(
            store, adapter(payload), project_id, run_id, progress, payload.get("selected_issue_ids")
        )),
        media_type="text/event-stream",
    )
```

Extend `test_web_app_exposes_outline_action_and_workspace_routes()` to assert all three route paths.

- [ ] **Step 6: Document, verify, and commit chapter-outline review**

Update `docs/IMPLEMENTATION_PLAN.md` with the new chapter-outline review API and artifact paths. Update `docs/SESSION_SUMMARY.md` with selective-apply and stale-snapshot test results.

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py -q
git status --short
```

Expected: PASS; `.superpowers/` is untracked only and excluded from staging.

Commit:

```bash
git add src/ai_novelist/storage/local_store.py src/ai_novelist/web/service.py src/ai_novelist/web/app.py tests/test_web_service.py tests/test_web_app.py docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "feat: add chapter outline overall review"
```

---

### Task 3: Provide Volume-Scoped Chapter-Body Workspace Data

**Files:**
- Modify: `src/ai_novelist/outline/chapter_outline_structure.py:20-98`
- Modify: `src/ai_novelist/web/service.py:971-1009,1440-1520`
- Modify: `src/ai_novelist/web/app.py:273-326`
- Modify: `tests/test_web_service.py:904-1017`
- Modify: `tests/test_web_app.py:30-52`
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Add failing tests for chapter ranges, volume filtering, and `未分卷`**

In `tests/test_web_service.py`, seed chapter-outline volume specs and chapter drafts:

```python
def test_chapter_body_workspace_groups_chapters_by_selected_volume_and_unassigned(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["chapter_outline"] = {
        "stage": "chapter_outline",
        "metadata": {"total_volumes": 2},
    }
    store.save_outline_artifact(
        state,
        "volume_outline",
        "## 第一卷：开局（第 1-2 章）\n\n## 第二卷：推进（第 3-4 章）\n",
    )
    store.save_state(state)
    for chapter in (1, 3, 9):
        state.current_chapter = chapter
        state.chapter_draft = f"# 第 {chapter} 章\n\n正文内容足够长。" * 10
        store.save_chapter(state)

    payload = service.chapter_body_workspace_payload(store, "web-demo", selected_volume_index=2)

    assert [item["chapter"] for item in payload["selected_volume"]["chapters"]] == [3]
    assert payload["unassigned"]["label"] == "未分卷"
    assert [item["chapter"] for item in payload["unassigned"]["chapters"]] == [9]
```

Add `test_chapter_body_workspace_keeps_global_review_scope()` that loads volume 1 but calls `review_all_chapters()` and asserts its report lists chapters from volumes 1 and 2.

- [ ] **Step 2: Run the body workspace tests and confirm failure**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_web_service.py::test_chapter_body_workspace_groups_chapters_by_selected_volume_and_unassigned \
  tests/test_web_service.py::test_chapter_body_workspace_keeps_global_review_scope -q
```

Expected: FAIL because no chapter-body workspace payload or range classifier exists.

- [ ] **Step 3: Implement chapter-range parsing as a small structure helper**

In `src/ai_novelist/outline/chapter_outline_structure.py`, add:

```python
def parse_chapter_range(value: str) -> set[int]:
    result: set[int] = set()
    for part in re.split(r"[,，、]", str(value or "")):
        match = re.search(r"(\d+)\s*[-~至]\s*(\d+)", part)
        if match:
            start, end = int(match.group(1)), int(match.group(2))
            result.update(range(min(start, end), max(start, end) + 1))
            continue
        single = re.search(r"\d+", part)
        if single:
            result.add(int(single.group()))
    return result
```

Extend `extract_volume_specs()` only where the volume outline already exposes chapter ranges, populating `VolumeSpec.chapter_range`; do not infer ranges from generated prose when no range exists:

```python
range_match = re.search(r"第?\s*(\d+)\s*[-~至]\s*(\d+)\s*章", body)
chapter_range = f"{range_match.group(1)}-{range_match.group(2)}" if range_match else ""
found[number] = VolumeSpec(index=number, label=volume_label(number), name=name, chapter_range=chapter_range, function=body)
```

- [ ] **Step 4: Implement body workspace payload without changing global review**

In `src/ai_novelist/web/service.py`, import `parse_chapter_range` and add:

```python
def chapter_body_workspace_payload(store: LocalStore, project_id: str, selected_volume_index: int | None = None) -> dict[str, Any]:
    state = store.load_state(project_id)
    chapter_artifact = dict(state.outline_stage_artifacts.get("chapter_outline") or {})
    volume_artifact = dict(state.outline_stage_artifacts.get("volume_outline") or {})
    volume_outline = load_stage_markdown(store, state, "volume_outline", volume_artifact)
    metadata = chapter_outline_metadata_from_artifact(chapter_artifact, volume_outline)
    specs = list(metadata.get("volume_specs") or [])
    all_chapters = list_chapters(store, project_id)
    groups = {str(item["index"]): [] for item in specs}
    unassigned: list[dict[str, Any]] = []
    for chapter in all_chapters:
        owner = next(
            (item for item in specs if chapter["chapter"] in parse_chapter_range(str(item.get("chapter_range") or ""))),
            None,
        )
        (groups[str(owner["index"])] if owner else unassigned).append(chapter)
    selected_index = selected_volume_index or (int(specs[0]["index"]) if specs else 1)
    selected = next((item for item in specs if int(item["index"]) == int(selected_index)), None)
    if selected is None:
        raise LocalStoreError(f"Unknown chapter body volume: {selected_index}")
    return {
        "volume_specs": specs,
        "selected_volume": {**selected, "chapters": groups[str(selected_index)]},
        "unassigned": {"label": "未分卷", "chapters": unassigned},
    }
```

Do not filter `review_all_chapters()`: it continues to call `collect_latest_chapters()` for the whole project.

- [ ] **Step 5: Add route and API route assertion**

In `src/ai_novelist/web/app.py`, add:

```python
@app.get("/api/projects/{project_id}/chapters/workspace")
def chapter_body_workspace(project_id: str, selected_volume_index: int | None = None):
    return service.chapter_body_workspace_payload(store, project_id, selected_volume_index)
```

Update `tests/test_web_app.py` to assert `/api/projects/{project_id}/chapters/workspace` is registered.

- [ ] **Step 6: Document, verify, and commit the body workspace contract**

Update the required docs with the volume-scoped chapter-body read payload and the explicit statement that `review-all` remains global.

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py -q
git status --short
```

Expected: PASS.

Commit:

```bash
git add src/ai_novelist/outline/chapter_outline_structure.py src/ai_novelist/web/service.py src/ai_novelist/web/app.py tests/test_web_service.py tests/test_web_app.py docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "feat: expose chapter bodies by volume"
```

---

### Task 4: Recompose the React Navigation and Review Workspaces

**Files:**
- Modify: `web/frontend/src/main.tsx:1-1160`
- Modify: `web/frontend/src/styles.css:1-190`
- Modify: `tests/test_frontend_review_tabs_structure.py`
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Replace old structure tests with failing contextual-navigation expectations**

Update `tests/test_frontend_review_tabs_structure.py` by removing the expectations that review is absent from sidebar navigation and that outline/body review use secondary tabs. Add:

```python
def test_contextual_sidebars_include_separated_overall_review_entries() -> None:
    source = read_main()

    assert "type OutlineSelection" in source
    assert "type VolumeSelection" in source
    assert "overall-review" in source
    assert "contextual-review-entry" in source
    assert "setOutlineSelection('overall-review')" in source
    assert "setChapterOutlineSelection('overall-review')" in source
    assert "setChapterBodySelection('overall-review')" in source
    assert "outlineStageView" not in source
    assert "chapterView === 'review'" not in source


def test_selected_chapter_body_volume_contains_batch_and_list_views() -> None:
    source = read_main()

    assert_union_type_includes(source, "ChapterBodyView", "batch", "list")
    assert "chapters/workspace${query}" in source
    assert "selected_volume.chapters" in source
    assert "chapterBodyView === 'batch'" in source
    assert "chapterBodyView === 'list'" in source
```

- [ ] **Step 2: Run the frontend structure tests and confirm failure**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py -q
```

Expected: FAIL because the current component uses `OutlineStageView` and `ChapterView = 'batch' | 'list' | 'review'`.

- [ ] **Step 3: Introduce explicit selection state and a reusable sidebar review entry**

In `web/frontend/src/main.tsx`, replace secondary review types with:

```tsx
type OutlineSelection = string | 'overall-review';
type VolumeSelection = number | 'overall-review';
type ChapterBodyView = 'batch' | 'list';
type ChapterBodyWorkspace = {
  volume_specs: ChapterOutlineVolumeSpec[];
  selected_volume: ChapterOutlineVolumeSpec & { chapters: Chapter[] };
  unassigned: { label: string; chapters: Chapter[] };
};
```

Replace state:

```tsx
const [outlineSelection, setOutlineSelection] = useState<OutlineSelection>('direction');
const [chapterOutlineSelection, setChapterOutlineSelection] = useState<VolumeSelection>(1);
const [chapterBodySelection, setChapterBodySelection] = useState<VolumeSelection>(1);
const [chapterBodyView, setChapterBodyView] = useState<ChapterBodyView>('batch');
const [chapterBodyWorkspace, setChapterBodyWorkspace] = useState<ChapterBodyWorkspace | null>(null);
```

Add a small presentational component:

```tsx
function OverallReviewNavButton({ active, onClick }: { active: boolean; onClick: () => void }) {
  return (
    <button className={active ? 'contextual-review-entry active' : 'contextual-review-entry'} onClick={onClick}>
      <ListChecks size={16} />
      <span>总体审查</span>
    </button>
  );
}
```

- [ ] **Step 4: Render each contextual sidebar according to the approved hierarchy**

In the sidebar block:

```tsx
{topSection === 'outline' && (
  <nav>
    {visibleStages.map((item) => (
      <button className={outlineSelection === item.stage ? 'active' : ''} onClick={() => setOutlineSelection(item.stage)} key={item.stage}>
        <FileText size={16} /><span>{stageLabel(item, item.stage)}</span><small>{item.status}</small>
      </button>
    ))}
    <OverallReviewNavButton active={outlineSelection === 'overall-review'} onClick={() => setOutlineSelection('overall-review')} />
  </nav>
)}
```

Render equivalent `volume_specs.map(...)` lists for `chapter-outline` and `chapters`, ending in `OverallReviewNavButton`. Use selected volume indices to load the corresponding workspace payload; use `chapterBodyWorkspace.unassigned` as an additional list row only when it contains chapters.

- [ ] **Step 5: Move review workspaces out of tabs and add chapter-outline review UI**

Render:

```tsx
{topSection === 'outline' && outlineSelection === 'overall-review' && <OutlineReviewWorkspace ... />}
{topSection === 'outline' && outlineSelection !== 'overall-review' && <OutlineStageWorkspace ... />}
{topSection === 'chapter-outline' && chapterOutlineSelection === 'overall-review' && <ChapterOutlineReviewWorkspace ... />}
{topSection === 'chapter-outline' && chapterOutlineSelection !== 'overall-review' && <ChapterOutlineVolumeWorkspace ... />}
{topSection === 'chapters' && chapterBodySelection === 'overall-review' && <ChapterReviewWorkspace ... />}
{topSection === 'chapters' && chapterBodySelection !== 'overall-review' && <ChapterBodyVolumeWorkspace ... />}
```

Add `ChapterOutlineReviewWorkspace` by reusing the selectable report visual pattern, with suggestions grouped by `volume_index` and submit action calling:

```tsx
await streamAction(
  `/api/projects/${projectId}/outline/chapter-workspace/review/${chapterOutlineReview.run_id}/apply`,
  { selected_issue_ids: selectedChapterOutlineRepairIds },
  (event) => pushLog(event),
);
```

For the selected chapter-body volume, render only:

```tsx
<div className="workspace-tabs" aria-label="当前卷正文视图">
  <button onClick={() => setChapterBodyView('batch')}>批量生成</button>
  <button onClick={() => setChapterBodyView('list')}>已生成章节</button>
</div>
```

Pass the selected volume directly into generation rather than relying on asynchronous state updates, and list chapters from `chapterBodyWorkspace.selected_volume.chapters`:

```tsx
async function generateBatch(selectedVolume: number) {
  await streamAction(
    `/api/projects/${projectId}/chapters/generate-batch`,
    { volume: selectedVolume, chapters: chapterSelector, max_workers: maxWorkers },
    (event) => pushLog(event),
  );
}
```

- [ ] **Step 6: Style contextual review separation and volume workspaces**

In `web/frontend/src/styles.css`, add:

```css
.contextual-review-entry {
  margin-top: 8px;
  padding-top: 12px;
  border-top: 1px solid #d9e0e7;
  color: #13636a;
  font-weight: 600;
}
.progress-item {
  border: 1px solid #d9e0e7;
  border-radius: 6px;
  background: #fff;
  padding: 9px 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.progress-item span {
  color: #647582;
  font-size: 12px;
}
```

Keep existing responsive grid behavior; do not introduce additional decorative layout.

- [ ] **Step 7: Document, build, test, and commit the navigation implementation**

Update the required docs with the final contextual sidebar behavior, chapter-outline review frontend, body-volume selection, and build/test output.

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py tests/test_web_service.py tests/test_web_app.py -q
npm --prefix web/frontend run build
git status --short
```

Expected: PASS; Vite may retain the existing CJS deprecation warning; `.superpowers/` is not staged.

Commit:

```bash
git add web/frontend/src/main.tsx web/frontend/src/styles.css tests/test_frontend_review_tabs_structure.py docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "feat: unify review navigation by context"
```

---

### Task 5: Run Full Web Regression Verification

**Files:**
- Modify only if verification notes need correction: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Run focused backend and frontend checks**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_frontend_review_tabs_structure.py tests/test_progress.py -q
npm --prefix web/frontend run build
```

Expected: all listed tests PASS and frontend build succeeds.

- [ ] **Step 2: Run the complete Python suite**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q
```

Expected: PASS. If a failure is unrelated to this feature, record the exact pre-existing failure and do not hide it.

- [ ] **Step 3: Inspect the final diff and artifact exclusions**

Run:

```bash
git status --short
git log --oneline -5
```

Expected: only deliberately untracked `.superpowers/` visual-companion files remain outside commits; no project artifacts or credentials are staged.

- [ ] **Step 4: Record any final verification correction**

If the most recent `docs/SESSION_SUMMARY.md` entry does not contain the exact final test commands and outcomes, update it, then commit only that documentation correction:

```bash
git add docs/SESSION_SUMMARY.md
git commit -m "docs: record web navigation verification"
```
