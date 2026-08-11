from __future__ import annotations

from typing import Any


def build_matter_projection_payload(artifacts: dict[str, Any]) -> dict[str, Any]:
    macros = list(artifacts.get("macro_material_states", []))
    zones = list(artifacts.get("material_environment_zones", []))
    contacts = list(artifacts.get("material_contact_records", []))
    responses = list(artifacts.get("material_response_records", []))
    bodies_by_id = {body.body_id: body for body in artifacts.get("material_bodies", [])}
    responses_by_contact: dict[str, list[Any]] = {}
    for response in responses:
        responses_by_contact.setdefault(response.material_contact_record_id, []).append(response)
    zones_by_id = {zone.zone_id: zone for zone in zones}
    overlays: list[dict[str, Any]] = []
    for macro in macros:
        body = bodies_by_id.get(macro.body_id)
        overlays.append(
            {
                "overlay_kind": "effective_material_body",
                "source_macro_material_state_id": macro.macro_material_state_id,
                "source_material_body_id": macro.body_id,
                "source_species_certificate_ids": list(macro.source_species_certificate_ids),
                "support_bounds_world": list(macro.support_bounds_world),
                "body_kind": body.body_kind if body else "unknown",
                "aggregate_effective_properties": dict(macro.aggregate_effective_properties),
                "source_record_ids": sorted(set([macro.macro_material_state_id, macro.body_id, *macro.source_record_ids])),
                "is_authority_state": False,
            }
        )
    zone_overlays: list[dict[str, Any]] = []
    for zone in zones:
        zone_overlays.append(
            {
                "overlay_kind": "effective_material_world_zone",
                "zone_id": zone.zone_id,
                "region_id": zone.region_id,
                "material_behavior_profile_id": zone.material_behavior_profile_id,
                "source_macro_material_state_id": zone.source_macro_material_state_id,
                "source_material_body_id": zone.source_material_body_id,
                "behavior_class": zone.behavior_class,
                "zone_role": zone.zone_role,
                "region_bounds_grid": list(zone.region_bounds_grid),
                "region_bounds_world": list(zone.region_bounds_world),
                "coordinate_frame": dict(zone.coordinate_frame),
                "source_record_ids": sorted(set(zone.source_record_ids)),
                "is_authority_state": False,
            }
        )
    contact_overlays: list[dict[str, Any]] = []
    for contact in contacts:
        contact_responses = responses_by_contact.get(contact.record_id, [])
        contact_zone = zones_by_id.get(contact.target_zone_id)
        response_ids = [response.record_id for response in contact_responses]
        response_kinds = [response.response_kind for response in contact_responses]
        source_record_ids = sorted(
            set(
                [
                    contact.record_id,
                    *contact.source_record_ids,
                    *response_ids,
                    *(record_id for response in contact_responses for record_id in response.source_record_ids),
                ]
            )
        )
        contact_overlays.append(
            {
                "overlay_kind": "material_contact_overlay_v1",
                "material_contact_record_id": contact.record_id,
                "material_response_record_ids": response_ids,
                "response_kinds": response_kinds,
                "contact_kind": contact.contact_kind,
                "target_zone_id": contact.target_zone_id,
                "target_behavior_profile_id": contact.target_behavior_profile_id,
                "target_macro_material_state_id": contact.target_macro_material_state_id,
                "source_component_id": contact.source_component_id,
                "contact_region_grid": list(contact.contact_region_grid),
                "contact_region_world": list(contact.contact_region_world),
                "support_centroid_grid": list(contact.support_centroid_grid),
                "incoming_vector_grid": list(contact.incoming_vector_grid),
                "contact_energy": contact.contact_energy,
                "overlap_fraction": contact.overlap_fraction,
                "coordinate_frame": dict(contact_zone.coordinate_frame) if contact_zone else {},
                "source_record_ids": source_record_ids,
                "is_authority_state": False,
            }
        )
    return {
        "schema": "effective_matter_projection_v1",
        "material_overlays": overlays,
        "material_environment_zones": zone_overlays,
        "material_contact_overlays": contact_overlays,
        "notice": "effective matter, not real chemical elements",
        "material_world_notice": "effective material behavior, not real chemistry",
        "is_authority_state": False,
    }
