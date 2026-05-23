import json

from ai_novelist.output_contracts import normalize_review_editor_report, normalize_review_synthesis


def test_review_editor_report_is_compacted():
    raw = {
        "role": "continuity_editor",
        "verdict": "needs_revision",
        "top_issues": [
            {"severity": "high", "location": "第3场", "issue": "问题" * 100, "fix": "修复" * 100}
            for _ in range(8)
        ],
        "rewrite_tasks": ["任务" * 100 for _ in range(8)],
        "keep": ["保留" * 100 for _ in range(5)],
    }

    report = normalize_review_editor_report(raw)

    assert 1 <= len(report["top_issues"]) <= 5
    assert len(report["rewrite_tasks"]) <= 5
    assert len(report["keep"]) <= 3
    assert all(len(item["issue"]) <= 80 for item in report["top_issues"])
    assert len(json.dumps(report, ensure_ascii=False)) <= 1200


def test_review_synthesis_falls_back_from_markdown():
    report = normalize_review_synthesis("## 审稿\n- 场景压力不足，需要增加阻碍。")

    assert report["decision"] == "revise"
    assert report["issues"]
    assert {"decision", "score", "blocking_issues", "issues", "rewrite_tasks", "do_not_change"}.issubset(set(report))
    assert {"blocking_fixes", "pacing_safe_fixes", "backlog_suggestions", "rejected_suggestions"}.issubset(set(report))


def test_review_synthesis_limits_arrays_and_item_lengths():
    raw = {
        "decision": "revise",
        "score": 88,
        "blocking_issues": ["阻塞" * 50 for _ in range(5)],
        "issues": ["问题" * 50 for _ in range(8)],
        "rewrite_tasks": ["任务" * 50 for _ in range(10)],
    }

    report = normalize_review_synthesis(raw)

    assert len(report["blocking_issues"]) <= 3
    assert len(report["issues"]) <= 6
    assert len(report["rewrite_tasks"]) <= 8
    assert all(len(item) <= 90 for item in report["blocking_issues"])
    assert all(len(item) <= 90 for item in report["issues"])
    assert all(len(item) <= 90 for item in report["rewrite_tasks"])
