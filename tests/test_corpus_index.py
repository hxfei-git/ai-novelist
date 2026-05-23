from pathlib import Path

from ai_novelist.corpus.index import build_corpus_index, load_chunks, load_works


def test_build_corpus_index_outputs_jsonl(tmp_path):
    result = build_corpus_index(Path("tests/fixtures/corpus"), tmp_path)

    assert result.works >= 2
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "works.jsonl").exists()
    assert (tmp_path / "chapters.jsonl").exists()
    assert (tmp_path / "scenes.jsonl").exists()
    assert (tmp_path / "chunks.jsonl").exists()
    assert (tmp_path / "quality_report.md").exists()
    assert list(load_works(tmp_path))
    assert list(load_chunks(tmp_path))
