# Web Prompt Context Prune Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strictly prune obsolete prompts and unreachable Web-era compatibility branches, then verify Web workflow logic and outline-to-body context consistency.

**Architecture:** Keep the Web-only runtime boundary: frontend actions call FastAPI routes, routes call focused Web action modules, action modules call retained graph entry points, graph code loads prompts through an explicit registry, and storage writes local project artifacts. The implementation first builds machine-checkable evidence for retained prompts and agents, then removes branches that are not reachable from active Web routes or retained graph nodes.

**Tech Stack:** Python 3.11+/3.12, pytest, FastAPI, Vite/React/TypeScript, LangGraph fallback sequential graphs, local `LocalStore`, markdown prompt package data.

---

## Scope Check

The approved spec touches prompt registry cleanup, adapter branch pruning, Web action correctness, and context correctness. These are related because prompt and adapter cleanup cannot be safely done without proving active Web graph paths, and context correctness depends on the same outline/chapter graph boundary. The plan keeps each phase independently testable and commit-sized.

## File Structure

- Create `src/ai_novelist/prompts/registry.py`: explicit retained prompt names, generated inline agent headers, and validation helpers.
- Modify `src/ai_novelist/prompts/__init__.py`: validate `load_prompt(name)` through the registry and remove stale policy entries.
- Modify `tests/test_prompt_loader.py`: registry coverage, orphan prompt detection, missing registry detection, policy entry consistency.
- Modify `src/ai_novelist/adapters/mock_codex.py`: remove responses for deleted old agents; expose the retained mock agent set for tests.
- Modify `src/ai_novelist/adapters/deepseek.py`: remove old non-Web agent category entries and keep category tests tied to the registry.
- Modify `tests/test_mock_codex_adapter.py` and `tests/test_deepseek_adapter.py`: assert adapter branch sets match retained Web agents.
- Modify `src/ai_novelist/graph_outline.py`: delete unused Director/show/status helper functions and old routing imports that no active Web action calls.
- Modify `src/ai_novelist/outline_graph/routing.py`: delete Director-only routing helpers if they become unreferenced after `graph_outline.py` cleanup.
- Modify `tests/test_outline_graph_modules.py`: replace shape/export assertions for deleted helper functions with active Web outline behavior assertions.
- Modify `src/ai_novelist/web/app.py`: import focused action modules directly when practical, reducing `web/service.py` facade dependency.
- Modify `src/ai_novelist/web/service.py`: remove re-exports no longer used by routes or tests.
- Modify `tests/test_web_app.py`, `tests/test_web_service.py`, `tests/test_web_outline_service.py`, `tests/test_web_chapter_service.py`: update tests to active routes and focused modules instead of facade preservation.
- Modify `src/ai_novelist/web/chapter_outline_actions.py`: fix review-apply persistence/idempotency if tests expose stale report or artifact behavior.
- Modify `src/ai_novelist/web/chapter_actions.py`: fix selected-volume chapter generation if tests expose wrong remaining chapter selection.
- Modify `src/ai_novelist/context_builder.py`, `src/ai_novelist/graph_volume_write.py`, `src/ai_novelist/graph_chapter_write.py`: fix context manifest or chapter-slice issues found by the context tests.
- Modify `tests/test_context_builder.py`, `tests/test_graph_volume_write.py`, `tests/test_web_service.py`: add context and Web regression coverage.
- Modify `docs/web_only_reference_matrix.md`: record retained/deleted prompt and branch decisions.
- Modify `docs/IMPLEMENTATION_PLAN.md` and `docs/SESSION_SUMMARY.md`: record implementation notes, test results, and remaining risk.

## Task 1: Prompt Registry And Orphan Detection

**Files:**
- Create: `src/ai_novelist/prompts/registry.py`
- Modify: `src/ai_novelist/prompts/__init__.py`
- Modify: `tests/test_prompt_loader.py`

- [ ] **Step 1: Add failing registry tests**

Add these tests to `tests/test_prompt_loader.py`:

```python
from importlib import resources

from ai_novelist.prompts.registry import INLINE_AGENT_NAMES, PROMPT_REGISTRY, validate_prompt_registry


def prompt_file_names() -> set[str]:
    return {
        path.name.removesuffix(".md")
        for path in resources.files("ai_novelist.prompts").iterdir()
        if path.name.endswith(".md")
    }


def test_prompt_registry_has_no_missing_files():
    problems = validate_prompt_registry()
    assert problems.missing_files == []


def test_prompt_directory_has_no_orphan_files():
    assert sorted(prompt_file_names() - set(PROMPT_REGISTRY)) == []


def test_author_craft_policy_prompt_names_are_registered():
    from ai_novelist.prompts import AUTHOR_CRAFT_POLICY_PROMPTS

    assert sorted(set(AUTHOR_CRAFT_POLICY_PROMPTS) - set(PROMPT_REGISTRY)) == []


def test_inline_agent_names_are_not_prompt_files():
    assert sorted(set(INLINE_AGENT_NAMES) & prompt_file_names()) == []
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py -q
```

Expected: fail because `ai_novelist.prompts.registry` does not exist.

- [ ] **Step 3: Create prompt registry**

Create `src/ai_novelist/prompts/registry.py`:

```python
"""Explicit prompt registry for retained Web runtime prompts."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources


PROMPT_REGISTRY: frozenset[str] = frozenset(
    {
        "atmosphere_enhancer",
        "bible_conflict_checker",
        "bible_update_extractor",
        "bible_update_synthesizer",
        "chapter_auto_reviser",
        "chapter_card_synthesizer",
        "chapter_conflict_agent",
        "chapter_goal_agent",
        "chapter_hook_agent",
        "chapter_pacing_agent",
        "chapter_planner",
        "chapter_writer",
        "craft_profile_extractor",
        "dialogue_enhancer",
        "direct_chapter_writer",
        "editor",
        "emotional_resonance_polisher",
        "ending_resonance_agent",
        "hook_enhancer",
        "human_feedback_reviser",
        "outline_editor",
        "outline_planner",
        "outline_reviser",
        "outline_stage_reviser",
        "project_craft_memory_extractor",
        "restraint_agent",
        "restraint_polisher",
        "scene_breakdown_agent",
        "scene_conflict_check_agent",
        "scene_synthesizer",
        "stage_craft_brief_synthesizer",
        "style_normalizer",
        "version_comparator",
        "volume_blocker_reviser",
        "volume_consistency_checker",
    }
)

INLINE_AGENT_NAMES: frozenset[str] = frozenset(
    {
        "characters_structure_repair",
        "chapter_outline_structure_repair",
        "global_consistency_repair",
        "global_consistency_reviewer",
        "outline_question_answerer",
        "outline_stage_role",
        "outline_stage_synthesizer",
        "story_flow_structure_repair",
        "volume_outline_structure_repair",
        "worldbuilding_structure_repair",
    }
)


@dataclass(frozen=True)
class PromptRegistryProblems:
    missing_files: list[str]
    orphan_files: list[str]


def prompt_file_names() -> set[str]:
    return {
        path.name.removesuffix(".md")
        for path in resources.files("ai_novelist.prompts").iterdir()
        if path.name.endswith(".md")
    }


def validate_prompt_registry() -> PromptRegistryProblems:
    files = prompt_file_names()
    registry = set(PROMPT_REGISTRY)
    return PromptRegistryProblems(
        missing_files=sorted(registry - files),
        orphan_files=sorted(files - registry),
    )
```

- [ ] **Step 4: Gate `load_prompt()` and trim stale policy entries**

Modify `src/ai_novelist/prompts/__init__.py`:

```python
"""Prompt loading utilities."""

from __future__ import annotations

from importlib import resources

from ai_novelist.prompts.registry import PROMPT_REGISTRY


class PromptNotFoundError(RuntimeError):
    """Raised when a prompt template is missing."""


AUTHOR_CRAFT_POLICY_PROMPTS = {
    "outline_planner",
    "outline_stage_reviser",
    "chapter_goal_agent",
    "chapter_conflict_agent",
    "chapter_hook_agent",
    "chapter_card_synthesizer",
    "scene_breakdown_agent",
    "scene_conflict_check_agent",
    "scene_synthesizer",
    "chapter_writer",
    "direct_chapter_writer",
    "chapter_auto_reviser",
    "volume_consistency_checker",
    "volume_blocker_reviser",
    "human_feedback_reviser",
    "dialogue_enhancer",
    "atmosphere_enhancer",
    "hook_enhancer",
    "style_normalizer",
    "restraint_polisher",
    "emotional_resonance_polisher",
}


def load_prompt(name: str) -> str:
    if name not in PROMPT_REGISTRY:
        raise PromptNotFoundError(f"Prompt is not registered: {name}.md")
    prompt_file = f"{name}.md"
    try:
        text = resources.files(__package__).joinpath(prompt_file).read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PromptNotFoundError(f"Prompt not found: {prompt_file}") from exc
    if name in AUTHOR_CRAFT_POLICY_PROMPTS:
        policy = load_author_craft_policy()
        if "Author Craft Policy" not in text:
            text = f"{text.rstrip()}\n\n{policy}"
    return text


def load_author_craft_policy() -> str:
    try:
        return resources.files(__package__).joinpath("partials", "author_craft_policy.md").read_text(encoding="utf-8").rstrip()
    except FileNotFoundError:
        return ""
```

- [ ] **Step 5: Run prompt tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py -q
```

Expected: pass. If it fails with orphan files, delete the orphan prompt only if Task 2 evidence proves it is not loaded by active Web paths; otherwise add it to `PROMPT_REGISTRY` and explain why in `docs/web_only_reference_matrix.md`.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/ai_novelist/prompts/registry.py src/ai_novelist/prompts/__init__.py tests/test_prompt_loader.py
git commit -m "test: add prompt registry guard"
```

## Task 2: Prompt And Agent Evidence Matrix

**Files:**
- Modify: `docs/web_only_reference_matrix.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Capture prompt and agent evidence**

Run:

```bash
rg -n "load_prompt\\(|AGENT:" src/ai_novelist tests > /tmp/ai_novelist_prompt_agent_refs.txt
rg -n "continuity_editor|structure_editor|character_arc_editor|style_editor|simulated_reader|pacing_guard_editor|revision_planner|targeted_reviser|revision_self_check|chapter_summarizer|final_bible_update_extractor|director|research|export|finalize|show_outline|show_status" src/ai_novelist tests > /tmp/ai_novelist_legacy_refs.txt
```

Expected: command exits `0` and both files contain references to classify.

- [ ] **Step 2: Update the reference matrix**

Append this section to `docs/web_only_reference_matrix.md`, filling only rows that are proven by the scans:

```markdown
## 2026-05-29 Prompt And Branch Prune Matrix

| Area | Evidence | Decision | Follow-up |
| --- | --- | --- | --- |
| Prompt registry | `tests/test_prompt_loader.py` verifies registered files, missing files, and orphan files | retain | registry is the allowed prompt boundary |
| `AUTHOR_CRAFT_POLICY_PROMPTS` stale names | missing prompt names were removed from the policy set | delete | keep policy set subset of registry |
| Inline outline agents | emitted from `outline_graph/prompts.py`, `outline_graph/repair.py`, and `graph_outline.py` | retain | not prompt files; covered by `INLINE_AGENT_NAMES` |
| Old Director agent | not called by current Web routes | delete | remove mock branch and unused prompt builder |
| Old research/export/finalize/show mock branches | not called by current Web routes | delete | remove mock branches and old routing helpers |
```

- [ ] **Step 3: Record session status**

Append to `docs/SESSION_SUMMARY.md` under the current cleanup area:

```markdown
## Web Prompt Context Prune Audit

- Added a manifest-backed prompt registry plan and started strict Web-only pruning.
- Current rule: prompts and branches are retained only when reachable from active Web routes, retained graph nodes, prompt loading, adapter execution, or active Web behavior tests.
- Compatibility with old deleted CLI flows is no longer a default retention reason for this cleanup batch.
```

- [ ] **Step 4: Run docs checks**

Run:

```bash
rg -n "2026-05-29 Prompt And Branch Prune Matrix|Web Prompt Context Prune Audit" docs/web_only_reference_matrix.md docs/SESSION_SUMMARY.md
git diff --check
```

Expected: `rg` finds both new headings; `git diff --check` has no output.

- [ ] **Step 5: Commit**

Run:

```bash
git add docs/web_only_reference_matrix.md docs/SESSION_SUMMARY.md
git commit -m "docs: record prompt prune evidence matrix"
```

## Task 3: Remove Old Mock And DeepSeek Agent Branches

**Files:**
- Modify: `src/ai_novelist/adapters/mock_codex.py`
- Modify: `src/ai_novelist/adapters/deepseek.py`
- Modify: `tests/test_mock_codex_adapter.py`
- Modify: `tests/test_deepseek_adapter.py`

- [ ] **Step 1: Add adapter branch tests**

Add this test to `tests/test_mock_codex_adapter.py`:

```python
def test_mock_adapter_does_not_expose_deleted_legacy_agents(tmp_path):
    adapter = CodexCLIAdapter(mock=True)
    deleted_agents = [
        "director",
        "retrieval_context_synthesizer",
        "direction_proposer",
        "continuity_editor",
        "structure_editor",
        "character_arc_editor",
        "style_editor",
        "simulated_reader",
        "pacing_guard_editor",
        "revision_planner",
        "targeted_reviser",
        "revision_self_check",
        "chapter_summarizer",
        "final_bible_update_extractor",
    ]
    for agent in deleted_agents:
        output = adapter.complete(f"AGENT: {agent}\n写作任务", tmp_path)
        assert "mock" not in output.lower()
        assert "action" not in output.lower()
```

Add this test to `tests/test_deepseek_adapter.py`:

```python
def test_deepseek_agent_categories_do_not_include_deleted_legacy_agents():
    from ai_novelist.adapters.deepseek import FAST_AGENT_NAMES, SLOW_AGENT_NAMES

    deleted_agents = {
        "continuity_editor",
        "structure_editor",
        "character_arc_editor",
        "style_editor",
        "simulated_reader",
        "pacing_guard_editor",
    }
    assert deleted_agents.isdisjoint(FAST_AGENT_NAMES)
    assert deleted_agents.isdisjoint(SLOW_AGENT_NAMES)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_mock_codex_adapter.py tests/test_deepseek_adapter.py -q
```

Expected: fail because deleted legacy agents still have explicit mock or category handling.

- [ ] **Step 3: Remove stale mock branches**

In `src/ai_novelist/adapters/mock_codex.py`, delete the top-level `complete()` branches for:

```python
"AGENT: director"
"AGENT: retrieval_context_synthesizer"
"AGENT: direction_proposer"
"AGENT: continuity_editor"
"AGENT: structure_editor"
"AGENT: character_arc_editor"
"AGENT: style_editor"
"AGENT: simulated_reader"
"AGENT: pacing_guard_editor"
"AGENT: revision_planner"
"AGENT: targeted_reviser"
"AGENT: revision_self_check"
"AGENT: chapter_summarizer"
"AGENT: final_bible_update_extractor"
```

Then remove now-unused private methods that only served those branches, including `_mock_director()`, `_mock_research_intent()`, and `_extract_director_request()` if `rg` confirms no remaining references:

```bash
rg -n "_mock_director|_mock_research_intent|_extract_director_request" src/ai_novelist/adapters/mock_codex.py
```

Expected after removal: no references.

- [ ] **Step 4: Remove stale DeepSeek category names**

In `src/ai_novelist/adapters/deepseek.py`, remove these names from category sets:

```python
"style_editor"
"simulated_reader"
"pacing_guard_editor"
"continuity_editor"
"structure_editor"
"character_arc_editor"
```

- [ ] **Step 5: Run adapter tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_mock_codex_adapter.py tests/test_deepseek_adapter.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/ai_novelist/adapters/mock_codex.py src/ai_novelist/adapters/deepseek.py tests/test_mock_codex_adapter.py tests/test_deepseek_adapter.py
git commit -m "fix: prune legacy adapter agent branches"
```

## Task 4: Remove Unreachable Outline Director Helpers

**Files:**
- Modify: `src/ai_novelist/graph_outline.py`
- Modify: `src/ai_novelist/outline_graph/routing.py`
- Modify: `tests/test_outline_graph_modules.py`

- [ ] **Step 1: Add source-guard tests for deleted helpers**

Add to `tests/test_outline_graph_modules.py`:

```python
from pathlib import Path


def test_outline_graph_no_longer_loads_deleted_director_prompt():
    source = Path("src/ai_novelist/graph_outline.py").read_text(encoding="utf-8")
    assert 'load_prompt("director")' not in source
    assert "def build_outline_director_prompt" not in source


def test_outline_routing_no_longer_exports_director_only_routes():
    source = Path("src/ai_novelist/outline_graph/routing.py").read_text(encoding="utf-8")
    assert "route_after_outline_director" not in source
    assert "stage_action_from_director" not in source
    assert "should_defer_stage_confirmation_to_director" not in source
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_outline_graph_modules.py -q
```

Expected: fail because old Director helpers still exist.

- [ ] **Step 3: Delete old helper imports and functions**

In `src/ai_novelist/graph_outline.py`:

- remove imports of `route_after_outline_director`, `should_defer_stage_confirmation_to_director`, and `stage_action_from_director`
- delete `build_outline_director_prompt`
- delete `parse_outline_director_output`, `normalize_outline_director_action`, and helpers only referenced by deleted Director parsing if `rg` proves they are unused
- delete `outline_show_outline_node` and `outline_show_status_node` only if `rg` confirms no active Web action or retained test calls them

Use:

```bash
rg -n "build_outline_director_prompt|parse_outline_director_output|normalize_outline_director_action|outline_show_outline_node|outline_show_status_node|route_after_outline_director|stage_action_from_director|should_defer_stage_confirmation_to_director" src tests
```

Expected after removal: no references except in tests that assert absence.

- [ ] **Step 4: Delete old routing helpers**

In `src/ai_novelist/outline_graph/routing.py`, delete:

- `should_defer_stage_confirmation_to_director`
- `stage_action_from_director`
- `route_after_outline_director`

Also delete constants that are only used by those helpers, such as old show/status action names, after verifying with `rg`.

- [ ] **Step 5: Run outline tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_outline_graph_modules.py tests/test_web_outline_service.py tests/test_web_service.py::test_outline_stage_list_hides_review_lock -q
```

Expected: pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/ai_novelist/graph_outline.py src/ai_novelist/outline_graph/routing.py tests/test_outline_graph_modules.py
git commit -m "fix: remove legacy outline director helpers"
```

## Task 5: Direct Web Route Imports And Facade Prune

**Files:**
- Modify: `src/ai_novelist/web/app.py`
- Modify: `src/ai_novelist/web/service.py`
- Modify: `tests/test_web_app.py`
- Modify: `tests/test_web_service.py`

- [ ] **Step 1: Add route import guard tests**

Add to `tests/test_web_app.py`:

```python
from pathlib import Path


def test_web_app_imports_focused_action_modules_not_service_facade():
    source = Path("src/ai_novelist/web/app.py").read_text(encoding="utf-8")
    assert "from ai_novelist.web import service" not in source
    assert "from ai_novelist.web import outline_actions" in source
    assert "from ai_novelist.web import chapter_outline_actions" in source
    assert "from ai_novelist.web import chapter_actions" in source
    assert "from ai_novelist.web import review_actions" in source
    assert "from ai_novelist.web import project_service" in source
```

Replace service facade export tests in `tests/test_web_service.py` with focused-module tests. Keep assertions that active modules export active functions, but remove assertions that `service.py` re-exports every function.

- [ ] **Step 2: Run route tests to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_app.py::test_web_app_imports_focused_action_modules_not_service_facade tests/test_web_service.py::test_project_service_exports_project_and_progress_helpers -q
```

Expected: fail because `web/app.py` still imports the service facade.

- [ ] **Step 3: Update app imports and call sites**

Modify `src/ai_novelist/web/app.py` to import modules directly:

```python
from ai_novelist.web import chapter_actions, chapter_outline_actions, outline_actions, project_service, review_actions
```

Then replace route call sites:

```python
service.list_projects -> project_service.list_projects
service.create_project -> project_service.create_project
service.build_progress_event -> project_service.build_progress_event
service.outline_stage_list -> outline_service.outline_stage_list
service.load_outline_stage_payload -> outline_actions.load_outline_stage_payload
service.generate_outline_stage -> outline_actions.generate_outline_stage
service.chapter_outline_workspace_payload -> chapter_outline_actions.chapter_outline_workspace_payload
service.generate_chapter_batch -> chapter_actions.generate_chapter_batch
service.review_all_chapters -> review_actions.review_all_chapters
```

If `outline_stage_list`, `latest_outline_review_report`, or shared helper functions live in `outline_service`, import that module too:

```python
from ai_novelist.web import outline_service
```

- [ ] **Step 4: Slim service facade**

In `src/ai_novelist/web/service.py`, remove unused imports that are no longer reached from `web/app.py` or tests. Keep only imports needed by public tests that still intentionally cover the facade. If no active route uses the facade, reduce the module to documented compatibility helpers or delete facade export tests.

Run:

```bash
rg -n "web import service|web\\.service|service\\." src tests
```

Expected: only deliberate tests or no references.

- [ ] **Step 5: Run Web route tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_app.py tests/test_web_service.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/ai_novelist/web/app.py src/ai_novelist/web/service.py tests/test_web_app.py tests/test_web_service.py
git commit -m "fix: route web app through focused action modules"
```

## Task 6: Chapter-Outline Review Apply Persistence

**Files:**
- Modify: `src/ai_novelist/web/chapter_outline_actions.py`
- Modify: `tests/test_web_service.py`

- [ ] **Step 1: Add failing chapter-outline apply test**

Add to `tests/test_web_service.py`:

```python
def test_apply_chapter_outline_review_marks_report_applied_and_updates_artifact(monkeypatch, tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("web-demo", "Web Demo")
    state.outline_stage_artifacts["chapter_outline"] = {
        "stage": "chapter_outline",
        "status": "options_ready",
        "metadata": {"total_volumes": 1, "current_volume_index": 1, "completed_volumes": []},
    }
    store.save_outline_artifact(state, "chapter_outline", "## 第一卷\n\n### 第 1 章：旧章纲\n")
    store.save_outline_stage(state, "chapter_outline", "## 第一卷\n\n### 第 1 章：旧章纲\n")
    store.save_state(state)
    report_path, _ = service.chapter_outline_review_report_paths(store, "web-demo", "run-1")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "project_id": "web-demo",
                "run_id": "run-1",
                "status": "reviewed",
                "decision": "revise",
                "score": 80,
                "summary": "需要修正第 1 章",
                "notes": "第 1 章目标不清。",
                "revision_instruction": "把第 1 章目标改清楚。",
                "source_outline": "## 第一卷\n\n### 第 1 章：旧章纲\n",
                "source_outline_summary": "旧章纲",
                "repair_suggestions": [{"id": "issue-1", "message": "目标不清", "recommendation": "明确目标", "selected": True}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def fake_run(data: dict, adapter: AgentAdapter, local_store: LocalStore, progress=None) -> dict:
        updated = NovelState.from_dict(data)
        updated.outline_stage_artifacts["chapter_outline"]["synthesis"] = "## 第一卷\n\n### 第 1 章：目标明确\n"
        local_store.save_outline_artifact(updated, "chapter_outline", "## 第一卷\n\n### 第 1 章：目标明确\n")
        return updated.to_dict()

    monkeypatch.setattr(chapter_outline_actions, "run_outline_stage_node", fake_run)
    result = service.apply_chapter_outline_review(store, DummyAdapter(), "web-demo", "run-1", selected_issue_ids=["issue-1"])

    assert result["applied"] is True
    applied_report = service.load_chapter_outline_review_report(store, "web-demo", "run-1")
    assert applied_report["status"] == "applied"
    assert applied_report["applied"] is True
    assert "目标明确" in store.load_outline_artifact("web-demo", "chapter_outline")
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_apply_chapter_outline_review_marks_report_applied_and_updates_artifact -q
```

Expected: fail because chapter-outline reports are not marked applied or the artifact is stale.

- [ ] **Step 3: Implement applied report persistence**

In `src/ai_novelist/web/chapter_outline_actions.py`, add a helper:

```python
def mark_chapter_outline_review_applied(store: LocalStore, project_id: str, report: dict[str, Any], path: Path) -> dict[str, Any]:
    updated = dict(report)
    updated["status"] = "applied"
    updated["applied"] = True
    updated["applied_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    updated["applied_path"] = path.relative_to(store.project_dir(project_id)).as_posix()
    report_path, markdown_path = chapter_outline_review_report_paths(store, project_id, str(updated.get("run_id") or ""))
    report_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_chapter_outline_review_markdown(updated), encoding="utf-8")
    return updated
```

In `apply_chapter_outline_review()`, before doing model work, return idempotent success when `report["applied"] is True` or `status == "applied"`. After `run_outline_stage_node()`, save the updated `chapter_outline` artifact if the revised state has a `synthesis` or if the artifact file already changed, then call `mark_chapter_outline_review_applied()`.

- [ ] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_apply_chapter_outline_review_marks_report_applied_and_updates_artifact tests/test_web_service.py::test_latest_chapter_outline_review_report_reads_saved_report -q
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/ai_novelist/web/chapter_outline_actions.py tests/test_web_service.py
git commit -m "fix: persist chapter outline review apply state"
```

## Task 7: Chapter Batch Selection And Context Slice Proof

**Files:**
- Modify: `tests/test_graph_volume_write.py`
- Modify: `tests/test_context_builder.py`
- Modify: `src/ai_novelist/graph_volume_write.py`
- Modify: `src/ai_novelist/context_builder.py`

- [ ] **Step 1: Add context slice regression tests**

Add to `tests/test_graph_volume_write.py`:

```python
def test_volume_batch_context_manifest_uses_chapter_specific_outline_slice(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("web-demo", "Web Demo")
    state.director_task_args = {"volume": 1, "chapters": "2"}
    outline = "## 第一卷\n\n### 第 1 章：只给第一章\n\n### 第 2 章：只给第二章\n\n### 第 3 章：只给第三章\n"
    store.save_outline_artifact(state, "chapter_outline", outline)
    store.save_state(state)

    result = NovelState.from_dict(prepare_volume_batch_node(state.to_dict(), store))
    item = result.director_task_args["batch_items"][0]

    assert item["chapter"] == 2
    assert "只给第二章" in item["outline"]
    assert "只给第一章" not in item["outline"]
    assert "只给第三章" not in item["outline"]
    manifest_text = json.dumps(result.director_task_args["batch_context_manifests"], ensure_ascii=False)
    assert "chapter_outline_slice" in manifest_text
```

Add to `tests/test_context_builder.py`:

```python
def test_direct_chapter_context_manifest_marks_fallback_outline(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("web-demo", "Web Demo")
    state.current_chapter = 7
    state.active_chapter = 7
    bundle = build_context_bundle(state, store, "direct_chapter_drafting", chapter=7)
    manifest = build_context_manifest(bundle)
    assert any(item["section"] == "章节大纲切片" for item in manifest)
    assert "暂无" in bundle.text or "缺失" in bundle.text
```

- [ ] **Step 2: Run tests to verify current behavior**

Run:

```bash
.venv/bin/python -m pytest tests/test_graph_volume_write.py::test_volume_batch_context_manifest_uses_chapter_specific_outline_slice tests/test_context_builder.py::test_direct_chapter_context_manifest_marks_fallback_outline -q
```

Expected: pass if existing context handling is correct, fail if the manifest does not expose the slice or fallback clearly.

- [ ] **Step 3: Fix context slice or manifest if needed**

If the first test fails, update `prepare_volume_batch_node()` in `src/ai_novelist/graph_volume_write.py` so each `chapter_state` receives:

```python
outline_slice = extract_chapter_outline_slice(full_outline, chapter)
if not outline_slice.strip() or outline_slice.strip() == "暂无":
    outline_slice = f"第 {chapter} 章：章节大纲切片缺失，来源为第 {volume} 卷完整章纲。"
chapter_state.director_task_args["selected_chapter_outline"] = outline_slice
```

If the second test fails, update `build_chapter_outline_slice_section()` in `src/ai_novelist/context_builder.py` so missing slices return an explicit fallback string:

```python
return f"第 {chapter or '未知'} 章：章节大纲切片缺失。"
```

- [ ] **Step 4: Run context tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_context_builder.py tests/test_graph_volume_write.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/ai_novelist/graph_volume_write.py src/ai_novelist/context_builder.py tests/test_context_builder.py tests/test_graph_volume_write.py
git commit -m "fix: prove chapter-specific drafting context"
```

## Task 8: Web Long-Running Action Guard Audit

**Files:**
- Modify: `tests/test_frontend_review_tabs_structure.py`
- Modify: `web/frontend/src/main.tsx`
- Modify: `tests/test_web_app.py`
- Modify: `src/ai_novelist/web/app.py`

- [ ] **Step 1: Add source guards for long-running frontend actions**

Add to `tests/test_frontend_review_tabs_structure.py`:

```python
def test_long_running_actions_release_flags_in_finally():
    source = FRONTEND_MAIN.read_text(encoding="utf-8")
    for function_name, setter in [
        ("runStage", "setStageRunning(false)"),
        ("runChapterOutlineVolume", "setChapterOutlineRunning(false)"),
        ("generateBatch", "setChapterBatchRunning(false)"),
        ("runOutlineReview", "setOutlineReviewRunning(false)"),
        ("applyOutlineReview", "setOutlineReviewApplying(false)"),
        ("runChapterOutlineReview", "setChapterOutlineReviewRunning(false)"),
        ("applyChapterOutlineReview", "setChapterOutlineReviewApplying(false)"),
        ("reviewAll", "setReviewRunning(false)"),
        ("applyRepair", "setApplyingChapter(null)"),
    ]:
        block = extract_function_block(source, function_name)
        assert "catch (error)" in block
        assert "showError(error)" in block
        assert "finally" in block
        assert setter in block
```

- [ ] **Step 2: Run source guard**

Run:

```bash
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py::test_long_running_actions_release_flags_in_finally -q
```

Expected: pass if current handlers are consistent; fail and identify missing guards otherwise.

- [ ] **Step 3: Fix missing frontend guards**

For any failing action in `web/frontend/src/main.tsx`, wrap streaming or mutating work like this:

```tsx
setSomeRunning(true);
try {
  await streamAction(path, payload, (line) => pushLog(line));
} catch (error) {
  showError(error);
} finally {
  setSomeRunning(false);
}
```

For background refresh after successful streams, use:

```tsx
try {
  await refreshSomething();
} catch (refreshError) {
  showBackgroundError(refreshError);
}
```

- [ ] **Step 4: Add SSE route error regression if missing**

Ensure `tests/test_web_app.py` has a regression where a streaming route service raises and the response contains `event: error`. If absent, add:

```python
def test_sse_streaming_route_returns_error_event(monkeypatch, tmp_path):
    app = web_app.make_app(Settings(projects_dir=tmp_path), mock=True)
    client = TestClient(app)

    def fail(*args, **kwargs):
        raise LocalStoreError("boom")

    monkeypatch.setattr(web_app.outline_actions, "generate_outline_stage", fail)
    response = client.post("/api/projects/missing/outline/stages/direction/generate", json={})

    assert response.status_code == 200
    assert "event: error" in response.text
    assert "boom" in response.text
```

- [ ] **Step 5: Run frontend and app tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py tests/test_web_app.py -q
npm --prefix web/frontend run build
```

Expected: pytest passes and Vite build passes with at most the known Vite CJS Node API deprecation warning.

- [ ] **Step 6: Commit**

Run:

```bash
git add web/frontend/src/main.tsx tests/test_frontend_review_tabs_structure.py src/ai_novelist/web/app.py tests/test_web_app.py
git commit -m "fix: verify long running web action guards"
```

## Task 9: Documentation And Verification Record

**Files:**
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`
- Modify: `docs/web_only_reference_matrix.md`

- [ ] **Step 1: Update implementation plan**

Append to `docs/IMPLEMENTATION_PLAN.md` under maintenance notes:

```markdown
## Web Prompt Context Prune Audit Notes

- 2026-05-29: Added a prompt registry guard so prompt files must be explicitly retained and stale prompt policy names cannot survive silently.
- 2026-05-29: Pruned legacy non-Web agent branches from mock and DeepSeek adapter handling.
- 2026-05-29: Removed unreachable old Director/show/status outline helpers after confirming active Web routes call explicit outline actions.
- 2026-05-29: Verified long-running Web action error handling and outline-to-body chapter context manifests.
```

- [ ] **Step 2: Update session summary**

Append to `docs/SESSION_SUMMARY.md`:

```markdown
## Web Prompt Context Prune Audit Completion

- Files changed: prompt registry/loading, adapter branch handling, outline helper pruning, Web route/action tests, context tests, and docs.
- Behavior changed: prompt loading is registry-gated; unused old prompt/agent branches are removed; Web-only active paths are the retained boundary.
- Verification: record exact command output from focused pytest runs, frontend build, and full pytest if run.
- Remaining risk: record any retained compatibility fields or prompt files that are still active and why.
```

- [ ] **Step 3: Update reference matrix final decisions**

In `docs/web_only_reference_matrix.md`, update rows for `src/ai_novelist/prompts/*.md`, `review_lock`, `state.py` Director/research fields, and `web/service.py` with the final retained/deleted decision from the implementation.

- [ ] **Step 4: Run final verification**

Run:

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py tests/test_mock_codex_adapter.py tests/test_deepseek_adapter.py -q
.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_web_chapter_service.py tests/test_web_outline_service.py -q
.venv/bin/python -m pytest tests/test_context_builder.py tests/test_graph_volume_write.py tests/test_workflow_payloads.py -q
npm --prefix web/frontend run build
```

If prompt registry, graph contracts, state fields, persistence, or shared context changed, also run:

```bash
.venv/bin/python -m pytest -q
```

Expected: all tests pass; frontend build passes with at most known Vite warning.

- [ ] **Step 5: Commit docs and verification**

Run:

```bash
git add docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md docs/web_only_reference_matrix.md
git commit -m "docs: record prompt context prune verification"
```

## Task 10: Completion Audit

**Files:**
- Read-only: all modified files

- [ ] **Step 1: Check legacy branch residue**

Run:

```bash
rg -n "load_prompt\\(\"director\"\\)|AGENT: director|retrieval_context_synthesizer|direction_proposer|continuity_editor|structure_editor|character_arc_editor|style_editor|simulated_reader|pacing_guard_editor|revision_planner|targeted_reviser|revision_self_check|chapter_summarizer|final_bible_update_extractor" src tests
```

Expected: no matches except names intentionally documented in deletion tests or historical docs. If there are source matches, either delete them or document why they are retained and add active-path tests.

- [ ] **Step 2: Check prompt registry**

Run:

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py -q
```

Expected: pass.

- [ ] **Step 3: Check working tree**

Run:

```bash
git status --short
git log --oneline -8
```

Expected: clean working tree and recent commits correspond to each completed task.

- [ ] **Step 4: Report final evidence**

Summarize:

- deleted prompt files and branch groups
- retained prompt groups
- Web logic bugs found and fixed
- context consistency evidence
- exact verification commands and pass counts
- remaining risk

Do not mark the thread goal complete unless this audit proves all spec success criteria.
