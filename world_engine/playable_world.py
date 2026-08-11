from __future__ import annotations

import math
from typing import Any


PLAYABLE_TOOL_CATALOG_V1: dict[str, dict[str, str]] = {
    "local_excite": {
        "kind": "field_source",
        "channel": "u",
        "authority": "interaction_command",
    },
    "local_dampen": {
        "kind": "field_dampening",
        "channel": "u",
        "authority": "interaction_command",
    },
    "directional_push": {
        "kind": "field_source_vector",
        "channel": "u",
        "authority": "interaction_command",
    },
    "sustained_source": {
        "kind": "field_source_trace",
        "channel": "u",
        "authority": "interaction_command",
    },
    "place_source_region": {
        "kind": "field_affordance_source",
        "channel": "u",
        "authority": "affordance_command",
    },
    "place_dampening_region": {
        "kind": "field_affordance_dampening",
        "channel": "u",
        "authority": "affordance_command",
    },
    "place_boundary_region": {
        "kind": "field_affordance_boundary",
        "channel": "u",
        "authority": "affordance_command",
    },
    "place_material_region": {
        "kind": "field_affordance_material",
        "channel": "u",
        "authority": "affordance_command",
    },
    "place_channel_region": {
        "kind": "field_affordance_channel",
        "channel": "u",
        "authority": "affordance_command",
    },
    "place_cohesion_region": {
        "kind": "field_affordance_cohesion",
        "channel": "u",
        "authority": "affordance_command",
    },
}


PLAYABLE_CONSEQUENCE_THRESHOLDS_V1: dict[str, float] = {
    "dampening_energy_decay_min": 0.35,
    "dampening_baseline_delta_min": 0.12,
    "boundary_penetration_depth_max_grid": 3.0,
    "boundary_reflected_energy_min": 0.20,
    "container_retained_energy_min": 0.55,
    "channel_transport_alignment_min": 0.55,
    "channel_exit_energy_min": 0.20,
    "channel_transport_baseline_delta_min": 0.10,
    "source_maintenance_energy_ratio_min": 0.70,
    "source_maintenance_baseline_delta_min": 0.15,
    "cohesion_support_iou_min": 0.35,
    "cohesion_component_count_delta_min": 1.0,
    "interaction_visible_frame_min": 3.0,
    "observer_overlay_coverage_ratio": 1.0,
}


PLAYABLE_PROJECTION_SCHEMA = "playable_projection_v1"
PLAYABLE_CONSEQUENCE_RECORD_SCHEMA = "playable_consequence_record_v1"
PLAYABLE_CONSEQUENCE_OVERLAY_SCHEMA = "playable_consequence_overlay_v1"
PLAYABLE_TOOL_REQUEST_SCHEMA = "playable_tool_request_v1"


def _finite_float(value: Any, field_name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field_name} must be finite")
    return result


def normalize_direction_world(value: Any) -> list[float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("direction_world must be a two-value list")
    x = _finite_float(value[0], "direction_world[0]")
    y = _finite_float(value[1], "direction_world[1]")
    norm = math.sqrt(x * x + y * y)
    if norm == 0.0:
        raise ValueError("direction_world must be nonzero")
    return [x / norm, y / norm]


def build_playable_tool_effect(tool: str, amplitude: float, direction_world: Any = None) -> dict[str, Any]:
    if tool not in PLAYABLE_TOOL_CATALOG_V1:
        raise ValueError(f"Unsupported playable tool: {tool}")
    amplitude_abs = min(1.0, abs(_finite_float(amplitude, "amplitude")))
    if tool == "place_channel_region":
        return {
            "affordance_kind": "material_region",
            "playable_effect": "channel_transport",
            "damping_delta": -0.020 * amplitude_abs,
            "feed_rate_delta": 0.010 * amplitude_abs,
            "kill_rate_delta": -0.004 * amplitude_abs,
            "direction_world": normalize_direction_world(direction_world),
        }
    if tool == "place_cohesion_region":
        return {
            "affordance_kind": "material_region",
            "playable_effect": "cohesion_accumulation",
            "damping_delta": 0.012 * amplitude_abs,
            "feed_rate_delta": 0.006 * amplitude_abs,
            "kill_rate_delta": -0.010 * amplitude_abs,
        }
    raise ValueError(f"Tool has no playable effect mapping: {tool}")


def build_playable_projection_mode(observer_frequency_window: dict[str, float] | None = None) -> dict[str, Any]:
    return {
        "schema": PLAYABLE_PROJECTION_SCHEMA,
        "observer_frequency_window": dict(observer_frequency_window or {"min": 0.0, "max": 1.0}),
        "background_flux_label": "background_flux",
        "display_is_authority": False,
    }


def build_playable_consequence_record(
    *,
    consequence_id: str,
    kind: str,
    tick: int,
    window_ticks: list[int],
    source_command_ids: list[str] | None = None,
    source_affordance_ids: list[str] | None = None,
    source_field_state_ids: list[str] | None = None,
    source_wave_step_record_ids: list[str] | None = None,
    source_material_response_record_ids: list[str] | None = None,
    source_property_record_ids: list[str] | None = None,
    baseline_case_id: str = "",
    metrics: dict[str, Any] | None = None,
    thresholds: dict[str, Any] | None = None,
    status: str = "failed",
    projection_frame_ids: list[str] | None = None,
) -> dict[str, Any]:
    if status not in {"passed", "failed"}:
        raise ValueError("Playable consequence status must be passed or failed")
    if not consequence_id:
        raise ValueError("consequence_id is required")
    if not kind:
        raise ValueError("kind is required")
    if len(window_ticks) != 2:
        raise ValueError("window_ticks must contain [start, end]")
    return {
        "schema": PLAYABLE_CONSEQUENCE_RECORD_SCHEMA,
        "consequence_id": consequence_id,
        "kind": kind,
        "tick": int(tick),
        "window_ticks": [int(window_ticks[0]), int(window_ticks[1])],
        "source_command_ids": list(source_command_ids or []),
        "source_affordance_ids": list(source_affordance_ids or []),
        "source_field_state_ids": list(source_field_state_ids or []),
        "source_wave_step_record_ids": list(source_wave_step_record_ids or []),
        "source_material_response_record_ids": list(source_material_response_record_ids or []),
        "source_property_record_ids": list(source_property_record_ids or []),
        "baseline_case_id": baseline_case_id,
        "metrics": dict(metrics or {}),
        "thresholds": dict(thresholds or PLAYABLE_CONSEQUENCE_THRESHOLDS_V1),
        "status": status,
        "projection_frame_ids": list(projection_frame_ids or []),
    }


def build_playable_consequence_overlay(
    *,
    consequence_id: str,
    kind: str,
    source_record_ids: list[str],
    support_grid: dict[str, int],
    centroid_world: list[float],
    spectral_band: str,
    status: str,
) -> dict[str, Any]:
    return {
        "schema": PLAYABLE_CONSEQUENCE_OVERLAY_SCHEMA,
        "consequence_id": consequence_id,
        "kind": kind,
        "source_record_ids": list(source_record_ids),
        "support_grid": dict(support_grid),
        "centroid_world": list(centroid_world),
        "spectral_band": spectral_band,
        "status": status,
    }
