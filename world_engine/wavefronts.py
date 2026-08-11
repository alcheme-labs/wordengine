from __future__ import annotations

import hashlib
import json
import math
from typing import Mapping, Sequence


DISTURBANCE_WAVEFRONT_RECORD_SCHEMA = "disturbance_wavefront_record_v1"
MATERIAL_WAVEFRONT_RESPONSE_SCHEMA = "material_wavefront_response_v1"
VISIBLE_WAVEFRONT_TRANSIENT_SCHEMA = "visible_wavefront_transient_v1"

FORBIDDEN_WAVEFRONT_SAMPLE_KEYS = {
    "world_xy",
    "grid_xy",
    "support_grid",
    "image_bounds",
    "material_color_name",
    "css_color",
    "viewer_color",
    "field_channel_label",
}


def _canonical_digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _finite_float(name: str, value: object) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _finite_pair(name: str, value: Sequence[object]) -> list[float]:
    if len(value) != 2:
        raise ValueError(f"{name} must have length 2")
    return [_finite_float(f"{name}[0]", value[0]), _finite_float(f"{name}[1]", value[1])]


def _clamp01(value: object) -> float:
    return max(0.0, min(1.0, _finite_float("score", value)))


def _unique(values: Sequence[object]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        text = str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _record_id(record: Mapping[str, object]) -> str | None:
    if record.get("record_id"):
        return str(record["record_id"])
    if record.get("id"):
        return str(record["id"])
    return None


def _field_state_id(field_state: Mapping[str, object]) -> str:
    if field_state.get("field_state_id"):
        return str(field_state["field_state_id"])
    if field_state.get("id"):
        return str(field_state["id"])
    return f"field-state::tick::{field_state.get('tick', 0)}"


def _tick(field_state: Mapping[str, object]) -> int:
    return int(field_state.get("tick", 0))


def _channel_grid(field_state: Mapping[str, object], channel: str) -> list[list[float]]:
    channels = field_state.get("channels")
    if not isinstance(channels, Mapping) or channel not in channels:
        raise ValueError(f"field_state missing channel {channel!r}")
    return [[float(value) for value in row] for row in channels[channel]]


def _coordinate_frame(field_state: Mapping[str, object]) -> tuple[int, int, float, float, float, float]:
    payload = field_state.get("payload", {})
    frame = payload.get("coordinate_frame", {}) if isinstance(payload, Mapping) else {}
    grid_shape = frame.get("grid_shape")
    world_bounds = frame.get("world_bounds")
    if world_bounds is None and frame.get("world_origin") is not None and frame.get("world_extent") is not None:
        origin = frame["world_origin"]
        extent = frame["world_extent"]
        world_bounds = [
            [float(origin[0]), float(origin[1])],
            [float(origin[0]) + float(extent[0]), float(origin[1]) + float(extent[1])],
        ]
    if not grid_shape or not world_bounds:
        raise ValueError("field_state payload requires coordinate_frame grid_shape and world bounds")
    height = int(grid_shape[0])
    width = int(grid_shape[1])
    [[min_x, min_y], [max_x, max_y]] = world_bounds
    if width <= 0 or height <= 0 or float(max_x) <= float(min_x) or float(max_y) <= float(min_y):
        raise ValueError("invalid coordinate_frame")
    return width, height, float(min_x), float(min_y), float(max_x), float(max_y)


def _grid_to_world(grid_xy: Sequence[float], frame: tuple[int, int, float, float, float, float]) -> list[float]:
    width, height, min_x, min_y, max_x, max_y = frame
    gx = _finite_float("grid_x", grid_xy[0])
    gy = _finite_float("grid_y", grid_xy[1])
    world_x = min_x + gx / max(1, width - 1) * (max_x - min_x)
    world_y = min_y + gy / max(1, height - 1) * (max_y - min_y)
    return [world_x, world_y]


def build_disturbance_wavefront_record(
    *,
    run_id: str,
    tick: int,
    channel: str,
    previous_field_state_id: str,
    current_field_state_id: str,
    wave_step_record_ids: Sequence[str],
    interaction_command_ids: Sequence[str],
    playable_consequence_record_ids: Sequence[str],
    wavefront_trace_id: str,
    previous_wavefront_record_id: str | None,
    source_center_grid: Sequence[float],
    source_center_world: Sequence[float],
    centroid_grid: Sequence[float],
    centroid_world: Sequence[float],
    radius_grid: float,
    front_radius_delta_grid: float,
    front_energy: float,
    front_delta_energy: float,
    front_band_count: int,
    outwardness_score: float,
    attenuation_score: float,
    reflection_score: float,
    absorption_score: float,
    support_digest: str,
    phase_signature: str,
    source_center_kind: str = "interaction_center",
) -> dict:
    source_ids = _unique(
        [
            previous_field_state_id,
            current_field_state_id,
            *wave_step_record_ids,
            *interaction_command_ids,
            *playable_consequence_record_ids,
            previous_wavefront_record_id,
        ]
    )
    return {
        "schema": DISTURBANCE_WAVEFRONT_RECORD_SCHEMA,
        "record_id": f"disturbance-wavefront::{run_id}::{int(tick)}::{channel}",
        "tick": int(tick),
        "channel": str(channel),
        "source_previous_field_state_id": str(previous_field_state_id),
        "source_current_field_state_id": str(current_field_state_id),
        "source_wave_step_record_ids": [str(value) for value in wave_step_record_ids],
        "source_interaction_command_ids": [str(value) for value in interaction_command_ids],
        "source_playable_consequence_record_ids": [str(value) for value in playable_consequence_record_ids],
        "wavefront_trace_id": str(wavefront_trace_id),
        "previous_wavefront_record_id": previous_wavefront_record_id,
        "source_center_kind": str(source_center_kind),
        "source_center_grid": _finite_pair("source_center_grid", source_center_grid),
        "source_center_world": _finite_pair("source_center_world", source_center_world),
        "centroid_grid": _finite_pair("centroid_grid", centroid_grid),
        "centroid_world": _finite_pair("centroid_world", centroid_world),
        "radius_grid": _finite_float("radius_grid", radius_grid),
        "front_radius_delta_grid": _finite_float("front_radius_delta_grid", front_radius_delta_grid),
        "front_energy": _finite_float("front_energy", front_energy),
        "front_delta_energy": _finite_float("front_delta_energy", front_delta_energy),
        "front_band_count": int(front_band_count),
        "outwardness_score": _clamp01(outwardness_score),
        "attenuation_score": _clamp01(attenuation_score),
        "reflection_score": _clamp01(reflection_score),
        "absorption_score": _clamp01(absorption_score),
        "phase_signature": str(phase_signature),
        "support_digest": str(support_digest),
        "source_record_ids": source_ids,
        "is_authority_state": False,
    }


def validate_disturbance_wavefront_record(record: Mapping[str, object]) -> None:
    if record.get("schema") != DISTURBANCE_WAVEFRONT_RECORD_SCHEMA:
        raise ValueError("disturbance wavefront schema mismatch")
    if record.get("is_authority_state") is not False:
        raise ValueError("disturbance wavefront must be non-authority")
    if not record.get("channel"):
        raise ValueError("disturbance wavefront requires channel")
    if not record.get("source_previous_field_state_id") or not record.get("source_current_field_state_id"):
        raise ValueError("disturbance wavefront requires previous and current field state ids")
    if not record.get("source_record_ids"):
        raise ValueError("disturbance wavefront requires source_record_ids")
    if int(record.get("front_band_count", 0)) <= 0:
        raise ValueError("disturbance wavefront requires positive front_band_count")
    for key in ("source_center_grid", "source_center_world", "centroid_grid", "centroid_world"):
        _finite_pair(key, record.get(key, []))
    for key in (
        "radius_grid",
        "front_radius_delta_grid",
        "front_energy",
        "front_delta_energy",
        "outwardness_score",
        "attenuation_score",
        "reflection_score",
        "absorption_score",
    ):
        _finite_float(key, record.get(key, float("nan")))
    for key in ("outwardness_score", "attenuation_score", "reflection_score", "absorption_score"):
        value = float(record[key])
        if value < 0.0 or value > 1.0:
            raise ValueError(f"{key} must be in [0, 1]")
    if not str(record.get("support_digest", "")).startswith("sha256:"):
        raise ValueError("support_digest must be sha256")
    if not str(record.get("phase_signature", "")).startswith("sha256:"):
        raise ValueError("phase_signature must be sha256")


def compute_disturbance_wavefront_records(
    *,
    run_id: str,
    previous_field_state: Mapping[str, object],
    current_field_state: Mapping[str, object],
    channel: str,
    wave_step_record_ids: Sequence[str],
    interaction_command_ids: Sequence[object],
    playable_consequence_record_ids: Sequence[str],
    delta_threshold: float = 0.05,
    require_adjacent_ticks: bool = True,
    source_center_grid: Sequence[float] | None = None,
    previous_wavefront_record: Mapping[str, object] | None = None,
) -> list[dict]:
    previous_tick = _tick(previous_field_state)
    current_tick = _tick(current_field_state)
    if require_adjacent_ticks and current_tick != previous_tick + 1:
        raise ValueError("wavefront propagation records require adjacent field state ticks")
    previous_grid = _channel_grid(previous_field_state, channel)
    current_grid = _channel_grid(current_field_state, channel)
    if len(previous_grid) != len(current_grid) or any(len(a) != len(b) for a, b in zip(previous_grid, current_grid)):
        raise ValueError("previous and current channel grids must have matching shape")
    threshold = abs(float(delta_threshold))
    support: list[tuple[int, int, float, float]] = []
    signed_support: list[list[object]] = []
    total_weight = 0.0
    total_current = 0.0
    weighted_x = 0.0
    weighted_y = 0.0
    positive_energy = 0.0
    negative_energy = 0.0
    for y, row in enumerate(current_grid):
        for x, current_value in enumerate(row):
            delta = float(current_value) - float(previous_grid[y][x])
            weight = abs(delta)
            if weight < threshold:
                continue
            support.append((x, y, delta, current_value))
            signed_support.append([x, y, 1 if delta >= 0.0 else -1])
            total_weight += weight
            total_current += abs(float(current_value))
            weighted_x += x * weight
            weighted_y += y * weight
            if delta >= 0.0:
                positive_energy += weight
            else:
                negative_energy += weight
    if not support or total_weight <= 0.0:
        return []
    centroid_grid = [weighted_x / total_weight, weighted_y / total_weight]
    radius_grid = sum(
        math.hypot(float(x) - centroid_grid[0], float(y) - centroid_grid[1]) * abs(delta)
        for x, y, delta, _current_value in support
    ) / total_weight
    frame = _coordinate_frame(current_field_state)
    centroid_world = _grid_to_world(centroid_grid, frame)
    source_center_kind = "explicit_interaction_center"
    resolved_source_center_grid = list(source_center_grid) if source_center_grid is not None else None
    if resolved_source_center_grid is None:
        for command in interaction_command_ids:
            if isinstance(command, Mapping):
                payload = command.get("payload", {})
                if isinstance(payload, Mapping) and payload.get("center_grid") is not None:
                    resolved_source_center_grid = _finite_pair("command.center_grid", payload["center_grid"])
                    source_center_kind = "interaction_center"
                    break
    if resolved_source_center_grid is None and previous_wavefront_record and previous_wavefront_record.get("centroid_grid"):
        resolved_source_center_grid = _finite_pair("previous.centroid_grid", previous_wavefront_record["centroid_grid"])
        source_center_kind = "previous_wavefront_centroid"
    if resolved_source_center_grid is None:
        resolved_source_center_grid = centroid_grid
        source_center_kind = "delta_centroid"
    source_center_world = _grid_to_world(resolved_source_center_grid, frame)
    previous_radius = None
    if previous_wavefront_record and previous_wavefront_record.get("radius_grid") is not None:
        previous_radius = float(previous_wavefront_record["radius_grid"])
    radius_delta = 0.0 if previous_radius is None else radius_grid - previous_radius
    previous_delta_energy = (
        float(previous_wavefront_record["front_delta_energy"])
        if previous_wavefront_record and previous_wavefront_record.get("front_delta_energy") is not None
        else None
    )
    attenuation_score = 0.0
    if previous_delta_energy and previous_delta_energy > 1e-12:
        attenuation_score = _clamp01((previous_delta_energy - (total_weight / len(support))) / previous_delta_energy)
    support_digest = _canonical_digest(signed_support)
    phase_signature = _canonical_digest(
        [[x, y, round(delta, 5)] for x, y, delta, _current_value in support]
    )
    command_ids = [
        _record_id(command) if isinstance(command, Mapping) else str(command)
        for command in interaction_command_ids
    ]
    trace_suffix = command_ids[0] if command_ids else "unbound"
    record = build_disturbance_wavefront_record(
        run_id=run_id,
        tick=current_tick,
        channel=channel,
        previous_field_state_id=_field_state_id(previous_field_state),
        current_field_state_id=_field_state_id(current_field_state),
        wave_step_record_ids=wave_step_record_ids,
        interaction_command_ids=_unique(command_ids),
        playable_consequence_record_ids=playable_consequence_record_ids,
        wavefront_trace_id=f"wavefront-trace::{run_id}::{trace_suffix}",
        previous_wavefront_record_id=(
            str(previous_wavefront_record["record_id"])
            if previous_wavefront_record and previous_wavefront_record.get("record_id")
            else None
        ),
        source_center_grid=resolved_source_center_grid,
        source_center_world=source_center_world,
        centroid_grid=centroid_grid,
        centroid_world=centroid_world,
        radius_grid=radius_grid,
        front_radius_delta_grid=radius_delta,
        front_energy=total_current / len(support),
        front_delta_energy=total_weight / len(support),
        front_band_count=len(support),
        outwardness_score=_clamp01(max(0.0, radius_delta) / max(1.0, radius_grid)),
        attenuation_score=attenuation_score,
        reflection_score=_clamp01(negative_energy / total_weight),
        absorption_score=_clamp01(max(0.0, negative_energy - positive_energy) / max(total_weight, 1e-12)),
        support_digest=support_digest,
        phase_signature=phase_signature,
        source_center_kind=source_center_kind,
    )
    validate_disturbance_wavefront_record(record)
    return [record]


def build_material_wavefront_response_record(
    *,
    record_id: str,
    tick: int,
    wavefront_record_id: str,
    source_property_record_ids: Sequence[str],
    source_playable_consequence_record_ids: Sequence[str],
    attenuation_delta: float,
    reflection_delta: float,
    absorption_delta: float,
    transmitted_energy: float,
) -> dict:
    source_ids = _unique([wavefront_record_id, *source_property_record_ids, *source_playable_consequence_record_ids])
    return {
        "schema": MATERIAL_WAVEFRONT_RESPONSE_SCHEMA,
        "record_id": str(record_id),
        "tick": int(tick),
        "source_wavefront_record_id": str(wavefront_record_id),
        "source_property_record_ids": [str(value) for value in source_property_record_ids],
        "source_playable_consequence_record_ids": [str(value) for value in source_playable_consequence_record_ids],
        "attenuation_delta": _clamp01(attenuation_delta),
        "reflection_delta": _clamp01(reflection_delta),
        "absorption_delta": _clamp01(absorption_delta),
        "transmitted_energy": _clamp01(transmitted_energy),
        "source_record_ids": source_ids,
        "is_authority_state": False,
    }


def validate_material_wavefront_response_record(record: Mapping[str, object]) -> None:
    if record.get("schema") != MATERIAL_WAVEFRONT_RESPONSE_SCHEMA:
        raise ValueError("material wavefront response schema mismatch")
    if record.get("is_authority_state") is not False:
        raise ValueError("material wavefront response must be non-authority")
    wavefront_record_id = str(record.get("source_wavefront_record_id", ""))
    if not wavefront_record_id:
        raise ValueError("material wavefront response requires source_wavefront_record_id")
    source_record_ids = set(str(value) for value in record.get("source_record_ids", []))
    if wavefront_record_id not in source_record_ids:
        raise ValueError("material wavefront response must cite wavefront source")
    for field in ("source_property_record_ids", "source_playable_consequence_record_ids"):
        for source_id in record.get(field, []):
            if str(source_id) not in source_record_ids:
                raise ValueError(f"material wavefront response missing {source_id} in source_record_ids")
    for key in ("attenuation_delta", "reflection_delta", "absorption_delta", "transmitted_energy"):
        value = _finite_float(key, record.get(key, float("nan")))
        if value < 0.0 or value > 1.0:
            raise ValueError(f"{key} must be in [0, 1]")


def compute_material_wavefront_response_records(
    *,
    case_id: str,
    wavefront_records: Sequence[Mapping[str, object]],
    property_records: Sequence[Mapping[str, object]],
    playable_consequence_records: Sequence[Mapping[str, object]],
) -> list[dict]:
    property_ids = _unique([_record_id(record) for record in property_records])
    consequence_ids = _unique([_record_id(record) for record in playable_consequence_records])
    attenuation_values: list[float] = []
    reflection_values: list[float] = []
    for record in property_records:
        payload = record.get("payload", {})
        if isinstance(payload, Mapping):
            if payload.get("attenuation") is not None:
                attenuation_values.append(_clamp01(payload["attenuation"]))
            if payload.get("reflection") is not None:
                reflection_values.append(_clamp01(payload["reflection"]))
    consequence_absorption_bonus = 0.0
    consequence_reflection_bonus = 0.0
    for record in playable_consequence_records:
        kind = str(record.get("kind", record.get("consequence_kind", "")))
        if "dampen" in kind or "absorption" in kind:
            consequence_absorption_bonus = max(consequence_absorption_bonus, 0.2)
        if "boundary" in kind or "reflection" in kind:
            consequence_reflection_bonus = max(consequence_reflection_bonus, 0.15)
    attenuation_base = sum(attenuation_values) / len(attenuation_values) if attenuation_values else 0.0
    reflection_base = sum(reflection_values) / len(reflection_values) if reflection_values else 0.0
    records: list[dict] = []
    for index, wavefront in enumerate(wavefront_records):
        wavefront_id = str(wavefront["record_id"])
        front_delta_energy = _clamp01(wavefront.get("front_delta_energy", 0.0))
        reflection = _clamp01(max(reflection_base, wavefront.get("reflection_score", 0.0)) + consequence_reflection_bonus)
        absorption = _clamp01(max(wavefront.get("absorption_score", 0.0), 0.0) + consequence_absorption_bonus)
        attenuation = _clamp01(max(attenuation_base, wavefront.get("attenuation_score", 0.0)))
        response = build_material_wavefront_response_record(
            record_id=f"material-wavefront-response::{case_id}::{int(wavefront.get('tick', index))}::{index}",
            tick=int(wavefront.get("tick", 0)),
            wavefront_record_id=wavefront_id,
            source_property_record_ids=property_ids,
            source_playable_consequence_record_ids=consequence_ids,
            attenuation_delta=attenuation,
            reflection_delta=reflection,
            absorption_delta=absorption,
            transmitted_energy=front_delta_energy * (1.0 - attenuation) * (1.0 - absorption),
        )
        validate_material_wavefront_response_record(response)
        records.append(response)
    return records
