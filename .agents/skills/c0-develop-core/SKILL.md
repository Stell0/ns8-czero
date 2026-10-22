---
name: c0-develop-core
description: Change or validate the reusable czero-core Python library, its migrations, compatibility and independent distribution in C0.
---

Read project AGENTS.md and the active PLAN.md subplan, and the current [development guide](https://github.com/Stell0/ns8-czero/blob/main/docs/development.md). Read `packages/czero-core/README.md` for library contracts; its version-specific examples do not override the consumer manifests and lock. Core owns reusable domain operations and packaged migrations; it must install independently without FastAPI, the reference app or the NS8 agent SDK. Lifecycle management stays in numbered NS8 actions.

Use the explicit local Core development setup documented by the repository. A fork's released Git/tag dependency and uv.lock must remain visible and reproducible; do not silently substitute an unreviewed local package in its runtime build.

Define authorization, concurrency, idempotency, limits and compatibility before implementing transport adapters. Recheck persisted membership inside privileged transactions and preserve existing lock order, evidence identities and immutable revisions. Register only trusted Python callbacks. Requests never choose imports, SQL, shell, provider credentials or schema-fetch locations.

For migrations, update the schema health constant, ship the migration in both wheel and archive, and test repeated migration plus real predecessor update/clean restore in disposable instances. Maintain independent package/runtime metadata and a compatible consumer range; breaking changes require explicit migration guidance.

Run focused Core/database tests and `tests/packaging` using the documented isolated PostgreSQL URL. Verify actual wheel/archive metadata, license, deterministic rebuild, clean external install and packaged migrations. Container packaging changes require the installed NethServer container skill and actual runtime audit, scans and native CI.

Core artifact tags use `core-v<version>` and the publication verifier requires local and both native successes for the exact source commit. Never replace published artifacts. Core library publication and an NS8 module release are separate operations; use the installed NethServer release skill for the latter. Record actual asset checksums/run links and do not infer a pass from a started workflow.

For fork-specific verification and managed-file boundaries, read the [fork development reference](../../references/development.md).
