# Outline Review Context Cleanup Design

## Problem

The `demo-web` outline review can report a `stop` decision with claims that versions 0, 1, and 2 are duplicated and mutually inconsistent. This comes from the review context, not just from the model:

- `build_outline_prompt()` injects the last three `outline_versions` as `版本 0/1/2`, which lets the reviewer treat historical revisions as active outline text.
- Applying outline review fixes can save an `outline_reviser` patch-style response (`修订摘要` / `变更区块`) as `outline.md`, so later reviews inspect a revision log instead of a single effective outline.
- Repair suggestion deduplication uses `message + recommendation`, so the same issue with two similar recommendations appears twice.
- High-priority continuation runs whenever exactly 10 high-priority suggestions are parsed, which can amplify one review into many high-priority-only items.
- `projects/demo-web` already contains the polluted current outline and state.

## Goals

- Future overall outline reviews should inspect one effective outline, not recent historical versions as peer drafts.
- Applying review suggestions should not overwrite the effective outline with a patch-only revision record.
- Duplicate repair suggestions should be collapsed at the issue level.
- High-priority continuation should run only for explicit truncation, not just because a model listed 10 items.
- `projects/demo-web` should be restored to a single effective outline that can be reviewed again.
- Tests and docs should cover the behavior change.

## Non-Goals

- Redesigning the frontend review workspace.
- Introducing a full snapshot/patch/baseline storage model.
- Rewriting all generated project artifacts unrelated to `demo-web` recovery.
- Changing chapter outline review behavior unless it shares the same helper and needs compatible test updates.

## Design

### Review Prompt Context

For `outline_editor`, the prompt should emphasize the current effective outline and should not include `最近大纲版本` as numbered `版本 0/1/2` blocks. Historical versions may remain available to other agents that need revision context, but the overall reviewer should not receive them in a form that looks like active content.

Implementation should keep the change narrow by updating `build_outline_prompt()` or adding a prompt-specific branch for `outline_editor`. The reviewer still receives title, idea, worldbuilding, current outline, revision instruction, locked constraints, style preferences, reference brief, retrieval context, and editor notes.

### Revision Apply Guard

When applying an outline review, the saved `outline.md` must remain a single effective outline. The preferred implementation is to force `outline_reviser` to output a complete effective outline in this path by setting a clear revision instruction before calling the reviser. After the reviser returns, validate that the result is not only a patch shell.

Patch-shell detection should be conservative. A result is unsafe to save as the effective outline when it primarily contains headings like `修订摘要`, `变更区块`, `保留约束`, and `未改动内容`, and lacks the expected outline stage sections. Unsafe output should fail with a clear `LocalStoreError` instead of overwriting the current outline.

### Repair Suggestion Deduplication

Deduplicate outline repair suggestions by normalized issue message first. If two items have the same normalized message but different recommendations, keep the first parsed recommendation for stability. This prevents duplicate rows such as:

- "版本2中“修订摘要”与“变更区块”内容重复，冗余" with "精简..."
- the same message with "删除..."

Normalization should trim whitespace and punctuation variants only enough to catch exact issue duplicates without merging distinct problems.

### High-Priority Continuation

Continuation should not trigger solely because the first batch contains 10 high-priority items. The trigger should require an explicit truncation signal, such as a report ending without required later sections, an adapter-level truncation marker if available, or another deterministic condition that proves the model output was cut off.

If no reliable truncation signal exists today, disable automatic continuation for now. The prompt already allows up to 50 high-priority items in one response, so a normal complete report with 10 high-priority issues should be accepted as complete.

### `demo-web` Cleanup

Restore `projects/demo-web` to a single effective outline. The cleaned outline should remove the revision-log wrapper and version-cleanup language, while preserving the latest accepted story decisions from the current `outline.md` where possible.

Update local state so subsequent reviews load the cleaned outline instead of the polluted patch shell:

- `projects/demo-web/outline.md`
- `projects/demo-web/state.json` fields that mirror the active outline, latest director message, and outline versions as needed
- Any minimal artifact metadata needed to stop old polluted review summaries from being treated as active state

Existing review history can remain as historical evidence unless it directly re-pollutes the current review source.

## Data Flow

1. User starts overall outline review.
2. `outline_review_source_text()` returns one effective outline.
3. `review_outline_node()` builds an `outline_editor` prompt without numbered historical versions.
4. The editor returns a structured priority report.
5. `build_outline_repair_suggestions()` parses and deduplicates issue-level suggestions.
6. Continuation is skipped unless deterministic truncation is detected.
7. Applying selected suggestions asks the reviser for a complete effective outline and validates before saving.

## Error Handling

- If reviser output is patch-only, raise `LocalStoreError` with a message explaining that the effective outline was not overwritten.
- If `demo-web` cleanup finds missing expected files, fail the cleanup step and leave source files unchanged.
- If a review has no low-priority or suggestion items, the frontend may continue to show only populated groups. This is correct; the fix is to prevent high-priority overproduction, not to invent lower-priority issues.

## Tests

Add focused tests covering:

- `outline_editor` prompt does not include numbered recent outline versions.
- duplicate repair suggestions with the same message collapse to one item.
- high-priority continuation does not run merely because there are exactly 10 high-priority suggestions.
- applying an outline review refuses patch-only reviser output or forces complete-outline output, depending on implementation.
- `demo-web` cleaned review source is a single effective outline and does not include `版本0/版本1/版本2` cleanup language.

Run targeted pytest selections for outline review helpers/actions and any affected web service tests. Run a `demo-web` mock review or equivalent smoke check if available without real Codex calls.

## Documentation

Update:

- `docs/IMPLEMENTATION_PLAN.md` with architecture/workflow changes.
- `docs/SESSION_SUMMARY.md` with implementation notes, verification scope, and remaining risk.

## Acceptance Criteria

- A new overall outline review for `demo-web` no longer claims that versions 0, 1, and 2 coexist as active outlines.
- `demo-web/outline.md` is a single effective outline, not a revision-summary document.
- Duplicate same-message repair suggestions appear once.
- A complete report with exactly 10 high-priority issues does not automatically append more high-priority-only issues.
- Tests and docs are updated.
- Changes are committed after implementation.
