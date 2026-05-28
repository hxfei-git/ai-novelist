# Outline Review Pending Choices Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make overall outline review suggestions use the same three-choice pending-question interaction as outline stage confirmations, with custom user opinions included in apply.

**Architecture:** Keep the existing outline review report and apply endpoint, but add a decision payload beside the current `selected_issue_ids` compatibility path. Backend decision normalization builds one revision instruction from recommended, skipped, and custom choices; frontend renders each repair suggestion with `推荐修改意见`, `暂不修改`, and `我的意见`, then submits per-item decisions.

**Tech Stack:** Python 3.11+, FastAPI/StreamingResponse, pytest, React + TypeScript in `web/frontend/src/main.tsx`, Vite frontend build.

---

## File Structure

- Modify `src/ai_novelist/web/service.py`
  - Add decision normalization for outline review apply.
  - Extend `selected_outline_revision_instruction()` or route it through a new helper that accepts `decisions`.
  - Keep `selected_issue_ids` behavior compatible.
- Modify `src/ai_novelist/web/app.py`
  - Parse `payload["decisions"]` and pass it to `service.apply_outline_review()`.
- Modify `web/frontend/src/main.tsx`
  - Add outline review decision state.
  - Replace checkbox-style overall outline review apply payload with per-item decisions.
  - Render three-choice controls for overall outline review suggestions.
  - Keep chapter outline review unchanged unless shared helper typing requires a non-behavioral adjustment.
- Modify `tests/test_web_service.py`
  - Add backend coverage for recommended/custom/skip decisions and invalid custom text.
- Modify `tests/test_frontend_review_tabs_structure.py`
  - Replace the old selectable-board assertion with three-choice decision UI and payload assertions.
- Modify `docs/IMPLEMENTATION_PLAN.md`
  - Record the implementation note and verification scope.
- Modify `docs/SESSION_SUMMARY.md`
  - Record changed behavior, tests run, and any remaining risk.

## Task 1: Backend Decision Payload

**Files:**
- Modify: `src/ai_novelist/web/service.py`
- Test: `tests/test_web_service.py`

- [ ] **Step 1: Write failing backend tests**

Add these tests after `test_apply_outline_review_uses_only_selected_suggestions` in `tests/test_web_service.py`:

```python
def test_apply_outline_review_uses_recommended_custom_and_skip_decisions(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline = "# 最终锁定总大纲\n\n## 章节大纲\n旧稿。"
    store.save_state(state)
    report = service.review_outline(store, OutlineReviewAdapter(), "web-demo", "请检查总纲")
    suggestions = report["repair_suggestions"]
    recommended = suggestions[0]
    custom = suggestions[1]
    skipped = suggestions[2] if len(suggestions) > 2 else suggestions[-1]
    adapter = CapturingOutlineReviewAdapter()

    service.apply_outline_review(
        store,
        adapter,
        "web-demo",
        report["run_id"],
        decisions=[
            {"issue_id": recommended["id"], "decision": "recommended", "custom_answer": ""},
            {"issue_id": custom["id"], "decision": "custom", "custom_answer": "按我的意见收束第二卷主线，不新增支线。"},
            {"issue_id": skipped["id"], "decision": "skip", "custom_answer": ""},
        ],
    )

    assert recommended["recommendation"] in adapter.reviser_prompt
    assert "按我的意见收束第二卷主线，不新增支线。" in adapter.reviser_prompt
    assert skipped["message"] not in adapter.reviser_prompt
    assert skipped["recommendation"] not in adapter.reviser_prompt
```

Add this validation test in the same section:

```python
def test_apply_outline_review_rejects_empty_custom_decision(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline = "# 最终锁定总大纲\n\n## 章节大纲\n旧稿。"
    store.save_state(state)
    report = service.review_outline(store, OutlineReviewAdapter(), "web-demo", "请检查总纲")
    suggestion = report["repair_suggestions"][0]

    with pytest.raises(LocalStoreError, match="我的意见不能为空"):
        service.apply_outline_review(
            store,
            OutlineReviewAdapter(),
            "web-demo",
            report["run_id"],
            decisions=[{"issue_id": suggestion["id"], "decision": "custom", "custom_answer": "  "}],
        )
```

- [ ] **Step 2: Run the new backend tests and verify they fail**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_web_service.py::test_apply_outline_review_uses_recommended_custom_and_skip_decisions tests/test_web_service.py::test_apply_outline_review_rejects_empty_custom_decision -q
```

Expected: fail because `apply_outline_review()` does not accept `decisions`.

- [ ] **Step 3: Implement backend normalization**

In `src/ai_novelist/web/service.py`, add this helper near `selected_outline_revision_instruction()`:

```python
def selected_outline_revision_instruction(
    report: dict[str, Any],
    selected_issue_ids: list[str] | None,
    decisions: list[dict[str, Any]] | None = None,
) -> str:
    suggestions = [item for item in report.get("repair_suggestions", []) if isinstance(item, dict)]
    if decisions is not None:
        return outline_revision_instruction_from_decisions(report, suggestions, decisions)
    selected_ids = [str(item) for item in (selected_issue_ids or []) if str(item).strip()]
    if selected_issue_ids is not None and not selected_ids:
        raise LocalStoreError("请选择至少一条大纲审查建议")
    if selected_ids:
        suggestions = [item for item in suggestions if str(item.get("id") or "") in selected_ids]
        if not suggestions:
            raise LocalStoreError("未找到选中的大纲审查建议")
    if suggestions:
        lines = outline_revision_instruction_lines(suggestions)
        if lines:
            return "仅采纳以下选中的大纲审查建议：\n" + "\n".join(lines)
    return str(report.get("revision_instruction") or report.get("summary") or report.get("notes") or "").strip()
```

Add these helpers immediately above or below it:

```python
def outline_revision_instruction_lines(suggestions: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in suggestions:
        message = str(item.get("message") or "").strip()
        recommendation = str(item.get("recommendation") or message).strip()
        if message and recommendation and message != recommendation:
            lines.append(f"- {message} -> {recommendation}")
        elif recommendation:
            lines.append(f"- {recommendation}")
    return lines


def outline_revision_instruction_from_decisions(
    report: dict[str, Any],
    suggestions: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
) -> str:
    by_id = {str(item.get("id") or ""): item for item in suggestions}
    lines: list[str] = []
    for raw in decisions:
        issue_id = str(raw.get("issue_id") or "").strip()
        decision = str(raw.get("decision") or "").strip()
        if issue_id not in by_id:
            raise LocalStoreError("未找到选中的大纲审查建议")
        if decision == "skip":
            continue
        if decision == "recommended":
            lines.extend(outline_revision_instruction_lines([by_id[issue_id]]))
            continue
        if decision == "custom":
            custom_answer = str(raw.get("custom_answer") or "").strip()
            if not custom_answer:
                raise LocalStoreError("我的意见不能为空")
            message = str(by_id[issue_id].get("message") or "").strip()
            if message:
                lines.append(f"- {message} -> {custom_answer}")
            else:
                lines.append(f"- {custom_answer}")
            continue
        raise LocalStoreError("不支持的大纲审查处理方式")
    if not lines:
        raise LocalStoreError("请选择至少一条大纲审查建议")
    return "按用户逐项确认采纳以下大纲审查意见：\n" + "\n".join(lines)
```

Update `apply_outline_review()` signature and call:

```python
def apply_outline_review(
    store: LocalStore,
    adapter: AgentAdapter,
    project_id: str,
    run_id: str,
    progress: ProgressFunc | None = None,
    selected_issue_ids: list[str] | None = None,
    decisions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
```

Replace:

```python
state.revision_instruction = selected_outline_revision_instruction(report, selected_issue_ids)
state.editor_notes = state.revision_instruction if selected_issue_ids is not None else str(report.get("notes") or "")
```

with:

```python
state.revision_instruction = selected_outline_revision_instruction(report, selected_issue_ids, decisions)
state.editor_notes = state.revision_instruction if selected_issue_ids is not None or decisions is not None else str(report.get("notes") or "")
```

- [ ] **Step 4: Run backend tests and verify they pass**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_web_service.py::test_apply_outline_review_uses_recommended_custom_and_skip_decisions tests/test_web_service.py::test_apply_outline_review_rejects_empty_custom_decision tests/test_web_service.py::test_apply_outline_review_uses_only_selected_suggestions -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit backend task**

Run:

```bash
git add src/ai_novelist/web/service.py tests/test_web_service.py
git commit -m "feat: apply outline review decisions"
```

## Task 2: API Route Decision Parsing

**Files:**
- Modify: `src/ai_novelist/web/app.py`
- Test: `tests/test_web_app.py`

- [ ] **Step 1: Write failing route test**

Add this route exposure test near the existing web app outline review tests in `tests/test_web_app.py`:

```python
def test_outline_review_apply_route_accepts_decisions(tmp_path) -> None:
    store = LocalStore(tmp_path)
    app = create_app(store=store)
    routes = {getattr(route, "path", ""): route for route in app.routes}

    route = routes["/api/projects/{project_id}/outline/review/{run_id}/apply"]
    source = route.endpoint.__code__.co_names

    assert "decisions" in source
```

- [ ] **Step 2: Run route test and verify it fails**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_web_app.py::test_outline_review_apply_route_accepts_decisions -q
```

Expected: fail because the route does not parse/pass `decisions`.

- [ ] **Step 3: Parse decisions in the route**

In `src/ai_novelist/web/app.py`, inside `apply_outline_review()`, add:

```python
        raw_decisions = payload.get("decisions")
        decisions = raw_decisions if isinstance(raw_decisions, list) else None
```

Then update the service call:

```python
                lambda progress: service.apply_outline_review(
                    store,
                    adapter(payload),
                    project_id,
                    run_id,
                    progress,
                    selected_issue_ids=selected_issue_ids,
                    decisions=decisions,
                )
```

- [ ] **Step 4: Run route test and verify it passes**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_web_app.py::test_outline_review_apply_route_accepts_decisions -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit API task**

Run:

```bash
git add src/ai_novelist/web/app.py tests/test_web_app.py
git commit -m "feat: accept outline review decisions in api"
```

## Task 3: Frontend Three-Choice Overall Review UI

**Files:**
- Modify: `web/frontend/src/main.tsx`
- Test: `tests/test_frontend_review_tabs_structure.py`

- [ ] **Step 1: Write failing frontend structure test**

Replace `test_outline_review_uses_selectable_suggestion_board()` in `tests/test_frontend_review_tabs_structure.py` with:

```python
def test_outline_review_uses_three_choice_decision_board() -> None:
    source = read_main()

    assert "outlineRepairDecisions" in source
    assert "推荐修改意见" in source
    assert "暂不修改" in source
    assert "我的意见" in source
    assert "custom_answer" in source
    assert "decisions:" in source
    assert "selected_issue_ids" not in source[source.index("async function applyOutlineReview"):source.index("function dismissOutlineReview")]
```

- [ ] **Step 2: Run frontend structure test and verify it fails**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py::test_outline_review_uses_three_choice_decision_board -q
```

Expected: fail because the frontend still uses `selectedOutlineRepairIds` and `selected_issue_ids`.

- [ ] **Step 3: Add frontend decision types and state**

In `web/frontend/src/main.tsx`, near existing review types, add:

```ts
type OutlineRepairDecisionValue = 'recommended' | 'skip' | 'custom';

type OutlineRepairDecision = {
  decision: OutlineRepairDecisionValue;
  custom_answer: string;
};
```

Replace overall-outline-only state:

```ts
const [selectedOutlineRepairIds, setSelectedOutlineRepairIds] = useState<Record<string, boolean>>({});
```

with:

```ts
const [outlineRepairDecisions, setOutlineRepairDecisions] = useState<Record<string, OutlineRepairDecision>>({});
```

Keep chapter outline state as `selectedChapterOutlineRepairIds` so chapter review behavior does not change.

- [ ] **Step 4: Add decision map helper**

Near `buildOutlineRepairSelectionMap()`, add:

```ts
function buildOutlineRepairDecisionMap(suggestions: OutlineReviewSuggestion[]): Record<string, OutlineRepairDecision> {
  return Object.fromEntries(
    suggestions.map((item) => [
      item.id,
      { decision: 'recommended' as OutlineRepairDecisionValue, custom_answer: '' },
    ]),
  );
}
```

In `loadLatestOutlineReview()`, replace:

```ts
setSelectedOutlineRepairIds(buildOutlineRepairSelectionMap(latest.repair_suggestions || []));
```

with:

```ts
setOutlineRepairDecisions(buildOutlineRepairDecisionMap(latest.repair_suggestions || []));
```

- [ ] **Step 5: Submit decisions from `applyOutlineReview()`**

Replace the current selected-id logic in `applyOutlineReview()`:

```ts
const selectedIssueIds = suggestions.filter((item) => selectedOutlineRepairIds[item.id] !== false).map((item) => item.id);
if (suggestions.length > 0 && selectedIssueIds.length === 0) {
  pushLog({ label: '大纲总体审查', elapsed: '', tokens: '', context: '', status: 'no_selection' });
  return;
}
```

with:

```ts
const decisions = suggestions.map((item) => ({
  issue_id: item.id,
  decision: outlineRepairDecisions[item.id]?.decision || 'recommended',
  custom_answer: outlineRepairDecisions[item.id]?.custom_answer || '',
}));
const activeDecisions = decisions.filter((item) => item.decision !== 'skip');
const emptyCustom = activeDecisions.find((item) => item.decision === 'custom' && !item.custom_answer.trim());
if (suggestions.length > 0 && activeDecisions.length === 0) {
  pushLog({ label: '大纲总体审查', elapsed: '', tokens: '', context: '', status: 'no_selection' });
  return;
}
if (emptyCustom) {
  showError(new Error('请先填写“我的意见”再应用。'));
  return;
}
```

Replace the stream payload:

```ts
{ selected_issue_ids: selectedIssueIds },
```

with:

```ts
{ decisions },
```

- [ ] **Step 6: Render three-choice controls**

Update the overall outline review usage of `OutlineRepairSuggestionBoard` so it receives decision props:

```tsx
<OutlineRepairSuggestionBoard
  suggestions={outlineReview.repair_suggestions || []}
  decisions={outlineRepairDecisions}
  onDecisionChange={(id, decision) =>
    setOutlineRepairDecisions((current) => ({
      ...current,
      [id]: { ...(current[id] || { decision: 'recommended', custom_answer: '' }), decision },
    }))
  }
  onCustomAnswerChange={(id, custom_answer) =>
    setOutlineRepairDecisions((current) => ({
      ...current,
      [id]: { ...(current[id] || { decision: 'recommended', custom_answer: '' }), custom_answer },
    }))
  }
/>
```

Change only the component branch used for overall outline review. Leave chapter outline review's checkbox selection props intact or split the component into two small components if that is simpler:

```tsx
function OutlineRepairDecisionBoard({
  suggestions,
  decisions,
  onDecisionChange,
  onCustomAnswerChange,
}: {
  suggestions: OutlineReviewSuggestion[];
  decisions: Record<string, OutlineRepairDecision>;
  onDecisionChange: (id: string, decision: OutlineRepairDecisionValue) => void;
  onCustomAnswerChange: (id: string, value: string) => void;
}) {
  return (
    <div className="repair-board">
      {suggestions.map((item) => {
        const value = decisions[item.id] || { decision: 'recommended', custom_answer: '' };
        return (
          <div className="repair-item" key={item.id}>
            <div className="repair-message">{item.message}</div>
            <label>
              <input type="radio" checked={value.decision === 'recommended'} onChange={() => onDecisionChange(item.id, 'recommended')} />
              推荐修改意见
            </label>
            <label>
              <input type="radio" checked={value.decision === 'skip'} onChange={() => onDecisionChange(item.id, 'skip')} />
              暂不修改
            </label>
            <label>
              <input type="radio" checked={value.decision === 'custom'} onChange={() => onDecisionChange(item.id, 'custom')} />
              我的意见
            </label>
            <textarea
              value={value.custom_answer}
              onChange={(event) => onCustomAnswerChange(item.id, event.target.value)}
              disabled={value.decision !== 'custom'}
              placeholder="写入你的采纳意见"
            />
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 7: Run frontend test and build**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py::test_outline_review_uses_three_choice_decision_board -q
npm --prefix web/frontend run build
```

Expected: test passes and Vite build succeeds.

- [ ] **Step 8: Commit frontend task**

Run:

```bash
git add web/frontend/src/main.tsx tests/test_frontend_review_tabs_structure.py
git commit -m "feat: add outline review decision controls"
```

## Task 4: Docs and Focused Verification

**Files:**
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Update implementation notes**

Append this section to `docs/IMPLEMENTATION_PLAN.md`:

```markdown
### 2026-05-28 大纲总体审查三栏采纳

目标：让大纲总体审查和各阶段待确认问题保持一致，每条建议都能选择“推荐修改意见 / 暂不修改 / 我的意见”，其中“我的意见”参与采纳应用。

- 后端 `apply_outline_review()` 新增 `decisions` 逐项决策输入，兼容旧的 `selected_issue_ids`。
- `recommended` 写入审查推荐，`custom` 写入用户自定义意见，`skip` 不进入修订指令。
- Web 大纲总体审查页改为三栏决策控件，并在应用时提交逐项 decisions。
- 应用中的按钮状态和空自定义意见校验避免“点击后无反馈”的体验。
```

- [ ] **Step 2: Update session summary**

Append this section to `docs/SESSION_SUMMARY.md`:

```markdown
### 2026-05-28 大纲总体审查三栏采纳

- 大纲总体审查建议现在按逐项决策应用：推荐修改意见、暂不修改、我的意见。
- “我的意见”会进入后端修订指令；空自定义意见会被前端和后端拦截。
- 旧 `selected_issue_ids` 仍兼容，章节大纲审查保持现有选择行为。
- 验证范围：后端大纲审查 apply 测试、Web route 测试、前端结构测试、前端 build。
```

- [ ] **Step 3: Run focused verification**

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_web_service.py::test_apply_outline_review_uses_recommended_custom_and_skip_decisions tests/test_web_service.py::test_apply_outline_review_rejects_empty_custom_decision tests/test_web_service.py::test_apply_outline_review_uses_only_selected_suggestions tests/test_web_app.py::test_outline_review_apply_route_accepts_decisions tests/test_frontend_review_tabs_structure.py::test_outline_review_uses_three_choice_decision_board -q
npm --prefix web/frontend run build
```

Expected: focused pytest selection passes and Vite build succeeds.

- [ ] **Step 4: Commit docs and final verification note**

Run:

```bash
git add docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "docs: record outline review decision controls"
```

- [ ] **Step 5: Inspect final git state**

Run:

```bash
git status --short
```

Expected: no tracked files modified. Unrelated untracked files may remain if they existed before this task.
