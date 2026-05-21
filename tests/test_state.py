from ai_novelist.state import NovelState


def test_state_round_trip():
    state = NovelState(project_id="demo", title="Demo", idea="Idea")

    loaded = NovelState.from_dict(state.to_dict())

    assert loaded == state
