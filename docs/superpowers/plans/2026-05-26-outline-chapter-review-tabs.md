# Outline and Chapter Review Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move outline and chapter global review surfaces into consistent workspace-level secondary tabs while preserving existing review APIs and explicit apply behavior.

**Architecture:** This is primarily a frontend information-architecture change. The backend is audited first to confirm the existing outline/chapter review endpoints support the new layout; implementation then refactors `web/frontend/src/main.tsx` state/rendering and `web/frontend/src/styles.css` styling, with static structure tests guarding against putting review actions back into stage/sidebar locations.

**Tech Stack:** Python 3.12, pytest, FastAPI service layer, React 18, TypeScript, Vite, lucide-react.

---

## File Structure

- `src/ai_novelist/web/service.py`: audit only unless an endpoint gap is found. Existing outline/chapter review functions should already support loading latest reports, running review, and explicit apply.
- `src/ai_novelist/web/app.py`: audit only unless route coverage is incomplete. Current routes should already expose the needed API.
- `web/frontend/src/main.tsx`: add `OutlineView`, move outline review UI from stage toolbar into `outlineView === 'review'`, move chapter view buttons from sidebar into workspace secondary tabs.
- `web/frontend/src/styles.css`: add/reuse secondary tab styling and keep the existing dense tool UI style.
- `tests/test_web_service.py`: no new tests expected if audit confirms current API coverage; keep existing regression tests running.
- `tests/test_frontend_review_tabs_structure.py`: create a static source test that fails on the current UI and passes when review is no longer in the wrong nav/toolbar locations.
- `docs/IMPLEMENTATION_PLAN.md`: update Web UI documentation to describe workspace secondary tabs and backend API audit outcome.
- `docs/SESSION_SUMMARY.md`: record implementation notes, validation commands, and any remaining limitations.

---

### Task 1: Backend API Audit

**Files:**
- Inspect: `src/ai_novelist/web/service.py`
- Inspect: `src/ai_novelist/web/app.py`
- Inspect: `tests/test_web_service.py`

- [ ] **Step 1: Confirm outline review service coverage**

Read the service functions and verify these behaviors exist:

```bash
rg -n "def latest_outline_review_report|def review_outline\(|def apply_outline_review\(" src/ai_novelist/web/service.py
```

Expected: all three functions are present.

- [ ] **Step 2: Confirm outline review route coverage**

```bash
rg -n "outline/review/latest|outline/review\"|outline/review/\{run_id\}/apply" src/ai_novelist/web/app.py
```

Expected: `GET latest`, `POST review`, and `POST apply` routes are present.

- [ ] **Step 3: Confirm chapter review service and route coverage**

```bash
rg -n "def latest_global_review|def review_all_chapters|def apply_repair" src/ai_novelist/web/service.py
rg -n "review-all/latest|review-all\"|apply-repair" src/ai_novelist/web/app.py
```

Expected: latest chapter review, run chapter review, and apply repair capabilities are present.

- [ ] **Step 4: Run current backend API regression tests**

```bash
.venv/bin/python -m pytest tests/test_web_service.py -q
```

Expected: PASS. If this fails, fix the backend regression before moving to UI work.

- [ ] **Step 5: Record audit decision**

If Steps 1-4 pass, do not add backend API. Add this exact conclusion to the implementation notes later:

```text
Backend API audit result: existing outline review and chapter review endpoints support the tabbed UI. No new backend endpoint was added.
```

If a gap is found, stop and update this plan before implementing code.

- [ ] **Step 6: Commit is not needed**

This task is inspection only. Do not commit unless you changed code to fix a regression.

---

### Task 2: Add Failing Frontend Structure Test

**Files:**
- Create: `tests/test_frontend_review_tabs_structure.py`

- [ ] **Step 1: Create the test file**

Create `tests/test_frontend_review_tabs_structure.py` with this complete content:

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN_TSX = ROOT / "web" / "frontend" / "src" / "main.tsx"


def read_main() -> str:
    return MAIN_TSX.read_text(encoding="utf-8")


def sidebar_source(source: str) -> str:
    start = source.index('<aside className="sidebar">')
    end = source.index('{topSection ===', start)
    return source[start:end]


def test_review_entries_are_not_sidebar_navigation() -> None:
    sidebar = sidebar_source(read_main())

    assert "章节批量生成" not in sidebar
    assert "已生成章节" not in sidebar
    assert "章节总体审查" not in sidebar
    assert "大纲总体审查" not in sidebar
    assert "总体审查" not in sidebar


def test_outline_workspace_uses_secondary_review_tab() -> None:
    source = read_main()

    assert "type OutlineView = 'edit' | 'review';" in source
    assert 'aria-label="大纲视图"' in source
    assert "outlineView === 'edit'" in source
    assert "outlineView === 'review'" in source
    assert "setOutlineView('edit')" in source
    assert "setOutlineView('review')" in source

    edit_start = source.index("{outlineView === 'edit' &&")
    review_start = source.index("{outlineView === 'review' &&")
    edit_block = source[edit_start:review_start]

    assert "runOutlineReview" not in edit_block
    assert "大纲总体审查" not in edit_block


def test_chapter_workspace_uses_secondary_tabs() -> None:
    source = read_main()

    assert 'aria-label="章节视图"' in source
    assert "chapterView === 'batch'" in source
    assert "chapterView === 'list'" in source
    assert "chapterView === 'review'" in source
    assert "setChapterView('batch')" in source
    assert "setChapterView('list')" in source
    assert "setChapterView('review')" in source

    sidebar = sidebar_source(source)
    assert "setChapterView('batch')" not in sidebar
    assert "setChapterView('list')" not in sidebar
    assert "setChapterView('review')" not in sidebar
```

- [ ] **Step 2: Run the new test and verify it fails**

```bash
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py -q
```

Expected: FAIL. The current implementation still has chapter review nav buttons in the sidebar and outline review action in the outline stage workspace.

- [ ] **Step 3: Commit the failing test**

```bash
git add tests/test_frontend_review_tabs_structure.py
git commit -m "test: cover review tab navigation structure"
```

---

### Task 3: Refactor Frontend View State and Sidebar

**Files:**
- Modify: `web/frontend/src/main.tsx`

- [ ] **Step 1: Add `OutlineView` type**

Near the existing `TopSection` and `ChapterView` type aliases, change this block:

```ts
type TopSection = 'outline' | 'chapters';
type ChapterView = 'batch' | 'list' | 'review';
```

To this exact block:

```ts
type TopSection = 'outline' | 'chapters';
type OutlineView = 'edit' | 'review';
type ChapterView = 'batch' | 'list' | 'review';
```

- [ ] **Step 2: Add `outlineView` state**

Find the state declarations in `App()` that include `topSection` and `chapterView`. Make them use this exact shape:

```ts
const [topSection, setTopSection] = useState<TopSection>('outline');
const [outlineView, setOutlineView] = useState<OutlineView>('edit');
const [chapterView, setChapterView] = useState<ChapterView>('batch');
```

Keep the existing `chapterView` state variable name so the chapter logic continues to work.

- [ ] **Step 3: Update top-level tab handlers without resetting secondary state**

In the sidebar `.top-tabs`, keep the top-level buttons but use block handlers that only set the top section:

```tsx
<div className="top-tabs">
  <button className={topSection === 'outline' ? 'active' : ''} onClick={() => setTopSection('outline')}>
    <Layers size={16} />大纲
  </button>
  <button className={topSection === 'chapters' ? 'active' : ''} onClick={() => setTopSection('chapters')}>
    <FileText size={16} />章节
  </button>
</div>
```

Do not reset `outlineView`, `chapterView`, `activeStage`, or selected chapter in these handlers.

- [ ] **Step 4: Remove chapter workflow buttons from sidebar**

Replace the current sidebar conditional nav block:

```tsx
{topSection === 'outline' ? (
  <nav>
    {visibleStages.map((item) => (
      <button className={item.stage === activeStage ? 'active' : ''} key={item.stage} onClick={() => setActiveStage(item.stage)}>
        <FileText size={16} />
        <span>{stageLabel(item, item.stage)}</span>
        <small>{item.status}</small>
      </button>
    ))}
  </nav>
) : (
  <nav>
    <button className={chapterView === 'batch' ? 'active' : ''} onClick={() => setChapterView('batch')}><Play size={16} /><span>章节批量生成</span></button>
    <button className={chapterView === 'list' ? 'active' : ''} onClick={() => setChapterView('list')}><FileText size={16} /><span>已生成章节</span><small>{chapters.length}</small></button>
    <button className={chapterView === 'review' ? 'active' : ''} onClick={() => setChapterView('review')}><ListChecks size={16} /><span>章节总体审查</span></button>
  </nav>
)}
```

With this exact block:

```tsx
{topSection === 'outline' ? (
  <nav>
    {visibleStages.map((item) => (
      <button className={item.stage === activeStage ? 'active' : ''} key={item.stage} onClick={() => setActiveStage(item.stage)}>
        <FileText size={16} />
        <span>{stageLabel(item, item.stage)}</span>
        <small>{item.status}</small>
      </button>
    ))}
  </nav>
) : (
  <nav className="sidebar-note">
    <p>章节功能在右侧工作区切换。</p>
  </nav>
)}
```

- [ ] **Step 5: Run the static test and verify partial progress**

```bash
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py -q
```

Expected: still FAIL because the outline workspace has not yet been refactored, but the sidebar-specific assertions should now pass.

- [ ] **Step 6: Commit state/sidebar refactor**

```bash
git add web/frontend/src/main.tsx tests/test_frontend_review_tabs_structure.py
git commit -m "refactor: move chapter workflow nav out of sidebar"
```

---

### Task 4: Move Outline Review Into Workspace Secondary Tab

**Files:**
- Modify: `web/frontend/src/main.tsx`

- [ ] **Step 1: Add outline secondary tabs above outline content**

Replace the current outline workspace render:

```tsx
{topSection === 'outline' ? (
  <section className="workspace">
    <header className="toolbar">
      <div>
        <h1>{stageLabel(current, activeStage)}</h1>
        <p>{current?.status || 'not_generated'}</p>
      </div>
      <button onClick={saveStage} disabled={loadingStage}><Save size={16} />保存</button>
      <button onClick={() => runStage('generate')} disabled={loadingStage}><RefreshCw size={16} />生成/修订</button>
      <button onClick={() => runStage('lock')} disabled={loadingStage}><Lock size={16} />锁定</button>
      <button onClick={runOutlineReview} disabled={loadingStage || outlineReviewRunning}><ListChecks size={16} />{outlineReviewRunning ? '审查中' : '总体审查'}</button>
    </header>
    <input className="instruction" value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="当前大纲阶段生成/修订说明" />
    {loadingStage ? <div className="loading">正在读取 {stageLabel(current, activeStage)}...</div> : <textarea className="editor" value={content} onChange={(event) => setContent(event.target.value)} />}
    <OutlineReviewPanel review={outlineReview} running={outlineReviewRunning} applying={outlineReviewApplying} onApply={applyOutlineReview} onDismiss={dismissOutlineReview} />
  </section>
) : (
```

With this exact block:

```tsx
{topSection === 'outline' ? (
  <section className="workspace">
    <div className="workspace-tabs" aria-label="大纲视图">
      <button className={outlineView === 'edit' ? 'active' : ''} onClick={() => setOutlineView('edit')}>
        <FileText size={16} />阶段编辑
      </button>
      <button className={outlineView === 'review' ? 'active' : ''} onClick={() => setOutlineView('review')}>
        <ListChecks size={16} />总体审查
      </button>
    </div>

    {outlineView === 'edit' && (
      <>
        <header className="toolbar">
          <div>
            <h1>{stageLabel(current, activeStage)}</h1>
            <p>{current?.status || 'not_generated'}</p>
          </div>
          <button onClick={saveStage} disabled={loadingStage}><Save size={16} />保存</button>
          <button onClick={() => runStage('generate')} disabled={loadingStage}><RefreshCw size={16} />生成/修订</button>
          <button onClick={() => runStage('lock')} disabled={loadingStage}><Lock size={16} />锁定</button>
        </header>
        <input className="instruction" value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="当前大纲阶段生成/修订说明" />
        {loadingStage ? <div className="loading">正在读取 {stageLabel(current, activeStage)}...</div> : <textarea className="editor" value={content} onChange={(event) => setContent(event.target.value)} />}
      </>
    )}

    {outlineView === 'review' && (
      <OutlineReviewWorkspace
        instruction={instruction}
        setInstruction={setInstruction}
        review={outlineReview}
        running={outlineReviewRunning}
        applying={outlineReviewApplying}
        onRun={runOutlineReview}
        onApply={applyOutlineReview}
        onDismiss={dismissOutlineReview}
      />
    )}
  </section>
) : (
```

- [ ] **Step 2: Replace `OutlineReviewPanel` with workspace component**

Replace the existing component that starts with `function OutlineReviewPanel({` and ends at its matching closing brace with this complete component:

```tsx
function OutlineReviewWorkspace({
  instruction,
  setInstruction,
  review,
  running,
  applying,
  onRun,
  onApply,
  onDismiss,
}: {
  instruction: string;
  setInstruction: (value: string) => void;
  review: OutlineReview | null;
  running: boolean;
  applying: boolean;
  onRun: () => void;
  onApply: () => void;
  onDismiss: () => void;
}) {
  const hasReview = Boolean(review);
  return (
    <section className="review-workspace outline-review-workspace">
      <header className="toolbar">
        <div>
          <h1>大纲总体审查</h1>
          <p>审查当前已有的大纲阶段产物</p>
        </div>
        <button onClick={onRun} disabled={running}><ListChecks size={16} />{running ? '审查中' : '开始审查'}</button>
      </header>
      <input
        className="instruction"
        value={instruction}
        onChange={(event) => setInstruction(event.target.value)}
        placeholder="可选：本次审查关注点"
      />
      {running && <div className="loading">大纲总体审查正在运行...</div>}
      {hasReview ? (
        <section className="outline-review-panel">
          <header className="review-header">
            <div>
              <strong>最近一次大纲总体审查</strong>
              <p>{review?.status || 'reviewed'} · {review?.decision || 'revise'} · {review?.score ?? 0}</p>
            </div>
            <div className="review-buttons">
              <button onClick={onDismiss} disabled={running || applying}><X size={16} />不采纳</button>
              <button onClick={onApply} disabled={running || applying || review?.decision === 'stop'}><Check size={16} />采纳修改</button>
            </div>
          </header>
          <div className="review-report outline-review-report">
            <span>run_id: {review?.run_id}</span>
            <strong>{review?.summary}</strong>
            <p>{review?.notes}</p>
            <small>参考大纲：{review?.source_outline_summary}</small>
          </div>
        </section>
      ) : (
        <div className="review-report outline-review-report empty-review">
          <p>暂无大纲审查结果。点击“开始审查”生成审查意见。</p>
        </div>
      )}
      {applying && <div className="loading">大纲审查建议正在应用...</div>}
    </section>
  );
}
```

- [ ] **Step 3: Run the static test**

```bash
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py -q
```

Expected: still FAIL until Task 5 adds the chapter workspace tabs; the outline-specific assertions should pass.

- [ ] **Step 4: Run TypeScript build**

```bash
npm --prefix web/frontend run build
```

Expected: PASS. Fix any TypeScript errors before committing.

- [ ] **Step 5: Commit outline review tab refactor**

```bash
git add web/frontend/src/main.tsx tests/test_frontend_review_tabs_structure.py
git commit -m "refactor: move outline review into workspace tab"
```

---

### Task 5: Move Chapter Views Into Workspace Secondary Tabs

**Files:**
- Modify: `web/frontend/src/main.tsx`

- [ ] **Step 1: Add chapter secondary tabs at top of chapter workspace**

Inside `<section className="workspace chapter-workspace">`, before the `{chapterView === 'batch' && (` block, insert this exact tab block:

```tsx
<div className="workspace-tabs" aria-label="章节视图">
  <button className={chapterView === 'batch' ? 'active' : ''} onClick={() => setChapterView('batch')}>
    <Play size={16} />批量生成
  </button>
  <button className={chapterView === 'list' ? 'active' : ''} onClick={() => setChapterView('list')}>
    <FileText size={16} />已生成章节
    <small>{chapters.length}</small>
  </button>
  <button className={chapterView === 'review' ? 'active' : ''} onClick={() => setChapterView('review')}>
    <ListChecks size={16} />总体审查
  </button>
</div>
```

- [ ] **Step 2: Keep existing chapter bodies unchanged**

Do not change the bodies of the existing `chapterView === 'batch'`, `chapterView === 'list'`, and `chapterView === 'review'` conditional blocks except indentation. This preserves chapter generation, chapter detail loading, review report display, selected repair IDs, and apply repair behavior.

- [ ] **Step 3: Run static frontend test**

```bash
.venv/bin/python -m pytest tests/test_frontend_review_tabs_structure.py -q
```

Expected: PASS.

- [ ] **Step 4: Run frontend build**

```bash
npm --prefix web/frontend run build
```

Expected: PASS.

- [ ] **Step 5: Commit chapter tabs refactor**

```bash
git add web/frontend/src/main.tsx tests/test_frontend_review_tabs_structure.py
git commit -m "refactor: move chapter tools into workspace tabs"
```

---

### Task 6: Style Secondary Tabs

**Files:**
- Modify: `web/frontend/src/styles.css`

- [ ] **Step 1: Add workspace tab styles**

Append or merge this complete CSS block into `web/frontend/src/styles.css`:

```css
.workspace-tabs {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px;
  margin-bottom: 12px;
  border: 1px solid #d7dce5;
  border-radius: 8px;
  background: #f4f6f9;
}

.workspace-tabs button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid transparent;
  border-radius: 6px;
  color: #4b5563;
  background: transparent;
  font-size: 14px;
  line-height: 1;
}

.workspace-tabs button.active {
  color: #111827;
  border-color: #c7ceda;
  background: #fff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
}

.workspace-tabs button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.workspace-tabs small {
  display: inline-flex;
  min-width: 20px;
  height: 20px;
  align-items: center;
  justify-content: center;
  padding: 0 6px;
  border-radius: 999px;
  color: #475569;
  background: #e2e8f0;
  font-size: 12px;
}

.sidebar-note {
  padding: 10px 12px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.5;
}

.sidebar-note p {
  margin: 0;
}

.review-workspace {
  display: flex;
  min-height: 0;
  flex-direction: column;
}
```

- [ ] **Step 2: Check existing class conflicts**

Run:

```bash
rg -n "workspace-tabs|sidebar-note|review-workspace" web/frontend/src/styles.css web/frontend/src/main.tsx
```

Expected: the class names appear only in the new intended places. If an existing class conflicts, rename the new classes to `subview-tabs`, `sidebar-context-note`, and `review-subview`, then update both CSS and TSX consistently.

- [ ] **Step 3: Run frontend build**

```bash
npm --prefix web/frontend run build
```

Expected: PASS.

- [ ] **Step 4: Commit styles**

```bash
git add web/frontend/src/styles.css web/frontend/src/main.tsx
git commit -m "style: add workspace secondary tabs"
```

---

### Task 7: Documentation Updates

**Files:**
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Update implementation plan documentation**

In `docs/IMPLEMENTATION_PLAN.md`, update the Web UI section that describes outline/chapter navigation. Replace any statement saying outline review is in the stage toolbar with text equivalent to:

```markdown
Web UI 的大纲与章节区采用统一的工作区二级标签：大纲区为 `阶段编辑 / 总体审查`，章节区为 `批量生成 / 已生成章节 / 总体审查`。大纲阶段页工具栏只保留阶段级操作 `保存 / 生成/修订 / 锁定`；大纲总体审查在独立二级标签中运行，可在任意阶段审查当前已有的大纲阶段产物。章节总体审查也从左侧导航迁移到章节工作区二级标签，继续复用 `/chapters/review-all` 流程。

后端 API 审计结果：现有 `/outline/review/latest`、`/outline/review`、`/outline/review/{run_id}/apply`、`/chapters/review-all/latest`、`/chapters/review-all` 和 `/chapters/{chapter}/apply-repair` 已覆盖新 UI 所需的读取、审查和显式应用能力，本次不新增后端接口。
```

- [ ] **Step 2: Update session summary**

In `docs/SESSION_SUMMARY.md`, add a dated note near the latest Web UI section:

```markdown
### 2026-05-26 大纲/章节审查二级标签

- 大纲区新增 `阶段编辑 / 总体审查` 二级标签；总体审查不再出现在方向定位、世界观设定等阶段页工具栏中。
- 章节区改为 `批量生成 / 已生成章节 / 总体审查` 二级标签；左侧不再把章节功能作为导航项堆叠展示。
- 已审计后端 API，现有大纲审查与章节审查接口可以支撑新布局，因此未新增后端接口。
- 验证：`npm --prefix web/frontend run build` 和目标 pytest 套件通过。
```

- [ ] **Step 3: Commit docs**

```bash
git add docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "docs: document review tab navigation"
```

---

### Task 8: Final Verification

**Files:**
- Verify: all modified files

- [ ] **Step 1: Run backend regression suite**

```bash
.venv/bin/python -m pytest tests/test_web_service.py tests/test_outline_collaboration.py tests/test_director_service.py tests/test_outline_stage_controls.py tests/test_frontend_review_tabs_structure.py
```

Expected: PASS.

- [ ] **Step 2: Run frontend build**

```bash
npm --prefix web/frontend run build
```

Expected: PASS.

- [ ] **Step 3: Check whitespace and status**

```bash
git diff --check
git status --short
```

Expected: no whitespace errors. `git status --short` may show untracked `.superpowers/`, `chat.log`, or `web-service.log`; do not add those unless the user explicitly asks.

- [ ] **Step 4: Final commit if needed**

If Task 8 created any fixes, commit them:

```bash
git add web/frontend/src/main.tsx web/frontend/src/styles.css tests/test_frontend_review_tabs_structure.py docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "fix: complete review tab navigation verification"
```

If no files changed, no commit is needed.

- [ ] **Step 5: Report completion**

Final response must include:

```text
Implemented the workspace secondary-tab navigation for outline and chapter review.
Backend API audit found no new endpoint was needed.
Verified with:
- .venv/bin/python -m pytest tests/test_web_service.py tests/test_outline_collaboration.py tests/test_director_service.py tests/test_outline_stage_controls.py tests/test_frontend_review_tabs_structure.py
- npm --prefix web/frontend run build
```
