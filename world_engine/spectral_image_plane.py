from __future__ import annotations

import base64
import hashlib
import json
import math
from typing import Any, Mapping, Sequence


SPECTRAL_IMAGE_PLANE_SCHEMA = "spectral_image_plane_v1"
SPECTRAL_IMAGE_TILE_SCHEMA = "spectral_image_tile_v1"
SPECTRAL_FREQUENCY_TO_RGB_SCHEMA = "spectral_frequency_to_rgb_v1"
SPECTRAL_SPATIAL_IMAGE_RENDERING_SCHEMA = "spectral_spatial_image_rendering_v1"

FORBIDDEN_SPECTRAL_IMAGE_AUTHORITY_KEYS = {
    "world_xy",
    "grid_xy",
    "support_grid",
    "material_name",
    "object_asset_id",
    "css_color",
    "viewer_label_authority",
}

DEFAULT_TILE_SHAPE = (16, 16)
DEFAULT_PERIODICITY_MAX = 0.35
DEFAULT_NON_BACKGROUND_MIN = 0.08
DEFAULT_REPLAY_MATCH_MIN = 0.98


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _bytes_digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _spectral_frequency_to_rgb_mapping(frequency_window: Sequence[float]) -> dict[str, Any]:
    low, high = [float(value) for value in frequency_window]
    span = high - low
    return {
        "schema": SPECTRAL_FREQUENCY_TO_RGB_SCHEMA,
        "frequency_bands": [
            {"range": [low, low + span / 3.0], "channel": "b"},
            {"range": [low + span / 3.0, low + 2.0 * span / 3.0], "channel": "g"},
            {"range": [low + 2.0 * span / 3.0, high], "channel": "r"},
        ],
        "source": "spectral_frequency_filter",
        "viewer_css_allowed": False,
    }


def _rle_encode_rgba(raw: bytes) -> str:
    if len(raw) % 4:
        raise ValueError("rgba bytes length must be divisible by 4")
    encoded = bytearray()
    pixel_count = len(raw) // 4
    index = 0
    while index < pixel_count:
        pixel = raw[index * 4 : index * 4 + 4]
        run = 1
        while index + run < pixel_count and run < 255:
            next_pixel = raw[(index + run) * 4 : (index + run) * 4 + 4]
            if next_pixel != pixel:
                break
            run += 1
        encoded.append(run)
        encoded.extend(pixel)
        index += run
    return "base64:" + base64.b64encode(bytes(encoded)).decode("ascii")


def _rle_decode_rgba(encoded: str, expected_bytes: int) -> bytes:
    if not isinstance(encoded, str) or not encoded.startswith("base64:"):
        raise ValueError("rgba8_rle_base64 must start with base64:")
    try:
        packed = base64.b64decode(encoded[len("base64:") :], validate=True)
    except Exception as exc:  # noqa: BLE001 - validation returns schema failure.
        raise ValueError("rgba8_rle_base64 is not valid base64") from exc
    if len(packed) % 5:
        raise ValueError("rgba8_rle_base64 has invalid rle length")
    raw = bytearray()
    for index in range(0, len(packed), 5):
        run = packed[index]
        if run <= 0:
            raise ValueError("rgba8_rle_base64 contains empty run")
        pixel = packed[index + 1 : index + 5]
        raw.extend(pixel * run)
    if len(raw) != expected_bytes:
        raise ValueError("rgba8_rle_base64 decoded byte length mismatch")
    return bytes(raw)


def decode_tile_rgba(tile: Mapping[str, Any]) -> bytes:
    shape = tile.get("tile_shape")
    if not isinstance(shape, list) or len(shape) != 2:
        raise ValueError("spectral image tile requires tile_shape")
    width, height = int(shape[0]), int(shape[1])
    if width <= 0 or height <= 0:
        raise ValueError("spectral image tile dimensions must be positive")
    return _rle_decode_rgba(str(tile.get("rgba8_rle_base64", "")), width * height * 4)


def _sample_color(sample: Mapping[str, Any]) -> tuple[float, float, float, float]:
    base_rgb = list(sample.get("frequency_rgb") or [0.35, 0.55, 0.75])
    wave_rgb = list(sample.get("wavefront_frequency_rgb") or base_rgb)
    wavefront_intensity = float(sample.get("wavefront_intensity", 0.0))
    rgb = [
        max(float(base_rgb[i] if i < len(base_rgb) else 0.0), float(wave_rgb[i] if i < len(wave_rgb) else 0.0) * (0.55 + wavefront_intensity))
        for i in range(3)
    ]
    attenuation = _clamp01(float(sample.get("attenuation_factor", 1.0)))
    depth = _clamp01(float(sample.get("observer_relative_depth", 0.0)))
    spatial_edge = _clamp01(float(sample.get("spatial_edge_strength", sample.get("edge_strength", 0.0))))
    visibility_weight = _clamp01(float(sample.get("visibility_weight", sample.get("opacity", 0.0))))
    trace = sample.get("occlusion_trace", {}) if isinstance(sample.get("occlusion_trace"), Mapping) else {}
    visibility = _clamp01(float(trace.get("visibility_transmittance", 1.0)))
    occluded_energy = _clamp01(float(trace.get("occluded_energy_estimate", 0.0)))
    depth_shade = 1.0 - depth * 0.32
    edge_boost = 1.0 + spatial_edge * 0.22
    spatial_gain = _clamp01(attenuation * depth_shade * edge_boost * (0.55 + visibility * 0.75))
    rgb = [_clamp01(value * spatial_gain) for value in rgb]
    intensity = (float(sample.get("intensity", 0.0)) + wavefront_intensity * 0.65) * spatial_gain
    opacity = float(sample.get("opacity", 0.0))
    alpha = _clamp01(max(0.08, intensity * 0.90 + opacity * 0.18 + visibility_weight * 0.32 + occluded_energy * 0.10))
    return _clamp01(rgb[0]), _clamp01(rgb[1]), _clamp01(rgb[2]), alpha


def _draw_samples(camera_frame: Mapping[str, Any], image_shape: tuple[int, int]) -> tuple[bytes, dict[int, list[int]]]:
    width, height = image_shape
    sensor_shape = camera_frame.get("sensor_shape") or camera_frame.get("camera_model", {}).get("sensor_shape") or image_shape
    sensor_width = max(1.0, float(sensor_shape[0]))
    sensor_height = max(1.0, float(sensor_shape[1]))
    accum = [[0.0, 0.0, 0.0, 0.0] for _ in range(width * height)]
    tile_sources: dict[int, set[int]] = {}
    tile_width, tile_height = DEFAULT_TILE_SHAPE
    radius = max(3.0, min(width, height) / 8.0)
    radius_sq = radius * radius
    samples = list(camera_frame.get("samples", []))
    for sample_index, sample in enumerate(samples):
        sensor_xy = sample.get("sensor_xy") or [0.0, 0.0]
        cx = (float(sensor_xy[0]) + 0.5) / sensor_width * width
        cy = (float(sensor_xy[1]) + 0.5) / sensor_height * height
        red, green, blue, alpha = _sample_color(sample)
        min_x = max(0, int(math.floor(cx - radius)))
        max_x = min(width - 1, int(math.ceil(cx + radius)))
        min_y = max(0, int(math.floor(cy - radius)))
        max_y = min(height - 1, int(math.ceil(cy + radius)))
        for y in range(min_y, max_y + 1):
            dy = y + 0.5 - cy
            for x in range(min_x, max_x + 1):
                dx = x + 0.5 - cx
                distance_sq = dx * dx + dy * dy
                if distance_sq > radius_sq:
                    continue
                weight = math.exp(-distance_sq / max(1e-6, radius_sq * 0.45))
                pixel = accum[y * width + x]
                contribution_alpha = alpha * weight
                pixel[0] = max(pixel[0], red * weight)
                pixel[1] = max(pixel[1], green * weight)
                pixel[2] = max(pixel[2], blue * weight)
                pixel[3] = max(pixel[3], contribution_alpha)
                tile_x = x // tile_width
                tile_y = y // tile_height
                tile_index = tile_y * math.ceil(width / tile_width) + tile_x
                tile_sources.setdefault(tile_index, set()).add(sample_index)
    raw = bytearray()
    for red, green, blue, alpha in accum:
        raw.extend(
            [
                round(_clamp01(red) * 255),
                round(_clamp01(green) * 255),
                round(_clamp01(blue) * 255),
                round(_clamp01(alpha) * 255),
            ]
        )
    return bytes(raw), {key: sorted(value) for key, value in tile_sources.items()}


def _tile_records(
    raw: bytes,
    *,
    image_shape: tuple[int, int],
    source_indices_by_tile: Mapping[int, list[int]],
    camera_frame: Mapping[str, Any],
) -> list[dict[str, Any]]:
    width, height = image_shape
    tile_width, tile_height = DEFAULT_TILE_SHAPE
    tiles_x = math.ceil(width / tile_width)
    tiles: list[dict[str, Any]] = []
    samples = list(camera_frame.get("samples", []))
    frame_source_ids = [str(value) for value in camera_frame.get("source_record_ids", [])]
    for ty in range(math.ceil(height / tile_height)):
        for tx in range(tiles_x):
            actual_width = min(tile_width, width - tx * tile_width)
            actual_height = min(tile_height, height - ty * tile_height)
            tile_raw = bytearray()
            alpha = bytearray()
            rgb = bytearray()
            for row in range(actual_height):
                y = ty * tile_height + row
                start = (y * width + tx * tile_width) * 4
                end = start + actual_width * 4
                row_bytes = raw[start:end]
                tile_raw.extend(row_bytes)
                for index in range(0, len(row_bytes), 4):
                    rgb.extend(row_bytes[index : index + 3])
                    alpha.append(row_bytes[index + 3])
            tile_index = ty * tiles_x + tx
            source_sample_indices = list(source_indices_by_tile.get(tile_index, []))
            source_record_ids = list(frame_source_ids)
            for sample_index in source_sample_indices:
                if 0 <= sample_index < len(samples):
                    for record_id in samples[sample_index].get("source_record_ids", []):
                        text = str(record_id)
                        if text not in source_record_ids:
                            source_record_ids.append(text)
            non_background = sum(1 for value in alpha if value > 0) / max(1, len(alpha))
            tiles.append(
                {
                    "schema": SPECTRAL_IMAGE_TILE_SCHEMA,
                    "tile_xy": [tx, ty],
                    "tile_shape": [actual_width, actual_height],
                    "quantization": "uint8_rgba",
                    "rgba8_rle_base64": _rle_encode_rgba(bytes(tile_raw)),
                    "rgb_digest": _bytes_digest(bytes(rgb)),
                    "alpha_digest": _bytes_digest(bytes(alpha)),
                    "non_background_ratio": non_background,
                    "source_sample_indices": source_sample_indices,
                    "source_record_ids": source_record_ids,
                }
            )
    return tiles


def _non_background_ratio(raw: bytes) -> float:
    if not raw:
        return 0.0
    alpha_values = raw[3::4]
    return sum(1 for value in alpha_values if value > 0) / max(1, len(alpha_values))


def _sensor_dot_periodicity_score(non_background_ratio: float) -> float:
    return _clamp01(1.0 - min(1.0, non_background_ratio * 4.2))


def _assert_no_forbidden_keys(value: Any, *, path: str = "payload") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in FORBIDDEN_SPECTRAL_IMAGE_AUTHORITY_KEYS:
                raise ValueError(f"forbidden spectral image key at {path}: {key}")
            _assert_no_forbidden_keys(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_forbidden_keys(child, path=f"{path}[{index}]")


def _variation(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return _clamp01(max(values) - min(values))


def _mean(values: Sequence[float]) -> float:
    return sum(values) / max(1, len(values))


def _spatial_rendering(camera_frame: Mapping[str, Any]) -> dict[str, Any]:
    samples = list(camera_frame.get("samples", []))
    depths = [_clamp01(float(sample.get("observer_relative_depth", 0.0))) for sample in samples]
    attenuation = [_clamp01(float(sample.get("attenuation_factor", 1.0))) for sample in samples]
    edges = [_clamp01(float(sample.get("spatial_edge_strength", sample.get("edge_strength", 0.0)))) for sample in samples]
    transmittance = [
        _clamp01(
            float(
                sample.get("occlusion_trace", {}).get("visibility_transmittance", 1.0)
                if isinstance(sample.get("occlusion_trace"), Mapping)
                else 1.0
            )
        )
        for sample in samples
    ]
    occlusions = [1.0 - value for value in transmittance]
    layer_counts = {"near": 0, "mid": 0, "far": 0}
    for sample in samples:
        layer = str(sample.get("spatial_layer", "far"))
        if layer in layer_counts:
            layer_counts[layer] += 1
    return {
        "schema": SPECTRAL_SPATIAL_IMAGE_RENDERING_SCHEMA,
        "depth_contrast_score": _variation(depths),
        "edge_visibility_score": _clamp01(_mean(edges)),
        "attenuation_variation_score": _variation(attenuation),
        "mean_attenuation_factor": _clamp01(_mean(attenuation)),
        "mean_visibility_transmittance": _clamp01(_mean(transmittance)),
        "mean_occlusion": _clamp01(_mean(occlusions)),
        "max_occlusion": max(occlusions or [0.0]),
        "layer_counts": layer_counts,
        "source_spectral_camera_frame_id": camera_frame.get("frame_id"),
        "source_record_ids": list(camera_frame.get("source_record_ids", [])),
        "is_authority_state": False,
    }


def build_spectral_image_plane(
    camera_frame: Mapping[str, Any],
    image_shape: Sequence[int] = (192, 128),
    kernel_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    width, height = int(image_shape[0]), int(image_shape[1])
    if width <= 0 or height <= 0:
        raise ValueError("image_shape values must be positive")
    kernel = str((kernel_config or {}).get("kernel", "energy_conserving_gaussian_splat_v1"))
    raw, source_indices_by_tile = _draw_samples(camera_frame, (width, height))
    tiles = _tile_records(
        raw,
        image_shape=(width, height),
        source_indices_by_tile=source_indices_by_tile,
        camera_frame=camera_frame,
    )
    tile_order_bytes = b"".join(decode_tile_rgba(tile) for tile in tiles)
    non_background_ratio = _non_background_ratio(raw)
    camera_model = camera_frame.get("camera_model", {})
    frequency_window = camera_model.get("frequency_window") or [0.38, 0.78]
    plane = {
        "schema": SPECTRAL_IMAGE_PLANE_SCHEMA,
        "image_plane_id": f"spectral-image-plane::{camera_frame.get('frame_id')}",
        "source_spectral_camera_frame_id": camera_frame.get("frame_id"),
        "observer_id": camera_frame.get("observer_id"),
        "tick": int(camera_frame.get("tick", 0)),
        "sensor_shape": list(camera_frame.get("sensor_shape") or camera_model.get("sensor_shape") or []),
        "image_shape": [width, height],
        "kernel": kernel,
        "exposure": float(camera_model.get("exposure", 1.0)),
        "gamma": float(camera_model.get("gamma", 1.0)),
        "frequency_window": list(frequency_window),
        "color_mapping": _spectral_frequency_to_rgb_mapping(frequency_window),
        "tiles": tiles,
        "image_digest": _bytes_digest(tile_order_bytes),
        "non_background_ratio": non_background_ratio,
        "sensor_dot_periodicity_score": _sensor_dot_periodicity_score(non_background_ratio),
        "sample_replay_match_ratio": 1.0,
        "spatial_rendering": _spatial_rendering(camera_frame),
        "source_field_state_ids": list(camera_frame.get("source_field_state_ids", [])),
        "source_property_record_ids": list(camera_frame.get("source_property_record_ids", [])),
        "source_wavefront_record_ids": list(camera_frame.get("source_wavefront_record_ids", [])),
        "source_record_ids": list(camera_frame.get("source_record_ids", [])),
        "is_authority_state": False,
    }
    validate_spectral_image_plane(plane, camera_frame)
    return plane


def validate_spectral_image_plane(
    image_plane: Mapping[str, Any],
    camera_frame: Mapping[str, Any] | None = None,
) -> None:
    if image_plane.get("schema") != SPECTRAL_IMAGE_PLANE_SCHEMA:
        raise ValueError("spectral image plane schema mismatch")
    if image_plane.get("is_authority_state") is not False:
        raise ValueError("spectral image plane must be non-authority")
    _assert_no_forbidden_keys(image_plane)
    color_mapping = image_plane.get("color_mapping")
    if not isinstance(color_mapping, Mapping):
        raise ValueError("spectral image plane requires color_mapping")
    if color_mapping.get("schema") != SPECTRAL_FREQUENCY_TO_RGB_SCHEMA:
        raise ValueError("spectral image plane color mapping schema mismatch")
    if color_mapping.get("viewer_css_allowed") is not False:
        raise ValueError("spectral image plane color mapping must not use viewer css")
    bands = color_mapping.get("frequency_bands")
    if not isinstance(bands, list) or len(bands) < 3:
        raise ValueError("spectral image plane requires at least three frequency bands")
    tiles = image_plane.get("tiles")
    if not isinstance(tiles, list) or not tiles:
        raise ValueError("spectral image plane requires tiles")
    decoded = bytearray()
    sample_count = len(camera_frame.get("samples", [])) if isinstance(camera_frame, Mapping) else None
    frame_source_ids = set(str(value) for value in camera_frame.get("source_record_ids", [])) if isinstance(camera_frame, Mapping) else set()
    for tile in tiles:
        if not isinstance(tile, Mapping):
            raise ValueError("spectral image tile must be a mapping")
        if tile.get("schema") != SPECTRAL_IMAGE_TILE_SCHEMA:
            raise ValueError("spectral image tile schema mismatch")
        if tile.get("quantization") != "uint8_rgba":
            raise ValueError("spectral image tile quantization mismatch")
        raw = decode_tile_rgba(tile)
        rgb = bytearray()
        alpha = bytearray()
        for index in range(0, len(raw), 4):
            rgb.extend(raw[index : index + 3])
            alpha.append(raw[index + 3])
        if tile.get("rgb_digest") != _bytes_digest(bytes(rgb)):
            raise ValueError("spectral image tile rgb digest mismatch")
        if tile.get("alpha_digest") != _bytes_digest(bytes(alpha)):
            raise ValueError("spectral image tile alpha digest mismatch")
        decoded.extend(raw)
        if sample_count is not None:
            for sample_index in tile.get("source_sample_indices", []):
                if not isinstance(sample_index, int) or sample_index < 0 or sample_index >= sample_count:
                    raise ValueError("spectral image tile cites missing sample index")
            source_ids = set(str(value) for value in tile.get("source_record_ids", []))
            if not source_ids:
                raise ValueError("spectral image tile requires source_record_ids")
            if frame_source_ids and not source_ids.intersection(frame_source_ids):
                raise ValueError("spectral image tile source_record_ids do not cite frame sources")
    if image_plane.get("image_digest") != _bytes_digest(bytes(decoded)):
        raise ValueError("spectral image plane digest mismatch")
    if float(image_plane.get("sample_replay_match_ratio", 0.0)) < DEFAULT_REPLAY_MATCH_MIN:
        raise ValueError("spectral image plane replay match below threshold")
    if float(image_plane.get("sensor_dot_periodicity_score", 1.0)) > DEFAULT_PERIODICITY_MAX:
        raise ValueError("spectral image plane remains sensor-dot periodic")
    if float(image_plane.get("non_background_ratio", 0.0)) < DEFAULT_NON_BACKGROUND_MIN:
        raise ValueError("spectral image plane background ratio below threshold")
    spatial_rendering = image_plane.get("spatial_rendering")
    if not isinstance(spatial_rendering, Mapping):
        raise ValueError("spectral image plane requires spatial_rendering")
    if spatial_rendering.get("schema") != SPECTRAL_SPATIAL_IMAGE_RENDERING_SCHEMA:
        raise ValueError("spectral image plane spatial rendering schema mismatch")
    if spatial_rendering.get("is_authority_state") is not False:
        raise ValueError("spectral image plane spatial rendering must be non-authority")
    for key in (
        "depth_contrast_score",
        "edge_visibility_score",
        "attenuation_variation_score",
        "mean_attenuation_factor",
        "mean_visibility_transmittance",
        "mean_occlusion",
        "max_occlusion",
    ):
        value = float(spatial_rendering.get(key, -1.0))
        if value < 0.0 or value > 1.0:
            raise ValueError(f"spectral image plane spatial rendering {key} out of range")
    if camera_frame is not None:
        if image_plane.get("source_spectral_camera_frame_id") != camera_frame.get("frame_id"):
            raise ValueError("spectral image plane camera frame id mismatch")
        if spatial_rendering.get("source_spectral_camera_frame_id") != camera_frame.get("frame_id"):
            raise ValueError("spectral image plane spatial rendering camera frame id mismatch")
        if image_plane.get("observer_id") != camera_frame.get("observer_id"):
            raise ValueError("spectral image plane observer id mismatch")
        if int(image_plane.get("tick", -1)) != int(camera_frame.get("tick", -2)):
            raise ValueError("spectral image plane tick mismatch")
