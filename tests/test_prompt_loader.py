from ai_novelist.prompts import load_prompt


def test_load_prompt_from_package():
    assert "AGENT: world_builder" in load_prompt("world_builder")
