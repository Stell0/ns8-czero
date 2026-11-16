# Knowledge maintenance

## Selected text evidence

Use `sources_ingest_text` only for selected sanitized UTF-8 plain text or Markdown, at most 131072 bytes. Retain provenance and the unchanged-request idempotency key. Poll the returned version with a bounded wait; queued/running is not ready. When ready, read its document, chunks and exact citations before recording findings.

Binary files use multipart REST upload or C0 Source tools, not an MCP upload operation. Explain that boundary if the current client cannot upload. Do not claim a file was ingested because its text was mentioned in chat.

## Revision-safe updates

Search for an existing page and resolve its exact fixed slug in the selected space. `wiki_pages_upsert` without `expected_revision` is create-only; an update includes the current revision. Preserve citations and conflicting observations. Existing slugs cannot be renamed.

On conflict, reload and reconcile both changes. A changed request uses its new expected revision and a new retry key. An unchanged uncertain retry keeps its original key and reconciles current state. A superseded request returns `content_superseded` (410); read current state, reconcile and use a new key with the current revision. Read back the saved current page before reporting success.

## Consolidation

Use `knowledge_bundle_apply` only for an explicitly requested group of related changes in one space: 1–25 supported mutations with current expected revisions and one retry receipt. Its space selector is inside `data`. It performs no extraction, jobs, provider calls, schema registration or grants. Failed steps roll back together; an unchanged retry returns the original whole receipt.

Applicability and verification are separate annotations on an exact content revision. Missing metadata means unknown; changed content does not inherit verification. Annotation revision zero creates only. Preserve exact citation identities, authored contradictions and quotations; superseded automatic content is deleted and its evidence explicitly becomes unavailable/stale. Do not mark a claim verified merely because a write succeeded.


## Automatic public-source updates

When the connected catalogue exposes `automatic_sources_list`, discover the exact
selected space and inspect existing definitions before proposing an update.
Users can configure public GitHub repositories or websites through native source
controls or these tools. `automatic_sources_preview` fetches a bounded sample
without saving source content. `automatic_sources_save` replaces the whole
configuration and requires a replay key plus expected revision for edits.
Setting enabled=true is explicit background authorization: do so only when the
user requests automatic updates for that selection/space. Use
`automatic_sources_command` to run now, pause or remove configuration; removal
retains documents. Inspect `automatic_source_runs_list` and read the current
complete documents before reporting success. Partial/queued work is incomplete.
Missing operations mean the installed server has not adopted this capability;
keep using the existing ingestion workflow, without installing another schedule.
