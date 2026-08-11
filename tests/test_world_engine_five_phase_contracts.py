import unittest

from world_engine.five_phase import (
    FIVE_PHASE_NAMES,
    FivePhaseConstraintSetRecord,
    FivePhaseFieldRecord,
    FivePhaseVector,
    validate_phase_vector,
)


class FivePhaseContractTests(unittest.TestCase):
    def test_phase_names_are_neutral_and_fixed(self) -> None:
        self.assertEqual(
            FIVE_PHASE_NAMES,
            ("contractive", "generative", "transport", "radiant", "substrate"),
        )

    def test_phase_vector_requires_all_five_finite_nonnegative_weights(self) -> None:
        vector = FivePhaseVector(
            contractive=0.8,
            generative=0.1,
            transport=0.2,
            radiant=0.0,
            substrate=0.4,
        )
        validate_phase_vector(vector)
        self.assertEqual(vector.dominant_phase(), "contractive")
        normalized = vector.normalized()
        self.assertAlmostEqual(1.0, sum(normalized.to_dict().values()), places=8)

    def test_phase_vector_rejects_missing_and_extra_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, "keys"):
            FivePhaseVector.from_dict(
                {
                    "contractive": 1.0,
                    "generative": 0.0,
                    "transport": 0.0,
                    "radiant": 0.0,
                }
            )

    def test_field_record_is_non_authority_and_cites_field_state(self) -> None:
        record = FivePhaseFieldRecord(
            record_id="five-phase-field::case::1",
            schema="five_phase_field_v1",
            tick=1,
            source_field_state_id="field-state::case::1",
            grid_shape=(4, 4),
            aggregate_phase=FivePhaseVector(0.7, 0.1, 0.2, 0.0, 0.5).normalized(),
            cell_phase_vectors=[],
            metrics={"mean_energy": 0.4},
            source_record_ids=("field-state::case::1",),
            is_authority_state=False,
        )
        roundtrip = FivePhaseFieldRecord.from_dict(record.to_dict())
        self.assertEqual(roundtrip.to_dict(), record.to_dict())
        self.assertFalse(roundtrip.is_authority_state)

    def test_field_record_rejects_missing_source_field_state_citation(self) -> None:
        with self.assertRaisesRegex(ValueError, "source_field_state_id"):
            FivePhaseFieldRecord(
                record_id="five-phase-field::case::missing-source",
                schema="five_phase_field_v1",
                tick=1,
                source_field_state_id="field-state::case::1",
                grid_shape=(4, 4),
                aggregate_phase=FivePhaseVector(0.7, 0.1, 0.2, 0.0, 0.5).normalized(),
                cell_phase_vectors=[],
                metrics={"mean_energy": 0.4},
                source_record_ids=("field-evidence::shortcut",),
                is_authority_state=False,
            )

    def test_constraint_set_rejects_viewer_shortcuts(self) -> None:
        with self.assertRaisesRegex(ValueError, "viewer_color"):
            FivePhaseConstraintSetRecord(
                record_id="five-phase-constraint-set::bad",
                schema="five_phase_constraint_set_v1",
                tick=1,
                phase_field_id="five-phase-field::1",
                payload={"viewer_color": "#fff"},
                source_record_ids=("five-phase-field::1",),
            )

    def test_constraint_set_rejects_authority_claim(self) -> None:
        with self.assertRaisesRegex(ValueError, "not authority"):
            FivePhaseConstraintSetRecord(
                record_id="five-phase-constraint-set::authority",
                schema="five_phase_constraint_set_v1",
                tick=1,
                phase_field_id="five-phase-field::1",
                payload={"formula": "five_phase_conservative_reaction_flow_v1"},
                source_record_ids=("five-phase-field::1",),
                is_authority_state=True,
            )


if __name__ == "__main__":
    unittest.main()
