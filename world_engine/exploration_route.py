from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


FIELD_ROUTE_NODE_SCHEMA = "field_route_node_v1"
FIELD_ROUTE_EDGE_SCHEMA = "field_route_edge_v1"
FIELD_ROUTE_STEP_SCHEMA = "field_route_step_record_v1"
FIELD_EXPLORATION_STATE_SCHEMA = "field_exploration_state_v1"

ALLOWED_NODE_KINDS = {"origin", "surface_gate", "channel", "emitter", "exit"}
ALLOWED_ROUTE_STEP_STATUSES = {"accepted", "rejected"}
ALLOWED_ROUTE_REJECTION_REASONS = {
    "",
    "edge_locked",
    "missing_signature",
    "missing_progress",
    "missing_tool_unlock",
    "outside_window",
}


def _unique(values: Sequence[object]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _as_list(value: object) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _round(value: float) -> float:
    return round(float(value), 6)


def _require(record: Mapping[str, object], key: str) -> None:
    if not record.get(key):
        raise ValueError(f"{key} is required")


def _reject_authority(record: Mapping[str, object], name: str) -> None:
    if record.get("is_authority_state") is True:
        raise ValueError(f"{name} is not authority state")


def _record_id(record: Mapping[str, object], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value:
            return str(value)
    return ""


def build_field_route_node(
    *,
    node_id: str,
    case_id: str,
    node_kind: str,
    field_signature_instance_ids: Sequence[str],
    required_goal_ids: Sequence[str],
    position_hint_world: Mapping[str, float],
    source_record_ids: Sequence[str],
) -> dict[str, object]:
    node = {
        "schema": FIELD_ROUTE_NODE_SCHEMA,
        "node_id": str(node_id),
        "case_id": str(case_id),
        "node_kind": str(node_kind),
        "field_signature_instance_ids": _unique(field_signature_instance_ids),
        "required_goal_ids": _unique(required_goal_ids),
        "position_hint_world": {str(key): float(value) for key, value in position_hint_world.items()},
        "source_record_ids": _unique(source_record_ids),
        "is_authority_state": False,
    }
    validate_field_route_node(node)
    return node


def validate_field_route_node(node: Mapping[str, object]) -> None:
    if node.get("schema") != FIELD_ROUTE_NODE_SCHEMA:
        raise ValueError("field route node schema is required")
    _reject_authority(node, "field route node")
    for key in ("node_id", "case_id", "field_signature_instance_ids", "source_record_ids"):
        _require(node, key)
    if node.get("node_kind") not in ALLOWED_NODE_KINDS:
        raise ValueError("unsupported route node kind")
    position = node.get("position_hint_world")
    if not isinstance(position, Mapping):
        raise ValueError("position_hint_world must be a mapping")
    for key in ("x", "y", "z"):
        if key not in position:
            raise ValueError(f"position_hint_world.{key} is required")


def build_field_route_edge(
    *,
    edge_id: str,
    case_id: str,
    from_node_id: str,
    to_node_id: str,
    required_unlocked_tool_ids: Sequence[str],
    required_progress_ids: Sequence[str],
    required_signature_instance_ids: Sequence[str],
    required_feedback_kinds: Sequence[str],
    traversal_window_ticks: Sequence[int],
    source_record_ids: Sequence[str],
) -> dict[str, object]:
    edge = {
        "schema": FIELD_ROUTE_EDGE_SCHEMA,
        "edge_id": str(edge_id),
        "case_id": str(case_id),
        "from_node_id": str(from_node_id),
        "to_node_id": str(to_node_id),
        "required_unlocked_tool_ids": _unique(required_unlocked_tool_ids),
        "required_progress_ids": _unique(required_progress_ids),
        "required_signature_instance_ids": _unique(required_signature_instance_ids),
        "required_feedback_kinds": _unique(required_feedback_kinds),
        "traversal_window_ticks": [int(value) for value in traversal_window_ticks],
        "source_record_ids": _unique(source_record_ids),
        "is_authority_state": False,
    }
    validate_field_route_edge(edge)
    return edge


def validate_field_route_edge(edge: Mapping[str, object]) -> None:
    if edge.get("schema") != FIELD_ROUTE_EDGE_SCHEMA:
        raise ValueError("field route edge schema is required")
    _reject_authority(edge, "field route edge")
    for key in ("edge_id", "case_id", "from_node_id", "to_node_id", "source_record_ids"):
        _require(edge, key)
    window = edge.get("traversal_window_ticks")
    if not isinstance(window, list) or len(window) != 2:
        raise ValueError("traversal_window_ticks must be [start, end]")
    if int(window[1]) < int(window[0]):
        raise ValueError("traversal window end must be >= start")
    for key in (
        "required_unlocked_tool_ids",
        "required_progress_ids",
        "required_signature_instance_ids",
        "required_feedback_kinds",
    ):
        if not isinstance(edge.get(key), list):
            raise ValueError(f"{key} must be a list")


def _available_tool_ids(tool_use_records: Sequence[Mapping[str, object]], tick: int) -> set[str]:
    return {
        str(record.get("tool_id"))
        for record in tool_use_records
        if record.get("status") == "accepted" and _as_int(record.get("tick"), tick) <= tick and record.get("tool_id")
    }


def _available_progress_ids(progress_records: Sequence[Mapping[str, object]]) -> set[str]:
    return {
        str(record.get("progress_id"))
        for record in progress_records
        if record.get("status") == "achieved" and record.get("progress_id")
    }


def _available_signature_ids(signature_instances: Sequence[Mapping[str, object]]) -> set[str]:
    return {
        _record_id(record, "instance_id", "id", "record_id")
        for record in signature_instances
        if _record_id(record, "instance_id", "id", "record_id")
    }


def _available_feedback_kinds(feedback_records: Sequence[Mapping[str, object]], tick: int) -> set[str]:
    return {
        str(record.get("kind"))
        for record in feedback_records
        if _as_int(record.get("tick"), tick) <= tick and record.get("kind")
    }


def _unlocked_tool_ids_from_feedback(feedback_records: Sequence[Mapping[str, object]], tick: int) -> set[str]:
    return {
        str(tool_id)
        for record in feedback_records
        if _as_int(record.get("tick"), tick) <= tick
        for tool_id in _as_list(record.get("unlocked_tool_ids"))
    }


def _edge_rejection_reason(
    *,
    edge: Mapping[str, object],
    tick: int,
    prior_state: Mapping[str, object],
    tool_use_records: Sequence[Mapping[str, object]],
    progress_records: Sequence[Mapping[str, object]],
    feedback_records: Sequence[Mapping[str, object]],
    signature_instances: Sequence[Mapping[str, object]],
) -> str:
    validate_field_route_edge(edge)
    if str(prior_state.get("current_node_id", "")) and prior_state.get("current_node_id") != edge.get("from_node_id"):
        return "edge_locked"
    start, end = [int(value) for value in edge["traversal_window_ticks"]]
    if tick < start or tick > end:
        return "outside_window"
    required_signatures = set(edge.get("required_signature_instance_ids", []))
    if not required_signatures.issubset(_available_signature_ids(signature_instances)):
        return "missing_signature"
    required_progress = set(edge.get("required_progress_ids", []))
    if not required_progress.issubset(_available_progress_ids(progress_records)):
        return "missing_progress"
    required_tools = set(edge.get("required_unlocked_tool_ids", []))
    available_tools = _available_tool_ids(tool_use_records, tick) | _unlocked_tool_ids_from_feedback(feedback_records, tick)
    if not required_tools.issubset(available_tools):
        return "missing_tool_unlock"
    required_feedback_kinds = set(edge.get("required_feedback_kinds", []))
    if not required_feedback_kinds.issubset(_available_feedback_kinds(feedback_records, tick)):
        return "edge_locked"
    return ""


def _projection_evidence(
    progress_records: Sequence[Mapping[str, object]],
    projection_frames: Sequence[Mapping[str, object]],
    required_progress_ids: set[str],
) -> tuple[list[str], list[str], list[str]]:
    frame_ids: list[str] = []
    camera_ids: list[str] = []
    digests: list[str] = []
    for progress in progress_records:
        if str(progress.get("progress_id", "")) not in required_progress_ids:
            continue
        frame_ids.extend(str(value) for value in _as_list(progress.get("matched_projection_frame_ids")))
        camera_ids.extend(str(value) for value in _as_list(progress.get("matched_spectral_camera_frame_ids")))
        digests.extend(str(value) for value in _as_list(progress.get("matched_spectral_image_plane_digests")))
    frames_by_id = {_record_id(frame, "frame_id", "id"): frame for frame in projection_frames}
    for frame_id in frame_ids:
        frame = frames_by_id.get(frame_id)
        if not frame:
            continue
        payload = frame.get("payload", {})
        if isinstance(payload, Mapping):
            camera = payload.get("spectral_camera_frame")
            if isinstance(camera, Mapping) and camera.get("frame_id"):
                camera_ids.append(str(camera["frame_id"]))
            image_plane = payload.get("spectral_image_plane")
            if isinstance(image_plane, Mapping) and image_plane.get("image_digest"):
                digests.append(str(image_plane["image_digest"]))
    return _unique(frame_ids), _unique(camera_ids), _unique(digests)


def build_field_route_step_record(
    *,
    route_step_id: str,
    case_id: str,
    tick: int,
    edge: Mapping[str, object],
    prior_state: Mapping[str, object],
    tool_use_records: Sequence[Mapping[str, object]],
    progress_records: Sequence[Mapping[str, object]],
    feedback_records: Sequence[Mapping[str, object]],
    signature_instances: Sequence[Mapping[str, object]],
    projection_frames: Sequence[Mapping[str, object]],
    baseline_case_id: str,
) -> dict[str, object]:
    reason = _edge_rejection_reason(
        edge=edge,
        tick=tick,
        prior_state=prior_state,
        tool_use_records=tool_use_records,
        progress_records=progress_records,
        feedback_records=feedback_records,
        signature_instances=signature_instances,
    )
    status = "accepted" if not reason else "rejected"
    required_progress_ids = {str(value) for value in _as_list(edge.get("required_progress_ids"))}
    required_signature_ids = {str(value) for value in _as_list(edge.get("required_signature_instance_ids"))}
    required_feedback_kinds = {str(value) for value in _as_list(edge.get("required_feedback_kinds"))}
    required_tool_ids = {str(value) for value in _as_list(edge.get("required_unlocked_tool_ids"))}
    if status == "accepted":
        projection_frame_ids, camera_frame_ids, image_digests = _projection_evidence(
            progress_records,
            projection_frames,
            required_progress_ids,
        )
        source_tool_use_ids = _unique(
            [
                str(record.get("tool_use_id"))
                for record in tool_use_records
                if record.get("status") == "accepted" and str(record.get("tool_id")) in required_tool_ids
            ]
        )
        source_feedback_ids = _unique(
            [
                str(record.get("feedback_id"))
                for record in feedback_records
                if str(record.get("kind")) in required_feedback_kinds
                or bool(required_tool_ids & {str(tool_id) for tool_id in _as_list(record.get("unlocked_tool_ids"))})
            ]
        )
        source_progress_ids = _unique(required_progress_ids)
        source_signature_instance_ids = _unique(required_signature_ids)
        source_record_ids = _unique(
            [
                str(route_step_id),
                str(edge.get("edge_id", "")),
                *source_tool_use_ids,
                *source_progress_ids,
                *source_signature_instance_ids,
                *source_feedback_ids,
                *projection_frame_ids,
            ]
        )
        baseline = str(baseline_case_id)
    else:
        source_tool_use_ids = []
        source_progress_ids = []
        source_signature_instance_ids = []
        source_feedback_ids = []
        projection_frame_ids = []
        camera_frame_ids = []
        image_digests = []
        source_record_ids = [str(route_step_id), str(edge.get("edge_id", ""))]
        baseline = ""
    step = {
        "schema": FIELD_ROUTE_STEP_SCHEMA,
        "route_step_id": str(route_step_id),
        "case_id": str(case_id),
        "tick": int(tick),
        "edge_id": str(edge.get("edge_id", "")),
        "from_node_id": str(edge.get("from_node_id", "")),
        "to_node_id": str(edge.get("to_node_id", "")),
        "status": status,
        "rejection_reason": reason,
        "source_tool_use_ids": source_tool_use_ids,
        "source_progress_ids": source_progress_ids,
        "source_signature_instance_ids": source_signature_instance_ids,
        "source_feedback_ids": source_feedback_ids,
        "source_projection_frame_ids": projection_frame_ids,
        "source_spectral_camera_frame_ids": camera_frame_ids,
        "source_spectral_image_plane_digests": image_digests,
        "baseline_case_id": baseline,
        "source_record_ids": source_record_ids,
        "is_authority_state": False,
    }
    validate_field_route_step_record(step)
    return step


def validate_field_route_step_record(step: Mapping[str, object]) -> None:
    if step.get("schema") != FIELD_ROUTE_STEP_SCHEMA:
        raise ValueError("field route step schema is required")
    _reject_authority(step, "field route step")
    for key in ("route_step_id", "case_id", "edge_id", "from_node_id", "to_node_id", "source_record_ids"):
        _require(step, key)
    status = step.get("status")
    if status not in ALLOWED_ROUTE_STEP_STATUSES:
        raise ValueError("route step status is invalid")
    reason = str(step.get("rejection_reason", ""))
    if reason not in ALLOWED_ROUTE_REJECTION_REASONS:
        raise ValueError("route step rejection reason is invalid")
    if status == "accepted":
        if reason:
            raise ValueError("accepted route step cannot have rejection reason")
        for key in (
            "source_progress_ids",
            "source_signature_instance_ids",
            "source_projection_frame_ids",
            "source_spectral_camera_frame_ids",
            "source_spectral_image_plane_digests",
            "baseline_case_id",
        ):
            _require(step, key)
    else:
        if not reason:
            raise ValueError("rejected route step requires rejection reason")
        for key in (
            "source_projection_frame_ids",
            "source_spectral_camera_frame_ids",
            "source_spectral_image_plane_digests",
            "baseline_case_id",
        ):
            if step.get(key):
                raise ValueError("rejected route step cannot carry field projection evidence")


def build_field_exploration_state(
    *,
    exploration_state_id: str,
    case_id: str,
    tick: int,
    current_node_id: str,
    visited_node_ids: Sequence[str],
    open_edge_ids: Sequence[str],
    accepted_route_step_ids: Sequence[str],
    rejected_route_step_ids: Sequence[str],
    route_score: float,
    completed_route: bool,
    source_record_ids: Sequence[str],
) -> dict[str, object]:
    state = {
        "schema": FIELD_EXPLORATION_STATE_SCHEMA,
        "exploration_state_id": str(exploration_state_id),
        "case_id": str(case_id),
        "tick": int(tick),
        "current_node_id": str(current_node_id),
        "visited_node_ids": _unique(visited_node_ids),
        "open_edge_ids": _unique(open_edge_ids),
        "accepted_route_step_ids": _unique(accepted_route_step_ids),
        "rejected_route_step_ids": _unique(rejected_route_step_ids),
        "route_score": _round(route_score),
        "completed_route": bool(completed_route),
        "source_record_ids": _unique(source_record_ids),
        "is_authority_state": False,
    }
    validate_field_exploration_state(state)
    return state


def validate_field_exploration_state(state: Mapping[str, object]) -> None:
    if state.get("schema") != FIELD_EXPLORATION_STATE_SCHEMA:
        raise ValueError("field exploration state schema is required")
    _reject_authority(state, "field exploration state")
    for key in ("exploration_state_id", "case_id", "current_node_id", "visited_node_ids", "source_record_ids"):
        _require(state, key)
    for key in ("open_edge_ids", "accepted_route_step_ids", "rejected_route_step_ids"):
        if not isinstance(state.get(key), list):
            raise ValueError(f"{key} must be a list")
    if "route_score" not in state:
        raise ValueError("route_score is required")
    if "completed_route" not in state:
        raise ValueError("completed_route is required")


def replay_field_exploration_state(
    *,
    case_id: str,
    tick: int,
    initial_node_id: str,
    exit_node_id: str,
    route_nodes: Sequence[Mapping[str, object]],
    route_edges: Sequence[Mapping[str, object]],
    route_step_records: Sequence[Mapping[str, object]],
    tool_use_records: Sequence[Mapping[str, object]],
    progress_records: Sequence[Mapping[str, object]],
    feedback_records: Sequence[Mapping[str, object]],
    signature_instances: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    for node in route_nodes:
        validate_field_route_node(node)
    for edge in route_edges:
        validate_field_route_edge(edge)
    current_node_id = str(initial_node_id)
    visited_node_ids = [current_node_id]
    accepted_step_ids: list[str] = []
    rejected_step_ids: list[str] = []
    route_score = 0.0
    relevant_steps = [
        dict(step)
        for step in route_step_records
        if str(step.get("case_id")) == str(case_id) and _as_int(step.get("tick"), 0) <= int(tick)
    ]
    relevant_steps.sort(key=lambda step: (_as_int(step.get("tick"), 0), str(step.get("route_step_id", ""))))
    for step in relevant_steps:
        validate_field_route_step_record(step)
        if step.get("status") == "accepted" and step.get("from_node_id") == current_node_id:
            current_node_id = str(step.get("to_node_id"))
            visited_node_ids.append(current_node_id)
            accepted_step_ids.append(str(step["route_step_id"]))
            route_score += 1.0
        else:
            rejected_step_ids.append(str(step["route_step_id"]))
    open_edge_ids = [
        str(edge["edge_id"])
        for edge in route_edges
        if not _edge_rejection_reason(
            edge=edge,
            tick=int(tick),
            prior_state={"current_node_id": edge.get("from_node_id", "")},
            tool_use_records=tool_use_records,
            progress_records=progress_records,
            feedback_records=feedback_records,
            signature_instances=signature_instances,
        )
    ]
    source_record_ids = _unique([*accepted_step_ids, *rejected_step_ids, *open_edge_ids, *visited_node_ids])
    return build_field_exploration_state(
        exploration_state_id=f"field-exploration-state::{case_id}::{int(tick)}",
        case_id=case_id,
        tick=int(tick),
        current_node_id=current_node_id,
        visited_node_ids=visited_node_ids,
        open_edge_ids=open_edge_ids,
        accepted_route_step_ids=accepted_step_ids,
        rejected_route_step_ids=rejected_step_ids,
        route_score=route_score,
        completed_route=current_node_id == str(exit_node_id),
        source_record_ids=source_record_ids or [f"field-exploration-state::{case_id}::{int(tick)}"],
    )
