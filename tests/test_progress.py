from ai_novelist.progress import with_agent_metadata


class FakeAdapter:
    model = "deepseek-v4-flash"

    def _thinking_strategy(self, agent):
        return "disabled-low"


def test_with_agent_metadata_adds_compact_context_and_token_usage():
    message = with_agent_metadata(
        "已完成「故事概念」角色短评",
        FakeAdapter(),
        "outline_stage_role",
        elapsed_seconds=9.9,
        context_chars=12400,
        estimated_tokens=7100,
    )

    assert message == "已完成「故事概念」角色短评（deepseek-v4-flash | disabled-low | 9.9s | ctx=6.2K/1M | tok≈7.1K）"


class FakeCodexAdapter:
    codex_bin = "codex"


def test_with_agent_metadata_uses_codex_context_capacity():
    message = with_agent_metadata(
        "已完成「世界观设定」角色短评",
        FakeCodexAdapter(),
        "outline_stage_role",
        elapsed_seconds=1.0,
        context_chars=5400,
        estimated_tokens=1000,
    )

    assert message == "已完成「世界观设定」角色短评（codex | cli-default | 1.0s | ctx=2.7K/258K | tok≈1.0K）"
