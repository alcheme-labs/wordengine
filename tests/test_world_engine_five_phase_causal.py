import unittest

from world_engine.five_phase_causal import build_feedback_effect_probe_records, merge_projection
from world_engine.implicit_live_session import ImplicitFieldSession


class FivePhaseCausalRuntimeTests(unittest.TestCase):
    def test_merge_projection_adds_channels_by_basis(self) -> None:
        merged = merge_projection(
            [
                {"basis-a": {"density": 0.2}},
                {"basis-a": {"density": 0.3, "direction_x": 1.0}},
                {"basis-b": {"density": -0.1}},
            ]
        )

        self.assertEqual({"density": 0.5, "direction_x": 1.0}, merged["basis-a"])
        self.assertEqual({"density": -0.1}, merged["basis-b"])

    def test_disabled_session_records_candidate_but_does_not_apply_feedback(self) -> None:
        session = ImplicitFieldSession.from_source_package(
            source_package_name="source-a",
            source_package_digest="digest-source-a",
            run_id="five-phase-causal-disabled-test",
            image_shape=[12, 8],
            samples_per_ray=6,
            five_phase_feedback_enabled=False,
        )

        session.advance(2)
        step = session.export_artifacts()["implicit_live_step_records"][-1]
        application = session.export_artifacts()["five_phase_feedback_applications"][-1]

        self.assertFalse(step["five_phase_feedback_enabled"])
        self.assertFalse(step["five_phase_feedback_applied"])
        self.assertEqual({}, step["five_phase_feedback_input_projection"])
        self.assertFalse(application["feedback_enabled"])
        self.assertFalse(application["feedback_applied"])
        self.assertTrue(application["candidate_feedback_projection"])
        self.assertEqual({}, application["applied_feedback_projection"])

    def test_enabled_and_disabled_exports_produce_readback_effect_probe(self) -> None:
        disabled = ImplicitFieldSession.from_source_package(
            source_package_name="source-a",
            source_package_digest="digest-source-a",
            run_id="five-phase-causal-probe-disabled",
            image_shape=[12, 8],
            samples_per_ray=6,
            five_phase_feedback_enabled=False,
        )
        snapshot = disabled.to_snapshot()
        enabled = ImplicitFieldSession.rehydrate_snapshot(
            snapshot,
            expected_snapshot_digest=snapshot["snapshot_digest"],
            five_phase_feedback_enabled_override=True,
        )
        disabled.advance(2)
        enabled.advance(2)

        probes = build_feedback_effect_probe_records(
            run_id="five-phase-causal-probe",
            enabled_export=enabled.export_artifacts(),
            disabled_export=disabled.export_artifacts(),
        )

        self.assertTrue(probes)
        self.assertGreater(max(probe["enabled_minus_disabled_norm"] for probe in probes), 0.0)
        self.assertGreaterEqual(max(probe["isolated_feedback_alignment"] for probe in probes), 0.05)


if __name__ == "__main__":
    unittest.main()
