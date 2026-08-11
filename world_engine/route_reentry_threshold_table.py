from __future__ import annotations

from typing import Any


THRESHOLD_SCHEMA = "route_reentry_thresholds_v1"
THRESHOLD_TABLE_SOURCE_PATH = "world_engine/route_reentry_threshold_table.py"


def route_reentry_threshold_owner_record() -> dict[str, Any]:
    return {
        "source_path": THRESHOLD_TABLE_SOURCE_PATH,
        "schema": THRESHOLD_SCHEMA,
        "manual_threshold_table_allowed": False,
    }


def threshold_table(thresholds: Any) -> dict[str, Any]:
    return {
        "prior_transfer_boundary": thresholds.prior_transfer_boundary,
        "transfer_boundary": thresholds.transfer_boundary,
        "prior_retention_boundary": thresholds.prior_retention_boundary,
        "retention_boundary": thresholds.retention_boundary,
        "prior_continuity_window": thresholds.prior_continuity_window,
        "continuity_window": thresholds.continuity_window,
        "prior_route_variant": thresholds.prior_route_variant,
        "route_variant": thresholds.route_variant,
        "prior_region_variant": thresholds.prior_region_variant,
        "region_variant": thresholds.region_variant,
        "record_count": thresholds.record_count,
        "score": thresholds.score,
        "baseline_advantage": thresholds.baseline_advantage,
        "runtime_budget": thresholds.runtime_budget,
        "artifact_budget": thresholds.artifact_budget,
    }


def route_reentry_threshold_table_record(target: Any) -> dict[str, Any]:
    return {
        "schema": THRESHOLD_SCHEMA,
        "source_path": THRESHOLD_TABLE_SOURCE_PATH,
        "target_registry_key": target.key,
        "capability": target.capability,
        "expected_target_id": target.expected_target_id,
        "thresholds": threshold_table(target.thresholds),
    }


def route_reentry_threshold_transition_record(reference_target: Any, candidate: Any) -> dict[str, Any]:
    return {
        "schema": THRESHOLD_SCHEMA,
        "source_path": THRESHOLD_TABLE_SOURCE_PATH,
        "predecessor_target_key": reference_target.key,
        "candidate_target_key": candidate.key,
        "capability": candidate.capability,
        "thresholds": threshold_table(candidate.thresholds),
    }
