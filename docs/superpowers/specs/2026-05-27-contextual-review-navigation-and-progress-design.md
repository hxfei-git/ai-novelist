# Contextual Review Navigation and Concise Progress Design

Date: 2026-05-27

## Problem

The Web UI currently treats review navigation inconsistently:

- In the `大纲` workspace, `总体审查` is presented as a secondary view above whichever outline stage is selected. It is independent of any one stage, so placing it inside the selected-stage workspace obscures its scope.
- In the `章节大纲` workspace, volume planning is available but there is no equivalent overall review surface for checking all volume chapter outlines together.
- In the `章节正文` workspace, the primary views are function-oriented (`批量生成 / 已生成章节 / 总体审查`) rather than volume-oriented, although the writing workflow operates by volume.

The right-side progress panel also stores and renders free-form messages. Those messages can include generated content, review summaries, or suggestion text, when the panel should only communicate execution status and operational metrics.

## Goals

- Keep the existing top-level workspaces: `大纲 / 章节大纲 / 章节正文`.
- Give all three workspaces the same contextual sidebar rule: list the current workflow objects, then show `总体审查` as a separated final entry.
- Make `大纲 / 总体审查` audit currently available outline-stage artifacts without joining the stage generation or locking chain.
- Add `章节大纲 / 总体审查`, which reviews all volume chapter outlines and explicitly applies selected changes only to affected volumes.
- Reorganize `章节正文` around volumes: choose a volume first, then operate on `批量生成` and `已生成章节` within that volume; keep `总体审查` as a peer to the volume entries.
- Keep chapter-body overall review global across all generated chapters and continue applying selected repairs per chapter.
- Limit new progress-panel entries to concise stage/action labels and operational metrics such as elapsed time, token estimates, and context size.

## Non-Goals

- Do not change the creative pipeline semantics of outline generation, locking, chapter generation, or chapter-body review.
- Do not introduce an unlock flow.
- Do not migrate, sanitize, or rewrite previously persisted free-form progress-log entries.
- Do not create a general-purpose review center outside the three existing workspaces.
- Do not introduce database persistence or replace the file-backed project model.

## Chosen Information Architecture

The selected layout uses a consistent contextual sidebar in each top-level workspace.

### 1. Outline Workspace

When `大纲` is active, the sidebar contains:

```text
方向定位
世界观设定
人物关系
故事流程
分卷大纲
----------------
总体审查
```

Selecting an outline stage renders its existing stage editor and stage-scoped actions. Selecting `总体审查` renders the independent outline review workspace in the main panel.

`总体审查` is visually separated because it audits the available stage set; it is not another sequential stage, does not expose generate/revise/lock actions, and does not affect stage progression unless the user explicitly applies selected review suggestions.

### 2. Chapter Outline Workspace

When `章节大纲` is active, the sidebar contains the available volume entries followed by review:

```text
第一卷
第二卷
第三卷
----------------
总体审查
```

Selecting a volume renders its existing volume chapter-outline surface:

- volume status
- `生成 / 修订 / 锁定` actions
- instruction input
- current volume chapter-outline content

Selecting `总体审查` renders a new cross-volume review workspace. It evaluates all existing volume chapter-outline content, displays selectable repair suggestions grouped or identified by affected volume, and changes content only after explicit application.

### 3. Chapter Body Workspace

When `章节正文` is active, the sidebar likewise contains volume entries followed by review:

```text
第一卷
第二卷
第三卷
----------------
总体审查
```

Selecting a volume renders volume-scoped writing views in the main panel:

- `批量生成`
- `已生成章节`

`批量生成` uses the selected volume by default while continuing to expose chapter range and concurrency inputs. `已生成章节` lists and displays generated chapters belonging to the selected volume.

Selecting `总体审查` renders the existing global chapter review surface. Its scope remains all generated chapters across every volume, and selected repairs are still applied per chapter.

## Review Scope and Application Rules

### Outline Overall Review

- Source: available ordinary outline stage artifacts.
- Existing workflow/API may be reused.
- Applying selected suggestions updates only the explicitly accepted outline changes.
- It must not appear as a generated or locked outline stage.

### Chapter Outline Overall Review

- Source: all existing per-volume chapter-outline content.
- A review report is independent stored output, not an implicit modification to chapter outlines.
- Each suggestion identifies at least its affected volume and the proposed correction.
- The user selects suggestions before applying them.
- Applying selected suggestions revises only the affected volumes; unselected volumes remain unchanged.
- Applying revisions must refresh the combined `chapter_outline` artifact consumed by later chapter-writing context.

### Chapter Body Overall Review

- Source: all currently generated chapter bodies, across all volumes.
- Existing global review and per-chapter repair behavior remains valid.
- Changing navigation must not reduce the scope to only the selected volume.

## Frontend State and Components

The frontend should express navigation directly rather than model review as an incidental tab on a stage.

Suggested view state:

```text
topSection = outline | chapter-outline | chapters

outlineSelection = <stage> | overall-review
chapterOutlineSelection = <volume index> | overall-review
chapterBodySelection = <volume index> | overall-review

selectedChapterBodyView = batch | list
```

Expected component responsibilities:

- Contextual navigation component: renders current object's list, separator, and `总体审查` entry with active state.
- Outline stage workspace: existing stage edit/actions surface only.
- Outline review workspace: existing independent outline review report and apply surface.
- Chapter-outline volume workspace: existing per-volume actions and content.
- Chapter-outline review workspace: new report and selected-application surface.
- Chapter-body volume workspace: `批量生成 / 已生成章节` within selected volume.
- Chapter-body review workspace: existing global body-review surface.

Switching between review and ordinary selections must preserve loaded reports and the user's last selected stage, volume, and chapter where practical, so the user can return to the same work context.

## Backend and Persistence Contract

### Existing APIs to Reuse

Outline overall review remains based on the existing outline review endpoints:

```text
GET  /api/projects/{project_id}/outline/review/latest
POST /api/projects/{project_id}/outline/review
POST /api/projects/{project_id}/outline/review/{run_id}/apply
```

Chapter-body overall review remains based on existing endpoints:

```text
GET  /api/projects/{project_id}/chapters/review-all/latest
POST /api/projects/{project_id}/chapters/review-all
POST /api/projects/{project_id}/chapters/{chapter}/apply-repair
```

### Chapter Outline Review Contract

The chapter-outline review uses a dedicated sibling contract, shaped like the body-review flow but applied by volume:

```text
GET  /api/projects/{project_id}/outline/chapter-workspace/review/latest
POST /api/projects/{project_id}/outline/chapter-workspace/review
POST /api/projects/{project_id}/outline/chapter-workspace/review/{run_id}/apply
```

These endpoints respectively load the latest report, run a review over all current volume chapter-outline artifacts, and apply selected suggestions with volume-level targeting.

A report must contain:

- `run_id`
- `status`, `summary`, and optional score/decision fields consistent with existing review UI patterns
- source digest or source summary describing the volume chapter-outline snapshot reviewed
- selectable `repair_suggestions`
- for every suggestion, an identifier and affected `volume_index`

Persist reports outside the chapter-outline content artifact:

```text
projects/<project>/outline/chapter_reviews/<run_id>/report.json
projects/<project>/outline/chapter_reviews/<run_id>/report.md
```

Application writes new volume content only after user confirmation and then rebuilds the combined chapter-outline output.

### Chapter-to-Volume Association

The chapter-body sidebar needs volume entries and volume-scoped chapter lists. The service must expose or derive the chapter range associated with each volume from the locked chapter-outline/volume metadata. If a legacy project's chapter cannot be resolved to a volume, it must appear in a fallback `未分卷` group rather than disappear from the UI.

## Concise Progress Panel

### Display Rule

New progress entries displayed in the right panel contain only:

- a short stage/action label, such as `世界观汇总`, `第二卷章节生成`, or `章节总体审查`
- elapsed time when available
- token estimate when available
- context usage when available
- concise error state when an operation fails

They do not contain:

- generated outline, chapter-outline, or chapter-body content
- review summaries or report prose
- repair suggestion text
- user-entered instructions

Example display:

```text
第二卷章节生成
18.2s · tok≈12K · ctx=6K/258K

章节总体审查
7.3s · tok≈4K
```

### Data Contract

The current persisted log is `string[]` and can carry arbitrary text. New progress recording uses structured display events. Readers may continue accepting legacy strings, but all new writers persist records containing only allowed metadata:

```json
{
  "label": "章节总体审查",
  "elapsed": "7.3s",
  "tokens": "tok≈4K",
  "context": "ctx=6K/258K",
  "status": "completed"
}
```

If backward compatibility requires continuing to accept old strings, the reader may render legacy saved entries unchanged while all new event writers persist only concise records or sanitized strings. This satisfies the explicitly chosen scope: historical logs are not migrated; content suppression applies to post-change events.

## Error Handling

- A review run that fails leaves the latest successful report visible and logs only a concise failure entry.
- Applying review suggestions is explicit; failures must not discard the report or replace source content.
- If a chapter-outline suggestion refers to a volume that has changed since the review was generated, the backend should reject or revalidate the apply operation rather than silently overwrite newer content.
- If no review report exists, each overall-review workspace shows an empty state and a start-review action.
- Loading or switching sidebar selections must preserve existing stale-response guards so an earlier request cannot overwrite a newer selection.

## Testing and Verification

Frontend structure coverage should assert:

- all three top-level workspaces still exist
- `大纲` sidebar contains a separated `总体审查` entry rather than an editor-level review tab
- `章节大纲` navigation renders volumes and a peer `总体审查` entry
- `章节正文` navigation renders volumes and a peer `总体审查` entry
- a selected body volume exposes `批量生成` and `已生成章节` views

Backend/service coverage should assert:

- existing outline review routes remain functional under the new navigation
- chapter-outline review can create and load a report across multiple volume outlines
- applying selected chapter-outline review suggestions updates only affected volumes and refreshes combined chapter-outline output
- chapter-body chapter listing can be filtered or grouped by selected volume without reducing overall-review scope
- legacy or unresolved chapter-to-volume mappings remain accessible

Progress coverage should assert:

- new progress events do not persist model-generated prose, report summaries, suggestions, or instructions
- stage/action labels and available elapsed/token/context metrics remain visible
- existing persisted legacy log data can still be loaded without migration

Required verification during implementation:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_frontend_review_tabs_structure.py -q
npm --prefix web/frontend run build
```

Additional focused tests should be run for any outline or volume metadata helper changed to implement chapter-outline review and chapter-to-volume navigation.

## Documentation and Change Constraints

- Update `docs/IMPLEMENTATION_PLAN.md` and `docs/SESSION_SUMMARY.md` with the implemented navigation, chapter-outline review contract, progress-event behavior, and verification results.
- Preserve existing unrelated worktree modifications in the service and test files while implementing this design.
- The visual-companion mockups under `.superpowers/` are brainstorming artifacts and are not implementation deliverables.

## Approved Decisions

- The chosen layout is the unified contextual sidebar option.
- `大纲 / 总体审查` is a sidebar peer entry separated from sequential stages.
- `章节大纲 / 总体审查` reviews all volumes and applies selected fixes only to affected volumes.
- `章节正文` is navigated by volume; each selected volume contains `批量生成` and `已生成章节`.
- `章节正文 / 总体审查` reviews all generated bodies across every volume and applies selected fixes per chapter.
- The progress panel retains stage/action names plus elapsed and token/context metrics, while post-change logs no longer display generated content or report prose.
- Previously saved logs are not migrated or sanitized.
