"""Legacy stage migration for outline workflow."""

from __future__ import annotations

from ai_novelist.outline.stage_contracts import LEGACY_STAGE_ALIAS, OUTLINE_STAGES, STAGE_LABELS
from ai_novelist.state import NovelState


def normalize_legacy_outline_artifacts(state: NovelState) -> None:
    for legacy_stage, stage in LEGACY_STAGE_ALIAS.items():
        if legacy_stage not in state.outline_stage_artifacts:
            continue
        if stage not in state.outline_stage_artifacts:
            artifact = state.outline_stage_artifacts[legacy_stage]
            if isinstance(artifact, dict):
                artifact = dict(artifact)
                artifact["stage"] = stage
                artifact.setdefault("label", STAGE_LABELS.get(stage, stage))
            state.outline_stage_artifacts[stage] = artifact
        if legacy_stage == "concept":
            # Keep concept as legacy artifact for display compatibility.
            concept = state.outline_stage_artifacts.get(legacy_stage)
            if isinstance(concept, dict):
                concept = dict(concept)
                concept["legacy"] = True
                concept["label"] = STAGE_LABELS["concept"]
                state.outline_stage_artifacts[legacy_stage] = concept
        else:
            del state.outline_stage_artifacts[legacy_stage]


def ensure_outline_stage(state: NovelState) -> None:
    normalize_legacy_outline_artifacts(state)
    if state.outline_stage == "done":
        state.outline_stage_status = "done"
        return
    if state.outline_stage == "concept":
        direction = state.outline_stage_artifacts.get("direction")
        if isinstance(direction, dict) and str(direction.get("synthesis", "")).strip():
            state.outline_stage = "worldbuilding"  # type: ignore[assignment]
        else:
            state.outline_stage = "direction"  # type: ignore[assignment]
    elif state.outline_stage == "outline_draft":
        state.outline_stage = "volume_outline"  # type: ignore[assignment]
    elif state.outline_stage not in OUTLINE_STAGES:
        state.outline_stage = "direction"  # type: ignore[assignment]
    if not state.outline_stage_status:
        state.outline_stage_status = "collecting"
