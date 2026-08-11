from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from world_engine.implicit_field import build_implicit_field_state, validate_implicit_field_state


IMPLICIT_LOCAL_REFINEMENT_REQUEST_SCHEMA = "implicit_local_refinement_request"
IMPLICIT_LOCAL_REFINEMENT_PATCH_SCHEMA = "implicit_local_refinement_patch"


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _require_region(region: Mapping[str, Any]) -> None:
    if "min" not in region or "max" not in region:
        raise ValueError("region must include min and max")
    if len(region["min"]) != 3 or len(region["max"]) != 3:
        raise ValueError("region bounds must be 3D")


def build_implicit_local_refinement_request(
    request_id: str,
    trigger_kind: str,
    trigger_record_ids: Sequence[str],
    region_world_3d: Mapping[str, Any],
    requested_grid_shape: Sequence[int],
    requested_tick_window: Sequence[int],
    source_implicit_field_state_id: str,
    error_metrics_before_refinement: Mapping[str, Any],
    source_record_ids: Sequence[str],
) -> dict[str, Any]:
    record = {
        "schema": IMPLICIT_LOCAL_REFINEMENT_REQUEST_SCHEMA,
        "request_id": str(request_id),
        "trigger_kind": str(trigger_kind),
        "trigger_record_ids": [str(value) for value in trigger_record_ids],
        "region_world_3d": dict(region_world_3d),
        "requested_grid_shape": [int(value) for value in requested_grid_shape],
        "requested_tick_window": [int(value) for value in requested_tick_window],
        "source_implicit_field_state_id": str(source_implicit_field_state_id),
        "error_metrics_before_refinement": dict(error_metrics_before_refinement),
        "source_record_ids": [str(value) for value in source_record_ids],
        "is_authority_state": False,
    }
    validate_implicit_local_refinement_request(record)
    return record


def validate_implicit_local_refinement_request(record: Mapping[str, Any]) -> None:
    if record.get("schema") != IMPLICIT_LOCAL_REFINEMENT_REQUEST_SCHEMA:
        raise ValueError("implicit local refinement request schema mismatch")
    if record.get("is_authority_state") is not False:
        raise ValueError("implicit local refinement request must be non-authority")
    if record.get("trigger_kind") not in {
        "observer_resolution",
        "interaction_uncertainty",
        "boundary_error",
        "ray_residual",
        "completion_probe",
    }:
        raise ValueError("unsupported implicit local refinement trigger kind")
    if not record.get("trigger_record_ids"):
        raise ValueError("implicit local refinement request requires trigger lineage")
    _require_region(record.get("region_world_3d", {}))
    shape = [int(value) for value in record.get("requested_grid_shape", [])]
    if len(shape) != 3 or any(value <= 0 for value in shape):
        raise ValueError("requested_grid_shape must be positive 3D shape")
    if len(record.get("requested_tick_window", [])) != 2:
        raise ValueError("requested_tick_window must include start and end")


def build_implicit_local_refinement_patch(
    patch_id: str,
    request_id: str,
    field_state_ids: Sequence[str],
    patch_coordinate_frame: Mapping[str, Any],
    initial_patch_snapshot: Mapping[str, Any],
    final_patch_snapshot: Mapping[str, Any],
    initial_patch_digest: str,
    final_patch_digest: str,
    patch_summary: Mapping[str, Any],
    patch_to_implicit_correction: Mapping[str, Any],
    source_wave_step_record_ids: Sequence[str],
    source_record_ids: Sequence[str],
) -> dict[str, Any]:
    record = {
        "schema": IMPLICIT_LOCAL_REFINEMENT_PATCH_SCHEMA,
        "patch_id": str(patch_id),
        "request_id": str(request_id),
        "field_state_ids": [str(value) for value in field_state_ids],
        "patch_coordinate_frame": dict(patch_coordinate_frame),
        "initial_patch_snapshot": dict(initial_patch_snapshot),
        "final_patch_snapshot": dict(final_patch_snapshot),
        "initial_patch_digest": str(initial_patch_digest),
        "final_patch_digest": str(final_patch_digest),
        "patch_summary": dict(patch_summary),
        "patch_to_implicit_correction": dict(patch_to_implicit_correction),
        "source_wave_step_record_ids": [str(value) for value in source_wave_step_record_ids],
        "source_record_ids": [str(value) for value in source_record_ids],
        "is_authority_state": False,
    }
    validate_implicit_local_refinement_patch(record)
    return record


def validate_implicit_local_refinement_patch(record: Mapping[str, Any]) -> None:
    if record.get("schema") != IMPLICIT_LOCAL_REFINEMENT_PATCH_SCHEMA:
        raise ValueError("implicit local refinement patch schema mismatch")
    if record.get("is_authority_state") is not False:
        raise ValueError("implicit local refinement patch must be non-authority")
    for key in ("request_id", "initial_patch_snapshot", "final_patch_snapshot", "initial_patch_digest", "final_patch_digest"):
        if not record.get(key):
            raise ValueError(f"implicit local refinement patch requires {key}")
    if not record.get("field_state_ids"):
        raise ValueError("implicit local refinement patch requires field_state_ids")
    summary = record.get("patch_summary")
    if not isinstance(summary, Mapping) or "relative_energy_delta" not in summary:
        raise ValueError("implicit local refinement patch requires recomputable summary")
    correction = record.get("patch_to_implicit_correction")
    if not isinstance(correction, Mapping) or not correction.get("basis_id") or not correction.get("channel"):
        raise ValueError("implicit local refinement patch requires correction target")
    if not record.get("source_wave_step_record_ids"):
        raise ValueError("implicit local refinement patch requires wave step lineage")


def apply_refinement_patch_to_implicit_state(
    state: Mapping[str, Any],
    bases: Sequence[Mapping[str, Any]],
    patch: Mapping[str, Any],
    *,
    relative_energy_max: float = 0.35,
) -> dict[str, Any]:
    validate_implicit_field_state(state)
    validate_implicit_local_refinement_patch(patch)
    correction = dict(patch["patch_to_implicit_correction"])
    relative_energy = float(correction.get("relative_energy_delta", patch["patch_summary"].get("relative_energy_delta", 0.0)))
    if relative_energy > relative_energy_max:
        raise ValueError("implicit refinement correction exceeds relative energy limit")
    basis_ids = {str(basis.get("basis_id")) for basis in bases}
    basis_id = str(correction["basis_id"])
    if basis_id not in basis_ids:
        raise ValueError("implicit refinement correction basis is outside request support")
    channel = str(correction["channel"])
    coefficients = {
        str(key): dict(value)
        for key, value in state.get("basis_coefficients", {}).items()
    }
    coefficients.setdefault(basis_id, {})
    coefficients[basis_id][channel] = float(coefficients[basis_id].get(channel, 0.0)) + float(correction.get("delta", 0.0))
    return build_implicit_field_state(
        implicit_field_state_id=str(state["implicit_field_state_id"]),
        tick=int(state.get("tick", 0)) + 1,
        basis_ids=list(state["basis_ids"]),
        basis_layout_digest=str(state["basis_layout_digest"]),
        basis_spatial_index_digest=str(state["basis_spatial_index_digest"]),
        basis_coefficients=coefficients,
        sparse_coupling_edges=list(state.get("sparse_coupling_edges", [])),
        background_model=dict(state.get("background_model", {})),
        active_local_patch_ids=[*state.get("active_local_patch_ids", []), str(patch["patch_id"])],
        validity_region_world=dict(state.get("validity_region_world", {})),
        energy_summary={"total_abs_coefficient": sum(abs(float(value)) for channels in coefficients.values() for value in channels.values())},
        source_record_ids=[*state.get("source_record_ids", []), str(patch["patch_id"])],
        authority_status=str(state.get("authority_status", "candidate")),
    )
