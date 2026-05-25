from ai_novelist.adapters.codex_cli import CodexCLIAdapter
from ai_novelist.graph_outline import ensure_volume_outline_structure
from ai_novelist.outline.volume_outline_structure import (
    append_missing_volume_outline_sections,
    canonical_volume_outline_heading,
    extract_volume_outline_memory,
    summarize_volume_outline,
    validate_volume_outline,
)
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore
from ai_novelist.volume_outline_framework import volume_outline_required_headings


OLD_SHORT_VOLUME_OUTLINE = """## 分卷大纲稿
### 分卷结构
- 第一卷：外门求生与线索起点。
- 第二卷：门内博弈与资源反制。
- 第三卷：真相揭示与立场决断。

### 卷目标
- 主角从求生推进到识破旧案。

### 卷级高潮
- 第三卷公开关键身份。

### 卷间钩子
- 更高层势力注意到主角。

## 仍需确认的问题
- 是否采用三卷结构作为当前基准？
"""


def test_volume_outline_aliases_map_legacy_short_sections():
    assert canonical_volume_outline_heading("分卷结构") == "分卷总体规划"
    assert canonical_volume_outline_heading("卷目标") == "本卷阶段目标"
    assert canonical_volume_outline_heading("卷级高潮") == "本卷关键节点"
    assert canonical_volume_outline_heading("卷间钩子") == "与前后卷的衔接"


def test_append_missing_volume_outline_sections_fills_core_modules():
    repaired = append_missing_volume_outline_sections(OLD_SHORT_VOLUME_OUTLINE)

    for heading in volume_outline_required_headings():
        assert f"### {heading}" in repaired
    assert "第一卷：外门求生与线索起点" in repaired
    ok, issues = validate_volume_outline(repaired, min_chars=0)
    assert ok, issues


def test_validate_volume_outline_rejects_chapter_lists():
    outline = append_missing_volume_outline_sections(OLD_SHORT_VOLUME_OUTLINE)
    outline += "\n- 第 1 章：开场。\n- 第 2 章：冲突。\n- 第 3 章：反转。\n"

    ok, issues = validate_volume_outline(outline)

    assert not ok
    assert "疑似逐章列表" in issues


def test_volume_outline_summary_and_memory_prefer_blueprint_sections():
    repaired = append_missing_volume_outline_sections(OLD_SHORT_VOLUME_OUTLINE)

    summary = summarize_volume_outline(repaired)
    memory = extract_volume_outline_memory(repaired)

    assert "分卷总体规划" in summary
    assert "本卷阶段目标" in summary
    assert any(item.startswith("本卷阶段目标：") for item in memory)
    assert any(item.startswith("与前后卷的衔接：") for item in memory)


def test_ensure_volume_outline_structure_repairs_mock_output(tmp_path):
    store = LocalStore(tmp_path)
    state = store.create_project("Demo", "demo")
    state.outline_stage_artifacts["direction"] = {"stage": "direction", "status": "locked", "synthesis": "低调求生追查真相。"}
    state.outline_stage_artifacts["worldbuilding"] = {"stage": "worldbuilding", "status": "locked", "synthesis": "外门资源压迫与寿元代价。"}
    state.outline_stage_artifacts["characters"] = {"stage": "characters", "status": "locked", "synthesis": "师姐隐瞒旧案证据。"}
    state.outline_stage_artifacts["story_flow"] = {"stage": "story_flow", "status": "locked", "synthesis": "主线从求生推进到公开旧案。"}

    repaired = ensure_volume_outline_structure(
        OLD_SHORT_VOLUME_OUTLINE,
        state,
        CodexCLIAdapter(mock=True),
        store,
        author_craft="保持卷级弹性，不硬锁死卷数。",
        role_reviews=[{"role": "分卷架构 Agent", "content": "补齐卷级蓝图。"}],
    )

    ok, issues = validate_volume_outline(repaired)
    assert ok, issues
    assert "### 分卷总体规划" in repaired
    assert "### 本卷剧情推进" in repaired
    assert "## 卷级约束与待确认项（可选）" in repaired
