from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from math import isfinite
from typing import Any


JsonDict = dict[str, Any]

PROJECTION_PIPELINE = (
    "authority_state -> event_radiative_or_interaction_records -> "
    "observer_filter -> image_plane_projection"
)


def _dict(value: JsonDict | None) -> JsonDict:
    return dict(value or {})


def _list(value: list[Any] | None) -> list[Any]:
    return list(value or [])


def _grid(value: list[list[float]] | None) -> list[list[float]]:
    return [_list(row) for row in value or []]


def _channels(value: dict[str, list[list[float]]] | None) -> dict[str, list[list[float]]]:
    return {key: _grid(grid) for key, grid in (value or {}).items()}


def _bool(value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError("authority flag must be a bool.")
    return value


def _validate_channel_grid(name: str, grid: list[list[float]], grid_shape: list[int]) -> None:
    if len(grid_shape) != 2:
        raise ValueError("FieldState grid_shape must contain [height, width].")
    expected_height, expected_width = grid_shape
    if len(grid) != expected_height:
        raise ValueError(f"Channel {name} height does not match grid_shape.")
    if any(len(row) != expected_width for row in grid):
        raise ValueError(f"Channel {name} width does not match grid_shape.")


@dataclass
class WorldObject:
    object_id: str
    family: str
    tick: int
    position: list[float]
    stability_score: float
    continuity_score: float
    payload: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "object_id": self.object_id,
            "family": self.family,
            "tick": self.tick,
            "position": _list(self.position),
            "stability_score": self.stability_score,
            "continuity_score": self.continuity_score,
            "payload": _dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> WorldObject:
        return cls(
            object_id=data["object_id"],
            family=data["family"],
            tick=data["tick"],
            position=_list(data["position"]),
            stability_score=data["stability_score"],
            continuity_score=data["continuity_score"],
            payload=_dict(data.get("payload")),
        )


@dataclass
class WorldEvent:
    record_id: str
    tick: int
    kind: str
    payload: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "record_id": self.record_id,
            "tick": self.tick,
            "kind": self.kind,
            "payload": _dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> WorldEvent:
        return cls(
            record_id=data["record_id"],
            tick=data["tick"],
            kind=data["kind"],
            payload=_dict(data.get("payload")),
        )


@dataclass
class RadiativeRecord:
    record_id: str
    tick: int
    kind: str
    payload: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "record_id": self.record_id,
            "tick": self.tick,
            "kind": self.kind,
            "payload": _dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> RadiativeRecord:
        return cls(
            record_id=data["record_id"],
            tick=data["tick"],
            kind=data["kind"],
            payload=_dict(data.get("payload")),
        )


@dataclass
class InteractionRecord:
    record_id: str
    tick: int
    kind: str
    payload: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "record_id": self.record_id,
            "tick": self.tick,
            "kind": self.kind,
            "payload": _dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> InteractionRecord:
        return cls(
            record_id=data["record_id"],
            tick=data["tick"],
            kind=data["kind"],
            payload=_dict(data.get("payload")),
        )


@dataclass
class CausalLink:
    link_id: str
    source_tick: int
    target_tick: int
    kind: str
    source_ids: list[str]
    target_ids: list[str]
    payload: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "link_id": self.link_id,
            "source_tick": self.source_tick,
            "target_tick": self.target_tick,
            "kind": self.kind,
            "source_ids": _list(self.source_ids),
            "target_ids": _list(self.target_ids),
            "payload": _dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> CausalLink:
        return cls(
            link_id=data["link_id"],
            source_tick=data["source_tick"],
            target_tick=data["target_tick"],
            kind=data["kind"],
            source_ids=_list(data["source_ids"]),
            target_ids=_list(data["target_ids"]),
            payload=_dict(data.get("payload")),
        )


@dataclass
class ObserverRecord:
    record_id: str
    observer_id: str
    valid_from: int
    valid_to: int
    visible_object_ids: list[str]
    payload: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "record_id": self.record_id,
            "observer_id": self.observer_id,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "visible_object_ids": _list(self.visible_object_ids),
            "payload": _dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> ObserverRecord:
        return cls(
            record_id=data["record_id"],
            observer_id=data["observer_id"],
            valid_from=data["valid_from"],
            valid_to=data["valid_to"],
            visible_object_ids=_list(data["visible_object_ids"]),
            payload=_dict(data.get("payload")),
        )


@dataclass
class ObserverProjection:
    projection_id: str
    observer_id: str
    observer_model: str
    light_model: str
    pipeline: str
    observer_filter: JsonDict
    image_plane: JsonDict
    source_state_ticks: list[int]
    source_object_ids: list[str]
    source_record_ids: list[str]
    authority_entities: list[str]
    derived_light_summary: JsonDict
    payload: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "projection_id": self.projection_id,
            "observer_id": self.observer_id,
            "observer_model": self.observer_model,
            "light_model": self.light_model,
            "pipeline": self.pipeline,
            "observer_filter": _dict(self.observer_filter),
            "image_plane": _dict(self.image_plane),
            "source_state_ticks": _list(self.source_state_ticks),
            "source_object_ids": _list(self.source_object_ids),
            "source_record_ids": _list(self.source_record_ids),
            "authority_entities": _list(self.authority_entities),
            "derived_light_summary": _dict(self.derived_light_summary),
            "payload": _dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> ObserverProjection:
        return cls(
            projection_id=data["projection_id"],
            observer_id=data["observer_id"],
            observer_model=data["observer_model"],
            light_model=data["light_model"],
            pipeline=data["pipeline"],
            observer_filter=_dict(data["observer_filter"]),
            image_plane=_dict(data["image_plane"]),
            source_state_ticks=_list(data["source_state_ticks"]),
            source_object_ids=_list(data["source_object_ids"]),
            source_record_ids=_list(data["source_record_ids"]),
            authority_entities=_list(data["authority_entities"]),
            derived_light_summary=_dict(data["derived_light_summary"]),
            payload=_dict(data.get("payload")),
        )


@dataclass
class NaturalPhenomenonSummary:
    phenomenon_id: str
    tick: int
    kind: str
    phenomenon: str
    source_state_ticks: list[int]
    source_object_ids: list[str]
    source_record_ids: list[str]
    payload: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "phenomenon_id": self.phenomenon_id,
            "tick": self.tick,
            "kind": self.kind,
            "phenomenon": self.phenomenon,
            "source_state_ticks": _list(self.source_state_ticks),
            "source_object_ids": _list(self.source_object_ids),
            "source_record_ids": _list(self.source_record_ids),
            "payload": _dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> NaturalPhenomenonSummary:
        return cls(
            phenomenon_id=data["phenomenon_id"],
            tick=data["tick"],
            kind=data["kind"],
            phenomenon=data["phenomenon"],
            source_state_ticks=_list(data["source_state_ticks"]),
            source_object_ids=_list(data["source_object_ids"]),
            source_record_ids=_list(data["source_record_ids"]),
            payload=_dict(data.get("payload")),
        )


@dataclass
class ProjectionSample:
    sample_id: str
    object_id: str
    family: str
    center: list[float]
    covariance: list[list[float]]
    intensity: float
    opacity: float
    color_hint: str
    source_state_ticks: list[int]
    source_object_ids: list[str]
    source_record_ids: list[str]
    payload: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "sample_id": self.sample_id,
            "object_id": self.object_id,
            "family": self.family,
            "center": _list(self.center),
            "covariance": [_list(row) for row in self.covariance],
            "intensity": self.intensity,
            "opacity": self.opacity,
            "color_hint": self.color_hint,
            "source_state_ticks": _list(self.source_state_ticks),
            "source_object_ids": _list(self.source_object_ids),
            "source_record_ids": _list(self.source_record_ids),
            "payload": _dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> ProjectionSample:
        return cls(
            sample_id=data["sample_id"],
            object_id=data["object_id"],
            family=data["family"],
            center=_list(data["center"]),
            covariance=[_list(row) for row in data["covariance"]],
            intensity=data["intensity"],
            opacity=data["opacity"],
            color_hint=data["color_hint"],
            source_state_ticks=_list(data["source_state_ticks"]),
            source_object_ids=_list(data["source_object_ids"]),
            source_record_ids=_list(data["source_record_ids"]),
            payload=_dict(data.get("payload")),
        )


@dataclass
class PhenomenonOverlay:
    overlay_id: str
    phenomenon: str
    kind: str
    visual_operator: str
    parameters: JsonDict
    source_state_ticks: list[int]
    source_object_ids: list[str]
    source_record_ids: list[str]
    payload: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "overlay_id": self.overlay_id,
            "phenomenon": self.phenomenon,
            "kind": self.kind,
            "visual_operator": self.visual_operator,
            "parameters": _dict(self.parameters),
            "source_state_ticks": _list(self.source_state_ticks),
            "source_object_ids": _list(self.source_object_ids),
            "source_record_ids": _list(self.source_record_ids),
            "payload": _dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> PhenomenonOverlay:
        return cls(
            overlay_id=data["overlay_id"],
            phenomenon=data["phenomenon"],
            kind=data["kind"],
            visual_operator=data["visual_operator"],
            parameters=_dict(data["parameters"]),
            source_state_ticks=_list(data["source_state_ticks"]),
            source_object_ids=_list(data["source_object_ids"]),
            source_record_ids=_list(data["source_record_ids"]),
            payload=_dict(data.get("payload")),
        )


@dataclass
class ProjectionFrame:
    frame_id: str
    tick: int
    observer_id: str
    image_plane: JsonDict
    samples: list[ProjectionSample]
    phenomena_overlays: list[PhenomenonOverlay]
    source_state_ticks: list[int]
    source_object_ids: list[str]
    source_record_ids: list[str]
    is_authority_state: bool
    audit: JsonDict
    payload: JsonDict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.is_authority_state:
            raise ValueError("Projection frames cannot be authority state.")
        if not self.source_state_ticks:
            raise ValueError("Projection frames must cite source state ticks.")
        required_audit_keys = {
            "projection_semantics",
            "no_persistent_light_object",
            "no_material_asset_authority",
            "no_global_raindrop_authority_state",
        }
        missing_keys = required_audit_keys - set(self.audit)
        if missing_keys:
            raise ValueError(
                "Projection frame audit is missing required boundary keys: "
                + ", ".join(sorted(missing_keys))
            )
        timeline = self.payload.get("event_timeline")
        if not isinstance(timeline, dict):
            raise ValueError("Projection frames must include payload.event_timeline.")
        required_timeline_keys = {
            "tick",
            "event_kinds",
            "interaction_record_ids",
            "wave_step_record_ids",
            "field_structure_event_ids",
            "source_record_ids",
            "observer_id",
            "is_authority_state",
        }
        missing_timeline_keys = required_timeline_keys - set(timeline)
        if missing_timeline_keys:
            raise ValueError(
                "Projection frame event_timeline is missing required keys: "
                + ", ".join(sorted(missing_timeline_keys))
            )
        if timeline.get("is_authority_state") is not False:
            raise ValueError("Projection frame event_timeline cannot be authority state.")
        if timeline.get("tick") != self.tick or timeline.get("observer_id") != self.observer_id:
            raise ValueError("Projection frame event_timeline must match frame tick and observer.")

    def to_dict(self) -> JsonDict:
        return {
            "frame_id": self.frame_id,
            "tick": self.tick,
            "observer_id": self.observer_id,
            "image_plane": _dict(self.image_plane),
            "samples": [sample.to_dict() for sample in self.samples],
            "phenomena_overlays": [overlay.to_dict() for overlay in self.phenomena_overlays],
            "source_state_ticks": _list(self.source_state_ticks),
            "source_object_ids": _list(self.source_object_ids),
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
            "audit": _dict(self.audit),
            "payload": _dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> ProjectionFrame:
        return cls(
            frame_id=data["frame_id"],
            tick=data["tick"],
            observer_id=data["observer_id"],
            image_plane=_dict(data["image_plane"]),
            samples=[ProjectionSample.from_dict(item) for item in data["samples"]],
            phenomena_overlays=[
                PhenomenonOverlay.from_dict(item)
                for item in data["phenomena_overlays"]
            ],
            source_state_ticks=_list(data["source_state_ticks"]),
            source_object_ids=_list(data["source_object_ids"]),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data["is_authority_state"],
            audit=_dict(data["audit"]),
            payload=_dict(data.get("payload")),
        )


@dataclass
class ProjectionCacheRecord:
    cache_id: str
    observer_id: str
    valid_from: int
    valid_to: int
    cache_scope: str
    is_authority_state: bool
    payload: JsonDict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.cache_scope != "observer_projection":
            raise ValueError("Projection cache scope must be observer_projection.")
        if self.is_authority_state:
            raise ValueError("Projection cache records cannot be authority state.")

    def to_dict(self) -> JsonDict:
        return {
            "cache_id": self.cache_id,
            "observer_id": self.observer_id,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "cache_scope": self.cache_scope,
            "is_authority_state": self.is_authority_state,
            "payload": _dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> ProjectionCacheRecord:
        return cls(
            cache_id=data["cache_id"],
            observer_id=data["observer_id"],
            valid_from=data["valid_from"],
            valid_to=data["valid_to"],
            cache_scope=data["cache_scope"],
            is_authority_state=data["is_authority_state"],
            payload=_dict(data.get("payload")),
        )


@dataclass
class InteractionCommand:
    command_id: str
    tick: int
    kind: str
    payload: JsonDict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.payload = _dict(self.payload)
        if self.kind == "field_affordance_patch":
            required_payload = {
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
                "region_clipped",
                "duration_ticks",
                "effect",
                "source_record_ids",
            }
            missing = sorted(required_payload - set(self.payload))
            if missing:
                raise ValueError("field_affordance_patch payload missing required fields: " + ", ".join(missing))
            if self.payload.get("schema") != "field_affordance_command_v1":
                raise ValueError("field_affordance_patch schema must be field_affordance_command_v1")
            if self.payload.get("origin_type") != "user_authored":
                raise ValueError("field_affordance_patch origin_type must be user_authored")
            if self.payload.get("affordance_kind") not in {
                "source_region",
                "dampening_region",
                "boundary_region",
                "material_region",
            }:
                raise ValueError("unsupported field_affordance_patch affordance_kind")
            if int(self.payload.get("duration_ticks", 0)) <= 0:
                raise ValueError("field_affordance_patch duration_ticks must be positive")
            effect = self.payload.get("effect")
            if not isinstance(effect, dict):
                raise ValueError("field_affordance_patch effect must be a dict")
            required_effect = {
                "source_bias",
                "damping_delta",
                "coupling_multiplier",
                "feed_rate_delta",
                "kill_rate_delta",
            }
            missing_effect = sorted(required_effect - set(effect))
            if missing_effect:
                raise ValueError("field_affordance_patch effect missing required fields: " + ", ".join(missing_effect))

    def to_dict(self) -> JsonDict:
        return {
            "command_id": self.command_id,
            "tick": self.tick,
            "kind": self.kind,
            "payload": _dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> InteractionCommand:
        return cls(
            command_id=data["command_id"],
            tick=data["tick"],
            kind=data["kind"],
            payload=_dict(data.get("payload")),
        )


@dataclass
class InteractionRequest:
    request_id: str
    observer_id: str
    frame_tick: int
    image_xy: list[float]
    tool: str = "local_field_source"
    radius_grid: int = 3
    amplitude: float = 0.4
    source_vector_image: list[float] = field(default_factory=lambda: [0.0, 0.0])
    payload: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "request_id": self.request_id,
            "observer_id": self.observer_id,
            "frame_tick": self.frame_tick,
            "image_xy": _list(self.image_xy),
            "tool": self.tool,
            "radius_grid": self.radius_grid,
            "amplitude": self.amplitude,
            "source_vector_image": _list(self.source_vector_image),
            "payload": _dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> InteractionRequest:
        payload = _dict(data.get("payload"))
        if "duration_ticks" in data and "duration_ticks" not in payload:
            payload["duration_ticks"] = data["duration_ticks"]
        return cls(
            request_id=data["request_id"],
            observer_id=data["observer_id"],
            frame_tick=data["frame_tick"],
            image_xy=_list(data["image_xy"]),
            tool=data.get("tool", "local_field_source"),
            radius_grid=int(data.get("radius_grid", data.get("radius", 3))),
            amplitude=float(data.get("amplitude", 0.4)),
            source_vector_image=_list(data.get("source_vector_image", [0.0, 0.0])),
            payload=payload,
        )


MACRO_ERROR_BOUND_DEFAULTS: JsonDict = {
    "centroid_grid_max_error_cells": 1.0,
    "support_iou_min": 0.70,
    "relative_energy_error_max": 0.15,
    "boundary_band_relative_error_max": 0.20,
    "component_count_delta_max": 0,
    "mode_signature_must_match": True,
}


def _validate_macro_error_bounds(error_bounds: JsonDict) -> None:
    required = set(MACRO_ERROR_BOUND_DEFAULTS) | {"centroid_world_max_error"}
    missing = sorted(required - set(error_bounds))
    if missing:
        raise ValueError("macro error_bounds missing required fields: " + ", ".join(missing))
    if float(error_bounds["centroid_grid_max_error_cells"]) > MACRO_ERROR_BOUND_DEFAULTS["centroid_grid_max_error_cells"]:
        raise ValueError("centroid_grid_max_error_cells is looser than the stage 1 default.")
    if float(error_bounds["support_iou_min"]) < MACRO_ERROR_BOUND_DEFAULTS["support_iou_min"]:
        raise ValueError("support_iou_min is looser than the stage 1 default.")
    if float(error_bounds["relative_energy_error_max"]) > MACRO_ERROR_BOUND_DEFAULTS["relative_energy_error_max"]:
        raise ValueError("relative_energy_error_max is looser than the stage 1 default.")
    if float(error_bounds["boundary_band_relative_error_max"]) > MACRO_ERROR_BOUND_DEFAULTS["boundary_band_relative_error_max"]:
        raise ValueError("boundary_band_relative_error_max is looser than the stage 1 default.")
    if int(error_bounds["component_count_delta_max"]) > MACRO_ERROR_BOUND_DEFAULTS["component_count_delta_max"]:
        raise ValueError("component_count_delta_max is looser than the stage 1 default.")
    if error_bounds["mode_signature_must_match"] is not True:
        raise ValueError("mode_signature_must_match must be true for stage 1 macro authority.")


def _validate_coordinate_frame_contract(coordinate_frame: JsonDict) -> None:
    required = {
        "world_origin",
        "world_extent",
        "grid_shape",
        "world_to_grid",
        "grid_to_world",
        "source_observer_window",
    }
    missing = sorted(required - set(coordinate_frame))
    if missing:
        raise ValueError("coordinate_frame missing required fields: " + ", ".join(missing))


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def canonical_json_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _ensure_finite_grid(channels: dict[str, list[list[float]]]) -> None:
    for name, grid in channels.items():
        for row in grid:
            for value in row:
                if not isfinite(float(value)):
                    raise ValueError(f"Channel {name} contains non-finite value.")


def summarize_compact_channels(channels: dict[str, list[list[float]]]) -> JsonDict:
    compact = _channels(channels)
    _ensure_finite_grid(compact)
    summaries: JsonDict = {}
    for name, grid in compact.items():
        energy = 0.0
        weighted_x = 0.0
        weighted_y = 0.0
        support: list[list[int]] = []
        for row_index, row in enumerate(grid):
            for col_index, value in enumerate(row):
                weight = float(value) * float(value)
                energy += weight
                if abs(float(value)) > 1e-12:
                    support.append([col_index, row_index])
                    weighted_x += col_index * weight
                    weighted_y += row_index * weight
        if support:
            min_x = min(cell[0] for cell in support)
            min_y = min(cell[1] for cell in support)
            max_x = max(cell[0] for cell in support)
            max_y = max(cell[1] for cell in support)
            centroid = [weighted_x / energy, weighted_y / energy] if energy else [0.0, 0.0]
            component_count = 1
        else:
            min_x = min_y = max_x = max_y = 0
            centroid = [0.0, 0.0]
            component_count = 0
        summaries[name] = {
            "energy": energy,
            "centroid_grid": centroid,
            "support_bounds_grid": [min_x, min_y, max_x, max_y],
            "boundary_band_energy": _boundary_band_energy(grid),
            "component_count": component_count,
            "mode_signature": f"mode::{name}:{len(grid)}x{len(grid[0]) if grid else 0}",
        }
    return {"channels": summaries}


def _boundary_band_energy(grid: list[list[float]]) -> float:
    if not grid:
        return 0.0
    height = len(grid)
    width = len(grid[0]) if grid[0] else 0
    energy = 0.0
    for row_index, row in enumerate(grid):
        for col_index, value in enumerate(row):
            if row_index in {0, height - 1} or col_index in {0, width - 1}:
                energy += float(value) * float(value)
    return energy


def _validate_non_authority(is_authority_state: bool, name: str) -> None:
    if _bool(is_authority_state):
        raise ValueError(f"{name} cannot be authority state.")


def _envelope_expands(parent: JsonDict, child: JsonDict) -> bool:
    parent_ticks = parent.get("tick_range", [])
    child_ticks = child.get("tick_range", [])
    if len(parent_ticks) == 2 and len(child_ticks) == 2:
        if int(child_ticks[0]) < int(parent_ticks[0]) or int(child_ticks[1]) > int(parent_ticks[1]):
            return True
    if "max_interaction_amplitude" in parent and "max_interaction_amplitude" in child:
        if float(child["max_interaction_amplitude"]) > float(parent["max_interaction_amplitude"]):
            return True
    if "max_observer_resolution" in parent and "max_observer_resolution" in child:
        if float(child["max_observer_resolution"]) < float(parent["max_observer_resolution"]):
            return True
    if parent.get("boundary_condition_digest") != child.get("boundary_condition_digest"):
        return True
    parent_affordances = set(parent.get("supported_affordance_kinds", []))
    child_affordances = set(child.get("supported_affordance_kinds", []))
    return not child_affordances.issubset(parent_affordances)


@dataclass
class StableStructureCertificate:
    certificate_id: str
    run_id: str
    component_id: str
    tick_range: list[int]
    coordinate_frame: JsonDict
    support_bounds_grid: list[float]
    support_bounds_world: list[float]
    source_field_state_ids: list[str]
    source_record_ids: list[str]
    metrics: JsonDict
    mode_signature: str
    validity_envelope: JsonDict
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.tick_range = _list(self.tick_range)
        self.coordinate_frame = _dict(self.coordinate_frame)
        self.support_bounds_grid = _list(self.support_bounds_grid)
        self.support_bounds_world = _list(self.support_bounds_world)
        self.source_field_state_ids = _list(self.source_field_state_ids)
        self.source_record_ids = _list(self.source_record_ids)
        self.metrics = _dict(self.metrics)
        self.validity_envelope = _dict(self.validity_envelope)
        if _bool(self.is_authority_state):
            raise ValueError("StableStructureCertificate cannot be authority state.")
        if not self.certificate_id:
            raise ValueError("StableStructureCertificate requires certificate_id.")
        if len(self.tick_range) != 2:
            raise ValueError("StableStructureCertificate tick_range must contain [start, end].")
        if not self.source_field_state_ids:
            raise ValueError("StableStructureCertificate requires source_field_state_ids.")
        if not self.source_record_ids:
            raise ValueError("StableStructureCertificate requires source_record_ids.")
        if not self.mode_signature:
            raise ValueError("StableStructureCertificate requires mode_signature.")
        _validate_coordinate_frame_contract(self.coordinate_frame)
        required_envelope = {
            "tick_range",
            "max_observer_resolution",
            "max_interaction_amplitude",
            "boundary_condition_digest",
            "supported_affordance_kinds",
        }
        missing_envelope = sorted(required_envelope - set(self.validity_envelope))
        if missing_envelope:
            raise ValueError("validity_envelope missing required fields: " + ", ".join(missing_envelope))

    def to_dict(self) -> JsonDict:
        return {
            "certificate_id": self.certificate_id,
            "run_id": self.run_id,
            "component_id": self.component_id,
            "tick_range": _list(self.tick_range),
            "coordinate_frame": _dict(self.coordinate_frame),
            "support_bounds_grid": _list(self.support_bounds_grid),
            "support_bounds_world": _list(self.support_bounds_world),
            "source_field_state_ids": _list(self.source_field_state_ids),
            "source_record_ids": _list(self.source_record_ids),
            "metrics": _dict(self.metrics),
            "mode_signature": self.mode_signature,
            "validity_envelope": _dict(self.validity_envelope),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> StableStructureCertificate:
        return cls(
            certificate_id=data["certificate_id"],
            run_id=data["run_id"],
            component_id=data["component_id"],
            tick_range=_list(data["tick_range"]),
            coordinate_frame=_dict(data["coordinate_frame"]),
            support_bounds_grid=_list(data["support_bounds_grid"]),
            support_bounds_world=_list(data["support_bounds_world"]),
            source_field_state_ids=_list(data["source_field_state_ids"]),
            source_record_ids=_list(data["source_record_ids"]),
            metrics=_dict(data["metrics"]),
            mode_signature=data["mode_signature"],
            validity_envelope=_dict(data["validity_envelope"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class MacroFieldState:
    macro_state_id: str
    run_id: str
    tick_range: list[int]
    coordinate_frame: JsonDict
    support_bounds_grid: list[float]
    support_bounds_world: list[float]
    source_field_state_ids: list[str]
    source_record_ids: list[str]
    invariants: JsonDict
    boundary_response: JsonDict
    reconstruction_recipe: JsonDict
    error_bounds: JsonDict
    certificate_id: str
    is_authority_state: bool = True

    def __post_init__(self) -> None:
        self.tick_range = _list(self.tick_range)
        self.coordinate_frame = _dict(self.coordinate_frame)
        self.support_bounds_grid = _list(self.support_bounds_grid)
        self.support_bounds_world = _list(self.support_bounds_world)
        self.source_field_state_ids = _list(self.source_field_state_ids)
        self.source_record_ids = _list(self.source_record_ids)
        self.invariants = _dict(self.invariants)
        self.boundary_response = _dict(self.boundary_response)
        self.reconstruction_recipe = _dict(self.reconstruction_recipe)
        self.error_bounds = _dict(self.error_bounds)
        if not _bool(self.is_authority_state):
            raise ValueError("MacroFieldState must be authority state.")
        if not self.macro_state_id:
            raise ValueError("MacroFieldState requires macro_state_id.")
        if not self.certificate_id:
            raise ValueError("MacroFieldState requires certificate_id.")
        if not self.source_field_state_ids:
            raise ValueError("MacroFieldState requires source_field_state_ids.")
        if not self.source_record_ids:
            raise ValueError("MacroFieldState requires source_record_ids.")
        if len(self.tick_range) != 2:
            raise ValueError("MacroFieldState tick_range must contain [start, end].")
        _validate_coordinate_frame_contract(self.coordinate_frame)
        _validate_macro_error_bounds(self.error_bounds)
        required_recipe = {"method", "source_field_state_ids", "coordinate_frame"}
        missing_recipe = sorted(required_recipe - set(self.reconstruction_recipe))
        if missing_recipe:
            raise ValueError("reconstruction_recipe missing required fields: " + ", ".join(missing_recipe))

    def to_dict(self) -> JsonDict:
        return {
            "macro_state_id": self.macro_state_id,
            "run_id": self.run_id,
            "tick_range": _list(self.tick_range),
            "coordinate_frame": _dict(self.coordinate_frame),
            "support_bounds_grid": _list(self.support_bounds_grid),
            "support_bounds_world": _list(self.support_bounds_world),
            "source_field_state_ids": _list(self.source_field_state_ids),
            "source_record_ids": _list(self.source_record_ids),
            "invariants": _dict(self.invariants),
            "boundary_response": _dict(self.boundary_response),
            "reconstruction_recipe": _dict(self.reconstruction_recipe),
            "error_bounds": _dict(self.error_bounds),
            "certificate_id": self.certificate_id,
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> MacroFieldState:
        return cls(
            macro_state_id=data["macro_state_id"],
            run_id=data["run_id"],
            tick_range=_list(data["tick_range"]),
            coordinate_frame=_dict(data["coordinate_frame"]),
            support_bounds_grid=_list(data["support_bounds_grid"]),
            support_bounds_world=_list(data["support_bounds_world"]),
            source_field_state_ids=_list(data["source_field_state_ids"]),
            source_record_ids=_list(data["source_record_ids"]),
            invariants=_dict(data["invariants"]),
            boundary_response=_dict(data["boundary_response"]),
            reconstruction_recipe=_dict(data["reconstruction_recipe"]),
            error_bounds=_dict(data["error_bounds"]),
            certificate_id=data["certificate_id"],
            is_authority_state=data.get("is_authority_state", True),
        )


@dataclass
class FineRefinementRequest:
    request_id: str
    tick: int
    trigger_kind: str
    source_macro_state_id: str
    observer_id: str
    interaction_record_ids: list[str]
    command_ids: list[str]
    requested_region_grid: list[float]
    requested_region_world: list[float]
    coordinate_frame: JsonDict
    requested_resolution: JsonDict
    reason: str
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.interaction_record_ids = _list(self.interaction_record_ids)
        self.command_ids = _list(self.command_ids)
        self.requested_region_grid = _list(self.requested_region_grid)
        self.requested_region_world = _list(self.requested_region_world)
        self.coordinate_frame = _dict(self.coordinate_frame)
        self.requested_resolution = _dict(self.requested_resolution)
        self.source_record_ids = _list(self.source_record_ids)
        if _bool(self.is_authority_state):
            raise ValueError("FineRefinementRequest cannot be authority state.")
        if not self.request_id:
            raise ValueError("FineRefinementRequest requires request_id.")
        if not self.source_macro_state_id:
            raise ValueError("FineRefinementRequest requires source_macro_state_id.")
        if len(self.requested_region_grid) != 4 or len(self.requested_region_world) != 4:
            raise ValueError("FineRefinementRequest regions must contain [x0, y0, x1, y1].")
        if not self.source_record_ids:
            raise ValueError("FineRefinementRequest requires source_record_ids.")
        _validate_coordinate_frame_contract(self.coordinate_frame)

    def to_dict(self) -> JsonDict:
        return {
            "request_id": self.request_id,
            "tick": self.tick,
            "trigger_kind": self.trigger_kind,
            "source_macro_state_id": self.source_macro_state_id,
            "observer_id": self.observer_id,
            "interaction_record_ids": _list(self.interaction_record_ids),
            "command_ids": _list(self.command_ids),
            "requested_region_grid": _list(self.requested_region_grid),
            "requested_region_world": _list(self.requested_region_world),
            "coordinate_frame": _dict(self.coordinate_frame),
            "requested_resolution": _dict(self.requested_resolution),
            "reason": self.reason,
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> FineRefinementRequest:
        return cls(
            request_id=data["request_id"],
            tick=data["tick"],
            trigger_kind=data["trigger_kind"],
            source_macro_state_id=data["source_macro_state_id"],
            observer_id=data["observer_id"],
            interaction_record_ids=_list(data["interaction_record_ids"]),
            command_ids=_list(data["command_ids"]),
            requested_region_grid=_list(data["requested_region_grid"]),
            requested_region_world=_list(data["requested_region_world"]),
            coordinate_frame=_dict(data["coordinate_frame"]),
            requested_resolution=_dict(data["requested_resolution"]),
            reason=data["reason"],
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class FineRefinementPatch:
    patch_id: str
    macro_state_id: str
    refinement_request_id: str
    tick: int
    region_grid: list[float]
    channels: dict[str, list[list[float]]]
    boundary_conditions: JsonDict
    lifting_recipe: JsonDict
    source_record_ids: list[str]

    def __post_init__(self) -> None:
        self.region_grid = _list(self.region_grid)
        self.channels = _channels(self.channels)
        self.boundary_conditions = _dict(self.boundary_conditions)
        self.lifting_recipe = _dict(self.lifting_recipe)
        self.source_record_ids = _list(self.source_record_ids)
        if not self.patch_id:
            raise ValueError("FineRefinementPatch requires patch_id.")
        if not self.macro_state_id:
            raise ValueError("FineRefinementPatch requires macro_state_id.")
        if not self.refinement_request_id:
            raise ValueError("FineRefinementPatch requires refinement_request_id.")
        if len(self.region_grid) != 4:
            raise ValueError("FineRefinementPatch region_grid must contain [x0, y0, x1, y1].")
        if not self.channels:
            raise ValueError("FineRefinementPatch requires channels.")
        if not self.source_record_ids:
            raise ValueError("FineRefinementPatch requires source_record_ids.")

    def to_dict(self) -> JsonDict:
        return {
            "patch_id": self.patch_id,
            "macro_state_id": self.macro_state_id,
            "refinement_request_id": self.refinement_request_id,
            "tick": self.tick,
            "region_grid": _list(self.region_grid),
            "channels": _channels(self.channels),
            "boundary_conditions": _dict(self.boundary_conditions),
            "lifting_recipe": _dict(self.lifting_recipe),
            "source_record_ids": _list(self.source_record_ids),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> FineRefinementPatch:
        return cls(
            patch_id=data["patch_id"],
            macro_state_id=data["macro_state_id"],
            refinement_request_id=data["refinement_request_id"],
            tick=data["tick"],
            region_grid=_list(data["region_grid"]),
            channels=_channels(data["channels"]),
            boundary_conditions=_dict(data["boundary_conditions"]),
            lifting_recipe=_dict(data["lifting_recipe"]),
            source_record_ids=_list(data["source_record_ids"]),
        )


@dataclass
class MacroEvolutionRecord:
    record_id: str
    tick: int
    previous_macro_state_id: str
    current_macro_state_id: str
    coarse_rule_id: str
    certificate_id: str
    boundary_exchange: JsonDict
    error_budget: JsonDict
    validity_envelope: JsonDict
    source_record_ids: list[str]

    def __post_init__(self) -> None:
        self.boundary_exchange = _dict(self.boundary_exchange)
        self.error_budget = _dict(self.error_budget)
        self.validity_envelope = _dict(self.validity_envelope)
        self.source_record_ids = _list(self.source_record_ids)
        if not self.record_id:
            raise ValueError("MacroEvolutionRecord requires record_id.")
        if not self.previous_macro_state_id or not self.current_macro_state_id:
            raise ValueError("MacroEvolutionRecord requires previous/current macro ids.")
        if not self.coarse_rule_id:
            raise ValueError("MacroEvolutionRecord requires coarse_rule_id.")
        if not self.certificate_id:
            raise ValueError("MacroEvolutionRecord requires certificate_id.")
        if not self.source_record_ids:
            raise ValueError("MacroEvolutionRecord requires source_record_ids.")
        _validate_macro_error_bounds(self.error_budget)

    def to_dict(self) -> JsonDict:
        return {
            "record_id": self.record_id,
            "tick": self.tick,
            "previous_macro_state_id": self.previous_macro_state_id,
            "current_macro_state_id": self.current_macro_state_id,
            "coarse_rule_id": self.coarse_rule_id,
            "certificate_id": self.certificate_id,
            "boundary_exchange": _dict(self.boundary_exchange),
            "error_budget": _dict(self.error_budget),
            "validity_envelope": _dict(self.validity_envelope),
            "source_record_ids": _list(self.source_record_ids),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> MacroEvolutionRecord:
        return cls(
            record_id=data["record_id"],
            tick=data["tick"],
            previous_macro_state_id=data["previous_macro_state_id"],
            current_macro_state_id=data["current_macro_state_id"],
            coarse_rule_id=data["coarse_rule_id"],
            certificate_id=data["certificate_id"],
            boundary_exchange=_dict(data["boundary_exchange"]),
            error_budget=_dict(data["error_budget"]),
            validity_envelope=_dict(data["validity_envelope"]),
            source_record_ids=_list(data["source_record_ids"]),
        )


@dataclass
class MacroProjectionRecord:
    record_id: str
    tick: int
    source_macro_state_id: str
    macro_certificate_id: str
    projection_frame_ids: list[str]
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.projection_frame_ids = _list(self.projection_frame_ids)
        self.source_record_ids = _list(self.source_record_ids)
        if _bool(self.is_authority_state):
            raise ValueError("MacroProjectionRecord cannot be authority state.")
        if not self.record_id:
            raise ValueError("MacroProjectionRecord requires record_id.")
        if not self.source_macro_state_id:
            raise ValueError("MacroProjectionRecord requires source_macro_state_id.")
        if not self.macro_certificate_id:
            raise ValueError("MacroProjectionRecord requires macro_certificate_id.")
        if not self.projection_frame_ids:
            raise ValueError("MacroProjectionRecord requires projection_frame_ids.")
        if not self.source_record_ids:
            raise ValueError("MacroProjectionRecord requires source_record_ids.")

    def to_dict(self) -> JsonDict:
        return {
            "record_id": self.record_id,
            "tick": self.tick,
            "source_macro_state_id": self.source_macro_state_id,
            "macro_certificate_id": self.macro_certificate_id,
            "projection_frame_ids": _list(self.projection_frame_ids),
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> MacroProjectionRecord:
        return cls(
            record_id=data["record_id"],
            tick=data["tick"],
            source_macro_state_id=data["source_macro_state_id"],
            macro_certificate_id=data["macro_certificate_id"],
            projection_frame_ids=_list(data["projection_frame_ids"]),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class FinePatchStateSnapshot:
    snapshot_id: str
    run_id: str
    patch_id: str
    tick: int
    step_index: int
    region_grid: list[float]
    coordinate_frame: JsonDict
    channels_compact: dict[str, list[list[float]]]
    channels_digest: str
    summary_digest: str
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.region_grid = _list(self.region_grid)
        self.coordinate_frame = _dict(self.coordinate_frame)
        self.channels_compact = _channels(self.channels_compact)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "FinePatchStateSnapshot")
        if not self.snapshot_id:
            raise ValueError("FinePatchStateSnapshot requires snapshot_id.")
        if not self.patch_id:
            raise ValueError("FinePatchStateSnapshot requires patch_id.")
        if len(self.region_grid) != 4:
            raise ValueError("FinePatchStateSnapshot region_grid must contain [x0, y0, x1, y1].")
        if not self.channels_compact:
            raise ValueError("FinePatchStateSnapshot requires channels_compact.")
        if not self.source_record_ids:
            raise ValueError("FinePatchStateSnapshot requires source_record_ids.")
        _validate_coordinate_frame_contract(self.coordinate_frame)
        _ensure_finite_grid(self.channels_compact)
        expected_channels_digest = canonical_json_digest(self.channels_compact)
        if self.channels_digest != expected_channels_digest:
            raise ValueError("FinePatchStateSnapshot channels_digest mismatch.")
        expected_summary_digest = canonical_json_digest(summarize_compact_channels(self.channels_compact))
        if self.summary_digest != expected_summary_digest:
            raise ValueError("FinePatchStateSnapshot summary_digest mismatch.")

    def to_dict(self) -> JsonDict:
        return {
            "snapshot_id": self.snapshot_id,
            "run_id": self.run_id,
            "patch_id": self.patch_id,
            "tick": self.tick,
            "step_index": self.step_index,
            "region_grid": _list(self.region_grid),
            "coordinate_frame": _dict(self.coordinate_frame),
            "channels_compact": _channels(self.channels_compact),
            "channels_digest": self.channels_digest,
            "summary_digest": self.summary_digest,
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> FinePatchStateSnapshot:
        return cls(
            snapshot_id=data["snapshot_id"],
            run_id=data["run_id"],
            patch_id=data["patch_id"],
            tick=data["tick"],
            step_index=data["step_index"],
            region_grid=_list(data["region_grid"]),
            coordinate_frame=_dict(data["coordinate_frame"]),
            channels_compact=_channels(data["channels_compact"]),
            channels_digest=data["channels_digest"],
            summary_digest=data["summary_digest"],
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class FinePatchStepRecord:
    record_id: str
    run_id: str
    tick: int
    patch_id: str
    previous_snapshot_id: str
    current_snapshot_id: str
    fine_rule_id: str
    coordinate_frame: JsonDict
    region_grid: list[float]
    boundary_condition_digest: str
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.coordinate_frame = _dict(self.coordinate_frame)
        self.region_grid = _list(self.region_grid)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "FinePatchStepRecord")
        if not self.record_id:
            raise ValueError("FinePatchStepRecord requires record_id.")
        if not self.patch_id:
            raise ValueError("FinePatchStepRecord requires patch_id.")
        if not self.previous_snapshot_id or not self.current_snapshot_id:
            raise ValueError("FinePatchStepRecord requires previous/current snapshot ids.")
        if not self.fine_rule_id:
            raise ValueError("FinePatchStepRecord requires fine_rule_id.")
        if len(self.region_grid) != 4:
            raise ValueError("FinePatchStepRecord region_grid must contain [x0, y0, x1, y1].")
        if not self.boundary_condition_digest:
            raise ValueError("FinePatchStepRecord requires boundary_condition_digest.")
        if not self.source_record_ids:
            raise ValueError("FinePatchStepRecord requires source_record_ids.")
        _validate_coordinate_frame_contract(self.coordinate_frame)

    def to_dict(self) -> JsonDict:
        return {
            "record_id": self.record_id,
            "run_id": self.run_id,
            "tick": self.tick,
            "patch_id": self.patch_id,
            "previous_snapshot_id": self.previous_snapshot_id,
            "current_snapshot_id": self.current_snapshot_id,
            "fine_rule_id": self.fine_rule_id,
            "coordinate_frame": _dict(self.coordinate_frame),
            "region_grid": _list(self.region_grid),
            "boundary_condition_digest": self.boundary_condition_digest,
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> FinePatchStepRecord:
        return cls(
            record_id=data["record_id"],
            run_id=data["run_id"],
            tick=data["tick"],
            patch_id=data["patch_id"],
            previous_snapshot_id=data["previous_snapshot_id"],
            current_snapshot_id=data["current_snapshot_id"],
            fine_rule_id=data["fine_rule_id"],
            coordinate_frame=_dict(data["coordinate_frame"]),
            region_grid=_list(data["region_grid"]),
            boundary_condition_digest=data["boundary_condition_digest"],
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class FinePatchOutcome:
    outcome_id: str
    run_id: str
    patch_id: str
    fine_refinement_request_id: str
    source_macro_state_id: str
    start_tick: int
    end_tick: int
    region_grid: list[float]
    coordinate_frame: JsonDict
    initial_snapshot_id: str
    final_snapshot_id: str
    final_patch_channels_digest: str
    raw_channel_summary: JsonDict
    error_metrics: JsonDict
    boundary_flux: JsonDict
    fine_patch_step_record_ids: list[str]
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.region_grid = _list(self.region_grid)
        self.coordinate_frame = _dict(self.coordinate_frame)
        self.raw_channel_summary = _dict(self.raw_channel_summary)
        self.error_metrics = _dict(self.error_metrics)
        self.boundary_flux = _dict(self.boundary_flux)
        self.fine_patch_step_record_ids = _list(self.fine_patch_step_record_ids)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "FinePatchOutcome")
        if not self.outcome_id:
            raise ValueError("FinePatchOutcome requires outcome_id.")
        if not self.patch_id:
            raise ValueError("FinePatchOutcome requires patch_id.")
        if not self.fine_refinement_request_id:
            raise ValueError("FinePatchOutcome requires fine_refinement_request_id.")
        if not self.source_macro_state_id:
            raise ValueError("FinePatchOutcome requires source_macro_state_id.")
        if not self.initial_snapshot_id or not self.final_snapshot_id:
            raise ValueError("FinePatchOutcome requires initial/final snapshot ids.")
        if not self.final_patch_channels_digest:
            raise ValueError("FinePatchOutcome requires final_patch_channels_digest.")
        if len(self.region_grid) != 4:
            raise ValueError("FinePatchOutcome region_grid must contain [x0, y0, x1, y1].")
        if not self.source_record_ids:
            raise ValueError("FinePatchOutcome requires source_record_ids.")
        if not self.fine_patch_step_record_ids:
            if self.start_tick != self.end_tick or self.raw_channel_summary.get("trigger_kind") != "observation_only":
                raise ValueError("FinePatchOutcome without steps must be observation_only with matching start/end tick.")
        _validate_coordinate_frame_contract(self.coordinate_frame)

    def to_dict(self) -> JsonDict:
        return {
            "outcome_id": self.outcome_id,
            "run_id": self.run_id,
            "patch_id": self.patch_id,
            "fine_refinement_request_id": self.fine_refinement_request_id,
            "source_macro_state_id": self.source_macro_state_id,
            "start_tick": self.start_tick,
            "end_tick": self.end_tick,
            "region_grid": _list(self.region_grid),
            "coordinate_frame": _dict(self.coordinate_frame),
            "initial_snapshot_id": self.initial_snapshot_id,
            "final_snapshot_id": self.final_snapshot_id,
            "final_patch_channels_digest": self.final_patch_channels_digest,
            "raw_channel_summary": _dict(self.raw_channel_summary),
            "error_metrics": _dict(self.error_metrics),
            "boundary_flux": _dict(self.boundary_flux),
            "fine_patch_step_record_ids": _list(self.fine_patch_step_record_ids),
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> FinePatchOutcome:
        return cls(
            outcome_id=data["outcome_id"],
            run_id=data["run_id"],
            patch_id=data["patch_id"],
            fine_refinement_request_id=data["fine_refinement_request_id"],
            source_macro_state_id=data["source_macro_state_id"],
            start_tick=data["start_tick"],
            end_tick=data["end_tick"],
            region_grid=_list(data["region_grid"]),
            coordinate_frame=_dict(data["coordinate_frame"]),
            initial_snapshot_id=data["initial_snapshot_id"],
            final_snapshot_id=data["final_snapshot_id"],
            final_patch_channels_digest=data["final_patch_channels_digest"],
            raw_channel_summary=_dict(data["raw_channel_summary"]),
            error_metrics=_dict(data["error_metrics"]),
            boundary_flux=_dict(data["boundary_flux"]),
            fine_patch_step_record_ids=_list(data["fine_patch_step_record_ids"]),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class MacroCorrectionRecord:
    correction_id: str
    run_id: str
    tick: int
    pre_correction_macro_state_id: str
    post_correction_macro_state_id: str
    source_macro_state_id: str
    source_fine_patch_id: str
    fine_patch_outcome_id: str
    fine_refinement_request_id: str
    certificate_id: str
    correction_certificate_extension_id: str
    correction_operator: str
    error_metrics: JsonDict
    boundary_flux: JsonDict
    validity_envelope_delta: JsonDict
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.error_metrics = _dict(self.error_metrics)
        self.boundary_flux = _dict(self.boundary_flux)
        self.validity_envelope_delta = _dict(self.validity_envelope_delta)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "MacroCorrectionRecord")
        required = [
            self.correction_id,
            self.pre_correction_macro_state_id,
            self.post_correction_macro_state_id,
            self.source_macro_state_id,
            self.source_fine_patch_id,
            self.fine_patch_outcome_id,
            self.fine_refinement_request_id,
            self.certificate_id,
            self.correction_certificate_extension_id,
            self.correction_operator,
        ]
        if any(not value for value in required):
            raise ValueError("MacroCorrectionRecord missing required id field.")
        if not self.source_record_ids:
            raise ValueError("MacroCorrectionRecord requires source_record_ids.")

    def to_dict(self) -> JsonDict:
        return {
            "correction_id": self.correction_id,
            "run_id": self.run_id,
            "tick": self.tick,
            "pre_correction_macro_state_id": self.pre_correction_macro_state_id,
            "post_correction_macro_state_id": self.post_correction_macro_state_id,
            "source_macro_state_id": self.source_macro_state_id,
            "source_fine_patch_id": self.source_fine_patch_id,
            "fine_patch_outcome_id": self.fine_patch_outcome_id,
            "fine_refinement_request_id": self.fine_refinement_request_id,
            "certificate_id": self.certificate_id,
            "correction_certificate_extension_id": self.correction_certificate_extension_id,
            "correction_operator": self.correction_operator,
            "error_metrics": _dict(self.error_metrics),
            "boundary_flux": _dict(self.boundary_flux),
            "validity_envelope_delta": _dict(self.validity_envelope_delta),
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> MacroCorrectionRecord:
        return cls(
            correction_id=data["correction_id"],
            run_id=data["run_id"],
            tick=data["tick"],
            pre_correction_macro_state_id=data["pre_correction_macro_state_id"],
            post_correction_macro_state_id=data["post_correction_macro_state_id"],
            source_macro_state_id=data["source_macro_state_id"],
            source_fine_patch_id=data["source_fine_patch_id"],
            fine_patch_outcome_id=data["fine_patch_outcome_id"],
            fine_refinement_request_id=data["fine_refinement_request_id"],
            certificate_id=data["certificate_id"],
            correction_certificate_extension_id=data["correction_certificate_extension_id"],
            correction_operator=data["correction_operator"],
            error_metrics=_dict(data["error_metrics"]),
            boundary_flux=_dict(data["boundary_flux"]),
            validity_envelope_delta=_dict(data["validity_envelope_delta"]),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class MacroCorrectionCertificateExtension:
    extension_id: str
    run_id: str
    parent_certificate_id: str
    pre_correction_macro_state_id: str
    post_correction_macro_state_id: str
    macro_correction_record_id: str
    fine_patch_outcome_id: str
    inherited_validity_envelope: JsonDict
    post_correction_validity_envelope: JsonDict
    error_bounds: JsonDict
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.inherited_validity_envelope = _dict(self.inherited_validity_envelope)
        self.post_correction_validity_envelope = _dict(self.post_correction_validity_envelope)
        self.error_bounds = _dict(self.error_bounds)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "MacroCorrectionCertificateExtension")
        required = [
            self.extension_id,
            self.parent_certificate_id,
            self.pre_correction_macro_state_id,
            self.post_correction_macro_state_id,
            self.macro_correction_record_id,
            self.fine_patch_outcome_id,
        ]
        if any(not value for value in required):
            raise ValueError("MacroCorrectionCertificateExtension missing required id field.")
        if not self.source_record_ids:
            raise ValueError("MacroCorrectionCertificateExtension requires source_record_ids.")
        _validate_macro_error_bounds(self.error_bounds)
        if _envelope_expands(self.inherited_validity_envelope, self.post_correction_validity_envelope):
            raise ValueError("MacroCorrectionCertificateExtension cannot expand parent validity envelope.")

    def to_dict(self) -> JsonDict:
        return {
            "extension_id": self.extension_id,
            "run_id": self.run_id,
            "parent_certificate_id": self.parent_certificate_id,
            "pre_correction_macro_state_id": self.pre_correction_macro_state_id,
            "post_correction_macro_state_id": self.post_correction_macro_state_id,
            "macro_correction_record_id": self.macro_correction_record_id,
            "fine_patch_outcome_id": self.fine_patch_outcome_id,
            "inherited_validity_envelope": _dict(self.inherited_validity_envelope),
            "post_correction_validity_envelope": _dict(self.post_correction_validity_envelope),
            "error_bounds": _dict(self.error_bounds),
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> MacroCorrectionCertificateExtension:
        return cls(
            extension_id=data["extension_id"],
            run_id=data["run_id"],
            parent_certificate_id=data["parent_certificate_id"],
            pre_correction_macro_state_id=data["pre_correction_macro_state_id"],
            post_correction_macro_state_id=data["post_correction_macro_state_id"],
            macro_correction_record_id=data["macro_correction_record_id"],
            fine_patch_outcome_id=data["fine_patch_outcome_id"],
            inherited_validity_envelope=_dict(data["inherited_validity_envelope"]),
            post_correction_validity_envelope=_dict(data["post_correction_validity_envelope"]),
            error_bounds=_dict(data["error_bounds"]),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class MacroBoundaryExchangeRecord:
    exchange_id: str
    run_id: str
    tick: int
    source_macro_state_ids: list[str]
    affected_macro_state_ids: list[str]
    exchange_pairs: list[JsonDict]
    boundary_condition_digest: str
    energy_flux_by_pair: JsonDict
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.source_macro_state_ids = _list(self.source_macro_state_ids)
        self.affected_macro_state_ids = _list(self.affected_macro_state_ids)
        self.exchange_pairs = [_dict(pair) for pair in self.exchange_pairs]
        self.energy_flux_by_pair = _dict(self.energy_flux_by_pair)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "MacroBoundaryExchangeRecord")
        if not self.exchange_id:
            raise ValueError("MacroBoundaryExchangeRecord requires exchange_id.")
        if not self.source_macro_state_ids or not self.affected_macro_state_ids:
            raise ValueError("MacroBoundaryExchangeRecord requires source/affected macro ids.")
        if not self.exchange_pairs:
            raise ValueError("MacroBoundaryExchangeRecord requires exchange_pairs.")
        if not self.boundary_condition_digest:
            raise ValueError("MacroBoundaryExchangeRecord requires boundary_condition_digest.")
        if not self.source_record_ids:
            raise ValueError("MacroBoundaryExchangeRecord requires source_record_ids.")

    def to_dict(self) -> JsonDict:
        return {
            "exchange_id": self.exchange_id,
            "run_id": self.run_id,
            "tick": self.tick,
            "source_macro_state_ids": _list(self.source_macro_state_ids),
            "affected_macro_state_ids": _list(self.affected_macro_state_ids),
            "exchange_pairs": [_dict(pair) for pair in self.exchange_pairs],
            "boundary_condition_digest": self.boundary_condition_digest,
            "energy_flux_by_pair": _dict(self.energy_flux_by_pair),
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> MacroBoundaryExchangeRecord:
        return cls(
            exchange_id=data["exchange_id"],
            run_id=data["run_id"],
            tick=data["tick"],
            source_macro_state_ids=_list(data["source_macro_state_ids"]),
            affected_macro_state_ids=_list(data["affected_macro_state_ids"]),
            exchange_pairs=[_dict(pair) for pair in data["exchange_pairs"]],
            boundary_condition_digest=data["boundary_condition_digest"],
            energy_flux_by_pair=_dict(data["energy_flux_by_pair"]),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


REGION_AUTHORITY_MODES = {
    "cold_macro",
    "warm_macro",
    "active_fine",
    "refining",
    "invalidated",
}

REGION_TRIGGER_KINDS = {
    "observer_window_enter",
    "observer_resolution",
    "local_interaction",
    "boundary_uncertainty",
    "reentry_replay",
    "budget_eviction",
    "macro_invalidated",
}

REGION_TRANSITION_PAIRS = {
    "cold_to_refining": ("cold_macro", "refining"),
    "warm_to_refining": ("warm_macro", "refining"),
    "invalidated_to_refining": ("invalidated", "refining"),
    "refining_to_active": ("refining", "active_fine"),
    "active_to_warm": ("active_fine", "warm_macro"),
    "warm_to_cold": ("warm_macro", "cold_macro"),
    "cold_to_warm": ("cold_macro", "warm_macro"),
    "active_to_invalidated": ("active_fine", "invalidated"),
    "warm_to_invalidated": ("warm_macro", "invalidated"),
    "cold_to_invalidated": ("cold_macro", "invalidated"),
    "refining_to_invalidated": ("refining", "invalidated"),
}

REGION_ERROR_BOUND_DEFAULTS: JsonDict = {
    "centroid_world_distance_max": 1.5,
    "centroid_grid_distance_max": 1.0,
    "support_iou_min": 0.82,
    "relative_energy_error_max": 0.08,
    "boundary_band_relative_error_max": 0.10,
    "component_count_delta_max": 1,
    "mode_signature_hamming_max": 2,
}

REGION_BUDGET_DEFAULTS: JsonDict = {
    "max_active_fine_regions": 4,
    "max_refinements_per_tick": 2,
    "max_fine_steps_per_tick": 16,
    "per_case_compact_budget_bytes": 16_000_000,
    "total_report_budget_bytes": 96_000_000,
}

REGION_BUDGET_STATUSES = {"passed", "failed", "learning_mode_required"}

REGION_BOUNDARY_EXCHANGE_KINDS = {
    "macro_macro_exchange",
    "fine_macro_exchange",
    "macro_fine_exchange",
    "fine_fine_exchange",
    "strong_overlap_invalidation",
    "merge_split_invalidation",
}

REGION_INVALIDATION_EXCHANGE_KINDS = {
    "strong_overlap_invalidation",
    "merge_split_invalidation",
}


def _validate_bounds4(value: list[Any], name: str) -> None:
    if len(value) != 4:
        raise ValueError(f"{name} must contain [x0, y0, x1, y1].")
    if float(value[2]) < float(value[0]) or float(value[3]) < float(value[1]):
        raise ValueError(f"{name} max bounds must be >= min bounds.")


def _validate_region_error_bounds(error_bounds: JsonDict) -> None:
    missing = sorted(set(REGION_ERROR_BOUND_DEFAULTS) - set(error_bounds))
    if missing:
        raise ValueError("RegionValidityEnvelope error_bounds missing required fields: " + ", ".join(missing))
    if float(error_bounds["centroid_world_distance_max"]) > REGION_ERROR_BOUND_DEFAULTS["centroid_world_distance_max"]:
        raise ValueError("centroid_world_distance_max is looser than the stage 1 default.")
    if float(error_bounds["centroid_grid_distance_max"]) > REGION_ERROR_BOUND_DEFAULTS["centroid_grid_distance_max"]:
        raise ValueError("centroid_grid_distance_max is looser than the stage 1 default.")
    if float(error_bounds["support_iou_min"]) < REGION_ERROR_BOUND_DEFAULTS["support_iou_min"]:
        raise ValueError("support_iou_min is looser than the stage 1 default.")
    if float(error_bounds["relative_energy_error_max"]) > REGION_ERROR_BOUND_DEFAULTS["relative_energy_error_max"]:
        raise ValueError("relative_energy_error_max is looser than the stage 1 default.")
    if float(error_bounds["boundary_band_relative_error_max"]) > REGION_ERROR_BOUND_DEFAULTS["boundary_band_relative_error_max"]:
        raise ValueError("boundary_band_relative_error_max is looser than the stage 1 default.")
    if int(error_bounds["component_count_delta_max"]) > REGION_ERROR_BOUND_DEFAULTS["component_count_delta_max"]:
        raise ValueError("component_count_delta_max is looser than the stage 1 default.")
    if int(error_bounds["mode_signature_hamming_max"]) > REGION_ERROR_BOUND_DEFAULTS["mode_signature_hamming_max"]:
        raise ValueError("mode_signature_hamming_max is looser than the stage 1 default.")


def _coerce_region_validity_envelope(value: Any) -> RegionValidityEnvelope:
    if isinstance(value, RegionValidityEnvelope):
        return value
    if isinstance(value, dict):
        return RegionValidityEnvelope.from_dict(value)
    raise ValueError("validity_envelope must be RegionValidityEnvelope.")


def _coerce_region_budget_policy(value: Any) -> RegionBudgetPolicy:
    if isinstance(value, RegionBudgetPolicy):
        return value
    if isinstance(value, dict):
        return RegionBudgetPolicy.from_dict(value)
    raise ValueError("budget_policy must be RegionBudgetPolicy.")


@dataclass
class RegionValidityEnvelope:
    envelope_id: str
    region_id: str
    coordinate_frame: JsonDict
    tick_start: int
    tick_end: int
    observer_resolution_limit: float
    interaction_strength_limit: float
    boundary_condition_digest: str
    error_bounds: JsonDict
    source_certificate_ids: list[str]
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.coordinate_frame = _dict(self.coordinate_frame)
        self.error_bounds = _dict(self.error_bounds)
        self.source_certificate_ids = _list(self.source_certificate_ids)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "RegionValidityEnvelope")
        if not self.envelope_id or not self.region_id:
            raise ValueError("RegionValidityEnvelope requires envelope_id and region_id.")
        _validate_coordinate_frame_contract(self.coordinate_frame)
        if int(self.tick_end) < int(self.tick_start):
            raise ValueError("RegionValidityEnvelope tick_end must be >= tick_start.")
        if float(self.observer_resolution_limit) <= 0:
            raise ValueError("RegionValidityEnvelope observer_resolution_limit must be > 0.")
        if float(self.interaction_strength_limit) < 0:
            raise ValueError("RegionValidityEnvelope interaction_strength_limit must be >= 0.")
        if not self.boundary_condition_digest:
            raise ValueError("RegionValidityEnvelope requires boundary_condition_digest.")
        if not self.source_certificate_ids or not self.source_record_ids:
            raise ValueError("RegionValidityEnvelope requires source certificate and record lineage.")
        _validate_region_error_bounds(self.error_bounds)

    def to_dict(self) -> JsonDict:
        return {
            "envelope_id": self.envelope_id,
            "region_id": self.region_id,
            "coordinate_frame": _dict(self.coordinate_frame),
            "tick_start": self.tick_start,
            "tick_end": self.tick_end,
            "observer_resolution_limit": self.observer_resolution_limit,
            "interaction_strength_limit": self.interaction_strength_limit,
            "boundary_condition_digest": self.boundary_condition_digest,
            "error_bounds": _dict(self.error_bounds),
            "source_certificate_ids": _list(self.source_certificate_ids),
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> RegionValidityEnvelope:
        return cls(
            envelope_id=data["envelope_id"],
            region_id=data["region_id"],
            coordinate_frame=_dict(data["coordinate_frame"]),
            tick_start=data["tick_start"],
            tick_end=data["tick_end"],
            observer_resolution_limit=data["observer_resolution_limit"],
            interaction_strength_limit=data["interaction_strength_limit"],
            boundary_condition_digest=data["boundary_condition_digest"],
            error_bounds=_dict(data["error_bounds"]),
            source_certificate_ids=_list(data["source_certificate_ids"]),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class RegionBudgetPolicy:
    policy_id: str
    max_active_fine_regions: int
    max_refinements_per_tick: int
    max_fine_steps_per_tick: int
    per_case_compact_budget_bytes: int
    total_report_budget_bytes: int
    debug_full_fine_stream_allowed: bool
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "RegionBudgetPolicy")
        if not self.policy_id:
            raise ValueError("RegionBudgetPolicy requires policy_id.")
        for field_name in REGION_BUDGET_DEFAULTS:
            if int(getattr(self, field_name)) <= 0:
                raise ValueError(f"RegionBudgetPolicy {field_name} must be > 0.")
        self.debug_full_fine_stream_allowed = _bool(self.debug_full_fine_stream_allowed)
        if not self.source_record_ids:
            raise ValueError("RegionBudgetPolicy requires source_record_ids.")

    def to_dict(self) -> JsonDict:
        return {
            "policy_id": self.policy_id,
            "max_active_fine_regions": self.max_active_fine_regions,
            "max_refinements_per_tick": self.max_refinements_per_tick,
            "max_fine_steps_per_tick": self.max_fine_steps_per_tick,
            "per_case_compact_budget_bytes": self.per_case_compact_budget_bytes,
            "total_report_budget_bytes": self.total_report_budget_bytes,
            "debug_full_fine_stream_allowed": self.debug_full_fine_stream_allowed,
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> RegionBudgetPolicy:
        return cls(
            policy_id=data["policy_id"],
            max_active_fine_regions=data["max_active_fine_regions"],
            max_refinements_per_tick=data["max_refinements_per_tick"],
            max_fine_steps_per_tick=data["max_fine_steps_per_tick"],
            per_case_compact_budget_bytes=data["per_case_compact_budget_bytes"],
            total_report_budget_bytes=data["total_report_budget_bytes"],
            debug_full_fine_stream_allowed=data["debug_full_fine_stream_allowed"],
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class WorldRegion:
    region_id: str
    run_id: str
    region_key: str
    region_bounds_grid: list[float]
    region_bounds_world: list[float]
    coordinate_frame: JsonDict
    parent_region_id: str | None
    neighbor_region_ids: list[str]
    authority_mode: str
    current_macro_state_id: str | None
    current_field_state_id: str | None
    active_fine_patch_id: str | None
    current_lifecycle_record_id: str
    current_authority_tick: int
    validity_envelope: RegionValidityEnvelope | JsonDict
    budget_policy: RegionBudgetPolicy | JsonDict
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.region_bounds_grid = _list(self.region_bounds_grid)
        self.region_bounds_world = _list(self.region_bounds_world)
        self.coordinate_frame = _dict(self.coordinate_frame)
        self.neighbor_region_ids = _list(self.neighbor_region_ids)
        self.validity_envelope = _coerce_region_validity_envelope(self.validity_envelope)
        self.budget_policy = _coerce_region_budget_policy(self.budget_policy)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "WorldRegion")
        if not self.region_id or not self.run_id or not self.region_key:
            raise ValueError("WorldRegion requires region_id, run_id, and region_key.")
        _validate_bounds4(self.region_bounds_grid, "WorldRegion region_bounds_grid")
        _validate_bounds4(self.region_bounds_world, "WorldRegion region_bounds_world")
        _validate_coordinate_frame_contract(self.coordinate_frame)
        if self.authority_mode not in REGION_AUTHORITY_MODES:
            raise ValueError("WorldRegion authority_mode is not supported.")
        if self.authority_mode in {"cold_macro", "warm_macro"} and not self.current_macro_state_id:
            raise ValueError("WorldRegion macro mode requires current_macro_state_id.")
        if self.authority_mode == "active_fine" and not (self.active_fine_patch_id or self.current_field_state_id):
            raise ValueError("WorldRegion active_fine requires fine patch or field state.")
        if self.authority_mode == "invalidated" and not any("invalidation" in item or "invalidated" in item for item in self.source_record_ids):
            raise ValueError("WorldRegion invalidated mode requires invalidation lineage.")
        if not self.current_lifecycle_record_id:
            raise ValueError("WorldRegion requires current_lifecycle_record_id.")
        if self.current_authority_tick < 0:
            raise ValueError("WorldRegion current_authority_tick must be >= 0.")
        if not self.source_record_ids:
            raise ValueError("WorldRegion requires source_record_ids.")

    def to_dict(self) -> JsonDict:
        return {
            "region_id": self.region_id,
            "run_id": self.run_id,
            "region_key": self.region_key,
            "region_bounds_grid": _list(self.region_bounds_grid),
            "region_bounds_world": _list(self.region_bounds_world),
            "coordinate_frame": _dict(self.coordinate_frame),
            "parent_region_id": self.parent_region_id,
            "neighbor_region_ids": _list(self.neighbor_region_ids),
            "authority_mode": self.authority_mode,
            "current_macro_state_id": self.current_macro_state_id,
            "current_field_state_id": self.current_field_state_id,
            "active_fine_patch_id": self.active_fine_patch_id,
            "current_lifecycle_record_id": self.current_lifecycle_record_id,
            "current_authority_tick": self.current_authority_tick,
            "validity_envelope": self.validity_envelope.to_dict(),
            "budget_policy": self.budget_policy.to_dict(),
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> WorldRegion:
        return cls(
            region_id=data["region_id"],
            run_id=data["run_id"],
            region_key=data["region_key"],
            region_bounds_grid=_list(data["region_bounds_grid"]),
            region_bounds_world=_list(data["region_bounds_world"]),
            coordinate_frame=_dict(data["coordinate_frame"]),
            parent_region_id=data.get("parent_region_id"),
            neighbor_region_ids=_list(data["neighbor_region_ids"]),
            authority_mode=data["authority_mode"],
            current_macro_state_id=data.get("current_macro_state_id"),
            current_field_state_id=data.get("current_field_state_id"),
            active_fine_patch_id=data.get("active_fine_patch_id"),
            current_lifecycle_record_id=data["current_lifecycle_record_id"],
            current_authority_tick=data["current_authority_tick"],
            validity_envelope=_dict(data["validity_envelope"]),
            budget_policy=_dict(data["budget_policy"]),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class RegionActivationRequest:
    request_id: str
    run_id: str
    tick: int
    trigger_kind: str
    region_id: str
    observer_ids: list[str]
    interaction_record_ids: list[str]
    command_ids: list[str]
    trigger_source_ids: list[str]
    secondary_trigger_kinds: list[str]
    requested_region_grid: list[float]
    requested_region_world: list[float]
    requested_resolution: JsonDict
    source_macro_state_id: str | None
    source_field_state_id: str | None
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.observer_ids = _list(self.observer_ids)
        self.interaction_record_ids = _list(self.interaction_record_ids)
        self.command_ids = _list(self.command_ids)
        self.trigger_source_ids = _list(self.trigger_source_ids)
        self.secondary_trigger_kinds = _list(self.secondary_trigger_kinds)
        self.requested_region_grid = _list(self.requested_region_grid)
        self.requested_region_world = _list(self.requested_region_world)
        self.requested_resolution = _dict(self.requested_resolution)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "RegionActivationRequest")
        if not self.request_id or not self.run_id or not self.region_id:
            raise ValueError("RegionActivationRequest requires request_id, run_id, and region_id.")
        if self.trigger_kind not in REGION_TRIGGER_KINDS:
            raise ValueError("RegionActivationRequest trigger_kind is not supported.")
        if any(kind not in REGION_TRIGGER_KINDS for kind in self.secondary_trigger_kinds):
            raise ValueError("RegionActivationRequest secondary_trigger_kinds contains unsupported trigger.")
        _validate_bounds4(self.requested_region_grid, "RegionActivationRequest requested_region_grid")
        _validate_bounds4(self.requested_region_world, "RegionActivationRequest requested_region_world")
        if not (self.source_macro_state_id or self.source_field_state_id):
            raise ValueError("RegionActivationRequest requires source macro or field lineage.")
        if not self.source_record_ids:
            raise ValueError("RegionActivationRequest requires source_record_ids.")
        if not self.trigger_source_ids:
            raise ValueError("RegionActivationRequest requires trigger_source_ids.")
        if self.trigger_kind.startswith("observer") and not self.observer_ids:
            raise ValueError("Observer-triggered RegionActivationRequest requires observer_ids.")
        if self.trigger_kind == "local_interaction" and not (self.interaction_record_ids or self.command_ids):
            raise ValueError("Interaction-triggered RegionActivationRequest requires interaction or command ids.")

    def to_dict(self) -> JsonDict:
        return {
            "request_id": self.request_id,
            "run_id": self.run_id,
            "tick": self.tick,
            "trigger_kind": self.trigger_kind,
            "region_id": self.region_id,
            "observer_ids": _list(self.observer_ids),
            "interaction_record_ids": _list(self.interaction_record_ids),
            "command_ids": _list(self.command_ids),
            "trigger_source_ids": _list(self.trigger_source_ids),
            "secondary_trigger_kinds": _list(self.secondary_trigger_kinds),
            "requested_region_grid": _list(self.requested_region_grid),
            "requested_region_world": _list(self.requested_region_world),
            "requested_resolution": _dict(self.requested_resolution),
            "source_macro_state_id": self.source_macro_state_id,
            "source_field_state_id": self.source_field_state_id,
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> RegionActivationRequest:
        return cls(
            request_id=data["request_id"],
            run_id=data["run_id"],
            tick=data["tick"],
            trigger_kind=data["trigger_kind"],
            region_id=data["region_id"],
            observer_ids=_list(data["observer_ids"]),
            interaction_record_ids=_list(data["interaction_record_ids"]),
            command_ids=_list(data["command_ids"]),
            trigger_source_ids=_list(data["trigger_source_ids"]),
            secondary_trigger_kinds=_list(data["secondary_trigger_kinds"]),
            requested_region_grid=_list(data["requested_region_grid"]),
            requested_region_world=_list(data["requested_region_world"]),
            requested_resolution=_dict(data["requested_resolution"]),
            source_macro_state_id=data.get("source_macro_state_id"),
            source_field_state_id=data.get("source_field_state_id"),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class RegionLifecycleRecord:
    record_id: str
    run_id: str
    tick: int
    region_id: str
    previous_mode: str
    next_mode: str
    transition_kind: str
    activation_request_id: str | None
    macro_state_id: str | None
    field_state_id: str | None
    fine_patch_id: str | None
    correction_record_id: str | None
    budget_ledger_id: str | None
    reason: str
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "RegionLifecycleRecord")
        if not self.record_id or not self.run_id or not self.region_id:
            raise ValueError("RegionLifecycleRecord requires record_id, run_id, and region_id.")
        expected_pair = REGION_TRANSITION_PAIRS.get(self.transition_kind)
        if expected_pair is None:
            raise ValueError("RegionLifecycleRecord transition_kind is not supported.")
        if expected_pair != (self.previous_mode, self.next_mode):
            raise ValueError("RegionLifecycleRecord transition_kind does not match mode pair.")
        if not self.source_record_ids:
            raise ValueError("RegionLifecycleRecord requires source_record_ids.")
        if not (self.macro_state_id or self.field_state_id or self.fine_patch_id or self.correction_record_id or self.activation_request_id):
            raise ValueError("RegionLifecycleRecord requires matching source artifacts.")

    def to_dict(self) -> JsonDict:
        return {
            "record_id": self.record_id,
            "run_id": self.run_id,
            "tick": self.tick,
            "region_id": self.region_id,
            "previous_mode": self.previous_mode,
            "next_mode": self.next_mode,
            "transition_kind": self.transition_kind,
            "activation_request_id": self.activation_request_id,
            "macro_state_id": self.macro_state_id,
            "field_state_id": self.field_state_id,
            "fine_patch_id": self.fine_patch_id,
            "correction_record_id": self.correction_record_id,
            "budget_ledger_id": self.budget_ledger_id,
            "reason": self.reason,
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> RegionLifecycleRecord:
        return cls(
            record_id=data["record_id"],
            run_id=data["run_id"],
            tick=data["tick"],
            region_id=data["region_id"],
            previous_mode=data["previous_mode"],
            next_mode=data["next_mode"],
            transition_kind=data["transition_kind"],
            activation_request_id=data.get("activation_request_id"),
            macro_state_id=data.get("macro_state_id"),
            field_state_id=data.get("field_state_id"),
            fine_patch_id=data.get("fine_patch_id"),
            correction_record_id=data.get("correction_record_id"),
            budget_ledger_id=data.get("budget_ledger_id"),
            reason=data["reason"],
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class RegionBudgetLedger:
    ledger_id: str
    run_id: str
    tick: int
    active_fine_region_ids: list[str]
    warm_macro_region_ids: list[str]
    cold_macro_region_ids: list[str]
    invalidated_region_ids: list[str]
    fine_step_count: int
    refinement_request_count: int
    artifact_bytes_estimate: int
    budget_limits: JsonDict
    budget_status: str
    learning_mode_required: bool
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.active_fine_region_ids = _list(self.active_fine_region_ids)
        self.warm_macro_region_ids = _list(self.warm_macro_region_ids)
        self.cold_macro_region_ids = _list(self.cold_macro_region_ids)
        self.invalidated_region_ids = _list(self.invalidated_region_ids)
        self.budget_limits = _dict(self.budget_limits)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "RegionBudgetLedger")
        if not self.ledger_id or not self.run_id:
            raise ValueError("RegionBudgetLedger requires ledger_id and run_id.")
        missing = sorted(set(REGION_BUDGET_DEFAULTS) - set(self.budget_limits))
        if missing:
            raise ValueError("RegionBudgetLedger budget_limits missing required fields: " + ", ".join(missing))
        if self.budget_status not in REGION_BUDGET_STATUSES:
            raise ValueError("RegionBudgetLedger budget_status is not supported.")
        if not self.source_record_ids:
            raise ValueError("RegionBudgetLedger requires source_record_ids.")
        hard_failed = (
            len(self.active_fine_region_ids) > int(self.budget_limits["max_active_fine_regions"])
            or int(self.refinement_request_count) > int(self.budget_limits["max_refinements_per_tick"])
            or int(self.fine_step_count) > int(self.budget_limits["max_fine_steps_per_tick"])
        )
        artifact_overrun = (
            int(self.artifact_bytes_estimate) > int(self.budget_limits["per_case_compact_budget_bytes"])
            or int(self.artifact_bytes_estimate) > int(self.budget_limits["total_report_budget_bytes"])
        )
        if hard_failed:
            self.budget_status = "failed"
            self.learning_mode_required = False
        elif artifact_overrun:
            self.budget_status = "learning_mode_required"
            self.learning_mode_required = True
        elif self.budget_status == "learning_mode_required":
            self.learning_mode_required = True
        elif self.budget_status == "passed":
            self.learning_mode_required = False

    def to_dict(self) -> JsonDict:
        return {
            "ledger_id": self.ledger_id,
            "run_id": self.run_id,
            "tick": self.tick,
            "active_fine_region_ids": _list(self.active_fine_region_ids),
            "warm_macro_region_ids": _list(self.warm_macro_region_ids),
            "cold_macro_region_ids": _list(self.cold_macro_region_ids),
            "invalidated_region_ids": _list(self.invalidated_region_ids),
            "fine_step_count": self.fine_step_count,
            "refinement_request_count": self.refinement_request_count,
            "artifact_bytes_estimate": self.artifact_bytes_estimate,
            "budget_limits": _dict(self.budget_limits),
            "budget_status": self.budget_status,
            "learning_mode_required": self.learning_mode_required,
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> RegionBudgetLedger:
        return cls(
            ledger_id=data["ledger_id"],
            run_id=data["run_id"],
            tick=data["tick"],
            active_fine_region_ids=_list(data["active_fine_region_ids"]),
            warm_macro_region_ids=_list(data["warm_macro_region_ids"]),
            cold_macro_region_ids=_list(data["cold_macro_region_ids"]),
            invalidated_region_ids=_list(data["invalidated_region_ids"]),
            fine_step_count=data["fine_step_count"],
            refinement_request_count=data["refinement_request_count"],
            artifact_bytes_estimate=data["artifact_bytes_estimate"],
            budget_limits=_dict(data["budget_limits"]),
            budget_status=data["budget_status"],
            learning_mode_required=data["learning_mode_required"],
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


@dataclass
class RegionBoundaryExchangeRecord:
    record_id: str
    run_id: str
    tick: int
    source_region_id: str
    target_region_id: str
    source_authority_mode: str
    target_authority_mode: str
    source_macro_state_id: str | None
    target_macro_state_id: str | None
    source_fine_patch_id: str | None
    target_fine_patch_id: str | None
    boundary_band_grid: list[float]
    boundary_band_world: list[float]
    overlap_iou: float
    signed_flux: float
    energy_before: float
    energy_after: float
    energy_conservation_relative_error: float
    exchange_kind: str
    invalidation_region_ids: list[str]
    source_record_ids: list[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        self.boundary_band_grid = _list(self.boundary_band_grid)
        self.boundary_band_world = _list(self.boundary_band_world)
        self.invalidation_region_ids = _list(self.invalidation_region_ids)
        self.source_record_ids = _list(self.source_record_ids)
        _validate_non_authority(self.is_authority_state, "RegionBoundaryExchangeRecord")
        if not self.record_id or not self.run_id:
            raise ValueError("RegionBoundaryExchangeRecord requires record_id and run_id.")
        if not self.source_region_id or not self.target_region_id:
            raise ValueError("RegionBoundaryExchangeRecord requires source/target region ids.")
        if self.source_region_id == self.target_region_id:
            raise ValueError("RegionBoundaryExchangeRecord source and target regions must differ.")
        if self.source_authority_mode not in REGION_AUTHORITY_MODES or self.target_authority_mode not in REGION_AUTHORITY_MODES:
            raise ValueError("RegionBoundaryExchangeRecord authority mode is not supported.")
        if self.exchange_kind not in REGION_BOUNDARY_EXCHANGE_KINDS:
            raise ValueError("RegionBoundaryExchangeRecord exchange_kind is not supported.")
        _validate_bounds4(self.boundary_band_grid, "RegionBoundaryExchangeRecord boundary_band_grid")
        _validate_bounds4(self.boundary_band_world, "RegionBoundaryExchangeRecord boundary_band_world")
        if not self.source_record_ids:
            raise ValueError("RegionBoundaryExchangeRecord requires source_record_ids.")
        if "macro" in self.source_authority_mode and not self.source_macro_state_id:
            raise ValueError("Macro source region exchange requires source_macro_state_id.")
        if "macro" in self.target_authority_mode and not self.target_macro_state_id:
            raise ValueError("Macro target region exchange requires target_macro_state_id.")
        if self.source_authority_mode == "active_fine" and not self.source_fine_patch_id:
            raise ValueError("Fine source region exchange requires source_fine_patch_id.")
        if self.target_authority_mode == "active_fine" and not self.target_fine_patch_id:
            raise ValueError("Fine target region exchange requires target_fine_patch_id.")
        if float(self.overlap_iou) < 0:
            raise ValueError("RegionBoundaryExchangeRecord overlap_iou must be >= 0.")
        if (
            float(self.energy_conservation_relative_error) > 0.05
            and self.exchange_kind not in REGION_INVALIDATION_EXCHANGE_KINDS
        ):
            raise ValueError("RegionBoundaryExchangeRecord energy conservation error exceeds threshold.")
        if self.exchange_kind in REGION_INVALIDATION_EXCHANGE_KINDS and not self.invalidation_region_ids:
            raise ValueError("Invalidation exchange requires invalidation_region_ids.")

    def to_dict(self) -> JsonDict:
        return {
            "record_id": self.record_id,
            "run_id": self.run_id,
            "tick": self.tick,
            "source_region_id": self.source_region_id,
            "target_region_id": self.target_region_id,
            "source_authority_mode": self.source_authority_mode,
            "target_authority_mode": self.target_authority_mode,
            "source_macro_state_id": self.source_macro_state_id,
            "target_macro_state_id": self.target_macro_state_id,
            "source_fine_patch_id": self.source_fine_patch_id,
            "target_fine_patch_id": self.target_fine_patch_id,
            "boundary_band_grid": _list(self.boundary_band_grid),
            "boundary_band_world": _list(self.boundary_band_world),
            "overlap_iou": self.overlap_iou,
            "signed_flux": self.signed_flux,
            "energy_before": self.energy_before,
            "energy_after": self.energy_after,
            "energy_conservation_relative_error": self.energy_conservation_relative_error,
            "exchange_kind": self.exchange_kind,
            "invalidation_region_ids": _list(self.invalidation_region_ids),
            "source_record_ids": _list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> RegionBoundaryExchangeRecord:
        return cls(
            record_id=data["record_id"],
            run_id=data["run_id"],
            tick=data["tick"],
            source_region_id=data["source_region_id"],
            target_region_id=data["target_region_id"],
            source_authority_mode=data["source_authority_mode"],
            target_authority_mode=data["target_authority_mode"],
            source_macro_state_id=data.get("source_macro_state_id"),
            target_macro_state_id=data.get("target_macro_state_id"),
            source_fine_patch_id=data.get("source_fine_patch_id"),
            target_fine_patch_id=data.get("target_fine_patch_id"),
            boundary_band_grid=_list(data["boundary_band_grid"]),
            boundary_band_world=_list(data["boundary_band_world"]),
            overlap_iou=data["overlap_iou"],
            signed_flux=data["signed_flux"],
            energy_before=data["energy_before"],
            energy_after=data["energy_after"],
            energy_conservation_relative_error=data["energy_conservation_relative_error"],
            exchange_kind=data["exchange_kind"],
            invalidation_region_ids=_list(data["invalidation_region_ids"]),
            source_record_ids=_list(data["source_record_ids"]),
            is_authority_state=data.get("is_authority_state", False),
        )


def validate_fine_patch_outcome_replay(
    outcome: FinePatchOutcome,
    snapshots: list[FinePatchStateSnapshot],
    step_records: list[FinePatchStepRecord],
) -> None:
    snapshots_by_id = {snapshot.snapshot_id: snapshot for snapshot in snapshots}
    steps_by_id = {step.record_id: step for step in step_records}
    if outcome.initial_snapshot_id not in snapshots_by_id:
        raise ValueError("FinePatchOutcome missing initial snapshot.")
    if outcome.final_snapshot_id not in snapshots_by_id:
        raise ValueError("FinePatchOutcome missing final snapshot.")
    initial = snapshots_by_id[outcome.initial_snapshot_id]
    final = snapshots_by_id[outcome.final_snapshot_id]
    for snapshot in [initial, final]:
        if snapshot.patch_id != outcome.patch_id:
            raise ValueError("FinePatchOutcome snapshot patch_id mismatch.")
        if snapshot.region_grid != outcome.region_grid:
            raise ValueError("FinePatchOutcome snapshot region_grid mismatch.")
        if snapshot.coordinate_frame != outcome.coordinate_frame:
            raise ValueError("FinePatchOutcome snapshot coordinate_frame mismatch.")
    if final.channels_digest != outcome.final_patch_channels_digest:
        raise ValueError("FinePatchOutcome final_patch_channels_digest mismatch.")
    if canonical_json_digest(summarize_compact_channels(final.channels_compact)) != final.summary_digest:
        raise ValueError("FinePatchOutcome final snapshot summary digest mismatch.")
    if not outcome.fine_patch_step_record_ids:
        if initial.snapshot_id != final.snapshot_id and initial.channels_digest != final.channels_digest:
            raise ValueError("Observation-only FinePatchOutcome changed patch state without steps.")
        return
    cursor = outcome.initial_snapshot_id
    for record_id in outcome.fine_patch_step_record_ids:
        step = steps_by_id.get(record_id)
        if step is None:
            raise ValueError("FinePatchOutcome references missing step record.")
        if step.patch_id != outcome.patch_id:
            raise ValueError("FinePatchStepRecord patch_id mismatch.")
        if step.previous_snapshot_id != cursor:
            raise ValueError("FinePatchStepRecord snapshot chain is discontinuous.")
        if step.current_snapshot_id not in snapshots_by_id:
            raise ValueError("FinePatchStepRecord current snapshot missing.")
        cursor = step.current_snapshot_id
    if cursor != outcome.final_snapshot_id:
        raise ValueError("FinePatchOutcome snapshot chain does not reach final snapshot.")


@dataclass
class FieldState:
    field_state_id: str
    run_id: str
    tick: int
    rule_id: str
    grid_shape: list[int]
    channels: dict[str, list[list[float]]]
    previous_channels: dict[str, list[list[float]]]
    energy: float
    source_state_ticks: list[int]
    source_record_ids: list[str]
    payload: JsonDict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.grid_shape = _list(self.grid_shape)
        self.channels = _channels(self.channels)
        self.previous_channels = _channels(self.previous_channels)
        self.source_state_ticks = _list(self.source_state_ticks)
        self.source_record_ids = _list(self.source_record_ids)
        self.payload = _dict(self.payload)

        if not self.channels:
            raise ValueError("FieldState channels cannot be empty.")
        for name, grid in self.channels.items():
            _validate_channel_grid(name, grid, self.grid_shape)
        for name, grid in self.previous_channels.items():
            _validate_channel_grid(name, grid, self.grid_shape)

        required_payload = {
            "authority_role",
            "wave_kernel",
            "source_package_digest",
            "stable_composite_evidence_id",
            "stable_composite_evidence_digest",
            "field_evidence_bridge_id",
            "previous_field_state_id",
            "source_field_state_ids",
            "field_wave_step_record_id",
            "channel_families",
            "seed_mode_signatures",
            "coordinate_frame",
        }
        missing = sorted(required_payload - set(self.payload))
        if missing:
            raise ValueError("FieldState payload missing required fields: " + ", ".join(missing))
        if self.payload.get("authority_role") != "field_substrate":
            raise ValueError("FieldState authority_role must be field_substrate.")

        evidence_id = self.payload.get("stable_composite_evidence_id", "")
        evidence_digest = self.payload.get("stable_composite_evidence_digest")
        if not isinstance(evidence_id, str) or ":sha256:" not in evidence_id:
            raise ValueError("FieldState stable_composite_evidence_id must contain :sha256:.")
        if evidence_digest != evidence_id.rsplit(":sha256:", 1)[-1]:
            raise ValueError("FieldState stable_composite_evidence_digest must match evidence id.")

        coordinate_frame = self.payload.get("coordinate_frame")
        required_frame = {
            "world_origin",
            "world_extent",
            "grid_shape",
            "world_to_grid",
            "grid_to_world",
            "source_observer_window",
        }
        if not isinstance(coordinate_frame, dict):
            raise ValueError("FieldState coordinate_frame must be a dict.")
        missing_frame = sorted(required_frame - set(coordinate_frame))
        if missing_frame:
            raise ValueError("FieldState coordinate_frame missing: " + ", ".join(missing_frame))

        bridge_id = self.payload.get("field_evidence_bridge_id")
        previous_field_state_id = self.payload.get("previous_field_state_id")
        source_field_state_ids = self.payload.get("source_field_state_ids")
        field_wave_step_record_id = self.payload.get("field_wave_step_record_id")
        if not isinstance(source_field_state_ids, list):
            raise ValueError("FieldState source_field_state_ids must be a list.")
        if self.tick == 0:
            if previous_field_state_id is not None or source_field_state_ids:
                raise ValueError("Seed FieldState must not cite a previous field state.")
            if field_wave_step_record_id is not None:
                raise ValueError("Seed FieldState must not cite a field wave step record.")
            if bridge_id not in self.source_record_ids:
                raise ValueError("Seed FieldState must cite field_evidence_bridge_id.")
        else:
            if not previous_field_state_id:
                raise ValueError("Non-seed FieldState requires previous_field_state_id.")
            if previous_field_state_id not in source_field_state_ids:
                raise ValueError("source_field_state_ids must include previous_field_state_id.")
            if not field_wave_step_record_id:
                raise ValueError("Non-seed FieldState requires field_wave_step_record_id.")
            if field_wave_step_record_id not in self.source_record_ids:
                raise ValueError("Non-seed FieldState must cite field_wave_step_record_id.")

    def to_dict(self) -> JsonDict:
        return {
            "field_state_id": self.field_state_id,
            "run_id": self.run_id,
            "tick": self.tick,
            "rule_id": self.rule_id,
            "grid_shape": _list(self.grid_shape),
            "channels": _channels(self.channels),
            "previous_channels": _channels(self.previous_channels),
            "energy": self.energy,
            "source_state_ticks": _list(self.source_state_ticks),
            "source_record_ids": _list(self.source_record_ids),
            "payload": _dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> FieldState:
        return cls(
            field_state_id=data["field_state_id"],
            run_id=data["run_id"],
            tick=data["tick"],
            rule_id=data["rule_id"],
            grid_shape=_list(data["grid_shape"]),
            channels=_channels(data["channels"]),
            previous_channels=_channels(data["previous_channels"]),
            energy=data["energy"],
            source_state_ticks=_list(data["source_state_ticks"]),
            source_record_ids=_list(data["source_record_ids"]),
            payload=_dict(data.get("payload")),
        )


@dataclass
class WorldState:
    run_id: str
    tick: int
    objects: list[WorldObject]
    events: list[WorldEvent]
    radiative_records: list[RadiativeRecord]
    interaction_records: list[InteractionRecord]
    observer_records: list[ObserverRecord]
    observer_projections: list[ObserverProjection]
    natural_phenomena: list[NaturalPhenomenonSummary]
    projection_cache: list[ProjectionCacheRecord]
    causal_links: list[CausalLink]
    payload: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "run_id": self.run_id,
            "tick": self.tick,
            "objects": [item.to_dict() for item in self.objects],
            "events": [item.to_dict() for item in self.events],
            "radiative_records": [item.to_dict() for item in self.radiative_records],
            "interaction_records": [item.to_dict() for item in self.interaction_records],
            "observer_records": [item.to_dict() for item in self.observer_records],
            "observer_projections": [item.to_dict() for item in self.observer_projections],
            "natural_phenomena": [item.to_dict() for item in self.natural_phenomena],
            "projection_cache": [item.to_dict() for item in self.projection_cache],
            "causal_links": [item.to_dict() for item in self.causal_links],
            "payload": _dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> WorldState:
        return cls(
            run_id=data["run_id"],
            tick=data["tick"],
            objects=[WorldObject.from_dict(item) for item in data["objects"]],
            events=[WorldEvent.from_dict(item) for item in data["events"]],
            radiative_records=[
                RadiativeRecord.from_dict(item) for item in data["radiative_records"]
            ],
            interaction_records=[
                InteractionRecord.from_dict(item) for item in data["interaction_records"]
            ],
            observer_records=[
                ObserverRecord.from_dict(item) for item in data["observer_records"]
            ],
            observer_projections=[
                ObserverProjection.from_dict(item) for item in data["observer_projections"]
            ],
            natural_phenomena=[
                NaturalPhenomenonSummary.from_dict(item)
                for item in data["natural_phenomena"]
            ],
            projection_cache=[
                ProjectionCacheRecord.from_dict(item) for item in data["projection_cache"]
            ],
            causal_links=[CausalLink.from_dict(item) for item in data["causal_links"]],
            payload=_dict(data.get("payload")),
        )


@dataclass
class CompletionCheck:
    name: str
    status: str
    details: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "name": self.name,
            "status": self.status,
            "details": _dict(self.details),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> CompletionCheck:
        return cls(
            name=data["name"],
            status=data["status"],
            details=_dict(data.get("details")),
        )


@dataclass
class CompletionReport:
    overall_status: str
    checks: list[CompletionCheck]
    summary: JsonDict = field(default_factory=dict)
    audit: JsonDict = field(default_factory=dict)

    def to_dict(self) -> JsonDict:
        return {
            "overall_status": self.overall_status,
            "checks": [item.to_dict() for item in self.checks],
            "summary": _dict(self.summary),
            "audit": _dict(self.audit),
        }

    @classmethod
    def from_dict(cls, data: JsonDict) -> CompletionReport:
        return cls(
            overall_status=data["overall_status"],
            checks=[CompletionCheck.from_dict(item) for item in data["checks"]],
            summary=_dict(data.get("summary")),
            audit=_dict(data.get("audit")),
        )


from world_engine.matter_contracts import (  # noqa: E402
    DEFAULT_MATERIAL_BEHAVIOR_THRESHOLDS,
    DerivedMaterialPropertyRecord,
    HypergraphCausalGraphRecord,
    HypergraphRewriteRuleRecord,
    HypergraphStateSnapshot,
    MacroMaterialState,
    MaterialBehaviorProfile,
    MaterialBody,
    MaterialBondRecord,
    MaterialContactRecord,
    MaterialCorrectionCertificateExtension,
    MaterialCorrectionRecord,
    MaterialEnvironmentZone,
    MaterialInteractionRecord,
    MaterialPatchOutcome,
    MaterialPatchStateSnapshot,
    MaterialPatchStepRecord,
    MaterialPropertyRuntimeBindingRecord,
    MaterialReactionRecord,
    MaterialRefinementPatch,
    MaterialRefinementRequest,
    MaterialResponseBaselineRecord,
    MaterialResponseRecord,
    MaterialSpeciesCandidate,
    MaterialSpeciesCertificate,
    MaterialUnit,
    MATERIAL_BEHAVIOR_RESPONSE_COMPATIBILITY,
    MATERIAL_CONTACT_AUTHORITY_KINDS,
    MATERIAL_CONTACT_KINDS,
    MATERIAL_RESPONSE_KINDS,
    MATERIAL_RESPONSE_RESULT_STATUSES,
    RegionMaterialAuthorityPointer,
    SubstrateMeasurementRecord,
    WorldSubstrateRecord,
    material_behavior_profile_digest,
    material_environment_zone_digest,
    material_property_runtime_binding_digest,
    material_response_baseline_digest,
)
