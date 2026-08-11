from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from math import isfinite
from typing import Any


JsonDict = dict[str, Any]

MATERIAL_EFFECTIVE_PROPERTY_KEYS = {
    "mass_like_quantity",
    "energy_like_quantity",
    "charge_like_quantity",
    "cohesion",
    "boundary_response",
    "damping_response",
    "source_response",
    "reactivity",
    "transport_response",
    "mode_signature",
    "stability_window",
}

MATERIAL_CONSERVATION_LIMITS = {
    "mass_like_relative_error": 0.02,
    "energy_like_relative_error": 0.08,
    "charge_like_absolute_error": 0.05,
}

MATERIAL_BOND_KINDS = {
    "cohesive_contact",
    "boundary_lock",
    "source_absorber_pair",
    "transport_channel",
    "unstable_contact",
}
MATERIAL_STABLE_BOND_KINDS = MATERIAL_BOND_KINDS - {"unstable_contact"}
MATERIAL_REACTION_KINDS = {"combine", "separate", "transform", "exchange", "failed_unbalanced"}
MATERIAL_BALANCE_STATUSES = {"balanced", "unbalanced", "fail_closed"}
MATERIAL_BODY_KINDS = {"single_species_body", "bonded_body", "compound_body"}
MATERIAL_AUTHORITY_MODES = {
    "none",
    "cold_macro_material",
    "warm_macro_material",
    "active_material_refinement",
    "invalidated_material",
}
MATERIAL_BEHAVIOR_PROPERTY_KEYS = {
    "density",
    "rigidity",
    "cohesion",
    "permeability",
    "friction",
    "damping",
    "transport",
    "reactivity",
    "conductivity",
    "optical_response",
}
MATERIAL_BEHAVIOR_CLASSES = {
    "rigid_solid_like",
    "granular_medium_like",
    "fluid_medium_like",
    "elastic_body_like",
    "absorbing_damper_like",
    "conductive_channel_like",
    "boundary_container_like",
    "unstable_reactive_like",
}
MATERIAL_BEHAVIOR_DERIVATION_METHODS = {
    "legacy_macro_threshold_scaffold_v1",
    "substrate_frequency_measurement_v1",
    "substrate_hypergraph_measurement_v1",
}
MATERIAL_BEHAVIOR_SCAFFOLD_STATUSES = {
    "stage1_scaffold",
    "substrate_derived",
    "fallback",
}
DEFAULT_MATERIAL_BEHAVIOR_THRESHOLDS = {
    "rigid_rigidity_min": 0.72,
    "rigid_permeability_max": 0.30,
    "rigid_damping_min": 0.35,
    "container_cohesion_min": 0.50,
    "container_rigidity_min": 0.45,
    "container_permeability_max": 0.50,
    "fluid_permeability_min": 0.68,
    "fluid_rigidity_max": 0.35,
    "fluid_transport_min": 0.45,
    "granular_rigidity_max": 0.45,
    "granular_friction_min": 0.45,
    "granular_cohesion_max": 0.55,
    "absorbing_damping_min": 0.65,
    "conductive_conductivity_min": 0.60,
    "conductive_transport_min": 0.40,
    "reactive_reactivity_min": 0.65,
}
MATERIAL_ZONE_ROLES = {"obstacle", "medium", "channel", "container", "surface", "reactive_site"}
MATERIAL_ZONE_ROLE_COMPATIBILITY = {
    "rigid_solid_like": {"obstacle", "surface"},
    "granular_medium_like": {"medium", "surface"},
    "fluid_medium_like": {"medium", "channel"},
    "elastic_body_like": {"surface", "medium"},
    "absorbing_damper_like": {"medium"},
    "conductive_channel_like": {"channel"},
    "boundary_container_like": {"container", "obstacle"},
    "unstable_reactive_like": {"reactive_site"},
}
MATERIAL_INTERACTION_INTENTS = {
    "inspect_material",
    "push_material",
    "carve_material",
    "compress_material",
    "heat_material",
    "cool_material",
    "dissolve_material",
    "bind_material",
}
MATERIAL_INTERACTION_RESULT_STATUSES = {
    "observation_only",
    "corrected_macro_material",
    "invalidated_macro_material",
    "failed_closed",
}
MATERIAL_CONTACT_KINDS = {
    "ordinary_inter_body_contact",
    "near_band_inter_body_contact",
    "container_boundary_contact",
    "failed_closed_contact",
}
MATERIAL_RESPONSE_KINDS = {
    "rigid_block_or_reflect",
    "damping_energy_absorption",
    "container_constraint",
    "channel_guided_transport",
    "granular_slowing_settling",
    "failed_closed",
}
MATERIAL_RESPONSE_RESULT_STATUSES = {
    "applied",
    "observation_only",
    "failed_closed",
    "refinement_required",
}
MATERIAL_CONTACT_AUTHORITY_KINDS = {
    "field_state",
    "fine_patch_snapshot",
    "material_patch_snapshot",
}
SUBSTRATE_TYPES = {
    "field_frequency_grid_v1",
    "hypergraph_rewrite_v1",
}
SUBSTRATE_MEASUREMENT_SOURCE_KINDS = {
    "field_state",
    "fine_patch_snapshot",
    "material_patch_snapshot",
    "hypergraph_state_snapshot",
}
MATERIAL_BEHAVIOR_RESPONSE_COMPATIBILITY = {
    "rigid_solid_like": {"rigid_block_or_reflect"},
    "absorbing_damper_like": {"damping_energy_absorption"},
    "boundary_container_like": {"container_constraint", "rigid_block_or_reflect"},
    "conductive_channel_like": {"channel_guided_transport"},
    "fluid_medium_like": {"channel_guided_transport"},
    "granular_medium_like": {"granular_slowing_settling"},
    "elastic_body_like": {"rigid_block_or_reflect", "damping_energy_absorption"},
    "unstable_reactive_like": {"failed_closed"},
}
MATERIAL_EXTERNAL_EXCHANGE_TYPES = {
    "energy_in",
    "energy_out",
    "cohesion_delta",
    "transport_delta",
    "reactivity_delta",
}


def _dict(value: JsonDict | None) -> JsonDict:
    return dict(value or {})


def _list(value: list[Any] | None) -> list[Any]:
    return list(value or [])


def _bool(value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError("authority flag must be a bool.")
    return value


def _canonical_json_digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _channels(value: dict[str, list[list[float]]] | None) -> dict[str, list[list[float]]]:
    channels: dict[str, list[list[float]]] = {}
    for key, grid in dict(value or {}).items():
        channels[str(key)] = [[float(cell) for cell in row] for row in grid]
    return channels


def _boundary_band_energy(grid: list[list[float]]) -> float:
    if not grid:
        return 0.0
    height = len(grid)
    width = len(grid[0]) if grid[0] else 0
    return sum(
        float(value) * float(value)
        for row_index, row in enumerate(grid)
        for col_index, value in enumerate(row)
        if row_index in {0, height - 1} or col_index in {0, width - 1}
    )


def _summarize_compact_channels(channels: dict[str, list[list[float]]]) -> JsonDict:
    compact = _channels(channels)
    summaries: JsonDict = {}
    for name, grid in compact.items():
        energy = 0.0
        weighted_x = 0.0
        weighted_y = 0.0
        support: list[list[int]] = []
        for row_index, row in enumerate(grid):
            for col_index, value in enumerate(row):
                weight = float(value) * float(value)
                energy += weight
                if abs(float(value)) > 1e-12:
                    support.append([col_index, row_index])
                    weighted_x += col_index * weight
                    weighted_y += row_index * weight
        if support:
            min_x = min(cell[0] for cell in support)
            min_y = min(cell[1] for cell in support)
            max_x = max(cell[0] for cell in support)
            max_y = max(cell[1] for cell in support)
            centroid = [weighted_x / energy, weighted_y / energy] if energy else [0.0, 0.0]
            component_count = 1
        else:
            min_x = min_y = max_x = max_y = 0
            centroid = [0.0, 0.0]
            component_count = 0
        summaries[name] = {
            "energy": energy,
            "centroid_grid": centroid,
            "support_bounds_grid": [min_x, min_y, max_x, max_y],
            "boundary_band_energy": _boundary_band_energy(grid),
            "component_count": component_count,
            "mode_signature": f"mode::{name}:{len(grid)}x{len(grid[0]) if grid else 0}",
        }
    return {"channels": summaries}


def _validate_non_authority(is_authority_state: bool, name: str) -> None:
    if _bool(is_authority_state):
        raise ValueError(f"{name} cannot be authority state.")


def _validate_tick_range(tick_range: list[Any], name: str) -> None:
    if len(tick_range) != 2 or int(tick_range[1]) < int(tick_range[0]):
        raise ValueError(f"{name} tick_range must contain [start, end].")


def _validate_bounds4(value: list[Any], name: str) -> None:
    if len(value) != 4:
        raise ValueError(f"{name} must contain [x0, y0, x1, y1].")
    if float(value[2]) < float(value[0]) or float(value[3]) < float(value[1]):
        raise ValueError(f"{name} has invalid bounds.")


def _validate_coordinate_frame(coordinate_frame: JsonDict) -> None:
    required = {
        "world_origin",
        "world_extent",
        "grid_shape",
        "world_to_grid",
        "grid_to_world",
        "source_observer_window",
    }
    missing = sorted(required - set(coordinate_frame))
    if missing:
        raise ValueError("coordinate_frame missing required fields: " + ", ".join(missing))


def _has_field_or_snapshot_lineage(field_ids: list[Any], snapshot_ids: list[Any]) -> bool:
    return bool(_list(field_ids) or _list(snapshot_ids))


def _validate_mode_signature(mode_signature: Any) -> None:
    if not isinstance(mode_signature, dict):
        raise ValueError("mode_signature must be a dict.")
    if not isinstance(mode_signature.get("bucket_vector"), list) or not mode_signature["bucket_vector"]:
        raise ValueError("mode_signature requires non-empty bucket_vector.")
    if not isinstance(mode_signature.get("digest"), str) or not mode_signature["digest"]:
        raise ValueError("mode_signature requires digest.")


def _validate_effective_properties(properties: JsonDict) -> None:
    missing = sorted(MATERIAL_EFFECTIVE_PROPERTY_KEYS - set(properties))
    if missing:
        raise ValueError("effective properties missing required fields: " + ", ".join(missing))
    _validate_mode_signature(properties["mode_signature"])
    for key in MATERIAL_EFFECTIVE_PROPERTY_KEYS - {"mode_signature", "stability_window"}:
        if not isfinite(float(properties[key])):
            raise ValueError(f"effective property {key} must be finite.")
    _validate_tick_range(_list(properties["stability_window"]), "effective property stability_window")


def _validate_probe_summary(summary: JsonDict) -> None:
    required = {
        "probe_protocol",
        "probe_tick_range",
        "probe_region_grid",
        "probe_region_world",
        "probe_source_record_ids",
        "probe_wave_step_record_ids",
        "probe_affordance_command_ids",
    }
    missing = sorted(required - set(summary))
    if missing:
        raise ValueError("response probe summary missing required fields: " + ", ".join(missing))
    if summary["probe_protocol"] not in {"passive_history_probe_v1", "controlled_affordance_probe_v1"}:
        raise ValueError("unsupported material response probe protocol.")
    _validate_tick_range(_list(summary["probe_tick_range"]), "response probe")
    _validate_bounds4(_list(summary["probe_region_grid"]), "probe_region_grid")
    _validate_bounds4(_list(summary["probe_region_world"]), "probe_region_world")
    if not _list(summary["probe_source_record_ids"]) or not _list(summary["probe_wave_step_record_ids"]):
        raise ValueError("response probe requires source and wave step lineage.")


def _validate_material_validity_envelope(envelope: JsonDict) -> None:
    required = {
        "tick_range",
        "region_ids",
        "observer_resolution_limit",
        "interaction_strength_limit",
        "support_bounds_grid",
        "support_bounds_world",
    }
    missing = sorted(required - set(envelope))
    if missing:
        raise ValueError("material validity_envelope missing required fields: " + ", ".join(missing))
    _validate_tick_range(_list(envelope["tick_range"]), "material validity envelope")
    if not _list(envelope["region_ids"]):
        raise ValueError("material validity_envelope requires region_ids.")
    if float(envelope["observer_resolution_limit"]) <= 0:
        raise ValueError("observer_resolution_limit must be positive.")
    if float(envelope["interaction_strength_limit"]) < 0:
        raise ValueError("interaction_strength_limit must be non-negative.")
    _validate_bounds4(_list(envelope["support_bounds_grid"]), "support_bounds_grid")
    _validate_bounds4(_list(envelope["support_bounds_world"]), "support_bounds_world")


def _profile_digest_payload(data: JsonDict) -> JsonDict:
    return {
        "property_values": _dict(data.get("property_values")),
        "behavior_class": data.get("behavior_class"),
        "behavior_thresholds": _dict(data.get("behavior_thresholds")),
        "effective_property_digest": data.get("effective_property_digest"),
        "source_macro_material_state_id": data.get("source_macro_material_state_id"),
        "source_material_body_id": data.get("source_material_body_id"),
        "source_species_certificate_ids": _list(data.get("source_species_certificate_ids")),
        "derivation_method": data.get("derivation_method", "legacy_macro_threshold_scaffold_v1"),
        "source_substrate_measurement_record_ids": _list(data.get("source_substrate_measurement_record_ids")),
        "source_derived_property_record_ids": _list(data.get("source_derived_property_record_ids")),
        "scaffold_status": data.get("scaffold_status", "stage1_scaffold"),
        "source_record_ids": _list(data.get("source_record_ids")),
    }


def material_behavior_profile_digest(data: JsonDict) -> str:
    return _canonical_json_digest(_profile_digest_payload(data))


def _zone_digest_payload(data: JsonDict) -> JsonDict:
    return {
        "material_behavior_profile_id": data.get("material_behavior_profile_id"),
        "source_macro_material_state_id": data.get("source_macro_material_state_id"),
        "source_material_body_id": data.get("source_material_body_id"),
        "region_id": data.get("region_id"),
        "region_bounds_grid": _list(data.get("region_bounds_grid")),
        "region_bounds_world": _list(data.get("region_bounds_world")),
        "tick_range": _list(data.get("tick_range")),
        "behavior_class": data.get("behavior_class"),
        "zone_role": data.get("zone_role"),
        "source_record_ids": _list(data.get("source_record_ids")),
    }


def material_environment_zone_digest(data: JsonDict) -> str:
    return _canonical_json_digest(_zone_digest_payload(data))


def _validate_behavior_values(values: JsonDict) -> None:
    missing = sorted(MATERIAL_BEHAVIOR_PROPERTY_KEYS - set(values))
    if missing:
        raise ValueError("material behavior property_values missing required fields: " + ", ".join(missing))
    for key in MATERIAL_BEHAVIOR_PROPERTY_KEYS:
        value = float(values[key])
        if not isfinite(value) or value < 0.0 or value > 1.0:
            raise ValueError(f"material behavior property {key} must be finite and in [0, 1].")


def _validate_external_exchange(summary: JsonDict) -> None:
    required = {
        "exchange_id",
        "exchange_type",
        "signed_amount",
        "source_system",
        "sink_system",
        "conservation_tolerance",
        "pre_exchange_energy_like",
        "post_exchange_energy_like",
        "source_record_ids",
    }
    missing = sorted(required - set(summary))
    if missing:
        raise ValueError("external exchange summary missing required fields: " + ", ".join(missing))
    if summary["exchange_type"] not in MATERIAL_EXTERNAL_EXCHANGE_TYPES:
        raise ValueError(f"Unsupported material external exchange type: {summary['exchange_type']!r}.")
    if not isfinite(float(summary["signed_amount"])):
        raise ValueError("external exchange signed_amount must be finite.")
    if float(summary["conservation_tolerance"]) > 1e-6:
        raise ValueError("external exchange conservation_tolerance exceeds deterministic test limit.")
    if not _list(summary["source_record_ids"]):
        raise ValueError("external exchange requires source_record_ids.")


def _reject_authority_semantic_labels(value: Any, path: str = "payload") -> None:
    if isinstance(value, dict):
        if "css_color" in value or "viewer_label" in value:
            raise ValueError(f"{path} cannot use viewer labels or CSS as substrate authority.")
        if ("real_material_name" in value or "real_element_symbol" in value) and (
            value.get("external_mapping_status") != "experimental_non_authority"
        ):
            raise ValueError(f"{path} cannot use real material names as authority.")
        for key, child in value.items():
            _reject_authority_semantic_labels(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_authority_semantic_labels(child, f"{path}[{index}]")


def _measurement_digest_payload(data: JsonDict) -> JsonDict:
    return {
        "source_authority_kind": data.get("source_authority_kind"),
        "source_field_state_id": data.get("source_field_state_id"),
        "source_fine_patch_snapshot_id": data.get("source_fine_patch_snapshot_id"),
        "source_material_patch_snapshot_id": data.get("source_material_patch_snapshot_id"),
        "source_hypergraph_state_snapshot_id": data.get("source_hypergraph_state_snapshot_id"),
        "world_substrate_record_id": data.get("world_substrate_record_id"),
        "region_grid": _list(data.get("region_grid")),
        "frequency_band_metrics": _dict(data.get("frequency_band_metrics")),
        "local_graph_metrics": _dict(data.get("local_graph_metrics")),
        "standard_perturbation_id": data.get("standard_perturbation_id"),
        "source_record_ids": _list(data.get("source_record_ids")),
    }


def _property_digest_payload(data: JsonDict) -> JsonDict:
    return {
        "source_substrate_measurement_record_ids": _list(data.get("source_substrate_measurement_record_ids")),
        "density_signature": _dict(data.get("density_signature")),
        "inertia_signature": _dict(data.get("inertia_signature")),
        "rigidity_signature": _dict(data.get("rigidity_signature")),
        "damping_signature": _dict(data.get("damping_signature")),
        "permeability_signature": _dict(data.get("permeability_signature")),
        "transport_signature": _dict(data.get("transport_signature")),
        "granular_signature": _dict(data.get("granular_signature")),
        "spectral_response": _dict(data.get("spectral_response")),
        "dense_link_signature": _dict(data.get("dense_link_signature")),
        "source_record_ids": _list(data.get("source_record_ids")),
    }


def _property_runtime_binding_digest_payload(data: JsonDict) -> JsonDict:
    return {
        "tick_range": _list(data.get("tick_range")),
        "zone_id": data.get("zone_id"),
        "material_behavior_profile_id": data.get("material_behavior_profile_id"),
        "macro_material_state_id": data.get("macro_material_state_id"),
        "material_body_id": data.get("material_body_id"),
        "derived_material_property_record_id": data.get("derived_material_property_record_id"),
        "source_substrate_measurement_record_ids": _list(data.get("source_substrate_measurement_record_ids")),
        "property_digest": data.get("property_digest"),
        "property_record_tick": data.get("property_record_tick"),
        "max_tick_lag": data.get("max_tick_lag"),
        "coordinate_frame": _dict(data.get("coordinate_frame")),
        "region_bounds_grid": _list(data.get("region_bounds_grid")),
        "region_bounds_world": _list(data.get("region_bounds_world")),
        "binding_thresholds": _dict(data.get("binding_thresholds")),
        "source_record_ids": _list(data.get("source_record_ids")),
    }


def material_property_runtime_binding_digest(data: JsonDict) -> str:
    return _canonical_json_digest(_property_runtime_binding_digest_payload(data))


def _baseline_metrics_digest_payload(data: JsonDict) -> JsonDict:
    return _dict(data.get("baseline_metrics"))


def material_response_baseline_digest(data: JsonDict) -> str:
    return _canonical_json_digest(_baseline_metrics_digest_payload(data))


def _hypergraph_state_digest_payload(data: JsonDict) -> JsonDict:
    return {
        "tick": data.get("tick"),
        "rule_id": data.get("rule_id"),
        "node_count": data.get("node_count"),
        "hyperedges": _list(data.get("hyperedges")),
        "local_motif_summary": _dict(data.get("local_motif_summary")),
        "component_summary": _dict(data.get("component_summary")),
        "source_record_ids": _list(data.get("source_record_ids")),
    }


def _validate_hypergraph_claim_scope(claim_scope: str) -> None:
    if claim_scope != "experimental_substrate_only":
        raise ValueError("Hypergraph substrate records must use claim_scope='experimental_substrate_only'.")


@dataclass
class WorldSubstrateRecord:
    record_id: str
    run_id: str
    tick_range: list[int]
    substrate_type: str
    substrate_rule_id: str
    frequency_channel_names: list[str]
    coupling_channel_names: list[str]
    propagation_speed_limit_grid_per_tick: float
    coordinate_frame: JsonDict
    source_field_state_ids: list[str]
    source_hypergraph_state_snapshot_ids: list[str]
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.tick_range = _list(self.tick_range)
        self.frequency_channel_names = _list(self.frequency_channel_names)
        self.coupling_channel_names = _list(self.coupling_channel_names)
        self.coordinate_frame = _dict(self.coordinate_frame)
        self.source_field_state_ids = _list(self.source_field_state_ids)
        self.source_hypergraph_state_snapshot_ids = _list(self.source_hypergraph_state_snapshot_ids)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "WorldSubstrateRecord")
        if not self.record_id or not self.run_id or not self.substrate_rule_id:
            raise ValueError("WorldSubstrateRecord requires record/run/rule ids.")
        if self.substrate_type not in SUBSTRATE_TYPES:
            raise ValueError(f"Unsupported substrate_type: {self.substrate_type!r}.")
        _validate_tick_range(self.tick_range, "WorldSubstrateRecord")
        if float(self.propagation_speed_limit_grid_per_tick) <= 0:
            raise ValueError("WorldSubstrateRecord propagation speed limit must be positive.")
        _validate_coordinate_frame(self.coordinate_frame)
        if self.substrate_type == "field_frequency_grid_v1" and not self.source_field_state_ids:
            raise ValueError("field_frequency_grid_v1 substrate requires source_field_state_ids.")
        if self.substrate_type == "hypergraph_rewrite_v1" and not self.source_hypergraph_state_snapshot_ids:
            raise ValueError("hypergraph_rewrite_v1 substrate requires source_hypergraph_state_snapshot_ids.")
        if not self.source_record_ids:
            raise ValueError("WorldSubstrateRecord requires source_record_ids.")

    def to_dict(self) -> JsonDict:
        return {
            "record_id": self.record_id,
            "run_id": self.run_id,
            "tick_range": _list(self.tick_range),
            "substrate_type": self.substrate_type,
            "substrate_rule_id": self.substrate_rule_id,
            "frequency_channel_names": _list(self.frequency_channel_names),
            "coupling_channel_names": _list(self.coupling_channel_names),
            "propagation_speed_limit_grid_per_tick": self.propagation_speed_limit_grid_per_tick,
            "coordinate_frame": _dict(self.coordinate_frame),
            "source_field_state_ids": _list(self.source_field_state_ids),
            "source_hypergraph_state_snapshot_ids": _list(self.source_hypergraph_state_snapshot_ids),
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "WorldSubstrateRecord":
        return cls(
            record_id=data["record_id"],
            run_id=data["run_id"],
            tick_range=_list(data["tick_range"]),
            substrate_type=data["substrate_type"],
            substrate_rule_id=data["substrate_rule_id"],
            frequency_channel_names=_list(data.get("frequency_channel_names")),
            coupling_channel_names=_list(data.get("coupling_channel_names")),
            propagation_speed_limit_grid_per_tick=data["propagation_speed_limit_grid_per_tick"],
            coordinate_frame=_dict(data["coordinate_frame"]),
            source_field_state_ids=_list(data.get("source_field_state_ids")),
            source_hypergraph_state_snapshot_ids=_list(data.get("source_hypergraph_state_snapshot_ids")),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class SubstrateMeasurementRecord:
    record_id: str
    run_id: str
    tick: int
    source_authority_kind: str
    source_field_state_id: str | None
    source_fine_patch_snapshot_id: str | None
    source_material_patch_snapshot_id: str | None
    source_hypergraph_state_snapshot_id: str | None
    world_substrate_record_id: str
    region_grid: list[float]
    frequency_band_metrics: JsonDict
    local_graph_metrics: JsonDict
    standard_perturbation_id: str
    measurement_digest: str
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.region_grid = _list(self.region_grid)
        self.frequency_band_metrics = _dict(self.frequency_band_metrics)
        self.local_graph_metrics = _dict(self.local_graph_metrics)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "SubstrateMeasurementRecord")
        if not self.record_id or not self.run_id or not self.world_substrate_record_id:
            raise ValueError("SubstrateMeasurementRecord requires record/run/substrate ids.")
        if self.source_authority_kind not in SUBSTRATE_MEASUREMENT_SOURCE_KINDS:
            raise ValueError(f"Unsupported substrate measurement source_authority_kind: {self.source_authority_kind!r}.")
        sources = {
            "field_state": self.source_field_state_id,
            "fine_patch_snapshot": self.source_fine_patch_snapshot_id,
            "material_patch_snapshot": self.source_material_patch_snapshot_id,
            "hypergraph_state_snapshot": self.source_hypergraph_state_snapshot_id,
        }
        present = [kind for kind, value in sources.items() if value]
        if len(present) != 1 or present[0] != self.source_authority_kind:
            raise ValueError("SubstrateMeasurementRecord requires exactly one matching source authority id.")
        _validate_bounds4(self.region_grid, "region_grid")
        if not self.standard_perturbation_id:
            raise ValueError("SubstrateMeasurementRecord requires standard_perturbation_id.")
        if not self.source_record_ids:
            raise ValueError("SubstrateMeasurementRecord requires source_record_ids.")
        _reject_authority_semantic_labels(self.frequency_band_metrics, "frequency_band_metrics")
        _reject_authority_semantic_labels(self.local_graph_metrics, "local_graph_metrics")
        expected = _canonical_json_digest(_measurement_digest_payload(self.to_dict(include_digest=False)))
        if self.measurement_digest != expected:
            raise ValueError("SubstrateMeasurementRecord measurement_digest mismatch.")

    def to_dict(self, *, include_digest: bool = True) -> JsonDict:
        data = {
            "record_id": self.record_id,
            "run_id": self.run_id,
            "tick": self.tick,
            "source_authority_kind": self.source_authority_kind,
            "source_field_state_id": self.source_field_state_id,
            "source_fine_patch_snapshot_id": self.source_fine_patch_snapshot_id,
            "source_material_patch_snapshot_id": self.source_material_patch_snapshot_id,
            "source_hypergraph_state_snapshot_id": self.source_hypergraph_state_snapshot_id,
            "world_substrate_record_id": self.world_substrate_record_id,
            "region_grid": _list(self.region_grid),
            "frequency_band_metrics": _dict(self.frequency_band_metrics),
            "local_graph_metrics": _dict(self.local_graph_metrics),
            "standard_perturbation_id": self.standard_perturbation_id,
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }
        if include_digest:
            data["measurement_digest"] = self.measurement_digest
        return data

    @classmethod
    def from_dict(cls, data: JsonDict) -> "SubstrateMeasurementRecord":
        return cls(
            record_id=data["record_id"],
            run_id=data["run_id"],
            tick=data["tick"],
            source_authority_kind=data["source_authority_kind"],
            source_field_state_id=data.get("source_field_state_id"),
            source_fine_patch_snapshot_id=data.get("source_fine_patch_snapshot_id"),
            source_material_patch_snapshot_id=data.get("source_material_patch_snapshot_id"),
            source_hypergraph_state_snapshot_id=data.get("source_hypergraph_state_snapshot_id"),
            world_substrate_record_id=data["world_substrate_record_id"],
            region_grid=_list(data["region_grid"]),
            frequency_band_metrics=_dict(data.get("frequency_band_metrics")),
            local_graph_metrics=_dict(data.get("local_graph_metrics")),
            standard_perturbation_id=data["standard_perturbation_id"],
            measurement_digest=data["measurement_digest"],
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class DerivedMaterialPropertyRecord:
    record_id: str
    run_id: str
    tick: int
    source_substrate_measurement_record_ids: list[str]
    density_signature: JsonDict
    inertia_signature: JsonDict
    rigidity_signature: JsonDict
    damping_signature: JsonDict
    permeability_signature: JsonDict
    transport_signature: JsonDict
    granular_signature: JsonDict
    spectral_response: JsonDict
    dense_link_signature: JsonDict
    property_digest: str
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.source_substrate_measurement_record_ids = _list(self.source_substrate_measurement_record_ids)
        self.density_signature = _dict(self.density_signature)
        self.inertia_signature = _dict(self.inertia_signature)
        self.rigidity_signature = _dict(self.rigidity_signature)
        self.damping_signature = _dict(self.damping_signature)
        self.permeability_signature = _dict(self.permeability_signature)
        self.transport_signature = _dict(self.transport_signature)
        self.granular_signature = _dict(self.granular_signature)
        self.spectral_response = _dict(self.spectral_response)
        self.dense_link_signature = _dict(self.dense_link_signature)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "DerivedMaterialPropertyRecord")
        if not self.record_id or not self.run_id:
            raise ValueError("DerivedMaterialPropertyRecord requires record/run ids.")
        if not self.source_substrate_measurement_record_ids or not self.source_record_ids:
            raise ValueError("DerivedMaterialPropertyRecord requires source measurement and record lineage.")
        for name in [
            "density_signature",
            "inertia_signature",
            "rigidity_signature",
            "damping_signature",
            "permeability_signature",
            "transport_signature",
            "granular_signature",
            "spectral_response",
            "dense_link_signature",
        ]:
            _reject_authority_semantic_labels(getattr(self, name), name)
        expected = _canonical_json_digest(_property_digest_payload(self.to_dict(include_digest=False)))
        if self.property_digest != expected:
            raise ValueError("DerivedMaterialPropertyRecord property_digest mismatch.")

    def to_dict(self, *, include_digest: bool = True) -> JsonDict:
        data = {
            "record_id": self.record_id,
            "run_id": self.run_id,
            "tick": self.tick,
            "source_substrate_measurement_record_ids": _list(self.source_substrate_measurement_record_ids),
            "density_signature": _dict(self.density_signature),
            "inertia_signature": _dict(self.inertia_signature),
            "rigidity_signature": _dict(self.rigidity_signature),
            "damping_signature": _dict(self.damping_signature),
            "permeability_signature": _dict(self.permeability_signature),
            "transport_signature": _dict(self.transport_signature),
            "granular_signature": _dict(self.granular_signature),
            "spectral_response": _dict(self.spectral_response),
            "dense_link_signature": _dict(self.dense_link_signature),
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }
        if include_digest:
            data["property_digest"] = self.property_digest
        return data

    @classmethod
    def from_dict(cls, data: JsonDict) -> "DerivedMaterialPropertyRecord":
        return cls(
            record_id=data["record_id"],
            run_id=data["run_id"],
            tick=data["tick"],
            source_substrate_measurement_record_ids=_list(data["source_substrate_measurement_record_ids"]),
            density_signature=_dict(data["density_signature"]),
            inertia_signature=_dict(data["inertia_signature"]),
            rigidity_signature=_dict(data["rigidity_signature"]),
            damping_signature=_dict(data["damping_signature"]),
            permeability_signature=_dict(data["permeability_signature"]),
            transport_signature=_dict(data["transport_signature"]),
            granular_signature=_dict(data["granular_signature"]),
            spectral_response=_dict(data["spectral_response"]),
            dense_link_signature=_dict(data["dense_link_signature"]),
            property_digest=data["property_digest"],
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class MaterialPropertyRuntimeBindingRecord:
    binding_id: str
    run_id: str
    tick_range: list[int]
    zone_id: str
    material_behavior_profile_id: str
    macro_material_state_id: str
    material_body_id: str
    derived_material_property_record_id: str
    source_substrate_measurement_record_ids: list[str]
    property_digest: str
    property_record_tick: int
    max_tick_lag: int
    coordinate_frame: JsonDict
    region_bounds_grid: list[float]
    region_bounds_world: list[float]
    binding_thresholds: JsonDict
    source_record_ids: list[str]
    binding_digest: str
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.tick_range = _list(self.tick_range)
        self.source_substrate_measurement_record_ids = _list(self.source_substrate_measurement_record_ids)
        self.coordinate_frame = _dict(self.coordinate_frame)
        self.region_bounds_grid = _list(self.region_bounds_grid)
        self.region_bounds_world = _list(self.region_bounds_world)
        self.binding_thresholds = _dict(self.binding_thresholds)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "MaterialPropertyRuntimeBindingRecord")
        _validate_tick_range(self.tick_range, "MaterialPropertyRuntimeBindingRecord")
        _validate_coordinate_frame(self.coordinate_frame)
        _validate_bounds4(self.region_bounds_grid, "region_bounds_grid")
        _validate_bounds4(self.region_bounds_world, "region_bounds_world")
        required_ids = [
            self.binding_id,
            self.run_id,
            self.zone_id,
            self.material_behavior_profile_id,
            self.macro_material_state_id,
            self.material_body_id,
            self.derived_material_property_record_id,
            self.property_digest,
        ]
        if any(not value for value in required_ids):
            raise ValueError("MaterialPropertyRuntimeBindingRecord missing required lineage.")
        if not self.source_substrate_measurement_record_ids or not self.source_record_ids:
            raise ValueError("MaterialPropertyRuntimeBindingRecord requires property and measurement lineage.")
        if int(self.max_tick_lag) < 0:
            raise ValueError("MaterialPropertyRuntimeBindingRecord max_tick_lag must be non-negative.")
        if int(self.property_record_tick) > int(self.tick_range[1]):
            raise ValueError("MaterialPropertyRuntimeBindingRecord property tick cannot be after binding tick_range.")
        if int(self.tick_range[0]) - int(self.property_record_tick) > int(self.max_tick_lag):
            raise ValueError("MaterialPropertyRuntimeBindingRecord property tick is outside max_tick_lag.")
        if self.derived_material_property_record_id not in self.source_record_ids:
            raise ValueError("MaterialPropertyRuntimeBindingRecord source_record_ids must include property record id.")
        for measurement_id in self.source_substrate_measurement_record_ids:
            if measurement_id not in self.source_record_ids:
                raise ValueError("MaterialPropertyRuntimeBindingRecord source_record_ids must include measurement ids.")
        _reject_authority_semantic_labels(self.binding_thresholds, "binding_thresholds")
        expected = material_property_runtime_binding_digest(self.to_dict(include_digest=False))
        if self.binding_digest != expected:
            raise ValueError("MaterialPropertyRuntimeBindingRecord binding_digest mismatch.")

    def to_dict(self, *, include_digest: bool = True) -> JsonDict:
        data = {
            "binding_id": self.binding_id,
            "run_id": self.run_id,
            "tick_range": _list(self.tick_range),
            "zone_id": self.zone_id,
            "material_behavior_profile_id": self.material_behavior_profile_id,
            "macro_material_state_id": self.macro_material_state_id,
            "material_body_id": self.material_body_id,
            "derived_material_property_record_id": self.derived_material_property_record_id,
            "source_substrate_measurement_record_ids": _list(self.source_substrate_measurement_record_ids),
            "property_digest": self.property_digest,
            "property_record_tick": self.property_record_tick,
            "max_tick_lag": self.max_tick_lag,
            "coordinate_frame": _dict(self.coordinate_frame),
            "region_bounds_grid": _list(self.region_bounds_grid),
            "region_bounds_world": _list(self.region_bounds_world),
            "binding_thresholds": _dict(self.binding_thresholds),
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }
        if include_digest:
            data["binding_digest"] = self.binding_digest
        return data

    @classmethod
    def from_dict(cls, data: JsonDict) -> "MaterialPropertyRuntimeBindingRecord":
        return cls(
            binding_id=data["binding_id"],
            run_id=data["run_id"],
            tick_range=_list(data["tick_range"]),
            zone_id=data["zone_id"],
            material_behavior_profile_id=data["material_behavior_profile_id"],
            macro_material_state_id=data["macro_material_state_id"],
            material_body_id=data["material_body_id"],
            derived_material_property_record_id=data["derived_material_property_record_id"],
            source_substrate_measurement_record_ids=_list(data["source_substrate_measurement_record_ids"]),
            property_digest=data["property_digest"],
            property_record_tick=data["property_record_tick"],
            max_tick_lag=data["max_tick_lag"],
            coordinate_frame=_dict(data["coordinate_frame"]),
            region_bounds_grid=_list(data["region_bounds_grid"]),
            region_bounds_world=_list(data["region_bounds_world"]),
            binding_thresholds=_dict(data.get("binding_thresholds")),
            source_record_ids=_list(data["source_record_ids"]),
            binding_digest=data["binding_digest"],
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class MaterialResponseBaselineRecord:
    baseline_record_id: str
    run_id: str
    case_id: str
    source_package_name: str
    seed_salt: str
    grid_shape: list[int]
    tick_count: int
    source_authority_kind: str
    source_field_state_id: str | None
    source_fine_patch_snapshot_id: str | None
    source_material_patch_snapshot_id: str | None
    source_hypergraph_state_snapshot_id: str | None
    baseline_metrics: JsonDict
    baseline_metrics_digest: str
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.grid_shape = [int(value) for value in _list(self.grid_shape)]
        self.tick_count = int(self.tick_count)
        self.baseline_metrics = _dict(self.baseline_metrics)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "MaterialResponseBaselineRecord")
        if not self.baseline_record_id or not self.run_id or not self.case_id:
            raise ValueError("MaterialResponseBaselineRecord requires baseline/run/case ids.")
        if not self.source_package_name or not self.seed_salt:
            raise ValueError("MaterialResponseBaselineRecord requires package and seed metadata.")
        if len(self.grid_shape) != 2 or any(value <= 0 for value in self.grid_shape):
            raise ValueError("MaterialResponseBaselineRecord grid_shape must contain two positive integers.")
        if self.tick_count <= 0:
            raise ValueError("MaterialResponseBaselineRecord tick_count must be positive.")
        if self.source_authority_kind not in {
            "field_state",
            "fine_patch_snapshot",
            "material_patch_snapshot",
            "hypergraph_state_snapshot",
        }:
            raise ValueError(f"Unsupported baseline source_authority_kind: {self.source_authority_kind!r}.")
        source_refs = [
            self.source_field_state_id,
            self.source_fine_patch_snapshot_id,
            self.source_material_patch_snapshot_id,
            self.source_hypergraph_state_snapshot_id,
        ]
        if sum(1 for ref in source_refs if ref) != 1:
            raise ValueError("MaterialResponseBaselineRecord requires exactly one source state reference.")
        expected_source_id = {
            "field_state": self.source_field_state_id,
            "fine_patch_snapshot": self.source_fine_patch_snapshot_id,
            "material_patch_snapshot": self.source_material_patch_snapshot_id,
            "hypergraph_state_snapshot": self.source_hypergraph_state_snapshot_id,
        }[self.source_authority_kind]
        if expected_source_id not in self.source_record_ids:
            raise ValueError("MaterialResponseBaselineRecord source_record_ids must include source state id.")
        if not self.baseline_metrics:
            raise ValueError("MaterialResponseBaselineRecord requires baseline_metrics.")
        expected = material_response_baseline_digest(self.to_dict(include_digest=False))
        if self.baseline_metrics_digest != expected:
            raise ValueError("MaterialResponseBaselineRecord baseline_metrics_digest mismatch.")

    def to_dict(self, *, include_digest: bool = True) -> JsonDict:
        data = {
            "baseline_record_id": self.baseline_record_id,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "source_package_name": self.source_package_name,
            "seed_salt": self.seed_salt,
            "grid_shape": list(self.grid_shape),
            "tick_count": self.tick_count,
            "source_authority_kind": self.source_authority_kind,
            "source_field_state_id": self.source_field_state_id,
            "source_fine_patch_snapshot_id": self.source_fine_patch_snapshot_id,
            "source_material_patch_snapshot_id": self.source_material_patch_snapshot_id,
            "source_hypergraph_state_snapshot_id": self.source_hypergraph_state_snapshot_id,
            "baseline_metrics": _dict(self.baseline_metrics),
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }
        if include_digest:
            data["baseline_metrics_digest"] = self.baseline_metrics_digest
        return data

    @classmethod
    def from_dict(cls, data: JsonDict) -> "MaterialResponseBaselineRecord":
        return cls(
            baseline_record_id=data["baseline_record_id"],
            run_id=data["run_id"],
            case_id=data["case_id"],
            source_package_name=data["source_package_name"],
            seed_salt=data["seed_salt"],
            grid_shape=_list(data["grid_shape"]),
            tick_count=data["tick_count"],
            source_authority_kind=data["source_authority_kind"],
            source_field_state_id=data.get("source_field_state_id"),
            source_fine_patch_snapshot_id=data.get("source_fine_patch_snapshot_id"),
            source_material_patch_snapshot_id=data.get("source_material_patch_snapshot_id"),
            source_hypergraph_state_snapshot_id=data.get("source_hypergraph_state_snapshot_id"),
            baseline_metrics=_dict(data["baseline_metrics"]),
            baseline_metrics_digest=data["baseline_metrics_digest"],
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class HypergraphRewriteRuleRecord:
    record_id: str
    run_id: str
    rule_id: str
    lhs_relations: list[list[str]]
    rhs_relations: list[list[str]]
    max_relation_arity: int
    update_order_policy: str
    branching_probe_enabled: bool
    source_record_ids: list[str]
    claim_scope: str = "experimental_substrate_only"
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.lhs_relations = [_list(row) for row in self.lhs_relations]
        self.rhs_relations = [_list(row) for row in self.rhs_relations]
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "HypergraphRewriteRuleRecord")
        _validate_hypergraph_claim_scope(self.claim_scope)
        if not self.record_id or not self.run_id or not self.rule_id:
            raise ValueError("HypergraphRewriteRuleRecord requires record/run/rule ids.")
        if not self.lhs_relations or not self.rhs_relations:
            raise ValueError("HypergraphRewriteRuleRecord requires lhs and rhs relations.")
        if int(self.max_relation_arity) <= 0:
            raise ValueError("HypergraphRewriteRuleRecord max_relation_arity must be positive.")
        if any(len(relation) > int(self.max_relation_arity) for relation in self.lhs_relations + self.rhs_relations):
            raise ValueError("HypergraphRewriteRuleRecord relation exceeds max_relation_arity.")
        if self.update_order_policy not in {"deterministic_first_match_v1", "bounded_multiway_probe_v1"}:
            raise ValueError("Unsupported hypergraph update_order_policy.")
        if not isinstance(self.branching_probe_enabled, bool):
            raise ValueError("HypergraphRewriteRuleRecord branching_probe_enabled must be bool.")
        if not self.source_record_ids:
            raise ValueError("HypergraphRewriteRuleRecord requires source_record_ids.")

    def to_dict(self) -> JsonDict:
        return {
            "record_id": self.record_id,
            "run_id": self.run_id,
            "rule_id": self.rule_id,
            "lhs_relations": [_list(row) for row in self.lhs_relations],
            "rhs_relations": [_list(row) for row in self.rhs_relations],
            "max_relation_arity": self.max_relation_arity,
            "update_order_policy": self.update_order_policy,
            "branching_probe_enabled": self.branching_probe_enabled,
            "source_record_ids": _list(self.source_record_ids),
            "claim_scope": self.claim_scope,
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "HypergraphRewriteRuleRecord":
        return cls(
            record_id=data["record_id"],
            run_id=data["run_id"],
            rule_id=data["rule_id"],
            lhs_relations=[_list(row) for row in data["lhs_relations"]],
            rhs_relations=[_list(row) for row in data["rhs_relations"]],
            max_relation_arity=data["max_relation_arity"],
            update_order_policy=data["update_order_policy"],
            branching_probe_enabled=data.get("branching_probe_enabled", False),
            source_record_ids=_list(data["source_record_ids"]),
            claim_scope=data.get("claim_scope", "experimental_substrate_only"),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class HypergraphStateSnapshot:
    snapshot_id: str
    run_id: str
    tick: int
    rule_id: str
    node_count: int
    hyperedges: list[list[str]]
    local_motif_summary: JsonDict
    component_summary: JsonDict
    state_digest: str
    source_record_ids: list[str]
    claim_scope: str = "experimental_substrate_only"
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.hyperedges = [_list(edge) for edge in self.hyperedges]
        self.local_motif_summary = _dict(self.local_motif_summary)
        self.component_summary = _dict(self.component_summary)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "HypergraphStateSnapshot")
        _validate_hypergraph_claim_scope(self.claim_scope)
        if not self.snapshot_id or not self.run_id or not self.rule_id:
            raise ValueError("HypergraphStateSnapshot requires snapshot/run/rule ids.")
        if int(self.node_count) < 0:
            raise ValueError("HypergraphStateSnapshot node_count must be non-negative.")
        if not self.source_record_ids:
            raise ValueError("HypergraphStateSnapshot requires source_record_ids.")
        expected = _canonical_json_digest(_hypergraph_state_digest_payload(self.to_dict(include_digest=False)))
        if self.state_digest != expected:
            raise ValueError("HypergraphStateSnapshot state_digest mismatch.")

    def to_dict(self, *, include_digest: bool = True) -> JsonDict:
        data = {
            "snapshot_id": self.snapshot_id,
            "run_id": self.run_id,
            "tick": self.tick,
            "rule_id": self.rule_id,
            "node_count": self.node_count,
            "hyperedges": [_list(edge) for edge in self.hyperedges],
            "local_motif_summary": _dict(self.local_motif_summary),
            "component_summary": _dict(self.component_summary),
            "source_record_ids": _list(self.source_record_ids),
            "claim_scope": self.claim_scope,
            "is_authority_state": self.is_authority_state,
        }
        if include_digest:
            data["state_digest"] = self.state_digest
        return data

    @classmethod
    def from_dict(cls, data: JsonDict) -> "HypergraphStateSnapshot":
        return cls(
            snapshot_id=data["snapshot_id"],
            run_id=data["run_id"],
            tick=data["tick"],
            rule_id=data["rule_id"],
            node_count=data["node_count"],
            hyperedges=[_list(edge) for edge in data.get("hyperedges", [])],
            local_motif_summary=_dict(data.get("local_motif_summary")),
            component_summary=_dict(data.get("component_summary")),
            state_digest=data["state_digest"],
            source_record_ids=_list(data["source_record_ids"]),
            claim_scope=data.get("claim_scope", "experimental_substrate_only"),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class HypergraphCausalGraphRecord:
    record_id: str
    run_id: str
    tick_range: list[int]
    rule_id: str
    source_snapshot_ids: list[str]
    event_count: int
    causal_edges: list[list[str]]
    causal_cone_metrics: JsonDict
    branch_reconvergence_metrics: JsonDict
    dense_link_metrics: JsonDict
    source_record_ids: list[str]
    claim_scope: str = "experimental_substrate_only"
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.tick_range = _list(self.tick_range)
        self.source_snapshot_ids = _list(self.source_snapshot_ids)
        self.causal_edges = [_list(edge) for edge in self.causal_edges]
        self.causal_cone_metrics = _dict(self.causal_cone_metrics)
        self.branch_reconvergence_metrics = _dict(self.branch_reconvergence_metrics)
        self.dense_link_metrics = _dict(self.dense_link_metrics)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "HypergraphCausalGraphRecord")
        _validate_hypergraph_claim_scope(self.claim_scope)
        if not self.record_id or not self.run_id or not self.rule_id:
            raise ValueError("HypergraphCausalGraphRecord requires record/run/rule ids.")
        _validate_tick_range(self.tick_range, "HypergraphCausalGraphRecord")
        if not self.source_snapshot_ids or not self.source_record_ids:
            raise ValueError("HypergraphCausalGraphRecord requires snapshot and source record lineage.")
        if int(self.event_count) < 0:
            raise ValueError("HypergraphCausalGraphRecord event_count must be non-negative.")
        if not self.causal_cone_metrics or not self.branch_reconvergence_metrics or not self.dense_link_metrics:
            raise ValueError("HypergraphCausalGraphRecord requires causal, branch, and dense-link metrics.")

    def to_dict(self) -> JsonDict:
        return {
            "record_id": self.record_id,
            "run_id": self.run_id,
            "tick_range": _list(self.tick_range),
            "rule_id": self.rule_id,
            "source_snapshot_ids": _list(self.source_snapshot_ids),
            "event_count": self.event_count,
            "causal_edges": [_list(edge) for edge in self.causal_edges],
            "causal_cone_metrics": _dict(self.causal_cone_metrics),
            "branch_reconvergence_metrics": _dict(self.branch_reconvergence_metrics),
            "dense_link_metrics": _dict(self.dense_link_metrics),
            "source_record_ids": _list(self.source_record_ids),
            "claim_scope": self.claim_scope,
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "HypergraphCausalGraphRecord":
        return cls(
            record_id=data["record_id"],
            run_id=data["run_id"],
            tick_range=_list(data["tick_range"]),
            rule_id=data["rule_id"],
            source_snapshot_ids=_list(data["source_snapshot_ids"]),
            event_count=data["event_count"],
            causal_edges=[_list(edge) for edge in data.get("causal_edges", [])],
            causal_cone_metrics=_dict(data["causal_cone_metrics"]),
            branch_reconvergence_metrics=_dict(data["branch_reconvergence_metrics"]),
            dense_link_metrics=_dict(data["dense_link_metrics"]),
            source_record_ids=_list(data["source_record_ids"]),
            claim_scope=data.get("claim_scope", "experimental_substrate_only"),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class MaterialSpeciesCandidate:
    candidate_id: str
    run_id: str
    tick_range: list[int]
    source_field_state_ids: list[str]
    source_snapshot_ids: list[str]
    source_record_ids: list[str]
    coordinate_frame: JsonDict
    support_bounds_grid: list[float]
    support_bounds_world: list[float]
    raw_channel_summary_digest: str
    effective_property_summary: JsonDict
    response_probe_summary: JsonDict
    mode_signature: JsonDict
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.tick_range = _list(self.tick_range)
        self.source_field_state_ids = _list(self.source_field_state_ids)
        self.source_snapshot_ids = _list(self.source_snapshot_ids)
        self.source_record_ids = _list(self.source_record_ids)
        self.coordinate_frame = _dict(self.coordinate_frame)
        self.support_bounds_grid = _list(self.support_bounds_grid)
        self.support_bounds_world = _list(self.support_bounds_world)
        self.effective_property_summary = _dict(self.effective_property_summary)
        self.response_probe_summary = _dict(self.response_probe_summary)
        self.mode_signature = _dict(self.mode_signature)
        _validate_non_authority(self.is_authority_state, "MaterialSpeciesCandidate")
        if not self.candidate_id:
            raise ValueError("MaterialSpeciesCandidate requires candidate_id.")
        _validate_tick_range(self.tick_range, "MaterialSpeciesCandidate")
        if not _has_field_or_snapshot_lineage(self.source_field_state_ids, self.source_snapshot_ids):
            raise ValueError("MaterialSpeciesCandidate requires field state or snapshot lineage.")
        if not self.source_record_ids:
            raise ValueError("MaterialSpeciesCandidate requires source_record_ids.")
        if not self.raw_channel_summary_digest:
            raise ValueError("MaterialSpeciesCandidate requires raw_channel_summary_digest.")
        _validate_coordinate_frame(self.coordinate_frame)
        _validate_bounds4(self.support_bounds_grid, "support_bounds_grid")
        _validate_bounds4(self.support_bounds_world, "support_bounds_world")
        _validate_effective_properties(self.effective_property_summary)
        _validate_probe_summary(self.response_probe_summary)
        _validate_mode_signature(self.mode_signature)

    def to_dict(self) -> JsonDict:
        return {
            "candidate_id": self.candidate_id,
            "run_id": self.run_id,
            "tick_range": _list(self.tick_range),
            "source_field_state_ids": _list(self.source_field_state_ids),
            "source_snapshot_ids": _list(self.source_snapshot_ids),
            "source_record_ids": _list(self.source_record_ids),
            "coordinate_frame": _dict(self.coordinate_frame),
            "support_bounds_grid": _list(self.support_bounds_grid),
            "support_bounds_world": _list(self.support_bounds_world),
            "raw_channel_summary_digest": self.raw_channel_summary_digest,
            "effective_property_summary": _dict(self.effective_property_summary),
            "response_probe_summary": _dict(self.response_probe_summary),
            "mode_signature": _dict(self.mode_signature),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "MaterialSpeciesCandidate":
        return cls(
            candidate_id=data["candidate_id"],
            run_id=data["run_id"],
            tick_range=_list(data["tick_range"]),
            source_field_state_ids=_list(data.get("source_field_state_ids")),
            source_snapshot_ids=_list(data.get("source_snapshot_ids")),
            source_record_ids=_list(data["source_record_ids"]),
            coordinate_frame=_dict(data["coordinate_frame"]),
            support_bounds_grid=_list(data["support_bounds_grid"]),
            support_bounds_world=_list(data["support_bounds_world"]),
            raw_channel_summary_digest=data["raw_channel_summary_digest"],
            effective_property_summary=_dict(data["effective_property_summary"]),
            response_probe_summary=_dict(data["response_probe_summary"]),
            mode_signature=_dict(data["mode_signature"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class MaterialSpeciesCertificate:
    certificate_id: str
    species_id: str
    run_id: str
    candidate_id: str
    tick_range: list[int]
    coordinate_frame: JsonDict
    source_field_state_ids: list[str]
    source_snapshot_ids: list[str]
    source_record_ids: list[str]
    effective_properties: JsonDict
    stability_metrics: JsonDict
    response_profile: JsonDict
    conservation_profile: JsonDict
    validity_envelope: JsonDict
    certification_method: str
    is_authority_state: bool = True

    def __post_init__(self) -> None:
        self.tick_range = _list(self.tick_range)
        self.coordinate_frame = _dict(self.coordinate_frame)
        self.source_field_state_ids = _list(self.source_field_state_ids)
        self.source_snapshot_ids = _list(self.source_snapshot_ids)
        self.source_record_ids = _list(self.source_record_ids)
        self.effective_properties = _dict(self.effective_properties)
        self.stability_metrics = _dict(self.stability_metrics)
        self.response_profile = _dict(self.response_profile)
        self.conservation_profile = _dict(self.conservation_profile)
        self.validity_envelope = _dict(self.validity_envelope)
        if not _bool(self.is_authority_state):
            raise ValueError("MaterialSpeciesCertificate must be authority state.")
        if not self.certificate_id or not self.species_id or not self.candidate_id:
            raise ValueError("MaterialSpeciesCertificate requires certificate/species/candidate ids.")
        _validate_tick_range(self.tick_range, "MaterialSpeciesCertificate")
        if not _has_field_or_snapshot_lineage(self.source_field_state_ids, self.source_snapshot_ids):
            raise ValueError("MaterialSpeciesCertificate requires field state or snapshot lineage.")
        if not self.source_record_ids:
            raise ValueError("MaterialSpeciesCertificate requires source_record_ids.")
        _validate_coordinate_frame(self.coordinate_frame)
        _validate_effective_properties(self.effective_properties)
        if not self.stability_metrics or not self.response_profile or not self.conservation_profile:
            raise ValueError("MaterialSpeciesCertificate requires stability, response, and conservation profiles.")
        if self.response_profile.get("probe_protocol") not in {"passive_history_probe_v1", "controlled_affordance_probe_v1"}:
            raise ValueError("MaterialSpeciesCertificate response_profile must declare a supported probe protocol.")
        _validate_material_validity_envelope(self.validity_envelope)
        if not self.certification_method:
            raise ValueError("MaterialSpeciesCertificate requires certification_method.")

    def to_dict(self) -> JsonDict:
        return {
            "certificate_id": self.certificate_id,
            "species_id": self.species_id,
            "run_id": self.run_id,
            "candidate_id": self.candidate_id,
            "tick_range": _list(self.tick_range),
            "coordinate_frame": _dict(self.coordinate_frame),
            "source_field_state_ids": _list(self.source_field_state_ids),
            "source_snapshot_ids": _list(self.source_snapshot_ids),
            "source_record_ids": _list(self.source_record_ids),
            "effective_properties": _dict(self.effective_properties),
            "stability_metrics": _dict(self.stability_metrics),
            "response_profile": _dict(self.response_profile),
            "conservation_profile": _dict(self.conservation_profile),
            "validity_envelope": _dict(self.validity_envelope),
            "certification_method": self.certification_method,
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "MaterialSpeciesCertificate":
        return cls(
            certificate_id=data["certificate_id"],
            species_id=data["species_id"],
            run_id=data["run_id"],
            candidate_id=data["candidate_id"],
            tick_range=_list(data["tick_range"]),
            coordinate_frame=_dict(data["coordinate_frame"]),
            source_field_state_ids=_list(data.get("source_field_state_ids")),
            source_snapshot_ids=_list(data.get("source_snapshot_ids")),
            source_record_ids=_list(data["source_record_ids"]),
            effective_properties=_dict(data["effective_properties"]),
            stability_metrics=_dict(data["stability_metrics"]),
            response_profile=_dict(data["response_profile"]),
            conservation_profile=_dict(data["conservation_profile"]),
            validity_envelope=_dict(data["validity_envelope"]),
            certification_method=data["certification_method"],
            is_authority_state=data.get("is_authority_state", True),
        )


@dataclass
class MaterialUnit:
    unit_id: str
    species_id: str
    species_certificate_id: str
    run_id: str
    tick: int
    region_id: str
    coordinate_frame: JsonDict
    support_bounds_grid: list[float]
    support_bounds_world: list[float]
    centroid_grid: list[float]
    centroid_world: list[float]
    effective_quantities: JsonDict
    source_field_state_id: str | None
    source_snapshot_id: str | None
    source_record_ids: list[str]
    is_authority_state: bool = True

    def __post_init__(self) -> None:
        self.coordinate_frame = _dict(self.coordinate_frame)
        self.support_bounds_grid = _list(self.support_bounds_grid)
        self.support_bounds_world = _list(self.support_bounds_world)
        self.centroid_grid = _list(self.centroid_grid)
        self.centroid_world = _list(self.centroid_world)
        self.effective_quantities = _dict(self.effective_quantities)
        self.source_record_ids = _list(self.source_record_ids)
        if not _bool(self.is_authority_state):
            raise ValueError("MaterialUnit must be authority state.")
        if not self.unit_id or not self.species_id or not self.species_certificate_id:
            raise ValueError("MaterialUnit requires unit/species/certificate ids.")
        if not self.region_id:
            raise ValueError("MaterialUnit requires region_id.")
        if not self.source_field_state_id and not self.source_snapshot_id:
            raise ValueError("MaterialUnit requires source_field_state_id or source_snapshot_id.")
        if not self.source_record_ids:
            raise ValueError("MaterialUnit requires source_record_ids.")
        _validate_coordinate_frame(self.coordinate_frame)
        _validate_bounds4(self.support_bounds_grid, "support_bounds_grid")
        _validate_bounds4(self.support_bounds_world, "support_bounds_world")
        _validate_effective_properties(self.effective_quantities)

    def to_dict(self) -> JsonDict:
        return {
            "unit_id": self.unit_id,
            "species_id": self.species_id,
            "species_certificate_id": self.species_certificate_id,
            "run_id": self.run_id,
            "tick": self.tick,
            "region_id": self.region_id,
            "coordinate_frame": _dict(self.coordinate_frame),
            "support_bounds_grid": _list(self.support_bounds_grid),
            "support_bounds_world": _list(self.support_bounds_world),
            "centroid_grid": _list(self.centroid_grid),
            "centroid_world": _list(self.centroid_world),
            "effective_quantities": _dict(self.effective_quantities),
            "source_field_state_id": self.source_field_state_id,
            "source_snapshot_id": self.source_snapshot_id,
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "MaterialUnit":
        return cls(
            unit_id=data["unit_id"],
            species_id=data["species_id"],
            species_certificate_id=data["species_certificate_id"],
            run_id=data["run_id"],
            tick=data["tick"],
            region_id=data["region_id"],
            coordinate_frame=_dict(data["coordinate_frame"]),
            support_bounds_grid=_list(data["support_bounds_grid"]),
            support_bounds_world=_list(data["support_bounds_world"]),
            centroid_grid=_list(data["centroid_grid"]),
            centroid_world=_list(data["centroid_world"]),
            effective_quantities=_dict(data["effective_quantities"]),
            source_field_state_id=data.get("source_field_state_id"),
            source_snapshot_id=data.get("source_snapshot_id"),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", True),
        )


@dataclass
class MaterialBondRecord:
    record_id: str
    run_id: str
    tick: int
    tick_range: list[int]
    bond_kind: str
    unit_ids: list[str]
    species_ids: list[str]
    bond_support_grid: list[float]
    bond_support_world: list[float]
    bond_strength: float
    stability_score: float
    support_history_digest: str
    source_field_state_id: str | None
    source_field_state_ids: list[str]
    source_snapshot_ids: list[str]
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.tick_range = _list(self.tick_range)
        self.unit_ids = _list(self.unit_ids)
        self.species_ids = _list(self.species_ids)
        self.bond_support_grid = _list(self.bond_support_grid)
        self.bond_support_world = _list(self.bond_support_world)
        self.source_field_state_ids = _list(self.source_field_state_ids)
        self.source_snapshot_ids = _list(self.source_snapshot_ids)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "MaterialBondRecord")
        if not self.record_id:
            raise ValueError("MaterialBondRecord requires record_id.")
        if self.bond_kind not in MATERIAL_BOND_KINDS:
            raise ValueError(f"Unsupported material bond_kind: {self.bond_kind!r}.")
        if len(self.unit_ids) < 2:
            raise ValueError("MaterialBondRecord requires at least two unit_ids.")
        if not self.species_ids:
            raise ValueError("MaterialBondRecord requires species_ids.")
        if not self.support_history_digest:
            raise ValueError("MaterialBondRecord requires support_history_digest.")
        if not _has_field_or_snapshot_lineage(self.source_field_state_ids, self.source_snapshot_ids):
            raise ValueError("MaterialBondRecord requires field or snapshot lineage.")
        if not self.source_record_ids:
            raise ValueError("MaterialBondRecord requires source_record_ids.")
        _validate_tick_range(self.tick_range, "tick_range")
        _validate_bounds4(self.bond_support_grid, "bond_support_grid")
        _validate_bounds4(self.bond_support_world, "bond_support_world")
        if not isfinite(float(self.bond_strength)):
            raise ValueError("MaterialBondRecord bond_strength must be finite.")
        if not 0.0 <= float(self.stability_score) <= 1.0:
            raise ValueError("MaterialBondRecord stability_score must be between 0 and 1.")

    def to_dict(self) -> JsonDict:
        return {
            "record_id": self.record_id,
            "run_id": self.run_id,
            "tick": self.tick,
            "tick_range": _list(self.tick_range),
            "bond_kind": self.bond_kind,
            "unit_ids": _list(self.unit_ids),
            "species_ids": _list(self.species_ids),
            "bond_support_grid": _list(self.bond_support_grid),
            "bond_support_world": _list(self.bond_support_world),
            "bond_strength": self.bond_strength,
            "stability_score": self.stability_score,
            "support_history_digest": self.support_history_digest,
            "source_field_state_id": self.source_field_state_id,
            "source_field_state_ids": _list(self.source_field_state_ids),
            "source_snapshot_ids": _list(self.source_snapshot_ids),
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "MaterialBondRecord":
        return cls(
            record_id=data["record_id"],
            run_id=data["run_id"],
            tick=data["tick"],
            tick_range=_list(data["tick_range"]),
            bond_kind=data["bond_kind"],
            unit_ids=_list(data["unit_ids"]),
            species_ids=_list(data["species_ids"]),
            bond_support_grid=_list(data["bond_support_grid"]),
            bond_support_world=_list(data["bond_support_world"]),
            bond_strength=data["bond_strength"],
            stability_score=data["stability_score"],
            support_history_digest=data["support_history_digest"],
            source_field_state_id=data.get("source_field_state_id"),
            source_field_state_ids=_list(data["source_field_state_ids"]),
            source_snapshot_ids=_list(data.get("source_snapshot_ids")),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class MaterialReactionRecord:
    record_id: str
    run_id: str
    tick: int
    reaction_kind: str
    input_unit_ids: list[str]
    output_unit_ids: list[str]
    input_species_ids: list[str]
    output_species_ids: list[str]
    input_quantity_summary: JsonDict
    output_quantity_summary: JsonDict
    external_exchange_summary: JsonDict
    conservation_errors: JsonDict
    balance_status: str
    pre_field_state_ids: list[str]
    post_field_state_ids: list[str]
    pre_snapshot_ids: list[str]
    post_snapshot_ids: list[str]
    source_field_state_ids: list[str]
    source_bond_record_ids: list[str]
    source_wave_step_record_ids: list[str]
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.input_unit_ids = _list(self.input_unit_ids)
        self.output_unit_ids = _list(self.output_unit_ids)
        self.input_species_ids = _list(self.input_species_ids)
        self.output_species_ids = _list(self.output_species_ids)
        self.input_quantity_summary = _dict(self.input_quantity_summary)
        self.output_quantity_summary = _dict(self.output_quantity_summary)
        self.external_exchange_summary = _dict(self.external_exchange_summary)
        self.conservation_errors = _dict(self.conservation_errors)
        self.pre_field_state_ids = _list(self.pre_field_state_ids)
        self.post_field_state_ids = _list(self.post_field_state_ids)
        self.pre_snapshot_ids = _list(self.pre_snapshot_ids)
        self.post_snapshot_ids = _list(self.post_snapshot_ids)
        self.source_field_state_ids = _list(self.source_field_state_ids)
        self.source_bond_record_ids = _list(self.source_bond_record_ids)
        self.source_wave_step_record_ids = _list(self.source_wave_step_record_ids)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "MaterialReactionRecord")
        if not self.record_id:
            raise ValueError("MaterialReactionRecord requires record_id.")
        if self.reaction_kind not in MATERIAL_REACTION_KINDS:
            raise ValueError(f"Unsupported material reaction_kind: {self.reaction_kind!r}.")
        if self.balance_status not in MATERIAL_BALANCE_STATUSES:
            raise ValueError(f"Unsupported material balance_status: {self.balance_status!r}.")
        if not self.input_unit_ids or not self.input_species_ids:
            raise ValueError("MaterialReactionRecord requires input units and species.")
        if self.balance_status == "balanced" and (not self.output_unit_ids or not self.output_species_ids):
            raise ValueError("Balanced MaterialReactionRecord requires output units and species.")
        if not self.external_exchange_summary:
            raise ValueError("MaterialReactionRecord requires external_exchange_summary.")
        if not _has_field_or_snapshot_lineage(self.pre_field_state_ids, self.pre_snapshot_ids):
            raise ValueError("MaterialReactionRecord requires pre field or snapshot lineage.")
        if self.balance_status == "balanced" and not _has_field_or_snapshot_lineage(
            self.post_field_state_ids, self.post_snapshot_ids
        ):
            raise ValueError("Balanced MaterialReactionRecord requires post field or snapshot lineage.")
        if not self.source_wave_step_record_ids:
            raise ValueError("MaterialReactionRecord requires source_wave_step_record_ids.")
        if not self.source_record_ids:
            raise ValueError("MaterialReactionRecord requires source_record_ids.")
        if self.balance_status == "balanced":
            for key, limit in MATERIAL_CONSERVATION_LIMITS.items():
                value = self.conservation_errors.get(key)
                if value is None or not isfinite(float(value)) or abs(float(value)) > limit:
                    raise ValueError(f"MaterialReactionRecord conservation error {key} exceeds limit {limit}.")

    def to_dict(self) -> JsonDict:
        return {
            "record_id": self.record_id,
            "run_id": self.run_id,
            "tick": self.tick,
            "reaction_kind": self.reaction_kind,
            "input_unit_ids": _list(self.input_unit_ids),
            "output_unit_ids": _list(self.output_unit_ids),
            "input_species_ids": _list(self.input_species_ids),
            "output_species_ids": _list(self.output_species_ids),
            "input_quantity_summary": _dict(self.input_quantity_summary),
            "output_quantity_summary": _dict(self.output_quantity_summary),
            "external_exchange_summary": _dict(self.external_exchange_summary),
            "conservation_errors": _dict(self.conservation_errors),
            "balance_status": self.balance_status,
            "pre_field_state_ids": _list(self.pre_field_state_ids),
            "post_field_state_ids": _list(self.post_field_state_ids),
            "pre_snapshot_ids": _list(self.pre_snapshot_ids),
            "post_snapshot_ids": _list(self.post_snapshot_ids),
            "source_field_state_ids": _list(self.source_field_state_ids),
            "source_bond_record_ids": _list(self.source_bond_record_ids),
            "source_wave_step_record_ids": _list(self.source_wave_step_record_ids),
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "MaterialReactionRecord":
        return cls(
            record_id=data["record_id"],
            run_id=data["run_id"],
            tick=data["tick"],
            reaction_kind=data["reaction_kind"],
            input_unit_ids=_list(data["input_unit_ids"]),
            output_unit_ids=_list(data.get("output_unit_ids")),
            input_species_ids=_list(data["input_species_ids"]),
            output_species_ids=_list(data.get("output_species_ids")),
            input_quantity_summary=_dict(data["input_quantity_summary"]),
            output_quantity_summary=_dict(data.get("output_quantity_summary")),
            external_exchange_summary=_dict(data["external_exchange_summary"]),
            conservation_errors=_dict(data["conservation_errors"]),
            balance_status=data["balance_status"],
            pre_field_state_ids=_list(data.get("pre_field_state_ids")),
            post_field_state_ids=_list(data.get("post_field_state_ids")),
            pre_snapshot_ids=_list(data.get("pre_snapshot_ids")),
            post_snapshot_ids=_list(data.get("post_snapshot_ids")),
            source_field_state_ids=_list(data.get("source_field_state_ids")),
            source_bond_record_ids=_list(data.get("source_bond_record_ids")),
            source_wave_step_record_ids=_list(data["source_wave_step_record_ids"]),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class MaterialBody:
    body_id: str
    run_id: str
    body_kind: str
    tick_range: list[int]
    region_ids: list[str]
    unit_ids: list[str]
    species_ids: list[str]
    bond_record_ids: list[str]
    reaction_record_ids: list[str]
    coordinate_frame: JsonDict
    support_bounds_grid: list[float]
    support_bounds_world: list[float]
    aggregate_effective_properties: JsonDict
    body_stability_metrics: JsonDict
    source_record_ids: list[str]
    is_authority_state: bool = True

    def __post_init__(self) -> None:
        self.tick_range = _list(self.tick_range)
        self.region_ids = _list(self.region_ids)
        self.unit_ids = _list(self.unit_ids)
        self.species_ids = _list(self.species_ids)
        self.bond_record_ids = _list(self.bond_record_ids)
        self.reaction_record_ids = _list(self.reaction_record_ids)
        self.coordinate_frame = _dict(self.coordinate_frame)
        self.support_bounds_grid = _list(self.support_bounds_grid)
        self.support_bounds_world = _list(self.support_bounds_world)
        self.aggregate_effective_properties = _dict(self.aggregate_effective_properties)
        self.body_stability_metrics = _dict(self.body_stability_metrics)
        self.source_record_ids = _list(self.source_record_ids)
        if not _bool(self.is_authority_state):
            raise ValueError("MaterialBody must be authority state.")
        if not self.body_id:
            raise ValueError("MaterialBody requires body_id.")
        if self.body_kind not in MATERIAL_BODY_KINDS:
            raise ValueError(f"Unsupported material body_kind: {self.body_kind!r}.")
        if not self.region_ids or not self.unit_ids or not self.species_ids:
            raise ValueError("MaterialBody requires region/unit/species ids.")
        if self.body_kind in {"bonded_body", "compound_body"} and not self.bond_record_ids:
            raise ValueError("Bonded or compound MaterialBody requires bond_record_ids.")
        if self.body_kind == "compound_body" and not self.reaction_record_ids:
            raise ValueError("Compound MaterialBody requires reaction_record_ids.")
        if not self.source_record_ids:
            raise ValueError("MaterialBody requires source_record_ids.")
        _validate_tick_range(self.tick_range, "tick_range")
        _validate_coordinate_frame(self.coordinate_frame)
        _validate_bounds4(self.support_bounds_grid, "support_bounds_grid")
        _validate_bounds4(self.support_bounds_world, "support_bounds_world")
        _validate_effective_properties(self.aggregate_effective_properties)

    def to_dict(self) -> JsonDict:
        return {
            "body_id": self.body_id,
            "run_id": self.run_id,
            "body_kind": self.body_kind,
            "tick_range": _list(self.tick_range),
            "region_ids": _list(self.region_ids),
            "unit_ids": _list(self.unit_ids),
            "species_ids": _list(self.species_ids),
            "bond_record_ids": _list(self.bond_record_ids),
            "reaction_record_ids": _list(self.reaction_record_ids),
            "coordinate_frame": _dict(self.coordinate_frame),
            "support_bounds_grid": _list(self.support_bounds_grid),
            "support_bounds_world": _list(self.support_bounds_world),
            "aggregate_effective_properties": _dict(self.aggregate_effective_properties),
            "body_stability_metrics": _dict(self.body_stability_metrics),
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "MaterialBody":
        return cls(
            body_id=data["body_id"],
            run_id=data["run_id"],
            body_kind=data["body_kind"],
            tick_range=_list(data["tick_range"]),
            region_ids=_list(data["region_ids"]),
            unit_ids=_list(data["unit_ids"]),
            species_ids=_list(data["species_ids"]),
            bond_record_ids=_list(data.get("bond_record_ids")),
            reaction_record_ids=_list(data.get("reaction_record_ids")),
            coordinate_frame=_dict(data["coordinate_frame"]),
            support_bounds_grid=_list(data["support_bounds_grid"]),
            support_bounds_world=_list(data["support_bounds_world"]),
            aggregate_effective_properties=_dict(data["aggregate_effective_properties"]),
            body_stability_metrics=_dict(data.get("body_stability_metrics")),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", True),
        )


@dataclass
class MacroMaterialState:
    macro_material_state_id: str
    body_id: str
    run_id: str
    tick_range: list[int]
    region_ids: list[str]
    coordinate_frame: JsonDict
    support_bounds_grid: list[float]
    support_bounds_world: list[float]
    source_material_body_id: str
    source_species_certificate_ids: list[str]
    source_unit_ids: list[str]
    source_bond_record_ids: list[str]
    source_reaction_record_ids: list[str]
    aggregate_effective_properties: JsonDict
    validity_envelope: JsonDict
    reconstruction_recipe: JsonDict
    error_bounds: JsonDict
    source_record_ids: list[str]
    is_authority_state: bool = True

    def __post_init__(self) -> None:
        self.tick_range = _list(self.tick_range)
        self.region_ids = _list(self.region_ids)
        self.coordinate_frame = _dict(self.coordinate_frame)
        self.support_bounds_grid = _list(self.support_bounds_grid)
        self.support_bounds_world = _list(self.support_bounds_world)
        self.source_species_certificate_ids = _list(self.source_species_certificate_ids)
        self.source_unit_ids = _list(self.source_unit_ids)
        self.source_bond_record_ids = _list(self.source_bond_record_ids)
        self.source_reaction_record_ids = _list(self.source_reaction_record_ids)
        self.aggregate_effective_properties = _dict(self.aggregate_effective_properties)
        self.validity_envelope = _dict(self.validity_envelope)
        self.reconstruction_recipe = _dict(self.reconstruction_recipe)
        self.error_bounds = _dict(self.error_bounds)
        self.source_record_ids = _list(self.source_record_ids)
        if not _bool(self.is_authority_state):
            raise ValueError("MacroMaterialState must be authority state.")
        if not self.macro_material_state_id or not self.body_id:
            raise ValueError("MacroMaterialState requires macro_material_state_id and body_id.")
        if not self.region_ids or not self.source_material_body_id:
            raise ValueError("MacroMaterialState requires region ids and source_material_body_id.")
        if not self.source_species_certificate_ids or not self.source_unit_ids:
            raise ValueError("MacroMaterialState requires species certificates and units.")
        if not self.reconstruction_recipe:
            raise ValueError("MacroMaterialState requires reconstruction_recipe.")
        if not self.source_record_ids:
            raise ValueError("MacroMaterialState requires source_record_ids.")
        _validate_tick_range(self.tick_range, "tick_range")
        _validate_coordinate_frame(self.coordinate_frame)
        _validate_bounds4(self.support_bounds_grid, "support_bounds_grid")
        _validate_bounds4(self.support_bounds_world, "support_bounds_world")
        _validate_effective_properties(self.aggregate_effective_properties)
        _validate_material_validity_envelope(self.validity_envelope)
        for key in (
            "aggregate_mass_like_relative_error_max",
            "aggregate_energy_like_relative_error_max",
            "aggregate_charge_like_absolute_error_max",
            "support_iou_min",
            "body_centroid_world_distance_max",
            "bond_graph_edit_distance_max",
        ):
            value = self.error_bounds.get(key)
            if value is None or not isfinite(float(value)):
                raise ValueError(f"MacroMaterialState error_bounds requires finite {key}.")

    def to_dict(self) -> JsonDict:
        return {
            "macro_material_state_id": self.macro_material_state_id,
            "body_id": self.body_id,
            "run_id": self.run_id,
            "tick_range": _list(self.tick_range),
            "region_ids": _list(self.region_ids),
            "coordinate_frame": _dict(self.coordinate_frame),
            "support_bounds_grid": _list(self.support_bounds_grid),
            "support_bounds_world": _list(self.support_bounds_world),
            "source_material_body_id": self.source_material_body_id,
            "source_species_certificate_ids": _list(self.source_species_certificate_ids),
            "source_unit_ids": _list(self.source_unit_ids),
            "source_bond_record_ids": _list(self.source_bond_record_ids),
            "source_reaction_record_ids": _list(self.source_reaction_record_ids),
            "aggregate_effective_properties": _dict(self.aggregate_effective_properties),
            "validity_envelope": _dict(self.validity_envelope),
            "reconstruction_recipe": _dict(self.reconstruction_recipe),
            "error_bounds": _dict(self.error_bounds),
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "MacroMaterialState":
        return cls(
            macro_material_state_id=data["macro_material_state_id"],
            body_id=data["body_id"],
            run_id=data["run_id"],
            tick_range=_list(data["tick_range"]),
            region_ids=_list(data["region_ids"]),
            coordinate_frame=_dict(data["coordinate_frame"]),
            support_bounds_grid=_list(data["support_bounds_grid"]),
            support_bounds_world=_list(data["support_bounds_world"]),
            source_material_body_id=data["source_material_body_id"],
            source_species_certificate_ids=_list(data["source_species_certificate_ids"]),
            source_unit_ids=_list(data["source_unit_ids"]),
            source_bond_record_ids=_list(data.get("source_bond_record_ids")),
            source_reaction_record_ids=_list(data.get("source_reaction_record_ids")),
            aggregate_effective_properties=_dict(data["aggregate_effective_properties"]),
            validity_envelope=_dict(data["validity_envelope"]),
            reconstruction_recipe=_dict(data["reconstruction_recipe"]),
            error_bounds=_dict(data["error_bounds"]),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", True),
        )


@dataclass
class RegionMaterialAuthorityPointer:
    pointer_id: str
    run_id: str
    tick: int
    region_id: str
    region_lifecycle_record_id: str
    material_authority_mode: str
    current_macro_material_state_id: str | None
    active_material_refinement_patch_id: str | None
    current_material_body_id: str | None
    invalidation_record_ids: list[str]
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.invalidation_record_ids = _list(self.invalidation_record_ids)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "RegionMaterialAuthorityPointer")
        if not self.pointer_id or not self.region_id or not self.region_lifecycle_record_id:
            raise ValueError("RegionMaterialAuthorityPointer requires pointer, region, and lifecycle ids.")
        if self.material_authority_mode not in MATERIAL_AUTHORITY_MODES:
            raise ValueError(f"Unsupported material authority mode: {self.material_authority_mode!r}.")
        if self.material_authority_mode in {"cold_macro_material", "warm_macro_material"}:
            if not self.current_macro_material_state_id:
                raise ValueError("Macro material authority mode requires current_macro_material_state_id.")
        if self.material_authority_mode == "active_material_refinement":
            if not self.active_material_refinement_patch_id:
                raise ValueError("Active material refinement mode requires active_material_refinement_patch_id.")
        if self.material_authority_mode == "invalidated_material" and not self.invalidation_record_ids:
            raise ValueError("Invalidated material authority pointer requires invalidation_record_ids.")
        if not self.source_record_ids:
            raise ValueError("RegionMaterialAuthorityPointer requires source_record_ids.")

    def to_dict(self) -> JsonDict:
        return {
            "pointer_id": self.pointer_id,
            "run_id": self.run_id,
            "tick": self.tick,
            "region_id": self.region_id,
            "region_lifecycle_record_id": self.region_lifecycle_record_id,
            "material_authority_mode": self.material_authority_mode,
            "current_macro_material_state_id": self.current_macro_material_state_id,
            "active_material_refinement_patch_id": self.active_material_refinement_patch_id,
            "current_material_body_id": self.current_material_body_id,
            "invalidation_record_ids": _list(self.invalidation_record_ids),
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "RegionMaterialAuthorityPointer":
        return cls(
            pointer_id=data["pointer_id"],
            run_id=data["run_id"],
            tick=data["tick"],
            region_id=data["region_id"],
            region_lifecycle_record_id=data["region_lifecycle_record_id"],
            material_authority_mode=data["material_authority_mode"],
            current_macro_material_state_id=data.get("current_macro_material_state_id"),
            active_material_refinement_patch_id=data.get("active_material_refinement_patch_id"),
            current_material_body_id=data.get("current_material_body_id"),
            invalidation_record_ids=_list(data.get("invalidation_record_ids")),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class MaterialRefinementRequest:
    request_id: str
    run_id: str
    tick: int
    trigger_kind: str
    source_macro_material_state_id: str
    observer_id: str | None
    interaction_record_id: str | None
    requested_region_grid: list[float]
    requested_region_world: list[float]
    requested_resolution: float
    coordinate_frame: JsonDict
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.requested_region_grid = _list(self.requested_region_grid)
        self.requested_region_world = _list(self.requested_region_world)
        self.coordinate_frame = _dict(self.coordinate_frame)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "MaterialRefinementRequest")
        if not self.request_id or not self.source_macro_material_state_id:
            raise ValueError("MaterialRefinementRequest requires request_id and source macro material id.")
        if self.trigger_kind not in {"observer_zoom", "local_interaction", "validation_probe"}:
            raise ValueError(f"Unsupported MaterialRefinementRequest trigger_kind: {self.trigger_kind!r}.")
        if self.trigger_kind == "observer_zoom" and not self.observer_id:
            raise ValueError("observer_zoom MaterialRefinementRequest requires observer_id.")
        if self.trigger_kind == "local_interaction" and not self.interaction_record_id:
            raise ValueError("local_interaction MaterialRefinementRequest requires interaction_record_id.")
        if float(self.requested_resolution) <= 0.0:
            raise ValueError("MaterialRefinementRequest requested_resolution must be positive.")
        _validate_bounds4(self.requested_region_grid, "requested_region_grid")
        _validate_bounds4(self.requested_region_world, "requested_region_world")
        _validate_coordinate_frame(self.coordinate_frame)
        if not self.source_record_ids:
            raise ValueError("MaterialRefinementRequest requires source_record_ids.")

    def to_dict(self) -> JsonDict:
        return {
            "request_id": self.request_id,
            "run_id": self.run_id,
            "tick": self.tick,
            "trigger_kind": self.trigger_kind,
            "source_macro_material_state_id": self.source_macro_material_state_id,
            "observer_id": self.observer_id,
            "interaction_record_id": self.interaction_record_id,
            "requested_region_grid": _list(self.requested_region_grid),
            "requested_region_world": _list(self.requested_region_world),
            "requested_resolution": self.requested_resolution,
            "coordinate_frame": _dict(self.coordinate_frame),
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "MaterialRefinementRequest":
        return cls(
            request_id=data["request_id"],
            run_id=data["run_id"],
            tick=data["tick"],
            trigger_kind=data["trigger_kind"],
            source_macro_material_state_id=data["source_macro_material_state_id"],
            observer_id=data.get("observer_id"),
            interaction_record_id=data.get("interaction_record_id"),
            requested_region_grid=_list(data["requested_region_grid"]),
            requested_region_world=_list(data["requested_region_world"]),
            requested_resolution=data["requested_resolution"],
            coordinate_frame=_dict(data["coordinate_frame"]),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class MaterialRefinementPatch:
    patch_id: str
    run_id: str
    material_refinement_request_id: str
    source_macro_material_state_id: str
    tick: int
    region_grid: list[float]
    region_world: list[float]
    coordinate_frame: JsonDict
    channels_compact: dict[str, list[list[float]]]
    lifting_recipe: JsonDict
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.region_grid = _list(self.region_grid)
        self.region_world = _list(self.region_world)
        self.coordinate_frame = _dict(self.coordinate_frame)
        self.channels_compact = _channels(self.channels_compact)
        self.lifting_recipe = _dict(self.lifting_recipe)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "MaterialRefinementPatch")
        if not self.patch_id or not self.material_refinement_request_id or not self.source_macro_material_state_id:
            raise ValueError("MaterialRefinementPatch missing required id.")
        _validate_bounds4(self.region_grid, "region_grid")
        _validate_bounds4(self.region_world, "region_world")
        _validate_coordinate_frame(self.coordinate_frame)
        if not self.channels_compact:
            raise ValueError("MaterialRefinementPatch requires channels_compact.")
        if not self.lifting_recipe or not self.source_record_ids:
            raise ValueError("MaterialRefinementPatch requires lifting_recipe and source_record_ids.")

    def to_dict(self) -> JsonDict:
        return {
            "patch_id": self.patch_id,
            "run_id": self.run_id,
            "material_refinement_request_id": self.material_refinement_request_id,
            "source_macro_material_state_id": self.source_macro_material_state_id,
            "tick": self.tick,
            "region_grid": _list(self.region_grid),
            "region_world": _list(self.region_world),
            "coordinate_frame": _dict(self.coordinate_frame),
            "channels_compact": _channels(self.channels_compact),
            "lifting_recipe": _dict(self.lifting_recipe),
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "MaterialRefinementPatch":
        return cls(
            patch_id=data["patch_id"],
            run_id=data["run_id"],
            material_refinement_request_id=data["material_refinement_request_id"],
            source_macro_material_state_id=data["source_macro_material_state_id"],
            tick=data["tick"],
            region_grid=_list(data["region_grid"]),
            region_world=_list(data["region_world"]),
            coordinate_frame=_dict(data["coordinate_frame"]),
            channels_compact=_channels(data["channels_compact"]),
            lifting_recipe=_dict(data["lifting_recipe"]),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class MaterialPatchStateSnapshot:
    snapshot_id: str
    run_id: str
    patch_id: str
    tick: int
    step_index: int
    region_grid: list[float]
    coordinate_frame: JsonDict
    channels_compact: dict[str, list[list[float]]]
    channels_digest: str
    summary_digest: str
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.region_grid = _list(self.region_grid)
        self.coordinate_frame = _dict(self.coordinate_frame)
        self.channels_compact = _channels(self.channels_compact)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "MaterialPatchStateSnapshot")
        if not self.snapshot_id or not self.patch_id:
            raise ValueError("MaterialPatchStateSnapshot requires snapshot_id and patch_id.")
        _validate_bounds4(self.region_grid, "region_grid")
        _validate_coordinate_frame(self.coordinate_frame)
        if not self.channels_compact or not self.source_record_ids:
            raise ValueError("MaterialPatchStateSnapshot requires channels_compact and source_record_ids.")
        if self.channels_digest != _canonical_json_digest(self.channels_compact):
            raise ValueError("MaterialPatchStateSnapshot channels_digest mismatch.")
        if self.summary_digest != _canonical_json_digest(_summarize_compact_channels(self.channels_compact)):
            raise ValueError("MaterialPatchStateSnapshot summary_digest mismatch.")

    def to_dict(self) -> JsonDict:
        return {
            "snapshot_id": self.snapshot_id,
            "run_id": self.run_id,
            "patch_id": self.patch_id,
            "tick": self.tick,
            "step_index": self.step_index,
            "region_grid": _list(self.region_grid),
            "coordinate_frame": _dict(self.coordinate_frame),
            "channels_compact": _channels(self.channels_compact),
            "channels_digest": self.channels_digest,
            "summary_digest": self.summary_digest,
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "MaterialPatchStateSnapshot":
        return cls(
            snapshot_id=data["snapshot_id"],
            run_id=data["run_id"],
            patch_id=data["patch_id"],
            tick=data["tick"],
            step_index=data["step_index"],
            region_grid=_list(data["region_grid"]),
            coordinate_frame=_dict(data["coordinate_frame"]),
            channels_compact=_channels(data["channels_compact"]),
            channels_digest=data["channels_digest"],
            summary_digest=data["summary_digest"],
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class MaterialPatchStepRecord:
    record_id: str
    run_id: str
    tick: int
    patch_id: str
    previous_snapshot_id: str
    current_snapshot_id: str
    material_rule_id: str
    coordinate_frame: JsonDict
    region_grid: list[float]
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.coordinate_frame = _dict(self.coordinate_frame)
        self.region_grid = _list(self.region_grid)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "MaterialPatchStepRecord")
        if not self.record_id or not self.patch_id or not self.previous_snapshot_id or not self.current_snapshot_id:
            raise ValueError("MaterialPatchStepRecord missing required id.")
        if not self.material_rule_id or not self.source_record_ids:
            raise ValueError("MaterialPatchStepRecord requires material_rule_id and source_record_ids.")
        _validate_bounds4(self.region_grid, "region_grid")
        _validate_coordinate_frame(self.coordinate_frame)

    def to_dict(self) -> JsonDict:
        return {
            "record_id": self.record_id,
            "run_id": self.run_id,
            "tick": self.tick,
            "patch_id": self.patch_id,
            "previous_snapshot_id": self.previous_snapshot_id,
            "current_snapshot_id": self.current_snapshot_id,
            "material_rule_id": self.material_rule_id,
            "coordinate_frame": _dict(self.coordinate_frame),
            "region_grid": _list(self.region_grid),
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "MaterialPatchStepRecord":
        return cls(
            record_id=data["record_id"],
            run_id=data["run_id"],
            tick=data["tick"],
            patch_id=data["patch_id"],
            previous_snapshot_id=data["previous_snapshot_id"],
            current_snapshot_id=data["current_snapshot_id"],
            material_rule_id=data["material_rule_id"],
            coordinate_frame=_dict(data["coordinate_frame"]),
            region_grid=_list(data["region_grid"]),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class MaterialPatchOutcome:
    outcome_id: str
    run_id: str
    patch_id: str
    material_refinement_request_id: str
    source_macro_material_state_id: str
    start_tick: int
    end_tick: int
    region_grid: list[float]
    coordinate_frame: JsonDict
    initial_snapshot_id: str
    final_snapshot_id: str
    final_patch_channels_digest: str
    raw_channel_summary: JsonDict
    material_patch_step_record_ids: list[str]
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.region_grid = _list(self.region_grid)
        self.coordinate_frame = _dict(self.coordinate_frame)
        self.raw_channel_summary = _dict(self.raw_channel_summary)
        self.material_patch_step_record_ids = _list(self.material_patch_step_record_ids)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "MaterialPatchOutcome")
        if not self.outcome_id or not self.patch_id or not self.material_refinement_request_id:
            raise ValueError("MaterialPatchOutcome missing required id.")
        if not self.source_macro_material_state_id or not self.initial_snapshot_id or not self.final_snapshot_id:
            raise ValueError("MaterialPatchOutcome requires macro and snapshot lineage.")
        if not self.final_patch_channels_digest or not self.raw_channel_summary or not self.source_record_ids:
            raise ValueError("MaterialPatchOutcome requires digest, raw summary, and source records.")
        _validate_bounds4(self.region_grid, "region_grid")
        _validate_coordinate_frame(self.coordinate_frame)

    def to_dict(self) -> JsonDict:
        return {
            "outcome_id": self.outcome_id,
            "run_id": self.run_id,
            "patch_id": self.patch_id,
            "material_refinement_request_id": self.material_refinement_request_id,
            "source_macro_material_state_id": self.source_macro_material_state_id,
            "start_tick": self.start_tick,
            "end_tick": self.end_tick,
            "region_grid": _list(self.region_grid),
            "coordinate_frame": _dict(self.coordinate_frame),
            "initial_snapshot_id": self.initial_snapshot_id,
            "final_snapshot_id": self.final_snapshot_id,
            "final_patch_channels_digest": self.final_patch_channels_digest,
            "raw_channel_summary": _dict(self.raw_channel_summary),
            "material_patch_step_record_ids": _list(self.material_patch_step_record_ids),
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "MaterialPatchOutcome":
        return cls(
            outcome_id=data["outcome_id"],
            run_id=data["run_id"],
            patch_id=data["patch_id"],
            material_refinement_request_id=data["material_refinement_request_id"],
            source_macro_material_state_id=data["source_macro_material_state_id"],
            start_tick=data["start_tick"],
            end_tick=data["end_tick"],
            region_grid=_list(data["region_grid"]),
            coordinate_frame=_dict(data["coordinate_frame"]),
            initial_snapshot_id=data["initial_snapshot_id"],
            final_snapshot_id=data["final_snapshot_id"],
            final_patch_channels_digest=data["final_patch_channels_digest"],
            raw_channel_summary=_dict(data["raw_channel_summary"]),
            material_patch_step_record_ids=_list(data.get("material_patch_step_record_ids")),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class MaterialCorrectionRecord:
    correction_id: str
    run_id: str
    tick: int
    pre_correction_macro_material_state_id: str
    post_correction_macro_material_state_id: str
    material_patch_outcome_id: str
    material_refinement_request_id: str
    correction_operator: str
    post_effective_properties_digest: str
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "MaterialCorrectionRecord")
        required = [
            self.correction_id,
            self.pre_correction_macro_material_state_id,
            self.post_correction_macro_material_state_id,
            self.material_patch_outcome_id,
            self.material_refinement_request_id,
            self.correction_operator,
            self.post_effective_properties_digest,
        ]
        if any(not value for value in required):
            raise ValueError("MaterialCorrectionRecord missing required id field.")
        if not self.source_record_ids:
            raise ValueError("MaterialCorrectionRecord requires source_record_ids.")

    def to_dict(self) -> JsonDict:
        return {
            "correction_id": self.correction_id,
            "run_id": self.run_id,
            "tick": self.tick,
            "pre_correction_macro_material_state_id": self.pre_correction_macro_material_state_id,
            "post_correction_macro_material_state_id": self.post_correction_macro_material_state_id,
            "material_patch_outcome_id": self.material_patch_outcome_id,
            "material_refinement_request_id": self.material_refinement_request_id,
            "correction_operator": self.correction_operator,
            "post_effective_properties_digest": self.post_effective_properties_digest,
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "MaterialCorrectionRecord":
        return cls(
            correction_id=data["correction_id"],
            run_id=data["run_id"],
            tick=data["tick"],
            pre_correction_macro_material_state_id=data["pre_correction_macro_material_state_id"],
            post_correction_macro_material_state_id=data["post_correction_macro_material_state_id"],
            material_patch_outcome_id=data["material_patch_outcome_id"],
            material_refinement_request_id=data["material_refinement_request_id"],
            correction_operator=data["correction_operator"],
            post_effective_properties_digest=data["post_effective_properties_digest"],
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class MaterialCorrectionCertificateExtension:
    extension_id: str
    run_id: str
    pre_correction_macro_material_state_id: str
    post_correction_macro_material_state_id: str
    material_correction_record_id: str
    material_patch_outcome_id: str
    inherited_validity_envelope: JsonDict
    post_correction_validity_envelope: JsonDict
    error_bounds: JsonDict
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.inherited_validity_envelope = _dict(self.inherited_validity_envelope)
        self.post_correction_validity_envelope = _dict(self.post_correction_validity_envelope)
        self.error_bounds = _dict(self.error_bounds)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "MaterialCorrectionCertificateExtension")
        required = [
            self.extension_id,
            self.pre_correction_macro_material_state_id,
            self.post_correction_macro_material_state_id,
            self.material_correction_record_id,
            self.material_patch_outcome_id,
        ]
        if any(not value for value in required):
            raise ValueError("MaterialCorrectionCertificateExtension missing required id field.")
        if not self.source_record_ids:
            raise ValueError("MaterialCorrectionCertificateExtension requires source_record_ids.")

    def to_dict(self) -> JsonDict:
        return {
            "extension_id": self.extension_id,
            "run_id": self.run_id,
            "pre_correction_macro_material_state_id": self.pre_correction_macro_material_state_id,
            "post_correction_macro_material_state_id": self.post_correction_macro_material_state_id,
            "material_correction_record_id": self.material_correction_record_id,
            "material_patch_outcome_id": self.material_patch_outcome_id,
            "inherited_validity_envelope": _dict(self.inherited_validity_envelope),
            "post_correction_validity_envelope": _dict(self.post_correction_validity_envelope),
            "error_bounds": _dict(self.error_bounds),
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "MaterialCorrectionCertificateExtension":
        return cls(
            extension_id=data["extension_id"],
            run_id=data["run_id"],
            pre_correction_macro_material_state_id=data["pre_correction_macro_material_state_id"],
            post_correction_macro_material_state_id=data["post_correction_macro_material_state_id"],
            material_correction_record_id=data["material_correction_record_id"],
            material_patch_outcome_id=data["material_patch_outcome_id"],
            inherited_validity_envelope=_dict(data["inherited_validity_envelope"]),
            post_correction_validity_envelope=_dict(data["post_correction_validity_envelope"]),
            error_bounds=_dict(data["error_bounds"]),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class MaterialBehaviorProfile:
    profile_id: str
    run_id: str
    tick_range: list[int]
    source_macro_material_state_id: str
    source_material_body_id: str
    source_species_certificate_ids: list[str]
    source_record_ids: list[str]
    effective_property_digest: str
    effective_property_inputs: JsonDict
    property_values: JsonDict
    secondary_behavior_scores: JsonDict
    behavior_class: str
    behavior_thresholds: JsonDict
    profile_digest: str
    derivation_method: str = "legacy_macro_threshold_scaffold_v1"
    source_substrate_measurement_record_ids: list[str] | None = None
    source_derived_property_record_ids: list[str] | None = None
    scaffold_status: str = "stage1_scaffold"
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.tick_range = _list(self.tick_range)
        self.source_species_certificate_ids = _list(self.source_species_certificate_ids)
        self.source_record_ids = _list(self.source_record_ids)
        self.source_substrate_measurement_record_ids = _list(self.source_substrate_measurement_record_ids)
        self.source_derived_property_record_ids = _list(self.source_derived_property_record_ids)
        self.effective_property_inputs = _dict(self.effective_property_inputs)
        self.property_values = _dict(self.property_values)
        self.secondary_behavior_scores = _dict(self.secondary_behavior_scores)
        self.behavior_thresholds = _dict(self.behavior_thresholds)
        _validate_non_authority(self.is_authority_state, "MaterialBehaviorProfile")
        _validate_tick_range(self.tick_range, "MaterialBehaviorProfile")
        if not self.profile_id or not self.source_macro_material_state_id or not self.source_material_body_id:
            raise ValueError("MaterialBehaviorProfile requires profile, macro, and body ids.")
        if not self.source_species_certificate_ids or not self.source_record_ids:
            raise ValueError("MaterialBehaviorProfile requires species certificate and source record lineage.")
        if self.behavior_class not in MATERIAL_BEHAVIOR_CLASSES:
            raise ValueError(f"Unsupported material behavior class: {self.behavior_class!r}.")
        if self.derivation_method not in MATERIAL_BEHAVIOR_DERIVATION_METHODS:
            raise ValueError(f"Unsupported material behavior derivation_method: {self.derivation_method!r}.")
        if self.scaffold_status not in MATERIAL_BEHAVIOR_SCAFFOLD_STATUSES:
            raise ValueError(f"Unsupported material behavior scaffold_status: {self.scaffold_status!r}.")
        if self.derivation_method in {"substrate_frequency_measurement_v1", "substrate_hypergraph_measurement_v1"}:
            if not self.source_substrate_measurement_record_ids or not self.source_derived_property_record_ids:
                raise ValueError("Substrate-derived MaterialBehaviorProfile requires measurement and property lineage.")
            if self.scaffold_status != "substrate_derived":
                raise ValueError("Substrate-derived MaterialBehaviorProfile must use scaffold_status='substrate_derived'.")
        _validate_behavior_values(self.property_values)
        if not self.effective_property_digest:
            raise ValueError("MaterialBehaviorProfile requires effective_property_digest.")
        expected = material_behavior_profile_digest(self.to_dict(include_digest=False))
        if self.profile_digest != expected:
            raise ValueError("MaterialBehaviorProfile profile_digest mismatch.")

    def to_dict(self, *, include_digest: bool = True) -> JsonDict:
        data = {
            "profile_id": self.profile_id,
            "run_id": self.run_id,
            "tick_range": _list(self.tick_range),
            "source_macro_material_state_id": self.source_macro_material_state_id,
            "source_material_body_id": self.source_material_body_id,
            "source_species_certificate_ids": _list(self.source_species_certificate_ids),
            "source_record_ids": _list(self.source_record_ids),
            "effective_property_digest": self.effective_property_digest,
            "effective_property_inputs": _dict(self.effective_property_inputs),
            "property_values": _dict(self.property_values),
            "secondary_behavior_scores": _dict(self.secondary_behavior_scores),
            "behavior_class": self.behavior_class,
            "behavior_thresholds": _dict(self.behavior_thresholds),
            "derivation_method": self.derivation_method,
            "source_substrate_measurement_record_ids": _list(self.source_substrate_measurement_record_ids),
            "source_derived_property_record_ids": _list(self.source_derived_property_record_ids),
            "scaffold_status": self.scaffold_status,
            "is_authority_state": self.is_authority_state,
        }
        if include_digest:
            data["profile_digest"] = self.profile_digest
        return data

    @classmethod
    def from_dict(cls, data: JsonDict) -> "MaterialBehaviorProfile":
        return cls(
            profile_id=data["profile_id"],
            run_id=data["run_id"],
            tick_range=_list(data["tick_range"]),
            source_macro_material_state_id=data["source_macro_material_state_id"],
            source_material_body_id=data["source_material_body_id"],
            source_species_certificate_ids=_list(data["source_species_certificate_ids"]),
            source_record_ids=_list(data["source_record_ids"]),
            effective_property_digest=data["effective_property_digest"],
            effective_property_inputs=_dict(data.get("effective_property_inputs")),
            property_values=_dict(data["property_values"]),
            secondary_behavior_scores=_dict(data.get("secondary_behavior_scores")),
            behavior_class=data["behavior_class"],
            behavior_thresholds=_dict(data["behavior_thresholds"]),
            profile_digest=data["profile_digest"],
            derivation_method=data.get("derivation_method", "legacy_macro_threshold_scaffold_v1"),
            source_substrate_measurement_record_ids=_list(data.get("source_substrate_measurement_record_ids")),
            source_derived_property_record_ids=_list(data.get("source_derived_property_record_ids")),
            scaffold_status=data.get("scaffold_status", "stage1_scaffold"),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class MaterialEnvironmentZone:
    zone_id: str
    run_id: str
    tick_range: list[int]
    region_id: str
    region_bounds_grid: list[float]
    region_bounds_world: list[float]
    coordinate_frame: JsonDict
    material_behavior_profile_id: str
    source_macro_material_state_id: str
    source_material_body_id: str
    behavior_class: str
    zone_role: str
    zone_digest: str
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.tick_range = _list(self.tick_range)
        self.region_bounds_grid = _list(self.region_bounds_grid)
        self.region_bounds_world = _list(self.region_bounds_world)
        self.coordinate_frame = _dict(self.coordinate_frame)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "MaterialEnvironmentZone")
        _validate_tick_range(self.tick_range, "MaterialEnvironmentZone")
        _validate_bounds4(self.region_bounds_grid, "region_bounds_grid")
        _validate_bounds4(self.region_bounds_world, "region_bounds_world")
        _validate_coordinate_frame(self.coordinate_frame)
        if not self.zone_id or not self.region_id or not self.material_behavior_profile_id:
            raise ValueError("MaterialEnvironmentZone requires zone, region, and profile ids.")
        if not self.source_macro_material_state_id or not self.source_material_body_id or not self.source_record_ids:
            raise ValueError("MaterialEnvironmentZone requires macro/body/source lineage.")
        if self.behavior_class not in MATERIAL_BEHAVIOR_CLASSES:
            raise ValueError(f"Unsupported material behavior class: {self.behavior_class!r}.")
        if self.zone_role not in MATERIAL_ZONE_ROLES:
            raise ValueError(f"Unsupported material zone role: {self.zone_role!r}.")
        if self.zone_role not in MATERIAL_ZONE_ROLE_COMPATIBILITY[self.behavior_class]:
            raise ValueError("MaterialEnvironmentZone zone_role is incompatible with behavior_class.")
        expected = material_environment_zone_digest(self.to_dict(include_digest=False))
        if self.zone_digest != expected:
            raise ValueError("MaterialEnvironmentZone zone_digest mismatch.")

    def to_dict(self, *, include_digest: bool = True) -> JsonDict:
        data = {
            "zone_id": self.zone_id,
            "run_id": self.run_id,
            "tick_range": _list(self.tick_range),
            "region_id": self.region_id,
            "region_bounds_grid": _list(self.region_bounds_grid),
            "region_bounds_world": _list(self.region_bounds_world),
            "coordinate_frame": _dict(self.coordinate_frame),
            "material_behavior_profile_id": self.material_behavior_profile_id,
            "source_macro_material_state_id": self.source_macro_material_state_id,
            "source_material_body_id": self.source_material_body_id,
            "behavior_class": self.behavior_class,
            "zone_role": self.zone_role,
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }
        if include_digest:
            data["zone_digest"] = self.zone_digest
        return data

    @classmethod
    def from_dict(cls, data: JsonDict) -> "MaterialEnvironmentZone":
        return cls(
            zone_id=data["zone_id"],
            run_id=data["run_id"],
            tick_range=_list(data["tick_range"]),
            region_id=data["region_id"],
            region_bounds_grid=_list(data["region_bounds_grid"]),
            region_bounds_world=_list(data["region_bounds_world"]),
            coordinate_frame=_dict(data["coordinate_frame"]),
            material_behavior_profile_id=data["material_behavior_profile_id"],
            source_macro_material_state_id=data["source_macro_material_state_id"],
            source_material_body_id=data["source_material_body_id"],
            behavior_class=data["behavior_class"],
            zone_role=data["zone_role"],
            zone_digest=data["zone_digest"],
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class MaterialContactRecord:
    record_id: str
    run_id: str
    tick: int
    contact_kind: str
    source_authority_kind: str
    source_field_state_id: str | None
    source_fine_patch_snapshot_id: str | None
    source_material_patch_snapshot_id: str | None
    source_structure_id: str
    source_component_id: str
    source_mode_signature: str
    source_support_cells_digest: str
    source_material_body_id: str | None
    source_macro_material_state_id: str | None
    target_zone_id: str
    target_behavior_profile_id: str
    target_material_body_id: str
    target_macro_material_state_id: str
    self_contact_boundary_evidence: JsonDict
    contact_region_grid: list[float]
    contact_region_world: list[float]
    support_bounds_grid: list[float]
    support_centroid_grid: list[float]
    incoming_vector_grid: list[float]
    contact_area_grid: float
    overlap_fraction: float
    contact_energy: float
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.self_contact_boundary_evidence = _dict(self.self_contact_boundary_evidence)
        self.contact_region_grid = _list(self.contact_region_grid)
        self.contact_region_world = _list(self.contact_region_world)
        self.support_bounds_grid = _list(self.support_bounds_grid)
        self.support_centroid_grid = _list(self.support_centroid_grid)
        self.incoming_vector_grid = _list(self.incoming_vector_grid)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "MaterialContactRecord")
        if self.contact_kind not in MATERIAL_CONTACT_KINDS:
            raise ValueError(f"Unsupported material contact kind: {self.contact_kind!r}.")
        if self.source_authority_kind not in MATERIAL_CONTACT_AUTHORITY_KINDS:
            raise ValueError(f"Unsupported material contact authority kind: {self.source_authority_kind!r}.")
        source_ids = {
            "field_state": self.source_field_state_id,
            "fine_patch_snapshot": self.source_fine_patch_snapshot_id,
            "material_patch_snapshot": self.source_material_patch_snapshot_id,
        }
        present = [kind for kind, value in source_ids.items() if value]
        if len(present) != 1 or present[0] != self.source_authority_kind:
            raise ValueError("MaterialContactRecord requires exactly one matching source authority id.")
        required = [
            self.record_id,
            self.run_id,
            self.source_structure_id,
            self.source_component_id,
            self.source_mode_signature,
            self.source_support_cells_digest,
            self.target_zone_id,
            self.target_behavior_profile_id,
            self.target_material_body_id,
            self.target_macro_material_state_id,
        ]
        if any(not value for value in required):
            raise ValueError("MaterialContactRecord missing required lineage.")
        if not self.source_support_cells_digest.startswith("sha256:"):
            raise ValueError("MaterialContactRecord requires source_support_cells_digest.")
        _validate_bounds4(self.contact_region_grid, "contact_region_grid")
        _validate_bounds4(self.contact_region_world, "contact_region_world")
        _validate_bounds4(self.support_bounds_grid, "support_bounds_grid")
        if len(self.support_centroid_grid) != 2:
            raise ValueError("support_centroid_grid must contain [x, y].")
        if len(self.incoming_vector_grid) != 2:
            raise ValueError("incoming_vector_grid must contain [dx, dy].")
        for name, value in {
            "contact_area_grid": self.contact_area_grid,
            "overlap_fraction": self.overlap_fraction,
            "contact_energy": self.contact_energy,
        }.items():
            if not isfinite(float(value)):
                raise ValueError(f"{name} must be finite.")
        if float(self.contact_area_grid) < 0.0 or float(self.contact_energy) < 0.0:
            raise ValueError("MaterialContactRecord contact area and energy must be non-negative.")
        if float(self.overlap_fraction) < 0.0 or float(self.overlap_fraction) > 1.0:
            raise ValueError("MaterialContactRecord overlap_fraction must be in [0, 1].")
        if self.contact_kind in {"ordinary_inter_body_contact", "near_band_inter_body_contact"}:
            if self.source_material_body_id and self.source_material_body_id == self.target_material_body_id:
                raise ValueError("ordinary material contacts cannot target the same material body.")
        if self.contact_kind == "container_boundary_contact":
            if self.source_material_body_id != self.target_material_body_id:
                raise ValueError("container_boundary_contact requires self body lineage.")
            if not self.self_contact_boundary_evidence:
                raise ValueError("container_boundary_contact requires boundary evidence.")
        if not self.source_record_ids:
            raise ValueError("MaterialContactRecord requires source_record_ids.")

    def to_dict(self) -> JsonDict:
        return {
            "record_id": self.record_id,
            "run_id": self.run_id,
            "tick": self.tick,
            "contact_kind": self.contact_kind,
            "source_authority_kind": self.source_authority_kind,
            "source_field_state_id": self.source_field_state_id,
            "source_fine_patch_snapshot_id": self.source_fine_patch_snapshot_id,
            "source_material_patch_snapshot_id": self.source_material_patch_snapshot_id,
            "source_structure_id": self.source_structure_id,
            "source_component_id": self.source_component_id,
            "source_mode_signature": self.source_mode_signature,
            "source_support_cells_digest": self.source_support_cells_digest,
            "source_material_body_id": self.source_material_body_id,
            "source_macro_material_state_id": self.source_macro_material_state_id,
            "target_zone_id": self.target_zone_id,
            "target_behavior_profile_id": self.target_behavior_profile_id,
            "target_material_body_id": self.target_material_body_id,
            "target_macro_material_state_id": self.target_macro_material_state_id,
            "self_contact_boundary_evidence": _dict(self.self_contact_boundary_evidence),
            "contact_region_grid": _list(self.contact_region_grid),
            "contact_region_world": _list(self.contact_region_world),
            "support_bounds_grid": _list(self.support_bounds_grid),
            "support_centroid_grid": _list(self.support_centroid_grid),
            "incoming_vector_grid": _list(self.incoming_vector_grid),
            "contact_area_grid": self.contact_area_grid,
            "overlap_fraction": self.overlap_fraction,
            "contact_energy": self.contact_energy,
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "MaterialContactRecord":
        return cls(
            record_id=data["record_id"],
            run_id=data["run_id"],
            tick=data["tick"],
            contact_kind=data["contact_kind"],
            source_authority_kind=data["source_authority_kind"],
            source_field_state_id=data.get("source_field_state_id"),
            source_fine_patch_snapshot_id=data.get("source_fine_patch_snapshot_id"),
            source_material_patch_snapshot_id=data.get("source_material_patch_snapshot_id"),
            source_structure_id=data["source_structure_id"],
            source_component_id=data["source_component_id"],
            source_mode_signature=data["source_mode_signature"],
            source_support_cells_digest=data["source_support_cells_digest"],
            source_material_body_id=data.get("source_material_body_id"),
            source_macro_material_state_id=data.get("source_macro_material_state_id"),
            target_zone_id=data["target_zone_id"],
            target_behavior_profile_id=data["target_behavior_profile_id"],
            target_material_body_id=data["target_material_body_id"],
            target_macro_material_state_id=data["target_macro_material_state_id"],
            self_contact_boundary_evidence=_dict(data.get("self_contact_boundary_evidence")),
            contact_region_grid=_list(data["contact_region_grid"]),
            contact_region_world=_list(data["contact_region_world"]),
            support_bounds_grid=_list(data["support_bounds_grid"]),
            support_centroid_grid=_list(data["support_centroid_grid"]),
            incoming_vector_grid=_list(data["incoming_vector_grid"]),
            contact_area_grid=data["contact_area_grid"],
            overlap_fraction=data["overlap_fraction"],
            contact_energy=data["contact_energy"],
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class MaterialResponseRecord:
    record_id: str
    run_id: str
    tick: int
    material_contact_record_id: str
    response_kind: str
    response_operator: str
    target_zone_id: str
    target_behavior_profile_id: str
    target_behavior_class: str
    target_macro_material_state_id: str
    source_authority_kind: str
    pre_source_state_ref: str
    post_source_state_ref: str
    source_state_ref_kind: str
    source_modulator_record_ids: list[str]
    source_wave_step_record_ids: list[str]
    response_metrics: JsonDict
    result_status: str
    validation_error: str | None
    pre_mutation_session_digest: str | None
    post_failure_session_digest: str | None
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.source_modulator_record_ids = _list(self.source_modulator_record_ids)
        self.source_wave_step_record_ids = _list(self.source_wave_step_record_ids)
        self.response_metrics = _dict(self.response_metrics)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "MaterialResponseRecord")
        if self.response_kind not in MATERIAL_RESPONSE_KINDS:
            raise ValueError(f"Unsupported material response kind: {self.response_kind!r}.")
        if self.result_status not in MATERIAL_RESPONSE_RESULT_STATUSES:
            raise ValueError(f"Unsupported material response result_status: {self.result_status!r}.")
        if self.source_authority_kind not in MATERIAL_CONTACT_AUTHORITY_KINDS:
            raise ValueError(f"Unsupported source_authority_kind: {self.source_authority_kind!r}.")
        if self.source_state_ref_kind not in MATERIAL_CONTACT_AUTHORITY_KINDS:
            raise ValueError(f"Unsupported source_state_ref_kind: {self.source_state_ref_kind!r}.")
        if self.source_authority_kind != self.source_state_ref_kind:
            raise ValueError("MaterialResponseRecord source authority kind must match source state ref kind.")
        if self.target_behavior_class not in MATERIAL_BEHAVIOR_CLASSES:
            raise ValueError(f"Unsupported material behavior class: {self.target_behavior_class!r}.")
        compatible = MATERIAL_BEHAVIOR_RESPONSE_COMPATIBILITY[self.target_behavior_class]
        if self.response_kind not in compatible:
            raise ValueError("MaterialResponseRecord response_kind is incompatible with behavior class.")
        required = [
            self.record_id,
            self.run_id,
            self.material_contact_record_id,
            self.response_operator,
            self.target_zone_id,
            self.target_behavior_profile_id,
            self.target_macro_material_state_id,
            self.pre_source_state_ref,
            self.post_source_state_ref,
        ]
        if any(not value for value in required):
            raise ValueError("MaterialResponseRecord missing required lineage.")
        if self.result_status == "failed_closed":
            if not self.validation_error:
                raise ValueError("failed_closed MaterialResponseRecord requires validation_error.")
            if self.post_source_state_ref != self.pre_source_state_ref:
                raise ValueError("failed_closed MaterialResponseRecord cannot mutate source state.")
            if not self.pre_mutation_session_digest or not self.post_failure_session_digest:
                raise ValueError("failed_closed response digests must both be present.")
            if self.pre_mutation_session_digest != self.post_failure_session_digest:
                raise ValueError("failed_closed MaterialResponseRecord session digests must match.")
        elif not (self.source_modulator_record_ids or self.source_wave_step_record_ids):
            raise ValueError("Applied MaterialResponseRecord requires modulator or wave-step lineage.")
        if self.material_contact_record_id not in self.source_record_ids:
            raise ValueError("MaterialResponseRecord source_record_ids must include material_contact_record_id.")
        if not self.source_record_ids:
            raise ValueError("MaterialResponseRecord requires source_record_ids.")

    def to_dict(self) -> JsonDict:
        return {
            "record_id": self.record_id,
            "run_id": self.run_id,
            "tick": self.tick,
            "material_contact_record_id": self.material_contact_record_id,
            "response_kind": self.response_kind,
            "response_operator": self.response_operator,
            "target_zone_id": self.target_zone_id,
            "target_behavior_profile_id": self.target_behavior_profile_id,
            "target_behavior_class": self.target_behavior_class,
            "target_macro_material_state_id": self.target_macro_material_state_id,
            "source_authority_kind": self.source_authority_kind,
            "pre_source_state_ref": self.pre_source_state_ref,
            "post_source_state_ref": self.post_source_state_ref,
            "source_state_ref_kind": self.source_state_ref_kind,
            "source_modulator_record_ids": _list(self.source_modulator_record_ids),
            "source_wave_step_record_ids": _list(self.source_wave_step_record_ids),
            "response_metrics": _dict(self.response_metrics),
            "result_status": self.result_status,
            "validation_error": self.validation_error,
            "pre_mutation_session_digest": self.pre_mutation_session_digest,
            "post_failure_session_digest": self.post_failure_session_digest,
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "MaterialResponseRecord":
        return cls(
            record_id=data["record_id"],
            run_id=data["run_id"],
            tick=data["tick"],
            material_contact_record_id=data["material_contact_record_id"],
            response_kind=data["response_kind"],
            response_operator=data["response_operator"],
            target_zone_id=data["target_zone_id"],
            target_behavior_profile_id=data["target_behavior_profile_id"],
            target_behavior_class=data["target_behavior_class"],
            target_macro_material_state_id=data["target_macro_material_state_id"],
            source_authority_kind=data["source_authority_kind"],
            pre_source_state_ref=data["pre_source_state_ref"],
            post_source_state_ref=data["post_source_state_ref"],
            source_state_ref_kind=data["source_state_ref_kind"],
            source_modulator_record_ids=_list(data.get("source_modulator_record_ids")),
            source_wave_step_record_ids=_list(data.get("source_wave_step_record_ids")),
            response_metrics=_dict(data.get("response_metrics")),
            result_status=data["result_status"],
            validation_error=data.get("validation_error"),
            pre_mutation_session_digest=data.get("pre_mutation_session_digest"),
            post_failure_session_digest=data.get("post_failure_session_digest"),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class MaterialInteractionRecord:
    record_id: str
    run_id: str
    tick: int
    interaction_intent: str
    interaction_strength: float
    region_id: str
    target_zone_id: str
    target_behavior_profile_id: str
    source_macro_material_state_id: str
    material_refinement_request_id: str | None
    material_refinement_patch_id: str | None
    source_command_ids: list[str]
    source_wave_step_record_ids: list[str]
    source_modulator_record_ids: list[str]
    external_exchange_summary: JsonDict
    pre_behavior_profile_id: str
    post_behavior_profile_id: str | None
    result_status: str
    validation_error: str | None
    pre_mutation_session_digest: str | None
    post_failure_session_digest: str | None
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.source_command_ids = _list(self.source_command_ids)
        self.source_wave_step_record_ids = _list(self.source_wave_step_record_ids)
        self.source_modulator_record_ids = _list(self.source_modulator_record_ids)
        self.external_exchange_summary = _dict(self.external_exchange_summary)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "MaterialInteractionRecord")
        if self.interaction_intent not in MATERIAL_INTERACTION_INTENTS:
            raise ValueError(f"Unsupported material interaction intent: {self.interaction_intent!r}.")
        if self.result_status not in MATERIAL_INTERACTION_RESULT_STATUSES:
            raise ValueError(f"Unsupported material interaction result_status: {self.result_status!r}.")
        if not isfinite(float(self.interaction_strength)) or float(self.interaction_strength) < 0.0:
            raise ValueError("MaterialInteractionRecord interaction_strength must be finite and non-negative.")
        required = [
            self.record_id,
            self.region_id,
            self.target_zone_id,
            self.target_behavior_profile_id,
            self.source_macro_material_state_id,
            self.pre_behavior_profile_id,
        ]
        if any(not value for value in required):
            raise ValueError("MaterialInteractionRecord missing required target lineage.")
        if self.result_status != "failed_closed" and (
            not self.material_refinement_request_id or not self.material_refinement_patch_id
        ):
            raise ValueError("MaterialInteractionRecord requires refinement request and patch lineage.")
        if self.result_status != "observation_only" and self.result_status != "failed_closed":
            if not (self.source_wave_step_record_ids or self.source_modulator_record_ids):
                raise ValueError("Non-observation material interactions require wave-step or modulator lineage.")
        if self.interaction_intent in {"heat_material", "cool_material"}:
            _validate_external_exchange(self.external_exchange_summary)
        if self.result_status == "corrected_macro_material" and not self.post_behavior_profile_id:
            raise ValueError("Corrected material interaction requires post_behavior_profile_id.")
        if self.result_status == "failed_closed":
            if not self.validation_error:
                raise ValueError("failed_closed MaterialInteractionRecord requires validation_error.")
            if bool(self.pre_mutation_session_digest) != bool(self.post_failure_session_digest):
                raise ValueError("failed_closed session digests must both be present or both absent.")
            if self.pre_mutation_session_digest and self.pre_mutation_session_digest != self.post_failure_session_digest:
                raise ValueError("failed_closed MaterialInteractionRecord session digests must match.")
        if not self.source_record_ids:
            raise ValueError("MaterialInteractionRecord requires source_record_ids.")

    def to_dict(self) -> JsonDict:
        return {
            "record_id": self.record_id,
            "run_id": self.run_id,
            "tick": self.tick,
            "interaction_intent": self.interaction_intent,
            "interaction_strength": self.interaction_strength,
            "region_id": self.region_id,
            "target_zone_id": self.target_zone_id,
            "target_behavior_profile_id": self.target_behavior_profile_id,
            "source_macro_material_state_id": self.source_macro_material_state_id,
            "material_refinement_request_id": self.material_refinement_request_id,
            "material_refinement_patch_id": self.material_refinement_patch_id,
            "source_command_ids": _list(self.source_command_ids),
            "source_wave_step_record_ids": _list(self.source_wave_step_record_ids),
            "source_modulator_record_ids": _list(self.source_modulator_record_ids),
            "external_exchange_summary": _dict(self.external_exchange_summary),
            "pre_behavior_profile_id": self.pre_behavior_profile_id,
            "post_behavior_profile_id": self.post_behavior_profile_id,
            "result_status": self.result_status,
            "validation_error": self.validation_error,
            "pre_mutation_session_digest": self.pre_mutation_session_digest,
            "post_failure_session_digest": self.post_failure_session_digest,
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> "MaterialInteractionRecord":
        return cls(
            record_id=data["record_id"],
            run_id=data["run_id"],
            tick=data["tick"],
            interaction_intent=data["interaction_intent"],
            interaction_strength=data["interaction_strength"],
            region_id=data["region_id"],
            target_zone_id=data["target_zone_id"],
            target_behavior_profile_id=data["target_behavior_profile_id"],
            source_macro_material_state_id=data["source_macro_material_state_id"],
            material_refinement_request_id=data.get("material_refinement_request_id"),
            material_refinement_patch_id=data.get("material_refinement_patch_id"),
            source_command_ids=_list(data.get("source_command_ids")),
            source_wave_step_record_ids=_list(data.get("source_wave_step_record_ids")),
            source_modulator_record_ids=_list(data.get("source_modulator_record_ids")),
            external_exchange_summary=_dict(data.get("external_exchange_summary")),
            pre_behavior_profile_id=data["pre_behavior_profile_id"],
            post_behavior_profile_id=data.get("post_behavior_profile_id"),
            result_status=data["result_status"],
            validation_error=data.get("validation_error"),
            pre_mutation_session_digest=data.get("pre_mutation_session_digest"),
            post_failure_session_digest=data.get("post_failure_session_digest"),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )
