from ai_novelist.corpus.encoding import read_text_with_fallback


def test_read_text_with_utf8(tmp_path):
    path = tmp_path / "novel.txt"
    path.write_text("第一章 测试", encoding="utf-8")

    text, encoding = read_text_with_fallback(path)

    assert text == "第一章 测试"
    assert encoding == "utf-8"


def test_read_text_with_gbk(tmp_path):
    path = tmp_path / "novel.txt"
    path.write_bytes("第一章 测试".encode("gbk"))

    text, encoding = read_text_with_fallback(path)

    assert "第一章" in text
    assert encoding in {"gb18030", "gbk"}
