from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping, Sequence


IMPLICIT_CAMERA_MOVE_REQUEST_SCHEMA = "implicit_camera_move_request"
IMPLICIT_CAMERA_MOVE_RECORD_SCHEMA = "implicit_camera_move_record"
ALLOWED_IMPLICIT_CAMERA_ACTIONS = {"forward", "back", "strafe_left", "strafe_right", "orbit_left", "orbit_right", "reset"}


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _finite_number(value: Any, *, name: str) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


def _finite_vector(values: Sequence[Any], *, name: str, length: int = 3) -> list[float]:
    if len(values) != length:
        raise ValueError(f"{name} must have length {length}")
    return [_finite_number(value, name=name) for value in values]


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


def _normalize(vector: Sequence[float]) -> list[float]:
    length = math.sqrt(_dot(vector, vector))
    if length <= 1e-12:
        raise ValueError("cannot normalize zero vector")
    return [float(value) / length for value in vector]


def _pose_basis(camera_pose: Mapping[str, Any]) -> tuple[list[float], list[float], list[float], list[float]]:
    origin = _finite_vector(camera_pose.get("origin", []), name="camera_pose.origin")
    look_at = _finite_vector(camera_pose.get("look_at", []), name="camera_pose.look_at")
    up_hint = _normalize(_finite_vector(camera_pose.get("up", [0.0, 0.0, 1.0]), name="camera_pose.up"))
    forward = _normalize(_sub(look_at, origin))
    right = _normalize(_cross(forward, up_hint))
    up = _normalize(_cross(right, forward))
    return origin, look_at, forward, right if _dot(right, right) else up


def _rotate_around_up(origin: Sequence[float], look_at: Sequence[float], up: Sequence[float], degrees: float) -> list[float]:
    angle = math.radians(float(degrees))
    relative = _sub(origin, look_at)
    axis = _normalize(up)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    cross = _cross(axis, relative)
    dot = _dot(axis, relative)
    rotated = [
        relative[index] * cos_a + cross[index] * sin_a + axis[index] * dot * (1.0 - cos_a)
        for index in range(3)
    ]
    return _add(look_at, rotated)


def validate_implicit_camera_move_request(
    request: Mapping[str, Any],
    *,
    declared_observer_ids: set[str],
    existing_request_ids: set[str],
    known_projection_frames_by_id: Mapping[str, Mapping[str, Any]],
) -> None:
    if request.get("schema") != IMPLICIT_CAMERA_MOVE_REQUEST_SCHEMA:
        raise ValueError("implicit camera move request schema mismatch")
    request_id = str(request.get("request_id", ""))
    if not request_id:
        raise ValueError("implicit camera move request requires request_id")
    if request_id in existing_request_ids:
        raise ValueError("duplicate implicit camera request_id")
    observer_id = str(request.get("observer_id", ""))
    if observer_id not in declared_observer_ids:
        raise ValueError("undeclared implicit camera observer_id")
    frame_id = str(request.get("source_projection_frame_id", ""))
    if frame_id not in known_projection_frames_by_id:
        raise ValueError("unknown source_projection_frame_id")
    source_frame = known_projection_frames_by_id[frame_id]
    if int(request.get("source_frame_tick", -1)) != int(source_frame.get("tick", -2)):
        raise ValueError("source_frame_tick does not match source_projection_frame_id")
    action = str(request.get("action", ""))
    if action not in ALLOWED_IMPLICIT_CAMERA_ACTIONS:
        raise ValueError("unsupported implicit camera action")
    step = _finite_number(request.get("step_world", 0.0), name="step_world")
    if step < 0.0 or step > 1.0:
        raise ValueError("step_world outside bounds")
    yaw = _finite_number(request.get("yaw_degrees", 0.0), name="yaw_degrees")
    if abs(yaw) > 20.0:
        raise ValueError("yaw_degrees outside bounds")


def apply_implicit_camera_move(
    camera_pose: Mapping[str, Any],
    request: Mapping[str, Any],
    *,
    initial_camera_pose: Mapping[str, Any],
) -> dict[str, Any]:
    action = str(request.get("action", ""))
    if action == "reset":
        return dict(initial_camera_pose)
    origin, look_at, forward, right = _pose_basis(camera_pose)
    up = _finite_vector(camera_pose.get("up", [0.0, 0.0, 1.0]), name="camera_pose.up")
    step = _finite_number(request.get("step_world", 0.0), name="step_world")
    yaw = _finite_number(request.get("yaw_degrees", 0.0), name="yaw_degrees")
    if action == "forward":
        delta = _scale(forward, step)
        origin = _add(origin, delta)
        look_at = _add(look_at, delta)
    elif action == "back":
        delta = _scale(forward, -step)
        origin = _add(origin, delta)
        look_at = _add(look_at, delta)
    elif action == "strafe_left":
        delta = _scale(right, -step)
        origin = _add(origin, delta)
        look_at = _add(look_at, delta)
    elif action == "strafe_right":
        delta = _scale(right, step)
        origin = _add(origin, delta)
        look_at = _add(look_at, delta)
    elif action == "orbit_left":
        origin = _rotate_around_up(origin, look_at, up, yaw or 8.0)
    elif action == "orbit_right":
        origin = _rotate_around_up(origin, look_at, up, -(yaw or 8.0))
    else:
        raise ValueError("unsupported implicit camera action")
    return {
        "origin": [round(value, 6) for value in origin],
        "look_at": [round(value, 6) for value in look_at],
        "up": [round(value, 6) for value in up],
        "fov_degrees": float(camera_pose.get("fov_degrees", 50.0)),
    }


def build_implicit_camera_move_record(
    request: Mapping[str, Any],
    *,
    previous_camera_pose: Mapping[str, Any],
    result_camera_pose: Mapping[str, Any],
    previous_state_id: str,
    result_state_id: str,
    previous_state_digest: str,
    result_state_digest: str,
) -> dict[str, Any]:
    request_id = str(request["request_id"])
    record = {
        "schema": IMPLICIT_CAMERA_MOVE_RECORD_SCHEMA,
        "camera_move_id": f"implicit-camera-move::{request_id}",
        "request_id": request_id,
        "observer_id": str(request["observer_id"]),
        "source_projection_frame_id": str(request.get("source_projection_frame_id", "")),
        "source_frame_tick": int(request.get("source_frame_tick", 0)),
        "action": str(request.get("action", "")),
        "previous_camera_pose": dict(previous_camera_pose),
        "result_camera_pose": dict(result_camera_pose),
        "previous_camera_pose_digest": _canonical_digest(previous_camera_pose),
        "result_camera_pose_digest": _canonical_digest(result_camera_pose),
        "previous_state_id": str(previous_state_id),
        "result_state_id": str(result_state_id),
        "previous_state_digest": str(previous_state_digest),
        "result_state_digest": str(result_state_digest),
        "state_digest_unchanged": str(previous_state_digest) == str(result_state_digest),
        "world_state_changed": str(previous_state_id) != str(result_state_id) or str(previous_state_digest) != str(result_state_digest),
        "source_record_ids": [f"implicit-camera-move-request::{request_id}", str(request.get("source_projection_frame_id", ""))],
        "is_authority_state": False,
    }
    if record["world_state_changed"]:
        raise ValueError("implicit camera move cannot change world state")
    return record


def complete_implicit_camera_move_record(
    record: Mapping[str, Any],
    *,
    ray_sample_record_id: str,
    image_plane_id: str,
    projection_frame_id: str,
) -> dict[str, Any]:
    completed = dict(record)
    completed.update(
        {
            "result_ray_sample_record_id": str(ray_sample_record_id),
            "result_image_plane_id": str(image_plane_id),
            "result_projection_frame_id": str(projection_frame_id),
            "source_record_ids": sorted(set(list(record.get("source_record_ids", [])) + [ray_sample_record_id, image_plane_id, projection_frame_id])),
        }
    )
    return completed
