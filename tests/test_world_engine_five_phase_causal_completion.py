import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_five_phase_causal_closed_loop_validation import run_five_phase_causal_closed_loop_validation
from world_engine.five_phase_causal import canonical_digest, canonical_json_bytes
from world_engine.five_phase_causal_completion import evaluate_five_phase_causal_completion


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _refresh_branch_manifest(bundle, branch: str) -> None:
    exported = bundle[f"{branch}_export"]
    manifest = bundle[f"{branch}_manifest"]
    export_digest = canonical_digest(exported)
    manifest["export_digest"] = export_digest
    manifest["artifact_bytes"] = canonical_json_bytes(exported)
    manifest["source_record_ids"] = [
        manifest["initial_snapshot_digest"],
        manifest["perturbation_schedule_digest"],
        export_digest,
    ]
    manifest.pop("manifest_digest", None)
    manifest["manifest_digest"] = canonical_digest(manifest)


def _rehash_counterfactual(evidence) -> None:
    evidence.pop("evidence_digest", None)
    evidence["evidence_digest"] = canonical_digest(evidence)


def _persist_counterfactual_artifact(bundle, path: Path) -> None:
    key = "counterfactual_perturbation_stability"
    path.write_text(
        json.dumps(bundle[key], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    previous_size = int(bundle["artifact_bytes_by_file"][key])
    current_size = path.stat().st_size
    bundle["artifact_paths"][key] = str(path)
    bundle["artifact_bytes_by_file"][key] = current_size
    bundle["artifact_bytes_total"] = (
        int(bundle["artifact_bytes_total"]) - previous_size + current_size
    )


class FivePhaseCausalCompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.output_dir = Path(cls._tmp.name)
        cls.report = run_five_phase_causal_closed_loop_validation(output_dir=cls.output_dir, ticks=8)
        artifact_dir = cls.output_dir / "artifacts"
        cls.bundle = {
            "schema": "five_phase_causal_completion_bundle_v1",
            "run_id": cls.report["run_id"],
            "enabled_export": _read_json(artifact_dir / "enabled_export.json"),
            "disabled_export": _read_json(artifact_dir / "disabled_export.json"),
            "enabled_manifest": _read_json(artifact_dir / "enabled_manifest.json"),
            "disabled_manifest": _read_json(artifact_dir / "disabled_manifest.json"),
            "perturbation_schedule": _read_json(artifact_dir / "perturbation_schedule.json"),
            "tick_metrics": _read_json(artifact_dir / "tick_metrics.json"),
            "feedback_effect_probes": _read_json(artifact_dir / "feedback_effect_probes.json"),
            "comparison": _read_json(artifact_dir / "causal_comparison.json"),
            "counterfactual_perturbation_stability": _read_json(
                artifact_dir / "counterfactual_perturbation_stability.json"
            ),
            "artifact_bytes_total": cls.report["artifact_bytes_total"],
            "artifact_bytes_by_file": cls.report["artifact_bytes_by_file"],
            "artifact_budget_bytes": cls.report["artifact_budget_bytes"],
            "artifact_paths": cls.report["artifact_paths"],
        }

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def _bundle(self):
        return copy.deepcopy(self.bundle)

    def test_completion_passes_readback_bundle(self) -> None:
        result = evaluate_five_phase_causal_completion(self._bundle())
        self.assertEqual("passed", result["overall_status"])
        self.assertEqual("passed", result["paired_baseline_status"])
        self.assertEqual("passed", result["feedback_application_status"])
        self.assertEqual("passed", result["causal_direction_status"])
        self.assertEqual("passed", result["quality_improvement_status"])

    def test_completion_rejects_self_rehashed_counterfactual_chi(self) -> None:
        bundle = self._bundle()
        evidence = bundle["counterfactual_perturbation_stability"]
        evidence["chi"] += 0.25
        _rehash_counterfactual(evidence)

        result = evaluate_five_phase_causal_completion(bundle)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["counterfactual_stability_status"])

    def test_completion_rejects_missing_counterfactual_evidence(self) -> None:
        bundle = self._bundle()
        bundle.pop("counterfactual_perturbation_stability")

        result = evaluate_five_phase_causal_completion(bundle)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["counterfactual_stability_status"])

    def test_completion_rejects_self_rehashed_counterfactual_relaxation_ratio(self) -> None:
        bundle = self._bundle()
        evidence = bundle["counterfactual_perturbation_stability"]
        evidence["relaxation_ratio"] = 0.0
        _rehash_counterfactual(evidence)

        result = evaluate_five_phase_causal_completion(bundle)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["counterfactual_stability_status"])

    def test_completion_rejects_self_rehashed_counterfactual_transcript_mismatch(self) -> None:
        bundle = self._bundle()
        evidence = bundle["counterfactual_perturbation_stability"]
        zero_request = evidence["zero_branch"]["interaction_transcript"][0]["request"]
        zero_request["radius_world"] += 0.125
        _rehash_counterfactual(evidence)

        result = evaluate_five_phase_causal_completion(bundle)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["counterfactual_stability_status"])

    def test_completion_rejects_control_scope_kappa_as_pattern_support_kappa(self) -> None:
        bundle = self._bundle()
        evidence = bundle["counterfactual_perturbation_stability"]
        evidence["kappa_by_basis"] = copy.deepcopy(evidence["control_scope_kappa_by_basis"])
        _rehash_counterfactual(evidence)

        result = evaluate_five_phase_causal_completion(bundle)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["counterfactual_stability_status"])

    def test_completion_rejects_counterfactual_detached_from_main_session_config(self) -> None:
        bundle = self._bundle()
        evidence = bundle["counterfactual_perturbation_stability"]
        evidence["trusted_configuration"]["session_id"] = "detached-session"
        evidence["trusted_configuration_digest"] = canonical_digest(evidence["trusted_configuration"])
        evidence["control_branch"]["session"]["session_id"] = "detached-session"
        evidence["zero_branch"]["session"]["session_id"] = "detached-session"
        _rehash_counterfactual(evidence)

        result = evaluate_five_phase_causal_completion(bundle)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["counterfactual_stability_status"])

    def test_completion_rejects_self_rehashed_counterfactual_transition_forgery(self) -> None:
        bundle = self._bundle()
        evidence = bundle["counterfactual_perturbation_stability"]
        final_state = evidence["control_branch"]["implicit_field_states"][-1]
        basis_id = final_state["basis_ids"][0]
        channel_name = next(
            channel
            for channel in final_state["basis_coefficients"][basis_id]
            if channel != "density"
        )
        final_state["basis_coefficients"][basis_id][channel_name] += 0.125
        final_state.pop("state_digest", None)
        final_state["state_digest"] = canonical_digest(final_state)
        evidence["control_branch"]["implicit_live_steps"][-1][
            "result_state_digest"
        ] = final_state["state_digest"]
        evidence["measurements"][-1]["control_state_digest"] = final_state[
            "state_digest"
        ]
        _rehash_counterfactual(evidence)
        _persist_counterfactual_artifact(
            bundle,
            self.output_dir / "forged-counterfactual-transition.json",
        )

        result = evaluate_five_phase_causal_completion(bundle)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["counterfactual_stability_status"])

    def test_completion_rejects_counterfactual_forged_source_frame_lineage(self) -> None:
        bundle = self._bundle()
        evidence = bundle["counterfactual_perturbation_stability"]
        forged_frame_id = "projection-frame::forged-counterfactual-source"
        for branch_name in ("control_branch", "zero_branch"):
            branch = evidence[branch_name]
            branch["interaction_transcript"][0]["request"][
                "source_projection_frame_id"
            ] = forged_frame_id
            branch["interaction_audits"][0][
                "source_projection_frame_id"
            ] = forged_frame_id
        _rehash_counterfactual(evidence)
        _persist_counterfactual_artifact(
            bundle,
            self.output_dir / "forged-counterfactual-source-frame.json",
        )

        result = evaluate_five_phase_causal_completion(bundle)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["counterfactual_stability_status"])

    def test_completion_rejects_different_canonical_run_id(self) -> None:
        bundle = self._bundle()
        bundle["disabled_export"]["session"]["run_id"] = "different-run"
        bundle["disabled_manifest"]["run_id"] = "different-run"
        _refresh_branch_manifest(bundle, "disabled")

        result = evaluate_five_phase_causal_completion(bundle)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["paired_baseline_status"])

    def test_completion_rejects_different_canonical_session_id(self) -> None:
        bundle = self._bundle()
        bundle["disabled_export"]["session"]["session_id"] = "different-session"
        _refresh_branch_manifest(bundle, "disabled")

        result = evaluate_five_phase_causal_completion(bundle)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["paired_baseline_status"])

    def test_completion_rejects_different_canonical_source_identity(self) -> None:
        bundle = self._bundle()
        bundle["disabled_export"]["session"]["source_package_digest"] = "different-source-digest"
        bundle["disabled_manifest"]["source_package_digest"] = "different-source-digest"
        _refresh_branch_manifest(bundle, "disabled")

        result = evaluate_five_phase_causal_completion(bundle)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["paired_baseline_status"])

    def test_completion_rejects_different_canonical_runtime_configuration(self) -> None:
        bundle = self._bundle()
        bundle["disabled_export"]["implicit_ray_sample_records"][0]["samples_per_ray"] += 1
        _refresh_branch_manifest(bundle, "disabled")

        result = evaluate_five_phase_causal_completion(bundle)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["paired_baseline_status"])

    def test_completion_rejects_different_canonical_s0(self) -> None:
        bundle = self._bundle()
        initial_state = bundle["disabled_export"]["implicit_field_states"][0]
        initial_state["source_record_ids"].append("different-s0-source")
        initial_state.pop("state_digest", None)
        initial_state["state_digest"] = canonical_digest(initial_state)
        bundle["disabled_export"]["implicit_live_step_records"][0]["previous_state_digest"] = initial_state[
            "state_digest"
        ]
        _refresh_branch_manifest(bundle, "disabled")

        result = evaluate_five_phase_causal_completion(bundle)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["paired_baseline_status"])

    def test_completion_rejects_matching_but_forged_s0_digest(self) -> None:
        bundle = self._bundle()
        for branch in ("enabled", "disabled"):
            initial_state = bundle[f"{branch}_export"]["implicit_field_states"][0]
            initial_state["state_digest"] = "sha256:forged-s0"
            bundle[f"{branch}_export"]["implicit_live_step_records"][0]["previous_state_digest"] = initial_state[
                "state_digest"
            ]
            _refresh_branch_manifest(bundle, branch)

        result = evaluate_five_phase_causal_completion(bundle)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["paired_baseline_status"])

    def test_completion_rejects_different_recomputed_basis_layout(self) -> None:
        bundle = self._bundle()
        initial_state = bundle["disabled_export"]["implicit_field_states"][0]
        initial_state["basis_layout_digest"] = "sha256:different-layout"
        initial_state.pop("state_digest", None)
        initial_state["state_digest"] = canonical_digest(initial_state)
        bundle["disabled_export"]["implicit_live_step_records"][0]["previous_state_digest"] = initial_state[
            "state_digest"
        ]
        _refresh_branch_manifest(bundle, "disabled")

        result = evaluate_five_phase_causal_completion(bundle)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["paired_baseline_status"])

    def test_completion_rejects_different_canonical_basis_identity(self) -> None:
        bundle = self._bundle()
        bundle["disabled_export"]["implicit_basis_records"][0]["phase"] += 0.125
        _refresh_branch_manifest(bundle, "disabled")

        result = evaluate_five_phase_causal_completion(bundle)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["paired_baseline_status"])

    def test_completion_rejects_different_canonical_interaction_transcript(self) -> None:
        bundle = self._bundle()
        transcript = bundle["disabled_export"]["implicit_interaction_transcript"]
        transcript[0]["request"]["advance_after_accept"] = True
        _refresh_branch_manifest(bundle, "disabled")

        result = evaluate_five_phase_causal_completion(bundle)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["paired_baseline_status"])

    def test_completion_rejects_different_canonical_step_schedule(self) -> None:
        bundle = self._bundle()
        step = next(
            record
            for record in bundle["disabled_export"]["implicit_live_step_records"]
            if record["applied_command_ids"]
        )
        step["applied_command_ids"].append("forged-command")
        _refresh_branch_manifest(bundle, "disabled")

        result = evaluate_five_phase_causal_completion(bundle)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["paired_baseline_status"])

    def test_completion_rejects_schedule_not_matching_canonical_transcript(self) -> None:
        bundle = self._bundle()
        bundle["perturbation_schedule"]["events"][0]["tool"] = "implicit_local_dampen"

        result = evaluate_five_phase_causal_completion(bundle)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["paired_baseline_status"])

    def test_completion_rejects_manifest_not_bound_to_canonical_export(self) -> None:
        bundle = self._bundle()
        bundle["disabled_export"]["session"]["observed_structure_count"] += 1

        result = evaluate_five_phase_causal_completion(bundle)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["paired_baseline_status"])

    def test_completion_rejects_identical_enabled_disabled_outputs(self) -> None:
        bundle = self._bundle()
        bundle["enabled_export"] = copy.deepcopy(bundle["disabled_export"])
        result = evaluate_five_phase_causal_completion(bundle)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["feedback_application_status"])
        self.assertEqual("failed", result["readback_divergence_status"])

    def test_completion_rejects_feedback_leak_into_disabled_branch(self) -> None:
        bundle = self._bundle()
        application = bundle["disabled_export"]["five_phase_feedback_applications"][-1]
        application["feedback_applied"] = True
        application["applied_feedback_projection"] = {"basis-x": {"density": 0.1}}
        step = bundle["disabled_export"]["implicit_live_step_records"][-1]
        step["five_phase_feedback_input_projection"] = {"basis-x": {"density": 0.1}}
        result = evaluate_five_phase_causal_completion(bundle)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["feedback_application_status"])

    def test_completion_rejects_missing_effect_probe_records(self) -> None:
        bundle = self._bundle()
        bundle["feedback_effect_probes"] = []
        result = evaluate_five_phase_causal_completion(bundle)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["lineage_status"])

    def test_completion_rejects_forged_tick_metrics(self) -> None:
        bundle = self._bundle()
        bundle["tick_metrics"][0]["readback_divergence_l2"] = 999.0
        result = evaluate_five_phase_causal_completion(bundle)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["lineage_status"])

    def test_completion_rejects_forged_quality_comparison(self) -> None:
        bundle = self._bundle()
        bundle["comparison"]["pattern_stability_delta"] = 999.0
        result = evaluate_five_phase_causal_completion(bundle)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["comparison_status"])

    def test_completion_rejects_no_quality_improvement(self) -> None:
        bundle = self._bundle()
        enabled_residual = bundle["enabled_manifest"]["residual_distance_mean"]
        enabled_stability = bundle["enabled_manifest"]["pattern_stability_mean"]
        bundle["disabled_manifest"]["residual_distance_mean"] = enabled_residual
        bundle["disabled_manifest"]["pattern_stability_mean"] = enabled_stability
        bundle["comparison"]["residual_distance_delta"] = 0.0
        bundle["comparison"]["pattern_stability_delta"] = 0.0
        for application in bundle["enabled_export"]["five_phase_feedback_applications"]:
            if application.get("feedback_applied") is not True:
                continue
            application["candidate_response_measurements"] = copy.deepcopy(
                application["baseline_response_measurements"]
            )
        result = evaluate_five_phase_causal_completion(bundle)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["quality_improvement_status"])

    def test_quality_gate_ignores_orphan_feedback_application_summary(self) -> None:
        bundle = self._bundle()
        enabled_residual = bundle["enabled_manifest"]["residual_distance_mean"]
        enabled_stability = bundle["enabled_manifest"]["pattern_stability_mean"]
        bundle["disabled_manifest"]["residual_distance_mean"] = enabled_residual
        bundle["disabled_manifest"]["pattern_stability_mean"] = enabled_stability
        bundle["comparison"]["residual_distance_delta"] = 0.0
        bundle["comparison"]["pattern_stability_delta"] = 0.0
        orphan = None
        for application in bundle["enabled_export"]["five_phase_feedback_applications"]:
            if application.get("feedback_applied") is not True:
                continue
            orphan = copy.deepcopy(application)
            application["candidate_response_measurements"] = copy.deepcopy(
                application["baseline_response_measurements"]
            )
        self.assertIsNotNone(orphan)
        orphan["application_record_id"] = "forged-orphan-quality-application"
        bundle["enabled_export"]["five_phase_feedback_applications"].append(orphan)

        result = evaluate_five_phase_causal_completion(bundle)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["quality_improvement_status"])

    def test_completion_rejects_forged_transition_energy_ledger(self) -> None:
        bundle = self._bundle()
        step = next(
            record
            for record in bundle["enabled_export"]["implicit_live_step_records"]
            if record["energy_ledgers"]
        )
        step["energy_ledgers"][0]["i_user"] += 0.125

        result = evaluate_five_phase_causal_completion(bundle)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["energy_budget_status"])

    def test_completion_fails_closed_on_malformed_tick_metrics(self) -> None:
        bundle = self._bundle()
        bundle["tick_metrics"] = ["not-a-record"]
        result = evaluate_five_phase_causal_completion(bundle)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["lineage_status"])
        self.assertIn("read-back failed", " ".join(result["reasons"]))

    def test_completion_rejects_wrong_baseline_manifest(self) -> None:
        bundle = self._bundle()
        bundle["disabled_manifest"]["initial_snapshot_digest"] = "sha256:wrong"
        result = evaluate_five_phase_causal_completion(bundle)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["paired_baseline_status"])

    def test_completion_rejects_missing_perturbation_schedule(self) -> None:
        bundle = self._bundle()
        bundle["perturbation_schedule"]["events"] = []
        result = evaluate_five_phase_causal_completion(bundle)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["paired_baseline_status"])

    def test_completion_rejects_artifact_budget_overrun(self) -> None:
        bundle = self._bundle()
        bundle["artifact_budget_bytes"] = 1
        result = evaluate_five_phase_causal_completion(bundle)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["artifact_budget_status"])

    def test_completion_rejects_forged_artifact_byte_accounting(self) -> None:
        bundle = self._bundle()
        bundle["artifact_bytes_total"] = int(bundle["artifact_bytes_total"]) + 1
        result = evaluate_five_phase_causal_completion(bundle)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["artifact_budget_status"])

    def test_completion_rejects_missing_artifact_readback_paths(self) -> None:
        bundle = self._bundle()
        bundle["artifact_paths"] = {}
        bundle["artifact_bytes_by_file"] = {}

        result = evaluate_five_phase_causal_completion(bundle)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["artifact_budget_status"])

    def test_completion_rejects_viewer_shortcut(self) -> None:
        bundle = self._bundle()
        bundle["enabled_export"]["five_phase_live_steps"][0]["canvas_pixels"] = [[0, 0, 0]]
        result = evaluate_five_phase_causal_completion(bundle)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["viewer_non_authority_status"])


if __name__ == "__main__":
    unittest.main()
