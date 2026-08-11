from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from world_engine.contracts import FieldState
from world_engine.five_phase import (
    ENERGY_BUDGET_ABS,
    FIVE_PHASE_NAMES,
    MASS_BUDGET_ABS,
    MAX_DELTA_PER_TICK,
    PHASE_PREDICTIVENESS_MIN_IMPROVEMENT,
    SIMPLIFICATION_MIN_ADVANTAGE,
    SIMPLIFICATION_MIN_CASES,
    FivePhaseAgentStateRecord,
    FivePhaseConstraintSetRecord,
    FivePhaseFeedbackRecord,
    FivePhaseFieldRecord,
    FivePhasePatternRecord,
    FivePhaseResidualConstraintRecord,
    FivePhaseTraceRecord,
    reject_authority_shortcuts,
)


@dataclass(frozen=True)
class FivePhaseCompletionResult:
    overall_status: str
    authority_lineage_status: str
    formula_contract_status: str
    runtime_baseline_status: str
    pattern_identity_status: str
    trace_projection_status: str
    residual_feedback_status: str
    phase_predictiveness_status: str
    density_flux_baseline_status: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "authority_lineage_status": self.authority_lineage_status,
            "formula_contract_status": self.formula_contract_status,
            "runtime_baseline_status": self.runtime_baseline_status,
            "pattern_identity_status": self.pattern_identity_status,
            "trace_projection_status": self.trace_projection_status,
            "residual_feedback_status": self.residual_feedback_status,
            "phase_predictiveness_status": self.phase_predictiveness_status,
            "density_flux_baseline_status": self.density_flux_baseline_status,
            "reasons": list(self.reasons),
        }


REQUIRED_METRIC_KEYS = {
    "rho",
    "grad_mag",
    "lap",
    "delta",
    "growth",
    "affinity",
    "mass_gate",
    "F",
    "J",
    "speed",
    "divJ",
    "curlJ",
    "compact",
    "low_grad",
    "normalization",
    "formula",
}

REQUIRED_COEFFICIENT_KEYS = {
    "phase_weights",
    "dt",
    "diffusion",
    "transport_gain",
    "generative_gain",
    "radiant_decay",
    "contractive_relax",
    "substrate_buffer_gain",
    "max_delta_per_tick",
    "mass_budget_abs",
    "energy_budget_abs",
    "formula",
}


def _status(ok: bool) -> str:
    return "passed" if ok else "failed"


def _record_dicts(world_run: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    return [dict(item) for item in world_run.get(key, [])]


def _ids(records: Sequence[Any]) -> set[str]:
    return {str(record.record_id) for record in records}


def _source_set(record: Any) -> set[str]:
    return {str(source) for source in getattr(record, "source_record_ids", ())}


def evaluate_five_phase_pattern_trace_feedback_completion(world_run: Mapping[str, Any]) -> FivePhaseCompletionResult:
    reasons: list[str] = []
    try:
        reject_authority_shortcuts(world_run, path="world_run")
    except ValueError as exc:
        reasons.append(str(exc))
        return FivePhaseCompletionResult(
            overall_status="failed",
            authority_lineage_status="failed",
            formula_contract_status="failed",
            runtime_baseline_status="failed",
            pattern_identity_status="failed",
            trace_projection_status="failed",
            residual_feedback_status="failed",
            phase_predictiveness_status="failed",
            density_flux_baseline_status="failed",
            reasons=tuple(reasons),
        )

    try:
        field_states = [FieldState.from_dict(item) for item in _record_dicts(world_run, "field_states")]
    except (KeyError, TypeError, ValueError) as exc:
        reasons.append(f"field state read-back failed: {exc}")
        field_states = []

    try:
        phase_fields = [FivePhaseFieldRecord.from_dict(item) for item in _record_dicts(world_run, "phase_fields")]
        constraint_sets = [FivePhaseConstraintSetRecord.from_dict(item) for item in _record_dicts(world_run, "constraint_sets")]
        patterns = [FivePhasePatternRecord.from_dict(item) for item in _record_dicts(world_run, "patterns")]
        traces = [FivePhaseTraceRecord.from_dict(item) for item in _record_dicts(world_run, "traces")]
        residuals = [FivePhaseResidualConstraintRecord.from_dict(item) for item in _record_dicts(world_run, "residual_constraints")]
        agent_states = [FivePhaseAgentStateRecord.from_dict(item) for item in _record_dicts(world_run, "agent_states")]
        feedback_records = [FivePhaseFeedbackRecord.from_dict(item) for item in _record_dicts(world_run, "feedback_records")]
    except (KeyError, TypeError, ValueError) as exc:
        reasons.append(f"record contract read-back failed: {exc}")
        phase_fields = []
        constraint_sets = []
        patterns = []
        traces = []
        residuals = []
        agent_states = []
        feedback_records = []

    audits = _record_dicts(world_run, "field_step_audits")
    lifecycle_records = _record_dicts(world_run, "lifecycle_records")
    field_state_ids = {str(state.field_state_id) for state in field_states}
    record_ids = (
        field_state_ids
        | _ids(phase_fields)
        | _ids(constraint_sets)
        | _ids(patterns)
        | _ids(traces)
        | _ids(residuals)
        | _ids(agent_states)
        | _ids(feedback_records)
        | {str(item.get("record_id")) for item in lifecycle_records}
        | {str(audit.get("constraint_set_id")) for audit in audits}
    )

    authority_lineage_ok = bool(field_states and phase_fields and constraint_sets and patterns and traces)
    phase_fields_by_id = {record.record_id: record for record in phase_fields}
    patterns_by_id = {record.record_id: record for record in patterns}
    traces_by_id = {record.record_id: record for record in traces}
    residuals_by_id = {record.record_id: record for record in residuals}
    agents_by_id = {record.record_id: record for record in agent_states}
    if not field_states:
        reasons.append("world_run must include read-back field_states.")
    for phase in phase_fields:
        if phase.is_authority_state:
            authority_lineage_ok = False
            reasons.append(f"{phase.record_id} cannot be authority state.")
        if phase.source_field_state_id not in phase.source_record_ids:
            authority_lineage_ok = False
            reasons.append(f"{phase.record_id} does not cite source_field_state_id.")
        if phase.source_field_state_id not in field_state_ids:
            authority_lineage_ok = False
            reasons.append(f"{phase.record_id} source_field_state_id is missing from read-back field_states.")
    for records in (constraint_sets, patterns, traces, residuals, agent_states, feedback_records):
        for record in records:
            if getattr(record, "is_authority_state", False):
                authority_lineage_ok = False
                reasons.append(f"{record.record_id} incorrectly claims authority state.")
            if not getattr(record, "source_record_ids", ()):
                authority_lineage_ok = False
                reasons.append(f"{record.record_id} has no source_record_ids.")
    for constraint in constraint_sets:
        if constraint.phase_field_id not in record_ids:
            authority_lineage_ok = False
            reasons.append(f"{constraint.record_id} has missing phase field lineage.")
        if constraint.phase_field_id not in _source_set(constraint):
            authority_lineage_ok = False
            reasons.append(f"{constraint.record_id} does not cite phase_field_id in source_record_ids.")
    for pattern in patterns:
        if pattern.phase_field_id not in record_ids:
            authority_lineage_ok = False
            reasons.append(f"{pattern.record_id} has missing phase field lineage.")
        if pattern.phase_field_id not in _source_set(pattern):
            authority_lineage_ok = False
            reasons.append(f"{pattern.record_id} does not cite phase_field_id in source_record_ids.")
    for trace in traces:
        if trace.pattern_id not in record_ids or trace.phase_field_id not in record_ids:
            authority_lineage_ok = False
            reasons.append(f"{trace.record_id} has missing pattern/phase lineage.")
        trace_sources = _source_set(trace)
        if trace.pattern_id not in trace_sources or trace.phase_field_id not in trace_sources:
            authority_lineage_ok = False
            reasons.append(f"{trace.record_id} does not cite pattern_id/phase_field_id in source_record_ids.")
    for residual in residuals:
        if residual.trace_id not in record_ids:
            authority_lineage_ok = False
            reasons.append(f"{residual.record_id} has missing trace lineage.")
        residual_sources = _source_set(residual)
        if (
            residual.trace_id not in residual_sources
            or residual.pattern_id not in residual_sources
            or residual.phase_field_id not in residual_sources
        ):
            authority_lineage_ok = False
            reasons.append(f"{residual.record_id} does not cite trace/pattern/phase lineage in source_record_ids.")
    for agent in agent_states:
        if agent.pattern_id not in record_ids:
            authority_lineage_ok = False
            reasons.append(f"{agent.record_id} has missing pattern lineage.")
        if agent.pattern_id not in _source_set(agent):
            authority_lineage_ok = False
            reasons.append(f"{agent.record_id} does not cite pattern_id in source_record_ids.")
        if agent.schema == "five_phase_agent_state_v2":
            pattern = patterns_by_id.get(agent.pattern_id)
            trace = traces_by_id.get(str(agent.trace_id))
            residual = residuals_by_id.get(str(agent.residual_constraint_id))
            phase = phase_fields_by_id.get(trace.phase_field_id) if trace is not None else None
            if trace is None or residual is None or pattern is None or phase is None:
                authority_lineage_ok = False
                reasons.append(f"{agent.record_id} has missing v2 Pattern/Trace/residual/phase lineage.")
            elif (
                trace.pattern_id != pattern.record_id
                or residual.trace_id != trace.record_id
                or residual.pattern_id != pattern.record_id
                or residual.phase_field_id != trace.phase_field_id
                or phase.source_field_state_id != agent.source_state_id
            ):
                authority_lineage_ok = False
                reasons.append(f"{agent.record_id} v2 Pattern/Trace/residual/state lineage is inconsistent.")
            if agent.source_state_id not in field_state_ids:
                authority_lineage_ok = False
                reasons.append(f"{agent.record_id} v2 source_state_id is missing from field read-back.")
            if pattern is not None and agent.response_stability != pattern.stability_score:
                authority_lineage_ok = False
                reasons.append(f"{agent.record_id} v2 response_stability does not match its Pattern instance.")
    for feedback in feedback_records:
        if feedback.agent_state_id not in record_ids or feedback.pattern_id not in record_ids:
            authority_lineage_ok = False
            reasons.append(f"{feedback.record_id} has missing agent/pattern lineage.")
        feedback_sources = _source_set(feedback)
        if feedback.agent_state_id not in feedback_sources or feedback.pattern_id not in feedback_sources:
            authority_lineage_ok = False
            reasons.append(f"{feedback.record_id} does not cite agent_state_id/pattern_id in source_record_ids.")
        if feedback.schema == "five_phase_feedback_v2":
            agent = agents_by_id.get(feedback.agent_state_id)
            trace = traces_by_id.get(str(feedback.trace_id))
            residual = residuals_by_id.get(str(feedback.residual_constraint_id))
            if agent is None or agent.schema != "five_phase_agent_state_v2" or trace is None or residual is None:
                authority_lineage_ok = False
                reasons.append(f"{feedback.record_id} has missing v2 Agent/Trace/residual lineage.")
            elif (
                feedback.pattern_id != agent.pattern_id
                or feedback.trace_id != agent.trace_id
                or feedback.residual_constraint_id != agent.residual_constraint_id
                or feedback.bridge_record_id != agent.bridge_record_id
                or feedback.source_state_id != agent.source_state_id
                or feedback.source_state_digest != agent.source_state_digest
                or trace.pattern_id != feedback.pattern_id
                or residual.trace_id != trace.record_id
                or residual.pattern_id != feedback.pattern_id
            ):
                authority_lineage_ok = False
                reasons.append(f"{feedback.record_id} v2 causal lineage does not match its Agent decision.")
            if (
                agent is not None
                and agent.support_energy_setpoint is not None
                and agent.support_energy_current is not None
                and feedback.signed_error is not None
            ):
                expected_error = float(agent.support_energy_setpoint) - float(agent.support_energy_current)
                if abs(float(feedback.signed_error) - expected_error) > 1e-12:
                    authority_lineage_ok = False
                    reasons.append(f"{feedback.record_id} signed_error does not match Agent support energy error.")
    for audit in audits:
        previous_field_state_id = str(audit.get("previous_field_state_id", ""))
        result_field_state_id = str(audit.get("result_field_state_id", ""))
        constraint_set_id = str(audit.get("constraint_set_id", ""))
        if previous_field_state_id not in field_state_ids or result_field_state_id not in field_state_ids:
            authority_lineage_ok = False
            reasons.append("field step audit references field states missing from read-back field_states.")
        if constraint_set_id not in record_ids:
            authority_lineage_ok = False
            reasons.append("field step audit references missing constraint_set_id.")
        audit_sources = {str(source) for source in audit.get("source_record_ids", [])}
        if previous_field_state_id not in audit_sources or constraint_set_id not in audit_sources:
            authority_lineage_ok = False
            reasons.append("field step audit does not cite previous field state and constraint set sources.")

    formula_ok = bool(phase_fields and constraint_sets)
    for phase in phase_fields:
        missing = REQUIRED_METRIC_KEYS - set(phase.metrics)
        if missing:
            formula_ok = False
            reasons.append(f"{phase.record_id} missing metrics: {sorted(missing)}")
        if phase.metrics.get("formula") != "five_phase_readback_extraction_v1":
            formula_ok = False
            reasons.append(f"{phase.record_id} has unsupported extraction formula.")
        total = sum(phase.aggregate_phase.to_dict().values())
        if abs(total - 1.0) > 1e-6:
            formula_ok = False
            reasons.append(f"{phase.record_id} aggregate phase is not normalized.")
    for constraint in constraint_sets:
        missing = REQUIRED_COEFFICIENT_KEYS - set(constraint.payload)
        if missing:
            formula_ok = False
            reasons.append(f"{constraint.record_id} missing coefficients: {sorted(missing)}")
        if constraint.payload.get("formula") != "five_phase_conservative_reaction_flow_v1":
            formula_ok = False
            reasons.append(f"{constraint.record_id} has unsupported runtime formula.")
        phase_weights = constraint.payload.get("phase_weights", {})
        if set(phase_weights) != set(FIVE_PHASE_NAMES):
            formula_ok = False
            reasons.append(f"{constraint.record_id} phase_weights keys are invalid.")

    runtime_ok = bool(audits)
    for audit in audits:
        if audit.get("formula") != "five_phase_conservative_reaction_flow_v1":
            runtime_ok = False
            reasons.append("field step audit missing conservative formula.")
        if audit.get("passive_baseline_required") is not True:
            runtime_ok = False
            reasons.append("field step audit does not require passive baseline.")
        budgets = audit.get("budget_values", {})
        if float(budgets.get("max_delta_per_tick", 0.0)) != MAX_DELTA_PER_TICK:
            runtime_ok = False
            reasons.append("field step audit has wrong max_delta budget.")
        if float(budgets.get("mass_budget_abs", 0.0)) != MASS_BUDGET_ABS:
            runtime_ok = False
            reasons.append("field step audit has wrong mass budget.")
        if float(budgets.get("energy_budget_abs", 0.0)) != ENERGY_BUDGET_ABS:
            runtime_ok = False
            reasons.append("field step audit has wrong energy budget.")
        if float(audit.get("max_delta", 999.0)) > MAX_DELTA_PER_TICK + 1e-6:
            runtime_ok = False
            reasons.append("field step max delta exceeds budget.")
        if float(audit.get("mass_delta_abs", 999.0)) > MASS_BUDGET_ABS + 1e-6:
            runtime_ok = False
            reasons.append("field step mass delta exceeds budget.")
        if float(audit.get("energy_delta_abs", 999.0)) > ENERGY_BUDGET_ABS + 1e-6:
            runtime_ok = False
            reasons.append("field step energy delta exceeds budget.")
        if audit.get("budget_status") != "passed":
            runtime_ok = False
            reasons.append("field step audit budget_status is not passed.")

    pattern_ok = bool(patterns)
    pattern_record_ids = [pattern.record_id for pattern in patterns]
    if len(pattern_record_ids) != len(set(pattern_record_ids)):
        pattern_ok = False
        reasons.append("Pattern instance record_id values must be unique.")
    patterns_by_id = {pattern.record_id: pattern for pattern in patterns}
    claimed_predecessors: set[str] = set()
    for pattern in patterns:
        if not pattern.invariant_signature.startswith("five-phase-invariant:sha256:"):
            pattern_ok = False
            reasons.append(f"{pattern.record_id} missing invariant signature.")
        if pattern.payload.get("objects_derive_downstream") is not True:
            pattern_ok = False
            reasons.append(f"{pattern.record_id} does not declare downstream object derivation.")
        pattern_identity_id = pattern.payload.get("pattern_identity_id")
        if not isinstance(pattern_identity_id, str) or not pattern_identity_id:
            pattern_ok = False
            reasons.append(f"{pattern.record_id} missing persistent pattern_identity_id.")
        previous_pattern_record_id = pattern.payload.get("previous_pattern_record_id")
        if previous_pattern_record_id is None:
            continue
        previous_pattern_record_id = str(previous_pattern_record_id)
        previous_pattern = patterns_by_id.get(previous_pattern_record_id)
        if previous_pattern is None:
            pattern_ok = False
            reasons.append(f"{pattern.record_id} previous_pattern_record_id is missing.")
            continue
        if previous_pattern_record_id not in _source_set(pattern):
            pattern_ok = False
            reasons.append(f"{pattern.record_id} does not cite previous_pattern_record_id.")
        if previous_pattern.tick >= pattern.tick:
            pattern_ok = False
            reasons.append(f"{pattern.record_id} previous Pattern must precede the current instance.")
        if previous_pattern.payload.get("pattern_identity_id") != pattern_identity_id:
            pattern_ok = False
            reasons.append(f"{pattern.record_id} changes pattern_identity_id across an exact predecessor link.")
        if previous_pattern_record_id in claimed_predecessors:
            pattern_ok = False
            reasons.append(f"{previous_pattern_record_id} is claimed by multiple Pattern successors.")
        claimed_predecessors.add(previous_pattern_record_id)
    if lifecycle_records and any(item.get("schema") != "boundary_crossing_record_v1" for item in lifecycle_records):
        pattern_ok = False
        reasons.append("lifecycle records must use boundary_crossing_record_v1.")

    trace_ok = bool(traces)
    for trace in traces:
        manifest = trace.projection_loss_manifest
        if manifest.get("schema") != "five_phase_projection_loss_manifest_v1":
            trace_ok = False
            reasons.append(f"{trace.record_id} missing projection loss schema.")
        if manifest.get("is_authority_state") is not False:
            trace_ok = False
            reasons.append(f"{trace.record_id} projection loss cannot be authority.")
        if not manifest.get("discarded_degrees_of_freedom"):
            trace_ok = False
            reasons.append(f"{trace.record_id} missing discarded degrees of freedom.")

    feedback_ok = bool(residuals and agent_states)
    for residual in residuals:
        if residual.memory_next < 0.0 or residual.memory_next > 1.0:
            feedback_ok = False
            reasons.append(f"{residual.record_id} memory_next out of bounds.")
    for feedback in feedback_records:
        if feedback.expected_distance_reduction <= 0.0:
            feedback_ok = False
            reasons.append(f"{feedback.record_id} does not reduce phase distance.")

    predictiveness = dict(world_run.get("phase_predictiveness", {}))
    improvement = float(predictiveness.get("improvement", -1.0))
    phase_predictiveness_ok = improvement >= PHASE_PREDICTIVENESS_MIN_IMPROVEMENT
    if not phase_predictiveness_ok:
        reasons.append("phase predictiveness improvement is below threshold.")

    density_flux = dict(world_run.get("density_flux_only_baseline", {}))
    case_count = int(density_flux.get("case_count", 0))
    five_phase_score = float(density_flux.get("five_phase_score", -1.0))
    density_flux_score = float(density_flux.get("density_flux_score", 0.0))
    density_flux_ok = (
        case_count >= SIMPLIFICATION_MIN_CASES
        and (five_phase_score - density_flux_score) >= SIMPLIFICATION_MIN_ADVANTAGE
    )
    if not density_flux_ok:
        reasons.append("density/flux-only baseline advantage is insufficient.")

    statuses = {
        "authority_lineage_status": authority_lineage_ok,
        "formula_contract_status": formula_ok,
        "runtime_baseline_status": runtime_ok,
        "pattern_identity_status": pattern_ok,
        "trace_projection_status": trace_ok,
        "residual_feedback_status": feedback_ok,
        "phase_predictiveness_status": phase_predictiveness_ok,
        "density_flux_baseline_status": density_flux_ok,
    }
    overall = all(statuses.values())
    return FivePhaseCompletionResult(
        overall_status=_status(overall),
        authority_lineage_status=_status(authority_lineage_ok),
        formula_contract_status=_status(formula_ok),
        runtime_baseline_status=_status(runtime_ok),
        pattern_identity_status=_status(pattern_ok),
        trace_projection_status=_status(trace_ok),
        residual_feedback_status=_status(feedback_ok),
        phase_predictiveness_status=_status(phase_predictiveness_ok),
        density_flux_baseline_status=_status(density_flux_ok),
        reasons=tuple(reasons),
    )


__all__ = ["FivePhaseCompletionResult", "evaluate_five_phase_pattern_trace_feedback_completion"]
