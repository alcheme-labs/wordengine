from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, Mapping, Sequence

from world_engine.contracts import ProjectionFrame
from world_engine.five_phase import (
    FIVE_PHASE_NAMES,
    FivePhaseFieldRecord,
    FivePhasePatternRecord,
    FivePhaseTraceRecord,
    FivePhaseVector,
    normalize_phase_weights,
    reject_authority_shortcuts,
    stable_record_id,
)


PHASE_RESPONSE_BY_BAND: dict[str, dict[str, float]] = {
    "low": {
        "contractive": 1.0,
        "generative": 0.35,
        "transport": 0.45,
        "radiant": 0.15,
        "substrate": 0.95,
    },
    "mid": {
        "contractive": 0.55,
        "generative": 0.85,
        "transport": 0.75,
        "radiant": 0.45,
        "substrate": 0.55,
    },
    "high": {
        "contractive": 0.25,
        "generative": 0.45,
        "transport": 0.65,
        "radiant": 1.0,
        "substrate": 0.2,
    },
    "wide": {
        "contractive": 0.7,
        "generative": 0.7,
        "transport": 0.7,
        "radiant": 0.7,
        "substrate": 0.7,
    },
}


def _resolve_band(frequency_window: Mapping[str, Any]) -> str:
    explicit = frequency_window.get("band")
    if explicit:
        band = str(explicit)
        if band not in PHASE_RESPONSE_BY_BAND:
            raise ValueError(f"unknown FivePhase frequency band {band!r}.")
        return band
    minimum = float(frequency_window.get("min_frequency", 0.0))
    maximum = float(frequency_window.get("max_frequency", 1.0))
    if maximum - minimum >= 0.75:
        return "wide"
    if maximum <= 0.34:
        return "low"
    if minimum >= 0.66:
        return "high"
    return "mid"


def _visibility_weight(pattern: FivePhasePatternRecord, frequency_window: Mapping[str, Any]) -> float:
    center = frequency_window.get("center_grid")
    if center is None:
        return 1.0
    sigma = max(float(frequency_window.get("sigma", 8.0)), 1e-6)
    theta = float(frequency_window.get("theta", 0.0))
    gamma = float(frequency_window.get("gamma", 1.0))
    wavelength = max(float(frequency_window.get("wavelength", 8.0)), 1e-6)
    phase = float(frequency_window.get("phase", 0.0))
    cx, cy = float(center[0]), float(center[1])
    x = float(pattern.centroid_grid[0]) - cx
    y = float(pattern.centroid_grid[1]) - cy
    xp = math.cos(theta) * x + math.sin(theta) * y
    yp = -math.sin(theta) * x + math.cos(theta) * y
    envelope = math.exp(-((xp * xp) + (gamma * gamma * yp * yp)) / (2.0 * sigma * sigma))
    carrier = abs(math.cos((2.0 * math.pi * xp / wavelength) + phase))
    return max(0.0, min(1.0, envelope * carrier))


def build_five_phase_trace(
    pattern: FivePhasePatternRecord,
    phase_field: FivePhaseFieldRecord,
    *,
    observer_id: str,
    frequency_window: Mapping[str, Any],
    tick: int | None = None,
) -> FivePhaseTraceRecord:
    reject_authority_shortcuts(frequency_window, path="frequency_window")
    band = _resolve_band(frequency_window)
    response = normalize_phase_weights(PHASE_RESPONSE_BY_BAND[band])
    pattern_values = pattern.phase_vector.to_dict()
    response_values = response.to_dict()
    visibility = _visibility_weight(pattern, frequency_window)
    support_energy = float(pattern.payload.get("support_energy", 1.0))
    support_scale = min(1.0, support_energy / max(float(phase_field.metrics.get("feature_summaries", {}).get("peak_rho", 1.0)), 1e-6))
    dot_response = sum(pattern_values[name] * response_values[name] for name in FIVE_PHASE_NAMES)
    trace_intensity = max(0.0, min(1.0, visibility * support_scale * dot_response))
    projection_loss_manifest = {
        "schema": "five_phase_projection_loss_manifest_v1",
        "preserved_invariants": [
            "pattern_id",
            "phase_field_id",
            "dominant_phase",
            "invariant_signature",
            "phase_response",
        ],
        "discarded_degrees_of_freedom": [
            "full_cell_phase_grid",
            "raw_field_channel_samples",
            "unobserved_frequency_windows",
        ],
        "frequency_band": band,
        "observer_visibility_weight": visibility,
        "source_pattern_invariant_signature": pattern.invariant_signature,
        "is_authority_state": False,
    }
    return FivePhaseTraceRecord(
        record_id=stable_record_id(
            "five-phase-trace",
            {
                "pattern_id": pattern.record_id,
                "phase_field_id": phase_field.record_id,
                "observer_id": observer_id,
                "frequency_window": dict(frequency_window),
                "tick": pattern.tick if tick is None else tick,
            },
        ),
        schema="five_phase_trace_v1",
        tick=pattern.tick if tick is None else int(tick),
        observer_id=observer_id,
        pattern_id=pattern.record_id,
        phase_field_id=phase_field.record_id,
        frequency_window=dict(frequency_window),
        phase_response=response,
        trace_intensity=trace_intensity,
        projection_loss_manifest=projection_loss_manifest,
        source_record_ids=(pattern.record_id, phase_field.record_id, *pattern.source_record_ids, *phase_field.source_record_ids),
        is_authority_state=False,
    )


def attach_five_phase_trace_summary(
    frame: ProjectionFrame,
    traces: Sequence[FivePhaseTraceRecord],
) -> ProjectionFrame:
    payload = dict(frame.payload)
    payload["five_phase_trace_summary"] = {
        "schema": "five_phase_trace_summary_v1",
        "is_authority_state": False,
        "trace_ids": [trace.record_id for trace in traces],
        "observer_id": frame.observer_id,
        "tick": frame.tick,
        "trace_intensity_by_pattern": {
            trace.pattern_id: trace.trace_intensity
            for trace in traces
        },
        "source_record_ids": [trace.record_id for trace in traces],
    }
    source_ids = list(dict.fromkeys([*frame.source_record_ids, *(trace.record_id for trace in traces)]))
    return replace(frame, payload=payload, source_record_ids=source_ids)


__all__ = ["PHASE_RESPONSE_BY_BAND", "build_five_phase_trace", "attach_five_phase_trace_summary"]
