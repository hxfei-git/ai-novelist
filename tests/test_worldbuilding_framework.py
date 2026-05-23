from ai_novelist.worldbuilding_framework import (
    append_missing_worldbuilding_sections,
    full_worldbuilding_headings,
    render_worldbuilding_framework,
    validate_worldbuilding_outline,
)


def test_full_worldbuilding_framework_has_33_sections():
    headings = full_worldbuilding_headings()

    assert len(headings) == 33
    assert headings[0] == "一、世界核心设定"
    assert headings[-1] == "三十三、结局后的世界格局"


def test_render_worldbuilding_framework_contains_required_sections():
    text = render_worldbuilding_framework("full")

    for heading in ["一、世界核心设定", "七、力量体系", "二十八、核心矛盾", "三十二、隐藏真相"]:
        assert heading in text


def test_validate_worldbuilding_outline_reports_missing_headings():
    text = "## 一、世界核心设定\n- 测试"

    ok, missing = validate_worldbuilding_outline(text)

    assert not ok
    assert "二、世界格局" in missing


def test_validate_worldbuilding_outline_accepts_all_headings():
    text = "\n".join(f"## {heading}\n- 测试设定" for heading in full_worldbuilding_headings())

    ok, missing = validate_worldbuilding_outline(text)

    assert ok
    assert missing == []


def test_append_missing_worldbuilding_sections_adds_last_resort_placeholders():
    text = "## 一、世界核心设定\n- 已有设定"

    repaired = append_missing_worldbuilding_sections(text, ["二、世界格局", "三、地理与环境"])

    assert "## 一、世界核心设定" in repaired
    assert "## 二、世界格局" in repaired
    assert "## 三、地理与环境" in repaired
    assert "结构兜底占位" in repaired
