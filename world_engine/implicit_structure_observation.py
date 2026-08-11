from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence


IMPLICIT_OBSERVED_STRUCTURE_SCHEMA = "implicit_observed_structure_record"
ALLOWED_IMPLICIT_STRUCTURE_KIND_HINTS = {
    "surface",
    "barrier",
    "channel",
    "emitter",
    "absorber",
    "cavity",
    "free_boundary",
    "interaction_mark",
    "mixed",
}


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _basis_id(basis: Mapping[str, Any]) -> str:
    return str(basis.get("basis_id", ""))


def _bounds(basis: Mapping[str, Any]) -> tuple[list[float], list[float]]:
    support = basis.get("support_region_world", {})
    lower = support.get("min")
    upper = support.get("max")
    if lower is None or upper is None:
        center = [float(value) for value in basis.get("center_world_3d", [0.0, 0.0, 0.0])]
        radius = float(basis.get("radius_world", 0.0))
        return [value - radius for value in center], [value + radius for value in center]
    return [float(value) for value in lower], [float(value) for value in upper]


def _overlaps(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_min, left_max = _bounds(left)
    right_min, right_max = _bounds(right)
    return all(left_min[index] <= right_max[index] and right_min[index] <= left_max[index] for index in range(3))


def _component_kind(bases: Sequence[Mapping[str, Any]]) -> str:
    kinds = set()
    for basis in bases:
        kind = str(basis.get("basis_kind", ""))
        weights = basis.get("channel_weights", {})
        if kind.startswith("signed_boundary") or float(weights.get("boundary", 0.0)) >= 0.25:
            kinds.add("barrier")
        elif kind.startswith("emitter") or float(weights.get("emission", 0.0)) >= 0.5:
            kinds.add("emitter")
        elif kind.startswith("absorption") or float(weights.get("absorption", 0.0)) >= 0.5:
            kinds.add("absorber")
        elif "channel" in str(basis.get("source_signature_template_id", "")):
            kinds.add("channel")
        else:
            kinds.add("surface")
    return kinds.pop() if len(kinds) == 1 else "mixed"


def _active_weight(state: Mapping[str, Any], basis_id: str) -> float:
    coefficients = state.get("basis_coefficients", {}).get(basis_id, {})
    return sum(abs(float(value)) for value in coefficients.values())


def _basis_components(state: Mapping[str, Any], bases: Sequence[Mapping[str, Any]]) -> list[list[Mapping[str, Any]]]:
    active = [basis for basis in bases if _basis_id(basis) in set(state.get("basis_ids", [])) and _active_weight(state, _basis_id(basis)) >= 0.02]
    remaining = list(active)
    components: list[list[Mapping[str, Any]]] = []
    while remaining:
        seed = remaining.pop(0)
        component = [seed]
        changed = True
        while changed:
            changed = False
            for candidate in list(remaining):
                if any(_overlaps(candidate, basis) for basis in component):
                    remaining.remove(candidate)
                    component.append(candidate)
                    changed = True
        components.append(component)
    return components


def _centroid(state: Mapping[str, Any], component: Sequence[Mapping[str, Any]]) -> list[float]:
    total = 0.0
    centroid = [0.0, 0.0, 0.0]
    for basis in component:
        basis_id = _basis_id(basis)
        weight = max(0.001, _active_weight(state, basis_id))
        center = [float(value) for value in basis.get("center_world_3d", [0.0, 0.0, 0.0])]
        total += weight
        for index in range(3):
            centroid[index] += center[index] * weight
    return [value / max(0.001, total) for value in centroid]


def _union_bounds(component: Sequence[Mapping[str, Any]]) -> dict[str, list[float]]:
    lowers, uppers = zip(*[_bounds(basis) for basis in component])
    return {
        "min": [min(values[index] for values in lowers) for index in range(3)],
        "max": [max(values[index] for values in uppers) for index in range(3)],
    }


def _spectral_signature(state: Mapping[str, Any], component: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    channels = {"density": 0.0, "emission": 0.0, "absorption": 0.0, "boundary": 0.0}
    total = 0.0
    for basis in component:
        basis_id = _basis_id(basis)
        active = max(0.001, _active_weight(state, basis_id))
        total += active
        weights = basis.get("channel_weights", {})
        coefficients = state.get("basis_coefficients", {}).get(basis_id, {})
        for channel in channels:
            channels[channel] += active * abs(float(weights.get(channel, 0.0))) * abs(float(coefficients.get(channel, coefficients.get("*", 1.0))))
    return {channel: channels[channel] / max(0.001, total) for channel in channels}


def _stability_ticks(component_basis_ids: set[str], previous_structures: Sequence[Mapping[str, Any]] | None) -> int:
    if not previous_structures:
        return 1
    best = 0
    for structure in previous_structures:
        previous = {str(value) for value in structure.get("basis_ids", [])}
        overlap = len(component_basis_ids & previous) / max(1, len(component_basis_ids | previous))
        if overlap >= 0.6:
            best = max(best, int(structure.get("stability_ticks", 0)) + 1)
    return best or 1


def extract_implicit_observed_structures(
    state: Mapping[str, Any],
    bases: Sequence[Mapping[str, Any]],
    *,
    ray_sample_records: Sequence[Mapping[str, Any]],
    previous_structures: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    basis_index_digest = str(state.get("basis_spatial_index_digest", ""))
    source_rays = [str(record.get("ray_sample_record_id", "")) for record in ray_sample_records]
    visible_observers = sorted({str(record.get("observer_id", "")) for record in ray_sample_records if record.get("observer_id")})
    structures: list[dict[str, Any]] = []
    for index, component in enumerate(_basis_components(state, bases)):
        basis_ids = [_basis_id(basis) for basis in component]
        structure = {
            "schema": IMPLICIT_OBSERVED_STRUCTURE_SCHEMA,
            "structure_id": f"implicit-observed-structure::{state.get('implicit_field_state_id')}::component-{index}",
            "state_tick": int(state.get("tick", 0)),
            "observation_tick": int(state.get("tick", 0)),
            "kind_hint": _component_kind(component),
            "basis_ids": basis_ids,
            "centroid_world_3d": _centroid(state, component),
            "support_bounds_world_3d": _union_bounds(component),
            "spectral_signature": _spectral_signature(state, component),
            "stability_ticks": _stability_ticks(set(basis_ids), previous_structures),
            "visible_observer_ids": visible_observers,
            "source_implicit_field_state_id": str(state.get("implicit_field_state_id", "")),
            "source_basis_spatial_index_digest": basis_index_digest,
            "source_ray_sample_record_ids": source_rays,
            "source_record_ids": [str(state.get("implicit_field_state_id", "")), *source_rays],
            "is_authority_state": False,
        }
        validate_implicit_observed_structure_record(structure, state=state, bases=bases)
        structures.append(structure)
    return structures


def validate_implicit_observed_structure_record(record: Mapping[str, Any], *, state: Mapping[str, Any], bases: Sequence[Mapping[str, Any]]) -> None:
    if record.get("schema") != IMPLICIT_OBSERVED_STRUCTURE_SCHEMA:
        raise ValueError("implicit observed structure schema mismatch")
    if record.get("is_authority_state") is not False:
        raise ValueError("implicit observed structure must be non-authority")
    if record.get("kind_hint") not in ALLOWED_IMPLICIT_STRUCTURE_KIND_HINTS:
        raise ValueError("unsupported implicit observed structure kind")
    state_basis_ids = {str(value) for value in state.get("basis_ids", [])}
    basis_by_id = {_basis_id(basis): basis for basis in bases}
    basis_ids = [str(value) for value in record.get("basis_ids", [])]
    if not basis_ids or not set(basis_ids).issubset(state_basis_ids):
        raise ValueError("implicit observed structure basis ids must exist in state")
    bounds = record.get("support_bounds_world_3d", {})
    lower = [float(value) for value in bounds.get("min", [])]
    upper = [float(value) for value in bounds.get("max", [])]
    if len(lower) != 3 or len(upper) != 3:
        raise ValueError("implicit observed structure requires support bounds")
    for basis_id in basis_ids:
        center = [float(value) for value in basis_by_id[basis_id].get("center_world_3d", [])]
        if len(center) != 3 or not all(lower[index] <= center[index] <= upper[index] for index in range(3)):
            raise ValueError("implicit observed structure bounds do not contain basis center")
    expected_digest = str(state.get("basis_spatial_index_digest", ""))
    if str(record.get("source_basis_spatial_index_digest", "")) != expected_digest:
        raise ValueError("implicit observed structure spatial index digest mismatch")


def observed_structure_by_basis_id(structures: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for structure in structures:
        for basis_id in structure.get("basis_ids", []):
            result[str(basis_id)] = structure
    return result
