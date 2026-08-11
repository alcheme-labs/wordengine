from __future__ import annotations

import base64
import hashlib
import json
import math
from typing import Any, Mapping, Sequence

from world_engine.implicit_field import (
    build_implicit_field_evaluation_record,
    evaluate_implicit_field,
    validate_implicit_field_evaluation_record,
    validate_implicit_field_state,
)
from world_engine.implicit_observation_channels import (
    build_rgb8_observation_channel_tile,
    build_u16_observation_channel_tile,
    summarize_depth_channel,
    summarize_scalar_channel,
    validate_implicit_observation_channel_tile,
)


IMPLICIT_OBSERVER_PATH_SCHEMA = "implicit_observer_path_record"
IMPLICIT_RAY_SAMPLE_SCHEMA = "implicit_ray_sample_record"
IMPLICIT_SPECTRAL_IMAGE_PLANE_SCHEMA = "implicit_spectral_image_plane"
IMPLICIT_IMAGE_TILE_SCHEMA = "spectral_image_tile_v1"

FORBIDDEN_IMPLICIT_VIEWER_AUTHORITY_KEYS = {
    "css_color",
    "viewer_shape",
    "viewer_label",
    "viewer_transform",
    "canvas_pixels",
    "mesh",
    "sprite",
    "object_asset_id",
}


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _short_digest(value: str) -> str:
    return str(value).replace("sha256:", "")[:12]


def _assert_no_forbidden_keys(value: Any, *, path: str = "payload") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in FORBIDDEN_IMPLICIT_VIEWER_AUTHORITY_KEYS:
                raise ValueError(f"forbidden implicit viewer authority key at {path}: {key}")
            _assert_no_forbidden_keys(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_forbidden_keys(child, path=f"{path}[{index}]")


def _finite_vector(values: Sequence[Any], *, name: str, length: int) -> list[float]:
    if len(values) != length:
        raise ValueError(f"{name} must have length {length}")
    result = [float(value) for value in values]
    if not all(math.isfinite(value) for value in result):
        raise ValueError(f"{name} values must be finite")
    return result


def _sub(left: Sequence[float], right: Sequence[float]) -> list[float]:
    return [float(left[index]) - float(right[index]) for index in range(3)]


def _add(left: Sequence[float], right: Sequence[float]) -> list[float]:
    return [float(left[index]) + float(right[index]) for index in range(3)]


def _scale(vector: Sequence[float], value: float) -> list[float]:
    return [float(item) * float(value) for item in vector]


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(float(left[index]) * float(right[index]) for index in range(3))


def _cross(left: Sequence[float], right: Sequence[float]) -> list[float]:
    return [
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    ]


def _norm(vector: Sequence[float]) -> float:
    return math.sqrt(_dot(vector, vector))


def _normalize(vector: Sequence[float]) -> list[float]:
    length = _norm(vector)
    if length <= 1e-12:
        raise ValueError("cannot normalize zero vector")
    return [float(value) / length for value in vector]


def _rle_encode_rgba(raw: bytes) -> str:
    encoded = bytearray()
    pixel_count = len(raw) // 4
    index = 0
    while index < pixel_count:
        pixel = raw[index * 4 : index * 4 + 4]
        run = 1
        while index + run < pixel_count and run < 255:
            if raw[(index + run) * 4 : (index + run) * 4 + 4] != pixel:
                break
            run += 1
        encoded.append(run)
        encoded.extend(pixel)
        index += run
    return "base64:" + base64.b64encode(bytes(encoded)).decode("ascii")


def _validate_pose(camera_pose: Mapping[str, Any]) -> None:
    origin = _finite_vector(camera_pose.get("origin", []), name="camera_pose.origin", length=3)
    look_at = _finite_vector(camera_pose.get("look_at", []), name="camera_pose.look_at", length=3)
    up = _finite_vector(camera_pose.get("up", [0.0, 0.0, 1.0]), name="camera_pose.up", length=3)
    _normalize(_sub(look_at, origin))
    _normalize(up)


def build_implicit_observer_path_record(
    observer_path_id: str,
    observer_id: str,
    tick_window: Sequence[int],
    camera_pose_records: Sequence[Mapping[str, Any]],
    source_record_ids: Sequence[str],
) -> dict[str, Any]:
    records = [dict(record) for record in camera_pose_records]
    for record in records:
        if "tick" not in record or "camera_pose" not in record:
            raise ValueError("observer path pose records require tick and camera_pose")
        _validate_pose(record["camera_pose"])
    payload = {
        "schema": IMPLICIT_OBSERVER_PATH_SCHEMA,
        "observer_path_id": str(observer_path_id),
        "observer_id": str(observer_id),
        "tick_window": [int(value) for value in tick_window],
        "camera_pose_records": records,
        "source_record_ids": [str(value) for value in source_record_ids],
        "is_authority_state": False,
    }
    payload["path_digest"] = _canonical_digest(
        {
            "observer_id": payload["observer_id"],
            "tick_window": payload["tick_window"],
            "camera_pose_records": payload["camera_pose_records"],
        }
    )
    validate_implicit_observer_path_record(payload)
    return payload


def validate_implicit_observer_path_record(record: Mapping[str, Any]) -> None:
    if record.get("schema") != IMPLICIT_OBSERVER_PATH_SCHEMA:
        raise ValueError("implicit observer path schema mismatch")
    if record.get("is_authority_state") is not False:
        raise ValueError("implicit observer path must be non-authority")
    if len(record.get("tick_window", [])) != 2:
        raise ValueError("implicit observer path requires tick window")
    for pose_record in record.get("camera_pose_records", []):
        _validate_pose(pose_record.get("camera_pose", {}))
    expected = _canonical_digest(
        {
            "observer_id": record.get("observer_id"),
            "tick_window": list(record.get("tick_window", [])),
            "camera_pose_records": list(record.get("camera_pose_records", [])),
        }
    )
    if record.get("path_digest") != expected:
        raise ValueError("implicit observer path digest mismatch")
    _assert_no_forbidden_keys(record)


def _ray_points(camera_pose: Mapping[str, Any], image_shape: Sequence[int], samples_per_ray: int, ray_march_config: Mapping[str, Any]) -> tuple[list[list[float]], list[list[float]]]:
    width, height = [int(value) for value in image_shape]
    origin = _finite_vector(camera_pose["origin"], name="camera_pose.origin", length=3)
    look_at = _finite_vector(camera_pose["look_at"], name="camera_pose.look_at", length=3)
    up_hint = _normalize(_finite_vector(camera_pose.get("up", [0.0, 0.0, 1.0]), name="camera_pose.up", length=3))
    forward = _normalize(_sub(look_at, origin))
    right = _normalize(_cross(forward, up_hint))
    up = _normalize(_cross(right, forward))
    fov = math.radians(float(camera_pose.get("fov_degrees", 50.0)))
    aspect = width / max(1, height)
    half_height = math.tan(fov / 2.0)
    half_width = half_height * aspect
    near = float(ray_march_config.get("near", 0.0))
    far = float(ray_march_config.get("far", 12.0))
    if far <= near:
        raise ValueError("ray far distance must exceed near distance")
    points: list[list[float]] = []
    directions: list[list[float]] = []
    for y in range(height):
        py = 1.0 - ((y + 0.5) / height) * 2.0
        for x in range(width):
            px = ((x + 0.5) / width) * 2.0 - 1.0
            direction = _normalize(
                _add(
                    forward,
                    _add(_scale(right, px * half_width), _scale(up, py * half_height)),
                )
            )
            directions.append(direction)
            for sample_index in range(samples_per_ray):
                fraction = (sample_index + 0.5) / samples_per_ray
                distance = near + (far - near) * fraction
                points.append(_add(origin, _scale(direction, distance)))
    return points, directions


def ray_direction_for_index(
    camera_pose: Mapping[str, Any],
    image_shape: Sequence[int],
    ray_index: int,
) -> list[float]:
    width, height = [int(value) for value in image_shape]
    if width <= 0 or height <= 0:
        raise ValueError("image_shape must be positive")
    index = max(0, min(width * height - 1, int(ray_index)))
    y = index // width
    x = index % width
    origin = _finite_vector(camera_pose["origin"], name="camera_pose.origin", length=3)
    look_at = _finite_vector(camera_pose["look_at"], name="camera_pose.look_at", length=3)
    up_hint = _normalize(_finite_vector(camera_pose.get("up", [0.0, 0.0, 1.0]), name="camera_pose.up", length=3))
    forward = _normalize(_sub(look_at, origin))
    right = _normalize(_cross(forward, up_hint))
    up = _normalize(_cross(right, forward))
    fov = math.radians(float(camera_pose.get("fov_degrees", 50.0)))
    aspect = width / max(1, height)
    half_height = math.tan(fov / 2.0)
    half_width = half_height * aspect
    py = 1.0 - ((y + 0.5) / height) * 2.0
    px = ((x + 0.5) / width) * 2.0 - 1.0
    return _normalize(_add(forward, _add(_scale(right, px * half_width), _scale(up, py * half_height))))


def ray_point_for_index(
    camera_pose: Mapping[str, Any],
    image_shape: Sequence[int],
    ray_index: int,
    hit_depth: float,
) -> list[float]:
    origin = _finite_vector(camera_pose["origin"], name="camera_pose.origin", length=3)
    direction = ray_direction_for_index(camera_pose, image_shape, ray_index)
    return _add(origin, _scale(direction, float(hit_depth)))


def build_implicit_ray_sample_record(
    ray_sample_record_id: str,
    observer_id: str,
    tick: int,
    camera_pose: Mapping[str, Any],
    observer_path_id: str,
    ray_march_config: Mapping[str, Any],
    ray_geometry_digest: str,
    ray_sample_points_digest: str,
    image_shape: Sequence[int],
    samples_per_ray: int,
    ray_integral_summary: Mapping[str, Any],
    source_implicit_field_state_id: str,
    source_evaluation_ids: Sequence[str],
    source_refinement_patch_ids: Sequence[str],
    source_record_ids: Sequence[str],
    ray_target_points_world_3d: Sequence[Sequence[float]] | None = None,
) -> dict[str, Any]:
    _validate_pose(camera_pose)
    record = {
        "schema": IMPLICIT_RAY_SAMPLE_SCHEMA,
        "ray_sample_record_id": str(ray_sample_record_id),
        "observer_id": str(observer_id),
        "tick": int(tick),
        "camera_pose": dict(camera_pose),
        "observer_path_id": str(observer_path_id),
        "ray_march_config": dict(ray_march_config),
        "ray_geometry_digest": str(ray_geometry_digest),
        "ray_sample_points_digest": str(ray_sample_points_digest),
        "image_shape": [int(value) for value in image_shape],
        "samples_per_ray": int(samples_per_ray),
        "ray_integral_summary": dict(ray_integral_summary),
        "ray_target_points_world_3d": [_finite_vector(point, name="ray_target_points_world_3d", length=3) for point in (ray_target_points_world_3d or [])],
        "source_implicit_field_state_id": str(source_implicit_field_state_id),
        "source_evaluation_ids": [str(value) for value in source_evaluation_ids],
        "source_refinement_patch_ids": [str(value) for value in source_refinement_patch_ids],
        "source_record_ids": [str(value) for value in source_record_ids],
        "is_authority_state": False,
    }
    validate_implicit_ray_sample_record(record)
    return record


def validate_implicit_ray_sample_record(record: Mapping[str, Any]) -> None:
    if record.get("schema") != IMPLICIT_RAY_SAMPLE_SCHEMA:
        raise ValueError("implicit ray sample schema mismatch")
    if record.get("is_authority_state") is not False:
        raise ValueError("implicit ray sample record must be non-authority")
    _validate_pose(record.get("camera_pose", {}))
    if not str(record.get("ray_geometry_digest", "")).startswith("sha256:"):
        raise ValueError("implicit ray sample requires ray_geometry_digest")
    if not str(record.get("ray_sample_points_digest", "")).startswith("sha256:"):
        raise ValueError("implicit ray sample requires ray_sample_points_digest")
    if int(record.get("samples_per_ray", 0)) <= 0:
        raise ValueError("implicit ray sample requires samples_per_ray")
    if not record.get("source_evaluation_ids"):
        raise ValueError("implicit ray sample requires source evaluation ids")
    _assert_no_forbidden_keys(record)


def build_implicit_spectral_image_plane(
    image_plane_id: str,
    ray_sample_record: Mapping[str, Any],
    tiles: Sequence[Mapping[str, Any]],
    frequency_mapping: Mapping[str, Any],
    non_background_ratio: float,
    ray_replay_match_ratio: float,
    occlusion_response_score: float,
    source_record_ids: Sequence[str],
    observation_channel_tiles: Sequence[Mapping[str, Any]] | None = None,
    dominant_basis_table: Sequence[Mapping[str, Any]] | None = None,
    ray_geometry_reference: Mapping[str, Any] | None = None,
    shared_basis_centroids: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    validate_implicit_ray_sample_record(ray_sample_record)
    record = {
        "schema": IMPLICIT_SPECTRAL_IMAGE_PLANE_SCHEMA,
        "image_plane_id": str(image_plane_id),
        "ray_sample_record_id": str(ray_sample_record["ray_sample_record_id"]),
        "tick": int(ray_sample_record["tick"]),
        "observer_id": str(ray_sample_record["observer_id"]),
        "image_shape": list(ray_sample_record["image_shape"]),
        "tile_shape": [16, 16],
        "tiles": [dict(tile) for tile in tiles],
        "frequency_mapping": dict(frequency_mapping),
        "non_background_ratio": float(non_background_ratio),
        "ray_replay_match_ratio": float(ray_replay_match_ratio),
        "occlusion_response_score": float(occlusion_response_score),
        "source_record_ids": [str(value) for value in source_record_ids],
        "is_authority_state": False,
    }
    if observation_channel_tiles is not None:
        record["observation_channel_tiles"] = [dict(tile) for tile in observation_channel_tiles]
    if dominant_basis_table is not None:
        record["dominant_basis_table"] = [dict(item) for item in dominant_basis_table]
    if ray_geometry_reference is not None:
        record["ray_geometry_reference"] = dict(ray_geometry_reference)
    if shared_basis_centroids is not None:
        record["shared_basis_centroids"] = dict(shared_basis_centroids)
    record["image_content_digest"] = _canonical_digest(
        {
            "tiles": record["tiles"],
            "observation_channel_tiles": record.get("observation_channel_tiles", []),
            "dominant_basis_table": record.get("dominant_basis_table", []),
            "frequency_mapping": record["frequency_mapping"],
            "non_background_ratio": record["non_background_ratio"],
            "occlusion_response_score": record["occlusion_response_score"],
        }
    )
    record["image_digest"] = _canonical_digest(
        {
            "ray_sample_record_id": record["ray_sample_record_id"],
            "tiles": record["tiles"],
            "frequency_mapping": record["frequency_mapping"],
            "non_background_ratio": record["non_background_ratio"],
            "occlusion_response_score": record["occlusion_response_score"],
        }
    )
    validate_implicit_spectral_image_plane(record)
    return record


def validate_implicit_spectral_image_plane(record: Mapping[str, Any]) -> None:
    if record.get("schema") != IMPLICIT_SPECTRAL_IMAGE_PLANE_SCHEMA:
        raise ValueError("implicit spectral image plane schema mismatch")
    if record.get("is_authority_state") is not False:
        raise ValueError("implicit spectral image plane must be non-authority")
    if float(record.get("ray_replay_match_ratio", 0.0)) < 0.98:
        raise ValueError("implicit spectral image plane ray replay below threshold")
    if not str(record.get("ray_sample_record_id", "")):
        raise ValueError("implicit spectral image plane requires ray sample id")
    if not record.get("source_record_ids"):
        raise ValueError("implicit spectral image plane requires source records")
    for tile in record.get("observation_channel_tiles", []):
        validate_implicit_observation_channel_tile(tile)
    _assert_no_forbidden_keys(record)


def _rgba_tiles(raw: bytes, image_shape: Sequence[int], source_record_ids: Sequence[str]) -> list[dict[str, Any]]:
    width, height = [int(value) for value in image_shape]
    tile_width = 16
    tile_height = 16
    tiles: list[dict[str, Any]] = []
    tiles_x = math.ceil(width / tile_width)
    for ty in range(math.ceil(height / tile_height)):
        for tx in range(tiles_x):
            actual_width = min(tile_width, width - tx * tile_width)
            actual_height = min(tile_height, height - ty * tile_height)
            tile_raw = bytearray()
            for row in range(actual_height):
                y = ty * tile_height + row
                start = (y * width + tx * tile_width) * 4
                tile_raw.extend(raw[start : start + actual_width * 4])
            tiles.append(
                {
                    "schema": IMPLICIT_IMAGE_TILE_SCHEMA,
                    "tile_xy": [tx, ty],
                    "tile_shape": [actual_width, actual_height],
                    "rgba8_rle_base64": _rle_encode_rgba(bytes(tile_raw)),
                    "source_record_ids": [str(value) for value in source_record_ids],
                    "is_authority_state": False,
                }
            )
    return tiles


def _basis_support_contains(point: Sequence[float], basis: Mapping[str, Any]) -> bool:
    support = basis.get("support_region_world", {})
    lower = support.get("min")
    upper = support.get("max")
    if lower is None or upper is None:
        center = _finite_vector(basis.get("center_world_3d", []), name="center_world_3d", length=3)
        radius = float(basis.get("radius_world", 0.0))
        return _norm(_sub(point, center)) <= radius
    return all(float(lower[index]) <= float(point[index]) <= float(upper[index]) for index in range(3))


def _dominant_basis_id_at_point(
    state: Mapping[str, Any],
    bases: Sequence[Mapping[str, Any]],
    point: Sequence[float],
    sample: Mapping[str, Any],
) -> str | None:
    declared = set(str(value) for value in state.get("basis_ids", []))
    best_id = None
    best_score = 0.0
    for basis in bases:
        basis_id = str(basis.get("basis_id", ""))
        if basis_id not in declared or not _basis_support_contains(point, basis):
            continue
        weights = basis.get("channel_weights", {})
        coefficients = state.get("basis_coefficients", {}).get(basis_id, {})
        score = 0.0
        for channel in ("density", "emission", "absorption", "boundary"):
            score += abs(float(weights.get(channel, 0.0))) * abs(float(coefficients.get(channel, coefficients.get("*", 1.0)))) * max(0.0, abs(float(sample.get(channel, 0.0))))
        if score > best_score:
            best_id = basis_id
            best_score = score
    return best_id


def _normal_hint_for_basis(point: Sequence[float], basis: Mapping[str, Any] | None) -> tuple[float, float, float] | None:
    if basis is None:
        return None
    center = _finite_vector(basis.get("center_world_3d", [0.0, 0.0, 0.0]), name="center_world_3d", length=3)
    try:
        direction = _normalize(_sub(point, center))
    except ValueError:
        direction = [0.0, 0.0, 1.0]
    return tuple((value + 1.0) / 2.0 for value in direction)


def _dominant_basis_centroids(
    basis_indexes: Sequence[int],
    depths: Sequence[float | None],
    dominant_basis_table: Sequence[Mapping[str, Any]],
    image_shape: Sequence[int],
) -> dict[str, dict[str, Any]]:
    width, height = [int(value) for value in image_shape]
    table = {int(item["index"]): str(item["basis_id"]) for item in dominant_basis_table}
    accum: dict[str, dict[str, float]] = {}
    for ray_index, basis_index in enumerate(basis_indexes):
        basis_id = table.get(int(basis_index))
        if not basis_id or depths[ray_index] is None:
            continue
        x = ray_index % width
        y = ray_index // width
        item = accum.setdefault(basis_id, {"x": 0.0, "y": 0.0, "depth": 0.0, "count": 0.0})
        item["x"] += x
        item["y"] += y
        item["depth"] += float(depths[ray_index])
        item["count"] += 1.0
    return {
        basis_id: {
            "centroid_image_xy": [values["x"] / values["count"], values["y"] / values["count"]],
            "mean_depth": values["depth"] / values["count"],
        }
        for basis_id, values in accum.items()
        if values["count"] > 0.0
    }


def _sampled_basis_support_centroids(
    points: Sequence[Sequence[float]],
    evaluation: Mapping[str, Any],
    state: Mapping[str, Any],
    bases: Sequence[Mapping[str, Any]],
    image_shape: Sequence[int],
    samples_per_ray: int,
    ray_config: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    width, _height = [int(value) for value in image_shape]
    declared = set(str(value) for value in state.get("basis_ids", []))
    accum: dict[str, dict[str, float]] = {}
    step_size = float(ray_config["step_size"])
    near = float(ray_config["near"])
    samples = list(evaluation.get("sample_values", []))
    for flat_index, point in enumerate(points):
        if flat_index >= len(samples):
            break
        sample = samples[flat_index]
        ray_index = flat_index // max(1, int(samples_per_ray))
        sample_index = flat_index % max(1, int(samples_per_ray))
        signal = (
            abs(float(sample.get("density", 0.0)))
            + abs(float(sample.get("emission", 0.0)))
            + abs(float(sample.get("absorption", 0.0)))
            + abs(float(sample.get("boundary", 0.0)))
        )
        if signal < 0.01:
            continue
        x = ray_index % width
        y = ray_index // width
        depth = near + (sample_index + 0.5) * step_size
        for basis in bases:
            basis_id = str(basis.get("basis_id", ""))
            if basis_id not in declared or not _basis_support_contains(point, basis):
                continue
            item = accum.setdefault(basis_id, {"x": 0.0, "y": 0.0, "depth": 0.0, "count": 0.0})
            item["x"] += x
            item["y"] += y
            item["depth"] += depth
            item["count"] += 1.0
    return {
        basis_id: {
            "centroid_image_xy": [values["x"] / values["count"], values["y"] / values["count"]],
            "mean_depth": values["depth"] / values["count"],
            "sample_count": int(values["count"]),
            "correspondence_source": "ray_sampled_basis_support",
        }
        for basis_id, values in accum.items()
        if values["count"] > 0.0
    }


def trace_implicit_ray_camera(
    state: Mapping[str, Any],
    bases: Sequence[Mapping[str, Any]],
    *,
    observer_path_record: Mapping[str, Any],
    observer_id: str,
    tick: int,
    camera_pose: Mapping[str, Any],
    image_shape: Sequence[int] = (32, 24),
    samples_per_ray: int = 48,
    ray_march_config: Mapping[str, Any] | None = None,
    active_basis_per_sample_max: int = 24,
) -> dict[str, Any]:
    validate_implicit_field_state(state)
    validate_implicit_observer_path_record(observer_path_record)
    ray_config = {"near": 0.0, "far": 12.0, "step_size": 12.0 / max(1, int(samples_per_ray))}
    if ray_march_config:
        ray_config.update(dict(ray_march_config))
    image_shape = [int(value) for value in image_shape]
    points, directions = _ray_points(camera_pose, image_shape, int(samples_per_ray), ray_config)
    ray_geometry_digest = _canonical_digest(
        {
            "observer_path_id": observer_path_record["observer_path_id"],
            "camera_pose": dict(camera_pose),
            "image_shape": image_shape,
            "ray_march_config": ray_config,
            "directions": directions,
        }
    )
    ray_sample_points_digest = _canonical_digest(points)
    evaluation = evaluate_implicit_field(
        state,
        bases,
        points,
        channel_names=["density", "emission", "absorption", "boundary"],
    )
    if int(evaluation["active_basis_per_sample_summary"]["max"]) > int(active_basis_per_sample_max):
        raise ValueError("implicit ray active basis count exceeds threshold")
    evaluation_record = build_implicit_field_evaluation_record(
        evaluation_id=(
            f"implicit-field-evaluation::{state['implicit_field_state_id']}::{observer_id}::{tick}::{_short_digest(ray_sample_points_digest)}"
        ),
        implicit_field_state_id=str(state["implicit_field_state_id"]),
        tick=int(tick),
        sample_points_world_3d=points,
        channel_names=["density", "emission", "absorption", "boundary"],
        evaluation_summary=evaluation["evaluation_summary"],
        basis_contribution_digest=evaluation["basis_contribution_digest"],
        basis_spatial_index_digest=str(evaluation["basis_spatial_index_digest"]),
        active_basis_per_sample_summary=evaluation["active_basis_per_sample_summary"],
        source_basis_ids=[str(basis.get("basis_id")) for basis in bases],
        source_local_patch_ids=list(state.get("active_local_patch_ids", [])),
        source_record_ids=[str(state["implicit_field_state_id"]), *[str(basis.get("basis_id")) for basis in bases]],
    )
    validate_implicit_field_evaluation_record(evaluation_record)

    width, height = image_shape
    raw = bytearray()
    intensities: list[float] = []
    occlusion_values: list[float] = []
    first_hit_depths: list[float | None] = []
    transmittance_values: list[float] = []
    dominant_basis_ids: list[str | None] = []
    normal_hints: list[tuple[float, float, float] | None] = []
    target_points: list[list[float]] = []
    step_size = (float(ray_config["far"]) - float(ray_config["near"])) / max(1, int(samples_per_ray))
    basis_by_id = {str(basis.get("basis_id")): basis for basis in bases}
    for ray_index in range(width * height):
        transmittance = 1.0
        intensity = 0.0
        absorbed = 0.0
        first_hit_depth: float | None = None
        first_hit_basis_id: str | None = None
        first_hit_normal: tuple[float, float, float] | None = None
        for sample_index in range(int(samples_per_ray)):
            sample = evaluation["sample_values"][ray_index * int(samples_per_ray) + sample_index]
            point = points[ray_index * int(samples_per_ray) + sample_index]
            density = max(0.0, float(sample.get("density", 0.0)))
            emission = max(0.0, float(sample.get("emission", density * 0.7)))
            absorption = max(0.0, float(sample.get("absorption", 0.0)))
            if first_hit_depth is None and (density >= 0.03 or emission >= 0.03 or absorption >= 0.03):
                first_hit_depth = float(ray_config["near"]) + (sample_index + 0.5) * step_size
                first_hit_basis_id = _dominant_basis_id_at_point(state, bases, point, sample)
                first_hit_normal = _normal_hint_for_basis(point, basis_by_id.get(first_hit_basis_id or ""))
            contribution = transmittance * density * max(0.05, emission) * step_size
            intensity += contribution
            absorbed += transmittance * absorption * step_size
            transmittance *= math.exp(-absorption * step_size)
        normalized = max(0.0, min(1.0, intensity * 1.7))
        occlusion = max(0.0, min(1.0, absorbed))
        intensities.append(normalized)
        occlusion_values.append(occlusion)
        first_hit_depths.append(first_hit_depth)
        transmittance_values.append(transmittance)
        dominant_basis_ids.append(first_hit_basis_id)
        normal_hints.append(first_hit_normal)
        if first_hit_depth is None:
            target_points.append(_finite_vector(camera_pose["look_at"], name="camera_pose.look_at", length=3))
        else:
            target_points.append(ray_point_for_index(camera_pose, image_shape, ray_index, first_hit_depth))
        red = round(255 * max(0.0, min(1.0, normalized * 0.72 + occlusion * 0.18)))
        green = round(255 * max(0.0, min(1.0, normalized * 0.95)))
        blue = round(255 * max(0.0, min(1.0, normalized * 0.78 + occlusion * 0.30)))
        alpha = 255 if normalized > 0.01 else 0
        raw.extend([red, green, blue, alpha])
    non_background_ratio = sum(1 for value in intensities if value > 0.01) / max(1, len(intensities))
    occlusion_response_score = sum(occlusion_values) / max(1, len(occlusion_values))
    ray_integral_summary = {
        "mean_intensity": sum(intensities) / max(1, len(intensities)),
        "max_intensity": max(intensities) if intensities else 0.0,
        "mean_occlusion": occlusion_response_score,
        "depth_summary": summarize_depth_channel(first_hit_depths),
        "opacity_summary": summarize_scalar_channel([1.0 - value for value in transmittance_values], name="opacity"),
        "transmittance_summary": summarize_scalar_channel(transmittance_values, name="transmittance"),
        "dominant_basis_summary": {
            "known_ratio": sum(1 for value in dominant_basis_ids if value) / max(1, len(dominant_basis_ids)),
            "basis_ids": sorted({str(value) for value in dominant_basis_ids if value}),
        },
        "active_basis_per_sample_summary": dict(evaluation["active_basis_per_sample_summary"]),
        "ray_geometry_digest": ray_geometry_digest,
        "ray_sample_points_digest": ray_sample_points_digest,
    }
    ray_sample_record_id = (
        f"implicit-ray-sample::{state['implicit_field_state_id']}::{observer_id}::{tick}::{_short_digest(ray_geometry_digest)}"
    )
    ray_sample_record = build_implicit_ray_sample_record(
        ray_sample_record_id=ray_sample_record_id,
        observer_id=observer_id,
        tick=int(tick),
        camera_pose=camera_pose,
        observer_path_id=str(observer_path_record["observer_path_id"]),
        ray_march_config=ray_config,
        ray_geometry_digest=ray_geometry_digest,
        ray_sample_points_digest=ray_sample_points_digest,
        image_shape=image_shape,
        samples_per_ray=int(samples_per_ray),
        ray_integral_summary=ray_integral_summary,
        source_implicit_field_state_id=str(state["implicit_field_state_id"]),
        source_evaluation_ids=[evaluation_record["evaluation_id"]],
        source_refinement_patch_ids=list(state.get("active_local_patch_ids", [])),
        source_record_ids=[evaluation_record["evaluation_id"], str(observer_path_record["observer_path_id"])],
        ray_target_points_world_3d=target_points,
    )
    dominant_basis_ids_known = sorted({str(value) for value in dominant_basis_ids if value})
    dominant_basis_table = [{"index": index + 1, "basis_id": basis_id} for index, basis_id in enumerate(dominant_basis_ids_known)]
    dominant_basis_index_by_id = {item["basis_id"]: int(item["index"]) for item in dominant_basis_table}
    dominant_basis_indexes = [dominant_basis_index_by_id.get(str(value), 0) if value else 0 for value in dominant_basis_ids]
    observation_channel_tiles = [
        build_u16_observation_channel_tile(
            channel="depth_u16",
            tile_xy=[0, 0],
            tile_shape=image_shape,
            values=first_hit_depths,
            value_range=[float(ray_config["near"]), float(ray_config["far"])],
            source_ray_sample_record_id=ray_sample_record["ray_sample_record_id"],
            source_record_ids=[ray_sample_record["ray_sample_record_id"], evaluation_record["evaluation_id"]],
        ),
        build_u16_observation_channel_tile(
            channel="opacity_u16",
            tile_xy=[0, 0],
            tile_shape=image_shape,
            values=[1.0 - value for value in transmittance_values],
            value_range=[0.0, 1.0],
            source_ray_sample_record_id=ray_sample_record["ray_sample_record_id"],
            source_record_ids=[ray_sample_record["ray_sample_record_id"], evaluation_record["evaluation_id"]],
        ),
        build_u16_observation_channel_tile(
            channel="transmittance_u16",
            tile_xy=[0, 0],
            tile_shape=image_shape,
            values=transmittance_values,
            value_range=[0.0, 1.0],
            source_ray_sample_record_id=ray_sample_record["ray_sample_record_id"],
            source_record_ids=[ray_sample_record["ray_sample_record_id"], evaluation_record["evaluation_id"]],
        ),
        build_u16_observation_channel_tile(
            channel="dominant_basis_index_u16",
            tile_xy=[0, 0],
            tile_shape=image_shape,
            values=[float(value) if value else None for value in dominant_basis_indexes],
            value_range=[0.0, float(max(1, len(dominant_basis_table)))],
            source_ray_sample_record_id=ray_sample_record["ray_sample_record_id"],
            source_record_ids=[ray_sample_record["ray_sample_record_id"], evaluation_record["evaluation_id"]],
        ),
        build_rgb8_observation_channel_tile(
            channel="normal_hint_rgb8",
            tile_xy=[0, 0],
            tile_shape=image_shape,
            values=normal_hints,
            source_ray_sample_record_id=ray_sample_record["ray_sample_record_id"],
            source_record_ids=[ray_sample_record["ray_sample_record_id"], evaluation_record["evaluation_id"]],
        ),
    ]
    shared_basis_centroids = _sampled_basis_support_centroids(
        points,
        evaluation,
        state,
        bases,
        image_shape,
        int(samples_per_ray),
        ray_config,
    )
    if len(shared_basis_centroids) < 2:
        shared_basis_centroids.update(_dominant_basis_centroids(dominant_basis_indexes, first_hit_depths, dominant_basis_table, image_shape))
    tiles = _rgba_tiles(bytes(raw), image_shape, [ray_sample_record["ray_sample_record_id"], evaluation_record["evaluation_id"]])
    image_plane = build_implicit_spectral_image_plane(
        image_plane_id=f"implicit-image-plane::{state['implicit_field_state_id']}::{observer_id}::{tick}::{_short_digest(ray_geometry_digest)}",
        ray_sample_record=ray_sample_record,
        tiles=tiles,
        frequency_mapping={"density": [0.42, 0.58], "emission": [0.58, 0.78], "absorption": [0.18, 0.42]},
        non_background_ratio=non_background_ratio,
        ray_replay_match_ratio=1.0,
        occlusion_response_score=occlusion_response_score,
        source_record_ids=[ray_sample_record["ray_sample_record_id"], evaluation_record["evaluation_id"]],
        observation_channel_tiles=observation_channel_tiles,
        dominant_basis_table=dominant_basis_table,
        ray_geometry_reference={
            "camera_pose_digest": _canonical_digest(dict(camera_pose)),
            "source_observer_path_record_id": str(observer_path_record["observer_path_id"]),
            "image_shape": image_shape,
            "ray_march_config_digest": _canonical_digest(ray_config),
        },
        shared_basis_centroids=shared_basis_centroids,
    )
    return {
        "evaluation": evaluation,
        "evaluation_record": evaluation_record,
        "ray_sample_record": ray_sample_record,
        "image_plane": image_plane,
    }
