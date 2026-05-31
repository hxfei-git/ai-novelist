import { Check, ListChecks, LoaderCircle, X } from 'lucide-react';
import type {
  OutlineRepairDecision,
  OutlineRepairDecisionValue,
  OutlineReview,
  OutlineReviewSuggestion,
  ReviewReportData,
  ReviewSuggestion,
} from '../types';

const OUTLINE_REPAIR_PRIORITY_GROUPS = [
  { priority: 'high', label: '高优先级问题' },
  { priority: 'low', label: '低优先级问题' },
  { priority: 'suggestion', label: '建议问题' },
] as const;

function outlineRepairPriority(item: OutlineReviewSuggestion) {
  const priority = item.priority || 'low';
  return priority === 'high' || priority === 'low' || priority === 'suggestion' ? priority : 'low';
}

function groupOutlineRepairSuggestions(suggestions: OutlineReviewSuggestion[]) {
  return OUTLINE_REPAIR_PRIORITY_GROUPS
    .map((group) => ({
      ...group,
      items: suggestions.filter((item) => outlineRepairPriority(item) === group.priority),
    }))
    .filter((group) => group.items.length > 0);
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

export function OutlineReviewWorkspace({
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
  const reviewApplied = review?.applied === true || review?.status === 'applied';
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
              <button onClick={onDismiss} disabled={running || applying || reviewApplied}><X size={16} />不采纳</button>
              <button onClick={onApply} disabled={running || applying || reviewApplied || review?.decision === 'stop'}>
                {applying ? <LoaderCircle className="spin-icon" size={16} /> : <Check size={16} />}
                {applying ? '正在采纳' : reviewApplied ? '采纳完成' : '采纳选中项'}
              </button>
            </div>
          </div>
          <p>{review?.notes}</p>
          <small>参考大纲：{review?.source_outline_summary}</small>
          {reviewApplied && (
            <div className="review-complete">
              <Check size={16} />
              <span>采纳完成</span>
            </div>
          )}
          {!reviewApplied && (review?.repair_suggestions || []).length > 0 && (
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
      {applying && <div className="loading apply-loading"><LoaderCircle className="spin-icon" size={16} />正在采纳...</div>}
    </section>
  );
}

export function OutlineRepairDecisionBoard({
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
  const groups = groupOutlineRepairSuggestions(suggestions);
  return (
    <div className="outline-repair-decisions" aria-label="大纲审查建议">
      {groups.map((group) => (
        <section className="outline-repair-priority-group" key={group.priority}>
          <h2>{group.label}</h2>
          <div className="outline-repair-table" role="table" aria-label={group.label}>
            <div className="outline-repair-row outline-repair-decision-head" role="row">
              <span role="columnheader">问题</span>
              <span role="columnheader">推荐修改意见</span>
              <span role="columnheader">暂不修改</span>
              <span role="columnheader">我的意见</span>
            </div>
            {group.items.map((item) => {
              const value = decisions[item.id] || { decision: 'recommended', custom_answer: '' };
              return (
                <div className="outline-repair-row outline-repair-decision-row" role="row" key={item.id}>
                  <span role="cell">
                    <strong>{item.message}</strong>
                    <small>{item.severity || 'normal'} · {item.category || 'review'}</small>
                  </span>
                  <label role="cell">
                    <input type="radio" name={`outline-repair-${item.id}`} checked={value.decision === 'recommended'} onChange={() => onDecisionChange(item.id, 'recommended')} />
                    <span>{item.recommendation}</span>
                  </label>
                  <label role="cell">
                    <input type="radio" name={`outline-repair-${item.id}`} checked={value.decision === 'skip'} onChange={() => onDecisionChange(item.id, 'skip')} />
                    <span>暂不修改</span>
                  </label>
                  <label role="cell" className="custom-repair-choice">
                    <span>
                      <input type="radio" name={`outline-repair-${item.id}`} checked={value.decision === 'custom'} onChange={() => onDecisionChange(item.id, 'custom')} />
                      我的意见
                    </span>
                    <textarea value={value.custom_answer} onChange={(event) => onCustomAnswerChange(item.id, event.target.value)} disabled={value.decision !== 'custom'} placeholder="写入你的采纳意见" />
                  </label>
                </div>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}

export function OutlineRepairSuggestionBoard({
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
            <input type="checkbox" checked={selectedOutlineRepairIds[item.id] ?? item.selected !== false} onChange={(event) => onToggle(item.id, event.target.checked)} />
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

export function IssueBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="issues">
      <strong>{title}</strong>
      {items.length === 0 ? <p>暂无</p> : items.map((item) => <p key={item}>{item}</p>)}
    </section>
  );
}

export function ReviewReport({ review }: { review: ReviewReportData }) {
  const issues = Array.isArray(review.issues) ? review.issues : [];
  return (
    <div className="review-report">
      <strong>{review.summary}</strong>
      <span>run_id: {review.run_id}</span>
      {issues.map((item, index) => (
        <p key={`${index}-${item.message}`}>[{item.severity}] {item.chapter ? `第 ${item.chapter} 章` : '全局'} {item.message}</p>
      ))}
    </div>
  );
}

export function RepairSuggestionBoard({
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
                  <input type="checkbox" checked={selectedRepairIds[item.id] ?? item.selected !== false} onChange={(event) => onToggle(item.id, event.target.checked)} />
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
