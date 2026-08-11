from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from world_engine.implicit_field import build_implicit_field_basis


FIELD_SIGNATURE_TEMPLATE_SCHEMA = "field_signature_template_v1"
FIELD_SIGNATURE_INSTANCE_SCHEMA = "field_signature_instance_v1"
FIELD_SIGNATURE_COMPILATION_SCHEMA = "field_signature_compilation_record_v1"
FIELD_SIGNATURE_EVIDENCE_SCHEMA = "field_signature_evidence_v1"

SIGNATURE_INSTANCE_RAW_MATCH_MIN = 0.85
SIGNATURE_STABILITY_TICK_MIN = 32
FORBIDDEN_SIGNATURE_EVIDENCE_KEYS = {
    "viewer_label",
    "viewer_color",
    "css_color",
    "mesh",
    "object_asset_id",
}


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _strip_digest(value: Mapping[str, Any], *digest_keys: str) -> dict[str, Any]:
    data = dict(value)
    for key in digest_keys:
        data.pop(key, None)
    return data


def _assert_no_forbidden_keys(value: Any, *, path: str = "payload") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in FORBIDDEN_SIGNATURE_EVIDENCE_KEYS:
                raise ValueError(f"forbidden field signature evidence key at {path}: {key}")
            _assert_no_forbidden_keys(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_forbidden_keys(child, path=f"{path}[{index}]")


def _template(
    *,
    name: str,
    intent: str,
    structure_family: str,
    required_constraint_roles: Sequence[str],
    readback_measurement_requirements: Sequence[str],
    support_constraints: dict[str, Any],
    material_response_constraints: dict[str, Any],
    interaction_constraints: dict[str, Any],
) -> dict[str, Any]:
    template = {
        "schema": FIELD_SIGNATURE_TEMPLATE_SCHEMA,
        "template_id": f"field-signature-template::{name}-v1",
        "name": name,
        "intent": intent,
        "structure_family": structure_family,
        "signature_channels": ["pattern"],
        "required_constraint_roles": [str(role) for role in required_constraint_roles],
        "readback_measurement_requirements": [str(requirement) for requirement in readback_measurement_requirements],
        "support_constraints": support_constraints,
        "lifecycle_constraints": {
            "stable_tick_min": SIGNATURE_STABILITY_TICK_MIN,
            "allowed_events": ["persist", "minor_boundary_shift"],
            "forbidden_events": ["unbounded_growth", "silent_extinction"],
        },
        "material_response_constraints": material_response_constraints,
        "interaction_constraints": interaction_constraints,
        "authoring_status": "human_authored_non_authority",
        "is_authority_state": False,
    }
    template["template_digest"] = _canonical_digest(template)
    return template


def built_in_signature_templates() -> dict[str, dict[str, Any]]:
    return {
        "surface_layer": _template(
            name="surface_layer",
            intent="stable exposed interface that refinement can reveal as local surface support",
            structure_family="surface",
            required_constraint_roles=["support", "boundary"],
            readback_measurement_requirements=["support_digest", "surface_gradient", "spectral_response"],
            support_constraints={
                "min_compactness": 0.50,
                "max_fragment_count": 3,
                "preferred_aspect_ratio_range": [1.2, 10.0],
            },
            material_response_constraints={
                "rigidity_min": 0.40,
                "surface_gradient_min": 0.30,
                "spectral_response_min": 0.35,
            },
            interaction_constraints={
                "expected_consequence_kinds": ["surface_readback", "local_refinement_reveal"],
                "baseline_required": True,
            },
        ),
        "surface_barrier": _template(
            name="surface_barrier",
            intent="stable boundary-like support that blocks or reflects local perturbation",
            structure_family="barrier",
            required_constraint_roles=["support", "boundary"],
            readback_measurement_requirements=["support_digest", "rigidity", "permeability"],
            support_constraints={
                "min_compactness": 0.55,
                "max_fragment_count": 2,
                "preferred_aspect_ratio_range": [2.0, 8.0],
            },
            material_response_constraints={
                "rigidity_min": 0.55,
                "damping_range": [0.05, 0.45],
                "permeability_max": 0.35,
            },
            interaction_constraints={
                "expected_consequence_kinds": ["boundary_containment", "local_perturbation_response"],
                "baseline_required": True,
            },
        ),
        "channel_conduit": _template(
            name="channel_conduit",
            intent="stable corridor-like support that guides transport across a region",
            structure_family="channel",
            required_constraint_roles=["support", "transport"],
            readback_measurement_requirements=["support_digest", "transport", "permeability"],
            support_constraints={
                "min_compactness": 0.35,
                "max_fragment_count": 3,
                "preferred_aspect_ratio_range": [3.0, 12.0],
            },
            material_response_constraints={
                "transport_min": 0.50,
                "permeability_range": [0.35, 0.85],
                "damping_range": [0.02, 0.35],
            },
            interaction_constraints={
                "expected_consequence_kinds": ["channel_transport", "guided_perturbation"],
                "baseline_required": True,
            },
        ),
        "source_emitter": _template(
            name="source_emitter",
            intent="localized oscillator-like source that maintains a spectral field response",
            structure_family="source",
            required_constraint_roles=["support", "source"],
            readback_measurement_requirements=["support_digest", "source_amplitude", "spectral_response"],
            support_constraints={
                "min_compactness": 0.20,
                "max_fragment_count": 4,
                "preferred_aspect_ratio_range": [0.5, 4.0],
            },
            material_response_constraints={
                "source_amplitude_min": 0.20,
                "spectral_response_min": 0.40,
                "damping_range": [0.0, 0.30],
            },
            interaction_constraints={
                "expected_consequence_kinds": ["source_maintenance", "local_perturbation_response"],
                "baseline_required": True,
            },
        ),
        "sink_absorber": _template(
            name="sink_absorber",
            intent="localized absorber that drains or damps incoming field energy",
            structure_family="sink",
            required_constraint_roles=["support", "sink"],
            readback_measurement_requirements=["support_digest", "sink_rate", "damping"],
            support_constraints={
                "min_compactness": 0.25,
                "max_fragment_count": 4,
                "preferred_aspect_ratio_range": [0.5, 5.0],
            },
            material_response_constraints={
                "sink_rate_min": 0.20,
                "damping_range": [0.25, 0.85],
                "permeability_range": [0.10, 0.55],
            },
            interaction_constraints={
                "expected_consequence_kinds": ["energy_absorption", "local_damping_response"],
                "baseline_required": True,
            },
        ),
        "container_envelope": _template(
            name="container_envelope",
            intent="closed or semi-closed envelope that contains pressure or transport inside a support region",
            structure_family="container",
            required_constraint_roles=["support", "boundary", "containment"],
            readback_measurement_requirements=["support_digest", "containment", "boundary_integrity"],
            support_constraints={
                "min_compactness": 0.42,
                "max_fragment_count": 4,
                "preferred_aspect_ratio_range": [1.0, 6.0],
            },
            material_response_constraints={
                "containment_min": 0.45,
                "permeability_max": 0.30,
                "pressure_storage_min": 0.25,
            },
            interaction_constraints={
                "expected_consequence_kinds": ["contained_transport", "pressure_storage_response"],
                "baseline_required": True,
            },
        ),
        "machine_coupler": _template(
            name="machine_coupler",
            intent="coupled structure that transforms one field response into another under budgeted constraints",
            structure_family="machine_like",
            required_constraint_roles=["support", "coupling"],
            readback_measurement_requirements=["support_digest", "coupling", "budget_response"],
            support_constraints={
                "min_compactness": 0.30,
                "max_fragment_count": 5,
                "preferred_aspect_ratio_range": [0.8, 8.0],
            },
            material_response_constraints={
                "coupling_min": 0.25,
                "budget_error_max": 0.25,
                "spectral_response_min": 0.30,
            },
            interaction_constraints={
                "expected_consequence_kinds": ["field_coupling_response", "budgeted_conversion"],
                "baseline_required": True,
            },
        ),
    }


def validate_field_signature_template(template: Mapping[str, Any]) -> None:
    if template.get("schema") != FIELD_SIGNATURE_TEMPLATE_SCHEMA:
        raise ValueError("field signature template schema mismatch")
    if template.get("is_authority_state") is not False:
        raise ValueError("field signature template must be non-authority")
    if not template.get("template_id") or not template.get("name"):
        raise ValueError("field signature template requires id and name")
    if not template.get("structure_family"):
        raise ValueError("field signature template requires structure_family")
    if not template.get("required_constraint_roles"):
        raise ValueError("field signature template requires required_constraint_roles")
    if not template.get("readback_measurement_requirements"):
        raise ValueError("field signature template requires readback_measurement_requirements")
    if template.get("template_digest") != _canonical_digest(_strip_digest(template, "template_digest")):
        raise ValueError("field signature template digest mismatch")
    _assert_no_forbidden_keys(template)


def _role_names(compiled_to: Mapping[str, Any]) -> list[str]:
    roles: set[str] = set()
    for value in compiled_to.values():
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, Mapping) and item.get("role"):
                roles.add(str(item["role"]))
    return sorted(roles)


def _compiled_to_for_template(template_name: str) -> dict[str, list[dict[str, Any]]]:
    if template_name == "surface_layer":
        return {
            "field_source_regions": [],
            "field_affordance_commands": [
                {
                    "role": "support",
                    "operator": "surface_support_field",
                    "purpose": "surface_layer_support",
                    "target_channel": "pattern",
                    "constraints": {"surface_gradient_min": 0.30, "spectral_response_min": 0.35},
                },
                {
                    "role": "boundary",
                    "operator": "surface_boundary_gradient",
                    "purpose": "surface_layer_visible_interface",
                    "target_channel": "pattern",
                    "constraints": {"boundary_softness_range": [0.15, 0.55]},
                },
            ],
            "property_constraints": [
                {"role": "support", "property": "surface_gradient", "min": 0.30},
                {"role": "boundary", "property": "spectral_response", "min": 0.35},
            ],
            "region_activation_requests": [
                {"role": "support", "purpose": "surface_layer_tracking", "mode": "fine_or_certified_macro"}
            ],
        }
    if template_name == "surface_barrier":
        return {
            "field_source_regions": [],
            "field_affordance_commands": [
                {
                    "role": "boundary",
                    "operator": "local_field_modulator",
                    "purpose": "surface_barrier_boundary_response",
                    "target_channel": "pattern",
                    "constraints": {"damping_range": [0.05, 0.45], "permeability_max": 0.35},
                }
            ],
            "property_constraints": [
                {"role": "support", "property": "rigidity", "min": 0.55},
                {"role": "boundary", "property": "permeability", "max": 0.35},
            ],
            "region_activation_requests": [
                {"role": "support", "purpose": "signature_support_tracking", "mode": "fine_or_certified_macro"}
            ],
        }
    if template_name == "channel_conduit":
        return {
            "field_source_regions": [],
            "field_affordance_commands": [
                {
                    "role": "transport",
                    "operator": "transport_permeability_gradient",
                    "purpose": "channel_conduit_transport",
                    "target_channel": "pattern",
                    "constraints": {"transport_min": 0.50, "permeability_range": [0.35, 0.85]},
                }
            ],
            "property_constraints": [
                {"role": "transport", "property": "transport", "min": 0.50},
                {"role": "support", "property": "permeability", "range": [0.35, 0.85]},
            ],
            "region_activation_requests": [
                {"role": "support", "purpose": "channel_support_band_tracking", "mode": "fine_or_certified_macro"}
            ],
        }
    if template_name == "source_emitter":
        return {
            "field_source_regions": [
                {
                    "role": "source",
                    "operator": "local_field_source_schedule",
                    "purpose": "source_emitter_oscillation",
                    "target_channel": "pattern",
                    "constraints": {"source_amplitude_min": 0.20, "frequency_band": [0.50, 0.78]},
                }
            ],
            "field_affordance_commands": [],
            "property_constraints": [
                {"role": "support", "property": "spectral_response", "min": 0.40},
                {"role": "source", "property": "source_amplitude", "min": 0.20},
            ],
            "region_activation_requests": [
                {"role": "support", "purpose": "emitter_support_tracking", "mode": "fine_or_certified_macro"}
            ],
        }
    if template_name == "sink_absorber":
        return {
            "field_source_regions": [],
            "field_affordance_commands": [
                {
                    "role": "sink",
                    "operator": "local_field_sink_schedule",
                    "purpose": "sink_absorber_energy_absorption",
                    "target_channel": "pattern",
                    "constraints": {"sink_rate_min": 0.20, "damping_range": [0.25, 0.85]},
                }
            ],
            "property_constraints": [
                {"role": "support", "property": "damping", "range": [0.25, 0.85]},
                {"role": "sink", "property": "sink_rate", "min": 0.20},
            ],
            "region_activation_requests": [
                {"role": "support", "purpose": "sink_absorber_tracking", "mode": "fine_or_certified_macro"}
            ],
        }
    if template_name == "container_envelope":
        return {
            "field_source_regions": [],
            "field_affordance_commands": [
                {
                    "role": "containment",
                    "operator": "closed_boundary_containment_modulator",
                    "purpose": "container_envelope_pressure_storage",
                    "target_channel": "pattern",
                    "constraints": {"containment_min": 0.45, "permeability_max": 0.30},
                }
            ],
            "property_constraints": [
                {"role": "support", "property": "boundary_integrity", "min": 0.45},
                {"role": "boundary", "property": "permeability", "max": 0.30},
                {"role": "containment", "property": "containment", "min": 0.45},
            ],
            "region_activation_requests": [
                {"role": "support", "purpose": "container_envelope_tracking", "mode": "fine_or_certified_macro"}
            ],
        }
    if template_name == "machine_coupler":
        return {
            "field_source_regions": [],
            "field_affordance_commands": [
                {
                    "role": "coupling",
                    "operator": "field_response_coupler",
                    "purpose": "machine_coupler_budgeted_conversion",
                    "target_channel": "pattern",
                    "constraints": {"coupling_min": 0.25, "budget_error_max": 0.25},
                }
            ],
            "property_constraints": [
                {"role": "support", "property": "spectral_response", "min": 0.30},
                {"role": "coupling", "property": "coupling", "min": 0.25},
            ],
            "region_activation_requests": [
                {"role": "support", "purpose": "machine_coupler_tracking", "mode": "fine_or_certified_macro"}
            ],
        }
    raise ValueError(f"unknown field signature template: {template_name}")


def compile_field_signature_template(
    template: Mapping[str, Any],
    *,
    run_id: str,
    instance_index: int,
) -> dict[str, Any]:
    validate_field_signature_template(template)
    template_name = str(template["name"])
    compiled_to = _compiled_to_for_template(template_name)
    operator_count = sum(len(value) for value in compiled_to.values())
    compiled_roles = _role_names(compiled_to)
    required_roles = [str(role) for role in template.get("required_constraint_roles", [])]
    record = {
        "schema": FIELD_SIGNATURE_COMPILATION_SCHEMA,
        "record_id": f"field-signature-compilation::{run_id}::{template_name}::{instance_index}",
        "template_id": template["template_id"],
        "instance_id": f"field-signature-instance::{run_id}::{template_name}::{instance_index}",
        "compiled_to": compiled_to,
        "required_constraint_roles": required_roles,
        "compiled_constraint_roles": compiled_roles,
        "compiled_operator_count": operator_count,
        "source_record_ids": [template["template_id"]],
        "is_authority_state": False,
    }
    record["compilation_digest"] = _canonical_digest(record)
    return record


def _support_region_3d(center: Sequence[float], half_extents: Sequence[float]) -> dict[str, list[float]]:
    return {
        "min": [float(center[index]) - float(half_extents[index]) for index in range(3)],
        "max": [float(center[index]) + float(half_extents[index]) for index in range(3)],
    }


def compile_field_signature_to_implicit_basis(
    template: Mapping[str, Any],
    instance: Mapping[str, Any],
    *,
    run_id: str,
    region_id: str,
    center_world_3d: Sequence[float],
) -> list[dict[str, Any]]:
    validate_field_signature_template(template)
    if instance.get("schema") != FIELD_SIGNATURE_INSTANCE_SCHEMA:
        raise ValueError("implicit basis compilation requires field signature instance")
    if instance.get("is_authority_state") is not False:
        raise ValueError("field signature instance must be non-authority")
    if instance.get("template_id") != template.get("template_id"):
        raise ValueError("field signature instance template mismatch")

    center = [float(value) for value in center_world_3d]
    template_name = str(template["name"])
    source_ids = [
        str(template["template_id"]),
        str(instance["instance_id"]),
        *[str(value) for value in instance.get("compiled_constraint_record_ids", [])],
        *[str(value) for value in instance.get("evidence_record_ids", [])],
        *[str(value) for value in instance.get("source_record_ids", [])],
        str(region_id),
    ]
    coordinate_frame = {"units": "world", "handedness": "right", "axes": ["x", "y", "z"]}
    common = {
        "coordinate_frame_3d": coordinate_frame,
        "source_signature_template_id": str(template["template_id"]),
        "source_signature_instance_id": str(instance["instance_id"]),
        "center_world_3d": center,
        "frequency_vector": [0.0, 0.0, 0.0],
        "phase": 0.0,
        "source_record_ids": source_ids,
    }

    if template_name == "surface_barrier":
        return [
            build_implicit_field_basis(
                basis_id=f"implicit-basis::{run_id}::{template_name}::boundary::0",
                basis_kind="signed_boundary",
                basis_axes=[[0.45, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 0.75]],
                radius_world=4.0,
                basis_profile="signed_step",
                basis_profile_params={"axis": "x", "threshold": center[0]},
                omega=0.0,
                channel_weights={"density": 0.55, "absorption": 0.75, "boundary": 1.0, "emission": 0.0},
                support_region_world=_support_region_3d(center, [8.0, 4.0, 5.0]),
                **common,
            )
        ]

    if template_name == "channel_conduit":
        return [
            build_implicit_field_basis(
                basis_id=f"implicit-basis::{run_id}::{template_name}::density::0",
                basis_kind="density_lobe",
                basis_axes=[[0.25, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                radius_world=4.5,
                basis_profile="density",
                basis_profile_params={"elongated_axis": "x"},
                omega=0.0,
                channel_weights={"density": 0.9, "absorption": 0.12, "boundary": 0.15, "emission": 0.0},
                support_region_world=_support_region_3d(center, [14.0, 4.5, 4.5]),
                **common,
            ),
            build_implicit_field_basis(
                basis_id=f"implicit-basis::{run_id}::{template_name}::absorption::0",
                basis_kind="absorption_region",
                basis_axes=[[0.22, 0.0, 0.0], [0.0, 0.8, 0.0], [0.0, 0.0, 0.8]],
                radius_world=5.0,
                basis_profile="absorption",
                basis_profile_params={"role": "channel_wall_loss"},
                omega=0.0,
                channel_weights={"density": 0.15, "absorption": 0.5, "boundary": 0.05, "emission": 0.0},
                support_region_world=_support_region_3d(center, [16.0, 5.0, 5.0]),
                **common,
            ),
        ]

    if template_name == "source_emitter":
        return [
            build_implicit_field_basis(
                basis_id=f"implicit-basis::{run_id}::{template_name}::emitter::0",
                basis_kind="emitter",
                basis_axes=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                radius_world=3.5,
                basis_profile="oscillator",
                basis_profile_params={"role": "compact_source_emission"},
                frequency_vector=[0.18, 0.0, 0.08],
                omega=0.42,
                channel_weights={"density": 0.45, "absorption": 0.05, "boundary": 0.0, "emission": 1.0},
                support_region_world=_support_region_3d(center, [3.5, 3.5, 3.5]),
                source_record_ids=source_ids,
                coordinate_frame_3d=coordinate_frame,
                source_signature_template_id=str(template["template_id"]),
                source_signature_instance_id=str(instance["instance_id"]),
                center_world_3d=center,
                phase=0.0,
            )
        ]

    raise ValueError(f"cannot compile template to implicit basis: {template_name}")


def _operator_count(compiled_to: Mapping[str, Any]) -> int:
    count = 0
    for value in compiled_to.values():
        if isinstance(value, list):
            count += len(value)
    return count


def validate_field_signature_compilation_record(
    record: Mapping[str, Any],
    *,
    accepted_instance: bool = False,
) -> None:
    if record.get("schema") != FIELD_SIGNATURE_COMPILATION_SCHEMA:
        raise ValueError("field signature compilation schema mismatch")
    if record.get("is_authority_state") is not False:
        raise ValueError("field signature compilation must be non-authority")
    compiled_to = record.get("compiled_to")
    if not isinstance(compiled_to, Mapping):
        raise ValueError("field signature compilation requires compiled_to")
    operator_count = _operator_count(compiled_to)
    if accepted_instance and operator_count <= 0:
        raise ValueError("accepted field signature compilation cannot be empty")
    if int(record.get("compiled_operator_count", -1)) != operator_count:
        raise ValueError("field signature compilation operator count mismatch")
    compiled_roles = {str(role) for role in record.get("compiled_constraint_roles", [])}
    required_roles = {str(role) for role in record.get("required_constraint_roles", [])}
    actual_roles = set(_role_names(compiled_to))
    if compiled_roles != actual_roles:
        raise ValueError("field signature compilation role mismatch")
    if accepted_instance and (not required_roles or not required_roles.issubset(compiled_roles)):
        raise ValueError("accepted field signature compilation missing required roles")
    if record.get("compilation_digest") != _canonical_digest(_strip_digest(record, "compilation_digest")):
        raise ValueError("field signature compilation digest mismatch")
    _assert_no_forbidden_keys(record)


def _field_mapping(field_state: Mapping[str, Any]) -> dict[str, Any]:
    if hasattr(field_state, "to_dict"):
        return dict(field_state.to_dict())
    return dict(field_state)


def _support_metrics(field_states: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not field_states:
        return {
            "support_count": 0,
            "component_count": 0,
            "compactness": 0.0,
            "boundary_energy_gradient": 0.0,
            "avg_energy": 0.0,
            "raw_channel_digest": _canonical_digest([]),
            "raw_support_digest": _canonical_digest([]),
        }
    state = _field_mapping(field_states[-1])
    channels = state.get("channels", {})
    channel = channels.get("pattern") or next(iter(channels.values()), [])
    support: list[tuple[int, int]] = []
    energy_sum = 0.0
    for y, row in enumerate(channel):
        for x, value in enumerate(row):
            numeric = float(value)
            energy_sum += abs(numeric)
            if abs(numeric) > 0.05:
                support.append((x, y))
    if support:
        xs = [point[0] for point in support]
        ys = [point[1] for point in support]
        bbox_area = max(1, (max(xs) - min(xs) + 1) * (max(ys) - min(ys) + 1))
        compactness = len(support) / bbox_area
        boundary_energy_gradient = min(1.0, len(support) / max(1, len(channel) * len(channel[0]) if channel else 1) * 5.0)
    else:
        compactness = 0.0
        boundary_energy_gradient = 0.0
    cell_count = sum(len(row) for row in channel) or 1
    return {
        "support_count": len(support),
        "component_count": 1 if support else 0,
        "compactness": compactness,
        "boundary_energy_gradient": boundary_energy_gradient,
        "avg_energy": energy_sum / cell_count,
        "raw_channel_digest": _canonical_digest([_field_mapping(state).get("channels", {}) for state in field_states]),
        "raw_support_digest": _canonical_digest(support),
    }


def summarize_field_signature_evidence(
    *,
    template: Mapping[str, Any],
    field_states: Sequence[Mapping[str, Any]],
    property_records: Sequence[Mapping[str, Any]],
    baseline_case_id: str,
) -> dict[str, Any]:
    validate_field_signature_template(template)
    metrics = _support_metrics(field_states)
    stability_ticks = len(field_states)
    has_support = metrics["support_count"] > 0
    raw_match_score = 0.0
    if has_support:
        raw_match_score += 0.60
        raw_match_score += min(0.30, stability_ticks / SIGNATURE_STABILITY_TICK_MIN * 0.30)
        raw_match_score += 0.10 if metrics["component_count"] >= 1 else 0.0
    raw_match_score = min(1.0, raw_match_score)
    first_tick = int(_field_mapping(field_states[0]).get("tick", 0)) if field_states else 0
    last_tick = int(_field_mapping(field_states[-1]).get("tick", 0)) if field_states else first_tick
    source_field_ids = [
        str(_field_mapping(field).get("field_state_id") or _field_mapping(field).get("id"))
        for field in field_states
    ]
    template_name = str(template["name"])
    run_hint = source_field_ids[0].replace("field-state::", "") if source_field_ids else "run"
    computed_metrics = {
        "stability_ticks": stability_ticks,
        "raw_match_score": raw_match_score,
        "component_count": metrics["component_count"],
        "centroid_drift_grid": 0.0 if has_support else 999.0,
        "boundary_energy_gradient": metrics["boundary_energy_gradient"],
        "mode_signature": _canonical_digest({"template": template_name, "support": metrics["raw_support_digest"]}),
    }
    return {
        "schema": FIELD_SIGNATURE_EVIDENCE_SCHEMA,
        "evidence_id": f"field-signature-evidence::{run_hint}::{template_name}",
        "template_id": template["template_id"],
        "tick_range": [first_tick, last_tick],
        "source_field_state_ids": [source_field_ids[0], source_field_ids[-1]] if source_field_ids else [],
        "source_field_state_range": {
            "start_tick": first_tick,
            "end_tick": last_tick,
            "sampled_tick_stride": 1,
            "range_digest": _canonical_digest(source_field_ids),
        },
        "sampled_tick_field_state_ids": source_field_ids,
        "source_property_record_ids": [
            str(record.get("record_id") or record.get("id")) for record in property_records
        ],
        "source_material_response_record_ids": [],
        "source_wave_step_record_ids": [f"field_wave_step::{tick}" for tick in range(first_tick, last_tick + 1)],
        "baseline_case_id": baseline_case_id,
        "raw_support_digest": metrics["raw_support_digest"],
        "raw_channel_digest": metrics["raw_channel_digest"],
        "computed_metrics": computed_metrics,
        "recompute_function": "summarize_field_signature_evidence_v1",
        "source_record_ids": [f"field_wave_step::{first_tick}", f"field_wave_step::{last_tick}"],
        "is_authority_state": False,
    }


def validate_field_signature_evidence_record(record: Mapping[str, Any]) -> None:
    if record.get("schema") != FIELD_SIGNATURE_EVIDENCE_SCHEMA:
        raise ValueError("field signature evidence schema mismatch")
    if record.get("is_authority_state") is not False:
        raise ValueError("field signature evidence must be non-authority")
    if not record.get("source_field_state_ids") or not record.get("sampled_tick_field_state_ids"):
        raise ValueError("field signature evidence requires read-back field-state lineage")
    if not record.get("source_field_state_range"):
        raise ValueError("field signature evidence requires source_field_state_range")
    metrics = record.get("computed_metrics")
    if not isinstance(metrics, Mapping):
        raise ValueError("field signature evidence requires computed_metrics")
    if float(metrics.get("raw_match_score", 0.0)) < SIGNATURE_INSTANCE_RAW_MATCH_MIN:
        raise ValueError("field signature evidence raw match below threshold")
    if int(metrics.get("stability_ticks", 0)) < SIGNATURE_STABILITY_TICK_MIN:
        raise ValueError("field signature evidence stability below threshold")
    _assert_no_forbidden_keys(record)


def build_field_signature_instance(
    template: Mapping[str, Any],
    compilation: Mapping[str, Any],
    evidence: Mapping[str, Any],
    *,
    run_id: str,
    region_id: str,
) -> dict[str, Any]:
    validate_field_signature_template(template)
    validate_field_signature_compilation_record(compilation, accepted_instance=True)
    validate_field_signature_evidence_record(evidence)
    template_name = str(template["name"])
    instance = {
        "schema": FIELD_SIGNATURE_INSTANCE_SCHEMA,
        "instance_id": compilation["instance_id"],
        "template_id": template["template_id"],
        "template_name": template_name,
        "run_id": run_id,
        "region_id": region_id,
        "tick_range": list(evidence["tick_range"]),
        "source_field_state_ids": list(evidence["source_field_state_ids"]),
        "source_macro_state_ids": [],
        "source_property_record_ids": list(evidence.get("source_property_record_ids", [])),
        "compiled_constraint_record_ids": [compilation["record_id"]],
        "evidence_record_ids": [evidence["evidence_id"]],
        "observed_signature_metrics": dict(evidence["computed_metrics"]),
        "source_record_ids": list(evidence.get("source_record_ids", [])),
        "is_authority_state": False,
    }
    return instance


def validate_field_signature_instance(
    instance: Mapping[str, Any],
    evidence_records: Sequence[Mapping[str, Any]],
    compilation_records: Sequence[Mapping[str, Any]],
    templates: Sequence[Mapping[str, Any]],
) -> None:
    if instance.get("schema") != FIELD_SIGNATURE_INSTANCE_SCHEMA:
        raise ValueError("field signature instance schema mismatch")
    if instance.get("is_authority_state") is not False:
        raise ValueError("field signature instance must be non-authority")
    if not instance.get("instance_id") or not instance.get("template_id"):
        raise ValueError("field signature instance requires id and template id")
    if not instance.get("source_field_state_ids"):
        raise ValueError("field signature instance requires source field states")
    evidence_ids = [str(value) for value in instance.get("evidence_record_ids", [])]
    compilation_ids = [str(value) for value in instance.get("compiled_constraint_record_ids", [])]
    if not evidence_ids:
        raise ValueError("field signature instance requires evidence records")
    if not compilation_ids:
        raise ValueError("field signature instance requires compilation records")
    evidence_by_id = {str(record.get("evidence_id")): record for record in evidence_records}
    compilation_by_id = {str(record.get("record_id")): record for record in compilation_records}
    template_by_id = {str(template.get("template_id")): template for template in templates}
    template = template_by_id.get(str(instance.get("template_id")))
    if not template:
        raise ValueError("field signature instance template missing")
    validate_field_signature_template(template)
    for compilation_id in compilation_ids:
        compilation = compilation_by_id.get(compilation_id)
        if not compilation:
            raise ValueError("field signature instance compilation missing")
        validate_field_signature_compilation_record(compilation, accepted_instance=True)
    for evidence_id in evidence_ids:
        evidence = evidence_by_id.get(evidence_id)
        if not evidence:
            raise ValueError("field signature instance evidence missing")
        validate_field_signature_evidence_record(evidence)
        metrics = evidence["computed_metrics"]
        observed = instance.get("observed_signature_metrics", {})
        if observed.get("mode_signature") != metrics.get("mode_signature"):
            raise ValueError("field signature instance observed metrics do not match evidence")
        if float(observed.get("raw_match_score", 0.0)) != float(metrics.get("raw_match_score", 0.0)):
            raise ValueError("field signature instance raw match does not match evidence")
    _assert_no_forbidden_keys(instance)
