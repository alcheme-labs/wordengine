from __future__ import annotations

import copy
import math
from typing import Any, Mapping, Sequence

from world_engine.implicit_observation_channels import decode_u16_observation_channel_tile
from world_engine.implicit_ray_camera import ray_direction_for_index, ray_point_for_index


IMPLICIT_INTERACTION_REQUEST_SCHEMA = "implicit_interaction_request"
IMPLICIT_INTERACTION_AUDIT_SCHEMA = "implicit_interaction_audit"

SUPPORTED_IMPLICIT_TOOLS = {
    "implicit_local_excite",
    "implicit_local_dampen",
    "implicit_directional_push",
    "implicit_refine_probe",
}


def _finite_number(value: Any, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


def _finite_vector(values: Sequence[Any], *, name: str, length: int) -> list[float]:
    if len(values) != length:
        raise ValueError(f"{name} must have length {length}")
    return [_finite_number(value, name=name) for value in values]


def canonical_implicit_tick_count(
    value: Any,
    *,
    name: str,
    max_ticks: int | None = None,
) -> int:
    """Validate a user-facing discrete tick count without numeric coercion."""

    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    ticks = value
    if ticks < 1 or (max_ticks is not None and ticks > int(max_ticks)):
        raise ValueError(f"{name} outside bounds")
    return ticks


def _basis_id(basis: Mapping[str, Any]) -> str:
    return str(basis.get("basis_id", ""))


def _required_request_string(request: Mapping[str, Any], field_name: str) -> str:
    value = request.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"implicit interaction request requires {field_name}")
    return value


def _distance(left: Sequence[float], right: Sequence[float]) -> float:
    return math.sqrt(sum((float(left[index]) - float(right[index])) ** 2 for index in range(3)))


def implicit_command_id(request_id: str) -> str:
    return f"cmd::implicit::{request_id}"


def canonical_implicit_signed_amplitude(
    request: Mapping[str, Any],
    *,
    max_amplitude: float = 1.0,
) -> float:
    amplitude = _finite_number(request.get("amplitude"), name="amplitude")
    if amplitude < 0.0:
        raise ValueError("amplitude must be non-negative")
    if amplitude > float(max_amplitude):
        raise ValueError("amplitude exceeds maximum")
    tool = str(request.get("tool", ""))
    if tool == "implicit_local_dampen":
        return -amplitude
    if tool in {"implicit_local_excite", "implicit_directional_push"}:
        return amplitude
    if tool == "implicit_refine_probe":
        return 0.0
    raise ValueError("unknown implicit tool")


def implicit_duration_schedule_weights(
    duration_ticks: Any,
    *,
    max_duration_ticks: float = 32.0,
) -> list[float]:
    duration = _finite_number(duration_ticks, name="duration_ticks")
    if duration <= 0.0 or duration > float(max_duration_ticks):
        raise ValueError("duration_ticks outside bounds")
    return [min(1.0, max(0.0, duration - index)) for index in range(math.ceil(duration))]


def validate_implicit_interaction_request(
    request: Mapping[str, Any],
    *,
    declared_observer_ids: Sequence[str],
    existing_request_ids: set[str] | None = None,
    max_radius_world: float = 4.0,
    max_amplitude: float = 1.0,
    max_duration_ticks: int = 32,
    max_advance_ticks: int = 32,
) -> None:
    if request.get("schema") != IMPLICIT_INTERACTION_REQUEST_SCHEMA:
        raise ValueError("implicit interaction request schema mismatch")
    request_id = str(request.get("request_id", ""))
    if not request_id:
        raise ValueError("implicit interaction request requires request_id")
    if existing_request_ids and request_id in existing_request_ids:
        raise ValueError("duplicate implicit request_id")
    tool = str(request.get("tool", ""))
    if tool not in SUPPORTED_IMPLICIT_TOOLS:
        raise ValueError("unknown implicit tool")
    observer_id = str(request.get("observer_id", ""))
    if observer_id not in {str(value) for value in declared_observer_ids}:
        raise ValueError("undeclared implicit observer_id")
    for field_name in (
        "source_projection_frame_id",
        "source_state_id",
        "source_ray_sample_record_id",
    ):
        _required_request_string(request, field_name)
    source_image_xy = _finite_vector(request.get("source_image_xy", []), name="source_image_xy", length=2)
    if any(value < 0.0 or value > 1.0 for value in source_image_xy):
        raise ValueError("source_image_xy outside normalized bounds")
    radius_world = _finite_number(request.get("radius_world"), name="radius_world")
    if radius_world <= 0.0:
        raise ValueError("radius_world must be positive")
    if radius_world > float(max_radius_world):
        raise ValueError("radius_world exceeds maximum")
    canonical_implicit_signed_amplitude(request, max_amplitude=max_amplitude)
    implicit_duration_schedule_weights(request.get("duration_ticks"), max_duration_ticks=max_duration_ticks)
    if "advance_after_accept" in request and not isinstance(
        request.get("advance_after_accept"), bool
    ):
        raise ValueError("advance_after_accept must be a boolean")
    if request.get("advance_after_accept") or "advance_ticks" in request:
        canonical_implicit_tick_count(
            request.get("advance_ticks", 0),
            name="advance_ticks",
            max_ticks=max_advance_ticks,
        )


def _ray_target_point(request: Mapping[str, Any], ray_sample_record: Mapping[str, Any]) -> list[float]:
    image_shape = [int(value) for value in ray_sample_record.get("image_shape", [])]
    if len(image_shape) != 2 or image_shape[0] <= 0 or image_shape[1] <= 0:
        raise ValueError("implicit ray sample requires image_shape")
    width, height = image_shape
    source_image_xy = _finite_vector(request.get("source_image_xy", []), name="source_image_xy", length=2)
    x_index = max(0, min(width - 1, int(math.floor(source_image_xy[0] * width))))
    y_index = max(0, min(height - 1, int(math.floor(source_image_xy[1] * height))))
    point_index = y_index * width + x_index
    points = ray_sample_record.get("ray_target_points_world_3d")
    if isinstance(points, Sequence) and len(points) > point_index:
        return _finite_vector(points[point_index], name="ray_target_points_world_3d", length=3)
    pose = ray_sample_record.get("camera_pose")
    if isinstance(pose, Mapping) and pose.get("look_at"):
        return _finite_vector(pose["look_at"], name="camera_pose.look_at", length=3)
    return [0.0, 0.0, 0.0]


def _target_ray_index(request: Mapping[str, Any], image_shape: Sequence[int]) -> int:
    width, height = [int(value) for value in image_shape]
    source_image_xy = _finite_vector(request.get("source_image_xy", []), name="source_image_xy", length=2)
    x_index = max(0, min(width - 1, int(math.floor(source_image_xy[0] * width))))
    y_index = max(0, min(height - 1, int(math.floor(source_image_xy[1] * height))))
    return y_index * width + x_index


def _channel_values(image_plane: Mapping[str, Any], channel: str) -> list[float | None]:
    for tile in image_plane.get("observation_channel_tiles", []):
        if tile.get("channel") == channel:
            return decode_u16_observation_channel_tile(tile)
    return []


def _basis_from_channel(image_plane: Mapping[str, Any], ray_index: int) -> str | None:
    indexes = _channel_values(image_plane, "dominant_basis_index_u16")
    if not indexes or ray_index >= len(indexes) or indexes[ray_index] is None:
        return None
    index = max(0, round(float(indexes[ray_index])))
    for item in image_plane.get("dominant_basis_table", []):
        if int(item.get("index", -1)) == index:
            return str(item.get("basis_id", ""))
    return None


def _depth_from_channel(image_plane: Mapping[str, Any], ray_index: int) -> float | None:
    depths = _channel_values(image_plane, "depth_u16")
    if not depths or ray_index >= len(depths):
        return None
    value = depths[ray_index]
    return None if value is None else float(value)


def _point_in_support(point: Sequence[float], basis: Mapping[str, Any]) -> bool:
    support = basis.get("support_region_world", {})
    lower = support.get("min")
    upper = support.get("max")
    if lower is None or upper is None:
        center = _finite_vector(basis.get("center_world_3d", []), name="center_world_3d", length=3)
        radius = float(basis.get("radius_world", 0.0))
        return _distance(point, center) <= radius
    lower_vec = _finite_vector(lower, name="support_region_world.min", length=3)
    upper_vec = _finite_vector(upper, name="support_region_world.max", length=3)
    return all(lower_vec[index] <= float(point[index]) <= upper_vec[index] for index in range(3))


def _support_intersects_local_radius(
    target_world_3d: Sequence[float],
    radius_world: float,
    basis: Mapping[str, Any],
) -> bool:
    support = basis.get("support_region_world")
    if not isinstance(support, Mapping) or "min" not in support or "max" not in support:
        raise ValueError("implicit local control basis requires support_region_world")
    lower = _finite_vector(support["min"], name="support_region_world.min", length=3)
    upper = _finite_vector(support["max"], name="support_region_world.max", length=3)
    if any(lower[index] > upper[index] for index in range(3)):
        raise ValueError("support_region_world bounds are reversed")
    distance_squared = 0.0
    for index, coordinate in enumerate(target_world_3d):
        if coordinate < lower[index]:
            distance_squared += (lower[index] - coordinate) ** 2
        elif coordinate > upper[index]:
            distance_squared += (coordinate - upper[index]) ** 2
    return distance_squared <= radius_world * radius_world


def _wendland_c2(normalized_distance: float) -> float:
    if normalized_distance >= 1.0:
        return 0.0
    remainder = max(0.0, 1.0 - normalized_distance)
    return remainder**4 * (4.0 * normalized_distance + 1.0)


def build_implicit_local_control_weights(
    *,
    target_world_3d: Sequence[Any],
    bases: Sequence[Mapping[str, Any]],
    radius_world: Any,
    kappa_norm_min: float = 1e-6,
    min_positive_support_bases: int = 2,
) -> dict[str, Any]:
    target = _finite_vector(target_world_3d, name="target_world_3d", length=3)
    radius = _finite_number(radius_world, name="radius_world")
    if radius <= 0.0:
        raise ValueError("radius_world must be positive")
    norm_min = _finite_number(kappa_norm_min, name="kappa_norm_min")
    if norm_min <= 0.0:
        raise ValueError("kappa_norm_min must be positive")
    if isinstance(min_positive_support_bases, bool) or not isinstance(min_positive_support_bases, int):
        raise ValueError("min_positive_support_bases must be an integer")
    if min_positive_support_bases < 1:
        raise ValueError("min_positive_support_bases must be positive")

    kappa_by_basis: dict[str, float] = {}
    basis_geometry: list[dict[str, Any]] = []
    seen_basis_ids: set[str] = set()
    for basis_record in sorted(bases, key=_basis_id):
        basis_id = _basis_id(basis_record)
        if not basis_id:
            raise ValueError("implicit local control basis requires basis_id")
        if basis_id in seen_basis_ids:
            raise ValueError("duplicate implicit local control basis_id")
        seen_basis_ids.add(basis_id)
        if not _support_intersects_local_radius(target, radius, basis_record):
            continue
        center = _finite_vector(basis_record.get("center_world_3d", []), name="center_world_3d", length=3)
        basis_radius = _finite_number(basis_record.get("radius_world"), name="basis.radius_world")
        if basis_radius <= 0.0:
            raise ValueError("basis.radius_world must be positive")
        kappa = _wendland_c2(_distance(target, center) / (radius + basis_radius))
        if kappa <= 0.0:
            continue
        kappa_by_basis[basis_id] = kappa
        basis_geometry.append(
            {
                "basis_id": basis_id,
                "center_world_3d": center,
                "radius_world": basis_radius,
                "support_region_world": {
                    "min": _finite_vector(
                        basis_record["support_region_world"]["min"],
                        name="support_region_world.min",
                        length=3,
                    ),
                    "max": _finite_vector(
                        basis_record["support_region_world"]["max"],
                        name="support_region_world.max",
                        length=3,
                    ),
                },
            }
        )

    if len(kappa_by_basis) < min_positive_support_bases:
        raise ValueError("implicit local control requires at least two positive-support bases")
    kappa_sum = sum(kappa_by_basis.values())
    if not math.isfinite(kappa_sum) or kappa_sum < norm_min:
        raise ValueError("implicit local control kappa is ill-conditioned")
    return {
        "kappa_by_basis": kappa_by_basis,
        "normalized_weights_by_basis": {
            basis_id: kappa / kappa_sum for basis_id, kappa in kappa_by_basis.items()
        },
        "kappa_sum": kappa_sum,
        "basis_geometry": basis_geometry,
    }


def build_implicit_pending_control_descriptor(
    request: Mapping[str, Any],
    *,
    target: Mapping[str, Any],
    bases: Sequence[Mapping[str, Any]],
    accepted_sequence: int,
    start_tick: int,
    kappa_norm_min: float = 1e-6,
) -> dict[str, Any]:
    tool = str(request.get("tool", ""))
    if tool not in {"implicit_local_excite", "implicit_local_dampen"}:
        raise ValueError("pending control descriptor requires a local excite/dampen tool")
    if isinstance(accepted_sequence, bool) or not isinstance(accepted_sequence, int) or accepted_sequence < 0:
        raise ValueError("accepted_sequence must be a non-negative integer")
    if isinstance(start_tick, bool) or not isinstance(start_tick, int) or start_tick < 0:
        raise ValueError("start_tick must be a non-negative integer")
    for field_name in (
        "request_id",
        "observer_id",
        "source_projection_frame_id",
        "source_state_id",
        "source_ray_sample_record_id",
    ):
        _required_request_string(request, field_name)
    target_ray_id = target.get("source_ray_sample_record_id")
    if target_ray_id and str(target_ray_id) != str(request["source_ray_sample_record_id"]):
        raise ValueError("target ray does not match source_ray_sample_record_id")

    radius = _finite_number(request.get("radius_world"), name="radius_world")
    duration = _finite_number(request.get("duration_ticks"), name="duration_ticks")
    signed_amplitude = canonical_implicit_signed_amplitude(request)
    schedule_weights = implicit_duration_schedule_weights(duration)
    weights = build_implicit_local_control_weights(
        target_world_3d=target.get("target_world_3d", []),
        bases=bases,
        radius_world=radius,
        kappa_norm_min=kappa_norm_min,
    )
    request_id = str(request["request_id"])
    command_id = implicit_command_id(request_id)
    return {
        "request_id": request_id,
        "command_id": command_id,
        "audit_id": f"implicit-interaction-audit::{command_id}",
        "accepted_sequence": accepted_sequence,
        "observer_id": str(request["observer_id"]),
        "source_projection_frame_id": str(request["source_projection_frame_id"]),
        "source_frame_tick": int(request.get("source_frame_tick", request.get("frame_tick", 0))),
        "source_state_id": str(request["source_state_id"]),
        "source_ray_sample_record_id": str(request["source_ray_sample_record_id"]),
        "tool": tool,
        "amplitude_magnitude": abs(signed_amplitude),
        "signed_amplitude": signed_amplitude,
        "target_world_3d": _finite_vector(target.get("target_world_3d", []), name="target_world_3d", length=3),
        "target_basis_ids": list(weights["kappa_by_basis"]),
        "radius_world": radius,
        "start_tick": start_tick,
        "duration_ticks": duration,
        "schedule_weights": schedule_weights,
        "requested_total_absolute_dose": abs(signed_amplitude) * duration,
        "target_channel": "density",
        **weights,
    }


def materialize_implicit_raw_control_projection(
    descriptor: Mapping[str, Any],
    *,
    schedule_index: int,
) -> dict[str, dict[str, float]]:
    if isinstance(schedule_index, bool) or not isinstance(schedule_index, int):
        raise ValueError("schedule_index must be an integer")
    schedule_weights = list(descriptor.get("schedule_weights", []))
    if schedule_index < 0 or schedule_index >= len(schedule_weights):
        raise ValueError("schedule_index outside pending control schedule")
    schedule_weight = _finite_number(schedule_weights[schedule_index], name="schedule_weight")
    signed_amplitude = _finite_number(descriptor.get("signed_amplitude"), name="signed_amplitude")
    signed_dose = signed_amplitude * schedule_weight
    if signed_dose == 0.0:
        return {}
    normalized = descriptor.get("normalized_weights_by_basis")
    if not isinstance(normalized, Mapping) or not normalized:
        raise ValueError("pending control descriptor requires normalized weights")
    return {
        str(basis_id): {"density": signed_dose * _finite_number(weight, name="normalized_weight")}
        for basis_id, weight in sorted(normalized.items())
    }


def target_basis_from_image_xy(
    request: Mapping[str, Any],
    *,
    current_state: Mapping[str, Any],
    bases: Sequence[Mapping[str, Any]],
    ray_sample_record: Mapping[str, Any],
    image_plane: Mapping[str, Any] | None = None,
    observed_structures: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    basis_by_id = {_basis_id(basis): basis for basis in bases}
    declared_basis_ids = [str(value) for value in current_state.get("basis_ids", [])]
    missing_basis_ids = sorted(set(declared_basis_ids) - set(basis_by_id))
    if missing_basis_ids:
        raise ValueError("current state references missing basis")
    image_shape = [int(value) for value in ray_sample_record.get("image_shape", [])]
    ray_index = _target_ray_index(request, image_shape)
    if isinstance(ray_sample_record.get("camera_pose"), Mapping) and ray_sample_record.get("camera_pose", {}).get("origin"):
        target_direction = ray_direction_for_index(ray_sample_record.get("camera_pose", {}), image_shape, ray_index)
    else:
        target_direction = [0.0, 1.0, 0.0]
    target_hit_depth = None
    channel_basis_id = None
    if image_plane is not None:
        target_hit_depth = _depth_from_channel(image_plane, ray_index)
        channel_basis_id = _basis_from_channel(image_plane, ray_index)
    if target_hit_depth is not None:
        target_point = ray_point_for_index(ray_sample_record.get("camera_pose", {}), image_shape, ray_index, target_hit_depth)
    else:
        target_point = _ray_target_point(request, ray_sample_record)
    direct_hits = [
        basis_id
        for basis_id in declared_basis_ids
        if _point_in_support(target_point, basis_by_id[basis_id])
    ]
    if channel_basis_id and channel_basis_id in declared_basis_ids:
        target_ids = [channel_basis_id]
        confidence = "direct"
        hit_source = "observation_channel"
    elif direct_hits:
        target_ids = direct_hits
        confidence = "direct"
        hit_source = "ray_integral"
    else:
        nearest = min(
            declared_basis_ids,
            key=lambda basis_id: _distance(
                target_point,
                _finite_vector(basis_by_id[basis_id].get("center_world_3d", []), name="center_world_3d", length=3),
            ),
        )
        target_ids = [nearest]
        confidence = "low"
        hit_source = "nearest_basis_fallback"
    structure_id = None
    if observed_structures:
        for structure in observed_structures:
            if any(basis_id in set(structure.get("basis_ids", [])) for basis_id in target_ids):
                structure_id = str(structure.get("structure_id"))
                break
    return {
        "target_basis_ids": target_ids,
        "target_world_3d": target_point,
        "targeting_confidence": confidence,
        "source_ray_sample_record_id": str(ray_sample_record.get("ray_sample_record_id", "")),
        "target_ray_id": str(ray_sample_record.get("ray_sample_record_id", "")),
        "target_ray_index": ray_index,
        "target_ray_direction_world_3d": target_direction,
        "target_hit_depth": float(target_hit_depth) if target_hit_depth is not None else None,
        "target_structure_id": structure_id,
        "target_hit_source": hit_source,
        "is_authority_state": False,
    }


def implicit_request_to_input_projection(
    request: Mapping[str, Any],
    target: Mapping[str, Any],
) -> dict[str, dict[str, float]]:
    tool = str(request.get("tool", ""))
    target_basis_ids = [str(value) for value in target.get("target_basis_ids", [])]
    if not target_basis_ids:
        raise ValueError("implicit input projection requires target basis ids")
    signed_amplitude = canonical_implicit_signed_amplitude(request)
    if tool == "implicit_refine_probe":
        return {}
    if tool == "implicit_local_dampen":
        return {basis_id: {"density": signed_amplitude / len(target_basis_ids)} for basis_id in target_basis_ids}
    if tool == "implicit_local_excite":
        return {basis_id: {"density": signed_amplitude / len(target_basis_ids)} for basis_id in target_basis_ids}
    if tool == "implicit_directional_push":
        source_vector = request.get("source_vector_image", [1.0, 0.0])
        dx, dy = _finite_vector(source_vector, name="source_vector_image", length=2)
        length = math.sqrt(dx * dx + dy * dy) or 1.0
        per_basis_amplitude = signed_amplitude / len(target_basis_ids)
        return {
            basis_id: {
                "density": per_basis_amplitude,
                "direction_x": per_basis_amplitude * dx / length,
                "direction_y": per_basis_amplitude * dy / length,
                "direction_z": 0.0,
            }
            for basis_id in target_basis_ids
        }
    raise ValueError("unknown implicit tool")


def build_implicit_interaction_audit(
    request: Mapping[str, Any],
    *,
    target: Mapping[str, Any],
    source_state_id: str,
    input_projection: Mapping[str, Mapping[str, float]],
    control_descriptor: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    request_id = str(request["request_id"])
    command_id = implicit_command_id(request_id)
    audit_id = f"implicit-interaction-audit::{command_id}"
    source_projection_frame_id = _required_request_string(request, "source_projection_frame_id")
    request_source_state_id = _required_request_string(request, "source_state_id")
    request_source_ray_id = _required_request_string(request, "source_ray_sample_record_id")
    if request_source_state_id != str(source_state_id):
        raise ValueError("source_state_id does not match interaction state")
    target_source_ray_id = str(target.get("source_ray_sample_record_id", ""))
    if target_source_ray_id and target_source_ray_id != request_source_ray_id:
        raise ValueError("source_ray_sample_record_id does not match interaction target")
    signed_amplitude = canonical_implicit_signed_amplitude(request)
    schedule_weights = implicit_duration_schedule_weights(request.get("duration_ticks"))
    descriptor = dict(control_descriptor or {})
    copied_projection = {
        str(basis_id): {str(channel): _finite_number(value, name="input_projection") for channel, value in channels.items()}
        for basis_id, channels in input_projection.items()
    }
    return {
        "schema": IMPLICIT_INTERACTION_AUDIT_SCHEMA,
        "audit_id": audit_id,
        "status": "accepted",
        "request_id": request_id,
        "command_id": command_id,
        "tool": str(request.get("tool", "")),
        "source_projection_frame_id": source_projection_frame_id,
        "source_frame_tick": int(request.get("source_frame_tick", request.get("frame_tick", 0))),
        "source_state_id": request_source_state_id,
        "source_ray_sample_record_id": request_source_ray_id,
        "source_image_xy": _finite_vector(request.get("source_image_xy", []), name="source_image_xy", length=2),
        "radius_world": _finite_number(request.get("radius_world"), name="radius_world"),
        "duration_ticks": _finite_number(request.get("duration_ticks"), name="duration_ticks"),
        "amplitude_magnitude": abs(signed_amplitude),
        "signed_amplitude": signed_amplitude,
        "schedule_weights": list(descriptor.get("schedule_weights", schedule_weights)),
        "kappa_by_basis": copy.deepcopy(descriptor.get("kappa_by_basis", {})),
        "normalized_weights_by_basis": copy.deepcopy(descriptor.get("normalized_weights_by_basis", {})),
        "accepted_sequence": descriptor.get("accepted_sequence"),
        "start_tick": descriptor.get("start_tick"),
        "target_basis_ids": [
            str(value)
            for value in descriptor.get("target_basis_ids", target.get("target_basis_ids", []))
        ],
        "target_world_3d": list(target.get("target_world_3d", [])),
        "targeting_confidence": str(target.get("targeting_confidence", "")),
        "target_ray_id": str(target.get("target_ray_id", target.get("source_ray_sample_record_id", ""))),
        "target_ray_index": int(target.get("target_ray_index", 0)),
        "target_ray_direction_world_3d": [float(value) for value in target.get("target_ray_direction_world_3d", [])],
        "target_hit_depth": target.get("target_hit_depth"),
        "target_structure_id": target.get("target_structure_id"),
        "target_hit_source": str(target.get("target_hit_source", "")),
        "input_projection": copy.deepcopy(copied_projection),
        "raw_input_projection": copy.deepcopy(copied_projection),
        "realized_input_projection": {},
        "applications": [],
        "refinement_request_id": None,
        "refinement_patch_id": None,
        "result_state_id": None,
        "resulting_ray_sample_record_ids": [],
        "resulting_projection_frame_ids": [],
        "source_record_ids": [source_projection_frame_id, request_source_state_id, request_source_ray_id],
        "is_authority_state": False,
    }


def record_implicit_interaction_application(
    audit: Mapping[str, Any],
    *,
    tick: int,
    schedule_index: int,
    raw_input_projection: Mapping[str, Mapping[str, Any]],
    realized_input_projection: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    if audit.get("schema") != IMPLICIT_INTERACTION_AUDIT_SCHEMA:
        raise ValueError("implicit interaction audit schema mismatch")
    if isinstance(tick, bool) or not isinstance(tick, int) or tick < 0:
        raise ValueError("application tick must be a non-negative integer")
    if isinstance(schedule_index, bool) or not isinstance(schedule_index, int):
        raise ValueError("schedule_index must be an integer")
    schedule_weights = list(audit.get("schedule_weights", []))
    if schedule_index < 0 or schedule_index >= len(schedule_weights):
        raise ValueError("schedule_index outside interaction audit schedule")
    applications = list(audit.get("applications", []))
    if schedule_index != len(applications):
        raise ValueError("interaction audit applications must be recorded in schedule order")

    def copied_projection(projection: Mapping[str, Mapping[str, Any]], *, name: str) -> dict[str, dict[str, float]]:
        return {
            str(basis_id): {
                str(channel): _finite_number(value, name=name)
                for channel, value in channels.items()
            }
            for basis_id, channels in projection.items()
        }

    updated = copy.deepcopy(dict(audit))
    raw = copied_projection(raw_input_projection, name="raw_input_projection")
    realized = copied_projection(realized_input_projection, name="realized_input_projection")
    updated["applications"].append(
        {
            "tick": tick,
            "schedule_index": schedule_index,
            "schedule_weight": _finite_number(schedule_weights[schedule_index], name="schedule_weight"),
            "raw_input_projection": raw,
            "realized_input_projection": realized,
        }
    )
    updated["realized_input_projection"] = copy.deepcopy(realized)
    updated["status"] = "applied" if schedule_index == len(schedule_weights) - 1 else "in_progress"
    return updated
