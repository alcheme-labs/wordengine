# Contributing

Thank you for helping improve GeNewWord Engine. This repository is a localhost research preview, not a production network service or content-complete game.

## Setup

Use Python 3.12 or newer and Node.js 18 or newer:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
npm ci
npx playwright install chromium
```

## Before opening a pull request

```bash
python tools/release_audit.py
python -m unittest discover -s tests -p "test_*.py"
python -m compileall -q world_engine scripts tests tools
python scripts/run_continuous_local_energy_response_validation.py --output /tmp/geneword-continuous.json
python scripts/run_five_phase_causal_closed_loop_validation.py --ticks 8 --source-package-name source-a --output-dir /tmp/geneword-causal
python scripts/run_five_phase_live_world_validation.py --ticks 8 --output-dir /tmp/geneword-live
python scripts/run_five_phase_pattern_trace_feedback_validation.py --output-dir /tmp/geneword-five-phase
npm run test:browser
```

Do not commit generated outputs, downloaded papers, browser binaries, model weights, caches, credentials, personal machine paths, or internal evidence archives.

## Architectural invariants

Contributions must preserve:

- one canonical ordinary Field writer;
- Viewer and FivePhase records as non-authority readback/derived artifacts;
- fail-closed request, frame, state, and ray lineage;
- exact replay and authoritative export readback;
- transaction, rollback, idempotency, concurrency, and negative coverage proportional to risk;
- application-time Feedback comparison before any later Field effect.

Core model or authority changes should begin with an issue and a concrete actor-to-readback capability path. Focused documentation, tests, and well-bounded fixes may proceed directly.

## Developer Certificate of Origin

Every commit must be signed off under [DCO 1.1](DCO):

```bash
git commit -s
```

The sign-off certifies that you have the right to submit the contribution under this repository's license.
