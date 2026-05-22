from ai_novelist.progress import with_agent_metadata


class FakeAdapter:
    model = "deepseek-v4-pro"

    def _thinking_strategy(self, agent):
        return "disabled-medium"


def test_with_agent_metadata_adds_compact_context_and_token_usage():
    message = with_agent_metadata(
        "已完成「故事概念」角色短评",
        FakeAdapter(),
        "outline_stage_role",
        elapsed_seconds=9.9,
        context_chars=12400,
        estimated_tokens=7100,
    )

    assert message == "已完成「故事概念」角色短评（deepseek-v4-pro | disabled-medium | 9.9s | ctx=6.2K/1M | tok≈7.1K）"
