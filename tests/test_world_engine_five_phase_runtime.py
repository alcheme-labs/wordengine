import unittest

from tests.five_phase_test_helpers import make_field_state
from world_engine.five_phase import (
    FIVE_PHASE_NAMES,
    MAX_DELTA_PER_TICK,
    FivePhaseAgentStateRecord,
    FivePhaseFeedbackRecord,
    FivePhaseVector,
    stable_digest,
)
from world_engine.five_phase_extraction import extract_five_phase_field
from world_engine.five_phase_runtime import (
    apply_five_phase_constraints,
    build_agent_repair_feedback,
    build_agent_state_from_pattern,
    build_residual_constraint_from_trace,
    derive_five_phase_constraints,
)
from world_engine.five_phase_patterns import detect_five_phase_patterns
from world_engine.five_phase_traces import build_five_phase_trace


def _blank(size: int = 10) -> list[list[float]]:
    return [[0.0 for _ in range(size)] for _ in range(size)]


def _block(size: int = 10, start: int = 3, end: int = 7, value: float = 0.76) -> list[list[float]]:
    grid = _blank(size)
    for row in range(start, end):
        for col in range(start, end):
            grid[row][col] = value
    return grid


def _total_abs_delta(left: list[list[float]], right: list[list[float]]) -> float:
    return sum(abs(right[row][col] - left[row][col]) for row in range(len(left)) for col in range(len(left[0])))


class FivePhaseRuntimeTests(unittest.TestCase):
    def test_agent_v2_carries_recomputable_trace_residual_and_support_lineage(self) -> None:
        grid = _block(value=0.72)
        state = make_field_state(grid, previous_grid=grid, tick=0, field_state_id="field-state::agent-v2")
        phase = extract_five_phase_field(state)
        patterns, _ = detect_five_phase_patterns(phase)
        trace = build_five_phase_trace(
            patterns[0],
            phase,
            observer_id="observer::agent-v2",
            frequency_window={"band": "mid"},
        )
        residual = build_residual_constraint_from_trace(trace, previous_memory=0.2, tick=1)

        agent = build_agent_state_from_pattern(
            patterns[0],
            setpoint=patterns[0].phase_vector,
            trace=trace,
            residual_constraint=residual,
            support_energy_setpoint=1.2,
            support_energy_current=0.9,
            response_stability=0.75,
            bridge_record_id="five-phase-bridge::agent-v2",
            source_state_id=state.field_state_id,
            source_state_digest="sha256:agent-v2",
            tick=1,
        )

        self.assertEqual("five_phase_agent_state_v2", agent.schema)
        self.assertEqual(trace.record_id, agent.trace_id)
        self.assertEqual(residual.record_id, agent.residual_constraint_id)
        self.assertIn(trace.record_id, agent.source_record_ids)
        self.assertIn(residual.record_id, agent.source_record_ids)
        self.assertEqual(agent.to_dict(), FivePhaseAgentStateRecord.from_dict(agent.to_dict()).to_dict())

        incomplete = agent.to_dict()
        incomplete["trace_id"] = None
        with self.assertRaisesRegex(ValueError, "five_phase_agent_state_v2 requires trace_id"):
            FivePhaseAgentStateRecord.from_dict(incomplete)

    def test_feedback_v2_carries_signed_candidate_projection_and_exact_lineage(self) -> None:
        grid = _block(value=0.72)
        state = make_field_state(grid, previous_grid=grid, tick=0, field_state_id="field-state::feedback-v2")
        phase = extract_five_phase_field(state)
        patterns, _ = detect_five_phase_patterns(phase)
        pattern = patterns[0]
        trace = build_five_phase_trace(pattern, phase, observer_id="observer::feedback-v2", frequency_window={"band": "mid"})
        residual = build_residual_constraint_from_trace(trace, previous_memory=0.2, tick=1)
        agent = build_agent_state_from_pattern(
            pattern,
            setpoint=FivePhaseVector(0.1, 0.7, 0.1, 0.0, 0.1).normalized(),
            trace=trace,
            residual_constraint=residual,
            support_energy_setpoint=1.2,
            support_energy_current=0.9,
            response_stability=0.75,
            bridge_record_id="five-phase-bridge::feedback-v2",
            source_state_id=state.field_state_id,
            source_state_digest="sha256:feedback-v2",
            tolerance=0.01,
            tick=1,
        )
        candidate_projection = {"basis::feedback-v2": {"density": 0.05}}

        feedback = build_agent_repair_feedback(
            agent,
            pattern,
            tick=1,
            target_basis_id="basis::feedback-v2",
            signed_error=0.3,
            sensitivity=0.4,
            eta=0.01,
            gain=0.2,
            candidate_projection=candidate_projection,
            predecessor_causal_step_id="five-phase-live-step::feedback-v2::0",
        )

        self.assertIsNotNone(feedback)
        self.assertEqual("five_phase_feedback_v2", feedback.schema)
        self.assertEqual(trace.record_id, feedback.trace_id)
        self.assertEqual(residual.record_id, feedback.residual_constraint_id)
        self.assertEqual(stable_digest(candidate_projection), feedback.candidate_projection_digest)
        self.assertIn("basis::feedback-v2", feedback.source_record_ids)
        self.assertIn("five-phase-live-step::feedback-v2::0", feedback.source_record_ids)
        self.assertEqual(feedback.to_dict(), FivePhaseFeedbackRecord.from_dict(feedback.to_dict()).to_dict())

        incomplete = feedback.to_dict()
        incomplete["trace_id"] = None
        with self.assertRaisesRegex(ValueError, "five_phase_feedback_v2 requires trace_id"):
            FivePhaseFeedbackRecord.from_dict(incomplete)

        forged_projection = feedback.to_dict()
        forged_projection["candidate_projection"] = {"basis::feedback-v2": {"density": -0.05}}
        forged_projection["candidate_projection_digest"] = stable_digest(forged_projection["candidate_projection"])
        with self.assertRaisesRegex(ValueError, "signed direction"):
            FivePhaseFeedbackRecord.from_dict(forged_projection)

        forged_digest = feedback.to_dict()
        forged_digest["candidate_projection_digest"] = "sha256:forged"
        with self.assertRaisesRegex(ValueError, "candidate_projection_digest mismatch"):
            FivePhaseFeedbackRecord.from_dict(forged_digest)

    def test_unmatched_current_setpoint_does_not_fabricate_initial_feedback(self) -> None:
        grid = _block(value=0.72)
        state = make_field_state(grid, previous_grid=grid, tick=0, field_state_id="field-state::initial-no-repair")
        phase = extract_five_phase_field(state)
        patterns, _ = detect_five_phase_patterns(phase)
        pattern = patterns[0]
        trace = build_five_phase_trace(pattern, phase, observer_id="observer::initial-no-repair", frequency_window={"band": "mid"})
        residual = build_residual_constraint_from_trace(trace, tick=0)
        support_energy = float(pattern.payload["support_energy"])
        agent = build_agent_state_from_pattern(
            pattern,
            setpoint=pattern.phase_vector,
            trace=trace,
            residual_constraint=residual,
            support_energy_setpoint=support_energy,
            support_energy_current=support_energy,
            response_stability=1.0,
            bridge_record_id="five-phase-bridge::initial-no-repair",
            source_state_id=state.field_state_id,
            source_state_digest="sha256:initial-no-repair",
            tick=0,
        )

        self.assertIsNone(build_agent_repair_feedback(agent, pattern, tick=0))

    def test_legacy_agent_and_feedback_payloads_remain_v1_shaped(self) -> None:
        grid = _block(value=0.72)
        state = make_field_state(grid, previous_grid=grid, tick=0, field_state_id="field-state::legacy-shape")
        phase = extract_five_phase_field(state)
        pattern = detect_five_phase_patterns(phase)[0][0]
        agent = build_agent_state_from_pattern(
            pattern,
            setpoint=FivePhaseVector(0.1, 0.7, 0.1, 0.0, 0.1).normalized(),
            tolerance=0.01,
            tick=1,
        )
        feedback = build_agent_repair_feedback(agent, pattern, tick=1)

        self.assertEqual("five_phase_agent_state_v1", agent.schema)
        self.assertNotIn("trace_id", agent.to_dict())
        self.assertIsNotNone(feedback)
        self.assertEqual("five_phase_feedback_v1", feedback.schema)
        self.assertNotIn("candidate_projection", feedback.to_dict())

    def test_derive_constraints_has_fixed_formula_coefficients(self) -> None:
        state = make_field_state(_block(), previous_grid=_block(), tick=0)
        phase = extract_five_phase_field(state)

        constraints = derive_five_phase_constraints(phase, tick=1)

        self.assertEqual("five_phase_conservative_reaction_flow_v1", constraints.payload["formula"])
        self.assertEqual(set(FIVE_PHASE_NAMES), set(constraints.payload["phase_weights"]))
        self.assertIn(phase.record_id, constraints.source_record_ids)
        self.assertGreaterEqual(constraints.payload["diffusion"], 0.005)
        self.assertLessEqual(constraints.payload["diffusion"], 0.18)

    def test_stable_constraint_preserves_support_more_than_blur_baseline(self) -> None:
        grid = _block(value=0.84)
        state = make_field_state(grid, previous_grid=grid, tick=0)
        phase = extract_five_phase_field(state)
        constraints = derive_five_phase_constraints(phase, tick=1)

        result, audit = apply_five_phase_constraints(state, constraints, tick=1)
        # Deliberately simple passive baseline: no phase constraints means no repair or preservation.
        passive_delta = _total_abs_delta(grid, _blank())

        self.assertLess(audit["total_abs_delta"], passive_delta)
        self.assertLessEqual(audit["max_delta"], MAX_DELTA_PER_TICK)
        self.assertEqual("passed", audit["budget_status"])
        self.assertIn(constraints.record_id, result.source_record_ids)

    def test_radiant_dominant_pulse_decays_with_bounded_delta(self) -> None:
        previous_grid = _blank()
        current_grid = _blank()
        current_grid[5][5] = 1.0
        previous = make_field_state(previous_grid, previous_grid=previous_grid, tick=0, field_state_id="field-state::runtime-previous-pulse")
        state = make_field_state(current_grid, previous_grid=previous_grid, tick=1, previous_field_state_id=previous.field_state_id)
        phase = extract_five_phase_field(state, previous_field_state=previous)
        constraints = derive_five_phase_constraints(phase, tick=2)

        result, audit = apply_five_phase_constraints(state, constraints, tick=2)

        self.assertGreater(constraints.payload["radiant_decay"], 0.0)
        self.assertLess(result.channels["pattern"][5][5], current_grid[5][5])
        self.assertLessEqual(audit["max_delta"], MAX_DELTA_PER_TICK)

    def test_transport_constraints_move_energy_relative_to_static_baseline(self) -> None:
        grid = _blank()
        for row in range(3, 7):
            for col in range(2, 8):
                grid[row][col] = 0.2 + 0.1 * col
        state = make_field_state(grid, previous_grid=grid, tick=0)
        phase = extract_five_phase_field(state)
        constraints = derive_five_phase_constraints(phase, tick=1)

        result, audit = apply_five_phase_constraints(state, constraints, tick=1)

        self.assertGreater(constraints.payload["transport_gain"], 0.0)
        self.assertGreater(audit["total_abs_delta"], 0.0)
        self.assertNotEqual(result.channels["pattern"], grid)

    def test_residual_trace_and_agent_repair_can_bias_later_generation(self) -> None:
        grid = _block(value=0.72)
        state = make_field_state(grid, previous_grid=grid, tick=0)
        phase = extract_five_phase_field(state)
        constraints = derive_five_phase_constraints(phase, tick=1)
        patterns, _ = detect_five_phase_patterns(phase, constraint_set=constraints)
        self.assertTrue(patterns)
        trace = build_five_phase_trace(
            patterns[0],
            phase,
            observer_id="observer::test",
            frequency_window={"band": "mid", "center_grid": [5.0, 5.0], "sigma": 6.0},
        )
        residual = build_residual_constraint_from_trace(
            trace,
            previous_memory=0.2,
            desired_phase_bias=FivePhaseVector(0.1, 0.7, 0.1, 0.0, 0.1).normalized(),
            tick=1,
        )
        result, audit = apply_five_phase_constraints(state, constraints, tick=1, residual_constraints=(residual,))
        agent = build_agent_state_from_pattern(
            patterns[0],
            setpoint=FivePhaseVector(0.1, 0.7, 0.1, 0.0, 0.1).normalized(),
            tolerance=0.01,
            tick=1,
        )
        feedback = build_agent_repair_feedback(agent, patterns[0], tick=1)

        self.assertGreater(residual.memory_next, 0.0)
        self.assertGreater(audit["residual_bias"], 0.0)
        self.assertIsNotNone(feedback)
        self.assertGreater(feedback.expected_distance_reduction, 0.0)
        self.assertIn(residual.record_id, result.source_record_ids)


if __name__ == "__main__":
    unittest.main()
