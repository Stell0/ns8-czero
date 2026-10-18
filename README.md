# C0 (Czero) — Application foundation for NethServer 8

**Status (18 October 2026): Agent Memory AM0–AM4 runtime acceptance passes.** The dedicated instance runs main `878978d`, with Core **0.28.0**, app **0.43.0** and schema **0016**. Agents can use protected spaces, ingest bounded evidence, revise Wiki pages safely, annotate exact content and search structured records with exact applicability filters. Current/legacy SDK workflows, fresh consent, supported update/restart, preservation and bounded journal privacy pass. The existing cached connector separately reconnects and reads retained Shared citations and historical Wiki content; new tools through its 63-operation catalog are not claimed.

Exact main passes 1127 Python/PostgreSQL/packaging cases, 125 scripts, producer/released-Core/Renovate and both native distributions: Debian genuine AM3 upgrade twenty passes, Rocky installation twenty-five passes/three expected skips, all eight browser/privacy workflows and twenty-five accessibility contexts. Actual source checkouts, image/scan artifacts and three OAuth-query artifacts are audited. See [PLAN.md](PLAN.md) for immutable Core artifacts, deployed results and frozen installed digests. The final AM4 marker/main `d889902` also passes its actual CI/native/artifact gates. AM5 consolidation is in progress; AM6 and Windmill Gate remain gated. Interactive Playwright and CPU-quota waivers persist; no stable module release is claimed.


## Applicability and structured retrieval (AM4)

Core 0.28 is independently published and app 0.43 pins its verified immutable
release. The dedicated instance accepts this behavior on main 878978d.
Applicability and verification describe
exact content through separate revisioned annotations. They do not rewrite source
evidence, article revisions or strict record payloads. Missing metadata is unknown;
changed content never inherits verification. C0 stores the observations supplied
by authorized editors; external agents assess and consolidate knowledge.

The application adds `knowledge_annotations_get`, `knowledge_annotations_history`,
`knowledge_annotations_update` and `knowledge_search_structured` with matching
REST operations. An annotation target uses its kind, content UUID and observed
revision: source versions and article revisions use their immutable UUIDs;
entities, objects and claims use their record UUIDs. Annotation reads/history
need read scope; changes need Editor authority in that space and write scope.
Zero is create-only for the expected annotation revision. Conflicts require a new
read, reconciliation and a new retry key; an unchanged retry returns the original
snapshot. Unknown status/extension values and explicit nullable observations are
preserved. Source verification requires ready extraction.

`POST /api/v1/knowledge/search/structured` is read-only and accepts `query`,
optional body `space_id`, `filters`, `limit`, `mode` and `rerank`. Query-string space selectors are rejected on this endpoint. Filters include
categories (`source`, `wiki`, `entity`, `object`, `claim`), products, components,
exact version tags, applicability statuses, verification statuses, archive
selection and inclusive UTC creation/observation/verification intervals. Supplied
fields combine with AND, values within a field with OR. An empty supplied list
is invalid. `8.4` matches exactly, without version-range or prefix expansion.
Unfiltered unknown metadata stays visible; an explicit `unknown` status matches
missing annotations. Omitted categories retain source/Wiki selection.

Structured results identify their space, observed resource revision and independent
annotation revisions/statuses. Immutable source citations and article revisions
remain separate from mutable record references; claim evidence references resolve
to immutable chunks. Entity/object/claim retrieval uses deterministic text.
Optional semantic/hybrid/reranking applies to eligible source/Wiki evidence and
reports its actual method/fallback. Ordinary `/api/v1/knowledge/search` keeps its
existing behavior and response contract. Space and applicability filters precede
candidate limits, counts, ranking, vector pruning and provider inputs.

For example, use this body with the structured REST endpoint (or as `data` for
`knowledge_search_structured`), replacing the space UUID:

```json
{"query":"getent","space_id":"<space-uuid>","mode":"text","filters":{"categories":["wiki","entity"],"products":["NS8"],"version_tags":["8.4"],"verification_statuses":["verified"]}}
```

Annotation REST paths are
`/api/v1/knowledge/annotations/{kind}/{target_id}/{content_revision}/{namespace}`,
with GET for reads, PUT for changes and GET `/history` for history. Supply the
same optional `space_id` query selector. A verification update body can be:

```json
{"value":{"status":"verified","verified_at":"2026-10-18T00:00:00Z","confidence":0.9},"expected_revision":0,"idempotency_key":"verify-observation-1"}
```

The `applicability` namespace supports literal product/component/version tags,
status, observation time, confidence and bounded extensions; `verification` has
its own status, observation/verification times, confidence and extensions. Times
require a timezone and normalize to UTC. New REST bodies retain the existing one-MiB knowledge request bound;
annotation values retain the existing 16-KiB JSON budget. Existing MCP request and
response bounds remain unchanged. Exact-source CI/native/publication and dedicated
update/restart acceptance pass, including all five target histories and changed
content returning unknown verification. The final documentation marker's actual
checks and main publication are verified in PLAN; AM5 remains in progress.

## Purpose and boundaries

C0 is a deployable application foundation and a forkable GitHub template. External coding agents can extend its shared operations and application UI while retaining native NethServer lifecycle, packaging and tests. C0 Core lives in `packages/czero-core`; fork-specific business logic belongs in `app`.

One installed C0 module owns a dedicated PostgreSQL instance and a permanent legacy Shared space. Protected spaces use explicit Reader/Editor grants; application Admins access all spaces. There is one owner and optional Reader, Editor and Admin application membership. This does not introduce per-document permissions or separate tenants.

Generic JSON Schema objects and deterministic jobs work now. M08 document evidence/source FTS pass local, native and permitted live tests; authored Wiki/claims and bounded PostgreSQL graph pass local, native and permitted live acceptance; optional retrieval passes acceptance; authenticated remote MCP and its discovery/OpenAPI connection metadata pass installed and permitted live owner acceptance. C0 stores and serves knowledge; external harnesses perform reasoning, research and wiki synthesis. No generative LLM, autonomous agent, scheduled AI prompts, local inference, arbitrary user shell jobs or second graph database belongs in the runtime.

## Current interfaces

Configure an application hostname in NS8 Settings. Older M01 installations retain `/czero/<module-id>` on the cluster host until hostname configuration.

| Path | Available behavior |
| --- | --- |
| `/` | Automatic knowledge home with sections and recent articles; account/sharing and service details at `/?view=account` |
| `/sources` | Readable source library, versioned extracted text and citation links; manual upload/retry/archive at `/sources?view=tools` |
| `/search` | Article/source search with linked excerpts; retrieval tuning and citation diagnostics under details |
| `/wiki` | Article reader, progressive page tree, linked facts/evidence and history; manual knowledge editing at `/wiki?view=tools` |
| `/api/v1/spaces`, `/api/v1/spaces/<id>`, `/api/v1/spaces/<id>/grants` | Authorized space discovery, Admin creation and revisioned grant management; protected content uses explicit `space_id` |
| `/api/v1/wiki/pages/resolve`, `/api/v1/wiki/pages/upsert` | Exact-slug lookup and create-only or expected-revision-checked updates; immutable history and original retry receipts |
| `/api/v1/wiki/pages`, `/api/v1/entities`, `/api/v1/claims`, `/api/v1/knowledge/graph/<id>`, `/api/v1/knowledge/changes` | Versioned Wiki, aliases, sourced assertions, bounded graph and change cursors; signed local REST, real disposable SSO/update/restore and permitted live owner acceptance verified |
| `/objects` | Schema-derived record fields, explicit advanced JSON, revisions and typed relation browsing; real disposable browser verified |
| `/admin` | Admin-only public-client approval/disable, deterministic jobs/attempts and UTC schedules; real disposable all-role browser verified |
| `/api/v1/object-types`, `/api/v1/objects`, `/api/v1/objects/batch` | Authenticated type inspection/registration, CRUD, paging/filters and atomic batches |
| `/api/v1/object-relations`, `/api/v1/objects/<id>/relations`, `/api/v1/object-events`, `/api/v1/references/<kind>/<id>` | Typed object edges, metadata changes and trusted registered reference resolution |
| `/api/v1/sources/ingest-text` | Bounded plain-text/Markdown evidence through REST and `sources_ingest_text`; poll extraction before using immutable chunks |
| `/api/v1/sources`, `/api/v1/sources/upload`, `/api/v1/sources/search` | Authenticated source browse, bounded queued uploads and sourced PostgreSQL text search; native and permitted live acceptance verified |
| `/api/v1/source-versions/<id>/document`, `/api/v1/documents/<id>/chunks`, `/api/v1/chunks/<id>/citation` | Retained full text, offsets/location chunks and stable citations |
| `/api/v1/knowledge/search` | Source/current-Wiki FTS with stable citations and bounded exact excerpts; installed provider-free acceptance verified; optional configured retrieval passes disposable acceptance |
| /api/v1/knowledge/index/status | Reader inspection of configured profile/generation and derivative row count; no provider credentials or URLs |
| `/api/v1/health` | Public Core/app versions and PostgreSQL/schema/vector readiness |
| `/api/v1/auth/status` | Public indication that authentication is configured |
| `/auth/login`, `/auth/callback` | OIDC authorization-code login with PKCE, one-use state and nonce |
| `POST /auth/logout` | Local session revocation and provider logout URL |
| `GET /api/v1/me` | Authenticated profile and current application role |
| `GET /api/v1/access/accounts` | Admin list of verified profiles and grants |
| `PUT /api/v1/access/accounts/<id>` | Admin grant/revocation of Reader, Editor or Admin |
| `/api/v1/oauth/clients`, `/api/v1/oauth/clients/<id>` | Admin approval of public clients, exact callbacks/scopes and revision-protected enable/disable; installed/live acceptance passes |
| `/api/v1/jobs`, `/api/v1/jobs/handlers`, `/api/v1/jobs/<id>`, `/api/v1/jobs/<id>/runs` | Admin inspection and idempotent enqueue of registered jobs |
| `/api/v1/schedules`, `/api/v1/schedules/<id>`, `/api/v1/schedules/<id>/runs` | Admin create/list/configure UTC interval schedules and inspect run state |
| `/mcp` | OAuth-protected Streamable HTTP tools and bounded knowledge resources, for configured hostname-root instances |
| `/oauth/authorize`, `/oauth/consent`, `/oauth/token`, `/oauth/revoke` | Explicit native-SSO consent, S256 codes, scoped tokens, rotating refresh and revocation |
| `/openapi.json`, `/docs` | REST schemas, role/scope metadata, safe connection metadata and Swagger UI |
| `/agents`, `/agents/capabilities.json` | Use with AI guide and role-aware task instructions; original caller-aware technical reference at `/agents?view=tools`; capability JSON unchanged |

Core/app versions are **0.28.0/0.43.0**, with migrations through `0016_annotations`. The accepted dedicated runtime is `878978d`; earlier M14, reader UI, Integration M15/M16 and structured-object acceptance remains recorded in PLAN. Public health returns HTTP 200 when PostgreSQL/schema/pgvector are ready, or safe HTTP 503 with a database reason. Authentication status reports configuration rather than provider reachability. Swagger loads CDN assets; OpenAPI JSON remains usable without them.

Objects, sources, immutable documents/citations, Wiki/claims/graph and optional retrieval pass local PostgreSQL-backed HTTP, real disposable SSO/browser, native recovery and permitted live acceptance. Readers inspect permitted content; Editors author/upload within their effective space role; Admins register schemas and manage spaces, grants, membership, clients and jobs. No per-document ACL exists. Optional providers stay disabled in live checks.

Use `/agents` for connection/task guidance; open `/agents?view=tools` or `/agents/capabilities.json` to inspect your current role's operations. The trusted catalog binds seventy-one typed JSON REST operations to the same handlers/DTOs used by MCP. Anonymous discovery lists no private operations; invalid credentials fail closed. OpenAPI contains operation role/scope requirements and `x-c0-interfaces` connection metadata. Multipart uploads, retained-original downloads and Markdown exports remain REST attachments. Legacy instance-prefix and unconfigured instances retain REST and report MCP unavailable.

External-client approval uses Admin GET/POST `/api/v1/oauth/clients` and PUT `/api/v1/oauth/clients/<id>`. Register `client_name`, one to four exact HTTPS `redirect_uris` (HTTP only for literal loopback), and `allowed_scopes` from `c0:read`, `c0:write`, `c0:admin`. Approval grants no user membership or token. Public clients use `token_endpoint_auth_method=none`; no client secret, dynamic registration or callback fetch exists. Identical registrations preserve disabled state; enable/disable requires `expected_revision` and invalidates old authority. Callbacks/scopes are immutable: register a new descriptor to change them. The instance caps registrations at sixty-four, including disabled clients, with sixteen KiB requests.

To connect a compatible MCP client:

1. Configure NS8 sign-in and hostname-root routing. An application Admin approves the client's exact callback and requested scopes through the authenticated REST endpoint, using its cookie session/Origin/CSRF contract or a verified native bearer token.
2. Configure the client with the canonical `https://<application-host>/mcp` URL and returned public client ID, without a secret. Discover protected-resource and authorization metadata using the URLs on `/agents`.
3. Follow browser sign-in and explicit consent. Use S256 and the exact MCP URL as `resource` for authorization and token/refresh requests. Your persisted role limits granted scopes and every operation.
4. Use the returned opaque access token for MCP or matching REST operations. Refresh rotates tokens; reusing an old refresh revokes its family. Explicit `/oauth/revoke`, client disable or membership changes revoke authority.

Grants last at most one hour and no later than the originating sign-in expiry; access tokens/codes last at most five minutes. Signing out of the browser does not revoke delegated client access. Native update/restart preserves bounded refresh authority; clean restore allocates a new native client and rejects old grants, requiring fresh sign-in/consent. Real SDK 2.3.0 current/legacy transport and local automatic OAuth discovery/exchange pass. The operator first confirmed actual ChatGPT connection/content reading on M15 source `6c02182`; current M16 acceptance is recorded below. Bounded application logs corroborate successful token exchange and MCP requests without OAuth-query leakage. Scheduled-run interoperability remains unverified; no scheduled task was created. The accepted Integration M15 compatibility fix accepts optional authorization parameters (for example `ui_locales`) on GET and form POST, ignores them before trusted authorization processing, and still rejects duplicate names. Token and revocation endpoints continue rejecting unknown fields. Exact callback/resource matching, S256, explicit consent and role-limited scope selection remain required. The fix was merged to main and originally deployed as `6c02182`; it remains in current runtime `9582568`. Exact-source CI and native upgrade/install/browser checks pass. Trusted-HTTPS checks now reach consent, preserve duplicate rejection and retain all existing data/settings and unrelated applications. The real ChatGPT connection/authenticated-read gate now passes. The operator also confirms signed-in Wiki/REST and client-disable/rejected-read/re-enable/reconnect acceptance. Integration M15 runtime acceptance is complete; completion marker `86c8b0a` passed its exact native/artifact checks and main local/publication before Integration M16 began. Exact granted scopes and the specific read tool used were not separately reported. Later milestones cover stable profiles, tool guidance, optional secure CIMD and measured delegated-session reliability; none is claimed implemented.

Integration M16 is accepted: its runtime passed exact-source CI/native checks and dedicated deployment, and the operator confirms the live OAuth checks in addition to the comprehensive 20/20 API report. Each MCP tool advertises its existing required OAuth scope in `securitySchemes` and a matching `_meta.securitySchemes` compatibility mirror. Tools available to your persisted role remain discoverable when your current token needs additional consent. Calling such a tool returns an `insufficient_scope` error with `_meta["mcp/www_authenticate"]`; a role denial remains denied without a scope-upgrade challenge. Initial resource discovery requests read access, while authorization-server metadata lists all supported scopes. A client must retain previously granted scopes when requesting a legitimate upgrade through explicit consent; refreshing cannot add authority. Resources and REST capabilities continue reflecting current granted scopes. These optional MCP extensions reuse existing Core authorization and preserve current/legacy SDK compatibility. Accepted `9582568` remains the historical structured-object runtime evidence; the subsequent AM0 deployment at `b66e159` is recorded below and preserves its behavior and data. Operator-reported live OAuth acceptance is distinct from CI/SDK checks and server-observed logs. The API exercise itself excludes new multi-format ingestion, batch rollback, invalid-write/conflict tests, replay/deduplication, job/scheduler execution, auth/restart durability and confirmation of the five original pilot sources as retained evidence; independent repository coverage remains valid. The test object was deleted and the claim retracted; immutable schema/history and other isolated regression data are not claimed removed. M17 is next after this documentation marker is verified. See [PLAN.md](PLAN.md) for acceptance gates and official protocol references.

M12 provides consistent local navigation and keyboard focus across the home, records, sources, Wiki, search and agent pages. Home links the main human workflows and retains service/API details. The agent page offers canonical URL copying with manual fallback. Sharing and availability refreshes ignore older responses, and role writes preserve newer selections. Installed navigation, focus, sharing and copying pass the disposable browser workflows; permitted live owner normal-TLS asset/API and full-manager restart checks also pass. Interactive live browser testing remains waived.

Records offer labelled fields derived from the registered schema, including optional omission, numeric limits, typed choices/constants and nested JSON. Use “Advanced JSON editor” for direct JSON, with the same authoritative server validation. Newer drafts survive earlier saves; record revisions still detect conflicts. Browse target records of the selected type or enter an ID to add a typed relation. Reader fields are disabled. Installed generated fields, advanced JSON, relation browsing and Reader controls pass disposable browser acceptance; permitted live owner normal-TLS asset/API and full-manager restart checks also pass. Interactive live browser testing remains waived.

M12 also protects source evidence selection: the latest clicked chunk keeps its citation, query edits clear old results, source metadata lookup preserves newer typing, and busy uploads cannot submit twice. Existing ingestion, retention and search contracts stay the same. Disposable native tests pass on both distributions with real source upload/history/search/Reader browser checks on Rocky; permitted live owner persistence also passes.

M12 provides readable Wiki graph entity/relationship/reference lists with click-through entity navigation and safe typed metadata links. Missing resources keep their saved label and an explicit missing marker. Expand Graph JSON for the exact transport data. Graph option changes invalidate prior evidence; edits typed during a page save remain in the draft with the newly saved revision. Disposable native checks pass on both distributions, with graph, provenance, revision and Reader browser checks on Rocky; permitted live owner normal-TLS asset/API and full-manager restart checks also pass. Interactive live browser testing remains waived.

M12 provides native Status cards for actual database/schema/vector readiness, sign-in connectivity, timer/worker state and optional retrieval configuration. Refresh uses existing native tasks and a small Core-backed runtime check; it does not test inference connectivity or quality. Cold/unavailable applications show a check failure, not a ready state. Disposable native checks pass on both distributions, with real administration browser checks on Rocky; permitted live owner normal-TLS asset/API and full-manager restart checks also pass. Interactive live browser testing remains waived.

M12 provides an Administration page for application Admins: approve exact public-client callbacks/scopes, enable/disable with revision checks, queue registered deterministic handlers with replay protection, inspect attempts, and create/pause UTC interval schedules. It uses existing REST/CSRF permissions; Readers and Editors cannot manage these controls. Hostname, identity and optional-provider credentials stay in NS8 settings. Job/schedule lists show at most fifty rows; refresh to inspect recent state. Disposable native checks pass on both distributions, with actual worker/client/schedule and all-role browser acceptance on Rocky; permitted live owner normal-TLS asset/API and full-manager restart checks also pass. Interactive live browser testing remains waived.


## Knowledge website (M15 accepted)

The end-user application now defaults to reading: compact documentation/wiki navigation, formatted articles, a source library and simple search. Manual creation, upload and editing live in **Tools**. **Account** contains sharing for Admins; Administration retains clients, jobs and schedules. NS8 settings and all domain APIs are unchanged.

Home automatically shows sections represented by the latest page summaries and up to eight recently updated articles. Knowledge builds a tree from existing slash-separated slugs, loading 100 summaries per batch with **Load more articles** while incomplete. Flat slugs stay at the top level; absent parent pages become navigation groups. Slugs are fixed: this UI does not move existing pages. Search works across the collection independently of the loaded tree, with Articles, Sources and All filters.

Article URLs use `/wiki?page=<id>` and optional `revision=<number>`. The reader safely formats Markdown, with a table of contents and page-linked sourced assertions. Conflicting assertions remain separate; evidence links pin their source version and passage. Historical revisions retain their own title/body and omit current assertions. Source links use `/sources?source=<id>&version=<id>&chunk=<id>`; extraction text remains literal and citation identity is checked before displaying the passage. Originals are downloadable only when actually retained/available. Histories and lists have explicit paging.

Markdown uses locally bundled markdown-it 15.0.2 (MIT), verified against the npm archive integrity with its license included. An allowlisted token renderer creates DOM elements; raw HTML, remote images and executable/credentialed links stay inactive. No external UI assets are required. Narrow layouts collapse navigation and move article context below the reading column.

**Use with AI** explains administrator-approved remote MCP setup and offers copyable research instructions, plus create/update/import recipes for Editors/Admins. Articles offer their own context-specific instructions. These are tasks for an external assistant: there is no integrated chat or generative runtime. Authorized writes publish directly and preserve history. Binary ingestion still needs an authorized REST-upload-capable client; it is not an MCP tool. No particular provider/client interoperability is implied.

Reader UI marker `05713b9` is merged to main and its local, publication, released-Core and both-native workflows are completed/successful. M15 in PLAN.md retains the initially failing browser evidence and verified correction. The dedicated instance includes this UI and originally accepted the separate Integration M15 OAuth compatibility source `6c02182`; the operator confirms actual ChatGPT connection and authenticated content reading, and also confirms signed-in Wiki/REST and client revocation/reconnect acceptance. Interactive UI and CPU-quota waivers persist; the real ChatGPT gate is required.

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

M12 provides a useful access-denied page and “Sign in with another account” retry. It requests fresh provider authentication; if the provider retains the name, use its restart/switch-account control. It clears an earlier C0 session after failed switching and preserves the ordinary sign-in bindings and access rules. Local signed HTTP covers root/legacy routes, fresh/existing cookies, state replay and admission; actual disposable account-switch browser acceptance now passes, including the provider restart control. The stronger timer/outage fixture passes on both distributions, as do permitted live owner update/restart checks. The completion marker passes. Accounts still need an explicit owner/Admin membership grant.

Native registration/binding is not a distributed transaction. A failed cross-module change reports an error and keeps the previous secret file, but may require re-saving the previous selection and hostname. Configured native update and encrypted clean restore preserve owner/member account IDs and saved roles, verified on Debian and Rocky. Restore re-registers the client for the new native module identity.

The current upstream IdP has no stable GitHub release; its README's `1.0.0` image is unavailable. Disposable tests pin a verified main image and require the upstream `ldapproxy:1.4.0-dev.1` listener fix for Keycloak pod access. These are development dependencies. Compatible stable IdP/proxy availability is a release prerequisite; no live proxy has been modified.

## Persistence and backup

Each module has PostgreSQL **17.11** plus pgvector **0.8.7**, a private pod and its own `czero-db-data` volume/password. Database ports are not published. Native startup runs packaged migrations before the app; repeated migration, restart, pod recreation and upgrades preserve data and knowledge-space identity.

Use the native NS8 Backup page to select Czero and a supported destination, run backup and verify a snapshot. Restore uses a clean module slot with its hostname available. Archives contain an atomic PostgreSQL custom dump, private configuration, service-state metadata and the retained-source volume; live database files are excluded. Offline restore uses fail-fast transactional `pg_restore`, retains the new native module ID/port and Core-assigned logical UUID and restores the prior enabled/running state. A completed-archive receipt permits replay without overwriting later database changes. Debian/Rocky native tests verify these baseline behaviors.

The source volume stores generated-ID originals with restricted permissions. Extraction commits full text/chunks before a separate cleanup job removes default originals. Explicitly retained and failed originals remain. Native backup now stops the app, worker and timer through both the SQL dump and volume copy, then restores their prior active states. Local and actual native copy-window checks verify writer quiescence; encrypted native restore preserves full text, versions, chunks, citations and retained/quarantined originals.

M06 currently adds Core queue/schedule storage and services with registered deterministic health/maintenance handlers, validated idempotency and Admin authorization. Standalone worker execution and authenticated REST pass local database tests. Native timer/one-shot execution, due-once runs, restart and backup/restore pass Debian/Rocky QEMU. Permitted live timer completion and API persistence pass.

Admins can POST `{"handler":"health","payload":{},"idempotency_key":"health-check-1"}` to `/api/v1/jobs`. Repeating the same request returns the same job; a conflicting handler/payload returns 409. Registered `health`/`maintenance` accept empty payloads; trusted `source.extract`/`source.cleanup` accept a version UUID and serve the ingestion pipeline. Schedule intervals range from 60 seconds to 31 days; missed intervals coalesce to one due run. Pausing stops future scheduling; queued jobs may complete. Worker attempts and terminal state survive restarts; failed attempts use bounded backoff. Handlers use one database transaction for effects/completion, and must make file/network effects idempotent. Job history retention is 30 days with bounded weekly pruning. The native timer wakes about one minute after activation and one minute after worker completion. Python handler deadlines are capped at 30 seconds and the native container at 150 seconds. The worker is idle between runs; `get-scheduler-status` reports timer, running and failure state. Backup pauses worker/timer through the copy and restores prior timer state. These native behaviors pass disposable QEMU; permitted live timer completion, idempotency, schedule/job/identity persistence and unchanged unrelated inventory also pass.

There is no full jobs/schedules application page yet; use the authenticated API/OpenAPI. The worker processes at most twenty jobs per wake within its bounded budget, serially. Python deadlines cannot preempt every extension call; the native container lifetime guard bounds those cases. External/file effects remain at-least-once and must be idempotent. Foreground source-file backup coordination is covered by local tests; a disposable observer checks actual writer states during Restic copy.

M07 Core implements immutable type registration, JSONB records, tags, optimistic revisions, optional top-level scalar uniqueness, atomic batches, typed object relations and paginated events. The REST transport passes signed local PostgreSQL tests; the record page passes actual repeatable QEMU browser assertions for owner forms, refresh, hostile-text rendering and Reader controls. Schemas support a bounded Draft 2020-12 subset: explicit types, properties/required, arrays, scalar bounds, enum and const. Remote/recursive references, regexes, combinators, `format` and unknown properties are rejected; validation never fetches URLs. Objects are capped at 64 KiB, batches at 25 operations/256 KiB, and reads at 100 rows. Existing object relations use foreign keys. Trusted application code can register relational reference resolvers; the app also registers bounded source/document/chunk reference metadata; The app registers bounded page/entity/claim metadata references.

On the Records page, choose a type, browse or open a record, and use New record or Save record with the labelled schema fields and comma-separated tags. Expand Advanced JSON editor for direct JSON; editing it explicitly switches the form to JSON mode. Browse target records of a selected type to add a relation, or enter its ID. Invalid schema values report the field/keyword. A revision conflict preserves the local draft; Load saved version explicitly refreshes it. Admins can expand Register a record type, enter its name/label/schema and optional unique scalar fields. Types are immutable. The type picker shows the first 100 definitions and record paging uses 50 rows; the API exposes paging and equality/containment filters. Optional fields distinguish omission from empty, false and null; nested values use bounded JSON. Reader fields are disabled.

Unique string fields must explicitly declare `maxLength` of at most **128**. A string without `maxLength` uses the general **8192** default and cannot be a unique key. REST and MCP return `unique_string_too_long` for an unbounded unique string; tool descriptions and input schemas explain the limit. Invalid or unsupported schemas return `invalid_schema` or `unsupported_schema`; invalid records return `record_invalid:<path>:<keyword>`. MCP errors include the public code and equivalent HTTP status in `_meta["c0/error"]`. Unexpected internal errors remain generic. These adapter changes preserve the existing schema and uniqueness validation. The repair is deployed and verified through the actual connected MCP tools: the original unbounded unique schema receives the precise code, while a bounded type is created and returned by get/list. Existing types and data remain unchanged. The expanded 812-case local suite independently checks REST and current/legacy MCP typed CRUD, required/type/closed-schema validation, unique/type/stale-revision conflicts, type isolation and role/scope/revocation denial. Both native distributions pass complete current/legacy CRUD after explicit Admin consent, including non-browser installations. The deployed connected MCP tools pass type create/get/list, record create/get/query, optimistic update/re-read, invalid-record rejection, unique/type/stale-revision conflicts and delete/absence. Independent observers preserve existing pilot data and settings. The two isolated empty regression types and audit history remain because definitions are immutable; test records are deleted. Separate ChatGPT UI prompt orchestration was not observed during M3; subsequent operator-provided M16 acceptance is recorded above. See the structured-object repair evidence in PLAN.md. Type creation requires application Admin permission and delegated `c0:admin`; ordinary record mutations require Editor and `c0:write`. Successful entity writes alone do not establish type-registration authority.

A URL field such as `source_url` can use an ordinary bounded string; URL formats are not interpreted or fetched. Duplicate type names and unique values return `object_conflict` (HTTP 409), as do stale expected revisions. Type definitions remain immutable; there is no type deletion endpoint.

For example, register `inventory` with `{"type":"object","properties":{"name":{"type":"string","maxLength":64}},"required":["name"]}` and `unique_fields:["name"]` at `/api/v1/object-types`; POST `{"type_name":"inventory","data":{"name":"Rack A"},"tags":["inventory"]}` to `/api/v1/objects`. PUT the record with `data` and `expected_revision` from its last response. Cookie writes require the existing CSRF token; bearer requests use the signed access token.

Native manager restart exposed a systemd app/timer/basic-target ordering cycle. The corrected timer keeps explicit app/shutdown bindings without default boot-target ordering. Actual Debian/Rocky manager restarts pass with no C0 ordering-cycle journal lines; three live manager restarts recover an active/successful timer and preserve object/job/schedule/configuration state. The native scheduler diagnostic includes bounded timer state/result/dependency names. App-only restart tests remain insufficient for this path.

M08 now adds isolated deterministic Text/Markdown/PDF/DOCX extraction, source/version/document/chunk storage, citations, source full-text search and typed REST. These pass local PostgreSQL-backed tests, real native SSO/browser/update/restore and permitted live ingestion/restart checks. Child limits cap memory/CPU/time, input bytes, text, PDF pages and archive expansion. Unsupported encrypted/scanned PDFs and unsafe/unsupported DOCX structures fail with static error codes and preserve the input file. The parser supports DOCX body, tables and defined headers/footers; notes/comments/macros and unsupported text controls, tracked changes, textboxes and simple fields are rejected to preserve incomplete originals. No OCR or provider credential is required. Ingestion acceptance and final documentation CI pass.


Use authenticated `POST /api/v1/sources/upload` multipart fields `file`, `title`, `media_type`, optional `metadata` JSON and `retain_original=true|false`. The four MIME types are text/plain, text/markdown, application/pdf and application/vnd.openxmlformats-officedocument.wordprocessingml.document. Upload returns HTTP 202 and a version UUID; poll `/api/v1/sources/<source-id>/versions` for queued/ready/failed state. Initial identical uploads with matching title/metadata/media deduplicate. To add changed content, include `source_id` and `expected_revision`; conflicts return 409. Different provenance remains a separate source. Source title/provenance are established by the first upload; existing-source uploads add versions and retain that source metadata. Version content/retention are immutable.

AM1 adds `sources_ingest_text` for selected, sanitized text evidence.
It requires Editor permission and delegated `c0:write`; use `c0:read` to inspect
extraction and citations. MCP arguments use the catalog's `data` object:

```json
{"data":{"idempotency_key":"investigation-42:evidence-1","title":"Service observation","body":"Observed a readiness failure; retain this observation as evidence.","media_type":"text/plain","metadata":{"origin":"external investigation"}}}
```

REST accepts the inner object at `POST /api/v1/sources/ingest-text` and returns
202. Plain text and Markdown are limited to **131072 UTF-8 bytes (128 KiB)**;
metadata uses the existing 16 KiB JSON limit. The serialized REST/MCP request
remains bounded to one MiB. Empty/whitespace-only text, NUL, invalid Unicode,
unsupported media and invalid metadata are rejected with safe static errors.
C0 stores the submitted evidence; it does not sanitize secrets for the caller or
execute instructions found in it.

The receipt contains source `source_id`, version `id`, content hash, job ID and
submission state. Reuse an unchanged actor/key after a timeout; a changed payload
conflicts. Keys share the existing Wiki/knowledge receipt namespace, so use a
separate key for each intended mutation. A replay returns its original snapshot,
even when its state is still `queued`. Poll `source_versions_list`, then use
`documents_get`, `document_chunks_list` and `citations_get` once the version is
ready. `claims_create` still requires actual immutable evidence chunks. Optional
indexing is unnecessary for ingestion and text search.

To append a version, fetch the source's current revision and send `source_id`,
`expected_revision`, its unchanged title/metadata and a fresh key with the new
text. A stale revision conflicts; replaying the winning request remains safe.
Existing source provenance, old versions and citations are preserved. The new
operation uses the same extraction, cleanup, restart and native backup pipeline
as file ingestion. Reviewed main `48937e1` is deployed with this operation;
the older 63 operation contracts are preserved.

If reconnecting an external client shows `invalid_session` at `/oauth/consent`,
start a fresh sign-in at `/auth/login?switch_account=true`, then restart the
client's authorization flow. A pending consent request expires after five
minutes. App 0.40.1's proposed recovery fix sends a stale C0 browser cookie through
normal sign-in while retaining a valid pending request; it does not extend
session/grant lifetimes or approve consent. That fix still needs reviewed CI,
main promotion and deployment; the deployed app remains 0.40.0.
The recovery candidate passes 870 local Python/PostgreSQL/packaging tests,
106 script tests, schema/shell checks and nineteen Robot dry-run cases. Its
actual image/native checks and review remain required before deployment.

Readers browse sources, documents, chunks, citations and retained/failed original attachments. Editors ingest, retry with `expected_generation`, and archive with `expected_revision`. Source deletion archives it from browse/search while preserving historical evidence and citations. Get full text at `/api/v1/source-versions/<id>/document`, chunks at `/api/v1/documents/<id>/chunks`, a citation at `/api/v1/chunks/<id>/citation`, and bounded FTS at `/api/v1/sources/search?query=inventory`. Downloads at `/api/v1/source-versions/<id>/original` use attachments/octet-stream. Uncertain database commit failures preserve generated originals for operator recovery; automatic orphan reconciliation is not yet implemented. The separate Sources page now offers upload/retention, history/full text/citations, FTS, quarantine/retry and archive controls; ten record/source Node race tests pass. Repeatable native owner/Reader browser workflows pass; interactive Playwright remains waived.

The runtime builder removes dependency-wheel development headers and Cython sources; compiled parser libraries and required runtime data remain.

On the Sources page, expand Upload evidence, choose a file/format, enter a title and provenance JSON, and optionally retain its original. Choose an existing source to add a version. Pending history refreshes about every four seconds until complete; choosing a ready version shows full text, chunks and citations. Failed files display a bounded reason and download/retry controls. Readers can browse/search and inspect historical evidence; Editors can upload/retry/archive. Archiving preserves existing citations. The browse/upload picker shows fifty sources per page, history up to one hundred versions and text search up to twenty matches; the REST endpoints provide paging.

Permitted live owner tests verify all four formats, deduplication, changed versions, FTS/citations, default deletion, retention, quarantine and retry. A DOCX content-control file remains intact with `unsupported_docx` and no partial document. Native restart preserves evidence and existing object/job/schedule/configuration state; unrelated inventory stays unchanged. Native Debian installation and Rocky update/browser suites pass. Reader/Editor/Admin source boundaries and encrypted restore are tested in disposable instances; a second live persona and live destructive restore were not exercised.

M09 adds authored Wiki pages with immutable revisions, optimistic edits, replay-safe mutations, archive history, Markdown/JSON export, entities/aliases and metadata change cursors. Core also provides sourced immutable assertions, evidence annotation/retraction, entity relations and bounded graph traversal. Typed REST and the minimal Wiki editor pass signed local HTTP, real disposable SSO/browser/update/restore and permitted live owner tests. Raw extracted evidence remains separate from authored Wiki data.

Claim values/entity/predicate/time are immutable assertions; record conflicting values as additional claims. Annotation adds metadata/evidence and retraction preserves it. Traversal is bounded to 1–3 hops, thirty-two active incident entity relations, at most one hundred returned entities/references and an explicit truncated flag. Typed references retain a missing-object marker after object deletion.

Wiki typed REST and the minimal page pass local, installed and permitted live acceptance. Open Tools → Articles and knowledge model, create a fixed slug/title/Markdown page, save with metadata and inspect immutable revisions or export Markdown/JSON. Reader controls permit inspection; Editors author pages/entities/claims/relationships. Every claim requires real evidence chunk IDs from Sources; conflicting values coexist and retraction preserves provenance. Select an entity to inspect its claims/citations and 1–3-hop graph. Names/data render as text; Markdown is not executed or rendered as HTML.

Knowledge POST/PUT bodies require `idempotency_key`; edits/archive/retraction require `expected_revision`. A replay returns its original snapshot; reused keys with changed payload and stale edits return 409. Page bodies cap at 128 KiB, metadata/value at 16 KiB, entity aliases at sixteen, active incident edges and typed references at thirty-two, reads at one hundred. Graph results report truncation. Entities show the first one hundred entries in the picker; bounded graph results offer entity navigation and readable relationships/references, with missing resources marked explicitly and exact JSON under details. Native update/encrypted backup/clean restore preserve exact Wiki data. Permitted live owner CRUD/exports/replay/CAS/CSRF and full native restart preserve knowledge, prior sources/objects/jobs, configuration and unrelated inventory. Interactive Playwright remains waived; only the owner persona was used live, with all roles verified in disposable tests.


Knowledge search is available at /search and GET /api/v1/knowledge/search. Source chunks retain complete citations; Wiki hits carry immutable revision IDs/hashes and exact excerpt offsets. Only current active Wiki revisions rank. Query text caps at 512 characters; result limits at fifty. Text mode works independently of all optional providers and indexing jobs. Semantic/hybrid requests without embeddings disclose embeddings_not_configured and preserve text results. Unknown request fields are rejected.

In NS8 Settings, optional embeddings require a full HTTPS endpoint, pinned model, expected dimensions (1–2000) and optional API key. A bounded trusted worker indexes source/Wiki chunks in batches of eight. Full-precision normalized vectors are zero-padded to 2000 dimensions; exact profile/model/dimension/generation filters prevent mixing. Model changes create separate profiles; reindex hides old generations without altering evidence. Repeated startup preserves an explicit schedule pause. Reader index status is available at /api/v1/knowledge/index/status.

Optional System One uses the common Jev/Kev model/state/questions/answers Noul protocol, with off/rerank/filter administration modes. Pin resolved Kev model IDs rather than latest aliases. Rerank evaluates at most sixteen candidates and preserves the unscored tail; filter returns only evaluated candidates above the model-specific threshold. Providers have absolute deadlines up to five seconds, byte/input limits and verified TLS, without redirect/proxy inheritance. Keys stay private in backed-up configuration and cannot be supplied through user requests. Providers receive query/text data; approve their data handling before enabling.

Use mode=text|semantic|hybrid|auto, kind=all|source|wiki, graph_depth=0|1|2|3 and rerank=off|rerank|filter within administrator caps. Graphs are supplemental unscored context, separate from ranked evidence, using at most three roots/sixteen nodes each. Fallback reasons, considered/scored counts, truncation and safe token usage are explicit. Search provider calls release database connections and recheck persisted roles before returning. Background indexing uses the existing bounded worker transaction so failed provider calls roll back derivative changes.

The minimal search page renders literal evidence/citations and ignores stale responses. Local protocol, database, configuration and UI tests pass. Configured QEMU HTTPS inference/indexing/vector recovery and repeatable owner/Reader search browsers pass. Provider-free live source/Wiki search, exact citations/offsets/fallbacks/graph/policy and full native restart persistence also pass; providers were kept disabled. Interactive Playwright remains waived. M10 documentation and the corrected complete-index/paused-refresh native recovery gate pass. The [fixture benchmark](docs/retrieval-benchmark.md) reports recall, precision, citations, latency and request costs; it shows RRF can favor distractors and deliberately unhelpful scoring can fail. No real provider quality/calibration is claimed.

MCP/OAuth use the maintained official SDK handlers and the existing verified NS8 SSO identity. Stored opaque codes/tokens and consent bindings are hashed; grants pin the approved client revision, native issuer/client, resource, role and expiry. Repeated code use, refresh replay, wrong resource/verifier/callback and unavailable/revoked authority fail closed. Trusted operations expose no SQL, shell, imports, provider credentials or NS8 administration actions. Request/reply/concurrency guards bound MCP to one MiB requests, eight MiB complete replies and eight concurrent requests; errors never truncate evidence or expose driver/token details. Hostname-root routing is required. All-role real consent controls and exact active-grant update/clean-restore snapshots pass disposable checks; permitted live owner read-scope lifecycle and full-manager restart persistence pass with normal TLS. Interactive Playwright remains waived.

## Remaining roadmap

| Capability | Agreed direction |
| --- | --- |
| Retrieval | PostgreSQL full-text search, optional external embeddings and graph expansion |
| System One | Optional Jev/Kev scoring with bounded requests and ordinary-ranking fallback |
| Agent access | Shared REST/MCP operations, OAuth protection and self-description |
| Forks | Reusable Core distribution, upstream-compatible extensions and development skills |

Object CRUD, deterministic ingestion and jobs work without AI credentials. Deterministic parsing/chunking, Wiki editing and source full-text retrieval retain that property. Binary originals are deleted by default only after successful extraction/persistence; optional retention uses an NS8 volume. Safe built-in defaults precede NS8 instance configuration and bounded request overrides. Request overrides cannot replace provider secrets. Semantic retrieval requires configured embeddings; Jev/Kev failures must disclose fallback and never determine authorization.

## Development and verification

`build-images.sh` publishes `ghcr.io/stell0/czero`, `czero-app` and `czero-postgres`. The module contains numbered actions and compiled NS8 Vue UI; the Python component contains installed Core/app packages and the separate user UI. Runtime images exclude agent instructions, plans, skills, CI, tests and development tools. The app runs unprivileged; NS8 lifecycle logic stays outside the application backend.

Install development dependencies in a virtualenv:

```sh
pip install uv==0.12.20 pytest robotframework robotframework-sshlibrary -e packages/czero-core -e 'app[test]'
python -m pytest -q app/tests packages/czero-core/tests tests/unit
```

The M14 candidate passes 675 Python unit/integration/packaging cases with an isolated PostgreSQL/pgvector database supplied by CI. Set `CZERO_TEST_DATABASE_URL` to a disposable database to execute database-backed cases locally; without it, skips are explicit. `node --test tests/ui/*.cjs` checks eighty-six accessibility/schema-field/graph/navigation/copy/administration/sharing/readiness/consent/source/Wiki/search response, role and retrieval-form cases using the real UI scripts. `go run tests/check_schemas.go` validates action regex compatibility with Core's Go engine. M13 adds `tests/packaging`: six actual Core wheel/sdist/license/reproducibility/isolated-install/migration checks, including a fresh dedicated PostgreSQL database when the isolated test URL is provided. Runtime dependency builds use `app/uv.lock` and frozen, non-development installation.

Disposable OAuth fixtures also seed active grants for exact update/clean-restore checks and exercise real Admin/Reader/Editor consent controls. Local signed HTTP verifies the exact preparation/recovery helpers and guards, including a deliberately bypassed Origin and a leftover earlier grant. Unknown virtual hosts are rejected by the NS8 proxy; the canonical application also rejects unauthorized Origins. Installed TLS, browser, exact recovery and permitted live owner acceptance pass; test credentials, token pairs and snapshots stay outside Git and runtime images.

Build the administration UI:

```sh
cd ui
corepack yarn install --immutable
NODE_OPTIONS=--openssl-legacy-provider corepack yarn build
```

`tests/czero.robot` runs native lifecycle in disposable QEMU, including the frozen verified predecessor recorded in PLAN.md, real PostgreSQL/vector persistence and encrypted backup/restore/replay. Baseline browser tests use a generated temporary cluster administrator. Real SSO fixtures provision OpenLDAP/IdP, generated private personas and trusted test certificates; native local-provider routing is used without fixture DNS overrides, asserting actual owner/member authorization, roles, revocation and logout. TLS and SELinux remain enabled. Private password/token values never become Robot variables, command arguments or nested keyword arguments. A report assertion checks the temporary browser password.

An older M01 installation may stop when pod/database dependencies are introduced; re-save hostname Settings to start the new stack. Live startup, migration, hostname/certificate/identity configuration, discovery, signed owner login/logout, CSRF/owner protection, negative REST authorization and stable owner identity after restart pass. All three member roles, revocation and identity restore are verified in disposable tests; a second live application persona was not exercised.

Czero strips queries from application access logs. Core Traefik has its own default access log; its production logging contract still needs release review. Disposable SSO fixtures suppress proxy access logs and assert no OAuth query values in both streams. The Browser wrapper's internal diagnostics are also disabled before startup and checked for OAuth queries alongside temporary credentials. M11 client approval passes the corrected Debian/Rocky native run and artifact privacy audit, plus permitted live owner approval/disable/replay/conflict and full-manager restart persistence. Interactive Playwright remains operator-waived. Permitted live tests use only the dedicated Czero instance; destructive backup/restore tests remain disposable.

Publication uses `GITHUB_TOKEN` with package-write permission and package Actions Write grants. `NS8_MODULE_RELEASES_TOKEN` is reserved for future GitHub releases. Private repositories are supported; private container packages additionally need authenticated guest pulls. Package names remove the repository's `ns8-` prefix, following Hermes.

Local and native browser CI check discovery text against available REST routes and documented limitations. CI includes local/schema/shell checks, image publication/runtime audits, Trivy SARIF/CycloneDX artifacts and native QEMU/Robot tests. Successful scans do not establish that dependency findings are resolved. Review findings before release. Follow AGENTS.md's milestone loop: plan, implement, commit/push, inspect actual CI/tests, fix failures, reconcile documentation, then advance. Keep live hostnames, passwords, tokens, cookies and auth-state files out of Git and artifacts.


## NethServer sources and license

Czero derives from [ns8-kickstart](https://github.com/NethServer/ns8-kickstart). Reuse [Core module contracts](https://github.com/NethServer/ns8-core/tree/main/docs/modules), [Hermes](https://github.com/NethServer/ns8-hermes-agent), [Dependency-Track](https://github.com/NethServer/ns8-dependencytrack), [IdP](https://github.com/NethServer/ns8-idp), [ns8-ui-lib](https://github.com/NethServer/ns8-ui-lib), [QEMU Actions](https://github.com/NethServer/ns8-github-actions) and [NethServer agent skills](https://github.com/NethServer/agents), prioritizing maintained, tested implementations linked in PLAN.md.

See [LICENSE](LICENSE) (GPL-3.0). Preserve attribution and verify license compatibility when copying code or distributing C0 Core.

Retrieval limitations: embeddings support at most 2000 full-precision dimensions; old profile/generation vectors remain stored until future derivative maintenance. Graph context is supplemental and unscored. C0 produces no generated answer. Real provider quality and model thresholds require corpus-specific evaluation. Live retrieval checks used the configured owner with providers disabled; disposable tests cover all roles and configured mock HTTPS providers. Stable IdP/proxy availability and the recorded image/UI vulnerabilities remain release-review work.

## Forks and Core distribution

[C0 Core 0.24.1](https://github.com/Stell0/ns8-czero/releases/tag/core-v0.24.1) is independently published as a wheel, source archive and SHA256SUMS. Its exact source ec940a9 passes local checks and both native distributions. Downloaded artifacts pass six clean-install, reproducibility and packaged-migration checks. GPL metadata, the full license and all migrations are included. Core has no dependency on the NS8 agent SDK or reference application.

The app pins released `core-v0.27.0` and its immutable subdirectory/commit in `uv.lock`, with compatible range `>=0.27.0,<0.28.0`. The accepted dedicated runtime uses Core 0.27.0. The controlled original consumer remains on `core-v0.24.1` with range `>=0.24.1,<0.25.0`; its existing patch-upgrade contract is preserved. Default image builds use the released source. Producer development explicitly uses `CZERO_CORE_SOURCE=local bash build-images.sh`; the override changes only its temporary builder source/lock. Upstream CI selects this mode; independent forks retain released defaults. Git, uv and the selector remain outside runtime images. Independent released-image CI verifies the actual installed version and immutable Git source against the committed lock, plus runtime content and license.

[Core 0.24.2](https://github.com/Stell0/ns8-czero/releases/tag/core-v0.24.2) is a published documentation/packaging patch with unchanged schema/API. Its exact-source local, image, both-native and artifact verification gates pass. Native Renovate uses prefix-aware regex versioning and explicit 0.24.x bounds; ordinary PEP 440 rejects complete `core-v` tags. Automatic merging is disabled. Review actual tag/lock diffs and run consumer tests; minor/breaking upgrades require separate compatibility and migration review. The real [compatible-patch Renovate PR](https://github.com/Stell0/c0-m13-example/pull/3) changes only the tag/lock and passes database-backed consumer CI.

The public [original consumer](https://github.com/Stell0/c0-m13-example) installs released Core with no local package tree. Its CI checks an original application schema, records, stale revisions, persisted Reader authorization and repeated packaged migrations in disposable PostgreSQL. Test identities are trusted fixture inputs, not SSO evidence. Generate another isolated example with `python examples/fork/create.py /tmp/c0-example`, then follow its README. Choose independent image/module names before using copied packaging files for an actual NS8 application fork.

Managed infrastructure uses `c0-upstream.json`: a trusted repository, immutable baseline and seventy-six explicitly registered paths with hash/mode identities. Preview from a maintainer checkout:

```sh
python scripts/sync-upstream.py --upstream-dir /path/to/trusted/upstream --revision FULL_SHA
```

Add `--apply` to prepare changes. Untouched files update; customized files stay intact with `needs_review`, `review_from`, `review_reason` and exact migration commands in `.c0/UPSTREAM_UPDATE.md`. Unresolved files retain the earliest comparison range across later proposals. Clear their markers only after resolving and testing the migration. Register required new helpers explicitly. Pre-distribution forks must also review their application dependency/lock transition; automatic infrastructure scope excludes application choices.

The scheduled/dispatch workflow opens review PRs and never merges them. Real [untouched](https://github.com/Stell0/c0-m13-example/pull/2) and [customized](https://github.com/Stell0/c0-m13-example/pull/1) proposals pass explicitly dispatched checks; repeat delivery preserves the proposal head. The customized exercise is closed unmerged. Actual [default-upstream PR 4](https://github.com/Stell0/c0-m13-example/pull/4) also passes consumer/database and managed CI after reviewed main promotion. Repeat default delivery preserves its exact head without duplicates. The weekly cron uses the same selector; no future cron event is claimed as executed.

Native Actions tokens cannot push workflow-file changes. The updater preserves those bytes and records permission/migration instructions. Use `--allow-workflow-updates` only in a reviewed maintainer checkout whose existing publishing credential has workflows permission; it grants no permission. Do not copy broad tokens into fork secrets. Enable the fork's Actions setting for workflow-created PRs, retaining default read permissions. Since [June 2026](https://github.blog/changelog/2026-06-11-bot-created-pull-requests-can-run-workflows-if-approved/), token-created PR checks require approval or explicit dispatch; token-created push builds remain suppressed. Dispatch module image publication for native QEMU acceptance and inspect completed results.

Four repository-only `.agents/skills/c0-*` skills cover feature development, Core development, reusable contributions and customized upgrades. They delegate native module/container/commit/PR/release operations to installed [NethServer skills](https://github.com/NethServer/agents). Independent exercises preserve branding, schemas and drafts while isolating a reusable [packaging contribution](https://github.com/Stell0/ns8-czero/pull/2) and porting real build dependencies. The contribution passes both native distributions and is closed unmerged after this controlled proof. Published patch, native/live persistence and independent review pass. The final documentation marker passes CI; no development skills ship in runtime images.

Core artifact publication is separate from an NS8 module release. The `core-v<version>` workflow requires successful local and both native checks for that exact source, builds/test artifacts read-only, then publishes with narrowly scoped write permission. Normalize archive ownership/timestamps/permissions with the commit epoch and rebuild wheels from that archive under umask 022. Verify uploaded hashes and never overwrite a published version. Runtime audits also require Core's license: standalone artifact success alone does not prove an assembled image contains it.

M00–M15, Integration M15/M16 and the structured-object repair have recorded implementation/acceptance evidence under the documented waivers; inspect this closeout marker's actual CI/main results before beginning M17. Image scans report findings rather than a clean security result; see PLAN.md for current counts and limitations.

M14 CPU-rate enforcement is deferred by operator request after the rootless test host rejected CPU quotas. The deployment candidate omits container CPU quotas; parser CPU/time limits remain. Memory/process limits and privilege restrictions retain their acceptance checks.

M14 candidate evidence, security findings and deployment limits are recorded in [the readiness report](docs/m14-readiness.md), with [development deployment notes](docs/m14-release-notes.md).


## Agent memory development track

The accepted C0-AM0–AM6 plan in [PLAN.md](PLAN.md) covers text evidence,
revision-safe Wiki operations, protected spaces, applicability-aware retrieval
and external-agent maintenance guidance. AM0–AM4 runtime acceptance passes at
main `878978d` (Core 0.28.0/app 0.43.0/schema 0016), including supported backup,
update, full-manager restart and live current/legacy SDK checks. All 7146 original
rows, 125 terminal jobs/attempts, four files, 97 scheduler-history rows, nineteen
old client descriptors, eleven prior backup plans and eleven unrelated instances
are preserved. The owned client is disabled after a valid bearer control; native
browser/private Wiki and an independent existing-client read remain accepted.
The actual 1027-line root journal passes request-controlled privacy checks.
Verify this documentation marker's actual CI/main publication before AM5.

[Core 0.28.0](https://github.com/Stell0/ns8-czero/releases/tag/core-v0.28.0)
is independently published after exact-source local, producer and both-native
gates. Downloaded wheel/archive checksums, reproducible builds, separate installs
and packaged migrations pass. App 0.43 pins that immutable released source with
all 53 transitive packages unchanged. Its 75-operation catalog preserves all 71
accepted contracts and six resource templates. Owned deployed SDK sessions use
all five annotation targets and exact structured retrieval, preserve original
receipts and return unknown verification after a content change. The existing
connector independently reconnects and reads retained Shared evidence and a
historical Wiki revision; its cached 63 operations do not expose the new APIs.

The agreed space contract keeps object-type definitions shared across the
instance. Records, relations, events and annotations are protected by space;
Admins access all spaces under actual OAuth scopes, while Readers/Editors need
explicit protected-space grants capped by their application role. The space
contract, revisioned applicability annotations and structured retrieval are
deployed. Consolidation reliability and complete agent guidance remain AM5/AM6 work. Existing knowledge, immutable evidence/history and
approved clients must survive every milestone. C0 remains deterministic storage,
retrieval and maintenance infrastructure; external agents perform reasoning and
consolidation. Windmill Gate remains blocked through AM6 deployment acceptance.

### Protected-space contract

The space selector applies to content reads, writes, histories, citations,
originals, feeds and retrieval. `spaces_list` discovers only permitted spaces;
application Admins create spaces and manage revisioned Reader/Editor grants.
Object-type definitions remain global. An omitted `space_id` always selects the
legacy shared space. Invalid or denied selectors fail without falling back.
REST content endpoints accept a `space_id` query parameter. MCP content tools
accept top-level `space_id`; `knowledge_search` uses `options.space_id`.
Qualified resources use `c0://spaces/{space_id}/...`; legacy URIs retain Shared
semantics. A UUID lookup never infers another space.

Application Admins have every-space access under their actual OAuth scopes.
Readers and Editors need an explicit protected grant, capped by their current
application role. Changing a grant invalidates affected delegated tokens; later
regrant does not revive them. Sign in and explicitly consent again when needed.
Shared types do not grant access to their private records. References and
citations must stay within their selected space. Same slugs, object keys and
source content in different spaces do not conflict. Retry keys bind protected
mutations to their space while legacy Shared receipts remain compatible.

The ordinary UI has a space selector; Admin space/grant controls live in
Administration. Space changes and access loss clear private views and invalidate
pending responses. Choosing Shared is explicit. Revision and unchanged-retry
protections still apply within each space. The deployed workflow preserves
retained originals, immutable history and original retry receipts across the
supported full-manager restart.

### Earlier implementation evidence

The following entries retain the progression of earlier candidates; the current
status and deployment are stated above and in PLAN.

The AM0 baseline passes 812 existing and 814 combined Python/PostgreSQL/packaging
cases, plus the existing script/schema/Robot checks. Read-only deployed health,
image identity and unchanged-data checks pass; no new feature is deployed. See
the [baseline report](docs/c0-agent-memory-baseline.md) for frozen public/installed
images, existing contracts and private-evidence boundaries.

AM0 candidate `ebc38ef` also passes exact-source producer/released-Core CI and
Debian genuine upgrade (19 cases) plus Rocky installation (23 cases, 3 expected
skips), including seven browser/privacy workflows and actual artifact audits.
The operator merged PR #3 as `b66e159`; its actual main checks, publication and
requested dedicated deployment pass as recorded below. That baseline deployment
keeps the existing runtime APIs.


AM0 is now merged and accepted at `b66e159`, including successful main CI,
Debian upgrade/Rocky installation, native C0-only backup and operator-requested
dedicated deployment. Current APIs and versions remain unchanged. Existing data,
OAuth rows and unrelated modules are preserved; connected MCP reads pass.
AM1 text-evidence ingestion is the next implementation, with independent Core
publication preceding the released application dependency. See PLAN.md for exact
accepted digests, checks and implementation gates.


The AM1 Core portion is implemented on the feature branch and passes 847 local
Python/PostgreSQL/packaging cases, plus script/schema/Robot and independent
installed-package checks. Text uses the existing source/extraction pipeline with
bounded UTF-8 input and retry receipts. Core publication, the application REST/MCP
operation and final native/review/deployment acceptance are still pending; the
installed application continues to expose its existing interfaces.


[Core 0.25.0](https://github.com/Stell0/ns8-czero/releases/tag/core-v0.25.0) is now
published from exact verified source `02d3e49`, with independently checked wheel
and source-archive hashes. The AM1 app 0.40.0 candidate pins that released source;
its 64-operation catalog adds bounded `sources_ingest_text` while retaining all
63 legacy bindings. The application change also keeps malformed JSON-RPC
validation errors from echoing submitted text, preserving standard protocol
codes and existing fixed resource errors. Root Renovate bounds cover 0.25.x
patches; the original example retains 0.24.x bounds and automatic merging stays
disabled. Review, exact application CI/native tests and deployment remain gates.


The final AM1 application candidate passes 862 local Python/PostgreSQL/packaging
cases, 106 scripts and schema/shell/Robot checks. The actual published Core
artifacts separately pass all six independent packaging checks. Candidate
publication, native tests and review/deployment are still required before AM1
is accepted on the dedicated installation.


AM1 application candidate `84f64b1` also passes exact-source producer, released
Core, Renovate and native CI. Downloaded reports prove Debian installation
(16 passes, 3 expected skips) and genuine Rocky upgrade (26 passes), including
seven browser/privacy workflows and actual text-receipt/evidence recovery.
Actual artifacts pass the OAuth-query audit. The default released-source image
passes runtime/license/source checks and Dive analysis. Vulnerability reports
retain vendor findings; a passing critical gate does not mean a clean scan.
[PR #4](https://github.com/Stell0/ns8-czero/pull/4) remains a draft until this
evidence marker is verified; review, main publication and dedicated deployment
are still required. The live installation remains AM0 `b66e159`.

AM2's Core candidate passes 904 complete Python/PostgreSQL/packaging and 106
script cases locally, including independent installed wheel/archive Wiki
revision/retry checks. It does not yet expose new REST/MCP operations. The
installed version remains accepted ece3e90; CI/native, immutable Core publication,
application integration and reviewed deployment remain required for AM2.

AM2 adds two optional Wiki operations for external agents. Resolve an exact path
with `wiki_pages_resolve({"slug":"procedures/network"})`. To create a page, call
`wiki_pages_upsert` with `data` containing `slug`, `title`, `body`, applicable
`metadata` and an `idempotency_key`. Omit `expected_revision` only for create-only
behavior. To revise it, include the current revision and a new key. A stale writer
must resolve again, reconcile observations externally and submit the new revision;
C0 never merges or overwrites another writer's content implicitly.

Successful receipts include the page `id`, `revision` and immutable
`content.content_hash`. Retry an unchanged request with its original key after an
uncertain response. The original receipt remains unchanged after later revisions;
resolve again to read the current page. Archived pages are hidden by default;
`include_deleted:true` permits authorized lookup of retained content. Existing
UUID-based Wiki operations remain supported. Authored Markdown is bounded to
131072 UTF-8 bytes, metadata to 16 KiB JSON and serialized requests to one MiB.

Knowledge tools expose fixed text codes and matching `c0/error` metadata with
`code` and `status`. `knowledge_not_found` means the target was not found;
`knowledge_conflict` requires reloading; `invalid_knowledge_request` requires a
valid bounded request; `evidence_not_ready` requires completed extraction of real
chunks. `permission_denied` requires membership/role authorization, while
`insufficient_scope` retains the existing fresh-consent challenge for an eligible
role. `service_unavailable` is safe to retry when service returns. Private database
or submitted content is never used as an error message. Ordinary transport
authentication failures retain their HTTP 401 behavior. These additions remain a
development candidate until the AM2 gates recorded in PLAN pass.

The operator confirms connector authorization now completes after the consent
recovery fix. Actual reconnected MCP reading retrieves the same immutable evidence
citation created by the separate SDK session; history and provenance persist.

[Core 0.26.0](https://github.com/Stell0/ns8-czero/releases/tag/core-v0.26.0) is
published from verified 6093219 after actual exact-source Debian/Rocky, image,
local and artifact/privacy checks. Downloaded wheel/archive checksums and all six
independent packaging checks pass. App 0.41.0 candidate pins its exact released
tag/subdirectory/commit with compatible range `>=0.26.0,<0.27.0`; all transitive
packages stay unchanged. The installed instance remains accepted ece3e90 until
AM2's application review, main publication and deployment gates pass.

The final AM2 app 0.41.0 candidate passes 958 full Python/PostgreSQL/packaging
cases, 106 scripts, schema/shell and nineteen Robot dry runs locally. Its actual
default image verifies the released Core Git pin, runtime contents and license.
All 64 existing operation schemas/roles/scopes remain fixed with two additions.
[PR 6](https://github.com/Stell0/ns8-czero/pull/6) tracks exact CI/native/review
promotion; this is not yet a deployed feature.

The AM2 application source `cf3e9c9` passes actual local, image publication,
released-Core and dependency-update checks. Published candidate images match
that source; retained vendor vulnerability findings are recorded in PLAN.
Actual native reports pass Debian installation (sixteen cases/three expected
skips) and genuine Rocky upgrade (twenty-six cases), all seven browser/privacy
workflows and both current/legacy SDK Wiki maintenance/history checks. Downloaded
reports and both checkout revisions are audited. The final evidence marker still
requires its own exact CI/native verification before review; the installed service
remains the accepted consent-fix revision.


AM2 runtime acceptance now passes at deployed main `1a45070`. The live owned
workflow resolves, creates and updates a page, handles a genuine stale revision,
retains three immutable revisions and original retry receipts, and reuses sourced
evidence across current/legacy SDK sessions and manager restart. Read-only tokens
receive a write-scope challenge; fresh explicit consent enables the write replay.
The temporary client is disabled and rejected; all seventeen earlier client
descriptors and eleven unrelated modules remain unchanged. Existing connector
reads of the new citation and historical Wiki content pass separately, including
after cleanup. This proves SDK new-tool behavior and actual connector reading;
it does not claim a refreshed connector catalog or live all-role coverage.
