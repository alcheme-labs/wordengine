from __future__ import annotations

import math
from typing import Any

from world_engine.playable_world import PLAYABLE_TOOL_CATALOG_V1


EXPLORATION_TOOL_STEP_SCHEMA = "exploration_tool_step_v1"
EXPLORATION_EPISODE_SCHEMA = "exploration_episode_v1"
CONSEQUENCE_WINDOW_SCHEMA = "consequence_window_v1"
REGION_REENTRY_SCHEMA = "region_reentry_v1"

MIN_PLAY_TICKS = 256
MIN_TOOL_COMMANDS = 6
MIN_DISTINCT_TOOL_KINDS = 4
MIN_CONSEQUENCE_WINDOWS = 5
MIN_BACKED_PLAYABLE_CONSEQUENCE_RECORDS = 5
MIN_REGION_REENTRY_COUNT = 2
MAX_DEAD_FRAME_RATIO = 0.15
OBSERVER_FRAME_COVERAGE_RATIO = 1.0
MIN_VISIBLE_CONSEQUENCE_FRAMES = 8
MAX_INTERACTION_RESPONSE_LAG_TICKS = 16
PER_CASE_ARTIFACT_BUDGET_BYTES = 384 * 1024 * 1024
TOTAL_ARTIFACT_BUDGET_BYTES = 3 * 1024 * 1024 * 1024

REQUIRED_WINDOW_METRICS = {
    "visible_frame_count",
    "dead_frame_ratio",
    "response_lag_ticks",
    "consequence_overlay_coverage",
    "field_energy_delta_vs_baseline",
}

REQUIRED_REENTRY_METRICS = {
    "centroid_world_distance",
    "support_iou",
    "energy_ratio",
    "mode_signature_match",
}


def build_exploration_tool_step(
    *,
    step_id: str,
    tick_offset: int,
    request: dict[str, object],
    expected_consequence_kinds: list[str],
) -> dict[str, object]:
    return {
        "schema": EXPLORATION_TOOL_STEP_SCHEMA,
        "step_id": step_id,
        "tick_offset": tick_offset,
        "request": dict(request),
        "expected_consequence_kinds": list(expected_consequence_kinds),
    }


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def validate_exploration_tool_step(
    step: dict[str, Any],
    *,
    declared_observer_ids: list[str],
) -> list[str]:
    errors: list[str] = []
    if step.get("schema") != EXPLORATION_TOOL_STEP_SCHEMA:
        errors.append("invalid_schema")
    try:
        tick_offset = int(step.get("tick_offset", -1))
    except (TypeError, ValueError):
        tick_offset = -1
    if tick_offset < 0:
        errors.append("invalid_tick_offset")

    request = step.get("request")
    if not isinstance(request, dict):
        errors.append("invalid_request")
        request = {}

    tool = request.get("tool")
    if tool not in PLAYABLE_TOOL_CATALOG_V1:
        errors.append("unsupported_tool")

    observer_id = request.get("observer_id")
    if observer_id not in set(declared_observer_ids):
        errors.append("unknown_observer_id")

    image_xy = request.get("image_xy")
    if image_xy is not None:
        if (
            not isinstance(image_xy, list)
            or len(image_xy) != 2
            or not all(_finite_number(item) for item in image_xy)
            or any(float(item) < 0.0 or float(item) > 1.0 for item in image_xy)
        ):
            errors.append("invalid_image_xy")

    radius_grid = request.get("radius_grid")
    if radius_grid is not None:
        try:
            radius = int(radius_grid)
        except (TypeError, ValueError):
            radius = -1
        if radius < 1 or radius > 16:
            errors.append("invalid_radius_grid")

    amplitude = request.get("amplitude")
    if amplitude is not None:
        if not _finite_number(amplitude) or float(amplitude) < -1.0 or float(amplitude) > 1.0:
            errors.append("invalid_amplitude")

    if not step.get("expected_consequence_kinds"):
        errors.append("missing_expected_consequence_kinds")
    return errors


def build_exploration_episode_record(
    *,
    episode_id: str,
    source_package_name: str,
    source_package_dir: str,
    case_type: str,
    seed_salt: str,
    grid_shape: list[int],
    warmup_ticks: int,
    play_ticks: int,
    baseline_case_id: str,
    declared_observer_ids: list[str],
    tool_schedule: list[dict[str, object]],
    command_ids: list[str],
    consequence_ids: list[str],
    frame_ids: list[str],
    region_reentry_ids: list[str],
    artifact_policy: dict[str, object],
) -> dict[str, object]:
    return {
        "schema": EXPLORATION_EPISODE_SCHEMA,
        "episode_id": episode_id,
        "source_package_name": source_package_name,
        "source_package_dir": source_package_dir,
        "case_type": case_type,
        "seed_salt": seed_salt,
        "grid_shape": list(grid_shape),
        "warmup_ticks": warmup_ticks,
        "play_ticks": play_ticks,
        "baseline_case_id": baseline_case_id,
        "declared_observer_ids": list(declared_observer_ids),
        "tool_schedule": list(tool_schedule),
        "command_ids": list(command_ids),
        "consequence_ids": list(consequence_ids),
        "frame_ids": list(frame_ids),
        "region_reentry_ids": list(region_reentry_ids),
        "artifact_policy": dict(artifact_policy),
    }


def build_consequence_window_record(
    *,
    window_id: str,
    episode_id: str,
    tick_start: int,
    tick_end: int,
    command_ids: list[str],
    consequence_ids: list[str],
    source_playable_consequence_record_ids: list[str],
    frame_ids: list[str],
    baseline_case_id: str,
    metrics: dict[str, float],
    status: str,
) -> dict[str, object]:
    return {
        "schema": CONSEQUENCE_WINDOW_SCHEMA,
        "window_id": window_id,
        "episode_id": episode_id,
        "tick_start": tick_start,
        "tick_end": tick_end,
        "command_ids": list(command_ids),
        "consequence_ids": list(consequence_ids),
        "source_playable_consequence_record_ids": list(source_playable_consequence_record_ids),
        "frame_ids": list(frame_ids),
        "baseline_case_id": baseline_case_id,
        "metrics": dict(metrics),
        "status": status,
    }


def build_region_reentry_record(
    *,
    reentry_id: str,
    episode_id: str,
    region_key: str,
    first_tick: int,
    return_tick: int,
    source_consequence_ids: list[str],
    source_frame_ids: list[str],
    continuity_metrics: dict[str, float],
    status: str,
) -> dict[str, object]:
    return {
        "schema": REGION_REENTRY_SCHEMA,
        "reentry_id": reentry_id,
        "episode_id": episode_id,
        "region_key": region_key,
        "first_tick": first_tick,
        "return_tick": return_tick,
        "source_consequence_ids": list(source_consequence_ids),
        "source_frame_ids": list(source_frame_ids),
        "continuity_metrics": dict(continuity_metrics),
        "status": status,
    }
