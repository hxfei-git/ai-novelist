import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Check, FileText, Layers, ListChecks, Lock, Play, RefreshCw, Save } from 'lucide-react';
import './styles.css';

type Project = { project_id: string; title: string; path: string };
type Stage = {
  stage: string;
  label: string;
  status: string;
  active: boolean;
  summary: string;
  pending_questions: string[];
  review_lock_issues: { blocking: string[]; detail: string[]; revision_targets: string[] };
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
type TopSection = 'outline' | 'chapters';
type ChapterView = 'batch' | 'list' | 'review';

const emptyIssues = { blocking: [], detail: [], revision_targets: [] };
const outlineReviewCopy = '大纲总体审查';

function stageLabel(stage: Stage | undefined, fallback: string) {
  if (!stage) return fallback;
  return stage.stage === 'review_lock' ? outlineReviewCopy : stage.label;
}

function chapterVersionLabel(chapter: Chapter | null) {
  if (!chapter) return '';
  if (chapter.source === 'final') return '定稿';
  if (chapter.source === 'draft') return `草稿 v${chapter.version ?? 1}`;
  return '旧正文';
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
  const [review, setReview] = useState<any>(null);
  const [reviewRunning, setReviewRunning] = useState(false);

  const stageRequestRef = useRef(0);
  const chapterRequestRef = useRef(0);
  const current = useMemo(() => stages.find((item) => item.stage === activeStage), [stages, activeStage]);
  const currentIssues = current?.review_lock_issues || emptyIssues;

  useEffect(() => {
    refreshProjects().catch(showError);
  }, []);

  useEffect(() => {
    if (!projectId) return;
    refreshStages().catch(showError);
    refreshChapters().catch(showError);
  }, [projectId]);

  useEffect(() => {
    if (!projectId || !activeStage) return;
    loadStage(activeStage).catch(showError);
  }, [projectId, activeStage]);

  useEffect(() => {
    if (!projectId || !selectedChapter) return;
    loadChapter(selectedChapter).catch(showError);
  }, [projectId, selectedChapter]);

  function showError(error: unknown) {
    setLog((items) => [`error: ${error instanceof Error ? error.message : String(error)}`, ...items].slice(0, 10));
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
    setLog((items) => [`saved ${activeStage}`, ...items].slice(0, 10));
  }

  async function runStage(action: 'generate' | 'lock') {
    await streamAction(
      `/api/projects/${projectId}/outline/stages/${activeStage}/${action}`,
      { instruction },
      (line) => setLog((items) => [line, ...items].slice(0, 10)),
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
    await streamAction(
      `/api/projects/${projectId}/chapters/generate-batch`,
      { volume, chapters: chapterSelector, max_workers: maxWorkers },
      (line) => setLog((items) => [line, ...items].slice(0, 10)),
    );
    await refreshChapters(true);
  }

  async function reviewAll() {
    setReviewRunning(true);
    setReview(null);
    setLog((items) => ['章节总体审查已开始', ...items].slice(0, 10));
    try {
      await streamAction(`/api/projects/${projectId}/chapters/review-all`, {}, (line) =>
        setLog((items) => [line, ...items].slice(0, 10)),
      );
      const latest = await api<any>(`/api/projects/${projectId}/chapters/review-all/latest`);
      setReview(latest);
      setLog((items) => [`章节总体审查完成：${latest.summary || '无摘要'}`, ...items].slice(0, 10));
    } finally {
      setReviewRunning(false);
    }
  }

  async function repairProposals() {
    if (!review?.run_id) return;
    const result = await api<any>(`/api/projects/${projectId}/chapters/review-all/${review.run_id}/repair-proposals`, {
      method: 'POST',
      body: JSON.stringify({}),
    });
    setLog((items) => [`repair proposals: ${result.proposals.length}`, ...items].slice(0, 10));
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
            {stages.map((item) => (
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
      </aside>

      {topSection === 'outline' ? (
        <section className="workspace">
          <header className="toolbar">
            <div>
              <h1>{stageLabel(current, activeStage)}</h1>
              <p>{activeStage === 'review_lock' ? '审查并锁定大纲阶段之间的继承、阻塞问题与回改目标' : current?.status || 'not_generated'}</p>
            </div>
            <button onClick={saveStage} disabled={loadingStage}><Save size={16} />保存</button>
            <button onClick={() => runStage('generate')} disabled={loadingStage}><RefreshCw size={16} />生成/修订</button>
            <button onClick={() => runStage('lock')} disabled={loadingStage}><Lock size={16} />锁定</button>
          </header>
          <input className="instruction" value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="当前大纲阶段生成/修订说明" />
          {loadingStage ? <div className="loading">正在读取 {stageLabel(current, activeStage)}...</div> : <textarea className="editor" value={content} onChange={(event) => setContent(event.target.value)} />}
          {activeStage === 'review_lock' && (
            <div className="issues-grid">
              <IssueBlock title="阻塞问题" items={currentIssues.blocking} />
              <IssueBlock title="非阻塞问题" items={currentIssues.detail} />
              <IssueBlock title="需回改阶段" items={currentIssues.revision_targets} />
            </div>
          )}
        </section>
      ) : (
        <section className="workspace chapter-workspace">
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
              <header className="toolbar"><div><h1>章节总体审查</h1><p>审查已生成章节之间的连续性、设定一致性、人物状态、时间线、重复/断裂问题</p></div></header>
              <div className="review-actions">
                <button onClick={reviewAll} disabled={reviewRunning}><Check size={16} />{reviewRunning ? '审查中' : '开始审查'}</button>
                <button onClick={repairProposals} disabled={reviewRunning || !review?.run_id}><RefreshCw size={16} />生成修复草稿</button>
              </div>
              {reviewRunning && <div className="loading">章节总体审查正在运行...</div>}
              {review && <ReviewReport review={review} />}
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

function IssueBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="issues">
      <strong>{title}</strong>
      {items.length === 0 ? <p>暂无</p> : items.map((item) => <p key={item}>{item}</p>)}
    </section>
  );
}

function ReviewReport({ review }: { review: any }) {
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

createRoot(document.getElementById('root')!).render(<App />);
