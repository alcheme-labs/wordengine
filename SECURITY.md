# Security policy

## Supported version

Only the latest `0.1.x` research-preview release is supported.

## Reporting a vulnerability

Use GitHub private vulnerability reporting for the repository. Do not open a public issue containing exploit details, personal data, credentials, or unpublished artifacts. Reports are acknowledged and coordinated on a best-effort basis; this research preview has no contractual response SLA.

## Deployment boundary

The included HTTP server is a single-user localhost research tool:

- it refuses non-loopback binds;
- mutation requests require same-origin `application/json` and are capped at 64 KiB;
- identifiers, session ticks, frames, and exported response sizes are bounded;
- public error responses do not expose raw exception text;
- it has no authentication or TLS;
- it is not approved for public-internet or untrusted-network exposure;
- it does not provide durable multi-user storage or cross-process checkpoints.

Security-sensitive areas include canonical Field ownership, interaction lineage, snapshot restore, replay/idempotency, export privacy, request parsing, and Viewer non-authority. Any change to those surfaces requires negative tests and authoritative readback.

If a networked product is built later, it requires a separate threat model and real authentication, TLS termination, session isolation, rate limiting, persistence/backup, audit-log privacy, and operational incident response.
