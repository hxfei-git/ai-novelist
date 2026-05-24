"""Filter stage confirmation questions to avoid invented choice menus."""

from __future__ import annotations

import re

from ai_novelist.outline.source_ledger import build_source_ledger, looks_like_concrete_canon
from ai_novelist.outline.stage_contracts import get_stage_contract
from ai_novelist.state import NovelState


def filter_stage_confirmation_questions(stage: str, questions: list[str], state: NovelState, synthesis: str = "") -> list[str]:
    del synthesis
    ledger = build_source_ledger(state)
    filtered: list[str] = []
    for question in questions:
        q = str(question).strip()
        if not q:
            continue
        if _looks_like_model_choice_menu(q) and not ledger.has_explicit_source(q):
            if stage == "worldbuilding" and _looks_like_memory_cost_question(q):
                q = "是否需要为前世记忆设置明确限制；若暂不确认，可先按“记忆不完整且会失准”处理？"
            else:
                continue
        if looks_like_concrete_canon(q) and not ledger.has_explicit_source(q):
            if stage == "direction":
                continue
            if stage == "worldbuilding":
                q = "该具体设定缺少来源，是否先保留为待确认项？"
        if q not in filtered:
            filtered.append(q)
    try:
        max_questions = get_stage_contract(stage).max_questions
    except KeyError:
        max_questions = 1 if stage == "direction" else 3
    return filtered[:max_questions]


def _looks_like_model_choice_menu(question: str) -> bool:
    if "还是" not in question:
        return False
    concrete = looks_like_concrete_canon(question)
    options = re.split(r"还是|或是|或者|/|／", question)
    rich_options = [item.strip(" ：:，,。?？") for item in options if len(item.strip()) >= 3]
    return concrete and len(rich_options) >= 2


def _looks_like_memory_cost_question(question: str) -> bool:
    markers = ("前世记忆", "代价", "寿命", "生命力", "情感", "羁绊")
    return any(marker in question for marker in markers)
