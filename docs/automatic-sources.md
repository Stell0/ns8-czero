# Automatic sources

Space-scoped native GitHub and website updates, with an optional personal Google Drive folder collector in the Core 0.52 producer candidate.
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

## Add a folder from your Google account

In the destination space, open **Sources → Automatic sources → Add automatic source**.
Choose a **Source type**. Each type keeps its own draft while the drawer is open.
Choose **Google Drive folder**, connect Google, then paste a link to a folder you
own in My Drive. Preview resolves the folder and suggests its name for the title.
The sample shows which direct children can be imported and why others are skipped.
A partial sample covers the items inspected. The C0 space audience will be able to
read published copies even when individual readers lack Google access.

The collector accepts PDFs up to 2,000 pages and 100 MiB (104,857,600 bytes).
It indexes the PDF text layer and preserves page numbers. When a PDF has both
text and image-only pages, the preview explains the omission and C0 keeps the
original for readers. A PDF with no extractable text is skipped. Document text,
parser memory and processing-time limits still apply.
Single-tab Google Docs (exported text), UTF-8 plain text and Markdown have a
2 MiB per-file limit. C0 skips shortcuts, subfolders, multi-tab Docs,
unsupported files and restricted downloads. It processes
two entries per page with durable continuation. Content is checked against the
file’s current parent, version and download permission before and after reading.
Renaming preserves a document's logical identity. Removal from Drive or a later
disconnect retains previously published C0 documents. C0 source management is
the place to remove those copies.

Saving paused keeps a configuration for later. To collect while signed out,
explicitly allow Google background access and enable updates. Manual frequency
supports **Update now** without scheduling subsequent runs. Each Google connection
belongs to one C0 account in one space. Replacing the connection pauses its sources
until the owner previews and saves again. Other Editors can pause/remove a source.
Disconnecting retires that connection in C0. Google Account's third-party access
controls can revoke the client grant across spaces. Reader-facing source metadata
contains an opaque C0 item identity. Google credentials and folder IDs stay private.

### Configure the instance

Use a Google Cloud OAuth **Web application** client for C0. Enable the Google
Drive and Google Docs APIs. Register the exact HTTPS redirect URI formed by
appending `/auth/google-drive/callback` to the instance's canonical base URL
(including any mount prefix). C0 requests only
`https://www.googleapis.com/auth/drive.readonly`. This gives the client permission
to read the account's Drive files. C0 applies the selected-folder boundary itself.
Google's `drive.file` scope covers individually opened/shared files and does not
document automatic access to all existing and future children of a pasted folder.
For external apps, review the Google publishing and verification requirements for
restricted scopes. Testing-mode grants can expire after seven days.
[Drive scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth) ·
[OAuth token expiration](https://developers.google.com/identity/protocols/oauth2#expiration)

In NS8, set the private, module-owned `state/google-drive.env` file to a single
line beginning with `CZERO_GOOGLE_DRIVE_CONFIG=` followed by a compact JSON
object containing `client_id`, `client_secret` and `encryption_key`.
Generate a dedicated 32-byte random key encoded in URL-safe Base64 (a Fernet key).
Use mode 0600. The file starts empty, which disables Drive. Restart the C0 app
after provisioning the file. The worker loads it on its next invocation.
Standalone operators can instead set `CZERO_GOOGLE_DRIVE_FILE` on both processes
to a regular, process-owned, mode-0600 JSON file with the same three fields.
Both processes need the same client, key, canonical origin and base path.

NS8 includes the private configuration in its module backup alongside the
database holding encrypted grants. Protect that backup as a credential. Restoring
the same instance requires the same key. Rotating the key or changing the
client or callback requires fresh Google consent. Restoring a predecessor with
no Drive configuration starts with the provider disabled. Credentials belong
outside Redis, Git, logs and support exports.

The browser routes require an active C0 session, current space Editor membership
and CSRF validation on changes. The callback checks a one-time session-bound state
and exchanges the authorization code with S256 PKCE. The current subject is Google's
opaque Drive permission ID, obtained with the granted access token. The preview
proof expires after ten minutes and binds the selection to the account, connection,
space and definition revision. REST bearer tokens and MCP cannot borrow a personal
Google connection. Public-source definitions retain their existing API contracts.

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
