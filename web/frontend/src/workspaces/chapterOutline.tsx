import { Check, ListChecks, RefreshCw, X } from 'lucide-react';
import type { ChapterOutlineWorkspace as ChapterOutlineWorkspaceData, OutlineReview } from '../types';
import { StageActionBar } from './outline';
import { OutlineRepairSuggestionBoard } from './review';

type StageAction = 'generate' | 'revise' | 'lock';

type ChapterOutlineWorkspaceViewProps = {
  workspace: ChapterOutlineWorkspaceData | null;
  loading: boolean;
  running: boolean;
  view: 'volume' | 'review';
  instruction: string;
  review: OutlineReview | null;
  reviewRunning: boolean;
  reviewApplying: boolean;
  selectedRepairIds: Record<string, boolean>;
  onRefresh: () => void;
  onRunVolume: (action: StageAction) => void;
  onInstructionChange: (value: string) => void;
  onRunReview: () => void;
  onDismissReview: () => void;
  onApplyReview: () => void;
  onToggleRepair: (id: string, checked: boolean) => void;
};

export function ChapterOutlineWorkspaceView({
  workspace,
  loading,
  running,
  view,
  instruction,
  review,
  reviewRunning,
  reviewApplying,
  selectedRepairIds,
  onRefresh,
  onRunVolume,
  onInstructionChange,
  onRunReview,
  onDismissReview,
  onApplyReview,
  onToggleRepair,
}: ChapterOutlineWorkspaceViewProps) {
  return (
    <section className="workspace chapter-outline-workspace">
      <header className="toolbar">
        <div>
          <h1>章节大纲</h1>
          <p>按卷生成、修订和锁定章节大纲</p>
        </div>
        <button onClick={onRefresh} disabled={loading || running}><RefreshCw size={16} />刷新</button>
      </header>
      {loading && <div className="loading">正在读取章节大纲...</div>}
      {!loading && workspace && (
        <div className="chapter-outline-layout">
          {view === 'review' ? (
            <section className="review-workspace outline-review-panel">
              <header className="toolbar">
                <div>
                  <h1>章节大纲总体审查</h1>
                  <p>审查当前章节大纲并按卷修订</p>
                </div>
                <button onClick={onRunReview} disabled={reviewRunning || reviewApplying}><ListChecks size={16} />{reviewRunning ? '审查中' : '开始审查'}</button>
              </header>
              <input className="instruction" value={instruction} onChange={(event) => onInstructionChange(event.target.value)} placeholder="可选：本次审查关注点" />
              {reviewRunning && <div className="loading">章节大纲总体审查正在运行...</div>}
              {review ? (
                <div className="review-report outline-review-report">
                  <div className="review-header">
                    <div>
                      <span>run_id: {review.run_id}</span>
                      <strong>{review.summary}</strong>
                      <small>{review.status || 'reviewed'} · {review.decision || 'revise'} · {review.score ?? 0}</small>
                    </div>
                    <div className="review-buttons">
                      <button onClick={onDismissReview} disabled={reviewRunning || reviewApplying}><X size={16} />不采纳</button>
                      <button onClick={onApplyReview} disabled={reviewRunning || reviewApplying || review.decision === 'stop'}><Check size={16} />采纳选中项</button>
                    </div>
                  </div>
                  <p>{review.notes}</p>
                  <small>参考大纲：{review.source_outline_summary}</small>
                  {(review.repair_suggestions || []).length > 0 && (
                    <OutlineRepairSuggestionBoard suggestions={review.repair_suggestions || []} selectedOutlineRepairIds={selectedRepairIds} onToggle={onToggleRepair} />
                  )}
                </div>
              ) : (
                <div className="review-report outline-review-report empty-review">
                  <p>点击“开始审查”生成章节大纲审查意见。</p>
                </div>
              )}
              {reviewApplying && <div className="loading">章节大纲审查建议正在应用...</div>}
            </section>
          ) : (
            <article className="chapter-detail">
              <header className="toolbar">
                <div>
                  <h1>{workspace.selected_volume.label}</h1>
                  <p>{workspace.selected_volume.name || workspace.selected_volume.status}</p>
                </div>
              </header>
              <StageActionBar actionState={workspace.selected_volume} loadingStage={loading} running={running} status={workspace.selected_volume.status} onRun={onRunVolume} />
              <input className="instruction" value={instruction} onChange={(event) => onInstructionChange(event.target.value)} placeholder="当前卷章节大纲生成、修订或锁定说明" />
              <pre className="chapter-body">{workspace.selected_volume.content || workspace.selected_volume.summary || '暂无章节大纲内容。'}</pre>
            </article>
          )}
        </div>
      )}
      {!loading && !workspace && <p className="empty">暂无章节大纲工作区。</p>}
    </section>
  );
}
