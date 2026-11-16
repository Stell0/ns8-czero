# Automatic sources

Implementation candidate: space-scoped native public GitHub and website updates.
A definition selects remote content; collected documents use existing C0 sources,
extraction, latest-only publication and indexing. No model executes in the worker.

Core 0.51 adds schema0042 after the immutable Core 0.50/schema0041 release.
Its published personal-space services and migrations remain intact; this feature
does not enable or install native personal-data collection. The app's released
Core 0.49 lock remains unchanged until independent publication and adoption.

Readers inspect definitions and run status. Editors create, revise, pause, remove
and run definitions in their selected space with c0:write. Enabling a definition
explicitly creates a revocable background authorization for this selection and
space, attributed to its saving account. It is independent of browser logout and
limited to the saving account's current Editor access. Account or space grant
revision changes invalidate that authority; renewed authority requires a save.
Credentials, private repositories and automatic organization discovery are outside
this first public-source implementation. Removing configuration retains documents.

Definitions carry strict type-specific configuration, expected revisions and
actor-scoped replay keys. Manual and scheduled execution share one durable run,
with bounded collection outside transactions, fenced publication and persisted
progress. Run order uses monotonic counters; leases use the database clock.
Completed/cancelled checkpoints are cleared. Older run summaries expire after
30 days while the latest summary and active checkpoint remain.
Edits or pause invalidate in-flight publication. Failed or partial work
cannot advance successful completion. Existing documents are replaced only through
the normal staged complete-document pipeline. Manually edited/deleted sources
cause a conflict rather than being overwritten. Remote disappearance never deletes
stored evidence. Run receipts contain metadata and hashes, never fetched bodies.
Extraction rechecks the saved authority at final publication, including the
parallel parser path. Stopping updates retires unpublished replacements and keeps
the previous complete document. Explicit resumption fetches fresh content while
retaining logical source IDs. Core embedders pass their trusted `AccessService`
as `access=` to `register_source_handlers`; native staging fails closed without it.

GitHub file collection selects UTF-8 text/code; known binary assets and documents
are excluded. Unsupported non-UTF-8 selections fail explicitly without truncation.

Website selection uses explicit public roots, seeds, include/exclude patterns,
robots rules and bounded traversal. GitHub selection uses explicit public
repositories and file paths/categories. Public HTTP rejects private DNS answers,
pins verified peers, verifies TLS and bounds redirects, requests and bytes.

Acceptance requires real database authorization, revisions/replays, concurrent
claims, restart recovery, pause/revocation during collection, unchanged-content,
partial coverage and extraction failure tests, matching REST/MCP contracts, UI
access-loss/draft guards and real browser workflows. Schema changes require full
native migration/recovery acceptance. Core publication and released-consumer
adoption are separate gates; no live update or existing job migration is implied.
