# Web UI Onboarding and Outline Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Web project onboarding, improve long instruction editing, and make outline stage performance diagnosable and less wasteful.

**Architecture:** Keep changes Web-first. Add small service functions and API routes for onboarding and diagnostics, reuse existing outline stage generation, and keep CLI/chat behavior stable unless shared helper changes are clearly safe. Frontend detects onboarding from project state and renders either the onboarding view or the existing workspace.

**Tech Stack:** Python 3.11+, FastAPI service layer, pytest, React + TypeScript + Vite, local JSON/Markdown project storage.

---

## File Map

- Modify `src/ai_novelist/web/service.py`: add onboarding helpers and outline diagnostic writer.
- Modify `src/ai_novelist/web/app.py`: expose onboarding state update endpoint and state read support used by the frontend.
- Modify `src/ai_novelist/storage/local_store.py`: add `outline_stage_context_log_path()` helper.
- Modify `src/ai_novelist/graph_outline.py`: add diagnostics hooks around outline stage generation and trim duplicated forward context only where supported by tests.
- Modify `web/frontend/src/main.tsx`: load project state, render onboarding view, submit idea, replace instruction inputs with textareas, retain content after actions.
- Modify `web/frontend/src/styles.css`: style onboarding and multi-line instruction textareas.
- Modify `tests/test_web_service.py`: cover onboarding persistence and diagnostics.
- Modify `tests/test_web_app.py`: cover the new idea endpoint wiring through `make_app`.
- Modify `docs/IMPLEMENTATION_PLAN.md` and `docs/SESSION_SUMMARY.md`: required by repository guidelines for every code change.

---

### Task 1: Backend Onboarding Service

**Files:**
- Modify: `src/ai_novelist/web/service.py`
- Modify: `src/ai_novelist/web/app.py`
- Test: `tests/test_web_service.py`
- Test: `tests/test_web_app.py`

- [ ] **Step 1: Write failing tests for onboarding state**

Add tests to `tests/test_web_service.py` near existing project/state service tests:

```python
def test_project_needs_onboarding_until_idea_or_outline_exists(tmp_path):
    store = LocalStore(tmp_path)
    state = service.create_project(store, "Onboard Demo", "onboard-demo")

    assert service.project_needs_onboarding(state) is True

    state.idea = "一个月球城市失忆工程师追查自己的小说手稿"
    store.save_state(state)

    assert service.project_needs_onboarding(store.load_state("onboard-demo")) is False


def test_save_project_idea_prepares_direction_without_model_call(tmp_path):
    store = LocalStore(tmp_path)
    service.create_project(store, "Idea Demo", "idea-demo")

    state = service.save_project_idea(store, "idea-demo", "一个赛博唐代的女仵作悬疑故事")

    assert state.idea == "一个赛博唐代的女仵作悬疑故事"
    assert state.outline_stage == "direction"
    assert state.outline_stage_status == "collecting"
    assert state.current_stage == "direction"
    assert state.active_workflow == "outline"
    assert state.user_request == "一个赛博唐代的女仵作悬疑故事"
    assert state.revision_instruction == "一个赛博唐代的女仵作悬疑故事"
    assert state.director_action == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_project_needs_onboarding_until_idea_or_outline_exists tests/test_web_service.py::test_save_project_idea_prepares_direction_without_model_call -q
```

Expected: FAIL because `project_needs_onboarding` and `save_project_idea` do not exist.

- [ ] **Step 3: Implement onboarding helpers**

Add to `src/ai_novelist/web/service.py` after `create_project()`:

```python
def project_needs_onboarding(state: NovelState) -> bool:
    if state.idea.strip():
        return False
    if state.outline.strip() or state.worldbuilding.strip() or state.chapter_plan.strip():
        return False
    for artifact in state.outline_stage_artifacts.values():
        if isinstance(artifact, dict) and str(artifact.get("summary") or artifact.get("path") or "").strip():
            return False
    return True


def save_project_idea(store: LocalStore, project_id: str, idea: str) -> NovelState:
    text = idea.strip()
    if not text:
        raise LocalStoreError("Novel idea cannot be empty")
    state = store.load_state(project_id)
    state.idea = text
    state.outline_stage = "direction"
    state.outline_stage_status = "collecting"
    state.current_stage = "direction"
    state.active_workflow = "outline"
    state.user_request = text
    state.revision_instruction = text
    state.director_action = ""
    state.director_message = ""
    store.save_state(state)
    return state
```

- [ ] **Step 4: Add API route**

In `src/ai_novelist/web/app.py`, add route after `project_state()`:

```python
    @app.post("/api/projects/{project_id}/idea")
    def save_project_idea(project_id: str, payload: dict[str, Any]):
        try:
            return service.save_project_idea(store, project_id, str(payload.get("idea") or "")).to_dict()
        except LocalStoreError as exc:
            raise as_http_error(exc)
```

- [ ] **Step 5: Add API route test**

Add to `tests/test_web_app.py`:

```python
def test_project_idea_endpoint_saves_onboarding_idea(tmp_path):
    try:
        from fastapi.testclient import TestClient
    except ModuleNotFoundError:
        pytest.skip("FastAPI test client is not installed")

    settings = Settings(projects_dir=tmp_path)
    client = TestClient(web_app.make_app(settings, mock=True))

    create_response = client.post("/api/projects", json={"title": "Idea Web", "project_id": "idea-web"})
    assert create_response.status_code == 200

    response = client.post("/api/projects/idea-web/idea", json={"idea": "月球城市失忆工程师"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["idea"] == "月球城市失忆工程师"
    assert payload["outline_stage"] == "direction"
    assert payload["active_workflow"] == "outline"
```

Add `import pytest` at the top of `tests/test_web_app.py`.

- [ ] **Step 6: Run focused backend tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_project_needs_onboarding_until_idea_or_outline_exists tests/test_web_service.py::test_save_project_idea_prepares_direction_without_model_call tests/test_web_app.py::test_project_idea_endpoint_saves_onboarding_idea -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add src/ai_novelist/web/service.py src/ai_novelist/web/app.py tests/test_web_service.py tests/test_web_app.py
git commit -m "feat: add web project onboarding service"
```

---

### Task 2: Outline Stage Diagnostic Log

**Files:**
- Modify: `src/ai_novelist/storage/local_store.py`
- Modify: `src/ai_novelist/web/service.py`
- Modify: `src/ai_novelist/graph_outline.py`
- Test: `tests/test_web_service.py`

- [ ] **Step 1: Write failing diagnostic service tests**

Add to `tests/test_web_service.py`:

```python
def test_write_outline_stage_diagnostic_appends_jsonl(tmp_path):
    store = LocalStore(tmp_path)
    service.create_project(store, "Diagnostic Demo", "diag-demo")

    service.write_outline_stage_diagnostic(
        store,
        "diag-demo",
        {
            "stage": "direction",
            "mode": "full",
            "instruction_chars": 12,
            "role_prompt_count": 2,
            "status": "ok",
        },
    )

    path = store.outline_stage_context_log_path("diag-demo")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["project_id"] == "diag-demo"
    assert rows[0]["stage"] == "direction"
    assert rows[0]["mode"] == "full"
    assert rows[0]["status"] == "ok"
    assert "created_at" in rows[0]
```

Ensure `json` is imported at the top of the test file if it is not already.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_write_outline_stage_diagnostic_appends_jsonl -q
```

Expected: FAIL because `outline_stage_context_log_path` and/or `write_outline_stage_diagnostic` do not exist.

- [ ] **Step 3: Add store path helper**

Add to `src/ai_novelist/storage/local_store.py` near other debug/path helpers:

```python
    def outline_stage_context_log_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "debug" / "outline_stage_context.jsonl"
```

- [ ] **Step 4: Add diagnostic writer**

Add to `src/ai_novelist/web/service.py`:

```python
def write_outline_stage_diagnostic(store: LocalStore, project_id: str, payload: dict[str, Any]) -> None:
    path = store.outline_stage_context_log_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "project_id": project_id,
        **payload,
    }
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
```

- [ ] **Step 5: Instrument Web outline generation**

In `src/ai_novelist/web/service.py`, update `generate_outline_stage()` to measure total elapsed and append a fallback diagnostic after `run_outline_stage_node()` returns:

```python
    started_at = datetime.now(UTC)
    result = run_outline_stage_node(state.to_dict(), adapter, store, progress or (lambda _stage, _message: None))
    result_state = NovelState.from_dict(result)
    elapsed_ms = int((datetime.now(UTC) - started_at).total_seconds() * 1000)
    diagnostics = dict(result_state.director_task_args.get("outline_stage_diagnostics") or {})
    diagnostics.setdefault("stage", stage)
    diagnostics.setdefault("mode", "light_revision" if diagnostics.get("light_revision") else "full")
    diagnostics.setdefault("instruction_chars", len(instruction.strip()))
    diagnostics.setdefault("elapsed_ms", elapsed_ms)
    diagnostics.setdefault("status", "error" if result_state.error else "ok")
    diagnostics.setdefault("error", result_state.error)
    write_outline_stage_diagnostic(store, project_id, diagnostics)
    return result_state
```

Remove the old direct `return NovelState.from_dict(result)` line.

- [ ] **Step 6: Add graph diagnostics payload**

In `src/ai_novelist/graph_outline.py`, inside `run_outline_stage_node()`:

After `author_craft = load_outline_stage_craft_brief(state, store)`, initialize:

```python
    diagnostics: dict[str, Any] = {
        "stage": stage,
        "mode": "full",
        "instruction_chars": len(state.user_request.strip()),
        "author_craft_chars": len(author_craft),
        "previous_stage_context_chars": len(previous_stage_context(state, stage)),
        "current_stage_context_chars": len(current_stage_context(state, stage)),
        "structure_repair_triggered": False,
    }
```

After `role_jobs` is built, add:

```python
    diagnostics["role_prompt_count"] = len(role_jobs)
    diagnostics["role_prompt_chars"] = [len(job.prompt) for job in role_jobs]
```

After `synthesizer_prompt` is built, add:

```python
    diagnostics["synthesizer_prompt_chars"] = len(synthesizer_prompt)
```

After synthesis is available and before saving state, add:

```python
    diagnostics["output_chars"] = len(synthesis)
    state.director_task_args["outline_stage_diagnostics"] = diagnostics
```

In `revise_outline_stage_from_existing()`, set equivalent minimal diagnostics before return:

```python
    state.director_task_args["outline_stage_diagnostics"] = {
        "stage": stage,
        "mode": "light_revision",
        "instruction_chars": len(state.user_request.strip()),
        "author_craft_chars": len(author_craft),
        "current_stage_context_chars": len(current_stage_markdown_for_revision(state, store, stage, artifact)),
        "role_prompt_count": 0,
        "role_prompt_chars": [],
        "synthesizer_prompt_chars": len(prompt),
        "output_chars": len(revised),
        "structure_repair_triggered": False,
    }
```

Place this assignment after `state.director_action = "run_outline_stage"` and before `store.save_state(state)`. The current local variable names in this function are `prompt`, `current_markdown`, `revised`, and `artifact`.

- [ ] **Step 7: Run diagnostic tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_write_outline_stage_diagnostic_appends_jsonl tests/test_web_service.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```bash
git add src/ai_novelist/storage/local_store.py src/ai_novelist/web/service.py src/ai_novelist/graph_outline.py tests/test_web_service.py
git commit -m "feat: log web outline stage diagnostics"
```

---

### Task 3: Frontend Onboarding and Textareas

**Files:**
- Modify: `web/frontend/src/main.tsx`
- Modify: `web/frontend/src/styles.css`
- Test/Verify: `npm --prefix web/frontend run build`

- [ ] **Step 1: Add project state type and state loading**

In `web/frontend/src/main.tsx`, add a state type near existing types:

```tsx
type ProjectState = {
  project_id: string;
  title: string;
  idea: string;
  outline: string;
  worldbuilding: string;
  chapter_plan: string;
  outline_stage_artifacts: Record<string, unknown>;
};
```

Add React state near existing project state:

```tsx
  const [projectState, setProjectState] = useState<ProjectState | null>(null);
  const [onboardingIdea, setOnboardingIdea] = useState('');
```

Add loader:

```tsx
  async function loadProjectState(id = projectId) {
    if (!id) {
      setProjectState(null);
      return;
    }
    const state = await api<ProjectState>(`/api/projects/${id}/state`);
    setProjectState(state);
    setOnboardingIdea(state.idea || '');
  }
```

Update the project effect so project changes load state as well as stages:

```tsx
  useEffect(() => {
    if (!projectId) return;
    loadProjectState(projectId).catch(showError);
    refreshStages().catch(showError);
    refreshChapters().catch(showError);
    loadLatestReview().catch(() => {});
    loadLatestOutlineReview().catch(() => {});
  }, [projectId]);
```

If this effect already exists with similar calls, merge `loadProjectState(projectId).catch(showError);` into it instead of duplicating the effect.

- [ ] **Step 2: Add onboarding detection and submit handler**

Add helper inside `App()` before `return`:

```tsx
  const hasOutlineArtifacts = Boolean(projectState && Object.keys(projectState.outline_stage_artifacts || {}).length > 0);
  const needsOnboarding = Boolean(projectState && !projectState.idea?.trim() && !projectState.outline?.trim() && !projectState.worldbuilding?.trim() && !projectState.chapter_plan?.trim() && !hasOutlineArtifacts);

  async function submitOnboardingIdea() {
    if (!projectId || !onboardingIdea.trim()) return;
    const state = await api<ProjectState>(`/api/projects/${projectId}/idea`, {
      method: 'POST',
      body: JSON.stringify({ idea: onboardingIdea }),
    });
    setProjectState(state);
    setInstruction(onboardingIdea);
    setTopSection('outline');
    setOutlineView('edit');
    setActiveStage('direction');
    await refreshStages();
    pushLog('已保存小说创意，请点击生成/修订开始方向定位');
  }
```

- [ ] **Step 3: Render onboarding view**

Before the normal `topSection === 'outline' ? ...` workspace branch, render onboarding when needed:

```tsx
      {needsOnboarding ? (
        <section className="workspace onboarding-workspace">
          <div className="onboarding-panel">
            <header>
              <h1>先确定这本小说要写什么</h1>
              <p>写下题材、主角、核心冲突、爽点、基调或限制。保存后再进入方向定位。</p>
            </header>
            <textarea
              className="instruction instruction-multiline onboarding-input"
              value={onboardingIdea}
              onChange={(event) => setOnboardingIdea(event.target.value)}
              rows={8}
              placeholder="例如：一个失忆工程师在月球城市追查自己的小说手稿，逐步发现自己参与过城市意识实验。"
            />
            <div className="toolbar compact-toolbar">
              <button onClick={submitOnboardingIdea} disabled={!onboardingIdea.trim()}>
                <Save size={16} />开始构思
              </button>
            </div>
          </div>
        </section>
      ) : topSection === 'outline' ? (
```

Keep the existing `) : (` chapter workspace branch aligned with this new conditional.

- [ ] **Step 4: Replace instruction inputs with textareas**

Replace the outline edit input:

```tsx
              <textarea
                className="instruction instruction-multiline"
                value={instruction}
                onChange={(event) => setInstruction(event.target.value)}
                rows={5}
                placeholder="当前大纲阶段生成/修订说明"
              />
```

Replace the outline review input inside `OutlineReviewWorkspace`:

```tsx
      <textarea
        className="instruction instruction-multiline"
        value={instruction}
        onChange={(event) => onInstructionChange(event.target.value)}
        rows={5}
        placeholder="可选：本次审查关注点"
      />
```

Do not add any code that clears `instruction` after `runStage()` or `runOutlineReview()`.

- [ ] **Step 5: Add styles**

In `web/frontend/src/styles.css`, replace or extend `.instruction`:

```css
.instruction { width: 100%; padding: 10px; }
.instruction-multiline { min-height: 120px; max-height: 220px; resize: vertical; overflow-y: auto; line-height: 1.45; }
.onboarding-workspace { align-items: stretch; justify-content: flex-start; }
.onboarding-panel { display: flex; flex-direction: column; gap: 12px; width: min(860px, 100%); }
.onboarding-panel header h1 { margin: 0 0 6px; font-size: 24px; }
.onboarding-panel header p { margin: 0; color: #52616f; line-height: 1.5; }
.onboarding-input { min-height: 180px; }
.compact-toolbar { justify-content: flex-start; border-bottom: 0; padding: 0; }
```

- [ ] **Step 6: Run frontend build**

Run:

```bash
npm --prefix web/frontend run build
```

Expected: TypeScript and Vite build complete successfully.

- [ ] **Step 7: Commit**

Run:

```bash
git add web/frontend/src/main.tsx web/frontend/src/styles.css
git commit -m "feat: add web onboarding and multiline instructions"
```

---

### Task 4: Forward Context and Output Shape Cleanup

**Files:**
- Modify: `src/ai_novelist/graph_outline.py`
- Test: `tests/test_outline_collaboration.py`

- [ ] **Step 1: Add focused tests for duplicate context avoidance**

Add a test in the outline stage test file that already covers prompt construction. The assertion should verify that previous full stage text is not repeated when stage memory is present.

In `tests/test_outline_collaboration.py`, add `previous_stage_context` to the existing `from ai_novelist.graph_outline import ...` import list, then add:

```python
def test_previous_stage_context_prefers_stage_memory_over_full_text(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Context Demo", "context-demo")
    repeated = "这是一段很长的世界观正文" * 200
    state.outline_stage_artifacts["worldbuilding"] = {
        "stage": "worldbuilding",
        "status": "locked",
        "summary": "世界观摘要",
        "stage_memory": ["世界观记忆一", "世界观记忆二"],
        "path": "outline/worldbuilding.md",
        "synthesis": repeated,
    }
    store.save_state(state)

    context = previous_stage_context(state, "characters", max_chars_per_stage=1800)

    assert "世界观记忆一" in context
    assert "世界观摘要" in context
    assert repeated[:80] not in context
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_outline_collaboration.py::test_previous_stage_context_prefers_stage_memory_over_full_text -q
```

Expected: FAIL with `AssertionError` when full `synthesis` appears in the context. If current behavior already passes, keep the test as regression coverage and continue.

- [ ] **Step 3: Implement context preference**

In `src/ai_novelist/graph_outline.py`, update `previous_stage_context()` so for each previous artifact it builds context in this order:

```python
memory = stage_memory_context(artifact, max_chars_per_stage)
summary = str(artifact.get("summary") or "").strip()
if memory or summary:
    parts = [f"## {STAGE_LABELS.get(previous_stage, previous_stage)}"]
    if summary:
        parts.append(f"摘要：{summary}")
    if memory:
        parts.append(memory)
    sections.append("\n".join(parts).strip())
    continue
```

Only fall back to `stage_full_text(state, store, previous_stage)` when both summary and memory are empty.

- [ ] **Step 4: Tighten output rules without removing required structure**

In `outline_stage_synthesizer_output_rule()` or the stage boundary prompt helper, add Web-safe wording that applies generally:

```python
        "输出应是可编辑决策稿：保留本阶段要求的标题和条目，但每个条目优先写具体设定、冲突、约束和待确认点；避免泛泛解释、重复前提和长篇说明文。"
```

For worldbuilding and characters, preserve existing framework-specific required headings. Do not delete the structure repair calls.

- [ ] **Step 5: Run outline tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_outline_collaboration.py tests/test_outline_stage_controls.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/ai_novelist/graph_outline.py tests/test_outline_collaboration.py tests/test_outline_stage_controls.py
git commit -m "perf: trim redundant outline stage context"
```

---

### Task 5: Documentation and Verification

**Files:**
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Update implementation documentation**

In `docs/IMPLEMENTATION_PLAN.md`, add a short subsection under the Web UI section:

```markdown
### Web onboarding and outline diagnostics

Web project creation now separates project naming from story onboarding. A new project without `idea` or outline artifacts shows an onboarding workspace that saves the novel idea into state and prepares the direction stage without calling the model.

Web outline stage generation appends lightweight context diagnostics to `projects/<project>/debug/outline_stage_context.jsonl`, recording prompt/context sizes, output size, status, and elapsed time. This complements `agent_runs.jsonl`: agent runs track model calls, while outline diagnostics track context assembly and stage-level cost.

Instruction fields for outline generation and outline review are multi-line scrollable textareas and retain content after generation/review actions complete.
```

- [ ] **Step 2: Update session summary**

In `docs/SESSION_SUMMARY.md`, add a dated note:

```markdown
### Web onboarding and outline performance diagnostics

Added Web onboarding for new projects, multi-line retained instruction fields, and lightweight outline stage context diagnostics. The performance work focuses on checking actual forward inputs and generated artifacts before trimming prompts; previous stage context now prefers summaries/stage memory over full prior-stage Markdown when sufficient.

Validation:

- `.venv/bin/python -m pytest tests/test_web_service.py tests/test_outline_collaboration.py tests/test_outline_stage_controls.py`
- `npm --prefix web/frontend run build`
```

- [ ] **Step 3: Run focused backend tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py tests/test_outline_collaboration.py tests/test_outline_stage_controls.py -q
```

Expected: PASS.

- [ ] **Step 4: Run frontend build**

Run:

```bash
npm --prefix web/frontend run build
```

Expected: PASS.

- [ ] **Step 5: Run full test suite if shared graph code changed**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS. If it fails, fix regressions before committing docs.

- [ ] **Step 6: Commit docs and final verification metadata**

Run:

```bash
git add docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "docs: update web onboarding performance notes"
```

---

## Plan Self-Review

Spec coverage:

- New-project onboarding is covered by Tasks 1 and 3.
- Multi-line retained instruction fields are covered by Task 3.
- Outline stage diagnostics are covered by Task 2.
- Forward input and output shape cleanup are covered by Task 4.
- Required docs updates are covered by Task 5.

Placeholder scan:

- No task depends on undefined future work.
- Every code-changing task includes explicit target files, test command, implementation shape, and commit command.

Type consistency:

- Backend functions use `NovelState`, `LocalStore`, and `LocalStoreError`, all already present in the project.
- Frontend state uses the existing `/api/projects/{project_id}/state` endpoint and new `/api/projects/{project_id}/idea` endpoint.
- Diagnostics are stored separately from `agent_runs.jsonl` as required by the spec.
