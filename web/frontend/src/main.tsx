import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Check, FileText, Layers, ListChecks, Lock, Play, RefreshCw, Save, X } from 'lucide-react';
import './styles.css';

type Project = { project_id: string; title: string; path: string };
type Stage = {
  stage: string;
  label: string;
  status: string;
  active: boolean;
  summary: string;
  pending_questions: string[];
  review_lock_issues?: { blocking: string[]; detail: string[]; revision_targets: string[] };
  content?: string;
};
type Chapter = {
  chapter: number;
  title: string;
  path: string;
  source: string;
  version: number | null;
  updated_at: string;
  summary: string;
  content?: string;
};
type ReviewIssue = {
  severity: string;
  chapter: number | null;
  category?: string;
  message: string;
};
type ReviewSuggestion = {
  id: string;
  chapter: number | null;
  severity: string;
  category: string;
  message: string;
  recommendation: string;
  selected: boolean;
};
type ReviewReportData = {
  project_id: string;
  run_id: string;
  status: string;
  summary: string;
  issues: ReviewIssue[];
  repair_suggestions?: ReviewSuggestion[];
};
type OutlineReview = {
  project_id: string;
  run_id: string;
  created_at: string;
  status: string;
  decision: string;
  score: number;
  summary: string;
  notes: string;
  revision_instruction: string;
  source_outline_summary: string;
  source_outline: string;
};
type TopSection = 'outline' | 'chapters';
type OutlineView = 'edit' | 'review';
type ChapterView = 'batch' | 'list' | 'review';

const maxLogItems = 10;

function progressLogKey(projectId: string) {
  return `ai-novelist:${projectId}:progress-log`;
}

function readProgressLog(projectId: string) {
  if (!projectId) return [];
  try {
    const raw = window.localStorage.getItem(progressLogKey(projectId));
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item === 'string').slice(0, maxLogItems) : [];
  } catch {
    return [];
  }
}

function writeProgressLog(projectId: string, items: string[]) {
  if (!projectId) return;
  window.localStorage.setItem(progressLogKey(projectId), JSON.stringify(items.slice(0, maxLogItems)));
}

function stageLabel(stage: Stage | undefined, fallback: string) {
  if (!stage) return fallback;
  return stage.label || fallback;
}

function chapterVersionLabel(chapter: Chapter | null) {
  if (!chapter) return '';
  if (chapter.source === 'final') return '定稿';
  if (chapter.source === 'draft') return `草稿 v${chapter.version ?? 1}`;
  return '旧正文';
}

function buildRepairSelectionMap(suggestions: ReviewSuggestion[]) {
  const next: Record<string, boolean> = {};
  suggestions.forEach((item) => {
    next[item.id] = item.selected !== false;
  });
  return next;
}

function groupRepairSuggestions(suggestions: ReviewSuggestion[]) {
  const groups = new Map<number | null, ReviewSuggestion[]>();
  suggestions.forEach((item) => {
    const key = item.chapter;
    const items = groups.get(key) || [];
    items.push(item);
    groups.set(key, items);
  });
  return [...groups.entries()]
    .sort((left, right) => {
      if (left[0] === null && right[0] === null) return 0;
      if (left[0] === null) return 1;
      if (right[0] === null) return -1;
      return left[0] - right[0];
    })
    .map(([chapter, items]) => ({ chapter, items }));
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function streamAction(path: string, body: unknown, onProgress: (line: string) => void): Promise<void> {
  const res = await fetch(path, {
    method: 'POST',
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) throw new Error(await res.text());
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split('\n\n');
    buffer = events.pop() || '';
    for (const event of events) {
      const lines = event.split('\n');
      const eventLine = lines.find((line) => line.startsWith('event: '));
      const dataLine = lines.find((line) => line.startsWith('data: '));
      if (!dataLine) continue;
      const data = dataLine.slice(6);
      if (eventLine?.slice(7) === 'error') {
        try {
          const parsed = JSON.parse(data);
          throw new Error(parsed.error || data);
        } catch (error) {
          if (error instanceof Error && error.message !== data) throw error;
          throw new Error(data);
        }
      }
      onProgress(data);
    }
  }
}

function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState('');
  const [title, setTitle] = useState('demo-web');
  const [topSection, setTopSection] = useState<TopSection>('outline');
  const [outlineView, setOutlineView] = useState<OutlineView>('edit');
  const [chapterView, setChapterView] = useState<ChapterView>('batch');
  const [stages, setStages] = useState<Stage[]>([]);
  const [activeStage, setActiveStage] = useState('direction');
  const [content, setContent] = useState('');
  const [instruction, setInstruction] = useState('');
  const [loadingStage, setLoadingStage] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const [chapterSelector, setChapterSelector] = useState('1-3');
  const [volume, setVolume] = useState(1);
  const [maxWorkers, setMaxWorkers] = useState(3);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [selectedChapter, setSelectedChapter] = useState<number | null>(null);
  const [chapterDetail, setChapterDetail] = useState<Chapter | null>(null);
  const [loadingChapter, setLoadingChapter] = useState(false);
  const [review, setReview] = useState<ReviewReportData | null>(null);
  const [reviewRunning, setReviewRunning] = useState(false);
  const [selectedRepairIds, setSelectedRepairIds] = useState<Record<string, boolean>>({});
  const [applyingChapter, setApplyingChapter] = useState<number | null>(null);
  const [outlineReview, setOutlineReview] = useState<OutlineReview | null>(null);
  const [outlineReviewRunning, setOutlineReviewRunning] = useState(false);
  const [outlineReviewApplying, setOutlineReviewApplying] = useState(false);

  const stageRequestRef = useRef(0);
  const chapterRequestRef = useRef(0);
  const current = useMemo(() => stages.find((item) => item.stage === activeStage), [stages, activeStage]);
  const visibleStages = useMemo(() => stages.filter((item) => item.stage !== 'review_lock'), [stages]);

  useEffect(() => {
    refreshProjects().catch(showError);
  }, []);

  useEffect(() => {
    if (!projectId) return;
    setLog(readProgressLog(projectId));
    refreshStages().catch(showError);
    refreshChapters().catch(showError);
    loadLatestReview().catch(() => setReview(null));
    loadLatestOutlineReview().catch(() => setOutlineReview(null));
  }, [projectId]);

  useEffect(() => {
    if (!projectId || !activeStage) return;
    loadStage(activeStage).catch(showError);
  }, [projectId, activeStage]);

  useEffect(() => {
    if (!projectId || !selectedChapter) return;
    loadChapter(selectedChapter).catch(showError);
  }, [projectId, selectedChapter]);

  function pushLog(message: string) {
    setLog((items) => {
      const next = [message, ...items].slice(0, maxLogItems);
      writeProgressLog(projectId, next);
      return next;
    });
  }

  function showError(error: unknown) {
    pushLog(`error: ${error instanceof Error ? error.message : String(error)}`);
  }

  async function refreshProjects() {
    const items = await api<Project[]>('/api/projects');
    setProjects(items);
    if (!projectId && items[0]) setProjectId(items[0].project_id);
  }

  async function createProject() {
    const state = await api<any>('/api/projects', { method: 'POST', body: JSON.stringify({ title, project_id: title }) });
    setProjectId(state.project_id);
    await refreshProjects();
  }

  async function refreshStages() {
    const items = await api<Stage[]>(`/api/projects/${projectId}/outline/stages`);
    setStages(items);
    if (items.length > 0 && !items.find((item) => item.stage === activeStage)) {
      const firstVisible = items.find((item) => item.stage !== 'review_lock');
      if (firstVisible) setActiveStage(firstVisible.stage);
    }
  }

  async function loadStage(stage: string) {
    const token = ++stageRequestRef.current;
    setLoadingStage(true);
    setContent('');
    const item = await api<Stage>(`/api/projects/${projectId}/outline/stages/${stage}`);
    if (token !== stageRequestRef.current || stage !== activeStage) return;
    setContent(item.content || '');
    setStages((prev) => prev.map((old) => (old.stage === stage ? item : old)));
    setLoadingStage(false);
  }

  async function saveStage() {
    const saved = await api<Stage>(`/api/projects/${projectId}/outline/stages/${activeStage}`, {
      method: 'PUT',
      body: JSON.stringify({ content }),
    });
    setStages((items) => items.map((item) => (item.stage === activeStage ? saved : item)));
    pushLog(`saved ${activeStage}`);
  }

  async function runStage(action: 'generate' | 'lock') {
    await streamAction(
      `/api/projects/${projectId}/outline/stages/${activeStage}/${action}`,
      { instruction },
      (line) => pushLog(line),
    );
    await refreshStages();
    await loadStage(activeStage);
  }

  async function refreshChapters(selectLatest = false) {
    const items = await api<Chapter[]>(`/api/projects/${projectId}/chapters`);
    setChapters(items);
    if (selectLatest && items.length > 0) {
      setSelectedChapter(items[items.length - 1].chapter);
      setChapterView('list');
    } else if (!selectedChapter && items.length > 0) {
      setSelectedChapter(items[0].chapter);
    }
  }

  async function loadChapter(chapter: number) {
    const token = ++chapterRequestRef.current;
    setLoadingChapter(true);
    setChapterDetail(null);
    const item = await api<Chapter>(`/api/projects/${projectId}/chapters/${chapter}`);
    if (token !== chapterRequestRef.current || chapter !== selectedChapter) return;
    setChapterDetail(item);
    setLoadingChapter(false);
  }

  async function generateBatch() {
    pushLog(`章节批量生成已开始：第 ${volume} 卷 ${chapterSelector}`);
    await streamAction(
      `/api/projects/${projectId}/chapters/generate-batch`,
      { volume, chapters: chapterSelector, max_workers: maxWorkers },
      (line) => pushLog(line),
    );
    await refreshChapters(true);
    pushLog('章节批量生成完成，已刷新章节列表');
  }

  async function loadLatestReview() {
    const latest = await api<ReviewReportData>(`/api/projects/${projectId}/chapters/review-all/latest`);
    setReview(latest);
    setSelectedRepairIds(buildRepairSelectionMap(latest.repair_suggestions || []));
  }

  async function loadLatestOutlineReview() {
    const latest = await api<OutlineReview>(`/api/projects/${projectId}/outline/review/latest`);
    setOutlineReview(latest);
  }

  async function runOutlineReview() {
    setOutlineReviewRunning(true);
    pushLog('大纲总体审查已开始');
    try {
      await streamAction(`/api/projects/${projectId}/outline/review`, { instruction: instruction.trim() }, (line) => pushLog(line));
      await loadLatestOutlineReview();
      pushLog('大纲总体审查完成');
    } catch (error) {
      showError(error);
    } finally {
      setOutlineReviewRunning(false);
    }
  }

  async function applyOutlineReview() {
    if (!outlineReview?.run_id) return;
    setOutlineReviewApplying(true);
    pushLog(`大纲审查应用已开始：${outlineReview.run_id}`);
    try {
      await streamAction(`/api/projects/${projectId}/outline/review/${outlineReview.run_id}/apply`, {}, (line) => pushLog(line));
      await loadLatestOutlineReview();
      pushLog('大纲审查建议已应用');
    } catch (error) {
      showError(error);
    } finally {
      setOutlineReviewApplying(false);
    }
  }

  function dismissOutlineReview() {
    if (!outlineReview) return;
    pushLog(`已拒绝采纳大纲审查建议：${outlineReview.run_id}`);
    setOutlineReview((currentReview) => (currentReview ? { ...currentReview, status: 'dismissed' } : currentReview));
  }

  async function reviewAll() {
    setReviewRunning(true);
    setReview(null);
    setSelectedRepairIds({});
    pushLog('章节总体审查已开始');
    try {
      await streamAction(`/api/projects/${projectId}/chapters/review-all`, {}, (line) => pushLog(line));
      const latest = await api<ReviewReportData>(`/api/projects/${projectId}/chapters/review-all/latest`);
      setReview(latest);
      setSelectedRepairIds(buildRepairSelectionMap(latest.repair_suggestions || []));
      pushLog(`章节总体审查完成：${latest.summary || '无摘要'}`);
    } finally {
      setReviewRunning(false);
    }
  }

  async function applyRepair(chapter: number) {
    if (!review?.run_id) return;
    const suggestions = (review.repair_suggestions || []).filter((item) => item.chapter === chapter);
    const selectedIssueIds = suggestions.filter((item) => selectedRepairIds[item.id] !== false).map((item) => item.id);
    if (selectedIssueIds.length === 0) {
      pushLog(`第 ${chapter} 章没有选中的修改建议`);
      return;
    }
    setApplyingChapter(chapter);
    try {
      const result = await api<{ path: string; version: number }>(`/api/projects/${projectId}/chapters/${chapter}/apply-repair`, {
        method: 'POST',
        body: JSON.stringify({ run_id: review.run_id, selected_issue_ids: selectedIssueIds }),
      });
      pushLog(`已提交第 ${chapter} 章修改：draft_v${result.version}`);
      await refreshChapters();
      if (selectedChapter === chapter) await loadChapter(chapter);
    } catch (error) {
      showError(error);
    } finally {
      setApplyingChapter(null);
    }
  }

  return (
    <main className="app">
      <aside className="sidebar">
        <div className="brand">AI Novelist</div>
        <div className="project-create">
          <input value={title} onChange={(event) => setTitle(event.target.value)} />
          <button onClick={createProject}><Save size={16} />新建</button>
        </div>
        <select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
          <option value="">选择项目</option>
          {projects.map((item) => <option key={item.project_id} value={item.project_id}>{item.title}</option>)}
        </select>
        <div className="top-tabs">
          <button className={topSection === 'outline' ? 'active' : ''} onClick={() => setTopSection('outline')}><Layers size={16} />大纲</button>
          <button className={topSection === 'chapters' ? 'active' : ''} onClick={() => setTopSection('chapters')}><FileText size={16} />章节</button>
        </div>
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
      </aside>

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
              review={outlineReview}
              instruction={instruction}
              running={outlineReviewRunning}
              applying={outlineReviewApplying}
              onInstructionChange={setInstruction}
              onRun={runOutlineReview}
              onApply={applyOutlineReview}
              onDismiss={dismissOutlineReview}
            />
          )}
        </section>
      ) : (
        <section className="workspace chapter-workspace">
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
          {chapterView === 'batch' && (
            <>
              <header className="toolbar"><div><h1>章节批量生成</h1><p>按卷号、章节范围和并发数生成章节正文</p></div></header>
              <div className="form-grid">
                <label>卷号<input type="number" min={1} value={volume} onChange={(e) => setVolume(Number(e.target.value))} /></label>
                <label>章节范围<input value={chapterSelector} onChange={(e) => setChapterSelector(e.target.value)} /></label>
                <label>并发数<input type="number" min={1} max={8} value={maxWorkers} onChange={(e) => setMaxWorkers(Number(e.target.value))} /></label>
                <button onClick={generateBatch}><Play size={16} />生成章节</button>
              </div>
            </>
          )}
          {chapterView === 'list' && (
            <>
              <header className="toolbar"><div><h1>已生成章节</h1><p>读取最新正文：final.md 优先，其次最高 draft_vN.md，再回退旧路径</p></div><button onClick={() => refreshChapters()}><RefreshCw size={16} />刷新</button></header>
              <div className="chapter-layout">
                <div className="chapter-list">
                  {chapters.map((item) => (
                    <button className={item.chapter === selectedChapter ? 'active' : ''} key={item.chapter} onClick={() => setSelectedChapter(item.chapter)}>
                      <span>{item.title}</span>
                      <small>第 {item.chapter} 章 · {chapterVersionLabel(item)}</small>
                    </button>
                  ))}
                  {chapters.length === 0 && <p className="empty">暂无已生成章节。</p>}
                </div>
                <article className="chapter-detail">
                  {loadingChapter && <div className="loading">正在读取章节...</div>}
                  {!loadingChapter && chapterDetail && (
                    <>
                      <div className="chapter-meta">
                        <strong>{chapterDetail.title}</strong>
                        <span>{chapterVersionLabel(chapterDetail)} · {chapterDetail.path}</span>
                      </div>
                      <pre className="chapter-body">{chapterDetail.content}</pre>
                    </>
                  )}
                </article>
              </div>
            </>
          )}
          {chapterView === 'review' && (
            <>
              <header className="toolbar"><div><h1>章节总体审查</h1><p>审查结果会直接显示默认勾选的修改建议，按章提交即可</p></div></header>
              <div className="review-actions">
                <button onClick={reviewAll} disabled={reviewRunning}><Check size={16} />{reviewRunning ? '审查中' : '开始审查'}</button>
              </div>
              {reviewRunning && <div className="loading">章节总体审查正在运行...</div>}
              {review && <ReviewReport review={review} />}
              {review && (review.repair_suggestions || []).length > 0 && (
                <RepairSuggestionBoard
                  review={review}
                  selectedRepairIds={selectedRepairIds}
                  onToggle={(id, checked) => setSelectedRepairIds((currentState) => ({ ...currentState, [id]: checked }))}
                  onSubmit={applyRepair}
                  submittingChapter={applyingChapter}
                />
              )}
            </>
          )}
        </section>
      )}

      <aside className="right">
        <section>
          <h2>进度</h2>
          {log.length === 0 && <p className="empty">暂无进度。</p>}
          {log.map((item, index) => <pre key={`${index}-${item}`}>{item}</pre>)}
        </section>
      </aside>
    </main>
  );
}


function OutlineReviewWorkspace({
  review,
  instruction,
  running,
  applying,
  onInstructionChange,
  onRun,
  onApply,
  onDismiss,
}: {
  review: OutlineReview | null;
  instruction: string;
  running: boolean;
  applying: boolean;
  onInstructionChange: (value: string) => void;
  onRun: () => void;
  onApply: () => void;
  onDismiss: () => void;
}) {
  const hasReview = Boolean(review);
  return (
    <section className="review-workspace outline-review-panel">
      <header className="toolbar">
        <div>
          <h1>大纲总体审查</h1>
          <p>审查当前已有的大纲阶段产物</p>
        </div>
        <button onClick={onRun} disabled={running || applying}><ListChecks size={16} />{running ? '审查中' : '开始审查'}</button>
      </header>
      <input className="instruction" value={instruction} onChange={(event) => onInstructionChange(event.target.value)} placeholder="可选：本次审查关注点" />
      {running && <div className="loading">大纲总体审查正在运行...</div>}
      {hasReview ? (
        <div className="review-report outline-review-report">
          <div className="review-header">
            <div>
              <span>run_id: {review?.run_id}</span>
              <strong>{review?.summary}</strong>
              <small>{review?.status || 'reviewed'} · {review?.decision || 'revise'} · {review?.score ?? 0}</small>
            </div>
            <div className="review-buttons">
              <button onClick={onDismiss} disabled={running || applying}><X size={16} />不采纳</button>
              <button onClick={onApply} disabled={running || applying || review?.decision === 'stop'}><Check size={16} />采纳修改</button>
            </div>
          </div>
          <p>{review?.notes}</p>
          <small>参考大纲：{review?.source_outline_summary}</small>
        </div>
      ) : (
        <div className="review-report outline-review-report empty-review">
          <p>点击“开始审查”生成大纲审查意见。</p>
        </div>
      )}
      {applying && <div className="loading">大纲审查建议正在应用...</div>}
    </section>
  );
}

function IssueBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="issues">
      <strong>{title}</strong>
      {items.length === 0 ? <p>暂无</p> : items.map((item) => <p key={item}>{item}</p>)}
    </section>
  );
}

function ReviewReport({ review }: { review: ReviewReportData }) {
  const issues = Array.isArray(review.issues) ? review.issues : [];
  return (
    <div className="review-report">
      <strong>{review.summary}</strong>
      <span>run_id: {review.run_id}</span>
      {issues.map((item: any, index: number) => (
        <p key={`${index}-${item.message}`}>[{item.severity}] {item.chapter ? `第 ${item.chapter} 章` : '全局'} {item.message}</p>
      ))}
    </div>
  );
}

function RepairSuggestionBoard({
  review,
  selectedRepairIds,
  onToggle,
  onSubmit,
  submittingChapter,
}: {
  review: ReviewReportData;
  selectedRepairIds: Record<string, boolean>;
  onToggle: (id: string, checked: boolean) => void;
  onSubmit: (chapter: number) => void;
  submittingChapter: number | null;
}) {
  const groups = groupRepairSuggestions(review.repair_suggestions || []);
  return (
    <div className="review-report repair-proposals">
      <strong>修改建议</strong>
      {groups.map((group) => {
        const chapter = typeof group.chapter === 'number' ? group.chapter : null;
        const label = chapter ? `第 ${chapter} 章` : '全局问题';
        const submitChapter = chapter === null ? undefined : () => onSubmit(chapter);
        return (
          <section className="repair-chapter" key={group.chapter ?? 'global'}>
            <div className="repair-chapter-head">
              <div>
                <strong>{label}</strong>
                <small>{group.items.length} 条建议，默认全选</small>
              </div>
              {chapter !== null && (
                <button onClick={submitChapter} disabled={submittingChapter === chapter}>
                  <Check size={16} />{submittingChapter === chapter ? '提交中' : '提交修改'}
                </button>
              )}
            </div>
            <div className="repair-suggestion-list">
              {group.items.map((item) => (
                <label className="repair-suggestion" key={item.id}>
                  <input
                    type="checkbox"
                    checked={selectedRepairIds[item.id] ?? item.selected !== false}
                    onChange={(event) => onToggle(item.id, event.target.checked)}
                  />
                  <div>
                    <strong>{item.recommendation}</strong>
                    <p>[{item.severity}] {item.message}</p>
                  </div>
                </label>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
