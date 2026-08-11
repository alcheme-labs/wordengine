from __future__ import annotations

from typing import Any, Mapping, Sequence


IMPLICIT_BASELINE_COMPARISON_SCHEMA = "implicit_baseline_comparison_record"

FORBIDDEN_BASELINE_AUTHORITY_KEYS = {
    "css_color",
    "viewer_shape",
    "viewer_label",
    "canvas_pixels",
    "viewer_transform",
    "mesh",
    "sprite",
    "object_asset_id",
}

REQUIRED_CONTEXT_KEYS = {
    "source_package_name",
    "seed_salt",
    "basis_layout_digest",
    "observer_path_digest",
    "tick_window",
}

REQUIRED_DELTA_METRICS = {
    "image_delta",
    "coefficient_delta",
    "ray_integral_delta",
    "local_refinement_correction_delta",
}


def _assert_no_forbidden_keys(value: Any, *, path: str = "payload") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in FORBIDDEN_BASELINE_AUTHORITY_KEYS:
                raise ValueError(f"forbidden implicit baseline key at {path}: {key}")
            _assert_no_forbidden_keys(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_forbidden_keys(child, path=f"{path}[{index}]")


def _context_copy(context: Mapping[str, Any]) -> dict[str, Any]:
    missing = REQUIRED_CONTEXT_KEYS - set(context)
    if missing:
        raise ValueError(f"implicit baseline context missing keys: {sorted(missing)}")
    return {
        "source_package_name": str(context["source_package_name"]),
        "seed_salt": str(context["seed_salt"]),
        "basis_layout_digest": str(context["basis_layout_digest"]),
        "observer_path_digest": str(context["observer_path_digest"]),
        "tick_window": [int(value) for value in context["tick_window"]],
    }


def build_implicit_baseline_comparison_record(
    comparison_id: str,
    case_id: str,
    baseline_case_id: str,
    source_context: Mapping[str, Any],
    baseline_context: Mapping[str, Any],
    source_implicit_field_state_id: str,
    baseline_implicit_field_state_id: str,
    source_ray_sample_record_ids: Sequence[str],
    baseline_ray_sample_record_ids: Sequence[str],
    source_image_plane_ids: Sequence[str],
    baseline_image_plane_ids: Sequence[str],
    delta_metrics: Mapping[str, Any],
    source_record_ids: Sequence[str],
) -> dict[str, Any]:
    record = {
        "schema": IMPLICIT_BASELINE_COMPARISON_SCHEMA,
        "comparison_id": str(comparison_id),
        "case_id": str(case_id),
        "baseline_case_id": str(baseline_case_id),
        "source_context": _context_copy(source_context),
        "baseline_context": _context_copy(baseline_context),
        "source_implicit_field_state_id": str(source_implicit_field_state_id),
        "baseline_implicit_field_state_id": str(baseline_implicit_field_state_id),
        "source_ray_sample_record_ids": [str(value) for value in source_ray_sample_record_ids],
        "baseline_ray_sample_record_ids": [str(value) for value in baseline_ray_sample_record_ids],
        "source_image_plane_ids": [str(value) for value in source_image_plane_ids],
        "baseline_image_plane_ids": [str(value) for value in baseline_image_plane_ids],
        "delta_metrics": {str(key): float(value) for key, value in delta_metrics.items()},
        "source_record_ids": [str(value) for value in source_record_ids],
        "is_authority_state": False,
    }
    validate_implicit_baseline_comparison_record(record)
    return record


def validate_implicit_baseline_comparison_record(record: Mapping[str, Any]) -> None:
    if record.get("schema") != IMPLICIT_BASELINE_COMPARISON_SCHEMA:
        raise ValueError("implicit baseline comparison schema mismatch")
    if record.get("is_authority_state") is not False:
        raise ValueError("implicit baseline comparison must be non-authority")
    source_context = _context_copy(record.get("source_context", {}))
    baseline_context = _context_copy(record.get("baseline_context", {}))
    for key in REQUIRED_CONTEXT_KEYS:
        if source_context[key] != baseline_context[key]:
            raise ValueError(f"implicit baseline context mismatch: {key}")
    metrics = record.get("delta_metrics")
    if not isinstance(metrics, Mapping):
        raise ValueError("implicit baseline comparison requires delta metrics")
    missing_metrics = REQUIRED_DELTA_METRICS - set(metrics)
    if missing_metrics:
        raise ValueError(f"implicit baseline comparison missing delta metrics: {sorted(missing_metrics)}")
    if float(metrics.get("image_delta", 0.0)) < 0.08:
        raise ValueError("implicit baseline comparison image delta below interaction threshold")
    if not record.get("source_ray_sample_record_ids") or not record.get("baseline_ray_sample_record_ids"):
        raise ValueError("implicit baseline comparison requires ray sample ids")
    if not record.get("source_image_plane_ids") or not record.get("baseline_image_plane_ids"):
        raise ValueError("implicit baseline comparison requires image plane ids")
    if not record.get("source_record_ids"):
        raise ValueError("implicit baseline comparison requires source records")
    _assert_no_forbidden_keys(record)
