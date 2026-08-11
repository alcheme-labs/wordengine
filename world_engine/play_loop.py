from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


FIELD_PLAY_INITIAL_STATE_SCHEMA = "field_play_initial_state_v1"
FIELD_TOOL_PROFILE_SCHEMA = "field_tool_profile_v1"
FIELD_TOOL_USE_SCHEMA = "field_tool_use_record_v1"
FIELD_PLAY_FEEDBACK_SCHEMA = "field_play_feedback_v1"
FIELD_PLAY_LOOP_STATE_SCHEMA = "field_play_loop_state_v1"

ALLOWED_TOOL_KINDS = {
    "local_dampen",
    "place_channel_region",
    "sustained_source",
    "local_excite",
}

ALLOWED_FEEDBACK_KINDS = {"reward", "risk", "unlock", "blocked"}
ALLOWED_TOOL_USE_STATUS = {"accepted", "rejected"}
ALLOWED_REJECTION_REASONS = {
    "",
    "locked_tool",
    "cooldown_active",
    "insufficient_energy",
    "risk_limit_exceeded",
    "unknown_tool",
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


def _as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _round(value: float) -> float:
    return round(float(value), 6)


def _cooldowns(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): int(raw) for key, raw in value.items()}


def _require(record: Mapping[str, object], key: str) -> None:
    if not record.get(key):
        raise ValueError(f"{key} is required")


def _reject_authority(record: Mapping[str, object], name: str) -> None:
    if record.get("is_authority_state") is True:
        raise ValueError(f"{name} is not authority state")


def build_field_play_initial_state(
    *,
    initial_state_id: str,
    case_id: str,
    tick: int,
    tool_energy: float,
    risk_level: float,
    score: float,
    cooldowns: Mapping[str, int],
    unlocked_tool_ids: Sequence[str],
    source_record_ids: Sequence[str],
) -> dict[str, object]:
    state = {
        "schema": FIELD_PLAY_INITIAL_STATE_SCHEMA,
        "initial_state_id": str(initial_state_id),
        "case_id": str(case_id),
        "tick": int(tick),
        "tool_energy": _round(tool_energy),
        "risk_level": _round(risk_level),
        "score": _round(score),
        "cooldowns": _cooldowns(cooldowns),
        "unlocked_tool_ids": _unique(unlocked_tool_ids),
        "source_record_ids": _unique(source_record_ids),
        "is_authority_state": False,
    }
    validate_field_play_initial_state(state)
    return state


def validate_field_play_initial_state(state: Mapping[str, object]) -> None:
    if state.get("schema") != FIELD_PLAY_INITIAL_STATE_SCHEMA:
        raise ValueError("field play initial state schema is required")
    _reject_authority(state, "field play initial state")
    for key in ("initial_state_id", "case_id", "source_record_ids"):
        _require(state, key)
    if _as_int(state.get("tick"), -1) < 0:
        raise ValueError("tick must be non-negative")
    for key in ("tool_energy", "risk_level", "score"):
        if key not in state:
            raise ValueError(f"{key} is required")
    if not isinstance(state.get("cooldowns"), Mapping):
        raise ValueError("cooldowns must be a mapping")
    if not isinstance(state.get("unlocked_tool_ids"), list):
        raise ValueError("unlocked_tool_ids must be a list")


def build_field_tool_profile(
    *,
    tool_id: str,
    case_id: str,
    tool_kind: str,
    display_name: str,
    allowed_consequence_kinds: Sequence[str],
    energy_cost: float,
    cooldown_ticks: int,
    risk_delta_on_use: float,
    risk_limit: float,
    unlock_requirements: Mapping[str, object],
    source_record_ids: Sequence[str],
) -> dict[str, object]:
    profile = {
        "schema": FIELD_TOOL_PROFILE_SCHEMA,
        "tool_id": str(tool_id),
        "case_id": str(case_id),
        "tool_kind": str(tool_kind),
        "display_name": str(display_name),
        "allowed_consequence_kinds": _unique(allowed_consequence_kinds),
        "energy_cost": _round(energy_cost),
        "cooldown_ticks": int(cooldown_ticks),
        "risk_delta_on_use": _round(risk_delta_on_use),
        "risk_limit": _round(risk_limit),
        "unlock_requirements": dict(unlock_requirements),
        "source_record_ids": _unique(source_record_ids),
        "is_authority_state": False,
    }
    validate_field_tool_profile(profile)
    return profile


def validate_field_tool_profile(profile: Mapping[str, object]) -> None:
    if profile.get("schema") != FIELD_TOOL_PROFILE_SCHEMA:
        raise ValueError("field tool profile schema is required")
    _reject_authority(profile, "field tool profile")
    for key in ("tool_id", "case_id", "tool_kind", "display_name", "source_record_ids"):
        _require(profile, key)
    if profile.get("tool_kind") not in ALLOWED_TOOL_KINDS:
        raise ValueError("unsupported tool kind")
    if not profile.get("allowed_consequence_kinds"):
        raise ValueError("allowed_consequence_kinds is required")
    if _as_float(profile.get("energy_cost"), -1.0) < 0.0:
        raise ValueError("energy_cost must be non-negative")
    if _as_int(profile.get("cooldown_ticks"), -1) < 0:
        raise ValueError("cooldown_ticks must be non-negative")
    if _as_float(profile.get("risk_limit"), -1.0) < 0.0:
        raise ValueError("risk_limit must be non-negative")
    requirements = profile.get("unlock_requirements")
    if not isinstance(requirements, Mapping):
        raise ValueError("unlock_requirements must be a mapping")
    if "min_score" not in requirements or "required_feedback_kinds" not in requirements:
        raise ValueError("unlock_requirements must include min_score and required_feedback_kinds")


def _state_id(state: Mapping[str, object]) -> str:
    return str(state.get("loop_state_id") or state.get("initial_state_id") or "")


def _state_unlocked(state: Mapping[str, object]) -> set[str]:
    return {str(value) for value in _as_list(state.get("unlocked_tool_ids"))}


def _expected_tool_use(
    *,
    tool_use_id: str,
    case_id: str,
    tick: int,
    profile: Mapping[str, object] | None,
    prior_state: Mapping[str, object],
    requested_command_id: str,
) -> dict[str, object]:
    energy_before = _round(_as_float(prior_state.get("tool_energy")))
    risk_before = _round(_as_float(prior_state.get("risk_level")))
    cooldowns = _cooldowns(prior_state.get("cooldowns"))
    source_record_ids: list[str] = []

    status = "accepted"
    reason = ""
    if profile is None:
        tool_id = ""
        tool_kind = ""
        cooldown_until_tick = int(tick)
        status = "rejected"
        reason = "unknown_tool"
    else:
        validate_field_tool_profile(profile)
        tool_id = str(profile["tool_id"])
        tool_kind = str(profile["tool_kind"])
        cooldown_until_tick = int(tick) + int(profile["cooldown_ticks"])
        source_record_ids.extend(_as_list(profile.get("source_record_ids")))
        if tool_id not in _state_unlocked(prior_state):
            status = "rejected"
            reason = "locked_tool"
        elif cooldowns.get(tool_id, -1) > int(tick):
            status = "rejected"
            reason = "cooldown_active"
            cooldown_until_tick = cooldowns[tool_id]
        elif energy_before < _as_float(profile.get("energy_cost")):
            status = "rejected"
            reason = "insufficient_energy"
        elif risk_before + _as_float(profile.get("risk_delta_on_use")) > _as_float(profile.get("risk_limit")):
            status = "rejected"
            reason = "risk_limit_exceeded"

    if status == "accepted" and profile is not None:
        energy_after = _round(energy_before - _as_float(profile.get("energy_cost")))
        risk_after = _round(risk_before + _as_float(profile.get("risk_delta_on_use")))
        source_command_ids = [str(requested_command_id)]
    else:
        energy_after = energy_before
        risk_after = risk_before
        source_command_ids = []

    return {
        "schema": FIELD_TOOL_USE_SCHEMA,
        "tool_use_id": str(tool_use_id),
        "case_id": str(case_id),
        "tick": int(tick),
        "tool_id": tool_id,
        "tool_kind": tool_kind,
        "requested_command_id": str(requested_command_id),
        "status": status,
        "rejection_reason": reason,
        "energy_before": energy_before,
        "energy_after": energy_after,
        "risk_before": risk_before,
        "risk_after": risk_after,
        "cooldown_until_tick": int(cooldown_until_tick),
        "source_command_ids": source_command_ids,
        "source_record_ids": _unique([*source_record_ids, _state_id(prior_state)]),
        "is_authority_state": False,
    }


def build_field_tool_use_record(
    *,
    tool_use_id: str,
    case_id: str,
    tick: int,
    profile: Mapping[str, object] | None,
    prior_state: Mapping[str, object],
    requested_command_id: str,
) -> dict[str, object]:
    record = _expected_tool_use(
        tool_use_id=tool_use_id,
        case_id=case_id,
        tick=tick,
        profile=profile,
        prior_state=prior_state,
        requested_command_id=requested_command_id,
    )
    validate_field_tool_use_record(record)
    return record


def validate_field_tool_use_record(record: Mapping[str, object]) -> None:
    if record.get("schema") != FIELD_TOOL_USE_SCHEMA:
        raise ValueError("field tool use schema is required")
    _reject_authority(record, "field tool use record")
    for key in ("tool_use_id", "case_id", "requested_command_id", "status", "source_record_ids"):
        _require(record, key)
    if record.get("status") not in ALLOWED_TOOL_USE_STATUS:
        raise ValueError("unsupported tool use status")
    if record.get("rejection_reason") not in ALLOWED_REJECTION_REASONS:
        raise ValueError("unsupported rejection reason")
    if record.get("status") == "accepted":
        if record.get("rejection_reason"):
            raise ValueError("accepted tool use cannot include rejection_reason")
        if not record.get("tool_id") or not record.get("tool_kind"):
            raise ValueError("accepted tool use requires tool_id and tool_kind")
        if not record.get("source_command_ids"):
            raise ValueError("accepted tool use requires source_command_ids")
        if _as_float(record.get("energy_after")) > _as_float(record.get("energy_before")):
            raise ValueError("accepted tool use cannot increase energy")
    else:
        if not record.get("rejection_reason"):
            raise ValueError("rejected tool use requires rejection_reason")
        if record.get("source_command_ids"):
            raise ValueError("rejected tool use cannot include source_command_ids")
        if _as_float(record.get("energy_after")) != _as_float(record.get("energy_before")):
            raise ValueError("rejected tool use cannot change energy")
        if _as_float(record.get("risk_after")) != _as_float(record.get("risk_before")):
            raise ValueError("rejected tool use cannot change risk")


def build_field_play_feedback(
    *,
    feedback_id: str,
    case_id: str,
    tick: int,
    kind: str,
    status: str,
    score_delta: float,
    risk_delta: float,
    unlocked_tool_ids: Sequence[str],
    source_tool_use_ids: Sequence[str],
    source_consequence_ids: Sequence[str],
    source_projection_frame_ids: Sequence[str],
    source_spectral_camera_frame_ids: Sequence[str],
    source_spectral_image_plane_digests: Sequence[str],
    baseline_case_id: str,
    metrics: Mapping[str, object],
    source_record_ids: Sequence[str],
) -> dict[str, object]:
    feedback = {
        "schema": FIELD_PLAY_FEEDBACK_SCHEMA,
        "feedback_id": str(feedback_id),
        "case_id": str(case_id),
        "tick": int(tick),
        "kind": str(kind),
        "status": str(status),
        "score_delta": _round(score_delta),
        "risk_delta": _round(risk_delta),
        "unlocked_tool_ids": _unique(unlocked_tool_ids),
        "source_tool_use_ids": _unique(source_tool_use_ids),
        "source_consequence_ids": _unique(source_consequence_ids),
        "source_projection_frame_ids": _unique(source_projection_frame_ids),
        "source_spectral_camera_frame_ids": _unique(source_spectral_camera_frame_ids),
        "source_spectral_image_plane_digests": _unique(source_spectral_image_plane_digests),
        "baseline_case_id": str(baseline_case_id),
        "metrics": dict(metrics),
        "source_record_ids": _unique(source_record_ids),
        "is_authority_state": False,
    }
    validate_field_play_feedback(feedback)
    return feedback


def validate_field_play_feedback(feedback: Mapping[str, object]) -> None:
    if feedback.get("schema") != FIELD_PLAY_FEEDBACK_SCHEMA:
        raise ValueError("field play feedback schema is required")
    _reject_authority(feedback, "field play feedback")
    for key in ("feedback_id", "case_id", "kind", "status", "source_tool_use_ids", "source_record_ids"):
        _require(feedback, key)
    if feedback.get("kind") not in ALLOWED_FEEDBACK_KINDS:
        raise ValueError("unsupported feedback kind")
    if feedback.get("status") not in ALLOWED_TOOL_USE_STATUS:
        raise ValueError("unsupported feedback status")
    if not isinstance(feedback.get("metrics"), Mapping):
        raise ValueError("metrics must be a mapping")

    if feedback.get("kind") == "blocked":
        metrics = feedback["metrics"]
        assert isinstance(metrics, Mapping)
        if metrics.get("rejection_reason") not in ALLOWED_REJECTION_REASONS - {""}:
            raise ValueError("blocked feedback requires valid rejection_reason")
        if _as_float(feedback.get("score_delta")) != 0.0 or _as_float(feedback.get("risk_delta")) != 0.0:
            raise ValueError("blocked feedback must have zero deltas")
        if feedback.get("unlocked_tool_ids"):
            raise ValueError("blocked feedback cannot unlock tools")
        for key in (
            "source_consequence_ids",
            "source_projection_frame_ids",
            "source_spectral_camera_frame_ids",
            "source_spectral_image_plane_digests",
        ):
            if feedback.get(key):
                raise ValueError("blocked feedback cannot carry field evidence")
        return

    if feedback.get("status") == "accepted":
        for key in (
            "source_consequence_ids",
            "source_projection_frame_ids",
            "source_spectral_camera_frame_ids",
            "source_spectral_image_plane_digests",
            "baseline_case_id",
        ):
            _require(feedback, key)


def _profiles_by_id(tool_profiles: Sequence[Mapping[str, object]]) -> dict[str, Mapping[str, object]]:
    result: dict[str, Mapping[str, object]] = {}
    for profile in tool_profiles:
        validate_field_tool_profile(profile)
        result[str(profile["tool_id"])] = profile
    return result


def _state_from_values(
    *,
    case_id: str,
    tick: int,
    tool_energy: float,
    risk_level: float,
    score: float,
    cooldowns: Mapping[str, int],
    unlocked_tool_ids: Sequence[str],
    accepted_tool_use_ids: Sequence[str],
    rejected_tool_use_ids: Sequence[str],
    feedback_ids: Sequence[str],
    source_record_ids: Sequence[str],
) -> dict[str, object]:
    state = {
        "schema": FIELD_PLAY_LOOP_STATE_SCHEMA,
        "loop_state_id": f"field-play-loop-state::{case_id}::{tick}",
        "case_id": str(case_id),
        "tick": int(tick),
        "tool_energy": _round(max(0.0, tool_energy)),
        "risk_level": _round(min(1.0, max(0.0, risk_level))),
        "score": _round(score),
        "cooldowns": _cooldowns(cooldowns),
        "unlocked_tool_ids": _unique(unlocked_tool_ids),
        "accepted_tool_use_ids": _unique(accepted_tool_use_ids),
        "rejected_tool_use_ids": _unique(rejected_tool_use_ids),
        "feedback_ids": _unique(feedback_ids),
        "source_record_ids": _unique(source_record_ids),
        "is_authority_state": False,
    }
    validate_field_play_loop_state(state)
    return state


def replay_field_play_loop_state(
    *,
    case_id: str,
    tick: int,
    initial_state: Mapping[str, object],
    tool_profiles: Sequence[Mapping[str, object]],
    tool_use_records: Sequence[Mapping[str, object]],
    feedback_records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    validate_field_play_initial_state(initial_state)
    profiles = _profiles_by_id(tool_profiles)
    tool_energy = _as_float(initial_state.get("tool_energy"))
    risk_level = _as_float(initial_state.get("risk_level"))
    score = _as_float(initial_state.get("score"))
    cooldowns = _cooldowns(initial_state.get("cooldowns"))
    unlocked_tool_ids = _as_list(initial_state.get("unlocked_tool_ids"))
    accepted_tool_use_ids: list[str] = []
    rejected_tool_use_ids: list[str] = []
    feedback_ids: list[str] = []
    source_record_ids: list[str] = _as_list(initial_state.get("source_record_ids"))
    current_state: Mapping[str, object] = initial_state
    events: list[tuple[int, int, str, Mapping[str, object]]] = []
    for record in tool_use_records:
        events.append((_as_int(record.get("tick")), 0, str(record.get("tool_use_id", "")), record))
    for feedback in feedback_records:
        events.append((_as_int(feedback.get("tick")), 1, str(feedback.get("feedback_id", "")), feedback))

    for event_tick, event_priority, _event_id, item in sorted(events):
        if event_tick > int(tick):
            continue
        if event_priority == 0:
            record = item
            validate_field_tool_use_record(record)
            if str(record.get("case_id")) != str(case_id):
                raise ValueError("tool use case_id mismatch")
            profile = profiles.get(str(record.get("tool_id")))
            expected = _expected_tool_use(
                tool_use_id=str(record["tool_use_id"]),
                case_id=str(case_id),
                tick=_as_int(record["tick"]),
                profile=profile,
                prior_state=current_state,
                requested_command_id=str(record["requested_command_id"]),
            )
            for key in (
                "status",
                "rejection_reason",
                "energy_before",
                "energy_after",
                "risk_before",
                "risk_after",
                "cooldown_until_tick",
                "source_command_ids",
            ):
                if record.get(key) != expected.get(key):
                    raise ValueError(f"tool use replay mismatch: {key}")
            if record["status"] == "accepted":
                tool_energy = _as_float(record.get("energy_after"))
                risk_level = _as_float(record.get("risk_after"))
                cooldowns[str(record["tool_id"])] = _as_int(record.get("cooldown_until_tick"))
                accepted_tool_use_ids.append(str(record["tool_use_id"]))
            else:
                rejected_tool_use_ids.append(str(record["tool_use_id"]))
            source_record_ids.extend(_as_list(record.get("source_record_ids")))
        else:
            feedback = item
            validate_field_play_feedback(feedback)
            if str(feedback.get("case_id")) != str(case_id):
                raise ValueError("feedback case_id mismatch")
            known_tool_use_ids = set(accepted_tool_use_ids) | set(rejected_tool_use_ids)
            missing_tool_uses = set(_as_list(feedback.get("source_tool_use_ids"))) - known_tool_use_ids
            if missing_tool_uses:
                raise ValueError("feedback references unknown tool use")
            if feedback.get("kind") != "blocked":
                score += _as_float(feedback.get("score_delta"))
                risk_level += _as_float(feedback.get("risk_delta"))
                unlocked_tool_ids.extend(_as_list(feedback.get("unlocked_tool_ids")))
            feedback_ids.append(str(feedback["feedback_id"]))
            source_record_ids.extend(_as_list(feedback.get("source_record_ids")))

        current_state = _state_from_values(
            case_id=case_id,
            tick=event_tick,
            tool_energy=tool_energy,
            risk_level=risk_level,
            score=score,
            cooldowns=cooldowns,
            unlocked_tool_ids=unlocked_tool_ids,
            accepted_tool_use_ids=accepted_tool_use_ids,
            rejected_tool_use_ids=rejected_tool_use_ids,
            feedback_ids=feedback_ids,
            source_record_ids=source_record_ids,
        )

    return _state_from_values(
        case_id=case_id,
        tick=tick,
        tool_energy=tool_energy,
        risk_level=risk_level,
        score=score,
        cooldowns=cooldowns,
        unlocked_tool_ids=unlocked_tool_ids,
        accepted_tool_use_ids=accepted_tool_use_ids,
        rejected_tool_use_ids=rejected_tool_use_ids,
        feedback_ids=feedback_ids,
        source_record_ids=source_record_ids,
    )


def validate_field_play_loop_state(state: Mapping[str, object]) -> None:
    if state.get("schema") != FIELD_PLAY_LOOP_STATE_SCHEMA:
        raise ValueError("field play loop state schema is required")
    _reject_authority(state, "field play loop state")
    for key in ("loop_state_id", "case_id", "source_record_ids"):
        _require(state, key)
    if _as_int(state.get("tick"), -1) < 0:
        raise ValueError("tick must be non-negative")
    for key in ("tool_energy", "risk_level", "score"):
        if key not in state:
            raise ValueError(f"{key} is required")
    for key in ("cooldowns",):
        if not isinstance(state.get(key), Mapping):
            raise ValueError(f"{key} must be a mapping")
    for key in ("unlocked_tool_ids", "accepted_tool_use_ids", "rejected_tool_use_ids", "feedback_ids"):
        if not isinstance(state.get(key), list):
            raise ValueError(f"{key} must be a list")
