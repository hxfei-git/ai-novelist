"""Outline stage contracts and guards."""

from .legacy_migration import ensure_outline_stage, normalize_legacy_outline_artifacts
from .question_filter import filter_stage_confirmation_questions
from .renderers import build_stage_output_rule
from .source_ledger import build_source_ledger, looks_like_concrete_canon
from .stage_contracts import (
    ACTIVE_OUTLINE_STAGES,
    LEGACY_OUTLINE_STAGES,
    OUTLINE_STAGES,
    STAGE_LABELS,
    StageContract,
    get_stage_contract,
)
from .stage_guard import GuardIssue, GuardResult, guard_stage_output

__all__ = [
    "ACTIVE_OUTLINE_STAGES",
    "LEGACY_OUTLINE_STAGES",
    "OUTLINE_STAGES",
    "STAGE_LABELS",
    "StageContract",
    "get_stage_contract",
    "build_source_ledger",
    "looks_like_concrete_canon",
    "GuardIssue",
    "GuardResult",
    "guard_stage_output",
    "filter_stage_confirmation_questions",
    "build_stage_output_rule",
    "ensure_outline_stage",
    "normalize_legacy_outline_artifacts",
]
