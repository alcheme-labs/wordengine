from __future__ import annotations

import math
from typing import Any

from world_engine.contracts import FieldState
from world_engine.five_phase import (
    EPS,
    FIVE_PHASE_NAMES,
    MASS_GATE_WIDTH,
    THETA_MASS,
    FivePhaseFieldRecord,
    FivePhaseVector,
    normalize_phase_weights,
    reject_authority_shortcuts,
    sigmoid,
    stable_record_id,
)


Grid = list[list[float]]
VectorGrid = list[list[tuple[float, float]]]


def _shape(grid: Grid) -> tuple[int, int]:
    height = len(grid)
    width = len(grid[0]) if height else 0
    return height, width


def _zeros(height: int, width: int) -> Grid:
    return [[0.0 for _ in range(width)] for _ in range(height)]


def _central_x(grid: Grid, row: int, col: int) -> float:
    height, width = _shape(grid)
    left = grid[row][max(0, col - 1)]
    right = grid[row][min(width - 1, col + 1)]
    return (right - left) * 0.5


def _central_y(grid: Grid, row: int, col: int) -> float:
    height, _ = _shape(grid)
    up = grid[max(0, row - 1)][col]
    down = grid[min(height - 1, row + 1)][col]
    return (down - up) * 0.5


def _grad(grid: Grid) -> tuple[VectorGrid, Grid]:
    height, width = _shape(grid)
    vectors: VectorGrid = []
    magnitudes: Grid = []
    for row in range(height):
        vector_row: list[tuple[float, float]] = []
        mag_row: list[float] = []
        for col in range(width):
            gx = _central_x(grid, row, col)
            gy = _central_y(grid, row, col)
            vector_row.append((gx, gy))
            mag_row.append(math.sqrt(gx * gx + gy * gy))
        vectors.append(vector_row)
        magnitudes.append(mag_row)
    return vectors, magnitudes


def _laplacian(grid: Grid) -> Grid:
    height, width = _shape(grid)
    lap = _zeros(height, width)
    for row in range(height):
        for col in range(width):
            center = grid[row][col]
            left = grid[row][max(0, col - 1)]
            right = grid[row][min(width - 1, col + 1)]
            up = grid[max(0, row - 1)][col]
            down = grid[min(height - 1, row + 1)][col]
            lap[row][col] = left + right + up + down - 4.0 * center
    return lap


def _blur3x3(grid: Grid) -> Grid:
    height, width = _shape(grid)
    blurred = _zeros(height, width)
    for row in range(height):
        for col in range(width):
            total = 0.0
            count = 0
            for rr in range(max(0, row - 1), min(height, row + 2)):
                for cc in range(max(0, col - 1), min(width, col + 2)):
                    total += grid[rr][cc]
                    count += 1
            blurred[row][col] = total / max(count, 1)
    return blurred


def _normalize_abs(grid: Grid) -> tuple[Grid, dict[str, float]]:
    max_abs = max((abs(value) for row in grid for value in row), default=0.0)
    scale = max(max_abs, EPS)
    return [[abs(value) / scale for value in row] for row in grid], {"max_abs": max_abs, "scale": scale}


def _normalize_signed(grid: Grid) -> tuple[Grid, dict[str, float]]:
    max_abs = max((abs(value) for row in grid for value in row), default=0.0)
    scale = max(max_abs, EPS)
    return [[value / scale for value in row] for row in grid], {"max_abs": max_abs, "scale": scale}


def _divergence(vector_grid: VectorGrid) -> Grid:
    height = len(vector_grid)
    width = len(vector_grid[0]) if height else 0
    jx = [[vector_grid[row][col][0] for col in range(width)] for row in range(height)]
    jy = [[vector_grid[row][col][1] for col in range(width)] for row in range(height)]
    div = _zeros(height, width)
    for row in range(height):
        for col in range(width):
            div[row][col] = _central_x(jx, row, col) + _central_y(jy, row, col)
    return div


def _curl(vector_grid: VectorGrid) -> Grid:
    height = len(vector_grid)
    width = len(vector_grid[0]) if height else 0
    jx = [[vector_grid[row][col][0] for col in range(width)] for row in range(height)]
    jy = [[vector_grid[row][col][1] for col in range(width)] for row in range(height)]
    curl = _zeros(height, width)
    for row in range(height):
        for col in range(width):
            curl[row][col] = _central_x(jy, row, col) - _central_y(jx, row, col)
    return curl


def _compact_grid(rho: Grid) -> Grid:
    height, width = _shape(rho)
    peak = max((value for row in rho for value in row), default=0.0)
    if peak <= 0.0:
        return _zeros(height, width)
    threshold = max(THETA_MASS * 0.25, peak * 0.2)
    active = [(row, col) for row in range(height) for col in range(width) if rho[row][col] >= threshold]
    if not active:
        return _zeros(height, width)
    rows = [row for row, _ in active]
    cols = [col for _, col in active]
    bbox_area = (max(rows) - min(rows) + 1) * (max(cols) - min(cols) + 1)
    compact = len(active) / max(float(bbox_area), EPS)
    out = _zeros(height, width)
    for row, col in active:
        out[row][col] = compact
    return out


def _weighted_aggregate(cell_phase_vectors: list[list[FivePhaseVector]], rho: Grid) -> FivePhaseVector:
    totals = {name: 0.0 for name in FIVE_PHASE_NAMES}
    weight_sum = 0.0
    for row_index, row in enumerate(cell_phase_vectors):
        for col_index, vector in enumerate(row):
            weight = rho[row_index][col_index]
            weight_sum += weight
            values = vector.to_dict()
            for name in FIVE_PHASE_NAMES:
                totals[name] += weight * values[name]
    if weight_sum <= 0.0:
        for row in cell_phase_vectors:
            for vector in row:
                values = vector.to_dict()
                for name in FIVE_PHASE_NAMES:
                    totals[name] += values[name]
                weight_sum += 1.0
    if weight_sum <= 0.0:
        raise ValueError("cannot aggregate empty phase field.")
    return FivePhaseVector(**{name: totals[name] / weight_sum for name in FIVE_PHASE_NAMES}).normalized()


def _grid_to_json(grid: Grid) -> list[list[float]]:
    return [[float(value) for value in row] for row in grid]


def _vector_grid_to_json(grid: VectorGrid) -> list[list[list[float]]]:
    return [[[float(x), float(y)] for x, y in row] for row in grid]


def _assert_grid_finite(name: str, grid: Grid) -> None:
    for row in grid:
        for value in row:
            if not math.isfinite(value):
                raise ValueError(f"{name} emitted non-finite feature.")


def extract_five_phase_field(
    field_state: FieldState,
    *,
    previous_field_state: FieldState | None = None,
    channel_name: str = "pattern",
) -> FivePhaseFieldRecord:
    """Derive continuous FivePhase weights from read-back FieldState channel data."""

    reject_authority_shortcuts(field_state.payload, path="field_state.payload")
    if channel_name not in field_state.channels:
        raise ValueError(f"FieldState missing FivePhase extraction channel {channel_name!r}.")
    u = [[float(value) for value in row] for row in field_state.channels[channel_name]]
    height, width = _shape(u)
    if height == 0 or width == 0:
        raise ValueError("FivePhase extraction requires a non-empty grid.")

    if previous_field_state is not None:
        if channel_name not in previous_field_state.channels:
            raise ValueError(f"previous FieldState missing channel {channel_name!r}.")
        previous = [[float(value) for value in row] for row in previous_field_state.channels[channel_name]]
    else:
        previous = [[float(value) for value in row] for row in field_state.previous_channels.get(channel_name, _zeros(height, width))]

    rho = [[value * value for value in row] for row in u]
    previous_rho = [[value * value for value in row] for row in previous]
    grad, grad_mag = _grad(u)
    lap = _laplacian(u)
    delta = [[abs(u[row][col] - previous[row][col]) for col in range(width)] for row in range(height)]
    growth = [[max(rho[row][col] - previous_rho[row][col], 0.0) for col in range(width)] for row in range(height)]
    affinity = _blur3x3(u)
    affinity_grad, _ = _grad(affinity)
    rho_grad, _ = _grad(rho)
    mass_gate = [
        [sigmoid((rho[row][col] - THETA_MASS) / MASS_GATE_WIDTH) for col in range(width)]
        for row in range(height)
    ]
    flow: VectorGrid = []
    flux: VectorGrid = []
    speed = _zeros(height, width)
    for row in range(height):
        flow_row: list[tuple[float, float]] = []
        flux_row: list[tuple[float, float]] = []
        for col in range(width):
            gate = mass_gate[row][col]
            fx = (1.0 - gate) * affinity_grad[row][col][0] - gate * rho_grad[row][col][0]
            fy = (1.0 - gate) * affinity_grad[row][col][1] - gate * rho_grad[row][col][1]
            jx = rho[row][col] * fx
            jy = rho[row][col] * fy
            flow_row.append((fx, fy))
            flux_row.append((jx, jy))
            speed[row][col] = math.sqrt(jx * jx + jy * jy) / (rho[row][col] + EPS)
        flow.append(flow_row)
        flux.append(flux_row)
    divj = _divergence(flux)
    curlj = _curl(flux)
    compact = _compact_grid(rho)

    rho_n, rho_norm = _normalize_abs(rho)
    grad_n, grad_norm = _normalize_abs(grad_mag)
    delta_n, delta_norm = _normalize_abs(delta)
    growth_n, growth_norm = _normalize_abs(growth)
    speed_n, speed_norm = _normalize_abs(speed)
    divj_n_signed, divj_norm = _normalize_signed(divj)
    curlj_n, curlj_norm = _normalize_abs(curlj)
    positive_divj_n = [[max(value, 0.0) for value in row] for row in divj_n_signed]
    abs_divj_n = [[abs(value) for value in row] for row in divj_n_signed]
    peak_rho = max((value for row in rho_n for value in row), default=0.0)
    low_grad = [[rho_n[row][col] * (1.0 - grad_n[row][col]) for col in range(width)] for row in range(height)]

    feature_grids = {
        "rho": rho,
        "grad_mag": grad_mag,
        "lap": lap,
        "delta": delta,
        "growth": growth,
        "affinity": affinity,
        "mass_gate": mass_gate,
        "speed": speed,
        "divJ": divj,
        "curlJ": curlj,
        "compact": compact,
        "low_grad": low_grad,
    }
    for feature_name, grid in feature_grids.items():
        _assert_grid_finite(feature_name, grid)

    cell_phase_vectors: list[list[FivePhaseVector]] = []
    for row in range(height):
        phase_row: list[FivePhaseVector] = []
        for col in range(width):
            raw = {
                "contractive": sigmoid(
                    +1.2 * rho_n[row][col]
                    + 1.0 * compact[row][col]
                    + 0.5 * grad_n[row][col]
                    - 0.8 * delta_n[row][col]
                    - 0.5 * abs_divj_n[row][col]
                ),
                "generative": sigmoid(
                    +1.1 * growth_n[row][col]
                    + 0.5 * grad_n[row][col]
                    + 0.4 * positive_divj_n[row][col]
                    - 0.4 * compact[row][col]
                ),
                "transport": sigmoid(
                    +1.1 * speed_n[row][col]
                    + 0.8 * abs_divj_n[row][col]
                    + 0.6 * curlj_n[row][col]
                ),
                "radiant": sigmoid(
                    +1.0 * delta_n[row][col]
                    + 0.8 * grad_n[row][col]
                    + 0.6 * positive_divj_n[row][col]
                    + 0.5 * peak_rho
                ),
                "substrate": sigmoid(
                    +1.1 * rho_n[row][col]
                    + 0.9 * low_grad[row][col]
                    + 0.4 * compact[row][col]
                    - 0.7 * delta_n[row][col]
                    - 0.4 * grad_n[row][col]
                ),
            }
            vector = normalize_phase_weights(raw)
            if abs(sum(vector.to_dict().values()) - 1.0) > 1e-6:
                raise ValueError("FivePhase cell vector normalization failed.")
            phase_row.append(vector)
        cell_phase_vectors.append(phase_row)

    aggregate_phase = _weighted_aggregate(cell_phase_vectors, rho)
    metrics: dict[str, Any] = {
        "formula": "five_phase_readback_extraction_v1",
        "channel_name": channel_name,
        "rho": _grid_to_json(rho),
        "grad": _vector_grid_to_json(grad),
        "grad_mag": _grid_to_json(grad_mag),
        "lap": _grid_to_json(lap),
        "delta": _grid_to_json(delta),
        "growth": _grid_to_json(growth),
        "affinity": _grid_to_json(affinity),
        "mass_gate": _grid_to_json(mass_gate),
        "F": _vector_grid_to_json(flow),
        "J": _vector_grid_to_json(flux),
        "speed": _grid_to_json(speed),
        "divJ": _grid_to_json(divj),
        "curlJ": _grid_to_json(curlj),
        "compact": _grid_to_json(compact),
        "low_grad": _grid_to_json(low_grad),
        "normalization": {
            "rho": rho_norm,
            "grad_mag": grad_norm,
            "delta": delta_norm,
            "growth": growth_norm,
            "speed": speed_norm,
            "divJ": divj_norm,
            "curlJ": curlj_norm,
        },
        "feature_summaries": {
            "mean_rho": sum(sum(row) for row in rho) / (height * width),
            "mean_delta": sum(sum(row) for row in delta) / (height * width),
            "mean_speed": sum(sum(row) for row in speed) / (height * width),
            "peak_rho": max((value for row in rho for value in row), default=0.0),
        },
    }
    source_ids = tuple(dict.fromkeys((field_state.field_state_id, *field_state.source_record_ids)))
    record_payload = {
        "field_state_id": field_state.field_state_id,
        "tick": field_state.tick,
        "channel": channel_name,
        "aggregate_phase": aggregate_phase.to_dict(),
    }
    return FivePhaseFieldRecord(
        record_id=stable_record_id("five-phase-field", record_payload),
        schema="five_phase_field_v1",
        tick=field_state.tick,
        source_field_state_id=field_state.field_state_id,
        grid_shape=tuple(int(value) for value in field_state.grid_shape),
        aggregate_phase=aggregate_phase,
        cell_phase_vectors=tuple(tuple(row) for row in cell_phase_vectors),
        metrics=metrics,
        source_record_ids=source_ids,
        is_authority_state=False,
    )


__all__ = ["extract_five_phase_field"]
