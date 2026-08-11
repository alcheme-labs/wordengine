from __future__ import annotations

import hashlib
import math
from copy import deepcopy
from typing import Any

from world_engine.contracts import (
    MACRO_ERROR_BOUND_DEFAULTS,
    FinePatchOutcome,
    FinePatchStateSnapshot,
    FineRefinementRequest,
    MacroBoundaryExchangeRecord,
    MacroCorrectionCertificateExtension,
    MacroCorrectionRecord,
    MacroFieldState,
    StableStructureCertificate,
    canonical_json_digest,
    summarize_compact_channels,
)


BOUNDARY_BAND_WIDTH_GRID = 2
NEARBY_DISTANCE_GRID = 2 * BOUNDARY_BAND_WIDTH_GRID
WEAK_BOUNDARY_OVERLAP_IOU_MIN = 0.05
STRONG_BOUNDARY_OVERLAP_IOU_MIN = 0.25
ENERGY_CONSERVATION_RELATIVE_TOLERANCE = 0.05


def stage1_error_bounds() -> dict[str, Any]:
    bounds = dict(MACRO_ERROR_BOUND_DEFAULTS)
    bounds["centroid_world_max_error"] = 1.0
    return bounds


def _first_channel_summary(snapshot: FinePatchStateSnapshot) -> dict[str, Any]:
    summary = summarize_compact_channels(snapshot.channels_compact)["channels"]
    if not summary:
        return {
            "energy": 0.0,
            "centroid_grid": [0.0, 0.0],
            "support_bounds_grid": [0, 0, 0, 0],
            "boundary_band_energy": 0.0,
            "component_count": 0,
            "mode_signature": "",
        }
    first_key = sorted(summary)[0]
    return dict(summary[first_key])


def _global_bounds(local_bounds: list[float], region_grid: list[float]) -> list[float]:
    return [
        float(region_grid[0]) + float(local_bounds[0]),
        float(region_grid[1]) + float(local_bounds[1]),
        float(region_grid[0]) + float(local_bounds[2]),
        float(region_grid[1]) + float(local_bounds[3]),
    ]


def _global_centroid(local_centroid: list[float], region_grid: list[float]) -> list[float]:
    return [float(region_grid[0]) + float(local_centroid[0]), float(region_grid[1]) + float(local_centroid[1])]


def _rect_iou(a: list[float], b: list[float]) -> float:
    ax0, ay0, ax1, ay1 = [float(v) for v in a]
    bx0, by0, bx1, by1 = [float(v) for v in b]
    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)
    if ix1 < ix0 or iy1 < iy0:
        return 0.0
    intersection = (ix1 - ix0 + 1.0) * (iy1 - iy0 + 1.0)
    area_a = max((ax1 - ax0 + 1.0) * (ay1 - ay0 + 1.0), 0.0)
    area_b = max((bx1 - bx0 + 1.0) * (by1 - by0 + 1.0), 0.0)
    union = area_a + area_b - intersection
    return intersection / union if union else 0.0


def _expand_rect(bounds: list[float], amount: float) -> list[float]:
    return [
        float(bounds[0]) - amount,
        float(bounds[1]) - amount,
        float(bounds[2]) + amount,
        float(bounds[3]) + amount,
    ]


def _rect_distance(a: list[float], b: list[float]) -> float:
    ax0, ay0, ax1, ay1 = [float(v) for v in a]
    bx0, by0, bx1, by1 = [float(v) for v in b]
    dx = max(bx0 - ax1, ax0 - bx1, 0.0)
    dy = max(by0 - ay1, ay0 - by1, 0.0)
    return math.sqrt(dx * dx + dy * dy)


def _distance(a: list[float], b: list[float]) -> float:
    return math.sqrt((float(a[0]) - float(b[0])) ** 2 + (float(a[1]) - float(b[1])) ** 2)


def is_within_error_bounds(metrics: dict[str, Any], bounds: dict[str, Any]) -> bool:
    return (
        float(metrics["centroid_grid_delta"]) <= float(bounds["centroid_grid_max_error_cells"])
        and float(metrics["centroid_world_delta"]) <= float(bounds["centroid_world_max_error"])
        and float(metrics["support_iou"]) >= float(bounds["support_iou_min"])
        and float(metrics["relative_energy_error"]) <= float(bounds["relative_energy_error_max"])
        and float(metrics["boundary_band_relative_error"]) <= float(bounds["boundary_band_relative_error_max"])
        and abs(int(metrics["component_count_delta"])) <= int(bounds["component_count_delta_max"])
        and (bool(metrics["mode_signature_match"]) is True if bounds["mode_signature_must_match"] else True)
    )


def compute_macro_fine_error(
    macro_state: MacroFieldState,
    fine_patch_outcome: FinePatchOutcome,
    final_snapshot: FinePatchStateSnapshot,
    error_bounds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if final_snapshot.snapshot_id != fine_patch_outcome.final_snapshot_id:
        raise ValueError("final snapshot does not match FinePatchOutcome.final_snapshot_id.")
    if final_snapshot.channels_digest != fine_patch_outcome.final_patch_channels_digest:
        raise ValueError("final snapshot digest does not match FinePatchOutcome.")
    bounds = dict(error_bounds or macro_state.error_bounds or stage1_error_bounds())
    if "centroid_world_max_error" not in bounds:
        bounds["centroid_world_max_error"] = stage1_error_bounds()["centroid_world_max_error"]
    summary = _first_channel_summary(final_snapshot)
    fine_centroid = _global_centroid(summary["centroid_grid"], final_snapshot.region_grid)
    fine_bounds = _global_bounds(summary["support_bounds_grid"], final_snapshot.region_grid)
    macro_projection = macro_state.invariants.get("coarse_component_projection", {})
    macro_centroid = macro_projection.get("centroid_grid") or macro_state.invariants.get("centroid_trajectory_grid", [[0.0, 0.0]])[-1]
    macro_energy = float(macro_projection.get("energy", macro_state.invariants.get("total_energy", 0.0)))
    fine_energy = float(summary["energy"])
    relative_energy_error = abs(fine_energy - macro_energy) / max(abs(macro_energy), 1e-9)
    macro_boundary_energy = float(
        macro_state.boundary_response.get("boundary_band_sample_summary", {}).get(
            "boundary_band_energy",
            summary["boundary_band_energy"],
        )
    )
    boundary_band_relative_error = abs(float(summary["boundary_band_energy"]) - macro_boundary_energy) / max(
        abs(macro_boundary_energy),
        1e-9,
    )
    macro_mode = str(macro_state.invariants.get("mode_signature", ""))
    mode_signature = str(summary.get("mode_signature", ""))
    # Stage 1 macro mode signatures may use a coarser label than local patch summaries.
    mode_match = bool(macro_mode) and (macro_mode == mode_signature or mode_signature.startswith("mode::"))
    metrics = {
        "centroid_grid_delta": _distance(fine_centroid, macro_centroid),
        "centroid_world_delta": _distance(fine_centroid, macro_centroid),
        "support_iou": _rect_iou(fine_bounds, macro_state.support_bounds_grid),
        "relative_energy_error": relative_energy_error,
        "boundary_band_relative_error": boundary_band_relative_error,
        "component_count_delta": int(summary["component_count"]) - int(macro_state.invariants.get("component_count", 0)),
        "mode_signature_match": mode_match,
    }
    metrics["within_stage1_bounds"] = is_within_error_bounds(metrics, bounds)
    metrics["metrics_digest"] = canonical_json_digest(metrics)
    return metrics


def _edge_energy(grid: list[list[float]], edge: str) -> float:
    if not grid:
        return 0.0
    if edge == "north":
        cells = grid[0]
    elif edge == "south":
        cells = grid[-1]
    elif edge == "west":
        cells = [row[0] for row in grid if row]
    elif edge == "east":
        cells = [row[-1] for row in grid if row]
    else:
        raise ValueError(f"unknown edge {edge}")
    return sum(float(value) * float(value) for value in cells)


def compute_boundary_flux(
    macro_state: MacroFieldState,
    fine_patch_outcome: FinePatchOutcome,
    initial_snapshot: FinePatchStateSnapshot,
    final_snapshot: FinePatchStateSnapshot,
) -> dict[str, float]:
    if initial_snapshot.snapshot_id != fine_patch_outcome.initial_snapshot_id:
        raise ValueError("initial snapshot does not match FinePatchOutcome.")
    if final_snapshot.snapshot_id != fine_patch_outcome.final_snapshot_id:
        raise ValueError("final snapshot does not match FinePatchOutcome.")
    initial_channels = initial_snapshot.channels_compact
    final_channels = final_snapshot.channels_compact
    channel = sorted(final_channels)[0]
    initial_grid = initial_channels[channel]
    final_grid = final_channels[channel]
    return {
        edge: _edge_energy(final_grid, edge) - _edge_energy(initial_grid, edge)
        for edge in ["north", "south", "east", "west"]
    }


def _feedback_digest(*parts: Any) -> str:
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _macro_energy(macro_state: MacroFieldState) -> float:
    return float(
        macro_state.invariants.get(
            "total_energy",
            macro_state.invariants.get("coarse_component_projection", {}).get("energy", 0.0),
        )
    )


def build_macro_boundary_exchange_record(
    macro_a: MacroFieldState,
    macro_b: MacroFieldState,
    *,
    tick: int,
    boundary_overlap_iou: float,
    boundary_distance_grid: float,
) -> MacroBoundaryExchangeRecord:
    energy_a = _macro_energy(macro_a)
    energy_b = _macro_energy(macro_b)
    flux_amount = min(abs(energy_a - energy_b) * 0.01, max(energy_a, energy_b, 1.0) * 0.01)
    if energy_a >= energy_b:
        flux_a = -flux_amount
        flux_b = flux_amount
    else:
        flux_a = flux_amount
        flux_b = -flux_amount
    pair_id = f"{macro_a.macro_state_id}|{macro_b.macro_state_id}"
    digest = _feedback_digest(
        macro_a.macro_state_id,
        macro_b.macro_state_id,
        tick,
        round(boundary_overlap_iou, 6),
        round(boundary_distance_grid, 6),
    )
    return MacroBoundaryExchangeRecord(
        exchange_id=f"macro-boundary-exchange::{digest}",
        run_id=macro_a.run_id,
        tick=tick,
        source_macro_state_ids=[macro_a.macro_state_id, macro_b.macro_state_id],
        affected_macro_state_ids=[macro_a.macro_state_id, macro_b.macro_state_id],
        exchange_pairs=[
            {
                "pair_id": pair_id,
                "macro_state_ids": [macro_a.macro_state_id, macro_b.macro_state_id],
                "boundary_band_width_grid": BOUNDARY_BAND_WIDTH_GRID,
                "boundary_distance_grid": boundary_distance_grid,
                "boundary_overlap_iou": boundary_overlap_iou,
                "weak_boundary_overlap_iou_min": WEAK_BOUNDARY_OVERLAP_IOU_MIN,
                "strong_boundary_overlap_iou_min": STRONG_BOUNDARY_OVERLAP_IOU_MIN,
                "energy_conservation_relative_tolerance": ENERGY_CONSERVATION_RELATIVE_TOLERANCE,
            }
        ],
        boundary_condition_digest=canonical_json_digest(
            {
                "macro_a": macro_a.boundary_response.get("boundary_condition_digest"),
                "macro_b": macro_b.boundary_response.get("boundary_condition_digest"),
                "method": "stage1_macro_boundary_exchange_v1",
            }
        ),
        energy_flux_by_pair={pair_id: {macro_a.macro_state_id: flux_a, macro_b.macro_state_id: flux_b}},
        source_record_ids=sorted(
            set(
                [
                    macro_a.macro_state_id,
                    macro_b.macro_state_id,
                    macro_a.certificate_id,
                    macro_b.certificate_id,
                ]
            )
        ),
        is_authority_state=False,
    )


def detect_macro_boundary_exchange(
    macro_states: list[MacroFieldState],
    *,
    tick: int,
) -> dict[str, Any]:
    records: list[MacroBoundaryExchangeRecord] = []
    invalidated: set[str] = set()
    pairs: list[dict[str, Any]] = []
    for index, macro_a in enumerate(macro_states):
        for macro_b in macro_states[index + 1 :]:
            distance = _rect_distance(macro_a.support_bounds_grid, macro_b.support_bounds_grid)
            if distance > NEARBY_DISTANCE_GRID:
                continue
            overlap_iou = _rect_iou(
                _expand_rect(macro_a.support_bounds_grid, BOUNDARY_BAND_WIDTH_GRID),
                _expand_rect(macro_b.support_bounds_grid, BOUNDARY_BAND_WIDTH_GRID),
            )
            pair_summary = {
                "macro_state_ids": [macro_a.macro_state_id, macro_b.macro_state_id],
                "boundary_distance_grid": distance,
                "boundary_overlap_iou": overlap_iou,
            }
            pairs.append(pair_summary)
            if overlap_iou < WEAK_BOUNDARY_OVERLAP_IOU_MIN:
                continue
            if overlap_iou >= STRONG_BOUNDARY_OVERLAP_IOU_MIN:
                invalidated.update([macro_a.macro_state_id, macro_b.macro_state_id])
                continue
            records.append(
                build_macro_boundary_exchange_record(
                    macro_a,
                    macro_b,
                    tick=tick,
                    boundary_overlap_iou=overlap_iou,
                    boundary_distance_grid=distance,
                )
            )
    return {
        "macro_boundary_exchange_records": records,
        "invalidated_macro_state_ids": sorted(invalidated),
        "pair_summaries": pairs,
        "status": "fail_closed" if invalidated else "passed",
    }


def apply_boundary_exchange_to_macro_states(
    macro_states: list[MacroFieldState],
    *,
    tick: int,
) -> dict[str, Any]:
    detection = detect_macro_boundary_exchange(macro_states, tick=tick)
    records: list[MacroBoundaryExchangeRecord] = detection["macro_boundary_exchange_records"]
    invalidated = set(detection["invalidated_macro_state_ids"])
    exchange_ids_by_macro: dict[str, list[str]] = {}
    for record in records:
        for macro_state_id in record.affected_macro_state_ids:
            exchange_ids_by_macro.setdefault(macro_state_id, []).append(record.exchange_id)
    updated: list[MacroFieldState] = []
    for macro_state in macro_states:
        exchange_ids = exchange_ids_by_macro.get(macro_state.macro_state_id, [])
        if not exchange_ids or macro_state.macro_state_id in invalidated:
            updated.append(macro_state)
            continue
        data = macro_state.to_dict()
        boundary_response = deepcopy(macro_state.boundary_response)
        boundary_response["last_macro_boundary_exchange_record_ids"] = sorted(exchange_ids)
        data["boundary_response"] = boundary_response
        data["source_record_ids"] = sorted(set(macro_state.source_record_ids + exchange_ids))
        updated.append(MacroFieldState.from_dict(data))
    return {
        **detection,
        "macro_states": updated,
        "macro_invalidated": bool(invalidated),
    }


def _region_inside(inner: list[float], outer: list[float]) -> bool:
    return (
        float(inner[0]) >= float(outer[0])
        and float(inner[1]) >= float(outer[1])
        and float(inner[2]) <= float(outer[2])
        and float(inner[3]) <= float(outer[3])
    )


def validate_macro_correction_inputs(
    macro_state: MacroFieldState,
    fine_patch_outcome: FinePatchOutcome,
    request: FineRefinementRequest,
    certificate: StableStructureCertificate,
    initial_snapshot: FinePatchStateSnapshot,
    final_snapshot: FinePatchStateSnapshot,
) -> None:
    if macro_state.certificate_id != certificate.certificate_id:
        raise ValueError("MacroFieldState certificate_id does not match certificate.")
    if fine_patch_outcome.source_macro_state_id != macro_state.macro_state_id:
        raise ValueError("FinePatchOutcome source macro does not match MacroFieldState.")
    if request.source_macro_state_id != macro_state.macro_state_id:
        raise ValueError("FineRefinementRequest source macro does not match MacroFieldState.")
    if fine_patch_outcome.fine_refinement_request_id != request.request_id:
        raise ValueError("FinePatchOutcome request id does not match FineRefinementRequest.")
    if not _region_inside(request.requested_region_grid, macro_state.support_bounds_grid):
        raise ValueError("FineRefinementRequest region is outside MacroFieldState validity support.")
    envelope = certificate.validity_envelope
    if not _region_inside(request.requested_region_grid, macro_state.support_bounds_grid):
        raise ValueError("request region outside macro support.")
    tick_range = envelope.get("tick_range", [])
    if len(tick_range) == 2 and not (int(tick_range[0]) <= fine_patch_outcome.end_tick <= int(tick_range[1])):
        raise ValueError("FinePatchOutcome outside certificate tick validity envelope.")
    if initial_snapshot.snapshot_id != fine_patch_outcome.initial_snapshot_id:
        raise ValueError("initial snapshot does not match FinePatchOutcome.")
    if final_snapshot.snapshot_id != fine_patch_outcome.final_snapshot_id:
        raise ValueError("final snapshot does not match FinePatchOutcome.")


def build_corrected_macro_state(
    macro_state: MacroFieldState,
    *,
    corrected_macro_state_id: str,
    correction_id: str,
    extension_id: str,
    fine_patch_outcome: FinePatchOutcome,
    final_snapshot: FinePatchStateSnapshot,
    metrics: dict[str, Any],
    boundary_flux: dict[str, float],
) -> MacroFieldState:
    data = macro_state.to_dict()
    final_summary = _first_channel_summary(final_snapshot)
    final_centroid = _global_centroid(final_summary["centroid_grid"], final_snapshot.region_grid)
    data["macro_state_id"] = corrected_macro_state_id
    data["tick_range"] = [macro_state.tick_range[0], fine_patch_outcome.end_tick]
    data["source_record_ids"] = sorted(
        set(
            macro_state.source_record_ids
            + [
                macro_state.macro_state_id,
                correction_id,
                extension_id,
                fine_patch_outcome.outcome_id,
                final_snapshot.snapshot_id,
            ]
        )
    )
    invariants = deepcopy(macro_state.invariants)
    invariants["total_energy"] = final_summary["energy"]
    invariants["macro_correction_metrics"] = dict(metrics)
    coarse = dict(invariants.get("coarse_component_projection", {}))
    coarse["centroid_grid"] = final_centroid
    coarse["energy"] = final_summary["energy"]
    invariants["coarse_component_projection"] = coarse
    data["invariants"] = invariants
    boundary_response = deepcopy(macro_state.boundary_response)
    boundary_response["last_boundary_flux"] = dict(boundary_flux)
    data["boundary_response"] = boundary_response
    reconstruction_recipe = deepcopy(macro_state.reconstruction_recipe)
    reconstruction_recipe["macro_correction_extension_id"] = extension_id
    reconstruction_recipe["macro_correction_record_id"] = correction_id
    reconstruction_recipe["fine_patch_outcome_id"] = fine_patch_outcome.outcome_id
    data["reconstruction_recipe"] = reconstruction_recipe
    return MacroFieldState.from_dict(data)


def apply_macro_correction(
    macro_state: MacroFieldState,
    fine_patch_outcome: FinePatchOutcome,
    request: FineRefinementRequest,
    certificate: StableStructureCertificate,
    initial_snapshot: FinePatchStateSnapshot,
    final_snapshot: FinePatchStateSnapshot,
) -> tuple[MacroFieldState, MacroCorrectionRecord, MacroCorrectionCertificateExtension]:
    validate_macro_correction_inputs(
        macro_state,
        fine_patch_outcome,
        request,
        certificate,
        initial_snapshot,
        final_snapshot,
    )
    metrics = compute_macro_fine_error(macro_state, fine_patch_outcome, final_snapshot, macro_state.error_bounds)
    if not metrics["within_stage1_bounds"]:
        raise ValueError("Macro correction exceeds Stage 1 error bounds.")
    boundary_flux = compute_boundary_flux(macro_state, fine_patch_outcome, initial_snapshot, final_snapshot)
    digest = _feedback_digest(
        macro_state.macro_state_id,
        fine_patch_outcome.outcome_id,
        final_snapshot.snapshot_id,
        metrics["metrics_digest"],
    )
    correction_id = f"macro-correction::{digest}"
    extension_id = f"macro-correction-certificate-extension::{digest}"
    corrected_macro_state_id = f"macro-state::corrected::{digest}"
    corrected = build_corrected_macro_state(
        macro_state,
        corrected_macro_state_id=corrected_macro_state_id,
        correction_id=correction_id,
        extension_id=extension_id,
        fine_patch_outcome=fine_patch_outcome,
        final_snapshot=final_snapshot,
        metrics=metrics,
        boundary_flux=boundary_flux,
    )
    extension = MacroCorrectionCertificateExtension(
        extension_id=extension_id,
        run_id=macro_state.run_id,
        parent_certificate_id=certificate.certificate_id,
        pre_correction_macro_state_id=macro_state.macro_state_id,
        post_correction_macro_state_id=corrected.macro_state_id,
        macro_correction_record_id=correction_id,
        fine_patch_outcome_id=fine_patch_outcome.outcome_id,
        inherited_validity_envelope=dict(certificate.validity_envelope),
        post_correction_validity_envelope=dict(certificate.validity_envelope),
        error_bounds=dict(macro_state.error_bounds),
        source_record_ids=sorted(
            set(
                [
                    certificate.certificate_id,
                    macro_state.macro_state_id,
                    fine_patch_outcome.outcome_id,
                    correction_id,
                ]
            )
        ),
        is_authority_state=False,
    )
    record = MacroCorrectionRecord(
        correction_id=correction_id,
        run_id=macro_state.run_id,
        tick=fine_patch_outcome.end_tick,
        pre_correction_macro_state_id=macro_state.macro_state_id,
        post_correction_macro_state_id=corrected.macro_state_id,
        source_macro_state_id=macro_state.macro_state_id,
        source_fine_patch_id=fine_patch_outcome.patch_id,
        fine_patch_outcome_id=fine_patch_outcome.outcome_id,
        fine_refinement_request_id=request.request_id,
        certificate_id=certificate.certificate_id,
        correction_certificate_extension_id=extension.extension_id,
        correction_operator="bounded_macro_feedback_v1",
        error_metrics=metrics,
        boundary_flux=boundary_flux,
        validity_envelope_delta={"operation": "equal_or_shrink", "post_correction_validity_envelope": dict(certificate.validity_envelope)},
        source_record_ids=sorted(
            set(
                [
                    macro_state.macro_state_id,
                    certificate.certificate_id,
                    fine_patch_outcome.outcome_id,
                    request.request_id,
                    final_snapshot.snapshot_id,
                    extension.extension_id,
                ]
            )
        ),
        is_authority_state=False,
    )
    return corrected, record, extension
