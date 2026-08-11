#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from world_engine.five_phase_causal import (  # noqa: E402
    COUNTERFACTUAL_RELAXATION_TICKS,
    DEFAULT_ARTIFACT_BUDGET_BYTES,
    build_causal_comparison_record,
    build_causal_run_manifest,
    build_causal_tick_metrics,
    build_counterfactual_perturbation_stability_evidence,
    build_feedback_effect_probe_records,
    build_perturbation_schedule,
    canonical_digest,
    canonical_json_bytes,
    jsonable,
    mean_feedback_distance,
    mean_pattern_stability,
)
from world_engine.five_phase_causal_completion import evaluate_five_phase_causal_completion  # noqa: E402
from world_engine.implicit_live_session import DEFAULT_OBSERVER_ID, ImplicitFieldSession  # noqa: E402


def _write_json(path: Path, value: Any, *, pretty: bool = False) -> None:
    if pretty:
        text = json.dumps(jsonable(value), indent=2, sort_keys=True)
    else:
        text = json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"))
    path.write_text(text, encoding="utf-8")


def _interaction_request(event: Mapping[str, Any], *, session: ImplicitFieldSession) -> dict[str, Any]:
    frame = session.projection_frames[-1]
    request = {
        "schema": "implicit_interaction_request",
        "request_id": str(event["event_id"]),
        "tool": str(event["tool"]),
        "observer_id": DEFAULT_OBSERVER_ID,
        "source_projection_frame_id": frame.frame_id,
        "source_frame_tick": int(frame.tick),
        "source_state_id": str(session.current_state["implicit_field_state_id"]),
        "source_ray_sample_record_id": str(
            frame.payload["implicit_ray_sample_record"]["ray_sample_record_id"]
        ),
        "source_image_xy": list(event["source_image_xy"]),
        "radius_world": float(event["radius_world"]),
        "amplitude": float(event["amplitude"]),
        "duration_ticks": float(event["duration_ticks"]),
        "advance_after_accept": False,
    }
    if event.get("source_vector_image") is not None:
        request["source_vector_image"] = list(event["source_vector_image"])
    return request


def _restore_branch(
    *,
    initial_snapshot: Mapping[str, Any],
    run_id: str,
    branch_name: str,
    source_package_name: str,
    source_package_digest: str,
    feedback_enabled: bool,
) -> ImplicitFieldSession:
    return ImplicitFieldSession.rehydrate_snapshot(
        initial_snapshot,
        expected_snapshot_digest=str(initial_snapshot["snapshot_digest"]),
        five_phase_feedback_enabled_override=bool(feedback_enabled),
    )


def _run_branch(
    session: ImplicitFieldSession,
    *,
    branch_name: str,
    ticks: int,
    perturbation_schedule: Mapping[str, Any],
) -> None:
    events_by_tick: dict[int, list[Mapping[str, Any]]] = {}
    for event in perturbation_schedule.get("events", []):
        events_by_tick.setdefault(int(event["apply_tick"]), []).append(event)
    for target_tick in range(1, int(ticks) + 1):
        for event in events_by_tick.get(target_tick, []):
            session.apply_interaction(_interaction_request(event, session=session))
        session.advance(1)


def _run_counterfactual_perturbation_pair(
    *,
    initial_snapshot: Mapping[str, Any],
    run_id: str,
    source_package_name: str,
    source_package_digest: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    control = _restore_branch(
        initial_snapshot=initial_snapshot,
        run_id=run_id,
        branch_name="counterfactual-control",
        source_package_name=source_package_name,
        source_package_digest=source_package_digest,
        feedback_enabled=False,
    )
    zero = _restore_branch(
        initial_snapshot=initial_snapshot,
        run_id=run_id,
        branch_name="counterfactual-zero",
        source_package_name=source_package_name,
        source_package_digest=source_package_digest,
        feedback_enabled=False,
    )
    event = {
        "schema": "five_phase_counterfactual_perturbation_event_v1",
        "event_id": f"five-phase-counterfactual-perturbation::{run_id}",
        "tool": "implicit_local_excite",
        "source_image_xy": [0.35, 0.42],
        "radius_world": 0.75,
        "amplitude": 0.22,
        "duration_ticks": 1.0,
        "is_authority_state": False,
    }
    control_request = _interaction_request(event, session=control)
    zero_event = dict(event)
    zero_event["amplitude"] = 0.0
    zero_request = _interaction_request(zero_event, session=zero)
    control.apply_interaction(control_request)
    zero.apply_interaction(zero_request)
    for _ in range(1 + COUNTERFACTUAL_RELAXATION_TICKS):
        control.advance(1)
        zero.advance(1)
    return control.export_artifacts(), zero.export_artifacts()


def run_five_phase_causal_closed_loop_validation(
    *,
    output_dir: Path,
    ticks: int = 64,
    source_package_name: str = "source-a",
    artifact_budget_bytes: int = DEFAULT_ARTIFACT_BUDGET_BYTES,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = "five-phase-causal-closed-loop"
    source_package_digest = f"digest-{source_package_name}"
    seed = ImplicitFieldSession.from_source_package(
        source_package_name=source_package_name,
        source_package_digest=source_package_digest,
        case_type="implicit_full_scene",
        run_id=f"{run_id}-seed",
        image_shape=[24, 16],
        samples_per_ray=8,
        five_phase_feedback_enabled=True,
    )
    initial_snapshot = copy.deepcopy(seed.to_snapshot())
    initial_snapshot_digest = str(initial_snapshot["snapshot_digest"])
    perturbation_schedule = build_perturbation_schedule(run_id=run_id, ticks=int(ticks))

    counterfactual_control_export, counterfactual_zero_export = _run_counterfactual_perturbation_pair(
        initial_snapshot=initial_snapshot,
        run_id=run_id,
        source_package_name=source_package_name,
        source_package_digest=source_package_digest,
    )
    counterfactual_perturbation_stability = (
        build_counterfactual_perturbation_stability_evidence(
            run_id=run_id,
            initial_snapshot=initial_snapshot,
            control_export=counterfactual_control_export,
            zero_export=counterfactual_zero_export,
        )
    )

    disabled = _restore_branch(
        initial_snapshot=initial_snapshot,
        run_id=run_id,
        branch_name="disabled",
        source_package_name=source_package_name,
        source_package_digest=source_package_digest,
        feedback_enabled=False,
    )
    enabled = _restore_branch(
        initial_snapshot=initial_snapshot,
        run_id=run_id,
        branch_name="enabled",
        source_package_name=source_package_name,
        source_package_digest=source_package_digest,
        feedback_enabled=True,
    )

    _run_branch(disabled, branch_name="disabled", ticks=int(ticks), perturbation_schedule=perturbation_schedule)
    _run_branch(enabled, branch_name="enabled", ticks=int(ticks), perturbation_schedule=perturbation_schedule)

    disabled_export = disabled.export_artifacts()
    enabled_export = enabled.export_artifacts()
    disabled_export_digest = canonical_digest(disabled_export)
    enabled_export_digest = canonical_digest(enabled_export)
    disabled_bytes = canonical_json_bytes(disabled_export)
    enabled_bytes = canonical_json_bytes(enabled_export)

    disabled_manifest = build_causal_run_manifest(
        run_id=disabled.run_id,
        branch_name="disabled",
        source_package_name=source_package_name,
        source_package_digest=source_package_digest,
        ticks=int(ticks),
        feedback_enabled=False,
        initial_snapshot_digest=initial_snapshot_digest,
        perturbation_schedule_digest=str(perturbation_schedule["schedule_digest"]),
        export_digest=disabled_export_digest,
        artifact_bytes=disabled_bytes,
        artifact_budget_bytes=artifact_budget_bytes,
        residual_distance_mean=mean_feedback_distance(disabled_export),
        pattern_stability_mean=mean_pattern_stability(disabled_export),
    )
    enabled_manifest = build_causal_run_manifest(
        run_id=enabled.run_id,
        branch_name="enabled",
        source_package_name=source_package_name,
        source_package_digest=source_package_digest,
        ticks=int(ticks),
        feedback_enabled=True,
        initial_snapshot_digest=initial_snapshot_digest,
        perturbation_schedule_digest=str(perturbation_schedule["schedule_digest"]),
        export_digest=enabled_export_digest,
        artifact_bytes=enabled_bytes,
        artifact_budget_bytes=artifact_budget_bytes,
        residual_distance_mean=mean_feedback_distance(enabled_export),
        pattern_stability_mean=mean_pattern_stability(enabled_export),
    )
    probes = build_feedback_effect_probe_records(
        run_id=run_id,
        enabled_export=enabled_export,
        disabled_export=disabled_export,
    )
    tick_metrics = build_causal_tick_metrics(
        run_id=run_id,
        enabled_export=enabled_export,
        disabled_export=disabled_export,
        probes=probes,
    )
    comparison = build_causal_comparison_record(
        run_id=run_id,
        enabled_manifest=enabled_manifest,
        disabled_manifest=disabled_manifest,
        perturbation_schedule=perturbation_schedule,
        tick_metrics=tick_metrics,
        feedback_effect_probes=probes,
    )
    artifact_dir = output_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_paths = {
        "disabled_export": artifact_dir / "disabled_export.json",
        "enabled_export": artifact_dir / "enabled_export.json",
        "disabled_manifest": artifact_dir / "disabled_manifest.json",
        "enabled_manifest": artifact_dir / "enabled_manifest.json",
        "perturbation_schedule": artifact_dir / "perturbation_schedule.json",
        "tick_metrics": artifact_dir / "tick_metrics.json",
        "feedback_effect_probes": artifact_dir / "feedback_effect_probes.json",
        "comparison": artifact_dir / "causal_comparison.json",
        "counterfactual_perturbation_stability": (
            artifact_dir / "counterfactual_perturbation_stability.json"
        ),
    }
    _write_json(artifact_paths["disabled_export"], disabled_export)
    _write_json(artifact_paths["enabled_export"], enabled_export)
    _write_json(artifact_paths["disabled_manifest"], disabled_manifest)
    _write_json(artifact_paths["enabled_manifest"], enabled_manifest)
    _write_json(artifact_paths["perturbation_schedule"], perturbation_schedule)
    _write_json(artifact_paths["tick_metrics"], tick_metrics)
    _write_json(artifact_paths["feedback_effect_probes"], probes)
    _write_json(artifact_paths["comparison"], comparison)
    _write_json(
        artifact_paths["counterfactual_perturbation_stability"],
        counterfactual_perturbation_stability,
    )
    artifact_bytes_by_file = {name: path.stat().st_size for name, path in artifact_paths.items()}
    artifact_bytes_total = sum(artifact_bytes_by_file.values())
    completion_bundle = {
        "schema": "five_phase_causal_completion_bundle_v1",
        "run_id": run_id,
        "enabled_export": enabled_export,
        "disabled_export": disabled_export,
        "enabled_manifest": enabled_manifest,
        "disabled_manifest": disabled_manifest,
        "perturbation_schedule": perturbation_schedule,
        "tick_metrics": tick_metrics,
        "feedback_effect_probes": probes,
        "comparison": comparison,
        "counterfactual_perturbation_stability": counterfactual_perturbation_stability,
        "artifact_bytes_total": artifact_bytes_total,
        "artifact_bytes_by_file": artifact_bytes_by_file,
        "artifact_budget_bytes": int(artifact_budget_bytes),
        "artifact_paths": {name: str(path) for name, path in artifact_paths.items()},
    }
    completion = evaluate_five_phase_causal_completion(completion_bundle)
    overall_status = (
        "passed"
        if completion["overall_status"] == "passed"
        and counterfactual_perturbation_stability["gate_status"] == "passed"
        else "failed"
    )
    report = {
        "schema": "five_phase_causal_closed_loop_validation_report_v1",
        "overall_status": overall_status,
        "run_id": run_id,
        "source_package_name": source_package_name,
        "ticks": int(ticks),
        "expected_case_count": 2,
        "case_count": 2,
        "cases_passed": 2 if overall_status == "passed" else 0,
        "initial_snapshot_digest": initial_snapshot_digest,
        "perturbation_schedule_digest": perturbation_schedule["schedule_digest"],
        "disabled_manifest": disabled_manifest,
        "enabled_manifest": enabled_manifest,
        "comparison": comparison,
        "counterfactual_stability_status": counterfactual_perturbation_stability["gate_status"],
        "counterfactual_perturbation_stability": counterfactual_perturbation_stability,
        "completion": completion,
        "artifact_bytes_total": artifact_bytes_total,
        "artifact_bytes_by_file": artifact_bytes_by_file,
        "artifact_budget_bytes": int(artifact_budget_bytes),
        "artifact_paths": {name: str(path) for name, path in artifact_paths.items()},
    }

    _write_json(output_dir / "five_phase_causal_closed_loop_report.json", report, pretty=True)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run FivePhase causal closed-loop validation.")
    parser.add_argument("--output-dir", type=Path, default=Path("tmp/five_phase_causal_closed_loop_validation"))
    parser.add_argument("--ticks", type=int, default=64)
    parser.add_argument("--source-package-name", default="source-a")
    parser.add_argument("--artifact-budget-bytes", type=int, default=DEFAULT_ARTIFACT_BUDGET_BYTES)
    args = parser.parse_args(argv)
    report = run_five_phase_causal_closed_loop_validation(
        output_dir=args.output_dir,
        ticks=args.ticks,
        source_package_name=args.source_package_name,
        artifact_budget_bytes=args.artifact_budget_bytes,
    )
    print(json.dumps(jsonable(report), indent=2, sort_keys=True))
    return 0 if report["overall_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
