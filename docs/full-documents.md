# Complete source documents

Knowledge Explorer offers All knowledge, Articles and Sources. Wiki articles
remain authored knowledge; sources remain externally ingested evidence. No Wiki
page is created just to make an import browsable.

## Identity and storage

A single-source logical document uses its source UUID and immutable version UUID.
A multipart original uses its existing `c0_project_source_snapshot_v1` object UUID
and immutable `c0_project_source_snapshot_history_v1` UUIDs. `DocumentService`
provides a generic read API over these existing storage forms; reading does not
require a project workflow or create another database model. Use the canonical
`id` returned by a whole-document read when requesting its history.

A selected snapshot names at most 100 immutable part receipts. Core restricts all
joins to the explicitly authorized space and verifies parent/connector identity,
ready extraction, ordinal order, contiguous byte lengths, source/text hashes,
total bytes and the full parent hash before returning a body. It reads retained
`c0_documents`, never overlapping retrieval chunks. A changed original creates a
new immutable snapshot; a shorter snapshot names only its current parts. Old
versions and citations remain readable after updates or archive.

Pending/missing parts return `state=incomplete` and `body=null`. Integrity errors
return the existing static conflict response. Unpublished importer parts stay out
of ordinary discovery; they remain inspectable through technical source tools.
The last complete snapshot remains current until a new complete one is saved.
New part receipt identities include their parent hash. For exact legacy receipt
identities that an older writer reused, explicit immutable snapshot membership
and all hashes must prove the reconstructed effective offsets. Current mutable
receipts are never borrowed to complete historical content.

## Interfaces

| Read | REST | MCP tool |
| --- | --- | --- |
| Bounded summaries | `GET /api/v1/source-documents` | `source_documents_list` |
| Selected complete body | `GET /api/v1/source-documents/{logical_document_id}?revision_id=…` | `source_documents_get` |
| Bounded history | `GET /api/v1/source-documents/{logical_document_id}/history` | `source_document_history` |
| Exact cited version's original | `GET /api/v1/source-versions/{version_id}/full-document` | `source_version_document_get` |

Every call uses current Reader authority and an explicit `space_id` for protected
spaces; delegated calls require actual `c0:read`. Denial never falls back to
Shared. Discovery/history return 1–100 items with the established offset bound.
Only selecting a document reads its full body. The existing sixteen-MiB parent
bound, 2 MiB/one-million-character per-part extraction bounds, 10 MiB file upload
bound and 8 MiB MCP response bound remain unchanged. Use REST/browser for logical
responses too large for MCP; no transport limit is silently raised.

Existing text extraction normalizes UTF-8 BOMs and line endings. The multipart
publisher requires normalized UTF-8/LF input whose exact bytes match retained
readback; mismatched input stays unverified. Ordinary uploads remain readable as
the complete normalized retained text. This reader does not recover discarded
original layout or byte encodings from extracted text.

Original `documents_get`, chunks and citations retain their exact immutable part
contracts. Existing `/sources?source=…&version=…&chunk=…` URLs still work. New
`/sources?document=…&snapshot=…` links retain a canonical logical identity. Search
opens the complete containing document while displaying its exact cited passage,
including historical snapshots containing a now-obsolete final part.

## Presentation and limits

The existing markdown-it 15.0.2 allowlisted token renderer handles source Markdown.
Large Markdown is parsed in a local worker and its DOM is built in bounded
batches; access/selection changes stop or invalidate older rendering. TOC links
navigate rendered headings. Text and PDF/DOCX extraction stay plain text, with
line breaks preserved and no claim to original visual layout. HTML and remote
media stay inactive; links use the existing safe URL policy. Relative source links resolve
against validated canonical/original provenance when available; TOC anchors stay
local.

Navigation groups explicit product, product-version and path metadata. It never
infers authoritative versions from document text. Each bounded summary page has
its own groups and an explicit incomplete-navigation notice. Older unclassified
sources use Other sources. This is not a corpus-wide hierarchy download.

## Verification

The [development guide](development.md#full-document-playwright-acceptance) gives
the pinned real-browser command. Synthetic fixtures cover formatting, three-part
legacy reconstruction, exact original bytes/hash/order, shrink/history/citations,
search navigation, read-only protected access, revocation, late replies, sign-out
and a large single REST upload. Core/integration cases additionally validate
corrupt/missing/queued parts, legacy receipt reuse, archives and role boundaries.
No production data or deployment is part of this feature's acceptance.

### Measured development fixtures

A local headless Chromium sample loaded the 534,750-byte legacy multipart
fixture in 2,073 ms and rendered its Markdown in 955 ms. During rendering the
browser serviced 56 timer ticks; the largest measured interval was 60 ms.
The directory loaded in 272 ms for that small corpus. These are individual
observations, not a service-level guarantee.

The earlier directory query timed out at the unchanged five-second SQL deadline
with 10,000 logical parents. A revised query using indexable UUID columns and an
equality anti-join returned 50 metadata summaries in 562 ms at offset 0 and 505 ms
at offset 9,950. PostgreSQL EXPLAIN confirms primary-key lookups and a hash
anti-join. The regression seeds complete synthetic source/version/document and
receipt/snapshot rows, reads no bodies for listing and uses bounded cleanup.
Pagination bounds response size; latency still depends on database resources and
stored receipt history.
