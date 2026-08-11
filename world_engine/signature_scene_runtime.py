from __future__ import annotations

import hashlib
import json
from typing import Any

from world_engine.field_signature_authoring import (
    built_in_signature_templates,
    build_field_signature_instance,
    compile_field_signature_to_implicit_basis,
    compile_field_signature_template,
    summarize_field_signature_evidence,
    validate_field_signature_instance,
)
from world_engine.implicit_field import build_basis_spatial_index, build_implicit_field_state


LEGACY_SIGNATURE_TEMPLATE_NAMES = ("surface_barrier", "channel_conduit", "source_emitter")
EXPANDED_SIGNATURE_TEMPLATE_NAMES = (
    "surface_layer",
    "surface_barrier",
    "channel_conduit",
    "source_emitter",
    "sink_absorber",
    "container_envelope",
    "machine_coupler",
)
EXPANSION_CASE_TYPES = {
    "expanded_template_compilation_scene",
    "refinement_reveal_scene",
    "interactive_authoring_response_scene",
}


def _stable_variation(source_package_name: str, source_package_digest: str) -> int:
    encoded = f"{source_package_name}|{source_package_digest}".encode("utf-8")
    return int(hashlib.sha256(encoded).hexdigest()[:8], 16)


def _field_state(
    run_id: str,
    tick: int,
    *,
    source_package_name: str,
    source_package_digest: str,
    grid_shape: tuple[int, int] = (32, 32),
) -> dict[str, Any]:
    height, width = grid_shape
    grid = [[0.0 for _ in range(width)] for _ in range(height)]
    variation = _stable_variation(source_package_name, source_package_digest)
    y_shift = variation % 3 - 1
    x_shift = (variation // 3) % 3 - 1
    amplitude_shift = ((variation // 9) % 5) * 0.01
    for y in range(height // 2 - 2, height // 2 + 2):
        for x in range(4, width - 4):
            yy = y + y_shift
            xx = x + x_shift
            if 0 <= yy < height and 0 <= xx < width:
                grid[yy][xx] = 0.90 + amplitude_shift
    for y in range(height // 2 - 5, height // 2 + 5):
        yy = y + y_shift
        x = width // 2 + x_shift
        if 0 <= yy < height and 0 <= x < width:
            grid[yy][x] = max(grid[yy][x], 0.72 + amplitude_shift)
    source_x = width // 4
    source_y = height // 2 + y_shift
    if 0 <= source_y < height and 0 <= source_x < width:
        grid[source_y][source_x] = 1.0
    return {
        "field_state_id": f"field-state::{run_id}::{tick}",
        "id": f"field-state::{run_id}::{tick}",
        "tick": tick,
        "channels": {"pattern": grid},
        "energy": sum(abs(value) for row in grid for value in row),
        "source_record_ids": [f"field_wave_step::{run_id}::{tick}"],
        "payload": {
            "coordinate_frame": {
                "grid_shape": [height, width],
                "world_bounds": [[-16.0, -16.0], [16.0, 16.0]],
            },
            "signature_scene": True,
            "source_package_name": source_package_name,
            "source_package_digest": source_package_digest,
            "source_package_variation": variation,
        },
    }


def _property_record(run_id: str, tick: int) -> dict[str, Any]:
    return {
        "id": f"property-signature::{run_id}::{tick}",
        "record_id": f"property-signature::{run_id}::{tick}",
        "payload": {
            "channel": "pattern",
            "rigidity": 0.68,
            "permeability": 0.28,
            "transport": 0.62,
            "spectral_response": 0.71,
            "source_amplitude": 0.46,
            "sink_rate": 0.39,
            "damping": 0.52,
            "containment": 0.58,
            "boundary_integrity": 0.66,
            "coupling": 0.44,
            "budget_response": 0.83,
            "surface_gradient": 0.48,
            "frequency_response": {"low": 0.25, "mid": 0.82, "high": 0.54},
        },
    }


def _selected_templates(case_type: str) -> list[str]:
    if case_type in EXPANSION_CASE_TYPES:
        return list(EXPANDED_SIGNATURE_TEMPLATE_NAMES)
    if case_type == "authored_surface_barrier_scene":
        return ["surface_barrier"]
    return list(LEGACY_SIGNATURE_TEMPLATE_NAMES)


def _selected_implicit_templates(case_type: str) -> list[str]:
    if case_type == "implicit_surface_boundary":
        return ["surface_barrier"]
    if case_type == "implicit_channel_conduit":
        return ["channel_conduit"]
    if case_type == "implicit_emitter_volume":
        return ["source_emitter"]
    return ["surface_barrier", "channel_conduit", "source_emitter"]


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def build_signature_scene(
    *,
    source_package_name: str,
    source_package_digest: str | None = None,
    case_type: str,
    run_id: str,
    ticks: int = 40,
) -> dict[str, Any]:
    package_digest = source_package_digest or hashlib.sha256(source_package_name.encode("utf-8")).hexdigest()
    templates_by_name = built_in_signature_templates()
    field_states = [
        _field_state(
            run_id,
            tick,
            source_package_name=source_package_name,
            source_package_digest=package_digest,
        )
        for tick in range(1, ticks + 1)
    ]
    property_records = [_property_record(run_id, 1)]
    templates = [templates_by_name[name] for name in _selected_templates(case_type)]
    compilation_records: list[dict[str, Any]] = []
    evidence_records: list[dict[str, Any]] = []
    instances: list[dict[str, Any]] = []
    for index, template in enumerate(templates, start=1):
        compilation = compile_field_signature_template(template, run_id=run_id, instance_index=index)
        evidence = summarize_field_signature_evidence(
            template=template,
            field_states=field_states,
            property_records=property_records,
            baseline_case_id=f"case::{source_package_name}::passive_signature_scene",
        )
        evidence["instance_id"] = compilation["instance_id"]
        instance = build_field_signature_instance(
            template,
            compilation,
            evidence,
            run_id=run_id,
            region_id=f"world-region::{run_id}::0",
        )
        compilation_records.append(compilation)
        evidence_records.append(evidence)
        instances.append(instance)
    return {
        "schema": "field_signature_scene_v1",
        "source_package_name": source_package_name,
        "source_package_digest": package_digest,
        "case_type": case_type,
        "run_id": run_id,
        "field_states": field_states,
        "property_records": property_records,
        "field_signature_templates": templates,
        "field_signature_compilation_records": compilation_records,
        "field_signature_evidence_records": evidence_records,
        "field_signature_instances": instances,
        "source_record_ids": [f"source_package::{source_package_name}::{package_digest}", f"field_wave_step::{run_id}::{ticks}"],
        "is_authority_state": False,
    }


def build_implicit_signature_scene(
    *,
    source_package_name: str,
    source_package_digest: str | None = None,
    case_type: str,
    run_id: str,
    ticks: int = 64,
) -> dict[str, Any]:
    evidence_ticks = max(ticks, 40)
    base_scene = build_signature_scene(
        source_package_name=source_package_name,
        source_package_digest=source_package_digest,
        case_type="authored_full_signature_scene",
        run_id=run_id,
        ticks=evidence_ticks,
    )
    selected_names = set(_selected_implicit_templates(case_type))
    templates = [
        template
        for template in base_scene["field_signature_templates"]
        if template["name"] in selected_names
    ]
    instances_by_template = {
        str(instance["template_name"]): instance
        for instance in base_scene["field_signature_instances"]
    }
    centers = {
        "surface_barrier": [-2.5, 0.0, 0.0],
        "channel_conduit": [0.0, 0.0, 0.0],
        "source_emitter": [3.0, 0.2, 0.0],
    }
    implicit_basis_records: list[dict[str, Any]] = []
    for template in templates:
        instance = instances_by_template[str(template["name"])]
        implicit_basis_records.extend(
            compile_field_signature_to_implicit_basis(
                template,
                instance,
                run_id=run_id,
                region_id=f"world-region::{run_id}::implicit",
                center_world_3d=centers[str(template["name"])],
            )
        )
    spatial_index = build_basis_spatial_index(implicit_basis_records)
    basis_ids = [basis["basis_id"] for basis in implicit_basis_records]
    basis_layout_digest = _digest(
        [
            {
                "basis_id": basis["basis_id"],
                "basis_kind": basis["basis_kind"],
                "basis_profile": basis["basis_profile"],
                "center_world_3d": basis["center_world_3d"],
                "basis_axes": basis["basis_axes"],
                "radius_world": basis["radius_world"],
                "coordinate_frame_3d": basis["coordinate_frame_3d"],
                "support_region_world": basis["support_region_world"],
            }
            for basis in sorted(implicit_basis_records, key=lambda item: item["basis_id"])
        ]
    )
    basis_coefficients = {
        basis["basis_id"]: {
            channel: 1.0
            for channel, weight in basis["channel_weights"].items()
            if abs(float(weight)) > 0.0
        }
        for basis in implicit_basis_records
    }
    validity_region = {
        "min": [min(float(basis["support_region_world"]["min"][axis]) for basis in implicit_basis_records) for axis in range(3)],
        "max": [max(float(basis["support_region_world"]["max"][axis]) for basis in implicit_basis_records) for axis in range(3)],
    }
    implicit_state = build_implicit_field_state(
        implicit_field_state_id=f"implicit-field-state::{run_id}::1",
        tick=1,
        basis_ids=basis_ids,
        basis_layout_digest=basis_layout_digest,
        basis_spatial_index_digest=spatial_index["basis_spatial_index_digest"],
        basis_coefficients=basis_coefficients,
        sparse_coupling_edges=[],
        background_model={"kind": "zero"},
        active_local_patch_ids=[],
        validity_region_world=validity_region,
        energy_summary={"total_abs_coefficient": sum(abs(float(value)) for channels in basis_coefficients.values() for value in channels.values())},
        source_record_ids=[*basis_ids, *base_scene["source_record_ids"]],
    )
    return {
        "schema": "implicit_field_signature_scene",
        "source_package_name": base_scene["source_package_name"],
        "source_package_digest": base_scene["source_package_digest"],
        "case_type": case_type,
        "run_id": run_id,
        "field_signature_templates": templates,
        "field_signature_instances": [instances_by_template[str(template["name"])] for template in templates],
        "implicit_basis_records": implicit_basis_records,
        "implicit_basis_spatial_index": spatial_index,
        "implicit_field_state": implicit_state,
        "observer_seed": {
            "observer_id": "observer::implicit-pinhole",
            "camera_pose": {"origin": [0.0, -9.0, 3.0], "look_at": [0.0, 0.0, 0.0], "up": [0.0, 0.0, 1.0]},
            "image_shape": [32, 24],
        },
        "source_record_ids": [*base_scene["source_record_ids"], implicit_state["implicit_field_state_id"]],
        "is_authority_state": False,
    }


def validate_signature_scene(scene: dict[str, Any]) -> bool:
    try:
        if scene.get("schema") != "field_signature_scene_v1":
            return False
        if not scene.get("source_package_name") or not scene.get("source_package_digest"):
            return False
        evidence_records = list(scene.get("field_signature_evidence_records", []))
        compilation_records = list(scene.get("field_signature_compilation_records", []))
        templates = list(scene.get("field_signature_templates", []))
        if not evidence_records or not compilation_records or not templates:
            return False
        for instance in scene.get("field_signature_instances", []):
            validate_field_signature_instance(instance, evidence_records, compilation_records, templates)
        return bool(scene.get("field_signature_instances"))
    except ValueError:
        return False


def build_signature_refinement_reveals(scene: dict[str, Any]) -> list[dict[str, Any]]:
    if not validate_signature_scene(scene):
        raise ValueError("signature scene must validate before building refinement reveals")
    evidence_by_id = {
        str(record.get("evidence_id")): record
        for record in scene.get("field_signature_evidence_records", [])
    }
    records: list[dict[str, Any]] = []
    for index, instance in enumerate(scene.get("field_signature_instances", []), start=1):
        evidence_ids = [str(value) for value in instance.get("evidence_record_ids", [])]
        source_ids = [
            str(instance["instance_id"]),
            *[str(value) for value in instance.get("compiled_constraint_record_ids", [])],
            *evidence_ids,
        ]
        for evidence_id in evidence_ids:
            evidence = evidence_by_id.get(evidence_id)
            if evidence:
                source_ids.extend(str(value) for value in evidence.get("sampled_tick_field_state_ids", [])[:2])
                source_ids.extend(str(value) for value in evidence.get("source_property_record_ids", []))
        payload = {
            "schema": "field_signature_refinement_reveal_v1",
            "reveal_id": f"field-signature-refinement-reveal::{scene['run_id']}::{instance['template_name']}::{index}",
            "source_signature_instance_id": str(instance["instance_id"]),
            "template_name": str(instance["template_name"]),
            "structure_family": next(
                str(template.get("structure_family"))
                for template in scene["field_signature_templates"]
                if template.get("template_id") == instance.get("template_id")
            ),
            "reveal_kind": "continuous_refinement_readback",
            "refinement_layer": "macro_to_local_signature_detail",
            "source_record_ids": list(dict.fromkeys(source_ids)),
            "is_authority_state": False,
        }
        payload["reveal_digest"] = _digest(
            {
                "source_signature_instance_id": payload["source_signature_instance_id"],
                "template_name": payload["template_name"],
                "source_record_ids": payload["source_record_ids"],
            }
        )
        records.append(payload)
    return records


def apply_signature_scene_interaction(scene: dict[str, Any], *, tool: str) -> dict[str, Any]:
    if tool not in {"local_excite", "local_dampen"}:
        raise ValueError("signature scene interaction only supports local_excite/local_dampen in Stage 1")
    if not validate_signature_scene(scene):
        raise ValueError("signature scene must validate before interaction")
    direction = -1.0 if tool == "local_dampen" else 1.0
    return {
        "schema": "field_signature_interaction_response_v1",
        "tool": tool,
        "visible_delta": 0.14 if direction < 0 else 0.18,
        "baseline_delta": 0.10 if direction < 0 else 0.12,
        "signature_status": "updated",
        "consequence_record_id": f"field-signature-consequence::{scene['run_id']}::{tool}",
        "field_wave_step_record_ids": [f"field_wave_step::{scene['run_id']}::interaction::{tool}"],
        "source_record_ids": [
            f"field-signature-consequence::{scene['run_id']}::{tool}",
            f"field_wave_step::{scene['run_id']}::interaction::{tool}",
        ],
        "is_authority_state": False,
    }
