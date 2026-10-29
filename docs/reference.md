# Interfaces and supported boundaries

## Discover the actual instance

Use the installed `/openapi.json` and authenticated `/agents/capabilities.json` for current schemas, tool names, roles, scopes and availability. MCP exposes the same trusted operations and `c0://capabilities` workflow guidance. Tool discovery is not authority to invoke a tool. Avoid building integrations around a tool count copied from a historical milestone.

| Interface | Purpose |
| --- | --- |
| `/`, `/wiki`, `/sources`, `/search` | Knowledge readers; manual mutation controls under the relevant `?view=tools` page |
| `/?view=account`, `/admin` | Account/sharing and authorized application administration |
| `/agents`, `/agents?view=tools` | Human Use with AI guide and technical discovery |
| `/mcp` | OAuth-protected Streamable HTTP on configured hostname-root instances |
| `/oauth/authorize`, `/oauth/consent`, `/oauth/token`, `/oauth/revoke` | Explicit SSO consent, S256, short tokens, rotating refresh and revocation |
| `/api/v1/profile`, MCP `get_profile` | Stable opaque account identity and supported profile labels |
| `/api/v1/health` | App/Core versions and database/schema/vector readiness |
| `/projects`, `/api/v1/project` | Protected project reader and explicit project state; candidate features require matching Core |
| `/api/v1/spaces` | Authorized space discovery; explicit selection for content |
| `/api/v1/oauth/clients`, `/api/v1/oauth/cimd` | Admin-approved manual clients and optional metadata discovery |
| `/docs`, `/openapi.json` | Interactive REST documentation and machine-readable schemas |

Legacy NS8-prefix installations retain REST compatibility but do not advertise MCP until configured on a hostname root.

## Roles, scopes and selectors

Application membership, effective space grants, actual OAuth scopes and current client/native authority all apply. Content reads ordinarily use `c0:read`; content maintenance uses `c0:write`; administration uses `c0:admin`. Initial read consent does not authorize a write. Role denial is different from an insufficient-scope challenge.

REST content selection normally uses `space_id` in the query; bundle selection is in its request body. MCP normally uses top-level `space_id`, except `knowledge_search` uses `options.space_id`, and structured search/bundle use `data.space_id`. Use current schemas for exact placement. Legacy content/resource forms select Shared and never grant protected access by a resource UUID.

## Evidence and edits

- Plain text/Markdown ingestion: at most 131072 UTF-8 bytes; use the returned immutable source version and await extraction.
- Files, retained-original downloads and exports: REST attachments; binary upload is not an MCP tool.
- Object payloads: bounded schema and 64 KiB records; consult the exact schema subset in OpenAPI. Type registration requires Admin and delegated Admin scope.
- Revision-safe Wiki upsert: omit expected revision for create-only; provide it for update-only. Slugs are fixed.
- Atomic knowledge bundle: 1–25 existing supported mutations in one space, at most 262144 aggregate JSON bytes; no extraction, jobs, files, schemas or grants.
- Annotation verification applies to an exact typed content revision. Missing annotations mean unknown; content changes do not inherit verification.

An unchanged replay-protected request retains its idempotency key. Changed requests need new keys. Ordinary creates and other operations without a receipt require saved-result inspection before an uncertain retry. A queued job or a configured optional provider is not proof of successful extraction, indexing or answer quality.

## Runtime responsibilities

C0 stores and serves knowledge, evidence, immutable history, deterministic jobs and optional retrieval. External agents perform reasoning and synthesis. The application contains no autonomous LLM, arbitrary user shell executor, local inference engine or second graph database.

Optional embeddings/scoring can incur configured external-provider effects. Text search remains usable independently. Retrieval/provider quality needs corpus-specific evaluation. Session policy, safe metadata fetching and retained evidence contracts remain enforced by Core/application code, not by plugin instructions.

See [Administration](administration.md) for lifecycle/security operations, [Development](development.md) for extension boundaries and the [historical evidence](history/PLAN.md) for executed compatibility limits.

## First-party workspace access

The people-first page uses browser-only Admin routes under `/api/v1/access`.
`GET /workspace?limit=25&offset=0` returns safe account summaries, permission
revisions and the active request count. `GET /accounts/{id}/applications` uses
limit10 (maximum50) and offset; both pages return `has_more`. Account pages allow
maximum100. These summaries confer no authority and make no provider request.

`POST /requests/{id}/preview` fetches verified metadata after authorization and
rechecks the request/current account after I/O. `POST /requests/{id}/approve`
requires its reviewed digest, explicit allowed scopes and existing client ID /
expected revision when reapproving. Core preserves earlier approved scopes and
checks the still-live exact callback/request and current block/policy.
`DELETE /requests/{id}` declines only that handoff; `DELETE /connections/{id}`
disconnects only the exact grant within the configured issuer/native/resource.
Writes require the browser cookie, same-origin Origin and CSRF. Native and
delegated bearer credentials cannot use these new routes. They add no MCP tools.

The existing `PUT /accounts/{id}` accepts optional `expected_revision`. A stale
revision returns409; unchanged revision-bound saves do not invalidate authority.
Real role changes and persistent blocks retain existing invalidation semantics.
Legacy account-list shape and legacy callers remain unchanged. Schema0021 adds
only `c0_accounts.access_revision` and a distinct random onboarding request UUID.

## Research project candidate

Projects reuse protected spaces, immutable typed schemas, current grants and
existing knowledge services. See [project contracts](projects/PROJECTS.md),
[source adapters/CLI](projects/SOURCES.md), [workflow/queue contracts](projects/WORKFLOWS.md),
[primary monitoring and agents](projects/MONITORING.md)
and the explicit
[readiness checkpoint](projects/WIKIPLANT_MIGRATION_READINESS.md). The development
branch does not activate real research schedules or migrate WikiPlant data.
Producer Core publication/default consumer adoption and final acceptance remain
required before claiming released project availability.

See [complete source documents](full-documents.md) for logical identities, bounded
summary/history APIs, safe rendering and exact historical part resolution.
