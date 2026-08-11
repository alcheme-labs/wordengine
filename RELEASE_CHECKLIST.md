# `v0.1.0-alpha.1` release checklist

The local source candidate is not authorization to publish. A maintainer must close every item before creating the public repository or tag.

## Rights and identity

- [ ] Confirm ownership or licensing authority for every original file in the allowlist.
- [ ] Confirm whether any pre-publication patent filing or trademark search is required.
- [ ] Choose the public GitHub owner, maintainer attribution, and conduct contact.
- [ ] Add the real repository URL and release date to `CITATION.cff` after the repository exists.

## Repository settings

- [ ] Create a brand-new repository with no private ancestor or imported `.git` history.
- [ ] Enable secret scanning, push protection, dependency graph, Dependabot alerts, private vulnerability reporting, and branch protection.
- [ ] Require the `hygiene`, Python, package, validators, browser, and CodeQL checks.
- [ ] Use DCO sign-offs for contributions.

## Clean-release evidence

- [ ] `python tools/release_audit.py`
- [ ] Formal Gitleaks working-tree and all-ref scans are clean.
- [ ] Clean Ubuntu and macOS clones install without local/Codex paths.
- [ ] Full allowlisted Python suite passes.
- [ ] Four documented validators pass.
- [ ] Both Chromium smoke tests pass.
- [ ] Wheel build and isolated import pass.
- [ ] Markdown links, metadata parsing, `git diff --check`, and clean `git status` pass.

## Claim boundary

- [ ] Release name is `v0.1.0-alpha.1 — Causal World Lab Research Preview`.
- [ ] README and release notes say localhost research preview, not production server or finished game.
- [ ] No public-network deployment instructions are published.
