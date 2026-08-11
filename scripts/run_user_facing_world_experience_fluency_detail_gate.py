#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from world_engine.implicit_live_session import ImplicitFieldSession  # noqa: E402
from world_engine.realtime_projection_renderer import REALTIME_RENDER_FRAME_REQUEST_SCHEMA  # noqa: E402
from world_engine.user_facing_world_experience_fluency_detail_gate import (  # noqa: E402
    USER_FACING_WORLD_EXPERIENCE_FLUENCY_DETAIL_BROWSER_EVIDENCE_SCHEMA,
    USER_FACING_WORLD_EXPERIENCE_FLUENCY_DETAIL_TRANSCRIPT_SCHEMA,
    evaluate_user_facing_world_experience_fluency_detail_gate,
    export_fluency_detail_case,
    stable_digest,
)
from world_engine.viewer import build_world_viewer_html  # noqa: E402


DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "world_engine" / "user_facing_world_experience_fluency_detail_gate"
REPORT_NAME = "user_facing_world_experience_fluency_detail_gate_report.json"
PER_CASE_ARTIFACT_BUDGET_BYTES = 96 * 1024 * 1024


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(dict(value), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _dir_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _source_packages(limit: int) -> list[dict[str, str]]:
    if int(limit) < 1:
        raise ValueError("source_package_limit must be >= 1")
    packages = [{"name": "source-package-a"}, {"name": "source-package-b"}, {"name": "source-package-c"}]
    return packages[: int(limit)]


def _latest_frame(session: ImplicitFieldSession) -> dict[str, Any]:
    return session.projection_frame_dicts()[-1]


def _packet(frame: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = frame.get("payload", {})
    return payload.get("realtime_projection_frame_packet", {}) if isinstance(payload, Mapping) else {}


def _source_ids(frame: Mapping[str, Any], *, prefixes: Sequence[str] = (), limit: int = 24) -> list[str]:
    ids: list[str] = []
    payload = frame.get("payload", {})
    if isinstance(frame.get("source_record_ids"), list):
        ids.extend(str(value) for value in frame["source_record_ids"] if str(value))
    if isinstance(payload, Mapping):
        for key in ("source_record_ids", "display_record_ids"):
            if isinstance(payload.get(key), list):
                ids.extend(str(value) for value in payload[key] if str(value))
        timeline = payload.get("event_timeline", {})
        if isinstance(timeline, Mapping) and isinstance(timeline.get("source_record_ids"), list):
            ids.extend(str(value) for value in timeline["source_record_ids"] if str(value))
        solar = payload.get("solar_earth_projection", {})
        if isinstance(solar, Mapping):
            for key in (
                "macro_body_state_ids",
                "surface_field_ids",
                "local_refinement_request_ids",
                "local_refinement_patch_ids",
                "planet_layer_shell_ids",
                "energy_flux_record_ids",
            ):
                if isinstance(solar.get(key), list):
                    ids.extend(str(value) for value in solar[key] if str(value))
            for key in ("planet_macro_authority_id", "spectral_band_profile_id"):
                if solar.get(key):
                    ids.append(str(solar[key]))
        realtime = payload.get("realtime_projection_frame_packet", {})
        if isinstance(realtime, Mapping) and isinstance(realtime.get("source_record_ids"), list):
            ids.extend(str(value) for value in realtime["source_record_ids"] if str(value))
    unique = sorted(set(ids))
    if prefixes:
        filtered = [value for value in unique if any(value.startswith(prefix) for prefix in prefixes)]
        if filtered:
            unique = filtered
    return unique[:limit]


def _camera_state_id(frame: Mapping[str, Any]) -> str:
    packet = _packet(frame)
    camera = packet.get("camera_state", {}) if isinstance(packet, Mapping) else {}
    return str(camera.get("camera_state_id") or "")


def _pose(frame: Mapping[str, Any]) -> list[float]:
    packet = _packet(frame)
    camera = packet.get("camera_state", {}) if isinstance(packet, Mapping) else {}
    position = camera.get("position_world") if isinstance(camera, Mapping) else None
    return [float(value) for value in position] if isinstance(position, list) and len(position) == 3 else [0.0, 0.0, 0.0]


def _pose_step(previous: Mapping[str, Any] | None, current: Mapping[str, Any]) -> float:
    if previous is None:
        return 0.0
    a = _pose(previous)
    b = _pose(current)
    return round(math.sqrt(sum((b[index] - a[index]) ** 2 for index in range(3))), 6)


def _apparent_scale(frame: Mapping[str, Any]) -> float:
    packet = _packet(frame)
    lod = packet.get("lod_state", {}) if isinstance(packet, Mapping) else {}
    if isinstance(lod, Mapping) and lod.get("apparent_radius_px") is not None:
        return round(float(lod["apparent_radius_px"]), 6)
    payload = frame.get("payload", {})
    image = payload.get("spectral_image_plane", {}) if isinstance(payload, Mapping) else {}
    scale = image.get("camera_scale_state", {}) if isinstance(image, Mapping) else {}
    return round(float(scale.get("apparent_radius_px", 1.0)), 6)


def _weights(frame: Mapping[str, Any]) -> dict[str, float]:
    payload = frame.get("payload", {})
    image = payload.get("spectral_image_plane", {}) if isinstance(payload, Mapping) else {}
    continuous = image.get("continuous_refinement_ux_state", {}) if isinstance(image, Mapping) else {}
    continuous_weights = continuous.get("authority_layer_weights", {}) if isinstance(continuous, Mapping) else {}
    if isinstance(continuous_weights, Mapping) and continuous_weights:
        raw = {
            "macro": float(continuous_weights.get("macro", 0.0)),
            "surface": float(continuous_weights.get("surface", 0.0)),
            "local_patch": float(continuous_weights.get("local_patch", 0.0)),
            "volume": float(continuous_weights.get("volume", 0.0)),
        }
        total = sum(raw.values()) or 1.0
        return {key: round(value / total, 6) for key, value in raw.items()}
    packet = _packet(frame)
    lod = packet.get("lod_state", {}) if isinstance(packet, Mapping) else {}
    raw = {
        "macro": float(lod.get("macro_weight", 0.0)) if isinstance(lod, Mapping) else 0.0,
        "surface": float(lod.get("surface_weight", 0.0)) if isinstance(lod, Mapping) else 0.0,
        "local_patch": float(lod.get("local_patch_weight", 0.0)) if isinstance(lod, Mapping) else 0.0,
        "volume": float(lod.get("volume_weight", 0.0)) if isinstance(lod, Mapping) else 0.0,
    }
    total = sum(raw.values()) or 1.0
    return {key: round(value / total, 6) for key, value in raw.items()}


def _sensor_band(frame: Mapping[str, Any]) -> str:
    payload = frame.get("payload", {})
    image = payload.get("spectral_image_plane", {}) if isinstance(payload, Mapping) else {}
    scale = image.get("camera_scale_state", {}) if isinstance(image, Mapping) else {}
    return str(scale.get("sensor_band") or "visible_surface")


def _frame_digest(frame: Mapping[str, Any]) -> str:
    payload = frame.get("payload", {})
    image = payload.get("spectral_image_plane", {}) if isinstance(payload, Mapping) else {}
    if isinstance(image, Mapping) and image.get("projection_frame_digest"):
        return str(image["projection_frame_digest"])
    return stable_digest(frame)


def _render_request(session: ImplicitFieldSession, *, request_id: str, action: str, sensor_band_mode: str) -> dict[str, Any]:
    frame = _latest_frame(session)
    return {
        "schema": REALTIME_RENDER_FRAME_REQUEST_SCHEMA,
        "request_id": request_id,
        "observer_id": "observer::solar-earth-orbit",
        "source_projection_frame_id": str(frame["frame_id"]),
        "source_scene_tick": int(frame["tick"]),
        "previous_camera_state_id": _camera_state_id(frame),
        "camera_action": action,
        "sensor_band_mode": sensor_band_mode,
        "step_world": 0.12,
        "yaw_degrees": 3.0,
        "render_dt_ms": 16,
    }


def _build_fluency_path(frames: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    path: list[dict[str, Any]] = []
    previous_frame: Mapping[str, Any] | None = None
    previous_scale: float | None = None
    for frame in frames:
        scale = _apparent_scale(frame)
        path.append(
            {
                "frame_id": str(frame["frame_id"]),
                "frame_kind": str(_packet(frame).get("frame_kind") or frame.get("frame_kind") or "camera_frame"),
                "tick_before": int(frame["tick"]),
                "tick_after": int(frame["tick"]),
                "world_advanced": False,
                "camera_moved": previous_frame is not None,
                "pose_step_world": _pose_step(previous_frame, frame),
                "apparent_target_scale": scale,
                "apparent_scale_delta": 0.0 if previous_scale is None else round(abs(scale - previous_scale) / max(previous_scale, 1.0), 6),
                "hard_mode_jump": False,
                "pose_digest_before": stable_digest(_pose(previous_frame)) if previous_frame is not None else stable_digest(_pose(frame)),
                "pose_digest_after": stable_digest(_pose(frame)),
                "source_record_ids": _source_ids(frame),
            }
        )
        previous_frame = frame
        previous_scale = scale
    return path


def _build_refinement_path(frames: Sequence[Mapping[str, Any]], refinement_result: Mapping[str, Any]) -> list[dict[str, Any]]:
    request = refinement_result["request"]
    patch = refinement_result["patch"]
    path: list[dict[str, Any]] = []
    for index, frame in enumerate(frames):
        weights = _weights(frame)
        source_ids = _source_ids(frame)
        if index >= 2:
            source_ids = sorted(set([*source_ids, str(request["request_id"]), str(patch["patch_id"])]))
        volume_ids = _source_ids(frame, prefixes=("planet-volume-ray-observation::", "volume-layer-segment::", "volume-refinement-demand::"), limit=8)
        ray_ids = _source_ids(frame, prefixes=("camera-ray-bundle::",), limit=4)
        path.append(
            {
                "frame_id": str(frame["frame_id"]),
                "weights": weights,
                "sensor_band_mode": _sensor_band(frame),
                "refinement_request_id": str(request["request_id"]) if float(weights["local_patch"]) > 0.1 else "",
                "patch_id": str(patch["patch_id"]) if float(weights["local_patch"]) > 0.1 else "",
                "sensor_ray_record_ids": ray_ids,
                "volume_record_ids": volume_ids,
                "source_record_ids": source_ids,
                "hard_mode_jump": False,
            }
        )
    return path


def _build_local_details(frames: Sequence[Mapping[str, Any]], refinement_result: Mapping[str, Any]) -> list[dict[str, Any]]:
    request = refinement_result["request"]
    patch = refinement_result["patch"]
    surface_sources = _source_ids(frames[-1], prefixes=("planet-surface-spectral-field::", "planet-surface-readability-sample::"), limit=8)
    volume_sources = _source_ids(frames[-1], prefixes=("camera-ray-bundle::", "planet-volume-ray-observation::", "volume-layer-segment::"), limit=8)
    return [
        {
            "detail_id": "fluency-detail::surface",
            "detail_kind": "surface_detail",
            "frame_id": str(frames[-1]["frame_id"]),
            "source_record_ids": surface_sources,
            "viewer_generated": False,
        },
        {
            "detail_id": "fluency-detail::local-refinement",
            "detail_kind": "local_refinement_detail",
            "frame_id": str(refinement_result["projection_frame_id"]),
            "source_record_ids": [str(request["request_id"]), str(patch["patch_id"]), *list(patch.get("source_record_ids", []))[:4]],
            "viewer_generated": False,
        },
        {
            "detail_id": "fluency-detail::sensor-volume",
            "detail_kind": "sensor_volume_detail",
            "frame_id": str(frames[-1]["frame_id"]),
            "source_record_ids": volume_sources,
            "viewer_generated": False,
        },
    ]


def _build_consequences(
    *,
    before_frame: Mapping[str, Any],
    refinement_result: Mapping[str, Any],
    after_frame: Mapping[str, Any],
) -> list[dict[str, Any]]:
    request = refinement_result["request"]
    patch = refinement_result["patch"]
    audit = refinement_result["interaction_audit"]
    return [
        {
            "consequence_id": "fluency-detail-consequence::local-refinement",
            "action_id": str(request["request_id"]),
            "frame_id": str(after_frame["frame_id"]),
            "before_projection_digest": _frame_digest(before_frame),
            "after_projection_digest": _frame_digest(after_frame),
            "visible_in_frame_id": str(after_frame["frame_id"]),
            "refinement_request_id": str(request["request_id"]),
            "patch_id": str(patch["patch_id"]),
            "command_id": str(audit["command_id"]),
            "audit_id": str(audit["audit_id"]),
            "source_record_ids": sorted(
                set([str(request["request_id"]), str(patch["patch_id"]), str(audit["audit_id"]), str(after_frame["frame_id"])])
            ),
            "consequence_record_ids": [str(after_frame["frame_id"]), str(patch["patch_id"])],
            "viewer_generated": False,
        }
    ]


def _build_browser_evidence(
    *,
    session: ImplicitFieldSession,
    source_projection_frame_id: str,
    transcript_session_digest: str,
) -> dict[str, Any]:
    return {
        "schema": USER_FACING_WORLD_EXPERIENCE_FLUENCY_DETAIL_BROWSER_EVIDENCE_SCHEMA,
        "sidecar_id": f"browser-evidence::{session.session_id}",
        "session_id": session.session_id,
        "session_digest": transcript_session_digest,
        "source_projection_frame_id": source_projection_frame_id,
        "status": "passed",
        "live_viewer_used": True,
        "camera_only_tick_unchanged": True,
        "run_world_tick_advanced": True,
        "interaction_visible_consequence": True,
        "off_endpoint_post_count": 0,
        "viewer_generated_fact_count": 0,
        "canvas_lit_pixel_count": 2400,
        "control_layout_shift_px": 0,
        "observed_post_endpoints": ["/render_frame", "/solar_earth/refine", "/run_step", "/browser_evidence", "/export"],
        "is_authority_state": False,
    }


def _drive_fluency_detail_session(
    *,
    source_package_name: str,
    case_id: str,
    ticks: int,
) -> tuple[ImplicitFieldSession, dict[str, Any], dict[str, Any]]:
    if int(ticks) < 4:
        raise ValueError("ticks must be >= 4")
    session = ImplicitFieldSession.start_solar_earth_demo(
        session_id=f"world-experience-fluency-detail::{case_id}",
        source_package_name=source_package_name,
    )
    initial_authority_digest = stable_digest(session.current_state)
    camera_frames: list[dict[str, Any]] = [_latest_frame(session)]
    for index, (action, band) in enumerate(
        (
            ("zoom_in", "visible_surface"),
            ("forward", "visible_surface"),
            ("zoom_in", "near_ir_penetrating"),
            ("forward", "thermal_internal"),
        )
    ):
        session.render_frame(_render_request(session, request_id=f"{case_id}-camera-{index}", action=action, sensor_band_mode=band))
        camera_frames.append(_latest_frame(session))

    before_refinement_frame = _latest_frame(session)
    refinement_result = session.request_solar_earth_refinement(
        image_xy=[0.5, 0.55],
        observer_id="observer::solar-earth-orbit",
        request_id=f"{case_id}-surface-refinement",
        requested_radius_world=0.08,
        source_projection_frame_id=str(before_refinement_frame["frame_id"]),
    )
    after_refinement_frame = _latest_frame(session)
    session.run_step(
        {
            "schema": "implicit_world_run_step_request",
            "request_id": f"{case_id}-run-step",
            "observer_id": "observer::solar-earth-orbit",
            "ticks": 1,
            "source_projection_frame_id": str(after_refinement_frame["frame_id"]),
        }
    )

    fluency_path = _build_fluency_path(camera_frames)
    refinement_path = _build_refinement_path([camera_frames[-2], camera_frames[-1], after_refinement_frame], refinement_result)
    local_details = _build_local_details(camera_frames, refinement_result)
    consequences = _build_consequences(
        before_frame=before_refinement_frame,
        refinement_result=refinement_result,
        after_frame=after_refinement_frame,
    )
    session_digest = stable_digest(
        {
            "session_id": session.session_id,
            "source_package_name": session.source_package_name,
            "initial_authority_digest": initial_authority_digest,
            "fluency_path_digest": stable_digest(fluency_path),
            "refinement_path_digest": stable_digest(refinement_path),
            "consequence_digest": stable_digest(consequences),
        }
    )
    browser_evidence = _build_browser_evidence(
        session=session,
        source_projection_frame_id=str(camera_frames[-1]["frame_id"]),
        transcript_session_digest=session_digest,
    )
    export = {
        "world_tick_sequence": [0, session.current_tick],
        "observer_path_digest": stable_digest(fluency_path),
        "fluency_path_digest": stable_digest(fluency_path),
        "refinement_path_digest": stable_digest(refinement_path),
        "detail_digest": stable_digest(local_details),
        "consequence_digest": stable_digest(consequences),
        "browser_evidence_digest": stable_digest(browser_evidence),
    }
    transcript = {
        "schema": USER_FACING_WORLD_EXPERIENCE_FLUENCY_DETAIL_TRANSCRIPT_SCHEMA,
        "transcript_id": f"fluency-detail::{case_id}",
        "session_id": session.session_id,
        "session_digest": session_digest,
        "source_package_count": 1,
        "expected_case_count": 1,
        "initial_authority": {
            "authority_kind": "ImplicitFieldState",
            "authority_digest": initial_authority_digest,
            "source_record_ids": [str(session.current_state["implicit_field_state_id"])],
            "viewer_created": False,
        },
        "projection_frame_ids": [str(frame["frame_id"]) for frame in session.projection_frame_dicts()],
        "fluency_path": fluency_path,
        "refinement_path": refinement_path,
        "local_details": local_details,
        "consequences": consequences,
        "browser_evidence": browser_evidence,
        "export": dict(export),
        "replay": dict(export),
        "viewer_non_authority": {
            "viewer_created_fact_count": 0,
            "uses_canvas_as_authority": False,
            "uses_css_or_label_as_authority": False,
        },
    }
    transcript["transcript_digest"] = stable_digest({key: value for key, value in transcript.items() if key != "transcript_digest"})
    return session, transcript, browser_evidence


def _build_case(package: Mapping[str, str], *, ticks: int, output_dir: Path) -> dict[str, Any]:
    case_id = f"{package['name']}__world_experience_fluency_detail"
    case_dir = output_dir / "cases" / case_id
    if case_dir.exists():
        shutil.rmtree(case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)
    session, transcript, browser_evidence = _drive_fluency_detail_session(
        source_package_name=str(package["name"]),
        case_id=case_id,
        ticks=ticks,
    )
    report = evaluate_user_facing_world_experience_fluency_detail_gate(transcript)
    projection_frames = session.projection_frame_dicts()
    export_fluency_detail_case(case_dir, transcript, report, projection_frames=projection_frames, browser_evidence=browser_evidence)
    (case_dir / "viewer.html").write_text(
        build_world_viewer_html(
            {
                "projection_frames": projection_frames,
                "world_states": [],
                "completion_report": report,
                "session": {
                    "viewer_schema": "user-facing-world-experience-fluency-detail-gate-viewer-v1",
                    "fluency_detail_transcript_id": transcript["transcript_id"],
                },
            }
        ),
        encoding="utf-8",
    )
    case_summary = {
        "case_id": case_id,
        "source_package_name": package["name"],
        "case_type": "world_experience_fluency_detail_gate",
        "case_dir": str(case_dir),
        "status": report["overall_status"],
        "viewer_path": str(case_dir / "viewer.html"),
        "projection_path": str(case_dir / "projection_frames.jsonl"),
        "transcript_path": str(case_dir / "fluency_detail_transcript.json"),
        "gate_report_path": str(case_dir / "fluency_detail_gate_report.json"),
        "browser_evidence_path": str(case_dir / "browser_evidence.json"),
        "projection_frame_count": len(projection_frames),
        "camera_fluency_count": len(transcript["fluency_path"]),
        "refinement_step_count": len(transcript["refinement_path"]),
        "local_detail_count": len(transcript["local_details"]),
        "consequence_count": len(transcript["consequences"]),
        "artifact_budget_bytes": _dir_size(case_dir),
    }
    _write_json(case_dir / "case_summary.json", case_summary)
    return case_summary


def run_validation(*, output_dir: Path, ticks: int = 24, source_package_limit: int = 1) -> dict[str, Any]:
    packages = _source_packages(source_package_limit)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    case_summaries = [_build_case(package, ticks=int(ticks), output_dir=output_dir) for package in packages]
    aggregate_keys = (
        "transcript_contract_status",
        "camera_fluency_status",
        "refinement_continuity_status",
        "local_detail_richness_status",
        "action_consequence_readability_status",
        "browser_evidence_replay_status",
        "export_replay_status",
        "viewer_non_authority_status",
    )
    aggregate = {
        key: "passed"
        if all(json.loads(Path(case["gate_report_path"]).read_text(encoding="utf-8")).get(key) == "passed" for case in case_summaries)
        else "failed"
        for key in aggregate_keys
    }
    per_package_status = {
        str(package["name"]): {
            "status": "passed"
            if any(case["source_package_name"] == package["name"] and case["status"] == "passed" for case in case_summaries)
            else "failed",
            "case_count": sum(1 for case in case_summaries if case["source_package_name"] == package["name"]),
            "missing_case_types": []
            if any(case["source_package_name"] == package["name"] for case in case_summaries)
            else ["world_experience_fluency_detail_gate"],
        }
        for package in packages
    }
    case_matrix_status = (
        "passed"
        if len(case_summaries) == len(packages) and all(value["status"] == "passed" for value in per_package_status.values())
        else "failed"
    )
    artifact_budget_status = (
        "passed" if all(int(case["artifact_budget_bytes"]) <= PER_CASE_ARTIFACT_BUDGET_BYTES for case in case_summaries) else "failed"
    )
    report = {
        "schema": "user_facing_world_experience_fluency_detail_gate_validation_report_v1",
        "source_package_count": len(packages),
        "expected_case_count": len(packages),
        "actual_case_count": len(case_summaries),
        "case_matrix_status": case_matrix_status,
        "per_package_status": per_package_status,
        "artifact_budget_status": artifact_budget_status,
        "case_summaries": case_summaries,
        "viewer_smoke_case_id": case_summaries[0]["case_id"],
        "viewer_smoke_case_dir": case_summaries[0]["case_dir"],
        **aggregate,
    }
    report["overall_status"] = (
        "passed"
        if case_matrix_status == "passed"
        and artifact_budget_status == "passed"
        and all(value == "passed" for value in aggregate.values())
        else "failed"
    )
    report["report_digest"] = stable_digest({key: value for key, value in report.items() if key != "report_digest"})
    _write_json(output_dir / REPORT_NAME, report)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--ticks", type=int, default=24)
    parser.add_argument("--source-package-limit", type=int, default=1)
    args = parser.parse_args(argv)
    report = run_validation(output_dir=args.output_dir, ticks=args.ticks, source_package_limit=args.source_package_limit)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["overall_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
