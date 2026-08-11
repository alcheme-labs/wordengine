from __future__ import annotations

from typing import Any

from world_engine.contracts import FieldState, WorldEvent, WorldObject
from world_engine.field_metrics import detect_field_components


Support = list[tuple[int, int]]


def compute_support_region(channel_grid: list[list[float]], threshold: float = 0.2) -> Support:
    max_abs = max((abs(value) for row in channel_grid for value in row), default=0.0)
    if max_abs == 0.0:
        return []
    effective_threshold = min(threshold, max_abs * 0.2)
    return [
        (row_index, col_index)
        for row_index, row in enumerate(channel_grid)
        for col_index, value in enumerate(row)
        if abs(value) >= effective_threshold
    ]


def compute_centroid(channel_grid: list[list[float]], support: Support) -> list[float]:
    if not support:
        raise ValueError("cannot compute centroid for empty support")
    weight_sum = 0.0
    col_sum = 0.0
    row_sum = 0.0
    for row_index, col_index in support:
        weight = abs(channel_grid[row_index][col_index]) ** 2
        weight_sum += weight
        col_sum += col_index * weight
        row_sum += row_index * weight
    if weight_sum == 0.0:
        raise ValueError("support has zero energy")
    return [col_sum / weight_sum, row_sum / weight_sum]


def support_bounds_grid(support: Support) -> list[int]:
    rows = [item[0] for item in support]
    cols = [item[1] for item in support]
    return [min(cols), min(rows), max(cols), max(rows)]


def _support_overlap(left: list[int], right: list[int]) -> float:
    left_x0, left_y0, left_x1, left_y1 = left
    right_x0, right_y0, right_x1, right_y1 = right
    x0 = max(left_x0, right_x0)
    y0 = max(left_y0, right_y0)
    x1 = min(left_x1, right_x1)
    y1 = min(left_y1, right_y1)
    intersection = max(0, x1 - x0 + 1) * max(0, y1 - y0 + 1)
    left_area = (left_x1 - left_x0 + 1) * (left_y1 - left_y0 + 1)
    right_area = (right_x1 - right_x0 + 1) * (right_y1 - right_y0 + 1)
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def _field_energy(channel_grid: list[list[float]], support: Support) -> float:
    return sum(channel_grid[row][col] ** 2 for row, col in support)


def _candidate_object(
    field_state: FieldState,
    component: dict[str, Any],
    extraction_record_id: str,
    same_family_component_count: int,
) -> WorldObject:
    family = component["family"]
    component_index = int(component["component_index"])
    object_id = (
        f"field-object::{family}"
        if same_family_component_count == 1
        else f"field-object::{family}::component-{component_index}"
    )
    return WorldObject(
        object_id=object_id,
        family=family,
        tick=field_state.tick,
        position=list(component["centroid_world"]),
        stability_score=1.0,
        continuity_score=1.0,
        payload={
            "derived_from_field_state_id": field_state.field_state_id,
            "field_component_id": component["component_id"],
            "field_channel": component["channel"],
            "field_energy": component["energy"],
            "field_centroid": list(component["centroid_grid"]),
            "field_centroid_grid": list(component["centroid_grid"]),
            "field_centroid_world": list(component["centroid_world"]),
            "field_support_size": component["support_size"],
            "field_support_bounds_grid": list(component["support_bounds_grid"]),
            "field_extraction_record_id": extraction_record_id,
            "objects_derived_from_field": True,
            "mode_signature": component["mode_signature"],
        },
    )


def match_field_objects(
    previous_objects: list[WorldObject],
    current_candidates: list[WorldObject],
    min_overlap: float = 0.25,
) -> tuple[list[WorldObject], dict[str, dict[str, Any]]]:
    matched: list[WorldObject] = []
    matches: dict[str, dict[str, Any]] = {}
    used_previous_ids: set[str] = set()
    for candidate in current_candidates:
        current_bounds = candidate.payload.get("field_support_bounds_grid")
        current_signature = candidate.payload.get("mode_signature")
        best_previous: WorldObject | None = None
        best_overlap = 0.0
        for previous in previous_objects:
            if previous.object_id in used_previous_ids or previous.family != candidate.family:
                continue
            previous_bounds = previous.payload.get("field_support_bounds_grid")
            previous_signature = previous.payload.get("mode_signature")
            if not previous_bounds or not current_bounds:
                continue
            overlap = _support_overlap(previous_bounds, current_bounds)
            if overlap > best_overlap:
                best_previous = previous
                best_overlap = overlap
        if best_previous is None:
            if candidate.tick > 0:
                candidate.object_id = f"{candidate.object_id}::{candidate.tick}"
            matched.append(candidate)
            continue

        if best_overlap >= min_overlap:
            candidate.object_id = best_previous.object_id
            candidate.payload["source_object_id"] = best_previous.object_id
            candidate.payload["overlap_score"] = best_overlap
            used_previous_ids.add(best_previous.object_id)
            matches[candidate.object_id] = {
                "previous_support_bounds_grid": list(best_previous.payload["field_support_bounds_grid"]),
                "current_support_bounds_grid": list(current_bounds),
                "overlap_score": best_overlap,
                "previous_mode_signature": best_previous.payload["mode_signature"],
                "current_mode_signature": current_signature,
                "mode_signature_changed": best_previous.payload["mode_signature"] != current_signature,
                "retained_object_id": best_previous.object_id,
            }
        else:
            candidate.object_id = f"{candidate.object_id}::{candidate.tick}"
        matched.append(candidate)
    return matched, matches


def build_field_object_extraction_record(
    field_state: FieldState,
    extracted_objects: list[WorldObject],
) -> WorldEvent:
    source_record_ids = list(field_state.source_record_ids)
    upstream_record_kind = "field_wave_step" if field_state.tick > 0 else "seed_evidence_bridge"
    return WorldEvent(
        record_id=f"field_object_extraction::{field_state.tick}",
        tick=field_state.tick,
        kind="field_object_extraction",
        payload={
            "field_state_id": field_state.field_state_id,
            "coordinate_frame": dict(field_state.payload["coordinate_frame"]),
            "source_state_ticks": list(field_state.source_state_ticks),
            "source_record_ids": source_record_ids,
            "source_object_ids": [obj.object_id for obj in extracted_objects],
            "upstream_record_kind": upstream_record_kind,
            "extracted_object_ids": [obj.object_id for obj in extracted_objects],
            "extractions_by_object_id": {
                obj.object_id: {
                    "field_channel": obj.payload["field_channel"],
                    "component_id": obj.payload["field_component_id"],
                    "support_bounds_grid": list(obj.payload["field_support_bounds_grid"]),
                    "support_size": obj.payload["field_support_size"],
                    "centroid_grid": list(obj.payload["field_centroid_grid"]),
                    "centroid_world": list(obj.payload["field_centroid_world"]),
                    "field_energy": obj.payload["field_energy"],
                    "mode_signature": obj.payload["mode_signature"],
                }
                for obj in extracted_objects
            },
        },
    )


def build_field_identity_match_record(
    previous_field_state: FieldState,
    current_field_state: FieldState,
    previous_objects: list[WorldObject],
    current_objects: list[WorldObject],
    matches_by_object_id: dict[str, dict[str, Any]],
) -> WorldEvent | None:
    if not matches_by_object_id:
        return None
    previous_extraction_record_id = previous_objects[0].payload.get("field_extraction_record_id")
    current_extraction_record_id = current_objects[0].payload.get("field_extraction_record_id")
    record = WorldEvent(
        record_id=f"field_identity_match::{current_field_state.tick}",
        tick=current_field_state.tick,
        kind="field_identity_match",
        payload={
            "previous_field_state_id": previous_field_state.field_state_id,
            "current_field_state_id": current_field_state.field_state_id,
            "previous_field_extraction_record_id": previous_extraction_record_id,
            "current_field_extraction_record_id": current_extraction_record_id,
            "matches_by_object_id": matches_by_object_id,
        },
    )
    for obj in current_objects:
        match = matches_by_object_id.get(obj.object_id)
        if match:
            obj.payload["field_identity_match_record_id"] = record.record_id
            obj.payload["overlap_score"] = match["overlap_score"]
    return record


def extract_objects_from_field(
    field_state: FieldState,
    previous_objects: list[WorldObject] | None = None,
    previous_field_state: FieldState | None = None,
    threshold: float = 0.2,
) -> tuple[list[WorldObject], WorldEvent, WorldEvent | None]:
    extraction_record_id = f"field_object_extraction::{field_state.tick}"
    candidates: list[WorldObject] = []
    components = detect_field_components(
        field_state,
        threshold=threshold,
        include_support_cells=False,
    )
    family_counts: dict[str, int] = {}
    for component in components:
        family_counts[component["family"]] = family_counts.get(component["family"], 0) + 1
    for component in components:
        candidates.append(
            _candidate_object(
                field_state,
                component,
                extraction_record_id,
                family_counts[component["family"]],
            )
        )

    objects, matches = match_field_objects(previous_objects or [], candidates)
    extraction_record = build_field_object_extraction_record(field_state, objects)
    identity_record = None
    if previous_objects and previous_field_state:
        identity_record = build_field_identity_match_record(
            previous_field_state,
            field_state,
            previous_objects,
            objects,
            matches,
        )
    return objects, extraction_record, identity_record
