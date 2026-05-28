import { Check, FileText, Play, RefreshCw } from 'lucide-react';
import type { Chapter, ChapterBatchWorkspace, ChapterView, ReviewReportData } from '../types';
import { RepairSuggestionBoard, ReviewReport } from './review';

function chapterVersionLabel(chapter: Chapter | null) {
  if (!chapter) return '';
  if (chapter.source === 'final') return '定稿';
  if (chapter.source === 'draft') return `草稿 v${chapter.version ?? 1}`;
  return '旧正文';
}

type ChaptersWorkspaceProps = {
  chapterView: ChapterView;
  chapters: Chapter[];
  selectedChapter: number | null;
  chapterDetail: Chapter | null;
  loadingChapter: boolean;
  volume: number;
  requestedChapterCount: number;
  chapterBatchWorkspace: ChapterBatchWorkspace | null;
  chapterBatchRunning: boolean;
  review: ReviewReportData | null;
  reviewRunning: boolean;
  selectedRepairIds: Record<string, boolean>;
  applyingChapter: number | null;
  onSetChapterView: (view: ChapterView) => void;
  onRefreshChapters: () => void;
  onRequestedChapterCountChange: (value: number) => void;
  onGenerateBatch: () => void;
  onSelectChapter: (chapter: number) => void;
  onReviewAll: () => void;
  onToggleRepair: (id: string, checked: boolean) => void;
  onApplyRepair: (chapter: number) => void;
};

export function ChaptersWorkspace({
  chapterView,
  chapters,
  selectedChapter,
  chapterDetail,
  loadingChapter,
  volume,
  requestedChapterCount,
  chapterBatchWorkspace,
  chapterBatchRunning,
  review,
  reviewRunning,
  selectedRepairIds,
  applyingChapter,
  onSetChapterView,
  onRefreshChapters,
  onRequestedChapterCountChange,
  onGenerateBatch,
  onSelectChapter,
  onReviewAll,
  onToggleRepair,
  onApplyRepair,
}: ChaptersWorkspaceProps) {
  return (
    <section className="workspace chapter-workspace">
      <div className="workspace-tabs" aria-label="章节视图">
        <button className={chapterView === 'batch' ? 'active' : ''} onClick={() => onSetChapterView('batch')}>
          <Play size={16} />批量生成
        </button>
        <button className={chapterView === 'list' ? 'active' : ''} onClick={() => onSetChapterView('list')}>
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
            <button onClick={onRefreshChapters}><RefreshCw size={16} />刷新</button>
          </header>
          <div className="batch-summary" aria-label="章节批量生成统计">
            <div><span>总章数</span><strong>{chapterBatchWorkspace?.total_chapters ?? 0}</strong></div>
            <div><span>已生成章数</span><strong>{chapterBatchWorkspace?.generated_chapters ?? 0}</strong></div>
            <div><span>剩余章数</span><strong>{chapterBatchWorkspace?.remaining_chapters ?? 0}</strong></div>
          </div>
          <div className="form-grid batch-form">
            <label>生成数量<input type="number" min={1} max={Math.max(1, chapterBatchWorkspace?.remaining_chapters ?? 1)} value={requestedChapterCount} onChange={(e) => onRequestedChapterCountChange(Number(e.target.value))} /></label>
            <button onClick={onGenerateBatch} disabled={chapterBatchRunning || (chapterBatchWorkspace?.remaining_chapters ?? 0) < 1}><Play size={16} />{chapterBatchRunning ? '生成中' : '生成章节'}</button>
          </div>
          {chapterBatchWorkspace?.next_chapter_number ? <p className="empty">下一章：第 {chapterBatchWorkspace.next_chapter_number} 章</p> : <p className="empty">当前卷没有剩余章节可生成。</p>}
        </>
      )}
      {chapterView === 'list' && (
        <>
          <header className="toolbar"><div><h1>已生成章节</h1><p>读取最新正文：final.md 优先，其次最高 draft_vN.md，再回退旧路径</p></div><button onClick={onRefreshChapters}><RefreshCw size={16} />刷新</button></header>
          <div className="chapter-layout">
            <div className="chapter-list">
              {chapters.map((item) => (
                <button className={item.chapter === selectedChapter ? 'active' : ''} key={item.chapter} onClick={() => onSelectChapter(item.chapter)}>
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
            <button onClick={onReviewAll} disabled={reviewRunning}><Check size={16} />{reviewRunning ? '审查中' : '开始审查'}</button>
          </div>
          {reviewRunning && <div className="loading">章节总体审查正在运行...</div>}
          {review && <ReviewReport review={review} />}
          {review && (review.repair_suggestions || []).length > 0 && (
            <RepairSuggestionBoard review={review} selectedRepairIds={selectedRepairIds} onToggle={onToggleRepair} onSubmit={onApplyRepair} submittingChapter={applyingChapter} />
          )}
        </>
      )}
    </section>
  );
}
