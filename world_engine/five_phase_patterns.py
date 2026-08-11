from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from world_engine.contracts import WorldObject
from world_engine.five_phase import (
    EPS,
    FIVE_PHASE_NAMES,
    FivePhaseConstraintSetRecord,
    FivePhaseFieldRecord,
    FivePhasePatternRecord,
    FivePhaseVector,
    normalize_phase_weights,
    stable_digest,
    stable_record_id,
)


Support = list[tuple[int, int]]


def _neighbors(row: int, col: int, height: int, width: int) -> list[tuple[int, int]]:
    return [
        (rr, cc)
        for rr, cc in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1))
        if 0 <= rr < height and 0 <= cc < width
    ]


def _components(rho: list[list[float]], threshold: float) -> list[Support]:
    height = len(rho)
    width = len(rho[0]) if height else 0
    active = [[rho[row][col] >= threshold for col in range(width)] for row in range(height)]
    supports: list[Support] = []
    for row in range(height):
        for col in range(width):
            if not active[row][col]:
                continue
            stack = [(row, col)]
            active[row][col] = False
            support: Support = []
            while stack:
                item = stack.pop()
                support.append(item)
                for rr, cc in _neighbors(item[0], item[1], height, width):
                    if active[rr][cc]:
                        active[rr][cc] = False
                        stack.append((rr, cc))
            supports.append(support)
    return supports


def _bounds(support: Support) -> tuple[int, int, int, int]:
    rows = [row for row, _ in support]
    cols = [col for _, col in support]
    return (min(cols), min(rows), max(cols), max(rows))


def _centroid(rho: list[list[float]], support: Support) -> tuple[float, float]:
    total = 0.0
    col_sum = 0.0
    row_sum = 0.0
    for row, col in support:
        weight = rho[row][col]
        total += weight
        col_sum += col * weight
        row_sum += row * weight
    if total <= EPS:
        return (sum(col for _, col in support) / len(support), sum(row for row, _ in support) / len(support))
    return (col_sum / total, row_sum / total)


def _phase_average(
    phase_field: FivePhaseFieldRecord,
    rho: list[list[float]],
    support: Support,
) -> FivePhaseVector:
    totals = {name: 0.0 for name in FIVE_PHASE_NAMES}
    total_weight = 0.0
    for row, col in support:
        weight = rho[row][col]
        vector = phase_field.cell_phase_vectors[row][col]
        if not isinstance(vector, FivePhaseVector):
            vector = FivePhaseVector.from_dict(vector)
        values = vector.to_dict()
        for name in FIVE_PHASE_NAMES:
            totals[name] += values[name] * weight
        total_weight += weight
    if total_weight <= EPS:
        total_weight = float(len(support))
        totals = {name: 0.0 for name in FIVE_PHASE_NAMES}
        for row, col in support:
            vector = phase_field.cell_phase_vectors[row][col]
            if not isinstance(vector, FivePhaseVector):
                vector = FivePhaseVector.from_dict(vector)
            values = vector.to_dict()
            for name in FIVE_PHASE_NAMES:
                totals[name] += values[name]
    return normalize_phase_weights({name: totals[name] / max(total_weight, EPS) for name in FIVE_PHASE_NAMES})


def _overlap(left: Sequence[int], right: Sequence[int]) -> float:
    lx0, ly0, lx1, ly1 = left
    rx0, ry0, rx1, ry1 = right
    x0 = max(lx0, rx0)
    y0 = max(ly0, ry0)
    x1 = min(lx1, rx1)
    y1 = min(ly1, ry1)
    intersection = max(0, x1 - x0 + 1) * max(0, y1 - y0 + 1)
    left_area = (lx1 - lx0 + 1) * (ly1 - ly0 + 1)
    right_area = (rx1 - rx0 + 1) * (ry1 - ry0 + 1)
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def _signature(bounds: Sequence[int], phase: FivePhaseVector, support_size: int) -> str:
    values = phase.to_dict()
    quantized = {
        "bounds_size": [bounds[2] - bounds[0] + 1, bounds[3] - bounds[1] + 1],
        "support_bin": int(round(support_size / 4.0)),
        "phase_bins": {name: int(round(values[name] * 10.0)) for name in FIVE_PHASE_NAMES},
    }
    return "five-phase-invariant:sha256:" + stable_digest(quantized).split(":", 1)[1][:16]


def _context_nonnegative(context: Mapping[str, Any], key: str, default: float) -> float:
    value = float(context.get(key, default))
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"FivePhase response context {key} must be finite and non-negative.")
    return value


def build_five_phase_response_context(
    *,
    previous_pattern: FivePhasePatternRecord | None,
    pattern_identity_id: str,
    tick: int,
    realized_user_dose: float,
    realized_feedback_dose: float,
    relaxation_horizon_ticks: int = 8,
) -> dict[str, Any]:
    user_dose = float(realized_user_dose)
    feedback_dose = float(realized_feedback_dose)
    if not math.isfinite(user_dose) or user_dose < 0.0:
        raise ValueError("FivePhase realized user dose must be finite and non-negative.")
    if not math.isfinite(feedback_dose) or feedback_dose < 0.0:
        raise ValueError("FivePhase realized Feedback dose must be finite and non-negative.")
    horizon = int(relaxation_horizon_ticks)
    if horizon <= 0:
        raise ValueError("FivePhase relaxation horizon must be positive.")
    previous_payload = dict(previous_pattern.payload) if previous_pattern is not None else {}
    previous_end = int(previous_payload.get("episode_end_tick", tick))
    previous_status = str(previous_payload.get("episode_status", "unperturbed"))
    continuing_episode = (
        bool(previous_payload.get("episode_id"))
        and previous_status in {"active", "relaxing"}
        and int(tick) <= previous_end
    )
    if user_dose > EPS and not continuing_episode:
        episode_start_tick = int(tick)
        episode_id = f"five-phase-pattern-episode::{pattern_identity_id}::{episode_start_tick}"
        last_user_input_tick = int(tick)
        episode_end_tick = int(tick) + horizon
    else:
        episode_start_tick = int(previous_payload.get("episode_start_tick", tick))
        episode_id = str(
            previous_payload.get("episode_id")
            or f"five-phase-pattern-episode::{pattern_identity_id}::{episode_start_tick}"
        )
        last_user_input_tick = (
            int(tick)
            if user_dose > EPS
            else int(previous_payload.get("last_user_input_tick", episode_start_tick))
        )
        episode_end_tick = (
            int(tick) + horizon
            if user_dose > EPS
            else int(previous_payload.get("episode_end_tick", last_user_input_tick + horizon))
        )
    previous_cumulative = _context_nonnegative(previous_payload, "cumulative_realized_user_dose", 0.0)
    episode_status = (
        "active"
        if user_dose > EPS
        else "relaxing"
        if int(tick) <= episode_end_tick and previous_cumulative > EPS
        else "closed"
        if previous_cumulative > EPS
        else "unperturbed"
    )
    return {
        "episode_id": episode_id,
        "episode_start_tick": episode_start_tick,
        "last_user_input_tick": last_user_input_tick,
        "episode_end_tick": episode_end_tick,
        "episode_status": episode_status,
        "realized_user_dose": user_dose,
        "realized_feedback_dose": feedback_dose,
        "user_dose_normalization": "fixed_support_kappa_density_norm_over_setpoint_v1",
        "feedback_dose_normalization": "fixed_support_kappa_density_norm_over_setpoint_v1",
    }


def build_five_phase_live_response_metrics(
    *,
    context: Mapping[str, Any],
    previous_pattern: FivePhasePatternRecord | None,
    pattern_identity_id: str,
    tick: int,
    measured_support_energy: float,
) -> tuple[float, dict[str, Any]]:
    previous_payload = dict(previous_pattern.payload) if previous_pattern is not None else {}
    prior_energy = _context_nonnegative(
        context,
        "support_energy_prior",
        _context_nonnegative(
            previous_payload,
            "support_energy_current",
            float(previous_payload.get("support_energy", measured_support_energy)),
        ),
    )
    current_energy = _context_nonnegative(context, "support_energy_current", measured_support_energy)
    setpoint_energy = _context_nonnegative(context, "support_energy_setpoint", prior_energy)
    user_dose = _context_nonnegative(context, "realized_user_dose", 0.0)
    feedback_dose = _context_nonnegative(context, "realized_feedback_dose", 0.0)
    episode_start_tick = int(context.get("episode_start_tick", tick))
    episode_id = str(
        context.get("episode_id")
        or stable_record_id(
            "five-phase-pattern-episode",
            {"pattern_identity_id": pattern_identity_id, "episode_start_tick": episode_start_tick},
        )
    )
    same_episode = previous_payload.get("episode_id") == episode_id
    cumulative_user_dose = (
        _context_nonnegative(previous_payload, "cumulative_realized_user_dose", 0.0) if same_episode else 0.0
    ) + user_dose
    deformation = abs(current_energy - setpoint_energy) / max(setpoint_energy, EPS)
    previous_peak = _context_nonnegative(previous_payload, "peak_deformation", 0.0) if same_episode else 0.0
    peak_deformation = max(previous_peak, deformation)
    stability_score = 1.0 if cumulative_user_dose <= EPS else 1.0 / (1.0 + deformation / max(cumulative_user_dose, EPS))
    last_user_input_tick = int(
        context.get(
            "last_user_input_tick",
            tick if user_dose > EPS else previous_payload.get("last_user_input_tick", episode_start_tick),
        )
    )
    episode_end_tick = int(context.get("episode_end_tick", last_user_input_tick + 8))
    episode_status = str(
        context.get(
            "episode_status",
            "unperturbed" if cumulative_user_dose <= EPS else "active" if user_dose > EPS else "relaxing",
        )
    )
    return stability_score, {
        "stability_formula": "five_phase_live_response_stability_v2",
        "deformation_normalization": "absolute_support_energy_delta_over_setpoint_v1",
        "user_dose_normalization": str(
            context.get(
                "user_dose_normalization",
                "fixed_support_kappa_density_norm_over_setpoint_v1",
            )
        ),
        "feedback_dose_normalization": str(
            context.get(
                "feedback_dose_normalization",
                "fixed_support_kappa_density_norm_over_setpoint_v1",
            )
        ),
        "episode_id": episode_id,
        "episode_status": episode_status,
        "episode_start_tick": episode_start_tick,
        "last_user_input_tick": last_user_input_tick,
        "episode_end_tick": episode_end_tick,
        "episode_age_ticks": max(0, int(tick) - episode_start_tick),
        "persistence_ticks": int(previous_payload.get("persistence_ticks", 0)) + 1 if previous_pattern else 1,
        "support_energy_prior": prior_energy,
        "support_energy_current": current_energy,
        "support_energy_setpoint": setpoint_energy,
        "deformation_from_setpoint": deformation,
        "q_user": user_dose,
        "Q_live": cumulative_user_dose,
        "realized_user_dose": user_dose,
        "cumulative_realized_user_dose": cumulative_user_dose,
        "q_feedback": feedback_dose,
        "realized_feedback_dose": feedback_dose,
        "peak_deformation": peak_deformation,
        "relaxation_from_peak": deformation / max(peak_deformation, EPS) if peak_deformation > EPS else 0.0,
    }


def detect_five_phase_patterns(
    phase_field: FivePhaseFieldRecord,
    *,
    constraint_set: FivePhaseConstraintSetRecord | None = None,
    previous_patterns: Sequence[FivePhasePatternRecord] = (),
    response_context_by_pattern_identity_id: Mapping[str, Mapping[str, Any]] | None = None,
    min_support_weight: float = 0.2,
) -> tuple[list[FivePhasePatternRecord], list[dict[str, Any]]]:
    rho = phase_field.metrics.get("rho")
    if not isinstance(rho, list) or not rho:
        raise ValueError("FivePhase pattern detection requires phase_field.metrics['rho'].")
    peak = max((float(value) for row in rho for value in row), default=0.0)
    threshold = max(peak * min_support_weight, 1e-6)
    supports = _components(rho, threshold)
    patterns: list[FivePhasePatternRecord] = []
    lifecycle_records: list[dict[str, Any]] = []
    used_previous: set[str] = set()

    for index, support in enumerate(supports):
        bounds = _bounds(support)
        phase = _phase_average(phase_field, rho, support)
        centroid = _centroid(rho, support)
        best_previous: FivePhasePatternRecord | None = None
        best_overlap = 0.0
        for previous in previous_patterns:
            if previous.record_id in used_previous:
                continue
            score = _overlap(previous.support_bounds_grid, bounds)
            if score > best_overlap:
                best_previous = previous
                best_overlap = score
        continuity = best_overlap if best_previous else 0.0
        previous_pattern_record_id: str | None = None
        if best_previous and best_overlap >= 0.25:
            previous_pattern_record_id = best_previous.record_id
            pattern_identity_id = str(best_previous.payload.get("pattern_identity_id") or best_previous.record_id)
            used_previous.add(best_previous.record_id)
        else:
            pattern_identity_id = stable_record_id(
                "five-phase-pattern-identity",
                {"phase_field_id": phase_field.record_id, "index": index, "bounds": bounds, "phase": phase.to_dict()},
            )
        pattern_id = stable_record_id(
            "five-phase-pattern",
            {
                "phase_field_id": phase_field.record_id,
                "index": index,
                "bounds": bounds,
                "phase": phase.to_dict(),
                "pattern_identity_id": pattern_identity_id,
                "previous_pattern_record_id": previous_pattern_record_id,
            },
        )
        support_area = len(support)
        bbox_area = (bounds[2] - bounds[0] + 1) * (bounds[3] - bounds[1] + 1)
        measured_support_energy = sum(float(rho[row][col]) for row, col in support)
        stability_score = min(1.0, (support_area / max(float(bbox_area), EPS)) * (phase.to_dict()["contractive"] + phase.to_dict()["substrate"] + 0.5))
        live_response_payload: dict[str, Any] = {}
        response_context = (response_context_by_pattern_identity_id or {}).get(pattern_identity_id)
        if response_context is not None:
            stability_score, live_response_payload = build_five_phase_live_response_metrics(
                context=response_context,
                previous_pattern=best_previous,
                pattern_identity_id=pattern_identity_id,
                tick=phase_field.tick,
                measured_support_energy=measured_support_energy,
            )
        pattern = FivePhasePatternRecord(
            record_id=pattern_id,
            schema="five_phase_pattern_v1",
            tick=phase_field.tick,
            phase_field_id=phase_field.record_id,
            constraint_set_id=constraint_set.record_id if constraint_set else None,
            support_bounds_grid=bounds,
            centroid_grid=centroid,
            phase_vector=phase,
            dominant_phase=phase.dominant_phase(),
            stability_score=stability_score,
            continuity_score=continuity,
            invariant_signature=_signature(bounds, phase, support_area),
            setpoint=phase if stability_score >= 0.3 else None,
            source_record_ids=(
                phase_field.record_id,
                *((previous_pattern_record_id,) if previous_pattern_record_id else ()),
                *(constraint_set.source_record_ids if constraint_set else ()),
                *phase_field.source_record_ids,
            ),
            payload={
                "support_size": support_area,
                "support_energy": measured_support_energy,
                "pattern_identity_id": pattern_identity_id,
                "previous_pattern_record_id": previous_pattern_record_id,
                **live_response_payload,
                "objects_derive_downstream": True,
            },
            is_authority_state=False,
        )
        patterns.append(pattern)

    previous_ids = {record.record_id for record in previous_patterns}
    current_ids = {record.record_id for record in patterns}
    if previous_patterns or patterns:
        event_kind = "persist"
        if len(patterns) > len(previous_patterns):
            event_kind = "boundary_crossing_split_or_release"
        elif len(patterns) < len(previous_patterns):
            event_kind = "boundary_crossing_merge_or_absorb"
        lifecycle_records.append(
            {
                "record_id": stable_record_id(
                    "boundary-crossing",
                    {
                        "phase_field_id": phase_field.record_id,
                        "previous": sorted(previous_ids),
                        "current": sorted(current_ids),
                        "event_kind": event_kind,
                    },
                ),
                "schema": "boundary_crossing_record_v1",
                "tick": phase_field.tick,
                "event_kind": event_kind,
                "previous_pattern_ids": sorted(previous_ids),
                "current_pattern_ids": sorted(current_ids),
                "source_record_ids": [phase_field.record_id, *phase_field.source_record_ids],
                "is_authority_state": False,
            }
        )
    return patterns, lifecycle_records


def derive_world_objects_from_five_phase_patterns(patterns: Sequence[FivePhasePatternRecord]) -> list[WorldObject]:
    objects: list[WorldObject] = []
    for pattern in patterns:
        objects.append(
            WorldObject(
                object_id=f"field-pattern-object::{pattern.record_id}",
                family="five_phase_pattern_projection",
                tick=pattern.tick,
                position=[float(pattern.centroid_grid[0]), float(pattern.centroid_grid[1])],
                stability_score=pattern.stability_score,
                continuity_score=pattern.continuity_score,
                payload={
                    "derived_from_five_phase_pattern_id": pattern.record_id,
                    "invariant_signature": pattern.invariant_signature,
                    "five_phase_pattern_projection": True,
                    "field_support_bounds_grid": list(pattern.support_bounds_grid),
                },
            )
        )
    return objects


__all__ = [
    "build_five_phase_live_response_metrics",
    "build_five_phase_response_context",
    "detect_five_phase_patterns",
    "derive_world_objects_from_five_phase_patterns",
]
