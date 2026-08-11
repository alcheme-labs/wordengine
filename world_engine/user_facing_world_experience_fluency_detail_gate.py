from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


USER_FACING_WORLD_EXPERIENCE_FLUENCY_DETAIL_TRANSCRIPT_SCHEMA = "user_facing_world_experience_fluency_detail_transcript_v1"
USER_FACING_WORLD_EXPERIENCE_FLUENCY_DETAIL_BROWSER_EVIDENCE_SCHEMA = "user_facing_world_experience_fluency_detail_browser_evidence_v1"
USER_FACING_WORLD_EXPERIENCE_FLUENCY_DETAIL_REPORT_SCHEMA = "user_facing_world_experience_fluency_detail_report_v1"

MAX_CAMERA_POSE_STEP_WORLD = 0.75
MAX_APPARENT_SCALE_DELTA = 0.35
MAX_REFINEMENT_WEIGHT_DELTA = 0.45
LOCAL_PATCH_LINEAGE_THRESHOLD = 0.1
VOLUME_LINEAGE_THRESHOLD = 0.001


def stable_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _status(reasons: Sequence[str]) -> str:
    return "passed" if not reasons else "failed"


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _record_ids(record: Mapping[str, Any], key: str = "source_record_ids") -> list[str]:
    return [str(value) for value in _as_list(record.get(key)) if str(value)]


def _weights_sum(weights: Mapping[str, Any]) -> float:
    return sum(float(value) for value in weights.values())


def _weight_delta(previous: Mapping[str, Any], current: Mapping[str, Any]) -> float:
    keys = set(previous) | set(current)
    return max((abs(float(current.get(key, 0.0)) - float(previous.get(key, 0.0))) for key in keys), default=0.0)


def _evaluate_camera_fluency(transcript: Mapping[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    path = _as_list(transcript.get("fluency_path"))
    if len(path) < 5:
        return "failed", ["missing camera fluency path"]
    for record in path:
        record = _as_mapping(record)
        if bool(record.get("world_advanced")) or int(record.get("tick_before", -1)) != int(record.get("tick_after", -2)):
            reasons.append("camera-only observation advanced world tick")
        if bool(record.get("hard_mode_jump")):
            reasons.append("hard camera mode jump")
        if float(record.get("pose_step_world", 0.0)) > MAX_CAMERA_POSE_STEP_WORLD:
            reasons.append("hard camera pose jump")
        if float(record.get("apparent_scale_delta", 0.0)) > MAX_APPARENT_SCALE_DELTA:
            reasons.append("hard apparent scale jump")
        if not _record_ids(record):
            reasons.append("missing camera fluency source records")
    return _status(reasons), reasons


def _evaluate_transcript_contract(transcript: Mapping[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if transcript.get("schema") != USER_FACING_WORLD_EXPERIENCE_FLUENCY_DETAIL_TRANSCRIPT_SCHEMA:
        reasons.append("transcript schema mismatch")
    transcript_digest = str(transcript.get("transcript_digest") or "")
    if transcript_digest:
        expected_digest = stable_digest({key: value for key, value in dict(transcript).items() if key != "transcript_digest"})
        if transcript_digest != expected_digest:
            reasons.append("transcript digest mismatch")
    authority = _as_mapping(transcript.get("initial_authority"))
    if not str(authority.get("authority_kind") or "") or not str(authority.get("authority_digest") or ""):
        reasons.append("missing initial authority")
    if bool(authority.get("viewer_created")):
        reasons.append("viewer-created initial authority")
    if not _record_ids(authority):
        reasons.append("missing initial authority source records")
    return _status(reasons), reasons


def _evaluate_refinement_continuity(transcript: Mapping[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    path = _as_list(transcript.get("refinement_path"))
    if len(path) < 3:
        return "failed", ["missing refinement continuity path"]
    previous_weights: Mapping[str, Any] | None = None
    for record in path:
        record = _as_mapping(record)
        weights = _as_mapping(record.get("weights"))
        if not weights:
            reasons.append("missing refinement weights")
            continue
        if abs(_weights_sum(weights) - 1.0) > 0.001:
            reasons.append("refinement weights not normalized")
        if previous_weights is not None and _weight_delta(previous_weights, weights) > MAX_REFINEMENT_WEIGHT_DELTA:
            reasons.append("hard refinement weight jump")
        previous_weights = weights
        if bool(record.get("hard_mode_jump")):
            reasons.append("hard refinement mode jump")
        local_patch_weight = float(weights.get("local_patch", 0.0))
        if local_patch_weight > LOCAL_PATCH_LINEAGE_THRESHOLD and (
            not str(record.get("refinement_request_id") or "") or not str(record.get("patch_id") or "")
        ):
            reasons.append("missing local refinement lineage")
        volume_weight = float(weights.get("volume", 0.0))
        sensor_band = str(record.get("sensor_band_mode") or "")
        if volume_weight > VOLUME_LINEAGE_THRESHOLD or sensor_band in {"near_ir_penetrating", "thermal_internal"}:
            if not _as_list(record.get("sensor_ray_record_ids")) or not _as_list(record.get("volume_record_ids")):
                reasons.append("missing volume sensor lineage")
        if not _record_ids(record):
            reasons.append("missing refinement source records")
    return _status(reasons), reasons


def _evaluate_detail_richness(transcript: Mapping[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    details = _as_list(transcript.get("local_details"))
    if not details:
        return "failed", ["missing local details"]
    kinds = {str(_as_mapping(detail).get("detail_kind") or "") for detail in details}
    required = {"surface_detail", "local_refinement_detail", "sensor_volume_detail"}
    missing = sorted(required - kinds)
    if missing:
        reasons.append("missing local detail kinds")
    for detail in details:
        detail = _as_mapping(detail)
        if bool(detail.get("viewer_generated")) or not _record_ids(detail):
            reasons.append("viewer-generated detail")
    return _status(reasons), reasons


def _evaluate_action_consequence(transcript: Mapping[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    consequences = _as_list(transcript.get("consequences"))
    if not consequences:
        return "failed", ["missing action consequence"]
    for consequence in consequences:
        consequence = _as_mapping(consequence)
        changed = str(consequence.get("before_projection_digest") or "") != str(consequence.get("after_projection_digest") or "")
        lineage = bool(str(consequence.get("command_id") or "") and str(consequence.get("audit_id") or "")) or bool(
            str(consequence.get("refinement_request_id") or "") and str(consequence.get("patch_id") or "")
        )
        if not changed or not str(consequence.get("visible_in_frame_id") or ""):
            reasons.append("missing visible action consequence")
        if not lineage or not _record_ids(consequence) or not _record_ids(consequence, key="consequence_record_ids"):
            reasons.append("missing action consequence lineage")
        if bool(consequence.get("viewer_generated")):
            reasons.append("viewer-generated consequence")
    return _status(reasons), reasons


def _evaluate_browser_evidence(transcript: Mapping[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    evidence = transcript.get("browser_evidence")
    if not isinstance(evidence, Mapping):
        return "failed", ["missing browser evidence sidecar"]
    if evidence.get("schema") != USER_FACING_WORLD_EXPERIENCE_FLUENCY_DETAIL_BROWSER_EVIDENCE_SCHEMA:
        reasons.append("browser evidence schema mismatch")
    if evidence.get("is_authority_state") is not False:
        reasons.append("browser evidence cannot be authority")
    if str(evidence.get("session_id") or "") != str(transcript.get("session_id") or ""):
        reasons.append("browser evidence session mismatch")
    if str(evidence.get("session_digest") or "") != str(transcript.get("session_digest") or ""):
        reasons.append("browser evidence session digest mismatch")
    required_true = ("live_viewer_used", "camera_only_tick_unchanged", "run_world_tick_advanced", "interaction_visible_consequence")
    for key in required_true:
        if not bool(evidence.get(key)):
            reasons.append(f"browser evidence missing {key}")
    if str(evidence.get("status") or "") != "passed":
        reasons.append("browser evidence not passed")
    if int(evidence.get("canvas_lit_pixel_count", 0)) <= 0:
        reasons.append("browser canvas blank")
    if float(evidence.get("control_layout_shift_px", 999.0)) > 2.0:
        reasons.append("browser control layout shifted")
    if int(evidence.get("off_endpoint_post_count", 1)) != 0:
        reasons.append("browser evidence has off-endpoint POST")
    if int(evidence.get("viewer_generated_fact_count", 1)) != 0:
        reasons.append("browser evidence has viewer-generated facts")
    if not _as_list(evidence.get("observed_post_endpoints")):
        reasons.append("browser evidence missing observed endpoints")
    fluency_frame_ids = {
        str(_as_mapping(record).get("frame_id") or "")
        for record in _as_list(transcript.get("fluency_path"))
        if str(_as_mapping(record).get("frame_id") or "")
    }
    known_projection_frame_ids = set(fluency_frame_ids)
    known_projection_frame_ids.update(str(value) for value in _as_list(transcript.get("projection_frame_ids")) if str(value))
    known_projection_frame_ids.update(
        str(_as_mapping(record).get("visible_in_frame_id") or "")
        for record in _as_list(transcript.get("consequences"))
        if str(_as_mapping(record).get("visible_in_frame_id") or "")
    )
    if str(evidence.get("source_projection_frame_id") or "") not in known_projection_frame_ids:
        reasons.append("browser evidence source frame not in serialized projection frames")
    expected_digest = _as_mapping(transcript.get("export")).get("browser_evidence_digest")
    if expected_digest and expected_digest != stable_digest(evidence):
        reasons.append("browser evidence digest mismatch")
    return _status(reasons), reasons


def _evaluate_export_replay(transcript: Mapping[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    export = _as_mapping(transcript.get("export"))
    replay = _as_mapping(transcript.get("replay"))
    if not export or not replay:
        return "failed", ["missing export replay records"]
    for key in (
        "world_tick_sequence",
        "observer_path_digest",
        "fluency_path_digest",
        "refinement_path_digest",
        "detail_digest",
        "consequence_digest",
        "browser_evidence_digest",
    ):
        if export.get(key) != replay.get(key):
            reasons.append("export replay mismatch")
            break
    if export.get("fluency_path_digest") != stable_digest(_as_list(transcript.get("fluency_path"))):
        reasons.append("export fluency digest mismatch")
    if export.get("refinement_path_digest") != stable_digest(_as_list(transcript.get("refinement_path"))):
        reasons.append("export refinement digest mismatch")
    if export.get("detail_digest") != stable_digest(_as_list(transcript.get("local_details"))):
        reasons.append("export detail digest mismatch")
    if export.get("consequence_digest") != stable_digest(_as_list(transcript.get("consequences"))):
        reasons.append("export consequence digest mismatch")
    return _status(reasons), reasons


def _evaluate_viewer_non_authority(transcript: Mapping[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    record = _as_mapping(transcript.get("viewer_non_authority"))
    if int(record.get("viewer_created_fact_count", 1)) != 0:
        reasons.append("viewer-created authority")
    if bool(record.get("uses_canvas_as_authority")):
        reasons.append("canvas used as authority")
    if bool(record.get("uses_css_or_label_as_authority")):
        reasons.append("css or label used as authority")
    return _status(reasons), reasons


def evaluate_user_facing_world_experience_fluency_detail_gate(transcript: Mapping[str, Any]) -> dict[str, Any]:
    status_checks = {
        "transcript_contract_status": _evaluate_transcript_contract(transcript),
        "camera_fluency_status": _evaluate_camera_fluency(transcript),
        "refinement_continuity_status": _evaluate_refinement_continuity(transcript),
        "local_detail_richness_status": _evaluate_detail_richness(transcript),
        "action_consequence_readability_status": _evaluate_action_consequence(transcript),
        "browser_evidence_replay_status": _evaluate_browser_evidence(transcript),
        "export_replay_status": _evaluate_export_replay(transcript),
        "viewer_non_authority_status": _evaluate_viewer_non_authority(transcript),
    }
    reasons: list[str] = []
    report: dict[str, Any] = {
        "schema": USER_FACING_WORLD_EXPERIENCE_FLUENCY_DETAIL_REPORT_SCHEMA,
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
    report["overall_status"] = "passed" if all(status == "passed" for status, _ in status_checks.values()) else "failed"
    report["report_digest"] = stable_digest({key: value for key, value in report.items() if key != "report_digest"})
    return report


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(dict(value), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, values: Sequence[Mapping[str, Any]]) -> None:
    path.write_text("".join(json.dumps(dict(value), sort_keys=True) + "\n" for value in values), encoding="utf-8")


def export_fluency_detail_case(
    case_dir: Path,
    transcript: Mapping[str, Any],
    report: Mapping[str, Any],
    *,
    projection_frames: Sequence[Mapping[str, Any]],
    browser_evidence: Mapping[str, Any],
) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    _write_json(case_dir / "fluency_detail_transcript.json", transcript)
    _write_json(case_dir / "fluency_detail_gate_report.json", report)
    _write_json(case_dir / "browser_evidence.json", browser_evidence)
    _write_jsonl(case_dir / "projection_frames.jsonl", projection_frames)
