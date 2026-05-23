from ai_novelist.corpus.chunker import chunk_scene, split_chapters, split_scenes


def test_split_chapters_detects_chinese_headings():
    text = "第一章 开端\n内容\n第二章 后续\n内容"

    chapters = split_chapters(text)

    assert len(chapters) == 2
    assert chapters[0].title == "第一章 开端"


def test_split_scenes_and_chunks():
    text = "第一场内容\n\n***\n\n第二场内容"

    scenes = split_scenes(text)
    chunks = chunk_scene(text, target_chars=10, overlap_chars=2, min_chunk_chars=4, max_chunk_chars=12)

    assert len(scenes) >= 2
    assert chunks
