import copy
import tempfile
import unittest
from pathlib import Path

from scripts.run_five_phase_causal_closed_loop_validation import run_five_phase_causal_closed_loop_validation
from world_engine.five_phase_causal import (
    canonical_digest,
    counterfactual_perturbation_stability_failures,
)


class FivePhaseCausalValidationRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary_directory = tempfile.TemporaryDirectory()
        cls.output_dir = Path(cls._temporary_directory.name)
        cls.report = run_five_phase_causal_closed_loop_validation(
            output_dir=cls.output_dir,
            ticks=24,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary_directory.cleanup()

    @staticmethod
    def _self_rehash(evidence):
        evidence["evidence_digest"] = canonical_digest(
            {key: value for key, value in evidence.items() if key != "evidence_digest"}
        )
        return evidence

    def test_runner_emits_pass_report_and_artifacts(self) -> None:
        output_dir = self.output_dir
        report = self.report
        counterfactual = report["counterfactual_perturbation_stability"]

        self.assertEqual("passed", report["overall_status"])
        self.assertEqual(2, report["expected_case_count"])
        self.assertEqual(2, report["case_count"])
        self.assertEqual(2, report["cases_passed"])
        self.assertEqual("passed", report["completion"]["feedback_application_status"])
        self.assertEqual("passed", report["completion"]["causal_direction_status"])
        self.assertEqual("passed", report["completion"]["quality_improvement_status"])
        self.assertGreater(report["completion"]["max_application_error_improvement"], 0.0)
        self.assertGreater(report["comparison"]["max_readback_divergence_l2"], 0.0)
        self.assertIn("pattern_stability_delta", report["comparison"])
        self.assertIn("residual_distance_delta", report["comparison"])
        self.assertEqual("passed", counterfactual["gate_status"])
        self.assertFalse(counterfactual["feedback_enabled"])
        self.assertEqual(8, counterfactual["relaxation_ticks"])
        self.assertEqual(
            counterfactual["t_off"] + 8,
            counterfactual["relaxation_tick"],
        )
        self.assertGreater(
            counterfactual["cumulative_realized_user_dose_through_t_off"],
            0.0,
        )
        self.assertGreater(counterfactual["delta_peak"], 0.0)
        self.assertGreater(counterfactual["counterfactual_stability_score"], 0.0)
        self.assertLessEqual(counterfactual["counterfactual_stability_score"], 1.0)
        self.assertLess(counterfactual["relaxation_ratio"], 1.0)
        self.assertEqual(
            ["amplitude"],
            counterfactual["transcript_request_difference_fields"],
        )
        self.assertEqual(
            counterfactual["control_branch"]["state_tick_id_sequence"],
            counterfactual["zero_branch"]["state_tick_id_sequence"],
        )
        self.assertEqual(
            counterfactual["control_branch"]["step_tick_id_sequence"],
            counterfactual["zero_branch"]["step_tick_id_sequence"],
        )
        self.assertEqual(
            counterfactual["control_branch"]["interaction_audits"][0]["kappa_by_basis"],
            counterfactual["zero_branch"]["interaction_audits"][0]["kappa_by_basis"],
        )
        pattern_support = counterfactual["pattern_support"]
        control_pattern = next(
            pattern
            for pattern in counterfactual["control_branch"]["five_phase_patterns"]
            if pattern["record_id"] == pattern_support["control_pattern_record_id"]
        )
        zero_pattern = next(
            pattern
            for pattern in counterfactual["zero_branch"]["five_phase_patterns"]
            if pattern["record_id"] == pattern_support["zero_pattern_record_id"]
        )
        self.assertEqual(
            control_pattern["payload"]["identity_support_kappa"],
            counterfactual["kappa_by_basis"],
        )
        self.assertEqual(
            zero_pattern["payload"]["identity_support_kappa"],
            counterfactual["kappa_by_basis"],
        )
        measurements = counterfactual["measurements"]
        self.assertEqual(10, len(measurements))
        self.assertEqual(
            list(range(measurements[0]["tick"], counterfactual["relaxation_tick"] + 1)),
            [measurement["tick"] for measurement in measurements],
        )
        self.assertTrue(
            all(measurement["zero_realized_user_norm_kappa"] == 0.0 for measurement in measurements)
        )
        self.assertEqual(
            counterfactual["cumulative_realized_user_dose_through_t_off"],
            next(
                measurement["cumulative_realized_user_dose"]
                for measurement in measurements
                if measurement["tick"] == counterfactual["t_off"]
            ),
        )
        self.assertAlmostEqual(
            max(
                measurement["susceptibility_ratio"]
                for measurement in measurements
                if measurement["tick"] <= counterfactual["t_off"]
            ),
            counterfactual["chi"],
        )
        self.assertAlmostEqual(
            1.0 / (1.0 + counterfactual["chi"]),
            counterfactual["counterfactual_stability_score"],
        )
        self.assertAlmostEqual(
            max(
                measurement["delta_kappa"]
                for measurement in measurements
                if measurement["tick"] <= counterfactual["t_off"]
            ),
            counterfactual["delta_peak"],
        )
        self.assertAlmostEqual(
            counterfactual["relaxation_delta_kappa"] / counterfactual["delta_peak"],
            counterfactual["relaxation_ratio"],
        )
        self.assertTrue((output_dir / "five_phase_causal_closed_loop_report.json").exists())
        self.assertTrue((output_dir / "artifacts" / "enabled_export.json").exists())
        self.assertTrue((output_dir / "artifacts" / "disabled_export.json").exists())
        self.assertTrue((output_dir / "artifacts" / "feedback_effect_probes.json").exists())
        self.assertTrue((output_dir / "artifacts" / "counterfactual_perturbation_stability.json").exists())

    def test_counterfactual_recomputation_rejects_self_rehashed_forgery(self) -> None:
        forged = copy.deepcopy(self.report["counterfactual_perturbation_stability"])
        forged["counterfactual_stability_score"] += 0.25
        self._self_rehash(forged)

        failures = counterfactual_perturbation_stability_failures(forged)

        self.assertIn(
            "counterfactual counterfactual_stability_score does not match recomputation",
            failures,
        )

    def test_counterfactual_recomputation_rejects_duplicate_or_missing_ticks(self) -> None:
        duplicate = copy.deepcopy(self.report["counterfactual_perturbation_stability"])
        duplicate["control_branch"]["implicit_field_states"][-1]["tick"] = duplicate[
            "control_branch"
        ]["implicit_field_states"][-2]["tick"]
        self._self_rehash(duplicate)
        self.assertIn(
            "counterfactual control state ticks must be unique",
            counterfactual_perturbation_stability_failures(duplicate),
        )

        missing = copy.deepcopy(self.report["counterfactual_perturbation_stability"])
        missing["zero_branch"]["implicit_field_states"].pop()
        self._self_rehash(missing)
        self.assertIn(
            "counterfactual state sequence is missing the fixed t_off+8 horizon",
            counterfactual_perturbation_stability_failures(missing),
        )

    def test_counterfactual_recomputation_rejects_zero_branch_user_dose(self) -> None:
        forged = copy.deepcopy(self.report["counterfactual_perturbation_stability"])
        basis_id = next(
            basis_id
            for basis_id, value in forged["kappa_by_basis"].items()
            if value > 0.0
        )
        zero_input_step = next(
            step
            for step in forged["zero_branch"]["implicit_live_steps"]
            if step["tick"] == forged["input_tick"]
        )
        zero_input_step["realized_user_input_projection"] = {
            basis_id: {"density": 0.1}
        }
        self._self_rehash(forged)

        self.assertIn(
            "counterfactual zero branch has non-zero realized USER dose",
            counterfactual_perturbation_stability_failures(forged),
        )

    def test_counterfactual_recomputation_rejects_changed_pattern_identity_support(self) -> None:
        forged = copy.deepcopy(self.report["counterfactual_perturbation_stability"])
        zero_pattern = next(
            pattern
            for pattern in forged["zero_branch"]["five_phase_patterns"]
            if pattern["record_id"]
            == forged["pattern_support"]["zero_pattern_record_id"]
        )
        kappa = zero_pattern["payload"]["identity_support_kappa"]
        basis_id = next(basis_id for basis_id, value in kappa.items() if value > 0.0)
        kappa[basis_id] += 0.1
        zero_pattern["payload"]["identity_support_kappa_digest"] = canonical_digest(kappa)
        self._self_rehash(forged)

        self.assertIn(
            "counterfactual control/zero Patterns do not share one fixed identity support",
            counterfactual_perturbation_stability_failures(forged),
        )


if __name__ == "__main__":
    unittest.main()
