# Outline Review Priority Audit Design

## Context

The Web "大纲总体审查" flow currently asks the outline editor to return one flat `## 主要问题` list and one flat `## 修改建议` list. The prompt caps both lists at 10 items. In `demo-web`, repeated review/apply cycles showed the practical failure mode: each review surfaced one batch of issues, applying them generated a more detailed outline with new unresolved details, and the next review surfaced the next batch. This made review feel endless even when each individual apply succeeded.

The desired behavior is not to remove one-click apply. The user wants one-click apply to remain, but the review needs to separate blocking issues from lower-priority improvements so the system can expose all true blockers in a single review while keeping lower-priority output bounded.

## Goals

- Change only the overall outline review flow in this iteration.
- Make high-priority review issues exhaustive for one review pass, so hard blockers are not intentionally capped at 10.
- Limit low-priority issues to 20 items.
- Limit suggestion issues to 10 items.
- Preserve one-click apply and per-item decisions.
- Let the frontend show high-priority, low-priority, and suggestion issues as separate groups.
- Make apply behavior prioritize true blockers without automatically turning every optional suggestion into another revision loop.
- Preserve compatibility with existing flat review reports.

## Non-Goals

- Do not change ordinary outline-stage pending question behavior in this iteration.
- Do not change chapter review or chapter-outline review behavior.
- Do not remove historical review reports.
- Do not require browser automation for this change; source-level frontend tests and backend service tests are sufficient.
- Do not build a new global issue tracker or cross-run deduplication system.

## Recommended Approach

Use a structured priority model for overall outline review reports.

The outline editor prompt should ask for three sections:

- `## 高优先级问题`: all blockers and hard conflicts. These are issues that would break chapter-outline work, violate locked constraints, contradict established canon, or leave a required structural decision unresolved. The prompt should say these must be exhaustive in one pass. To protect against pathological model output, the implementation may enforce a safety cap of 50 high-priority items, but the product behavior is "do not cap real blockers at 10".
- `## 低优先级问题`: quality and clarity issues that should be fixed but do not block moving forward. Maximum 20.
- `## 建议问题`: optional improvements, chapter-outline reminders, and polish suggestions. Maximum 10.

The backend should parse these sections and attach `priority` to each `repair_suggestions` item:

```json
{
  "priority": "high|low|suggestion"
}
```

Existing flat reports without a priority should be treated as `low` for compatibility.

This approach is preferred over only changing the prompt because the frontend and apply logic need priority information. It is preferred over changing every outline stage at once because the current repeated-loop problem is in the overall review workflow, while ordinary stage pending questions are separate lock/confirmation behavior.

## Prompt Contract

`outline_editor.md` should stop using the flat `## 主要问题` / `## 修改建议` shape for new reports. It should produce:

```md
STATUS: pass|revise|stop
QUALITY_SCORE: 0-100

## 总体判断
...

## 高优先级问题
1. 问题描述。——推荐修改意见：具体修复建议。

## 低优先级问题
1. 问题描述。——推荐修改意见：具体修复建议。

## 建议问题
1. 问题描述。——推荐修改意见：具体建议或后置处理方式。

## 锁定约束检查
...

## 下一步建议
...
```

Each issue line should carry its own recommendation using `——推荐修改意见：...`. This avoids relying only on matching same-numbered problem and recommendation lists. The parser should still keep compatibility with the existing paired `## 主要问题` / `## 修改建议` format.

Status semantics:

- `revise`: one or more high-priority issues exist, or a low-priority issue is severe enough that the editor chooses revision before moving on.
- `pass`: no high-priority blockers exist. Low-priority and suggestion issues may still be present as non-blocking follow-up items.
- `stop`: the outline cannot be reviewed usefully because required context is missing or constraints conflict irreconcilably.

## Backend Behavior

`build_outline_repair_suggestions()` should support priority-aware parsing:

1. Parse `## 高优先级问题`, `## 低优先级问题`, and `## 建议问题` first.
2. For each item, split embedded `推荐修改意见` into `message` and `recommendation`.
3. Attach `priority` as `high`, `low`, or `suggestion`.
4. Enforce caps after parsing: high safety cap 50, low cap 20, suggestion cap 10.
5. Fall back to the existing same-numbered `## 主要问题` / `## 修改建议` pairing for old reports, assigning `priority="low"`.
6. Fall back to old flat bullet extraction only when no structured sections are found.

`outline_revision_instruction_lines()` and decision handling should include enough priority context for the reviser to apply the right changes. A recommended line can remain `message -> recommendation`, but the grouped instruction should preserve priority order: high first, low second, suggestion last.

## Frontend Behavior

The outline review decision board should group suggestions by `priority`:

- 高优先级问题
- 低优先级问题
- 建议问题

Default decisions:

- High priority: `recommended`
- Low priority: `recommended`
- Suggestion: `skip`

The user can still switch any item to `暂不修改` or `我的意见`.

The apply button and SSE flow remain the same. One-click apply sends the current decision map. Because suggestions default to skip, optional items are visible but do not automatically trigger another revision loop.

## Compatibility

Historical reports may contain only flat `repair_suggestions` with no `priority`. The frontend should treat missing priority as `low`, and backend apply should continue to accept those reports. Existing applied-state behavior remains unchanged.

If an old report has both `message` and `recommendation` but no priority, apply behavior should not fail or require report migration.

## Error Handling

- Empty custom answers remain blocked in the frontend before submission.
- Unsupported priority values should normalize to `low`.
- A structured section item with no recommendation should use the message as the fallback recommendation, matching legacy behavior.
- A `decision: stop` report remains non-applicable.
- Parsing failures should fall back to legacy extraction rather than returning an empty suggestion list when review text contains bullets.

## Testing

Backend tests should cover:

- Priority sections parse into `repair_suggestions` with distinct `priority`, `message`, and `recommendation`.
- High-priority items are not capped at 10; a test with more than 10 high-priority items returns all of them.
- Low-priority items are capped at 20.
- Suggestion items are capped at 10.
- Existing `## 主要问题` / `## 修改建议` reports still parse and default to `priority="low"`.
- Apply instruction generation preserves high, low, suggestion order for selected items.

Frontend/source tests should cover:

- The decision map defaults high and low items to `recommended`, and suggestion items to `skip`.
- The decision board renders separate priority group labels.
- Missing priority is treated as low.

Verification should include focused backend Web service tests, frontend structure tests, `git diff --check`, and `npm --prefix web/frontend run build` because the review payload shape affects the frontend.
