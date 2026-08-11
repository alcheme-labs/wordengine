from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping, Sequence


DEFAULT_ARTIFACT_BUDGET_BYTES = 40_000_000
DEFAULT_MIN_READBACK_DIVERGENCE = 1e-5
DEFAULT_MIN_DIRECTIONAL_ALIGNMENT = 0.55
DEFAULT_MIN_QUALITY_IMPROVEMENT = 0.01
DEFAULT_ENERGY_RUNAWAY_RATIO_MAX = 2.5
DEFAULT_ENERGY_RUNAWAY_ABS_MAX = 12.0
COUNTERFACTUAL_RELAXATION_TICKS = 8
COUNTERFACTUAL_EPSILON = 1e-12
COUNTERFACTUAL_PERTURBATION_STABILITY_SCHEMA = (
    "five_phase_counterfactual_perturbation_stability_evidence_v1"
)
PHASE_NAMES = ("contractive", "generative", "radiant", "substrate", "transport")


def jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(jsonable(value), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def canonical_json_bytes(value: Any) -> int:
    return len(json.dumps(jsonable(value), sort_keys=True, separators=(",", ":")).encode("utf-8"))


def merge_projection(projections: Sequence[Mapping[str, Mapping[str, float]]]) -> dict[str, dict[str, float]]:
    merged: dict[str, dict[str, float]] = {}
    for projection in projections:
        for basis_id, channels in (projection or {}).items():
            merged.setdefault(str(basis_id), {})
            for channel, value in channels.items():
                merged[str(basis_id)][str(channel)] = merged[str(basis_id)].get(str(channel), 0.0) + float(value)
    return merged


def build_perturbation_schedule(*, run_id: str, ticks: int) -> dict[str, Any]:
    apply_ticks = sorted({2, max(3, int(ticks) // 3), max(4, (int(ticks) * 2) // 3)})
    events = []
    tools = ["implicit_local_excite", "implicit_directional_push", "implicit_local_dampen"]
    points = [[0.35, 0.42], [0.55, 0.50], [0.45, 0.58]]
    for index, tick in enumerate(apply_ticks):
        if tick > int(ticks):
            continue
        event = {
            "schema": "five_phase_perturbation_event_v1",
            "event_id": f"five-phase-perturbation::{run_id}::{index}",
            "apply_tick": int(tick),
            "tool": tools[index % len(tools)],
            "source_image_xy": points[index % len(points)],
            "radius_world": 0.75,
            "amplitude": 0.22 if index != 2 else 0.16,
            "duration_ticks": 2,
            "source_vector_image": [1.0, 0.15],
            "is_authority_state": False,
        }
        event["source_record_ids"] = [event["event_id"]]
        events.append(event)
    schedule = {
        "schema": "five_phase_perturbation_schedule_v1",
        "schedule_id": f"five-phase-perturbation-schedule::{run_id}",
        "run_id": str(run_id),
        "ticks": int(ticks),
        "events": events,
        "source_record_ids": [event["event_id"] for event in events],
        "is_authority_state": False,
    }
    schedule["schedule_digest"] = canonical_digest(schedule)
    return schedule


def build_causal_run_manifest(
    *,
    run_id: str,
    branch_name: str,
    source_package_name: str,
    source_package_digest: str,
    ticks: int,
    feedback_enabled: bool,
    initial_snapshot_digest: str,
    perturbation_schedule_digest: str,
    export_digest: str,
    artifact_bytes: int,
    artifact_budget_bytes: int = DEFAULT_ARTIFACT_BUDGET_BYTES,
    residual_distance_mean: float = 0.0,
    pattern_stability_mean: float = 0.0,
) -> dict[str, Any]:
    manifest = {
        "schema": "five_phase_causal_run_manifest_v1",
        "run_id": str(run_id),
        "branch_name": str(branch_name),
        "source_package_name": str(source_package_name),
        "source_package_digest": str(source_package_digest),
        "ticks": int(ticks),
        "feedback_enabled": bool(feedback_enabled),
        "initial_snapshot_digest": str(initial_snapshot_digest),
        "perturbation_schedule_digest": str(perturbation_schedule_digest),
        "export_digest": str(export_digest),
        "artifact_bytes": int(artifact_bytes),
        "artifact_budget_bytes": int(artifact_budget_bytes),
        "residual_distance_mean": float(residual_distance_mean),
        "pattern_stability_mean": float(pattern_stability_mean),
        "source_record_ids": [str(initial_snapshot_digest), str(perturbation_schedule_digest), str(export_digest)],
        "is_authority_state": False,
    }
    manifest["manifest_digest"] = canonical_digest(manifest)
    return manifest


def coefficient_vector(state: Mapping[str, Any]) -> dict[tuple[str, str], float]:
    vector: dict[tuple[str, str], float] = {}
    for basis_id, channels in (state.get("basis_coefficients") or {}).items():
        for channel, value in (channels or {}).items():
            vector[(str(basis_id), str(channel))] = float(value)
    return vector


def projection_vector(projection: Mapping[str, Mapping[str, float]]) -> dict[tuple[str, str], float]:
    vector: dict[tuple[str, str], float] = {}
    for basis_id, channels in (projection or {}).items():
        for channel, value in (channels or {}).items():
            vector[(str(basis_id), str(channel))] = float(value)
    return vector


def subtract_vectors(left: Mapping[tuple[str, str], float], right: Mapping[tuple[str, str], float]) -> dict[tuple[str, str], float]:
    keys = set(left) | set(right)
    return {key: float(left.get(key, 0.0)) - float(right.get(key, 0.0)) for key in keys}


def vector_norm(vector: Mapping[tuple[str, str], float]) -> float:
    return math.sqrt(sum(float(value) * float(value) for value in vector.values()))


def vector_cosine(left: Mapping[tuple[str, str], float], right: Mapping[tuple[str, str], float]) -> float:
    left_norm = vector_norm(left)
    right_norm = vector_norm(right)
    if left_norm <= 1e-12 or right_norm <= 1e-12:
        return 0.0
    keys = set(left) | set(right)
    dot = sum(float(left.get(key, 0.0)) * float(right.get(key, 0.0)) for key in keys)
    return max(-1.0, min(1.0, dot / (left_norm * right_norm)))


def sequence_norm(vector: Sequence[float]) -> float:
    return math.sqrt(sum(float(value) * float(value) for value in vector))


def sequence_distance(left: Sequence[float], right: Sequence[float]) -> float:
    length = min(len(left), len(right))
    if length <= 0:
        return 0.0
    return math.sqrt(sum((float(left[index]) - float(right[index])) ** 2 for index in range(length)))


def sequence_cosine(left: Sequence[float], right: Sequence[float]) -> float:
    length = min(len(left), len(right))
    if length <= 0:
        return 0.0
    left_values = [float(left[index]) for index in range(length)]
    right_values = [float(right[index]) for index in range(length)]
    left_norm = sequence_norm(left_values)
    right_norm = sequence_norm(right_values)
    if left_norm <= 1e-12 or right_norm <= 1e-12:
        return 0.0
    dot = sum(left_values[index] * right_values[index] for index in range(length))
    return max(-1.0, min(1.0, dot / (left_norm * right_norm)))


def live_field_vector(field_state: Mapping[str, Any]) -> list[float]:
    vector: list[float] = []
    for channel_name in sorted((field_state.get("channels") or {})):
        grid = (field_state.get("channels") or {}).get(channel_name) or []
        for row in grid:
            vector.extend(float(value) for value in row)
    return vector


def phase_vector(record: Mapping[str, Any]) -> list[float]:
    values = record.get("aggregate_phase") or record.get("phase_bias") or {}
    return [float(values.get(name, 0.0)) for name in PHASE_NAMES]


def _implicit_tick_from_live_field(field_state: Mapping[str, Any]) -> int:
    source_ticks = field_state.get("source_state_ticks") or []
    if source_ticks:
        return int(source_ticks[0])
    return int(field_state.get("tick", 0))


def live_fields_by_implicit_tick(exported: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for record in exported.get("five_phase_live_field_states", []) or []:
        if not isinstance(record, Mapping):
            continue
        result[_implicit_tick_from_live_field(record)] = dict(record)
    return result


def phase_fields_by_implicit_tick(exported: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    live_fields = {
        str(record.get("field_state_id")): record
        for record in exported.get("five_phase_live_field_states", []) or []
        if isinstance(record, Mapping)
    }
    result: dict[int, dict[str, Any]] = {}
    for record in exported.get("five_phase_phase_fields", []) or []:
        if not isinstance(record, Mapping):
            continue
        live_field_id = next(
            (
                str(source_id)
                for source_id in record.get("source_record_ids", []) or []
                if str(source_id).startswith("five-phase-live-field-state::")
            ),
            "",
        )
        live_field = live_fields.get(live_field_id)
        if live_field:
            result[_implicit_tick_from_live_field(live_field)] = dict(record)
    return result


def _feedback_phase_bias_for_application(
    application: Mapping[str, Any],
    exported: Mapping[str, Any],
    *,
    max_source_steps: int = 3,
) -> list[float]:
    live_steps = {
        str(record.get("live_step_id")): record
        for record in exported.get("five_phase_live_steps", []) or []
        if isinstance(record, Mapping)
    }
    feedback_records = {
        str(record.get("record_id")): record
        for record in exported.get("five_phase_feedback_records", []) or []
        if isinstance(record, Mapping)
    }
    bias = [0.0 for _ in PHASE_NAMES]
    for live_step_id in list(application.get("five_phase_live_step_ids", []) or [])[-max_source_steps:]:
        live_step = live_steps.get(str(live_step_id))
        if not live_step:
            continue
        for feedback_id in live_step.get("feedback_record_ids", []) or []:
            feedback = feedback_records.get(str(feedback_id))
            if not feedback:
                continue
            feedback_bias = phase_vector({"phase_bias": feedback.get("phase_bias") or {}})
            bias = [bias[index] + feedback_bias[index] for index in range(len(PHASE_NAMES))]
    return bias


def mean_feedback_distance(exported: Mapping[str, Any], *, last_window: int = 16) -> float:
    values = [
        float(record.get("phase_l2_distance_before", 0.0))
        for record in exported.get("five_phase_feedback_records", []) or []
        if isinstance(record, Mapping)
    ]
    if not values:
        return 0.0
    window = values[-max(1, min(int(last_window), len(values))) :]
    return sum(window) / len(window)


def mean_pattern_stability(exported: Mapping[str, Any], *, last_window: int = 16) -> float:
    values = [
        float(record.get("stability_score", 0.0))
        for record in exported.get("five_phase_patterns", []) or []
        if isinstance(record, Mapping)
    ]
    if not values:
        return 0.0
    window = values[-max(1, min(int(last_window), len(values))) :]
    return sum(window) / len(window)


def state_energy(state: Mapping[str, Any]) -> float:
    summary = state.get("energy_summary") or {}
    if "total_abs_coefficient" in summary:
        return float(summary["total_abs_coefficient"])
    return sum(abs(value) for value in coefficient_vector(state).values())


def states_by_tick(exported: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for state in exported.get("implicit_field_states", []) or []:
        if not isinstance(state, Mapping):
            continue
        result[int(state.get("tick", 0))] = dict(state)
    return result


def steps_by_tick(exported: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for step in exported.get("implicit_live_step_records", []) or []:
        if not isinstance(step, Mapping):
            continue
        result[int(step.get("tick", 0))] = dict(step)
    return result


def applications_by_tick(exported: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for record in exported.get("five_phase_feedback_applications", []) or []:
        if not isinstance(record, Mapping):
            continue
        result[int(record.get("tick", 0))] = dict(record)
    return result



def _counterfactual_records(values: Any, *, label: str) -> list[dict[str, Any]]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise ValueError(f"{label} must be a sequence")
    records: list[dict[str, Any]] = []
    for value in values:
        converted = jsonable(value)
        if not isinstance(converted, Mapping):
            raise ValueError(f"{label} must contain mappings")
        records.append(dict(converted))
    return records


def _counterfactual_branch_evidence(
    exported: Mapping[str, Any],
    *,
    branch_label: str,
) -> dict[str, Any]:
    session = jsonable(exported.get("session") or {})
    if not isinstance(session, Mapping):
        raise ValueError(f"{branch_label} counterfactual session must be a mapping")
    states = _counterfactual_records(
        exported.get("implicit_field_states", []),
        label=f"{branch_label} counterfactual states",
    )
    steps = _counterfactual_records(
        exported.get("implicit_live_step_records", []),
        label=f"{branch_label} counterfactual steps",
    )
    return {
        "branch_label": str(branch_label),
        "session": dict(session),
        "state_tick_id_sequence": [
            {
                "tick": int(state.get("tick", -1)),
                "state_id": str(state.get("implicit_field_state_id", "")),
            }
            for state in states
        ],
        "step_tick_id_sequence": [
            {
                "tick": int(step.get("tick", -1)),
                "step_id": str(step.get("step_id", "")),
                "previous_state_id": str(step.get("previous_state_id", "")),
                "result_state_id": str(step.get("result_state_id", "")),
            }
            for step in steps
        ],
        "implicit_field_states": states,
        "implicit_live_steps": steps,
        "interaction_audits": _counterfactual_records(
            exported.get("implicit_interaction_audits", []),
            label=f"{branch_label} counterfactual audits",
        ),
        "interaction_transcript": _counterfactual_records(
            exported.get("implicit_interaction_transcript", []),
            label=f"{branch_label} counterfactual transcript",
        ),
        "five_phase_patterns": _counterfactual_records(
            exported.get("five_phase_patterns", []),
            label=f"{branch_label} counterfactual Patterns",
        ),
    }


def _counterfactual_tick_map(
    records: Sequence[Mapping[str, Any]],
    *,
    label: str,
    failures: list[str],
) -> dict[int, Mapping[str, Any]]:
    ticks = [int(record.get("tick", -1)) for record in records]
    if len(ticks) != len(set(ticks)):
        failures.append(f"counterfactual {label} ticks must be unique")
        return {}
    return {tick: record for tick, record in zip(ticks, records)}


def _counterfactual_density_norm(
    projection: Mapping[str, Mapping[str, Any]],
    *,
    kappa_by_basis: Mapping[str, float],
    density_weight_by_basis: Mapping[str, float],
) -> float:
    terms = []
    for basis_id, kappa in kappa_by_basis.items():
        coefficient = float((projection.get(str(basis_id)) or {}).get("density", 0.0))
        term = float(kappa) * (float(density_weight_by_basis[str(basis_id)]) * coefficient) ** 2
        if not math.isfinite(term) or term < 0.0:
            raise ValueError("counterfactual kappa norm requires finite non-negative terms")
        terms.append(term)
    return math.sqrt(math.fsum(terms))


def _counterfactual_recompute(
    evidence: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    try:
        configuration = evidence.get("trusted_configuration") or {}
        if not isinstance(configuration, Mapping):
            raise ValueError("trusted configuration must be a mapping")
        if str(evidence.get("trusted_configuration_digest", "")) != canonical_digest(configuration):
            failures.append("counterfactual trusted configuration digest mismatch")
        if not str(evidence.get("trusted_initial_snapshot_digest", "")):
            failures.append("counterfactual trusted S0 digest is missing")

        basis_records = _counterfactual_records(
            evidence.get("implicit_basis_records", []),
            label="counterfactual basis records",
        )
        basis_ids = [str(basis.get("basis_id", "")) for basis in basis_records]
        if any(not basis_id for basis_id in basis_ids) or len(basis_ids) != len(set(basis_ids)):
            raise ValueError("counterfactual basis IDs must be unique and non-empty")
        density_weights = {
            str(basis["basis_id"]): float((basis.get("channel_weights") or {}).get("density", 0.0))
            for basis in basis_records
        }
        if any(not math.isfinite(value) for value in density_weights.values()):
            raise ValueError("counterfactual density basis weights must be finite")

        branch_data: dict[str, dict[str, Any]] = {}
        for branch_name in ("control", "zero"):
            branch = evidence.get(f"{branch_name}_branch") or {}
            if not isinstance(branch, Mapping):
                raise ValueError(f"counterfactual {branch_name} branch must be a mapping")
            session = branch.get("session") or {}
            states = _counterfactual_records(
                branch.get("implicit_field_states", []),
                label=f"counterfactual {branch_name} states",
            )
            steps = _counterfactual_records(
                branch.get("implicit_live_steps", []),
                label=f"counterfactual {branch_name} steps",
            )
            audits = _counterfactual_records(
                branch.get("interaction_audits", []),
                label=f"counterfactual {branch_name} audits",
            )
            transcript = _counterfactual_records(
                branch.get("interaction_transcript", []),
                label=f"counterfactual {branch_name} transcript",
            )
            patterns = _counterfactual_records(
                branch.get("five_phase_patterns", []),
                label=f"counterfactual {branch_name} Patterns",
            )
            state_map = _counterfactual_tick_map(
                states,
                label=f"{branch_name} state",
                failures=failures,
            )
            step_map = _counterfactual_tick_map(
                steps,
                label=f"{branch_name} step",
                failures=failures,
            )
            state_sequence = [
                {
                    "tick": int(state.get("tick", -1)),
                    "state_id": str(state.get("implicit_field_state_id", "")),
                }
                for state in states
            ]
            step_sequence = [
                {
                    "tick": int(step.get("tick", -1)),
                    "step_id": str(step.get("step_id", "")),
                    "previous_state_id": str(step.get("previous_state_id", "")),
                    "result_state_id": str(step.get("result_state_id", "")),
                }
                for step in steps
            ]
            if jsonable(branch.get("state_tick_id_sequence")) != state_sequence:
                failures.append(f"counterfactual {branch_name} state sequence projection mismatch")
            if jsonable(branch.get("step_tick_id_sequence")) != step_sequence:
                failures.append(f"counterfactual {branch_name} step sequence projection mismatch")
            state_ids = [item["state_id"] for item in state_sequence]
            step_ids = [item["step_id"] for item in step_sequence]
            pattern_ids = [str(pattern.get("record_id", "")) for pattern in patterns]
            if any(not value for value in state_ids) or len(state_ids) != len(set(state_ids)):
                failures.append(
                    f"counterfactual {branch_name} state IDs must be unique and non-empty"
                )
            if any(not value for value in step_ids) or len(step_ids) != len(set(step_ids)):
                failures.append(
                    f"counterfactual {branch_name} step IDs must be unique and non-empty"
                )
            if any(not value for value in pattern_ids) or len(pattern_ids) != len(set(pattern_ids)):
                failures.append(
                    f"counterfactual {branch_name} Pattern instances must be unique"
                )
            if session.get("five_phase_feedback_enabled") is not False:
                failures.append(f"counterfactual {branch_name} branch must disable Feedback")
            branch_data[branch_name] = {
                "branch": branch,
                "session": session,
                "states": states,
                "steps": steps,
                "audits": audits,
                "transcript": transcript,
                "patterns": patterns,
                "state_map": state_map,
                "step_map": step_map,
                "state_sequence": state_sequence,
                "step_sequence": step_sequence,
            }

        if failures and (
            not branch_data["control"]["state_map"]
            or not branch_data["zero"]["state_map"]
            or not branch_data["control"]["step_map"]
            or not branch_data["zero"]["step_map"]
        ):
            return {}, failures

        identity_fields = ("session_id", "run_id", "source_package_name", "source_package_digest")
        control_identity = {
            field: branch_data["control"]["session"].get(field) for field in identity_fields
        }
        zero_identity = {
            field: branch_data["zero"]["session"].get(field) for field in identity_fields
        }
        trusted_identity = {field: configuration.get(field) for field in identity_fields}
        if control_identity != zero_identity or control_identity != trusted_identity:
            failures.append(
                "counterfactual branches do not preserve trusted session/run/source identity"
            )

        control_states = branch_data["control"]["states"]
        zero_states = branch_data["zero"]["states"]
        control_steps = branch_data["control"]["steps"]
        zero_steps = branch_data["zero"]["steps"]
        if not control_states or not zero_states:
            raise ValueError("counterfactual branches require states")
        if canonical_digest(control_states[0]) != canonical_digest(zero_states[0]):
            failures.append("counterfactual branches do not share identical S0 state")
        if (
            str(control_states[0].get("implicit_field_state_id", ""))
            != str(evidence.get("trusted_initial_state_id", ""))
            or str(control_states[0].get("state_digest", ""))
            != str(evidence.get("trusted_initial_state_digest", ""))
        ):
            failures.append("counterfactual branch initial state does not match trusted S0 lineage")
        if branch_data["control"]["state_sequence"] != branch_data["zero"]["state_sequence"]:
            failures.append("counterfactual branch state tick/ID sequences differ")
        if branch_data["control"]["step_sequence"] != branch_data["zero"]["step_sequence"]:
            failures.append("counterfactual branch step tick/ID sequences differ")

        for branch_name in ("control", "zero"):
            states = branch_data[branch_name]["states"]
            steps = branch_data[branch_name]["steps"]
            if len(steps) != len(states) - 1:
                failures.append(
                    f"counterfactual {branch_name} branch requires a complete state/step chain"
                )
            for previous_state, result_state, step in zip(states, states[1:], steps):
                if (
                    str(step.get("previous_state_id", ""))
                    != str(previous_state.get("implicit_field_state_id", ""))
                    or str(step.get("result_state_id", ""))
                    != str(result_state.get("implicit_field_state_id", ""))
                    or str(step.get("previous_state_digest", ""))
                    != str(previous_state.get("state_digest", ""))
                    or str(step.get("result_state_digest", ""))
                    != str(result_state.get("state_digest", ""))
                    or int(step.get("tick", -1)) != int(result_state.get("tick", -2))
                ):
                    failures.append(
                        f"counterfactual {branch_name} state/step chain mismatch"
                    )
                    break
                if (
                    step.get("five_phase_feedback_enabled") is not False
                    or step.get("five_phase_feedback_applied") is not False
                    or step.get("realized_five_phase_feedback_input_projection")
                ):
                    failures.append(f"counterfactual {branch_name} step leaked Feedback")
                    break

        control_transcript = branch_data["control"]["transcript"]
        zero_transcript = branch_data["zero"]["transcript"]
        control_audits = branch_data["control"]["audits"]
        zero_audits = branch_data["zero"]["audits"]
        if (
            len(control_transcript) != 1
            or len(zero_transcript) != 1
            or len(control_audits) != 1
            or len(zero_audits) != 1
        ):
            raise ValueError(
                "counterfactual branches require exactly one transcript entry and audit"
            )
        control_entry = control_transcript[0]
        zero_entry = zero_transcript[0]
        control_request = control_entry.get("request") or {}
        zero_request = zero_entry.get("request") or {}
        if not isinstance(control_request, Mapping) or not isinstance(zero_request, Mapping):
            raise ValueError("counterfactual transcript requests must be mappings")
        control_entry_lineage = dict(control_entry)
        zero_entry_lineage = dict(zero_entry)
        control_entry_lineage.pop("request", None)
        zero_entry_lineage.pop("request", None)
        if canonical_digest(control_entry_lineage) != canonical_digest(zero_entry_lineage):
            failures.append(
                "counterfactual transcript lineage differs outside request amplitude"
            )
        request_difference_fields = sorted(
            field
            for field in set(control_request) | set(zero_request)
            if jsonable(control_request.get(field)) != jsonable(zero_request.get(field))
        )
        if request_difference_fields != ["amplitude"]:
            failures.append(
                "counterfactual transcript requests may differ only by amplitude"
            )
        control_amplitude = float(control_request.get("amplitude", 0.0))
        zero_amplitude = float(zero_request.get("amplitude", 0.0))
        if abs(control_amplitude) <= COUNTERFACTUAL_EPSILON:
            failures.append("counterfactual control amplitude must be non-zero")
        if abs(zero_amplitude) > COUNTERFACTUAL_EPSILON:
            failures.append("counterfactual zero amplitude must be zero")

        control_audit = control_audits[0]
        zero_audit = zero_audits[0]
        if (
            str(control_entry.get("audit_id", "")) != str(control_audit.get("audit_id", ""))
            or str(zero_entry.get("audit_id", "")) != str(zero_audit.get("audit_id", ""))
        ):
            failures.append("counterfactual transcript/audit lineage mismatch")
        control_scope_kappa = {
            str(basis_id): float(value)
            for basis_id, value in (control_audit.get("kappa_by_basis") or {}).items()
        }
        zero_scope_kappa = {
            str(basis_id): float(value)
            for basis_id, value in (zero_audit.get("kappa_by_basis") or {}).items()
        }
        if (
            not control_scope_kappa
            or control_scope_kappa != zero_scope_kappa
            or any(
                basis_id not in density_weights or not math.isfinite(value) or value < 0.0
                for basis_id, value in control_scope_kappa.items()
            )
            or not any(value > 0.0 for value in control_scope_kappa.values())
        ):
            failures.append(
                "counterfactual branches require one identical valid local-control kappa"
            )
        control_applications = _counterfactual_records(
            control_audit.get("applications", []),
            label="counterfactual control applications",
        )
        zero_applications = _counterfactual_records(
            zero_audit.get("applications", []),
            label="counterfactual zero applications",
        )
        if (
            list(control_audit.get("schedule_weights") or [])
            != list(zero_audit.get("schedule_weights") or [])
            or len(list(control_audit.get("schedule_weights") or [])) != 1
            or len(control_applications) != 1
            or len(zero_applications) != 1
        ):
            failures.append(
                "counterfactual pair must record the same single-tick control schedule"
            )
        input_tick = int(control_audit.get("start_tick", -1))
        if (
            input_tick != int(zero_audit.get("start_tick", -2))
            or int(control_applications[0].get("tick", -1)) != input_tick
            or int(zero_applications[0].get("tick", -2)) != input_tick
        ):
            failures.append("counterfactual application tick does not equal t_off")
        t_off = input_tick
        relaxation_tick = t_off + COUNTERFACTUAL_RELAXATION_TICKS
        initial_tick = int(control_states[0].get("tick", -1))
        expected_state_ticks = list(range(initial_tick, relaxation_tick + 1))
        expected_step_ticks = list(range(initial_tick + 1, relaxation_tick + 1))
        if t_off != initial_tick + 1:
            failures.append(
                "counterfactual pair must apply exactly one input tick after S0"
            )
        for branch_name in ("control", "zero"):
            state_ticks = [
                int(state.get("tick", -1)) for state in branch_data[branch_name]["states"]
            ]
            step_ticks = [
                int(step.get("tick", -1)) for step in branch_data[branch_name]["steps"]
            ]
            if state_ticks != expected_state_ticks or step_ticks != expected_step_ticks:
                failures.append(
                    "counterfactual state sequence is missing the fixed t_off+8 horizon"
                )
                return {}, failures

        control_state_at_off = branch_data["control"]["state_map"][t_off]
        zero_state_at_off = branch_data["zero"]["state_map"][t_off]
        control_pattern_candidates = [
            pattern
            for pattern in branch_data["control"]["patterns"]
            if str((pattern.get("payload") or {}).get("source_implicit_field_state_id", ""))
            == str(control_state_at_off.get("implicit_field_state_id", ""))
            and (pattern.get("payload") or {}).get("episode_started") is True
            and float(
                (pattern.get("payload") or {}).get(
                    "realized_user_input_norm_kappa", 0.0
                )
            )
            > COUNTERFACTUAL_EPSILON
        ]
        if len(control_pattern_candidates) != 1:
            raise ValueError(
                "counterfactual control branch requires one Pattern episode started at t_off"
            )
        control_pattern = control_pattern_candidates[0]
        control_payload = control_pattern.get("payload") or {}
        pattern_identity_id = str(control_payload.get("pattern_identity_id", ""))
        zero_pattern_candidates = [
            pattern
            for pattern in branch_data["zero"]["patterns"]
            if str((pattern.get("payload") or {}).get("source_implicit_field_state_id", ""))
            == str(zero_state_at_off.get("implicit_field_state_id", ""))
            and str((pattern.get("payload") or {}).get("pattern_identity_id", ""))
            == pattern_identity_id
        ]
        if len(zero_pattern_candidates) != 1:
            raise ValueError(
                "counterfactual zero branch lacks the matching fixed-support Pattern identity"
            )
        zero_pattern = zero_pattern_candidates[0]
        zero_payload = zero_pattern.get("payload") or {}
        identity_kappa = {
            str(basis_id): float(value)
            for basis_id, value in (control_payload.get("identity_support_kappa") or {}).items()
        }
        identity_kappa_digest = str(
            control_payload.get("identity_support_kappa_digest", "")
        )
        if (
            not pattern_identity_id
            or set(identity_kappa) != set(basis_ids)
            or not any(value > 0.0 for value in identity_kappa.values())
            or any(not math.isfinite(value) or value < 0.0 for value in identity_kappa.values())
            or {
                str(basis_id): float(value)
                for basis_id, value in (zero_payload.get("identity_support_kappa") or {}).items()
            }
            != identity_kappa
            or identity_kappa_digest != canonical_digest(identity_kappa)
            or str(zero_payload.get("identity_support_kappa_digest", ""))
            != identity_kappa_digest
            or list(zero_payload.get("identity_support_bounds_grid") or [])
            != list(control_payload.get("identity_support_bounds_grid") or [])
            or list(zero_payload.get("identity_support_grid_shape") or [])
            != list(control_payload.get("identity_support_grid_shape") or [])
            or int(zero_pattern.get("tick", -1)) != int(control_pattern.get("tick", -2))
        ):
            failures.append(
                "counterfactual control/zero Patterns do not share one fixed identity support"
            )
        if (
            int(control_payload.get("episode_start_tick", -1)) != t_off
            or int(control_payload.get("last_user_input_tick", -1)) != t_off
            or int(control_payload.get("episode_end_tick", -1)) != relaxation_tick
            or str(control_payload.get("source_implicit_field_state_digest", ""))
            != str(control_state_at_off.get("state_digest", ""))
            or str(zero_payload.get("source_implicit_field_state_digest", ""))
            != str(zero_state_at_off.get("state_digest", ""))
        ):
            failures.append("counterfactual Pattern episode/state lineage mismatch")
        for branch_name in ("control", "zero"):
            for pattern in branch_data[branch_name]["patterns"]:
                payload = pattern.get("payload") or {}
                if (
                    str(payload.get("pattern_identity_id", "")) == pattern_identity_id
                    and (
                        {
                            str(basis_id): float(value)
                            for basis_id, value in (
                                payload.get("identity_support_kappa") or {}
                            ).items()
                        }
                        != identity_kappa
                        or str(payload.get("identity_support_kappa_digest", ""))
                        != identity_kappa_digest
                    )
                ):
                    failures.append(
                        f"counterfactual {branch_name} Pattern identity support changed"
                    )
                    break
        pattern_support = {
            "pattern_identity_id": pattern_identity_id,
            "control_episode_id": str(control_payload.get("episode_id", "")),
            "control_pattern_record_id": str(control_pattern.get("record_id", "")),
            "zero_pattern_record_id": str(zero_pattern.get("record_id", "")),
            "control_pattern_tick": int(control_pattern.get("tick", -1)),
            "zero_pattern_tick": int(zero_pattern.get("tick", -1)),
            "control_source_state_id": str(
                control_payload.get("source_implicit_field_state_id", "")
            ),
            "zero_source_state_id": str(
                zero_payload.get("source_implicit_field_state_id", "")
            ),
            "identity_support_bounds_grid": list(
                control_payload.get("identity_support_bounds_grid") or []
            ),
            "identity_support_grid_shape": list(
                control_payload.get("identity_support_grid_shape") or []
            ),
            "identity_support_kappa_digest": identity_kappa_digest,
        }

        scope_id = f"implicit-energy-scope::{control_audit.get('command_id', '')}"
        expected_scope_kappa = {
            basis_id: float(control_scope_kappa.get(basis_id, 0.0))
            for basis_id in basis_ids
        }
        for branch_name in ("control", "zero"):
            for tick in expected_step_ticks:
                step = branch_data[branch_name]["step_map"][tick]
                ledgers = [
                    ledger
                    for ledger in step.get("energy_ledgers", []) or []
                    if isinstance(ledger, Mapping)
                    and str(ledger.get("scope_id", "")) == scope_id
                ]
                if (
                    len(ledgers) != 1
                    or {
                        str(basis_id): float(value)
                        for basis_id, value in (ledgers[0].get("kappa") or {}).items()
                    }
                    != expected_scope_kappa
                ):
                    failures.append(
                        f"counterfactual {branch_name} local-scope ledger mismatch at tick {tick}"
                    )

        cumulative_dose = 0.0
        max_zero_user_norm = 0.0
        control_nonzero_user_ticks: list[int] = []
        susceptibility_values: list[float] = []
        deltas_through_off: list[float] = []
        measurements: list[dict[str, Any]] = []
        for tick in expected_state_ticks:
            control_state = branch_data["control"]["state_map"][tick]
            zero_state = branch_data["zero"]["state_map"][tick]
            difference = {
                basis_id: {
                    "density": float(
                        (control_state.get("basis_coefficients", {}).get(basis_id, {}) or {}).get(
                            "density", 0.0
                        )
                    )
                    - float(
                        (zero_state.get("basis_coefficients", {}).get(basis_id, {}) or {}).get(
                            "density", 0.0
                        )
                    )
                }
                for basis_id in identity_kappa
            }
            delta_kappa = _counterfactual_density_norm(
                difference,
                kappa_by_basis=identity_kappa,
                density_weight_by_basis=density_weights,
            )
            control_step = branch_data["control"]["step_map"].get(tick, {})
            zero_step = branch_data["zero"]["step_map"].get(tick, {})
            control_user_norm = _counterfactual_density_norm(
                control_step.get("realized_user_input_projection", {}) or {},
                kappa_by_basis=identity_kappa,
                density_weight_by_basis=density_weights,
            )
            zero_user_norm = _counterfactual_density_norm(
                zero_step.get("realized_user_input_projection", {}) or {},
                kappa_by_basis=identity_kappa,
                density_weight_by_basis=density_weights,
            )
            max_zero_user_norm = max(max_zero_user_norm, zero_user_norm)
            if control_user_norm > COUNTERFACTUAL_EPSILON:
                control_nonzero_user_ticks.append(tick)
            if tick <= t_off:
                cumulative_dose = math.fsum((cumulative_dose, control_user_norm))
                susceptibility = delta_kappa / max(
                    cumulative_dose, COUNTERFACTUAL_EPSILON
                )
                susceptibility_values.append(susceptibility)
                deltas_through_off.append(delta_kappa)
            else:
                susceptibility = None
            measurements.append(
                {
                    "tick": tick,
                    "control_state_id": str(
                        control_state.get("implicit_field_state_id", "")
                    ),
                    "control_state_digest": str(control_state.get("state_digest", "")),
                    "zero_state_id": str(
                        zero_state.get("implicit_field_state_id", "")
                    ),
                    "zero_state_digest": str(zero_state.get("state_digest", "")),
                    "control_step_id": str(control_step.get("step_id", "")),
                    "zero_step_id": str(zero_step.get("step_id", "")),
                    "control_realized_user_norm_kappa": control_user_norm,
                    "zero_realized_user_norm_kappa": zero_user_norm,
                    "cumulative_realized_user_dose": cumulative_dose,
                    "delta_kappa": delta_kappa,
                    "susceptibility_ratio": susceptibility,
                }
            )
        chi = max(susceptibility_values, default=0.0)
        delta_peak = max(deltas_through_off, default=0.0)
        relaxation_delta = next(
            measurement["delta_kappa"]
            for measurement in measurements
            if measurement["tick"] == relaxation_tick
        )
        stability_score = 1.0 / (1.0 + chi)
        relaxation_ratio = relaxation_delta / max(
            delta_peak, COUNTERFACTUAL_EPSILON
        )
        if cumulative_dose <= COUNTERFACTUAL_EPSILON:
            failures.append("counterfactual control branch has zero realized USER dose")
        if control_nonzero_user_ticks != [t_off]:
            failures.append(
                "counterfactual control branch must realize USER dose only at t_off"
            )
        if max_zero_user_norm > COUNTERFACTUAL_EPSILON:
            failures.append(
                "counterfactual zero branch has non-zero realized USER dose"
            )
        if delta_peak <= COUNTERFACTUAL_EPSILON:
            failures.append("counterfactual perturbation delta_peak is zero")
        if (
            not math.isfinite(chi)
            or not math.isfinite(stability_score)
            or not math.isfinite(relaxation_ratio)
            or relaxation_ratio >= 1.0
        ):
            failures.append(
                "counterfactual perturbation did not produce finite fixed-horizon relaxation"
            )

        return {
            "feedback_enabled": False,
            "input_tick": input_tick,
            "t_off": t_off,
            "relaxation_ticks": COUNTERFACTUAL_RELAXATION_TICKS,
            "relaxation_tick": relaxation_tick,
            "transcript_request_difference_fields": request_difference_fields,
            "control_amplitude": control_amplitude,
            "zero_amplitude": zero_amplitude,
            "local_scope_id": scope_id,
            "control_scope_kappa_by_basis": control_scope_kappa,
            "pattern_support": pattern_support,
            "kappa_by_basis": identity_kappa,
            "measurements": measurements,
            "cumulative_realized_user_dose_through_t_off": cumulative_dose,
            "max_zero_realized_user_norm_kappa": max_zero_user_norm,
            "chi": chi,
            "counterfactual_stability_score": stability_score,
            "delta_peak": delta_peak,
            "relaxation_delta_kappa": relaxation_delta,
            "relaxation_ratio": relaxation_ratio,
        }, failures
    except (KeyError, TypeError, ValueError, OverflowError, StopIteration) as exc:
        failures.append(f"counterfactual evidence recomputation failed: {exc}")
        return {}, failures


def counterfactual_perturbation_stability_failures(
    evidence: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if evidence.get("schema") != COUNTERFACTUAL_PERTURBATION_STABILITY_SCHEMA:
        failures.append("counterfactual evidence schema mismatch")
    if evidence.get("is_authority_state") is not False:
        failures.append("counterfactual evidence must be non-authority")
    digest_payload = {
        key: value for key, value in evidence.items() if key != "evidence_digest"
    }
    if str(evidence.get("evidence_digest", "")) != canonical_digest(digest_payload):
        failures.append("counterfactual evidence digest mismatch")

    recomputed, recomputation_failures = _counterfactual_recompute(evidence)
    failures.extend(recomputation_failures)
    structured_fields = (
        "feedback_enabled",
        "input_tick",
        "t_off",
        "relaxation_ticks",
        "relaxation_tick",
        "transcript_request_difference_fields",
        "local_scope_id",
        "control_scope_kappa_by_basis",
        "pattern_support",
        "kappa_by_basis",
        "measurements",
    )
    for field_name in structured_fields:
        if (
            field_name in recomputed
            and canonical_digest(evidence.get(field_name))
            != canonical_digest(recomputed[field_name])
        ):
            failures.append(
                f"counterfactual {field_name} does not match recomputation"
            )
    scalar_fields = (
        "control_amplitude",
        "zero_amplitude",
        "cumulative_realized_user_dose_through_t_off",
        "max_zero_realized_user_norm_kappa",
        "chi",
        "counterfactual_stability_score",
        "delta_peak",
        "relaxation_delta_kappa",
        "relaxation_ratio",
    )
    for field_name in scalar_fields:
        if field_name not in recomputed:
            continue
        try:
            matches = math.isclose(
                float(evidence.get(field_name, math.nan)),
                float(recomputed[field_name]),
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
        except (TypeError, ValueError):
            matches = False
        if not matches:
            failures.append(
                f"counterfactual {field_name} does not match recomputation"
            )
    expected_status = "passed" if not failures else "failed"
    if evidence.get("gate_status") != expected_status:
        failures.append("counterfactual gate_status does not match evidence")
    return failures


def build_counterfactual_perturbation_stability_evidence(
    *,
    run_id: str,
    initial_snapshot: Mapping[str, Any],
    control_export: Mapping[str, Any],
    zero_export: Mapping[str, Any],
) -> dict[str, Any]:
    trusted_snapshot_digest = str(initial_snapshot.get("snapshot_digest", ""))
    snapshot_payload = {
        key: value for key, value in initial_snapshot.items() if key != "snapshot_digest"
    }
    if (
        not trusted_snapshot_digest
        or trusted_snapshot_digest != canonical_digest(snapshot_payload)
    ):
        raise ValueError(
            "counterfactual runner requires the canonical trusted S0 digest"
        )
    configuration = jsonable(initial_snapshot.get("configuration") or {})
    if not isinstance(configuration, Mapping):
        raise ValueError("counterfactual runner requires trusted S0 configuration")
    configuration_digest = str(initial_snapshot.get("configuration_digest", ""))
    if configuration_digest != canonical_digest(configuration):
        raise ValueError(
            "counterfactual runner trusted configuration digest mismatch"
        )
    initial_state = jsonable(initial_snapshot.get("current_state") or {})
    if not isinstance(initial_state, Mapping):
        raise ValueError("counterfactual runner requires trusted S0 state")
    snapshot_bases = _counterfactual_records(
        initial_snapshot.get("bases", []),
        label="counterfactual trusted S0 bases",
    )
    control_bases = _counterfactual_records(
        control_export.get("implicit_basis_records", []),
        label="counterfactual control bases",
    )
    zero_bases = _counterfactual_records(
        zero_export.get("implicit_basis_records", []),
        label="counterfactual zero bases",
    )
    if (
        canonical_digest(snapshot_bases) != canonical_digest(control_bases)
        or canonical_digest(snapshot_bases) != canonical_digest(zero_bases)
    ):
        raise ValueError("counterfactual branches changed trusted S0 bases")

    evidence: dict[str, Any] = {
        "schema": COUNTERFACTUAL_PERTURBATION_STABILITY_SCHEMA,
        "evidence_id": (
            f"five-phase-counterfactual-perturbation-stability::{run_id}"
        ),
        "run_id": str(run_id),
        "trusted_initial_snapshot_digest": trusted_snapshot_digest,
        "trusted_configuration_digest": configuration_digest,
        "trusted_configuration": dict(configuration),
        "trusted_initial_state_id": str(
            initial_state.get("implicit_field_state_id", "")
        ),
        "trusted_initial_state_digest": str(initial_state.get("state_digest", "")),
        "implicit_basis_records": snapshot_bases,
        "control_branch": _counterfactual_branch_evidence(
            control_export,
            branch_label="control",
        ),
        "zero_branch": _counterfactual_branch_evidence(
            zero_export,
            branch_label="zero",
        ),
        "is_authority_state": False,
    }
    recomputed, failures = _counterfactual_recompute(evidence)
    if failures:
        raise ValueError("; ".join(failures))
    evidence.update(recomputed)
    evidence["source_record_ids"] = list(
        dict.fromkeys(
            [
                trusted_snapshot_digest,
                configuration_digest,
                str(
                    evidence["control_branch"]["interaction_audits"][0].get(
                        "audit_id", ""
                    )
                ),
                str(
                    evidence["zero_branch"]["interaction_audits"][0].get(
                        "audit_id", ""
                    )
                ),
                str(
                    evidence["pattern_support"].get(
                        "control_pattern_record_id", ""
                    )
                ),
                str(
                    evidence["pattern_support"].get("zero_pattern_record_id", "")
                ),
                *[
                    str(item.get("state_id", ""))
                    for item in evidence["control_branch"][
                        "state_tick_id_sequence"
                    ]
                ],
                *[
                    str(item.get("step_id", ""))
                    for item in evidence["control_branch"][
                        "step_tick_id_sequence"
                    ]
                ],
            ]
        )
    )
    evidence["source_record_ids"] = [
        value for value in evidence["source_record_ids"] if value
    ]
    evidence["gate_status"] = "passed"
    evidence["evidence_digest"] = canonical_digest(evidence)
    validation_failures = counterfactual_perturbation_stability_failures(
        evidence
    )
    if validation_failures:
        raise ValueError("; ".join(validation_failures))
    return evidence


def build_feedback_effect_probe_records(
    *,
    run_id: str,
    enabled_export: Mapping[str, Any],
    disabled_export: Mapping[str, Any],
) -> list[dict[str, Any]]:
    enabled_states = states_by_tick(enabled_export)
    disabled_states = states_by_tick(disabled_export)
    enabled_live_fields = live_fields_by_implicit_tick(enabled_export)
    disabled_live_fields = live_fields_by_implicit_tick(disabled_export)
    enabled_phase_fields = phase_fields_by_implicit_tick(enabled_export)
    disabled_phase_fields = phase_fields_by_implicit_tick(disabled_export)
    enabled_steps = steps_by_tick(enabled_export)
    disabled_steps = steps_by_tick(disabled_export)
    enabled_apps = applications_by_tick(enabled_export)
    probes: list[dict[str, Any]] = []
    for tick in sorted(set(enabled_steps) & set(disabled_steps) & set(enabled_apps)):
        app = enabled_apps[tick]
        applied_projection = app.get("applied_feedback_projection") or {}
        projection = projection_vector(applied_projection)
        if not projection:
            continue
        enabled_state = enabled_states.get(tick)
        disabled_state = disabled_states.get(tick)
        previous_enabled = enabled_states.get(tick - 1)
        previous_disabled = disabled_states.get(tick - 1)
        enabled_live_field = enabled_live_fields.get(tick)
        disabled_live_field = disabled_live_fields.get(tick)
        enabled_phase_field = enabled_phase_fields.get(tick)
        disabled_phase_field = disabled_phase_fields.get(tick)
        if not enabled_state or not disabled_state or not previous_enabled or not previous_disabled:
            continue
        enabled_delta = subtract_vectors(coefficient_vector(enabled_state), coefficient_vector(previous_enabled))
        disabled_delta = subtract_vectors(coefficient_vector(disabled_state), coefficient_vector(previous_disabled))
        enabled_minus_disabled = subtract_vectors(coefficient_vector(enabled_state), coefficient_vector(disabled_state))
        enabled_alignment = vector_cosine(projection, enabled_delta)
        disabled_alignment = vector_cosine(projection, disabled_delta)
        coefficient_alignment = vector_cosine(projection, enabled_minus_disabled)
        readback_delta_norm = 0.0
        readback_phase_alignment = 0.0
        feedback_phase_bias: list[float] = []
        readback_phase_delta: list[float] = []
        if enabled_live_field and disabled_live_field:
            readback_delta_norm = sequence_distance(
                live_field_vector(enabled_live_field),
                live_field_vector(disabled_live_field),
            )
        if enabled_phase_field and disabled_phase_field:
            feedback_phase_bias = _feedback_phase_bias_for_application(app, enabled_export)
            enabled_phase = phase_vector(enabled_phase_field)
            disabled_phase = phase_vector(disabled_phase_field)
            readback_phase_delta = [
                enabled_phase[index] - disabled_phase[index]
                for index in range(len(PHASE_NAMES))
            ]
            readback_phase_alignment = sequence_cosine(feedback_phase_bias, readback_phase_delta)
        probe = {
            "schema": "five_phase_feedback_effect_probe_record_v1",
            "probe_record_id": f"five-phase-feedback-effect-probe::{run_id}::{tick}",
            "run_id": str(run_id),
            "tick": int(tick),
            "enabled_implicit_live_step_id": str(enabled_steps[tick].get("step_id")),
            "disabled_implicit_live_step_id": str(disabled_steps[tick].get("step_id")),
            "feedback_application_id": str(app.get("application_record_id")),
            "feedback_projection_digest": canonical_digest(applied_projection),
            "enabled_alignment": float(enabled_alignment),
            "disabled_alignment": float(disabled_alignment),
            "coefficient_feedback_alignment": float(coefficient_alignment),
            "isolated_feedback_alignment": float(readback_phase_alignment),
            "readback_phase_alignment": float(readback_phase_alignment),
            "readback_field_delta_l2": float(readback_delta_norm),
            "feedback_phase_bias": dict(zip(PHASE_NAMES, feedback_phase_bias)) if feedback_phase_bias else {},
            "readback_phase_delta": dict(zip(PHASE_NAMES, readback_phase_delta)) if readback_phase_delta else {},
            "enabled_minus_disabled_norm": float(readback_delta_norm),
            "source_record_ids": [
                str(enabled_steps[tick].get("step_id")),
                str(disabled_steps[tick].get("step_id")),
                str(app.get("application_record_id")),
                str(enabled_state.get("implicit_field_state_id")),
                str(disabled_state.get("implicit_field_state_id")),
                str((enabled_live_field or {}).get("field_state_id", "")),
                str((disabled_live_field or {}).get("field_state_id", "")),
                str((enabled_phase_field or {}).get("record_id", "")),
                str((disabled_phase_field or {}).get("record_id", "")),
            ],
            "is_authority_state": False,
        }
        probe["source_record_ids"] = [source_id for source_id in probe["source_record_ids"] if source_id]
        probes.append(probe)
    return probes


def build_causal_tick_metrics(
    *,
    run_id: str,
    enabled_export: Mapping[str, Any],
    disabled_export: Mapping[str, Any],
    probes: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    enabled_states = states_by_tick(enabled_export)
    disabled_states = states_by_tick(disabled_export)
    enabled_live_fields = live_fields_by_implicit_tick(enabled_export)
    disabled_live_fields = live_fields_by_implicit_tick(disabled_export)
    probe_by_tick = {int(probe.get("tick", 0)): probe for probe in probes}
    records: list[dict[str, Any]] = []
    for tick in sorted(set(enabled_states) & set(disabled_states)):
        if tick == 0:
            continue
        enabled_state = enabled_states[tick]
        disabled_state = disabled_states[tick]
        enabled_live_field = enabled_live_fields.get(tick)
        disabled_live_field = disabled_live_fields.get(tick)
        if enabled_live_field and disabled_live_field:
            divergence = sequence_distance(live_field_vector(enabled_live_field), live_field_vector(disabled_live_field))
        else:
            divergence = vector_norm(subtract_vectors(coefficient_vector(enabled_state), coefficient_vector(disabled_state)))
        probe = probe_by_tick.get(tick, {})
        residual_error = 1.0 - max(0.0, float(probe.get("isolated_feedback_alignment", 0.0)))
        record = {
            "schema": "five_phase_causal_tick_metrics_v1",
            "metrics_record_id": f"five-phase-causal-tick-metrics::{run_id}::{tick}",
            "run_id": str(run_id),
            "tick": int(tick),
            "enabled_state_id": str(enabled_state.get("implicit_field_state_id")),
            "disabled_state_id": str(disabled_state.get("implicit_field_state_id")),
            "readback_divergence_l2": float(divergence),
            "enabled_energy": float(state_energy(enabled_state)),
            "disabled_energy": float(state_energy(disabled_state)),
            "energy_delta_abs": abs(float(state_energy(enabled_state)) - float(state_energy(disabled_state))),
            "feedback_isolated_alignment": float(probe.get("isolated_feedback_alignment", 0.0)),
            "feedback_readback_phase_alignment": float(probe.get("readback_phase_alignment", 0.0)),
            "feedback_enabled_alignment": float(probe.get("enabled_alignment", 0.0)),
            "feedback_disabled_alignment": float(probe.get("disabled_alignment", 0.0)),
            "causal_residual_error": float(residual_error),
            "source_record_ids": [
                str(enabled_state.get("implicit_field_state_id")),
                str(disabled_state.get("implicit_field_state_id")),
                str((enabled_live_field or {}).get("field_state_id", "")),
                str((disabled_live_field or {}).get("field_state_id", "")),
                str(probe.get("probe_record_id", "")),
            ],
            "is_authority_state": False,
        }
        record["source_record_ids"] = [source_id for source_id in record["source_record_ids"] if source_id]
        records.append(record)
    return records


def build_causal_comparison_record(
    *,
    run_id: str,
    enabled_manifest: Mapping[str, Any],
    disabled_manifest: Mapping[str, Any],
    perturbation_schedule: Mapping[str, Any],
    tick_metrics: Sequence[Mapping[str, Any]],
    feedback_effect_probes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    max_divergence = max((float(record.get("readback_divergence_l2", 0.0)) for record in tick_metrics), default=0.0)
    max_alignment = max((float(record.get("isolated_feedback_alignment", 0.0)) for record in feedback_effect_probes), default=0.0)
    max_energy_delta = max((float(record.get("energy_delta_abs", 0.0)) for record in tick_metrics), default=0.0)
    enabled_residual_distance = float(enabled_manifest.get("residual_distance_mean", 0.0))
    disabled_residual_distance = float(disabled_manifest.get("residual_distance_mean", 0.0))
    enabled_pattern_stability = float(enabled_manifest.get("pattern_stability_mean", 0.0))
    disabled_pattern_stability = float(disabled_manifest.get("pattern_stability_mean", 0.0))
    comparison = {
        "schema": "five_phase_causal_comparison_record_v1",
        "comparison_record_id": f"five-phase-causal-comparison::{run_id}",
        "run_id": str(run_id),
        "enabled_run_id": str(enabled_manifest.get("run_id")),
        "disabled_run_id": str(disabled_manifest.get("run_id")),
        "initial_snapshot_digest": str(enabled_manifest.get("initial_snapshot_digest")),
        "perturbation_schedule_digest": str(perturbation_schedule.get("schedule_digest")),
        "max_readback_divergence_l2": float(max_divergence),
        "max_feedback_isolated_alignment": float(max_alignment),
        "max_energy_delta_abs": float(max_energy_delta),
        "residual_distance_delta": float(enabled_residual_distance - disabled_residual_distance),
        "pattern_stability_delta": float(enabled_pattern_stability - disabled_pattern_stability),
        "tick_metric_ids": [str(record.get("metrics_record_id")) for record in tick_metrics],
        "feedback_effect_probe_ids": [str(record.get("probe_record_id")) for record in feedback_effect_probes],
        "source_record_ids": [
            str(enabled_manifest.get("manifest_digest")),
            str(disabled_manifest.get("manifest_digest")),
            str(perturbation_schedule.get("schedule_digest")),
            *[str(record.get("metrics_record_id")) for record in tick_metrics],
            *[str(record.get("probe_record_id")) for record in feedback_effect_probes],
        ],
        "is_authority_state": False,
    }
    comparison["comparison_digest"] = canonical_digest(comparison)
    return comparison


__all__ = [
    "COUNTERFACTUAL_EPSILON",
    "COUNTERFACTUAL_PERTURBATION_STABILITY_SCHEMA",
    "COUNTERFACTUAL_RELAXATION_TICKS",
    "DEFAULT_ARTIFACT_BUDGET_BYTES",
    "DEFAULT_ENERGY_RUNAWAY_ABS_MAX",
    "DEFAULT_ENERGY_RUNAWAY_RATIO_MAX",
    "DEFAULT_MIN_DIRECTIONAL_ALIGNMENT",
    "DEFAULT_MIN_QUALITY_IMPROVEMENT",
    "DEFAULT_MIN_READBACK_DIVERGENCE",
    "PHASE_NAMES",
    "build_causal_comparison_record",
    "build_causal_run_manifest",
    "build_causal_tick_metrics",
    "build_counterfactual_perturbation_stability_evidence",
    "build_feedback_effect_probe_records",
    "build_perturbation_schedule",
    "canonical_digest",
    "canonical_json_bytes",
    "counterfactual_perturbation_stability_failures",
    "live_field_vector",
    "jsonable",
    "mean_feedback_distance",
    "mean_pattern_stability",
    "merge_projection",
    "phase_vector",
]
