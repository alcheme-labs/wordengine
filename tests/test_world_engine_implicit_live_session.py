import copy
import threading
import unittest
from unittest.mock import patch

import world_engine.implicit_live_session as implicit_live_session_module
from world_engine.five_phase import FivePhaseAgentStateRecord, FivePhasePatternRecord
from world_engine.five_phase_runtime import build_agent_repair_feedback
from world_engine.implicit_live_session import ImplicitFieldSession


def make_session():
    return ImplicitFieldSession.from_source_package(
        source_package_name="source-a",
        source_package_digest="digest-a",
        case_type="implicit_full_scene",
        run_id="test-live-session",
        image_shape=[12, 8],
        samples_per_ray=6,
    )


def request(session=None, **overrides):
    payload = {
        "schema": "implicit_interaction_request",
        "request_id": "viewer-1",
        "tool": "implicit_local_excite",
        "observer_id": "observer::implicit-pinhole",
        "source_frame_tick": 1,
        "source_image_xy": [0.5, 0.5],
        "radius_world": 1.0,
        "amplitude": 0.35,
        "duration_ticks": 2,
        "advance_after_accept": True,
        "advance_ticks": 2,
    }
    if session is not None:
        frame = session.projection_frames[-1]
        payload.update(
            {
                "source_projection_frame_id": frame.frame_id,
                "source_frame_tick": frame.tick,
                "source_state_id": session.current_state["implicit_field_state_id"],
                "source_ray_sample_record_id": frame.payload["implicit_ray_sample_record"]["ray_sample_record_id"],
            }
        )
    payload.update(overrides)
    return payload


def snapshot_with_stale_feedback_predecessor(session):
    forged = copy.deepcopy(session.to_snapshot())
    live_steps = forged["five_phase_live_steps"]
    owner_index = next(
        index
        for index, step in enumerate(live_steps)
        if index >= 2 and step["feedback_record_ids"]
    )
    owner = live_steps[owner_index]
    old_feedback_id = owner["feedback_record_ids"][0]
    old_feedback = next(
        record
        for record in forged["five_phase_feedback_records"]
        if record["record_id"] == old_feedback_id
    )
    pattern = FivePhasePatternRecord.from_dict(
        next(
            record
            for record in forged["five_phase_patterns"]
            if record["record_id"] == old_feedback["pattern_id"]
        )
    )
    agent = FivePhaseAgentStateRecord.from_dict(
        next(
            record
            for record in forged["five_phase_agent_states"]
            if record["record_id"] == old_feedback["agent_state_id"]
        )
    )
    stale_predecessor_id = live_steps[owner_index - 2]["live_step_id"]
    rebuilt = build_agent_repair_feedback(
        agent,
        pattern,
        tick=old_feedback["tick"],
        target_basis_id=old_feedback["target_basis_id"],
        signed_error=old_feedback["signed_error"],
        sensitivity=old_feedback["sensitivity"],
        eta=old_feedback["eta"],
        gain=old_feedback["gain"],
        candidate_projection=old_feedback["candidate_projection"],
        predecessor_causal_step_id=stale_predecessor_id,
    )
    if rebuilt is None:
        raise AssertionError("expected a rebuilt stale Feedback candidate")
    new_feedback_id = rebuilt.record_id
    forged["five_phase_feedback_records"] = [
        rebuilt.to_dict() if record["record_id"] == old_feedback_id else record
        for record in forged["five_phase_feedback_records"]
    ]
    owner["feedback_record_ids"] = [
        new_feedback_id if value == old_feedback_id else value
        for value in owner["feedback_record_ids"]
    ]
    owner["source_record_ids"] = [
        new_feedback_id if value == old_feedback_id else value
        for value in owner["source_record_ids"]
    ]
    for application in forged["five_phase_feedback_applications"]:
        if owner["live_step_id"] not in application["five_phase_live_step_ids"]:
            continue
        application["feedback_record_ids"] = [
            new_feedback_id if value == old_feedback_id else value
            for value in application["feedback_record_ids"]
        ]
        application["source_record_ids"] = [
            new_feedback_id if value == old_feedback_id else value
            for value in application["source_record_ids"]
        ]
        for measurement in [
            *application["baseline_response_measurements"],
            *application["candidate_response_measurements"],
        ]:
            if measurement["feedback_record_id"] != old_feedback_id:
                continue
            measurement["feedback_record_id"] = new_feedback_id
            measurement["source_record_ids"] = [
                new_feedback_id if value == old_feedback_id else value
                for value in measurement["source_record_ids"]
            ]
            unsigned = {
                key: value
                for key, value in measurement.items()
                if key != "measurement_digest"
            }
            measurement["measurement_digest"] = implicit_live_session_module._canonical_digest(
                unsigned
            )
    forged["snapshot_digest"] = implicit_live_session_module._snapshot_digest(forged)
    return forged


class ImplicitLiveSessionCreationTests(unittest.TestCase):
    def test_session_manifest_and_initial_frame_are_implicit(self):
        session = make_session()
        manifest = session.manifest()
        self.assertEqual("live-implicit-3d-field", manifest["runtime_mode"])
        self.assertEqual(["observer::implicit-pinhole"], manifest["observer_ids"])
        self.assertIn("implicit_local_excite", manifest["supported_tools"])
        self.assertEqual(1, manifest["projection_frame_count"])
        frame = session.projection_frames[-1]
        self.assertEqual("implicit_3d_field_observation", frame.payload["render_mode"])
        self.assertIn("implicit_ray_sample_record", frame.payload)
        self.assertIn("implicit_spectral_image_plane", frame.payload)
        forbidden = {"viewer_shape", "css_color", "canvas_pixels", "mesh", "object_asset_id"}
        self.assertTrue(forbidden.isdisjoint(str(frame.to_dict()).split()))

    def test_session_does_not_use_old_interactive_session(self):
        session = make_session()
        self.assertNotIn("InteractiveFieldSession", type(session).__mro__[0].__name__)


class ImplicitLiveSessionFivePhaseTests(unittest.TestCase):
    def test_initial_frame_has_five_phase_live_summary(self):
        session = make_session()
        manifest = session.manifest()
        self.assertGreaterEqual(manifest["five_phase_live_step_count"], 1)
        frame = session.projection_frames[-1]
        summary = frame.payload["five_phase_live_summary"]
        self.assertEqual("five_phase_live_summary_v1", summary["schema"])
        self.assertEqual(frame.tick, summary["tick"])
        self.assertIn("aggregate_phase", summary)
        self.assertIn(summary["live_step_id"], summary["source_record_ids"])
        self.assertIn(summary["phase_field_id"], summary["source_record_ids"])

    def test_advance_appends_five_phase_live_artifacts_per_frame(self):
        session = make_session()
        before_count = session.manifest()["five_phase_live_step_count"]
        session.advance(2)
        after = session.manifest()
        self.assertEqual(before_count + 2, after["five_phase_live_step_count"])
        self.assertEqual(len(session.projection_frames), after["five_phase_live_step_count"])
        self.assertEqual(len(session.five_phase_live_steps), len(session.five_phase_phase_fields))
        self.assertEqual(
            "five_phase_live_summary_v1",
            session.projection_frames[-1].payload["five_phase_live_summary"]["schema"],
        )

    def test_frame_summary_exposes_bounded_energy_stability_and_feedback_readback(self):
        session = make_session()
        session.apply_interaction(
            request(session, request_id="frame-response-readback", duration_ticks=2, advance_ticks=5)
        )
        summary = session.projection_frames[-1].payload["five_phase_live_summary"]

        self.assertFalse(summary["viewer_generated"])
        self.assertTrue(summary["display_only"])
        self.assertTrue(summary["pattern_response"])
        for response in summary["pattern_response"]:
            self.assertIn("stability_score", response)
            self.assertEqual(
                "five_phase_live_response_stability_v2",
                response["stability_formula"],
            )
            self.assertIn("q_user", response)
            self.assertIn("Q_live", response)
            self.assertEqual(
                "fixed_support_kappa_density_norm_over_setpoint_v1",
                response["user_dose_normalization"],
            )
        self.assertGreaterEqual(summary["energy_response"]["ledger_count"], 2)
        self.assertTrue(
            all(
                abs(item["residual"]) <= item["residual_tolerance"]
                for item in summary["energy_response"]["ledgers"]
            )
        )
        self.assertIsNotNone(summary["feedback_application"])
        self.assertIn(
            summary["feedback_application"]["application_record_id"],
            summary["source_record_ids"],
        )


class ImplicitLiveSessionAdvanceTests(unittest.TestCase):
    def test_discrete_tick_entrypoints_reject_fractional_ticks_without_mutation(self):
        session = make_session()
        before = session.to_snapshot()

        with self.assertRaisesRegex(ValueError, "advance ticks must be an integer"):
            session.advance(1.9)
        self.assertEqual(before, session.to_snapshot())

        with self.assertRaisesRegex(ValueError, "run_step ticks must be an integer"):
            session.run_step(
                {
                    "schema": "implicit_world_run_step_request",
                    "request_id": "fractional-run-step",
                    "observer_id": "observer::implicit-pinhole",
                    "ticks": 1.9,
                    "source_projection_frame_id": session.projection_frames[-1].frame_id,
                }
            )
        self.assertEqual(before, session.to_snapshot())

    def test_advance_emits_state_steps_and_frames(self):
        session = make_session()
        original_tick = session.current_tick
        original_digest = session.image_planes[-1]["image_digest"]
        session.advance(3)
        self.assertEqual(original_tick + 3, session.current_tick)
        self.assertEqual(4, len(session.implicit_field_states))
        self.assertEqual(3, len(session.implicit_live_steps))
        self.assertEqual(4, len(session.ray_sample_records))
        self.assertEqual(4, len(session.image_planes))
        self.assertEqual(4, len(session.projection_frames))
        self.assertFalse(session.implicit_live_steps[-1]["runtime_cost_summary"]["dense_volume_used"])
        self.assertEqual(
            session.implicit_field_states[-2]["implicit_field_state_id"],
            session.implicit_live_steps[-1]["previous_state_id"],
        )
        self.assertNotEqual(original_digest, session.image_planes[-1]["image_digest"])

    def test_advance_live_step_records_five_phase_feedback_input_projection(self):
        session = make_session()
        session.advance(1)
        step = session.implicit_live_steps[-1]

        self.assertIn("five_phase_feedback_input_projection", step)
        self.assertIn("five_phase_live_step_ids", step)
        self.assertTrue(step["five_phase_live_step_ids"])
        if step["five_phase_feedback_input_projection"]:
            self.assertTrue(
                set(step["five_phase_live_step_ids"]).issubset(set(step["source_record_ids"]))
            )

    def test_camera_move_emits_frame_without_state_change(self):
        session = make_session()
        before_state_id = session.current_state["implicit_field_state_id"]
        before_state_digest = session.current_state["state_digest"]
        before_frame_count = len(session.projection_frames)
        result = session.move_camera(
            {
                "schema": "implicit_camera_move_request",
                "request_id": "camera-session-1",
                "observer_id": "observer::implicit-pinhole",
                "source_projection_frame_id": session.projection_frames[-1].frame_id,
                "source_frame_tick": session.current_tick,
                "action": "strafe_left",
                "step_world": 0.35,
                "yaw_degrees": 8.0,
            }
        )

        self.assertEqual(before_state_id, session.current_state["implicit_field_state_id"])
        self.assertEqual(before_state_digest, session.current_state["state_digest"])
        self.assertEqual(False, result["world_state_changed"])
        self.assertEqual(before_frame_count + 1, len(session.projection_frames))
        self.assertGreater(len(session.camera_move_records), 0)
        self.assertGreater(len(session.spatial_consistency_records), 0)
        self.assertGreater(len(session.observed_structure_records), 0)

    def test_camera_only_observation_creates_no_causal_artifacts_or_later_field_delta(self):
        control = make_session()
        observed = make_session()
        before_live_steps = len(observed.five_phase_live_steps)
        before_feedback = len(observed.five_phase_feedback_records)

        observed.move_camera(
            {
                "schema": "implicit_camera_move_request",
                "request_id": "camera-causal-inert-1",
                "observer_id": "observer::implicit-pinhole",
                "source_projection_frame_id": observed.projection_frames[-1].frame_id,
                "source_frame_tick": observed.current_tick,
                "action": "strafe_left",
                "step_world": 0.35,
                "yaw_degrees": 8.0,
            }
        )

        self.assertEqual(before_live_steps, len(observed.five_phase_live_steps))
        self.assertEqual(before_feedback, len(observed.five_phase_feedback_records))
        control.advance(1)
        observed.advance(1)
        self.assertEqual(
            control.current_state["basis_coefficients"],
            observed.current_state["basis_coefficients"],
        )

    def test_multi_tick_run_step_appends_one_causal_step_per_world_tick(self):
        session = make_session()
        before = len(session.five_phase_live_steps)
        session.run_step(
            {
                "schema": "implicit_world_run_step_request",
                "request_id": "multi-tick-causal-1",
                "observer_id": "observer::implicit-pinhole",
                "ticks": 3,
                "source_projection_frame_id": session.projection_frames[-1].frame_id,
            }
        )

        self.assertEqual(before + 3, len(session.five_phase_live_steps))
        self.assertEqual(
            [session.current_tick - 2, session.current_tick - 1, session.current_tick],
            [step["tick"] for step in session.five_phase_live_steps[-3:]],
        )


class ImplicitLiveSessionInteractionTests(unittest.TestCase):
    def test_interaction_advances_and_completes_audit(self):
        session = make_session()
        audit = session.apply_interaction(request(session))
        self.assertEqual("applied", audit["status"])
        self.assertEqual(3, session.current_tick)
        self.assertGreaterEqual(len(audit["resulting_projection_frame_ids"]), 1)
        self.assertEqual(audit["audit_id"], session.interaction_audits[-1]["audit_id"])
        self.assertIn("target_ray_index", audit)
        self.assertIn("target_hit_depth", audit)
        self.assertIn("target_structure_id", audit)

    def test_duplicate_or_invalid_request_does_not_mutate_session(self):
        session = make_session()
        session.apply_interaction(request(session))
        snapshot = session.to_snapshot()
        for bad in [
            request(session, request_id="viewer-1"),
            request(session, request_id="viewer-2", observer_id="observer::missing"),
            request(session, request_id="viewer-3", radius_world=0),
            request(session, request_id="viewer-4", amplitude=1.5),
            request(session, request_id="viewer-5", advance_ticks=1.9),
            request(session, request_id="viewer-6", advance_after_accept="false"),
        ]:
            with self.subTest(request_id=bad["request_id"]):
                with self.assertRaises(ValueError):
                    session.apply_interaction(bad)
                self.assertEqual(snapshot, session.to_snapshot())

    def test_refine_probe_records_request_patch_and_baseline(self):
        session = make_session()
        audit = session.apply_interaction(
            request(session, request_id="viewer-refine", tool="implicit_refine_probe", advance_ticks=1)
        )
        self.assertEqual("applied", audit["status"])
        self.assertTrue(audit["refinement_request_id"])
        self.assertTrue(audit["refinement_patch_id"])
        self.assertEqual(1, len(session.refinement_requests))
        self.assertEqual(1, len(session.refinement_patches))
        self.assertEqual(1, len(session.baseline_comparisons))
        self.assertIn(session.refinement_patches[-1]["patch_id"], session.current_state["active_local_patch_ids"])

    def test_restore_snapshot_round_trips_all_session_lists(self):
        session = make_session()
        snapshot = copy.deepcopy(session.to_snapshot())
        session.advance(1)
        session.restore_snapshot(
            snapshot,
            expected_snapshot_digest=snapshot["snapshot_digest"],
        )
        self.assertEqual(snapshot, session.to_snapshot())

    def test_public_restore_requires_caller_supplied_trusted_digest(self):
        session = make_session()
        snapshot = session.to_snapshot()

        with self.assertRaisesRegex(TypeError, "expected_snapshot_digest"):
            session.restore_snapshot(snapshot)

    def test_self_rehashed_snapshot_rejects_divergent_current_state_history_head(self):
        session = make_session()
        forged = copy.deepcopy(session.to_snapshot())
        forged_head = copy.deepcopy(forged["current_state"])
        basis_id = next(iter(forged_head["basis_coefficients"]))
        forged_head["basis_coefficients"][basis_id]["density"] += 0.125
        forged["current_state"] = ImplicitFieldSession._retag_state_static(
            forged_head,
            session.run_id,
            session.current_tick,
        )
        forged["snapshot_digest"] = implicit_live_session_module._snapshot_digest(forged)

        with self.assertRaisesRegex(
            ValueError,
            "current state content differs from history head",
        ):
            ImplicitFieldSession.rehydrate_snapshot(
                forged,
                expected_snapshot_digest=forged["snapshot_digest"],
            )

    def test_self_rehashed_snapshot_rejects_forged_projection_frame_summary(self):
        session = make_session()
        session.advance(1)
        forged = copy.deepcopy(session.to_snapshot())
        forged["projection_frames"][-1]["payload"]["five_phase_live_summary"][
            "live_step_id"
        ] = forged["five_phase_live_steps"][0]["live_step_id"]
        forged["snapshot_digest"] = implicit_live_session_module._snapshot_digest(forged)

        with self.assertRaisesRegex(
            ValueError,
            "projection frame semantic completion mismatch",
        ):
            ImplicitFieldSession.rehydrate_snapshot(
                forged,
                expected_snapshot_digest=forged["snapshot_digest"],
            )

    def test_self_rehashed_snapshot_rejects_forged_pattern_intrinsic_geometry(self):
        session = make_session()
        session.advance(2)
        forged = copy.deepcopy(session.to_snapshot())
        pattern = next(
            record
            for record in reversed(forged["five_phase_patterns"])
            if record["payload"].get("previous_pattern_record_id")
        )
        bounds = list(pattern["support_bounds_grid"])
        bounds[0] = min(bounds[2], bounds[0] + 1)
        pattern["support_bounds_grid"] = bounds
        forged["snapshot_digest"] = implicit_live_session_module._snapshot_digest(forged)

        with self.assertRaisesRegex(
            ValueError,
            "FivePhase authority lineage completion mismatch",
        ):
            ImplicitFieldSession.rehydrate_snapshot(
                forged,
                expected_snapshot_digest=forged["snapshot_digest"],
            )

    def test_self_rehashed_snapshot_rejects_camera_path_head_mismatch(self):
        session = make_session()
        forged = copy.deepcopy(session.to_snapshot())
        forged["camera_pose"]["origin"][0] += 0.5
        forged["snapshot_digest"] = implicit_live_session_module._snapshot_digest(forged)

        with self.assertRaisesRegex(
            ValueError,
            "camera pose does not match active observer path",
        ):
            ImplicitFieldSession.rehydrate_snapshot(
                forged,
                expected_snapshot_digest=forged["snapshot_digest"],
            )

    def test_self_rehashed_snapshot_rejects_duplicate_interaction_audit(self):
        session = make_session()
        session.apply_interaction(
            request(session, request_id="snapshot-duplicate-audit", advance_ticks=1)
        )
        forged = copy.deepcopy(session.to_snapshot())
        forged["interaction_audits"].append(
            copy.deepcopy(forged["interaction_audits"][0])
        )
        forged["snapshot_digest"] = implicit_live_session_module._snapshot_digest(forged)

        with self.assertRaisesRegex(
            ValueError,
            "interaction .* identity must be unique",
        ):
            ImplicitFieldSession.rehydrate_snapshot(
                forged,
                expected_snapshot_digest=forged["snapshot_digest"],
            )

    def test_self_rehashed_snapshot_rejects_ordinary_transition_without_application(self):
        session = make_session()
        session.advance(1)
        before = session.to_snapshot()
        forged = copy.deepcopy(before)
        forged["five_phase_feedback_applications"].pop()
        forged["snapshot_digest"] = implicit_live_session_module._snapshot_digest(forged)

        with self.assertRaisesRegex(ValueError, "application ownership mismatch"):
            session.restore_snapshot(
                forged,
                expected_snapshot_digest=forged["snapshot_digest"],
            )

        self.assertEqual(before, session.to_snapshot())

    def test_self_rehashed_snapshot_rejects_duplicate_application_owner(self):
        session = make_session()
        session.advance(1)
        before = session.to_snapshot()
        forged = copy.deepcopy(before)
        duplicate = copy.deepcopy(forged["five_phase_feedback_applications"][-1])
        duplicate["application_record_id"] += "::duplicate"
        forged["five_phase_feedback_applications"].append(duplicate)
        forged["snapshot_digest"] = implicit_live_session_module._snapshot_digest(forged)

        with self.assertRaisesRegex(ValueError, "application ownership mismatch"):
            session.restore_snapshot(
                forged,
                expected_snapshot_digest=forged["snapshot_digest"],
            )

        self.assertEqual(before, session.to_snapshot())

    def test_self_rehashed_snapshot_rejects_orphan_feedback_record(self):
        session = make_session()
        session.apply_interaction(
            request(session, request_id="orphan-feedback", duration_ticks=2, advance_ticks=6)
        )
        before = session.to_snapshot()
        forged = copy.deepcopy(before)
        owner = forged["five_phase_live_steps"][-1]
        self.assertTrue(owner["feedback_record_ids"])
        orphan_id = owner["feedback_record_ids"].pop()
        owner["source_record_ids"].remove(orphan_id)
        forged["snapshot_digest"] = implicit_live_session_module._snapshot_digest(forged)

        with self.assertRaisesRegex(ValueError, "feedback_record_ids ownership mismatch"):
            session.restore_snapshot(
                forged,
                expected_snapshot_digest=forged["snapshot_digest"],
            )

        self.assertEqual(before, session.to_snapshot())

    def test_self_rehashed_snapshot_rejects_stale_pattern_predecessor(self):
        session = make_session()
        session.advance(3)
        before = session.to_snapshot()
        forged = copy.deepcopy(before)
        patterns_by_id = {
            record["record_id"]: record for record in forged["five_phase_patterns"]
        }
        owner_index = 2
        current = patterns_by_id[forged["five_phase_live_steps"][owner_index]["pattern_ids"][0]]
        identity_id = current["payload"]["pattern_identity_id"]
        stale = next(
            patterns_by_id[record_id]
            for record_id in forged["five_phase_live_steps"][owner_index - 2]["pattern_ids"]
            if patterns_by_id[record_id]["payload"]["pattern_identity_id"] == identity_id
        )
        current["payload"]["previous_pattern_record_id"] = stale["record_id"]
        forged["snapshot_digest"] = implicit_live_session_module._snapshot_digest(forged)

        with self.assertRaisesRegex(ValueError, "Pattern predecessor is not immediate"):
            session.restore_snapshot(
                forged,
                expected_snapshot_digest=forged["snapshot_digest"],
            )

        self.assertEqual(before, session.to_snapshot())

    def test_self_rehashed_snapshot_rejects_forged_pattern_stability_even_with_matching_agent(self):
        session = make_session()
        session.advance(2)
        before = session.to_snapshot()
        forged = copy.deepcopy(before)
        owner = forged["five_phase_live_steps"][-1]
        pattern_id = owner["pattern_ids"][0]
        pattern = next(
            record for record in forged["five_phase_patterns"] if record["record_id"] == pattern_id
        )
        pattern["stability_score"] = 0.123
        agent = next(
            record
            for record in forged["five_phase_agent_states"]
            if record["pattern_id"] == pattern_id
        )
        agent["response_stability"] = 0.123
        forged["snapshot_digest"] = implicit_live_session_module._snapshot_digest(forged)

        with self.assertRaisesRegex(ValueError, "Pattern stability does not match fixed-support response"):
            session.restore_snapshot(
                forged,
                expected_snapshot_digest=forged["snapshot_digest"],
            )

        self.assertEqual(before, session.to_snapshot())

    def test_self_rehashed_snapshot_rejects_stale_feedback_predecessor(self):
        session = make_session()
        session.apply_interaction(
            request(session, request_id="stale-feedback", duration_ticks=2, advance_ticks=6)
        )
        before = session.to_snapshot()
        forged = snapshot_with_stale_feedback_predecessor(session)

        with self.assertRaisesRegex(ValueError, "Feedback predecessor is not immediate"):
            session.restore_snapshot(
                forged,
                expected_snapshot_digest=forged["snapshot_digest"],
            )

        self.assertEqual(before, session.to_snapshot())

    def test_self_rehashed_snapshot_rejects_stale_application_source_step(self):
        session = make_session()
        session.five_phase_feedback_enabled = False
        session.advance(2)
        before = session.to_snapshot()
        forged = copy.deepcopy(before)
        implicit_step = forged["implicit_live_steps"][-1]
        application = next(
            record
            for record in forged["five_phase_feedback_applications"]
            if record["implicit_live_step_id"] == implicit_step["step_id"]
        )
        immediate_id = application["five_phase_live_step_ids"][0]
        stale_step = forged["five_phase_live_steps"][0]
        stale_id = stale_step["live_step_id"]
        self.assertNotEqual(immediate_id, stale_id)
        application["five_phase_live_step_ids"] = [stale_id]
        application["feedback_record_ids"] = list(stale_step["feedback_record_ids"])
        application["candidate_feedback_projection"] = copy.deepcopy(
            stale_step["feedback_input_projection"]
        )
        application["candidate_feedback_projection_digest"] = (
            implicit_live_session_module._canonical_digest(
                application["candidate_feedback_projection"]
            )
        )
        application["baseline_response_measurements"] = []
        application["candidate_response_measurements"] = []
        application["eligibility_reason"] = "no_candidate"
        application["source_record_ids"] = [
            stale_id if value == immediate_id else value
            for value in application["source_record_ids"]
        ]
        implicit_step["five_phase_live_step_ids"] = [stale_id]
        implicit_step["source_record_ids"] = [
            stale_id if value == immediate_id else value
            for value in implicit_step["source_record_ids"]
        ]
        forged["snapshot_digest"] = implicit_live_session_module._snapshot_digest(forged)

        with self.assertRaisesRegex(ValueError, "application source step is not immediate"):
            session.restore_snapshot(
                forged,
                expected_snapshot_digest=forged["snapshot_digest"],
            )

        self.assertEqual(before, session.to_snapshot())

    def test_self_rehashed_snapshot_rejects_duplicate_feedback_consumption(self):
        session = make_session()
        session.apply_interaction(
            request(session, request_id="duplicate-feedback", duration_ticks=2, advance_ticks=6)
        )
        before = session.to_snapshot()
        forged = copy.deepcopy(before)
        application = next(
            record
            for record in forged["five_phase_feedback_applications"]
            if record["feedback_record_ids"]
        )
        application["feedback_record_ids"].append(application["feedback_record_ids"][0])
        forged["snapshot_digest"] = implicit_live_session_module._snapshot_digest(forged)

        with self.assertRaisesRegex(
            ValueError,
            "does not consume exact predecessor Feedback",
        ):
            session.restore_snapshot(
                forged,
                expected_snapshot_digest=forged["snapshot_digest"],
            )

        self.assertEqual(before, session.to_snapshot())

    def test_self_rehashed_snapshot_requires_one_shot_consumption_marker(self):
        session = make_session()
        session.advance(1)
        before = session.to_snapshot()
        forged = copy.deepcopy(before)
        forged["five_phase_feedback_applications"][-1]["feedback_consumed"] = False
        forged["snapshot_digest"] = implicit_live_session_module._snapshot_digest(forged)

        with self.assertRaisesRegex(ValueError, "one-shot consumption"):
            session.restore_snapshot(
                forged,
                expected_snapshot_digest=forged["snapshot_digest"],
            )

        self.assertEqual(before, session.to_snapshot())

    def test_stale_interaction_frame_fails_without_rebinding_to_latest_state(self):
        session = make_session()
        stale = request(session, request_id="viewer-stale")
        session.advance(1)
        snapshot = session.to_snapshot()

        with self.assertRaisesRegex(ValueError, "stale source_projection_frame_id"):
            session.apply_interaction(stale)

        self.assertEqual(snapshot, session.to_snapshot())

    def test_fractional_duration_changes_realized_field_dose(self):
        short = make_session()
        long = make_session()
        short.five_phase_feedback_enabled = False
        long.five_phase_feedback_enabled = False

        short.apply_interaction(
            request(
                short,
                request_id="duration-short",
                duration_ticks=1.0,
                advance_ticks=3,
                amplitude=0.1,
            )
        )
        long.apply_interaction(
            request(
                long,
                request_id="duration-long",
                duration_ticks=2.5,
                advance_ticks=3,
                amplitude=0.1,
            )
        )

        self.assertNotEqual(
            short.current_state["basis_coefficients"],
            long.current_state["basis_coefficients"],
        )
        self.assertEqual(1, len(short.interaction_audits[-1]["applications"]))
        self.assertEqual(3, len(long.interaction_audits[-1]["applications"]))

    def test_radius_changes_local_support_and_each_energy_ledger_closes(self):
        narrow = make_session()
        wide = make_session()
        narrow.five_phase_feedback_enabled = False
        wide.five_phase_feedback_enabled = False

        narrow_audit = narrow.apply_interaction(
            request(narrow, request_id="radius-narrow", radius_world=0.25, duration_ticks=1.0, advance_ticks=1)
        )
        wide_audit = wide.apply_interaction(
            request(wide, request_id="radius-wide", radius_world=4.0, duration_ticks=1.0, advance_ticks=1)
        )

        self.assertNotEqual(narrow_audit["kappa_by_basis"], wide_audit["kappa_by_basis"])
        self.assertNotEqual(
            narrow_audit["applications"][0]["realized_input_projection"],
            wide_audit["applications"][0]["realized_input_projection"],
        )
        for session in (narrow, wide):
            step = session.implicit_live_steps[-1]
            self.assertEqual(2, len(step["energy_ledgers"]))
            for ledger in step["energy_ledgers"]:
                self.assertLessEqual(abs(ledger["residual"]), ledger["residual_tolerance"])

    def test_signed_controls_have_audited_raw_and_realized_energy_response(self):
        excited = make_session()
        dampened = make_session()
        excited.five_phase_feedback_enabled = False
        dampened.five_phase_feedback_enabled = False

        excite_audit = excited.apply_interaction(
            request(excited, request_id="signed-excite", tool="implicit_local_excite", duration_ticks=1, advance_ticks=1)
        )
        dampen_audit = dampened.apply_interaction(
            request(dampened, request_id="signed-dampen", tool="implicit_local_dampen", duration_ticks=1, advance_ticks=1)
        )

        self.assertGreater(excite_audit["signed_amplitude"], 0.0)
        self.assertLess(dampen_audit["signed_amplitude"], 0.0)
        self.assertGreater(excited.implicit_live_steps[-1]["energy_ledgers"][-1]["i_user"], 0.0)
        self.assertLess(dampened.implicit_live_steps[-1]["energy_ledgers"][-1]["i_user"], 0.0)
        self.assertEqual(
            excite_audit["applications"][0]["raw_input_projection"],
            excited.implicit_live_steps[-1]["raw_user_input_projection"],
        )
        self.assertTrue(dampen_audit["applications"][0]["realized_input_projection"])
        self.assertTrue(
            all(
                float(channels.get("density", 0.0)) >= 0.0
                for channels in dampened.current_state["basis_coefficients"].values()
            )
        )

    def test_trusted_s0_transcript_replay_is_exact_and_s1_duplicate_rejects(self):
        session = make_session()
        session.five_phase_feedback_enabled = False
        s0 = session.to_snapshot()
        session.apply_interaction(
            request(session, request_id="exact-replay", duration_ticks=2.5, advance_ticks=3, amplitude=0.1)
        )
        s1 = session.to_snapshot()

        replayed = ImplicitFieldSession.replay_interaction_transcript(
            s0,
            session.interaction_transcript,
            expected_snapshot_digest=s0["snapshot_digest"],
        )

        self.assertEqual(s1, replayed.to_snapshot())
        restored_s1 = ImplicitFieldSession.rehydrate_snapshot(
            s1,
            expected_snapshot_digest=s1["snapshot_digest"],
        )
        with self.assertRaisesRegex(ValueError, "duplicate implicit request_id"):
            restored_s1.apply_interaction(session.interaction_transcript[-1]["request"])

    def test_snapshot_feedback_override_is_the_only_controlled_fork(self):
        session = make_session()
        snapshot = session.to_snapshot()
        fork = ImplicitFieldSession.rehydrate_snapshot(
            snapshot,
            expected_snapshot_digest=snapshot["snapshot_digest"],
            five_phase_feedback_enabled_override=False,
        )

        self.assertEqual(session.session_id, fork.session_id)
        self.assertEqual(session.run_id, fork.run_id)
        self.assertFalse(fork.five_phase_feedback_enabled)
        self.assertEqual(session.current_state, fork.current_state)

    def test_failed_multi_tick_advance_rolls_back_first_tick_without_full_snapshot_restore(self):
        session = make_session()
        session.five_phase_feedback_enabled = False
        session.apply_interaction(
            request(
                session,
                request_id="journal-rollback",
                duration_ticks=2,
                advance_after_accept=False,
            )
        )
        before = session.to_snapshot()
        real_advance = implicit_live_session_module.advance_implicit_field_state
        calls = 0

        def fail_second_tick(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValueError("injected second-tick failure")
            return real_advance(*args, **kwargs)

        with patch.object(
            implicit_live_session_module,
            "advance_implicit_field_state",
            side_effect=fail_second_tick,
        ):
            with self.assertRaisesRegex(ValueError, "injected second-tick failure"):
                session.advance(2)

        self.assertEqual(before, session.to_snapshot())

    def test_concurrent_success_and_failure_cannot_lose_committed_update(self):
        session = make_session()
        session.five_phase_feedback_enabled = False
        success_request = request(
            session,
            request_id="concurrent-success",
            duration_ticks=1,
            advance_ticks=1,
            amplitude=0.1,
        )
        failing_request = request(
            session,
            request_id="concurrent-failure",
            tool="implicit_directional_push",
            duration_ticks=1,
            advance_ticks=1,
            amplitude=1.0,
            source_vector_image=[float("nan"), 0.0],
        )
        barrier = threading.Barrier(3)
        outcomes = []

        def invoke(payload):
            barrier.wait()
            try:
                outcomes.append((payload["request_id"], "ok", session.apply_interaction(payload)))
            except ValueError as exc:
                outcomes.append((payload["request_id"], "error", str(exc)))

        threads = [
            threading.Thread(target=invoke, args=(success_request,)),
            threading.Thread(target=invoke, args=(failing_request,)),
        ]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()

        self.assertEqual(1, len([item for item in outcomes if item[1] == "ok"]))
        self.assertEqual("concurrent-success", [item for item in outcomes if item[1] == "ok"][0][0])
        self.assertEqual(2, session.current_tick)
        self.assertEqual(["concurrent-success"], [audit["request_id"] for audit in session.interaction_audits])

    def test_ninth_due_control_rejects_tick_without_consuming_pending_state(self):
        session = make_session()
        session.five_phase_feedback_enabled = False
        for index in range(9):
            session.apply_interaction(
                request(
                    session,
                    request_id=f"due-budget-{index}",
                    amplitude=0.05,
                    duration_ticks=1,
                    advance_after_accept=False,
                )
            )
        before = session.to_snapshot()

        with self.assertRaisesRegex(ValueError, "due control budget"):
            session.advance(1)

        self.assertEqual(before, session.to_snapshot())

    def test_aggregate_user_budget_rejects_all_eight_controls_atomically(self):
        session = make_session()
        session.five_phase_feedback_enabled = False
        for index in range(8):
            session.apply_interaction(
                request(
                    session,
                    request_id=f"aggregate-budget-{index}",
                    amplitude=0.2,
                    duration_ticks=1,
                    advance_after_accept=False,
                )
            )
        before = session.to_snapshot()

        with self.assertRaisesRegex(ValueError, "per-tick L1 budget"):
            session.advance(1)

        self.assertEqual(before, session.to_snapshot())

    def test_sixty_fifth_pending_control_rejects_before_mutation(self):
        session = make_session()
        session.five_phase_feedback_enabled = False
        for index in range(64):
            session.apply_interaction(
                request(
                    session,
                    request_id=f"pending-budget-{index}",
                    amplitude=0.0,
                    duration_ticks=1,
                    advance_after_accept=False,
                )
            )
        before = session.to_snapshot()

        with self.assertRaisesRegex(ValueError, "pending control budget"):
            session.apply_interaction(
                request(
                    session,
                    request_id="pending-budget-64",
                    amplitude=0.0,
                    duration_ticks=1,
                    advance_after_accept=False,
                )
            )

        self.assertEqual(before, session.to_snapshot())

    def test_sixty_fifth_active_scope_fails_detached_restore_before_commit(self):
        session = make_session()
        before = session.to_snapshot()
        forged = copy.deepcopy(before)
        basis_id = session.current_state["basis_ids"][0]
        forged["active_energy_scopes"] = [
            {
                "scope_id": f"forged-active-scope-{index}",
                "kappa_by_basis": {basis_id: 1.0},
                "activation_tick": session.current_tick,
                "final_input_tick": session.current_tick,
                "expiry_tick": session.current_tick + 8,
            }
            for index in range(65)
        ]
        forged["snapshot_digest"] = implicit_live_session_module._snapshot_digest(forged)

        with self.assertRaisesRegex(ValueError, "active scope budget exceeded"):
            session.restore_snapshot(
                forged,
                expected_snapshot_digest=forged["snapshot_digest"],
            )

        self.assertEqual(before, session.to_snapshot())

    def test_self_rehashed_snapshot_rejects_unowned_active_energy_scope(self):
        session = make_session()
        before = session.to_snapshot()
        forged = copy.deepcopy(before)
        basis_id = session.current_state["basis_ids"][0]
        forged["active_energy_scopes"].append(
            {
                "scope_id": "forged-unowned-scope",
                "kappa_by_basis": {basis_id: 1.0},
                "activation_tick": session.current_tick + 1,
                "final_input_tick": session.current_tick + 1,
                "expiry_tick": session.current_tick + 9,
            }
        )
        forged["snapshot_digest"] = implicit_live_session_module._snapshot_digest(forged)

        with self.assertRaisesRegex(ValueError, "active energy scope ownership/lifecycle mismatch"):
            session.restore_snapshot(
                forged,
                expected_snapshot_digest=forged["snapshot_digest"],
            )

        self.assertEqual(before, session.to_snapshot())

    def test_self_rehashed_snapshot_requires_zero_amplitude_pending_scope(self):
        session = make_session()
        session.apply_interaction(
            request(
                session,
                request_id="zero-amplitude-scope",
                amplitude=0.0,
                duration_ticks=2.25,
                advance_after_accept=False,
            )
        )
        before = session.to_snapshot()
        forged = copy.deepcopy(before)
        forged["active_energy_scopes"] = []
        forged["snapshot_digest"] = implicit_live_session_module._snapshot_digest(forged)

        with self.assertRaisesRegex(ValueError, "active energy scope ownership/lifecycle mismatch"):
            session.restore_snapshot(
                forged,
                expected_snapshot_digest=forged["snapshot_digest"],
            )

        self.assertEqual(before, session.to_snapshot())

    def test_applied_feedback_is_one_shot_and_strictly_reduces_fixed_support_error(self):
        session = make_session()
        session.apply_interaction(
            request(session, request_id="feedback-precommit", duration_ticks=2, advance_ticks=6)
        )
        eligible = [
            application
            for application in session.five_phase_feedback_applications
            if application["feedback_applied"]
        ]

        self.assertTrue(eligible)
        consumed_ids = []
        for application in eligible:
            self.assertEqual("eligible_error_reduction", application["eligibility_reason"])
            self.assertTrue(application["feedback_consumed"])
            self.assertTrue(application["applied_feedback_projection"])
            self.assertEqual(
                len(application["baseline_response_measurements"]),
                len(application["candidate_response_measurements"]),
            )
            for baseline, candidate in zip(
                application["baseline_response_measurements"],
                application["candidate_response_measurements"],
            ):
                self.assertTrue(baseline["candidate_direction_eligible"])
                self.assertLess(candidate["absolute_error"], baseline["absolute_error"])
            consumed_ids.extend(application["feedback_record_ids"])
        self.assertEqual(len(consumed_ids), len(set(consumed_ids)))

    def test_external_snapshot_has_schema_digest_and_rejects_corruption(self):
        session = make_session()
        snapshot = session.to_snapshot()
        self.assertEqual("implicit_live_session_snapshot_v2", snapshot["schema"])
        self.assertTrue(snapshot["snapshot_digest"].startswith("sha256:"))

        corrupted = copy.deepcopy(snapshot)
        corrupted["current_state"]["basis_coefficients"] = {}
        with self.assertRaisesRegex(ValueError, "snapshot digest mismatch"):
            session.restore_snapshot(
                corrupted,
                expected_snapshot_digest=snapshot["snapshot_digest"],
            )

    def test_self_rehashed_forged_ledger_fails_semantic_transition_replay(self):
        session = make_session()
        session.five_phase_feedback_enabled = False
        session.apply_interaction(
            request(session, request_id="forged-ledger", duration_ticks=1, advance_ticks=1)
        )
        before = session.to_snapshot()
        forged = copy.deepcopy(before)
        forged["implicit_live_steps"][-1]["energy_ledgers"][-1]["i_user"] += 0.25
        forged["snapshot_digest"] = implicit_live_session_module._snapshot_digest(forged)

        with self.assertRaisesRegex(ValueError, "energy ledger replay mismatch"):
            session.restore_snapshot(
                forged,
                expected_snapshot_digest=forged["snapshot_digest"],
            )

        self.assertEqual(before, session.to_snapshot())

    def test_self_rehashed_forged_feedback_fails_semantic_reconstruction(self):
        session = make_session()
        session.apply_interaction(
            request(session, request_id="forged-feedback", duration_ticks=2, advance_ticks=5)
        )
        before = session.to_snapshot()
        forged = copy.deepcopy(before)
        self.assertTrue(forged["five_phase_feedback_records"])
        forged["five_phase_feedback_records"][0]["expected_distance_reduction"] += 0.5
        forged["snapshot_digest"] = implicit_live_session_module._snapshot_digest(forged)

        with self.assertRaisesRegex(ValueError, "Feedback semantic reconstruction mismatch"):
            session.restore_snapshot(
                forged,
                expected_snapshot_digest=forged["snapshot_digest"],
            )

        self.assertEqual(before, session.to_snapshot())

    def test_self_rehashed_forged_application_measurement_fails_recomputation(self):
        session = make_session()
        session.apply_interaction(
            request(session, request_id="forged-measurement", duration_ticks=2, advance_ticks=5)
        )
        before = session.to_snapshot()
        forged = copy.deepcopy(before)
        application = next(
            item
            for item in forged["five_phase_feedback_applications"]
            if item["baseline_response_measurements"]
        )
        measurement = application["baseline_response_measurements"][0]
        measurement["absolute_error"] += 0.25
        unsigned_measurement = {key: value for key, value in measurement.items() if key != "measurement_digest"}
        measurement["measurement_digest"] = implicit_live_session_module._canonical_digest(unsigned_measurement)
        forged["snapshot_digest"] = implicit_live_session_module._snapshot_digest(forged)

        with self.assertRaisesRegex(ValueError, "baseline measurement reconstruction mismatch"):
            session.restore_snapshot(
                forged,
                expected_snapshot_digest=forged["snapshot_digest"],
            )

        self.assertEqual(before, session.to_snapshot())


if __name__ == "__main__":
    unittest.main()
