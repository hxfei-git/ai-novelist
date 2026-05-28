"""File-backed services used by the Web API."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError
from ai_novelist.graph_volume_write import build_volume_write_graph, parse_chapter_override
from ai_novelist.outline.chapter_outline_structure import (
    chinese_number_to_int,
    current_volume_spec,
    volume_label,
)
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore, LocalStoreError, summarize_text
from ai_novelist.workflow_payloads import set_chapter_batch_payload
from ai_novelist.web.json_utils import parse_json_object
from ai_novelist.web.chapter_outline_actions import (
    apply_chapter_outline_review,
    chapter_outline_review_report_paths,
    chapter_outline_workspace_payload,
    generate_chapter_outline_volume,
    latest_chapter_outline_review_report,
    latest_chapter_outline_review_run,
    load_chapter_outline_review_report,
    lock_chapter_outline_volume,
    prepare_chapter_outline_volume_action,
    render_chapter_outline_review_markdown,
    review_chapter_outline,
    revise_chapter_outline_volume,
)
from ai_novelist.web.outline_actions import (
    apply_outline_review,
    build_pending_revision_instruction,
    generate_outline_stage,
    load_outline_stage_payload,
    lock_outline_stage,
    normalize_pending_answers,
    outline_stage_pending_payload,
    review_outline,
    revise_outline_stage,
    save_outline_stage_content,
    strip_markdown_heading,
    submit_stage_pending_answers,
)
from ai_novelist.web.chapter_service import (
    build_global_review_prompt,
    chapter_outline_review_source_text,
)
from ai_novelist.web.project_service import (
    MAX_WEB_PROGRESS_LOG_ITEMS,
    ProgressItem,
    WebProject,
    build_progress_event,
    create_project,
    list_projects,
    load_project_progress_log,
    normalize_progress_log_items,
    project_needs_onboarding,
    project_progress_log_path,
    save_project_idea,
    save_project_progress_log,
)
from ai_novelist.web.outline_service import (
    action_state_for_status,
    build_outline_repair_suggestions,
    collect_stage_pending_questions,
    default_pending_options,
    ensure_ordinary_stage_mutation,
    ensure_outline_stage_mutable,
    ensure_valid_stage,
    extract_pending_questions_from_stage_markdown,
    has_outline_stage_content,
    latest_outline_review_report,
    latest_outline_review_run,
    load_outline_review_report,
    load_stage_markdown,
    outline_review_source_text,
    outline_stage_action_state,
    outline_stage_list,
    outline_stage_payload,
    pending_display_question,
    pending_item_id,
    selected_outline_revision_instruction,
    write_outline_review_baseline_sections,
    write_outline_review_report,
)
from ai_novelist.web.chapter_actions import (
    WebChapter,
    chapter_batch_workspace_payload,
    chapter_payload,
    chapter_source,
    chapter_title,
    collect_latest_chapters,
    extract_volume_chapter_numbers,
    fallback_repair_text,
    generate_chapter_batch,
    latest_chapter_path,
    latest_volume_batch_manifest,
    list_chapters,
    load_chapter_payload,
    load_latest_chapter_text,
    next_draft_version,
    normalize_chapter_selector,
)
from ai_novelist.web.review_actions import (
    apply_repair,
    build_chapter_repair_prompt,
    build_repair_suggestions,
    generate_repair_proposals,
    global_review_root,
    group_repair_suggestions_by_chapter,
    issue_identifier,
    issue_recommendation,
    latest_global_review,
    load_global_review,
    local_chapter_review_issues,
    merge_review_issues,
    normalize_global_review_output,
    normalize_issue_chapter,
    normalize_repair_suggestions,
    proposed_repair_path,
    review_all_chapters,
    safe_run_id,
    write_global_review_report,
)

ProgressFunc = Callable[[str, str], None]
