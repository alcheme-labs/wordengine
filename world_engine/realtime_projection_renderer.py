from __future__ import annotations

from typing import Any, Iterable, Mapping


REALTIME_PROJECTION_FRAME_PACKET_SCHEMA = "realtime_projection_frame_packet_v1"
REALTIME_RENDER_FRAME_REQUEST_SCHEMA = "realtime_render_frame_request_v1"
REALTIME_OBSERVER_CAMERA_STATE_SCHEMA = "realtime_observer_camera_state_v1"
REALTIME_RENDERABLE_SCHEMA = "realtime_renderable_v1"
REALTIME_LOD_STATE_SCHEMA = "realtime_lod_state_v1"
REALTIME_SENSOR_STATE_SCHEMA = "realtime_sensor_state_v1"

ALLOWED_REALTIME_CAMERA_ACTIONS = frozenset(
    {
        "forward",
        "back",
        "strafe_left",
        "strafe_right",
        "up",
        "down",
        "orbit_left",
        "orbit_right",
        "yaw_left",
        "yaw_right",
        "pitch_up",
        "pitch_down",
        "zoom_in",
        "zoom_out",
        "reset",
    }
)

ALLOWED_REALTIME_SENSOR_BAND_MODES = frozenset(
    {"visible_surface", "near_ir_penetrating", "thermal_internal"}
)

REALTIME_RENDERER_THRESHOLDS = {
    "max_camera_position_delta_without_intermediate_frame": 0.65,
    "max_apparent_radius_ratio_delta": 1.18,
    "max_lod_weight_delta_per_frame": 0.22,
    "min_nonblack_canvas_pixels": 500,
    "min_render_packet_source_record_ids": 4,
    "max_renderer_owned_authority_fields": 0,
    "max_render_only_world_tick_delta": 0,
}

_FORBIDDEN_RENDERABLE_KEYS = frozenset(
    {
        "renderer_defined_region_kind",
        "renderer_defined_material",
        "renderer_defined_body",
        "renderer_defined_force",
    }
)

_RENDERABLE_AUTHORITY_REF_KEYS = (
    "geometry_ref",
    "volume_ref",
    "surface_field_ref",
    "radiation_ref",
    "material_response_ref",
)


def _require_mapping(value: Any, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return value


def _require_nonempty_string(value: Any, *, name: str) -> str:
    parsed = str(value or "")
    if not parsed:
        raise ValueError(f"{name} must be non-empty")
    return parsed


def _require_nonempty_list(value: Any, *, name: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} must be a non-empty list")
    return list(value)


def _string_set(values: Iterable[Any]) -> set[str]:
    return {str(value) for value in values if str(value)}


def validate_realtime_projection_frame_packet(packet: Mapping[str, Any]) -> None:
    packet = _require_mapping(packet, name="packet")
    if packet.get("schema") != REALTIME_PROJECTION_FRAME_PACKET_SCHEMA:
        raise ValueError("realtime projection packet schema mismatch")
    if packet.get("viewer_is_not_authority") is not True:
        raise ValueError("viewer_is_not_authority must be true")
    if packet.get("is_authority_state") is not False:
        raise ValueError("realtime projection packet cannot be authority state")

    source_record_ids = _require_nonempty_list(packet.get("source_record_ids"), name="source_record_ids")
    source_refs = _string_set(source_record_ids)
    authority_summary_ids = _require_nonempty_list(packet.get("authority_summary_ids"), name="authority_summary_ids")
    authority_refs = _string_set(authority_summary_ids)
    _require_nonempty_string(packet.get("projection_loss_manifest_id"), name="projection_loss_manifest_id")
    _require_nonempty_list(packet.get("invariant_signature_ids"), name="invariant_signature_ids")
    spectral_refs = _require_mapping(packet.get("spectral_observation_refs"), name="spectral_observation_refs")
    image_plane_id = _require_nonempty_string(
        spectral_refs.get("image_plane_id"),
        name="spectral_observation_refs.image_plane_id",
    )
    sensor_state_id = _require_nonempty_string(
        spectral_refs.get("spectral_sensor_state_id"),
        name="spectral_observation_refs.spectral_sensor_state_id",
    )
    ray_observation_id = _require_nonempty_string(
        spectral_refs.get("sensor_ray_observation_id"),
        name="spectral_observation_refs.sensor_ray_observation_id",
    )
    for value, name in (
        (image_plane_id, "spectral_observation_refs.image_plane_id"),
        (sensor_state_id, "spectral_observation_refs.spectral_sensor_state_id"),
        (ray_observation_id, "spectral_observation_refs.sensor_ray_observation_id"),
    ):
        if value not in source_refs:
            raise ValueError(f"{name} missing from source_record_ids")

    camera_state = _require_mapping(packet.get("camera_state"), name="camera_state")
    if camera_state.get("schema") != REALTIME_OBSERVER_CAMERA_STATE_SCHEMA:
        raise ValueError("camera_state schema mismatch")
    lod_state = _require_mapping(packet.get("lod_state"), name="lod_state")
    if lod_state.get("schema") != REALTIME_LOD_STATE_SCHEMA:
        raise ValueError("lod_state schema mismatch")
    sensor_state = _require_mapping(packet.get("sensor_state"), name="sensor_state")
    if sensor_state.get("schema") != REALTIME_SENSOR_STATE_SCHEMA:
        raise ValueError("sensor_state schema mismatch")
    if str(sensor_state.get("sensor_state_id") or "") != sensor_state_id:
        raise ValueError("sensor_state_id must match spectral_observation_refs")

    packet_id = str(packet.get("packet_id") or "")
    if packet_id and packet_id in source_refs:
        raise ValueError("packet_id must not appear in source_record_ids")

    if packet.get("frame_kind") == "render_only_camera_frame" and int(packet.get("world_tick_delta", 0)) != 0:
        raise ValueError("render-only frame cannot advance world tick")

    renderables = packet.get("renderables")
    if not isinstance(renderables, list) or not renderables:
        raise ValueError("renderables must be a non-empty list")
    for renderable in renderables:
        renderable = _require_mapping(renderable, name="renderable")
        if renderable.get("schema") != REALTIME_RENDERABLE_SCHEMA:
            raise ValueError("renderable schema mismatch")
        if renderable.get("is_authority_state") is not False:
            raise ValueError("renderable cannot be authority state")
        forbidden = _FORBIDDEN_RENDERABLE_KEYS.intersection(renderable)
        if forbidden:
            raise ValueError(sorted(forbidden)[0])
        cited_refs = {str(renderable.get(key)) for key in _RENDERABLE_AUTHORITY_REF_KEYS if renderable.get(key)}
        if not cited_refs.intersection(source_refs | authority_refs):
            raise ValueError("renderable authority reference missing from source_record_ids or authority_summary_ids")


def validate_realtime_render_frame_request(
    request: Mapping[str, Any],
    *,
    current_frame_id: str,
    current_tick: int,
    current_camera_state_id: str,
    seen_request_ids: set[str],
) -> None:
    request = _require_mapping(request, name="request")
    if request.get("schema") != REALTIME_RENDER_FRAME_REQUEST_SCHEMA:
        raise ValueError("realtime render frame request schema mismatch")
    request_id = _require_nonempty_string(request.get("request_id"), name="request_id")
    if request_id in seen_request_ids:
        raise ValueError("duplicate request_id")
    if str(request.get("source_projection_frame_id") or "") != str(current_frame_id):
        raise ValueError("source_projection_frame_id must match current frame")
    if int(request.get("source_scene_tick", -1)) != int(current_tick):
        raise ValueError("source_scene_tick must match current tick")
    if str(request.get("previous_camera_state_id") or "") != str(current_camera_state_id):
        raise ValueError("previous_camera_state_id must match current camera state")
    render_dt_ms = int(request.get("render_dt_ms", 0))
    if render_dt_ms < 1 or render_dt_ms > 50:
        raise ValueError("render_dt_ms outside bounds")
    if str(request.get("camera_action") or "") not in ALLOWED_REALTIME_CAMERA_ACTIONS:
        raise ValueError("unsupported realtime camera_action")
    if str(request.get("sensor_band_mode") or "") not in ALLOWED_REALTIME_SENSOR_BAND_MODES:
        raise ValueError("unsupported realtime sensor_band_mode")
