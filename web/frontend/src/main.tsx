import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Check, FileText, Layers, ListChecks, Lock, Play, RefreshCw, Save, X } from 'lucide-react';
import './styles.css';

type Project = { project_id: string; title: string; path: string };
type ProjectState = {
  project_id: string;
  title: string;
  idea: string;
  outline: string;
  worldbuilding: string;
  chapter_plan: string;
  outline_stage_summaries: Record<string, string>;
  outline_stage_artifacts: Record<string, { status?: string; summary?: string }>;
};
type ActionState = {
  can_generate: boolean;
  can_revise: boolean;
  can_lock: boolean;
  lock_reason: string;
};
type Stage = {
  stage: string;
  label: string;
  status: string;
  active: boolean;
  summary: string;
  pending_questions: string[];
  review_lock_issues?: { blocking: string[]; detail: string[]; revision_targets: string[] };
  content?: string;
  action_state?: ActionState;
};
type PendingOption = {
  id: string;
  label: string;
  answer: string;
  requires_input?: boolean;
};
type PendingQuestion = {
  id: string;
  question: string;
  options: PendingOption[];
};
type PendingQuestionPayload = {
  project_id: string;
  stage: string;
  items: PendingQuestion[];
};
type ChapterOutlineVolumeSpec = {
  index: number;
  label: string;
  name: string;
  summary?: string;
};
type ChapterOutlineSelectedVolume = {
  index: number;
  label: string;
  name: string;
  status: string;
  summary: string;
  content: string;
} & ActionState;
type ChapterOutlineWorkspace = {
  volume_specs: ChapterOutlineVolumeSpec[];
  current_volume_index: number;
  completed_volumes: number[];
  volume_statuses: Record<string, string>;
  selected_volume: ChapterOutlineSelectedVolume;
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
type ChapterBatchWorkspace = {
  volume_index: number;
  volume_label: string;
  volume_name: string;
  total_chapters: number;
  generated_chapters: number;
  remaining_chapters: number;
  next_chapter_number: number | null;
  planned_chapter_numbers: number[];
  remaining_chapter_numbers: number[];
  chapters: Chapter[];
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
  repair_suggestions?: OutlineReviewSuggestion[];
};
type OutlineReviewSuggestion = {
  id: string;
  severity: string;
  category: string;
  message: string;
  recommendation: string;
  selected: boolean;
};
type OutlineRepairDecisionValue = 'recommended' | 'skip' | 'custom';
type OutlineRepairDecision = {
  decision: OutlineRepairDecisionValue;
  custom_answer: string;
};
type ProgressEvent = {
  key?: string;
  label: string;
  elapsed: string;
  tokens: string;
  context: string;
  status: string;
};
type ProgressItem = string | ProgressEvent;
type TopSection = 'outline' | 'chapter-outline' | 'chapters';
type OutlineStageView = 'edit' | 'review';
type ChapterView = 'batch' | 'list' | 'review';

const maxLogItems = 10;
const disabledActionState: ActionState = {
  can_generate: false,
  can_revise: false,
  can_lock: false,
  lock_reason: '',
};

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

function buildOutlineRepairSelectionMap(suggestions: OutlineReviewSuggestion[]) {
  const next: Record<string, boolean> = {};
  suggestions.forEach((item) => {
    next[item.id] = item.selected !== false;
  });
  return next;
}

function buildOutlineRepairDecisionMap(suggestions: OutlineReviewSuggestion[]) {
  const next: Record<string, OutlineRepairDecision> = {};
  suggestions.forEach((item) => {
    next[item.id] = { decision: item.selected === false ? 'skip' : 'recommended', custom_answer: '' };
  });
  return next;
}

function buildPendingAnswerSelection(items: PendingQuestion[]) {
  const next: Record<string, string> = {};
  items.forEach((item) => {
    next[item.id] = item.options[0]?.id || '';
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

function progressItemKey(item: ProgressItem) {
  if (typeof item === 'string') return item;
  return item.key || item.label;
}

function upsertProgressItem(items: ProgressItem[], message: ProgressItem) {
  const key = progressItemKey(message);
  if (!key) return [...items, message].slice(-maxLogItems);
  const next = items.filter((item) => progressItemKey(item) !== key);
  return [...next, message].slice(-maxLogItems);
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

async function streamAction(path: string, body: unknown, onProgress: (event: ProgressEvent) => void): Promise<unknown> {
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
  let donePayload: unknown;
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
      if (eventLine?.slice(7) === 'done') {
        donePayload = JSON.parse(data);
        continue;
      }
      if (eventLine?.slice(7) !== 'progress') continue;
      onProgress(JSON.parse(data) as ProgressEvent);
    }
  }
  return donePayload;
}

function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState('');
  const [title, setTitle] = useState('demo-web');
  const [topSection, setTopSection] = useState<TopSection>('outline');
  const [outlineStageView, setOutlineStageView] = useState<OutlineStageView>('edit');
  const [chapterView, setChapterView] = useState<ChapterView>('batch');
  const [stages, setStages] = useState<Stage[]>([]);
  const [projectState, setProjectState] = useState<ProjectState | null>(null);
  const [onboardingIdea, setOnboardingIdea] = useState('');
  const [activeStage, setActiveStage] = useState('direction');
  const [content, setContent] = useState('');
  const [instruction, setInstruction] = useState('');
  const [loadingStage, setLoadingStage] = useState(false);
  const [stageRunning, setStageRunning] = useState(false);
  const [chapterOutlineWorkspace, setChapterOutlineWorkspace] = useState<ChapterOutlineWorkspace | null>(null);
  const [loadingChapterOutline, setLoadingChapterOutline] = useState(false);
  const [chapterOutlineRunning, setChapterOutlineRunning] = useState(false);
  const [chapterOutlineView, setChapterOutlineView] = useState<'volume' | 'review'>('volume');
  const [log, setLog] = useState<ProgressItem[]>([]);
  const [volume, setVolume] = useState(1);
  const [requestedChapterCount, setRequestedChapterCount] = useState(3);
  const [chapterBatchWorkspace, setChapterBatchWorkspace] = useState<ChapterBatchWorkspace | null>(null);
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
  const [outlineRepairDecisions, setOutlineRepairDecisions] = useState<Record<string, OutlineRepairDecision>>({});
  const [chapterOutlineReview, setChapterOutlineReview] = useState<OutlineReview | null>(null);
  const [chapterOutlineReviewRunning, setChapterOutlineReviewRunning] = useState(false);
  const [chapterOutlineReviewApplying, setChapterOutlineReviewApplying] = useState(false);
  const [selectedChapterOutlineRepairIds, setSelectedChapterOutlineRepairIds] = useState<Record<string, boolean>>({});
  const [pendingQuestions, setPendingQuestions] = useState<PendingQuestionPayload | null>(null);
  const [pendingAnswerSelection, setPendingAnswerSelection] = useState<Record<string, string>>({});
  const [pendingCustomAnswers, setPendingCustomAnswers] = useState<Record<string, string>>({});
  const [pendingSubmitting, setPendingSubmitting] = useState(false);

  const stageRequestRef = useRef(0);
  const stageRunningRef = useRef(false);
  const chapterRequestRef = useRef(0);
  const current = useMemo(() => stages.find((item) => item.stage === activeStage), [stages, activeStage]);
  const currentActionState = current?.action_state || disabledActionState;
  const currentStageLocked = current?.status === 'locked';
  const visibleStages = useMemo(() => stages.filter((item) => item.stage !== 'review_lock' && item.stage !== 'chapter_outline'), [stages]);
  const needsOnboarding = useMemo(() => {
    if (!projectState) return false;
    if (projectState.idea.trim() || projectState.outline.trim() || projectState.worldbuilding.trim() || projectState.chapter_plan.trim()) return false;
    if (Object.values(projectState.outline_stage_summaries || {}).some((value) => value.trim())) return false;
    return Object.values(projectState.outline_stage_artifacts || {}).every((artifact) => {
      const status = (artifact?.status || '').trim();
      const summary = (artifact?.summary || '').trim();
      return !status && !summary;
    });
  }, [projectState]);

  useEffect(() => {
    refreshProjects().catch(showError);
  }, []);

  useEffect(() => {
    if (!projectId) return;
    setProjectState(null);
    setOnboardingIdea('');
    setLog([]);
    setStages([]);
    setContent('');
    setInstruction('');
    setPendingQuestions(null);
    setPendingAnswerSelection({});
    setPendingCustomAnswers({});
    setChapterOutlineWorkspace(null);
    setChapterBatchWorkspace(null);
    setChapters([]);
    setChapterDetail(null);
    setReview(null);
    setOutlineReview(null);
    setChapterOutlineReview(null);
    setSelectedRepairIds({});
    setOutlineRepairDecisions({});
    setSelectedChapterOutlineRepairIds({});
    setOutlineStageView('edit');
    setChapterOutlineView('volume');
    setChapterView('batch');
    loadProjectState().catch(showError);
    loadProjectProgressLog().catch(showError);
    refreshStages().catch(showError);
    refreshChapters(false, 1).catch(showError);
    loadLatestReview().catch(() => setReview(null));
    loadLatestOutlineReview().catch(() => setOutlineReview(null));
    loadLatestChapterOutlineReview().catch(() => setChapterOutlineReview(null));
    loadChapterOutlineWorkspace().catch(showError);
  }, [projectId]);

  useEffect(() => {
    if (!projectId || !activeStage) return;
    loadStage(activeStage).catch(showError);
  }, [projectId, activeStage]);

  useEffect(() => {
    if (!projectId || !selectedChapter) return;
    loadChapter(selectedChapter).catch(showError);
  }, [projectId, selectedChapter]);

  function pushLog(message: ProgressItem) {
    setLog((items) => {
      const next = upsertProgressItem(items, message);
      void saveProjectProgressLog(next);
      return next;
    });
  }

  function showError(error: unknown) {
    pushLog(`error: ${error instanceof Error ? error.message : String(error)}`);
  }

  async function loadProjectState() {
    const state = await api<ProjectState>(`/api/projects/${projectId}/state`);
    setProjectState(state);
    setOnboardingIdea(state.idea || '');
  }

  async function loadProjectProgressLog() {
    const payload = await api<{ items: ProgressItem[] }>(`/api/projects/${projectId}/progress-log`);
    setLog(Array.isArray(payload.items) ? payload.items : []);
  }

  async function saveProjectProgressLog(items: ProgressItem[]) {
    if (!projectId) return;
    await api<{ items: ProgressItem[] }>(`/api/projects/${projectId}/progress-log`, {
      method: 'PUT',
      body: JSON.stringify({ items }),
    });
  }

  async function refreshProjects() {
    const items = await api<Project[]>('/api/projects');
    setProjects(items);
    if (!projectId && items[0]) setProjectId(items[0].project_id);
  }

  async function createProject() {
    const state = await api<ProjectState>('/api/projects', { method: 'POST', body: JSON.stringify({ title, project_id: title }) });
    setProjectId(state.project_id);
    setProjectState(state);
    setOnboardingIdea(state.idea || '');
    setLog([]);
    await saveProjectProgressLog([]);
    await refreshProjects();
  }

  async function refreshStages() {
    const items = await api<Stage[]>(`/api/projects/${projectId}/outline/stages`);
    setStages(items);
    if (items.length > 0 && !items.find((item) => item.stage === activeStage)) {
      const firstVisible = items.find((item) => item.stage !== 'review_lock' && item.stage !== 'chapter_outline');
      if (firstVisible) setActiveStage(firstVisible.stage);
    }
  }

  async function loadStage(stage: string) {
    const token = ++stageRequestRef.current;
    setLoadingStage(true);
    setContent('');
    setPendingQuestions(null);
    setPendingAnswerSelection({});
    setPendingCustomAnswers({});
    try {
      const [item, pending] = await Promise.all([
        api<Stage>(`/api/projects/${projectId}/outline/stages/${stage}`),
        api<PendingQuestionPayload>(`/api/projects/${projectId}/outline/stages/${stage}/pending`),
      ]);
      if (token !== stageRequestRef.current || stage !== activeStage) return;
      setContent(item.content || '');
      setStages((prev) => prev.map((old) => (old.stage === stage ? item : old)));
      setPendingQuestions(pending);
      setPendingAnswerSelection(buildPendingAnswerSelection(pending.items || []));
    } finally {
      if (token === stageRequestRef.current && stage === activeStage) setLoadingStage(false);
    }
  }

  async function saveStage() {
    const saved = await api<Stage>(`/api/projects/${projectId}/outline/stages/${activeStage}`, {
      method: 'PUT',
      body: JSON.stringify({ content }),
    });
    setStages((items) => items.map((item) => (item.stage === activeStage ? saved : item)));
    pushLog(`saved ${activeStage}`);
  }

  async function submitOnboardingIdea() {
    if (!projectId || !onboardingIdea.trim()) return;
    const state = await api<ProjectState>(`/api/projects/${projectId}/idea`, {
      method: 'POST',
      body: JSON.stringify({ idea: onboardingIdea }),
    });
    setProjectState(state);
    setOnboardingIdea(state.idea || onboardingIdea.trim());
    setInstruction(onboardingIdea.trim());
    pushLog('已保存小说创意');
  }

  async function runStage(action: 'generate' | 'revise' | 'lock') {
    if (stageRunningRef.current) return;
    stageRunningRef.current = true;
    setStageRunning(true);
    try {
      await streamAction(
        `/api/projects/${projectId}/outline/stages/${activeStage}/${action}`,
        { instruction },
        (line) => pushLog(line),
      );
      setInstruction('');
      await refreshStages();
      await loadStage(activeStage);
    } finally {
      stageRunningRef.current = false;
      setStageRunning(false);
    }
  }

  async function loadChapterOutlineWorkspace(selectedVolumeIndex?: number) {
    if (!projectId) return;
    setLoadingChapterOutline(true);
    const query = selectedVolumeIndex ? `?selected_volume_index=${selectedVolumeIndex}` : '';
    try {
      const payload = await api<ChapterOutlineWorkspace>(`/api/projects/${projectId}/outline/chapter-workspace${query}`);
      setChapterOutlineWorkspace(payload);
    } finally {
      setLoadingChapterOutline(false);
    }
  }

  async function runChapterOutlineVolume(action: 'generate' | 'revise' | 'lock') {
    if (!chapterOutlineWorkspace || chapterOutlineRunning) return;
    const volumeIndex = chapterOutlineWorkspace.selected_volume.index;
    setChapterOutlineRunning(true);
    try {
      await streamAction(
        `/api/projects/${projectId}/outline/chapter-workspace/volumes/${volumeIndex}/${action}`,
        { instruction },
        (line) => pushLog(line),
      );
      await loadChapterOutlineWorkspace(action === 'lock' ? undefined : volumeIndex);
    } finally {
      setChapterOutlineRunning(false);
    }
  }

  async function refreshChapters(selectLatest = false, volumeIndex?: number) {
    let items: Chapter[] = [];
    if (volumeIndex) {
      const payload = await api<ChapterBatchWorkspace>(`/api/projects/${projectId}/chapters/workspace?volume=${volumeIndex}`);
      setChapterBatchWorkspace(payload);
      items = payload.chapters || [];
    } else {
      items = await api<Chapter[]>(`/api/projects/${projectId}/chapters`);
    }
    setChapters(items);
    if (selectLatest && items.length > 0) {
      setSelectedChapter(items[items.length - 1].chapter);
      setChapterView('list');
    } else if (items.length > 0) {
      setSelectedChapter(items[0].chapter);
    } else {
      setSelectedChapter(null);
      setChapterDetail(null);
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
    const remainingChapters = chapterBatchWorkspace?.remaining_chapters ?? 0;
    const requestedCount = Math.max(1, Number(requestedChapterCount) || 1);
    const actualCount = Math.min(requestedCount, remainingChapters);
    if (actualCount < 1) return;
    pushLog({ label: '章节批量生成', elapsed: '', tokens: '', context: '', status: 'started' });
    await streamAction(
      `/api/projects/${projectId}/chapters/generate-batch`,
      { volume, requested_count: actualCount },
      (line) => pushLog(line),
    );
    await refreshChapters(true, volume);
    pushLog({ label: '章节批量生成', elapsed: '', tokens: '', context: '', status: 'completed' });
  }

  async function loadLatestReview() {
    const latest = await api<ReviewReportData>(`/api/projects/${projectId}/chapters/review-all/latest`);
    setReview(latest);
    setSelectedRepairIds(buildRepairSelectionMap(latest.repair_suggestions || []));
  }

  async function loadLatestOutlineReview() {
    const latest = await api<OutlineReview>(`/api/projects/${projectId}/outline/review/latest`);
    setOutlineReview(latest);
    setOutlineRepairDecisions(buildOutlineRepairDecisionMap(latest.repair_suggestions || []));
  }

  async function loadLatestChapterOutlineReview() {
    const latest = await api<OutlineReview>(`/api/projects/${projectId}/outline/chapter-review/latest`);
    setChapterOutlineReview(latest);
    setSelectedChapterOutlineRepairIds(buildOutlineRepairSelectionMap(latest.repair_suggestions || []));
  }

  async function runOutlineReview() {
    setOutlineReviewRunning(true);
    pushLog({ label: '大纲总体审查', elapsed: '', tokens: '', context: '', status: 'started' });
    try {
      await streamAction(`/api/projects/${projectId}/outline/review`, { instruction: instruction.trim() }, (line) => pushLog(line));
      await loadLatestOutlineReview();
      pushLog({ label: '大纲总体审查', elapsed: '', tokens: '', context: '', status: 'completed' });
    } catch (error) {
      showError(error);
    } finally {
      setOutlineReviewRunning(false);
    }
  }

  async function applyOutlineReview() {
    if (!outlineReview?.run_id) return;
    const suggestions = outlineReview.repair_suggestions || [];
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
    setOutlineReviewApplying(true);
    pushLog({ label: '大纲审查应用', elapsed: '', tokens: '', context: '', status: 'started' });
    try {
      const applyResult = await streamAction(
        `/api/projects/${projectId}/outline/review/${outlineReview.run_id}/apply`,
        { decisions },
        (line) => pushLog(line),
      );
      await loadLatestOutlineReview();
      await loadProjectState();
      await refreshStages();
      const updatedStages = Array.isArray((applyResult as { updated_stages?: unknown })?.updated_stages)
        ? (applyResult as { updated_stages: unknown[] }).updated_stages.filter((stage): stage is string => typeof stage === 'string')
        : [];
      const targetStage = updatedStages.find((stage) => visibleStages.some((item) => item.stage === stage)) || activeStage;
      setTopSection('outline');
      setActiveStage(targetStage);
      setOutlineStageView('edit');
      if (targetStage === activeStage) await loadStage(targetStage);
      pushLog({ label: '大纲审查应用', elapsed: '', tokens: '', context: '', status: 'completed' });
    } catch (error) {
      showError(error);
    } finally {
      setOutlineReviewApplying(false);
    }
  }

  function dismissOutlineReview() {
    if (!outlineReview) return;
    pushLog({ label: '大纲审查建议', elapsed: '', tokens: '', context: '', status: 'dismissed' });
    setOutlineReview((currentReview) => (currentReview ? { ...currentReview, status: 'dismissed' } : currentReview));
  }

  async function runChapterOutlineReview() {
    setChapterOutlineReviewRunning(true);
    pushLog({ label: '章节大纲总体审查', elapsed: '', tokens: '', context: '', status: 'started' });
    try {
      await streamAction(`/api/projects/${projectId}/outline/chapter-review`, { instruction: instruction.trim() }, (line) => pushLog(line));
      await loadLatestChapterOutlineReview();
      pushLog({ label: '章节大纲总体审查', elapsed: '', tokens: '', context: '', status: 'completed' });
    } catch (error) {
      showError(error);
    } finally {
      setChapterOutlineReviewRunning(false);
    }
  }

  async function applyChapterOutlineReview() {
    if (!chapterOutlineReview?.run_id) return;
    const suggestions = chapterOutlineReview.repair_suggestions || [];
    const selectedIssueIds = suggestions.filter((item) => selectedChapterOutlineRepairIds[item.id] !== false).map((item) => item.id);
    if (suggestions.length > 0 && selectedIssueIds.length === 0) {
      pushLog({ label: '章节大纲总体审查', elapsed: '', tokens: '', context: '', status: 'no_selection' });
      return;
    }
    setChapterOutlineReviewApplying(true);
    pushLog({ label: '章节大纲审查应用', elapsed: '', tokens: '', context: '', status: 'started' });
    try {
      await streamAction(
        `/api/projects/${projectId}/outline/chapter-review/${chapterOutlineReview.run_id}/apply`,
        { selected_issue_ids: selectedIssueIds },
        (line) => pushLog(line),
      );
      await loadLatestChapterOutlineReview();
      await loadChapterOutlineWorkspace(chapterOutlineWorkspace?.selected_volume.index);
      pushLog({ label: '章节大纲审查应用', elapsed: '', tokens: '', context: '', status: 'completed' });
    } catch (error) {
      showError(error);
    } finally {
      setChapterOutlineReviewApplying(false);
    }
  }

  function dismissChapterOutlineReview() {
    if (!chapterOutlineReview) return;
    pushLog({ label: '章节大纲审查建议', elapsed: '', tokens: '', context: '', status: 'dismissed' });
    setChapterOutlineReview((currentReview) => (currentReview ? { ...currentReview, status: 'dismissed' } : currentReview));
  }

  async function submitPendingQuestions() {
    if (!pendingQuestions || pendingQuestions.items.length === 0 || pendingSubmitting || stageRunningRef.current) return;
    const answers = pendingQuestions.items.map((item) => {
      const selectedId = pendingAnswerSelection[item.id] || item.options[0]?.id || '';
      const selected = item.options.find((option) => option.id === selectedId) || item.options[0];
      if (!selected) throw new Error(`待确认问题没有可用选项：${item.question}`);
      if (selected.requires_input) {
        const customAnswer = (pendingCustomAnswers[item.id] || '').trim();
        if (!customAnswer) throw new Error(`请填写你的建议：${item.question}`);
        return { question: item.question, custom_answer: customAnswer, selected_option_id: selected.id };
      }
      return { question: item.question, answer: selected.answer, selected_option_id: selected.id };
    });
    stageRunningRef.current = true;
    setStageRunning(true);
    setPendingSubmitting(true);
    try {
      await streamAction(
        `/api/projects/${projectId}/outline/stages/${pendingQuestions.stage}/pending/submit`,
        { answers },
        (line) => pushLog(line),
      );
      setInstruction('');
      await refreshStages();
      await loadStage(activeStage);
    } catch (error) {
      showError(error);
    } finally {
      stageRunningRef.current = false;
      setStageRunning(false);
      setPendingSubmitting(false);
    }
  }

  async function reviewAll() {
    setReviewRunning(true);
    setReview(null);
    setSelectedRepairIds({});
    pushLog({ label: '章节总体审查', elapsed: '', tokens: '', context: '', status: 'started' });
    try {
      await streamAction(`/api/projects/${projectId}/chapters/review-all`, {}, (line) => pushLog(line));
      const latest = await api<ReviewReportData>(`/api/projects/${projectId}/chapters/review-all/latest`);
      setReview(latest);
      setSelectedRepairIds(buildRepairSelectionMap(latest.repair_suggestions || []));
      pushLog({ label: '章节总体审查', elapsed: '', tokens: '', context: '', status: 'completed' });
    } finally {
      setReviewRunning(false);
    }
  }

  async function applyRepair(chapter: number) {
    if (!review?.run_id) return;
    const suggestions = (review.repair_suggestions || []).filter((item) => item.chapter === chapter);
    const selectedIssueIds = suggestions.filter((item) => selectedRepairIds[item.id] !== false).map((item) => item.id);
    if (selectedIssueIds.length === 0) {
      pushLog({ label: `第 ${chapter} 章修改`, elapsed: '', tokens: '', context: '', status: 'no_selection' });
      return;
    }
    setApplyingChapter(chapter);
    try {
      const result = await api<{ path: string; version: number }>(`/api/projects/${projectId}/chapters/${chapter}/apply-repair`, {
        method: 'POST',
        body: JSON.stringify({ run_id: review.run_id, selected_issue_ids: selectedIssueIds }),
      });
      pushLog({ label: `第 ${chapter} 章修改`, elapsed: '', tokens: '', context: '', status: `draft_v${result.version}` });
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
          <button className={topSection === 'chapter-outline' ? 'active' : ''} onClick={() => setTopSection('chapter-outline')}><ListChecks size={16} />章节大纲</button>
          <button className={topSection === 'chapters' ? 'active' : ''} onClick={() => setTopSection('chapters')}><FileText size={16} />章节正文</button>
        </div>
        {topSection === 'outline' ? (
          <nav>
            {visibleStages.map((item) => (
              <button className={item.stage === activeStage && outlineStageView === 'edit' ? 'active' : ''} key={item.stage} onClick={() => { setActiveStage(item.stage); setOutlineStageView('edit'); }}>
                <FileText size={16} />
                <span>{stageLabel(item, item.stage)}</span>
                <small>{item.status}</small>
              </button>
            ))}
            <button className={outlineStageView === 'review' ? 'active' : ''} onClick={() => setOutlineStageView('review')}>
              <ListChecks size={16} />
              <span>总体审查</span>
              <small>outline</small>
            </button>
          </nav>
        ) : topSection === 'chapter-outline' ? (
          <nav>
            {(chapterOutlineWorkspace?.volume_specs || []).map((item) => (
              <button
                className={chapterOutlineWorkspace?.selected_volume.index === item.index && chapterOutlineView === 'volume' ? 'active' : ''}
                key={item.index}
                onClick={() => { setChapterOutlineView('volume'); loadChapterOutlineWorkspace(item.index).catch(showError); }}
              >
                <FileText size={16} />
                <span>{item.label || `第 ${item.index} 卷`}</span>
                <small>{item.name || '未命名'}</small>
              </button>
            ))}
            <button className={chapterOutlineView === 'review' ? 'active' : ''} onClick={() => setChapterOutlineView('review')}>
              <ListChecks size={16} />
              <span>总体审查</span>
              <small>chapter-outline</small>
            </button>
          </nav>
        ) : (
          <nav>
            {(chapterOutlineWorkspace?.volume_specs || []).map((item) => (
              <button
                className={chapterView !== 'review' && volume === item.index ? 'active' : ''}
                key={item.index}
                onClick={() => { setVolume(item.index); setChapterView('batch'); refreshChapters(false, item.index).catch(showError); }}
              >
                <FileText size={16} />
                <span>{item.label || `第 ${item.index} 卷`}</span>
                <small>{item.name || '未命名'}</small>
              </button>
            ))}
            <button className={chapterView === 'review' ? 'active' : ''} onClick={() => setChapterView('review')}>
              <ListChecks size={16} />
              <span>总体审查</span>
              <small>chapters</small>
            </button>
          </nav>
        )}
      </aside>

      {needsOnboarding ? (
        <section className="workspace onboarding-workspace">
          <div className="onboarding-panel">
            <header className="toolbar">
              <div>
                <h1>你想写一个什么样的故事？</h1>
                <p>先保存小说创意，再进入大纲。</p>
              </div>
              <button onClick={submitOnboardingIdea} disabled={!onboardingIdea.trim()}><Save size={16} />保存创意</button>
            </header>
            <textarea
              className="editor onboarding-input"
              value={onboardingIdea}
              onChange={(event) => setOnboardingIdea(event.target.value)}
              placeholder="例如：月球城市失忆工程师追查自己的小说手稿"
            />
            <div className="onboarding-hint">创意会保存到当前项目目录，并作为后续大纲阶段的输入。</div>
          </div>
        </section>
      ) : topSection === 'outline' && (
        <section className="workspace">
          {outlineStageView === 'edit' && (
            <>
              <header className="toolbar">
                <div>
                  <h1>{stageLabel(current, activeStage)}</h1>
                  <p>{current?.status || 'not_generated'}</p>
                </div>
                <button onClick={saveStage} disabled={loadingStage || stageRunning || currentStageLocked}><Save size={16} />保存</button>
              </header>
              <StageActionBar
                actionState={currentActionState}
                loadingStage={loadingStage}
                running={stageRunning}
                status={current?.status || 'not_generated'}
                onRun={runStage}
              />
              <input className="instruction" value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="当前大纲阶段生成、修订或锁定说明" />
              {pendingQuestions && pendingQuestions.items.length > 0 && (
                <PendingQuestionPanel
                  payload={pendingQuestions}
                  selectedAnswers={pendingAnswerSelection}
                  customAnswers={pendingCustomAnswers}
                  submitting={pendingSubmitting || stageRunning || loadingStage}
                  onSelectAnswer={(questionId, optionId) => setPendingAnswerSelection((values) => ({ ...values, [questionId]: optionId }))}
                  onCustomAnswerChange={(questionId, answer) => setPendingCustomAnswers((values) => ({ ...values, [questionId]: answer }))}
                  onSubmit={submitPendingQuestions}
                />
              )}
              {loadingStage ? <div className="loading">正在读取 {stageLabel(current, activeStage)}...</div> : <textarea className="editor" value={content} onChange={(event) => setContent(event.target.value)} disabled={currentStageLocked} />}
            </>
          )}
          {outlineStageView === 'review' && (
            <OutlineReviewWorkspace
              review={outlineReview}
              instruction={instruction}
              running={outlineReviewRunning}
              applying={outlineReviewApplying}
              onInstructionChange={setInstruction}
              onRun={runOutlineReview}
              outlineRepairDecisions={outlineRepairDecisions}
              onDecisionChange={(id, decision) => setOutlineRepairDecisions((currentState) => ({
                ...currentState,
                [id]: { ...(currentState[id] || { decision: 'recommended', custom_answer: '' }), decision },
              }))}
              onCustomAnswerChange={(id, customAnswer) => setOutlineRepairDecisions((currentState) => ({
                ...currentState,
                [id]: { ...(currentState[id] || { decision: 'recommended', custom_answer: '' }), custom_answer: customAnswer },
              }))}
              onApply={applyOutlineReview}
              onDismiss={dismissOutlineReview}
            />
          )}
        </section>
      )}

      {topSection === 'chapter-outline' && (
        <section className="workspace chapter-outline-workspace">
          <header className="toolbar">
            <div>
              <h1>章节大纲</h1>
              <p>按卷生成、修订和锁定章节大纲</p>
            </div>
            <button onClick={() => loadChapterOutlineWorkspace()} disabled={loadingChapterOutline || chapterOutlineRunning}><RefreshCw size={16} />刷新</button>
          </header>
          {loadingChapterOutline && <div className="loading">正在读取章节大纲...</div>}
          {!loadingChapterOutline && chapterOutlineWorkspace && (
            <div className="chapter-outline-layout">
              {chapterOutlineView === 'review' ? (
                <section className="review-workspace outline-review-panel">
                  <header className="toolbar">
                    <div>
                      <h1>章节大纲总体审查</h1>
                      <p>审查当前章节大纲并按卷修订</p>
                    </div>
                    <button onClick={runChapterOutlineReview} disabled={chapterOutlineReviewRunning || chapterOutlineReviewApplying}><ListChecks size={16} />{chapterOutlineReviewRunning ? '审查中' : '开始审查'}</button>
                  </header>
                  <input className="instruction" value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="可选：本次审查关注点" />
                  {chapterOutlineReviewRunning && <div className="loading">章节大纲总体审查正在运行...</div>}
                  {chapterOutlineReview ? (
                    <div className="review-report outline-review-report">
                      <div className="review-header">
                        <div>
                          <span>run_id: {chapterOutlineReview.run_id}</span>
                          <strong>{chapterOutlineReview.summary}</strong>
                          <small>{chapterOutlineReview.status || 'reviewed'} · {chapterOutlineReview.decision || 'revise'} · {chapterOutlineReview.score ?? 0}</small>
                        </div>
                        <div className="review-buttons">
                          <button onClick={dismissChapterOutlineReview} disabled={chapterOutlineReviewRunning || chapterOutlineReviewApplying}><X size={16} />不采纳</button>
                          <button onClick={applyChapterOutlineReview} disabled={chapterOutlineReviewRunning || chapterOutlineReviewApplying || chapterOutlineReview.decision === 'stop'}><Check size={16} />采纳选中项</button>
                        </div>
                      </div>
                      <p>{chapterOutlineReview.notes}</p>
                      <small>参考大纲：{chapterOutlineReview.source_outline_summary}</small>
                      {(chapterOutlineReview.repair_suggestions || []).length > 0 && (
                        <OutlineRepairSuggestionBoard
                          suggestions={chapterOutlineReview.repair_suggestions || []}
                          selectedOutlineRepairIds={selectedChapterOutlineRepairIds}
                          onToggle={(id, checked) => setSelectedChapterOutlineRepairIds((currentState) => ({ ...currentState, [id]: checked }))}
                        />
                      )}
                    </div>
                  ) : (
                    <div className="review-report outline-review-report empty-review">
                      <p>点击“开始审查”生成章节大纲审查意见。</p>
                    </div>
                  )}
                  {chapterOutlineReviewApplying && <div className="loading">章节大纲审查建议正在应用...</div>}
                </section>
              ) : (
                <article className="chapter-detail">
                  <header className="toolbar">
                    <div>
                      <h1>{chapterOutlineWorkspace.selected_volume.label}</h1>
                      <p>{chapterOutlineWorkspace.selected_volume.name || chapterOutlineWorkspace.selected_volume.status}</p>
                    </div>
                  </header>
                  <StageActionBar
                    actionState={chapterOutlineWorkspace.selected_volume}
                    loadingStage={loadingChapterOutline}
                    running={chapterOutlineRunning}
                    status={chapterOutlineWorkspace.selected_volume.status}
                    onRun={runChapterOutlineVolume}
                  />
                  <input className="instruction" value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="当前卷章节大纲生成、修订或锁定说明" />
                  <pre className="chapter-body">{chapterOutlineWorkspace.selected_volume.content || chapterOutlineWorkspace.selected_volume.summary || '暂无章节大纲内容。'}</pre>
                </article>
              )}
            </div>
          )}
          {!loadingChapterOutline && !chapterOutlineWorkspace && <p className="empty">暂无章节大纲工作区。</p>}
        </section>
      )}

      {topSection === 'chapters' && (
        <section className="workspace chapter-workspace">
          <div className="workspace-tabs" aria-label="章节视图">
            <button className={chapterView === 'batch' ? 'active' : ''} onClick={() => setChapterView('batch')}>
              <Play size={16} />批量生成
            </button>
            <button className={chapterView === 'list' ? 'active' : ''} onClick={() => setChapterView('list')}>
              <FileText size={16} />已生成章节
              <small>{chapters.length}</small>
            </button>
          </div>
          {chapterView === 'batch' && (
            <>
              <header className="toolbar">
                <div>
                  <h1>章节批量生成</h1>
                  <p>{chapterBatchWorkspace?.volume_label || `第 ${volume} 卷`} · 从第一个未生成章节开始连续生成</p>
                </div>
                <button onClick={() => refreshChapters(false, volume)}><RefreshCw size={16} />刷新</button>
              </header>
              <div className="batch-summary" aria-label="章节批量生成统计">
                <div><span>总章数</span><strong>{chapterBatchWorkspace?.total_chapters ?? 0}</strong></div>
                <div><span>已生成章数</span><strong>{chapterBatchWorkspace?.generated_chapters ?? 0}</strong></div>
                <div><span>剩余章数</span><strong>{chapterBatchWorkspace?.remaining_chapters ?? 0}</strong></div>
              </div>
              <div className="form-grid batch-form">
                <label>生成数量<input type="number" min={1} max={Math.max(1, chapterBatchWorkspace?.remaining_chapters ?? 1)} value={requestedChapterCount} onChange={(e) => setRequestedChapterCount(Number(e.target.value))} /></label>
                <button onClick={generateBatch} disabled={(chapterBatchWorkspace?.remaining_chapters ?? 0) < 1}><Play size={16} />生成章节</button>
              </div>
              {chapterBatchWorkspace?.next_chapter_number ? <p className="empty">下一章：第 {chapterBatchWorkspace.next_chapter_number} 章</p> : <p className="empty">当前卷没有剩余章节可生成。</p>}
            </>
          )}
          {chapterView === 'list' && (
            <>
              <header className="toolbar"><div><h1>已生成章节</h1><p>读取最新正文：final.md 优先，其次最高 draft_vN.md，再回退旧路径</p></div><button onClick={() => refreshChapters(false, volume)}><RefreshCw size={16} />刷新</button></header>
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
        <section className="progress-panel">
          <h2>进度</h2>
          <div className="progress-log">
            {log.length === 0 && <p className="empty">暂无进度。</p>}
            {log.map((item, index) => typeof item === 'string' ? (
              <pre key={`${index}-${item}`}>{item}</pre>
            ) : (
              <div className="progress-item" key={`${index}-${item.label}-${item.status}`}>
                <strong>{item.label}</strong>
                <span>{[item.status, item.elapsed, item.tokens, item.context].filter(Boolean).join(' · ')}</span>
              </div>
            ))}
          </div>
        </section>
      </aside>
    </main>
  );
}


function StageActionBar({
  actionState,
  loadingStage,
  running,
  status,
  onRun,
}: {
  actionState: ActionState;
  loadingStage: boolean;
  running: boolean;
  status: string;
  onRun: (action: 'generate' | 'revise' | 'lock') => void;
}) {
  return (
    <div className="stage-action-bar">
      <div className="stage-action-group">
        <span className="stage-status">{status}</span>
        <button onClick={() => onRun('generate')} disabled={loadingStage || running || !actionState.can_generate}>生成</button>
        <button onClick={() => onRun('revise')} disabled={loadingStage || running || !actionState.can_revise}>修订</button>
        <button onClick={() => onRun('lock')} disabled={loadingStage || running || !actionState.can_lock}>锁定</button>
      </div>
      {actionState.lock_reason && <span className="lock-badge"><Lock size={14} />{actionState.lock_reason}</span>}
    </div>
  );
}


function PendingQuestionPanel({
  payload,
  selectedAnswers,
  customAnswers,
  submitting,
  onSelectAnswer,
  onCustomAnswerChange,
  onSubmit,
}: {
  payload: PendingQuestionPayload;
  selectedAnswers: Record<string, string>;
  customAnswers: Record<string, string>;
  submitting: boolean;
  onSelectAnswer: (questionId: string, optionId: string) => void;
  onCustomAnswerChange: (questionId: string, answer: string) => void;
  onSubmit: () => void;
}) {
  const customIncomplete = payload.items.some((item) => {
    const selectedId = selectedAnswers[item.id] || item.options[0]?.id || '';
    return selectedId === 'custom' && !(customAnswers[item.id] || '').trim();
  });
  return (
    <section className="pending-panel">
      <header className="pending-panel-head">
        <div>
          <strong>待确认问题</strong>
          <small>{payload.items.length} 条，已预选推荐建议</small>
        </div>
        <button onClick={onSubmit} disabled={submitting || customIncomplete}>
          <Check size={16} />{submitting ? '提交中' : '提交确认'}
        </button>
      </header>
      <div className="pending-question-list">
        {payload.items.map((item) => (
          <section className="pending-question" key={item.id}>
            <strong>{item.question}</strong>
            <div className="pending-option-group" role="group" aria-label={item.question}>
              {item.options.map((option) => (
                <button
                  type="button"
                  key={option.id}
                  className={(selectedAnswers[item.id] || item.options[0]?.id) === option.id ? 'pending-option active' : 'pending-option'}
                  onClick={() => onSelectAnswer(item.id, option.id)}
                >
                  <span>{option.label}</span>
                  {option.answer && <small>{option.answer}</small>}
                </button>
              ))}
            </div>
            {(selectedAnswers[item.id] || item.options[0]?.id) === 'custom' && (
              <input
                className="pending-custom-answer"
                value={customAnswers[item.id] || ''}
                onChange={(event) => onCustomAnswerChange(item.id, event.target.value)}
                placeholder="请输入你的建议"
              />
            )}
          </section>
        ))}
      </div>
    </section>
  );
}


function OutlineReviewWorkspace({
  review,
  instruction,
  running,
  applying,
  onInstructionChange,
  onRun,
  outlineRepairDecisions,
  onDecisionChange,
  onCustomAnswerChange,
  onApply,
  onDismiss,
}: {
  review: OutlineReview | null;
  instruction: string;
  running: boolean;
  applying: boolean;
  outlineRepairDecisions: Record<string, OutlineRepairDecision>;
  onInstructionChange: (value: string) => void;
  onRun: () => void;
  onDecisionChange: (id: string, decision: OutlineRepairDecisionValue) => void;
  onCustomAnswerChange: (id: string, value: string) => void;
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
              <button onClick={onApply} disabled={running || applying || review?.decision === 'stop'}><Check size={16} />采纳选中项</button>
            </div>
          </div>
          <p>{review?.notes}</p>
          <small>参考大纲：{review?.source_outline_summary}</small>
          {(review?.repair_suggestions || []).length > 0 && (
            <OutlineRepairDecisionBoard
              suggestions={review?.repair_suggestions || []}
              decisions={outlineRepairDecisions}
              onDecisionChange={onDecisionChange}
              onCustomAnswerChange={onCustomAnswerChange}
            />
          )}
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
    <div className="outline-repair-table outline-repair-decisions" role="table" aria-label="大纲审查建议">
      <div className="outline-repair-row outline-repair-decision-head" role="row">
        <span role="columnheader">问题</span>
        <span role="columnheader">推荐修改意见</span>
        <span role="columnheader">暂不修改</span>
        <span role="columnheader">我的意见</span>
      </div>
      {suggestions.map((item) => {
        const value = decisions[item.id] || { decision: 'recommended', custom_answer: '' };
        return (
          <div className="outline-repair-row outline-repair-decision-row" role="row" key={item.id}>
            <span role="cell">
              <strong>{item.message}</strong>
              <small>{item.severity || 'normal'} · {item.category || 'review'}</small>
            </span>
            <label role="cell">
              <input
                type="radio"
                name={`outline-repair-${item.id}`}
                checked={value.decision === 'recommended'}
                onChange={() => onDecisionChange(item.id, 'recommended')}
              />
              <span>{item.recommendation}</span>
            </label>
            <label role="cell">
              <input
                type="radio"
                name={`outline-repair-${item.id}`}
                checked={value.decision === 'skip'}
                onChange={() => onDecisionChange(item.id, 'skip')}
              />
              <span>暂不修改</span>
            </label>
            <label role="cell" className="custom-repair-choice">
              <span>
                <input
                  type="radio"
                  name={`outline-repair-${item.id}`}
                  checked={value.decision === 'custom'}
                  onChange={() => onDecisionChange(item.id, 'custom')}
                />
                我的意见
              </span>
              <textarea
                value={value.custom_answer}
                onChange={(event) => onCustomAnswerChange(item.id, event.target.value)}
                disabled={value.decision !== 'custom'}
                placeholder="写入你的采纳意见"
              />
            </label>
          </div>
        );
      })}
    </div>
  );
}

function OutlineRepairSuggestionBoard({
  suggestions,
  selectedOutlineRepairIds,
  onToggle,
}: {
  suggestions: OutlineReviewSuggestion[];
  selectedOutlineRepairIds: Record<string, boolean>;
  onToggle: (id: string, checked: boolean) => void;
}) {
  return (
    <div className="outline-repair-table" role="table" aria-label="大纲审查建议">
      <div className="outline-repair-row outline-repair-head" role="row">
        <span role="columnheader">选择</span>
        <span role="columnheader">问题</span>
        <span role="columnheader">建议</span>
      </div>
      {suggestions.map((item) => (
        <label className="outline-repair-row" role="row" key={item.id}>
          <span role="cell">
            <input
              type="checkbox"
              checked={selectedOutlineRepairIds[item.id] ?? item.selected !== false}
              onChange={(event) => onToggle(item.id, event.target.checked)}
            />
          </span>
          <span role="cell">
            <strong>{item.message}</strong>
            <small>{item.severity || 'normal'} · {item.category || 'review'}</small>
          </span>
          <span role="cell">{item.recommendation}</span>
        </label>
      ))}
    </div>
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
