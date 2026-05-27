# Manual Outline Stage Advancement Design

## Context

The outline workflow currently treats a lock action as both confirmation and advancement. Locking an ordinary outline stage switches `state.outline_stage` to the next stage and immediately runs generation for that next stage. Locking a chapter-outline volume can also immediately generate the next volume.

This is too eager for the current Web workflow. Users need a review pause after each stage, especially after `分卷大纲`, and chapter-outline generation should be explicitly started per volume from the `章节大纲` workspace.

## Requirements

- Locking `方向定位`, `世界观设定`, `人物关系`, `故事流程`, or `分卷大纲` only locks the current stage artifact.
- Locking a stage must not switch to the next stage, must not set the next stage to `collecting`, and must not call generation for the next stage.
- After locking `分卷大纲`, the user remains able to run the top-level outline review before opening `章节大纲`.
- `章节大纲` remains a separate top-level navigation workspace. The user manually selects a volume and clicks generate, revise, or lock.
- Locking one chapter-outline volume must not automatically select or generate the next volume.
- The `章节大纲` workspace should have a single volume navigation surface. The left sidebar owns volume selection; the right workspace shows only the selected volume title, actions, instruction input, and content.
- Final workflow closure may still finalize locked outline data when there is no next stage, because that is not automatic advancement to another stage.

## Backend Design

`advance_outline_stage_node()` will keep its validation and unresolved-question handling, but change the successful lock path:

- For ordinary non-final stages, mark the current artifact `locked`, clear pending questions, save state, and return.
- Keep `state.outline_stage` and `state.current_stage` on the locked stage.
- Set a director message that tells the user the stage is locked and they can manually choose the next workspace/stage when ready.
- Do not call `run_outline_stage_node()` for the next stage.
- For `chapter_outline`, call `confirm_current_chapter_outline_volume()` to mark the selected volume locked, then save and return without setting a next-volume generation directive.

The existing final-stage branch that calls `finalize_locked_outline()` remains available when `next_outline_stage(stage)` returns `None`.

## Frontend Design

The left navigation already lists chapter-outline volumes. The duplicated right-side `volume-list` inside `chapter-outline-layout` will be removed. The right panel will render only the current selected volume or the chapter-outline review view.

The layout can become a single-column content area for the selected volume. Existing left navigation remains the only way to switch volumes.

## Tests

Add backend regression tests for:

- Locking an ordinary stage with a next stage does not advance or generate.
- Locking a chapter-outline volume with another volume remaining does not auto-generate the next volume.

Add a frontend structural test for:

- `topSection === 'chapter-outline'` workspace does not include the duplicate right-side `volume-list`.
- The source still includes left-sidebar volume navigation and selected-volume content rendering.

## Documentation

Update `docs/IMPLEMENTATION_PLAN.md` and `docs/SESSION_SUMMARY.md` with the behavior change, verification scope, and remaining risk.
