from ai_novelist.outline_graph.review_lock import (
    extract_review_lock_issue_buckets,
    review_lock_blocking_issues,
    review_lock_issue_lines,
)
from ai_novelist.outline_graph.routing import (
    detect_stage_reference,
    is_lock_request,
    next_outline_stage,
)


def test_review_lock_helpers_parse_blocking_and_detail_issues() -> None:
    markdown = """
## 审稿锁定
BLOCKING:
- 人物动机缺失
DETAIL:
- 道具名称需统一
"""
    buckets = extract_review_lock_issue_buckets(markdown)

    assert review_lock_blocking_issues(buckets) == ["人物动机缺失"]
    assert "道具名称需统一" in review_lock_issue_lines(buckets)


def test_routing_helpers_detect_lock_and_stage_reference() -> None:
    assert is_lock_request("锁定世界观并进入下一阶段")
    assert detect_stage_reference("请修订人物阶段") == "characters"
    assert next_outline_stage("characters") == "story_flow"
