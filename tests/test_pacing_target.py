from ai_novelist.pacing import (
    PacingTarget,
    allow_hook_enhance,
    parse_pacing_target_from_card,
    required_chapter_card_sections,
    scene_required_fields,
    select_chapter_agent_specs,
)


def test_quiet_chapter_uses_restraint_and_ending_resonance():
    pacing = PacingTarget(chapter=3, function="breather", intensity=2, hook_strength="soft")
    specs = select_chapter_agent_specs(pacing)
    names = [name for _, name in specs]
    assert "chapter_conflict_agent" not in names
    assert "restraint_agent" in names
    assert "chapter_hook_agent" not in names
    assert "ending_resonance_agent" in names


def test_high_intensity_keeps_conflict_and_hook_agents():
    pacing = PacingTarget(chapter=8, function="climax", intensity=5, hook_strength="hard")
    names = [name for _, name in select_chapter_agent_specs(pacing)]
    assert "chapter_conflict_agent" in names
    assert "chapter_hook_agent" in names


def test_required_sections_dynamic():
    low = PacingTarget(chapter=2, intensity=2, hook_strength="none")
    high = PacingTarget(chapter=2, intensity=4, hook_strength="hard")
    assert "关键冲突" not in required_chapter_card_sections(low)
    assert "结尾钩子" not in required_chapter_card_sections(low)
    assert "关键冲突" in required_chapter_card_sections(high)
    assert "结尾钩子" in required_chapter_card_sections(high)


def test_parse_pacing_target_from_card_extracts_guardrails():
    card = """
## 本章功能
余波章

## 目标强度
2

## 张力来源
信息不对称

## 结尾方式
软收束

## 禁止升级项
不得新增冲突；不得大反转

## 延后信息
终局真相
"""
    target = parse_pacing_target_from_card(5, card)
    assert target.function == "aftermath"
    assert target.intensity == 2
    assert target.hook_strength in {"none", "soft"}
    assert any("不得新增冲突" in item for item in target.must_not or [])


def test_scene_required_fields_follow_intensity():
    low = PacingTarget(chapter=1, intensity=2)
    high = PacingTarget(chapter=1, intensity=4)
    assert "冲突对象" not in scene_required_fields(low)
    assert "场景转折" not in scene_required_fields(low)
    assert "冲突对象" in scene_required_fields(high)
    assert "场景转折" in scene_required_fields(high)


def test_allow_hook_enhance_depends_on_target():
    assert allow_hook_enhance(PacingTarget(chapter=1, intensity=5, hook_strength="hard"))
    assert not allow_hook_enhance(PacingTarget(chapter=1, intensity=2, hook_strength="none"))
