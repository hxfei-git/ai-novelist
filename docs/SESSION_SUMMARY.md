# Session Summary

Updated: 2026-05-29
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
- Verification: targeted RED tests failed before implementation for missing applied report state and review-page completion UI; final-review RED concurrency test failed with `assert 2 == 1` for duplicate reviser calls before the lock; focused server-side duplicate-apply tests passed with `.venv/bin/python -m pytest tests/test_web_service.py::test_apply_outline_review_concurrent_duplicate_waits_for_applied_report tests/test_web_service.py::test_apply_outline_review_is_idempotent_after_report_applied tests/test_web_service.py::test_outline_review_apply_marks_latest_report_applied -q`; affected-suite verification passed with `.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_frontend_review_tabs_structure.py -q`; full pytest passed with `.venv/bin/python -m pytest -q`; frontend build passed with `npm --prefix web/frontend run build`.
- Remaining risk: no live browser/SSE click test was added; source-structure tests verify the state handling and TypeScript build verifies the component compiles.

## Remaining Risk

One verified dead module has been removed. The main remaining risk is stale compatibility code that appears unused but may still be reached through dynamic prompt names, old project state, or retained Web workflow helpers.

Any pruning batch must update this summary with:

- files changed
- tests run
- residual compatibility risk
- whether frontend build was required
