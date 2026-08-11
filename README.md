# GeNewWord Engine

[English](README.md) / [中文](README.zh-CN.md)

GeNewWord Engine is a playable, field-driven world-engine research preview built around an auditable causal chain:

**Field → Constraint → Pattern → Trace → Agent → Feedback → later Field**

Instead of treating the Viewer as world authority or replaying a prerecorded effect, the local runtime owns one continuous world state. Signed, spatially bounded interactions can excite or dampen that Field; derived patterns and Agent feedback may influence a later Field only after a fail-closed application-time comparison.

## Status

`v0.1.0-alpha.1` is a **localhost research preview**. It is not a finished game, a universal physical theory, or an internet-ready server. See [current public status](docs/status.md) and the [architecture and authority model](docs/architecture.md).

## Three-minute start

Requirements:

- Python 3.12 or newer;
- a modern browser;
- Node.js 18 or newer only when running browser acceptance tests.

The runtime has no third-party Python dependencies.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .

python scripts/serve_implicit_3d_field_window.py \
  --host 127.0.0.1 \
  --port 8766 \
  --max-advance-ticks 8
```

Open `http://127.0.0.1:8766/viewer.html`, select `interact`, choose `local_excite` or `local_dampen`, and click the canvas. Use `Run World` to advance the canonical state and `/export` for authoritative readback.

The server deliberately refuses non-loopback binds. It has no authentication or TLS and must not be exposed to the public internet or an untrusted network.

## Reproduce the causal claims

```bash
python scripts/run_continuous_local_energy_response_validation.py \
  --output /tmp/geneword-continuous.json

python scripts/run_five_phase_causal_closed_loop_validation.py \
  --ticks 8 \
  --source-package-name source-a \
  --output-dir /tmp/geneword-causal

python scripts/run_five_phase_live_world_validation.py \
  --ticks 8 \
  --output-dir /tmp/geneword-live

python scripts/run_five_phase_pattern_trace_feedback_validation.py \
  --output-dir /tmp/geneword-five-phase
```

These are bounded engineering validations, not claims of conserved thermodynamic energy or universal laws.

## Tests

```bash
python -m unittest discover -s tests -p "test_*.py"
python -m compileall -q world_engine scripts tests tools

npm ci
npx playwright install chromium
npm run test:browser
```

Use dedicated `/tmp/geneword-*` output directories: validation runners may recreate the output directory they receive.

## Documentation

- [Play, build, validation, and troubleshooting guide](docs/continuous-local-energy-response-guide.md) / [中文完整译文](docs/continuous-local-energy-response-guide.zh-CN.md)
- [Architecture and authority model](docs/architecture.md) / [架构与权威边界](docs/architecture.zh-CN.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)

## Repository boundary

This public repository contains original engine code, tests, and documentation only. It does not bundle downloaded research papers, article mirrors, video metadata, internal experiment archives, model weights, or generated validation output.

## License

Original project code and documentation are licensed under the [Apache License 2.0](LICENSE). Dependencies retain their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md).
