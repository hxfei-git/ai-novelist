from ai_novelist.corpus.craft_query_planner import plan_craft_query
from ai_novelist.state import NovelState


def test_query_planner_maps_purpose_to_facets():
    state = NovelState(project_id="demo", title="Demo", idea="悬疑科幻")
    state.craft_mode = "assist"

    query = plan_craft_query(state, None, "chapter_planning", chapter=1)

    assert "chapter_hook" in query.facets
    assert "pacing" in query.facets
    assert query.intensity == 3


def test_low_intensity_boosts_restraint():
    state = NovelState(project_id="demo", title="Demo")
    state.craft_mode = "assist"

    query = plan_craft_query(state, None, "chapter_planning", chapter=1, pacing_target={"function": "aftermath", "intensity": 1})

    assert query.facets[0] == "restraint"
    assert query.intensity == 1
