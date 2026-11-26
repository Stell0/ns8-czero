# Automatic sources

Automatic sources update a selected C0 space from public GitHub repositories, websites and folders owned by a connected Google account.
A definition selects remote content; collected documents use existing C0 sources,
extraction, latest-only publication and indexing. No model executes in the worker.

App 0.70 uses the published Core 0.52.0 Git release and schema 0045. The
forward migrations add private Google connection and folder records and raise
the size limit for PDF originals. Existing GitHub and website definitions keep
their space, schedule and document identities.

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

## Collect PDF attachments from a public website

Choose **Website** and enter the HTML listing URLs and HTML roots. Under
**PDF attachments**, select **Collect PDF attachments** and enter the HTTPS
prefixes where the publisher stores files. Selecting attachments retains the
official original PDF for each completed source. Existing definitions retain
their HTML behavior until an Editor selects attachments and saves the change.

This example follows HTML under `/notices` and accepts PDF links under the
independently approved `/files` prefix.

```json
{
  "website": {
    "seeds": ["https://publisher.example.org/notices"],
    "allowed_roots": ["https://publisher.example.org/notices"]
  },
  "attachments": {
    "allowed_roots": ["https://publisher.example.org/files"],
    "seeds": [],
    "include": ["/files/*.pdf"],
    "media_types": ["application/pdf"],
    "max_depth": 10,
    "page_queue": false
  }
}
```

PDF links are recognized by their path suffix. An explicit attachment filter
can select an extensionless download, and an extra PDF starting URL can select
a file directly. Attachment filters also constrain redirect destinations. Use
the narrowest eligible HTTPS prefix on each publisher or file host.

Preview shows a bounded sample with selected or skipped PDF links. It checks
public transport, robots, media type and file signature. A selected preview
item still needs full extraction and publication. Preview only inspects the
selection. Run **Update now**, inspect **Recent runs**, and
open the completed documents. An HTML listing without an extractable article
can still supply approved PDF links. The run records the HTML failure and
publishes any complete attachments. A partial run records unresolved reasons. A
completed run covers the recorded frontier under the saved definition. Coverage
depends on what the publisher exposes through the selected website paths.

Collection is serial. Each batch uses the existing website limits of up to
20 items, 30 HTTP requests, three redirects per request and 2 MiB per file.
Batch downloads also obey the configured website byte budget and a 20-second
collection deadline. HTML link depth defaults to 10 and can be set from 0 to
20 for attachment-enabled definitions. Eligible links remaining after a batch
cap persist in a checkpoint. Frontier and depth limits report incomplete
coverage. The existing PDF parser and page count limits apply. HTTPS peers are
validated and pinned, and redirect and robots decisions are rechecked.

Repeated links and identical content preserve the logical document and its
current citation. C0 can use a strong ETag at the original HTTPS URL after
verifying the current local original. It downloads and checks bytes when the
origin has no suitable validator or the retained original is unavailable.
A changed PDF replaces the current publication only after
complete extraction and indexing. A failed replacement leaves the last complete
original and its citations available. An identical verified download can repair
a missing retained original without advancing its generation. Remote removal
does not archive a saved source.

Encrypted, unsupported, or textless pages report an unresolved result. **Use
page extraction** opts this definition into the instance’s existing enabled page
queue. Local OCR is available only when the instance already enables it. It uses
the existing page provenance and extraction limits. A PDF with omitted textless
pages is not published as complete. Pause, edit and revocation fence staged work.

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
the place to remove those copies. If the parser runs out of time or is unavailable,
C0 continues through the folder, reports partial coverage and retries on the next update.

Saving paused keeps a configuration for later. To collect while signed out,
explicitly allow Google background access and enable updates. Manual frequency
supports **Update now** without scheduling subsequent runs. Each Google connection
belongs to one C0 account in one space. Replacing the connection pauses its sources
until the owner previews and saves again. Changes to the space’s access policy or explicit grants
also require a fresh preview. In a restricted space, C0 pauses imports when the set of people
who can read changes. This includes unblocking a person with a retained grant and admitting
a new instance Admin. The configured instance owner always has access. For Shared and spaces
readable by all, the approval includes people who gain C0 access later.
Other Editors can pause/remove a source.
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
