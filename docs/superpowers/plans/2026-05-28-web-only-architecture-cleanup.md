# Web-Only Architecture Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the repository's active documentation and low-risk hygiene into alignment with the actual `ai-novelist web` runtime, and produce a reference matrix for later verified pruning.

**Architecture:** Execute the cleanup in a safe first batch. P0 changes update docs, ignore local brainstorming artifacts, and align runtime defaults without touching creative workflow behavior. P1 work in this plan only creates a reference matrix and decision record; it does not delete modules, state fields, prompts, or tests.

**Tech Stack:** Python 3.11+, pytest, FastAPI, Vite/React/TypeScript, file-backed `projects/` storage, Git.

---

## Scope

This plan implements the first cleanup batch from `docs/superpowers/specs/2026-05-28-web-only-architecture-audit-design.md`.

In scope:

- `.gitignore` hygiene for `.superpowers/`
- README rewrite for the active Web-only CLI
- active architecture documentation rewrite
- current session summary rewrite
- DeepSeek default alignment between code, script, and docs
- a tracked reference matrix for P1 pruning candidates
- verification commands and one commit per task

Out of scope:

- deleting modules, prompts, tests, or `NovelState` fields
- splitting `graph_outline.py`, `web/service.py`, `web/frontend/src/main.tsx`, or `CodexCLIAdapter`
- changing Web API payload shapes
- changing model calling semantics beyond aligning documented/script defaults

## File Structure

Files to modify:

- `.gitignore`: ignore local Superpowers browser companion artifacts.
- `README.md`: replace stale chat/compose/feishu/research instructions with Web-only usage.
- `docs/IMPLEMENTATION_PLAN.md`: replace stale historical implementation narrative with current Web-only architecture and cleanup roadmap.
- `docs/SESSION_SUMMARY.md`: replace contradictory session summary with a concise current state, audit results, and verification scope.
- `scripts/run_web.sh`: align the default DeepSeek model with `src/ai_novelist/config.py`.
- `tests/test_web_runtime_defaults.py`: add a focused test that guards runtime default drift.
- `docs/web_only_reference_matrix.md`: add the P1 candidate matrix for future verified pruning.

Files to read during execution:

- `src/ai_novelist/config.py`
- `src/ai_novelist/cli.py`
- `src/ai_novelist/web/app.py`
- `docs/superpowers/specs/2026-05-28-web-only-architecture-audit-design.md`

---

### Task 1: Ignore Local Superpowers Artifacts

**Files:**

- Modify: `.gitignore`
- Test: Git ignore/status checks

- [ ] **Step 1: Confirm the current failure**

Run:

```bash
git status --short
git check-ignore -v .superpowers
```

Expected:

- `git status --short` includes `?? .superpowers/`
- `git check-ignore -v .superpowers` exits non-zero and prints nothing

- [ ] **Step 2: Add `.superpowers/` to `.gitignore`**

Append this line after `run/`:

```gitignore
.superpowers/
```

- [ ] **Step 3: Verify the directory is ignored**

Run:

```bash
git check-ignore -v .superpowers
git status --short
```

Expected:

- `git check-ignore -v .superpowers` prints the `.gitignore` line for `.superpowers/`
- `git status --short` no longer includes `?? .superpowers/`

- [ ] **Step 4: Commit**

Run:

```bash
git add .gitignore
git commit -m "chore: ignore local superpowers artifacts"
```

---

### Task 2: Guard Web Runtime Defaults

**Files:**

- Create: `tests/test_web_runtime_defaults.py`
- Modify: `scripts/run_web.sh`
- Test: `tests/test_web_runtime_defaults.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_web_runtime_defaults.py`:

```python
from __future__ import annotations

from pathlib import Path

from ai_novelist.config import load_settings


def test_deepseek_default_model_is_consistent(monkeypatch) -> None:
    monkeypatch.delenv("AI_NOVELIST_DEEPSEEK_MODEL", raising=False)

    settings = load_settings()
    script = Path("scripts/run_web.sh").read_text(encoding="utf-8")

    assert settings.deepseek_model == "deepseek-v4-pro"
    assert 'MODEL="${AI_NOVELIST_DEEPSEEK_MODEL:-deepseek-v4-pro}"' in script
```

- [ ] **Step 2: Run the test and confirm it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_runtime_defaults.py -q
```

Expected:

- one failed test
- failure shows `scripts/run_web.sh` still defaults to `deepseek-chat`

- [ ] **Step 3: Align `scripts/run_web.sh`**

Change this line:

```bash
MODEL="${AI_NOVELIST_DEEPSEEK_MODEL:-deepseek-chat}"
```

to:

```bash
MODEL="${AI_NOVELIST_DEEPSEEK_MODEL:-deepseek-v4-pro}"
```

- [ ] **Step 4: Run the focused test**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_runtime_defaults.py -q
```

Expected:

- `1 passed`

- [ ] **Step 5: Commit**

Run:

```bash
git add scripts/run_web.sh tests/test_web_runtime_defaults.py
git commit -m "test: guard web runtime defaults"
```

---

### Task 3: Rewrite README for Web-Only Usage

**Files:**

- Modify: `README.md`
- Test: CLI help and deleted-command keyword scan

- [ ] **Step 1: Replace `README.md` with current Web-only content**

Use this full content:

````markdown
# AI Novelist

AI Novelist is currently maintained as a local Web UI/API application for novel outlining, chapter outline planning, chapter batch drafting, review, and repair workflows.

The active command surface is:

```bash
.venv/bin/ai-novelist web
```

Older chat-centric CLI flows have been removed from the active runtime. Do not use `chat`, `compose`, `feishu`, `research`, `write-chapter`, `finalize-chapter`, `export`, or `show` commands in this checkout.

## Environment

```bash
cd /home/ubuntu/1.project/ai-novelist
.venv/bin/ai-novelist --help
```

Expected command list:

```text
{web}
```

Key local dependencies:

- Python 3.12 virtual environment under `.venv/`
- pytest for backend tests
- Vite + React + TypeScript under `web/frontend/`
- optional FastAPI/Uvicorn dependencies installed through the `web` extra

## Running the Web App

Mock mode avoids real model calls:

```bash
.venv/bin/ai-novelist web --host 127.0.0.1 --port 8000 --mock
```

Real Codex CLI mode is the default when `--mock` is omitted and `AI_NOVELIST_MODEL_PROVIDER` is not set:

```bash
.venv/bin/ai-novelist web --host 127.0.0.1 --port 8000
```

DeepSeek mode:

```bash
export AI_NOVELIST_MODEL_PROVIDER=deepseek
export DEEPSEEK_API_KEY="your DeepSeek API key"
export AI_NOVELIST_DEEPSEEK_MODEL=deepseek-v4-pro

.venv/bin/ai-novelist web --host 127.0.0.1 --port 8000 --provider deepseek --timeout 180
```

The helper script starts the Web service with DeepSeek defaults and writes logs under `run/`:

```bash
scripts/run_web.sh start
scripts/run_web.sh status
scripts/run_web.sh logs
scripts/run_web.sh stop
```

## Web Workflows

The Web app uses local file-backed projects under `projects/<project>/`.

Supported workflows:

- create and open local projects
- save the project seed idea
- generate, revise, save, and lock ordinary outline stages
- resolve pending outline questions through recommended, uncertain, or custom answers
- review the full outline and explicitly apply selected fixes
- generate, revise, review, and lock chapter-outline volumes
- batch-generate chapter drafts for a selected volume
- review all generated chapter bodies
- apply selected repair suggestions to a chapter as a new draft version

The main backend modules are:

- `src/ai_novelist/web/app.py`: FastAPI routes, adapter selection, SSE streaming, static frontend mounting
- `src/ai_novelist/web/service.py`: file-backed Web workflow services
- `src/ai_novelist/graph_outline.py`: outline-stage orchestration used by Web
- `src/ai_novelist/graph_volume_write.py`: volume chapter batch generation used by Web
- `src/ai_novelist/storage/local_store.py`: local project persistence

## Generated Project Files

Common project artifacts:

```text
projects/<project>/state.json
projects/<project>/outline.md
projects/<project>/worldbuilding.md
projects/<project>/outline/<stage>.md
projects/<project>/outline_stages/<stage>.md
projects/<project>/outline/reviews/<run_id>/report.json
projects/<project>/outline/chapter_reviews/<run_id>/report.json
projects/<project>/chapters/chapter_001/draft_v1.md
projects/<project>/chapters/chapter_001/draft_v2.md
projects/<project>/chapters/chapter_001/final.md
projects/<project>/chapters/global_consistency/<run_id>/report.json
projects/<project>/web_progress_log.json
```

`projects/` is local generated data and is ignored by Git.

## Development Checks

Backend tests:

```bash
.venv/bin/python -m pytest -q
```

Frontend build:

```bash
npm --prefix web/frontend run build
```

Runtime command check:

```bash
.venv/bin/ai-novelist --help
```

## Cleanup Status

The repository has already removed the non-Web CLI command surface. Remaining cleanup is tracked in:

- `docs/superpowers/specs/2026-05-28-web-only-architecture-audit-design.md`
- `docs/superpowers/plans/2026-05-28-web-only-architecture-cleanup.md`

Future pruning must verify Web call paths, dynamic prompt loading, and persisted project compatibility before deleting modules, prompts, tests, or state fields.
````

- [ ] **Step 2: Verify deleted commands are only mentioned as removed**

Run:

```bash
rg -n "ai-novelist (chat|compose|feishu|research|write-chapter|finalize-chapter|export|show)" README.md
```

Expected:

- no matches

- [ ] **Step 3: Verify active CLI help**

Run:

```bash
.venv/bin/ai-novelist --help
```

Expected:

- output lists only `{web}`

- [ ] **Step 4: Commit**

Run:

```bash
git add README.md
git commit -m "docs: rewrite readme for web-only runtime"
```

---

### Task 4: Rewrite Active Architecture Plan

**Files:**

- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Test: architecture-doc keyword scan

- [ ] **Step 1: Replace `docs/IMPLEMENTATION_PLAN.md` with current architecture content**

Use this full content:

````markdown
# AI Novelist Web-Only Architecture Plan

Updated: 2026-05-28

## Current State

AI Novelist is maintained as a local Web UI/API application. The active CLI surface is only:

```bash
.venv/bin/ai-novelist web
```

The historical chat, compose, feishu, research-only, export, finalize, and one-off writer commands are not active in this checkout.

## Runtime Architecture

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
  |-- LocalStore-backed project operations
  |-- outline stage payloads and pending-question submission
  |-- explicit outline stage generate/revise/lock calls
  |-- outline and chapter-outline review report persistence
  |-- volume chapter batch generation
  |-- global chapter review and repair application
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
  |-- CodexCLIAdapter
  |-- DeepSeekAdapter
  `-- mock mode through CodexCLIAdapter(mock=True)
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
  - `web/service.py`
  - `web/frontend/src/main.tsx`
  - `adapters/codex_cli.py`
  - `tests/test_web_service.py`

## Cleanup Roadmap

### P0: Immediate Hygiene

- keep README and active docs aligned with `ai-novelist web`
- ignore `.superpowers/`
- align script/docs defaults with `deepseek-v4-pro`
- keep tests passing

### P1: Verified Prune

- maintain `docs/web_only_reference_matrix.md`
- classify candidates as retained, deleted, or compatibility-kept
- delete only after import, dynamic prompt, Web route, test, and persisted-project checks
- update `docs/SESSION_SUMMARY.md` with each cleanup batch

### P2: Structural Refactor

- split large files by workflow boundary
- keep Web API payloads stable
- separate mock model behavior from the real Codex adapter
- split broad Web service tests by workflow area

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
````

- [ ] **Step 2: Verify old command examples are gone from the active architecture plan**

Run:

```bash
rg -n "ai-novelist (chat|compose|feishu|research|write-chapter|finalize-chapter|export|show)" docs/IMPLEMENTATION_PLAN.md
```

Expected:

- no matches

- [ ] **Step 3: Commit**

Run:

```bash
git add docs/IMPLEMENTATION_PLAN.md
git commit -m "docs: align implementation plan with web-only architecture"
```

---

### Task 5: Add the P1 Reference Matrix

**Files:**

- Create: `docs/web_only_reference_matrix.md`
- Test: static search and human review

- [ ] **Step 1: Create the reference matrix**

Create `docs/web_only_reference_matrix.md`:

````markdown
# Web-Only Reference Matrix

Updated: 2026-05-28

## Purpose

This matrix records cleanup candidates from the Web-only architecture audit. It prevents deleting files solely because their names look legacy.

Statuses:

- `retain`: used by active Web workflows
- `candidate`: may be removed or trimmed after deeper verification
- `compatibility-kept`: retained for old persisted project data or migration safety
- `deferred`: belongs to a later structural refactor plan

## Confirmed Runtime Surface

- CLI entrypoint: `ai-novelist web`
- Backend app: `src/ai_novelist/web/app.py`
- Backend service: `src/ai_novelist/web/service.py`
- Frontend: `web/frontend/src/main.tsx`
- Storage: `src/ai_novelist/storage/local_store.py`

## Candidate Matrix

| Path or Area | Current Evidence | Status | Decision Rule |
| --- | --- | --- | --- |
| `src/ai_novelist/cli.py` | actual CLI exposes only `web` | retain | keep as thin Web command entrypoint |
| `src/ai_novelist/web/app.py` | FastAPI routes and adapter selection for Web | retain | split only in P2 refactor |
| `src/ai_novelist/web/service.py` | all retained Web workflows call this layer | retain | split only in P2 refactor |
| `src/ai_novelist/graph_outline.py` | Web outline stage and review functions import from it | retain | prune internals only after route-level tests |
| `src/ai_novelist/graph_volume_write.py` | Web chapter batch generation uses it | retain | keep while chapter body workspace exists |
| `src/ai_novelist/graph_chapter_write.py` | volume writer imports direct chapter write helpers | retain | verify before any split |
| `src/ai_novelist/graph_chapter_plan.py` | chapter write and outline workspace helpers depend on it | retain | verify call path before pruning |
| `src/ai_novelist/graph_bible.py` | outline graph imports bible helpers | retain | verify old-project compatibility before pruning |
| `src/ai_novelist/state.py` Director/research fields | fields load and save through project `state.json` | candidate | remove only with backward-compatible loader behavior |
| `src/ai_novelist/output_contracts.py` | audit found direct references only from tests | candidate | delete only if no retained workflow imports it after full search |
| `src/ai_novelist/corpus/project_memory.py` | audit found direct references only from tests | candidate | delete only if craft retrieval no longer needs project memory artifacts |
| `src/ai_novelist/corpus/*` | some craft helpers are reachable through chapter and outline contexts | candidate | classify module-by-module with import and runtime checks |
| `src/ai_novelist/prompts/*.md` | dynamic `load_prompt(prompt_name)` undercounts usage | candidate | remove only after tracing prompt_name values in graph code and tests |
| `review_lock` stage compatibility | hidden from Web navigation but still present in state/contracts/helpers | compatibility-kept | remove only with old project fixture coverage |
| `.superpowers/` local directory | untracked local browser companion artifacts | candidate | ignore through `.gitignore`, do not commit |
| `web/frontend/src/main.tsx` | active UI in a large file | deferred | split in P2 frontend plan |
| `tests/test_web_service.py` | broad active service coverage in a large file | deferred | split in P2 test-structure plan |
| `src/ai_novelist/adapters/codex_cli.py` mock routing | real adapter and mock fixture behavior are coupled | deferred | split mock adapter in P2 adapter plan |

## Required Checks Before Deletion

For any candidate deletion, run:

```bash
rg -n "candidate_name|load_prompt\\(|AGENT:" src tests docs README.md
.venv/bin/python -m pytest -q
```

If the candidate touches frontend payloads or Web route behavior, also run:

```bash
npm --prefix web/frontend run build
```

If the candidate touches persisted state fields, create or update a test that loads an old-style `state.json` containing the removed field and verifies `NovelState.from_dict()` still succeeds.

## Current Decision

No P1 candidate is approved for deletion by this matrix alone. It is a prerequisite for a later verified-prune implementation plan.
````

- [ ] **Step 2: Verify matrix references current candidate names**

Run:

```bash
rg -n "output_contracts|project_memory|review_lock|load_prompt|CodexCLIAdapter|graph_outline|web/service" docs/web_only_reference_matrix.md
```

Expected:

- matches for each named candidate or retained hotspot

- [ ] **Step 3: Commit**

Run:

```bash
git add docs/web_only_reference_matrix.md
git commit -m "docs: add web-only reference matrix"
```

---

### Task 6: Rewrite Session Summary for Current State

**Files:**

- Modify: `docs/SESSION_SUMMARY.md`
- Test: summary keyword scan and verification command record

- [ ] **Step 1: Replace `docs/SESSION_SUMMARY.md` with current concise summary**

Use this full content:

````markdown
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
````

- [ ] **Step 2: Verify active summary no longer presents old commands as runnable**

Run:

```bash
rg -n "ai-novelist (chat|compose|feishu|research|write-chapter|finalize-chapter|export|show)" docs/SESSION_SUMMARY.md
```

Expected:

- no matches

- [ ] **Step 3: Commit**

Run:

```bash
git add docs/SESSION_SUMMARY.md
git commit -m "docs: refresh session summary for web-only cleanup"
```

---

### Task 7: Final Verification for Batch 1

**Files:**

- Read: `.gitignore`
- Read: `README.md`
- Read: `docs/IMPLEMENTATION_PLAN.md`
- Read: `docs/SESSION_SUMMARY.md`
- Read: `docs/web_only_reference_matrix.md`
- Read: `scripts/run_web.sh`
- Test: backend, frontend, CLI help, keyword scans

- [ ] **Step 1: Run CLI checks**

Run:

```bash
.venv/bin/ai-novelist --help
.venv/bin/ai-novelist chat --help
```

Expected:

- first command lists only `{web}`
- second command exits with code `2` and reports `invalid choice: 'chat'`

- [ ] **Step 2: Run deleted-command scans against active docs**

Run:

```bash
rg -n "ai-novelist (chat|compose|feishu|research|write-chapter|finalize-chapter|export|show)" README.md docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
```

Expected:

- no matches

- [ ] **Step 3: Run focused runtime-default test**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_runtime_defaults.py -q
```

Expected:

- `1 passed`

- [ ] **Step 4: Run full backend suite**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected:

- all tests pass

- [ ] **Step 5: Run frontend build**

Run:

```bash
npm --prefix web/frontend run build
```

Expected:

- build succeeds
- Vite may print the known CJS Node API deprecation warning

- [ ] **Step 6: Confirm no local artifact pollution**

Run:

```bash
git status --short
git check-ignore -v .superpowers
```

Expected:

- no `?? .superpowers/`
- `git check-ignore -v .superpowers` points to `.gitignore`

- [ ] **Step 7: Commit any missed verification-doc adjustments**

If verification required correcting a documentation line, commit it:

```bash
git add README.md docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md docs/web_only_reference_matrix.md scripts/run_web.sh tests/test_web_runtime_defaults.py .gitignore
git commit -m "docs: complete web-only cleanup verification"
```

If no files changed after the previous commits, do not create an empty commit.

