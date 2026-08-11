from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping

from world_engine.contracts import FieldState, ProjectionFrame
from world_engine.five_phase import (
    FivePhaseAgentStateRecord,
    FivePhaseConstraintSetRecord,
    FivePhaseFeedbackRecord,
    FivePhaseFieldRecord,
    FivePhasePatternRecord,
    FivePhaseResidualConstraintRecord,
    FivePhaseTraceRecord,
)
from world_engine.five_phase_live import (
    build_five_phase_initial_response_context,
    build_five_phase_transition_response_context,
    measure_five_phase_feedback_response,
    measure_five_phase_support_energy,
    materialize_five_phase_pattern_response,
    reject_five_phase_live_shortcuts,
)
from world_engine.five_phase_patterns import detect_five_phase_patterns
from world_engine.completion import (
    implicit_live_energy_ledger_failures,
    implicit_projection_frame_lineage_failures,
)
from world_engine.implicit_field import build_basis_spatial_index, build_implicit_field_state
from world_engine.implicit_field_runtime import advance_implicit_field_state


def _jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _dicts(values: Any) -> list[dict[str, Any]]:
    result = []
    for value in values or []:
        converted = _jsonable(value)
        if not isinstance(converted, Mapping):
            raise ValueError("expected mapping record")
        result.append(dict(converted))
    return result


def _dicts_or_fail(values: Any, *, label: str, reasons: list[str]) -> list[dict[str, Any]]:
    try:
        return _dicts(values)
    except Exception as exc:
        reasons.append(f"{label} read-back failed: {exc}")
        return []


def _parse_or_fail(parser, values: Any, *, label: str, reasons: list[str]):
    parsed = []
    for value in _dicts_or_fail(values, label=label, reasons=reasons):
        try:
            parsed.append(parser(value))
        except Exception as exc:
            reasons.append(f"{label} read-back failed: {exc}")
    return parsed


def _retag_recomputed_implicit_state(state: Mapping[str, Any], *, state_id: str) -> dict[str, Any]:
    return build_implicit_field_state(
        implicit_field_state_id=state_id,
        tick=int(state["tick"]),
        basis_ids=list(state["basis_ids"]),
        basis_layout_digest=str(state["basis_layout_digest"]),
        basis_spatial_index_digest=str(state["basis_spatial_index_digest"]),
        basis_coefficients=dict(state.get("basis_coefficients", {})),
        sparse_coupling_edges=list(state.get("sparse_coupling_edges", [])),
        background_model=dict(state.get("background_model", {})),
        active_local_patch_ids=list(state.get("active_local_patch_ids", [])),
        validity_region_world=dict(state.get("validity_region_world", {})),
        energy_summary=dict(state.get("energy_summary", {})),
        source_record_ids=list(state.get("source_record_ids", [])),
        authority_status=str(state.get("authority_status", "candidate")),
        runtime_cost_summary=dict(state.get("runtime_cost_summary", {})),
    )


def _response_value_matches(actual: Any, expected: Any) -> bool:
    if isinstance(expected, float):
        try:
            return math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=1e-12)
        except (TypeError, ValueError):
            return False
    if isinstance(expected, (Mapping, list, tuple)):
        return _canonical_digest(actual) == _canonical_digest(expected)
    return actual == expected


def evaluate_five_phase_live_completion(exported: Mapping[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    jsonable_export = _jsonable(exported)
    try:
        reject_five_phase_live_shortcuts(jsonable_export, path="five_phase_live_export")
    except ValueError as exc:
        reasons.append(str(exc))

    live_steps = _dicts_or_fail(exported.get("five_phase_live_steps", []), label="five phase live step", reasons=reasons)
    frames = _parse_or_fail(ProjectionFrame.from_dict, exported.get("projection_frames", []), label="projection frame", reasons=reasons)
    live_field_states = _parse_or_fail(
        FieldState.from_dict,
        exported.get("five_phase_live_field_states", []),
        label="five phase live field state",
        reasons=reasons,
    )
    phase_fields = _parse_or_fail(
        FivePhaseFieldRecord.from_dict,
        exported.get("five_phase_phase_fields", []),
        label="five phase field",
        reasons=reasons,
    )
    constraint_sets = _parse_or_fail(
        FivePhaseConstraintSetRecord.from_dict,
        exported.get("five_phase_constraint_sets", []),
        label="five phase constraint set",
        reasons=reasons,
    )
    patterns = _parse_or_fail(FivePhasePatternRecord.from_dict, exported.get("five_phase_patterns", []), label="five phase pattern", reasons=reasons)
    traces = _parse_or_fail(FivePhaseTraceRecord.from_dict, exported.get("five_phase_traces", []), label="five phase trace", reasons=reasons)
    residuals = _parse_or_fail(
        FivePhaseResidualConstraintRecord.from_dict,
        exported.get("five_phase_residual_constraints", []),
        label="five phase residual constraint",
        reasons=reasons,
    )
    agents = _parse_or_fail(FivePhaseAgentStateRecord.from_dict, exported.get("five_phase_agent_states", []), label="five phase agent state", reasons=reasons)
    feedbacks = _parse_or_fail(FivePhaseFeedbackRecord.from_dict, exported.get("five_phase_feedback_records", []), label="five phase feedback", reasons=reasons)
    bridges = _dicts_or_fail(exported.get("five_phase_live_bridges", []), label="five phase live bridge", reasons=reasons)
    implicit_steps = _dicts_or_fail(exported.get("implicit_live_step_records", []), label="implicit live step", reasons=reasons)
    implicit_states = _dicts_or_fail(exported.get("implicit_field_states", []), label="implicit field state", reasons=reasons)
    feedback_applications = _dicts_or_fail(
        exported.get("five_phase_feedback_applications", []),
        label="five phase feedback application",
        reasons=reasons,
    )
    session_manifest = exported.get("session", {})
    feedback_enabled_value = session_manifest.get("five_phase_feedback_enabled", True) if isinstance(session_manifest, Mapping) else True
    if not isinstance(feedback_enabled_value, bool):
        reasons.append("session five_phase_feedback_enabled must be a bool")
        feedback_enabled_value = True
    feedback_enabled = bool(feedback_enabled_value)

    phase_ids = {record.record_id for record in phase_fields}
    constraint_ids = {record.record_id for record in constraint_sets}
    pattern_ids = {record.record_id for record in patterns}
    trace_ids = {record.record_id for record in traces}
    residual_ids = {record.record_id for record in residuals}
    agent_ids = {record.record_id for record in agents}
    feedback_ids = {record.record_id for record in feedbacks}
    implicit_bases = _dicts_or_fail(exported.get("implicit_basis_records", []), label="implicit basis", reasons=reasons)
    basis_ids = {str(record.get("basis_id")) for record in implicit_bases}
    try:
        basis_spatial_index = build_basis_spatial_index(implicit_bases)
    except (KeyError, TypeError, ValueError) as exc:
        basis_spatial_index = {}
        reasons.append(f"implicit basis spatial index recomputation failed: {exc}")
    bridge_ids = {record.get("bridge_record_id") for record in bridges}
    live_step_ids = {record.get("live_step_id") for record in live_steps}
    field_ids = {state.field_state_id for state in live_field_states}
    implicit_states_by_id = {str(state.get("implicit_field_state_id")): state for state in implicit_states}

    authority_ok = bool(live_steps and phase_fields and bridges and patterns and traces and residuals and agents) and not reasons
    if not authority_ok and not reasons:
        reasons.append("five phase live export missing required derived artifact family")
    for step in live_steps:
        if step.get("is_authority_state") is not False:
            authority_ok = False
            reasons.append("five phase live step must be non-authority")
        if step.get("phase_field_id") not in phase_ids or step.get("bridge_record_id") not in bridge_ids:
            authority_ok = False
            reasons.append("five phase live step references missing bridge or phase field")
        if step.get("constraint_set_id") not in constraint_ids:
            authority_ok = False
            reasons.append("five phase live step references missing constraint set")
        if step.get("field_state_id") not in field_ids:
            authority_ok = False
            reasons.append("five phase live step references missing read-back field state")
        step_artifact_refs = {
            "pattern_ids": pattern_ids,
            "trace_ids": trace_ids,
            "residual_constraint_ids": residual_ids,
            "agent_state_ids": agent_ids,
            "feedback_record_ids": feedback_ids,
        }
        for key, known_ids in step_artifact_refs.items():
            referenced_ids = {str(value) for value in step.get(key, [])}
            if not referenced_ids and key != "feedback_record_ids":
                authority_ok = False
                reasons.append(f"five phase live step missing {key}")
                continue
            if not referenced_ids.issubset(known_ids):
                authority_ok = False
                reasons.append(f"five phase live step references missing {key}")
        if step.get("feedback_record_ids") and not step.get("feedback_input_projection"):
            authority_ok = False
            reasons.append("five phase live step with Feedback records is missing its candidate projection")
        if not step.get("feedback_record_ids") and step.get("feedback_input_projection"):
            authority_ok = False
            reasons.append("five phase live step has a projection without Feedback lineage")
        source_ids = {str(value) for value in step.get("source_record_ids", [])}
        required_lineage_ids = [
            step.get("live_step_id"),
            step.get("phase_field_id"),
            step.get("constraint_set_id"),
            step.get("bridge_record_id"),
            step.get("field_state_id"),
            *step.get("pattern_ids", []),
            *step.get("trace_ids", []),
            *step.get("residual_constraint_ids", []),
            *step.get("agent_state_ids", []),
            *step.get("feedback_record_ids", []),
        ]
        for required_id in required_lineage_ids:
            if str(required_id) not in source_ids:
                authority_ok = False
                reasons.append("five phase live step source_record_ids missing required lineage id")
                break

    future_record_id_lists = {
        "canonical implicit state": [
            str(record.get("implicit_field_state_id", "")) for record in implicit_states
        ],
        "canonical implicit step": [str(record.get("step_id", "")) for record in implicit_steps],
        "five phase live step": [str(record.get("live_step_id")) for record in live_steps],
        "five phase bridge": [str(record.get("bridge_record_id")) for record in bridges],
        "five phase field": [record.record_id for record in phase_fields],
        "five phase constraint": [record.record_id for record in constraint_sets],
        "five phase Pattern instance": [record.record_id for record in patterns],
        "five phase Trace": [record.record_id for record in traces],
        "five phase residual": [record.record_id for record in residuals],
        "five phase Agent": [record.record_id for record in agents],
        "five phase Feedback": [record.record_id for record in feedbacks],
    }
    for label, values in future_record_id_lists.items():
        if any(not value for value in values) or len(values) != len(set(values)):
            authority_ok = False
            reasons.append(f"{label} record IDs must be unique per canonical transition")

    causal_steps_by_implicit_state: dict[str, list[dict[str, Any]]] = {}
    for step in live_steps:
        implicit_state_id = str(step.get("implicit_field_state_id", ""))
        causal_steps_by_implicit_state.setdefault(implicit_state_id, []).append(step)
        implicit_state = implicit_states_by_id.get(implicit_state_id)
        bridge = next((record for record in bridges if record.get("bridge_record_id") == step.get("bridge_record_id")), None)
        if implicit_state is None:
            authority_ok = False
            reasons.append("five phase live step references missing canonical implicit state")
        elif int(step.get("tick", -1)) != int(implicit_state.get("tick", -2)):
            authority_ok = False
            reasons.append("five phase live step tick does not match canonical implicit state")
        if bridge is None or str(bridge.get("implicit_field_state_id")) != implicit_state_id:
            authority_ok = False
            reasons.append("five phase live step bridge does not cite its canonical implicit state")
        elif int(bridge.get("implicit_tick", -1)) != int(step.get("tick", -2)):
            authority_ok = False
            reasons.append("five phase live bridge implicit_tick does not match causal step")
    if set(causal_steps_by_implicit_state) != set(implicit_states_by_id):
        authority_ok = False
        reasons.append("every canonical implicit state must own exactly one FivePhase causal step")
    if any(len(items) != 1 for items in causal_steps_by_implicit_state.values()):
        authority_ok = False
        reasons.append("canonical implicit state cannot own multiple FivePhase causal steps")

    artifact_owners: dict[str, dict[str, Any]] = {}
    for key, known_ids in (
        ("pattern_ids", pattern_ids),
        ("trace_ids", trace_ids),
        ("residual_constraint_ids", residual_ids),
        ("agent_state_ids", agent_ids),
        ("feedback_record_ids", feedback_ids),
    ):
        ownership_counts: dict[str, int] = {}
        for step in live_steps:
            for record_id in map(str, step.get(key, [])):
                ownership_counts[record_id] = ownership_counts.get(record_id, 0) + 1
                artifact_owners[record_id] = step
        if set(ownership_counts) != set(map(str, known_ids)) or any(count != 1 for count in ownership_counts.values()):
            authority_ok = False
            reasons.append(f"{key} must belong to exactly one canonical FivePhase step")

    patterns_by_id = {record.record_id: record for record in patterns}
    traces_by_id = {record.record_id: record for record in traces}
    residuals_by_id = {record.record_id: record for record in residuals}
    agents_by_id = {record.record_id: record for record in agents}
    bridges_by_id = {str(record.get("bridge_record_id")): record for record in bridges}
    phase_fields_by_id = {record.record_id: record for record in phase_fields}
    constraint_sets_by_id = {record.record_id: record for record in constraint_sets}
    ordered_live_steps = sorted(live_steps, key=lambda record: int(record.get("tick", -1)))

    def intrinsic_pattern_projection(record: FivePhasePatternRecord) -> dict[str, Any]:
        return {
            "record_id": record.record_id,
            "schema": record.schema,
            "tick": int(record.tick),
            "phase_field_id": record.phase_field_id,
            "constraint_set_id": record.constraint_set_id,
            "support_bounds_grid": [int(value) for value in record.support_bounds_grid],
            "centroid_grid": [float(value) for value in record.centroid_grid],
            "phase_vector": record.phase_vector.to_dict(),
            "dominant_phase": record.dominant_phase,
            "continuity_score": float(record.continuity_score),
            "invariant_signature": record.invariant_signature,
            "source_record_ids": list(
                dict.fromkeys(str(value) for value in record.source_record_ids)
            ),
            "payload": {
                field_name: record.payload.get(field_name)
                for field_name in (
                    "support_size",
                    "support_energy",
                    "pattern_identity_id",
                    "previous_pattern_record_id",
                    "objects_derive_downstream",
                )
            },
            "is_authority_state": bool(record.is_authority_state),
        }

    previous_expected_patterns: list[FivePhasePatternRecord] = []
    for live_step in ordered_live_steps:
        phase_field = phase_fields_by_id.get(str(live_step.get("phase_field_id", "")))
        constraint_set = constraint_sets_by_id.get(
            str(live_step.get("constraint_set_id", ""))
        )
        actual_step_patterns = [
            patterns_by_id[pattern_id]
            for pattern_id in map(str, live_step.get("pattern_ids", []))
            if pattern_id in patterns_by_id
        ]
        if phase_field is None or constraint_set is None:
            authority_ok = False
            reasons.append("FivePhase Pattern intrinsic replay lacks phase/constraint owner")
            previous_expected_patterns = []
            continue
        try:
            expected_step_patterns, _expected_lifecycle = detect_five_phase_patterns(
                phase_field,
                constraint_set=constraint_set,
                previous_patterns=previous_expected_patterns,
                min_support_weight=0.1,
            )
        except (KeyError, TypeError, ValueError) as exc:
            authority_ok = False
            reasons.append(f"FivePhase Pattern intrinsic replay failed: {exc}")
            previous_expected_patterns = []
            continue
        if _canonical_digest(
            [intrinsic_pattern_projection(record) for record in actual_step_patterns]
        ) != _canonical_digest(
            [intrinsic_pattern_projection(record) for record in expected_step_patterns]
        ):
            authority_ok = False
            reasons.append("FivePhase Pattern intrinsic geometry/identity does not match detection replay")
        previous_expected_patterns = expected_step_patterns

    live_step_index = {str(record.get("live_step_id")): index for index, record in enumerate(ordered_live_steps)}
    implicit_steps_by_result_state: dict[str, list[dict[str, Any]]] = {}
    for implicit_step in implicit_steps:
        implicit_steps_by_result_state.setdefault(str(implicit_step.get("result_state_id", "")), []).append(
            implicit_step
        )
    claimed_pattern_predecessors: set[str] = set()
    for pattern in patterns:
        identity_id = pattern.payload.get("pattern_identity_id")
        previous_id = pattern.payload.get("previous_pattern_record_id")
        if not isinstance(identity_id, str) or not identity_id:
            authority_ok = False
            reasons.append("five phase Pattern instance is missing pattern_identity_id")
        if previous_id is None:
            continue
        previous_id = str(previous_id)
        previous = patterns_by_id.get(previous_id)
        if previous is None or previous.tick >= pattern.tick:
            authority_ok = False
            reasons.append("five phase Pattern previous_pattern_record_id is missing or stale")
            continue
        if previous_id not in {str(value) for value in pattern.source_record_ids}:
            authority_ok = False
            reasons.append("five phase Pattern does not cite previous_pattern_record_id")
        if previous.payload.get("pattern_identity_id") != identity_id:
            authority_ok = False
            reasons.append("five phase Pattern changes identity across predecessor lineage")
        if previous_id in claimed_pattern_predecessors:
            authority_ok = False
            reasons.append("five phase Pattern predecessor is claimed by multiple successors")
        claimed_pattern_predecessors.add(previous_id)

    for pattern in patterns:
        owner = artifact_owners.get(pattern.record_id)
        current_state = (
            implicit_states_by_id.get(str(owner.get("implicit_field_state_id", "")))
            if owner is not None
            else None
        )
        bridge = bridges_by_id.get(str(owner.get("bridge_record_id", ""))) if owner is not None else None
        if owner is None or current_state is None or bridge is None:
            authority_ok = False
            reasons.append("live FivePhase Pattern is missing its canonical state or bridge owner")
            continue
        previous_id = str(pattern.payload.get("previous_pattern_record_id") or "")
        previous_pattern = patterns_by_id.get(previous_id) if previous_id else None
        current_tick = int(current_state.get("tick", -1))
        try:
            if previous_pattern is None:
                fixed_bounds = [int(value) for value in pattern.support_bounds_grid]
                grid_shape = [int(value) for value in bridge.get("grid_shape", [])]
                source_channel_name = str(bridge.get("source_channel_name", ""))
                identity_id = str(pattern.payload.get("pattern_identity_id") or pattern.record_id)
                expected_context = build_five_phase_initial_response_context(
                    pattern_identity_id=identity_id,
                    support_bounds_grid=fixed_bounds,
                    grid_shape=grid_shape,
                    source_channel_name=source_channel_name,
                    implicit_field_state=current_state,
                    implicit_basis_records=implicit_bases,
                    basis_spatial_index=basis_spatial_index,
                    tick=current_tick,
                )
            else:
                previous_owner = artifact_owners.get(previous_pattern.record_id)
                owner_index = live_step_index.get(str(owner.get("live_step_id")), -1)
                previous_owner_index = (
                    live_step_index.get(str(previous_owner.get("live_step_id")), -1)
                    if previous_owner is not None
                    else -1
                )
                if owner_index <= 0 or previous_owner_index != owner_index - 1:
                    raise ValueError("Pattern predecessor is not from the immediate canonical causal step")
                previous_state = implicit_states_by_id.get(
                    str(previous_owner.get("implicit_field_state_id", ""))
                )
                transitions = implicit_steps_by_result_state.get(
                    str(current_state.get("implicit_field_state_id", "")),
                    [],
                )
                if previous_state is None or len(transitions) != 1:
                    raise ValueError("Pattern response is missing one exact canonical transition")
                transition = transitions[0]
                if str(transition.get("previous_state_id", "")) != str(
                    previous_state.get("implicit_field_state_id", "")
                ):
                    raise ValueError("Pattern response transition does not start at its predecessor state")
                expected_context = build_five_phase_transition_response_context(
                    previous_pattern=previous_pattern,
                    previous_implicit_field_state=previous_state,
                    current_implicit_field_state=current_state,
                    implicit_basis_records=implicit_bases,
                    basis_spatial_index=basis_spatial_index,
                    realized_user_input_projection=transition.get("realized_user_input_projection") or {},
                    realized_feedback_input_projection=transition.get(
                        "realized_five_phase_feedback_input_projection"
                    )
                    or {},
                    tick=current_tick,
                )
                fixed_bounds = [
                    int(value)
                    for value in previous_pattern.payload.get(
                        "identity_support_bounds_grid",
                        previous_pattern.support_bounds_grid,
                    )
                ]
                grid_shape = [
                    int(value)
                    for value in previous_pattern.payload.get(
                        "identity_support_grid_shape",
                        bridge.get("grid_shape", []),
                    )
                ]
                source_channel_name = str(
                    previous_pattern.payload.get(
                        "support_source_channel_name",
                        bridge.get("source_channel_name", ""),
                    )
                )
                identity_id = str(pattern.payload.get("pattern_identity_id") or pattern.record_id)
            expected_stability, expected_payload = materialize_five_phase_pattern_response(
                previous_pattern=previous_pattern,
                pattern_identity_id=identity_id,
                response_context=expected_context,
                support_bounds_grid=fixed_bounds,
                grid_shape=grid_shape,
                source_channel_name=source_channel_name,
                implicit_field_state=current_state,
                tick=current_tick,
            )
        except (KeyError, TypeError, ValueError) as exc:
            authority_ok = False
            reasons.append(f"live FivePhase Pattern response recomputation failed: {exc}")
            continue
        if not math.isclose(float(pattern.stability_score), expected_stability, rel_tol=0.0, abs_tol=1e-12):
            authority_ok = False
            reasons.append("live FivePhase Pattern stability_score does not match fixed-support response")
        for field_name, expected_value in expected_payload.items():
            if not _response_value_matches(pattern.payload.get(field_name), expected_value):
                authority_ok = False
                reasons.append(f"live FivePhase Pattern {field_name} does not match response recomputation")

    for agent in agents:
        owner = artifact_owners.get(agent.record_id)
        pattern = patterns_by_id.get(agent.pattern_id)
        trace = traces_by_id.get(str(agent.trace_id))
        residual = residuals_by_id.get(str(agent.residual_constraint_id))
        bridge = bridges_by_id.get(str(agent.bridge_record_id))
        implicit_state = implicit_states_by_id.get(str(agent.source_state_id))
        if agent.schema != "five_phase_agent_state_v2":
            authority_ok = False
            reasons.append("live FivePhase Agent must use exact-lineage v2 schema")
            continue
        if owner is None or pattern is None or trace is None or residual is None or bridge is None or implicit_state is None:
            authority_ok = False
            reasons.append("live FivePhase Agent has missing Pattern/Trace/residual/bridge/state lineage")
            continue
        if (
            agent.pattern_id not in set(map(str, owner.get("pattern_ids", [])))
            or agent.trace_id not in set(map(str, owner.get("trace_ids", [])))
            or agent.residual_constraint_id not in set(map(str, owner.get("residual_constraint_ids", [])))
            or agent.bridge_record_id != owner.get("bridge_record_id")
            or agent.source_state_id != owner.get("implicit_field_state_id")
            or trace.pattern_id != pattern.record_id
            or residual.trace_id != trace.record_id
            or residual.pattern_id != pattern.record_id
            or residual.phase_field_id != trace.phase_field_id
            or str(bridge.get("implicit_field_state_id")) != agent.source_state_id
            or agent.source_state_digest != implicit_state.get("state_digest")
        ):
            authority_ok = False
            reasons.append("live FivePhase Agent v2 lineage crosses canonical steps")
        if not math.isclose(float(agent.response_stability), float(pattern.stability_score), rel_tol=0.0, abs_tol=1e-12):
            authority_ok = False
            reasons.append("live FivePhase Agent response_stability does not match Pattern")
        for field_name, payload_name in (
            ("support_energy_setpoint", "support_energy_setpoint"),
            ("support_energy_current", "support_energy_current"),
        ):
            payload_value = pattern.payload.get(payload_name)
            if payload_value is None or not math.isclose(float(getattr(agent, field_name)), float(payload_value), rel_tol=0.0, abs_tol=1e-12):
                authority_ok = False
                reasons.append(f"live FivePhase Agent {field_name} does not match Pattern read-back")

    for feedback in feedbacks:
        owner = artifact_owners.get(feedback.record_id)
        agent = agents_by_id.get(feedback.agent_state_id)
        if feedback.schema != "five_phase_feedback_v2" or owner is None or agent is None:
            authority_ok = False
            reasons.append("live FivePhase Feedback must use v2 and cite an owned Agent")
            continue
        owner_index = live_step_index.get(str(owner.get("live_step_id")), -1)
        expected_predecessor = ordered_live_steps[owner_index - 1].get("live_step_id") if owner_index > 0 else None
        if (
            feedback.pattern_id != agent.pattern_id
            or feedback.trace_id != agent.trace_id
            or feedback.residual_constraint_id != agent.residual_constraint_id
            or feedback.bridge_record_id != agent.bridge_record_id
            or feedback.source_state_id != agent.source_state_id
            or feedback.source_state_digest != agent.source_state_digest
            or feedback.predecessor_causal_step_id != expected_predecessor
            or feedback.agent_state_id not in set(map(str, owner.get("agent_state_ids", [])))
            or feedback.target_basis_id not in basis_ids
        ):
            authority_ok = False
            reasons.append("live FivePhase Feedback v2 lineage does not match its immediate causal predecessor")
        expected_error = float(agent.support_energy_setpoint) - float(agent.support_energy_current)
        if not math.isclose(float(feedback.signed_error), expected_error, rel_tol=0.0, abs_tol=1e-12):
            authority_ok = False
            reasons.append("live FivePhase Feedback signed_error does not match Agent support error")

    for bridge in bridges:
        if bridge.get("is_authority_state") is not False:
            authority_ok = False
            reasons.append("five phase live bridge must be non-authority")
        if bridge.get("field_tick") != bridge.get("tick"):
            authority_ok = False
            reasons.append("five phase live bridge field_tick must match bridge tick")
        if bridge.get("field_state_id") not in field_ids:
            authority_ok = False
            reasons.append("five phase live bridge references missing FieldState")

    frame_ok = bool(frames and live_steps)
    frame_lineage_failures = implicit_projection_frame_lineage_failures(exported)
    if frame_lineage_failures:
        frame_ok = False
        reasons.extend(
            f"projection frame {failure.get('frame_id', '')} {failure.get('reason', 'lineage failure')}"
            for failure in frame_lineage_failures
        )
    frame_live_step_ids: list[str] = []
    for frame in frames:
        summary = frame.payload.get("five_phase_live_summary")
        if not summary:
            frame_ok = False
            reasons.append("projection frame missing five_phase_live_summary")
            continue
        frame_live_step_ids.append(str(summary.get("live_step_id")))
        semantics = frame.payload.get("timeline_semantics")
        if not isinstance(semantics, Mapping):
            frame_ok = False
            reasons.append("projection frame missing timeline_semantics")
            continue
        source_world_state_id = str(semantics.get("source_world_state_id", ""))
        state_causal_steps = causal_steps_by_implicit_state.get(source_world_state_id, [])
        if len(state_causal_steps) != 1 or summary.get("live_step_id") != state_causal_steps[0].get("live_step_id"):
            frame_ok = False
            reasons.append("projection frame must cite the existing causal step for its source world state")
        if int(summary.get("tick", -999)) != int(frame.tick):
            frame_ok = False
            reasons.append("five_phase_live_summary tick does not match projection frame tick")
        live_step = next((step for step in live_steps if step.get("live_step_id") == summary.get("live_step_id")), None)
        if live_step is not None and int(live_step.get("tick", -999)) != int(frame.tick):
            frame_ok = False
            reasons.append("five_phase_live_summary live step tick does not match projection frame tick")
        if live_step is not None:
            expected_pattern_response = []
            for pattern_id in map(str, live_step.get("pattern_ids", [])):
                pattern = patterns_by_id.get(pattern_id)
                if pattern is None:
                    continue
                expected_pattern_response.append(
                    {
                        "pattern_id": pattern.record_id,
                        "pattern_identity_id": pattern.payload.get("pattern_identity_id"),
                        "previous_pattern_record_id": pattern.payload.get("previous_pattern_record_id"),
                        "stability_score": float(pattern.stability_score),
                        "stability_formula": pattern.payload.get("stability_formula"),
                        "deformation_normalization": pattern.payload.get("deformation_normalization"),
                        "episode_id": pattern.payload.get("episode_id"),
                        "episode_status": pattern.payload.get("episode_status"),
                        "support_energy_setpoint": pattern.payload.get("support_energy_setpoint"),
                        "support_energy_current": pattern.payload.get("support_energy_current"),
                        "deformation_from_setpoint": pattern.payload.get("deformation_from_setpoint"),
                        "q_user": pattern.payload.get("q_user"),
                        "Q_live": pattern.payload.get("Q_live"),
                        "user_dose_normalization": pattern.payload.get("user_dose_normalization"),
                        "cumulative_realized_user_dose": pattern.payload.get(
                            "cumulative_realized_user_dose"
                        ),
                        "q_feedback": pattern.payload.get("q_feedback"),
                        "feedback_dose_normalization": pattern.payload.get(
                            "feedback_dose_normalization"
                        ),
                        "realized_feedback_dose": pattern.payload.get("realized_feedback_dose"),
                        "relaxation_from_peak": pattern.payload.get("relaxation_from_peak"),
                    }
                )
            if _canonical_digest(summary.get("pattern_response")) != _canonical_digest(
                expected_pattern_response
            ):
                frame_ok = False
                reasons.append("five_phase_live_summary Pattern response does not match causal records")
        if summary.get("live_step_id") not in live_step_ids:
            frame_ok = False
            reasons.append("five_phase_live_summary references missing live step")
        if summary.get("phase_field_id") not in phase_ids:
            frame_ok = False
            reasons.append("five_phase_live_summary references missing phase field")
        summary_sources = {str(source_id) for source_id in summary.get("source_record_ids", [])}
        if str(summary.get("live_step_id")) not in summary_sources:
            frame_ok = False
            reasons.append("five_phase_live_summary must cite its live_step_id in source_record_ids")
        if str(summary.get("phase_field_id")) not in summary_sources:
            frame_ok = False
            reasons.append("five_phase_live_summary must cite its phase_field_id in source_record_ids")
        frame_sources = {str(source_id) for source_id in frame.source_record_ids}
        if str(summary.get("live_step_id")) not in frame_sources or str(summary.get("phase_field_id")) not in frame_sources:
            frame_ok = False
            reasons.append("projection frame source_record_ids must cite FivePhase summary lineage")
        if summary.get("is_authority_state") is not False:
            frame_ok = False
            reasons.append("five_phase_live_summary must be non-authority")
    if frame_ok:
        if set(frame_live_step_ids) != {str(value) for value in live_step_ids}:
            frame_ok = False
            reasons.append("projection frames must cover every FivePhase live step")

    feedback_ok = bool(implicit_steps)
    ordinary_implicit_steps = [step for step in implicit_steps if not step.get("refinement_patch_ids")]
    application_record_ids = [str(record.get("application_record_id") or "") for record in feedback_applications]
    owned_application_ids = [
        str(step.get("five_phase_feedback_application_id") or "")
        for step in ordinary_implicit_steps
    ]
    if any(not record_id for record_id in application_record_ids) or len(application_record_ids) != len(
        set(application_record_ids)
    ):
        feedback_ok = False
        reasons.append("five phase feedback application record IDs must be unique and non-empty")
    if any(not record_id for record_id in owned_application_ids) or len(owned_application_ids) != len(
        set(owned_application_ids)
    ):
        feedback_ok = False
        reasons.append("ordinary implicit steps must each own one unique feedback application")
    if len(application_record_ids) != len(owned_application_ids) or set(application_record_ids) != set(
        owned_application_ids
    ):
        feedback_ok = False
        reasons.append("feedback applications must belong to exactly one ordinary implicit step")
    applications_by_id = {
        str(record.get("application_record_id") or ""): record
        for record in feedback_applications
    }
    live_steps_by_id = {str(record.get("live_step_id")): record for record in live_steps}
    consumed_source_step_ids: list[str] = []
    for step in implicit_steps:
        if step.get("refinement_patch_ids"):
            if step.get("five_phase_feedback_application_id") or step.get("five_phase_feedback_input_projection"):
                feedback_ok = False
                reasons.append("refinement transition must not claim an ordinary Feedback application")
            continue
        if "five_phase_feedback_input_projection" not in step:
            feedback_ok = False
            reasons.append("implicit live step missing five phase feedback projection field")
        if "five_phase_feedback_enabled" in step:
            if not isinstance(step.get("five_phase_feedback_enabled"), bool):
                feedback_ok = False
                reasons.append("implicit live step feedback enabled flag must be a bool")
            elif bool(step.get("five_phase_feedback_enabled")) != feedback_enabled:
                feedback_ok = False
                reasons.append("implicit live step feedback enabled flag does not match session")
        source_step_ids = [str(value) for value in step.get("five_phase_live_step_ids", [])]
        consumed_source_step_ids.extend(source_step_ids)
        projection = step.get("five_phase_feedback_input_projection") or {}
        application_id = str(step.get("five_phase_feedback_application_id") or "")
        application = applications_by_id.get(application_id)
        if application is None:
            feedback_ok = False
            reasons.append("implicit live step references missing five phase feedback application")
        if not feedback_enabled and projection:
            feedback_ok = False
            reasons.append("disabled implicit live step must not apply five phase feedback projection")
        if projection and step.get("five_phase_feedback_applied") is not True:
            feedback_ok = False
            reasons.append("non-empty five phase feedback projection must be marked applied")
        if not projection and step.get("five_phase_feedback_applied") is not False:
            feedback_ok = False
            reasons.append("empty five phase feedback projection must not be marked applied")
        if not feedback_enabled and step.get("five_phase_feedback_applied") is not False:
            feedback_ok = False
            reasons.append("disabled implicit live step must mark five phase feedback as not applied")
        if not feedback_enabled and not source_step_ids:
            feedback_ok = False
            reasons.append("disabled implicit live step missing candidate five phase source lineage")
        if projection and not source_step_ids:
            feedback_ok = False
            reasons.append("feedback projection missing source five phase live step ids")
        if projection and not set(source_step_ids).issubset(live_step_ids):
            feedback_ok = False
            reasons.append("feedback projection references missing FivePhase live step")
        source_record_ids = {str(value) for value in step.get("source_record_ids", [])}
        if projection and not set(source_step_ids).issubset(source_record_ids):
            feedback_ok = False
            reasons.append("feedback projection source step ids missing from implicit live source_record_ids")
        expected_source_steps = causal_steps_by_implicit_state.get(str(step.get("previous_state_id", "")), [])
        expected_source_ids = [str(record.get("live_step_id")) for record in expected_source_steps]
        if source_step_ids != expected_source_ids:
            feedback_ok = False
            reasons.append("Feedback must consume only the immediate predecessor canonical causal step")
        if application is not None:
            if application.get("schema") != "five_phase_feedback_application_record_v2":
                feedback_ok = False
                reasons.append("five phase feedback application must use v2 semantic record")
            if application.get("feedback_consumed") is not True:
                feedback_ok = False
                reasons.append("five phase feedback application must consume its immediate predecessor once")
            if application.get("is_authority_state") is not False:
                feedback_ok = False
                reasons.append("five phase feedback application must be non-authority")
            if not isinstance(application.get("feedback_enabled"), bool):
                feedback_ok = False
                reasons.append("five phase feedback application enabled flag must be a bool")
            elif bool(application.get("feedback_enabled")) != feedback_enabled:
                feedback_ok = False
                reasons.append("five phase feedback application enabled flag does not match session")
            if str(application.get("implicit_live_step_id")) != str(step.get("step_id")):
                feedback_ok = False
                reasons.append("five phase feedback application references wrong implicit live step")
            if str(application.get("previous_state_id")) != str(step.get("previous_state_id")) or str(
                application.get("result_state_id")
            ) != str(step.get("result_state_id")):
                feedback_ok = False
                reasons.append("five phase feedback application state transition does not match implicit step")
            if [str(value) for value in application.get("five_phase_live_step_ids", [])] != source_step_ids:
                feedback_ok = False
                reasons.append("five phase feedback application predecessor lineage does not match implicit step")
            expected_candidate_projection: dict[str, Any] = {}
            expected_feedback_ids: list[str] = []
            for source_step_id in source_step_ids:
                source_step = live_steps_by_id.get(source_step_id)
                if source_step is None:
                    continue
                expected_feedback_ids.extend(str(value) for value in source_step.get("feedback_record_ids", []))
                for basis_id, channels in dict(source_step.get("feedback_input_projection") or {}).items():
                    target = expected_candidate_projection.setdefault(str(basis_id), {})
                    for channel, value in dict(channels).items():
                        target[str(channel)] = float(target.get(str(channel), 0.0)) + float(value)
            if _canonical_digest(application.get("candidate_feedback_projection") or {}) != _canonical_digest(expected_candidate_projection):
                feedback_ok = False
                reasons.append("five phase feedback application candidate does not match predecessor Feedback records")
            if [str(value) for value in application.get("feedback_record_ids", [])] != expected_feedback_ids:
                feedback_ok = False
                reasons.append("five phase feedback application record IDs do not match predecessor causal step")

            local_scopes = {
                str(ledger.get("scope_id")): dict(ledger.get("kappa") or {})
                for ledger in step.get("energy_ledgers", [])
                if isinstance(ledger, Mapping) and ledger.get("scope_kind") == "local"
            }
            previous_state = implicit_states_by_id.get(str(step.get("previous_state_id", "")))
            expected_baseline_measurements: list[dict[str, Any]] = []
            expected_candidate_measurements: list[dict[str, Any]] = []
            expected_application = False
            expected_eligibility_reason = "no_candidate"
            expected_applied_projection: dict[str, Any] = {}
            try:
                if previous_state is None:
                    raise ValueError("missing previous implicit state")
                baseline_state = _retag_recomputed_implicit_state(
                    advance_implicit_field_state(
                        previous_state,
                        implicit_bases,
                        user_input_projection=step.get("raw_user_input_projection") or {},
                        feedback_input_projection={},
                        local_energy_scopes=local_scopes,
                    ),
                    state_id=str(step.get("result_state_id")),
                )
                candidate_state = _retag_recomputed_implicit_state(
                    advance_implicit_field_state(
                        previous_state,
                        implicit_bases,
                        user_input_projection=step.get("raw_user_input_projection") or {},
                        feedback_input_projection=expected_candidate_projection,
                        local_energy_scopes=local_scopes,
                    ),
                    state_id=str(step.get("result_state_id")),
                )
                for feedback_id in sorted(expected_feedback_ids):
                    feedback_record = next((record for record in feedbacks if record.record_id == feedback_id), None)
                    if feedback_record is None:
                        raise ValueError("missing predecessor Feedback record")
                    pattern = patterns_by_id.get(feedback_record.pattern_id)
                    agent = agents_by_id.get(feedback_record.agent_state_id)
                    if pattern is None or agent is None:
                        raise ValueError("missing predecessor Pattern or Agent")
                    expected_baseline_measurements.append(
                        measure_five_phase_feedback_response(
                            implicit_field_state=baseline_state,
                            implicit_basis_records=implicit_bases,
                            basis_spatial_index=basis_spatial_index,
                            pattern=pattern,
                            agent_state=agent,
                            feedback=feedback_record,
                        )
                    )
                    expected_candidate_measurements.append(
                        measure_five_phase_feedback_response(
                            implicit_field_state=candidate_state,
                            implicit_basis_records=implicit_bases,
                            basis_spatial_index=basis_spatial_index,
                            pattern=pattern,
                            agent_state=agent,
                            feedback=feedback_record,
                        )
                    )
                if expected_feedback_ids:
                    directions_eligible = all(
                        bool(measurement.get("candidate_direction_eligible"))
                        for measurement in expected_baseline_measurements
                    )
                    errors_improve = all(
                        float(candidate.get("absolute_error", math.inf))
                        < float(baseline.get("absolute_error", -math.inf)) - 1e-12
                        for baseline, candidate in zip(expected_baseline_measurements, expected_candidate_measurements)
                    )
                    if not directions_eligible:
                        expected_eligibility_reason = "application_direction_ineligible"
                    elif not errors_improve:
                        expected_eligibility_reason = "application_error_not_reduced"
                    elif not feedback_enabled:
                        expected_eligibility_reason = "feedback_disabled_baseline"
                    else:
                        expected_eligibility_reason = "eligible_error_reduction"
                        expected_application = True
                        expected_applied_projection = dict(
                            candidate_state.get("energy_summary", {})
                            .get("density_response", {})
                            .get("realized_feedback_projection", {})
                        )
            except (KeyError, TypeError, ValueError) as exc:
                feedback_ok = False
                reasons.append(f"five phase feedback application recomputation failed: {exc}")
            else:
                if _canonical_digest(application.get("baseline_response_measurements") or []) != _canonical_digest(expected_baseline_measurements):
                    feedback_ok = False
                    reasons.append("five phase feedback baseline response measurements mismatch")
                if _canonical_digest(application.get("candidate_response_measurements") or []) != _canonical_digest(expected_candidate_measurements):
                    feedback_ok = False
                    reasons.append("five phase feedback candidate response measurements mismatch")
                if application.get("eligibility_reason") != expected_eligibility_reason:
                    feedback_ok = False
                    reasons.append("five phase feedback eligibility reason does not match recomputation")
                if application.get("feedback_applied") is not expected_application:
                    feedback_ok = False
                    reasons.append("five phase feedback applied status does not match response reduction")
                if _canonical_digest(application.get("applied_feedback_projection") or {}) != _canonical_digest(expected_applied_projection):
                    feedback_ok = False
                    reasons.append("five phase feedback applied projection does not match recomputation")
            if str(application.get("merged_input_projection_digest")) != str(step.get("merged_input_projection_digest", step.get("input_projection_digest"))):
                feedback_ok = False
                reasons.append("feedback application merged projection digest does not match implicit step")
            if dict(application.get("applied_feedback_projection") or {}) != dict(projection):
                feedback_ok = False
                reasons.append("five phase feedback application applied projection does not match implicit step")
            if str(application.get("candidate_feedback_projection_digest")) != _canonical_digest(application.get("candidate_feedback_projection") or {}):
                feedback_ok = False
                reasons.append("five phase feedback application candidate projection digest mismatch")
            if str(application.get("applied_feedback_projection_digest")) != _canonical_digest(application.get("applied_feedback_projection") or {}):
                feedback_ok = False
                reasons.append("five phase feedback application applied projection digest mismatch")
            if application.get("feedback_applied") is True:
                if not feedback_enabled:
                    feedback_ok = False
                    reasons.append("disabled five phase feedback application cannot be applied")
                if not application.get("applied_feedback_projection"):
                    feedback_ok = False
                    reasons.append("applied five phase feedback application missing projection")
            else:
                if application.get("feedback_applied") is not False:
                    feedback_ok = False
                    reasons.append("five phase feedback application applied flag must be a bool")
                if application.get("applied_feedback_projection"):
                    feedback_ok = False
                    reasons.append("ineligible five phase feedback application leaked applied projection")

    if len(consumed_source_step_ids) != len(set(consumed_source_step_ids)):
        feedback_ok = False
        reasons.append("FivePhase causal Feedback source step was consumed more than once")

    energy_failures = implicit_live_energy_ledger_failures(exported)
    energy_ok = not energy_failures
    reasons.extend(
        f"implicit energy ledger completion failed: {failure.get('reason')} ({failure.get('step_id', 'unknown')})"
        for failure in energy_failures[:20]
    )

    overall = authority_ok and frame_ok and feedback_ok and energy_ok
    return {
        "schema": "five_phase_live_completion_v1",
        "overall_status": "passed" if overall else "failed",
        "authority_lineage_status": "passed" if authority_ok else "failed",
        "frame_payload_status": "passed" if frame_ok else "failed",
        "feedback_runtime_binding_status": "passed" if feedback_ok else "failed",
        "energy_ledger_status": "passed" if energy_ok else "failed",
        "verified_feedback_application_ids": owned_application_ids if feedback_ok else [],
        "reasons": reasons,
    }


__all__ = ["evaluate_five_phase_live_completion"]
