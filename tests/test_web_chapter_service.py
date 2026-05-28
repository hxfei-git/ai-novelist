from ai_novelist.web import chapter_service


def test_chapter_service_exports_review_helpers() -> None:
    assert callable(chapter_service.chapter_outline_review_source_text)
    assert callable(chapter_service.build_global_review_prompt)
