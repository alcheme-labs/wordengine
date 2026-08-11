from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


FIELD_PLAY_GOAL_SCHEMA = "field_play_goal_v1"
FIELD_PLAY_PROGRESS_SCHEMA = "field_play_progress_v1"

GOAL_CASE_TYPES = {
    "damping_goal",
    "channel_goal",
    "source_goal",
    "combined_goal",
}

DEFAULT_VISIBLE_DELTA_REQUIREMENT = {
    "min_image_digest_count": 2,
    "min_non_background_delta": 0.002,
    "min_spectral_change_ratio": 0.01,
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


def _as_list(values: object) -> list[Any]:
    if values is None:
        return []
    if isinstance(values, list):
        return list(values)
    if isinstance(values, tuple):
        return list(values)
    return [values]


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _record_id(record: Mapping[str, object], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value:
            return str(value)
    return ""


def _frame_payload(frame: Mapping[str, object]) -> Mapping[str, object]:
    payload = frame.get("payload")
    return payload if isinstance(payload, Mapping) else {}


def _frame_tick(frame: Mapping[str, object]) -> int:
    try:
        return int(frame.get("tick", 0))
    except (TypeError, ValueError):
        return 0


def _frame_id(frame: Mapping[str, object]) -> str:
    return _record_id(frame, "frame_id", "id")


def _consequence_tool_kinds(record: Mapping[str, object]) -> list[str]:
    values: list[object] = []
    if "source_tool_kinds" in record:
        values.extend(_as_list(record.get("source_tool_kinds")))
    payload = record.get("payload")
    if isinstance(payload, Mapping):
        values.extend(_as_list(payload.get("source_tool_kinds")))
    return _unique(values)


def build_field_play_goal(
    *,
    goal_id: str,
    case_id: str,
    source_package_name: str,
    case_type: str,
    description: str,
    required_consequence_kinds: Sequence[str],
    required_tool_kinds: Sequence[str],
    target_window_ticks: Sequence[int],
    baseline_case_id: str,
    source_record_ids: Sequence[str],
    required_visible_delta: Mapping[str, object] | None = None,
) -> dict[str, object]:
    goal = {
        "schema": FIELD_PLAY_GOAL_SCHEMA,
        "goal_id": str(goal_id),
        "case_id": str(case_id),
        "source_package_name": str(source_package_name),
        "case_type": str(case_type),
        "description": str(description),
        "required_consequence_kinds": _unique(required_consequence_kinds),
        "required_tool_kinds": _unique(required_tool_kinds),
        "target_window_ticks": [int(target_window_ticks[0]), int(target_window_ticks[1])],
        "required_visible_delta": dict(required_visible_delta or DEFAULT_VISIBLE_DELTA_REQUIREMENT),
        "baseline_case_id": str(baseline_case_id),
        "source_record_ids": _unique(source_record_ids),
        "is_authority_state": False,
    }
    validate_field_play_goal(goal)
    return goal


def validate_field_play_goal(goal: Mapping[str, object]) -> None:
    if goal.get("schema") != FIELD_PLAY_GOAL_SCHEMA:
        raise ValueError("field play goal schema is required")
    if goal.get("is_authority_state") is True:
        raise ValueError("field play goal is not authority state")
    for key in ("goal_id", "case_id", "source_package_name", "description", "baseline_case_id"):
        if not goal.get(key):
            raise ValueError(f"{key} is required")
    if goal.get("case_type") not in GOAL_CASE_TYPES:
        raise ValueError("unsupported goal case type")
    if not goal.get("required_consequence_kinds"):
        raise ValueError("required_consequence_kinds is required")
    if not goal.get("required_tool_kinds"):
        raise ValueError("required_tool_kinds is required")
    target_window_ticks = goal.get("target_window_ticks")
    if not isinstance(target_window_ticks, list) or len(target_window_ticks) != 2:
        raise ValueError("target_window_ticks must be [start, end]")
    if int(target_window_ticks[1]) < int(target_window_ticks[0]):
        raise ValueError("target_window_ticks end must be >= start")
    requirements = goal.get("required_visible_delta")
    if not isinstance(requirements, Mapping):
        raise ValueError("required_visible_delta is required")
    for key in ("min_image_digest_count", "min_non_background_delta", "min_spectral_change_ratio"):
        if key not in requirements:
            raise ValueError(f"{key} is required")
    if not goal.get("source_record_ids"):
        raise ValueError("source_record_ids is required")


def evaluate_field_play_progress(
    *,
    goal: Mapping[str, object],
    consequence_records: Sequence[Mapping[str, object]],
    projection_frames: Sequence[Mapping[str, object]],
    baseline_projection_frames: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    validate_field_play_goal(goal)
    required_kinds = {str(value) for value in _as_list(goal.get("required_consequence_kinds"))}
    required_tools = {str(value) for value in _as_list(goal.get("required_tool_kinds"))}
    target_start, target_end = [int(value) for value in _as_list(goal.get("target_window_ticks"))[:2]]
    requirement = goal.get("required_visible_delta")
    assert isinstance(requirement, Mapping)

    matching_consequences: list[Mapping[str, object]] = []
    matched_tools: list[str] = []
    for record in consequence_records:
        kind = str(record.get("kind", ""))
        if kind in required_kinds and record.get("status") == "passed":
            matching_consequences.append(record)
            matched_tools.extend(_consequence_tool_kinds(record))

    matched_consequence_kinds = {str(record.get("kind", "")) for record in matching_consequences}
    missing: list[str] = [
        f"missing_required_consequence_kind:{kind}"
        for kind in sorted(required_kinds - matched_consequence_kinds)
    ]
    matched_tool_kinds = set(_unique(matched_tools))
    missing.extend(f"missing_required_tool_kind:{kind}" for kind in sorted(required_tools - matched_tool_kinds))

    consequence_frame_ids = {
        str(frame_id)
        for record in matching_consequences
        for frame_id in _as_list(record.get("projection_frame_ids"))
    }
    frames_by_id = {_frame_id(frame): frame for frame in projection_frames if _frame_id(frame)}
    matched_frames = [
        frames_by_id[frame_id]
        for frame_id in consequence_frame_ids
        if frame_id in frames_by_id and target_start <= _frame_tick(frames_by_id[frame_id]) <= target_end
    ]
    matched_frames.sort(key=_frame_tick)

    camera_frame_ids: list[str] = []
    image_digests: list[str] = []
    ratios: list[float] = []
    for frame in matched_frames:
        payload = _frame_payload(frame)
        camera = payload.get("spectral_camera_frame")
        if isinstance(camera, Mapping) and camera.get("frame_id"):
            camera_frame_ids.append(str(camera["frame_id"]))
        image_plane = payload.get("spectral_image_plane")
        if isinstance(image_plane, Mapping):
            if image_plane.get("image_digest"):
                image_digests.append(str(image_plane["image_digest"]))
            try:
                ratios.append(float(image_plane.get("non_background_ratio", 0.0)))
            except (TypeError, ValueError):
                ratios.append(0.0)

    baseline_ratios: list[float] = []
    for frame in baseline_projection_frames:
        image_plane = _frame_payload(frame).get("spectral_image_plane")
        if isinstance(image_plane, Mapping):
            try:
                baseline_ratios.append(float(image_plane.get("non_background_ratio", 0.0)))
            except (TypeError, ValueError):
                baseline_ratios.append(0.0)

    unique_digests = _unique(image_digests)
    baseline_mean = _mean(baseline_ratios)
    non_background_delta = max([abs(ratio - baseline_mean) for ratio in ratios] or [0.0])
    spectral_change_ratio = len(unique_digests) / max(1, len(matched_frames))
    visible_delta = {
        "image_digest_count": len(unique_digests),
        "non_background_delta": round(non_background_delta, 6),
        "spectral_change_ratio": round(spectral_change_ratio, 6),
    }
    if int(visible_delta["image_digest_count"]) < int(requirement["min_image_digest_count"]):
        missing.append("visible_delta_below_threshold")
    elif float(visible_delta["non_background_delta"]) < float(requirement["min_non_background_delta"]):
        missing.append("visible_delta_below_threshold")
    elif float(visible_delta["spectral_change_ratio"]) < float(requirement["min_spectral_change_ratio"]):
        missing.append("visible_delta_below_threshold")

    status = "achieved" if not missing else "failed"
    matched_consequence_ids = _unique(
        [_record_id(record, "consequence_id", "record_id", "id") for record in matching_consequences]
    )
    matched_projection_frame_ids = _unique([_frame_id(frame) for frame in matched_frames])
    source_record_ids = _unique(
        [
            str(goal["goal_id"]),
            *matched_consequence_ids,
            *matched_projection_frame_ids,
        ]
    )
    progress = {
        "schema": FIELD_PLAY_PROGRESS_SCHEMA,
        "progress_id": f"field-play-progress::{goal['case_id']}::{goal['goal_id']}",
        "goal_id": str(goal["goal_id"]),
        "case_id": str(goal["case_id"]),
        "status": status,
        "matched_consequence_ids": matched_consequence_ids,
        "matched_tool_kinds": _unique(sorted(matched_tool_kinds)),
        "matched_projection_frame_ids": matched_projection_frame_ids,
        "matched_spectral_camera_frame_ids": _unique(camera_frame_ids),
        "matched_spectral_image_plane_digests": unique_digests,
        "baseline_case_id": str(goal["baseline_case_id"]),
        "visible_delta": visible_delta,
        "missing_requirements": _unique(missing),
        "source_record_ids": source_record_ids,
        "is_authority_state": False,
    }
    validate_field_play_progress(progress, goal)
    return progress


def validate_field_play_progress(progress: Mapping[str, object], goal: Mapping[str, object]) -> None:
    validate_field_play_goal(goal)
    if progress.get("schema") != FIELD_PLAY_PROGRESS_SCHEMA:
        raise ValueError("field play progress schema is required")
    if progress.get("is_authority_state") is True:
        raise ValueError("field play progress is not authority state")
    if progress.get("goal_id") != goal.get("goal_id"):
        raise ValueError("progress goal_id must match goal")
    if progress.get("case_id") != goal.get("case_id"):
        raise ValueError("progress case_id must match goal")
    if progress.get("baseline_case_id") != goal.get("baseline_case_id"):
        raise ValueError("progress baseline_case_id must match goal")
    if progress.get("status") not in {"achieved", "active", "failed"}:
        raise ValueError("progress status is invalid")
    if not progress.get("source_record_ids"):
        raise ValueError("progress source_record_ids is required")
    visible_delta = progress.get("visible_delta")
    if not isinstance(visible_delta, Mapping):
        raise ValueError("progress visible_delta is required")
    for key in ("image_digest_count", "non_background_delta", "spectral_change_ratio"):
        if key not in visible_delta:
            raise ValueError(f"progress visible_delta.{key} is required")
    if progress.get("status") == "achieved":
        if not progress.get("matched_consequence_ids"):
            raise ValueError("achieved progress requires matched_consequence_ids")
        if not progress.get("matched_tool_kinds"):
            raise ValueError("achieved progress requires matched_tool_kinds")
        if not progress.get("matched_projection_frame_ids"):
            raise ValueError("achieved progress requires matched_projection_frame_ids")
        if not progress.get("matched_spectral_camera_frame_ids"):
            raise ValueError("achieved progress requires matched_spectral_camera_frame_ids")
        if not progress.get("matched_spectral_image_plane_digests"):
            raise ValueError("achieved progress requires matched_spectral_image_plane_digests")
