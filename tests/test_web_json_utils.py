from ai_novelist.web.json_utils import parse_json_object


def test_parse_json_object_accepts_embedded_json() -> None:
    assert parse_json_object('prefix {"status": "pass"} suffix') == {"status": "pass"}


def test_parse_json_object_returns_empty_dict_for_invalid_text() -> None:
    assert parse_json_object("not json") == {}
