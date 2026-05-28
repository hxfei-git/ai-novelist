# Web Structural Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split large Web and adapter files into focused modules without changing the Web-only product behavior.

**Architecture:** This is an extraction-only refactor. Move cohesive functions into helper modules, leave public route and service names stable, add import-level and focused behavior tests after each extraction, and avoid UI redesign or workflow changes.

**Tech Stack:** FastAPI backend, pytest, Vite/React frontend, TypeScript, Python adapter classes.

---

## File Structure

- Modify: `src/ai_novelist/web/service.py`; preserve public functions used by `web/app.py` and tests.
- Create: `src/ai_novelist/web/outline_service.py` for outline stage, review baseline, stage action, and outline review helpers.
- Create if shared JSON parsing remains duplicated: `src/ai_novelist/web/json_utils.py`.
- Create: `src/ai_novelist/web/chapter_service.py` for chapter review helpers.
- Modify: `tests/test_web_service.py`; move focused tests into smaller files.
- Create: `tests/test_web_outline_service.py`.
- Create: `tests/test_web_chapter_service.py`.
- Modify: `src/ai_novelist/adapters/codex_cli.py`; keep real CLI execution and JSON event extraction.
- Create: `src/ai_novelist/adapters/mock_codex.py` for deterministic mock responses.
- Create: `tests/test_mock_codex_adapter.py`.
- Modify: `web/frontend/src/main.tsx`; extract types and API helpers first.
- Create: `web/frontend/src/types.ts`.
- Create: `web/frontend/src/api.ts`.
- Modify: `docs/IMPLEMENTATION_PLAN.md` and `docs/SESSION_SUMMARY.md`.

## Task 1: Split Mock Adapter From Real Codex Adapter

**Files:**
- Create: `src/ai_novelist/adapters/mock_codex.py`
- Modify: `src/ai_novelist/adapters/codex_cli.py`
- Modify: `src/ai_novelist/adapters/__init__.py`
- Create: `tests/test_mock_codex_adapter.py`
- Modify: `tests/test_codex_adapter.py`
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Add mock adapter tests**

Create `tests/test_mock_codex_adapter.py`:

```python
from pathlib import Path

from ai_novelist.adapters.mock_codex import MockCodexAdapter


def test_mock_codex_adapter_routes_outline_agent(tmp_path: Path) -> None:
    adapter = MockCodexAdapter()

    output = adapter.complete("AGENT: outline_planner\n写作任务", tmp_path)

    assert "方向" in output or "大纲" in output


def test_mock_codex_adapter_routes_chapter_writer(tmp_path: Path) -> None:
    adapter = MockCodexAdapter()

    output = adapter.complete("AGENT: chapter_writer\n写作任务", tmp_path)

    assert "第" in output or "章节" in output
```

- [ ] **Step 2: Run test to verify import fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_mock_codex_adapter.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'ai_novelist.adapters.mock_codex'`.

- [ ] **Step 3: Extract mock implementation**

Create `src/ai_novelist/adapters/mock_codex.py` with this header and class, then move `CodexCLIAdapter._mock_response()` and all `_mock_*` helpers from `codex_cli.py` into the class unchanged:

```python
"""Deterministic mock adapter used by tests and local Web mock mode."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_novelist.adapters.base import AgentAdapter, AgentCallOptions


@dataclass
class MockCodexAdapter(AgentAdapter):
    def complete(self, prompt: str, workspace: Path, options: AgentCallOptions | None = None) -> str:
        del workspace, options
        return self._mock_response(prompt)
```

- [ ] **Step 4: Preserve `CodexCLIAdapter(mock=True)` compatibility**

In `src/ai_novelist/adapters/codex_cli.py`, keep the `mock` constructor argument and delegate inside `complete()`:

```python
if self.mock:
    from ai_novelist.adapters.mock_codex import MockCodexAdapter

    return MockCodexAdapter().complete(prompt, workspace, options)
```

- [ ] **Step 5: Run adapter tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_codex_adapter.py tests/test_mock_codex_adapter.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add src/ai_novelist/adapters/codex_cli.py src/ai_novelist/adapters/mock_codex.py src/ai_novelist/adapters/__init__.py tests/test_codex_adapter.py tests/test_mock_codex_adapter.py docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "refactor: split mock codex adapter"
```

## Task 2: Extract Web JSON Utility

**Files:**
- Create: `src/ai_novelist/web/json_utils.py`
- Modify: `src/ai_novelist/web/service.py`
- Create: `tests/test_web_json_utils.py`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Add JSON utility tests**

Create `tests/test_web_json_utils.py`:

```python
from ai_novelist.web.json_utils import parse_json_object


def test_parse_json_object_accepts_embedded_json() -> None:
    assert parse_json_object('prefix {"status": "pass"} suffix') == {"status": "pass"}


def test_parse_json_object_returns_empty_dict_for_invalid_text() -> None:
    assert parse_json_object("not json") == {}
```

- [ ] **Step 2: Run test to verify import fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_json_utils.py -q
```

Expected: fail because `ai_novelist.web.json_utils` does not exist.

- [ ] **Step 3: Create utility module**

Create `src/ai_novelist/web/json_utils.py`:

```python
"""JSON parsing helpers for Web service agent outputs."""

from __future__ import annotations

import json
from typing import Any


def parse_json_object(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return dict(parsed) if isinstance(parsed, dict) else {}
```

- [ ] **Step 4: Use utility from service**

In `src/ai_novelist/web/service.py`, import the helper:

```python
from ai_novelist.web.json_utils import parse_json_object
```

Remove the local `parse_json_object()` function from `service.py`.

- [ ] **Step 5: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_json_utils.py tests/test_web_service.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add src/ai_novelist/web/service.py src/ai_novelist/web/json_utils.py tests/test_web_json_utils.py docs/SESSION_SUMMARY.md
git commit -m "refactor: extract web json utility"
```

## Task 3: Extract Web Outline Service Helpers

**Files:**
- Create: `src/ai_novelist/web/outline_service.py`
- Modify: `src/ai_novelist/web/service.py`
- Create: `tests/test_web_outline_service.py`
- Modify: `tests/test_web_service.py`
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Add import compatibility test**

Create `tests/test_web_outline_service.py`:

```python
from ai_novelist.web import outline_service


def test_outline_service_exports_stage_helpers() -> None:
    assert callable(outline_service.outline_stage_list)
    assert callable(outline_service.outline_stage_payload)
    assert callable(outline_service.outline_review_source_text)
```

- [ ] **Step 2: Run test to verify module is missing**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_outline_service.py -q
```

Expected: fail because `ai_novelist.web.outline_service` does not exist.

- [ ] **Step 3: Move cohesive outline helpers**

Move these functions and their direct private helpers from `src/ai_novelist/web/service.py` to `src/ai_novelist/web/outline_service.py`:

```text
outline_stage_list
outline_stage_payload
ensure_outline_stage_mutable
has_outline_stage_content
outline_review_source_text
write_outline_review_baseline_sections
collect_stage_pending_questions
outline_stage_action_state
write_outline_review_report
load_stage_markdown
```

Leave compatibility imports in `service.py`:

```python
from ai_novelist.web.outline_service import (
    collect_stage_pending_questions,
    ensure_outline_stage_mutable,
    has_outline_stage_content,
    load_stage_markdown,
    outline_review_source_text,
    outline_stage_action_state,
    outline_stage_list,
    outline_stage_payload,
    write_outline_review_baseline_sections,
    write_outline_review_report,
)
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_outline_service.py tests/test_web_service.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/ai_novelist/web/service.py src/ai_novelist/web/outline_service.py tests/test_web_outline_service.py tests/test_web_service.py docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "refactor: extract web outline service helpers"
```

## Task 4: Extract Web Chapter Service Helpers

**Files:**
- Create: `src/ai_novelist/web/chapter_service.py`
- Modify: `src/ai_novelist/web/service.py`
- Create: `tests/test_web_chapter_service.py`
- Modify: `tests/test_web_service.py`
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Add import compatibility test**

Create `tests/test_web_chapter_service.py`:

```python
from ai_novelist.web import chapter_service


def test_chapter_service_exports_review_helpers() -> None:
    assert callable(chapter_service.chapter_outline_review_source_text)
    assert callable(chapter_service.build_global_review_prompt)
```

- [ ] **Step 2: Run test to verify module is missing**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_chapter_service.py -q
```

Expected: fail because `ai_novelist.web.chapter_service` does not exist.

- [ ] **Step 3: Move cohesive chapter helpers**

Move these functions and their direct private helpers from `src/ai_novelist/web/service.py` to `src/ai_novelist/web/chapter_service.py`:

```text
chapter_outline_review_source_text
build_global_review_prompt
```

Keep `parse_json_object` imported from `ai_novelist.web.json_utils` in every module that needs it.

- [ ] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_chapter_service.py tests/test_web_service.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/ai_novelist/web/service.py src/ai_novelist/web/chapter_service.py tests/test_web_chapter_service.py tests/test_web_service.py docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "refactor: extract web chapter service helpers"
```

## Task 5: Split Broad Web Service Tests

**Files:**
- Modify: `tests/test_web_service.py`
- Modify: `tests/test_web_outline_service.py`
- Modify: `tests/test_web_chapter_service.py`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Move outline-only tests**

Move tests covering these behaviors from `tests/test_web_service.py` to `tests/test_web_outline_service.py`:

```text
outline stage list hiding review_lock
outline stage payload
pending question collection
outline review baseline/report helpers
```

- [ ] **Step 2: Move chapter-only tests**

Move tests covering these behaviors from `tests/test_web_service.py` to `tests/test_web_chapter_service.py`:

```text
chapter outline review source text
global chapter review prompt
selected repair helpers
```

- [ ] **Step 3: Run moved tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_web_service.py tests/test_web_outline_service.py tests/test_web_chapter_service.py -q
```

Expected: pass with unchanged assertions.

- [ ] **Step 4: Commit**

```bash
git add tests/test_web_service.py tests/test_web_outline_service.py tests/test_web_chapter_service.py docs/SESSION_SUMMARY.md
git commit -m "test: split web service coverage"
```

## Task 6: Extract Frontend API and Types

**Files:**
- Create: `web/frontend/src/types.ts`
- Create: `web/frontend/src/api.ts`
- Modify: `web/frontend/src/main.tsx`
- Modify: `docs/IMPLEMENTATION_PLAN.md`
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Move TypeScript types**

Move existing type aliases and interfaces from `main.tsx` into `web/frontend/src/types.ts`. Preserve field names and exported names. Start with this pattern and include every moved existing type:

```ts
export type ProjectSummary = {
  id: string
  title: string
  updated_at?: string
}
```

- [ ] **Step 2: Move API helpers**

Move fetch helpers from `main.tsx` into `web/frontend/src/api.ts`. Preserve endpoint strings and return shapes. Use this pattern for each moved function:

```ts
import type { ProjectSummary } from './types'

const API_BASE = ''

export async function apiGetProjects(): Promise<ProjectSummary[]> {
  const response = await fetch(`${API_BASE}/api/projects`)
  if (!response.ok) throw new Error(await response.text())
  return response.json()
}
```

- [ ] **Step 3: Update `main.tsx` imports**

Replace local type and API definitions with imports:

```ts
import type { ProjectSummary } from './types'
import { apiGetProjects } from './api'
```

Include every moved exported name in these import lists.

- [ ] **Step 4: Run frontend build**

Run:

```bash
npm --prefix web/frontend run build
```

Expected: pass. The known Vite CJS Node API deprecation warning may appear.

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/main.tsx web/frontend/src/api.ts web/frontend/src/types.ts docs/IMPLEMENTATION_PLAN.md docs/SESSION_SUMMARY.md
git commit -m "refactor: split frontend api and types"
```

## Task 7: Final Verification

**Files:**
- Modify: `docs/SESSION_SUMMARY.md`

- [ ] **Step 1: Run full Python suite**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected: pass.

- [ ] **Step 2: Run frontend build**

Run:

```bash
npm --prefix web/frontend run build
```

Expected: pass. The known Vite CJS Node API deprecation warning may appear.

- [ ] **Step 3: Check hotspot file sizes**

Run:

```bash
wc -l src/ai_novelist/web/service.py src/ai_novelist/adapters/codex_cli.py web/frontend/src/main.tsx tests/test_web_service.py
```

Expected: each original hotspot is materially smaller than the baseline: service 2004, adapter 1389, frontend 1475, test 1491 lines.

- [ ] **Step 4: Commit verification note**

```bash
git add docs/SESSION_SUMMARY.md
git commit -m "docs: record structural refactor verification"
```

## Self-Review

- Spec coverage: covers backend service, frontend entrypoint, broad Web tests, and mock adapter coupling.
- Placeholder scan: no prohibited placeholder text remains.
- Type consistency: exported helper and module names are introduced before use and match current service or adapter names.
