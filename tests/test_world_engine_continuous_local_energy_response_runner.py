import json
import unittest

from scripts.run_continuous_local_energy_response_validation import (
    run_continuous_local_energy_response_validation,
)


class ContinuousLocalEnergyResponseRunnerTests(unittest.TestCase):
    def test_same_snapshot_parameter_and_feedback_branches_are_causal_and_machine_readable(self):
        report = run_continuous_local_energy_response_validation(
            source_package_name="source-a",
            source_package_digest="digest-source-a",
            run_id="continuous-local-energy-response-test",
            image_shape=(12, 8),
            samples_per_ray=6,
        )

        self.assertEqual("continuous_local_energy_response_validation_v1", report["schema"])
        self.assertEqual("passed", report["overall_status"])
        self.assertEqual([], report["missing_public_api_fields"])
        json.dumps(report, sort_keys=True, allow_nan=False)

        trusted = report["trusted_s0"]
        self.assertTrue(trusted["snapshot_digest"].startswith("sha256:"))
        self.assertTrue(report["same_s0_identity"]["passed"])
        self.assertTrue(report["same_s0_identity"]["branch_labels_are_non_authority"])
        for branch in report["branches"].values():
            self.assertEqual(trusted["snapshot_digest"], branch["restored_snapshot_digest"])
            self.assertEqual(trusted["run_id"], branch["run_id"])
            self.assertEqual(trusted["session_id"], branch["session_id"])
            self.assertFalse(branch["is_authority_state"])
            self.assertNotIn(branch["branch_label"], branch["run_id"])
            self.assertNotIn(branch["branch_label"], branch["session_id"])

        comparisons = report["comparisons"]
        self.assertTrue(comparisons["signed_direction"]["passed"])
        self.assertLess(comparisons["signed_direction"]["dampen_realized_dose"], 0.0)
        self.assertGreater(comparisons["signed_direction"]["excite_realized_dose"], 0.0)
        self.assertTrue(comparisons["amplitude_grading"]["passed"])
        self.assertTrue(comparisons["radius_locality"]["passed"])
        self.assertTrue(comparisons["fractional_duration"]["passed"])
        for comparison_name in (
            "amplitude_continuity",
            "radius_continuity",
            "fractional_duration_continuity",
        ):
            continuity = comparisons[comparison_name]
            self.assertTrue(continuity["passed"])
            self.assertTrue(continuity["same_trusted_s0"])
            self.assertTrue(continuity["feedback_disabled"])
            self.assertTrue(continuity["common_final_horizon"])
            self.assertEqual(0.98, continuity["contraction_rate_ceiling"])
            self.assertGreater(continuity["parameter_delta"], 0.0)
            self.assertGreater(continuity["total_realized_input_delta_l1"], 0.0)
            self.assertGreater(continuity["final_response_delta_l1"], 0.0)
            self.assertLessEqual(
                continuity["final_response_delta_l1"],
                continuity["passive_response_bound_l1"] + 1e-10,
            )

        continuity_labels = {
            "amplitude_neighbor_low",
            "amplitude_neighbor_high",
            "radius_neighbor_low",
            "radius_neighbor_high",
            "duration_neighbor_below_integer",
            "duration_neighbor_above_integer",
        }
        self.assertTrue(continuity_labels.issubset(report["branches"]))
        common_final_tick = report["branches"]["feedback_off_zero"]["final_tick"]
        for label in continuity_labels:
            branch = report["branches"][label]
            self.assertFalse(branch["feedback_enabled_override"])
            self.assertEqual(common_final_tick, branch["final_tick"])
        self.assertEqual(
            [1.0, 0.99],
            report["branches"]["duration_neighbor_below_integer"]["schedule_weights"],
        )
        above_integer_weights = report["branches"]["duration_neighbor_above_integer"][
            "schedule_weights"
        ]
        self.assertEqual([1.0, 1.0], above_integer_weights[:2])
        self.assertAlmostEqual(0.01, above_integer_weights[2])
        self.assertTrue(comparisons["feedback_counterfactual"]["passed"])
        self.assertEqual(
            comparisons["feedback_counterfactual"]["enabled_run_id"],
            comparisons["feedback_counterfactual"]["disabled_run_id"],
        )
        self.assertGreater(comparisons["feedback_counterfactual"]["response_distance"], 0.0)


if __name__ == "__main__":
    unittest.main()
