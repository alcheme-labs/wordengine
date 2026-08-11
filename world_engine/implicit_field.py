from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping, Sequence


IMPLICIT_FIELD_BASIS_SCHEMA = "implicit_field_basis"
IMPLICIT_FIELD_STATE_SCHEMA = "implicit_field_state"
IMPLICIT_FIELD_EVALUATION_SCHEMA = "implicit_field_evaluation_record"
IMPLICIT_FIELD_AUTHORITY_CERTIFICATE_SCHEMA = "implicit_field_authority_certificate"

FORBIDDEN_IMPLICIT_FIELD_KEYS = {
    "dense_volume",
    "voxel_grid",
    "mesh",
    "sprite",
    "css_color",
    "viewer_shape",
    "object_asset_id",
}

ALLOWED_BASIS_KINDS = {
    "compact_oscillator",
    "signed_boundary",
    "emitter",
    "absorption_region",
    "density_lobe",
    "radial_emitter",
    "spherical_shell",
}

ALLOWED_PROFILES_BY_KIND = {
    "compact_oscillator": {"oscillator"},
    "emitter": {"oscillator"},
    "signed_boundary": {"signed_step", "signed_plane"},
    "absorption_region": {"constant", "absorption"},
    "density_lobe": {"constant", "density"},
    "radial_emitter": {"radial_inverse_square"},
    "spherical_shell": {"spherical_shell_band"},
}


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _strip_digest(value: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    data = dict(value)
    for key in keys:
        data.pop(key, None)
    return data


def _assert_no_forbidden_keys(value: Any, *, path: str = "payload") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in FORBIDDEN_IMPLICIT_FIELD_KEYS:
                raise ValueError(f"forbidden implicit field key at {path}: {key}")
            _assert_no_forbidden_keys(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_forbidden_keys(child, path=f"{path}[{index}]")


def _finite_number(value: Any, *, name: str) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


def _finite_vector(values: Sequence[Any], *, name: str, length: int) -> list[float]:
    if len(values) != length:
        raise ValueError(f"{name} must have length {length}")
    return [_finite_number(value, name=name) for value in values]


def _finite_matrix(matrix: Sequence[Sequence[Any]], *, name: str) -> list[list[float]]:
    if len(matrix) != 3:
        raise ValueError(f"{name} must have three rows")
    rows = [_finite_vector(row, name=name, length=3) for row in matrix]
    determinant = (
        rows[0][0] * (rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1])
        - rows[0][1] * (rows[1][0] * rows[2][2] - rows[1][2] * rows[2][0])
        + rows[0][2] * (rows[1][0] * rows[2][1] - rows[1][1] * rows[2][0])
    )
    if abs(determinant) < 1e-9:
        raise ValueError(f"{name} must be invertible enough for evaluation")
    return rows


def _basis_id(record: Mapping[str, Any]) -> str:
    return str(record.get("basis_id", ""))


def wendland_c2(radius_ratio: float) -> float:
    r = float(radius_ratio)
    if not math.isfinite(r):
        raise ValueError("radius ratio must be finite")
    if r >= 1.0:
        return 0.0
    r = max(0.0, r)
    return (1.0 - r) ** 4 * (4.0 * r + 1.0)


def build_implicit_field_basis(
    basis_id: str,
    basis_kind: str,
    coordinate_frame_3d: Mapping[str, Any],
    source_signature_template_id: str,
    source_signature_instance_id: str,
    center_world_3d: Sequence[float],
    basis_axes: Sequence[Sequence[float]],
    radius_world: float,
    basis_profile: str,
    basis_profile_params: Mapping[str, Any],
    frequency_vector: Sequence[float],
    omega: float,
    phase: float,
    channel_weights: Mapping[str, float],
    support_region_world: Mapping[str, Any],
    source_record_ids: Sequence[str],
) -> dict[str, Any]:
    record = {
        "schema": IMPLICIT_FIELD_BASIS_SCHEMA,
        "basis_id": str(basis_id),
        "basis_kind": str(basis_kind),
        "coordinate_frame_3d": dict(coordinate_frame_3d),
        "source_signature_template_id": str(source_signature_template_id),
        "source_signature_instance_id": str(source_signature_instance_id),
        "center_world_3d": _finite_vector(center_world_3d, name="center_world_3d", length=3),
        "basis_axes": _finite_matrix(basis_axes, name="basis_axes"),
        "radius_world": _finite_number(radius_world, name="radius_world"),
        "basis_profile": str(basis_profile),
        "basis_profile_params": dict(basis_profile_params),
        "frequency_vector": _finite_vector(frequency_vector, name="frequency_vector", length=3),
        "omega": _finite_number(omega, name="omega"),
        "phase": _finite_number(phase, name="phase"),
        "channel_weights": {str(key): _finite_number(value, name=f"channel_weights.{key}") for key, value in channel_weights.items()},
        "support_region_world": dict(support_region_world),
        "source_record_ids": [str(value) for value in source_record_ids],
        "is_authority_state": False,
    }
    validate_implicit_field_basis(record)
    return record


def validate_implicit_field_basis(record: Mapping[str, Any]) -> None:
    if record.get("schema") != IMPLICIT_FIELD_BASIS_SCHEMA:
        raise ValueError("implicit field basis schema mismatch")
    if record.get("is_authority_state") is not False:
        raise ValueError("implicit field basis must be non-authority")
    if not record.get("basis_id"):
        raise ValueError("implicit field basis requires basis_id")
    basis_kind = str(record.get("basis_kind", ""))
    if basis_kind not in ALLOWED_BASIS_KINDS:
        raise ValueError("unsupported implicit field basis kind")
    coordinate_frame = record.get("coordinate_frame_3d")
    if not isinstance(coordinate_frame, Mapping):
        raise ValueError("implicit field basis requires coordinate_frame_3d")
    if not coordinate_frame.get("units") or not coordinate_frame.get("handedness") or len(list(coordinate_frame.get("axes", []))) != 3:
        raise ValueError("coordinate_frame_3d must define units, handedness, and axes")
    radius = _finite_number(record.get("radius_world"), name="radius_world")
    if radius <= 0.0:
        raise ValueError("radius_world must be positive")
    _finite_matrix(record.get("basis_axes", []), name="basis_axes")
    _finite_vector(record.get("center_world_3d", []), name="center_world_3d", length=3)
    _finite_vector(record.get("frequency_vector", []), name="frequency_vector", length=3)
    profile = str(record.get("basis_profile", ""))
    if profile not in ALLOWED_PROFILES_BY_KIND[basis_kind]:
        raise ValueError("basis_profile does not match basis_kind")
    params = record.get("basis_profile_params", {})
    if profile == "spherical_shell_band":
        inner_radius = _finite_number(params.get("inner_radius_world", 0.0), name="basis_profile_params.inner_radius_world")
        outer_radius = _finite_number(params.get("outer_radius_world", radius), name="basis_profile_params.outer_radius_world")
        if inner_radius < 0.0 or outer_radius <= inner_radius:
            raise ValueError("spherical shell profile requires monotonic inner/outer radius")
    if profile == "radial_inverse_square":
        clamp = _finite_number(params.get("clamp_radius_world", 1.0), name="basis_profile_params.clamp_radius_world")
        if clamp <= 0.0:
            raise ValueError("radial inverse square profile requires positive clamp radius")
    support = record.get("support_region_world")
    if not isinstance(support, Mapping) or "min" not in support or "max" not in support:
        raise ValueError("support_region_world must include min and max")
    _finite_vector(support["min"], name="support_region_world.min", length=3)
    _finite_vector(support["max"], name="support_region_world.max", length=3)
    _assert_no_forbidden_keys(record)


def build_basis_spatial_index(bases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    cells = [
        {
            "basis_id": _basis_id(basis),
            "support_region_world": dict(basis.get("support_region_world", {})),
        }
        for basis in sorted(bases, key=_basis_id)
    ]
    payload = {
        "schema": "implicit_basis_spatial_index",
        "index_kind": "support_aabb_list",
        "cells": cells,
    }
    payload["basis_spatial_index_digest"] = _canonical_digest(payload)
    return payload


def _basis_layout_digest_payload(basis_ids: Sequence[str], basis_spatial_index_digest: str) -> dict[str, Any]:
    return {"basis_ids": list(basis_ids), "basis_spatial_index_digest": basis_spatial_index_digest}


def build_implicit_field_state(
    implicit_field_state_id: str,
    tick: int,
    basis_ids: Sequence[str],
    basis_layout_digest: str,
    basis_spatial_index_digest: str,
    basis_coefficients: Mapping[str, Mapping[str, float]],
    sparse_coupling_edges: Sequence[Mapping[str, Any]],
    background_model: Mapping[str, Any],
    active_local_patch_ids: Sequence[str],
    validity_region_world: Mapping[str, Any],
    energy_summary: Mapping[str, Any],
    source_record_ids: Sequence[str],
    authority_status: str = "candidate",
    runtime_cost_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    record = {
        "schema": IMPLICIT_FIELD_STATE_SCHEMA,
        "implicit_field_state_id": str(implicit_field_state_id),
        "tick": int(tick),
        "basis_ids": [str(value) for value in basis_ids],
        "basis_layout_digest": str(basis_layout_digest),
        "basis_spatial_index_digest": str(basis_spatial_index_digest),
        "basis_coefficients": {
            str(basis_id): {str(channel): _finite_number(value, name=f"basis_coefficients.{basis_id}.{channel}") for channel, value in channels.items()}
            for basis_id, channels in basis_coefficients.items()
        },
        "sparse_coupling_edges": [dict(edge) for edge in sparse_coupling_edges],
        "background_model": dict(background_model),
        "active_local_patch_ids": [str(value) for value in active_local_patch_ids],
        "validity_region_world": dict(validity_region_world),
        "energy_summary": dict(energy_summary),
        "source_record_ids": [str(value) for value in source_record_ids],
        "authority_status": str(authority_status),
    }
    if runtime_cost_summary is not None:
        record["runtime_cost_summary"] = dict(runtime_cost_summary)
    record["state_digest"] = _canonical_digest(_strip_digest(record, "state_digest"))
    validate_implicit_field_state(record)
    return record


def validate_implicit_field_state(record: Mapping[str, Any]) -> None:
    if record.get("schema") != IMPLICIT_FIELD_STATE_SCHEMA:
        raise ValueError("implicit field state schema mismatch")
    if record.get("authority_status") not in {"candidate", "failed_closed"}:
        raise ValueError("implicit field state cannot self-mark as validated")
    basis_ids = [str(value) for value in record.get("basis_ids", [])]
    if not basis_ids:
        raise ValueError("implicit field state requires basis_ids")
    if not record.get("basis_layout_digest") or not record.get("basis_spatial_index_digest"):
        raise ValueError("implicit field state requires basis layout and spatial index digests")
    for basis_id in record.get("basis_coefficients", {}):
        if basis_id not in basis_ids:
            raise ValueError("basis coefficient references undeclared basis")
    for edge in record.get("sparse_coupling_edges", []):
        if str(edge.get("from_basis_id")) not in basis_ids or str(edge.get("to_basis_id")) not in basis_ids:
            raise ValueError("sparse coupling edge references undeclared basis")
    if record.get("state_digest") != _canonical_digest(_strip_digest(record, "state_digest")):
        raise ValueError("implicit field state digest mismatch")
    _assert_no_forbidden_keys(record)


def _basis_envelope_value(basis: Mapping[str, Any], point: Sequence[float]) -> float:
    center = [float(value) for value in basis["center_world_3d"]]
    axes = basis["basis_axes"]
    delta = [float(point[index]) - center[index] for index in range(3)]
    transformed = [
        sum(float(axes[row][col]) * delta[col] for col in range(3))
        for row in range(3)
    ]
    radius = float(basis["radius_world"])
    return wendland_c2(math.sqrt(sum(value * value for value in transformed)) / radius)


def _basis_profile_value(basis: Mapping[str, Any], point: Sequence[float], tick: int) -> float:
    envelope = _basis_envelope_value(basis, point)
    if envelope == 0.0:
        return 0.0
    profile = str(basis.get("basis_profile"))
    if profile in {"constant", "density", "absorption"}:
        return envelope
    if profile in {"signed_step", "signed_plane"}:
        axis = str(basis.get("basis_profile_params", {}).get("axis", "x"))
        axis_index = {"x": 0, "y": 1, "z": 2}.get(axis, 0)
        threshold = float(basis.get("basis_profile_params", {}).get("threshold", 0.0))
        return envelope * (1.0 if float(point[axis_index]) >= threshold else -1.0)
    if profile == "oscillator":
        frequency_vector = [float(value) for value in basis.get("frequency_vector", [0.0, 0.0, 0.0])]
        phase = float(basis.get("phase", 0.0))
        omega = float(basis.get("omega", 0.0))
        argument = sum(frequency_vector[index] * float(point[index]) for index in range(3)) + omega * tick + phase
        return envelope * math.cos(argument)
    if profile == "radial_inverse_square":
        center = [float(value) for value in basis.get("center_world_3d", [0.0, 0.0, 0.0])]
        params = basis.get("basis_profile_params", {})
        clamp = max(1e-6, float(params.get("clamp_radius_world", 1.0)))
        distance = math.sqrt(sum((float(point[index]) - center[index]) ** 2 for index in range(3)))
        effective = max(clamp, distance)
        return envelope * (clamp / effective) ** 2
    if profile == "spherical_shell_band":
        center = [float(value) for value in basis.get("center_world_3d", [0.0, 0.0, 0.0])]
        params = basis.get("basis_profile_params", {})
        inner_radius = float(params.get("inner_radius_world", 0.0))
        outer_radius = float(params.get("outer_radius_world", basis.get("radius_world", 1.0)))
        edge_width = max(1e-6, float(params.get("edge_width_world", (outer_radius - inner_radius) * 0.15)))
        distance = math.sqrt(sum((float(point[index]) - center[index]) ** 2 for index in range(3)))
        if distance < inner_radius or distance > outer_radius:
            return 0.0
        inner_blend = min(1.0, max(0.0, (distance - inner_radius) / edge_width)) if inner_radius > 0.0 else 1.0
        outer_blend = min(1.0, max(0.0, (outer_radius - distance) / edge_width))
        return envelope * min(inner_blend, outer_blend)
    return envelope


def _active_basis_ids_for_point(
    bases: Sequence[Mapping[str, Any]],
    point: Sequence[float],
) -> list[str]:
    active = []
    for basis in bases:
        support = basis.get("support_region_world", {})
        lower = support.get("min", [-math.inf, -math.inf, -math.inf])
        upper = support.get("max", [math.inf, math.inf, math.inf])
        if all(float(lower[index]) <= float(point[index]) <= float(upper[index]) for index in range(3)):
            if _basis_envelope_value(basis, point) > 0.0:
                active.append(_basis_id(basis))
    return active


def evaluate_implicit_field(
    state: Mapping[str, Any],
    bases: Sequence[Mapping[str, Any]],
    sample_points_world_3d: Sequence[Sequence[float]],
    *,
    channel_names: Sequence[str],
    basis_spatial_index: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    validate_implicit_field_state(state)
    bases_by_id = {_basis_id(basis): basis for basis in bases}
    samples: list[dict[str, float]] = []
    contribution_rows: list[dict[str, Any]] = []
    active_counts: list[int] = []
    tick = int(state.get("tick", 0))
    for point in sample_points_world_3d:
        _finite_vector(point, name="sample_point_world_3d", length=3)
        active_ids = _active_basis_ids_for_point(list(bases), point)
        active_counts.append(len(active_ids))
        values = {str(channel): 0.0 for channel in channel_names}
        for basis_id in active_ids:
            basis = bases_by_id[basis_id]
            profile_value = _basis_profile_value(basis, point, tick)
            coefficients = state.get("basis_coefficients", {}).get(basis_id, {})
            for channel in channel_names:
                weight = float(basis.get("channel_weights", {}).get(channel, 0.0))
                coefficient = float(coefficients.get(channel, coefficients.get("*", 1.0)))
                values[str(channel)] += profile_value * weight * coefficient
            contribution_rows.append({"point": list(point), "basis_id": basis_id, "profile_value": profile_value})
        samples.append(values)
    active_max = max(active_counts) if active_counts else 0
    active_avg = sum(active_counts) / max(1, len(active_counts))
    return {
        "schema": "implicit_field_evaluation_result",
        "sample_values": samples,
        "evaluation_summary": {
            "sample_count": len(samples),
            "channel_names": [str(channel) for channel in channel_names],
            "active_basis_per_sample_avg": active_avg,
            "active_basis_per_sample_max": active_max,
        },
        "basis_contribution_digest": _canonical_digest(contribution_rows),
        "basis_spatial_index_digest": str((basis_spatial_index or {}).get("basis_spatial_index_digest", state.get("basis_spatial_index_digest", ""))),
        "active_basis_per_sample_summary": {"avg": active_avg, "max": active_max},
    }


def build_implicit_field_evaluation_record(
    evaluation_id: str,
    implicit_field_state_id: str,
    tick: int,
    sample_points_world_3d: Sequence[Sequence[float]],
    channel_names: Sequence[str],
    evaluation_summary: Mapping[str, Any],
    basis_contribution_digest: str,
    basis_spatial_index_digest: str,
    active_basis_per_sample_summary: Mapping[str, Any],
    source_basis_ids: Sequence[str],
    source_local_patch_ids: Sequence[str],
    source_record_ids: Sequence[str],
) -> dict[str, Any]:
    points = [[_finite_number(value, name="sample_point") for value in point] for point in sample_points_world_3d]
    record = {
        "schema": IMPLICIT_FIELD_EVALUATION_SCHEMA,
        "evaluation_id": str(evaluation_id),
        "implicit_field_state_id": str(implicit_field_state_id),
        "tick": int(tick),
        "sample_points_world_3d_digest": _canonical_digest(points),
        "sample_count": len(points),
        "channel_names": [str(channel) for channel in channel_names],
        "evaluation_summary": dict(evaluation_summary),
        "basis_contribution_digest": str(basis_contribution_digest),
        "basis_spatial_index_digest": str(basis_spatial_index_digest),
        "active_basis_per_sample_summary": dict(active_basis_per_sample_summary),
        "source_basis_ids": [str(value) for value in source_basis_ids],
        "source_local_patch_ids": [str(value) for value in source_local_patch_ids],
        "source_record_ids": [str(value) for value in source_record_ids],
        "is_authority_state": False,
    }
    validate_implicit_field_evaluation_record(record)
    return record


def validate_implicit_field_evaluation_record(record: Mapping[str, Any]) -> None:
    if record.get("schema") != IMPLICIT_FIELD_EVALUATION_SCHEMA:
        raise ValueError("implicit field evaluation record schema mismatch")
    if record.get("is_authority_state") is not False:
        raise ValueError("implicit field evaluation record must be non-authority")
    if int(record.get("sample_count", 0)) <= 0:
        raise ValueError("implicit field evaluation requires samples")
    if not record.get("sample_points_world_3d_digest") or not record.get("basis_contribution_digest"):
        raise ValueError("implicit field evaluation requires digests")
    if not record.get("basis_spatial_index_digest"):
        raise ValueError("implicit field evaluation requires basis_spatial_index_digest")
    summary = record.get("active_basis_per_sample_summary")
    if not isinstance(summary, Mapping) or "avg" not in summary or "max" not in summary:
        raise ValueError("implicit field evaluation requires active basis summary")
    if not record.get("source_basis_ids"):
        raise ValueError("implicit field evaluation requires source basis ids")
    _assert_no_forbidden_keys(record)


def build_implicit_field_authority_certificate(
    certificate_id: str,
    implicit_field_state: Mapping[str, Any],
    source_basis_ids: Sequence[str],
    source_evaluation_ids: Sequence[str],
    source_ray_sample_record_ids: Sequence[str],
    source_refinement_patch_ids: Sequence[str],
    validity_region_world: Mapping[str, Any],
    validity_tick_window: Sequence[int],
    error_bounds: Mapping[str, Any],
    completion_input_digest: str,
    source_record_ids: Sequence[str],
) -> dict[str, Any]:
    validate_implicit_field_state(implicit_field_state)
    record = {
        "schema": IMPLICIT_FIELD_AUTHORITY_CERTIFICATE_SCHEMA,
        "certificate_id": str(certificate_id),
        "implicit_field_state_id": str(implicit_field_state["implicit_field_state_id"]),
        "state_digest": str(implicit_field_state["state_digest"]),
        "source_basis_ids": [str(value) for value in source_basis_ids],
        "source_evaluation_ids": [str(value) for value in source_evaluation_ids],
        "source_ray_sample_record_ids": [str(value) for value in source_ray_sample_record_ids],
        "source_refinement_patch_ids": [str(value) for value in source_refinement_patch_ids],
        "validity_region_world": dict(validity_region_world),
        "validity_tick_window": [int(value) for value in validity_tick_window],
        "error_bounds": dict(error_bounds),
        "completion_input_digest": str(completion_input_digest),
        "source_record_ids": [str(value) for value in source_record_ids],
        "is_authority_state": False,
    }
    validate_implicit_field_authority_certificate(record, implicit_field_state)
    return record


def validate_implicit_field_authority_certificate(
    record: Mapping[str, Any],
    implicit_field_state: Mapping[str, Any],
) -> None:
    if record.get("schema") != IMPLICIT_FIELD_AUTHORITY_CERTIFICATE_SCHEMA:
        raise ValueError("implicit field authority certificate schema mismatch")
    if record.get("is_authority_state") is not False:
        raise ValueError("implicit field authority certificate must be non-authority")
    if record.get("state_digest") != implicit_field_state.get("state_digest"):
        raise ValueError("implicit field authority certificate state digest mismatch")
    required_bounds = {
        "compact_support_leak",
        "ray_replay_mismatch",
        "occlusion_response_error",
        "local_refinement_correction_energy",
        "stability_margin",
        "coefficient_clamp_saturation_ratio",
        "boundary_temporal_flicker",
        "active_basis_per_sample_max",
    }
    if not required_bounds.issubset(set(record.get("error_bounds", {}))):
        raise ValueError("implicit field authority certificate missing error bounds")
    if not record.get("completion_input_digest"):
        raise ValueError("implicit field authority certificate requires completion_input_digest")
    _assert_no_forbidden_keys(record)
