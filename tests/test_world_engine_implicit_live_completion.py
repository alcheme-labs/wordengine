import copy
import unittest

from world_engine.completion import (
    evaluate_implicit_3d_live_interaction_completion,
    implicit_live_energy_ledger_failures,
)
from world_engine.implicit_live_session import ImplicitFieldSession


def live_artifacts():
    session = ImplicitFieldSession.from_source_package(
        source_package_name="source-a",
        source_package_digest="digest-a",
        case_type="implicit_full_scene",
        run_id="test-live-completion",
        image_shape=[12, 8],
        samples_per_ray=6,
    )
    session.advance(1)
    source_frame = session.projection_frames[-1]
    session.apply_interaction(
        {
            "schema": "implicit_interaction_request",
            "request_id": "viewer-1",
            "tool": "implicit_local_excite",
            "observer_id": "observer::implicit-pinhole",
            "source_frame_tick": source_frame.tick,
            "source_projection_frame_id": source_frame.frame_id,
            "source_state_id": session.current_state["implicit_field_state_id"],
            "source_ray_sample_record_id": source_frame.payload["implicit_ray_sample_record"]["ray_sample_record_id"],
            "source_image_xy": [0.5, 0.5],
            "radius_world": 1.0,
            "amplitude": 0.35,
            "duration_ticks": 2,
            "advance_after_accept": True,
            "advance_ticks": 2,
        }
    )
    source_frame = session.projection_frames[-1]
    session.apply_interaction(
        {
            "schema": "implicit_interaction_request",
            "request_id": "viewer-refine",
            "tool": "implicit_refine_probe",
            "observer_id": "observer::implicit-pinhole",
            "source_frame_tick": source_frame.tick,
            "source_projection_frame_id": source_frame.frame_id,
            "source_state_id": session.current_state["implicit_field_state_id"],
            "source_ray_sample_record_id": source_frame.payload["implicit_ray_sample_record"]["ray_sample_record_id"],
            "source_image_xy": [0.5, 0.5],
            "radius_world": 1.0,
            "amplitude": 0.25,
            "duration_ticks": 1,
            "advance_after_accept": True,
            "advance_ticks": 1,
        }
    )
    return session.export_artifacts()


def zero_amplitude_scoped_artifacts():
    session = ImplicitFieldSession.from_source_package(
        source_package_name="source-a",
        source_package_digest="digest-a",
        case_type="implicit_full_scene",
        run_id="test-zero-amplitude-energy-scope-completion",
        image_shape=[12, 8],
        samples_per_ray=6,
        five_phase_feedback_enabled=False,
    )
    source_frame = session.projection_frames[-1]
    session.apply_interaction(
        {
            "schema": "implicit_interaction_request",
            "request_id": "zero-amplitude-scope",
            "tool": "implicit_local_excite",
            "observer_id": "observer::implicit-pinhole",
            "source_frame_tick": source_frame.tick,
            "source_projection_frame_id": source_frame.frame_id,
            "source_state_id": session.current_state["implicit_field_state_id"],
            "source_ray_sample_record_id": source_frame.payload["implicit_ray_sample_record"][
                "ray_sample_record_id"
            ],
            "source_image_xy": [0.5, 0.5],
            "radius_world": 1.0,
            "amplitude": 0.0,
            "duration_ticks": 1.5,
            "advance_after_accept": True,
            "advance_ticks": 11,
        }
    )
    return session.export_artifacts()


class Implicit3DLiveCompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.zero_scope_baseline = zero_amplitude_scoped_artifacts()

    def test_completion_accepts_live_implicit_interaction_artifacts(self):
        report = evaluate_implicit_3d_live_interaction_completion(live_artifacts())
        self.assertEqual("passed", report.overall_status)
        check_names = {check.name for check in report.checks}
        self.assertIn("implicit_live_runtime_mode_status", check_names)
        self.assertIn("implicit_live_step_chain_status", check_names)
        self.assertIn("implicit_live_interaction_audit_status", check_names)
        self.assertIn("implicit_live_visible_delta_status", check_names)

    def test_completion_fails_wrong_runtime_mode_or_broken_step_chain(self):
        data = live_artifacts()
        data["session"]["runtime_mode"] = "interactive-field"
        self.assertEqual("failed", evaluate_implicit_3d_live_interaction_completion(data).overall_status)

        broken = live_artifacts()
        broken["implicit_live_step_records"][1]["previous_state_id"] = "state::missing"
        self.assertEqual("failed", evaluate_implicit_3d_live_interaction_completion(broken).overall_status)

    def test_completion_rejects_duplicate_canonical_state_identity(self):
        data = live_artifacts()
        data["implicit_field_states"].append(copy.deepcopy(data["implicit_field_states"][0]))
        data["session"]["implicit_field_state_count"] = len(data["implicit_field_states"])

        report = evaluate_implicit_3d_live_interaction_completion(data)

        self.assertEqual("failed", report.overall_status)
        self.assertEqual(
            "failed",
            next(
                check.status
                for check in report.checks
                if check.name == "implicit_live_step_chain_status"
            ),
        )

    def test_completion_fails_broken_interaction_or_refinement_lineage(self):
        data = live_artifacts()
        data["implicit_interaction_audits"][0]["resulting_projection_frame_ids"] = []
        self.assertEqual("failed", evaluate_implicit_3d_live_interaction_completion(data).overall_status)

        missing_patch = live_artifacts()
        refine_audit = next(audit for audit in missing_patch["implicit_interaction_audits"] if audit["tool"] == "implicit_refine_probe")
        refine_audit["refinement_patch_id"] = None
        self.assertEqual("failed", evaluate_implicit_3d_live_interaction_completion(missing_patch).overall_status)

    def test_completion_rejects_duplicate_interaction_audit_identity(self):
        data = live_artifacts()
        data["implicit_interaction_audits"].append(
            copy.deepcopy(data["implicit_interaction_audits"][0])
        )
        data["session"]["interaction_audit_count"] = len(
            data["implicit_interaction_audits"]
        )

        report = evaluate_implicit_3d_live_interaction_completion(data)

        self.assertEqual("failed", report.overall_status)
        self.assertEqual(
            "failed",
            next(
                check.status
                for check in report.checks
                if check.name == "implicit_live_interaction_audit_status"
            ),
        )

    def test_completion_fails_no_visible_or_state_delta_after_interaction(self):
        data = live_artifacts()
        first_image_digest = data["implicit_spectral_image_planes"][0]["image_digest"]
        for image in data["implicit_spectral_image_planes"]:
            image["image_digest"] = first_image_digest
        self.assertEqual("failed", evaluate_implicit_3d_live_interaction_completion(data).overall_status)

        state_static = live_artifacts()
        first_state_digest = state_static["implicit_field_states"][0]["state_digest"]
        for state in state_static["implicit_field_states"]:
            state["state_digest"] = first_state_digest
        self.assertEqual("failed", evaluate_implicit_3d_live_interaction_completion(state_static).overall_status)

    def test_completion_fails_viewer_authority_leak(self):
        data = live_artifacts()
        frame = copy.deepcopy(data["projection_frames"][0])
        frame.payload["viewer_shape"] = "cube"
        data["projection_frames"][0] = frame
        self.assertEqual("failed", evaluate_implicit_3d_live_interaction_completion(data).overall_status)

    def test_completion_rejects_forged_projection_frame_source_state_digest(self):
        data = live_artifacts()
        data["projection_frames"][-1].payload["timeline_semantics"][
            "source_world_state_digest"
        ] = "sha256:forged"

        report = evaluate_implicit_3d_live_interaction_completion(data)

        self.assertEqual("failed", report.overall_status)
        self.assertEqual(
            "failed",
            next(
                check.status
                for check in report.checks
                if check.name == "implicit_live_projection_runtime_status"
            ),
        )

    def test_completion_rejects_forged_energy_ledger_term(self):
        data = live_artifacts()
        step = next(record for record in data["implicit_live_step_records"] if record["energy_ledgers"])
        step["energy_ledgers"][0]["i_user"] += 0.125

        report = evaluate_implicit_3d_live_interaction_completion(data)

        self.assertEqual("failed", report.overall_status)
        self.assertEqual(
            "failed",
            next(check.status for check in report.checks if check.name == "implicit_live_energy_ledger_status"),
        )

    def test_completion_rejects_shifted_or_mismatched_control_application_lineage(self):
        shifted = live_artifacts()
        audit = next(
            record
            for record in shifted["implicit_interaction_audits"]
            if record["tool"] == "implicit_local_excite"
        )
        self.assertEqual(2, len(audit["applications"]))
        audit["applications"][0]["tick"] = audit["applications"][1]["tick"]

        shifted_report = evaluate_implicit_3d_live_interaction_completion(shifted)

        self.assertEqual("failed", shifted_report.overall_status)
        self.assertEqual(
            "failed",
            next(
                check.status
                for check in shifted_report.checks
                if check.name == "implicit_live_energy_ledger_status"
            ),
        )

        mismatched = live_artifacts()
        audit = next(
            record
            for record in mismatched["implicit_interaction_audits"]
            if record["tool"] == "implicit_local_excite"
        )
        application_tick = int(audit["applications"][0]["tick"])
        step = next(
            record
            for record in mismatched["implicit_live_step_records"]
            if int(record["tick"]) == application_tick
        )
        lineage = next(
            record
            for record in step["pending_control_lineage"]
            if record["command_id"] == audit["command_id"]
        )
        lineage["schedule_index"] = 1

        mismatched_report = evaluate_implicit_3d_live_interaction_completion(mismatched)

        self.assertEqual("failed", mismatched_report.overall_status)
        self.assertEqual(
            "failed",
            next(
                check.status
                for check in mismatched_report.checks
                if check.name == "implicit_live_energy_ledger_status"
            ),
        )

    def test_zero_amplitude_scope_is_required_through_exact_relaxation_boundary(self):
        data = copy.deepcopy(self.zero_scope_baseline)
        audit = data["implicit_interaction_audits"][0]
        scope_id = f"implicit-energy-scope::{audit['command_id']}"
        activation_tick = int(audit["start_tick"])
        expiry_tick = activation_tick + len(audit["schedule_weights"]) - 1 + 8
        scopes_by_tick = {
            int(step["tick"]): {ledger["scope_id"] for ledger in step["energy_ledgers"]}
            for step in data["implicit_live_step_records"]
        }

        self.assertEqual(0.0, audit["amplitude_magnitude"])
        self.assertEqual(
            list(range(activation_tick, expiry_tick + 1)),
            [
                tick
                for tick, scope_ids in sorted(scopes_by_tick.items())
                if scope_id in scope_ids
            ],
        )
        self.assertNotIn(scope_id, scopes_by_tick[expiry_tick + 1])
        self.assertEqual(
            "passed",
            evaluate_implicit_3d_live_interaction_completion(data).overall_status,
        )

    def test_completion_rejects_missing_and_unowned_local_scope_membership(self):
        baseline = copy.deepcopy(self.zero_scope_baseline)
        audit = baseline["implicit_interaction_audits"][0]
        scope_id = f"implicit-energy-scope::{audit['command_id']}"
        activation_step = next(
            step
            for step in baseline["implicit_live_step_records"]
            if int(step["tick"]) == int(audit["start_tick"])
        )

        missing = copy.deepcopy(baseline)
        missing_step = next(
            step for step in missing["implicit_live_step_records"] if step["step_id"] == activation_step["step_id"]
        )
        missing_step["energy_ledgers"] = [
            ledger for ledger in missing_step["energy_ledgers"] if ledger["scope_id"] != scope_id
        ]
        missing_failure = next(
            failure
            for failure in implicit_live_energy_ledger_failures(missing)
            if failure["reason"] == "energy_ledger_scope_set_mismatch"
        )
        self.assertIn(scope_id, missing_failure["missing_scope_ids"])

        unowned = copy.deepcopy(baseline)
        unowned_step = next(
            step for step in unowned["implicit_live_step_records"] if step["step_id"] == activation_step["step_id"]
        )
        local_ledger = next(
            ledger for ledger in unowned_step["energy_ledgers"] if ledger["scope_id"] == scope_id
        )
        local_ledger["scope_id"] = "implicit-energy-scope::forged-unowned"
        unowned_failure = next(
            failure
            for failure in implicit_live_energy_ledger_failures(unowned)
            if failure["reason"] == "energy_ledger_scope_set_mismatch"
        )
        self.assertIn(scope_id, unowned_failure["missing_scope_ids"])
        self.assertIn(
            "implicit-energy-scope::forged-unowned",
            unowned_failure["extra_scope_ids"],
        )

    def test_completion_rejects_expired_extra_scope_and_wrong_kappa(self):
        baseline = copy.deepcopy(self.zero_scope_baseline)
        audit = baseline["implicit_interaction_audits"][0]
        scope_id = f"implicit-energy-scope::{audit['command_id']}"
        expiry_tick = int(audit["start_tick"]) + len(audit["schedule_weights"]) - 1 + 8
        source_step = next(
            step
            for step in baseline["implicit_live_step_records"]
            if int(step["tick"]) == expiry_tick
        )
        expired = copy.deepcopy(baseline)
        expired_step = next(
            step
            for step in expired["implicit_live_step_records"]
            if int(step["tick"]) == expiry_tick + 1
        )
        expired_step["energy_ledgers"].append(
            copy.deepcopy(
                next(
                    ledger
                    for ledger in source_step["energy_ledgers"]
                    if ledger["scope_id"] == scope_id
                )
            )
        )
        expired_failure = next(
            failure
            for failure in implicit_live_energy_ledger_failures(expired)
            if failure["reason"] == "energy_ledger_scope_set_mismatch"
        )
        self.assertIn(scope_id, expired_failure["extra_scope_ids"])

        wrong_kappa = copy.deepcopy(baseline)
        activation_step = next(
            step
            for step in wrong_kappa["implicit_live_step_records"]
            if int(step["tick"]) == int(audit["start_tick"])
        )
        local_ledger = next(
            ledger for ledger in activation_step["energy_ledgers"] if ledger["scope_id"] == scope_id
        )
        changed_basis_id = next(iter(local_ledger["kappa"]))
        local_ledger["kappa"][changed_basis_id] += 0.125
        reasons = {
            failure["reason"]
            for failure in implicit_live_energy_ledger_failures(wrong_kappa)
        }
        self.assertIn("local_scope_kappa_lineage_mismatch", reasons)

    def test_feedback_scope_uses_exact_v2_application_window_and_target(self):
        baseline = copy.deepcopy(self.zero_scope_baseline)
        application = next(
            record
            for record in baseline["five_phase_feedback_applications"]
            if record["eligibility_reason"] == "feedback_disabled_baseline"
            and record["feedback_record_ids"]
        )
        feedback_id = application["feedback_record_ids"][0]
        feedback = next(
            record
            for record in baseline["five_phase_feedback_records"]
            if record["record_id"] == feedback_id
        )
        scope_id = f"implicit-feedback-energy-scope::{feedback_id}"
        activation_tick = int(application["tick"])
        expiry_tick = activation_tick + 8
        scopes_by_tick = {
            int(step["tick"]): {ledger["scope_id"] for ledger in step["energy_ledgers"]}
            for step in baseline["implicit_live_step_records"]
        }

        self.assertEqual("five_phase_feedback_application_record_v2", application["schema"])
        self.assertEqual("five_phase_feedback_v2", feedback["schema"])
        self.assertTrue(
            all(
                scope_id in scopes_by_tick[tick]
                for tick in range(activation_tick, expiry_tick + 1)
            )
        )
        self.assertNotIn(scope_id, scopes_by_tick[expiry_tick + 1])

        missing = copy.deepcopy(baseline)
        activation_step = next(
            step
            for step in missing["implicit_live_step_records"]
            if int(step["tick"]) == activation_tick
        )
        activation_step["energy_ledgers"] = [
            ledger
            for ledger in activation_step["energy_ledgers"]
            if ledger["scope_id"] != scope_id
        ]
        mismatch = next(
            failure
            for failure in implicit_live_energy_ledger_failures(missing)
            if failure["reason"] == "energy_ledger_scope_set_mismatch"
        )
        self.assertIn(scope_id, mismatch["missing_scope_ids"])


if __name__ == "__main__":
    unittest.main()
