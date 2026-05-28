from ai_novelist.state import NovelState
from ai_novelist.workflow_payloads import (
    chapter_batch_payload,
    get_task_arg_int,
    get_task_arg_str,
    set_chapter_batch_payload,
    set_task_arg,
)


def test_task_arg_helpers_normalize_values() -> None:
    state = NovelState(project_id="demo", title="Demo")
    set_task_arg(state, "chapter", 3)
    set_task_arg(state, "notes", "  revise  ")

    assert get_task_arg_int(state, "chapter", 1) == 3
    assert get_task_arg_str(state, "notes") == "revise"
    assert get_task_arg_int(state, "missing", 7) == 7


def test_chapter_batch_payload_round_trip() -> None:
    state = NovelState(project_id="demo", title="Demo")

    set_chapter_batch_payload(state, volume=2, requested_count=3, chapters=[4, 5, 6])
    payload = chapter_batch_payload(state)

    assert payload.volume == 2
    assert payload.requested_count == 3
    assert payload.chapters == [4, 5, 6]
    assert state.director_task_args["chapters"] == "4,5,6"
