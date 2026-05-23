from ai_novelist.corpus.models import RetrievalChunk
from ai_novelist.corpus.similarity_guard import check_similarity, longest_common_substring, overlap_score


def test_longest_common_substring_detects_copy():
    copied = "这是一个非常明显的连续复制片段" * 10

    assert longest_common_substring(copied, copied) > 120


def test_similarity_guard_high_for_obvious_copy():
    source = "这是一个非常明显的连续复制片段" * 8
    chunk = RetrievalChunk(
        chunk_id="c1",
        work_id="w1",
        chapter_id="ch1",
        scene_id="sc1",
        chunk_index=1,
        text=source,
        char_start=0,
        char_end=len(source),
        chapter_index=1,
        chapter_title="第一章",
        position="scene_full",
    )

    report = check_similarity(source, [chunk], project_id="demo", chapter=1)

    assert report.risk == "high"
    assert report.matched_sources


def test_similarity_guard_low_for_original_text():
    source = "这是一个非常明显的连续复制片段" * 8
    generated = "完全不同的原创章节，讨论月球城市中的身份权限和维修行动。"
    chunk = RetrievalChunk(
        chunk_id="c1",
        work_id="w1",
        chapter_id="ch1",
        scene_id="sc1",
        chunk_index=1,
        text=source,
        char_start=0,
        char_end=len(source),
        chapter_index=1,
        chapter_title="第一章",
        position="scene_full",
    )

    report = check_similarity(generated, [chunk], project_id="demo", chapter=1)

    assert report.risk == "low"
    assert overlap_score(generated, source) < 0.22
