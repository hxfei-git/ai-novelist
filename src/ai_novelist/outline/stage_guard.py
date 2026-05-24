"""Quality guard for outline stage outputs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ai_novelist.outline.source_ledger import SourceLedger, build_source_ledger, looks_like_concrete_canon
from ai_novelist.outline.stage_contracts import StageContract, get_stage_contract
from ai_novelist.state import NovelState

UNIVERSAL_MARKERS = ("每一次", "每次", "任何", "所有", "一旦", "只要", "凡是", "无论")
INEVITABILITY_MARKERS = ("必然", "必定", "都会", "就会", "都是", "从来", "永远", "注定", "有债必偿")
WORLD_ABSTRACT_MARKERS = ("机制", "系统", "模型", "结构", "变量", "阈值", "红线", "抵押", "闭环", "反馈")


@dataclass
class GuardIssue:
    code: str
    severity: str
    message: str
    excerpt: str = ""


@dataclass
class GuardResult:
    text: str
    issues: list[GuardIssue] = field(default_factory=list)


def guard_stage_output(text: str, stage: str, state: NovelState) -> GuardResult:
    source_ledger = build_source_ledger(state)
    contract = get_stage_contract(stage)
    issues: list[GuardIssue] = []
    issues.extend(detect_stage_overreach(text, contract))
    issues.extend(detect_unsupported_canon(text, stage, source_ledger, contract))
    issues.extend(detect_formulaic_causality(text))
    issues.extend(detect_non_worldbuilding_language(text, stage))
    rewritten = rewrite_or_demote_issues(text, issues, stage, source_ledger)
    return GuardResult(text=rewritten, issues=issues)


def detect_stage_overreach(text: str, contract: StageContract) -> list[GuardIssue]:
    issues: list[GuardIssue] = []
    content = text or ""
    for item in contract.forbidden_intents:
        if item and item in content:
            issues.append(GuardIssue("stage_overreach", "warning", f"命中阶段禁区：{item}", item))
    if contract.key == "direction":
        if looks_like_concrete_canon(content):
            issues.append(GuardIssue("direction_concrete_canon", "rewrite", "方向阶段不应细化具体 canon", content[:80]))
    return issues


def detect_unsupported_canon(text: str, stage: str, ledger: SourceLedger, contract: StageContract) -> list[GuardIssue]:
    issues: list[GuardIssue] = []
    for sentence in split_sentences(text):
        if not looks_like_concrete_canon(sentence):
            continue
        sourced = ledger.has_explicit_source(sentence)
        if contract.canon_policy in {"no_new_canon", "audit_only"} and not sourced:
            issues.append(GuardIssue("unsupported_concrete_canon", "rewrite", "缺少来源的具体 canon", sentence))
        if stage == "direction" and not ledger.is_user_requested(sentence):
            issues.append(GuardIssue("direction_unsupported_cost", "rewrite", "方向阶段不应自造具体代价", sentence))
    return issues


def detect_formulaic_causality(text: str) -> list[GuardIssue]:
    issues: list[GuardIssue] = []
    for sentence in split_sentences(text):
        if any(marker in sentence for marker in UNIVERSAL_MARKERS) and any(marker in sentence for marker in INEVITABILITY_MARKERS):
            issues.append(GuardIssue("formulaic_absolute_causality", "rewrite", "命中公式化绝对因果句式", sentence))
    return issues


def detect_non_worldbuilding_language(text: str, stage: str) -> list[GuardIssue]:
    if stage != "worldbuilding":
        return []
    issues: list[GuardIssue] = []
    if any(marker in text for marker in ("世界运行原则", "关键边界", "冲突资源", "代价红线")):
        issues.append(GuardIssue("legacy_worldbuilding_template", "rewrite", "命中旧世界观模板标题"))
    for sentence in split_sentences(text):
        if sentence.lstrip().startswith("#"):
            continue
        if any(marker in sentence for marker in WORLD_ABSTRACT_MARKERS):
            issues.append(GuardIssue("abstract_mechanism_language", "warning", "命中抽象机制语言", sentence))
    return issues


def rewrite_or_demote_issues(text: str, issues: list[GuardIssue], stage: str, ledger: SourceLedger) -> str:
    content = (text or "").strip()
    if not content:
        return content
    content = content.replace("## 世界运行原则", "### 题材核心结构")
    content = content.replace("## 关键边界", "### 主角所在组织或生活圈")
    content = content.replace("## 冲突资源", "### 势力、资源与日常压力")
    content = content.replace("## 代价红线", "### 待确认事项")

    for issue in issues:
        if issue.code == "formulaic_absolute_causality" and issue.excerpt:
            content = content.replace(issue.excerpt, soften_formulaic_sentence(issue.excerpt))
        if stage == "worldbuilding" and issue.code == "abstract_mechanism_language" and issue.excerpt:
            content = content.replace(issue.excerpt, rewrite_worldbuilding_sentence(issue.excerpt))

    if stage == "direction":
        lines = []
        for raw in content.splitlines():
            line = raw.strip()
            if not line:
                lines.append(raw)
                continue
            if direction_line_should_strip(line, ledger):
                continue
            lines.append(raw)
        content = ensure_direction_heading("\n".join(lines).strip())

    if stage == "worldbuilding":
        content = content.replace("有债必偿", "具体代价需基于场景确认")
        content = content.replace("情感变量", "关系压力")
        content = content.replace("阈值", "边界")
        content = content.replace("羁绊抵押", "关系把柄")
    return content



def direction_line_should_strip(line: str, ledger: SourceLedger) -> bool:
    if ledger.is_user_requested(line):
        return False
    risky_markers = (
        "寿元",
        "生命力",
        "情感纽带",
        "羁绊",
        "有债必偿",
        "阈值",
        "抵押",
        "机制",
        "系统",
        "模型",
        "变量",
        "红线",
    )
    return any(marker in line for marker in risky_markers)

def split_sentences(text: str) -> list[str]:
    lines: list[str] = []
    for piece in re.split(r"[\n。！？!?；;]+", text or ""):
        value = piece.strip()
        if value:
            lines.append(value)
    return lines


def soften_formulaic_sentence(sentence: str) -> str:
    value = sentence
    value = value.replace("每一次", "在常见场景里")
    value = value.replace("每次", "很多时候")
    value = value.replace("任何", "大多数")
    value = value.replace("所有", "不少")
    value = value.replace("一旦", "当")
    value = value.replace("只要", "当")
    value = value.replace("凡是", "通常")
    value = value.replace("无论", "即使")
    value = value.replace("必然", "往往")
    value = value.replace("必定", "通常")
    value = value.replace("都会", "容易")
    value = value.replace("就会", "可能")
    value = value.replace("从来", "通常不")
    value = value.replace("永远", "长期")
    value = value.replace("注定", "大概率")
    value = value.replace("有债必偿", "可能伴随代价")
    if value == sentence:
        return "该处应改为可观察的场景后果，而非绝对因果断言。"
    return value


def rewrite_worldbuilding_sentence(sentence: str) -> str:
    value = sentence
    for marker in WORLD_ABSTRACT_MARKERS:
        value = value.replace(marker, "")
    value = re.sub(r"\s+", " ", value).strip(" ：:-")
    if not value:
        return "请改写为角色可见、可触、可承受的世界压力。"
    return value


def ensure_direction_heading(text: str) -> str:
    content = text.strip()
    content = content.replace("## 方向控制稿", "## 方向定位稿")
    if "## 方向定位稿" in content:
        return content
    return "## 方向定位稿\n" + content
