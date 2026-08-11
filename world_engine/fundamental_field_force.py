from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


GRAVITY_RULE_ID = "effective-gravity-rule::inverse-square-softened-v1"
DEFAULT_G_EFF = 0.0006
DEFAULT_SOFTENING_WORLD = 0.8
DEFAULT_DT = 1.0
MAX_ORBIT_ENERGY_ERROR_RELATIVE = 0.20
MAX_ORBIT_ANGULAR_MOMENTUM_ERROR_RELATIVE = 0.20


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _vec3(values: Sequence[Any]) -> tuple[float, float, float]:
    if len(values) != 3:
        raise ValueError("vector must have length 3")
    parsed = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in parsed):
        raise ValueError("vector values must be finite")
    return parsed  # type: ignore[return-value]


def _tuple_str(values: Sequence[Any]) -> tuple[str, ...]:
    return tuple(str(value) for value in values)


def _vec_sub(left: Sequence[float], right: Sequence[float]) -> tuple[float, float, float]:
    return tuple(float(left[index]) - float(right[index]) for index in range(3))  # type: ignore[return-value]


def _vec_add(left: Sequence[float], right: Sequence[float]) -> tuple[float, float, float]:
    return tuple(float(left[index]) + float(right[index]) for index in range(3))  # type: ignore[return-value]


def _vec_scale(vector: Sequence[float], value: float) -> tuple[float, float, float]:
    return tuple(float(item) * float(value) for item in vector)  # type: ignore[return-value]


def _vec_dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(float(left[index]) * float(right[index]) for index in range(3))


def _vec_cross(left: Sequence[float], right: Sequence[float]) -> tuple[float, float, float]:
    return (
        float(left[1]) * float(right[2]) - float(left[2]) * float(right[1]),
        float(left[2]) * float(right[0]) - float(left[0]) * float(right[2]),
        float(left[0]) * float(right[1]) - float(left[1]) * float(right[0]),
    )


def _vec_length(vector: Sequence[float]) -> float:
    return math.sqrt(_vec_dot(vector, vector))


@dataclass(frozen=True)
class MacroCelestialBodyStateRecord:
    record_id: str
    schema: str
    tick: int
    body_id: str
    body_kind: str
    center_world: tuple[float, float, float]
    velocity_world_per_tick: tuple[float, float, float]
    effective_mass_energy: float
    radius_world: float
    source_macro_authority_ids: tuple[str, ...]
    source_record_ids: tuple[str, ...]
    is_authority_state: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "schema": self.schema,
            "tick": self.tick,
            "body_id": self.body_id,
            "body_kind": self.body_kind,
            "center_world": list(self.center_world),
            "velocity_world_per_tick": list(self.velocity_world_per_tick),
            "effective_mass_energy": self.effective_mass_energy,
            "radius_world": self.radius_world,
            "source_macro_authority_ids": list(self.source_macro_authority_ids),
            "source_record_ids": list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MacroCelestialBodyStateRecord":
        return cls(
            record_id=str(data["record_id"]),
            schema=str(data["schema"]),
            tick=int(data["tick"]),
            body_id=str(data["body_id"]),
            body_kind=str(data["body_kind"]),
            center_world=_vec3(data["center_world"]),
            velocity_world_per_tick=_vec3(data["velocity_world_per_tick"]),
            effective_mass_energy=float(data["effective_mass_energy"]),
            radius_world=float(data["radius_world"]),
            source_macro_authority_ids=_tuple_str(data.get("source_macro_authority_ids", [])),
            source_record_ids=_tuple_str(data.get("source_record_ids", [])),
            is_authority_state=bool(data.get("is_authority_state", True)),
        )


@dataclass(frozen=True)
class EffectiveGravityPotentialRecord:
    record_id: str
    schema: str
    tick: int
    rule_id: str
    gravitational_constant_eff: float
    softening_world: float
    source_body_state_ids: tuple[str, ...]
    potential_by_body_id: Mapping[str, float]
    acceleration_by_body_id: Mapping[str, tuple[float, float, float]]
    source_record_ids: tuple[str, ...]
    is_authority_state: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "schema": self.schema,
            "tick": self.tick,
            "rule_id": self.rule_id,
            "gravitational_constant_eff": self.gravitational_constant_eff,
            "softening_world": self.softening_world,
            "source_body_state_ids": list(self.source_body_state_ids),
            "potential_by_body_id": dict(self.potential_by_body_id),
            "acceleration_by_body_id": {key: list(value) for key, value in self.acceleration_by_body_id.items()},
            "source_record_ids": list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EffectiveGravityPotentialRecord":
        return cls(
            record_id=str(data["record_id"]),
            schema=str(data["schema"]),
            tick=int(data["tick"]),
            rule_id=str(data["rule_id"]),
            gravitational_constant_eff=float(data["gravitational_constant_eff"]),
            softening_world=float(data["softening_world"]),
            source_body_state_ids=_tuple_str(data.get("source_body_state_ids", [])),
            potential_by_body_id={str(key): float(value) for key, value in dict(data.get("potential_by_body_id", {})).items()},
            acceleration_by_body_id={str(key): _vec3(value) for key, value in dict(data.get("acceleration_by_body_id", {})).items()},
            source_record_ids=_tuple_str(data.get("source_record_ids", [])),
            is_authority_state=bool(data.get("is_authority_state", True)),
        )


@dataclass(frozen=True)
class MacroBodyStepRecord:
    record_id: str
    schema: str
    tick: int
    previous_tick: int
    dt: float
    rule_id: str
    previous_body_state_ids: tuple[str, ...]
    result_body_state_ids: tuple[str, ...]
    gravity_potential_record_id: str
    energy_error_relative: float
    angular_momentum_error_relative: float
    source_record_ids: tuple[str, ...]
    is_authority_state: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "schema": self.schema,
            "tick": self.tick,
            "previous_tick": self.previous_tick,
            "dt": self.dt,
            "rule_id": self.rule_id,
            "previous_body_state_ids": list(self.previous_body_state_ids),
            "result_body_state_ids": list(self.result_body_state_ids),
            "gravity_potential_record_id": self.gravity_potential_record_id,
            "energy_error_relative": self.energy_error_relative,
            "angular_momentum_error_relative": self.angular_momentum_error_relative,
            "source_record_ids": list(self.source_record_ids),
            "is_authority_state": self.is_authority_state,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MacroBodyStepRecord":
        return cls(
            record_id=str(data["record_id"]),
            schema=str(data["schema"]),
            tick=int(data["tick"]),
            previous_tick=int(data["previous_tick"]),
            dt=float(data["dt"]),
            rule_id=str(data["rule_id"]),
            previous_body_state_ids=_tuple_str(data.get("previous_body_state_ids", [])),
            result_body_state_ids=_tuple_str(data.get("result_body_state_ids", [])),
            gravity_potential_record_id=str(data["gravity_potential_record_id"]),
            energy_error_relative=float(data["energy_error_relative"]),
            angular_momentum_error_relative=float(data["angular_momentum_error_relative"]),
            source_record_ids=_tuple_str(data.get("source_record_ids", [])),
            is_authority_state=bool(data.get("is_authority_state", True)),
        )


def compute_effective_gravity_potential(
    bodies: Sequence[MacroCelestialBodyStateRecord],
    *,
    tick: int,
    gravitational_constant_eff: float = DEFAULT_G_EFF,
    softening_world: float = DEFAULT_SOFTENING_WORLD,
) -> EffectiveGravityPotentialRecord:
    potential_by_body_id: dict[str, float] = {}
    acceleration_by_body_id: dict[str, tuple[float, float, float]] = {}
    for body in bodies:
        potential = 0.0
        acceleration = (0.0, 0.0, 0.0)
        for other in bodies:
            if other.body_id == body.body_id:
                continue
            delta = _vec_sub(other.center_world, body.center_world)
            dist_sq = _vec_dot(delta, delta) + float(softening_world) * float(softening_world)
            dist = math.sqrt(dist_sq)
            potential -= float(gravitational_constant_eff) * other.effective_mass_energy / dist
            accel_scale = float(gravitational_constant_eff) * other.effective_mass_energy / (dist_sq * dist)
            acceleration = _vec_add(acceleration, _vec_scale(delta, accel_scale))
        potential_by_body_id[body.body_id] = potential
        acceleration_by_body_id[body.body_id] = acceleration
    source_body_ids = tuple(body.record_id for body in bodies)
    payload = {
        "tick": int(tick),
        "rule_id": GRAVITY_RULE_ID,
        "source_body_state_ids": source_body_ids,
        "potential_by_body_id": potential_by_body_id,
        "acceleration_by_body_id": acceleration_by_body_id,
    }
    return EffectiveGravityPotentialRecord(
        record_id=f"effective-gravity-potential::{_canonical_digest(payload).split(':', 1)[1][:16]}",
        schema="effective_gravity_potential_record_v1",
        tick=int(tick),
        rule_id=GRAVITY_RULE_ID,
        gravitational_constant_eff=float(gravitational_constant_eff),
        softening_world=float(softening_world),
        source_body_state_ids=source_body_ids,
        potential_by_body_id=potential_by_body_id,
        acceleration_by_body_id=acceleration_by_body_id,
        source_record_ids=source_body_ids,
    )


def _kinetic_energy(bodies: Sequence[MacroCelestialBodyStateRecord]) -> float:
    return sum(
        0.5 * body.effective_mass_energy * _vec_dot(body.velocity_world_per_tick, body.velocity_world_per_tick)
        for body in bodies
    )


def _potential_energy(
    bodies: Sequence[MacroCelestialBodyStateRecord],
    *,
    gravitational_constant_eff: float,
    softening_world: float,
) -> float:
    total = 0.0
    for index, left in enumerate(bodies):
        for right in bodies[index + 1 :]:
            delta = _vec_sub(right.center_world, left.center_world)
            dist = math.sqrt(_vec_dot(delta, delta) + float(softening_world) * float(softening_world))
            total -= float(gravitational_constant_eff) * left.effective_mass_energy * right.effective_mass_energy / dist
    return total


def _angular_momentum_vector(bodies: Sequence[MacroCelestialBodyStateRecord]) -> tuple[float, float, float]:
    total = (0.0, 0.0, 0.0)
    for body in bodies:
        momentum = _vec_scale(body.velocity_world_per_tick, body.effective_mass_energy)
        total = _vec_add(total, _vec_cross(body.center_world, momentum))
    return total


def advance_macro_bodies(
    bodies: Sequence[MacroCelestialBodyStateRecord],
    *,
    tick: int,
    dt: float = DEFAULT_DT,
    gravitational_constant_eff: float = DEFAULT_G_EFF,
    softening_world: float = DEFAULT_SOFTENING_WORLD,
) -> tuple[tuple[MacroCelestialBodyStateRecord, ...], EffectiveGravityPotentialRecord, MacroBodyStepRecord]:
    previous_bodies = tuple(bodies)
    if not previous_bodies:
        raise ValueError("advance_macro_bodies requires at least one body")
    potential = compute_effective_gravity_potential(
        previous_bodies,
        tick=int(tick) - 1,
        gravitational_constant_eff=gravitational_constant_eff,
        softening_world=softening_world,
    )
    before_energy = _kinetic_energy(previous_bodies) + _potential_energy(
        previous_bodies,
        gravitational_constant_eff=gravitational_constant_eff,
        softening_world=softening_world,
    )
    before_angular = _vec_length(_angular_momentum_vector(previous_bodies))
    next_bodies: list[MacroCelestialBodyStateRecord] = []
    for body in previous_bodies:
        acceleration = potential.acceleration_by_body_id[body.body_id]
        next_velocity = _vec_add(body.velocity_world_per_tick, _vec_scale(acceleration, dt))
        next_center = _vec_add(body.center_world, _vec_scale(next_velocity, dt))
        payload = {
            "tick": int(tick),
            "body_id": body.body_id,
            "center_world": next_center,
            "velocity_world_per_tick": next_velocity,
            "previous_body_state_id": body.record_id,
            "gravity_potential_record_id": potential.record_id,
        }
        next_bodies.append(
            MacroCelestialBodyStateRecord(
                record_id=f"macro-body::{body.body_id.split('::')[-1]}::{_canonical_digest(payload).split(':', 1)[1][:16]}",
                schema="macro_celestial_body_state_v1",
                tick=int(tick),
                body_id=body.body_id,
                body_kind=body.body_kind,
                center_world=next_center,
                velocity_world_per_tick=next_velocity,
                effective_mass_energy=body.effective_mass_energy,
                radius_world=body.radius_world,
                source_macro_authority_ids=body.source_macro_authority_ids,
                source_record_ids=tuple(dict.fromkeys([body.record_id, potential.record_id, *body.source_record_ids])),
            )
        )
    result_bodies = tuple(next_bodies)
    after_energy = _kinetic_energy(result_bodies) + _potential_energy(
        result_bodies,
        gravitational_constant_eff=gravitational_constant_eff,
        softening_world=softening_world,
    )
    after_angular = _vec_length(_angular_momentum_vector(result_bodies))
    energy_error_relative = abs(after_energy - before_energy) / max(abs(before_energy), 1e-9)
    angular_error_relative = abs(after_angular - before_angular) / max(abs(before_angular), 1e-9)
    step_payload = {
        "tick": int(tick),
        "previous_body_state_ids": tuple(body.record_id for body in previous_bodies),
        "result_body_state_ids": tuple(body.record_id for body in result_bodies),
        "gravity_potential_record_id": potential.record_id,
    }
    step = MacroBodyStepRecord(
        record_id=f"macro-body-step::{_canonical_digest(step_payload).split(':', 1)[1][:16]}",
        schema="macro_body_step_record_v1",
        tick=int(tick),
        previous_tick=int(tick) - 1,
        dt=float(dt),
        rule_id=GRAVITY_RULE_ID,
        previous_body_state_ids=tuple(body.record_id for body in previous_bodies),
        result_body_state_ids=tuple(body.record_id for body in result_bodies),
        gravity_potential_record_id=potential.record_id,
        energy_error_relative=float(energy_error_relative),
        angular_momentum_error_relative=float(angular_error_relative),
        source_record_ids=tuple(
            dict.fromkeys(
                [
                    potential.record_id,
                    *(body.record_id for body in previous_bodies),
                    *(body.record_id for body in result_bodies),
                ]
            )
        ),
    )
    return result_bodies, potential, step
