from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _finite_float(value: Any, *, name: str) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


def _finite_vec3(values: Sequence[Any], *, name: str) -> tuple[float, float, float]:
    if len(values) != 3:
        raise ValueError(f"{name} must have three values")
    return tuple(_finite_float(value, name=name) for value in values)  # type: ignore[return-value]


def _distance(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt(sum((float(a[index]) - float(b[index])) ** 2 for index in range(3)))


def _normalize(v: Sequence[float]) -> tuple[float, float, float]:
    length = math.sqrt(sum(float(value) * float(value) for value in v))
    if length <= 1e-12:
        return (1.0, 0.0, 0.0)
    return tuple(float(value) / length for value in v)  # type: ignore[return-value]


@dataclass(frozen=True)
class SpectralBand:
    band_id: str
    wavelength_nm_min: float
    wavelength_nm_max: float
    display_name: str
    visible: bool
    response_weight: float


@dataclass(frozen=True)
class SpectralBandProfile:
    profile_id: str
    schema: str
    bands: tuple[SpectralBand, ...]
    rgb_response_matrix: tuple[tuple[float, float, float], ...]
    source_record_ids: tuple[str, ...]


def default_spectral_band_profile() -> SpectralBandProfile:
    bands = (
        SpectralBand("violet", 380.0, 450.0, "violet", True, 0.85),
        SpectralBand("blue", 450.0, 495.0, "blue", True, 1.00),
        SpectralBand("green", 495.0, 570.0, "green", True, 1.00),
        SpectralBand("yellow", 570.0, 590.0, "yellow", True, 0.92),
        SpectralBand("red", 620.0, 750.0, "red", True, 1.00),
        SpectralBand("near_ir", 750.0, 1050.0, "near infrared", False, 0.35),
    )
    return SpectralBandProfile(
        profile_id="spectral-band-profile::visible-plus-near-ir",
        schema="spectral_band_profile_v1",
        bands=bands,
        rgb_response_matrix=(
            (0.36, 0.10, 0.80),
            (0.15, 0.42, 1.00),
            (0.18, 0.95, 0.28),
            (0.96, 0.86, 0.10),
            (1.00, 0.20, 0.08),
            (0.75, 0.08, 0.02),
        ),
        source_record_ids=("spectral-band-profile::visible-plus-near-ir",),
    )


def validate_spectral_band_profile(profile: SpectralBandProfile) -> None:
    if profile.schema != "spectral_band_profile_v1":
        raise ValueError("spectral band profile schema mismatch")
    if not profile.bands:
        raise ValueError("spectral band profile requires bands")
    if len(profile.rgb_response_matrix) != len(profile.bands):
        raise ValueError("rgb response matrix must match band count")
    previous_max = -math.inf
    seen_ids: set[str] = set()
    for index, band in enumerate(profile.bands):
        if not band.band_id:
            raise ValueError("spectral band requires band_id")
        if band.band_id in seen_ids:
            raise ValueError("duplicate spectral band")
        seen_ids.add(band.band_id)
        if band.wavelength_nm_min >= band.wavelength_nm_max:
            raise ValueError("spectral band wavelength range must be increasing")
        if band.visible and band.wavelength_nm_min < previous_max:
            raise ValueError("visible spectral band ranges overlap")
        previous_max = max(previous_max, band.wavelength_nm_max) if band.visible else previous_max
        row = profile.rgb_response_matrix[index]
        if len(row) != 3 or any(not math.isfinite(float(value)) for value in row):
            raise ValueError("rgb response row must contain finite rgb values")
    if not any(band.visible for band in profile.bands):
        raise ValueError("spectral band profile requires visible bands")


def compose_visible_rgb(profile: SpectralBandProfile, energy_by_band: Mapping[str, float]) -> tuple[float, float, float]:
    validate_spectral_band_profile(profile)
    rgb = [0.0, 0.0, 0.0]
    for band, row in zip(profile.bands, profile.rgb_response_matrix):
        energy = max(0.0, float(energy_by_band.get(band.band_id, 0.0))) * band.response_weight
        for channel in range(3):
            rgb[channel] += energy * float(row[channel])
    peak = max(1.0, *rgb)
    return tuple(max(0.0, min(1.0, value / peak)) for value in rgb)  # type: ignore[return-value]


@dataclass(frozen=True)
class SolarEarthTemplateBindingRecord:
    record_id: str
    schema: str
    source_package_name: str
    source_package_digest: str
    seed_salt: str
    spectral_profile_id: str
    star_template_id: str
    planet_template_id: str
    parameter_digest: str
    source_record_ids: tuple[str, ...]


def build_solar_earth_template_binding(
    *,
    source_package_name: str,
    source_package_digest: str,
    seed_salt: str,
    spectral_profile_id: str,
    star_template_id: str,
    planet_template_id: str,
) -> SolarEarthTemplateBindingRecord:
    payload = {
        "source_package_name": str(source_package_name),
        "source_package_digest": str(source_package_digest),
        "seed_salt": str(seed_salt),
        "spectral_profile_id": str(spectral_profile_id),
        "star_template_id": str(star_template_id),
        "planet_template_id": str(planet_template_id),
    }
    digest = _canonical_digest(payload)
    short = digest.split(":", 1)[1][:16]
    record = SolarEarthTemplateBindingRecord(
        record_id=f"solar-earth-template-binding::{short}",
        schema="solar_earth_template_binding_v1",
        source_package_name=str(source_package_name),
        source_package_digest=str(source_package_digest),
        seed_salt=str(seed_salt),
        spectral_profile_id=str(spectral_profile_id),
        star_template_id=str(star_template_id),
        planet_template_id=str(planet_template_id),
        parameter_digest=digest,
        source_record_ids=(f"source-package::{source_package_name}", digest),
    )
    validate_solar_earth_template_binding(record)
    return record


def default_solar_earth_template_binding(source_package_name: str = "source-package-a") -> SolarEarthTemplateBindingRecord:
    profile = default_spectral_band_profile()
    digest = "sha256:" + hashlib.sha256(source_package_name.encode("utf-8")).hexdigest()
    return build_solar_earth_template_binding(
        source_package_name=source_package_name,
        source_package_digest=digest,
        seed_salt=f"solar-earth::{source_package_name}",
        spectral_profile_id=profile.profile_id,
        star_template_id="star-template::effective-main-sequence",
        planet_template_id="planet-template::earth-like-layered",
    )


def validate_solar_earth_template_binding(record: SolarEarthTemplateBindingRecord) -> None:
    if record.schema != "solar_earth_template_binding_v1":
        raise ValueError("solar earth template binding schema mismatch")
    if not record.source_package_name or not record.source_package_digest:
        raise ValueError("solar earth template binding requires source package identity")
    if not record.spectral_profile_id or not record.star_template_id or not record.planet_template_id:
        raise ValueError("solar earth template binding requires template ids")
    expected = _canonical_digest(
        {
            "source_package_name": record.source_package_name,
            "source_package_digest": record.source_package_digest,
            "seed_salt": record.seed_salt,
            "spectral_profile_id": record.spectral_profile_id,
            "star_template_id": record.star_template_id,
            "planet_template_id": record.planet_template_id,
        }
    )
    if record.parameter_digest != expected:
        raise ValueError("solar earth template binding parameter digest mismatch")
    if not record.source_record_ids:
        raise ValueError("solar earth template binding requires source_record_ids")


@dataclass(frozen=True)
class SolarRadiationSourceRecord:
    record_id: str
    schema: str
    source_kind: str
    center_world: tuple[float, float, float]
    radius_world: float
    emission_direction_model: str
    spectral_power_by_band: dict[str, float]
    luminosity_scale: float
    falloff_model: str
    source_field_basis_ids: tuple[str, ...]
    source_record_ids: tuple[str, ...]

    def validated(self, profile: SpectralBandProfile) -> "SolarRadiationSourceRecord":
        validate_spectral_band_profile(profile)
        if self.schema != "solar_radiation_source_v1":
            raise ValueError("solar radiation source schema mismatch")
        known = {band.band_id for band in profile.bands}
        unknown = set(self.spectral_power_by_band) - known
        if unknown:
            raise ValueError("unknown spectral band in solar radiation source")
        if self.radius_world <= 0.0 or self.luminosity_scale < 0.0:
            raise ValueError("solar radiation source requires positive radius and non-negative luminosity")
        if self.emission_direction_model != "outward_radial" or self.falloff_model != "inverse_square_clamped":
            raise ValueError("unsupported solar radiation source model")
        return self


@dataclass(frozen=True)
class SpectralRadiationSample:
    point_world: tuple[float, float, float]
    direction_world: tuple[float, float, float]
    energy_by_band: dict[str, float]
    source_record_ids: tuple[str, ...]


def demo_solar_radiation_source(profile: SpectralBandProfile) -> SolarRadiationSourceRecord:
    validate_spectral_band_profile(profile)
    powers = {band.band_id: (1.4 if band.band_id in {"yellow", "red"} else 1.0) for band in profile.bands}
    source = SolarRadiationSourceRecord(
        record_id="solar-radiation-source::effective-sun",
        schema="solar_radiation_source_v1",
        source_kind="star_radiation_source",
        center_world=(0.0, 0.0, 0.0),
        radius_world=2.0,
        emission_direction_model="outward_radial",
        spectral_power_by_band=powers,
        luminosity_scale=1.0,
        falloff_model="inverse_square_clamped",
        source_field_basis_ids=("implicit-basis::solar-radial-emitter",),
        source_record_ids=("solar-radiation-source::effective-sun", profile.profile_id),
    )
    return source.validated(profile)


def sample_solar_radiation_at(
    source: SolarRadiationSourceRecord,
    point_world: Sequence[float],
    profile: SpectralBandProfile,
) -> SpectralRadiationSample:
    source.validated(profile)
    point = _finite_vec3(point_world, name="point_world")
    direction = _normalize([point[index] - source.center_world[index] for index in range(3)])
    distance = max(source.radius_world, _distance(source.center_world, point))
    falloff = (source.radius_world / distance) ** 2
    energy = {
        band.band_id: max(0.0, float(source.spectral_power_by_band.get(band.band_id, 0.0))) * source.luminosity_scale * falloff
        for band in profile.bands
    }
    return SpectralRadiationSample(
        point_world=point,
        direction_world=direction,
        energy_by_band=energy,
        source_record_ids=(source.record_id,),
    )


@dataclass(frozen=True)
class PlanetLayerShellRecord:
    record_id: str
    schema: str
    planet_id: str
    layer_kind: str
    inner_radius_world: float
    outer_radius_world: float
    density_class: str
    absorption_by_band: dict[str, float]
    scattering_by_band: dict[str, float]
    thermal_response: float
    source_record_ids: tuple[str, ...]


def demo_earth_like_layer_shells(profile: SpectralBandProfile) -> tuple[PlanetLayerShellRecord, ...]:
    validate_spectral_band_profile(profile)
    bands = [band.band_id for band in profile.bands]

    def band_map(base: float, visible_boost: float = 0.0) -> dict[str, float]:
        return {band_id: base + (visible_boost if band_id in {"blue", "green"} else 0.0) for band_id in bands}

    specs = (
        ("core", 0.00, 0.28, "dense_metal", 0.95, 0.01, 1.00),
        ("mantle", 0.28, 0.78, "viscous_rock", 0.68, 0.03, 0.64),
        ("crust", 0.78, 0.93, "solid_rock", 0.45, 0.05, 0.34),
        ("ocean", 0.93, 1.00, "liquid_water", 0.22, 0.18, 0.26),
        ("atmosphere", 1.00, 1.15, "gas_shell", 0.08, 0.42, 0.12),
    )
    records = []
    for kind, inner, outer, density, absorption, scattering, thermal in specs:
        records.append(
            PlanetLayerShellRecord(
                record_id=f"planet-layer-shell::earth-like::{kind}",
                schema="planet_layer_shell_v1",
                planet_id="planet::earth-like",
                layer_kind=kind,
                inner_radius_world=inner,
                outer_radius_world=outer,
                density_class=density,
                absorption_by_band=band_map(absorption, visible_boost=0.02 if kind == "atmosphere" else 0.0),
                scattering_by_band=band_map(scattering, visible_boost=0.18 if kind == "atmosphere" else 0.0),
                thermal_response=thermal,
                source_record_ids=(f"planet-layer-shell::earth-like::{kind}", profile.profile_id),
            )
        )
    validate_planet_layer_shells(tuple(records), profile)
    return tuple(records)


def validate_planet_layer_shells(layers: Sequence[PlanetLayerShellRecord], profile: SpectralBandProfile) -> None:
    validate_spectral_band_profile(profile)
    if not layers:
        raise ValueError("planet layer shells required")
    known = {band.band_id for band in profile.bands}
    previous_outer = -1.0
    for layer in layers:
        if layer.schema != "planet_layer_shell_v1":
            raise ValueError("planet layer shell schema mismatch")
        if layer.inner_radius_world < previous_outer - 1e-9 or layer.outer_radius_world <= layer.inner_radius_world:
            raise ValueError("planet layer shells must be monotonic")
        previous_outer = layer.outer_radius_world
        if set(layer.absorption_by_band) - known or set(layer.scattering_by_band) - known:
            raise ValueError("planet layer shell references unknown spectral band")
        if not layer.source_record_ids:
            raise ValueError("planet layer shell requires source_record_ids")


def find_layers_at_radius(layers: Sequence[PlanetLayerShellRecord], radius_world: float) -> tuple[PlanetLayerShellRecord, ...]:
    radius = float(radius_world)
    tolerance = 1e-9
    return tuple(
        layer
        for layer in layers
        if layer.inner_radius_world - tolerance <= radius <= layer.outer_radius_world + tolerance
    )


@dataclass(frozen=True)
class PlanetMacroAuthorityRecord:
    record_id: str
    schema: str
    planet_id: str
    macro_state_id: str
    macro_certificate_id: str
    center_world: tuple[float, float, float]
    radius_world: float
    layer_shell_record_ids: tuple[str, ...]
    source_field_state_ids: tuple[str, ...]
    validity_envelope: dict[str, Any]
    source_record_ids: tuple[str, ...]


def build_planet_macro_authority_record(
    *,
    planet_id: str,
    macro_state_id: str,
    macro_certificate_id: str,
    center_world: Sequence[float],
    radius_world: float,
    layer_shells: Sequence[PlanetLayerShellRecord],
    source_field_state_ids: Sequence[str],
) -> PlanetMacroAuthorityRecord:
    record = PlanetMacroAuthorityRecord(
        record_id=f"planet-macro-authority::{planet_id}",
        schema="planet_macro_authority_v1",
        planet_id=str(planet_id),
        macro_state_id=str(macro_state_id),
        macro_certificate_id=str(macro_certificate_id),
        center_world=_finite_vec3(center_world, name="center_world"),
        radius_world=_finite_float(radius_world, name="radius_world"),
        layer_shell_record_ids=tuple(layer.record_id for layer in layer_shells),
        source_field_state_ids=tuple(str(value) for value in source_field_state_ids),
        validity_envelope={
            "tick_start": 0,
            "tick_end": 10_000,
            "max_refinement_depth": 4,
            "observer_resolution_limit_world": 0.02,
            "macro_authority_kind": "certified_layered_planet",
        },
        source_record_ids=tuple(
            [
                str(macro_state_id),
                str(macro_certificate_id),
                *[layer.record_id for layer in layer_shells],
                *[str(value) for value in source_field_state_ids],
            ]
        ),
    )
    return record


def validate_planet_macro_authority(record: PlanetMacroAuthorityRecord, layer_shells: Sequence[PlanetLayerShellRecord]) -> None:
    if record.schema != "planet_macro_authority_v1":
        raise ValueError("planet macro authority schema mismatch")
    if not record.macro_certificate_id:
        raise ValueError("planet macro authority requires macro_certificate_id")
    if record.radius_world <= 0.0:
        raise ValueError("planet macro authority radius must be positive")
    expected_layers = {layer.record_id for layer in layer_shells}
    if set(record.layer_shell_record_ids) != expected_layers:
        raise ValueError("planet macro authority layer shell set mismatch")
    if not record.source_field_state_ids or not record.source_record_ids:
        raise ValueError("planet macro authority requires source records")


@dataclass(frozen=True)
class PlanetEnergyFluxRecord:
    record_id: str
    schema: str
    tick: int
    flux_kind: str
    input_energy_total: float
    output_energy_total: float
    relative_budget_error: float
    source_record_ids: tuple[str, ...]


@dataclass(frozen=True)
class PlanetLocalRefinementRequest:
    request_id: str
    schema: str
    observer_id: str
    trigger_kind: str
    world_point: tuple[float, float, float]
    requested_radius_world: float
    requested_resolution: tuple[int, int, int]
    max_refinement_depth: int
    source_planet_macro_authority_ids: tuple[str, ...]
    source_layer_shell_ids: tuple[str, ...]
    source_record_ids: tuple[str, ...]


@dataclass(frozen=True)
class PlanetLocalRefinementPatch:
    patch_id: str
    schema: str
    request_id: str
    covered_layer_ids: tuple[str, ...]
    final_patch_digest: str
    patch_summary: dict[str, Any]
    source_record_ids: tuple[str, ...]
