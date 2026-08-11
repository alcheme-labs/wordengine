from __future__ import annotations

from pathlib import Path
import math
from typing import Any, Mapping

from world_engine.contracts import (
    CompletionCheck,
    CompletionReport,
    FieldState,
    FinePatchOutcome,
    FinePatchStateSnapshot,
    FinePatchStepRecord,
    FineRefinementPatch,
    FineRefinementRequest,
    InteractionCommand,
    MacroBoundaryExchangeRecord,
    MacroCorrectionCertificateExtension,
    MacroCorrectionRecord,
    MacroEvolutionRecord,
    MacroFieldState,
    MacroProjectionRecord,
    NaturalPhenomenonSummary,
    ObserverProjection,
    ObserverRecord,
    PROJECTION_PIPELINE,
    ProjectionFrame,
    RegionActivationRequest,
    RegionBoundaryExchangeRecord,
    RegionBudgetLedger,
    RegionLifecycleRecord,
    WorldRegion,
    StableStructureCertificate,
    WorldState,
    MACRO_ERROR_BOUND_DEFAULTS,
    REGION_BUDGET_DEFAULTS,
    REGION_ERROR_BOUND_DEFAULTS,
    REGION_INVALIDATION_EXCHANGE_KINDS,
    summarize_compact_channels,
    validate_fine_patch_outcome_replay,
)
from world_engine.field_coordinates import grid_to_world
from world_engine.field_objects import compute_centroid, compute_support_region
from world_engine.field_metrics import summarize_field_structure
from world_engine.exploration_loop import (
    CONSEQUENCE_WINDOW_SCHEMA,
    EXPLORATION_EPISODE_SCHEMA,
    MAX_DEAD_FRAME_RATIO,
    MAX_INTERACTION_RESPONSE_LAG_TICKS,
    MIN_BACKED_PLAYABLE_CONSEQUENCE_RECORDS,
    MIN_CONSEQUENCE_WINDOWS,
    MIN_DISTINCT_TOOL_KINDS,
    MIN_PLAY_TICKS,
    MIN_REGION_REENTRY_COUNT,
    MIN_TOOL_COMMANDS,
    MIN_VISIBLE_CONSEQUENCE_FRAMES,
    OBSERVER_FRAME_COVERAGE_RATIO,
    REGION_REENTRY_SCHEMA,
    REQUIRED_REENTRY_METRICS,
    REQUIRED_WINDOW_METRICS,
)
from world_engine.macro_feedback import compute_boundary_flux, compute_macro_fine_error
from world_engine.playable_consequences import (
    compute_boundary_containment,
    compute_channel_transport,
    compute_cohesion_accumulation,
    compute_dampening_absorption,
    compute_local_perturbation_response,
    compute_source_maintenance,
)
from world_engine.play_goals import (
    evaluate_field_play_progress,
    validate_field_play_goal,
    validate_field_play_progress,
)
from world_engine.play_loop import (
    replay_field_play_loop_state,
    validate_field_play_feedback,
    validate_field_play_initial_state,
    validate_field_play_loop_state,
    validate_field_tool_profile,
    validate_field_tool_use_record,
)
from world_engine.exploration_route import (
    replay_field_exploration_state,
    validate_field_exploration_state,
    validate_field_route_edge,
    validate_field_route_node,
    validate_field_route_step_record,
)
from world_engine.spectral_camera import (
    canonical_spectral_camera_pixel_digest,
    sample_spectral_camera_frame,
    validate_spectral_camera_frame,
)
from world_engine.spectral_image_plane import (
    build_spectral_image_plane,
    validate_spectral_image_plane,
)
from world_engine.field_signature_authoring import (
    summarize_field_signature_evidence,
    validate_field_signature_instance,
)
from world_engine.projection_frames import SPECTRAL_CAMERA_DEBUG_LAYER_KEYS
from world_engine.five_phase import stable_digest
from world_engine.implicit_field_runtime import (
    ENERGY_RESIDUAL_TAU_ABS,
    ENERGY_RESIDUAL_TAU_REL,
    advance_implicit_field_state,
)
from world_engine.implicit_live_session import (
    ENERGY_SCOPE_RELAXATION_TICKS,
    FEEDBACK_ERROR_IMPROVEMENT_TOLERANCE,
)
from world_engine.wavefronts import (
    compute_disturbance_wavefront_records,
    validate_material_wavefront_response_record,
)


FORBIDDEN_AUTHORITY_ENTITIES = {
    "light_object",
    "particle_object",
    "persistent_light_object",
    "material_asset",
    "global_raindrop_authority_state",
}
REQUIRED_FAMILIES = {"bare", "intermediate", "dressed"}
REQUIRED_PHENOMENA = {"wind", "rain", "light", "discharge"}
ALLOWED_FIELD_KERNELS = {
    "linear_local_wave_damped_source",
    "local_multichannel_wave_reaction_v2",
    "conservative_reaction_flow_v3",
    "seeded_turing_instability",
}
MEMBERSHIP_RECORD_KINDS = {
    "seed_from_certified_package",
    "seed_field_signature",
    "world_tick",
}


def _completion_check(name: str, ok: bool, details: dict[str, Any]) -> CompletionCheck:
    return CompletionCheck(name=name, status="passed" if ok else "failed", details=details)


def _state_records(states: list[WorldState]) -> set[str]:
    return {
        record.record_id
        for state in states
        for record in state.events + state.radiative_records + state.interaction_records
    }


def _records_by_state_tick(states: list[WorldState]) -> dict[int, dict[str, Any]]:
    return {
        state.tick: {
            record.record_id: record
            for record in state.events + state.radiative_records + state.interaction_records
        }
        for state in states
    }


def _objects_by_state_tick(states: list[WorldState]) -> dict[int, dict[str, Any]]:
    return {state.tick: {obj.object_id: obj for obj in state.objects} for state in states}


def _check_minimum_tick_window(states: list[WorldState]) -> CompletionCheck:
    last_tick = states[-1].tick if states else None
    return _completion_check(
        "minimum_tick_window",
        bool(states) and last_tick >= 64,
        {"last_tick": last_tick, "required_minimum": 64},
    )


def _check_family_identity_coverage(states: list[WorldState]) -> CompletionCheck:
    families = {obj.family for state in states for obj in state.objects}
    missing = sorted(REQUIRED_FAMILIES - families)
    return _completion_check(
        "family_identity_coverage",
        not missing,
        {"families": sorted(families), "missing": missing},
    )


def _check_stable_composite_evidence(evidence: dict[str, Any]) -> CompletionCheck:
    state_law = evidence.get("step960", {}).get("state_law", {})
    threshold = evidence.get("threshold_robustness", {})
    ok = (
        evidence.get("status") == "established"
        and not evidence.get("validation_errors")
        and state_law.get("seed0") == {
            "active_pair_count": 211,
            "relation_stash_count": 722,
        }
        and state_law.get("seed1") == {
            "active_pair_count": 200,
            "relation_stash_count": 723,
        }
        and threshold.get("thresholds") == [0.91, 0.92, 0.93]
        and threshold.get("per_seed_count_sets") == {
            "seed0": [[209, 720]],
            "seed1": [[183, 710]],
        }
    )
    return _completion_check(
        "stable_composite_evidence",
        ok,
        {
            "status": evidence.get("status"),
            "evidence_id": evidence.get("evidence_id"),
            "validation_errors": evidence.get("validation_errors", []),
        },
    )


def _check_runtime_source_bridge(
    states: list[WorldState],
    evidence: dict[str, Any],
) -> CompletionCheck:
    evidence_id = evidence.get("evidence_id")
    missing: list[dict[str, Any]] = []
    required_bridge_fields = {
        "v3_queryable_object_id",
        "v2_package_digest",
        "phase0_stable_composite_evidence_id",
        "source_tick",
        "runtime_tick_offset",
    }
    for state in states:
        if not state.payload.get("source_to_runtime_tick_map"):
            missing.append({"tick": state.tick, "missing": "source_to_runtime_tick_map"})
        if state.payload.get("stable_composite_evidence_id") != evidence_id:
            missing.append({"tick": state.tick, "missing": "state_matching_evidence_id"})
        state_bridge = state.payload.get("runtime_source_bridge")
        if not state_bridge:
            missing.append({"tick": state.tick, "missing": "state_runtime_source_bridge"})
        else:
            expected_state_bridge = {
                "v2_package_digest": state.payload.get("source_package_digest"),
                "phase0_evidence_digest": evidence_id,
                "source_tick_base": state.payload.get("source_tick_base"),
                "runtime_tick_base": state.payload.get("runtime_tick_base"),
                "runtime_tick_offset": state.payload.get("runtime_tick_offset"),
                "source_to_runtime_tick_map": state.payload.get("source_to_runtime_tick_map"),
            }
            for field, expected in expected_state_bridge.items():
                if expected is None or state_bridge.get(field) != expected:
                    missing.append({"tick": state.tick, "missing": f"state_matching_{field}"})
            if not state_bridge.get("v3_query_object_ids"):
                missing.append({"tick": state.tick, "missing": "state_v3_query_object_ids"})
        for obj in state.objects:
            bridge = obj.payload.get("runtime_source_bridge")
            if not bridge:
                missing.append({"tick": state.tick, "object_id": obj.object_id, "missing": "bridge"})
                continue
            absent = sorted(required_bridge_fields - set(bridge))
            if absent:
                missing.append({"tick": state.tick, "object_id": obj.object_id, "missing": absent})
            if bridge.get("phase0_stable_composite_evidence_id") != evidence_id:
                missing.append(
                    {
                        "tick": state.tick,
                        "object_id": obj.object_id,
                        "missing": "matching_evidence_id",
                    }
                )
            expected_values = {
                "v3_queryable_object_id": obj.payload.get("source_query_object_id"),
                "v2_package_digest": obj.payload.get("source_package_digest"),
                "source_tick": obj.payload.get("source_tick"),
                "runtime_tick_offset": obj.payload.get("runtime_tick_offset"),
            }
            for field, expected in expected_values.items():
                if expected is None or bridge.get(field) != expected:
                    missing.append(
                        {
                            "tick": state.tick,
                            "object_id": obj.object_id,
                            "missing": f"matching_{field}",
                        }
                    )
        for link in state.causal_links:
            if link.payload.get("stable_composite_evidence_id") != evidence_id:
                missing.append(
                    {
                        "tick": state.tick,
                        "link_id": link.link_id,
                        "missing": "causal_matching_evidence_id",
                    }
                )
            if not link.payload.get("runtime_source_bridge_id"):
                missing.append(
                    {
                        "tick": state.tick,
                        "link_id": link.link_id,
                        "missing": "causal_runtime_source_bridge_id",
                    }
                )
    return _completion_check(
        "runtime_source_bridge",
        not missing,
        {"missing": missing[:20], "evidence_id": evidence_id},
    )


def _check_full_window_identity_chain(
    chains: list[dict[str, Any]],
    expected_ticks: int,
) -> CompletionCheck:
    full_window_count = sum(
        1 for chain in chains if chain.get("length") == expected_ticks and not chain.get("breaks")
    )
    return _completion_check(
        "full_window_identity_chain",
        full_window_count >= 1,
        {"expected_ticks": expected_ticks, "full_window_chain_count": full_window_count},
    )


def _check_public_observer_record(
    states: list[WorldState],
    records: list[ObserverRecord],
) -> CompletionCheck:
    first_tick = states[0].tick if states else None
    last_tick = states[-1].tick if states else None
    ok = any(
        record.valid_from <= first_tick
        and record.valid_to >= last_tick
        and bool(record.visible_object_ids)
        and record.payload.get("source_state_ticks") == [state.tick for state in states]
        for record in records
    )
    return _completion_check(
        "public_observer_record",
        ok,
        {"record_count": len(records), "required_interval": [first_tick, last_tick]},
    )


def _check_observer_projection_chain(
    projections: list[ObserverProjection],
    state_record_ids: set[str],
) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    for projection in projections:
        forbidden = sorted(FORBIDDEN_AUTHORITY_ENTITIES & set(projection.authority_entities))
        source_records_valid = set(projection.source_record_ids) <= state_record_ids
        if (
            projection.pipeline != PROJECTION_PIPELINE
            or projection.light_model != "derived_on_demand"
            or forbidden
            or not projection.source_record_ids
            or not source_records_valid
        ):
            failures.append(
                {
                    "projection_id": projection.projection_id,
                    "pipeline": projection.pipeline,
                    "light_model": projection.light_model,
                    "forbidden_authority_entities": forbidden,
                    "source_records_valid": source_records_valid,
                }
            )
    return _completion_check(
        "observer_projection_chain",
        bool(projections) and not failures,
        {"projection_count": len(projections), "failures": failures},
    )


def _phenomenon_map(
    phenomena: list[NaturalPhenomenonSummary] | dict[str, NaturalPhenomenonSummary],
) -> dict[str, NaturalPhenomenonSummary]:
    if isinstance(phenomena, dict):
        return phenomena
    return {item.phenomenon: item for item in phenomena}


def _check_derived_natural_phenomena(
    phenomena: list[NaturalPhenomenonSummary] | dict[str, NaturalPhenomenonSummary],
    state_record_ids: set[str],
) -> CompletionCheck:
    by_name = _phenomenon_map(phenomena)
    missing = sorted(REQUIRED_PHENOMENA - set(by_name))
    failures: list[dict[str, Any]] = []
    for name, summary in by_name.items():
        if not summary.source_record_ids or not set(summary.source_record_ids) <= state_record_ids:
            failures.append({"phenomenon": name, "reason": "invalid_source_record_ids"})
        if summary.payload.get("is_authority_entity") is not False:
            failures.append({"phenomenon": name, "reason": "authority_entity"})
    light = by_name.get("light")
    rain = by_name.get("rain")
    if light and light.payload.get("is_persistent_light_object") is not False:
        failures.append({"phenomenon": "light", "reason": "persistent_light_object"})
    if rain and rain.payload.get("no_global_raindrop_authority_state") is not True:
        failures.append({"phenomenon": "rain", "reason": "global_raindrop_authority_state"})
    return _completion_check(
        "derived_natural_phenomena",
        not missing and not failures,
        {"missing": missing, "failures": failures},
    )


def _check_interaction_causal_trace(
    states: list[WorldState],
    commands: list[InteractionCommand],
) -> CompletionCheck:
    missing: list[str] = []
    for command in commands:
        found = False
        for state in states:
            if state.tick <= command.tick:
                continue
            if any(command.command_id in record.payload.get("command_ids", []) for record in state.interaction_records):
                found = True
            if any(command.command_id in link.payload.get("command_ids", []) for link in state.causal_links):
                found = True
        if not found:
            missing.append(command.command_id)
    return _completion_check(
        "interaction_causal_trace",
        not missing,
        {"command_count": len(commands), "missing_command_ids": missing},
    )


def _check_artifact_replayability(world_run: dict[str, Any]) -> CompletionCheck:
    ok = world_run.get("artifact_replayability") is True
    return _completion_check(
        "artifact_replayability",
        ok,
        {"artifact_replayability": world_run.get("artifact_replayability")},
    )


def _check_projection_frame_replayability(
    states: list[WorldState],
    frames: list[ProjectionFrame],
    observer_records: list[ObserverRecord],
    projections: list[ObserverProjection],
    run_manifest: dict[str, Any] | None = None,
) -> CompletionCheck:
    state_ticks = [state.tick for state in states]
    manifest_observers = list((run_manifest or {}).get("observer_ids", []))
    record_observers = [record.observer_id for record in observer_records]
    projection_observers = [projection.observer_id for projection in projections]
    declared_observers = manifest_observers or record_observers or projection_observers
    failures: list[dict[str, Any]] = []
    if manifest_observers and sorted(manifest_observers) != sorted(record_observers):
        failures.append(
            {
                "reason": "manifest_observers_do_not_match_observer_records",
                "manifest_observer_ids": manifest_observers,
                "observer_record_ids": record_observers,
            }
        )
    if manifest_observers and sorted(manifest_observers) != sorted(projection_observers):
        failures.append(
            {
                "reason": "manifest_observers_do_not_match_observer_projections",
                "manifest_observer_ids": manifest_observers,
                "observer_projection_ids": projection_observers,
            }
        )
    if record_observers and projection_observers and sorted(record_observers) != sorted(projection_observers):
        failures.append(
            {
                "reason": "observer_records_do_not_match_observer_projections",
                "observer_record_ids": record_observers,
                "observer_projection_ids": projection_observers,
            }
        )
    frame_keys: dict[tuple[int, str], int] = {}
    unknown_observers = sorted(
        {frame.observer_id for frame in frames}
        - set(declared_observers)
    ) if declared_observers else []
    for observer_id in unknown_observers:
        failures.append({"reason": "frame_observer_not_declared", "observer_id": observer_id})
    if declared_observers:
        for frame in frames:
            frame_keys[(frame.tick, frame.observer_id)] = frame_keys.get((frame.tick, frame.observer_id), 0) + 1
        for tick in state_ticks:
            for observer_id in declared_observers:
                count = frame_keys.get((tick, observer_id), 0)
                if count != 1:
                    failures.append(
                        {
                            "reason": "observer_tick_frame_count_mismatch",
                            "tick": tick,
                            "observer_id": observer_id,
                            "frame_count": count,
                        }
                    )
    else:
        frame_ticks = [frame.tick for frame in frames]
        if len(frames) != len(states) or frame_ticks != state_ticks:
            failures.append({"reason": "legacy_frame_ticks_mismatch"})
    return _completion_check(
        "projection_frame_replayability",
        bool(states) and bool(frames) and not failures,
        {
            "world_state_count": len(states),
            "projection_frame_count": len(frames),
            "declared_observer_ids": declared_observers,
            "state_ticks": state_ticks[:5] + state_ticks[-5:] if len(state_ticks) > 10 else state_ticks,
            "frame_keys_sample": [
                {"tick": tick, "observer_id": observer_id, "frame_count": count}
                for (tick, observer_id), count in sorted(frame_keys.items())[:10]
            ],
            "failures": failures[:20],
        },
    )


def _resolve_record_field_path(record: Any, field_path: str) -> Any:
    if not field_path:
        return None
    current: Any = record
    for part in field_path.split("."):
        if part == "payload":
            current = getattr(record, "payload", None)
            continue
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current


def _inside_frame_window(obj: Any, frame: ProjectionFrame) -> bool:
    window = frame.image_plane.get("window", {})
    origin = window.get("origin", [0.0, 0.0])
    extent = window.get("extent", [0.0, 0.0])
    if not extent or extent[0] == 0 or extent[1] == 0:
        return False
    normalized_x = (obj.position[0] - origin[0]) / extent[0]
    normalized_y = (obj.position[1] - origin[1]) / extent[1]
    return 0 <= normalized_x <= 1 and 0 <= normalized_y <= 1


def _record_binding_valid(record: Any, binding: dict[str, Any], object_id: str) -> bool:
    if binding.get("object_id") != object_id:
        return False
    binding_kind = binding.get("binding_kind")
    if binding_kind == "payload_field":
        return _resolve_record_field_path(record, binding.get("field_path", "")) is not None
    if binding_kind == "source_object_membership":
        return (
            record.kind in MEMBERSHIP_RECORD_KINDS
            and object_id in record.payload.get("source_object_ids", [])
        )
    return False


def _check_projection_frame_provenance(
    states: list[WorldState],
    frames: list[ProjectionFrame],
) -> CompletionCheck:
    records_by_tick = _records_by_state_tick(states)
    objects_by_tick = _objects_by_state_tick(states)
    failures: list[dict[str, Any]] = []
    for frame in frames:
        state_records = records_by_tick.get(frame.tick, {})
        state_objects = objects_by_tick.get(frame.tick, {})
        if frame.is_authority_state:
            failures.append({"frame_id": frame.frame_id, "reason": "authority_state"})
        if frame.source_state_ticks != [frame.tick]:
            failures.append({"frame_id": frame.frame_id, "reason": "invalid_frame_source_state_ticks"})
        if not set(frame.source_record_ids) <= set(state_records):
            failures.append({"frame_id": frame.frame_id, "reason": "invalid_frame_source_record_ids"})
        timeline = frame.payload.get("event_timeline", {})
        valid_interaction_ids = {
            record_id for record_id, record in state_records.items()
            if getattr(record, "record_id", "").startswith("interaction::")
            or getattr(record, "record_id", "").startswith("field_source_interaction::")
            or getattr(record, "kind", "") == "field_source_injection"
        }
        valid_wave_step_ids = {
            record_id for record_id, record in state_records.items()
            if getattr(record, "kind", "") == "field_wave_step"
        }
        valid_structure_event_ids = {
            record_id for record_id, record in state_records.items()
            if getattr(record, "kind", "") == "field_structure_event"
        }
        if (
            timeline.get("tick") != frame.tick
            or timeline.get("observer_id") != frame.observer_id
            or timeline.get("is_authority_state") is not False
            or not set(timeline.get("source_record_ids", [])) <= set(state_records)
            or set(timeline.get("interaction_record_ids", [])) - valid_interaction_ids
            or set(timeline.get("wave_step_record_ids", [])) - valid_wave_step_ids
            or set(timeline.get("field_structure_event_ids", [])) - valid_structure_event_ids
        ):
            failures.append({"frame_id": frame.frame_id, "reason": "invalid_event_timeline"})
        for sample in frame.samples:
            obj = state_objects.get(sample.object_id)
            if obj is None:
                failures.append(
                    {
                        "frame_id": frame.frame_id,
                        "sample_id": sample.sample_id,
                        "reason": "missing_state_object",
                    }
                )
                continue
            if sample.object_id not in sample.source_object_ids:
                failures.append(
                    {
                        "frame_id": frame.frame_id,
                        "sample_id": sample.sample_id,
                        "reason": "sample_object_not_in_source_object_ids",
                    }
                )
            if sample.source_state_ticks != [frame.tick]:
                failures.append(
                    {
                        "frame_id": frame.frame_id,
                        "sample_id": sample.sample_id,
                        "reason": "invalid_source_state_ticks",
                    }
                )
            if sample.payload.get("renderable") is not False and not _inside_frame_window(obj, frame):
                failures.append(
                    {
                        "frame_id": frame.frame_id,
                        "sample_id": sample.sample_id,
                        "reason": "renderable_sample_outside_window",
                    }
                )
            bindings = sample.payload.get("record_bindings", {})
            valid_object_bound_record = False
            for record_id in sample.source_record_ids:
                record = state_records.get(record_id)
                if record is None:
                    failures.append(
                        {
                            "frame_id": frame.frame_id,
                            "sample_id": sample.sample_id,
                            "reason": "missing_source_record",
                            "record_id": record_id,
                        }
                    )
                    continue
                if sample.object_id not in record.payload.get("source_object_ids", []):
                    failures.append(
                        {
                            "frame_id": frame.frame_id,
                            "sample_id": sample.sample_id,
                            "reason": "record_not_bound_to_object",
                            "record_id": record_id,
                        }
                    )
                    continue
                binding = bindings.get(record_id)
                if not binding or not _record_binding_valid(record, binding, sample.object_id):
                    failures.append(
                        {
                            "frame_id": frame.frame_id,
                            "sample_id": sample.sample_id,
                            "reason": "invalid_record_binding",
                            "record_id": record_id,
                        }
                    )
                    continue
                valid_object_bound_record = True
            if not valid_object_bound_record:
                failures.append(
                    {
                        "frame_id": frame.frame_id,
                        "sample_id": sample.sample_id,
                        "reason": "no_valid_object_bound_record",
                    }
                )
    return _completion_check(
        "projection_frame_provenance",
        bool(frames) and not failures,
        {"frame_count": len(frames), "failures": failures[:20]},
    )


def _check_derived_visual_light(
    states: list[WorldState],
    frames: list[ProjectionFrame],
) -> CompletionCheck:
    records_by_tick = _records_by_state_tick(states)
    failures: list[dict[str, Any]] = []
    for frame in frames:
        state_records = records_by_tick.get(frame.tick, {})
        radiative_record_ids = {
            record_id
            for record_id, record in state_records.items()
            if record_id.startswith("radiative::")
            or record_id.startswith("field_radiative::")
            or getattr(record, "kind", "") == "field_emission"
        }
        light_overlays = [
            overlay for overlay in frame.phenomena_overlays if overlay.phenomenon == "light"
        ]
        if radiative_record_ids and not light_overlays:
            failures.append({"frame_id": frame.frame_id, "reason": "missing_light_overlay"})
        for overlay in light_overlays:
            if overlay.payload.get("derived_on_demand") is not True:
                failures.append({"overlay_id": overlay.overlay_id, "reason": "not_derived_on_demand"})
            if not overlay.source_record_ids or not set(overlay.source_record_ids) <= radiative_record_ids:
                failures.append({"overlay_id": overlay.overlay_id, "reason": "invalid_radiative_source"})
            if overlay.payload.get("is_persistent_light_object") is not False:
                failures.append({"overlay_id": overlay.overlay_id, "reason": "persistent_light_object"})
    return _completion_check(
        "derived_visual_light",
        bool(frames) and not failures,
        {"failures": failures[:20]},
    )


def _check_visual_rendering_boundary(frames: list[ProjectionFrame]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    for frame in frames:
        audit = frame.audit
        required_true = {
            "no_persistent_light_object",
            "no_material_asset_authority",
            "no_global_raindrop_authority_state",
            "no_mesh_material_light_pipeline",
        }
        if audit.get("projection_semantics") != "observer_projection_not_object_painting":
            failures.append({"frame_id": frame.frame_id, "reason": "invalid_projection_semantics"})
        for key in required_true:
            if audit.get(key) is not True:
                failures.append({"frame_id": frame.frame_id, "reason": f"missing_{key}"})
        if frame.is_authority_state:
            failures.append({"frame_id": frame.frame_id, "reason": "authority_state"})
    return _completion_check(
        "visual_rendering_boundary",
        bool(frames) and not failures,
        {"frame_count": len(frames), "failures": failures[:20]},
    )


def _derived_light_audit(
    projections: list[ObserverProjection],
    phenomena: list[NaturalPhenomenonSummary] | dict[str, NaturalPhenomenonSummary],
) -> dict[str, Any]:
    projection = projections[0] if projections else None
    by_name = _phenomenon_map(phenomena)
    rain = by_name.get("rain")
    if projection is None:
        return {}
    return {
        "light_model": projection.light_model,
        "source_state_ticks": projection.derived_light_summary.get("source_state_ticks", []),
        "source_record_ids": projection.derived_light_summary.get("source_record_ids", []),
        "authority_entities": list(projection.authority_entities),
        "no_persistent_light_object": (
            projection.derived_light_summary.get("is_persistent_light_object") is False
        ),
        "no_material_asset_authority": (
            projection.derived_light_summary.get("is_material_asset_authority") is False
        ),
        "no_global_raindrop_authority_state": (
            rain is not None
            and rain.payload.get("no_global_raindrop_authority_state") is True
        ),
    }


def _field_states_by_tick(field_states: list[FieldState]) -> dict[int, FieldState]:
    return {state.tick: state for state in field_states}


def _record_index(states: list[WorldState]) -> dict[str, Any]:
    return {
        record.record_id: record
        for state in states
        for record in state.events + state.radiative_records + state.interaction_records
    }


def _check_field_state_replayability(
    states: list[WorldState],
    field_states: list[FieldState],
) -> CompletionCheck:
    ok = (
        bool(field_states)
        and len(field_states) == len(states)
        and [state.tick for state in field_states] == [state.tick for state in states]
    )
    return _completion_check(
        "field_state_replayability",
        ok,
        {
            "world_state_count": len(states),
            "field_state_count": len(field_states),
            "world_ticks": [state.tick for state in states],
            "field_ticks": [state.tick for state in field_states],
        },
    )


def _check_field_evidence_bridge(
    states: list[WorldState],
    field_states: list[FieldState],
    field_rule: dict[str, Any],
) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    expected_bridge = field_rule.get("field_evidence_bridge_id")
    expected_evidence = field_rule.get("stable_composite_evidence_id")
    expected_digest = field_rule.get("stable_composite_evidence_digest")
    if expected_evidence and expected_digest != expected_evidence.rsplit(":sha256:", 1)[-1]:
        failures.append({"reason": "field_rule_digest_mismatch"})
    for field_state in field_states:
        payload = field_state.payload
        for key, expected in [
            ("field_evidence_bridge_id", expected_bridge),
            ("stable_composite_evidence_id", expected_evidence),
            ("stable_composite_evidence_digest", expected_digest),
        ]:
            if not expected or payload.get(key) != expected:
                failures.append({"tick": field_state.tick, "reason": f"field_state_{key}_mismatch"})
    for state in states:
        for key, expected in [
            ("field_evidence_bridge_id", expected_bridge),
            ("stable_composite_evidence_id", expected_evidence),
            ("stable_composite_evidence_digest", expected_digest),
        ]:
            if not expected or state.payload.get(key) != expected:
                failures.append({"tick": state.tick, "reason": f"world_state_{key}_mismatch"})
    return _completion_check(
        "field_evidence_bridge",
        not failures,
        {"failures": failures[:20], "field_evidence_bridge_id": expected_bridge},
    )


def _check_field_coordinate_frame(
    states: list[WorldState],
    field_states: list[FieldState],
    field_rule: dict[str, Any],
) -> CompletionCheck:
    expected = field_rule.get("coordinate_frame")
    failures: list[dict[str, Any]] = []
    if not expected:
        failures.append({"reason": "missing_field_rule_coordinate_frame"})
    for field_state in field_states:
        if field_state.payload.get("coordinate_frame") != expected:
            failures.append({"tick": field_state.tick, "reason": "field_state_coordinate_frame_mismatch"})
    for state in states:
        if state.payload.get("coordinate_frame") != expected:
            failures.append({"tick": state.tick, "reason": "world_state_coordinate_frame_mismatch"})
    return _completion_check(
        "field_coordinate_frame",
        not failures,
        {"failures": failures[:20]},
    )


def _check_field_state_lineage(field_states: list[FieldState]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    by_tick = _field_states_by_tick(field_states)
    for field_state in field_states:
        if field_state.tick == 0:
            if field_state.payload.get("previous_field_state_id") is not None:
                failures.append({"tick": 0, "reason": "seed_has_previous_field_state"})
            continue
        previous = by_tick.get(field_state.tick - 1)
        previous_id = previous.field_state_id if previous else None
        if field_state.payload.get("previous_field_state_id") != previous_id:
            failures.append({"tick": field_state.tick, "reason": "previous_field_state_id_mismatch"})
        if previous_id not in field_state.payload.get("source_field_state_ids", []):
            failures.append({"tick": field_state.tick, "reason": "missing_source_field_state_id"})
        wave_step_id = field_state.payload.get("field_wave_step_record_id")
        if not wave_step_id or wave_step_id not in field_state.source_record_ids:
            failures.append({"tick": field_state.tick, "reason": "missing_field_wave_step_record_id"})
    return _completion_check(
        "field_state_lineage",
        bool(field_states) and not failures,
        {"failures": failures[:20]},
    )


def _check_field_wave_step_records(
    states: list[WorldState],
    field_states: list[FieldState],
) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    world_by_tick = {state.tick: state for state in states}
    field_by_tick = _field_states_by_tick(field_states)
    for field_state in field_states:
        if field_state.tick == 0:
            continue
        world_state = world_by_tick.get(field_state.tick)
        previous = field_by_tick.get(field_state.tick - 1)
        record_id = field_state.payload.get("field_wave_step_record_id")
        record = next(
            (
                event for event in (world_state.events if world_state else [])
                if event.record_id == record_id and event.kind == "field_wave_step"
            ),
            None,
        )
        if record is None:
            failures.append({"tick": field_state.tick, "reason": "missing_field_wave_step"})
            continue
        required = {
            "previous_field_state_id",
            "current_field_state_id",
            "rule_id",
            "kernel",
            "kernel_config_digest",
            "coordinate_frame",
            "sources_by_channel",
            "energy_before",
            "energy_after",
        }
        missing = sorted(required - set(record.payload))
        if missing:
            failures.append({"tick": field_state.tick, "reason": "wave_step_missing_fields", "missing": missing})
        if previous and record.payload.get("previous_field_state_id") != previous.field_state_id:
            failures.append({"tick": field_state.tick, "reason": "wave_step_previous_mismatch"})
        if record.payload.get("current_field_state_id") != field_state.field_state_id:
            failures.append({"tick": field_state.tick, "reason": "wave_step_current_mismatch"})
        if record.payload.get("kernel") not in ALLOWED_FIELD_KERNELS:
            failures.append({"tick": field_state.tick, "reason": "invalid_kernel"})
    return _completion_check(
        "field_wave_step_records",
        bool(field_states) and not failures,
        {"failures": failures[:20]},
    )


def _check_objects_derived_from_field(states: list[WorldState]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    for state in states:
        if state.payload.get("objects_derived_from_field") is not True:
            failures.append({"tick": state.tick, "reason": "state_not_marked_field_derived"})
        field_state_id = state.payload.get("field_state_id")
        for obj in state.objects:
            if obj.payload.get("derived_from_field_state_id") != field_state_id:
                failures.append({"tick": state.tick, "object_id": obj.object_id, "reason": "object_field_state_mismatch"})
            if not obj.payload.get("field_extraction_record_id"):
                failures.append({"tick": state.tick, "object_id": obj.object_id, "reason": "missing_extraction_record_id"})
    return _completion_check(
        "objects_derived_from_field",
        bool(states) and not failures,
        {"failures": failures[:20]},
    )


def _close(left: list[float], right: list[float], tolerance: float = 1e-6) -> bool:
    return len(left) == len(right) and all(abs(a - b) <= tolerance for a, b in zip(left, right))


def _check_field_extraction_record_replayability(
    states: list[WorldState],
    field_states: list[FieldState],
) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    field_by_tick = _field_states_by_tick(field_states)
    for state in states:
        field_state = field_by_tick.get(state.tick)
        extraction = next((event for event in state.events if event.kind == "field_object_extraction"), None)
        if field_state is None or extraction is None:
            failures.append({"tick": state.tick, "reason": "missing_field_or_extraction_record"})
            continue
        component_by_id = {
            component["component_id"]: component
            for component in summarize_field_structure(
                field_state,
                include_support_cells=False,
            ).get("components", [])
        }
        for obj in state.objects:
            component = component_by_id.get(obj.payload.get("field_component_id"))
            if component is None:
                channel = obj.payload.get("field_channel")
                support = compute_support_region(field_state.channels[channel], threshold=0.2)
                centroid_grid = compute_centroid(field_state.channels[channel], support)
                centroid_world = grid_to_world(centroid_grid, field_state.payload["coordinate_frame"])
            else:
                centroid_grid = component["centroid_grid"]
                centroid_world = component["centroid_world"]
            extraction_payload = extraction.payload.get("extractions_by_object_id", {}).get(obj.object_id)
            if extraction_payload is None:
                failures.append({"tick": state.tick, "object_id": obj.object_id, "reason": "missing_object_extraction"})
                continue
            if not _close(obj.position, centroid_world):
                failures.append({"tick": state.tick, "object_id": obj.object_id, "reason": "object_position_not_recomputed_centroid"})
            if not _close(obj.payload.get("field_centroid_world", []), centroid_world):
                failures.append({"tick": state.tick, "object_id": obj.object_id, "reason": "payload_centroid_not_recomputed_centroid"})
            if not _close(extraction_payload.get("centroid_world", []), centroid_world):
                failures.append({"tick": state.tick, "object_id": obj.object_id, "reason": "extraction_centroid_not_recomputed_centroid"})
    return _completion_check(
        "field_extraction_record_replayability",
        bool(field_states) and not failures,
        {"failures": failures[:20]},
    )


def _check_identity_from_field_overlap(states: list[WorldState]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    for state in states:
        if state.tick == 0:
            continue
        identity_records = {
            event.record_id: event
            for event in state.events
            if event.kind == "field_identity_match"
        }
        for obj in state.objects:
            if obj.payload.get("source_object_id") == obj.object_id:
                record_id = obj.payload.get("field_identity_match_record_id")
                if record_id not in identity_records:
                    failures.append({"tick": state.tick, "object_id": obj.object_id, "reason": "missing_identity_match_record"})
                if obj.payload.get("overlap_score") is None:
                    failures.append({"tick": state.tick, "object_id": obj.object_id, "reason": "missing_overlap_score"})
    return _completion_check(
        "identity_from_field_overlap",
        not failures,
        {"failures": failures[:20]},
    )


def _check_interaction_as_field_source(states: list[WorldState]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    for state in states:
        for record in state.interaction_records:
            payload = record.payload
            required = {
                "interaction_applied_as",
                "source_field_state_id",
                "target_channel",
                "center_world",
                "center_grid",
                "radius_grid",
                "source_region_grid",
                "source_vector_world",
                "source_kernel",
                "source_amplitude",
                "command_ids",
                "source_state_ticks",
                "source_record_ids",
            }
            missing = sorted(required - set(payload))
            if missing:
                failures.append({"record_id": record.record_id, "reason": "missing_fields", "missing": missing})
            if payload.get("interaction_applied_as") != "field_source":
                failures.append({"record_id": record.record_id, "reason": "not_field_source"})
            if "direct_object_delta" in payload:
                failures.append({"record_id": record.record_id, "reason": "direct_object_delta"})
            if payload.get("radius_grid", 0) <= 0:
                failures.append({"record_id": record.record_id, "reason": "invalid_radius_grid"})
            wave_steps = [event for event in state.events if event.kind == "field_wave_step"]
            if not any(
                record.record_id in event.payload.get("source_record_ids", [])
                or any(
                    record.record_id in metadata.get("source_record_ids", [])
                    for metadata in event.payload.get("sources_by_channel", {}).values()
                )
                for event in wave_steps
            ):
                failures.append({"record_id": record.record_id, "reason": "missing_wave_step_reference"})
    return _completion_check(
        "interaction_as_field_source",
        not failures,
        {"failures": failures[:20]},
    )


def _check_radiative_records_from_field(states: list[WorldState]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    for state in states:
        for record in state.radiative_records:
            source_record_ids = record.payload.get("source_record_ids", [])
            if "field_tendency" not in record.payload or "field_energy" not in record.payload:
                failures.append({"record_id": record.record_id, "reason": "missing_field_readout"})
            if not any(str(record_id).startswith("field_object_extraction::") for record_id in source_record_ids):
                failures.append({"record_id": record.record_id, "reason": "missing_extraction_source"})
            if state.tick > 0 and not any(str(record_id).startswith("field_wave_step::") for record_id in source_record_ids):
                failures.append({"record_id": record.record_id, "reason": "missing_wave_step_source"})
    return _completion_check(
        "radiative_records_from_field",
        bool(states) and not failures,
        {"failures": failures[:20]},
    )


def _check_natural_phenomena_field_backed(
    phenomena: list[NaturalPhenomenonSummary] | dict[str, NaturalPhenomenonSummary],
    states: list[WorldState],
) -> CompletionCheck:
    by_name = _phenomenon_map(phenomena)
    valid_record_ids = _state_records(states)
    failures: list[dict[str, Any]] = []
    for name, summary in by_name.items():
        if summary.payload.get("authority_substrate") != "FieldState":
            failures.append({"phenomenon": name, "reason": "missing_field_authority"})
        if summary.payload.get("field_backed") is not True:
            failures.append({"phenomenon": name, "reason": "not_field_backed"})
        if not summary.source_record_ids or not set(summary.source_record_ids) <= valid_record_ids:
            failures.append({"phenomenon": name, "reason": "invalid_source_records"})
        if summary.source_record_ids == [f"event::tick::{summary.tick}"]:
            failures.append({"phenomenon": name, "reason": "broad_world_tick_only"})
    light = by_name.get("light")
    if light and light.payload.get("derived_on_demand") is not True:
        failures.append({"phenomenon": "light", "reason": "not_derived_on_demand"})
    return _completion_check(
        "natural_phenomena_field_backed",
        bool(by_name) and not failures,
        {"failures": failures[:20]},
    )


def _check_projection_frames_field_backed(frames: list[ProjectionFrame]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    for frame in frames:
        if frame.audit.get("authority_substrate") != "FieldState":
            failures.append({"frame_id": frame.frame_id, "reason": "missing_field_authority"})
        for sample in frame.samples:
            required = {
                "derived_from_field_state_id",
                "field_channel",
                "field_centroid",
                "field_extraction_record_id",
                "field_energy",
            }
            missing = sorted(required - set(sample.payload))
            if missing:
                failures.append(
                    {
                        "sample_id": sample.sample_id,
                        "reason": "missing_field_payload",
                        "missing": missing,
                    }
                )
            extraction_record_id = sample.payload.get("field_extraction_record_id")
            if extraction_record_id not in sample.source_record_ids:
                failures.append(
                    {
                        "sample_id": sample.sample_id,
                        "reason": "missing_extraction_source_record",
                    }
                )
    return _completion_check(
        "projection_frames_field_backed",
        bool(frames) and all(frame.samples for frame in frames) and not failures,
        {"failures": failures[:20]},
    )


def _check_no_family_specific_drift_kernel(field_rule: dict[str, Any]) -> CompletionCheck:
    ok = field_rule.get("kernel") in ALLOWED_FIELD_KERNELS
    return _completion_check(
        "no_family_specific_drift_kernel",
        ok,
        {"kernel": field_rule.get("kernel")},
    )


def _check_field_structure_metrics_replayable(
    states: list[WorldState],
    field_states: list[FieldState],
) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    previous_summary: dict[str, Any] | None = None
    state_by_tick = {state.tick: state for state in states}
    for field_state in field_states:
        recomputed = summarize_field_structure(
            field_state,
            previous_summary,
            include_support_cells=False,
        )
        previous_summary = recomputed
        stored = state_by_tick.get(field_state.tick).payload.get("field_structure_metrics") if field_state.tick in state_by_tick else None
        if stored is None:
            failures.append({"tick": field_state.tick, "reason": "missing_stored_metrics"})
            continue
        if stored.get("component_count") != recomputed.get("component_count"):
            failures.append({"tick": field_state.tick, "reason": "component_count_mismatch"})
        if abs(stored.get("total_component_energy", 0.0) - recomputed.get("total_component_energy", 0.0)) > 1e-6:
            failures.append({"tick": field_state.tick, "reason": "component_energy_mismatch"})
        stored_components = {
            component.get("component_id"): component
            for component in stored.get("components", [])
        }
        recomputed_components = {
            component.get("component_id"): component
            for component in recomputed.get("components", [])
        }
        if set(stored_components) != set(recomputed_components):
            failures.append({"tick": field_state.tick, "reason": "component_list_length_mismatch"})
            continue
        for component_id, stored_component in stored_components.items():
            recomputed_component = recomputed_components[component_id]
            if not _close(stored_component.get("centroid_world", []), recomputed_component.get("centroid_world", [])):
                failures.append({"tick": field_state.tick, "reason": "component_centroid_mismatch"})
    return _completion_check(
        "field_structure_metrics_replayable",
        bool(field_states) and not failures,
        {"failures": failures[:20]},
    )


def _check_field_structure_events_sourced(states: list[WorldState]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    for state in states:
        if state.tick == 0:
            continue
        record_ids = _records_by_state_tick([state]).get(state.tick, {})
        extraction_ids = {
            event.record_id for event in state.events if event.kind == "field_object_extraction"
        }
        wave_ids = {
            event.record_id for event in state.events if event.kind == "field_wave_step"
        }
        structure_events = [
            event for event in state.events if event.kind == "field_structure_event"
        ]
        if not structure_events:
            failures.append({"tick": state.tick, "reason": "missing_structure_event"})
            continue
        for event in structure_events:
            source_ids = set(event.payload.get("source_record_ids", []))
            if not source_ids <= set(record_ids):
                failures.append({"tick": state.tick, "reason": "invalid_source_record_ids"})
            if not source_ids & extraction_ids:
                failures.append({"tick": state.tick, "reason": "missing_extraction_source"})
            if not source_ids & wave_ids:
                failures.append({"tick": state.tick, "reason": "missing_wave_step_source"})
            if not event.payload.get("current_metrics"):
                failures.append({"tick": state.tick, "reason": "missing_current_metrics"})
    return _completion_check(
        "field_structure_events_sourced",
        bool(states) and not failures,
        {"failures": failures[:20]},
    )


def _field_structure_series(states: list[WorldState]) -> list[dict[str, Any]]:
    return [
        state.payload.get("field_structure_metrics", {})
        for state in states
        if state.payload.get("field_structure_metrics") is not None
    ]


def _check_field_law_long_run_stability(
    states: list[WorldState],
    field_states: list[FieldState],
    field_rule: dict[str, Any],
) -> CompletionCheck:
    metrics = _field_structure_series(states)
    energies = [field_state.energy for field_state in field_states]
    component_counts = [item.get("component_count", 0) for item in metrics]
    required_last_tick = 512
    energy_limit = float(field_rule.get("energy_limit", 1_000_000.0))
    nonzero_ratio = (
        sum(1 for count in component_counts if count > 0) / len(component_counts)
        if component_counts else 0.0
    )
    ok = (
        bool(states)
        and states[-1].tick >= required_last_tick
        and bool(energies)
        and all(isinstance(value, (int, float)) and value == value and value < energy_limit for value in energies)
        and nonzero_ratio >= 0.90
    )
    return _completion_check(
        "field_law_long_run_stability",
        ok,
        {
            "last_tick": states[-1].tick if states else None,
            "required_last_tick": required_last_tick,
            "energy_min": min(energies) if energies else None,
            "energy_max": max(energies) if energies else None,
            "energy_limit": energy_limit,
            "nonzero_component_ratio": nonzero_ratio,
        },
    )


def _check_field_law_structure_richness(
    states: list[WorldState],
    chains: list[dict[str, Any]],
) -> CompletionCheck:
    metrics = _field_structure_series(states)
    component_counts = [item.get("component_count", 0) for item in metrics]
    nonzero_ratio = (
        sum(1 for count in component_counts if count > 0) / len(component_counts)
        if component_counts else 0.0
    )
    expected_length = len(states)
    stable_chain_count = sum(
        1
        for chain in chains
        if chain.get("length", 0) >= expected_length * 0.8 and not chain.get("breaks")
    )
    event_kinds = {
        kind
        for state in states
        for event in state.events
        if event.kind == "field_structure_event"
        for kind in event.payload.get("event_kinds", [])
        if kind != "persist"
    }
    initial_count = component_counts[0] if component_counts else 0
    max_count = max(component_counts) if component_counts else 0
    ok = (
        nonzero_ratio >= 0.90
        and stable_chain_count >= 3
        and (max_count > initial_count or len(event_kinds) >= 2)
    )
    return _completion_check(
        "field_law_structure_richness",
        ok,
        {
            "nonzero_component_ratio": nonzero_ratio,
            "stable_chain_count": stable_chain_count,
            "required_stable_chain_count": 3,
            "initial_component_count": initial_count,
            "max_component_count": max_count,
            "non_persist_event_kinds": sorted(event_kinds),
        },
    )


def _check_field_law_no_scripted_objects(
    states: list[WorldState],
    field_rule: dict[str, Any],
) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    if field_rule.get("kernel") not in ALLOWED_FIELD_KERNELS:
        failures.append({"reason": "unsupported_or_scripted_kernel", "kernel": field_rule.get("kernel")})
    for state in states:
        for obj in state.objects:
            for forbidden in ["direct_delta", "direct_object_delta", "scripted_position", "family_drift"]:
                if forbidden in obj.payload:
                    failures.append({"tick": state.tick, "object_id": obj.object_id, "reason": forbidden})
        for record in state.interaction_records:
            if "direct_object_delta" in record.payload:
                failures.append({"tick": state.tick, "record_id": record.record_id, "reason": "direct_object_delta"})
    return _completion_check(
        "field_law_no_scripted_objects",
        not failures,
        {"failures": failures[:20]},
    )


def evaluate_world_completion(world_run: dict[str, Any]) -> CompletionReport:
    states: list[WorldState] = world_run.get("world_states", [])
    runtime_mode = world_run.get("runtime_mode", "legacy-drift")
    field_states: list[FieldState] = world_run.get("field_states", [])
    field_rule: dict[str, Any] = world_run.get("field_rule", {})
    evidence = world_run.get("stable_composite_evidence", {})
    chains = world_run.get("identity_chains", [])
    observer_records = world_run.get("observer_records", [])
    projections = world_run.get("observer_projections", [])
    phenomena = world_run.get("natural_phenomena", [])
    commands = world_run.get("interaction_commands", [])
    projection_frames = world_run.get("projection_frames", [])
    run_manifest = world_run.get("run_manifest", {})
    state_record_ids = _state_records(states)

    checks = [
        _check_minimum_tick_window(states),
        _check_family_identity_coverage(states),
        _check_stable_composite_evidence(evidence),
        _check_full_window_identity_chain(chains, expected_ticks=len(states)),
        _check_public_observer_record(states, observer_records),
        _check_observer_projection_chain(projections, state_record_ids),
        _check_derived_natural_phenomena(phenomena, state_record_ids),
        _check_interaction_causal_trace(states, commands),
        _check_artifact_replayability(world_run),
        _check_projection_frame_replayability(
            states,
            projection_frames,
            observer_records,
            projections,
            run_manifest,
        ),
        _check_projection_frame_provenance(states, projection_frames),
        _check_derived_visual_light(states, projection_frames),
        _check_visual_rendering_boundary(projection_frames),
    ]
    if runtime_mode != "field":
        checks.insert(3, _check_runtime_source_bridge(states, evidence))
    if runtime_mode == "field" or field_states:
        checks.extend(
            [
                _check_field_state_replayability(states, field_states),
                _check_field_evidence_bridge(states, field_states, field_rule),
                _check_field_coordinate_frame(states, field_states, field_rule),
                _check_field_state_lineage(field_states),
                _check_field_wave_step_records(states, field_states),
                _check_objects_derived_from_field(states),
                _check_field_extraction_record_replayability(states, field_states),
                _check_identity_from_field_overlap(states),
                _check_interaction_as_field_source(states),
                _check_radiative_records_from_field(states),
                _check_natural_phenomena_field_backed(phenomena, states),
                _check_projection_frames_field_backed(projection_frames),
                _check_no_family_specific_drift_kernel(field_rule),
                _check_field_structure_metrics_replayable(states, field_states),
                _check_field_structure_events_sourced(states),
                _check_field_law_long_run_stability(states, field_states, field_rule),
                _check_field_law_structure_richness(states, chains),
                _check_field_law_no_scripted_objects(states, field_rule),
            ]
        )
    maturity_check_names = {
        "field_law_long_run_stability",
        "field_law_structure_richness",
        "field_law_no_scripted_objects",
    }
    blocking_checks = [
        check for check in checks if check.name not in maturity_check_names
    ]
    overall_status = "passed" if all(check.status == "passed" for check in blocking_checks) else "failed"
    maturity_checks = {
        check.name: check.status
        for check in checks
        if check.name in maturity_check_names
    }
    summary = {
        "engineering_world_completion": overall_status,
        "physics_substrate_scope": "evidence-backed-reference-runtime",
        "visual_projection": {
            "projection_frame_count": len(projection_frames),
            "kernel": "anisotropic_gaussian_2d",
            "light_model": "derived_on_demand",
            "rendering_boundary": "observer_projection_not_object_painting",
        },
    }
    if runtime_mode == "field" or field_states:
        summary.update(
            {
                "runtime_mode": "field",
                "authority_substrate": "FieldState",
                "world_growth_rule": field_rule.get("kernel", "linear_local_wave_damped_source"),
                "field_evidence_bridge_id": field_rule.get("field_evidence_bridge_id"),
                "coordinate_frame": "affine_window_grid_v1",
                "field_law_maturity_status": "passed"
                if maturity_checks
                and all(status == "passed" for status in maturity_checks.values())
                else "failed",
                "field_law_maturity_checks": maturity_checks,
            }
        )
    return CompletionReport(
        overall_status=overall_status,
        checks=checks,
        summary=summary,
        audit={
            "derived_on_demand_light": _derived_light_audit(projections, phenomena),
        },
    )


def _macro_source_ids(item: Any) -> list[str]:
    return list(getattr(item, "source_record_ids", []))


def _has_derived_summary_source(items: list[Any]) -> bool:
    for item in items:
        for record_id in _macro_source_ids(item):
            if str(record_id).startswith("field_derived"):
                return True
    return False


def _macro_error_bounds_are_stage1_or_stricter(error_bounds: dict[str, Any]) -> bool:
    required = set(MACRO_ERROR_BOUND_DEFAULTS) | {"centroid_world_max_error"}
    if required - set(error_bounds):
        return False
    return (
        float(error_bounds["centroid_grid_max_error_cells"]) <= float(MACRO_ERROR_BOUND_DEFAULTS["centroid_grid_max_error_cells"])
        and float(error_bounds["support_iou_min"]) >= float(MACRO_ERROR_BOUND_DEFAULTS["support_iou_min"])
        and float(error_bounds["relative_energy_error_max"]) <= float(MACRO_ERROR_BOUND_DEFAULTS["relative_energy_error_max"])
        and float(error_bounds["boundary_band_relative_error_max"]) <= float(MACRO_ERROR_BOUND_DEFAULTS["boundary_band_relative_error_max"])
        and int(error_bounds["component_count_delta_max"]) <= int(MACRO_ERROR_BOUND_DEFAULTS["component_count_delta_max"])
        and error_bounds["mode_signature_must_match"] is True
    )


def _check_macro_certificate_provenance(
    macro_states: list[MacroFieldState],
    certificates: list[StableStructureCertificate],
) -> CompletionCheck:
    certificates_by_id = {certificate.certificate_id: certificate for certificate in certificates}
    failures: list[dict[str, Any]] = []
    for macro_state in macro_states:
        certificate = certificates_by_id.get(macro_state.certificate_id)
        if certificate is None:
            failures.append({"macro_state_id": macro_state.macro_state_id, "reason": "missing_certificate"})
            continue
        if not certificate.source_field_state_ids or not certificate.source_record_ids:
            failures.append({"certificate_id": certificate.certificate_id, "reason": "empty_source_lineage"})
        if macro_state.source_field_state_ids != certificate.source_field_state_ids:
            failures.append({"macro_state_id": macro_state.macro_state_id, "reason": "source_field_state_mismatch"})
    return _completion_check(
        "macro_certificate_provenance",
        bool(macro_states) and bool(certificates) and not failures,
        {"failures": failures[:20]},
    )


def _check_macro_authority_boundary(
    macro_states: list[MacroFieldState],
    certificates: list[StableStructureCertificate],
    requests: list[FineRefinementRequest],
    projections: list[MacroProjectionRecord],
) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    for macro_state in macro_states:
        if not macro_state.is_authority_state:
            failures.append({"macro_state_id": macro_state.macro_state_id, "reason": "macro_not_authority"})
    for certificate in certificates:
        if certificate.is_authority_state:
            failures.append({"certificate_id": certificate.certificate_id, "reason": "certificate_is_authority"})
    for request in requests:
        if request.is_authority_state:
            failures.append({"request_id": request.request_id, "reason": "request_is_authority"})
    for projection in projections:
        if projection.is_authority_state:
            failures.append({"record_id": projection.record_id, "reason": "projection_is_authority"})
    return _completion_check("macro_authority_boundary", not failures, {"failures": failures[:20]})


def _check_macro_evolution_provenance(
    macro_states: list[MacroFieldState],
    certificates: list[StableStructureCertificate],
    records: list[MacroEvolutionRecord],
    correction_records: list[MacroCorrectionRecord] | None = None,
) -> CompletionCheck:
    macro_ids = {macro_state.macro_state_id for macro_state in macro_states}
    certificate_ids = {certificate.certificate_id for certificate in certificates}
    corrected_macro_ids = {
        record.post_correction_macro_state_id for record in list(correction_records or [])
    }
    failures: list[dict[str, Any]] = []
    for macro_state in macro_states[1:]:
        upstream_macro_ids = (set(macro_state.source_record_ids) & macro_ids) - {macro_state.macro_state_id}
        if not upstream_macro_ids:
            continue
        if (
            macro_state.macro_state_id not in corrected_macro_ids
            and all(record.current_macro_state_id != macro_state.macro_state_id for record in records)
        ):
            failures.append({"macro_state_id": macro_state.macro_state_id, "reason": "missing_macro_lineage_record"})
    for record in records:
        if record.previous_macro_state_id not in macro_ids:
            failures.append({"record_id": record.record_id, "reason": "missing_previous_macro_state"})
        if record.current_macro_state_id not in macro_ids:
            failures.append({"record_id": record.record_id, "reason": "missing_current_macro_state"})
        if record.certificate_id not in certificate_ids:
            failures.append({"record_id": record.record_id, "reason": "missing_certificate"})
        if record.previous_macro_state_id not in record.source_record_ids:
            failures.append({"record_id": record.record_id, "reason": "missing_previous_macro_source"})
    return _completion_check("macro_evolution_provenance", not failures, {"failures": failures[:20]})


def _close_dict(left: Any, right: Any, *, tolerance: float = 1e-9) -> bool:
    if isinstance(left, dict) and isinstance(right, dict):
        if set(left) != set(right):
            return False
        return all(_close_dict(left[key], right[key], tolerance=tolerance) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return False
        return all(_close_dict(a, b, tolerance=tolerance) for a, b in zip(left, right))
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)) <= tolerance
    return left == right


def _check_fine_refinement_request_lineage(
    macro_states: list[MacroFieldState],
    requests: list[FineRefinementRequest],
) -> CompletionCheck:
    macros_by_id = {macro_state.macro_state_id: macro_state for macro_state in macro_states}
    failures: list[dict[str, Any]] = []
    for request in requests:
        macro_state = macros_by_id.get(request.source_macro_state_id)
        if macro_state is None:
            failures.append({"request_id": request.request_id, "reason": "missing_source_macro"})
            continue
        if request.coordinate_frame != macro_state.coordinate_frame:
            failures.append({"request_id": request.request_id, "reason": "coordinate_frame_mismatch"})
        if macro_state.macro_state_id not in request.source_record_ids:
            failures.append({"request_id": request.request_id, "reason": "missing_macro_source_record"})
    return _completion_check(
        "fine_refinement_request_lineage",
        bool(requests) and not failures,
        {"failures": failures[:20]},
    )


def _check_macro_to_fine_refinement_replayability(
    macro_states: list[MacroFieldState],
    requests: list[FineRefinementRequest],
    patches: list[FineRefinementPatch],
) -> CompletionCheck:
    macro_ids = {macro_state.macro_state_id for macro_state in macro_states}
    requests_by_id = {request.request_id: request for request in requests}
    failures: list[dict[str, Any]] = []
    for patch in patches:
        request = requests_by_id.get(patch.refinement_request_id)
        if request is None:
            failures.append({"patch_id": patch.patch_id, "reason": "missing_refinement_request"})
            continue
        if patch.macro_state_id not in macro_ids:
            failures.append({"patch_id": patch.patch_id, "reason": "missing_macro_state"})
        if request.source_macro_state_id != patch.macro_state_id:
            failures.append({"patch_id": patch.patch_id, "reason": "request_patch_macro_mismatch"})
        if request.request_id not in patch.source_record_ids or patch.macro_state_id not in patch.source_record_ids:
            failures.append({"patch_id": patch.patch_id, "reason": "missing_patch_source_lineage"})
    return _completion_check(
        "macro_to_fine_refinement_replayability",
        bool(patches) and not failures,
        {"failures": failures[:20]},
    )


def _check_macro_projection_lineage(
    macro_states: list[MacroFieldState],
    certificates: list[StableStructureCertificate],
    projections: list[MacroProjectionRecord],
) -> CompletionCheck:
    macro_ids = {macro_state.macro_state_id for macro_state in macro_states}
    certificate_ids = {certificate.certificate_id for certificate in certificates}
    failures: list[dict[str, Any]] = []
    for projection in projections:
        if projection.source_macro_state_id not in macro_ids:
            failures.append({"record_id": projection.record_id, "reason": "missing_source_macro"})
        if projection.macro_certificate_id not in certificate_ids:
            failures.append({"record_id": projection.record_id, "reason": "missing_macro_certificate"})
        if (
            projection.source_macro_state_id not in projection.source_record_ids
            or projection.macro_certificate_id not in projection.source_record_ids
        ):
            failures.append({"record_id": projection.record_id, "reason": "missing_projection_source_lineage"})
    return _completion_check(
        "macro_projection_lineage",
        bool(projections) and not failures,
        {"failures": failures[:20]},
    )


def _check_macro_validity_envelope_enforcement(
    macro_states: list[MacroFieldState],
    certificates: list[StableStructureCertificate],
) -> CompletionCheck:
    certificates_by_id = {certificate.certificate_id: certificate for certificate in certificates}
    failures: list[dict[str, Any]] = []
    for macro_state in macro_states:
        certificate = certificates_by_id.get(macro_state.certificate_id)
        if not certificate:
            continue
        envelope_tick_range = certificate.validity_envelope.get("tick_range", [])
        if len(envelope_tick_range) != 2:
            failures.append({"macro_state_id": macro_state.macro_state_id, "reason": "invalid_envelope_tick_range"})
        elif (
            macro_state.tick_range[0] < envelope_tick_range[0]
            or macro_state.tick_range[1] > envelope_tick_range[1]
        ):
            failures.append({"macro_state_id": macro_state.macro_state_id, "reason": "macro_outside_validity_envelope"})
        if not _macro_error_bounds_are_stage1_or_stricter(macro_state.error_bounds):
            failures.append({"macro_state_id": macro_state.macro_state_id, "reason": "loose_error_bounds"})
    return _completion_check(
        "macro_validity_envelope_enforcement",
        not failures,
        {"failures": failures[:20]},
    )


def _check_no_derived_summary_authority(
    items: list[Any],
) -> CompletionCheck:
    has_derived = _has_derived_summary_source(items)
    return _completion_check(
        "no_derived_summary_authority",
        not has_derived,
        {"derived_summary_source_present": has_derived},
    )


def _check_fine_patch_outcome_replayability(
    patches: list[FineRefinementPatch],
    requests: list[FineRefinementRequest],
    snapshots: list[FinePatchStateSnapshot],
    step_records: list[FinePatchStepRecord],
    outcomes: list[FinePatchOutcome],
    *,
    required: bool,
) -> CompletionCheck:
    if not required:
        return _completion_check(
            "fine_patch_outcome_replayability",
            True,
            {"required": False},
        )
    patches_by_id = {patch.patch_id: patch for patch in patches}
    requests_by_id = {request.request_id: request for request in requests}
    snapshots_by_id = {snapshot.snapshot_id: snapshot for snapshot in snapshots}
    failures: list[dict[str, Any]] = []
    if not outcomes:
        failures.append({"reason": "missing_fine_patch_outcomes"})
    for outcome in outcomes:
        patch = patches_by_id.get(outcome.patch_id)
        request = requests_by_id.get(outcome.fine_refinement_request_id)
        final_snapshot = snapshots_by_id.get(outcome.final_snapshot_id)
        if patch is None:
            failures.append({"outcome_id": outcome.outcome_id, "reason": "missing_patch"})
        if request is None:
            failures.append({"outcome_id": outcome.outcome_id, "reason": "missing_request"})
        if final_snapshot is None:
            failures.append({"outcome_id": outcome.outcome_id, "reason": "missing_final_snapshot"})
            continue
        try:
            validate_fine_patch_outcome_replay(outcome, snapshots, step_records)
        except ValueError as exc:
            failures.append({"outcome_id": outcome.outcome_id, "reason": str(exc)})
        expected_summary = summarize_compact_channels(final_snapshot.channels_compact)
        if "trigger_kind" in outcome.raw_channel_summary:
            expected_summary["trigger_kind"] = outcome.raw_channel_summary["trigger_kind"]
        if not _close_dict(outcome.raw_channel_summary, expected_summary):
            failures.append({"outcome_id": outcome.outcome_id, "reason": "raw_summary_not_recomputed_from_final_snapshot"})
        expected_sources = {outcome.patch_id, outcome.fine_refinement_request_id, outcome.final_snapshot_id}
        if expected_sources - set(outcome.source_record_ids):
            failures.append({"outcome_id": outcome.outcome_id, "reason": "missing_outcome_source_lineage"})
    for item in [*snapshots, *step_records, *outcomes]:
        if getattr(item, "is_authority_state", False):
            failures.append({"record_id": getattr(item, "snapshot_id", getattr(item, "record_id", getattr(item, "outcome_id", ""))), "reason": "fine_artifact_is_authority"})
    return _completion_check(
        "fine_patch_outcome_replayability",
        not failures,
        {"failures": failures[:20]},
    )


def _check_macro_correction_provenance(
    macro_states: list[MacroFieldState],
    certificates: list[StableStructureCertificate],
    requests: list[FineRefinementRequest],
    patches: list[FineRefinementPatch],
    snapshots: list[FinePatchStateSnapshot],
    outcomes: list[FinePatchOutcome],
    corrections: list[MacroCorrectionRecord],
    extensions: list[MacroCorrectionCertificateExtension],
    *,
    required: bool,
) -> CompletionCheck:
    if not required:
        return _completion_check("macro_correction_provenance", True, {"required": False})
    macros_by_id = {macro.macro_state_id: macro for macro in macro_states}
    certificates_by_id = {certificate.certificate_id: certificate for certificate in certificates}
    requests_by_id = {request.request_id: request for request in requests}
    patches_by_id = {patch.patch_id: patch for patch in patches}
    snapshots_by_id = {snapshot.snapshot_id: snapshot for snapshot in snapshots}
    outcomes_by_id = {outcome.outcome_id: outcome for outcome in outcomes}
    extensions_by_id = {extension.extension_id: extension for extension in extensions}
    failures: list[dict[str, Any]] = []
    if not corrections:
        failures.append({"reason": "missing_macro_correction_records"})
    if corrections and not extensions:
        failures.append({"reason": "missing_macro_correction_certificate_extensions"})
    for correction in corrections:
        pre_macro = macros_by_id.get(correction.pre_correction_macro_state_id)
        post_macro = macros_by_id.get(correction.post_correction_macro_state_id)
        outcome = outcomes_by_id.get(correction.fine_patch_outcome_id)
        request = requests_by_id.get(correction.fine_refinement_request_id)
        certificate = certificates_by_id.get(correction.certificate_id)
        extension = extensions_by_id.get(correction.correction_certificate_extension_id)
        patch = patches_by_id.get(correction.source_fine_patch_id)
        missing = [
            name
            for name, value in [
                ("pre_macro", pre_macro),
                ("post_macro", post_macro),
                ("outcome", outcome),
                ("request", request),
                ("certificate", certificate),
                ("extension", extension),
                ("patch", patch),
            ]
            if value is None
        ]
        if missing:
            failures.append({"correction_id": correction.correction_id, "reason": "missing_lineage", "missing": missing})
            continue
        initial_snapshot = snapshots_by_id.get(outcome.initial_snapshot_id)
        final_snapshot = snapshots_by_id.get(outcome.final_snapshot_id)
        if initial_snapshot is None or final_snapshot is None:
            failures.append({"correction_id": correction.correction_id, "reason": "missing_outcome_snapshots"})
            continue
        recomputed_metrics = compute_macro_fine_error(pre_macro, outcome, final_snapshot, pre_macro.error_bounds)
        if not _close_dict(correction.error_metrics, recomputed_metrics):
            failures.append({"correction_id": correction.correction_id, "reason": "error_metrics_not_recomputed"})
        if correction.error_metrics.get("within_stage1_bounds") is not True:
            failures.append({"correction_id": correction.correction_id, "reason": "outside_stage1_bounds"})
        recomputed_flux = compute_boundary_flux(pre_macro, outcome, initial_snapshot, final_snapshot)
        if not _close_dict(correction.boundary_flux, recomputed_flux):
            failures.append({"correction_id": correction.correction_id, "reason": "boundary_flux_not_recomputed"})
        required_sources = {
            pre_macro.macro_state_id,
            certificate.certificate_id,
            outcome.outcome_id,
            request.request_id,
            final_snapshot.snapshot_id,
            extension.extension_id,
        }
        if required_sources - set(correction.source_record_ids):
            failures.append({"correction_id": correction.correction_id, "reason": "missing_correction_source_lineage"})
        post_sources = {correction.correction_id, extension.extension_id, outcome.outcome_id}
        if post_sources - set(post_macro.source_record_ids):
            failures.append({"macro_state_id": post_macro.macro_state_id, "reason": "missing_post_correction_source_lineage"})
        if extension.parent_certificate_id != certificate.certificate_id:
            failures.append({"extension_id": extension.extension_id, "reason": "parent_certificate_mismatch"})
        if extension.macro_correction_record_id != correction.correction_id:
            failures.append({"extension_id": extension.extension_id, "reason": "correction_record_mismatch"})
        if extension.fine_patch_outcome_id != outcome.outcome_id:
            failures.append({"extension_id": extension.extension_id, "reason": "outcome_mismatch"})
        if extension.pre_correction_macro_state_id != pre_macro.macro_state_id:
            failures.append({"extension_id": extension.extension_id, "reason": "pre_macro_mismatch"})
        if extension.post_correction_macro_state_id != post_macro.macro_state_id:
            failures.append({"extension_id": extension.extension_id, "reason": "post_macro_mismatch"})
        if extension.inherited_validity_envelope != extension.post_correction_validity_envelope:
            failures.append({"extension_id": extension.extension_id, "reason": "stage1_extension_expanded_or_changed_envelope"})
        if {certificate.certificate_id, outcome.outcome_id, correction.correction_id} - set(extension.source_record_ids):
            failures.append({"extension_id": extension.extension_id, "reason": "missing_extension_source_lineage"})
    return _completion_check("macro_correction_provenance", not failures, {"failures": failures[:20]})


def _check_macro_correction_error_bounds(
    macro_states: list[MacroFieldState],
    snapshots: list[FinePatchStateSnapshot],
    outcomes: list[FinePatchOutcome],
    corrections: list[MacroCorrectionRecord],
    *,
    required: bool,
) -> CompletionCheck:
    if not required:
        return _completion_check("macro_correction_error_bounds", True, {"required": False})
    macros_by_id = {macro.macro_state_id: macro for macro in macro_states}
    snapshots_by_id = {snapshot.snapshot_id: snapshot for snapshot in snapshots}
    outcomes_by_id = {outcome.outcome_id: outcome for outcome in outcomes}
    failures: list[dict[str, Any]] = []
    if not corrections:
        failures.append({"reason": "missing_macro_correction_records"})
    for correction in corrections:
        macro = macros_by_id.get(correction.pre_correction_macro_state_id)
        outcome = outcomes_by_id.get(correction.fine_patch_outcome_id)
        final_snapshot = snapshots_by_id.get(outcome.final_snapshot_id) if outcome else None
        if macro is None or outcome is None or final_snapshot is None:
            failures.append({"correction_id": correction.correction_id, "reason": "missing_recompute_inputs"})
            continue
        recomputed = compute_macro_fine_error(macro, outcome, final_snapshot, macro.error_bounds)
        if not _close_dict(correction.error_metrics, recomputed):
            failures.append({"correction_id": correction.correction_id, "reason": "error_metrics_not_recomputed"})
        if recomputed.get("within_stage1_bounds") is not True:
            failures.append({"correction_id": correction.correction_id, "reason": "outside_stage1_bounds"})
    return _completion_check("macro_correction_error_bounds", not failures, {"failures": failures[:20]})


def _check_macro_correction_certificate_extension(
    certificates: list[StableStructureCertificate],
    corrections: list[MacroCorrectionRecord],
    extensions: list[MacroCorrectionCertificateExtension],
    *,
    required: bool,
) -> CompletionCheck:
    if not required:
        return _completion_check("macro_correction_certificate_extension", True, {"required": False})
    certificates_by_id = {certificate.certificate_id: certificate for certificate in certificates}
    extensions_by_id = {extension.extension_id: extension for extension in extensions}
    failures: list[dict[str, Any]] = []
    if not corrections:
        failures.append({"reason": "missing_macro_correction_records"})
    if corrections and not extensions:
        failures.append({"reason": "missing_macro_correction_certificate_extensions"})
    for correction in corrections:
        extension = extensions_by_id.get(correction.correction_certificate_extension_id)
        certificate = certificates_by_id.get(correction.certificate_id)
        if extension is None:
            failures.append({"correction_id": correction.correction_id, "reason": "missing_extension"})
            continue
        if certificate is None:
            failures.append({"extension_id": extension.extension_id, "reason": "missing_parent_certificate"})
            continue
        if extension.parent_certificate_id != certificate.certificate_id:
            failures.append({"extension_id": extension.extension_id, "reason": "parent_certificate_mismatch"})
        if extension.macro_correction_record_id != correction.correction_id:
            failures.append({"extension_id": extension.extension_id, "reason": "correction_record_mismatch"})
        if extension.inherited_validity_envelope != extension.post_correction_validity_envelope:
            failures.append({"extension_id": extension.extension_id, "reason": "stage1_extension_changed_envelope"})
        if {certificate.certificate_id, correction.correction_id, correction.fine_patch_outcome_id} - set(extension.source_record_ids):
            failures.append({"extension_id": extension.extension_id, "reason": "missing_extension_source_lineage"})
    return _completion_check("macro_correction_certificate_extension", not failures, {"failures": failures[:20]})


def _check_macro_boundary_exchange_conservation(
    macro_states: list[MacroFieldState],
    exchange_records: list[MacroBoundaryExchangeRecord],
) -> CompletionCheck:
    macro_ids = {macro.macro_state_id for macro in macro_states}
    failures: list[dict[str, Any]] = []
    for record in exchange_records:
        if record.is_authority_state:
            failures.append({"exchange_id": record.exchange_id, "reason": "exchange_is_authority"})
        if set(record.source_macro_state_ids) - macro_ids:
            failures.append({"exchange_id": record.exchange_id, "reason": "missing_source_macro_state"})
        if set(record.affected_macro_state_ids) - macro_ids:
            failures.append({"exchange_id": record.exchange_id, "reason": "missing_affected_macro_state"})
        total_flux = 0.0
        for value in record.energy_flux_by_pair.values():
            if isinstance(value, dict):
                total_flux += sum(float(v) for v in value.values() if isinstance(v, (int, float)))
            elif isinstance(value, (int, float)):
                total_flux += float(value)
        if abs(total_flux) > 0.05:
            failures.append({"exchange_id": record.exchange_id, "reason": "energy_flux_not_conserved", "net_flux": total_flux})
    return _completion_check("macro_boundary_exchange_conservation", not failures, {"failures": failures[:20]})


def _check_macro_feedback_authority_boundary(
    items: list[Any],
) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    for item in items:
        if getattr(item, "is_authority_state", False):
            record_id = (
                getattr(item, "snapshot_id", "")
                or getattr(item, "record_id", "")
                or getattr(item, "outcome_id", "")
                or getattr(item, "correction_id", "")
                or getattr(item, "extension_id", "")
                or getattr(item, "exchange_id", "")
            )
            failures.append({"record_id": record_id, "reason": "feedback_artifact_is_authority"})
    return _completion_check("macro_feedback_authority_boundary", not failures, {"failures": failures[:20]})


def _check_macro_feedback_compact_artifact_policy(manifest: dict[str, Any]) -> CompletionCheck:
    artifacts = manifest.get("artifacts", {})
    artifact_names = set(artifacts.values() if isinstance(artifacts, dict) else [])
    forbidden = {
        "full_fine_patch_states.jsonl",
        "full_fine_patch_states.jsonl.gz",
        "full_field_states.jsonl",
        "full_field_states.jsonl.gz",
    }
    present = sorted(forbidden & artifact_names)
    return _completion_check(
        "macro_feedback_compact_artifact_policy",
        not present,
        {"forbidden_artifacts_present": present},
    )


def _region_manifest(world_run: dict[str, Any]) -> dict[str, Any]:
    return world_run.get("manifest") or world_run.get("run_manifest", {})


def _region_ids_by_type(world_run: dict[str, Any]) -> dict[str, set[str]]:
    macro_ids = {macro.macro_state_id for macro in world_run.get("macro_field_states", [])}
    field_ids = {field.field_state_id for field in world_run.get("field_states", [])}
    patch_ids = {patch.patch_id for patch in world_run.get("fine_refinement_patches", [])}
    request_ids = {request.request_id for request in world_run.get("region_activation_requests", [])}
    lifecycle_ids = {record.record_id for record in world_run.get("region_lifecycle_records", [])}
    budget_ids = {ledger.ledger_id for ledger in world_run.get("region_budget_ledgers", [])}
    correction_ids = {record.correction_id for record in world_run.get("macro_correction_records", [])}
    exchange_ids = {record.record_id for record in world_run.get("region_boundary_exchange_records", [])}
    return {
        "macro": macro_ids,
        "field": field_ids,
        "patch": patch_ids,
        "request": request_ids,
        "lifecycle": lifecycle_ids,
        "budget": budget_ids,
        "correction": correction_ids,
        "exchange": exchange_ids,
    }


def _check_region_index_declared_coverage(
    manifest: dict[str, Any],
    regions: list[WorldRegion],
    authority_index: dict[str, Any],
) -> CompletionCheck:
    declared_count = int(manifest.get("world_region_count", 0) or 0)
    entries = authority_index.get("entries", {}) if isinstance(authority_index, dict) else {}
    region_ids = {region.region_id for region in regions}
    failures: list[dict[str, Any]] = []
    if declared_count and len(regions) != declared_count:
        failures.append({"reason": "declared_region_count_mismatch", "declared": declared_count, "actual": len(regions)})
    if declared_count and not regions:
        failures.append({"reason": "missing_world_regions"})
    if entries and set(entries) != region_ids:
        failures.append({"reason": "authority_index_region_set_mismatch", "index": sorted(entries), "regions": sorted(region_ids)})
    if regions and not entries:
        failures.append({"reason": "missing_region_authority_index_entries"})
    return _completion_check(
        "region_index_declared_coverage",
        not failures,
        {"declared_count": declared_count, "region_count": len(regions), "failures": failures[:20]},
    )


def _region_envelope_within_bounds(region: WorldRegion) -> bool:
    bounds = region.validity_envelope.error_bounds
    required = set(REGION_ERROR_BOUND_DEFAULTS)
    return (
        not (required - set(bounds))
        and float(bounds["centroid_world_distance_max"]) <= float(REGION_ERROR_BOUND_DEFAULTS["centroid_world_distance_max"])
        and float(bounds["centroid_grid_distance_max"]) <= float(REGION_ERROR_BOUND_DEFAULTS["centroid_grid_distance_max"])
        and float(bounds["support_iou_min"]) >= float(REGION_ERROR_BOUND_DEFAULTS["support_iou_min"])
        and float(bounds["relative_energy_error_max"]) <= float(REGION_ERROR_BOUND_DEFAULTS["relative_energy_error_max"])
        and float(bounds["boundary_band_relative_error_max"]) <= float(REGION_ERROR_BOUND_DEFAULTS["boundary_band_relative_error_max"])
        and int(bounds["component_count_delta_max"]) <= int(REGION_ERROR_BOUND_DEFAULTS["component_count_delta_max"])
        and int(bounds["mode_signature_hamming_max"]) <= int(REGION_ERROR_BOUND_DEFAULTS["mode_signature_hamming_max"])
    )


def _check_region_authority_mode_validity(
    regions: list[WorldRegion],
    world_run: dict[str, Any],
) -> CompletionCheck:
    ids = _region_ids_by_type(world_run)
    activation_region_ids = {request.region_id for request in world_run.get("region_activation_requests", [])}
    invalidated_region_ids = {
        region_id
        for record in world_run.get("region_boundary_exchange_records", [])
        for region_id in record.invalidation_region_ids
    }
    failures: list[dict[str, Any]] = []
    for region in regions:
        if region.is_authority_state:
            failures.append({"region_id": region.region_id, "reason": "region_claims_authority"})
        if region.authority_mode in {"cold_macro", "warm_macro", "refining"} and region.current_macro_state_id not in ids["macro"]:
            failures.append({"region_id": region.region_id, "reason": "missing_current_macro_state"})
        if region.authority_mode == "active_fine":
            if region.active_fine_patch_id not in ids["patch"] and region.current_field_state_id not in ids["field"]:
                failures.append({"region_id": region.region_id, "reason": "missing_active_fine_authority_pointer"})
        if region.authority_mode == "invalidated" and region.region_id not in invalidated_region_ids:
            if not any("invalidation" in source_id or "invalidated" in source_id for source_id in region.source_record_ids):
                failures.append({"region_id": region.region_id, "reason": "invalidated_without_invalidation_lineage"})
        if not _region_envelope_within_bounds(region):
            failures.append({"region_id": region.region_id, "reason": "loose_or_missing_region_error_bounds"})
        if region.current_authority_tick > region.validity_envelope.tick_end and region.region_id not in activation_region_ids and region.authority_mode != "invalidated":
            failures.append({"region_id": region.region_id, "reason": "outside_validity_envelope_without_activation_or_invalidation"})
    return _completion_check("region_authority_mode_validity", not failures, {"failures": failures[:20]})


def _check_region_activation_provenance(
    requests: list[RegionActivationRequest],
    world_run: dict[str, Any],
) -> CompletionCheck:
    ids = _region_ids_by_type(world_run)
    region_ids = {region.region_id for region in world_run.get("world_regions", [])}
    failures: list[dict[str, Any]] = []
    for request in requests:
        if request.region_id not in region_ids:
            failures.append({"request_id": request.request_id, "reason": "missing_region"})
        if request.source_macro_state_id and request.source_macro_state_id not in ids["macro"]:
            failures.append({"request_id": request.request_id, "reason": "missing_source_macro"})
        if request.source_field_state_id and request.source_field_state_id not in ids["field"]:
            failures.append({"request_id": request.request_id, "reason": "missing_source_field"})
        if request.source_macro_state_id and request.source_macro_state_id not in request.source_record_ids:
            failures.append({"request_id": request.request_id, "reason": "missing_source_macro_lineage"})
        if not request.trigger_source_ids:
            failures.append({"request_id": request.request_id, "reason": "missing_trigger_source_ids"})
    return _completion_check("region_activation_provenance", not failures, {"failures": failures[:20]})


def _latest_lifecycle_by_region(records: list[RegionLifecycleRecord]) -> dict[str, RegionLifecycleRecord]:
    latest: dict[str, RegionLifecycleRecord] = {}
    for record in records:
        previous = latest.get(record.region_id)
        if previous is None or record.tick >= previous.tick:
            latest[record.region_id] = record
    return latest


def _check_region_lifecycle_replayability(
    regions: list[WorldRegion],
    lifecycle_records: list[RegionLifecycleRecord],
    authority_index: dict[str, Any],
    world_run: dict[str, Any],
) -> CompletionCheck:
    ids = _region_ids_by_type(world_run)
    requests_by_id = {request.request_id: request for request in world_run.get("region_activation_requests", [])}
    latest_by_region = _latest_lifecycle_by_region(lifecycle_records)
    entries = authority_index.get("entries", {}) if isinstance(authority_index, dict) else {}
    failures: list[dict[str, Any]] = []
    for record in lifecycle_records:
        if record.activation_request_id and record.activation_request_id not in requests_by_id:
            failures.append({"record_id": record.record_id, "reason": "missing_activation_request"})
        if record.activation_request_id and record.activation_request_id not in record.source_record_ids:
            failures.append({"record_id": record.record_id, "reason": "missing_activation_source_lineage"})
        if record.macro_state_id and record.macro_state_id not in ids["macro"]:
            failures.append({"record_id": record.record_id, "reason": "missing_macro_state"})
        if record.field_state_id and record.field_state_id not in ids["field"]:
            failures.append({"record_id": record.record_id, "reason": "missing_field_state"})
        if record.fine_patch_id and record.fine_patch_id not in ids["patch"]:
            failures.append({"record_id": record.record_id, "reason": "missing_fine_patch"})
        if record.budget_ledger_id and record.budget_ledger_id not in ids["budget"]:
            failures.append({"record_id": record.record_id, "reason": "missing_budget_ledger"})
        declared_sources = [
            record.activation_request_id,
            record.macro_state_id,
            record.field_state_id,
            record.fine_patch_id,
            record.correction_record_id,
            record.budget_ledger_id,
        ]
        if not any(source_id in record.source_record_ids for source_id in declared_sources if source_id):
            failures.append({"record_id": record.record_id, "reason": "lifecycle_sources_do_not_bind_declared_artifact"})
    for region in regions:
        if region.current_lifecycle_record_id not in ids["lifecycle"]:
            failures.append({"region_id": region.region_id, "reason": "missing_current_lifecycle_record"})
        latest = latest_by_region.get(region.region_id)
        if latest and latest.record_id != region.current_lifecycle_record_id:
            failures.append({"region_id": region.region_id, "reason": "region_not_pointing_to_latest_lifecycle"})
        entry = entries.get(region.region_id)
        if entry is None:
            failures.append({"region_id": region.region_id, "reason": "missing_authority_index_entry"})
            continue
        expected = {
            "authority_mode": region.authority_mode,
            "current_macro_state_id": region.current_macro_state_id,
            "current_field_state_id": region.current_field_state_id,
            "active_fine_patch_id": region.active_fine_patch_id,
            "current_lifecycle_record_id": region.current_lifecycle_record_id,
            "current_authority_tick": region.current_authority_tick,
            "validity_envelope_id": region.validity_envelope.envelope_id,
        }
        for key, value in expected.items():
            if entry.get(key) != value:
                failures.append({"region_id": region.region_id, "reason": f"authority_index_{key}_mismatch"})
    return _completion_check("region_lifecycle_replayability", not failures, {"failures": failures[:20]})


def _check_region_reentry_continuity(
    requests: list[RegionActivationRequest],
    lifecycle_records: list[RegionLifecycleRecord],
) -> CompletionCheck:
    records_by_id = {record.record_id: record for record in lifecycle_records}
    failures: list[dict[str, Any]] = []
    for request in requests:
        if request.trigger_kind != "reentry_replay" and "reentry_replay" not in request.secondary_trigger_kinds:
            continue
        linked_prior = [
            source_id
            for source_id in request.trigger_source_ids + request.source_record_ids
            if source_id in records_by_id
        ]
        if not linked_prior:
            failures.append({"request_id": request.request_id, "reason": "reentry_without_prior_lifecycle_lineage"})
    return _completion_check("region_reentry_continuity", not failures, {"failures": failures[:20]})


def _check_region_budget_enforcement(ledgers: list[RegionBudgetLedger]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    for ledger in ledgers:
        limits = ledger.budget_limits
        missing = sorted(set(REGION_BUDGET_DEFAULTS) - set(limits))
        if missing:
            failures.append({"ledger_id": ledger.ledger_id, "reason": "missing_budget_limits", "missing": missing})
            continue
        hard_failed = (
            len(ledger.active_fine_region_ids) > int(limits["max_active_fine_regions"])
            or int(ledger.refinement_request_count) > int(limits["max_refinements_per_tick"])
            or int(ledger.fine_step_count) > int(limits["max_fine_steps_per_tick"])
        )
        artifact_overrun = int(ledger.artifact_bytes_estimate) > int(limits["per_case_compact_budget_bytes"])
        if hard_failed and ledger.budget_status != "failed":
            failures.append({"ledger_id": ledger.ledger_id, "reason": "hard_limit_overrun_not_failed"})
        if artifact_overrun and ledger.budget_status != "learning_mode_required":
            failures.append({"ledger_id": ledger.ledger_id, "reason": "artifact_overrun_not_learning_mode"})
        if ledger.budget_status == "passed" and (hard_failed or artifact_overrun or ledger.learning_mode_required):
            failures.append({"ledger_id": ledger.ledger_id, "reason": "passed_status_contradicts_budget_facts"})
        if not ledger.source_record_ids:
            failures.append({"ledger_id": ledger.ledger_id, "reason": "missing_budget_lineage"})
    return _completion_check("region_budget_enforcement", not failures, {"failures": failures[:20]})


def _region_overlay_boundary_ids(frames: list[ProjectionFrame]) -> set[str]:
    ids: set[str] = set()
    for frame in frames:
        for overlay in frame.payload.get("region_overlays", []):
            ids.update(str(item) for item in overlay.get("region_boundary_exchange_record_ids", []) if item)
    return ids


def _check_region_boundary_exchange_conservation(
    records: list[RegionBoundaryExchangeRecord],
    regions: list[WorldRegion],
    frames: list[ProjectionFrame],
) -> CompletionCheck:
    region_ids = {region.region_id for region in regions}
    record_ids = {record.record_id for record in records}
    overlay_exchange_ids = _region_overlay_boundary_ids(frames)
    failures: list[dict[str, Any]] = []
    for missing in sorted(overlay_exchange_ids - record_ids):
        failures.append({"record_id": missing, "reason": "overlay_references_missing_boundary_exchange_record"})
    for missing in sorted(record_ids - overlay_exchange_ids):
        failures.append({"record_id": missing, "reason": "boundary_exchange_missing_projection_overlay"})
    for record in records:
        if record.is_authority_state:
            failures.append({"record_id": record.record_id, "reason": "boundary_exchange_claims_authority"})
        if record.source_region_id not in region_ids or record.target_region_id not in region_ids:
            failures.append({"record_id": record.record_id, "reason": "missing_source_or_target_region"})
        if (
            float(record.energy_conservation_relative_error) > 0.05
            and record.exchange_kind not in REGION_INVALIDATION_EXCHANGE_KINDS
        ):
            failures.append({"record_id": record.record_id, "reason": "energy_not_conserved"})
        if record.exchange_kind in REGION_INVALIDATION_EXCHANGE_KINDS and not record.invalidation_region_ids:
            failures.append({"record_id": record.record_id, "reason": "invalidation_exchange_without_invalidation_ids"})
    return _completion_check("region_boundary_exchange_conservation", not failures, {"failures": failures[:20]})


def _check_region_compact_artifact_policy(manifest: dict[str, Any]) -> CompletionCheck:
    artifacts = manifest.get("artifacts", {})
    artifact_names = set(artifacts.values() if isinstance(artifacts, dict) else [])
    forbidden = {
        "full_fine_patch_states.jsonl",
        "full_fine_patch_states.jsonl.gz",
        "full_field_states.jsonl",
        "full_field_states.jsonl.gz",
    }
    present = sorted(forbidden & artifact_names)
    debug_allowed = bool(manifest.get("debug_full_fine_stream_allowed"))
    return _completion_check(
        "region_compact_artifact_policy",
        not present or debug_allowed,
        {"forbidden_artifacts_present": present, "debug_full_fine_stream_allowed": debug_allowed},
    )


def _check_region_viewer_non_authority(frames: list[ProjectionFrame]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    for frame in frames:
        for field_name in [
            "region_overlays",
            "region_lifecycle_overlays",
        ]:
            for overlay in frame.payload.get(field_name, []):
                if overlay.get("is_authority_state") is not False:
                    failures.append({"frame_id": frame.frame_id, "field": field_name, "reason": "overlay_claims_authority"})
                if not overlay.get("source_record_ids"):
                    failures.append({"frame_id": frame.frame_id, "field": field_name, "reason": "overlay_missing_source_records"})
        if frame.payload.get("region_authority_from_viewer_state"):
            failures.append({"frame_id": frame.frame_id, "reason": "viewer_local_region_authority"})
    return _completion_check("region_viewer_non_authority", not failures, {"failures": failures[:20]})


def evaluate_demand_driven_region_completion(world_run: dict[str, Any]) -> CompletionReport:
    manifest = _region_manifest(world_run)
    regions: list[WorldRegion] = world_run.get("world_regions", [])
    requests: list[RegionActivationRequest] = world_run.get("region_activation_requests", [])
    lifecycle_records: list[RegionLifecycleRecord] = world_run.get("region_lifecycle_records", [])
    ledgers: list[RegionBudgetLedger] = world_run.get("region_budget_ledgers", [])
    exchanges: list[RegionBoundaryExchangeRecord] = world_run.get("region_boundary_exchange_records", [])
    frames: list[ProjectionFrame] = world_run.get("projection_frames", [])
    authority_index = world_run.get("region_authority_index", {})

    checks = [
        _check_region_index_declared_coverage(manifest, regions, authority_index),
        _check_region_authority_mode_validity(regions, world_run),
        _check_region_activation_provenance(requests, world_run),
        _check_region_lifecycle_replayability(regions, lifecycle_records, authority_index, world_run),
        _check_region_reentry_continuity(requests, lifecycle_records),
        _check_region_budget_enforcement(ledgers),
        _check_region_boundary_exchange_conservation(exchanges, regions, frames),
        _check_region_compact_artifact_policy(manifest),
        _check_region_viewer_non_authority(frames),
    ]
    overall_status = "passed" if all(check.status == "passed" for check in checks) else "failed"
    return CompletionReport(
        overall_status=overall_status,
        checks=checks,
        summary={
            "demand_driven_region_completion": overall_status,
            "authority_boundary": "WorldRegion routes to FieldState/MacroFieldState but is not world-content authority",
            "world_region_count": len(regions),
            "region_activation_request_count": len(requests),
            "region_lifecycle_record_count": len(lifecycle_records),
            "region_budget_ledger_count": len(ledgers),
            "region_boundary_exchange_record_count": len(exchanges),
        },
        audit={
            "region_ids": [region.region_id for region in regions],
            "activation_request_ids": [request.request_id for request in requests],
            "lifecycle_record_ids": [record.record_id for record in lifecycle_records],
        },
    )


def evaluate_hierarchical_authority_completion(world_run: dict[str, Any]) -> CompletionReport:
    manifest = world_run.get("manifest") or world_run.get("run_manifest", {})
    case_type = manifest.get("hierarchical_case_type")
    macro_states: list[MacroFieldState] = world_run.get("macro_field_states", [])
    certificates: list[StableStructureCertificate] = world_run.get("stable_structure_certificates", [])
    requests: list[FineRefinementRequest] = world_run.get("fine_refinement_requests", [])
    patches: list[FineRefinementPatch] = world_run.get("fine_refinement_patches", [])
    fine_snapshots: list[FinePatchStateSnapshot] = world_run.get("fine_patch_state_snapshots", [])
    fine_step_records: list[FinePatchStepRecord] = world_run.get("fine_patch_step_records", [])
    fine_outcomes: list[FinePatchOutcome] = world_run.get("fine_patch_outcomes", [])
    correction_records: list[MacroCorrectionRecord] = world_run.get("macro_correction_records", [])
    correction_extensions: list[MacroCorrectionCertificateExtension] = world_run.get(
        "macro_correction_certificate_extensions",
        [],
    )
    boundary_exchange_records: list[MacroBoundaryExchangeRecord] = world_run.get(
        "macro_boundary_exchange_records",
        [],
    )
    evolution_records: list[MacroEvolutionRecord] = world_run.get("macro_evolution_records", [])
    projection_records: list[MacroProjectionRecord] = world_run.get("macro_projection_records", [])
    refinement_optional_case_types = {
        "passive_macro_promotion",
        "passive_macro_feedback",
        "multi_component_boundary_exchange",
    }
    require_refinement = case_type not in refinement_optional_case_types or bool(requests) or bool(patches)
    require_feedback = (
        bool(manifest.get("macro_feedback_required"))
        or bool(fine_snapshots)
        or bool(fine_step_records)
        or bool(fine_outcomes)
        or bool(correction_records)
        or bool(correction_extensions)
        or bool(boundary_exchange_records)
    )
    correction_expected = (
        bool(correction_records)
        or int(manifest.get("macro_correction_record_count", 0) or 0) > 0
        or any(
            any(str(record_id).startswith("macro-correction::") for record_id in macro.source_record_ids)
            for macro in macro_states
        )
    )
    lineage_items: list[Any] = [
        *macro_states,
        *certificates,
        *requests,
        *patches,
        *fine_snapshots,
        *fine_step_records,
        *fine_outcomes,
        *correction_records,
        *correction_extensions,
        *boundary_exchange_records,
        *evolution_records,
        *projection_records,
    ]
    checks = [
        _check_macro_certificate_provenance(macro_states, certificates),
        _check_macro_authority_boundary(macro_states, certificates, requests, projection_records),
        _check_macro_evolution_provenance(
            macro_states,
            certificates,
            evolution_records,
            correction_records,
        ),
        (
            _check_macro_to_fine_refinement_replayability(macro_states, requests, patches)
            if require_refinement
            else _completion_check(
                "macro_to_fine_refinement_replayability",
                True,
                {"required": False, "case_type": case_type},
            )
        ),
        _check_macro_projection_lineage(macro_states, certificates, projection_records),
        (
            _check_fine_refinement_request_lineage(macro_states, requests)
            if require_refinement
            else _completion_check(
                "fine_refinement_request_lineage",
                True,
                {"required": False, "case_type": case_type},
            )
        ),
        _check_macro_validity_envelope_enforcement(macro_states, certificates),
        _check_fine_patch_outcome_replayability(
            patches,
            requests,
            fine_snapshots,
            fine_step_records,
            fine_outcomes,
            required=bool(fine_snapshots or fine_step_records or fine_outcomes)
            or (bool(manifest.get("macro_feedback_required")) and bool(requests or patches)),
        ),
        _check_macro_correction_provenance(
            macro_states,
            certificates,
            requests,
            patches,
            fine_snapshots,
            fine_outcomes,
            correction_records,
            correction_extensions,
            required=correction_expected,
        ),
        _check_macro_correction_error_bounds(
            macro_states,
            fine_snapshots,
            fine_outcomes,
            correction_records,
            required=correction_expected,
        ),
        _check_macro_correction_certificate_extension(
            certificates,
            correction_records,
            correction_extensions,
            required=correction_expected,
        ),
        _check_macro_boundary_exchange_conservation(macro_states, boundary_exchange_records),
        _check_macro_feedback_authority_boundary(
            [
                *fine_snapshots,
                *fine_step_records,
                *fine_outcomes,
                *correction_records,
                *correction_extensions,
                *boundary_exchange_records,
            ]
        ),
        _check_macro_feedback_compact_artifact_policy(manifest),
        _check_no_derived_summary_authority(lineage_items),
    ]
    overall_status = "passed" if all(check.status == "passed" for check in checks) else "failed"
    return CompletionReport(
        overall_status=overall_status,
        checks=checks,
        summary={
            "hierarchical_field_authority_completion": overall_status,
            "authority_substrate": "FieldState+MacroFieldState",
            "macro_field_state_count": len(macro_states),
            "fine_refinement_patch_count": len(patches),
            "fine_patch_outcome_count": len(fine_outcomes),
            "macro_correction_record_count": len(correction_records),
        },
        audit={
            "macro_state_ids": [macro_state.macro_state_id for macro_state in macro_states],
            "certificate_ids": [certificate.certificate_id for certificate in certificates],
        },
    )


def _interactive_commands_by_id(commands: list[InteractionCommand]) -> dict[str, InteractionCommand]:
    return {command.command_id: command for command in commands}


def _interactive_frames_by_id(frames: list[ProjectionFrame]) -> dict[str, ProjectionFrame]:
    return {frame.frame_id: frame for frame in frames}


def _interactive_summaries_by_tick(summaries: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {int(summary["tick"]): summary for summary in summaries if "tick" in summary}


def _interactive_affordances_by_id(affordances: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(affordance.get("affordance_id")): affordance
        for affordance in affordances
        if affordance.get("affordance_id")
    }


def _check_interactive_artifact_replayability(loaded_session: dict[str, Any]) -> CompletionCheck:
    manifest = loaded_session.get("manifest", {})
    frames = loaded_session.get("projection_frames", [])
    commands = loaded_session.get("interaction_commands", [])
    audit = loaded_session.get("interaction_audit", [])
    summaries = loaded_session.get("field_summaries", [])
    affordances = loaded_session.get("field_affordances", [])
    failures: list[dict[str, Any]] = []
    if loaded_session.get("artifact_replayability") is not True:
        failures.append({"reason": "read_back_artifact_replayability_false"})
    if manifest.get("artifact_schema") != "interactive_field_session_artifacts_v1":
        failures.append({"reason": "invalid_artifact_schema"})
    if manifest.get("runtime_mode") != "interactive-field":
        failures.append({"reason": "invalid_runtime_mode"})
    expected_counts = {
        "projection_frame_count": len(frames),
        "interaction_command_count": len(commands),
        "field_summary_count": len(summaries),
    }
    if manifest.get("affordance_schema") == "field_affordance_artifacts_v1":
        expected_counts["field_affordance_count"] = len(affordances)
    for key, actual in expected_counts.items():
        if manifest.get(key) != actual:
            failures.append(
                {
                    "reason": "manifest_count_mismatch",
                    "field": key,
                    "manifest_value": manifest.get(key),
                    "actual": actual,
                }
            )
    if not frames:
        failures.append({"reason": "missing_projection_frames"})
    if not commands:
        failures.append({"reason": "missing_interaction_commands"})
    if not audit:
        failures.append({"reason": "missing_interaction_audit"})
    if not summaries:
        failures.append({"reason": "missing_field_summaries"})
    return _completion_check(
        "interactive_artifact_replayability",
        not failures,
        {"failures": failures[:20]},
    )


def _check_interactive_command_provenance(loaded_session: dict[str, Any]) -> CompletionCheck:
    manifest = loaded_session.get("manifest", {})
    observer_ids = set(manifest.get("observer_ids", []))
    commands: list[InteractionCommand] = loaded_session.get("interaction_commands", [])
    audits = loaded_session.get("interaction_audit", [])
    audits_by_command = {
        audit.get("command", {}).get("command_id"): audit
        for audit in audits
        if audit.get("command")
    }
    failures: list[dict[str, Any]] = []
    required_low_level_payload = {
        "interaction_request_schema",
        "request_id",
        "observer_id",
        "source_frame_tick",
        "source_image_xy",
        "tool",
        "channel",
        "center_world",
        "center_grid",
        "radius_grid",
        "source_region_grid",
        "source_vector_world",
        "amplitude",
        "tool_semantics",
        "parent_request_id",
        "interaction_trace_id",
        "generated_command_ids",
    }
    required_affordance_payload = {
        "schema",
        "request_id",
        "parent_request_id",
        "affordance_id",
        "origin_type",
        "observer_id",
        "source_frame_tick",
        "source_image_xy",
        "affordance_kind",
        "channel",
        "center_world",
        "center_grid",
        "radius_grid",
        "region_grid",
        "duration_ticks",
        "effect",
    }
    for command in commands:
        if command.kind == "field_affordance_patch":
            missing = sorted(required_affordance_payload - set(command.payload))
            if command.payload.get("schema") != "field_affordance_command_v1":
                failures.append({"command_id": command.command_id, "reason": "invalid_affordance_command_schema"})
            if command.payload.get("origin_type") != "user_authored":
                failures.append({"command_id": command.command_id, "reason": "invalid_affordance_origin"})
        else:
            missing = sorted(required_low_level_payload - set(command.payload))
            if command.kind != "local_field_source":
                failures.append({"command_id": command.command_id, "reason": "invalid_command_kind"})
            if command.payload.get("interaction_request_schema") != "interactive_field_input_v1":
                failures.append({"command_id": command.command_id, "reason": "invalid_request_schema"})
            if command.command_id not in command.payload.get("generated_command_ids", []):
                failures.append({"command_id": command.command_id, "reason": "command_missing_from_generated_command_ids"})
        if missing:
            failures.append({"command_id": command.command_id, "reason": "missing_payload_fields", "missing": missing})
        if observer_ids and command.payload.get("observer_id") not in observer_ids:
            failures.append({"command_id": command.command_id, "reason": "observer_not_declared"})
        audit = audits_by_command.get(command.command_id)
        if not audit:
            failures.append({"command_id": command.command_id, "reason": "missing_audit"})
            continue
        if audit.get("status") != "applied":
            failures.append({"command_id": command.command_id, "reason": "audit_not_applied"})
        if audit.get("command", {}).get("payload", {}).get("request_id") != command.payload.get("request_id"):
            failures.append({"command_id": command.command_id, "reason": "audit_command_payload_mismatch"})
        if audit.get("request", {}).get("request_id") != command.payload.get("request_id"):
            failures.append({"command_id": command.command_id, "reason": "audit_request_mismatch"})
    return _completion_check(
        "interactive_command_provenance",
        bool(commands) and not failures,
        {"command_count": len(commands), "failures": failures[:20]},
    )


def _frame_payload_or_debug_layer(frame: ProjectionFrame, key: str, default: Any) -> Any:
    if key in frame.payload:
        return frame.payload.get(key, default)
    debug_layers = frame.payload.get("debug_layers", {})
    if isinstance(debug_layers, dict):
        layers = debug_layers.get("layers", {})
        if isinstance(layers, dict) and key in layers:
            return layers.get(key, default)
    return default


def _frame_interaction_overlays(frame: ProjectionFrame) -> list[dict[str, Any]]:
    return list(_frame_payload_or_debug_layer(frame, "interaction_overlays", []))


def _frame_interaction_traces(frame: ProjectionFrame) -> list[dict[str, Any]]:
    return list(_frame_payload_or_debug_layer(frame, "interaction_traces", []))


def _frame_affordance_overlays(frame: ProjectionFrame) -> list[dict[str, Any]]:
    return list(_frame_payload_or_debug_layer(frame, "affordance_overlays", []))


def _check_interaction_overlay_provenance(loaded_session: dict[str, Any]) -> CompletionCheck:
    commands = _interactive_commands_by_id(
        [
            command
            for command in loaded_session.get("interaction_commands", [])
            if command.kind != "field_affordance_patch"
        ]
    )
    audits = {
        audit.get("command", {}).get("command_id"): audit
        for audit in loaded_session.get("interaction_audit", [])
        if audit.get("command")
    }
    frames = loaded_session.get("projection_frames", [])
    overlays_by_command: dict[str, list[dict[str, Any]]] = {}
    failures: list[dict[str, Any]] = []
    for frame in frames:
        for overlay in _frame_interaction_overlays(frame):
            if overlay.get("schema") != "interaction_overlay_v1":
                failures.append({"frame_id": frame.frame_id, "reason": "invalid_overlay_schema"})
            if overlay.get("is_authority_state") is not False:
                failures.append({"frame_id": frame.frame_id, "reason": "overlay_authority_state"})
            command_id = overlay.get("command_id")
            overlays_by_command.setdefault(command_id, []).append(overlay)
            command = commands.get(command_id)
            audit = audits.get(command_id)
            if command is None:
                failures.append({"frame_id": frame.frame_id, "command_id": command_id, "reason": "overlay_command_missing"})
                continue
            if audit is None:
                failures.append({"frame_id": frame.frame_id, "command_id": command_id, "reason": "overlay_audit_missing"})
                continue
            if overlay.get("interaction_record_id") != audit.get("interaction_record_id"):
                failures.append({"frame_id": frame.frame_id, "command_id": command_id, "reason": "overlay_interaction_record_mismatch"})
            if overlay.get("wave_step_record_id") != audit.get("field_wave_step_record_id"):
                failures.append({"frame_id": frame.frame_id, "command_id": command_id, "reason": "overlay_wave_step_mismatch"})
            if overlay.get("interaction_trace_id") != command.payload.get("interaction_trace_id"):
                failures.append({"frame_id": frame.frame_id, "command_id": command_id, "reason": "overlay_trace_mismatch"})
            generated = set(overlay.get("generated_command_ids", []))
            expected_generated = set(command.payload.get("generated_command_ids", []))
            if generated != expected_generated or command_id not in generated:
                failures.append({"frame_id": frame.frame_id, "command_id": command_id, "reason": "overlay_generated_command_ids_mismatch"})
            source_ids = set(overlay.get("source_record_ids", []))
            required_sources = {
                audit.get("interaction_record_id"),
                audit.get("field_wave_step_record_id"),
            }
            if None in required_sources or not required_sources <= source_ids:
                failures.append({"frame_id": frame.frame_id, "command_id": command_id, "reason": "overlay_missing_source_records"})
    for command_id in commands:
        if command_id not in overlays_by_command:
            failures.append({"command_id": command_id, "reason": "missing_overlay_for_command"})
    return _completion_check(
        "interaction_overlay_provenance",
        not failures,
        {"overlay_count": sum(len(items) for items in overlays_by_command.values()), "failures": failures[:20]},
    )


def _check_interaction_trace_replayability(loaded_session: dict[str, Any]) -> CompletionCheck:
    commands = _interactive_commands_by_id(
        [
            command
            for command in loaded_session.get("interaction_commands", [])
            if command.kind != "field_affordance_patch"
        ]
    )
    audits = {
        audit.get("command", {}).get("command_id"): audit
        for audit in loaded_session.get("interaction_audit", [])
        if audit.get("command")
    }
    frames = _interactive_frames_by_id(loaded_session.get("projection_frames", []))
    traces_by_id: dict[str, list[dict[str, Any]]] = {}
    active_trace_ids: set[str] = set()
    failures: list[dict[str, Any]] = []
    for frame in frames.values():
        for trace_id in frame.payload.get("active_interaction_trace_ids", []):
            active_trace_ids.add(trace_id)
        for trace in _frame_interaction_traces(frame):
            traces_by_id.setdefault(trace.get("interaction_trace_id"), []).append(trace)
    for trace_id in active_trace_ids:
        if trace_id not in traces_by_id:
            failures.append({"trace_id": trace_id, "reason": "active_trace_missing_serialized_trace"})
    command_ids_by_trace: dict[str, set[str]] = {}
    for command in commands.values():
        command_ids_by_trace.setdefault(command.payload.get("interaction_trace_id"), set()).add(command.command_id)
    for trace_id, command_ids in command_ids_by_trace.items():
        traces = traces_by_id.get(trace_id, [])
        if not traces:
            failures.append({"trace_id": trace_id, "reason": "missing_trace_for_commands"})
            continue
        trace_generated_ids = set()
        trace_result_frame_ids = set()
        for trace in traces:
            if trace.get("schema") != "interaction_trace_v1":
                failures.append({"trace_id": trace_id, "reason": "invalid_trace_schema"})
            if trace.get("is_authority_state") is not False:
                failures.append({"trace_id": trace_id, "reason": "trace_authority_state"})
            trace_generated_ids.update(trace.get("generated_command_ids", []))
            trace_result_frame_ids.update(trace.get("resulting_projection_frame_ids", []))
        expected_generated_ids = set()
        for command_id in command_ids:
            expected_generated_ids.update(commands[command_id].payload.get("generated_command_ids", []))
        if trace_generated_ids != expected_generated_ids:
            failures.append({"trace_id": trace_id, "reason": "trace_generated_command_ids_mismatch"})
        for command_id in expected_generated_ids:
            audit = audits.get(command_id)
            if command_id not in commands:
                failures.append({"trace_id": trace_id, "command_id": command_id, "reason": "trace_command_missing"})
                continue
            if audit is None or audit.get("status") != "applied":
                failures.append({"trace_id": trace_id, "command_id": command_id, "reason": "trace_audit_not_applied"})
                continue
            if not set(audit.get("resulting_projection_frame_ids", [])) <= set(frames):
                failures.append({"trace_id": trace_id, "command_id": command_id, "reason": "audit_resulting_frame_missing"})
            for frame_id in audit.get("resulting_projection_frame_ids", []):
                if frame_id not in trace_result_frame_ids:
                    failures.append({"trace_id": trace_id, "command_id": command_id, "reason": "trace_missing_audit_result_frame"})
    return _completion_check(
        "interaction_trace_replayability",
        not failures,
        {"trace_count": len(traces_by_id), "active_trace_count": len(active_trace_ids), "failures": failures[:20]},
    )


def _check_interaction_to_field_wave_step(loaded_session: dict[str, Any]) -> CompletionCheck:
    commands = _interactive_commands_by_id(loaded_session.get("interaction_commands", []))
    audits = loaded_session.get("interaction_audit", [])
    failures: list[dict[str, Any]] = []
    for audit in audits:
        command_id = audit.get("command", {}).get("command_id")
        if command_id not in commands:
            failures.append({"audit_id": audit.get("audit_id"), "reason": "audit_command_missing_from_stream"})
            continue
        wave_step_id = audit.get("field_wave_step_record_id")
        interaction_record_id = audit.get("interaction_record_id")
        source_record_ids = set(audit.get("source_record_ids", []))
        if not wave_step_id or not str(wave_step_id).startswith("field_wave_step::"):
            failures.append({"command_id": command_id, "reason": "missing_field_wave_step_record_id"})
        valid_interaction_prefixes = ("field_source_interaction::", "field_affordance_interaction::")
        if not interaction_record_id or not str(interaction_record_id).startswith(valid_interaction_prefixes):
            failures.append({"command_id": command_id, "reason": "missing_interaction_record_id"})
        if wave_step_id not in source_record_ids or interaction_record_id not in source_record_ids:
            failures.append({"command_id": command_id, "reason": "audit_source_records_do_not_bind_interaction_and_wave_step"})
    return _completion_check(
        "interaction_to_field_wave_step",
        bool(audits) and not failures,
        {"audit_count": len(audits), "failures": failures[:20]},
    )


def _check_affordance_command_provenance(loaded_session: dict[str, Any]) -> CompletionCheck:
    commands = [
        command
        for command in loaded_session.get("interaction_commands", [])
        if command.kind == "field_affordance_patch"
    ]
    affordances = _interactive_affordances_by_id(loaded_session.get("field_affordances", []))
    audits = {
        audit.get("command", {}).get("command_id"): audit
        for audit in loaded_session.get("interaction_audit", [])
        if audit.get("command")
    }
    failures: list[dict[str, Any]] = []
    for command in commands:
        affordance_id = command.payload.get("affordance_id")
        affordance = affordances.get(str(affordance_id))
        if affordance is None:
            failures.append({"command_id": command.command_id, "reason": "missing_field_affordance_record"})
            continue
        if affordance.get("origin_type") != "user_authored":
            failures.append({"command_id": command.command_id, "reason": "affordance_origin_not_user_authored"})
        if affordance.get("defined_by_command_id") != command.command_id:
            failures.append({"command_id": command.command_id, "reason": "affordance_defined_by_command_mismatch"})
        if not str(affordance.get("definition_record_id", "")).startswith("field_affordance_definition::"):
            failures.append({"command_id": command.command_id, "reason": "missing_definition_record_id"})
        audit = audits.get(command.command_id)
        if audit is None or audit.get("status") != "applied":
            failures.append({"command_id": command.command_id, "reason": "missing_or_unapplied_affordance_audit"})
            continue
        if audit.get("affordance_id") != affordance_id:
            failures.append({"command_id": command.command_id, "reason": "audit_affordance_id_mismatch"})
        if not str(audit.get("interaction_record_id", "")).startswith("field_affordance_interaction::"):
            failures.append({"command_id": command.command_id, "reason": "audit_missing_affordance_interaction_record"})
    return _completion_check(
        "affordance_command_provenance",
        not failures,
        {"affordance_command_count": len(commands), "failures": failures[:20]},
    )


def _check_affordance_wave_step_binding(loaded_session: dict[str, Any]) -> CompletionCheck:
    commands = [
        command
        for command in loaded_session.get("interaction_commands", [])
        if command.kind == "field_affordance_patch"
    ]
    failures: list[dict[str, Any]] = []
    overlays_by_affordance: dict[str, list[dict[str, Any]]] = {}
    overlays_by_frame_affordance: dict[tuple[int, str, str], list[dict[str, Any]]] = {}
    frames_by_tick_observer: dict[tuple[int, str], ProjectionFrame] = {}
    for frame in loaded_session.get("projection_frames", []):
        frames_by_tick_observer[(frame.tick, frame.observer_id)] = frame
        for overlay in _frame_affordance_overlays(frame):
            affordance_id = str(overlay.get("affordance_id"))
            overlays_by_affordance.setdefault(affordance_id, []).append(overlay)
            overlays_by_frame_affordance.setdefault(
                (frame.tick, frame.observer_id, affordance_id),
                [],
            ).append(overlay)
            source_record_ids = list(overlay.get("source_record_ids", []))
            if not any(str(record_id).startswith("field_affordance_application::") for record_id in source_record_ids):
                failures.append({"frame_id": frame.frame_id, "affordance_id": affordance_id, "reason": "overlay_missing_application_record"})
            if not any(str(record_id).startswith("field_wave_step::") for record_id in source_record_ids):
                failures.append({"frame_id": frame.frame_id, "affordance_id": affordance_id, "reason": "overlay_missing_wave_step_record"})
    for command in commands:
        affordance_id = str(command.payload.get("affordance_id"))
        if affordance_id not in overlays_by_affordance:
            failures.append({"command_id": command.command_id, "reason": "missing_affordance_overlay"})
    manifest = loaded_session.get("manifest", {})
    observer_ids = list(manifest.get("observer_ids") or sorted({
        frame.observer_id for frame in loaded_session.get("projection_frames", [])
    }))
    for affordance in loaded_session.get("field_affordances", []):
        affordance_id = str(affordance.get("affordance_id"))
        if not affordance_id:
            continue
        valid_from_tick = int(affordance.get("valid_from_tick", affordance.get("source_frame_tick", 0)))
        valid_to_tick = int(affordance.get("valid_to_tick", valid_from_tick))
        for tick in range(valid_from_tick + 1, valid_to_tick + 1):
            for observer_id in observer_ids:
                frame = frames_by_tick_observer.get((tick, observer_id))
                if frame is None:
                    continue
                overlays = overlays_by_frame_affordance.get((tick, observer_id, affordance_id), [])
                if not overlays:
                    failures.append(
                        {
                            "frame_id": frame.frame_id,
                            "affordance_id": affordance_id,
                            "reason": "missing_affordance_overlay_for_application_frame",
                        }
                    )
                    continue
                expected_application_record_id = f"field_affordance_application::{tick}::{affordance_id}"
                if not any(
                    expected_application_record_id in overlay.get("source_record_ids", [])
                    for overlay in overlays
                ):
                    failures.append(
                        {
                            "frame_id": frame.frame_id,
                            "affordance_id": affordance_id,
                            "reason": "overlay_missing_expected_application_record",
                            "expected_record_id": expected_application_record_id,
                        }
                    )
    return _completion_check(
        "affordance_wave_step_binding",
        not failures,
        {"affordance_overlay_count": sum(len(items) for items in overlays_by_affordance.values()), "failures": failures[:20]},
    )


def _check_affordance_projection_replayability(loaded_session: dict[str, Any]) -> CompletionCheck:
    affordances = _interactive_affordances_by_id(loaded_session.get("field_affordances", []))
    failures: list[dict[str, Any]] = []
    for frame in loaded_session.get("projection_frames", []):
        for overlay in _frame_affordance_overlays(frame):
            affordance_id = str(overlay.get("affordance_id"))
            source_record_ids = list(overlay.get("source_record_ids", []))
            if overlay.get("schema") != "field_affordance_overlay_v1":
                failures.append({"frame_id": frame.frame_id, "reason": "invalid_affordance_overlay_schema"})
            if overlay.get("is_authority_state") is not False:
                failures.append({"frame_id": frame.frame_id, "affordance_id": affordance_id, "reason": "affordance_overlay_authority_state"})
            if overlay.get("origin_type") != "user_authored":
                failures.append({"frame_id": frame.frame_id, "affordance_id": affordance_id, "reason": "affordance_overlay_origin_mismatch"})
            if affordance_id not in affordances:
                failures.append({"frame_id": frame.frame_id, "affordance_id": affordance_id, "reason": "affordance_overlay_definition_missing"})
            if overlay.get("visible") is True and not overlay.get("image_region"):
                failures.append({"frame_id": frame.frame_id, "affordance_id": affordance_id, "reason": "visible_overlay_missing_image_region"})
            required_prefixes = [
                "field_affordance_definition::",
                "field_affordance_application::",
                "field_wave_step::",
            ]
            for prefix in required_prefixes:
                if not any(str(record_id).startswith(prefix) for record_id in source_record_ids):
                    failures.append({"frame_id": frame.frame_id, "affordance_id": affordance_id, "reason": f"missing_{prefix.rstrip(':')}"})
    return _completion_check(
        "affordance_projection_replayability",
        not failures,
        {"failures": failures[:20]},
    )


def _check_no_derived_affordance_authority(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    for affordance in loaded_session.get("field_affordances", []):
        if affordance.get("origin_type") != "user_authored":
            failures.append({"affordance_id": affordance.get("affordance_id"), "reason": "non_user_affordance_in_authority_artifact"})
    for frame in loaded_session.get("projection_frames", []):
        for summary in _frame_payload_or_debug_layer(frame, "field_derived_affordance_summaries", []):
            if summary.get("origin_type") != "field_derived":
                failures.append({"frame_id": frame.frame_id, "reason": "invalid_derived_affordance_origin"})
            if summary.get("is_authority_state") is not False:
                failures.append({"frame_id": frame.frame_id, "reason": "derived_affordance_authority_state"})
            if summary.get("used_as_wave_source") is True or summary.get("must_not_feed_back") is False:
                failures.append({"frame_id": frame.frame_id, "reason": "derived_affordance_used_as_wave_source"})
        for overlay in _frame_affordance_overlays(frame):
            if overlay.get("origin_type") == "field_derived":
                failures.append({"frame_id": frame.frame_id, "affordance_id": overlay.get("affordance_id"), "reason": "derived_affordance_used_as_active_overlay"})
    return _completion_check(
        "no_derived_affordance_authority",
        not failures,
        {"failures": failures[:20]},
    )


def _summary_changed(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if abs(float(left.get("energy", 0.0)) - float(right.get("energy", 0.0))) > 1e-6:
        return True
    if int(left.get("component_count", 0)) != int(right.get("component_count", 0)):
        return True
    left_components = left.get("components", [])
    right_components = right.get("components", [])
    if len(left_components) != len(right_components):
        return True
    for left_component, right_component in zip(left_components, right_components):
        if left_component.get("component_id") != right_component.get("component_id"):
            return True
        if not _close(
            left_component.get("centroid_world", []),
            right_component.get("centroid_world", []),
            tolerance=1e-6,
        ):
            return True
    return False


def _check_field_response_against_baseline(
    loaded_session: dict[str, Any],
    baseline_session: dict[str, Any] | None,
) -> CompletionCheck:
    commands: list[InteractionCommand] = loaded_session.get("interaction_commands", [])
    summaries = _interactive_summaries_by_tick(loaded_session.get("field_summaries", []))
    baseline_summaries = _interactive_summaries_by_tick((baseline_session or {}).get("field_summaries", []))
    failures: list[dict[str, Any]] = []
    if not commands:
        failures.append({"reason": "missing_interaction_commands"})
    for command in commands:
        source_tick = int(command.payload.get("source_frame_tick", command.tick))
        post_ticks = sorted(tick for tick in summaries if tick > source_tick)
        if not post_ticks:
            failures.append({"command_id": command.command_id, "reason": "missing_post_interaction_summary"})
            continue
        changed = False
        if baseline_summaries:
            for tick in post_ticks:
                baseline = baseline_summaries.get(tick)
                if baseline is not None and _summary_changed(summaries[tick], baseline):
                    changed = True
                    break
        else:
            source_summary = summaries.get(source_tick)
            if source_summary is not None:
                changed = any(_summary_changed(summaries[tick], source_summary) for tick in post_ticks)
        if not changed:
            failures.append({"command_id": command.command_id, "reason": "no_measurable_field_response"})
    return _completion_check(
        "field_response_against_baseline",
        bool(commands) and not failures,
        {"baseline_provided": baseline_session is not None, "failures": failures[:20]},
    )


def _check_projection_after_interaction(loaded_session: dict[str, Any]) -> CompletionCheck:
    frames = _interactive_frames_by_id(loaded_session.get("projection_frames", []))
    failures: list[dict[str, Any]] = []
    for audit in loaded_session.get("interaction_audit", []):
        command_payload = audit.get("command", {}).get("payload", {})
        source_tick = int(command_payload.get("source_frame_tick", audit.get("source_frame_tick", -1)))
        wave_step_id = audit.get("field_wave_step_record_id")
        interaction_record_id = audit.get("interaction_record_id")
        resulting_frame_ids = audit.get("resulting_projection_frame_ids", [])
        if not resulting_frame_ids:
            failures.append({"audit_id": audit.get("audit_id"), "reason": "missing_resulting_projection_frames"})
            continue
        for frame_id in resulting_frame_ids:
            frame = frames.get(frame_id)
            if frame is None:
                failures.append({"audit_id": audit.get("audit_id"), "reason": "resulting_frame_missing", "frame_id": frame_id})
                continue
            timeline = frame.payload.get("event_timeline", {})
            if frame.tick <= source_tick:
                failures.append({"frame_id": frame_id, "reason": "frame_not_after_interaction"})
            if wave_step_id not in timeline.get("wave_step_record_ids", []):
                failures.append({"frame_id": frame_id, "reason": "frame_timeline_missing_wave_step"})
            if frame.tick == source_tick + 1 and interaction_record_id not in timeline.get("interaction_record_ids", []):
                failures.append({"frame_id": frame_id, "reason": "first_result_frame_missing_interaction_record"})
            if not frame.samples:
                failures.append({"frame_id": frame_id, "reason": "empty_projection_samples"})
    return _completion_check(
        "projection_after_interaction",
        bool(loaded_session.get("interaction_audit", [])) and not failures,
        {"failures": failures[:20]},
    )


def _check_compact_artifact_policy(
    loaded_session: dict[str, Any],
    *,
    max_default_artifact_bytes: int,
) -> CompletionCheck:
    artifact_dir = loaded_session.get("artifact_dir")
    manifest = loaded_session.get("manifest", {})
    failures: list[dict[str, Any]] = []
    total_bytes = 0
    forbidden_default_files = {"field_states.jsonl", "full_field_states.jsonl.gz"}
    if not artifact_dir:
        failures.append({"reason": "missing_artifact_dir"})
    else:
        output_path = Path(artifact_dir)
        for path in output_path.iterdir():
            if path.is_file():
                total_bytes += path.stat().st_size
        for filename in forbidden_default_files:
            if (output_path / filename).exists():
                failures.append({"reason": "forbidden_default_full_field_artifact", "file": filename})
    if total_bytes > max_default_artifact_bytes:
        failures.append(
            {
                "reason": "artifact_size_exceeds_limit",
                "total_bytes": total_bytes,
                "max_default_artifact_bytes": max_default_artifact_bytes,
            }
        )
    if manifest.get("debug_full_field_history") is False and "full_field_states" in manifest.get("artifacts", {}):
        failures.append({"reason": "full_field_history_without_debug_flag"})
    return _completion_check(
        "compact_artifact_policy",
        not failures,
        {
            "artifact_dir": artifact_dir,
            "total_bytes": total_bytes,
            "max_default_artifact_bytes": max_default_artifact_bytes,
            "failures": failures[:20],
        },
    )


def _check_no_viewer_authority_state(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    manifest = loaded_session.get("manifest", {})
    if manifest.get("viewer_authority_state") is not None:
        failures.append({"reason": "manifest_contains_viewer_authority_state"})
    for frame in loaded_session.get("projection_frames", []):
        payload = frame.get("payload", {}) if isinstance(frame, dict) else frame.payload
        frame_id = str(frame.get("frame_id", "")) if isinstance(frame, dict) else frame.frame_id
        timeline = payload.get("event_timeline", {})
        is_authority_state = bool(frame.get("is_authority_state", False)) if isinstance(frame, dict) else frame.is_authority_state
        if is_authority_state:
            failures.append({"frame_id": frame_id, "reason": "frame_authority_state"})
        if timeline.get("is_authority_state") is not False:
            failures.append({"frame_id": frame_id, "reason": "timeline_authority_state"})
        if payload.get("viewer_authority_state") is not None:
            failures.append({"frame_id": frame_id, "reason": "frame_contains_viewer_authority_state"})
    return _completion_check(
        "no_viewer_authority_state",
        not failures,
        {"failures": failures[:20]},
    )


def _check_no_persistent_light_or_particle_authority(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    forbidden_terms = FORBIDDEN_AUTHORITY_ENTITIES | {"particle", "light_source_object"}
    for frame in loaded_session.get("projection_frames", []):
        frame_id = str(frame.get("frame_id", "")) if isinstance(frame, dict) else frame.frame_id
        samples = list(frame.get("samples", [])) if isinstance(frame, dict) else frame.samples
        phenomena_overlays = list(frame.get("phenomena_overlays", [])) if isinstance(frame, dict) else frame.phenomena_overlays
        for sample in samples:
            sample_object_id = sample.get("object_id", "") if isinstance(sample, dict) else sample.object_id
            sample_family = sample.get("family", "") if isinstance(sample, dict) else sample.family
            sample_source_object_ids = sample.get("source_object_ids", []) if isinstance(sample, dict) else sample.source_object_ids
            sample_id = sample.get("sample_id", "") if isinstance(sample, dict) else sample.sample_id
            sample_terms = {
                str(sample_object_id),
                str(sample_family),
                *[str(item) for item in sample_source_object_ids],
            }
            if forbidden_terms & sample_terms:
                failures.append({"frame_id": frame_id, "sample_id": sample_id, "reason": "forbidden_sample_authority"})
        for overlay in phenomena_overlays:
            phenomenon = overlay.get("phenomenon", "") if isinstance(overlay, dict) else overlay.phenomenon
            payload = overlay.get("payload", {}) if isinstance(overlay, dict) else overlay.payload
            overlay_id = overlay.get("overlay_id", "") if isinstance(overlay, dict) else overlay.overlay_id
            if phenomenon == "light" and payload.get("is_persistent_light_object") is not False:
                failures.append({"overlay_id": overlay_id, "reason": "persistent_light_object"})
            if phenomenon == "rain" and payload.get("no_global_raindrop_authority_state") is not True:
                failures.append({"overlay_id": overlay_id, "reason": "global_raindrop_authority_state"})
            if phenomenon == "background_flux" and payload.get("no_global_raindrop_authority_state") is not True:
                failures.append({"overlay_id": overlay_id, "reason": "background_flux_authority_state"})
    return _completion_check(
        "no_persistent_light_or_particle_authority",
        not failures,
        {"failures": failures[:20]},
    )


def evaluate_interactive_session_completion(
    loaded_session: dict[str, Any],
    *,
    baseline_session: dict[str, Any] | None = None,
    max_default_artifact_bytes: int = 25_000_000,
) -> CompletionReport:
    checks = [
        _check_interactive_artifact_replayability(loaded_session),
        _check_interactive_command_provenance(loaded_session),
        _check_interaction_to_field_wave_step(loaded_session),
        _check_interaction_overlay_provenance(loaded_session),
        _check_interaction_trace_replayability(loaded_session),
        _check_field_response_against_baseline(loaded_session, baseline_session),
        _check_affordance_command_provenance(loaded_session),
        _check_affordance_wave_step_binding(loaded_session),
        _check_affordance_projection_replayability(loaded_session),
        _check_no_derived_affordance_authority(loaded_session),
        _check_projection_after_interaction(loaded_session),
        _check_compact_artifact_policy(
            loaded_session,
            max_default_artifact_bytes=max_default_artifact_bytes,
        ),
        _check_no_viewer_authority_state(loaded_session),
        _check_no_persistent_light_or_particle_authority(loaded_session),
    ]
    overall_status = "passed" if all(check.status == "passed" for check in checks) else "failed"
    manifest = loaded_session.get("manifest", {})
    return CompletionReport(
        overall_status=overall_status,
        checks=checks,
        summary={
            "runtime_mode": manifest.get("runtime_mode"),
            "interactive_world_window_completion": overall_status,
            "projection_frame_count": len(loaded_session.get("projection_frames", [])),
            "interaction_command_count": len(loaded_session.get("interaction_commands", [])),
            "field_summary_count": len(loaded_session.get("field_summaries", [])),
            "baseline_used": baseline_session is not None,
            "trace_replayability_status": "passed"
            if any(
                check.name == "interaction_trace_replayability" and check.status == "passed"
                for check in checks
            )
            else "failed",
        },
        audit={
            "authority_boundary": "viewer_requests_are_not_authority_state",
            "interaction_chain": "request -> command -> field_source -> field_wave_step -> projection_frame",
        },
    )


def _playable_records(loaded_session: dict[str, Any]) -> list[dict[str, Any]]:
    records = list(loaded_session.get("playable_consequence_records", []))
    for state in loaded_session.get("world_states", []):
        for event in getattr(state, "events", state.get("events", [])):
            kind = getattr(event, "kind", event.get("kind"))
            if kind != "playable_consequence":
                continue
            payload = getattr(event, "payload", event.get("payload", {}))
            record = dict(payload)
            record.setdefault("event_record_id", getattr(event, "record_id", event.get("record_id", "")))
            records.append(record)
    return records


def _frame_playable_overlays(frame: ProjectionFrame | dict[str, Any]) -> list[dict[str, Any]]:
    payload = frame.get("payload", {}) if isinstance(frame, dict) else frame.payload
    return list(payload.get("playable_consequence_overlays", []))


def _check_playable_consequence_lineage(records: list[dict[str, Any]]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    if not records:
        failures.append({"reason": "missing_playable_consequence_records"})
    for record in records:
        consequence_id = record.get("consequence_id")
        if record.get("schema") != "playable_consequence_record_v1":
            failures.append({"consequence_id": consequence_id, "reason": "invalid_schema"})
        if not record.get("baseline_case_id"):
            failures.append({"consequence_id": consequence_id, "reason": "missing_baseline_case_id"})
        if not record.get("source_wave_step_record_ids"):
            failures.append({"consequence_id": consequence_id, "reason": "missing_wave_step_lineage"})
        if not (record.get("source_command_ids") or record.get("source_affordance_ids")):
            failures.append({"consequence_id": consequence_id, "reason": "missing_command_or_affordance_lineage"})
        if not record.get("projection_frame_ids"):
            failures.append({"consequence_id": consequence_id, "reason": "missing_projection_frame_ids"})
    return _completion_check(
        "playable_consequence_lineage",
        not failures,
        {"record_count": len(records), "failures": failures[:20]},
    )


def _recompute_playable_record(record: dict[str, Any]) -> dict[str, Any]:
    inputs = dict(record.get("recompute_inputs", {}))
    kind = record.get("kind")
    common = {
        "consequence_id": str(record.get("consequence_id")),
        "tick": int(record.get("tick", 0)),
        "source_command_ids": list(record.get("source_command_ids", [])),
        "source_affordance_ids": list(record.get("source_affordance_ids", [])),
        "source_wave_step_record_ids": list(record.get("source_wave_step_record_ids", [])),
        "baseline_case_id": str(record.get("baseline_case_id", "")),
        "projection_frame_ids": list(record.get("projection_frame_ids", [])),
    }
    if kind == "dampening_absorption":
        return compute_dampening_absorption(
            consequence_id=common["consequence_id"],
            tick=common["tick"],
            channel=inputs["channel"],
            before_field=inputs["before_field"],
            after_field=inputs["after_field"],
            baseline_before_field=inputs["baseline_before_field"],
            baseline_after_field=inputs["baseline_after_field"],
            source_command_ids=common["source_command_ids"],
            source_wave_step_record_ids=common["source_wave_step_record_ids"],
            baseline_case_id=common["baseline_case_id"],
            projection_frame_ids=common["projection_frame_ids"],
        )
    if kind == "boundary_containment":
        return compute_boundary_containment(
            consequence_id=common["consequence_id"],
            tick=common["tick"],
            boundary_grid=inputs["boundary_grid"],
            support_grid=inputs["support_grid"],
            reflected_energy_ratio=float(inputs["reflected_energy_ratio"]),
            retained_energy_ratio=float(inputs["retained_energy_ratio"]),
            source_affordance_ids=common["source_affordance_ids"],
            source_wave_step_record_ids=common["source_wave_step_record_ids"],
            baseline_case_id=common["baseline_case_id"],
            projection_frame_ids=common["projection_frame_ids"],
        )
    if kind == "channel_transport":
        return compute_channel_transport(
            consequence_id=common["consequence_id"],
            tick=common["tick"],
            transport_vector_world=inputs["transport_vector_world"],
            channel_direction_world=inputs["channel_direction_world"],
            exit_energy_ratio=float(inputs["exit_energy_ratio"]),
            baseline_exit_energy_ratio=float(inputs["baseline_exit_energy_ratio"]),
            source_affordance_ids=common["source_affordance_ids"],
            source_wave_step_record_ids=common["source_wave_step_record_ids"],
            baseline_case_id=common["baseline_case_id"],
            projection_frame_ids=common["projection_frame_ids"],
        )
    if kind == "source_maintenance":
        return compute_source_maintenance(
            consequence_id=common["consequence_id"],
            tick=common["tick"],
            maintained_energy_ratio=float(inputs["maintained_energy_ratio"]),
            baseline_maintained_energy_ratio=float(inputs["baseline_maintained_energy_ratio"]),
            source_command_ids=common["source_command_ids"],
            source_wave_step_record_ids=common["source_wave_step_record_ids"],
            baseline_case_id=common["baseline_case_id"],
            projection_frame_ids=common["projection_frame_ids"],
        )
    if kind == "cohesion_accumulation":
        return compute_cohesion_accumulation(
            consequence_id=common["consequence_id"],
            tick=common["tick"],
            support_iou=float(inputs["support_iou"]),
            component_count_delta=int(inputs["component_count_delta"]),
            source_affordance_ids=common["source_affordance_ids"],
            source_wave_step_record_ids=common["source_wave_step_record_ids"],
            baseline_case_id=common["baseline_case_id"],
            projection_frame_ids=common["projection_frame_ids"],
        )
    if kind == "local_perturbation_response":
        return compute_local_perturbation_response(
            consequence_id=common["consequence_id"],
            tick=common["tick"],
            visible_frame_count=int(inputs["visible_frame_count"]),
            source_command_ids=common["source_command_ids"],
            source_wave_step_record_ids=common["source_wave_step_record_ids"],
            baseline_case_id=common["baseline_case_id"],
            projection_frame_ids=common["projection_frame_ids"],
        )
    raise ValueError(f"Unsupported playable consequence kind: {kind}")


def _check_playable_consequence_recompute(records: list[dict[str, Any]]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    for record in records:
        consequence_id = record.get("consequence_id")
        if not record.get("recompute_inputs"):
            failures.append({"consequence_id": consequence_id, "reason": "missing_recompute_inputs"})
            continue
        try:
            recomputed = _recompute_playable_record(record)
        except (KeyError, TypeError, ValueError) as exc:
            failures.append({"consequence_id": consequence_id, "reason": f"recompute_failed: {exc}"})
            continue
        if recomputed.get("status") != record.get("status"):
            failures.append(
                {
                    "consequence_id": consequence_id,
                    "reason": "status_not_recomputed_from_raw_inputs",
                    "record_status": record.get("status"),
                    "recomputed_status": recomputed.get("status"),
                }
            )
    return _completion_check(
        "playable_consequence_recompute",
        bool(records) and not failures,
        {"record_count": len(records), "failures": failures[:20]},
    )


def _check_playable_projection_replayability(
    records: list[dict[str, Any]],
    frames: list[ProjectionFrame],
    observer_ids: list[str],
) -> CompletionCheck:
    frames_by_id = {
        str(frame.get("frame_id", "")) if isinstance(frame, dict) else frame.frame_id: frame
        for frame in frames
    }
    frames_by_tick_observer = {
        (
            int(frame.get("tick", -1)) if isinstance(frame, dict) else frame.tick,
            str(frame.get("observer_id", "")) if isinstance(frame, dict) else frame.observer_id,
        ): frame
        for frame in frames
    }
    failures: list[dict[str, Any]] = []
    for record in records:
        consequence_id = record.get("consequence_id")
        listed_frame_ids = list(record.get("projection_frame_ids", []))
        for frame_id in listed_frame_ids:
            frame = frames_by_id.get(frame_id)
            if frame is None:
                failures.append({"consequence_id": consequence_id, "frame_id": frame_id, "reason": "missing_projection_frame"})
                continue
            overlays = [
                overlay
                for overlay in _frame_playable_overlays(frame)
                if overlay.get("consequence_id") == consequence_id
            ]
            if not overlays:
                failures.append({"consequence_id": consequence_id, "frame_id": frame_id, "reason": "missing_playable_overlay"})
                continue
            for overlay in overlays:
                if overlay.get("schema") != "playable_consequence_overlay_v1":
                    failures.append({"consequence_id": consequence_id, "frame_id": frame_id, "reason": "invalid_overlay_schema"})
                if overlay.get("is_authority_state") is not False:
                    failures.append({"consequence_id": consequence_id, "frame_id": frame_id, "reason": "overlay_authority_state"})
                source_ids = set(overlay.get("source_record_ids", []))
                if not set(record.get("source_wave_step_record_ids", [])) <= source_ids:
                    failures.append({"consequence_id": consequence_id, "frame_id": frame_id, "reason": "overlay_missing_wave_step_source"})
        for observer_id in observer_ids:
            frame = frames_by_tick_observer.get((int(record.get("tick", -1)), observer_id))
            if frame is None:
                continue
            if not any(
                overlay.get("consequence_id") == consequence_id
                for overlay in _frame_playable_overlays(frame)
            ):
                frame_id = str(frame.get("frame_id", "")) if isinstance(frame, dict) else frame.frame_id
                failures.append(
                    {
                        "consequence_id": consequence_id,
                        "frame_id": frame_id,
                        "reason": "missing_overlay_for_declared_observer_tick",
                    }
                )
    return _completion_check(
        "playable_projection_replayability",
        bool(records) and not failures,
        {"record_count": len(records), "frame_count": len(frames), "failures": failures[:20]},
    )


def evaluate_playable_world_completion(loaded_session: dict[str, Any]) -> CompletionReport:
    records = _playable_records(loaded_session)
    frames = list(loaded_session.get("projection_frames", []))
    observer_ids = list(loaded_session.get("manifest", {}).get("observer_ids") or sorted({frame.observer_id for frame in frames}))
    checks = [
        _check_playable_consequence_lineage(records),
        _check_playable_consequence_recompute(records),
        _check_playable_projection_replayability(records, frames, observer_ids),
        _check_no_viewer_authority_state(loaded_session),
        _check_no_persistent_light_or_particle_authority(loaded_session),
    ]
    overall_status = "passed" if all(check.status == "passed" for check in checks) else "failed"
    return CompletionReport(
        overall_status=overall_status,
        checks=checks,
        summary={
            "playable_world_completion": overall_status,
            "playable_consequence_count": len(records),
            "projection_frame_count": len(frames),
        },
        audit={
            "authority_boundary": "playable consequences are replayed from raw field inputs and projection frames",
        },
    )


def _frame_value(frame: Any, key: str, default: Any = None) -> Any:
    if isinstance(frame, dict):
        return frame.get(key, default)
    return getattr(frame, key, default)


def _check_exploration_episode_shape(episode: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    if episode.get("schema") != EXPLORATION_EPISODE_SCHEMA:
        failures.append({"reason": "invalid_episode_schema"})
    if int(episode.get("play_ticks", 0)) < MIN_PLAY_TICKS:
        failures.append({"reason": "insufficient_play_ticks", "play_ticks": episode.get("play_ticks")})
    command_ids = list(episode.get("command_ids", []))
    if len(command_ids) < MIN_TOOL_COMMANDS:
        failures.append({"reason": "insufficient_command_count", "command_count": len(command_ids)})
    tool_schedule = list(episode.get("tool_schedule", []))
    tool_kinds = {
        str(step.get("request", {}).get("tool"))
        for step in tool_schedule
        if isinstance(step, dict) and isinstance(step.get("request"), dict)
    }
    if tool_schedule and len(tool_kinds) < MIN_DISTINCT_TOOL_KINDS:
        failures.append({"reason": "insufficient_distinct_tool_kinds", "tool_kinds": sorted(tool_kinds)})
    if not episode.get("declared_observer_ids"):
        failures.append({"reason": "missing_declared_observer_ids"})
    return _completion_check(
        "exploration_episode_shape",
        not failures,
        {"failures": failures[:20]},
    )


def _playable_records_by_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(record.get("consequence_id")): record for record in records}


def _check_exploration_consequence_windows(
    windows: list[dict[str, Any]],
    playable_records: list[dict[str, Any]],
) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    records_by_id = _playable_records_by_id(playable_records)
    backed_ids: set[str] = set()
    passed_windows = 0
    for window in windows:
        window_id = str(window.get("window_id", ""))
        if window.get("schema") != CONSEQUENCE_WINDOW_SCHEMA:
            failures.append({"window_id": window_id, "reason": "invalid_window_schema"})
            continue
        metrics = window.get("metrics", {})
        missing_metrics = sorted(REQUIRED_WINDOW_METRICS - set(metrics))
        if missing_metrics:
            failures.append({"window_id": window_id, "reason": "missing_window_metrics", "metrics": missing_metrics})
        if not window.get("baseline_case_id"):
            failures.append({"window_id": window_id, "reason": "missing_baseline_case_id"})
        if not window.get("frame_ids"):
            failures.append({"window_id": window_id, "reason": "missing_frame_ids"})
        if not window.get("consequence_ids"):
            failures.append({"window_id": window_id, "reason": "missing_consequence_ids"})
        source_ids = list(window.get("source_playable_consequence_record_ids", []))
        if not source_ids:
            failures.append({"window_id": window_id, "reason": "missing_backing_playable_records"})
        for consequence_id in source_ids:
            record = records_by_id.get(str(consequence_id))
            if record is None:
                failures.append(
                    {"window_id": window_id, "consequence_id": consequence_id, "reason": "missing_backing_playable_record"}
                )
                continue
            backed_ids.add(str(consequence_id))
            if record.get("status") != "passed":
                failures.append({"window_id": window_id, "consequence_id": consequence_id, "reason": "backing_record_not_passed"})
            if not record.get("baseline_case_id"):
                failures.append({"window_id": window_id, "consequence_id": consequence_id, "reason": "backing_record_missing_baseline"})
            if not record.get("projection_frame_ids"):
                failures.append({"window_id": window_id, "consequence_id": consequence_id, "reason": "backing_record_missing_projection_frames"})
            if not record.get("source_wave_step_record_ids"):
                failures.append({"window_id": window_id, "consequence_id": consequence_id, "reason": "backing_record_missing_wave_steps"})
        try:
            visible_frame_count = float(metrics.get("visible_frame_count", -1))
            dead_frame_ratio = float(metrics.get("dead_frame_ratio", 1))
            response_lag = float(metrics.get("response_lag_ticks", 10**9))
            overlay_coverage = float(metrics.get("consequence_overlay_coverage", 0))
        except (TypeError, ValueError):
            failures.append({"window_id": window_id, "reason": "invalid_metric_value"})
            continue
        if visible_frame_count < MIN_VISIBLE_CONSEQUENCE_FRAMES:
            failures.append({"window_id": window_id, "reason": "insufficient_visible_frames"})
        if dead_frame_ratio > MAX_DEAD_FRAME_RATIO:
            failures.append({"window_id": window_id, "reason": "dead_frame_ratio_exceeded"})
        if response_lag > MAX_INTERACTION_RESPONSE_LAG_TICKS:
            failures.append({"window_id": window_id, "reason": "response_lag_exceeded"})
        if overlay_coverage < 1.0:
            failures.append({"window_id": window_id, "reason": "incomplete_overlay_coverage"})
        if window.get("status") == "passed":
            passed_windows += 1
    if passed_windows < MIN_CONSEQUENCE_WINDOWS:
        failures.append({"reason": "insufficient_passed_consequence_windows", "passed_window_count": passed_windows})
    if len(backed_ids) < MIN_BACKED_PLAYABLE_CONSEQUENCE_RECORDS:
        failures.append({"reason": "insufficient_backed_playable_consequence_records", "backed_count": len(backed_ids)})
    return _completion_check(
        "exploration_consequence_windows",
        not failures,
        {"failures": failures[:20], "window_count": len(windows), "backed_count": len(backed_ids)},
    )


def _check_exploration_region_reentry(records: list[dict[str, Any]]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    passed = 0
    for record in records:
        reentry_id = str(record.get("reentry_id", ""))
        if record.get("schema") != REGION_REENTRY_SCHEMA:
            failures.append({"reentry_id": reentry_id, "reason": "invalid_reentry_schema"})
            continue
        metrics = record.get("continuity_metrics", {})
        missing_metrics = sorted(REQUIRED_REENTRY_METRICS - set(metrics))
        if missing_metrics:
            failures.append({"reentry_id": reentry_id, "reason": "missing_reentry_metrics", "metrics": missing_metrics})
        if not record.get("source_consequence_ids"):
            failures.append({"reentry_id": reentry_id, "reason": "missing_source_consequence_ids"})
        if not record.get("source_frame_ids"):
            failures.append({"reentry_id": reentry_id, "reason": "missing_source_frame_ids"})
        if int(record.get("return_tick", 0)) <= int(record.get("first_tick", 0)):
            failures.append({"reentry_id": reentry_id, "reason": "invalid_return_tick"})
        if record.get("status") == "passed":
            passed += 1
    if passed < MIN_REGION_REENTRY_COUNT:
        failures.append({"reason": "insufficient_region_reentry_count", "passed_count": passed})
    return _completion_check(
        "exploration_region_reentry",
        not failures,
        {"failures": failures[:20], "passed_count": passed},
    )


def _check_exploration_observer_coverage(
    episode: dict[str, Any],
    manifest: dict[str, Any],
    frames: list[Any],
) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    declared = list(episode.get("declared_observer_ids", []))
    manifest_ids = list(manifest.get("observer_ids", []))
    if manifest_ids and sorted(manifest_ids) != sorted(declared):
        failures.append({"reason": "manifest_observer_mismatch", "manifest": manifest_ids, "declared": declared})
    if not frames:
        failures.append({"reason": "missing_projection_frames"})
    ticks = sorted({int(_frame_value(frame, "tick", -1)) for frame in frames})
    for tick in ticks:
        observers_for_tick = sorted(
            str(_frame_value(frame, "observer_id"))
            for frame in frames
            if int(_frame_value(frame, "tick", -1)) == tick
        )
        if sorted(declared) != observers_for_tick:
            failures.append({"reason": "observer_frame_coverage_gap", "tick": tick, "observers": observers_for_tick})
    coverage = 0.0 if failures else OBSERVER_FRAME_COVERAGE_RATIO
    return _completion_check(
        "exploration_observer_coverage",
        not failures,
        {"failures": failures[:20], "coverage": coverage},
    )


def _check_exploration_backing_playable_completion(loaded_session: dict[str, Any]) -> CompletionCheck:
    report = evaluate_playable_world_completion(loaded_session)
    failed_checks = [
        {"name": check.name, "details": check.details}
        for check in report.checks
        if check.status != "passed"
    ]
    return _completion_check(
        "exploration_backing_playable_completion",
        report.overall_status == "passed",
        {
            "playable_world_completion": report.overall_status,
            "playable_consequence_count": report.summary.get("playable_consequence_count", 0),
            "failed_checks": failed_checks[:20],
        },
    )


def evaluate_long_interactive_exploration_completion(loaded_session: dict[str, Any]) -> CompletionReport:
    episode = dict(loaded_session.get("exploration_episode") or {})
    manifest = dict(loaded_session.get("manifest") or {})
    frames = list(loaded_session.get("projection_frames", []))
    windows = list(loaded_session.get("consequence_windows", []))
    reentries = list(loaded_session.get("region_reentry_records", []))
    playable_records = list(loaded_session.get("playable_consequence_records", []))
    checks = [
        _check_exploration_episode_shape(episode),
        _check_exploration_consequence_windows(windows, playable_records),
        _check_exploration_region_reentry(reentries),
        _check_exploration_observer_coverage(episode, manifest, frames),
        _check_exploration_backing_playable_completion(loaded_session),
    ]
    overall_status = "passed" if all(check.status == "passed" for check in checks) else "failed"
    return CompletionReport(
        overall_status=overall_status,
        checks=checks,
        summary={
            "long_interactive_exploration_completion": overall_status,
            "play_ticks": episode.get("play_ticks"),
            "consequence_window_count": len(windows),
            "region_reentry_count": len(reentries),
            "projection_frame_count": len(frames),
        },
        audit={
            "authority_boundary": "exploration records index read-back field consequences and projection frames",
        },
    )


SPECTRAL_CAMERA_MAIN_PAYLOAD_FORBIDDEN_KEYS = set(SPECTRAL_CAMERA_DEBUG_LAYER_KEYS)


def _spectral_as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        return dict(value.to_dict())
    return dict(value)


def _spectral_id(value: dict[str, Any], *keys: str) -> str:
    for key in keys:
        if value.get(key):
            return str(value[key])
    return ""


def _spectral_frame_payload(frame: Any) -> dict[str, Any]:
    payload = _frame_value(frame, "payload", {})
    return dict(payload or {})


def _index_spectral_records(items: list[Any], *id_keys: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in items:
        mapping = _spectral_as_dict(item)
        record_id = _spectral_id(mapping, *id_keys)
        if record_id:
            indexed[record_id] = mapping
    return indexed


def _normalize_spectral_property_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(record)
    if "id" not in normalized and normalized.get("record_id"):
        normalized["id"] = normalized["record_id"]
    return normalized


def _check_spectral_camera_frame_contract(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    frames = list(loaded_session.get("projection_frames", []))
    if not frames:
        failures.append({"reason": "missing_projection_frames"})
    for frame in frames:
        frame_id = str(_frame_value(frame, "frame_id", ""))
        payload = _spectral_frame_payload(frame)
        if payload.get("render_mode") != "spectral_camera_observation_v1":
            failures.append({"frame_id": frame_id, "reason": "missing_spectral_camera_render_mode"})
        forbidden = sorted(SPECTRAL_CAMERA_MAIN_PAYLOAD_FORBIDDEN_KEYS.intersection(payload.keys()))
        if forbidden:
            failures.append({"frame_id": frame_id, "reason": "direct_artifact_main_payload", "keys": forbidden})
        debug_layers = payload.get("debug_layers", {})
        if not isinstance(debug_layers, dict) or debug_layers.get("schema") != "spectral_camera_debug_layers_v1":
            failures.append({"frame_id": frame_id, "reason": "missing_debug_layers"})
        elif debug_layers.get("default_enabled") is not False or debug_layers.get("is_authority_state") is not False:
            failures.append({"frame_id": frame_id, "reason": "debug_layers_not_default_off_non_authority"})
        camera_frame = payload.get("spectral_camera_frame")
        if not isinstance(camera_frame, dict):
            failures.append({"frame_id": frame_id, "reason": "missing_spectral_camera_frame"})
            continue
        try:
            validate_spectral_camera_frame(camera_frame)
        except ValueError as exc:
            failures.append({"frame_id": frame_id, "reason": "invalid_spectral_camera_frame", "message": str(exc)})
            continue
        if camera_frame.get("observer_id") != _frame_value(frame, "observer_id"):
            failures.append({"frame_id": frame_id, "reason": "observer_id_mismatch"})
        if int(camera_frame.get("tick", -1)) != int(_frame_value(frame, "tick", -2)):
            failures.append({"frame_id": frame_id, "reason": "tick_mismatch"})
        expected_digest = canonical_spectral_camera_pixel_digest(camera_frame)
        if camera_frame.get("pixel_digest") != expected_digest:
            failures.append({"frame_id": frame_id, "reason": "pixel_digest_mismatch"})
    return _completion_check(
        "spectral_camera_frame_contract",
        not failures,
        {"failures": failures[:20], "projection_frame_count": len(frames)},
    )


def _check_spectral_camera_readback_replay(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    fields = _index_spectral_records(
        list(loaded_session.get("field_states", [])),
        "field_state_id",
        "id",
    )
    properties = _index_spectral_records(
        list(loaded_session.get("derived_material_property_records", [])),
        "record_id",
        "id",
    )
    consequences = _index_spectral_records(
        list(loaded_session.get("playable_consequence_records", [])),
        "consequence_id",
        "record_id",
        "id",
    )
    for frame in loaded_session.get("projection_frames", []):
        frame_id = str(_frame_value(frame, "frame_id", ""))
        camera_frame = _spectral_frame_payload(frame).get("spectral_camera_frame")
        if not isinstance(camera_frame, dict):
            failures.append({"frame_id": frame_id, "reason": "missing_spectral_camera_frame"})
            continue
        source_field_ids = list(camera_frame.get("source_field_state_ids", []))
        if not source_field_ids:
            failures.append({"frame_id": frame_id, "reason": "missing_source_field_state_ids"})
            continue
        field_state = fields.get(str(source_field_ids[0]))
        if not field_state:
            failures.append({"frame_id": frame_id, "reason": "source_field_state_not_found", "field_state_id": source_field_ids[0]})
            continue
        source_property_ids = [str(item) for item in camera_frame.get("source_property_record_ids", [])]
        missing_property_ids = [record_id for record_id in source_property_ids if record_id not in properties]
        if missing_property_ids:
            failures.append({"frame_id": frame_id, "reason": "source_property_records_not_found", "record_ids": missing_property_ids})
            continue
        property_records = [
            _normalize_spectral_property_record(properties[record_id])
            for record_id in source_property_ids
        ]
        source_consequence_ids = [str(item) for item in camera_frame.get("source_playable_consequence_record_ids", [])]
        missing_consequence_ids = [record_id for record_id in source_consequence_ids if record_id not in consequences]
        if missing_consequence_ids:
            failures.append({"frame_id": frame_id, "reason": "source_playable_consequence_records_not_found", "record_ids": missing_consequence_ids})
            continue
        consequence_records = [
            {"id": record_id, **consequences[record_id]}
            for record_id in source_consequence_ids
        ]
        base_source_record_ids = [
            str(record_id)
            for record_id in camera_frame.get("source_record_ids", [])
            if str(record_id) not in set(source_property_ids + source_consequence_ids)
        ]
        try:
            replayed = sample_spectral_camera_frame(
                field_state={**field_state, "id": _spectral_id(field_state, "field_state_id", "id")},
                observer_pose=camera_frame["observer_pose"],
                camera_model=camera_frame["camera_model"],
                property_records=property_records,
                playable_consequence_records=consequence_records,
                source_record_ids=base_source_record_ids,
            )
        except Exception as exc:  # noqa: BLE001 - completion reports replay failures as data.
            failures.append({"frame_id": frame_id, "reason": "readback_replay_error", "message": str(exc)})
            continue
        if replayed.get("pixel_digest") != camera_frame.get("pixel_digest"):
            failures.append(
                {
                    "frame_id": frame_id,
                    "reason": "readback_pixel_digest_mismatch",
                    "expected": replayed.get("pixel_digest"),
                    "actual": camera_frame.get("pixel_digest"),
                }
            )
    return _completion_check(
        "spectral_camera_readback_replay",
        not failures,
        {"failures": failures[:20], "projection_frame_count": len(loaded_session.get("projection_frames", []))},
    )


def evaluate_spectral_camera_observation_completion(loaded_session: dict[str, Any]) -> CompletionReport:
    checks = [
        _check_spectral_camera_frame_contract(loaded_session),
        _check_spectral_camera_readback_replay(loaded_session),
    ]
    overall_status = "passed" if all(check.status == "passed" for check in checks) else "failed"
    return CompletionReport(
        overall_status=overall_status,
        checks=checks,
        summary={
            "spectral_camera_observation_completion": overall_status,
            "projection_frame_count": len(loaded_session.get("projection_frames", [])),
            "field_state_count": len(loaded_session.get("field_states", [])),
        },
        audit={
            "authority_boundary": "main visual frame is a non-authority observer-relative spectral camera sample replayed from read-back field states",
        },
    )


CONTINUOUS_SPECTRAL_MAIN_PAYLOAD_FORBIDDEN_KEYS = set(SPECTRAL_CAMERA_MAIN_PAYLOAD_FORBIDDEN_KEYS) | {
    "css_color",
    "object_asset_id",
    "viewer_label_authority",
}


def _check_continuous_spectral_image_plane_contract(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    frames = list(loaded_session.get("projection_frames", []))
    if not frames:
        failures.append({"reason": "missing_projection_frames"})
    for frame in frames:
        frame_id = str(_frame_value(frame, "frame_id", ""))
        payload = _spectral_frame_payload(frame)
        if payload.get("render_mode") != "continuous_spectral_world_window_v1":
            failures.append({"frame_id": frame_id, "reason": "missing_continuous_render_mode"})
        forbidden = sorted(CONTINUOUS_SPECTRAL_MAIN_PAYLOAD_FORBIDDEN_KEYS.intersection(payload.keys()))
        if forbidden:
            failures.append({"frame_id": frame_id, "reason": "main_payload_authority_leak", "keys": forbidden})
        debug_layers = payload.get("debug_layers", {})
        if not isinstance(debug_layers, dict) or debug_layers.get("schema") != "spectral_camera_debug_layers_v1":
            failures.append({"frame_id": frame_id, "reason": "missing_debug_layers"})
        elif debug_layers.get("default_enabled") is not False or debug_layers.get("is_authority_state") is not False:
            failures.append({"frame_id": frame_id, "reason": "debug_layers_not_default_off_non_authority"})
        camera_frame = payload.get("spectral_camera_frame")
        if not isinstance(camera_frame, dict):
            failures.append({"frame_id": frame_id, "reason": "missing_spectral_camera_frame"})
            continue
        try:
            validate_spectral_camera_frame(camera_frame)
        except ValueError as exc:
            failures.append({"frame_id": frame_id, "reason": "invalid_spectral_camera_frame", "message": str(exc)})
            continue
        image_plane = payload.get("spectral_image_plane")
        if not isinstance(image_plane, dict):
            failures.append({"frame_id": frame_id, "reason": "missing_spectral_image_plane"})
            continue
        try:
            validate_spectral_image_plane(image_plane, camera_frame)
        except ValueError as exc:
            failures.append({"frame_id": frame_id, "reason": "invalid_spectral_image_plane", "message": str(exc)})
    return _completion_check(
        "continuous_spectral_image_plane_contract",
        not failures,
        {"failures": failures[:20], "projection_frame_count": len(frames)},
    )


def _check_continuous_spectral_camera_readback_replay(loaded_session: dict[str, Any]) -> CompletionCheck:
    replay = _check_spectral_camera_readback_replay(loaded_session)
    return _completion_check(
        "continuous_spectral_camera_readback_replay",
        replay.status == "passed",
        replay.details,
    )


def _check_continuous_spectral_image_plane_replay(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    for frame in loaded_session.get("projection_frames", []):
        frame_id = str(_frame_value(frame, "frame_id", ""))
        payload = _spectral_frame_payload(frame)
        camera_frame = payload.get("spectral_camera_frame")
        image_plane = payload.get("spectral_image_plane")
        if not isinstance(camera_frame, dict) or not isinstance(image_plane, dict):
            failures.append({"frame_id": frame_id, "reason": "missing_camera_or_image_plane"})
            continue
        try:
            replayed = build_spectral_image_plane(
                camera_frame,
                image_shape=image_plane.get("image_shape", [192, 128]),
                kernel_config={"kernel": image_plane.get("kernel", "energy_conserving_gaussian_splat_v1")},
            )
        except Exception as exc:  # noqa: BLE001 - completion reports replay failure as data.
            failures.append({"frame_id": frame_id, "reason": "image_plane_replay_error", "message": str(exc)})
            continue
        mismatches = [
            key
            for key in (
                "image_digest",
                "non_background_ratio",
                "sensor_dot_periodicity_score",
                "sample_replay_match_ratio",
                "color_mapping",
                "spatial_rendering",
            )
            if image_plane.get(key) != replayed.get(key)
        ]
        if mismatches:
            failures.append(
                {
                    "frame_id": frame_id,
                    "reason": "image_plane_replay_mismatch",
                    "mismatches": mismatches,
                }
            )
    return _completion_check(
        "continuous_spectral_image_plane_replay",
        not failures,
        {"failures": failures[:20], "projection_frame_count": len(loaded_session.get("projection_frames", []))},
    )


def _check_field_signature_authoring_replay(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    instances = [_spectral_as_dict(item) for item in loaded_session.get("field_signature_instances", [])]
    evidence_records = [_spectral_as_dict(item) for item in loaded_session.get("field_signature_evidence_records", [])]
    compilation_records = [_spectral_as_dict(item) for item in loaded_session.get("field_signature_compilation_records", [])]
    templates = [_spectral_as_dict(item) for item in loaded_session.get("field_signature_templates", [])]
    fields = _index_spectral_records(
        list(loaded_session.get("field_states", [])),
        "field_state_id",
        "id",
    )
    properties = _index_spectral_records(
        list(loaded_session.get("derived_material_property_records", [])),
        "record_id",
        "id",
    )
    if not instances:
        return _completion_check(
            "field_signature_authoring_replay",
            True,
            {"instance_count": 0, "status": "not_present"},
        )
    evidence_by_id = {str(record.get("evidence_id")): record for record in evidence_records}
    template_by_id = {str(template.get("template_id")): template for template in templates}
    for instance in instances:
        try:
            validate_field_signature_instance(instance, evidence_records, compilation_records, templates)
        except ValueError as exc:
            failures.append(
                {
                    "instance_id": instance.get("instance_id"),
                    "reason": "field_signature_replay_failed",
                    "message": str(exc),
                }
            )
            continue
        for evidence_id in [str(value) for value in instance.get("evidence_record_ids", [])]:
            evidence = evidence_by_id.get(evidence_id)
            template = template_by_id.get(str(instance.get("template_id")))
            if not evidence or not template:
                failures.append(
                    {
                        "instance_id": instance.get("instance_id"),
                        "reason": "missing_signature_replay_inputs",
                        "evidence_id": evidence_id,
                    }
                )
                continue
            sampled_field_ids = [str(value) for value in evidence.get("sampled_tick_field_state_ids", [])]
            missing_field_ids = [field_id for field_id in sampled_field_ids if field_id not in fields]
            if missing_field_ids:
                failures.append(
                    {
                        "instance_id": instance.get("instance_id"),
                        "reason": "signature_evidence_field_states_not_found",
                        "evidence_id": evidence_id,
                        "field_state_ids": missing_field_ids[:10],
                    }
                )
                continue
            property_ids = [str(value) for value in evidence.get("source_property_record_ids", [])]
            missing_property_ids = [record_id for record_id in property_ids if record_id not in properties]
            if missing_property_ids:
                failures.append(
                    {
                        "instance_id": instance.get("instance_id"),
                        "reason": "signature_evidence_property_records_not_found",
                        "evidence_id": evidence_id,
                        "record_ids": missing_property_ids[:10],
                    }
                )
                continue
            try:
                replayed = summarize_field_signature_evidence(
                    template=template,
                    field_states=[fields[field_id] for field_id in sampled_field_ids],
                    property_records=[properties[record_id] for record_id in property_ids],
                    baseline_case_id=str(evidence.get("baseline_case_id", "")),
                )
            except Exception as exc:  # noqa: BLE001 - completion reports replay failure as data.
                failures.append(
                    {
                        "instance_id": instance.get("instance_id"),
                        "reason": "signature_evidence_replay_error",
                        "evidence_id": evidence_id,
                        "message": str(exc),
                    }
                )
                continue
            mismatches = [
                key
                for key in (
                    "tick_range",
                    "source_field_state_ids",
                    "source_field_state_range",
                    "raw_support_digest",
                    "raw_channel_digest",
                    "computed_metrics",
                    "baseline_case_id",
                )
                if evidence.get(key) != replayed.get(key)
            ]
            if mismatches:
                failures.append(
                    {
                        "instance_id": instance.get("instance_id"),
                        "reason": "signature_evidence_replay_mismatch",
                        "evidence_id": evidence_id,
                        "mismatches": mismatches,
                    }
                )
    return _completion_check(
        "field_signature_authoring_replay",
        not failures,
        {"failures": failures[:20], "instance_count": len(instances)},
    )


def evaluate_continuous_spectral_world_window_completion(loaded_session: dict[str, Any]) -> CompletionReport:
    checks = [
        _check_continuous_spectral_image_plane_contract(loaded_session),
        _check_continuous_spectral_camera_readback_replay(loaded_session),
        _check_continuous_spectral_image_plane_replay(loaded_session),
        _check_field_signature_authoring_replay(loaded_session),
    ]
    overall_status = "passed" if all(check.status == "passed" for check in checks) else "failed"
    return CompletionReport(
        overall_status=overall_status,
        checks=checks,
        summary={
            "continuous_spectral_world_window_completion": overall_status,
            "projection_frame_count": len(loaded_session.get("projection_frames", [])),
        },
        audit={
            "authority_boundary": "continuous image plane is a non-authority observer artifact replayed from spectral camera samples",
        },
    )


def _check_spatial_camera_summary_contract(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    for frame in loaded_session.get("projection_frames", []):
        frame_id = str(_frame_value(frame, "frame_id", ""))
        camera_frame = _spectral_frame_payload(frame).get("spectral_camera_frame")
        if not isinstance(camera_frame, dict):
            failures.append({"frame_id": frame_id, "reason": "missing_spectral_camera_frame"})
            continue
        summary = camera_frame.get("spatial_summary")
        if not isinstance(summary, dict):
            failures.append({"frame_id": frame_id, "reason": "missing_spatial_summary"})
            continue
        if summary.get("schema") != "spectral_spatial_summary_v1":
            failures.append({"frame_id": frame_id, "reason": "spatial_summary_schema_mismatch"})
        if summary.get("is_authority_state") is not False:
            failures.append({"frame_id": frame_id, "reason": "spatial_summary_authority_leak"})
        layer_counts = summary.get("layer_counts")
        if not isinstance(layer_counts, dict) or not {"near", "mid", "far"}.issubset(layer_counts):
            failures.append({"frame_id": frame_id, "reason": "spatial_summary_missing_layers"})
        for key in ("mean_depth", "mean_attenuation", "mean_spatial_edge_strength", "mean_occlusion", "max_occlusion"):
            value = float(summary.get(key, -1.0))
            if value < 0.0 or value > 1.0:
                failures.append({"frame_id": frame_id, "reason": f"spatial_summary_{key}_out_of_range"})
        if not summary.get("source_record_ids"):
            failures.append({"frame_id": frame_id, "reason": "spatial_summary_missing_source_record_ids"})
    return _completion_check(
        "spatial_camera_summary_contract",
        not failures,
        {"failures": failures[:20], "projection_frame_count": len(loaded_session.get("projection_frames", []))},
    )


def _check_spatial_image_rendering_contract(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    for frame in loaded_session.get("projection_frames", []):
        frame_id = str(_frame_value(frame, "frame_id", ""))
        payload = _spectral_frame_payload(frame)
        image_plane = payload.get("spectral_image_plane")
        camera_frame = payload.get("spectral_camera_frame")
        if not isinstance(image_plane, dict) or not isinstance(camera_frame, dict):
            failures.append({"frame_id": frame_id, "reason": "missing_image_plane_or_camera_frame"})
            continue
        spatial_rendering = image_plane.get("spatial_rendering")
        if not isinstance(spatial_rendering, dict):
            failures.append({"frame_id": frame_id, "reason": "missing_spatial_rendering"})
            continue
        if spatial_rendering.get("schema") != "spectral_spatial_image_rendering_v1":
            failures.append({"frame_id": frame_id, "reason": "spatial_rendering_schema_mismatch"})
        if spatial_rendering.get("is_authority_state") is not False:
            failures.append({"frame_id": frame_id, "reason": "spatial_rendering_authority_leak"})
        if spatial_rendering.get("source_spectral_camera_frame_id") != camera_frame.get("frame_id"):
            failures.append({"frame_id": frame_id, "reason": "spatial_rendering_camera_source_mismatch"})
        for key in (
            "depth_contrast_score",
            "edge_visibility_score",
            "attenuation_variation_score",
            "mean_attenuation_factor",
            "mean_visibility_transmittance",
            "mean_occlusion",
            "max_occlusion",
        ):
            value = float(spatial_rendering.get(key, -1.0))
            if value < 0.0 or value > 1.0:
                failures.append({"frame_id": frame_id, "reason": f"spatial_rendering_{key}_out_of_range"})
    return _completion_check(
        "spatial_image_rendering_contract",
        not failures,
        {"failures": failures[:20], "projection_frame_count": len(loaded_session.get("projection_frames", []))},
    )


def evaluate_spatial_field_room_completion(loaded_session: dict[str, Any]) -> CompletionReport:
    checks = [
        _check_continuous_spectral_image_plane_contract(loaded_session),
        _check_continuous_spectral_camera_readback_replay(loaded_session),
        _check_continuous_spectral_image_plane_replay(loaded_session),
        _check_spatial_camera_summary_contract(loaded_session),
        _check_spatial_image_rendering_contract(loaded_session),
    ]
    overall_status = "passed" if all(check.status == "passed" for check in checks) else "failed"
    return CompletionReport(
        overall_status=overall_status,
        checks=checks,
        summary={
            "spatial_field_room_completion": overall_status,
            "projection_frame_count": len(loaded_session.get("projection_frames", [])),
        },
        audit={
            "authority_boundary": "spatial cues are non-authority observer artifacts replayed from field and property read-back records",
        },
    )


def _check_occlusion_trace_contract(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    forbidden_keys = {
        "world_xy",
        "grid_xy",
        "support_grid",
        "image_bounds",
        "css_color",
        "viewer_color",
        "field_channel_label",
        "material_color_name",
    }
    for frame in loaded_session.get("projection_frames", []):
        frame_id = str(_frame_value(frame, "frame_id", ""))
        camera_frame = _spectral_frame_payload(frame).get("spectral_camera_frame", {})
        if not isinstance(camera_frame, dict):
            failures.append({"frame_id": frame_id, "reason": "missing_spectral_camera_frame"})
            continue
        for index, sample in enumerate(camera_frame.get("samples", [])):
            trace = sample.get("occlusion_trace")
            if not isinstance(trace, dict):
                failures.append({"frame_id": frame_id, "sample_index": index, "reason": "missing_occlusion_trace"})
                continue
            if trace.get("schema") != "spectral_occlusion_trace_v1":
                failures.append({"frame_id": frame_id, "sample_index": index, "reason": "occlusion_trace_schema_mismatch"})
            if trace.get("is_authority_state") is not False:
                failures.append({"frame_id": frame_id, "sample_index": index, "reason": "occlusion_trace_authority_leak"})
            if not trace.get("source_record_ids"):
                failures.append({"frame_id": frame_id, "sample_index": index, "reason": "occlusion_trace_missing_source_record_ids"})
            for key in ("visibility_transmittance", "first_surface_depth", "occluded_energy_estimate"):
                value = float(trace.get(key, -1.0))
                if value < 0.0 or value > 1.0:
                    failures.append(
                        {"frame_id": frame_id, "sample_index": index, "reason": f"occlusion_trace_{key}_out_of_range"}
                    )
            leaked = sorted(forbidden_keys.intersection(trace.keys()))
            if leaked:
                failures.append(
                    {"frame_id": frame_id, "sample_index": index, "reason": "occlusion_trace_forbidden_keys", "keys": leaked}
                )
    return _completion_check(
        "occlusion_trace_contract",
        not failures,
        {"failures": failures[:20], "projection_frame_count": len(loaded_session.get("projection_frames", []))},
    )


def _check_camera_path_continuity(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    frames_by_observer: dict[str, list[Any]] = {}
    for frame in loaded_session.get("projection_frames", []):
        frames_by_observer.setdefault(str(_frame_value(frame, "observer_id", "")), []).append(frame)
    for observer_id, frames in frames_by_observer.items():
        ordered = sorted(frames, key=lambda item: int(_frame_value(item, "tick", 0)))
        previous_position: list[float] | None = None
        previous_tick: int | None = None
        for frame in ordered:
            frame_id = str(_frame_value(frame, "frame_id", ""))
            tick = int(_frame_value(frame, "tick", 0))
            camera = _spectral_frame_payload(frame).get("spectral_camera_frame", {})
            pose = camera.get("observer_pose", {}) if isinstance(camera, dict) else {}
            position = pose.get("position_world") if isinstance(pose, dict) else None
            if not isinstance(position, list) or len(position) != 3:
                failures.append({"observer_id": observer_id, "frame_id": frame_id, "reason": "missing_position_world"})
                continue
            current_position = [float(value) for value in position]
            if previous_position is not None:
                distance = sum((current_position[index] - previous_position[index]) ** 2 for index in range(3)) ** 0.5
                tick_delta = max(1, tick - int(previous_tick or tick))
                if distance / tick_delta > 12.0:
                    failures.append(
                        {
                            "observer_id": observer_id,
                            "frame_id": frame_id,
                            "reason": "camera_path_jump",
                            "distance": distance,
                            "tick_delta": tick_delta,
                        }
                    )
            previous_position = current_position
            previous_tick = tick
    return _completion_check(
        "camera_path_continuity",
        not failures,
        {"failures": failures[:20], "observer_count": len(frames_by_observer)},
    )


def evaluate_occlusion_camera_path_completion(loaded_session: dict[str, Any]) -> CompletionReport:
    checks = [
        _check_continuous_spectral_image_plane_contract(loaded_session),
        _check_continuous_spectral_camera_readback_replay(loaded_session),
        _check_continuous_spectral_image_plane_replay(loaded_session),
        _check_spatial_camera_summary_contract(loaded_session),
        _check_spatial_image_rendering_contract(loaded_session),
        _check_occlusion_trace_contract(loaded_session),
        _check_camera_path_continuity(loaded_session),
    ]
    overall_status = "passed" if all(check.status == "passed" for check in checks) else "failed"
    return CompletionReport(
        overall_status=overall_status,
        checks=checks,
        summary={
            "occlusion_camera_path_completion": overall_status,
            "projection_frame_count": len(loaded_session.get("projection_frames", [])),
        },
        audit={
            "authority_boundary": "occlusion and camera path are non-authority observer artifacts replayed from field and property read-back records",
        },
    )


GOAL_DIRECTED_CASE_TYPES = {"damping_goal", "channel_goal", "source_goal", "combined_goal"}


def _goal_records(loaded_session: dict[str, Any]) -> list[dict[str, Any]]:
    return [_spectral_as_dict(item) for item in loaded_session.get("goals", [])]


def _field_play_progress_records(loaded_session: dict[str, Any]) -> list[dict[str, Any]]:
    return [_spectral_as_dict(item) for item in loaded_session.get("field_play_progress_records", [])]


def _field_play_progress_payloads(frame: Any) -> list[dict[str, Any]]:
    payload = _spectral_frame_payload(frame)
    values = payload.get("field_play_progress", [])
    if not isinstance(values, list):
        return []
    return [dict(value) for value in values if isinstance(value, dict)]


def _check_field_play_goal_contract(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    goals = _goal_records(loaded_session)
    progress_records = _field_play_progress_records(loaded_session)
    goals_by_id = {str(goal.get("goal_id")): goal for goal in goals}
    if not goals:
        failures.append({"reason": "missing_goals"})
    for goal in goals:
        try:
            validate_field_play_goal(goal)
        except ValueError as exc:
            failures.append({"goal_id": goal.get("goal_id"), "reason": "invalid_goal", "message": str(exc)})
    if not progress_records:
        failures.append({"reason": "missing_field_play_progress_records"})
    for progress in progress_records:
        goal = goals_by_id.get(str(progress.get("goal_id")))
        if goal is None:
            failures.append({"progress_id": progress.get("progress_id"), "reason": "missing_goal_for_progress"})
            continue
        try:
            validate_field_play_progress(progress, goal)
        except ValueError as exc:
            failures.append({"progress_id": progress.get("progress_id"), "reason": "invalid_progress", "message": str(exc)})
    return _completion_check(
        "field_play_goal_contract",
        not failures,
        {"goal_count": len(goals), "progress_count": len(progress_records), "failures": failures[:20]},
    )


def _check_field_play_progress_replay(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    goals = _goal_records(loaded_session)
    progress_by_goal_id = {
        str(record.get("goal_id")): record
        for record in _field_play_progress_records(loaded_session)
    }
    consequence_records = [_spectral_as_dict(item) for item in loaded_session.get("playable_consequence_records", [])]
    frames = [_spectral_as_dict(item) for item in loaded_session.get("projection_frames", [])]
    baseline_by_case = loaded_session.get("baseline_projection_frames_by_case_id", {})
    if not isinstance(baseline_by_case, dict):
        baseline_by_case = {}
    if not goals:
        failures.append({"reason": "missing_goals"})
    for goal in goals:
        goal_id = str(goal.get("goal_id", ""))
        stored = progress_by_goal_id.get(goal_id)
        if stored is None:
            failures.append({"goal_id": goal_id, "reason": "missing_top_level_progress"})
            continue
        baseline_case_id = str(goal.get("baseline_case_id", ""))
        baseline_frames = baseline_by_case.get(baseline_case_id, [])
        if not isinstance(baseline_frames, list) or not baseline_frames:
            failures.append({"goal_id": goal_id, "reason": "missing_baseline_projection_frames", "baseline_case_id": baseline_case_id})
            continue
        try:
            replayed = evaluate_field_play_progress(
                goal=goal,
                consequence_records=consequence_records,
                projection_frames=frames,
                baseline_projection_frames=[_spectral_as_dict(frame) for frame in baseline_frames],
            )
        except Exception as exc:  # noqa: BLE001 - completion reports replay failure as data.
            failures.append({"goal_id": goal_id, "reason": "progress_replay_error", "message": str(exc)})
            continue
        mismatches = [
            key
            for key in (
                "status",
                "matched_consequence_ids",
                "matched_tool_kinds",
                "matched_projection_frame_ids",
                "matched_spectral_camera_frame_ids",
                "matched_spectral_image_plane_digests",
                "baseline_case_id",
                "visible_delta",
                "missing_requirements",
            )
            if stored.get(key) != replayed.get(key)
        ]
        if mismatches:
            failures.append({"goal_id": goal_id, "reason": "progress_replay_mismatch", "mismatches": mismatches})
        if replayed.get("status") != "achieved":
            failures.append({"goal_id": goal_id, "reason": "goal_not_achieved", "missing": replayed.get("missing_requirements", [])})
    return _completion_check(
        "field_play_progress_replay",
        not failures,
        {"goal_count": len(goals), "failures": failures[:20]},
    )


def _check_goal_projection_replayability(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    progress_records = _field_play_progress_records(loaded_session)
    if not progress_records:
        failures.append({"reason": "missing_top_level_progress_records"})
    payloads_by_progress_id: dict[str, list[dict[str, Any]]] = {}
    for frame in loaded_session.get("projection_frames", []):
        frame_id = str(_frame_value(frame, "frame_id", ""))
        payload = _spectral_frame_payload(frame)
        if payload.get("field_play_progress") and not payload.get("field_play_progress_ids"):
            failures.append({"frame_id": frame_id, "reason": "progress_payload_missing_progress_ids"})
        for payload_progress in _field_play_progress_payloads(frame):
            payloads_by_progress_id.setdefault(str(payload_progress.get("progress_id", "")), []).append(payload_progress)
    for progress in progress_records:
        progress_id = str(progress.get("progress_id", ""))
        payloads = payloads_by_progress_id.get(progress_id, [])
        if not payloads:
            failures.append({"progress_id": progress_id, "reason": "progress_missing_from_projection_payload"})
            continue
        for payload_progress in payloads:
            for key in ("goal_id", "status", "matched_consequence_ids", "matched_tool_kinds", "visible_delta"):
                if payload_progress.get(key) != progress.get(key):
                    failures.append({"progress_id": progress_id, "reason": "projection_progress_mismatch", "key": key})
            if not payload_progress.get("source_record_ids"):
                failures.append({"progress_id": progress_id, "reason": "projection_progress_missing_source_record_ids"})
        if not progress.get("matched_spectral_image_plane_digests"):
            failures.append({"progress_id": progress_id, "reason": "progress_missing_image_plane_digests"})
    return _completion_check(
        "goal_projection_replayability",
        not failures,
        {"progress_count": len(progress_records), "payload_progress_count": sum(len(values) for values in payloads_by_progress_id.values()), "failures": failures[:20]},
    )


def _check_goal_case_matrix(loaded_session: dict[str, Any]) -> CompletionCheck:
    report = loaded_session.get("report", {})
    failures: list[dict[str, Any]] = []
    if not isinstance(report, dict):
        return _completion_check("goal_case_matrix", False, {"failures": [{"reason": "missing_report"}]})
    if report.get("scope") == "case":
        case_type = str(report.get("case_type", ""))
        if case_type not in GOAL_DIRECTED_CASE_TYPES:
            failures.append({"reason": "invalid_case_type", "case_type": case_type})
        if not report.get("viewer_smoke_case_dir"):
            failures.append({"reason": "missing_viewer_smoke_case_dir"})
        return _completion_check(
            "goal_case_matrix",
            not failures,
            {"scope": "case", "case_type": case_type, "failures": failures[:20]},
        )
    source_package_count = int(report.get("source_package_count", 0))
    expected_case_count = int(report.get("expected_case_count", 0))
    case_count = int(report.get("case_count", 0))
    if expected_case_count != source_package_count * len(GOAL_DIRECTED_CASE_TYPES):
        failures.append({"reason": "expected_case_count_mismatch", "source_package_count": source_package_count, "expected_case_count": expected_case_count})
    if case_count != expected_case_count:
        failures.append({"reason": "case_count_mismatch", "case_count": case_count, "expected_case_count": expected_case_count})
    per_package_status = report.get("per_package_status")
    if not isinstance(per_package_status, dict) or not per_package_status:
        failures.append({"reason": "missing_per_package_status"})
    else:
        for package_name, statuses in per_package_status.items():
            if not isinstance(statuses, dict):
                failures.append({"package": package_name, "reason": "invalid_package_status"})
                continue
            missing = sorted(GOAL_DIRECTED_CASE_TYPES - set(statuses))
            failed = sorted(case_type for case_type, status in statuses.items() if status != "passed")
            if missing:
                failures.append({"package": package_name, "reason": "missing_case_types", "case_types": missing})
            if failed:
                failures.append({"package": package_name, "reason": "failed_case_types", "case_types": failed})
    if not report.get("viewer_smoke_case_dir"):
        failures.append({"reason": "missing_viewer_smoke_case_dir"})
    return _completion_check(
        "goal_case_matrix",
        not failures,
        {"failures": failures[:20], "source_package_count": source_package_count, "case_count": case_count, "expected_case_count": expected_case_count},
    )


def evaluate_goal_directed_play_loop_completion(loaded_session: dict[str, Any]) -> CompletionReport:
    checks = [
        _check_field_play_goal_contract(loaded_session),
        _check_field_play_progress_replay(loaded_session),
        _check_goal_projection_replayability(loaded_session),
        _check_goal_case_matrix(loaded_session),
    ]
    overall_status = "passed" if all(check.status == "passed" for check in checks) else "failed"
    return CompletionReport(
        overall_status=overall_status,
        checks=checks,
        summary={
            "goal_directed_play_loop_completion": overall_status,
            "goal_count": len(loaded_session.get("goals", [])),
            "field_play_progress_count": len(loaded_session.get("field_play_progress_records", [])),
        },
        audit={
            "authority_boundary": "goals are non-authority scenario contracts; progress is replayed from consequence records and spectral image artifacts",
        },
    )


TOOL_PROGRESSION_CASE_TYPES = {
    "costed_damping_loop",
    "cooldown_block_loop",
    "overload_risk_loop",
    "unlock_channel_loop",
    "combined_progression_loop",
}


def _field_play_initial_state(loaded_session: dict[str, Any]) -> dict[str, Any]:
    value = loaded_session.get("field_play_initial_state", {})
    return _spectral_as_dict(value) if isinstance(value, dict) else {}


def _tool_profiles(loaded_session: dict[str, Any]) -> list[dict[str, Any]]:
    return [_spectral_as_dict(item) for item in loaded_session.get("tool_profiles", [])]


def _field_tool_use_records(loaded_session: dict[str, Any]) -> list[dict[str, Any]]:
    return [_spectral_as_dict(item) for item in loaded_session.get("field_tool_use_records", [])]


def _field_play_feedback_records(loaded_session: dict[str, Any]) -> list[dict[str, Any]]:
    return [_spectral_as_dict(item) for item in loaded_session.get("field_play_feedback_records", [])]


def _field_play_loop_states(loaded_session: dict[str, Any]) -> list[dict[str, Any]]:
    return [_spectral_as_dict(item) for item in loaded_session.get("field_play_loop_states", [])]


def _field_play_loop_state_payloads(frame: Any) -> list[dict[str, Any]]:
    payload = _spectral_frame_payload(frame)
    values = payload.get("field_play_loop_state", [])
    if not isinstance(values, list):
        return []
    return [dict(value) for value in values if isinstance(value, dict)]


def _check_initial_loop_state_contract(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    initial_state = _field_play_initial_state(loaded_session)
    if not initial_state:
        failures.append({"reason": "missing_field_play_initial_state"})
    else:
        try:
            validate_field_play_initial_state(initial_state)
        except ValueError as exc:
            failures.append({"reason": "invalid_field_play_initial_state", "message": str(exc)})
    return _completion_check("initial_loop_state_contract", not failures, {"failures": failures[:20]})


def _check_tool_profile_contract(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    profiles = _tool_profiles(loaded_session)
    if not profiles:
        failures.append({"reason": "missing_tool_profiles"})
    for profile in profiles:
        try:
            validate_field_tool_profile(profile)
        except ValueError as exc:
            failures.append({"tool_id": profile.get("tool_id"), "reason": "invalid_tool_profile", "message": str(exc)})
    return _completion_check("tool_profile_contract", not failures, {"profile_count": len(profiles), "failures": failures[:20]})


def _check_tool_use_ledger_replay(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    initial_state = _field_play_initial_state(loaded_session)
    profiles = _tool_profiles(loaded_session)
    tool_use_records = _field_tool_use_records(loaded_session)
    feedback_records = _field_play_feedback_records(loaded_session)
    if not tool_use_records:
        failures.append({"reason": "missing_field_tool_use_records"})
    for record in tool_use_records:
        try:
            validate_field_tool_use_record(record)
        except ValueError as exc:
            failures.append({"tool_use_id": record.get("tool_use_id"), "reason": "invalid_tool_use_record", "message": str(exc)})
    rejected_tool_use_ids = {
        str(record.get("tool_use_id"))
        for record in tool_use_records
        if record.get("status") == "rejected"
    }
    rejected_requested_command_ids = {
        str(record.get("requested_command_id"))
        for record in tool_use_records
        if record.get("status") == "rejected" and record.get("requested_command_id")
    }
    for consequence in loaded_session.get("playable_consequence_records", []):
        consequence_dict = _spectral_as_dict(consequence)
        source_record_ids = {str(value) for value in consequence_dict.get("source_record_ids", [])}
        source_command_ids = {str(value) for value in consequence_dict.get("source_command_ids", [])}
        if rejected_tool_use_ids & source_record_ids:
            failures.append({"consequence_id": consequence_dict.get("consequence_id"), "reason": "consequence_references_rejected_tool_use"})
        if rejected_requested_command_ids & source_command_ids:
            failures.append({"consequence_id": consequence_dict.get("consequence_id"), "reason": "consequence_references_rejected_command"})
    if initial_state and tool_use_records:
        replay_tick = max([int(record.get("tick", 0)) for record in tool_use_records] + [int(initial_state.get("tick", 0))])
        try:
            replay_field_play_loop_state(
                case_id=str(initial_state.get("case_id", "")),
                tick=replay_tick,
                initial_state=initial_state,
                tool_profiles=profiles,
                tool_use_records=tool_use_records,
                feedback_records=feedback_records,
            )
        except Exception as exc:  # noqa: BLE001 - completion reports replay failure as data.
            failures.append({"reason": "tool_use_ledger_replay_error", "message": str(exc)})
    return _completion_check(
        "tool_use_ledger_replay",
        not failures,
        {"tool_use_count": len(tool_use_records), "failures": failures[:20]},
    )


def _check_feedback_field_binding(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    feedback_records = _field_play_feedback_records(loaded_session)
    tool_use_ids = {str(record.get("tool_use_id")) for record in _field_tool_use_records(loaded_session)}
    consequence_ids = {
        str(_spectral_as_dict(record).get("consequence_id"))
        for record in loaded_session.get("playable_consequence_records", [])
    }
    frames = [_spectral_as_dict(frame) for frame in loaded_session.get("projection_frames", [])]
    frame_ids = {str(frame.get("frame_id")) for frame in frames}
    camera_frame_ids: set[str] = set()
    image_digests: set[str] = set()
    for frame in frames:
        payload = _spectral_frame_payload(frame)
        camera = payload.get("spectral_camera_frame")
        if isinstance(camera, dict) and camera.get("frame_id"):
            camera_frame_ids.add(str(camera["frame_id"]))
        image_plane = payload.get("spectral_image_plane")
        if isinstance(image_plane, dict) and image_plane.get("image_digest"):
            image_digests.add(str(image_plane["image_digest"]))
    baseline_by_case = loaded_session.get("baseline_projection_frames_by_case_id", {})
    if not isinstance(baseline_by_case, dict):
        baseline_by_case = {}
    if not feedback_records:
        failures.append({"reason": "missing_field_play_feedback_records"})
    for feedback in feedback_records:
        feedback_id = str(feedback.get("feedback_id", ""))
        try:
            validate_field_play_feedback(feedback)
        except ValueError as exc:
            failures.append({"feedback_id": feedback_id, "reason": "invalid_feedback", "message": str(exc)})
            continue
        missing_tool_uses = set(feedback.get("source_tool_use_ids", [])) - tool_use_ids
        if missing_tool_uses:
            failures.append({"feedback_id": feedback_id, "reason": "missing_source_tool_uses", "ids": sorted(missing_tool_uses)})
        if feedback.get("kind") == "blocked":
            continue
        missing_consequences = set(feedback.get("source_consequence_ids", [])) - consequence_ids
        missing_frames = set(feedback.get("source_projection_frame_ids", [])) - frame_ids
        missing_camera_frames = set(feedback.get("source_spectral_camera_frame_ids", [])) - camera_frame_ids
        missing_digests = set(feedback.get("source_spectral_image_plane_digests", [])) - image_digests
        baseline_case_id = str(feedback.get("baseline_case_id", ""))
        if missing_consequences:
            failures.append({"feedback_id": feedback_id, "reason": "missing_source_consequences", "ids": sorted(missing_consequences)})
        if missing_frames:
            failures.append({"feedback_id": feedback_id, "reason": "missing_source_projection_frames", "ids": sorted(missing_frames)})
        if missing_camera_frames:
            failures.append({"feedback_id": feedback_id, "reason": "missing_source_spectral_camera_frames", "ids": sorted(missing_camera_frames)})
        if missing_digests:
            failures.append({"feedback_id": feedback_id, "reason": "missing_source_image_digests", "ids": sorted(missing_digests)})
        if baseline_case_id not in baseline_by_case:
            failures.append({"feedback_id": feedback_id, "reason": "missing_feedback_baseline", "baseline_case_id": baseline_case_id})
    return _completion_check(
        "feedback_field_binding",
        not failures,
        {"feedback_count": len(feedback_records), "failures": failures[:20]},
    )


def _close_enough(left: Any, right: Any) -> bool:
    if isinstance(left, float) or isinstance(right, float):
        return abs(float(left) - float(right)) <= 0.000001
    return left == right


def _check_loop_state_replay(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    initial_state = _field_play_initial_state(loaded_session)
    profiles = _tool_profiles(loaded_session)
    tool_use_records = _field_tool_use_records(loaded_session)
    feedback_records = _field_play_feedback_records(loaded_session)
    loop_states = _field_play_loop_states(loaded_session)
    if not loop_states:
        failures.append({"reason": "missing_field_play_loop_states"})
    for state in loop_states:
        state_id = str(state.get("loop_state_id", ""))
        try:
            validate_field_play_loop_state(state)
        except ValueError as exc:
            failures.append({"loop_state_id": state_id, "reason": "invalid_loop_state", "message": str(exc)})
            continue
        try:
            replayed = replay_field_play_loop_state(
                case_id=str(state.get("case_id", "")),
                tick=int(state.get("tick", 0)),
                initial_state=initial_state,
                tool_profiles=profiles,
                tool_use_records=tool_use_records,
                feedback_records=feedback_records,
            )
        except Exception as exc:  # noqa: BLE001 - completion reports replay failure as data.
            failures.append({"loop_state_id": state_id, "reason": "loop_state_replay_error", "message": str(exc)})
            continue
        for key in (
            "tool_energy",
            "risk_level",
            "score",
            "cooldowns",
            "unlocked_tool_ids",
            "accepted_tool_use_ids",
            "rejected_tool_use_ids",
            "feedback_ids",
        ):
            if not _close_enough(state.get(key), replayed.get(key)):
                failures.append({"loop_state_id": state_id, "reason": "loop_state_replay_mismatch", "key": key})
    return _completion_check(
        "loop_state_replay",
        not failures,
        {"loop_state_count": len(loop_states), "failures": failures[:20]},
    )


def _check_loop_projection_replayability(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    states_by_id = {str(state.get("loop_state_id")): state for state in _field_play_loop_states(loaded_session)}
    payload_count = 0
    if not states_by_id:
        failures.append({"reason": "missing_top_level_loop_states"})
    for frame in loaded_session.get("projection_frames", []):
        frame_id = str(_frame_value(frame, "frame_id", ""))
        frame_tick = int(_frame_value(frame, "tick", 0))
        payload = _spectral_frame_payload(frame)
        if payload.get("field_play_loop_state") and not payload.get("field_play_loop_state_ids"):
            failures.append({"frame_id": frame_id, "reason": "loop_state_payload_missing_ids"})
        for payload_state in _field_play_loop_state_payloads(frame):
            payload_count += 1
            state_id = str(payload_state.get("loop_state_id", ""))
            top_level = states_by_id.get(state_id)
            if top_level is None:
                failures.append({"frame_id": frame_id, "loop_state_id": state_id, "reason": "payload_loop_state_missing_top_level_state"})
                continue
            if int(payload_state.get("tick", 0)) > frame_tick:
                failures.append({"frame_id": frame_id, "loop_state_id": state_id, "reason": "payload_loop_state_from_future"})
            for key in ("tool_energy", "risk_level", "score", "cooldowns", "unlocked_tool_ids"):
                if not _close_enough(payload_state.get(key), top_level.get(key)):
                    failures.append({"frame_id": frame_id, "loop_state_id": state_id, "reason": "payload_loop_state_mismatch", "key": key})
            if not payload_state.get("source_record_ids"):
                failures.append({"frame_id": frame_id, "loop_state_id": state_id, "reason": "payload_loop_state_missing_source_records"})
    if payload_count == 0:
        failures.append({"reason": "missing_projection_loop_state_payloads"})
    return _completion_check(
        "loop_projection_replayability",
        not failures,
        {"payload_count": payload_count, "failures": failures[:20]},
    )


def _check_tool_progression_case_matrix(loaded_session: dict[str, Any]) -> CompletionCheck:
    report = loaded_session.get("report", {})
    failures: list[dict[str, Any]] = []
    if not isinstance(report, dict):
        return _completion_check("tool_progression_case_matrix", False, {"failures": [{"reason": "missing_report"}]})
    if report.get("scope") == "case":
        case_type = str(report.get("case_type", ""))
        if case_type not in TOOL_PROGRESSION_CASE_TYPES:
            failures.append({"reason": "invalid_case_type", "case_type": case_type})
        if not report.get("viewer_smoke_case_dir"):
            failures.append({"reason": "missing_viewer_smoke_case_dir"})
        return _completion_check(
            "tool_progression_case_matrix",
            not failures,
            {"scope": "case", "case_type": case_type, "failures": failures[:20]},
        )
    source_package_count = int(report.get("source_package_count", 0))
    expected_case_count = int(report.get("expected_case_count", 0))
    case_count = int(report.get("case_count", 0))
    if expected_case_count != source_package_count * len(TOOL_PROGRESSION_CASE_TYPES):
        failures.append({"reason": "expected_case_count_mismatch", "source_package_count": source_package_count, "expected_case_count": expected_case_count})
    if case_count != expected_case_count:
        failures.append({"reason": "case_count_mismatch", "case_count": case_count, "expected_case_count": expected_case_count})
    per_package_status = report.get("per_package_status")
    if not isinstance(per_package_status, dict) or not per_package_status:
        failures.append({"reason": "missing_per_package_status"})
    else:
        for package_name, statuses in per_package_status.items():
            if not isinstance(statuses, dict):
                failures.append({"package": package_name, "reason": "invalid_package_status"})
                continue
            missing = sorted(TOOL_PROGRESSION_CASE_TYPES - set(statuses))
            failed = sorted(case_type for case_type, status in statuses.items() if status != "passed")
            if missing:
                failures.append({"package": package_name, "reason": "missing_case_types", "case_types": missing})
            if failed:
                failures.append({"package": package_name, "reason": "failed_case_types", "case_types": failed})
    if not report.get("viewer_smoke_case_dir"):
        failures.append({"reason": "missing_viewer_smoke_case_dir"})
    return _completion_check(
        "tool_progression_case_matrix",
        not failures,
        {"failures": failures[:20], "source_package_count": source_package_count, "case_count": case_count, "expected_case_count": expected_case_count},
    )


def evaluate_tool_progression_play_loop_completion(loaded_session: dict[str, Any]) -> CompletionReport:
    checks = [
        _check_initial_loop_state_contract(loaded_session),
        _check_tool_profile_contract(loaded_session),
        _check_tool_use_ledger_replay(loaded_session),
        _check_feedback_field_binding(loaded_session),
        _check_loop_state_replay(loaded_session),
        _check_loop_projection_replayability(loaded_session),
        _check_field_play_goal_contract(loaded_session),
        _check_field_play_progress_replay(loaded_session),
        _check_goal_projection_replayability(loaded_session),
        _check_tool_progression_case_matrix(loaded_session),
    ]
    overall_status = "passed" if all(check.status == "passed" for check in checks) else "failed"
    return CompletionReport(
        overall_status=overall_status,
        checks=checks,
        summary={
            "tool_progression_play_loop_completion": overall_status,
            "tool_profile_count": len(loaded_session.get("tool_profiles", [])),
            "field_tool_use_count": len(loaded_session.get("field_tool_use_records", [])),
            "field_play_feedback_count": len(loaded_session.get("field_play_feedback_records", [])),
            "field_play_loop_state_count": len(loaded_session.get("field_play_loop_states", [])),
        },
        audit={
            "authority_boundary": "tool progression state is replayed scenario state; field consequences and spectral images remain the evidence chain",
        },
    )


FIELD_AUTHORED_ROUTE_CASE_TYPES = {
    "barrier_to_channel_route",
    "emitter_unlock_route",
    "blocked_locked_route",
    "combined_exploration_route",
}


def _route_nodes(loaded_session: dict[str, Any]) -> list[dict[str, Any]]:
    return [_spectral_as_dict(item) for item in loaded_session.get("route_nodes", [])]


def _route_edges(loaded_session: dict[str, Any]) -> list[dict[str, Any]]:
    return [_spectral_as_dict(item) for item in loaded_session.get("route_edges", [])]


def _route_step_records(loaded_session: dict[str, Any]) -> list[dict[str, Any]]:
    return [_spectral_as_dict(item) for item in loaded_session.get("route_step_records", [])]


def _field_exploration_states(loaded_session: dict[str, Any]) -> list[dict[str, Any]]:
    return [_spectral_as_dict(item) for item in loaded_session.get("field_exploration_states", [])]


def _field_exploration_state_payloads(frame: Any) -> list[dict[str, Any]]:
    payload = _spectral_frame_payload(frame)
    values = payload.get("field_exploration_state", [])
    if not isinstance(values, list):
        return []
    return [dict(value) for value in values if isinstance(value, dict)]


def _field_signature_instance_ids(loaded_session: dict[str, Any]) -> set[str]:
    return {
        str(instance.get("instance_id") or instance.get("id") or instance.get("record_id"))
        for instance in loaded_session.get("field_signature_instances", [])
        if instance.get("instance_id") or instance.get("id") or instance.get("record_id")
    }


def _check_field_route_graph_contract(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    nodes = _route_nodes(loaded_session)
    edges = _route_edges(loaded_session)
    signature_ids = _field_signature_instance_ids(loaded_session)
    node_ids = {str(node.get("node_id")) for node in nodes}
    if not nodes:
        failures.append({"reason": "missing_route_nodes"})
    if not edges:
        failures.append({"reason": "missing_route_edges"})
    for node in nodes:
        try:
            validate_field_route_node(node)
        except ValueError as exc:
            failures.append({"node_id": node.get("node_id"), "reason": "invalid_route_node", "message": str(exc)})
            continue
        missing_signatures = set(node.get("field_signature_instance_ids", [])) - signature_ids
        if missing_signatures:
            failures.append({"node_id": node.get("node_id"), "reason": "missing_node_signature_instances", "ids": sorted(missing_signatures)})
    for edge in edges:
        try:
            validate_field_route_edge(edge)
        except ValueError as exc:
            failures.append({"edge_id": edge.get("edge_id"), "reason": "invalid_route_edge", "message": str(exc)})
            continue
        if edge.get("from_node_id") not in node_ids or edge.get("to_node_id") not in node_ids:
            failures.append({"edge_id": edge.get("edge_id"), "reason": "edge_references_missing_node"})
        missing_signatures = set(edge.get("required_signature_instance_ids", [])) - signature_ids
        if missing_signatures:
            failures.append({"edge_id": edge.get("edge_id"), "reason": "missing_edge_signature_instances", "ids": sorted(missing_signatures)})
    return _completion_check(
        "field_route_graph_contract",
        not failures,
        {"route_node_count": len(nodes), "route_edge_count": len(edges), "failures": failures[:20]},
    )


def _check_field_route_step_binding(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    steps = _route_step_records(loaded_session)
    progress_ids = {str(record.get("progress_id")) for record in _field_play_progress_records(loaded_session)}
    feedback_ids = {str(record.get("feedback_id")) for record in _field_play_feedback_records(loaded_session)}
    signature_ids = _field_signature_instance_ids(loaded_session)
    frames = [_spectral_as_dict(frame) for frame in loaded_session.get("projection_frames", [])]
    frame_ids = {str(frame.get("frame_id")) for frame in frames}
    camera_frame_ids: set[str] = set()
    image_digests: set[str] = set()
    for frame in frames:
        payload = _spectral_frame_payload(frame)
        camera = payload.get("spectral_camera_frame")
        if isinstance(camera, dict) and camera.get("frame_id"):
            camera_frame_ids.add(str(camera["frame_id"]))
        image_plane = payload.get("spectral_image_plane")
        if isinstance(image_plane, dict) and image_plane.get("image_digest"):
            image_digests.add(str(image_plane["image_digest"]))
    baseline_by_case = loaded_session.get("baseline_projection_frames_by_case_id", {})
    if not isinstance(baseline_by_case, dict):
        baseline_by_case = {}
    if not steps:
        failures.append({"reason": "missing_route_step_records"})
    if steps and not any(step.get("status") == "accepted" for step in steps):
        failures.append({"reason": "missing_accepted_route_step"})
    for step in steps:
        step_id = str(step.get("route_step_id", ""))
        try:
            validate_field_route_step_record(step)
        except ValueError as exc:
            failures.append({"route_step_id": step_id, "reason": "invalid_route_step", "message": str(exc)})
            continue
        if step.get("status") == "rejected":
            continue
        missing_progress = set(step.get("source_progress_ids", [])) - progress_ids
        missing_feedback = set(step.get("source_feedback_ids", [])) - feedback_ids
        missing_signatures = set(step.get("source_signature_instance_ids", [])) - signature_ids
        missing_frames = set(step.get("source_projection_frame_ids", [])) - frame_ids
        missing_camera = set(step.get("source_spectral_camera_frame_ids", [])) - camera_frame_ids
        missing_digests = set(step.get("source_spectral_image_plane_digests", [])) - image_digests
        if missing_progress:
            failures.append({"route_step_id": step_id, "reason": "missing_route_progress", "ids": sorted(missing_progress)})
        if missing_feedback:
            failures.append({"route_step_id": step_id, "reason": "missing_route_feedback", "ids": sorted(missing_feedback)})
        if missing_signatures:
            failures.append({"route_step_id": step_id, "reason": "missing_route_signatures", "ids": sorted(missing_signatures)})
        if missing_frames:
            failures.append({"route_step_id": step_id, "reason": "missing_route_projection_frames", "ids": sorted(missing_frames)})
        if missing_camera:
            failures.append({"route_step_id": step_id, "reason": "missing_route_camera_frames", "ids": sorted(missing_camera)})
        if missing_digests:
            failures.append({"route_step_id": step_id, "reason": "missing_route_image_digests", "ids": sorted(missing_digests)})
        baseline_case_id = str(step.get("baseline_case_id", ""))
        if baseline_case_id not in baseline_by_case:
            failures.append({"route_step_id": step_id, "reason": "missing_route_baseline", "baseline_case_id": baseline_case_id})
    return _completion_check(
        "field_route_step_binding",
        not failures,
        {"route_step_count": len(steps), "failures": failures[:20]},
    )


def _route_initial_and_exit(nodes: list[dict[str, Any]]) -> tuple[str, str]:
    initial = next((str(node.get("node_id")) for node in nodes if node.get("node_kind") == "origin"), "")
    exit_node = next((str(node.get("node_id")) for node in nodes if node.get("node_kind") == "exit"), "")
    if not initial and nodes:
        initial = str(nodes[0].get("node_id"))
    if not exit_node and nodes:
        exit_node = str(nodes[-1].get("node_id"))
    return initial, exit_node


def _check_field_exploration_state_replay(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    nodes = _route_nodes(loaded_session)
    edges = _route_edges(loaded_session)
    steps = _route_step_records(loaded_session)
    states = _field_exploration_states(loaded_session)
    initial_node_id, exit_node_id = _route_initial_and_exit(nodes)
    if not states:
        failures.append({"reason": "missing_field_exploration_states"})
    for state in states:
        state_id = str(state.get("exploration_state_id", ""))
        try:
            validate_field_exploration_state(state)
        except ValueError as exc:
            failures.append({"exploration_state_id": state_id, "reason": "invalid_exploration_state", "message": str(exc)})
            continue
        try:
            replayed = replay_field_exploration_state(
                case_id=str(state.get("case_id", "")),
                tick=int(state.get("tick", 0)),
                initial_node_id=initial_node_id,
                exit_node_id=exit_node_id,
                route_nodes=nodes,
                route_edges=edges,
                route_step_records=steps,
                tool_use_records=_field_tool_use_records(loaded_session),
                progress_records=_field_play_progress_records(loaded_session),
                feedback_records=_field_play_feedback_records(loaded_session),
                signature_instances=[_spectral_as_dict(item) for item in loaded_session.get("field_signature_instances", [])],
            )
        except Exception as exc:  # noqa: BLE001 - completion reports replay failure as data.
            failures.append({"exploration_state_id": state_id, "reason": "exploration_state_replay_error", "message": str(exc)})
            continue
        for key in (
            "current_node_id",
            "visited_node_ids",
            "open_edge_ids",
            "accepted_route_step_ids",
            "rejected_route_step_ids",
            "route_score",
            "completed_route",
        ):
            if not _close_enough(state.get(key), replayed.get(key)):
                failures.append({"exploration_state_id": state_id, "reason": "exploration_state_replay_mismatch", "key": key})
    return _completion_check(
        "field_exploration_state_replay",
        not failures,
        {"exploration_state_count": len(states), "failures": failures[:20]},
    )


def _check_field_route_projection_replayability(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    states_by_id = {str(state.get("exploration_state_id")): state for state in _field_exploration_states(loaded_session)}
    payload_count = 0
    if not states_by_id:
        failures.append({"reason": "missing_top_level_exploration_states"})
    for frame in loaded_session.get("projection_frames", []):
        frame_id = str(_frame_value(frame, "frame_id", ""))
        frame_tick = int(_frame_value(frame, "tick", 0))
        payload = _spectral_frame_payload(frame)
        if payload.get("field_exploration_state") and not payload.get("field_exploration_state_ids"):
            failures.append({"frame_id": frame_id, "reason": "exploration_state_payload_missing_ids"})
        for payload_state in _field_exploration_state_payloads(frame):
            payload_count += 1
            state_id = str(payload_state.get("exploration_state_id", ""))
            top_level = states_by_id.get(state_id)
            if top_level is None:
                failures.append({"frame_id": frame_id, "exploration_state_id": state_id, "reason": "payload_route_state_missing_top_level_state"})
                continue
            if int(payload_state.get("tick", 0)) > frame_tick:
                failures.append({"frame_id": frame_id, "exploration_state_id": state_id, "reason": "payload_route_state_from_future"})
            for key in (
                "current_node_id",
                "visited_node_ids",
                "open_edge_ids",
                "accepted_route_step_ids",
                "rejected_route_step_ids",
                "route_score",
                "completed_route",
            ):
                if not _close_enough(payload_state.get(key), top_level.get(key)):
                    failures.append({"frame_id": frame_id, "exploration_state_id": state_id, "reason": "payload_route_state_mismatch", "key": key})
            if not payload_state.get("source_record_ids"):
                failures.append({"frame_id": frame_id, "exploration_state_id": state_id, "reason": "payload_route_state_missing_source_records"})
    if payload_count == 0:
        failures.append({"reason": "missing_projection_route_state_payloads"})
    return _completion_check(
        "field_route_projection_replayability",
        not failures,
        {"payload_count": payload_count, "failures": failures[:20]},
    )


def _check_field_route_case_matrix(loaded_session: dict[str, Any]) -> CompletionCheck:
    report = loaded_session.get("report", {})
    failures: list[dict[str, Any]] = []
    if not isinstance(report, dict):
        return _completion_check("field_route_case_matrix", False, {"failures": [{"reason": "missing_report"}]})
    if report.get("scope") == "case":
        case_type = str(report.get("case_type", ""))
        if case_type not in FIELD_AUTHORED_ROUTE_CASE_TYPES:
            failures.append({"reason": "invalid_case_type", "case_type": case_type})
        if not report.get("viewer_smoke_case_dir"):
            failures.append({"reason": "missing_viewer_smoke_case_dir"})
        return _completion_check(
            "field_route_case_matrix",
            not failures,
            {"scope": "case", "case_type": case_type, "failures": failures[:20]},
        )
    source_package_count = int(report.get("source_package_count", 0))
    expected_case_count = int(report.get("expected_case_count", 0))
    case_count = int(report.get("case_count", 0))
    if expected_case_count != source_package_count * len(FIELD_AUTHORED_ROUTE_CASE_TYPES):
        failures.append({"reason": "expected_case_count_mismatch", "source_package_count": source_package_count, "expected_case_count": expected_case_count})
    if case_count != expected_case_count:
        failures.append({"reason": "case_count_mismatch", "case_count": case_count, "expected_case_count": expected_case_count})
    per_package_status = report.get("per_package_status")
    if not isinstance(per_package_status, dict) or not per_package_status:
        failures.append({"reason": "missing_per_package_status"})
    else:
        for package_name, statuses in per_package_status.items():
            if not isinstance(statuses, dict):
                failures.append({"package": package_name, "reason": "invalid_package_status"})
                continue
            missing = sorted(FIELD_AUTHORED_ROUTE_CASE_TYPES - set(statuses))
            failed = sorted(case_type for case_type, status in statuses.items() if status != "passed")
            if missing:
                failures.append({"package": package_name, "reason": "missing_case_types", "case_types": missing})
            if failed:
                failures.append({"package": package_name, "reason": "failed_case_types", "case_types": failed})
    if not report.get("viewer_smoke_case_dir"):
        failures.append({"reason": "missing_viewer_smoke_case_dir"})
    return _completion_check(
        "field_route_case_matrix",
        not failures,
        {"failures": failures[:20], "source_package_count": source_package_count, "case_count": case_count, "expected_case_count": expected_case_count},
    )


def evaluate_field_authored_exploration_route_completion(loaded_session: dict[str, Any]) -> CompletionReport:
    checks = [
        _check_field_route_graph_contract(loaded_session),
        _check_field_route_step_binding(loaded_session),
        _check_field_exploration_state_replay(loaded_session),
        _check_field_route_projection_replayability(loaded_session),
        _check_field_route_case_matrix(loaded_session),
    ]
    overall_status = "passed" if all(check.status == "passed" for check in checks) else "failed"
    return CompletionReport(
        overall_status=overall_status,
        checks=checks,
        summary={
            "field_authored_exploration_route_completion": overall_status,
            "route_node_count": len(loaded_session.get("route_nodes", [])),
            "route_step_count": len(loaded_session.get("route_step_records", [])),
        },
        audit={
            "authority_boundary": "exploration route state is non-authority scenario state replayed from field signature, tool, goal, consequence, projection, and baseline artifacts",
        },
    )


VISIBLE_WAVEFRONT_MAIN_PAYLOAD_FORBIDDEN_KEYS = set(SPECTRAL_CAMERA_MAIN_PAYLOAD_FORBIDDEN_KEYS) | {
    "wavefront_overlays",
    "material_wavefront_response_overlays",
    "field_structure_projection",
    "material_environment_zones",
    "playable_consequence_overlays",
}


def _visible_field_ids(fields: dict[str, dict[str, Any]], camera_frame: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    for field_id in camera_frame.get("source_field_state_ids", []):
        text = str(field_id)
        if text in fields:
            return fields[text], text
    return None, None


def _wavefront_run_id(record: dict[str, Any]) -> str:
    record_id = str(record.get("record_id", ""))
    tick = str(record.get("tick", ""))
    channel = str(record.get("channel", ""))
    prefix = "disturbance-wavefront::"
    suffix = f"::{tick}::{channel}"
    if record_id.startswith(prefix) and record_id.endswith(suffix):
        return record_id[len(prefix) : -len(suffix)]
    return "run"


def _check_visible_wavefront_record_replay(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    fields = _index_spectral_records(list(loaded_session.get("field_states", [])), "field_state_id", "id")
    records = [_spectral_as_dict(record) for record in loaded_session.get("disturbance_wavefront_records", [])]
    records_by_id = {str(record.get("record_id")): record for record in records if record.get("record_id")}
    if not records:
        failures.append({"reason": "missing_disturbance_wavefront_records"})
    for record in records:
        record_id = str(record.get("record_id", ""))
        previous = fields.get(str(record.get("source_previous_field_state_id", "")))
        current = fields.get(str(record.get("source_current_field_state_id", "")))
        if not previous or not current:
            failures.append({"record_id": record_id, "reason": "missing_source_field_state"})
            continue
        previous_record = records_by_id.get(str(record.get("previous_wavefront_record_id", "")))
        try:
            recomputed = compute_disturbance_wavefront_records(
                run_id=_wavefront_run_id(record),
                previous_field_state=previous,
                current_field_state=current,
                channel=str(record.get("channel", "")),
                wave_step_record_ids=[str(value) for value in record.get("source_wave_step_record_ids", [])],
                interaction_command_ids=[str(value) for value in record.get("source_interaction_command_ids", [])],
                playable_consequence_record_ids=[
                    str(value) for value in record.get("source_playable_consequence_record_ids", [])
                ],
                delta_threshold=float(record.get("delta_threshold", 0.05)),
                source_center_grid=record.get("source_center_grid"),
                previous_wavefront_record=previous_record,
            )
        except Exception as exc:  # noqa: BLE001 - completion returns structured failures.
            failures.append({"record_id": record_id, "reason": "wavefront_replay_error", "message": str(exc)})
            continue
        if not recomputed:
            failures.append({"record_id": record_id, "reason": "wavefront_replay_empty"})
            continue
        expected = recomputed[0]
        mismatches = [
            key
            for key in ("record_id", "support_digest", "phase_signature", "source_previous_field_state_id", "source_current_field_state_id")
            if str(record.get(key)) != str(expected.get(key))
        ]
        missing_source_ids = sorted(set(expected.get("source_record_ids", [])) - set(record.get("source_record_ids", [])))
        if mismatches or missing_source_ids:
            failures.append(
                {
                    "record_id": record_id,
                    "reason": "wavefront_replay_mismatch",
                    "mismatches": mismatches,
                    "missing_source_ids": missing_source_ids,
                }
            )
    return _completion_check(
        "visible_wavefront_record_replay",
        not failures,
        {"failures": failures[:20], "wavefront_record_count": len(records)},
    )


def _check_visible_wavefront_projection_boundary(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    for frame in loaded_session.get("projection_frames", []):
        frame_id = str(_frame_value(frame, "frame_id", ""))
        payload = _spectral_frame_payload(frame)
        forbidden = sorted(VISIBLE_WAVEFRONT_MAIN_PAYLOAD_FORBIDDEN_KEYS.intersection(payload.keys()))
        if forbidden:
            failures.append({"frame_id": frame_id, "reason": "direct_wavefront_artifact_main_payload", "keys": forbidden})
        debug_layers = payload.get("debug_layers", {})
        if not isinstance(debug_layers, dict) or debug_layers.get("schema") != "spectral_camera_debug_layers_v1":
            failures.append({"frame_id": frame_id, "reason": "missing_debug_layers"})
        elif debug_layers.get("default_enabled") is not False or debug_layers.get("is_authority_state") is not False:
            failures.append({"frame_id": frame_id, "reason": "debug_layers_not_default_off_non_authority"})
    return _completion_check(
        "visible_wavefront_projection_boundary",
        not failures,
        {"failures": failures[:20], "projection_frame_count": len(loaded_session.get("projection_frames", []))},
    )


def _check_visible_wavefront_camera_replay(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    fields = _index_spectral_records(list(loaded_session.get("field_states", [])), "field_state_id", "id")
    properties = _index_spectral_records(list(loaded_session.get("derived_material_property_records", [])), "record_id", "id")
    consequences = _index_spectral_records(
        list(loaded_session.get("playable_consequence_records", [])), "consequence_id", "record_id", "id"
    )
    wavefronts = _index_spectral_records(list(loaded_session.get("disturbance_wavefront_records", [])), "record_id", "id")
    responses = _index_spectral_records(
        list(loaded_session.get("material_wavefront_response_records", [])), "record_id", "id"
    )
    for frame in loaded_session.get("projection_frames", []):
        frame_id = str(_frame_value(frame, "frame_id", ""))
        camera_frame = _spectral_frame_payload(frame).get("spectral_camera_frame")
        if not isinstance(camera_frame, dict):
            failures.append({"frame_id": frame_id, "reason": "missing_spectral_camera_frame"})
            continue
        current_field, _field_id = _visible_field_ids(fields, camera_frame)
        if current_field is None:
            failures.append({"frame_id": frame_id, "reason": "source_field_state_not_found"})
            continue
        source_wavefront_ids = [str(value) for value in camera_frame.get("source_wavefront_record_ids", [])]
        missing_wavefront_ids = [record_id for record_id in source_wavefront_ids if record_id not in wavefronts]
        if missing_wavefront_ids:
            failures.append({"frame_id": frame_id, "reason": "source_wavefront_records_not_found", "record_ids": missing_wavefront_ids})
            continue
        wavefront_records = [wavefronts[record_id] for record_id in source_wavefront_ids]
        previous_field = None
        for wavefront in wavefront_records:
            previous_id = str(wavefront.get("source_previous_field_state_id", ""))
            if previous_id in fields:
                previous_field = fields[previous_id]
                break
        source_property_ids = [str(value) for value in camera_frame.get("source_property_record_ids", [])]
        source_consequence_ids = [str(value) for value in camera_frame.get("source_playable_consequence_record_ids", [])]
        source_response_ids = [str(value) for value in camera_frame.get("source_material_wavefront_response_record_ids", [])]
        missing = [
            *[record_id for record_id in source_property_ids if record_id not in properties],
            *[record_id for record_id in source_consequence_ids if record_id not in consequences],
            *[record_id for record_id in source_response_ids if record_id not in responses],
        ]
        if missing:
            failures.append({"frame_id": frame_id, "reason": "source_records_not_found", "record_ids": missing})
            continue
        property_records = [_normalize_spectral_property_record(properties[record_id]) for record_id in source_property_ids]
        consequence_records = [{"id": record_id, **consequences[record_id]} for record_id in source_consequence_ids]
        response_records = [responses[record_id] for record_id in source_response_ids]
        excluded = set(source_property_ids + source_consequence_ids + source_wavefront_ids + source_response_ids)
        base_source_record_ids = [str(record_id) for record_id in camera_frame.get("source_record_ids", []) if str(record_id) not in excluded]
        try:
            replayed = sample_spectral_camera_frame(
                field_state={**current_field, "id": _spectral_id(current_field, "field_state_id", "id")},
                previous_field_state=previous_field,
                observer_pose=camera_frame["observer_pose"],
                camera_model=camera_frame["camera_model"],
                property_records=property_records,
                playable_consequence_records=consequence_records,
                wavefront_records=wavefront_records,
                material_wavefront_response_records=response_records,
                source_record_ids=base_source_record_ids,
            )
        except Exception as exc:  # noqa: BLE001
            failures.append({"frame_id": frame_id, "reason": "camera_replay_error", "message": str(exc)})
            continue
        if replayed.get("pixel_digest") != camera_frame.get("pixel_digest"):
            failures.append(
                {
                    "frame_id": frame_id,
                    "reason": "camera_pixel_digest_mismatch",
                    "expected": replayed.get("pixel_digest"),
                    "actual": camera_frame.get("pixel_digest"),
                }
            )
    return _completion_check(
        "visible_wavefront_camera_replay",
        not failures,
        {"failures": failures[:20], "projection_frame_count": len(loaded_session.get("projection_frames", []))},
    )


def _check_visible_wavefront_temporal_response(loaded_session: dict[str, Any]) -> CompletionCheck:
    frames = list(loaded_session.get("projection_frames", []))
    digests: list[str] = []
    transient_sample_count = 0
    for frame in frames:
        camera_frame = _spectral_frame_payload(frame).get("spectral_camera_frame", {})
        if isinstance(camera_frame, dict):
            if camera_frame.get("pixel_digest"):
                digests.append(str(camera_frame["pixel_digest"]))
            transient_sample_count += sum(
                1 for sample in camera_frame.get("samples", []) if isinstance(sample, dict) and sample.get("transient_schema")
            )
    ok = transient_sample_count > 0 and (len(frames) < 2 or len(set(digests)) >= 2)
    return _completion_check(
        "visible_wavefront_temporal_response",
        ok,
        {
            "projection_frame_count": len(frames),
            "distinct_camera_pixel_digest_count": len(set(digests)),
            "transient_sample_count": transient_sample_count,
        },
    )


def _check_visible_wavefront_propagation_trace(loaded_session: dict[str, Any]) -> CompletionCheck:
    records = sorted(
        [_spectral_as_dict(record) for record in loaded_session.get("disturbance_wavefront_records", [])],
        key=lambda item: int(item.get("tick", 0)),
    )
    failures: list[dict[str, Any]] = []
    if len(records) >= 3:
        runs: list[list[dict[str, Any]]] = []
        current_run: list[dict[str, Any]] = []
        for record in records:
            if not current_run or int(record.get("tick", 0)) == int(current_run[-1].get("tick", 0)) + 1:
                current_run.append(record)
            else:
                runs.append(current_run)
                current_run = [record]
        if current_run:
            runs.append(current_run)
        consecutive_run = max(runs, key=len)
        ticks = [int(record.get("tick", 0)) for record in consecutive_run]
        trace_ids = {str(record.get("wavefront_trace_id", "")) for record in consecutive_run}
        source_interactions = sorted(
            {str(value) for record in consecutive_run for value in record.get("source_interaction_command_ids", [])}
        )
        radius_series = [float(record.get("radius_grid", 0.0)) for record in consecutive_run]
        if len(consecutive_run) < 3:
            failures.append({"reason": "missing_three_adjacent_wavefront_records", "ticks": [int(record.get("tick", 0)) for record in records]})
        if len(trace_ids) != 1 or "" in trace_ids:
            failures.append({"reason": "trace_id_mismatch", "trace_ids": sorted(trace_ids)})
        if not source_interactions:
            failures.append({"reason": "missing_source_interaction_command_ids"})
        if max(radius_series) - min(radius_series) < 0.5:
            failures.append({"reason": "insufficient_radius_movement", "radius_grid_series": radius_series})
    elif records:
        # Single-frame/two-frame inspection cases do not prove propagation, but they should not block failure tests.
        return _completion_check(
            "visible_wavefront_propagation_trace",
            True,
            {"wavefront_record_count": len(records), "propagation_case": False},
        )
    else:
        failures.append({"reason": "missing_disturbance_wavefront_records"})
    return _completion_check(
        "visible_wavefront_propagation_trace",
        not failures,
        {"failures": failures[:20], "wavefront_record_count": len(records)},
    )


def _check_visible_wavefront_material_response(loaded_session: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    wavefronts = _index_spectral_records(list(loaded_session.get("disturbance_wavefront_records", [])), "record_id", "id")
    responses = [_spectral_as_dict(record) for record in loaded_session.get("material_wavefront_response_records", [])]
    for response in responses:
        response_id = str(response.get("record_id", ""))
        try:
            validate_material_wavefront_response_record(response)
        except Exception as exc:  # noqa: BLE001
            failures.append({"record_id": response_id, "reason": "invalid_material_wavefront_response", "message": str(exc)})
            continue
        if str(response.get("source_wavefront_record_id", "")) not in wavefronts:
            failures.append({"record_id": response_id, "reason": "missing_source_wavefront_record"})
        if not response.get("source_property_record_ids") and not response.get("source_playable_consequence_record_ids"):
            failures.append({"record_id": response_id, "reason": "missing_property_or_consequence_sources"})
    summary = loaded_session.get("case_summary", {})
    case_type = str(summary.get("case_type", ""))
    if case_type == "local_dampen_wavefront_absorption":
        baseline = float(summary.get("baseline_front_delta_energy_mean", 0.0))
        case = float(summary.get("case_front_delta_energy_mean", 0.0))
        ratio = case / baseline if baseline > 0.0 else 1.0
        if ratio > 0.85:
            failures.append({"reason": "dampening_absorption_ratio_too_weak", "ratio": ratio})
    if case_type == "boundary_wavefront_reflection":
        reflection_delta = float(summary.get("boundary_reflection_delta", 0.0))
        baseline = float(summary.get("baseline_front_delta_energy_mean", 0.0))
        case = float(summary.get("case_front_delta_energy_mean", 0.0))
        if reflection_delta < 0.05 or abs(case - baseline) < 0.03:
            failures.append(
                {
                    "reason": "boundary_reflection_too_weak",
                    "boundary_reflection_delta": reflection_delta,
                    "front_delta_energy_difference": abs(case - baseline),
                }
            )
    return _completion_check(
        "visible_wavefront_material_response",
        not failures,
        {"failures": failures[:20], "material_wavefront_response_record_count": len(responses)},
    )


def evaluate_visible_wavefront_completion(loaded_session: dict[str, Any]) -> CompletionReport:
    checks = [
        _check_visible_wavefront_record_replay(loaded_session),
        _check_visible_wavefront_camera_replay(loaded_session),
        _check_visible_wavefront_projection_boundary(loaded_session),
        _check_visible_wavefront_temporal_response(loaded_session),
        _check_visible_wavefront_propagation_trace(loaded_session),
        _check_visible_wavefront_material_response(loaded_session),
    ]
    overall_status = "passed" if all(check.status == "passed" for check in checks) else "failed"
    return CompletionReport(
        overall_status=overall_status,
        checks=checks,
        summary={
            "visible_wavefront_completion": overall_status,
            "projection_frame_count": len(loaded_session.get("projection_frames", [])),
            "field_state_count": len(loaded_session.get("field_states", [])),
            "disturbance_wavefront_record_count": len(loaded_session.get("disturbance_wavefront_records", [])),
        },
        audit={
            "authority_boundary": "visible wavefront samples are replayed from adjacent read-back field-state deltas and rendered only through observer-relative spectral camera samples",
        },
    )


IMPLICIT_VIEWER_AUTHORITY_FORBIDDEN_KEYS = {
    "css_color",
    "viewer_shape",
    "viewer_label",
    "canvas_pixels",
    "viewer_transform",
    "mesh",
    "sprite",
    "object_asset_id",
    "dense_volume",
    "voxel_grid",
}


def _implicit_dict(record: Any) -> dict[str, Any]:
    if hasattr(record, "to_dict"):
        return dict(record.to_dict())
    return dict(record or {})


def _check_no_implicit_viewer_authority_value(value: Any, *, path: str, failures: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in IMPLICIT_VIEWER_AUTHORITY_FORBIDDEN_KEYS:
                failures.append({"reason": "viewer_or_dense_authority_key", "path": f"{path}.{key}", "key": key})
            _check_no_implicit_viewer_authority_value(child, path=f"{path}.{key}", failures=failures)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _check_no_implicit_viewer_authority_value(child, path=f"{path}[{index}]", failures=failures)


def _check_implicit_basis_contract(report_inputs: dict[str, Any]) -> CompletionCheck:
    from world_engine.implicit_field import validate_implicit_field_basis

    failures: list[dict[str, Any]] = []
    bases = [_implicit_dict(record) for record in report_inputs.get("implicit_basis_records", [])]
    for basis in bases:
        try:
            validate_implicit_field_basis(basis)
        except Exception as exc:  # noqa: BLE001
            failures.append({"basis_id": basis.get("basis_id"), "reason": "invalid_basis", "message": str(exc)})
    if not bases:
        failures.append({"reason": "missing_implicit_basis_records"})
    return _completion_check("implicit_basis_contract_status", not failures, {"basis_count": len(bases), "failures": failures[:20]})


def _check_implicit_state_replay(report_inputs: dict[str, Any]) -> CompletionCheck:
    from world_engine.implicit_field import validate_implicit_field_state

    failures: list[dict[str, Any]] = []
    states = [_implicit_dict(record) for record in report_inputs.get("implicit_field_states", [])]
    for state in states:
        try:
            validate_implicit_field_state(state)
        except Exception as exc:  # noqa: BLE001
            failures.append({"state_id": state.get("implicit_field_state_id"), "reason": "invalid_state", "message": str(exc)})
        if state.get("authority_status") == "validated":
            failures.append({"state_id": state.get("implicit_field_state_id"), "reason": "self_validated_state"})
    if not states:
        failures.append({"reason": "missing_implicit_field_states"})
    return _completion_check("implicit_state_replay_status", not failures, {"state_count": len(states), "failures": failures[:20]})


def _check_implicit_ray_and_image_replay(report_inputs: dict[str, Any]) -> CompletionCheck:
    from world_engine.implicit_field import validate_implicit_field_evaluation_record
    from world_engine.implicit_ray_camera import validate_implicit_ray_sample_record, validate_implicit_spectral_image_plane

    failures: list[dict[str, Any]] = []
    evaluations = {_implicit_dict(record).get("evaluation_id"): _implicit_dict(record) for record in report_inputs.get("implicit_evaluation_records", [])}
    rays = {_implicit_dict(record).get("ray_sample_record_id"): _implicit_dict(record) for record in report_inputs.get("implicit_ray_sample_records", [])}
    images = {_implicit_dict(record).get("image_plane_id"): _implicit_dict(record) for record in report_inputs.get("implicit_spectral_image_planes", [])}
    for evaluation_id, evaluation in evaluations.items():
        try:
            validate_implicit_field_evaluation_record(evaluation)
        except Exception as exc:  # noqa: BLE001
            failures.append({"evaluation_id": evaluation_id, "reason": "invalid_evaluation", "message": str(exc)})
    for ray_id, ray in rays.items():
        try:
            validate_implicit_ray_sample_record(ray)
        except Exception as exc:  # noqa: BLE001
            failures.append({"ray_sample_record_id": ray_id, "reason": "invalid_ray_sample", "message": str(exc)})
            continue
        for evaluation_id in ray.get("source_evaluation_ids", []):
            evaluation = evaluations.get(evaluation_id)
            if not evaluation:
                failures.append({"ray_sample_record_id": ray_id, "evaluation_id": evaluation_id, "reason": "missing_source_evaluation"})
                continue
            if evaluation.get("sample_points_world_3d_digest") != ray.get("ray_sample_points_digest"):
                failures.append({"ray_sample_record_id": ray_id, "evaluation_id": evaluation_id, "reason": "ray_sample_digest_mismatch"})
    for image_id, image in images.items():
        try:
            validate_implicit_spectral_image_plane(image)
        except Exception as exc:  # noqa: BLE001
            failures.append({"image_plane_id": image_id, "reason": "invalid_image_plane", "message": str(exc)})
            continue
        if image.get("ray_sample_record_id") not in rays:
            failures.append({"image_plane_id": image_id, "reason": "missing_ray_sample_record"})
    if not rays:
        failures.append({"reason": "missing_implicit_ray_sample_records"})
    if not images:
        failures.append({"reason": "missing_implicit_spectral_image_planes"})
    return _completion_check(
        "ray_replay_status",
        not failures,
        {"evaluation_count": len(evaluations), "ray_count": len(rays), "image_count": len(images), "failures": failures[:20]},
    )


def _check_implicit_authority_certificate(report_inputs: dict[str, Any]) -> CompletionCheck:
    from world_engine.implicit_field import validate_implicit_field_authority_certificate

    failures: list[dict[str, Any]] = []
    states = {_implicit_dict(record).get("implicit_field_state_id"): _implicit_dict(record) for record in report_inputs.get("implicit_field_states", [])}
    certificates = [_implicit_dict(record) for record in report_inputs.get("implicit_authority_certificates", [])]
    for certificate in certificates:
        state = states.get(certificate.get("implicit_field_state_id"))
        if not state:
            failures.append({"certificate_id": certificate.get("certificate_id"), "reason": "missing_state"})
            continue
        try:
            validate_implicit_field_authority_certificate(certificate, state)
        except Exception as exc:  # noqa: BLE001
            failures.append({"certificate_id": certificate.get("certificate_id"), "reason": "invalid_certificate", "message": str(exc)})
    if not certificates:
        failures.append({"reason": "missing_implicit_authority_certificates"})
    return _completion_check("implicit_authority_certificate_status", not failures, {"certificate_count": len(certificates), "failures": failures[:20]})


def _check_implicit_observer_path_lineage(report_inputs: dict[str, Any]) -> CompletionCheck:
    from world_engine.implicit_ray_camera import validate_implicit_observer_path_record

    failures: list[dict[str, Any]] = []
    paths = {_implicit_dict(record).get("observer_path_id"): _implicit_dict(record) for record in report_inputs.get("implicit_observer_path_records", [])}
    rays = [_implicit_dict(record) for record in report_inputs.get("implicit_ray_sample_records", [])]
    for path_id, path in paths.items():
        try:
            validate_implicit_observer_path_record(path)
        except Exception as exc:  # noqa: BLE001
            failures.append({"observer_path_id": path_id, "reason": "invalid_observer_path", "message": str(exc)})
    for ray in rays:
        if ray.get("observer_path_id") not in paths:
            failures.append({"ray_sample_record_id": ray.get("ray_sample_record_id"), "reason": "missing_observer_path"})
    multi_tick_paths = [path for path in paths.values() if len(path.get("camera_pose_records", [])) >= 2]
    if multi_tick_paths and len({ray.get("ray_sample_points_digest") for ray in rays}) <= 1:
        failures.append({"reason": "camera_motion_does_not_change_ray_sample_digest"})
    return _completion_check("observer_path_lineage_status", not failures, {"path_count": len(paths), "failures": failures[:20]})


def _check_implicit_runtime_and_culling(report_inputs: dict[str, Any]) -> list[CompletionCheck]:
    failures_stability: list[dict[str, Any]] = []
    failures_culling: list[dict[str, Any]] = []
    states = [_implicit_dict(record) for record in report_inputs.get("implicit_field_states", [])]
    evaluations = [_implicit_dict(record) for record in report_inputs.get("implicit_evaluation_records", [])]
    certificates = [_implicit_dict(record) for record in report_inputs.get("implicit_authority_certificates", [])]
    for state in states:
        cost = state.get("runtime_cost_summary", {})
        if isinstance(cost, dict):
            if "dense_volume_used" in cost and cost.get("dense_volume_used") is not False:
                failures_stability.append({"state_id": state.get("implicit_field_state_id"), "reason": "dense_volume_used"})
            if float(cost.get("coefficient_clamp_saturation_ratio", 0.0)) > 0.05:
                failures_stability.append({"state_id": state.get("implicit_field_state_id"), "reason": "excessive_clamp_saturation"})
    for certificate in certificates:
        bounds = certificate.get("error_bounds", {})
        if float(bounds.get("coefficient_clamp_saturation_ratio", 0.0)) > 0.05:
            failures_stability.append({"certificate_id": certificate.get("certificate_id"), "reason": "certificate_excessive_clamp_saturation"})
        if float(bounds.get("active_basis_per_sample_max", 0.0)) > 24:
            failures_culling.append({"certificate_id": certificate.get("certificate_id"), "reason": "certificate_active_basis_too_high"})
    for evaluation in evaluations:
        summary = evaluation.get("active_basis_per_sample_summary", {})
        if float(summary.get("max", 0.0)) > 24:
            failures_culling.append({"evaluation_id": evaluation.get("evaluation_id"), "reason": "active_basis_too_high"})
    return [
        _completion_check("runtime_stability_status", not failures_stability, {"failures": failures_stability[:20]}),
        _completion_check("basis_spatial_culling_status", not failures_culling, {"failures": failures_culling[:20]}),
    ]


def _check_implicit_baseline_and_refinement(report_inputs: dict[str, Any]) -> list[CompletionCheck]:
    from world_engine.implicit_baseline import validate_implicit_baseline_comparison_record
    from world_engine.implicit_refinement import validate_implicit_local_refinement_patch, validate_implicit_local_refinement_request

    baseline_failures: list[dict[str, Any]] = []
    refinement_failures: list[dict[str, Any]] = []
    baselines = [_implicit_dict(record) for record in report_inputs.get("implicit_baseline_comparisons", [])]
    requests = {_implicit_dict(record).get("request_id"): _implicit_dict(record) for record in report_inputs.get("implicit_refinement_requests", [])}
    patches = [_implicit_dict(record) for record in report_inputs.get("implicit_refinement_patches", [])]
    for baseline in baselines:
        try:
            validate_implicit_baseline_comparison_record(baseline)
        except Exception as exc:  # noqa: BLE001
            baseline_failures.append({"comparison_id": baseline.get("comparison_id"), "reason": "invalid_baseline", "message": str(exc)})
    for request_id, request in requests.items():
        try:
            validate_implicit_local_refinement_request(request)
        except Exception as exc:  # noqa: BLE001
            refinement_failures.append({"request_id": request_id, "reason": "invalid_refinement_request", "message": str(exc)})
    for patch in patches:
        try:
            validate_implicit_local_refinement_patch(patch)
        except Exception as exc:  # noqa: BLE001
            refinement_failures.append({"patch_id": patch.get("patch_id"), "reason": "invalid_refinement_patch", "message": str(exc)})
            continue
        if patch.get("request_id") not in requests:
            refinement_failures.append({"patch_id": patch.get("patch_id"), "reason": "missing_refinement_request"})
    if patches and not baselines:
        baseline_failures.append({"reason": "local_refinement_missing_baseline_comparison"})
    return [
        _completion_check("local_refinement_lineage_status", not refinement_failures, {"failures": refinement_failures[:20]}),
        _completion_check("baseline_comparison_status", not baseline_failures, {"comparison_count": len(baselines), "failures": baseline_failures[:20]}),
    ]


def _check_implicit_projection_and_viewer_boundary(report_inputs: dict[str, Any]) -> list[CompletionCheck]:
    projection_failures: list[dict[str, Any]] = []
    viewer_failures: list[dict[str, Any]] = []
    certificate_ids = {str(_implicit_dict(record).get("certificate_id")) for record in report_inputs.get("implicit_authority_certificates", [])}
    ray_ids = {str(_implicit_dict(record).get("ray_sample_record_id")) for record in report_inputs.get("implicit_ray_sample_records", [])}
    for frame in report_inputs.get("projection_frames", []):
        frame_id = str(_frame_value(frame, "frame_id", ""))
        payload = _spectral_frame_payload(frame)
        _check_no_implicit_viewer_authority_value(payload, path=f"projection_frame.{frame_id}.payload", failures=viewer_failures)
        if payload.get("implicit_field_state_id"):
            certificate_id = str(payload.get("implicit_authority_certificate_id", ""))
            if certificate_id not in certificate_ids:
                projection_failures.append({"frame_id": frame_id, "reason": "missing_or_unknown_implicit_certificate"})
            image = payload.get("implicit_spectral_image_plane")
            ray = payload.get("implicit_ray_sample_record")
            if not isinstance(image, dict) or not isinstance(ray, dict):
                projection_failures.append({"frame_id": frame_id, "reason": "missing_implicit_image_or_ray_payload"})
            elif str(ray.get("ray_sample_record_id")) not in ray_ids or image.get("ray_sample_record_id") != ray.get("ray_sample_record_id"):
                projection_failures.append({"frame_id": frame_id, "reason": "implicit_ray_image_source_mismatch"})
    if not report_inputs.get("projection_frames"):
        projection_failures.append({"reason": "missing_projection_frames"})
    return [
        _completion_check("implicit_projection_payload_status", not projection_failures, {"failures": projection_failures[:20]}),
        _completion_check("no_viewer_authority_status", not viewer_failures, {"failures": viewer_failures[:20]}),
    ]


def _check_implicit_no_dense_global_volume(report_inputs: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    _check_no_implicit_viewer_authority_value(report_inputs.get("implicit_field_states", []), path="implicit_field_states", failures=failures)
    return _completion_check("no_dense_global_volume_status", not failures, {"failures": failures[:20]})


def evaluate_implicit_3d_field_completion(report_inputs: dict[str, Any]) -> CompletionReport:
    checks = [
        _check_implicit_basis_contract(report_inputs),
        _check_implicit_state_replay(report_inputs),
        *_check_implicit_runtime_and_culling(report_inputs),
        _check_implicit_ray_and_image_replay(report_inputs),
        _check_implicit_authority_certificate(report_inputs),
        _check_implicit_observer_path_lineage(report_inputs),
        *_check_implicit_baseline_and_refinement(report_inputs),
        *_check_implicit_projection_and_viewer_boundary(report_inputs),
        _check_implicit_no_dense_global_volume(report_inputs),
    ]
    overall_status = "passed" if all(check.status == "passed" for check in checks) else "failed"
    return CompletionReport(
        overall_status=overall_status,
        checks=checks,
        summary={
            "implicit_3d_field_completion": overall_status,
            "implicit_basis_count": len(report_inputs.get("implicit_basis_records", [])),
            "implicit_ray_sample_count": len(report_inputs.get("implicit_ray_sample_records", [])),
            "implicit_image_plane_count": len(report_inputs.get("implicit_spectral_image_planes", [])),
        },
        audit={
            "authority_boundary": "implicit field state is compact authority candidate; viewer image is ray-derived non-authority observation",
        },
    )


def _check_implicit_live_runtime_mode(report_inputs: dict[str, Any]) -> CompletionCheck:
    session = dict(report_inputs.get("session", {}))
    failures: list[dict[str, Any]] = []
    if session.get("runtime_mode") != "live-implicit-3d-field":
        failures.append({"reason": "runtime_mode_mismatch", "runtime_mode": session.get("runtime_mode")})
    if int(session.get("projection_frame_count", 0)) != len(report_inputs.get("projection_frames", [])):
        failures.append({"reason": "projection_frame_count_mismatch"})
    if int(session.get("implicit_live_step_count", 0)) != len(report_inputs.get("implicit_live_step_records", [])):
        failures.append({"reason": "implicit_live_step_count_mismatch"})
    if "observer::implicit-pinhole" not in set(session.get("observer_ids", [])):
        failures.append({"reason": "missing_declared_implicit_observer"})
    return _completion_check("implicit_live_runtime_mode_status", not failures, {"failures": failures[:20]})


def _check_implicit_live_step_chain(report_inputs: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    states = [_implicit_dict(record) for record in report_inputs.get("implicit_field_states", [])]
    state_id_list = [str(state.get("implicit_field_state_id", "")) for state in states]
    state_tick_list = [state.get("tick") for state in states]
    if (
        any(not state_id for state_id in state_id_list)
        or len(state_id_list) != len(set(state_id_list))
        or any(isinstance(tick, bool) or not isinstance(tick, int) for tick in state_tick_list)
        or len(state_tick_list) != len(set(state_tick_list))
    ):
        failures.append({"reason": "canonical_state_identity_or_tick_not_unique"})
    state_ids = {str(state.get("implicit_field_state_id")) for state in states}
    steps = [_implicit_dict(record) for record in report_inputs.get("implicit_live_step_records", [])]
    step_id_list = [str(step.get("step_id", "")) for step in steps]
    if any(not step_id for step_id in step_id_list) or len(step_id_list) != len(set(step_id_list)):
        failures.append({"reason": "implicit_step_identity_not_unique"})
    if not steps:
        failures.append({"reason": "missing_implicit_live_step_records"})
    previous_result_id = str(states[0].get("implicit_field_state_id")) if states else ""
    for step in sorted(steps, key=lambda item: int(item.get("tick", 0))):
        if step.get("schema") != "implicit_live_step_record":
            failures.append({"step_id": step.get("step_id"), "reason": "schema_mismatch"})
        if str(step.get("previous_state_id")) != previous_result_id:
            failures.append({"step_id": step.get("step_id"), "reason": "previous_state_chain_mismatch"})
        if str(step.get("result_state_id")) not in state_ids:
            failures.append({"step_id": step.get("step_id"), "reason": "missing_result_state"})
        runtime_cost = step.get("runtime_cost_summary", {})
        if not isinstance(runtime_cost, dict) or runtime_cost.get("dense_volume_used") is not False:
            failures.append({"step_id": step.get("step_id"), "reason": "dense_volume_used"})
        previous_result_id = str(step.get("result_state_id"))
    return _completion_check("implicit_live_step_chain_status", not failures, {"step_count": len(steps), "failures": failures[:20]})


_IMPLICIT_ENERGY_LEDGER_NUMBER_KEYS = (
    "energy_before",
    "energy_after_decay",
    "energy_after_internal",
    "energy_after_coupling",
    "energy_after_user",
    "energy_before_clip",
    "energy_after",
    "d_decay",
    "x_internal",
    "f_boundary_proxy",
    "i_user",
    "i_feedback",
    "d_clip",
    "residual",
    "residual_tolerance",
)


def _expected_implicit_local_energy_scopes(
    report_inputs: Mapping[str, Any],
    *,
    basis_ids: set[str],
    ordinary_steps: list[dict[str, Any]],
) -> tuple[dict[int, dict[str, dict[str, float]]], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    ordinary_steps_by_id = {
        str(step.get("step_id", "")): step for step in ordinary_steps
    }
    ordinary_steps_by_tick = {
        int(step.get("tick", -1)): step for step in ordinary_steps
    }
    expected_by_tick: dict[int, dict[str, dict[str, float]]] = {
        tick: {} for tick in ordinary_steps_by_tick
    }

    def parse_kappa(
        raw_kappa: Any,
        *,
        owner_id: str,
    ) -> dict[str, float] | None:
        if not isinstance(raw_kappa, Mapping) or any(
            isinstance(value, bool) for value in raw_kappa.values()
        ):
            failures.append(
                {"owner_id": owner_id, "reason": "energy_scope_kappa_lineage_invalid"}
            )
            return None
        try:
            unknown_basis_ids = sorted(set(map(str, raw_kappa)) - basis_ids)
            kappa = {
                basis_id: float(raw_kappa.get(basis_id, 0.0))
                for basis_id in basis_ids
            }
        except (TypeError, ValueError):
            failures.append(
                {"owner_id": owner_id, "reason": "energy_scope_kappa_lineage_invalid"}
            )
            return None
        if (
            unknown_basis_ids
            or any(not math.isfinite(value) or value < 0.0 for value in kappa.values())
            or not any(value > 0.0 for value in kappa.values())
        ):
            failures.append(
                {
                    "owner_id": owner_id,
                    "reason": "energy_scope_kappa_lineage_invalid",
                    "unknown_basis_ids": unknown_basis_ids,
                }
            )
            return None
        return kappa

    def register_scope(
        *,
        scope_id: str,
        kappa: dict[str, float],
        activation_tick: int,
        expiry_tick: int,
        owner_id: str,
    ) -> None:
        if not scope_id or activation_tick < 0 or expiry_tick < activation_tick:
            failures.append(
                {"owner_id": owner_id, "reason": "energy_scope_window_invalid"}
            )
            return
        for tick, expected_scopes in expected_by_tick.items():
            if not activation_tick <= tick <= expiry_tick:
                continue
            existing = expected_scopes.get(scope_id)
            if existing is not None and stable_digest(existing) != stable_digest(kappa):
                failures.append(
                    {
                        "owner_id": owner_id,
                        "scope_id": scope_id,
                        "tick": tick,
                        "reason": "energy_scope_owner_collision",
                    }
                )
                continue
            expected_scopes[scope_id] = dict(kappa)

    for audit in (
        _implicit_dict(record)
        for record in report_inputs.get("implicit_interaction_audits", [])
    ):
        if str(audit.get("tool", "")) not in {
            "implicit_local_excite",
            "implicit_local_dampen",
        }:
            continue
        command_id = str(audit.get("command_id", ""))
        scope_id = f"implicit-energy-scope::{command_id}"
        raw_start_tick = audit.get("start_tick")
        schedule_weights = audit.get("schedule_weights")
        if (
            not command_id
            or isinstance(raw_start_tick, bool)
            or not isinstance(raw_start_tick, int)
            or raw_start_tick < 0
            or not isinstance(schedule_weights, list)
            or not schedule_weights
        ):
            failures.append(
                {"owner_id": str(audit.get("audit_id", "")), "reason": "user_energy_scope_lineage_invalid"}
            )
            continue
        try:
            parsed_schedule = [float(value) for value in schedule_weights]
        except (TypeError, ValueError):
            failures.append(
                {"owner_id": str(audit.get("audit_id", "")), "reason": "user_energy_scope_lineage_invalid"}
            )
            continue
        if any(
            isinstance(raw_value, bool)
            or not math.isfinite(value)
            or value <= 0.0
            or value > 1.0
            for raw_value, value in zip(schedule_weights, parsed_schedule)
        ):
            failures.append(
                {"owner_id": str(audit.get("audit_id", "")), "reason": "user_energy_scope_lineage_invalid"}
            )
            continue
        kappa = parse_kappa(
            audit.get("kappa_by_basis"), owner_id=str(audit.get("audit_id", ""))
        )
        if kappa is None:
            continue
        final_input_tick = raw_start_tick + len(parsed_schedule) - 1
        register_scope(
            scope_id=scope_id,
            kappa=kappa,
            activation_tick=raw_start_tick,
            expiry_tick=final_input_tick + ENERGY_SCOPE_RELAXATION_TICKS,
            owner_id=str(audit.get("audit_id", "")),
        )

        applications = audit.get("applications")
        if not isinstance(applications, list) or len(applications) > len(parsed_schedule):
            failures.append(
                {"owner_id": str(audit.get("audit_id", "")), "reason": "user_energy_scope_application_lineage_invalid"}
            )
            continue
        for expected_index, raw_application in enumerate(applications):
            if not isinstance(raw_application, Mapping):
                failures.append(
                    {"owner_id": str(audit.get("audit_id", "")), "reason": "user_energy_scope_application_lineage_invalid"}
                )
                continue
            application = dict(raw_application)
            application_tick = application.get("tick")
            schedule_index = application.get("schedule_index")
            schedule_weight = application.get("schedule_weight")
            application_step = (
                ordinary_steps_by_tick.get(int(application_tick))
                if isinstance(application_tick, int) and not isinstance(application_tick, bool)
                else None
            )
            matching_pending_lineage = []
            if application_step is not None:
                matching_pending_lineage = [
                    dict(lineage)
                    for lineage in application_step.get("pending_control_lineage", [])
                    if isinstance(lineage, Mapping)
                    and str(lineage.get("command_id", "")) == command_id
                ]
            pending_lineage_matches = (
                len(matching_pending_lineage) == 1
                and str(matching_pending_lineage[0].get("request_id", ""))
                == str(audit.get("request_id", ""))
                and matching_pending_lineage[0].get("accepted_sequence")
                == audit.get("accepted_sequence")
                and matching_pending_lineage[0].get("schedule_index") == expected_index
                and str(matching_pending_lineage[0].get("scope_id", "")) == scope_id
            )
            try:
                schedule_weight_matches = math.isclose(
                    float(schedule_weight),
                    parsed_schedule[expected_index],
                    rel_tol=0.0,
                    abs_tol=1e-15,
                )
            except (TypeError, ValueError):
                schedule_weight_matches = False
            if (
                isinstance(schedule_index, bool)
                or schedule_index != expected_index
                or not isinstance(application_tick, int)
                or isinstance(application_tick, bool)
                or application_tick != raw_start_tick + expected_index
                or not schedule_weight_matches
                or application_step is None
                or command_id not in set(map(str, application_step.get("applied_command_ids", [])))
                or not pending_lineage_matches
            ):
                failures.append(
                    {
                        "owner_id": str(audit.get("audit_id", "")),
                        "schedule_index": expected_index,
                        "reason": "user_energy_scope_application_lineage_invalid",
                    }
                )

    feedback_records = [
        _implicit_dict(record)
        for record in report_inputs.get("five_phase_feedback_records", [])
    ]
    feedback_by_id = {
        str(record.get("record_id", "")): record for record in feedback_records
    }
    if any(not record_id for record_id in feedback_by_id) or len(feedback_by_id) != len(feedback_records):
        failures.append({"reason": "feedback_energy_scope_record_identity_invalid"})

    feedback_applications = [
        _implicit_dict(record)
        for record in report_inputs.get("five_phase_feedback_applications", [])
    ]
    application_by_id = {
        str(record.get("application_record_id", "")): record
        for record in feedback_applications
    }
    if (
        any(not application_id for application_id in application_by_id)
        or len(application_by_id) != len(feedback_applications)
    ):
        failures.append({"reason": "feedback_energy_scope_application_identity_invalid"})

    retained_feedback_ids: set[str] = set()
    for application in feedback_applications:
        application_id = str(application.get("application_record_id", ""))
        step_id = str(application.get("implicit_live_step_id", ""))
        step = ordinary_steps_by_id.get(step_id)
        raw_tick = application.get("tick")
        if (
            application.get("schema") != "five_phase_feedback_application_record_v2"
            or step is None
            or isinstance(raw_tick, bool)
            or not isinstance(raw_tick, int)
            or raw_tick != int(step.get("tick", -1))
            or str(step.get("five_phase_feedback_application_id", "")) != application_id
        ):
            failures.append(
                {"application_record_id": application_id, "reason": "feedback_energy_scope_application_lineage_invalid"}
            )
            continue

        raw_feedback_ids = application.get("feedback_record_ids")
        baseline_measurements = application.get("baseline_response_measurements")
        candidate_measurements = application.get("candidate_response_measurements")
        if (
            not isinstance(raw_feedback_ids, list)
            or not isinstance(baseline_measurements, list)
            or not isinstance(candidate_measurements, list)
        ):
            failures.append(
                {"application_record_id": application_id, "reason": "feedback_energy_scope_measurement_lineage_invalid"}
            )
            continue
        feedback_ids = [str(value) for value in raw_feedback_ids]
        if (
            len(feedback_ids) != len(set(feedback_ids))
            or len(baseline_measurements) != len(feedback_ids)
            or len(candidate_measurements) != len(feedback_ids)
            or application.get("feedback_consumed") is not True
        ):
            failures.append(
                {"application_record_id": application_id, "reason": "feedback_energy_scope_measurement_lineage_invalid"}
            )
            continue
        measurement_ids_match = all(
            isinstance(baseline, Mapping)
            and isinstance(candidate, Mapping)
            and str(baseline.get("feedback_record_id", "")) == feedback_id
            and str(candidate.get("feedback_record_id", "")) == feedback_id
            for feedback_id, baseline, candidate in zip(
                feedback_ids, baseline_measurements, candidate_measurements
            )
        )
        try:
            directions_eligible = all(
                bool(baseline["candidate_direction_eligible"])
                for baseline in baseline_measurements
            )
            errors_improve = all(
                float(candidate["absolute_error"])
                < float(baseline["absolute_error"])
                - FEEDBACK_ERROR_IMPROVEMENT_TOLERANCE
                for baseline, candidate in zip(
                    baseline_measurements, candidate_measurements
                )
            )
        except (KeyError, TypeError, ValueError):
            directions_eligible = False
            errors_improve = False
            measurement_ids_match = False
        if not measurement_ids_match:
            failures.append(
                {"application_record_id": application_id, "reason": "feedback_energy_scope_measurement_lineage_invalid"}
            )
            continue
        precommit_eligible = bool(feedback_ids) and directions_eligible and errors_improve
        expected_reason = (
            "no_candidate"
            if not feedback_ids
            else "application_direction_ineligible"
            if not directions_eligible
            else "application_error_not_reduced"
            if not errors_improve
            else "feedback_disabled_baseline"
            if not bool(application.get("feedback_enabled"))
            else "eligible_error_reduction"
        )
        if str(application.get("eligibility_reason", "")) != expected_reason:
            failures.append(
                {"application_record_id": application_id, "reason": "feedback_energy_scope_eligibility_mismatch"}
            )

        for feedback_id in feedback_ids:
            feedback = feedback_by_id.get(feedback_id)
            target_basis_id = str((feedback or {}).get("target_basis_id", ""))
            if (
                feedback is None
                or feedback.get("schema") != "five_phase_feedback_v2"
                or target_basis_id not in basis_ids
                or feedback_id in retained_feedback_ids
            ):
                failures.append(
                    {
                        "application_record_id": application_id,
                        "feedback_record_id": feedback_id,
                        "reason": "feedback_energy_scope_target_lineage_invalid",
                    }
                )
                continue
            retained_feedback_ids.add(feedback_id)
            register_scope(
                scope_id=f"implicit-feedback-energy-scope::{feedback_id}",
                kappa={
                    basis_id: 1.0 if basis_id == target_basis_id else 0.0
                    for basis_id in basis_ids
                },
                activation_tick=raw_tick,
                expiry_tick=(
                    raw_tick + ENERGY_SCOPE_RELAXATION_TICKS
                    if precommit_eligible
                    else raw_tick
                ),
                owner_id=application_id,
            )

    for step in ordinary_steps:
        application_id = str(step.get("five_phase_feedback_application_id", ""))
        application = application_by_id.get(application_id)
        if (
            application is None
            or str(application.get("implicit_live_step_id", ""))
            != str(step.get("step_id", ""))
        ):
            failures.append(
                {
                    "step_id": str(step.get("step_id", "")),
                    "reason": "feedback_energy_scope_application_ownership_invalid",
                }
            )

    return expected_by_tick, failures


def implicit_live_energy_ledger_failures(report_inputs: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Recompute every ordinary implicit transition from stored authority inputs."""

    failures: list[dict[str, Any]] = []
    states = [_implicit_dict(record) for record in report_inputs.get("implicit_field_states", [])]
    states_by_id = {str(state.get("implicit_field_state_id")): state for state in states}
    bases = [_implicit_dict(record) for record in report_inputs.get("implicit_basis_records", [])]
    basis_ids = {str(basis.get("basis_id")) for basis in bases}
    steps = [
        _implicit_dict(record)
        for record in report_inputs.get("implicit_live_step_records", [])
    ]
    ordinary_steps = [step for step in steps if not step.get("refinement_patch_ids")]
    expected_scopes_by_tick, scope_lineage_failures = (
        _expected_implicit_local_energy_scopes(
            report_inputs,
            basis_ids=basis_ids,
            ordinary_steps=ordinary_steps,
        )
    )
    failures.extend(scope_lineage_failures)

    for step in steps:
        step_id = str(step.get("step_id", ""))
        previous_state = states_by_id.get(str(step.get("previous_state_id", "")))
        result_state = states_by_id.get(str(step.get("result_state_id", "")))
        if previous_state is None or result_state is None:
            failures.append({"step_id": step_id, "reason": "energy_ledger_state_missing"})
            continue
        if step.get("previous_state_digest") != previous_state.get("state_digest"):
            failures.append({"step_id": step_id, "reason": "previous_state_digest_mismatch"})
        if step.get("result_state_digest") != result_state.get("state_digest"):
            failures.append({"step_id": step_id, "reason": "result_state_digest_mismatch"})
        if int(result_state.get("tick", -1)) != int(previous_state.get("tick", -1)) + 1:
            failures.append({"step_id": step_id, "reason": "canonical_transition_tick_mismatch"})
        if int(step.get("tick", -1)) != int(result_state.get("tick", -2)):
            failures.append({"step_id": step_id, "reason": "step_result_tick_mismatch"})

        ledgers = step.get("energy_ledgers")
        if not isinstance(ledgers, list):
            failures.append({"step_id": step_id, "reason": "energy_ledgers_must_be_list"})
            continue
        is_refinement = bool(step.get("refinement_patch_ids"))
        if is_refinement:
            if ledgers:
                failures.append({"step_id": step_id, "reason": "refinement_must_not_claim_ordinary_energy_ledger"})
            continue
        if not ledgers:
            failures.append({"step_id": step_id, "reason": "ordinary_transition_missing_energy_ledgers"})
            continue

        expected_local_scopes = expected_scopes_by_tick.get(int(step.get("tick", -1)), {})
        scope_ids: list[str] = []
        for raw_ledger in ledgers:
            if not isinstance(raw_ledger, Mapping):
                failures.append({"step_id": step_id, "reason": "energy_ledger_must_be_mapping"})
                continue
            ledger = dict(raw_ledger)
            scope_id = str(ledger.get("scope_id", ""))
            scope_kind = str(ledger.get("scope_kind", ""))
            scope_ids.append(scope_id)
            kappa = ledger.get("kappa")
            if not scope_id or scope_kind not in {"fixed_scene", "local"} or not isinstance(kappa, Mapping):
                failures.append({"step_id": step_id, "scope_id": scope_id, "reason": "energy_ledger_scope_contract_invalid"})
                continue
            try:
                parsed_kappa = {str(key): float(value) for key, value in kappa.items()}
            except (TypeError, ValueError):
                failures.append({"step_id": step_id, "scope_id": scope_id, "reason": "energy_ledger_kappa_invalid"})
                continue
            if set(parsed_kappa) != basis_ids or any(not math.isfinite(value) or value < 0.0 for value in parsed_kappa.values()):
                failures.append({"step_id": step_id, "scope_id": scope_id, "reason": "energy_ledger_kappa_invalid"})
            if scope_kind == "fixed_scene":
                if scope_id != "fixed_scene" or any(value != 1.0 for value in parsed_kappa.values()):
                    failures.append({"step_id": step_id, "scope_id": scope_id, "reason": "fixed_scene_kappa_mismatch"})
            else:
                expected_kappa = expected_local_scopes.get(scope_id)
                if expected_kappa is None or stable_digest(parsed_kappa) != stable_digest(expected_kappa):
                    failures.append({"step_id": step_id, "scope_id": scope_id, "reason": "local_scope_kappa_lineage_mismatch"})
            numeric_values: dict[str, float] = {}
            for key in _IMPLICIT_ENERGY_LEDGER_NUMBER_KEYS:
                value = ledger.get(key)
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                    failures.append({"step_id": step_id, "scope_id": scope_id, "reason": f"energy_ledger_{key}_invalid"})
                    continue
                numeric_values[key] = float(value)
            if len(numeric_values) == len(_IMPLICIT_ENERGY_LEDGER_NUMBER_KEYS):
                residual = (numeric_values["energy_after"] - numeric_values["energy_before"]) - (
                    numeric_values["x_internal"]
                    + numeric_values["f_boundary_proxy"]
                    + numeric_values["i_user"]
                    + numeric_values["i_feedback"]
                    - numeric_values["d_decay"]
                    - numeric_values["d_clip"]
                )
                tolerance = ENERGY_RESIDUAL_TAU_ABS + ENERGY_RESIDUAL_TAU_REL * max(
                    1.0,
                    numeric_values["energy_before"],
                    numeric_values["energy_after"],
                    math.fsum(
                        abs(numeric_values[key])
                        for key in ("d_decay", "x_internal", "f_boundary_proxy", "i_user", "i_feedback", "d_clip")
                    ),
                )
                if not math.isclose(numeric_values["residual"], residual, rel_tol=0.0, abs_tol=1e-15):
                    failures.append({"step_id": step_id, "scope_id": scope_id, "reason": "energy_ledger_residual_recomputation_mismatch"})
                if not math.isclose(numeric_values["residual_tolerance"], tolerance, rel_tol=0.0, abs_tol=1e-18):
                    failures.append({"step_id": step_id, "scope_id": scope_id, "reason": "energy_ledger_tolerance_mismatch"})
                if abs(residual) > tolerance:
                    failures.append({"step_id": step_id, "scope_id": scope_id, "reason": "energy_ledger_residual_exceeds_tolerance"})

        if len(scope_ids) != len(set(scope_ids)) or scope_ids.count("fixed_scene") != 1:
            failures.append({"step_id": step_id, "reason": "energy_ledger_scope_identity_invalid"})
        actual_local_scope_ids = set(scope_ids) - {"fixed_scene"}
        expected_local_scope_ids = set(expected_local_scopes)
        if actual_local_scope_ids != expected_local_scope_ids:
            failures.append(
                {
                    "step_id": step_id,
                    "reason": "energy_ledger_scope_set_mismatch",
                    "missing_scope_ids": sorted(
                        expected_local_scope_ids - actual_local_scope_ids
                    ),
                    "extra_scope_ids": sorted(
                        actual_local_scope_ids - expected_local_scope_ids
                    ),
                }
            )

        try:
            recomputed_state = advance_implicit_field_state(
                previous_state,
                bases,
                user_input_projection=step.get("raw_user_input_projection") or {},
                feedback_input_projection=step.get("raw_five_phase_feedback_input_projection") or {},
                local_energy_scopes=expected_local_scopes,
            )
        except (KeyError, TypeError, ValueError) as exc:
            failures.append({"step_id": step_id, "reason": "energy_ledger_transition_recompute_failed", "message": str(exc)})
            continue
        recomputed_response = recomputed_state.get("energy_summary", {}).get("density_response", {})
        comparisons = {
            "realized_user_projection_mismatch": (step.get("realized_user_input_projection") or {}, recomputed_response.get("realized_user_projection") or {}),
            "realized_feedback_projection_mismatch": (
                step.get("realized_five_phase_feedback_input_projection") or {},
                recomputed_response.get("realized_feedback_projection") or {},
            ),
            "merged_realized_projection_mismatch": (step.get("merged_realized_input_projection") or {}, recomputed_response.get("merged_realized_projection") or {}),
            "energy_ledgers_recompute_mismatch": (ledgers, recomputed_response.get("ledgers") or []),
            "result_coefficients_recompute_mismatch": (result_state.get("basis_coefficients") or {}, recomputed_state.get("basis_coefficients") or {}),
            "runtime_cost_recompute_mismatch": (step.get("runtime_cost_summary") or {}, recomputed_state.get("runtime_cost_summary") or {}),
        }
        for reason, (actual, expected) in comparisons.items():
            if stable_digest(actual) != stable_digest(expected):
                failures.append({"step_id": step_id, "reason": reason})
        digest_values = {
            "input_projection_digest_mismatch": (step.get("input_projection_digest"), step.get("merged_realized_input_projection") or {}),
            "merged_input_projection_digest_mismatch": (step.get("merged_input_projection_digest"), step.get("merged_realized_input_projection") or {}),
            "user_input_projection_digest_mismatch": (step.get("user_input_projection_digest"), step.get("realized_user_input_projection") or {}),
        }
        for reason, (actual_digest, value) in digest_values.items():
            if actual_digest != stable_digest(value):
                failures.append({"step_id": step_id, "reason": reason})

    return failures


def _check_implicit_live_energy_ledgers(report_inputs: dict[str, Any]) -> CompletionCheck:
    failures = implicit_live_energy_ledger_failures(report_inputs)
    return _completion_check(
        "implicit_live_energy_ledger_status",
        not failures,
        {"failures": failures[:20]},
    )


def _check_implicit_live_interaction_audits(report_inputs: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    state_ids = {str(_implicit_dict(state).get("implicit_field_state_id")) for state in report_inputs.get("implicit_field_states", [])}
    basis_ids = {str(_implicit_dict(basis).get("basis_id")) for basis in report_inputs.get("implicit_basis_records", [])}
    frame_ids = {str(_frame_value(frame, "frame_id", "")) for frame in report_inputs.get("projection_frames", [])}
    ray_ids = {str(_implicit_dict(ray).get("ray_sample_record_id")) for ray in report_inputs.get("implicit_ray_sample_records", [])}
    request_ids = {str(_implicit_dict(request).get("request_id")) for request in report_inputs.get("implicit_refinement_requests", [])}
    patch_ids = {str(_implicit_dict(patch).get("patch_id")) for patch in report_inputs.get("implicit_refinement_patches", [])}
    audits = [_implicit_dict(record) for record in report_inputs.get("implicit_interaction_audits", [])]
    audit_identity_fields = {
        "audit_id": [str(audit.get("audit_id", "")) for audit in audits],
        "command_id": [str(audit.get("command_id", "")) for audit in audits],
        "request_id": [str(audit.get("request_id", "")) for audit in audits],
        "accepted_sequence": [audit.get("accepted_sequence") for audit in audits],
    }
    for field_name, values in audit_identity_fields.items():
        if (
            any(
                value in {None, ""}
                or (field_name == "accepted_sequence" and (isinstance(value, bool) or not isinstance(value, int)))
                for value in values
            )
            or len(values) != len(set(values))
        ):
            failures.append({"reason": "interaction_audit_identity_not_unique", "field": field_name})
    for audit in audits:
        if audit.get("schema") != "implicit_interaction_audit":
            failures.append({"audit_id": audit.get("audit_id"), "reason": "schema_mismatch"})
        if audit.get("status") == "applied":
            if str(audit.get("result_state_id")) not in state_ids:
                failures.append({"audit_id": audit.get("audit_id"), "reason": "missing_result_state"})
            if not audit.get("resulting_projection_frame_ids"):
                failures.append({"audit_id": audit.get("audit_id"), "reason": "missing_resulting_projection_frames"})
            for frame_id in audit.get("resulting_projection_frame_ids", []):
                if str(frame_id) not in frame_ids:
                    failures.append({"audit_id": audit.get("audit_id"), "frame_id": frame_id, "reason": "unknown_resulting_projection_frame"})
            for ray_id in audit.get("resulting_ray_sample_record_ids", []):
                if str(ray_id) not in ray_ids:
                    failures.append({"audit_id": audit.get("audit_id"), "ray_id": ray_id, "reason": "unknown_resulting_ray_sample"})
        for basis_id in audit.get("target_basis_ids", []):
            if str(basis_id) not in basis_ids:
                failures.append({"audit_id": audit.get("audit_id"), "basis_id": basis_id, "reason": "unknown_target_basis"})
        if audit.get("tool") == "implicit_refine_probe":
            if str(audit.get("refinement_request_id")) not in request_ids:
                failures.append({"audit_id": audit.get("audit_id"), "reason": "missing_refinement_request"})
            if str(audit.get("refinement_patch_id")) not in patch_ids:
                failures.append({"audit_id": audit.get("audit_id"), "reason": "missing_refinement_patch"})
    return _completion_check("implicit_live_interaction_audit_status", not failures, {"audit_count": len(audits), "failures": failures[:20]})


def _check_implicit_live_visible_delta(report_inputs: dict[str, Any]) -> CompletionCheck:
    audits = [_implicit_dict(record) for record in report_inputs.get("implicit_interaction_audits", [])]
    applied_audit_count = len([audit for audit in audits if audit.get("status") == "applied"])
    images = [_implicit_dict(record) for record in report_inputs.get("implicit_spectral_image_planes", [])]
    states = [_implicit_dict(record) for record in report_inputs.get("implicit_field_states", [])]
    image_digests = {str(image.get("image_digest")) for image in images}
    state_digests = {str(state.get("state_digest")) for state in states}
    failures: list[dict[str, Any]] = []
    if applied_audit_count and len(image_digests) <= 1:
        failures.append({"reason": "interaction_without_visible_image_delta"})
    if applied_audit_count and len(state_digests) <= 1:
        failures.append({"reason": "interaction_without_state_delta"})
    return _completion_check(
        "implicit_live_visible_delta_status",
        not failures,
        {"applied_audit_count": applied_audit_count, "image_digest_count": len(image_digests), "state_digest_count": len(state_digests), "failures": failures[:20]},
    )


def implicit_projection_frame_lineage_failures(
    report_inputs: Mapping[str, Any],
) -> list[dict[str, Any]]:
    states = [
        _implicit_dict(record) for record in report_inputs.get("implicit_field_states", [])
    ]
    states_by_id = {
        str(state.get("implicit_field_state_id", "")): state for state in states
    }
    failures: list[dict[str, Any]] = []
    for frame in report_inputs.get("projection_frames", []):
        frame_id = str(_frame_value(frame, "frame_id", ""))
        frame_tick = int(_frame_value(frame, "tick", -1))
        payload = _spectral_frame_payload(frame)
        semantics = payload.get("timeline_semantics")
        if not isinstance(semantics, Mapping):
            failures.append({"frame_id": frame_id, "reason": "missing_timeline_semantics"})
            continue
        source_state_id = str(semantics.get("source_world_state_id", ""))
        source_state = states_by_id.get(source_state_id)
        frame_source_ids = {
            str(value) for value in _frame_value(frame, "source_record_ids", [])
        }
        if (
            semantics.get("schema") != "projection_timeline_semantics_v1"
            or semantics.get("is_authority_state") is not False
        ):
            failures.append({"frame_id": frame_id, "reason": "timeline_semantics_contract_mismatch"})
        if source_state is None:
            failures.append({"frame_id": frame_id, "reason": "missing_source_world_state"})
            continue
        if (
            str(semantics.get("source_world_state_digest", ""))
            != str(source_state.get("state_digest", ""))
            or int(semantics.get("world_tick", -2)) != int(source_state.get("tick", -3))
            or frame_tick != int(source_state.get("tick", -3))
            or str(payload.get("implicit_field_state_id", "")) != source_state_id
            or source_state_id not in frame_source_ids
        ):
            failures.append({"frame_id": frame_id, "reason": "source_world_state_lineage_mismatch"})
    return failures


def _check_implicit_live_projection_runtime(report_inputs: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    for frame in report_inputs.get("projection_frames", []):
        frame_id = str(_frame_value(frame, "frame_id", ""))
        payload = _spectral_frame_payload(frame)
        if payload.get("render_mode") != "implicit_3d_field_observation":
            failures.append({"frame_id": frame_id, "reason": "non_implicit_render_mode"})
        if payload.get("implicit_runtime_mode") not in {None, "live-implicit-3d-field"}:
            failures.append({"frame_id": frame_id, "reason": "runtime_mode_mismatch"})
    failures.extend(implicit_projection_frame_lineage_failures(report_inputs))
    return _completion_check("implicit_live_projection_runtime_status", not failures, {"failures": failures[:20]})


def evaluate_implicit_3d_live_interaction_completion(report_inputs: dict[str, Any]) -> CompletionReport:
    base_report = evaluate_implicit_3d_field_completion(report_inputs)
    live_checks = [
        _check_implicit_live_runtime_mode(report_inputs),
        _check_implicit_live_step_chain(report_inputs),
        _check_implicit_live_energy_ledgers(report_inputs),
        _check_implicit_live_interaction_audits(report_inputs),
        _check_implicit_live_visible_delta(report_inputs),
        _check_implicit_live_projection_runtime(report_inputs),
    ]
    checks = [*base_report.checks, *live_checks]
    overall_status = "passed" if all(check.status == "passed" for check in checks) else "failed"
    return CompletionReport(
        overall_status=overall_status,
        checks=checks,
        summary={
            "implicit_3d_live_interaction_completion": overall_status,
            "implicit_basis_count": len(report_inputs.get("implicit_basis_records", [])),
            "implicit_live_step_count": len(report_inputs.get("implicit_live_step_records", [])),
            "implicit_interaction_audit_count": len(report_inputs.get("implicit_interaction_audits", [])),
            "projection_frame_count": len(report_inputs.get("projection_frames", [])),
        },
        audit={
            "authority_boundary": "live implicit interaction updates ImplicitFieldState and retraces the ray camera; viewer pixels remain non-authority",
        },
    )


def _check_implicit_spatial_camera_moves(report_inputs: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    state_by_id = {str(_implicit_dict(state).get("implicit_field_state_id")): _implicit_dict(state) for state in report_inputs.get("implicit_field_states", [])}
    ray_ids = {str(_implicit_dict(ray).get("ray_sample_record_id")) for ray in report_inputs.get("implicit_ray_sample_records", [])}
    image_ids = {str(_implicit_dict(image).get("image_plane_id")) for image in report_inputs.get("implicit_spectral_image_planes", [])}
    frame_ids = {str(_frame_value(frame, "frame_id", "")) for frame in report_inputs.get("projection_frames", [])}
    records = [_implicit_dict(record) for record in report_inputs.get("implicit_camera_move_records", [])]
    if not records:
        failures.append({"reason": "missing_implicit_camera_move_records"})
    for record in records:
        if record.get("schema") != "implicit_camera_move_record":
            failures.append({"camera_move_id": record.get("camera_move_id"), "reason": "schema_mismatch"})
        if record.get("world_state_changed") is not False:
            failures.append({"camera_move_id": record.get("camera_move_id"), "reason": "world_state_changed"})
        if str(record.get("previous_state_id")) != str(record.get("result_state_id")):
            failures.append({"camera_move_id": record.get("camera_move_id"), "reason": "state_id_changed"})
        if str(record.get("previous_state_id")) not in state_by_id:
            failures.append({"camera_move_id": record.get("camera_move_id"), "reason": "missing_previous_state"})
        if str(record.get("result_state_id")) not in state_by_id:
            failures.append({"camera_move_id": record.get("camera_move_id"), "reason": "missing_result_state"})
        previous_state = state_by_id.get(str(record.get("previous_state_id")), {})
        if previous_state and str(previous_state.get("state_digest")) != str(record.get("previous_state_digest")):
            failures.append({"camera_move_id": record.get("camera_move_id"), "reason": "previous_state_digest_mismatch"})
        if str(record.get("previous_state_digest")) != str(record.get("result_state_digest")) or record.get("state_digest_unchanged") is not True:
            failures.append({"camera_move_id": record.get("camera_move_id"), "reason": "state_digest_changed"})
        if str(record.get("source_projection_frame_id")) not in frame_ids:
            failures.append({"camera_move_id": record.get("camera_move_id"), "reason": "missing_source_projection_frame"})
        if str(record.get("result_ray_sample_record_id")) not in ray_ids:
            failures.append({"camera_move_id": record.get("camera_move_id"), "reason": "missing_result_ray"})
        if str(record.get("result_image_plane_id")) not in image_ids:
            failures.append({"camera_move_id": record.get("camera_move_id"), "reason": "missing_result_image"})
        if str(record.get("result_projection_frame_id")) not in frame_ids:
            failures.append({"camera_move_id": record.get("camera_move_id"), "reason": "missing_result_frame"})
    return _completion_check("implicit_spatial_camera_move_status", not failures, {"camera_move_count": len(records), "failures": failures[:20]})


def _check_implicit_spatial_records(report_inputs: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    camera_move_ids = {str(_implicit_dict(record).get("camera_move_id")) for record in report_inputs.get("implicit_camera_move_records", [])}
    ray_ids = {str(_implicit_dict(ray).get("ray_sample_record_id")) for ray in report_inputs.get("implicit_ray_sample_records", [])}
    records = [_implicit_dict(record) for record in report_inputs.get("implicit_spatial_consistency_records", [])]
    if not records:
        failures.append({"reason": "missing_implicit_spatial_consistency_records"})
    for record in records:
        if record.get("schema") != "implicit_spatial_consistency_record":
            failures.append({"spatial_consistency_id": record.get("spatial_consistency_id"), "reason": "schema_mismatch"})
        if str(record.get("camera_move_id")) not in camera_move_ids:
            failures.append({"spatial_consistency_id": record.get("spatial_consistency_id"), "reason": "unknown_camera_move"})
        if str(record.get("before_ray_sample_record_id")) not in ray_ids or str(record.get("after_ray_sample_record_id")) not in ray_ids:
            failures.append({"spatial_consistency_id": record.get("spatial_consistency_id"), "reason": "unknown_ray_sample"})
        if record.get("state_digest_unchanged") is not True:
            failures.append({"spatial_consistency_id": record.get("spatial_consistency_id"), "reason": "state_digest_changed"})
        if record.get("ray_geometry_changed") is not True:
            failures.append({"spatial_consistency_id": record.get("spatial_consistency_id"), "reason": "ray_geometry_not_changed"})
        if record.get("image_digest_changed") is not True:
            failures.append({"spatial_consistency_id": record.get("spatial_consistency_id"), "reason": "image_content_digest_not_changed"})
        if len(record.get("shared_target_motion", [])) < 2:
            failures.append({"spatial_consistency_id": record.get("spatial_consistency_id"), "reason": "insufficient_shared_target_motion"})
        if float(record.get("parallax_ratio", 0.0)) < 1.15:
            failures.append({"spatial_consistency_id": record.get("spatial_consistency_id"), "reason": "parallax_below_threshold"})
        if record.get("status") != "passed":
            failures.append({"spatial_consistency_id": record.get("spatial_consistency_id"), "reason": "spatial_status_not_passed", "status": record.get("status")})
    return _completion_check("implicit_spatial_consistency_status", not failures, {"spatial_record_count": len(records), "failures": failures[:20]})


def _check_implicit_observation_channels(report_inputs: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    required_channels = {"depth_u16", "opacity_u16", "transmittance_u16", "normal_hint_rgb8", "dominant_basis_index_u16"}
    images = [_implicit_dict(image) for image in report_inputs.get("implicit_spectral_image_planes", [])]
    if not images:
        failures.append({"reason": "missing_implicit_spectral_image_planes"})
    for image in images:
        image_id = str(image.get("image_plane_id"))
        channels = {str(tile.get("channel")) for tile in image.get("observation_channel_tiles", [])}
        missing = sorted(required_channels - channels)
        if missing:
            failures.append({"image_plane_id": image_id, "reason": "missing_observation_channels", "missing": missing})
        if not str(image.get("image_content_digest", "")).startswith("sha256:"):
            failures.append({"image_plane_id": image_id, "reason": "missing_image_content_digest"})
        if not image.get("dominant_basis_table"):
            failures.append({"image_plane_id": image_id, "reason": "missing_dominant_basis_table"})
        geometry = image.get("ray_geometry_reference", {})
        if not isinstance(geometry, dict) or not geometry.get("source_observer_path_record_id"):
            failures.append({"image_plane_id": image_id, "reason": "missing_ray_geometry_reference"})
        if not image.get("shared_basis_centroids"):
            failures.append({"image_plane_id": image_id, "reason": "missing_shared_basis_centroids"})
    return _completion_check("implicit_observation_channel_status", not failures, {"image_count": len(images), "failures": failures[:20]})


def _check_implicit_observed_structures(report_inputs: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    basis_ids = {str(_implicit_dict(basis).get("basis_id")) for basis in report_inputs.get("implicit_basis_records", [])}
    structures = [_implicit_dict(record) for record in report_inputs.get("implicit_observed_structure_records", [])]
    if not structures:
        failures.append({"reason": "missing_implicit_observed_structure_records"})
    for structure in structures:
        if structure.get("schema") != "implicit_observed_structure_record":
            failures.append({"structure_id": structure.get("structure_id"), "reason": "schema_mismatch"})
        if structure.get("is_authority_state") is not False:
            failures.append({"structure_id": structure.get("structure_id"), "reason": "authority_structure"})
        for basis_id in structure.get("basis_ids", []):
            if str(basis_id) not in basis_ids:
                failures.append({"structure_id": structure.get("structure_id"), "basis_id": basis_id, "reason": "unknown_basis"})
        if not structure.get("source_ray_sample_record_ids"):
            failures.append({"structure_id": structure.get("structure_id"), "reason": "missing_ray_source"})
    return _completion_check("implicit_observed_structure_status", not failures, {"structure_count": len(structures), "failures": failures[:20]})


def _check_implicit_spatial_interaction_targets(report_inputs: dict[str, Any]) -> CompletionCheck:
    from world_engine.implicit_ray_camera import ray_direction_for_index, ray_point_for_index

    failures: list[dict[str, Any]] = []
    structures = {str(_implicit_dict(record).get("structure_id")): _implicit_dict(record) for record in report_inputs.get("implicit_observed_structure_records", [])}
    ray_by_id = {str(_implicit_dict(ray).get("ray_sample_record_id")): _implicit_dict(ray) for ray in report_inputs.get("implicit_ray_sample_records", [])}
    basis_ids = {str(_implicit_dict(basis).get("basis_id")) for basis in report_inputs.get("implicit_basis_records", [])}
    audits = [_implicit_dict(record) for record in report_inputs.get("implicit_interaction_audits", [])]
    for audit in audits:
        if audit.get("status") != "applied":
            continue
        audit_id = str(audit.get("audit_id"))
        structure_id = str(audit.get("target_structure_id") or "")
        if structure_id not in structures:
            failures.append({"audit_id": audit_id, "reason": "unknown_target_structure"})
        ray_id = str(audit.get("target_ray_id") or audit.get("source_ray_sample_record_id"))
        ray = ray_by_id.get(ray_id)
        if not ray:
            failures.append({"audit_id": audit_id, "reason": "unknown_target_ray"})
            continue
        for basis_id in audit.get("target_basis_ids", []):
            if str(basis_id) not in basis_ids:
                failures.append({"audit_id": audit_id, "basis_id": basis_id, "reason": "unknown_target_basis"})
        target_index = int(audit.get("target_ray_index", -1))
        image_shape = ray.get("image_shape", [])
        if target_index < 0:
            failures.append({"audit_id": audit_id, "reason": "missing_target_ray_index"})
            continue
        expected_direction = ray_direction_for_index(ray.get("camera_pose", {}), image_shape, target_index)
        actual_direction = [float(value) for value in audit.get("target_ray_direction_world_3d", [])]
        if len(actual_direction) != 3 or max(abs(actual_direction[index] - expected_direction[index]) for index in range(3)) > 1e-5:
            failures.append({"audit_id": audit_id, "reason": "target_ray_direction_not_replayable"})
        hit_depth = audit.get("target_hit_depth")
        if hit_depth is not None:
            expected_point = ray_point_for_index(ray.get("camera_pose", {}), image_shape, target_index, float(hit_depth))
            actual_point = [float(value) for value in audit.get("target_world_3d", [])]
            if len(actual_point) != 3 or max(abs(actual_point[index] - expected_point[index]) for index in range(3)) > 1e-3:
                failures.append({"audit_id": audit_id, "reason": "target_world_point_not_replayable"})
        if not audit.get("target_basis_ids"):
            failures.append({"audit_id": audit_id, "reason": "target_structure_without_basis_authority"})
        if audit.get("target_hit_source") == "nearest_basis_fallback":
            failures.append({"audit_id": audit_id, "reason": "target_not_ray_observation_derived"})
    return _completion_check("implicit_spatial_interaction_target_status", not failures, {"audit_count": len(audits), "failures": failures[:20]})


def _check_projection_timeline_semantics(report_inputs: dict[str, Any]) -> CompletionCheck:
    failures: list[dict[str, Any]] = []
    previous_world_tick = None
    valid_frame_kinds = {
        "initial_observation",
        "world_step_observation",
        "camera_only_observation",
        "camera_world_step_observation",
        "interaction_step_observation",
        "debug_replay_frame",
    }
    valid_tracks = {"world_run", "camera_path", "debug_all"}
    for frame in report_inputs.get("projection_frames", []):
        frame_id = str(_frame_value(frame, "frame_id", ""))
        frame_tick = int(_frame_value(frame, "tick", -2))
        payload = _spectral_frame_payload(frame)
        semantics = payload.get("timeline_semantics")
        if not isinstance(semantics, dict):
            failures.append({"frame_id": frame_id, "reason": "missing_timeline_semantics"})
            continue
        if semantics.get("schema") != "projection_timeline_semantics_v1":
            failures.append({"frame_id": frame_id, "reason": "invalid_timeline_schema"})
        frame_kind = semantics.get("frame_kind")
        if frame_kind not in valid_frame_kinds:
            failures.append({"frame_id": frame_id, "reason": "invalid_frame_kind", "frame_kind": frame_kind})
        playback_track = semantics.get("playback_track")
        if playback_track not in valid_tracks:
            failures.append({"frame_id": frame_id, "reason": "invalid_playback_track", "playback_track": playback_track})
        if int(semantics.get("world_tick", -1)) != frame_tick:
            failures.append({"frame_id": frame_id, "reason": "world_tick_does_not_match_frame_tick"})
        if semantics.get("is_authority_state") is not False:
            failures.append({"frame_id": frame_id, "reason": "timeline_claims_authority"})
        window = semantics.get("world_tick_window")
        if not isinstance(window, list) or len(window) != 2:
            failures.append({"frame_id": frame_id, "reason": "invalid_world_tick_window"})
            window = [frame_tick, frame_tick]
        world_advanced = semantics.get("world_advanced")
        camera_moved = semantics.get("camera_moved")
        if not isinstance(world_advanced, bool):
            failures.append({"frame_id": frame_id, "reason": "world_advanced_not_bool"})
            world_advanced = False
        if not isinstance(camera_moved, bool):
            failures.append({"frame_id": frame_id, "reason": "camera_moved_not_bool"})
            camera_moved = False
        if world_advanced is False and int(window[0]) != int(window[1]):
            failures.append({"frame_id": frame_id, "reason": "non_advanced_frame_has_tick_window"})
        if camera_moved:
            if not semantics.get("camera_action"):
                failures.append({"frame_id": frame_id, "reason": "camera_moved_without_action"})
            if not semantics.get("previous_camera_pose_digest") or not semantics.get("result_camera_pose_digest"):
                failures.append({"frame_id": frame_id, "reason": "camera_moved_without_pose_digests"})
        if frame_kind == "camera_only_observation":
            if world_advanced or not camera_moved:
                failures.append({"frame_id": frame_id, "reason": "invalid_camera_only_semantics"})
            if not semantics.get("source_camera_move_id"):
                failures.append({"frame_id": frame_id, "reason": "camera_only_missing_source_camera_move"})
        if frame_kind == "world_step_observation" and (not world_advanced or camera_moved):
            failures.append({"frame_id": frame_id, "reason": "invalid_world_step_semantics"})
        if frame_kind == "camera_world_step_observation":
            if not world_advanced or not camera_moved:
                failures.append({"frame_id": frame_id, "reason": "invalid_camera_world_step_semantics"})
            if semantics.get("source_camera_move_id"):
                failures.append({"frame_id": frame_id, "reason": "camera_world_step_cites_pure_camera_move"})
        if frame_kind == "interaction_step_observation":
            if not world_advanced or not semantics.get("source_interaction_audit_ids"):
                failures.append({"frame_id": frame_id, "reason": "invalid_interaction_step_semantics"})
        if playback_track == "world_run":
            world_tick = int(semantics.get("world_tick", -1))
            if previous_world_tick is not None and world_tick < previous_world_tick:
                failures.append({"frame_id": frame_id, "reason": "world_run_tick_moved_backward"})
            previous_world_tick = world_tick
    if not report_inputs.get("projection_frames"):
        failures.append({"reason": "missing_projection_frames"})
    return _completion_check("timeline_semantics", not failures, {"failures": failures[:20]})


def evaluate_implicit_3d_spatial_observation_completion(report_inputs: dict[str, Any]) -> CompletionReport:
    base_report = evaluate_implicit_3d_live_interaction_completion(report_inputs)
    spatial_checks = [
        _check_projection_timeline_semantics(report_inputs),
        _check_implicit_spatial_camera_moves(report_inputs),
        _check_implicit_spatial_records(report_inputs),
        _check_implicit_observation_channels(report_inputs),
        _check_implicit_observed_structures(report_inputs),
        _check_implicit_spatial_interaction_targets(report_inputs),
    ]
    checks = [*base_report.checks, *spatial_checks]
    overall_status = "passed" if all(check.status == "passed" for check in checks) else "failed"
    return CompletionReport(
        overall_status=overall_status,
        checks=checks,
        summary={
            "implicit_3d_spatial_observation_completion": overall_status,
            "implicit_camera_move_count": len(report_inputs.get("implicit_camera_move_records", [])),
            "implicit_spatial_consistency_record_count": len(report_inputs.get("implicit_spatial_consistency_records", [])),
            "implicit_observed_structure_count": len(report_inputs.get("implicit_observed_structure_records", [])),
        },
        audit={
            "authority_boundary": "camera movement retraces implicit ray artifacts; structures and targets are observation records, not mesh/object authority",
        },
    )
