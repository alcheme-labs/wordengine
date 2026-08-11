#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from world_engine.implicit_live_session import (  # noqa: E402
    DEFAULT_OBSERVER_ID,
    ImplicitFieldSession,
)


SCHEMA = "continuous_local_energy_response_validation_v1"
ABS_TOLERANCE = 1e-10
RESPONSE_TOLERANCE = 1e-12
DEFAULT_HORIZON_TICKS = 4
PASSIVE_CONTRACTION_RATE_CEILING = 0.98


def _density_coefficients(state: Mapping[str, Any]) -> dict[str, float]:
    return {
        str(basis_id): float(channels.get("density", 0.0))
        for basis_id, channels in sorted(state.get("basis_coefficients", {}).items())
    }


def _vector_delta(
    left: Mapping[str, float],
    right: Mapping[str, float],
) -> dict[str, float]:
    return {
        basis_id: float(left.get(basis_id, 0.0)) - float(right.get(basis_id, 0.0))
        for basis_id in sorted(set(left) | set(right))
    }


def _vector_l2(values: Mapping[str, float]) -> float:
    return math.sqrt(sum(float(value) ** 2 for value in values.values()))


def _vector_l1(values: Mapping[str, float]) -> float:
    return sum(abs(float(value)) for value in values.values())


def _vector_distance(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    return _vector_l2(_vector_delta(left, right))


def _vector_dot(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    return sum(
        float(left.get(basis_id, 0.0)) * float(right.get(basis_id, 0.0))
        for basis_id in set(left) | set(right)
    )


def _projection_density_sum(projection: Mapping[str, Mapping[str, Any]]) -> float:
    return sum(float(channels.get("density", 0.0)) for channels in projection.values())


def _projection_density_l1(projection: Mapping[str, Mapping[str, Any]]) -> float:
    return sum(abs(float(channels.get("density", 0.0))) for channels in projection.values())


def _projection_density_vector(
    projection: Mapping[str, Mapping[str, Any]],
) -> dict[str, float]:
    return {
        str(basis_id): float(channels.get("density", 0.0))
        for basis_id, channels in sorted(projection.items())
    }


def _latest_request_context(session: ImplicitFieldSession) -> dict[str, Any]:
    frame = session.projection_frame_dicts()[-1]
    payload = frame["payload"]
    state_id = str(
        payload.get("timeline_semantics", {}).get("source_world_state_id")
        or payload.get("implicit_field_state_id")
        or ""
    )
    ray_id = str(payload["implicit_ray_sample_record"]["ray_sample_record_id"])
    if not state_id or not ray_id:
        raise ValueError("latest public projection frame lacks interaction lineage")
    return {
        "source_projection_frame_id": str(frame["frame_id"]),
        "source_frame_tick": int(frame["tick"]),
        "source_state_id": state_id,
        "source_ray_sample_record_id": ray_id,
    }


def _interaction_request(
    session: ImplicitFieldSession,
    *,
    request_id: str,
    tool: str,
    amplitude: float,
    radius_world: float,
    duration_ticks: float,
) -> dict[str, Any]:
    return {
        "schema": "implicit_interaction_request",
        "request_id": request_id,
        "tool": tool,
        "observer_id": DEFAULT_OBSERVER_ID,
        **_latest_request_context(session),
        "source_image_xy": [0.5, 0.5],
        "radius_world": float(radius_world),
        "amplitude": float(amplitude),
        "duration_ticks": float(duration_ticks),
        "advance_after_accept": False,
    }


def _new_session(
    *,
    source_package_name: str,
    source_package_digest: str,
    run_id: str,
    image_shape: Sequence[int],
    samples_per_ray: int,
) -> ImplicitFieldSession:
    return ImplicitFieldSession.from_source_package(
        source_package_name=source_package_name,
        source_package_digest=source_package_digest,
        case_type="implicit_full_scene",
        run_id=run_id,
        image_shape=list(image_shape),
        samples_per_ray=int(samples_per_ray),
        five_phase_feedback_enabled=True,
    )


def _restore_branch(
    *,
    trusted_snapshot: Mapping[str, Any],
    source_package_name: str,
    source_package_digest: str,
    run_id: str,
    image_shape: Sequence[int],
    samples_per_ray: int,
    feedback_enabled: bool,
) -> ImplicitFieldSession:
    session = _new_session(
        source_package_name=source_package_name,
        source_package_digest=source_package_digest,
        run_id=run_id,
        image_shape=image_shape,
        samples_per_ray=samples_per_ray,
    )
    session.restore_snapshot(
        copy.deepcopy(trusted_snapshot),
        expected_snapshot_digest=str(trusted_snapshot["snapshot_digest"]),
        five_phase_feedback_enabled_override=bool(feedback_enabled),
    )
    return session


def _run_branch(
    *,
    branch_label: str,
    trusted_snapshot: Mapping[str, Any],
    source_package_name: str,
    source_package_digest: str,
    run_id: str,
    image_shape: Sequence[int],
    samples_per_ray: int,
    feedback_enabled: bool,
    request_id: str,
    tool: str,
    amplitude: float,
    radius_world: float,
    duration_ticks: float,
    horizon_ticks: int,
) -> dict[str, Any]:
    session = _restore_branch(
        trusted_snapshot=trusted_snapshot,
        source_package_name=source_package_name,
        source_package_digest=source_package_digest,
        run_id=run_id,
        image_shape=image_shape,
        samples_per_ray=samples_per_ray,
        feedback_enabled=feedback_enabled,
    )
    restored = session.export_artifacts()
    restored_state = restored["implicit_field_states"][-1]
    audit = session.apply_interaction(
        _interaction_request(
            session,
            request_id=request_id,
            tool=tool,
            amplitude=amplitude,
            radius_world=radius_world,
            duration_ticks=duration_ticks,
        )
    )
    session.advance(int(horizon_ticks))
    artifacts = session.export_artifacts()
    manifest = artifacts["session"]
    final_state = artifacts["implicit_field_states"][-1]
    live_steps = [
        step
        for step in artifacts["implicit_live_step_records"]
        if int(step["tick"]) > int(trusted_snapshot["current_state"]["tick"])
    ]
    final_audit = next(
        record
        for record in artifacts["implicit_interaction_audits"]
        if record["request_id"] == request_id
    )

    raw_user_dose = sum(
        _projection_density_sum(step.get("raw_user_input_projection", {}))
        for step in live_steps
    )
    realized_user_dose = sum(
        _projection_density_sum(step.get("realized_user_input_projection", {}))
        for step in live_steps
    )
    raw_feedback_l1 = sum(
        _projection_density_l1(step.get("raw_five_phase_feedback_input_projection", {}))
        for step in live_steps
    )
    realized_feedback_l1 = sum(
        _projection_density_l1(
            step.get(
                "realized_five_phase_feedback_input_projection",
                step.get("five_phase_feedback_input_projection", {}),
            )
        )
        for step in live_steps
    )
    energy_ledgers = [
        {"tick": int(step["tick"]), "ledgers": copy.deepcopy(step.get("energy_ledgers", []))}
        for step in live_steps
    ]
    realized_user_density_by_tick = [
        {
            "tick": int(step["tick"]),
            "density_by_basis": _projection_density_vector(
                step.get("realized_user_input_projection", {})
            ),
        }
        for step in live_steps
    ]

    return {
        "branch_label": branch_label,
        "is_authority_state": False,
        "feedback_enabled_override": bool(feedback_enabled),
        "restored_snapshot_digest": str(trusted_snapshot["snapshot_digest"]),
        "restored_state_digest": str(restored_state["state_digest"]),
        "configuration_digest": str(trusted_snapshot["configuration_digest"]),
        "run_id": str(manifest["run_id"]),
        "session_id": str(manifest["session_id"]),
        "source_package_name": str(manifest["source_package_name"]),
        "source_package_digest": str(manifest["source_package_digest"]),
        "request_id": request_id,
        "tool": tool,
        "amplitude": float(amplitude),
        "radius_world": float(radius_world),
        "duration_ticks": float(duration_ticks),
        "horizon_ticks": int(horizon_ticks),
        "signed_amplitude": float(final_audit["signed_amplitude"]),
        "schedule_weights": [float(value) for value in final_audit["schedule_weights"]],
        "target_basis_ids": [str(value) for value in final_audit["target_basis_ids"]],
        "kappa_by_basis": {
            str(key): float(value)
            for key, value in sorted(final_audit.get("kappa_by_basis", {}).items())
        },
        "normalized_weights_by_basis": {
            str(key): float(value)
            for key, value in sorted(final_audit.get("normalized_weights_by_basis", {}).items())
        },
        "application_count": len(final_audit.get("applications", [])),
        "raw_user_dose": raw_user_dose,
        "realized_user_dose": realized_user_dose,
        "raw_feedback_l1": raw_feedback_l1,
        "realized_feedback_l1": realized_feedback_l1,
        "final_tick": int(final_state["tick"]),
        "final_state_id": str(final_state["implicit_field_state_id"]),
        "final_state_digest": str(final_state["state_digest"]),
        "density_coefficients": _density_coefficients(final_state),
        "realized_user_density_by_tick": realized_user_density_by_tick,
        "energy_ledgers": energy_ledgers,
        "interaction_status": str(final_audit["status"]),
        "accepted_audit_id": str(audit["audit_id"]),
    }


def _energy_budget_comparison(branches: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    ledger_count = 0
    for branch_label, branch in branches.items():
        for tick_record in branch["energy_ledgers"]:
            for ledger in tick_record["ledgers"]:
                ledger_count += 1
                residual = abs(float(ledger["residual"]))
                tolerance = float(ledger["residual_tolerance"])
                if residual > tolerance + ABS_TOLERANCE:
                    failures.append(
                        {
                            "branch_label": branch_label,
                            "tick": int(tick_record["tick"]),
                            "scope_id": str(ledger["scope_id"]),
                            "residual": residual,
                            "residual_tolerance": tolerance,
                        }
                    )
    return {
        "passed": ledger_count > 0 and not failures,
        "ledger_count": ledger_count,
        "failures": failures,
    }


def _passive_continuity_comparison(
    lower: Mapping[str, Any],
    upper: Mapping[str, Any],
    *,
    parameter_name: str,
) -> dict[str, Any]:
    lower_inputs = list(lower["realized_user_density_by_tick"])
    upper_inputs = list(upper["realized_user_density_by_tick"])
    common_final_horizon = bool(
        int(lower["horizon_ticks"]) == int(upper["horizon_ticks"])
        and int(lower["final_tick"]) == int(upper["final_tick"])
        and [int(item["tick"]) for item in lower_inputs]
        == [int(item["tick"]) for item in upper_inputs]
    )
    input_delta_l1_by_tick = [
        {
            "tick": int(lower_item["tick"]),
            "realized_input_delta_l1": _vector_l1(
                _vector_delta(
                    lower_item["density_by_basis"],
                    upper_item["density_by_basis"],
                )
            ),
        }
        for lower_item, upper_item in zip(lower_inputs, upper_inputs)
    ]
    horizon = int(lower["horizon_ticks"])
    passive_response_bound = math.fsum(
        PASSIVE_CONTRACTION_RATE_CEILING ** (horizon - 1 - index)
        * float(item["realized_input_delta_l1"])
        for index, item in enumerate(input_delta_l1_by_tick)
    )
    final_response_delta = _vector_l1(
        _vector_delta(lower["density_coefficients"], upper["density_coefficients"])
    )
    total_input_delta = math.fsum(
        float(item["realized_input_delta_l1"])
        for item in input_delta_l1_by_tick
    )
    parameter_delta = abs(float(upper[parameter_name]) - float(lower[parameter_name]))
    same_trusted_s0 = bool(
        lower["restored_snapshot_digest"] == upper["restored_snapshot_digest"]
        and lower["restored_state_digest"] == upper["restored_state_digest"]
        and lower["configuration_digest"] == upper["configuration_digest"]
        and lower["run_id"] == upper["run_id"]
        and lower["session_id"] == upper["session_id"]
    )
    feedback_disabled = bool(
        lower["feedback_enabled_override"] is False
        and upper["feedback_enabled_override"] is False
        and float(lower["realized_feedback_l1"]) <= ABS_TOLERANCE
        and float(upper["realized_feedback_l1"]) <= ABS_TOLERANCE
    )
    comparison = {
        "parameter": parameter_name,
        "lower_branch_label": str(lower["branch_label"]),
        "upper_branch_label": str(upper["branch_label"]),
        "lower_parameter_value": float(lower[parameter_name]),
        "upper_parameter_value": float(upper[parameter_name]),
        "parameter_delta": parameter_delta,
        "same_trusted_s0": same_trusted_s0,
        "feedback_disabled": feedback_disabled,
        "common_final_horizon": common_final_horizon,
        "horizon_ticks": horizon,
        "final_tick": int(lower["final_tick"]),
        "contraction_rate_ceiling": PASSIVE_CONTRACTION_RATE_CEILING,
        "initial_state_delta_l1": 0.0,
        "input_delta_l1_by_tick": input_delta_l1_by_tick,
        "total_realized_input_delta_l1": total_input_delta,
        "passive_response_bound_l1": passive_response_bound,
        "final_response_delta_l1": final_response_delta,
        "response_to_bound_ratio": (
            final_response_delta / passive_response_bound
            if passive_response_bound > RESPONSE_TOLERANCE
            else 0.0
        ),
        "acceptance_tolerance": ABS_TOLERANCE,
    }
    comparison["passed"] = bool(
        same_trusted_s0
        and feedback_disabled
        and common_final_horizon
        and len(lower_inputs) == horizon
        and len(upper_inputs) == horizon
        and parameter_delta > 0.0
        and total_input_delta > RESPONSE_TOLERANCE
        and final_response_delta > RESPONSE_TOLERANCE
        and final_response_delta <= passive_response_bound + ABS_TOLERANCE
    )
    return comparison


def _blocked_report(
    *,
    trusted_snapshot: Mapping[str, Any],
    missing_field: str,
    error: str,
) -> dict[str, Any]:
    configuration = trusted_snapshot["configuration"]
    return {
        "schema": SCHEMA,
        "overall_status": "blocked_missing_public_api",
        "missing_public_api_fields": [missing_field],
        "trusted_s0": {
            "snapshot_digest": str(trusted_snapshot["snapshot_digest"]),
            "state_digest": str(trusted_snapshot["current_state"]["state_digest"]),
            "tick": int(trusted_snapshot["current_state"]["tick"]),
            "run_id": str(configuration["run_id"]),
            "session_id": str(configuration["session_id"]),
            "configuration_digest": str(trusted_snapshot["configuration_digest"]),
        },
        "same_s0_identity": {"passed": False, "branch_labels_are_non_authority": True},
        "branches": {},
        "comparisons": {},
        "error": error,
    }


def run_continuous_local_energy_response_validation(
    *,
    source_package_name: str = "source-a",
    source_package_digest: str = "digest-source-a",
    run_id: str = "continuous-local-energy-response-validation",
    image_shape: Sequence[int] = (12, 8),
    samples_per_ray: int = 6,
    horizon_ticks: int = DEFAULT_HORIZON_TICKS,
) -> dict[str, Any]:
    if int(horizon_ticks) < 3:
        raise ValueError("horizon_ticks must cover the 2.25-tick fractional schedule")
    seed = _new_session(
        source_package_name=source_package_name,
        source_package_digest=source_package_digest,
        run_id=run_id,
        image_shape=image_shape,
        samples_per_ray=samples_per_ray,
    )
    trusted_snapshot = copy.deepcopy(seed.to_snapshot())
    missing_override = (
        "ImplicitFieldSession.restore_snapshot."
        "five_phase_feedback_enabled_override"
    )
    try:
        _restore_branch(
            trusted_snapshot=trusted_snapshot,
            source_package_name=source_package_name,
            source_package_digest=source_package_digest,
            run_id=run_id,
            image_shape=image_shape,
            samples_per_ray=samples_per_ray,
            feedback_enabled=False,
        )
    except TypeError as exc:
        if "five_phase_feedback_enabled_override" not in str(exc):
            raise
        return _blocked_report(
            trusted_snapshot=trusted_snapshot,
            missing_field=missing_override,
            error=str(exc),
        )

    branch_specs = [
        ("feedback_off_zero", False, "validation::control::00", "implicit_local_excite", 0.0, 1.5, 1.0),
        ("feedback_on_zero", True, "validation::control::00", "implicit_local_excite", 0.0, 1.5, 1.0),
        ("excite_low", False, "validation::control::01", "implicit_local_excite", 0.1, 1.5, 1.0),
        ("excite_mid", False, "validation::control::02", "implicit_local_excite", 0.2, 1.5, 1.0),
        ("feedback_on_excite", True, "validation::control::02", "implicit_local_excite", 0.2, 1.5, 1.0),
        ("excite_high", False, "validation::control::03", "implicit_local_excite", 0.3, 1.5, 1.0),
        ("dampen_mid", False, "validation::control::04", "implicit_local_dampen", 0.2, 1.5, 1.0),
        ("radius_small", False, "validation::control::05", "implicit_local_excite", 0.2, 1.0, 1.0),
        ("radius_large", False, "validation::control::06", "implicit_local_excite", 0.2, 2.0, 1.0),
        ("duration_one_half", False, "validation::control::07", "implicit_local_excite", 0.2, 1.5, 1.5),
        ("duration_two_quarter", False, "validation::control::08", "implicit_local_excite", 0.2, 1.5, 2.25),
        ("amplitude_neighbor_low", False, "validation::control::09", "implicit_local_excite", 0.199, 1.5, 1.0),
        ("amplitude_neighbor_high", False, "validation::control::10", "implicit_local_excite", 0.201, 1.5, 1.0),
        ("radius_neighbor_low", False, "validation::control::11", "implicit_local_excite", 0.2, 1.49, 1.0),
        ("radius_neighbor_high", False, "validation::control::12", "implicit_local_excite", 0.2, 1.51, 1.0),
        (
            "duration_neighbor_below_integer",
            False,
            "validation::control::13",
            "implicit_local_excite",
            0.2,
            1.5,
            1.99,
        ),
        (
            "duration_neighbor_above_integer",
            False,
            "validation::control::14",
            "implicit_local_excite",
            0.2,
            1.5,
            2.01,
        ),
        ("determinism_repeat", False, "validation::control::02", "implicit_local_excite", 0.2, 1.5, 1.0),
    ]
    branches = {
        label: _run_branch(
            branch_label=label,
            trusted_snapshot=trusted_snapshot,
            source_package_name=source_package_name,
            source_package_digest=source_package_digest,
            run_id=run_id,
            image_shape=image_shape,
            samples_per_ray=samples_per_ray,
            feedback_enabled=feedback_enabled,
            request_id=request_id,
            tool=tool,
            amplitude=amplitude,
            radius_world=radius_world,
            duration_ticks=duration_ticks,
            horizon_ticks=int(horizon_ticks),
        )
        for (
            label,
            feedback_enabled,
            request_id,
            tool,
            amplitude,
            radius_world,
            duration_ticks,
        ) in branch_specs
    }

    passive = branches["feedback_off_zero"]["density_coefficients"]
    excite = _vector_delta(branches["excite_mid"]["density_coefficients"], passive)
    dampen = _vector_delta(branches["dampen_mid"]["density_coefficients"], passive)
    signed_direction = {
        "excite_realized_dose": branches["excite_mid"]["realized_user_dose"],
        "dampen_realized_dose": branches["dampen_mid"]["realized_user_dose"],
        "excite_response_sum": sum(excite.values()),
        "dampen_response_sum": sum(dampen.values()),
        "response_dot_product": _vector_dot(excite, dampen),
    }
    signed_direction["passed"] = bool(
        signed_direction["excite_realized_dose"] > RESPONSE_TOLERANCE
        and signed_direction["dampen_realized_dose"] < -RESPONSE_TOLERANCE
        and signed_direction["excite_response_sum"] > RESPONSE_TOLERANCE
        and signed_direction["dampen_response_sum"] < -RESPONSE_TOLERANCE
        and signed_direction["response_dot_product"] < -RESPONSE_TOLERANCE
    )

    amplitude_norms = {
        label: _vector_distance(branches[label]["density_coefficients"], passive)
        for label in ("excite_low", "excite_mid", "excite_high")
    }
    amplitude_grading = {
        "response_l2": amplitude_norms,
        "realized_doses": {
            label: branches[label]["realized_user_dose"]
            for label in ("excite_low", "excite_mid", "excite_high")
        },
    }
    amplitude_grading["passed"] = bool(
        amplitude_norms["excite_low"] + RESPONSE_TOLERANCE < amplitude_norms["excite_mid"]
        and amplitude_norms["excite_mid"] + RESPONSE_TOLERANCE < amplitude_norms["excite_high"]
    )

    small = branches["radius_small"]
    large = branches["radius_large"]
    kernel_distance = _vector_distance(
        small["normalized_weights_by_basis"],
        large["normalized_weights_by_basis"],
    )
    radius_response_distance = _vector_distance(
        small["density_coefficients"],
        large["density_coefficients"],
    )
    radius_locality = {
        "small_radius_world": small["radius_world"],
        "large_radius_world": large["radius_world"],
        "small_target_basis_ids": small["target_basis_ids"],
        "large_target_basis_ids": large["target_basis_ids"],
        "normalized_kernel_distance": kernel_distance,
        "response_distance": radius_response_distance,
        "realized_dose_delta": abs(small["realized_user_dose"] - large["realized_user_dose"]),
    }
    radius_locality["passed"] = bool(
        kernel_distance > RESPONSE_TOLERANCE
        and radius_response_distance > RESPONSE_TOLERANCE
        and radius_locality["realized_dose_delta"] <= ABS_TOLERANCE
    )

    duration_labels = ("excite_mid", "duration_one_half", "duration_two_quarter")
    duration_norms = {
        label: _vector_distance(branches[label]["density_coefficients"], passive)
        for label in duration_labels
    }
    fractional_duration = {
        "schedule_weights": {
            label: branches[label]["schedule_weights"] for label in duration_labels
        },
        "application_counts": {
            label: branches[label]["application_count"] for label in duration_labels
        },
        "realized_doses": {
            label: branches[label]["realized_user_dose"] for label in duration_labels
        },
        "response_l2": duration_norms,
    }
    fractional_duration["passed"] = bool(
        branches["duration_one_half"]["schedule_weights"] == [1.0, 0.5]
        and branches["duration_two_quarter"]["schedule_weights"] == [1.0, 1.0, 0.25]
        and branches["excite_mid"]["realized_user_dose"] + RESPONSE_TOLERANCE
        < branches["duration_one_half"]["realized_user_dose"]
        and branches["duration_one_half"]["realized_user_dose"] + RESPONSE_TOLERANCE
        < branches["duration_two_quarter"]["realized_user_dose"]
        and duration_norms["excite_mid"] + RESPONSE_TOLERANCE
        < duration_norms["duration_one_half"]
        and duration_norms["duration_one_half"] + RESPONSE_TOLERANCE
        < duration_norms["duration_two_quarter"]
    )

    disabled = branches["excite_mid"]
    enabled = branches["feedback_on_excite"]
    feedback_distance = _vector_distance(
        disabled["density_coefficients"], enabled["density_coefficients"]
    )
    passive_norm = max(_vector_l2(disabled["density_coefficients"]), RESPONSE_TOLERANCE)
    feedback_counterfactual = {
        "disabled_run_id": disabled["run_id"],
        "enabled_run_id": enabled["run_id"],
        "disabled_session_id": disabled["session_id"],
        "enabled_session_id": enabled["session_id"],
        "disabled_realized_feedback_l1": disabled["realized_feedback_l1"],
        "enabled_realized_feedback_l1": enabled["realized_feedback_l1"],
        "response_distance": feedback_distance,
        "dimensionless_response_distance": feedback_distance / passive_norm,
    }
    feedback_counterfactual["passed"] = bool(
        disabled["run_id"] == enabled["run_id"]
        and disabled["session_id"] == enabled["session_id"]
        and disabled["realized_feedback_l1"] <= ABS_TOLERANCE
        and enabled["realized_feedback_l1"] > RESPONSE_TOLERANCE
        and feedback_distance > RESPONSE_TOLERANCE
    )

    repeated = branches["determinism_repeat"]
    reference = branches["excite_mid"]
    determinism = {
        "passed": bool(
            repeated["final_state_digest"] == reference["final_state_digest"]
            and repeated["density_coefficients"] == reference["density_coefficients"]
            and repeated["realized_user_dose"] == reference["realized_user_dose"]
            and repeated["energy_ledgers"] == reference["energy_ledgers"]
        ),
        "reference_final_state_digest": reference["final_state_digest"],
        "repeat_final_state_digest": repeated["final_state_digest"],
    }

    trusted_configuration = trusted_snapshot["configuration"]
    same_s0_identity = {
        "passed": all(
            branch["restored_snapshot_digest"] == trusted_snapshot["snapshot_digest"]
            and branch["restored_state_digest"] == trusted_snapshot["current_state"]["state_digest"]
            and branch["configuration_digest"] == trusted_snapshot["configuration_digest"]
            and branch["run_id"] == trusted_configuration["run_id"]
            and branch["session_id"] == trusted_configuration["session_id"]
            for branch in branches.values()
        ),
        "branch_labels_are_non_authority": all(
            not branch["is_authority_state"]
            and branch["branch_label"] not in branch["run_id"]
            and branch["branch_label"] not in branch["session_id"]
            for branch in branches.values()
        ),
        "allowed_counterfactual_difference": ["five_phase_feedback_enabled"],
    }
    comparisons = {
        "signed_direction": signed_direction,
        "amplitude_grading": amplitude_grading,
        "radius_locality": radius_locality,
        "fractional_duration": fractional_duration,
        "amplitude_continuity": _passive_continuity_comparison(
            branches["amplitude_neighbor_low"],
            branches["amplitude_neighbor_high"],
            parameter_name="amplitude",
        ),
        "radius_continuity": _passive_continuity_comparison(
            branches["radius_neighbor_low"],
            branches["radius_neighbor_high"],
            parameter_name="radius_world",
        ),
        "fractional_duration_continuity": _passive_continuity_comparison(
            branches["duration_neighbor_below_integer"],
            branches["duration_neighbor_above_integer"],
            parameter_name="duration_ticks",
        ),
        "feedback_counterfactual": feedback_counterfactual,
        "determinism": determinism,
        "energy_budget": _energy_budget_comparison(branches),
    }
    overall_passed = bool(
        same_s0_identity["passed"]
        and same_s0_identity["branch_labels_are_non_authority"]
        and all(comparison["passed"] for comparison in comparisons.values())
    )
    report = {
        "schema": SCHEMA,
        "overall_status": "passed" if overall_passed else "failed",
        "missing_public_api_fields": [],
        "trusted_s0": {
            "snapshot_digest": str(trusted_snapshot["snapshot_digest"]),
            "state_digest": str(trusted_snapshot["current_state"]["state_digest"]),
            "tick": int(trusted_snapshot["current_state"]["tick"]),
            "run_id": str(trusted_configuration["run_id"]),
            "session_id": str(trusted_configuration["session_id"]),
            "configuration_digest": str(trusted_snapshot["configuration_digest"]),
        },
        "same_s0_identity": same_s0_identity,
        "branches": branches,
        "comparisons": comparisons,
    }
    json.dumps(report, sort_keys=True, allow_nan=False)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run same-S0 continuous local energy-response validation."
    )
    parser.add_argument("--source-package-name", default="source-a")
    parser.add_argument("--source-package-digest", default="digest-source-a")
    parser.add_argument("--run-id", default="continuous-local-energy-response-validation")
    parser.add_argument("--horizon-ticks", type=int, default=DEFAULT_HORIZON_TICKS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = run_continuous_local_energy_response_validation(
        source_package_name=args.source_package_name,
        source_package_digest=args.source_package_digest,
        run_id=args.run_id,
        horizon_ticks=args.horizon_ticks,
    )
    payload = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    sys.stdout.write(payload)
    return 0 if report["overall_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
