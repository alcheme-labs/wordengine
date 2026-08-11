from __future__ import annotations

from collections import defaultdict
import math
from typing import Any, Mapping, Sequence

from world_engine.implicit_field import (
    build_implicit_field_state,
    validate_implicit_field_basis,
    validate_implicit_field_state,
)


DEFAULT_DECAY = 0.96
DEFAULT_COEFFICIENT_ABS_MAX = 8.0
DEFAULT_CLAMP_SATURATION_RATIO_MAX = 0.05
ENERGY_RESIDUAL_TAU_ABS = 1e-10
ENERGY_RESIDUAL_TAU_REL = 1e-12
MAX_LOCAL_ENERGY_SCOPES = 64


def _basis_id(record: Mapping[str, Any]) -> str:
    return str(record.get("basis_id", ""))


def _as_projection(input_projection: Mapping[str, Mapping[str, float]] | None) -> dict[str, dict[str, float]]:
    if input_projection is None:
        return {}
    return {
        str(basis_id): {str(channel): float(value) for channel, value in channels.items()}
        for basis_id, channels in input_projection.items()
    }


def _merge_projections(
    left: Mapping[str, Mapping[str, float]],
    right: Mapping[str, Mapping[str, float]],
) -> dict[str, dict[str, float]]:
    merged = {basis_id: dict(channels) for basis_id, channels in left.items()}
    for basis_id, channels in right.items():
        for channel, value in channels.items():
            merged.setdefault(basis_id, {})
            merged_value = merged[basis_id].get(channel, 0.0) + float(value)
            if not math.isfinite(merged_value):
                raise ValueError("input projection merge must be finite")
            merged[basis_id][channel] = merged_value
    return merged


def _validate_projection(
    projection: Mapping[str, Mapping[str, float]],
    *,
    bases_by_id: Mapping[str, Mapping[str, Any]],
) -> None:
    for basis_id, channels in projection.items():
        basis = bases_by_id.get(basis_id)
        if basis is None:
            raise ValueError("input projection references undeclared basis")
        declared_channels = set(map(str, basis.get("channel_weights", {})))
        for channel, value in channels.items():
            if channel not in declared_channels:
                raise ValueError("input projection references undeclared channel")
            if not math.isfinite(float(value)):
                raise ValueError("input projection values must be finite")


def _add_projection(
    coefficients: Mapping[str, Mapping[str, float]],
    projection: Mapping[str, Mapping[str, float]],
) -> dict[str, dict[str, float]]:
    result = {basis_id: dict(channels) for basis_id, channels in coefficients.items()}
    for basis_id, channels in projection.items():
        for channel, value in channels.items():
            result.setdefault(basis_id, {})
            result[basis_id][channel] = result[basis_id].get(channel, 0.0) + float(value)
    return result


def _cap_density_projection(
    projection: Mapping[str, Mapping[str, float]],
    baseline: Mapping[str, Mapping[str, float]],
) -> dict[str, dict[str, float]]:
    realized = {basis_id: dict(channels) for basis_id, channels in projection.items()}
    for basis_id, channels in projection.items():
        if "density" not in channels or float(channels["density"]) == 0.0:
            continue
        density_before = float(baseline.get(basis_id, {}).get("density", 0.0))
        if density_before < 0.0:
            raise ValueError("density input requires a non-negative post-coupling baseline")
        density_input = float(channels["density"])
        if density_input < 0.0:
            realized[basis_id]["density"] = max(density_input, -density_before)
    return realized


def _apply_coupling(
    decayed_coefficients: Mapping[str, Mapping[str, float]],
    source_coefficients: Mapping[str, Mapping[str, float]],
    edges: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, float]]:
    result = {basis_id: dict(channels) for basis_id, channels in decayed_coefficients.items()}
    for edge in edges:
        from_basis_id = str(edge["from_basis_id"])
        to_basis_id = str(edge["to_basis_id"])
        weight = float(edge.get("weight", 0.0))
        for channel, value in source_coefficients.get(from_basis_id, {}).items():
            result.setdefault(to_basis_id, {})
            result[to_basis_id][str(channel)] = result[to_basis_id].get(str(channel), 0.0) + float(value) * weight
    return result


def _density_energy(
    coefficients: Mapping[str, Mapping[str, float]],
    *,
    basis_ids: Sequence[str],
    bases_by_id: Mapping[str, Mapping[str, Any]],
    kappa: Mapping[str, float],
) -> float:
    return 0.5 * math.fsum(
        float(kappa[basis_id])
        * (
            float(bases_by_id[basis_id].get("channel_weights", {}).get("density", 0.0))
            * float(coefficients.get(basis_id, {}).get("density", 0.0))
        )
        ** 2
        for basis_id in basis_ids
    )


def _local_energy_scopes(
    scopes: Mapping[str, Mapping[str, float]] | None,
    *,
    basis_ids: Sequence[str],
) -> list[tuple[str, dict[str, float]]]:
    if scopes is None:
        return []
    if not isinstance(scopes, Mapping):
        raise ValueError("local_energy_scopes must be a mapping")
    if len(scopes) > MAX_LOCAL_ENERGY_SCOPES:
        raise ValueError("implicit runtime exceeds active local energy scope budget")
    known_basis_ids = set(basis_ids)
    result: list[tuple[str, dict[str, float]]] = []
    for raw_scope_id in sorted(scopes, key=str):
        scope_id = str(raw_scope_id)
        if not scope_id or scope_id == "fixed_scene":
            raise ValueError("local energy scope requires a non-reserved scope_id")
        raw_kappa = scopes[raw_scope_id]
        if not isinstance(raw_kappa, Mapping):
            raise ValueError("local energy scope kappa must be a mapping")
        if set(map(str, raw_kappa)) - known_basis_ids:
            raise ValueError("local energy scope references undeclared basis")
        kappa = {basis_id: float(raw_kappa.get(basis_id, 0.0)) for basis_id in basis_ids}
        if any(not math.isfinite(value) or value < 0.0 for value in kappa.values()):
            raise ValueError("local energy scope kappa must be finite and non-negative")
        if not any(value > 0.0 for value in kappa.values()):
            raise ValueError("local energy scope requires positive support")
        result.append((scope_id, kappa))
    return result


def _density_energy_ledger(
    *,
    scope_id: str,
    scope_kind: str,
    kappa: Mapping[str, float],
    state_coefficients: Mapping[str, Mapping[str, float]],
    decayed_coefficients: Mapping[str, Mapping[str, float]],
    coupled_coefficients: Mapping[str, Mapping[str, float]],
    post_user_coefficients: Mapping[str, Mapping[str, float]],
    unclipped_coefficients: Mapping[str, Mapping[str, float]],
    next_coefficients: Mapping[str, Mapping[str, float]],
    edges: Sequence[Mapping[str, Any]],
    basis_ids: Sequence[str],
    bases_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    internal_edges = [
        edge
        for edge in edges
        if (float(kappa[str(edge["from_basis_id"])]) > 0.0)
        == (float(kappa[str(edge["to_basis_id"])]) > 0.0)
    ]
    internal_coefficients = _apply_coupling(decayed_coefficients, state_coefficients, internal_edges)

    energy_before = _density_energy(state_coefficients, basis_ids=basis_ids, bases_by_id=bases_by_id, kappa=kappa)
    energy_after_decay = _density_energy(decayed_coefficients, basis_ids=basis_ids, bases_by_id=bases_by_id, kappa=kappa)
    energy_after_internal = _density_energy(internal_coefficients, basis_ids=basis_ids, bases_by_id=bases_by_id, kappa=kappa)
    energy_after_coupling = _density_energy(coupled_coefficients, basis_ids=basis_ids, bases_by_id=bases_by_id, kappa=kappa)
    energy_after_user = _density_energy(post_user_coefficients, basis_ids=basis_ids, bases_by_id=bases_by_id, kappa=kappa)
    energy_before_clip = _density_energy(unclipped_coefficients, basis_ids=basis_ids, bases_by_id=bases_by_id, kappa=kappa)
    energy_after = _density_energy(next_coefficients, basis_ids=basis_ids, bases_by_id=bases_by_id, kappa=kappa)

    d_decay = energy_before - energy_after_decay
    x_internal = energy_after_internal - energy_after_decay
    f_boundary_proxy = energy_after_coupling - energy_after_internal
    i_user = energy_after_user - energy_after_coupling
    i_feedback = energy_before_clip - energy_after_user
    d_clip = energy_before_clip - energy_after
    residual = (energy_after - energy_before) - (
        x_internal + f_boundary_proxy + i_user + i_feedback - d_decay - d_clip
    )
    residual_tolerance = ENERGY_RESIDUAL_TAU_ABS + ENERGY_RESIDUAL_TAU_REL * max(
        1.0,
        energy_before,
        energy_after,
        math.fsum(abs(value) for value in (d_decay, x_internal, f_boundary_proxy, i_user, i_feedback, d_clip)),
    )
    if not math.isfinite(residual) or abs(residual) > residual_tolerance:
        raise ValueError("implicit density energy ledger residual exceeds fixed tolerance")
    return {
        "scope_id": scope_id,
        "scope_kind": scope_kind,
        "kappa": dict(kappa),
        "energy_before": energy_before,
        "energy_after_decay": energy_after_decay,
        "energy_after_internal": energy_after_internal,
        "energy_after_coupling": energy_after_coupling,
        "energy_after_user": energy_after_user,
        "energy_before_clip": energy_before_clip,
        "energy_after": energy_after,
        "d_decay": d_decay,
        "x_internal": x_internal,
        "f_boundary_proxy": f_boundary_proxy,
        "i_user": i_user,
        "i_feedback": i_feedback,
        "d_clip": d_clip,
        "residual": residual,
        "residual_tolerance": residual_tolerance,
    }


def _validate_sparse_coupling(
    state: Mapping[str, Any],
    *,
    decay: float,
    non_zero_coupling_per_basis_max: int,
) -> dict[str, float]:
    decay = float(decay)
    if not math.isfinite(decay) or decay < 0.0 or decay > 0.98:
        raise ValueError("implicit runtime decay must be finite and between 0 and 0.98")
    basis_ids = {str(value) for value in state.get("basis_ids", [])}
    row_sums: dict[str, float] = defaultdict(float)
    edge_counts: dict[str, int] = defaultdict(int)
    for edge in state.get("sparse_coupling_edges", []):
        from_basis_id = str(edge.get("from_basis_id"))
        to_basis_id = str(edge.get("to_basis_id"))
        if from_basis_id not in basis_ids or to_basis_id not in basis_ids:
            raise ValueError("implicit sparse coupling edge references undeclared basis")
        weight = float(edge.get("weight", 0.0))
        if not math.isfinite(weight):
            raise ValueError("implicit sparse coupling weight must be finite")
        row_sums[from_basis_id] += abs(weight)
        edge_counts[from_basis_id] += 1
        if edge_counts[from_basis_id] > non_zero_coupling_per_basis_max:
            raise ValueError("implicit sparse coupling exceeds per-basis edge budget")
    row_bound = 0.98 - decay
    for basis_id, row_sum in row_sums.items():
        if row_sum > row_bound + 1e-12:
            raise ValueError(f"implicit sparse coupling row sum exceeds stability bound for {basis_id}")
    return dict(row_sums)


def advance_implicit_field_state(
    state: Mapping[str, Any],
    bases: Sequence[Mapping[str, Any]],
    *,
    input_projection: Mapping[str, Mapping[str, float]] | None = None,
    user_input_projection: Mapping[str, Mapping[str, float]] | None = None,
    feedback_input_projection: Mapping[str, Mapping[str, float]] | None = None,
    local_energy_scopes: Mapping[str, Mapping[str, float]] | None = None,
    decay: float = DEFAULT_DECAY,
    coefficient_abs_max: float = DEFAULT_COEFFICIENT_ABS_MAX,
    clamp_saturation_ratio_max: float = DEFAULT_CLAMP_SATURATION_RATIO_MAX,
    non_zero_coupling_per_basis_max: int = 8,
) -> dict[str, Any]:
    validate_implicit_field_state(state)
    basis_ids = [str(value) for value in state.get("basis_ids", [])]
    bases_by_id = {_basis_id(basis): basis for basis in bases}
    if set(basis_ids) - set(bases_by_id):
        raise ValueError("implicit runtime is missing basis records")
    for basis in bases:
        validate_implicit_field_basis(basis)
    if len(basis_ids) > 256:
        raise ValueError("implicit runtime basis count exceeds M6 budget")
    coefficient_abs_max = float(coefficient_abs_max)
    if not math.isfinite(coefficient_abs_max) or coefficient_abs_max <= 0.0:
        raise ValueError("coefficient_abs_max must be finite and positive")
    clamp_saturation_ratio_max = float(clamp_saturation_ratio_max)
    if not math.isfinite(clamp_saturation_ratio_max) or not 0.0 <= clamp_saturation_ratio_max <= 1.0:
        raise ValueError("clamp_saturation_ratio_max must be finite and between 0 and 1")
    row_sums = _validate_sparse_coupling(
        state,
        decay=decay,
        non_zero_coupling_per_basis_max=non_zero_coupling_per_basis_max,
    )
    if input_projection is not None and user_input_projection is not None:
        raise ValueError("input_projection and user_input_projection are aliases; provide only one")
    raw_user_projection = _as_projection(user_input_projection if user_input_projection is not None else input_projection)
    raw_feedback_projection = _as_projection(feedback_input_projection)
    _validate_projection(raw_user_projection, bases_by_id=bases_by_id)
    _validate_projection(raw_feedback_projection, bases_by_id=bases_by_id)
    raw_projection = _merge_projections(raw_user_projection, raw_feedback_projection)
    if set(raw_projection) - set(basis_ids):
        raise ValueError("input projection references undeclared basis")
    local_scopes = _local_energy_scopes(local_energy_scopes, basis_ids=basis_ids)

    state_coefficients = state.get("basis_coefficients", {})
    decayed_coefficients: dict[str, dict[str, float]] = {
        basis_id: {str(channel): float(value) * float(decay) for channel, value in state.get("basis_coefficients", {}).get(basis_id, {}).items()}
        for basis_id in basis_ids
    }
    edges = list(state.get("sparse_coupling_edges", []))
    coupled_coefficients = _apply_coupling(decayed_coefficients, state_coefficients, edges)

    realized_user_projection = _cap_density_projection(raw_user_projection, coupled_coefficients)
    post_user_coefficients = _add_projection(coupled_coefficients, realized_user_projection)
    realized_feedback_projection = _cap_density_projection(raw_feedback_projection, post_user_coefficients)
    projection = _merge_projections(realized_user_projection, realized_feedback_projection)
    unclipped_coefficients = _add_projection(post_user_coefficients, realized_feedback_projection)
    next_coefficients = {basis_id: dict(channels) for basis_id, channels in unclipped_coefficients.items()}

    clamped = 0
    total = 0
    for basis_id, channels in next_coefficients.items():
        for channel, value in list(channels.items()):
            total += 1
            if value > coefficient_abs_max:
                channels[channel] = coefficient_abs_max
                clamped += 1
            elif value < -coefficient_abs_max:
                channels[channel] = -coefficient_abs_max
                clamped += 1
    saturation_ratio = clamped / max(1, total)
    if saturation_ratio > clamp_saturation_ratio_max + 1e-12:
        raise ValueError("implicit runtime relies on excessive coefficient clamping")

    scopes = [("fixed_scene", "fixed_scene", {basis_id: 1.0 for basis_id in basis_ids})]
    scopes.extend((scope_id, "local", kappa) for scope_id, kappa in local_scopes)
    ledgers = [
        _density_energy_ledger(
            scope_id=scope_id,
            scope_kind=scope_kind,
            kappa=kappa,
            state_coefficients=state_coefficients,
            decayed_coefficients=decayed_coefficients,
            coupled_coefficients=coupled_coefficients,
            post_user_coefficients=post_user_coefficients,
            unclipped_coefficients=unclipped_coefficients,
            next_coefficients=next_coefficients,
            edges=edges,
            basis_ids=basis_ids,
            bases_by_id=bases_by_id,
        )
        for scope_id, scope_kind, kappa in scopes
    ]

    sparse_edge_count = len(edges)
    runtime_cost_summary = {
        "basis_count": len(basis_ids),
        "sparse_edge_count": sparse_edge_count,
        "dense_volume_used": False,
        "active_basis_count": len([basis_id for basis_id, channels in next_coefficients.items() if channels]),
        "coupling_row_sum_abs_max": max(row_sums.values()) if row_sums else 0.0,
        "coefficient_clamp_saturation_ratio": saturation_ratio,
        "coefficient_abs_max": coefficient_abs_max,
        "update_cost_units": len(basis_ids) + sparse_edge_count,
    }
    return build_implicit_field_state(
        implicit_field_state_id=str(state["implicit_field_state_id"]),
        tick=int(state.get("tick", 0)) + 1,
        basis_ids=basis_ids,
        basis_layout_digest=str(state["basis_layout_digest"]),
        basis_spatial_index_digest=str(state["basis_spatial_index_digest"]),
        basis_coefficients=next_coefficients,
        sparse_coupling_edges=list(state.get("sparse_coupling_edges", [])),
        background_model=dict(state.get("background_model", {})),
        active_local_patch_ids=list(state.get("active_local_patch_ids", [])),
        validity_region_world=dict(state.get("validity_region_world", {})),
        energy_summary={
            "total_abs_coefficient": sum(abs(float(value)) for channels in next_coefficients.values() for value in channels.values()),
            "density_response": {
                "raw_user_projection": raw_user_projection,
                "realized_user_projection": realized_user_projection,
                "raw_feedback_projection": raw_feedback_projection,
                "realized_feedback_projection": realized_feedback_projection,
                "merged_realized_projection": projection,
                "ledgers": ledgers,
            },
        },
        source_record_ids=[*state.get("source_record_ids", []), f"implicit-field-runtime-step::{state.get('tick', 0)}"],
        authority_status=str(state.get("authority_status", "candidate")),
        runtime_cost_summary=runtime_cost_summary,
    )
