import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Check, FileText, Lock, Play, RefreshCw, Save } from 'lucide-react';
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

const emptyIssues = { blocking: [], detail: [], revision_targets: [] };

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function streamAction(path: string, body: unknown, onProgress: (line: string) => void): Promise<void> {
  const res = await fetch(path, {
    method: 'POST',
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
      const dataLine = event.split('\n').find((line) => line.startsWith('data: '));
      if (!dataLine) continue;
      onProgress(dataLine.slice(6));
    }
  }
}

function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState('');
  const [title, setTitle] = useState('demo-web');
  const [stages, setStages] = useState<Stage[]>([]);
  const [activeStage, setActiveStage] = useState('direction');
  const [content, setContent] = useState('');
  const [instruction, setInstruction] = useState('');
  const [log, setLog] = useState<string[]>([]);
  const [chapterSelector, setChapterSelector] = useState('1-3');
  const [volume, setVolume] = useState(1);
  const [maxWorkers, setMaxWorkers] = useState(3);
  const [review, setReview] = useState<any>(null);

  const current = useMemo(() => stages.find((item) => item.stage === activeStage), [stages, activeStage]);

  useEffect(() => {
    refreshProjects();
  }, []);

  useEffect(() => {
    if (projectId) refreshStages();
  }, [projectId]);

  useEffect(() => {
    if (projectId && activeStage) loadStage(activeStage);
  }, [projectId, activeStage]);

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
    const item = await api<Stage>(`/api/projects/${projectId}/outline/stages/${stage}`);
    setContent(item.content || '');
    setStages((prev) => prev.map((old) => (old.stage === stage ? item : old)));
  }

  async function saveStage() {
    await api<Stage>(`/api/projects/${projectId}/outline/stages/${activeStage}`, {
      method: 'PUT',
      body: JSON.stringify({ content }),
    });
    await refreshStages();
    setLog((items) => [`saved ${activeStage}`, ...items].slice(0, 8));
  }

  async function runStage(action: 'generate' | 'lock') {
    await streamAction(
      `/api/projects/${projectId}/outline/stages/${activeStage}/${action}`,
      { instruction, mock: true },
      (line) => setLog((items) => [line, ...items].slice(0, 8)),
    );
    await refreshStages();
    await loadStage(activeStage);
  }

  async function generateBatch() {
    await streamAction(
      `/api/projects/${projectId}/chapters/generate-batch`,
      { volume, chapters: chapterSelector, max_workers: maxWorkers, mock: true },
      (line) => setLog((items) => [line, ...items].slice(0, 8)),
    );
  }

  async function reviewAll() {
    await streamAction(`/api/projects/${projectId}/chapters/review-all`, { mock: true }, (line) =>
      setLog((items) => [line, ...items].slice(0, 8)),
    );
    const latest = await api<any>(`/api/projects/${projectId}/chapters/review-all/latest`);
    setReview(latest);
  }

  async function repairProposals() {
    if (!review?.run_id) return;
    const result = await api<any>(`/api/projects/${projectId}/chapters/review-all/${review.run_id}/repair-proposals`, {
      method: 'POST',
      body: JSON.stringify({ mock: true }),
    });
    setLog((items) => [`repair proposals: ${result.proposals.length}`, ...items].slice(0, 8));
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
        <nav>
          {stages.map((item) => (
            <button className={item.stage === activeStage ? 'active' : ''} key={item.stage} onClick={() => setActiveStage(item.stage)}>
              <FileText size={16} />
              <span>{item.label}</span>
              <small>{item.status}</small>
            </button>
          ))}
        </nav>
      </aside>
      <section className="workspace">
        <header className="toolbar">
          <div>
            <h1>{current?.label || activeStage}</h1>
            <p>{current?.status || 'not_generated'}</p>
          </div>
          <button onClick={saveStage}><Save size={16} />保存</button>
          <button onClick={() => runStage('generate')}><RefreshCw size={16} />生成/修订</button>
          <button onClick={() => runStage('lock')}><Lock size={16} />锁定</button>
        </header>
        <input className="instruction" value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="当前阶段生成/修订说明" />
        <textarea className="editor" value={content} onChange={(event) => setContent(event.target.value)} />
        {(current?.review_lock_issues || emptyIssues).blocking.length > 0 && (
          <div className="issues">
            <strong>阻塞问题</strong>
            {(current?.review_lock_issues.blocking || []).map((item) => <p key={item}>{item}</p>)}
          </div>
        )}
      </section>
      <aside className="right">
        <section>
          <h2>章节批量</h2>
          <label>卷号<input type="number" min={1} value={volume} onChange={(e) => setVolume(Number(e.target.value))} /></label>
          <label>章节<input value={chapterSelector} onChange={(e) => setChapterSelector(e.target.value)} /></label>
          <label>并发<input type="number" min={1} max={8} value={maxWorkers} onChange={(e) => setMaxWorkers(Number(e.target.value))} /></label>
          <button onClick={generateBatch}><Play size={16} />生成批次</button>
        </section>
        <section>
          <h2>全章节审查</h2>
          <button onClick={reviewAll}><Check size={16} />审查</button>
          <button onClick={repairProposals}><RefreshCw size={16} />修复草稿</button>
          {review && <p>{review.summary}</p>}
        </section>
        <section>
          <h2>进度</h2>
          {log.map((item, index) => <pre key={`${index}-${item}`}>{item}</pre>)}
        </section>
      </aside>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<App />);

