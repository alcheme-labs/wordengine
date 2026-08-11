import copy
import unittest

from world_engine.five_phase_extraction import extract_five_phase_field
from world_engine.implicit_field import build_implicit_field_state
from world_engine.implicit_field_runtime import advance_implicit_field_state
from world_engine.implicit_live_session import ImplicitFieldSession
from world_engine.five_phase_live import (
    build_five_phase_identity_support_kappa,
    build_five_phase_live_artifacts,
    build_five_phase_live_field_state,
    build_five_phase_transition_response_context,
    five_phase_feedback_to_implicit_input_projection,
    measure_five_phase_density_kappa_norm,
    measure_five_phase_feedback_response,
)
from world_engine.five_phase_patterns import build_five_phase_live_response_metrics


def make_session() -> ImplicitFieldSession:
    return ImplicitFieldSession.from_source_package(
        source_package_name="source-a",
        source_package_digest="digest-a",
        case_type="implicit_full_scene",
        run_id="five-phase-live-test",
        image_shape=[12, 8],
        samples_per_ray=6,
    )


def make_matched_artifacts() -> tuple[ImplicitFieldSession, dict, dict, dict]:
    session = make_session()
    first = build_five_phase_live_artifacts(
        implicit_field_state=session.current_state,
        implicit_basis_records=session.bases,
        basis_spatial_index=session.basis_spatial_index,
        run_id=session.run_id,
        bridge_index=0,
        previous_live_field_state=None,
        observer_id="observer::implicit-pinhole",
        frequency_window={"band": "wide"},
    )
    density_basis_id = next(
        str(basis["basis_id"])
        for basis in session.bases
        if basis.get("basis_kind") == "density_lobe"
    )
    second_state = advance_implicit_field_state(
        session.current_state,
        session.bases,
        user_input_projection={density_basis_id: {"density": 0.4}},
    )
    pattern_identity_id = str(first["patterns"][0].payload["pattern_identity_id"])
    second = build_five_phase_live_artifacts(
        implicit_field_state=second_state,
        implicit_basis_records=session.bases,
        basis_spatial_index=session.basis_spatial_index,
        run_id=session.run_id,
        bridge_index=1,
        previous_live_field_state=first["field_states"][0],
        previous_patterns=first["patterns"],
        previous_residual_constraints=first["residual_constraints"],
        previous_live_step_id=first["live_step"]["live_step_id"],
        response_context_by_pattern_identity_id={
            pattern_identity_id: {
                "episode_id": "episode::five-phase-live::1",
                "episode_start_tick": 1,
                "last_user_input_tick": 1,
                "episode_end_tick": 9,
                "realized_user_dose": 0.2,
                "realized_feedback_dose": 0.0,
            }
        },
        observer_id="observer::implicit-pinhole",
        frequency_window={"band": "wide"},
    )
    return session, first, second, second_state


class FivePhaseLiveBridgeTests(unittest.TestCase):
    def test_bridge_reads_implicit_state_into_field_state(self) -> None:
        session = make_session()

        field_state, bridge = build_five_phase_live_field_state(
            implicit_field_state=session.current_state,
            implicit_basis_records=session.bases,
            basis_spatial_index=session.basis_spatial_index,
            run_id=session.run_id,
            bridge_index=0,
            previous_live_field_state=None,
            grid_shape=(8, 6),
        )

        self.assertEqual("five_phase_live_field_bridge_v1", bridge["schema"])
        self.assertEqual(session.current_tick, bridge["implicit_tick"])
        self.assertEqual(0, bridge["field_tick"])
        self.assertEqual(0, field_state.tick)
        self.assertEqual([6, 8], field_state.grid_shape)
        self.assertIn("pattern", field_state.channels)
        self.assertEqual(session.current_state["implicit_field_state_id"], bridge["implicit_field_state_id"])
        self.assertEqual(field_state.field_state_id, bridge["field_state_id"])
        self.assertIn(session.current_state["implicit_field_state_id"], field_state.source_record_ids)
        self.assertIn(bridge["bridge_record_id"], field_state.source_record_ids)

        phase = extract_five_phase_field(field_state)
        self.assertEqual(field_state.field_state_id, phase.source_field_state_id)
        self.assertIn(field_state.field_state_id, phase.source_record_ids)

    def test_bridge_preserves_raw_signed_density_samples(self) -> None:
        session = make_session()
        source = session.current_state
        coefficients = {
            basis_id: {**channels, "density": 0.0}
            for basis_id, channels in source["basis_coefficients"].items()
        }
        density_basis_id = next(
            str(basis["basis_id"])
            for basis in session.bases
            if basis.get("basis_kind") == "density_lobe"
        )
        coefficients[density_basis_id]["density"] = -1.0
        signed_state = build_implicit_field_state(
            implicit_field_state_id="implicit-field-state::signed-bridge",
            tick=int(source["tick"]),
            basis_ids=source["basis_ids"],
            basis_layout_digest=source["basis_layout_digest"],
            basis_spatial_index_digest=source["basis_spatial_index_digest"],
            basis_coefficients=coefficients,
            sparse_coupling_edges=source["sparse_coupling_edges"],
            background_model=source["background_model"],
            active_local_patch_ids=source["active_local_patch_ids"],
            validity_region_world=source["validity_region_world"],
            energy_summary=source["energy_summary"],
            source_record_ids=source["source_record_ids"],
        )

        field_state, bridge = build_five_phase_live_field_state(
            implicit_field_state=signed_state,
            implicit_basis_records=session.bases,
            basis_spatial_index=session.basis_spatial_index,
            run_id=session.run_id,
            bridge_index=0,
            previous_live_field_state=None,
            grid_shape=(8, 6),
        )

        self.assertLess(min(value for row in field_state.channels["pattern"] for value in row), 0.0)
        self.assertTrue(bridge["signed_samples_preserved"])
        self.assertTrue(str(bridge["sample_values_digest"]).startswith("sha256:"))

    def test_bridge_rejects_viewer_shortcut_payload(self) -> None:
        session = make_session()
        bad_state = dict(session.current_state)
        bad_state["canvas_pixels"] = [[0, 0, 0]]

        with self.assertRaises(ValueError):
            build_five_phase_live_field_state(
                implicit_field_state=bad_state,
                implicit_basis_records=session.bases,
                basis_spatial_index=session.basis_spatial_index,
                run_id=session.run_id,
                bridge_index=0,
                previous_live_field_state=None,
                grid_shape=(8, 6),
            )


class FivePhaseLiveArtifactBundleTests(unittest.TestCase):
    def test_fixed_support_kappa_excludes_remote_basis_input(self) -> None:
        session = make_session()
        artifacts = build_five_phase_live_artifacts(
            implicit_field_state=session.current_state,
            implicit_basis_records=session.bases,
            basis_spatial_index=session.basis_spatial_index,
            run_id=session.run_id,
            bridge_index=0,
            previous_live_field_state=None,
            observer_id="observer::implicit-pinhole",
            frequency_window={"band": "wide"},
        )
        pattern = artifacts["patterns"][0]
        remote_bases = copy.deepcopy(session.bases)
        remote_basis = remote_bases[-1]
        remote_basis_id = str(remote_basis["basis_id"])
        remote_basis["support_region_world"] = {
            "min": [100.0, 100.0, 100.0],
            "max": [101.0, 101.0, 101.0],
        }
        kappa = build_five_phase_identity_support_kappa(
            implicit_field_state=session.current_state,
            implicit_basis_records=remote_bases,
            support_bounds_grid=pattern.payload["identity_support_bounds_grid"],
            grid_shape=pattern.payload["identity_support_grid_shape"],
        )
        remote_norm = measure_five_phase_density_kappa_norm(
            coefficient_projection={remote_basis_id: {"density": 0.75}},
            implicit_basis_records=remote_bases,
            identity_support_kappa=kappa,
        )

        self.assertEqual(0.0, kappa[remote_basis_id])
        self.assertEqual(0.0, remote_norm)

    def test_live_user_dose_uses_setpoint_kappa_norm_and_excludes_feedback_from_Q(self) -> None:
        session = make_session()
        first = build_five_phase_live_artifacts(
            implicit_field_state=session.current_state,
            implicit_basis_records=session.bases,
            basis_spatial_index=session.basis_spatial_index,
            run_id=session.run_id,
            bridge_index=0,
            previous_live_field_state=None,
            observer_id="observer::implicit-pinhole",
            frequency_window={"band": "wide"},
        )
        pattern = first["patterns"][0]
        density_basis_id = next(
            str(basis["basis_id"])
            for basis in session.bases
            if basis.get("basis_kind") == "density_lobe"
        )
        user_projection = {density_basis_id: {"density": 0.1}}
        feedback_projection = {density_basis_id: {"density": 0.2}}
        current_state = advance_implicit_field_state(
            session.current_state,
            session.bases,
            user_input_projection=user_projection,
            feedback_input_projection=feedback_projection,
        )
        context = build_five_phase_transition_response_context(
            previous_pattern=pattern,
            previous_implicit_field_state=session.current_state,
            current_implicit_field_state=current_state,
            implicit_basis_records=session.bases,
            basis_spatial_index=session.basis_spatial_index,
            realized_user_input_projection=user_projection,
            realized_feedback_input_projection=feedback_projection,
            tick=int(current_state["tick"]),
        )
        expected_user_norm = measure_five_phase_density_kappa_norm(
            coefficient_projection=user_projection,
            implicit_basis_records=session.bases,
            identity_support_kappa=pattern.payload["identity_support_kappa"],
        )
        expected_q_user = expected_user_norm / pattern.payload["support_coefficient_norm_setpoint"]
        _, response = build_five_phase_live_response_metrics(
            context=context,
            previous_pattern=pattern,
            pattern_identity_id=pattern.payload["pattern_identity_id"],
            tick=int(current_state["tick"]),
            measured_support_energy=context["support_energy_current"],
        )

        self.assertAlmostEqual(expected_q_user, context["realized_user_dose"])
        self.assertGreater(context["realized_feedback_dose"], 0.0)
        self.assertAlmostEqual(context["realized_user_dose"], response["Q_live"])
        self.assertNotAlmostEqual(
            context["realized_user_dose"] + context["realized_feedback_dose"],
            response["Q_live"],
        )

    def test_initial_unmatched_artifacts_have_exact_agent_chain_without_feedback(self) -> None:
        session = make_session()

        artifacts = build_five_phase_live_artifacts(
            implicit_field_state=session.current_state,
            implicit_basis_records=session.bases,
            basis_spatial_index=session.basis_spatial_index,
            run_id=session.run_id,
            bridge_index=0,
            previous_live_field_state=None,
            observer_id="observer::implicit-pinhole",
            frequency_window={"band": "wide"},
        )

        self.assertEqual("five_phase_live_step_record_v1", artifacts["live_step"]["schema"])
        self.assertEqual(1, len(artifacts["field_states"]))
        self.assertEqual(1, len(artifacts["phase_fields"]))
        self.assertEqual(1, len(artifacts["constraint_sets"]))
        self.assertGreaterEqual(len(artifacts["patterns"]), 1)
        self.assertGreaterEqual(len(artifacts["traces"]), 1)
        self.assertGreaterEqual(len(artifacts["residual_constraints"]), 1)
        self.assertGreaterEqual(len(artifacts["agent_states"]), 1)
        self.assertIn(artifacts["live_step"]["live_step_id"], artifacts["live_step"]["source_record_ids"])
        self.assertIn(artifacts["phase_fields"][0].record_id, artifacts["live_step"]["source_record_ids"])
        self.assertIn(artifacts["traces"][0].record_id, artifacts["live_step"]["trace_ids"])
        agent = artifacts["agent_states"][0]
        trace = artifacts["traces"][0]
        residual = artifacts["residual_constraints"][0]
        pattern = artifacts["patterns"][0]
        self.assertEqual("five_phase_agent_state_v2", agent.schema)
        self.assertEqual(pattern.record_id, agent.pattern_id)
        self.assertEqual(trace.record_id, agent.trace_id)
        self.assertEqual(residual.record_id, agent.residual_constraint_id)
        self.assertEqual(pattern.phase_vector.to_dict(), agent.setpoint.to_dict())
        self.assertEqual(agent.support_energy_setpoint, agent.support_energy_current)
        self.assertEqual([], artifacts["feedback_records"])
        self.assertEqual({}, artifacts["live_step"]["feedback_input_projection"])
        self.assertFalse(artifacts["live_step"]["is_authority_state"])

    def test_matched_step_reuses_identity_memory_and_prior_measurement_setpoint(self) -> None:
        _, first, second, second_state = make_matched_artifacts()
        previous_pattern = first["patterns"][0]
        pattern_identity_id = str(previous_pattern.payload["pattern_identity_id"])

        pattern = second["patterns"][0]
        trace = second["traces"][0]
        residual = second["residual_constraints"][0]
        agent = second["agent_states"][0]
        self.assertNotEqual(previous_pattern.record_id, pattern.record_id)
        self.assertEqual(pattern_identity_id, pattern.payload["pattern_identity_id"])
        self.assertEqual(previous_pattern.record_id, pattern.payload["previous_pattern_record_id"])
        self.assertGreater(
            residual.memory_next,
            0.45 * trace.trace_intensity,
        )
        self.assertEqual(previous_pattern.phase_vector.to_dict(), agent.setpoint.to_dict())
        self.assertEqual(trace.record_id, agent.trace_id)
        self.assertEqual(residual.record_id, agent.residual_constraint_id)
        self.assertEqual(second["bridges"][0]["bridge_record_id"], agent.bridge_record_id)
        self.assertEqual(second_state["implicit_field_state_id"], agent.source_state_id)
        self.assertEqual(second_state["state_digest"], agent.source_state_digest)
        self.assertNotEqual(agent.support_energy_setpoint, agent.support_energy_current)

    def test_matched_response_emits_spatial_signed_candidate_and_projection_consumes_it_exactly(self) -> None:
        session, first, second, _ = make_matched_artifacts()

        self.assertEqual(1, len(second["feedback_records"]))
        feedback = second["feedback_records"][0]
        pattern = second["patterns"][0]
        self.assertEqual("five_phase_feedback_v2", feedback.schema)
        self.assertEqual(first["live_step"]["live_step_id"], feedback.predecessor_causal_step_id)
        self.assertEqual(pattern.record_id, feedback.pattern_id)
        self.assertEqual({feedback.target_basis_id}, set(feedback.candidate_projection))
        density_delta = float(feedback.candidate_projection[feedback.target_basis_id]["density"])
        self.assertGreater(density_delta * feedback.signed_error * feedback.sensitivity, 0.0)

        frame = second["field_states"][0].payload["coordinate_frame"]
        origin = frame["world_origin"]
        extent = frame["world_extent"]
        height, width = second["field_states"][0].grid_shape
        point = [
            float(origin[0]) + float(extent[0]) * ((float(pattern.centroid_grid[0]) + 0.5) / width),
            float(origin[1]) + float(extent[1]) * ((float(pattern.centroid_grid[1]) + 0.5) / height),
            0.0,
        ]
        target_basis = next(basis for basis in session.bases if basis["basis_id"] == feedback.target_basis_id)
        support = target_basis["support_region_world"]
        self.assertTrue(
            all(float(support["min"][index]) <= point[index] <= float(support["max"][index]) for index in range(3))
        )

        projection = five_phase_feedback_to_implicit_input_projection(
            feedback_records=[feedback],
            patterns=second["patterns"],
            implicit_basis_records=list(reversed(session.bases)),
        )
        self.assertEqual(feedback.candidate_projection, projection)
        self.assertEqual(projection, second["live_step"]["feedback_input_projection"])

    def test_application_time_measurement_recomputes_error_and_sensitivity_for_detached_states(self) -> None:
        session, _, second, second_state = make_matched_artifacts()
        pattern = second["patterns"][0]
        agent = second["agent_states"][0]
        feedback = second["feedback_records"][0]

        baseline = measure_five_phase_feedback_response(
            implicit_field_state=second_state,
            implicit_basis_records=session.bases,
            basis_spatial_index=session.basis_spatial_index,
            pattern=pattern,
            agent_state=agent,
            feedback=feedback,
        )
        self.assertAlmostEqual(feedback.signed_error, baseline["signed_error"])
        self.assertAlmostEqual(feedback.sensitivity, baseline["sensitivity"])
        self.assertTrue(baseline["candidate_direction_eligible"])

        coefficients = {
            basis_id: dict(channels)
            for basis_id, channels in second_state["basis_coefficients"].items()
        }
        target_channels = coefficients[feedback.target_basis_id]
        target_channels["density"] = float(target_channels["density"]) + float(
            feedback.candidate_projection[feedback.target_basis_id]["density"]
        )
        candidate_state = build_implicit_field_state(
            implicit_field_state_id="implicit-field-state::feedback-candidate",
            tick=int(second_state["tick"]),
            basis_ids=second_state["basis_ids"],
            basis_layout_digest=second_state["basis_layout_digest"],
            basis_spatial_index_digest=second_state["basis_spatial_index_digest"],
            basis_coefficients=coefficients,
            sparse_coupling_edges=second_state["sparse_coupling_edges"],
            background_model=second_state["background_model"],
            active_local_patch_ids=second_state["active_local_patch_ids"],
            validity_region_world=second_state["validity_region_world"],
            energy_summary=second_state["energy_summary"],
            source_record_ids=second_state["source_record_ids"],
            runtime_cost_summary=second_state.get("runtime_cost_summary"),
        )
        candidate = measure_five_phase_feedback_response(
            implicit_field_state=candidate_state,
            implicit_basis_records=session.bases,
            basis_spatial_index=session.basis_spatial_index,
            pattern=pattern,
            agent_state=agent,
            feedback=feedback,
        )

        self.assertLess(abs(candidate["signed_error"]), abs(baseline["signed_error"]))


if __name__ == "__main__":
    unittest.main()
