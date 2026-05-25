from ai_novelist.story_flow_framework import render_story_flow_framework, story_flow_required_headings


def test_story_flow_framework_renders_required_headings():
    text = render_story_flow_framework()

    for heading in story_flow_required_headings():
        assert heading in text
    assert len(story_flow_required_headings()) == 14
    assert "不是章节大纲" in text
    assert "未锁定" in text


def test_story_flow_framework_declares_generation_boundaries():
    text = render_story_flow_framework()

    assert "不要直接写章节正文" in text
    assert "不要生成逐章列表" in text
    assert "不要替代 volume_outline" in text
    assert "候选方向" in text
