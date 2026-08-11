from __future__ import annotations

from typing import Any

from world_engine.contracts import WorldState


def _structure_records(state: WorldState) -> list[Any]:
    return [
        event
        for event in state.events
        if event.kind in {"field_structure_event", "field_object_extraction", "field_wave_step"}
    ]


def _inferred_kind(component: dict[str, Any], event_kinds: list[str]) -> str:
    if "decay" in event_kinds:
        return "dampening_like_region"
    if "birth" in event_kinds or "split" in event_kinds:
        return "source_like_region"
    if int(component.get("support_size", 0)) >= 16:
        return "boundary_like_region"
    return "material_like_region"


def derive_field_affordance_summaries(state: WorldState, *, limit: int = 8) -> list[dict[str, Any]]:
    metrics = state.payload.get("field_structure_metrics", {})
    components = list(metrics.get("components", []))
    records = _structure_records(state)
    source_record_ids = [record.record_id for record in records]
    event_kinds = sorted(
        {
            kind
            for record in records
            if record.kind == "field_structure_event"
            for kind in record.payload.get("event_kinds", [])
        }
    )
    summaries: list[dict[str, Any]] = []
    for index, component in enumerate(components[:limit]):
        region_grid = list(component.get("support_bounds_grid", []))
        if len(region_grid) != 4:
            continue
        summaries.append(
            {
                "schema": "field_derived_affordance_summary_v1",
                "summary_id": f"field-derived-affordance::{state.tick}::{index}",
                "origin_type": "field_derived",
                "is_authority_state": False,
                "read_only": True,
                "must_not_feed_back": True,
                "inferred_affordance_kind": _inferred_kind(component, event_kinds),
                "component_id": component.get("component_id"),
                "field_channel": component.get("channel"),
                "region_grid": region_grid,
                "centroid_world": component.get("centroid_world"),
                "support_size": component.get("support_size"),
                "field_energy": component.get("energy"),
                "confidence": 0.35,
                "source_record_ids": source_record_ids,
            }
        )
    return summaries
