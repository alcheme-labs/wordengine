from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from world_engine.contracts import FieldState
from world_engine.five_phase import (
    CARRYING_CAPACITY,
    DEFAULT_DT,
    ENERGY_BUDGET_ABS,
    EPS,
    FIVE_PHASE_NAMES,
    MASS_BUDGET_ABS,
    MAX_DELTA_PER_TICK,
    FivePhaseAgentStateRecord,
    FivePhaseConstraintSetRecord,
    FivePhaseFeedbackRecord,
    FivePhaseFieldRecord,
    FivePhasePatternRecord,
    FivePhaseResidualConstraintRecord,
    FivePhaseTraceRecord,
    FivePhaseVector,
    clamp,
    reject_authority_shortcuts,
    sigmoid,
    stable_digest,
    stable_record_id,
)
from world_engine.five_phase_extraction import _blur3x3, _divergence, _grad


Grid = list[list[float]]
VectorGrid = list[list[tuple[float, float]]]


def _shape(grid: Grid) -> tuple[int, int]:
    height = len(grid)
    width = len(grid[0]) if height else 0
    return height, width


def _laplacian_from_grad_diffusion(grid: Grid, diffusion: float) -> Grid:
    height, width = _shape(grid)
    out = [[0.0 for _ in range(width)] for _ in range(height)]
    for row in range(height):
        for col in range(width):
            center = grid[row][col]
            left = grid[row][max(0, col - 1)]
            right = grid[row][min(width - 1, col + 1)]
            up = grid[max(0, row - 1)][col]
            down = grid[min(height - 1, row + 1)][col]
            out[row][col] = diffusion * (left + right + up + down - 4.0 * center)
    return out


def _field_mass(grid: Grid) -> float:
    return sum(sum(row) for row in grid)


def _field_energy(grid: Grid) -> float:
    return sum(value * value for row in grid for value in row)


def _diff_abs_sum(left: Grid, right: Grid) -> float:
    return sum(
        abs(right[row][col] - left[row][col])
        for row in range(len(left))
        for col in range(len(left[0]) if left else 0)
    )


def _normalize_flux_direction(grid: Grid) -> VectorGrid:
    grad, _ = _grad(grid)
    height, width = _shape(grid)
    result: VectorGrid = []
    for row in range(height):
        result_row: list[tuple[float, float]] = []
        for col in range(width):
            gx, gy = grad[row][col]
            magnitude = math.sqrt(gx * gx + gy * gy)
            if magnitude <= EPS:
                result_row.append((0.0, 0.0))
            else:
                result_row.append((gx / magnitude, gy / magnitude))
        result.append(result_row)
    return result


def _transport_divergence(grid: Grid, transport_gain: float) -> Grid:
    direction = _normalize_flux_direction(grid)
    height, width = _shape(grid)
    transported: VectorGrid = []
    for row in range(height):
        transported_row: list[tuple[float, float]] = []
        for col in range(width):
            u = grid[row][col]
            dx, dy = direction[row][col]
            transported_row.append((transport_gain * dx * u, transport_gain * dy * u))
        transported.append(transported_row)
    return _divergence(transported)


def derive_five_phase_constraints(
    phase_field: FivePhaseFieldRecord,
    *,
    tick: int,
) -> FivePhaseConstraintSetRecord:
    phase = phase_field.aggregate_phase.normalized()
    values = phase.to_dict()
    contractive = values["contractive"]
    generative = values["generative"]
    transport = values["transport"]
    radiant = values["radiant"]
    substrate = values["substrate"]
    payload = {
        "phase_weights": phase.to_dict(),
        "dt": DEFAULT_DT,
        "diffusion": clamp(0.035 + 0.055 * substrate + 0.035 * transport - 0.025 * contractive, 0.005, 0.18),
        "transport_gain": 0.12 * transport,
        "generative_gain": 0.10 * generative,
        "radiant_decay": 0.12 * radiant,
        "contractive_relax": 0.10 * contractive,
        "substrate_buffer_gain": 0.08 * substrate,
        "max_delta_per_tick": MAX_DELTA_PER_TICK,
        "mass_budget_abs": MASS_BUDGET_ABS,
        "energy_budget_abs": ENERGY_BUDGET_ABS,
        "formula": "five_phase_conservative_reaction_flow_v1",
    }
    return FivePhaseConstraintSetRecord(
        record_id=stable_record_id(
            "five-phase-constraint-set",
            {"phase_field_id": phase_field.record_id, "tick": tick, "payload": payload},
        ),
        schema="five_phase_constraint_set_v1",
        tick=int(tick),
        phase_field_id=phase_field.record_id,
        payload=payload,
        source_record_ids=(phase_field.record_id, *phase_field.source_record_ids),
        is_authority_state=False,
    )


def _residual_bias_scalar(
    residual_constraints: Sequence[FivePhaseResidualConstraintRecord],
    phase_weights: dict[str, float],
) -> float:
    bias = 0.0
    for residual in residual_constraints:
        values = residual.residual_phase_bias.to_dict()
        phase_alignment = sum(values[name] * phase_weights.get(name, 0.0) for name in FIVE_PHASE_NAMES)
        bias += residual.strength * residual.memory_next * phase_alignment
    return clamp(bias * 0.025, -0.05, 0.05)


def apply_five_phase_constraints(
    field_state: FieldState,
    constraint_set: FivePhaseConstraintSetRecord,
    *,
    tick: int,
    channel_name: str = "pattern",
    residual_constraints: Sequence[FivePhaseResidualConstraintRecord] = (),
) -> tuple[FieldState, dict[str, Any]]:
    reject_authority_shortcuts(field_state.payload, path="field_state.payload")
    reject_authority_shortcuts(constraint_set.payload, path="constraint_set.payload")
    if channel_name not in field_state.channels:
        raise ValueError(f"FieldState missing constrained channel {channel_name!r}.")
    payload = dict(constraint_set.payload)
    if payload.get("formula") != "five_phase_conservative_reaction_flow_v1":
        raise ValueError("FivePhase constraint set has unsupported formula.")
    phase_weights = dict(payload["phase_weights"])
    dt = float(payload["dt"])
    diffusion = float(payload["diffusion"])
    transport_gain = float(payload["transport_gain"])
    generative_gain = float(payload["generative_gain"])
    radiant_decay = float(payload["radiant_decay"])
    contractive_relax = float(payload["contractive_relax"])
    max_delta = float(payload["max_delta_per_tick"])
    mass_budget = float(payload["mass_budget_abs"])
    energy_budget = float(payload["energy_budget_abs"])

    u = [[float(value) for value in row] for row in field_state.channels[channel_name]]
    height, width = _shape(u)
    blurred = _blur3x3(u)
    lap = _laplacian_from_grad_diffusion(u, diffusion)
    transport_div = _transport_divergence(u, transport_gain)
    residual_bias = _residual_bias_scalar(residual_constraints, phase_weights)

    candidate_grid: Grid = [[0.0 for _ in range(width)] for _ in range(height)]
    for row in range(height):
        for col in range(width):
            current = u[row][col]
            reaction = (
                lap[row][col]
                - transport_div[row][col]
                + generative_gain * current * (1.0 - current / CARRYING_CAPACITY)
                - radiant_decay * (current ** 3)
                - contractive_relax * (current - blurred[row][col])
                + residual_bias
            )
            raw_delta = dt * reaction
            if abs(raw_delta) > max_delta:
                raw_delta = math.copysign(max_delta, raw_delta)
            next_value = clamp(current + raw_delta, 0.0, 1.0)
            candidate_grid[row][col] = next_value

    def _scale_delta(candidate: Grid, scale: float) -> Grid:
        return [
            [
                clamp(u[row][col] + scale * (candidate[row][col] - u[row][col]), 0.0, 1.0)
                for col in range(width)
            ]
            for row in range(height)
        ]

    next_grid = candidate_grid
    delta_scale = 1.0
    for _ in range(12):
        mass_delta = abs(_field_mass(next_grid) - _field_mass(u))
        energy_delta = abs(_field_energy(next_grid) - _field_energy(u))
        max_abs_delta = max(
            (abs(next_grid[row][col] - u[row][col]) for row in range(height) for col in range(width)),
            default=0.0,
        )
        if (
            mass_delta <= mass_budget + EPS
            and energy_delta <= energy_budget + EPS
            and max_abs_delta <= max_delta + EPS
        ):
            break
        ratios = [1.0]
        if mass_delta > mass_budget + EPS:
            ratios.append(max(mass_budget / max(mass_delta, EPS), 0.0))
        if energy_delta > energy_budget + EPS:
            ratios.append(max(energy_budget / max(energy_delta, EPS), 0.0))
        if max_abs_delta > max_delta + EPS:
            ratios.append(max(max_delta / max(max_abs_delta, EPS), 0.0))
        delta_scale *= max(0.0, min(ratios) * 0.98)
        next_grid = _scale_delta(candidate_grid, delta_scale)
    max_abs_delta = max(
        (abs(next_grid[row][col] - u[row][col]) for row in range(height) for col in range(width)),
        default=0.0,
    )

    channels = {name: [[float(value) for value in row] for row in grid] for name, grid in field_state.channels.items()}
    channels[channel_name] = next_grid
    previous_channels = {name: [[float(value) for value in row] for row in grid] for name, grid in field_state.channels.items()}
    wave_step_record_id = stable_record_id(
        "five-phase-field-step",
        {
            "previous_field_state_id": field_state.field_state_id,
            "constraint_set_id": constraint_set.record_id,
            "tick": tick,
        },
    )
    result_field_state_id = stable_record_id(
        "field-state",
        {
            "previous_field_state_id": field_state.field_state_id,
            "tick": tick,
            "constraint_set_id": constraint_set.record_id,
            "channel": channel_name,
            "grid_digest": next_grid,
        },
    )
    payload_next = dict(field_state.payload)
    source_field_state_ids = list(dict.fromkeys([field_state.field_state_id, *field_state.payload.get("source_field_state_ids", [])]))
    payload_next.update(
        {
            "previous_field_state_id": field_state.field_state_id,
            "source_field_state_ids": source_field_state_ids,
            "field_wave_step_record_id": wave_step_record_id,
            "five_phase_constraint_set_id": constraint_set.record_id,
            "five_phase_residual_constraint_ids": [record.record_id for record in residual_constraints],
        }
    )
    source_record_ids = tuple(
        dict.fromkeys(
            (
                wave_step_record_id,
                field_state.field_state_id,
                constraint_set.record_id,
                *field_state.source_record_ids,
                *constraint_set.source_record_ids,
                *(record.record_id for record in residual_constraints),
            )
        )
    )
    result = FieldState(
        field_state_id=result_field_state_id,
        run_id=field_state.run_id,
        tick=int(tick),
        rule_id="five_phase_conservative_reaction_flow_v1",
        grid_shape=list(field_state.grid_shape),
        channels=channels,
        previous_channels=previous_channels,
        energy=_field_energy(next_grid),
        source_state_ticks=list(dict.fromkeys([*field_state.source_state_ticks, field_state.tick])),
        source_record_ids=list(source_record_ids),
        payload=payload_next,
    )

    mass_before = _field_mass(u)
    mass_after = _field_mass(next_grid)
    energy_before = _field_energy(u)
    energy_after = _field_energy(next_grid)
    audit = {
        "schema": "five_phase_field_step_audit_v1",
        "previous_field_state_id": field_state.field_state_id,
        "result_field_state_id": result.field_state_id,
        "constraint_set_id": constraint_set.record_id,
        "source_record_ids": list(source_record_ids),
        "residual_constraint_ids": [record.record_id for record in residual_constraints],
        "passive_baseline_required": True,
        "formula": "five_phase_conservative_reaction_flow_v1",
        "mass_before": mass_before,
        "mass_after": mass_after,
        "mass_delta_abs": abs(mass_after - mass_before),
        "energy_before": energy_before,
        "energy_after": energy_after,
        "energy_delta_abs": abs(energy_after - energy_before),
        "max_delta": max_abs_delta,
        "total_abs_delta": _diff_abs_sum(u, next_grid),
        "coefficient_bounds": {
            "diffusion": [0.005, 0.18],
            "transport_gain": [0.0, 0.12],
            "generative_gain": [0.0, 0.10],
            "radiant_decay": [0.0, 0.12],
            "contractive_relax": [0.0, 0.10],
        },
        "budget_values": {
            "max_delta_per_tick": max_delta,
            "mass_budget_abs": mass_budget,
            "energy_budget_abs": energy_budget,
        },
        "budget_status": "passed"
        if max_abs_delta <= max_delta + EPS
        and abs(mass_after - mass_before) <= mass_budget + EPS
        and abs(energy_after - energy_before) <= energy_budget + EPS
        else "failed",
        "residual_bias": residual_bias,
        "delta_scale": delta_scale,
    }
    return result, audit


def build_residual_constraint_from_trace(
    trace: FivePhaseTraceRecord,
    *,
    previous_memory: float = 0.0,
    desired_phase_bias: FivePhaseVector | None = None,
    tick: int,
    decay: float = 0.72,
    strength: float = 0.45,
) -> FivePhaseResidualConstraintRecord:
    desired = desired_phase_bias or trace.phase_response
    memory_next = clamp(decay * float(previous_memory) + strength * float(trace.trace_intensity), 0.0, 1.0)
    return FivePhaseResidualConstraintRecord(
        record_id=stable_record_id(
            "five-phase-residual-constraint",
            {"trace_id": trace.record_id, "tick": tick, "memory_next": memory_next, "bias": desired.to_dict()},
        ),
        schema="five_phase_residual_constraint_v1",
        tick=int(tick),
        trace_id=trace.record_id,
        pattern_id=trace.pattern_id,
        phase_field_id=trace.phase_field_id,
        memory_next=memory_next,
        residual_phase_bias=desired.normalized(),
        strength=float(strength),
        decay=float(decay),
        source_record_ids=(trace.record_id, *trace.source_record_ids),
        is_authority_state=False,
    )


def build_agent_state_from_pattern(
    pattern: FivePhasePatternRecord,
    *,
    setpoint: FivePhaseVector | None = None,
    trace: FivePhaseTraceRecord | None = None,
    residual_constraint: FivePhaseResidualConstraintRecord | None = None,
    support_energy_setpoint: float | None = None,
    support_energy_current: float | None = None,
    response_stability: float | None = None,
    bridge_record_id: str | None = None,
    source_state_id: str | None = None,
    source_state_digest: str | None = None,
    tolerance: float = 0.18,
    tick: int | None = None,
) -> FivePhaseAgentStateRecord:
    target = setpoint or (pattern.setpoint if pattern.setpoint is not None else pattern.phase_vector)
    if trace is not None and trace.pattern_id != pattern.record_id:
        raise ValueError("FivePhase Agent trace must cite the exact Pattern instance.")
    if residual_constraint is not None:
        if residual_constraint.pattern_id != pattern.record_id:
            raise ValueError("FivePhase Agent residual must cite the exact Pattern instance.")
        if trace is not None and residual_constraint.trace_id != trace.record_id:
            raise ValueError("FivePhase Agent residual must cite the supplied Trace.")
    semantic_values = (
        trace,
        residual_constraint,
        support_energy_setpoint,
        support_energy_current,
        response_stability,
        bridge_record_id,
        source_state_id,
        source_state_digest,
    )
    is_v2 = any(value is not None for value in semantic_values)
    agent_tick = pattern.tick if tick is None else int(tick)
    normalized_target = target.normalized()
    semantic_payload = {
        "trace_id": trace.record_id if trace is not None else None,
        "residual_constraint_id": residual_constraint.record_id if residual_constraint is not None else None,
        "support_energy_setpoint": support_energy_setpoint,
        "support_energy_current": support_energy_current,
        "response_stability": response_stability,
        "bridge_record_id": bridge_record_id,
        "source_state_id": source_state_id,
        "source_state_digest": source_state_digest,
    }
    identity_payload: dict[str, Any] = {
        "pattern_id": pattern.record_id,
        "tick": agent_tick,
        "setpoint": normalized_target.to_dict(),
    }
    if is_v2:
        identity_payload["semantic_fields"] = semantic_payload
    sources = tuple(
        dict.fromkeys(
            (
                pattern.record_id,
                *(trace.source_record_ids if trace is not None else ()),
                *((trace.record_id,) if trace is not None else ()),
                *(residual_constraint.source_record_ids if residual_constraint is not None else ()),
                *((residual_constraint.record_id,) if residual_constraint is not None else ()),
                *((bridge_record_id,) if bridge_record_id else ()),
                *((source_state_id,) if source_state_id else ()),
                *pattern.source_record_ids,
            )
        )
    )
    return FivePhaseAgentStateRecord(
        record_id=stable_record_id("five-phase-agent-state", identity_payload),
        schema="five_phase_agent_state_v2" if is_v2 else "five_phase_agent_state_v1",
        tick=agent_tick,
        pattern_id=pattern.record_id,
        setpoint=normalized_target,
        boundary_pattern_id=str(pattern.payload.get("boundary_pattern_id")) if pattern.payload.get("boundary_pattern_id") else None,
        repair_policy={"schema": "bounded_setpoint_repair_v1", "gate_width": 0.08, "gain": 0.6},
        tolerance=float(tolerance),
        source_record_ids=sources,
        is_authority_state=False,
        **semantic_payload,
    )


def build_agent_repair_feedback(
    agent_state: FivePhaseAgentStateRecord,
    pattern: FivePhasePatternRecord,
    *,
    tick: int,
    target_basis_id: str | None = None,
    signed_error: float | None = None,
    sensitivity: float | None = None,
    eta: float | None = None,
    gain: float | None = None,
    candidate_projection: Mapping[str, Any] | None = None,
    predecessor_causal_step_id: str | None = None,
) -> FivePhaseFeedbackRecord | None:
    if agent_state.pattern_id != pattern.record_id:
        raise ValueError("FivePhase Feedback Agent must cite the exact Pattern instance.")
    distance = pattern.phase_vector.l2_distance(agent_state.setpoint)
    derived_support_error = None
    if agent_state.support_energy_setpoint is not None and agent_state.support_energy_current is not None:
        derived_support_error = float(agent_state.support_energy_setpoint) - float(agent_state.support_energy_current)
    if signed_error is not None and derived_support_error is not None:
        if abs(float(signed_error) - derived_support_error) > 1e-12:
            raise ValueError("FivePhase Feedback signed_error does not match Agent support energy error.")
    support_error = derived_support_error if signed_error is None else float(signed_error)
    if distance <= agent_state.tolerance and (support_error is None or abs(support_error) <= agent_state.tolerance):
        return None
    gate_width = float(agent_state.repair_policy.get("gate_width", 0.08))
    feedback_gain = float(agent_state.repair_policy.get("gain", 0.6)) if gain is None else float(gain)
    decision_distance = max(distance, abs(support_error) if support_error is not None else 0.0)
    repair_gate = sigmoid((decision_distance - agent_state.tolerance) / max(gate_width, EPS))
    current = pattern.phase_vector.to_dict()
    target = agent_state.setpoint.to_dict()
    phase_bias = FivePhaseVector(
        **{
            name: max(0.0, repair_gate * feedback_gain * (target[name] - current[name]))
            for name in FIVE_PHASE_NAMES
        }
    )
    semantic_values = (
        agent_state.trace_id,
        agent_state.residual_constraint_id,
        agent_state.bridge_record_id,
        agent_state.source_state_id,
        agent_state.source_state_digest,
        target_basis_id,
        support_error,
        sensitivity,
        eta,
        gain,
        candidate_projection,
        predecessor_causal_step_id,
    )
    is_v2 = agent_state.schema == "five_phase_agent_state_v2" or any(value is not None for value in semantic_values)
    if not is_v2 and sum(phase_bias.to_dict().values()) <= 0.0:
        phase_bias = agent_state.setpoint
    candidate_projection_value = dict(candidate_projection) if candidate_projection is not None else None
    candidate_projection_digest = stable_digest(candidate_projection_value) if candidate_projection_value is not None else None
    semantic_payload = {
        "trace_id": agent_state.trace_id,
        "residual_constraint_id": agent_state.residual_constraint_id,
        "bridge_record_id": agent_state.bridge_record_id,
        "source_state_id": agent_state.source_state_id,
        "source_state_digest": agent_state.source_state_digest,
        "target_basis_id": target_basis_id,
        "signed_error": support_error,
        "sensitivity": sensitivity,
        "eta": eta,
        "gain": feedback_gain if is_v2 else None,
        "candidate_projection": candidate_projection_value,
        "candidate_projection_digest": candidate_projection_digest,
        "predecessor_causal_step_id": predecessor_causal_step_id,
    }
    identity_payload: dict[str, Any] = {
        "agent_state_id": agent_state.record_id,
        "pattern_id": pattern.record_id,
        "tick": tick,
        "distance": distance,
    }
    if is_v2:
        identity_payload["semantic_fields"] = semantic_payload
    sources = tuple(
        dict.fromkeys(
            (
                agent_state.record_id,
                pattern.record_id,
                *agent_state.source_record_ids,
                *pattern.source_record_ids,
                *((target_basis_id,) if target_basis_id else ()),
                *((predecessor_causal_step_id,) if predecessor_causal_step_id else ()),
            )
        )
    )
    return FivePhaseFeedbackRecord(
        record_id=stable_record_id("five-phase-feedback", identity_payload),
        schema="five_phase_feedback_v2" if is_v2 else "five_phase_feedback_v1",
        tick=int(tick),
        agent_state_id=agent_state.record_id,
        pattern_id=pattern.record_id,
        phase_l2_distance_before=distance,
        repair_gate=repair_gate,
        phase_bias=phase_bias,
        expected_distance_reduction=min(distance, repair_gate * feedback_gain * distance),
        source_record_ids=sources,
        is_authority_state=False,
        **semantic_payload,
    )


__all__ = [
    "derive_five_phase_constraints",
    "apply_five_phase_constraints",
    "build_residual_constraint_from_trace",
    "build_agent_state_from_pattern",
    "build_agent_repair_feedback",
]
