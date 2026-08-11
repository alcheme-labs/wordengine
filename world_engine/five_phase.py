from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


JsonDict = dict[str, Any]

FIVE_PHASE_NAMES = ("contractive", "generative", "transport", "radiant", "substrate")

EPS = 1e-9
THETA_MASS = 0.12
MASS_GATE_WIDTH = 0.04
CARRYING_CAPACITY = 1.0
DEFAULT_DT = 0.08
MAX_DELTA_PER_TICK = 0.12
MASS_BUDGET_ABS = 0.03
ENERGY_BUDGET_ABS = 0.05
PHASE_PREDICTIVENESS_MIN_IMPROVEMENT = 0.10
SIMPLIFICATION_MIN_ADVANTAGE = 0.05
SIMPLIFICATION_MIN_CASES = 4

FORBIDDEN_AUTHORITY_SHORTCUT_KEYS = {
    "viewer_color",
    "css_color",
    "mesh",
    "texture",
    "object_asset_id",
    "material_label",
}


def _tuple_str(values: Sequence[Any] | None) -> tuple[str, ...]:
    return tuple(str(value) for value in values or ())


def _list_int(values: Sequence[Any] | None) -> tuple[int, ...]:
    return tuple(int(value) for value in values or ())


def _to_json(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, tuple):
        return [_to_json(item) for item in value]
    if isinstance(value, list):
        return [_to_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_json(item) for key, item in value.items()}
    return value


def stable_digest(value: Any) -> str:
    encoded = json.dumps(_to_json(value), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def stable_record_id(prefix: str, value: Any) -> str:
    return f"{prefix}::{stable_digest(value).split(':', 1)[1][:16]}"


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def sigmoid(value: float) -> float:
    if value >= 40.0:
        return 1.0
    if value <= -40.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-value))


def reject_authority_shortcuts(value: Any, *, path: str = "record") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_AUTHORITY_SHORTCUT_KEYS:
                raise ValueError(f"FivePhase records cannot use authority shortcut key {path}.{key_text}.")
            reject_authority_shortcuts(item, path=f"{path}.{key_text}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            reject_authority_shortcuts(item, path=f"{path}[{index}]")


def _finite_nonnegative(value: float, *, name: str) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite.")
    if value < 0.0:
        raise ValueError(f"{name} must be non-negative.")
    return value


def _finite(value: float, *, name: str) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite.")
    return value


@dataclass(frozen=True)
class FivePhaseVector:
    contractive: float
    generative: float
    transport: float
    radiant: float
    substrate: float

    def __post_init__(self) -> None:
        validate_phase_vector(self)

    def to_dict(self) -> dict[str, float]:
        return {
            "contractive": float(self.contractive),
            "generative": float(self.generative),
            "transport": float(self.transport),
            "radiant": float(self.radiant),
            "substrate": float(self.substrate),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FivePhaseVector":
        if tuple(data.keys()) != FIVE_PHASE_NAMES:
            if set(data.keys()) != set(FIVE_PHASE_NAMES):
                raise ValueError(f"FivePhaseVector keys must be exactly {FIVE_PHASE_NAMES}.")
            ordered = {name: data[name] for name in FIVE_PHASE_NAMES}
        else:
            ordered = dict(data)
        return cls(**{name: _finite_nonnegative(float(ordered[name]), name=name) for name in FIVE_PHASE_NAMES})

    def dominant_phase(self) -> str:
        values = self.to_dict()
        best_value = max(values.values())
        for name in FIVE_PHASE_NAMES:
            if values[name] == best_value:
                return name
        return FIVE_PHASE_NAMES[0]

    def normalized(self) -> "FivePhaseVector":
        values = self.to_dict()
        total = sum(values.values())
        if total <= 0.0:
            raise ValueError("FivePhaseVector cannot normalize a zero vector.")
        return FivePhaseVector(**{name: values[name] / total for name in FIVE_PHASE_NAMES})

    def l2_distance(self, other: "FivePhaseVector") -> float:
        left = self.to_dict()
        right = other.to_dict()
        return math.sqrt(sum((left[name] - right[name]) ** 2 for name in FIVE_PHASE_NAMES))

    def scaled_difference(self, target: "FivePhaseVector", scale: float) -> "FivePhaseVector":
        current = self.to_dict()
        target_values = target.to_dict()
        return FivePhaseVector(
            **{
                name: max(0.0, scale * (target_values[name] - current[name]))
                for name in FIVE_PHASE_NAMES
            }
        )


def validate_phase_vector(vector: FivePhaseVector) -> None:
    for name, value in vector.to_dict().items():
        _finite_nonnegative(value, name=name)


def _phase_from_payload(value: Mapping[str, Any] | FivePhaseVector) -> FivePhaseVector:
    if isinstance(value, FivePhaseVector):
        return value
    return FivePhaseVector.from_dict(value)


def normalize_phase_weights(values: Mapping[str, float]) -> FivePhaseVector:
    raw = {name: _finite_nonnegative(float(values[name]), name=name) for name in FIVE_PHASE_NAMES}
    total = sum(raw.values())
    if total <= 0.0:
        raise ValueError("phase weights cannot sum to zero.")
    return FivePhaseVector(**{name: raw[name] / total for name in FIVE_PHASE_NAMES})


def _require_non_empty_text(value: Any, *, name: str) -> str:
    text = str(value)
    if not text:
        raise ValueError(f"{name} must be non-empty.")
    return text


def _require_sources(values: Sequence[Any] | None, *, name: str = "source_record_ids") -> tuple[str, ...]:
    sources = _tuple_str(values)
    if not sources:
        raise ValueError(f"{name} must be non-empty.")
    if any(not source for source in sources):
        raise ValueError(f"{name} cannot contain empty ids.")
    return tuple(dict.fromkeys(sources))


@dataclass(frozen=True)
class FivePhaseFieldRecord:
    record_id: str
    schema: str
    tick: int
    source_field_state_id: str
    grid_shape: Sequence[int]
    aggregate_phase: FivePhaseVector
    cell_phase_vectors: Sequence[Sequence[FivePhaseVector | Mapping[str, Any]]]
    metrics: Mapping[str, Any]
    source_record_ids: Sequence[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        _require_non_empty_text(self.record_id, name="record_id")
        _require_non_empty_text(self.schema, name="schema")
        _require_non_empty_text(self.source_field_state_id, name="source_field_state_id")
        if self.is_authority_state:
            raise ValueError("FivePhaseFieldRecord is a read-back derivative, not authority state.")
        _require_sources(self.source_record_ids)
        if self.source_field_state_id not in self.source_record_ids:
            raise ValueError("FivePhaseFieldRecord must cite source_field_state_id.")
        reject_authority_shortcuts(self.metrics, path="metrics")
        validate_phase_vector(self.aggregate_phase)

    def _cell_dicts(self) -> list[list[dict[str, float]]]:
        return [
            [_phase_from_payload(cell).to_dict() for cell in row]
            for row in self.cell_phase_vectors
        ]

    def to_dict(self) -> JsonDict:
        return {
            "record_id": self.record_id,
            "schema": self.schema,
            "tick": int(self.tick),
            "source_field_state_id": self.source_field_state_id,
            "grid_shape": list(_list_int(self.grid_shape)),
            "aggregate_phase": self.aggregate_phase.to_dict(),
            "cell_phase_vectors": self._cell_dicts(),
            "metrics": _to_json(dict(self.metrics)),
            "source_record_ids": list(_require_sources(self.source_record_ids)),
            "is_authority_state": bool(self.is_authority_state),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FivePhaseFieldRecord":
        return cls(
            record_id=str(data["record_id"]),
            schema=str(data["schema"]),
            tick=int(data["tick"]),
            source_field_state_id=str(data["source_field_state_id"]),
            grid_shape=tuple(int(value) for value in data["grid_shape"]),
            aggregate_phase=FivePhaseVector.from_dict(data["aggregate_phase"]),
            cell_phase_vectors=tuple(
                tuple(FivePhaseVector.from_dict(cell) for cell in row)
                for row in data.get("cell_phase_vectors", [])
            ),
            metrics=dict(data.get("metrics", {})),
            source_record_ids=_tuple_str(data.get("source_record_ids", [])),
            is_authority_state=bool(data.get("is_authority_state", False)),
        )


@dataclass(frozen=True)
class FivePhaseConstraintSetRecord:
    record_id: str
    schema: str
    tick: int
    phase_field_id: str
    payload: Mapping[str, Any]
    source_record_ids: Sequence[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        _require_non_empty_text(self.record_id, name="record_id")
        _require_non_empty_text(self.schema, name="schema")
        _require_non_empty_text(self.phase_field_id, name="phase_field_id")
        if self.is_authority_state:
            raise ValueError("FivePhaseConstraintSetRecord is not authority state.")
        _require_sources(self.source_record_ids)
        if self.phase_field_id not in self.source_record_ids:
            raise ValueError("FivePhaseConstraintSetRecord must cite phase_field_id.")
        reject_authority_shortcuts(self.payload, path="payload")

    def to_dict(self) -> JsonDict:
        return {
            "record_id": self.record_id,
            "schema": self.schema,
            "tick": int(self.tick),
            "phase_field_id": self.phase_field_id,
            "payload": _to_json(dict(self.payload)),
            "source_record_ids": list(_require_sources(self.source_record_ids)),
            "is_authority_state": bool(self.is_authority_state),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FivePhaseConstraintSetRecord":
        return cls(
            record_id=str(data["record_id"]),
            schema=str(data["schema"]),
            tick=int(data["tick"]),
            phase_field_id=str(data["phase_field_id"]),
            payload=dict(data.get("payload", {})),
            source_record_ids=_tuple_str(data.get("source_record_ids", [])),
            is_authority_state=bool(data.get("is_authority_state", False)),
        )


@dataclass(frozen=True)
class FivePhasePatternRecord:
    record_id: str
    schema: str
    tick: int
    phase_field_id: str
    constraint_set_id: str | None
    support_bounds_grid: Sequence[int]
    centroid_grid: Sequence[float]
    phase_vector: FivePhaseVector
    dominant_phase: str
    stability_score: float
    continuity_score: float
    invariant_signature: str
    setpoint: FivePhaseVector | None
    source_record_ids: Sequence[str]
    payload: Mapping[str, Any] = field(default_factory=dict)
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        _require_non_empty_text(self.record_id, name="record_id")
        _require_non_empty_text(self.schema, name="schema")
        _require_non_empty_text(self.phase_field_id, name="phase_field_id")
        _require_non_empty_text(self.invariant_signature, name="invariant_signature")
        if self.is_authority_state:
            raise ValueError("FivePhasePatternRecord is non-authority read-back evidence.")
        if self.dominant_phase not in FIVE_PHASE_NAMES:
            raise ValueError("dominant_phase must be a fixed FivePhase name.")
        _require_sources(self.source_record_ids)
        if self.phase_field_id not in self.source_record_ids:
            raise ValueError("FivePhasePatternRecord must cite phase_field_id.")
        validate_phase_vector(self.phase_vector)
        if self.setpoint is not None:
            validate_phase_vector(self.setpoint)
        reject_authority_shortcuts(self.payload, path="payload")

    def to_dict(self) -> JsonDict:
        return {
            "record_id": self.record_id,
            "schema": self.schema,
            "tick": int(self.tick),
            "phase_field_id": self.phase_field_id,
            "constraint_set_id": self.constraint_set_id,
            "support_bounds_grid": [int(value) for value in self.support_bounds_grid],
            "centroid_grid": [float(value) for value in self.centroid_grid],
            "phase_vector": self.phase_vector.to_dict(),
            "dominant_phase": self.dominant_phase,
            "stability_score": float(self.stability_score),
            "continuity_score": float(self.continuity_score),
            "invariant_signature": self.invariant_signature,
            "setpoint": self.setpoint.to_dict() if self.setpoint else None,
            "source_record_ids": list(_require_sources(self.source_record_ids)),
            "payload": _to_json(dict(self.payload)),
            "is_authority_state": bool(self.is_authority_state),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FivePhasePatternRecord":
        setpoint = data.get("setpoint")
        return cls(
            record_id=str(data["record_id"]),
            schema=str(data["schema"]),
            tick=int(data["tick"]),
            phase_field_id=str(data["phase_field_id"]),
            constraint_set_id=data.get("constraint_set_id"),
            support_bounds_grid=tuple(int(value) for value in data["support_bounds_grid"]),
            centroid_grid=tuple(float(value) for value in data["centroid_grid"]),
            phase_vector=FivePhaseVector.from_dict(data["phase_vector"]),
            dominant_phase=str(data["dominant_phase"]),
            stability_score=float(data["stability_score"]),
            continuity_score=float(data["continuity_score"]),
            invariant_signature=str(data["invariant_signature"]),
            setpoint=FivePhaseVector.from_dict(setpoint) if setpoint else None,
            source_record_ids=_tuple_str(data.get("source_record_ids", [])),
            payload=dict(data.get("payload", {})),
            is_authority_state=bool(data.get("is_authority_state", False)),
        )


@dataclass(frozen=True)
class FivePhaseTraceRecord:
    record_id: str
    schema: str
    tick: int
    observer_id: str
    pattern_id: str
    phase_field_id: str
    frequency_window: Mapping[str, Any]
    phase_response: FivePhaseVector
    trace_intensity: float
    projection_loss_manifest: Mapping[str, Any]
    source_record_ids: Sequence[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        _require_non_empty_text(self.record_id, name="record_id")
        _require_non_empty_text(self.schema, name="schema")
        _require_non_empty_text(self.observer_id, name="observer_id")
        _require_non_empty_text(self.pattern_id, name="pattern_id")
        _require_non_empty_text(self.phase_field_id, name="phase_field_id")
        if self.is_authority_state:
            raise ValueError("FivePhaseTraceRecord is observer projection, not authority state.")
        _require_sources(self.source_record_ids)
        if self.pattern_id not in self.source_record_ids or self.phase_field_id not in self.source_record_ids:
            raise ValueError("FivePhaseTraceRecord must cite pattern_id and phase_field_id.")
        validate_phase_vector(self.phase_response)
        _finite_nonnegative(self.trace_intensity, name="trace_intensity")
        reject_authority_shortcuts(self.frequency_window, path="frequency_window")
        reject_authority_shortcuts(self.projection_loss_manifest, path="projection_loss_manifest")

    def to_dict(self) -> JsonDict:
        return {
            "record_id": self.record_id,
            "schema": self.schema,
            "tick": int(self.tick),
            "observer_id": self.observer_id,
            "pattern_id": self.pattern_id,
            "phase_field_id": self.phase_field_id,
            "frequency_window": _to_json(dict(self.frequency_window)),
            "phase_response": self.phase_response.to_dict(),
            "trace_intensity": float(self.trace_intensity),
            "projection_loss_manifest": _to_json(dict(self.projection_loss_manifest)),
            "source_record_ids": list(_require_sources(self.source_record_ids)),
            "is_authority_state": bool(self.is_authority_state),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FivePhaseTraceRecord":
        return cls(
            record_id=str(data["record_id"]),
            schema=str(data["schema"]),
            tick=int(data["tick"]),
            observer_id=str(data["observer_id"]),
            pattern_id=str(data["pattern_id"]),
            phase_field_id=str(data["phase_field_id"]),
            frequency_window=dict(data.get("frequency_window", {})),
            phase_response=FivePhaseVector.from_dict(data["phase_response"]),
            trace_intensity=float(data["trace_intensity"]),
            projection_loss_manifest=dict(data.get("projection_loss_manifest", {})),
            source_record_ids=_tuple_str(data.get("source_record_ids", [])),
            is_authority_state=bool(data.get("is_authority_state", False)),
        )


@dataclass(frozen=True)
class FivePhaseResidualConstraintRecord:
    record_id: str
    schema: str
    tick: int
    trace_id: str
    pattern_id: str
    phase_field_id: str
    memory_next: float
    residual_phase_bias: FivePhaseVector
    strength: float
    decay: float
    source_record_ids: Sequence[str]
    is_authority_state: bool = False

    def __post_init__(self) -> None:
        _require_non_empty_text(self.record_id, name="record_id")
        _require_non_empty_text(self.schema, name="schema")
        _require_non_empty_text(self.trace_id, name="trace_id")
        _require_non_empty_text(self.pattern_id, name="pattern_id")
        _require_non_empty_text(self.phase_field_id, name="phase_field_id")
        if self.is_authority_state:
            raise ValueError("FivePhaseResidualConstraintRecord is not authority state.")
        _require_sources(self.source_record_ids)
        if (
            self.trace_id not in self.source_record_ids
            or self.pattern_id not in self.source_record_ids
            or self.phase_field_id not in self.source_record_ids
        ):
            raise ValueError("Residual constraints must cite trace_id, pattern_id, and phase_field_id.")
        _finite_nonnegative(self.memory_next, name="memory_next")
        _finite_nonnegative(self.strength, name="strength")
        _finite_nonnegative(self.decay, name="decay")
        validate_phase_vector(self.residual_phase_bias)

    def to_dict(self) -> JsonDict:
        return {
            "record_id": self.record_id,
            "schema": self.schema,
            "tick": int(self.tick),
            "trace_id": self.trace_id,
            "pattern_id": self.pattern_id,
            "phase_field_id": self.phase_field_id,
            "memory_next": float(self.memory_next),
            "residual_phase_bias": self.residual_phase_bias.to_dict(),
            "strength": float(self.strength),
            "decay": float(self.decay),
            "source_record_ids": list(_require_sources(self.source_record_ids)),
            "is_authority_state": bool(self.is_authority_state),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FivePhaseResidualConstraintRecord":
        return cls(
            record_id=str(data["record_id"]),
            schema=str(data["schema"]),
            tick=int(data["tick"]),
            trace_id=str(data["trace_id"]),
            pattern_id=str(data["pattern_id"]),
            phase_field_id=str(data["phase_field_id"]),
            memory_next=float(data["memory_next"]),
            residual_phase_bias=FivePhaseVector.from_dict(data["residual_phase_bias"]),
            strength=float(data["strength"]),
            decay=float(data["decay"]),
            source_record_ids=_tuple_str(data.get("source_record_ids", [])),
            is_authority_state=bool(data.get("is_authority_state", False)),
        )


@dataclass(frozen=True)
class FivePhaseAgentStateRecord:
    record_id: str
    schema: str
    tick: int
    pattern_id: str
    setpoint: FivePhaseVector
    boundary_pattern_id: str | None
    repair_policy: Mapping[str, Any]
    tolerance: float
    source_record_ids: Sequence[str]
    is_authority_state: bool = False
    trace_id: str | None = None
    residual_constraint_id: str | None = None
    support_energy_setpoint: float | None = None
    support_energy_current: float | None = None
    response_stability: float | None = None
    bridge_record_id: str | None = None
    source_state_id: str | None = None
    source_state_digest: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_text(self.record_id, name="record_id")
        _require_non_empty_text(self.schema, name="schema")
        _require_non_empty_text(self.pattern_id, name="pattern_id")
        if self.is_authority_state:
            raise ValueError("FivePhaseAgentStateRecord is a controller read-back state, not authority.")
        if self.schema == "five_phase_agent_state_v2":
            for name, value in (
                ("trace_id", self.trace_id),
                ("residual_constraint_id", self.residual_constraint_id),
                ("support_energy_setpoint", self.support_energy_setpoint),
                ("support_energy_current", self.support_energy_current),
                ("response_stability", self.response_stability),
                ("bridge_record_id", self.bridge_record_id),
                ("source_state_id", self.source_state_id),
                ("source_state_digest", self.source_state_digest),
            ):
                if value is None:
                    raise ValueError(f"five_phase_agent_state_v2 requires {name}.")
        sources = _require_sources(self.source_record_ids)
        if self.pattern_id not in self.source_record_ids:
            raise ValueError("FivePhaseAgentStateRecord must cite pattern_id.")
        for name, value in (
            ("trace_id", self.trace_id),
            ("residual_constraint_id", self.residual_constraint_id),
            ("bridge_record_id", self.bridge_record_id),
            ("source_state_id", self.source_state_id),
        ):
            if value is not None:
                _require_non_empty_text(value, name=name)
                if value not in sources:
                    raise ValueError(f"FivePhaseAgentStateRecord must cite {name}.")
        if self.source_state_digest is not None:
            _require_non_empty_text(self.source_state_digest, name="source_state_digest")
        for name, value in (
            ("support_energy_setpoint", self.support_energy_setpoint),
            ("support_energy_current", self.support_energy_current),
            ("response_stability", self.response_stability),
        ):
            if value is not None:
                _finite_nonnegative(value, name=name)
        if self.response_stability is not None and float(self.response_stability) > 1.0:
            raise ValueError("response_stability must be at most 1.0.")
        validate_phase_vector(self.setpoint)
        _finite_nonnegative(self.tolerance, name="tolerance")
        reject_authority_shortcuts(self.repair_policy, path="repair_policy")

    def to_dict(self) -> JsonDict:
        data = {
            "record_id": self.record_id,
            "schema": self.schema,
            "tick": int(self.tick),
            "pattern_id": self.pattern_id,
            "setpoint": self.setpoint.to_dict(),
            "boundary_pattern_id": self.boundary_pattern_id,
            "repair_policy": _to_json(dict(self.repair_policy)),
            "tolerance": float(self.tolerance),
            "source_record_ids": list(_require_sources(self.source_record_ids)),
            "is_authority_state": bool(self.is_authority_state),
        }
        if self.schema == "five_phase_agent_state_v2" or any(
            value is not None
            for value in (
                self.trace_id,
                self.residual_constraint_id,
                self.support_energy_setpoint,
                self.support_energy_current,
                self.response_stability,
                self.bridge_record_id,
                self.source_state_id,
                self.source_state_digest,
            )
        ):
            data.update(
                {
                    "trace_id": self.trace_id,
                    "residual_constraint_id": self.residual_constraint_id,
                    "support_energy_setpoint": self.support_energy_setpoint,
                    "support_energy_current": self.support_energy_current,
                    "response_stability": self.response_stability,
                    "bridge_record_id": self.bridge_record_id,
                    "source_state_id": self.source_state_id,
                    "source_state_digest": self.source_state_digest,
                }
            )
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FivePhaseAgentStateRecord":
        return cls(
            record_id=str(data["record_id"]),
            schema=str(data["schema"]),
            tick=int(data["tick"]),
            pattern_id=str(data["pattern_id"]),
            setpoint=FivePhaseVector.from_dict(data["setpoint"]),
            boundary_pattern_id=data.get("boundary_pattern_id"),
            repair_policy=dict(data.get("repair_policy", {})),
            tolerance=float(data["tolerance"]),
            source_record_ids=_tuple_str(data.get("source_record_ids", [])),
            is_authority_state=bool(data.get("is_authority_state", False)),
            trace_id=str(data["trace_id"]) if data.get("trace_id") is not None else None,
            residual_constraint_id=str(data["residual_constraint_id"])
            if data.get("residual_constraint_id") is not None
            else None,
            support_energy_setpoint=float(data["support_energy_setpoint"])
            if data.get("support_energy_setpoint") is not None
            else None,
            support_energy_current=float(data["support_energy_current"])
            if data.get("support_energy_current") is not None
            else None,
            response_stability=float(data["response_stability"])
            if data.get("response_stability") is not None
            else None,
            bridge_record_id=str(data["bridge_record_id"]) if data.get("bridge_record_id") is not None else None,
            source_state_id=str(data["source_state_id"]) if data.get("source_state_id") is not None else None,
            source_state_digest=str(data["source_state_digest"])
            if data.get("source_state_digest") is not None
            else None,
        )


@dataclass(frozen=True)
class FivePhaseFeedbackRecord:
    record_id: str
    schema: str
    tick: int
    agent_state_id: str
    pattern_id: str
    phase_l2_distance_before: float
    repair_gate: float
    phase_bias: FivePhaseVector
    expected_distance_reduction: float
    source_record_ids: Sequence[str]
    is_authority_state: bool = False
    trace_id: str | None = None
    residual_constraint_id: str | None = None
    bridge_record_id: str | None = None
    source_state_id: str | None = None
    source_state_digest: str | None = None
    target_basis_id: str | None = None
    signed_error: float | None = None
    sensitivity: float | None = None
    eta: float | None = None
    gain: float | None = None
    candidate_projection: Mapping[str, Any] | None = None
    candidate_projection_digest: str | None = None
    predecessor_causal_step_id: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_text(self.record_id, name="record_id")
        _require_non_empty_text(self.schema, name="schema")
        _require_non_empty_text(self.agent_state_id, name="agent_state_id")
        _require_non_empty_text(self.pattern_id, name="pattern_id")
        if self.is_authority_state:
            raise ValueError("FivePhaseFeedbackRecord is not authority state.")
        if self.schema == "five_phase_feedback_v2":
            for name, value in (
                ("trace_id", self.trace_id),
                ("residual_constraint_id", self.residual_constraint_id),
                ("bridge_record_id", self.bridge_record_id),
                ("source_state_id", self.source_state_id),
                ("source_state_digest", self.source_state_digest),
                ("target_basis_id", self.target_basis_id),
                ("signed_error", self.signed_error),
                ("sensitivity", self.sensitivity),
                ("eta", self.eta),
                ("gain", self.gain),
                ("candidate_projection", self.candidate_projection),
                ("candidate_projection_digest", self.candidate_projection_digest),
                ("predecessor_causal_step_id", self.predecessor_causal_step_id),
            ):
                if value is None:
                    raise ValueError(f"five_phase_feedback_v2 requires {name}.")
        sources = _require_sources(self.source_record_ids)
        if self.agent_state_id not in self.source_record_ids or self.pattern_id not in self.source_record_ids:
            raise ValueError("FivePhaseFeedbackRecord must cite agent_state_id and pattern_id.")
        for name, value in (
            ("trace_id", self.trace_id),
            ("residual_constraint_id", self.residual_constraint_id),
            ("bridge_record_id", self.bridge_record_id),
            ("source_state_id", self.source_state_id),
            ("target_basis_id", self.target_basis_id),
            ("predecessor_causal_step_id", self.predecessor_causal_step_id),
        ):
            if value is not None:
                _require_non_empty_text(value, name=name)
                if value not in sources:
                    raise ValueError(f"FivePhaseFeedbackRecord must cite {name}.")
        if self.source_state_digest is not None:
            _require_non_empty_text(self.source_state_digest, name="source_state_digest")
        for name, value in (("signed_error", self.signed_error), ("sensitivity", self.sensitivity)):
            if value is not None:
                _finite(value, name=name)
        if self.eta is not None:
            if _finite_nonnegative(self.eta, name="eta") <= 0.0:
                raise ValueError("eta must be positive.")
        if self.gain is not None:
            _finite_nonnegative(self.gain, name="gain")
        if (self.candidate_projection is None) != (self.candidate_projection_digest is None):
            raise ValueError("candidate_projection and candidate_projection_digest must be supplied together.")
        if self.candidate_projection is not None:
            reject_authority_shortcuts(self.candidate_projection, path="candidate_projection")
            for basis_id, channels in self.candidate_projection.items():
                _require_non_empty_text(basis_id, name="candidate_projection basis_id")
                if not isinstance(channels, Mapping):
                    raise ValueError("candidate_projection channels must be a mapping.")
                for channel, value in channels.items():
                    _require_non_empty_text(channel, name="candidate_projection channel")
                    _finite(value, name="candidate_projection value")
            if self.candidate_projection_digest != stable_digest(self.candidate_projection):
                raise ValueError("candidate_projection_digest mismatch.")
            if self.target_basis_id is not None:
                if set(self.candidate_projection) != {self.target_basis_id}:
                    raise ValueError("candidate_projection must target only target_basis_id.")
                target_channels = self.candidate_projection[self.target_basis_id]
                if "density" not in target_channels:
                    raise ValueError("candidate_projection target must carry density.")
                density_delta = _finite(target_channels["density"], name="candidate_projection density")
                if self.signed_error is not None and self.sensitivity is not None:
                    if density_delta * float(self.signed_error) * float(self.sensitivity) <= 0.0:
                        raise ValueError("candidate_projection has the wrong signed direction.")
                if self.gain is not None and abs(density_delta) > float(self.gain) + EPS:
                    raise ValueError("candidate_projection density exceeds gain.")
        _finite_nonnegative(self.phase_l2_distance_before, name="phase_l2_distance_before")
        _finite_nonnegative(self.repair_gate, name="repair_gate")
        _finite_nonnegative(self.expected_distance_reduction, name="expected_distance_reduction")
        validate_phase_vector(self.phase_bias)

    def to_dict(self) -> JsonDict:
        data = {
            "record_id": self.record_id,
            "schema": self.schema,
            "tick": int(self.tick),
            "agent_state_id": self.agent_state_id,
            "pattern_id": self.pattern_id,
            "phase_l2_distance_before": float(self.phase_l2_distance_before),
            "repair_gate": float(self.repair_gate),
            "phase_bias": self.phase_bias.to_dict(),
            "expected_distance_reduction": float(self.expected_distance_reduction),
            "source_record_ids": list(_require_sources(self.source_record_ids)),
            "is_authority_state": bool(self.is_authority_state),
        }
        if self.schema == "five_phase_feedback_v2" or any(
            value is not None
            for value in (
                self.trace_id,
                self.residual_constraint_id,
                self.bridge_record_id,
                self.source_state_id,
                self.source_state_digest,
                self.target_basis_id,
                self.signed_error,
                self.sensitivity,
                self.eta,
                self.gain,
                self.candidate_projection,
                self.candidate_projection_digest,
                self.predecessor_causal_step_id,
            )
        ):
            data.update(
                {
                    "trace_id": self.trace_id,
                    "residual_constraint_id": self.residual_constraint_id,
                    "bridge_record_id": self.bridge_record_id,
                    "source_state_id": self.source_state_id,
                    "source_state_digest": self.source_state_digest,
                    "target_basis_id": self.target_basis_id,
                    "signed_error": self.signed_error,
                    "sensitivity": self.sensitivity,
                    "eta": self.eta,
                    "gain": self.gain,
                    "candidate_projection": _to_json(dict(self.candidate_projection))
                    if self.candidate_projection is not None
                    else None,
                    "candidate_projection_digest": self.candidate_projection_digest,
                    "predecessor_causal_step_id": self.predecessor_causal_step_id,
                }
            )
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FivePhaseFeedbackRecord":
        return cls(
            record_id=str(data["record_id"]),
            schema=str(data["schema"]),
            tick=int(data["tick"]),
            agent_state_id=str(data["agent_state_id"]),
            pattern_id=str(data["pattern_id"]),
            phase_l2_distance_before=float(data["phase_l2_distance_before"]),
            repair_gate=float(data["repair_gate"]),
            phase_bias=FivePhaseVector.from_dict(data["phase_bias"]),
            expected_distance_reduction=float(data["expected_distance_reduction"]),
            source_record_ids=_tuple_str(data.get("source_record_ids", [])),
            is_authority_state=bool(data.get("is_authority_state", False)),
            trace_id=str(data["trace_id"]) if data.get("trace_id") is not None else None,
            residual_constraint_id=str(data["residual_constraint_id"])
            if data.get("residual_constraint_id") is not None
            else None,
            bridge_record_id=str(data["bridge_record_id"]) if data.get("bridge_record_id") is not None else None,
            source_state_id=str(data["source_state_id"]) if data.get("source_state_id") is not None else None,
            source_state_digest=str(data["source_state_digest"])
            if data.get("source_state_digest") is not None
            else None,
            target_basis_id=str(data["target_basis_id"]) if data.get("target_basis_id") is not None else None,
            signed_error=float(data["signed_error"]) if data.get("signed_error") is not None else None,
            sensitivity=float(data["sensitivity"]) if data.get("sensitivity") is not None else None,
            eta=float(data["eta"]) if data.get("eta") is not None else None,
            gain=float(data["gain"]) if data.get("gain") is not None else None,
            candidate_projection=dict(data["candidate_projection"])
            if data.get("candidate_projection") is not None
            else None,
            candidate_projection_digest=str(data["candidate_projection_digest"])
            if data.get("candidate_projection_digest") is not None
            else None,
            predecessor_causal_step_id=str(data["predecessor_causal_step_id"])
            if data.get("predecessor_causal_step_id") is not None
            else None,
        )
