from ai_novelist.artifacts import load_artifacts
from ai_novelist.graph_outline import run_outline_stage_node
from ai_novelist.outline.story_flow_structure import (
    STORY_FLOW_REQUIRED_HEADINGS,
    append_missing_story_flow_sections,
    empty_story_flow_sections,
    extract_markdown_sections,
    has_nonempty_story_flow_section,
    missing_story_flow_headings,
    normalize_heading,
    validate_story_flow_outline,
)
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


class StubAdapter:
    def __init__(self, output: str) -> None:
        self.output = output
        self.prompts: list[str] = []

    def complete(self, prompt: str, project_dir):  # noqa: ANN001
        self.prompts.append(prompt)
        return self.output


def test_normalize_heading_handles_common_variants():
    assert normalize_heading("### 爽点 / 卖点兑现节奏") == normalize_heading("爽点/卖点兑现节奏")
    assert normalize_heading("伏笔、悬念与揭示节奏") == normalize_heading("伏笔悬念与揭示节奏")
    assert normalize_heading("## 结局路径") == normalize_heading("终局路径")


def test_story_flow_section_extraction_matches_canonical_headings():
    text = """## 故事流程稿\n\n### 故事主线推进\n- 主线推进\n\n### 爽点/卖点兑现节奏\n- 开局卖点\n\n### 结局路径\n- 主线结局\n"""

    sections = extract_markdown_sections(text)

    assert sections["故事主线推进"].startswith("- 主线推进")
    assert sections["爽点 / 卖点兑现节奏"].startswith("- 开局卖点")
    assert sections["结局路径"].startswith("- 主线结局")


def test_story_flow_validate_reports_missing_and_empty_sections():
    text = """## 故事流程稿\n### 故事主线推进\n- 主线推进\n### 故事阶段划分\n- 暂无\n"""

    ok, issues = validate_story_flow_outline(text)

    assert not ok
    assert "核心冲突升级路径" in issues
    assert "内容过短" in issues


def test_story_flow_validate_accepts_full_outline():
    text = "\n".join(
        [f"## 故事流程稿"] + [f"### {heading}\n- 测试内容 {index}" for index, heading in enumerate(STORY_FLOW_REQUIRED_HEADINGS, start=1)]
    )

    ok, issues = validate_story_flow_outline(text, min_chars=20)

    assert ok
    assert issues == []


def test_story_flow_append_missing_sections_adds_last_resort_placeholders():
    text = "## 故事流程稿\n### 故事主线推进\n- 主线推进\n"

    repaired = append_missing_story_flow_sections(text, ["故事阶段划分", "结局路径"])

    assert "### 故事阶段划分" in repaired
    assert "### 结局路径" in repaired
    assert "结构兜底占位" in repaired


def test_story_flow_empty_section_detection_ignores_placeholders():
    text = """## 故事流程稿\n### 故事主线推进\n- 待补充：结构兜底占位。\n### 故事阶段划分\n- 开局阶段：..."""

    assert not has_nonempty_story_flow_section(text, "故事主线推进")
    assert "故事主线推进" in empty_story_flow_sections(text)
    assert "故事阶段划分" in missing_story_flow_headings("## 故事流程稿")


class RepairAwareAdapter:
    def complete(self, prompt: str, project_dir, *args, **kwargs):  # noqa: ANN001
        if "AGENT: story_flow_structure_repair" in prompt:
            return build_full_story_flow_markdown()
        if "AGENT: outline_stage_synthesizer" in prompt:
            return """## 故事流程稿
### 故事主线推进
- 主角先求生。
### 故事阶段划分
- 开局和中段。
### 关键剧情节点
- 先避祸后翻盘。
"""
        if "AGENT: outline_stage_role" in prompt:
            return '{"role":"story_flow","opportunities":["推进"],"risks":["过短"],"suggestions":["补齐"]}'
        return ""


def build_full_story_flow_markdown() -> str:
    sections = {
        "故事主线推进": [
            "- 故事起点：主角重生为魔门外门弟子，先想活下来。",
            "- 终局目标：在付出代价后争得新的选择空间。",
        ],
        "故事阶段划分": [
            "- 开局阶段：建立苟活卖点。",
            "- 结局阶段：完成有限胜利。",
        ],
        "核心冲突升级路径": [
            "- 初级冲突：外门差事和资源压力。",
            "- 终极冲突：自由选择与规则吞噬对撞。",
        ],
        "关键剧情节点": [
            "- 开篇钩子：前世记忆第一次失准。",
            "- 终局对决：公开站队并撕开旧案。",
        ],
        "人物弧光嵌入流程": [
            "- 主角从自保转向承担代价。",
            "- 反派形成吞噬他人的镜像。",
        ],
        "伏笔、悬念与揭示节奏": [
            "- 核心悬念：前世记忆为何失准。",
            "- 真相揭示顺序：从小异常到旧案共犯。",
        ],
        "爽点 / 卖点兑现节奏": [
            "- 开局卖点：先手避坑。",
            "- 升级型爽点：反向逼迫阵营表态。",
        ],
        "情绪节奏与阅读体验": [
            "- 情绪曲线：轻松和高压交替。",
            "- 终局满足：有限但明确。",
        ],
        "世界观展开顺序": [
            "- 开局展示外门规则。",
            "- 后期揭示寿元债黑箱。",
        ],
        "阵营与势力推进": [
            "- 登场顺序：外门、内门、圣女线、师傅旧势力。",
            "- 主角位置：从边缘人到主动选边。",
        ],
        "代价与失败机制": [
            "- 能力代价：前世记忆会失准。",
            "- 失败节点：一次必须发生的判断失误。",
        ],
        "反转与认知升级": [
            "- 中段反转：盟友与旧案有关。",
            "- 终局反转：记忆本身可能是代价。",
        ],
        "分卷衔接方向": [
            "- 第一卷功能：入局与立卖点。",
            "- 卷尾钩子：发现记忆偏差。",
        ],
        "结局路径": [
            "- 主线结局：撕开规则黑箱。",
            "- 余味空间：新秩序仍有余波。",
        ],
    }

    lines = ["## 故事流程稿", ""]
    for heading in STORY_FLOW_REQUIRED_HEADINGS:
        lines.append(f"### {heading}")
        lines.extend(sections[heading])
        lines.append("")
    return "\n".join(lines)




def test_story_flow_stage_node_repairs_and_persists_full_outline(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.outline_stage = "story_flow"
    state.outline_stage_status = "collecting"
    state.user_request = "生成故事流程"
    state.idea = "重生魔门底层弟子，谨慎苟活"
    state.outline_stage_artifacts["direction"] = {"stage": "direction", "status": "locked", "synthesis": "低调求生，守住关键关系。"}
    state.outline_stage_artifacts["worldbuilding"] = {"stage": "worldbuilding", "status": "locked", "synthesis": "外门、执事、寿元债与黑市共同压迫底层。"}
    state.outline_stage_artifacts["characters"] = {"stage": "characters", "status": "locked", "synthesis": "师姐与师妹构成小院互保关系。"}
    store.save_state(state)

    result = NovelState.from_dict(run_outline_stage_node(state.to_dict(), RepairAwareAdapter(), store))
    story_flow = result.outline_stage_artifacts["story_flow"]["synthesis"]
    artifact_records = load_artifacts(store.project_dir("demo"))

    assert result.outline_stage == "story_flow"
    assert "故事主线推进" in story_flow
    assert "结局路径" in story_flow
    assert "故事主线推进" in result.outline_stage_artifacts["story_flow"]["summary"]
    assert any(record.type == "story_flow" and record.stage == "story_flow" and record.path == "outline/story_flow.md" for record in artifact_records)
    assert store.outline_stage_path("demo", "story_flow").exists()
    assert "故事阶段划分" in store.outline_stage_path("demo", "story_flow").read_text(encoding="utf-8")
