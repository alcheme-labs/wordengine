from __future__ import annotations

from typing import Any

from world_engine.contracts import DerivedMaterialPropertyRecord


FORBIDDEN_AUTHORITY_KEYS = {"css_color", "viewer_color", "material_color_name"}


def _scan_forbidden_keys(value: Any, path: str = "spectral_response") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in FORBIDDEN_AUTHORITY_KEYS:
                raise ValueError(f"{path}.{key} cannot be used as spectral authority.")
            _scan_forbidden_keys(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _scan_forbidden_keys(nested, f"{path}[{index}]")


def _clamp01(value: Any) -> float:
    return max(0.0, min(1.0, float(value or 0.0)))


def _avg(values: list[float]) -> float:
    return round(sum(values) / max(1, len(values)), 6)


def _band_key_for_window(observer_frequency_window: dict[str, Any]) -> str:
    if observer_frequency_window.get("band_key"):
        return str(observer_frequency_window["band_key"])
    max_frequency = float(observer_frequency_window.get("max_frequency", 770.0))
    min_frequency = float(observer_frequency_window.get("min_frequency", 430.0))
    if max_frequency <= 430.0:
        return "low_band"
    if min_frequency >= 650.0:
        return "high_band"
    return "visible_band"


def build_spectral_observation_payload(
    property_records: list[DerivedMaterialPropertyRecord],
    observer_frequency_window: dict[str, Any],
) -> dict[str, Any]:
    if not property_records:
        raise ValueError("spectral observation requires derived material property records.")
    for record in property_records:
        _scan_forbidden_keys(record.spectral_response)
    band_key = _band_key_for_window(observer_frequency_window)
    visible_bands = [
        dict(record.spectral_response.get(band_key) or record.spectral_response.get("visible_band") or {})
        for record in property_records
    ]
    visible_band_response = {
        "absorb": _avg([_clamp01(band.get("absorb")) for band in visible_bands]),
        "reflect": _avg([_clamp01(band.get("reflect")) for band in visible_bands]),
        "transmit": _avg([_clamp01(band.get("transmit")) for band in visible_bands]),
        "emit": _avg([_clamp01(band.get("emit")) for band in visible_bands]),
    }
    source_record_ids = sorted(
        set(
            record_id
            for record in property_records
            for record_id in [
                record.record_id,
                *record.source_substrate_measurement_record_ids,
                *record.source_record_ids,
            ]
        )
    )
    opacity = _clamp01(1.0 - visible_band_response["transmit"] * 0.75)
    emission = _clamp01(visible_band_response["emit"])
    return {
        "spectral_projection_schema": "substrate_spectral_observation_v1",
        "observer_semantics": "observer-filtered spectral projection",
        "observer_frequency_window": dict(observer_frequency_window),
        "selected_frequency_band": band_key,
        "visible_band_response": visible_band_response,
        "absorb_reflect_transmit_emit": dict(visible_band_response),
        "render_hints": {
            "opacity": round(opacity, 6),
            "emission_intensity": round(emission, 6),
            "reflectance_intensity": visible_band_response["reflect"],
            "transmission_intensity": visible_band_response["transmit"],
        },
        "source_property_record_ids": [record.record_id for record in property_records],
        "source_measurement_record_ids": [
            measurement_id
            for record in property_records
            for measurement_id in record.source_substrate_measurement_record_ids
        ],
        "source_record_ids": source_record_ids,
        "is_authority_state": False,
    }


def build_multi_observer_spectral_observations(
    property_records: list[DerivedMaterialPropertyRecord],
    observer_frequency_windows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not observer_frequency_windows:
        raise ValueError("multi-observer spectral observation requires declared observer windows.")
    observations = {
        observer_id: build_spectral_observation_payload(property_records, window)
        for observer_id, window in sorted(observer_frequency_windows.items())
    }
    source_record_ids = sorted(
        {
            source_record_id
            for observation in observations.values()
            for source_record_id in observation["source_record_ids"]
        }
    )
    source_property_record_ids = sorted(
        {
            property_id
            for observation in observations.values()
            for property_id in observation["source_property_record_ids"]
        }
    )
    source_measurement_record_ids = sorted(
        {
            measurement_id
            for observation in observations.values()
            for measurement_id in observation["source_measurement_record_ids"]
        }
    )
    return {
        "spectral_projection_schema": "multi_observer_substrate_spectral_observation_v1",
        "observer_semantics": "declared observer frequency windows over substrate-derived property records",
        "declared_observer_frequency_windows": {
            observer_id: dict(window)
            for observer_id, window in sorted(observer_frequency_windows.items())
        },
        "spectral_observations_by_observer": observations,
        "source_property_record_ids": source_property_record_ids,
        "source_measurement_record_ids": source_measurement_record_ids,
        "source_record_ids": source_record_ids,
        "is_authority_state": False,
    }
