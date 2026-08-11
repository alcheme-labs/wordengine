from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from world_engine.contracts import CompletionCheck, CompletionReport, ProjectionFrame


JsonDict = dict[str, Any]

M13_SCHEMA_VERSION = "m13_projection_invariant_boundary_reset_v1"
ALLOWED_NO_STABLE_STRUCTURE_REASONS = {
    "empty_observation_window",
    "below_stability_threshold",
    "transient_only",
    "occluded_by_projection_limits",
}

DEFAULT_M13_THRESHOLD_PROFILE: JsonDict = {
    "threshold_profile_id": "threshold-profile::m13-defaults",
    "boundary_signed_distance_crossing_min": 0.01,
    "boundary_overlap_delta_min": 0.05,
    "boundary_flux_delta_min": 0.03,
    "phase_energy_gradient_min": 0.08,
    "phase_temperature_delta_min": 0.05,
    "phase_moisture_delta_min": 0.05,
    "phase_damping_delta_min": 0.04,
    "invariant_energy_relative_delta_max": 0.12,
    "invariant_centroid_delta_world_max": 0.08,
    "projection_known_ambiguity_max_severity": "bounded",
}


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(_to_json(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def short_record_id(prefix: str, value: Any) -> str:
    return f"{prefix}::{canonical_digest(value).split(':', 1)[1][:16]}"


def _to_json(value: Any) -> Any:
    if hasattr(value, "to_payload"):
        return value.to_payload()
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, tuple):
        return [_to_json(item) for item in value]
    if isinstance(value, list):
        return [_to_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_json(item) for key, item in value.items()}
    return value


def _tuple_str(values: Sequence[Any]) -> tuple[str, ...]:
    return tuple(str(value) for value in values)


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    value = str(payload.get(key, ""))
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _required_ids(payload: Mapping[str, Any], key: str) -> tuple[str, ...]:
    values = _tuple_str(payload.get(key, ()))
    if not values:
        raise ValueError(f"{key} is required")
    return values


@dataclass(frozen=True)
class ProjectionLossManifest:
    manifest_id: str
    projection_frame_id: str
    observer_id: str
    authority_record_ids: tuple[str, ...]
    projection_map_id: str
    observer_resolution: Mapping[str, Any]
    preserved_invariants: tuple[Mapping[str, Any], ...]
    discarded_degrees_of_freedom: tuple[str, ...]
    known_ambiguities: tuple[Mapping[str, Any], ...]
    source_record_ids: tuple[str, ...]
    no_stable_structure_reason: str | None = None

    def to_payload(self) -> JsonDict:
        return {
            "projection_loss_manifest_v1": {
                "manifest_id": self.manifest_id,
                "projection_frame_id": self.projection_frame_id,
                "observer_id": self.observer_id,
                "authority_record_ids": list(self.authority_record_ids),
                "projection_map_id": self.projection_map_id,
                "observer_resolution": _to_json(dict(self.observer_resolution)),
                "preserved_invariants": [_to_json(dict(item)) for item in self.preserved_invariants],
                "no_stable_structure_reason": self.no_stable_structure_reason,
                "discarded_degrees_of_freedom": list(self.discarded_degrees_of_freedom),
                "known_ambiguities": [_to_json(dict(item)) for item in self.known_ambiguities],
                "source_record_ids": list(self.source_record_ids),
            }
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ProjectionLossManifest":
        data = payload.get("projection_loss_manifest_v1", payload)
        validate_projection_loss_manifest_payload(data)
        return cls(
            manifest_id=str(data["manifest_id"]),
            projection_frame_id=str(data["projection_frame_id"]),
            observer_id=str(data["observer_id"]),
            authority_record_ids=_tuple_str(data["authority_record_ids"]),
            projection_map_id=str(data["projection_map_id"]),
            observer_resolution=dict(data.get("observer_resolution", {})),
            preserved_invariants=tuple(dict(item) for item in data.get("preserved_invariants", [])),
            no_stable_structure_reason=data.get("no_stable_structure_reason"),
            discarded_degrees_of_freedom=_tuple_str(data.get("discarded_degrees_of_freedom", [])),
            known_ambiguities=tuple(dict(item) for item in data.get("known_ambiguities", [])),
            source_record_ids=_tuple_str(data["source_record_ids"]),
        )


@dataclass(frozen=True)
class InvariantSignature:
    signature_id: str
    structure_id: str
    source_authority_record_ids: tuple[str, ...]
    runtime_window: Mapping[str, int]
    signature_method: str
    runtime_summary_record_id: str
    summary_source_kind: str
    input_digest: str
    stable_features: Mapping[str, Any]
    instability_flags: tuple[str, ...]
    source_record_ids: tuple[str, ...]

    def to_payload(self) -> JsonDict:
        return {
            "invariant_signature_v1": {
                "signature_id": self.signature_id,
                "structure_id": self.structure_id,
                "source_authority_record_ids": list(self.source_authority_record_ids),
                "runtime_window": _to_json(dict(self.runtime_window)),
                "signature_method": self.signature_method,
                "runtime_summary_record_id": self.runtime_summary_record_id,
                "summary_source_kind": self.summary_source_kind,
                "input_digest": self.input_digest,
                "stable_features": _to_json(dict(self.stable_features)),
                "instability_flags": list(self.instability_flags),
                "source_record_ids": list(self.source_record_ids),
            }
        }


@dataclass(frozen=True)
class BoundaryCrossingRecord:
    boundary_crossing_id: str
    event_kind: str
    before_support_record_id: str
    after_support_record_id: str
    before_support_digest: str
    after_support_digest: str
    input_digest: str
    boundary_kind: str
    crossing_metric: Mapping[str, float]
    affected_signature_ids: tuple[str, ...]
    source_record_ids: tuple[str, ...]

    def to_payload(self) -> JsonDict:
        return {
            "boundary_crossing_record_v1": {
                "boundary_crossing_id": self.boundary_crossing_id,
                "event_kind": self.event_kind,
                "before_support_record_id": self.before_support_record_id,
                "after_support_record_id": self.after_support_record_id,
                "before_support_digest": self.before_support_digest,
                "after_support_digest": self.after_support_digest,
                "input_digest": self.input_digest,
                "boundary_kind": self.boundary_kind,
                "crossing_metric": _to_json(dict(self.crossing_metric)),
                "affected_signature_ids": list(self.affected_signature_ids),
                "source_record_ids": list(self.source_record_ids),
            }
        }


@dataclass(frozen=True)
class PhaseTransitionRecord:
    phase_transition_id: str
    transition_kind: str
    before_phase: str
    after_phase: str
    before_metric_record_id: str
    after_metric_record_id: str
    threshold_profile_id: str
    input_digest: str
    trigger_metric: Mapping[str, float]
    thresholds: Mapping[str, Any]
    affected_region_ids: tuple[str, ...]
    source_record_ids: tuple[str, ...]

    def to_payload(self) -> JsonDict:
        return {
            "phase_transition_record_v1": {
                "phase_transition_id": self.phase_transition_id,
                "transition_kind": self.transition_kind,
                "before_phase": self.before_phase,
                "after_phase": self.after_phase,
                "before_metric_record_id": self.before_metric_record_id,
                "after_metric_record_id": self.after_metric_record_id,
                "threshold_profile_id": self.threshold_profile_id,
                "input_digest": self.input_digest,
                "trigger_metric": _to_json(dict(self.trigger_metric)),
                "thresholds": _to_json(dict(self.thresholds)),
                "affected_region_ids": list(self.affected_region_ids),
                "source_record_ids": list(self.source_record_ids),
            }
        }


@dataclass(frozen=True)
class GenesisRuleEvidence:
    genesis_rule_id: str
    authoring_template_id: str
    input_condition_ids: tuple[str, ...]
    compiled_constraint_record_ids: tuple[str, ...]
    expected_transition_kinds: tuple[str, ...]
    observed_transition_record_ids: tuple[str, ...]
    observed_signature_ids: tuple[str, ...]
    status: str
    source_record_ids: tuple[str, ...]

    def to_payload(self) -> JsonDict:
        return {
            "genesis_rule_evidence_v1": {
                "genesis_rule_id": self.genesis_rule_id,
                "authoring_template_id": self.authoring_template_id,
                "input_condition_ids": list(self.input_condition_ids),
                "compiled_constraint_record_ids": list(self.compiled_constraint_record_ids),
                "expected_transition_kinds": list(self.expected_transition_kinds),
                "observed_transition_record_ids": list(self.observed_transition_record_ids),
                "observed_signature_ids": list(self.observed_signature_ids),
                "status": self.status,
                "source_record_ids": list(self.source_record_ids),
            }
        }


def validate_projection_loss_manifest_payload(payload: Mapping[str, Any], *, visible_structure_count: int = 0) -> None:
    _required_text(payload, "manifest_id")
    _required_text(payload, "projection_frame_id")
    _required_text(payload, "observer_id")
    _required_text(payload, "projection_map_id")
    _required_ids(payload, "authority_record_ids")
    _required_ids(payload, "source_record_ids")
    if not payload.get("discarded_degrees_of_freedom"):
        raise ValueError("discarded_degrees_of_freedom is required")
    preserved = list(payload.get("preserved_invariants", []))
    reason = payload.get("no_stable_structure_reason")
    if visible_structure_count > 0 and not preserved:
        raise ValueError("visible stable structures require preserved invariant signatures")
    if not preserved:
        if reason not in ALLOWED_NO_STABLE_STRUCTURE_REASONS:
            raise ValueError("no_stable_structure_reason is required for frames without preserved invariants")
    if preserved and reason:
        raise ValueError("no_stable_structure_reason must be empty when preserved invariants exist")


def build_projection_loss_manifest(
    frame_payload: Mapping[str, Any],
    *,
    authority_record_ids: Sequence[str],
    projection_map_id: str,
    preserved_invariants: Sequence[Mapping[str, Any]],
    discarded_degrees_of_freedom: Sequence[str],
    known_ambiguities: Sequence[Mapping[str, Any]],
    no_stable_structure_reason: str | None = None,
) -> ProjectionLossManifest:
    projection_frame_id = str(frame_payload.get("frame_id") or frame_payload.get("projection_frame_id") or "")
    observer_id = str(frame_payload.get("observer_id") or "")
    if not projection_frame_id:
        raise ValueError("projection frame id is required")
    if not observer_id:
        raise ValueError("observer_id is required")
    source_ids = tuple(dict.fromkeys([*map(str, authority_record_ids), projection_frame_id]))
    payload = {
        "projection_frame_id": projection_frame_id,
        "observer_id": observer_id,
        "authority_record_ids": list(map(str, authority_record_ids)),
        "projection_map_id": projection_map_id,
        "preserved_invariants": [_to_json(dict(item)) for item in preserved_invariants],
        "no_stable_structure_reason": no_stable_structure_reason,
        "discarded_degrees_of_freedom": list(map(str, discarded_degrees_of_freedom)),
        "known_ambiguities": [_to_json(dict(item)) for item in known_ambiguities],
        "source_record_ids": list(source_ids),
    }
    manifest = ProjectionLossManifest(
        manifest_id=short_record_id("projection-loss", payload),
        projection_frame_id=projection_frame_id,
        observer_id=observer_id,
        authority_record_ids=tuple(map(str, authority_record_ids)),
        projection_map_id=str(projection_map_id),
        observer_resolution=dict(frame_payload.get("observer_resolution", {})),
        preserved_invariants=tuple(dict(item) for item in preserved_invariants),
        no_stable_structure_reason=no_stable_structure_reason,
        discarded_degrees_of_freedom=tuple(map(str, discarded_degrees_of_freedom)),
        known_ambiguities=tuple(dict(item) for item in known_ambiguities),
        source_record_ids=source_ids,
    )
    validate_projection_loss_manifest_payload(manifest.to_payload()["projection_loss_manifest_v1"])
    return manifest


def compute_invariant_signature(
    runtime_summary: Mapping[str, Any],
    *,
    method: str,
    source_record_ids: Sequence[str],
) -> InvariantSignature:
    runtime_summary_record_id = str(runtime_summary.get("record_id") or "")
    if not runtime_summary_record_id:
        raise ValueError("runtime summary record_id is required")
    input_digest = str(runtime_summary.get("digest") or canonical_digest(runtime_summary))
    stable_features = {
        "support_digest": canonical_digest(runtime_summary.get("support", runtime_summary.get("support_digest", ""))),
        "centroid_world": _to_json(runtime_summary.get("centroid_world", [0.0, 0.0, 0.0])),
        "relative_energy": float(runtime_summary.get("relative_energy", runtime_summary.get("energy", 0.0))),
        "mode_signature": _to_json(runtime_summary.get("mode_signature", [])),
        "boundary_digest": canonical_digest(runtime_summary.get("boundary", runtime_summary.get("boundary_digest", ""))),
    }
    source_authority_record_ids = _tuple_str(runtime_summary.get("source_authority_record_ids", source_record_ids))
    payload = {
        "structure_id": runtime_summary.get("structure_id", runtime_summary_record_id),
        "source_authority_record_ids": list(source_authority_record_ids),
        "runtime_window": runtime_summary.get("runtime_window", {"start_tick": int(runtime_summary.get("tick", 0)), "end_tick": int(runtime_summary.get("tick", 0))}),
        "signature_method": str(method),
        "runtime_summary_record_id": runtime_summary_record_id,
        "summary_source_kind": runtime_summary.get("summary_source_kind", "compact_digest_verified"),
        "input_digest": input_digest,
        "stable_features": stable_features,
    }
    return InvariantSignature(
        signature_id=short_record_id("invariant-signature", payload),
        structure_id=str(payload["structure_id"]),
        source_authority_record_ids=source_authority_record_ids,
        runtime_window=dict(payload["runtime_window"]),
        signature_method=str(method),
        runtime_summary_record_id=runtime_summary_record_id,
        summary_source_kind=str(payload["summary_source_kind"]),
        input_digest=input_digest,
        stable_features=stable_features,
        instability_flags=_tuple_str(runtime_summary.get("instability_flags", [])),
        source_record_ids=tuple(dict.fromkeys([*map(str, source_record_ids), runtime_summary_record_id])),
    )


def detect_boundary_crossing(
    before_support: Mapping[str, Any],
    after_support: Mapping[str, Any],
    *,
    boundary_kind: str,
    thresholds: Mapping[str, Any],
    source_record_ids: Sequence[str],
    event_kind: str = "contact",
    affected_signature_ids: Sequence[str] = (),
) -> BoundaryCrossingRecord | None:
    before_id = str(before_support.get("record_id") or "")
    after_id = str(after_support.get("record_id") or "")
    if not before_id or not after_id:
        raise ValueError("before/after support record ids are required for boundary crossing")
    before_digest = str(before_support.get("digest") or canonical_digest(before_support))
    after_digest = str(after_support.get("digest") or canonical_digest(after_support))
    before_signed = float(before_support.get("signed_distance", 0.0))
    after_signed = float(after_support.get("signed_distance", 0.0))
    overlap_delta = float(after_support.get("overlap", 0.0)) - float(before_support.get("overlap", 0.0))
    flux_delta = float(after_support.get("flux", 0.0)) - float(before_support.get("flux", 0.0))
    signed_crossed = before_signed * after_signed <= 0.0 and abs(after_signed - before_signed) >= float(thresholds["boundary_signed_distance_crossing_min"])
    overlap_crossed = abs(overlap_delta) >= float(thresholds["boundary_overlap_delta_min"])
    flux_crossed = abs(flux_delta) >= float(thresholds["boundary_flux_delta_min"])
    if not (signed_crossed or overlap_crossed or flux_crossed):
        return None
    payload = {
        "event_kind": event_kind,
        "before_support_record_id": before_id,
        "after_support_record_id": after_id,
        "before_support_digest": before_digest,
        "after_support_digest": after_digest,
        "boundary_kind": boundary_kind,
        "crossing_metric": {
            "signed_distance_before": before_signed,
            "signed_distance_after": after_signed,
            "overlap_delta": overlap_delta,
            "flux_delta": flux_delta,
        },
        "affected_signature_ids": list(map(str, affected_signature_ids)),
        "source_record_ids": list(dict.fromkeys([*map(str, source_record_ids), before_id, after_id])),
    }
    input_digest = canonical_digest(payload)
    return BoundaryCrossingRecord(
        boundary_crossing_id=short_record_id("boundary-crossing", {**payload, "input_digest": input_digest}),
        event_kind=event_kind,
        before_support_record_id=before_id,
        after_support_record_id=after_id,
        before_support_digest=before_digest,
        after_support_digest=after_digest,
        input_digest=input_digest,
        boundary_kind=str(boundary_kind),
        crossing_metric=payload["crossing_metric"],
        affected_signature_ids=_tuple_str(affected_signature_ids),
        source_record_ids=tuple(payload["source_record_ids"]),
    )


def _reject_loose_thresholds(thresholds: Mapping[str, Any]) -> None:
    has_source_profile = bool(thresholds.get("threshold_profile_record_id"))
    for key, value in DEFAULT_M13_THRESHOLD_PROFILE.items():
        if key == "threshold_profile_id" or not isinstance(value, (int, float)):
            continue
        candidate = thresholds.get(key, value)
        if isinstance(candidate, (int, float)) and float(candidate) < float(value) and not has_source_profile:
            raise ValueError("threshold profile source record is required for looser-than-default thresholds")


def detect_phase_transition(
    before_metrics: Mapping[str, Any],
    after_metrics: Mapping[str, Any],
    *,
    transition_kind: str,
    thresholds: Mapping[str, Any],
    source_record_ids: Sequence[str],
    affected_region_ids: Sequence[str] = (),
) -> PhaseTransitionRecord | None:
    _reject_loose_thresholds(thresholds)
    before_id = str(before_metrics.get("record_id") or "")
    after_id = str(after_metrics.get("record_id") or "")
    if not before_id or not after_id:
        raise ValueError("before/after metric record ids are required for phase transition")
    trigger_metric = {
        "energy_gradient": float(after_metrics.get("energy", 0.0)) - float(before_metrics.get("energy", 0.0)),
        "temperature_delta": float(after_metrics.get("temperature", 0.0)) - float(before_metrics.get("temperature", 0.0)),
        "moisture_delta": float(after_metrics.get("moisture", 0.0)) - float(before_metrics.get("moisture", 0.0)),
        "damping_delta": float(after_metrics.get("damping", 0.0)) - float(before_metrics.get("damping", 0.0)),
    }
    crossed = (
        abs(trigger_metric["energy_gradient"]) >= float(thresholds["phase_energy_gradient_min"])
        or abs(trigger_metric["temperature_delta"]) >= float(thresholds["phase_temperature_delta_min"])
        or abs(trigger_metric["moisture_delta"]) >= float(thresholds["phase_moisture_delta_min"])
        or abs(trigger_metric["damping_delta"]) >= float(thresholds["phase_damping_delta_min"])
    )
    if not crossed:
        return None
    payload = {
        "transition_kind": transition_kind,
        "before_phase": before_metrics.get("phase", "unknown"),
        "after_phase": after_metrics.get("phase", "unknown"),
        "before_metric_record_id": before_id,
        "after_metric_record_id": after_id,
        "threshold_profile_id": thresholds.get("threshold_profile_id", DEFAULT_M13_THRESHOLD_PROFILE["threshold_profile_id"]),
        "trigger_metric": trigger_metric,
        "thresholds": dict(thresholds),
        "affected_region_ids": list(map(str, affected_region_ids)),
        "source_record_ids": list(dict.fromkeys([*map(str, source_record_ids), before_id, after_id])),
    }
    input_digest = canonical_digest(payload)
    return PhaseTransitionRecord(
        phase_transition_id=short_record_id("phase-transition", {**payload, "input_digest": input_digest}),
        transition_kind=str(transition_kind),
        before_phase=str(payload["before_phase"]),
        after_phase=str(payload["after_phase"]),
        before_metric_record_id=before_id,
        after_metric_record_id=after_id,
        threshold_profile_id=str(payload["threshold_profile_id"]),
        input_digest=input_digest,
        trigger_metric=trigger_metric,
        thresholds=dict(thresholds),
        affected_region_ids=_tuple_str(affected_region_ids),
        source_record_ids=tuple(payload["source_record_ids"]),
    )


def validate_genesis_rule_evidence_payload(payload: Mapping[str, Any]) -> None:
    _required_text(payload, "genesis_rule_id")
    _required_text(payload, "authoring_template_id")
    _required_ids(payload, "input_condition_ids")
    _required_ids(payload, "compiled_constraint_record_ids")
    _required_ids(payload, "expected_transition_kinds")
    _required_ids(payload, "source_record_ids")
    status = str(payload.get("status", ""))
    if status not in {"matched", "partial", "failed"}:
        raise ValueError("genesis evidence status must be matched, partial, or failed")
    if status == "matched" and not payload.get("observed_transition_record_ids"):
        raise ValueError("matched genesis evidence requires observed transition records")
    if status == "matched" and not payload.get("observed_signature_ids"):
        raise ValueError("matched genesis evidence requires observed signature records")


def _unwrap_record_payload(record: Any, expected_key: str) -> JsonDict:
    payload = record.to_payload() if hasattr(record, "to_payload") else dict(record)
    data = payload.get(expected_key, payload)
    return _to_json(dict(data))


def _record_id_for_kind(record_kind: str, payload: Mapping[str, Any]) -> str:
    key_by_kind = {
        "projection_loss_manifest_v1": "manifest_id",
        "invariant_signature_v1": "signature_id",
        "boundary_crossing_record_v1": "boundary_crossing_id",
        "phase_transition_record_v1": "phase_transition_id",
        "genesis_rule_evidence_v1": "genesis_rule_id",
    }
    key = key_by_kind[record_kind]
    return str(payload.get(key, ""))


def _frame_m13_payload(frame: ProjectionFrame) -> Mapping[str, Any]:
    value = frame.payload.get("m13_projection_invariant_boundary_v1", {})
    return value if isinstance(value, Mapping) else {}


def collect_projection_invariant_boundary_sidecar_records(frames: Sequence[ProjectionFrame]) -> list[JsonDict]:
    records: list[JsonDict] = []
    for frame in frames:
        payloads_by_kind = {
            "projection_loss_manifest_v1": [frame.payload.get("projection_loss_manifest_v1")],
            "invariant_signature_v1": list(frame.payload.get("invariant_signatures_v1", [])),
            "boundary_crossing_record_v1": list(frame.payload.get("boundary_crossing_records_v1", [])),
            "phase_transition_record_v1": list(frame.payload.get("phase_transition_records_v1", [])),
            "genesis_rule_evidence_v1": list(frame.payload.get("genesis_rule_evidence_v1", [])),
        }
        for record_kind, payloads in payloads_by_kind.items():
            for payload in payloads:
                if not isinstance(payload, Mapping):
                    continue
                record_id = _record_id_for_kind(record_kind, payload)
                if not record_id:
                    continue
                records.append(
                    {
                        "schema": M13_SCHEMA_VERSION,
                        "record_kind": record_kind,
                        "record_id": record_id,
                        "projection_frame_id": frame.frame_id,
                        "payload_digest": canonical_digest(payload),
                        "payload": _to_json(dict(payload)),
                        "source_record_ids": list(dict.fromkeys([frame.frame_id, *map(str, payload.get("source_record_ids", []))])),
                    }
                )
    return records


def _sidecar_index(sidecar_records: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], Mapping[str, Any]]:
    index: dict[tuple[str, str], Mapping[str, Any]] = {}
    for record in sidecar_records:
        kind = str(record.get("record_kind", ""))
        record_id = str(record.get("record_id", ""))
        payload = record.get("payload")
        if not kind or not record_id or not isinstance(payload, Mapping):
            continue
        index[(kind, record_id)] = record
    return index


def _check_sidecar_payload(
    *,
    index: Mapping[tuple[str, str], Mapping[str, Any]],
    record_kind: str,
    record_id: str,
    embedded_payload: Mapping[str, Any] | None,
) -> str | None:
    sidecar = index.get((record_kind, record_id))
    if sidecar is None:
        return f"missing sidecar {record_kind}:{record_id}"
    payload = sidecar.get("payload")
    if not isinstance(payload, Mapping):
        return f"sidecar {record_kind}:{record_id} lacks payload"
    digest = str(sidecar.get("payload_digest", ""))
    if digest and digest != canonical_digest(payload):
        return f"sidecar digest mismatch for {record_kind}:{record_id}"
    if embedded_payload is not None and canonical_digest(embedded_payload) != canonical_digest(payload):
        return f"sidecar payload diverges from frame payload for {record_kind}:{record_id}"
    return None


def evaluate_projection_invariant_boundary_completion(
    frames: Sequence[ProjectionFrame],
    sidecar_records: Sequence[Mapping[str, Any]],
) -> CompletionReport:
    sidecar_index = _sidecar_index(sidecar_records)
    reasons_by_check: dict[str, list[str]] = {
        "frame_contract": [],
        "sidecar_readback": [],
        "frame_source_lineage": [],
        "projection_non_authority": [],
    }

    if not frames:
        reasons_by_check["frame_contract"].append("no projection frames were provided")

    for frame in frames:
        if frame.is_authority_state is not False:
            reasons_by_check["projection_non_authority"].append(f"{frame.frame_id}: projection frame became authority")
        m13 = _frame_m13_payload(frame)
        if not m13:
            reasons_by_check["frame_contract"].append(f"{frame.frame_id}: missing m13_projection_invariant_boundary_v1")
            continue
        manifest_id = str(m13.get("projection_loss_manifest_id", ""))
        embedded_manifest = frame.payload.get("projection_loss_manifest_v1")
        if not manifest_id or not isinstance(embedded_manifest, Mapping):
            reasons_by_check["frame_contract"].append(f"{frame.frame_id}: missing embedded projection loss manifest")
            continue
        reason = _check_sidecar_payload(
            index=sidecar_index,
            record_kind="projection_loss_manifest_v1",
            record_id=manifest_id,
            embedded_payload=embedded_manifest,
        )
        if reason:
            reasons_by_check["sidecar_readback"].append(f"{frame.frame_id}: {reason}")
            continue
        try:
            visible_count = len(frame.samples) + len(embedded_manifest.get("preserved_invariants", []))
            validate_projection_loss_manifest_payload(embedded_manifest, visible_structure_count=visible_count)
        except Exception as exc:  # noqa: BLE001
            reasons_by_check["frame_contract"].append(f"{frame.frame_id}: {exc}")

        frame_sources = set(map(str, frame.source_record_ids))
        auxiliary_payload_sources = {
            *map(str, frame.payload.get("source_record_ids", [])),
            *map(str, frame.payload.get("event_timeline", {}).get("source_record_ids", [])),
        }
        missing_authority = set(map(str, embedded_manifest.get("authority_record_ids", []))) - frame_sources
        if missing_authority:
            reasons_by_check["frame_source_lineage"].append(
                f"{frame.frame_id}: authority ids missing from top-level frame sources: {sorted(missing_authority)}"
            )
        payload_only_authority = set(map(str, embedded_manifest.get("authority_record_ids", []))) & auxiliary_payload_sources - frame_sources
        if payload_only_authority:
            reasons_by_check["frame_source_lineage"].append(
                f"{frame.frame_id}: authority ids appear only in payload/timeline, not top-level sources: {sorted(payload_only_authority)}"
            )

        embedded_by_id: dict[str, Mapping[str, Any]] = {}
        for payload in frame.payload.get("invariant_signatures_v1", []):
            if isinstance(payload, Mapping) and payload.get("signature_id"):
                embedded_by_id[str(payload["signature_id"])] = payload
        for signature_ref in embedded_manifest.get("preserved_invariants", []):
            if not isinstance(signature_ref, Mapping):
                reasons_by_check["frame_contract"].append(f"{frame.frame_id}: preserved invariant is not a record payload")
                continue
            signature_id = str(signature_ref.get("signature_id") or signature_ref.get("record_id") or "")
            if not signature_id:
                reasons_by_check["frame_contract"].append(f"{frame.frame_id}: preserved invariant missing signature_id")
                continue
            embedded_signature = embedded_by_id.get(signature_id)
            reason = _check_sidecar_payload(
                index=sidecar_index,
                record_kind="invariant_signature_v1",
                record_id=signature_id,
                embedded_payload=embedded_signature,
            )
            if reason:
                reasons_by_check["sidecar_readback"].append(f"{frame.frame_id}: {reason}")
            sidecar = sidecar_index.get(("invariant_signature_v1", signature_id), {})
            payload = sidecar.get("payload", {}) if isinstance(sidecar.get("payload"), Mapping) else {}
            missing_sources = set(map(str, payload.get("source_authority_record_ids", []))) - frame_sources
            if missing_sources:
                reasons_by_check["frame_source_lineage"].append(
                    f"{frame.frame_id}: invariant authority ids missing from frame sources: {sorted(missing_sources)}"
                )

        for kind, id_key, payload_key in (
            ("boundary_crossing_record_v1", "boundary_crossing_ids", "boundary_crossing_records_v1"),
            ("phase_transition_record_v1", "phase_transition_ids", "phase_transition_records_v1"),
            ("genesis_rule_evidence_v1", "genesis_rule_evidence_ids", "genesis_rule_evidence_v1"),
        ):
            embedded_records = {
                _record_id_for_kind(kind, item): item
                for item in frame.payload.get(payload_key, [])
                if isinstance(item, Mapping)
            }
            for record_id in map(str, m13.get(id_key, [])):
                reason = _check_sidecar_payload(
                    index=sidecar_index,
                    record_kind=kind,
                    record_id=record_id,
                    embedded_payload=embedded_records.get(record_id),
                )
                if reason:
                    reasons_by_check["sidecar_readback"].append(f"{frame.frame_id}: {reason}")

    checks = [
        CompletionCheck(
            name=name,
            status="passed" if not reasons else "failed",
            details={"reasons": reasons},
        )
        for name, reasons in reasons_by_check.items()
    ]
    return CompletionReport(
        overall_status="passed" if all(check.status == "passed" for check in checks) else "failed",
        checks=checks,
        summary={
            "frame_count": len(frames),
            "sidecar_record_count": len(sidecar_records),
            "schema": M13_SCHEMA_VERSION,
        },
        audit={
            "completion_source": "read_back_projection_frames_and_sidecar_records",
            "viewer_is_not_authority": True,
        },
    )
