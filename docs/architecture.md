# Architecture and authority model

[English](architecture.md) / [中文](architecture.zh-CN.md)

## One world, one ordinary writer

The canonical world is an `ImplicitFieldState`: a finite, multi-channel coefficient vector over spatial basis records. `advance_implicit_field_state` is the ordinary transition owner. User controls and eligible Feedback are inputs to that one transition; they are not competing world writers.

```text
browser actor
  -> same-origin JSON request with current frame/state/ray lineage
  -> ImplicitFieldSession transaction
  -> canonical implicit Field transition
  -> energy ledgers and projection frame
  -> Pattern -> Trace -> Agent -> candidate Feedback
  -> application-time comparison on a later transition
  -> export, replay, completion, and Viewer readback
```

Camera movement creates an observation frame but does not advance the world tick. The Viewer consumes frames and audits; pixels, labels, browser sidecars, and FivePhase records are not authority state.

## Continuous local control

`local_excite` and `local_dampen` are positive and negative directions on one signed density-control axis. Radius creates a smooth compact spatial support. Fractional duration is materialized as a finite schedule whose weights sum to the requested dose. The runtime caps user input, then Feedback input, against the current density stage and records raw and realized projections.

The energy ledger is a bounded engineering proxy over the finite coefficient model. It tracks previous energy, internal coupling, cross-boundary coupling, dissipation, realized input, clipping, and residual. It is not a claim of thermodynamic conservation.

## Derived causal loop

FivePhase is a measurement vocabulary over the Field:

1. a phase projection is derived from canonical state;
2. Pattern identifies persistent bounded support;
3. Trace carries observation-specific loss and memory;
4. Agent compares current support energy with the episode setpoint;
5. Feedback proposes a signed basis-local correction;
6. the next transition recomputes sensitivity against its actual post-user baseline;
7. only a strict fixed-support error reduction is applied; otherwise Feedback is consumed as an empty projection.

Feedback-enabled and Feedback-disabled runs can be restored from the same trusted snapshot. Completion independently replays transitions, ledgers, lineage, persisted artifacts, and the counterfactual episode rather than trusting summary claims.

## Boundaries

This release deliberately has no authentication, TLS, multi-user isolation, durable database, public-network deployment, distributed consensus, or claim of universal physical law. The local server refuses non-loopback binds. A network product would be a separate capability vertical and threat model.

The v0.1 source closure still contains a large generated Viewer and legacy readout helpers used by real current paths. They remain in this preview to preserve tested behavior; decomposing them without creating a second authority path is future work.
