from __future__ import annotations

import hashlib
import json
from typing import Any

from world_engine.contracts import FieldState


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def make_coordinate_frame(height: int, width: int) -> dict[str, Any]:
    return {
        "world_origin": [0.0, 0.0],
        "world_extent": [float(width), float(height)],
        "grid_shape": [height, width],
        "world_to_grid": "linear_world_to_grid_v1",
        "grid_to_world": "linear_grid_to_world_v1",
        "source_observer_window": {
            "x_min": 0.0,
            "y_min": 0.0,
            "x_max": float(width),
            "y_max": float(height),
        },
    }


def make_field_payload(
    *,
    tick: int,
    height: int,
    width: int,
    previous_field_state_id: str | None = None,
    field_wave_step_record_id: str | None = None,
) -> dict[str, Any]:
    evidence_digest = _digest({"seed": "five-phase-test", "height": height, "width": width})
    evidence_id = f"stable-composite-evidence:sha256:{evidence_digest}"
    bridge_id = f"field-evidence-bridge:sha256:{_digest({'bridge': evidence_id})}"
    return {
        "authority_role": "field_substrate",
        "wave_kernel": "five_phase_test_fixture_kernel_v1",
        "source_package_digest": "sha256:five-phase-test-source",
        "stable_composite_evidence_id": evidence_id,
        "stable_composite_evidence_digest": evidence_digest,
        "field_evidence_bridge_id": bridge_id,
        "previous_field_state_id": previous_field_state_id,
        "source_field_state_ids": [previous_field_state_id] if previous_field_state_id else [],
        "field_wave_step_record_id": field_wave_step_record_id,
        "channel_families": {"pattern": "five_phase_test_pattern"},
        "seed_mode_signatures": {"pattern": "mode-signature:five-phase-test"},
        "coordinate_frame": make_coordinate_frame(height, width),
    }


def make_field_state(
    grid: list[list[float]],
    *,
    tick: int = 0,
    previous_grid: list[list[float]] | None = None,
    field_state_id: str | None = None,
    previous_field_state_id: str | None = None,
) -> FieldState:
    height = len(grid)
    width = len(grid[0]) if height else 0
    if previous_grid is None:
        previous_grid = [[0.0 for _ in range(width)] for _ in range(height)]
    if field_state_id is None:
        field_state_id = f"field-state::five-phase-test::{tick}::{_digest(grid)[:12]}"
    field_wave_step_record_id = None if tick == 0 else f"field-wave-step::{field_state_id}"
    payload = make_field_payload(
        tick=tick,
        height=height,
        width=width,
        previous_field_state_id=previous_field_state_id,
        field_wave_step_record_id=field_wave_step_record_id,
    )
    source_record_ids = [payload["field_evidence_bridge_id"]]
    if field_wave_step_record_id:
        source_record_ids.append(field_wave_step_record_id)
    return FieldState(
        field_state_id=field_state_id,
        run_id="run::five-phase-test",
        tick=tick,
        rule_id="five_phase_test_fixture_rule_v1",
        grid_shape=[height, width],
        channels={"pattern": grid},
        previous_channels={"pattern": previous_grid},
        energy=sum(value * value for row in grid for value in row),
        source_state_ticks=[tick],
        source_record_ids=source_record_ids,
        payload=payload,
    )
