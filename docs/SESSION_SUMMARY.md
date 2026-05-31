# Session Summary

Updated: 2026-05-31
Project path: `/home/ubuntu/1.project/ai-novelist`

## Current Goal

AI Novelist is being maintained as a Web-only local application. The active runtime command is:

```bash
.venv/bin/ai-novelist web
```

The current cleanup effort aligns active docs and low-risk repository hygiene with that runtime boundary.

## Current Product Surface

Retained:

- local FastAPI Web API
- Vite/React frontend
- file-backed `projects/<project>/` storage
- outline stage generation, revision, save, pending-question submission, and lock
- outline review and explicit apply
- chapter-outline volume workspace
- chapter batch generation
- global chapter review and selected repair application
- Codex CLI, DeepSeek, and mock adapter paths used by Web

Removed from active CLI:

- chat-centric conversation command
- compose command
- feishu command
- research-only command
- one-off writer/review/finalize/export/show commands

## 2026-05-31 Web Frontend Loading Fix

- Investigation found the Web process and API were healthy: `/`, `/api/projects`, project state, outline stages, chapter workspace, and chapter-outline workspace all returned successfully from `127.0.0.1:8000`.
- nginx access logs for the reported browser session showed only `/` and `/assets/index-C0yUo9mO.js`, with no `/api/projects` request. The user agent was Chrome 83, while Vite 5 defaults production builds to `chrome87`.
- `web/frontend/vite.config.ts` now sets `build.target` to `chrome80`, and `tests/test_frontend_review_tabs_structure.py` includes a source regression guard for that target.
- Verification: the new regression test failed before the config change, then passed after it; `tests/test_frontend_review_tabs_structure.py` passed with 38 tests; `npm --prefix web/frontend run build` passed and regenerated the served frontend assets with the known Vite CJS deprecation warning.
- Remaining risk: no live Chrome 83 browser automation is installed in this checkout, so browser confirmation still depends on a hard refresh in the affected client.

## Latest Audit Results

Design spec committed:

- `ffb0fab docs: add web-only architecture audit design`
- `docs/superpowers/specs/2026-05-28-web-only-architecture-audit-design.md`

Key findings:

- The app was healthy under tests and frontend build at audit time.
- Active docs contained stale command examples for removed CLI flows; this cleanup batch rewrote the active docs for Web-only usage.
- `.superpowers/` appeared as an untracked local artifact directory; this cleanup batch added ignore coverage.
- DeepSeek default references were inconsistent between code/docs/script; this cleanup batch aligned the script default and added a drift guard.
- `graph_outline.py`, `web/service.py`, `web/frontend/src/main.tsx`, `adapters/codex_cli.py`, and `tests/test_web_service.py` remain maintenance hotspots.
- Some modules and prompts remain pruning candidates, but dynamic prompt loading and persisted project compatibility require future verified deletion work.

## Verification Recorded During Audit

```bash
.venv/bin/python -m pytest -q
# 225 passed in 2.11s
```

```bash
npm --prefix web/frontend run build
# passed; Vite printed the known CJS Node API deprecation warning
```

```bash
.venv/bin/ai-novelist --help
# only exposes {web}
```

Removed chat command check: invalid choice, proving the chat command is no longer active.

## Verification Recorded After Cleanup

```bash
.venv/bin/ai-novelist --help
# only exposes {web}
```

Removed chat command check: invalid choice, confirming the removed chat subcommand remains inactive.

Active-doc deleted command scan over README, implementation plan, and session summary returned no matches.

```bash
.venv/bin/python -m pytest tests/test_web_runtime_defaults.py -q
# 1 passed in 0.02s
```

```bash
.venv/bin/python -m pytest -q
# 226 passed in 2.15s
```

```bash
npm --prefix web/frontend run build
# passed; Vite printed the known CJS Node API deprecation warning
```

```bash
git status --short
# clean
```

```bash
git check-ignore -v .superpowers
# .gitignore:16:.superpowers/ .superpowers
```

## Web Prompt Context Prune Audit Progress

- Prompt registry cleanup added a retained Web prompt manifest, loader gating, orphan detection, inline-agent separation, and author-craft policy consistency checks. Verification: `.venv/bin/python -m pytest tests/test_prompt_loader.py -q` passed with 12 tests.
- Prompt/branch evidence was recorded in `docs/web_only_reference_matrix.md`; strict Web-only pruning remains the rule for unused prompts and unreachable branches.
- Legacy mock adapter branches were removed for deleted non-Web agents, stale DeepSeek categories were pruned including `retrieval_context_synthesizer`, and deleted first-line mock agents are denied before body substring routing. Active retained mock fallback is preserved for Web mock mode. Verification: `.venv/bin/python -m pytest tests/test_mock_codex_adapter.py tests/test_deepseek_adapter.py -q` and `.venv/bin/python -m pytest tests/test_web_service.py -q` passed during Task 3 review.
- Unreachable outline Director prompt/parser helpers, show/status nodes, and Director-only routing helpers were removed from the active graph surface. Verification: `.venv/bin/python -m pytest tests/test_outline_graph_modules.py tests/test_web_outline_service.py tests/test_web_service.py::test_outline_stage_list_hides_review_lock -q` passed during Task 4 review.
- Final completion audit also removed the remaining legacy outline stage view node and view-request routing helpers; deletion guards now cover those names. Verification: `.venv/bin/python -m pytest tests/test_outline_graph_modules.py tests/test_web_outline_service.py tests/test_web_service.py::test_outline_stage_list_hides_review_lock -q` passed with 11 tests.
- Web service facade prune is complete for FastAPI routes: routes now import focused modules directly, and `web/service.py` is compatibility-only.
- Chapter-outline/body context consistency has focused coverage for missing and present chapter slices across direct drafting, volume batch generation, and Arabic/Chinese Markdown/plain headings.
- Remaining risk: no live Codex drafting run or browser-level interaction run was performed in this batch; verification is focused unit/API/frontend build coverage.

## Web Prompt Context Prune Audit Completion

- Files changed: prompt registry/loading, mock and DeepSeek adapter branch handling, outline graph helper pruning, focused Web route/action boundaries, chapter-outline review apply persistence, chapter context slice extraction, frontend/Web SSE guard tests, and docs.
- Behavior changed: prompt loading is registry-gated; old non-Web agent branches and unreachable outline Director helpers are removed; FastAPI routes call focused Web modules directly; chapter-outline review apply state is persisted; chapter drafting context now rejects missing or adjacent outline slices explicitly.
- Verification: final Task 9 commands passed: `.venv/bin/python -m pytest tests/test_prompt_loader.py tests/test_mock_codex_adapter.py tests/test_deepseek_adapter.py -q` -> 29 passed in 0.11s; `.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_web_chapter_service.py tests/test_web_outline_service.py -q` -> 96 passed in 1.23s; `.venv/bin/python -m pytest tests/test_context_builder.py tests/test_graph_volume_write.py tests/test_workflow_payloads.py -q` -> 30 passed in 0.73s; `npm --prefix web/frontend run build` passed with the known Vite CJS Node API deprecation warning; `.venv/bin/python -m pytest -q` -> 305 passed in 2.39s.
- Remaining risk: `NovelState` Director/research fields and `review_lock` compatibility remain intentionally retained for active graph state and old project compatibility; `web/service.py` remains compatibility-only until remaining tests stop importing it; no live Codex/DeepSeek generation run was performed.

## Completed in This Cleanup Batch

Implementation plan:

- `docs/superpowers/plans/2026-05-28-web-only-architecture-cleanup.md`

Completed implementation commits before this final verification record:

- `25bc6bf` ignored local `.superpowers/` artifacts in `.gitignore`.
- `56999de` aligned `scripts/run_web.sh` with the configured DeepSeek default and added the initial runtime default guard.
- `07deb4a` isolated `tests/test_web_runtime_defaults.py` from unrelated environment variables.
- `cc60773` rewrote `README.md` for the Web-only command surface.
- `34702ed` rewrote `docs/IMPLEMENTATION_PLAN.md` for the current Web-only architecture and roadmap.
- `314e5dd` created `docs/web_only_reference_matrix.md` for future verified pruning decisions.
- `870b14f` rewrote `docs/SESSION_SUMMARY.md` from stale historical notes to the current Web-only summary.
- `f33a34d` clarified completed cleanup work versus deferred future work in `docs/SESSION_SUMMARY.md`.

## Planned Follow-Up Work

- P1 verified prune is planned in `docs/superpowers/plans/2026-05-28-web-only-verified-prune.md`.
- P2 structural refactor is planned in `docs/superpowers/plans/2026-05-28-web-structural-refactor.md`.
- No P1/P2 runtime code has been changed after the cleanup verification record yet.

## P1 Verified Prune Progress

- Confirmed local `__pycache__` directories are not tracked by Git; no repository deletion is needed.
- Removed `src/ai_novelist/output_contracts.py` and `tests/test_output_contracts.py` after confirming the module had no runtime imports.
- Verified output-contract removal with `tests/test_web_service.py tests/test_graph_volume_write.py`: 73 passed in 0.93s.
- Verified output-contract removal with full pytest: 223 passed in 2.03s.
- Retained `src/ai_novelist/corpus/project_memory.py` because Author Craft query and retrieval paths still reference project craft memory artifacts; focused craft tests passed: 5 passed in 0.10s.
- Retained Director/research fields in `NovelState`; active Web/graph paths still use them, and old-state compatibility coverage was added; `tests/test_state.py` passed: 2 passed in 0.03s.
- Kept prompt deletion blocked: dynamic `load_prompt(prompt_name)` remains in active graph paths, so prompt pruning needs a manifest or explicit registry test first.
- Completed P1 verified-prune batch verification with full pytest: 224 passed in 2.02s. Frontend build was not required because this batch did not change Web payloads or frontend files.

## P2 Structural Refactor Progress

- Split deterministic mock behavior from `CodexCLIAdapter` into `src/ai_novelist/adapters/mock_codex.py`; `CodexCLIAdapter(mock=True)` now delegates to `MockCodexAdapter` for compatibility. Focused adapter tests passed: 8 passed in 0.06s; full pytest passed: 226 passed in 2.28s.
- Extracted Web agent-output JSON parsing into `src/ai_novelist/web/json_utils.py`; focused Web tests passed: 72 passed in 0.56s; full pytest passed: 228 passed in 2.04s.
- Extracted outline stage, pending-question, and outline review helpers into `src/ai_novelist/web/outline_service.py`; focused outline/Web service tests passed: 71 passed in 0.53s; full pytest passed: 229 passed in 1.99s.
- Extracted chapter review source/prompt helpers into `src/ai_novelist/web/chapter_service.py`; focused chapter/Web service tests passed: 71 passed in 0.47s; full pytest passed: 230 passed in 2.04s.
- Extracted frontend shared types and fetch helpers into `web/frontend/src/types.ts` and `web/frontend/src/api.ts`; frontend build passed with the known Vite CJS Node API deprecation warning; frontend structure tests were updated for the split and passed: 21 passed in 0.11s.
- Final P2 verification passed: full pytest 230 passed in 2.02s; frontend build passed with the known Vite CJS Node API deprecation warning. Hotspot sizes after refactor: `web/service.py` 1477 lines, `adapters/codex_cli.py` 106 lines, `web/frontend/src/main.tsx` 1294 lines, `tests/test_web_service.py` unchanged at 1491 lines.

## Architecture Web Context Remediation Progress

### Phase 1: Web Operation Logic

- Files changed: `web/frontend/src/main.tsx`, `tests/test_frontend_review_tabs_structure.py`, `docs/IMPLEMENTATION_PLAN.md`, and `docs/SESSION_SUMMARY.md`.
- Behavior changed: new project progress log writes target the newly created project id; chapter detail loading resets through a current-request `finally` guard; chapter batch generation has a running guard, disabled/running button state, error reporting, and `finally` cleanup.
- Verification: selected RED regression run first failed as expected with 4 frontend source assertions failing; `.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py -q` passed with 25 passed in 0.05s; `npm --prefix web/frontend run build` passed with the known Vite CJS Node API deprecation warning.
- Remaining risk: browser-level click concurrency and request-race behavior is still represented by source-level assertions and TypeScript/build verification, not Playwright interaction coverage.
- Next entry point: continue with SSE and Web route error behavior tests in Task 2.
- Continuation note: resume at Task 2 in `docs/superpowers/plans/2026-05-29-architecture-web-context-remediation.md`; do not revisit Task 1 unless its focused tests fail.

### Phase 1b: SSE and Web Error Handling

- Files changed: frontend action handlers, Web app tests, docs.
- Behavior changed: streaming Web actions report errors consistently and release running flags through `finally`; SSE service failures are represented as `event: error`.
- Verification: RED selected run failed before implementation with 1 failed, 2 passed; focused 3-test run passed with 3 passed in 0.37s; broader `.venv/bin/python -m pytest tests/test_web_app.py tests/test_frontend_review_tabs_structure.py -q` passed with 37 passed in 0.81s; `npm --prefix web/frontend run build` passed with the known Vite CJS Node API deprecation warning.
- Remaining risk: source tests verify handler structure; browser event-loop behavior is still covered indirectly.
- Next entry point: begin Task 3 context manifest and deduplication work.
- Continuation note: resume with context builder tests in Task 3; Web operation guard changes are complete when both focused commands above pass.

### Phase 2: Context Manifest Paths and Deduplication

- Files changed: `src/ai_novelist/context_builder.py`, `tests/test_context_builder.py`, docs.
- Behavior changed: context manifests now expose artifact paths and source types; repeated artifact/state fallback content is deduplicated by digest.
- Verification: `.venv/bin/python -m pytest tests/test_context_builder.py -q` passed with 9 passed in 0.11s.
- Remaining risk: direct chapter writing still uses its own context assembler until Task 4.
- Next entry point: migrate direct chapter context to `ContextBundle`.
- Continuation note: resume at Task 4; keep Task 3 helper names unchanged because later tasks use `SectionRecord` and `build_artifact_section_records`.

#### Task 3 Quality Fix

- Fixed context digest dedupe so protected sections (`用户当前请求`, `当前任务`, `锁定约束`) are always retained and their content suppresses duplicate unprotected sections.
- Fixed final context cap handling so protected section headers remain present under tight budgets; unprotected overflow is dropped or reduced before protected content is truncated.

#### Task 3 Final Quality Fix

- Routed `bible_update` through a protected-aware context profile instead of the legacy truncation path.
- Preserved dropped unprotected sections in context source metadata with `included_chars=0` and `truncated=True` so omitted content marks the bundle as truncated.
- Verification: `.venv/bin/python -m pytest tests/test_context_builder.py -q` passed with 15 passed in 0.10s.


### Phase 2b: Direct Chapter Context Migration

- Files changed: context builder, direct chapter write graph, volume write graph tests, docs.
- Behavior changed: direct chapter drafting uses the shared context profile and records a context manifest.
- Verification: `.venv/bin/python -m pytest tests/test_context_builder.py tests/test_graph_volume_write.py -q` passed with 20 passed in 0.66s.
- Remaining risk: other workflows still read some payload values directly from `director_task_args`.
- Next entry point: introduce workflow payload helpers in Task 5.
- Continuation note: resume at Task 5; direct drafting context should remain profile name `direct_chapter_drafting`.


#### Task 4 Quality Fix

- Fixed volume writes so `batch_context_manifests` remains the durable per-chapter manifest map, while `direct_chapter_context_manifest` is exposed only for single-chapter compatibility and includes `direct_chapter_context_manifest_chapter`.
- Batch manifest JSON now includes `context_manifests` keyed by chapter in deterministic order.
- Verification: `.venv/bin/python -m pytest tests/test_graph_volume_write.py tests/test_context_builder.py -q` passed with 22 passed in 0.80s.


### Phase 3: Workflow Payload Helpers

- Files changed: `src/ai_novelist/workflow_payloads.py`, chapter workflow entry points, Web batch generation, tests, docs.
- Behavior changed: high-risk chapter and batch payload reads/writes use named helpers while preserving `director_task_args` persistence compatibility.
- Verification: `.venv/bin/python -m pytest tests/test_workflow_payloads.py tests/test_graph_volume_write.py tests/test_web_service.py::test_chapter_batch_payload_sets_director_task_args -q` passed with 9 passed in 0.71s.
- Remaining risk: outline and Craft payload keys still have raw reads until later graph/service extraction tasks.
- Next entry point: split Web service modules behind compatibility imports.
- Continuation note: resume at Task 6; keep `workflow_payloads.py` helper names stable for later replacements.

### Phase 4a: Project Service Split

- Files changed: `src/ai_novelist/web/project_service.py`, `src/ai_novelist/web/service.py`, Web tests, docs.
- Behavior changed: project and progress logic moved behind a focused service module; `web/service.py` remains a compatibility facade.
- Verification: `.venv/bin/python -m pytest tests/test_web_service.py::test_project_service_exports_project_and_progress_helpers tests/test_web_service.py::test_project_progress_log_accepts_legacy_strings_and_structured_events tests/test_web_app.py::test_project_idea_and_progress_log_endpoints_are_project_scoped -q` passed with 3 passed in 0.39s.
- Remaining risk: outline, chapter, and review functions still live in `web/service.py`.
- Next entry point: split outline actions.
- Continuation note: resume at Task 7; project/progress imports should come from `ai_novelist.web.project_service` for new code.


### Phase 4b: Outline Web Action Split

- Files changed: outline/chapter outline Web action modules, service facade, Web tests, docs.
- Behavior changed: ordinary outline and chapter outline Web actions now live in focused modules while route behavior remains stable.
- Verification: `.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py -q`.
- Remaining risk: chapter list/batch/review/repair actions still need extraction.
- Next entry point: split chapter and review Web actions.
- Continuation note: resume at Task 8; keep `web/service.py` as a compatibility facade until all route call sites are stable.

### Phase 4c: Chapter and Review Web Action Split
- Files changed: chapter/review Web action modules, service facade, Web tests, docs.
- Behavior changed: chapter batch/list/detail and review/repair logic now live in focused modules while public route behavior remains stable.
- Verification: `.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_chapter_service.py tests/test_web_app.py -q` passed with 84 passed in 1.16s; line-count proof: parent `1645404^` `web/service.py` was 758 lines, current `wc -l` reports 136 `service.py`, 286 `chapter_actions.py`, 430 `review_actions.py`, 852 total.
- Remaining risk: FastAPI routes still call through the facade in places where direct module imports can be cleaned later.
- Next entry point: split outline graph helpers.
- Continuation note: resume at Task 9; keep route behavior unchanged and avoid deleting facade exports until final full tests pass.

### Task 5: Direct Web Route Imports and Facade Prune

- Files changed: `src/ai_novelist/web/app.py`, `src/ai_novelist/web/service.py`, Web app/service tests, docs.
- Behavior changed: FastAPI routes now call `project_service`, `outline_service`, `outline_actions`, `chapter_outline_actions`, `chapter_actions`, and `review_actions` directly; `web/service.py` no longer re-exports action functions.
- Verification: RED run `.venv/bin/python -m pytest tests/test_web_app.py::test_web_app_imports_focused_action_modules_not_service_facade tests/test_web_service.py::test_project_service_exports_project_and_progress_helpers -q` failed as expected with the app import guard; green run `.venv/bin/python -m pytest tests/test_web_app.py tests/test_web_service.py -q` passed with 90 passed in 1.47s.
- Facade scan: requested `rg -n "web import service|web\.service|service\." src tests` was run after edits; it reports the import-guard test plus `_service` module-name false positives such as `project_service` and `outline_service`, with no route facade imports. A precise facade scan with `rg -n "from ai_novelist\.web import service|web\.service|\bservice\." src tests` reports only the import-guard assertion.
- Remaining risk: `tests/test_web_service.py` still groups many focused-module integration checks in one file.

### Phase 5a: Outline Graph Routing and Review Lock Split
- Files changed: `src/ai_novelist/outline_graph/routing.py`, `src/ai_novelist/outline_graph/review_lock.py`, `graph_outline.py`, tests, docs.
- Behavior changed: routing and review-lock helpers moved out of the main outline graph, with small compatibility expansions for bare `BLOCKING:` / `DETAIL:` review-lock labels and Chinese `锁定` lock requests.
- Verification: `.venv/bin/python -m pytest tests/test_outline_graph_modules.py tests/test_web_outline_service.py tests/test_web_service.py::test_outline_stage_list_hides_review_lock -q` passed with 4 passed in 0.15s.
- Remaining risk: prompt builders and structure repair helpers still remain in `graph_outline.py`.
- Next entry point: extract prompt and repair helpers.
- Continuation note: resume at Task 10; keep helper function names exported because tests and `graph_outline.py` import them directly.

### Phase 5b: Outline Graph Prompt and Repair Split
- Files changed: prompt, repair, artifact IO helper modules, `graph_outline.py`, tests, docs.
- Behavior changed: prompt building, structure repair, and artifact formatting helpers moved out of `graph_outline.py` with route and graph entry points preserved.
- Verification: `.venv/bin/python -m pytest tests/test_outline_graph_modules.py tests/test_web_outline_service.py tests/test_web_service.py -q` -> passed with 81 passed in 0.56s; `wc -l` confirms phase-local `graph_outline.py` shrinkage (`graph_outline.py` from parent commit 2637 to 1719 lines; current module line counts: `prompts.py` 358, `repair.py` 415, `artifact_io.py` 315; total 2807).
- Regression coverage: `tests/test_outline_graph_modules.py` now smokes remaining `graph_outline.py` runtime references to moved prompt helpers, stage output rules, and chapter volume helper globals.
- Remaining risk: additional graph-node extraction can continue later, but this phase removes the largest helper clusters.
- Next entry point: frontend structural split.
- Continuation note: resume at Task 11; do not move graph node functions until frontend and full verification are stable.
- Implementation note: the initially requested prompt-helper test strings did not match existing production wording, so assertions were adjusted to the current stage-specific text while preserving production behavior.

### Phase 6: Frontend Workspace Split
- Files changed: frontend progress utility, workspace components, `main.tsx`, frontend structure tests, docs.
- Behavior changed: frontend UI is split into focused modules while existing tabs, actions, progress log, and review workspaces remain compatible.
- Verification: `.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py -q` -> passed with 29 passed in 0.05s; `npm --prefix web/frontend run build` -> passed with the known Vite CJS Node API deprecation warning; `main.tsx` is 799 lines (<900).
- Remaining risk: action handlers still live in `main.tsx`; a future phase can split hooks once component boundaries settle.
- Next entry point: final verification and cleanup.
- Continuation note: resume at Task 12; frontend split is accepted only when `main.tsx` is below 900 lines and build passes.

### Final Verification: Architecture Web Context Remediation
- Files changed: Web frontend, Web services, context builder, workflow payload helpers, outline graph helpers, tests, docs.
- Behavior changed: Web operations have stronger guards and error reporting; context is traceable and deduplicated; large modules are split into focused helper modules while public Web routes remain stable.
- Verification: `.venv/bin/python -m pytest -q` -> 263 passed in 2.28s; `npm --prefix web/frontend run build` -> passed with the known Vite CJS Node API deprecation warning; residual `rg` architecture scan was rerun excluding `web/frontend/node_modules/**` and `web/frontend/dist/**`; file-size scan reports `graph_outline.py` 1719 lines, `web/service.py` 136 lines, `main.tsx` 799 lines, `context_builder.py` 796 lines.
- Residual scan notes: no frontend source `localStorage` hit remains and the old chapter-batch disabled expression is absent; remaining `director_task_args` hits are compatibility debt in graph/corpus/context paths plus documented plan snippets.
- Remaining risk: any retained `director_task_args` access is compatibility debt and should be handled with targeted payload helpers in future work; source/build tests do not replace browser-level click coverage.
- Next recommended work: add browser-level interaction tests if a real UI runtime issue appears after these source and service-level guards.
- Continuation note: this remediation batch is complete when full pytest, frontend build, and residual scans match the recorded outputs.

### Follow-up: Onboarding Instruction and Progress Noise Guard
- Files changed: `web/frontend/src/main.tsx`, `tests/test_frontend_review_tabs_structure.py`, and docs.
- Behavior changed: saving the initial novel idea no longer copies the idea into the outline-stage instruction input; transient browser `Failed to fetch` errors from background project/stage/chapter refreshes are ignored instead of being persisted to the project progress log.
- Verification: targeted RED runs first failed for the current code (`setInstruction('')` absent; `showBackgroundError` absent); focused regression tests passed with `.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py::test_onboarding_save_does_not_prefill_outline_instruction tests/test_frontend_review_tabs_structure.py::test_background_transient_fetch_errors_are_not_persisted_to_progress_log -q` -> 2 passed in 0.04s; broader frontend structure suite passed with 31 passed in 0.06s; `npm --prefix web/frontend run build` passed with the known Vite CJS Node API deprecation warning.
- Remaining risk: coverage is source-structure plus TypeScript/build validation; no Playwright browser click test was added for the onboarding handoff.

### Follow-up: Progress Order and Model Metrics
- Files changed: `src/ai_novelist/web/project_service.py`, `web/frontend/src/types.ts`, `web/frontend/src/main.tsx`, `tests/test_web_service.py`, `tests/test_frontend_review_tabs_structure.py`, `docs/IMPLEMENTATION_PLAN.md`, `docs/SESSION_SUMMARY.md`, and `docs/superpowers/plans/2026-05-29-progress-order-and-model-metrics.md`.
- Behavior changed: the right-side progress panel now renders newest entries first while preserving the saved append order; structured progress rows display status, model, elapsed time, token estimate, and context usage; backend progress parsing preserves `model`, accepts both legacy `/` and current `|` metadata separators, and avoids treating context capacity as a model when no model is present.
- Verification: backend RED failed first for missing `model` persistence and missing pipe-separated elapsed parsing; frontend RED failed first for missing `visibleLog` and `item.model` rendering. Target verification passed with `.venv/bin/python -m pytest tests/test_web_service.py::test_project_progress_log_accepts_legacy_strings_and_structured_events tests/test_web_service.py::test_progress_event_drops_generated_message_body_but_retains_metrics tests/test_web_service.py::test_progress_event_includes_key_and_completion_metrics tests/test_web_service.py::test_progress_event_includes_model_and_elapsed_from_pipe_metadata tests/test_web_service.py::test_progress_event_without_model_does_not_use_context_capacity_as_model tests/test_frontend_review_tabs_structure.py::test_progress_panel_renders_structured_metrics_and_keeps_legacy_branch tests/test_frontend_review_tabs_structure.py::test_progress_panel_merges_rows_by_key_and_renders_completion_metrics -q` -> 7 passed in 0.14s; final affected-suite verification passed with `.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_frontend_review_tabs_structure.py -q` -> 116 passed in 1.25s; `npm --prefix web/frontend run build` passed with the known Vite CJS Node API deprecation warning.
- Remaining risk: this was not verified with a browser-level visual test; existing persisted structured rows that lack `model` remain readable and simply omit that field in the rendered metadata line.

### Follow-up: Outline Save Progress Completion
- Files changed: `src/ai_novelist/graph_outline.py`, `tests/test_web_service.py`, `docs/IMPLEMENTATION_PLAN.md`, `docs/SESSION_SUMMARY.md`, and `docs/superpowers/plans/2026-05-29-outline-save-progress-completion.md`.
- Behavior changed: outline-stage save progress now completes after artifact and state writes for full stage generation and light revision, so the right-side progress row does not stay `running` after a successful save.
- Evidence from the reported project: `projects/demo-web/outline/characters.md`, `projects/demo-web/outline_stages/characters.md`, `projects/demo-web/state.json`, and `projects/demo-web/artifacts.json` were already updated at 2026-05-29 13:33:26 +0800; the stale local `projects/demo-web/web_progress_log.json` row was updated from `running` to `completed` for refresh visibility and remains untracked generated data.
- Verification: targeted RED first failed because the save progress label was still `正在保存「人物关系」轻修订产物...` with `status=running`; after wrapping saves with `run_with_progress`, `.venv/bin/python -m pytest tests/test_web_service.py::test_revise_outline_stage_completes_save_progress -q` passed with 1 passed in 0.17s. Affected-suite verification passed with `.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_outline_graph_modules.py -q` -> 93 passed in 1.17s.
- Remaining risk: this was not exercised through a live browser stream; old generated project logs outside `demo-web` may still have stale rows until those projects receive a new progress update.

### Follow-up: Stage Refresh Fallback
- Files changed: `web/frontend/src/main.tsx`, `tests/test_frontend_review_tabs_structure.py`, `docs/IMPLEMENTATION_PLAN.md`, `docs/SESSION_SUMMARY.md`, and `docs/superpowers/plans/2026-05-29-stage-refresh-fallback.md`.
- Behavior changed: outline-stage refreshes preserve the current editor content until a new payload arrives, and successful generation streams no longer persist transient post-stream `Failed to fetch` refresh errors into the progress log.
- Evidence from `demo-web`: `outline/volume_outline.md` and `outline_stages/volume_outline.md` both contain the generated 分卷大纲, and the Web service payload returns `status=options_ready` with non-empty content; the visible empty editor was caused by frontend pre-refresh clearing plus a transient refresh fetch failure. The stale generated `projects/demo-web/web_progress_log.json` `error: Failed to fetch` row was removed locally.
- Verification: targeted RED first failed for pre-request `setContent('')` and missing `showBackgroundError(refreshError)` in `runStage()`; after the fix, `.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py::test_stage_load_preserves_existing_content_while_refreshing tests/test_frontend_review_tabs_structure.py::test_run_stage_does_not_log_transient_post_stream_refresh_failure -q` passed with 2 passed in 0.02s. Broader frontend structure suite passed with 33 passed in 0.17s; `npm --prefix web/frontend run build` passed with the known Vite CJS Node API deprecation warning.
- Remaining risk: no live browser network interruption test was added; old generated logs in projects other than `demo-web` may still contain historical `error: Failed to fetch` rows.

### Follow-up: Outline Review Apply Completion
- Files changed: `src/ai_novelist/web/outline_service.py`, `src/ai_novelist/web/outline_actions.py`, `web/frontend/src/types.ts`, `web/frontend/src/main.tsx`, `web/frontend/src/workspaces/review.tsx`, `web/frontend/src/styles.css`, tests, docs, and `docs/superpowers/plans/2026-05-29-outline-review-apply-completion.md`.
- Behavior changed: outline overall-review apply now marks the persisted review report as applied, duplicate apply requests for the same run return idempotent success without rerunning revision, concurrent duplicate apply requests for the same project/run are serialized by a process-local lock, and the frontend stays on the "大纲总体审查" view with an applying spinner followed by "采纳完成".
- Verification: targeted RED tests failed before implementation for missing applied report state and review-page completion UI; final-review RED concurrency test failed with `assert 2 == 1` for duplicate reviser calls before the lock; focused server-side duplicate-apply tests passed with `.venv/bin/python -m pytest tests/test_web_service.py::test_apply_outline_review_concurrent_duplicate_waits_for_applied_report tests/test_web_service.py::test_apply_outline_review_is_idempotent_after_report_applied tests/test_web_service.py::test_outline_review_apply_marks_latest_report_applied -q`; final affected-suite verification passed with `.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_frontend_review_tabs_structure.py -q` -> 125 passed in 1.33s; full pytest passed with `.venv/bin/python -m pytest -q` -> 276 passed in 2.30s; frontend build passed with `npm --prefix web/frontend run build` and the known Vite CJS Node API deprecation warning.
- Remaining risk: no live browser/SSE click test was added; source-structure tests verify the state handling and TypeScript build verifies the component compiles.


### Task 6: Chapter-Outline Review Apply Persistence
- Files changed: `src/ai_novelist/web/chapter_outline_actions.py`, `tests/test_web_service.py`, `docs/IMPLEMENTATION_PLAN.md`, and `docs/SESSION_SUMMARY.md`.
- Behavior changed: chapter-outline review apply persists `status=applied`, `applied=true`, `applied_at`, and `applied_path` to the saved report JSON/Markdown; duplicate apply calls for already-applied reports return success without invoking model work; revised `chapter_outline` synthesis is saved back to the artifact and outline-stage mirror.
- Verification: RED run `.venv/bin/python -m pytest tests/test_web_service.py::test_apply_chapter_outline_review_marks_report_applied_and_updates_artifact -q` first failed with `assert 'reviewed' == 'applied'`; follow-up status-only idempotency coverage passed without production changes, proving `status=applied` alone skips model work; focused green Task 6 run passed with 4 tests.
- Remaining risk: no live browser-level apply flow was exercised; concurrency serialization was not added for chapter-outline apply because this task only required already-applied idempotency.

## Web Prompt Context Prune Audit

- Task 1 from commit `a4c73a5` added `src/ai_novelist/prompts/registry.py`, gated `load_prompt()` through the registry, trimmed stale `AUTHOR_CRAFT_POLICY_PROMPTS` entries, and added prompt registry guard tests.
- Task 1 focused verification: `.venv/bin/python -m pytest tests/test_prompt_loader.py -q` -> 12 passed.
- Added a manifest-backed prompt registry plan and started strict Web-only pruning.
- Current rule: prompts and branches are retained only when reachable from active Web routes, retained graph nodes, prompt loading, adapter execution, or active Web behavior tests.
- Compatibility with old deleted CLI flows is no longer a default retention reason for this cleanup batch.

## Remaining Risk

One verified dead module has been removed. The main remaining risk is stale compatibility code that appears unused but may still be reached through dynamic prompt names, old project state, or retained Web workflow helpers.

Any pruning batch must update this summary with:

- files changed
- tests run
- residual compatibility risk
- whether frontend build was required

### Task 7: Chapter Batch Selection And Context Slice Proof
- Files changed: src/ai_novelist/context_builder.py, src/ai_novelist/outline/chapter_outline_structure.py, src/ai_novelist/graph_volume_write.py, src/ai_novelist/graph_chapter_write.py, tests/test_context_builder.py, tests/test_graph_volume_write.py, tests/test_graph_chapter_write.py, docs/IMPLEMENTATION_PLAN.md, and docs/SESSION_SUMMARY.md.
- Behavior changed: chapter outline slice context manifest entries now expose source_type=chapter_outline_slice; selected-volume chapter batching has regression coverage proving chapter 2 receives only chapter 2 outline slice and chapter 7 receives an explicit missing-slice fallback instead of adjacent chapter 6 or 8 outline text; direct chapter drafting and direct chapter write preparation have matching missing-slice coverage; Chinese-number headings such as 第七章, including plain non-Markdown chapter lines, are now sliced without including adjacent 第六章 or 第八章 content.
- Verification: focused RED run first failed because batch_context_manifests did not contain chapter_outline_slice; follow-up RED reproduced adjacent chapter 6/8 outline leakage for missing direct chapter 7; second follow-up RED reproduced the same leakage in volume batch chapter 7 seeding; final follow-up RED reproduced direct chapter write chapter 7 seeding leakage; after the manifest source tagging, all missing-slice fallback fixes, and the shared Chinese-number and plain-heading extractor fixes, focused tests passed. Final affected-suite verification: .venv/bin/python -m pytest tests/test_context_builder.py tests/test_graph_volume_write.py tests/test_graph_chapter_write.py tests/test_chapter_outline_structure.py -q passed with 35 passed in 0.79s; git diff --check passed with no output.
- Remaining risk: no real Codex batch drafting was run; this verifies context assembly and manifest contracts only.

### Task 8: Web Long-Running Action Guard Audit
- Files changed: `tests/test_frontend_review_tabs_structure.py`, `tests/test_web_app.py`, `docs/IMPLEMENTATION_PLAN.md`, and `docs/SESSION_SUMMARY.md`.
- Behavior changed: added source guards proving long-running frontend actions catch errors, call `showError(error)`, and release their running/applying flags in `finally`; added a streaming-route exception regression proving SSE failures return `event: error` with the exception message. No changes were needed in `web/frontend/src/main.tsx` or `src/ai_novelist/web/app.py`.
- Verification: focused frontend guard `.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py::test_long_running_actions_release_flags_in_finally -q` passed with 1 passed in 0.16s; focused SSE regression `.venv/bin/python -m pytest tests/test_web_app.py::test_sse_streaming_route_returns_error_event -q` passed with 1 passed in 0.44s. Final requested verification passed with `.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py tests/test_web_app.py -q` -> 49 passed in 0.95s; `npm --prefix web/frontend run build` passed with the known Vite CJS Node API deprecation warning; `git diff --check` passed with no output.
- Remaining risk: this audit uses source-level guards and TestClient SSE checks, not browser-level interaction coverage.


### Follow-up: DeepSeek Runtime Environment Defaults
- Files changed: `src/ai_novelist/config.py`, `src/ai_novelist/adapters/deepseek.py`, `src/ai_novelist/progress.py`, `src/ai_novelist/web/app.py`, `src/ai_novelist/cli.py`, `scripts/run_web.sh`, tests, and docs. `~/.bashrc` was updated locally outside the repo with an AI Novelist DeepSeek block.
- Behavior changed: DeepSeek defaults to `deepseek-v4-flash`; enabled-thinking calls use `AI_NOVELIST_DEEPSEEK_REASONING_EFFORT` with default `low`; disabled-thinking calls remain disabled and omit `reasoning_effort`.
- Verification: RED target run first failed for the old `deepseek-v4-pro` default, missing `deepseek_reasoning_effort`, old `medium` payloads, and missing adapter constructor support. Focused green verification passed with `.venv/bin/python -m pytest tests/test_web_runtime_defaults.py tests/test_deepseek_adapter.py tests/test_progress.py tests/test_web_app.py::test_web_app_passes_deepseek_reasoning_effort_to_adapter -q` -> 19 passed in 0.45s. Final verification passed with `.venv/bin/python -m pytest tests/test_web_runtime_defaults.py tests/test_deepseek_adapter.py tests/test_progress.py tests/test_web_app.py -q` -> 31 passed in 0.81s, `git diff --check`, and `.venv/bin/python -m pytest -q` -> 309 passed in 2.53s.
- Remaining risk: no live DeepSeek API call was run; payload behavior is covered through adapter request capture tests.


### Follow-up: Inline Pending Lock Guard
- Files changed: `src/ai_novelist/web/outline_service.py`, `tests/test_web_service.py`, `docs/IMPLEMENTATION_PLAN.md`, and `docs/SESSION_SUMMARY.md`.
- Root cause: `projects/demo-web/outline_stages/direction.md` contained inline unresolved fields such as `读者预期：待确认`, `价值取向：待确认`, `内部冲突：待确认`, and `关系冲突：待确认`, but the explicit `仍需确认的问题` section said `暂无`; the Web lock guard only considered explicit pending sources, so it allowed locking.
- Behavior changed: pending collection now keeps artifact/state real questions authoritative and, when they are absent, scans stage Markdown body lines containing `待确认` outside the pending section; the resulting list feeds both the pending API and `can_lock`. On the current `demo-web` project, `direction` now reports `can_lock=False` with 5 pending items.
- Verification: RED `.venv/bin/python -m pytest tests/test_web_service.py::test_outline_stage_payload_blocks_lock_for_inline_pending_markers -q` first failed with `assert True is False`; after the fix it passed. Focused lock/pending verification passed with `.venv/bin/python -m pytest tests/test_web_service.py::test_outline_stage_payload_includes_action_state tests/test_web_service.py::test_outline_stage_payload_allows_lock_without_real_pending_questions tests/test_web_service.py::test_outline_stage_payload_blocks_lock_for_inline_pending_markers tests/test_web_service.py::test_extract_stage_pending_questions_from_markdown_filters_status_lines tests/test_web_service.py::test_lock_outline_stage_rejects_real_pending_questions tests/test_web_service.py::test_lock_outline_stage_stays_on_current_stage_without_auto_generation -q` -> 6 passed in 0.14s. Compatibility verification for artifact priority plus inline fallback passed with 2 passed in 0.16s; full Web service verification passed with `.venv/bin/python -m pytest tests/test_web_service.py -q` -> 83 passed in 0.60s. Final affected-suite verification passed with `.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py -q` -> 96 passed in 1.31s; `git diff --check`; full verification passed with `.venv/bin/python -m pytest -q` -> 310 passed in 2.52s.
- Remaining risk: no browser-level click test was run; coverage is backend payload/action behavior plus direct verification against the current local project files.


### Follow-up: Pending Feedback Loop Guard
- Files changed: `src/ai_novelist/web/outline_service.py`, `tests/test_web_service.py`, `docs/IMPLEMENTATION_PLAN.md`, and `docs/SESSION_SUMMARY.md`; ignored generated files `projects/demo-web/outline/worldbuilding.md` and `projects/demo-web/outline_stages/worldbuilding.md` were cleaned locally.
- Root cause: after inline `待确认` scanning was added, the scanner also read the generated `## 用户本轮反馈` block and submitted `问题：` / `答案：` lines. Re-submitting then fed those records back into the next revision, creating recursive pending items such as `问题：问题：答案：...`.
- Behavior changed: inline pending scanning skips feedback sections and submitted answer record lines while still detecting real unresolved body fields such as `主角重生的关键记忆节点：待确认`. On the current `demo-web` project, `worldbuilding` now reports `pending_count=0` and `can_lock=True` after cleaning the polluted feedback block.
- Verification: RED `.venv/bin/python -m pytest tests/test_web_service.py::test_collect_pending_questions_ignores_submitted_answer_feedback_block -q` first failed by returning submitted feedback lines as pending questions; focused green verification passed with that test plus `test_outline_stage_payload_blocks_lock_for_inline_pending_markers`; focused regression verification passed with 3 passed in 0.16s. Full Web service verification passed with `.venv/bin/python -m pytest tests/test_web_service.py -q` -> 84 passed in 0.65s; full verification passed with `.venv/bin/python -m pytest -q` -> 311 passed in 3.62s; `git diff --check` passed.
- Remaining risk: the existing generated project cleanup removed only the recursive feedback block from worldbuilding mirrors; no model re-run was performed.

### Follow-up: Outline Review Recommendation Pairing
- Files changed: `src/ai_novelist/web/outline_service.py`, `tests/test_web_service.py`, `docs/IMPLEMENTATION_PLAN.md`, and `docs/SESSION_SUMMARY.md`.
- Root cause: `build_outline_repair_suggestions()` flattened all numbered bullets from the review notes and used each bullet as both `message` and `recommendation`, so bullets under `## 主要问题` rendered the same text in the 问题 and 推荐修改意见 columns.
- Behavior changed: structured overall-review notes now pair same-numbered `## 主要问题` and `## 修改建议` entries into distinct problem/recommendation rows, with the old flat extraction retained as fallback. The current `demo-web` latest review run `20260531142926-641c38cf` is applied and wrote `outline.md`, `state.json`, and report metadata at 2026-05-31 22:30:15 +0800; `updated_stages=[]` indicates only the total outline artifact was updated, not individual stage mirrors.
- Verification: RED `.venv/bin/python -m pytest tests/test_web_service.py::test_outline_review_suggestions_pair_numbered_issues_with_recommendations -q` first failed because six flat suggestions were returned; after the fix, the new regression plus `test_outline_review_report_exposes_selectable_suggestions` passed, and a direct check against `demo-web` report `20260531142604-d23ec68e` produced distinct recommendations for the first three rows. Final affected verification passed with `.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py -q` -> 98 passed in 3.89s; `npm --prefix web/frontend run build` passed with the known Vite CJS Node API deprecation warning.

### Follow-up: Outline Review Priority Audit

- Files changed: `src/ai_novelist/web/outline_service.py`, `src/ai_novelist/prompts/outline_editor.md`, `web/frontend/src/types.ts`, `web/frontend/src/main.tsx`, `web/frontend/src/workspaces/review.tsx`, `tests/test_web_service.py`, `tests/test_web_app.py`, `tests/test_prompt_loader.py`, `tests/test_frontend_review_tabs_structure.py`, and docs.
- Behavior changed: overall outline review parses high/low/suggestion priority sections with caps of 50, 20, and 10 respectively; priority sections accept both numbered Markdown lists and bullet lists while the outline editor prompt now explicitly requires numbered lists; legacy flat or paired reports default to low priority; frontend grouping prioritizes high, then low, then suggestion items; frontend defaults high/low decisions to recommended and suggestion decisions to skipped; selected apply decisions are rendered in priority order, including custom decisions, with stable submitted ordering inside the same priority.
- Final verification before reviewer follow-up: `.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_prompt_loader.py -q` -> 114 passed in 1.86s; `.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py -q` -> 41 passed in 0.07s; `npm --prefix web/frontend run build` -> passed, 1590 modules transformed, built in 4.88s, with the known Vite CJS Node API deprecation warning; `git diff --check` -> passed with no output.
- Final review follow-up: the overall reviewer found that bullet lists inside priority sections could fall back to low-priority flat parsing. Added a failing regression for bullet-form high/low/suggestion sections and fixed priority parsing to preserve priority plus distinct recommendations for numbered and bullet list items.
- Follow-up verification: RED `.venv/bin/python -m pytest tests/test_web_service.py::test_outline_review_priority_sections_parse_bullet_items -q` first failed with all priorities parsed as `low`; RED `.venv/bin/python -m pytest tests/test_prompt_loader.py::test_outline_editor_prompt_keeps_parseable_status_and_review_boundary -q` first failed because the prompt lacked the numbered-list requirement. GREEN focused verification passed with `.venv/bin/python -m pytest tests/test_web_service.py::test_outline_review_priority_sections_parse_bullet_items tests/test_web_service.py::test_outline_review_priority_sections_parse_and_cap_items tests/test_web_service.py::test_outline_review_priority_sections_split_long_items_before_summarizing tests/test_web_service.py::test_outline_review_legacy_pairing_defaults_to_low_priority -q` -> 4 passed in 0.22s and `.venv/bin/python -m pytest tests/test_prompt_loader.py::test_outline_editor_prompt_keeps_parseable_status_and_review_boundary -q` -> 1 passed in 0.04s. Final affected verification after the follow-up passed with `.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_prompt_loader.py -q` -> 115 passed in 1.52s; `.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py -q` -> 41 passed in 0.20s; `npm --prefix web/frontend run build` -> passed, 1590 modules transformed, built in 5.23s, with the known Vite CJS Node API deprecation warning.
- Remaining risk: no live browser click test or real model review run was performed.

### Task 4: Frontend Priority Defaults And Grouping
- Files changed: `web/frontend/src/types.ts`, `web/frontend/src/main.tsx`, `web/frontend/src/workspaces/review.tsx`, `tests/test_frontend_review_tabs_structure.py`, and docs.
- Behavior changed: outline review suggestions now expose optional `priority`; frontend outline repair decisions default `suggestion` priority items to skip while high/low items remain recommended; the decision board renders high-priority, low-priority, and suggestion groups while keeping existing row controls.
- Verification: RED targeted pytest run first failed with 3 expected missing-source assertions; GREEN passed with `.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py::test_outline_review_suggestion_type_exposes_priority tests/test_frontend_review_tabs_structure.py::test_outline_review_decisions_default_by_priority tests/test_frontend_review_tabs_structure.py::test_outline_review_decision_board_groups_by_priority tests/test_frontend_review_tabs_structure.py::test_outline_review_workspace_renders_apply_completion_state -q` -> 4 passed in 0.03s. `npm --prefix web/frontend run build` passed with the known Vite CJS Node API deprecation warning.
- Remaining risk: coverage is source-structure and TypeScript build level; no browser-level visual grouping test was added.

### Follow-up: Outline Review High-Priority Continuation
- Files changed: `src/ai_novelist/web/outline_actions.py`, `tests/test_web_service.py`, `docs/IMPLEMENTATION_PLAN.md`, and `docs/SESSION_SUMMARY.md`.
- Root cause: the parser and frontend could already carry more than 10 high-priority suggestions, but the model often stopped its first high-priority batch at exactly 10 items. The Web table then displayed the full saved report, which was still only 10 parsed suggestions.
- Behavior changed: when an overall outline review or continuation batch produces exactly 10 newly returned high-priority suggestions, the backend now runs bounded same-click continuation prompts for only unlisted high-priority blockers, merges distinct results into the same report, and stops at no-new-items, a shorter follow-up batch, or the 50-item high-priority safety cap.
- Verification so far: RED `.venv/bin/python -m pytest tests/test_web_service.py::test_outline_review_continues_when_high_priority_batch_stops_at_ten -q` first failed with `adapter.review_calls == 1`; after the fix it passed with 1 passed in 0.20s. A boundary RED for `test_outline_review_does_not_continue_when_initial_high_priority_batch_exceeds_ten` first failed with `adapter.review_calls == 2`; after narrowing continuation to the last returned batch size, the two focused tests passed with 2 passed in 0.16s.
- Final affected verification: `.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py -q` -> 105 passed in 4.37s; `.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py -q` -> 41 passed in 0.31s; `npm --prefix web/frontend run build` -> passed, 1590 modules transformed, built in 5.55s, with the known Vite CJS Node API deprecation warning.
- Remaining risk: no live model or browser click run was performed; verification covers backend generation/merge behavior, Web route/service regressions, frontend source structure, and TypeScript production build.
