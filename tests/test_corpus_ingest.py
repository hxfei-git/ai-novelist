from pathlib import Path

from ai_novelist.corpus.ingest import scan_corpus


def test_scan_corpus_reads_txt_and_meta():
    files = scan_corpus(Path("tests/fixtures/corpus"))

    assert len(files) >= 2
    first = next(item for item in files if item.relative_path == "mock_novel_a.txt")
    assert first.metadata["title"] == "示例小说A"
    assert first.work_id.startswith("work_")
