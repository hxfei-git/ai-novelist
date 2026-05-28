# Architecture, Web Behavior, and Context Remediation Design

## Status

Approved design scope from user:

- Use the aggressive remediation boundary: core architecture, Web UI behavior, context precision, frontend structure, backend structure, and tests may all change.
- Keep the existing Web runtime entry point and project data layout compatible.
- Every implementation phase must end with a written phase summary, verification results, documentation updates, and a Git commit.
- After each phase, prepare a compact continuation summary so work can resume after context compression without losing the next step.

## Baseline

The current baseline before implementation:

- Branch: `main`, clean working tree, ahead of `origin/main` by 45 commits.
- Python verification: `.venv/bin/python -m pytest -q` passes with `230 passed`.
- Frontend verification: `npm --prefix web/frontend run build` passes with the known Vite CJS Node API deprecation warning.
- The project is Web-first. The runtime command remains `.venv/bin/ai-novelist web`.

Observed hotspots:

- `src/ai_novelist/state.py` keeps persistent project state, runtime state, Director fields, legacy compatibility, Craft metadata, review state, and a broad `director_task_args` scratch dictionary in one dataclass.
- `src/ai_novelist/graph_outline.py` is the largest runtime file and mixes outline orchestration, prompt construction, stage routing, compatibility handling, structural repair, and `review_lock` support.
- `src/ai_novelist/web/service.py` still owns project, progress, outline, chapter outline, chapter generation, review, repair, and path utilities.
- `web/frontend/src/main.tsx` is still a single large component with many unrelated state variables, API calls, action handlers, and render branches.
- `src/ai_novelist/context_builder.py` has useful context profiles, but source manifests do not carry reliable real source paths, and duplicate content can still enter through artifact lookup plus state fallback.

## Confirmed Risk Areas

### Web UI Behavior

The implementation must audit and fix Web operations that can appear to do nothing or behave inconsistently:

- Project creation currently clears the progress log through a helper that reads the old `projectId` closure.
- Chapter detail loading sets `loadingChapter` but does not guarantee reset on request failure or stale request return.
- Chapter batch generation lacks an explicit running state, so repeat clicks can start overlapping batch actions.
- Chapter workspace volume switching and chapter detail switching have partial request token protection but not complete protection across all async branches.
- Some actions catch and display errors, while others rely on outer `.catch(showError)` or leave the UI state reset to `finally`; this needs consistency.
- SSE errors must reliably appear in the progress panel and must always release loading or running flags.

### Context Precision and Redundancy

The implementation must prove that context used by each stage is targeted and non-redundant:

- `ContextBundle.sources` must include useful source type, section, real path where available, digest, original size, included size, and truncation flag.
- The same semantic source must not be injected twice through artifact lookup and state fallback.
- Chapter planning must include the selected chapter outline slice, not adjacent chapter slices.
- Direct chapter writing should use the same context profile machinery instead of a separate hand-assembled context path.
- Context manifests should be saved or exposed in a way that lets future audits explain exactly what an agent saw.
- Tests must cover precision and redundancy, not only maximum length and presence of expected strings.

## Recommended Strategy

Use a test-guarded aggressive refactor:

1. Add failing tests and audit assertions for the highest-risk Web and context behavior.
2. Fix behavior and structure in phases, keeping public API paths stable.
3. Split large modules only when a phase already touches their responsibilities.
4. After every phase, run focused verification, update docs, commit, and produce a compact phase summary.
5. End with broad verification and final cleanup.

This keeps the aggressive scope while preserving recoverability during a long unattended run.

## Target Architecture

### Backend Web Services

Keep FastAPI route paths stable in `src/ai_novelist/web/app.py`. Move behavior behind clearer service modules:

- `web/project_service.py`: project listing, project creation, onboarding idea, project state, progress log.
- `web/outline_actions.py`: ordinary outline stage payloads, save, generate, revise, lock, pending questions.
- `web/chapter_outline_actions.py`: chapter outline workspace, per-volume generate/revise/lock, chapter outline review and apply.
- `web/chapter_actions.py`: chapter batch workspace, batch generation, chapter list, chapter detail.
- `web/review_actions.py`: outline review, global chapter review, repair suggestion normalization, repair application.
- `web/service.py`: temporary compatibility facade while routes and tests migrate.

Each module should expose a small public API and keep route-independent logic testable without FastAPI.

### Outline Graph

Split `graph_outline.py` by responsibility while preserving behavior:

- Stage routing and user-intent parsing.
- Prompt construction and stage boundary instructions.
- Stage output normalization and structural repair.
- Stage artifact persistence and memory extraction.
- `review_lock` compatibility helpers.
- Chapter outline volume metadata helpers.

The first refactor should avoid semantic rewrites. Behavior changes belong in explicit tests.

### State and Workflow Payloads

Reduce raw `director_task_args` usage by adding typed or named helper accessors before removing fields:

- Chapter batch payload: volume, run id, selected chapters, latest drafts, repair outputs.
- Chapter plan payload: selected chapter outline, pacing target, planning context, agent reports.
- Chapter write payload: selected chapter outline, direct context, draft metadata.
- Outline payload: stage, chapter outline metadata, forced full generation, internal request.
- Craft payload: warnings, brief paths, source paths, similarity reports.

The initial goal is not to delete `director_task_args` outright. The goal is to stop spreading new raw dictionary reads and make each workflow boundary explicit and testable.

### Context System

Context building should become manifest-first:

- Every profile has a clear purpose and allowed source set.
- Source extraction returns structured source records before rendering text.
- Deduplication happens by digest and source priority before truncation.
- Rendering preserves protected sections such as user request, task summary, and locked constraints.
- Real artifact paths are recorded when loaded from disk.
- State fallback records `state:<field>` as a source path equivalent.
- Agent calls that depend on context store a compact context manifest alongside existing digest/report metadata.

Direct chapter context should move to this system so chapter planning, drafting, review, revision, and bible update all share one inspection model.

### Frontend

Split `main.tsx` into focused parts:

- Project workspace hook and project sidebar.
- Outline workspace hook and components.
- Chapter outline workspace hook and components.
- Chapter workspace hook and components.
- Progress log hook.
- SSE/action helper wrapper with consistent error handling.

Fix UI action behavior while splitting:

- Avoid stale project id after creating or switching projects.
- Add running guards and disabled states for chapter batch generation and repair actions.
- Ensure every async load has a reset path for loading state.
- Use request tokens or equivalent guards wherever stale async responses can overwrite current state.
- Keep visible UI behavior compatible unless a test proves the old behavior is wrong.

## Data Flow

### Web Action Flow

1. Component action handler validates local state and sets a running flag.
2. API wrapper performs HTTP or SSE request.
3. Progress events are normalized and appended or merged in the progress log.
4. Done payload is used when available to refresh the exact changed workspace.
5. Errors are shown in the progress log and release all running/loading flags.
6. Follow-up refreshes use current project, volume, stage, and request token state.

### Context Flow

1. Workflow chooses a named profile.
2. Profile source collector returns candidate sources.
3. Deduplication removes same digest sources according to priority.
4. Renderer applies per-section budgets and protected-section rules.
5. Context bundle records text, sources, total chars, estimated tokens, and truncation.
6. Workflow stores digest and compact manifest for later audit.

## Error Handling

- `LocalStoreError` remains the main user-facing service error type for invalid Web operations.
- Frontend API errors must be rendered in the progress log with enough detail to explain which operation failed.
- SSE `error` events must throw in `streamAction`, and all callers must catch or release state through `finally`.
- Long-running buttons must be disabled while their operation is active.
- Request failures must not leave loading indicators permanently active.

## Testing Strategy

Use test-driven implementation per phase:

- Web service tests for route-to-service payload shape and error paths.
- Frontend source or component tests for action guards, stale request protection, and disabled states.
- Context builder tests for real source paths, deduplication, profile precision, and direct chapter context migration.
- Graph tests for unchanged outline stage behavior after module extraction.
- Focused tests after each phase.
- Final verification with `.venv/bin/python -m pytest -q` and `npm --prefix web/frontend run build`.

If a real browser behavior test is necessary, add the smallest practical browser smoke setup and document why static tests were insufficient.

## Implementation Phases

### Phase 0: Audit Harness

Add tests and audit helpers that fail for the highest-risk findings:

- Web action stale project id and loading reset.
- Chapter batch repeated submit guard.
- SSE error propagation and UI state release.
- Context source path recording.
- Context duplicate suppression.
- Stage-specific context precision.

Exit conditions:

- Focused tests demonstrate current risks.
- Documentation records the audit scope.
- Commit contains only tests, audit helpers, and docs unless a tiny fixture change is required.
- Phase summary is written for context compression.

### Phase 1: Web Operation Logic

Fix Web behavior without broad structural movement:

- Correct project creation and progress log project scoping.
- Add running state and disabled guard for chapter batch generation.
- Harden loading reset for chapter detail, stage load, chapter outline workspace, and chapter workspace.
- Normalize error reporting across Web actions.
- Ensure done payload refresh targets the correct stage, volume, or chapter.

Exit conditions:

- Focused Web tests pass.
- Frontend build passes if frontend code changed.
- Docs and phase summary updated.
- Commit created.

### Phase 2: Context Precision

Refactor context collection to source-manifest-first behavior:

- Add source records with real paths.
- Deduplicate repeated content by digest and priority.
- Add manifest storage for key agent calls.
- Move direct chapter context onto a named context profile.
- Add tests for chapter planning slice precision and no duplicate artifact/state fallback content.

Exit conditions:

- Focused context and chapter graph tests pass.
- Docs and phase summary updated.
- Commit created.

### Phase 3: State and Payload Access

Add explicit workflow payload helpers and replace high-risk raw `director_task_args` access:

- Chapter batch payload helpers.
- Chapter planning payload helpers.
- Chapter writing payload helpers.
- Outline stage metadata helpers.
- Craft metadata helper where it intersects context.

Exit conditions:

- Existing state compatibility tests still pass.
- Raw dictionary access is reduced and documented where retained.
- Docs and phase summary updated.
- Commit created.

### Phase 4: Backend Service Split

Extract Web service modules while keeping route behavior stable:

- Move project/progress functions.
- Move outline stage actions.
- Move chapter outline actions.
- Move chapter actions.
- Move review and repair actions.
- Keep compatibility imports during transition if needed.

Exit conditions:

- Web service and app tests pass.
- Public route paths unchanged.
- Docs and phase summary updated.
- Commit created.

### Phase 5: Outline Graph Split

Extract `graph_outline.py` helpers by responsibility:

- Prompt builders.
- Stage routing and intent detection.
- Stage repair and structure enforcement.
- Artifact rendering and memory extraction.
- Review lock helpers.
- Chapter outline metadata helpers.

Exit conditions:

- Graph, outline service, prompt loader, and related tests pass.
- No intended behavior change unless covered by tests.
- Docs and phase summary updated.
- Commit created.

### Phase 6: Frontend Structure Split

Break the frontend entry file into hooks and components:

- API/action hooks.
- Sidebar and progress components.
- Outline workspace.
- Chapter outline workspace.
- Chapter workspace.
- Review and repair components.

Exit conditions:

- Frontend structural tests updated.
- Frontend build passes.
- Relevant Web tests pass.
- Docs and phase summary updated.
- Commit created.

### Phase 7: Final Verification and Cleanup

Run final verification and remove residual scaffolding:

- Full pytest.
- Frontend build.
- Focused Web smoke where available.
- Scan for unresolved placeholders, accidental generated files, and stale imports.
- Final docs update and final summary.

Exit conditions:

- Working tree clean after final commit.
- Final summary lists completed phases, verification commands, remaining risks, and next recommended work.

## Phase Summary and Context Compression Contract

At the end of every phase, write a summary that includes:

- Phase name and commit hash.
- Files changed.
- Behavior changed.
- Tests run and exact result.
- Known risk or deferred item.
- Next phase entry point.
- Compact continuation note suitable for context compression.

The continuation note must be short enough to paste into a resumed session and specific enough to avoid rediscovering completed work.

## Documentation Requirements

Every code phase must update:

- `docs/IMPLEMENTATION_PLAN.md` for architecture, workflow, state, CLI, adapter, prompt, or persistence changes.
- `docs/SESSION_SUMMARY.md` for implementation notes, test results, limitations, and phase summaries.

Design and plan documents belong under `docs/superpowers/`.

## Risks

- Aggressive refactoring can create cross-workflow regressions because outline, chapter generation, review, and context share state.
- Frontend behavior tests are currently mostly static, so some UI issues may require adding a browser smoke dependency.
- Reducing `director_task_args` must preserve existing project compatibility.
- Splitting `graph_outline.py` may create import cycles unless modules are cut by dependency direction.

Mitigation:

- Add focused tests before each behavior change.
- Preserve route and data compatibility.
- Commit after each phase.
- Keep compatibility facades while moving internals.
- Use context compression checkpoints between phases.

## Out of Scope

- Changing the public Web URL layout.
- Removing old project compatibility without fixture coverage.
- Replacing the model provider system.
- Redesigning the visual appearance of the Web UI beyond what is needed for correct behavior.
- Deleting prompts solely because static search does not find direct references.
