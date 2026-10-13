# C0 (Czero) — AI-native application foundation for NethServer 8

**Status (13 October 2026): M00 is complete; M01 documentation verification is pending.** Czero provides a FastAPI application, a small end-user landing page and a separately versioned C0 Core package. Local, published-image and QEMU lifecycle/browser checks pass. Further interactive Playwright and live testing are temporarily waived by the operator. The repository and container packages are public. Follow [PLAN.md](PLAN.md) for evidence and [AGENTS.md](AGENTS.md) for coding rules.

## Why C0?

C0 is a **working application foundation**, not merely a library. The intended first installation provides a browser application, a REST API, a remotely usable OAuth-protected MCP endpoint, reusable PostgreSQL storage, and a generic LLM Wiki / retrieval engine.

It also serves as a GitHub template: fork C0, tell Codex or Claude Code what application to build, and have the agent modify, test, package, deploy and maintain an independent NethServer 8 module. Many knowledge-centric applications should reuse existing generic storage and operations before adding domain-specific tables and code.

**C0 stores and serves knowledge; external AI harnesses reason about and maintain it.**

## Planned runtime

| Capability | Design |
| --- | --- |
| Hosting | NS8 rootless module, Podman/systemd, Traefik HTTPS, native volume and backup lifecycle |
| Application backend | Python, FastAPI, REST/OpenAPI and a shared operation/service layer |
| Database | One PostgreSQL instance **per installed C0 module**, pgvector plus relational and JSONB storage |
| Knowledge | Original-source metadata, retained extracted text, chunks, embeddings, wiki pages, revisions, provenance, claims, entities and typed relationships |
| Generic app data | Object types defined by JSON Schema, JSONB records, relations, tags/events and CRUD |
| Search | Always-on PostgreSQL full-text search; optional external embeddings for vector/hybrid retrieval; graph expansion |
| System One | Optional external **Jev or Kev** scoring/filtering adapter; safe standard-ranking fallback |
| Authentication | NS8 user domains and ns8-idp/OIDC for browser and MCP |
| Permissions | Personal owner by default; optional shared Reader/Editor/Admin roles, **one common knowledge space**, no per-document ACLs |
| Scheduling | Small PostgreSQL-backed deterministic job queue and scheduled-tasks table, dispatched by a systemd user timer |
| Admin UI | Native NS8 module settings for host, role access, external-provider configuration, health and services |
| User UI | Knowledge, generic records, search, wiki, jobs and a self-describing `/agents` page |
| Agent access | REST, native MCP tool discovery and `/agents/capabilities.json` |

The Python **C0 Core** runtime is a separately versioned package under `packages/czero-core`; it currently provides the health operation. Fork-specific business logic belongs in `app`. Package registry publication arrives in M13. The NS8 lifecycle remains implemented as short, numbered **actions**.

### What works with no AI credentials

After C0 is implemented, a clean installation must work for users, data CRUD, deterministic document text extraction/chunking, wiki editing, PostgreSQL full-text search, graph queries, REST/MCP and administration **without any generative-model service**. Semantic search requires a configured external embedding API. Jev and Kev are optional external System One services; timeout/error falls back to unfiltered standard retrieval.

C0 deliberately **does not** contain a generative LLM, autonomous research agent, scheduled LLM prompts, local model inference, user-defined shell jobs, document-level ACLs, webhooks, or a second graph database. External harnesses (e.g. ChatGPT, Claude, Hermes) maintain the wiki through authenticated APIs/MCP.

### Documents and storage

Keep full extracted text and source locations: vectors alone are insufficient for citations, re-chunking and re-embedding. Original binary uploads may be deleted **after successful extraction and persistence** by default, or retained on an NS8-backed volume when chosen. Backups must cover PostgreSQL logical dumps, required persistent files and secret configuration. Knowledge can be exported without an AI provider.

### Search configuration

Safe defaults live in C0. NS8 admin UI sets instance-wide embedding and System One provider credentials, models, timeouts and resource limits; REST/MCP requests may override safe query parameters (limit, retrieval mode, graph depth, rerank mode) **within configured bounds**. Full-text fallback is always available and the response reports which retrieval method was used.

## Planned application development paths

**Configure an installed C0:** An authenticated agent defines object types, records, relationships and generic forms using existing REST/MCP operations; simple applications need little or no new code.

**Fork and extend C0:** For specialized rules/UI/SQL transactions, create a fork and ask an AI coding agent to implement the feature using [AGENTS.md](AGENTS.md) and [PLAN.md](PLAN.md). Changes to C0 Core should be separated into upstream-ready PRs where generally reusable.

Development-only files (`AGENTS.md`, skills, CI, tests, build scripts, templates) stay in the repository; they are **not** exposed as installed app runtime content. The current app provides an introductory `/agents` page and health/OpenAPI discovery. Authenticated REST/MCP discovery arrives in later milestones.

## Current interfaces

M01 serves these paths beneath `/czero/<module-id>` on the cluster web host:

| Path | Current behavior |
| --- | --- |
| `/` | Static application landing page with API and agent links |
| `/api/v1/health` | JSON status and Core/application versions (`0.1.0`) |
| `/openapi.json` | OpenAPI schema for the health endpoint and instance prefix |
| `/docs` | Swagger API documentation |
| `/agents` | Introduction describing the available health/OpenAPI capabilities |

These endpoints are currently public and hold no application data. Login, database storage, document ingestion, Wiki, search, jobs and MCP are later milestones. The health response currently reports the application process contract, not database or provider readiness. `/docs` loads Swagger assets from a CDN; `/openapi.json` remains usable without them.

## Planned interfaces

- Machine-readable capabilities: `/agents/capabilities.json`
- Authenticated object, source, Wiki, search and job operations: `/api/v1/...`
- Remote MCP: `/mcp`

Machine-readable capabilities, authenticated resource operations and MCP remain planned. Exact schemas and auth flows will be recorded as each milestone passes and generated from one capability/operation registry where possible.

## Source code and NethServer conventions

This repository starts from [ns8-kickstart](https://github.com/NethServer/ns8-kickstart). Existing NS8 technology must be **reused**, not rebuilt:

- Module actions and configuration: [NS8 module agent](https://github.com/NethServer/ns8-core/blob/main/docs/modules/agent.md); modern [Hermes action organization](https://github.com/NethServer/ns8-hermes-agent).
- Embedded PostgreSQL and logical backup: [ns8-dependencytrack](https://github.com/NethServer/ns8-dependencytrack).
- Volume and backup: [NS8 Core](https://github.com/NethServer/ns8-core/blob/main/docs/modules/backup_restore.md).
- OIDC registration: [ns8-idp](https://github.com/NethServer/ns8-idp).
- Admin components: [ns8-ui-lib](https://github.com/NethServer/ns8-ui-lib).
- CI/Robot/QEMU image tests: [ns8-github-actions](https://github.com/NethServer/ns8-github-actions).
- Coding-agent instructions and NethServer PR skills: [NethServer/agents](https://github.com/NethServer/agents).

Prefer the maintained patterns linked directly in each milestone. The repository currently includes a GPL-3.0 license; retain proper attribution and check any copied code for license compatibility.

## Development and testing

`build-images.sh` builds the small `ghcr.io/stell0/czero` NS8 module image and the separate `ghcr.io/stell0/czero-app` Python component. The module contains actions and the compiled administration UI; the component contains installed Core/app runtime packages and the static user page. Its Python base and runtime dependencies are pinned, and the app runs as an unprivileged user. Repository instructions, tests, CI, skills and builder tools stay outside the runtime filesystem.

Settings Save configures `{}`, enables `czero.service` on an allocated loopback port, and registers `/czero/<module-id>/` in Traefik. The app preserves that prefix. Native update hooks reconcile the M00 instance identity and restart running services; unconfigured services stay stopped. Hostname/TLS configuration arrives in M02 and login in M05. The M01 QEMU suite has passed Debian 13/update and Rocky 9/install, including access logs, restart, invalid-input rejection, browser settings/service recovery and disposable removal. The dedicated live instance was upgraded from M00 to M01 successfully: health, service status, invalid-input rejection, Settings Save and basic app navigation passed before the operator suspended further live testing. Remaining live restart/refresh and final inventory checks are waived. No release is ready.

For development installation, use the native NS8 `add-module` action with `image: "ghcr.io/stell0/czero:main"` and your node id. Open the installed module's Settings and click Save, then visit `/czero/<module-id>/` or `/czero/<module-id>/api/v1/health` on the cluster web host. Check PLAN.md for the tested commit and image digest. `:main` and `:latest` track development builds; they are not stable releases. Core 3.21.0 displays digest-only image URLs incorrectly in inventory, although installation works.

Install test dependencies in a development virtualenv with `pip install pytest robotframework robotframework-sshlibrary -e packages/czero-core -e 'app[test]'`, then run `python -m pytest -q app/tests packages/czero-core/tests tests/unit` (18 tests). Runtime builds use `app/uv.lock` with `uv sync --frozen --no-dev --no-editable`. Build the admin UI with `cd ui && corepack yarn install --immutable && NODE_OPTIONS=--openssl-legacy-provider corepack yarn build`. `tests/czero.robot` verifies native lifecycle in disposable QEMU. Browser checks create a random temporary administrator and assert Settings Save recovering a deliberately stopped service, About, the landing page, health, OpenAPI and agent introduction. They never use live credentials. Genuine earlier-version data migration tests arrive in M04.

Publication uses `GITHUB_TOKEN` with explicit checkout and package-write permissions; each container package must grant the repository Actions Write access. `NS8_MODULE_RELEASES_TOKEN` is reserved for future GitHub releases. Private source checkout is supported; private container packages would also require authenticated QEMU/guest pulls. Package naming follows Hermes: remove the repository’s `ns8-` prefix.

CI workflows already present in the template:

- `.github/workflows/publish-images.yml` — module/component image publication and Trivy scans; source/image SARIF reports and CycloneDX SBOMs are retained as CI artifacts. Reports contain dependency findings; successful scan execution does not mean they are resolved. Review them before release.
- `.github/workflows/test-module.yml` — NS8 Robot integration via [QEMU reusable workflow](https://github.com/NethServer/ns8-github-actions/blob/v1/.github/workflows/test-module-qemu.yml).
- `renovate.json` — baseline Renovate config (fork/upstream awareness to be added later).
- `.github/workflows/test-local.yml` — action tests, shell syntax and Robot dry-run.

Follow the loop in `AGENTS.md`: plan **one milestone**, implement in small increments, commit/push, verify actual CI runs, run applicable NS8 and browser checks, update both documentation files, mark evidence, then advance. Use [Playwright MCP](https://github.com/microsoft/playwright-mcp) interactively to check both the NS8 administrator UI and the separate C0 user UI; add repeatable automated checks to CI.

Do not place private live-server details, passwords, session cookies or auth-state files in the repository. Authorized live testing details are supplied by the operator at execution time.

## Roadmap

[PLAN.md](PLAN.md) contains ordered milestones from kickstart/CI through database, authentication, reusable storage, wiki ingestion, retrieval, MCP, Web UI, fork upgrades and final acceptance. No item is complete until its evidence is recorded in the plan.

## License

See [LICENSE](LICENSE) (GPL-3.0 as present in the template). Verify license compatibility when copying implementation code or splitting out the C0 Core distribution.
