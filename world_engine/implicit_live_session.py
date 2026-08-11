from __future__ import annotations

import copy
import functools
import hashlib
import json
import math
import threading
from dataclasses import replace
from typing import Any, Mapping, Sequence

from world_engine.contracts import FieldState, ProjectionFrame
from world_engine.five_phase import (
    FivePhaseAgentStateRecord,
    FivePhaseConstraintSetRecord,
    FivePhaseFeedbackRecord,
    FivePhaseFieldRecord,
    FivePhasePatternRecord,
    FivePhaseResidualConstraintRecord,
    FivePhaseTraceRecord,
)
from world_engine.implicit_baseline import build_implicit_baseline_comparison_record
from world_engine.implicit_camera_control import (
    ALLOWED_IMPLICIT_CAMERA_ACTIONS,
    apply_implicit_camera_move,
    build_implicit_camera_move_record,
    complete_implicit_camera_move_record,
    validate_implicit_camera_move_request,
)
from world_engine.implicit_field import (
    build_implicit_field_authority_certificate,
    build_implicit_field_state,
    validate_implicit_field_state,
)
from world_engine.implicit_field_runtime import advance_implicit_field_state
from world_engine.five_phase_live import (
    build_five_phase_initial_response_context,
    build_five_phase_live_artifacts,
    build_five_phase_transition_response_context,
    five_phase_feedback_to_implicit_input_projection,
    materialize_five_phase_pattern_response,
    measure_five_phase_feedback_response,
)
from world_engine.five_phase_runtime import build_agent_repair_feedback, build_agent_state_from_pattern
from world_engine.implicit_interaction import (
    SUPPORTED_IMPLICIT_TOOLS,
    build_implicit_pending_control_descriptor,
    build_implicit_interaction_audit,
    canonical_implicit_tick_count,
    implicit_request_to_input_projection,
    materialize_implicit_raw_control_projection,
    record_implicit_interaction_application,
    target_basis_from_image_xy,
    validate_implicit_interaction_request,
)
from world_engine.implicit_ray_camera import (
    build_implicit_observer_path_record,
    trace_implicit_ray_camera,
    validate_implicit_observer_path_record,
    validate_implicit_ray_sample_record,
)
from world_engine.implicit_refinement import (
    apply_refinement_patch_to_implicit_state,
    build_implicit_local_refinement_patch,
    build_implicit_local_refinement_request,
)
from world_engine.implicit_spatial_consistency import build_implicit_spatial_consistency_record
from world_engine.implicit_structure_observation import extract_implicit_observed_structures
from world_engine.projection_frames import attach_implicit_field_payload_to_projection_frame
from world_engine.realtime_projection_renderer import validate_realtime_render_frame_request
from world_engine.signature_scene_runtime import build_implicit_signature_scene
from world_engine.solar_earth_runtime import (
    ALLOWED_SOLAR_EARTH_SENSOR_BAND_MODES,
    ALLOWED_SOLAR_EARTH_CAMERA_ACTIONS,
    advance_solar_earth_scene,
    apply_solar_earth_camera_move,
    build_demo_solar_earth_scene_for_source_package,
    default_solar_earth_camera_pose,
    project_solar_earth_scene,
    refine_planet_local_region,
    request_planet_local_refinement,
)


RUNTIME_MODE = "live-implicit-3d-field"
DEFAULT_OBSERVER_ID = "observer::implicit-pinhole"
TIMELINE_SEMANTICS_SCHEMA = "projection_timeline_semantics_v1"

INITIAL_OBSERVATION = "initial_observation"
WORLD_STEP_OBSERVATION = "world_step_observation"
CAMERA_ONLY_OBSERVATION = "camera_only_observation"
CAMERA_WORLD_STEP_OBSERVATION = "camera_world_step_observation"
INTERACTION_STEP_OBSERVATION = "interaction_step_observation"
DEBUG_REPLAY_FRAME = "debug_replay_frame"

WORLD_RUN_TRACK = "world_run"
CAMERA_PATH_TRACK = "camera_path"
DEBUG_ALL_TRACK = "debug_all"

IMPLICIT_LIVE_SESSION_SNAPSHOT_SCHEMA = "implicit_live_session_snapshot_v2"
KAPPA_NORM_MIN = 1e-8
MAX_DUE_CONTROLS_PER_TICK = 8
MAX_PENDING_CONTROLS = 64
MAX_ACTIVE_ENERGY_SCOPES = 64
MAX_USER_INPUT_L1_PER_TICK = 1.0
MAX_FEEDBACK_INPUT_L1_PER_TICK = 0.1
ENERGY_SCOPE_RELAXATION_TICKS = 8
FEEDBACK_ERROR_IMPROVEMENT_TOLERANCE = 1e-12

_MUTATION_HISTORY_ATTRIBUTES = (
    "implicit_field_states",
    "authority_certificates",
    "evaluation_records",
    "ray_sample_records",
    "image_planes",
    "projection_frames",
    "observer_path_records",
    "camera_move_records",
    "spatial_consistency_records",
    "observed_structure_records",
    "interaction_audits",
    "interaction_transcript",
    "implicit_live_steps",
    "five_phase_live_bridges",
    "five_phase_live_field_states",
    "five_phase_phase_fields",
    "five_phase_constraint_sets",
    "five_phase_patterns",
    "five_phase_lifecycle_records",
    "five_phase_traces",
    "five_phase_residual_constraints",
    "five_phase_agent_states",
    "five_phase_feedback_records",
    "five_phase_feedback_applications",
    "five_phase_live_steps",
    "refinement_requests",
    "refinement_patches",
    "baseline_comparisons",
)


def _session_locked(method):
    @functools.wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._session_lock:
            return method(self, *args, **kwargs)

    return wrapped


def _solar_earth_camera_substep_count(request: Mapping[str, Any], camera_pose: Mapping[str, Any], ticks: int) -> int:
    raw_steps = request.get("camera_steps_per_world_tick", camera_pose.get("camera_steps_per_world_tick", 1))
    try:
        steps_per_tick = int(raw_steps)
    except (TypeError, ValueError):
        steps_per_tick = 1
    steps_per_tick = max(1, min(16, steps_per_tick))
    return max(1, int(ticks)) * steps_per_tick


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _snapshot_digest(snapshot: Mapping[str, Any]) -> str:
    payload = copy.deepcopy(dict(snapshot))
    payload.pop("snapshot_digest", None)
    solar_scene = payload.get("solar_earth_scene")
    if solar_scene is not None and hasattr(solar_scene, "to_dict"):
        payload["solar_earth_scene"] = solar_scene.to_dict()
    return _canonical_digest(payload)


def _response_value_matches(actual: Any, expected: Any) -> bool:
    if isinstance(expected, float):
        try:
            return math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=1e-12)
        except (TypeError, ValueError):
            return False
    if isinstance(expected, (Mapping, list, tuple)):
        return _canonical_digest(actual) == _canonical_digest(expected)
    return actual == expected


def _require_unique_record_ids(records: Sequence[Any], *, family: str) -> None:
    identifiers: list[str] = []
    for record in records:
        if hasattr(record, "record_id"):
            identifier = str(record.record_id)
        elif isinstance(record, Mapping):
            identifier = str(
                record.get("step_id")
                or record.get("live_step_id")
                or record.get("application_record_id")
                or record.get("record_id")
                or ""
            )
        else:
            identifier = ""
        if not identifier:
            raise ValueError(f"{family} record requires identifier")
        identifiers.append(identifier)
    if len(identifiers) != len(set(identifiers)):
        raise ValueError(f"duplicate future-affecting {family} record id")


def _refresh_image_plane_digest(image_plane: Mapping[str, Any]) -> str:
    digest_payload = {
        "image_plane_id": image_plane.get("image_plane_id"),
        "tiles": image_plane.get("tiles", []),
        "camera_ray_bundle": image_plane.get("camera_ray_bundle", {}),
        "camera_scale_state": image_plane.get("camera_scale_state", {}),
        "surface_sample_ids": [sample.get("sample_id") for sample in image_plane.get("surface_readability_samples", [])],
        "volume_segment_ids": [segment.get("segment_id") for segment in image_plane.get("volume_layer_segments", [])],
        "visible_response_id": (image_plane.get("visible_interaction_response") or {}).get("visible_response_id"),
        "projection_response_overlay_ids": [
            overlay.get("overlay_id") for overlay in image_plane.get("projection_response_overlays", [])
        ],
    }
    return _canonical_digest(digest_payload)


def _normalize_vec3(values: Sequence[float]) -> list[float]:
    length = math.sqrt(sum(float(value) * float(value) for value in values))
    if length <= 1e-12:
        raise ValueError("cannot normalize zero vector")
    return [float(value) / length for value in values]


def _ensure_state_digest(state: dict[str, Any]) -> None:
    if not state.get("state_digest"):
        digest_input = {key: value for key, value in state.items() if key != "state_digest"}
        state["state_digest"] = _canonical_digest(digest_input)


def _timeline_semantics(
    *,
    frame_kind: str,
    world_tick: int,
    world_tick_window: tuple[int, int],
    world_advanced: bool,
    camera_moved: bool,
    camera_pose_id: str,
    camera_action: str | None,
    previous_camera_pose_digest: str | None,
    result_camera_pose_digest: str | None,
    source_world_state_id: str,
    source_world_state_digest: str,
    source_live_step_ids: Sequence[str],
    source_camera_move_id: str | None,
    source_interaction_audit_ids: Sequence[str],
    playback_track: str,
    sequence_index: int,
) -> dict[str, Any]:
    return {
        "schema": TIMELINE_SEMANTICS_SCHEMA,
        "frame_kind": frame_kind,
        "world_tick": int(world_tick),
        "world_tick_window": [int(world_tick_window[0]), int(world_tick_window[1])],
        "world_advanced": bool(world_advanced),
        "camera_moved": bool(camera_moved),
        "camera_action": camera_action,
        "camera_pose_id": str(camera_pose_id),
        "previous_camera_pose_digest": previous_camera_pose_digest,
        "result_camera_pose_digest": result_camera_pose_digest,
        "source_world_state_id": str(source_world_state_id),
        "source_world_state_digest": str(source_world_state_digest),
        "source_live_step_ids": [str(value) for value in source_live_step_ids],
        "source_camera_move_id": source_camera_move_id,
        "source_interaction_audit_ids": [str(value) for value in source_interaction_audit_ids],
        "playback_track": playback_track,
        "sequence_index": int(sequence_index),
        "is_authority_state": False,
    }


def _merge_projection(projections: Sequence[Mapping[str, Mapping[str, float]]]) -> dict[str, dict[str, float]]:
    merged: dict[str, dict[str, float]] = {}
    for projection in projections:
        for basis_id, channels in projection.items():
            merged.setdefault(str(basis_id), {})
            for channel, value in channels.items():
                merged[str(basis_id)][str(channel)] = merged[str(basis_id)].get(str(channel), 0.0) + float(value)
    return merged


def _projection_l1(projection: Mapping[str, Mapping[str, float]]) -> float:
    return math.fsum(abs(float(value)) for channels in projection.values() for value in channels.values())


def _declared_runtime_projection(
    projection: Mapping[str, Mapping[str, float]],
    bases: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, float]]:
    bases_by_id = {str(basis.get("basis_id", "")): basis for basis in bases}
    result: dict[str, dict[str, float]] = {}
    for basis_id, channels in projection.items():
        basis = bases_by_id.get(str(basis_id))
        if basis is None:
            raise ValueError("input projection references undeclared basis")
        declared_channels = set(map(str, basis.get("channel_weights", {})))
        filtered = {
            str(channel): float(value)
            for channel, value in channels.items()
            if str(channel) in declared_channels
        }
        if filtered:
            result[str(basis_id)] = filtered
    return result


def _attribute_realized_user_projections(
    raw_by_command: Sequence[tuple[str, Mapping[str, Mapping[str, float]]]],
    *,
    aggregate_realized: Mapping[str, Mapping[str, float]],
) -> dict[str, dict[str, dict[str, float]]]:
    attributed: dict[str, dict[str, dict[str, float]]] = {
        str(command_id): {
            str(basis_id): {str(channel): float(value) for channel, value in channels.items()}
            for basis_id, channels in projection.items()
        }
        for command_id, projection in raw_by_command
    }
    basis_channels = {
        (str(basis_id), str(channel))
        for _command_id, projection in raw_by_command
        for basis_id, channels in projection.items()
        for channel in channels
    }
    for basis_id, channel in sorted(basis_channels):
        contributions = [
            (str(command_id), float(projection.get(basis_id, {}).get(channel, 0.0)))
            for command_id, projection in raw_by_command
        ]
        raw_total = math.fsum(value for _command_id, value in contributions)
        realized_total = float(aggregate_realized.get(basis_id, {}).get(channel, 0.0))
        if abs(raw_total - realized_total) <= 1e-15:
            continue
        positive_total = math.fsum(value for _command_id, value in contributions if value > 0.0)
        negative_total = math.fsum(value for _command_id, value in contributions if value < 0.0)
        if negative_total >= 0.0:
            raise ValueError("realized aggregate input cannot be attributed")
        negative_scale = (realized_total - positive_total) / negative_total
        if negative_scale < -1e-12 or negative_scale > 1.0 + 1e-12:
            raise ValueError("realized aggregate dampen cap attribution is outside bounds")
        negative_scale = max(0.0, min(1.0, negative_scale))
        for command_id, value in contributions:
            if value < 0.0:
                attributed.setdefault(command_id, {}).setdefault(basis_id, {})[channel] = value * negative_scale
    return attributed


class ImplicitFieldSession:
    def __init__(
        self,
        *,
        session_id: str,
        run_id: str,
        source_package_name: str,
        source_package_digest: str,
        current_state: dict[str, Any],
        bases: list[dict[str, Any]],
        basis_spatial_index: dict[str, Any],
        observer_path_record: dict[str, Any],
        camera_pose: dict[str, Any],
        image_shape: Sequence[int],
        samples_per_ray: int,
        five_phase_feedback_enabled: bool = True,
    ) -> None:
        self._session_lock = threading.RLock()
        self.session_id = session_id
        self.run_id = run_id
        self.source_package_name = source_package_name
        self.source_package_digest = source_package_digest
        self.current_state = dict(current_state)
        self.bases = [dict(basis) for basis in bases]
        self.basis_spatial_index = dict(basis_spatial_index)
        self.observer_path_record = dict(observer_path_record)
        self.observer_path_records: list[dict[str, Any]] = [dict(observer_path_record)]
        self.camera_pose = dict(camera_pose)
        self.initial_camera_pose = dict(camera_pose)
        self.image_shape = [int(value) for value in image_shape]
        self.samples_per_ray = int(samples_per_ray)
        self.five_phase_feedback_enabled = bool(five_phase_feedback_enabled)
        self.observer_ids = [DEFAULT_OBSERVER_ID]
        self.implicit_field_states: list[dict[str, Any]] = [dict(current_state)]
        self.authority_certificates: list[dict[str, Any]] = []
        self.evaluation_records: list[dict[str, Any]] = []
        self.ray_sample_records: list[dict[str, Any]] = []
        self.image_planes: list[dict[str, Any]] = []
        self.projection_frames: list[ProjectionFrame] = []
        self.camera_move_records: list[dict[str, Any]] = []
        self.spatial_consistency_records: list[dict[str, Any]] = []
        self.observed_structure_records: list[dict[str, Any]] = []
        self.interaction_audits: list[dict[str, Any]] = []
        self._audit_index_by_command: dict[str, int] = {}
        self.interaction_transcript: list[dict[str, Any]] = []
        self.implicit_live_steps: list[dict[str, Any]] = []
        self.five_phase_live_bridges: list[dict[str, Any]] = []
        self.five_phase_live_field_states: list[FieldState] = []
        self.five_phase_phase_fields: list[FivePhaseFieldRecord] = []
        self.five_phase_constraint_sets: list[FivePhaseConstraintSetRecord] = []
        self.five_phase_patterns: list[FivePhasePatternRecord] = []
        self.five_phase_lifecycle_records: list[dict[str, Any]] = []
        self.five_phase_traces: list[FivePhaseTraceRecord] = []
        self.five_phase_residual_constraints: list[FivePhaseResidualConstraintRecord] = []
        self.five_phase_agent_states: list[FivePhaseAgentStateRecord] = []
        self.five_phase_feedback_records: list[FivePhaseFeedbackRecord] = []
        self.five_phase_feedback_applications: list[dict[str, Any]] = []
        self.five_phase_live_steps: list[dict[str, Any]] = []
        self.refinement_requests: list[dict[str, Any]] = []
        self.refinement_patches: list[dict[str, Any]] = []
        self.baseline_comparisons: list[dict[str, Any]] = []
        self.run_step_request_ids: set[str] = set()
        self.render_frame_request_ids: set[str] = set()
        self._pending_inputs: list[dict[str, Any]] = []
        self._accepted_sequence = 0
        self._active_energy_scopes: list[dict[str, Any]] = []
        self._append_five_phase_causal_artifacts(observer_id=DEFAULT_OBSERVER_ID)
        self._append_observation_frame(
            event_kinds=["implicit_ray_observation"],
            frame_kind=INITIAL_OBSERVATION,
            world_advanced=False,
            camera_moved=False,
            world_tick_window=(self.current_tick, self.current_tick),
            playback_track=WORLD_RUN_TRACK,
        )

    @classmethod
    def from_source_package(
        cls,
        *,
        source_package_name: str,
        source_package_digest: str | None = None,
        case_type: str = "implicit_full_scene",
        run_id: str = "implicit-live-session",
        image_shape: Sequence[int] = (24, 16),
        samples_per_ray: int = 8,
        five_phase_feedback_enabled: bool = True,
    ) -> "ImplicitFieldSession":
        digest = source_package_digest or hashlib.sha256(source_package_name.encode("utf-8")).hexdigest()
        scene = build_implicit_signature_scene(
            source_package_name=source_package_name,
            source_package_digest=digest,
            case_type=case_type,
            run_id=run_id,
            ticks=64,
        )
        observer_seed = scene["observer_seed"]
        camera_pose = dict(observer_seed["camera_pose"])
        camera_pose.setdefault("fov_degrees", 50.0)
        observer_path = build_implicit_observer_path_record(
            observer_path_id=f"implicit-observer-path::{run_id}",
            observer_id=DEFAULT_OBSERVER_ID,
            tick_window=[int(scene["implicit_field_state"]["tick"]), 10_000],
            camera_pose_records=[{"tick": int(scene["implicit_field_state"]["tick"]), "camera_pose": camera_pose}],
            source_record_ids=[scene["implicit_field_state"]["implicit_field_state_id"]],
        )
        state = cls._retag_state_static(scene["implicit_field_state"], run_id, int(scene["implicit_field_state"]["tick"]))
        return cls(
            session_id=f"implicit-live-session::{run_id}",
            run_id=run_id,
            source_package_name=source_package_name,
            source_package_digest=digest,
            current_state=state,
            bases=list(scene["implicit_basis_records"]),
            basis_spatial_index=dict(scene["implicit_basis_spatial_index"]),
            observer_path_record=observer_path,
            camera_pose=camera_pose,
            image_shape=image_shape,
            samples_per_ray=samples_per_ray,
            five_phase_feedback_enabled=five_phase_feedback_enabled,
        )

    @classmethod
    def rehydrate_snapshot(
        cls,
        snapshot: Mapping[str, Any],
        *,
        expected_snapshot_digest: str,
        five_phase_feedback_enabled_override: bool | None = None,
    ) -> "ImplicitFieldSession":
        configuration = snapshot.get("configuration")
        if not isinstance(configuration, Mapping):
            raise ValueError("implicit live session snapshot requires configuration")
        session = cls.from_source_package(
            source_package_name=str(configuration.get("source_package_name", "")),
            source_package_digest=str(configuration.get("source_package_digest", "")),
            run_id=str(configuration.get("run_id", "")),
            image_shape=list(configuration.get("image_shape", [])),
            samples_per_ray=int(configuration.get("samples_per_ray", 0)),
            five_phase_feedback_enabled=bool(snapshot.get("five_phase_feedback_enabled", True)),
        )
        session.restore_snapshot(
            snapshot,
            expected_snapshot_digest=expected_snapshot_digest,
            five_phase_feedback_enabled_override=five_phase_feedback_enabled_override,
        )
        return session

    @classmethod
    def replay_interaction_transcript(
        cls,
        snapshot: Mapping[str, Any],
        transcript: Sequence[Mapping[str, Any]],
        *,
        expected_snapshot_digest: str,
        five_phase_feedback_enabled_override: bool | None = None,
    ) -> "ImplicitFieldSession":
        session = cls.rehydrate_snapshot(
            snapshot,
            expected_snapshot_digest=expected_snapshot_digest,
            five_phase_feedback_enabled_override=five_phase_feedback_enabled_override,
        )
        expected_sequence = session._accepted_sequence + 1
        for raw_entry in transcript:
            entry = dict(raw_entry)
            if entry.get("schema") != "implicit_interaction_transcript_entry_v1":
                raise ValueError("interaction replay transcript schema mismatch")
            if int(entry.get("accepted_sequence", -1)) != expected_sequence:
                raise ValueError("interaction replay transcript order mismatch")
            request = entry.get("request")
            if not isinstance(request, Mapping):
                raise ValueError("interaction replay transcript requires request")
            audit = session.apply_interaction(request)
            if str(audit["audit_id"]) != str(entry.get("audit_id", "")):
                raise ValueError("interaction replay audit id mismatch")
            expected_sequence += 1
        return session

    @classmethod
    def start_solar_earth_demo(
        cls,
        *,
        session_id: str = "solar-earth-live",
        source_package_name: str = "source-package-a",
    ) -> "ImplicitFieldSession":
        scene = build_demo_solar_earth_scene_for_source_package(source_package_name=source_package_name, tick=0)
        session = cls.from_source_package(
            source_package_name=source_package_name,
            run_id=session_id,
            image_shape=[96, 64],
            samples_per_ray=8,
        )
        session.session_id = session_id
        session.run_id = session_id
        session.source_package_name = scene.template_binding.source_package_name
        session.source_package_digest = scene.template_binding.source_package_digest
        session.current_state = copy.deepcopy(scene.implicit_state.state)
        session.bases = [copy.deepcopy(basis) for basis in scene.implicit_state.bases]
        session.basis_spatial_index = copy.deepcopy(scene.implicit_state.basis_spatial_index)
        session.implicit_field_states = [copy.deepcopy(session.current_state)]
        session.authority_certificates = []
        session.evaluation_records = []
        session.ray_sample_records = []
        session.image_planes = []
        session.projection_frames = []
        session.camera_move_records = []
        session.spatial_consistency_records = []
        session.observed_structure_records = []
        session.interaction_audits = []
        session._audit_index_by_command = {}
        session.interaction_transcript = []
        session.implicit_live_steps = []
        session.five_phase_live_bridges = []
        session.five_phase_live_field_states = []
        session.five_phase_phase_fields = []
        session.five_phase_constraint_sets = []
        session.five_phase_patterns = []
        session.five_phase_lifecycle_records = []
        session.five_phase_traces = []
        session.five_phase_residual_constraints = []
        session.five_phase_agent_states = []
        session.five_phase_feedback_records = []
        session.five_phase_feedback_applications = []
        session.five_phase_live_steps = []
        session.refinement_requests = []
        session.refinement_patches = []
        session.baseline_comparisons = []
        session.run_step_request_ids = set()
        session.render_frame_request_ids = set()
        session._pending_inputs = []
        session.solar_earth_scene = scene
        session.camera_pose = {**default_solar_earth_camera_pose(scene), "target_lock": "planet_center"}
        session.initial_camera_pose = copy.deepcopy(session.camera_pose)
        session.observer_ids = ["observer::solar-earth-orbit"]
        session._append_solar_earth_projection_frame(event_kinds=["solar_earth_initial_observation"])
        return session

    @property
    def current_tick(self) -> int:
        return int(self.current_state.get("tick", 0))

    @_session_locked
    def manifest(self) -> dict[str, Any]:
        return {
            "schema": "implicit_live_session_manifest",
            "runtime_mode": "solar-earth-layered-spectral-world" if hasattr(self, "solar_earth_scene") else RUNTIME_MODE,
            "session_id": self.session_id,
            "run_id": self.run_id,
            "source_package_name": self.source_package_name,
            "source_package_digest": self.source_package_digest,
            "current_tick": self.current_tick,
            "projection_frame_count": len(self.projection_frames),
            "implicit_field_state_count": len(self.implicit_field_states),
            "implicit_live_step_count": len(self.implicit_live_steps),
            "five_phase_live_step_count": len(self.five_phase_live_steps),
            "five_phase_phase_field_count": len(self.five_phase_phase_fields),
            "five_phase_trace_count": len(self.five_phase_traces),
            "five_phase_feedback_enabled": bool(self.five_phase_feedback_enabled),
            "five_phase_feedback_application_count": len(self.five_phase_feedback_applications),
            "interaction_audit_count": len(self.interaction_audits),
            "camera_move_count": len(self.camera_move_records),
            "spatial_consistency_record_count": len(self.spatial_consistency_records),
            "observed_structure_count": len(self.observed_structure_records),
            "observer_ids": list(self.observer_ids),
            "supported_tools": sorted(SUPPORTED_IMPLICIT_TOOLS),
            "is_authority_state": False,
        }

    @_session_locked
    def to_snapshot(self) -> dict[str, Any]:
        configuration = {
            "session_id": self.session_id,
            "run_id": self.run_id,
            "source_package_name": self.source_package_name,
            "source_package_digest": self.source_package_digest,
            "image_shape": list(self.image_shape),
            "samples_per_ray": int(self.samples_per_ray),
            "observer_ids": list(self.observer_ids),
            "initial_camera_pose": copy.deepcopy(self.initial_camera_pose),
        }
        snapshot = {
            "schema": IMPLICIT_LIVE_SESSION_SNAPSHOT_SCHEMA,
            "configuration": configuration,
            "configuration_digest": _canonical_digest(configuration),
            "current_state": copy.deepcopy(self.current_state),
            "bases": copy.deepcopy(self.bases),
            "basis_spatial_index": copy.deepcopy(self.basis_spatial_index),
            "implicit_field_states": copy.deepcopy(self.implicit_field_states),
            "authority_certificates": copy.deepcopy(self.authority_certificates),
            "evaluation_records": copy.deepcopy(self.evaluation_records),
            "ray_sample_records": copy.deepcopy(self.ray_sample_records),
            "image_planes": copy.deepcopy(self.image_planes),
            "projection_frames": [frame.to_dict() for frame in self.projection_frames],
            "camera_pose": copy.deepcopy(self.camera_pose),
            "observer_path_record": copy.deepcopy(self.observer_path_record),
            "observer_path_records": copy.deepcopy(self.observer_path_records),
            "camera_move_records": copy.deepcopy(self.camera_move_records),
            "spatial_consistency_records": copy.deepcopy(self.spatial_consistency_records),
            "observed_structure_records": copy.deepcopy(self.observed_structure_records),
            "interaction_audits": copy.deepcopy(self.interaction_audits),
            "interaction_transcript": copy.deepcopy(self.interaction_transcript),
            "implicit_live_steps": copy.deepcopy(self.implicit_live_steps),
            "five_phase_live_bridges": copy.deepcopy(self.five_phase_live_bridges),
            "five_phase_live_field_states": [state.to_dict() for state in self.five_phase_live_field_states],
            "five_phase_phase_fields": [record.to_dict() for record in self.five_phase_phase_fields],
            "five_phase_constraint_sets": [record.to_dict() for record in self.five_phase_constraint_sets],
            "five_phase_patterns": [record.to_dict() for record in self.five_phase_patterns],
            "five_phase_lifecycle_records": copy.deepcopy(self.five_phase_lifecycle_records),
            "five_phase_traces": [record.to_dict() for record in self.five_phase_traces],
            "five_phase_residual_constraints": [record.to_dict() for record in self.five_phase_residual_constraints],
            "five_phase_agent_states": [record.to_dict() for record in self.five_phase_agent_states],
            "five_phase_feedback_records": [record.to_dict() for record in self.five_phase_feedback_records],
            "five_phase_feedback_applications": copy.deepcopy(self.five_phase_feedback_applications),
            "five_phase_live_steps": copy.deepcopy(self.five_phase_live_steps),
            "refinement_requests": copy.deepcopy(self.refinement_requests),
            "refinement_patches": copy.deepcopy(self.refinement_patches),
            "baseline_comparisons": copy.deepcopy(self.baseline_comparisons),
            "run_step_request_ids": sorted(self.run_step_request_ids),
            "render_frame_request_ids": sorted(getattr(self, "render_frame_request_ids", set())),
            "pending_inputs": copy.deepcopy(self._pending_inputs),
            "accepted_sequence": int(self._accepted_sequence),
            "active_energy_scopes": copy.deepcopy(self._active_energy_scopes),
            "solar_earth_scene": copy.deepcopy(getattr(self, "solar_earth_scene", None)),
            "five_phase_feedback_enabled": bool(self.five_phase_feedback_enabled),
        }
        snapshot["snapshot_digest"] = _snapshot_digest(snapshot)
        return snapshot

    def snapshot_for_rollback(self) -> dict[str, Any]:
        return self.to_snapshot()

    def _rebuild_audit_index(self) -> None:
        index: dict[str, int] = {}
        for audit_index, audit in enumerate(self.interaction_audits):
            command_id = str(audit.get("command_id", ""))
            if not command_id or command_id in index:
                raise ValueError("interaction audits require unique command_id")
            index[command_id] = audit_index
        self._audit_index_by_command = index

    def _begin_mutation_journal(self) -> dict[str, Any]:
        pending_command_ids = {
            str(item.get("command_id", "")) for item in self._pending_inputs if item.get("command_id")
        }
        audit_backups = {
            self._audit_index_by_command[command_id]: copy.deepcopy(
                self.interaction_audits[self._audit_index_by_command[command_id]]
            )
            for command_id in sorted(pending_command_ids)
            if command_id in self._audit_index_by_command
        }
        return {
            "history_lengths": {
                attribute: len(getattr(self, attribute)) for attribute in _MUTATION_HISTORY_ATTRIBUTES
            },
            "audit_backups": audit_backups,
            "current_state": copy.deepcopy(self.current_state),
            "camera_pose": copy.deepcopy(self.camera_pose),
            "observer_path_record": copy.deepcopy(self.observer_path_record),
            "pending_inputs": copy.deepcopy(self._pending_inputs),
            "accepted_sequence": int(self._accepted_sequence),
            "active_energy_scopes": copy.deepcopy(self._active_energy_scopes),
            "had_solar_earth_scene": hasattr(self, "solar_earth_scene"),
            "solar_earth_scene": copy.deepcopy(getattr(self, "solar_earth_scene", None)),
        }

    def _rollback_mutation_journal(self, journal: Mapping[str, Any]) -> None:
        for attribute, raw_length in journal["history_lengths"].items():
            history = getattr(self, attribute)
            del history[int(raw_length) :]
        for raw_index, audit in journal["audit_backups"].items():
            audit_index = int(raw_index)
            if audit_index >= len(self.interaction_audits):
                raise RuntimeError("mutation journal audit index is no longer available")
            self.interaction_audits[audit_index] = copy.deepcopy(audit)
        self.current_state = copy.deepcopy(journal["current_state"])
        self.camera_pose = copy.deepcopy(journal["camera_pose"])
        self.observer_path_record = copy.deepcopy(journal["observer_path_record"])
        self._pending_inputs = copy.deepcopy(journal["pending_inputs"])
        self._accepted_sequence = int(journal["accepted_sequence"])
        self._active_energy_scopes = copy.deepcopy(journal["active_energy_scopes"])
        if journal["had_solar_earth_scene"]:
            self.solar_earth_scene = copy.deepcopy(journal["solar_earth_scene"])
        elif hasattr(self, "solar_earth_scene"):
            delattr(self, "solar_earth_scene")
        self._rebuild_audit_index()

    @staticmethod
    def _validate_detached_snapshot_candidate(candidate: Mapping[str, Any]) -> None:
        configuration = candidate["configuration"]
        for field_name in ("session_id", "run_id", "source_package_name", "source_package_digest"):
            if not isinstance(configuration.get(field_name), str) or not configuration[field_name]:
                raise ValueError(f"snapshot configuration requires {field_name}")
        image_shape = list(configuration.get("image_shape", []))
        if len(image_shape) != 2 or any(int(value) <= 0 for value in image_shape):
            raise ValueError("snapshot configuration requires positive image_shape")
        if int(configuration.get("samples_per_ray", 0)) <= 0:
            raise ValueError("snapshot configuration requires positive samples_per_ray")

        states = list(candidate["implicit_field_states"])
        states_by_id = {str(state["implicit_field_state_id"]): state for state in states}
        state_ids = [str(state["implicit_field_state_id"]) for state in states]
        if len(state_ids) != len(states_by_id):
            raise ValueError("duplicate future-affecting implicit field state id")
        if not states or state_ids[-1] != str(candidate["current_state"]["implicit_field_state_id"]):
            raise ValueError("snapshot current state is not history head")
        if _canonical_digest(states[-1]) != _canonical_digest(candidate["current_state"]):
            raise ValueError("snapshot current state content differs from history head")
        if candidate.get("solar_earth_scene") is None:
            if len(candidate["implicit_live_steps"]) != len(states) - 1:
                raise ValueError("snapshot ordinary transition history length mismatch")
            if len(candidate["five_phase_live_steps"]) != len(states):
                raise ValueError("snapshot FivePhase transition history length mismatch")

            observer_paths = list(candidate["observer_path_records"])
            observer_path_ids = [
                str(record.get("observer_path_id", "")) for record in observer_paths
            ]
            if (
                not observer_paths
                or any(not value for value in observer_path_ids)
                or len(observer_path_ids) != len(set(observer_path_ids))
            ):
                raise ValueError("snapshot observer path identity is invalid")
            for observer_path in observer_paths:
                validate_implicit_observer_path_record(observer_path)
                if str(observer_path.get("observer_id", "")) not in set(
                    map(str, configuration.get("observer_ids", []))
                ):
                    raise ValueError("snapshot observer path uses an undeclared observer")
            active_observer_path = dict(candidate["observer_path_record"])
            if _canonical_digest(active_observer_path) != _canonical_digest(observer_paths[-1]):
                raise ValueError("snapshot active observer path is not history head")
            pose_records = list(active_observer_path.get("camera_pose_records", []))
            if not pose_records or _canonical_digest(
                pose_records[-1].get("camera_pose", {})
            ) != _canonical_digest(candidate["camera_pose"]):
                raise ValueError("snapshot camera pose does not match active observer path")

            ray_records = list(candidate["ray_sample_records"])
            ray_ids = [str(record.get("ray_sample_record_id", "")) for record in ray_records]
            if (
                not ray_records
                or any(not value for value in ray_ids)
                or len(ray_ids) != len(set(ray_ids))
            ):
                raise ValueError("snapshot ray sample identity is invalid")
            for ray_record in ray_records:
                validate_implicit_ray_sample_record(ray_record)
            latest_ray = ray_records[-1]
            if (
                str(latest_ray.get("observer_path_id", ""))
                != str(active_observer_path.get("observer_path_id", ""))
                or _canonical_digest(latest_ray.get("camera_pose", {}))
                != _canonical_digest(candidate["camera_pose"])
            ):
                raise ValueError("snapshot latest ray does not match active camera/path")
            projection_frames = list(candidate["projection_frames"])
            frame_ids = [str(frame.frame_id) for frame in projection_frames]
            if (
                not projection_frames
                or any(not value for value in frame_ids)
                or len(frame_ids) != len(set(frame_ids))
            ):
                raise ValueError("snapshot projection frame identity is invalid")
            latest_frame = projection_frames[-1]
            embedded_latest_ray = latest_frame.payload.get("implicit_ray_sample_record", {})
            if (
                str(latest_frame.payload.get("implicit_observer_path_id", ""))
                != str(active_observer_path.get("observer_path_id", ""))
                or str(embedded_latest_ray.get("ray_sample_record_id", ""))
                != str(latest_ray.get("ray_sample_record_id", ""))
                or int(latest_frame.tick) != int(candidate["current_state"]["tick"])
            ):
                raise ValueError("snapshot latest frame does not match active observation head")

        expected_previous_id = state_ids[0]
        for step in candidate["implicit_live_steps"]:
            if step.get("schema") != "implicit_live_step_record":
                if candidate.get("solar_earth_scene") is not None:
                    continue
                raise ValueError("snapshot contains an unexpected implicit live step schema")
            previous_id = str(step.get("previous_state_id", ""))
            result_id = str(step.get("result_state_id", ""))
            if previous_id != expected_previous_id or previous_id not in states_by_id or result_id not in states_by_id:
                raise ValueError("snapshot implicit state transition chain mismatch")
            previous_state = states_by_id[previous_id]
            result_state = states_by_id[result_id]
            if int(result_state["tick"]) != int(previous_state["tick"]) + 1:
                raise ValueError("snapshot implicit transition must advance exactly one tick")
            if int(step.get("tick", -1)) != int(result_state["tick"]):
                raise ValueError("snapshot implicit live step tick mismatch")
            if str(step.get("previous_state_digest", "")) != str(previous_state["state_digest"]):
                raise ValueError("snapshot implicit previous state digest mismatch")
            if str(step.get("result_state_digest", "")) != str(result_state["state_digest"]):
                raise ValueError("snapshot implicit result state digest mismatch")
            energy_ledgers = list(step.get("energy_ledgers", []))
            if energy_ledgers:
                local_scopes = {
                    str(ledger["scope_id"]): copy.deepcopy(ledger["kappa"])
                    for ledger in energy_ledgers
                    if str(ledger.get("scope_kind")) == "local"
                }
                recomputed = advance_implicit_field_state(
                    previous_state,
                    candidate["bases"],
                    user_input_projection=step.get("raw_user_input_projection", {}),
                    feedback_input_projection=step.get("raw_five_phase_feedback_input_projection", {}),
                    local_energy_scopes=local_scopes,
                )
                recomputed = ImplicitFieldSession._retag_state_static(
                    recomputed,
                    str(configuration["run_id"]),
                    int(result_state["tick"]),
                )
                if recomputed != result_state:
                    raise ValueError("snapshot canonical implicit transition replay mismatch")
                response = recomputed.get("energy_summary", {}).get("density_response", {})
                if list(response.get("ledgers", [])) != energy_ledgers:
                    raise ValueError("snapshot implicit energy ledger replay mismatch")
                if response.get("realized_user_projection", {}) != step.get(
                    "realized_user_input_projection", {}
                ):
                    raise ValueError("snapshot realized user projection mismatch")
                if response.get("realized_feedback_projection", {}) != step.get(
                    "realized_five_phase_feedback_input_projection", {}
                ):
                    raise ValueError("snapshot realized Feedback projection mismatch")
            elif not step.get("refinement_patch_ids"):
                raise ValueError("snapshot transition has neither ordinary ledger nor refinement lineage")
            expected_previous_id = result_id

        pattern_records = list(candidate["five_phase_patterns"])
        trace_records = list(candidate["five_phase_traces"])
        residual_records = list(candidate["five_phase_residual_constraints"])
        agent_records = list(candidate["five_phase_agent_states"])
        feedback_records = list(candidate["five_phase_feedback_records"])
        pattern_by_id = {record.record_id: record for record in pattern_records}
        trace_by_id = {record.record_id: record for record in trace_records}
        residual_by_id = {
            record.record_id: record for record in residual_records
        }
        agent_by_id = {record.record_id: record for record in agent_records}
        feedback_by_id = {record.record_id: record for record in feedback_records}
        bridge_by_id = {
            str(record.get("bridge_record_id", "")): record for record in candidate["five_phase_live_bridges"]
        }
        record_families = (
            ("pattern_ids", pattern_records, pattern_by_id),
            ("trace_ids", trace_records, trace_by_id),
            ("residual_constraint_ids", residual_records, residual_by_id),
            ("agent_state_ids", agent_records, agent_by_id),
            ("feedback_record_ids", feedback_records, feedback_by_id),
        )
        for field_name, records, records_by_id in record_families:
            if len(records) != len(records_by_id):
                raise ValueError(f"snapshot {field_name} record IDs must be unique")

        live_steps = list(candidate["five_phase_live_steps"])
        live_step_by_id = {str(record["live_step_id"]): record for record in live_steps}
        if len(live_steps) != len(live_step_by_id):
            raise ValueError("snapshot FivePhase live step IDs must be unique")
        artifact_owner_index_by_field: dict[str, dict[str, int]] = {
            field_name: {} for field_name, _records, _records_by_id in record_families
        }
        for index, live_step in enumerate(live_steps):
            state_id = str(live_step.get("implicit_field_state_id", ""))
            if candidate.get("solar_earth_scene") is None and state_id != state_ids[index]:
                raise ValueError("snapshot FivePhase step is not aligned to canonical state history")
            if str(live_step.get("bridge_record_id", "")) not in bridge_by_id:
                raise ValueError("snapshot FivePhase step references missing bridge")
            for field_name, _records, records_by_id in record_families:
                record_ids = [str(record_id) for record_id in live_step.get(field_name, [])]
                if len(record_ids) != len(set(record_ids)):
                    raise ValueError(f"snapshot {field_name} ownership mismatch")
                if any(record_id not in records_by_id for record_id in record_ids):
                    raise ValueError(f"snapshot FivePhase step references missing {field_name}")
                owners = artifact_owner_index_by_field[field_name]
                if any(record_id in owners for record_id in record_ids):
                    raise ValueError(f"snapshot {field_name} ownership mismatch")
                owners.update({record_id: index for record_id in record_ids})

        for field_name, _records, records_by_id in record_families:
            if set(artifact_owner_index_by_field[field_name]) != set(records_by_id):
                raise ValueError(f"snapshot {field_name} ownership mismatch")

        implicit_steps_by_result_state: dict[str, list[dict[str, Any]]] = {}
        for implicit_step in candidate["implicit_live_steps"]:
            implicit_steps_by_result_state.setdefault(
                str(implicit_step.get("result_state_id", "")),
                [],
            ).append(implicit_step)
        pattern_owner_indices = artifact_owner_index_by_field["pattern_ids"]
        for pattern in pattern_records:
            owner_index = pattern_owner_indices[pattern.record_id]
            previous_pattern_id = pattern.payload.get("previous_pattern_record_id")
            identity_id = str(pattern.payload.get("pattern_identity_id", ""))
            previous_pattern = None
            if not identity_id:
                raise ValueError("snapshot Pattern requires persistent identity")
            if previous_pattern_id is not None:
                previous_pattern_id = str(previous_pattern_id)
                previous_pattern = pattern_by_id.get(previous_pattern_id)
                if previous_pattern is None:
                    raise ValueError("snapshot Pattern references missing predecessor instance")
                if str(previous_pattern.payload.get("pattern_identity_id", "")) != identity_id:
                    raise ValueError("snapshot Pattern identity continuity mismatch")
                if (
                    owner_index <= 0
                    or pattern_owner_indices[previous_pattern_id] != owner_index - 1
                ):
                    raise ValueError("snapshot Pattern predecessor is not immediate")
                if previous_pattern_id not in {str(value) for value in pattern.source_record_ids}:
                    raise ValueError("snapshot Pattern does not cite its immediate predecessor")
            current_state = states[owner_index]
            bridge = bridge_by_id[str(live_steps[owner_index]["bridge_record_id"])]
            current_tick = int(current_state["tick"])
            if previous_pattern is None:
                fixed_bounds = [int(value) for value in pattern.support_bounds_grid]
                grid_shape = [int(value) for value in bridge.get("grid_shape", [])]
                source_channel_name = str(bridge.get("source_channel_name", ""))
                response_context = build_five_phase_initial_response_context(
                    pattern_identity_id=identity_id,
                    support_bounds_grid=fixed_bounds,
                    grid_shape=grid_shape,
                    source_channel_name=source_channel_name,
                    implicit_field_state=current_state,
                    implicit_basis_records=candidate["bases"],
                    basis_spatial_index=candidate["basis_spatial_index"],
                    tick=current_tick,
                )
            else:
                transitions = implicit_steps_by_result_state.get(
                    str(current_state["implicit_field_state_id"]),
                    [],
                )
                if len(transitions) != 1:
                    raise ValueError("snapshot Pattern response requires one exact canonical transition")
                transition = transitions[0]
                previous_state = states[owner_index - 1]
                if str(transition.get("previous_state_id", "")) != str(
                    previous_state["implicit_field_state_id"]
                ):
                    raise ValueError("snapshot Pattern response transition predecessor mismatch")
                response_context = build_five_phase_transition_response_context(
                    previous_pattern=previous_pattern,
                    previous_implicit_field_state=previous_state,
                    current_implicit_field_state=current_state,
                    implicit_basis_records=candidate["bases"],
                    basis_spatial_index=candidate["basis_spatial_index"],
                    realized_user_input_projection=transition.get("realized_user_input_projection") or {},
                    realized_feedback_input_projection=transition.get(
                        "realized_five_phase_feedback_input_projection"
                    )
                    or {},
                    tick=current_tick,
                    relaxation_horizon_ticks=ENERGY_SCOPE_RELAXATION_TICKS,
                )
                fixed_bounds = [
                    int(value)
                    for value in previous_pattern.payload.get(
                        "identity_support_bounds_grid",
                        previous_pattern.support_bounds_grid,
                    )
                ]
                grid_shape = [
                    int(value)
                    for value in previous_pattern.payload.get(
                        "identity_support_grid_shape",
                        bridge.get("grid_shape", []),
                    )
                ]
                source_channel_name = str(
                    previous_pattern.payload.get(
                        "support_source_channel_name",
                        bridge.get("source_channel_name", ""),
                    )
                )
            expected_stability, expected_payload = materialize_five_phase_pattern_response(
                previous_pattern=previous_pattern,
                pattern_identity_id=identity_id,
                response_context=response_context,
                support_bounds_grid=fixed_bounds,
                grid_shape=grid_shape,
                source_channel_name=source_channel_name,
                implicit_field_state=current_state,
                tick=current_tick,
            )
            if not math.isclose(
                float(pattern.stability_score),
                expected_stability,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise ValueError("snapshot Pattern stability does not match fixed-support response")
            for field_name, expected_value in expected_payload.items():
                if not _response_value_matches(pattern.payload.get(field_name), expected_value):
                    raise ValueError(f"snapshot Pattern {field_name} response mismatch")

        for agent in candidate["five_phase_agent_states"]:
            pattern = pattern_by_id.get(agent.pattern_id)
            trace = trace_by_id.get(str(agent.trace_id or ""))
            residual = residual_by_id.get(str(agent.residual_constraint_id or ""))
            state = states_by_id.get(str(agent.source_state_id or ""))
            if agent.schema != "five_phase_agent_state_v2":
                raise ValueError("snapshot live Agent must use v2 causal schema")
            if pattern is None or trace is None or residual is None or state is None:
                raise ValueError("snapshot Agent has incomplete causal lineage")
            if trace.pattern_id != pattern.record_id or residual.trace_id != trace.record_id:
                raise ValueError("snapshot Agent Trace/residual lineage mismatch")
            if str(agent.source_state_digest) != str(state["state_digest"]):
                raise ValueError("snapshot Agent source state digest mismatch")
            rebuilt_agent = build_agent_state_from_pattern(
                pattern,
                setpoint=agent.setpoint,
                trace=trace,
                residual_constraint=residual,
                support_energy_setpoint=agent.support_energy_setpoint,
                support_energy_current=agent.support_energy_current,
                response_stability=agent.response_stability,
                bridge_record_id=agent.bridge_record_id,
                source_state_id=agent.source_state_id,
                source_state_digest=agent.source_state_digest,
                tolerance=agent.tolerance,
                tick=agent.tick,
            )
            if rebuilt_agent != agent:
                raise ValueError("snapshot Agent semantic reconstruction mismatch")

        feedback_owner_indices = artifact_owner_index_by_field["feedback_record_ids"]
        agent_owner_indices = artifact_owner_index_by_field["agent_state_ids"]
        for feedback in feedback_records:
            agent = agent_by_id.get(feedback.agent_state_id)
            pattern = pattern_by_id.get(feedback.pattern_id)
            state = states_by_id.get(str(feedback.source_state_id or ""))
            if feedback.schema != "five_phase_feedback_v2":
                raise ValueError("snapshot live Feedback must use v2 causal schema")
            if agent is None or pattern is None or state is None:
                raise ValueError("snapshot Feedback has incomplete causal lineage")
            if agent.pattern_id != pattern.record_id:
                raise ValueError("snapshot Feedback Agent/Pattern lineage mismatch")
            if feedback.trace_id != agent.trace_id or feedback.residual_constraint_id != agent.residual_constraint_id:
                raise ValueError("snapshot Feedback Trace/residual lineage mismatch")
            if feedback.bridge_record_id != agent.bridge_record_id:
                raise ValueError("snapshot Feedback bridge lineage mismatch")
            if str(feedback.source_state_digest) != str(state["state_digest"]):
                raise ValueError("snapshot Feedback source state digest mismatch")
            owner_index = feedback_owner_indices[feedback.record_id]
            if (
                agent_owner_indices[agent.record_id] != owner_index
                or pattern_owner_indices[pattern.record_id] != owner_index
            ):
                raise ValueError("snapshot Feedback lineage crosses causal owners")
            expected_predecessor_id = (
                str(live_steps[owner_index - 1]["live_step_id"])
                if owner_index > 0
                else None
            )
            if str(feedback.predecessor_causal_step_id or "") != str(
                expected_predecessor_id or ""
            ):
                raise ValueError("snapshot Feedback predecessor is not immediate")
            rebuilt_feedback = build_agent_repair_feedback(
                agent,
                pattern,
                tick=feedback.tick,
                target_basis_id=feedback.target_basis_id,
                signed_error=feedback.signed_error,
                sensitivity=feedback.sensitivity,
                eta=feedback.eta,
                gain=feedback.gain,
                candidate_projection=feedback.candidate_projection,
                predecessor_causal_step_id=feedback.predecessor_causal_step_id,
            )
            if rebuilt_feedback != feedback:
                raise ValueError("snapshot Feedback semantic reconstruction mismatch")

        implicit_step_by_id = {
            str(record["step_id"]): record for record in candidate["implicit_live_steps"]
        }
        if len(implicit_step_by_id) != len(candidate["implicit_live_steps"]):
            raise ValueError("snapshot implicit live step IDs must be unique")
        ordinary_implicit_step_ids = {
            step_id
            for step_id, record in implicit_step_by_id.items()
            if record.get("schema") == "implicit_live_step_record"
            and not record.get("refinement_patch_ids")
        }
        applications = list(candidate["five_phase_feedback_applications"])
        application_ids = [str(record.get("application_record_id", "")) for record in applications]
        if any(not value for value in application_ids) or len(application_ids) != len(set(application_ids)):
            raise ValueError("snapshot Feedback application IDs must be unique")
        application_owner_step_ids = [str(record.get("implicit_live_step_id", "")) for record in applications]
        if (
            len(application_owner_step_ids) != len(set(application_owner_step_ids))
            or set(application_owner_step_ids) != ordinary_implicit_step_ids
        ):
            raise ValueError("snapshot Feedback application ownership mismatch")

        live_step_id_by_state_id = {
            str(record.get("implicit_field_state_id", "")): str(record["live_step_id"])
            for record in live_steps
        }
        if len(live_step_id_by_state_id) != len(live_steps):
            raise ValueError("snapshot canonical state has multiple FivePhase causal owners")
        consumed_source_step_ids: set[str] = set()
        consumed_feedback_ids: set[str] = set()
        for application in applications:
            if application.get("schema") != "five_phase_feedback_application_record_v2":
                raise ValueError("snapshot Feedback application schema mismatch")
            implicit_step = implicit_step_by_id.get(str(application.get("implicit_live_step_id", "")))
            if implicit_step is None or int(application.get("tick", -1)) != int(implicit_step["tick"]):
                raise ValueError("snapshot Feedback application transition mismatch")
            if str(implicit_step.get("five_phase_feedback_application_id", "")) != str(
                application["application_record_id"]
            ):
                raise ValueError("snapshot Feedback application ownership mismatch")
            if (
                str(application.get("previous_state_id", ""))
                != str(implicit_step.get("previous_state_id", ""))
                or str(application.get("result_state_id", ""))
                != str(implicit_step.get("result_state_id", ""))
            ):
                raise ValueError("snapshot Feedback application transition mismatch")
            expected_source_step_id = live_step_id_by_state_id.get(
                str(implicit_step.get("previous_state_id", ""))
            )
            source_step_ids = [
                str(step_id) for step_id in application.get("five_phase_live_step_ids", [])
            ]
            if expected_source_step_id is None or source_step_ids != [expected_source_step_id]:
                raise ValueError("snapshot Feedback application source step is not immediate")
            if [str(value) for value in implicit_step.get("five_phase_live_step_ids", [])] != source_step_ids:
                raise ValueError("snapshot implicit step Feedback source does not match its application")
            if expected_source_step_id in consumed_source_step_ids:
                raise ValueError("snapshot FivePhase predecessor causal step was consumed more than once")
            consumed_source_step_ids.add(expected_source_step_id)
            source_step = live_step_by_id[expected_source_step_id]
            available_feedback_ids = [
                str(record_id) for record_id in source_step.get("feedback_record_ids", [])
            ]
            application_feedback_ids = [
                str(value) for value in application.get("feedback_record_ids", [])
            ]
            if (
                len(application_feedback_ids) != len(set(application_feedback_ids))
                or application_feedback_ids != available_feedback_ids
            ):
                raise ValueError("snapshot Feedback application does not consume exact predecessor Feedback")
            if any(feedback_id in consumed_feedback_ids for feedback_id in application_feedback_ids):
                raise ValueError("snapshot Feedback record was consumed more than once")
            consumed_feedback_ids.update(application_feedback_ids)
            if application.get("feedback_consumed") is not True:
                raise ValueError("snapshot Feedback application must record one-shot consumption")
            exact_feedback = [
                feedback_by_id[feedback_id] for feedback_id in application_feedback_ids
            ]
            exact_patterns = [
                pattern_by_id[pattern_id]
                for pattern_id in sorted({feedback.pattern_id for feedback in exact_feedback})
            ]
            recomputed_candidate_projection = five_phase_feedback_to_implicit_input_projection(
                feedback_records=exact_feedback,
                patterns=exact_patterns,
                implicit_basis_records=candidate["bases"],
            )
            if recomputed_candidate_projection != application.get("candidate_feedback_projection", {}):
                raise ValueError("snapshot Feedback application candidate projection mismatch")
            if application.get("applied_feedback_projection", {}) != implicit_step.get(
                "realized_five_phase_feedback_input_projection", {}
            ):
                raise ValueError("snapshot Feedback application realized projection mismatch")
            for measurement in [
                *application.get("baseline_response_measurements", []),
                *application.get("candidate_response_measurements", []),
            ]:
                copied = dict(measurement)
                digest = copied.pop("measurement_digest", None)
                if digest != _canonical_digest(copied):
                    raise ValueError("snapshot Feedback response measurement digest mismatch")
            baseline_measurements = application.get("baseline_response_measurements", [])
            candidate_measurements = application.get("candidate_response_measurements", [])
            if len(baseline_measurements) != len(candidate_measurements):
                raise ValueError("snapshot Feedback response measurement count mismatch")
            previous_state = states_by_id[str(application["previous_state_id"])]
            local_scopes = {
                str(ledger["scope_id"]): copy.deepcopy(ledger["kappa"])
                for ledger in implicit_step.get("energy_ledgers", [])
                if str(ledger.get("scope_kind")) == "local"
            }
            baseline_preview = advance_implicit_field_state(
                previous_state,
                candidate["bases"],
                user_input_projection=implicit_step.get("raw_user_input_projection", {}),
                feedback_input_projection={},
                local_energy_scopes=local_scopes,
            )
            candidate_preview = advance_implicit_field_state(
                previous_state,
                candidate["bases"],
                user_input_projection=implicit_step.get("raw_user_input_projection", {}),
                feedback_input_projection=recomputed_candidate_projection,
                local_energy_scopes=local_scopes,
            )
            baseline_preview = ImplicitFieldSession._retag_state_static(
                baseline_preview,
                str(configuration["run_id"]),
                int(implicit_step["tick"]),
            )
            candidate_preview = ImplicitFieldSession._retag_state_static(
                candidate_preview,
                str(configuration["run_id"]),
                int(implicit_step["tick"]),
            )
            expected_baseline_measurements = [
                measure_five_phase_feedback_response(
                    implicit_field_state=baseline_preview,
                    implicit_basis_records=candidate["bases"],
                    basis_spatial_index=candidate["basis_spatial_index"],
                    pattern=pattern_by_id[feedback.pattern_id],
                    agent_state=agent_by_id[feedback.agent_state_id],
                    feedback=feedback,
                )
                for feedback in exact_feedback
            ]
            expected_candidate_measurements = [
                measure_five_phase_feedback_response(
                    implicit_field_state=candidate_preview,
                    implicit_basis_records=candidate["bases"],
                    basis_spatial_index=candidate["basis_spatial_index"],
                    pattern=pattern_by_id[feedback.pattern_id],
                    agent_state=agent_by_id[feedback.agent_state_id],
                    feedback=feedback,
                )
                for feedback in exact_feedback
            ]
            if baseline_measurements != expected_baseline_measurements:
                raise ValueError("snapshot Feedback baseline measurement reconstruction mismatch")
            if candidate_measurements != expected_candidate_measurements:
                raise ValueError("snapshot Feedback candidate measurement reconstruction mismatch")
            reduced = bool(baseline_measurements) and all(
                bool(baseline["candidate_direction_eligible"])
                and float(candidate_measurement["absolute_error"])
                < float(baseline["absolute_error"]) - FEEDBACK_ERROR_IMPROVEMENT_TOLERANCE
                for baseline, candidate_measurement in zip(baseline_measurements, candidate_measurements)
            )
            if bool(application.get("feedback_applied")) != bool(
                reduced and application.get("feedback_enabled")
            ):
                raise ValueError("snapshot Feedback application eligibility mismatch")

        audit_ids = [str(audit.get("audit_id", "")) for audit in candidate["interaction_audits"]]
        command_ids = [str(audit.get("command_id", "")) for audit in candidate["interaction_audits"]]
        request_ids = [str(audit.get("request_id", "")) for audit in candidate["interaction_audits"]]
        audit_sequences = [audit.get("accepted_sequence") for audit in candidate["interaction_audits"]]
        if any(not value for value in [*audit_ids, *command_ids, *request_ids]):
            raise ValueError("snapshot interaction audit identity is missing")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 1
            for value in audit_sequences
        ):
            raise ValueError("snapshot interaction audit sequence is invalid")
        for label, values in (
            ("audit", audit_ids),
            ("command", command_ids),
            ("request", request_ids),
            ("sequence", audit_sequences),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"snapshot interaction {label} identity must be unique")

        audits_by_id = {str(audit["audit_id"]): audit for audit in candidate["interaction_audits"]}
        audits_by_command = {
            str(audit["command_id"]): audit for audit in candidate["interaction_audits"]
        }
        transcript_sequences: list[int] = []
        for entry in candidate["interaction_transcript"]:
            if entry.get("schema") != "implicit_interaction_transcript_entry_v1":
                raise ValueError("snapshot interaction transcript schema mismatch")
            sequence = int(entry.get("accepted_sequence", -1))
            transcript_sequences.append(sequence)
            audit = audits_by_id.get(str(entry.get("audit_id", "")))
            request = entry.get("request")
            if audit is None or not isinstance(request, Mapping):
                raise ValueError("snapshot interaction transcript has missing audit/request")
            if str(request.get("request_id", "")) != str(audit.get("request_id", "")):
                raise ValueError("snapshot interaction transcript request/audit mismatch")
            if sequence != int(audit.get("accepted_sequence", -1)):
                raise ValueError("snapshot interaction transcript sequence mismatch")
        if transcript_sequences != sorted(set(transcript_sequences)):
            raise ValueError("snapshot interaction transcript ordering mismatch")
        transcript_audit_ids = [str(entry.get("audit_id", "")) for entry in candidate["interaction_transcript"]]
        if transcript_audit_ids != audit_ids:
            raise ValueError("snapshot interaction transcript/audit ownership mismatch")

        pending = list(candidate["pending_inputs"])
        pending_order = sorted(
            pending,
            key=lambda item: (
                int(item["apply_tick"]),
                int(item.get("accepted_sequence", -1)),
                str(item.get("request_id", "")),
            ),
        )
        if pending != pending_order:
            raise ValueError("snapshot pending controls are not deterministically ordered")
        if len([item for item in pending if int(item["apply_tick"]) <= int(candidate["current_state"]["tick"]) + 1]) > MAX_DUE_CONTROLS_PER_TICK:
            raise ValueError("snapshot due control budget exceeded")
        if len({str(item["command_id"]) for item in pending}) != len(pending):
            raise ValueError("snapshot contains duplicate pending command")
        for item in pending:
            audit = audits_by_command.get(str(item.get("command_id", "")))
            if audit is None:
                raise ValueError("snapshot pending control has no audit")
            if item.get("kind") == "local_control":
                descriptor = item.get("control_descriptor", {})
                schedule_index = int(item.get("next_schedule_index", -1))
                if schedule_index != len(audit.get("applications", [])):
                    raise ValueError("snapshot pending control application index mismatch")
                if schedule_index < 0 or schedule_index >= len(descriptor.get("schedule_weights", [])):
                    raise ValueError("snapshot pending control schedule index is outside bounds")
                if str(descriptor.get("command_id", "")) != str(audit["command_id"]):
                    raise ValueError("snapshot pending descriptor/audit mismatch")

        from world_engine.completion import implicit_live_energy_ledger_failures

        energy_failures = implicit_live_energy_ledger_failures(
            {
                "implicit_field_states": states,
                "implicit_basis_records": candidate["bases"],
                "implicit_live_step_records": candidate["implicit_live_steps"],
                "implicit_interaction_audits": candidate["interaction_audits"],
                "five_phase_feedback_records": candidate["five_phase_feedback_records"],
                "five_phase_feedback_applications": candidate["five_phase_feedback_applications"],
            }
        )
        if energy_failures:
            raise ValueError(
                "snapshot implicit energy scope/ledger reconstruction mismatch: "
                + str(energy_failures[0].get("reason", "unknown"))
            )

        active_scopes = list(candidate["active_energy_scopes"])
        scope_ids = [str(scope.get("scope_id", "")) for scope in active_scopes]
        if any(not scope_id for scope_id in scope_ids) or len(scope_ids) != len(set(scope_ids)):
            raise ValueError("snapshot active energy scopes require unique IDs")
        for scope in active_scopes:
            if int(scope.get("expiry_tick", -1)) <= int(candidate["current_state"]["tick"]):
                raise ValueError("snapshot retains an expired energy scope")
            kappa = scope.get("kappa_by_basis")
            if not isinstance(kappa, Mapping) or not kappa:
                raise ValueError("snapshot active energy scope requires kappa")
            if any(
                str(basis_id) not in states[-1]["basis_ids"]
                or not math.isfinite(float(value))
                or float(value) < 0.0
                for basis_id, value in kappa.items()
            ):
                raise ValueError("snapshot active energy scope kappa is invalid")
        current_tick = int(candidate["current_state"]["tick"])
        expected_active_scopes: dict[str, dict[str, Any]] = {}
        for audit in candidate["interaction_audits"]:
            if str(audit.get("tool", "")) not in {
                "implicit_local_excite",
                "implicit_local_dampen",
            }:
                continue
            schedule_weights = list(audit.get("schedule_weights", []))
            start_tick = int(audit.get("start_tick", -1))
            final_input_tick = start_tick + len(schedule_weights) - 1
            expiry_tick = final_input_tick + ENERGY_SCOPE_RELAXATION_TICKS
            if expiry_tick <= current_tick:
                continue
            command_id = str(audit.get("command_id", ""))
            scope_id = f"implicit-energy-scope::{command_id}"
            expected_active_scopes[scope_id] = {
                "scope_id": scope_id,
                "request_id": str(audit.get("request_id", "")),
                "command_id": command_id,
                "accepted_sequence": int(audit.get("accepted_sequence", -1)),
                "kappa_by_basis": copy.deepcopy(dict(audit.get("kappa_by_basis", {}))),
                "activation_tick": start_tick,
                "final_input_tick": final_input_tick,
                "expiry_tick": expiry_tick,
            }
        for application in candidate["five_phase_feedback_applications"]:
            feedback_ids = [str(value) for value in application.get("feedback_record_ids", [])]
            baseline_measurements = list(application.get("baseline_response_measurements", []))
            candidate_measurements = list(application.get("candidate_response_measurements", []))
            precommit_eligible = bool(feedback_ids) and all(
                bool(baseline.get("candidate_direction_eligible"))
                and float(candidate_measurement.get("absolute_error", math.inf))
                < float(baseline.get("absolute_error", -math.inf))
                - FEEDBACK_ERROR_IMPROVEMENT_TOLERANCE
                for baseline, candidate_measurement in zip(
                    baseline_measurements,
                    candidate_measurements,
                )
            )
            if not precommit_eligible:
                continue
            activation_tick = int(application["tick"])
            expiry_tick = activation_tick + ENERGY_SCOPE_RELAXATION_TICKS
            if expiry_tick <= current_tick:
                continue
            for feedback_id in feedback_ids:
                feedback = feedback_by_id[feedback_id]
                scope_id = f"implicit-feedback-energy-scope::{feedback_id}"
                expected_active_scopes[scope_id] = {
                    "scope_id": scope_id,
                    "feedback_record_id": feedback_id,
                    "source_kind": "five_phase_feedback",
                    "kappa_by_basis": {str(feedback.target_basis_id): 1.0},
                    "activation_tick": activation_tick,
                    "final_input_tick": activation_tick,
                    "expiry_tick": expiry_tick,
                }
        actual_active_scopes = {
            str(scope["scope_id"]): dict(scope) for scope in active_scopes
        }
        if _canonical_digest(actual_active_scopes) != _canonical_digest(expected_active_scopes):
            raise ValueError("snapshot active energy scope ownership/lifecycle mismatch")

        accepted_sequence = int(candidate["accepted_sequence"])
        observed_sequences = [
            int(audit["accepted_sequence"])
            for audit in candidate["interaction_audits"]
            if audit.get("accepted_sequence") is not None
        ]
        if observed_sequences and max(observed_sequences) != accepted_sequence:
            raise ValueError("snapshot accepted sequence does not match interaction history")

        if candidate.get("solar_earth_scene") is None:
            from world_engine.five_phase_live_completion import (
                evaluate_five_phase_live_completion,
            )

            live_export = {
                "session": {
                    "schema": "implicit_live_session_manifest",
                    "runtime_mode": RUNTIME_MODE,
                    "session_id": str(configuration["session_id"]),
                    "run_id": str(configuration["run_id"]),
                    "source_package_name": str(configuration["source_package_name"]),
                    "source_package_digest": str(configuration["source_package_digest"]),
                    "current_tick": int(candidate["current_state"]["tick"]),
                    "projection_frame_count": len(candidate["projection_frames"]),
                    "implicit_field_state_count": len(candidate["implicit_field_states"]),
                    "implicit_live_step_count": len(candidate["implicit_live_steps"]),
                    "five_phase_live_step_count": len(candidate["five_phase_live_steps"]),
                    "five_phase_feedback_enabled": bool(
                        candidate["five_phase_feedback_enabled"]
                    ),
                    "observer_ids": list(configuration["observer_ids"]),
                    "is_authority_state": False,
                },
                "implicit_basis_records": candidate["bases"],
                "implicit_field_states": candidate["implicit_field_states"],
                "implicit_authority_certificates": candidate["authority_certificates"],
                "implicit_evaluation_records": candidate["evaluation_records"],
                "implicit_observer_path_records": candidate["observer_path_records"],
                "implicit_ray_sample_records": candidate["ray_sample_records"],
                "implicit_spectral_image_planes": candidate["image_planes"],
                "implicit_camera_move_records": candidate["camera_move_records"],
                "implicit_spatial_consistency_records": candidate["spatial_consistency_records"],
                "implicit_observed_structure_records": candidate["observed_structure_records"],
                "implicit_live_step_records": candidate["implicit_live_steps"],
                "five_phase_live_bridges": candidate["five_phase_live_bridges"],
                "five_phase_live_field_states": candidate["five_phase_live_field_states"],
                "five_phase_phase_fields": candidate["five_phase_phase_fields"],
                "five_phase_constraint_sets": candidate["five_phase_constraint_sets"],
                "five_phase_patterns": candidate["five_phase_patterns"],
                "five_phase_lifecycle_records": candidate["five_phase_lifecycle_records"],
                "five_phase_traces": candidate["five_phase_traces"],
                "five_phase_residual_constraints": candidate[
                    "five_phase_residual_constraints"
                ],
                "five_phase_agent_states": candidate["five_phase_agent_states"],
                "five_phase_feedback_records": candidate["five_phase_feedback_records"],
                "five_phase_feedback_applications": candidate[
                    "five_phase_feedback_applications"
                ],
                "five_phase_live_steps": candidate["five_phase_live_steps"],
                "implicit_interaction_audits": candidate["interaction_audits"],
                "implicit_interaction_transcript": candidate["interaction_transcript"],
                "implicit_refinement_requests": candidate["refinement_requests"],
                "implicit_refinement_patches": candidate["refinement_patches"],
                "implicit_baseline_comparisons": candidate["baseline_comparisons"],
                "projection_frames": candidate["projection_frames"],
            }
            live_completion = evaluate_five_phase_live_completion(live_export)
            if live_completion.get("authority_lineage_status") != "passed":
                raise ValueError("snapshot FivePhase authority lineage completion mismatch")
            if live_completion.get("frame_payload_status") != "passed":
                raise ValueError("snapshot projection frame semantic completion mismatch")

    @_session_locked
    def restore_snapshot(
        self,
        snapshot: Mapping[str, Any],
        *,
        expected_snapshot_digest: str,
        five_phase_feedback_enabled_override: bool | None = None,
    ) -> None:
        if five_phase_feedback_enabled_override is not None and not isinstance(
            five_phase_feedback_enabled_override,
            bool,
        ):
            raise ValueError("five_phase_feedback_enabled_override must be boolean")
        if snapshot.get("schema") != IMPLICIT_LIVE_SESSION_SNAPSHOT_SCHEMA:
            raise ValueError("implicit live session snapshot schema mismatch")
        provided_digest = str(snapshot.get("snapshot_digest", ""))
        computed_digest = _snapshot_digest(snapshot)
        trusted_digest = str(expected_snapshot_digest)
        if not provided_digest or provided_digest != computed_digest or provided_digest != trusted_digest:
            raise ValueError("snapshot digest mismatch")
        configuration = copy.deepcopy(dict(snapshot.get("configuration", {})))
        if str(snapshot.get("configuration_digest", "")) != _canonical_digest(configuration):
            raise ValueError("snapshot configuration digest mismatch")

        candidate: dict[str, Any] = {
            "configuration": configuration,
            "current_state": copy.deepcopy(snapshot["current_state"]),
            "bases": copy.deepcopy(snapshot["bases"]),
            "basis_spatial_index": copy.deepcopy(snapshot["basis_spatial_index"]),
            "implicit_field_states": copy.deepcopy(snapshot["implicit_field_states"]),
            "authority_certificates": copy.deepcopy(snapshot["authority_certificates"]),
            "evaluation_records": copy.deepcopy(snapshot["evaluation_records"]),
            "ray_sample_records": copy.deepcopy(snapshot["ray_sample_records"]),
            "image_planes": copy.deepcopy(snapshot["image_planes"]),
            "projection_frames": [ProjectionFrame.from_dict(frame) for frame in snapshot["projection_frames"]],
            "camera_pose": copy.deepcopy(snapshot["camera_pose"]),
            "observer_path_record": copy.deepcopy(snapshot["observer_path_record"]),
            "observer_path_records": copy.deepcopy(snapshot.get("observer_path_records", [])),
            "camera_move_records": copy.deepcopy(snapshot.get("camera_move_records", [])),
            "spatial_consistency_records": copy.deepcopy(snapshot.get("spatial_consistency_records", [])),
            "observed_structure_records": copy.deepcopy(snapshot.get("observed_structure_records", [])),
            "interaction_audits": copy.deepcopy(snapshot["interaction_audits"]),
            "interaction_transcript": copy.deepcopy(snapshot.get("interaction_transcript", [])),
            "implicit_live_steps": copy.deepcopy(snapshot["implicit_live_steps"]),
            "five_phase_live_bridges": copy.deepcopy(snapshot.get("five_phase_live_bridges", [])),
            "five_phase_live_field_states": [FieldState.from_dict(item) for item in snapshot.get("five_phase_live_field_states", [])],
            "five_phase_phase_fields": [FivePhaseFieldRecord.from_dict(item) for item in snapshot.get("five_phase_phase_fields", [])],
            "five_phase_constraint_sets": [FivePhaseConstraintSetRecord.from_dict(item) for item in snapshot.get("five_phase_constraint_sets", [])],
            "five_phase_patterns": [FivePhasePatternRecord.from_dict(item) for item in snapshot.get("five_phase_patterns", [])],
            "five_phase_lifecycle_records": copy.deepcopy(snapshot.get("five_phase_lifecycle_records", [])),
            "five_phase_traces": [FivePhaseTraceRecord.from_dict(item) for item in snapshot.get("five_phase_traces", [])],
            "five_phase_residual_constraints": [FivePhaseResidualConstraintRecord.from_dict(item) for item in snapshot.get("five_phase_residual_constraints", [])],
            "five_phase_agent_states": [FivePhaseAgentStateRecord.from_dict(item) for item in snapshot.get("five_phase_agent_states", [])],
            "five_phase_feedback_records": [FivePhaseFeedbackRecord.from_dict(item) for item in snapshot.get("five_phase_feedback_records", [])],
            "five_phase_feedback_applications": copy.deepcopy(snapshot.get("five_phase_feedback_applications", [])),
            "five_phase_live_steps": copy.deepcopy(snapshot.get("five_phase_live_steps", [])),
            "refinement_requests": copy.deepcopy(snapshot["refinement_requests"]),
            "refinement_patches": copy.deepcopy(snapshot["refinement_patches"]),
            "baseline_comparisons": copy.deepcopy(snapshot["baseline_comparisons"]),
            "run_step_request_ids": set(snapshot.get("run_step_request_ids", [])),
            "render_frame_request_ids": set(snapshot.get("render_frame_request_ids", [])),
            "pending_inputs": copy.deepcopy(snapshot["pending_inputs"]),
            "accepted_sequence": int(snapshot.get("accepted_sequence", 0)),
            "active_energy_scopes": copy.deepcopy(snapshot.get("active_energy_scopes", [])),
            "solar_earth_scene": copy.deepcopy(snapshot.get("solar_earth_scene")),
            "five_phase_feedback_enabled": bool(snapshot.get("five_phase_feedback_enabled", True)),
        }
        if five_phase_feedback_enabled_override is not None:
            candidate["five_phase_feedback_enabled"] = five_phase_feedback_enabled_override
        validate_implicit_field_state(candidate["current_state"])
        for state in candidate["implicit_field_states"]:
            validate_implicit_field_state(state)
        state_ids = [str(state["implicit_field_state_id"]) for state in candidate["implicit_field_states"]]
        if len(state_ids) != len(set(state_ids)):
            raise ValueError("duplicate future-affecting implicit field state id")
        if not state_ids or state_ids[-1] != str(candidate["current_state"]["implicit_field_state_id"]):
            raise ValueError("snapshot current state is not history head")
        if _canonical_digest(candidate["implicit_field_states"][-1]) != _canonical_digest(
            candidate["current_state"]
        ):
            raise ValueError("snapshot current state content differs from history head")
        _require_unique_record_ids(candidate["implicit_live_steps"], family="implicit live step")
        _require_unique_record_ids(candidate["five_phase_live_steps"], family="five phase live step")
        _require_unique_record_ids(candidate["five_phase_patterns"], family="five phase pattern instance")
        _require_unique_record_ids(candidate["five_phase_traces"], family="five phase trace")
        _require_unique_record_ids(candidate["five_phase_agent_states"], family="five phase agent")
        _require_unique_record_ids(candidate["five_phase_feedback_records"], family="five phase feedback")
        _require_unique_record_ids(candidate["five_phase_feedback_applications"], family="feedback application")
        if len(candidate["pending_inputs"]) > 64 or len(candidate["active_energy_scopes"]) > 64:
            raise ValueError("snapshot pending control or active scope budget exceeded")
        self._validate_detached_snapshot_candidate(candidate)

        self.session_id = str(configuration["session_id"])
        self.run_id = str(configuration["run_id"])
        self.source_package_name = str(configuration["source_package_name"])
        self.source_package_digest = str(configuration["source_package_digest"])
        self.image_shape = [int(value) for value in configuration["image_shape"]]
        self.samples_per_ray = int(configuration["samples_per_ray"])
        self.observer_ids = [str(value) for value in configuration["observer_ids"]]
        self.initial_camera_pose = copy.deepcopy(configuration["initial_camera_pose"])
        self.current_state = candidate["current_state"]
        self.bases = candidate["bases"]
        self.basis_spatial_index = candidate["basis_spatial_index"]
        self.implicit_field_states = candidate["implicit_field_states"]
        self.authority_certificates = candidate["authority_certificates"]
        self.evaluation_records = candidate["evaluation_records"]
        self.ray_sample_records = candidate["ray_sample_records"]
        self.image_planes = candidate["image_planes"]
        self.projection_frames = candidate["projection_frames"]
        self.camera_pose = candidate["camera_pose"]
        self.observer_path_record = candidate["observer_path_record"]
        self.observer_path_records = candidate["observer_path_records"] or [copy.deepcopy(self.observer_path_record)]
        self.camera_move_records = candidate["camera_move_records"]
        self.spatial_consistency_records = candidate["spatial_consistency_records"]
        self.observed_structure_records = candidate["observed_structure_records"]
        self.interaction_audits = candidate["interaction_audits"]
        self._rebuild_audit_index()
        self.interaction_transcript = candidate["interaction_transcript"]
        self.implicit_live_steps = candidate["implicit_live_steps"]
        self.five_phase_live_bridges = candidate["five_phase_live_bridges"]
        self.five_phase_live_field_states = candidate["five_phase_live_field_states"]
        self.five_phase_phase_fields = candidate["five_phase_phase_fields"]
        self.five_phase_constraint_sets = candidate["five_phase_constraint_sets"]
        self.five_phase_patterns = candidate["five_phase_patterns"]
        self.five_phase_lifecycle_records = candidate["five_phase_lifecycle_records"]
        self.five_phase_traces = candidate["five_phase_traces"]
        self.five_phase_residual_constraints = candidate["five_phase_residual_constraints"]
        self.five_phase_agent_states = candidate["five_phase_agent_states"]
        self.five_phase_feedback_records = candidate["five_phase_feedback_records"]
        self.five_phase_feedback_applications = candidate["five_phase_feedback_applications"]
        self.five_phase_live_steps = candidate["five_phase_live_steps"]
        self.refinement_requests = candidate["refinement_requests"]
        self.refinement_patches = candidate["refinement_patches"]
        self.baseline_comparisons = candidate["baseline_comparisons"]
        self.run_step_request_ids = candidate["run_step_request_ids"]
        self.render_frame_request_ids = candidate["render_frame_request_ids"]
        self._pending_inputs = candidate["pending_inputs"]
        self._accepted_sequence = candidate["accepted_sequence"]
        self._active_energy_scopes = candidate["active_energy_scopes"]
        solar_scene = candidate["solar_earth_scene"]
        if solar_scene is None:
            if hasattr(self, "solar_earth_scene"):
                delattr(self, "solar_earth_scene")
        else:
            self.solar_earth_scene = copy.deepcopy(solar_scene)
        self.five_phase_feedback_enabled = candidate["five_phase_feedback_enabled"]

    @_session_locked
    def projection_frame_dicts(self) -> list[dict[str, Any]]:
        return [frame.to_dict() for frame in self.projection_frames]

    @_session_locked
    def export_artifacts(self) -> dict[str, Any]:
        artifacts = {
            "session": self.manifest(),
            "implicit_basis_records": copy.deepcopy(self.bases),
            "implicit_field_states": copy.deepcopy(self.implicit_field_states),
            "implicit_authority_certificates": copy.deepcopy(self.authority_certificates),
            "implicit_evaluation_records": copy.deepcopy(self.evaluation_records),
            "implicit_observer_path_records": copy.deepcopy(self.observer_path_records),
            "implicit_ray_sample_records": copy.deepcopy(self.ray_sample_records),
            "implicit_spectral_image_planes": copy.deepcopy(self.image_planes),
            "implicit_camera_move_records": copy.deepcopy(self.camera_move_records),
            "implicit_spatial_consistency_records": copy.deepcopy(self.spatial_consistency_records),
            "implicit_observed_structure_records": copy.deepcopy(self.observed_structure_records),
            "implicit_live_step_records": copy.deepcopy(self.implicit_live_steps),
            "five_phase_live_bridges": copy.deepcopy(self.five_phase_live_bridges),
            "five_phase_live_field_states": [state.to_dict() for state in self.five_phase_live_field_states],
            "five_phase_phase_fields": [record.to_dict() for record in self.five_phase_phase_fields],
            "five_phase_constraint_sets": [record.to_dict() for record in self.five_phase_constraint_sets],
            "five_phase_patterns": [record.to_dict() for record in self.five_phase_patterns],
            "five_phase_lifecycle_records": copy.deepcopy(self.five_phase_lifecycle_records),
            "five_phase_traces": [record.to_dict() for record in self.five_phase_traces],
            "five_phase_residual_constraints": [record.to_dict() for record in self.five_phase_residual_constraints],
            "five_phase_agent_states": [record.to_dict() for record in self.five_phase_agent_states],
            "five_phase_feedback_records": [record.to_dict() for record in self.five_phase_feedback_records],
            "five_phase_feedback_applications": copy.deepcopy(self.five_phase_feedback_applications),
            "five_phase_live_steps": copy.deepcopy(self.five_phase_live_steps),
            "implicit_interaction_audits": copy.deepcopy(self.interaction_audits),
            "implicit_interaction_transcript": copy.deepcopy(self.interaction_transcript),
            "implicit_refinement_requests": copy.deepcopy(self.refinement_requests),
            "implicit_refinement_patches": copy.deepcopy(self.refinement_patches),
            "implicit_baseline_comparisons": copy.deepcopy(self.baseline_comparisons),
            "projection_frames": list(self.projection_frames),
        }
        if hasattr(self, "solar_earth_scene"):
            artifacts["solar_earth_scene"] = copy.deepcopy(getattr(self, "solar_earth_scene"))
        return artifacts

    @staticmethod
    def _retag_state_static(state: Mapping[str, Any], run_id: str, tick: int) -> dict[str, Any]:
        return build_implicit_field_state(
            implicit_field_state_id=f"implicit-field-state::{run_id}::{tick}",
            tick=int(tick),
            basis_ids=list(state["basis_ids"]),
            basis_layout_digest=str(state["basis_layout_digest"]),
            basis_spatial_index_digest=str(state["basis_spatial_index_digest"]),
            basis_coefficients=copy.deepcopy(state.get("basis_coefficients", {})),
            sparse_coupling_edges=copy.deepcopy(state.get("sparse_coupling_edges", [])),
            background_model=copy.deepcopy(state.get("background_model", {})),
            active_local_patch_ids=list(state.get("active_local_patch_ids", [])),
            validity_region_world=copy.deepcopy(state.get("validity_region_world", {})),
            energy_summary=copy.deepcopy(state.get("energy_summary", {})),
            source_record_ids=list(state.get("source_record_ids", [])),
            authority_status=str(state.get("authority_status", "candidate")),
            runtime_cost_summary=copy.deepcopy(state.get("runtime_cost_summary")) if state.get("runtime_cost_summary") else None,
        )

    def _retag_state(self, state: Mapping[str, Any], tick: int) -> dict[str, Any]:
        return self._retag_state_static(state, self.run_id, int(tick))

    def _base_frame(self, tick: int, source_state_id: str, event_kinds: Sequence[str]) -> ProjectionFrame:
        return ProjectionFrame(
            frame_id=f"projection-frame::{self.run_id}::{DEFAULT_OBSERVER_ID}::{tick}::{len(self.projection_frames)}",
            tick=int(tick),
            observer_id=DEFAULT_OBSERVER_ID,
            image_plane={"schema": "projection_image_plane_v1", "width": int(self.image_shape[0]), "height": int(self.image_shape[1])},
            samples=[],
            phenomena_overlays=[],
            source_state_ticks=[int(tick)],
            source_object_ids=[],
            source_record_ids=[source_state_id],
            is_authority_state=False,
            audit={
                "projection_semantics": "observer_projection_not_object_painting",
                "no_persistent_light_object": True,
                "no_material_asset_authority": True,
                "no_global_raindrop_authority_state": True,
            },
            payload={
                "event_timeline": {
                    "tick": int(tick),
                    "event_kinds": list(event_kinds),
                    "interaction_record_ids": [],
                    "wave_step_record_ids": [],
                    "field_structure_event_ids": [],
                    "source_record_ids": [source_state_id],
                    "observer_id": DEFAULT_OBSERVER_ID,
                    "is_authority_state": False,
                }
            },
        )

    def _certificate(self, state: Mapping[str, Any], trace: Mapping[str, Any]) -> dict[str, Any]:
        evaluation = trace["evaluation_record"]
        ray = trace["ray_sample_record"]
        max_active = int(evaluation["active_basis_per_sample_summary"]["max"])
        return build_implicit_field_authority_certificate(
            certificate_id=f"implicit-field-certificate::{self.run_id}::{state['tick']}",
            implicit_field_state=state,
            source_basis_ids=[basis["basis_id"] for basis in self.bases],
            source_evaluation_ids=[evaluation["evaluation_id"]],
            source_ray_sample_record_ids=[ray["ray_sample_record_id"]],
            source_refinement_patch_ids=list(state.get("active_local_patch_ids", [])),
            validity_region_world=state["validity_region_world"],
            validity_tick_window=[int(state["tick"]), int(state["tick"])],
            error_bounds={
                "compact_support_leak": 0.0,
                "ray_replay_mismatch": 0.0,
                "occlusion_response_error": 0.01,
                "local_refinement_correction_energy": 0.12 if state.get("active_local_patch_ids") else 0.0,
                "stability_margin": 0.2,
                "coefficient_clamp_saturation_ratio": float(state.get("runtime_cost_summary", {}).get("coefficient_clamp_saturation_ratio", 0.0)),
                "boundary_temporal_flicker": 0.02,
                "active_basis_per_sample_max": max_active,
            },
            completion_input_digest=_canonical_digest(
                {
                    "state_digest": state["state_digest"],
                    "ray_sample_record_id": ray["ray_sample_record_id"],
                    "image_shape": self.image_shape,
                }
            ),
            source_record_ids=[state["implicit_field_state_id"], evaluation["evaluation_id"], ray["ray_sample_record_id"]],
        )

    def _append_observation_frame(
        self,
        *,
        event_kinds: Sequence[str],
        live_step_id: str | None = None,
        frame_kind: str,
        world_advanced: bool,
        camera_moved: bool,
        world_tick_window: tuple[int, int],
        state_override: Mapping[str, Any] | None = None,
        camera_pose_override: Mapping[str, Any] | None = None,
        observer_path_record_override: Mapping[str, Any] | None = None,
        source_camera_move_id: str | None = None,
        camera_action: str | None = None,
        previous_camera_pose_digest: str | None = None,
        result_camera_pose_digest: str | None = None,
        source_live_step_ids: Sequence[str] | None = None,
        source_interaction_audit_ids: Sequence[str] | None = None,
        playback_track: str = WORLD_RUN_TRACK,
    ) -> ProjectionFrame:
        state = copy.deepcopy(state_override) if state_override is not None else copy.deepcopy(self.current_state)
        _ensure_state_digest(state)
        tick = int(state["tick"])
        camera_pose = copy.deepcopy(camera_pose_override) if camera_pose_override is not None else copy.deepcopy(self.camera_pose)
        observer_path_record = (
            copy.deepcopy(observer_path_record_override)
            if observer_path_record_override is not None
            else copy.deepcopy(self.observer_path_record)
        )
        source_live_step_ids = list(source_live_step_ids or ([live_step_id] if live_step_id else []))
        source_interaction_audit_ids = list(source_interaction_audit_ids or [])
        camera_pose_id = str(observer_path_record["observer_path_id"])
        trace = trace_implicit_ray_camera(
            state,
            self.bases,
            observer_path_record=observer_path_record,
            observer_id=DEFAULT_OBSERVER_ID,
            tick=tick,
            camera_pose=camera_pose,
            image_shape=self.image_shape,
            samples_per_ray=self.samples_per_ray,
        )
        certificate = self._certificate(state, trace)
        self.evaluation_records.append(trace["evaluation_record"])
        self.ray_sample_records.append(trace["ray_sample_record"])
        self.image_planes.append(trace["image_plane"])
        self.authority_certificates.append(certificate)
        previous_structures = [record for record in self.observed_structure_records if int(record.get("state_tick", -1)) == int(tick) - 1]
        observed_structures = extract_implicit_observed_structures(
            state,
            self.bases,
            ray_sample_records=[trace["ray_sample_record"]],
            previous_structures=previous_structures,
        )
        self.observed_structure_records.extend(copy.deepcopy(observed_structures))
        frame = attach_implicit_field_payload_to_projection_frame(
            self._base_frame(tick, state["implicit_field_state_id"], event_kinds),
            implicit_field_state=state,
            implicit_authority_certificate=certificate,
            implicit_basis_records=self.bases,
            implicit_evaluation_records=[trace["evaluation_record"]],
            implicit_observer_path_record=observer_path_record,
            implicit_ray_sample_record=trace["ray_sample_record"],
            implicit_spectral_image_plane=trace["image_plane"],
            implicit_refinement_patch_ids=[patch["patch_id"] for patch in self.refinement_patches],
            implicit_baseline_comparison_ids=[comparison["comparison_id"] for comparison in self.baseline_comparisons],
        )
        timeline = dict(frame.payload["event_timeline"])
        timeline["event_kinds"] = list(event_kinds)
        timeline["interaction_record_ids"] = (
            list(source_interaction_audit_ids)
            if source_interaction_audit_ids
            else [audit["audit_id"] for audit in self.interaction_audits if audit.get("status") == "applied"]
        )
        timeline["source_record_ids"] = sorted(set(timeline["source_record_ids"] + [trace["ray_sample_record"]["ray_sample_record_id"], trace["image_plane"]["image_plane_id"]]))
        payload = {
            **frame.payload,
            "event_timeline": timeline,
            "timeline_semantics": _timeline_semantics(
                frame_kind=frame_kind,
                world_tick=tick,
                world_tick_window=world_tick_window,
                world_advanced=world_advanced,
                camera_moved=camera_moved,
                camera_pose_id=camera_pose_id,
                camera_action=camera_action,
                previous_camera_pose_digest=previous_camera_pose_digest,
                result_camera_pose_digest=result_camera_pose_digest,
                source_world_state_id=state["implicit_field_state_id"],
                source_world_state_digest=state["state_digest"],
                source_live_step_ids=source_live_step_ids,
                source_camera_move_id=source_camera_move_id,
                source_interaction_audit_ids=source_interaction_audit_ids,
                playback_track=playback_track,
                sequence_index=len(self.projection_frames),
            ),
            "implicit_live_session_id": self.session_id,
            "implicit_live_step_id": live_step_id,
            "implicit_interaction_audit_ids": [audit["audit_id"] for audit in self.interaction_audits],
            "implicit_runtime_mode": RUNTIME_MODE,
            "implicit_observed_structures": copy.deepcopy(observed_structures),
            "implicit_observed_structure_ids": [structure["structure_id"] for structure in observed_structures],
        }
        frame = replace(frame, payload=payload)
        frame = self._attach_five_phase_live_summary(
            frame=frame,
            implicit_field_state_id=str(state["implicit_field_state_id"]),
        )
        self.projection_frames.append(frame)
        return frame

    def _append_five_phase_causal_artifacts(self, *, observer_id: str) -> dict[str, Any]:
        previous_field = self.five_phase_live_field_states[-1] if self.five_phase_live_field_states else None
        previous_step = self.five_phase_live_steps[-1] if self.five_phase_live_steps else None
        previous_pattern_ids = {
            str(value) for value in (previous_step or {}).get("pattern_ids", [])
        }
        previous_residual_ids = {
            str(value) for value in (previous_step or {}).get("residual_constraint_ids", [])
        }
        previous_patterns = [
            record for record in self.five_phase_patterns if record.record_id in previous_pattern_ids
        ]
        previous_residuals = [
            record
            for record in self.five_phase_residual_constraints
            if record.record_id in previous_residual_ids
        ]
        current_step = (
            self.implicit_live_steps[-1]
            if self.implicit_live_steps and int(self.implicit_live_steps[-1].get("tick", -1)) == self.current_tick
            else None
        )
        realized_user = (current_step or {}).get("realized_user_input_projection", {})
        realized_feedback = (current_step or {}).get(
            "realized_five_phase_feedback_input_projection",
            {},
        )
        response_contexts: dict[str, dict[str, Any]] = {}
        if previous_patterns:
            if current_step is None:
                raise ValueError("matched FivePhase response requires the exact canonical transition")
            previous_state_id = str(current_step.get("previous_state_id", ""))
            previous_state = next(
                (
                    state
                    for state in self.implicit_field_states
                    if str(state.get("implicit_field_state_id", "")) == previous_state_id
                ),
                None,
            )
            if previous_state is None:
                raise ValueError("matched FivePhase response is missing its predecessor Field state")
            for pattern in previous_patterns:
                identity_id = str(pattern.payload.get("pattern_identity_id") or pattern.record_id)
                response_contexts[identity_id] = build_five_phase_transition_response_context(
                    previous_pattern=pattern,
                    previous_implicit_field_state=previous_state,
                    current_implicit_field_state=self.current_state,
                    implicit_basis_records=self.bases,
                    basis_spatial_index=self.basis_spatial_index,
                    realized_user_input_projection=realized_user,
                    realized_feedback_input_projection=realized_feedback,
                    tick=self.current_tick,
                    relaxation_horizon_ticks=ENERGY_SCOPE_RELAXATION_TICKS,
                )
        artifacts = build_five_phase_live_artifacts(
            implicit_field_state=self.current_state,
            implicit_basis_records=self.bases,
            basis_spatial_index=self.basis_spatial_index,
            run_id=self.run_id,
            bridge_index=len(self.five_phase_live_steps),
            previous_live_field_state=previous_field,
            observer_id=observer_id,
            frequency_window={"band": "wide"},
            previous_patterns=previous_patterns,
            previous_residual_constraints=previous_residuals,
            previous_live_step_id=str(previous_step["live_step_id"]) if previous_step else None,
            response_context_by_pattern_identity_id=response_contexts,
        )
        self.five_phase_live_bridges.extend(copy.deepcopy(artifacts["bridges"]))
        self.five_phase_live_field_states.extend(artifacts["field_states"])
        self.five_phase_phase_fields.extend(artifacts["phase_fields"])
        self.five_phase_constraint_sets.extend(artifacts["constraint_sets"])
        self.five_phase_patterns.extend(artifacts["patterns"])
        self.five_phase_lifecycle_records.extend(copy.deepcopy(artifacts["lifecycle_records"]))
        self.five_phase_traces.extend(artifacts["traces"])
        self.five_phase_residual_constraints.extend(artifacts["residual_constraints"])
        self.five_phase_agent_states.extend(artifacts["agent_states"])
        self.five_phase_feedback_records.extend(artifacts["feedback_records"])
        self.five_phase_live_steps.append(copy.deepcopy(artifacts["live_step"]))
        return copy.deepcopy(artifacts["live_step"])

    def _attach_five_phase_live_summary(
        self,
        *,
        frame: ProjectionFrame,
        implicit_field_state_id: str,
    ) -> ProjectionFrame:
        live_step = next(
            (
                step
                for step in reversed(self.five_phase_live_steps)
                if str(step.get("implicit_field_state_id")) == str(implicit_field_state_id)
            ),
            None,
        )
        if live_step is None:
            raise ValueError("projection frame has no causal FivePhase step")
        phase = next(
            (
                record
                for record in reversed(self.five_phase_phase_fields)
                if record.record_id == str(live_step["phase_field_id"])
            ),
            None,
        )
        if phase is None:
            raise ValueError("causal FivePhase step references missing phase field")
        pattern_ids = {str(value) for value in live_step.get("pattern_ids", [])}
        patterns = [
            record for record in self.five_phase_patterns if record.record_id in pattern_ids
        ]
        implicit_step = next(
            (
                step
                for step in reversed(self.implicit_live_steps)
                if str(step.get("result_state_id")) == str(implicit_field_state_id)
            ),
            None,
        )
        feedback_application = next(
            (
                record
                for record in reversed(self.five_phase_feedback_applications)
                if implicit_step is not None
                and str(record.get("implicit_live_step_id")) == str(implicit_step.get("step_id"))
            ),
            None,
        )
        energy_ledgers = list((implicit_step or {}).get("energy_ledgers", []))
        summary = {
            "schema": "five_phase_live_summary_v1",
            "tick": frame.tick,
            "live_step_id": live_step["live_step_id"],
            "phase_field_id": phase.record_id,
            "dominant_phase": phase.aggregate_phase.dominant_phase(),
            "aggregate_phase": phase.aggregate_phase.to_dict(),
            "pattern_ids": list(live_step["pattern_ids"]),
            "pattern_response": [
                {
                    "pattern_id": pattern.record_id,
                    "pattern_identity_id": pattern.payload.get("pattern_identity_id"),
                    "previous_pattern_record_id": pattern.payload.get("previous_pattern_record_id"),
                    "stability_score": float(pattern.stability_score),
                    "stability_formula": pattern.payload.get("stability_formula"),
                    "deformation_normalization": pattern.payload.get("deformation_normalization"),
                    "episode_id": pattern.payload.get("episode_id"),
                    "episode_status": pattern.payload.get("episode_status"),
                    "support_energy_setpoint": pattern.payload.get("support_energy_setpoint"),
                    "support_energy_current": pattern.payload.get("support_energy_current"),
                    "deformation_from_setpoint": pattern.payload.get("deformation_from_setpoint"),
                    "q_user": pattern.payload.get("q_user"),
                    "Q_live": pattern.payload.get("Q_live"),
                    "user_dose_normalization": pattern.payload.get("user_dose_normalization"),
                    "cumulative_realized_user_dose": pattern.payload.get("cumulative_realized_user_dose"),
                    "q_feedback": pattern.payload.get("q_feedback"),
                    "feedback_dose_normalization": pattern.payload.get("feedback_dose_normalization"),
                    "realized_feedback_dose": pattern.payload.get("realized_feedback_dose"),
                    "relaxation_from_peak": pattern.payload.get("relaxation_from_peak"),
                }
                for pattern in patterns
            ],
            "trace_ids": list(live_step["trace_ids"]),
            "feedback_record_ids": list(live_step["feedback_record_ids"]),
            "energy_response": {
                "implicit_live_step_id": (implicit_step or {}).get("step_id"),
                "raw_user_input_projection": copy.deepcopy(
                    (implicit_step or {}).get("raw_user_input_projection", {})
                ),
                "realized_user_input_projection": copy.deepcopy(
                    (implicit_step or {}).get("realized_user_input_projection", {})
                ),
                "raw_feedback_input_projection": copy.deepcopy(
                    (implicit_step or {}).get("raw_five_phase_feedback_input_projection", {})
                ),
                "realized_feedback_input_projection": copy.deepcopy(
                    (implicit_step or {}).get("realized_five_phase_feedback_input_projection", {})
                ),
                "ledger_count": len(energy_ledgers),
                "ledgers": [
                    {
                        key: ledger.get(key)
                        for key in (
                            "scope_id",
                            "scope_kind",
                            "energy_before",
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
                    }
                    for ledger in energy_ledgers
                ],
            },
            "feedback_application": (
                {
                    "application_record_id": feedback_application["application_record_id"],
                    "feedback_record_ids": list(feedback_application.get("feedback_record_ids", [])),
                    "feedback_enabled": bool(feedback_application.get("feedback_enabled")),
                    "feedback_applied": bool(feedback_application.get("feedback_applied")),
                    "feedback_consumed": bool(feedback_application.get("feedback_consumed")),
                    "eligibility_reason": feedback_application.get("eligibility_reason"),
                    "candidate_feedback_projection_digest": feedback_application.get(
                        "candidate_feedback_projection_digest"
                    ),
                    "applied_feedback_projection_digest": feedback_application.get(
                        "applied_feedback_projection_digest"
                    ),
                    "baseline_response_measurements": copy.deepcopy(
                        feedback_application.get("baseline_response_measurements", [])
                    ),
                    "candidate_response_measurements": copy.deepcopy(
                        feedback_application.get("candidate_response_measurements", [])
                    ),
                }
                if feedback_application is not None
                else None
            ),
            "source_record_ids": list(live_step["source_record_ids"]),
            "viewer_generated": False,
            "display_only": True,
            "is_authority_state": False,
        }
        if implicit_step is not None:
            summary["source_record_ids"] = list(
                dict.fromkeys([*summary["source_record_ids"], str(implicit_step["step_id"])])
            )
        if feedback_application is not None:
            summary["source_record_ids"] = list(
                dict.fromkeys(
                    [
                        *summary["source_record_ids"],
                        str(feedback_application["application_record_id"]),
                        *[str(value) for value in feedback_application.get("feedback_record_ids", [])],
                    ]
                )
            )
        payload = {**frame.payload, "five_phase_live_summary": summary}
        source_record_ids = list(dict.fromkeys([*frame.source_record_ids, *summary["source_record_ids"]]))
        return replace(frame, payload=payload, source_record_ids=source_record_ids)

    def _projection_frame_by_id(self, frame_id: str) -> ProjectionFrame:
        for frame in self.projection_frames:
            if frame.frame_id == frame_id:
                return frame
        raise ValueError("unknown source_projection_frame_id")

    def _require_latest_projection_frame_id(self, frame_id: str) -> ProjectionFrame:
        frame = self._projection_frame_by_id(frame_id)
        latest_frame_id = self.projection_frames[-1].frame_id if self.projection_frames else ""
        if str(frame_id) != str(latest_frame_id):
            raise ValueError("stale source_projection_frame_id")
        return frame

    def _state_for_projection_frame(self, frame: ProjectionFrame) -> dict[str, Any]:
        payload = frame.payload
        semantics = payload.get("timeline_semantics") or {}
        state_id = semantics.get("source_world_state_id") or payload.get("implicit_field_state_id")
        for state in self.implicit_field_states:
            if state.get("implicit_field_state_id") == state_id:
                copied = copy.deepcopy(state)
                _ensure_state_digest(copied)
                return copied
        raise ValueError("source projection frame state is not available")

    def _move_solar_earth_camera(self, request: Mapping[str, Any]) -> dict[str, Any]:
        if request.get("schema") != "implicit_camera_move_request":
            raise ValueError("solar earth camera move request schema mismatch")
        request_id = str(request.get("request_id", ""))
        if not request_id:
            raise ValueError("solar earth camera move requires request_id")
        if request_id in {str(record.get("request_id")) for record in self.camera_move_records}:
            raise ValueError("duplicate solar earth camera move request_id")
        observer_id = str(request.get("observer_id") or "observer::solar-earth-orbit")
        if observer_id not in self.observer_ids:
            raise ValueError("undeclared solar earth camera observer_id")
        action = str(request.get("action", ""))
        if action not in ALLOWED_SOLAR_EARTH_CAMERA_ACTIONS:
            raise ValueError("unsupported solar earth camera action")
        source_frame_id = str(request.get("source_projection_frame_id") or "")
        if source_frame_id:
            self._require_latest_projection_frame_id(source_frame_id)
        journal = self._begin_mutation_journal()
        try:
            scene = getattr(self, "solar_earth_scene")
            previous_pose = copy.deepcopy(self.camera_pose)
            camera_request = {
                "action": action,
                "step_world": float(request.get("step_world", 0.35)),
                "yaw_degrees": float(request.get("yaw_degrees", 8.0)),
                "sensor_band_mode": str(request.get("sensor_band_mode") or previous_pose.get("sensor_band_mode") or "visible_surface"),
                "request_id": request_id,
                "observer_id": observer_id,
            }
            result_pose = apply_solar_earth_camera_move(
                scene,
                previous_pose,
                camera_request,
                initial_camera_pose=self.initial_camera_pose,
                local_refinement_requests=self.refinement_requests,
                local_refinement_patches=self.refinement_patches,
            )
            previous_digest = _canonical_digest(previous_pose)
            result_digest = _canonical_digest(result_pose)
            camera_move_id = f"solar-earth-camera-move::{request_id}"
            self.camera_pose = result_pose
            frame = self._append_solar_earth_projection_frame(
                event_kinds=["solar_earth_camera_move"],
                source_camera_move_id=camera_move_id,
                camera_moved=True,
                camera_action=action,
                previous_camera_pose_digest=previous_digest,
                result_camera_pose_digest=result_digest,
                world_tick_window=[self.current_tick, self.current_tick],
                extra_source_record_ids=[camera_move_id, f"implicit-camera-move-request::{request_id}"],
            )
            record = {
                "schema": "solar_earth_camera_move_record",
                "camera_move_id": camera_move_id,
                "request_id": request_id,
                "observer_id": observer_id,
                "action": action,
                "previous_tick": self.current_tick,
                "result_tick": self.current_tick,
                "source_projection_frame_id": source_frame_id,
                "previous_camera_pose": previous_pose,
                "result_camera_pose": result_pose,
                "previous_camera_pose_digest": previous_digest,
                "result_camera_pose_digest": result_digest,
                "result_projection_frame_id": frame.frame_id,
                "source_record_ids": sorted(
                    set([camera_move_id, f"implicit-camera-move-request::{request_id}", source_frame_id, frame.frame_id])
                    - {""}
                ),
                "is_authority_state": False,
            }
            self.camera_move_records.append(record)
            return copy.deepcopy(record)
        except Exception:
            self._rollback_mutation_journal(journal)
            raise

    @_session_locked
    def render_frame(self, request: Mapping[str, Any]) -> dict[str, Any]:
        if not hasattr(self, "solar_earth_scene"):
            raise ValueError("realtime render_frame requires solar-earth session")
        journal = self._begin_mutation_journal()
        try:
            current_frame = self.projection_frames[-1]
            packet = current_frame.payload.get("realtime_projection_frame_packet") or {}
            current_camera_state_id = str((packet.get("camera_state") or {}).get("camera_state_id") or "")
            source_frame_id = str(request.get("source_projection_frame_id") or "")
            if source_frame_id != current_frame.frame_id:
                raise ValueError("stale source_projection_frame_id")
            validate_realtime_render_frame_request(
                request,
                current_frame_id=current_frame.frame_id,
                current_tick=self.current_tick,
                current_camera_state_id=current_camera_state_id,
                seen_request_ids=getattr(self, "render_frame_request_ids", set()),
            )
            action = str(request["camera_action"])
            if action not in ALLOWED_SOLAR_EARTH_CAMERA_ACTIONS:
                raise ValueError("unsupported solar earth camera action")
            previous_pose = copy.deepcopy(self.camera_pose)
            camera_request = {
                "action": action,
                "step_world": float(request.get("step_world", 0.35)),
                "yaw_degrees": float(request.get("yaw_degrees", 8.0)),
                "sensor_band_mode": str(request.get("sensor_band_mode") or previous_pose.get("sensor_band_mode") or "visible_surface"),
                "sensor_band_blend_factor": float(request.get("sensor_band_blend_factor", 1.0)),
                "request_id": str(request["request_id"]),
                "observer_id": str(request.get("observer_id") or "observer::solar-earth-orbit"),
            }
            result_pose = apply_solar_earth_camera_move(
                getattr(self, "solar_earth_scene"),
                previous_pose,
                camera_request,
                initial_camera_pose=self.initial_camera_pose,
                local_refinement_requests=self.refinement_requests,
                local_refinement_patches=self.refinement_patches,
            )
            previous_digest = _canonical_digest(previous_pose)
            result_digest = _canonical_digest(result_pose)
            camera_move_id = f"realtime-render-camera-move::{request['request_id']}"
            self.camera_pose = result_pose
            frame = self._append_solar_earth_projection_frame(
                event_kinds=["realtime_render_frame", "solar_earth_camera_move"],
                source_camera_move_id=camera_move_id,
                camera_moved=True,
                camera_action=action,
                previous_camera_pose_digest=previous_digest,
                result_camera_pose_digest=result_digest,
                world_tick_window=[self.current_tick, self.current_tick],
                extra_source_record_ids=[camera_move_id, f"realtime-render-frame-request::{request['request_id']}"],
                force_frame_kind="render_only_camera_frame",
            )
            record = {
                "schema": "realtime_render_frame_record",
                "camera_move_id": camera_move_id,
                "request_id": str(request["request_id"]),
                "observer_id": str(camera_request["observer_id"]),
                "action": action,
                "previous_tick": self.current_tick,
                "result_tick": self.current_tick,
                "source_projection_frame_id": source_frame_id,
                "previous_camera_pose": previous_pose,
                "result_camera_pose": result_pose,
                "previous_camera_pose_digest": previous_digest,
                "result_camera_pose_digest": result_digest,
                "result_projection_frame_id": frame.frame_id,
                "source_record_ids": sorted(
                    set([camera_move_id, f"realtime-render-frame-request::{request['request_id']}", source_frame_id, frame.frame_id])
                ),
                "is_authority_state": False,
            }
            self.camera_move_records.append(record)
            self.render_frame_request_ids.add(str(request["request_id"]))
            return {
                "schema": "realtime_render_frame_response",
                "request_id": str(request["request_id"]),
                "camera_moved": True,
                "result_projection_frame_id": frame.frame_id,
                "result_world_tick": self.current_tick,
                "projection_frame": frame,
            }
        except Exception:
            self._rollback_mutation_journal(journal)
            raise

    @_session_locked
    def move_camera(self, request: Mapping[str, Any]) -> dict[str, Any]:
        if hasattr(self, "solar_earth_scene"):
            return self._move_solar_earth_camera(request)
        validate_implicit_camera_move_request(
            request,
            declared_observer_ids=set(self.observer_ids),
            existing_request_ids={record["request_id"] for record in self.camera_move_records},
            known_projection_frames_by_id={frame.frame_id: frame.to_dict() for frame in self.projection_frames},
        )
        journal = self._begin_mutation_journal()
        try:
            source_frame = self._projection_frame_by_id(str(request["source_projection_frame_id"]))
            source_state = self._state_for_projection_frame(source_frame)
            before_state_id = str(source_state["implicit_field_state_id"])
            before_state_digest = str(source_state["state_digest"])
            before_ray = copy.deepcopy(source_frame.payload["implicit_ray_sample_record"])
            before_image = copy.deepcopy(source_frame.payload["implicit_spectral_image_plane"])
            previous_pose = copy.deepcopy(before_ray.get("camera_pose") or self.camera_pose)
            result_pose = apply_implicit_camera_move(previous_pose, request, initial_camera_pose=self.initial_camera_pose)
            record = build_implicit_camera_move_record(
                request,
                previous_camera_pose=previous_pose,
                result_camera_pose=result_pose,
                previous_state_id=before_state_id,
                result_state_id=before_state_id,
                previous_state_digest=before_state_digest,
                result_state_digest=before_state_digest,
            )
            self.camera_pose = result_pose
            self.observer_path_record = build_implicit_observer_path_record(
                observer_path_id=f"implicit-observer-path::{self.run_id}::camera::{len(self.camera_move_records) + 1}",
                observer_id=DEFAULT_OBSERVER_ID,
                tick_window=[int(source_state["tick"]), 10_000],
                camera_pose_records=[{"tick": int(source_state["tick"]), "camera_pose": result_pose}],
                source_record_ids=[before_state_id, record["camera_move_id"]],
            )
            self.observer_path_records.append(copy.deepcopy(self.observer_path_record))
            frame = self._append_observation_frame(
                event_kinds=["implicit_camera_move"],
                frame_kind=CAMERA_ONLY_OBSERVATION,
                world_advanced=False,
                camera_moved=True,
                world_tick_window=(int(source_state["tick"]), int(source_state["tick"])),
                state_override=source_state,
                camera_pose_override=result_pose,
                observer_path_record_override=self.observer_path_record,
                source_camera_move_id=record["camera_move_id"],
                camera_action=str(request["action"]),
                previous_camera_pose_digest=record["previous_camera_pose_digest"],
                result_camera_pose_digest=record["result_camera_pose_digest"],
                playback_track=CAMERA_PATH_TRACK,
            )
            completed = complete_implicit_camera_move_record(
                record,
                ray_sample_record_id=self.ray_sample_records[-1]["ray_sample_record_id"],
                image_plane_id=self.image_planes[-1]["image_plane_id"],
                projection_frame_id=frame.frame_id,
            )
            self.camera_move_records.append(completed)
            spatial = build_implicit_spatial_consistency_record(
                camera_move_id=completed["camera_move_id"],
                before_ray_sample_record_id=before_ray["ray_sample_record_id"],
                after_ray_sample_record_id=self.ray_sample_records[-1]["ray_sample_record_id"],
                before_image=before_image,
                after_image=self.image_planes[-1],
                source_state_digest=before_state_digest,
                result_state_digest=before_state_digest,
            )
            self.spatial_consistency_records.append(spatial)
            frame.payload["implicit_camera_move_ids"] = [completed["camera_move_id"]]
            frame.payload["implicit_spatial_consistency_ids"] = [spatial["spatial_consistency_id"]]
            return copy.deepcopy(completed)
        except Exception:
            self._rollback_mutation_journal(journal)
            raise

    def _live_step_record(
        self,
        *,
        tick: int,
        previous_state_id: str,
        previous_state_digest: str,
        result_state_id: str,
        result_state_digest: str,
        input_projection: Mapping[str, Mapping[str, float]],
        raw_user_input_projection: Mapping[str, Mapping[str, float]] | None = None,
        user_input_projection: Mapping[str, Mapping[str, float]] | None = None,
        raw_five_phase_feedback_input_projection: Mapping[str, Mapping[str, float]] | None = None,
        five_phase_feedback_input_projection: Mapping[str, Mapping[str, float]] | None = None,
        energy_ledgers: Sequence[Mapping[str, Any]] = (),
        pending_control_lineage: Sequence[Mapping[str, Any]] = (),
        five_phase_live_step_ids: Sequence[str] = (),
        five_phase_feedback_enabled: bool | None = None,
        five_phase_feedback_applied: bool = False,
        five_phase_feedback_application_id: str | None = None,
        applied_command_ids: Sequence[str],
        refinement_patch_ids: Sequence[str],
        runtime_cost_summary: Mapping[str, Any],
    ) -> dict[str, Any]:
        five_phase_source_ids = [str(value) for value in five_phase_live_step_ids]
        raw_user_projection = copy.deepcopy(dict(raw_user_input_projection or user_input_projection or {}))
        user_projection = copy.deepcopy(dict(user_input_projection or {}))
        raw_feedback_projection = copy.deepcopy(
            dict(raw_five_phase_feedback_input_projection or five_phase_feedback_input_projection or {})
        )
        feedback_projection = copy.deepcopy(dict(five_phase_feedback_input_projection or {}))
        step = {
            "schema": "implicit_live_step_record",
            "step_id": f"implicit-live-step::{self.session_id}::{tick}",
            "tick": int(tick),
            "previous_state_id": str(previous_state_id),
            "previous_state_digest": str(previous_state_digest),
            "result_state_id": str(result_state_id),
            "result_state_digest": str(result_state_digest),
            "input_projection_digest": _canonical_digest(input_projection),
            "raw_user_input_projection": raw_user_projection,
            "realized_user_input_projection": user_projection,
            "user_input_projection_digest": _canonical_digest(user_projection),
            "raw_five_phase_feedback_input_projection": raw_feedback_projection,
            "realized_five_phase_feedback_input_projection": feedback_projection,
            "merged_realized_input_projection": copy.deepcopy(dict(input_projection)),
            "merged_input_projection_digest": _canonical_digest(input_projection),
            "five_phase_feedback_enabled": bool(self.five_phase_feedback_enabled if five_phase_feedback_enabled is None else five_phase_feedback_enabled),
            "five_phase_feedback_applied": bool(five_phase_feedback_applied),
            "five_phase_feedback_application_id": five_phase_feedback_application_id,
            "five_phase_feedback_input_projection": feedback_projection,
            "energy_ledgers": copy.deepcopy([dict(ledger) for ledger in energy_ledgers]),
            "pending_control_lineage": copy.deepcopy([dict(item) for item in pending_control_lineage]),
            "five_phase_live_step_ids": list(five_phase_source_ids),
            "applied_command_ids": [str(value) for value in applied_command_ids],
            "refinement_patch_ids": [str(value) for value in refinement_patch_ids],
            "runtime_cost_summary": dict(runtime_cost_summary),
            "source_record_ids": list(
                dict.fromkeys(
                    [
                        str(previous_state_id),
                        str(result_state_id),
                        str(five_phase_feedback_application_id or ""),
                        *five_phase_source_ids,
                        *[str(value) for value in applied_command_ids],
                        *[str(value) for value in refinement_patch_ids],
                    ]
                )
            ),
            "is_authority_state": False,
        }
        step["source_record_ids"] = [source_id for source_id in step["source_record_ids"] if source_id]
        if step["runtime_cost_summary"].get("dense_volume_used") is not False:
            raise ValueError("implicit live step cannot use dense volume")
        return step

    def _append_five_phase_feedback_application(
        self,
        *,
        tick: int,
        implicit_live_step_id: str,
        previous_state_id: str,
        result_state_id: str,
        user_input_projection: Mapping[str, Mapping[str, float]],
        candidate_feedback_projection: Mapping[str, Mapping[str, float]],
        applied_feedback_projection: Mapping[str, Mapping[str, float]],
        merged_input_projection: Mapping[str, Mapping[str, float]],
        five_phase_live_step_ids: Sequence[str],
        feedback_record_ids: Sequence[str] = (),
        baseline_response_measurements: Sequence[Mapping[str, Any]] = (),
        candidate_response_measurements: Sequence[Mapping[str, Any]] = (),
        eligibility_reason: str = "no_candidate",
    ) -> dict[str, Any]:
        application_id = f"five-phase-feedback-application::{self.session_id}::{tick}"
        candidate = copy.deepcopy(dict(candidate_feedback_projection or {}))
        applied = copy.deepcopy(dict(applied_feedback_projection or {}))
        merged = copy.deepcopy(dict(merged_input_projection or {}))
        user_projection = copy.deepcopy(dict(user_input_projection or {}))
        record = {
            "schema": "five_phase_feedback_application_record_v2",
            "application_record_id": application_id,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "tick": int(tick),
            "implicit_live_step_id": str(implicit_live_step_id),
            "previous_state_id": str(previous_state_id),
            "result_state_id": str(result_state_id),
            "feedback_enabled": bool(self.five_phase_feedback_enabled),
            "feedback_applied": bool(applied),
            "feedback_consumed": True,
            "eligibility_reason": str(eligibility_reason),
            "feedback_record_ids": [str(value) for value in feedback_record_ids],
            "candidate_feedback_projection": candidate,
            "applied_feedback_projection": applied,
            "baseline_response_measurements": copy.deepcopy(
                [dict(value) for value in baseline_response_measurements]
            ),
            "candidate_response_measurements": copy.deepcopy(
                [dict(value) for value in candidate_response_measurements]
            ),
            "user_input_projection_digest": _canonical_digest(user_projection),
            "candidate_feedback_projection_digest": _canonical_digest(candidate),
            "applied_feedback_projection_digest": _canonical_digest(applied),
            "merged_input_projection_digest": _canonical_digest(merged),
            "five_phase_live_step_ids": [str(value) for value in five_phase_live_step_ids],
            "source_record_ids": list(
                dict.fromkeys(
                    [
                        application_id,
                        str(implicit_live_step_id),
                        str(previous_state_id),
                        str(result_state_id),
                        *[str(value) for value in five_phase_live_step_ids],
                        *[str(value) for value in feedback_record_ids],
                    ]
                )
            ),
            "is_authority_state": False,
        }
        self.five_phase_feedback_applications.append(record)
        return record

    def _complete_audits(
        self,
        *,
        command_ids: Sequence[str],
        result_state_id: str,
        frame: ProjectionFrame,
    ) -> None:
        command_set = set(command_ids)
        for audit in self.interaction_audits:
            if audit["command_id"] not in command_set:
                continue
            if not audit.get("applications"):
                audit["status"] = "applied"
            audit["result_state_id"] = str(result_state_id)
            ray_id = frame.payload["implicit_ray_sample_record"]["ray_sample_record_id"]
            if ray_id not in audit["resulting_ray_sample_record_ids"]:
                audit["resulting_ray_sample_record_ids"].append(ray_id)
            if frame.frame_id not in audit["resulting_projection_frame_ids"]:
                audit["resulting_projection_frame_ids"].append(frame.frame_id)
            audit["source_record_ids"] = sorted(set(audit["source_record_ids"] + [result_state_id, frame.frame_id]))

    def _applied_audit_ids(self, command_ids: Sequence[str]) -> list[str]:
        command_set = {str(value) for value in command_ids}
        return [audit["audit_id"] for audit in self.interaction_audits if audit["command_id"] in command_set]

    def _record_interaction_transcript(self, request: Mapping[str, Any], *, audit_id: str) -> None:
        self.interaction_transcript.append(
            {
                "schema": "implicit_interaction_transcript_entry_v1",
                "accepted_sequence": int(self._accepted_sequence),
                "audit_id": str(audit_id),
                "request": copy.deepcopy(dict(request)),
            }
        )

    def _advance_one_tick(self, *, append_frame: bool) -> tuple[dict[str, Any], list[str], ProjectionFrame | None, int]:
        previous_tick = self.current_tick
        next_tick = previous_tick + 1
        due = sorted(
            [item for item in self._pending_inputs if int(item["apply_tick"]) <= next_tick],
            key=lambda item: (
                int(item["apply_tick"]),
                int(item.get("accepted_sequence", -1)),
                str(item.get("request_id", "")),
            ),
        )
        if len(due) > MAX_DUE_CONTROLS_PER_TICK:
            raise ValueError("implicit runtime exceeds due control budget")

        raw_by_command: list[tuple[str, dict[str, dict[str, float]]]] = []
        pending_lineage: list[dict[str, Any]] = []
        updated_pending = [
            copy.deepcopy(item)
            for item in self._pending_inputs
            if int(item["apply_tick"]) > next_tick
        ]
        for item in due:
            command_id = str(item["command_id"])
            if item.get("kind") == "local_control":
                descriptor = item["control_descriptor"]
                schedule_index = int(item["next_schedule_index"])
                raw_projection = materialize_implicit_raw_control_projection(
                    descriptor,
                    schedule_index=schedule_index,
                )
                next_schedule_index = schedule_index + 1
                if next_schedule_index < len(descriptor["schedule_weights"]):
                    updated_pending.append(
                        {
                            **copy.deepcopy(item),
                            "apply_tick": next_tick + 1,
                            "next_schedule_index": next_schedule_index,
                        }
                    )
                pending_lineage.append(
                    {
                        "request_id": str(item["request_id"]),
                        "command_id": command_id,
                        "accepted_sequence": int(item["accepted_sequence"]),
                        "schedule_index": schedule_index,
                        "scope_id": str(item["scope_id"]),
                    }
                )
            else:
                schedule_index = 0
                raw_projection = copy.deepcopy(item["input_projection"])
                pending_lineage.append(
                    {
                        "request_id": str(item.get("request_id", command_id)),
                        "command_id": command_id,
                        "accepted_sequence": int(item.get("accepted_sequence", -1)),
                        "schedule_index": schedule_index,
                        "scope_id": None,
                    }
                )
            raw_by_command.append((command_id, raw_projection))

        raw_user_input_projection = _merge_projection([projection for _command_id, projection in raw_by_command])
        if _projection_l1(raw_user_input_projection) > MAX_USER_INPUT_L1_PER_TICK + 1e-12:
            raise ValueError("implicit user input exceeds per-tick L1 budget")

        active_scope_records = [
            scope
            for scope in self._active_energy_scopes
            if int(scope["activation_tick"]) <= next_tick <= int(scope["expiry_tick"])
        ]
        if len(active_scope_records) > MAX_ACTIVE_ENERGY_SCOPES:
            raise ValueError("implicit runtime exceeds active local energy scope budget")
        local_energy_scopes = {
            str(scope["scope_id"]): copy.deepcopy(scope["kappa_by_basis"])
            for scope in sorted(active_scope_records, key=lambda value: str(value["scope_id"]))
        }
        five_phase_projection: dict[str, dict[str, float]] = {}
        five_phase_source_step_ids: list[str] = []
        predecessor_feedback: list[FivePhaseFeedbackRecord] = []
        predecessor_patterns: list[FivePhasePatternRecord] = []
        predecessor_agents: list[FivePhaseAgentStateRecord] = []
        if self.five_phase_live_steps:
            predecessor_step = self.five_phase_live_steps[-1]
            feedback_ids = {str(value) for value in predecessor_step.get("feedback_record_ids", [])}
            pattern_ids = {str(value) for value in predecessor_step.get("pattern_ids", [])}
            agent_ids = {str(value) for value in predecessor_step.get("agent_state_ids", [])}
            predecessor_feedback = [
                record for record in self.five_phase_feedback_records if record.record_id in feedback_ids
            ]
            predecessor_patterns = [
                record for record in self.five_phase_patterns if record.record_id in pattern_ids
            ]
            predecessor_agents = [
                record for record in self.five_phase_agent_states if record.record_id in agent_ids
            ]
            five_phase_projection = five_phase_feedback_to_implicit_input_projection(
                feedback_records=predecessor_feedback,
                patterns=predecessor_patterns,
                implicit_basis_records=self.bases,
            )
            five_phase_source_step_ids = [str(predecessor_step["live_step_id"])]
        if _projection_l1(five_phase_projection) > MAX_FEEDBACK_INPUT_L1_PER_TICK + 1e-12:
            raise ValueError("implicit Feedback exceeds per-tick L1 budget")

        new_feedback_scope_records = [
            {
                "scope_id": f"implicit-feedback-energy-scope::{feedback.record_id}",
                "feedback_record_id": feedback.record_id,
                "source_kind": "five_phase_feedback",
                "kappa_by_basis": {str(feedback.target_basis_id): 1.0},
                "activation_tick": next_tick,
                "final_input_tick": next_tick,
                "expiry_tick": next_tick + ENERGY_SCOPE_RELAXATION_TICKS,
            }
            for feedback in predecessor_feedback
            if feedback.target_basis_id is not None
        ]
        if len(active_scope_records) + len(new_feedback_scope_records) > MAX_ACTIVE_ENERGY_SCOPES:
            raise ValueError("implicit runtime exceeds active local energy scope budget")
        measurement_scopes = {
            **local_energy_scopes,
            **{
                str(scope["scope_id"]): copy.deepcopy(scope["kappa_by_basis"])
                for scope in new_feedback_scope_records
            },
        }
        applied_command_ids = [str(item["command_id"]) for item in due]
        previous_state_id = self.current_state["implicit_field_state_id"]
        previous_state_digest = str(self.current_state["state_digest"])
        baseline_advanced = advance_implicit_field_state(
            self.current_state,
            self.bases,
            user_input_projection=raw_user_input_projection,
            feedback_input_projection={},
            local_energy_scopes=measurement_scopes,
        )
        baseline_measurements: list[dict[str, Any]] = []
        candidate_measurements: list[dict[str, Any]] = []
        feedback_precommit_eligible = False
        eligibility_reason = "no_candidate"
        candidate_advanced = None
        if predecessor_feedback:
            patterns_by_id = {record.record_id: record for record in predecessor_patterns}
            agents_by_id = {record.record_id: record for record in predecessor_agents}
            candidate_advanced = advance_implicit_field_state(
                self.current_state,
                self.bases,
                user_input_projection=raw_user_input_projection,
                feedback_input_projection=five_phase_projection,
                local_energy_scopes=measurement_scopes,
            )
            baseline_preview = self._retag_state(baseline_advanced, next_tick)
            candidate_preview = self._retag_state(candidate_advanced, next_tick)
            for feedback in sorted(predecessor_feedback, key=lambda record: record.record_id):
                pattern = patterns_by_id.get(feedback.pattern_id)
                agent = agents_by_id.get(feedback.agent_state_id)
                if pattern is None or agent is None:
                    raise ValueError("Feedback application has incomplete predecessor lineage")
                baseline_measurements.append(
                    measure_five_phase_feedback_response(
                        implicit_field_state=baseline_preview,
                        implicit_basis_records=self.bases,
                        basis_spatial_index=self.basis_spatial_index,
                        pattern=pattern,
                        agent_state=agent,
                        feedback=feedback,
                    )
                )
                candidate_measurements.append(
                    measure_five_phase_feedback_response(
                        implicit_field_state=candidate_preview,
                        implicit_basis_records=self.bases,
                        basis_spatial_index=self.basis_spatial_index,
                        pattern=pattern,
                        agent_state=agent,
                        feedback=feedback,
                    )
                )
            directions_eligible = all(
                bool(measurement["candidate_direction_eligible"])
                for measurement in baseline_measurements
            )
            errors_improve = all(
                float(candidate["absolute_error"])
                < float(baseline["absolute_error"]) - FEEDBACK_ERROR_IMPROVEMENT_TOLERANCE
                for baseline, candidate in zip(baseline_measurements, candidate_measurements)
            )
            feedback_precommit_eligible = directions_eligible and errors_improve
            if not directions_eligible:
                eligibility_reason = "application_direction_ineligible"
            elif not errors_improve:
                eligibility_reason = "application_error_not_reduced"
            elif not self.five_phase_feedback_enabled:
                eligibility_reason = "feedback_disabled_baseline"
            else:
                eligibility_reason = "eligible_error_reduction"
        raw_five_phase_projection = (
            five_phase_projection
            if self.five_phase_feedback_enabled and feedback_precommit_eligible
            else {}
        )
        advanced = (
            candidate_advanced
            if raw_five_phase_projection and candidate_advanced is not None
            else baseline_advanced
        )
        density_response = advanced.get("energy_summary", {}).get("density_response", {})
        realized_user_input_projection = copy.deepcopy(density_response.get("realized_user_projection", {}))
        applied_five_phase_projection = copy.deepcopy(density_response.get("realized_feedback_projection", {}))
        input_projection = copy.deepcopy(density_response.get("merged_realized_projection", {}))
        energy_ledgers = copy.deepcopy(density_response.get("ledgers", []))
        attributed_realized = _attribute_realized_user_projections(
            raw_by_command,
            aggregate_realized=realized_user_input_projection,
        )

        updated_audits = list(self.interaction_audits)
        audit_index_by_command = {
            str(audit["command_id"]): index for index, audit in enumerate(updated_audits)
        }
        for item in due:
            if item.get("kind") != "local_control":
                continue
            command_id = str(item["command_id"])
            audit_index = audit_index_by_command.get(command_id)
            if audit_index is None:
                raise ValueError("pending local control has no interaction audit")
            updated_audits[audit_index] = record_implicit_interaction_application(
                updated_audits[audit_index],
                tick=next_tick,
                schedule_index=int(item["next_schedule_index"]),
                raw_input_projection=dict(raw_by_command[applied_command_ids.index(command_id)][1]),
                realized_input_projection=attributed_realized[command_id],
            )
            updated_audits[audit_index]["result_state_id"] = f"implicit-field-state::{self.run_id}::{next_tick}"

        self._pending_inputs = sorted(
            updated_pending,
            key=lambda item: (
                int(item["apply_tick"]),
                int(item.get("accepted_sequence", -1)),
                str(item.get("request_id", "")),
            ),
        )
        self._active_energy_scopes = [
            copy.deepcopy(scope)
            for scope in self._active_energy_scopes
            if int(scope["expiry_tick"]) > next_tick
        ] + (
            copy.deepcopy(new_feedback_scope_records) if feedback_precommit_eligible else []
        )
        self.interaction_audits = updated_audits
        self.current_state = self._retag_state(advanced, int(advanced["tick"]))
        self.implicit_field_states.append(copy.deepcopy(self.current_state))
        step = self._live_step_record(
            tick=self.current_tick,
            previous_state_id=previous_state_id,
            previous_state_digest=previous_state_digest,
            result_state_id=self.current_state["implicit_field_state_id"],
            result_state_digest=str(self.current_state["state_digest"]),
            input_projection=input_projection,
            raw_user_input_projection=raw_user_input_projection,
            user_input_projection=realized_user_input_projection,
            raw_five_phase_feedback_input_projection=raw_five_phase_projection,
            five_phase_feedback_input_projection=applied_five_phase_projection,
            energy_ledgers=energy_ledgers,
            pending_control_lineage=pending_lineage,
            five_phase_live_step_ids=five_phase_source_step_ids,
            five_phase_feedback_enabled=self.five_phase_feedback_enabled,
            five_phase_feedback_applied=bool(applied_five_phase_projection),
            applied_command_ids=applied_command_ids,
            refinement_patch_ids=[],
            runtime_cost_summary=self.current_state.get("runtime_cost_summary", {"dense_volume_used": False}),
        )
        application = self._append_five_phase_feedback_application(
            tick=self.current_tick,
            implicit_live_step_id=step["step_id"],
            previous_state_id=previous_state_id,
            result_state_id=self.current_state["implicit_field_state_id"],
            user_input_projection=realized_user_input_projection,
            candidate_feedback_projection=five_phase_projection,
            applied_feedback_projection=applied_five_phase_projection,
            merged_input_projection=input_projection,
            five_phase_live_step_ids=five_phase_source_step_ids,
            feedback_record_ids=[record.record_id for record in predecessor_feedback],
            baseline_response_measurements=baseline_measurements,
            candidate_response_measurements=candidate_measurements,
            eligibility_reason=eligibility_reason,
        )
        step["five_phase_feedback_application_id"] = application["application_record_id"]
        step["source_record_ids"] = list(dict.fromkeys([*step["source_record_ids"], application["application_record_id"]]))
        self.implicit_live_steps.append(step)
        self._append_five_phase_causal_artifacts(observer_id=DEFAULT_OBSERVER_ID)
        frame = None
        if append_frame:
            source_interaction_audit_ids = self._applied_audit_ids(applied_command_ids)
            frame = self._append_observation_frame(
                event_kinds=["implicit_live_step", "implicit_interaction_applied"] if applied_command_ids else ["implicit_live_step"],
                live_step_id=step["step_id"],
                frame_kind=INTERACTION_STEP_OBSERVATION if applied_command_ids else WORLD_STEP_OBSERVATION,
                world_advanced=True,
                camera_moved=False,
                world_tick_window=(previous_tick, self.current_tick),
                source_live_step_ids=[step["step_id"]],
                source_interaction_audit_ids=source_interaction_audit_ids,
                playback_track=WORLD_RUN_TRACK,
            )
            self._complete_audits(command_ids=applied_command_ids, result_state_id=self.current_state["implicit_field_state_id"], frame=frame)
        return step, applied_command_ids, frame, previous_tick

    @_session_locked
    def advance(self, ticks: int = 1) -> None:
        tick_count = canonical_implicit_tick_count(ticks, name="advance ticks")
        journal = self._begin_mutation_journal()
        try:
            if hasattr(self, "solar_earth_scene"):
                scene = getattr(self, "solar_earth_scene")
                for _ in range(tick_count):
                    scene = advance_solar_earth_scene(scene, ticks=1)
                    self.solar_earth_scene = scene
                    self.current_state = copy.deepcopy(scene.implicit_state.state)
                    self.implicit_field_states.append(copy.deepcopy(self.current_state))
                    frame = self._append_solar_earth_projection_frame(event_kinds=["solar_earth_live_step", "planet_energy_flux"])
                    self.implicit_live_steps.append(
                        {
                            "schema": "solar_earth_live_step_record",
                            "step_id": f"solar-earth-live-step::{self.session_id}::{scene.tick}",
                            "tick": scene.tick,
                            "result_projection_frame_id": frame.frame_id,
                            "source_record_ids": list(frame.source_record_ids),
                            "is_authority_state": False,
                        }
                    )
                return
            for _ in range(tick_count):
                self._advance_one_tick(append_frame=True)
        except Exception:
            self._rollback_mutation_journal(journal)
            raise

    @_session_locked
    def run_step(self, request: Mapping[str, Any]) -> dict[str, Any]:
        journal = self._begin_mutation_journal()
        try:
            return self._run_step_unchecked(request)
        except Exception:
            self._rollback_mutation_journal(journal)
            raise

    def _run_step_unchecked(self, request: Mapping[str, Any]) -> dict[str, Any]:
        if request.get("schema") != "implicit_world_run_step_request":
            raise ValueError("implicit world run step request schema mismatch")
        request_id = str(request.get("request_id", ""))
        if not request_id:
            raise ValueError("implicit world run step request requires request_id")
        if request_id in self.run_step_request_ids:
            raise ValueError("duplicate implicit world run step request_id")
        if hasattr(self, "solar_earth_scene"):
            observer_id = str(request.get("observer_id") or "observer::solar-earth-orbit")
            if observer_id not in self.observer_ids:
                raise ValueError("undeclared solar earth run step observer_id")
            ticks = canonical_implicit_tick_count(
                request.get("ticks", 1),
                name="run_step ticks",
            )
            source_frame_id = str(request.get("source_projection_frame_id") or "")
            if source_frame_id:
                self._require_latest_projection_frame_id(source_frame_id)
            start_tick = self.current_tick
            camera_action = request.get("camera_action")
            camera_action = None if camera_action in {None, ""} else str(camera_action)
            sensor_band_mode = request.get("sensor_band_mode")
            sensor_band_mode = None if sensor_band_mode in {None, ""} else str(sensor_band_mode)
            if sensor_band_mode is not None and sensor_band_mode not in ALLOWED_SOLAR_EARTH_SENSOR_BAND_MODES:
                raise ValueError("unsupported solar earth sensor_band_mode")
            previous_camera_pose_digest = None
            result_camera_pose_digest = None
            camera_move_id = None
            camera_record = None
            camera_substep_poses: list[dict[str, Any]] = []
            previous_pose = None
            camera_request = None
            if camera_action is not None:
                if camera_action not in ALLOWED_SOLAR_EARTH_CAMERA_ACTIONS:
                    raise ValueError("unsupported solar earth camera action")
                previous_pose = copy.deepcopy(self.camera_pose)
                camera_request = {
                    "action": camera_action,
                    "step_world": float(request.get("camera_step_world", 0.35)),
                    "yaw_degrees": float(request.get("camera_yaw_degrees", 8.0)),
                    "sensor_band_mode": sensor_band_mode or self.camera_pose.get("sensor_band_mode") or "visible_surface",
                    "request_id": request_id,
                    "observer_id": observer_id,
                }
                previous_camera_pose_digest = _canonical_digest(previous_pose)
                camera_move_id = f"solar-earth-camera-step::{request_id}"
            scene = advance_solar_earth_scene(getattr(self, "solar_earth_scene"), ticks=ticks)
            self.solar_earth_scene = scene
            if camera_action is not None and previous_pose is not None and camera_request is not None:
                substep_count = _solar_earth_camera_substep_count(request, previous_pose, ticks)
                result_pose = previous_pose
                for substep_index in range(substep_count):
                    substep_request = {
                        **camera_request,
                        "request_id": f"{request_id}::camera-substep::{substep_index + 1}",
                    }
                    result_pose = apply_solar_earth_camera_move(
                        scene,
                        result_pose,
                        substep_request,
                        initial_camera_pose=self.initial_camera_pose,
                        local_refinement_requests=self.refinement_requests,
                        local_refinement_patches=self.refinement_patches,
                    )
                    camera_substep_poses.append(
                        {
                            "substep_index": substep_index + 1,
                            "camera_pose": copy.deepcopy(result_pose),
                            "camera_pose_digest": _canonical_digest(result_pose),
                        }
                    )
                result_camera_pose_digest = _canonical_digest(result_pose)
                self.camera_pose = result_pose
                camera_record = {
                    "schema": "solar_earth_camera_step_record",
                    "camera_move_id": camera_move_id,
                    "request_id": request_id,
                    "observer_id": observer_id,
                    "action": camera_action,
                    "previous_tick": start_tick,
                    "source_projection_frame_id": str(request.get("source_projection_frame_id") or ""),
                    "previous_camera_pose": previous_pose,
                    "result_camera_pose": result_pose,
                    "previous_camera_pose_digest": previous_camera_pose_digest,
                    "result_camera_pose_digest": result_camera_pose_digest,
                    "camera_steps_per_world_tick": max(1, substep_count // max(1, ticks)),
                    "camera_substep_count": substep_count,
                    "camera_substep_poses": copy.deepcopy(camera_substep_poses),
                    "is_authority_state": False,
                }
            elif sensor_band_mode is not None:
                self.camera_pose = {**copy.deepcopy(self.camera_pose), "sensor_band_mode": sensor_band_mode}
            self.current_state = copy.deepcopy(scene.implicit_state.state)
            self.implicit_field_states.append(copy.deepcopy(self.current_state))
            step_id = f"solar-earth-live-step::{self.session_id}::{scene.tick}"
            event_kinds = ["solar_earth_live_step", "planet_energy_flux"]
            if camera_action:
                event_kinds.append("implicit_camera_world_step")
            extra_source_record_ids = [f"implicit-world-run-step-request::{request_id}"]
            if camera_move_id:
                extra_source_record_ids.append(camera_move_id)
            frame = self._append_solar_earth_projection_frame(
                event_kinds=event_kinds,
                source_live_step_ids=[step_id],
                source_camera_move_id=camera_move_id,
                camera_moved=camera_action is not None,
                camera_action=camera_action,
                previous_camera_pose_digest=previous_camera_pose_digest,
                result_camera_pose_digest=result_camera_pose_digest,
                world_tick_window=[start_tick, scene.tick],
                extra_source_record_ids=extra_source_record_ids,
            )
            step = {
                "schema": "solar_earth_live_step_record",
                "step_id": step_id,
                "tick": scene.tick,
                "previous_tick": start_tick,
                "result_projection_frame_id": frame.frame_id,
                "source_record_ids": list(frame.source_record_ids),
                "is_authority_state": False,
            }
            self.implicit_live_steps.append(step)
            if camera_record is not None:
                camera_record["result_tick"] = scene.tick
                camera_record["result_projection_frame_id"] = frame.frame_id
                camera_record["source_record_ids"] = sorted(
                    set(
                        [
                            f"implicit-world-run-step-request::{request_id}",
                            step_id,
                            frame.frame_id,
                            camera_record["source_projection_frame_id"],
                        ]
                    )
                    - {""}
                )
                self.camera_move_records.append(camera_record)
            self.run_step_request_ids.add(request_id)
            return {
                "schema": "implicit_world_run_step_response",
                "request_id": request_id,
                "advanced_ticks": ticks,
                "camera_moved": camera_action is not None,
                "result_projection_frame_id": frame.frame_id,
                "result_world_tick": self.current_tick,
                "projection_frame": frame,
            }
        observer_id = str(request.get("observer_id", ""))
        if observer_id not in self.observer_ids:
            raise ValueError("undeclared implicit world run step observer_id")
        ticks = canonical_implicit_tick_count(
            request.get("ticks", 0),
            name="run_step ticks",
        )

        source_frame_id = str(request.get("source_projection_frame_id") or "")
        if source_frame_id:
            source_frame = self._projection_frame_by_id(source_frame_id)
            source_state = self._state_for_projection_frame(source_frame)
            if str(source_state["implicit_field_state_id"]) != str(self.current_state["implicit_field_state_id"]):
                raise ValueError("source projection frame must cite current world state for /run_step")

        camera_action = request.get("camera_action")
        camera_action = None if camera_action in {None, ""} else str(camera_action)
        previous_camera_pose_digest = None
        result_camera_pose_digest = None
        if camera_action is not None:
            if camera_action not in ALLOWED_IMPLICIT_CAMERA_ACTIONS:
                raise ValueError("unsupported implicit camera action")
            previous_pose = copy.deepcopy(self.camera_pose)
            camera_request = {
                "action": camera_action,
                "step_world": float(request.get("camera_step_world", 0.35)),
                "yaw_degrees": float(request.get("camera_yaw_degrees", 8.0)),
            }
            result_pose = apply_implicit_camera_move(previous_pose, camera_request, initial_camera_pose=self.initial_camera_pose)
            previous_camera_pose_digest = _canonical_digest(previous_pose)
            result_camera_pose_digest = _canonical_digest(result_pose)
            self.camera_pose = result_pose
            self.observer_path_record = build_implicit_observer_path_record(
                observer_path_id=f"implicit-observer-path::{self.run_id}::run-camera::{len(self.observer_path_records) + 1}",
                observer_id=DEFAULT_OBSERVER_ID,
                tick_window=[self.current_tick, 10_000],
                camera_pose_records=[{"tick": self.current_tick, "camera_pose": result_pose}],
                source_record_ids=[self.current_state["implicit_field_state_id"], f"implicit-world-run-step-request::{request_id}"],
            )
            self.observer_path_records.append(copy.deepcopy(self.observer_path_record))

        start_tick = self.current_tick
        source_live_step_ids: list[str] = []
        applied_command_ids: list[str] = []
        for _ in range(ticks):
            step, command_ids, _frame, _previous_tick = self._advance_one_tick(append_frame=False)
            source_live_step_ids.append(step["step_id"])
            applied_command_ids.extend(command_ids)

        source_interaction_audit_ids = self._applied_audit_ids(applied_command_ids)
        frame_kind = (
            INTERACTION_STEP_OBSERVATION
            if source_interaction_audit_ids
            else CAMERA_WORLD_STEP_OBSERVATION
            if camera_action
            else WORLD_STEP_OBSERVATION
        )
        event_kinds = ["implicit_live_step"]
        if camera_action:
            event_kinds.append("implicit_camera_world_step")
        if source_interaction_audit_ids:
            event_kinds.append("implicit_interaction_applied")
        frame = self._append_observation_frame(
            event_kinds=event_kinds,
            live_step_id=source_live_step_ids[-1] if source_live_step_ids else None,
            frame_kind=frame_kind,
            world_advanced=True,
            camera_moved=camera_action is not None,
            world_tick_window=(start_tick, self.current_tick),
            camera_action=camera_action,
            previous_camera_pose_digest=previous_camera_pose_digest,
            result_camera_pose_digest=result_camera_pose_digest,
            source_live_step_ids=source_live_step_ids,
            source_interaction_audit_ids=source_interaction_audit_ids,
            playback_track=WORLD_RUN_TRACK,
        )
        self._complete_audits(
            command_ids=applied_command_ids,
            result_state_id=self.current_state["implicit_field_state_id"],
            frame=frame,
        )
        self.run_step_request_ids.add(request_id)
        return {
            "schema": "implicit_world_run_step_response",
            "request_id": request_id,
            "advanced_ticks": ticks,
            "camera_moved": camera_action is not None,
            "result_projection_frame_id": frame.frame_id,
            "result_world_tick": self.current_tick,
        }

    def _append_solar_earth_projection_frame(
        self,
        *,
        event_kinds: Sequence[str],
        local_refinement_request_ids: Sequence[str] | None = None,
        local_refinement_patch_ids: Sequence[str] | None = None,
        source_live_step_ids: Sequence[str] | None = None,
        source_camera_move_id: str | None = None,
        camera_moved: bool = False,
        camera_action: str | None = None,
        previous_camera_pose_digest: str | None = None,
        result_camera_pose_digest: str | None = None,
        world_tick_window: Sequence[int] | None = None,
        extra_source_record_ids: Sequence[str] | None = None,
        force_frame_kind: str | None = None,
    ) -> ProjectionFrame:
        scene = getattr(self, "solar_earth_scene")
        frame = project_solar_earth_scene(
            scene,
            observer_id="observer::solar-earth-orbit",
            camera_pose=self.camera_pose,
            include_debug_bands=False,
            local_refinement_requests=self.refinement_requests,
            local_refinement_patches=self.refinement_patches,
        )
        existing_frame_ids = {existing.frame_id for existing in self.projection_frames}
        if frame.frame_id in existing_frame_ids:
            frame = replace(frame, frame_id=f"{frame.frame_id}::{len(self.projection_frames)}")

        local_refinement_request_ids = [str(value) for value in (local_refinement_request_ids or [])]
        local_refinement_patch_ids = [str(value) for value in (local_refinement_patch_ids or [])]
        source_live_step_ids = [str(value) for value in (source_live_step_ids or [])]
        extra_source_record_ids = [str(value) for value in (extra_source_record_ids or [])]
        local_refinement_source_ids = [*local_refinement_request_ids, *local_refinement_patch_ids]
        timeline = dict(frame.payload["event_timeline"])
        timeline["event_kinds"] = list(event_kinds)
        timeline["source_record_ids"] = sorted(set([*timeline["source_record_ids"], *local_refinement_source_ids, *extra_source_record_ids]))
        payload = dict(frame.payload)
        semantics = dict(payload["timeline_semantics"])
        semantics["camera_moved"] = bool(camera_moved)
        semantics["camera_action"] = camera_action
        semantics["previous_camera_pose_digest"] = previous_camera_pose_digest
        semantics["result_camera_pose_digest"] = result_camera_pose_digest
        semantics["source_live_step_ids"] = source_live_step_ids
        semantics["source_camera_move_id"] = source_camera_move_id
        if world_tick_window is not None:
            semantics["world_tick_window"] = [int(value) for value in world_tick_window]
        projection = dict(payload["solar_earth_projection"])
        projection["local_refinement_request_ids"] = local_refinement_request_ids
        projection["local_refinement_patch_ids"] = local_refinement_patch_ids
        image_plane = copy.deepcopy(payload["spectral_image_plane"])
        world_tick_delta = 0
        if world_tick_window is not None:
            parsed_window = [int(value) for value in world_tick_window]
            world_tick_delta = max(0, parsed_window[1] - parsed_window[0]) if len(parsed_window) == 2 else 0
            world_advanced = world_tick_delta > 0
        else:
            world_advanced = False
        frame_kind = (
            force_frame_kind
            if force_frame_kind is not None
            else
            "world_step_with_camera"
            if world_advanced and camera_moved
            else "world_step"
            if world_advanced
            else "camera_only"
            if camera_moved
            else image_plane.get("camera_ray_bundle", {}).get("frame_kind", "camera_only")
        )
        if "camera_ray_bundle" in image_plane:
            image_plane["camera_ray_bundle"] = {**dict(image_plane["camera_ray_bundle"]), "frame_kind": frame_kind}
        if "camera_scale_state" in image_plane:
            image_plane["camera_scale_state"] = {**dict(image_plane["camera_scale_state"]), "frame_kind": frame_kind}
        image_plane["projection_frame_digest"] = _refresh_image_plane_digest(image_plane)
        payload["timeline_semantics"] = semantics
        semantics["frame_kind"] = force_frame_kind or ("world_step_projection" if world_advanced else "render_only_camera_frame" if camera_moved else semantics.get("frame_kind"))
        semantics["world_advanced"] = bool(world_advanced)
        payload["event_timeline"] = timeline
        payload["solar_earth_projection"] = projection
        payload["spectral_image_plane"] = image_plane
        packet = copy.deepcopy(payload.get("realtime_projection_frame_packet") or {})
        if packet:
            packet["frame_kind"] = "world_step_projection" if world_advanced else "render_only_camera_frame" if camera_moved else packet.get("frame_kind")
            packet["world_tick_delta"] = world_tick_delta
            packet["source_scene_tick"] = self.current_tick
            packet["packet_id"] = f"realtime-projection-packet::{frame.frame_id}"
            payload["realtime_projection_frame_packet"] = packet
        frame = replace(
            frame,
            payload=payload,
            source_record_ids=sorted(set([*frame.source_record_ids, *local_refinement_source_ids, *extra_source_record_ids])),
        )
        self.projection_frames.append(frame)
        self.image_planes.append(copy.deepcopy(frame.payload["spectral_image_plane"]))
        return frame

    def _attach_solar_earth_visible_interaction_response(
        self,
        frame: ProjectionFrame,
        *,
        request: Any,
        patch: Any,
        audit: Mapping[str, Any],
        image_xy: Sequence[float] | None,
    ) -> ProjectionFrame:
        source_ids = sorted(
            set(
                [
                    str(audit["audit_id"]),
                    str(audit["command_id"]),
                    str(request.request_id),
                    str(patch.patch_id),
                    str(patch.final_patch_digest),
                    *[str(value) for value in request.source_record_ids],
                    *[str(value) for value in patch.source_record_ids],
                ]
            )
        )
        visible_response = {
            "schema": "visible_interaction_response_v1",
            "visible_response_id": f"visible-interaction-response::{str(request.request_id).split('::')[-1]}",
            "interaction_audit_id": str(audit["audit_id"]),
            "affected_region_ids": [str(value) for value in request.source_layer_shell_ids],
            "response_kind": "surface_refinement_wavefront",
            "pre_response_digest": str(request.request_id),
            "post_response_digest": str(patch.final_patch_digest),
            "screen_response_energy": round(max(0.03, min(1.0, float(request.requested_radius_world) * 1.6)), 6),
            "source_record_ids": source_ids,
            "is_authority_state": False,
        }
        xy = [0.5, 0.5] if image_xy is None else [max(0.0, min(1.0, float(image_xy[0]))), max(0.0, min(1.0, float(image_xy[1])))]
        overlay = {
            "schema": "interaction_overlay_v1",
            "overlay_id": f"projection-response-overlay::{str(request.request_id).split('::')[-1]}",
            "visible_response_id": visible_response["visible_response_id"],
            "interaction_trace_id": str(audit["interaction_trace_id"]),
            "parent_request_id": str(request.request_id),
            "command_id": str(audit["command_id"]),
            "interaction_record_id": str(audit["audit_id"]),
            "tool": "local_excite",
            "channel": "surface_spectral_response",
            "source_amplitude": visible_response["screen_response_energy"],
            "radius_grid": max(4, int(round(float(request.requested_radius_world) * 90.0))),
            "source_image_xy": xy,
            "source_vector_image": [0.0, 0.0],
            "source_record_ids": source_ids,
            "is_authority_state": False,
        }
        trace = {
            "schema": "interaction_trace_v1",
            "interaction_trace_id": str(audit["interaction_trace_id"]),
            "parent_request_id": str(request.request_id),
            "generated_command_ids": [str(audit["command_id"])],
            "interaction_record_ids": [str(audit["audit_id"])],
            "wave_step_record_ids": [],
            "resulting_projection_frame_ids": [frame.frame_id],
            "source_record_ids": source_ids,
            "is_authority_state": False,
        }
        payload = copy.deepcopy(frame.payload)
        timeline = dict(payload["event_timeline"])
        timeline["interaction_record_ids"] = sorted(set([*timeline.get("interaction_record_ids", []), str(audit["audit_id"])]))
        timeline["source_record_ids"] = sorted(set([*timeline.get("source_record_ids", []), *source_ids]))
        image_plane = copy.deepcopy(payload["spectral_image_plane"])
        image_plane["visible_interaction_response"] = visible_response
        image_plane["projection_response_overlays"] = [overlay]
        image_plane["source_record_ids"] = sorted(set([*image_plane.get("source_record_ids", []), *source_ids]))
        image_plane["projection_frame_digest"] = _refresh_image_plane_digest(image_plane)
        payload["event_timeline"] = timeline
        payload["spectral_image_plane"] = image_plane
        payload["interaction_overlays"] = sorted(
            [*payload.get("interaction_overlays", []), overlay],
            key=lambda item: str(item.get("overlay_id", "")),
        )
        payload["interaction_traces"] = sorted(
            [*payload.get("interaction_traces", []), trace],
            key=lambda item: str(item.get("interaction_trace_id", "")),
        )
        payload["active_interaction_trace_ids"] = sorted(
            set([*payload.get("active_interaction_trace_ids", []), str(audit["interaction_trace_id"])])
        )
        payload["source_record_ids"] = sorted(set([*payload.get("source_record_ids", []), *source_ids]))
        updated = replace(
            frame,
            payload=payload,
            source_record_ids=sorted(set([*frame.source_record_ids, *source_ids])),
        )
        if self.projection_frames and self.projection_frames[-1].frame_id == frame.frame_id:
            self.projection_frames[-1] = updated
        if self.image_planes:
            self.image_planes[-1] = copy.deepcopy(image_plane)
        return updated

    def _solar_earth_surface_point_from_image_xy(self, image_xy: Sequence[float] | None) -> tuple[float, float, float]:
        scene = getattr(self, "solar_earth_scene")
        if image_xy is None:
            return scene.demo_surface_point_world
        if len(image_xy) != 2:
            raise ValueError("solar earth refinement image_xy must have two values")
        u = max(0.0, min(1.0, float(image_xy[0])))
        v = max(0.0, min(1.0, float(image_xy[1])))
        try:
            origin = [float(value) for value in self.camera_pose.get("origin") or self.camera_pose.get("position")]
            look_at = [float(value) for value in self.camera_pose.get("look_at") or scene.planet_center_world]
            up_hint = [float(value) for value in self.camera_pose.get("up") or [0.0, 0.0, 1.0]]
            forward = _normalize_vec3([look_at[index] - origin[index] for index in range(3)])
            right = _normalize_vec3(
                [
                    forward[1] * up_hint[2] - forward[2] * up_hint[1],
                    forward[2] * up_hint[0] - forward[0] * up_hint[2],
                    forward[0] * up_hint[1] - forward[1] * up_hint[0],
                ]
            )
            up = _normalize_vec3(
                [
                    right[1] * forward[2] - right[2] * forward[1],
                    right[2] * forward[0] - right[0] * forward[2],
                    right[0] * forward[1] - right[1] * forward[0],
                ]
            )
            fov = math.radians(float(self.camera_pose.get("fov_degrees", 50.0)))
            aspect = 96.0 / 64.0
            px = (u * 2.0 - 1.0) * math.tan(fov / 2.0) * aspect
            py = -(v * 2.0 - 1.0) * math.tan(fov / 2.0)
            ray = _normalize_vec3(
                [
                    forward[index] + right[index] * px + up[index] * py
                    for index in range(3)
                ]
            )
            oc = [origin[index] - float(scene.planet_center_world[index]) for index in range(3)]
            b = 2.0 * sum(oc[index] * ray[index] for index in range(3))
            c = sum(value * value for value in oc) - scene.planet_radius_world * scene.planet_radius_world
            disc = b * b - 4.0 * c
            if disc >= 0.0:
                t0 = (-b - math.sqrt(disc)) / 2.0
                if t0 > 0.0:
                    return tuple(origin[index] + ray[index] * t0 for index in range(3))  # type: ignore[return-value]
        except Exception:
            pass
        nx = u * 2.0 - 1.0
        ny = v * 2.0 - 1.0
        dx = (nx - 0.40) / 0.34
        dy = (ny - 0.02) / 0.34
        radial_sq = dx * dx + dy * dy
        if radial_sq > 1.0:
            return scene.demo_surface_point_world
        facing = -math.sqrt(max(0.0, 1.0 - radial_sq))
        direction = (facing, dy, dx)
        length = math.sqrt(sum(value * value for value in direction))
        if length <= 1e-12:
            return scene.demo_surface_point_world
        radius = scene.planet_radius_world * 0.98
        return tuple(
            float(scene.planet_center_world[index]) + (direction[index] / length) * radius
            for index in range(3)
        )  # type: ignore[return-value]

    @_session_locked
    def request_solar_earth_refinement(
        self,
        *,
        world_point: Sequence[float] | None = None,
        image_xy: Sequence[float] | None = None,
        observer_id: str = "observer::solar-earth-orbit",
        request_id: str | None = None,
        requested_radius_world: float | None = None,
        source_projection_frame_id: str | None = None,
    ) -> dict[str, Any]:
        if not hasattr(self, "solar_earth_scene"):
            raise ValueError("solar earth refinement requires solar earth session mode")
        if observer_id not in self.observer_ids:
            raise ValueError("undeclared solar earth refinement observer_id")
        journal = self._begin_mutation_journal()
        try:
            if source_projection_frame_id:
                self._require_latest_projection_frame_id(str(source_projection_frame_id))
            scene = getattr(self, "solar_earth_scene")
            point = self._solar_earth_surface_point_from_image_xy(image_xy) if world_point is None else world_point
            radius = 0.08 if requested_radius_world is None else max(0.02, min(0.25, float(requested_radius_world)))
            request_id_override = None
            if request_id:
                request_id_override = str(request_id)
                if not request_id_override.startswith("planet-local-refinement-request::"):
                    request_id_override = f"planet-local-refinement-request::{request_id_override}"
            request = request_planet_local_refinement(
                scene,
                observer_id=observer_id,
                world_point=point,
                trigger_kind="live_surface_refinement",
                requested_radius_world=radius,
                requested_resolution=(12, 12, 12),
                max_refinement_depth=2,
                request_id_override=request_id_override,
            )
            existing_request_ids = {str(item["request_id"]) for item in self.refinement_requests}
            if request.request_id in existing_request_ids:
                raise ValueError("duplicate solar earth refinement request_id")
            patch = refine_planet_local_region(scene, request)
            self.refinement_requests.append(copy.deepcopy(request.__dict__))
            self.refinement_patches.append(copy.deepcopy(patch.__dict__))
            audit = {
                "schema": "solar_earth_interaction_audit_v1",
                "audit_id": f"interaction-audit::solar-earth::{request.request_id.split('::')[-1]}",
                "request_id": request.request_id,
                "command_id": f"cmd::solar-earth-refine::{request.request_id.split('::')[-1]}",
                "interaction_trace_id": f"interaction-trace::solar-earth::{request.request_id.split('::')[-1]}",
                "observer_id": observer_id,
                "tool": "local_surface_refinement",
                "status": "applied",
                "target_world": list(request.world_point),
                "affected_region_ids": list(request.source_layer_shell_ids),
                "source_record_ids": sorted(
                    set(
                        [
                            request.request_id,
                            patch.patch_id,
                            patch.final_patch_digest,
                            *request.source_record_ids,
                            *patch.source_record_ids,
                        ]
                    )
                ),
                "is_authority_state": False,
            }
            self.interaction_audits.append(copy.deepcopy(audit))
            self._audit_index_by_command[str(audit["command_id"])] = len(self.interaction_audits) - 1
            frame = self._append_solar_earth_projection_frame(
                event_kinds=["solar_earth_local_refinement"],
                local_refinement_request_ids=[request.request_id],
                local_refinement_patch_ids=[patch.patch_id],
                extra_source_record_ids=[audit["audit_id"], audit["command_id"]],
            )
            frame = self._attach_solar_earth_visible_interaction_response(
                frame,
                request=request,
                patch=patch,
                audit=audit,
                image_xy=image_xy,
            )
            return {
                "status": "accepted",
                "request": request.__dict__,
                "patch": patch.__dict__,
                "interaction_audit": audit,
                "projection_frame_id": frame.frame_id,
                "projection_frame": frame,
            }
        except Exception:
            self._rollback_mutation_journal(journal)
            raise

    def _build_refinement_for_audit(self, audit: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        basis_id = str(audit["target_basis_ids"][0])
        target = audit.get("target_world_3d") or [0.0, 0.0, 0.0]
        radius = 1.25
        region = {
            "min": [float(target[index]) - radius for index in range(3)],
            "max": [float(target[index]) + radius for index in range(3)],
        }
        request = build_implicit_local_refinement_request(
            request_id=f"implicit-refinement-request::{audit['request_id']}",
            trigger_kind="interaction_uncertainty",
            trigger_record_ids=[str(audit["command_id"])],
            region_world_3d=region,
            requested_grid_shape=[6, 6, 4],
            requested_tick_window=[self.current_tick, self.current_tick + 1],
            source_implicit_field_state_id=self.current_state["implicit_field_state_id"],
            error_metrics_before_refinement={"ray_residual": 0.16, "targeting_confidence": audit.get("targeting_confidence")},
            source_record_ids=[str(audit["command_id"]), str(audit["source_ray_sample_record_id"])],
        )
        patch = build_implicit_local_refinement_patch(
            patch_id=f"implicit-refinement-patch::{audit['request_id']}",
            request_id=request["request_id"],
            field_state_ids=[f"fine-patch-field-state::{audit['request_id']}::initial", f"fine-patch-field-state::{audit['request_id']}::final"],
            patch_coordinate_frame={"grid_shape": [6, 6, 4], "world_bounds": [region["min"], region["max"]]},
            initial_patch_snapshot={"channels": {"density": {"shape": [2, 2, 2], "digest": "sha256:implicit-live-initial"}}},
            final_patch_snapshot={"channels": {"density": {"shape": [2, 2, 2], "digest": "sha256:implicit-live-final"}}},
            initial_patch_digest="sha256:implicit-live-initial",
            final_patch_digest="sha256:implicit-live-final",
            patch_summary={"relative_energy_delta": 0.1, "centroid_delta_world_3d": [0.06, 0.0, 0.0], "boundary_error_delta": -0.02},
            patch_to_implicit_correction={"basis_id": basis_id, "channel": "density", "delta": 0.12, "relative_energy_delta": 0.1},
            source_wave_step_record_ids=[f"implicit-refinement-fine-step::{audit['request_id']}::1"],
            source_record_ids=[request["request_id"], str(audit["command_id"])],
        )
        return request, patch

    def _baseline_for_refinement(
        self,
        *,
        before_state: Mapping[str, Any],
        before_image_plane: Mapping[str, Any],
        after_image_plane: Mapping[str, Any],
        audit: Mapping[str, Any],
    ) -> dict[str, Any]:
        context = {
            "source_package_name": self.source_package_name,
            "seed_salt": "seed::implicit-live-m7",
            "basis_layout_digest": self.current_state["basis_layout_digest"],
            "observer_path_digest": self.observer_path_record["path_digest"],
            "tick_window": [self.current_tick, self.current_tick],
        }
        return build_implicit_baseline_comparison_record(
            comparison_id=f"implicit-baseline-comparison::{audit['request_id']}",
            case_id=f"case::{self.run_id}::implicit_live_refine_probe",
            baseline_case_id=f"case::{self.run_id}::implicit_live_passive",
            source_context=context,
            baseline_context=context,
            source_implicit_field_state_id=self.current_state["implicit_field_state_id"],
            baseline_implicit_field_state_id=str(before_state["implicit_field_state_id"]),
            source_ray_sample_record_ids=[after_image_plane["ray_sample_record_id"]],
            baseline_ray_sample_record_ids=[before_image_plane["ray_sample_record_id"]],
            source_image_plane_ids=[after_image_plane["image_plane_id"]],
            baseline_image_plane_ids=[before_image_plane["image_plane_id"]],
            delta_metrics={
                "image_delta": 0.1,
                "coefficient_delta": 0.12,
                "ray_integral_delta": 0.1,
                "local_refinement_correction_delta": 0.12,
            },
            source_record_ids=[after_image_plane["image_plane_id"], before_image_plane["image_plane_id"], str(audit["command_id"])],
        )

    @_session_locked
    def apply_interaction(self, request: Mapping[str, Any]) -> dict[str, Any]:
        validate_implicit_interaction_request(
            request,
            declared_observer_ids=self.observer_ids,
            existing_request_ids={audit["request_id"] for audit in self.interaction_audits},
        )
        source_frame = self._require_latest_projection_frame_id(str(request["source_projection_frame_id"]))
        if int(request["source_frame_tick"]) != int(source_frame.tick):
            raise ValueError("source_frame_tick does not match latest projection frame")
        source_semantics = source_frame.payload.get("timeline_semantics", {})
        frame_state_id = str(
            source_semantics.get("source_world_state_id")
            or source_frame.payload.get("implicit_field_state_id")
            or ""
        )
        if frame_state_id != str(self.current_state["implicit_field_state_id"]):
            raise ValueError("source projection frame does not cite current state")
        if str(request["source_state_id"]) != frame_state_id:
            raise ValueError("source_state_id does not match latest projection frame")
        frame_ray_id = str(
            source_frame.payload.get("implicit_ray_sample_record", {}).get("ray_sample_record_id", "")
        )
        if str(request["source_ray_sample_record_id"]) != frame_ray_id:
            raise ValueError("source_ray_sample_record_id does not match latest projection frame")
        journal = self._begin_mutation_journal()
        try:
            target = target_basis_from_image_xy(
                request,
                current_state=self.current_state,
                bases=self.bases,
                ray_sample_record=self.ray_sample_records[-1],
                image_plane=self.image_planes[-1],
                observed_structures=[record for record in self.observed_structure_records if int(record.get("state_tick", -1)) == self.current_tick],
            )
            accepted_sequence = self._accepted_sequence + 1
            control_descriptor = None
            if request["tool"] in {"implicit_local_excite", "implicit_local_dampen"}:
                control_descriptor = build_implicit_pending_control_descriptor(
                    request,
                    target=target,
                    bases=self.bases,
                    accepted_sequence=accepted_sequence,
                    start_tick=self.current_tick + 1,
                    kappa_norm_min=KAPPA_NORM_MIN,
                )
                input_projection = materialize_implicit_raw_control_projection(
                    control_descriptor,
                    schedule_index=0,
                )
            else:
                input_projection = implicit_request_to_input_projection(request, target)
            audit = build_implicit_interaction_audit(
                request,
                target=target,
                source_state_id=self.current_state["implicit_field_state_id"],
                input_projection=input_projection,
                control_descriptor=control_descriptor,
            )
            audit["accepted_sequence"] = accepted_sequence
            self.interaction_audits.append(audit)
            self._audit_index_by_command[str(audit["command_id"])] = len(self.interaction_audits) - 1
            self._accepted_sequence = accepted_sequence
            if request["tool"] == "implicit_refine_probe":
                before_state = copy.deepcopy(self.current_state)
                before_image_plane = copy.deepcopy(self.image_planes[-1])
                refinement_request, refinement_patch = self._build_refinement_for_audit(audit)
                corrected = apply_refinement_patch_to_implicit_state(self.current_state, self.bases, refinement_patch)
                self.current_state = self._retag_state(corrected, int(corrected["tick"]))
                self.implicit_field_states.append(copy.deepcopy(self.current_state))
                self.refinement_requests.append(refinement_request)
                self.refinement_patches.append(refinement_patch)
                audit["refinement_request_id"] = refinement_request["request_id"]
                audit["refinement_patch_id"] = refinement_patch["patch_id"]
                step = self._live_step_record(
                    tick=self.current_tick,
                    previous_state_id=before_state["implicit_field_state_id"],
                    previous_state_digest=str(before_state["state_digest"]),
                    result_state_id=self.current_state["implicit_field_state_id"],
                    result_state_digest=str(self.current_state["state_digest"]),
                    input_projection={},
                    applied_command_ids=[audit["command_id"]],
                    refinement_patch_ids=[refinement_patch["patch_id"]],
                    runtime_cost_summary={"basis_count": len(self.bases), "sparse_edge_count": len(self.current_state.get("sparse_coupling_edges", [])), "dense_volume_used": False, "update_cost_units": len(self.bases)},
                )
                self.implicit_live_steps.append(step)
                self._append_five_phase_causal_artifacts(observer_id=DEFAULT_OBSERVER_ID)
                frame = self._append_observation_frame(
                    event_kinds=["implicit_refinement_applied", "implicit_interaction_applied"],
                    live_step_id=step["step_id"],
                    frame_kind=INTERACTION_STEP_OBSERVATION,
                    world_advanced=True,
                    camera_moved=False,
                    world_tick_window=(int(before_state["tick"]), self.current_tick),
                    source_live_step_ids=[step["step_id"]],
                    source_interaction_audit_ids=[audit["audit_id"]],
                    playback_track=WORLD_RUN_TRACK,
                )
                baseline = self._baseline_for_refinement(
                    before_state=before_state,
                    before_image_plane=before_image_plane,
                    after_image_plane=self.image_planes[-1],
                    audit=audit,
                )
                self.baseline_comparisons.append(baseline)
                frame.payload["implicit_baseline_comparison_ids"] = [baseline["comparison_id"]]
                self._complete_audits(command_ids=[audit["command_id"]], result_state_id=self.current_state["implicit_field_state_id"], frame=frame)
                extra_ticks = max(0, int(request.get("advance_ticks", 1)) - 1) if request.get("advance_after_accept") else 0
                if extra_ticks:
                    self.advance(extra_ticks)
                self._record_interaction_transcript(request, audit_id=audit["audit_id"])
                return copy.deepcopy(next(item for item in self.interaction_audits if item["audit_id"] == audit["audit_id"]))
            if len(self._pending_inputs) >= MAX_PENDING_CONTROLS:
                raise ValueError("implicit session exceeds pending control budget")
            if control_descriptor is not None:
                if len(self._active_energy_scopes) >= MAX_ACTIVE_ENERGY_SCOPES:
                    raise ValueError("implicit session exceeds active local energy scope budget")
                scope_id = f"implicit-energy-scope::{audit['command_id']}"
                final_input_tick = self.current_tick + len(control_descriptor["schedule_weights"])
                self._pending_inputs.append(
                    {
                        "kind": "local_control",
                        "apply_tick": self.current_tick + 1,
                        "request_id": audit["request_id"],
                        "command_id": audit["command_id"],
                        "accepted_sequence": accepted_sequence,
                        "next_schedule_index": 0,
                        "scope_id": scope_id,
                        "control_descriptor": copy.deepcopy(control_descriptor),
                    }
                )
                self._active_energy_scopes.append(
                    {
                        "scope_id": scope_id,
                        "request_id": audit["request_id"],
                        "command_id": audit["command_id"],
                        "accepted_sequence": accepted_sequence,
                        "kappa_by_basis": copy.deepcopy(control_descriptor["kappa_by_basis"]),
                        "activation_tick": self.current_tick + 1,
                        "final_input_tick": final_input_tick,
                        "expiry_tick": final_input_tick + ENERGY_SCOPE_RELAXATION_TICKS,
                    }
                )
            else:
                runtime_projection = _declared_runtime_projection(input_projection, self.bases)
                self._pending_inputs.append(
                    {
                        "kind": "fixed_projection",
                        "apply_tick": self.current_tick + 1,
                        "request_id": audit["request_id"],
                        "command_id": audit["command_id"],
                        "accepted_sequence": accepted_sequence,
                        "input_projection": runtime_projection,
                    }
                )
            self._pending_inputs.sort(
                key=lambda item: (
                    int(item["apply_tick"]),
                    int(item.get("accepted_sequence", -1)),
                    str(item.get("request_id", "")),
                )
            )
            if request.get("advance_after_accept"):
                self.advance(int(request.get("advance_ticks", 1)))
            self._record_interaction_transcript(request, audit_id=audit["audit_id"])
            return copy.deepcopy(next(item for item in self.interaction_audits if item["audit_id"] == audit["audit_id"]))
        except Exception:
            self._rollback_mutation_journal(journal)
            raise
