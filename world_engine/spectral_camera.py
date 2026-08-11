from __future__ import annotations

import hashlib
import json
import math
from typing import Iterable, Mapping, Sequence

from world_engine.wavefronts import VISIBLE_WAVEFRONT_TRANSIENT_SCHEMA


OBSERVER_POSE_SCHEMA = "observer_pose_v1"
SPECTRAL_CAMERA_MODEL_SCHEMA = "spectral_camera_model_v1"
SPECTRAL_CAMERA_SAMPLE_SCHEMA = "spectral_camera_sample_v1"
SPECTRAL_CAMERA_FRAME_SCHEMA = "spectral_camera_frame_v1"
SPECTRAL_SPATIAL_SUMMARY_SCHEMA = "spectral_spatial_summary_v1"
SPECTRAL_OCCLUSION_TRACE_SCHEMA = "spectral_occlusion_trace_v1"

FORBIDDEN_MAIN_SAMPLE_KEYS = {
    "world_xy",
    "grid_xy",
    "support_grid",
    "image_bounds",
    "material_color_name",
    "css_color",
    "viewer_color",
    "field_channel_label",
}


def _finite_vector(name: str, values: Sequence[float], length: int) -> list[float]:
    if len(values) != length:
        raise ValueError(f"{name} must have length {length}")
    result = [float(value) for value in values]
    if any(not math.isfinite(value) for value in result):
        raise ValueError(f"{name} must contain finite numbers")
    return result


def _normalize(name: str, values: Sequence[float]) -> list[float]:
    vector = _finite_vector(name, values, 3)
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude <= 1e-12:
        raise ValueError(f"{name} vector must be non-zero")
    return [value / magnitude for value in vector]


def _canonical_digest(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _pixel_digest(camera_model: Mapping[str, object], samples: Sequence[Mapping[str, object]]) -> str:
    return _canonical_digest({"camera_model": dict(camera_model), "samples": [dict(sample) for sample in samples]})


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


def build_observer_pose(
    *,
    observer_id: str,
    position_world: Sequence[float],
    forward: Sequence[float],
    up: Sequence[float],
    aperture: float = 0.18,
    near: float = 0.1,
    far: float = 96.0,
) -> dict:
    if not observer_id:
        raise ValueError("observer_id is required")
    position = _finite_vector("position_world", position_world, 3)
    forward_unit = _normalize("forward", forward)
    up_unit = _normalize("up", up)
    aperture_value = float(aperture)
    near_value = float(near)
    far_value = float(far)
    if aperture_value <= 0.0 or near_value <= 0.0 or far_value <= near_value:
        raise ValueError("aperture, near, and far must define a valid camera range")
    return {
        "schema": OBSERVER_POSE_SCHEMA,
        "observer_id": observer_id,
        "position_world": position,
        "forward": forward_unit,
        "up": up_unit,
        "aperture": aperture_value,
        "near": near_value,
        "far": far_value,
    }


def build_spectral_camera_model(
    *,
    sensor_shape: Sequence[int],
    frequency_window: Sequence[float],
    exposure: float = 1.0,
    gamma: float = 1.0,
) -> dict:
    if len(sensor_shape) != 2:
        raise ValueError("sensor_shape must have width and height")
    width, height = int(sensor_shape[0]), int(sensor_shape[1])
    if width <= 0 or height <= 0:
        raise ValueError("sensor_shape values must be positive")
    low, high = [float(value) for value in frequency_window]
    if not (0.0 < low < high):
        raise ValueError("frequency_window must be ordered positive values")
    return {
        "schema": SPECTRAL_CAMERA_MODEL_SCHEMA,
        "sensor_shape": [width, height],
        "frequency_window": [low, high],
        "frequency_bands": [
            {"name": "low", "range": [low, low + (high - low) / 3.0]},
            {
                "name": "mid",
                "range": [low + (high - low) / 3.0, low + 2.0 * (high - low) / 3.0],
            },
            {"name": "high", "range": [low + 2.0 * (high - low) / 3.0, high]},
        ],
        "exposure": float(exposure),
        "gamma": float(gamma),
        "attenuation_model": "field_density_exponential_v1",
        "occlusion_model": "density_depth_v1",
    }


def build_spectral_camera_frame(
    *,
    frame_id: str,
    observer_id: str,
    tick: int,
    observer_pose: Mapping[str, object],
    camera_model: Mapping[str, object],
    samples: Iterable[Mapping[str, object]],
    source_field_state_ids: Sequence[str],
    source_property_record_ids: Sequence[str],
    source_playable_consequence_record_ids: Sequence[str],
    source_record_ids: Sequence[str],
    source_macro_state_ids: Sequence[str] | None = None,
    source_wavefront_record_ids: Sequence[str] | None = None,
    source_material_wavefront_response_record_ids: Sequence[str] | None = None,
    spatial_summary: Mapping[str, object] | None = None,
) -> dict:
    sample_list = []
    near = float(observer_pose.get("near", 0.1))
    far = float(observer_pose.get("far", 96.0))
    for raw_sample in samples:
        sample = dict(raw_sample)
        if "observer_relative_depth" not in sample:
            sample["observer_relative_depth"] = _clamp01((float(sample.get("path_length", near)) - near) / max(1e-9, far - near))
        if "attenuation_factor" not in sample:
            sample["attenuation_factor"] = 1.0
        if "visibility_weight" not in sample:
            sample["visibility_weight"] = _clamp01(
                float(sample.get("opacity", 0.0)) * 0.7 + float(sample.get("edge_strength", 0.0)) * 0.3
            )
        if "spatial_edge_strength" not in sample:
            sample["spatial_edge_strength"] = _clamp01(float(sample.get("edge_strength", 0.0)))
        if "spatial_layer" not in sample:
            sample["spatial_layer"] = _spatial_layer(float(sample["observer_relative_depth"]))
        if "occlusion_trace" not in sample:
            sample["occlusion_trace"] = _default_occlusion_trace(sample.get("source_record_ids", source_record_ids))
        sample_list.append(sample)
    summary = dict(spatial_summary or _spatial_summary(sample_list, source_record_ids))
    return {
        "schema": SPECTRAL_CAMERA_FRAME_SCHEMA,
        "frame_id": frame_id,
        "observer_id": observer_id,
        "tick": int(tick),
        "observer_pose": dict(observer_pose),
        "camera_model": dict(camera_model),
        "sensor_shape": list(camera_model["sensor_shape"]),
        "samples": sample_list,
        "pixel_digest": _pixel_digest(camera_model, sample_list),
        "source_field_state_ids": list(source_field_state_ids),
        "source_macro_state_ids": list(source_macro_state_ids or []),
        "source_property_record_ids": list(source_property_record_ids),
        "source_playable_consequence_record_ids": list(source_playable_consequence_record_ids),
        "source_wavefront_record_ids": list(source_wavefront_record_ids or []),
        "source_material_wavefront_response_record_ids": list(source_material_wavefront_response_record_ids or []),
        "source_record_ids": list(source_record_ids),
        "spatial_summary": summary,
        "is_authority_state": False,
    }


def validate_spectral_camera_frame(frame: Mapping[str, object]) -> None:
    if frame.get("schema") != SPECTRAL_CAMERA_FRAME_SCHEMA:
        raise ValueError("spectral camera frame schema mismatch")
    if frame.get("is_authority_state") is not False:
        raise ValueError("spectral camera frame must be non-authority")
    if not frame.get("source_field_state_ids"):
        raise ValueError("spectral camera frame requires source_field_state_ids")
    if not frame.get("source_record_ids"):
        raise ValueError("spectral camera frame requires source_record_ids")
    samples = frame.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("spectral camera frame requires non-empty samples")
    spatial_summary = frame.get("spatial_summary")
    if not isinstance(spatial_summary, Mapping) or spatial_summary.get("schema") != SPECTRAL_SPATIAL_SUMMARY_SCHEMA:
        raise ValueError("spectral camera frame requires spectral_spatial_summary_v1")
    if spatial_summary.get("is_authority_state") is not False:
        raise ValueError("spectral spatial summary must be non-authority")
    for index, sample in enumerate(samples):
        forbidden = sorted(FORBIDDEN_MAIN_SAMPLE_KEYS.intersection(sample.keys()))
        if forbidden:
            raise ValueError(f"forbidden main sample key at sample {index}: {forbidden[0]}")
        if sample.get("schema") != SPECTRAL_CAMERA_SAMPLE_SCHEMA:
            raise ValueError(f"spectral camera sample {index} schema mismatch")
        if sample.get("is_authority_state") is not False:
            raise ValueError(f"spectral camera sample {index} must be non-authority")
        for spatial_key in (
            "observer_relative_depth",
            "attenuation_factor",
            "visibility_weight",
            "spatial_edge_strength",
            "spatial_layer",
        ):
            if spatial_key not in sample:
                raise ValueError(f"spectral camera sample {index} missing {spatial_key}")
        if sample.get("spatial_layer") not in {"near", "mid", "far"}:
            raise ValueError(f"spectral camera sample {index} spatial_layer mismatch")
        trace = sample.get("occlusion_trace")
        if not isinstance(trace, Mapping):
            raise ValueError(f"spectral camera sample {index} requires occlusion_trace")
        if trace.get("schema") != SPECTRAL_OCCLUSION_TRACE_SCHEMA:
            raise ValueError(f"spectral camera sample {index} occlusion trace schema mismatch")
        if trace.get("is_authority_state") is not False:
            raise ValueError(f"spectral camera sample {index} occlusion trace must be non-authority")
        trace_forbidden = sorted(FORBIDDEN_MAIN_SAMPLE_KEYS.intersection(trace.keys()))
        if trace_forbidden:
            raise ValueError(f"forbidden occlusion trace key at sample {index}: {trace_forbidden[0]}")
        for trace_key in ("visibility_transmittance", "first_surface_depth", "occluded_energy_estimate"):
            trace_value = float(trace.get(trace_key, -1.0))
            if trace_value < 0.0 or trace_value > 1.0:
                raise ValueError(f"spectral camera sample {index} occlusion trace {trace_key} out of range")
        if not trace.get("source_record_ids"):
            raise ValueError(f"spectral camera sample {index} occlusion trace requires source_record_ids")
        if not sample.get("source_record_ids"):
            raise ValueError(f"spectral camera sample {index} requires source_record_ids")
        if sample.get("transient_schema"):
            if sample.get("transient_schema") != VISIBLE_WAVEFRONT_TRANSIENT_SCHEMA:
                raise ValueError(f"spectral camera sample {index} transient schema mismatch")
            source_wavefront_ids = [str(value) for value in sample.get("source_wavefront_record_ids", [])]
            frame_wavefront_ids = {str(value) for value in frame.get("source_wavefront_record_ids", [])}
            if not source_wavefront_ids:
                raise ValueError(f"spectral camera sample {index} requires source_wavefront_record_ids")
            if not set(source_wavefront_ids).issubset(frame_wavefront_ids):
                raise ValueError(f"spectral camera sample {index} cites wavefront missing from frame")
            sample_source_ids = {str(value) for value in sample.get("source_record_ids", [])}
            if not set(source_wavefront_ids).issubset(sample_source_ids):
                raise ValueError(f"spectral camera sample {index} must cite wavefront ids in source_record_ids")


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _round_unit_interval(value: float) -> float:
    return round(_clamp01(value), 6)


def _spatial_layer(depth: float) -> str:
    if depth < 0.34:
        return "near"
    if depth < 0.67:
        return "mid"
    return "far"


def _spatial_summary(samples: Sequence[Mapping[str, object]], source_record_ids: Sequence[str]) -> dict[str, object]:
    depths = [float(sample.get("observer_relative_depth", 0.0)) for sample in samples]
    attenuations = [float(sample.get("attenuation_factor", 0.0)) for sample in samples]
    edges = [float(sample.get("spatial_edge_strength", 0.0)) for sample in samples]
    occlusions = [
        1.0 - float(sample.get("occlusion_trace", {}).get("visibility_transmittance", 1.0))
        for sample in samples
    ]
    layer_counts = {"near": 0, "mid": 0, "far": 0}
    for sample in samples:
        layer = str(sample.get("spatial_layer", "far"))
        if layer in layer_counts:
            layer_counts[layer] += 1
    return {
        "schema": SPECTRAL_SPATIAL_SUMMARY_SCHEMA,
        "depth_range": [min(depths or [0.0]), max(depths or [0.0])],
        "mean_depth": sum(depths) / max(1, len(depths)),
        "mean_attenuation": sum(attenuations) / max(1, len(attenuations)),
        "mean_spatial_edge_strength": sum(edges) / max(1, len(edges)),
        "mean_occlusion": sum(occlusions) / max(1, len(occlusions)),
        "max_occlusion": max(occlusions or [0.0]),
        "layer_counts": layer_counts,
        "source_record_ids": _unique(source_record_ids),
        "is_authority_state": False,
    }


def _property_response(property_records: Sequence[Mapping[str, object]]) -> tuple[float, float, float, float]:
    low = mid = high = 0.0
    attenuation = 0.0
    if not property_records:
        return 0.55, 0.55, 0.55, 0.2
    for record in property_records:
        payload = record.get("payload", {})
        response = payload.get("frequency_response", {}) if isinstance(payload, Mapping) else {}
        low += float(response.get("low", 0.0))
        mid += float(response.get("mid", 0.0))
        high += float(response.get("high", 0.0))
        attenuation += float(payload.get("attenuation", 0.0)) if isinstance(payload, Mapping) else 0.0
    count = float(len(property_records))
    return _clamp01(low / count), _clamp01(mid / count), _clamp01(high / count), _clamp01(attenuation / count)


def _preferred_channel_name(property_records: Sequence[Mapping[str, object]]) -> str | None:
    for record in property_records:
        payload = record.get("payload", {})
        if isinstance(payload, Mapping) and payload.get("channel"):
            return str(payload["channel"])
    return None


def _primary_channel(field_state: Mapping[str, object], preferred_channel: str | None = None) -> list[list[float]]:
    channels = field_state.get("channels")
    if not isinstance(channels, Mapping) or not channels:
        raise ValueError("field_state requires channels")
    if preferred_channel and preferred_channel in channels:
        channel = channels[preferred_channel]
    else:
        channel = next(iter(channels.values()))
    return [[float(value) for value in row] for row in channel]


def _sample_grid(channel: Sequence[Sequence[float]], gx: float, gy: float) -> float:
    height = len(channel)
    width = len(channel[0]) if height else 0
    if width == 0:
        return 0.0
    x0 = max(0, min(width - 1, int(math.floor(gx))))
    y0 = max(0, min(height - 1, int(math.floor(gy))))
    x1 = max(0, min(width - 1, x0 + 1))
    y1 = max(0, min(height - 1, y0 + 1))
    tx = _clamp01(gx - x0)
    ty = _clamp01(gy - y0)
    top = float(channel[y0][x0]) * (1.0 - tx) + float(channel[y0][x1]) * tx
    bottom = float(channel[y1][x0]) * (1.0 - tx) + float(channel[y1][x1]) * tx
    return top * (1.0 - ty) + bottom * ty


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
    grid_height = int(grid_shape[0])
    grid_width = int(grid_shape[1])
    [[min_x, min_y], [max_x, max_y]] = world_bounds
    if grid_width <= 0 or grid_height <= 0 or float(max_x) <= float(min_x) or float(max_y) <= float(min_y):
        raise ValueError("invalid coordinate_frame")
    return grid_width, grid_height, float(min_x), float(min_y), float(max_x), float(max_y)


def _world_to_grid(world_x: float, world_y: float, frame: tuple[int, int, float, float, float, float]) -> tuple[float, float]:
    grid_width, grid_height, min_x, min_y, max_x, max_y = frame
    gx = (world_x - min_x) / (max_x - min_x) * (grid_width - 1)
    gy = (world_y - min_y) / (max_y - min_y) * (grid_height - 1)
    return gx, gy


def _grid_to_world(gx: float, gy: float, frame: tuple[int, int, float, float, float, float]) -> tuple[float, float]:
    grid_width, grid_height, min_x, min_y, max_x, max_y = frame
    world_x = min_x + float(gx) / max(1, grid_width - 1) * (max_x - min_x)
    world_y = min_y + float(gy) / max(1, grid_height - 1) * (max_y - min_y)
    return world_x, world_y


def _edge_strength(channel: Sequence[Sequence[float]], gx: float, gy: float) -> float:
    left = _sample_grid(channel, gx - 1.0, gy)
    right = _sample_grid(channel, gx + 1.0, gy)
    up = _sample_grid(channel, gx, gy - 1.0)
    down = _sample_grid(channel, gx, gy + 1.0)
    return _clamp01(abs(right - left) + abs(down - up))


def _default_occlusion_trace(source_record_ids: Sequence[object]) -> dict[str, object]:
    return {
        "schema": SPECTRAL_OCCLUSION_TRACE_SCHEMA,
        "visibility_transmittance": 1.0,
        "first_surface_depth": 1.0,
        "occluded_energy_estimate": 0.0,
        "source_record_ids": _unique(source_record_ids),
        "is_authority_state": False,
    }


def _occlusion_trace(
    *,
    channel: Sequence[Sequence[float]],
    coord_frame: tuple[int, int, float, float, float, float],
    pose_x: float,
    pose_y: float,
    forward_x: float,
    forward_y: float,
    nx: float,
    ny: float,
    aperture: float,
    near: float,
    far: float,
    attenuation: float,
    source_record_ids: Sequence[object],
) -> dict[str, object]:
    steps = 9
    transmittance = 1.0
    first_surface_depth = 1.0
    occluded_energy = 0.0
    previous_energy = 0.0
    view_span = max(1.0, min(24.0, float(far) - float(near)))
    for step in range(steps):
        depth = (step + 1) / steps
        distance = float(near) + depth * view_span
        lateral = nx * aperture * 64.0 * (0.35 + depth * 0.65)
        vertical = -ny * aperture * 64.0 * (0.35 + depth * 0.65)
        world_x = pose_x + forward_x * distance + lateral
        world_y = pose_y + forward_y * distance + vertical
        gx, gy = _world_to_grid(world_x, world_y, coord_frame)
        energy = _clamp01(_sample_grid(channel, gx, gy))
        if energy > 0.08 and first_surface_depth >= 1.0:
            first_surface_depth = depth
        occluded_energy += max(0.0, previous_energy - energy) * transmittance
        transmittance *= math.exp(-float(attenuation) * energy * 0.42)
        previous_energy = max(previous_energy, energy)
    return {
        "schema": SPECTRAL_OCCLUSION_TRACE_SCHEMA,
        "visibility_transmittance": _round_unit_interval(transmittance),
        "first_surface_depth": _round_unit_interval(first_surface_depth),
        "occluded_energy_estimate": _round_unit_interval(occluded_energy),
        "source_record_ids": _unique(source_record_ids),
        "is_authority_state": False,
    }


def _delta_channel(
    previous: Sequence[Sequence[float]],
    current: Sequence[Sequence[float]],
) -> list[list[float]]:
    if len(previous) != len(current) or any(len(a) != len(b) for a, b in zip(previous, current)):
        raise ValueError("previous and current field channels must have matching shape")
    return [
        [float(current_value) - float(previous[y][x]) for x, current_value in enumerate(row)]
        for y, row in enumerate(current)
    ]


def _frequency_rgb(model: Mapping[str, object], response: tuple[float, float, float, float], energy: float) -> list[float]:
    low, mid, high, attenuation = response
    window = model["frequency_window"]
    center = (float(window[0]) + float(window[1])) / 2.0
    blue_weight = _clamp01((0.55 - center) / 0.25)
    red_weight = _clamp01((center - 0.55) / 0.25)
    green_weight = 1.0 - abs(red_weight - blue_weight) * 0.5
    transmission = math.exp(-attenuation * max(0.0, energy))
    raw_rgb = [
        _clamp01(energy * (0.35 * low + 0.65 * red_weight) * transmission),
        _clamp01(energy * (0.35 * mid + 0.65 * green_weight) * transmission),
        _clamp01(energy * (0.35 * high + 0.65 * blue_weight) * transmission),
    ]
    exposure = max(0.0, float(model.get("exposure", 1.0)))
    gamma = max(1e-6, float(model.get("gamma", 1.0)))
    return [_clamp01(math.pow(_clamp01(value * exposure), gamma)) for value in raw_rgb]


def sample_spectral_camera_frame(
    *,
    field_state: Mapping[str, object],
    observer_pose: Mapping[str, object],
    camera_model: Mapping[str, object],
    property_records: Sequence[Mapping[str, object]],
    playable_consequence_records: Sequence[Mapping[str, object]],
    source_record_ids: Sequence[str],
    previous_field_state: Mapping[str, object] | None = None,
    wavefront_records: Sequence[Mapping[str, object]] | None = None,
    material_wavefront_response_records: Sequence[Mapping[str, object]] | None = None,
) -> dict:
    preferred_channel = _preferred_channel_name(property_records)
    channel = _primary_channel(field_state, preferred_channel)
    delta_grid: list[list[float]] | None = None
    if previous_field_state is not None:
        previous_channel = _primary_channel(previous_field_state, preferred_channel)
        delta_grid = _delta_channel(previous_channel, channel)
    height = len(channel)
    width = len(channel[0]) if height else 0
    if width == 0:
        raise ValueError("field channel cannot be empty")
    coord_frame = _coordinate_frame(field_state)
    sensor_width, sensor_height = [int(value) for value in camera_model["sensor_shape"]]
    pose_x = float(observer_pose["position_world"][0])
    pose_y = float(observer_pose["position_world"][1])
    forward_x = float(observer_pose["forward"][0])
    forward_y = float(observer_pose["forward"][1])
    aperture = float(observer_pose["aperture"])
    response = _property_response(property_records)
    wavefront_records = list(wavefront_records or [])
    material_wavefront_response_records = list(material_wavefront_response_records or [])
    wavefront_ids = _unique([record.get("record_id") for record in wavefront_records])
    material_wavefront_response_ids = _unique([record.get("record_id") for record in material_wavefront_response_records])
    wavefront_energy = _clamp01(
        sum(float(record.get("front_delta_energy", 0.0)) for record in wavefront_records) / max(1, len(wavefront_records))
    )
    response_attenuation = _clamp01(
        sum(float(record.get("attenuation_delta", 0.0)) for record in material_wavefront_response_records)
        / max(1, len(material_wavefront_response_records))
    )
    response_absorption = _clamp01(
        sum(float(record.get("absorption_delta", 0.0)) for record in material_wavefront_response_records)
        / max(1, len(material_wavefront_response_records))
    )
    source_ids = _unique([*source_record_ids, *wavefront_ids, *material_wavefront_response_ids])
    property_ids = [str(record["id"]) for record in property_records if record.get("id")]
    consequence_ids = [str(record["id"]) for record in playable_consequence_records if record.get("id")]
    samples = []
    stride_x = max(1, sensor_width // 32)
    stride_y = max(1, sensor_height // 24)
    for sy in range(0, sensor_height, stride_y):
        for sx in range(0, sensor_width, stride_x):
            nx = (sx + 0.5) / sensor_width - 0.5
            ny = (sy + 0.5) / sensor_height - 0.5
            world_x = pose_x + forward_x * 8.0 + nx * aperture * 64.0
            world_y = pose_y + forward_y * 8.0 - ny * aperture * 64.0
            gx, gy = _world_to_grid(world_x, world_y, coord_frame)
            energy = _clamp01(_sample_grid(channel, gx, gy))
            edge = _edge_strength(channel, gx, gy)
            hit_distance = math.sqrt(
                (world_x - pose_x) * (world_x - pose_x)
                + (world_y - pose_y) * (world_y - pose_y)
                + float(observer_pose["position_world"][2]) * float(observer_pose["position_world"][2])
            )
            observer_depth = _clamp01(
                (hit_distance - float(observer_pose["near"]))
                / max(1e-9, float(observer_pose["far"]) - float(observer_pose["near"]))
                + (1.0 - energy) * 0.18
                + edge * 0.05
            )
            attenuation_factor = _clamp01(math.exp(-response[3] * hit_distance * (0.08 + 0.24 * energy)))
            spatial_edge = _clamp01(edge * (0.75 + 0.25 * (1.0 - attenuation_factor)) + observer_depth * 0.08)
            visibility_weight = _clamp01((energy * 0.72 + edge * 0.28) * attenuation_factor)
            local_delta = _sample_grid(delta_grid, gx, gy) if delta_grid is not None else 0.0
            delta_edge = _edge_strength(delta_grid, gx, gy) if delta_grid is not None else 0.0
            transient_signal = 0.0
            if wavefront_ids and delta_grid is not None:
                material_transmission = (1.0 - response_attenuation) * (1.0 - response_absorption)
                transient_signal = _clamp01((abs(local_delta) + 0.35 * delta_edge) * max(0.2, wavefront_energy) * material_transmission * 5.0)
            if energy <= 0.001 and edge <= 0.001 and transient_signal <= 0.001:
                continue
            rgb = _frequency_rgb(camera_model, response, energy + 0.35 * edge)
            direction = _normalize(
                "observer_relative_direction",
                (nx * aperture, -ny * aperture, -1.0),
            )
            path_length = float(observer_pose["near"]) + observer_depth * (
                float(observer_pose["far"]) - float(observer_pose["near"])
            )
            source_record_set = _unique([*source_ids, *property_ids, *consequence_ids])
            trace_source_record_ids = _unique([*source_record_ids, *property_ids])
            trace = _occlusion_trace(
                channel=channel,
                coord_frame=coord_frame,
                pose_x=pose_x,
                pose_y=pose_y,
                forward_x=forward_x,
                forward_y=forward_y,
                nx=nx,
                ny=ny,
                aperture=aperture,
                near=float(observer_pose["near"]),
                far=float(observer_pose["far"]),
                attenuation=response[3],
                source_record_ids=trace_source_record_ids,
            )
            attenuation_factor = _clamp01(attenuation_factor * (0.35 + trace["visibility_transmittance"] * 0.65))
            visibility_weight = _clamp01(visibility_weight * (0.45 + trace["visibility_transmittance"] * 0.55))
            sample = {
                    "schema": SPECTRAL_CAMERA_SAMPLE_SCHEMA,
                    "sensor_xy": [sx, sy],
                    "observer_relative_direction": direction,
                    "path_length": path_length,
                    "frequency_rgb": rgb,
                    "intensity": _clamp01(sum(rgb) / 3.0),
                    "opacity": _clamp01(energy),
                    "occlusion_depth": _clamp01(1.0 - math.exp(-energy * (1.0 + response[3]))),
                    "edge_strength": edge,
                    "observer_relative_depth": observer_depth,
                    "attenuation_factor": attenuation_factor,
                    "visibility_weight": visibility_weight,
                    "spatial_edge_strength": spatial_edge,
                    "spatial_layer": _spatial_layer(observer_depth),
                    "occlusion_trace": trace,
                    "source_record_ids": source_record_set,
                    "is_authority_state": False,
                }
            if transient_signal > 0.001 and wavefront_ids:
                arrival = _clamp01((path_length - float(observer_pose["near"])) / (float(observer_pose["far"]) - float(observer_pose["near"])))
                phase = _clamp01((local_delta + 1.0) / 2.0)
                transient_rgb = [
                    _clamp01(rgb[0] + transient_signal * 0.45),
                    _clamp01(rgb[1] + transient_signal * (0.25 + 0.50 * phase)),
                    _clamp01(rgb[2] + transient_signal * (0.75 - 0.35 * phase)),
                ]
                sample.update(
                    {
                        "transient_schema": VISIBLE_WAVEFRONT_TRANSIENT_SCHEMA,
                        "wavefront_intensity": transient_signal,
                        "wavefront_phase": phase,
                        "wavefront_edge": _clamp01(delta_edge),
                        "wavefront_arrival": arrival,
                        "wavefront_frequency_rgb": transient_rgb,
                        "source_wavefront_record_ids": list(wavefront_ids),
                    }
                )
            samples.append(sample)
    if not samples and delta_grid is not None and wavefront_ids:
        strongest: tuple[int, int, float] | None = None
        for y, row in enumerate(delta_grid):
            for x, delta in enumerate(row):
                if strongest is None or abs(delta) > abs(strongest[2]):
                    strongest = (x, y, float(delta))
        if strongest is not None and abs(strongest[2]) > 0.001:
            grid_x, grid_y, local_delta = strongest
            world_x, world_y = _grid_to_world(grid_x, grid_y, coord_frame)
            nx = (world_x - pose_x - forward_x * 8.0) / max(1e-12, aperture * 64.0)
            ny = -(world_y - pose_y - forward_y * 8.0) / max(1e-12, aperture * 64.0)
            if -0.5 <= nx <= 0.5 and -0.5 <= ny <= 0.5:
                sx = int(round((nx + 0.5) * sensor_width - 0.5))
                sy = int(round((ny + 0.5) * sensor_height - 0.5))
                energy = _clamp01(_sample_grid(channel, grid_x, grid_y))
                edge = _edge_strength(channel, grid_x, grid_y)
                hit_distance = math.sqrt(
                    (world_x - pose_x) * (world_x - pose_x)
                    + (world_y - pose_y) * (world_y - pose_y)
                    + float(observer_pose["position_world"][2]) * float(observer_pose["position_world"][2])
                )
                observer_depth = _clamp01(
                    (hit_distance - float(observer_pose["near"]))
                    / max(1e-9, float(observer_pose["far"]) - float(observer_pose["near"]))
                    + (1.0 - energy) * 0.18
                    + edge * 0.05
                )
                attenuation_factor = _clamp01(math.exp(-response[3] * hit_distance * (0.08 + 0.24 * energy)))
                spatial_edge = _clamp01(edge * (0.75 + 0.25 * (1.0 - attenuation_factor)) + observer_depth * 0.08)
                visibility_weight = _clamp01((energy * 0.72 + edge * 0.28) * attenuation_factor)
                rgb = _frequency_rgb(camera_model, response, energy + 0.35 * edge)
                direction = _normalize(
                    "observer_relative_direction",
                    (nx * aperture, -ny * aperture, -1.0),
                )
                path_length = float(observer_pose["near"]) + observer_depth * (
                    float(observer_pose["far"]) - float(observer_pose["near"])
                )
                material_transmission = (1.0 - response_attenuation) * (1.0 - response_absorption)
                transient_signal = _clamp01(abs(local_delta) * max(0.2, wavefront_energy) * material_transmission * 5.0)
                phase = _clamp01((local_delta + 1.0) / 2.0)
                source_record_set = _unique([*source_ids, *property_ids, *consequence_ids])
                trace_source_record_ids = _unique([*source_record_ids, *property_ids])
                trace = _occlusion_trace(
                    channel=channel,
                    coord_frame=coord_frame,
                    pose_x=pose_x,
                    pose_y=pose_y,
                    forward_x=forward_x,
                    forward_y=forward_y,
                    nx=nx,
                    ny=ny,
                    aperture=aperture,
                    near=float(observer_pose["near"]),
                    far=float(observer_pose["far"]),
                    attenuation=response[3],
                    source_record_ids=trace_source_record_ids,
                )
                attenuation_factor = _clamp01(attenuation_factor * (0.35 + trace["visibility_transmittance"] * 0.65))
                visibility_weight = _clamp01(visibility_weight * (0.45 + trace["visibility_transmittance"] * 0.55))
                samples.append(
                    {
                        "schema": SPECTRAL_CAMERA_SAMPLE_SCHEMA,
                        "sensor_xy": [max(0, min(sensor_width - 1, sx)), max(0, min(sensor_height - 1, sy))],
                        "observer_relative_direction": direction,
                        "path_length": path_length,
                        "frequency_rgb": rgb,
                        "intensity": _clamp01(sum(rgb) / 3.0),
                        "opacity": _clamp01(energy),
                        "occlusion_depth": _clamp01(1.0 - math.exp(-energy * (1.0 + response[3]))),
                        "edge_strength": edge,
                        "observer_relative_depth": observer_depth,
                        "attenuation_factor": attenuation_factor,
                        "visibility_weight": visibility_weight,
                        "spatial_edge_strength": spatial_edge,
                        "spatial_layer": _spatial_layer(observer_depth),
                        "occlusion_trace": trace,
                        "transient_schema": VISIBLE_WAVEFRONT_TRANSIENT_SCHEMA,
                        "wavefront_intensity": transient_signal,
                        "wavefront_phase": phase,
                        "wavefront_edge": 0.0,
                        "wavefront_arrival": _clamp01((path_length - float(observer_pose["near"])) / (float(observer_pose["far"]) - float(observer_pose["near"]))),
                        "wavefront_frequency_rgb": [
                            _clamp01(rgb[0] + transient_signal * 0.45),
                            _clamp01(rgb[1] + transient_signal * (0.25 + 0.50 * phase)),
                            _clamp01(rgb[2] + transient_signal * (0.75 - 0.35 * phase)),
                        ],
                        "source_wavefront_record_ids": list(wavefront_ids),
                        "source_record_ids": source_record_set,
                        "is_authority_state": False,
                    }
                )
    frame = build_spectral_camera_frame(
        frame_id=f"spectral-camera-frame::{observer_pose['observer_id']}::{field_state.get('tick', 0)}",
        observer_id=str(observer_pose["observer_id"]),
        tick=int(field_state.get("tick", 0)),
        observer_pose=observer_pose,
        camera_model=camera_model,
        samples=samples,
        source_field_state_ids=[str(field_state.get("id", f"field-state::tick::{field_state.get('tick', 0)}"))],
        source_property_record_ids=property_ids,
        source_playable_consequence_record_ids=consequence_ids,
        source_wavefront_record_ids=wavefront_ids,
        source_material_wavefront_response_record_ids=material_wavefront_response_ids,
        source_record_ids=_unique([*source_ids, *property_ids, *consequence_ids]),
        spatial_summary=_spatial_summary(samples, _unique([*source_ids, *property_ids, *consequence_ids])),
    )
    validate_spectral_camera_frame(frame)
    return frame


def canonical_spectral_camera_pixel_digest(camera_frame: Mapping[str, object]) -> str:
    return _pixel_digest(camera_frame.get("camera_model", {}), camera_frame.get("samples", []))
