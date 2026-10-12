# C0 (Czero) — AI-native application foundation for NethServer 8

**Status (12 October 2026): M00 acceptance blocked; C0 application unimplemented.** Packaging has been adapted from [NS8 kickstart](https://github.com/NethServer/ns8-kickstart) to `czero`, with a pinned HTTP echo stub. Image publication is verified; QEMU and live installed behavior remain unverified. The repository is now public, but the GHCR package remains private, so unauthenticated installations are blocked. Package visibility is managed separately in GitHub. Follow [PLAN.md](PLAN.md) for milestone evidence. [AGENTS.md](AGENTS.md) defines the coding-agent rules.

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

The Python **C0 Core** runtime will eventually be a separately versioned package; fork-specific business logic belongs in the application layer. The NS8 lifecycle itself remains implemented as short, numbered **actions**, not as a giant Python manager.

### What works with no AI credentials

After C0 is implemented, a clean installation must work for users, data CRUD, deterministic document text extraction/chunking, wiki editing, PostgreSQL full-text search, graph queries, REST/MCP and administration **without any generative-model service**. Semantic search requires a configured external embedding API. Jev and Kev are optional external System One services; timeout/error falls back to unfiltered standard retrieval.

C0 deliberately **does not** contain a generative LLM, autonomous research agent, scheduled LLM prompts, local model inference, user-defined shell jobs, document-level ACLs, webhooks, or a second graph database. External harnesses (e.g. ChatGPT, Claude, Hermes) maintain the wiki through authenticated APIs/MCP.

### Documents and storage

Keep full extracted text and source locations: vectors alone are insufficient for citations, re-chunking and re-embedding. Original binary uploads may be deleted **after successful extraction and persistence** by default, or retained on an NS8-backed volume when chosen. Backups must cover PostgreSQL logical dumps, required persistent files and secret configuration. Knowledge can be exported without an AI provider.

### Search configuration

Safe defaults live in C0. NS8 admin UI sets instance-wide embedding and System One provider credentials, models, timeouts and resource limits; REST/MCP requests may override safe query parameters (limit, retrieval mode, graph depth, rerank mode) **within configured bounds**. Full-text fallback is always available and the response reports which retrieval method was used.

## Two ways to make an application

**Configure an installed C0:** An authenticated agent defines object types, records, relationships and generic forms using existing REST/MCP operations; simple applications need little or no new code.

**Fork and extend C0:** For specialized rules/UI/SQL transactions, create a fork and ask an AI coding agent to implement the feature using [AGENTS.md](AGENTS.md) and [PLAN.md](PLAN.md). Changes to C0 Core should be separated into upstream-ready PRs where generally reusable.

Development-only files (`AGENTS.md`, skills, CI, tests, build scripts, templates) stay in the repository; they are **not** exposed as installed app runtime content. The installed app does provide **usage documentation** at `/agents` and standard REST/MCP discovery.

## Intended interfaces (not yet implemented)

- End-user browser: `/`
- Human-readable agent capabilities: `/agents`
- Machine-readable capabilities: `/agents/capabilities.json`
- REST/OpenAPI: `/api/v1/...` and `/openapi.json`
- Remote MCP: `/mcp`

Exact resource schemas, auth flows and operation names will be recorded as each milestone passes. They must be generated from one capability/operation registry where possible.

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

**Current repository baseline:** `build-images.sh` builds the `ghcr.io/stell0/czero` module, packaging only NS8 actions and the compiled administration UI. `czero.service` runs `jmalloc/echo-server:v0.3.7` on an allocated loopback port. Configuring with `{}` enables the service and registers `/czero/<module-id>/` in Traefik. This is a packaging smoke endpoint, with no authentication or C0 storage; do not send it sensitive content. The administration Settings page starts this stub; application hostname/provider settings arrive in later milestones. Build/publication and local checks pass, but QEMU cannot pull the private package and live acceptance has not run. Live Playwright navigation additionally stops because the administration certificate is not trusted by the test browser; login has not been attempted. Install instructions remain provisional until those checks pass.

Install development test dependencies (`pytest`, `robotframework`, `robotframework-sshlibrary`), then run local checks with `python3 -m pytest -q tests/unit`; build the administration UI with `cd ui && corepack yarn install --immutable && NODE_OPTIONS=--openssl-legacy-provider corepack yarn build`. `tests/czero.robot` verifies installation, repeated configuration, invalid input, service restart, native forced update and removal on disposable QEMU. Browser checks create a random temporary administrator and assert rendered module identity, settings and HTTP response. They do not use live credentials. M00 has no earlier released image; migration from a predecessor is covered starting at M04.

CI workflows already present in the template:

- `.github/workflows/publish-images.yml` — Czero image build/publication and Trivy scan; source/image SARIF reports and CycloneDX SBOMs are retained as CI artifacts. These workflows retain reports as artifacts rather than submitting them to GitHub Security. Reports contain known findings in the inherited UI dependencies and temporary echo runtime; a completed scan does not mean they are resolved.
- `.github/workflows/test-module.yml` — NS8 Robot integration via [QEMU reusable workflow](https://github.com/NethServer/ns8-github-actions/blob/v1/.github/workflows/test-module-qemu.yml).
- `renovate.json` — baseline Renovate config (fork/upstream awareness to be added later).
- `.github/workflows/test-local.yml` — action tests, shell syntax and Robot dry-run.

Follow the loop in `AGENTS.md`: plan **one milestone**, implement in small increments, commit/push, verify actual CI runs, run applicable NS8 and browser checks, update both documentation files, mark evidence, then advance. Use [Playwright MCP](https://github.com/microsoft/playwright-mcp) interactively to check both the NS8 administrator UI and the separate C0 user UI; add repeatable automated checks to CI.

Do not place private live-server details, passwords, session cookies or auth-state files in the repository. Authorized live testing details are supplied by the operator at execution time.

## Roadmap

[PLAN.md](PLAN.md) contains ordered milestones from kickstart/CI through database, authentication, reusable storage, wiki ingestion, retrieval, MCP, Web UI, fork upgrades and final acceptance. No item is complete until its evidence is recorded in the plan.

## License

See [LICENSE](LICENSE) (GPL-3.0 as present in the template). Verify license compatibility when copying implementation code or splitting out the C0 Core distribution.
