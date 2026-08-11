import unittest

from world_engine.field_signature_authoring import (
    built_in_signature_templates,
    build_field_signature_instance,
    compile_field_signature_template,
    compile_field_signature_to_implicit_basis,
    summarize_field_signature_evidence,
)
from world_engine.implicit_field import build_implicit_field_state, validate_implicit_field_basis, validate_implicit_field_state
from world_engine.implicit_field_runtime import advance_implicit_field_state
from world_engine.signature_scene_runtime import build_implicit_signature_scene, build_signature_scene


class ImplicitFieldRuntimeTests(unittest.TestCase):
    def instance_for(self, template_name: str):
        template = built_in_signature_templates()[template_name]
        compilation = compile_field_signature_template(template, run_id="implicit-test", instance_index=1)
        evidence = summarize_field_signature_evidence(
            template=template,
            field_states=build_signature_scene(
                source_package_name="source-a",
                source_package_digest="digest-a",
                case_type="authored_full_signature_scene",
                run_id="implicit-test",
                ticks=40,
            )["field_states"],
            property_records=[],
            baseline_case_id="case::baseline",
        )
        evidence["instance_id"] = compilation["instance_id"]
        return template, build_field_signature_instance(
            template,
            compilation,
            evidence,
            run_id="implicit-test",
            region_id="world-region::implicit-test::0",
        )

    def test_field_signatures_compile_to_matching_implicit_basis_records(self):
        expected = {
            "surface_barrier": {"signed_boundary"},
            "channel_conduit": {"density_lobe", "absorption_region"},
            "source_emitter": {"emitter"},
        }

        for template_name, expected_kinds in expected.items():
            template, instance = self.instance_for(template_name)
            bases = compile_field_signature_to_implicit_basis(
                template,
                instance,
                run_id="implicit-test",
                region_id="world-region::implicit-test::0",
                center_world_3d=[0.0, 0.0, 0.0],
            )
            self.assertTrue(bases)
            self.assertTrue(expected_kinds.intersection({basis["basis_kind"] for basis in bases}))
            for basis in bases:
                validate_implicit_field_basis(basis)
                self.assertFalse(basis["is_authority_state"])
                self.assertEqual(basis["source_signature_template_id"], template["template_id"])
                self.assertEqual(basis["source_signature_instance_id"], instance["instance_id"])
                self.assertIn(instance["instance_id"], basis["source_record_ids"])

        emitter_template, emitter_instance = self.instance_for("source_emitter")
        emitter_bases = compile_field_signature_to_implicit_basis(
            emitter_template,
            emitter_instance,
            run_id="implicit-test",
            region_id="world-region::implicit-test::0",
            center_world_3d=[0.0, 0.0, 0.0],
        )
        self.assertTrue(any(basis["omega"] != 0.0 for basis in emitter_bases))

    def test_build_implicit_signature_scene_carries_basis_and_state(self):
        scene = build_implicit_signature_scene(
            source_package_name="source-a",
            source_package_digest="digest-a",
            case_type="implicit_surface_boundary",
            run_id="implicit-scene-test",
            ticks=4,
        )

        self.assertEqual(scene["schema"], "implicit_field_signature_scene")
        self.assertTrue(scene["implicit_basis_records"])
        self.assertTrue(scene["implicit_field_state"])
        for basis in scene["implicit_basis_records"]:
            validate_implicit_field_basis(basis)
        validate_implicit_field_state(scene["implicit_field_state"])

    def test_low_rank_update_preserves_basis_ids_and_reports_sparse_cost(self):
        scene = build_implicit_signature_scene(
            source_package_name="source-a",
            source_package_digest="digest-a",
            case_type="implicit_emitter_volume",
            run_id="implicit-runtime-test",
            ticks=4,
        )
        state = scene["implicit_field_state"]
        bases = scene["implicit_basis_records"]
        advanced = advance_implicit_field_state(
            state,
            bases,
            input_projection={state["basis_ids"][0]: {"density": 0.25}},
            decay=0.96,
        )

        validate_implicit_field_state(advanced)
        self.assertEqual(set(advanced["basis_ids"]), set(state["basis_ids"]))
        self.assertFalse(advanced["runtime_cost_summary"]["dense_volume_used"])
        self.assertEqual(advanced["runtime_cost_summary"]["basis_count"], len(state["basis_ids"]))
        self.assertIn("coefficient_clamp_saturation_ratio", advanced["runtime_cost_summary"])
        self.assertEqual(
            advanced["energy_summary"]["density_response"]["raw_user_projection"],
            {state["basis_ids"][0]: {"density": 0.25}},
        )
        self.assertEqual(advanced["energy_summary"]["density_response"]["raw_feedback_projection"], {})

    def test_split_user_and_feedback_inputs_are_applied_in_order_and_reported(self):
        scene = build_implicit_signature_scene(
            source_package_name="source-a",
            source_package_digest="digest-a",
            case_type="implicit_emitter_volume",
            run_id="implicit-runtime-split-input-test",
            ticks=4,
        )
        state = scene["implicit_field_state"]
        basis_id = state["basis_ids"][0]

        advanced = advance_implicit_field_state(
            state,
            scene["implicit_basis_records"],
            user_input_projection={basis_id: {"density": 0.2}},
            feedback_input_projection={basis_id: {"density": -0.1}},
        )

        self.assertAlmostEqual(advanced["basis_coefficients"][basis_id]["density"], 1.06)
        response = advanced["energy_summary"]["density_response"]
        self.assertEqual(response["raw_user_projection"], {basis_id: {"density": 0.2}})
        self.assertEqual(response["realized_user_projection"], {basis_id: {"density": 0.2}})
        self.assertEqual(response["raw_feedback_projection"], {basis_id: {"density": -0.1}})
        self.assertEqual(response["realized_feedback_projection"], {basis_id: {"density": -0.1}})
        self.assertEqual(response["merged_realized_projection"], {basis_id: {"density": 0.1}})
        self.assertEqual([ledger["scope_id"] for ledger in response["ledgers"]], ["fixed_scene"])
        ledger = response["ledgers"][0]
        self.assertGreater(ledger["i_user"], 0.0)
        self.assertLess(ledger["i_feedback"], 0.0)
        self.assertEqual(ledger["d_clip"], 0.0)

    def test_density_caps_user_then_feedback_against_the_current_stage(self):
        scene = build_implicit_signature_scene(
            source_package_name="source-a",
            source_package_digest="digest-a",
            case_type="implicit_channel_conduit",
            run_id="implicit-runtime-density-cap-test",
            ticks=4,
        )
        state = scene["implicit_field_state"]
        first_basis, second_basis = state["basis_ids"]

        advanced = advance_implicit_field_state(
            state,
            scene["implicit_basis_records"],
            user_input_projection={
                first_basis: {"density": -2.0},
                second_basis: {"density": 0.25},
            },
            feedback_input_projection={
                first_basis: {"density": 0.25},
                second_basis: {"density": -2.0},
            },
        )

        self.assertAlmostEqual(advanced["basis_coefficients"][first_basis]["density"], 0.25)
        self.assertAlmostEqual(advanced["basis_coefficients"][second_basis]["density"], 0.0)
        response = advanced["energy_summary"]["density_response"]
        self.assertEqual(
            response["realized_user_projection"],
            {
                first_basis: {"density": -0.96},
                second_basis: {"density": 0.25},
            },
        )
        self.assertEqual(
            response["realized_feedback_projection"],
            {
                first_basis: {"density": 0.25},
                second_basis: {"density": -1.21},
            },
        )

    def test_density_input_fails_closed_when_the_post_coupling_baseline_is_negative(self):
        scene = build_implicit_signature_scene(
            source_package_name="source-a",
            source_package_digest="digest-a",
            case_type="implicit_emitter_volume",
            run_id="implicit-runtime-negative-envelope-test",
            ticks=4,
        )
        original = scene["implicit_field_state"]
        basis_id = original["basis_ids"][0]
        state = build_implicit_field_state(
            implicit_field_state_id=original["implicit_field_state_id"],
            tick=original["tick"],
            basis_ids=original["basis_ids"],
            basis_layout_digest=original["basis_layout_digest"],
            basis_spatial_index_digest=original["basis_spatial_index_digest"],
            basis_coefficients={basis_id: {"density": -1.0}},
            sparse_coupling_edges=original["sparse_coupling_edges"],
            background_model=original["background_model"],
            active_local_patch_ids=original["active_local_patch_ids"],
            validity_region_world=original["validity_region_world"],
            energy_summary=original["energy_summary"],
            source_record_ids=original["source_record_ids"],
            authority_status=original["authority_status"],
        )

        with self.assertRaisesRegex(ValueError, "non-negative post-coupling baseline"):
            advance_implicit_field_state(
                state,
                scene["implicit_basis_records"],
                user_input_projection={basis_id: {"density": 0.1}},
            )

    def test_global_and_local_ledgers_split_internal_and_cross_scope_coupling(self):
        scene = build_implicit_signature_scene(
            source_package_name="source-a",
            source_package_digest="digest-a",
            case_type="implicit_channel_conduit",
            run_id="implicit-runtime-ledger-test",
            ticks=4,
        )
        original = scene["implicit_field_state"]
        inside_basis, outside_basis = original["basis_ids"]
        state = build_implicit_field_state(
            implicit_field_state_id=original["implicit_field_state_id"],
            tick=original["tick"],
            basis_ids=original["basis_ids"],
            basis_layout_digest=original["basis_layout_digest"],
            basis_spatial_index_digest=original["basis_spatial_index_digest"],
            basis_coefficients={
                inside_basis: {"density": 1.0},
                outside_basis: {"density": 2.0},
            },
            sparse_coupling_edges=[
                {"from_basis_id": outside_basis, "to_basis_id": inside_basis, "weight": 0.01}
            ],
            background_model=original["background_model"],
            active_local_patch_ids=original["active_local_patch_ids"],
            validity_region_world=original["validity_region_world"],
            energy_summary=original["energy_summary"],
            source_record_ids=original["source_record_ids"],
            authority_status=original["authority_status"],
        )

        advanced = advance_implicit_field_state(
            state,
            scene["implicit_basis_records"],
            local_energy_scopes={"local-inside": {inside_basis: 1.0, outside_basis: 0.0}},
        )

        ledgers = {
            ledger["scope_id"]: ledger
            for ledger in advanced["energy_summary"]["density_response"]["ledgers"]
        }
        self.assertEqual(set(ledgers), {"fixed_scene", "local-inside"})
        self.assertEqual(ledgers["fixed_scene"]["f_boundary_proxy"], 0.0)
        self.assertGreater(ledgers["fixed_scene"]["x_internal"], 0.0)
        self.assertEqual(ledgers["local-inside"]["x_internal"], 0.0)
        self.assertGreater(ledgers["local-inside"]["f_boundary_proxy"], 0.0)
        self.assertEqual(
            ledgers["local-inside"]["kappa"],
            {inside_basis: 1.0, outside_basis: 0.0},
        )
        density_weight = float(scene["implicit_basis_records"][0]["channel_weights"]["density"])
        self.assertAlmostEqual(ledgers["local-inside"]["energy_before"], 0.5 * density_weight**2)
        for ledger in ledgers.values():
            self.assertLessEqual(abs(ledger["residual"]), ledger["residual_tolerance"])
            self.assertAlmostEqual(
                ledger["energy_after"] - ledger["energy_before"],
                ledger["x_internal"]
                + ledger["f_boundary_proxy"]
                + ledger["i_user"]
                + ledger["i_feedback"]
                - ledger["d_decay"]
                - ledger["d_clip"],
            )

    def test_density_ledger_accounts_for_coefficient_clipping(self):
        scene = build_implicit_signature_scene(
            source_package_name="source-a",
            source_package_digest="digest-a",
            case_type="implicit_emitter_volume",
            run_id="implicit-runtime-clip-ledger-test",
            ticks=4,
        )
        basis_id = scene["implicit_field_state"]["basis_ids"][0]

        advanced = advance_implicit_field_state(
            scene["implicit_field_state"],
            scene["implicit_basis_records"],
            user_input_projection={basis_id: {"density": 10.0}},
            coefficient_abs_max=1.0,
            clamp_saturation_ratio_max=1.0,
        )

        ledger = advanced["energy_summary"]["density_response"]["ledgers"][0]
        self.assertGreater(ledger["i_user"], 0.0)
        self.assertGreater(ledger["d_clip"], 0.0)
        self.assertLessEqual(abs(ledger["residual"]), ledger["residual_tolerance"])

    def test_runtime_rejects_invalid_or_over_budget_local_energy_scopes(self):
        scene = build_implicit_signature_scene(
            source_package_name="source-a",
            source_package_digest="digest-a",
            case_type="implicit_emitter_volume",
            run_id="implicit-runtime-scope-budget-test",
            ticks=4,
        )
        basis_id = scene["implicit_field_state"]["basis_ids"][0]

        with self.assertRaisesRegex(ValueError, "finite and non-negative"):
            advance_implicit_field_state(
                scene["implicit_field_state"],
                scene["implicit_basis_records"],
                local_energy_scopes={"bad-scope": {basis_id: -0.1}},
            )
        with self.assertRaisesRegex(ValueError, "scope budget"):
            advance_implicit_field_state(
                scene["implicit_field_state"],
                scene["implicit_basis_records"],
                local_energy_scopes={f"scope-{index}": {basis_id: 1.0} for index in range(65)},
            )

    def test_runtime_rejects_projection_channels_not_declared_by_the_basis(self):
        scene = build_implicit_signature_scene(
            source_package_name="source-a",
            source_package_digest="digest-a",
            case_type="implicit_emitter_volume",
            run_id="implicit-runtime-channel-test",
            ticks=4,
        )
        basis_id = scene["implicit_field_state"]["basis_ids"][0]

        with self.assertRaisesRegex(ValueError, "undeclared channel"):
            advance_implicit_field_state(
                scene["implicit_field_state"],
                scene["implicit_basis_records"],
                user_input_projection={basis_id: {"not-a-channel": 0.1}},
            )

    def test_runtime_rejects_negative_decay_outside_the_passive_contraction_envelope(self):
        scene = build_implicit_signature_scene(
            source_package_name="source-a",
            source_package_digest="digest-a",
            case_type="implicit_emitter_volume",
            run_id="implicit-runtime-decay-envelope-test",
            ticks=4,
        )

        with self.assertRaisesRegex(ValueError, "decay must be finite and between"):
            advance_implicit_field_state(
                scene["implicit_field_state"],
                scene["implicit_basis_records"],
                decay=-0.01,
            )

    def test_runtime_rejects_non_finite_coefficient_and_clamp_limits(self):
        scene = build_implicit_signature_scene(
            source_package_name="source-a",
            source_package_digest="digest-a",
            case_type="implicit_emitter_volume",
            run_id="implicit-runtime-limit-envelope-test",
            ticks=4,
        )

        for kwargs in (
            {"coefficient_abs_max": float("nan")},
            {"clamp_saturation_ratio_max": float("inf")},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(ValueError, "must be finite"):
                    advance_implicit_field_state(
                        scene["implicit_field_state"],
                        scene["implicit_basis_records"],
                        **kwargs,
                    )

    def test_runtime_rejects_projection_merge_overflow_before_audit_readback(self):
        scene = build_implicit_signature_scene(
            source_package_name="source-a",
            source_package_digest="digest-a",
            case_type="implicit_emitter_volume",
            run_id="implicit-runtime-projection-overflow-test",
            ticks=4,
        )
        basis_id = scene["implicit_field_state"]["basis_ids"][0]

        with self.assertRaisesRegex(ValueError, "projection merge must be finite"):
            advance_implicit_field_state(
                scene["implicit_field_state"],
                scene["implicit_basis_records"],
                user_input_projection={basis_id: {"absorption": 1e308}},
                feedback_input_projection={basis_id: {"absorption": 1e308}},
                clamp_saturation_ratio_max=1.0,
            )

    def test_runtime_rejects_bad_coupling_and_excessive_clamp_saturation(self):
        scene = build_implicit_signature_scene(
            source_package_name="source-a",
            source_package_digest="digest-a",
            case_type="implicit_channel_conduit",
            run_id="implicit-runtime-test",
            ticks=4,
        )
        state = dict(scene["implicit_field_state"])
        state["sparse_coupling_edges"] = [
            {"from_basis_id": state["basis_ids"][0], "to_basis_id": "missing", "weight": 0.01}
        ]
        with self.assertRaises(ValueError):
            advance_implicit_field_state(state, scene["implicit_basis_records"])

        state = dict(scene["implicit_field_state"])
        state["sparse_coupling_edges"] = [
            {"from_basis_id": state["basis_ids"][0], "to_basis_id": state["basis_ids"][0], "weight": 0.08}
        ]
        with self.assertRaises(ValueError):
            advance_implicit_field_state(state, scene["implicit_basis_records"], decay=0.96)

        state = dict(scene["implicit_field_state"])
        with self.assertRaises(ValueError):
            advance_implicit_field_state(
                state,
                scene["implicit_basis_records"],
                input_projection={basis_id: {"density": 99.0} for basis_id in state["basis_ids"]},
                coefficient_abs_max=1.0,
                clamp_saturation_ratio_max=0.0,
            )


if __name__ == "__main__":
    unittest.main()
