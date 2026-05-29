# AI Novelist Web-Only Architecture Plan

Updated: 2026-05-28

## Current State

AI Novelist is maintained as a local Web UI/API application. The active CLI surface is only:

```bash
.venv/bin/ai-novelist web
```

The historical chat, compose, feishu, research-only, export, finalize, and one-off writer commands are not active in this checkout.

## Runtime Architecture

- 2026-05-29: Web operation hardening started with explicit project-scoped progress log writes, chapter detail loading cleanup, and chapter batch running guards. Public API paths remain unchanged.

```text
Browser
  |
  v
FastAPI app: src/ai_novelist/web/app.py
  |-- project routes
  |-- outline stage routes
  |-- outline review routes
  |-- chapter-outline workspace routes
  |-- chapter batch routes
  |-- chapter review and repair routes
  |-- SSE progress streaming
  `-- static frontend mount when web/frontend/dist exists
  |
  v
Web service layer: src/ai_novelist/web/service.py
  |-- delegates outline helper behavior to src/ai_novelist/web/outline_service.py
  |-- delegates ordinary outline actions to src/ai_novelist/web/outline_actions.py
  |-- delegates chapter-outline actions to src/ai_novelist/web/chapter_outline_actions.py
  |-- delegates chapter review prompt/source helpers to src/ai_novelist/web/chapter_service.py
  |-- LocalStore-backed project operations
  |-- outline stage payloads and pending-question submission
  |-- explicit outline stage generate/revise/lock calls
  |-- outline and chapter-outline review report persistence
  |-- volume chapter batch generation
  |-- global chapter review and repair application
  |-- shared Web JSON parsing helpers in web/json_utils.py
  |
  v
Workflow helpers
  |-- graph_outline.py
  |-- graph_volume_write.py
  |-- graph_chapter_write.py
  |-- graph_chapter_plan.py
  |-- graph_bible.py
  |-- outline/* structure and contract helpers
  |-- corpus/* craft helpers when reachable from active workflows
  |
  v
Model adapters
  |-- CodexCLIAdapter for real Codex CLI execution
  |-- MockCodexAdapter for deterministic mock mode
  |-- DeepSeekAdapter
  `-- CodexCLIAdapter(mock=True) compatibility delegates to MockCodexAdapter
  |
  v
Local files under projects/<project>/
```

## Active Web Workflows

### Project Management

- list projects with `state.json`
- create a project
- save the seed idea
- load and save per-project progress logs

### Ordinary Outline Stages

- list stages while hiding `review_lock` and `chapter_outline`
- load stage Markdown
- save editable stage content
- generate, revise, and lock stages explicitly
- submit pending question answers

### Outline Review

- generate a review report without mutating outline content
- store reports under `outline/reviews/<run_id>/`
- apply selected recommendations only after explicit user action

### Chapter Outline Workspace

- expose volume specs and volume statuses
- generate, revise, and lock only the current allowed volume
- keep completed volumes while refreshing the merged `chapter_outline` artifact
- review and apply chapter-outline suggestions through explicit actions

### Chapter Body Workspace

- generate selected chapter drafts for a volume
- preserve old drafts by creating higher `draft_vN.md` versions
- read latest chapter body by `final.md > highest draft_vN.md > legacy chapter_###.md`
- run global chapter review
- apply selected repair suggestions as new draft versions

## Configuration

Core settings live in `src/ai_novelist/config.py`.

Important environment variables:

- `AI_NOVELIST_PROJECTS_DIR`: local project root, default `projects`
- `AI_NOVELIST_MODEL_PROVIDER`: `codex` or `deepseek`, default `codex`
- `AI_NOVELIST_CODEX_BIN`: Codex CLI binary, default `codex`
- `AI_NOVELIST_CODEX_TIMEOUT`: optional Codex timeout in seconds
- `DEEPSEEK_API_KEY`: DeepSeek API key
- `AI_NOVELIST_DEEPSEEK_MODEL`: DeepSeek model, default `deepseek-v4-pro`
- `AI_NOVELIST_DEEPSEEK_BASE_URL`: default `https://api.deepseek.com`

Search and corpus settings still exist in configuration because some craft helpers and persisted-state compatibility may depend on them. They are pruning candidates only after reference-matrix verification.

## Current Maintenance Risks

- Active docs can drift from the actual `web`-only CLI surface.
- Dynamic prompt loading makes unused prompt detection non-trivial.
- `NovelState` retains fields from deleted flows and needs compatibility-aware trimming.
- Large modules concentrate unrelated responsibilities:
  - `graph_outline.py`
  - `web/service.py`, reduced by moving project/progress helpers and outline/chapter-outline actions but still large
  - `web/frontend/src/main.tsx`, reduced by moving shared types and API helpers into `web/frontend/src/types.ts` and `web/frontend/src/api.ts`
  - `adapters/mock_codex.py` as a large deterministic fixture isolated from the real adapter
  - `tests/test_web_service.py`

## Cleanup Roadmap

### P0: Immediate Hygiene

- keep README and active docs aligned with `ai-novelist web`
- ignore `.superpowers/`
- align script/docs defaults with `deepseek-v4-pro`
- keep tests passing

### P1: Verified Prune

- maintain the P1 reference matrix
- classify candidates as retained, deleted, or compatibility-kept
- delete only after import, dynamic prompt, Web route, test, and persisted-project checks
- update `docs/SESSION_SUMMARY.md` with each cleanup batch

### P2: Structural Refactor

- split large files by workflow boundary
- keep Web API payloads stable
- keep mock model behavior separate from the real Codex adapter
- split broad Web service tests by workflow area

## Web Prompt Context Prune Audit Notes

- 2026-05-29: Added an explicit prompt registry for retained Web prompt files and prompt-loader tests that reject missing registry entries, orphan prompt files, and stale author-craft policy prompt names.
- 2026-05-29: Pruned legacy mock adapter branches and stale DeepSeek agent category names for deleted non-Web agents; deleted first-line mock agents now return `UNSUPPORTED_AGENT: <agent>` before any body substring routing, while active retained mock agents keep fallback behavior for Web mock mode.

## Architecture Web Context Remediation Notes

- 2026-05-29: Stage refresh after successful outline generation now preserves existing editor content during pending fetches and treats transient post-stream `Failed to fetch` refresh failures as background noise instead of progress-log errors.
- 2026-05-29: Outline-stage save steps now emit completed progress events after artifacts and state are written, preventing right-side save rows from remaining `running` after successful generation or light revision.
- 2026-05-29: Web progress events now preserve a `model` field, parse elapsed time from both slash-separated and pipe-separated metadata, and render the right-side progress panel newest-first without changing persisted chronological order.
- 2026-05-29: Saving an onboarding idea no longer pre-fills the outline-stage instruction input, and transient browser `Failed to fetch` errors from background project/stage refreshes are filtered out of the persisted progress log.
- 2026-05-29: Hardened SSE/Web error behavior by adding source-level guards that require streaming workspace actions to call `showError(error)` and release running flags in `finally`; added a Web app regression for service exceptions surfacing as SSE `event: error` payloads.
- 2026-05-29: Context profiles now record source paths and suppress duplicate artifact/state fallback content by digest before rendering.
- 2026-05-29: Direct chapter drafting now uses the shared `direct_chapter_drafting` `ContextBundle` profile and records a context manifest for direct and volume write paths.
- 2026-05-29: Added `workflow_payloads.py` helpers for high-risk `director_task_args` reads and writes; chapter workflow entry points and Web batch generation now use named payload helpers while preserving persisted payload keys.
- 2026-05-29: Project and progress-log Web operations moved into `src/ai_novelist/web/project_service.py`; `web/service.py` re-exports the helpers as a compatibility facade while later outline, chapter, and review splits proceed.
- 2026-05-29: Ordinary outline and chapter-outline Web actions moved into `src/ai_novelist/web/outline_actions.py` and `src/ai_novelist/web/chapter_outline_actions.py`; `web/service.py` re-exports the action entry points as a compatibility facade.
- 2026-05-29: Chapter batch/list/detail and global review/repair Web actions moved into `src/ai_novelist/web/chapter_actions.py` and `src/ai_novelist/web/review_actions.py`; `web/service.py` re-exports the action entry points as a compatibility facade.
- 2026-05-29: Completed the architecture/Web/context remediation batch. Web actions have stronger running/error guards, context profiles record source manifests and deduplicate sources, Web services and outline graph helpers are split behind compatibility facades, and frontend workspace components are split from the entry file.

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

### Phase 6: Frontend Workspace Split
- Files changed: frontend progress utility, workspace components, `main.tsx`, frontend structure tests, docs.
- Behavior changed: frontend UI is split into focused modules while existing tabs, actions, progress log, and review workspaces remain compatible.
- Verification: `.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py -q` -> passed with 29 passed in 0.05s; `npm --prefix web/frontend run build` -> passed with the known Vite CJS Node API deprecation warning; `main.tsx` is 799 lines (<900).
- Remaining risk: action handlers still live in `main.tsx`; a future phase can split hooks once component boundaries settle.
- Next entry point: final verification and cleanup.
- Continuation note: resume at Task 12; frontend split is accepted only when `main.tsx` is below 900 lines and build passes.

### Phase 6b: Onboarding Instruction and Progress Noise Guard
- Files changed: frontend state orchestration and frontend source regression tests.
- Behavior changed: saving the initial novel idea clears the shared stage instruction field instead of copying the full idea into the direction-stage input; background project/stage/chapter loaders ignore transient browser `TypeError: Failed to fetch` errors so those network interruptions are not persisted as progress-log entries.
- Verification: RED targeted runs first failed for the missing `setInstruction('')` guard and missing `showBackgroundError`; `.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py -q` passed with 31 passed in 0.06s; `npm --prefix web/frontend run build` passed with the known Vite CJS Node API deprecation warning.
- Remaining risk: this is source/build coverage, not browser-level interaction coverage; user-triggered action failures still persist to the progress log through `showError`.
- Next entry point: add browser interaction coverage if more UI state leakage appears.

### Phase 6c: Progress Order and Model Metrics
- Files changed: Web project progress service, frontend progress types/rendering, Web/front-end structure tests, docs, and the Superpowers implementation plan.
- Behavior changed: right-side progress rows render newest-first while the saved progress log remains append-ordered; structured progress rows now include `model` between status and elapsed time; backend parsing keeps legacy `/` metadata, accepts `|` metadata, and does not treat context capacity as a model when no model is present such as `deepseek-v4-pro | medium | 12.4s | ctx=4K/1M | tok≈8.1K`.
- Verification: backend RED failed first because `model` was dropped and pipe-separated elapsed time was empty; frontend RED failed first because `visibleLog` and `item.model` rendering were absent. Target verification passed with `.venv/bin/python -m pytest tests/test_web_service.py::test_project_progress_log_accepts_legacy_strings_and_structured_events tests/test_web_service.py::test_progress_event_drops_generated_message_body_but_retains_metrics tests/test_web_service.py::test_progress_event_includes_key_and_completion_metrics tests/test_web_service.py::test_progress_event_includes_model_and_elapsed_from_pipe_metadata tests/test_web_service.py::test_progress_event_without_model_does_not_use_context_capacity_as_model tests/test_frontend_review_tabs_structure.py::test_progress_panel_renders_structured_metrics_and_keeps_legacy_branch tests/test_frontend_review_tabs_structure.py::test_progress_panel_merges_rows_by_key_and_renders_completion_metrics -q` -> 7 passed in 0.14s; final affected-suite verification passed with `.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_frontend_review_tabs_structure.py -q` -> 116 passed in 1.25s; `npm --prefix web/frontend run build` passed with the known Vite CJS Node API deprecation warning.
- Remaining risk: coverage is source/service/build level; no browser screenshot test was added for visual order, and old persisted structured rows without `model` render with that slot omitted.
- Next entry point: add browser-level progress-panel ordering coverage if UI regressions continue.

### Phase 6d: Outline Save Progress Completion
- Files changed: outline graph save progress handling, Web service regression tests, docs, and the Superpowers implementation plan.
- Behavior changed: full outline-stage saves and light-revision saves are wrapped with `run_with_progress`, so successful artifact/state writes emit a matching completed `OutlineStage` event and failures emit a failed event instead of leaving the save row `running`.
- Verification: RED run `.venv/bin/python -m pytest tests/test_web_service.py::test_revise_outline_stage_completes_save_progress -q` first failed because the final save event remained `running`; after the fix the same test passed with 1 passed in 0.17s. Affected-suite verification passed with `.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_outline_graph_modules.py -q` -> 93 passed in 1.17s.
- Remaining risk: coverage is service/graph-level; no live browser SSE run was performed. Existing generated project logs can still contain stale `running` rows until refreshed or cleaned.
- Next entry point: browser-level SSE progress coverage if more long-running status drift appears.

### Phase 6e: Stage Refresh Fallback
- Files changed: frontend stage loading/orchestration, frontend source regression tests, docs, and the Superpowers implementation plan.
- Behavior changed: `loadStage()` no longer clears the current outline editor content before a refresh response arrives; after a successful outline generation stream, `refreshStages()` and `loadStage(activeStage)` run in a nested refresh guard so transient browser `TypeError: Failed to fetch` errors do not append `error: Failed to fetch` to the project progress log.
- Verification: RED targeted run first failed because `loadStage()` called `setContent('')` before fetching and `runStage()` lacked the nested `showBackgroundError(refreshError)` guard. Target tests passed with `.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py::test_stage_load_preserves_existing_content_while_refreshing tests/test_frontend_review_tabs_structure.py::test_run_stage_does_not_log_transient_post_stream_refresh_failure -q` -> 2 passed in 0.02s; full frontend structure suite passed with `.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py -q` -> 33 passed in 0.17s; `npm --prefix web/frontend run build` passed with the known Vite CJS Node API deprecation warning.
- Remaining risk: coverage is source/build level, not a live browser network-drop run. Current `demo-web` generated progress log was locally cleaned of the stale `error: Failed to fetch` row; other generated project logs may retain old rows until cleaned or overwritten.
- Next entry point: add browser-level SSE refresh coverage if post-stream refresh failures recur.

### Phase 6f: Outline Review Apply Completion
- Files changed: outline review apply service/actions, Web frontend review workspace, frontend/backend regression tests, docs, and the Superpowers implementation plan.
- Behavior changed: applying selected outline overall-review suggestions now persists an applied report state, returns idempotent success for duplicate apply calls, serializes concurrent duplicate apply requests for the same project/run inside the Web process, keeps the browser on the "大纲总体审查" view, shows an applying spinner, and renders "采纳完成" instead of stale selectable issues after success.
- Verification: final-review RED concurrency test first failed with two reviser calls; focused server-side duplicate-apply tests then passed with `.venv/bin/python -m pytest tests/test_web_service.py::test_apply_outline_review_concurrent_duplicate_waits_for_applied_report tests/test_web_service.py::test_apply_outline_review_is_idempotent_after_report_applied tests/test_web_service.py::test_outline_review_apply_marks_latest_report_applied -q`; final affected-suite verification passed with `.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_frontend_review_tabs_structure.py -q` -> 125 passed in 1.33s; full pytest passed with `.venv/bin/python -m pytest -q` -> 276 passed in 2.30s; `npm --prefix web/frontend run build` passed with the known Vite CJS Node API deprecation warning.
- Remaining risk: coverage is service/source/build level; no browser-level click test was added for the long-running apply spinner.
- Next entry point: add browser-level review-apply interaction coverage if this UI flow regresses again.

## Verification Policy

Use the smallest relevant test set during implementation. Run full pytest when a change touches state, persistence, graph contracts, adapters, prompts, or shared workflow helpers.

Baseline checks:

```bash
.venv/bin/ai-novelist --help
.venv/bin/python -m pytest -q
npm --prefix web/frontend run build
```

For docs-only changes, run the relevant keyword scans and CLI help checks.

For frontend or API payload changes, run:

```bash
.venv/bin/python -m pytest tests/test_web_app.py tests/test_web_service.py -q
npm --prefix web/frontend run build
```

## Current Reference Documents

- `docs/superpowers/specs/2026-05-28-web-only-architecture-audit-design.md`
- `docs/superpowers/plans/2026-05-28-web-only-architecture-cleanup.md`
- `docs/superpowers/plans/2026-05-28-web-only-verified-prune.md`
- `docs/superpowers/plans/2026-05-28-web-structural-refactor.md`
- `docs/superpowers/plans/2026-05-29-progress-order-and-model-metrics.md`
- `docs/superpowers/plans/2026-05-29-outline-save-progress-completion.md`
- `docs/superpowers/plans/2026-05-29-stage-refresh-fallback.md`
- `docs/superpowers/plans/2026-05-29-outline-review-apply-completion.md`
