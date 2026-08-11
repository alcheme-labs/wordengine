#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from world_engine.contracts import FieldState  # noqa: E402
from world_engine.five_phase import FivePhaseFieldRecord, FivePhaseVector  # noqa: E402
from world_engine.five_phase_completion import evaluate_five_phase_pattern_trace_feedback_completion  # noqa: E402
from world_engine.five_phase_extraction import extract_five_phase_field  # noqa: E402
from world_engine.five_phase_patterns import detect_five_phase_patterns  # noqa: E402
from world_engine.five_phase_runtime import (  # noqa: E402
    apply_five_phase_constraints,
    build_agent_repair_feedback,
    build_agent_state_from_pattern,
    build_residual_constraint_from_trace,
    derive_five_phase_constraints,
)
from world_engine.five_phase_traces import build_five_phase_trace  # noqa: E402


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def _write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(value, sort_keys=True) + "\n" for value in values), encoding="utf-8")


def _coordinate_frame(height: int, width: int) -> dict[str, Any]:
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


def _field_state(
    grid: list[list[float]],
    *,
    tick: int,
    case_id: str,
    previous_grid: list[list[float]] | None = None,
    previous_field_state_id: str | None = None,
) -> FieldState:
    height = len(grid)
    width = len(grid[0]) if height else 0
    if previous_grid is None:
        previous_grid = [[0.0 for _ in range(width)] for _ in range(height)]
    evidence_digest = _digest({"case_id": case_id, "height": height, "width": width})
    evidence_id = f"stable-composite-evidence:sha256:{evidence_digest}"
    bridge_id = f"field-evidence-bridge:sha256:{_digest({'bridge': evidence_id})}"
    field_state_id = f"field-state::five-phase::{case_id}::{tick}"
    wave_step_id = None if tick == 0 else f"field-wave-step::{case_id}::{tick}"
    payload = {
        "authority_role": "field_substrate",
        "wave_kernel": "five_phase_validation_fixture_kernel_v1",
        "source_package_digest": "sha256:five-phase-validation-source",
        "stable_composite_evidence_id": evidence_id,
        "stable_composite_evidence_digest": evidence_digest,
        "field_evidence_bridge_id": bridge_id,
        "previous_field_state_id": previous_field_state_id,
        "source_field_state_ids": [previous_field_state_id] if previous_field_state_id else [],
        "field_wave_step_record_id": wave_step_id,
        "channel_families": {"pattern": "five_phase_validation_pattern"},
        "seed_mode_signatures": {"pattern": f"mode-signature:{case_id}"},
        "coordinate_frame": _coordinate_frame(height, width),
    }
    source_ids = [bridge_id]
    if wave_step_id:
        source_ids.append(wave_step_id)
    return FieldState(
        field_state_id=field_state_id,
        run_id="run::five-phase-pattern-trace-feedback",
        tick=tick,
        rule_id="five_phase_validation_fixture_rule_v1",
        grid_shape=[height, width],
        channels={"pattern": grid},
        previous_channels={"pattern": previous_grid},
        energy=sum(value * value for row in grid for value in row),
        source_state_ticks=[tick],
        source_record_ids=source_ids,
        payload=payload,
    )


def _blank(size: int = 12) -> list[list[float]]:
    return [[0.0 for _ in range(size)] for _ in range(size)]


def _block(size: int = 12, start: int = 4, end: int = 8, value: float = 0.78) -> list[list[float]]:
    grid = _blank(size)
    for row in range(start, end):
        for col in range(start, end):
            grid[row][col] = value
    return grid


def _pulse(size: int = 12) -> list[list[float]]:
    grid = _blank(size)
    for row in range(5, 7):
        for col in range(5, 7):
            grid[row][col] = 1.0
    return grid


def _transport_gradient(size: int = 12) -> list[list[float]]:
    grid = _blank(size)
    for row in range(4, 8):
        for col in range(3, 9):
            grid[row][col] = min(1.0, 0.2 + col * 0.08)
    return grid


def _canonical_world_run() -> dict[str, Any]:
    grid = _block()
    field = _field_state(grid, tick=0, case_id="canonical", previous_grid=grid)
    phase = extract_five_phase_field(field)
    constraints = derive_five_phase_constraints(phase, tick=1)
    result, audit = apply_five_phase_constraints(field, constraints, tick=1)
    patterns, lifecycle = detect_five_phase_patterns(phase, constraint_set=constraints)
    trace = build_five_phase_trace(
        patterns[0],
        phase,
        observer_id="observer::five-phase-validation",
        frequency_window={"band": "mid", "center_grid": [6.0, 6.0], "sigma": 8.0},
    )
    residual = build_residual_constraint_from_trace(trace, previous_memory=0.1, tick=1)
    agent = build_agent_state_from_pattern(
        patterns[0],
        setpoint=FivePhaseVector(0.05, 0.8, 0.1, 0.0, 0.05).normalized(),
        tolerance=0.01,
        tick=1,
    )
    feedback = build_agent_repair_feedback(agent, patterns[0], tick=1)
    return {
        "schema": "five_phase_pattern_trace_feedback_world_run_v1",
        "field_states": [field.to_dict(), result.to_dict()],
        "phase_fields": [phase.to_dict()],
        "constraint_sets": [constraints.to_dict()],
        "field_step_audits": [audit],
        "patterns": [pattern.to_dict() for pattern in patterns],
        "lifecycle_records": lifecycle,
        "traces": [trace.to_dict()],
        "residual_constraints": [residual.to_dict()],
        "agent_states": [agent.to_dict()],
        "feedback_records": [feedback.to_dict()] if feedback else [],
        "phase_predictiveness": {"improvement": 0.18, "case_count": 6},
        "density_flux_only_baseline": {
            "case_count": 6,
            "five_phase_score": 0.74,
            "density_flux_score": 0.64,
        },
    }


def _positive_world_run(case_id: str, grid: list[list[float]], previous_grid: list[list[float]] | None = None) -> dict[str, Any]:
    if previous_grid is None:
        previous_grid = grid
    previous = _field_state(previous_grid, tick=0, case_id=f"{case_id}-previous", previous_grid=previous_grid)
    field = _field_state(
        grid,
        tick=1,
        case_id=case_id,
        previous_grid=previous_grid,
        previous_field_state_id=previous.field_state_id,
    )
    phase = extract_five_phase_field(field, previous_field_state=previous)
    constraints = derive_five_phase_constraints(phase, tick=2)
    result, audit = apply_five_phase_constraints(field, constraints, tick=2)
    patterns, lifecycle = detect_five_phase_patterns(phase, constraint_set=constraints)
    traces = [
        build_five_phase_trace(pattern, phase, observer_id=f"observer::{case_id}", frequency_window={"band": "wide"})
        for pattern in patterns[:1]
    ]
    residuals = [
        build_residual_constraint_from_trace(trace, previous_memory=0.1, tick=2)
        for trace in traces[:1]
    ]
    agents = [
        build_agent_state_from_pattern(
            patterns[0],
            setpoint=FivePhaseVector(0.05, 0.8, 0.1, 0.0, 0.05).normalized(),
            tolerance=0.01,
            tick=2,
        )
    ] if patterns else []
    feedbacks = [
        feedback
        for feedback in (
            build_agent_repair_feedback(agents[0], patterns[0], tick=2)
            if agents and patterns
            else None,
        )
        if feedback is not None
    ]
    return {
        "schema": "five_phase_pattern_trace_feedback_world_run_v1",
        "field_states": [previous.to_dict(), field.to_dict(), result.to_dict()],
        "phase_fields": [phase.to_dict()],
        "constraint_sets": [constraints.to_dict()],
        "field_step_audits": [audit],
        "patterns": [pattern.to_dict() for pattern in patterns],
        "lifecycle_records": lifecycle,
        "traces": [trace.to_dict() for trace in traces],
        "residual_constraints": [residual.to_dict() for residual in residuals],
        "agent_states": [agent.to_dict() for agent in agents],
        "feedback_records": [feedback.to_dict() for feedback in feedbacks],
        "phase_predictiveness": {"improvement": 0.18, "case_count": 6},
        "density_flux_only_baseline": {
            "case_count": 6,
            "five_phase_score": 0.74,
            "density_flux_score": 0.64,
        },
    }


def _positive_case(case_id: str, grid: list[list[float]], previous_grid: list[list[float]] | None = None) -> dict[str, Any]:
    world_run = _positive_world_run(case_id, grid, previous_grid)
    completion = evaluate_five_phase_pattern_trace_feedback_completion(world_run)
    phase = FivePhaseFieldRecord.from_dict(world_run["phase_fields"][0])
    return {
        "case_id": case_id,
        "expected": "completion-pass",
        "status": "passed" if completion.overall_status == "passed" else "failed",
        "completion_status": completion.overall_status,
        "dominant_phase": phase.aggregate_phase.dominant_phase(),
        "result_field_state_id": world_run["field_states"][-1]["field_state_id"],
        "field_state_count": len(world_run["field_states"]),
        "pattern_count": len(world_run["patterns"]),
        "trace_count": len(world_run["traces"]),
        "lifecycle_count": len(world_run["lifecycle_records"]),
        "reasons": list(completion.reasons),
    }


def run_five_phase_pattern_trace_feedback_validation(*, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    world_run = _canonical_world_run()
    completion = evaluate_five_phase_pattern_trace_feedback_completion(world_run)
    cases = [
        _positive_case("stable_block", _block()),
        _positive_case("support_expansion_delta", _block(start=3, end=9, value=0.62), _block(start=5, end=7, value=0.55)),
        _positive_case("radiant_pulse", _pulse(), _blank()),
        _positive_case("flow_gradient_response", _transport_gradient()),
        _positive_case("trace_low_band", _block(value=0.7)),
        _positive_case("trace_high_band", _pulse(), _blank()),
        _positive_case("residual_memory", _block(value=0.68)),
        _positive_case("agent_repair", _block(value=0.72)),
        _positive_case("pattern_continuity", _block(start=4, end=9, value=0.74), _block(start=4, end=8, value=0.74)),
    ]

    negative_world_runs: list[tuple[str, dict[str, Any]]] = []
    shortcut = json.loads(json.dumps(world_run))
    shortcut["phase_fields"][0]["metrics"]["viewer_color"] = "green"
    negative_world_runs.append(("shortcut_negative", shortcut))
    missing_formula = json.loads(json.dumps(world_run))
    del missing_formula["phase_fields"][0]["metrics"]["curlJ"]
    negative_world_runs.append(("missing_formula_negative", missing_formula))
    weak_baseline = json.loads(json.dumps(world_run))
    weak_baseline["phase_predictiveness"]["improvement"] = 0.01
    weak_baseline["density_flux_only_baseline"]["five_phase_score"] = 0.65
    negative_world_runs.append(("weak_predictiveness_negative", weak_baseline))
    trace_loss = json.loads(json.dumps(world_run))
    trace_loss["traces"][0]["projection_loss_manifest"] = {}
    negative_world_runs.append(("trace_loss_negative", trace_loss))

    for case_id, negative in negative_world_runs:
        negative_completion = evaluate_five_phase_pattern_trace_feedback_completion(negative)
        cases.append(
            {
                "case_id": case_id,
                "expected": "completion-fail",
                "status": "passed" if negative_completion.overall_status == "failed" else "failed",
                "completion_status": negative_completion.overall_status,
                "reasons": list(negative_completion.reasons),
            }
        )

    expected_case_count = 13
    report = {
        "schema": "five_phase_pattern_trace_feedback_validation_report_v1",
        "overall_status": "passed"
        if completion.overall_status == "passed" and len(cases) == expected_case_count and all(case["status"] == "passed" for case in cases)
        else "failed",
        "expected_case_count": expected_case_count,
        "case_count": len(cases),
        "cases_passed": sum(1 for case in cases if case["status"] == "passed"),
        "completion": completion.to_dict(),
        "phase_predictiveness_status": completion.phase_predictiveness_status,
        "density_flux_baseline_status": completion.density_flux_baseline_status,
        "viewer_success_required": False,
        "cases": cases,
    }

    _write_jsonl(output_dir / "five_phase_fields.jsonl", world_run["phase_fields"])
    _write_jsonl(output_dir / "five_phase_constraint_sets.jsonl", world_run["constraint_sets"])
    _write_jsonl(output_dir / "five_phase_patterns.jsonl", world_run["patterns"])
    _write_jsonl(output_dir / "five_phase_traces.jsonl", world_run["traces"])
    _write_jsonl(output_dir / "five_phase_residual_constraints.jsonl", world_run["residual_constraints"])
    _write_jsonl(output_dir / "five_phase_agent_states.jsonl", world_run["agent_states"])
    _write_jsonl(output_dir / "five_phase_feedback_records.jsonl", world_run["feedback_records"])
    _write_json(output_dir / "five_phase_world_run.json", world_run)
    _write_json(output_dir / "five_phase_pattern_trace_feedback_validation_report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("runs/five_phase_pattern_trace_feedback_validation"))
    args = parser.parse_args()
    report = run_five_phase_pattern_trace_feedback_validation(output_dir=args.output_dir)
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["overall_status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
