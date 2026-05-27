# Outline Pending Confirmation Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a current-stage Web workbench that surfaces outline pending questions, offers default answers plus custom input, and submits all answers in one revision action.

**Architecture:** Add focused pending-confirmation helpers to the existing Web service layer, expose GET/POST FastAPI endpoints, and render a compact current-stage workbench in the outline edit view. Reuse the existing `run_outline_stage_node()` revision path so pending-answer submission behaves like a normal current-stage revision.

**Tech Stack:** Python 3.11+, FastAPI, existing file-backed `LocalStore`, React + TypeScript + Vite, pytest.

---

## File Structure

- Modify `src/ai_novelist/web/service.py`: own extraction, option generation, payload building, answer validation, and stage revision submission.
- Modify `src/ai_novelist/web/app.py`: add pending GET endpoint and SSE submit endpoint.
- Modify `web/frontend/src/main.tsx`: add pending payload types, loader state, answer selection state, submit action, and the pending workbench UI in the outline edit workspace.
- Modify `web/frontend/src/styles.css`: style the workbench, options, custom inputs, and validation state.
- Modify `tests/test_web_service.py`: backend TDD coverage for extraction, fallback behavior, default options, submit instruction, and validation.
- Modify `tests/test_web_app.py`: source-level route registration coverage for pending endpoints.
- Modify `tests/test_frontend_review_tabs_structure.py`: structure checks for frontend workbench controls.
- Modify `docs/IMPLEMENTATION_PLAN.md` and `docs/SESSION_SUMMARY.md`: required project documentation updates for this code change.

Note: the current worktree may contain user edits in `web/frontend/src/main.tsx` and `tests/test_frontend_review_tabs_structure.py`. Before editing, inspect those files and preserve unrelated changes.

---

### Task 1: Backend Pending Payload Extraction

**Files:**
- Modify: `src/ai_novelist/web/service.py`
- Test: `tests/test_web_service.py`

- [ ] **Step 1: Write failing extraction tests**

Add these tests to `tests/test_web_service.py` after the existing outline stage tests:

```python
def test_extract_stage_pending_questions_from_markdown_filters_status_lines() -> None:
    markdown = """# 人物关系

## 十三、待确认问题
1. 沈灵儿决裂的3-5章小纲是否需要在章节规划阶段提前完成？——影响R02中期演化强度。
2. 林霄的1-2个专属视角章的具体内容方向是否需提前规划？——影响正魔反转说服力。
暂无，当前阶段可继续修改或确认进入下一阶段。

## 仍需确认的问题
- 暂无，当前阶段可继续修改或确认进入下一阶段。
"""

    questions = service.extract_pending_questions_from_stage_markdown(markdown)

    assert questions == [
        "沈灵儿决裂的3-5章小纲是否需要在章节规划阶段提前完成？——影响R02中期演化强度。",
        "林霄的1-2个专属视角章的具体内容方向是否需提前规划？——影响正魔反转说服力。",
    ]


def test_outline_stage_pending_payload_prefers_artifact_questions(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage = "characters"
    state.pending_questions = ["请确认是否锁定人物关系并进入下一阶段，或继续提出修改。"]
    state.outline_stage_artifacts["characters"] = {
        "stage": "characters",
        "status": "options_ready",
        "pending_questions": ["artifact question?"],
    }
    store.save_outline_artifact(state, "characters", "## 十三、待确认问题\n1. markdown question?\n")
    store.save_state(state)

    payload = service.outline_stage_pending_payload(store, "web-demo", "characters")

    assert payload["project_id"] == "web-demo"
    assert payload["stage"] == "characters"
    assert [item["question"] for item in payload["items"]] == ["artifact question?"]
    assert payload["items"][0]["options"][0]["id"] == "accept"
    assert payload["items"][0]["options"][-1]["id"] == "keep"


def test_outline_stage_pending_payload_falls_back_to_markdown(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage = "characters"
    state.pending_questions = ["请确认是否锁定人物关系并进入下一阶段，或继续提出修改。"]
    store.save_outline_artifact(
        state,
        "characters",
        "## 十三、待确认问题\n"
        "1. 最终战隐藏据点势力是否有具体来源？——若不归渊遗民已覆盖，则无需额外设定。\n",
    )
    store.save_state(state)

    payload = service.outline_stage_pending_payload(store, "web-demo", "characters")

    assert [item["question"] for item in payload["items"]] == [
        "最终战隐藏据点势力是否有具体来源？——若不归渊遗民已覆盖，则无需额外设定。"
    ]
    assert payload["items"][0]["id"]
    assert any(option["label"] == "采纳建议" for option in payload["items"][0]["options"])
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_extract_stage_pending_questions_from_markdown_filters_status_lines tests/test_web_service.py::test_outline_stage_pending_payload_prefers_artifact_questions tests/test_web_service.py::test_outline_stage_pending_payload_falls_back_to_markdown -q
```

Expected: fail with missing `extract_pending_questions_from_stage_markdown` or `outline_stage_pending_payload`.

- [ ] **Step 3: Implement extraction helpers**

Add these helpers near the existing outline review helper functions in `src/ai_novelist/web/service.py`:

```python
PENDING_SECTION_RE = re.compile(r"^#{1,6}\s*(?:[一二三四五六七八九十]+、)?(?:待确认问题|仍需确认的问题)\s*$")
GENERIC_PENDING_PATTERNS = (
    "暂无",
    "当前阶段可继续修改或确认进入下一阶段",
    "请确认是否锁定",
    "并进入下一阶段",
)


def is_generic_pending_question(text: str) -> bool:
    normalized = str(text or "").strip().strip("-* \t")
    if not normalized:
        return True
    if normalized in {"暂无", "无", "没有"}:
        return True
    return any(pattern in normalized for pattern in GENERIC_PENDING_PATTERNS)


def clean_pending_question_line(line: str) -> str:
    cleaned = str(line or "").strip()
    cleaned = re.sub(r"^[-*+\u2022]\s+", "", cleaned)
    cleaned = re.sub(r"^\d+[.)、]\s*", "", cleaned)
    return cleaned.strip()


def extract_pending_questions_from_stage_markdown(text: str) -> list[str]:
    questions: list[str] = []
    in_pending_section = False
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            in_pending_section = bool(PENDING_SECTION_RE.match(stripped))
            continue
        if not in_pending_section:
            continue
        cleaned = clean_pending_question_line(stripped)
        if is_generic_pending_question(cleaned):
            continue
        questions.append(cleaned)
    return dedupe_pending_questions(questions)


def dedupe_pending_questions(questions: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for question in questions:
        cleaned = clean_pending_question_line(question)
        key = re.sub(r"\s+", "", cleaned)
        if not cleaned or key in seen or is_generic_pending_question(cleaned):
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def default_pending_options(question: str, stage: str) -> list[dict[str, str]]:
    accept = "采纳当前建议，并写入当前阶段修订。"
    if "章节规划" in question:
        accept = "采纳当前建议，并在后续章节规划阶段展开。"
    elif "命名" in question or "命名" in question or "预先命名" in question:
        accept = "采纳当前建议，具体命名延后到章节规划或正文写作时决定。"
    elif "已有世界观" in question or "具体来源" in question:
        accept = "采纳当前建议，优先复用已有世界观来源，不新增独立设定。"
    return [
        {"id": "accept", "label": "采纳建议", "answer": accept},
        {"id": "defer", "label": "延后处理", "answer": "暂不锁定细节，延后到后续规划阶段决定。"},
        {"id": "keep", "label": "保持现状", "answer": "保持当前阶段设定，不新增稳定设定。"},
    ]


def collect_stage_pending_questions(store: LocalStore, state: NovelState, stage: str) -> list[str]:
    artifact = state.outline_stage_artifacts.get(stage)
    artifact_dict = dict(artifact) if isinstance(artifact, dict) else {}
    artifact_questions = normalize_pending_source(artifact_dict.get("pending_questions"))
    if artifact_questions:
        return artifact_questions
    state_questions: list[str] = []
    if state.outline_stage == stage:
        state_questions = normalize_pending_source(state.pending_questions)
    if state_questions:
        return state_questions
    markdown = load_stage_markdown(store, state, stage, artifact_dict)
    return extract_pending_questions_from_stage_markdown(markdown)


def normalize_pending_source(value: Any) -> list[str]:
    if isinstance(value, str):
        raw = [value]
    elif isinstance(value, list):
        raw = [str(item) for item in value]
    else:
        raw = []
    return dedupe_pending_questions(raw)


def pending_item_id(stage: str, question: str) -> str:
    return hashlib.sha1(f"{stage}|{question}".encode("utf-8")).hexdigest()[:12]


def outline_stage_pending_payload(store: LocalStore, project_id: str, stage: str) -> dict[str, Any]:
    ensure_valid_stage(stage)
    state = store.load_state(project_id)
    questions = collect_stage_pending_questions(store, state, stage)
    return {
        "project_id": project_id,
        "stage": stage,
        "items": [
            {
                "id": pending_item_id(stage, question),
                "question": question,
                "options": default_pending_options(question, stage),
            }
            for question in questions
        ],
    }
```

Fix the duplicate `elif "命名"` condition while implementing:

```python
elif "命名" in question or "预先命名" in question:
```

- [ ] **Step 4: Run backend extraction tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_extract_stage_pending_questions_from_markdown_filters_status_lines tests/test_web_service.py::test_outline_stage_pending_payload_prefers_artifact_questions tests/test_web_service.py::test_outline_stage_pending_payload_falls_back_to_markdown -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit backend extraction**

```bash
git add src/ai_novelist/web/service.py tests/test_web_service.py
git commit -m "feat: expose outline pending payload"
```

---

### Task 2: Backend Pending Answer Submission

**Files:**
- Modify: `src/ai_novelist/web/service.py`
- Test: `tests/test_web_service.py`

- [ ] **Step 1: Write failing submission tests**

Add these tests to `tests/test_web_service.py`:

```python
def test_submit_stage_pending_answers_builds_revision_instruction(monkeypatch, tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    state = store.create_project("Web Demo", "web-demo")
    state.outline_stage_artifacts["characters"] = {
        "stage": "characters",
        "status": "options_ready",
        "pending_questions": ["林霄视角章是否需提前规划？"],
    }
    store.save_state(state)
    captured = {}

    def fake_run(data: dict, adapter: AgentAdapter, local_store: LocalStore, progress=None) -> dict:
        captured["data"] = dict(data)
        data["outline_stage_artifacts"] = {
            **data.get("outline_stage_artifacts", {}),
            "characters": {
                "stage": "characters",
                "status": "options_ready",
                "pending_questions": [],
            },
        }
        return data

    monkeypatch.setattr(service, "run_outline_stage_node", fake_run)

    result = service.submit_stage_pending_answers(
        store,
        DummyAdapter(),
        "web-demo",
        "characters",
        [
            {
                "question": "林霄视角章是否需提前规划？",
                "selected_option_id": "accept",
                "answer": "采纳当前建议，提前规划1-2个专属视角章。",
            }
        ],
    )

    assert result.outline_stage == "characters"
    assert captured["data"]["director_action"] == "run_outline_stage"
    assert "针对当前阶段待确认项" in captured["data"]["revision_instruction"]
    assert "林霄视角章是否需提前规划？" in captured["data"]["revision_instruction"]
    assert "提前规划1-2个专属视角章" in captured["data"]["revision_instruction"]


def test_submit_stage_pending_answers_rejects_incomplete_answer(tmp_path: Path) -> None:
    store = LocalStore(tmp_path)
    store.create_project("Web Demo", "web-demo")

    with pytest.raises(LocalStoreError, match="每条待确认项都需要选择默认方案或填写自定义答案"):
        service.submit_stage_pending_answers(
            store,
            DummyAdapter(),
            "web-demo",
            "characters",
            [{"question": "问题？", "selected_option_id": "", "answer": ""}],
        )
```

If `pytest` or `LocalStoreError` is not imported at the top of `tests/test_web_service.py`, add:

```python
import pytest
from ai_novelist.storage.local_store import LocalStore, LocalStoreError
```

Do not duplicate existing imports.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_submit_stage_pending_answers_builds_revision_instruction tests/test_web_service.py::test_submit_stage_pending_answers_rejects_incomplete_answer -q
```

Expected: fail with missing `submit_stage_pending_answers`.

- [ ] **Step 3: Implement answer validation and submission**

Add these functions to `src/ai_novelist/web/service.py` near `generate_outline_stage()`:

```python
def normalize_pending_answers(answers: Any) -> list[dict[str, str]]:
    if not isinstance(answers, list) or not answers:
        raise LocalStoreError("请至少提交一条待确认项答案")
    normalized: list[dict[str, str]] = []
    for raw in answers:
        if not isinstance(raw, dict):
            raise LocalStoreError("待确认项答案格式无效")
        question = str(raw.get("question") or "").strip()
        answer = str(raw.get("answer") or raw.get("custom_answer") or "").strip()
        selected_option_id = str(raw.get("selected_option_id") or "").strip()
        if not question or not answer:
            raise LocalStoreError("每条待确认项都需要选择默认方案或填写自定义答案")
        normalized.append(
            {
                "question": question,
                "answer": answer,
                "selected_option_id": selected_option_id,
            }
        )
    return normalized


def build_pending_revision_instruction(answers: list[dict[str, str]]) -> str:
    lines = ["针对当前阶段待确认项，按以下答案修订："]
    for index, item in enumerate(answers, 1):
        lines.append(f"{index}. 问题：{item['question']}")
        lines.append(f"   答案：{item['answer']}")
    return "\n".join(lines)


def submit_stage_pending_answers(
    store: LocalStore,
    adapter: AgentAdapter,
    project_id: str,
    stage: str,
    answers: Any,
    progress: ProgressFunc | None = None,
) -> NovelState:
    ensure_valid_stage(stage)
    normalized = normalize_pending_answers(answers)
    instruction = build_pending_revision_instruction(normalized)
    state = store.load_state(project_id)
    state.outline_stage = stage  # type: ignore[assignment]
    state.outline_stage_status = "collecting"
    state.current_stage = stage
    state.active_workflow = "outline"
    state.user_request = instruction
    state.revision_instruction = instruction
    state.director_action = "run_outline_stage"
    state.director_intent = "answer_pending_questions"
    store.save_state(state)
    result = run_outline_stage_node(state.to_dict(), adapter, store, progress or (lambda _stage, _message: None))
    return NovelState.from_dict(result)
```

- [ ] **Step 4: Run backend submission tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py::test_submit_stage_pending_answers_builds_revision_instruction tests/test_web_service.py::test_submit_stage_pending_answers_rejects_incomplete_answer -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Run full web service tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py -q
```

Expected: all tests in `tests/test_web_service.py` pass.

- [ ] **Step 6: Commit backend submission**

```bash
git add src/ai_novelist/web/service.py tests/test_web_service.py
git commit -m "feat: submit outline pending answers"
```

---

### Task 3: FastAPI Pending Endpoints

**Files:**
- Modify: `src/ai_novelist/web/app.py`
- Modify: `tests/test_web_app.py`

- [ ] **Step 1: Add route registration test**

Add this import near the top of `tests/test_web_app.py`:

```python
from pathlib import Path
```

Add these constants below the imports:

```python
ROOT = Path(__file__).resolve().parents[1]
WEB_APP = ROOT / "src" / "ai_novelist" / "web" / "app.py"
```

Add this test:

```python
def test_pending_outline_routes_are_registered() -> None:
    source = WEB_APP.read_text(encoding="utf-8")

    assert "/api/projects/{project_id}/outline/stages/{stage}/pending" in source
    assert "/api/projects/{project_id}/outline/stages/{stage}/pending/submit" in source
    assert "outline_stage_pending_payload" in source
    assert "submit_stage_pending_answers" in source
```

- [ ] **Step 2: Run the new app test and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_app.py::test_pending_outline_routes_are_registered -q
```

Expected: fail because routes do not exist.

- [ ] **Step 3: Implement routes**

In `src/ai_novelist/web/app.py`, add these route handlers near the existing outline stage generate/lock routes:

```python
    @app.get("/api/projects/{project_id}/outline/stages/{stage}/pending")
    def outline_stage_pending(project_id: str, stage: str):
        try:
            return service.outline_stage_pending_payload(store, project_id, stage)
        except LocalStoreError as exc:
            raise as_http_error(exc)

    @app.post("/api/projects/{project_id}/outline/stages/{stage}/pending/submit")
    def submit_outline_stage_pending(project_id: str, stage: str, payload: dict[str, Any] | None = None):
        payload = payload or {}
        return StreamingResponse(
            sse_events(
                lambda progress: service.submit_stage_pending_answers(
                    store,
                    adapter(payload),
                    project_id,
                    stage,
                    payload.get("answers"),
                    progress,
                ).to_dict()
            ),
            media_type="text/event-stream",
        )
```

- [ ] **Step 4: Run app tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_app.py -q
```

Expected: all app tests pass.

- [ ] **Step 5: Commit API routes**

```bash
git add src/ai_novelist/web/app.py tests/test_web_app.py
git commit -m "feat: add outline pending API routes"
```

---

### Task 4: Frontend Workbench State and UI

**Files:**
- Modify: `web/frontend/src/main.tsx`
- Modify: `web/frontend/src/styles.css`
- Test: `tests/test_frontend_review_tabs_structure.py`

- [ ] **Step 1: Write failing frontend structure test**

Add this test to `tests/test_frontend_review_tabs_structure.py`:

```python
def test_outline_edit_has_pending_confirmation_workbench() -> None:
    source = read_main()

    assert "type PendingQuestionItem" in source
    assert "type PendingPayload" in source
    assert "pendingPayload" in source
    assert "loadPendingQuestions" in source
    assert "submitPendingAnswers" in source
    assert "PendingConfirmationWorkbench" in source
    assert "待确认" in source
    assert "自定义答案" in source
    assert "提交待确认项" in source
    assert "/pending/submit" in source
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py::test_outline_edit_has_pending_confirmation_workbench -q
```

Expected: fail because frontend workbench code does not exist.

- [ ] **Step 3: Add TypeScript types**

In `web/frontend/src/main.tsx`, add after `type Stage`:

```typescript
type PendingOption = {
  id: string;
  label: string;
  answer: string;
};
type PendingQuestionItem = {
  id: string;
  question: string;
  options: PendingOption[];
};
type PendingPayload = {
  project_id: string;
  stage: string;
  items: PendingQuestionItem[];
};
type PendingAnswerDraft = {
  selectedOptionId: string;
  customAnswer: string;
};
```

- [ ] **Step 4: Add state and loaders**

Inside `App()`, add state near existing outline review state:

```typescript
  const [pendingPayload, setPendingPayload] = useState<PendingPayload | null>(null);
  const [pendingAnswers, setPendingAnswers] = useState<Record<string, PendingAnswerDraft>>({});
  const [pendingSubmitting, setPendingSubmitting] = useState(false);
```

Add loader functions near `loadStage`:

```typescript
  async function loadPendingQuestions(stage = activeStage) {
    if (!projectId || !stage) return;
    const payload = await api<PendingPayload>(`/api/projects/${projectId}/outline/stages/${stage}/pending`);
    setPendingPayload(payload);
    setPendingAnswers((currentState) => {
      const next: Record<string, PendingAnswerDraft> = {};
      payload.items.forEach((item) => {
        next[item.id] = currentState[item.id] || { selectedOptionId: '', customAnswer: '' };
      });
      return next;
    });
  }

  function pendingAnswerFor(item: PendingQuestionItem): string {
    const draft = pendingAnswers[item.id];
    if (!draft) return '';
    if (draft.selectedOptionId === 'custom') return draft.customAnswer.trim();
    const option = item.options.find((candidate) => candidate.id === draft.selectedOptionId);
    return option?.answer.trim() || '';
  }

  function allPendingItemsAnswered() {
    const items = pendingPayload?.items || [];
    return items.length > 0 && items.every((item) => pendingAnswerFor(item));
  }

  async function submitPendingAnswers() {
    if (!projectId || !activeStage || !pendingPayload || !allPendingItemsAnswered()) return;
    setPendingSubmitting(true);
    try {
      const answers = pendingPayload.items.map((item) => ({
        id: item.id,
        question: item.question,
        selected_option_id: pendingAnswers[item.id]?.selectedOptionId || '',
        answer: pendingAnswerFor(item),
      }));
      await streamAction(
        `/api/projects/${projectId}/outline/stages/${activeStage}/pending/submit`,
        { answers },
        (line) => pushLog(`pending: ${line}`),
      );
      pushLog('待确认项已提交并完成阶段修订');
      await refreshStages();
      await loadStage(activeStage);
      await loadPendingQuestions(activeStage);
    } catch (error) {
      showError(error);
    } finally {
      setPendingSubmitting(false);
    }
  }
```

- [ ] **Step 5: Wire refresh points**

Update the `useEffect` that loads a stage:

```typescript
  useEffect(() => {
    if (!projectId || !activeStage) return;
    loadStage(activeStage).catch(showError);
    loadPendingQuestions(activeStage).catch(showError);
  }, [projectId, activeStage]);
```

After successful `saveStage()` and `runStage()` flows, call:

```typescript
      await loadPendingQuestions(activeStage);
```

Place it after the existing stage refresh/content reload calls.

- [ ] **Step 6: Add workbench component**

Add this component below `groupRepairSuggestions()` or near other presentational components:

```typescript
function PendingConfirmationWorkbench({
  payload,
  answers,
  submitting,
  onSelect,
  onCustomChange,
  onSubmit,
}: {
  payload: PendingPayload | null;
  answers: Record<string, PendingAnswerDraft>;
  submitting: boolean;
  onSelect: (itemId: string, optionId: string) => void;
  onCustomChange: (itemId: string, value: string) => void;
  onSubmit: () => void;
}) {
  const items = payload?.items || [];
  const isComplete = items.length > 0 && items.every((item) => {
    const draft = answers[item.id];
    if (!draft) return false;
    if (draft.selectedOptionId === 'custom') return draft.customAnswer.trim().length > 0;
    return draft.selectedOptionId.length > 0;
  });
  if (!payload) {
    return <section className="pending-workbench compact">正在读取待确认项...</section>;
  }
  if (items.length === 0) {
    return <section className="pending-workbench compact">暂无待确认项</section>;
  }
  return (
    <section className="pending-workbench">
      <div className="pending-header">
        <div>
          <h2>待确认</h2>
          <p>当前阶段有 {items.length} 项需要处理。选择默认方案，或填写自定义答案后一次性提交。</p>
        </div>
        <button onClick={onSubmit} disabled={!isComplete || submitting}>
          <Check size={16} />{submitting ? '提交中' : '提交待确认项'}
        </button>
      </div>
      <div className="pending-list">
        {items.map((item, index) => {
          const draft = answers[item.id] || { selectedOptionId: '', customAnswer: '' };
          return (
            <article className="pending-item" key={item.id}>
              <h3>{index + 1}. {item.question}</h3>
              <div className="pending-options">
                {item.options.map((option) => (
                  <label className={draft.selectedOptionId === option.id ? 'selected' : ''} key={option.id}>
                    <input
                      type="radio"
                      name={`pending-${item.id}`}
                      checked={draft.selectedOptionId === option.id}
                      onChange={() => onSelect(item.id, option.id)}
                    />
                    <span>{option.label}</span>
                    <small>{option.answer}</small>
                  </label>
                ))}
                <label className={draft.selectedOptionId === 'custom' ? 'selected custom' : 'custom'}>
                  <input
                    type="radio"
                    name={`pending-${item.id}`}
                    checked={draft.selectedOptionId === 'custom'}
                    onChange={() => onSelect(item.id, 'custom')}
                  />
                  <span>自定义答案</span>
                  <input
                    value={draft.customAnswer}
                    onChange={(event) => onCustomChange(item.id, event.target.value)}
                    placeholder="默认方案都不满意时，在这里输入你的答案"
                  />
                </label>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
```

- [ ] **Step 7: Render workbench in outline edit view**

In the `outlineView === 'edit'` block, insert this between `</header>` and the instruction input:

```tsx
              <PendingConfirmationWorkbench
                payload={pendingPayload}
                answers={pendingAnswers}
                submitting={pendingSubmitting}
                onSelect={(itemId, optionId) => setPendingAnswers((currentState) => ({
                  ...currentState,
                  [itemId]: { ...(currentState[itemId] || { selectedOptionId: '', customAnswer: '' }), selectedOptionId: optionId },
                }))}
                onCustomChange={(itemId, value) => setPendingAnswers((currentState) => ({
                  ...currentState,
                  [itemId]: { ...(currentState[itemId] || { selectedOptionId: 'custom', customAnswer: '' }), selectedOptionId: 'custom', customAnswer: value },
                }))}
                onSubmit={submitPendingAnswers}
              />
```

- [ ] **Step 8: Add CSS**

In `web/frontend/src/styles.css`, add:

```css
.pending-workbench {
  border: 1px solid #d7dde8;
  border-radius: 8px;
  background: #f8fafc;
  padding: 14px;
  margin-bottom: 12px;
}

.pending-workbench.compact {
  color: #64748b;
  font-size: 14px;
}

.pending-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.pending-header h2 {
  margin: 0;
  font-size: 16px;
}

.pending-header p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
}

.pending-list {
  display: grid;
  gap: 12px;
  margin-top: 12px;
}

.pending-item {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  padding: 12px;
}

.pending-item h3 {
  margin: 0 0 10px;
  font-size: 14px;
  line-height: 1.5;
}

.pending-options {
  display: grid;
  gap: 8px;
}

.pending-options label {
  display: grid;
  grid-template-columns: auto 96px 1fr;
  gap: 8px;
  align-items: center;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px;
}

.pending-options label.selected {
  border-color: #2563eb;
  background: #eff6ff;
}

.pending-options label.custom {
  grid-template-columns: auto 96px 1fr;
}

.pending-options small {
  color: #475569;
  line-height: 1.4;
}

.pending-options input[type='text'],
.pending-options label.custom input:not([type]) {
  width: 100%;
}
```

If the custom input is affected by the global selector, adjust it to:

```css
.pending-options label.custom input:last-child {
  width: 100%;
}
```

- [ ] **Step 9: Run frontend structure test**

Run:

```bash
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py::test_outline_edit_has_pending_confirmation_workbench -q
```

Expected: pass.

- [ ] **Step 10: Build frontend**

Run:

```bash
npm --prefix web/frontend run build
```

Expected: TypeScript and Vite build pass.

- [ ] **Step 11: Commit frontend workbench**

```bash
git add web/frontend/src/main.tsx web/frontend/src/styles.css tests/test_frontend_review_tabs_structure.py
git commit -m "feat: add outline pending workbench UI"
```

---

### Task 5: Documentation and Integration Verification

**Files:**
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Update implementation documentation**

Add a concise section to `docs/IMPLEMENTATION_PLAN.md` near the Web UI section:

```markdown
### 当前阶段待确认工作台

Web 大纲阶段编辑页新增当前阶段“待确认”工作台。后端通过 `/api/projects/{project_id}/outline/stages/{stage}/pending` 返回当前阶段待确认项，优先读取 artifact/state 中的结构化 `pending_questions`，为空时从当前阶段 Markdown 的“待确认问题 / 仍需确认的问题”小节兜底抽取，并过滤“暂无”和锁定推进类提示。

每个待确认项包含稳定 id、问题文本和确定性的默认方案：采纳建议、延后处理、保持现状。前端允许用户选择默认方案或填写自定义答案，所有项处理完成后通过 `/pending/submit` 一次性提交。提交后端合并为阶段修订 instruction，并复用 `run_outline_stage_node()` 重跑当前阶段，刷新阶段正文和待确认项。
```

- [ ] **Step 2: Update session summary**

Append a new dated entry to `docs/SESSION_SUMMARY.md`:

```markdown
### 当前阶段待确认工作台：已完成

能力：

- Web 大纲阶段编辑页显示当前阶段待确认项，不再要求用户在长 Markdown 中翻找。
- 后端待确认 payload 支持 artifact/state 优先、Markdown 小节兜底，并过滤“暂无”和锁定推进提示。
- 每条待确认项提供“采纳建议 / 延后处理 / 保持现状”默认方案，也支持自定义答案。
- 用户可一次性提交所有待确认项，后端合并为修订说明并复用当前阶段修订路径。

验证：

- `.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_frontend_review_tabs_structure.py`
- `npm --prefix web/frontend run build`
```

- [ ] **Step 3: Run focused backend/frontend tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_app.py tests/test_frontend_review_tabs_structure.py -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Run frontend build**

Run:

```bash
npm --prefix web/frontend run build
```

Expected: build passes.

- [ ] **Step 5: Run full test suite if time permits**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected: full suite passes. If too slow or blocked, record the reason in final notes and `docs/SESSION_SUMMARY.md`.

- [ ] **Step 6: Check git status**

Run:

```bash
git status --short
```

Expected: only intended docs changes are unstaged before commit, plus any pre-existing unrelated user files if they were not part of this task.

- [ ] **Step 7: Commit docs and final verification**

```bash
git add docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "docs: document outline pending workbench"
```

---

## Final Acceptance Criteria

- Current-stage Web pending questions are visible outside the Markdown editor.
- `projects/demo-test` `characters` Markdown-only pending questions are surfaced by the backend fallback.
- Every pending item offers default choices and custom answer entry.
- Batch submit validates all items and reruns the current stage through existing revision behavior.
- Existing stage save/generate/lock flows still work.
- Focused pytest tests and frontend build pass.
- `docs/IMPLEMENTATION_PLAN.md` and `docs/SESSION_SUMMARY.md` are updated in the implementation change set.

