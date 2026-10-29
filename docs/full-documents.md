# Complete current source documents

Knowledge Explorer offers All knowledge, Articles and Sources. Wiki articles are
authored knowledge; imported sources are evidence. Each logical document retains
one current complete generation. This replaces the previous history guarantee.

## Identity and publication

A single-source document keeps its source UUID. A multipart document keeps its
`c0_project_source_snapshot_v1` UUID. Its current generation has verified
`c0_project_source_part_v1` membership; the document reader no longer depends on
snapshot or synchronization history. Generation identities are never recycled,
including A → B → A updates. Counters remain monotonic concurrency controls.

Core stages a replacement, extracts it, validates all retained document bodies,
and atomically publishes the complete generation. It verifies ordered parts,
contiguous UTF-8 byte ranges, hashes, parent identity and whole-document hash.
Overlapping search chunks are never assembly input. Pending, failed or corrupt
parts leave the previous publication intact. An initial incomplete import reports
`state=incomplete`, `body=null` and cannot enter ordinary search. A part is only
technical staging until its whole parent publishes.

Publication deletes superseded source bodies, originals, extracted documents,
chunks, vectors and obsolete part membership. Wiki updates retain one current
body. Database cleanup is transactional; durable file-deletion intents are retried
by the worker after rechecking ownership. Abandoned staging is bounded and expires
after 24 hours. There is no configurable content-history retention.

Archiving preserves the current body and existing archive semantics. Old manuals
for different product versions and separately authored reports remain distinct
current documents. Authored quotations remain authored text; expired evidence is
marked stale instead of deleting the author's work.

## Interfaces and expired evidence

| Read | REST | MCP tool |
| --- | --- | --- |
| Bounded current summaries | `GET /api/v1/source-documents` | `source_documents_list` |
| Complete current body | `GET /api/v1/source-documents/{logical_document_id}` | `source_documents_get` |
| Current containing document | `GET /api/v1/source-versions/{version_id}/full-document` | `source_version_document_get` |

Every operation rechecks current Reader authority and explicit protected-space
selection; delegated calls require `c0:read`. Authorization precedes tombstone
lookup, so another space's expired IDs reveal no metadata. No denied-space fallback
is allowed. Listings contain 1–100 metadata summaries; selecting a document reads
its body. Retained technical compatibility history routes list current content
only. History tools are removed from MCP capabilities and the reader has no
history selector or rollback action.

A stable logical URL opens current content. An exact generation/version/chunk
citation selects only that evidence. Once retired, it returns HTTP 410 with
`content_superseded` (the same structured MCP error), never new text under the old
identity. A reader may offer a separately labelled current-document link. Minimal
tombstones contain IDs, generation, hash and status only. Claims and annotations
whose evidence expires report stale/unsupported evidence. Changed content never
inherits verification. No deterministic evidence-transfer rule is implemented.

An optional `revision_id` must match the current generation. Concurrent read
snapshots retain explicit generation identity; searches recheck returned current
IDs and may report `content_superseded` when publication races the request. Bytes
already delivered cannot be recalled. Superseded mutation replays likewise return
410; callers read current state, reconcile and use a new key with the current
expected revision. Replay receipts contain no retired bodies.

## Formatting and limits

The existing markdown-it 15.0.2 token renderer uses local assets and inactive raw
HTML/media. Markdown headings, tables, lists, fenced code and links are rendered
with a TOC. Large Markdown is parsed in a local worker and rendered in bounded
batches; selection/access-loss guards invalidate late results. Relative links use
validated provenance and local heading anchors remain local. PDF/DOCX/plain text
retain extracted text without claiming original visual layout.

The sixteen-MiB parent, 2 MiB/one-million-character per-part extraction, 10 MiB
file-upload and 8 MiB MCP response bounds remain unchanged. The publisher uses a
single REST upload when it fits existing extraction limits, and genuine multipart
otherwise. Normalized UTF-8/LF Markdown must hash exactly like retained readback.
REST/browser reads handle bodies too large for MCP without raising its bound.

Navigation groups explicit product, version, language and path metadata, without
inferring dates or versions from prose. Each bounded summary page reports its own
incomplete navigation; this is not a full-corpus hierarchy download.

See the [migration/preflight](latest-only-migration.md),
[website recipe](../samples/ingestion/examples/website/README.md) and
[real-browser acceptance command](development.md#full-document-playwright-acceptance).

An unchanged multipart part may retain its existing version/chunk IDs only when
retained bytes and hashes match exactly and the new whole-document membership
passes order, range and parent-hash validation. This deterministic reuse preserves
that exact unchanged evidence; it does not transfer verification to different
bytes or to another part. Wiki metadata/archive changes may advance concurrency
counters while retaining byte-identical body/chunk/vector identities. No semantic
verification is inferred from either reuse rule.

Before the first multipart publication, discovery shows one incomplete first-part
entry with no readable body. Current membership replaces that pending entry with
the verified logical parent after atomic publication; its source link still opens
the current complete parent. Other unpublished parts are not listed separately.
