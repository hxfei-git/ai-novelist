# Web Outline Smoke and Context Slimming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real-model Web smoke path from project creation and initial idea through first chapter generation, record compact outline-stage diagnostics, and trim duplicated outline forward context without changing stage contracts.

**Architecture:** Keep the Web service as the entry point for smoke verification and diagnostics. Add a small live-smoke script for the full flow, extend the Web outline service to persist one compact diagnostic JSONL record per run, and tighten outline context assembly so later stages prefer summaries and stage memory over repeated full Markdown when that is enough.

**Tech Stack:** Python 3.11+, pytest, stdlib smoke scripts, local Markdown/JSON file storage, DeepSeek real-model provider via the existing adapter layer.

---

### Task 1: Add a real-provider Web smoke path

**Files:**
- Create: `tests/smoke_web_outline_deepseek.py`
- Create: `tests/test_web_smoke.py`

- [ ] **Step 1: Write the failing smoke-path test**

Add a focused smoke-entrypoint test that proves the helper replays confirmations and that the module can be loaded from `tests/smoke_web_outline_deepseek.py`:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


def load_smoke_module():
    smoke_path = Path("tests/smoke_web_outline_deepseek.py")
    spec = importlib.util.spec_from_file_location("smoke_web_outline_deepseek", smoke_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_confirmed_turn_replays_confirmation():
    module = load_smoke_module()
    calls: list[str] = []

    class FakeResult:
        def __init__(self, needs_confirmation: bool) -> None:
            self.choices = [SimpleNamespace(id="1", label="确认", value="1")] if needs_confirmation else []
            self.state = SimpleNamespace()

    class FakeService:
        def __init__(self) -> None:
            self.count = 0

        def handle_turn(self, project_id: str, text: str, channel: str = "test"):
            calls.append(text)
            self.count += 1
            return FakeResult(self.count == 1)

    module.run_confirmed_turn(FakeService(), "demo", "生成大纲")

    assert calls == ["生成大纲", "1"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_smoke.py::test_run_confirmed_turn_replays_confirmation -q
```

Expected: FAIL because `tests/smoke_web_outline_deepseek.py` does not exist yet.

- [ ] **Step 3: Add the live smoke script**

Create `tests/smoke_web_outline_deepseek.py` as a stdlib-only runner that:

```python
from __future__ import annotations

import os
import shutil
from pathlib import Path

from ai_novelist.adapters.deepseek import DeepSeekAdapter
from ai_novelist.config import load_settings
from ai_novelist.director_service import DirectorService
from ai_novelist.research import MockSearchBackend
from ai_novelist.storage.local_store import LocalStore
from ai_novelist.web import service as web_service


def run_confirmed_turn(service: DirectorService, project_id: str, text: str):
    result = service.handle_turn(project_id, text, channel="test")
    if result.choices:
        result = service.handle_turn(project_id, "1", channel="test")
    return result


def build_service(store: LocalStore) -> DirectorService:
    settings = load_settings()
    api_key = settings.deepseek_api_key or os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("Set DEEPSEEK_API_KEY before running this smoke script")
    adapter = DeepSeekAdapter(
        api_key=api_key,
        model=settings.deepseek_model,
        base_url=settings.deepseek_base_url,
        timeout_seconds=180,
    )
    return DirectorService(store, adapter, MockSearchBackend())


def main() -> int:
    root = Path("projects")
    project_id = "smoke-web-outline-deepseek"
    project_dir = root / project_id
    if project_dir.exists():
        shutil.rmtree(project_dir)

    store = LocalStore(root)
    web_service.create_project(
        store,
        "Web Outline Smoke",
        project_id,
        idea="月球城市失忆工程师追查自己失落的小说手稿",
    )
    service = build_service(store)

    state = run_confirmed_turn(service, project_id, "生成大纲").state
    while state and state.outline_stage != "chapter_outline":
        state = run_confirmed_turn(service, project_id, "确认进入下一阶段").state
    run_confirmed_turn(service, project_id, "写第 1 章")

    assert store.outline_path(project_id).exists()
    assert store.chapter_draft_path(project_id, 1, 1).exists()
    print("web outline smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Use the existing smoke scripts as style references; this one should stay stdlib-only and exit nonzero on failed assertions.

- [ ] **Step 4: Keep the smoke runner self-contained**

Do not add a parallel app route or a test-only Web code path. Keep the helper functions in `tests/smoke_web_outline_deepseek.py` beside `run_confirmed_turn()` and `build_service()` so the unit test can import them directly.

- [ ] **Step 5: Run the smoke and unit tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_smoke.py::test_run_confirmed_turn_replays_confirmation -q
.venv/bin/python tests/smoke_web_outline_deepseek.py
```

Expected: the unit test passes, and the smoke script prints `web outline smoke passed` when DeepSeek credentials and network access are available.

- [ ] **Step 6: Commit**

```bash
git add tests/smoke_web_outline_deepseek.py tests/test_web_smoke.py
git commit -m "test: add web deepseek outline smoke"
```

### Task 2: Persist compact outline-stage diagnostics

**Files:**
- Modify: `src/ai_novelist/storage/local_store.py`
- Modify: `src/ai_novelist/web/service.py`
- Modify: `src/ai_novelist/graph_outline.py`
- Test: `tests/test_web_service.py`

- [ ] **Step 1: Write the failing diagnostics tests**

Add two unit tests: one for a successful diagnostic record and one for a failure-shaped record.

```python
import json

from ai_novelist.state import NovelState


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


def test_generate_outline_stage_writes_error_diagnostic(monkeypatch, tmp_path):
    store = LocalStore(tmp_path)
    service.create_project(store, "Diagnostic Demo", "diag-demo")

    def fake_run_outline_stage_node(data, adapter, local_store, progress=None):
        state = NovelState.from_dict(data)
        state.director_task_args["outline_stage_diagnostics"] = {
            "stage": "direction",
            "mode": "full",
            "instruction_chars": 12,
            "author_craft_chars": 0,
            "previous_stage_context_chars": 0,
            "current_stage_context_chars": 0,
            "role_prompt_count": 2,
            "role_prompt_chars": [120, 80],
            "synthesizer_prompt_chars": 240,
            "output_chars": 300,
            "structure_repair_triggered": False,
            "elapsed_ms": 9,
            "status": "error",
            "error": "boom",
        }
        state.error = "boom"
        return state.to_dict()

    monkeypatch.setattr(service, "run_outline_stage_node", fake_run_outline_stage_node)

    service.generate_outline_stage(store, DummyAdapter(), "diag-demo", "direction", "补强方向")

    path = store.outline_stage_context_log_path("diag-demo")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["status"] == "error"
    assert rows[-1]["error"] == "boom"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_write_outline_stage_diagnostic_appends_jsonl tests/test_web_service.py::test_generate_outline_stage_writes_error_diagnostic -q
```

Expected: FAIL because the diagnostic path and JSONL helper are not yet implemented end to end.

- [ ] **Step 3: Add the local-store path helper**

Add to `src/ai_novelist/storage/local_store.py` near the other debug/path helpers:

```python
    def outline_stage_context_log_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "debug" / "outline_stage_context.jsonl"
```

- [ ] **Step 4: Add the Web diagnostic writer and stage payload**

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

Then update `generate_outline_stage()` so it measures elapsed time and appends a compact diagnostics record after `run_outline_stage_node()` returns:

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

In `src/ai_novelist/graph_outline.py`, attach the per-stage diagnostics to `state.director_task_args["outline_stage_diagnostics"]` before saving state, and include the compact size fields for:

```python
diagnostics = {
    "stage": stage,
    "mode": "full",
    "instruction_chars": len(state.user_request.strip()),
    "author_craft_chars": len(author_craft),
    "previous_stage_context_chars": len(previous_stage_context(state, stage)),
    "current_stage_context_chars": len(current_stage_context(state, stage)),
    "structure_repair_triggered": False,
}
```

Also populate `role_prompt_count`, `role_prompt_chars`, `synthesizer_prompt_chars`, and `output_chars` from the real run, and mirror the same shape in `revise_outline_stage_from_existing()` with `mode = "light_revision"`. Keep the record small; do not store full prompt text.

- [ ] **Step 5: Run the diagnostics test suite**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_write_outline_stage_diagnostic_appends_jsonl tests/test_web_service.py::test_generate_outline_stage_writes_error_diagnostic tests/test_web_service.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ai_novelist/storage/local_store.py src/ai_novelist/web/service.py src/ai_novelist/graph_outline.py tests/test_web_service.py
git commit -m "feat: log web outline stage diagnostics"
```

### Task 3: Slim duplicated outline forward context

**Files:**
- Modify: `src/ai_novelist/graph_outline.py`
- Test: `tests/test_outline_collaboration.py`

- [ ] **Step 1: Write the failing context-slimming tests**

Add one test that proves `previous_stage_context()` prefers summary and stage memory over the full Markdown when the stored artifact only needs a compact handoff:

```python
def test_previous_stage_context_prefers_summary_and_memory(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.outline_stage_artifacts["worldbuilding"] = {
        "stage": "worldbuilding",
        "label": "世界观设定",
        "status": "options_ready",
        "summary": "世界观摘要",
        "stage_memory": ["世界规则", "势力关系"],
        "synthesis": "# 世界观设定\n\n不应被优先重复。",
    }
    store.save_state(state)

    text = previous_stage_context(store.load_state("demo"), "characters", store=store)

    assert "世界观摘要" in text
    assert "世界规则" in text
    assert "不应被优先重复" not in text
```

Add a second test that checks the outline-stage revision prompt can still use the saved artifact store and keep the prompt compact:

```python
def test_outline_stage_revision_prompt_uses_saved_context(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.outline_stage_artifacts["direction"] = {
        "stage": "direction",
        "label": "方向定位",
        "status": "options_ready",
        "summary": "方向摘要",
        "stage_memory": ["题材", "主角", "冲突"],
    }
    store.save_state(state)

    prompt = build_outline_stage_revision_prompt(
        state=store.load_state("demo"),
        stage="worldbuilding",
        author_craft="作者构思参考",
        current_markdown="## 世界观设定\n\n应保持精简。",
        store=store,
        artifact=state.outline_stage_artifacts["direction"],
    )

    assert "方向摘要" in prompt
    assert "题材" in prompt
    assert "不应被优先重复" not in prompt
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_outline_collaboration.py -q
```

Expected: FAIL until `previous_stage_context()` and the prompt builders use the compact source selection consistently.

- [ ] **Step 3: Implement the forward-context slimming**

Update `src/ai_novelist/graph_outline.py` so the outline stage context assembly follows these rules:

```python
def previous_stage_context(state: NovelState, stage: str, store: LocalStore | None = None, max_chars_per_stage: int = 1800) -> str:
    ...
```

The implementation should:

```python
    - prefer `summary` and explicit `stage_memory`
    - only fall back to saved Markdown / in-memory `synthesis` when lighter context is unavailable
    - keep status labels when using synthesis fallback
    - avoid re-inserting the same long content into both previous and current stage sections
```

Also update `build_outline_stage_role_prompt()`, `build_outline_stage_synthesizer_prompt()`, and `build_outline_stage_revision_prompt()` to accept `store: LocalStore | None = None` so the real flow can use saved artifacts without forcing duplicate text through helper layers.

In the same file, trim duplicated forward input in the stage prompt composition so later stages only receive:

```python
    - the current stage instruction
    - the compact previous-stage handoff
    - the current stage artifact or revision target
    - the author craft brief
    - the minimal role-review set needed for the stage
```

Do not remove any stage contract, lock constraint, or required heading structure. Do not add a new global context layer; keep this change local to outline prompt assembly.

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_outline_collaboration.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ai_novelist/graph_outline.py tests/test_outline_collaboration.py
git commit -m "fix: slim outline forward context"
```

### Task 4: Validate the real smoke path and update project docs

**Files:**
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`
- Test: `tests/smoke_web_outline_deepseek.py`
- Test: `tests/test_web_service.py`
- Test: `tests/test_outline_collaboration.py`
- Test: `tests/test_web_smoke.py`

- [ ] **Step 1: Write the validation expectation into the docs**

Before merging code, update the two repository-mandated docs to capture:

```markdown
- the new Web DeepSeek smoke path
- the new outline-stage diagnostic JSONL log
- the forward-context slimming rules
- any remaining limitation around live model availability
```

The doc update should be in the same change set as the code so the repo rule stays satisfied.

- [ ] **Step 2: Run the smoke plus focused Python suite**

Run:

```bash
.venv/bin/python tests/smoke_web_outline_deepseek.py
.venv/bin/python -m pytest tests/test_web_service.py tests/test_outline_collaboration.py tests/test_web_smoke.py -q
```

Expected: the smoke script succeeds with a real DeepSeek configuration, and the focused pytest run passes.

- [ ] **Step 3: Verify the generated artifacts and log**

Check that the smoke run produced:

```text
projects/<project>/outline.md
projects/<project>/chapters/chapter_001/draft_v1.md
projects/<project>/debug/outline_stage_context.jsonl
```

The JSONL file should contain compact records only, not long prompt dumps.

- [ ] **Step 4: Commit the completed change set**

```bash
git add docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md tests/smoke_web_outline_deepseek.py tests/test_web_smoke.py src/ai_novelist/web/service.py src/ai_novelist/storage/local_store.py src/ai_novelist/graph_outline.py tests/test_web_service.py tests/test_outline_collaboration.py
git commit -m "feat: add web outline smoke and slimming"
```

## Self-Review

Spec coverage check:

- live DeepSeek Web smoke path: Task 1 and Task 4
- compact diagnostic JSONL logging: Task 2 and Task 4
- duplicated forward-context slimming: Task 3 and Task 4
- required docs updates: Task 4

Placeholder scan:

- no TBD/TODO placeholders
- no “write tests for the above” shortcuts
- each step has an explicit test command or implementation snippet

Type consistency check:

- `outline_stage_context_log_path()` is defined before it is used
- `write_outline_stage_diagnostic()` is introduced in the Web service before the service calls it
- `previous_stage_context(..., store=...)` and the prompt-builder `store` parameter are consistent across tasks
- the smoke script uses the existing `DeepSeekAdapter`, `DirectorService`, `MockSearchBackend`, and `LocalStore` types already present in the repository
