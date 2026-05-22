# Repository Guidelines

## Project Structure & Module Organization

This is a Python CLI project using a `src/` layout. Runtime code lives in `src/ai_novelist/`: `cli.py` defines the command entry point, `state.py` stores workflow state models, `graph_minimal.py` and `graph_writer.py` contain LangGraph workflows, and `adapters/` wraps external model execution such as Codex CLI. Prompt templates are package data under `src/ai_novelist/prompts/*.md`. Local persistence is implemented in `src/ai_novelist/storage/`.

Tests live in `tests/`, with unit tests named `test_*.py` and smoke checks named `smoke_*.py`. Generated demo outputs and local project state are under `projects/<project>/`, including `state.json`, `outline.md`, `worldbuilding.md`, and chapter files.

## Build, Test, and Development Commands

- `.venv/bin/ai-novelist --help`: inspect available CLI commands.
- `.venv/bin/ai-novelist chat --project demo-chat --mock`: run the Director chat flow without real Codex calls.
- `.venv/bin/ai-novelist compose --project demo-compose --idea "..." --chapter 1 --mock --auto-approve`: run the full mock drafting workflow.
- `.venv/bin/python -m pytest`: run the unit test suite.
- `.venv/bin/python tests/smoke_phase2.py`: run a targeted smoke scenario.

Use `--mock` for fast, deterministic checks. Omit it only when validating real `codex exec` integration.

## Coding Style & Naming Conventions

Target Python 3.11+ and keep code compatible with the existing Python 3.12 virtual environment. Follow PEP 8 with 4-space indentation, snake_case functions and modules, PascalCase classes, and concise type hints where they clarify data flow. Keep prompt names descriptive and lowercase, for example `chapter_writer.md`. Prefer small workflow functions and adapters over large cross-cutting modules.

## Testing Guidelines

Use `pytest` for unit coverage. Add tests beside related behavior in `tests/test_*.py`; reserve `smoke_*.py` for end-to-end CLI or workflow checks. Prefer mock mode in tests so Codex CLI is not required. When changing graph routing, persistence, or prompt loading, add or update focused tests and run both `pytest` and the relevant smoke script.

## Documentation Requirements

This is a hard requirement: every code change must update the relevant documentation in `docs/`. Architecture, workflow, state, CLI, adapter, prompt, or persistence changes must update `docs/IMPLEMENTATION_PLAN.md`; implementation notes, test results, and remaining limitations must update `docs/SESSION_SUMMARY.md`. Do not consider a code change complete until the docs are updated in the same change set.

## Commit & Pull Request Guidelines

This checkout does not include Git history, so follow clear conventional-style commits such as `feat: add chapter planning route` or `fix: preserve state on review failure`. After every completed modification, create a new Git commit that includes the relevant code, tests, and documentation updates. Pull requests should include a short summary, affected commands or workflows, test results, and any generated project artifacts worth reviewing. Link issues when applicable and include screenshots only for future UI-facing changes.

## Security & Configuration Tips

Do not commit secrets, local Codex credentials, or machine-specific virtual environment files. Treat `projects/` as generated local data unless a fixture is intentionally needed for tests or documentation.
