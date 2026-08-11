#!/usr/bin/env python3
from __future__ import annotations

import argparse
import dataclasses
import ipaddress
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from world_engine.implicit_interaction import canonical_implicit_tick_count  # noqa: E402
from world_engine.implicit_live_session import ImplicitFieldSession  # noqa: E402
from world_engine.user_facing_world_experience_loop_gate import (  # noqa: E402
    build_experience_transcript_from_session,
    evaluate_user_facing_world_experience_loop_gate,
    stable_digest,
)
from world_engine.user_facing_world_experience_fluency_detail_gate import (  # noqa: E402
    MAX_APPARENT_SCALE_DELTA,
    MAX_CAMERA_POSE_STEP_WORLD,
    USER_FACING_WORLD_EXPERIENCE_FLUENCY_DETAIL_BROWSER_EVIDENCE_SCHEMA,
    USER_FACING_WORLD_EXPERIENCE_FLUENCY_DETAIL_TRANSCRIPT_SCHEMA,
    evaluate_user_facing_world_experience_fluency_detail_gate,
)
from scripts.run_user_facing_world_experience_fluency_detail_gate import (  # noqa: E402
    _build_consequences as _build_fluency_detail_consequences,
    _build_fluency_path as _build_fluency_detail_path,
    _build_local_details as _build_fluency_detail_local_details,
    _build_refinement_path as _build_fluency_detail_refinement_path,
    _source_ids as _fluency_detail_source_ids,
)
from world_engine.viewer import build_world_viewer_html  # noqa: E402


MAX_JSON_BODY_BYTES = 64 * 1024
DEFAULT_MAX_SESSION_TICKS = 256
DEFAULT_MAX_FRAME_RECORDS = 512
DEFAULT_MAX_EXPORT_BYTES = 32 * 1024 * 1024
PUBLIC_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@/+~-]{0,127}\Z")


class PublicRequestError(ValueError):
    def __init__(self, status: int, code: str, public_message: str) -> None:
        super().__init__(public_message)
        self.status = status
        self.code = code
        self.public_message = public_message


def _is_loopback_hostname(hostname: str) -> bool:
    normalized = hostname.strip().lower().rstrip(".")
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _hostname_from_host_header(host_header: str) -> str:
    value = host_header.strip()
    if value.startswith("["):
        end = value.find("]")
        return value[1:end] if end > 1 else ""
    if value.count(":") == 1:
        return value.rsplit(":", 1)[0]
    return value


def _validate_public_identifiers(value: Any, *, key: str = "") -> None:
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            _validate_public_identifiers(child_value, key=str(child_key))
        return
    if isinstance(value, list):
        for child in value:
            _validate_public_identifiers(child, key=key[:-1] if key.endswith("s") else key)
        return
    if key.endswith("_id") and value is not None:
        if not isinstance(value, str) or not PUBLIC_IDENTIFIER_PATTERN.fullmatch(value):
            raise PublicRequestError(400, "invalid_identifier", "request contains an invalid identifier")


def _json_bytes(value: Any) -> bytes:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    elif isinstance(value, list):
        value = [_jsonable(item) for item in value]
    elif isinstance(value, dict):
        value = {key: _jsonable(item) for key, item in value.items()}
    return json.dumps(value, sort_keys=True).encode("utf-8")


def _jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if dataclasses.is_dataclass(value):
        return {field.name: _jsonable(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _jsonl_bytes(values: list[dict[str, Any]]) -> bytes:
    return b"".join(json.dumps(value, sort_keys=True).encode("utf-8") + b"\n" for value in values)


def _with_browser_evidence_count(manifest: dict[str, Any], count: int) -> dict[str, Any]:
    return {**manifest, "browser_evidence_count": int(count)}


def _experience_loop_payload(session: ImplicitFieldSession) -> dict[str, Any]:
    initial_state = session.implicit_field_states[0] if session.implicit_field_states else session.current_state
    camera_records = list(getattr(session, "camera_move_records", []))
    initial_tick = int(initial_state.get("tick", 0))
    camera_only_tick_unchanged = bool(camera_records) and all(
        int(record.get("previous_tick", initial_tick)) == int(record.get("result_tick", initial_tick))
        for record in camera_records
    )
    transcript = build_experience_transcript_from_session(
        session,
        transcript_id=f"live-experience-loop::{session.session_id}",
        initial_authority_digest=stable_digest(initial_state),
        browser_evidence={
            "status": "passed",
            "live_viewer_used": True,
            "camera_only_tick_unchanged": camera_only_tick_unchanged,
            "run_world_tick_advanced": session.current_tick > initial_tick,
            "interaction_visible_consequence": bool(session.interaction_audits and session.refinement_patches),
            "off_endpoint_post_count": 0,
            "viewer_generated_fact_count": 0,
            "canvas_lit_pixel_count": 1,
            "control_layout_shift_px": 0,
        },
    )
    report = evaluate_user_facing_world_experience_loop_gate(transcript)
    return {
        "schema": "live_user_facing_world_experience_loop_payload_v1",
        "transcript": transcript,
        "report": report,
    }


def _frame_ids(session: ImplicitFieldSession) -> list[str]:
    return [str(frame["frame_id"]) for frame in session.projection_frame_dicts()]


def _initial_authority_record(session: ImplicitFieldSession) -> dict[str, Any]:
    initial_state = session.implicit_field_states[0] if session.implicit_field_states else session.current_state
    state_id = str(initial_state.get("implicit_field_state_id") or initial_state.get("field_state_id") or "")
    return {
        "authority_kind": "ImplicitFieldState",
        "authority_digest": stable_digest(initial_state),
        "source_record_ids": [state_id] if state_id else list(initial_state.get("source_record_ids", []))[:4],
        "viewer_created": False,
    }


def _empty_fluency_detail_transcript(session: ImplicitFieldSession, browser_evidence: dict[str, Any]) -> dict[str, Any]:
    evidence = dict(browser_evidence)
    session_digest = str(evidence.get("session_digest") or stable_digest(_with_browser_evidence_count(session.manifest(), 0)))
    export = {
        "world_tick_sequence": [int(state.get("tick", session.current_tick)) for state in session.implicit_field_states] or [session.current_tick],
        "observer_path_digest": stable_digest([]),
        "fluency_path_digest": stable_digest([]),
        "refinement_path_digest": stable_digest([]),
        "detail_digest": stable_digest([]),
        "consequence_digest": stable_digest([]),
        "browser_evidence_digest": stable_digest(evidence),
    }
    transcript = {
        "schema": USER_FACING_WORLD_EXPERIENCE_FLUENCY_DETAIL_TRANSCRIPT_SCHEMA,
        "transcript_id": f"live-fluency-detail::{session.session_id}",
        "session_id": session.session_id,
        "session_digest": session_digest,
        "source_package_count": 1,
        "expected_case_count": 1,
        "initial_authority": _initial_authority_record(session),
        "projection_frame_ids": _frame_ids(session),
        "fluency_path": [],
        "refinement_path": [],
        "local_details": [],
        "consequences": [],
        "browser_evidence": evidence,
        "export": dict(export),
        "replay": dict(export),
        "viewer_non_authority": {
            "viewer_created_fact_count": 0,
            "uses_canvas_as_authority": False,
            "uses_css_or_label_as_authority": False,
        },
    }
    transcript["transcript_digest"] = stable_digest({key: value for key, value in transcript.items() if key != "transcript_digest"})
    return transcript


def _fluency_detail_payload(session: ImplicitFieldSession, browser_evidence: dict[str, Any]) -> dict[str, Any]:
    transcript = _empty_fluency_detail_transcript(session, browser_evidence)
    frames = session.projection_frame_dicts()
    if hasattr(session, "solar_earth_scene") and len(frames) >= 5 and session.refinement_requests and session.refinement_patches:
        initial_tick = int(frames[0]["tick"])
        camera_frames = [
            frame
            for frame in frames
            if int(frame["tick"]) == initial_tick
            and (
                frame is frames[0]
                or str(
                    (((frame.get("payload") or {}).get("realtime_projection_frame_packet") or {}).get("frame_kind") or "")
                )
                == "render_only_camera_frame"
            )
        ]
        if len(camera_frames) >= 5:
            for start in range(0, len(camera_frames) - 4):
                candidate_frames = camera_frames[start : start + 5]
                candidate_path = _build_fluency_detail_path(candidate_frames)
                if all(
                    float(record.get("pose_step_world", 0.0)) <= MAX_CAMERA_POSE_STEP_WORLD
                    and float(record.get("apparent_scale_delta", 0.0)) <= MAX_APPARENT_SCALE_DELTA
                    for record in candidate_path
                ):
                    camera_frames = candidate_frames
                    break
            else:
                camera_frames = camera_frames[:5]
        request = dict(session.refinement_requests[-1])
        patch = dict(session.refinement_patches[-1])
        audit = dict(session.interaction_audits[-1]) if session.interaction_audits else {
            "audit_id": "",
            "command_id": "",
        }
        refinement_result = {
            "request": request,
            "patch": patch,
            "interaction_audit": audit,
            "projection_frame_id": "",
        }
        refinement_frame = frames[-1]
        for frame in frames:
            source_ids = set(_fluency_detail_source_ids(frame, limit=256))
            if str(request.get("request_id", "")) in source_ids or str(patch.get("patch_id", "")) in source_ids:
                refinement_frame = frame
                refinement_result["projection_frame_id"] = str(frame["frame_id"])
                break
        if len(camera_frames) >= 5:
            fluency_path = _build_fluency_detail_path(camera_frames)
            refinement_path = _build_fluency_detail_refinement_path([camera_frames[-2], camera_frames[-1], refinement_frame], refinement_result)
            local_details = _build_fluency_detail_local_details(camera_frames, refinement_result)
            consequences = _build_fluency_detail_consequences(
                before_frame=camera_frames[-1],
                refinement_result=refinement_result,
                after_frame=refinement_frame,
            )
            export = {
                "world_tick_sequence": [initial_tick, session.current_tick],
                "observer_path_digest": stable_digest(fluency_path),
                "fluency_path_digest": stable_digest(fluency_path),
                "refinement_path_digest": stable_digest(refinement_path),
                "detail_digest": stable_digest(local_details),
                "consequence_digest": stable_digest(consequences),
                "browser_evidence_digest": stable_digest(browser_evidence),
            }
            transcript.update(
                {
                    "fluency_path": fluency_path,
                    "refinement_path": refinement_path,
                    "local_details": local_details,
                    "consequences": consequences,
                    "export": dict(export),
                    "replay": dict(export),
                }
            )
            transcript["transcript_digest"] = stable_digest(
                {key: value for key, value in transcript.items() if key != "transcript_digest"}
            )
    report = evaluate_user_facing_world_experience_fluency_detail_gate(transcript)
    return {
        "schema": "live_user_facing_world_experience_fluency_detail_payload_v1",
        "fluency_detail_transcript": transcript,
        "fluency_detail_gate_report": report,
    }


def make_handler(
    session: ImplicitFieldSession,
    *,
    max_advance_ticks: int = 32,
    max_session_ticks: int = DEFAULT_MAX_SESSION_TICKS,
    max_frame_records: int = DEFAULT_MAX_FRAME_RECORDS,
    max_response_bytes: int = DEFAULT_MAX_EXPORT_BYTES,
):
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value <= 0
        for value in (max_advance_ticks, max_session_ticks, max_frame_records, max_response_bytes)
    ):
        raise ValueError("server resource limits must be positive integers")
    browser_evidence_store: dict[str, dict[str, Any]] = {"browser_evidence": {}}
    initial_tick = int(session.current_tick)

    class Implicit3DFieldHandler(BaseHTTPRequestHandler):
        server_version = "Implicit3DFieldHTTP/0.1"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send(self, status: int, body: bytes, *, content_type: str = "application/json") -> None:
            if len(body) > max_response_bytes:
                status = 413
                content_type = "application/json"
                body = _json_bytes({"error": "response_too_large", "message": "response exceeds the configured byte limit"})
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
                "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
                "object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
            )
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, status: int, value: Any) -> None:
            self._send(status, _json_bytes(value), content_type="application/json")

        def _read_json(self) -> dict[str, Any]:
            host_header = self.headers.get("Host", "")
            if not host_header or not _is_loopback_hostname(_hostname_from_host_header(host_header)):
                raise PublicRequestError(403, "invalid_host", "mutation requests require a loopback Host")

            origin = self.headers.get("Origin")
            if origin:
                parsed_origin = urlparse(origin)
                if parsed_origin.scheme not in {"http", "https"} or parsed_origin.netloc.lower() != host_header.lower():
                    raise PublicRequestError(403, "foreign_origin", "cross-origin mutation requests are rejected")
            fetch_site = self.headers.get("Sec-Fetch-Site")
            if fetch_site and fetch_site not in {"none", "same-origin"}:
                raise PublicRequestError(403, "cross_site_request", "cross-site mutation requests are rejected")

            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                raise PublicRequestError(415, "unsupported_media_type", "mutation requests require application/json")
            if self.headers.get("Transfer-Encoding"):
                raise PublicRequestError(400, "unsupported_transfer_encoding", "chunked request bodies are not accepted")
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                raise PublicRequestError(411, "length_required", "Content-Length is required")
            try:
                length = int(raw_length)
            except ValueError as exc:
                raise PublicRequestError(400, "invalid_content_length", "Content-Length must be an integer") from exc
            if length <= 0:
                raise PublicRequestError(400, "empty_body", "a JSON object body is required")
            if length > MAX_JSON_BODY_BYTES:
                raise PublicRequestError(413, "request_too_large", "request body exceeds 64 KiB")
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise PublicRequestError(400, "invalid_json", "request body must be valid UTF-8 JSON") from exc
            if not isinstance(payload, dict):
                raise PublicRequestError(400, "invalid_json_shape", "request body must be a JSON object")
            _validate_public_identifiers(payload)
            return payload

        def _ensure_tick_budget(self, ticks: int) -> None:
            if session.current_tick + ticks > initial_tick + max_session_ticks:
                raise PublicRequestError(429, "session_tick_limit", "session tick budget exhausted")

        def _ensure_frame_budget(self, additional_frames: int = 1) -> None:
            if len(session.projection_frame_dicts()) + additional_frames > max_frame_records:
                raise PublicRequestError(429, "frame_limit", "projection frame budget exhausted")

        def _validate_advance_ticks(self, payload: dict[str, Any], *, key: str = "ticks") -> int:
            return canonical_implicit_tick_count(
                payload.get(key, 0),
                name="advance_ticks",
                max_ticks=max_advance_ticks,
            )

        def _session_manifest(self) -> dict[str, Any]:
            return _with_browser_evidence_count(session.manifest(), 1 if browser_evidence_store["browser_evidence"] else 0)

        def _validate_browser_evidence(self, payload: dict[str, Any]) -> dict[str, Any]:
            if payload.get("schema") != USER_FACING_WORLD_EXPERIENCE_FLUENCY_DETAIL_BROWSER_EVIDENCE_SCHEMA:
                raise ValueError("browser evidence schema mismatch")
            if payload.get("is_authority_state") is not False:
                raise ValueError("browser evidence cannot be authority")
            manifest = self._session_manifest()
            if str(payload.get("session_id") or "") != str(manifest["session_id"]):
                raise ValueError("browser evidence session mismatch")
            if str(payload.get("session_digest") or "") != stable_digest(manifest):
                raise ValueError("browser evidence session digest mismatch")
            latest_frame_id = session.projection_frame_dicts()[-1]["frame_id"]
            if str(payload.get("source_projection_frame_id") or "") != str(latest_frame_id):
                raise ValueError("browser evidence stale source_projection_frame_id")
            required_true = ("live_viewer_used", "camera_only_tick_unchanged", "run_world_tick_advanced", "interaction_visible_consequence")
            for key in required_true:
                if not bool(payload.get(key)):
                    raise ValueError(f"browser evidence missing {key}")
            if str(payload.get("status") or "") != "passed":
                raise ValueError("browser evidence not passed")
            if int(payload.get("canvas_lit_pixel_count", 0)) <= 0:
                raise ValueError("browser evidence canvas blank")
            if float(payload.get("control_layout_shift_px", 999.0)) > 2.0:
                raise ValueError("browser evidence layout shifted")
            if int(payload.get("off_endpoint_post_count", 1)) != 0:
                raise ValueError("browser evidence has off-endpoint POST")
            if int(payload.get("viewer_generated_fact_count", 1)) != 0:
                raise ValueError("browser evidence has viewer-generated facts")
            endpoints = payload.get("observed_post_endpoints")
            if not isinstance(endpoints, list) or not endpoints:
                raise ValueError("browser evidence missing observed endpoints")
            return dict(payload)

        def do_GET(self) -> None:
            with session._session_lock:
                self._do_GET_locked()

        def _do_GET_locked(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            try:
                if path in {"/", "/viewer.html"}:
                    html = build_world_viewer_html(
                        {
                            "projection_frames": session.projection_frames,
                            "session": session.manifest(),
                        }
                    )
                    self._send(200, html.encode("utf-8"), content_type="text/html; charset=utf-8")
                    return
                if path == "/session":
                    self._send_json(200, self._session_manifest())
                    return
                if path == "/status":
                    self._send_json(200, {"status": "ok", "session": self._session_manifest()})
                    return
                if path == "/projection_frames.jsonl":
                    self._send(200, _jsonl_bytes(session.projection_frame_dicts()), content_type="application/x-ndjson")
                    return
                if path == "/frames":
                    query = parse_qs(parsed.query)
                    after = query.get("after", [None])[0]
                    frames = session.projection_frame_dicts()
                    if after:
                        seen = False
                        filtered = []
                        for frame in frames:
                            if seen:
                                filtered.append(frame)
                            elif frame["frame_id"] == after:
                                seen = True
                        frames = filtered
                    self._send_json(200, {"frames": frames, "session": self._session_manifest()})
                    return
                if path == "/audit":
                    self._send_json(
                        200,
                        {
                            "interaction_audits": session.interaction_audits,
                            "implicit_live_steps": session.implicit_live_steps,
                            "five_phase_live_steps": session.five_phase_live_steps,
                            "five_phase_live_bridges": session.five_phase_live_bridges,
                            "five_phase_phase_fields": [record.to_dict() for record in session.five_phase_phase_fields],
                            "five_phase_traces": [record.to_dict() for record in session.five_phase_traces],
                            "five_phase_feedback_records": [record.to_dict() for record in session.five_phase_feedback_records],
                            "implicit_camera_move_records": session.camera_move_records,
                            "implicit_spatial_consistency_records": session.spatial_consistency_records,
                            "implicit_observed_structure_records": session.observed_structure_records,
                        },
                    )
                    return
                if path == "/experience_loop":
                    self._send_json(200, _experience_loop_payload(session))
                    return
                if path == "/browser_evidence":
                    self._send_json(200, {"browser_evidence": dict(browser_evidence_store["browser_evidence"])})
                    return
                self._send_json(404, {"error": "not_found"})
            except Exception:
                self._send_json(500, {"error": "server_error", "message": "request could not be completed"})

        def do_POST(self) -> None:
            try:
                payload = self._read_json()
                path = urlparse(self.path).path
                with session._session_lock:
                    self._do_POST_locked(path, payload)
            except PublicRequestError as exc:
                self._send_json(exc.status, {"error": exc.code, "message": exc.public_message})
            except Exception:
                self._send_json(400, {"error": "bad_request", "message": "request was rejected"})

        def _do_POST_locked(self, path: str, payload: dict[str, Any]) -> None:
            if path == "/advance":
                ticks = self._validate_advance_ticks(payload)
                self._ensure_tick_budget(ticks)
                self._ensure_frame_budget()
                session.advance(ticks)
                self._send_json(200, {"session": self._session_manifest()})
                return
            if path == "/run_step":
                ticks = self._validate_advance_ticks(payload)
                self._ensure_tick_budget(ticks)
                self._ensure_frame_budget()
                payload = dict(payload)
                payload["ticks"] = ticks
                result = session.run_step(payload)
                self._send_json(200, {"result": result, "session": self._session_manifest()})
                return
            if path == "/interaction":
                ticks = 0
                if payload.get("advance_after_accept"):
                    ticks = self._validate_advance_ticks(payload, key="advance_ticks")
                self._ensure_tick_budget(ticks)
                self._ensure_frame_budget()
                audit = session.apply_interaction(payload)
                self._send_json(200, {"audit": audit, "session": self._session_manifest()})
                return
            if path == "/camera":
                self._ensure_frame_budget()
                move = session.move_camera(payload)
                self._send_json(200, {"camera_move": move, "session": self._session_manifest()})
                return
            if path == "/render_frame":
                self._ensure_frame_budget()
                result = session.render_frame(payload)
                self._send_json(200, {"result": result, "session": self._session_manifest()})
                return
            if path == "/export":
                exported = session.export_artifacts()
                exported.update(_experience_loop_payload(session))
                exported["experience_transcript"] = exported["transcript"]
                exported["experience_loop_gate_report"] = exported["report"]
                exported["browser_evidence"] = dict(browser_evidence_store["browser_evidence"])
                exported.update(_fluency_detail_payload(session, dict(browser_evidence_store["browser_evidence"])))
                self._send_json(200, exported)
                return
            if path == "/browser_evidence":
                evidence = self._validate_browser_evidence(payload)
                browser_evidence_store["browser_evidence"] = evidence
                self._send_json(200, {"browser_evidence": dict(evidence), "session": self._session_manifest()})
                return
            if path == "/solar_earth/refine":
                self._ensure_frame_budget()
                result = session.request_solar_earth_refinement(
                    world_point=payload.get("world_point"),
                    image_xy=payload.get("source_image_xy") or payload.get("image_xy"),
                    observer_id=payload.get("observer_id", "observer::solar-earth-orbit"),
                    request_id=payload.get("request_id"),
                    requested_radius_world=payload.get("requested_radius_world"),
                    source_projection_frame_id=payload.get("source_projection_frame_id"),
                )
                result = dict(result)
                result.pop("projection_frame", None)
                self._send_json(200, {"result": result, "session": self._session_manifest()})
                return
            self._send_json(404, {"error": "not_found"})

    return Implicit3DFieldHandler


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve a live implicit 3D field interaction window.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--source-package-name", default="source-a")
    parser.add_argument("--source-package-digest", default=None)
    parser.add_argument("--case-type", default="implicit_full_scene")
    parser.add_argument("--run-id", default="implicit-live-demo")
    parser.add_argument("--max-advance-ticks", type=int, default=32)
    parser.add_argument("--max-session-ticks", type=int, default=DEFAULT_MAX_SESSION_TICKS)
    parser.add_argument("--max-frame-records", type=int, default=DEFAULT_MAX_FRAME_RECORDS)
    parser.add_argument("--max-response-bytes", type=int, default=DEFAULT_MAX_EXPORT_BYTES)
    parser.add_argument("--mode", choices=["implicit", "solar-earth"], default="implicit")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not _is_loopback_hostname(args.host):
        print("Refusing non-loopback bind: this research preview is localhost-only.", file=sys.stderr)
        return 2
    if args.mode == "solar-earth":
        session = ImplicitFieldSession.start_solar_earth_demo(session_id=args.run_id, source_package_name=args.source_package_name)
    else:
        session = ImplicitFieldSession.from_source_package(
            source_package_name=args.source_package_name,
            source_package_digest=args.source_package_digest,
            case_type=args.case_type,
            run_id=args.run_id,
            image_shape=[32, 24],
            samples_per_ray=10,
        )
    handler = make_handler(
        session,
        max_advance_ticks=args.max_advance_ticks,
        max_session_ticks=args.max_session_ticks,
        max_frame_records=args.max_frame_records,
        max_response_bytes=args.max_response_bytes,
    )
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving implicit 3D live field viewer at http://{args.host}:{args.port}/viewer.html")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
