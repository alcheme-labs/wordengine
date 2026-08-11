#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from world_engine.five_phase_live_completion import evaluate_five_phase_live_completion  # noqa: E402
from world_engine.implicit_live_session import ImplicitFieldSession  # noqa: E402
from world_engine.viewer import build_world_viewer_html  # noqa: E402


def _jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(_jsonable(value), indent=2, sort_keys=True), encoding="utf-8")


def _write_jsonl(path: Path, values: list[Any]) -> None:
    path.write_text("".join(json.dumps(_jsonable(value), sort_keys=True) + "\n" for value in values), encoding="utf-8")


def run_five_phase_live_world_validation(
    *,
    output_dir: Path,
    ticks: int = 8,
    source_package_name: str = "source-a",
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    session = ImplicitFieldSession.from_source_package(
        source_package_name=source_package_name,
        source_package_digest=f"digest-{source_package_name}",
        case_type="implicit_full_scene",
        run_id="five-phase-live-world",
        image_shape=[24, 16],
        samples_per_ray=8,
    )
    session.advance(int(ticks))
    exported = session.export_artifacts()
    completion = evaluate_five_phase_live_completion(exported)
    case_status = "passed" if completion["overall_status"] == "passed" else "failed"

    viewer_dir = output_dir / "viewer"
    viewer_dir.mkdir(parents=True, exist_ok=True)
    frames = [frame.to_dict() for frame in session.projection_frames]
    _write_jsonl(viewer_dir / "projection_frames.jsonl", frames)
    world_run = {"projection_frames": frames, "world_states": [], "completion": completion}
    (viewer_dir / "viewer.html").write_text(build_world_viewer_html(world_run), encoding="utf-8")

    artifact_dir = output_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    _write_json(artifact_dir / "five_phase_live_export.json", exported)

    report = {
        "schema": "five_phase_live_world_validation_report_v1",
        "overall_status": case_status,
        "expected_case_count": 1,
        "case_count": 1,
        "cases_passed": 1 if case_status == "passed" else 0,
        "ticks": int(ticks),
        "projection_frame_count": len(session.projection_frames),
        "five_phase_live_step_count": len(session.five_phase_live_steps),
        "implicit_live_step_count": len(session.implicit_live_steps),
        "completion": completion,
        "viewer_dir": str(viewer_dir),
        "viewer_path": str(viewer_dir / "viewer.html"),
        "artifact_path": str(artifact_dir / "five_phase_live_export.json"),
        "cases": [
            {
                "case_id": "five_phase_live_world",
                "case_type": "implicit_full_scene",
                "source_package_name": source_package_name,
                "completion_status": completion["overall_status"],
                "projection_frame_count": len(session.projection_frames),
                "five_phase_live_step_count": len(session.five_phase_live_steps),
            }
        ],
    }
    _write_json(output_dir / "five_phase_live_world_report.json", report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run FivePhase live world validation.")
    parser.add_argument("--output-dir", type=Path, default=Path("tmp/five_phase_live_world_validation"))
    parser.add_argument("--ticks", type=int, default=8)
    parser.add_argument("--source-package-name", default="source-a")
    args = parser.parse_args(argv)
    report = run_five_phase_live_world_validation(
        output_dir=args.output_dir,
        ticks=args.ticks,
        source_package_name=args.source_package_name,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["overall_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
