# Knowledge maintenance

## Selected text evidence

Use `sources_ingest_text` only for selected sanitized UTF-8 plain text or Markdown, at most 131072 bytes. Retain provenance and the unchanged-request idempotency key. Poll the returned version with a bounded wait; queued/running is not ready. When ready, read its document, chunks and exact citations before recording findings.

Binary files use multipart REST upload or C0 Source tools, not an MCP upload operation. Explain that boundary if the current client cannot upload. Do not claim a file was ingested because its text was mentioned in chat.

## Revision-safe updates

Search for an existing page and resolve its exact fixed slug in the selected space. `wiki_pages_upsert` without `expected_revision` is create-only; an update includes the current revision. Preserve citations and conflicting observations. Existing slugs cannot be renamed.

On conflict, reload and reconcile both changes. A changed request uses its new expected revision and a new retry key. An unchanged uncertain retry keeps its original key and returns the original receipt. Read back the saved page and immutable history before reporting success.

## Consolidation

Use `knowledge_bundle_apply` only for an explicitly requested group of related changes in one space: 1–25 supported mutations with current expected revisions and one retry receipt. Its space selector is inside `data`. It performs no extraction, jobs, provider calls, schema registration or grants. Failed steps roll back together; an unchanged retry returns the original whole receipt.

Applicability and verification are separate annotations on an exact content revision. Missing metadata means unknown; changed content does not inherit verification. Annotation revision zero creates only. Preserve original citations, contradictions and superseded typed revisions rather than erasing history. Do not mark a claim verified merely because a write succeeded.
