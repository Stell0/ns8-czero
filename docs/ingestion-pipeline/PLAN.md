# C0 ingestion pipeline — implementation plan

Status: **approved design; M0 candidate implemented, review/CI pending**
Decision date: **2026-11-02**  
Scope: independently queued document extraction units, selective retries, bounded concurrency, structure-aware indexing, optional OCR, conservative caching, selective-context REST/MCP interfaces, observability and measurement.

This is a **standalone execution plan** for `ns8-czero`. The root [roadmap](../../PLAN.md) links here; this document does not replace existing release, Core publication, or deployment gates. Implement **one milestone per independently reviewed pull request**. The user approved all defaults underlying this plan. No production ingestion, deployment, credentials, scheduling, release, or merge is authorized by this planning document.

## 1. Problem, baseline and decisions

M0 candidate: [assembly/manifest/lease/authorization contracts](CONTRACTS.md),
[executed baseline and reproduction commands](BASELINE.md), and deterministic
synthetic originals/regressions are implemented. Local evidence includes 114
focused database/parser/HTTP/MCP cases and 1,333 fast Python cases. Runtime,
schema, versions, dependencies, connector contracts and installed baselines are
unchanged. Exact-source CI and milestone review remain separate; M1 has not started.

The conference talk's key lesson is **fan-out at extraction time**: partition an original document into separately queued extraction units, persist each successful unit, retry only failed units, and assemble/publish only after the complete set is verified. **Extraction units are not search chunks.** Extraction units isolate processing cost and failure; search chunks are separately derived for retrieval.

Observed in original repository `main` at `fe38990b7c74594e2a7f91dbbb23697e7d1f1793` (2026-11-02; reread latest main before each milestone):

- `packages/czero-core/src/czero_core/sources.py`: one `source.extract` job handles a complete source version, calls `extract_isolated` and `chunks`, then publishes current content.
- `packages/czero-core/src/czero_core/extraction.py`: isolated parser has a 25-second parent timeout; PDF processing visits all pages; retrieval chunks default to **1,200 characters with 150 overlap**. PDF maximum is **200 pages**, file upload **10 MiB**, extracted body **2 MiB / 1,000,000 characters**, locations **4,000**, chunks **4,096**, and chunk text at most **4,096 characters**.
- `packages/czero-core/src/czero_core/worker.py`: serial one-shot worker, instance-wide PostgreSQL advisory lock and job execution within a database transaction. The systemd unit currently starts one bounded container; its timer wakes it periodically.
- `packages/czero-core/src/czero_core/jobs.py` and migration `0004_jobs`: generic job attempts/timeouts are bounded (at most five attempts; at most 30 seconds per handler). **Do not silently lift this contract for unrelated jobs.**
- `packages/czero-core/src/czero_core/documents.py`, `current_content.py`, `docs/full-documents.md` and migration `0023_current_content`: current-generation-only publication, exact citations returning `content_superseded` (410) when retired, complete multipart logical parents, and cleanup of superseded content.
- `samples/ingestion` and `docs/projects/SOURCES.md`: external, scope-authorized collectors and a resumable publisher already exist. Their source-sync part receipts (`c0_project_source_part_v1`) are **logical publication parts**, not extraction tasks.
- `samples/ingestion/examples/website/BENCHMARK.md` and `docs/agentic-retrieval.md`: retrieval benchmarks and controlled agentic comparisons already exist.

### Accepted design choices

1. **PostgreSQL is the only queue backend.** Reuse existing job infrastructure and worker conventions, with the smallest compatible extraction-specific lease/staging extension. No Redis, RabbitMQ, SQS, Step Functions or new orchestration service.
2. **Separate extraction execution from publication.** Never run expensive parsing/OCR while holding the shared publication lock or a long-lived database transaction.
3. **Bounded parallelism**, configurable per instance, initially **2 workers**, adjustable to **4** after resource tests. One NS8 instance only; no distributed multi-host coordination in the initial release.
4. **PDF first**, then DOCX, Markdown and plain text. Existing crawler-produced Markdown uses the same pipeline. Partition adaptively: PDF page or small page range; deterministic structural units for rich text; larger inexpensive units for simple text.
5. Preserve the current document/page/byte limits until later benchmarks justify a **separate** limit-expansion milestone.
6. **Three automatic extraction-unit attempts** with exponential backoff, then failed/blocked for operator action; do not restart successful units merely because another failed. Retain successful results within the allowed staging lifetime. Never publish an incomplete generation.
7. **Pluggable OCR**, initially optional local OCR; cloud OCR is **not** part of the initial implementation and must require explicit future opt-in and privacy review.
8. **Space-scoped cache only**, keyed by exact input and extractor configuration, with latest-only-aware cleanup. No perpetual archive or cross-space deduplication.
9. Later introduce **document outline, section reads, reference resolution and bounded context bundles** over REST/MCP. External agents plan; C0 validates and retrieves. No internal generative agent or hosted LLM required.
10. Show document progress in **Knowledge Explorer**, detailed task status in **Background Work**. Existing sources remain usable through **lazy migration** and explicit reindex; no automatic corpus-wide rewrite at upgrade.
11. **Correctness/security first**, then performance, cost and answer quality; maintain existing Core/consumer/image/native acceptance and deployment requirements.

### Non-goals

- No partial-publication mode; no hidden omitted pages described as complete.
- No OCR of every already-readable PDF page by default.
- No autonomous LLM analysis or extraction-time claim generation.
- No different versions/history browser, permanent storage of retired extraction bodies, or reuse of expired exact citations.
- No change to connector authorization scope, automatic source discovery, production schedules or external-source approval.
- No unconditional multi-instance distributed extraction or new message broker.

## 2. End-to-end contract

```text
External collector / REST upload
  -> validate input, original hash, space, source version, limits
  -> stage a non-public candidate generation and immutable original
  -> build a deterministic, bounded extraction-unit manifest
  -> enqueue each unit durably in PostgreSQL
  -> independent workers claim/parse/persist results (retry failed units only)
  -> verify every unit and assemble canonical full document in source order
  -> derive locations / structured blocks / search chunks / optional vectors
  -> short transaction: recheck authority + generation + hashes; atomically publish
  -> retire old exact evidence, clean up orphaned original/staging artifacts
```

**Three separate identities must never be conflated:**

| Identity | Responsibility | Publication rule |
| --- | --- | --- |
| Logical source/document and existing multipart parent | Stable external identity, complete source reading | Stable logical links resolve current only |
| Extraction run and unit | Internal, retryable processing state | **Never** visible as authoritative evidence or individual logical documents |
| Published document and search chunk generation | Searchable evidence with exact source offsets and citations | Published atomically; expired exact IDs return 410 |

### Core invariants (apply to *every* milestone)

- Existing `c0_sources`, `c0_source_versions`, `c0_documents`, `c0_chunks`, `c0_embeddings`, current-generation rules and external `source_sync` parent/part contracts must not be weakened.
- Preserve original input bytes/hash through the attempt. Before committing an extraction result, verify the input belongs to the **same selected space, source version and processing generation**. No completion from an expired lease or superseded generation may overwrite current state.
- All current reads remain authorized inside the same space. Staging cannot appear in general search, source listings or citations. Admin status routes must not disclose protected-space titles, file paths, document text or internal credentials to unauthorized callers.
- Stage output may be persisted for recovery; **publication is all-or-nothing**. On initial failure the document is incomplete/unsearchable; on replacement failure the previous published complete generation remains readable and searchable.
- The assembler validates the ordered manifest, contiguous normalized offsets, page/section coverage, bounds, content hashes and final full-text SHA-256. **Never assemble from overlapping search chunks or previously published multipart receipts.**
- Idempotent enqueue, acquire and completion must survive dropped replies, SIGTERM, worker crashes, duplicate requests, restart and competing workers. Use compare-and-swap revision/lease fencing, not 'we expect exactly once' assumptions.
- Follow current latest-only policy: retired bodies, staging, temporary files and old chunk/vector rows are eventually removed; payload-free tombstones remain. **A → B → A** creates a fresh publication identity. Identical unchanged current data may preserve existing identity under current proven rules.
- Continue bounded parser isolation, file safety, symlink checks, XML/ZIP/PDF safeguards, least-privilege execution, output validation and source content as **untrusted data**. External retrieval must not execute content instructions.
- Reuse existing OAuth, access, ingestion journals, source-space bindings, expected revisions and uncertainty reconciliation; absence of permission is never interpreted as an empty result.
- **Backward compatibility:** existing documents, REST/MCP operations, client packages and external source-sync workflows continue to work. Introduce opt-in flags and gradual rollout. Do not deploy or reindex real instances as part of merely implementing a milestone.

## 3. Work units, lifecycle and suggested persisted contract

Finalize naming after reading current migrations/callers in milestone M0. Prefer extending current `c0_jobs` to schedule extraction-unit work while keeping its ordinary synchronous handler contract unchanged; add a dedicated leased execution path where needed. If extending generic jobs introduces unacceptable compatibility risk, isolate extraction leases in a **PostgreSQL** table and document the reason. Do not build an unrelated workflow engine.

A candidate schema (adapt before migrations):

- **Extraction run:** `id`, `space_id`, `source_version_id`, `processing_generation`, `original_sha256`, `media_type`, `partitioner_revision`, `extractor_profile`, `manifest_sha256`, expected unit count, state (`staging|extracting|assembling|ready|failed|superseded`), timestamps and safe error code.
- **Extraction unit:** `id`, run/space IDs, ordinal, **source-relative** page range or structural boundaries, stable input partition fingerprint, selected engine/settings revision, attempts, queue time, state (`queued|leased|succeeded|retry_wait|failed|cancelled`), worker/lease token, lease deadline, error code and durations.
- **Unit result:** run/unit IDs, text and typed local location metadata, result hash, bounded byte/character counts, optional confidence/provenance, readback checksum. Keep staging results out of published evidence tables. PostgreSQL text staging is preferred initially; do not add object storage solely for this feature.
- **Publication record:** references only the validated ready run and current source-version generation. Persist idempotent completion status so interrupted acknowledgement can be reconciled.

Define exact state transitions and persistence boundaries, including terminal failure, administrative retry, cancellation, supersession, cleanup and race with original deletion. Each claimed unit receives a unique **lease token**; a stale worker's late result must be rejected even when its process is still running.

Default attempt policy: **3 automated attempts per unit**, bounded exponential backoff and bounded jitter; distinguish transient timeout/provider error from terminal invalid/encrypted/corrupt input. Explicit manual retry can rearm only failed units if their original and successful staging results still exist. Existing 24-hour abandoned-staging cleanup remains the initial ceiling; after expiry, report `staging_expired` and recreate the run from the still-authorized retained source rather than pretending successful outputs remain. Do not delete an original needed by a live run.

## 4. Milestones and delivery order

Every milestone is one separable, tested PR; **don't combine future milestones because they are described here**. Report implementation evidence and unknowns, not fictional benchmark improvements. Dependencies are explicit.

### M0 — Freeze current behavior and specify extraction contracts

**Purpose:** baseline without changing runtime behavior. **Depends on:** current original `main`.

**Work**
- Re-read `AGENTS.md`, root `PLAN.md`, relevant `c0-develop-core`/`c0-create-feature` skills, source/worker/migration code and current released-Core pin. Capture actual tested limits and old/full-document/source-sync behavior.
- Create deterministic fixtures: 100-page readable PDF with individually identifiable pages; 2-page PDF with an unsupported scanned page; PDF with empty legitimate pages; DOCX with headers, tables and section boundaries; Markdown with fenced headings, links, Unicode and CRLF; plain text; external multipart logical parent.
- Specify canonical normalized-text assembly and offset rules, page/blank/scan classification, manifest hash, bounded task/result payloads, lease state machine, actor roles, read/status API contracts and cancellation/supersession semantics.
- Record a test matrix and baseline timings for whole-document extraction, failed whole-document retry, existing citations, full-document view and worker/queue interference. Add no production data or private sample.
- Record the migration/compatibility choice and verify the latest-only/current-content protocol triggers accept the proposed new writes.

**Likely paths:** `docs/ingestion-pipeline/`; `tests/fixtures/evidence/`; extraction/source/job integration tests.

**Done when:** fixture and design review are committed; all baseline tests run on a **disposable** PostgreSQL instance; no behavior or schema change; acceptance criteria for M1/M2 are reproducible.

### M1 — Durable unit queue and transaction-free extraction execution

**Purpose:** safely execute a bounded task outside the current long-running publication transaction. **Depends on M0.**

**Work**
- Add versioned Core migration(s) for extraction runs/units/results and indexes, including space ownership, uniqueness, referential integrity, constrained states, cleanup and lease fencing. Use the **next sequential Alembic revision at implementation time**; don't assume 0024 is still free.
- Introduce a dedicated claim → external isolated parse → persist result → acknowledge pattern. Queue reservation and result commit are separate, short DB transactions. Use `FOR UPDATE SKIP LOCKED` or equivalent PostgreSQL-safe acquisition.
- Add lease expiry/reclaim, per-attempt unique token, stale-writer rejection, bounded timeout, safe parser error classification, idempotency and generation cancellation. Do not keep a PostgreSQL transaction or shared `content_lock` open while parsing.
- Keep existing `source.extract` and unrelated job handler behavior unchanged behind a feature flag; preserve existing generic 30-second timeout / attempt constraints until explicitly migrated.
- Add bounded maintenance of abandoned units/results and metrics of claimed/succeeded/failed/retried work. Retain the existing worker for ordinary deterministic schedules.

**Likely paths:** `packages/czero-core/src/czero_core/{jobs,worker,sources}.py`, new extraction service, Alembic migrations, `app/src/czero_app/job_handlers.py`, unit and integration tests.

**Done when:** two claimants cannot own one attempt; killing a worker after claim safely reclaims only its expired work; stale completion is rejected; successful results survive worker restart; no long parser transaction; ordinary maintenance/health jobs still run; old extraction remains the default.

### M2 — PDF fan-out, selective retry and atomic assembly

**Purpose:** first usable end-to-end per-unit extraction path. **Depends on M1.**

**Work**
- Preflight the original PDF once: input checksum, encryption, page count, limits, section/page inventory and a deterministic manifest. Partition into pages or small page ranges. Use single-page tasks for OCR candidates; group cheap text pages when justified by measurements.
- Implement a restricted page-range parser that consumes the **verified immutable original**. Do not treat an independently reconstructed PDF fragment as the original without proven fidelity.
- Persist unit outputs with ordinal, normalized text, local page locations and SHA-256. Recognize genuinely blank pages; an image-only page is a terminal `unsupported_scan` result until the OCR milestone.
- On transient failure retry only affected units. Verify all outputs before deterministic assembly; preserve canonical PDF separators and precise full-body offsets. Enforce existing 2 MiB / 1M-character body and location/chunk ceilings.
- Publish once through the **existing** current-content service with expected generation and source state. On any failed/absent/corrupt unit, retain the previous complete generation and expose a safe incomplete/failed status; no partial search result.
- Add an authorized, idempotent operator retry route/command for terminal failed units **within the staging lifetime**, with explicit full-rerun behavior after expiry. Add cancellation and replaced-original tests.
- Keep publication compatible with external logical multipart parent snapshots; extraction units never appear as source-sync part receipts.

**Likely paths:** `czero_core/extraction.py`, `sources.py`, `documents.py`, `current_content.py`, Core/API/worker integration tests.

**Required end-to-end fixture:** PDF with 100 distinct pages; intentionally fail units covering pages 37 and 72. Confirm 98 completed units are never re-parsed during recovery, two fail/retry according to policy, final full-text hash/ordering match the baseline, and the document appears only once after complete publication. Kill a worker during unit 72 and repeat.

**Done when:** selective retries, failed-replacement preservation, final readback, citations, stale/superseded behavior, safe cleanup and restart recovery pass actual PostgreSQL/HTTP tests.

### M3 — Configurable parallel extraction workers and resource safety

**Purpose:** process independent units concurrently without serializing heavy work. **Depends on M2.**

**Work**
- Introduce bounded extraction worker pool in the existing NS8 Podman/systemd lifecycle. Start **2** by default; allow **up to 4** only with explicit CPU/RAM/pids and DB connection budgets. Preserve the ordinary serial scheduler/maintenance role.
- Remove global advisory-lock serialization **only for leased extraction execution**, not for short publish/cleanup critical sections. Ensure a slow parser cannot block login, ordinary jobs or another successful unit.
- Fence duplicate work across process crashes, forced termination, overlapping timers and concurrent uploads. Reclaim expired attempts without accepting zombie worker results.
- Limit per-document/per-space concurrent tasks to avoid one 200-page document starving other projects. Apply backpressure on queue depth, extracted bytes, and memory. Handle shutdown gracefully.
- Instrument task wait, run and retry time, queue depth, active worker count, page throughput, peak memory and timeout/recovery counts without high-cardinality Prometheus labels.

**Likely paths:** `czero_core/worker.py` / extraction worker; `imageroot/systemd/user/`; native lifecycle, health and test fixtures.

**Done when:** actual concurrent-worker tests prove no double publication, lost task, unauthorized crossover or lock starvation; kill/restart tests pass; 2-worker mode has no meaningful regression for unrelated jobs; full native upgrade/restart/backup tests pass for systemd/Podman changes. Record measured throughput, don't promise a particular multiplier.

### M4 — DOCX, Markdown, plain text and website-source adoption

**Purpose:** the same queue/retry contract across all supported formats. **Depends on M2–M3.**

**Work**
- Add format-specific deterministic partitioners. DOCX units follow document structure while respecting tables, headers/footers and section-scoped content. Markdown units follow actual parsed headings/blocks, never headings inside fenced code. Plain text uses bounded contiguous paragraphs/character ranges with no dropped separators.
- For tiny/cheap documents, a **single extraction unit** is valid; unitization must not add pointless overhead. Validate reassembly against the existing extractor's canonical output before switching defaults.
- Website crawler continues fetching/converting whole source pages externally. Its resulting Markdown uses the same extraction pathway; don't re-fetch source URLs inside Core or broaden approved connector roots.
- Preserve original document identity, full-body hash, table text, Unicode and explicit product/version/language metadata. Verify nested logical-parent/part boundaries are not accidentally treated as extractor units.

**Likely paths:** Core extraction and tests; `samples/ingestion` integration tests; source publication integration tests.

**Done when:** each format supports deterministic original-to-full-body readback, failed-unit-only retry where meaningful, existing source-sync cursors/receipts, and no content loss or citation regressions.

### M5 — Structural document model and section-aware search chunks

**Purpose:** improve evidence quality without confusing extraction with retrieval. **Depends on M4.**

**Work**
- Add a bounded structured representation of the **current full document**: section tree, headings/ancestors, typed text blocks (paragraph/table/list/code/warning), original text spans, page locations and explicit anchors/links where unambiguous.
- Prefer deterministic parsing. Persist the full extracted body as authoritative; structured blocks and search chunks are *derived*, never substitutes for that body.
- Produce section-aware retrieval chunks within current Core chunk limits, with exact offsets into the complete body, optional small overlaps, bounded splits for oversized sections/tables/code, and enough ancestor context for useful searching. Do not fabricate text in citation spans.
- Keep existing lexical/semantic/hybrid retrieval and reranking available; new chunking is versioned/configurable, not an uncontrolled index rewrite. Avoid eager generation of LLM summaries or unverified semantic claims.
- Changes to published chunk identity require a deliberate **new current generation**, proper retirement and 410 for superseded exact citations; reuse byte-identical identity only where existing rules explicitly prove it. Do not silently mutate published evidence or transfer verification to different bytes.

**Likely paths:** `czero_core/extraction.py`, `documents.py`, retrieval/index services and migrations, browser/source tests.

**Done when:** full-body roundtrip and offsets are exact; structure preserves headings/tables/code/links; multi-hop prerequisite+procedure fixtures improve or match evidence coverage; old citation/version/access tests pass; controlled A/B against fixed-size chunks records actual quality and cost.

### M6 — Optional local OCR and extractor plugin contract

**Purpose:** support scanned PDFs without forcing cloud dependencies. **Depends on M3–M5.**

**Work**
- Define bounded extractor adapter interface and revisioned profiles: `preflight`, `partition`, `extract_unit`, output validation, failure classification, engine/version/settings fingerprint. Prefer an existing installed local OCR backend only if security, licensing and packaging are acceptable.
- Add **opt-in local OCR** for specific pages marked `unsupported_scan`, with per-unit process/resource/time limits and configurable language settings. OCR outputs retain page mapping, confidence/provenance where available, and explicit extraction errors; never silently omit unreadable text.
- Preserve no-external-call, provider-free behavior by default. Keep adapters disabled/unavailable without affecting normal text imports.
- Reserve cloud OCR for a **separate future opt-in** with admin consent, declared data egress, tenant privacy review, credential isolation, budget/rate limits and exact provider/version logging. Do not ship such a provider automatically in M6.

**Likely paths:** Core extractor/adapter registry, packaging/runtime optional dependencies, configuration and tests.

**Done when:** synthetic scanned-page fixtures recover through local OCR if enabled; disabling OCR restores the explicit unsupported-scan failure; OCR unit retry doesn't repeat successful pages; no unexpected network connections or sensitive output in logs.

### M7 — Space-scoped extraction caching and cost accounting

**Purpose:** avoid repeated deterministic work without keeping retired evidence. **Depends on M2–M6.**

**Work**
- Cache **only authorized current-generation or live-staging extraction results**, keyed by selected space, original/content SHA-256, exact partition/input identity, engine/version/config fingerprint and normalized output revision. No cross-space cache hits.
- Reuse successful units for uncertain replies, retries and unchanged authorized reimports while their validated source content remains current. Caching never bypasses latest-only generation, ACL, publication or hash checks.
- Couple cache lifetime to current-content ownership and bounded staging cleanup. Do not keep old source bodies in a permanent shared content-addressed cache. On delete/replace/access change, promptly invalidate or make entries inaccessible and complete existing cleanup.
- Add safe cache hit/miss/reuse metrics, wall time, actual provider usage/cost when reported. Never fabricate cloud/provider costs from request counts.

**Likely paths:** extraction staging/cleanup, current-content retirement, metadata settings and metrics tests.

**Done when:** identical eligible inputs reuse results with correct readback; extractor/config revision forces recomputation; retiring a generation removes obsolete cached bodies; protected-space and A→B→A tests prevent cross-space/history resurrection.

### M8 — Selective context loading over existing REST/MCP

**Purpose:** let agents request exact evidence instead of repeatedly loading an entire long document. **Depends on M5; M7 optional.**

**Work**
- Add **read-only** document outline, bounded multi-section reads, explicit cross-reference resolution and context-bundle APIs. Suggested MCP names (confirm transport conventions before finalizing): `source_document_outline_get`, `source_document_sections_get`, `source_document_references_get`, `context_bundle_get`.
- Every result binds selected space, logical document ID, **exact current generation**, section/block IDs, canonical offsets, source citation handles and content hashes. Resolve stale IDs with `content_superseded` (410) rather than silently returning newer text.
- External model/agent may propose a JSON **plan**; Core validates allowed IDs, ACL, maximum sections, response bytes, estimated token budget, relevance ordering and explicit no-fallback policy. C0 itself does **no** LLM reasoning, inference or external fetch.
- Return only bounded selected evidence, optional referenced definitions and clearly labelled omitted/too-large sections. Never imply an incomplete context bundle is a complete document. Retain whole-document reads for readers/legacy clients.
- Reuse the existing `docs/agentic-retrieval.md` frozen-corpus comparison framework and avoid leaking benchmark question labels into the agent's context.

**Likely paths:** Core documents/retrieval/access services, `app` REST and MCP adapters, plugin/skill contracts, `docs/reference.md`, integration tests.

**Done when:** agent can answer multi-section and cross-reference fixtures with fewer observed context bytes/calls at equal or better citation accuracy; limits, access revocation, concurrent publication and denied-space failures are verified.

### M9 — User/admin progress, inspection and controlled recovery

**Purpose:** make long extraction understandable and repairable. **Depends on M2–M3; can be developed after the Core contracts stabilize.**

**Work**
- Knowledge Explorer: show source extraction `queued / processing (completed-total units) / retrying / failed / ready`; link from the logical source to accessible status. Pending/incomplete first imports do not display fabricated body content.
- Background Work: authorized admin detail with unit ordinal/page range, safe error code, attempt count, timings, next retry, selected parser revision, cancellation/retry actions and clear staging-expired behavior.
- Use bounded, paginated metadata APIs; avoid downloading unit bodies merely to render progress. Never expose source titles, filenames, error text or exact URLs to other protected spaces.
- Separate re-run of failed units from **explicit full reindex**. Reindex is an authorized, generation-changing operation, not an implicit upgrade task; show effect on exact citations.
- Ensure accessibility, mobile layouts, locale-neutral timestamps, valid warning states and stable page behavior when a source is replaced during inspection.

**Likely paths:** `app/static/sources.*`, existing Background Work UI/transport, Core status routes, `tests/e2e` and UI controller tests.

**Done when:** genuine browser/Playwright flow demonstrates the 100-page two-failure fixture, recovery progress, complete publication, error views, Reader/Editor/Admin role boundaries and a protected-space denial.

### M10 — Quality, throughput, upgrade and guarded rollout

**Purpose:** prove reliability and measured benefit before making the new pipeline default. **Depends on M1–M9.**

**Work**
- Add reproducible **extraction** benchmark (text fidelity, page/block/heading/table correctness, cross-reference recovery, hash/offset exactness, failure recovery and successful-unit reprocessing rate). Keep it separate from **retrieval** metrics (Hit@K, evidence coverage, multi-hop complete evidence, citation quality).
- Compare old whole-document parser vs queued units at 1, 2 and 4 workers, with frozen inputs and explicit cold/warm cache states. Measure P50/P95, throughput, DB size/IO, CPU/RAM, queue overhead, extraction latency, and *reported* OCR cost. Include tiny documents to catch regressions.
- Test cancellation, new source generation mid-flight, double submit, two workers racing, stale lease expiry, process kill -9, PostgreSQL restart, full worker restart, corrupted unit result, unsupported scan, upload too large, superseded citations and ordinary jobs under load.
- Upgrade from a **genuine accepted installed predecessor** using NS8 lifecycle, backed-up source volume, released Core pin and exact image identities. Prove pre-existing sources remain readable/searchable, and no automatic backfill or corpus churn occurs. Smoke test explicit reindex on a **disposable** instance.
- Enable as opt-in by format/instance for a controlled pilot, observe queue/retry metrics and compare quality. Only change default after a separate reviewed candidate and successful full local, CI, native Debian/Rocky, browser, privacy/scan, release/Core consumer and deployment gates.
- Preserve frozen failed results, source commits, before/after database/file counts, backup/restore evidence and rollback operator instructions. Rollback of executable configuration **does not imply** a database downgrade; use documented restore/compatibility procedure.

**Likely paths:** benchmark harness, integration and Playwright suites, `imageroot` lifecycle/backup, `docs/administration.md`, `docs/full-documents.md`, operator release notes.

**Done when:** no regression in source-sync, source version/readers, access, jobs, backups and current-document consistency; measured quality is non-inferior with no citation/coverage regression on held-out tests; all required current-source acceptance gates pass. Performance benefits are reported, not assumed.

## 5. Cross-milestone acceptance matrix

| Scenario | Required result |
| --- | --- |
| PDF 100 pages; pages 37 and 72 fail transiently | Only failed units retry; successful attempts are not duplicated; one verified full-body publication |
| Unit fails permanently on first import | Visible failed/incomplete status, no searchable/document body, successful results preserved only within staging policy |
| Replacement fails midway | Previous complete current generation remains searchable and readable |
| Crash after result commit but before response | Readback/reconciliation recognizes success; no duplicate processing or publication |
| Crash after claim; expired lease; late zombie result | New worker can reclaim; stale token cannot commit |
| Upload/reindex races source replacement or deletion | Fenced result rejected; no resurrected content; cleanup finishes |
| Current source A → B → A | Fresh exact generation; old citations 410; no retired body/cache resurrection |
| Multipart external source import | Complete parent only; unchanged receipt, cursor and recovery behavior |
| Two protected spaces contain identical originals | No cross-space cache/metadata leak; independent authorization and cleanup |
| Mixed PDF/DOCX/Markdown/HTML, Unicode, headings/tables/code | Exact full body, stable offsets, correct structure, same supported limits |
| OCR disabled / encrypted / invalid / over limit | Explicit safe failure, no phantom success or outgoing OCR request |
| Ordinary health/maintenance jobs while extraction is busy | Remain schedulable, no global long-held extraction lock |
| Old deployed data after schema upgrade | Still readable without re-extraction; no surprise full-corpus queue |
| Real browser: status, retry, completion | Progress accurate; role/space safe; no partial text or stale display |

## 6. Test and implementation workflow for each milestone

1. Fetch **latest original** `Stell0/ns8-czero/main` into an **isolated worktree**; read current AGENTS, installed NethServer skills, relevant Core/app skills, CI policy and preceding merged milestone. Rebase before PR; never assume a frozen older `main` is current.
2. Implement only the milestone's public contracts and data migration. Prefer Core changes for reusable behavior, app for transport/browser, `imageroot` for NS8 lifecycle. Avoid private credentials and fixtures in Git.
3. Write targeted deterministic tests **first**, including a failing control proving the old behavior. Exercise real disposable PostgreSQL, parse child isolation, race/restart and exact source/body hashes. Do not count skipped DB tests as a pass.
4. Run relevant local Python/Core/app/integration/packaging and Node controller tests, schema/docs checks, browser tests for affected workflows and **full** acceptance whenever migration, worker, container, permissions, Core dependencies or uncertain changes are involved. Follow `docs/ci-policy.md` for PR classification and exact-source artifact proof.
5. Open one independent reviewed PR with schema/compatibility consequences, feature flags, tests, metrics and failure recovery explained. Do not merge or publish on merely writing this plan. For independently released Core, follow producer release → frozen app consumer pin/lock → full consumer/native acceptance in order.
6. After merge, record status, accepted SHA, results and next prerequisite in this file or a concise progress log without rewriting prior evidence. Never turn checklist intentions into 'verified' claims. Actual instance deployment requires separate authorization and guarded release actions.

### Suggested implementation/test entry points

- Core: `packages/czero-core/src/czero_core/{extraction,sources,documents,current_content,jobs,worker}.py`; new processing services and versioned migrations.
- App: `app/src/czero_app/{worker,job_handlers,sources,jobs}.py` and corresponding HTTP/MCP composition; `app/static/sources.*`.
- Native: `imageroot/systemd/user/czero-worker.service`, `czero-worker.timer` and validated module lifecycle.
- Existing regression suites: `packages/czero-core/tests/test_extraction.py`, `tests/integration/test_job_worker.py`, `tests/integration/test_sources.py`, `tests/integration/test_source_text.py`, `tests/e2e/test_document_explorer.py`, `tests/e2e/test_website_crawler.py`, and `samples/ingestion` tests.
- Evaluations: `samples/ingestion/examples/website/BENCHMARK.md`, `docs/agentic-retrieval.md`, `scripts/evaluate-agentic-retrieval.py`.

## 7. Risks and explicit review gates

- **Transaction duration:** current worker executes handler under a DB transaction. M1 must genuinely move extraction outside it; moving code into another function without changing transaction boundaries is not completion.
- **Resource spikes:** 4 concurrent subprocesses in a single existing 1 GiB Podman worker container may be unsafe. Worker budget and container resource limits must be measured before enabling parallelism; adjust bounded pool sizes rather than hiding OOM failures.
- **Canonical text fidelity:** per-page/section extraction can alter separators, headers or table order. Compare normalized extracted bodies against old stable fixtures and independently labelled originals; always preserve actual original bytes.
- **Latest-only vs caching:** staging and optional cache cannot become undeclared version-history storage. Keep current-source ownership, explicit lifetime and cleanup on every retirement path.
- **Logical multipart sources:** `c0_project_source_part_v1` tracks external publication composition; splitting one of those parts into extraction tasks must not create nested visible documents, advance a source cursor early or change parent hash semantics.
- **Citation identity on reindex:** a new chunking profile can alter exact evidence identities even without a changed original. Require an explicit new publication generation and superseded citations, except narrowly proven identity reuse.
- **Internal vs external inference:** local deterministic extraction and optional OCR are in C0's worker domain; planning, summarization and research remain with external agents. Any cloud OCR requires new explicit data-egress approval.
- **Compatibility with existing installations:** schema/worker changes must be forward-safe with documented upgrade orchestration and an available previous-current-data backup. Never assume downgrade support.
- **Evaluation integrity:** preserve held-out questions, corpus manifest hashes, original evidence, model/provider versions, actual observed token and cost data. Small exploratory results are not production-quality evidence.

## 8. Later, explicitly out-of-scope candidates

After M10 acceptance, consider larger PDFs/uploads, distributed multi-host workers, specialized remote OCR, complex table/layout vision extraction, per-format queue autoscaling and advanced semantic cross-reference discovery. Open separate design/approval milestones with clear benchmarks; do not quietly expand limits in M1–M10.

---

**First implementation task:** execute **M0 only** on the newest original main, confirm each existing contract, add the specified fixtures and submit a *documentation/tests-only* PR. Do not start M1 until M0's state machine and assembly/hash/lease contracts are reviewed.
