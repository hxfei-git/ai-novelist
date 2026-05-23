"""Output normalization contracts for compact agent reports."""

from __future__ import annotations

import json
import re
from typing import Any


def compact_text(text: str, max_chars: int) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max(0, max_chars - 3)].rstrip() + "..."


def normalize_string_list(value: object, *, max_items: int, max_item_chars: int) -> list[str]:
    if isinstance(value, str):
        raw_items = [value] if value.strip() else []
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = []
    result: list[str] = []
    for item in raw_items:
        if isinstance(item, dict):
            text = "；".join(str(part).strip() for part in item.values() if str(part).strip())
        else:
            text = str(item).strip()
        text = compact_text(text, max_item_chars)
        if text:
            result.append(text)
        if len(result) >= max_items:
            break
    return result


def normalize_review_editor_report(raw: object, fallback_text: str = "") -> dict[str, Any]:
    data = parse_json_object(raw)
    fallback = fallback_text or (raw if isinstance(raw, str) else "")
    if not data:
        data = fallback_editor_data(fallback)
    role = compact_text(str(data.get("role") or "review_editor"), 40) or "review_editor"
    verdict = str(data.get("verdict") or data.get("decision") or "needs_revision").strip().lower()
    if verdict not in {"pass", "needs_revision", "severe"}:
        verdict = "needs_revision"
    issues = normalize_issue_list(data.get("top_issues"), fallback_text=fallback_text)
    report = {
        "role": role,
        "verdict": verdict,
        "top_issues": issues[:5],
        "rewrite_tasks": normalize_string_list(data.get("rewrite_tasks"), max_items=5, max_item_chars=80),
        "keep": normalize_string_list(data.get("keep"), max_items=3, max_item_chars=80),
    }
    return enforce_editor_report_size(report)


def normalize_review_synthesis(raw: object, fallback_text: str = "") -> dict[str, Any]:
    data = parse_json_object(raw)
    fallback = fallback_text or (raw if isinstance(raw, str) else "")
    decision = str(data.get("decision") or data.get("status") or "revise").strip().lower()
    if decision not in {"pass", "revise", "stop"}:
        decision = "revise"
    try:
        score = int(data.get("score") or data.get("quality_score") or 0)
    except (TypeError, ValueError):
        score = 0
    issues = normalize_string_list(data.get("issues"), max_items=6, max_item_chars=90)
    if not issues and str(fallback).strip():
        issues = extract_fallback_bullets(str(fallback), max_items=5, max_chars=90)
    blocking_issues = normalize_string_list(data.get("blocking_issues"), max_items=3, max_item_chars=90)
    rewrite_tasks = normalize_string_list(data.get("rewrite_tasks"), max_items=8, max_item_chars=90)
    blocking_fixes = normalize_string_list(data.get("blocking_fixes"), max_items=6, max_item_chars=90) or list(blocking_issues)
    pacing_safe_fixes = normalize_string_list(data.get("pacing_safe_fixes"), max_items=6, max_item_chars=90) or list(rewrite_tasks)
    backlog_suggestions = normalize_string_list(data.get("backlog_suggestions"), max_items=6, max_item_chars=90)
    rejected_suggestions = normalize_string_list(data.get("rejected_suggestions"), max_items=6, max_item_chars=90)
    return {
        "decision": decision,
        "score": max(0, min(score, 100)),
        "blocking_issues": blocking_issues,
        "issues": issues,
        "rewrite_tasks": rewrite_tasks,
        "do_not_change": normalize_string_list(data.get("do_not_change"), max_items=5, max_item_chars=80),
        "blocking_fixes": blocking_fixes,
        "pacing_safe_fixes": pacing_safe_fixes,
        "backlog_suggestions": backlog_suggestions,
        "rejected_suggestions": rejected_suggestions,
    }



def enforce_editor_report_size(report: dict[str, Any], max_chars: int = 1200) -> dict[str, Any]:
    compact = dict(report)
    while len(json.dumps(compact, ensure_ascii=False)) > max_chars and compact.get("keep"):
        compact["keep"] = compact["keep"][:-1]
    while len(json.dumps(compact, ensure_ascii=False)) > max_chars and compact.get("rewrite_tasks"):
        compact["rewrite_tasks"] = compact["rewrite_tasks"][:-1]
    while len(json.dumps(compact, ensure_ascii=False)) > max_chars and len(compact.get("top_issues", [])) > 3:
        compact["top_issues"] = compact["top_issues"][:-1]
    if len(json.dumps(compact, ensure_ascii=False)) > max_chars:
        for item in compact.get("top_issues", []):
            item["issue"] = compact_text(item.get("issue", ""), 50)
            item["fix"] = compact_text(item.get("fix", ""), 50)
    return compact

def parse_json_object(raw: object) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
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


def normalize_issue_list(value: object, fallback_text: str = "") -> list[dict[str, str]]:
    source = value if isinstance(value, list) else []
    if not source and fallback_text.strip():
        source = [{"issue": item, "fix": "按审稿意见定向修订。"} for item in extract_fallback_bullets(fallback_text, max_items=5, max_chars=80)]
    result: list[dict[str, str]] = []
    for item in source:
        if isinstance(item, dict):
            severity = str(item.get("severity") or "medium").strip().lower()
            if severity not in {"high", "medium", "low"}:
                severity = "medium"
            result.append(
                {
                    "severity": severity,
                    "location": compact_text(str(item.get("location") or "全章"), 80),
                    "issue": compact_text(str(item.get("issue") or item.get("problem") or ""), 80),
                    "fix": compact_text(str(item.get("fix") or item.get("suggestion") or ""), 80),
                }
            )
        else:
            result.append({"severity": "medium", "location": "全章", "issue": compact_text(str(item), 80), "fix": "定向修订。"})
        if len(result) >= 5:
            break
    return [item for item in result if item["issue"]]


def fallback_editor_data(text: str) -> dict[str, Any]:
    bullets = extract_fallback_bullets(text, max_items=5, max_chars=80)
    return {"top_issues": bullets, "rewrite_tasks": bullets[:5], "keep": []}


def extract_fallback_bullets(text: str, *, max_items: int, max_chars: int) -> list[str]:
    items: list[str] = []
    for line in str(text or "").splitlines():
        stripped = re.sub(r"^[-*+\d.、\s]+", "", line).strip()
        if stripped and not stripped.startswith("#"):
            items.append(compact_text(stripped, max_chars))
        if len(items) >= max_items:
            break
    if not items and text.strip():
        items = [compact_text(text, max_chars)]
    return items[:max_items]
