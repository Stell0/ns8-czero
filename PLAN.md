# C0 implementation plan — milestone-by-milestone Codex handoff

**State:** M00 implementation is prepared; installed acceptance is blocked by private GHCR access and live browser certificate trust. Czero packaging has replaced the kickstart identity, but the runtime is still an HTTP echo stub. No milestone is complete. Start at **M00** and mark milestones complete only with verified results.

This plan is intended to be **executed iteratively**: inspect, refine the current milestone, implement, test, commit/push, verify CI, perform applicable live and Playwright MCP checks, update docs, and only then advance. Never implement several milestones blindly before reviewing the prior milestone's results.

## Product contract (do not quietly change)

- C0 = AI-native, forkable NethServer 8 web application, using NS8's native module framework and readable **numbered action scripts**. Don't replace lifecycle actions with a monolithic Python NS8 management library.
- Runtime: Python/FastAPI, user Web UI, REST/OpenAPI, remote MCP, NS8-idp authentication, one PostgreSQL **instance per C0 installation**, pgvector, generic structured-object storage and an LLM Wiki with relational graph connections.
- Single shared knowledge space per installation. Personal-owner default; optional Reader/Editor/Admin application-wide roles. No per-document ACLs, UGO, policy engine or multi-tenancy.
- No embedded generative LLM, local model server, autonomous AI maintenance or AI scheduling. External agents do reasoning/wiki updates. C0 may optionally call an external embedding API and a System One scorer (**Jev or Kev**) for retrieval; graceful full-text and standard-ranking fallbacks.
- Deterministic ingestion, chunking, jobs, trusted scheduled tasks, and native NS8 backup/restore. Keep extracted text even when deleting binary originals after successful extraction.
- Installed application exposes `/agents` and native MCP discovery. `AGENTS.md`/skills/build/CI/tests are Git/repository-only, never bundled into the runtime.
- An external developer forks C0 to build an application. Generally useful enhancements flow upstream by a focused, tested PR. Versioned C0 Core should be upgraded automatically where possible, with Codex used for conflicts.
- Favor reuse from NS8. Respect GPL/license headers, secret handling and existing module interfaces.

## Source precedence and selection

1. Current checked-in behavior and the deployed NS8 version.
2. [NS8 official module contracts](https://github.com/NethServer/ns8-core/tree/main/docs/modules) and [NethServer/agents module skill](https://github.com/NethServer/agents/tree/main/skills/nethserver-ns8-module).
3. Current, maintained, tested examples referenced in each milestone: [ns8-kickstart](https://github.com/NethServer/ns8-kickstart), [ns8-hermes-agent](https://github.com/NethServer/ns8-hermes-agent), [ns8-dependencytrack](https://github.com/NethServer/ns8-dependencytrack), [ns8-idp](https://github.com/NethServer/ns8-idp), [ns8-mail](https://github.com/NethServer/ns8-mail), [ns8-github-actions](https://github.com/NethServer/ns8-github-actions).
4. Official upstream project reference for features NS8 modules do not supply.

**When no code link is listed for a C0-specific feature:** search maintained NethServer/Nethesis repos first, starting with filenames, actions, services and REST schema names matching the operation. Review at least two patterns when available, compare freshness, test coverage, security and lifecycle, choose the current better implementation and note the finding in the milestone subplan. If nothing reusable exists, implement the smallest component and record why. Do not copy older hard-coded secrets or image tags.

## Non-negotiable execution loop for EVERY milestone

1. **Inspect and plan.** Read `AGENTS.md` and `README.md`, the pending milestone, previous evidence, local git status and relevant upstream sources. Expand only the active milestone's `Work plan` with implementation steps, specific files and tests. Record changed assumptions. Maintain a short task checklist in that milestone rather than opening a separate planning document.
2. **Build early.** From **M00**, configure actual image publication in GitHub Actions. For each meaningful slice: make a focused commit, push it, inspect the image-build workflow and the ensuing QEMU/Robot test workflow. Fix and repush until green. Check both source/build failures and installed-service behavior. Never claim CI green without a completed successful run.
3. **Test in layers.** Unit/type/lint locally; service integration against isolated PostgreSQL; NS8 install/configure/update/backup/restore in QEMU where applicable. Once bootable and CI green, test on an explicitly authorized live NS8 node provided at runtime. Use **Playwright MCP** for interactive NS8 admin UI and C0 user UI (including auth, settings, errors and persistence); maintain automated Robot/browser coverage too. A browser screenshot alone is not a passing behavioral test.
4. **Protect live systems.** Use only the dedicated C0 instance, test accounts and designated C0 hostname supplied in the execution prompt. Never modify unrelated modules, reset system passwords, publish secrets, delete a module with useful data, or run destructive installation/restore tests on a shared live node. Use disposable QEMU for destructive scenarios. A missing SSH/MCP/browser capability is a blocker to record, not a license to invent results.
5. **Document each milestone.** Update `AGENTS.md` with discoveries/developer rules, `README.md` with actual human-visible behavior, configuration and known limitations, and this `PLAN.md` with status and evidence. Keep documentation concise; move sprawling details to reference files if necessary. Commit and push the docs changes, and observe the triggered CI.
6. **Exit gate.** Mark `[x]` only after all milestone-specific acceptance tests pass and `Evidence` includes commit SHA(s), relevant CI run URL(s), test commands/results and live/Playwright result if applicable. If blocked, keep `[ ]`, write the exact blocker, and stop instead of silently skipping.

**Evidence template for every milestone:** `Evidence: pending. Work plan: pending. Tests: pending. CI: pending. Live/UI: pending or not applicable (explain). Docs: pending.`

### Tests and CI conventions

- Preserve the existing `.github/workflows/publish-images.yml` / `test-module.yml` structure where sound; use [publish-branch.yml](https://github.com/NethServer/ns8-github-actions/blob/v1/.github/workflows/publish-branch.yml), [test-module-qemu.yml](https://github.com/NethServer/ns8-github-actions/blob/v1/.github/workflows/test-module-qemu.yml), [test-module runner](https://github.com/NethServer/ns8-github-actions/blob/v1/scripts/test-module.sh) and [Trivy scanning](https://github.com/NethServer/ns8-github-actions/blob/v1/.github/workflows/scan-with-trivy.yml). Inspect `workflow_run` permissions, GHCR image visibility, fork Actions settings and the proper output image tag.
- QEMU Robot suites must verify **install and update**, not merely parse Robot tests. For browser coverage use Robot Browser/Playwright in CI and use [Playwright MCP](https://github.com/microsoft/playwright-mcp) interactively when an operator-supplied live test host is available.
- Stop using the template's sample `kickstart` credentials in `tests/kickstart.robot` in M00. Do not commit operator-supplied live credentials, hostnames, OAuth tokens, browser auth state or private URLs. Runtime config and test secrets are injected safely.
- NS8 operations use `imageroot/actions/<action>/<NN>step`, JSON input/output validation, `agent` SDK, systemd user services, private secrets files, Traefik and volumes. Application business logic can live in a versioned Python library; **module lifecycle logic must not** become a single giant library.
- If a requirement is blocked by a missing facility, add a clear, testable follow-up to this milestone; do not silently weaken acceptance criteria.

## Milestones

### M00 — Rebrand kickstart, create working CI and smoke-test the module [ ]

**Goal:** On the first implementation push, build an actual `czero` module image from this repository and get an honest install/configure/uninstall smoke test. The baseline may still be a simple HTTP stub, but must no longer pretend to be implemented C0.

**Copy/adapt from:** [ns8-kickstart/build-images.sh](https://github.com/NethServer/ns8-kickstart/blob/main/build-images.sh); [kickstart CI publish](https://github.com/NethServer/ns8-kickstart/blob/main/.github/workflows/publish-images.yml); [kickstart QEMU test](https://github.com/NethServer/ns8-kickstart/blob/main/.github/workflows/test-module.yml); [kickstart Robot](https://github.com/NethServer/ns8-kickstart/blob/main/tests/kickstart.robot); [ns8-github-actions](https://github.com/NethServer/ns8-github-actions/blob/v1/README.md); [module developer skill](https://github.com/NethServer/agents/tree/main/skills/nethserver-ns8-module).

**Implement:** Rename `kickstart` across scripts, unit files, tests, UI, metadata, image labels and workflows. Use a verified image name/tag and pinned runtime images; make the registry owned by this repo, not `ghcr.io/nethserver/kickstart`. Remove placeholder README behavior and hard-coded Robot passwords; pass test credentials safely. Ensure publish + QEMU/Robot workflows really run on appropriate pushes; fix Actions permissions/trigger order. Add a basic health smoke and clear module identity. Preserve GPL/attribution.

**Acceptance:** A pushed commit yields a **published czero image**, successful CI build and QEMU install/configure/uninstall with correct name; no leftover kickstart functionality falsely represented as C0; no credentials committed. No use of the shared live host for destructive tests.

**Documentation gate:** Correct agent source/layout/CI instructions in `AGENTS.md`; update `README.md` with achieved install and honest limitations; record image tag/commit/build/test URLs in `PLAN.md`.

**Work plan (active, 12 October 2026):**

- [x] Rename the module/image/unit/metadata to `czero`; retain the pinned echo HTTP stub explicitly until M01. Remove unused SMTP discovery and the fake settings field. Use an instance-specific `/czero/<module-id>/` smoke route.
- [x] Fix checkout permissions in publication, remove the first-run skip, and gate QEMU on successful publication. Run browser assertions on every tested image. Retain native reusable NS8 workflows where their contracts support this private repository.
- [x] Add repeatable install/configure/reconfigure/restart/update/uninstall Robot assertions. With no released predecessor at M00, exercise Core's forced update of the installed image; older-image migration remains M04. Create a random disposable cluster administrator for browser tests, without committed passwords.
- [ ] Run local action/packaging contract tests, Robot dry-run and UI build; inspect actual publication, scan and QEMU matrix results. Verify anonymous GHCR access before live installation. Exercise the dedicated module through Playwright MCP; keep destructive checks in QEMU.
- [ ] Reconcile all three project documents with observed behavior and record commit/run/image evidence before closing M00.

**Source findings:** Checked current `ns8-kickstart` build/actions and `ns8-hermes-agent` component build pattern, Core `docs/modules/agent.md` and `agent.set_route`, and `ns8-github-actions@v1` publication, module-info, QEMU and Robot runner files. Core supplies image environment names and lifecycle cleanup. The QEMU wrapper needs `${SCENARIO}` in the suite to exercise updates. Docker Hub confirms `jmalloc/echo-server:v0.3.7` and `node:24.21.0-slim` exist. The local installed NethServer skills are active. The existing publication run [38232079693](https://github.com/Stell0/ns8-czero/actions/runs/38232079693) failed at checkout because publication grants only `packages: write`; its apparently successful downstream run skipped QEMU entirely. The first caller-permission fix at `6124dca` still failed in run [38233736825](https://github.com/Stell0/ns8-czero/actions/runs/38233736825): the called workflow explicitly declares only `packages: write` and strips checkout access. Adapt its small build/push job locally with explicit permissions; retain the reusable QEMU workflow. API schema documentation run [38233736701](https://github.com/Stell0/ns8-czero/actions/runs/38233736701) and local checks [38233735916](https://github.com/Stell0/ns8-czero/actions/runs/38233735916) pass. Correct the disposable user request to include Core's required `set` field and `owner` role; regression tests cover hashing, hidden entry and log-level restoration.

**CI follow-up:** `a1692f5` published `ghcr.io/stell0/czero:main` and `:latest`, digest `sha256:31e9be27367eadcef922570e1ab9321385e628466218db6f78a81fb0b2362193`, in [38234197326](https://github.com/Stell0/ns8-czero/actions/runs/38234197326). Build/push succeeded and [local checks](https://github.com/Stell0/ns8-czero/actions/runs/38234196282) passed. The overall workflow failed only at SARIF upload because GitHub code scanning is disabled. Adapt Trivy/SBOM steps locally to retain scan artifacts without requiring that optional feature. Upstream module-info masks an anonymous pull failure; use authenticated metadata inspection that fails on errors. Authenticated archive inspection found 99 entries, only `imageroot/` and `ui/`, no forbidden development paths. The package is private and anonymous GHCR token acquisition returns 401; a public-visibility decision is pending. No QEMU or live test has passed.

**Resume verification:** The operator made the repository public and requested continuation. GitHub REST now reports repository `visibility: public`, while the existing `czero` package still reports `visibility: private`; anonymous GHCR access still returns HTTP 401. A signed-in GitHub browser is not connected, and the available GitHub GraphQL mutation schema exposes no package visibility operation. The separate package-setting action was requested in the session. The documentation commit `a9fcfa4` had successful [image publication/scans 38235324960](https://github.com/Stell0/ns8-czero/actions/runs/38235324960) and [local checks 38235324952](https://github.com/Stell0/ns8-czero/actions/runs/38235324952); its [QEMU run 38235543599](https://github.com/Stell0/ns8-czero/actions/runs/38235543599) failed on both distro legs at the private-image pull before boot. No source or runtime change is justified by the repository-visibility change alone.

**Live browser preflight:** Playwright MCP navigation to the execution-time authorized administration endpoint returned `ERR_CERT_AUTHORITY_INVALID` before login. Automatic approval review rejected a temporary `ignoreHTTPSErrors` test context, requiring user hand-off. No credentials were entered, no authentication state was saved, and no live module or service was changed. Require a trusted test-browser connection or an operator-resolved certificate before live login; do not bypass this rejection. Platform-version inspection and live module acceptance remain unverified.

**Blocker and required action:** In [QEMU run 38234990734](https://github.com/Stell0/ns8-czero/actions/runs/38234990734), Debian 13/install and Rocky 9/update both failed at `Describe the image under test`: anonymous `skopeo` access to `ghcr.io/stell0/czero:latest` was unauthorized. This happens before VM boot or Robot execution, so no installed, update, removal or browser behavior is verified. The [Czero package](https://github.com/users/Stell0/packages/container/package/czero) is private. The operator must decide whether to make this package public (GitHub makes that irreversible), or retain private images and arrange authenticated QEMU/live installation. Repository visibility need not change. The repository is now public; the separate package visibility update was requested in the execution session and has not been observed. Do not advance M01 until the image access and M00 acceptance gates pass. No live service was installed or modified.

**Evidence:** Partial M00 only; milestone remains `[ ]`. Implementation commits `6124dca`, `a1692f5`, `9cb2aca`. [Image build/publication/scans 38234794696](https://github.com/Stell0/ns8-czero/actions/runs/38234794696) succeeded, publishing `ghcr.io/stell0/czero:main` and `:latest`, digest `sha256:23b1108def06597671e494e0ea3124552a15721e1c5cf8226a8a6a86f616720e`. [Local CI 38234794655](https://github.com/Stell0/ns8-czero/actions/runs/38234794655) passed four pytest tests, shell syntax and six non-UI Robot dry-run checks. Four SARIF and four CycloneDX artifacts were downloaded and inspected: no findings for module image or imageroot; 29 findings in inherited UI dependencies and 95 in the temporary echo runtime. Scan execution is green; findings are reported, not asserted resolved. Replace the echo runtime in M01 and review/update affected UI dependencies before release; no security-clean release claim. Playwright MCP/live checks are blocked on verified installability. Documentation-push build/local CI passed as recorded above; QEMU still failed. Resume-check documentation CI must also be observed.

**Local verification details:** Baseline `868242a`; clean worktree before implementation. Local `PYTHONPATH=/tmp/czero-python python3 -m pytest -q tests/unit`: 4 passed (Robot/SSH dependencies installed in the temporary path). Robot dry-run excluding UI: 6 parsed/passed (not an installed-service test). Shell syntax, action JSON and workflow YAML parse checks pass. Immutable Yarn installation and production UI build pass after refreshing the renamed workspace lock entry; inherited peer-dependency and bundle-size warnings remain. Repository is private, so image visibility must be checked explicitly. Local SSH Git transport fails on system SSH configuration permissions; use authenticated HTTPS without changing Git configuration. No live deployment performed.

### M01 — Minimal Python runtime, Web UI and Core/application separation [ ]

**Goal:** Replace the echo sample with an actual installable HTTP application and established package boundaries.

**Copy/adapt from:** [ns8-hermes-agent/build-images.sh](https://github.com/NethServer/ns8-hermes-agent/blob/main/build-images.sh) (component images); [ns8-kickstart/systemd service](https://github.com/NethServer/ns8-kickstart/blob/main/imageroot/systemd/user/kickstart.service); [ns8-dependencytrack/systemd components](https://github.com/NethServer/ns8-dependencytrack/tree/main/imageroot/systemd/user); [nethserver-containerfile skill](https://github.com/NethServer/agents/tree/main/skills/nethserver-containerfile).

**Implement:** Minimal FastAPI runtime with `GET /api/v1/health`, OpenAPI, initial browser `/` page and honest `/agents` introductory page. Create clearly separated, versioned/releasable Python C0 Core package, application-specific extension module, and repository-only development files; use a pinned, minimal Python container and a user Web UI bundle. NS8 action scripts stay separate from FastAPI. Build all required images in CI.

**Acceptance:** Install image, start systemd units, access browser and REST health through NS8 path/route, verify request logs and restart behavior, run pytest and QEMU smoke; no development files in runtime images. Playwright MCP browser health/UI check when feasible.

**Documentation gate:** Record package/app boundaries in `AGENTS.md`; actual endpoints/UI and install caveats in `README.md`; tests and evidence in `PLAN.md`.

**Evidence:** Pending.

### M02 — NS8 configuration, Traefik and administrator UI [ ]

**Goal:** Make installation configurable using native NS8 actions, not a custom admin service.

**Copy/adapt from:** [Hermes validation](https://github.com/NethServer/ns8-hermes-agent/tree/main/imageroot/actions/configure-module); [Hermes get-configuration](https://github.com/NethServer/ns8-hermes-agent/blob/main/imageroot/actions/get-configuration/20read); [Hermes route reconciliation](https://github.com/NethServer/ns8-hermes-agent/blob/main/imageroot/actions/configure-module/90reconcile-desired-routes); [kickstart Settings.vue](https://github.com/NethServer/ns8-kickstart/blob/main/ui/src/views/Settings.vue); [ns8-ui-lib](https://github.com/NethServer/ns8-ui-lib); [Core Traefik/certificates](https://github.com/NethServer/ns8-core/blob/main/docs/modules/certificates.md).

**Implement:** `configure-module`/`get-configuration` with input/output schemas, persisted non-secret environment, secrets separated, single host and TLS configuration, port allocation and route reconciliation, systemd service control, native NS8 admin settings/errors/progress. Avoid extra nginx proxy unless it has a demonstrated purpose. No giant lifecycle manager. Ensure idempotence on repeated configure and hostname changes.

**Acceptance:** Configure through API and NS8 admin UI; settings round-trip, valid TLS route, repeated configure harmless, invalid input rejected, service status accurate. Test admin UI with Playwright MCP, then dedicated live C0 install once image build is green.

**Documentation gate:** Update `AGENTS.md` action steps/secrets rules; `README.md` administrator operation instructions; `PLAN.md` evidence.

**Evidence:** Pending.

### M03 — Dedicated PostgreSQL + pgvector and migrations [ ]

**Goal:** Each installed C0 owns its own isolated PostgreSQL container/database and durable state; enable pgvector without introducing a separate vector database.

**Copy/adapt from:** [ns8-dependencytrack PostgreSQL unit](https://github.com/NethServer/ns8-dependencytrack/blob/main/imageroot/systemd/user/postgresql-app.service); [ns8-idp modern PostgreSQL unit](https://github.com/NethServer/ns8-idp/blob/main/imageroot/systemd/user/postgres.service) (**use Type=notify only if selected image supports it**); [ns8-postgresql module](https://github.com/NethServer/ns8-postgresql); [NS8 volumes](https://github.com/NethServer/ns8-core/blob/main/docs/modules/volumes.md); [pgvector upstream](https://github.com/pgvector/pgvector).

**Implement:** Select/pin an actual supported PostgreSQL+pgvector image (build a minimal derived image if needed); secrets in private `state` files; database connectivity/readiness, SQLAlchemy/Alembic migrations, `CREATE EXTENSION vector` and baseline version tables. Isolate instance naming/credentials and keep DB off public ports.

**Acceptance:** Two module instances cannot see each other's DB; data survives service restarts; vector extension is available and indexed test vectors can be queried; migration repeatable; UI health indicates DB availability. Build/Robot/QEMU green.

**Documentation gate:** `AGENTS.md` schema/migration and systemd conventions, `README.md` DB/version/setup behavior, `PLAN.md` evidence.

**Evidence:** Pending.

### M04 — Backup, restore and upgrade-safe persistence [ ]

**Goal:** Use NS8's native lifecycle, not custom backup infrastructure.

**Copy/adapt from:** [NS8 backup/restore contract](https://github.com/NethServer/ns8-core/blob/main/docs/modules/backup_restore.md); [dependencytrack dump](https://github.com/NethServer/ns8-dependencytrack/blob/main/imageroot/bin/module-dump-state); [dependencytrack restore](https://github.com/NethServer/ns8-dependencytrack/blob/main/imageroot/actions/restore-module/40restore_database); [dependencytrack cleanup](https://github.com/NethServer/ns8-dependencytrack/blob/main/imageroot/bin/module-cleanup-state); [dependencytrack state include](https://github.com/NethServer/ns8-dependencytrack/blob/main/imageroot/etc/state-include.conf); [Hermes restore reconcile](https://github.com/NethServer/ns8-hermes-agent/blob/main/imageroot/actions/restore-module/20configure); [Core updates](https://github.com/NethServer/ns8-core/blob/main/docs/modules/updates.md).

**Implement:** Logical `pg_dump`/`pg_restore` flow; `state-include.conf` for DB dump, secrets and retained uploaded-source volume; cleanup temporary dump; rebuild derivative config on restore; idempotent restore/reconfigure; versioned DB/app migrations in update scripts. Do not blindly back up running DB files together with redundant full dumps; decide strategy based on authoritative NS8 behavior.

**Acceptance:** Seed persistent data and retained test file, backup, restore to clean QEMU instance, verify identities/data/config and REST behavior; upgrade from an earlier test image; run destructive tests ONLY in disposable infrastructure.

**Documentation gate:** `AGENTS.md` backup/restore invariants; `README.md` operator restore/upgrades; `PLAN.md` evidence.

**Evidence:** Pending.

### M05 — ns8-idp login and minimal application-wide authorization [ ]

**Goal:** Browser, REST and later MCP share NS8 identities and simple roles.

**Copy/adapt from:** [ns8-idp README and register-client](https://github.com/NethServer/ns8-idp/blob/main/README.md); [register-client schema](https://github.com/NethServer/ns8-idp/blob/main/imageroot/actions/register-client/validate-input.json); [NS8 user-domain binding](https://github.com/NethServer/ns8-core/blob/main/docs/core/user_domains.md); [Hermes user-domain action](https://github.com/NethServer/ns8-hermes-agent/tree/main/imageroot/actions/configure-module); [NS8 idp tests](https://github.com/NethServer/ns8-idp/tree/main/tests).

**Implement:** Discover ns8-idp service, bind one user domain, register/update OIDC client with proper redirect URIs, preserve client secret safely, authenticate app browser, validate issuer/audience/expiry/signature for API, stable user identity. Default personal owner; optionally admit named users as Reader/Editor/Admin with a single knowledge space. Check access at shared service boundaries. No per-document ACLs.

**Acceptance:** Owner login/logout and session expiry work; unadmitted user denied; reader cannot write; editor cannot administer; admin may configure; REST rejects absent/invalid/mis-audienced tokens. Exercise owner and a normal test user using Playwright MCP on live C0 UI and admin settings. No passwords or cookies in Git.

**Documentation gate:** `AGENTS.md` identity/roles invariants; `README.md` login and sharing instructions; `PLAN.md` evidence.

**Evidence:** Pending.

### M06 — Deterministic jobs and database-backed scheduler [ ]

**Goal:** A simple reusable asynchronous/cron substrate for application developers, with no AI orchestrator.

**Copy/adapt from:** [ns8-mail systemd timer](https://github.com/NethServer/ns8-mail/blob/main/imageroot/systemd/user/spam-expunge.timer); [ns8-mail timer activation action](https://github.com/NethServer/ns8-mail/blob/main/imageroot/actions/create-module/20spam-expunge); [ns8-mail one-shot service](https://github.com/NethServer/ns8-mail/blob/main/imageroot/systemd/user/spam-expunge.service); [ns8-porthos timer](https://github.com/NethServer/ns8-porthos/blob/main/imageroot/systemd/user/snapshot.timer).

**Implement:** PostgreSQL-backed `jobs`/`job_runs` and `scheduled_tasks`/`task_runs`; registered Python handlers, idempotency, retry and concurrency/timeout limits, restart recovery; one systemd user timer wakes scheduler. Seed one cheap statistics/health task and a weekly bounded maintenance check. No user-defined arbitrary shell, SQL, or built-in LLM calls. Expose simple status/configuration REST.

**Acceptance:** Due tasks execute once under normal conditions and safely recover from restarts; failures logged and retried within limits; no duplicate concurrent execution; admin can inspect schedules; CI/QEMU timer/service checks pass.

**Documentation gate:** `AGENTS.md` scheduler registration contract; `README.md` operator schedule and status; `PLAN.md` evidence.

**Evidence:** Pending.

### M07 — Generic application object model and reusable CRUD [ ]

**Goal:** Cover common CRM/inventory/project/idea-style records without creating a database table for every object type.

**Search rule (no direct reusable NS8 object engine identified):** Search current NethServer/Nethesis code for `JSON Schema`, `jsonb`, `validate-input.json`, CRUD action contracts and data-driven forms. Reuse NS8 action/schema conventions from [ns8-core agent](https://github.com/NethServer/ns8-core/blob/main/docs/modules/agent.md) and form components from [ns8-ui-lib](https://github.com/NethServer/ns8-ui-lib); use PostgreSQL's ordinary JSONB/index constraints rather than imitating a huge no-code platform.

**Implement:** `object_types` (JSON Schema, names/labels), `objects` (JSONB, revision, stable id), `object_relations`, tags/events and indexed query/CRUD services. Validate schema, permission, paging/filters, type-level uniqueness where needed, optimistic concurrency, safe batch writes, and typed references to future wiki/real relational records. Dedicated SQL tables remain supported for transactional domains. Add generic REST endpoints and minimal reusable record list/detail UI.

**Acceptance:** Agents/API can register types and CRUD records; two test domains (inventory and projects) run without new schema tables; conflict/invalid input detected; typed relations resolve; Reader/Editor rights enforced; CI and browser checks pass.

**Documentation gate:** `AGENTS.md` type/schema extension rules; `README.md` CRUD examples and limitations; `PLAN.md` evidence.

**Evidence:** Pending.

### M08 — Source ingestion, text extraction and chunk storage [ ]

**Goal:** A normal C0 installation can ingest, inspect and text-search documents without any AI provider.

**Search rule (C0-specific):** Search maintained NS8 applications for upload handling, background ingestion and safe user-file storage; adopt only reusable file/NS8-volume and queue patterns. For text extraction libraries, verify current supported upstream APIs and benchmark PDFs/DOCX/Markdown before selecting dependencies; do not invent NethServer-specific document parsers.

**Implement:** `sources`, `source_versions`, `documents` and `chunks` with content hashes, offsets, page/section locations and deduplication; deterministic upload/parser/chunker task handlers. Always retain extracted full text in PostgreSQL. Delete binary original only after validated persistence by default; allow per-source or instance `retain_original` backed by an NS8 volume. Quarantine failed/extraction-incomplete originals for explicit resolution. Paginated REST browse/search/delete, UI upload/details, version history.

**Acceptance:** Text/Markdown/PDF/DOCX samples round-trip with citations and stable hashes; re-upload doesn't duplicate identical content; changed source creates a version; failed extraction never silently loses original; no AI credentials needed; backup/restore source checks and UI tests pass.

**Documentation gate:** `AGENTS.md` ingestion/retention invariants; `README.md` supported formats, storage and recovery; `PLAN.md` evidence.

**Evidence:** Pending.

### M09 — Versioned Wiki, entities, claims, provenance and PostgreSQL graph [ ]

**Goal:** Persistent LLM Wiki data usable by external agents, without a second graph database.

**Search rule (no matching NS8 knowledge graph identified):** Search NethServer/Nethesis repositories for versioned records, entity aliasing, relation tables, source provenance and event/change feeds; prefer PostgreSQL constraints and recursive SQL for graph traversal. Consult the existing C0 `sources`/`objects` schema before designing new identities. If nothing reusable exists, implement minimal typed tables and small APIs.

**Implement:** `wiki_pages`, `wiki_revisions`, `entities`, `entity_aliases`, `relations`, `claims`, `evidence_links` and stable references to objects/chunks/sources. Conflicting claims coexist with sources and time metadata, not silent replacement. Expose CRUD, citation lookup, bounded graph traversal, export to Markdown/JSON, changes-since cursor, idempotency keys and optimistic concurrency.

**Acceptance:** External test agent can add/update knowledge, retrieve its evidence, resolve aliases, traverse 1-3 hops, export and reconcile concurrent edits; every claim tracks provenance; backups preserve revisions; REST/authorization tests pass.

**Documentation gate:** `AGENTS.md` canonical identity/provenance and change-feed contracts; `README.md` Wiki usage/exports; `PLAN.md` evidence.

**Evidence:** Pending.

### M10 — Full-text, vectors, external embeddings and Jev/Kev System One RAG [ ]

**Goal:** Useful `knowledge_search` by default and optional state-of-the-art retrieval components without built-in generation.

**Copy/adapt from:** [pgvector](https://github.com/pgvector/pgvector); [Jev System One API examples](https://github.com/SC0d3r/jev-systemone); [Kev server and compatible API](https://github.com/arjun988/Kev); [NS8 module config UI](https://github.com/NethServer/ns8-kickstart/blob/main/ui/src/views/Settings.vue). **Search rule:** no matching NS8 embedding/RAG engine was identified; compare current PostgreSQL FTS/hybrid retrieval and supported provider protocols before implementing any query/vector pipeline. Confirm Jev/Kev wire-format compatibility against real docs, not only names.

**Implement:** PostgreSQL FTS baseline; optional embedding provider adapter with model/dimension registry, background embeddings/re-embedding, pgvector ANN/indexes; bounded hybrid ranking (e.g. RRF), optional graph expansion; System One `/v1/systemone` compatible Jev and Kev scorer (off/rerank/filter), bounded candidate set and calibrated threshold per model. NS8 admin UI/env config for endpoints, model names, timeouts, credentials stored as secrets. Safe request-time overrides for `mode`, `limit`, `graph_depth`, `rerank` within administrator caps. Graceful fallbacks and reported `retrieval_method`/`fallback_reason`. No generative model or arbitrary per-request provider URLs.

**Acceptance:** With no provider, FTS returns sourced results. With mocked/real authorized external embedding provider, semantic/hybrid works and model mismatch rejected. Jev and Kev adapters pass protocol mocks; unavailable/rate-limited services preserve ordinary results. Benchmark Recall@k, precision/answer evidence, latency and candidate costs on a fixture corpus; do not assume System One improves quality without evidence.

**Documentation gate:** `AGENTS.md` retrieval/provider contracts and fallback rules; `README.md` configuration/examples/privacy tradeoffs; `PLAN.md` benchmarks and evidence.

**Evidence:** Pending.

### M11 — REST/MCP parity, OAuth interoperability and `/agents` discovery [ ]

**Goal:** An external AI client can connect immediately and discover exactly what the installed C0 can do.

**Copy/adapt from:** [ns8-idp registration](https://github.com/NethServer/ns8-idp/blob/main/README.md); [NS8 module identity docs](https://github.com/NethServer/ns8-core/blob/main/docs/core/user_domains.md); [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk); [MCP protocol](https://github.com/modelcontextprotocol/modelcontextprotocol); [ns8-github-actions API-doc CI](https://github.com/NethServer/ns8-github-actions/blob/v1/.github/workflows/build-apidoc.yml). **Search rule:** inspect current ns8-idp protocol support, client registration and issuer behavior and test with real clients; no general NS8 MCP OAuth bridge is known to reuse blindly.

**Implement:** Shared service operation/capability registry powering FastAPI routes/OpenAPI, MCP tools/resources and human-readable `GET /agents` + machine-readable `GET /agents/capabilities.json`. Remote MCP Streamable HTTP; OAuth protected-resource/authorization discovery and delegated user tokens with ns8-idp as identity source; enforce caller's application-wide role and token scopes at boundary. Basic tools: inspect capabilities, types/objects, wiki/documents, search, changes feed, schedules/jobs; **no arbitrary SQL/shell or raw privileged NS8 actions**. Discovery and permissions reflect current caller. OAuth errors and expired/mismatched tokens handled correctly.

**Acceptance:** Authorized client successfully lists/calls tools and sees the same result as REST; Reader cannot mutate by either transport; live OAuth browser login and token lifecycle tested; `/agents` and OpenAPI actually describe installed capabilities; a real compatible MCP client can connect if harness allows. Do not assume scheduled ChatGPT tasks support custom MCP connectors without checking.

**Documentation gate:** `AGENTS.md` operation registry and discovery rules; `README.md` connection steps, API/MCP limitations and authorization; `PLAN.md` client interop evidence.

**Evidence:** Pending.

### M12 — Full C0 user UI and NS8 configuration experience [ ]

**Goal:** Make the vanilla C0 installation genuinely usable without an AI client.

**Copy/adapt from:** [ns8-kickstart UI](https://github.com/NethServer/ns8-kickstart/tree/main/ui); [ns8-ui-lib](https://github.com/NethServer/ns8-ui-lib) for NS8 administration; [Hermes status/config UI patterns](https://github.com/NethServer/ns8-hermes-agent/tree/main/ui). **Search rule:** for the separate application UI, inspect maintained NethServer/Nethesis user-facing CRUD apps for list/detail form, loading, errors and accessibility patterns; use a small app UI rather than creating a new NS8 control plane. Browser automation reference: [Playwright MCP](https://github.com/microsoft/playwright-mcp).

**Implement:** End-user navigation, knowledge/source explorer, upload/retry, Wiki editor with revisions, generic object type/forms, relations/graph view, full-text/semantic search, jobs/schedules, `/agents` with copyable URLs and descriptions; proper owner/read/editor UI state. Admin module page configures host/domain/sharing, embedding and Jev/Kev providers, limits/health, with fields stored via NS8-native configuration actions. Validate frontend state and accessibility.

**Acceptance:** Playwright MCP tests **both** the NS8 admin interface and C0 Web UI, including wrong/valid logins, upload/search/edit, missing provider fallback, role gates, refresh/persistence and useful errors; add repeatable CI browser assertions; QEMU + permitted live tests pass.

**Documentation gate:** `AGENTS.md` UI testing/component conventions; `README.md` illustrated-by-text human usage and config (no secrets); `PLAN.md` evidence.

**Evidence:** Pending.

### M13 — Fork upgrades, C0 Core distribution and upstream contribution skills [ ]

**Goal:** Forked applications can receive most upstream infrastructure updates automatically; Codex handles only semantic merges, and reusable contributions flow back upstream.

**Copy/adapt from:** [NethServer/agents](https://github.com/NethServer/agents); [nethserver-pr](https://github.com/NethServer/agents/tree/main/skills/nethserver-pr); [nethserver-release](https://github.com/NethServer/agents/tree/main/skills/nethserver-release); [Hermes Renovate config](https://github.com/NethServer/ns8-hermes-agent/blob/main/renovate.json); [Hermes testing releases](https://github.com/NethServer/ns8-hermes-agent/blob/main/.github/workflows/create-testing-release.yml); [NS8 Core update mechanism](https://github.com/NethServer/ns8-core/blob/main/docs/modules/updates.md). **Search rule:** review current GitHub Actions, Renovate and package-distribution patterns in maintained NethServer forks. Don't introduce bespoke bot infrastructure if ordinary Renovate/reusable workflows suffice.

**Implement:** Version/publish `czero-core` package (choose and document a usable package registry/artifact workflow and compatible version range); fork app depends on it with Renovate PRs. Introduce versioned upstream manifest and scheduled fork workflow comparing managed NS8 packaging/skills/build files against upstream, opening safe update PRs and explanatory upgrade PRs for changed customized files. Add repository-only skills `c0-create-feature`, `c0-develop-core`, `c0-contribute-upstream`, `c0-upgrade-from-upstream`; delegate NS8-specific tasks to installed [NethServer/agents](https://github.com/NethServer/agents), don't vendor their copies. Publish original test fixtures/example fork. Ensure workflow tokens and permissions are least-privilege.

**Acceptance:** Change Core patch version -> Renovate PR builds/tests; change upstream managed module file -> sync PR; conflicting customized file -> migration instructions without overwrite; agent can isolate a reusable feature into a correct upstream PR; no development skills ship in runtime image.

**Documentation gate:** `AGENTS.md` fork/Core contribution rules; `README.md` how to fork/update/contribute; `PLAN.md` upgrade simulation evidence.

**Evidence:** Pending.

### M14 — End-to-end hardening, compatibility and release gate [ ]

**Goal:** Prove C0 is installable, restorable, independently usable, expandable and safe for other developers to fork.

**Copy/adapt from:** [QEMU install/update scenarios](https://github.com/NethServer/ns8-github-actions/blob/v1/docs/test-module-qemu.md); [NS8 module testing](https://github.com/NethServer/ns8-core/blob/main/docs/modules/testing.md); [Hermes Robot/testing patterns](https://github.com/NethServer/ns8-hermes-agent/tree/main/tests); [Trivy scan](https://github.com/NethServer/ns8-github-actions/blob/v1/.github/workflows/scan-with-trivy.yml); [NethServer PR/release skills](https://github.com/NethServer/agents).

**Implement:** Add coherent reference-app acceptance suite for normal CRUD plus Wiki-backed knowledge, exported sources, backup/restore, older-image upgrade, multiple C0 instances, resource limits, failures of optional providers, PostgreSQL migration and Jev/Kev fallback, network/auth errors, MCP client discovery, jobs/timer restart. Audit package contents and docs, verify no runtime developer files/secrets, check accessibility, latency and memory targets. Generate SBOM and release notes.

**Acceptance:** Successful image build, unit/integration suites, QEMU install+update (Rocky 9 and Debian 13 or clearly justified support matrix), NS8 admin and C0 UI exercised via Playwright MCP on authorized live environment, authenticated REST/MCP tests, backup/restore on disposable host, GPL/source compliance, ready-for-release report with no hidden failures.

**Documentation gate:** `AGENTS.md` final agent handoff/runbook; `README.md` accurate install/use/config/reference; `PLAN.md` complete evidence, known limitations and release state.

**Evidence:** Pending.

## After M14

Only after complete acceptance should additional features enter the roadmap. Prefer independent application forks or optional Core adapters over growing the default install. Any new milestone follows the **same** plan -> focused commits/push -> CI build+QEMU -> applicable live+Playwright MCP -> docs+evidence gate.

## Current next action

**M00 is the only active milestone.** Rebranding, pinned smoke runtime, credential-free Robot tests and local checks are implemented. Verify publication, GHCR access, QEMU install/update/browser/removal, and permitted live checks before advancing. Do not claim C0 application storage, RAG, OIDC or MCP exist yet. Iterate exactly one milestone at a time.
