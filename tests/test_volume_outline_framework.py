from ai_novelist.volume_outline_framework import render_volume_outline_framework, volume_outline_required_headings


def test_volume_outline_framework_declares_fourteen_core_modules():
    headings = volume_outline_required_headings()

    assert len(headings) == 14
    assert headings == (
        "分卷总体规划",
        "单卷基础定位",
        "本卷一句话概括",
        "本卷阶段目标",
        "本卷核心冲突",
        "本卷剧情推进",
        "本卷关键节点",
        "本卷人物推进",
        "本卷世界观释放",
        "本卷爽点与卖点兑现",
        "本卷伏笔、悬念与信息差",
        "本卷情绪节奏",
        "本卷开头与结尾",
        "与前后卷的衔接",
    )


def test_volume_outline_framework_sets_volume_level_boundaries():
    prompt = render_volume_outline_framework()

    for heading in volume_outline_required_headings():
        assert heading in prompt
    assert "本阶段产物是卷级蓝图" in prompt
    assert "不要写逐章细纲" in prompt
    assert "不要替代 chapter_outline" in prompt
    assert "未确认信息写成候选方向" in prompt
    assert "仍需确认的问题`，但最多 10 条" in prompt
    assert "卷级约束只在确有必要时附加" in prompt
