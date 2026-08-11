import unittest

from tests.five_phase_test_helpers import make_field_state
from world_engine.five_phase_extraction import extract_five_phase_field
from world_engine.five_phase_patterns import (
    derive_world_objects_from_five_phase_patterns,
    detect_five_phase_patterns,
)
from world_engine.five_phase_runtime import derive_five_phase_constraints


def _two_blocks() -> list[list[float]]:
    grid = [[0.0 for _ in range(10)] for _ in range(10)]
    for row in range(2, 5):
        for col in range(2, 5):
            grid[row][col] = 0.75
    for row in range(6, 8):
        for col in range(6, 9):
            grid[row][col] = 0.65
    return grid


class FivePhasePatternTests(unittest.TestCase):
    def test_detect_patterns_from_phase_support_and_invariant_signature(self) -> None:
        state = make_field_state(_two_blocks(), previous_grid=_two_blocks(), tick=0)
        phase = extract_five_phase_field(state)
        constraints = derive_five_phase_constraints(phase, tick=1)

        patterns, lifecycle = detect_five_phase_patterns(phase, constraint_set=constraints)

        self.assertEqual(2, len(patterns))
        self.assertTrue(all(pattern.invariant_signature.startswith("five-phase-invariant:sha256:") for pattern in patterns))
        self.assertTrue(all(pattern.phase_field_id == phase.record_id for pattern in patterns))
        self.assertEqual("boundary_crossing_record_v1", lifecycle[0]["schema"])

    def test_pattern_continuity_uses_unique_instances_and_persistent_identity(self) -> None:
        first_grid = _two_blocks()
        second_grid = _two_blocks()
        second_grid[4][4] = 0.75
        first = make_field_state(first_grid, previous_grid=first_grid, tick=0, field_state_id="field-state::patterns::0")
        second = make_field_state(second_grid, previous_grid=first_grid, tick=1, previous_field_state_id=first.field_state_id)
        first_phase = extract_five_phase_field(first)
        first_patterns, _ = detect_five_phase_patterns(first_phase)
        second_phase = extract_five_phase_field(second, previous_field_state=first)

        second_patterns, _ = detect_five_phase_patterns(second_phase, previous_patterns=first_patterns)

        self.assertNotEqual(first_patterns[0].record_id, second_patterns[0].record_id)
        self.assertEqual(
            first_patterns[0].payload["pattern_identity_id"],
            second_patterns[0].payload["pattern_identity_id"],
        )
        self.assertEqual(first_patterns[0].record_id, second_patterns[0].payload["previous_pattern_record_id"])
        self.assertIn(first_patterns[0].record_id, second_patterns[0].source_record_ids)
        self.assertGreater(second_patterns[0].continuity_score, 0.25)

    def test_supplied_live_response_context_drives_episode_stability(self) -> None:
        grid = _two_blocks()
        first = make_field_state(grid, previous_grid=grid, tick=0, field_state_id="field-state::patterns::episode::0")
        second = make_field_state(
            grid,
            previous_grid=grid,
            tick=1,
            field_state_id="field-state::patterns::episode::1",
            previous_field_state_id=first.field_state_id,
        )
        first_phase = extract_five_phase_field(first)
        first_patterns, _ = detect_five_phase_patterns(first_phase)
        second_phase = extract_five_phase_field(second, previous_field_state=first)
        identity_id = first_patterns[0].payload["pattern_identity_id"]

        second_patterns, _ = detect_five_phase_patterns(
            second_phase,
            previous_patterns=first_patterns,
            response_context_by_pattern_identity_id={
                identity_id: {
                    "episode_id": "episode::patterns::1",
                    "episode_start_tick": 1,
                    "last_user_input_tick": 1,
                    "episode_end_tick": 9,
                    "support_energy_prior": 1.8,
                    "support_energy_setpoint": 2.0,
                    "support_energy_current": 3.0,
                    "realized_user_dose": 0.25,
                    "realized_feedback_dose": 0.05,
                }
            },
        )

        pattern = second_patterns[0]
        self.assertAlmostEqual(1.8, pattern.payload["support_energy_prior"])
        self.assertAlmostEqual(0.5, pattern.payload["deformation_from_setpoint"])
        self.assertAlmostEqual(0.25, pattern.payload["q_user"])
        self.assertAlmostEqual(0.25, pattern.payload["Q_live"])
        self.assertAlmostEqual(0.25, pattern.payload["cumulative_realized_user_dose"])
        self.assertAlmostEqual(1.0 / 3.0, pattern.stability_score)
        self.assertEqual("active", pattern.payload["episode_status"])
        self.assertEqual("five_phase_live_response_stability_v2", pattern.payload["stability_formula"])
        self.assertEqual(
            "absolute_support_energy_delta_over_setpoint_v1",
            pattern.payload["deformation_normalization"],
        )
        self.assertAlmostEqual(0.05, pattern.payload["realized_feedback_dose"])
        self.assertAlmostEqual(0.05, pattern.payload["q_feedback"])

    def test_world_objects_are_downstream_of_patterns(self) -> None:
        state = make_field_state(_two_blocks(), previous_grid=_two_blocks(), tick=0)
        phase = extract_five_phase_field(state)
        patterns, _ = detect_five_phase_patterns(phase)

        objects = derive_world_objects_from_five_phase_patterns(patterns)

        self.assertEqual(len(patterns), len(objects))
        self.assertTrue(all(obj.payload["five_phase_pattern_projection"] for obj in objects))
        self.assertTrue(all(obj.payload["derived_from_five_phase_pattern_id"] for obj in objects))


if __name__ == "__main__":
    unittest.main()
