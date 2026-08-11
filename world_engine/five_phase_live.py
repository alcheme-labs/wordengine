from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import replace
from typing import Any, Mapping, Sequence

from world_engine.contracts import FieldState
from world_engine.five_phase import (
    EPS,
    FORBIDDEN_AUTHORITY_SHORTCUT_KEYS,
    FivePhaseAgentStateRecord,
    FivePhaseFeedbackRecord,
    FivePhasePatternRecord,
    FivePhaseResidualConstraintRecord,
)
from world_engine.five_phase_extraction import extract_five_phase_field
from world_engine.five_phase_patterns import (
    build_five_phase_live_response_metrics,
    build_five_phase_response_context,
    detect_five_phase_patterns,
)
from world_engine.five_phase_runtime import (
    build_agent_repair_feedback,
    build_agent_state_from_pattern,
    build_residual_constraint_from_trace,
    derive_five_phase_constraints,
)
from world_engine.five_phase_traces import build_five_phase_trace
from world_engine.implicit_field import evaluate_implicit_field


FORBIDDEN_FIVE_PHASE_LIVE_SHORTCUT_KEYS = {
    "viewer_color",
    "css_color",
    "viewer_shape",
    "viewer_label",
    "viewer_transform",
    "canvas_pixels",
    "mesh",
    "sprite",
    "texture",
    "object_asset_id",
    "material_label",
}

FEEDBACK_FINITE_DIFFERENCE_ETA = 1e-4
FEEDBACK_SENSITIVITY_MIN = 1e-8
FEEDBACK_DENSITY_GAIN = 0.03
FEEDBACK_SPATIAL_CANDIDATE_LIMIT = 8


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def reject_five_phase_live_shortcuts(value: Any, *, path: str = "record") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key) in FORBIDDEN_AUTHORITY_SHORTCUT_KEYS or str(key) in FORBIDDEN_FIVE_PHASE_LIVE_SHORTCUT_KEYS:
                raise ValueError(f"forbidden five phase live viewer shortcut at {path}: {key}")
            reject_five_phase_live_shortcuts(child, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            reject_five_phase_live_shortcuts(child, path=f"{path}[{index}]")


def _finite_bounds(region: Mapping[str, Any]) -> tuple[list[float], list[float]]:
    lower = [float(value) for value in region.get("min", [])]
    upper = [float(value) for value in region.get("max", [])]
    if len(lower) != 3 or len(upper) != 3:
        raise ValueError("implicit validity_region_world must include 3D min/max")
    if any(upper[index] <= lower[index] for index in range(3)):
        raise ValueError("implicit validity_region_world must have positive extent")
    return lower, upper


def _sample_points(region: Mapping[str, Any], grid_shape: Sequence[int]) -> list[list[float]]:
    width, height = int(grid_shape[0]), int(grid_shape[1])
    if width <= 1 or height <= 1:
        raise ValueError("five phase live bridge grid must be at least 2x2")
    lower, upper = _finite_bounds(region)
    z = (lower[2] + upper[2]) / 2.0
    points: list[list[float]] = []
    for row in range(height):
        y = lower[1] + (upper[1] - lower[1]) * ((row + 0.5) / height)
        for col in range(width):
            x = lower[0] + (upper[0] - lower[0]) * ((col + 0.5) / width)
            points.append([x, y, z])
    return points


def _grid_from_samples(
    samples: Sequence[Mapping[str, float]],
    *,
    channel_name: str,
    grid_shape: Sequence[int],
) -> list[list[float]]:
    width, height = int(grid_shape[0]), int(grid_shape[1])
    values = [float(sample.get(channel_name, 0.0)) for sample in samples]
    if any(not math.isfinite(value) for value in values):
        raise ValueError("five phase live bridge samples must be finite")
    if len(values) != width * height:
        raise ValueError("five phase live bridge sample count mismatch")
    return [values[row * width : (row + 1) * width] for row in range(height)]


def _resolve_source_channel(
    implicit_basis_records: Sequence[Mapping[str, Any]],
    requested_channel_name: str,
) -> str:
    available = {
        str(channel)
        for basis in implicit_basis_records
        for channel in (basis.get("channel_weights") or {})
        if abs(float((basis.get("channel_weights") or {}).get(channel, 0.0))) > 0.0
    }
    if requested_channel_name in available:
        return requested_channel_name
    if requested_channel_name == "pattern" and "density" in available:
        return "density"
    raise ValueError(f"implicit field has no nonzero basis channel for {requested_channel_name!r}")


def _support_energy(field_state: FieldState, bounds: Sequence[int], *, channel_name: str = "pattern") -> float:
    grid = field_state.channels[channel_name]
    height = len(grid)
    width = len(grid[0]) if height else 0
    x0, y0, x1, y1 = (int(value) for value in bounds)
    if not (0 <= x0 <= x1 < width and 0 <= y0 <= y1 < height):
        raise ValueError("five phase support bounds are outside the live bridge grid")
    coordinate_frame = field_state.payload.get("coordinate_frame", {})
    extent = [float(value) for value in coordinate_frame.get("world_extent", [])]
    if len(extent) != 2 or any(value <= 0.0 for value in extent):
        raise ValueError("five phase live bridge requires a positive 2D world extent")
    cell_area = (extent[0] / width) * (extent[1] / height)
    return 0.5 * cell_area * math.fsum(
        float(grid[row][col]) ** 2
        for row in range(y0, y1 + 1)
        for col in range(x0, x1 + 1)
    )


def _support_points(
    region: Mapping[str, Any],
    grid_shape: Sequence[int],
    bounds: Sequence[int],
) -> list[list[float]]:
    width, height = int(grid_shape[0]), int(grid_shape[1])
    x0, y0, x1, y1 = (int(value) for value in bounds)
    if not (0 <= x0 <= x1 < width and 0 <= y0 <= y1 < height):
        raise ValueError("five phase support bounds are outside the implicit sampling grid")
    points = _sample_points(region, grid_shape)
    return [
        points[row * width + col]
        for row in range(y0, y1 + 1)
        for col in range(x0, x1 + 1)
    ]


def _implicit_support_energy(
    *,
    implicit_field_state: Mapping[str, Any],
    implicit_basis_records: Sequence[Mapping[str, Any]],
    basis_spatial_index: Mapping[str, Any],
    support_bounds_grid: Sequence[int],
    grid_shape: Sequence[int],
    source_channel_name: str,
) -> float:
    points = _support_points(
        implicit_field_state.get("validity_region_world", {}),
        grid_shape,
        support_bounds_grid,
    )
    evaluation = evaluate_implicit_field(
        implicit_field_state,
        implicit_basis_records,
        points,
        channel_names=[source_channel_name],
        basis_spatial_index=basis_spatial_index,
    )
    lower, upper = _finite_bounds(implicit_field_state.get("validity_region_world", {}))
    width, height = int(grid_shape[0]), int(grid_shape[1])
    cell_area = ((upper[0] - lower[0]) / width) * ((upper[1] - lower[1]) / height)
    return 0.5 * cell_area * math.fsum(
        float(sample[source_channel_name]) ** 2
        for sample in evaluation["sample_values"]
    )


def measure_five_phase_support_energy(
    *,
    implicit_field_state: Mapping[str, Any],
    implicit_basis_records: Sequence[Mapping[str, Any]],
    basis_spatial_index: Mapping[str, Any],
    support_bounds_grid: Sequence[int],
    grid_shape: Sequence[int],
    source_channel_name: str,
) -> float:
    """Measure the declared fixed-cell support energy through the canonical evaluator."""

    return _implicit_support_energy(
        implicit_field_state=implicit_field_state,
        implicit_basis_records=implicit_basis_records,
        basis_spatial_index=basis_spatial_index,
        support_bounds_grid=support_bounds_grid,
        grid_shape=grid_shape,
        source_channel_name=source_channel_name,
    )


def build_five_phase_identity_support_kappa(
    *,
    implicit_field_state: Mapping[str, Any],
    implicit_basis_records: Sequence[Mapping[str, Any]],
    support_bounds_grid: Sequence[int],
    grid_shape: Sequence[int],
) -> dict[str, float]:
    """Map a fixed Pattern cell set to immutable, dimensionless basis participation."""

    points = _support_points(
        implicit_field_state.get("validity_region_world", {}),
        grid_shape,
        support_bounds_grid,
    )
    if not points:
        raise ValueError("five phase identity support requires at least one sample point")
    kappa: dict[str, float] = {}
    for basis in implicit_basis_records:
        basis_id = str(basis.get("basis_id", ""))
        if not basis_id or basis_id in kappa:
            raise ValueError("five phase identity support requires unique non-empty basis IDs")
        density_weight = float(basis.get("channel_weights", {}).get("density", 0.0))
        support = basis.get("support_region_world", {})
        lower = [float(value) for value in support.get("min", [])]
        upper = [float(value) for value in support.get("max", [])]
        if len(lower) != 3 or len(upper) != 3 or any(
            not math.isfinite(value) for value in [*lower, *upper, density_weight]
        ):
            raise ValueError("five phase identity support requires finite basis geometry")
        if any(upper[index] <= lower[index] for index in range(3)):
            raise ValueError("five phase identity support requires positive basis extent")
        overlap_count = sum(
            1
            for point in points
            if all(lower[index] <= point[index] <= upper[index] for index in range(3))
        )
        kappa[basis_id] = (
            float(overlap_count) / float(len(points))
            if abs(density_weight) > 0.0
            else 0.0
        )
    if not any(value > 0.0 for value in kappa.values()):
        raise ValueError("five phase identity support has no density-capable basis participation")
    return kappa


def measure_five_phase_density_kappa_norm(
    *,
    coefficient_projection: Mapping[str, Mapping[str, float]],
    implicit_basis_records: Sequence[Mapping[str, Any]],
    identity_support_kappa: Mapping[str, float],
) -> float:
    """Compute the plan's weighted density coefficient norm on one fixed support."""

    bases_by_id = {str(basis.get("basis_id", "")): basis for basis in implicit_basis_records}
    if not bases_by_id or "" in bases_by_id or len(bases_by_id) != len(implicit_basis_records):
        raise ValueError("five phase density norm requires unique non-empty basis IDs")
    if set(map(str, identity_support_kappa)) != set(bases_by_id):
        raise ValueError("five phase identity support kappa must cover every declared basis exactly")
    unknown_projection = set(map(str, coefficient_projection)) - set(bases_by_id)
    if unknown_projection:
        raise ValueError("five phase density norm projection references an undeclared basis")
    terms: list[float] = []
    for basis_id, basis in bases_by_id.items():
        kappa = float(identity_support_kappa[basis_id])
        coefficient = float(coefficient_projection.get(basis_id, {}).get("density", 0.0))
        density_weight = float(basis.get("channel_weights", {}).get("density", 0.0))
        if any(not math.isfinite(value) for value in (kappa, coefficient, density_weight)) or kappa < 0.0:
            raise ValueError("five phase density norm inputs must be finite and kappa non-negative")
        terms.append(kappa * (density_weight * coefficient) ** 2)
    return math.sqrt(max(0.0, math.fsum(terms)))


def build_five_phase_transition_response_context(
    *,
    previous_pattern: FivePhasePatternRecord,
    previous_implicit_field_state: Mapping[str, Any],
    current_implicit_field_state: Mapping[str, Any],
    implicit_basis_records: Sequence[Mapping[str, Any]],
    basis_spatial_index: Mapping[str, Any],
    realized_user_input_projection: Mapping[str, Mapping[str, float]],
    realized_feedback_input_projection: Mapping[str, Mapping[str, float]],
    tick: int,
    relaxation_horizon_ticks: int = 8,
) -> dict[str, Any]:
    """Rebuild one matched Pattern's dimensionless live-response episode context."""

    payload = dict(previous_pattern.payload)
    identity_id = str(payload.get("pattern_identity_id") or previous_pattern.record_id)
    support_bounds = [
        int(value)
        for value in payload.get("identity_support_bounds_grid", previous_pattern.support_bounds_grid)
    ]
    grid_shape = [int(value) for value in payload.get("identity_support_grid_shape", [16, 16])]
    source_channel_name = str(payload.get("support_source_channel_name", "density"))
    kappa = build_five_phase_identity_support_kappa(
        implicit_field_state=previous_implicit_field_state,
        implicit_basis_records=implicit_basis_records,
        support_bounds_grid=support_bounds,
        grid_shape=grid_shape,
    )
    stored_kappa = payload.get("identity_support_kappa")
    if stored_kappa is not None and {
        str(key): float(value) for key, value in dict(stored_kappa).items()
    } != kappa:
        raise ValueError("five phase identity support kappa changed across one persistent identity")
    user_norm = measure_five_phase_density_kappa_norm(
        coefficient_projection=realized_user_input_projection,
        implicit_basis_records=implicit_basis_records,
        identity_support_kappa=kappa,
    )
    feedback_norm = measure_five_phase_density_kappa_norm(
        coefficient_projection=realized_feedback_input_projection,
        implicit_basis_records=implicit_basis_records,
        identity_support_kappa=kappa,
    )
    previous_end = int(payload.get("episode_end_tick", previous_pattern.tick))
    previous_status = str(payload.get("episode_status", "unperturbed"))
    continuing_episode = (
        previous_status in {"active", "relaxing"}
        and int(tick) <= previous_end
    )
    episode_started = user_norm > EPS and not continuing_episode
    previous_support_energy = measure_five_phase_support_energy(
        implicit_field_state=previous_implicit_field_state,
        implicit_basis_records=implicit_basis_records,
        basis_spatial_index=basis_spatial_index,
        support_bounds_grid=support_bounds,
        grid_shape=grid_shape,
        source_channel_name=source_channel_name,
    )
    current_support_energy = measure_five_phase_support_energy(
        implicit_field_state=current_implicit_field_state,
        implicit_basis_records=implicit_basis_records,
        basis_spatial_index=basis_spatial_index,
        support_bounds_grid=support_bounds,
        grid_shape=grid_shape,
        source_channel_name=source_channel_name,
    )
    previous_state_norm = measure_five_phase_density_kappa_norm(
        coefficient_projection=previous_implicit_field_state.get("basis_coefficients", {}),
        implicit_basis_records=implicit_basis_records,
        identity_support_kappa=kappa,
    )
    if episode_started:
        setpoint_energy = previous_support_energy
        setpoint_norm = previous_state_norm
        setpoint_state_id = str(previous_implicit_field_state["implicit_field_state_id"])
        setpoint_state_digest = str(previous_implicit_field_state["state_digest"])
    else:
        setpoint_energy = float(payload.get("support_energy_setpoint", previous_support_energy))
        setpoint_norm = float(payload.get("support_coefficient_norm_setpoint", previous_state_norm))
        setpoint_state_id = str(
            payload.get("support_setpoint_state_id", previous_implicit_field_state["implicit_field_state_id"])
        )
        setpoint_state_digest = str(
            payload.get("support_setpoint_state_digest", previous_implicit_field_state["state_digest"])
        )
    if not math.isfinite(setpoint_norm) or setpoint_norm < 0.0:
        raise ValueError("five phase support setpoint coefficient norm must be finite and non-negative")
    q_user = user_norm / max(setpoint_norm, EPS)
    q_feedback = feedback_norm / max(setpoint_norm, EPS)
    context = build_five_phase_response_context(
        previous_pattern=previous_pattern,
        pattern_identity_id=identity_id,
        tick=int(tick),
        realized_user_dose=q_user,
        realized_feedback_dose=q_feedback,
        relaxation_horizon_ticks=relaxation_horizon_ticks,
    )
    context.update(
        {
            "support_energy_prior": previous_support_energy,
            "support_energy_current": current_support_energy,
            "support_energy_setpoint": setpoint_energy,
            "support_coefficient_norm_setpoint": setpoint_norm,
            "support_setpoint_state_id": setpoint_state_id,
            "support_setpoint_state_digest": setpoint_state_digest,
            "identity_support_kappa": kappa,
            "identity_support_kappa_digest": _canonical_digest(kappa),
            "realized_user_input_norm_kappa": user_norm,
            "realized_feedback_input_norm_kappa": feedback_norm,
            "episode_started": episode_started,
        }
    )
    return context


def build_five_phase_initial_response_context(
    *,
    pattern_identity_id: str,
    support_bounds_grid: Sequence[int],
    grid_shape: Sequence[int],
    source_channel_name: str,
    implicit_field_state: Mapping[str, Any],
    implicit_basis_records: Sequence[Mapping[str, Any]],
    basis_spatial_index: Mapping[str, Any],
    tick: int,
) -> dict[str, Any]:
    """Build the zero-dose setpoint context for a newly observed Pattern identity."""

    kappa = build_five_phase_identity_support_kappa(
        implicit_field_state=implicit_field_state,
        implicit_basis_records=implicit_basis_records,
        support_bounds_grid=support_bounds_grid,
        grid_shape=grid_shape,
    )
    support_energy = measure_five_phase_support_energy(
        implicit_field_state=implicit_field_state,
        implicit_basis_records=implicit_basis_records,
        basis_spatial_index=basis_spatial_index,
        support_bounds_grid=support_bounds_grid,
        grid_shape=grid_shape,
        source_channel_name=source_channel_name,
    )
    setpoint_norm = measure_five_phase_density_kappa_norm(
        coefficient_projection=implicit_field_state.get("basis_coefficients", {}),
        implicit_basis_records=implicit_basis_records,
        identity_support_kappa=kappa,
    )
    context = build_five_phase_response_context(
        previous_pattern=None,
        pattern_identity_id=str(pattern_identity_id),
        tick=int(tick),
        realized_user_dose=0.0,
        realized_feedback_dose=0.0,
    )
    context.update(
        {
            "support_energy_prior": support_energy,
            "support_energy_current": support_energy,
            "support_energy_setpoint": support_energy,
            "support_coefficient_norm_setpoint": setpoint_norm,
            "support_setpoint_state_id": str(implicit_field_state["implicit_field_state_id"]),
            "support_setpoint_state_digest": str(implicit_field_state["state_digest"]),
            "identity_support_kappa": kappa,
            "identity_support_kappa_digest": _canonical_digest(kappa),
            "realized_user_input_norm_kappa": 0.0,
            "realized_feedback_input_norm_kappa": 0.0,
            "episode_started": False,
        }
    )
    return context


def materialize_five_phase_pattern_response(
    *,
    previous_pattern: FivePhasePatternRecord | None,
    pattern_identity_id: str,
    response_context: Mapping[str, Any],
    support_bounds_grid: Sequence[int],
    grid_shape: Sequence[int],
    source_channel_name: str,
    implicit_field_state: Mapping[str, Any],
    tick: int,
) -> tuple[float, dict[str, Any]]:
    """Materialize the exact live Pattern response payload shared by runtime and validators."""

    kappa = {str(key): float(value) for key, value in dict(response_context["identity_support_kappa"]).items()}
    stability_score, response_payload = build_five_phase_live_response_metrics(
        context=response_context,
        previous_pattern=previous_pattern,
        pattern_identity_id=str(pattern_identity_id),
        tick=int(tick),
        measured_support_energy=float(response_context["support_energy_current"]),
    )
    return stability_score, {
        **response_payload,
        "identity_support_bounds_grid": [int(value) for value in support_bounds_grid],
        "identity_support_grid_shape": [int(value) for value in grid_shape],
        "identity_support_kappa": kappa,
        "identity_support_kappa_digest": _canonical_digest(kappa),
        "support_source_channel_name": str(source_channel_name),
        "support_coefficient_norm_setpoint": float(response_context["support_coefficient_norm_setpoint"]),
        "support_setpoint_state_id": str(response_context["support_setpoint_state_id"]),
        "support_setpoint_state_digest": str(response_context["support_setpoint_state_digest"]),
        "realized_user_input_norm_kappa": float(response_context["realized_user_input_norm_kappa"]),
        "realized_feedback_input_norm_kappa": float(response_context["realized_feedback_input_norm_kappa"]),
        "episode_started": bool(response_context["episode_started"]),
        "source_implicit_field_state_id": str(implicit_field_state["implicit_field_state_id"]),
        "source_implicit_field_state_digest": str(implicit_field_state["state_digest"]),
    }


def _state_with_density_delta(
    implicit_field_state: Mapping[str, Any],
    *,
    basis_id: str,
    density_delta: float,
) -> dict[str, Any]:
    preview = copy.deepcopy(dict(implicit_field_state))
    coefficients = copy.deepcopy(dict(preview.get("basis_coefficients", {})))
    if basis_id not in coefficients:
        raise ValueError("feedback target basis is absent from the implicit state")
    channels = dict(coefficients[basis_id])
    channels["density"] = float(channels.get("density", 0.0)) + float(density_delta)
    coefficients[basis_id] = channels
    preview["basis_coefficients"] = coefficients
    preview["state_digest"] = _canonical_digest(
        {key: value for key, value in preview.items() if key != "state_digest"}
    )
    return preview


def _support_sensitivity(
    *,
    implicit_field_state: Mapping[str, Any],
    implicit_basis_records: Sequence[Mapping[str, Any]],
    basis_spatial_index: Mapping[str, Any],
    support_bounds_grid: Sequence[int],
    grid_shape: Sequence[int],
    source_channel_name: str,
    basis_id: str,
    eta: float,
) -> float:
    eta = float(eta)
    if not math.isfinite(eta) or eta <= 0.0:
        raise ValueError("five phase feedback eta must be finite and positive")
    plus = _implicit_support_energy(
        implicit_field_state=_state_with_density_delta(
            implicit_field_state,
            basis_id=basis_id,
            density_delta=eta,
        ),
        implicit_basis_records=implicit_basis_records,
        basis_spatial_index=basis_spatial_index,
        support_bounds_grid=support_bounds_grid,
        grid_shape=grid_shape,
        source_channel_name=source_channel_name,
    )
    minus = _implicit_support_energy(
        implicit_field_state=_state_with_density_delta(
            implicit_field_state,
            basis_id=basis_id,
            density_delta=-eta,
        ),
        implicit_basis_records=implicit_basis_records,
        basis_spatial_index=basis_spatial_index,
        support_bounds_grid=support_bounds_grid,
        grid_shape=grid_shape,
        source_channel_name=source_channel_name,
    )
    sensitivity = (plus - minus) / (2.0 * eta)
    if not math.isfinite(sensitivity):
        raise ValueError("five phase feedback sensitivity must be finite")
    return sensitivity


def _centroid_world(
    pattern: FivePhasePatternRecord,
    *,
    region: Mapping[str, Any],
    grid_shape: Sequence[int],
) -> list[float]:
    width, height = int(grid_shape[0]), int(grid_shape[1])
    lower, upper = _finite_bounds(region)
    return [
        lower[0] + (upper[0] - lower[0]) * ((float(pattern.centroid_grid[0]) + 0.5) / width),
        lower[1] + (upper[1] - lower[1]) * ((float(pattern.centroid_grid[1]) + 0.5) / height),
        (lower[2] + upper[2]) / 2.0,
    ]


def _spatial_feedback_candidate(
    *,
    implicit_field_state: Mapping[str, Any],
    implicit_basis_records: Sequence[Mapping[str, Any]],
    basis_spatial_index: Mapping[str, Any],
    pattern: FivePhasePatternRecord,
    agent_state: FivePhaseAgentStateRecord,
    trace_intensity: float,
    residual_strength: float,
) -> tuple[str, float, dict[str, dict[str, float]]] | None:
    if agent_state.support_energy_setpoint is None or agent_state.support_energy_current is None:
        return None
    signed_error = float(agent_state.support_energy_setpoint) - float(agent_state.support_energy_current)
    if abs(signed_error) <= float(agent_state.tolerance):
        return None
    support_bounds = pattern.payload.get("identity_support_bounds_grid", pattern.support_bounds_grid)
    grid_shape = pattern.payload.get("identity_support_grid_shape", [16, 16])
    source_channel_name = str(pattern.payload.get("support_source_channel_name", "density"))
    point = _centroid_world(
        pattern,
        region=implicit_field_state.get("validity_region_world", {}),
        grid_shape=grid_shape,
    )
    spatial_candidates: list[tuple[float, str]] = []
    for basis in implicit_basis_records:
        basis_id = str(basis.get("basis_id", ""))
        if not basis_id or abs(float(basis.get("channel_weights", {}).get("density", 0.0))) <= 0.0:
            continue
        support = basis.get("support_region_world", {})
        lower = [float(value) for value in support.get("min", [])]
        upper = [float(value) for value in support.get("max", [])]
        if len(lower) != 3 or len(upper) != 3:
            continue
        if not all(lower[index] <= point[index] <= upper[index] for index in range(3)):
            continue
        center = [float(value) for value in basis.get("center_world_3d", [])]
        if len(center) != 3:
            continue
        distance = math.sqrt(math.fsum((center[index] - point[index]) ** 2 for index in range(3)))
        spatial_candidates.append((distance, basis_id))
    measured: list[tuple[float, float, str]] = []
    for distance, basis_id in sorted(spatial_candidates)[:FEEDBACK_SPATIAL_CANDIDATE_LIMIT]:
        sensitivity = _support_sensitivity(
            implicit_field_state=implicit_field_state,
            implicit_basis_records=implicit_basis_records,
            basis_spatial_index=basis_spatial_index,
            support_bounds_grid=support_bounds,
            grid_shape=grid_shape,
            source_channel_name=source_channel_name,
            basis_id=basis_id,
            eta=FEEDBACK_FINITE_DIFFERENCE_ETA,
        )
        if abs(sensitivity) > FEEDBACK_SENSITIVITY_MIN:
            measured.append((abs(sensitivity), distance, basis_id))
    if not measured:
        return None
    _, _, target_basis_id = sorted(measured, key=lambda item: (-item[0], item[1], item[2]))[0]
    sensitivity = _support_sensitivity(
        implicit_field_state=implicit_field_state,
        implicit_basis_records=implicit_basis_records,
        basis_spatial_index=basis_spatial_index,
        support_bounds_grid=support_bounds,
        grid_shape=grid_shape,
        source_channel_name=source_channel_name,
        basis_id=target_basis_id,
        eta=FEEDBACK_FINITE_DIFFERENCE_ETA,
    )
    confidence = (
        max(0.0, min(1.0, float(pattern.continuity_score)))
        * max(0.0, min(1.0, float(agent_state.response_stability or 0.0)))
        * max(0.0, min(1.0, float(trace_intensity)))
        * max(0.0, min(1.0, float(residual_strength)))
    )
    magnitude = min(FEEDBACK_DENSITY_GAIN, abs(signed_error / sensitivity) * confidence)
    if magnitude <= 0.0:
        return None
    density_delta = math.copysign(magnitude, signed_error * sensitivity)
    return target_basis_id, sensitivity, {target_basis_id: {"density": density_delta}}


def measure_five_phase_feedback_response(
    *,
    implicit_field_state: Mapping[str, Any],
    implicit_basis_records: Sequence[Mapping[str, Any]],
    basis_spatial_index: Mapping[str, Any],
    pattern: FivePhasePatternRecord,
    agent_state: FivePhaseAgentStateRecord,
    feedback: FivePhaseFeedbackRecord,
) -> dict[str, Any]:
    """Recompute fixed-support error and sensitivity on a detached candidate state."""

    if agent_state.pattern_id != pattern.record_id or feedback.pattern_id != pattern.record_id:
        raise ValueError("application-time feedback measurement requires the exact Pattern instance")
    if feedback.agent_state_id != agent_state.record_id:
        raise ValueError("application-time feedback measurement requires the exact Agent")
    for name in ("trace_id", "residual_constraint_id", "bridge_record_id", "source_state_id"):
        if getattr(feedback, name) != getattr(agent_state, name):
            raise ValueError(f"application-time feedback measurement has mismatched {name}")
    if agent_state.support_energy_setpoint is None:
        raise ValueError("application-time feedback measurement requires Agent support setpoint")
    if feedback.target_basis_id is None or feedback.eta is None or feedback.candidate_projection is None:
        raise ValueError("application-time feedback measurement requires a complete Feedback candidate")
    target_channels = feedback.candidate_projection.get(feedback.target_basis_id)
    if not isinstance(target_channels, Mapping) or "density" not in target_channels:
        raise ValueError("application-time feedback candidate is missing target density")
    support_bounds = pattern.payload.get("identity_support_bounds_grid")
    grid_shape = pattern.payload.get("identity_support_grid_shape")
    source_channel_name = str(pattern.payload.get("support_source_channel_name", ""))
    if support_bounds is None or grid_shape is None or not source_channel_name:
        raise ValueError("application-time feedback measurement is missing fixed support metadata")
    support_energy_current = _implicit_support_energy(
        implicit_field_state=implicit_field_state,
        implicit_basis_records=implicit_basis_records,
        basis_spatial_index=basis_spatial_index,
        support_bounds_grid=support_bounds,
        grid_shape=grid_shape,
        source_channel_name=source_channel_name,
    )
    signed_error = float(agent_state.support_energy_setpoint) - support_energy_current
    sensitivity = _support_sensitivity(
        implicit_field_state=implicit_field_state,
        implicit_basis_records=implicit_basis_records,
        basis_spatial_index=basis_spatial_index,
        support_bounds_grid=support_bounds,
        grid_shape=grid_shape,
        source_channel_name=source_channel_name,
        basis_id=feedback.target_basis_id,
        eta=float(feedback.eta),
    )
    density_delta = float(target_channels["density"])
    record = {
        "schema": "five_phase_feedback_response_measurement_v1",
        "implicit_field_state_id": str(implicit_field_state["implicit_field_state_id"]),
        "implicit_field_state_digest": str(implicit_field_state["state_digest"]),
        "pattern_id": pattern.record_id,
        "agent_state_id": agent_state.record_id,
        "feedback_record_id": feedback.record_id,
        "support_bounds_grid": [int(value) for value in support_bounds],
        "grid_shape": [int(value) for value in grid_shape],
        "support_energy_setpoint": float(agent_state.support_energy_setpoint),
        "support_energy_current": support_energy_current,
        "signed_error": signed_error,
        "absolute_error": abs(signed_error),
        "target_basis_id": feedback.target_basis_id,
        "eta": float(feedback.eta),
        "sensitivity": sensitivity,
        "candidate_density_delta": density_delta,
        "candidate_direction_eligible": (
            abs(sensitivity) > FEEDBACK_SENSITIVITY_MIN
            and density_delta * signed_error * sensitivity > 0.0
        ),
        "source_record_ids": [
            str(implicit_field_state["implicit_field_state_id"]),
            pattern.record_id,
            agent_state.record_id,
            feedback.record_id,
            feedback.target_basis_id,
        ],
        "is_authority_state": False,
    }
    record["measurement_digest"] = _canonical_digest(record)
    return record


def _live_response_contexts(
    *,
    previous_patterns: Sequence[FivePhasePatternRecord],
    previous_live_field_state: FieldState | None,
    field_state: FieldState,
    supplied: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    if previous_patterns and previous_live_field_state is None:
        raise ValueError("previous_patterns require the immediate previous live FieldState")
    supplied_contexts = dict(supplied or {})
    result: dict[str, dict[str, Any]] = {}
    known_identity_ids: set[str] = set()
    for previous in previous_patterns:
        if previous_live_field_state is None or previous.tick != previous_live_field_state.tick:
            raise ValueError("previous_patterns must come from the immediate previous live step")
        identity_id = str(previous.payload.get("pattern_identity_id") or previous.record_id)
        if identity_id in known_identity_ids:
            raise ValueError("previous_patterns contain duplicate persistent identity")
        known_identity_ids.add(identity_id)
        fixed_bounds = previous.payload.get("identity_support_bounds_grid", previous.support_bounds_grid)
        prior_energy = _support_energy(previous_live_field_state, fixed_bounds)
        current_energy = _support_energy(field_state, fixed_bounds)
        context = dict(supplied_contexts.get(identity_id, {}))
        context["support_energy_prior"] = prior_energy
        context["support_energy_current"] = current_energy
        if bool(context.get("episode_started", False)):
            context.setdefault("support_energy_setpoint", prior_energy)
        else:
            context.setdefault(
                "support_energy_setpoint",
                float(previous.payload.get("support_energy_setpoint", prior_energy)),
            )
        result[identity_id] = context
    unknown = set(map(str, supplied_contexts)) - known_identity_ids
    if unknown:
        raise ValueError("response context references a non-immediate Pattern identity")
    return result


def build_five_phase_live_field_state(
    *,
    implicit_field_state: Mapping[str, Any],
    implicit_basis_records: Sequence[Mapping[str, Any]],
    basis_spatial_index: Mapping[str, Any],
    run_id: str,
    bridge_index: int,
    previous_live_field_state: FieldState | None,
    grid_shape: Sequence[int] = (16, 16),
    channel_name: str = "pattern",
) -> tuple[FieldState, dict[str, Any]]:
    reject_five_phase_live_shortcuts(implicit_field_state, path="implicit_field_state")
    reject_five_phase_live_shortcuts(implicit_basis_records, path="implicit_basis_records")
    state_id = str(implicit_field_state["implicit_field_state_id"])
    implicit_tick = int(implicit_field_state.get("tick", 0))
    field_tick = 0 if previous_live_field_state is None else int(previous_live_field_state.tick) + 1
    source_channel_name = _resolve_source_channel(implicit_basis_records, channel_name)
    points = _sample_points(implicit_field_state.get("validity_region_world", {}), grid_shape)
    evaluation = evaluate_implicit_field(
        implicit_field_state,
        implicit_basis_records,
        points,
        channel_names=[source_channel_name],
        basis_spatial_index=basis_spatial_index,
    )
    grid = _grid_from_samples(evaluation["sample_values"], channel_name=source_channel_name, grid_shape=grid_shape)
    previous_grid = (
        previous_live_field_state.channels[channel_name]
        if previous_live_field_state is not None and channel_name in previous_live_field_state.channels
        else grid
    )
    bridge_record_id = f"five-phase-live-field-bridge::{run_id}::{implicit_tick}::{bridge_index}"
    bridge = {
        "schema": "five_phase_live_field_bridge_v1",
        "bridge_record_id": bridge_record_id,
        "run_id": str(run_id),
        "tick": field_tick,
        "implicit_tick": implicit_tick,
        "field_tick": field_tick,
        "implicit_field_state_id": state_id,
        "field_state_id": f"five-phase-live-field-state::{run_id}::{implicit_tick}::{bridge_index}",
        "grid_shape": [int(grid_shape[0]), int(grid_shape[1])],
        "channel_name": channel_name,
        "source_channel_name": source_channel_name,
        "sample_points_world_3d_digest": _canonical_digest(points),
        "sample_values_digest": _canonical_digest(evaluation["sample_values"]),
        "signed_samples_preserved": True,
        "basis_contribution_digest": evaluation.get("basis_contribution_digest"),
        "source_record_ids": list(
            dict.fromkeys(
                [
                    state_id,
                    str(implicit_field_state.get("basis_layout_digest", "")),
                    str(implicit_field_state.get("basis_spatial_index_digest", "")),
                    str((basis_spatial_index or {}).get("basis_spatial_index_digest", "")),
                    bridge_record_id,
                    *[str(basis.get("basis_id")) for basis in implicit_basis_records],
                ]
            )
        ),
        "is_authority_state": False,
    }
    evidence_digest = _canonical_digest(bridge).split(":", 1)[1]
    previous_id = previous_live_field_state.field_state_id if previous_live_field_state is not None else None
    lower, upper = _finite_bounds(implicit_field_state.get("validity_region_world", {}))
    field = FieldState(
        field_state_id=bridge["field_state_id"],
        run_id=str(run_id),
        tick=field_tick,
        rule_id="five_phase_live_implicit_readback_bridge_v1",
        grid_shape=[int(grid_shape[1]), int(grid_shape[0])],
        channels={channel_name: grid},
        previous_channels={channel_name: previous_grid},
        energy=sum(value * value for row in grid for value in row),
        source_state_ticks=[implicit_tick],
        source_record_ids=list(dict.fromkeys(bridge["source_record_ids"])),
        payload={
            "authority_role": "field_substrate",
            "wave_kernel": "five_phase_live_implicit_sample_bridge_v1",
            "source_package_digest": str(implicit_field_state.get("basis_layout_digest", "")),
            "stable_composite_evidence_id": f"five-phase-live-bridge:sha256:{evidence_digest}",
            "stable_composite_evidence_digest": evidence_digest,
            "field_evidence_bridge_id": bridge_record_id,
            "previous_field_state_id": previous_id,
            "source_field_state_ids": [previous_id] if previous_id else [],
            "field_wave_step_record_id": bridge_record_id if previous_id else None,
            "channel_families": {channel_name: "implicit_live_sample"},
            "source_channel_families": {channel_name: source_channel_name},
            "seed_mode_signatures": [],
            "coordinate_frame": {
                "world_origin": [lower[0], lower[1]],
                "world_extent": [upper[0] - lower[0], upper[1] - lower[1]],
                "grid_shape": [int(grid_shape[1]), int(grid_shape[0])],
                "world_to_grid": "five_phase_live_bridge_xy_sample_v1",
                "grid_to_world": "five_phase_live_bridge_grid_center_v1",
                "source_observer_window": "implicit_live_validity_region_mid_z",
            },
        },
    )
    return field, bridge


def build_five_phase_live_artifacts(
    *,
    implicit_field_state: Mapping[str, Any],
    implicit_basis_records: Sequence[Mapping[str, Any]],
    basis_spatial_index: Mapping[str, Any],
    run_id: str,
    bridge_index: int,
    previous_live_field_state: FieldState | None,
    observer_id: str,
    frequency_window: Mapping[str, Any],
    previous_patterns: Sequence[FivePhasePatternRecord] = (),
    previous_residual_constraints: Sequence[FivePhaseResidualConstraintRecord] = (),
    previous_live_step_id: str | None = None,
    response_context_by_pattern_identity_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    field_state, bridge = build_five_phase_live_field_state(
        implicit_field_state=implicit_field_state,
        implicit_basis_records=implicit_basis_records,
        basis_spatial_index=basis_spatial_index,
        run_id=run_id,
        bridge_index=bridge_index,
        previous_live_field_state=previous_live_field_state,
    )
    phase = extract_five_phase_field(field_state, previous_field_state=previous_live_field_state)
    constraints = derive_five_phase_constraints(phase, tick=field_state.tick)
    response_contexts = _live_response_contexts(
        previous_patterns=previous_patterns,
        previous_live_field_state=previous_live_field_state,
        field_state=field_state,
        supplied=response_context_by_pattern_identity_id,
    )
    patterns, lifecycle = detect_five_phase_patterns(
        phase,
        constraint_set=constraints,
        previous_patterns=previous_patterns,
        min_support_weight=0.1,
    )
    previous_pattern_by_id = {pattern.record_id: pattern for pattern in previous_patterns}
    measured_patterns: list[FivePhasePatternRecord] = []
    for pattern in patterns:
        previous_record_id = str(pattern.payload.get("previous_pattern_record_id") or "")
        previous_pattern = previous_pattern_by_id.get(previous_record_id)
        identity_id = str(pattern.payload["pattern_identity_id"])
        fixed_bounds = list(
            previous_pattern.payload.get(
                "identity_support_bounds_grid",
                previous_pattern.support_bounds_grid,
            )
            if previous_pattern is not None
            else pattern.support_bounds_grid
        )
        if previous_pattern is None:
            response_context = build_five_phase_initial_response_context(
                pattern_identity_id=identity_id,
                support_bounds_grid=fixed_bounds,
                grid_shape=bridge["grid_shape"],
                source_channel_name=str(bridge["source_channel_name"]),
                implicit_field_state=implicit_field_state,
                implicit_basis_records=implicit_basis_records,
                basis_spatial_index=basis_spatial_index,
                tick=int(implicit_field_state.get("tick", field_state.tick)),
            )
            kappa = dict(response_context["identity_support_kappa"])
        else:
            kappa = build_five_phase_identity_support_kappa(
                implicit_field_state=implicit_field_state,
                implicit_basis_records=implicit_basis_records,
                support_bounds_grid=fixed_bounds,
                grid_shape=bridge["grid_shape"],
            )
            response_context = dict(response_contexts[identity_id])
            response_context.setdefault(
                "support_coefficient_norm_setpoint",
                float(previous_pattern.payload.get("support_coefficient_norm_setpoint", 0.0)),
            )
            response_context.setdefault(
                "support_setpoint_state_id",
                str(previous_pattern.payload.get("support_setpoint_state_id", "")),
            )
            response_context.setdefault(
                "support_setpoint_state_digest",
                str(previous_pattern.payload.get("support_setpoint_state_digest", "")),
            )
            response_context.setdefault("realized_user_input_norm_kappa", 0.0)
            response_context.setdefault("realized_feedback_input_norm_kappa", 0.0)
            response_context.setdefault("episode_started", False)
        supplied_kappa = response_context.get("identity_support_kappa")
        if supplied_kappa is not None and {
            str(key): float(value) for key, value in dict(supplied_kappa).items()
        } != kappa:
            raise ValueError("five phase response context changed the fixed identity support kappa")
        response_context["identity_support_kappa"] = kappa
        response_context["identity_support_kappa_digest"] = _canonical_digest(kappa)
        stability_score, response_payload = materialize_five_phase_pattern_response(
            previous_pattern=previous_pattern,
            pattern_identity_id=identity_id,
            response_context=response_context,
            support_bounds_grid=fixed_bounds,
            grid_shape=bridge["grid_shape"],
            source_channel_name=str(bridge["source_channel_name"]),
            implicit_field_state=implicit_field_state,
            tick=int(implicit_field_state.get("tick", field_state.tick)),
        )
        measured_patterns.append(
            replace(
                pattern,
                stability_score=stability_score,
                setpoint=pattern.phase_vector if stability_score >= 0.3 else None,
                payload={
                    **pattern.payload,
                    **response_payload,
                },
            )
        )
    patterns = measured_patterns
    traces = [
        build_five_phase_trace(pattern, phase, observer_id=observer_id, frequency_window=frequency_window, tick=field_state.tick)
        for pattern in patterns[:3]
    ]
    previous_residual_by_pattern_id = {
        residual.pattern_id: residual
        for residual in previous_residual_constraints
    }
    residuals = [
        build_residual_constraint_from_trace(
            trace,
            previous_memory=float(
                previous_residual_by_pattern_id.get(
                    str(pattern.payload.get("previous_pattern_record_id", ""))
                ).memory_next
                if previous_residual_by_pattern_id.get(
                    str(pattern.payload.get("previous_pattern_record_id", ""))
                )
                is not None
                else 0.0
            ),
            tick=field_state.tick,
        )
        for pattern, trace in zip(patterns[:3], traces)
    ]
    agents = [
        build_agent_state_from_pattern(
            pattern,
            setpoint=(
                previous_pattern_by_id[str(pattern.payload["previous_pattern_record_id"])].phase_vector
                if pattern.payload.get("previous_pattern_record_id")
                else pattern.phase_vector
            ),
            trace=trace,
            residual_constraint=residual,
            support_energy_setpoint=float(pattern.payload["support_energy_setpoint"]),
            support_energy_current=float(pattern.payload["support_energy_current"]),
            response_stability=pattern.stability_score,
            bridge_record_id=bridge["bridge_record_id"],
            source_state_id=str(implicit_field_state["implicit_field_state_id"]),
            source_state_digest=str(implicit_field_state["state_digest"]),
            tolerance=0.01,
            tick=field_state.tick,
        )
        for pattern, trace, residual in zip(patterns[:3], traces, residuals)
    ]
    feedbacks: list[FivePhaseFeedbackRecord] = []
    for pattern, trace, residual, agent in zip(patterns[:3], traces, residuals, agents):
        if not pattern.payload.get("previous_pattern_record_id") or not previous_live_step_id:
            continue
        candidate = _spatial_feedback_candidate(
            implicit_field_state=implicit_field_state,
            implicit_basis_records=implicit_basis_records,
            basis_spatial_index=basis_spatial_index,
            pattern=pattern,
            agent_state=agent,
            trace_intensity=trace.trace_intensity,
            residual_strength=residual.strength,
        )
        if candidate is None:
            continue
        target_basis_id, sensitivity, candidate_projection = candidate
        feedback = build_agent_repair_feedback(
            agent,
            pattern,
            tick=field_state.tick,
            target_basis_id=target_basis_id,
            signed_error=float(agent.support_energy_setpoint) - float(agent.support_energy_current),
            sensitivity=sensitivity,
            eta=FEEDBACK_FINITE_DIFFERENCE_ETA,
            gain=FEEDBACK_DENSITY_GAIN,
            candidate_projection=candidate_projection,
            predecessor_causal_step_id=previous_live_step_id,
        )
        if feedback is not None:
            feedbacks.append(feedback)
    feedback_projection = five_phase_feedback_to_implicit_input_projection(
        feedback_records=feedbacks,
        patterns=patterns,
        implicit_basis_records=implicit_basis_records,
    )
    live_step_id = f"five-phase-live-step::{run_id}::{int(implicit_field_state.get('tick', 0))}::{bridge_index}"
    live_step = {
        "schema": "five_phase_live_step_record_v1",
        "live_step_id": live_step_id,
        "tick": int(implicit_field_state.get("tick", 0)),
        "implicit_field_state_id": str(implicit_field_state["implicit_field_state_id"]),
        "bridge_record_id": bridge["bridge_record_id"],
        "field_state_id": field_state.field_state_id,
        "phase_field_id": phase.record_id,
        "constraint_set_id": constraints.record_id,
        "pattern_ids": [record.record_id for record in patterns],
        "trace_ids": [record.record_id for record in traces],
        "residual_constraint_ids": [record.record_id for record in residuals],
        "agent_state_ids": [record.record_id for record in agents],
        "feedback_record_ids": [record.record_id for record in feedbacks],
        "feedback_input_projection": feedback_projection,
        "source_record_ids": list(
            dict.fromkeys(
                [
                    live_step_id,
                    str(implicit_field_state["implicit_field_state_id"]),
                    bridge["bridge_record_id"],
                    field_state.field_state_id,
                    phase.record_id,
                    constraints.record_id,
                    *bridge["source_record_ids"],
                    *[record.record_id for record in patterns],
                    *[record.record_id for record in traces],
                    *[record.record_id for record in residuals],
                    *[record.record_id for record in agents],
                    *[record.record_id for record in feedbacks],
                ]
            )
        ),
        "is_authority_state": False,
    }
    return {
        "bridges": [bridge],
        "field_states": [field_state],
        "phase_fields": [phase],
        "constraint_sets": [constraints],
        "patterns": patterns,
        "lifecycle_records": lifecycle,
        "traces": traces,
        "residual_constraints": residuals,
        "agent_states": agents,
        "feedback_records": feedbacks,
        "live_step": live_step,
    }


def five_phase_feedback_to_implicit_input_projection(
    *,
    feedback_records: Sequence[FivePhaseFeedbackRecord],
    patterns: Sequence[FivePhasePatternRecord],
    implicit_basis_records: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, float]]:
    bases_by_id = {
        str(basis["basis_id"]): basis
        for basis in implicit_basis_records
        if basis.get("basis_id")
    }
    pattern_by_id = {pattern.record_id: pattern for pattern in patterns}
    projection: dict[str, dict[str, float]] = {}
    for feedback in feedback_records:
        if feedback.pattern_id not in pattern_by_id:
            raise ValueError("five phase feedback references missing pattern")
        if feedback.candidate_projection is None or feedback.target_basis_id is None:
            raise ValueError("five phase feedback is missing its candidate projection")
        if feedback.target_basis_id not in bases_by_id:
            raise ValueError("five phase feedback target basis is undeclared")
        for basis_id, channels in feedback.candidate_projection.items():
            basis = bases_by_id.get(str(basis_id))
            if basis is None:
                raise ValueError("five phase feedback candidate references an undeclared basis")
            declared_channels = set(map(str, basis.get("channel_weights", {})))
            for channel, raw_value in channels.items():
                if str(channel) not in declared_channels:
                    raise ValueError("five phase feedback candidate references an undeclared channel")
                value = float(raw_value)
                if not math.isfinite(value):
                    raise ValueError("five phase feedback candidate must be finite")
                projection.setdefault(str(basis_id), {})
                merged = projection[str(basis_id)].get(str(channel), 0.0) + value
                if not math.isfinite(merged):
                    raise ValueError("five phase feedback aggregate must be finite")
                projection[str(basis_id)][str(channel)] = merged
    return projection


__all__ = [
    "FEEDBACK_DENSITY_GAIN",
    "FEEDBACK_FINITE_DIFFERENCE_ETA",
    "FEEDBACK_SENSITIVITY_MIN",
    "FORBIDDEN_FIVE_PHASE_LIVE_SHORTCUT_KEYS",
    "build_five_phase_identity_support_kappa",
    "build_five_phase_initial_response_context",
    "build_five_phase_live_artifacts",
    "build_five_phase_live_field_state",
    "build_five_phase_transition_response_context",
    "five_phase_feedback_to_implicit_input_projection",
    "measure_five_phase_density_kappa_norm",
    "measure_five_phase_feedback_response",
    "measure_five_phase_support_energy",
    "materialize_five_phase_pattern_response",
    "reject_five_phase_live_shortcuts",
]
