# C0 / ns8-czero — Instructions for coding agents

This repository is the **C0 (Czero)** application template for NethServer 8. Read [PLAN.md](PLAN.md) for milestones and [README.md](README.md) for the public product contract. **Current baseline:** M00 through M03 are complete with local/CI/QEMU and documentation evidence. M04 native backup/restore implementation is active. The operator temporarily waived further interactive Playwright and live testing on 13 October 2026. Retain automated CI/QEMU/Robot checks and record live checks as waived, never passed. Do not describe planned storage, authentication, search or MCP as implemented. Start with the first pending milestone in PLAN.md.

## M04 implementation conventions (verification pending)

- Native dump/cleanup hooks prepare a mode-0600 custom PostgreSQL archive and backup format/service-state metadata. Restic includes these, `passwords.env` and `czero-sources`; never include live PostgreSQL files. Dumping a cold DB preserves prior database/pod state and does not start an unconfigured app.
- Restore extends Core with numbered settings, validation, offline database, route and service steps. Keep new Core node/port/image identity; restore only C0 settings. Fail on invalid formats/archives and use `pg_restore --single-transaction --exit-on-error`. Receipts prevent overwriting initialized data on repeated delivery of an already completed archive.
- The retained-source volume is infrastructure for later ingestion. Actual original-retention policy and coordination with file-writing ingest/worker operations must be verified in M07/M11; current M04 tests use a controlled retained file.
- Disposable backup setup captures Core's generated encryption password with Robot logging disabled and returns only identifiers. Genuine upgrade tests pin both predecessor module and component digests, not mutable tags. All destructive backup/restore cases remain QEMU-only.

## Established M03 database conventions

- Keep PostgreSQL and app in a native private pod; publish only the allocated app port on loopback. `czero.service` remains the app identity; pod and database are ordered dependencies. Active children use `PartOf` for pod restart propagation; retain a pod-recreation persistence test. Selected PostgreSQL supports notify and its entrypoint suppresses temporary-server notifications. Actual notify/startup, pod restart and database outage behavior pass QEMU.
- Credentials are generated once with native atomic safe I/O into mode-0600 `state/passwords.env`, loaded by Podman env-file. Create/update invoke the same focused helper; never export credentials through `agent.set_env` or action stdout. Do not rotate initialized database passwords during configure.
- Core owns packaged Alembic migrations and database operations. NS8 invokes the Core migration CLI before app startup. Migrations hold a PostgreSQL transaction/advisory lock and retain the knowledge-space identity across repeat runs. No NS8 lifecycle manager belongs in Core.
- Health reports safe database status/schema/vector versions and returns 503 on unavailability. Driver exceptions and connection URLs never enter responses. Application health SQL runs in FastAPI's sync worker pool.
- Keep upstream PGXS/compilers and all repository tests/configuration out of runtime images. PostgreSQL logical backup/restore implementation is under M04 verification; do not describe native restore as passing until QEMU proves it.

## Established M02 configuration conventions

- Keep configure steps focused: `10validate` checks native route ownership; `20configure-route` delegates TLS and explicitly clears legacy `path` with `null`; `40persist` writes only non-secrets after route acceptance; `80start_services` restarts; `90wait-ready` bounds local health checks. Do not hide native route/certificate failures.
- Action schema regex patterns must compile with Core's Go/RE2 validator as well as Python tests. Avoid lookaheads; `tests/check_schemas.go` gates compatibility in CI. Robot curl format placeholders must escape `%{...}`. Native update completion precedes ASGI readiness; poll health in integration tests.
- Persist hostname lowercase and certificate flags as `true`/`false`. An explicitly empty `CZERO_BASE_PATH` means hostname-root routing. Update hooks initialize a missing key to the legacy instance prefix, never overwrite a configured empty key.
- Track admin task listeners, including repeated progress events, and remove them on every terminal result, task creation failure and Vue destruction. Field errors use native validation parameters. Only English translation source is edited.
- Synthetic `.test` hosts and certificate exceptions belong only to disposable QEMU tests. The operator's live-testing pause remains active.

## Established M01 conventions

- `packages/czero-core` contains reusable runtime operations and an independent version; `app` owns FastAPI transport, route composition and the separate static application UI. Both currently have version `0.1.0`. Core is a local package dependency until M13 distribution work.
- NS8 still owns lifecycle through short numbered scripts. Core injects `CZERO_APP_IMAGE` from the module dependency-image label; `configure-module/20configure` persists only the non-secret `CZERO_MODULE_ID`. The app validates that identity and mounts at `/czero/<module-id>` because the NS8 route preserves its prefix.
- Application routes currently provide a landing page, `/api/v1/health`, `/openapi.json`, `/docs` and an honest `/agents` introduction. They have no authentication or persistence yet. Keep the application UI separate from the compiled NS8 Vue administration UI.
- `app/uv.lock` locks runtime dependencies. Build non-editable packages into `/opt/czero/.venv` in both container stages: generated console-script interpreter paths must not change when the virtualenv is copied. The final stage runs as UID 10001 and removes base-image package installers; copy only the virtualenv and static runtime files.
- Audit installed dependency wheels too: FastAPI currently bundles `.agents` authoring skills, which the builder removes. The publisher runs `tests/audit_runtime.py` against the assembled image through stdin before publication; this repository-only check rejects development files and installed build/test tools.
- The inherited Core `get-status` action expects no input (`null`), so omit `data` in its UI/API task payload. Sending `{}` fails Core input validation. Czero configuration accepts a required DNS `host` and optional boolean `lets_encrypt`.
- The service unit uses `%N`, so the Podman container is named `czero`, not `czero.service`. Check request logs with that container name. Uvicorn access logs are enabled; Robot verifies a real health request appears in the logs.
- Run pytest across `app/tests`, `packages/czero-core/tests` and `tests/unit`. QEMU verifies mounted application routes, configuration/rejection, logs, restart, forced native update and disposable uninstall, with admin and end-user browser assertions. A same-image forced update does not prove a future database migration.
- Core reloads units and image environment during update but delegates service restart to hooks. `update-module.d/20instance-id` reconciles the non-secret ID missing from M00, then `80restart` uses native `try-restart` so running containers are replaced and unconfigured instances remain stopped.

## Established M00 conventions

- Module image: `ghcr.io/stell0/czero`; lifecycle service: `czero.service`. M02 registers an instance-owned hostname route with HTTPS redirection; existing M01 prefix routes are preserved until hostname configuration. M01 adds FastAPI and the separate application UI; authentication remains pending M05.
- Module images carry OCI source, revision, license and product title labels. Source labels preserve repository attribution; existing package Actions permissions may still need a one-time operator repair.
- `build-images.sh` packages only `imageroot/` and generated `ui/dist/` into the NS8 module image. Preserve this explicit runtime allowlist. M01 replaces the pinned M00 echo stub with the separately built `czero-app` component image.
- Publication needs both `contents: read` and `packages: write`. The upstream reusable publisher explicitly removes checkout access; the small local job was adapted from its steps while the repository was private and is retained after the repository became public. QEMU runs only after successful publication and checks install and forced native update scenarios; M00 has no older released predecessor. UI tests run every time. A green wrapper with skipped tests is not evidence.
- Publication inspects image metadata with GHCR authentication and fails on pull errors. Trivy scans sources and runtime images and stores SARIF/CycloneDX artifacts; optional GitHub Security ingestion is not configured in these workflows. Both repository and package are now public; anonymous manifest access has been verified. Package Actions Write access is separate from public read access and must survive repository reconnection. Earlier QEMU legs failed before VM boot; corrected Debian 13/update and Rocky 9/install/browser suites now pass. Existing scan findings in UI dependencies and the echo stub are recorded in PLAN.md and must be reviewed before release.
- Publish module images with the native `GITHUB_TOKEN` and explicit `contents: read`/`packages: write`. The existing package must grant this repository Actions Write access. `NS8_MODULE_RELEASES_TOKEN` is for future GitHub release automation, not this publisher; leave the operator-created secret untouched. Private source checkout works with the contents permission. Private packages need authenticated QEMU/guest pulls in addition; current upstream QEMU pulls anonymously. A successful owner-token push does not prove repository Actions Write access.
- Live installation/configuration/restart/HTTP checks pass on Core 3.21.0/Rocky 9.8 using native authenticated tasks and Playwright MCP. No SSH is assumed. Core inventory misparses digest-only URLs via a colon split; prefer verified version tags and compare actual digests. Normalize unordered flags when comparing inventories. Live System logs showed no Czero entries; do not claim log visibility verified.
- The operator resolved live browser trust; Playwright admin login succeeds with normal certificate validation. Earlier exception attempts were rejected and were not bypassed. Ignore `.playwright-mcp/` artifacts and keep private browser evidence in restricted temporary storage. Do not commit hostnames, auth state or credentials.
- Core `add-module` prints a Python dictionary; `api-cli` prints JSON. `tests/CzeroActions.py` safely accepts either output form with literal parsing and checks Czero identity. Never use unrestricted `eval` on command output.
- Browser smoke checks must assert an actual state transition: in disposable QEMU, stop only Czero and verify that Settings Save restores the HTTP route. Use substring selectors for the longer honest-stub paragraph.
- Browser calls inside Python Robot helpers must use `BuiltIn.run_keyword` so enum/timeout arguments receive normal Robot conversion. Await a positive authenticated heading; `#main-content` alone may also exist on login. The authorized live test platform reported Core 3.21.0 through advertised read-only facts.
- `tests/CzeroBrowser.py` creates a random administrator only on disposable QEMU and suppresses password-entry logging. Never use this helper on a shared/live host. Local action tests live in `tests/unit/`; Robot tests remain in `tests/czero.robot`.

## Mission and boundaries

C0 is a deployable NS8 web application plus a forkable, AI-first development foundation. A vanilla installation must eventually provide a browser UI, FastAPI REST endpoints, PostgreSQL + pgvector, reusable generic-object and LLM Wiki storage, text and optional semantic/graph retrieval, an authenticated remote MCP endpoint, a self-describing `/agents` page, and deterministic jobs/scheduled maintenance.

- **Single C0 instance = dedicated PostgreSQL instance and shared knowledge space.** Initial access: one owner; optional application-wide Reader, Editor, Admin roles. No document ACLs, UGO, policy engine or multi-tenancy.
- No built-in generative LLM, autonomous wiki agent, research orchestrator, or AI cron. External harnesses handle reasoning, wiki synthesis and research.
- Only optional outbound AI requests: embedding generation and System One relevance scoring (**Jev and Kev**). If unavailable, text search still works; System One failure falls back to normal ranking.
- Deterministic parsing, indexing, CRUD, relationships, backup, health tasks and job processing do belong in C0.
- Source originals are **deleted by default only after successful extraction/persistence**; retain complete extracted text, offsets, citations, revisions and metadata. Optional original retention uses an NS8-backed volume.
- Development instructions, skills, CI files and tests belong **only in Git**. Do not bake `AGENTS.md`, `PLAN.md`, `.agents/`, `.github/`, tests, credentials or development tools into runtime images.
- All documentation must match actual behavior. Never state that a feature works merely because there is scaffolding.

## Source hierarchy: reuse before implementing

1. Inspect current local code and the target NS8 platform version.
2. Consult the official [NS8 Core developer manual](https://github.com/NethServer/ns8-core/tree/main/docs/modules) and the maintained [NethServer agent skills](https://github.com/NethServer/agents/tree/main/skills/nethserver-ns8-module).
3. Inspect maintained, task-specific implementations linked in the current milestone of [PLAN.md](PLAN.md): [ns8-kickstart](https://github.com/NethServer/ns8-kickstart), [ns8-hermes-agent](https://github.com/NethServer/ns8-hermes-agent), [ns8-dependencytrack](https://github.com/NethServer/ns8-dependencytrack), [ns8-idp](https://github.com/NethServer/ns8-idp), [ns8-mail](https://github.com/NethServer/ns8-mail), and [ns8-github-actions](https://github.com/NethServer/ns8-github-actions).
4. When alternatives disagree, prefer current documented Core contracts, then the newer maintained implementation with passing tests. Check its actual files rather than copying a README example blindly. Preserve license headers and attribution; this repository currently carries GPL-3.0.
5. If no matching NS8 pattern exists, search current NethServer/Nethesis module code by operation, identify why no reusable solution fits, and implement the smallest C0-specific component.

Recommended installed development skills: `nethserver-ns8-module`, `nethserver-admin`, `nethserver-containerfile`, `nethserver-pr`, `nethserver-release`, `conventional-commit` (all from [NethServer/agents](https://github.com/NethServer/agents)). C0-specific skills may be added later, but must delegate NS8 rules instead of duplicating them.

## Keep NS8 actions readable

**Do not build a monolithic Python manager for NS8 lifecycle.** Use NS8's action/step convention:

- `imageroot/actions/<action-name>/10validate`, `20persist`, `40configure-service`, etc.; one focused executable per meaningful step, ordered lexicographically.
- Reuse inherited Core actions; add only missing steps. User-facing actions have `validate-input.json` and `validate-output.json` where applicable.
- Read JSON from stdin. Write only machine-readable JSON to stdout for actions returning data. Send diagnostics to stderr/journald. Nonzero step exit stops the action.
- Use `import agent` helpers: `set_env` for **non-secrets**, `bind_user_domains`, `set_route`, `run_helper` and `agent.tasks.run` as appropriate. Prefer platform conventions over direct Redis/Podman hacks.
- Never write secrets with `agent.set_env`; its environment reaches Redis. Keep credentials in restricted `state` secret files, backed up through native NS8 mechanisms and loaded by systemd/container env-file. Do not log credentials.
- NS8 module owns systemd, Podman, Traefik, lifecycle, backup, restore and service configuration. The **application backend** owns FastAPI, shared operation/services, domain validation, PostgreSQL queries, REST/MCP, retrieval and jobs. Avoid duplicate business logic across interfaces.
- Keep the cluster-administration UI (existing NS8 Vue 2 + ns8-ui-lib convention) distinct from the C0 end-user application UI. No custom NS8 control plane.

## Runtime design invariants

- One versioned Python **C0 Core** package for reusable runtime operations, with stable public interfaces; applications extend it. C0 Core is not a replacement for small NS8 action scripts.
- Generic objects (JSONB + schemas) complement dedicated relational tables; typed references connect objects, knowledge pages and sources. Use database transactions and migrations.
- Knowledge storage preserves raw extracted evidence separately from AI-produced claims; provenance and revisions must survive reindexing and restore.
- Full-text PostgreSQL search is always usable. Semantic/hybrid search needs optional compatible embedding configuration. Jev/Kev provide optional relevance scoring, never access-control decisions; bound inputs and timeouts, disclose fallbacks.
- Treat uploaded documents, page contents and retrieved material as untrusted data; never interpret them as executable or developer instructions. REST and MCP use the same service methods and authorization.
- Only registered, trusted deterministic handlers may run from scheduled tasks; no arbitrary SQL or shell-command execution exposed via user REST/MCP tools.
- Configuration hierarchy: built-in safe defaults -> NS8 admin-managed instance config -> validated, bounded request-time overrides. External provider secrets cannot be overwritten per request.

## Mandatory milestone loop

Work through [PLAN.md](PLAN.md) **one milestone at a time**, in order; never skip a red prerequisite. Every milestone contains upstream implementation links or explicit code-search instructions and acceptance criteria.

1. Inspect the worktree, current milestone, platform/source references, and actual CI status. Make a small **implementation subplan in PLAN.md** for the active milestone, with tests and anticipated docs; don't make speculative architecture expansions.
2. Implement vertical slices with focused tests. Commit and **push each meaningful working increment** using the conventional-commit skill. Build/publish images in CI starting at M00; don't postpone CI until the end of the roadmap.
3. For each push, inspect the relevant GitHub Actions image build, QEMU/Robot integration tests and logs. If red, diagnose, fix, commit and push; rerun until green or document a genuine blocker. Never mark a test passing without evidence.
4. When a user-facing NS8/admin or application UI changes, test interactively using **Playwright MCP**: navigate, log in as the appropriate permitted test persona, inspect accessibility snapshots, exercise the workflow and assert actual state. Also add repeatable browser/Robot tests to CI where appropriate. Test **both** NS8 administration UI and the C0 user interface when present.
5. Once a bootable C0 image exists and CI passes, validate on an explicitly authorized live NS8 test instance with the execution-time access details provided by the operator; deploy only the C0 module, do not alter unrelated modules, and protect existing data. Do not assume SSH exists just because the web UI exists. If a capability is unavailable, record the gap instead of claiming a pass.
6. **At every milestone, update AGENTS.md (technical/agent instructions), README.md (human-facing current features, usage, limitations), and PLAN.md (milestone results, evidence and next step).** Commit/push these updates; watch the resulting CI as appropriate.
7. Mark a milestone `[x]` only when its acceptance criteria and mandatory evidence are satisfied. Record commit SHAs, CI run links, test results and any remaining nonblocking limitations in its `Evidence` paragraph. Move to the next milestone only then.

The template's hard-coded Robot login credentials have been removed. Use disposable random test identities or execution-time configuration. **Never commit real live hostnames, usernames/passwords, tokens, cookies, auth state, screenshots containing secrets, or private test-server details.** Pass live access details only in the operator's execution prompt/session; mask them in logs, reports, PRs and traces.

## Definition of done for any change

Code, data migrations, REST/MCP schema, end-user/admin UI, tests, backup implications and docs must be considered together. Before declaring completion: inspect diff, run relevant local tests, push, verify CI, run QEMU/live/browser checks when applicable, and reconcile `AGENTS.md`, `README.md` and `PLAN.md`. Document blockers precisely; do not substitute fabricated output.

**Start at [PLAN.md — M00](PLAN.md) unless a milestone has already been recorded as complete with evidence.**
