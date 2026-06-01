# Outline Review Context Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix overall outline review so it reviews one effective outline, does not amplify duplicate high-priority issues, refuses patch-only applied outlines, and restores `projects/demo-web` to a usable single-outline state.

**Architecture:** Keep changes local to the outline review workflow. Add tests around existing helpers in `tests/test_web_service.py`, then update `graph_outline.py`, `outline_service.py`, and `outline_actions.py`. Clean `projects/demo-web` with the existing outline stage artifacts as the canonical single effective outline source.

**Tech Stack:** Python 3.11+, pytest, existing `LocalStore`, `NovelState`, and Web outline service/action modules.

---

## File Structure

- Modify `tests/test_web_service.py`: add focused regression tests near existing outline review tests.
- Modify `src/ai_novelist/graph_outline.py`: suppress numbered `最近大纲版本` blocks for `outline_editor`; optionally request complete outlines for review-apply revisions.
- Modify `src/ai_novelist/web/outline_service.py`: add issue-message normalization/deduplication and patch-shell detection helper.
- Modify `src/ai_novelist/web/outline_actions.py`: disable heuristic high-priority continuation without a deterministic truncation signal; validate applied revised outline before saving.
- Modify `projects/demo-web/outline.md`: replace revision-log shell with one effective outline.
- Modify `projects/demo-web/state.json`: mirror the cleaned effective outline and trim active polluted review state.
- Modify `docs/IMPLEMENTATION_PLAN.md`: record workflow and persistence behavior changes.
- Modify `docs/SESSION_SUMMARY.md`: record implementation notes, tests run, and remaining risk.

## Task 1: Regression Tests For Prompt, Suggestions, And Continuation

**Files:**
- Modify: `tests/test_web_service.py`
- Modify: `src/ai_novelist/graph_outline.py`
- Modify: `src/ai_novelist/web/outline_service.py`
- Modify: `src/ai_novelist/web/outline_actions.py`

- [ ] **Step 1: Add failing tests**

Add these tests near the existing outline review priority tests in `tests/test_web_service.py`:

```python
def test_outline_editor_prompt_omits_numbered_recent_outline_versions(tmp_path: Path) -> None:
    from ai_novelist.graph_outline import build_outline_prompt

    state = NovelState(project_id="web-demo", title="Web Demo", idea="修仙复仇")
    state.outline = "# 当前有效大纲\n\n## 方向定位\n只审查这一份。"
    state.outline_versions = [
        {"label": "修订后大纲", "content": "旧版本 A"},
        {"label": "修订后大纲", "content": "旧版本 B"},
        {"label": "修订后大纲", "content": "旧版本 C"},
    ]

    prompt = build_outline_prompt(state, "outline_editor")

    assert "当前大纲：\n# 当前有效大纲" in prompt
    assert "最近大纲版本：" not in prompt
    assert "版本 0:" not in prompt
    assert "版本 1:" not in prompt
    assert "版本 2:" not in prompt
    assert "旧版本 A" not in prompt
    assert "旧版本 B" not in prompt
    assert "旧版本 C" not in prompt


def test_outline_review_deduplicates_same_message_with_different_recommendations() -> None:
    notes = """STATUS: revise
QUALITY_SCORE: 70

## 高优先级问题
1. 版本2中“修订摘要”与“变更区块”内容重复，冗余。——推荐修改意见：精简版本2“修订摘要”表格，仅保留变更项编号和简要描述。
2. 版本2中“修订摘要”与“变更区块”内容重复，冗余。——推荐修改意见：删除“修订摘要”表格，仅保留“变更区块”作为唯一修订记录。
"""

    suggestions = outline_service.build_outline_repair_suggestions(notes, "", "")

    assert len(suggestions) == 1
    assert suggestions[0]["message"] == "版本2中“修订摘要”与“变更区块”内容重复，冗余。"
    assert suggestions[0]["recommendation"] == "精简版本2“修订摘要”表格，仅保留变更项编号和简要描述。"


def test_outline_review_does_not_continue_when_initial_high_priority_batch_is_exactly_ten(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline = "# 最终锁定总大纲\n\n## 方向定位\n已有单一大纲。"
    store.save_state(state)
    adapter = CappedHighPriorityOutlineReviewAdapter()

    report = outline_actions.review_outline(store, adapter, "web-demo", "请检查总纲")

    assert adapter.review_calls == 1
    assert len(report["repair_suggestions"]) == 10
    assert all("续审" not in item["message"] for item in report["repair_suggestions"])
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_outline_editor_prompt_omits_numbered_recent_outline_versions tests/test_web_service.py::test_outline_review_deduplicates_same_message_with_different_recommendations tests/test_web_service.py::test_outline_review_does_not_continue_when_initial_high_priority_batch_is_exactly_ten -q
```

Expected: all three tests fail before implementation.

- [ ] **Step 3: Commit failing tests**

```bash
git add tests/test_web_service.py
git commit -m "test: cover outline review context cleanup"
```

## Task 2: Fix Review Prompt Context, Deduplication, And Continuation

**Files:**
- Modify: `src/ai_novelist/graph_outline.py`
- Modify: `src/ai_novelist/web/outline_service.py`
- Modify: `src/ai_novelist/web/outline_actions.py`
- Test: `tests/test_web_service.py`

- [ ] **Step 1: Remove recent versions from `outline_editor` prompt**

In `src/ai_novelist/graph_outline.py`, replace the tail of `build_outline_prompt()` with prompt-specific version context:

```python
def build_outline_prompt(state: NovelState, prompt_name: str) -> str:
    template = load_prompt(prompt_name)
    versions = "\n\n".join(
        f"版本 {idx}: {item.get('label', '')}\n{item.get('content', '')}"
        for idx, item in enumerate(state.outline_versions[-3:])
    )
    if prompt_name == "outline_editor":
        version_context = ""
    else:
        version_context = f"最近大纲版本：\n{versions or '暂无'}\n"
    return (
        f"{template.rstrip()}\n\n"
        "## 项目上下文\n"
        f"标题：{state.title}\n"
        f"创意：{state.idea}\n"
        f"世界观：\n{state.worldbuilding or '暂无'}\n\n"
        f"当前大纲：\n{state.outline or '暂无'}\n\n"
        f"修订要求：{state.revision_instruction or '暂无'}\n"
        f"锁定约束：{', '.join(state.locked_constraints) or '暂无'}\n"
        f"风格偏好：{', '.join(state.style_preferences) or '暂无'}\n"
        f"参考简报：\n{state.reference_brief or '暂无'}\n\n"
        f"检索查询：{state.retrieval_query or '暂无'}\n"
        f"检索上下文：\n{state.retrieval_context or '暂无'}\n\n"
        f"检索来源：\n{format_retrieval_sources(state.retrieval_sources)}\n"
        f"原作事实：{', '.join(state.canon_facts) or '暂无'}\n"
        f"原作不确定点：{', '.join(state.research_uncertainties) or '暂无'}\n"
        "如果存在原作不确定点，必须要求用户确认，不得擅自补完原作设定。\n"
        f"编辑意见：\n{state.editor_notes or '暂无'}\n\n"
        f"{version_context}"
    )
```

- [ ] **Step 2: Deduplicate repair suggestions by normalized message**

In `src/ai_novelist/web/outline_service.py`, add this helper near `outline_suggestion_identifier()`:

```python
def normalize_outline_review_message(message: str) -> str:
    normalized = re.sub(r"\s+", "", str(message or ""))
    normalized = re.sub(r"[。；;,.，]+$", "", normalized)
    return normalized
```

Then update the seen key in `build_outline_repair_suggestions()`:

```python
    seen_messages: set[str] = set()
    for raw_message, raw_recommendation, raw_priority in raw_pairs:
        message = summarize_text(raw_message, max_chars=180).strip()
        recommendation = summarize_text(raw_recommendation, max_chars=180).strip()
        if not message or not recommendation:
            continue
        key = normalize_outline_review_message(message)
        if key in seen_messages:
            continue
        seen_messages.add(key)
        suggestions.append(build_outline_repair_suggestion(message, recommendation, raw_priority))
```

Remove the old `seen: set[str]` / `message + recommendation` logic.

- [ ] **Step 3: Disable heuristic high-priority continuation**

In `src/ai_novelist/web/outline_actions.py`, change `outline_review_needs_high_priority_continuation()` to return `False` until a deterministic truncation signal exists:

```python
def outline_review_needs_high_priority_continuation(
    suggestions: list[dict[str, Any]],
    last_high_priority_batch_count: int,
) -> bool:
    del suggestions, last_high_priority_batch_count
    return False
```

Leave `continue_outline_review_high_priority_items()` in place so future truncation support can reuse it.

- [ ] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_outline_editor_prompt_omits_numbered_recent_outline_versions tests/test_web_service.py::test_outline_review_deduplicates_same_message_with_different_recommendations tests/test_web_service.py::test_outline_review_does_not_continue_when_initial_high_priority_batch_is_exactly_ten tests/test_web_service.py::test_outline_review_priority_sections_parse_bullet_items tests/test_web_service.py::test_outline_review_legacy_pairing_defaults_to_low_priority -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit implementation**

```bash
git add src/ai_novelist/graph_outline.py src/ai_novelist/web/outline_service.py src/ai_novelist/web/outline_actions.py tests/test_web_service.py
git commit -m "fix: isolate outline review context"
```

## Task 3: Guard Against Patch-Only Applied Outlines

**Files:**
- Modify: `tests/test_web_service.py`
- Modify: `src/ai_novelist/web/outline_service.py`
- Modify: `src/ai_novelist/web/outline_actions.py`

- [ ] **Step 1: Add failing patch-shell apply test**

Add this adapter near other test adapters in `tests/test_web_service.py`:

```python
class PatchShellOutlineApplyAdapter(AgentAdapter):
    def complete(self, prompt: str, workspace: Path, options: AgentCallOptions | None = None) -> str:
        if "outline_reviser" in prompt:
            return """### 1. 修订摘要

| 编号 | 变更项 |
| :--- | :--- |
| 1 | 清理版本。 |

### 2. 变更区块

#### 变更项 1：清理重复版本
- **执行**：删除版本0、版本1，确认当前有效版本为版本2。

### 3. 保留约束
- **锁定约束**：暂无。

### 4. 未改动内容
保持原意。
"""
        return "{}"
```

Add this test near apply outline review tests:

```python
def test_apply_outline_review_rejects_patch_only_reviser_output(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline = "# 最终锁定总大纲\n\n## 方向定位\n旧有效大纲。"
    store.save_outline(state)
    store.save_state(state)
    report = outline_actions.review_outline(store, OutlineReviewAdapter(), "web-demo", "请检查总纲")

    with pytest.raises(LocalStoreError, match="修订结果不是完整有效大纲"):
        outline_actions.apply_outline_review(store, PatchShellOutlineApplyAdapter(), "web-demo", report["run_id"])

    saved = store.load_state("web-demo")
    assert saved.outline == "# 最终锁定总大纲\n\n## 方向定位\n旧有效大纲。"
    assert store.outline_path("web-demo").read_text(encoding="utf-8") == saved.outline
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_apply_outline_review_rejects_patch_only_reviser_output -q
```

Expected: FAIL because patch-only output is currently saved.

- [ ] **Step 3: Add patch-shell detection helper**

In `src/ai_novelist/web/outline_service.py`, add:

```python
PATCH_SHELL_HEADINGS = ("修订摘要", "变更区块", "保留约束", "未改动内容")


def is_patch_only_outline_text(text: str) -> bool:
    cleaned = str(text or "").strip()
    if not cleaned:
        return True
    sections = markdown_sections(cleaned)
    section_titles = set(sections)
    patch_heading_count = sum(1 for heading in PATCH_SHELL_HEADINGS if heading in section_titles)
    if patch_heading_count < 2:
        return False
    effective_sections = split_outline_review_sections(cleaned)
    return not any(value.strip() for value in effective_sections.values())
```

- [ ] **Step 4: Validate before saving applied revision**

In `src/ai_novelist/web/outline_actions.py`, import `is_patch_only_outline_text` from `outline_service`.

After:

```python
    revised = NovelState.from_dict(revise_outline_node(state.to_dict(), adapter, store))
```

add:

```python
    if is_patch_only_outline_text(revised.outline):
        state.outline = source_outline
        store.save_state(state)
        store.save_outline(state)
        raise LocalStoreError("修订结果不是完整有效大纲，已保留原大纲。")
```

Before calling `revise_outline_node`, append a complete-outline instruction:

```python
    state.revision_instruction = (
        f"{state.revision_instruction}\n\n"
        "应用要求：请输出完整有效大纲正文，不要只输出“修订摘要”或“变更区块”。"
    ).strip()
```

- [ ] **Step 5: Run apply tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_apply_outline_review_rejects_patch_only_reviser_output tests/test_web_service.py::test_outline_review_roundtrip_and_apply_updates_outline tests/test_web_service.py::test_apply_outline_review_is_idempotent_after_report_applied tests/test_web_service.py::test_apply_outline_review_uses_only_selected_suggestions -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit guard**

```bash
git add src/ai_novelist/web/outline_service.py src/ai_novelist/web/outline_actions.py tests/test_web_service.py
git commit -m "fix: reject patch-only outline revisions"
```

## Task 4: Clean `projects/demo-web`

**Files:**
- Modify: `projects/demo-web/outline.md`
- Modify: `projects/demo-web/state.json`

- [ ] **Step 1: Build a single effective outline from stage files**

Run this read-only command to preview the cleaned outline source:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path

root = Path("projects/demo-web/outline")
for name, title in [
    ("direction.md", "## 方向定位"),
    ("story_flow.md", "## 故事脉络"),
    ("worldbuilding.md", "## 世界观"),
    ("characters.md", "## 人物关系"),
    ("volume_outline.md", "## 分卷大纲"),
]:
    text = (root / name).read_text(encoding="utf-8").strip()
    print(title)
    print(text)
    print()
PY
```

Expected: output contains the five outline sections and does not start with `修订摘要`.

- [ ] **Step 2: Replace `outline.md` with one effective outline**

Run this structured cleanup command to replace `projects/demo-web/outline.md` with the current stage files as one effective outline:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path

project = Path("projects/demo-web")
sections = [
    ("方向定位", project / "outline" / "direction.md"),
    ("故事脉络", project / "outline" / "story_flow.md"),
    ("世界观", project / "outline" / "worldbuilding.md"),
    ("人物关系", project / "outline" / "characters.md"),
    ("分卷大纲", project / "outline" / "volume_outline.md"),
]
lines = ["# demo-web 有效大纲", ""]
for title, path in sections:
    text = path.read_text(encoding="utf-8").strip()
    lines.extend([f"## {title}", "", text, ""])
(project / "outline.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
PY
```

Expected: `projects/demo-web/outline.md` starts with `# demo-web 有效大纲` and contains five `##` stage sections.

- [ ] **Step 3: Update `state.json` active outline fields**

Use a small structured Python update because `state.json` is generated structured data:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

path = Path("projects/demo-web/state.json")
data = json.loads(path.read_text(encoding="utf-8"))
outline = Path("projects/demo-web/outline.md").read_text(encoding="utf-8").strip()
data["outline"] = outline
data["director_message"] = "已清理为单一有效大纲，可重新进行总体审查。"
data["outline_review_status"] = ""
data["outline_review_score"] = 0
data["outline_review_summary"] = ""
data["director_intent"] = ""
data["user_request"] = ""
data["director_action"] = ""
data["revision_instruction"] = ""
data["editor_notes"] = ""
data["review_status"] = "draft"
data["editor_decision"] = "revise"
data["outline_versions"] = [
    {
        "kind": "outline",
        "label": "清理后有效大纲",
        "content": outline,
        "created_at": "2026-06-02T00:00:00+00:00",
    }
]
data["selected_outline_version"] = 0
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
```

- [ ] **Step 4: Verify cleanup text**

Run:

```bash
rg -n "版本0|版本1|版本2|最近大纲版本|修订摘要|变更区块|大纲修订专家" projects/demo-web/outline.md projects/demo-web/state.json
```

Expected: no matches in `outline.md`; `state.json` should not contain these strings in active `outline`, `director_message`, or `outline_versions`.

- [ ] **Step 5: Commit demo cleanup**

```bash
git add projects/demo-web/outline.md projects/demo-web/state.json
git commit -m "chore: clean demo web outline state"
```

## Task 5: Docs And Final Verification

**Files:**
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`
- Possibly modify: `tests/test_web_service.py` if final verification reveals fixture drift

- [ ] **Step 1: Update implementation docs**

Add a concise entry to `docs/IMPLEMENTATION_PLAN.md` describing:

```markdown
### 2026-06-02 Outline Review Context Cleanup

- Overall outline review now receives only the current effective outline, not numbered recent outline versions.
- Outline review apply rejects patch-only reviser output before saving `outline.md`.
- Repair suggestions are deduplicated by normalized issue message.
- Automatic high-priority continuation is disabled until a deterministic truncation signal exists.
- `projects/demo-web` was restored to a single effective outline for future reviews.
```

- [ ] **Step 2: Update session summary**

Add a concise entry to `docs/SESSION_SUMMARY.md` with:

```markdown
### 2026-06-02 Outline review context cleanup

Implemented the approved cleanup for overall outline review context. Verified focused outline review parser/apply tests and cleaned `projects/demo-web` so its current outline is no longer a revision-summary shell.

Verification:
- `.venv/bin/python -m pytest tests/test_web_service.py::test_outline_editor_prompt_omits_numbered_recent_outline_versions tests/test_web_service.py::test_outline_review_deduplicates_same_message_with_different_recommendations tests/test_web_service.py::test_outline_review_does_not_continue_when_initial_high_priority_batch_is_exactly_ten tests/test_web_service.py::test_apply_outline_review_rejects_patch_only_reviser_output tests/test_web_service.py::test_outline_review_roundtrip_and_apply_updates_outline tests/test_web_service.py::test_outline_review_priority_sections_parse_bullet_items tests/test_web_service.py::test_outline_review_legacy_pairing_defaults_to_low_priority -q`
- `.venv/bin/python -m pytest tests/test_web_outline_service.py tests/test_web_chapter_service.py -q`

Remaining risk:
- Full real Codex review behavior was not exercised; verification used deterministic adapters and local project state.
```

If command output differs, record the exact failing command and reason instead of this passing verification text.

- [ ] **Step 3: Run focused regression suite**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_outline_editor_prompt_omits_numbered_recent_outline_versions tests/test_web_service.py::test_outline_review_deduplicates_same_message_with_different_recommendations tests/test_web_service.py::test_outline_review_does_not_continue_when_initial_high_priority_batch_is_exactly_ten tests/test_web_service.py::test_apply_outline_review_rejects_patch_only_reviser_output tests/test_web_service.py::test_outline_review_roundtrip_and_apply_updates_outline tests/test_web_service.py::test_outline_review_priority_sections_parse_bullet_items tests/test_web_service.py::test_outline_review_legacy_pairing_defaults_to_low_priority -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Run import smoke for web outline service**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_outline_service.py tests/test_web_chapter_service.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Inspect git diff**

Run:

```bash
git diff --stat
git diff -- src/ai_novelist/graph_outline.py src/ai_novelist/web/outline_service.py src/ai_novelist/web/outline_actions.py tests/test_web_service.py docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md projects/demo-web/outline.md projects/demo-web/state.json
```

Expected: only planned files changed.

- [ ] **Step 6: Commit final docs**

```bash
git add docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "docs: record outline review cleanup"
```

If docs were committed together with implementation in an earlier task, skip this separate commit and note that in the final response.

## Self-Review Notes

- Spec coverage: prompt context, patch-only guard, dedupe, continuation, demo cleanup, tests, and docs each map to a task.
- Scope: one workflow plus one generated demo project cleanup; no frontend redesign or broad persistence model changes.
- Placeholder scan: no placeholder markers remain; cleanup commands are explicit.
- Type consistency: helper names are `normalize_outline_review_message()` and `is_patch_only_outline_text()` throughout.
