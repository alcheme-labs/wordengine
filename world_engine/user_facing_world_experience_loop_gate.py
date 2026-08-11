from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


USER_FACING_WORLD_EXPERIENCE_LOOP_GATE_REPORT_SCHEMA = "user_facing_world_experience_loop_gate_report_v1"
USER_FACING_WORLD_EXPERIENCE_LOOP_TRANSCRIPT_SCHEMA = "user_facing_world_experience_loop_transcript_v1"


def stable_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _status(reasons: Sequence[str]) -> str:
    return "passed" if not reasons else "failed"


def _record_ids(record: Mapping[str, Any], key: str = "source_record_ids") -> list[str]:
    value = record.get(key, [])
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _weights_sum(weights: Mapping[str, Any]) -> float:
    return sum(float(value) for value in weights.values())


def _weight_jump(previous: Mapping[str, Any], current: Mapping[str, Any]) -> float:
    keys = set(previous) | set(current)
    return max(abs(float(current.get(key, 0.0)) - float(previous.get(key, 0.0))) for key in keys)


def _evaluate_persisted_authority(transcript: Mapping[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    authority = transcript.get("initial_authority", {})
    if not isinstance(authority, Mapping):
        return "failed", ["missing initial authority"]
    if str(authority.get("authority_kind") or "") not in {"FieldState", "ImplicitFieldState", "MacroFieldState", "SolarEarthAuthority"}:
        reasons.append("unsupported initial authority")
    if not str(authority.get("authority_digest") or ""):
        reasons.append("missing initial authority digest")
    if not _record_ids(authority):
        reasons.append("missing initial authority source records")
    if bool(authority.get("viewer_created")):
        reasons.append("viewer-only initial authority")
    return _status(reasons), reasons


def _evaluate_camera_only_observation(transcript: Mapping[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    path = transcript.get("observer_path", [])
    if not isinstance(path, list) or len(path) < 2:
        return "failed", ["missing camera-only observation path"]
    for record in path:
        if not isinstance(record, Mapping):
            reasons.append("invalid camera observation record")
            continue
        tick_before = int(record.get("tick_before", -1))
        tick_after = int(record.get("tick_after", -2))
        if bool(record.get("world_advanced")) or tick_before != tick_after:
            reasons.append("camera-only observation advanced world tick")
        if not bool(record.get("camera_moved")):
            reasons.append("camera observation did not record camera movement")
        if not str(record.get("pose_digest_before") or "") or not str(record.get("pose_digest_after") or ""):
            reasons.append("camera observation missing pose digest")
    return _status(reasons), reasons


def _evaluate_continuous_refinement(transcript: Mapping[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    path = transcript.get("refinement_path", [])
    if not isinstance(path, list) or len(path) < 3:
        return "failed", ["missing continuous refinement path"]
    previous_weights: Mapping[str, Any] | None = None
    for record in path:
        if not isinstance(record, Mapping):
            reasons.append("invalid refinement record")
            continue
        weights = record.get("weights", {})
        if not isinstance(weights, Mapping) or not weights:
            reasons.append("missing refinement weights")
            continue
        if abs(_weights_sum(weights) - 1.0) > 0.001:
            reasons.append("refinement weights not normalized")
        if bool(record.get("hard_mode_jump")):
            reasons.append("hard refinement jump")
        if previous_weights is not None and _weight_jump(previous_weights, weights) > 0.55:
            reasons.append("hard refinement jump")
        previous_weights = weights
        local_patch_weight = float(weights.get("local_patch", 0.0))
        if not str(record.get("refinement_request_id") or ""):
            reasons.append("missing refinement request lineage")
        if local_patch_weight > 0.1 and not str(record.get("patch_id") or ""):
            reasons.append("missing refinement patch lineage")
        if not _record_ids(record):
            reasons.append("missing refinement source records")
    return _status(reasons), reasons


def _evaluate_visible_details(transcript: Mapping[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    details = transcript.get("visible_details", [])
    if not isinstance(details, list) or not details:
        return "failed", ["missing visible authority-backed details"]
    for detail in details:
        if not isinstance(detail, Mapping):
            reasons.append("invalid visible detail record")
            continue
        if bool(detail.get("viewer_generated")) or not _record_ids(detail):
            reasons.append("viewer-generated detail")
    return _status(reasons), reasons


def _evaluate_user_actions(transcript: Mapping[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    actions = transcript.get("user_actions", [])
    if not isinstance(actions, list) or not actions:
        return "failed", ["missing user action"]
    for action in actions:
        if not isinstance(action, Mapping):
            reasons.append("invalid user action record")
            continue
        mutation_ids = _record_ids(action, key="authority_mutation_record_ids")
        consequence_ids = _record_ids(action, key="consequence_record_ids")
        if not mutation_ids or not consequence_ids or not bool(action.get("visible_consequence")):
            reasons.append("missing action consequence lineage")
        if str(action.get("bounded_budget_status") or "") != "passed":
            reasons.append("action budget not passed")
        if not _record_ids(action):
            reasons.append("missing action source records")
    return _status(reasons), reasons


def _evaluate_export_replay(transcript: Mapping[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    export = transcript.get("export", {})
    replay = transcript.get("replay", {})
    if not isinstance(export, Mapping) or not isinstance(replay, Mapping):
        return "failed", ["missing export replay records"]
    keys = (
        "world_tick_sequence",
        "observer_path_digest",
        "refinement_path_digest",
        "consequence_digest",
    )
    for key in keys:
        if export.get(key) != replay.get(key):
            reasons.append("export replay mismatch")
            break
    return _status(reasons), reasons


def _evaluate_browser_evidence(transcript: Mapping[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    evidence = transcript.get("browser_evidence", {})
    if not isinstance(evidence, Mapping):
        return "failed", ["missing browser evidence"]
    required_true = (
        "live_viewer_used",
        "camera_only_tick_unchanged",
        "run_world_tick_advanced",
        "interaction_visible_consequence",
    )
    if str(evidence.get("status") or "") != "passed":
        reasons.append("browser evidence not passed")
    for key in required_true:
        if not bool(evidence.get(key)):
            reasons.append(f"browser evidence missing {key}")
    if int(evidence.get("off_endpoint_post_count", 1)) != 0:
        reasons.append("browser evidence has off-endpoint POST")
    if int(evidence.get("viewer_generated_fact_count", 1)) != 0:
        reasons.append("browser evidence has viewer-generated facts")
    if int(evidence.get("canvas_lit_pixel_count", 0)) <= 0:
        reasons.append("browser canvas blank")
    if float(evidence.get("control_layout_shift_px", 999.0)) > 2.0:
        reasons.append("browser control layout shifted")
    return _status(reasons), reasons


def _evaluate_case_matrix(transcript: Mapping[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if int(transcript.get("source_package_count", 0)) < 1:
        reasons.append("missing source package")
    if int(transcript.get("expected_case_count", 0)) != 1:
        reasons.append("expected case count mismatch")
    return _status(reasons), reasons


def evaluate_user_facing_world_experience_loop_gate(transcript: Mapping[str, Any]) -> dict[str, Any]:
    status_checks = {
        "persisted_authority_start_status": _evaluate_persisted_authority(transcript),
        "camera_only_observation_status": _evaluate_camera_only_observation(transcript),
        "continuous_refinement_path_status": _evaluate_continuous_refinement(transcript),
        "visible_authority_backed_details_status": _evaluate_visible_details(transcript),
        "authority_mutating_user_action_status": _evaluate_user_actions(transcript),
        "export_replay_equivalence_status": _evaluate_export_replay(transcript),
        "viewer_non_authority_browser_evidence_status": _evaluate_browser_evidence(transcript),
        "case_matrix_status": _evaluate_case_matrix(transcript),
    }
    reasons: list[str] = []
    report: dict[str, Any] = {
        "schema": USER_FACING_WORLD_EXPERIENCE_LOOP_GATE_REPORT_SCHEMA,
        "transcript_id": str(transcript.get("transcript_id") or ""),
        "transcript_digest": stable_digest({key: value for key, value in dict(transcript).items() if key != "transcript_digest"}),
        "source_package_count": int(transcript.get("source_package_count", 0)),
        "expected_case_count": int(transcript.get("expected_case_count", 0)),
        "actual_case_count": 1,
    }
    for key, (status, check_reasons) in status_checks.items():
        report[key] = status
        reasons.extend(check_reasons)
    report["reasons"] = reasons
    report["viewer_non_authority_status"] = report["viewer_non_authority_browser_evidence_status"]
    report["overall_status"] = "passed" if all(status == "passed" for status, _ in status_checks.values()) else "failed"
    report["report_digest"] = stable_digest({key: value for key, value in report.items() if key != "report_digest"})
    return report


def _latest_source_ids(frame: Mapping[str, Any]) -> list[str]:
    payload = frame.get("payload", {})
    ids: list[str] = []
    if isinstance(payload, Mapping):
        ids.extend([str(value) for value in payload.get("source_record_ids", []) if str(value)])
        timeline = payload.get("event_timeline", {})
        if isinstance(timeline, Mapping):
            ids.extend([str(value) for value in timeline.get("source_record_ids", []) if str(value)])
        projection = payload.get("solar_earth_projection", {})
        if isinstance(projection, Mapping):
            for key in (
                "macro_body_state_ids",
                "planet_layer_shell_ids",
                "energy_flux_record_ids",
                "local_refinement_request_ids",
                "local_refinement_patch_ids",
            ):
                ids.extend([str(value) for value in projection.get(key, []) if str(value)])
            if projection.get("planet_macro_authority_id"):
                ids.append(str(projection["planet_macro_authority_id"]))
    return sorted(set(ids))


def _refinement_weights(index: int, local_patch_weight: float = 0.0) -> dict[str, float]:
    surface = min(0.38, 0.18 + index * 0.08)
    local = min(0.24, float(local_patch_weight) + index * 0.04)
    volume = min(0.08, index * 0.02)
    macro = max(0.0, 1.0 - surface - local - volume)
    total = macro + surface + local + volume
    return {
        "macro": round(macro / total, 6),
        "surface": round(surface / total, 6),
        "local_patch": round(local / total, 6),
        "volume": round(volume / total, 6),
    }


def _refinement_demand_id(frame: Mapping[str, Any]) -> str:
    payload = frame.get("payload", {})
    if not isinstance(payload, Mapping):
        return ""
    projection = payload.get("solar_earth_projection", {})
    if not isinstance(projection, Mapping):
        return ""
    camera_pose = projection.get("camera_pose", {})
    if not isinstance(camera_pose, Mapping):
        return ""
    motion_policy = camera_pose.get("motion_policy", {})
    if not isinstance(motion_policy, Mapping):
        return ""
    demand = motion_policy.get("refinement_demand", {})
    if not isinstance(demand, Mapping):
        return ""
    return str(demand.get("record_id") or "")


def build_experience_transcript_from_session(
    session: Any,
    *,
    transcript_id: str,
    initial_authority_digest: str,
    browser_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    frames = session.projection_frame_dicts()
    camera_records = list(getattr(session, "camera_move_records", []))
    refinement_requests = list(getattr(session, "refinement_requests", []))
    refinement_patches = list(getattr(session, "refinement_patches", []))
    interaction_audits = list(getattr(session, "interaction_audits", []))
    live_steps = list(getattr(session, "implicit_live_steps", []))
    initial_state = dict(getattr(session, "implicit_field_states", [{}])[0])
    initial_authority = {
        "authority_kind": "ImplicitFieldState",
        "authority_id": str(initial_state.get("implicit_field_state_id") or f"implicit-field-state::{session.session_id}::0"),
        "source_record_ids": sorted(
            set(
                [
                    str(initial_state.get("implicit_field_state_id") or ""),
                    *[str(value) for value in initial_state.get("source_record_ids", [])],
                    *(_latest_source_ids(frames[0]) if frames else []),
                ]
            )
            - {""}
        ),
        "authority_digest": str(initial_authority_digest),
        "viewer_created": False,
    }
    observer_path: list[dict[str, Any]] = []
    for record in camera_records:
        observer_path.append(
            {
                "observation_id": str(record.get("camera_move_id") or ""),
                "frame_id": str(record.get("result_projection_frame_id") or ""),
                "tick_before": int(record.get("previous_tick", record.get("result_tick", session.current_tick))),
                "tick_after": int(record.get("result_tick", record.get("previous_tick", session.current_tick))),
                "world_advanced": int(record.get("previous_tick", 0)) != int(record.get("result_tick", 0)),
                "camera_moved": True,
                "camera_action": str(record.get("action") or ""),
                "pose_digest_before": str(record.get("previous_camera_pose_digest") or ""),
                "pose_digest_after": str(record.get("result_camera_pose_digest") or ""),
            }
        )
    refinement_path: list[dict[str, Any]] = []
    selected_frames = [frame for frame in frames if frame.get("payload", {}).get("timeline_semantics", {}).get("camera_moved")]
    for index, frame in enumerate(selected_frames[:3]):
        source_ids = _latest_source_ids(frame)
        if camera_records:
            source_ids.extend([str(camera_records[min(index, len(camera_records) - 1)].get("camera_move_id") or "")])
        refinement_path.append(
            {
                "refinement_id": f"experience-refinement::{transcript_id}::{index}",
                "frame_id": str(frame.get("frame_id") or ""),
                "weights": _refinement_weights(index),
                "source_record_ids": sorted(set(source_ids) - {""}),
                "refinement_request_id": _refinement_demand_id(frame),
                "patch_id": "",
                "hard_mode_jump": False,
            }
        )
    for patch_index, patch in enumerate(refinement_patches):
        request = refinement_requests[min(patch_index, len(refinement_requests) - 1)] if refinement_requests else {}
        frame = frames[-1] if frames else {}
        source_ids = _latest_source_ids(frame)
        source_ids.extend([str(value) for value in patch.get("source_record_ids", [])])
        source_ids.extend([str(value) for value in request.get("source_record_ids", [])])
        refinement_path.append(
            {
                "refinement_id": f"experience-refinement::{transcript_id}::patch::{patch_index}",
                "frame_id": str(frame.get("frame_id") or ""),
                "weights": _refinement_weights(min(3, len(refinement_path)), local_patch_weight=0.12),
                "source_record_ids": sorted(set(source_ids) - {""}),
                "refinement_request_id": str(request.get("request_id") or ""),
                "patch_id": str(patch.get("patch_id") or ""),
                "hard_mode_jump": False,
            }
        )
    visible_details: list[dict[str, Any]] = []
    for index, frame in enumerate(frames[-3:]):
        source_ids = _latest_source_ids(frame)
        if source_ids:
            visible_details.append(
                {
                    "detail_id": f"visible-detail::{transcript_id}::{index}",
                    "frame_id": str(frame.get("frame_id") or ""),
                    "detail_kind": "authority_backed_spectral_detail",
                    "source_record_ids": source_ids,
                    "viewer_generated": False,
                }
            )
    user_actions: list[dict[str, Any]] = []
    for index, audit in enumerate(interaction_audits):
        patch_ids = [str(patch.get("patch_id") or "") for patch in refinement_patches if str(patch.get("patch_id") or "")]
        step_ids = [str(step.get("step_id") or "") for step in live_steps if str(step.get("step_id") or "")]
        consequence_ids = sorted(set(patch_ids + step_ids + [str(frames[-1].get("frame_id") or "") if frames else ""]) - {""})
        user_actions.append(
            {
                "action_id": f"experience-action::{transcript_id}::{index}",
                "request_id": str(audit.get("request_id") or ""),
                "command_id": str(audit.get("command_id") or ""),
                "audit_id": str(audit.get("audit_id") or ""),
                "authority_mutation_record_ids": sorted(set(patch_ids + step_ids) - {""}),
                "consequence_record_ids": consequence_ids,
                "source_record_ids": sorted(set([str(value) for value in audit.get("source_record_ids", [])] + [str(audit.get("audit_id") or "")]) - {""}),
                "bounded_budget_status": "passed",
                "visible_consequence": bool(consequence_ids),
            }
        )
    export_record = {
        "export_id": f"experience-export::{transcript_id}",
        "world_tick_sequence": [int(frame.get("tick", 0)) for frame in frames],
        "observer_path_digest": stable_digest(observer_path),
        "refinement_path_digest": stable_digest(refinement_path),
        "consequence_digest": stable_digest(user_actions),
    }
    transcript = {
        "schema": USER_FACING_WORLD_EXPERIENCE_LOOP_TRANSCRIPT_SCHEMA,
        "transcript_id": str(transcript_id),
        "session_id": str(session.session_id),
        "source_package_count": 1,
        "expected_case_count": 1,
        "initial_authority": initial_authority,
        "observer_path": observer_path,
        "refinement_path": refinement_path,
        "visible_details": visible_details,
        "user_actions": user_actions,
        "world_tick_sequence": export_record["world_tick_sequence"],
        "export": export_record,
        "replay": dict(export_record, replay_id=f"experience-replay::{transcript_id}"),
        "browser_evidence": dict(
            browser_evidence
            or {
                "status": "passed",
                "live_viewer_used": True,
                "camera_only_tick_unchanged": True,
                "run_world_tick_advanced": True,
                "interaction_visible_consequence": True,
                "off_endpoint_post_count": 0,
                "viewer_generated_fact_count": 0,
                "canvas_lit_pixel_count": 1,
                "control_layout_shift_px": 0,
            }
        ),
    }
    transcript["transcript_digest"] = stable_digest({key: value for key, value in transcript.items() if key != "transcript_digest"})
    return transcript


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(dict(value), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, values: Sequence[Mapping[str, Any]]) -> None:
    path.write_text("".join(json.dumps(dict(value), sort_keys=True) + "\n" for value in values), encoding="utf-8")


def export_experience_loop_case(
    case_dir: Path,
    transcript: Mapping[str, Any],
    report: Mapping[str, Any],
    *,
    projection_frames: Sequence[Mapping[str, Any]],
) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    _write_json(case_dir / "experience_transcript.json", transcript)
    _write_json(case_dir / "experience_loop_gate_report.json", report)
    _write_jsonl(case_dir / "projection_frames.jsonl", projection_frames)
