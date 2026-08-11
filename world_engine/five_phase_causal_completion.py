from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from world_engine.five_phase_causal import (
    DEFAULT_ARTIFACT_BUDGET_BYTES,
    DEFAULT_ENERGY_RUNAWAY_ABS_MAX,
    DEFAULT_ENERGY_RUNAWAY_RATIO_MAX,
    DEFAULT_MIN_DIRECTIONAL_ALIGNMENT,
    DEFAULT_MIN_QUALITY_IMPROVEMENT,
    DEFAULT_MIN_READBACK_DIVERGENCE,
    build_causal_tick_metrics,
    build_feedback_effect_probe_records,
    canonical_digest,
    canonical_json_bytes,
    counterfactual_perturbation_stability_failures,
    jsonable,
    mean_feedback_distance,
    mean_pattern_stability,
)
from world_engine.five_phase_live import reject_five_phase_live_shortcuts
from world_engine.five_phase_live_completion import evaluate_five_phase_live_completion
from world_engine.implicit_field import (
    build_basis_spatial_index,
    validate_implicit_field_basis,
    validate_implicit_field_state,
)
from world_engine.implicit_field_runtime import advance_implicit_field_state
from world_engine.implicit_interaction import (
    build_implicit_pending_control_descriptor,
    materialize_implicit_raw_control_projection,
    target_basis_from_image_xy,
)


def _records(values: Any) -> list[dict[str, Any]]:
    result = []
    for value in values or []:
        converted = jsonable(value)
        if not isinstance(converted, Mapping):
            raise ValueError("expected mapping record")
        result.append(dict(converted))
    return result


def _records_or_fail(values: Any, *, label: str, reasons: list[str]) -> list[dict[str, Any]]:
    try:
        return _records(values)
    except Exception as exc:
        reasons.append(f"{label} read-back failed: {exc}")
        return []


def _same_digest(left: Any, right: Any) -> bool:
    return canonical_digest(left) == canonical_digest(right)


def _status(ok: bool) -> str:
    return "passed" if ok else "failed"


def _max_float(records: Sequence[Mapping[str, Any]], key: str) -> float:
    return max((float(record.get(key, 0.0)) for record in records), default=0.0)


def _max_application_error_improvement(applications: Sequence[Mapping[str, Any]]) -> float:
    improvements: list[float] = []
    for application in applications:
        if application.get("feedback_applied") is not True:
            continue
        baseline = application.get("baseline_response_measurements") or []
        candidate = application.get("candidate_response_measurements") or []
        if not isinstance(baseline, Sequence) or isinstance(baseline, (str, bytes)):
            continue
        if not isinstance(candidate, Sequence) or isinstance(candidate, (str, bytes)):
            continue
        for before, after in zip(baseline, candidate):
            if not isinstance(before, Mapping) or not isinstance(after, Mapping):
                continue
            before_error = float(before.get("absolute_error", math.inf))
            after_error = float(after.get("absolute_error", math.inf))
            if math.isfinite(before_error) and math.isfinite(after_error):
                improvements.append(before_error - after_error)
    return max(improvements, default=0.0)


def _canonical_runtime_configuration_digest(
    exported: Mapping[str, Any],
    *,
    label: str,
    reasons: list[str],
) -> str:
    session = exported.get("session") or {}
    states = _records_or_fail(exported.get("implicit_field_states", []), label=f"{label} implicit states", reasons=reasons)
    frames = _records_or_fail(exported.get("projection_frames", []), label=f"{label} projection frames", reasons=reasons)
    rays = _records_or_fail(exported.get("implicit_ray_sample_records", []), label=f"{label} ray samples", reasons=reasons)
    observer_paths = _records_or_fail(
        exported.get("implicit_observer_path_records", []),
        label=f"{label} observer paths",
        reasons=reasons,
    )
    if not isinstance(session, Mapping) or not states or not frames or not rays or not observer_paths:
        reasons.append(f"{label} export lacks canonical runtime configuration evidence")
        return ""
    initial_state = states[0]
    initial_frame = frames[0]
    initial_ray = rays[0]
    initial_state_id = str(initial_state.get("implicit_field_state_id") or "")
    initial_tick = int(initial_state.get("tick", -1))
    if (
        not initial_state_id
        or int(initial_frame.get("tick", -2)) != initial_tick
        or initial_state_id not in {str(value) for value in initial_frame.get("source_record_ids", [])}
        or int(initial_ray.get("tick", -2)) != initial_tick
        or str(initial_ray.get("source_implicit_field_state_id") or "") != initial_state_id
    ):
        reasons.append(f"{label} initial observation configuration is not bound to canonical S0")
        return ""
    image_plane = initial_frame.get("image_plane") or {}
    image_shape = initial_ray.get("image_shape") or []
    if (
        not isinstance(image_plane, Mapping)
        or len(image_shape) != 2
        or [int(image_plane.get("width", 0)), int(image_plane.get("height", 0))]
        != [int(value) for value in image_shape]
    ):
        reasons.append(f"{label} initial projection and ray configuration mismatch")
        return ""
    configuration = {
        "session": {
            field_name: jsonable(session.get(field_name))
            for field_name in (
                "schema",
                "runtime_mode",
                "session_id",
                "run_id",
                "source_package_name",
                "source_package_digest",
                "observer_ids",
                "supported_tools",
            )
        },
        "initial_image_plane": image_plane,
        "initial_ray": {
            field_name: jsonable(initial_ray.get(field_name))
            for field_name in (
                "schema",
                "observer_id",
                "observer_path_id",
                "camera_pose",
                "image_shape",
                "samples_per_ray",
                "ray_march_config",
                "ray_geometry_digest",
                "ray_sample_points_digest",
            )
        },
        "initial_observer_path": observer_paths[0],
    }
    return canonical_digest(configuration)


def _canonical_state_chain_evidence(
    exported: Mapping[str, Any],
    *,
    label: str,
    reasons: list[str],
) -> dict[str, Any]:
    ok = True
    bases = _records_or_fail(exported.get("implicit_basis_records", []), label=f"{label} implicit bases", reasons=reasons)
    states = _records_or_fail(exported.get("implicit_field_states", []), label=f"{label} implicit states", reasons=reasons)
    steps = _records_or_fail(exported.get("implicit_live_step_records", []), label=f"{label} implicit steps", reasons=reasons)
    session = exported.get("session") or {}
    if not isinstance(session, Mapping) or not bases or not states or len(steps) != len(states) - 1:
        reasons.append(f"{label} export lacks a complete canonical state transition chain")
        ok = False

    basis_ids = [str(record.get("basis_id") or "") for record in bases]
    if any(not basis_id for basis_id in basis_ids) or len(basis_ids) != len(set(basis_ids)):
        reasons.append(f"{label} canonical basis IDs must be unique and non-empty")
        ok = False
    try:
        for basis in bases:
            validate_implicit_field_basis(basis)
        spatial_index_digest = str(build_basis_spatial_index(bases)["basis_spatial_index_digest"])
        layout_payload = [
            {
                field_name: basis[field_name]
                for field_name in (
                    "basis_id",
                    "basis_kind",
                    "basis_profile",
                    "center_world_3d",
                    "basis_axes",
                    "radius_world",
                    "coordinate_frame_3d",
                    "support_region_world",
                )
            }
            for basis in sorted(bases, key=lambda record: str(record.get("basis_id") or ""))
        ]
        layout_digest = canonical_digest(layout_payload)
    except (KeyError, TypeError, ValueError) as exc:
        reasons.append(f"{label} canonical basis/layout recomputation failed: {exc}")
        spatial_index_digest = ""
        layout_digest = ""
        ok = False

    state_ids: list[str] = []
    for state in states:
        try:
            validate_implicit_field_state(state)
        except (KeyError, TypeError, ValueError) as exc:
            reasons.append(f"{label} canonical state digest validation failed: {exc}")
            ok = False
        state_id = str(state.get("implicit_field_state_id") or "")
        state_ids.append(state_id)
        if (
            list(state.get("basis_ids") or []) != basis_ids
            or str(state.get("basis_spatial_index_digest") or "") != spatial_index_digest
            or str(state.get("basis_layout_digest") or "") != layout_digest
        ):
            reasons.append(f"{label} canonical state basis/layout lineage mismatch")
            ok = False
    if any(not state_id for state_id in state_ids) or len(state_ids) != len(set(state_ids)):
        reasons.append(f"{label} canonical state IDs must be unique and non-empty")
        ok = False

    step_ids: list[str] = []
    for index, step in enumerate(steps):
        step_id = str(step.get("step_id") or "")
        step_ids.append(step_id)
        previous_state = states[index] if index < len(states) else {}
        result_state = states[index + 1] if index + 1 < len(states) else {}
        if (
            step.get("schema") != "implicit_live_step_record"
            or str(step.get("previous_state_id") or "") != str(previous_state.get("implicit_field_state_id") or "")
            or str(step.get("result_state_id") or "") != str(result_state.get("implicit_field_state_id") or "")
            or str(step.get("previous_state_digest") or "") != str(previous_state.get("state_digest") or "")
            or str(step.get("result_state_digest") or "") != str(result_state.get("state_digest") or "")
            or int(result_state.get("tick", -1)) != int(previous_state.get("tick", -2)) + 1
            or int(step.get("tick", -1)) != int(result_state.get("tick", -2))
        ):
            reasons.append(f"{label} canonical branch does not form an ordered S0 transition chain")
            ok = False
            break
    if any(not step_id for step_id in step_ids) or len(step_ids) != len(set(step_ids)):
        reasons.append(f"{label} canonical step IDs must be unique and non-empty")
        ok = False
    if states and isinstance(session, Mapping):
        if (
            int(session.get("implicit_field_state_count", -1)) != len(states)
            or int(session.get("implicit_live_step_count", -1)) != len(steps)
            or int(session.get("current_tick", -1)) != int(states[-1].get("tick", -2))
        ):
            reasons.append(f"{label} canonical session counts do not match state read-back")
            ok = False
        feedback_enabled = session.get("five_phase_feedback_enabled")
        if not isinstance(feedback_enabled, bool) or any(
            step.get("five_phase_feedback_enabled") is not feedback_enabled for step in steps
        ):
            reasons.append(f"{label} canonical steps do not match session feedback mode")
            ok = False

    initial_state = states[0] if states else {}
    return {
        "ok": ok,
        "basis_digest": canonical_digest(sorted(bases, key=lambda record: str(record.get("basis_id") or ""))),
        "basis_layout_digest": layout_digest,
        "basis_spatial_index_digest": spatial_index_digest,
        "initial_state_id": str(initial_state.get("implicit_field_state_id") or ""),
        "initial_state_digest": str(initial_state.get("state_digest") or ""),
        "step_count": len(steps),
    }


def _canonical_interaction_evidence(
    exported: Mapping[str, Any],
    *,
    label: str,
    reasons: list[str],
) -> dict[str, Any]:
    transcripts = _records_or_fail(
        exported.get("implicit_interaction_transcript", []),
        label=f"{label} interaction transcript",
        reasons=reasons,
    )
    audits = _records_or_fail(
        exported.get("implicit_interaction_audits", []),
        label=f"{label} interaction audits",
        reasons=reasons,
    )
    steps = _records_or_fail(
        exported.get("implicit_live_step_records", []),
        label=f"{label} implicit steps",
        reasons=reasons,
    )
    states = _records_or_fail(
        exported.get("implicit_field_states", []),
        label=f"{label} implicit states",
        reasons=reasons,
    )
    frames = _records_or_fail(
        exported.get("projection_frames", []),
        label=f"{label} projection frames",
        reasons=reasons,
    )
    rays = _records_or_fail(
        exported.get("implicit_ray_sample_records", []),
        label=f"{label} ray samples",
        reasons=reasons,
    )
    ok = bool(transcripts and audits and steps and states and frames and rays)
    if not ok:
        reasons.append(f"{label} export lacks canonical interaction-to-step evidence")

    audits_by_id = {str(record.get("audit_id") or ""): record for record in audits}
    audit_ids = [str(record.get("audit_id") or "") for record in audits]
    audit_command_ids = [str(record.get("command_id") or "") for record in audits]
    audit_request_ids = [str(record.get("request_id") or "") for record in audits]
    frame_by_id = {str(record.get("frame_id") or ""): record for record in frames}
    ray_by_id = {str(record.get("ray_sample_record_id") or ""): record for record in rays}
    state_ids = {str(record.get("implicit_field_state_id") or "") for record in states}
    if any(not audit_id for audit_id in audit_ids) or len(audit_ids) != len(set(audit_ids)):
        reasons.append(f"{label} interaction audit IDs must be unique and non-empty")
        ok = False
    if (
        any(not command_id for command_id in audit_command_ids)
        or len(audit_command_ids) != len(set(audit_command_ids))
        or any(not request_id for request_id in audit_request_ids)
        or len(audit_request_ids) != len(set(audit_request_ids))
    ):
        reasons.append(f"{label} interaction command/request IDs must be unique and non-empty")
        ok = False

    transcript_audit_ids: list[str] = []
    transcript_sequences: list[int] = []
    request_schedule: list[dict[str, Any]] = []
    audit_schedule: list[dict[str, Any]] = []
    applications_by_tick: dict[int, list[dict[str, Any]]] = {}
    try:
        step_lineage_by_command: dict[str, list[dict[str, Any]]] = {}
        for step in steps:
            for lineage in _records(step.get("pending_control_lineage", [])):
                step_lineage_by_command.setdefault(str(lineage.get("command_id") or ""), []).append(
                    {"tick": int(step.get("tick", -1)), **lineage}
                )
        for entry in transcripts:
            request = entry.get("request")
            audit_id = str(entry.get("audit_id") or "")
            sequence = int(entry.get("accepted_sequence", -1))
            audit = audits_by_id.get(audit_id)
            if (
                entry.get("schema") != "implicit_interaction_transcript_entry_v1"
                or not isinstance(request, Mapping)
                or audit is None
                or request.get("advance_after_accept") is not False
            ):
                raise ValueError("transcript entry lacks its canonical request/audit binding")
            transcript_audit_ids.append(audit_id)
            transcript_sequences.append(sequence)
            request_id = str(request.get("request_id") or "")
            source_frame_id = str(request.get("source_projection_frame_id") or "")
            source_state_id = str(request.get("source_state_id") or "")
            source_ray_id = str(request.get("source_ray_sample_record_id") or "")
            source_tick = int(request.get("source_frame_tick", -1))
            source_frame = frame_by_id.get(source_frame_id)
            source_ray = ray_by_id.get(source_ray_id)
            if (
                not request_id
                or source_state_id not in state_ids
                or source_frame is None
                or int(source_frame.get("tick", -2)) != source_tick
                or source_state_id not in {str(value) for value in source_frame.get("source_record_ids", [])}
                or source_ray is None
                or int(source_ray.get("tick", -2)) != source_tick
                or str(source_ray.get("source_implicit_field_state_id") or "") != source_state_id
            ):
                raise ValueError("interaction request source frame/state/ray lineage mismatch")
            if (
                str(audit.get("request_id") or "") != request_id
                or int(audit.get("accepted_sequence", -2)) != sequence
                or str(audit.get("tool") or "") != str(request.get("tool") or "")
                or str(audit.get("source_projection_frame_id") or "") != source_frame_id
                or int(audit.get("source_frame_tick", -2)) != source_tick
                or str(audit.get("source_state_id") or "") != source_state_id
                or str(audit.get("source_ray_sample_record_id") or "") != source_ray_id
                or canonical_digest(audit.get("source_image_xy")) != canonical_digest(request.get("source_image_xy"))
                or not math.isclose(float(audit.get("radius_world")), float(request.get("radius_world")), rel_tol=0.0, abs_tol=1e-12)
                or not math.isclose(float(audit.get("amplitude_magnitude")), float(request.get("amplitude")), rel_tol=0.0, abs_tol=1e-12)
                or not math.isclose(float(audit.get("duration_ticks")), float(request.get("duration_ticks")), rel_tol=0.0, abs_tol=1e-12)
            ):
                raise ValueError("interaction transcript request does not match canonical audit")
            request_schedule.append(
                {
                    "event_id": request_id,
                    "apply_tick": source_tick,
                    "tool": str(request.get("tool") or ""),
                    "source_image_xy": jsonable(request.get("source_image_xy")),
                    "radius_world": float(request.get("radius_world")),
                    "amplitude": float(request.get("amplitude")),
                    "duration_ticks": float(request.get("duration_ticks")),
                    "source_vector_image": jsonable(request.get("source_vector_image")),
                }
            )

            applications = _records(audit.get("applications", []))
            schedule_weights = [float(value) for value in audit.get("schedule_weights", [])]
            schedule_applications = []
            for application in applications:
                application_tick = int(application.get("tick", -1))
                application_index = int(application.get("schedule_index", -1))
                if (
                    application_index < 0
                    or application_index >= len(schedule_weights)
                    or not math.isclose(
                        float(application.get("schedule_weight")),
                        schedule_weights[application_index],
                        rel_tol=0.0,
                        abs_tol=1e-12,
                    )
                ):
                    raise ValueError("interaction audit application order/weight mismatch")
                schedule_application = {
                    "tick": application_tick,
                    "schedule_index": application_index,
                    "schedule_weight": schedule_weights[application_index],
                    "raw_input_projection": jsonable(application.get("raw_input_projection") or {}),
                }
                schedule_applications.append(schedule_application)
                applications_by_tick.setdefault(application_tick, []).append(
                    {
                        "accepted_sequence": sequence,
                        "command_id": str(audit.get("command_id") or ""),
                        "request_id": request_id,
                        **schedule_application,
                    }
                )
            if not schedule_applications:
                for lineage in step_lineage_by_command.get(str(audit.get("command_id") or ""), []):
                    schedule_index = int(lineage.get("schedule_index", -1))
                    if schedule_index < 0 or schedule_index >= len(schedule_weights):
                        raise ValueError("canonical step lineage has invalid interaction schedule index")
                    schedule_application = {
                        "tick": int(lineage["tick"]),
                        "schedule_index": schedule_index,
                        "schedule_weight": schedule_weights[schedule_index],
                        "raw_input_projection": {},
                    }
                    schedule_applications.append(schedule_application)
                    applications_by_tick.setdefault(int(lineage["tick"]), []).append(
                        {
                            "accepted_sequence": sequence,
                            "command_id": str(audit.get("command_id") or ""),
                            "request_id": request_id,
                            **schedule_application,
                        }
                    )
            if not schedule_applications:
                raise ValueError("interaction audit is not consumed by a canonical step")
            audit_schedule.append(
                {
                    "audit_id": audit_id,
                    "command_id": str(audit.get("command_id") or ""),
                    "request_id": request_id,
                    "accepted_sequence": sequence,
                    "start_tick": int(audit["start_tick"]) if audit.get("start_tick") is not None else None,
                    "schedule_weights": schedule_weights,
                    "applications": schedule_applications,
                    "raw_input_projection": jsonable(audit.get("raw_input_projection") or {}),
                    "target_basis_ids": [str(value) for value in audit.get("target_basis_ids", [])],
                    "target_world_3d": jsonable(audit.get("target_world_3d")),
                    "target_ray_id": str(audit.get("target_ray_id") or ""),
                }
            )

        if transcript_sequences != sorted(set(transcript_sequences)):
            raise ValueError("interaction transcript sequence is not strictly ordered")
        if transcript_sequences and transcript_sequences != list(
            range(transcript_sequences[0], transcript_sequences[0] + len(transcript_sequences))
        ):
            raise ValueError("interaction transcript sequence is not contiguous")
        if transcript_audit_ids != audit_ids:
            raise ValueError("interaction transcript/audit ownership is not one-to-one and ordered")

        step_ticks = {int(step.get("tick", -1)) for step in steps}
        if any(tick not in step_ticks for tick in applications_by_tick):
            raise ValueError("interaction audit application has no canonical step")
        step_schedule = []
        for step in steps:
            tick = int(step.get("tick", -1))
            expected_applications = sorted(
                applications_by_tick.get(tick, []),
                key=lambda item: (int(item["accepted_sequence"]), str(item["request_id"])),
            )
            expected_command_ids = [str(item["command_id"]) for item in expected_applications]
            expected_lineage = [
                {
                    "accepted_sequence": int(item["accepted_sequence"]),
                    "command_id": str(item["command_id"]),
                    "request_id": str(item["request_id"]),
                    "schedule_index": int(item["schedule_index"]),
                }
                for item in expected_applications
            ]
            actual_lineage = [
                {
                    "accepted_sequence": int(item.get("accepted_sequence", -1)),
                    "command_id": str(item.get("command_id") or ""),
                    "request_id": str(item.get("request_id") or ""),
                    "schedule_index": int(item.get("schedule_index", -1)),
                }
                for item in _records(step.get("pending_control_lineage", []))
            ]
            if (
                [str(value) for value in step.get("applied_command_ids", [])] != expected_command_ids
                or actual_lineage != expected_lineage
            ):
                raise ValueError("canonical step schedule does not match interaction audit applications")
            step_schedule.append(
                {
                    "step_id": str(step.get("step_id") or ""),
                    "tick": tick,
                    "previous_state_id": str(step.get("previous_state_id") or ""),
                    "result_state_id": str(step.get("result_state_id") or ""),
                    "raw_user_input_projection": jsonable(step.get("raw_user_input_projection") or {}),
                    "applied_command_ids": expected_command_ids,
                    "pending_control_lineage": actual_lineage,
                    "refinement_patch_ids": [str(value) for value in step.get("refinement_patch_ids", [])],
                }
            )
    except (KeyError, TypeError, ValueError) as exc:
        reasons.append(f"{label} canonical interaction schedule validation failed: {exc}")
        ok = False
        step_schedule = []

    return {
        "ok": ok,
        "transcript_digest": canonical_digest(transcripts),
        "audit_schedule_digest": canonical_digest(audit_schedule),
        "step_schedule_digest": canonical_digest(step_schedule),
        "request_schedule": request_schedule,
    }


def _manifest_matches_canonical_export(
    manifest: Mapping[str, Any],
    exported: Mapping[str, Any],
    *,
    branch_name: str,
    feedback_enabled: bool,
    step_count: int,
    schedule_digest: str,
    reasons: list[str],
) -> bool:
    session = exported.get("session") or {}
    if not isinstance(session, Mapping):
        reasons.append(f"{branch_name} manifest lacks canonical session read-back")
        return False
    try:
        export_digest = canonical_digest(exported)
        manifest_payload = dict(manifest)
        provided_manifest_digest = str(manifest_payload.pop("manifest_digest", ""))
        expected_source_ids = [
            str(manifest.get("initial_snapshot_digest") or ""),
            schedule_digest,
            export_digest,
        ]
        valid = (
            manifest.get("schema") == "five_phase_causal_run_manifest_v1"
            and str(manifest.get("branch_name") or "") == branch_name
            and str(manifest.get("run_id") or "") == str(session.get("run_id") or "")
            and str(manifest.get("source_package_name") or "")
            == str(session.get("source_package_name") or "")
            and str(manifest.get("source_package_digest") or "")
            == str(session.get("source_package_digest") or "")
            and int(manifest.get("ticks", -1)) == int(step_count)
            and manifest.get("feedback_enabled") is feedback_enabled
            and session.get("five_phase_feedback_enabled") is feedback_enabled
            and str(manifest.get("initial_snapshot_digest") or "")
            and str(manifest.get("perturbation_schedule_digest") or "") == schedule_digest
            and str(manifest.get("export_digest") or "") == export_digest
            and int(manifest.get("artifact_bytes", -1)) == canonical_json_bytes(exported)
            and int(manifest.get("artifact_budget_bytes", 0)) > 0
            and [str(value) for value in manifest.get("source_record_ids", [])] == expected_source_ids
            and manifest.get("is_authority_state") is False
            and provided_manifest_digest == canonical_digest(manifest_payload)
            and math.isclose(
                float(manifest.get("residual_distance_mean")),
                mean_feedback_distance(exported),
                rel_tol=1e-9,
                abs_tol=1e-12,
            )
            and math.isclose(
                float(manifest.get("pattern_stability_mean")),
                mean_pattern_stability(exported),
                rel_tol=1e-9,
                abs_tol=1e-12,
            )
        )
    except (KeyError, TypeError, ValueError) as exc:
        reasons.append(f"{branch_name} canonical manifest recomputation failed: {exc}")
        return False
    if not valid:
        reasons.append(f"{branch_name} manifest does not match canonical export read-back")
    return bool(valid)


def _counterfactual_transition_replay_failures(
    evidence: Mapping[str, Any],
    *,
    reference_export: Mapping[str, Any],
) -> list[str]:
    """Replay embedded Feedback-off branches instead of trusting their steps."""

    failures: list[str] = []
    try:
        bases = _records(evidence.get("implicit_basis_records", []))
        if not bases:
            raise ValueError("counterfactual replay requires implicit bases")
        for basis in bases:
            validate_implicit_field_basis(basis)
        reference_frames = {
            str(frame.get("frame_id", "")): frame
            for frame in _records(reference_export.get("projection_frames", []))
        }
        reference_rays = {
            str(ray.get("ray_sample_record_id", "")): ray
            for ray in _records(
                reference_export.get("implicit_ray_sample_records", [])
            )
        }
        reference_image_planes = {
            str(image_plane.get("ray_sample_record_id", "")): image_plane
            for image_plane in _records(
                reference_export.get("implicit_spectral_image_planes", [])
            )
        }
        reference_states = {
            str(state.get("implicit_field_state_id", "")): state
            for state in _records(reference_export.get("implicit_field_states", []))
        }
        reference_structures = _records(
            reference_export.get("implicit_observed_structure_records", [])
        )

        for branch_name in ("control_branch", "zero_branch"):
            branch = evidence.get(branch_name) or {}
            if not isinstance(branch, Mapping):
                raise ValueError(f"counterfactual {branch_name} must be a mapping")
            states = _records(branch.get("implicit_field_states", []))
            steps = _records(branch.get("implicit_live_steps", []))
            audits = _records(branch.get("interaction_audits", []))
            transcripts = _records(branch.get("interaction_transcript", []))
            if len(audits) != 1 or len(transcripts) != 1:
                raise ValueError(
                    f"counterfactual {branch_name} requires one transcript and audit"
                )
            audit = audits[0]
            request = transcripts[0].get("request") or {}
            if not isinstance(request, Mapping):
                raise ValueError(
                    f"counterfactual {branch_name} request must be a mapping"
                )
            source_frame_id = str(request.get("source_projection_frame_id", ""))
            source_state_id = str(request.get("source_state_id", ""))
            source_ray_id = str(request.get("source_ray_sample_record_id", ""))
            source_frame = reference_frames.get(source_frame_id)
            source_state = reference_states.get(source_state_id)
            source_ray = reference_rays.get(source_ray_id)
            source_image_plane = reference_image_planes.get(source_ray_id)
            if (
                source_frame is None
                or source_state is None
                or source_ray is None
                or source_image_plane is None
            ):
                raise ValueError(
                    f"counterfactual {branch_name} source frame/state/ray/image lineage is missing"
                )
            frame_payload = source_frame.get("payload") or {}
            frame_semantics = frame_payload.get("timeline_semantics") or {}
            frame_state_id = str(
                frame_semantics.get("source_world_state_id")
                or frame_payload.get("implicit_field_state_id")
                or ""
            )
            frame_ray_id = str(
                (frame_payload.get("implicit_ray_sample_record") or {}).get(
                    "ray_sample_record_id", ""
                )
            )
            if (
                int(source_frame.get("tick", -1))
                != int(request.get("source_frame_tick", -2))
                or int(source_ray.get("tick", -1))
                != int(request.get("source_frame_tick", -2))
                or str(source_frame.get("observer_id", ""))
                != str(request.get("observer_id", ""))
                or str(source_ray.get("observer_id", ""))
                != str(request.get("observer_id", ""))
                or int(source_image_plane.get("tick", -1))
                != int(request.get("source_frame_tick", -2))
                or str(source_image_plane.get("observer_id", ""))
                != str(request.get("observer_id", ""))
                or frame_state_id != source_state_id
                or frame_ray_id != source_ray_id
                or not states
                or not _same_digest(source_state, states[0])
                or source_state_id
                not in {str(value) for value in source_frame.get("source_record_ids", [])}
                or source_ray_id
                not in {str(value) for value in source_frame.get("source_record_ids", [])}
            ):
                failures.append(
                    f"counterfactual {branch_name} source frame/state/ray lineage mismatch"
                )
            target = target_basis_from_image_xy(
                request,
                current_state=source_state,
                bases=bases,
                ray_sample_record=source_ray,
                image_plane=source_image_plane,
                observed_structures=[
                    structure
                    for structure in reference_structures
                    if int(structure.get("state_tick", -1))
                    == int(request.get("source_frame_tick", -2))
                ],
            )
            target_fields = (
                "target_world_3d",
                "targeting_confidence",
                "target_ray_id",
                "target_ray_index",
                "target_ray_direction_world_3d",
                "target_hit_depth",
                "target_structure_id",
                "target_hit_source",
            )
            if any(
                not _same_digest(audit.get(field_name), target.get(field_name))
                for field_name in target_fields
            ):
                failures.append(
                    f"counterfactual {branch_name} target does not match canonical source ray"
                )
            applications = _records(audit.get("applications", []))
            if len(applications) != 1:
                raise ValueError(
                    f"counterfactual {branch_name} requires one audit application"
                )
            application = applications[0]
            application_tick = int(application.get("tick", -1))
            descriptor = build_implicit_pending_control_descriptor(
                request,
                target=target,
                bases=bases,
                accepted_sequence=int(audit.get("accepted_sequence", -1)),
                start_tick=int(audit.get("start_tick", -1)),
            )
            descriptor_fields = (
                "request_id",
                "command_id",
                "audit_id",
                "accepted_sequence",
                "source_projection_frame_id",
                "source_frame_tick",
                "source_state_id",
                "source_ray_sample_record_id",
                "tool",
                "amplitude_magnitude",
                "signed_amplitude",
                "target_world_3d",
                "target_basis_ids",
                "radius_world",
                "start_tick",
                "duration_ticks",
                "schedule_weights",
                "kappa_by_basis",
                "normalized_weights_by_basis",
            )
            if any(
                not _same_digest(audit.get(field_name), descriptor.get(field_name))
                for field_name in descriptor_fields
            ) or not _same_digest(
                audit.get("source_image_xy") or [],
                request.get("source_image_xy") or [],
            ):
                failures.append(
                    f"counterfactual {branch_name} audit descriptor does not match transcript"
                )
            schedule_index = int(application.get("schedule_index", -1))
            expected_raw_projection = materialize_implicit_raw_control_projection(
                descriptor,
                schedule_index=schedule_index,
            )
            if (
                application_tick
                != int(descriptor["start_tick"]) + schedule_index
                or not _same_digest(
                    application.get("schedule_weight"),
                    descriptor["schedule_weights"][schedule_index],
                )
                or not _same_digest(
                    application.get("raw_input_projection") or {},
                    expected_raw_projection,
                )
                or not _same_digest(
                    audit.get("raw_input_projection") or {},
                    expected_raw_projection,
                )
                or not _same_digest(
                    audit.get("realized_input_projection") or {},
                    application.get("realized_input_projection") or {},
                )
                or not _same_digest(
                    audit.get("input_projection") or {},
                    application.get("realized_input_projection") or {},
                )
            ):
                failures.append(
                    f"counterfactual {branch_name} materialized control projection mismatch"
                )
            state_by_id = {
                str(state.get("implicit_field_state_id", "")): state
                for state in states
            }
            if len(state_by_id) != len(states):
                raise ValueError(
                    f"counterfactual {branch_name} state IDs must be unique"
                )

            for step in steps:
                step_id = str(step.get("step_id", ""))
                previous_state = state_by_id.get(str(step.get("previous_state_id", "")))
                result_state = state_by_id.get(str(step.get("result_state_id", "")))
                if previous_state is None or result_state is None:
                    failures.append(
                        f"counterfactual {branch_name} transition state lineage is missing"
                    )
                    continue

                is_application_step = int(step.get("tick", -1)) == application_tick
                if is_application_step:
                    expected_lineage = {
                        "accepted_sequence": int(audit.get("accepted_sequence", -1)),
                        "command_id": str(audit.get("command_id", "")),
                        "request_id": str(audit.get("request_id", "")),
                        "schedule_index": int(application.get("schedule_index", -1)),
                        "scope_id": (
                            f"implicit-energy-scope::{audit.get('command_id', '')}"
                        ),
                    }
                    if (
                        not _same_digest(
                            step.get("pending_control_lineage") or [],
                            [expected_lineage],
                        )
                        or [str(value) for value in step.get("applied_command_ids", [])]
                        != [str(audit.get("command_id", ""))]
                        or not _same_digest(
                            step.get("raw_user_input_projection") or {},
                            application.get("raw_input_projection") or {},
                        )
                        or not _same_digest(
                            step.get("realized_user_input_projection") or {},
                            application.get("realized_input_projection") or {},
                        )
                        or str(audit.get("result_state_id", ""))
                        != str(result_state.get("implicit_field_state_id", ""))
                    ):
                        failures.append(
                            f"counterfactual {branch_name} audit-to-step application mismatch"
                        )
                elif (
                    step.get("pending_control_lineage")
                    or step.get("applied_command_ids")
                    or step.get("raw_user_input_projection")
                    or step.get("realized_user_input_projection")
                ):
                    failures.append(
                        f"counterfactual {branch_name} has USER input outside t_off"
                    )

                ledgers = _records(step.get("energy_ledgers", []))
                local_energy_scopes: dict[str, dict[str, float]] = {}
                for ledger in ledgers:
                    if str(ledger.get("scope_kind", "")) != "local":
                        continue
                    scope_id = str(ledger.get("scope_id", ""))
                    if not scope_id or scope_id in local_energy_scopes:
                        raise ValueError(
                            f"counterfactual {branch_name} local scope IDs must be unique"
                        )
                    local_energy_scopes[scope_id] = {
                        str(basis_id): float(value)
                        for basis_id, value in (ledger.get("kappa") or {}).items()
                    }
                recomputed_state = advance_implicit_field_state(
                    previous_state,
                    bases,
                    user_input_projection=step.get("raw_user_input_projection") or {},
                    feedback_input_projection=(
                        step.get("raw_five_phase_feedback_input_projection") or {}
                    ),
                    local_energy_scopes=local_energy_scopes,
                )
                recomputed_response = (
                    recomputed_state.get("energy_summary", {})
                    .get("density_response", {})
                )
                comparisons = (
                    (
                        "result coefficients",
                        result_state.get("basis_coefficients") or {},
                        recomputed_state.get("basis_coefficients") or {},
                    ),
                    (
                        "result energy summary",
                        result_state.get("energy_summary") or {},
                        recomputed_state.get("energy_summary") or {},
                    ),
                    (
                        "result runtime cost",
                        result_state.get("runtime_cost_summary") or {},
                        recomputed_state.get("runtime_cost_summary") or {},
                    ),
                    (
                        "step runtime cost",
                        step.get("runtime_cost_summary") or {},
                        recomputed_state.get("runtime_cost_summary") or {},
                    ),
                    (
                        "realized USER projection",
                        step.get("realized_user_input_projection") or {},
                        recomputed_response.get("realized_user_projection") or {},
                    ),
                    (
                        "realized Feedback projection",
                        step.get("realized_five_phase_feedback_input_projection") or {},
                        recomputed_response.get("realized_feedback_projection") or {},
                    ),
                    (
                        "merged realized projection",
                        step.get("merged_realized_input_projection") or {},
                        recomputed_response.get("merged_realized_projection") or {},
                    ),
                    (
                        "energy ledgers",
                        ledgers,
                        recomputed_response.get("ledgers") or [],
                    ),
                )
                for label, actual, expected in comparisons:
                    if not _same_digest(actual, expected):
                        failures.append(
                            f"counterfactual {branch_name} {step_id} {label} replay mismatch"
                        )
                expected_merged = step.get("merged_realized_input_projection") or {}
                expected_user = step.get("realized_user_input_projection") or {}
                for field_name, expected_value in (
                    ("input_projection_digest", expected_merged),
                    ("merged_input_projection_digest", expected_merged),
                    ("user_input_projection_digest", expected_user),
                ):
                    if str(step.get(field_name, "")) != canonical_digest(expected_value):
                        failures.append(
                            f"counterfactual {branch_name} {step_id} {field_name} mismatch"
                        )
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        failures.append(f"counterfactual transition replay failed: {exc}")
    return failures


def evaluate_five_phase_causal_completion(bundle: Mapping[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    try:
        reject_five_phase_live_shortcuts(jsonable(bundle), path="five_phase_causal_bundle")
    except ValueError as exc:
        reasons.append(str(exc))

    enabled_export = bundle.get("enabled_export") or {}
    disabled_export = bundle.get("disabled_export") or {}
    if not isinstance(enabled_export, Mapping) or not isinstance(disabled_export, Mapping):
        reasons.append("causal completion requires enabled_export and disabled_export")
        enabled_export = {}
        disabled_export = {}

    enabled_live = evaluate_five_phase_live_completion(enabled_export)
    disabled_live = evaluate_five_phase_live_completion(disabled_export)
    live_completion_ok = enabled_live["overall_status"] == "passed" and disabled_live["overall_status"] == "passed"
    if not live_completion_ok:
        reasons.append("enabled or disabled live completion failed")

    enabled_manifest = dict(bundle.get("enabled_manifest") or {})
    disabled_manifest = dict(bundle.get("disabled_manifest") or {})
    enabled_session = enabled_export.get("session") or {}
    disabled_session = disabled_export.get("session") or {}
    if not isinstance(enabled_session, Mapping) or not isinstance(disabled_session, Mapping):
        reasons.append("causal exports require canonical session manifests")
        enabled_session = {}
        disabled_session = {}
    schedule = dict(bundle.get("perturbation_schedule") or {})
    comparison = dict(bundle.get("comparison") or {})
    provided_metrics = _records_or_fail(bundle.get("tick_metrics", []), label="causal tick metrics", reasons=reasons)
    provided_probes = _records_or_fail(bundle.get("feedback_effect_probes", []), label="feedback effect probes", reasons=reasons)

    enabled_configuration_digest = _canonical_runtime_configuration_digest(
        enabled_export,
        label="enabled",
        reasons=reasons,
    )
    disabled_configuration_digest = _canonical_runtime_configuration_digest(
        disabled_export,
        label="disabled",
        reasons=reasons,
    )
    enabled_chain = _canonical_state_chain_evidence(enabled_export, label="enabled", reasons=reasons)
    disabled_chain = _canonical_state_chain_evidence(disabled_export, label="disabled", reasons=reasons)
    enabled_interactions = _canonical_interaction_evidence(enabled_export, label="enabled", reasons=reasons)
    disabled_interactions = _canonical_interaction_evidence(disabled_export, label="disabled", reasons=reasons)

    schedule_canonical_ok = True
    schedule_events = _records_or_fail(
        schedule.get("events", []),
        label="perturbation schedule events",
        reasons=reasons,
    )
    try:
        schedule_payload = dict(schedule)
        provided_schedule_digest = str(schedule_payload.pop("schedule_digest", ""))
        recomputed_schedule_digest = canonical_digest(schedule_payload)
        event_ids = [str(event.get("event_id") or "") for event in schedule_events]
        normalized_schedule = [
            {
                "event_id": str(event.get("event_id") or ""),
                "apply_tick": int(event.get("apply_tick", -1)),
                "tool": str(event.get("tool") or ""),
                "source_image_xy": jsonable(event.get("source_image_xy")),
                "radius_world": float(event.get("radius_world")),
                "amplitude": float(event.get("amplitude")),
                "duration_ticks": float(event.get("duration_ticks")),
                "source_vector_image": jsonable(event.get("source_vector_image")),
            }
            for event in schedule_events
        ]
        if (
            schedule.get("schema") != "five_phase_perturbation_schedule_v1"
            or not provided_schedule_digest
            or provided_schedule_digest != recomputed_schedule_digest
            or str(schedule.get("run_id") or "") != str(bundle.get("run_id") or "")
            or any(not event_id for event_id in event_ids)
            or len(event_ids) != len(set(event_ids))
            or [str(value) for value in schedule.get("source_record_ids", [])] != event_ids
            or schedule.get("is_authority_state") is not False
            or int(schedule.get("ticks", -1)) != int(enabled_chain["step_count"])
            or int(schedule.get("ticks", -1)) != int(disabled_chain["step_count"])
            or not _same_digest(normalized_schedule, enabled_interactions["request_schedule"])
            or not _same_digest(normalized_schedule, disabled_interactions["request_schedule"])
        ):
            schedule_canonical_ok = False
            reasons.append("perturbation schedule does not match canonical branch transcripts")
    except (KeyError, TypeError, ValueError) as exc:
        schedule_canonical_ok = False
        recomputed_schedule_digest = ""
        reasons.append(f"perturbation schedule canonical recomputation failed: {exc}")

    enabled_manifest_ok = _manifest_matches_canonical_export(
        enabled_manifest,
        enabled_export,
        branch_name="enabled",
        feedback_enabled=True,
        step_count=int(enabled_chain["step_count"]),
        schedule_digest=recomputed_schedule_digest,
        reasons=reasons,
    )
    disabled_manifest_ok = _manifest_matches_canonical_export(
        disabled_manifest,
        disabled_export,
        branch_name="disabled",
        feedback_enabled=False,
        step_count=int(disabled_chain["step_count"]),
        schedule_digest=recomputed_schedule_digest,
        reasons=reasons,
    )

    counterfactual_ok = True
    counterfactual = bundle.get("counterfactual_perturbation_stability") or {}
    if not isinstance(counterfactual, Mapping) or not counterfactual:
        counterfactual_ok = False
        reasons.append("missing counterfactual perturbation stability evidence")
        counterfactual = {}
    else:
        counterfactual_failures = counterfactual_perturbation_stability_failures(counterfactual)
        if counterfactual_failures:
            counterfactual_ok = False
            reasons.extend(counterfactual_failures)
        transition_replay_failures = _counterfactual_transition_replay_failures(
            counterfactual,
            reference_export=enabled_export,
        )
        if transition_replay_failures:
            counterfactual_ok = False
            reasons.extend(transition_replay_failures)
        try:
            enabled_rays = _records(enabled_export.get("implicit_ray_sample_records", []))
            initial_ray = enabled_rays[0]
            trusted_configuration = {
                "session_id": str(enabled_session.get("session_id") or ""),
                "run_id": str(enabled_session.get("run_id") or ""),
                "source_package_name": str(enabled_session.get("source_package_name") or ""),
                "source_package_digest": str(enabled_session.get("source_package_digest") or ""),
                "image_shape": [int(value) for value in initial_ray.get("image_shape", [])],
                "samples_per_ray": int(initial_ray.get("samples_per_ray", 0)),
                "observer_ids": [str(value) for value in enabled_session.get("observer_ids", [])],
                "initial_camera_pose": jsonable(initial_ray.get("camera_pose") or {}),
            }
            enabled_bases = _records(enabled_export.get("implicit_basis_records", []))
            for branch_name in ("control_branch", "zero_branch"):
                branch = counterfactual.get(branch_name) or {}
                if not isinstance(branch, Mapping):
                    raise ValueError(f"counterfactual {branch_name} must be a mapping")
                for state in _records(branch.get("implicit_field_states", [])):
                    validate_implicit_field_state(state)
            if (
                str(counterfactual.get("run_id") or "") != str(bundle.get("run_id") or "")
                or not _same_digest(counterfactual.get("trusted_configuration") or {}, trusted_configuration)
                or str(counterfactual.get("trusted_configuration_digest") or "")
                != canonical_digest(trusted_configuration)
                or str(counterfactual.get("trusted_initial_snapshot_digest") or "")
                != str(enabled_manifest.get("initial_snapshot_digest") or "")
                or str(counterfactual.get("trusted_initial_snapshot_digest") or "")
                != str(disabled_manifest.get("initial_snapshot_digest") or "")
                or str(counterfactual.get("trusted_initial_state_id") or "")
                != str(enabled_chain["initial_state_id"])
                or str(counterfactual.get("trusted_initial_state_digest") or "")
                != str(enabled_chain["initial_state_digest"])
                or not _same_digest(counterfactual.get("implicit_basis_records") or [], enabled_bases)
            ):
                counterfactual_ok = False
                reasons.append("counterfactual evidence does not share the paired canonical S0/config/bases")
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            counterfactual_ok = False
            reasons.append(f"counterfactual paired-root recomputation failed: {exc}")

    paired_ok = True
    if not enabled_manifest or not disabled_manifest:
        paired_ok = False
        reasons.append("missing causal run manifest")
    if not enabled_manifest_ok or not disabled_manifest_ok:
        paired_ok = False
    if not schedule_canonical_ok:
        paired_ok = False
    if not enabled_configuration_digest or enabled_configuration_digest != disabled_configuration_digest:
        paired_ok = False
        reasons.append("paired canonical runtime configuration mismatch")
    if not enabled_chain["ok"] or not disabled_chain["ok"]:
        paired_ok = False
        reasons.append("paired branches require complete canonical state chains")
    for field_name in (
        "basis_digest",
        "basis_layout_digest",
        "basis_spatial_index_digest",
        "initial_state_id",
        "initial_state_digest",
    ):
        if not enabled_chain[field_name] or enabled_chain[field_name] != disabled_chain[field_name]:
            paired_ok = False
            reasons.append(f"paired canonical {field_name} mismatch")
    if not enabled_interactions["ok"] or not disabled_interactions["ok"]:
        paired_ok = False
        reasons.append("paired branches require canonical interaction-to-step evidence")
    for field_name in ("transcript_digest", "audit_schedule_digest", "step_schedule_digest"):
        if (
            not enabled_interactions[field_name]
            or enabled_interactions[field_name] != disabled_interactions[field_name]
        ):
            paired_ok = False
            reasons.append(f"paired canonical {field_name} mismatch")
    for field_name in ("run_id", "session_id", "source_package_name", "source_package_digest"):
        enabled_value = str(enabled_session.get(field_name) or "")
        disabled_value = str(disabled_session.get(field_name) or "")
        if not enabled_value or enabled_value != disabled_value:
            paired_ok = False
            reasons.append(f"paired canonical session {field_name} mismatch")
    for branch_name, session, manifest in (
        ("enabled", enabled_session, enabled_manifest),
        ("disabled", disabled_session, disabled_manifest),
    ):
        for field_name in ("run_id", "source_package_name", "source_package_digest"):
            if str(manifest.get(field_name) or "") != str(session.get(field_name) or ""):
                paired_ok = False
                reasons.append(f"{branch_name} manifest {field_name} does not match canonical session")
    if enabled_manifest.get("source_package_name") != disabled_manifest.get("source_package_name"):
        paired_ok = False
        reasons.append("paired baseline source_package_name mismatch")
    if enabled_manifest.get("source_package_digest") != disabled_manifest.get("source_package_digest"):
        paired_ok = False
        reasons.append("paired baseline source_package_digest mismatch")
    if int(enabled_manifest.get("ticks", -1)) != int(disabled_manifest.get("ticks", -2)):
        paired_ok = False
        reasons.append("paired baseline tick count mismatch")
    if enabled_manifest.get("initial_snapshot_digest") != disabled_manifest.get("initial_snapshot_digest"):
        paired_ok = False
        reasons.append("paired baseline initial snapshot digest mismatch")
    if enabled_manifest.get("perturbation_schedule_digest") != disabled_manifest.get("perturbation_schedule_digest"):
        paired_ok = False
        reasons.append("paired baseline perturbation schedule digest mismatch")
    if enabled_manifest.get("perturbation_schedule_digest") != schedule.get("schedule_digest"):
        paired_ok = False
        reasons.append("run manifest does not cite perturbation schedule digest")
    if not schedule.get("events"):
        paired_ok = False
        reasons.append("perturbation schedule must be non-empty")
    if enabled_manifest.get("feedback_enabled") is not True or disabled_manifest.get("feedback_enabled") is not False:
        paired_ok = False
        reasons.append("paired baseline must compare enabled=true against disabled=false")

    feedback_ok = True
    enabled_apps = _records_or_fail(enabled_export.get("five_phase_feedback_applications", []), label="enabled feedback applications", reasons=reasons)
    disabled_apps = _records_or_fail(disabled_export.get("five_phase_feedback_applications", []), label="disabled feedback applications", reasons=reasons)
    enabled_apps_by_id = {
        str(record.get("application_record_id") or ""): record
        for record in enabled_apps
    }
    verified_enabled_apps = [
        enabled_apps_by_id[record_id]
        for record_id in enabled_live.get("verified_feedback_application_ids", [])
        if record_id in enabled_apps_by_id
    ]
    if not enabled_apps or not disabled_apps:
        feedback_ok = False
        reasons.append("missing five phase feedback application records")
    if not any(record.get("feedback_applied") is True and record.get("applied_feedback_projection") for record in enabled_apps):
        feedback_ok = False
        reasons.append("enabled branch never applied non-empty feedback projection")
    if any(record.get("feedback_applied") is True or record.get("applied_feedback_projection") for record in disabled_apps):
        feedback_ok = False
        reasons.append("disabled branch leaked feedback projection")
    enabled_steps = _records_or_fail(enabled_export.get("implicit_live_step_records", []), label="enabled implicit live steps", reasons=reasons)
    disabled_steps = _records_or_fail(disabled_export.get("implicit_live_step_records", []), label="disabled implicit live steps", reasons=reasons)
    if any(step.get("five_phase_feedback_input_projection") for step in disabled_steps):
        feedback_ok = False
        reasons.append("disabled implicit live step contains feedback projection")
    if not any(step.get("five_phase_feedback_input_projection") for step in enabled_steps):
        feedback_ok = False
        reasons.append("enabled implicit live step lacks feedback projection")

    recomputed_probes = build_feedback_effect_probe_records(
        run_id=str(bundle.get("run_id", "five-phase-causal")),
        enabled_export=enabled_export,
        disabled_export=disabled_export,
    )
    recomputed_metrics = build_causal_tick_metrics(
        run_id=str(bundle.get("run_id", "five-phase-causal")),
        enabled_export=enabled_export,
        disabled_export=disabled_export,
        probes=recomputed_probes,
    )
    lineage_ok = True
    if not provided_probes or not provided_metrics or not comparison:
        lineage_ok = False
        reasons.append("missing causal probe, tick metrics, or comparison records")
    if provided_probes and not _same_digest(provided_probes, recomputed_probes):
        lineage_ok = False
        reasons.append("feedback effect probes do not match read-back recomputation")
    if provided_metrics and not _same_digest(provided_metrics, recomputed_metrics):
        lineage_ok = False
        reasons.append("causal tick metrics do not match read-back recomputation")

    max_divergence = _max_float(recomputed_metrics, "readback_divergence_l2")
    divergence_ok = max_divergence >= DEFAULT_MIN_READBACK_DIVERGENCE
    if not divergence_ok:
        reasons.append("enabled and disabled read-back states did not diverge")

    max_alignment = _max_float(recomputed_probes, "isolated_feedback_alignment")
    direction_ok = bool(recomputed_probes) and max_alignment >= DEFAULT_MIN_DIRECTIONAL_ALIGNMENT
    if not direction_ok:
        reasons.append("feedback effect probe did not align with read-back state delta")

    comparison_ok = bool(comparison)
    if comparison:
        if not math.isclose(float(comparison.get("max_readback_divergence_l2", 0.0)), max_divergence, rel_tol=1e-9, abs_tol=1e-12):
            comparison_ok = False
            reasons.append("comparison max_readback_divergence_l2 mismatch")
        if not math.isclose(float(comparison.get("max_feedback_isolated_alignment", 0.0)), max_alignment, rel_tol=1e-9, abs_tol=1e-12):
            comparison_ok = False
            reasons.append("comparison max_feedback_isolated_alignment mismatch")
        residual_delta = float(enabled_manifest.get("residual_distance_mean", 0.0)) - float(disabled_manifest.get("residual_distance_mean", 0.0))
        pattern_stability_delta = float(enabled_manifest.get("pattern_stability_mean", 0.0)) - float(disabled_manifest.get("pattern_stability_mean", 0.0))
        if not math.isclose(float(comparison.get("residual_distance_delta", 0.0)), residual_delta, rel_tol=1e-9, abs_tol=1e-12):
            comparison_ok = False
            reasons.append("comparison residual_distance_delta mismatch")
        if not math.isclose(float(comparison.get("pattern_stability_delta", 0.0)), pattern_stability_delta, rel_tol=1e-9, abs_tol=1e-12):
            comparison_ok = False
            reasons.append("comparison pattern_stability_delta mismatch")
        if comparison.get("initial_snapshot_digest") != enabled_manifest.get("initial_snapshot_digest"):
            comparison_ok = False
            reasons.append("comparison initial snapshot digest mismatch")
        if comparison.get("perturbation_schedule_digest") != schedule.get("schedule_digest"):
            comparison_ok = False
            reasons.append("comparison perturbation schedule digest mismatch")

    residual_improvement = float(disabled_manifest.get("residual_distance_mean", 0.0)) - float(
        enabled_manifest.get("residual_distance_mean", 0.0)
    )
    pattern_stability_improvement = float(enabled_manifest.get("pattern_stability_mean", 0.0)) - float(
        disabled_manifest.get("pattern_stability_mean", 0.0)
    )
    max_application_error_improvement = _max_application_error_improvement(verified_enabled_apps)
    quality_ok = (
        max_application_error_improvement > 1e-12
        or residual_improvement >= DEFAULT_MIN_QUALITY_IMPROVEMENT
        or pattern_stability_improvement >= DEFAULT_MIN_QUALITY_IMPROVEMENT
    )
    if not quality_ok:
        reasons.append("no read-back causal quality metric improved")

    energy_ok = (
        enabled_live.get("energy_ledger_status") == "passed"
        and disabled_live.get("energy_ledger_status") == "passed"
    )
    if not energy_ok:
        reasons.append("enabled or disabled transition energy ledger failed")
    for record in recomputed_metrics:
        enabled_energy = float(record.get("enabled_energy", 0.0))
        disabled_energy = float(record.get("disabled_energy", 0.0))
        allowed = disabled_energy * DEFAULT_ENERGY_RUNAWAY_RATIO_MAX + DEFAULT_ENERGY_RUNAWAY_ABS_MAX
        if enabled_energy > allowed:
            energy_ok = False
            reasons.append("enabled branch energy exceeded feedback budget")
            break

    artifact_budget = int(bundle.get("artifact_budget_bytes", DEFAULT_ARTIFACT_BUDGET_BYTES))
    artifact_bytes = int(bundle.get("artifact_bytes_total", 0))
    artifact_paths = bundle.get("artifact_paths") or {}
    artifact_bytes_by_file = bundle.get("artifact_bytes_by_file") or {}
    artifact_payloads = {
        "enabled_export": enabled_export,
        "disabled_export": disabled_export,
        "enabled_manifest": enabled_manifest,
        "disabled_manifest": disabled_manifest,
        "perturbation_schedule": schedule,
        "tick_metrics": provided_metrics,
        "feedback_effect_probes": provided_probes,
        "comparison": comparison,
        "counterfactual_perturbation_stability": counterfactual,
    }
    artifact_readback_ok = True
    if not isinstance(artifact_paths, Mapping) or not artifact_paths:
        artifact_readback_ok = False
        reasons.append("five phase causal artifact read-back paths are missing")
    else:
        try:
            measured_by_file = {str(name): Path(str(path)).stat().st_size for name, path in artifact_paths.items()}
            measured_total = sum(measured_by_file.values())
            missing_artifact_names = sorted(set(artifact_payloads) - set(artifact_paths))
            if missing_artifact_names:
                artifact_readback_ok = False
                reasons.append(
                    "five phase causal artifact read-back paths are incomplete: "
                    + ", ".join(missing_artifact_names)
                )
            if (
                not isinstance(artifact_bytes_by_file, Mapping)
                or dict(artifact_bytes_by_file) != measured_by_file
            ):
                artifact_readback_ok = False
                reasons.append("five phase causal artifact per-file byte accounting mismatch")
            if artifact_bytes != measured_total:
                artifact_readback_ok = False
                reasons.append("five phase causal artifact total byte accounting mismatch")
            artifact_bytes = measured_total
            for artifact_name, expected_payload in artifact_payloads.items():
                artifact_path = artifact_paths.get(artifact_name)
                if not artifact_path:
                    continue
                persisted_payload = json.loads(
                    Path(str(artifact_path)).read_text(encoding="utf-8")
                )
                if not _same_digest(persisted_payload, expected_payload):
                    artifact_readback_ok = False
                    reasons.append(
                        f"{artifact_name} artifact read-back mismatch"
                    )
                    if artifact_name == "counterfactual_perturbation_stability":
                        counterfactual_ok = False
        except (OSError, UnicodeError, ValueError) as exc:
            artifact_readback_ok = False
            reasons.append(f"five phase causal artifact path read-back failed: {exc}")
    artifact_ok = (
        artifact_readback_ok
        and artifact_bytes > 0
        and artifact_bytes <= artifact_budget
    )
    if not artifact_ok:
        reasons.append("five phase causal artifact byte budget failed")

    viewer_ok = not any("shortcut" in reason for reason in reasons)

    overall = (
        live_completion_ok
        and paired_ok
        and counterfactual_ok
        and feedback_ok
        and lineage_ok
        and divergence_ok
        and direction_ok
        and quality_ok
        and comparison_ok
        and energy_ok
        and artifact_ok
        and viewer_ok
    )
    return {
        "schema": "five_phase_causal_completion_v1",
        "overall_status": _status(overall),
        "live_completion_status": _status(live_completion_ok),
        "paired_baseline_status": _status(paired_ok),
        "counterfactual_stability_status": _status(counterfactual_ok),
        "feedback_application_status": _status(feedback_ok),
        "lineage_status": _status(lineage_ok),
        "readback_divergence_status": _status(divergence_ok),
        "causal_direction_status": _status(direction_ok),
        "quality_improvement_status": _status(quality_ok),
        "comparison_status": _status(comparison_ok),
        "energy_budget_status": _status(energy_ok),
        "artifact_budget_status": _status(artifact_ok),
        "viewer_non_authority_status": _status(viewer_ok),
        "max_readback_divergence_l2": max_divergence,
        "max_feedback_isolated_alignment": max_alignment,
        "max_application_error_improvement": max_application_error_improvement,
        "residual_improvement": residual_improvement,
        "pattern_stability_improvement": pattern_stability_improvement,
        "enabled_live_completion": enabled_live,
        "disabled_live_completion": disabled_live,
        "reasons": reasons,
    }


__all__ = ["evaluate_five_phase_causal_completion"]
