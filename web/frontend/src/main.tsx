import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { FileText, Layers, ListChecks, Save } from 'lucide-react';
import './styles.css';
import { api, streamAction } from './api';
import { upsertProgressItem } from './progress';
import { ChaptersWorkspace } from './workspaces/chapters';
import { ChapterOutlineWorkspaceView } from './workspaces/chapterOutline';
import { OutlineEditWorkspace } from './workspaces/outline';
import { OnboardingWorkspace } from './workspaces/project';
import { OutlineReviewWorkspace } from './workspaces/review';
import type {
  ActionState,
  Chapter,
  ChapterBatchWorkspace,
  ChapterOutlineWorkspace,
  ChapterView,
  OutlineRepairDecision,
  OutlineReview,
  OutlineReviewSuggestion,
  OutlineStageView,
  PendingQuestion,
  PendingQuestionPayload,
  ProgressItem,
  Project,
  ProjectState,
  ReviewReportData,
  ReviewSuggestion,
  Stage,
  TopSection,
} from './types';

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
  const [chapterBatchRunning, setChapterBatchRunning] = useState(false);
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
    loadProjectState().catch(showBackgroundError);
    loadProjectProgressLog().catch(showBackgroundError);
    refreshStages().catch(showBackgroundError);
    refreshChapters(false, 1).catch(showBackgroundError);
    loadLatestReview().catch(() => setReview(null));
    loadLatestOutlineReview().catch(() => setOutlineReview(null));
    loadLatestChapterOutlineReview().catch(() => setChapterOutlineReview(null));
    loadChapterOutlineWorkspace().catch(showBackgroundError);
  }, [projectId]);

  useEffect(() => {
    if (!projectId || !activeStage) return;
    loadStage(activeStage).catch(showBackgroundError);
  }, [projectId, activeStage]);

  useEffect(() => {
    if (!projectId || !selectedChapter) return;
    loadChapter(selectedChapter).catch(showBackgroundError);
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

  function isTransientFetchError(error: unknown) {
    return error instanceof TypeError && error.message === 'Failed to fetch';
  }

  function showBackgroundError(error: unknown) {
    if (isTransientFetchError(error)) return;
    showError(error);
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

  async function saveProjectProgressLogForProject(targetProjectId: string, items: ProgressItem[]) {
    if (!targetProjectId) return;
    await api<{ items: ProgressItem[] }>(`/api/projects/${targetProjectId}/progress-log`, {
      method: 'PUT',
      body: JSON.stringify({ items }),
    });
  }

  async function saveProjectProgressLog(items: ProgressItem[]) {
    await saveProjectProgressLogForProject(projectId, items);
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
    await saveProjectProgressLogForProject(state.project_id, []);
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
    setInstruction('');
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
      try {
        await refreshStages();
        await loadStage(activeStage);
      } catch (refreshError) {
        showBackgroundError(refreshError);
      }
    } catch (error) {
      showError(error);
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
    } catch (error) {
      showError(error);
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
    try {
      const item = await api<Chapter>(`/api/projects/${projectId}/chapters/${chapter}`);
      if (token !== chapterRequestRef.current || chapter !== selectedChapter) return;
      setChapterDetail(item);
    } finally {
      if (token === chapterRequestRef.current && chapter === selectedChapter) setLoadingChapter(false);
    }
  }

  async function generateBatch() {
    if (chapterBatchRunning) return;
    const remainingChapters = chapterBatchWorkspace?.remaining_chapters ?? 0;
    const requestedCount = Math.max(1, Number(requestedChapterCount) || 1);
    const actualCount = Math.min(requestedCount, remainingChapters);
    if (actualCount < 1) return;
    setChapterBatchRunning(true);
    try {
      pushLog({ label: '章节批量生成', model: '', elapsed: '', tokens: '', context: '', status: 'started' });
      await streamAction(
        `/api/projects/${projectId}/chapters/generate-batch`,
        { volume, requested_count: actualCount },
        (line) => pushLog(line),
      );
      await refreshChapters(true, volume);
      pushLog({ label: '章节批量生成', model: '', elapsed: '', tokens: '', context: '', status: 'completed' });
    } catch (error) {
      showError(error);
    } finally {
      setChapterBatchRunning(false);
    }
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
    pushLog({ label: '大纲总体审查', model: '', elapsed: '', tokens: '', context: '', status: 'started' });
    try {
      await streamAction(`/api/projects/${projectId}/outline/review`, { instruction: instruction.trim() }, (line) => pushLog(line));
      await loadLatestOutlineReview();
      pushLog({ label: '大纲总体审查', model: '', elapsed: '', tokens: '', context: '', status: 'completed' });
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
      pushLog({ label: '大纲总体审查', model: '', elapsed: '', tokens: '', context: '', status: 'no_selection' });
      return;
    }
    if (emptyCustom) {
      showError(new Error('请先填写“我的意见”再应用。'));
      return;
    }
    setOutlineReviewApplying(true);
    pushLog({ label: '大纲审查应用', model: '', elapsed: '', tokens: '', context: '', status: 'started' });
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
      pushLog({ label: '大纲审查应用', model: '', elapsed: '', tokens: '', context: '', status: 'completed' });
    } catch (error) {
      showError(error);
    } finally {
      setOutlineReviewApplying(false);
    }
  }

  function dismissOutlineReview() {
    if (!outlineReview) return;
    pushLog({ label: '大纲审查建议', model: '', elapsed: '', tokens: '', context: '', status: 'dismissed' });
    setOutlineReview((currentReview) => (currentReview ? { ...currentReview, status: 'dismissed' } : currentReview));
  }

  async function runChapterOutlineReview() {
    setChapterOutlineReviewRunning(true);
    pushLog({ label: '章节大纲总体审查', model: '', elapsed: '', tokens: '', context: '', status: 'started' });
    try {
      await streamAction(`/api/projects/${projectId}/outline/chapter-review`, { instruction: instruction.trim() }, (line) => pushLog(line));
      await loadLatestChapterOutlineReview();
      pushLog({ label: '章节大纲总体审查', model: '', elapsed: '', tokens: '', context: '', status: 'completed' });
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
      pushLog({ label: '章节大纲总体审查', model: '', elapsed: '', tokens: '', context: '', status: 'no_selection' });
      return;
    }
    setChapterOutlineReviewApplying(true);
    pushLog({ label: '章节大纲审查应用', model: '', elapsed: '', tokens: '', context: '', status: 'started' });
    try {
      await streamAction(
        `/api/projects/${projectId}/outline/chapter-review/${chapterOutlineReview.run_id}/apply`,
        { selected_issue_ids: selectedIssueIds },
        (line) => pushLog(line),
      );
      await loadLatestChapterOutlineReview();
      await loadChapterOutlineWorkspace(chapterOutlineWorkspace?.selected_volume.index);
      pushLog({ label: '章节大纲审查应用', model: '', elapsed: '', tokens: '', context: '', status: 'completed' });
    } catch (error) {
      showError(error);
    } finally {
      setChapterOutlineReviewApplying(false);
    }
  }

  function dismissChapterOutlineReview() {
    if (!chapterOutlineReview) return;
    pushLog({ label: '章节大纲审查建议', model: '', elapsed: '', tokens: '', context: '', status: 'dismissed' });
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
    pushLog({ label: '章节总体审查', model: '', elapsed: '', tokens: '', context: '', status: 'started' });
    try {
      await streamAction(`/api/projects/${projectId}/chapters/review-all`, {}, (line) => pushLog(line));
      const latest = await api<ReviewReportData>(`/api/projects/${projectId}/chapters/review-all/latest`);
      setReview(latest);
      setSelectedRepairIds(buildRepairSelectionMap(latest.repair_suggestions || []));
      pushLog({ label: '章节总体审查', model: '', elapsed: '', tokens: '', context: '', status: 'completed' });
    } catch (error) {
      showError(error);
    } finally {
      setReviewRunning(false);
    }
  }

  async function applyRepair(chapter: number) {
    if (!review?.run_id) return;
    const suggestions = (review.repair_suggestions || []).filter((item) => item.chapter === chapter);
    const selectedIssueIds = suggestions.filter((item) => selectedRepairIds[item.id] !== false).map((item) => item.id);
    if (selectedIssueIds.length === 0) {
      pushLog({ label: `第 ${chapter} 章修改`, model: '', elapsed: '', tokens: '', context: '', status: 'no_selection' });
      return;
    }
    setApplyingChapter(chapter);
    try {
      const result = await api<{ path: string; version: number }>(`/api/projects/${projectId}/chapters/${chapter}/apply-repair`, {
        method: 'POST',
        body: JSON.stringify({ run_id: review.run_id, selected_issue_ids: selectedIssueIds }),
      });
      pushLog({ label: `第 ${chapter} 章修改`, model: '', elapsed: '', tokens: '', context: '', status: `draft_v${result.version}` });
      await refreshChapters();
      if (selectedChapter === chapter) await loadChapter(chapter);
    } catch (error) {
      showError(error);
    } finally {
      setApplyingChapter(null);
    }
  }

  const visibleLog = [...log].reverse();

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
        <OnboardingWorkspace idea={onboardingIdea} onIdeaChange={setOnboardingIdea} onSubmit={submitOnboardingIdea} />
      ) : topSection === 'outline' && (
        <section className="workspace">
          {outlineStageView === 'edit' && (
            <OutlineEditWorkspace
              title={stageLabel(current, activeStage)}
              status={current?.status || 'not_generated'}
              actionState={currentActionState}
              loadingStage={loadingStage}
              running={stageRunning}
              locked={currentStageLocked}
              instruction={instruction}
              pendingQuestions={pendingQuestions}
              selectedAnswers={pendingAnswerSelection}
              customAnswers={pendingCustomAnswers}
              pendingSubmitting={pendingSubmitting}
              content={content}
              onSave={saveStage}
              onRun={runStage}
              onInstructionChange={setInstruction}
              onSelectPendingAnswer={(questionId, optionId) => setPendingAnswerSelection((values) => ({ ...values, [questionId]: optionId }))}
              onCustomPendingAnswerChange={(questionId, answer) => setPendingCustomAnswers((values) => ({ ...values, [questionId]: answer }))}
              onSubmitPendingQuestions={submitPendingQuestions}
              onContentChange={setContent}
            />
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
        <ChapterOutlineWorkspaceView
          workspace={chapterOutlineWorkspace}
          loading={loadingChapterOutline}
          running={chapterOutlineRunning}
          view={chapterOutlineView}
          instruction={instruction}
          review={chapterOutlineReview}
          reviewRunning={chapterOutlineReviewRunning}
          reviewApplying={chapterOutlineReviewApplying}
          selectedRepairIds={selectedChapterOutlineRepairIds}
          onRefresh={() => loadChapterOutlineWorkspace()}
          onRunVolume={runChapterOutlineVolume}
          onInstructionChange={setInstruction}
          onRunReview={runChapterOutlineReview}
          onDismissReview={dismissChapterOutlineReview}
          onApplyReview={applyChapterOutlineReview}
          onToggleRepair={(id, checked) => setSelectedChapterOutlineRepairIds((currentState) => ({ ...currentState, [id]: checked }))}
        />
      )}


      {topSection === 'chapters' && (
        <ChaptersWorkspace
          chapterView={chapterView}
          chapters={chapters}
          selectedChapter={selectedChapter}
          chapterDetail={chapterDetail}
          loadingChapter={loadingChapter}
          volume={volume}
          requestedChapterCount={requestedChapterCount}
          chapterBatchWorkspace={chapterBatchWorkspace}
          chapterBatchRunning={chapterBatchRunning}
          review={review}
          reviewRunning={reviewRunning}
          selectedRepairIds={selectedRepairIds}
          applyingChapter={applyingChapter}
          onSetChapterView={setChapterView}
          onRefreshChapters={() => refreshChapters(false, volume)}
          onRequestedChapterCountChange={setRequestedChapterCount}
          onGenerateBatch={generateBatch}
          onSelectChapter={setSelectedChapter}
          onReviewAll={reviewAll}
          onToggleRepair={(id, checked) => setSelectedRepairIds((currentState) => ({ ...currentState, [id]: checked }))}
          onApplyRepair={applyRepair}
        />
      )}


      <aside className="right">
        <section className="progress-panel">
          <h2>进度</h2>
          <div className="progress-log">
            {log.length === 0 && <p className="empty">暂无进度。</p>}
            {visibleLog.map((item, index) => typeof item === 'string' ? (
              <pre key={`${index}-${item}`}>{item}</pre>
            ) : (
              <div className="progress-item" key={`${index}-${item.label}-${item.status}`}>
                <strong>{item.label}</strong>
                <span>{[item.status, item.model, item.elapsed, item.tokens, item.context].filter(Boolean).join(' · ')}</span>
              </div>
            ))}
          </div>
        </section>
      </aside>
    </main>
  );
}


createRoot(document.getElementById('root')!).render(<App />);
