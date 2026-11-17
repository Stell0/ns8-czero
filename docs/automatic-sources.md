# Automatic sources

Space-scoped native public GitHub and website updates.
A definition selects remote content; collected documents use existing C0 sources,
extraction, latest-only publication and indexing. No model executes in the worker.

Core 0.51 adds schema0042 after the immutable Core 0.50/schema0041 release.
Its published personal-space services and migrations remain intact; this feature
does not enable or install native personal-data collection. App 0.69 consumes the
immutable `core-v0.51.0` Git release and frozen lock,
with compatible range `>=0.51.0,<0.52.0` and matching patch-only updater bounds.

Readers inspect definitions and run status. Editors create, revise, pause, remove
and run definitions in their selected space with c0:write. Enabling a definition
explicitly creates a revocable background authorization for this selection and
space, attributed to its saving account. It is independent of browser logout and
limited to the saving account's current Editor access. Account or space grant
revision changes invalidate that authority; renewed authority requires a save.
Per-source credentials, private repositories and automatic organization discovery
are outside this first public-source implementation. Removing configuration retains documents.

An operator can mount an owned mode0600 credential file into the worker and set
`CZERO_GITHUB_TOKEN_FILE` to its path to avoid the shared anonymous GitHub API
quota. The token is used only for `https://api.github.com`, never websites or
cross-host redirects. Repositories must still be public. Neither the token nor
its path is a source setting; tokens never enter definitions or receipts. Store
credentials in a private file, never NS8 Redis configuration. CI supplies its
temporary read token through the same worker path for the real public import.

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
Enter each repository as `owner/repository_name`, one per line. An organization
name alone does not select all its repositories. **Text and code files** imports
each file matching the include/exclude patterns as a separate source document,
titled with its repository path and linked to the imported GitHub commit.
The branch/reference and file patterns apply only to files, not issues, pull
requests or releases. Empty file patterns in the form use `README*` and `docs/*`.
Preview lists a bounded sample of titles and links; after collection, open the
documents from the automatic source's details or Sources. Code is stored as text
and is never executed.

## Validation errors

App0.69.1 preserves the HTTP `detail` code and adds allowlisted `reason`, `message`
and `field` diagnostics. For an organization name entered as a repository:

```json
{
  "detail": "invalid_automatic_source",
  "reason": "invalid_github_repositories",
  "message": "Enter 1–100 distinct repositories as owner/repository_name. An organization name alone is not supported.",
  "field": "config.repositories"
}
```

The response remains HTTP422 with `Cache-Control: no-store`. MCP returns the
same diagnostics in an `isError` text result and `c0/error` metadata, including
the status. Unknown failures use a fixed generic correction; submitted values,
credentials and remote response bodies are never echoed. Role/space denials
remain denials. The form translates recognized reasons into English or Italian,
shows field corrections and names the failed action. No Core, schema, scope or
stored definition changes are required.

## Collection boundaries

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
