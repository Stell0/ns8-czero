# Personal Data ingestion

## Scope

An NS8-only switch, disabled by default, selects one NethVoice instance, one
WebTop instance, or both. No modifications or PRs to either product. No C0
production deployment. Provision one private **Personal Data** space per active
human directory identity, even before first C0 login. Bind by canonical provider
and AD objectGUID / LDAP entryUUID; names and email domains grant no authority.
WebTop must use C0's provider through its selected Mail instance.

The admitted owner has Editor content authority only in that personal space;
application role, persistent blocks and delegated scopes remain authoritative.
Admins retain access. Sharing and audience changes are forbidden. Renames retain
the space; username reuse cannot inherit it. Core retains observed directory aliases.
A name claimed by another immutable identity suspends ingestion with
`identity_ambiguous`; renaming again does not silently clear that ambiguity.
This does not prevent the new identity from using its own personal space.
After source reads, the native runner rechecks that the destination username
still resolves to the same active immutable directory ID before staging or removal. Directory disable/removal suspends
access and retires imports, retaining separately authored knowledge.

## Existing NethCTI API

Inspect persistent-token support before assuming a browser session is required.
Current source has user-issued tokens for a closed audience set; admin issuance
requires super-admin authority. C0 never copies existing super-admin tokens or
personal passwords. Without a verified usable per-user credential, report
**suspended / session unavailable**, retain imports and make no absence inference.
Do not create an audience or impersonate another integration to bypass policy.

Only participated conversations qualify, including for supervisors. Establish
current unique directory-to-profile/phone mapping and per-transcript participation;
ambiguous evidence is excluded, not guessed from a shared uniqueid or linkedid.
Use exact transcript row IDs for retrieval and identity, namespaced by source
instance, destination directory identity and document kind. Transcript and existing
summary are separate linked documents; cleaned text and summaries are derived.
The operator accepts the single variant returned by the existing API: cleaned
when available, otherwise raw. The API does not identify the chosen variant, so
record that uncertainty and do not claim to preserve both separately.
No generated summaries, Satellite vectors or PostgreSQL source access.

## Existing WebTop API

Read only the user's own mailbox; exclude Junk, Trash, Drafts and delegated/shared
mailboxes. Use set_seen=false and existing attachment reads. Never fetch remote
message images. Extract HTML safely; normal C0 extraction handles supported
attachments and reports unsupported, oversized and failed ones explicitly.

Date/page scans can shift under concurrent arrivals/deletions. Repeat scans and
report incomplete/backfill coverage honestly. Never assume folder+UID means
unchanged: verify message content and attachment hashes. Message-ID is metadata,
not a key. Detect UID reuse/content anomalies and rescan; no claimed UIDVALIDITY
guarantee. Missing items in incomplete, unstable or failed scans never authorize
deletion. Delay propagation until independently confirmed absence; retain data
during outages. Record the actual confirmation policy and scan bounds.

## Synchronization and secrets

Run bounded resumable batches every five minutes, with a complete inventory attempt
at least daily. Remote reads occur outside content transactions. Recheck provider,
config generation and destination ownership before every publication. One runner
lock per C0; payload-free receipts/checkpoints, no parallel body store.

Replace only last-receipt-matching local content. Local edits become overridden;
local deletion creates a persistent payload-free exclusion, retained across
disable/re-enable. Confirmed source deletion/access loss retires even overridden
imports and attachments, chunks, vectors and retained payloads. Authored Wiki text
remains and evidence becomes stale. Temporary/session errors are not access loss.

Disable immediately fences publications and queues resumable verified cleanup;
spaces/authored content/exclusions remain. Provider mismatch does the same for
the incompatible connection; never remap identities automatically. Back up
configuration, mappings, checkpoints and private dedicated credentials. Restore
requires source/provider revalidation before publication resumes.

Dedicated credentials may have broader upstream rights when existing APIs cannot
restrict them; C0 source adapters execute reads only (including documented POST
read endpoints). Provisioning/revocation is a separate explicit lifecycle step.
Never copy individual passwords or existing super-admin tokens. Secrets remain
mode 0600 outside environment/Redis/logs and HTTP/MCP responses.

## Acceptance

Verify never-logged-in/renamed/reused/disabled/blocked identities; own-space
browser/REST/MCP CRUD and denial of cross-user/global/sharing writes; OAuth/API
key scope ceilings; config/runtime provider matching; participants and supervisor
exclusion; shared-uniqueid transfers; persistent token/session expiry; shifting mail
pages, UID reuse, missing Message-ID, MIME and attachment limits/unread flags;
retry/restart/partial inventories; overrides/exclusions; disable races; payload
retirement and stale citations; backup/restore; Debian/Rocky native/privacy checks.
Record exact installed versions and probe outcomes separately from synthetic
fixture and source-inspection results.

## Candidate implementation and release gates

This candidate changes C0 only. Core producer 0.50 / schema0041 owns directory
spaces, effective authorization, generation fencing, import receipts, exclusions,
checkpoints and retirement. The released consumer lock remains on Core0.49 until
independent publication and consumer adoption have passed; this branch is explicit
producer development and is not a released consumer deployment.

The native settings provide compatible instance selection and sanitized per-user
coverage. `set-personal-data-credential` accepts a dedicated WebTop domain API key
or a per-user NethCTI token, stored privately by immutable directory identity.
It accepts no passwords. Saving is explicitly **unverified** until authorized
source reads succeed; clearing a local credential does not claim upstream revocation.
Summaries link to the recipient’s local transcript source ID when that copy is
available. Users not yet visited by the runner appear as unverified in coverage.
Do not pass credentials as shell arguments; submit private JSON on stdin. Backups
retain the private credential file and database state. Restore invalidates source
bindings before workers resume. Canonical private files retain module ownership;
per-invocation read-only copies are mapped to the existing image UID10001 and
removed before container teardown. Generated runtime snapshots contain identities and
selectors, never message bodies. A fixed private pipe asks the native helper to
recheck bindings after remote reads, before each staging/removal transaction.

Removal candidates require two complete matching inventories separated by at least
five minutes. They still require a current positive read control and an exact-item
404, or verified NethCTI per-record participation loss. Transient errors, failed
attachments and partial scans do not authorize removal. An entirely empty mailbox
with no current positive message-read control is retained conservatively.

The current bounded runner rotates at most five directory owners per pass and
uses five historical items plus a bounded refresh of five recent items.
WebTop rotates the recent refresh across eligible folders; NethCTI refreshes
the latest personal calls separately from the pinned historical window. A
completed old NethCTI window is backfill progress, not a current inventory. The status exposes overdue inventories instead of
claiming daily coverage. Reads remain bounded to32 requests and85 seconds
per source adapter,10 MiB per response and320 MiB aggregate raw responses. The
existing image runs with a1 GiB memory limit and a150-second native service
deadline; publication still uses the normal C0 extraction limits. Complete daily reconciliation at the target workload,
new-arrival throughput under load, supported attachment retry coverage,
and full upstream credential provisioning/revocation remain acceptance work.
NethCTI's served transcription variant is marked derived/variant-unverified, as
accepted by the operator. The inspected endpoint returns cleaned text with a raw
fallback; an individual record is still needed to verify the installed behavior.
Both variants are not claimed as separately preserved. Attachment failures are
persisted as payload-free observations, cleared after a successful retry, and
reported by category. Imported attachments include their parent C0 source ID.

Before readiness: finish those workflow limits, actual installed-version/token/
mailbox tests, browser workflows and full Debian/Rocky native/privacy acceptance;
then publish Core independently and adopt its immutable tag/lock in a separate
consumer candidate. No production deployment is authorized.

## Operator credential setup (candidate)

Select the compatible service in NS8 first. Create a new dedicated WebTop domain
API key through that product's supported administration interface, or obtain an
explicitly authorized usable NethCTI token for each directory user. Do not supply
a personal password or an existing provisioning/super-admin token. The source
products are unchanged; their broader credential permissions remain an upstream
limit even though this collector issues only reads.

Submit a private mode-0600 JSON file to
`api-cli run module/<module-id>/set-personal-data-credential --data -` on stdin. Required
fields are `connector`, selected immutable `instance_id` and `secret`; NethCTI
also requires the exact current `username`. Never put the secret in command
arguments, environment variables or a checked-in file. NS8 masks the `secret`
input in task context. Saving resolves the directory UUID and reports
`verified=false`; only subsequent successful bound source reads establish
coverage. No credential entry means suspended ingestion, not source removal.

To disconnect a credential, submit the same selector with `clear=true` and no
secret. For NethCTI, include a username to clear that current directory identity, or
omit it to clear all saved user credentials for the specified source instance.
Clearing an old disconnected source does not require it or its provider to be
reachable and never touches credentials saved for another instance. Local clearing reports
`revocation_pending=true`; revoke only the dedicated key/token through its
source product's supported interface and retain private confirmation. This
candidate does not claim unattended upstream creation or revocation. Switching
ingestion off fences and cleans imports independently of credential validity.

WebTop folder traversal uses a sorted folder inventory and persists its hash with
the checkpoint. Adding, removing or renaming an eligible folder invalidates that
scan's indices and restarts traversal with a fresh scan identity. A changed list
cannot make a previously interrupted traversal appear complete.

Confirmed removals target the exact document kind: loss of an existing summary
does not remove a still-available transcript. Available source timestamps are
preserved as provenance. Changes to provenance/title/type are reconciled even
when body bytes are unchanged, using normal source publication and retaining
local overrides. Native publication checks also reject an in-flight credential
copy after its canonical credential has been cleared or rotated; disconnection
intent is persisted before the Core generation fence.

A runtime mismatch is scoped to the verified incompatible connector and instance.
Other connections' imported content remains intact. Unknown/unscoped discovery
errors fence publication without inferring removal. An authoritative change of
C0's directory binding suspends the old identities and retires their imports.
Mismatch fencing/cleanup does not depend on successful directory reads or access
to the connector credential file.
