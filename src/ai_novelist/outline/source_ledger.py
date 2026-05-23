"""Source ledger for canon provenance checks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from ai_novelist.state import NovelState


class SourceLevel(str, Enum):
    USER_EXPLICIT = "user_explicit"
    LOCKED_STAGE = "locked_stage"
    REFERENCE_BRIEF = "reference_brief"
    CURRENT_DRAFT = "current_draft"
    MODEL_UNSUPPORTED = "model_unsupported"


@dataclass(frozen=True)
class SourceHit:
    level: SourceLevel
    source: str
    excerpt: str


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


class SourceLedger:
    def __init__(self, hits: list[SourceHit]) -> None:
        self.hits = [hit for hit in hits if normalize_text(hit.excerpt)]

    def has_explicit_source(self, text: str) -> bool:
        hit = self.find_source(text)
        return bool(hit and hit.level != SourceLevel.MODEL_UNSUPPORTED)

    def find_source(self, text: str) -> SourceHit | None:
        target = normalize_text(text)
        if not target:
            return None
        for hit in self.hits:
            source_text = normalize_text(hit.excerpt)
            if not source_text:
                continue
            if target in source_text or source_text in target:
                return hit
            if _token_overlap(target, source_text):
                return hit
        return None

    def is_user_requested(self, text: str) -> bool:
        target = normalize_text(text)
        if not target:
            return False
        for hit in self.hits:
            if hit.level != SourceLevel.USER_EXPLICIT:
                continue
            source_text = normalize_text(hit.excerpt)
            if target in source_text or source_text in target or _token_overlap(target, source_text):
                return True
        return False


def build_source_ledger(state: NovelState) -> SourceLedger:
    hits: list[SourceHit] = []
    user_sources = [
        state.idea,
        state.user_request,
        state.last_user_feedback,
        *state.locked_constraints,
        *(msg.get("content", "") for msg in state.messages if msg.get("role") == "user"),
    ]
    for excerpt in user_sources:
        text = normalize_text(str(excerpt))
        if text:
            hits.append(SourceHit(SourceLevel.USER_EXPLICIT, "user", text))

    for stage, artifact in state.outline_stage_artifacts.items():
        if not isinstance(artifact, dict):
            continue
        if str(artifact.get("status", "")) != "locked":
            continue
        synthesis = normalize_text(str(artifact.get("synthesis", "")))
        summary = normalize_text(str(artifact.get("summary", "")))
        memory = artifact.get("stage_memory")
        for text in (synthesis, summary):
            if text:
                hits.append(SourceHit(SourceLevel.LOCKED_STAGE, f"outline:{stage}", text))
        if isinstance(memory, list):
            for item in memory:
                value = normalize_text(str(item))
                if value:
                    hits.append(SourceHit(SourceLevel.LOCKED_STAGE, f"outline:{stage}", value))

    for source, excerpt in (
        ("reference_brief", state.reference_brief),
        ("retrieval_context", state.retrieval_context),
    ):
        text = normalize_text(excerpt)
        if text:
            hits.append(SourceHit(SourceLevel.REFERENCE_BRIEF, source, text))

    current = state.outline_stage_artifacts.get(state.outline_stage)
    if isinstance(current, dict):
        synthesis = normalize_text(str(current.get("synthesis", "")))
        if synthesis:
            hits.append(SourceHit(SourceLevel.CURRENT_DRAFT, f"draft:{state.outline_stage}", synthesis))
    return SourceLedger(hits)


CONCRETE_CANON_KEYWORDS = (
    "寿元",
    "生命力",
    "情感纽带",
    "羁绊",
    "债",
    "魔痕",
    "灵魂",
    "记忆损耗",
    "反噬",
    "阈值",
    "倒计时",
    "不可逆",
    "积分",
    "等级",
    "机制",
    "系统",
    "规则",
    "模型",
    "结构",
    "变量",
    "红线",
    "抵押",
)

ORG_SUFFIX_PATTERN = re.compile(r"[\u4e00-\u9fff]{1,8}(宗|门|堂|阁|司|会|城|院|榜|令|契|册)")
NUMERIC_RULE_PATTERN = re.compile(r"(第?\d+次|次数|阈值|等级|积分|倒计时|不可逆)")


def looks_like_concrete_canon(text: str) -> bool:
    value = normalize_text(text)
    if not value:
        return False
    if ORG_SUFFIX_PATTERN.search(value):
        return True
    if NUMERIC_RULE_PATTERN.search(value):
        return True
    return any(token in value for token in CONCRETE_CANON_KEYWORDS)


def _token_overlap(a: str, b: str) -> bool:
    tokens_a = {item for item in re.split(r"[，。；：、,.!?？\s]+", a) if len(item) >= 2}
    tokens_b = {item for item in re.split(r"[，。；：、,.!?？\s]+", b) if len(item) >= 2}
    if not tokens_a or not tokens_b:
        return False
    overlap = tokens_a & tokens_b
    return len(overlap) >= 2 or any(token in b for token in tokens_a)
