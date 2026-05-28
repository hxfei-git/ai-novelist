# Outline Review Pending Choices Design

Date: 2026-05-28

## Goal

Make the overall outline review use the same confirmation pattern as outline stage pending questions. Each review item should give the user three choices:

- Use the recommended revision.
- Do not revise this item.
- Use my own opinion.

When the user chooses "my own opinion", that text participates in the apply step and becomes part of the outline revision instruction.

## Current Problem

The overall outline review currently behaves differently from the stage review flow. It presents selectable review suggestions, but it does not let the user answer each item with the familiar three-column pending-question controls. This makes the overall review feel inconsistent and prevents the user from supplying targeted instructions during apply.

There is also a usability failure around apply: after clicking the apply button, the page can appear to wait for a long time without a clear result, and if the web connection fails the user does not get enough feedback.

## Proposed Approach

Reuse the stage pending-question interaction model for overall outline review items.

The overall review workspace will render each review item as a decision row with three choices:

- `推荐修改意见`: apply the reviewer recommendation for this item.
- `暂不修改`: exclude this item from the apply instruction.
- `我的意见`: show a text input and apply the user's custom text for this item.

The default decision should be `推荐修改意见` for actionable review items, matching the current expectation that the reviewer has produced recommended fixes. The user can switch individual items to `暂不修改` or `我的意见` before applying.

## Data Flow

The frontend should stop treating overall review application as a simple list of selected issue ids. Instead, it should send per-item decisions:

```json
{
  "decisions": [
    {
      "issue_id": "issue-1",
      "decision": "recommended",
      "custom_answer": ""
    },
    {
      "issue_id": "issue-2",
      "decision": "skip",
      "custom_answer": ""
    },
    {
      "issue_id": "issue-3",
      "decision": "custom",
      "custom_answer": "按我的理解收束第二卷主线，不新增支线。"
    }
  ]
}
```

The backend apply handler should translate these decisions into the revision instruction:

- `recommended`: include the review item's recommended action.
- `custom`: include the user's custom answer instead of the recommended action.
- `skip`: exclude the item.

If the request omits `decisions`, the backend may keep accepting the existing `selected_issue_ids` shape for compatibility, but the web UI should use the new decision format.

## UI Behavior

The overall review page should present a compact table or board consistent with existing stage pending questions. It should avoid introducing a separate interaction style.

Each item should show the review problem or risk, then the three decision columns. The `我的意见` column includes a textarea/input that is enabled when the custom decision is selected. Empty custom text should not be silently applied; the UI should show a validation message requiring text before applying.

The apply button should clearly show pending state while the request is running, disable duplicate submission, and then refresh the outline, review report state, and stage list after success.

## Error Handling

If apply fails, times out, or the browser loses connection, the UI should show a visible error message and re-enable the apply button. The user should not be left with a disabled button or a page that appears to be waiting indefinitely.

The backend should reject invalid decisions with a clear validation error:

- unknown `issue_id`
- unsupported `decision`
- `custom` decision with empty custom text

## Testing

Backend tests should verify:

- Recommended decisions are included in the revision instruction.
- Custom decisions are included as user input.
- Skipped decisions are not included.
- Invalid custom decisions return an error instead of applying an empty instruction.
- The previous `selected_issue_ids` request shape remains compatible if kept.

Frontend structure tests should verify:

- Overall outline review renders the three decision labels: `推荐修改意见`, `暂不修改`, and `我的意见`.
- The custom text control is present for overall outline review decisions.
- Apply submits per-item decisions rather than only selected issue ids.
- Apply has loading/disabled behavior to prevent duplicate submission.

## Out of Scope

This change does not redesign the stage pending-question flow, does not change chapter review behavior, and does not add a new long-running job system. It only aligns overall outline review decisions with the existing stage confirmation model and improves the apply request feedback.
