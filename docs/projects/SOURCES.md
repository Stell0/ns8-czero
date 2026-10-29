# Project sources

The independently installable `samples/ingestion` package now supplies
`c0-projects` alongside `c0-ingest`. Collection (`c0_projects.adapters`) returns
bounded original-content items; publication (`c0_projects.publish`) uses the
existing OAuth client, text ingestion, multipart REST upload and source services.
Neither fetches URLs in the C0 server nor executes document instructions.

## Configuration and authorization

Use strict TOML, JSON or YAML. All definitions validate before network I/O.
YAML uses a bounded SafeLoader without aliases, duplicate/non-string keys,
custom tags or non-JSON values. Dates remain strings. Configuration is bounded
at64 KiB/10000 nodes/depth20; no executable constructors are accepted.
An existing protected project space must be initialized separately. The existing
private-job initializer creates only local files:

```sh
uv pip install ./samples/ingestion
c0-ingest init /private/path/project-job
# Edit its private .env with the approved instance/client/account/space binding.
# Save the configuration below as config/project.toml.
c0-projects sources validate --config /private/path/project-job/config/project.toml
c0-projects auth login --config /private/path/project-job/config/project.toml
c0-projects auth bind-account --config /private/path/project-job/config/project.toml
c0-projects sources bootstrap --config /private/path/project-job/config/project.toml --apply --authorization-ref USER_APPROVAL_REFERENCE
c0-projects sources scan --config /private/path/project-job/config/project.toml
c0-projects sources sync --config /private/path/project-job/config/project.toml --dry-run
c0-projects sources sync --config /private/path/project-job/config/project.toml --apply
c0-projects sources status --config /private/path/project-job/config/project.toml
c0-projects sources verify --config /private/path/project-job/config/project.toml
c0-projects sources resume --config /private/path/project-job/config/project.toml --apply
```

Bootstrap requires Admin and records the exact definition hash/config history.
The routine job's read/write connection cannot approve its own sources. Use the
existing authorized setup interfaces or a separately approved setup connection
whose allowed/consented scopes explicitly include `c0:admin` and whose current
account has Admin authority. If using that connection in a private setup job,
set `C0_SCOPES="c0:read c0:write c0:admin"` before explicit login/consent. This
configuration grants no authority itself. Keep routine workers on read/write;
the client's bootstrap flag never adds roles, grants or scopes.
Ordinary synchronization needs existing read/write consent and current Editor
space membership. Login is explicit; expiry, revocation, wrong identity or space
fail without falling back to Shared. Tokens use the existing private OAuth
credential store and are never stored in connector definitions or receipts.
Unattended authentication remains a separately observed external capability.
Revoking source-space access blocks future refreshes; already authorized copies
retain their immutable evidence inside the separately protected target space.
Scan fetches and saves a private local snapshot, without C0 writes. Dry-run may
fetch/read but writes no C0 state. Resume publishes the exact saved scan without
fetching content again; private GitHub replay also rechecks current consent and
access. Verify only checks an already saved receipt and evidence.

```toml
schema_version = 1
server_url = "https://c0.example.org/mcp"
project_space_id = "00000000-0000-4000-8000-000000000001"

[[sources]]
id = "selected-documents"
adapter = "local_files"
root = "inputs"
paths = ["documentation"]
include = ["*.md", "*.pdf", "*.docx"]

[[sources]]
id = "public-repository"
adapter = "github"
repository = "synthetic/example"
include = ["readme", "docs", "commits", "releases", "issues", "pull_requests", "comments"]
max_items = 100
max_requests = 40
max_pages = 5

[[sources]]
id = "selected-news"
adapter = "rss_atom"
url = "https://example.org/feed.xml"
```

## Adapters and bounds

| Adapter | Selection and identity | Coverage |
|---|---|---|
| local_files | Explicit root/paths, recursive extension/include selection; relative path identity | Text/Markdown and PDF/DOCX; bounded inventory, durable item offset |
| http | Explicit public URL, same-host canonical link | Inert HTML text or supported original document; one page |
| rss_atom | Feed GUID/Atom ID; original publication/update timestamps | Same-host linked original pages; bounded feed, explicit partial status |
| sitemap | Selected path prefixes, same-host sitemap indexes and pages | Bounded recursion/pages; incomplete inventory remains partial |
| github | Public repository numeric ID plus object ID/blob path | README, recursive docs, commits, releases, issues, PRs, issue/review comments; durable stream/page/index cursor |
| c0_space | Explicit separately authorized source UUID and authorization_ref; immutable page/version identity | Selected wiki/sources snapshot with feed boundary and resumable offsets; source access rechecked on reads |
| wikiplant_export | Offline raw snapshot INSTANCE.json plus selected data paths | Legacy instance/path identity; no real import or live Drive access |

Defaults: 100 items, 40 requests, 8 MiB/item, five inventory/pages, depth two,
15 seconds/request. Hard maxima: 1000 items, 500 requests, 16 MiB/item, 20 pages,
depth four, 30 seconds/request. A collected connector batch is at most32 MiB;
a saved scan is at most64 MiB. XML is at most2 MiB and rejects DTD/entities.
Local inventories are bounded at10000 entries; publication inventory lookups
at10000 records. Limit hits are explicit partial coverage, never silent success.
Raising an authorized bound or narrowing a selection may be necessary for a
large inventory; this is not an unrestricted website crawler. Feed/sitemap
polls retain a hash-bound inventory offset for partial recovery and rescan the
selection after completion; stored hashes suppress duplicate versions.

Public fetches reject non-global DNS answers, pin the verified public peer,
verify TLS/SNI, ignore proxy credentials, restrict ports and disallow cross-host
redirects or HTTPS downgrade. Credentials/query secrets are forbidden. Local
reads use no-follow directory/file descriptors; symlinks/traversal, credential
filenames and unsupported files reject. GitHub collection defaults to anonymous
public repositories and preserves original bodies while removing credential-like API fields.
A new adapter can return Item/Batch without changing the publisher.

## Persistence and recovery

Each original has a stable connector/external identity and SHA-256. New UTF-8
text/Markdown within2 MiB and one million characters uses a single source: text
MCP up to131072 bytes, otherwise existing multipart REST file upload. Existing
multipart layouts remain stable on retries. Larger originals are split on
paragraph boundaries when possible, at most131072 bytes/part with
explicit parent/hash/part/byte offsets; at most100 parts/original, with an
explicit limit error beyond that bound. No content is truncated. Binary uploads
retain the existing10 MiB server bound despite the larger collector byte ceiling. PDF/DOCX use
multipart REST and retained originals. Current source and current-generation
provenance retain original/canonical URLs and distinct retrieval/publication/
update times. An old article fetched today is not a new event.

Before publication, a private journal freezes intent. On lost replies the
publisher finds the original source and exact content hash before retrying.
The complete verified part set is published atomically as one current parent
snapshot with verified current-generation membership. Shrinking removes obsolete
parts, bodies, originals, chunks and vectors. Unchanged normalized bytes reuse
current identities; A → B → A creates fresh generation IDs. A previously applied
observation cannot roll back a newer publication. Queued extraction is pending;
private part verification checks full retained bodies/hashes, and citations become
available only after complete publication. No claims are created by ingestion.

Managed typed connector config/history, current source membership and connector
coverage records live in the protected space. Expected revisions reject racing
collectors. Connector updates must name the verified part receipt IDs. Core joins them
to actual ready, non-archived source versions and complete immutable parent
snapshots; reported counts alone cannot advance a cursor.
Only verified publication advances partial progress; only complete
verified collection advances the successful cursor/watermark. Failed extraction
or lost responses retain recoverable receipts. Bounded exponential retry starts
at30 seconds, caps atone hour, honors a bounded requested retry up toone day,
and resets after success. Latest-only replacement deletes superseded automatic
content; expired exact citations return `content_superseded` (410). Remote deletion
reconciliation is outside the website milestone.
Remote missing/denied/invalid pages, incomplete pagination and rate limits are
partial/blocked observations. Resume does not assert a source was searched or
fully audited merely because its existing content was already saved.

Local tests exercise synthetic adapters and actual signed HTTP/OAuth/SDK/Core/
PostgreSQL text/PDF publication, uncertain-response reconciliation, expired-version
retention, pending extraction and cursor conflicts. No private instance or live
WikiPlant data has been synchronized by this implementation task.

Publication now uses [fenced source-sync runs](WORKFLOWS.md#source-synchronization)
while retaining the private job lock and normal source/version APIs. Scan, dry-run,
status and verification remain read-only with respect to C0 workflow state.

## Explicit private GitHub collection

Private repositories require a separate local0600 JSON/YAML authorization file
and `--private-github-authorization FILE` on each collection/replay. It contains
schema_version1, project_space_id, an exact repositories list and an attributed
authorization_ref. It contains no credentials. The selected repository must also
be explicitly approved in the destination project connector definition.

The worker reuses GITHUB_TOKEN/GH_TOKEN or the existing gh authentication helper;
there is no new C0 authentication mechanism. Requests bind the exact repository
namespace on api.github.com, deny redirects/cross-repository paths and require
fresh repository metadata authorization before cached content. Private logs
omit repository paths and tokens; provenance retains actual repository identity,
visibility and authorization reference. Frozen replay requires current local
consent and a fresh matching numeric repository ID/access check before any C0
publication/run mutation. Removed consent, expired authentication or revoked
access blocks replay. Previously authorized immutable evidence stays protected
in its destination. Public-only behavior remains the default.

## Typed C0-space subscriptions

`c0_space.include` accepts `wiki`, `sources` and explicitly selected
`objects:<registered-type-name>`. Schema and record revisions are preserved as
source content/provenance. Knowledge and object change cursors remain separate;
bounded partial inventories resume without treating an incomplete scan as a
successful cursor. The worker selects the source with its own current Read
authorization on every refresh. Destination approval does not grant source
access. No graph traversal or implicit cross-space permission is introduced.
Tests include a third protected space containing synthetic GitHub knowledge,
incremental object revisions and revoked source grants.

See [export/preparation contracts](EXPORTS.md) and the fabricated reference
configurations for offline fixtures. No production source was imported.

Readers and agents can open the complete logical original through
`source_documents_get`/`source_version_document_get`, including historical
multifile storage. Discovery shows verified parents once and excludes unpublished
parts. Logical reconstruction uses immutable documents/receipts and verifies the
full parent hash; search chunks are never concatenated. See
[full-document contracts](../full-documents.md).

The reusable [website recipe and catalog](../../samples/ingestion/examples/website/README.md) documents approved roots, robots/sitemap boundaries, structured Markdown, private resumable state, periodic one-shot commands and partial-coverage reporting. See the [destructive upgrade/preflight](../latest-only-migration.md) before a separately authorized production upgrade.
