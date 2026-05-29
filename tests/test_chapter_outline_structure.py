from ai_novelist.outline.chapter_outline_structure import extract_chapter_outline_slice


def test_extract_chapter_outline_slice_stops_plain_chinese_heading_at_next_chapter() -> None:
    outline = """## 第一卷

第六章：只给第六章
第六章相邻大纲内容。

第七章：目标章
第七章专属大纲内容。

第八章：只给第八章
第八章相邻大纲内容。
"""

    result = extract_chapter_outline_slice(outline, 7)

    assert "第七章：目标章" in result
    assert "第七章专属大纲内容" in result
    assert "第六章：只给第六章" not in result
    assert "第六章相邻大纲内容" not in result
    assert "第八章：只给第八章" not in result
    assert "第八章相邻大纲内容" not in result


def test_extract_chapter_outline_slice_stops_plain_arabic_heading_at_next_chapter() -> None:
    outline = """## 第一卷

第 6 章：只给第六章
第六章相邻大纲内容。

第 7 章：目标章
第七章专属大纲内容。

第 8 章：只给第八章
第八章相邻大纲内容。
"""

    result = extract_chapter_outline_slice(outline, 7)

    assert "第 7 章：目标章" in result
    assert "第七章专属大纲内容" in result
    assert "第 6 章：只给第六章" not in result
    assert "第六章相邻大纲内容" not in result
    assert "第 8 章：只给第八章" not in result
    assert "第八章相邻大纲内容" not in result


def test_extract_chapter_outline_slice_stops_no_space_markdown_heading_at_next_chapter() -> None:
    outline = """## 第一卷

###第6章：只给第六章
第六章相邻大纲内容。

###第7章：目标章
第七章专属大纲内容。

###第8章：只给第八章
第八章相邻大纲内容。
"""

    result = extract_chapter_outline_slice(outline, 7)

    assert "###第7章：目标章" in result
    assert "第七章专属大纲内容" in result
    assert "###第6章：只给第六章" not in result
    assert "第六章相邻大纲内容" not in result
    assert "###第8章：只给第八章" not in result
    assert "第八章相邻大纲内容" not in result
