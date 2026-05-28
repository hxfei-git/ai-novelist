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

- The app is currently healthy under tests and frontend build.
- Active docs contained stale command examples for removed CLI flows.
- `.superpowers/` appeared as an untracked local artifact directory.
- DeepSeek default references were inconsistent between code/docs/script.
- `graph_outline.py`, `web/service.py`, `web/frontend/src/main.tsx`, `adapters/codex_cli.py`, and `tests/test_web_service.py` are maintenance hotspots.
- Some modules and prompts are pruning candidates, but dynamic prompt loading and persisted project compatibility require a reference matrix before deletion.

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

## Cleanup Plan

Current implementation plan:

- `docs/superpowers/plans/2026-05-28-web-only-architecture-cleanup.md`

Batch scope:

- ignore local `.superpowers/`
- rewrite README for Web-only usage
- rewrite active architecture plan
- align DeepSeek default in `scripts/run_web.sh`
- add a focused runtime-default drift test
- create `docs/web_only_reference_matrix.md`
- rewrite this session summary

Deferred to separate future plans:

- verified deletion of state fields, prompts, modules, or tests
- splitting large backend/frontend/test files
- separating mock behavior from `CodexCLIAdapter`

## Remaining Risk

No code deletion has been approved yet. The main remaining risk is stale compatibility code that appears unused but may still be reached through dynamic prompt names, old project state, or retained Web workflow helpers.

Any pruning batch must update this summary with:

- files changed
- tests run
- residual compatibility risk
- whether frontend build was required
