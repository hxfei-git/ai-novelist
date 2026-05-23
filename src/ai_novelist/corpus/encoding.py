"""Encoding helpers for local author corpora."""

from __future__ import annotations

from pathlib import Path

SUPPORTED_ENCODINGS = ("utf-8", "utf-8-sig", "gb18030", "gbk")


def read_text_with_fallback(path: Path) -> tuple[str, str]:
    """Read a text file using the supported encoding fallback order."""
    raw = path.read_bytes()
    errors: list[str] = []
    for encoding in SUPPORTED_ENCODINGS:
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError as exc:
            errors.append(f"{encoding}: {exc}")
    raise UnicodeDecodeError("author-corpus", raw, 0, min(len(raw), 1), "; ".join(errors))
