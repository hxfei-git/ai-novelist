import { Save } from 'lucide-react';

type OnboardingWorkspaceProps = {
  idea: string;
  onIdeaChange: (value: string) => void;
  onSubmit: () => void;
};

export function OnboardingWorkspace({ idea, onIdeaChange, onSubmit }: OnboardingWorkspaceProps) {
  return (
    <section className="workspace onboarding-workspace">
      <div className="onboarding-panel">
        <header className="toolbar">
          <div>
            <h1>你想写一个什么样的故事？</h1>
            <p>先保存小说创意，再进入大纲。</p>
          </div>
          <button onClick={onSubmit} disabled={!idea.trim()}><Save size={16} />保存创意</button>
        </header>
        <textarea
          className="editor onboarding-input"
          value={idea}
          onChange={(event) => onIdeaChange(event.target.value)}
          placeholder="例如：月球城市失忆工程师追查自己的小说手稿"
        />
        <div className="onboarding-hint">创意会保存到当前项目目录，并作为后续大纲阶段的输入。</div>
      </div>
    </section>
  );
}
