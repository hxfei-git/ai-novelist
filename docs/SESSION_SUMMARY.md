# Session Summary

Updated: 2026-05-28
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

## Remaining Risk

One verified dead module has been removed. The main remaining risk is stale compatibility code that appears unused but may still be reached through dynamic prompt names, old project state, or retained Web workflow helpers.

Any pruning batch must update this summary with:

- files changed
- tests run
- residual compatibility risk
- whether frontend build was required
