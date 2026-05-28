from ai_novelist.web import outline_service


def test_outline_service_exports_stage_helpers() -> None:
    assert callable(outline_service.outline_stage_list)
    assert callable(outline_service.outline_stage_payload)
    assert callable(outline_service.outline_review_source_text)
