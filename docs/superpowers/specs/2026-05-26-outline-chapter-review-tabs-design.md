# Outline and Chapter Review Tabs Design

Date: 2026-05-26

## Problem

The current Web UI places the outline-level `总体审查` action in the toolbar of every outline stage page. This makes it look like `方向定位`, `世界观设定`, and other individual stages each have their own global review, which is misleading.

The chapter area already treats review as a separate workflow surface, but its entry currently lives in the left navigation beside chapter batch generation and generated chapter list. The requested direction is to make the outline and chapter areas consistent: each top-level area owns its own secondary views, and review is one of those views.

## Goals

- Keep review and workflow-tool entries out of the left sidebar. The sidebar keeps the top-level `大纲 / 章节` switch, and may keep the outline stage list as a contextual stage selector when `大纲` is active.
- Move outline `总体审查` out of every stage toolbar.
- Add an outline workspace secondary tab model: `阶段编辑 / 总体审查`.
- Add a chapter workspace secondary tab model: `批量生成 / 已生成章节 / 总体审查`.
- Allow outline `总体审查` to run at any time against currently available outline stage artifacts.
- Preserve current review behavior: generating a review report does not rewrite content; applying accepted changes is explicit.
- Audit existing backend APIs before implementation. Add no backend API if current endpoints can complete the feature.

## Non-Goals

- Do not reintroduce `review_lock` as a required outline stage.
- Do not change outline stage generation, locking, or chapter generation semantics.
- Do not redesign the visual theme beyond the navigation and view structure needed for this change.
- Do not change the chapter review repair model unless the API audit finds a blocking gap.

## Proposed UX

### Top-Level Sidebar

The sidebar keeps the top-level switch:

- `大纲`
- `章节`

When `大纲` is selected, the sidebar may still show the outline stage list as contextual navigation for stage editing. It must not show `总体审查` as another stage, and the stage toolbar must not include a global review action.

When `章节` is selected, the sidebar no longer shows `章节批量生成`, `已生成章节`, and `章节总体审查` as separate nav buttons. Those move into the chapter workspace secondary tabs.

### Outline Workspace

The outline workspace has two secondary tabs near the top of the main panel:

- `阶段编辑`
- `总体审查`

`阶段编辑` shows the selected outline stage editor. Its toolbar includes only stage-scoped actions:

- `保存`
- `生成/修订`
- `锁定`

`总体审查` shows the independent outline review view. It includes:

- Optional instruction input for this review run.
- `开始审查` action.
- Running state.
- Latest review report, if present.
- `采纳修改` and `不采纳` actions when a report is available.

The review source is the currently available outline artifact set. It can run before all stages are complete, and the backend should review the content that exists.

### Chapter Workspace

The chapter workspace has three secondary tabs near the top of the main panel:

- `批量生成`
- `已生成章节`
- `总体审查`

The existing chapter batch generation, chapter list/detail, and chapter review surfaces move under those tabs without changing their underlying behavior.

## State Model

Frontend state should keep two levels of view state:

- `topSection = outline | chapters`
- `outlineView = edit | review`
- `chapterView = batch | list | review`

Existing data state remains scoped to the feature that uses it:

- `activeStage` remains the selected outline stage and is relevant only when `outlineView = edit`.
- `outlineReview` remains the latest outline review report state.
- `review` remains the latest chapter review report state.
- `selectedRepairIds` remains chapter-review-specific state.

Switching secondary tabs must not reset `activeStage`, selected chapter, or existing review report state.

## Backend API Audit

Before implementation, verify the current endpoints can complete the target UX:

Outline review:

- `GET /api/projects/{project_id}/outline/review/latest` loads the latest report.
- `POST /api/projects/{project_id}/outline/review` runs a report against current available outline artifacts.
- `POST /api/projects/{project_id}/outline/review/{run_id}/apply` explicitly applies accepted changes.

Chapter review:

- `GET /api/projects/{project_id}/chapters/review-all/latest` loads the latest chapter review report.
- `POST /api/projects/{project_id}/chapters/review-all` runs chapter review.
- `POST /api/projects/{project_id}/chapters/{chapter}/apply-repair` applies selected repair suggestions.

Expected result: no new backend API is needed if these endpoints already support loading, running, applying, and no-op dismissal from the new tab layout. `不采纳` can remain a frontend-only dismissal unless persistent dismissal is already required elsewhere.

If the audit finds a blocking gap, the implementation plan must document the smallest backend change needed before changing code.

## Error Handling

- If no latest review exists, the review tab should show an empty state and the start-review action.
- If `latest` endpoints return “not found”, the frontend should treat that as no report rather than a broken view.
- Running review errors should use the existing error display/log mechanism.
- Apply errors should leave the current report visible so the user can retry or inspect the issue.

## Testing

Verification should include:

- `npm --prefix web/frontend run build`.
- Backend regression tests: `.venv/bin/python -m pytest tests/test_web_service.py tests/test_outline_collaboration.py tests/test_director_service.py tests/test_outline_stage_controls.py`.
- Frontend structure check by code review/build: outline stage editor toolbar no longer contains `总体审查`; outline review appears under `outlineView = review`; chapter views are secondary tabs in the chapter workspace rather than sidebar nav buttons.

## Documentation

Implementation must update:

- `docs/IMPLEMENTATION_PLAN.md` for architecture/workflow documentation.
- `docs/SESSION_SUMMARY.md` for implementation notes, validation, and remaining limitations.

## Approval Notes

User-selected direction: B, workspace secondary tabs.

Confirmed details:

- Outline review is available at any stage and reviews existing outline artifacts.
- Chapter area should use the same secondary-tab pattern.
- Backend APIs should be audited first; no new API should be added if current endpoints can finish the feature.
