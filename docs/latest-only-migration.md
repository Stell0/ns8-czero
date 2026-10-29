# Latest-only storage and documentation collection

The operator's 29 October 2026 request replaces the previous content-history
contract. Preserve one successfully published generation, bounded hidden staging,
monotonic counters and payload-free retry identities. Never infer obsolescence
from product version or publication date. Authored quotations remain authored text.

| Automatic copy | Replacement / cleanup |
| --- | --- |
| Source versions and retained originals | Explicit current pointer; one bounded replacement; transactional retirement and durable file-deletion queue |
| Extracted documents, chunks and vectors | Only current generation is eligible for retrieval/indexing; retire old derivatives with publication |
| Wiki revisions and Wiki chunks/vectors | One current body per page; counters survive replacement/archive |
| Knowledge mutation receipts, including bundles/project replies | Fingerprints plus typed identifiers/counters; retries reconcile against current state and never return retired bodies |
| Multipart snapshot/sync history records | Verified current-generation part membership, copied from validated retained document bodies before deleting legacy records |
| Current sync records for removed multipart parts | Payload-free connector/source/parent aliases preserve stable links; retired version IDs remain unavailable and cannot reconstruct content |
| Claims, annotation anchors and project evidence | Payload-free expired evidence identities; explicit stale/unsupported state; authored knowledge remains |
| Export/read/history endpoints and browser selectors | Current bodies only; old exact evidence is explicitly unavailable; remove advertised history operations |
| Publisher journals and crawler cache | Current representation plus a pending resumable scan; verified cleanup; payload-free run summaries |
| Jobs and security records | Retain operational/security state; results must not become a content archive |

Migration must preflight every current parent, including archived sources, and
block corrupt/ambiguous membership. Select the last complete publication rather
than a queued maximum. Run under the schema/writer fence; old writers fail after
upgrade. Preserve the current bodies, slugs, logical IDs, permissions and counters.
Queue filesystem deletion before committing retirement; retry only obsolete IDs,
never current files. Interrupted migration is transactional and rerunnable.

Back up before upgrade. Data rollback requires an external pre-upgrade backup.
Do not delete operator backups or claim removal from PostgreSQL WAL/storage.
This task uses disposable databases only and installs no schedules.

## Operator procedure

1. Take and verify an external pre-upgrade database/originals backup. This is the
   only data rollback path; a schema downgrade cannot recreate removed content.
2. Stop all old application/worker writers. Independently install the new Core in
   an operator environment, keeping its connection pointed only at the intended
   database. Run `python -m czero_core.retention --dry-run --originals /explicit/managed/source-directory` with
   `CZERO_DATABASE_URL` supplied privately. This command uses a read-only transaction
   and makes zero database/file mutations.
3. Inspect retained/current counts, archived sources, pending imports, superseded
   versions, affected evidence links, original-file cleanup estimates and blocked
   multipart diagnostics. Repair ambiguous/corrupt parents before proceeding; do
   not select a version just because it has the highest queued number.
4. Upgrade using the normal supported application lifecycle. Migration 0023 is
   transactional and can be retried after interruption. Its writer protocol fence
   rejects old processes rather than allowing mixed-version history writers.
5. Start the matching application and standalone worker. The worker drains
   durable original cleanup in bounded batches; failures retry. Run preflight
   again, inspect cleanup status and verify current content/readback hashes and
   authorized expired-evidence responses before disposing of upgrade artifacts.

Preflight does not scan operator backups, PostgreSQL WAL or filesystem free space.
The guarantee covers application-accessible content after migration and cleanup,
not forensic erasure. Operational jobs, security records and payload-free project
configuration/research events are not mechanically deleted because their names
contain “history”. Historical Git commits and released artifacts remain evidence.

The payload-free typed identity registry retains same-space database foreign-key
checks for claims and all annotation target kinds after old bodies disappear. Tombstones and unavailable
links contain no passage text. Project report/publication records may retain
identifiers/hashes as evidence of past operations; their referenced body can
expire. A saved report is not a new factual verification, and another publication
must validate current evidence again.


The explicit originals-directory audit is read-only and bounded. It checks retained
original hashes and reports unidentified generated UUID files, including legacy
crash staging. Such ambiguous files block preflight; reconcile their provenance
outside the managed application store before upgrade. The tool never deletes or
moves them, operator backups or unrelated entries. New writes create a durable
cleanup intent before using a version-bound temporary filename, so interrupted
future writes can be cleaned safely without guessing ownership.
