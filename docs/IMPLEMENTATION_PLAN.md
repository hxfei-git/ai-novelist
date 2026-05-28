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
  - `web/service.py`, reduced by moving outline helpers but still large
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

## Architecture Web Context Remediation Notes

- 2026-05-29: Hardened SSE/Web error behavior by adding source-level guards that require streaming workspace actions to call `showError(error)` and release running flags in `finally`; added a Web app regression for service exceptions surfacing as SSE `event: error` payloads.
- 2026-05-29: Context profiles now record source paths and suppress duplicate artifact/state fallback content by digest before rendering.
- 2026-05-29: Direct chapter drafting now uses the shared `direct_chapter_drafting` `ContextBundle` profile and records a context manifest for direct and volume write paths.

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
