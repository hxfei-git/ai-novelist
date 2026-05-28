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
