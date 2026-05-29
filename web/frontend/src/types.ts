export type Project = { project_id: string; title: string; path: string };
export type ProjectState = {
  project_id: string;
  title: string;
  idea: string;
  outline: string;
  worldbuilding: string;
  chapter_plan: string;
  outline_stage_summaries: Record<string, string>;
  outline_stage_artifacts: Record<string, { status?: string; summary?: string }>;
};
export type ActionState = {
  can_generate: boolean;
  can_revise: boolean;
  can_lock: boolean;
  lock_reason: string;
};
export type Stage = {
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
export type PendingOption = {
  id: string;
  label: string;
  answer: string;
  requires_input?: boolean;
};
export type PendingQuestion = {
  id: string;
  question: string;
  options: PendingOption[];
};
export type PendingQuestionPayload = {
  project_id: string;
  stage: string;
  items: PendingQuestion[];
};
export type ChapterOutlineVolumeSpec = {
  index: number;
  label: string;
  name: string;
  summary?: string;
};
export type ChapterOutlineSelectedVolume = {
  index: number;
  label: string;
  name: string;
  status: string;
  summary: string;
  content: string;
} & ActionState;
export type ChapterOutlineWorkspace = {
  volume_specs: ChapterOutlineVolumeSpec[];
  current_volume_index: number;
  completed_volumes: number[];
  volume_statuses: Record<string, string>;
  selected_volume: ChapterOutlineSelectedVolume;
};
export type Chapter = {
  chapter: number;
  title: string;
  path: string;
  source: string;
  version: number | null;
  updated_at: string;
  summary: string;
  content?: string;
};
export type ChapterBatchWorkspace = {
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
export type ReviewIssue = {
  severity: string;
  chapter: number | null;
  category?: string;
  message: string;
};
export type ReviewSuggestion = {
  id: string;
  chapter: number | null;
  severity: string;
  category: string;
  message: string;
  recommendation: string;
  selected: boolean;
};
export type ReviewReportData = {
  project_id: string;
  run_id: string;
  status: string;
  summary: string;
  issues: ReviewIssue[];
  repair_suggestions?: ReviewSuggestion[];
};
export type OutlineReview = {
  project_id: string;
  run_id: string;
  created_at: string;
  status: string;
  applied?: boolean;
  applied_at?: string;
  applied_path?: string;
  updated_stages?: string[];
  skipped_stages?: string[];
  decision: string;
  score: number;
  summary: string;
  notes: string;
  revision_instruction: string;
  source_outline_summary: string;
  source_outline: string;
  repair_suggestions?: OutlineReviewSuggestion[];
};
export type OutlineReviewSuggestion = {
  id: string;
  severity: string;
  category: string;
  message: string;
  recommendation: string;
  selected: boolean;
};
export type OutlineRepairDecisionValue = 'recommended' | 'skip' | 'custom';
export type OutlineRepairDecision = {
  decision: OutlineRepairDecisionValue;
  custom_answer: string;
};
export type ProgressEvent = {
  key?: string;
  label: string;
  model: string;
  elapsed: string;
  tokens: string;
  context: string;
  status: string;
};
export type ProgressItem = string | ProgressEvent;
export type TopSection = 'outline' | 'chapter-outline' | 'chapters';
export type OutlineStageView = 'edit' | 'review';
export type ChapterView = 'batch' | 'list' | 'review';
