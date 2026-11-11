# Secure cross-space references

Implementation contract selected by the operator on 11 November 2026. Inspected
and original-main implementation baseline: `bdb928e62a057309d7822282fd7c505303d3bbfb`.
Core producer 0.46.0/schema0037, app0.63.0; released consumer still Core0.44.x.
Producer development, immutable Core publication, consumer adoption and live
acceptance are separate milestones. No live deployment is authorized here.

## Purpose and architectural decision

Add one outgoing-only table and a small Core service, separate from object
relationships and knowledge graphs. A reference identifies two current resources;
it grants no authority, stores no target content, is not evidence and never
publishes knowledge. Object JSON pointers already permit independently authorized
reads, but reveal pointer metadata to every source reader. Dedicated references
also hide the edge itself when either endpoint cannot currently be read.

Reuse persisted SpaceService policies and AccessService.checked_actor. Do not
extend same-space object relations, entity links (which retain label snapshots),
graph traversal, feeds, indexing or exports. Project subscriptions are a separate,
authorized content-copying workflow. Preserve existing composite ownership FKs,
latest-only evidence, credential bindings, API-key ceilings and OAuth scopes.

## Endpoint and storage contract

Both endpoints support object, page, source, entity and claim. Descriptors use
`kind`, stable UUID `id`, and mandatory registered `type_name` only for objects.
Pages are stable Wiki pages; sources are c0_sources, never versions, documents or
chunks. Multipart parents use their managed object type. Never silently convert
an ID into another kind. Only relation kind `references` is supported.

The additive next migration creates c0_cross_space_references with immutable
server UUID, explicit source_space_id/source_kind/source_id and corresponding
target fields, relation_kind, created_by and created_at. No Shared default.
Source and target spaces must differ. Five nullable typed UUID columns at each
endpoint enforce exactly one populated column matching its kind and generic ID.
Each has a composite (space_id,id) FK with hard-delete cascade. Unique logical
edge: source tuple, target tuple, relation_kind. No labels, descriptions, metadata,
URLs, bodies, excerpts, credentials or target snapshots are persisted.

Index outgoing UUID pagination, selected target spaces, and populated typed FK
columns for endpoint deletion. Inspect actual query plans before removing indexes.
References are immutable: change means delete/create. Hard deletion cascades;
soft-deleted/archived endpoints hide retained edges, restoration can reveal them.
Current edits retain edges and summaries use current revisions. Claims retain
existing stale-evidence status; linking a claim never verifies its evidence.

Use actor/source-space-scoped c0_knowledge_receipts with payload-free acknowledgement
and reference ID. Changed-argument retry is409. Create replay rechecks both
endpoints and current authority, returns the original acknowledgement, and never
resurrects a deleted edge. The acknowledgement does not assert current existence.
No reference events enter source-only object/knowledge feeds.

## Authorization and transactions

Create requires source Editor, target Reader and both c0:write/c0:read. List
requires source Reader/c0:read and independently readable targets. Follow uses a
fresh existing content API. Delete requires only source Editor/c0:write, filters
the full source tuple plus reference UUID, and returns indistinguishable empty
success for missing, foreign-source and already deleted UUIDs. Never read its target.

List accepts 1–10 distinct explicit target-space UUIDs. Denied, missing, archived
and deleted targets contribute nothing: no placeholders, hidden counts, IDs,
space names, omissions or reasons. Invalid global credentials fail. Denied and
unknown source spaces remain403; missing source resource404. Unavailable, denied,
archived or mismatched create targets all return reference_target_unavailable404.
Malformed/bounds errors422; transient DB errors use sanitized503. Responses are
no-store on success and failure. No SQL parameters or supplied IDs in errors/logs.

SpaceService.authorize_many accepts at most11 explicit selectors (source plus10),
validates captured bindings and membership once, queries spaces/grants set-wise,
and shares policy evaluation with authorize. API-key ceilings precede Admin/owner
bypass. Return authorized effective actors internally; no denied diagnostics or
process cache. Keep all original session/OAuth/key bindings.

Use one short READ COMMITTED transaction. Reads acquire hold_authority locks
49372→49378→49379→49382 before credential/membership reads, authorize selection,
check source, query summaries, revalidate time-sensitive credentials and materialize
before commit. Mutations take object49375→knowledge49376 before authority locks,
then the existing content lock, then validate endpoints and receipts. Do not use
the generic mutation helper's source-only replay or preliminary authorization.
No network/model/extraction/streaming work under locks. Existing DB deadlines apply.
An admitted read may finish before waiting revocation; reads after committed
revocation cannot use old authority. Already delivered bytes cannot be recalled.

API-key issuance currently needs Editor in every selected space for a Write key.
Support Editor plus Documentation Reader can use Read+Write OAuth, but cannot
issue one asymmetric Write key. Preserve that limitation; never combine credentials.

## Transport contract

Register typed handlers in the shared REST/MCP catalog:

| REST | MCP | Result |
| --- | --- | --- |
| POST /api/v1/cross-space-references?space_id=UUID | cross_space_ref_create | {reference_id: UUID}, uniform200 |
| GET /api/v1/cross-space-references?space_id=UUID | cross_space_refs_list | {references: [...], next_after: UUID or null} |
| DELETE /api/v1/cross-space-references?space_id=UUID | cross_space_ref_delete | empty/204 |

space_id is required, never inferred/defaulted. Create body: source descriptor,
target descriptor including space_id, relation_kind=references, bounded
idempotency_key. Delete body: source descriptor, reference_id, idempotency_key.
List: source_kind/source_id/source_type_name, target_space_ids, limit1–100(default50),
optional after UUID. Each item contains id, relation_kind and target with space_id,
kind,id,current revision; page/source title as label, entity label, object type_name
only, or claim predicate/stale-evidence status only. Never include object properties,
claim value/evidence or entity traversal. No separate resolve endpoint.

Create primary scope remains Write and advertises additional Read in security
metadata and description; unchanged operations retain single-scope contracts.
MCP tool failures use isError with stable c0/error metadata; HTTP200 is not success.
Preserve REST CSRF and old discovery behavior.

## Bounded query and benchmark acceptance

One list call, one batched policy query, one source identity check and one set-wise
UNION summary query over trusted branches. Filter authorized target spaces and
active endpoints before UUID keyset pagination/limit. Fetch one extra visible row
for next_after. Cursor is only an ordering boundary, never authority. Bound to100
summaries/256KiB. No source-wide quota (hidden-edge occupancy would leak). No
persistent authorization/summary cache. Concurrent inserts may require restarting.

Synthetic benchmark matrix: references1/10/50/100 × selected spaces1/2/5/10 ×
visibility100%/approximately50%/0%; empty selected spaces when spaces exceed rows.
Separate missing/archived fixtures, single/mixed five-kind sets and session/OAuth/key
authentication. Fixed seed,20 warmups,200 samples,three repetitions,concurrency1/5.
Record SQL statements via SQLAlchemy instrumentation, server P50/P95 separately
from client time, peak allocations/RSS, bytes, EXPLAIN(ANALYZE,BUFFERS), and
revocation wait/progress. Include100000 synthetic edges with sparse visible matches.
Compare same-space object relationships, entity links within degree32, and
independent per-target resolution. Freeze baseline before candidate measurements.

Proposed, unmeasured gates: SQL constant with count/spaces (at most two credential
validation passes plus nine fixed statements); maximum case P95≤250ms/P50≤100ms;
same-space P95 regression≤max(10%,5ms); added allocations≤8MiB; no accumulating
RSS, timeout or deadlock. Review failures; never silently relax thresholds.
Existing health/search probe thresholds do not establish this baseline.

## Security and regression matrix

Exercise both-space Reader, source-only, target-only, neither, source Editor plus
target Reader, target Editor without source Write, Admin/owner with constrained
keys, Read-only/Write-only credentials, and keys covering one endpoint. Compare
single/batch policy across roles/scopes/bindings. Test captured Actors after account
block, downgrade, space revocation, disconnect, key revoke, browser logout, expiry
and regrant; old revoked credentials stay invalid.

Test forged kind/type/ID/space, all25 endpoint pairs, FK ownership, hard/soft deletion,
archive/restore, updates, stale claims, duplicates/concurrent create, changed retries,
delete then old create replay, blind deletion of foreign/missing UUID, hidden-edge
pagination and cursors reused across actors/sources/selections. Barrier tests prove
both revocation orderings and endpoint-delete/create atomicity. Compare matched
hidden/nonexistent status/body/headers; inspect gross timing distributions without
claiming constant time. No new graph/search/export/feed discovery or content execution.

End-to-end: private Support ticket plus Documentation guide, four access profiles.
Create as source Editor/target Reader, list/follow as both Reader; target-only cannot
discover ticket, source-only sees no target metadata, neither denied. Revoke target,
verify omission/invalid old tokens; regrant with fresh credentials reveals retained
link. Revoke again, blind-delete, regrant and verify absence. Repeat with Shared target.

## Agent boundary

Reference resolution never copies target content, adds evidence, triggers ingestion,
publishes Wiki/compiler proposals or expands scopes. Read plus separate Write can
already leak information; this feature is not information-flow control. Agent
instructions require an explicitly authorized publication task and destination
before copying information. No automated declassification, publication policy,
scheduler installation or API-key redesign is included. Browser panels are deferred.

## Milestones and completion

| Milestone | Deliverable | Acceptance |
| --- | --- | --- |
| M0 | Preserve contract and roadmap/index links | Documentation checks; no runtime changes |
| M1 | Shared batch authorization | Differential PostgreSQL/security tests, revocation barriers, baseline measurements |
| M2 | Storage and Core create/list/blind-delete | Migration/package/lifecycle/retry/concurrency/25-pair/security tests and benchmark gates |
| M3 | REST/MCP and agent guidance | Authenticated parity/errors/scopes/no-store/discovery/archive and end-to-end tests |
| M4 | Immutable Core release then separate consumer lock adoption | Exact producer full/native, external package install, Debian/Rocky, released Git identity inside actual app image |
| M5 | Separately authorized deployment; optional later browser panels | Supported backup/update/readiness/privacy/restart/preservation and browser checks |

Keep M1/M2 independently reviewable. Follow full/native CI classification,
exact-source merge gate and automatic regular merge policy. Preserve frozen
candidates and failed/private evidence. Local tests, merge, publication and installed
acceptance are separate facts. Main risks: metadata leaks, policy divergence,
revocation deadlocks, multipart confusion, authorized copying and release mismatch.
Minimum useful delivery is all five kinds, guarded creation/list/blind-delete and
real PostgreSQL plus authenticated REST/MCP proof, without browser mutation panels.
