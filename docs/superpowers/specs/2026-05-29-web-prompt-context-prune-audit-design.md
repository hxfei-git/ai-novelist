# Web Prompt Context Prune Audit Design

Date: 2026-05-29
Project: `/home/ubuntu/1.project/ai-novelist`

## Purpose

Run a focused, roughly four-hour audit and cleanup pass for the current Web-only AI Novelist project. The work must identify architecture problems, Web logic errors, obsolete generation prompts, repeated or redundant prompt rules, and context mismatches between outline generation and chapter-body drafting.

The cleanup direction is strict: keep only paths proven reachable from the current Web runtime, and delete old prompts, mock branches, adapter agent branches, helper functions, tests, or facade exports that only support removed or unreachable flows.

## Current Evidence

The active runtime command is `ai-novelist web`. The active surfaces are:

- FastAPI app and routes in `src/ai_novelist/web/app.py`
- Web workflow action modules under `src/ai_novelist/web/`
- React frontend under `web/frontend/src/`
- outline stage generation and locking through `src/ai_novelist/graph_outline.py`
- chapter-outline volume generation through the same outline graph
- chapter batch drafting through `src/ai_novelist/graph_volume_write.py`
- direct chapter prompt/context construction through `src/ai_novelist/graph_chapter_write.py`
- novel bible update hooks reached by outline finalization in `src/ai_novelist/graph_bible.py`
- Author Craft helpers only where they are reached by retained outline or chapter context paths

The current scan shows several cleanup and risk areas:

- `src/ai_novelist/prompts/*.md` is still dynamically loaded, so prompt deletion needs a manifest-backed proof.
- `src/ai_novelist/prompts/__init__.py` still lists old agent names such as `continuity_editor`, `structure_editor`, `character_arc_editor`, `style_editor`, `simulated_reader`, and `pacing_guard_editor`, while matching prompt files are absent.
- `src/ai_novelist/adapters/mock_codex.py` still contains responses for old Director, research, export, finalize, revision, and editor agents.
- `src/ai_novelist/adapters/deepseek.py` still categorizes old editor agents that are not part of the current prompt set.
- `src/ai_novelist/graph_outline.py` still contains old Director/show/status helpers and parses actions that are not exposed by current Web routes.
- `src/ai_novelist/web/service.py` is now a compatibility facade; after route imports are proven direct, unused facade exports can be removed.
- `src/ai_novelist/state.py`, `LocalStore`, and context helpers retain research/export fields and path helpers that may no longer serve the active Web runtime.
- `ContextBundle` coverage exists for direct drafting, but the audit must verify that batch drafting, review apply, and chapter repair do not silently use stale whole-outline or fallback content when a chapter-specific slice is required.

## Goals

1. Produce a concrete active-path evidence matrix for prompts, graph nodes, Web actions, frontend actions, adapter agent branches, state fields, and persistence helpers.
2. Delete unused prompt files and unused prompt policy entries after proving they are not loaded by retained Web paths.
3. Delete unreachable old branches, especially old Director/chat/research/export/finalize/show behavior and related mock or adapter branches.
4. Find and fix Web logic errors that affect long-running generation, review apply, chapter-outline application, chapter batch selection, SSE error handling, and running/loading state cleanup.
5. Find and fix outline-to-body context mismatches where chapter body generation can receive the wrong outline slice, stale artifacts, duplicated context, or unprotected fallback content.
6. Reduce prompt redundancy where repeated restrictions are better represented by a shared partial, registry, or narrowly scoped prompt contract.
7. Update docs and tests in the same change set, then commit each completed modification.

## Non-Goals

- Do not preserve removed CLI flows such as `chat`, `compose`, `research`, `export`, `show`, or one-off write/finalize commands.
- Do not retain old prompt files or mock responses solely because old tests assert them.
- Do not redesign the product UI or add new workflows.
- Do not remove active Author Craft behavior that is reached from retained outline or chapter context paths.
- Do not delete generated project data under `projects/`.

## Retention Rule

A file, prompt, branch, or exported helper is retained only if one of these is true:

- It is reachable from an active Web API route in `src/ai_novelist/web/app.py`.
- It is reachable from the React frontend through an active API call or streaming action.
- It is used by a retained graph node called by active Web actions.
- It is required by retained storage, context, prompt loading, adapter execution, or current tests that cover active Web behavior.
- It is package infrastructure required for installation or runtime startup.

Everything else becomes a deletion candidate. Compatibility with old `state.json` files is not a default retention reason for this cleanup. If old-state compatibility blocks meaningful cleanup, the implementation should either migrate the field to an active contract or delete the compatibility path with tests updated to the new Web-only boundary.

## Four-Hour Work Plan

### Phase 1: Evidence Matrix, 0-45 Minutes

Build a table for:

- all prompt files and `load_prompt()` names
- all `AGENT:` headers emitted from code
- mock and DeepSeek agent classification branches
- Web routes and their service/action call targets
- graph entry points and helper functions
- frontend actions and API endpoints
- state fields and `LocalStore` helpers that still mention research, export, finalize, or old Director flows

For each item, mark `retain`, `delete`, or `fix`. The matrix should be committed or recorded in `docs/web_only_reference_matrix.md`.

### Phase 2: Prompt And Dead Branch Prune, 45-120 Minutes

Expected deletion candidates include:

- prompt files not referenced by the retained prompt manifest
- `AUTHOR_CRAFT_POLICY_PROMPTS` entries for missing or deleted prompts
- mock responses for old Director, research, export, finalize, and non-Web revision agents
- DeepSeek agent-category entries for deleted agents
- old `graph_outline.py` Director/show/status helpers that no active Web route calls
- tests that only protect deleted behavior

After this phase, there should be a single prompt registry or manifest that names every allowed runtime prompt. A test should fail if a prompt file exists without registry membership, if the registry points to a missing file, or if active code loads a prompt outside the registry.

### Phase 3: Web Logic Audit And Fixes, 120-180 Minutes

Review the following flows against current code and tests:

- outline stage generate, revise, lock, and pending-question submit
- outline review latest, apply, idempotency, and selected decisions
- chapter-outline volume generate, revise, lock, review, and apply
- chapter batch workspace, requested chapter count, remaining chapter selection, and volume switching
- global chapter review, proposal generation, selected repair apply, and chapter refresh
- SSE worker errors, structured progress events, frontend running flags, and transient refresh failures

Fix defects found during this audit. Add focused tests for each bug before or with the fix.

### Phase 4: Outline-To-Body Context Audit And Fixes, 180-225 Minutes

Trace the context path from locked outline stages to body drafting:

```text
outline stages
  -> chapter_outline artifact and metadata
  -> selected chapter outline slice
  -> direct_chapter_drafting ContextBundle
  -> direct_chapter_writer and chapter_auto_reviser prompts
  -> saved draft and batch manifest context manifest
```

The audit must prove:

- body generation receives only the intended chapter slice, not a whole volume unless the slice cannot be parsed
- fallback text is explicit and visible in the context manifest
- repeated artifact/state fallback content is deduplicated
- protected sections such as current request and locked constraints cannot be dropped before ordinary context
- chapter-outline review apply updates the artifact used by later body generation
- context manifests are saved for both direct and batch drafting paths

If any proof is missing, add tests and fix the implementation.

### Phase 5: Verification, Docs, And Commit, 225-240 Minutes

Run focused tests first, then broaden only as needed:

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py tests/test_mock_codex_adapter.py tests/test_deepseek_adapter.py -q
.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_web_chapter_service.py tests/test_web_outline_service.py -q
.venv/bin/python -m pytest tests/test_context_builder.py tests/test_graph_volume_write.py tests/test_workflow_payloads.py -q
npm --prefix web/frontend run build
```

Run full pytest if state, persistence, prompt registry, graph contracts, or shared context behavior changed:

```bash
.venv/bin/python -m pytest -q
```

Update:

- `docs/IMPLEMENTATION_PLAN.md`
- `docs/SESSION_SUMMARY.md`
- `docs/web_only_reference_matrix.md`
- this spec's implementation plan counterpart under `docs/superpowers/plans/`

Commit every completed modification with a conventional-style message.

## Architecture Design

The retained architecture should be:

```text
Browser
  -> web/frontend/src/*
  -> FastAPI routes in web/app.py
  -> focused Web action modules
  -> retained graph entry points
  -> prompt registry and prompt files
  -> model adapter
  -> LocalStore project artifacts
```

`web/service.py` should not remain the primary boundary. If route call sites can import focused action modules directly without circular imports, the implementation should remove unused facade exports and update tests accordingly.

Prompt access should move from open-ended dynamic names toward explicit registry membership. Dynamic helper functions may remain only if they validate against the registry.

## Prompt Design

Prompts should be grouped by retained workflow:

- outline stage generation and revision
- outline review and selected repair
- chapter-outline generation and review
- direct chapter drafting and auto revision
- volume consistency check and blocker repair
- human repair from retained Web flows
- novel bible extraction/conflict/synthesis if still reached by retained outline finalization
- Author Craft extraction and stage brief if still reached by retained context

Repeated prompt rules should be consolidated only when consolidation reduces drift without weakening local stage contracts. The shared Author Craft partial can remain, but stale policy entries must be removed.

## Error Handling Design

Long-running Web actions should follow one contract:

- backend streaming actions emit `progress`, then either `done` or `error`
- frontend action handlers catch errors through `showError(error)`
- running/loading flags are released in `finally`
- transient background refresh errors use `showBackgroundError(error)`
- duplicate long-running submissions are guarded in the UI and, where the operation mutates shared artifacts, guarded in the backend

## Testing Design

Tests should prove behavior, not preserve old code shape. When a branch is deleted, tests that only assert the deleted branch should be removed or rewritten around retained Web behavior.

Required regression categories:

- prompt registry completeness and no orphan prompt files
- mock/DeepSeek branch set matches retained prompt registry or generated `AGENT:` headers
- Web route streaming errors surface as SSE error events
- review apply is idempotent where repeat clicks are possible
- chapter-outline review apply updates the artifact later used by body generation
- chapter batch generation selects the requested remaining chapters for the selected volume
- context manifests include chapter-specific outline sources and protected sections

## Success Criteria

The cleanup is complete when:

- no prompt file exists outside the retained registry
- no retained prompt registry entry points to a missing file
- no old Director/chat/research/export/finalize/show branch is reachable from source except historical docs
- Web routes and frontend actions still cover the supported workflows
- chapter body generation is backed by a chapter-specific context manifest
- focused tests and required builds pass
- full pytest passes if shared contracts changed
- docs describe the new retained boundary and removed items
- `git status --short` is clean after the final commit

## Risks

- Some tests currently protect compatibility facades or old branch names. The implementation should update those tests instead of keeping dead code.
- Prompt deletion can break dynamic loading if the registry is incomplete. This is why the first implementation step is a manifest-backed proof.
- Removing old state fields can break existing local projects. This cleanup accepts that risk unless the field is actively used by current Web routes.
- The four-hour window may not be enough to remove every compatibility field safely. If time runs out, prioritize prompt registry cleanup, unreachable branch deletion, and context correctness over large state migrations.
