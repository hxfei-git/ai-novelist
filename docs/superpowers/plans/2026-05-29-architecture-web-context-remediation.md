# Architecture Web Context Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the remaining architecture, Web operation, and context precision issues while keeping the existing Web runtime and project data compatible.

**Architecture:** Use a test-guarded aggressive refactor. First add focused regression tests for Web operation and context defects, then split large backend/frontend/context modules behind compatibility facades, with a phase summary, verification result, commit, and context-compression note after each phase.

**Tech Stack:** Python 3.12, pytest, FastAPI TestClient, React 19, TypeScript 5.8, Vite 5, existing local `.venv`, existing `npm --prefix web/frontend run build`.

---

## Source Spec

Design document:

- `docs/superpowers/specs/2026-05-29-architecture-web-context-remediation-design.md`

Current verified baseline before implementation:

- `git status --short --branch`: `## main...origin/main [ahead 1]`
- `.venv/bin/python -m pytest -q`: `230 passed in 1.90s`
- `npm --prefix web/frontend run build`: passed with the known Vite CJS Node API deprecation warning

## Execution Rules

- Work on `main`, as requested by the user.
- Do not revert user changes.
- Use `apply_patch` for manual edits.
- Every code-changing task must update `docs/IMPLEMENTATION_PLAN.md` and `docs/SESSION_SUMMARY.md`.
- Every completed task must end with a Git commit.
- At the end of every phase, write a compact continuation note in `docs/SESSION_SUMMARY.md` with:
  - phase name
  - files changed
  - behavior changed
  - tests run and exact result
  - remaining risk
  - next phase entry point
  - one short continuation paragraph suitable for context compression

## File Structure Target

Create or modify these files during the plan:

- Modify `web/frontend/src/main.tsx`: fix immediate UI operation bugs, then shrink it by moving work into hooks and components.
- Modify `web/frontend/src/api.ts`: keep `api()` and `streamAction()` stable, add stronger SSE error parsing only if tests require it.
- Create `web/frontend/src/progress.ts`: progress keying and merge helpers.
- Create `web/frontend/src/workspaces/project.tsx`: project sidebar/onboarding helpers.
- Create `web/frontend/src/workspaces/outline.tsx`: ordinary outline workspace UI.
- Create `web/frontend/src/workspaces/chapterOutline.tsx`: chapter outline workspace UI.
- Create `web/frontend/src/workspaces/chapters.tsx`: chapter generation/list/review workspace UI.
- Create `web/frontend/src/workspaces/review.tsx`: shared review and repair UI components.
- Modify `tests/test_frontend_review_tabs_structure.py`: keep source-level frontend regression tests aligned with the split.
- Modify `src/ai_novelist/context_builder.py`: make contexts source-manifest-first and deduplicated.
- Modify `src/ai_novelist/graph_chapter_write.py`: route direct chapter context through `ContextBundle`.
- Modify `src/ai_novelist/graph_chapter_plan.py`: store context manifest for chapter planning.
- Modify `src/ai_novelist/graph_bible.py`: store context manifest for bible update context.
- Create `src/ai_novelist/workflow_payloads.py`: explicit helpers for high-risk `director_task_args` use.
- Modify `src/ai_novelist/state.py`: retain compatibility while documenting and normalizing context manifests where required.
- Create `src/ai_novelist/web/project_service.py`: project, onboarding, and progress log functions.
- Create `src/ai_novelist/web/outline_actions.py`: ordinary outline stage actions.
- Create `src/ai_novelist/web/chapter_outline_actions.py`: chapter outline workspace and review actions.
- Create `src/ai_novelist/web/chapter_actions.py`: chapter list/detail/batch functions.
- Create `src/ai_novelist/web/review_actions.py`: global review, repair suggestions, repair application.
- Modify `src/ai_novelist/web/service.py`: keep a compatibility facade while route imports migrate.
- Modify `src/ai_novelist/web/app.py`: keep public routes stable while importing clearer action modules where practical.
- Create `src/ai_novelist/outline_graph/prompts.py`: outline prompt builders.
- Create `src/ai_novelist/outline_graph/routing.py`: user intent and stage routing helpers.
- Create `src/ai_novelist/outline_graph/repair.py`: stage structure enforcement helpers.
- Create `src/ai_novelist/outline_graph/artifact_io.py`: artifact formatting, memory, and persistence helpers.
- Create `src/ai_novelist/outline_graph/review_lock.py`: `review_lock` issue parsing and messages.
- Modify `src/ai_novelist/graph_outline.py`: import extracted helpers and keep graph entry points stable.
- Modify focused tests under `tests/` for context, Web service, Web app, graph, and payload helpers.
- Modify `docs/IMPLEMENTATION_PLAN.md`: architecture and workflow notes for every code phase.
- Modify `docs/SESSION_SUMMARY.md`: phase summaries, verification, risks, continuation notes.

## Verification Commands

Use these commands throughout:

```bash
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py -q
.venv/bin/python -m pytest tests/test_context_builder.py -q
.venv/bin/python -m pytest tests/test_web_app.py tests/test_web_service.py -q
.venv/bin/python -m pytest tests/test_graph_volume_write.py tests/test_graph_bible.py tests/test_state.py -q
npm --prefix web/frontend run build
.venv/bin/python -m pytest -q
git status --short --branch
```

---

## Task 1: Frontend Web Operation Regression Tests and Immediate Fixes

**Files:**
- Modify: `tests/test_frontend_review_tabs_structure.py`
- Modify: `web/frontend/src/main.tsx`
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Add failing source-level regression tests for current Web operation bugs**

Add these tests to `tests/test_frontend_review_tabs_structure.py` near the existing frontend behavior tests:

```python
def test_create_project_clears_progress_for_new_project_id() -> None:
    source = read_main()
    create_block = re.search(r"async function createProject\(\).*?\n  }", source, re.DOTALL)
    assert create_block is not None
    assert "async function saveProjectProgressLogForProject" in source
    assert "await saveProjectProgressLogForProject(state.project_id, [])" in create_block.group(0)
    assert "await saveProjectProgressLog([])" not in create_block.group(0)


def test_chapter_batch_generation_has_running_guard_and_disabled_button() -> None:
    source = read_main()
    generate_block = re.search(r"async function generateBatch\(\).*?\n  }", source, re.DOTALL)
    assert generate_block is not None
    assert "const [chapterBatchRunning, setChapterBatchRunning] = useState(false)" in source
    assert "if (chapterBatchRunning) return;" in generate_block.group(0)
    assert "setChapterBatchRunning(true)" in generate_block.group(0)
    assert "setChapterBatchRunning(false)" in generate_block.group(0)
    assert "disabled={chapterBatchRunning || (chapterBatchWorkspace?.remaining_chapters ?? 0) < 1}" in source


def test_chapter_detail_loading_resets_in_finally_for_current_request() -> None:
    source = read_main()
    load_block = re.search(r"async function loadChapter\\(chapter: number\\).*?\n  }", source, re.DOTALL)
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
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py::test_create_project_clears_progress_for_new_project_id tests/test_frontend_review_tabs_structure.py::test_chapter_batch_generation_has_running_guard_and_disabled_button tests/test_frontend_review_tabs_structure.py::test_chapter_detail_loading_resets_in_finally_for_current_request tests/test_frontend_review_tabs_structure.py::test_chapter_batch_generation_reports_errors_and_releases_running_state -q
```

Expected result: failures showing missing `saveProjectProgressLogForProject`, missing `chapterBatchRunning`, and missing `try/finally` or `catch`.

- [ ] **Step 3: Implement the minimal frontend fixes**

In `web/frontend/src/main.tsx`, add the batch running state after `chapterBatchWorkspace`:

```tsx
  const [chapterBatchWorkspace, setChapterBatchWorkspace] = useState<ChapterBatchWorkspace | null>(null);
  const [chapterBatchRunning, setChapterBatchRunning] = useState(false);
```

Replace `saveProjectProgressLog` with an explicit project helper:

```tsx
  async function saveProjectProgressLogForProject(targetProjectId: string, items: ProgressItem[]) {
    if (!targetProjectId) return;
    await api<{ items: ProgressItem[] }>(`/api/projects/${targetProjectId}/progress-log`, {
      method: 'PUT',
      body: JSON.stringify({ items }),
    });
  }

  async function saveProjectProgressLog(items: ProgressItem[]) {
    await saveProjectProgressLogForProject(projectId, items);
  }
```

In `createProject`, clear the new project progress log explicitly:

```tsx
  async function createProject() {
    const state = await api<ProjectState>('/api/projects', { method: 'POST', body: JSON.stringify({ title, project_id: title }) });
    setProjectId(state.project_id);
    setProjectState(state);
    setOnboardingIdea(state.idea || '');
    setLog([]);
    await saveProjectProgressLogForProject(state.project_id, []);
    await refreshProjects();
  }
```

Replace `loadChapter` with:

```tsx
  async function loadChapter(chapter: number) {
    const token = ++chapterRequestRef.current;
    setLoadingChapter(true);
    setChapterDetail(null);
    try {
      const item = await api<Chapter>(`/api/projects/${projectId}/chapters/${chapter}`);
      if (token !== chapterRequestRef.current || chapter !== selectedChapter) return;
      setChapterDetail(item);
    } finally {
      if (token === chapterRequestRef.current && chapter === selectedChapter) setLoadingChapter(false);
    }
  }
```

Replace `generateBatch` with:

```tsx
  async function generateBatch() {
    if (chapterBatchRunning) return;
    const remainingChapters = chapterBatchWorkspace?.remaining_chapters ?? 0;
    const requestedCount = Math.max(1, Number(requestedChapterCount) || 1);
    const actualCount = Math.min(requestedCount, remainingChapters);
    if (actualCount < 1) return;
    setChapterBatchRunning(true);
    pushLog({ label: '章节批量生成', elapsed: '', tokens: '', context: '', status: 'started' });
    try {
      await streamAction(
        `/api/projects/${projectId}/chapters/generate-batch`,
        { volume, requested_count: actualCount },
        (line) => pushLog(line),
      );
      await refreshChapters(true, volume);
      pushLog({ label: '章节批量生成', elapsed: '', tokens: '', context: '', status: 'completed' });
    } catch (error) {
      showError(error);
    } finally {
      setChapterBatchRunning(false);
    }
  }
```

Update the batch button:

```tsx
                <button onClick={generateBatch} disabled={chapterBatchRunning || (chapterBatchWorkspace?.remaining_chapters ?? 0) < 1}><Play size={16} />{chapterBatchRunning ? '生成中' : '生成章节'}</button>
```

- [ ] **Step 4: Run focused frontend source tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py -q
```

Expected result: all tests in the file pass.

- [ ] **Step 5: Run frontend build**

Run:

```bash
npm --prefix web/frontend run build
```

Expected result: build passes. The Vite CJS Node API deprecation warning may appear.

- [ ] **Step 6: Update documentation and phase summary**

In `docs/IMPLEMENTATION_PLAN.md`, add a dated bullet under the current Web architecture section:

```markdown
- 2026-05-29: Web operation hardening started with explicit project-scoped progress log writes, chapter detail loading cleanup, and chapter batch running guards. Public API paths remain unchanged.
```

In `docs/SESSION_SUMMARY.md`, add a phase summary containing the focused tests and build result:

```markdown
### Phase 1: Web Operation Logic
- Files changed: `web/frontend/src/main.tsx`, `tests/test_frontend_review_tabs_structure.py`, docs.
- Behavior changed: new project progress log writes target the newly created project id; chapter detail loading resets through `finally`; chapter batch generation has a running guard and error reporting.
- Verification: `.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py -q`; `npm --prefix web/frontend run build`.
- Remaining risk: browser-level click behavior is still represented by source-level assertions and build verification.
- Next entry point: continue with SSE and Web route error behavior tests.
- Continuation note: resume at Task 2 in `docs/superpowers/plans/2026-05-29-architecture-web-context-remediation.md`; do not revisit Task 1 unless its focused tests fail.
```

- [ ] **Step 7: Commit Task 1**

Run:

```bash
git add web/frontend/src/main.tsx tests/test_frontend_review_tabs_structure.py docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "fix: harden web operation guards"
```

Expected result: commit succeeds.

---

## Task 2: SSE and Web Route Error Behavior

**Files:**
- Modify: `tests/test_frontend_review_tabs_structure.py`
- Modify: `tests/test_web_app.py`
- Modify: `web/frontend/src/main.tsx`
- Modify: `src/ai_novelist/web/app.py`
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Add frontend source tests for consistent action error handling**

Add these tests to `tests/test_frontend_review_tabs_structure.py`:

```python
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
        block = re.search(rf"async function {function_name}\\(.*?\\n  }}", source, re.DOTALL)
        assert block is not None, function_name
        assert "} catch (error) {" in block.group(0), function_name
        assert "showError(error)" in block.group(0), function_name


def test_chapter_outline_volume_action_releases_running_flag_in_finally() -> None:
    source = read_main()
    block = re.search(r"async function runChapterOutlineVolume\\(.*?\\n  }", source, re.DOTALL)
    assert block is not None
    text = block.group(0)
    assert "setChapterOutlineRunning(true)" in text
    assert "setChapterOutlineRunning(false)" in text.split("finally", 1)[1]
```

- [ ] **Step 2: Add Web app SSE error event regression test**

Add this test to `tests/test_web_app.py`:

```python
def test_sse_route_returns_error_event_when_service_raises(monkeypatch, tmp_path) -> None:
    client = TestClient(web_app.make_app(Settings(projects_dir=tmp_path), mock=True))
    created = client.post("/api/projects", json={"title": "Web Demo", "project_id": "web-demo"})
    assert created.status_code == 200

    def fake_generate(store, adapter, project_id, stage, instruction="", progress=None):
        raise web_app.service.LocalStoreError("阶段不可执行")

    monkeypatch.setattr(web_app.service, "generate_outline_stage", fake_generate)

    response = client.post("/api/projects/web-demo/outline/stages/worldbuilding/generate", json={})

    assert response.status_code == 200
    assert "event: error" in response.text
    assert "阶段不可执行" in response.text
```

- [ ] **Step 3: Run the new tests and verify failures**

Run:

```bash
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py::test_streaming_workspace_actions_report_errors tests/test_frontend_review_tabs_structure.py::test_chapter_outline_volume_action_releases_running_flag_in_finally tests/test_web_app.py::test_sse_route_returns_error_event_when_service_raises -q
```

Expected result: frontend source test fails until all streaming actions catch errors. The SSE route test may fail because `LocalStoreError` is not available through `web_app.service`.

- [ ] **Step 4: Make `LocalStoreError` available to the monkeypatched service module**

In `src/ai_novelist/web/service.py`, ensure this import remains public:

```python
from ai_novelist.storage.local_store import LocalStore, LocalStoreError, summarize_text
```

Do not hide `LocalStoreError` behind `__all__` during this task.

- [ ] **Step 5: Add catch blocks to remaining frontend streaming actions**

Use this pattern in every streaming action that currently lacks `catch`:

```tsx
    } catch (error) {
      showError(error);
    } finally {
      setSomeRunningFlag(false);
    }
```

For `runStage`, preserve the `stageRunningRef` reset:

```tsx
  async function runStage(action: 'generate' | 'revise' | 'lock') {
    if (stageRunningRef.current) return;
    stageRunningRef.current = true;
    setStageRunning(true);
    try {
      await streamAction(
        `/api/projects/${projectId}/outline/stages/${activeStage}/${action}`,
        { instruction },
        (line) => pushLog(line),
      );
      setInstruction('');
      await refreshStages();
      await loadStage(activeStage);
    } catch (error) {
      showError(error);
    } finally {
      stageRunningRef.current = false;
      setStageRunning(false);
    }
  }
```

For `runChapterOutlineVolume`, use:

```tsx
  async function runChapterOutlineVolume(action: 'generate' | 'revise' | 'lock') {
    if (!chapterOutlineWorkspace || chapterOutlineRunning) return;
    const volumeIndex = chapterOutlineWorkspace.selected_volume.index;
    setChapterOutlineRunning(true);
    try {
      await streamAction(
        `/api/projects/${projectId}/outline/chapter-workspace/volumes/${volumeIndex}/${action}`,
        { instruction },
        (line) => pushLog(line),
      );
      await loadChapterOutlineWorkspace(action === 'lock' ? undefined : volumeIndex);
    } catch (error) {
      showError(error);
    } finally {
      setChapterOutlineRunning(false);
    }
  }
```

For `reviewAll`, add:

```tsx
    } catch (error) {
      showError(error);
    } finally {
      setReviewRunning(false);
    }
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py::test_streaming_workspace_actions_report_errors tests/test_frontend_review_tabs_structure.py::test_chapter_outline_volume_action_releases_running_flag_in_finally tests/test_web_app.py::test_sse_route_returns_error_event_when_service_raises -q
```

Expected result: all selected tests pass.

- [ ] **Step 7: Run Web app and frontend regression checks**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_app.py tests/test_frontend_review_tabs_structure.py -q
npm --prefix web/frontend run build
```

Expected result: all tests pass and frontend build passes.

- [ ] **Step 8: Update docs and commit**

Add to `docs/SESSION_SUMMARY.md`:

```markdown
### Phase 1b: SSE and Web Error Handling
- Files changed: frontend action handlers, Web app tests, docs.
- Behavior changed: streaming Web actions report errors consistently and release running flags through `finally`; SSE service failures are represented as `event: error`.
- Verification: `.venv/bin/python -m pytest tests/test_web_app.py tests/test_frontend_review_tabs_structure.py -q`; `npm --prefix web/frontend run build`.
- Remaining risk: source tests verify handler structure; browser event-loop behavior is still covered indirectly.
- Next entry point: begin Task 3 context manifest and deduplication work.
- Continuation note: resume with context builder tests in Task 3; Web operation guard changes are complete when both focused commands above pass.
```

Run:

```bash
git add src/ai_novelist/web/app.py src/ai_novelist/web/service.py web/frontend/src/main.tsx tests/test_web_app.py tests/test_frontend_review_tabs_structure.py docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "fix: surface web stream errors consistently"
```

Expected result: commit succeeds.

---

## Task 3: Context Manifest Source Paths and Deduplication

**Files:**
- Modify: `tests/test_context_builder.py`
- Modify: `src/ai_novelist/context_builder.py`
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Add failing context manifest and dedup tests**

Add these tests to `tests/test_context_builder.py`:

```python
def test_context_manifest_records_artifact_path(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    save_markdown_artifact(
        store.project_dir("demo"),
        "chapters/chapter_001/chapter_card.md",
        "# 章节卡\n\n唯一章节卡内容",
        "chapter_card",
        chapter=1,
    )

    bundle = build_context_bundle(state, store, "drafting", chapter=1)
    manifest = build_context_manifest(bundle)

    assert any(item["path"] == "chapters/chapter_001/chapter_card.md" for item in manifest)
    assert any(item["source_type"] == "artifact:chapter_card" for item in manifest)


def test_context_deduplicates_artifact_and_state_fallback_by_digest(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.current_chapter_card = "# 章节卡\n\n唯一重复内容"
    save_markdown_artifact(
        store.project_dir("demo"),
        "chapters/chapter_001/chapter_card.md",
        "# 章节卡\n\n唯一重复内容",
        "chapter_card",
        chapter=1,
    )

    bundle = build_context_bundle(state, store, "drafting", chapter=1)

    assert bundle.text.count("唯一重复内容") == 1
    assert len({item.digest for item in bundle.sources if item.digest}) == len([item for item in bundle.sources if item.digest])
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_context_builder.py::test_context_manifest_records_artifact_path tests/test_context_builder.py::test_context_deduplicates_artifact_and_state_fallback_by_digest -q
```

Expected result: manifest path/source type assertions fail, and duplicate content may appear twice.

- [ ] **Step 3: Add a structured section record to `context_builder.py`**

In `src/ai_novelist/context_builder.py`, replace the current `Section = tuple[str, str]` definition with:

```python
@dataclass(frozen=True)
class SectionRecord:
    title: str
    content: str
    source_type: str
    path: str | None = None
    priority: int = 100


Section = tuple[str, str] | SectionRecord
```

Add these helpers below `build_context_manifest`:

```python
def section_record(title: str, content: str, source_type: str, path: str | None = None, priority: int = 100) -> SectionRecord:
    return SectionRecord(title=title, content=content, source_type=source_type, path=path, priority=priority)


def section_title(section: Section) -> str:
    return section.title if isinstance(section, SectionRecord) else section[0]


def section_content(section: Section) -> str:
    return section.content if isinstance(section, SectionRecord) else section[1]


def section_source_type(section: Section, profile: ContextProfile) -> str:
    return section.source_type if isinstance(section, SectionRecord) else profile.name


def section_path(section: Section) -> str | None:
    return section.path if isinstance(section, SectionRecord) else None


def section_priority(section: Section) -> int:
    return section.priority if isinstance(section, SectionRecord) else 100
```

- [ ] **Step 4: Expand artifact sections into source-specific records**

Change `build_profile_section` so `chapter_artifacts` can return a composite string through a new helper first, then replace it with list-aware handling in `build_context_bundle`.

Add this function near `build_artifact_section`:

```python
def build_artifact_section_records(
    state: NovelState,
    store: LocalStore,
    purpose: str,
    chapter: int | None,
    stage: str | None,
    artifact_types: tuple[str, ...] | None = None,
) -> list[SectionRecord]:
    project_dir = store.project_dir(state.project_id)
    records: list[SectionRecord] = []
    for artifact_type in artifact_types or tuple(PURPOSE_ARTIFACT_TYPES.get(purpose, [])):
        record = get_latest_artifact(project_dir, artifact_type, chapter=chapter)
        if record is None and stage:
            record = get_latest_artifact(project_dir, artifact_type, stage=stage)
        if record is None:
            record = get_latest_artifact(project_dir, artifact_type)
        if record is None:
            continue
        text = load_artifact_text(project_dir, record).strip()
        records.append(
            section_record(
                f"当前任务 Artifact: {artifact_type}",
                text or "暂无",
                f"artifact:{artifact_type}",
                record.path,
                priority=10,
            )
        )
    fallback = build_state_artifact_fallback_records(state, purpose)
    records.extend(fallback)
    return records
```

Replace `build_state_artifact_fallback` with record-producing support while keeping the old function for compatibility:

```python
def build_state_artifact_fallback_records(state: NovelState, purpose: str) -> list[SectionRecord]:
    records: list[SectionRecord] = []
    if purpose in {"scene_design", "drafting", "review", "revision"} and state.current_chapter_card.strip():
        records.append(section_record("当前任务 Artifact: current_chapter_card", state.current_chapter_card.strip(), "state:current_chapter_card", "state:current_chapter_card", priority=80))
    if purpose in {"drafting", "review", "revision"} and state.current_scene_cards.strip():
        records.append(section_record("当前任务 Artifact: current_scene_cards", state.current_scene_cards.strip(), "state:current_scene_cards", "state:current_scene_cards", priority=80))
    if purpose == "revision" and state.chapter_draft.strip():
        records.append(section_record("当前任务 Artifact: chapter_draft", state.chapter_draft.strip(), "state:chapter_draft", "state:chapter_draft", priority=80))
    if purpose == "revision" and state.current_review_report.strip():
        records.append(section_record("当前任务 Artifact: current_review_report", state.current_review_report.strip(), "state:current_review_report", "state:current_review_report", priority=80))
    return records


def build_state_artifact_fallback(state: NovelState, purpose: str) -> str:
    return "\n\n".join(f"## {record.path}\n{record.content}" for record in build_state_artifact_fallback_records(state, purpose))
```

Update `build_context_bundle` so it expands artifact records:

```python
    sections: list[Section] = []
    for key in profile.sections:
        if key == "chapter_artifacts":
            records = build_artifact_section_records(state, store, profile.purpose, selected_chapter, selected_stage, artifact_types=profile.artifact_types)
            sections.extend(records if records else [section_record("当前任务 Artifact", "暂无", profile.name)])
        else:
            sections.append(build_profile_section(key, state, store, profile, selected_chapter, selected_stage))
```

- [ ] **Step 5: Deduplicate sections by digest before rendering**

Replace the start of `render_profile_sections` with this logic:

```python
def render_profile_sections(sections: list[Section], profile: ContextProfile, max_chars: int) -> tuple[str, list[ContextSource]]:
    protected_titles = {"用户当前请求", "当前任务", "锁定约束"}
    unique_sections: list[Section] = []
    seen: dict[str, Section] = {}
    for section in sorted(sections, key=section_priority):
        original = (section_content(section) or "暂无").strip() or "暂无"
        digest = sha256_text(original)
        if digest in seen:
            continue
        seen[digest] = section
        unique_sections.append(section)
    unique_sections.sort(key=lambda item: sections.index(item))
    rendered_parts: list[tuple[str, str]] = []
    sources: list[ContextSource] = []
    fixed_overhead = len("# Task Context\n\n") + sum(len(f"## {section_title(section)}\n\n") + 2 for section in unique_sections)
    remaining = max(1, max_chars - fixed_overhead)
    default_budget = max(120, remaining // max(1, len(unique_sections)))
    for section in unique_sections:
        title = section_title(section)
        original = (section_content(section) or "暂无").strip() or "暂无"
        budget = profile.per_section_budget.get(title, default_budget)
        if title in protected_titles:
            budget = max(budget, min(len(original), 1200))
        included = original
        truncated = False
        if len(included) > budget:
            included = included[: max(40, budget - 28)].rstrip() + "\n[已截断，完整内容见 artifact path]"
            truncated = True
        rendered_parts.append((title, included))
        sources.append(
            ContextSource(
                section=title,
                source_type=section_source_type(section, profile),
                path=section_path(section),
                original_chars=len(original),
                included_chars=len(included),
                truncated=truncated,
                digest=sha256_text(original),
            )
        )
```

Keep the existing final `text = render_sections(rendered_parts)` and max length truncation logic below this replacement.

- [ ] **Step 6: Run focused context tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_context_builder.py -q
```

Expected result: all context builder tests pass.

- [ ] **Step 7: Update docs and commit**

Add to `docs/IMPLEMENTATION_PLAN.md`:

```markdown
- 2026-05-29: Context profiles now record source paths and suppress duplicate artifact/state fallback content by digest before rendering.
```

Add to `docs/SESSION_SUMMARY.md`:

```markdown
### Phase 2: Context Manifest Paths and Deduplication
- Files changed: `src/ai_novelist/context_builder.py`, `tests/test_context_builder.py`, docs.
- Behavior changed: context manifests now expose artifact paths and source types; repeated artifact/state fallback content is deduplicated by digest.
- Verification: `.venv/bin/python -m pytest tests/test_context_builder.py -q`.
- Remaining risk: direct chapter writing still uses its own context assembler until Task 4.
- Next entry point: migrate direct chapter context to `ContextBundle`.
- Continuation note: resume at Task 4; keep Task 3 helper names unchanged because later tasks use `SectionRecord` and `build_artifact_section_records`.
```

Run:

```bash
git add src/ai_novelist/context_builder.py tests/test_context_builder.py docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "feat: track context sources and dedupe content"
```

Expected result: commit succeeds.

---

## Task 4: Direct Chapter Context Profile Migration

**Files:**
- Modify: `tests/test_context_builder.py`
- Modify: `tests/test_graph_volume_write.py`
- Modify: `src/ai_novelist/context_builder.py`
- Modify: `src/ai_novelist/graph_chapter_write.py`
- Modify: `src/ai_novelist/graph_volume_write.py`
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Add tests for direct chapter context profile**

Add this test to `tests/test_context_builder.py`:

```python
def test_direct_chapter_context_profile_uses_selected_outline_and_manifest(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.user_request = "写第 2 章"
    state.active_chapter = 2
    state.current_chapter = 2
    state.director_task_args["selected_chapter_outline"] = "第 2 章专属大纲"
    state.chapter_summaries = {"1": "第一章摘要", "2": "当前章摘要不应注入"}

    bundle = build_context_bundle(state, store, "direct_chapter_drafting", chapter=2)
    manifest = build_context_manifest(bundle)

    assert "第 2 章专属大纲" in bundle.text
    assert "第一章摘要" in bundle.text
    assert "当前章摘要不应注入" not in bundle.text
    assert any(item["section"] == "章节大纲切片" for item in manifest)
```

Add this test to `tests/test_graph_volume_write.py`:

```python
def test_volume_write_records_direct_context_manifest(monkeypatch, tmp_path):
    from ai_novelist.adapters.mock_codex import MockCodexAdapter
    from ai_novelist.graph_volume_write import build_volume_write_graph
    from ai_novelist.storage.local_store import LocalStore

    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.director_task_args = {"volume": 1, "chapters": "1"}
    state.outline_stage_artifacts["chapter_outline"] = {
        "stage": "chapter_outline",
        "synthesis": "#### 第 1 章：开局\n- 第一章专属大纲。",
    }
    store.save_state(state)

    result = build_volume_write_graph(MockCodexAdapter(), store).invoke(state.to_dict())

    manifest = result["director_task_args"].get("direct_chapter_context_manifest")
    assert isinstance(manifest, list)
    assert any(item.get("section") == "章节大纲切片" for item in manifest)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_context_builder.py::test_direct_chapter_context_profile_uses_selected_outline_and_manifest tests/test_graph_volume_write.py::test_volume_write_records_direct_context_manifest -q
```

Expected result: fails because `direct_chapter_drafting` profile and manifest storage do not exist yet.

- [ ] **Step 3: Add the direct chapter context profile**

In `src/ai_novelist/context_builder.py`, add this profile to `CONTEXT_PROFILES`:

```python
    "direct_chapter_drafting": ContextProfile(
        name="direct_chapter_drafting",
        purpose="drafting",
        max_chars=18000,
        sections=("user_request", "locked_constraints", "author_craft", "bible_digest", "chapter_outline_slice", "previous_chapter_summaries"),
        include_reference="none",
        include_bible="full",
    ),
```

Update `build_chapter_outline_slice_section` so it first uses an already selected chapter outline:

```python
    selected_existing = str(state.director_task_args.get("selected_chapter_outline") or "").strip()
    if selected_existing and selected_existing != "暂无":
        return selected_existing
```

Place that snippet after `selected = chapter or state.active_chapter or state.current_chapter or 1`.

- [ ] **Step 4: Replace direct context assembly in `graph_chapter_write.py`**

At the imports in `src/ai_novelist/graph_chapter_write.py`, import the bundle helpers:

```python
from ai_novelist.context_builder import build_context_bundle, build_context_manifest
```

Replace `context = build_direct_chapter_context(state, store)` in `load_direct_write_context_node` with:

```python
    bundle = build_context_bundle(state, store, "direct_chapter_drafting", chapter=state.active_chapter)
    context = bundle.text
    state.director_task_args["direct_chapter_context_manifest"] = build_context_manifest(bundle)
```

Keep `state.director_task_args["direct_chapter_context"] = context`.

Update `build_direct_chapter_context` to delegate to the bundle for compatibility:

```python
def build_direct_chapter_context(state: NovelState, store: LocalStore, max_chars: int = 18000) -> str:
    return build_context_bundle(state, store, "direct_chapter_drafting", chapter=state.active_chapter or state.current_chapter, max_chars=max_chars).text
```

- [ ] **Step 5: Store direct context manifest in volume write**

In `src/ai_novelist/graph_volume_write.py`, after the call to `build_direct_chapter_context(chapter_state, store)`, add:

```python
        chapter_state.director_task_args["direct_chapter_context_manifest"] = chapter_state.director_task_args.get("direct_chapter_context_manifest", [])
```

If volume write builds context directly through `build_direct_chapter_context`, replace that call with a helper that returns both text and manifest:

```python
        context = build_direct_chapter_context(chapter_state, store)
        chapter_state.director_task_args["direct_chapter_context"] = context
```

Then update `build_direct_chapter_context` as described in Step 4 so the manifest is set during chapter write load. Preserve existing volume batch output behavior.

- [ ] **Step 6: Run focused graph/context tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_context_builder.py tests/test_graph_volume_write.py -q
```

Expected result: all selected tests pass.

- [ ] **Step 7: Update docs and commit**

Add to `docs/SESSION_SUMMARY.md`:

```markdown
### Phase 2b: Direct Chapter Context Migration
- Files changed: context builder, direct chapter write graph, volume write graph tests, docs.
- Behavior changed: direct chapter drafting uses the shared context profile and records a context manifest.
- Verification: `.venv/bin/python -m pytest tests/test_context_builder.py tests/test_graph_volume_write.py -q`.
- Remaining risk: other workflows still read some payload values directly from `director_task_args`.
- Next entry point: introduce workflow payload helpers in Task 5.
- Continuation note: resume at Task 5; direct drafting context should remain profile name `direct_chapter_drafting`.
```

Run:

```bash
git add src/ai_novelist/context_builder.py src/ai_novelist/graph_chapter_write.py src/ai_novelist/graph_volume_write.py tests/test_context_builder.py tests/test_graph_volume_write.py docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "feat: unify direct chapter context profile"
```

Expected result: commit succeeds.

---

## Task 5: Workflow Payload Helper Layer

**Files:**
- Create: `src/ai_novelist/workflow_payloads.py`
- Create: `tests/test_workflow_payloads.py`
- Modify: `src/ai_novelist/graph_chapter_plan.py`
- Modify: `src/ai_novelist/graph_chapter_write.py`
- Modify: `src/ai_novelist/graph_volume_write.py`
- Modify: `src/ai_novelist/web/service.py`
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Add tests for payload helpers**

Create `tests/test_workflow_payloads.py`:

```python
from ai_novelist.state import NovelState
from ai_novelist.workflow_payloads import (
    chapter_batch_payload,
    get_task_arg_int,
    get_task_arg_str,
    set_chapter_batch_payload,
    set_task_arg,
)


def test_task_arg_helpers_normalize_values() -> None:
    state = NovelState(project_id="demo", title="Demo")
    set_task_arg(state, "chapter", 3)
    set_task_arg(state, "notes", "  revise  ")

    assert get_task_arg_int(state, "chapter", 1) == 3
    assert get_task_arg_str(state, "notes") == "revise"
    assert get_task_arg_int(state, "missing", 7) == 7


def test_chapter_batch_payload_round_trip() -> None:
    state = NovelState(project_id="demo", title="Demo")

    set_chapter_batch_payload(state, volume=2, requested_count=3, chapters=[4, 5, 6])
    payload = chapter_batch_payload(state)

    assert payload.volume == 2
    assert payload.requested_count == 3
    assert payload.chapters == [4, 5, 6]
    assert state.director_task_args["chapters"] == "4,5,6"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_workflow_payloads.py -q
```

Expected result: import failure for `ai_novelist.workflow_payloads`.

- [ ] **Step 3: Create payload helper module**

Create `src/ai_novelist/workflow_payloads.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from ai_novelist.graph_volume_write import parse_chapter_override
from ai_novelist.state import NovelState


def set_task_arg(state: NovelState, key: str, value: Any) -> None:
    state.director_task_args[str(key)] = value


def get_task_arg_str(state: NovelState, key: str, default: str = "") -> str:
    value = state.director_task_args.get(key, default)
    return str(value or default).strip()


def get_task_arg_int(state: NovelState, key: str, default: int = 0) -> int:
    value = state.director_task_args.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_task_arg_dict(state: NovelState, key: str) -> dict[str, Any]:
    value = state.director_task_args.get(key)
    return dict(value) if isinstance(value, dict) else {}


def get_task_arg_list(state: NovelState, key: str) -> list[Any]:
    value = state.director_task_args.get(key)
    return list(value) if isinstance(value, list) else []


@dataclass(frozen=True)
class ChapterBatchPayload:
    volume: int
    requested_count: int | None
    chapters: list[int]
    run_id: str


def set_chapter_batch_payload(
    state: NovelState,
    *,
    volume: int,
    requested_count: int | None = None,
    chapters: Iterable[int] | str | None = None,
    run_id: str = "",
) -> None:
    state.director_task_args["volume"] = int(volume)
    if requested_count is not None:
        state.director_task_args["requested_count"] = int(requested_count)
    if chapters is not None:
        if isinstance(chapters, str):
            chapter_text = chapters
        else:
            chapter_text = ",".join(str(int(item)) for item in chapters)
        if chapter_text.strip():
            state.director_task_args["chapters"] = chapter_text.strip()
    if run_id:
        state.director_task_args["batch_run_id"] = run_id


def chapter_batch_payload(state: NovelState) -> ChapterBatchPayload:
    requested = state.director_task_args.get("requested_count")
    try:
        requested_count = int(requested) if requested is not None else None
    except (TypeError, ValueError):
        requested_count = None
    return ChapterBatchPayload(
        volume=get_task_arg_int(state, "volume", 1),
        requested_count=requested_count,
        chapters=parse_chapter_override(state.director_task_args.get("chapters")),
        run_id=get_task_arg_str(state, "batch_run_id"),
    )
```

- [ ] **Step 4: Avoid import cycle with `parse_chapter_override`**

If importing `parse_chapter_override` from `graph_volume_write` creates an import cycle, move the parse helper into `workflow_payloads.py`:

```python
def parse_chapter_selector(value: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, list):
        return [int(item) for item in value if str(item).strip().isdigit()]
    text = str(value or "").strip()
    if not text:
        return []
    chapters: list[int] = []
    for part in text.split(","):
        item = part.strip()
        if "-" in item:
            start_raw, end_raw = item.split("-", 1)
            if start_raw.strip().isdigit() and end_raw.strip().isdigit():
                start = int(start_raw)
                end = int(end_raw)
                chapters.extend(range(start, end + 1))
        elif item.isdigit():
            chapters.append(int(item))
    return chapters
```

Then replace `parse_chapter_override(...)` in `chapter_batch_payload` with `parse_chapter_selector(...)`.

- [ ] **Step 5: Replace high-risk raw payload writes in Web batch generation**

In `src/ai_novelist/web/service.py`, import:

```python
from ai_novelist.workflow_payloads import set_chapter_batch_payload
```

In `generate_chapter_batch`, replace direct initialization:

```python
    state.director_task_args = {"volume": volume}
```

with:

```python
    state.director_task_args = {}
    set_chapter_batch_payload(state, volume=volume)
```

Replace requested count writes:

```python
        state.director_task_args["requested_count"] = requested_total
        state.director_task_args["chapters"] = ",".join(str(item) for item in selected_numbers)
```

with:

```python
        set_chapter_batch_payload(state, volume=volume, requested_count=requested_total, chapters=selected_numbers)
```

Replace chapter selector writes:

```python
            state.director_task_args["chapters"] = chapter_text
```

with:

```python
            set_chapter_batch_payload(state, volume=volume, chapters=chapter_text)
```

- [ ] **Step 6: Replace simple reads in chapter plan/write entry nodes**

In `src/ai_novelist/graph_chapter_plan.py`, import:

```python
from ai_novelist.workflow_payloads import get_task_arg_int, set_task_arg
```

Replace:

```python
    chapter = int(state.director_task_args.get("chapter") or state.current_chapter or state.active_chapter or 1)
```

with:

```python
    chapter = get_task_arg_int(state, "chapter", state.current_chapter or state.active_chapter or 1)
```

Replace writes such as:

```python
    state.director_task_args["selected_chapter_outline"] = chapter_outline
```

with:

```python
    set_task_arg(state, "selected_chapter_outline", chapter_outline)
```

In `src/ai_novelist/graph_chapter_write.py`, apply the same `get_task_arg_int` and `set_task_arg` pattern in `load_direct_write_context_node`.

- [ ] **Step 7: Run payload and workflow tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_workflow_payloads.py tests/test_graph_volume_write.py tests/test_web_service.py::test_chapter_batch_payload_sets_director_task_args -q
```

Expected result: all selected tests pass.

- [ ] **Step 8: Update docs and commit**

Add to `docs/SESSION_SUMMARY.md`:

```markdown
### Phase 3: Workflow Payload Helpers
- Files changed: `src/ai_novelist/workflow_payloads.py`, chapter workflow entry points, Web batch generation, tests, docs.
- Behavior changed: high-risk chapter and batch payload reads/writes use named helpers while preserving `director_task_args` persistence compatibility.
- Verification: `.venv/bin/python -m pytest tests/test_workflow_payloads.py tests/test_graph_volume_write.py tests/test_web_service.py::test_chapter_batch_payload_sets_director_task_args -q`.
- Remaining risk: outline and Craft payload keys still have raw reads until later graph/service extraction tasks.
- Next entry point: split Web service modules behind compatibility imports.
- Continuation note: resume at Task 6; keep `workflow_payloads.py` helper names stable for later replacements.
```

Run:

```bash
git add src/ai_novelist/workflow_payloads.py src/ai_novelist/graph_chapter_plan.py src/ai_novelist/graph_chapter_write.py src/ai_novelist/graph_volume_write.py src/ai_novelist/web/service.py tests/test_workflow_payloads.py docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "refactor: add workflow payload helpers"
```

Expected result: commit succeeds.

---

## Task 6: Project and Progress Web Service Split

**Files:**
- Create: `src/ai_novelist/web/project_service.py`
- Modify: `src/ai_novelist/web/service.py`
- Modify: `tests/test_web_service.py`
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Add import tests for the new project service module**

Add this test to `tests/test_web_service.py`:

```python
def test_project_service_exports_project_and_progress_helpers() -> None:
    from ai_novelist.web import project_service

    for name in [
        "list_projects",
        "create_project",
        "project_needs_onboarding",
        "save_project_idea",
        "load_project_progress_log",
        "save_project_progress_log",
        "build_progress_event",
    ]:
        assert hasattr(project_service, name)
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_project_service_exports_project_and_progress_helpers -q
```

Expected result: import failure for `ai_novelist.web.project_service`.

- [ ] **Step 3: Create `project_service.py` by moving functions unchanged**

Create `src/ai_novelist/web/project_service.py` with the imports and these functions moved from `service.py`:

```python
from __future__ import annotations

import re
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore, LocalStoreError

ProgressItem = str | dict[str, str]
MAX_WEB_PROGRESS_LOG_ITEMS = 10


@dataclass(frozen=True)
class WebProject:
    project_id: str
    title: str
    path: str
```

Move the existing bodies for:

- `list_projects`
- `create_project`
- `project_needs_onboarding`
- `save_project_idea`
- `project_progress_log_path`
- `normalize_progress_log_items`
- `build_progress_event`
- `load_project_progress_log`
- `save_project_progress_log`

Do not change behavior while moving.

- [ ] **Step 4: Re-export project helpers from `service.py`**

In `src/ai_novelist/web/service.py`, import:

```python
from ai_novelist.web.project_service import (
    MAX_WEB_PROGRESS_LOG_ITEMS,
    ProgressItem,
    WebProject,
    build_progress_event,
    create_project,
    list_projects,
    load_project_progress_log,
    normalize_progress_log_items,
    project_needs_onboarding,
    project_progress_log_path,
    save_project_idea,
    save_project_progress_log,
)
```

Remove the moved definitions from `service.py` after confirming the imported names satisfy existing route and test references.

- [ ] **Step 5: Run focused Web tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_project_service_exports_project_and_progress_helpers tests/test_web_service.py::test_project_progress_log_accepts_legacy_strings_and_structured_events tests/test_web_app.py::test_project_idea_and_progress_log_endpoints_are_project_scoped -q
```

Expected result: all selected tests pass.

- [ ] **Step 6: Update docs and commit**

Add to `docs/SESSION_SUMMARY.md`:

```markdown
### Phase 4a: Project Service Split
- Files changed: `src/ai_novelist/web/project_service.py`, `src/ai_novelist/web/service.py`, Web tests, docs.
- Behavior changed: project and progress logic moved behind a focused service module; `web/service.py` remains a compatibility facade.
- Verification: focused project/progress Web tests passed.
- Remaining risk: outline, chapter, and review functions still live in `web/service.py`.
- Next entry point: split outline actions.
- Continuation note: resume at Task 7; project/progress imports should come from `ai_novelist.web.project_service` for new code.
```

Run:

```bash
git add src/ai_novelist/web/project_service.py src/ai_novelist/web/service.py tests/test_web_service.py docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "refactor: extract web project service"
```

Expected result: commit succeeds.

---

## Task 7: Outline and Chapter Outline Web Action Split

**Files:**
- Create: `src/ai_novelist/web/outline_actions.py`
- Create: `src/ai_novelist/web/chapter_outline_actions.py`
- Modify: `src/ai_novelist/web/service.py`
- Modify: `tests/test_web_service.py`
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Add export tests for the new action modules**

Add this test to `tests/test_web_service.py`:

```python
def test_outline_action_modules_export_web_entry_points() -> None:
    from ai_novelist.web import chapter_outline_actions, outline_actions

    for name in [
        "load_outline_stage_payload",
        "save_outline_stage_content",
        "outline_stage_pending_payload",
        "submit_stage_pending_answers",
        "generate_outline_stage",
        "revise_outline_stage",
        "lock_outline_stage",
        "review_outline",
        "apply_outline_review",
    ]:
        assert hasattr(outline_actions, name)

    for name in [
        "chapter_outline_workspace_payload",
        "generate_chapter_outline_volume",
        "revise_chapter_outline_volume",
        "lock_chapter_outline_volume",
        "review_chapter_outline",
        "apply_chapter_outline_review",
        "latest_chapter_outline_review_report",
    ]:
        assert hasattr(chapter_outline_actions, name)
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_outline_action_modules_export_web_entry_points -q
```

Expected result: import failures for the new modules.

- [ ] **Step 3: Create `outline_actions.py`**

Create `src/ai_novelist/web/outline_actions.py`. Move these functions from `service.py` unchanged:

- `load_outline_stage_payload`
- `save_outline_stage_content`
- `outline_stage_pending_payload`
- `review_outline`
- `apply_outline_review`
- `normalize_pending_answers`
- `build_pending_revision_instruction`
- `submit_stage_pending_answers`
- `generate_outline_stage`
- `revise_outline_stage`
- `lock_outline_stage`
- `strip_markdown_heading`

Use imports already present in `service.py` that these functions require:

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ai_novelist.adapters.base import AgentAdapter
from ai_novelist.graph_outline import advance_outline_stage_node, run_outline_stage_node
from ai_novelist.outline.stage_contracts import STAGE_LABELS
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore, LocalStoreError, summarize_text
from ai_novelist.web.outline_service import (
    build_outline_repair_suggestions,
    ensure_ordinary_stage_mutation,
    ensure_outline_stage_mutable,
    ensure_valid_stage,
    has_outline_stage_content,
    latest_outline_review_report,
    load_outline_review_report,
    outline_review_source_text,
    outline_stage_action_state,
    outline_stage_payload,
    selected_outline_revision_instruction,
    write_outline_review_baseline_sections,
    write_outline_review_report,
)
```

Add any missing imports reported by pytest without changing function behavior.

- [ ] **Step 4: Create `chapter_outline_actions.py`**

Create `src/ai_novelist/web/chapter_outline_actions.py`. Move these functions from `service.py` unchanged:

- `chapter_outline_review_report_paths`
- `latest_chapter_outline_review_run`
- `load_chapter_outline_review_report`
- `latest_chapter_outline_review_report`
- `render_chapter_outline_review_markdown`
- `chapter_outline_workspace_payload`
- `prepare_chapter_outline_volume_action`
- `generate_chapter_outline_volume`
- `revise_chapter_outline_volume`
- `lock_chapter_outline_volume`
- `review_chapter_outline`
- `apply_chapter_outline_review`

Use imports already present in `service.py` that these functions require, including:

```python
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from ai_novelist.adapters.base import AgentAdapter
from ai_novelist.graph_outline import advance_outline_stage_node, run_outline_stage_node
from ai_novelist.outline.chapter_outline_structure import chapter_outline_metadata_from_artifact
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore, LocalStoreError
from ai_novelist.web.chapter_service import chapter_outline_review_source_text
from ai_novelist.web.json_utils import parse_json_object
```

Add exact imports shown by test failures.

- [ ] **Step 5: Re-export moved outline functions from `service.py`**

In `src/ai_novelist/web/service.py`, import moved names from the new modules so existing tests and routes continue to work:

```python
from ai_novelist.web.outline_actions import (
    apply_outline_review,
    build_pending_revision_instruction,
    generate_outline_stage,
    load_outline_stage_payload,
    lock_outline_stage,
    normalize_pending_answers,
    outline_stage_pending_payload,
    review_outline,
    revise_outline_stage,
    save_outline_stage_content,
    strip_markdown_heading,
    submit_stage_pending_answers,
)
from ai_novelist.web.chapter_outline_actions import (
    apply_chapter_outline_review,
    chapter_outline_review_report_paths,
    chapter_outline_workspace_payload,
    generate_chapter_outline_volume,
    latest_chapter_outline_review_report,
    latest_chapter_outline_review_run,
    load_chapter_outline_review_report,
    lock_chapter_outline_volume,
    prepare_chapter_outline_volume_action,
    render_chapter_outline_review_markdown,
    review_chapter_outline,
    revise_chapter_outline_volume,
)
```

Remove duplicate moved function definitions from `service.py`.

- [ ] **Step 6: Run focused Web tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py -q
```

Expected result: all Web service and Web app tests pass.

- [ ] **Step 7: Update docs and commit**

Add to `docs/SESSION_SUMMARY.md`:

```markdown
### Phase 4b: Outline Web Action Split
- Files changed: outline/chapter outline Web action modules, service facade, Web tests, docs.
- Behavior changed: ordinary outline and chapter outline Web actions now live in focused modules while route behavior remains stable.
- Verification: `.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py -q`.
- Remaining risk: chapter list/batch/review/repair actions still need extraction.
- Next entry point: split chapter and review Web actions.
- Continuation note: resume at Task 8; keep `web/service.py` as a compatibility facade until all route call sites are stable.
```

Run:

```bash
git add src/ai_novelist/web/outline_actions.py src/ai_novelist/web/chapter_outline_actions.py src/ai_novelist/web/service.py tests/test_web_service.py docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "refactor: extract web outline actions"
```

Expected result: commit succeeds.

---

## Task 8: Chapter and Review Web Action Split

**Files:**
- Create: `src/ai_novelist/web/chapter_actions.py`
- Create: `src/ai_novelist/web/review_actions.py`
- Modify: `src/ai_novelist/web/service.py`
- Modify: `tests/test_web_service.py`
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Add export tests**

Add this test to `tests/test_web_service.py`:

```python
def test_chapter_and_review_action_modules_export_web_entry_points() -> None:
    from ai_novelist.web import chapter_actions, review_actions

    for name in [
        "generate_chapter_batch",
        "chapter_batch_workspace_payload",
        "list_chapters",
        "load_chapter_payload",
        "latest_chapter_path",
        "load_latest_chapter_text",
    ]:
        assert hasattr(chapter_actions, name)

    for name in [
        "review_all_chapters",
        "latest_global_review",
        "generate_repair_proposals",
        "apply_repair",
        "build_repair_suggestions",
        "normalize_global_review_output",
    ]:
        assert hasattr(review_actions, name)
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_chapter_and_review_action_modules_export_web_entry_points -q
```

Expected result: import failures for the new modules.

- [ ] **Step 3: Create `chapter_actions.py`**

Create `src/ai_novelist/web/chapter_actions.py`. Move these functions unchanged from `service.py`:

- `generate_chapter_batch`
- `latest_volume_batch_manifest`
- `extract_volume_chapter_numbers`
- `chapter_batch_workspace_payload`
- `list_chapters`
- `load_chapter_payload`
- `normalize_chapter_selector`
- `collect_latest_chapters`
- `chapter_payload`
- `chapter_source`
- `chapter_title`
- `latest_chapter_path`
- `load_latest_chapter_text`
- `next_draft_version`
- `fallback_repair_text`

Keep imports narrow:

```python
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from collections.abc import Iterable

from ai_novelist.graph_volume_write import build_volume_write_graph, parse_chapter_override
from ai_novelist.outline.chapter_outline_structure import chinese_number_to_int, current_volume_spec, volume_label
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore, LocalStoreError, summarize_text
from ai_novelist.web.chapter_outline_actions import chapter_outline_workspace_payload
from ai_novelist.workflow_payloads import set_chapter_batch_payload
```

- [ ] **Step 4: Create `review_actions.py`**

Create `src/ai_novelist/web/review_actions.py`. Move these functions unchanged from `service.py`:

- `review_all_chapters`
- `local_chapter_review_issues`
- `normalize_global_review_output`
- `merge_review_issues`
- `build_repair_suggestions`
- `normalize_repair_suggestions`
- `issue_identifier`
- `normalize_issue_chapter`
- `issue_recommendation`
- `group_repair_suggestions_by_chapter`
- `latest_global_review`
- `generate_repair_proposals`
- `apply_repair`
- `build_chapter_repair_prompt`
- `global_review_root`
- `write_global_review_report`
- `load_global_review`
- `proposed_repair_path`
- `safe_run_id`

Import chapter helpers from `chapter_actions`:

```python
from ai_novelist.web.chapter_actions import (
    fallback_repair_text,
    latest_chapter_path,
    load_latest_chapter_text,
    next_draft_version,
    collect_latest_chapters,
)
```

Use existing imports from `service.py` for `AgentAdapter`, `AgentAdapterError`, `LocalStore`, `LocalStoreError`, `parse_json_object`, `build_global_review_prompt`, `defaultdict`, `datetime`, `UTC`, `hashlib`, `json`, `re`, and `Any`.

- [ ] **Step 5: Re-export moved functions from `service.py`**

Import all moved chapter and review names into `service.py`. Remove duplicate definitions after tests pass.

- [ ] **Step 6: Run Web service tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_chapter_service.py tests/test_web_app.py -q
```

Expected result: all selected tests pass.

- [ ] **Step 7: Check service file size reduction**

Run:

```bash
wc -l src/ai_novelist/web/service.py src/ai_novelist/web/chapter_actions.py src/ai_novelist/web/review_actions.py
```

Expected result: `web/service.py` is substantially smaller than the baseline 1477 lines.

- [ ] **Step 8: Update docs and commit**

Add to `docs/SESSION_SUMMARY.md`:

```markdown
### Phase 4c: Chapter and Review Web Action Split
- Files changed: chapter/review Web action modules, service facade, Web tests, docs.
- Behavior changed: chapter batch/list/detail and review/repair logic now live in focused modules while public route behavior remains stable.
- Verification: `.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_chapter_service.py tests/test_web_app.py -q`; `wc -l` confirms `web/service.py` shrinkage.
- Remaining risk: FastAPI routes still call through the facade in places where direct module imports can be cleaned later.
- Next entry point: split outline graph helpers.
- Continuation note: resume at Task 9; keep route behavior unchanged and avoid deleting facade exports until final full tests pass.
```

Run:

```bash
git add src/ai_novelist/web/chapter_actions.py src/ai_novelist/web/review_actions.py src/ai_novelist/web/service.py tests/test_web_service.py docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "refactor: extract web chapter review actions"
```

Expected result: commit succeeds.

---

## Task 9: Outline Graph Review Lock and Routing Extraction

**Files:**
- Create: `src/ai_novelist/outline_graph/__init__.py`
- Create: `src/ai_novelist/outline_graph/review_lock.py`
- Create: `src/ai_novelist/outline_graph/routing.py`
- Modify: `src/ai_novelist/graph_outline.py`
- Modify: tests that import moved helpers
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Add import tests for extracted outline graph helpers**

Create `tests/test_outline_graph_modules.py`:

```python
from ai_novelist.outline_graph.review_lock import (
    extract_review_lock_issue_buckets,
    review_lock_blocking_issues,
    review_lock_issue_lines,
)
from ai_novelist.outline_graph.routing import (
    detect_stage_reference,
    is_lock_request,
    next_outline_stage,
)


def test_review_lock_helpers_parse_blocking_and_detail_issues() -> None:
    markdown = """
## 审稿锁定
BLOCKING:
- 人物动机缺失
DETAIL:
- 道具名称需统一
"""
    buckets = extract_review_lock_issue_buckets(markdown)

    assert review_lock_blocking_issues(buckets) == ["人物动机缺失"]
    assert "道具名称需统一" in review_lock_issue_lines(buckets)


def test_routing_helpers_detect_lock_and_stage_reference() -> None:
    assert is_lock_request("锁定世界观并进入下一阶段")
    assert detect_stage_reference("请修订人物阶段") == "characters"
    assert next_outline_stage("characters") == "story_flow"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_outline_graph_modules.py -q
```

Expected result: import failure for `ai_novelist.outline_graph`.

- [ ] **Step 3: Create package and move review lock helpers**

Create `src/ai_novelist/outline_graph/__init__.py`:

```python
"""Focused helpers for the outline graph runtime."""
```

Create `src/ai_novelist/outline_graph/review_lock.py` by moving these functions unchanged from `graph_outline.py`:

- `extract_review_lock_issue_buckets`
- `review_lock_blocking_issues`
- `review_lock_detail_issues`
- `review_lock_issue_lines`
- `review_lock_pending_question_text`
- `review_lock_blocking_message`
- `review_lock_issue_buckets_from_artifact`
- `filter_review_lock_issue_buckets_by_history`

Move required helper functions used only by these functions, including list normalization helpers, if imports would create cycles.

- [ ] **Step 4: Create routing module**

Create `src/ai_novelist/outline_graph/routing.py` by moving these functions unchanged from `graph_outline.py`:

- `negates_stage_advance`
- `should_defer_stage_confirmation_to_director`
- `should_run_outline_stage`
- `is_final_outline_view_request`
- `is_final_outline_save_request`
- `is_lock_request`
- `is_stage_confirmation`
- `is_short_stage_confirmation`
- `delegates_stage_decision`
- `answers_stage_pending_questions`
- `is_revision_request`
- `is_stage_view_request`
- `is_stage_switch_request`
- `detect_stage_reference`
- `stage_action_from_director`
- `stage_number`
- `next_outline_stage`
- `route_after_outline_director`
- `route_after_human_feedback`

Import `STAGE_LABELS` or stage constants from `ai_novelist.outline.stage_contracts` where needed.

- [ ] **Step 5: Import extracted helpers in `graph_outline.py`**

At the top of `src/ai_novelist/graph_outline.py`, add:

```python
from ai_novelist.outline_graph.review_lock import (
    extract_review_lock_issue_buckets,
    filter_review_lock_issue_buckets_by_history,
    review_lock_blocking_issues,
    review_lock_blocking_message,
    review_lock_detail_issues,
    review_lock_issue_buckets_from_artifact,
    review_lock_issue_lines,
    review_lock_pending_question_text,
)
from ai_novelist.outline_graph.routing import (
    answers_stage_pending_questions,
    delegates_stage_decision,
    detect_stage_reference,
    is_final_outline_save_request,
    is_final_outline_view_request,
    is_lock_request,
    is_revision_request,
    is_short_stage_confirmation,
    is_stage_confirmation,
    is_stage_switch_request,
    is_stage_view_request,
    negates_stage_advance,
    next_outline_stage,
    route_after_human_feedback,
    route_after_outline_director,
    should_defer_stage_confirmation_to_director,
    should_run_outline_stage,
    stage_action_from_director,
    stage_number,
)
```

Remove duplicate function definitions from `graph_outline.py` after imports are green.

- [ ] **Step 6: Run outline graph tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_outline_graph_modules.py tests/test_web_outline_service.py tests/test_web_service.py::test_outline_stage_list_hides_review_lock -q
```

Expected result: selected tests pass.

- [ ] **Step 7: Update docs and commit**

Add to `docs/SESSION_SUMMARY.md`:

```markdown
### Phase 5a: Outline Graph Routing and Review Lock Split
- Files changed: `src/ai_novelist/outline_graph/routing.py`, `src/ai_novelist/outline_graph/review_lock.py`, `graph_outline.py`, tests, docs.
- Behavior changed: routing and review-lock helpers moved out of the main outline graph without intended semantic changes.
- Verification: `.venv/bin/python -m pytest tests/test_outline_graph_modules.py tests/test_web_outline_service.py tests/test_web_service.py::test_outline_stage_list_hides_review_lock -q`.
- Remaining risk: prompt builders and structure repair helpers still remain in `graph_outline.py`.
- Next entry point: extract prompt and repair helpers.
- Continuation note: resume at Task 10; keep helper function names exported because tests and `graph_outline.py` import them directly.
```

Run:

```bash
git add src/ai_novelist/outline_graph/__init__.py src/ai_novelist/outline_graph/review_lock.py src/ai_novelist/outline_graph/routing.py src/ai_novelist/graph_outline.py tests/test_outline_graph_modules.py docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "refactor: split outline routing helpers"
```

Expected result: commit succeeds.

---

## Task 10: Outline Graph Prompt and Repair Extraction

**Files:**
- Create: `src/ai_novelist/outline_graph/prompts.py`
- Create: `src/ai_novelist/outline_graph/repair.py`
- Create: `src/ai_novelist/outline_graph/artifact_io.py`
- Modify: `src/ai_novelist/graph_outline.py`
- Modify: `tests/test_outline_graph_modules.py`
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Extend outline graph module tests**

Add to `tests/test_outline_graph_modules.py`:

```python
from ai_novelist.outline_graph.prompts import outline_stage_boundary_prompt, stage_continuity_requirement
from ai_novelist.outline_graph.artifact_io import summarize_stage_text


def test_prompt_helpers_return_stage_specific_rules() -> None:
    assert "世界观" in outline_stage_boundary_prompt("worldbuilding")
    assert "前序阶段" in stage_continuity_requirement("characters")


def test_artifact_io_summary_compacts_markdown() -> None:
    text = "# 标题\n\n" + "内容" * 500
    summary = summarize_stage_text(text, max_chars=30)
    assert len(summary) <= 33
    assert "\n" not in summary
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_outline_graph_modules.py::test_prompt_helpers_return_stage_specific_rules tests/test_outline_graph_modules.py::test_artifact_io_summary_compacts_markdown -q
```

Expected result: import failures for `prompts` and `artifact_io`.

- [ ] **Step 3: Create `prompts.py`**

Move these helpers unchanged from `graph_outline.py` into `src/ai_novelist/outline_graph/prompts.py`:

- `chapter_outline_framework_prompt`
- `worldbuilding_framework_prompt`
- `characters_framework_prompt`
- `story_flow_framework_prompt`
- `volume_outline_framework_prompt`
- `chapter_outline_forced_full_generation`
- `chapter_outline_internal_generation_request`
- `outline_stage_user_request_for_prompt`
- `build_outline_stage_role_prompt`
- `build_outline_stage_synthesizer_prompt`
- `outline_stage_boundary_prompt`
- `worldbuilding_overfine_terms_guard`
- `characters_relationship_guard`
- `outline_stage_synthesizer_output_rule`
- `role_focus_instruction`
- `stage_continuity_requirement`
- `locked_stage_summary`

Import framework constants from their current modules and import `NovelState`, `LocalStore`, and prompt loader helpers as needed.

- [ ] **Step 4: Create `repair.py`**

Move these helpers unchanged from `graph_outline.py` into `src/ai_novelist/outline_graph/repair.py`:

- `ensure_worldbuilding_outline_structure`
- `ensure_characters_outline_structure`
- `ensure_story_flow_outline_structure`
- `ensure_volume_outline_structure`
- `ensure_chapter_outline_structure`
- `chapter_outline_has_next_volume`
- `confirm_current_chapter_outline_volume`
- `sanitize_direction_stage_output`
- `replace_pending_questions_section`

Keep imports explicit. Avoid importing `graph_outline.py` from `repair.py`.

- [ ] **Step 5: Create `artifact_io.py`**

Move these helpers unchanged from `graph_outline.py` into `src/ai_novelist/outline_graph/artifact_io.py`:

- `summarize_worldbuilding_outline`
- `extract_worldbuilding_memory`
- `split_worldbuilding_sections`
- `worldbuilding_bullets`
- `first_worldbuilding_bullet`
- `summarize_outline_stage_for_artifact`
- `extract_outline_stage_memory_for_artifact`
- `summarize_stage_text`
- `extract_stage_memory`
- `stage_memory_context`
- `stage_full_text`
- `previous_stage_context`
- `current_stage_context`
- `format_stage_markdown`
- `build_final_outline_text`
- `finalize_locked_outline`

- [ ] **Step 6: Import extracted helpers into `graph_outline.py`**

Add imports from the three new modules. Remove duplicate definitions only after focused tests pass.

- [ ] **Step 7: Run focused outline tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_outline_graph_modules.py tests/test_web_outline_service.py tests/test_web_service.py -q
```

Expected result: selected tests pass.

- [ ] **Step 8: Check outline graph file size**

Run:

```bash
wc -l src/ai_novelist/graph_outline.py src/ai_novelist/outline_graph/prompts.py src/ai_novelist/outline_graph/repair.py src/ai_novelist/outline_graph/artifact_io.py
```

Expected result: `graph_outline.py` is materially smaller than the baseline 2860 lines.

- [ ] **Step 9: Update docs and commit**

Add to `docs/SESSION_SUMMARY.md`:

```markdown
### Phase 5b: Outline Graph Prompt and Repair Split
- Files changed: prompt, repair, artifact IO helper modules, `graph_outline.py`, tests, docs.
- Behavior changed: prompt building, structure repair, and artifact formatting helpers moved out of `graph_outline.py` with route and graph entry points preserved.
- Verification: `.venv/bin/python -m pytest tests/test_outline_graph_modules.py tests/test_web_outline_service.py tests/test_web_service.py -q`; `wc -l` confirms `graph_outline.py` shrinkage.
- Remaining risk: additional graph-node extraction can continue later, but this phase removes the largest helper clusters.
- Next entry point: frontend structural split.
- Continuation note: resume at Task 11; do not move graph node functions until frontend and full verification are stable.
```

Run:

```bash
git add src/ai_novelist/outline_graph/prompts.py src/ai_novelist/outline_graph/repair.py src/ai_novelist/outline_graph/artifact_io.py src/ai_novelist/graph_outline.py tests/test_outline_graph_modules.py docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "refactor: split outline prompt repair helpers"
```

Expected result: commit succeeds.

---

## Task 11: Frontend Utility and Component Split

**Files:**
- Create: `web/frontend/src/progress.ts`
- Create: `web/frontend/src/workspaces/review.tsx`
- Create: `web/frontend/src/workspaces/chapters.tsx`
- Create: `web/frontend/src/workspaces/outline.tsx`
- Create: `web/frontend/src/workspaces/chapterOutline.tsx`
- Create: `web/frontend/src/workspaces/project.tsx`
- Modify: `web/frontend/src/main.tsx`
- Modify: `tests/test_frontend_review_tabs_structure.py`
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Add frontend split structure tests**

Add to `tests/test_frontend_review_tabs_structure.py`:

```python
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
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py::test_frontend_workspace_modules_exist_after_split tests/test_frontend_review_tabs_structure.py::test_frontend_main_is_smaller_after_workspace_split -q
```

Expected result: module existence and size assertions fail.

- [ ] **Step 3: Extract progress helpers**

Create `web/frontend/src/progress.ts`:

```ts
import type { ProgressItem } from './types';

export const maxLogItems = 10;

export function progressItemKey(item: ProgressItem) {
  if (typeof item === 'string') return item;
  return item.key || item.label;
}

export function upsertProgressItem(items: ProgressItem[], message: ProgressItem) {
  const key = progressItemKey(message);
  if (!key) return [...items, message].slice(-maxLogItems);
  const next = items.filter((item) => progressItemKey(item) !== key);
  return [...next, message].slice(-maxLogItems);
}
```

Remove the duplicate definitions from `main.tsx` and import:

```ts
import { upsertProgressItem } from './progress';
```

- [ ] **Step 4: Extract review components**

Create `web/frontend/src/workspaces/review.tsx` with moved component definitions from `main.tsx`:

- `OutlineReviewWorkspace`
- `OutlineRepairDecisionBoard`
- `OutlineRepairSuggestionBoard`
- `IssueBlock`
- `ReviewReport`
- `RepairSuggestionBoard`

Use the same props types currently declared inline. Import React only if the build requires it:

```tsx
import { Check, ListChecks, X } from 'lucide-react';
import type {
  OutlineRepairDecision,
  OutlineRepairDecisionValue,
  OutlineReview,
  OutlineReviewSuggestion,
  ReviewReportData,
  ReviewSuggestion,
} from '../types';
```

Export each moved component:

```tsx
export function OutlineReviewWorkspace(...) {
  ...
}
```

Import them in `main.tsx`:

```tsx
import { OutlineReviewWorkspace, OutlineRepairSuggestionBoard, RepairSuggestionBoard, ReviewReport } from './workspaces/review';
```

- [ ] **Step 5: Extract low-risk workspace components**

Create thin component modules for project/sidebar-independent UI after review extraction:

- `project.tsx`: move onboarding panel into `OnboardingWorkspace`.
- `outline.tsx`: move `StageActionBar` and `PendingQuestionPanel`.
- `chapterOutline.tsx`: move the chapter outline review/volume render branches after `StageActionBar` is imported.
- `chapters.tsx`: move chapter list detail and batch summary helpers after `ReviewReport` and `RepairSuggestionBoard` imports are stable.

For each moved component, export a function with explicit props. Keep behavior unchanged and leave API action handlers in `main.tsx` until build is green.

- [ ] **Step 6: Run frontend tests and build repeatedly during extraction**

After each module extraction, run:

```bash
npm --prefix web/frontend run build
```

Expected result: build passes before moving to the next component.

After all extraction steps, run:

```bash
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py -q
npm --prefix web/frontend run build
```

Expected result: all frontend source tests pass and build passes.

- [ ] **Step 7: Update docs and commit**

Add to `docs/SESSION_SUMMARY.md`:

```markdown
### Phase 6: Frontend Workspace Split
- Files changed: frontend progress utility, workspace components, `main.tsx`, frontend structure tests, docs.
- Behavior changed: frontend UI is split into focused modules while existing tabs, actions, progress log, and review workspaces remain compatible.
- Verification: `.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py -q`; `npm --prefix web/frontend run build`.
- Remaining risk: action handlers still live in `main.tsx`; a future phase can split hooks once component boundaries settle.
- Next entry point: final verification and cleanup.
- Continuation note: resume at Task 12; frontend split is accepted only when `main.tsx` is below 900 lines and build passes.
```

Run:

```bash
git add web/frontend/src/main.tsx web/frontend/src/progress.ts web/frontend/src/workspaces tests/test_frontend_review_tabs_structure.py docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "refactor: split frontend workspace components"
```

Expected result: commit succeeds.

---

## Task 12: Final Verification, Residual Scan, and Closeout

**Files:**
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`
- Modify only cleanup files identified by scans in this task.

- [ ] **Step 1: Run full Python verification**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected result: full suite passes.

- [ ] **Step 2: Run frontend build verification**

Run:

```bash
npm --prefix web/frontend run build
```

Expected result: build passes. The Vite CJS Node API deprecation warning may appear.

- [ ] **Step 3: Run residual architecture scans**

Run:

```bash
rg -n "T[O]DO|T[B]D|P[L]ACEHOLDER|pass$|NotImplemented|director_task_args\\[|director_task_args\\.get|localStorage|disabled=\\{\\(chapterBatchWorkspace\\?\\.remaining_chapters" src web tests docs README.md
```

Expected result:

- No placeholder lines from newly written plan/code/docs.
- Remaining `director_task_args` hits are reviewed and documented as compatibility or queued follow-up.
- No `localStorage` reintroduced.
- No old chapter batch disabled expression remains.

- [ ] **Step 4: Check large-file progress**

Run:

```bash
wc -l src/ai_novelist/graph_outline.py src/ai_novelist/web/service.py web/frontend/src/main.tsx src/ai_novelist/context_builder.py
```

Expected result:

- `graph_outline.py` is smaller than 2860 lines.
- `web/service.py` is smaller than 1477 lines.
- `main.tsx` is smaller than 1294 lines and target below 900 lines.
- `context_builder.py` may grow modestly because it owns structured context source behavior.

- [ ] **Step 5: Inspect Git status**

Run:

```bash
git status --short --branch
```

Expected result: only intended docs cleanup changes are present, or no changes are present if all prior tasks committed.

- [ ] **Step 6: Update final docs**

In `docs/IMPLEMENTATION_PLAN.md`, add a final architecture note:

```markdown
- 2026-05-29: Completed the architecture/Web/context remediation batch. Web actions have stronger running/error guards, context profiles record source manifests and deduplicate sources, Web services and outline graph helpers are split behind compatibility facades, and frontend workspace components are split from the entry file.
```

In `docs/SESSION_SUMMARY.md`, add:

```markdown
### Final Verification: Architecture Web Context Remediation
- Files changed: Web frontend, Web services, context builder, workflow payload helpers, outline graph helpers, tests, docs.
- Behavior changed: Web operations have stronger guards and error reporting; context is traceable and deduplicated; large modules are split into focused helper modules while public Web routes remain stable.
- Verification: `.venv/bin/python -m pytest -q`; `npm --prefix web/frontend run build`; residual `rg` architecture scan; file-size `wc -l` scan.
- Remaining risk: any retained `director_task_args` access is compatibility debt and should be handled with targeted payload helpers in future work.
- Next recommended work: add browser-level interaction tests if a real UI runtime issue appears after these source and service-level guards.
- Continuation note: this remediation batch is complete when full pytest, frontend build, and residual scans match the recorded outputs.
```

- [ ] **Step 7: Commit final docs**

Run:

```bash
git add docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "docs: close architecture web context remediation"
```

Expected result: commit succeeds if docs changed. If no docs changed because the final summary was already committed in a previous task, run `git status --short --branch` and record the clean status in the final response.

- [ ] **Step 8: Final status**

Run:

```bash
git status --short --branch
git log --oneline -12
```

Expected result: working tree clean; recent log shows the phase commits from this plan.

## Plan Self-Review Checklist

- Spec coverage:
  - Web operation logic: Tasks 1 and 2.
  - Context precision and non-redundancy: Tasks 3 and 4.
  - `director_task_args` containment: Task 5.
  - Web service split: Tasks 6, 7, and 8.
  - Outline graph split: Tasks 9 and 10.
  - Frontend split: Task 11.
  - Phase summary, docs, commit, and context compression: every task exit step plus Task 12.
- Placeholder scan:
  - This plan intentionally avoids unresolved placeholder sections and vague implementation instructions.
- Type consistency:
  - `SectionRecord`, `ContextSource`, `build_context_bundle`, `build_context_manifest`, `set_chapter_batch_payload`, and `chapter_batch_payload` names are introduced before use.
  - Frontend imports are introduced after the files that export them.
  - Web service facade remains available while modules are extracted.
