# Web-Only Prune Design

Date: 2026-05-27
Status: Approved for implementation

## Goal

Remove every chat-centric and non-web runtime path from the repository so the project is maintained as a web-only application.

The retained product surface is:

- `ai-novelist web`
- the web API and frontend
- the file-backed outline / chapter / review workflows that the web app already uses
- shared storage, state, adapter, prompt, and outline modules that the web app still depends on

Everything else should be deleted rather than disabled.

## Scope

Remove:

- `chat` command and all Director-specific code
- `feishu` command and bot/session helpers
- `compose`, `outline`, `plan-*`, `write-*`, `review`, `finalize-chapter`, `export`, `show`, and other non-web CLI paths
- research-only and author-craft-only runtime entrypoints that are not directly used by web
- chat-only helpers, prompt templates, and state fields that only exist to support the deleted flows
- chat-oriented tests and smoke scripts
- README / implementation docs / session summary content that describes deleted flows as active

Keep:

- `web` CLI entrypoint and FastAPI app
- `src/ai_novelist/web/service.py` and `src/ai_novelist/web/app.py`
- outline, chapter outline workspace, chapter batch generation, global chapter review, outline review, and repair application flows used by web
- storage, state, artifact, prompt-loader, and adapter code needed by those retained flows

## Design

Use a hard cut, not a compatibility layer.

1. Delete the CLI subcommands that are not needed by web.
2. Remove unused modules and their imports instead of leaving dead branches behind.
3. Trim `NovelState` to the fields still persisted by web.
4. Keep the web service behavior intact and update the frontend only where deleted routes or data shapes force it.
5. Remove tests that exercise deleted runtime paths; keep and tighten tests that cover web-only behavior.

This approach is intentionally aggressive because the project goal is to simplify maintenance, not preserve command-line compatibility.

## Validation

The implementation is complete when:

- `ai-novelist --help` only exposes `web`
- the web app still builds and serves the existing project / outline / chapter workflows
- removed routes, commands, and tests no longer exist in the tree
- the remaining test suite passes for the retained web surface

Expected checks:

- Python unit tests for `web/`, storage, state, outline, and chapter review paths
- frontend build
- a narrow smoke test for the retained web app if one already exists

## Risks

- A shared helper may look chat-specific but still be used by web. The implementation should verify each deletion against actual web imports.
- Trimming `NovelState` too far could break persisted projects. Keep only fields that are still read by `web/service.py` and its retained helpers.
- Removing many tests may reduce coverage temporarily. The retained web tests should be audited after deletion so the remaining surface still has direct coverage.
