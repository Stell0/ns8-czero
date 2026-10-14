# C0 (Czero) — Application foundation for NethServer 8

**Status (14 October 2026): M00–M07 are complete with local, disposable, documentation and permitted live evidence. Generic objects, REST, the minimal record editor and corrected native scheduler pass acceptance. M08 document ingestion is next.** Czero has a FastAPI application, dedicated PostgreSQL/pgvector, native NS8 configuration and backup, and a separately versioned C0 Core package. Interactive Playwright remains waived; targeted live testing is reauthorized. See [PLAN.md](PLAN.md) for commit, CI and test evidence, and [AGENTS.md](AGENTS.md) for development rules. No stable release is ready.

## Purpose and boundaries

C0 is a deployable application foundation and a forkable GitHub template. External coding agents can extend its shared operations and application UI while retaining native NethServer lifecycle, packaging and tests. C0 Core lives in `packages/czero-core`; fork-specific business logic belongs in `app`.

One installed C0 module owns one dedicated PostgreSQL instance and one shared knowledge space. Access uses one owner and optional Reader, Editor and Admin memberships. There is no per-document ACL system or multi-tenancy.

Generic JSON Schema objects and deterministic jobs work now. Document evidence, an LLM Wiki, text/vector/graph retrieval and authenticated remote MCP remain planned. C0 stores and serves knowledge; external harnesses perform reasoning, research and wiki synthesis. No generative LLM, autonomous agent, scheduled AI prompts, local inference, arbitrary user shell jobs or second graph database belongs in the runtime.

## Current interfaces

Configure an application hostname in NS8 Settings. Older M01 installations retain `/czero/<module-id>` on the cluster host until hostname configuration.

| Path | Available behavior |
| --- | --- |
| `/` | Landing page, database status, sign-in status and Admin sharing controls |
| `/objects` | Minimal typed record list/detail and JSON editor; disposable/browser verified; live interactive browser waived |
| `/api/v1/object-types`, `/api/v1/objects`, `/api/v1/objects/batch` | Authenticated type inspection/registration, CRUD, paging/filters and atomic batches |
| `/api/v1/object-relations`, `/api/v1/objects/<id>/relations`, `/api/v1/object-events`, `/api/v1/references/<kind>/<id>` | Typed object edges, metadata changes and trusted registered reference resolution |
| `/api/v1/health` | Public Core/app versions and PostgreSQL/schema/vector readiness |
| `/api/v1/auth/status` | Public indication that authentication is configured |
| `/auth/login`, `/auth/callback` | OIDC authorization-code login with PKCE, one-use state and nonce |
| `POST /auth/logout` | Local session revocation and provider logout URL |
| `GET /api/v1/me` | Authenticated profile and current application role |
| `GET /api/v1/access/accounts` | Admin list of verified profiles and grants |
| `PUT /api/v1/access/accounts/<id>` | Admin grant/revocation of Reader, Editor or Admin |
| `/api/v1/jobs`, `/api/v1/jobs/handlers`, `/api/v1/jobs/<id>`, `/api/v1/jobs/<id>/runs` | Admin inspection and idempotent enqueue of registered jobs |
| `/api/v1/schedules`, `/api/v1/schedules/<id>`, `/api/v1/schedules/<id>/runs` | Admin create/list/configure UTC interval schedules and inspect run state |
| `/openapi.json`, `/docs` | REST schemas and Swagger UI |
| `/agents` | Honest introduction to implemented interfaces and remaining roadmap |

Core/app versions are **0.9.0/0.10.0**, with packaged migrations through `0005_objects`. Public health returns HTTP 200 when PostgreSQL, schema and pgvector are ready, or safe HTTP 503 with a database reason. Authentication status reports configuration rather than provider reachability. Swagger loads assets from a CDN; OpenAPI JSON remains usable without them.

Source CRUD, ingestion, Wiki, retrieval, `/mcp` and `/agents/capabilities.json` remain later milestones. Readers can inspect object records; Editors can write objects and relations. Admins register immutable schemas and manage membership. These object transports pass local PostgreSQL-backed HTTP, actual disposable SSO/browser, native update/restore and permitted live owner CRUD/restart persistence. Interactive live browser remains waived.

## Install and configure

For development installation, use native NS8 `add-module` with image `ghcr.io/stell0/czero:main` and your node ID. `:main` and `:latest` track development builds and are not stable releases; consult PLAN.md for tested commits/digests. The repository and module/app/database packages are public. Core 3.21.0 has an inventory display issue for digest-only image URLs, although installation works.

In **Czero Settings**, enter a fully qualified DNS hostname pointing to the NS8 node. Enable **Request a Let's Encrypt certificate** when public DNS/network access permits issuance; otherwise Traefik uses its configured certificate. Save registers HTTPS routing, redirects HTTP, restarts services and waits for local health. Conflicting or malformed hostnames are rejected. The saved application link opens `https://<hostname>/`. Native Let's Encrypt configuration and trusted application HTTPS were exercised on the authorized test instance.

The native `get-authentication-status` action checks the running app's trusted IdP discovery/keys and returns only status/reason categories (TLS, DNS, refused/unreachable connections, timeout, provider HTTP or metadata errors). It returns disabled before sign-in is configured. Malformed bearer values are rejected locally before contacting an unavailable provider. Diagnostics and native same-node routing pass Debian/Rocky QEMU and live tests.

The native API accepts hostname-only configuration such as `{"host":"c0.example.test","lets_encrypt":false}`. `get-configuration` returns saved host/certificate and identity settings without secrets. Authentication remains disabled until an IdP, user domain and owner are selected; resource access fails closed.

### Sign-in and sharing

1. Configure a compatible NS8 IdP with trusted HTTPS and a user domain. Enable **NethServer sign-in** in Czero Settings, select both and enter an existing domain account as owner. Save resolves its stable LDAP UUID, binds one domain and registers exact callback/logout URLs plus the Czero audience.
2. Open Czero and sign in with that domain account. This is separate from the cluster-administration account. The owner receives Admin access to the shared space.
3. A prospective member first attempts sign-in and is denied until admitted. The owner can then select Reader, Editor or Admin for that verified account in the sharing controls. Revocation applies to the next request, including existing sessions. Ownership is managed through NS8 Settings.

Native configuration maps a selected same-node IdP hostname to the rootless host gateway; remote providers use normal DNS. The pod uses the standard NS8 slirp host-loopback pattern, retaining the registered HTTPS issuer and certificate validation. Configure/update replace pod, database and app together. This routing pattern passes real disposable and live SSO.

Signed issuer/LDAP UUIDs identify accounts; usernames and token role claims do not grant ownership or membership. REST accepts verified access tokens and the browser uses opaque Secure/HttpOnly/SameSite cookies. Cookie writes require CSRF plus the configured Origin. Server sessions expire at the earlier token expiry or one hour. Sign-out revokes the local session and opens provider confirmation. If the provider is unavailable, local logout still succeeds but its SSO session may remain.

Native registration/binding is not a distributed transaction. A failed cross-module change reports an error and keeps the previous secret file, but may require re-saving the previous selection and hostname. Configured native update and encrypted clean restore preserve owner/member account IDs and saved roles, verified on Debian and Rocky. Restore re-registers the client for the new native module identity.

The current upstream IdP has no stable GitHub release; its README's `1.0.0` image is unavailable. Disposable tests pin a verified main image and require the upstream `ldapproxy:1.4.0-dev.1` listener fix for Keycloak pod access. These are development dependencies. Compatible stable IdP/proxy availability is a release prerequisite; no live proxy has been modified.

## Persistence and backup

Each module has PostgreSQL **17.11** plus pgvector **0.8.7**, a private pod and its own `czero-db-data` volume/password. Database ports are not published. Native startup runs packaged migrations before the app; repeated migration, restart, pod recreation and upgrades preserve data and knowledge-space identity.

Use the native NS8 Backup page to select Czero and a supported destination, run backup and verify a snapshot. Restore uses a clean module slot with its hostname available. Archives contain an atomic PostgreSQL custom dump, private configuration, service-state metadata and the retained-source volume; live database files are excluded. Offline restore uses fail-fast transactional `pg_restore`, retains the new native module ID/port and Core-assigned logical UUID and restores the prior enabled/running state. A completed-archive receipt permits replay without overwriting later database changes. Debian/Rocky native tests verify these baseline behaviors.

The retained-source volume currently holds controlled test fixtures. Document ingestion and original-retention behavior arrive in M08. Backup pauses workers/timer through the copy. Foreground file-writing coordination must be extended with ingestion.

M06 currently adds Core queue/schedule storage and services with registered deterministic health/maintenance handlers, validated idempotency and Admin authorization. Standalone worker execution and authenticated REST pass local database tests. Native timer/one-shot execution, due-once runs, restart and backup/restore pass Debian/Rocky QEMU. Permitted live timer completion and API persistence pass.

Admins can POST `{"handler":"health","payload":{},"idempotency_key":"health-check-1"}` to `/api/v1/jobs`. Repeating the same request returns the same job; a conflicting handler/payload returns 409. Only registered `health`/`maintenance` accept empty payloads in the default app. Schedule intervals range from 60 seconds to 31 days; missed intervals coalesce to one due run. Pausing stops future scheduling; queued jobs may complete. Worker attempts and terminal state survive restarts; failed attempts use bounded backoff. Handlers use one database transaction for effects/completion, and must make file/network effects idempotent. Job history retention is 30 days with bounded weekly pruning. The native timer wakes about one minute after activation and one minute after worker completion. Python handler deadlines are capped at 30 seconds and the native container at 150 seconds. The worker is idle between runs; `get-scheduler-status` reports timer, running and failure state. Backup pauses worker/timer through the copy and restores prior timer state. These native behaviors pass disposable QEMU; permitted live timer completion, idempotency, schedule/job/identity persistence and unchanged unrelated inventory also pass.

There is no full jobs/schedules application page yet; use the authenticated API/OpenAPI. The worker processes at most twenty jobs per wake within its bounded budget, serially. Python deadlines cannot preempt every extension call; the native container lifetime guard bounds those cases. External/file effects remain at-least-once and must be idempotent. Foreground source-file backup coordination will be added with ingestion in M08.

M07 Core implements immutable type registration, JSONB records, tags, optimistic revisions, optional top-level scalar uniqueness, atomic batches, typed object relations and paginated events. The REST transport passes signed local PostgreSQL tests; the record page passes actual repeatable QEMU browser assertions for owner forms, refresh, hostile-text rendering and Reader controls. Schemas support a bounded Draft 2020-12 subset: explicit types, properties/required, arrays, scalar bounds, enum and const. Remote/recursive references, regexes, combinators and unknown properties are rejected; validation never fetches URLs. Objects are capped at 64 KiB, batches at 25 operations/256 KiB, and reads at 100 rows. Existing object relations use foreign keys. Trusted application code can register relational reference resolvers; the default app resolves only object kinds until sources/Wiki tables are implemented.

On the Records page, choose a type, browse or open a record, and use New record or Save record with a JSON object and comma-separated tags. Invalid schema values report the field/keyword. A revision conflict preserves the local draft; Load saved version explicitly refreshes it. Admins can expand Register a record type, enter its name/label/schema and optional unique scalar fields. Types are immutable. The type picker shows the first 100 definitions and record paging uses 50 rows; the API exposes paging and equality/containment filters. Full schema-generated forms remain M12.

For example, register `inventory` with `{"type":"object","properties":{"name":{"type":"string","maxLength":64}},"required":["name"]}` and `unique_fields:["name"]` at `/api/v1/object-types`; POST `{"type_name":"inventory","data":{"name":"Rack A"},"tags":["inventory"]}` to `/api/v1/objects`. PUT the record with `data` and `expected_revision` from its last response. Cookie writes require the existing CSRF token; bearer requests use the signed access token.

Native manager restart exposed a systemd app/timer/basic-target ordering cycle. The corrected timer keeps explicit app/shutdown bindings without default boot-target ordering. Actual Debian/Rocky manager restarts pass with no C0 ordering-cycle journal lines; three live manager restarts recover an active/successful timer and preserve object/job/schedule/configuration state. The native scheduler diagnostic includes bounded timer state/result/dependency names. App-only restart tests remain insufficient for this path.

## Remaining roadmap

| Capability | Agreed direction |
| --- | --- |
| Evidence | Full extracted text, offsets, metadata, revisions and citations |
| Wiki | Pages, claims, entities, revisions and provenance, separate from raw evidence |
| Retrieval | PostgreSQL full-text search, optional external embeddings and graph expansion |
| System One | Optional Jev/Kev scoring with bounded requests and ordinary-ranking fallback |
| Agent access | Shared REST/MCP operations, OAuth protection and self-description |
| Forks | Reusable Core distribution, upstream-compatible extensions and development skills |

Object CRUD and jobs work without AI credentials. Deterministic parsing/chunking, Wiki editing and full-text retrieval must retain that property as they are implemented. Binary originals are deleted by default only after successful extraction/persistence; optional retention uses an NS8 volume. Safe built-in defaults precede NS8 instance configuration and bounded request overrides. Request overrides cannot replace provider secrets. Semantic retrieval requires configured embeddings; Jev/Kev failures must disclose fallback and never determine authorization.

## Development and verification

`build-images.sh` publishes `ghcr.io/stell0/czero`, `czero-app` and `czero-postgres`. The module contains numbered actions and compiled NS8 Vue UI; the Python component contains installed Core/app packages and the separate user UI. Runtime images exclude agent instructions, plans, skills, CI, tests and development tools. The app runs unprivileged; NS8 lifecycle logic stays outside the application backend.

Install development dependencies in a virtualenv:

```sh
pip install pytest robotframework robotframework-sshlibrary -e packages/czero-core -e 'app[test]'
python -m pytest -q app/tests packages/czero-core/tests tests/unit
```

There are 205 unit cases. Set `CZERO_TEST_DATABASE_URL` to an isolated PostgreSQL/pgvector database and include `tests/integration` for fifty-eight actual database cases. CI supplies a disposable service. `node --test tests/ui/*.cjs` checks record refresh races using the real UI script. `go run tests/check_schemas.go` validates action regex compatibility with Core's Go engine. Runtime dependency builds use `app/uv.lock` and frozen, non-development installation.

Build the administration UI:

```sh
cd ui
corepack yarn install --immutable
NODE_OPTIONS=--openssl-legacy-provider corepack yarn build
```

`tests/czero.robot` runs native lifecycle in disposable QEMU, including an immutable M05 predecessor, real PostgreSQL/vector persistence and encrypted backup/restore/replay. Baseline browser tests use a generated temporary cluster administrator. Real SSO fixtures provision OpenLDAP/IdP, generated private personas and trusted test certificates; native local-provider routing is used without fixture DNS overrides, asserting actual owner/member authorization, roles, revocation and logout. TLS and SELinux remain enabled. Private password/token values never become Robot variables, command arguments or nested keyword arguments. A report assertion checks the temporary browser password.

An older M01 installation may stop when pod/database dependencies are introduced; re-save hostname Settings to start the new stack. Live startup, migration, hostname/certificate/identity configuration, discovery, signed owner login/logout, CSRF/owner protection, negative REST authorization and stable owner identity after restart pass. All three member roles, revocation and identity restore are verified in disposable tests; a second live application persona was not exercised.

Czero strips queries from application access logs. Core Traefik has its own default access log; its production logging contract still needs release review. Disposable SSO fixtures suppress proxy access logs and assert no OAuth query values in both streams. Interactive Playwright remains operator-waived. Permitted live tests use only the dedicated Czero instance; destructive backup/restore tests remain disposable.

Publication uses `GITHUB_TOKEN` with package-write permission and package Actions Write grants. `NS8_MODULE_RELEASES_TOKEN` is reserved for future GitHub releases. Private repositories are supported; private container packages additionally need authenticated guest pulls. Package names remove the repository's `ns8-` prefix, following Hermes.

CI includes local/schema/shell checks, image publication/runtime audits, Trivy SARIF/CycloneDX artifacts and native QEMU/Robot tests. Successful scans do not establish that dependency findings are resolved. Review findings before release. Follow AGENTS.md's milestone loop: plan, implement, commit/push, inspect actual CI/tests, fix failures, reconcile documentation, then advance. Keep live hostnames, passwords, tokens, cookies and auth-state files out of Git and artifacts.

## NethServer sources and license

Czero derives from [ns8-kickstart](https://github.com/NethServer/ns8-kickstart). Reuse [Core module contracts](https://github.com/NethServer/ns8-core/tree/main/docs/modules), [Hermes](https://github.com/NethServer/ns8-hermes-agent), [Dependency-Track](https://github.com/NethServer/ns8-dependencytrack), [IdP](https://github.com/NethServer/ns8-idp), [ns8-ui-lib](https://github.com/NethServer/ns8-ui-lib), [QEMU Actions](https://github.com/NethServer/ns8-github-actions) and [NethServer agent skills](https://github.com/NethServer/agents), prioritizing maintained, tested implementations linked in PLAN.md.

See [LICENSE](LICENSE) (GPL-3.0). Preserve attribution and verify license compatibility when copying code or distributing C0 Core.
