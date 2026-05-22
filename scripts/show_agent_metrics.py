#!/usr/bin/env python3
"""Show recorded agent metrics for a project."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Show ai-novelist agent metrics.")
    parser.add_argument("--project", required=True, help="Project id under projects/")
    parser.add_argument("--root", default="projects", help="Projects root directory")
    parser.add_argument("--top", choices=["prompt_chars", "output_chars", "elapsed_ms"], default="elapsed_ms")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    path = Path(args.root) / args.project / "debug" / "agent_runs.jsonl"
    if not path.exists():
        print(f"No agent metrics found: {path}")
        return 1

    rows = load_rows(path)
    rows.sort(key=lambda item: int(item.get(args.top) or 0), reverse=True)
    print("graph node agent prompt_chars output_chars elapsed_ms status prompt_profile")
    for row in rows[: max(1, args.limit)]:
        print(
            f"{row.get('graph', '')} "
            f"{row.get('node', '')} "
            f"{row.get('agent', '')} "
            f"{row.get('prompt_chars', 0)} "
            f"{row.get('output_chars', 0)} "
            f"{row.get('elapsed_ms', 0)} "
            f"{row.get('status', '')} "
            f"{row.get('prompt_profile') or ''}"
        )
    return 0


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            rows.append(data)
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
