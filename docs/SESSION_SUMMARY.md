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
- Behavior changed: routing and review-lock helpers moved out of the main outline graph without intended semantic changes.
- Verification: `.venv/bin/python -m pytest tests/test_outline_graph_modules.py tests/test_web_outline_service.py tests/test_web_service.py::test_outline_stage_list_hides_review_lock -q`.
- Remaining risk: prompt builders and structure repair helpers still remain in `graph_outline.py`.
- Next entry point: extract prompt and repair helpers.
- Continuation note: resume at Task 10; keep helper function names exported because tests and `graph_outline.py` import them directly.

## Remaining Risk

One verified dead module has been removed. The main remaining risk is stale compatibility code that appears unused but may still be reached through dynamic prompt names, old project state, or retained Web workflow helpers.

Any pruning batch must update this summary with:

- files changed
- tests run
- residual compatibility risk
- whether frontend build was required
