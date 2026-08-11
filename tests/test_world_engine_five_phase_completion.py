import copy
import unittest

from tests.five_phase_test_helpers import make_field_state
from world_engine.five_phase import FivePhaseVector, stable_digest
from world_engine.five_phase_completion import evaluate_five_phase_pattern_trace_feedback_completion
from world_engine.five_phase_extraction import extract_five_phase_field
from world_engine.five_phase_patterns import detect_five_phase_patterns
from world_engine.five_phase_runtime import (
    apply_five_phase_constraints,
    build_agent_repair_feedback,
    build_agent_state_from_pattern,
    build_residual_constraint_from_trace,
    derive_five_phase_constraints,
)
from world_engine.five_phase_traces import build_five_phase_trace


def _grid() -> list[list[float]]:
    grid = [[0.0 for _ in range(10)] for _ in range(10)]
    for row in range(3, 7):
        for col in range(3, 7):
            grid[row][col] = 0.78
    return grid


def _world_run() -> dict:
    state = make_field_state(_grid(), previous_grid=_grid(), tick=0, field_state_id="field-state::completion")
    phase = extract_five_phase_field(state)
    constraints = derive_five_phase_constraints(phase, tick=1)
    result, audit = apply_five_phase_constraints(state, constraints, tick=1)
    patterns, lifecycle = detect_five_phase_patterns(phase, constraint_set=constraints)
    trace = build_five_phase_trace(patterns[0], phase, observer_id="observer::completion", frequency_window={"band": "mid"})
    residual = build_residual_constraint_from_trace(trace, previous_memory=0.1, tick=1)
    agent = build_agent_state_from_pattern(
        patterns[0],
        setpoint=FivePhaseVector(0.05, 0.8, 0.1, 0.0, 0.05).normalized(),
        tolerance=0.01,
        tick=1,
    )
    feedback = build_agent_repair_feedback(agent, patterns[0], tick=1)
    return {
        "schema": "five_phase_pattern_trace_feedback_world_run_v1",
        "field_states": [state.to_dict(), result.to_dict()],
        "phase_fields": [phase.to_dict()],
        "constraint_sets": [constraints.to_dict()],
        "field_step_audits": [audit],
        "patterns": [pattern.to_dict() for pattern in patterns],
        "lifecycle_records": lifecycle,
        "traces": [trace.to_dict()],
        "residual_constraints": [residual.to_dict()],
        "agent_states": [agent.to_dict()],
        "feedback_records": [feedback.to_dict()] if feedback else [],
        "phase_predictiveness": {"improvement": 0.18, "case_count": 6},
        "density_flux_only_baseline": {
            "case_count": 6,
            "five_phase_score": 0.74,
            "density_flux_score": 0.64,
        },
    }


def _world_run_v2() -> dict:
    world_run = _world_run()
    pattern = world_run["patterns"][0]
    trace = world_run["traces"][0]
    residual = world_run["residual_constraints"][0]
    agent = world_run["agent_states"][0]
    bridge_id = "five-phase-bridge::completion-v2"
    state_id = world_run["field_states"][0]["field_state_id"]
    state_digest = "sha256:completion-v2"
    agent.update(
        {
            "schema": "five_phase_agent_state_v2",
            "trace_id": trace["record_id"],
            "residual_constraint_id": residual["record_id"],
            "support_energy_setpoint": 1.2,
            "support_energy_current": 0.9,
            "response_stability": pattern["stability_score"],
            "bridge_record_id": bridge_id,
            "source_state_id": state_id,
            "source_state_digest": state_digest,
        }
    )
    agent["source_record_ids"] = list(
        dict.fromkeys([*agent["source_record_ids"], trace["record_id"], residual["record_id"], bridge_id, state_id])
    )
    feedback = world_run["feedback_records"][0]
    candidate_projection = {"basis::completion-v2": {"density": 0.05}}
    feedback.update(
        {
            "schema": "five_phase_feedback_v2",
            "trace_id": trace["record_id"],
            "residual_constraint_id": residual["record_id"],
            "bridge_record_id": bridge_id,
            "source_state_id": state_id,
            "source_state_digest": state_digest,
            "target_basis_id": "basis::completion-v2",
            "signed_error": 0.3,
            "sensitivity": 0.4,
            "eta": 0.01,
            "gain": 0.2,
            "candidate_projection": candidate_projection,
            "candidate_projection_digest": stable_digest(candidate_projection),
            "predecessor_causal_step_id": "five-phase-live-step::completion-v2::0",
        }
    )
    feedback["source_record_ids"] = list(
        dict.fromkeys(
            [
                *feedback["source_record_ids"],
                trace["record_id"],
                residual["record_id"],
                bridge_id,
                state_id,
                "basis::completion-v2",
                "five-phase-live-step::completion-v2::0",
            ]
        )
    )
    return world_run


class FivePhaseCompletionTests(unittest.TestCase):
    def test_complete_world_run_passes(self) -> None:
        result = evaluate_five_phase_pattern_trace_feedback_completion(_world_run())

        self.assertEqual("passed", result.overall_status)
        self.assertEqual("passed", result.formula_contract_status)
        self.assertEqual("passed", result.trace_projection_status)
        self.assertEqual("passed", result.residual_feedback_status)

    def test_completion_rejects_viewer_shortcut_anywhere(self) -> None:
        world_run = _world_run()
        world_run["phase_fields"][0]["metrics"]["viewer_color"] = "green"

        result = evaluate_five_phase_pattern_trace_feedback_completion(world_run)

        self.assertEqual("failed", result.overall_status)
        self.assertEqual("failed", result.authority_lineage_status)

    def test_completion_rejects_missing_formula_metric(self) -> None:
        world_run = _world_run()
        del world_run["phase_fields"][0]["metrics"]["curlJ"]

        result = evaluate_five_phase_pattern_trace_feedback_completion(world_run)

        self.assertEqual("failed", result.overall_status)
        self.assertEqual("failed", result.formula_contract_status)

    def test_completion_rejects_weak_predictiveness_and_density_baseline(self) -> None:
        world_run = _world_run()
        world_run["phase_predictiveness"]["improvement"] = 0.02
        world_run["density_flux_only_baseline"]["five_phase_score"] = 0.65

        result = evaluate_five_phase_pattern_trace_feedback_completion(world_run)

        self.assertEqual("failed", result.overall_status)
        self.assertEqual("failed", result.phase_predictiveness_status)
        self.assertEqual("failed", result.density_flux_baseline_status)

    def test_completion_rejects_trace_missing_projection_loss(self) -> None:
        world_run = _world_run()
        world_run["traces"][0]["projection_loss_manifest"] = {}

        result = evaluate_five_phase_pattern_trace_feedback_completion(world_run)

        self.assertEqual("failed", result.overall_status)
        self.assertEqual("failed", result.trace_projection_status)

    def test_completion_rejects_field_step_budget_violation(self) -> None:
        world_run = _world_run()
        world_run["field_step_audits"][0]["energy_delta_abs"] = 10.0

        result = evaluate_five_phase_pattern_trace_feedback_completion(world_run)

        self.assertEqual("failed", result.overall_status)
        self.assertEqual("failed", result.runtime_baseline_status)

    def test_completion_rejects_missing_source_field_state_readback(self) -> None:
        world_run = _world_run()
        world_run["field_states"] = world_run["field_states"][1:]

        result = evaluate_five_phase_pattern_trace_feedback_completion(world_run)

        self.assertEqual("failed", result.overall_status)
        self.assertEqual("failed", result.authority_lineage_status)

    def test_completion_rejects_missing_field_states_artifact(self) -> None:
        world_run = _world_run()
        del world_run["field_states"]

        result = evaluate_five_phase_pattern_trace_feedback_completion(world_run)

        self.assertEqual("failed", result.overall_status)
        self.assertEqual("failed", result.authority_lineage_status)

    def test_completion_rejects_trace_source_without_pattern_or_phase(self) -> None:
        world_run = _world_run()
        world_run["traces"][0]["source_record_ids"] = ["field-evidence::trace-shortcut"]

        result = evaluate_five_phase_pattern_trace_feedback_completion(world_run)

        self.assertEqual("failed", result.overall_status)
        self.assertEqual("failed", result.authority_lineage_status)

    def test_completion_rejects_feedback_source_without_agent_or_pattern(self) -> None:
        world_run = _world_run()
        world_run["feedback_records"][0]["source_record_ids"] = ["field-evidence::feedback-shortcut"]

        result = evaluate_five_phase_pattern_trace_feedback_completion(world_run)

        self.assertEqual("failed", result.overall_status)
        self.assertEqual("failed", result.authority_lineage_status)

    def test_completion_rejects_duplicate_pattern_instance_record_id(self) -> None:
        world_run = _world_run()
        world_run["patterns"].append(copy.deepcopy(world_run["patterns"][0]))

        result = evaluate_five_phase_pattern_trace_feedback_completion(world_run)

        self.assertEqual("failed", result.overall_status)
        self.assertEqual("failed", result.pattern_identity_status)

    def test_completion_rejects_v2_agent_trace_outside_exact_lineage(self) -> None:
        world_run = _world_run_v2()
        world_run["agent_states"][0]["trace_id"] = "five-phase-trace::forged"
        world_run["agent_states"][0]["source_record_ids"].append("five-phase-trace::forged")

        result = evaluate_five_phase_pattern_trace_feedback_completion(world_run)

        self.assertEqual("failed", result.overall_status)
        self.assertEqual("failed", result.authority_lineage_status)


if __name__ == "__main__":
    unittest.main()
