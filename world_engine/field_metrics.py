from __future__ import annotations

import hashlib
from typing import Any

from world_engine.contracts import FieldState
from world_engine.field_coordinates import grid_to_world


Support = list[tuple[int, int]]


def _effective_threshold(grid: list[list[float]], threshold: float) -> float:
    max_abs = 0.0
    for row in grid:
        for value in row:
            abs_value = abs(value)
            if abs_value > max_abs:
                max_abs = abs_value
    if max_abs == 0.0:
        return threshold
    return min(threshold, max_abs * 0.2)


def _neighbors(row: int, col: int, height: int, width: int) -> list[tuple[int, int]]:
    candidates = [
        (row - 1, col),
        (row + 1, col),
        (row, col - 1),
        (row, col + 1),
    ]
    return [
        (r, c)
        for r, c in candidates
        if 0 <= r < height and 0 <= c < width
    ]


def _component_supports(
    grid: list[list[float]],
    threshold: float,
) -> list[Support]:
    height = len(grid)
    width = len(grid[0]) if height else 0
    effective = _effective_threshold(grid, threshold)
    active = [
        [abs(value) >= effective for value in row]
        for row in grid
    ]
    supports: list[Support] = []
    for row_index in range(height):
        for col_index in range(width):
            if not active[row_index][col_index]:
                continue
            stack = [(row_index, col_index)]
            active[row_index][col_index] = False
            support: Support = []
            while stack:
                cell = stack.pop()
                support.append(cell)
                for neighbor in _neighbors(cell[0], cell[1], height, width):
                    neighbor_row, neighbor_col = neighbor
                    if active[neighbor_row][neighbor_col]:
                        active[neighbor_row][neighbor_col] = False
                        stack.append(neighbor)
            supports.append(support)
    return supports


def _support_bounds_grid(support: Support) -> list[int]:
    rows = [row for row, _ in support]
    cols = [col for _, col in support]
    return [min(cols), min(rows), max(cols), max(rows)]


def _support_energy(grid: list[list[float]], support: Support) -> float:
    return sum(grid[row][col] ** 2 for row, col in support)


def _support_peak(grid: list[list[float]], support: Support) -> float:
    return max(abs(grid[row][col]) for row, col in support)


def _support_centroid(grid: list[list[float]], support: Support) -> list[float]:
    weight_sum = 0.0
    col_sum = 0.0
    row_sum = 0.0
    for row, col in support:
        weight = grid[row][col] ** 2
        weight_sum += weight
        col_sum += col * weight
        row_sum += row * weight
    if weight_sum == 0.0:
        raise ValueError("support has zero energy")
    return [col_sum / weight_sum, row_sum / weight_sum]


def _support_stats(grid: list[list[float]], support: Support) -> dict[str, Any]:
    min_row = min_col = 10**12
    max_row = max_col = -1
    energy = 0.0
    peak_abs = 0.0
    weight_sum = 0.0
    col_sum = 0.0
    row_sum = 0.0
    for row, col in support:
        value = grid[row][col]
        abs_value = abs(value)
        squared = value * value
        if row < min_row:
            min_row = row
        if row > max_row:
            max_row = row
        if col < min_col:
            min_col = col
        if col > max_col:
            max_col = col
        if abs_value > peak_abs:
            peak_abs = abs_value
        energy += squared
        weight_sum += squared
        col_sum += col * squared
        row_sum += row * squared
    if weight_sum == 0.0:
        raise ValueError("support has zero energy")
    return {
        "support_bounds_grid": [min_col, min_row, max_col, max_row],
        "energy": energy,
        "peak_abs": peak_abs,
        "centroid_grid": [col_sum / weight_sum, row_sum / weight_sum],
    }


def _mode_signature(
    field_state: FieldState,
    channel_name: str,
    component_index: int,
    component_count: int,
) -> str:
    seeded = field_state.payload.get("seed_mode_signatures", {}).get(channel_name)
    if seeded and component_count == 1:
        return str(seeded)
    raw = f"{field_state.rule_id}|{channel_name}|{component_index}|{component_count}"
    return f"mode-signature:sha256:{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def _component_id(
    field_state: FieldState,
    channel_name: str,
    component_index: int,
) -> str:
    channel_slug = channel_name.replace("::", "-")
    return f"field-component::{field_state.tick}::{channel_slug}::{component_index}"


def detect_field_components(
    field_state: FieldState,
    threshold: float = 0.2,
    *,
    include_support_cells: bool = True,
) -> list[dict[str, Any]]:
    coordinate_frame = field_state.payload["coordinate_frame"]
    components: list[dict[str, Any]] = []
    for channel_name, grid in field_state.channels.items():
        supports = _component_supports(grid, threshold)
        family = field_state.payload.get("channel_families", {}).get(channel_name, channel_name)
        for index, support in enumerate(supports):
            stats = _support_stats(grid, support)
            component = {
                "component_id": _component_id(field_state, channel_name, index),
                "channel": channel_name,
                "family": family,
                "component_index": index,
                "support_size": len(support),
                "support_bounds_grid": stats["support_bounds_grid"],
                "energy": stats["energy"],
                "peak_abs": stats["peak_abs"],
                "centroid_grid": stats["centroid_grid"],
                "centroid_world": grid_to_world(stats["centroid_grid"], coordinate_frame),
                "mode_signature": _mode_signature(
                    field_state,
                    channel_name,
                    index,
                    len(supports),
                ),
            }
            if include_support_cells:
                component["support_cells_grid"] = [[row, col] for row, col in support]
            components.append(component)
    return components


def summarize_field_structure(
    field_state: FieldState,
    previous_summary: dict[str, Any] | None = None,
    threshold: float = 0.2,
    *,
    include_support_cells: bool = True,
) -> dict[str, Any]:
    components = detect_field_components(
        field_state,
        threshold=threshold,
        include_support_cells=include_support_cells,
    )
    previous_components = previous_summary.get("components", []) if previous_summary else []
    previous_signatures = {component["mode_signature"] for component in previous_components}
    current_signatures = {component["mode_signature"] for component in components}
    born = sorted(current_signatures - previous_signatures)
    decayed = sorted(previous_signatures - current_signatures)
    return {
        "field_state_id": field_state.field_state_id,
        "tick": field_state.tick,
        "threshold": threshold,
        "component_count": len(components),
        "total_component_energy": sum(component["energy"] for component in components),
        "component_birth_count": len(born),
        "component_decay_count": len(decayed),
        "born_mode_signatures": born,
        "decayed_mode_signatures": decayed,
        "components": components,
    }
