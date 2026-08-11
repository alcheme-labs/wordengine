from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from world_engine.route_reentry_target_registry import route_reentry_viewer_registry


ROUTE_REENTRY_VIEWER_READOUT_CONTRACT = "route-reentry-viewer-readout-contract-v1"
ROUTE_REENTRY_VIEWER_STATIC_SLOT_GROWTH_GUARD_SCHEMA = "route_reentry_viewer_static_slot_growth_guard_v1"
GENERIC_VIEWER_READOUT_GUARD_SOURCE_PATH = "world_engine/route_reentry_generic_viewer_readout_guard.py"
VIEWER_SOURCE_PATH = "world_engine/viewer.py"
GRANDFATHERED_STATIC_TARGET_KEYS = (
    "latest_corrected_transfer",
    "planned_retention_after_latest_transfer",
    "planned_continuity_after_latest_retention",
    "planned_generalization_after_latest_continuity",
)


def route_reentry_generic_viewer_readout_guard_owner_record() -> dict[str, Any]:
    return {
        "source_path": GENERIC_VIEWER_READOUT_GUARD_SOURCE_PATH,
        "schema": ROUTE_REENTRY_VIEWER_STATIC_SLOT_GROWTH_GUARD_SCHEMA,
        "viewer_source_path": VIEWER_SOURCE_PATH,
        "viewer_readout_contract": ROUTE_REENTRY_VIEWER_READOUT_CONTRACT,
        "target_specific_viewer_required": False,
    }


def route_reentry_viewer_static_slot_growth_guard_record(
    *,
    viewer_source: str | None = None,
    registry: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    viewer_text = _viewer_source_text() if viewer_source is None else viewer_source
    viewer_registry = route_reentry_viewer_registry() if registry is None else registry
    grandfathered: list[dict[str, Any]] = []
    registry_only: list[dict[str, Any]] = []
    violations: list[dict[str, str]] = []

    for authority_output_stem, spec in viewer_registry.items():
        target_key = str(spec.get("key", ""))
        entry = _static_slot_entry(viewer_text, authority_output_stem, spec)
        if target_key in GRANDFATHERED_STATIC_TARGET_KEYS:
            grandfathered.append(entry)
            continue
        registry_only.append(entry)
        if entry["static_readout_id_present"]:
            violations.append(
                {
                    "target_registry_key": target_key,
                    "reason": "static_readout_id_present",
                    "readout_id": entry["readout_id"],
                }
            )
        if entry["static_authority_output_stem_present"]:
            violations.append(
                {
                    "target_registry_key": target_key,
                    "reason": "static_authority_output_stem_present",
                    "authority_output_stem": authority_output_stem,
                }
            )

    return {
        "schema": ROUTE_REENTRY_VIEWER_STATIC_SLOT_GROWTH_GUARD_SCHEMA,
        "source_path": GENERIC_VIEWER_READOUT_GUARD_SOURCE_PATH,
        "viewer_source_path": VIEWER_SOURCE_PATH,
        "viewer_readout_contract": ROUTE_REENTRY_VIEWER_READOUT_CONTRACT,
        "generic_registry_slots_present": "registry-derived-route-reentry-readout-slots-v1" in viewer_text,
        "grandfathered_static_target_keys": list(GRANDFATHERED_STATIC_TARGET_KEYS),
        "grandfathered_static_targets": grandfathered,
        "registry_only_targets": registry_only,
        "violations": violations,
    }


def validate_route_reentry_viewer_static_slot_growth_guard_record(record: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if record.get("schema") != ROUTE_REENTRY_VIEWER_STATIC_SLOT_GROWTH_GUARD_SCHEMA:
        failures.append("viewer static slot growth guard schema mismatch")
    if record.get("source_path") != GENERIC_VIEWER_READOUT_GUARD_SOURCE_PATH:
        failures.append("viewer static slot growth guard source path mismatch")
    if record.get("viewer_source_path") != VIEWER_SOURCE_PATH:
        failures.append("viewer static slot growth guard viewer source path mismatch")
    if record.get("viewer_readout_contract") != ROUTE_REENTRY_VIEWER_READOUT_CONTRACT:
        failures.append("viewer readout contract mismatch")
    if record.get("generic_registry_slots_present") is not True:
        failures.append("generic registry route-reentry slots missing")
    if tuple(record.get("grandfathered_static_target_keys") or ()) != GRANDFATHERED_STATIC_TARGET_KEYS:
        failures.append("grandfathered static target keys mismatch")

    grandfathered_targets = _list_of_mappings(record.get("grandfathered_static_targets"))
    registry_only_targets = _list_of_mappings(record.get("registry_only_targets"))
    if _target_keys(grandfathered_targets) != sorted(GRANDFATHERED_STATIC_TARGET_KEYS):
        failures.append("grandfathered static target list mismatch")
    if _target_keys(registry_only_targets) != _expected_registry_only_target_keys():
        failures.append("registry-only target list mismatch")

    for target in registry_only_targets:
        key = str(target.get("target_registry_key", ""))
        if target.get("static_readout_id_present") is True:
            failures.append(f"registry-only target has static viewer slot: {key}")
        if target.get("static_authority_output_stem_present") is True:
            failures.append(f"registry-only target has static authority stem: {key}")

    for violation in _list_of_mappings(record.get("violations")):
        key = str(violation.get("target_registry_key", ""))
        reason = str(violation.get("reason", ""))
        if reason == "static_readout_id_present":
            failures.append(f"registry-only target has static viewer slot: {key}")
        elif reason == "static_authority_output_stem_present":
            failures.append(f"registry-only target has static authority stem: {key}")
        else:
            failures.append(f"viewer static slot growth guard violation: {key}")

    return list(dict.fromkeys(failures))


def _static_slot_entry(viewer_source: str, authority_output_stem: str, spec: Mapping[str, Any]) -> dict[str, Any]:
    readout_id = str(spec.get("readoutId", ""))
    target_key = str(spec.get("key", ""))
    return {
        "target_registry_key": target_key,
        "authority_output_stem": authority_output_stem,
        "readout_id": readout_id,
        "static_readout_id_present": _quoted_attribute_value_present(viewer_source, "id", readout_id),
        "static_authority_output_stem_present": authority_output_stem in viewer_source,
    }


def _quoted_attribute_value_present(source: str, attribute: str, value: str) -> bool:
    if not value:
        return False
    return f'{attribute}="{value}"' in source or f"{attribute}='{value}'" in source


def _viewer_source_text() -> str:
    return (Path(__file__).resolve().parents[1] / VIEWER_SOURCE_PATH).read_text(encoding="utf-8")


def _list_of_mappings(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _target_keys(targets: list[Mapping[str, Any]]) -> list[str]:
    return sorted(str(target.get("target_registry_key", "")) for target in targets)


def _expected_registry_only_target_keys() -> list[str]:
    return sorted(
        str(spec.get("key", ""))
        for spec in route_reentry_viewer_registry().values()
        if str(spec.get("key", "")) not in GRANDFATHERED_STATIC_TARGET_KEYS
    )
