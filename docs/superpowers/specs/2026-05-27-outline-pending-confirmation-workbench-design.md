# Outline Pending Confirmation Workbench Design

## Problem

The Web outline flow currently treats pending confirmation as secondary metadata. In `projects/demo-test`, the current `characters` stage shows the real unresolved questions inside `outline/characters.md`, while `state.pending_questions` only contains the generic prompt asking whether to lock the stage or keep editing. The Web UI also does not surface pending questions as actionable controls, so users must search through long Markdown documents and can easily miss items before locking a stage.

The desired behavior is a current-stage confirmation workbench: each pending item is visible, has practical default choices, allows custom input when defaults are not suitable, and can be submitted in one batch.

## Goals

- Surface pending confirmation items for the currently opened outline stage without requiring the user to inspect Markdown manually.
- Provide 2-3 default choices per item plus a custom answer path.
- Require every visible item to be handled before batch submission.
- Submit all answers in one action and re-run the existing current-stage revision path.
- Refresh stage content and pending items after submission.
- Handle existing projects where pending questions exist only in the stage Markdown.

## Non-Goals

- Do not build a global pending-question center across all stages in this iteration.
- Do not require all outline agents to emit JSON.
- Do not introduce a new database or persistence layer.
- Do not replace the existing stage editor, stage generation, or lock flow.
- Do not make pending questions blocking if the stage has none.

## Recommended Approach

Implement a Web service layer payload for the current stage:

```text
current stage state/artifact
  -> collect pending questions from structured state/artifact fields
  -> fallback parse current stage Markdown pending sections
  -> filter non-questions such as "暂无"
  -> generate deterministic default options
  -> return pending confirmation payload to frontend
```

The frontend renders the payload as a "待确认" workbench above the stage editor. Each item has radio-style default options and a custom text input. The user handles all items, then clicks one submit button. The backend converts selections into a clear revision instruction and calls the existing stage generation/revision service for the same stage.

This keeps the feature isolated: the backend owns extraction and instruction building, while the frontend owns selection state and validation.

## Backend Design

Add service-level helpers in `src/ai_novelist/web/service.py`:

- `outline_stage_pending_payload(store, project_id, stage) -> dict`
- `collect_stage_pending_questions(store, state, stage) -> list[str]`
- `extract_pending_questions_from_stage_markdown(text) -> list[str]`
- `default_pending_options(question, stage) -> list[dict]`
- `submit_stage_pending_answers(store, adapter, project_id, stage, answers, progress=None) -> NovelState`

The payload shape:

```json
{
  "project_id": "demo-test",
  "stage": "characters",
  "items": [
    {
      "id": "sha1-short",
      "question": "沈灵儿决裂的3-5章小纲是否需要在章节规划阶段提前完成？",
      "options": [
        {"id": "accept", "label": "采纳建议", "answer": "采纳当前建议，并在后续章节规划阶段展开。"},
        {"id": "defer", "label": "延后处理", "answer": "暂不锁定细节，延后到章节规划阶段决定。"},
        {"id": "keep", "label": "保持现状", "answer": "保持当前阶段设定，不新增细节。"}
      ]
    }
  ]
}
```

Question collection priority:

1. `state.outline_stage_artifacts[stage].pending_questions`
2. `state.pending_questions` only when the state's `outline_stage` matches `stage` and the question is not a generic lock/continue prompt
3. Current stage Markdown sections headed like `待确认问题` or `仍需确认的问题`

Filtering rules:

- Drop empty items.
- Drop generic status lines such as `暂无`, `当前阶段可继续修改或确认进入下一阶段`.
- Drop generic lock prompts such as `请确认是否锁定...并进入下一阶段`.
- De-duplicate normalized question text.
- Keep the current stage only.

Default options should be deterministic in v1. They do not need model calls. The initial default set can be:

- `采纳建议`: Use the recommendation implied by the question or current draft.
- `延后处理`: Explicitly defer the decision to a later planning stage.
- `保持现状`: Keep the current stage content without adding new canon.

For questions containing clear timing phrases such as `章节规划`, the accept answer should mention that later stage explicitly. For naming questions, the accept answer can say to decide names during chapter planning. These should be short, transparent defaults rather than invented canon.

Submission API behavior:

- Validate that each payload item has either a selected option answer or non-empty custom answer.
- Build a revision instruction:

```text
针对当前阶段待确认项，按以下答案修订：
1. 问题：...
   答案：...
2. 问题：...
   答案：...
```

- Call the same stage revision path used by `generate_outline_stage()`, with `state.outline_stage = stage`, `state.revision_instruction = instruction`, and `state.user_request = instruction`.
- Save the resulting state through existing `run_outline_stage_node()` behavior.
- Return the refreshed `NovelState` or stage payload.

Add FastAPI routes in `src/ai_novelist/web/app.py`:

- `GET /api/projects/{project_id}/outline/stages/{stage}/pending`
- `POST /api/projects/{project_id}/outline/stages/{stage}/pending/submit`

The submit route should stream SSE progress like existing generate/lock endpoints because it invokes a model-backed revision.

## Frontend Design

In `web/frontend/src/main.tsx`, add a current-stage pending workbench to the outline edit view between the toolbar and the instruction input.

Behavior:

- Load pending payload whenever `projectId` or `activeStage` changes, and after stage generate/save/lock/pending-submit completes.
- Show nothing noisy when there are no pending items: a compact "暂无待确认项" status is enough.
- For each pending item, render:
  - question text
  - default option radio buttons or selectable rows
  - a custom option with an input field
  - local validation state
- The submit button is disabled until every item has either a selected default option or a non-empty custom answer.
- On submit, send all answers in one request, stream progress to the existing log, then refresh the stage content and pending payload.

The UI should not force users to scroll inside the Markdown editor to find questions. The workbench is the operational source for current-stage confirmation.

## Data Flow

```text
User opens current outline stage
  -> frontend loads stage content
  -> frontend loads pending payload
  -> user selects defaults or writes custom answers
  -> frontend submits all answers
  -> backend builds revision instruction
  -> existing outline stage revision runs
  -> backend saves refreshed artifact/state
  -> frontend reloads content and pending payload
```

## Error Handling

- If no pending items exist, submit should return a clear 400-style error or the frontend should disable submission.
- If any answer is incomplete, the frontend blocks submission and the backend also validates.
- If model revision fails, the SSE error should surface in the progress log and leave existing stage files unchanged except for normal error state already used by the graph.
- If Markdown extraction finds malformed items, skip malformed lines rather than exposing broken controls.

## Testing

Backend unit tests in `tests/test_web_service.py`:

- Extract pending questions from a Markdown section headed `## 十三、待确认问题`.
- Ignore `暂无` and generic "可继续修改或确认进入下一阶段" lines.
- Prefer artifact pending questions when present.
- Fall back to Markdown-only questions for a `demo-test`-like state.
- Build deterministic default options for each pending item.
- Submit answers and verify the existing stage revision path receives the combined instruction.
- Reject incomplete answer payloads.

Frontend structure tests:

- Verify the outline edit workspace contains a pending confirmation area.
- Verify default options, custom input, and batch submit controls are represented.

Manual verification:

- Open `projects/demo-test` in Web.
- Select `人物关系`.
- Confirm the six Markdown-only pending questions appear in the workbench.
- Choose defaults or custom answers for every item.
- Submit once and verify the stage reruns, content refreshes, and unresolved items update.

## Documentation Updates for Implementation

When implementing this spec, update:

- `docs/IMPLEMENTATION_PLAN.md` with the Web pending confirmation workbench architecture and API behavior.
- `docs/SESSION_SUMMARY.md` with implementation notes, verification commands, and remaining limitations.

