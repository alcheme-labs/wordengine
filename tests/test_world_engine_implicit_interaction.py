import unittest

from world_engine.implicit_interaction import (
    build_implicit_interaction_audit,
    build_implicit_local_control_weights,
    build_implicit_pending_control_descriptor,
    canonical_implicit_signed_amplitude,
    implicit_command_id,
    implicit_duration_schedule_weights,
    implicit_request_to_input_projection,
    materialize_implicit_raw_control_projection,
    record_implicit_interaction_application,
    target_basis_from_image_xy,
    validate_implicit_interaction_request,
)


def valid_request(**overrides):
    request = {
        "schema": "implicit_interaction_request",
        "request_id": "viewer-1",
        "tool": "implicit_local_excite",
        "observer_id": "observer::implicit-pinhole",
        "source_projection_frame_id": "projection-frame::1",
        "source_frame_tick": 1,
        "source_state_id": "state::1",
        "source_ray_sample_record_id": "ray::1",
        "source_image_xy": [0.5, 0.5],
        "radius_world": 1.2,
        "amplitude": 0.35,
        "duration_ticks": 4,
        "advance_after_accept": True,
        "advance_ticks": 2,
    }
    request.update(overrides)
    return request


def basis(basis_id, center, radius=1.0):
    return {
        "basis_id": basis_id,
        "center_world_3d": list(center),
        "radius_world": radius,
        "support_region_world": {
            "min": [center[0] - radius, center[1] - radius, center[2] - radius],
            "max": [center[0] + radius, center[1] + radius, center[2] + radius],
        },
    }


class ImplicitInteractionRequestTests(unittest.TestCase):
    def test_valid_request_passes_and_generates_command_id(self):
        validate_implicit_interaction_request(
            valid_request(duration_ticks=1.25),
            declared_observer_ids=["observer::implicit-pinhole"],
            existing_request_ids=set(),
        )
        self.assertEqual("cmd::implicit::viewer-1", implicit_command_id("viewer-1"))

    def assert_invalid(self, request, message):
        with self.assertRaisesRegex(ValueError, message):
            validate_implicit_interaction_request(
                request,
                declared_observer_ids=["observer::implicit-pinhole"],
                existing_request_ids={"seen"},
            )

    def test_rejects_invalid_request_fields(self):
        cases = [
            (valid_request(tool="unknown"), "unknown implicit tool"),
            (valid_request(source_image_xy=[1.5, 0.5]), "source_image_xy outside normalized bounds"),
            (valid_request(radius_world=0), "radius_world must be positive"),
            (valid_request(radius_world=4.1), "radius_world exceeds maximum"),
            (valid_request(amplitude=-0.1), "amplitude must be non-negative"),
            (valid_request(amplitude=True), "amplitude must be a number"),
            (valid_request(amplitude="0.1"), "amplitude must be a number"),
            (valid_request(amplitude=float("inf")), "amplitude must be finite"),
            (valid_request(amplitude=1.1), "amplitude exceeds maximum"),
            (valid_request(duration_ticks=True), "duration_ticks must be a number"),
            (valid_request(duration_ticks="4"), "duration_ticks must be a number"),
            (valid_request(duration_ticks=float("nan")), "duration_ticks must be finite"),
            (valid_request(duration_ticks=0), "duration_ticks outside bounds"),
            (valid_request(duration_ticks=33), "duration_ticks outside bounds"),
            (
                valid_request(advance_after_accept="false"),
                "advance_after_accept must be a boolean",
            ),
            (valid_request(source_projection_frame_id=""), "requires source_projection_frame_id"),
            (valid_request(source_state_id=""), "requires source_state_id"),
            (valid_request(source_ray_sample_record_id=""), "requires source_ray_sample_record_id"),
            (valid_request(request_id="seen"), "duplicate implicit request_id"),
            (valid_request(observer_id="observer::missing"), "undeclared implicit observer_id"),
        ]
        for request, message in cases:
            with self.subTest(message=message):
                self.assert_invalid(request, message)

    def test_rejects_invalid_advance_ticks_when_present(self):
        self.assert_invalid(valid_request(advance_ticks=0), "advance_ticks outside bounds")
        for value in (1.9, True, "2"):
            with self.subTest(value=value):
                self.assert_invalid(
                    valid_request(advance_ticks=value),
                    "advance_ticks must be an integer",
                )


class ImplicitInteractionTargetingTests(unittest.TestCase):
    def test_targets_basis_hit_from_latest_ray_cell(self):
        current_state = {"basis_ids": ["basis::near"]}
        ray_sample = {
            "ray_sample_record_id": "ray::1",
            "image_shape": [2, 2],
            "ray_target_points_world_3d": [
                [-2.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],
                [2.0, 0.0, 0.0],
                [4.0, 0.0, 0.0],
            ],
        }
        target = target_basis_from_image_xy(
            valid_request(source_image_xy=[0.25, 0.25]),
            current_state=current_state,
            bases=[basis("basis::near", [-2.0, 0.0, 0.0])],
            ray_sample_record=ray_sample,
        )
        self.assertEqual(["basis::near"], target["target_basis_ids"])
        self.assertEqual("direct", target["targeting_confidence"])
        self.assertEqual("ray::1", target["source_ray_sample_record_id"])

    def test_targets_nearest_basis_when_ray_cell_misses_support(self):
        current_state = {"basis_ids": ["basis::near", "basis::far"]}
        ray_sample = {
            "ray_sample_record_id": "ray::1",
            "image_shape": [1, 1],
            "ray_target_points_world_3d": [[3.0, 0.0, 0.0]],
        }
        target = target_basis_from_image_xy(
            valid_request(source_image_xy=[0.5, 0.5]),
            current_state=current_state,
            bases=[
                basis("basis::near", [2.6, 0.0, 0.0], radius=0.2),
                basis("basis::far", [-10.0, 0.0, 0.0], radius=0.2),
            ],
            ray_sample_record=ray_sample,
        )
        self.assertEqual(["basis::near"], target["target_basis_ids"])
        self.assertEqual("low", target["targeting_confidence"])

    def test_fails_when_state_references_unknown_basis(self):
        with self.assertRaisesRegex(ValueError, "current state references missing basis"):
            target_basis_from_image_xy(
                valid_request(source_image_xy=[0.5, 0.5]),
                current_state={"basis_ids": ["basis::missing"]},
                bases=[basis("basis::near", [0.0, 0.0, 0.0])],
                ray_sample_record={
                    "ray_sample_record_id": "ray::1",
                    "image_shape": [1, 1],
                    "ray_target_points_world_3d": [[0.0, 0.0, 0.0]],
                },
            )


class ImplicitInteractionProjectionTests(unittest.TestCase):
    def test_signed_amplitude_and_fractional_schedule_are_canonical(self):
        self.assertEqual(0.4, canonical_implicit_signed_amplitude(valid_request(amplitude=0.4)))
        self.assertEqual(
            -0.4,
            canonical_implicit_signed_amplitude(
                valid_request(tool="implicit_local_dampen", amplitude=0.4)
            ),
        )
        self.assertEqual([1.0, 1.0, 0.25], implicit_duration_schedule_weights(2.25))
        self.assertAlmostEqual(2.25, sum(implicit_duration_schedule_weights(2.25)))

    def test_local_control_weights_are_smooth_normalized_and_support_bounded(self):
        weights = build_implicit_local_control_weights(
            target_world_3d=[0.0, 0.0, 0.0],
            bases=[
                basis("basis::a", [0.0, 0.0, 0.0]),
                basis("basis::b", [1.0, 0.0, 0.0]),
                basis("basis::outside", [4.0, 0.0, 0.0]),
            ],
            radius_world=1.5,
        )

        self.assertEqual(["basis::a", "basis::b"], list(weights["kappa_by_basis"]))
        self.assertGreater(weights["kappa_by_basis"]["basis::a"], weights["kappa_by_basis"]["basis::b"])
        self.assertAlmostEqual(1.0, sum(weights["normalized_weights_by_basis"].values()))
        self.assertEqual(2, len(weights["basis_geometry"]))

    def test_local_control_weights_fail_closed_when_support_is_not_well_conditioned(self):
        with self.assertRaisesRegex(ValueError, "at least two positive-support bases"):
            build_implicit_local_control_weights(
                target_world_3d=[0.0, 0.0, 0.0],
                bases=[basis("basis::only", [0.0, 0.0, 0.0])],
                radius_world=1.5,
            )

    def test_pending_descriptor_materializes_ordered_fractional_raw_projections(self):
        descriptor = build_implicit_pending_control_descriptor(
            valid_request(duration_ticks=2.25, amplitude=0.4),
            target={"target_world_3d": [0.0, 0.0, 0.0]},
            bases=[
                basis("basis::a", [0.0, 0.0, 0.0]),
                basis("basis::b", [1.0, 0.0, 0.0]),
                basis("basis::outside", [4.0, 0.0, 0.0]),
            ],
            accepted_sequence=7,
            start_tick=3,
        )

        self.assertEqual("projection-frame::1", descriptor["source_projection_frame_id"])
        self.assertEqual("state::1", descriptor["source_state_id"])
        self.assertEqual("ray::1", descriptor["source_ray_sample_record_id"])
        self.assertEqual("implicit-interaction-audit::cmd::implicit::viewer-1", descriptor["audit_id"])
        self.assertEqual(7, descriptor["accepted_sequence"])
        self.assertEqual(3, descriptor["start_tick"])
        self.assertEqual([1.0, 1.0, 0.25], descriptor["schedule_weights"])
        first = materialize_implicit_raw_control_projection(descriptor, schedule_index=0)
        last = materialize_implicit_raw_control_projection(descriptor, schedule_index=2)
        self.assertAlmostEqual(0.4, sum(channels["density"] for channels in first.values()))
        self.assertAlmostEqual(0.1, sum(channels["density"] for channels in last.values()))

    def test_pending_descriptor_preserves_dampen_sign_and_zero_noop(self):
        bases = [
            basis("basis::a", [0.0, 0.0, 0.0]),
            basis("basis::b", [1.0, 0.0, 0.0]),
        ]
        dampen = build_implicit_pending_control_descriptor(
            valid_request(tool="implicit_local_dampen", amplitude=0.4),
            target={"target_world_3d": [0.0, 0.0, 0.0]},
            bases=bases,
            accepted_sequence=1,
            start_tick=2,
        )
        zero = build_implicit_pending_control_descriptor(
            valid_request(request_id="viewer-zero", amplitude=0.0),
            target={"target_world_3d": [0.0, 0.0, 0.0]},
            bases=bases,
            accepted_sequence=2,
            start_tick=2,
        )

        projection = materialize_implicit_raw_control_projection(dampen, schedule_index=0)
        self.assertAlmostEqual(-0.4, sum(channels["density"] for channels in projection.values()))
        self.assertEqual({}, materialize_implicit_raw_control_projection(zero, schedule_index=0))

    def test_tool_projection_and_audit(self):
        target = {
            "target_basis_ids": ["basis::a"],
            "target_world_3d": [0.0, 0.0, 0.0],
            "targeting_confidence": "direct",
            "source_ray_sample_record_id": "ray::1",
            "target_ray_id": "ray::1",
            "target_ray_index": 0,
            "target_ray_direction_world_3d": [0.0, 1.0, 0.0],
            "target_hit_depth": 3.0,
            "target_structure_id": "implicit-observed-structure::0",
            "target_hit_source": "observation_channel",
        }
        projection = implicit_request_to_input_projection(valid_request(), target)
        self.assertEqual({"basis::a": {"density": 0.35}}, projection)
        audit = build_implicit_interaction_audit(
            valid_request(),
            target=target,
            source_state_id="state::1",
            input_projection=projection,
        )
        self.assertEqual("implicit_interaction_audit", audit["schema"])
        self.assertEqual("accepted", audit["status"])
        self.assertEqual("cmd::implicit::viewer-1", audit["command_id"])
        self.assertEqual(["basis::a"], audit["target_basis_ids"])
        self.assertEqual(0, audit["target_ray_index"])
        self.assertEqual(3.0, audit["target_hit_depth"])
        self.assertEqual("implicit-observed-structure::0", audit["target_structure_id"])
        self.assertIsNone(audit["result_state_id"])

    def test_audit_carries_exact_lineage_and_raw_realized_application_lifecycle(self):
        request = valid_request(duration_ticks=1.25, amplitude=0.4)
        target = {
            "target_basis_ids": ["basis::a"],
            "target_world_3d": [0.0, 0.0, 0.0],
            "targeting_confidence": "direct",
            "source_ray_sample_record_id": "ray::1",
            "target_ray_id": "ray::1",
            "target_ray_index": 0,
            "target_ray_direction_world_3d": [0.0, 1.0, 0.0],
            "target_hit_depth": 3.0,
            "target_structure_id": None,
            "target_hit_source": "ray_integral",
        }
        descriptor = build_implicit_pending_control_descriptor(
            request,
            target=target,
            bases=[
                basis("basis::a", [0.0, 0.0, 0.0]),
                basis("basis::b", [1.0, 0.0, 0.0]),
            ],
            accepted_sequence=2,
            start_tick=2,
        )
        raw_first = materialize_implicit_raw_control_projection(descriptor, schedule_index=0)
        audit = build_implicit_interaction_audit(
            request,
            target=target,
            source_state_id="state::1",
            input_projection=raw_first,
            control_descriptor=descriptor,
        )

        self.assertEqual("projection-frame::1", audit["source_projection_frame_id"])
        self.assertEqual("state::1", audit["source_state_id"])
        self.assertEqual("ray::1", audit["source_ray_sample_record_id"])
        self.assertEqual(0.4, audit["amplitude_magnitude"])
        self.assertEqual(0.4, audit["signed_amplitude"])
        self.assertEqual([1.0, 0.25], audit["schedule_weights"])
        self.assertEqual(["basis::a", "basis::b"], audit["target_basis_ids"])
        self.assertEqual([], audit["applications"])

        in_progress = record_implicit_interaction_application(
            audit,
            tick=2,
            schedule_index=0,
            raw_input_projection=raw_first,
            realized_input_projection=raw_first,
        )
        self.assertEqual("in_progress", in_progress["status"])
        self.assertEqual(raw_first, in_progress["applications"][0]["raw_input_projection"])
        raw_last = materialize_implicit_raw_control_projection(descriptor, schedule_index=1)
        applied = record_implicit_interaction_application(
            in_progress,
            tick=3,
            schedule_index=1,
            raw_input_projection=raw_last,
            realized_input_projection=raw_last,
        )
        self.assertEqual("applied", applied["status"])
        self.assertEqual(raw_last, applied["applications"][1]["realized_input_projection"])

    def test_dampen_projection_is_negative(self):
        projection = implicit_request_to_input_projection(
            valid_request(tool="implicit_local_dampen", amplitude=0.4),
            {"target_basis_ids": ["basis::a"]},
        )
        self.assertEqual({"basis::a": {"density": -0.4}}, projection)

    def test_directional_push_includes_direction_components(self):
        projection = implicit_request_to_input_projection(
            valid_request(tool="implicit_directional_push", amplitude=0.6, source_vector_image=[0.25, -0.5]),
            {"target_basis_ids": ["basis::a", "basis::b"]},
        )
        self.assertEqual(0.3, projection["basis::a"]["density"])
        self.assertIn("direction_x", projection["basis::a"])
        self.assertIn("direction_y", projection["basis::b"])

    def test_refine_probe_has_empty_projection(self):
        projection = implicit_request_to_input_projection(
            valid_request(tool="implicit_refine_probe"),
            {"target_basis_ids": ["basis::a"]},
        )
        self.assertEqual({}, projection)


if __name__ == "__main__":
    unittest.main()
