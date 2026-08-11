import copy
import unittest

from world_engine.five_phase_live_completion import evaluate_five_phase_live_completion
from world_engine.implicit_live_session import ImplicitFieldSession


def make_export(*, camera_only_frame: bool = False):
    session = ImplicitFieldSession.from_source_package(
        source_package_name="source-a",
        source_package_digest="digest-a",
        case_type="implicit_full_scene",
        run_id="five-phase-live-completion",
        image_shape=[12, 8],
        samples_per_ray=6,
    )
    session.advance(2)
    if camera_only_frame:
        session.move_camera(
            {
                "schema": "implicit_camera_move_request",
                "request_id": "five-phase-live-completion-camera",
                "observer_id": "observer::implicit-pinhole",
                "source_projection_frame_id": session.projection_frames[-1].frame_id,
                "source_frame_tick": session.current_tick,
                "action": "strafe_left",
                "step_world": 0.35,
                "yaw_degrees": 8.0,
            }
        )
    return session.export_artifacts()


class FivePhaseLiveCompletionTests(unittest.TestCase):
    def test_live_completion_passes_exported_session(self):
        result = evaluate_five_phase_live_completion(make_export())
        self.assertEqual("passed", result["overall_status"])
        self.assertEqual("passed", result["frame_payload_status"])
        self.assertEqual("passed", result["feedback_runtime_binding_status"])

    def test_live_completion_accepts_camera_frame_reusing_latest_causal_step(self):
        exported = make_export(camera_only_frame=True)

        result = evaluate_five_phase_live_completion(exported)

        self.assertEqual("passed", result["overall_status"])
        self.assertEqual(len(exported["implicit_field_states"]), len(exported["five_phase_live_steps"]))
        self.assertGreater(len(exported["projection_frames"]), len(exported["five_phase_live_steps"]))

    def test_live_completion_rejects_second_causal_step_for_same_canonical_state(self):
        exported = make_export()
        duplicate = copy.deepcopy(exported["five_phase_live_steps"][-1])
        original_id = duplicate["live_step_id"]
        duplicate["live_step_id"] = original_id + "::forged-camera-step"
        duplicate["source_record_ids"] = [
            duplicate["live_step_id"] if value == original_id else value
            for value in duplicate["source_record_ids"]
        ]
        exported["five_phase_live_steps"].append(duplicate)

        result = evaluate_five_phase_live_completion(exported)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["authority_lineage_status"])

    def test_live_completion_rejects_v2_agent_trace_from_another_causal_step(self):
        exported = make_export()
        agent = exported["five_phase_agent_states"][-1]
        forged_trace_id = exported["five_phase_traces"][0]["record_id"]
        agent["trace_id"] = forged_trace_id
        agent["source_record_ids"].append(forged_trace_id)

        result = evaluate_five_phase_live_completion(exported)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["authority_lineage_status"])

    def test_live_completion_rejects_forged_pattern_stability_even_with_matching_agent(self):
        exported = make_export()
        owner = exported["five_phase_live_steps"][-1]
        pattern_id = owner["pattern_ids"][0]
        pattern = next(
            record for record in exported["five_phase_patterns"] if record["record_id"] == pattern_id
        )
        pattern["stability_score"] = 0.123
        agent = next(
            record
            for record in exported["five_phase_agent_states"]
            if record["pattern_id"] == pattern_id
        )
        agent["response_stability"] = 0.123

        result = evaluate_five_phase_live_completion(exported)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["authority_lineage_status"])
        self.assertIn("stability_score", " ".join(result["reasons"]))

    def test_live_completion_rejects_v2_feedback_agent_from_another_causal_step(self):
        exported = make_export()
        feedback = exported["five_phase_feedback_records"][-1]
        forged_agent_id = exported["five_phase_agent_states"][0]["record_id"]
        feedback["agent_state_id"] = forged_agent_id
        feedback["source_record_ids"].append(forged_agent_id)

        result = evaluate_five_phase_live_completion(exported)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["authority_lineage_status"])

    def test_live_completion_rejects_forged_feedback_response_measurement(self):
        exported = make_export()
        application = next(
            record
            for record in exported["five_phase_feedback_applications"]
            if record["candidate_response_measurements"]
        )
        application["candidate_response_measurements"][0]["absolute_error"] += 0.125

        result = evaluate_five_phase_live_completion(exported)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["feedback_runtime_binding_status"])

    def test_live_completion_rejects_orphan_feedback_application(self):
        exported = make_export()
        orphan = copy.deepcopy(exported["five_phase_feedback_applications"][-1])
        orphan["application_record_id"] += "::orphan"
        exported["five_phase_feedback_applications"].append(orphan)

        result = evaluate_five_phase_live_completion(exported)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["feedback_runtime_binding_status"])

    def test_live_completion_rejects_duplicate_feedback_application_id(self):
        exported = make_export()
        exported["five_phase_feedback_applications"].append(
            copy.deepcopy(exported["five_phase_feedback_applications"][-1])
        )

        result = evaluate_five_phase_live_completion(exported)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["feedback_runtime_binding_status"])

    def test_live_completion_rejects_forged_energy_ledger_term(self):
        exported = make_export()
        step = next(record for record in exported["implicit_live_step_records"] if record["energy_ledgers"])
        step["energy_ledgers"][0]["i_user"] += 0.125

        result = evaluate_five_phase_live_completion(exported)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["energy_ledger_status"])

    def test_live_completion_rejects_duplicate_canonical_implicit_state_identity(self):
        exported = make_export()
        exported["implicit_field_states"].append(
            copy.deepcopy(exported["implicit_field_states"][0])
        )
        exported["session"]["implicit_field_state_count"] = len(
            exported["implicit_field_states"]
        )

        result = evaluate_five_phase_live_completion(exported)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["authority_lineage_status"])

    def test_live_completion_rejects_forged_pattern_intrinsic_geometry(self):
        exported = make_export()
        pattern = next(
            record
            for record in reversed(exported["five_phase_patterns"])
            if record["payload"].get("previous_pattern_record_id")
        )
        bounds = list(pattern["support_bounds_grid"])
        bounds[0] = min(bounds[2], bounds[0] + 1)
        pattern["support_bounds_grid"] = bounds

        result = evaluate_five_phase_live_completion(exported)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["authority_lineage_status"])

    def test_live_completion_rejects_missing_frame_summary(self):
        exported = make_export()
        exported["projection_frames"][-1].payload.pop("five_phase_live_summary", None)
        result = evaluate_five_phase_live_completion(exported)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["frame_payload_status"])

    def test_live_completion_rejects_forged_projection_frame_source_state_digest(self):
        exported = make_export()
        exported["projection_frames"][-1].payload["timeline_semantics"][
            "source_world_state_digest"
        ] = "sha256:forged"

        result = evaluate_five_phase_live_completion(exported)

        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["frame_payload_status"])

    def test_live_completion_rejects_feedback_projection_without_source_step(self):
        exported = make_export()
        exported["implicit_live_step_records"][-1]["five_phase_live_step_ids"] = []
        result = evaluate_five_phase_live_completion(exported)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["feedback_runtime_binding_status"])

    def test_live_completion_rejects_viewer_shortcut(self):
        exported = make_export()
        exported["five_phase_live_steps"][0]["canvas_pixels"] = [[0, 0, 0]]
        result = evaluate_five_phase_live_completion(exported)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["authority_lineage_status"])

    def test_live_completion_rejects_stale_summary_tick(self):
        exported = make_export()
        exported["projection_frames"][-1].payload["five_phase_live_summary"]["tick"] = -1
        result = evaluate_five_phase_live_completion(exported)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["frame_payload_status"])

    def test_live_completion_rejects_live_step_tick_mismatch(self):
        exported = make_export()
        live_step_id = exported["projection_frames"][-1].payload["five_phase_live_summary"]["live_step_id"]
        for step in exported["five_phase_live_steps"]:
            if step["live_step_id"] == live_step_id:
                step["tick"] = -1
                break
        result = evaluate_five_phase_live_completion(exported)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["frame_payload_status"])

    def test_live_completion_rejects_missing_projection_frame_for_live_step(self):
        exported = make_export()
        exported["projection_frames"] = exported["projection_frames"][:-1]
        result = evaluate_five_phase_live_completion(exported)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["frame_payload_status"])

    def test_live_completion_rejects_frame_missing_summary_source_lineage(self):
        exported = make_export()
        frame = exported["projection_frames"][-1]
        summary = frame.payload["five_phase_live_summary"]
        frame.source_record_ids = [
            source_id
            for source_id in frame.source_record_ids
            if source_id not in {summary["live_step_id"], summary["phase_field_id"]}
        ]
        result = evaluate_five_phase_live_completion(exported)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["frame_payload_status"])

    def test_live_completion_rejects_authority_bridge(self):
        exported = make_export()
        exported["five_phase_live_bridges"][0]["is_authority_state"] = True
        result = evaluate_five_phase_live_completion(exported)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["authority_lineage_status"])

    def test_live_completion_fails_closed_on_malformed_records(self):
        exported = make_export()
        exported["five_phase_live_steps"] = ["not-a-record"]
        result = evaluate_five_phase_live_completion(exported)
        self.assertEqual("failed", result["overall_status"])
        self.assertIn("read-back failed", " ".join(result["reasons"]))

    def test_live_completion_rejects_missing_bridge_source(self):
        exported = make_export()
        exported["five_phase_live_steps"][0]["bridge_record_id"] = "missing"
        result = evaluate_five_phase_live_completion(exported)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["authority_lineage_status"])

    def test_live_completion_rejects_missing_feedback_artifact_family(self):
        exported = make_export()
        exported["five_phase_feedback_records"] = []
        result = evaluate_five_phase_live_completion(exported)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["authority_lineage_status"])

    def test_live_completion_rejects_empty_feedback_projection(self):
        exported = make_export()
        exported["implicit_live_step_records"][-1]["five_phase_feedback_input_projection"] = {}
        result = evaluate_five_phase_live_completion(exported)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["feedback_runtime_binding_status"])

    def test_live_completion_rejects_empty_live_step_feedback_projection(self):
        exported = make_export()
        exported["five_phase_live_steps"][-1]["feedback_input_projection"] = {}
        result = evaluate_five_phase_live_completion(exported)
        self.assertEqual("failed", result["overall_status"])
        self.assertEqual("failed", result["authority_lineage_status"])


if __name__ == "__main__":
    unittest.main()
