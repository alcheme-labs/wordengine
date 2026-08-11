from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


IMPLICIT_SPATIAL_CONSISTENCY_SCHEMA = "implicit_spatial_consistency_record"


def _distance(left: Sequence[float], right: Sequence[float]) -> float:
    return math.sqrt(sum((float(left[index]) - float(right[index])) ** 2 for index in range(2)))


def _image_content_digest(image: Mapping[str, Any]) -> str:
    return str(image.get("image_content_digest") or image.get("image_digest", ""))


def _shared_centroids(image: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    centroids = image.get("shared_basis_centroids")
    if isinstance(centroids, Mapping):
        return {str(key): value for key, value in centroids.items() if isinstance(value, Mapping)}
    result: dict[str, dict[str, Any]] = {}
    table = {int(item.get("index", 0)): str(item.get("basis_id", "")) for item in image.get("dominant_basis_table", []) if isinstance(item, Mapping)}
    for entry in image.get("dominant_basis_centroids", []):
        if not isinstance(entry, Mapping):
            continue
        basis_id = str(entry.get("basis_id") or table.get(int(entry.get("basis_index", 0)), ""))
        if basis_id:
            result[basis_id] = entry
    return result


def estimate_parallax_from_observation_channels(before_image: Mapping[str, Any], after_image: Mapping[str, Any]) -> dict[str, Any]:
    before = _shared_centroids(before_image)
    after = _shared_centroids(after_image)
    shared_ids = sorted(set(before) & set(after))
    motions: list[dict[str, Any]] = []
    for basis_id in shared_ids:
        before_xy = [float(value) for value in before[basis_id].get("centroid_image_xy", [0.0, 0.0])]
        after_xy = [float(value) for value in after[basis_id].get("centroid_image_xy", [0.0, 0.0])]
        mean_depth = (float(before[basis_id].get("mean_depth", 0.0)) + float(after[basis_id].get("mean_depth", 0.0))) / 2.0
        motions.append(
            {
                "basis_id": basis_id,
                "before_centroid_image_xy": before_xy,
                "after_centroid_image_xy": after_xy,
                "mean_depth": mean_depth,
                "motion_pixels": _distance(before_xy, after_xy),
            }
        )
    if len(motions) < 2:
        return {"status": "failed", "reason": "insufficient_spatial_correspondence", "shared_target_motion": []}
    sorted_by_depth = sorted(motions, key=lambda item: float(item["mean_depth"]))
    midpoint = max(1, len(sorted_by_depth) // 2)
    near = sorted_by_depth[:midpoint]
    far = sorted_by_depth[midpoint:] or sorted_by_depth[-1:]
    near_motion = sum(float(item["motion_pixels"]) for item in near) / len(near)
    far_motion = sum(float(item["motion_pixels"]) for item in far) / len(far)
    smaller_motion = min(near_motion, far_motion)
    larger_motion = max(near_motion, far_motion)
    return {
        "status": "passed",
        "near_motion_pixels": near_motion,
        "far_motion_pixels": far_motion,
        "parallax_ratio": larger_motion / max(smaller_motion, 0.01),
        "shared_target_motion": motions,
    }


def estimate_depth_order_consistency(before_image: Mapping[str, Any], after_image: Mapping[str, Any]) -> float:
    before = _shared_centroids(before_image)
    after = _shared_centroids(after_image)
    shared_ids = sorted(set(before) & set(after))
    if len(shared_ids) < 2:
        return 0.0
    consistent = 0
    total = 0
    for i, left in enumerate(shared_ids):
        for right in shared_ids[i + 1 :]:
            before_order = float(before[left].get("mean_depth", 0.0)) <= float(before[right].get("mean_depth", 0.0))
            after_order = float(after[left].get("mean_depth", 0.0)) <= float(after[right].get("mean_depth", 0.0))
            total += 1
            if before_order == after_order:
                consistent += 1
    return consistent / max(1, total)


def build_implicit_spatial_consistency_record(
    camera_move_id: str,
    before_ray_sample_record_id: str,
    after_ray_sample_record_id: str,
    before_image: Mapping[str, Any],
    after_image: Mapping[str, Any],
    source_state_digest: str,
    result_state_digest: str,
) -> dict[str, Any]:
    parallax = estimate_parallax_from_observation_channels(before_image, after_image)
    record = {
        "schema": IMPLICIT_SPATIAL_CONSISTENCY_SCHEMA,
        "spatial_consistency_id": f"implicit-spatial-consistency::{camera_move_id}",
        "camera_move_id": str(camera_move_id),
        "before_ray_sample_record_id": str(before_ray_sample_record_id),
        "after_ray_sample_record_id": str(after_ray_sample_record_id),
        "before_image_content_digest": _image_content_digest(before_image),
        "after_image_content_digest": _image_content_digest(after_image),
        "source_state_digest": str(source_state_digest),
        "result_state_digest": str(result_state_digest),
        "state_digest_unchanged": str(source_state_digest) == str(result_state_digest),
        "ray_geometry_changed": str(before_ray_sample_record_id) != str(after_ray_sample_record_id),
        "image_digest_changed": _image_content_digest(before_image) != _image_content_digest(after_image),
        "near_motion_pixels": float(parallax.get("near_motion_pixels", 0.0)),
        "far_motion_pixels": float(parallax.get("far_motion_pixels", 0.0)),
        "parallax_ratio": float(parallax.get("parallax_ratio", 0.0)),
        "shared_target_motion": list(parallax.get("shared_target_motion", [])),
        "occlusion_delta": abs(float(after_image.get("occlusion_response_score", 0.0)) - float(before_image.get("occlusion_response_score", 0.0))),
        "depth_order_consistency": estimate_depth_order_consistency(before_image, after_image),
        "status": str(parallax.get("status", "passed")),
        "source_record_ids": [str(camera_move_id), str(before_ray_sample_record_id), str(after_ray_sample_record_id)],
        "is_authority_state": False,
    }
    if parallax.get("reason"):
        record["reason"] = str(parallax["reason"])
    if record["status"] == "passed" and float(record.get("parallax_ratio", 0.0)) < 1.15:
        record["status"] = "failed"
        record["reason"] = "parallax_below_threshold"
    if record["status"] == "passed" and float(record.get("depth_order_consistency", 0.0)) < 0.5:
        record["status"] = "failed"
        record["reason"] = "depth_order_below_threshold"
    if record["status"] == "passed":
        validate_implicit_spatial_consistency_record(record)
    return record


def validate_implicit_spatial_consistency_record(record: Mapping[str, Any]) -> None:
    if record.get("schema") != IMPLICIT_SPATIAL_CONSISTENCY_SCHEMA:
        raise ValueError("implicit spatial consistency schema mismatch")
    if record.get("is_authority_state") is not False:
        raise ValueError("implicit spatial consistency record must be non-authority")
    if record.get("state_digest_unchanged") is not True:
        raise ValueError("implicit spatial consistency requires unchanged state digest")
    if record.get("ray_geometry_changed") is not True:
        raise ValueError("implicit spatial consistency requires changed ray geometry")
    if record.get("image_digest_changed") is not True:
        raise ValueError("implicit spatial consistency requires changed image content digest")
    if len(record.get("shared_target_motion", [])) < 2:
        raise ValueError("implicit spatial consistency requires shared target motion")
    if float(record.get("parallax_ratio", 0.0)) < 1.15:
        raise ValueError("implicit spatial consistency parallax below threshold")
    if float(record.get("depth_order_consistency", 0.0)) < 0.5:
        raise ValueError("implicit spatial consistency depth order below threshold")
