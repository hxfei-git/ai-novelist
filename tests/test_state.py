from ai_novelist.state import NovelState


def test_state_round_trip():
    state = NovelState(project_id="demo", title="Demo", idea="Idea")

    loaded = NovelState.from_dict(state.to_dict())

    assert loaded == state


def test_from_dict_accepts_old_director_and_research_fields():
    data = {
        "project_id": "demo",
        "title": "Demo",
        "messages": [{"role": "user", "content": "old chat"}],
        "research_sources": [{"title": "source"}],
        "research_uncertainties": ["missing canon"],
        "director_intent": "web_research",
        "director_action": "research",
        "director_message": "old director response",
        "director_task_args": {"topic": "canon"},
        "outline_stage_artifacts": {
            "review_lock": {"stage": "review_lock", "status": "options_ready"}
        },
    }

    state = NovelState.from_dict(data)

    assert state.project_id == "demo"
    assert state.messages == [{"role": "user", "content": "old chat"}]
    assert state.research_sources == [{"title": "source"}]
    assert state.research_uncertainties == ["missing canon"]
    assert state.director_intent == "web_research"
    assert state.director_action == "research"
    assert state.director_message == "old director response"
    assert state.director_task_args == {"topic": "canon"}
    assert "review_lock" in state.outline_stage_artifacts
