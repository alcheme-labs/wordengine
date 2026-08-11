from __future__ import annotations

import math
from typing import Any

from world_engine.playable_world import (
    PLAYABLE_CONSEQUENCE_THRESHOLDS_V1,
    build_playable_consequence_record,
)


def _field_id(field_state: Any) -> str:
    return str(getattr(field_state, "field_state_id", "") or field_state.get("field_state_id", ""))


def _channel_grid(field_state: Any, channel: str) -> list[list[float]]:
    channels = getattr(field_state, "channels", None)
    if channels is None:
        channels = field_state.get("channels", {})
    if channel not in channels:
        raise ValueError(f"Missing channel for playable consequence: {channel}")
    return channels[channel]


def _channel_energy(field_state: Any, channel: str) -> float:
    grid = _channel_grid(field_state, channel)
    return sum(float(value) * float(value) for row in grid for value in row)


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def _grid_bounds(support_grid: dict[str, int] | list[int]) -> tuple[int, int, int, int]:
    if isinstance(support_grid, dict):
        return (
            int(support_grid["min_x"]),
            int(support_grid["min_y"]),
            int(support_grid["max_x"]),
            int(support_grid["max_y"]),
        )
    if len(support_grid) != 4:
        raise ValueError("support_grid must contain four bounds")
    return int(support_grid[0]), int(support_grid[1]), int(support_grid[2]), int(support_grid[3])


def _penetration_depth(boundary_grid: dict[str, int] | list[int], support_grid: dict[str, int] | list[int]) -> float:
    bx0, by0, bx1, by1 = _grid_bounds(boundary_grid)
    sx0, sy0, sx1, sy1 = _grid_bounds(support_grid)
    outside_left = max(0, bx0 - sx0)
    outside_top = max(0, by0 - sy0)
    outside_right = max(0, sx1 - bx1)
    outside_bottom = max(0, sy1 - by1)
    return float(max(outside_left, outside_top, outside_right, outside_bottom))


def _alignment(vector: list[float], direction: list[float]) -> float:
    if len(vector) != 2 or len(direction) != 2:
        raise ValueError("vectors must have two values")
    vx, vy = float(vector[0]), float(vector[1])
    dx, dy = float(direction[0]), float(direction[1])
    vnorm = math.sqrt(vx * vx + vy * vy)
    dnorm = math.sqrt(dx * dx + dy * dy)
    if vnorm == 0.0 or dnorm == 0.0:
        return 0.0
    return max(0.0, (vx * dx + vy * dy) / (vnorm * dnorm))


def compute_dampening_absorption(
    *,
    consequence_id: str,
    tick: int,
    channel: str,
    before_field: Any,
    after_field: Any,
    baseline_before_field: Any,
    baseline_after_field: Any,
    source_command_ids: list[str],
    source_wave_step_record_ids: list[str],
    baseline_case_id: str,
    projection_frame_ids: list[str] | None = None,
) -> dict[str, Any]:
    before = _channel_energy(before_field, channel)
    after = _channel_energy(after_field, channel)
    baseline_before = _channel_energy(baseline_before_field, channel)
    baseline_after = _channel_energy(baseline_after_field, channel)
    energy_decay = _safe_ratio(before - after, before)
    baseline_decay = _safe_ratio(baseline_before - baseline_after, baseline_before)
    baseline_delta = energy_decay - baseline_decay
    thresholds = PLAYABLE_CONSEQUENCE_THRESHOLDS_V1
    passed = (
        energy_decay >= thresholds["dampening_energy_decay_min"]
        and baseline_delta >= thresholds["dampening_baseline_delta_min"]
    )
    return build_playable_consequence_record(
        consequence_id=consequence_id,
        kind="dampening_absorption",
        tick=tick,
        window_ticks=[tick, tick + 1],
        source_command_ids=source_command_ids,
        source_field_state_ids=[_field_id(before_field), _field_id(after_field)],
        source_wave_step_record_ids=source_wave_step_record_ids,
        baseline_case_id=baseline_case_id,
        metrics={
            "channel": channel,
            "energy_before": before,
            "energy_after": after,
            "energy_decay": energy_decay,
            "baseline_decay": baseline_decay,
            "baseline_delta": baseline_delta,
        },
        thresholds=thresholds,
        status="passed" if passed else "failed",
        projection_frame_ids=projection_frame_ids or [],
    )


def compute_boundary_containment(
    *,
    consequence_id: str,
    tick: int,
    boundary_grid: dict[str, int] | list[int],
    support_grid: dict[str, int] | list[int],
    reflected_energy_ratio: float,
    retained_energy_ratio: float,
    source_affordance_ids: list[str],
    source_wave_step_record_ids: list[str],
    baseline_case_id: str,
    projection_frame_ids: list[str] | None = None,
) -> dict[str, Any]:
    penetration_depth = _penetration_depth(boundary_grid, support_grid)
    thresholds = PLAYABLE_CONSEQUENCE_THRESHOLDS_V1
    passed = (
        penetration_depth <= thresholds["boundary_penetration_depth_max_grid"]
        and (
            reflected_energy_ratio >= thresholds["boundary_reflected_energy_min"]
            or retained_energy_ratio >= thresholds["container_retained_energy_min"]
        )
    )
    return build_playable_consequence_record(
        consequence_id=consequence_id,
        kind="boundary_containment",
        tick=tick,
        window_ticks=[tick, tick + 1],
        source_affordance_ids=source_affordance_ids,
        source_wave_step_record_ids=source_wave_step_record_ids,
        baseline_case_id=baseline_case_id,
        metrics={
            "boundary_grid": boundary_grid,
            "support_grid": support_grid,
            "penetration_depth_grid": penetration_depth,
            "reflected_energy_ratio": reflected_energy_ratio,
            "retained_energy_ratio": retained_energy_ratio,
        },
        thresholds=thresholds,
        status="passed" if passed else "failed",
        projection_frame_ids=projection_frame_ids or [],
    )


def compute_channel_transport(
    *,
    consequence_id: str,
    tick: int,
    transport_vector_world: list[float],
    channel_direction_world: list[float],
    exit_energy_ratio: float,
    baseline_exit_energy_ratio: float,
    source_affordance_ids: list[str],
    source_wave_step_record_ids: list[str],
    baseline_case_id: str,
    projection_frame_ids: list[str] | None = None,
) -> dict[str, Any]:
    alignment = _alignment(transport_vector_world, channel_direction_world)
    baseline_delta = exit_energy_ratio - baseline_exit_energy_ratio
    thresholds = PLAYABLE_CONSEQUENCE_THRESHOLDS_V1
    passed = (
        alignment >= thresholds["channel_transport_alignment_min"]
        and exit_energy_ratio >= thresholds["channel_exit_energy_min"]
        and baseline_delta >= thresholds["channel_transport_baseline_delta_min"]
    )
    return build_playable_consequence_record(
        consequence_id=consequence_id,
        kind="channel_transport",
        tick=tick,
        window_ticks=[tick, tick + 1],
        source_affordance_ids=source_affordance_ids,
        source_wave_step_record_ids=source_wave_step_record_ids,
        baseline_case_id=baseline_case_id,
        metrics={
            "transport_vector_world": transport_vector_world,
            "channel_direction_world": channel_direction_world,
            "alignment": alignment,
            "exit_energy_ratio": exit_energy_ratio,
            "baseline_exit_energy_ratio": baseline_exit_energy_ratio,
            "baseline_delta": baseline_delta,
        },
        thresholds=thresholds,
        status="passed" if passed else "failed",
        projection_frame_ids=projection_frame_ids or [],
    )


def compute_source_maintenance(
    *,
    consequence_id: str,
    tick: int,
    maintained_energy_ratio: float,
    baseline_maintained_energy_ratio: float,
    source_command_ids: list[str],
    source_wave_step_record_ids: list[str],
    baseline_case_id: str,
    projection_frame_ids: list[str] | None = None,
) -> dict[str, Any]:
    baseline_delta = maintained_energy_ratio - baseline_maintained_energy_ratio
    thresholds = PLAYABLE_CONSEQUENCE_THRESHOLDS_V1
    passed = (
        maintained_energy_ratio >= thresholds["source_maintenance_energy_ratio_min"]
        and baseline_delta >= thresholds["source_maintenance_baseline_delta_min"]
    )
    return build_playable_consequence_record(
        consequence_id=consequence_id,
        kind="source_maintenance",
        tick=tick,
        window_ticks=[tick, tick + 1],
        source_command_ids=source_command_ids,
        source_wave_step_record_ids=source_wave_step_record_ids,
        baseline_case_id=baseline_case_id,
        metrics={
            "maintained_energy_ratio": maintained_energy_ratio,
            "baseline_maintained_energy_ratio": baseline_maintained_energy_ratio,
            "baseline_delta": baseline_delta,
        },
        thresholds=thresholds,
        status="passed" if passed else "failed",
        projection_frame_ids=projection_frame_ids or [],
    )


def compute_cohesion_accumulation(
    *,
    consequence_id: str,
    tick: int,
    support_iou: float,
    component_count_delta: int,
    source_affordance_ids: list[str],
    source_wave_step_record_ids: list[str],
    baseline_case_id: str,
    projection_frame_ids: list[str] | None = None,
) -> dict[str, Any]:
    thresholds = PLAYABLE_CONSEQUENCE_THRESHOLDS_V1
    passed = (
        support_iou >= thresholds["cohesion_support_iou_min"]
        and component_count_delta >= thresholds["cohesion_component_count_delta_min"]
    )
    return build_playable_consequence_record(
        consequence_id=consequence_id,
        kind="cohesion_accumulation",
        tick=tick,
        window_ticks=[tick, tick + 1],
        source_affordance_ids=source_affordance_ids,
        source_wave_step_record_ids=source_wave_step_record_ids,
        baseline_case_id=baseline_case_id,
        metrics={
            "support_iou": support_iou,
            "component_count_delta": component_count_delta,
        },
        thresholds=thresholds,
        status="passed" if passed else "failed",
        projection_frame_ids=projection_frame_ids or [],
    )


def compute_local_perturbation_response(
    *,
    consequence_id: str,
    tick: int,
    visible_frame_count: int,
    source_command_ids: list[str],
    source_wave_step_record_ids: list[str],
    baseline_case_id: str,
    projection_frame_ids: list[str] | None = None,
) -> dict[str, Any]:
    thresholds = PLAYABLE_CONSEQUENCE_THRESHOLDS_V1
    passed = visible_frame_count >= thresholds["interaction_visible_frame_min"]
    return build_playable_consequence_record(
        consequence_id=consequence_id,
        kind="local_perturbation_response",
        tick=tick,
        window_ticks=[tick, tick + visible_frame_count],
        source_command_ids=source_command_ids,
        source_wave_step_record_ids=source_wave_step_record_ids,
        baseline_case_id=baseline_case_id,
        metrics={"visible_frame_count": visible_frame_count},
        thresholds=thresholds,
        status="passed" if passed else "failed",
        projection_frame_ids=projection_frame_ids or [],
    )
