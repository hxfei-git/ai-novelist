# Web-Only Architecture Audit Design

Date: 2026-05-28
Status: Approved for documentation

## Goal

Define a conservative cleanup design for the current web-only AI Novelist repository. This document records the architecture audit findings, separates confirmed low-risk cleanup from higher-risk candidates, and defines validation gates for any later implementation work.

This spec does not authorize immediate code deletion or refactoring. It is a design checkpoint for a later implementation plan.

## Current Product Boundary

The retained runtime surface is the local Web application:

- `ai-novelist web`
- FastAPI routes in `src/ai_novelist/web/app.py`
- file-backed Web services in `src/ai_novelist/web/service.py`
- outline stage generation, revision, locking, outline review, chapter outline workspace, chapter batch generation, chapter review, and repair application
- shared storage, state, adapter, prompt, outline, chapter, bible, and craft helpers still used by the Web workflows

The previous chat-centric CLI surface is no longer active. A direct check shows `ai-novelist --help` only exposes `web`, and `ai-novelist chat --help` fails with `invalid choice: 'chat'`.

## Audit Evidence

The audit reviewed project files, docs, recent git status, CLI behavior, source layout, prompt references, generated files, and tests.

Observed health checks:

- `.venv/bin/python -m pytest -q`: `225 passed in 2.11s`
- `npm --prefix web/frontend run build`: passed; Vite emitted only the known CJS Node API deprecation warning
- `ai-novelist --help`: only the `web` subcommand is available
- `ai-novelist chat --help`: fails because `chat` has been removed
- exact duplicate non-empty source/test/doc/frontend files: none found

Observed worktree state:

- `?? .superpowers/`
- `src/ai_novelist/prompts/__pycache__/` and `tests/__pycache__/` are ignored by `.gitignore`
- `.superpowers/` is not ignored and contains previous brainstorming companion HTML and server state files

## Key Findings

The project is currently runnable and tested, but the repository has not fully converged around the web-only boundary.

The largest immediate issue is documentation drift. `README.md`, `docs/IMPLEMENTATION_PLAN.md`, and parts of `docs/SESSION_SUMMARY.md` still describe deleted or inactive flows such as `chat`, `compose`, `feishu`, `research`, `write-chapter`, `finalize-chapter`, and old smoke commands as active workflows. This directly conflicts with the actual CLI.

The second issue is cleanup uncertainty. Some files are likely legacy-only, but several workflows still use dynamic prompt names and shared state fields. Removing files by name alone would be risky. For example, chapter writing and volume writing load prompts through `load_prompt(prompt_name)`, so static string searches undercount real prompt usage.

The third issue is concentration of responsibility. Several modules are maintenance hotspots:

- `src/ai_novelist/graph_outline.py`: about 2860 lines
- `src/ai_novelist/web/service.py`: about 2004 lines
- `web/frontend/src/main.tsx`: about 1475 lines
- `src/ai_novelist/adapters/codex_cli.py`: about 1389 lines
- `tests/test_web_service.py`: about 1491 lines

These files are not necessarily wrong, but they make future cleanup harder because unrelated concerns are coupled in large files.

## Cleanup Design

Use a three-tier cleanup plan.

### P0: Immediate Hygiene

P0 contains changes that should be safe and should not alter runtime behavior.

- Rewrite active user-facing docs so they describe `ai-novelist web` as the only supported entrypoint.
- Remove or clearly archive stale docs that present deleted CLI commands as current.
- Add `.superpowers/` to `.gitignore` or remove the local untracked directory from the worktree before commits.
- Align DeepSeek default model documentation with the actual code path, which defaults to `deepseek-v4-pro` while some docs and `scripts/run_web.sh` still mention `deepseek-chat`.

Validation:

- `ai-novelist --help`
- keyword scan for deleted commands in active docs
- `git status --short`
- focused doc-only review

### P1: Verified Prune

P1 contains candidates that may be removable or shrinkable, but only after a reference matrix and tests confirm they are not used by retained Web workflows.

Candidates:

- `NovelState` fields left from Director, research, chat, finalize, old review, and export workflows
- modules directly referenced only by tests during the audit, including `src/ai_novelist/output_contracts.py` and `src/ai_novelist/corpus/project_memory.py`
- prompt files and mock branches that appear tied to deleted flows
- old `review_lock` compatibility paths if retained projects no longer need them
- Author Craft and corpus modules that are no longer reachable from Web workflows, if confirmed by import and runtime tests

Required method:

1. Build a reference matrix from imports, dynamic `load_prompt()` calls, Web service call paths, tests, and stored artifact compatibility.
2. Classify each candidate as retained, deleted, or kept for migration compatibility.
3. Delete only one coherent group per change.
4. Update tests and active docs in the same change.

Validation:

- focused tests for the changed area
- full `.venv/bin/python -m pytest -q` when state, persistence, prompts, adapters, or graph contracts change
- `npm --prefix web/frontend run build` when API payloads or frontend behavior change
- a brief note in `docs/SESSION_SUMMARY.md` recording scope, tests, and residual risk

### P2: Structural Refactor

P2 contains refactors that improve maintainability but should not be mixed with deletion work.

Suggested boundaries:

- Split `web/service.py` into project/progress, outline stage, outline review, chapter outline, chapter batch, chapter review, and repair modules.
- Split `graph_outline.py` into stage orchestration, prompt construction, stage structure repair, review-lock compatibility, and final outline persistence.
- Split `web/frontend/src/main.tsx` into API client, project shell, outline workspace, chapter outline workspace, chapter body workspace, review panels, and shared controls.
- Move mock response routing out of `CodexCLIAdapter` into a dedicated mock adapter or fixture module.
- Split `tests/test_web_service.py` by Web workflow area.

Validation:

- preserve public Web API response shapes unless a deliberate API migration is documented
- run focused service/app tests for the extracted boundary
- run frontend build for UI extractions
- run full pytest after broad module moves

## Non-Goals

This design does not add new product behavior, new workflows, new UI screens, or new storage backends.

This design does not remove `outline`, `chapter`, `bible`, `craft`, or prompt modules solely because their names look legacy. They must be evaluated through actual Web call paths and persisted project compatibility.

This design does not require cleaning historical `docs/superpowers/plans/*` files unless they are actively surfaced as current user documentation. Historical design and plan records can remain as archive material.

## Risks

Dynamic prompt loading can hide real dependencies. A prompt that looks unused in static search may still be passed through a variable prompt name.

State trimming can break existing `projects/<project>/state.json` files. Any removal from `NovelState` needs migration or backward-compatible loading.

Old compatibility paths such as `review_lock` may still matter for projects created before the web-only prune. Removing them requires fixture coverage for old project state.

Large-file refactors can create behavior changes even when intended as mechanical moves. P2 work should be isolated from deletion and covered by tests before and after the move.

## Acceptance Criteria

The later cleanup implementation is complete when:

- active docs match the actual `web`-only CLI surface
- `.superpowers/` no longer appears as an untracked repository artifact
- every deleted module, field, prompt, or test has a recorded reason and validation result
- retained Web workflows continue to pass Python tests and frontend build
- `docs/SESSION_SUMMARY.md` records verification scope and remaining risk for each cleanup batch

