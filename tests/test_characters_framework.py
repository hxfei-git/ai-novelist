from ai_novelist.characters_framework import (
    append_missing_characters_sections,
    extract_characters_memory,
    full_characters_headings,
    render_characters_framework,
    summarize_characters_outline,
    validate_characters_outline,
)


def test_full_characters_framework_has_plan_sections():
    headings = full_characters_headings()

    assert len(headings) == 14
    assert headings[0] == "人物关系稿"
    assert headings[-1] == "十三、待确认问题"
    assert "四、核心人物关系卡" in headings
    assert "七、秘密与信息差网络" in headings


def test_render_characters_framework_contains_relationship_blueprint_rules():
    text = render_characters_framework("full")

    assert "全文人物关系蓝图" in text
    assert "作者侧真相" in text
    assert "角色侧认知" in text
    assert "读者侧认知" in text
    assert "阵营 / 组织关系" in text


def test_validate_characters_outline_reports_missing_headings():
    text = "## 人物关系稿\n- 测试"

    ok, missing = validate_characters_outline(text)

    assert not ok
    assert "一、全角色总表" in missing


def test_validate_characters_outline_accepts_all_headings():
    text = "\n".join(f"## {heading}\n- 测试关系设定" for heading in full_characters_headings())

    ok, missing = validate_characters_outline(text)

    assert ok
    assert missing == []


def test_append_missing_characters_sections_adds_last_resort_placeholders():
    text = "## 人物关系稿\n- 已有关系蓝图"

    repaired = append_missing_characters_sections(text, ["一、全角色总表", "二、角色个人驱动力"])

    assert "## 人物关系稿" in repaired
    assert "## 一、全角色总表" in repaired
    assert "## 二、角色个人驱动力" in repaired
    assert "结构兜底占位" in repaired


def test_characters_summary_and_memory_prioritize_relationship_sections():
    text = """## 人物关系稿
- 全文围绕主角从不信任到主动结盟展开。

## 一、全角色总表
- C001｜主角｜A 级核心。

## 二、角色个人驱动力
- 主角当前目标是外门求生。

## 三、主角关系弧光
- 主角终局学会公开信任。

## 四、核心人物关系卡
- R001 主角-师姐从互疑到互保。

## 五、关系演化时间轴
- R001 开局互疑，中期决裂，后期重盟。

## 六、读者认知进度表
- K001 读者中期知道师姐隐瞒证据。

## 七、秘密与信息差网络
- S001 师傅吞噬旧案影响主角和师姐。

## 八、阵营 / 组织关系
- G001 来自 worldbuilding 的外门结构。

## 九、关系冲突类型
- R001 信息冲突。

## 十、关系事件种子
- E001 被迫互保。

## 十一、角色退场与关系遗产
- 执事失势后留下账册。

## 十二、锁定项与可变项
- locked：R001 必须从互疑到互保。

## 十三、待确认问题
- 暂无，当前阶段可继续修改或确认进入下一阶段。
"""

    summary = summarize_characters_outline(text)
    memory = extract_characters_memory(text)

    assert "人物关系稿：全文围绕主角" in summary
    assert any("核心人物关系卡" in item and "R001" in item for item in memory)
