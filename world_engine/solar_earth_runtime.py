from __future__ import annotations

import base64
import copy
import hashlib
import json
import math
from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

from world_engine.contracts import ProjectionFrame
from world_engine.implicit_field import (
    build_basis_spatial_index,
    build_implicit_field_basis,
    build_implicit_field_state,
)
from world_engine.fundamental_field_force import (
    MacroCelestialBodyStateRecord,
    EffectiveGravityPotentialRecord,
    MacroBodyStepRecord,
    advance_macro_bodies,
)
from world_engine.planet_surface_field import (
    PlanetSurfaceSpectralFieldRecord,
    PlanetSurfaceSpectralSampleRecord,
    build_planet_surface_spectral_field,
    sample_planet_surface_readability,
    sample_planet_surface_frequency_pyramid,
    sample_planet_surface_spectral_field,
)
from world_engine.projection_frames import attach_projection_invariant_boundary_records_to_projection_frame
from world_engine.projection_invariant_boundary import (
    build_projection_loss_manifest,
    canonical_digest as m13_canonical_digest,
    compute_invariant_signature,
)
from world_engine.realtime_projection_renderer import (
    REALTIME_LOD_STATE_SCHEMA,
    REALTIME_OBSERVER_CAMERA_STATE_SCHEMA,
    REALTIME_PROJECTION_FRAME_PACKET_SCHEMA,
    REALTIME_RENDERER_THRESHOLDS,
    REALTIME_RENDERABLE_SCHEMA,
    REALTIME_SENSOR_STATE_SCHEMA,
    validate_realtime_projection_frame_packet,
)
from world_engine.solar_earth_spectral_world import (
    PlanetEnergyFluxRecord,
    PlanetLayerShellRecord,
    PlanetLocalRefinementPatch,
    PlanetLocalRefinementRequest,
    PlanetMacroAuthorityRecord,
    SolarEarthTemplateBindingRecord,
    SolarRadiationSourceRecord,
    SpectralBandProfile,
    build_planet_macro_authority_record,
    compose_visible_rgb,
    default_solar_earth_template_binding,
    default_spectral_band_profile,
    demo_earth_like_layer_shells,
    demo_solar_radiation_source,
    find_layers_at_radius,
    sample_solar_radiation_at,
    validate_planet_layer_shells,
    validate_planet_macro_authority,
    validate_solar_earth_template_binding,
    validate_spectral_band_profile,
)


ALLOWED_SOLAR_EARTH_SENSOR_BAND_MODES = frozenset(
    {"visible_surface", "near_ir_penetrating", "thermal_internal"}
)

ALLOWED_SOLAR_EARTH_CAMERA_ACTIONS = frozenset(
    {
        "forward",
        "back",
        "strafe_left",
        "strafe_right",
        "up",
        "down",
        "orbit_left",
        "orbit_right",
        "yaw_left",
        "yaw_right",
        "pitch_up",
        "pitch_down",
        "zoom_in",
        "zoom_out",
        "reset",
    }
)


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _distance(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt(sum((float(a[index]) - float(b[index])) ** 2 for index in range(3)))


def _vec_sub(a: Sequence[float], b: Sequence[float]) -> list[float]:
    return [float(a[index]) - float(b[index]) for index in range(3)]


def _vec_add(a: Sequence[float], b: Sequence[float]) -> list[float]:
    return [float(a[index]) + float(b[index]) for index in range(3)]


def _vec_scale(v: Sequence[float], value: float) -> list[float]:
    return [float(item) * float(value) for item in v]


def _vec_dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(float(a[index]) * float(b[index]) for index in range(3))


def _vec_cross(a: Sequence[float], b: Sequence[float]) -> list[float]:
    return [
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    ]


def _vec_norm(v: Sequence[float]) -> list[float]:
    length = math.sqrt(_vec_dot(v, v))
    if length <= 1e-12:
        raise ValueError("cannot normalize zero vector")
    return [float(value) / length for value in v]


def _rotate_vector_around_axis(vector: Sequence[float], axis: Sequence[float], degrees: float) -> list[float]:
    angle = math.radians(float(degrees))
    unit_axis = _vec_norm(axis)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    cross = _vec_cross(unit_axis, vector)
    dot = _vec_dot(unit_axis, vector)
    return [
        float(vector[index]) * cos_a + cross[index] * sin_a + unit_axis[index] * dot * (1.0 - cos_a)
        for index in range(3)
    ]


def _finite_vec3(values: Sequence[Any], *, name: str) -> tuple[float, float, float]:
    if len(values) != 3:
        raise ValueError(f"{name} must have length 3")
    parsed = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in parsed):
        raise ValueError(f"{name} must be finite")
    return parsed


def _dataclass_tuple_to_dicts(values: Sequence[Any]) -> list[dict[str, Any]]:
    return [_dataclass_to_dict(value) for value in values]


def _record_id_digest(prefix: str, payload: Mapping[str, Any]) -> str:
    return f"{prefix}::{_canonical_digest(payload).split(':', 1)[1][:16]}"


def _record_get(record: Any, key: str, default: Any = None) -> Any:
    if isinstance(record, Mapping):
        return record.get(key, default)
    return getattr(record, key, default)


def _dataclass_to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return copy.deepcopy(value.__dict__)


def _smoothstep(edge0: float, edge1: float, value: float) -> float:
    if abs(edge1 - edge0) <= 1e-12:
        return 1.0 if value >= edge1 else 0.0
    t = max(0.0, min(1.0, (float(value) - float(edge0)) / (float(edge1) - float(edge0))))
    return t * t * (3.0 - 2.0 * t)


def _observer_motion_vector(
    origin: Sequence[float],
    look_at: Sequence[float],
    up: Sequence[float],
    action: str,
    step_world: float,
) -> tuple[float, float, float]:
    if action in {"", "none"} or step_world <= 0.0:
        return (0.0, 0.0, 0.0)
    forward = _vec_norm(_vec_sub(look_at, origin))
    up_unit = _vec_norm(up)
    right = _vec_cross(forward, up_unit)
    if _vec_dot(right, right) <= 1e-10:
        right = [1.0, 0.0, 0.0]
    right = _vec_norm(right)
    if action == "forward":
        vector = _vec_scale(forward, step_world)
    elif action == "back":
        vector = _vec_scale(forward, -step_world)
    elif action == "strafe_left":
        vector = _vec_scale(right, -step_world)
    elif action == "strafe_right":
        vector = _vec_scale(right, step_world)
    else:
        vector = (0.0, 0.0, 0.0)
    return tuple(round(float(value), 9) for value in vector)  # type: ignore[return-value]


def _macro_error_bound_world(scene: SolarEarthSceneState) -> float:
    envelope = getattr(scene.planet_macro_authority, "validity_envelope", {}) or {}
    for key in ("max_boundary_error_world", "boundary_error_world", "surface_error_bound_world"):
        value = envelope.get(key)
        if value is not None:
            parsed = float(value)
            if math.isfinite(parsed) and parsed > 0.0:
                return parsed
    return scene.planet_radius_world * 0.035


def _solar_source_for_star_body(
    solar_source: SolarRadiationSourceRecord,
    star_body_state: MacroCelestialBodyStateRecord,
    *,
    tick: int,
) -> SolarRadiationSourceRecord:
    payload = {
        "previous_solar_source_id": solar_source.record_id,
        "star_body_state_id": star_body_state.record_id,
        "center_world": list(star_body_state.center_world),
        "tick": int(tick),
    }
    return replace(
        solar_source,
        record_id=_record_id_digest("solar-radiation-source", payload),
        center_world=star_body_state.center_world,
        source_record_ids=tuple(dict.fromkeys([solar_source.record_id, star_body_state.record_id, *solar_source.source_record_ids])),
    )


@dataclass(frozen=True)
class SolarEarthImplicitState:
    state: dict[str, Any]
    bases: tuple[dict[str, Any], ...]
    basis_spatial_index: dict[str, Any]


@dataclass(frozen=True)
class SolarEarthSceneState:
    template_binding: SolarEarthTemplateBindingRecord
    spectral_profile: SpectralBandProfile
    solar_source: SolarRadiationSourceRecord
    layer_shells: tuple[PlanetLayerShellRecord, ...]
    planet_macro_authority: PlanetMacroAuthorityRecord
    implicit_state: SolarEarthImplicitState
    payload: dict[str, Any]
    source_record_ids: tuple[str, ...]
    planet_center_world: tuple[float, float, float]
    planet_radius_world: float
    tick: int
    energy_flux_records: tuple[PlanetEnergyFluxRecord, ...]
    demo_surface_point_world: tuple[float, float, float]
    macro_body_states: tuple[MacroCelestialBodyStateRecord, ...] = ()
    star_body_state: MacroCelestialBodyStateRecord | None = None
    planet_body_state: MacroCelestialBodyStateRecord | None = None
    gravity_potential_records: tuple[EffectiveGravityPotentialRecord, ...] = ()
    macro_body_step_records: tuple[MacroBodyStepRecord, ...] = ()
    surface_field: PlanetSurfaceSpectralFieldRecord | None = None
    surface_fields: tuple[PlanetSurfaceSpectralFieldRecord, ...] = ()
    solar_sources: tuple[SolarRadiationSourceRecord, ...] = ()


@dataclass(frozen=True)
class EnergyFluxBudgetResult:
    status: str
    per_window_relative_energy_error: float
    record_count: int


@dataclass(frozen=True)
class ObserverStateRecord:
    record_id: str
    schema: str
    observer_id: str
    tick: int
    origin_world: tuple[float, float, float]
    look_at_world: tuple[float, float, float]
    forward_world: tuple[float, float, float]
    up_world: tuple[float, float, float]
    fov_degrees: float
    sensor_band_mode: str
    intended_motion_world: tuple[float, float, float]
    source_record_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "schema": self.schema,
            "observer_id": self.observer_id,
            "tick": self.tick,
            "origin_world": list(self.origin_world),
            "look_at_world": list(self.look_at_world),
            "forward_world": list(self.forward_world),
            "up_world": list(self.up_world),
            "fov_degrees": self.fov_degrees,
            "sensor_band_mode": self.sensor_band_mode,
            "intended_motion_world": list(self.intended_motion_world),
            "source_record_ids": list(self.source_record_ids),
            "is_authority_state": False,
        }


@dataclass(frozen=True)
class SensorMaterialQueryRecord:
    record_id: str
    schema: str
    observer_state_id: str
    sensor_band_mode: str
    observation_allowed: bool
    traversal_allowed: bool
    penetration_depth_world: float
    material_layer_ids: tuple[str, ...]
    source_record_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "schema": self.schema,
            "observer_state_id": self.observer_state_id,
            "sensor_band_mode": self.sensor_band_mode,
            "observation_allowed": self.observation_allowed,
            "traversal_allowed": self.traversal_allowed,
            "penetration_depth_world": self.penetration_depth_world,
            "material_layer_ids": list(self.material_layer_ids),
            "source_record_ids": list(self.source_record_ids),
            "is_authority_state": False,
        }


@dataclass(frozen=True)
class PlanetVolumeRayObservationRecord:
    record_id: str
    schema: str
    observer_state_id: str
    sensor_band_mode: str
    ray_origin_world: tuple[float, float, float]
    ray_direction_world: tuple[float, float, float]
    sample_depth_world: float
    traversed_layer_ids: tuple[str, ...]
    dominant_layer_id: str | None
    attenuation: float
    emission_response: float
    occlusion_status: str
    source_record_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "schema": self.schema,
            "observer_state_id": self.observer_state_id,
            "sensor_band_mode": self.sensor_band_mode,
            "ray_origin_world": list(self.ray_origin_world),
            "ray_direction_world": list(self.ray_direction_world),
            "sample_depth_world": self.sample_depth_world,
            "traversed_layer_ids": list(self.traversed_layer_ids),
            "dominant_layer_id": self.dominant_layer_id,
            "attenuation": self.attenuation,
            "emission_response": self.emission_response,
            "occlusion_status": self.occlusion_status,
            "source_record_ids": list(self.source_record_ids),
            "is_authority_state": False,
        }


@dataclass(frozen=True)
class RefinementDemandRecord:
    record_id: str
    schema: str
    observer_state_id: str
    refinement_weight: float
    prewarm_weight: float
    projected_footprint_world: float
    macro_error_bound_world: float
    boundary_distance_world: float
    required_patch_radius_world: float
    required_resolution: tuple[int, int, int]
    reason_codes: tuple[str, ...]
    source_record_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "schema": self.schema,
            "observer_state_id": self.observer_state_id,
            "refinement_weight": self.refinement_weight,
            "prewarm_weight": self.prewarm_weight,
            "projected_footprint_world": self.projected_footprint_world,
            "macro_error_bound_world": self.macro_error_bound_world,
            "boundary_distance_world": self.boundary_distance_world,
            "required_patch_radius_world": self.required_patch_radius_world,
            "required_resolution": list(self.required_resolution),
            "reason_codes": list(self.reason_codes),
            "source_record_ids": list(self.source_record_ids),
            "is_authority_state": False,
        }


@dataclass(frozen=True)
class VolumeRefinementDemandRecord:
    record_id: str
    schema: str
    observer_state_id: str
    volume_ray_observation_id: str
    refinement_weight: float
    target_depth_world: float
    required_volume_radius_world: float
    required_resolution: tuple[int, int, int]
    reason_codes: tuple[str, ...]
    source_record_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "schema": self.schema,
            "observer_state_id": self.observer_state_id,
            "volume_ray_observation_id": self.volume_ray_observation_id,
            "refinement_weight": self.refinement_weight,
            "target_depth_world": self.target_depth_world,
            "required_volume_radius_world": self.required_volume_radius_world,
            "required_resolution": list(self.required_resolution),
            "reason_codes": list(self.reason_codes),
            "source_record_ids": list(self.source_record_ids),
            "is_authority_state": False,
        }


def _support_for(center: Sequence[float], radius: float) -> dict[str, list[float]]:
    return {
        "min": [float(center[index]) - float(radius) for index in range(3)],
        "max": [float(center[index]) + float(radius) for index in range(3)],
    }


def _build_solar_earth_bases(
    binding: SolarEarthTemplateBindingRecord,
    profile: SpectralBandProfile,
    solar_source: SolarRadiationSourceRecord,
    layer_shells: Sequence[PlanetLayerShellRecord],
    planet_center: tuple[float, float, float],
) -> list[dict[str, Any]]:
    coordinate_frame = {"units": "world", "handedness": "right", "axes": ["x", "y", "z"]}
    axes = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    bands = [band.band_id for band in profile.bands]
    solar_weights = {band_id: solar_source.spectral_power_by_band.get(band_id, 0.0) for band_id in bands}
    bases = [
        build_implicit_field_basis(
            basis_id="implicit-basis::solar-radial-emitter",
            basis_kind="radial_emitter",
            coordinate_frame_3d=coordinate_frame,
            source_signature_template_id=binding.star_template_id,
            source_signature_instance_id=f"{binding.record_id}::star",
            center_world_3d=solar_source.center_world,
            basis_axes=axes,
            radius_world=18.0,
            basis_profile="radial_inverse_square",
            basis_profile_params={"clamp_radius_world": solar_source.radius_world},
            frequency_vector=[0.0, 0.0, 0.0],
            omega=0.0,
            phase=0.0,
            channel_weights=solar_weights,
            support_region_world=_support_for(solar_source.center_world, 18.0),
            source_record_ids=[solar_source.record_id, binding.record_id],
        )
    ]
    for layer in layer_shells:
        radius = max(layer.outer_radius_world * 1.2, layer.outer_radius_world + 0.02)
        bases.append(
            build_implicit_field_basis(
                basis_id=f"implicit-basis::earth-like-layer::{layer.layer_kind}",
                basis_kind="spherical_shell",
                coordinate_frame_3d=coordinate_frame,
                source_signature_template_id=binding.planet_template_id,
                source_signature_instance_id=f"{binding.record_id}::planet::{layer.layer_kind}",
                center_world_3d=planet_center,
                basis_axes=axes,
                radius_world=radius,
                basis_profile="spherical_shell_band",
                basis_profile_params={
                    "inner_radius_world": layer.inner_radius_world,
                    "outer_radius_world": layer.outer_radius_world,
                    "edge_width_world": max(0.01, (layer.outer_radius_world - layer.inner_radius_world) * 0.22),
                },
                frequency_vector=[0.08, 0.03, 0.01],
                omega=0.02,
                phase=0.0,
                channel_weights={
                    **{f"absorb::{band_id}": layer.absorption_by_band.get(band_id, 0.0) for band_id in bands},
                    **{f"scatter::{band_id}": layer.scattering_by_band.get(band_id, 0.0) for band_id in bands},
                    "density": layer.thermal_response,
                },
                support_region_world=_support_for(planet_center, radius),
                source_record_ids=[layer.record_id, binding.record_id],
            )
        )
    return bases


def build_solar_earth_scene_from_template_binding(
    binding: SolarEarthTemplateBindingRecord,
    *,
    tick: int = 0,
) -> SolarEarthSceneState:
    validate_solar_earth_template_binding(binding)
    profile = default_spectral_band_profile()
    validate_spectral_band_profile(profile)
    if binding.spectral_profile_id != profile.profile_id:
        raise ValueError("template binding spectral profile does not match stage-one profile")
    solar_source = demo_solar_radiation_source(profile)
    layer_shells = demo_earth_like_layer_shells(profile)
    validate_planet_layer_shells(layer_shells, profile)
    planet_center = (12.0, 0.0, 0.0)
    planet_radius = layer_shells[-1].outer_radius_world
    bases = _build_solar_earth_bases(binding, profile, solar_source, layer_shells, planet_center)
    index = build_basis_spatial_index(bases)
    basis_ids = [basis["basis_id"] for basis in bases]
    basis_layout_digest = _canonical_digest({"basis_ids": basis_ids, "basis_spatial_index_digest": index["basis_spatial_index_digest"]})
    state = build_implicit_field_state(
        implicit_field_state_id=f"implicit-field-state::solar-earth::{binding.source_package_name}::{tick}",
        tick=int(tick),
        basis_ids=basis_ids,
        basis_layout_digest=basis_layout_digest,
        basis_spatial_index_digest=index["basis_spatial_index_digest"],
        basis_coefficients={basis_id: {"*": 1.0} for basis_id in basis_ids},
        sparse_coupling_edges=[
            {
                "from_basis_id": "implicit-basis::solar-radial-emitter",
                "to_basis_id": "implicit-basis::earth-like-layer::atmosphere",
                "coupling_kind": "radiation_to_scattering_shell",
                "strength": 0.32,
            }
        ],
        background_model={"kind": "sparse_implicit_background", "dense_volume_used": False},
        active_local_patch_ids=[],
        validity_region_world={"min": [-3.0, -4.0, -4.0], "max": [15.0, 4.0, 4.0]},
        energy_summary={"solar_luminosity_scale": solar_source.luminosity_scale, "planet_radius_world": planet_radius},
        source_record_ids=[binding.record_id, solar_source.record_id, *[layer.record_id for layer in layer_shells]],
        authority_status="candidate",
        runtime_cost_summary={"dense_volume_used": False, "basis_count": len(bases), "mode": "sparse_implicit_solar_earth"},
    )
    macro = build_planet_macro_authority_record(
        planet_id="planet::earth-like",
        macro_state_id=f"macro-field-state::earth-like::{binding.source_package_name}::{tick}",
        macro_certificate_id=f"macro-certificate::earth-like::{binding.source_package_name}::{tick}",
        center_world=planet_center,
        radius_world=planet_radius,
        layer_shells=layer_shells,
        source_field_state_ids=(state["implicit_field_state_id"],),
    )
    star_body = MacroCelestialBodyStateRecord(
        record_id=f"macro-body::effective-sun::{binding.source_package_name}::{tick}",
        schema="macro_celestial_body_state_v1",
        tick=int(tick),
        body_id="body::effective-sun",
        body_kind="radiant_star",
        center_world=solar_source.center_world,
        velocity_world_per_tick=(0.0, 0.0, 0.0),
        effective_mass_energy=1000.0,
        radius_world=solar_source.radius_world,
        source_macro_authority_ids=(solar_source.record_id,),
        source_record_ids=(solar_source.record_id, binding.record_id),
    )
    planet_body = MacroCelestialBodyStateRecord(
        record_id=f"macro-body::earth-like::{binding.source_package_name}::{tick}",
        schema="macro_celestial_body_state_v1",
        tick=int(tick),
        body_id="body::earth-like",
        body_kind="layered_planet",
        center_world=planet_center,
        velocity_world_per_tick=(0.0, 0.22, 0.0),
        effective_mass_energy=12.0,
        radius_world=planet_radius,
        source_macro_authority_ids=(macro.record_id,),
        source_record_ids=(macro.record_id, binding.record_id),
    )
    surface_field = build_planet_surface_spectral_field(
        planet_id="planet::earth-like",
        tick=int(tick),
        parameter_seed=binding.seed_salt,
        layer_shells=layer_shells,
        source_macro_authority_ids=(macro.record_id,),
    )
    implicit = SolarEarthImplicitState(state=state, bases=tuple(bases), basis_spatial_index=index)
    source_record_ids = tuple(
        dict.fromkeys(
            [
                binding.record_id,
                solar_source.record_id,
                macro.record_id,
                star_body.record_id,
                planet_body.record_id,
                surface_field.record_id,
                *[layer.record_id for layer in layer_shells],
                state["implicit_field_state_id"],
            ]
        )
    )
    return SolarEarthSceneState(
        template_binding=binding,
        spectral_profile=profile,
        solar_source=solar_source,
        layer_shells=tuple(layer_shells),
        planet_macro_authority=macro,
        implicit_state=implicit,
        payload={
            "schema": "solar_earth_scene_state_v1",
            "dense_volume_allocated": False,
            "template_binding_parameter_digest": binding.parameter_digest,
            "layer_shells": _dataclass_tuple_to_dicts(layer_shells),
        },
        source_record_ids=source_record_ids,
        planet_center_world=planet_center,
        planet_radius_world=planet_radius,
        tick=int(tick),
        energy_flux_records=(),
        demo_surface_point_world=(planet_center[0] - 0.98, planet_center[1], planet_center[2]),
        macro_body_states=(star_body, planet_body),
        star_body_state=star_body,
        planet_body_state=planet_body,
        gravity_potential_records=(),
        macro_body_step_records=(),
        surface_field=surface_field,
        surface_fields=(surface_field,),
        solar_sources=(solar_source,),
    )


def build_demo_solar_earth_scene(*, tick: int = 0) -> SolarEarthSceneState:
    return build_solar_earth_scene_from_template_binding(default_solar_earth_template_binding(), tick=tick)


def build_demo_solar_earth_scene_for_source_package(
    *,
    source_package_name: str,
    tick: int = 0,
) -> SolarEarthSceneState:
    return build_solar_earth_scene_from_template_binding(
        default_solar_earth_template_binding(source_package_name=source_package_name),
        tick=tick,
    )


def _flux_records_for_tick(scene: SolarEarthSceneState, tick: int) -> tuple[PlanetEnergyFluxRecord, ...]:
    sample = sample_solar_radiation_at(scene.solar_source, scene.planet_center_world, scene.spectral_profile)
    input_energy = sum(sample.energy_by_band.values()) * math.pi * scene.planet_radius_world * scene.planet_radius_world
    scatter = input_energy * 0.18
    surface = input_energy * 0.62
    retained = input_energy * 0.17
    records = (
        PlanetEnergyFluxRecord(
            record_id=f"planet-energy-flux::{scene.template_binding.source_package_name}::{tick}::stellar_absorption",
            schema="planet_energy_flux_record_v1",
            tick=int(tick),
            flux_kind="stellar_absorption",
            input_energy_total=input_energy,
            output_energy_total=scatter + surface + retained,
            relative_budget_error=abs(input_energy - (scatter + surface + retained)) / max(1e-9, input_energy),
            source_record_ids=(scene.solar_source.record_id, scene.planet_macro_authority.record_id),
        ),
        PlanetEnergyFluxRecord(
            record_id=f"planet-energy-flux::{scene.template_binding.source_package_name}::{tick}::atmospheric_scattering",
            schema="planet_energy_flux_record_v1",
            tick=int(tick),
            flux_kind="atmospheric_scattering",
            input_energy_total=scatter,
            output_energy_total=scatter * 0.96,
            relative_budget_error=0.04,
            source_record_ids=(scene.solar_source.record_id, "planet-layer-shell::earth-like::atmosphere"),
        ),
        PlanetEnergyFluxRecord(
            record_id=f"planet-energy-flux::{scene.template_binding.source_package_name}::{tick}::surface_absorption",
            schema="planet_energy_flux_record_v1",
            tick=int(tick),
            flux_kind="surface_absorption",
            input_energy_total=surface,
            output_energy_total=surface * 0.94,
            relative_budget_error=0.06,
            source_record_ids=(scene.solar_source.record_id, "planet-layer-shell::earth-like::crust", "planet-layer-shell::earth-like::ocean"),
        ),
    )
    return records


def advance_solar_earth_scene(scene: SolarEarthSceneState, *, ticks: int = 1) -> SolarEarthSceneState:
    if int(ticks) < 1:
        raise ValueError("solar earth advance ticks must be positive")
    current = scene
    records = list(scene.energy_flux_records)
    gravity_records = list(scene.gravity_potential_records)
    body_step_records = list(scene.macro_body_step_records)
    surface_fields = list(scene.surface_fields)
    solar_sources = list(scene.solar_sources)
    if scene.solar_source not in solar_sources:
        solar_sources.append(scene.solar_source)
    if scene.surface_field and scene.surface_field not in surface_fields:
        surface_fields.append(scene.surface_field)
    for _ in range(int(ticks)):
        next_tick = current.tick + 1
        macro_bodies = current.macro_body_states
        if not macro_bodies and current.star_body_state and current.planet_body_state:
            macro_bodies = (current.star_body_state, current.planet_body_state)
        next_bodies, potential, body_step = advance_macro_bodies(macro_bodies, tick=next_tick)
        by_id = {body.body_id: body for body in next_bodies}
        star_body = by_id.get("body::effective-sun") or next_bodies[0]
        planet_body = by_id.get("body::earth-like") or next_bodies[-1]
        current_solar_source = _solar_source_for_star_body(current.solar_source, star_body, tick=next_tick)
        solar_sources.append(current_solar_source)
        current_for_flux = replace(
            current,
            solar_source=current_solar_source,
            planet_center_world=planet_body.center_world,
            macro_body_states=next_bodies,
            star_body_state=star_body,
            planet_body_state=planet_body,
        )
        records.extend(_flux_records_for_tick(current_for_flux, next_tick))
        gravity_records.append(potential)
        body_step_records.append(body_step)
        current_state = copy.deepcopy(current.implicit_state.state)
        current_state["tick"] = next_tick
        current_state["implicit_field_state_id"] = f"implicit-field-state::solar-earth::{current.template_binding.source_package_name}::{next_tick}"
        current_state["state_digest"] = _canonical_digest({key: value for key, value in current_state.items() if key != "state_digest"})
        implicit = SolarEarthImplicitState(
            state=current_state,
            bases=current.implicit_state.bases,
            basis_spatial_index=current.implicit_state.basis_spatial_index,
        )
        surface_field = build_planet_surface_spectral_field(
            planet_id="planet::earth-like",
            tick=next_tick,
            parameter_seed=current.template_binding.seed_salt,
            layer_shells=current.layer_shells,
            source_macro_authority_ids=(current.planet_macro_authority.record_id, planet_body.record_id),
        )
        surface_fields.append(surface_field)
        source_record_ids = tuple(
            dict.fromkeys(
                [
                    *current.source_record_ids,
                    current_solar_source.record_id,
                    star_body.record_id,
                    planet_body.record_id,
                    potential.record_id,
                    body_step.record_id,
                    surface_field.record_id,
                    current_state["implicit_field_state_id"],
                ]
            )
        )
        deduped_solar_sources: list[SolarRadiationSourceRecord] = []
        seen_solar_source_ids: set[str] = set()
        for source in solar_sources:
            if source.record_id in seen_solar_source_ids:
                continue
            seen_solar_source_ids.add(source.record_id)
            deduped_solar_sources.append(source)
        current = replace(
            current,
            tick=next_tick,
            implicit_state=implicit,
            solar_source=current_solar_source,
            planet_center_world=planet_body.center_world,
            energy_flux_records=tuple(records),
            macro_body_states=next_bodies,
            star_body_state=star_body,
            planet_body_state=planet_body,
            gravity_potential_records=tuple(gravity_records),
            macro_body_step_records=tuple(body_step_records),
            surface_field=surface_field,
            surface_fields=tuple(surface_fields),
            solar_sources=tuple(deduped_solar_sources),
            source_record_ids=source_record_ids,
            demo_surface_point_world=(planet_body.center_world[0] - 0.98, planet_body.center_world[1], planet_body.center_world[2]),
        )
    return current


def evaluate_energy_flux_budget(records: Sequence[PlanetEnergyFluxRecord]) -> EnergyFluxBudgetResult:
    if not records:
        return EnergyFluxBudgetResult(status="failed", per_window_relative_energy_error=1.0, record_count=0)
    total_input = sum(max(0.0, record.input_energy_total) for record in records)
    total_error = sum(abs(record.input_energy_total - record.output_energy_total) for record in records)
    relative = total_error / max(1e-9, total_input)
    lineage_ok = all(record.source_record_ids for record in records)
    per_record_ok = all(record.relative_budget_error <= 0.20 for record in records)
    return EnergyFluxBudgetResult(
        status="passed" if relative <= 0.12 and lineage_ok and per_record_ok else "failed",
        per_window_relative_energy_error=relative,
        record_count=len(records),
    )


def _encode_rle_rgba(raw: bytes) -> str:
    packed = bytearray()
    index = 0
    while index < len(raw):
        pixel = raw[index : index + 4]
        run = 1
        while index + run * 4 < len(raw) and run < 255 and raw[index + run * 4 : index + run * 4 + 4] == pixel:
            run += 1
        packed.extend([run, *pixel])
        index += run * 4
    return "base64:" + base64.b64encode(bytes(packed)).decode("ascii")


def _unique_record_ids(values: Sequence[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in {None, ""}:
            continue
        record_id = str(value)
        if record_id not in seen:
            seen.add(record_id)
            result.append(record_id)
    return result


def _optional_image_shape(value: Any) -> tuple[int, int] | None:
    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 2:
        raise ValueError("image shape override must be a two-item sequence")
    width = int(value[0])
    height = int(value[1])
    if width < 16 or height < 16:
        raise ValueError("image shape override must be at least 16x16")
    return width, height


def _uv_from_unit_normal(normal: Sequence[float]) -> tuple[float, float]:
    unit = _vec_norm(normal)
    longitude = math.atan2(unit[1], unit[0])
    u = (longitude / math.tau) % 1.0
    v = (math.asin(max(-1.0, min(1.0, unit[2]))) / math.pi) + 0.5
    return u, v


def _body_spectral_profile_payload(scene: SolarEarthSceneState) -> dict[str, Any]:
    payload = {
        "body_id": scene.planet_macro_authority.planet_id,
        "body_kind": "layered_spherical_macro_body",
        "radius_world": round(scene.planet_radius_world, 6),
        "surface_field_record_id": scene.surface_field.record_id if scene.surface_field else "",
        "layer_profile_record_id": f"planet-layer-profile::{scene.planet_macro_authority.planet_id}",
        "supported_sensor_bands": sorted(ALLOWED_SOLAR_EARTH_SENSOR_BAND_MODES),
        "source_record_ids": _unique_record_ids(
            [
                scene.planet_macro_authority.record_id,
                scene.surface_field.record_id if scene.surface_field else "",
                *[layer.record_id for layer in scene.layer_shells],
            ]
        ),
    }
    return {
        "schema": "body_spectral_profile_v1",
        "body_profile_id": _record_id_digest("body-spectral-profile", payload),
        **payload,
        "is_authority_state": False,
    }


def _camera_ray_bundle_payload(
    scene: SolarEarthSceneState,
    *,
    observer_id: str,
    camera_pose_id: str,
    camera_pose: Mapping[str, Any],
    image_shape: tuple[int, int],
    frame_kind: str,
) -> dict[str, Any]:
    origin, forward, _right, up, fov_degrees = _camera_basis(camera_pose)
    sensor_band_mode = str(camera_pose.get("sensor_band_mode") or "visible_surface")
    payload = {
        "observer_id": observer_id,
        "frame_kind": frame_kind,
        "world_tick": int(scene.tick),
        "camera_step": int(camera_pose.get("camera_step", scene.tick)),
        "camera_steps_per_world_tick": int(camera_pose.get("camera_steps_per_world_tick", 1)),
        "origin_world": [round(value, 6) for value in origin],
        "forward_world": [round(value, 6) for value in forward],
        "up_world": [round(value, 6) for value in up],
        "fov_y_degrees": round(float(fov_degrees), 6),
        "sensor_band": sensor_band_mode,
        "sample_grid_shape": [int(image_shape[0]), int(image_shape[1])],
        "source_record_ids": _unique_record_ids(
            [
                camera_pose_id,
                scene.implicit_state.state["implicit_field_state_id"],
                scene.planet_macro_authority.record_id,
            ]
        ),
    }
    return {
        "schema": "camera_ray_bundle_v1",
        "ray_bundle_id": _record_id_digest("camera-ray-bundle", payload),
        **payload,
        "is_authority_state": False,
    }


def _spectral_sensor_state_payload(
    scene: SolarEarthSceneState,
    *,
    observer_id: str,
    camera_pose_id: str,
    camera_pose: Mapping[str, Any],
) -> dict[str, Any]:
    origin, forward, right, up, fov_degrees = _camera_basis(camera_pose)
    sensor_band_mode = str(camera_pose.get("sensor_band_mode") or "visible_surface")
    if sensor_band_mode not in ALLOWED_SOLAR_EARTH_SENSOR_BAND_MODES:
        raise ValueError("unsupported solar earth sensor_band_mode")
    payload = {
        "schema": "spectral_sensor_state_v1",
        "observer_id": observer_id,
        "tick": int(scene.tick),
        "camera_pose_id": camera_pose_id,
        "origin_world": [round(value, 6) for value in origin],
        "forward_world": [round(value, 6) for value in forward],
        "right_world": [round(value, 6) for value in right],
        "up_world": [round(value, 6) for value in up],
        "fov_degrees": round(float(fov_degrees), 6),
        "sensor_band_mode": sensor_band_mode,
        "source_record_ids": _unique_record_ids(
            [
                camera_pose_id,
                scene.planet_macro_authority.record_id,
                scene.solar_source.record_id,
                scene.spectral_profile.profile_id,
            ]
        ),
    }
    return {
        **payload,
        "sensor_state_id": _record_id_digest("spectral-sensor-state", payload),
        "is_authority_state": False,
    }


def _sensor_ray_observation_payload(
    scene: SolarEarthSceneState,
    *,
    sensor_state: Mapping[str, Any],
    ray_bundle: Mapping[str, Any],
    image_shape: tuple[int, int],
    volume_observation: PlanetVolumeRayObservationRecord,
    volume_demand: VolumeRefinementDemandRecord,
) -> dict[str, Any]:
    sensor_band_mode = str(sensor_state.get("sensor_band_mode") or ray_bundle.get("sensor_band") or "visible_surface")
    if sensor_band_mode not in ALLOWED_SOLAR_EARTH_SENSOR_BAND_MODES:
        raise ValueError("unsupported solar earth sensor_band_mode")
    payload = {
        "schema": "sensor_ray_observation_v1",
        "sensor_state_id": str(sensor_state["sensor_state_id"]),
        "ray_bundle_id": str(ray_bundle["ray_bundle_id"]),
        "observer_id": str(sensor_state["observer_id"]),
        "tick": int(scene.tick),
        "sensor_band_mode": sensor_band_mode,
        "image_shape": [int(image_shape[0]), int(image_shape[1])],
        "sample_grid_shape": list(ray_bundle.get("sample_grid_shape", [int(image_shape[0]), int(image_shape[1])])),
        "max_penetration_depth_world": round(_penetration_depth_for_sensor_band(scene, sensor_band_mode), 6),
        "sample_depth_world": round(float(volume_observation.sample_depth_world), 6),
        "attenuation": round(float(volume_observation.attenuation), 6),
        "emission_response": round(float(volume_observation.emission_response), 6),
        "dominant_layer_id": str(volume_observation.dominant_layer_id),
        "traversed_layer_ids": list(volume_observation.traversed_layer_ids),
        "radiance_sample_ids": _unique_record_ids(
            [
                volume_observation.record_id,
                volume_demand.record_id,
                *volume_observation.source_record_ids,
                *volume_demand.source_record_ids,
            ]
        ),
        "ray_authority": "observer_sensor_ray_readback",
        "source_record_ids": _unique_record_ids(
            [
                str(sensor_state["sensor_state_id"]),
                str(ray_bundle["ray_bundle_id"]),
                volume_observation.record_id,
                volume_demand.record_id,
                *volume_observation.source_record_ids,
                *volume_demand.source_record_ids,
            ]
        ),
    }
    return {
        **payload,
        "is_authority_state": False,
    }


def _camera_scale_state_payload(
    scene: SolarEarthSceneState,
    *,
    camera_pose: Mapping[str, Any],
    camera_pose_id: str,
    ray_bundle: Mapping[str, Any],
    apparent_planet_radius: float,
    surface_lod_blend: float,
    frame_kind: str,
    volume_demand: VolumeRefinementDemandRecord,
    volume_observation: PlanetVolumeRayObservationRecord,
) -> dict[str, Any]:
    origin = _finite_vec3(camera_pose.get("origin") or camera_pose.get("position") or [0.0, -18.0, 5.0], name="camera_pose.origin")
    distance_to_target = _distance(origin, scene.planet_center_world)
    fov = float(camera_pose.get("fov_degrees", 50.0))
    footprint = max(
        1e-6,
        2.0 * max(distance_to_target, scene.planet_radius_world) * math.tan(math.radians(fov) / 2.0) / 64.0,
    )
    sensor_band = str(ray_bundle["sensor_band"])
    if sensor_band != "visible_surface" and distance_to_target < scene.planet_radius_world:
        scale_level = "subsurface"
    elif float(apparent_planet_radius) >= 2.08:
        scale_level = "surface"
    elif float(apparent_planet_radius) >= 0.92:
        scale_level = "approach"
    else:
        scale_level = "orbital"
    payload = {
        "camera_pose_id": camera_pose_id,
        "target_body_id": scene.planet_macro_authority.planet_id,
        "distance_to_target_world": round(distance_to_target, 6),
        "apparent_radius_px": round(float(apparent_planet_radius), 6),
        "footprint_radius_world": round(footprint, 6),
        "scale_level": scale_level,
        "transition_weight": round(max(0.0, min(1.0, float(surface_lod_blend))), 6),
        "sensor_band": sensor_band,
        "target_depth_world": round(float(volume_observation.sample_depth_world), 6),
        "frame_kind": frame_kind,
        "camera_steps_per_world_tick": int(ray_bundle.get("camera_steps_per_world_tick", 1)),
        "refinement_demand_record_id": volume_demand.record_id,
        "source_record_ids": _unique_record_ids(
            [
                camera_pose_id,
                str(ray_bundle["ray_bundle_id"]),
                volume_observation.record_id,
                volume_demand.record_id,
                scene.planet_macro_authority.record_id,
            ]
        ),
    }
    return {
        "schema": "camera_scale_state_v1",
        "camera_scale_state_id": _record_id_digest("camera-scale-state", payload),
        **payload,
        "is_authority_state": False,
    }


def _volume_layer_segments_payload(
    scene: SolarEarthSceneState,
    *,
    volume_observation: PlanetVolumeRayObservationRecord,
    volume_demand: VolumeRefinementDemandRecord,
    ray_bundle_id: str,
) -> list[dict[str, Any]]:
    layer_by_id = {layer.record_id: layer for layer in scene.layer_shells}
    ordered_layers = sorted(
        (layer_by_id[layer_id] for layer_id in volume_observation.traversed_layer_ids if layer_id in layer_by_id),
        key=lambda layer: layer.outer_radius_world,
        reverse=True,
    )
    segments: list[dict[str, Any]] = []
    max_depth = max(0.0, float(volume_observation.sample_depth_world))
    for layer in ordered_layers:
        entry = max(0.0, scene.planet_radius_world - float(layer.outer_radius_world))
        exit_depth = min(max_depth, max(0.0, scene.planet_radius_world - float(layer.inner_radius_world)))
        if exit_depth + 1e-9 < entry:
            continue
        width = max(1e-9, exit_depth - entry)
        payload = {
            "layer_id": layer.record_id,
            "entry_depth_world": round(entry, 6),
            "exit_depth_world": round(exit_depth, 6),
            "attenuation": volume_observation.attenuation,
            "emission": round(float(layer.thermal_response), 6),
            "screen_band_weight": round(min(1.0, width / max(1e-9, scene.planet_radius_world)), 6),
            "sample_count": max(1, int(round(width / max(1e-9, scene.planet_radius_world) * 64))),
            "ray_bundle_id": str(ray_bundle_id),
            "volume_observation_record_id": volume_observation.record_id,
            "refinement_demand_record_ids": [volume_demand.record_id],
            "source_record_ids": _unique_record_ids(
                [
                    str(ray_bundle_id),
                    volume_observation.record_id,
                    volume_demand.record_id,
                    layer.record_id,
                    *layer.source_record_ids,
                ]
            ),
        }
        segments.append(
            {
                "schema": "volume_layer_segment_v1",
                "segment_id": _record_id_digest("volume-layer-segment", payload),
                **payload,
                "is_authority_state": False,
            }
        )
    return segments


def _continuous_refinement_ux_state_payload(
    scene: SolarEarthSceneState,
    *,
    observer_id: str,
    camera_pose_id: str,
    camera_pose: Mapping[str, Any],
    contribution: Mapping[str, Any],
    sensor_state: Mapping[str, Any],
    ray_observation: Mapping[str, Any],
    scale_state: Mapping[str, Any],
    volume_observation: PlanetVolumeRayObservationRecord,
    volume_demand: VolumeRefinementDemandRecord,
    surface_samples: Sequence[Mapping[str, Any]],
    volume_segments: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    sensor_band_mode = str(camera_pose.get("sensor_band_mode") or ray_observation.get("sensor_band_mode") or "visible_surface")
    sensor_band_blend_factor = max(
        0.0,
        min(1.0, float(camera_pose.get("sensor_band_blend_factor", 1.0) or 0.0)),
    )
    volume_raw = 0.0
    if sensor_band_mode in {"near_ir_penetrating", "thermal_internal"} or volume_observation.occlusion_status == "penetrating_observation":
        volume_raw = min(0.68, max(0.0, float(volume_demand.refinement_weight)) * 0.68) * sensor_band_blend_factor
    remaining = max(0.0, 1.0 - volume_raw)
    macro_raw = max(0.0, float(contribution.get("macro_weight", 0.0) or 0.0))
    surface_raw = max(0.0, float(contribution.get("surface_weight", 0.0) or 0.0))
    local_raw = max(0.0, float(contribution.get("local_patch_weight", 0.0) or 0.0))
    base_total = max(1e-9, macro_raw + surface_raw + local_raw)
    weights = {
        "macro": round(remaining * macro_raw / base_total, 6),
        "surface": round(remaining * surface_raw / base_total, 6),
        "local_patch": round(remaining * local_raw / base_total, 6),
        "volume": round(volume_raw, 6),
    }
    drift = round(1.0 - sum(weights.values()), 6)
    weights["macro"] = round(weights["macro"] + drift, 6)
    local_request_ids = [
        str(value)
        for value in contribution.get("local_refinement_request_ids", [])
        if value
    ]
    local_patch_ids = [
        str(value)
        for value in contribution.get("local_refinement_patch_ids", [])
        if value
    ]
    volume_segment_ids = [str(segment.get("segment_id")) for segment in volume_segments if segment.get("segment_id")]
    surface_sample_ids = [str(sample.get("sample_id")) for sample in surface_samples if sample.get("sample_id")]
    if weights["local_patch"] > 0.01:
        stage = "local_refinement_blend"
    elif weights["volume"] > 0.01:
        stage = "volume_probe_blend"
    elif weights["surface"] > 0.36:
        stage = "surface_evidence_blend"
    else:
        stage = "macro_evidence_blend"
    payload = {
        "schema": "continuous_refinement_ux_state_v1",
        "observer_id": observer_id,
        "tick": int(scene.tick),
        "camera_pose_id": camera_pose_id,
        "sensor_band_mode": sensor_band_mode,
        "sensor_band_blend_factor": round(sensor_band_blend_factor, 6),
        "transition_mode": "continuous_authority_evidence_blend",
        "refinement_stage": stage,
        "authority_layer_weights": weights,
        "weight_sum": round(sum(weights.values()), 6),
        "macro_authority_id": scene.planet_macro_authority.record_id,
        "surface_field_id": scene.surface_field.record_id if scene.surface_field else "",
        "sensor_state_id": str(sensor_state.get("sensor_state_id") or ""),
        "sensor_ray_observation_id": str(ray_observation.get("ray_bundle_id") or ""),
        "camera_scale_state_id": str(scale_state.get("camera_scale_state_id") or ""),
        "refinement_demand_id": str(contribution.get("refinement_demand_id") or ""),
        "volume_refinement_demand_id": volume_demand.record_id,
        "volume_ray_observation_id": volume_observation.record_id,
        "local_refinement_request_ids": local_request_ids,
        "local_refinement_patch_ids": local_patch_ids,
        "surface_sample_ids": surface_sample_ids[:64],
        "volume_layer_segment_ids": volume_segment_ids,
        "projected_footprint_world": contribution.get("projected_footprint_world"),
        "macro_error_bound_world": contribution.get("macro_error_bound_world"),
        "apparent_planet_radius": contribution.get("apparent_planet_radius"),
        "hard_mode_switch": False,
        "viewer_generated_detail_allowed": False,
        "viewer_may_render_only_serialized_projection": True,
        "is_authority_state": False,
    }
    source_record_ids = _unique_record_ids(
        [
            scene.planet_macro_authority.record_id,
            scene.surface_field.record_id if scene.surface_field else "",
            str(sensor_state.get("sensor_state_id") or ""),
            str(ray_observation.get("ray_bundle_id") or ""),
            str(scale_state.get("camera_scale_state_id") or ""),
            str(contribution.get("contribution_id") or ""),
            str(contribution.get("refinement_demand_id") or ""),
            volume_observation.record_id,
            volume_demand.record_id,
            *local_request_ids,
            *local_patch_ids,
            *surface_sample_ids[:64],
            *volume_segment_ids,
            *contribution.get("source_record_ids", []),
            *ray_observation.get("source_record_ids", []),
            *scale_state.get("source_record_ids", []),
        ]
    )
    payload["source_record_ids"] = source_record_ids
    payload["ux_state_id"] = _record_id_digest("continuous-refinement-ux-state", payload)
    return payload


def _surface_readability_samples_payload(
    scene: SolarEarthSceneState,
    *,
    camera_pose: Mapping[str, Any],
    origin: Sequence[float],
    forward: Sequence[float],
    ray_bundle_id: str,
    refinement_demand_record_ids: Sequence[str],
    footprint_span_world: float,
    grid_size: int = 16,
) -> list[dict[str, Any]]:
    if scene.surface_field is None:
        return []
    surface_normal = _vec_norm(_vec_sub(origin, scene.planet_center_world))
    tangent_right, tangent_forward = _surface_tangent_axes(surface_normal, forward)
    span = max(0.55, min(1.40, float(footprint_span_world) * 4.0))
    samples: list[dict[str, Any]] = []
    for row in range(grid_size):
        for col in range(grid_size):
            sx = (col / max(1, grid_size - 1) - 0.5) * span
            sy = (row / max(1, grid_size - 1) - 0.5) * span
            sample_normal = _vec_norm(
                _vec_add(
                    _vec_add(surface_normal, _vec_scale(tangent_right, sx)),
                    _vec_scale(tangent_forward, sy),
                )
            )
            u, v = _uv_from_unit_normal(sample_normal)
            sample = sample_planet_surface_readability(
                scene.surface_field,
                u=u,
                v=v,
                footprint_span_world=max(1e-5, span / grid_size),
                tick=scene.tick,
                ray_bundle_id=ray_bundle_id,
                refinement_demand_record_ids=refinement_demand_record_ids,
                center_world=scene.planet_center_world,
                radius_world=scene.planet_radius_world,
            )
            samples.append(sample.to_dict())
    return samples


def _image_plane_digest(image_plane: Mapping[str, Any]) -> str:
    digest_payload = {
        "image_plane_id": image_plane.get("image_plane_id"),
        "tiles": image_plane.get("tiles", []),
        "camera_ray_bundle": image_plane.get("camera_ray_bundle", {}),
        "spectral_sensor_state": image_plane.get("spectral_sensor_state", {}),
        "sensor_ray_observation": image_plane.get("sensor_ray_observation", {}),
        "camera_scale_state": image_plane.get("camera_scale_state", {}),
        "continuous_refinement_ux_state": image_plane.get("continuous_refinement_ux_state", {}),
        "surface_sample_ids": [sample.get("sample_id") for sample in image_plane.get("surface_readability_samples", [])],
        "volume_segment_ids": [segment.get("segment_id") for segment in image_plane.get("volume_layer_segments", [])],
        "visible_response_id": (image_plane.get("visible_interaction_response") or {}).get("visible_response_id"),
        "projection_response_overlay_ids": [
            overlay.get("overlay_id") for overlay in image_plane.get("projection_response_overlays", [])
        ],
    }
    return _canonical_digest(digest_payload)


def _m13_authority_summary_payload(
    scene: SolarEarthSceneState,
    image_plane: Mapping[str, Any],
    *,
    observer_id: str,
) -> dict[str, Any]:
    scale_state = image_plane.get("camera_scale_state", {})
    body_profile = image_plane.get("body_spectral_profile", {})
    surface_samples = list(image_plane.get("surface_readability_samples", []))
    volume_segments = list(image_plane.get("volume_layer_segments", []))
    support = [
        {
            "sample_id": sample.get("sample_id"),
            "u": sample.get("u"),
            "v": sample.get("v"),
            "dominant_material": sample.get("dominant_material"),
            "readability": sample.get("readability"),
        }
        for sample in surface_samples[:32]
    ]
    boundary = [
        {
            "segment_id": segment.get("segment_id"),
            "layer_id": segment.get("layer_id"),
            "entry_depth_world": segment.get("entry_depth_world"),
            "exit_depth_world": segment.get("exit_depth_world"),
            "attenuation": segment.get("attenuation"),
        }
        for segment in volume_segments
    ]
    summary = {
        "schema": "m13_authority_summary_v1",
        "structure_id": f"solar-earth-planet::{scene.planet_macro_authority.planet_id}",
        "observer_id": observer_id,
        "tick": int(scene.tick),
        "runtime_window": {"start_tick": int(scene.tick), "end_tick": int(scene.tick)},
        "summary_source_kind": "compact_readback_summary_with_input_digest",
        "source_authority_record_ids": _unique_record_ids(
            [
                scene.planet_macro_authority.record_id,
                scene.surface_field.record_id if scene.surface_field else "",
                *[layer.record_id for layer in scene.layer_shells],
            ]
        ),
        "support": support,
        "boundary": boundary,
        "centroid_world": [round(float(value), 6) for value in scene.planet_center_world],
        "relative_energy": round(float(image_plane.get("radiance_summary", {}).get("mean", 0.0) or 0.0), 6),
        "mode_signature": [
            "layered_macro_body",
            str(scale_state.get("scale_level", "unknown_scale")),
            str((body_profile or {}).get("body_kind", "unknown_body")),
        ],
        "instability_flags": [] if surface_samples else ["projection_window_has_no_surface_samples"],
        "source_record_ids": _unique_record_ids(
            [
                scene.planet_macro_authority.record_id,
                scene.surface_field.record_id if scene.surface_field else "",
                *[layer.record_id for layer in scene.layer_shells],
                *[sample.get("sample_id") for sample in surface_samples],
                *[segment.get("segment_id") for segment in volume_segments],
                *image_plane.get("source_record_ids", []),
            ]
        ),
    }
    digest_input = {key: value for key, value in summary.items() if key not in {"record_id", "digest"}}
    summary["digest"] = m13_canonical_digest(digest_input)
    summary["record_id"] = f"authority-summary::m13::solar-earth::{summary['digest'].split(':', 1)[1][:16]}"
    return summary


def _realtime_lod_state(
    scene: SolarEarthSceneState,
    image_plane: Mapping[str, Any],
    *,
    camera_pose_id: str,
) -> dict[str, Any]:
    camera_projection = image_plane.get("camera_projection", {})
    surface_detail = (camera_projection.get("surface_detail") or {}) if isinstance(camera_projection, Mapping) else {}
    distance = float(camera_projection.get("camera_distance_to_planet", 0.0) or 0.0)
    apparent_radius = float(surface_detail.get("apparent_planet_radius", camera_projection.get("planet_screen_radius", 0.0)) or 0.0)
    sensor_band_mode = str(surface_detail.get("sensor_band_mode") or image_plane.get("camera_ray_bundle", {}).get("sensor_band") or "visible_surface")
    scale_level = "orbit"
    if distance < scene.planet_radius_world:
        scale_level = "subsurface"
    elif apparent_radius >= 1.0:
        scale_level = "surface"
    elif apparent_radius >= 0.25:
        scale_level = "near_surface"
    surface_weight = max(0.0, min(1.0, float(surface_detail.get("strength", 0.0) or 0.0)))
    volume_weight = 1.0 if sensor_band_mode in {"near_ir_penetrating", "thermal_internal"} or scale_level == "subsurface" else 0.0
    macro_weight = max(0.0, min(1.0, 1.0 - surface_weight * 0.55))
    active_layers = ["macro_body"]
    if surface_weight > 0.0 or scene.surface_field:
        active_layers.append("surface_field")
    if volume_weight > 0.0:
        active_layers.append("volume_layer")
    local_patch_weight = 1.0 if surface_detail.get("active_local_patch_id") else 0.0
    if local_patch_weight:
        active_layers.append("fine_refinement_patch")
    return {
        "schema": REALTIME_LOD_STATE_SCHEMA,
        "lod_state_id": f"realtime-lod-state::{camera_pose_id.split('::')[-1]}::{scene.tick}",
        "scale_level": scale_level,
        "camera_distance_to_target_world": round(distance, 6),
        "apparent_radius_px": round(apparent_radius * 512.0, 6),
        "footprint_radius_world": round(max(0.001, scene.planet_radius_world / max(0.1, apparent_radius + 0.1)), 6),
        "macro_weight": round(macro_weight, 6),
        "surface_weight": round(surface_weight, 6),
        "local_patch_weight": round(local_patch_weight, 6),
        "volume_weight": round(volume_weight, 6),
        "active_authority_layers": active_layers,
        "source_record_ids": _unique_record_ids(
            [
                scene.planet_macro_authority.record_id,
                scene.surface_field.record_id if scene.surface_field else "",
                *[layer.record_id for layer in scene.layer_shells],
                *surface_detail.get("penetrated_layer_ids", []),
            ]
        ),
    }


def _build_realtime_projection_frame_packet(
    scene: SolarEarthSceneState,
    *,
    frame: ProjectionFrame,
    observer_id: str,
    camera_pose: Mapping[str, Any],
    image_plane: Mapping[str, Any],
    authority_summary: Mapping[str, Any],
) -> dict[str, Any]:
    camera_projection = image_plane.get("camera_projection", {})
    surface_detail = (camera_projection.get("surface_detail") or {}) if isinstance(camera_projection, Mapping) else {}
    camera_pose_id = str(camera_projection.get("camera_pose_id") or f"solar-earth-camera::{observer_id}")
    sensor_band_mode = str(surface_detail.get("sensor_band_mode") or image_plane.get("camera_ray_bundle", {}).get("sensor_band") or "visible_surface")
    spectral_sensor_state = image_plane.get("spectral_sensor_state", {})
    sensor_ray_observation = image_plane.get("sensor_ray_observation", {})
    loss = frame.payload.get("projection_loss_manifest_v1", {})
    invariants = frame.payload.get("invariant_signatures_v1", [])
    invariant_ids = [str(item.get("signature_id")) for item in invariants if item.get("signature_id")]
    authority_summary_id = str(authority_summary.get("record_id") or "")
    source_ids = _unique_record_ids(
        [
            *scene.source_record_ids,
            *[body.record_id for body in scene.macro_body_states],
            scene.solar_source.record_id,
            scene.surface_field.record_id if scene.surface_field else "",
            scene.planet_macro_authority.record_id,
            *[layer.record_id for layer in scene.layer_shells],
            *[record.record_id for record in scene.gravity_potential_records],
            *image_plane.get("source_record_ids", []),
            image_plane.get("image_plane_id", ""),
            spectral_sensor_state.get("sensor_state_id") if isinstance(spectral_sensor_state, Mapping) else "",
            sensor_ray_observation.get("ray_bundle_id") if isinstance(sensor_ray_observation, Mapping) else "",
            frame.frame_id,
        ]
    )
    renderables: list[dict[str, Any]] = []
    for body in scene.macro_body_states:
        renderables.append(
            {
                "schema": REALTIME_RENDERABLE_SCHEMA,
                "renderable_id": f"renderable::{body.record_id}",
                "kind": "macro_body_sphere",
                "is_authority_state": False,
                "geometry_ref": body.record_id,
                "material_response_ref": scene.surface_field.record_id if scene.surface_field and body.body_kind == "planet" else scene.solar_source.record_id,
                "source_record_ids": _unique_record_ids([body.record_id, scene.surface_field.record_id if scene.surface_field else "", scene.solar_source.record_id]),
            }
        )
    for layer in scene.layer_shells:
        if layer.layer_kind == "atmosphere":
            renderables.append(
                {
                    "schema": REALTIME_RENDERABLE_SCHEMA,
                    "renderable_id": f"renderable::{layer.record_id}",
                    "kind": "atmosphere_shell",
                    "is_authority_state": False,
                    "geometry_ref": layer.record_id,
                    "volume_ref": layer.record_id,
                    "source_record_ids": [layer.record_id],
                }
            )
    if scene.surface_field:
        renderables.append(
            {
                "schema": REALTIME_RENDERABLE_SCHEMA,
                "renderable_id": f"renderable::{scene.surface_field.record_id}",
                "kind": "surface_spectral_tile",
                "is_authority_state": False,
                "surface_field_ref": scene.surface_field.record_id,
                "material_response_ref": scene.surface_field.record_id,
                "source_record_ids": _unique_record_ids([scene.surface_field.record_id, *surface_detail.get("sample_record_ids", [])]),
            }
        )
    renderables.append(
        {
            "schema": REALTIME_RENDERABLE_SCHEMA,
            "renderable_id": f"renderable::{scene.solar_source.record_id}",
            "kind": "star_radiation_emitter",
            "is_authority_state": False,
            "geometry_ref": scene.solar_source.record_id,
            "radiation_ref": scene.solar_source.record_id,
            "source_record_ids": [scene.solar_source.record_id],
        }
    )
    packet = {
        "schema": REALTIME_PROJECTION_FRAME_PACKET_SCHEMA,
        "packet_id": f"realtime-projection-packet::{frame.frame_id}",
        "frame_kind": "render_only_camera_frame" if not frame.payload.get("timeline_semantics", {}).get("world_advanced") else "world_step_projection",
        "is_authority_state": False,
        "viewer_is_not_authority": True,
        "source_scene_tick": int(scene.tick),
        "world_tick_delta": 1 if frame.payload.get("timeline_semantics", {}).get("world_advanced") else 0,
        "source_record_ids": source_ids,
        "authority_summary_ids": [authority_summary_id],
        "projection_loss_manifest_id": str(loss.get("manifest_id") or ""),
        "invariant_signature_ids": invariant_ids,
        "spectral_observation_refs": {
            "schema": "realtime_spectral_observation_refs_v1",
            "image_plane_id": str(image_plane.get("image_plane_id") or ""),
            "spectral_sensor_state_id": str(
                spectral_sensor_state.get("sensor_state_id") if isinstance(spectral_sensor_state, Mapping) else ""
            ),
            "sensor_ray_observation_id": str(
                sensor_ray_observation.get("ray_bundle_id") if isinstance(sensor_ray_observation, Mapping) else ""
            ),
        },
        "camera_state": {
            "schema": REALTIME_OBSERVER_CAMERA_STATE_SCHEMA,
            "camera_state_id": camera_pose_id,
            "observer_id": observer_id,
            "position_world": list(camera_pose.get("origin") or camera_pose.get("position") or [0.0, 0.0, 0.0]),
            "look_at_world": list(camera_pose.get("look_at") or scene.planet_center_world),
            "up_world": list(camera_pose.get("up") or [0.0, 0.0, 1.0]),
            "fov_y_degrees": float(camera_pose.get("fov_degrees", 50.0)),
            "source_record_ids": [frame.frame_id],
        },
        "sensor_state": {
            "schema": REALTIME_SENSOR_STATE_SCHEMA,
            "sensor_state_id": str(
                spectral_sensor_state.get("sensor_state_id")
                if isinstance(spectral_sensor_state, Mapping)
                else f"realtime-sensor-state::{camera_pose_id.split('::')[-1]}::{sensor_band_mode}"
            ),
            "mode": sensor_band_mode,
            "band_weights": {
                band.band_id: float(band.response_weight)
                for band in scene.spectral_profile.bands
                if bool(band.visible)
            },
            "source_record_ids": [scene.spectral_profile.profile_id],
        },
        "lod_state": _realtime_lod_state(scene, image_plane, camera_pose_id=camera_pose_id),
        "renderables": renderables,
    }
    validate_realtime_projection_frame_packet(packet)
    return packet


def _attach_continuous_earth_slice_contracts(
    image_plane: dict[str, Any],
    scene: SolarEarthSceneState,
    *,
    observer_id: str,
    camera_pose: Mapping[str, Any],
    camera_pose_id: str,
    image_shape: tuple[int, int],
    origin: Sequence[float],
    forward: Sequence[float],
    apparent_planet_radius: float,
    surface_lod_blend: float,
    volume_observation: PlanetVolumeRayObservationRecord,
    volume_demand: VolumeRefinementDemandRecord,
    frame_kind: str = "world_step",
) -> dict[str, Any]:
    ray_bundle = _camera_ray_bundle_payload(
        scene,
        observer_id=observer_id,
        camera_pose_id=camera_pose_id,
        camera_pose=camera_pose,
        image_shape=image_shape,
        frame_kind=frame_kind,
    )
    sensor_state = _spectral_sensor_state_payload(
        scene,
        observer_id=observer_id,
        camera_pose_id=camera_pose_id,
        camera_pose=camera_pose,
    )
    ray_observation = _sensor_ray_observation_payload(
        scene,
        sensor_state=sensor_state,
        ray_bundle=ray_bundle,
        image_shape=image_shape,
        volume_observation=volume_observation,
        volume_demand=volume_demand,
    )
    scale_state = _camera_scale_state_payload(
        scene,
        camera_pose=camera_pose,
        camera_pose_id=camera_pose_id,
        ray_bundle=ray_bundle,
        apparent_planet_radius=apparent_planet_radius,
        surface_lod_blend=surface_lod_blend,
        frame_kind=frame_kind,
        volume_demand=volume_demand,
        volume_observation=volume_observation,
    )
    footprint = float(scale_state["footprint_radius_world"])
    surface_samples = _surface_readability_samples_payload(
        scene,
        camera_pose=camera_pose,
        origin=origin,
        forward=forward,
        ray_bundle_id=str(ray_bundle["ray_bundle_id"]),
        refinement_demand_record_ids=[volume_demand.record_id],
        footprint_span_world=max(footprint, scene.planet_radius_world * 0.08),
    )
    volume_segments = _volume_layer_segments_payload(
        scene,
        volume_observation=volume_observation,
        volume_demand=volume_demand,
        ray_bundle_id=str(ray_bundle["ray_bundle_id"]),
    )
    continuous_ux_state = _continuous_refinement_ux_state_payload(
        scene,
        observer_id=observer_id,
        camera_pose_id=camera_pose_id,
        camera_pose=camera_pose,
        contribution=image_plane.get("multiscale_projection_contribution", {}),
        sensor_state=sensor_state,
        ray_observation=ray_observation,
        scale_state=scale_state,
        volume_observation=volume_observation,
        volume_demand=volume_demand,
        surface_samples=surface_samples,
        volume_segments=volume_segments,
    )
    image_plane["body_spectral_profile"] = _body_spectral_profile_payload(scene)
    image_plane["camera_ray_bundle"] = ray_bundle
    image_plane["spectral_sensor_state"] = sensor_state
    image_plane["sensor_ray_observation"] = ray_observation
    image_plane["sampling_policy"] = {
        "schema": "spectral_sensor_sampling_policy_v1",
        "basis": "observer_footprint_adaptive",
        "pixel_artifact_policy": "continuous_sensor_filter",
        "image_shape": [int(image_shape[0]), int(image_shape[1])],
        "sampling_resolution_mode": str(camera_pose.get("sampling_resolution_mode") or "default_adaptive"),
        "max_adaptive_image_shape": list(_optional_image_shape(camera_pose.get("max_adaptive_image_shape")) or []),
        "source_record_ids": [str(sensor_state["sensor_state_id"]), str(ray_observation["ray_bundle_id"])],
        "is_authority_state": False,
    }
    image_plane["camera_scale_state"] = scale_state
    image_plane["surface_readability_samples"] = surface_samples
    image_plane["volume_layer_segments"] = volume_segments
    image_plane["continuous_refinement_ux_state"] = continuous_ux_state
    image_plane["projection_frame_digest"] = _image_plane_digest(image_plane)
    image_plane["source_record_ids"] = _unique_record_ids(
        [
            *image_plane.get("source_record_ids", []),
            image_plane["body_spectral_profile"]["body_profile_id"],
            ray_bundle["ray_bundle_id"],
            sensor_state["sensor_state_id"],
            ray_observation["ray_bundle_id"],
            *ray_observation["source_record_ids"],
            scale_state["camera_scale_state_id"],
            continuous_ux_state["ux_state_id"],
            *[sample["sample_id"] for sample in surface_samples],
            *[segment["segment_id"] for segment in volume_segments],
            *continuous_ux_state["source_record_ids"],
            *ray_bundle.get("source_record_ids", []),
            *scale_state.get("source_record_ids", []),
        ]
    )
    return image_plane


def default_solar_earth_camera_pose(scene: SolarEarthSceneState) -> dict[str, Any]:
    midpoint = [
        (float(scene.solar_source.center_world[index]) + float(scene.planet_center_world[index])) / 2.0
        for index in range(3)
    ]
    return {
        "origin": [midpoint[0], -18.0, 5.0],
        "look_at": list(scene.planet_center_world),
        "up": [0.0, 0.0, 1.0],
        "fov_degrees": 50.0,
        "sensor_band_mode": "visible_surface",
    }


def _surface_point_from_origin(scene: SolarEarthSceneState, origin: Sequence[float]) -> list[float]:
    direction = _vec_norm(_vec_sub(origin, scene.planet_center_world))
    return _vec_add(scene.planet_center_world, _vec_scale(direction, scene.planet_radius_world))


def _covering_local_patch_id(
    scene: SolarEarthSceneState,
    surface_point: Sequence[float],
    local_refinement_requests: Sequence[Any],
    local_refinement_patches: Sequence[Any],
) -> str | None:
    requests_by_id = {str(_record_get(request, "request_id")): request for request in local_refinement_requests}
    best: tuple[float, str] | None = None
    for patch in local_refinement_patches:
        patch_id = str(_record_get(patch, "patch_id", ""))
        request_id = str(_record_get(patch, "request_id", ""))
        request = requests_by_id.get(request_id)
        if not patch_id or request is None:
            continue
        point = _record_get(request, "world_point", None)
        radius = float(_record_get(request, "requested_radius_world", 0.0) or 0.0)
        if point is None or radius <= 0.0:
            continue
        distance = _distance(surface_point, point)
        try:
            surface_normal = _vec_norm(_vec_sub(surface_point, scene.planet_center_world))
            request_normal = _vec_norm(_vec_sub(point, scene.planet_center_world))
            angular_distance = math.sqrt(
                sum((surface_normal[index] - request_normal[index]) ** 2 for index in range(3))
            ) * scene.planet_radius_world
            distance = min(distance, angular_distance)
        except ValueError:
            pass
        tolerance = max(radius, scene.planet_radius_world * 0.16)
        if distance <= tolerance and (best is None or distance < best[0]):
            best = (distance, patch_id)
    return None if best is None else best[1]


def apply_solar_earth_camera_move(
    scene: SolarEarthSceneState,
    camera_pose: Mapping[str, Any],
    request: Mapping[str, Any],
    *,
    initial_camera_pose: Mapping[str, Any],
    local_refinement_requests: Sequence[Any] | None = None,
    local_refinement_patches: Sequence[Any] | None = None,
) -> dict[str, Any]:
    action = str(request.get("action", ""))
    if action not in ALLOWED_SOLAR_EARTH_CAMERA_ACTIONS:
        raise ValueError("unsupported solar earth camera action")
    sensor_band_mode = str(request.get("sensor_band_mode") or camera_pose.get("sensor_band_mode") or "visible_surface")
    if sensor_band_mode not in ALLOWED_SOLAR_EARTH_SENSOR_BAND_MODES:
        raise ValueError("unsupported solar earth sensor_band_mode")
    if action == "reset":
        return {**dict(initial_camera_pose), "sensor_band_mode": sensor_band_mode}
    motion_action = {
        "zoom_in": "forward",
        "zoom_out": "back",
    }.get(action, action)
    origin, forward, right, up, fov_degrees = _camera_basis(camera_pose)
    origin = list(origin)
    forward = list(forward)
    right = list(right)
    up = list(up)
    look_at_hint = _finite_vec3(camera_pose.get("look_at") or _vec_add(origin, forward), name="camera_pose.look_at")
    focus_distance = max(1.0, _distance(origin, look_at_hint))
    step = float(request.get("step_world", 0.0))
    if not math.isfinite(step) or step < 0.0:
        raise ValueError("solar earth camera step_world must be non-negative")
    yaw = float(request.get("yaw_degrees", 0.0))
    if not math.isfinite(yaw):
        raise ValueError("solar earth camera yaw_degrees must be finite")
    target_center = [float(value) for value in scene.planet_center_world]
    distance_to_planet = _distance(origin, target_center)
    target_locked_motion = (
        str(camera_pose.get("target_lock") or "") == "planet_center"
        or _distance(look_at_hint, target_center) <= max(1e-6, scene.planet_radius_world * 0.001)
    )
    max_camera_delta = float(REALTIME_RENDERER_THRESHOLDS["max_camera_position_delta_without_intermediate_frame"])
    requested_zoom_step = step if step > 0.0 else max(0.08, distance_to_planet * 0.035)
    requested_pan_step = step if step > 0.0 else max(0.04, distance_to_planet * 0.025)
    effective_zoom_step = min(requested_zoom_step, max_camera_delta)
    effective_pan_step = min(requested_pan_step, max_camera_delta)

    motion_policy: dict[str, Any] = {
        "schema": "solar_earth_camera_motion_policy_v1",
        "status": "free_sensor_motion",
        "refinement_demand": {},
        "source_record_ids": [scene.planet_macro_authority.record_id],
    }

    focus_point: list[float] | None = None
    if motion_action == "forward":
        motion_forward = _vec_norm(_vec_sub(target_center, origin)) if target_locked_motion else forward
        next_origin = _vec_add(origin, _vec_scale(motion_forward, effective_zoom_step))
        if sensor_band_mode == "visible_surface":
            clamp_distance = scene.planet_radius_world * 1.012
            oc = _vec_sub(origin, target_center)
            b = 2.0 * _vec_dot(oc, motion_forward)
            c = _vec_dot(oc, oc) - clamp_distance * clamp_distance
            discriminant = b * b - 4.0 * c
            candidates: list[float] = []
            if discriminant >= 0.0:
                root = math.sqrt(discriminant)
                candidates = [
                    candidate
                    for candidate in ((-b - root) / 2.0, (-b + root) / 2.0)
                    if 0.0 <= candidate <= effective_zoom_step
                ]
            if candidates or _distance(next_origin, target_center) < clamp_distance:
                if candidates:
                    next_origin = _vec_add(origin, _vec_scale(motion_forward, min(candidates)))
                else:
                    surface_direction = _vec_norm(_vec_sub(next_origin, target_center))
                    next_origin = _vec_add(target_center, _vec_scale(surface_direction, clamp_distance))
                origin = next_origin
                motion_policy["status"] = "macro_boundary_requires_refinement"
            else:
                origin = next_origin
        else:
            if target_locked_motion and effective_zoom_step >= distance_to_planet:
                effective_zoom_step = max(0.0, distance_to_planet * 0.9)
                next_origin = _vec_add(origin, _vec_scale(motion_forward, effective_zoom_step))
            origin = next_origin
            if _distance(origin, target_center) < scene.planet_radius_world:
                motion_policy["status"] = "spectral_probe_internal_motion"
                motion_policy["traversal_mode"] = "spectral_probe"
        if target_locked_motion:
            forward = _vec_norm(_vec_sub(target_center, origin))
            right = _vec_norm(_vec_cross(forward, up))
            up = _vec_norm(_vec_cross(right, forward))
            focus_point = target_center
    elif motion_action == "back":
        motion_forward = _vec_norm(_vec_sub(target_center, origin)) if target_locked_motion else forward
        origin = _vec_sub(origin, _vec_scale(motion_forward, effective_zoom_step))
        if target_locked_motion:
            forward = _vec_norm(_vec_sub(target_center, origin))
            right = _vec_norm(_vec_cross(forward, up))
            up = _vec_norm(_vec_cross(right, forward))
            focus_point = target_center
    elif motion_action == "strafe_left":
        origin = _vec_sub(origin, _vec_scale(right, effective_pan_step))
    elif motion_action == "strafe_right":
        origin = _vec_add(origin, _vec_scale(right, effective_pan_step))
    elif motion_action == "up":
        origin = _vec_add(origin, _vec_scale(up, effective_pan_step))
    elif motion_action == "down":
        origin = _vec_sub(origin, _vec_scale(up, effective_pan_step))
    elif motion_action == "pitch_up":
        forward = _vec_norm(_rotate_vector_around_axis(forward, right, yaw or 8.0))
        up = _vec_norm(_vec_cross(right, forward))
        origin = _vec_add(origin, _vec_scale(up, effective_pan_step))
    elif motion_action == "pitch_down":
        forward = _vec_norm(_rotate_vector_around_axis(forward, right, -(yaw or 8.0)))
        up = _vec_norm(_vec_cross(right, forward))
        origin = _vec_sub(origin, _vec_scale(up, effective_pan_step))
    elif motion_action == "yaw_left":
        forward = _vec_norm(_rotate_vector_around_axis(forward, up, yaw or 8.0))
        right = _vec_norm(_vec_cross(forward, up))
        up = _vec_norm(_vec_cross(right, forward))
    elif motion_action == "yaw_right":
        forward = _vec_norm(_rotate_vector_around_axis(forward, up, -(yaw or 8.0)))
        right = _vec_norm(_vec_cross(forward, up))
        up = _vec_norm(_vec_cross(right, forward))
    elif motion_action in {"orbit_left", "orbit_right"}:
        signed_yaw = yaw or 8.0
        if motion_action == "orbit_right":
            signed_yaw = -signed_yaw
        if target_locked_motion:
            offset = _vec_sub(origin, target_center)
            rotated_offset = _rotate_vector_around_axis(offset, up, signed_yaw)
            origin = _vec_add(target_center, rotated_offset)
            forward = _vec_norm(_vec_sub(target_center, origin))
            right = _vec_norm(_vec_cross(forward, up))
            up = _vec_norm(_vec_cross(right, forward))
            focus_point = target_center
        else:
            forward = _vec_norm(_rotate_vector_around_axis(forward, up, signed_yaw))
            right = _vec_norm(_vec_cross(forward, up))
            up = _vec_norm(_vec_cross(right, forward))
    else:
        raise ValueError("unsupported solar earth camera action")

    if focus_point is None:
        focus_point = _vec_add(origin, _vec_scale(forward, focus_distance))
    observer = build_observer_state_record(
        scene,
        str(request.get("observer_id") or "observer::solar-earth-orbit"),
        {
            **dict(camera_pose),
            "origin": origin,
            "look_at": focus_point,
            "forward_world": forward,
            "right_world": right,
            "up_world": up,
            "up": up,
            "sensor_band_mode": sensor_band_mode,
            "sensor_band_blend_factor": max(
                0.0,
                min(1.0, float(request.get("sensor_band_blend_factor", 1.0) or 0.0)),
            ),
        },
        {
            "action": action,
            "step_world": effective_zoom_step if motion_action in {"forward", "back"} else effective_pan_step,
            "request_id": request.get("request_id") or request.get("source_request_id") or "camera-request::anonymous",
            "sensor_band_mode": sensor_band_mode,
        },
    )
    volume_observation = trace_planet_volume_observation(scene, observer)
    volume_demand = compute_volume_refinement_demand(scene, observer, volume_observation)
    demand = compute_refinement_demand(scene, observer)
    motion_policy["refinement_demand"] = demand.to_dict()
    motion_policy["volume_ray_observation"] = volume_observation.to_dict()
    motion_policy["volume_refinement_demand"] = volume_demand.to_dict()
    motion_policy["source_record_ids"] = _unique_record_ids(
        [
            *motion_policy["source_record_ids"],
            observer.record_id,
            volume_observation.record_id,
            volume_demand.record_id,
            *volume_observation.source_record_ids,
            *volume_demand.source_record_ids,
        ]
    )
    surface_point = _surface_point_from_origin(scene, origin)
    patch_id = _covering_local_patch_id(
        scene,
        surface_point,
        local_refinement_requests or (),
        local_refinement_patches or (),
    )
    if patch_id:
        motion_policy["status"] = "free_sensor_motion_with_local_patch"
        motion_policy["active_local_patch_id"] = patch_id

    result = {
        "origin": [round(value, 6) for value in origin],
        "look_at": [round(value, 6) for value in focus_point],
        "up": [round(value, 6) for value in up],
        "forward_world": [round(value, 6) for value in forward],
        "right_world": [round(value, 6) for value in right],
        "up_world": [round(value, 6) for value in up],
        "fov_degrees": float(camera_pose.get("fov_degrees", fov_degrees)),
        "sensor_band_mode": sensor_band_mode,
        "sensor_band_blend_factor": max(
            0.0,
            min(1.0, float(request.get("sensor_band_blend_factor", 1.0) or 0.0)),
        ),
        "coordinate_mode": str(camera_pose.get("coordinate_mode") or "macro_world"),
        "motion_policy": motion_policy,
    }
    if target_locked_motion and motion_action in {"forward", "back", "orbit_left", "orbit_right"}:
        result["target_lock"] = "planet_center"
    if motion_policy.get("active_local_patch_id"):
        result["coordinate_mode"] = "local_patch"
        result["active_local_patch_id"] = motion_policy["active_local_patch_id"]
        result["local_origin_world"] = result["origin"]
        result["local_surface_point_world"] = [round(value, 6) for value in _surface_point_from_origin(scene, origin)]
    return result


def _camera_basis(camera_pose: Mapping[str, Any]) -> tuple[tuple[float, float, float], list[float], list[float], list[float], float]:
    origin = _finite_vec3(camera_pose.get("origin") or camera_pose.get("position") or [0.0, -18.0, 5.0], name="camera_pose.origin")
    up_hint = _vec_norm(_finite_vec3(camera_pose.get("up") or [0.0, 0.0, 1.0], name="camera_pose.up"))
    if camera_pose.get("forward_world") is not None:
        forward = _vec_norm(_finite_vec3(camera_pose.get("forward_world"), name="camera_pose.forward_world"))
        right_hint_value = camera_pose.get("right_world")
        if right_hint_value is not None:
            right_hint = _vec_norm(_finite_vec3(right_hint_value, name="camera_pose.right_world"))
            right_rejected = _vec_sub(right_hint, _vec_scale(forward, _vec_dot(right_hint, forward)))
            right = _vec_norm(right_rejected) if _vec_dot(right_rejected, right_rejected) > 1e-10 else _vec_norm(_vec_cross(forward, up_hint))
        else:
            right = _vec_norm(_vec_cross(forward, up_hint))
    else:
        look_at = _finite_vec3(camera_pose.get("look_at") or [0.0, 0.0, 0.0], name="camera_pose.look_at")
        forward = _vec_norm(_vec_sub(look_at, origin))
        right = _vec_norm(_vec_cross(forward, up_hint))
    up = _vec_norm(_vec_cross(right, forward))
    fov = float(camera_pose.get("fov_degrees", 50.0))
    if not math.isfinite(fov) or fov <= 5.0 or fov >= 160.0:
        raise ValueError("camera_pose.fov_degrees outside bounds")
    return origin, forward, right, up, fov


def build_observer_state_record(
    scene: SolarEarthSceneState,
    observer_id: str,
    camera_pose: Mapping[str, Any],
    camera_action: Mapping[str, Any] | None = None,
) -> ObserverStateRecord:
    action = dict(camera_action or {"action": "none"})
    origin, forward, _right, up, fov = _camera_basis(camera_pose)
    look_at = _finite_vec3(camera_pose.get("look_at") or scene.planet_center_world, name="camera_pose.look_at")
    sensor_band_mode = str(camera_pose.get("sensor_band_mode") or action.get("sensor_band_mode") or "visible_surface")
    if sensor_band_mode not in ALLOWED_SOLAR_EARTH_SENSOR_BAND_MODES:
        raise ValueError("unsupported solar earth sensor_band_mode")
    intended = _observer_motion_vector(
        origin,
        look_at,
        up,
        str(action.get("action") or "none"),
        float(action.get("step_world") or 0.0),
    )
    source_ids = tuple(
        dict.fromkeys(
            [
                scene.planet_macro_authority.record_id,
                scene.surface_field.record_id if scene.surface_field else "",
                str(action.get("request_id") or ""),
            ]
        )
    )
    payload = {
        "observer_id": str(observer_id),
        "tick": scene.tick,
        "origin": [round(value, 6) for value in origin],
        "look_at": [round(value, 6) for value in look_at],
        "sensor_band_mode": sensor_band_mode,
        "intended_motion_world": list(intended),
        "source_record_ids": [value for value in source_ids if value],
    }
    return ObserverStateRecord(
        record_id=_record_id_digest("observer-state", payload),
        schema="observer_state_v1",
        observer_id=str(observer_id),
        tick=int(scene.tick),
        origin_world=origin,
        look_at_world=look_at,
        forward_world=tuple(float(value) for value in forward),  # type: ignore[arg-type]
        up_world=tuple(float(value) for value in up),  # type: ignore[arg-type]
        fov_degrees=float(fov),
        sensor_band_mode=sensor_band_mode,
        intended_motion_world=intended,
        source_record_ids=tuple(value for value in source_ids if value),
    )


def _penetration_depth_for_sensor_band(scene: SolarEarthSceneState, sensor_band_mode: str) -> float:
    if sensor_band_mode not in ALLOWED_SOLAR_EARTH_SENSOR_BAND_MODES:
        raise ValueError("unsupported solar earth sensor_band_mode")
    return {
        "visible_surface": 0.0,
        "near_ir_penetrating": scene.planet_radius_world * 0.18,
        "thermal_internal": scene.planet_radius_world * 1.0,
    }[sensor_band_mode]


def _planet_layers_for_penetration(
    scene: SolarEarthSceneState,
    penetration_depth_world: float,
) -> tuple[PlanetLayerShellRecord, ...]:
    min_radius = max(0.0, scene.planet_radius_world - max(0.0, float(penetration_depth_world)))
    return tuple(
        layer
        for layer in scene.layer_shells
        if layer.outer_radius_world >= min_radius and layer.inner_radius_world <= scene.planet_radius_world
    )


def _spectral_band_key_for_sensor_mode(sensor_band_mode: str) -> str:
    if sensor_band_mode == "near_ir_penetrating":
        return "near_ir"
    if sensor_band_mode == "thermal_internal":
        return "near_ir"
    return "green"


def _ray_sphere_path_length(
    *,
    origin: Sequence[float],
    direction: Sequence[float],
    center: Sequence[float],
    radius: float,
) -> float:
    oc = _vec_sub(origin, center)
    b = 2.0 * _vec_dot(oc, direction)
    c = _vec_dot(oc, oc) - float(radius) * float(radius)
    discriminant = b * b - 4.0 * c
    if discriminant < 0.0:
        return 0.0
    sqrt_d = math.sqrt(discriminant)
    t0 = (-b - sqrt_d) / 2.0
    t1 = (-b + sqrt_d) / 2.0
    if t1 <= 0.0:
        return 0.0
    return max(0.0, t1 - max(0.0, t0))


def trace_planet_volume_observation(
    scene: SolarEarthSceneState,
    observer_state: ObserverStateRecord,
) -> PlanetVolumeRayObservationRecord:
    penetration_depth = _penetration_depth_for_sensor_band(scene, observer_state.sensor_band_mode)
    path_length = _ray_sphere_path_length(
        origin=observer_state.origin_world,
        direction=observer_state.forward_world,
        center=scene.planet_center_world,
        radius=scene.planet_radius_world,
    )
    sample_depth = min(max(0.0, path_length), penetration_depth)
    if observer_state.sensor_band_mode == "visible_surface":
        sample_depth = 0.0
    if path_length <= 0.0:
        traversed_layers = ()
    else:
        traversed_layers = _planet_layers_for_penetration(scene, sample_depth)
    layer_ids = tuple(layer.record_id for layer in traversed_layers)
    spectral_band = _spectral_band_key_for_sensor_mode(observer_state.sensor_band_mode)
    attenuation = 1.0
    weighted_emission = 0.0
    weight_total = 0.0
    for layer in traversed_layers:
        shell_width = max(0.0, layer.outer_radius_world - layer.inner_radius_world)
        overlap_weight = shell_width / max(1e-9, scene.planet_radius_world)
        absorption = max(0.0, float(layer.absorption_by_band.get(spectral_band, 0.0)))
        attenuation *= math.exp(-absorption * overlap_weight)
        weighted_emission += max(0.0, float(layer.thermal_response)) * overlap_weight
        weight_total += overlap_weight
    dominant_layer = None
    if traversed_layers:
        dominant_layer = max(traversed_layers, key=lambda layer: float(layer.thermal_response)).record_id
    if path_length <= 0.0:
        occlusion_status = "outside_macro_body"
    elif observer_state.sensor_band_mode == "visible_surface":
        occlusion_status = "surface_blocked"
    else:
        occlusion_status = "penetrating_observation"
    emission_response = weighted_emission / max(1e-9, weight_total)
    payload = {
        "observer_state_id": observer_state.record_id,
        "sensor_band_mode": observer_state.sensor_band_mode,
        "sample_depth_world": round(sample_depth, 6),
        "layer_ids": layer_ids,
        "occlusion_status": occlusion_status,
    }
    return PlanetVolumeRayObservationRecord(
        record_id=_record_id_digest("planet-volume-ray-observation", payload),
        schema="planet_volume_ray_observation_v1",
        observer_state_id=observer_state.record_id,
        sensor_band_mode=observer_state.sensor_band_mode,
        ray_origin_world=tuple(round(float(value), 6) for value in observer_state.origin_world),  # type: ignore[arg-type]
        ray_direction_world=tuple(round(float(value), 6) for value in observer_state.forward_world),  # type: ignore[arg-type]
        sample_depth_world=round(sample_depth, 6),
        traversed_layer_ids=layer_ids,
        dominant_layer_id=dominant_layer,
        attenuation=round(max(0.0, min(1.0, attenuation)), 6),
        emission_response=round(emission_response, 6),
        occlusion_status=occlusion_status,
        source_record_ids=tuple(
            dict.fromkeys(
                [
                    observer_state.record_id,
                    scene.planet_macro_authority.record_id,
                    scene.surface_field.record_id if scene.surface_field else "",
                    *layer_ids,
                ]
            )
        ),
    )


def query_sensor_material_response(
    scene: SolarEarthSceneState,
    observer_state: ObserverStateRecord,
) -> SensorMaterialQueryRecord:
    band = observer_state.sensor_band_mode
    penetration_depth = _penetration_depth_for_sensor_band(scene, band)
    layer_ids = tuple(layer.record_id for layer in _planet_layers_for_penetration(scene, penetration_depth))
    observer_distance = _distance(observer_state.origin_world, scene.planet_center_world)
    traversal_allowed = band == "visible_surface" and observer_distance > scene.planet_radius_world + 1e-6
    payload = {
        "observer_state_id": observer_state.record_id,
        "sensor_band_mode": band,
        "penetration_depth_world": round(penetration_depth, 6),
        "material_layer_ids": layer_ids,
    }
    return SensorMaterialQueryRecord(
        record_id=_record_id_digest("sensor-material-query", payload),
        schema="sensor_material_query_v1",
        observer_state_id=observer_state.record_id,
        sensor_band_mode=band,
        observation_allowed=True,
        traversal_allowed=bool(traversal_allowed),
        penetration_depth_world=round(penetration_depth, 6),
        material_layer_ids=layer_ids,
        source_record_ids=tuple(dict.fromkeys([observer_state.record_id, scene.planet_macro_authority.record_id, *layer_ids])),
    )


def compute_refinement_demand(
    scene: SolarEarthSceneState,
    observer_state: ObserverStateRecord,
) -> RefinementDemandRecord:
    distance = _distance(observer_state.origin_world, scene.planet_center_world)
    altitude = max(0.0, distance - scene.planet_radius_world)
    macro_error = _macro_error_bound_world(scene)
    sensor_samples = 64.0
    footprint = max(
        1e-5,
        2.0 * max(distance, scene.planet_radius_world) * math.tan(math.radians(observer_state.fov_degrees) / 2.0) / sensor_samples,
    )
    footprint_weight = 1.0 - _smoothstep(macro_error * 1.15, macro_error * 9.0, footprint)
    prewarm_band = max(scene.planet_radius_world * 0.06, macro_error * 7.0)
    prewarm_weight = 1.0 - _smoothstep(0.0, prewarm_band, altitude)
    motion_toward_surface = _vec_dot(observer_state.intended_motion_world, _vec_norm(_vec_sub(scene.planet_center_world, observer_state.origin_world)))
    motion_weight = max(0.0, min(1.0, motion_toward_surface / max(1e-9, prewarm_band)))
    refinement_weight = max(0.0, min(1.0, max(footprint_weight, prewarm_weight * 0.82, motion_weight * 0.55)))
    reason_codes: list[str] = []
    if footprint <= macro_error * 2.0:
        reason_codes.append("footprint_below_macro_error")
    if prewarm_weight > 0.0:
        reason_codes.append("boundary_prewarm_band")
    if motion_weight > 0.0:
        reason_codes.append("observer_motion_toward_macro_boundary")
    if not reason_codes:
        reason_codes.append("macro_projection_sufficient")
    required_patch_radius = max(macro_error * 2.0, footprint * 2.2, scene.planet_radius_world * 0.03)
    required_patch_radius = min(scene.planet_radius_world * 0.28, required_patch_radius)
    resolution_edge = 12 + int(round(refinement_weight * 20))
    payload = {
        "observer_state_id": observer_state.record_id,
        "tick": scene.tick,
        "footprint": round(footprint, 6),
        "macro_error": round(macro_error, 6),
        "refinement_weight": round(refinement_weight, 6),
        "reasons": reason_codes,
    }
    return RefinementDemandRecord(
        record_id=_record_id_digest("refinement-demand", payload),
        schema="refinement_demand_v1",
        observer_state_id=observer_state.record_id,
        refinement_weight=round(refinement_weight, 6),
        prewarm_weight=round(prewarm_weight, 6),
        projected_footprint_world=round(footprint, 6),
        macro_error_bound_world=round(macro_error, 6),
        boundary_distance_world=round(altitude, 6),
        required_patch_radius_world=round(required_patch_radius, 6),
        required_resolution=(resolution_edge, resolution_edge, max(4, resolution_edge // 3)),
        reason_codes=tuple(reason_codes),
        source_record_ids=tuple(dict.fromkeys([observer_state.record_id, scene.planet_macro_authority.record_id])),
    )


def compute_volume_refinement_demand(
    scene: SolarEarthSceneState,
    observer_state: ObserverStateRecord,
    volume_observation: PlanetVolumeRayObservationRecord,
) -> VolumeRefinementDemandRecord:
    macro_error = _macro_error_bound_world(scene)
    target_depth = max(0.0, float(volume_observation.sample_depth_world))
    penetrating = volume_observation.occlusion_status == "penetrating_observation"
    depth_weight = min(1.0, target_depth / max(1e-9, scene.planet_radius_world * 0.5))
    layer_weight = min(1.0, len(volume_observation.traversed_layer_ids) / 5.0)
    refinement_weight = 0.0
    reason_codes: list[str] = ["macro_volume_summary_sufficient"]
    if penetrating:
        refinement_weight = max(0.34, min(1.0, 0.45 + depth_weight * 0.35 + layer_weight * 0.20))
        reason_codes = ["penetrating_sensor_band_requires_volume_authority"]
        if target_depth >= scene.planet_radius_world * 0.5:
            reason_codes.append("deep_layer_lineage_required")
    elif volume_observation.occlusion_status == "surface_blocked":
        reason_codes = ["visible_band_surface_occlusion"]
    required_radius = max(macro_error * 3.0, scene.planet_radius_world * (0.04 + 0.16 * refinement_weight))
    resolution_edge = 10 + int(round(refinement_weight * 22))
    payload = {
        "observer_state_id": observer_state.record_id,
        "volume_ray_observation_id": volume_observation.record_id,
        "target_depth": round(target_depth, 6),
        "refinement_weight": round(refinement_weight, 6),
        "reasons": reason_codes,
    }
    return VolumeRefinementDemandRecord(
        record_id=_record_id_digest("volume-refinement-demand", payload),
        schema="volume_refinement_demand_v1",
        observer_state_id=observer_state.record_id,
        volume_ray_observation_id=volume_observation.record_id,
        refinement_weight=round(refinement_weight, 6),
        target_depth_world=round(target_depth, 6),
        required_volume_radius_world=round(required_radius, 6),
        required_resolution=(resolution_edge, resolution_edge, max(6, resolution_edge // 2)),
        reason_codes=tuple(reason_codes),
        source_record_ids=tuple(
            dict.fromkeys(
                [
                    observer_state.record_id,
                    volume_observation.record_id,
                    scene.planet_macro_authority.record_id,
                    *volume_observation.traversed_layer_ids,
                ]
            )
        ),
    )


def _multiscale_projection_contribution(
    scene: SolarEarthSceneState,
    *,
    observer_id: str,
    camera_pose: Mapping[str, Any],
    camera_pose_id: str,
    surface_strength: float,
    apparent_planet_radius: float,
    local_refinement_requests: Sequence[Any] | None = None,
    local_refinement_patches: Sequence[Any] | None = None,
) -> dict[str, Any]:
    observer = build_observer_state_record(
        scene,
        observer_id,
        camera_pose,
        {
            "action": "none",
            "step_world": 0.0,
            "request_id": camera_pose_id,
            "sensor_band_mode": camera_pose.get("sensor_band_mode") or "visible_surface",
        },
    )
    demand = compute_refinement_demand(scene, observer)
    coordinate_mode = str(camera_pose.get("coordinate_mode") or "macro_world")
    active_patch_id = str(camera_pose.get("active_local_patch_id") or "")
    local_patch_weight = 0.0
    source_patch_ids: list[str] = []
    source_request_ids: list[str] = []
    if coordinate_mode == "local_patch" and active_patch_id:
        patch_ids = {str(_record_get(patch, "patch_id", "")) for patch in (local_refinement_patches or ())}
        if active_patch_id in patch_ids:
            blend_factor = max(0.0, min(1.0, float(camera_pose.get("local_patch_blend_factor", 1.0) or 0.0)))
            local_patch_weight = max(0.18, min(0.62, demand.refinement_weight * 0.55 + 0.18)) * blend_factor
            source_patch_ids.append(active_patch_id)
            for patch in local_refinement_patches or ():
                if str(_record_get(patch, "patch_id", "")) == active_patch_id:
                    source_request_ids.append(str(_record_get(patch, "request_id", "")))
                    break
    surface_weight = max(0.0, min(0.74, float(surface_strength) * 0.72 + demand.refinement_weight * 0.18))
    macro_weight = max(0.08, 1.0 - surface_weight - local_patch_weight)
    total = macro_weight + surface_weight + local_patch_weight
    macro_weight /= total
    surface_weight /= total
    local_patch_weight /= total
    source_ids = list(
        dict.fromkeys(
            [
                scene.planet_macro_authority.record_id,
                scene.surface_field.record_id if scene.surface_field else "",
                observer.record_id,
                demand.record_id,
                *source_request_ids,
                *source_patch_ids,
            ]
        )
    )
    payload = {
        "tick": scene.tick,
        "observer": observer_id,
        "camera_pose_id": camera_pose_id,
        "macro": round(macro_weight, 6),
        "surface": round(surface_weight, 6),
        "local": round(local_patch_weight, 6),
        "coordinate_mode": coordinate_mode,
        "active_patch_id": active_patch_id,
        "local_patch_blend_factor": round(float(camera_pose.get("local_patch_blend_factor", 1.0) or 0.0), 6),
    }
    return {
        "schema": "multiscale_projection_contribution_v1",
        "contribution_id": _record_id_digest("multiscale-projection-contribution", payload),
        "observer_state_id": observer.record_id,
        "refinement_demand_id": demand.record_id,
        "macro_weight": round(macro_weight, 6),
        "surface_weight": round(surface_weight, 6),
        "local_patch_weight": round(local_patch_weight, 6),
        "weight_sum": round(macro_weight + surface_weight + local_patch_weight, 6),
        "coordinate_mode": coordinate_mode,
        "local_patch_blend_factor": round(float(camera_pose.get("local_patch_blend_factor", 1.0) or 0.0), 6),
        "apparent_planet_radius": round(float(apparent_planet_radius), 6),
        "projected_footprint_world": demand.projected_footprint_world,
        "macro_error_bound_world": demand.macro_error_bound_world,
        "local_patch_id": active_patch_id or None,
        "local_refinement_request_ids": [value for value in source_request_ids if value],
        "local_refinement_patch_ids": [value for value in source_patch_ids if value],
        "source_record_ids": [value for value in source_ids if value],
        "is_authority_state": False,
    }


def _project_world_to_image(
    point: Sequence[float],
    *,
    origin: Sequence[float],
    forward: Sequence[float],
    right: Sequence[float],
    up: Sequence[float],
    fov_degrees: float,
    aspect: float,
) -> tuple[float, float, float] | None:
    rel = _vec_sub(point, origin)
    depth = _vec_dot(rel, forward)
    if depth <= 1e-6:
        return None
    tan_y = math.tan(math.radians(fov_degrees) / 2.0)
    x = _vec_dot(rel, right) / max(1e-9, depth * tan_y * aspect)
    y = -_vec_dot(rel, up) / max(1e-9, depth * tan_y)
    return x, y, depth


def _surface_tangent_axes(surface_normal: Sequence[float], forward: Sequence[float]) -> tuple[list[float], list[float]]:
    tangent_forward = _vec_sub(forward, _vec_scale(surface_normal, _vec_dot(forward, surface_normal)))
    if _vec_dot(tangent_forward, tangent_forward) <= 1e-10:
        tangent_forward = _vec_cross([0.0, 0.0, 1.0], surface_normal)
    if _vec_dot(tangent_forward, tangent_forward) <= 1e-10:
        tangent_forward = [0.0, 1.0, 0.0]
    tangent_forward = _vec_norm(tangent_forward)
    tangent_right = _vec_cross(tangent_forward, surface_normal)
    if _vec_dot(tangent_right, tangent_right) <= 1e-10:
        tangent_right = _vec_cross([1.0, 0.0, 0.0], surface_normal)
    return _vec_norm(tangent_right), tangent_forward


def _observer_resolved_surface_image_plane(
    scene: SolarEarthSceneState,
    *,
    observer_id: str,
    image_shape: tuple[int, int],
    camera_pose: Mapping[str, Any],
    camera_pose_id: str,
    camera_pose_digest: str,
    origin: Sequence[float],
    forward: Sequence[float],
    apparent_planet_radius: float,
    local_refinement_requests: Sequence[Any] | None = None,
    local_refinement_patches: Sequence[Any] | None = None,
) -> dict[str, Any]:
    width, height = image_shape
    raw = bytearray()
    phase = scene.tick * 0.07
    source_surface_field_id = scene.surface_field.record_id if scene.surface_field else ""
    detail_layer_ids = [
        layer.record_id
        for layer in scene.layer_shells
        if layer.layer_kind in {"crust", "ocean", "atmosphere"}
    ]
    camera_distance = _distance(origin, scene.planet_center_world)
    altitude = max(0.0, camera_distance - scene.planet_radius_world)
    sensor_band_mode = str(camera_pose.get("sensor_band_mode") or "visible_surface")
    if sensor_band_mode not in ALLOWED_SOLAR_EARTH_SENSOR_BAND_MODES:
        raise ValueError("unsupported solar earth sensor_band_mode")
    penetration_depth = {
        "visible_surface": 0.0,
        "near_ir_penetrating": scene.planet_radius_world * 0.18,
        "thermal_internal": scene.planet_radius_world * 1.0,
    }[sensor_band_mode]
    min_sample_radius = scene.planet_radius_world - penetration_depth
    penetrated_layers = [
        layer
        for layer in scene.layer_shells
        if layer.outer_radius_world >= min_sample_radius and layer.inner_radius_world <= scene.planet_radius_world
    ]
    if not penetrated_layers:
        penetrated_layers = [layer for layer in scene.layer_shells if layer.layer_kind in {"crust", "ocean", "atmosphere"}]
    subsurface_heat = max((layer.thermal_response for layer in penetrated_layers), default=0.0)
    surface_normal = _vec_norm(_vec_sub(origin, scene.planet_center_world))
    tangent_right, tangent_forward = _surface_tangent_axes(surface_normal, forward)
    surface_point = _vec_add(scene.planet_center_world, _vec_scale(surface_normal, scene.planet_radius_world))
    sun_dir = _vec_norm(_vec_sub(scene.solar_source.center_world, surface_point))
    sun_above_surface = max(0.0, _vec_dot(surface_normal, sun_dir))
    sky_response = {"violet": 0.26, "blue": 0.70, "green": 0.18}
    sky_rgb = compose_visible_rgb(scene.spectral_profile, sky_response)
    region_counts: dict[str, int] = {}
    sample_record_ids: list[str] = []
    surface_lod_blend = max(0.0, min(1.0, (float(apparent_planet_radius) - 0.84) / 0.42))
    horizon_y = -0.42 + min(0.18, altitude / max(1e-9, scene.planet_radius_world) * 0.12)
    footprint_span = max(0.08, min(0.52, 0.16 + altitude * 0.34))

    for y in range(height):
        ny = (y / max(1, height - 1)) * 2.0 - 1.0
        for x in range(width):
            nx = (x / max(1, width - 1)) * 2.0 - 1.0
            if ny < horizon_y:
                sky_depth = (horizon_y - ny) / max(1e-6, horizon_y + 1.0)
                horizon_glow = max(0.0, 1.0 - abs(ny - horizon_y) / 0.20)
                sun_glow = max(0.0, 1.0 - math.sqrt((nx - 0.46) ** 2 + (ny + 0.64) ** 2) / 0.22) ** 2
                r = 8 + int(sky_rgb[0] * (38 + 45 * sun_above_surface) * (0.65 + 0.35 * sky_depth)) + int(horizon_glow * 30) + int(sun_glow * 120)
                g = 14 + int(sky_rgb[1] * (58 + 60 * sun_above_surface) * (0.65 + 0.35 * sky_depth)) + int(horizon_glow * 45) + int(sun_glow * 115)
                b = 24 + int(sky_rgb[2] * (82 + 80 * sun_above_surface) * (0.65 + 0.35 * sky_depth)) + int(horizon_glow * 80) + int(sun_glow * 95)
                raw.extend([min(255, r), min(255, g), min(255, b), 255])
                continue

            ground_depth = (ny - horizon_y) / max(1e-6, 1.0 - horizon_y)
            lateral = nx * footprint_span * (0.55 + ground_depth * 0.65)
            forward_offset = ground_depth * footprint_span * 1.45
            sample_normal = _vec_norm(
                _vec_add(
                    _vec_add(surface_normal, _vec_scale(tangent_right, lateral)),
                    _vec_scale(tangent_forward, forward_offset),
                )
            )
            pyramid = sample_planet_surface_frequency_pyramid(
                scene.surface_field,
                u=(math.atan2(sample_normal[1], sample_normal[0]) / math.tau) % 1.0,
                v=(math.asin(max(-1.0, min(1.0, sample_normal[2]))) / math.pi) + 0.5,
                footprint_span_world=footprint_span / max(1.0, height),
            )
            sample = sample_planet_surface_spectral_field(scene.surface_field, unit_normal=sample_normal, tick=scene.tick)
            region_counts[sample.region_kind] = region_counts.get(sample.region_kind, 0) + 1
            if sample.record_id not in sample_record_ids and len(sample_record_ids) < 96:
                sample_record_ids.append(sample.record_id)
            rgb = compose_visible_rgb(scene.spectral_profile, pyramid["composite_spectral_response"])
            light = max(0.10, _vec_dot(sample_normal, sun_dir))
            fine_wave = 0.5 + 0.5 * math.sin((nx * 17.0) + (ground_depth * 21.0) + phase)
            terrain_shade = 0.72 + 0.22 * fine_wave + 0.14 * (1.0 - ground_depth)
            haze = max(0.0, ground_depth - 0.70) / 0.30
            penetration_mix = min(1.0, penetration_depth / max(1e-9, scene.planet_radius_world))
            r = int(12 + rgb[0] * 190 * light * terrain_shade + haze * 20 + subsurface_heat * 70 * penetration_mix)
            g = int(14 + rgb[1] * 210 * light * terrain_shade + haze * 32 + subsurface_heat * 24 * penetration_mix)
            b = int(16 + rgb[2] * 220 * light * terrain_shade + haze * 55 - subsurface_heat * 34 * penetration_mix)
            raw.extend([max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)), 255])

    sample_summary_payload = {
        "source_surface_field_id": source_surface_field_id,
        "tick": scene.tick,
        "sample_count": sum(region_counts.values()),
        "region_counts": region_counts,
        "sample_record_ids": sample_record_ids,
        "surface_view": True,
        "camera_pose_digest": camera_pose_digest,
        "sensor_band_mode": sensor_band_mode,
        "penetrated_layer_ids": [layer.record_id for layer in penetrated_layers],
    }
    sample_summary_id = _record_id_digest("planet-surface-spectral-sample-summary", sample_summary_payload)
    contribution = _multiscale_projection_contribution(
        scene,
        observer_id=observer_id,
        camera_pose=camera_pose,
        camera_pose_id=camera_pose_id,
        surface_strength=surface_lod_blend,
        apparent_planet_radius=apparent_planet_radius,
        local_refinement_requests=local_refinement_requests,
        local_refinement_patches=local_refinement_patches,
    )
    volume_observer = build_observer_state_record(
        scene,
        observer_id,
        camera_pose,
        {
            "action": "none",
            "step_world": 0.0,
            "request_id": camera_pose_id,
            "sensor_band_mode": sensor_band_mode,
        },
    )
    volume_observation = trace_planet_volume_observation(scene, volume_observer)
    volume_demand = compute_volume_refinement_demand(scene, volume_observer, volume_observation)
    image_plane = {
        "schema": "spectral_image_plane_v1",
        "image_plane_id": f"spectral-image-plane::solar-earth-surface::{scene.template_binding.source_package_name}::{scene.tick}::{camera_pose_digest.split(':', 1)[1][:12]}",
        "image_shape": [width, height],
        "color_source": "spectral_band_response",
        "source_record_ids": _unique_record_ids([
            scene.solar_source.record_id,
            scene.spectral_profile.profile_id,
            scene.planet_macro_authority.record_id,
            camera_pose_id,
            contribution["contribution_id"],
            source_surface_field_id,
            *detail_layer_ids,
            *[layer.record_id for layer in penetrated_layers],
            *sample_record_ids,
            *contribution["source_record_ids"],
        ]),
        "is_authority_state": False,
        "planet_surface_spectral_sample_summary": {
            "schema": "planet_surface_spectral_sample_summary_v1",
            "summary_id": sample_summary_id,
            "source_surface_field_id": source_surface_field_id,
            "sample_count": sum(region_counts.values()),
            "sample_record_ids": sample_record_ids,
            "region_counts": region_counts,
            "is_authority_state": False,
        },
        "multiscale_projection_contribution": contribution,
        "camera_projection": {
            "schema": "solar_earth_camera_projection_v1",
            "camera_pose_id": camera_pose_id,
            "planet_screen_center": [0.0, 0.0],
            "planet_screen_radius": round(float(apparent_planet_radius), 6),
            "camera_distance_to_planet": round(camera_distance, 6),
            "surface_detail": {
                "mode": "observer_resolved_surface_sampling",
                "lod_basis": "apparent_planet_radius_exceeds_image_plane",
                "strength": round(surface_lod_blend, 6),
                "apparent_planet_radius": round(float(apparent_planet_radius), 6),
                "surface_lod_blend": round(surface_lod_blend, 6),
                "footprint_span_world": round(footprint_span, 6),
                "source_surface_field_id": source_surface_field_id,
                "sample_summary_id": sample_summary_id,
                "source_layer_shell_ids": detail_layer_ids,
                "sensor_band_mode": sensor_band_mode,
                "penetration_depth_world": round(penetration_depth, 6),
                "penetrated_layer_ids": [layer.record_id for layer in penetrated_layers],
                "altitude_world": round(altitude, 6),
                "horizon_y": round(horizon_y, 6),
                "coordinate_mode": str(camera_pose.get("coordinate_mode") or "macro_world"),
                "active_local_patch_id": camera_pose.get("active_local_patch_id"),
                "derivation": "camera footprint samples planet surface spectral field",
            },
        },
        "tiles": [
            {
                "schema": "spectral_image_tile_v1",
                "tile_xy": [0, 0],
                "tile_shape": [width, height],
                "rgba8_rle_base64": _encode_rle_rgba(bytes(raw)),
            }
        ],
    }
    return _attach_continuous_earth_slice_contracts(
        image_plane,
        scene,
        observer_id=observer_id,
        camera_pose=camera_pose,
        camera_pose_id=camera_pose_id,
        image_shape=image_shape,
        origin=origin,
        forward=forward,
        apparent_planet_radius=apparent_planet_radius,
        surface_lod_blend=surface_lod_blend,
        volume_observation=volume_observation,
        volume_demand=volume_demand,
        frame_kind="world_step" if scene.tick > 0 else "camera_only",
    )


def _spectral_image_plane(
    scene: SolarEarthSceneState,
    image_shape: tuple[int, int] = (96, 64),
    *,
    observer_id: str,
    camera_pose: Mapping[str, Any] | None = None,
    local_refinement_requests: Sequence[Any] | None = None,
    local_refinement_patches: Sequence[Any] | None = None,
) -> dict[str, Any]:
    width, height = image_shape
    camera_pose = dict(camera_pose or default_solar_earth_camera_pose(scene))
    camera_pose_digest = _canonical_digest(camera_pose)
    camera_pose_id = f"solar-earth-camera-pose::{camera_pose_digest.split(':', 1)[1][:16]}"
    origin, forward, right, up, fov_degrees = _camera_basis(camera_pose)
    aspect = width / max(1.0, float(height))
    star_projected = _project_world_to_image(
        scene.solar_source.center_world,
        origin=origin,
        forward=forward,
        right=right,
        up=up,
        fov_degrees=fov_degrees,
        aspect=aspect,
    )
    planet_projected = _project_world_to_image(
        scene.planet_center_world,
        origin=origin,
        forward=forward,
        right=right,
        up=up,
        fov_degrees=fov_degrees,
        aspect=aspect,
    )
    star_rgb = compose_visible_rgb(scene.spectral_profile, scene.solar_source.spectral_power_by_band)
    planet_rgb = compose_visible_rgb(
        scene.spectral_profile,
        {
            "violet": 0.08,
            "blue": 0.26,
            "green": 0.34,
            "yellow": 0.18,
            "red": 0.10,
            "near_ir": 0.14,
        },
    )
    raw = bytearray()
    phase = scene.tick * 0.11
    tan_y = math.tan(math.radians(fov_degrees) / 2.0)
    if star_projected:
        star_x, star_y, star_depth = star_projected
        star_radius_x = max(0.04, min(0.70, scene.solar_source.radius_world / max(1e-6, star_depth * tan_y * aspect)))
        star_radius_y = max(0.04, min(0.70, scene.solar_source.radius_world / max(1e-6, star_depth * tan_y)))
    else:
        star_x, star_y, star_radius_x, star_radius_y = 99.0, 99.0, 0.05, 0.05
    if planet_projected:
        planet_x, planet_y, planet_depth = planet_projected
        planet_radius_x_raw = scene.planet_radius_world / max(1e-6, planet_depth * tan_y * aspect)
        planet_radius_y_raw = scene.planet_radius_world / max(1e-6, planet_depth * tan_y)
        apparent_planet_radius = max(planet_radius_x_raw, planet_radius_y_raw)
        planet_radius_x = max(0.03, min(3.0, planet_radius_x_raw))
        planet_radius_y = max(0.03, min(3.0, planet_radius_y_raw))
    else:
        planet_x, planet_y, planet_radius_x, planet_radius_y = 99.0, 99.0, 0.05, 0.05
        apparent_planet_radius = 0.05
    planet_screen_radius = max(planet_radius_x, planet_radius_y)
    surface_view_threshold = 2.08
    surface_transition_blend = _smoothstep(0.92, surface_view_threshold, apparent_planet_radius)
    surface_detail_strength = max(0.0, min(1.0, (planet_screen_radius - 0.18) / 0.36))
    if apparent_planet_radius >= 0.72 and width < 384:
        target_width, target_height = 384, 256
        max_adaptive_shape = _optional_image_shape(camera_pose.get("max_adaptive_image_shape"))
        if max_adaptive_shape is not None:
            target_width = max(width, min(target_width, max_adaptive_shape[0]))
            target_height = max(height, min(target_height, max_adaptive_shape[1]))
        width, height = target_width, target_height
        image_shape = (width, height)
    if surface_transition_blend > 0.05:
        surface_detail_mode = "macro_surface_continuous_close_projection"
    else:
        surface_detail_mode = "macro_surface_spectral_heterogeneity" if surface_detail_strength > 0.05 else "orbital_disc"
    detail_layer_ids = [
        layer.record_id
        for layer in scene.layer_shells
        if layer.layer_kind in {"crust", "ocean", "atmosphere"}
    ]
    source_surface_field_id = scene.surface_field.record_id if scene.surface_field else ""
    sensor_band_mode = str(camera_pose.get("sensor_band_mode") or "visible_surface")
    if sensor_band_mode not in ALLOWED_SOLAR_EARTH_SENSOR_BAND_MODES:
        raise ValueError("unsupported solar earth sensor_band_mode")
    penetration_depth = {
        "visible_surface": 0.0,
        "near_ir_penetrating": scene.planet_radius_world * 0.18,
        "thermal_internal": scene.planet_radius_world * 1.0,
    }[sensor_band_mode]
    min_sample_radius = scene.planet_radius_world - penetration_depth
    penetrated_layers = [
        layer
        for layer in scene.layer_shells
        if layer.outer_radius_world >= min_sample_radius and layer.inner_radius_world <= scene.planet_radius_world
    ]
    if not penetrated_layers:
        penetrated_layers = [layer for layer in scene.layer_shells if layer.layer_kind in {"crust", "ocean", "atmosphere"}]
    volume_observer = build_observer_state_record(
        scene,
        observer_id,
        camera_pose,
        {
            "action": "none",
            "step_world": 0.0,
            "request_id": camera_pose_id,
            "sensor_band_mode": sensor_band_mode,
        },
    )
    volume_observation = trace_planet_volume_observation(scene, volume_observer)
    volume_demand = compute_volume_refinement_demand(scene, volume_observer, volume_observation)
    region_counts: dict[str, int] = {}
    sample_record_ids: list[str] = []
    light_x = star_x - planet_x
    light_y = star_y - planet_y
    light_len = math.sqrt(light_x * light_x + light_y * light_y) or 1.0
    light_x /= light_len
    light_y /= light_len
    for y in range(height):
        ny = (y / max(1, height - 1)) * 2.0 - 1.0
        for x in range(width):
            nx = (x / max(1, width - 1)) * 2.0 - 1.0
            star_edge = math.sqrt(((nx - star_x) / max(1e-6, star_radius_x * 2.4)) ** 2 + ((ny - star_y) / max(1e-6, star_radius_y * 2.4)) ** 2)
            star_glow = max(0.0, 1.0 - star_edge) ** 2
            planet_px = (nx - planet_x) / max(1e-6, planet_radius_x)
            planet_py = (ny - planet_y) / max(1e-6, planet_radius_y)
            planet_edge = math.sqrt(planet_px * planet_px + planet_py * planet_py)
            planet_disc = 1.0 if planet_edge < 1.0 else 0.0
            atmosphere = max(0.0, 1.0 - abs(planet_edge - 1.08) / 0.18)
            facing_light = planet_px * light_x + planet_py * light_y
            day_side = max(0.08, min(1.0, 0.35 + 0.65 * facing_light + 0.08 * math.sin(phase)))
            planet_r = planet_rgb[0] * 120.0
            planet_g = planet_rgb[1] * 150.0
            planet_b = planet_rgb[2] * 170.0
            if planet_disc and surface_detail_strength > 0.0 and scene.surface_field:
                radial_sq = planet_px * planet_px + planet_py * planet_py
                front = math.sqrt(max(0.0, 1.0 - radial_sq))
                surface_normal = _vec_norm(
                    _vec_add(
                        _vec_add(_vec_scale(right, planet_px), _vec_scale(up, -planet_py)),
                        _vec_scale(forward, -front),
                    )
                )
                sample = sample_planet_surface_spectral_field(
                    scene.surface_field,
                    unit_normal=surface_normal,
                    tick=scene.tick,
                )
                region_counts[sample.region_kind] = region_counts.get(sample.region_kind, 0) + 1
                if sample.record_id not in sample_record_ids and len(sample_record_ids) < 64:
                    sample_record_ids.append(sample.record_id)
                detail_rgb = compose_visible_rgb(scene.spectral_profile, sample.spectral_response)
                detail_r = detail_rgb[0] * 165.0
                detail_g = detail_rgb[1] * 185.0
                detail_b = detail_rgb[2] * 205.0
                planet_r = planet_r * (1.0 - surface_detail_strength) + detail_r * surface_detail_strength
                planet_g = planet_g * (1.0 - surface_detail_strength) + detail_g * surface_detail_strength
                planet_b = planet_b * (1.0 - surface_detail_strength) + detail_b * surface_detail_strength
            if planet_disc and sensor_band_mode == "thermal_internal":
                heat = max(0.0, min(1.0, float(volume_observation.emission_response)))
                attenuation_loss = 1.0 - max(0.0, min(1.0, float(volume_observation.attenuation)))
                depth_mix = min(1.0, float(volume_observation.sample_depth_world) / max(1e-9, scene.planet_radius_world))
                radial_core_signal = max(0.0, 1.0 - planet_edge) ** 0.7
                thermal_r = 72.0 + 150.0 * heat + 24.0 * radial_core_signal
                thermal_g = 34.0 + 64.0 * heat
                thermal_b = 78.0 + 112.0 * attenuation_loss + 38.0 * radial_core_signal
                false_color_mix = max(0.42, min(0.88, 0.42 + depth_mix * 0.46))
                planet_r = planet_r * (1.0 - false_color_mix) + thermal_r * false_color_mix
                planet_g = planet_g * (1.0 - false_color_mix) + thermal_g * false_color_mix
                planet_b = planet_b * (1.0 - false_color_mix) + thermal_b * false_color_mix
            elif planet_disc and sensor_band_mode == "near_ir_penetrating":
                attenuation_loss = 1.0 - max(0.0, min(1.0, float(volume_observation.attenuation)))
                near_ir_mix = 0.32
                planet_r = planet_r * (1.0 - near_ir_mix) + (36.0 + 52.0 * attenuation_loss) * near_ir_mix
                planet_g = planet_g * (1.0 - near_ir_mix) + (108.0 + 70.0 * attenuation_loss) * near_ir_mix
                planet_b = planet_b * (1.0 - near_ir_mix) + (126.0 + 36.0 * attenuation_loss) * near_ir_mix
            r = 8 + int(star_glow * star_rgb[0] * 240) + int(planet_disc * planet_r * day_side) + int(atmosphere * 50)
            g = 12 + int(star_glow * star_rgb[1] * 230) + int(planet_disc * planet_g * day_side) + int(atmosphere * 95)
            b = 18 + int(star_glow * star_rgb[2] * 210) + int(planet_disc * planet_b * day_side) + int(atmosphere * 155)
            a = 255
            raw.extend([min(255, r), min(255, g), min(255, b), a])

    sample_summary_payload = {
        "source_surface_field_id": source_surface_field_id,
        "tick": scene.tick,
        "sample_count": sum(region_counts.values()),
        "region_counts": region_counts,
        "sample_record_ids": sample_record_ids,
        "sensor_band_mode": sensor_band_mode,
        "penetrated_layer_ids": [layer.record_id for layer in penetrated_layers],
    }
    sample_summary_id = _record_id_digest("planet-surface-spectral-sample-summary", sample_summary_payload)
    contribution = _multiscale_projection_contribution(
        scene,
        observer_id=observer_id,
        camera_pose=camera_pose,
        camera_pose_id=camera_pose_id,
        surface_strength=surface_detail_strength,
        apparent_planet_radius=apparent_planet_radius,
        local_refinement_requests=local_refinement_requests,
        local_refinement_patches=local_refinement_patches,
    )
    image_plane = {
        "schema": "spectral_image_plane_v1",
        "image_plane_id": f"spectral-image-plane::solar-earth::{scene.template_binding.source_package_name}::{scene.tick}::{camera_pose_digest.split(':', 1)[1][:12]}",
        "image_shape": [width, height],
        "color_source": "spectral_band_response",
        "source_record_ids": _unique_record_ids([
            scene.solar_source.record_id,
            scene.spectral_profile.profile_id,
            scene.planet_macro_authority.record_id,
            camera_pose_id,
            contribution["contribution_id"],
            volume_observation.record_id,
            volume_demand.record_id,
            source_surface_field_id,
            *detail_layer_ids,
            *[layer.record_id for layer in penetrated_layers],
            *sample_record_ids,
            *volume_observation.source_record_ids,
            *volume_demand.source_record_ids,
            *contribution["source_record_ids"],
        ]),
        "is_authority_state": False,
        "planet_surface_spectral_sample_summary": {
            "schema": "planet_surface_spectral_sample_summary_v1",
            "summary_id": sample_summary_id,
            "source_surface_field_id": source_surface_field_id,
            "sample_count": sum(region_counts.values()),
            "sample_record_ids": sample_record_ids,
            "region_counts": region_counts,
            "is_authority_state": False,
        },
        "multiscale_projection_contribution": contribution,
        "camera_projection": {
            "schema": "solar_earth_camera_projection_v1",
            "camera_pose_id": camera_pose_id,
            "planet_screen_center": [round(planet_x, 6), round(planet_y, 6)],
            "planet_screen_radius": round(planet_screen_radius, 6),
            "camera_distance_to_planet": round(_distance(origin, scene.planet_center_world), 6),
            "surface_detail": {
                "mode": surface_detail_mode,
                "strength": round(surface_detail_strength, 6),
                "surface_lod_blend": round(surface_transition_blend, 6),
                "lod_basis": "continuous_apparent_radius_transition",
                "visual_blend": "same_camera_surface_sampling",
                "apparent_planet_radius": round(float(apparent_planet_radius), 6),
                "resolved_surface_threshold": round(surface_view_threshold, 6),
                "source_surface_field_id": source_surface_field_id,
                "sample_summary_id": sample_summary_id,
                "source_layer_shell_ids": detail_layer_ids,
                "sensor_band_mode": sensor_band_mode,
                "penetration_depth_world": round(penetration_depth, 6),
                "penetrated_layer_ids": [layer.record_id for layer in penetrated_layers],
                "volume_ray_observation_id": volume_observation.record_id,
                "volume_ray_observation": volume_observation.to_dict(),
                "volume_refinement_demand_id": volume_demand.record_id,
                "volume_refinement_demand": volume_demand.to_dict(),
                "occlusion_status": volume_observation.occlusion_status,
                "traversed_layer_ids": list(volume_observation.traversed_layer_ids),
                "dominant_layer_id": volume_observation.dominant_layer_id,
                "sample_depth_world": volume_observation.sample_depth_world,
                "attenuation": volume_observation.attenuation,
                "emission_response": volume_observation.emission_response,
                "ray_authority": "macro_volume_summary",
                "sensor_color_mapping": (
                    "false_color_from_volume_ray_emission_and_attenuation"
                    if sensor_band_mode == "thermal_internal"
                    else "false_color_from_near_ir_attenuation"
                    if sensor_band_mode == "near_ir_penetrating"
                    else "visible_rgb_from_surface_spectral_response"
                ),
                "coordinate_mode": str(camera_pose.get("coordinate_mode") or "macro_world"),
                "active_local_patch_id": camera_pose.get("active_local_patch_id"),
                "derivation": "spectral macro-surface detail sampled from planet surface spectral field",
            },
        },
        "tiles": [
            {
                "schema": "spectral_image_tile_v1",
                "tile_xy": [0, 0],
                "tile_shape": [width, height],
                "rgba8_rle_base64": _encode_rle_rgba(bytes(raw)),
            }
        ],
    }
    return _attach_continuous_earth_slice_contracts(
        image_plane,
        scene,
        observer_id=observer_id,
        camera_pose=camera_pose,
        camera_pose_id=camera_pose_id,
        image_shape=image_shape,
        origin=origin,
        forward=forward,
        apparent_planet_radius=apparent_planet_radius,
        surface_lod_blend=surface_transition_blend,
        volume_observation=volume_observation,
        volume_demand=volume_demand,
        frame_kind="world_step" if scene.tick > 0 else "camera_only",
    )


def project_solar_earth_scene(
    scene: SolarEarthSceneState,
    observer_id: str,
    *,
    camera_pose: Mapping[str, Any] | None = None,
    include_debug_bands: bool = False,
    local_refinement_requests: Sequence[Any] | None = None,
    local_refinement_patches: Sequence[Any] | None = None,
) -> ProjectionFrame:
    camera_pose = dict(camera_pose or default_solar_earth_camera_pose(scene))
    camera_pose_digest = _canonical_digest(camera_pose)
    image_plane = _spectral_image_plane(
        scene,
        observer_id=observer_id,
        camera_pose=camera_pose,
        local_refinement_requests=local_refinement_requests,
        local_refinement_patches=local_refinement_patches,
    )
    flux_ids = [record.record_id for record in scene.energy_flux_records]
    body_ids = [body.record_id for body in scene.macro_body_states]
    gravity_ids = [record.record_id for record in scene.gravity_potential_records]
    step_ids = [record.record_id for record in scene.macro_body_step_records]
    surface_ids = [scene.surface_field.record_id] if scene.surface_field else []
    image_source_ids = [str(value) for value in image_plane.get("source_record_ids", []) if value]
    refinement_source_ids = [
        str(value)
        for value in [
            *[str(_record_get(request, "request_id", "")) for request in (local_refinement_requests or [])],
            *[str(_record_get(patch, "patch_id", "")) for patch in (local_refinement_patches or [])],
        ]
        if value
    ]
    source_record_ids = tuple(
        dict.fromkeys(
            [
                *scene.source_record_ids,
                *flux_ids,
                *body_ids,
                *gravity_ids,
                *step_ids,
                *surface_ids,
                *image_source_ids,
                *refinement_source_ids,
                image_plane["image_plane_id"],
            ]
        )
    )
    authority_summary = _m13_authority_summary_payload(scene, image_plane, observer_id=observer_id)
    invariant_signature = compute_invariant_signature(
        authority_summary,
        method="support_energy_centroid_boundary_modes_v1",
        source_record_ids=authority_summary["source_record_ids"],
    )
    payload = {
        "event_timeline": {
            "tick": scene.tick,
            "event_kinds": ["solar_earth_layered_world_projection", "planet_energy_flux"],
            "interaction_record_ids": [],
            "wave_step_record_ids": flux_ids,
            "field_structure_event_ids": [],
            "source_record_ids": list(source_record_ids),
            "observer_id": observer_id,
            "is_authority_state": False,
        },
        "timeline_semantics": {
            "schema": "projection_timeline_semantics_v1",
            "frame_kind": "solar_earth_world_step_observation" if scene.tick > 0 else "initial_observation",
            "world_tick": scene.tick,
            "world_tick_window": [max(0, scene.tick - 1), scene.tick],
            "world_advanced": scene.tick > 0,
            "camera_moved": False,
            "camera_action": None,
            "camera_pose_id": f"solar-earth-camera::{observer_id}",
            "previous_camera_pose_digest": None,
            "result_camera_pose_digest": None,
            "source_world_state_id": scene.implicit_state.state["implicit_field_state_id"],
            "source_world_state_digest": scene.implicit_state.state["state_digest"],
            "source_live_step_ids": [],
            "source_camera_move_id": None,
            "source_interaction_audit_ids": [],
            "playback_track": "world_run",
            "sequence_index": scene.tick,
            "is_authority_state": False,
        },
        "spectral_image_plane": image_plane,
        "solar_earth_projection": {
            "schema": "solar_earth_projection_payload_v1",
            "visible_color_source": "spectral_band_response",
            "spectral_band_profile_id": scene.spectral_profile.profile_id,
            "solar_radiation_source_ids": [scene.solar_source.record_id],
            "planet_macro_authority_id": scene.planet_macro_authority.record_id,
            "star_center_world": list(scene.star_body_state.center_world if scene.star_body_state else scene.solar_source.center_world),
            "planet_center_world": list(scene.planet_center_world),
            "macro_body_state_ids": body_ids,
            "effective_gravity_potential_ids": gravity_ids,
            "macro_body_step_ids": step_ids,
            "surface_field_ids": surface_ids,
            "local_refinement_request_ids": [str(_record_get(request, "request_id", "")) for request in (local_refinement_requests or []) if _record_get(request, "request_id", "")],
            "local_refinement_patch_ids": [str(_record_get(patch, "patch_id", "")) for patch in (local_refinement_patches or []) if _record_get(patch, "patch_id", "")],
            "planet_layer_shell_ids": [layer.record_id for layer in scene.layer_shells],
            "energy_flux_record_ids": flux_ids,
            "camera_pose": camera_pose,
            "debug_bands_included": bool(include_debug_bands),
            "is_authority_state": False,
        },
        "m13_authority_summaries_v1": [authority_summary],
        "source_record_ids": list(source_record_ids),
    }
    frame = ProjectionFrame(
        frame_id=f"projection-frame::solar-earth::{observer_id}::{scene.tick}::{camera_pose_digest.split(':', 1)[1][:12]}",
        tick=scene.tick,
        observer_id=observer_id,
        image_plane={"schema": "projection_image_plane_v1", "width": image_plane["image_shape"][0], "height": image_plane["image_shape"][1]},
        samples=[],
        phenomena_overlays=[],
        source_state_ticks=[scene.tick],
        source_object_ids=[],
        source_record_ids=list(source_record_ids),
        is_authority_state=False,
        audit={
            "projection_semantics": "observer_projection_not_object_painting",
            "no_persistent_light_object": True,
            "no_material_asset_authority": True,
            "no_global_raindrop_authority_state": True,
            "spectral bands": "visible color is composed from explicit spectral band response",
            "solar radiation": "star source is a radiation source record, not a viewer light",
            "planet layers": "planet shell records are cited by projection lineage",
            "local refinement": "surface detail must cite refinement request and patch artifacts",
        },
        payload=payload,
    )
    loss_manifest = build_projection_loss_manifest(
        {
            "frame_id": frame.frame_id,
            "observer_id": frame.observer_id,
            "observer_resolution": {
                "image_shape": list(image_plane.get("image_shape", [])),
                "camera_scale_state_id": image_plane.get("camera_scale_state", {}).get("camera_scale_state_id", ""),
                "sensor_band": image_plane.get("camera_ray_bundle", {}).get("sensor_band", "visible_surface"),
            },
        },
        authority_record_ids=authority_summary["source_authority_record_ids"],
        projection_map_id=f"projection-map::solar-earth::{image_plane.get('image_plane_id', 'unknown')}",
        preserved_invariants=(invariant_signature.to_payload()["invariant_signature_v1"],),
        discarded_degrees_of_freedom=(
            "subpixel_phase",
            "unobserved_internal_modes",
            "sensor_band_rejected_frequencies",
            "camera_frustum_outside_samples",
        ),
        known_ambiguities=(
            {
                "kind": "observer_band_limit",
                "severity": "bounded",
                "sensor_band": image_plane.get("camera_ray_bundle", {}).get("sensor_band", "visible_surface"),
                "source_record_ids": [image_plane.get("camera_ray_bundle", {}).get("ray_bundle_id", "")],
            },
            {
                "kind": "compact_surface_summary",
                "severity": "bounded",
                "summary_record_id": authority_summary["record_id"],
                "source_record_ids": [authority_summary["record_id"]],
            },
        ),
    )
    frame = attach_projection_invariant_boundary_records_to_projection_frame(
        frame,
        projection_loss_manifest=loss_manifest,
        invariant_signatures=(invariant_signature,),
    )
    packet = _build_realtime_projection_frame_packet(
        scene,
        frame=frame,
        observer_id=observer_id,
        camera_pose=camera_pose,
        image_plane=image_plane,
        authority_summary=authority_summary,
    )
    payload = dict(frame.payload)
    timeline = dict(payload["event_timeline"])
    display_record_ids = list(dict.fromkeys([*map(str, payload.get("display_record_ids", [])), packet["packet_id"]]))
    timeline["display_record_ids"] = display_record_ids
    payload["event_timeline"] = timeline
    payload["display_record_ids"] = display_record_ids
    payload["realtime_projection_frame_packet"] = packet
    payload["renderer_display_only_not_authority"] = True
    return replace(frame, payload=payload)


def request_planet_local_refinement(
    scene: SolarEarthSceneState,
    *,
    observer_id: str,
    world_point: Sequence[float],
    trigger_kind: str,
    requested_radius_world: float,
    requested_resolution: Sequence[int],
    max_refinement_depth: int,
    request_id_override: str | None = None,
) -> PlanetLocalRefinementRequest:
    point = tuple(float(value) for value in world_point)
    if len(point) != 3:
        raise ValueError("world_point must be 3D")
    radius_from_center = _distance(point, scene.planet_center_world)
    if radius_from_center > scene.planet_radius_world + float(requested_radius_world):
        raise ValueError("outside planet envelope")
    covered = find_layers_at_radius(scene.layer_shells, radius_from_center)
    if not covered:
        raise ValueError("outside planet envelope")
    payload = {
        "observer_id": observer_id,
        "world_point": list(point),
        "trigger_kind": trigger_kind,
        "tick": scene.tick,
        "radius": float(requested_radius_world),
    }
    request_id = str(request_id_override) if request_id_override else _record_id_digest("planet-local-refinement-request", payload)
    source_ids = tuple(dict.fromkeys([scene.planet_macro_authority.record_id, *[layer.record_id for layer in covered]]))
    return PlanetLocalRefinementRequest(
        request_id=request_id,
        schema="planet_local_refinement_request_v1",
        observer_id=str(observer_id),
        trigger_kind=str(trigger_kind),
        world_point=point,  # type: ignore[arg-type]
        requested_radius_world=float(requested_radius_world),
        requested_resolution=tuple(int(value) for value in requested_resolution),  # type: ignore[arg-type]
        max_refinement_depth=int(max_refinement_depth),
        source_planet_macro_authority_ids=(scene.planet_macro_authority.record_id,),
        source_layer_shell_ids=tuple(layer.record_id for layer in covered),
        source_record_ids=source_ids,
    )


def refine_planet_local_region(
    scene: SolarEarthSceneState,
    request: PlanetLocalRefinementRequest,
) -> PlanetLocalRefinementPatch:
    if request.schema != "planet_local_refinement_request_v1":
        raise ValueError("planet local refinement request schema mismatch")
    summary = {
        "sampled_layer_count": len(request.source_layer_shell_ids),
        "requested_resolution": list(request.requested_resolution),
        "surface_energy_density": round(sum(record.output_energy_total for record in scene.energy_flux_records[-3:]) / 3.0, 8)
        if scene.energy_flux_records
        else 0.0,
        "dense_volume_used": False,
    }
    digest = _canonical_digest({"request_id": request.request_id, "summary": summary, "source_layers": request.source_layer_shell_ids})
    return PlanetLocalRefinementPatch(
        patch_id=f"planet-local-refinement-patch::{request.request_id.split('::')[-1]}",
        schema="planet_local_refinement_patch_v1",
        request_id=request.request_id,
        covered_layer_ids=request.source_layer_shell_ids,
        final_patch_digest=digest,
        patch_summary=summary,
        source_record_ids=tuple(dict.fromkeys([request.request_id, *request.source_record_ids, scene.implicit_state.state["implicit_field_state_id"]])),
    )
