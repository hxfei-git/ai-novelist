# Outline Web Fixes Design

Date: 2026-05-28

## Goal

Fix three Web outline workbench issues as one coherent behavior update:

- Outline stage pending questions must continue across rounds until no remaining questions block locking.
- The right progress log must keep one live row per task and replace `running` with the final status, elapsed time, token estimate, and context estimate.
- Applying an outline-wide review must save a new outline baseline into the stage source files, so a later manually triggered review uses the updated outline.

## Non-Goals

- Do not automatically start another outline review after apply. A new review only starts when the user clicks "大纲总体审查" again.
- Do not redesign the page layout.
- Do not add a rollback system or a database-backed transaction layer.
- Do not change model prompts beyond what is needed to preserve the existing selected-issue apply behavior.

## Pending Question Loop

Pending questions remain a lock blocker for the active outline stage. After the user submits one round of answers, the backend reruns the current stage revision and then recollects remaining questions from the same sources already used by the Web payload:

1. `state.outline_stage_artifacts[stage].pending_questions`
2. `state.pending_questions` when the state is still on the same stage
3. The stage Markdown section named `待确认问题`, `待确认的问题`, or `仍需确认的问题`

The Web client must treat answer submission as a loop, not as a terminal action. After submit it refreshes the current stage payload. If the refreshed payload contains pending question items, the panel stays visible with the new round. If there are no pending question items, the panel clears and the stage action state controls whether the stage can be locked.

Acceptance:

- A generated or revised stage shows all pending questions collected for that round.
- Submitting answers can produce another pending-question round.
- The lock action remains disabled while any pending question remains.
- The pending panel disappears only after the refreshed stage payload has no pending questions.

## Progress Log

The progress sidebar uses one row per task. Each SSE progress event is normalized to a stable key. Prefer a backend-provided key if available; otherwise use the progress label as the compatibility key.

When the client receives a `started` or `running` event, it creates or updates that row. When it receives `completed` or `error`, it updates the same row instead of prepending another row. Persisted project progress remains in `web_progress_log.json`, but it should contain the final merged rows rather than stale running rows.

Display format:

```text
大纲总体审查
completed · 12.4s · tok≈8.2K · ctx=4.1K/258K
```

If token or context data is missing, show the available fields:

```text
大纲审查应用
completed · 3.1s
```

Acceptance:

- A completed task does not leave an older `running` row behind.
- The start and completion of the same stage node do not produce duplicate visible rows.
- Completed rows show elapsed time when available, and token/context estimates when present.
- Refreshing the page restores the merged final progress rows for the project.

## Outline Review Apply

Applying an outline-wide review creates a new saved outline baseline. The apply endpoint must not only save the merged `outline.md`; it must also write the revised content back to stage source data where the content can be mapped safely.

Successful apply persists:

- `outline/<stage>.md`
- `outline_stages/<stage>.md`
- `state.outline_stage_artifacts[stage]` metadata, including summary, stage memory, path, pending questions, and `updated_at`
- root `outline.md`
- `state.outline`
- outline review metadata, including `outline_review_applied_run_id`

After saving, the endpoint returns apply metadata such as `applied`, `updated_stages`, `skipped_stages`, and a summary of the saved source outline. The frontend refreshes the stage list, the current stage content, and the latest review state. If the user is viewing a stage that was updated, the editor immediately shows the saved revision.

Only selected review suggestions enter the revision instruction. Unselected suggestions must not be passed to the reviser.

## Review Baseline for Later Manual Reviews

Apply must not start another review. A subsequent review only happens after the user manually clicks the review button again.

When the user manually starts a new outline-wide review after a successful apply, the backend builds `source_outline` from the current saved baseline, not from the previous review report. The current saved baseline is the stage files and current `state.outline` produced by the apply step. This ensures the next report reflects the previous accepted changes.

Acceptance:

- Clicking apply updates the relevant stage editor content and the combined outline.
- Switching to an updated stage shows the applied content.
- Later chapter outline and chapter writing flows read the applied stage files.
- Immediately clicking "大纲总体审查" again produces a report whose `source_outline` includes the previously applied changes.
- A new review is never triggered automatically by apply.

## Error Handling

If a stage section cannot be safely identified in the revised outline, the endpoint records that stage in `skipped_stages` and does not silently overwrite it. If the final combined outline cannot be saved, the endpoint fails instead of returning `applied: true`.

Partial stage skips are acceptable only when the final combined outline has been saved and the response explicitly reports the skipped stages. Critical write failures return an error and leave the frontend in its previous visible state after showing the error progress row.

## Testing

Backend tests should cover:

- Pending question answer submission followed by another round of pending questions.
- Pending question answer submission followed by no remaining questions and a lockable stage.
- Outline review apply saving stage files and `state.outline`.
- A second manually triggered review using the newly saved baseline.
- Selected issue IDs limiting the revision instruction.

Frontend tests should cover:

- Progress events with the same key/label updating one row from running to completed.
- Progress rows rendering elapsed, token, and context fields.
- Apply success refreshing the active stage content and latest review payload.

## Documentation

The implementation must update:

- `docs/IMPLEMENTATION_PLAN.md` with the architecture and workflow changes.
- `docs/SESSION_SUMMARY.md` with implementation notes, test results, and remaining limitations.
