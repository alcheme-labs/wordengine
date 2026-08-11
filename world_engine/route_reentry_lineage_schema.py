from __future__ import annotations

from typing import Any


GUARD_CONTRACT = "registry-backed-route-reentry-guard-v1"
LINEAGE_SCHEMA = "route_reentry_target_lineage_v1"
LINEAGE_SCHEMA_SOURCE_PATH = "world_engine/route_reentry_lineage_schema.py"


def route_reentry_lineage_schema_owner_record() -> dict[str, Any]:
    return {
        "source_path": LINEAGE_SCHEMA_SOURCE_PATH,
        "schema": LINEAGE_SCHEMA,
        "guard_contract": GUARD_CONTRACT,
        "manual_lineage_schema_allowed": False,
    }


def route_reentry_lineage_record(target: Any) -> dict[str, Any]:
    return {
        "schema": LINEAGE_SCHEMA,
        "source_path": LINEAGE_SCHEMA_SOURCE_PATH,
        "guard_contract": GUARD_CONTRACT,
        "target_registry_key": target.key,
        "lifecycle": target.lifecycle,
        "capability": target.capability,
        "implementation_slug": target.implementation_slug,
        "result_slug": target.result_slug,
        "expected_target_id": target.expected_target_id,
        "authority_output_stem": target.authority_output_stem,
        "payload_key": target.payload_key,
        "projection_schema": target.projection_schema,
        "predecessor_target_key": target.predecessor_target_key,
        "predecessor_module_name": target.predecessor_module_name,
        "readout_id": target.readout_id,
        "payload_guard": target.payload_guard,
    }
