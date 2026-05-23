from pathlib import Path

from ai_novelist.corpus.craft_extractor import extract_craft_profiles
from ai_novelist.corpus.index import build_corpus_index, load_profiles


def test_extract_craft_profiles_mock(tmp_path):
    build_corpus_index(Path("tests/fixtures/corpus"), tmp_path)

    result = extract_craft_profiles(tmp_path, mock=True)

    assert result.work_profiles >= 2
    assert result.chapter_profiles >= 1
    assert result.scene_profiles >= 1
    assert (tmp_path / "craft_profiles" / "works").exists()
    profiles = list(load_profiles(tmp_path))
    assert profiles
    assert all("门禁系统显示" not in note.pattern for profile in profiles for note in profile.notes)
