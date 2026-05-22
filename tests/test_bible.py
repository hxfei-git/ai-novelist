from ai_novelist.bible import (
    CharacterCard,
    NovelBible,
    WorldRule,
    bible_from_dict,
    detect_bible_conflicts,
    load_bible,
    merge_bible_updates,
    render_bible_markdown,
    save_bible,
)


def test_load_empty_bible(tmp_path):
    bible = load_bible(tmp_path)

    assert isinstance(bible, NovelBible)
    assert bible.version == 1


def test_save_and_load_bible(tmp_path):
    bible = NovelBible()
    bible.project.title = "月城手稿"
    bible.characters.append(CharacterCard(name="林澈", role="主角"))

    save_bible(tmp_path, bible)
    loaded = load_bible(tmp_path)

    assert loaded.project.title == "月城手稿"
    assert loaded.characters[0].name == "林澈"
    assert (tmp_path / "novel_bible.json").exists()
    assert (tmp_path / "novel_bible.md").exists()


def test_render_bible_markdown():
    bible = NovelBible()
    bible.project.title = "月城手稿"
    bible.concept.logline = "失忆工程师追查自己的罪。"

    markdown = render_bible_markdown(bible)

    assert "# 小说圣经" in markdown
    assert "月城手稿" in markdown
    assert "失忆工程师" in markdown


def test_merge_bible_updates():
    bible = NovelBible()
    bible.characters.append(CharacterCard(name="林澈", role="主角"))

    merged = merge_bible_updates(
        bible,
        {
            "project": {"title": "月城手稿"},
            "characters": [{"name": "林澈", "identity": "记忆工程师"}],
            "world_rules": [{"name": "记忆审计", "description": "记忆可被编号追踪。"}],
            "chapter_summaries": {"1": "主角醒来。"},
        },
    )

    assert merged.version == 2
    assert merged.project.title == "月城手稿"
    assert merged.characters[0].role == "主角"
    assert merged.characters[0].identity == "记忆工程师"
    assert merged.world_rules[0].name == "记忆审计"
    assert merged.chapter_summaries["1"] == "主角醒来。"


def test_detect_bible_conflicts():
    bible = NovelBible(
        characters=[CharacterCard(name="林澈", role="主角")],
        world_rules=[WorldRule(name="记忆审计", description="记忆只能读取编号。")],
        chapter_summaries={"1": "主角醒来。"},
    )

    conflicts = detect_bible_conflicts(
        bible,
        {
            "characters": [{"name": "林澈", "role": "反派"}],
            "world_rules": [{"name": "记忆审计", "description": "记忆可以随意重写。"}],
            "chapter_summaries": {"1": "主角已经破案。"},
        },
    )

    assert {item["type"] for item in conflicts} == {"character_role", "world_rule", "chapter_summary"}


def test_bible_from_dict_tolerates_missing_fields():
    bible = bible_from_dict({"project": {"title": "Demo"}})

    assert bible.project.title == "Demo"
    assert bible.characters == []
