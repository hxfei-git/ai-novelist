# Outline Review Apply Completion Design

## Context

The Web outline workspace has an "大纲总体审查" view where users can run an overall outline review, choose repair decisions, and apply selected items. Today, applying selected items can feel frozen while the long-running SSE request is in progress. After success, the frontend switches away from the review view into an outline edit stage. When the user returns to "总体审查", the same review suggestions are still visible because the latest review report does not expose an applied state. A second click on "采纳选中项" can submit the same run again and may surface `Failed to fetch`.

## Goals

- Keep the user on the "大纲总体审查" view after clicking "采纳选中项".
- Show a visible in-place busy state while the apply request is running.
- Show "采纳完成" in the same review view after success.
- Prevent duplicate application of the same review `run_id`.
- Preserve the review summary, `run_id`, score, and status context so the user can see which report was applied.
- Refresh project and stage metadata after apply so the rest of the outline UI still reflects updated stage status.

## Non-Goals

- Do not redesign the whole outline review workspace.
- Do not change the review generation flow.
- Do not alter chapter-outline review or chapter review behavior in this change.
- Do not remove historical review report files.

## Recommended Approach

Use a combined frontend and backend applied-state fix.

The backend should persist the fact that a review report has been applied. The latest review endpoint should return that state, so a browser refresh still shows completion instead of actionable stale suggestions. The frontend should treat the applied state as terminal for the current `run_id`: hide the decision table, disable the apply button, and display "采纳完成".

This is preferred over a frontend-only state patch because local state would be lost after refresh. It is also preferred over hiding the latest report completely because the user should still see which review was just accepted.

## Frontend Behavior

When the user clicks "采纳选中项":

- The current "大纲总体审查" view remains active.
- The apply button is disabled.
- The view shows an inline busy indicator with a rotating icon and text such as "正在采纳...".
- "开始审查" and "不采纳" remain disabled while the apply request is active.

When the apply request succeeds:

- The frontend does not call `setOutlineStageView('edit')`.
- The frontend does not change `activeStage` for navigation purposes.
- The frontend refreshes project state and outline stage metadata.
- The frontend reloads the latest outline review and displays the applied state.
- The review panel shows "采纳完成".
- The repair decision table is hidden for the applied report.
- "采纳选中项" is disabled for the applied report.

If the apply request fails, the user stays on the review view and the existing error handling displays the error.

## Backend Behavior

After `apply_outline_review()` succeeds, update the persisted review report for the same `run_id` with applied metadata:

- `status`: `applied`
- `applied`: `true`
- `applied_at`: UTC ISO timestamp
- `applied_path`: relative outline path
- `updated_stages`: returned updated stage list when available
- `skipped_stages`: returned skipped stage list when available

The existing state fields such as `outline_review_applied_run_id`, `outline_review_run_id`, `outline_review_status`, `outline_review_score`, `outline_review_summary`, and `outline_review_report_path` remain updated as they are today.

If `apply_outline_review()` is called again for a report already marked applied, the backend should return an idempotent success response without invoking the model revision flow again. This prevents duplicate work and avoids repeated apply behavior for the same review run.

## Data Flow

1. User runs overall outline review.
2. Backend writes a review report under `outline/reviews/<run_id>/`.
3. User selects decisions and clicks "采纳选中项".
4. Frontend sends the existing SSE apply request with `decisions`.
5. Backend applies the selected decisions, writes updated outline outputs, and marks the review report as applied.
6. Frontend refreshes project state, stage metadata, and latest review data.
7. Frontend stays in "大纲总体审查" and renders completion state for the applied report.

## Error Handling

- Empty custom answers remain blocked before request submission.
- A report with `decision: stop` remains non-applicable.
- Network or SSE errors keep the user on the review page and use the existing `showError()` path.
- Duplicate apply requests for an already applied report return applied success without rerunning the model.

## Testing

Backend tests should cover:

- Applying an outline review marks the persisted latest report as applied.
- Reapplying an already applied `run_id` returns success without invoking the model revision path again.
- Existing decision payload behavior remains unchanged.

Frontend structure tests should cover:

- `applyOutlineReview()` no longer switches to the edit view after success.
- The apply flow still refreshes project state and stage metadata.
- `OutlineReviewWorkspace` renders a visible applying indicator.
- Applied reports display "采纳完成", hide the repair decision table, and disable the apply action.

Verification should include the focused backend Web service tests, frontend structure tests, and frontend build.
