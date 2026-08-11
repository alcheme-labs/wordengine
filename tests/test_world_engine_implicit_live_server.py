import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from scripts.serve_implicit_3d_field_window import MAX_JSON_BODY_BYTES, main, make_handler
from world_engine.implicit_live_session import ImplicitFieldSession
from world_engine.user_facing_world_experience_fluency_detail_gate import (
    USER_FACING_WORLD_EXPERIENCE_FLUENCY_DETAIL_BROWSER_EVIDENCE_SCHEMA,
    stable_digest,
)


def make_session():
    return ImplicitFieldSession.from_source_package(
        source_package_name="source-a",
        source_package_digest="digest-a",
        case_type="implicit_full_scene",
        run_id="test-live-server",
        image_shape=[12, 8],
        samples_per_ray=6,
    )


class LiveServerFixture:
    def __init__(self, **handler_options):
        self.handler_options = handler_options

    def __enter__(self):
        self.session = make_session()
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            make_handler(self.session, max_advance_ticks=4, **self.handler_options),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        return self

    def __exit__(self, exc_type, exc, tb):
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()

    def get_json(self, path):
        with urllib.request.urlopen(self.base_url + path, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_text(self, path):
        with urllib.request.urlopen(self.base_url + path, timeout=5) as response:
            return response.read().decode("utf-8")

    def post_json(self, path, payload):
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def post_json_expect_error(self, path, payload):
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as error:
            return json.loads(error.read().decode("utf-8"))
        raise AssertionError(f"{path} unexpectedly succeeded")


def interaction(fixture, **overrides):
    source_frame = json.loads(fixture.get_text("/projection_frames.jsonl").strip().splitlines()[-1])
    payload = {
        "schema": "implicit_interaction_request",
        "request_id": "viewer-1",
        "tool": "implicit_local_excite",
        "observer_id": "observer::implicit-pinhole",
        "source_projection_frame_id": source_frame["frame_id"],
        "source_frame_tick": source_frame["tick"],
        "source_state_id": source_frame["payload"]["implicit_field_state_id"],
        "source_ray_sample_record_id": source_frame["payload"]["implicit_ray_sample_record"]["ray_sample_record_id"],
        "source_image_xy": [0.5, 0.5],
        "radius_world": 1.0,
        "amplitude": 0.35,
        "duration_ticks": 2.0,
        "advance_after_accept": True,
        "advance_ticks": 2,
    }
    payload.update(overrides)
    return payload


def browser_evidence(fixture):
    session = fixture.get_json("/session")
    latest_frame = json.loads(fixture.get_text("/projection_frames.jsonl").strip().splitlines()[-1])
    return {
        "schema": USER_FACING_WORLD_EXPERIENCE_FLUENCY_DETAIL_BROWSER_EVIDENCE_SCHEMA,
        "sidecar_id": "browser-evidence::unit-test",
        "session_id": session["session_id"],
        "session_digest": stable_digest(session),
        "source_projection_frame_id": latest_frame["frame_id"],
        "status": "passed",
        "live_viewer_used": True,
        "camera_only_tick_unchanged": True,
        "run_world_tick_advanced": True,
        "interaction_visible_consequence": True,
        "canvas_lit_pixel_count": 1200,
        "control_layout_shift_px": 0,
        "observed_post_endpoints": ["/render_frame", "/run_step", "/browser_evidence", "/export"],
        "off_endpoint_post_count": 0,
        "viewer_generated_fact_count": 0,
        "is_authority_state": False,
    }


class ImplicitLiveServerTests(unittest.TestCase):
    def test_session_viewer_and_projection_routes(self):
        with LiveServerFixture() as fixture:
            session = fixture.get_json("/session")
            self.assertEqual("live-implicit-3d-field", session["runtime_mode"])
            html = fixture.get_text("/viewer.html")
            self.assertIn("projection_frames.jsonl", html)
            frame_lines = fixture.get_text("/projection_frames.jsonl").strip().splitlines()
            self.assertEqual(1, len(frame_lines))
            frame = json.loads(frame_lines[0])
            self.assertEqual("implicit_3d_field_observation", frame["payload"]["render_mode"])

    def test_public_server_refuses_non_loopback_bind_and_sets_security_headers(self):
        self.assertEqual(2, main(["--host", "0.0.0.0", "--port", "0"]))
        with LiveServerFixture() as fixture:
            with urllib.request.urlopen(fixture.base_url + "/viewer.html", timeout=5) as response:
                html = response.read().decode("utf-8")
                self.assertEqual("DENY", response.headers["X-Frame-Options"])
                self.assertEqual("nosniff", response.headers["X-Content-Type-Options"])
                self.assertEqual("same-origin", response.headers["Cross-Origin-Resource-Policy"])
                self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
            self.assertNotIn("eventTimelineEl.innerHTML", html)
            self.assertIn("eventTimelineEl.replaceChildren", html)

    def test_cross_site_wrong_media_type_and_oversized_posts_are_atomic(self):
        with LiveServerFixture() as fixture:
            before = fixture.get_json("/session")
            cases = (
                (b'{"ticks":1}', {"Content-Type": "text/plain"}, 415),
                (
                    b'{"ticks":1}',
                    {"Content-Type": "application/json", "Origin": "https://attacker.invalid"},
                    403,
                ),
                (
                    b"{" + b" " * MAX_JSON_BODY_BYTES,
                    {"Content-Type": "application/json"},
                    413,
                ),
            )
            for body, headers, expected_status in cases:
                with self.subTest(status=expected_status):
                    request = urllib.request.Request(
                        fixture.base_url + "/advance",
                        data=body,
                        headers=headers,
                        method="POST",
                    )
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        urllib.request.urlopen(request, timeout=5)
                    self.assertEqual(expected_status, error.exception.code)
                    self.assertEqual(before, fixture.get_json("/session"))

    def test_unsafe_identifier_and_internal_exception_text_are_not_reflected(self):
        with LiveServerFixture() as fixture:
            unsafe = interaction(
                fixture,
                request_id='<img src=x onerror="window.__genewordXssProbe=1">',
            )
            response = fixture.post_json_expect_error("/interaction", unsafe)
            self.assertEqual("invalid_identifier", response["error"])
            self.assertNotIn("<img", json.dumps(response))

            response = fixture.post_json_expect_error(
                "/interaction",
                interaction(fixture, request_id="safe-invalid-radius", radius_world=0),
            )
            self.assertEqual({"error": "bad_request", "message": "request was rejected"}, response)

    def test_session_frame_and_response_budgets_fail_closed(self):
        with LiveServerFixture(max_session_ticks=1) as fixture:
            fixture.post_json("/advance", {"ticks": 1})
            before = fixture.get_json("/session")
            response = fixture.post_json_expect_error("/advance", {"ticks": 1})
            self.assertEqual("session_tick_limit", response["error"])
            self.assertEqual(before, fixture.get_json("/session"))

        with LiveServerFixture(max_frame_records=1) as fixture:
            before = fixture.get_json("/session")
            response = fixture.post_json_expect_error("/advance", {"ticks": 1})
            self.assertEqual("frame_limit", response["error"])
            self.assertEqual(before, fixture.get_json("/session"))

        with LiveServerFixture(max_response_bytes=256) as fixture:
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(fixture.base_url + "/session", timeout=5)
            self.assertEqual(413, error.exception.code)

    def test_advance_and_interaction_mutate_session(self):
        with LiveServerFixture() as fixture:
            before = fixture.get_json("/session")
            advanced = fixture.post_json("/advance", {"ticks": 2})
            self.assertEqual(before["current_tick"] + 2, advanced["session"]["current_tick"])
            interacted = fixture.post_json("/interaction", interaction(fixture, request_id="viewer-advance"))
            self.assertEqual("applied", interacted["audit"]["status"])
            after = fixture.get_json("/session")
            self.assertGreater(after["projection_frame_count"], before["projection_frame_count"])
            self.assertGreater(after["interaction_audit_count"], 0)

    def test_export_route_returns_json_artifacts(self):
        with LiveServerFixture() as fixture:
            exported = fixture.post_json("/export", {})
            self.assertEqual("live-implicit-3d-field", exported["session"]["runtime_mode"])
            self.assertGreater(len(exported["projection_frames"]), 0)
            self.assertIn("frame_id", exported["projection_frames"][0])
            self.assertIn("implicit_ray_sample_record", exported["projection_frames"][0]["payload"])

    def test_camera_route_moves_observer_without_mutating_world_state(self):
        with LiveServerFixture() as fixture:
            before = fixture.get_json("/session")
            first_frame = json.loads(fixture.get_text("/projection_frames.jsonl").strip().splitlines()[-1])
            moved = fixture.post_json(
                "/camera",
                {
                    "schema": "implicit_camera_move_request",
                    "request_id": "camera-route-1",
                    "observer_id": "observer::implicit-pinhole",
                    "source_projection_frame_id": first_frame["frame_id"],
                    "source_frame_tick": first_frame["tick"],
                    "action": "orbit_left",
                    "step_world": 0.45,
                    "yaw_degrees": 12.0,
                },
            )
            self.assertFalse(moved["camera_move"]["world_state_changed"])
            self.assertTrue(moved["camera_move"]["state_digest_unchanged"])
            after = fixture.get_json("/session")
            self.assertEqual(before["current_tick"], after["current_tick"])
            self.assertEqual(1, after["camera_move_count"])
            self.assertGreater(after["projection_frame_count"], before["projection_frame_count"])
            audit = fixture.get_json("/audit")
            self.assertEqual(1, len(audit["implicit_camera_move_records"]))
            self.assertEqual(1, len(audit["implicit_spatial_consistency_records"]))

    def test_invalid_request_and_invalid_advance_roll_back(self):
        with LiveServerFixture() as fixture:
            before = fixture.get_json("/session")
            with self.assertRaises(urllib.error.HTTPError) as error:
                fixture.post_json("/interaction", interaction(fixture, request_id="bad", radius_world=0))
            self.assertEqual(400, error.exception.code)
            self.assertEqual(before, fixture.get_json("/session"))

            with self.assertRaises(urllib.error.HTTPError) as error:
                fixture.post_json("/interaction", interaction(fixture, request_id="bad-advance", advance_ticks=99))
            self.assertEqual(400, error.exception.code)
            self.assertEqual(before, fixture.get_json("/session"))

            for path, payload in (
                ("/advance", {"ticks": 1.9}),
                (
                    "/run_step",
                    {
                        "schema": "implicit_world_run_step_request",
                        "request_id": "fractional-run-step",
                        "observer_id": "observer::implicit-pinhole",
                        "ticks": 1.9,
                    },
                ),
                (
                    "/interaction",
                    interaction(
                        fixture,
                        request_id="fractional-interaction-advance",
                        advance_ticks=1.9,
                    ),
                ),
                (
                    "/interaction",
                    interaction(
                        fixture,
                        request_id="non-boolean-interaction-advance",
                        advance_after_accept="false",
                    ),
                ),
            ):
                with self.subTest(path=path):
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        fixture.post_json(path, payload)
                    self.assertEqual(400, error.exception.code)
                    self.assertEqual(before, fixture.get_json("/session"))

    def test_run_step_advances_world_and_returns_world_step_frame(self):
        with LiveServerFixture() as fixture:
            before = fixture.get_json("/session")
            response = fixture.post_json(
                "/run_step",
                {
                    "schema": "implicit_world_run_step_request",
                    "request_id": "run-step-001",
                    "observer_id": "observer::implicit-pinhole",
                    "ticks": 1,
                    "camera_action": None,
                    "source_projection_frame_id": json.loads(
                        fixture.get_text("/projection_frames.jsonl").strip().splitlines()[-1]
                    )["frame_id"],
                },
            )
            after = response["session"]

            self.assertEqual(after["current_tick"], before["current_tick"] + 1)
            latest = json.loads(fixture.get_text("/projection_frames.jsonl").strip().splitlines()[-1])
            semantics = latest["payload"]["timeline_semantics"]
            self.assertEqual(semantics["frame_kind"], "world_step_observation")
            self.assertTrue(semantics["world_advanced"])
            self.assertFalse(semantics["camera_moved"])

    def test_run_step_can_move_camera_and_advance_world_in_one_frame(self):
        with LiveServerFixture() as fixture:
            source = json.loads(fixture.get_text("/projection_frames.jsonl").strip().splitlines()[-1])
            before = fixture.get_json("/session")
            response = fixture.post_json(
                "/run_step",
                {
                    "schema": "implicit_world_run_step_request",
                    "request_id": "run-step-camera-001",
                    "observer_id": "observer::implicit-pinhole",
                    "ticks": 2,
                    "camera_action": "forward",
                    "camera_step_world": 0.35,
                    "camera_yaw_degrees": 8.0,
                    "source_projection_frame_id": source["frame_id"],
                },
            )
            after = response["session"]

            self.assertEqual(after["current_tick"], before["current_tick"] + 2)
            self.assertEqual(after["projection_frame_count"], before["projection_frame_count"] + 1)
            latest = json.loads(fixture.get_text("/projection_frames.jsonl").strip().splitlines()[-1])
            semantics = latest["payload"]["timeline_semantics"]
            self.assertEqual(semantics["frame_kind"], "camera_world_step_observation")
            self.assertTrue(semantics["world_advanced"])
            self.assertTrue(semantics["camera_moved"])
            self.assertEqual(semantics["world_tick_window"], [before["current_tick"], after["current_tick"]])
            self.assertEqual(semantics["camera_action"], "forward")
            self.assertIsNone(semantics["source_camera_move_id"])
            self.assertIsNotNone(semantics["previous_camera_pose_digest"])
            self.assertIsNotNone(semantics["result_camera_pose_digest"])
            self.assertEqual(after["camera_move_count"], before["camera_move_count"])

    def test_run_step_failure_rolls_back_session(self):
        with LiveServerFixture() as fixture:
            before = fixture.get_json("/session")
            response = fixture.post_json_expect_error(
                "/run_step",
                {
                    "schema": "implicit_world_run_step_request",
                    "request_id": "run-step-invalid",
                    "observer_id": "observer::implicit-pinhole",
                    "ticks": 99999,
                    "camera_action": "forward",
                },
            )

            self.assertEqual({"error": "bad_request", "message": "request was rejected"}, response)
            after = fixture.get_json("/session")
            self.assertEqual(after["current_tick"], before["current_tick"])
            self.assertEqual(after["projection_frame_count"], before["projection_frame_count"])
            self.assertEqual(after["camera_move_count"], before["camera_move_count"])

    def test_run_step_rejects_historical_source_frame(self):
        with LiveServerFixture() as fixture:
            historical = json.loads(fixture.get_text("/projection_frames.jsonl").strip().splitlines()[-1])
            fixture.post_json("/advance", {"ticks": 1})
            before = fixture.get_json("/session")

            response = fixture.post_json_expect_error(
                "/run_step",
                {
                    "schema": "implicit_world_run_step_request",
                    "request_id": "run-step-historical-source",
                    "observer_id": "observer::implicit-pinhole",
                    "ticks": 1,
                    "camera_action": None,
                    "source_projection_frame_id": historical["frame_id"],
                },
            )

            self.assertEqual({"error": "bad_request", "message": "request was rejected"}, response)
            self.assertEqual(fixture.get_json("/session"), before)

    def test_browser_evidence_route_records_non_authority_sidecar(self):
        with LiveServerFixture() as fixture:
            evidence = browser_evidence(fixture)
            stored = fixture.post_json("/browser_evidence", evidence)

            self.assertEqual(evidence, stored["browser_evidence"])
            self.assertFalse(stored["browser_evidence"]["is_authority_state"])
            self.assertEqual(evidence, fixture.get_json("/browser_evidence")["browser_evidence"])

    def test_export_includes_browser_evidence_sidecar_without_mutating_world_state(self):
        with LiveServerFixture() as fixture:
            before = fixture.get_json("/session")
            latest_frame = json.loads(fixture.get_text("/projection_frames.jsonl").strip().splitlines()[-1])
            evidence = browser_evidence(fixture)

            fixture.post_json("/browser_evidence", evidence)
            exported = fixture.post_json("/export", {})
            after = fixture.get_json("/session")

            self.assertEqual(evidence, exported["browser_evidence"])
            self.assertIn("fluency_detail_transcript", exported)
            self.assertIn("fluency_detail_gate_report", exported)
            self.assertEqual("passed", exported["fluency_detail_gate_report"]["browser_evidence_replay_status"])
            self.assertEqual(before["current_tick"], after["current_tick"])
            self.assertEqual(before["projection_frame_count"], after["projection_frame_count"])
            self.assertEqual(before["camera_move_count"], after["camera_move_count"])
            self.assertEqual(before["interaction_audit_count"], after["interaction_audit_count"])
            self.assertEqual(latest_frame["frame_id"], evidence["source_projection_frame_id"])
            self.assertEqual(1, after["browser_evidence_count"])

    def test_browser_evidence_rejects_stale_session_digest(self):
        with LiveServerFixture() as fixture:
            evidence = browser_evidence(fixture)
            evidence["session_digest"] = "stale-session-digest"

            with self.assertRaises(urllib.error.HTTPError) as error:
                fixture.post_json("/browser_evidence", evidence)

            self.assertEqual(400, error.exception.code)
            self.assertEqual({}, fixture.get_json("/browser_evidence")["browser_evidence"])


if __name__ == "__main__":
    unittest.main()
