"""Review-lock issue parsing and user-facing messages."""

from __future__ import annotations

import re

from ai_novelist.artifacts import sha256_text


def _int_value(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_meta_str_list(value) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _normalize_meta_dict_list(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _stage_revision_metadata(artifact: dict) -> dict:
    raw = artifact.get("revision_meta") if isinstance(artifact, dict) else {}
    metadata = dict(raw) if isinstance(raw, dict) else {}
    metadata["revision_count"] = _int_value(metadata.get("revision_count"), _int_value(artifact.get("revision_count"), 0))
    metadata["last_revision_mode"] = str(metadata.get("last_revision_mode") or artifact.get("last_revision_mode") or "")
    metadata["last_revision_at"] = str(metadata.get("last_revision_at") or artifact.get("last_revision_at") or "")
    metadata["last_revision_intent"] = str(metadata.get("last_revision_intent") or artifact.get("last_revision_intent") or "")
    metadata["last_revision_instruction"] = str(metadata.get("last_revision_instruction") or artifact.get("last_revision_instruction") or "")
    metadata["last_revision_user_text"] = str(metadata.get("last_revision_user_text") or artifact.get("last_revision_user_text") or "")
    metadata["question_round"] = _int_value(metadata.get("question_round"), _int_value(artifact.get("question_round"), 0))
    metadata["last_question_round"] = _int_value(metadata.get("last_question_round"), _int_value(artifact.get("question_round"), 0))
    metadata["last_question_fingerprints"] = _normalize_meta_str_list(metadata.get("last_question_fingerprints") or artifact.get("last_question_fingerprints"))
    metadata["seen_question_fingerprints"] = _normalize_meta_str_list(metadata.get("seen_question_fingerprints") or artifact.get("seen_question_fingerprints"))
    metadata["question_history"] = _normalize_meta_dict_list(metadata.get("question_history") or artifact.get("question_history"))
    return metadata


def _normalize_stage_question_text(question: str) -> str:
    text = str(question or "").strip()
    text = re.sub(r"^[-*+•\s]*", "", text)
    text = re.sub(r"^\d+[.、)]\s*", "", text)
    text = re.sub(r"[`*_#>\[\]【】()（）{}]+", "", text)
    text = re.sub(r"\s+", "", text)
    text = text.strip(" ：:，,。.!！?？；;、-/\\")
    return text.lower()


def _stage_question_fingerprint(question: str) -> str:
    normalized = _normalize_stage_question_text(question)
    return sha256_text(normalized) if normalized else ""


def _filter_stage_questions_by_history(artifact: object, questions: list[str]) -> list[str]:
    if not isinstance(artifact, dict):
        return questions
    metadata = _stage_revision_metadata(artifact)
    seen = set(_normalize_meta_str_list(metadata.get("seen_question_fingerprints")))
    filtered: list[str] = []
    fingerprints: set[str] = set()
    for question in questions:
        cleaned = str(question).strip()
        if not cleaned:
            continue
        fingerprint = _stage_question_fingerprint(cleaned)
        if fingerprint in seen or fingerprint in fingerprints:
            continue
        filtered.append(cleaned)
        fingerprints.add(fingerprint)
    return filtered


def filter_review_lock_issue_buckets_by_history(artifact: object, issue_buckets: dict[str, list[str]]) -> dict[str, list[str]]:
    return {
        key: _filter_stage_questions_by_history(artifact, list(issue_buckets.get(key) or []))
        for key in ("blocking", "detail", "rework", "questions")
    }


def extract_review_lock_issue_buckets(markdown: str) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {
        "blocking": [],
        "detail": [],
        "rework": [],
        "questions": [],
    }
    current: str | None = None
    headings = {
        "阻塞型结构问题": "blocking",
        "结构阻塞问题": "blocking",
        "BLOCKING": "blocking",
        "非阻塞细节问题": "detail",
        "细节问题": "detail",
        "DETAIL": "detail",
        "需要回改的阶段": "rework",
        "回改阶段": "rework",
        "REWORK": "rework",
        "仍需确认的问题": "questions",
        "待确认问题": "questions",
        "待确认的问题": "questions",
        "QUESTIONS": "questions",
    }
    for raw_line in (markdown or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("## ", "### ")):
            title = line.lstrip("#").strip()
            current = headings.get(title)
            continue
        title = line.rstrip("：:")
        if title in headings:
            current = headings[title]
            continue
        if current is None:
            continue
        if line in {"暂无", "暂无。", "无", "无。"} or "暂无" in line:
            continue
        cleaned = re.sub(r"^[-*+•\s]*", "", line)
        cleaned = re.sub(r"^\d+[.、)]\s*", "", cleaned).strip(" ：:-")
        if cleaned and cleaned not in buckets[current]:
            buckets[current].append(cleaned)
    return {key: value[:10] for key, value in buckets.items()}


def review_lock_blocking_issues(issue_buckets: dict[str, list[str]]) -> list[str]:
    blocking = list(dict.fromkeys((issue_buckets.get("blocking") or []) + (issue_buckets.get("rework") or [])))
    return blocking[:10]


def review_lock_detail_issues(issue_buckets: dict[str, list[str]]) -> list[str]:
    detail = list(dict.fromkeys((issue_buckets.get("detail") or []) + (issue_buckets.get("questions") or [])))
    return detail[:10]


def review_lock_issue_lines(issue_buckets: dict[str, list[str]]) -> list[str]:
    combined = review_lock_blocking_issues(issue_buckets) + review_lock_detail_issues(issue_buckets)
    return list(dict.fromkeys(item for item in combined if item))[:10]


def review_lock_pending_question_text(issue_buckets: dict[str, list[str]]) -> str:
    blocking = review_lock_blocking_issues(issue_buckets)
    detail = review_lock_detail_issues(issue_buckets)
    if blocking:
        detail_note = f"，另有 {len(detail)} 项非阻塞细节问题" if detail else ""
        return f"审稿锁定仍有 {len(blocking)} 项阻塞型结构问题{detail_note}；请先回改前序阶段，再确认是否锁定。"
    if detail:
        return f"审稿锁定剩余 {len(detail)} 项非阻塞细节问题；可以补齐后再锁定，或明确接受当前风险并进入章节卡。"
    return "审稿锁定未发现阻塞型结构问题，可以确认锁定并进入章节卡。"


def review_lock_blocking_message(issue_buckets: dict[str, list[str]]) -> str:
    blocking = review_lock_blocking_issues(issue_buckets)
    detail = review_lock_detail_issues(issue_buckets)
    lines = ["审稿锁定暂不通过，需要先回改前序阶段。"]
    if blocking:
        lines.append("阻塞型结构问题：")
        lines.extend(f"- {item}" for item in blocking)
    if detail:
        lines.append("非阻塞细节问题：")
        lines.extend(f"- {item}" for item in detail)
    lines.append("请先回改这些阶段，再重新进入审稿锁定。")
    return "\n".join(lines)


def review_lock_issue_buckets_from_artifact(artifact: dict) -> dict[str, list[str]]:
    buckets = artifact.get("review_lock_issues")
    if isinstance(buckets, dict):
        normalized: dict[str, list[str]] = {"blocking": [], "detail": [], "rework": [], "questions": []}
        for key in normalized:
            value = buckets.get(key)
            if isinstance(value, list):
                normalized[key] = [str(item).strip() for item in value if str(item).strip()][:10]
        return normalized
    synthesis = str(artifact.get("synthesis") or "")
    return extract_review_lock_issue_buckets(synthesis)
