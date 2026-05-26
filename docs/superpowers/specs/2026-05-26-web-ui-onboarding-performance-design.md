# Web UI Onboarding and Outline Performance Design

Date: 2026-05-26
Status: Approved design, pending implementation plan

## Context

The Web UI currently has three user-facing problems:

- Creating a project immediately drops the user into the main workspace without first collecting the novel idea. The CLI chat flow asks for creative intent first, but Web does not.
- Outline stage generation can take several minutes. Existing `projects/demo-web/debug/agent_runs.jsonl` shows the slowest calls are mainly outline synthesizer calls with large outputs, for example worldbuilding/characters-style stage outputs around 10k-11k characters and 160s-205s elapsed time. The current data is not enough to clearly separate useless forward context, repeated stage content, long required structure, and model fixed overhead.
- The generation/revision instruction field is a single-line input. Longer instructions are hard to edit, and the content stays only incidentally because the component state is shared.

The goal is to fix the interaction gaps and add enough observability to make performance work evidence-based, without changing the core CLI/chat workflow.

## Chosen Approach

Use a focused Web-first change set:

1. Add a new-project creative onboarding screen.
2. Replace generation/review instruction inputs with scrollable multi-line textareas that keep their contents after actions finish.
3. Add lightweight outline stage context diagnostics for Web generation.
4. Use those diagnostics plus current project artifacts to trim obviously duplicated or low-value forward context and constrain stage output shape, while preserving each stage's required structure.

This is intentionally not a fast/full mode split. Reducing role Agent count or changing the workflow semantics may be useful later, but this pass should first prove where the time is going.

## Onboarding UX

When a newly created project has no `state.idea` and no meaningful outline stage artifact, the main workspace should show an onboarding view instead of the normal outline editor.

The onboarding view asks what kind of novel the user wants to write. It provides a multi-line text box for the story idea, genre, protagonist, tone, constraints, or desired reading experience. Submitting the form saves the idea and prepares the `direction` outline stage, but does not automatically call the model.

Expected behavior:

- The sidebar project creation form remains lightweight and only creates/selects a project by name.
- After creation, the new project is selected and the onboarding view is displayed.
- Submitting the onboarding idea saves it to `NovelState.idea`.
- The saved idea is also available to the next direction-stage generation as `user_request` and `revision_instruction`.
- Existing projects skip onboarding if they already have an idea or any generated outline artifact.
- No model call is triggered just by creating a project or submitting the onboarding idea.

## Instruction Input UX

The outline stage generation/revision instruction input and outline review focus input should become multi-line textareas.

Requirements:

- Minimum visible height is at least five text rows.
- Longer content scrolls inside the textarea.
- Running "生成/修订", "锁定", or "开始审查" does not clear the textarea after completion.
- Switching projects may reset the field according to existing component state behavior, but action completion must not clear it.
- Styling should remain consistent with the current utilitarian Web UI.

## Outline Diagnostics

Add a lightweight JSONL diagnostic log for Web outline stage generation:

`projects/<project>/debug/outline_stage_context.jsonl`

Each Web `generate_outline_stage` run should append one record with summary metadata. The log should avoid storing full prompts or long source text.

Minimum fields:

- `created_at`
- `project_id`
- `stage`
- `mode`: `full` or `light_revision`
- `instruction_chars`
- `author_craft_chars`
- `previous_stage_context_chars`
- `current_stage_context_chars`
- `role_prompt_count`
- `role_prompt_chars`
- `synthesizer_prompt_chars`
- `output_chars`
- `structure_repair_triggered`
- `elapsed_ms`
- `status`
- `error`, if any

If practical, include a compact `context_sources` array with `{name, chars}` entries for major inputs such as locked stage summaries, stage memory, current artifact, framework guidance, author craft brief, and user instruction.

## Performance Optimization Rules

Optimization should start by checking actual generated artifacts and forward inputs, not by blindly shortening every prompt.

Forward input rules:

- Later stages should prefer summaries and `stage_memory` from prior stages.
- Full previous-stage Markdown should only be included when the current stage truly needs exact structure or wording.
- Avoid passing the same information through both complete stage text and stage memory in the same prompt unless there is a clear reason.
- Avoid repeating long framework guidance in both role prompts and synthesizer prompts when one location is enough.
- Web stage generation should avoid carrying unrelated old editor notes, stale user requests, or non-current stage content.

Output rules:

- Preserve each stage's structure contract, such as the worldbuilding framework and character relationship blueprint.
- Ask for an editable decision draft rather than a long explanatory essay.
- Prefer concrete settings, conflicts, constraints, dependencies, and pending questions.
- Limit generic analysis and repeated restatement of the premise.
- Keep mandatory sections, but cap the depth of each item to short actionable bullets where possible.

## Scope Boundaries

In scope:

- Web frontend onboarding and textarea changes.
- Web/backend state update needed to save the onboarding idea.
- Web outline-stage diagnostic logging.
- Focused context trimming in outline prompt construction where diagnostics or current artifacts show duplication or irrelevant input.
- Tests for onboarding, textarea behavior, diagnostic log creation, and unchanged artifact persistence.
- Required documentation updates in `docs/IMPLEMENTATION_PLAN.md` and `docs/SESSION_SUMMARY.md` during implementation.

Out of scope:

- A complex performance dashboard.
- Database-backed metrics.
- Replacing the multi-Agent outline workflow.
- Adding fast/full generation mode.
- Changing CLI/chat behavior except through shared safe helper functions that preserve existing semantics.

## Testing Plan

Backend tests:

- Creating or updating onboarding idea persists `state.idea` and prepares direction-stage state without invoking the model.
- Web outline generation appends a diagnostic record with expected fields.
- Diagnostic logging works for successful and failed generation attempts.
- Existing outline stage artifact save/load behavior remains intact.

Frontend tests or build checks:

- The onboarding view appears for a project with no idea and no outline artifacts.
- The normal workspace appears for projects with an idea or outline artifacts.
- Instruction controls render as textareas and retain content after generation/review actions complete.
- `npm --prefix web/frontend run build` passes.

Regression checks:

- Relevant Python tests around Web service and outline stages pass.
- Full pytest should be run if prompt/context helper logic is shared with CLI/chat.

## Open Implementation Notes

- Prefer a small Web service function for onboarding, for example `save_project_idea`, rather than overloading unrelated stage save calls.
- Keep diagnostic logging independent from `agent_runs.jsonl`; `agent_runs.jsonl` tracks model calls, while the new log tracks Web outline-stage context assembly.
- If existing prompt builders make source-level diagnostics hard, introduce small helper functions that return both rendered context and length metadata.
