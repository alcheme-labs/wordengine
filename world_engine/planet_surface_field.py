from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


SURFACE_FIELD_SCHEMA = "planet_surface_spectral_field_v1"
SURFACE_SAMPLE_SCHEMA = "planet_surface_spectral_sample_v1"
SURFACE_PYRAMID_SAMPLE_SCHEMA = "planet_surface_frequency_pyramid_sample_v1"
SURFACE_READABILITY_SAMPLE_SCHEMA = "planet_surface_readability_sample_v1"


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _vec3(values: Sequence[Any]) -> tuple[float, float, float]:
    if len(values) != 3:
        raise ValueError("unit_normal must have length 3")
    parsed = tuple(float(value) for value in values)
    length = math.sqrt(sum(value * value for value in parsed))
    if length <= 1e-12:
        raise ValueError("unit_normal cannot be zero")
    return tuple(value / length for value in parsed)  # type: ignore[return-value]


def _tuple_str(values: Sequence[Any]) -> tuple[str, ...]:
    return tuple(str(value) for value in values)


def _record_id(value: Any) -> str:
    if hasattr(value, "record_id"):
        return str(value.record_id)
    if isinstance(value, Mapping):
        return str(value["record_id"])
    raise ValueError("source layer shell requires record_id")


@dataclass(frozen=True)
class PlanetSurfaceSpectralFieldRecord:
    record_id: str
    schema: str
    tick: int
    planet_id: str
    parameter_seed: str
    coordinate_frame: Mapping[str, Any]
    spherical_harmonic_terms: tuple[Mapping[str, Any], ...]
    material_response_by_region: Mapping[str, Mapping[str, float]]
    source_layer_shell_ids: tuple[str, ...]
    source_macro_authority_ids: tuple[str, ...]
    source_record_ids: tuple[str, ...]
    is_authority_state: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "schema": self.schema,
            "tick": self.tick,
            "planet_id": self.planet_id,
            "parameter_seed": self.parameter_seed,
            "coordinate_frame": dict(self.coordinate_frame),
            "spherical_harmonic_terms": [dict(term) for term in self.spherical_harmonic_terms],
            "material_response_by_region": {
                key: dict(value) for key, value in self.material_response_by_region.items()
            },
            "source_layer_shell_ids": list(self.source_layer_shell_ids),
            "source_macro_authority_ids": list(self.source_macro_authority_ids),
            "source_record_ids": list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PlanetSurfaceSpectralFieldRecord":
        return cls(
            record_id=str(data["record_id"]),
            schema=str(data["schema"]),
            tick=int(data["tick"]),
            planet_id=str(data["planet_id"]),
            parameter_seed=str(data["parameter_seed"]),
            coordinate_frame=dict(data.get("coordinate_frame", {})),
            spherical_harmonic_terms=tuple(dict(term) for term in data.get("spherical_harmonic_terms", [])),
            material_response_by_region={
                str(key): {str(k): float(v) for k, v in dict(value).items()}
                for key, value in dict(data.get("material_response_by_region", {})).items()
            },
            source_layer_shell_ids=_tuple_str(data.get("source_layer_shell_ids", [])),
            source_macro_authority_ids=_tuple_str(data.get("source_macro_authority_ids", [])),
            source_record_ids=_tuple_str(data.get("source_record_ids", [])),
            is_authority_state=bool(data.get("is_authority_state", True)),
        )


@dataclass(frozen=True)
class PlanetSurfaceSpectralSampleRecord:
    record_id: str
    schema: str
    tick: int
    planet_id: str
    source_surface_field_id: str
    unit_normal: tuple[float, float, float]
    region_kind: str
    spectral_response: Mapping[str, float]
    source_record_ids: tuple[str, ...]
    is_authority_state: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "schema": self.schema,
            "tick": self.tick,
            "planet_id": self.planet_id,
            "source_surface_field_id": self.source_surface_field_id,
            "unit_normal": list(self.unit_normal),
            "region_kind": self.region_kind,
            "spectral_response": dict(self.spectral_response),
            "source_record_ids": list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PlanetSurfaceSpectralSampleRecord":
        return cls(
            record_id=str(data["record_id"]),
            schema=str(data["schema"]),
            tick=int(data["tick"]),
            planet_id=str(data["planet_id"]),
            source_surface_field_id=str(data["source_surface_field_id"]),
            unit_normal=_vec3(data["unit_normal"]),
            region_kind=str(data["region_kind"]),
            spectral_response={str(key): float(value) for key, value in dict(data.get("spectral_response", {})).items()},
            source_record_ids=_tuple_str(data.get("source_record_ids", [])),
            is_authority_state=bool(data.get("is_authority_state", False)),
        )


@dataclass(frozen=True)
class PlanetSurfaceReadabilitySampleRecord:
    record_id: str
    schema: str
    tick: int
    planet_id: str
    source_surface_field_id: str
    uv: tuple[float, float]
    unit_normal: tuple[float, float, float]
    world_position: tuple[float, float, float] | None
    region_kind: str
    spectral_response: Mapping[str, float]
    height: float
    slope: float
    roughness: float
    moisture: float
    footprint_span_world: float
    ray_bundle_id: str
    refinement_demand_record_ids: tuple[str, ...]
    source_record_ids: tuple[str, ...]
    is_authority_state: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.record_id,
            "record_id": self.record_id,
            "schema": self.schema,
            "tick": self.tick,
            "planet_id": self.planet_id,
            "source_surface_field_id": self.source_surface_field_id,
            "surface_field_record_id": self.source_surface_field_id,
            "uv": [round(value, 6) for value in self.uv],
            "unit_normal": [round(value, 6) for value in self.unit_normal],
            "world_position": None
            if self.world_position is None
            else [round(value, 6) for value in self.world_position],
            "region_kind": self.region_kind,
            "spectral_response": dict(self.spectral_response),
            "height": self.height,
            "slope": self.slope,
            "roughness": self.roughness,
            "moisture": self.moisture,
            "footprint_span_world": self.footprint_span_world,
            "ray_bundle_id": self.ray_bundle_id,
            "refinement_demand_record_ids": list(self.refinement_demand_record_ids),
            "source_record_ids": list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }


def _harmonic_value(term: Mapping[str, Any], normal: Sequence[float]) -> float:
    axis = _vec3(term["axis"])
    frequency = float(term["frequency"])
    phase = float(term["phase"])
    amplitude = float(term["amplitude"])
    return amplitude * math.sin(frequency * sum(axis[index] * float(normal[index]) for index in range(3)) + phase)


def _seed_float(seed: str, index: int, *, low: float, high: float) -> float:
    digest = hashlib.sha256(f"{seed}:{index}".encode("utf-8")).hexdigest()
    raw = int(digest[:12], 16) / float(16**12 - 1)
    return low + raw * (high - low)


def build_planet_surface_spectral_field(
    *,
    planet_id: str,
    tick: int,
    parameter_seed: str,
    layer_shells: Sequence[Any],
    source_macro_authority_ids: Sequence[str],
) -> PlanetSurfaceSpectralFieldRecord:
    layer_ids = tuple(_record_id(layer) for layer in layer_shells)
    seed = f"{parameter_seed}:{planet_id}:{','.join(layer_ids)}"
    axes = (
        (1.0, 0.15, 0.05),
        (0.12, 1.0, 0.23),
        (0.21, -0.13, 1.0),
        (0.75, 0.25, 0.61),
    )
    terms = tuple(
        {
            "axis": list(axis),
            "frequency": round(_seed_float(seed, index, low=4.0, high=18.0), 6),
            "phase": round(_seed_float(seed, index + 10, low=-math.pi, high=math.pi), 6),
            "amplitude": round(_seed_float(seed, index + 20, low=0.22, high=0.82), 6),
        }
        for index, axis in enumerate(axes)
    )
    material_response = {
        "ocean_like": {"blue": 0.62, "green": 0.26, "red": 0.06, "near_ir": 0.05},
        "land_like": {"blue": 0.16, "green": 0.58, "yellow": 0.32, "red": 0.18, "near_ir": 0.10},
        "ice_like": {"violet": 0.28, "blue": 0.50, "green": 0.44, "red": 0.28},
        "atmosphere_limb": {"blue": 0.72, "violet": 0.26, "green": 0.18},
    }
    payload = {
        "planet_id": str(planet_id),
        "tick": int(tick),
        "parameter_seed": str(parameter_seed),
        "source_layer_shell_ids": layer_ids,
        "source_macro_authority_ids": [str(value) for value in source_macro_authority_ids],
        "terms": terms,
    }
    record_id = f"planet-surface-spectral-field::{_canonical_digest(payload).split(':', 1)[1][:16]}"
    return PlanetSurfaceSpectralFieldRecord(
        record_id=record_id,
        schema=SURFACE_FIELD_SCHEMA,
        tick=int(tick),
        planet_id=str(planet_id),
        parameter_seed=str(parameter_seed),
        coordinate_frame={"kind": "unit_sphere_normal", "handedness": "right"},
        spherical_harmonic_terms=terms,
        material_response_by_region=material_response,
        source_layer_shell_ids=layer_ids,
        source_macro_authority_ids=tuple(str(value) for value in source_macro_authority_ids),
        source_record_ids=tuple(dict.fromkeys([*layer_ids, *[str(value) for value in source_macro_authority_ids]])),
    )


def sample_planet_surface_spectral_field(
    field: PlanetSurfaceSpectralFieldRecord,
    *,
    unit_normal: Sequence[float],
    tick: int,
) -> PlanetSurfaceSpectralSampleRecord:
    normal = _vec3(unit_normal)
    score = sum(_harmonic_value(term, normal) for term in field.spherical_harmonic_terms)
    latitude = abs(normal[2])
    if latitude > 0.78 and score > -0.25:
        region_kind = "ice_like"
    elif latitude < 0.18 and score > 0.62:
        region_kind = "atmosphere_limb"
    elif score > 0.18:
        region_kind = "land_like"
    else:
        region_kind = "ocean_like"
    spectral = dict(field.material_response_by_region[region_kind])
    payload = {
        "field": field.record_id,
        "tick": int(tick),
        "unit_normal": [round(value, 5) for value in normal],
        "region_kind": region_kind,
    }
    return PlanetSurfaceSpectralSampleRecord(
        record_id=f"planet-surface-spectral-sample::{_canonical_digest(payload).split(':', 1)[1][:16]}",
        schema=SURFACE_SAMPLE_SCHEMA,
        tick=int(tick),
        planet_id=field.planet_id,
        source_surface_field_id=field.record_id,
        unit_normal=normal,
        region_kind=region_kind,
        spectral_response=spectral,
        source_record_ids=(field.record_id, *field.source_record_ids),
    )


def _smoothstep(edge0: float, edge1: float, value: float) -> float:
    if abs(edge1 - edge0) <= 1e-12:
        return 1.0 if value >= edge1 else 0.0
    t = max(0.0, min(1.0, (float(value) - float(edge0)) / (float(edge1) - float(edge0))))
    return t * t * (3.0 - 2.0 * t)


def _region_alias(region_kind: str) -> str:
    return {
        "ocean_like": "ocean",
        "land_like": "land",
        "ice_like": "ice",
        "atmosphere_limb": "coast",
    }.get(region_kind, "land")


def _unit_normal_from_uv(u: float, v: float) -> tuple[float, float, float]:
    longitude = (float(u) % 1.0) * math.tau
    latitude = (max(0.0, min(1.0, float(v))) - 0.5) * math.pi
    cos_lat = math.cos(latitude)
    return (
        cos_lat * math.cos(longitude),
        cos_lat * math.sin(longitude),
        math.sin(latitude),
    )


def _surface_height_signal(field: PlanetSurfaceSpectralFieldRecord, normal: Sequence[float]) -> float:
    raw = sum(_harmonic_value(term, normal) for term in field.spherical_harmonic_terms)
    return max(0.0, min(1.0, 0.5 + raw * 0.12))


def sample_planet_surface_readability(
    field: PlanetSurfaceSpectralFieldRecord,
    *,
    u: float,
    v: float,
    footprint_span_world: float,
    tick: int | None = None,
    ray_bundle_id: str = "",
    refinement_demand_record_ids: Sequence[str] = (),
    center_world: Sequence[float] | None = None,
    radius_world: float | None = None,
) -> PlanetSurfaceReadabilitySampleRecord:
    footprint = max(1e-6, float(footprint_span_world))
    normal = _unit_normal_from_uv(float(u), float(v))
    pyramid = sample_planet_surface_frequency_pyramid(
        field,
        u=float(u),
        v=float(v),
        footprint_span_world=footprint,
    )
    height = _surface_height_signal(field, normal)
    delta = min(0.015, max(0.002, footprint * 0.012))
    height_u = _surface_height_signal(field, _unit_normal_from_uv(float(u) + delta, float(v)))
    height_v = _surface_height_signal(field, _unit_normal_from_uv(float(u), float(v) + delta))
    slope = max(0.0, min(1.0, math.sqrt((height_u - height) ** 2 + (height_v - height) ** 2) / max(1e-6, delta)))
    region_kind = str(pyramid["dominant_region_kind"])
    moisture_by_region = {
        "ocean": 1.0,
        "coast": 0.78,
        "river": 0.86,
        "ice": 0.42,
        "land": 0.32,
        "mountain": 0.18,
    }
    roughness = max(0.0, min(1.0, float(pyramid["high_frequency_weight"]) * 0.82 + slope * 0.18))
    moisture = moisture_by_region.get(region_kind, 0.30)
    world_position = None
    if center_world is not None and radius_world is not None:
        if len(center_world) != 3:
            raise ValueError("center_world must have length 3")
        surface_radius = float(radius_world) + (height - 0.5) * max(0.0, float(radius_world)) * 0.035
        world_position = tuple(float(center_world[index]) + normal[index] * surface_radius for index in range(3))
    source_ids = tuple(
        dict.fromkeys(
            [
                field.record_id,
                ray_bundle_id,
                *[str(value) for value in refinement_demand_record_ids],
                *[str(value) for value in pyramid.get("source_record_ids", [])],
                *field.source_record_ids,
            ]
        )
    )
    payload = {
        "field": field.record_id,
        "u": round(float(u), 5),
        "v": round(float(v), 5),
        "footprint": round(footprint, 6),
        "ray_bundle_id": ray_bundle_id,
        "refinement_demand_record_ids": [str(value) for value in refinement_demand_record_ids],
        "tick": int(field.tick if tick is None else tick),
    }
    return PlanetSurfaceReadabilitySampleRecord(
        record_id=f"planet-surface-readability-sample::{_canonical_digest(payload).split(':', 1)[1][:16]}",
        schema=SURFACE_READABILITY_SAMPLE_SCHEMA,
        tick=int(field.tick if tick is None else tick),
        planet_id=field.planet_id,
        source_surface_field_id=field.record_id,
        uv=(float(u) % 1.0, max(0.0, min(1.0, float(v)))),
        unit_normal=normal,
        world_position=world_position,  # type: ignore[arg-type]
        region_kind=region_kind,
        spectral_response=dict(pyramid["composite_spectral_response"]),
        height=round(height, 6),
        slope=round(slope, 6),
        roughness=round(roughness, 6),
        moisture=round(moisture, 6),
        footprint_span_world=round(footprint, 6),
        ray_bundle_id=str(ray_bundle_id),
        refinement_demand_record_ids=tuple(str(value) for value in refinement_demand_record_ids),
        source_record_ids=tuple(value for value in source_ids if value),
    )


def sample_planet_surface_frequency_pyramid(
    field: PlanetSurfaceSpectralFieldRecord,
    *,
    u: float,
    v: float,
    footprint_span_world: float,
) -> dict[str, Any]:
    """Return a compact low/mid/high surface sample for continuous LOD.

    This is still derived from the authoritative surface field. The extra
    bands are not hand-painted geometry; they are deterministic filters over
    the same harmonic surface signal at different footprint sizes.
    """

    footprint = max(1e-6, float(footprint_span_world))
    normal = _unit_normal_from_uv(float(u), float(v))
    low_sample = sample_planet_surface_spectral_field(field, unit_normal=normal, tick=field.tick)

    neighbor_a = _unit_normal_from_uv(float(u) + min(0.12, footprint * 0.08), float(v))
    neighbor_b = _unit_normal_from_uv(float(u), float(v) + min(0.12, footprint * 0.08))
    mid_a = sample_planet_surface_spectral_field(field, unit_normal=neighbor_a, tick=field.tick)
    mid_b = sample_planet_surface_spectral_field(field, unit_normal=neighbor_b, tick=field.tick)

    high_seed = f"{field.record_id}:{round(float(u), 5)}:{round(float(v), 5)}"
    high_value = int(hashlib.sha256(high_seed.encode("utf-8")).hexdigest()[:8], 16) / float(16**8 - 1)
    high_frequency_weight = 1.0 - _smoothstep(0.03, 0.45, footprint)
    mid_frequency_weight = _smoothstep(0.85, 0.12, footprint)
    low_frequency_weight = max(0.0, 1.0 - max(high_frequency_weight, mid_frequency_weight) * 0.55)

    dominant = _region_alias(low_sample.region_kind)
    if dominant == "land" and high_frequency_weight > 0.55:
        dominant = "mountain" if high_value > 0.58 else "river"
    elif dominant == "ocean" and high_frequency_weight > 0.70 and high_value > 0.72:
        dominant = "coast"

    composite: dict[str, float] = {}
    keys = set(low_sample.spectral_response) | set(mid_a.spectral_response) | set(mid_b.spectral_response)
    for key in keys:
        low = float(low_sample.spectral_response.get(key, 0.0))
        mid = (float(mid_a.spectral_response.get(key, 0.0)) + float(mid_b.spectral_response.get(key, 0.0))) * 0.5
        high_mod = (high_value - 0.5) * high_frequency_weight * (0.18 if key in {"green", "blue", "near_ir"} else 0.10)
        composite[key] = round(max(0.0, low * low_frequency_weight + mid * (1.0 - low_frequency_weight) + high_mod), 6)

    payload = {
        "field": field.record_id,
        "u": round(float(u), 5),
        "v": round(float(v), 5),
        "footprint": round(footprint, 6),
        "dominant": dominant,
        "high_weight": round(high_frequency_weight, 6),
    }
    return {
        "schema": SURFACE_PYRAMID_SAMPLE_SCHEMA,
        "sample_id": f"planet-surface-frequency-pyramid::{_canonical_digest(payload).split(':', 1)[1][:16]}",
        "source_surface_field_id": field.record_id,
        "low_frequency": {
            "region_kind": _region_alias(low_sample.region_kind),
            "sample_record_id": low_sample.record_id,
            "weight": round(low_frequency_weight, 6),
        },
        "mid_frequency": {
            "region_kinds": [_region_alias(mid_a.region_kind), _region_alias(mid_b.region_kind)],
            "sample_record_ids": [mid_a.record_id, mid_b.record_id],
            "weight": round(mid_frequency_weight, 6),
        },
        "high_frequency": {
            "feature_seed": round(high_value, 6),
            "feature_kind": dominant,
            "weight": round(high_frequency_weight, 6),
        },
        "dominant_region_kind": dominant,
        "high_frequency_weight": round(high_frequency_weight, 6),
        "footprint_span_world": round(footprint, 6),
        "composite_spectral_response": composite,
        "source_record_ids": list(dict.fromkeys([field.record_id, low_sample.record_id, mid_a.record_id, mid_b.record_id, *field.source_record_ids])),
        "is_authority_state": False,
    }
