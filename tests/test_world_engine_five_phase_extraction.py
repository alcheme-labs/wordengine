import unittest

from tests.five_phase_test_helpers import make_field_state
from world_engine.five_phase_extraction import extract_five_phase_field


def _blank(size: int = 8) -> list[list[float]]:
    return [[0.0 for _ in range(size)] for _ in range(size)]


def _block(size: int = 8, start: int = 2, end: int = 5, value: float = 0.8) -> list[list[float]]:
    grid = _blank(size)
    for row in range(start, end):
        for col in range(start, end):
            grid[row][col] = value
    return grid


class FivePhaseExtractionTests(unittest.TestCase):
    def test_stable_dense_block_extracts_contract_substrate_structure(self) -> None:
        grid = _block(value=0.82)
        state = make_field_state(grid, previous_grid=grid, tick=0)

        phase = extract_five_phase_field(state)
        values = phase.aggregate_phase.to_dict()

        self.assertEqual("five_phase_readback_extraction_v1", phase.metrics["formula"])
        self.assertTrue({"rho", "grad_mag", "lap", "delta", "growth", "affinity", "mass_gate", "F", "J", "speed", "divJ", "curlJ", "compact", "low_grad", "normalization"}.issubset(phase.metrics))
        self.assertGreater(values["contractive"] + values["substrate"], values["generative"] + values["radiant"])
        self.assertAlmostEqual(1.0, sum(values.values()), places=6)
        self.assertIn(state.field_state_id, phase.source_record_ids)

    def test_expanding_support_increases_generative_phase(self) -> None:
        previous_grid = _block(start=3, end=5, value=0.55)
        current_grid = _block(start=2, end=6, value=0.62)
        previous = make_field_state(previous_grid, previous_grid=previous_grid, tick=0, field_state_id="field-state::previous")
        current = make_field_state(
            current_grid,
            previous_grid=previous_grid,
            tick=1,
            previous_field_state_id=previous.field_state_id,
        )

        previous_phase = extract_five_phase_field(previous)
        current_phase = extract_five_phase_field(current, previous_field_state=previous)

        self.assertGreater(
            current_phase.aggregate_phase.to_dict()["generative"],
            previous_phase.aggregate_phase.to_dict()["generative"],
        )

    def test_high_delta_pulse_extracts_radiant_phase(self) -> None:
        previous_grid = _blank()
        current_grid = _blank()
        for row in range(3, 5):
            for col in range(3, 5):
                current_grid[row][col] = 1.0
        previous = make_field_state(previous_grid, previous_grid=previous_grid, tick=0, field_state_id="field-state::previous-pulse")
        current = make_field_state(
            current_grid,
            previous_grid=previous_grid,
            tick=1,
            previous_field_state_id=previous.field_state_id,
        )

        phase = extract_five_phase_field(current, previous_field_state=previous)
        values = phase.aggregate_phase.to_dict()

        self.assertGreater(values["radiant"], values["substrate"])
        self.assertGreater(values["radiant"], values["generative"])

    def test_extraction_rejects_viewer_payload_shortcut(self) -> None:
        state = make_field_state(_block(), previous_grid=_block(), tick=0)
        state.payload["viewer_color"] = "green"

        with self.assertRaisesRegex(ValueError, "viewer_color"):
            extract_five_phase_field(state)

    def test_extraction_rejects_missing_channel(self) -> None:
        state = make_field_state(_block(), previous_grid=_block(), tick=0)
        with self.assertRaisesRegex(ValueError, "missing"):
            extract_five_phase_field(state, channel_name="missing")

    def test_extraction_emits_source_record_ids(self) -> None:
        state = make_field_state(_block(), previous_grid=_block(), tick=0)
        phase = extract_five_phase_field(state)
        self.assertTrue(phase.source_record_ids)
        self.assertIn(state.field_state_id, phase.source_record_ids)


if __name__ == "__main__":
    unittest.main()
