# M0 extraction contracts

This specifies the next implementation against original C0 main
`fe38990b7c74594e2a7f91dbbb23697e7d1f1793`. M0 changes tests and documentation
only. The [approved execution plan](https://github.com/Stell0/ns8-czero/blob/7a737e89ada542a3a4f04f45185ff7e6b9a2c3d5/docs/ingestion-pipeline/PLAN.md)
requires one independently reviewed PR per milestone. M1 remains gated on review
of this contract; M2 remains gated on M1 acceptance. See [baseline evidence](BASELINE.md)
and [synthetic originals](../../tests/fixtures/evidence/pipeline/README.md).

## Frozen existing behavior

The producer and frozen app consumer both select Core 0.36.1; the consumer lock
names `core-v0.36.1`, Git source `8dbb746c000401cc07ebbe85429bcbaf8e2bd113`,
range `>=0.36.1,<0.37.0`. Schema is `0023_current_content`. No version, dependency,
lock, migration, feature flag, runtime file or connector contract changes in M0.

| Boundary | Current enforced value |
| --- | --- |
| Original file | 10 MiB; regular file, original SHA-256 and size verified |
| Extracted full body | 2 MiB UTF-8 and 1,000,000 Python Unicode code points |
| PDF | At most 200 pages and 16 MiB decoded content streams |
| Locations / chunks | At most 4,000 / 4,096 |
| Retrieval chunks | Default 1,200 characters, 150 overlap; allowed size 256–4,096, overlap 0–size/4 |
| Isolated parser | 25 seconds parent wall time; child 20/21 seconds CPU, 512 MiB address space, zero file output |
| Parser response | At most 16 MiB captured stdout; validated text and locations |
| DOCX archive | At most 1,000 entries, 16 MiB expanded, 4 MiB per entry; ratio check and existing XML/ZIP/unsupported-part guards |
| Generic job | JSON payload/result 16 KiB; at most 5 attempts / 30 seconds per handler |
| Source handler | 3 generic attempts / 30 seconds; handled parser errors mark source failed and finish job successfully |
| Worker tick | At most 20 jobs / 90 seconds, one instance-wide session lock |
| Abandoned replacement | Existing cleanup retires non-current versions older than 24 hours |
| MCP text ingestion | 128 KiB UTF-8; larger originals use existing REST upload/publisher |

The current worker claims in one transaction and executes each complete handler
in another transaction. `source.extract` takes `content_lock` **before parsing**.
Safe `ExtractionError` results do not cause automatic source re-extraction:
`SourceService.retry(expected_generation=...)` explicitly advances generation.
Unexpected handler exceptions use ordinary queue backoff. These are distinct
failure paths and neither establishes selective retry.

## Canonical text and offsets

The original is immutable input. SHA-256 always hashes the exact original bytes;
canonical text hashes always hash UTF-8 without a BOM. Do not apply Unicode NFC,
trim nonblank fragments, rewrite links, insert headings or synthesize page text.
Normalize CRLF and CR to LF once, preserving all other characters. Offsets are
zero-based, half-open Python Unicode code-point ranges into the complete body,
never UTF-8 byte offsets or JavaScript UTF-16 offsets. External source-sync
`start_byte`/`end_byte` remain **UTF-8 byte offsets** under their existing contract.

For PDF, process the exact original with the same pinned engine. Each source page
has an inventory entry even when it contributes no text. Preserve page numbers
starting at 1. A nonblank page contributes its normalized text unchanged; join
contributing pages with exactly `\n\n`, with no leading/trailing added separator.
Locations exclude separator spans and blank pages; page indexes may have gaps.
Blank entries have zero body contribution and an explicit classification, rather
than invented zero-length published locations. Entirely blank input fails `no_text`.

Classification must distinguish readable text, verified blank, unsupported scan
and invalid input. An empty text result with an image (including a nested Form
XObject) is `unsupported_scan` with OCR disabled, even after earlier readable
pages. It is never a successful empty unit. M2 preflight must fail closed for
ambiguous non-text graphical content, retaining its original for inspection.
The existing parser's no-image/empty-text rule is the measured baseline, not
proof that every visually nonempty page has been detected.

DOCX currently walks body paragraphs/tables in order, then distinct defined
headers/footers in section order, deduplicating merged cells and linked parts.
Empty paragraphs create gaps in location indexes but no body text. A new
partitioner must preserve this canonical output before changing defaults; section
metadata must not reorder headers into body text. Plain text/Markdown retain
normalized full text. Today's Markdown location regex also matches fenced
headings; the frozen fixture records this limitation. M4/M5 may improve derived
structure deliberately while retaining body fidelity.

The assembler consumes successful **unit results**, never overlapping search
chunks or external publication-part receipts. It checks unique ordered ordinals,
complete page/structural coverage, exact local ranges/hashes, contiguous canonical
assembly (with explicit separator gaps), final character/UTF-8 limits and the
final full-text hash before deriving retrieval chunks. Validate each published
location/chunk slice against the full body. Any missing, duplicate, mismatched,
over-limit or corrupt result prevents publication of the entire candidate.

## Manifest identity and bounded staging

Freeze a versioned manifest before scheduling units. A manifest binds the exact
space, source version, processing generation, original hash/size/media type,
partitioner revision, extractor engine/version/settings and normalized-output
revision. It includes ordered unit fingerprints and source-relative boundaries.
PDF boundaries use inclusive first/last page; text boundaries explicitly name
their coordinate system. No request supplies an executable engine/import/SQL/path.

Canonical hash encoding is UTF-8 JSON with sorted object keys, separators `,`/`:`,
`ensure_ascii=False`, `allow_nan=False`, no BOM/newline. Only validated schemas,
strings, integers, booleans, null, arrays and objects are permitted; reject unknown
fields, floats, duplicate JSON keys and booleans where integers are required.
Absent optional fields are encoded as null in the versioned schema. Array order
is semantic. SHA-256 hashes those bytes. Unit fingerprint inputs include the run's
input/profile identities, ordinal and boundaries, excluding lease/worker/timing
fields. Result hashes bind text and typed local locations using the same encoding;
also keep a separate SHA-256 of UTF-8 text for canonical full-body checks.

Initial maximums: 200 PDF units (one per page); 4,000 structural units for later
formats, never more than their location ceiling. Cheap text may use one unit.
Persist each unit in its own bounded row; a whole 200-page manifest must not be
stuffed into the generic 16 KiB queue payload. Unit locator/settings metadata
remain at most 16 KiB each. One result cannot exceed existing body/location bounds;
reserve/check aggregate staging character/byte budgets in the result transaction
and check separator overhead again during assembly. Reject excess rather than
keeping an unbounded sum of individually valid results. Limit preflight, claim,
cleanup and status page sizes; M1 defaults to at most 100 metadata rows per call.

Text/locations live in private PostgreSQL staging, separate from evidence tables.
Status contains no result body. No cross-space cache or object store is introduced.
The parser keeps the existing isolated process/resource/output checks; splitting
work does not authorize longer generic handlers or unbounded page reads.

## Persistence choice and lease state machine

Use dedicated `c0_extraction_runs` and `c0_extraction_units` tables in PostgreSQL,
with bounded result columns (or a one-to-one result table), rather than stretching
`c0_jobs`' synchronous contract. The measured worker holds its session lock and
transaction throughout handler execution; changing that generic contract would
affect all registered jobs, schedules and crash recovery. Reuse Core database,
validation, original storage and cleanup services. The existing serial worker and
`source.extract` stay the default behind an off-by-default extraction feature flag.
This is an extraction-specific lease path, not a second generic job engine.

M1 must select the next free Alembic revision, update schema health and packaging,
and add space-bound foreign keys, constrained states, unique `(version,generation)`
run identity and unique `(run,ordinal)` units. A version deletion/supersession must
cancel its run before body/result deletion. Composite ownership bindings prevent
moving a unit/result between spaces or runs. No migration enqueues old documents.

| Run transition | Required condition |
| --- | --- |
| absent → staging | Authorized enqueue; bind original and generation; same request reconciles to same run |
| staging → extracting | Complete validated manifest and units commit together |
| extracting → assembling | Every expected unit succeeded; compare-and-swap claim of assembly |
| assembling → ready | Verified final body; publication and durable completion commit together |
| staging/extracting/assembling → failed | Terminal input failure, exhausted unit, expired staging or assembly validation error |
| any live state → superseded | New processing generation, source replacement/deletion or cancellation; fence every lease |
| failed → extracting | Authorized expected-revision retry, retained original/results, unexpired staging; failed units only |

Ready is terminal for that processing generation. A deliberate reindex of
published evidence stages a fresh source-version UUID/monotonic version number
and run, even when original bytes are unchanged. Processing-generation retries
are only for unpublished candidates: incrementing that counter must never rebind
an already cited source-version UUID to different text/chunks. The reindex
operation must explicitly avoid ordinary unchanged-upload deduplication; its
implementation belongs to the later milestone. User cancellation records a safe
`cancelled` reason on a superseded run. A run in assembling after a crash is
reconciled against publication completion before reassembly; it never republishes
merely because an acknowledgement was lost.

| Unit transition | Required condition |
| --- | --- |
| queued/retry_wait → leased | Due, live run/generation, attempts < 3; short `FOR UPDATE SKIP LOCKED` transaction |
| leased → succeeded | Matching unique token, unexpired deadline, same run/space/input/generation; validated result commit |
| leased → retry_wait | Transient failure or expired lease with attempts remaining; invalidate old token |
| leased → failed | Third transient failure, or terminal invalid/encrypted/corrupt/unsupported input |
| failed → queued | Explicit operator retry within staging lifetime; retain successful sibling units |
| live unit → cancelled | Cancellation, authority loss, deletion, supersession or staging expiry; invalidate token |

Each claim increments a monotonic fencing generation and automated-attempt count
and issues a fresh unpredictable lease token. Default lease: 60 seconds using DB
time, parser wall deadline 25 seconds; M1 must verify this leaves commit/shutdown
margin. No heartbeat is needed at this bound. Reclaim and completion race under
the same row lock; both must compare deadline, token and run generation. A late
result is rejected even if nobody has reclaimed it. No parse or assembly runs
inside a transaction or while holding `content_lock`/the serial `WORKER_LOCK`.

Transient `parser_timeout`, `resource_limit` and `parser_failed` use three attempts
with 10/20-second exponential delays and bounded 0–2-second jitter. Invalid,
encrypted, too-large, unsupported and hash-mismatched input fail terminally.
No provider is called. Manual retry uses an expected run revision and idempotency
key, starts a fresh three-attempt budget only on failed units and retains lifetime
attempt/fencing counters. It cannot replay successful units. Concurrent mutation
or expired/ambiguous authority fails closed rather than resetting state.

## Publication, retirement and recovery

Assemble outside the transaction. In a short publication transaction acquire the
existing content lock first, then source/version and run/unit locks in a documented
consistent order. Recheck persisted authority, original/manifest/result hashes,
complete manifest, expected processing generation, current source and publication
claim. Insert the verified document/chunks and call the existing current-content
publication service, recording ready/completion in the **same** commit. Never let
a stale generation overtake a newer candidate. No unit is a public source version.

Existing `Database` sets `c0.content_protocol=1` on each connection. Schema 0023
writer triggers protect source/version/document/chunk/object/job/run writes;
they reject legacy writers independently of application authorization. M0 tests
both rejection with protocol 0 and successful writes with protocol 1. New tables
must have the same writer fence; public evidence writes continue through current
Core publication, never direct worker SQL that bypasses retirement. M0 does not
install proposed tables, so their actual trigger/FK acceptance remains M1 work.

First-import failure has no body/searchable chunks. Replacement failure preserves
the last complete generation, including citations, until successful publication.
After publication, retire old bodies/chunks/vectors and invalidate evidence through
existing services. A → B → A has fresh exact identities; expired exact reads return
authorized `content_superseded` (410). Unchanged identity reuse is limited to the
existing proven current-content rules. Authored Wiki/claims remain and become stale.

Staging expires no later than 24 hours after run creation, without extension on
retry. Cleanup cancels/fences first, then removes result bodies and retired run
metadata in bounded batches. Preserve only payload-free completion/tombstone
identities. Do not unlink an original while an unexpired extracting, assembling
or retry-eligible failed run owns it. A reader
must never gain access through a cleanup race. After expiry report `staging_expired`;
explicit full rerun requires a still-authorized retained original (or a fresh
upload), a new run generation and a clear warning about fresh evidence identities.
Do not claim prior successful outputs survive expiry. Source deletion and authority
loss deny status/results immediately, then use the same fenced cleanup path.

External multipart logical parents and `c0_project_source_part_v1`/snapshot records
remain unchanged. Extracting a publication part neither creates another logical
document nor commits connector coverage. The existing publisher verifies all parts
and the whole parent hash before making that parent complete. Extraction status
must not advance its external cursor or masquerade as a source-sync receipt.

## Actors and future read/status interfaces

These are requirements for M1/M2/M9, **not endpoints added by M0**. Final operation
names and transport schemas must be reviewed with callers when implemented.

| Actor | Permitted operation under actual delegated scope |
| --- | --- |
| Reader | Selected-space logical progress, complete current reads/citations; read scope |
| Editor | Same, authorized submission and generation-bound retry/cancel of accessible source; write scope |
| Admin | Same plus bounded unit diagnostics in Background Work; manage scope and explicit space selection |
| Trusted extraction worker | Fixed registered operations on its claimed run; no caller-selected commands or credentials |

Bind each new run to the submitting account and the authorized handoff. For an
OAuth handoff retain the grant identity and approved scope identity, never a token.
Before claim and publication recheck current persisted account/space role and,
where applicable, the still-valid client/grant/resource and actual write scope.
Revocation/expiry fences new work and publication; it cannot silently become a
native Admin job. Existing accepted work on the legacy path is unchanged.

Suggested REST surfaces are a source-version extraction summary and a separately
authorized paginated unit-status collection. Every lookup first authorizes the
selected space using existing services. Unknown/denied/retired outcomes follow
current no-fallback rules. Do not globally probe IDs before authorization.
Responses bind space/version/run/generation/revision and report safe state,
total/completed/failed/retrying units, attempt counts and UTC timestamps.
Diagnostics may include ordinal/page range, safe error, parser revision and next
retry, never paths, credentials, original URLs, text or raw exception strings.
Bound pages to 100 rows and metadata responses to 64 KiB, with stable keyset
pagination tied to run identity. Reader summaries exclude internal unit details.
No body text is downloaded for progress. Retrieval/outline/context APIs belong to
M8 and require separate schemas, exact-generation checks and connector verification.

## Reproducible next acceptance

| Gate | Evidence required |
| --- | --- |
| M0 | Frozen originals/hash/text/location tests, existing source/job/full-document suites, protocol fence, measured whole retry/locks and multipart readback on disposable PostgreSQL |
| M1 claim | Two real claimants: exactly one owner, unique attempt token; parser observed with no open work transaction or shared lock |
| M1 recovery | Kill after claim; expire lease; reclaim; reject zombie completion; crash after result commit reconciles success |
| M1 compatibility | Old extraction remains default; health/maintenance/schedules continue; clean/repeated migration and independent Core package/native gates |
| M2 fan-out | Labelled 100-page original; inject pages 37 and 72 failures; 98 successful pages not parsed again; kill/restart page 72; one final body matches M0 hash |
| M2 publication | Missing/corrupt/duplicate/over-limit unit prevents publication; failed replacement retains old body/citations; complete publication retires old exact evidence |
| M2 boundaries | Original replacement/deletion, stale lease/generation, revoked grant/role, denied protected space, A→B→A and 24-hour expiry all fail closed |
| M2 external parent | Existing source-sync receipts/cursor and logical multipart full-body/hash/readback are unchanged |

Run the commands and interpret the measurements in [BASELINE](BASELINE.md).
No throughput, concurrency, selective-retry, OCR or answer-quality benefit is
claimed before its milestone's real tests. No production ingestion, scheduling,
deployment, Core publication or module release is part of M0.
