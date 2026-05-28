import { Check, Lock, Save } from 'lucide-react';
import type { ActionState, PendingQuestionPayload } from '../types';

type StageAction = 'generate' | 'revise' | 'lock';

export function StageActionBar({
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
  onRun: (action: StageAction) => void;
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

export function PendingQuestionPanel({
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

type OutlineEditWorkspaceProps = {
  title: string;
  status: string;
  actionState: ActionState;
  loadingStage: boolean;
  running: boolean;
  locked: boolean;
  instruction: string;
  pendingQuestions: PendingQuestionPayload | null;
  selectedAnswers: Record<string, string>;
  customAnswers: Record<string, string>;
  pendingSubmitting: boolean;
  content: string;
  onSave: () => void;
  onRun: (action: StageAction) => void;
  onInstructionChange: (value: string) => void;
  onSelectPendingAnswer: (questionId: string, optionId: string) => void;
  onCustomPendingAnswerChange: (questionId: string, answer: string) => void;
  onSubmitPendingQuestions: () => void;
  onContentChange: (value: string) => void;
};

export function OutlineEditWorkspace({
  title,
  status,
  actionState,
  loadingStage,
  running,
  locked,
  instruction,
  pendingQuestions,
  selectedAnswers,
  customAnswers,
  pendingSubmitting,
  content,
  onSave,
  onRun,
  onInstructionChange,
  onSelectPendingAnswer,
  onCustomPendingAnswerChange,
  onSubmitPendingQuestions,
  onContentChange,
}: OutlineEditWorkspaceProps) {
  return (
    <>
      <header className="toolbar">
        <div>
          <h1>{title}</h1>
          <p>{status}</p>
        </div>
        <button onClick={onSave} disabled={loadingStage || running || locked}><Save size={16} />保存</button>
      </header>
      <StageActionBar actionState={actionState} loadingStage={loadingStage} running={running} status={status} onRun={onRun} />
      <input className="instruction" value={instruction} onChange={(event) => onInstructionChange(event.target.value)} placeholder="当前大纲阶段生成、修订或锁定说明" />
      {pendingQuestions && pendingQuestions.items.length > 0 && (
        <PendingQuestionPanel
          payload={pendingQuestions}
          selectedAnswers={selectedAnswers}
          customAnswers={customAnswers}
          submitting={pendingSubmitting || running || loadingStage}
          onSelectAnswer={onSelectPendingAnswer}
          onCustomAnswerChange={onCustomPendingAnswerChange}
          onSubmit={onSubmitPendingQuestions}
        />
      )}
      {loadingStage ? <div className="loading">正在读取 {title}...</div> : <textarea className="editor" value={content} onChange={(event) => onContentChange(event.target.value)} disabled={locked} />}
    </>
  );
}
