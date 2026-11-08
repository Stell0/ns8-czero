# Interfaces and supported boundaries

## Discover the actual instance

Use the installed `/openapi.json` and authenticated `/agents/capabilities.json` for current schemas, tool names, roles, scopes and availability. MCP exposes the same trusted operations and `c0://capabilities` workflow guidance. Tool discovery is not authority to invoke a tool. Avoid building integrations around a tool count copied from a historical milestone.

| Interface | Purpose |
| --- | --- |
| `/`, `/wiki`, `/sources`, `/search` | Knowledge readers; authorized source upload, replacement and recovery on Sources |
| `/wiki/{id}`, `/sources/{id}`, `/evidence/{id}` | Complete articles/documents and exact cited evidence |
| `/explore` | Read-only entities, claims, relationships, annotations and structured records |
| `/account`, `/admin` | Personal preferences, connections/API keys and authorized people/application administration |
| `/agents`, `/agents/capabilities.json` | Use with AI setup/downloads and caller-aware technical discovery |
| `/mcp` | OAuth-protected Streamable HTTP on configured hostname-root instances |
| `/oauth/authorize`, `/oauth/consent`, `/oauth/token`, `/oauth/revoke` | Explicit SSO consent, S256, short tokens, rotating refresh and revocation |
| `/api/v1/profile`, MCP `get_profile` | Stable opaque account identity and supported profile labels |
| `/api/v1/health` | App/Core versions and database/schema/vector readiness |
| `/projects`, `/api/v1/project` | Protected project reader and explicit project state; candidate features require matching Core |
| `/api/v1/spaces` | Authorized space discovery; explicit selection for content |
| `/api/v1/oauth/clients`, `/api/v1/oauth/cimd` | Admin-approved manual clients and optional metadata discovery |
| `/docs`, `/openapi.json` | Interactive REST documentation and machine-readable schemas |

Legacy NS8-prefix installations retain REST compatibility but do not advertise MCP until configured on a hostname root.

The website does not create, edit, annotate, archive or delete knowledge.
Authorized assistants retain these REST/MCP operations. Source file controls are
the exception; original retention is opt-in, and replacements keep the published
document readable until complete validation. The Vue website uses explicit routes
without legacy page aliases; see [the website contract](vue-website.md).

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

C0 stores and serves knowledge, current evidence, payload-free synchronization events, deterministic jobs and optional retrieval. External agents perform reasoning and synthesis. The application contains no autonomous LLM, arbitrary user shell executor, local inference engine or second graph database.

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

## Protected research projects

Projects reuse protected spaces, immutable typed schemas, current grants and
existing knowledge services. See [project contracts](projects/PROJECTS.md),
[source adapters/CLI](projects/SOURCES.md), [workflow/queue contracts](projects/WORKFLOWS.md),
[primary monitoring and agents](projects/MONITORING.md)
and the explicit
[readiness checkpoint](projects/WIKIPLANT_MIGRATION_READINESS.md). Project operations are implemented in compatible released Core. Discover actual installed capabilities. Reading or configuring a project does not activate external research schedules or migrate WikiPlant data; host execution and migration acceptance remain separate.

See [complete source documents](full-documents.md) for logical identities, bounded
current summary/body APIs, safe rendering and exact current part resolution.

Source and Wiki content uses [latest-only storage](latest-only-migration.md). Historical source/Wiki body reads, rollback and content-history export are removed. History compatibility routes list current content only and are omitted from OpenAPI discovery; MCP no longer advertises `source_document_history`, `wiki_revisions_list` or `knowledge_annotations_history`. Expired exact content and superseded replay requests return HTTP 410 / MCP `content_superseded`, after current space authorization.


## Selective source context

When advertised by the installed Core, `source_document_outline_get` reads bounded
section metadata for a stable logical document. Retain its exact `revision_id` and
full-body hash; use `view=blocks` for bN page/paragraph/table/code spans. Paginate
with `limit`, `offset` and `next_offset`. This metadata contains no complete body.

`source_document_sections_get` requires `data.revision_id` and 1–20 `selection_ids`
(sN sections or bN blocks). It returns exact Unicode character offsets, selected
text/hash and source chunk citation handles. Chunk `start_offset`/`end_offset` are
relative to the extracted source part; `document_start_offset`/`document_end_offset`
are relative to the complete logical document. OCR selections include observed
page confidence and the frozen local extractor profile; absence is not a score.

`source_document_references_get` resolves explicit local rN IDs from selected
context at that same revision. Unresolved/ambiguous anchors remain unresolved.
`context_bundle_get` accepts `data.plan`: at most five objects containing
`logical_document_id`, `revision_id`, `selection_ids` and `reference_ids`, with
at most twenty total selected IDs in one space and caller order. It performs no
model inference or network fetch. A denied/missing/stale selection never falls
back; retired revisions return `content_superseded` (410).

These are Reader operations under `c0:read`, with ordinary top-level `space_id`.
REST uses GET `/api/v1/source-documents/{id}/outline`, POST the corresponding
`/sections` and `/references`, and POST `/api/v1/context-bundles`. Request bodies
are bounded to 16 KiB. `max_bytes` bounds the serialized context payload (4096–65536
UTF-8 bytes, excluding transport envelopes); `max_tokens` bounds its bytes/3
estimate (256–16384). Provider tokenization and message overhead remain external.
Replies always say `complete_document=false`, list oversized omissions and keep
unresolved references explicit. Whole-document readers remain unchanged. Legacy
in-memory structural derivation retains the 2 MiB/1M-character extracted-body
ceiling; larger multipart originals retain their existing complete reader.

## Extraction progress and recovery

When installed Core exposes these capabilities, browser REST provides
`GET /sources/{source_id}/extraction` for selected-space Reader progress and
`GET /extraction-runs`, `GET /extraction-runs/{run_id}/units` for Admin diagnostics.
Lists accept limit 1–100 and offset 0–10000. Results contain metadata, never unit
bodies or leases. The usual API base and explicit `space_id` apply.

Editor writes use `POST /extraction-runs/{run_id}/retry` with expected_revision
and idempotency_key, or `/cancel` with expected_revision. Full restart retains
the existing `/source-versions/{version_id}/retry` expected_generation contract.
Explicit `POST /sources/{source_id}/reindex` requires expected_revision and
idempotency_key plus a retained original; successful full publication expires
previous exact citations. Managed source-sync publications use their own workflow.
Cookie writes require current CSRF. No MCP tool, new scope, public durable handoff,
background grant promotion or automatic reindex is added.

## Personal API keys

REST and MCP accept personal API keys through the existing Bearer header. Keys
carry explicit Read/Write scope ceilings and selected spaces; they never grant
administration. Create, list and revoke keys only from a browser session on the
Account page. See [the API-key interface and workflow guide](api-keys.md).

## Knowledge compilation

Compiler coordination, guarded publication, source discovery, assessment and semantic-review operations are implemented under `/api/v1/compilation` and matching `compilation_*` MCP names. The app registers only operations supported by its installed Core. The producer package can contain newer inputs than the released consumer; inspect actual capabilities and schemas.

Policies default to disabled, retrieval feedback off and queue-only publication. Admin policy configuration requires actual authority and expected revision; it installs no scheduler. Editor coordination and publication require enabled selected-space policy, Read+Write, current evidence, target/policy revisions, live fences and budgets. Queue-only and held plans require exact-plan review. `compilation_plan_validate` is a dry-run; `compilation_apply` publishes atomically and returns pending verification; `compilation_verify` records fresh saved-result readback. None proves semantic truth.

`knowledge_search` and other retrieval operations never queue learning. A compatible external agent can use a separate bounded post-answer proposal workflow under enabled retrieval-feedback policy. Reader and explicitly read-only tasks cannot do so. See [the complete search/update rules](llm-wiki.md#what-happens-after-a-search), [compiler operations](knowledge-compilation/OPERATIONS.md) and [external maintenance](wiki-maintenance.md).
