# Outline Review Priority Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change Web overall outline review so high-priority blockers are surfaced exhaustively in one pass, low-priority issues are capped at 20, suggestion issues are capped at 10, and one-click apply preserves priority-aware defaults.

**Architecture:** Keep the change scoped to the overall outline review flow. The backend parser will produce priority-aware `repair_suggestions`; the prompt will request priority sections; the frontend will group and default decisions by priority while preserving legacy reports without `priority`.

**Tech Stack:** Python 3.11+, pytest, FastAPI Web service helpers, React/TypeScript, Vite.

---

## File Structure

- Modify `src/ai_novelist/web/outline_service.py`: parse priority sections, normalize priority values, cap each priority bucket, sort selected suggestions for apply instructions, and retain legacy parsing.
- Modify `src/ai_novelist/prompts/outline_editor.md`: replace flat issue/suggestion caps with the priority section contract.
- Modify `web/frontend/src/types.ts`: add priority metadata to `OutlineReviewSuggestion`.
- Modify `web/frontend/src/main.tsx`: default high/low decisions to `recommended` and suggestion decisions to `skip`.
- Modify `web/frontend/src/workspaces/review.tsx`: group overall outline repair decisions by priority label.
- Modify `tests/test_web_service.py`: add backend regression tests for parsing, caps, legacy priority default, and apply ordering.
- Modify `tests/test_prompt_loader.py`: assert the new outline editor prompt contract.
- Modify `tests/test_frontend_review_tabs_structure.py`: assert frontend priority typing, defaults, and grouping labels.
- Modify `docs/IMPLEMENTATION_PLAN.md` and `docs/SESSION_SUMMARY.md`: record behavior, verification scope, and remaining risk.

---

### Task 1: Backend Priority Parser

**Files:**
- Modify: `src/ai_novelist/web/outline_service.py`
- Test: `tests/test_web_service.py`

- [ ] **Step 1: Write failing parser tests**

Add these tests near the existing outline review suggestion tests in `tests/test_web_service.py`:

```python
def test_outline_review_priority_sections_parse_and_cap_items() -> None:
    high_lines = [
        f"{index}. 高优先级问题{index}。——推荐修改意见：高优先级修复{index}。"
        for index in range(1, 13)
    ]
    low_lines = [
        f"{index}. 低优先级问题{index}。——推荐修改意见：低优先级修复{index}。"
        for index in range(1, 26)
    ]
    suggestion_lines = [
        f"{index}. 建议问题{index}。——推荐修改意见：建议处理{index}。"
        for index in range(1, 13)
    ]
    notes = "\n".join(
        [
            "STATUS: revise",
            "QUALITY_SCORE: 70",
            "",
            "## 高优先级问题",
            *high_lines,
            "",
            "## 低优先级问题",
            *low_lines,
            "",
            "## 建议问题",
            *suggestion_lines,
            "",
            "## 锁定约束检查",
            "未发现。",
        ]
    )

    suggestions = outline_service.build_outline_repair_suggestions(notes, "", "")

    priorities = [item["priority"] for item in suggestions]
    assert priorities.count("high") == 12
    assert priorities.count("low") == 20
    assert priorities.count("suggestion") == 10
    assert suggestions[0]["message"] == "高优先级问题1。"
    assert suggestions[0]["recommendation"] == "高优先级修复1。"
    assert suggestions[11]["message"] == "高优先级问题12。"
    assert "低优先级问题21。" not in [item["message"] for item in suggestions]
    assert "建议问题11。" not in [item["message"] for item in suggestions]


def test_outline_review_legacy_pairing_defaults_to_low_priority() -> None:
    notes = """STATUS: revise
QUALITY_SCORE: 82

## 主要问题
1. 温和派候选人战死与萧琅终局牺牲冲突，归属未定。

## 修改建议
1. 将温和派候选人归入萧琅早期伪装，删除独立角色。
"""

    suggestions = outline_service.build_outline_repair_suggestions(notes, "", "")

    assert suggestions == [
        {
            "id": suggestions[0]["id"],
            "severity": "normal",
            "category": "revision",
            "message": "温和派候选人战死与萧琅终局牺牲冲突，归属未定。",
            "recommendation": "将温和派候选人归入萧琅早期伪装，删除独立角色。",
            "priority": "low",
            "selected": True,
        }
    ]
```

- [ ] **Step 2: Run parser tests to verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_outline_review_priority_sections_parse_and_cap_items tests/test_web_service.py::test_outline_review_legacy_pairing_defaults_to_low_priority -q
```

Expected: FAIL because priority sections are not parsed and existing suggestions do not include `priority`.

- [ ] **Step 3: Implement priority parsing**

In `src/ai_novelist/web/outline_service.py`, add constants after `outline_suggestion_identifier()`:

```python
OUTLINE_REVIEW_PRIORITY_ORDER = ("high", "low", "suggestion")
OUTLINE_REVIEW_PRIORITY_LABELS = {
    "high": "高优先级问题",
    "low": "低优先级问题",
    "suggestion": "建议问题",
}
OUTLINE_REVIEW_PRIORITY_TITLES = {
    "高优先级问题": "high",
    "高优先级": "high",
    "阻塞问题": "high",
    "低优先级问题": "low",
    "低优先级": "low",
    "建议问题": "suggestion",
    "建议项": "suggestion",
}
OUTLINE_REVIEW_PRIORITY_CAPS = {
    "high": 50,
    "low": 20,
    "suggestion": 10,
}
```

Add helpers before `build_outline_repair_suggestions()`:

```python
def normalize_outline_review_priority(value: Any) -> str:
    priority = str(value or "").strip().lower()
    return priority if priority in OUTLINE_REVIEW_PRIORITY_ORDER else "low"


def split_recommendation_from_review_item(text: str) -> tuple[str, str]:
    cleaned = str(text or "").strip()
    for marker in ("——推荐修改意见：", "--推荐修改意见：", "推荐修改意见：", "——修改建议：", "修改建议：", "——建议：", "建议："):
        if marker in cleaned:
            message, recommendation = cleaned.split(marker, 1)
            message = message.strip()
            recommendation = recommendation.strip()
            return message, recommendation or message
    return cleaned, cleaned


def build_outline_repair_suggestion(message: str, recommendation: str, priority: str = "low") -> dict[str, Any]:
    normalized_priority = normalize_outline_review_priority(priority)
    category = "revision" if re.search(r"建议|补|改|修|强化|调整|明确|确认|锁定|删除|统一", recommendation) else "issue"
    return {
        "id": outline_suggestion_identifier(message, recommendation),
        "severity": "normal",
        "category": category,
        "message": message,
        "recommendation": recommendation,
        "priority": normalized_priority,
        "selected": True,
    }


def priority_outline_review_pairs(notes: str) -> list[tuple[str, str, str]]:
    sections = markdown_sections(notes)
    pairs: list[tuple[str, str, str]] = []
    for title, body in sections.items():
        priority = OUTLINE_REVIEW_PRIORITY_TITLES.get(title.strip())
        if not priority:
            continue
        items = extract_numbered_markdown_items(body)
        limit = OUTLINE_REVIEW_PRIORITY_CAPS[priority]
        for _, text in sorted(items.items())[:limit]:
            message, recommendation = split_recommendation_from_review_item(text)
            if message.strip():
                pairs.append((message.strip(), recommendation.strip() or message.strip(), priority))
    return pairs
```

Replace `build_outline_repair_suggestions()` with:

```python
def build_outline_repair_suggestions(notes: str, revision_instruction: str, summary: str) -> list[dict[str, Any]]:
    raw_priority_pairs = priority_outline_review_pairs(notes)
    if raw_priority_pairs:
        raw_pairs = raw_priority_pairs
    else:
        raw_pairs = [(message, recommendation, "low") for message, recommendation in outline_review_issue_recommendation_pairs(notes)]
        if not raw_pairs:
            raw_items = [*extract_markdown_bullets(notes), *extract_markdown_bullets(revision_instruction)]
            if not raw_items:
                fallback = str(revision_instruction or summary or notes or "").strip()
                if fallback:
                    raw_items = [fallback]
            raw_pairs = [(item, item, "low") for item in raw_items]
    suggestions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_message, raw_recommendation, raw_priority in raw_pairs:
        message = summarize_text(raw_message, max_chars=180).strip()
        recommendation = summarize_text(raw_recommendation, max_chars=180).strip()
        if not message or not recommendation:
            continue
        priority = normalize_outline_review_priority(raw_priority)
        key = f"{priority}\n{message}\n{recommendation}"
        if key in seen:
            continue
        seen.add(key)
        suggestions.append(build_outline_repair_suggestion(message, recommendation, priority))
    return suggestions
```

- [ ] **Step 4: Run parser tests to verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_outline_review_priority_sections_parse_and_cap_items tests/test_web_service.py::test_outline_review_legacy_pairing_defaults_to_low_priority tests/test_web_service.py::test_outline_review_suggestions_pair_numbered_issues_with_recommendations -q
```

Expected: PASS.

- [ ] **Step 5: Commit backend parser**

Run:

```bash
git add src/ai_novelist/web/outline_service.py tests/test_web_service.py
git commit -m "feat: parse prioritized outline review issues"
```

---

### Task 2: Outline Editor Prompt Contract

**Files:**
- Modify: `src/ai_novelist/prompts/outline_editor.md`
- Test: `tests/test_prompt_loader.py`

- [ ] **Step 1: Update prompt test first**

Replace the assertions in `test_outline_editor_prompt_keeps_parseable_status_and_review_boundary()` that check the old flat caps with these assertions:

```python
    assert "高优先级问题" in prompt
    assert "低优先级问题" in prompt
    assert "建议问题" in prompt
    assert "高优先级问题必须尽量一次性列全" in prompt
    assert "低优先级问题最多 20 条" in prompt
    assert "建议问题最多 10 条" in prompt
    assert "推荐修改意见" in prompt
    assert "主要问题最多 10 条" not in prompt
    assert "修改建议最多 10 条" not in prompt
```

Keep the existing status, score, boundary, and forbidden-content assertions.

- [ ] **Step 2: Run prompt test to verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py::test_outline_editor_prompt_keeps_parseable_status_and_review_boundary -q
```

Expected: FAIL because `outline_editor.md` still uses the old `主要问题` and `修改建议` caps.

- [ ] **Step 3: Update `outline_editor.md`**

Replace the output budget and Markdown sections in `src/ai_novelist/prompts/outline_editor.md` with this contract:

```markdown
优先级规则：
- 高优先级问题：会阻塞章节细纲、违反 locked_constraints、造成前后硬冲突、或留下必须先决策的结构缺口。高优先级问题必须尽量一次性列全，不得因为数量超过 10 条而省略真实阻塞项。
- 低优先级问题：影响质量、连续性或清晰度，但不直接阻塞进入章节细纲。低优先级问题最多 20 条。
- 建议问题：优化项、章节细纲参考项或可后置处理的问题。建议问题最多 10 条。

输出预算：
- 高优先级问题工程安全上限 50 条，每条不超过 100 中文字符。
- 低优先级问题最多 20 条，每条不超过 90 中文字符。
- 建议问题最多 10 条，每条不超过 90 中文字符。
- 锁定约束检查最多 3 条。

输出 Markdown，包含：
## 总体判断
简述 STATUS 和 QUALITY_SCORE 的依据，不超过 120 中文字符。

## 高优先级问题
列出所有阻塞项；每条格式为“问题描述。——推荐修改意见：具体修复建议。”；没有则写“暂无”。

## 低优先级问题
最多 20 条；每条格式为“问题描述。——推荐修改意见：具体修复建议。”；没有则写“暂无”。

## 建议问题
最多 10 条；每条格式为“问题描述。——推荐修改意见：具体建议或后置处理方式。”；没有则写“暂无”。

## 锁定约束检查
检查是否违反 locked_constraints；没有则写“未发现”。

## 下一步建议
只写 pass/revise/stop 对应的下一步，不展开创作方案。
```

Preserve the existing top status block, judgment rules, and boundaries. Remove the old `## 主要问题` and `## 修改建议` instructions from the prompt.

- [ ] **Step 4: Run prompt test to verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_prompt_loader.py::test_outline_editor_prompt_keeps_parseable_status_and_review_boundary -q
```

Expected: PASS.

- [ ] **Step 5: Commit prompt contract**

Run:

```bash
git add src/ai_novelist/prompts/outline_editor.md tests/test_prompt_loader.py
git commit -m "feat: request prioritized outline review"
```

---

### Task 3: Priority-Aware Apply Instruction Ordering

**Files:**
- Modify: `src/ai_novelist/web/outline_service.py`
- Test: `tests/test_web_service.py`

- [ ] **Step 1: Write failing apply-order test**

Add this test near the other `selected_outline_revision_instruction` or apply-decision tests in `tests/test_web_service.py`:

```python
def test_outline_review_revision_instruction_orders_selected_items_by_priority() -> None:
    report = {
        "repair_suggestions": [
            {
                "id": "suggestion-1",
                "message": "建议项。",
                "recommendation": "建议项修复。",
                "priority": "suggestion",
            },
            {
                "id": "low-1",
                "message": "低优先级项。",
                "recommendation": "低优先级修复。",
                "priority": "low",
            },
            {
                "id": "high-1",
                "message": "高优先级项。",
                "recommendation": "高优先级修复。",
                "priority": "high",
            },
        ]
    }

    instruction = outline_service.selected_outline_revision_instruction(
        report,
        selected_issue_ids=None,
        decisions=[
            {"issue_id": "suggestion-1", "decision": "recommended", "custom_answer": ""},
            {"issue_id": "low-1", "decision": "recommended", "custom_answer": ""},
            {"issue_id": "high-1", "decision": "recommended", "custom_answer": ""},
        ],
    )

    assert instruction.index("高优先级项。 -> 高优先级修复。") < instruction.index("低优先级项。 -> 低优先级修复。")
    assert instruction.index("低优先级项。 -> 低优先级修复。") < instruction.index("建议项。 -> 建议项修复。")
```

- [ ] **Step 2: Run apply-order test to verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_outline_review_revision_instruction_orders_selected_items_by_priority -q
```

Expected: FAIL because current decision handling preserves submitted order.

- [ ] **Step 3: Implement priority sorting for selected suggestions**

In `src/ai_novelist/web/outline_service.py`, add this helper near the priority constants:

```python
def outline_review_priority_rank(value: Any) -> int:
    priority = normalize_outline_review_priority(value)
    return OUTLINE_REVIEW_PRIORITY_ORDER.index(priority)
```

Update `outline_revision_instruction_from_decisions()` so it collects selected suggestion dicts and custom lines, then orders selected items by priority before rendering. Use this structure:

```python
    selected_items: list[dict[str, Any]] = []
    custom_lines: list[tuple[int, str]] = []
    for raw_decision in decisions:
        issue_id = str(raw_decision.get("issue_id") or "").strip()
        decision = str(raw_decision.get("decision") or "").strip()
        if issue_id not in suggestions_by_id:
            raise LocalStoreError("未找到选中的大纲审查建议")
        suggestion = suggestions_by_id[issue_id]
        if decision == "skip":
            continue
        if decision == "recommended":
            selected_items.append(suggestion)
            continue
        if decision == "custom":
            custom_answer = str(raw_decision.get("custom_answer") or "").strip()
            if not custom_answer:
                raise LocalStoreError("我的意见不能为空")
            message = str(suggestion.get("message") or "").strip()
            line = f"- {message} -> {custom_answer}" if message else f"- {custom_answer}"
            custom_lines.append((outline_review_priority_rank(suggestion.get("priority")), line))
            continue
        raise LocalStoreError("不支持的大纲审查处理方式")
    lines: list[str] = []
    for item in sorted(selected_items, key=lambda item: outline_review_priority_rank(item.get("priority"))):
        lines.extend(outline_revision_instruction_lines([item]))
    lines.extend(line for _, line in sorted(custom_lines, key=lambda item: item[0]))
```

Keep the existing empty-selection guard and return prefix.

- [ ] **Step 4: Run apply-order tests to verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_outline_review_revision_instruction_orders_selected_items_by_priority tests/test_web_service.py::test_apply_outline_review_uses_recommended_custom_and_skip_decisions -q
```

Expected: PASS.

- [ ] **Step 5: Commit apply ordering**

Run:

```bash
git add src/ai_novelist/web/outline_service.py tests/test_web_service.py
git commit -m "feat: order outline review apply by priority"
```

---

### Task 4: Frontend Priority Defaults And Grouping

**Files:**
- Modify: `web/frontend/src/types.ts`
- Modify: `web/frontend/src/main.tsx`
- Modify: `web/frontend/src/workspaces/review.tsx`
- Test: `tests/test_frontend_review_tabs_structure.py`

- [ ] **Step 1: Write failing frontend source tests**

Add these tests near the existing outline review workspace tests in `tests/test_frontend_review_tabs_structure.py`:

```python
def test_outline_review_suggestion_type_exposes_priority() -> None:
    source = read_types()

    assert "export type OutlineReviewSuggestionPriority = 'high' | 'low' | 'suggestion';" in source
    assert "priority?: OutlineReviewSuggestionPriority" in source


def test_outline_review_decisions_default_by_priority() -> None:
    source = read_main()

    assert "function outlineReviewSuggestionPriority" in source
    assert "item.priority || 'low'" in source
    assert "priority === 'suggestion' ? 'skip' : 'recommended'" in source


def test_outline_review_decision_board_groups_by_priority() -> None:
    source = read_workspace("review.tsx")

    assert "const OUTLINE_REPAIR_PRIORITY_GROUPS" in source
    assert "高优先级问题" in source
    assert "低优先级问题" in source
    assert "建议问题" in source
    assert "group.items.map" in source
```

- [ ] **Step 2: Run frontend tests to verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py::test_outline_review_suggestion_type_exposes_priority tests/test_frontend_review_tabs_structure.py::test_outline_review_decisions_default_by_priority tests/test_frontend_review_tabs_structure.py::test_outline_review_decision_board_groups_by_priority -q
```

Expected: FAIL because priority type/default/grouping does not exist.

- [ ] **Step 3: Add frontend type**

In `web/frontend/src/types.ts`, add before `OutlineReviewSuggestion`:

```typescript
export type OutlineReviewSuggestionPriority = 'high' | 'low' | 'suggestion';
```

Update `OutlineReviewSuggestion`:

```typescript
export type OutlineReviewSuggestion = {
  id: string;
  severity: string;
  category: string;
  message: string;
  recommendation: string;
  priority?: OutlineReviewSuggestionPriority;
  selected: boolean;
};
```

- [ ] **Step 4: Add frontend decision default helper**

In `web/frontend/src/main.tsx`, add this helper near `buildOutlineRepairDecisionMap()`:

```typescript
function outlineReviewSuggestionPriority(item: OutlineReviewSuggestion) {
  const priority = item.priority || 'low';
  return priority === 'high' || priority === 'low' || priority === 'suggestion' ? priority : 'low';
}
```

Update `buildOutlineRepairDecisionMap()`:

```typescript
function buildOutlineRepairDecisionMap(suggestions: OutlineReviewSuggestion[]) {
  const next: Record<string, OutlineRepairDecision> = {};
  suggestions.forEach((item) => {
    const priority = outlineReviewSuggestionPriority(item);
    next[item.id] = {
      decision: item.selected === false ? 'skip' : priority === 'suggestion' ? 'skip' : 'recommended',
      custom_answer: '',
    };
  });
  return next;
}
```

- [ ] **Step 5: Group the outline repair decision board**

In `web/frontend/src/workspaces/review.tsx`, add helpers above `OutlineReviewWorkspace`:

```typescript
const OUTLINE_REPAIR_PRIORITY_GROUPS = [
  { priority: 'high', label: '高优先级问题' },
  { priority: 'low', label: '低优先级问题' },
  { priority: 'suggestion', label: '建议问题' },
] as const;

function outlineRepairPriority(item: OutlineReviewSuggestion) {
  const priority = item.priority || 'low';
  return priority === 'high' || priority === 'low' || priority === 'suggestion' ? priority : 'low';
}

function groupOutlineRepairSuggestions(suggestions: OutlineReviewSuggestion[]) {
  return OUTLINE_REPAIR_PRIORITY_GROUPS
    .map((group) => ({
      ...group,
      items: suggestions.filter((item) => outlineRepairPriority(item) === group.priority),
    }))
    .filter((group) => group.items.length > 0);
}
```

Update `OutlineRepairDecisionBoard()` to render groups:

```tsx
  const groups = groupOutlineRepairSuggestions(suggestions);
  return (
    <div className="outline-repair-decisions" aria-label="大纲审查建议">
      {groups.map((group) => (
        <section className="outline-repair-priority-group" key={group.priority}>
          <h2>{group.label}</h2>
          <div className="outline-repair-table" role="table" aria-label={group.label}>
            <div className="outline-repair-row outline-repair-decision-head" role="row">
              <span role="columnheader">问题</span>
              <span role="columnheader">推荐修改意见</span>
              <span role="columnheader">暂不修改</span>
              <span role="columnheader">我的意见</span>
            </div>
            {group.items.map((item) => {
              const value = decisions[item.id] || { decision: 'recommended', custom_answer: '' };
              return (
                <div className="outline-repair-row outline-repair-decision-row" role="row" key={item.id}>
                  <span role="cell">
                    <strong>{item.message}</strong>
                    <small>{item.severity || 'normal'} · {item.category || 'review'}</small>
                  </span>
                  <label role="cell">
                    <input type="radio" name={`outline-repair-${item.id}`} checked={value.decision === 'recommended'} onChange={() => onDecisionChange(item.id, 'recommended')} />
                    <span>{item.recommendation}</span>
                  </label>
                  <label role="cell">
                    <input type="radio" name={`outline-repair-${item.id}`} checked={value.decision === 'skip'} onChange={() => onDecisionChange(item.id, 'skip')} />
                    <span>暂不修改</span>
                  </label>
                  <label role="cell" className="custom-repair-choice">
                    <span>
                      <input type="radio" name={`outline-repair-${item.id}`} checked={value.decision === 'custom'} onChange={() => onDecisionChange(item.id, 'custom')} />
                      我的意见
                    </span>
                    <textarea value={value.custom_answer} onChange={(event) => onCustomAnswerChange(item.id, event.target.value)} disabled={value.decision !== 'custom'} placeholder="写入你的采纳意见" />
                  </label>
                </div>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
```

This keeps the existing row markup and only wraps rows into priority groups.

- [ ] **Step 6: Run frontend tests and build to verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py::test_outline_review_suggestion_type_exposes_priority tests/test_frontend_review_tabs_structure.py::test_outline_review_decisions_default_by_priority tests/test_frontend_review_tabs_structure.py::test_outline_review_decision_board_groups_by_priority tests/test_frontend_review_tabs_structure.py::test_outline_review_workspace_renders_apply_completion_state -q
npm --prefix web/frontend run build
```

Expected: pytest PASS; build PASS with the known Vite CJS Node API deprecation warning.

- [ ] **Step 7: Commit frontend priority UI**

Run:

```bash
git add web/frontend/src/types.ts web/frontend/src/main.tsx web/frontend/src/workspaces/review.tsx tests/test_frontend_review_tabs_structure.py
git commit -m "feat: group outline review issues by priority"
```

---

### Task 5: Documentation And Final Verification

**Files:**
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Update implementation docs**

Append this section to `docs/IMPLEMENTATION_PLAN.md`:

```markdown
### Outline Review Priority Audit

- Overall outline review now separates repair suggestions into high-priority, low-priority, and suggestion groups.
- High-priority items represent blockers and hard conflicts and are not capped at 10; the backend uses a safety cap of 50.
- Low-priority items are capped at 20, suggestion items are capped at 10.
- The Web decision board groups these priorities and defaults high/low items to recommended while defaulting suggestion items to skip.
- Historical flat reports remain compatible and are treated as low priority.
```

- [ ] **Step 2: Update session summary**

Append this section to `docs/SESSION_SUMMARY.md`:

```markdown
### Follow-up: Outline Review Priority Audit
- Files changed: `src/ai_novelist/web/outline_service.py`, `src/ai_novelist/prompts/outline_editor.md`, `web/frontend/src/types.ts`, `web/frontend/src/main.tsx`, `web/frontend/src/workspaces/review.tsx`, tests, and docs.
- Behavior changed: overall outline review suggestions now carry `priority=high|low|suggestion`; high-priority blockers are parsed as one review batch with a safety cap of 50, low-priority issues are capped at 20, and suggestion issues are capped at 10. The frontend groups these priorities and defaults suggestion items to skip.
- Verification: record RED/green parser, prompt, apply-order, frontend structure, affected Web service, frontend build, and `git diff --check` results here after running them.
- Remaining risk: no live browser click test or real model review run was performed; coverage is service parsing/apply behavior, prompt contract, source-level frontend behavior, and TypeScript build.
```

- [ ] **Step 3: Run affected backend tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_prompt_loader.py -q
```

Expected: PASS.

- [ ] **Step 4: Run frontend structure tests and build**

Run:

```bash
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py -q
npm --prefix web/frontend run build
```

Expected: pytest PASS; build PASS with the known Vite CJS Node API deprecation warning.

- [ ] **Step 5: Run diff validation**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 6: Fill final verification details in `docs/SESSION_SUMMARY.md`**

Replace the verification line from Step 2 with a sentence that records the exact output from Steps 3, 4, and 5. The sentence must include the backend pytest command and pass count, the frontend pytest command and pass count, the frontend build result including the known Vite CJS warning, and the `git diff --check` result. Do not leave generic wording in the final session summary.

- [ ] **Step 7: Commit docs and final verification**

Run:

```bash
git add docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "docs: record outline review priority audit"
```

- [ ] **Step 8: Confirm clean worktree**

Run:

```bash
git status --short
```

Expected: no output.
