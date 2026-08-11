from __future__ import annotations

from dataclasses import replace
from typing import Any

from world_engine.contracts import (
    FineRefinementPatch,
    FineRefinementRequest,
    MacroBoundaryExchangeRecord,
    MacroCorrectionRecord,
    MacroFieldState,
    MacroProjectionRecord,
    PhenomenonOverlay,
    ProjectionFrame,
    ProjectionSample,
    RegionBoundaryExchangeRecord,
    RegionBudgetLedger,
    RegionLifecycleRecord,
    WorldRegion,
    StableStructureCertificate,
    WorldObject,
    WorldState,
)
from world_engine.derived_affordances import derive_field_affordance_summaries
from world_engine.field_coordinates import grid_to_world
from world_engine.implicit_field import validate_implicit_field_authority_certificate, validate_implicit_field_state
from world_engine.implicit_ray_camera import (
    validate_implicit_observer_path_record,
    validate_implicit_ray_sample_record,
    validate_implicit_spectral_image_plane,
)
from world_engine.playable_world import build_playable_projection_mode
from world_engine.projection_invariant_boundary import (
    BoundaryCrossingRecord,
    GenesisRuleEvidence,
    InvariantSignature,
    PhaseTransitionRecord,
    ProjectionLossManifest,
    M13_SCHEMA_VERSION,
)


DEFAULT_IMAGE_PLANE = {"width": 960, "height": 640, "model": "pinhole"}
DEFAULT_WINDOW = {"origin": [0.0, 0.0], "extent": [12.0, 9.0]}
FAMILY_COLORS = {
    "bare": "#66c2a5",
    "intermediate": "#8da0cb",
    "dressed": "#fc8d62",
}
MEMBERSHIP_RECORD_KINDS = {
    "seed_from_certified_package",
    "seed_field_signature",
    "world_tick",
}
HIGH_ENERGY_EVENT_KINDS = {
    "field_discharge",
    "high_energy_discharge",
}
SPECTRAL_CAMERA_DEBUG_LAYER_KEYS = {
    "active_interaction_trace_ids",
    "affordance_overlays",
    "declared_observer_frequency_windows",
    "field_derived_affordance_summaries",
    "field_structure_projection",
    "fine_refinement_overlays",
    "interaction_overlays",
    "interaction_traces",
    "macro_boundary_exchange_overlays",
    "macro_correction_overlays",
    "macro_state_overlays",
    "material_contact_overlays",
    "material_environment_zones",
    "material_wavefront_response_overlays",
    "playable_consequence_overlays",
    "region_budget_summary",
    "region_lifecycle_overlays",
    "region_overlays",
    "spectral_observation",
    "spectral_observations_by_observer",
    "wavefront_overlays",
}
def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return min(high, max(low, value))


def _record_ids(state: WorldState) -> list[str]:
    return [
        record.record_id
        for record in state.events + state.radiative_records + state.interaction_records
    ]


def _event_timeline(state: WorldState, observer_id: str) -> dict[str, Any]:
    records = state.events + state.radiative_records + state.interaction_records
    event_kinds: list[str] = []
    for event in state.events:
        if event.kind not in event_kinds:
            event_kinds.append(event.kind)
        if event.kind == "field_structure_event":
            for kind in event.payload.get("event_kinds", []):
                if kind not in event_kinds:
                    event_kinds.append(kind)
    return {
        "tick": state.tick,
        "observer_id": observer_id,
        "event_kinds": sorted(event_kinds),
        "interaction_record_ids": [
            record.record_id for record in state.interaction_records
        ],
        "wave_step_record_ids": [
            event.record_id for event in state.events if event.kind == "field_wave_step"
        ],
        "field_structure_event_ids": [
            event.record_id for event in state.events if event.kind == "field_structure_event"
        ],
        "playable_consequence_ids": [
            event.payload.get("consequence_id", event.record_id)
            for event in state.events
            if event.kind == "playable_consequence"
        ],
        "source_record_ids": [record.record_id for record in records],
        "is_authority_state": False,
    }


def _source_object_ids(records: list[Any]) -> list[str]:
    object_ids: list[str] = []
    for record in records:
        for object_id in record.payload.get("source_object_ids", []):
            if object_id not in object_ids:
                object_ids.append(object_id)
    return object_ids


def _field_path_for_object(obj: WorldObject) -> str:
    return f"payload.field_tendency.{obj.object_id}"


def _source_record_bindings(
    state: WorldState,
    obj: WorldObject,
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    extraction_record_id = obj.payload.get("field_extraction_record_id")
    if extraction_record_id:
        for record in state.events:
            if record.record_id == extraction_record_id:
                return (
                    [record.record_id],
                    {
                        record.record_id: {
                            "binding_kind": "payload_field",
                            "object_id": obj.object_id,
                            "field_path": f"payload.extractions_by_object_id.{obj.object_id}",
                        }
                    },
                )

    for record in state.radiative_records:
        tendency = record.payload.get("field_tendency", {})
        if obj.object_id in tendency:
            return (
                [record.record_id],
                {
                    record.record_id: {
                        "binding_kind": "payload_field",
                        "object_id": obj.object_id,
                        "field_path": _field_path_for_object(obj),
                    }
                },
            )

    for record in state.radiative_records + state.events:
        if (
            record.kind in MEMBERSHIP_RECORD_KINDS
            and obj.object_id in record.payload.get("source_object_ids", [])
        ):
            return (
                [record.record_id],
                {
                    record.record_id: {
                        "binding_kind": "source_object_membership",
                        "object_id": obj.object_id,
                        "field_path": "payload.source_object_ids",
                    }
                },
            )

    return [], {}


def _project_center(
    obj: WorldObject,
    *,
    image_plane: dict[str, Any],
    window: dict[str, Any],
) -> tuple[list[float] | None, bool]:
    return _project_world_point(obj.position, image_plane=image_plane, window=window)


def _project_world_point(
    point: list[float],
    *,
    image_plane: dict[str, Any],
    window: dict[str, Any],
) -> tuple[list[float] | None, bool]:
    origin = window.get("origin", [0.0, 0.0])
    extent = window.get("extent", [1.0, 1.0])
    width = float(image_plane.get("width", DEFAULT_IMAGE_PLANE["width"]))
    height = float(image_plane.get("height", DEFAULT_IMAGE_PLANE["height"]))
    margin = float(image_plane.get("margin", min(width, height) * 0.08))
    normalized_x = (float(point[0]) - origin[0]) / extent[0]
    normalized_y = (float(point[1]) - origin[1]) / extent[1]
    if normalized_x < 0 or normalized_x > 1 or normalized_y < 0 or normalized_y > 1:
        return None, False
    return [
        margin + normalized_x * (width - margin * 2),
        height - margin - normalized_y * (height - margin * 2),
    ], True


def _covariance(
    obj: WorldObject,
    *,
    image_plane: dict[str, Any],
    window: dict[str, Any],
) -> list[list[float]]:
    extent = obj.payload.get("extent", [1.0, 1.0])
    window_extent = window.get("extent", [1.0, 1.0])
    width = float(image_plane.get("width", DEFAULT_IMAGE_PLANE["width"]))
    height = float(image_plane.get("height", DEFAULT_IMAGE_PLANE["height"]))
    sigma_x = max(8.0, float(extent[0]) / float(window_extent[0]) * width * 0.18)
    sigma_y = max(8.0, float(extent[1]) / float(window_extent[1]) * height * 0.18)
    return [[sigma_x**2, 0.0], [0.0, sigma_y**2]]


def _object_has_interaction(state: WorldState, obj: WorldObject) -> bool:
    return any(
        obj.object_id in record.payload.get("source_object_ids", [])
        for record in state.interaction_records
    )


def _intensity(state: WorldState, obj: WorldObject) -> float:
    base = 0.35 + 0.45 * obj.continuity_score
    radiative_boost = 0.10 if state.radiative_records else 0.0
    interaction_boost = 0.15 if _object_has_interaction(state, obj) else 0.0
    return _clamp(base + radiative_boost + interaction_boost)


def _opacity(obj: WorldObject) -> float:
    return _clamp(0.35 + 0.55 * obj.stability_score)


def attach_spectral_observation_to_payload(
    payload: dict[str, Any],
    spectral_observation: dict[str, Any],
) -> dict[str, Any]:
    if spectral_observation.get("is_authority_state") is not False:
        raise ValueError("spectral observation payload must be non-authority.")
    if spectral_observation.get("spectral_projection_schema") != "substrate_spectral_observation_v1":
        raise ValueError("Unsupported spectral observation payload schema.")
    merged = dict(payload)
    merged["spectral_observation"] = dict(spectral_observation)
    return merged


def attach_spectral_observations_by_observer_to_payload(
    payload: dict[str, Any],
    multi_observer_spectral_observation: dict[str, Any],
) -> dict[str, Any]:
    if multi_observer_spectral_observation.get("is_authority_state") is not False:
        raise ValueError("multi-observer spectral observation payload must be non-authority.")
    if (
        multi_observer_spectral_observation.get("spectral_projection_schema")
        != "multi_observer_substrate_spectral_observation_v1"
    ):
        raise ValueError("Unsupported multi-observer spectral observation payload schema.")
    merged = dict(payload)
    merged["declared_observer_frequency_windows"] = dict(
        multi_observer_spectral_observation["declared_observer_frequency_windows"]
    )
    merged["spectral_observations_by_observer"] = dict(
        multi_observer_spectral_observation["spectral_observations_by_observer"]
    )
    merged["spectral_source_record_ids"] = list(multi_observer_spectral_observation["source_record_ids"])
    merged["spectral_projection_schema"] = multi_observer_spectral_observation["spectral_projection_schema"]
    return merged


def attach_spectral_camera_frame_to_payload(
    payload: dict[str, Any],
    spectral_camera_frame: dict[str, Any],
) -> dict[str, Any]:
    if not spectral_camera_frame:
        raise ValueError("spectral_camera_frame is required")
    if spectral_camera_frame.get("schema") != "spectral_camera_frame_v1":
        raise ValueError("Unsupported spectral camera frame schema.")
    if spectral_camera_frame.get("is_authority_state") is not False:
        raise ValueError("spectral camera frame must be non-authority.")
    merged = dict(payload)
    debug_layers: dict[str, Any] = {}
    for key in sorted(SPECTRAL_CAMERA_DEBUG_LAYER_KEYS):
        if key in merged:
            debug_layers[key] = merged.pop(key)
    existing_debug_layers = merged.get("debug_layers")
    if isinstance(existing_debug_layers, dict):
        debug_layers.update(existing_debug_layers.get("layers", {}))
    merged["render_mode"] = "spectral_camera_observation_v1"
    merged["spectral_camera_frame"] = dict(spectral_camera_frame)
    merged["debug_layers"] = {
        "schema": "spectral_camera_debug_layers_v1",
        "default_enabled": False,
        "is_authority_state": False,
        "layers": debug_layers,
    }
    return merged


def attach_spectral_image_plane_to_payload(
    payload: dict[str, Any],
    spectral_image_plane: dict[str, Any],
) -> dict[str, Any]:
    if not spectral_image_plane:
        raise ValueError("spectral_image_plane is required")
    if spectral_image_plane.get("schema") != "spectral_image_plane_v1":
        raise ValueError("Unsupported spectral image plane schema.")
    if spectral_image_plane.get("is_authority_state") is not False:
        raise ValueError("spectral image plane must be non-authority.")
    merged = dict(payload)
    existing_debug_layers = merged.get("debug_layers")
    if not isinstance(existing_debug_layers, dict) or existing_debug_layers.get("schema") != "spectral_camera_debug_layers_v1":
        merged["debug_layers"] = {
            "schema": "spectral_camera_debug_layers_v1",
            "default_enabled": False,
            "is_authority_state": False,
            "layers": {},
        }
    else:
        merged["debug_layers"] = {
            **existing_debug_layers,
            "default_enabled": False,
            "is_authority_state": False,
            "layers": dict(existing_debug_layers.get("layers", {})),
        }
    merged["render_mode"] = "continuous_spectral_world_window_v1"
    merged["spectral_image_plane"] = dict(spectral_image_plane)
    return merged


def attach_spectral_image_plane_to_projection_frame(
    frame: ProjectionFrame,
    spectral_image_plane: dict[str, Any],
) -> ProjectionFrame:
    return replace(
        frame,
        payload=attach_spectral_image_plane_to_payload(dict(frame.payload), spectral_image_plane),
    )


def attach_implicit_field_payload_to_projection_frame(
    frame: ProjectionFrame,
    *,
    implicit_field_state: dict[str, Any],
    implicit_authority_certificate: dict[str, Any],
    implicit_basis_records: list[dict[str, Any]],
    implicit_evaluation_records: list[dict[str, Any]],
    implicit_observer_path_record: dict[str, Any],
    implicit_ray_sample_record: dict[str, Any],
    implicit_spectral_image_plane: dict[str, Any],
    implicit_refinement_patch_ids: list[str],
    implicit_baseline_comparison_ids: list[str],
) -> ProjectionFrame:
    validate_implicit_field_state(implicit_field_state)
    validate_implicit_field_authority_certificate(implicit_authority_certificate, implicit_field_state)
    validate_implicit_observer_path_record(implicit_observer_path_record)
    validate_implicit_ray_sample_record(implicit_ray_sample_record)
    validate_implicit_spectral_image_plane(implicit_spectral_image_plane)
    payload = dict(frame.payload)
    existing_debug_layers = payload.get("debug_layers")
    if not isinstance(existing_debug_layers, dict) or existing_debug_layers.get("schema") != "spectral_camera_debug_layers_v1":
        payload["debug_layers"] = {
            "schema": "spectral_camera_debug_layers_v1",
            "default_enabled": False,
            "is_authority_state": False,
            "layers": {},
        }
    else:
        payload["debug_layers"] = {
            **existing_debug_layers,
            "default_enabled": False,
            "is_authority_state": False,
            "layers": dict(existing_debug_layers.get("layers", {})),
        }
    payload.update(
        {
            "render_mode": "implicit_3d_field_observation",
            "implicit_observation_label": "implicit ray observation",
            "implicit_field_state_id": implicit_field_state["implicit_field_state_id"],
            "implicit_authority_certificate_id": implicit_authority_certificate["certificate_id"],
            "implicit_basis_ids": [basis["basis_id"] for basis in implicit_basis_records],
            "implicit_evaluation_ids": [record["evaluation_id"] for record in implicit_evaluation_records],
            "implicit_observer_path_id": implicit_observer_path_record["observer_path_id"],
            "implicit_ray_sample_record": dict(implicit_ray_sample_record),
            "implicit_spectral_image_plane": dict(implicit_spectral_image_plane),
            "implicit_refinement_patch_ids": [str(value) for value in implicit_refinement_patch_ids],
            "implicit_baseline_comparison_ids": [str(value) for value in implicit_baseline_comparison_ids],
        }
    )
    source_record_ids = sorted(
        {
            *[str(value) for value in frame.source_record_ids],
            str(implicit_field_state["implicit_field_state_id"]),
            str(implicit_authority_certificate["certificate_id"]),
            *[str(basis["basis_id"]) for basis in implicit_basis_records],
            *[str(record["evaluation_id"]) for record in implicit_evaluation_records],
            str(implicit_observer_path_record["observer_path_id"]),
            str(implicit_ray_sample_record["ray_sample_record_id"]),
            str(implicit_spectral_image_plane["image_plane_id"]),
        }
    )
    return replace(frame, payload=payload, source_record_ids=source_record_ids)


def attach_spectral_camera_frame_to_projection_frame(
    frame: ProjectionFrame,
    spectral_camera_frame: dict[str, Any],
) -> ProjectionFrame:
    return replace(
        frame,
        payload=attach_spectral_camera_frame_to_payload(dict(frame.payload), spectral_camera_frame),
    )


def attach_projection_invariant_boundary_records_to_projection_frame(
    frame: ProjectionFrame,
    *,
    projection_loss_manifest: ProjectionLossManifest,
    invariant_signatures: tuple[InvariantSignature, ...] = (),
    boundary_crossing_records: tuple[BoundaryCrossingRecord, ...] = (),
    phase_transition_records: tuple[PhaseTransitionRecord, ...] = (),
    genesis_rule_evidence: tuple[GenesisRuleEvidence, ...] = (),
) -> ProjectionFrame:
    manifest_payload = projection_loss_manifest.to_payload()["projection_loss_manifest_v1"]
    if manifest_payload["projection_frame_id"] != frame.frame_id:
        raise ValueError("projection loss manifest must cite the frame it is attached to")
    if manifest_payload["observer_id"] != frame.observer_id:
        raise ValueError("projection loss manifest observer_id must match frame observer")
    signature_payloads = [signature.to_payload()["invariant_signature_v1"] for signature in invariant_signatures]
    boundary_payloads = [record.to_payload()["boundary_crossing_record_v1"] for record in boundary_crossing_records]
    transition_payloads = [record.to_payload()["phase_transition_record_v1"] for record in phase_transition_records]
    genesis_payloads = [record.to_payload()["genesis_rule_evidence_v1"] for record in genesis_rule_evidence]
    payload = dict(frame.payload)
    payload["projection_loss_manifest_v1"] = manifest_payload
    payload["invariant_signatures_v1"] = signature_payloads
    payload["boundary_crossing_records_v1"] = boundary_payloads
    payload["phase_transition_records_v1"] = transition_payloads
    payload["genesis_rule_evidence_v1"] = genesis_payloads
    payload["m13_projection_invariant_boundary_v1"] = {
        "schema": M13_SCHEMA_VERSION,
        "projection_loss_manifest_id": manifest_payload["manifest_id"],
        "invariant_signature_ids": [item["signature_id"] for item in signature_payloads],
        "boundary_crossing_ids": [item["boundary_crossing_id"] for item in boundary_payloads],
        "phase_transition_ids": [item["phase_transition_id"] for item in transition_payloads],
        "genesis_rule_evidence_ids": [item["genesis_rule_id"] for item in genesis_payloads],
        "completion_requires_sidecar_readback": True,
        "viewer_is_not_authority": True,
    }
    added_record_ids = [
        manifest_payload["manifest_id"],
        *[item["signature_id"] for item in signature_payloads],
        *[item["boundary_crossing_id"] for item in boundary_payloads],
        *[item["phase_transition_id"] for item in transition_payloads],
        *[item["genesis_rule_id"] for item in genesis_payloads],
    ]
    payload_sources = list(dict.fromkeys([*map(str, payload.get("source_record_ids", [])), *added_record_ids]))
    payload["source_record_ids"] = payload_sources
    timeline = dict(payload.get("event_timeline", {}))
    timeline["source_record_ids"] = list(dict.fromkeys([*map(str, timeline.get("source_record_ids", [])), *added_record_ids]))
    payload["event_timeline"] = timeline
    return replace(
        frame,
        payload=payload,
        source_record_ids=list(dict.fromkeys([*map(str, frame.source_record_ids), *added_record_ids])),
    )


def _sample_for_object(
    state: WorldState,
    obj: WorldObject,
    *,
    image_plane: dict[str, Any],
    window: dict[str, Any],
) -> ProjectionSample | None:
    center, renderable = _project_center(obj, image_plane=image_plane, window=window)
    if not renderable or center is None:
        return None

    source_record_ids, bindings = _source_record_bindings(state, obj)
    if not source_record_ids:
        return None

    return ProjectionSample(
        sample_id=f"sample::{state.tick}::{obj.object_id}",
        object_id=obj.object_id,
        family=obj.family,
        center=center,
        covariance=_covariance(obj, image_plane=image_plane, window=window),
        intensity=_intensity(state, obj),
        opacity=_opacity(obj),
        color_hint=FAMILY_COLORS.get(obj.family, "#b3b3b3"),
        source_state_ticks=[state.tick],
        source_object_ids=[obj.object_id],
        source_record_ids=source_record_ids,
        payload={
            "kernel": "anisotropic_gaussian_2d",
            "record_bindings": bindings,
            "renderable": True,
            **{
                key: obj.payload[key]
                for key in [
                    "derived_from_field_state_id",
                    "field_channel",
                    "field_centroid",
                    "field_centroid_world",
                    "field_centroid_grid",
                    "field_extraction_record_id",
                    "field_energy",
                ]
                if key in obj.payload
            },
        },
    )


def _frame_audit(state: WorldState) -> dict[str, Any]:
    audit = {
        "projection_semantics": "observer_projection_not_object_painting",
        "kernel": "anisotropic_gaussian_2d",
        "light_model": "derived_on_demand",
        "no_persistent_light_object": True,
        "no_material_asset_authority": True,
        "no_global_raindrop_authority_state": True,
        "no_mesh_material_light_pipeline": True,
    }
    if state.payload.get("runtime_mode") == "field":
        audit["authority_substrate"] = "FieldState"
    return audit


def _overlay(
    *,
    state: WorldState,
    phenomenon: str,
    kind: str,
    visual_operator: str,
    parameters: dict[str, Any],
    records: list[Any],
    payload: dict[str, Any],
) -> PhenomenonOverlay:
    return PhenomenonOverlay(
        overlay_id=f"overlay::{phenomenon}::{state.tick}",
        phenomenon=phenomenon,
        kind=kind,
        visual_operator=visual_operator,
        parameters=parameters,
        source_state_ticks=[state.tick],
        source_object_ids=_source_object_ids(records)
        or [obj.object_id for obj in state.objects],
        source_record_ids=[record.record_id for record in records],
        payload={"is_authority_entity": False, **payload},
    )


def _background_flux_strength(state: WorldState) -> float:
    return _clamp(0.10 + 0.02 * len(_record_ids(state)), 0.0, 0.45)


def _build_overlays(state: WorldState) -> list[PhenomenonOverlay]:
    overlays: list[PhenomenonOverlay] = []
    if state.radiative_records:
        overlays.append(
            _overlay(
                state=state,
                phenomenon="wind",
                kind="field_tendency",
                visual_operator="flow_vector_field",
                parameters={"strength": 0.35},
                records=list(state.radiative_records),
                payload={"derived_from": "radiative_records"},
            )
        )
        overlays.append(
            _overlay(
                state=state,
                phenomenon="light",
                kind="observer_derived_radiative_result",
                visual_operator="radiative_halo",
                parameters={"intensity": 0.65},
                records=list(state.radiative_records),
                payload={
                    "derived_from": "radiative_records",
                    "derived_on_demand": True,
                    "is_persistent_light_object": False,
                },
            )
        )

    flux_records = state.events + state.radiative_records + state.interaction_records
    overlays.append(
        _overlay(
            state=state,
            phenomenon="background_flux",
            kind="local_manifestation_likelihood",
            visual_operator="spectral_flux_noise",
            parameters={"strength": _background_flux_strength(state)},
            records=flux_records,
            payload={
                "derived_from": "local_field_manifestation_probability",
                "no_global_raindrop_authority_state": True,
                "display_label": "background_flux",
            },
        )
    )

    high_energy_events = [
        event for event in state.events if event.kind in HIGH_ENERGY_EVENT_KINDS
    ]
    discharge_interaction_records = [
        record
        for record in state.interaction_records
        if record.kind != "field_affordance_interaction"
    ]
    if discharge_interaction_records or high_energy_events:
        overlays.append(
            _overlay(
                state=state,
                phenomenon="discharge",
                kind="event_driven_emissive_projection",
                visual_operator="event_pulse",
                parameters={"strength": 1.0},
                records=discharge_interaction_records + high_energy_events,
                payload={
                    "derived_from": "event_or_interaction_records",
                    "persistent_lightning_object": False,
                    "renderable": True,
                },
            )
        )

    return overlays


def _structure_event_records(state: WorldState) -> list[Any]:
    return [event for event in state.events if event.kind == "field_structure_event"]


def _field_object_extraction_records(state: WorldState) -> list[Any]:
    return [event for event in state.events if event.kind == "field_object_extraction"]


def _project_grid_bounds(
    bounds_grid: list[int],
    *,
    coordinate_frame: dict[str, Any],
    image_plane: dict[str, Any],
    window: dict[str, Any],
) -> tuple[list[float] | None, bool]:
    if len(bounds_grid) != 4:
        return None, False
    min_col, min_row, max_col, max_row = bounds_grid
    corners_world = [
        grid_to_world([min_col, min_row], coordinate_frame),
        grid_to_world([max_col, min_row], coordinate_frame),
        grid_to_world([max_col, max_row], coordinate_frame),
        grid_to_world([min_col, max_row], coordinate_frame),
    ]
    projected = [
        _project_world_point(point, image_plane=image_plane, window=window)
        for point in corners_world
    ]
    if not all(renderable for _, renderable in projected):
        return None, False
    xs = [point[0][0] for point in projected if point[0] is not None]
    ys = [point[0][1] for point in projected if point[0] is not None]
    return [min(xs), min(ys), max(xs), max(ys)], True


def _field_structure_projection(
    state: WorldState,
    *,
    image_plane: dict[str, Any],
    window: dict[str, Any],
) -> dict[str, Any]:
    metrics = state.payload.get("field_structure_metrics", {})
    components = metrics.get("components", [])
    coordinate_frame = state.payload.get("coordinate_frame", {})
    structure_records = _structure_event_records(state)
    extraction_records = _field_object_extraction_records(state)
    event_kinds = sorted(
        {
            kind
            for record in structure_records
            for kind in record.payload.get("event_kinds", [])
        }
    )
    object_by_component = {
        obj.payload.get("field_component_id"): obj
        for obj in state.objects
        if obj.payload.get("field_component_id")
    }
    projected_components: list[dict[str, Any]] = []
    for component in components:
        component_id = component.get("component_id")
        obj = object_by_component.get(component_id)
        centroid_world = list(component.get("centroid_world", []))
        image_centroid, center_renderable = (
            _project_world_point(centroid_world, image_plane=image_plane, window=window)
            if len(centroid_world) == 2
            else (None, False)
        )
        image_bounds, bounds_renderable = _project_grid_bounds(
            list(component.get("support_bounds_grid", [])),
            coordinate_frame=coordinate_frame,
            image_plane=image_plane,
            window=window,
        )
        source_record_ids: list[str] = []
        if obj and obj.payload.get("field_extraction_record_id"):
            source_record_ids.append(obj.payload["field_extraction_record_id"])
        for record in structure_records:
            if record.record_id not in source_record_ids:
                source_record_ids.append(record.record_id)
        for record in extraction_records:
            if (
                obj
                and obj.object_id in record.payload.get("extractions_by_object_id", {})
                and record.record_id not in source_record_ids
            ):
                source_record_ids.append(record.record_id)

        projected_components.append(
            {
                "component_id": component_id,
                "object_id": obj.object_id if obj else None,
                "family": component.get("family"),
                "field_channel": component.get("channel"),
                "mode_signature": component.get("mode_signature"),
                "image_bounds": image_bounds,
                "image_centroid": image_centroid,
                "support_size": component.get("support_size"),
                "field_energy": component.get("energy"),
                "event_kinds": event_kinds,
                "source_record_ids": source_record_ids,
                "renderable": bool(center_renderable and bounds_renderable),
                "is_authority_state": False,
            }
        )

    return {
        "schema": "field_structure_projection_v1",
        "is_authority_state": False,
        "source": "derived_from_world_state_field_structure_metrics",
        "component_count": len(projected_components),
        "event_kinds": event_kinds,
        "source_record_ids": [
            record.record_id for record in structure_records + extraction_records
        ],
        "components": projected_components,
    }


def _interaction_visual_payload(
    state: WorldState,
    *,
    frame_id: str,
    observer_id: str,
) -> dict[str, Any]:
    wave_step_ids = [
        event.record_id for event in state.events if event.kind == "field_wave_step"
    ]
    overlays: list[dict[str, Any]] = []
    traces_by_id: dict[str, dict[str, Any]] = {}
    active_trace_ids: list[str] = []
    for record in state.interaction_records:
        if record.kind == "field_affordance_interaction":
            continue
        payload = record.payload
        command_ids = list(payload.get("command_ids", []))
        if not command_ids:
            continue
        command_id = command_ids[0]
        generated_command_ids = list(payload.get("generated_command_ids", command_ids))
        parent_request_id = payload.get("parent_request_id") or payload.get("request_id")
        trace_id = payload.get("interaction_trace_id") or f"interaction-trace::{parent_request_id}"
        source_record_ids = [record.record_id] + [
            wave_step_id for wave_step_id in wave_step_ids if wave_step_id != record.record_id
        ]
        overlay = {
            "schema": "interaction_overlay_v1",
            "is_authority_state": False,
            "command_id": command_id,
            "request_id": payload.get("request_id"),
            "parent_request_id": parent_request_id,
            "interaction_trace_id": trace_id,
            "command_sequence_index": payload.get("command_sequence_index", 0),
            "command_sequence_count": payload.get("command_sequence_count", 1),
            "generated_command_ids": generated_command_ids,
            "interaction_record_id": record.record_id,
            "wave_step_record_id": wave_step_ids[0] if wave_step_ids else None,
            "observer_id": payload.get("observer_id") or observer_id,
            "source_frame_tick": payload.get("source_frame_tick"),
            "applied_tick": state.tick,
            "tool": payload.get("tool_semantics") or payload.get("tool"),
            "channel": payload.get("target_channel") or payload.get("channel"),
            "source_image_xy": payload.get("source_image_xy"),
            "center_world": payload.get("center_world"),
            "center_grid": payload.get("center_grid"),
            "radius_grid": payload.get("radius_grid"),
            "source_region_grid": payload.get("source_region_grid"),
            "source_region_clipped": payload.get("source_region_clipped", False),
            "source_vector_image": payload.get("source_vector_image") or [0.0, 0.0],
            "source_vector_world": payload.get("source_vector_world") or [0.0, 0.0],
            "source_amplitude": payload.get("source_amplitude"),
            "source_record_ids": source_record_ids,
        }
        overlays.append(overlay)
        if trace_id not in active_trace_ids:
            active_trace_ids.append(trace_id)
        trace = traces_by_id.setdefault(
            trace_id,
            {
                "schema": "interaction_trace_v1",
                "is_authority_state": False,
                "interaction_trace_id": trace_id,
                "parent_request_id": parent_request_id,
                "tool": payload.get("tool_semantics") or payload.get("tool"),
                "generated_command_ids": generated_command_ids,
                "interaction_record_ids": [],
                "wave_step_record_ids": [],
                "resulting_projection_frame_ids": [],
                "source_record_ids": [],
            },
        )
        if record.record_id not in trace["interaction_record_ids"]:
            trace["interaction_record_ids"].append(record.record_id)
        for wave_step_id in wave_step_ids:
            if wave_step_id not in trace["wave_step_record_ids"]:
                trace["wave_step_record_ids"].append(wave_step_id)
        if frame_id not in trace["resulting_projection_frame_ids"]:
            trace["resulting_projection_frame_ids"].append(frame_id)
        for source_record_id in source_record_ids:
            if source_record_id not in trace["source_record_ids"]:
                trace["source_record_ids"].append(source_record_id)
    return {
        "interaction_overlays": overlays,
        "interaction_traces": list(traces_by_id.values()),
        "active_interaction_trace_ids": active_trace_ids,
    }


def _affordance_overlays(
    state: WorldState,
    *,
    image_plane: dict[str, Any],
    window: dict[str, Any],
    observer_id: str,
) -> list[dict[str, Any]]:
    coordinate_frame = state.payload.get("coordinate_frame", {})
    definition_by_affordance_id = {
        event.payload.get("affordance_id"): event
        for event in state.events
        if event.kind == "field_affordance_definition"
    }
    wave_step_ids = [
        event.record_id for event in state.events if event.kind == "field_wave_step"
    ]
    overlays: list[dict[str, Any]] = []
    for event in state.events:
        if event.kind != "field_affordance_application":
            continue
        payload = event.payload
        affordance_id = payload.get("affordance_id")
        definition = definition_by_affordance_id.get(affordance_id)
        definition_payload = definition.payload if definition is not None else {}
        region_grid = list(payload.get("region_grid", definition_payload.get("region_grid", [])))
        image_region, visible = _project_grid_bounds(
            region_grid,
            coordinate_frame=coordinate_frame,
            image_plane=image_plane,
            window=window,
        )
        definition_record_id = payload.get("definition_record_id") or (
            definition.record_id if definition is not None else None
        )
        source_record_ids: list[str] = []
        for record_id in [
            definition_record_id,
            event.record_id,
            *wave_step_ids,
            *payload.get("source_record_ids", []),
        ]:
            if record_id and record_id not in source_record_ids:
                source_record_ids.append(record_id)
        valid_from_tick = definition_payload.get("valid_from_tick", payload.get("field_state_tick"))
        valid_to_tick = definition_payload.get("valid_to_tick", payload.get("applied_to_tick", state.tick) + 1)
        overlays.append(
            {
                "schema": "field_affordance_overlay_v1",
                "is_authority_state": False,
                "affordance_id": affordance_id,
                "origin_type": definition_payload.get("origin_type", "user_authored"),
                "affordance_kind": payload.get("affordance_kind"),
                "channel": payload.get("channel", definition_payload.get("channel")),
                "observer_id": observer_id,
                "visible": visible,
                "region_grid": region_grid,
                "image_region": image_region,
                "active": bool(valid_from_tick is None or int(valid_from_tick) <= state.tick < int(valid_to_tick)),
                "valid_from_tick": valid_from_tick,
                "valid_to_tick": valid_to_tick,
                "effect": dict(payload.get("effect", definition_payload.get("effect", {}))),
                "source_record_ids": source_record_ids,
            }
        )
    return overlays


def _bounds_to_dict(bounds: dict[str, Any] | list[Any]) -> dict[str, int]:
    if isinstance(bounds, dict):
        return {
            "min_x": int(bounds["min_x"]),
            "min_y": int(bounds["min_y"]),
            "max_x": int(bounds["max_x"]),
            "max_y": int(bounds["max_y"]),
        }
    if len(bounds) != 4:
        raise ValueError("playable consequence support_grid must contain four bounds")
    return {
        "min_x": int(bounds[0]),
        "min_y": int(bounds[1]),
        "max_x": int(bounds[2]),
        "max_y": int(bounds[3]),
    }


def _playable_spectral_band(kind: str) -> str:
    if kind == "dampening_absorption":
        return "low"
    if kind == "boundary_containment":
        return "boundary"
    if kind in {"source_maintenance", "local_perturbation_response"}:
        return "high"
    if kind in {"channel_transport", "cohesion_accumulation"}:
        return "mid"
    return "flux"


def _playable_consequence_overlays(
    state: WorldState,
    *,
    image_plane: dict[str, Any],
    window: dict[str, Any],
    observer_id: str,
) -> list[dict[str, Any]]:
    coordinate_frame = state.payload.get("coordinate_frame", {})
    overlays: list[dict[str, Any]] = []
    for event in state.events:
        if event.kind != "playable_consequence":
            continue
        payload = event.payload
        kind = str(payload.get("kind", "playable_consequence"))
        support_grid = _bounds_to_dict(payload.get("support_grid", payload.get("region_grid", [0, 0, 0, 0])))
        image_region = None
        visible = False
        if coordinate_frame:
            image_region, visible = _project_grid_bounds(
                [
                    support_grid["min_x"],
                    support_grid["min_y"],
                    support_grid["max_x"],
                    support_grid["max_y"],
                ],
                coordinate_frame=coordinate_frame,
                image_plane=image_plane,
                window=window,
            )
        source_record_ids: list[str] = []
        for record_id in [
            event.record_id,
            *payload.get("source_record_ids", []),
            *payload.get("source_wave_step_record_ids", []),
            *payload.get("source_material_response_record_ids", []),
            *payload.get("source_property_record_ids", []),
        ]:
            if record_id and record_id not in source_record_ids:
                source_record_ids.append(record_id)
        overlays.append(
            {
                "schema": "playable_consequence_overlay_v1",
                "is_authority_state": False,
                "consequence_id": payload.get("consequence_id", event.record_id),
                "kind": kind,
                "observer_id": observer_id,
                "visible": visible,
                "support_grid": support_grid,
                "image_region": image_region,
                "centroid_world": list(payload.get("centroid_world", payload.get("metrics", {}).get("centroid_world", [0.0, 0.0]))),
                "spectral_band": payload.get("spectral_band", _playable_spectral_band(kind)),
                "status": payload.get("overlay_status", "active" if payload.get("status") == "passed" else "settled"),
                "source_record_ids": source_record_ids,
            }
        )
    return overlays


def build_projection_frames(
    states: list[WorldState],
    observer: dict[str, Any],
) -> list[ProjectionFrame]:
    if not states:
        raise ValueError("states must not be empty")

    observer_id = observer.get("observer_id", "observer::pinhole-default")
    image_plane = dict(observer.get("image_plane", DEFAULT_IMAGE_PLANE))
    window = dict(observer.get("window", DEFAULT_WINDOW))
    frames: list[ProjectionFrame] = []
    for state in states:
        frame_id = f"projection-frame::{observer_id}::{state.tick}"
        interaction_visuals = _interaction_visual_payload(
            state,
            frame_id=frame_id,
            observer_id=observer_id,
        )
        samples = [
            sample
            for obj in state.objects
            if (
                sample := _sample_for_object(
                    state,
                    obj,
                    image_plane=image_plane,
                    window=window,
                )
            )
            is not None
        ]
        frames.append(
            ProjectionFrame(
                frame_id=frame_id,
                tick=state.tick,
                observer_id=observer_id,
                image_plane={
                    **image_plane,
                    "margin": float(image_plane.get("margin", min(
                        float(image_plane.get("width", DEFAULT_IMAGE_PLANE["width"])),
                        float(image_plane.get("height", DEFAULT_IMAGE_PLANE["height"])),
                    ) * 0.08)),
                    "window": {
                        "origin": list(window.get("origin", DEFAULT_WINDOW["origin"])),
                        "extent": list(window.get("extent", DEFAULT_WINDOW["extent"])),
                    },
                    "observer_model": "pinhole",
                },
                samples=samples,
                phenomena_overlays=_build_overlays(state),
                source_state_ticks=[state.tick],
                source_object_ids=[obj.object_id for obj in state.objects],
                source_record_ids=_record_ids(state),
                is_authority_state=False,
                audit=_frame_audit(state),
                payload={
                    "playable_mode": build_playable_projection_mode(),
                    "event_timeline": _event_timeline(state, observer_id),
                    "field_structure_projection": _field_structure_projection(
                        state,
                        image_plane=image_plane,
                        window=window,
                    ),
                    "affordance_overlays": _affordance_overlays(
                        state,
                        image_plane=image_plane,
                        window=window,
                        observer_id=observer_id,
                    ),
                    "playable_consequence_overlays": _playable_consequence_overlays(
                        state,
                        image_plane=image_plane,
                        window=window,
                        observer_id=observer_id,
                    ),
                    "field_derived_affordance_summaries": derive_field_affordance_summaries(state),
                    **interaction_visuals,
                },
            )
        )
    return frames


def _unique(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


def _macro_frame_audit() -> dict[str, Any]:
    return {
        "projection_semantics": "observer_projection_not_object_painting",
        "kernel": "macro_bounds_and_centroid_projection_v1",
        "light_model": "derived_on_demand",
        "no_persistent_light_object": True,
        "no_material_asset_authority": True,
        "no_global_raindrop_authority_state": True,
        "no_mesh_material_light_pipeline": True,
        "authority_substrate": "MacroFieldState",
    }


def _macro_sample(
    macro_state: MacroFieldState,
    certificate: StableStructureCertificate | None,
    projection_record: MacroProjectionRecord | None,
    *,
    image_plane: dict[str, Any],
    window: dict[str, Any],
) -> ProjectionSample | None:
    coarse = macro_state.invariants.get("coarse_component_projection", {})
    centroid_world = coarse.get("centroid_world")
    if not centroid_world:
        center_grid = [
            (float(macro_state.support_bounds_grid[0]) + float(macro_state.support_bounds_grid[2])) / 2.0,
            (float(macro_state.support_bounds_grid[1]) + float(macro_state.support_bounds_grid[3])) / 2.0,
        ]
        centroid_world = grid_to_world(center_grid, macro_state.coordinate_frame)
    center, renderable = _project_world_point(
        list(centroid_world),
        image_plane=image_plane,
        window=window,
    )
    if not renderable or center is None:
        return None
    source_record_ids = _unique([
        projection_record.record_id if projection_record else "",
        macro_state.certificate_id,
        certificate.certificate_id if certificate else "",
        macro_state.macro_state_id,
        *macro_state.source_record_ids,
    ])
    return ProjectionSample(
        sample_id=f"sample::macro::{macro_state.macro_state_id}",
        object_id=macro_state.macro_state_id,
        family="macro_field_state",
        center=center,
        covariance=[[1600.0, 0.0], [0.0, 1600.0]],
        intensity=0.72,
        opacity=0.48,
        color_hint="#f0b429",
        source_state_ticks=list(macro_state.tick_range),
        source_object_ids=[macro_state.macro_state_id],
        source_record_ids=source_record_ids,
        payload={
            "projection_source_type": "macro_field_state",
            "source_macro_state_id": macro_state.macro_state_id,
            "macro_certificate_id": macro_state.certificate_id,
            "macro_projection_record_id": projection_record.record_id if projection_record else None,
            "support_bounds_grid": list(macro_state.support_bounds_grid),
            "support_bounds_world": list(macro_state.support_bounds_world),
            "error_bounds": dict(macro_state.error_bounds),
            "is_authority_state": False,
        },
    )


def _fine_patch_sample(
    patch: FineRefinementPatch,
    request: FineRefinementRequest | None,
    *,
    coordinate_frame: dict[str, Any],
    image_plane: dict[str, Any],
    window: dict[str, Any],
) -> ProjectionSample | None:
    center_grid = [
        (float(patch.region_grid[0]) + float(patch.region_grid[2])) / 2.0,
        (float(patch.region_grid[1]) + float(patch.region_grid[3])) / 2.0,
    ]
    center_world = grid_to_world(center_grid, coordinate_frame)
    center, renderable = _project_world_point(center_world, image_plane=image_plane, window=window)
    if not renderable or center is None:
        return None
    source_record_ids = _unique([
        patch.patch_id,
        patch.refinement_request_id,
        request.request_id if request else "",
        patch.macro_state_id,
        *patch.source_record_ids,
    ])
    return ProjectionSample(
        sample_id=f"sample::fine-refinement::{patch.patch_id}",
        object_id=patch.patch_id,
        family="fine_refinement_patch",
        center=center,
        covariance=[[900.0, 0.0], [0.0, 900.0]],
        intensity=0.86,
        opacity=0.55,
        color_hint="#4cc9f0",
        source_state_ticks=[patch.tick],
        source_object_ids=[patch.patch_id],
        source_record_ids=source_record_ids,
        payload={
            "projection_source_type": "fine_refinement_patch",
            "fine_refinement_patch_id": patch.patch_id,
            "fine_refinement_request_id": patch.refinement_request_id,
            "source_macro_state_id": patch.macro_state_id,
            "region_grid": list(patch.region_grid),
            "is_authority_state": False,
        },
    )


def _macro_overlay(
    macro_state: MacroFieldState,
    certificate: StableStructureCertificate | None,
    projection_record: MacroProjectionRecord | None,
    *,
    image_plane: dict[str, Any],
    window: dict[str, Any],
) -> dict[str, Any]:
    image_bounds, visible = _project_grid_bounds(
        list(macro_state.support_bounds_grid),
        coordinate_frame=macro_state.coordinate_frame,
        image_plane=image_plane,
        window=window,
    )
    return {
        "schema": "macro_state_overlay_v1",
        "is_authority_state": False,
        "source_macro_state_id": macro_state.macro_state_id,
        "macro_certificate_id": macro_state.certificate_id,
        "macro_projection_record_id": projection_record.record_id if projection_record else None,
        "visible": visible,
        "support_bounds_grid": list(macro_state.support_bounds_grid),
        "support_bounds_world": list(macro_state.support_bounds_world),
        "image_bounds": image_bounds,
        "validity_envelope": dict(certificate.validity_envelope if certificate else {}),
        "source_record_ids": _unique([
            projection_record.record_id if projection_record else "",
            macro_state.certificate_id,
            macro_state.macro_state_id,
        ]),
    }


def _fine_overlay(
    patch: FineRefinementPatch,
    request: FineRefinementRequest | None,
    *,
    coordinate_frame: dict[str, Any],
    image_plane: dict[str, Any],
    window: dict[str, Any],
) -> dict[str, Any]:
    image_bounds, visible = _project_grid_bounds(
        list(patch.region_grid),
        coordinate_frame=coordinate_frame,
        image_plane=image_plane,
        window=window,
    )
    return {
        "schema": "fine_refinement_overlay_v1",
        "is_authority_state": False,
        "fine_refinement_patch_id": patch.patch_id,
        "fine_refinement_request_id": patch.refinement_request_id,
        "source_macro_state_id": patch.macro_state_id,
        "trigger_kind": request.trigger_kind if request else None,
        "visible": visible,
        "region_grid": list(patch.region_grid),
        "image_bounds": image_bounds,
        "source_record_ids": _unique([
            patch.patch_id,
            patch.refinement_request_id,
            request.request_id if request else "",
            patch.macro_state_id,
        ]),
    }


def _macro_correction_overlay(
    correction: MacroCorrectionRecord,
    macro_state: MacroFieldState | None,
    *,
    image_plane: dict[str, Any],
    window: dict[str, Any],
) -> dict[str, Any]:
    if macro_state is None:
        return {
            "schema": "macro_correction_overlay_v1",
            "is_authority_state": False,
            "visible": False,
            "macro_correction_record_id": correction.correction_id,
            "source_record_ids": list(correction.source_record_ids),
        }
    image_bounds, visible = _project_grid_bounds(
        list(macro_state.support_bounds_grid),
        coordinate_frame=macro_state.coordinate_frame,
        image_plane=image_plane,
        window=window,
    )
    return {
        "schema": "macro_correction_overlay_v1",
        "is_authority_state": False,
        "visible": visible,
        "macro_correction_record_id": correction.correction_id,
        "fine_patch_outcome_id": correction.fine_patch_outcome_id,
        "pre_correction_macro_state_id": correction.pre_correction_macro_state_id,
        "post_correction_macro_state_id": correction.post_correction_macro_state_id,
        "image_bounds": image_bounds,
        "error_metrics": dict(correction.error_metrics),
        "boundary_flux": dict(correction.boundary_flux),
        "source_record_ids": _unique([
            correction.correction_id,
            correction.fine_patch_outcome_id,
            correction.correction_certificate_extension_id,
            *correction.source_record_ids,
        ]),
    }


def _macro_center_image(
    macro_state: MacroFieldState,
    *,
    image_plane: dict[str, Any],
    window: dict[str, Any],
) -> list[float] | None:
    coarse = macro_state.invariants.get("coarse_component_projection", {})
    center_world = coarse.get("centroid_world")
    if not center_world:
        center_grid = [
            (float(macro_state.support_bounds_grid[0]) + float(macro_state.support_bounds_grid[2])) / 2.0,
            (float(macro_state.support_bounds_grid[1]) + float(macro_state.support_bounds_grid[3])) / 2.0,
        ]
        center_world = grid_to_world(center_grid, macro_state.coordinate_frame)
    center, renderable = _project_world_point(list(center_world), image_plane=image_plane, window=window)
    return center if renderable else None


def _macro_boundary_exchange_overlay(
    exchange: MacroBoundaryExchangeRecord,
    macros_by_id: dict[str, MacroFieldState],
    *,
    image_plane: dict[str, Any],
    window: dict[str, Any],
) -> dict[str, Any]:
    points = [
        _macro_center_image(macros_by_id[macro_state_id], image_plane=image_plane, window=window)
        for macro_state_id in exchange.affected_macro_state_ids
        if macro_state_id in macros_by_id
    ]
    points = [point for point in points if point is not None]
    return {
        "schema": "macro_boundary_exchange_overlay_v1",
        "is_authority_state": False,
        "visible": len(points) >= 2,
        "macro_boundary_exchange_record_id": exchange.exchange_id,
        "affected_macro_state_ids": list(exchange.affected_macro_state_ids),
        "image_points": points,
        "exchange_pairs": [dict(pair) for pair in exchange.exchange_pairs],
        "energy_flux_by_pair": dict(exchange.energy_flux_by_pair),
        "source_record_ids": _unique([exchange.exchange_id, *exchange.source_record_ids]),
    }


def _region_overlay(
    region: WorldRegion,
    *,
    image_plane: dict[str, Any],
    window: dict[str, Any],
    budget_ledger_id: str | None,
    boundary_exchange_ids: list[str],
) -> dict[str, Any]:
    image_bounds, visible = _project_grid_bounds(
        list(region.region_bounds_grid),
        coordinate_frame=region.coordinate_frame,
        image_plane=image_plane,
        window=window,
    )
    return {
        "schema": "region_overlay_v1",
        "region_id": region.region_id,
        "authority_mode": region.authority_mode,
        "region_bounds_grid": list(region.region_bounds_grid),
        "region_bounds_world": list(region.region_bounds_world),
        "image_bounds": image_bounds,
        "visible": visible,
        "region_lifecycle_record_id": region.current_lifecycle_record_id,
        "region_activation_request_ids": [
            source_id for source_id in region.source_record_ids if str(source_id).startswith("region-activation::")
        ],
        "region_boundary_exchange_record_ids": list(boundary_exchange_ids),
        "budget_ledger_id": budget_ledger_id,
        "source_record_ids": _unique(
            [
                region.region_id,
                region.current_lifecycle_record_id,
                region.current_macro_state_id or "",
                region.current_field_state_id or "",
                region.active_fine_patch_id or "",
                *region.source_record_ids,
                *boundary_exchange_ids,
                budget_ledger_id or "",
            ]
        ),
        "is_authority_state": False,
    }


def _region_lifecycle_overlays(
    lifecycle_records: list[RegionLifecycleRecord] | None,
) -> list[dict[str, Any]]:
    overlays: list[dict[str, Any]] = []
    for record in list(lifecycle_records or []):
        overlays.append(
            {
                "schema": "region_lifecycle_overlay_v1",
                "region_lifecycle_record_id": record.record_id,
                "region_id": record.region_id,
                "tick": record.tick,
                "previous_mode": record.previous_mode,
                "next_mode": record.next_mode,
                "transition_kind": record.transition_kind,
                "activation_request_id": record.activation_request_id,
                "budget_ledger_id": record.budget_ledger_id,
                "source_record_ids": _unique([record.record_id, *record.source_record_ids]),
                "is_authority_state": False,
            }
        )
    return overlays


def _region_budget_summary(ledgers: list[RegionBudgetLedger] | None) -> dict[str, Any]:
    ledger = list(ledgers or [])[-1] if ledgers else None
    if ledger is None:
        return {
            "schema": "region_budget_summary_v1",
            "budget_status": "not_declared",
            "learning_mode_required": False,
            "source_record_ids": [],
            "is_authority_state": False,
        }
    return {
        "schema": "region_budget_summary_v1",
        "budget_ledger_id": ledger.ledger_id,
        "tick": ledger.tick,
        "budget_status": ledger.budget_status,
        "learning_mode_required": ledger.learning_mode_required,
        "active_fine_region_ids": list(ledger.active_fine_region_ids),
        "warm_macro_region_ids": list(ledger.warm_macro_region_ids),
        "cold_macro_region_ids": list(ledger.cold_macro_region_ids),
        "invalidated_region_ids": list(ledger.invalidated_region_ids),
        "fine_step_count": ledger.fine_step_count,
        "refinement_request_count": ledger.refinement_request_count,
        "artifact_bytes_estimate": ledger.artifact_bytes_estimate,
        "budget_limits": dict(ledger.budget_limits),
        "source_record_ids": _unique([ledger.ledger_id, *ledger.source_record_ids]),
        "is_authority_state": False,
    }


def _boundary_exchange_ids_by_region(
    records: list[RegionBoundaryExchangeRecord] | None,
) -> dict[str, list[str]]:
    ids: dict[str, list[str]] = {}
    for record in list(records or []):
        ids.setdefault(record.source_region_id, []).append(record.record_id)
        ids.setdefault(record.target_region_id, []).append(record.record_id)
    return ids


def build_hierarchical_projection_frames(
    *,
    macro_field_states: list[MacroFieldState],
    stable_structure_certificates: list[StableStructureCertificate],
    fine_refinement_requests: list[FineRefinementRequest],
    fine_refinement_patches: list[FineRefinementPatch],
    macro_projection_records: list[MacroProjectionRecord],
    observer: dict[str, Any],
    macro_correction_records: list[MacroCorrectionRecord] | None = None,
    macro_boundary_exchange_records: list[MacroBoundaryExchangeRecord] | None = None,
    world_regions: list[WorldRegion] | None = None,
    region_lifecycle_records: list[RegionLifecycleRecord] | None = None,
    region_budget_ledgers: list[RegionBudgetLedger] | None = None,
    region_boundary_exchange_records: list[RegionBoundaryExchangeRecord] | None = None,
    region_authority_index: dict[str, Any] | None = None,
) -> list[ProjectionFrame]:
    if not macro_field_states:
        return []
    observer_id = observer.get("observer_id", "observer::pinhole-default")
    image_plane = dict(observer.get("image_plane", DEFAULT_IMAGE_PLANE))
    window = dict(observer.get("window", DEFAULT_WINDOW))
    certificates_by_id = {
        certificate.certificate_id: certificate
        for certificate in stable_structure_certificates
    }
    projections_by_macro_id = {
        projection.source_macro_state_id: projection
        for projection in macro_projection_records
    }
    requests_by_id = {
        request.request_id: request
        for request in fine_refinement_requests
    }
    macros_by_id = {macro.macro_state_id: macro for macro in macro_field_states}
    latest_tick = max(int(macro.tick_range[-1]) for macro in macro_field_states)
    frame_id = f"projection-frame::{observer_id}::hierarchical::{latest_tick}"
    samples: list[ProjectionSample] = []
    macro_overlays: list[dict[str, Any]] = []
    for macro_state in macro_field_states:
        projection_record = projections_by_macro_id.get(macro_state.macro_state_id)
        if projection_record is None:
            continue
        certificate = certificates_by_id.get(macro_state.certificate_id)
        macro_sample = _macro_sample(
            macro_state,
            certificate,
            projection_record,
            image_plane=image_plane,
            window=window,
        )
        if macro_sample is not None:
            samples.append(macro_sample)
        macro_overlays.append(
            _macro_overlay(
                macro_state,
                certificate,
                projection_record,
                image_plane=image_plane,
                window=window,
            )
        )
    patches_by_macro = {patch.macro_state_id: patch for patch in fine_refinement_patches}
    fine_overlays: list[dict[str, Any]] = []
    for patch in fine_refinement_patches:
        macro_state = next(
            (macro for macro in macro_field_states if macro.macro_state_id == patch.macro_state_id),
            None,
        )
        coordinate_frame = macro_state.coordinate_frame if macro_state else {}
        request = requests_by_id.get(patch.refinement_request_id)
        fine_sample = _fine_patch_sample(
            patch,
            request,
            coordinate_frame=coordinate_frame,
            image_plane=image_plane,
            window=window,
        )
        if fine_sample is not None:
            samples.append(fine_sample)
        fine_overlays.append(
            _fine_overlay(
                patch,
                request,
                coordinate_frame=coordinate_frame,
                image_plane=image_plane,
                window=window,
            )
        )
    correction_overlays = [
        _macro_correction_overlay(
            correction,
            macros_by_id.get(correction.post_correction_macro_state_id),
            image_plane=image_plane,
            window=window,
        )
        for correction in list(macro_correction_records or [])
    ]
    boundary_exchange_overlays = [
        _macro_boundary_exchange_overlay(
            exchange,
            macros_by_id,
            image_plane=image_plane,
            window=window,
        )
        for exchange in list(macro_boundary_exchange_records or [])
    ]
    latest_ledger = list(region_budget_ledgers or [])[-1] if region_budget_ledgers else None
    region_boundary_ids = _boundary_exchange_ids_by_region(region_boundary_exchange_records)
    region_overlays = [
        _region_overlay(
            region,
            image_plane=image_plane,
            window=window,
            budget_ledger_id=latest_ledger.ledger_id if latest_ledger else None,
            boundary_exchange_ids=region_boundary_ids.get(region.region_id, []),
        )
        for region in list(world_regions or [])
    ]
    region_lifecycle_overlays = _region_lifecycle_overlays(region_lifecycle_records)
    region_budget_summary = _region_budget_summary(region_budget_ledgers)
    active_fine_region_ids = sorted(
        region.region_id for region in list(world_regions or []) if region.authority_mode == "active_fine"
    )
    macro_region_ids = sorted(
        region.region_id for region in list(world_regions or []) if region.authority_mode in {"cold_macro", "warm_macro"}
    )
    invalidated_region_ids = sorted(
        region.region_id for region in list(world_regions or []) if region.authority_mode == "invalidated"
    )
    source_record_ids = _unique([
        *[macro.macro_state_id for macro in macro_field_states],
        *[certificate.certificate_id for certificate in stable_structure_certificates],
        *[projection.record_id for projection in macro_projection_records],
        *[request.request_id for request in fine_refinement_requests],
        *[patch.patch_id for patch in fine_refinement_patches],
        *[correction.correction_id for correction in list(macro_correction_records or [])],
        *[exchange.exchange_id for exchange in list(macro_boundary_exchange_records or [])],
        *[region.region_id for region in list(world_regions or [])],
        *[record.record_id for record in list(region_lifecycle_records or [])],
        *[ledger.ledger_id for ledger in list(region_budget_ledgers or [])],
        *[record.record_id for record in list(region_boundary_exchange_records or [])],
    ])
    return [
        ProjectionFrame(
            frame_id=frame_id,
            tick=latest_tick,
            observer_id=observer_id,
            image_plane={
                **image_plane,
                "window": {
                    "origin": list(window.get("origin", DEFAULT_WINDOW["origin"])),
                    "extent": list(window.get("extent", DEFAULT_WINDOW["extent"])),
                },
                "observer_model": image_plane.get("model", "pinhole"),
            },
            samples=samples,
            phenomena_overlays=[],
            source_state_ticks=[latest_tick],
            source_object_ids=[sample.object_id for sample in samples],
            source_record_ids=source_record_ids,
            is_authority_state=False,
            audit=_macro_frame_audit(),
            payload={
                "event_timeline": {
                    "tick": latest_tick,
                    "observer_id": observer_id,
                    "event_kinds": ["macro_projection"],
                    "interaction_record_ids": [],
                    "wave_step_record_ids": [],
                    "field_structure_event_ids": [],
                    "source_record_ids": source_record_ids,
                    "is_authority_state": False,
                },
                "macro_state_overlays": macro_overlays,
                "fine_refinement_overlays": fine_overlays,
                "macro_correction_overlays": correction_overlays,
                "macro_boundary_exchange_overlays": boundary_exchange_overlays,
                "region_overlays": region_overlays,
                "region_lifecycle_overlays": region_lifecycle_overlays,
                "active_fine_region_ids": active_fine_region_ids,
                "macro_region_ids": macro_region_ids,
                "invalidated_region_ids": invalidated_region_ids,
                "region_budget_summary": region_budget_summary,
                "region_authority_index_digest": (region_authority_index or {}).get("region_namespace_digest"),
                "macro_certificate_ids": [certificate.certificate_id for certificate in stable_structure_certificates],
                "fine_refinement_patch_ids": [patch.patch_id for patch in fine_refinement_patches],
                "fine_refinement_request_ids": [request.request_id for request in fine_refinement_requests],
                "macro_projection_record_ids": [projection.record_id for projection in macro_projection_records],
                "macro_correction_record_ids": [
                    correction.correction_id for correction in list(macro_correction_records or [])
                ],
                "macro_boundary_exchange_record_ids": [
                    exchange.exchange_id for exchange in list(macro_boundary_exchange_records or [])
                ],
                "region_boundary_exchange_record_ids": [
                    record.record_id for record in list(region_boundary_exchange_records or [])
                ],
                "patches_by_macro_state_id": {
                    macro_state_id: patch.patch_id
                    for macro_state_id, patch in patches_by_macro.items()
                },
            },
        )
    ]
