from ai_novelist.artifacts import (
    ArtifactRecord,
    get_latest_artifact,
    load_artifact_text,
    load_artifacts,
    register_artifact,
    save_json_artifact,
    save_markdown_artifact,
)


def test_load_empty_artifact_registry(tmp_path):
    assert load_artifacts(tmp_path) == []


def test_save_markdown_artifact(tmp_path):
    record = save_markdown_artifact(
        tmp_path,
        "outline/direction.md",
        "# 方向定位",
        "direction",
        stage="direction",
        source_agent="test",
    )

    assert record.type == "direction"
    assert record.path == "outline/direction.md"
    assert record.version == 1
    assert (tmp_path / "outline" / "direction.md").read_text(encoding="utf-8") == "# 方向定位\n"
    assert load_artifact_text(tmp_path, record) == "# 方向定位\n"


def test_save_json_artifact(tmp_path):
    record = save_json_artifact(
        tmp_path,
        "chapters/chapter_001/review_v1.json",
        {"decision": "revise"},
        "review_report",
        chapter=1,
    )

    assert record.chapter == 1
    assert '"decision": "revise"' in load_artifact_text(tmp_path, record)


def test_get_latest_artifact(tmp_path):
    save_markdown_artifact(tmp_path, "chapters/chapter_001/draft_v1.md", "v1", "chapter_draft", chapter=1)
    latest = save_markdown_artifact(tmp_path, "chapters/chapter_001/draft_v1.md", "v2", "chapter_draft", chapter=1)

    found = get_latest_artifact(tmp_path, "chapter_draft", chapter=1)

    assert found == latest
    assert found.version == 2


def test_register_artifact_increments_version(tmp_path):
    first = register_artifact(
        tmp_path,
        ArtifactRecord(id="", type="novel_bible", path="novel_bible.md"),
    )
    second = register_artifact(
        tmp_path,
        ArtifactRecord(id="", type="novel_bible", path="novel_bible.md"),
    )

    assert first.version == 1
    assert second.version == 2
    assert [item.version for item in load_artifacts(tmp_path)] == [1, 2]


def test_register_artifact_dedupes_same_content_digest(tmp_path):
    first = save_markdown_artifact(tmp_path, "a.md", "same", "chapter_card", chapter=1)
    second = save_markdown_artifact(tmp_path, "a.md", "same", "chapter_card", chapter=1)
    records = load_artifacts(tmp_path)

    assert first.id == second.id
    assert len([item for item in records if item.type == "chapter_card"]) == 1
    assert records[0].sha256
    assert records[0].chars > 0
