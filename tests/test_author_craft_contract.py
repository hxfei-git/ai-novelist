from pathlib import Path


def test_author_craft_policy_contains_contract_terms():
    policy = Path("src/ai_novelist/prompts/partials/author_craft_policy.md").read_text(encoding="utf-8")

    assert "复刻本地小说原文" in policy
    assert "模仿某个具体作者" in policy
    assert "Pacing Target" in policy


def test_author_craft_contract_doc_exists():
    contract = Path("docs/author_craft_contract.md")

    assert contract.exists()
    assert "不复刻原文" in contract.read_text(encoding="utf-8")
