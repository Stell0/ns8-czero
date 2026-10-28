# C0 Core

Reusable Python services for C0 applications, independent of the NethServer
agent SDK and the FastAPI transport. This package owns the PostgreSQL schema,
shared application operations and trusted deterministic worker.

One database retains its original shared knowledge space and supports protected
spaces with explicit Reader/Editor grants capped by current application roles.
Application Admins can access every space under actual delegated OAuth scopes.
Object-type definitions remain shared across the instance. Services implement
persisted Reader/Editor/Admin membership, browser/OIDC sessions, objects and typed relations,
immutable document evidence/citations, authored Wiki/claims/graph, text and optional
semantic retrieval, deterministic jobs and bounded external-client grants.
The application supplies trusted adapters, authenticated actors and HTTP/MCP
transport. Requests never select Python imports, arbitrary SQL or shell commands.

See the repository [README](https://github.com/Stell0/ns8-czero/blob/main/README.md)
for supported interfaces, limits and tested versions. Native module lifecycle,
container management, route configuration and backups remain in numbered NS8
scripts outside this package. Optional providers do not determine authorization;
text search remains independent of inference. Generative operations stay outside
the runtime.

## Optional verified-user admission and client onboarding

Version0.31.1 adds `AccessService(..., admit_readers=True)` for applications that admit new verified users as Readers. The default remains closed admission for existing consumers. An explicit `set_role(..., None)` persists a block, so repeated sign-in cannot readmit a revoked user. Migration0019 preserves existing accounts without membership as blocked; owner identity and existing explicit roles remain authoritative. An application Admin must explicitly grant an old blocked identity access. Protected-space grants and delegated scopes are unchanged.

`ClientOnboardingService` stages a valid public metadata-URL authorization request for at most five minutes. Separate opaque browser/request bindings, issuer/native/resource/policy revision checks, count limits and current verified sessions protect the handoff. It never fetches metadata or approves a client. Only signed-in, CSRF-protected requests appear in the Admin queue. Trusted adapters use the ordinary reviewed CIMD flow, then atomically consume the handoff into ordinary consent with explicitly selected requested/approved scopes. State and PKCE values remain private; role changes, policy changes, expiry and replay fail closed. This is independent of HTTP/UI and preserves legacy approved-client behavior.

## Explicit background connections (0.32)

`NativeAuthorityService(..., connection_policy=ConnectionPolicy())` opts into
provider-attested offline authority with a thirty-day inactivity window and no
fixed maximum lifetime. The default remains bounded interactive authority.
New grants need explicit `persistent=True` consent and a same-account offline
sign-in; existing grants keep their original deadlines. Browser cookies retain
their configured idle and maximum lifetimes independently of offline activity.
Browser logout revokes bounded grants while
preserving explicitly consented background grants; connection disconnect and
current client/account revocation still deny delegated operations.

`SessionService.begin_login(background=True, session=verified_session)` binds a
five-minute, one-use login to the verified account. The OIDC adapter requests and
requires `offline_access` and verifies the same immutable identity on return and
renewal. Ordinary login never requests offline access. Pending consent can be
prepared for that round trip without extending expiry or enlarging scopes.

Persistent access tokens still expire within five minutes. Refresh credentials
rotate; a keyed family/generation authenticator detects reuse of any issued old
generation while retaining only the current refresh hash. The opaque token
contains a 96-bit random family locator, a 32-bit generation and a 128-bit
domain-separated HMAC; client/resource/native identity bind its authentication.
Fabricated, future and wrong-client credentials confer no authority and cannot
revoke another family. Counter exhaustion fails closed. Existing random tokens
and bounded replay-history behavior remain supported. Signing/encryption keys
derive from the native client secret, outside database backups.

Provider support, application transport/consent, migrations, independent
artifacts, both native distributions and actual multi-day ChatGPT use each
require verification. See the repository PLAN for executed release/acceptance
evidence; the library contract alone does not establish application readiness.

## Building and verifying

From the repository root:

```sh
uv build --no-sources packages/czero-core --out-dir /tmp/czero-core-dist
python -m pytest tests/packaging
```

Packaging checks install both wheel and source archive into separate clean
environments outside the checkout and exercise imports, metadata and migrations. PostgreSQL/pgvector
checks require an isolated `CZERO_TEST_DATABASE_URL`; never point tests at live data.
Only Core is installed: the NS8 SDK and reference FastAPI application are separate.

Application code can import `czero_core.core_health` and construct the domain
services against `czero_core.Database`. Database-backed operations require the
packaged schema: set `CZERO_DATABASE_URL` privately and run
`python -m czero_core.migrate` before serving requests. Repeated migration preserves
the knowledge-space identity. Never place a database URL or identity/provider
secret in source code or application logs.

Version `0.28.0` is independently published as `core-v0.28.0` from verified
source `48ac409`, adding forward migration `0016_annotations`, separate exact-content
applicability/verification histories and opt-in structured retrieval. Exact-source
local, producer/released-Core, Debian genuine upgrade and Rocky installation gates
pass, including all eight browser workflows and audited native/privacy artifacts.
Published wheel/archive checksums, independent installations, reproducibility and
repeated migrations pass. The reference app 0.43 adopts that immutable Git source;
its deployment acceptance remains a separate gate in PLAN.md.

Trusted callers use `SpaceService` for discovery, creation and revisioned grant
management. Content services select a space with `service.in_space(space_id)`;
this returns a separate service copy and never mutates shared request state.
Omitting selection always uses the original shared UUID. Invalid or unauthorized
selectors fail; direct resource UUIDs never select or authorize another space.
Core checks current membership, selected-space grants and actual bound OAuth
authority inside service transactions, including receipt replay and after waits
or optional provider calls. Revocation/regrant cannot revive captured tokens.

Existing shared mutation fingerprints, response shapes and receipt snapshots are
preserved. Protected receipts and uniqueness are space-bound. Re-read current
content before revisioned writes; replay returns the original result. Immutable
source citations retain their identities and exact evidence. Space-qualified
transport references are an application responsibility; registered trusted
reference resolvers must honor the canonical caller space. Workers derive
ownership from stored parents. Optional retrieval filters candidates, counts and
provider input by space and falls back to exact vector distance when a filtered
approximate scan underfills. Configuration does not establish provider quality.

Licensed GPL-3.0-or-later; the complete license is included in both distributions.

## Core artifact publication

`.github/workflows/publish-core.yml` handles `core-v<package-version>` tags,
independently of NS8 module releases. It checks the exact checkout/source,
successful local CI and both native distributions before building artifacts.
The exact wheel/source archive is tested, including packaged PostgreSQL
migrations, before a separate narrowly scoped job creates a draft release,
checks its uploaded hashes and publishes it without replacing the module's
latest release. Replays must match existing artifact bytes; published files
are never clobbered.

The accepted M20 predecessor uses independently published Core 0.29.0:
https://github.com/Stell0/ns8-czero/releases/tag/core-v0.29.0.
Its accepted AM6 application source is `97a7a1b` (app 0.45/schema 0016).
Core 0.30 renewal and its application adoption have separate gates;
library publication does not establish deployment acceptance.
Consult PLAN.md for subsequent exact-source publication gates and actual
consumer/Renovate evidence; a started workflow does not establish acceptance.

Release builds also normalize generated source-archive ownership, timestamps,
permissions and gzip metadata with `scripts/normalize-core-sdist.py` and the
source commit's `SOURCE_DATE_EPOCH`. Wheel and normalized archive rebuild hashes
are checked; package contents are preserved. Setuptools source archives alone
retain build-host metadata, so raw uv sdist output is not a replayable release
artifact. This development helper stays outside the installed Core package.
Build the final wheel from the normalized archive under umask 022 to avoid
checkout group-write modes changing ZIP metadata. Its bytes reproduce the
published wheel across build hosts.

## Independent installation

Use a Python 3.12–3.14 virtual environment and the verified release assets, or
the immutable Git tag/subdirectory source:

```sh
uv pip install "czero-core @ git+https://github.com/Stell0/ns8-czero.git@core-v0.29.0#subdirectory=packages/czero-core"
```

For that released generation, declare the compatible range `>=0.29.0,<0.30.0` and the
reviewed Git tag in `[tool.uv.sources]`, then commit uv.lock. Never replace the
released source with a local checkout implicitly. The template producer can
opt in with `CZERO_CORE_SOURCE=local`; this affects only its build environment.
Minor/breaking releases require separate compatibility and migration review.


## Text evidence submission (0.25.0)

`SourceService.ingest_text(actor, idempotency_key=..., title=..., body=...,
media_type="text/plain", metadata={})` adds UTF-8 text through the existing
immutable source-version, extraction-job and original-cleanup pipeline. Plain
text and Markdown are accepted, up to 131072 UTF-8 bytes; empty/whitespace-only,
NUL and malformed Unicode are rejected. Titles use the existing 256-character
bound and metadata the existing 16 KiB JSON bound. Keys are 1–128 ASCII letters,
digits, underscores, periods, colons or hyphens. Persisted Editor authorization
is checked inside the receipt transaction, including after waiting for its lock.

The result contains `source_id`, version `id`, `content_hash`, `job_id` and actual
state at submission. A same-actor/key replay returns that original receipt, even
after extraction finishes; poll `versions`, then use `document`, `chunks` and
`citation` to obtain immutable ready evidence. A changed payload under the same
key conflicts. This actor/key namespace is shared with Wiki/knowledge writes;
use distinct keys for separate operations. Content hashes also reuse identical
versions across distinct keys. Extraction and evidence claims retain their existing readiness checks.

To append an immutable version, supply `source_id` and `expected_revision`, plus
the existing source's exact title/metadata. Provenance is not silently changed.
Concurrent stale updates conflict; replay of the winning key remains safe.
Originals are handled by the existing storage/cleanup/backup pipeline. As with
file ingestion, uncertain database commit failures retain potentially committed
originals rather than deleting recoverable evidence.

This additive Core minor keeps schema `0013_oauth_consent` and existing service
contracts. The reference app's released dependency remains 0.24.2 during Core
publication preparation; the REST/MCP text operation will require released 0.25.0
in the subsequent application increment. No external provider or generative
operation is needed to store or extract text. Submit only selected, sanitized
session evidence; C0 does not redact it or execute instructions in its contents.


## Safe Wiki maintenance (0.26.0)

`WikiService.resolve_page(actor, slug, include_deleted=False)` returns the exact
existing page and current immutable content revision. Slugs retain the existing
lowercase ASCII grammar and 128-character bound; no fuzzy lookup, case folding or
implicit normalization occurs. Archived pages require explicit `include_deleted`.
Persisted Reader membership is checked on every lookup.

`WikiService.upsert_page(actor, slug, title, body, metadata={},
expected_revision=None, idempotency_key=...)` creates only when the revision is
omitted. An existing slug, including an archived page, conflicts. Supplying an
expected revision updates only that existing page: absent slugs raise
`KnowledgeNotFound`; stale or archived pages raise `KnowledgeConflict`. After a
conflict, resolve again, reconcile the observations outside C0 and submit the
new expected revision with a new key. C0 never decides how to merge prose.

The return shape matches the existing page API: `id`, `revision` and immutable
`content`, including `content_hash`. The body limit remains 131072 UTF-8 bytes,
metadata 16 KiB JSON and title 256 characters. Same-actor/key retries return the
original snapshot even after later edits or archive. A changed request or another
operation under that key conflicts. Fresh persisted Editor checks occur before
and after the existing receipt lock. Failed writes roll back page, revision,
event and receipt together. Existing create/update operations and fingerprints
are unchanged; no schema migration is needed.

`czero_core.knowledge.EvidenceNotReady` subclasses `KnowledgeConflict`. Claim
creation and evidence attachment require actual immutable chunks and verify the
parent source version is ready within the authorized transaction. Missing chunks
remain `KnowledgeNotFound`; archived ready evidence remains valid. This does not
relax sourced assertion requirements or introduce inference.

During publication preparation the reference app still pins released Core
0.25.0; its explicit local producer override alone uses the 0.26.0 candidate.
The released application increment follows verified immutable artifact publication.

## Content annotations (0.28.0)

`AnnotationService(database, access)` uses the same immutable `in_space` selector
as content services. `ContentTarget(kind, id, revision)` identifies an exact
`source_version`, `wiki_revision`, `entity`, `object` or `claim`. Source/Wiki IDs
are their immutable version/revision UUIDs; `revision` is their stored number.
Other kinds use the record UUID and observed revision. Reads return a typed
reference with its parent resource, content hash and space.

`get(actor, target, namespace)` and `history(...)` read `applicability` and
`verification` separately. Missing metadata has annotation revision zero,
`value=None` and status `unknown`; it does not create a row. `update(actor,
target, namespace, value, expected_revision=..., idempotency_key=...)` requires
an explicit annotation revision, with zero for create-only. Each successful
update creates an immutable history entry and commit-ordered metadata event in
the existing receipt transaction. Independent writers have one winner; retry
returns the original successful snapshot after fresh authorization.

Applicability values support literal `products`, `components`, `version_tags`,
`status`, `observed_at`, `confidence` and bounded `extensions`. Verification has
its own `status`, `observed_at`, `verified_at`, `confidence` and `extensions`.
Times require an offset and normalize to UTC. Tags are exact strings, not version
ranges or prefixes. Status strings remain literal, including unknown future
values. Missing fields remain unknown; no inference adds verification. Values
retain the existing sixteen-KiB JSON budget. Ready extraction is required before
marking a source version verified.

Changing a mutable entity/object/claim makes an old observed revision stale for
new writes. Existing annotations remain readable at their exact old target;
new content has no inherited verification. Historical immutable source/Wiki
targets remain explicit. Object removal retains its annotation anchor and
history through the established same-space retained-reference pattern. Reads
report whether the target is still current or archived. Annotation writes never
change strict object data or retained evidence/Wiki provenance. This API is released in Core 0.28.0; application deployment acceptance remains
a separate AM4 gate in PLAN.

## Structured retrieval (0.28.0)

`StructuredSearchService(database, access, **retrieval_options)` reuses existing
provider configuration and immutable `in_space` selection. `search(actor, query,
filters=StructuredFilters(...), limit=20, mode='auto', rerank=None)` is opt-in;
`SearchService` keeps its existing signature, default behavior and result shape.
Omitted categories select source and current Wiki evidence. Explicit categories
also include entity, object and claim, retrieved through deterministic PostgreSQL
text queries (including entity aliases). Structured records never enter optional
embedding or relevance-scoring requests.

`StructuredFilters` accepts `categories`, `products`, `components`, `version_tags`,
`statuses` (applicability), `verification_statuses`, `archive` (`active`, `archived`
or `all`), and inclusive `created_from/to`, `observed_from/to` and `verified_from/to`
intervals. Times require a timezone and normalize to UTC; observation time comes
from applicability and verification time from verification. Lists must be
nonempty when supplied. Fields combine with AND, values within a field with OR;
tags match exact literal strings. `8.4` does not match `8.40` or a version range.
Unannotated content remains unknown and matches an explicit `unknown` status.

Space, archive and applicability eligibility precede candidate limits, counts,
text ranking, vector pruning and provider inputs. Filtered semantic readiness uses
the same predicate; underfilled ANN results use a filtered exact-distance fallback.
The existing provider-unavailable text fallback and post-provider authority
rechecks apply. Optional providers process only selected source/Wiki evidence;
each hit reports its actual retrieval method, and mixed results retain the
`structured_text` distinction. No provider configuration is selected by a request.

Results carry typed `reference` fields (`kind`, `id`, observed `revision`,
`space_id`, `resource_id`) plus independent applicability/verification revision,
status and value summaries. Source hits retain immutable chunk citations; Wiki
hits retain immutable revision references. Mutable entity/object/claim references
are observations, not immutable evidence citations. Claim `evidence_refs` contain
bounded immutable chunk/version/hash identities that clients resolve separately.
Editing content never carries verification from its old revision. Current search
excludes archived content by default; historical annotations remain explicitly
readable through the annotation API.

## Atomic consolidation (0.29.0)

`KnowledgeBundleService(database, access).in_space(space_id).apply(actor,
operations, idempotency_key=...)` publishes one to twenty-five content mutations
in one transaction. Omitting selection uses the original Shared space. The whole
operations array has the existing 256-KiB JSON bound, sixteen-level/4096-node
complexity limit and ordinary per-resource bounds. Failed writes leave no
partial records, revisions, metadata events, cursors or retry receipt.

Each step is `{"operation":"wiki.upsert","arguments":{...}}`. The fixed
operation set is `wiki.upsert/archive`, `entity.create/update/archive/alias/link/
unlink`, `claim.create/update/archive`, `relation.create/update`,
`object.create/update/delete` and `annotation.update`. Arguments use the existing
service method names; object mutations use `object_id` and optional `tags`.
Annotation targets are `{kind,id,revision}` dictionaries. Claim time arguments
are timezone-aware ISO strings. Existing expected revisions are required for
updates; Wiki upsert without one remains create-only. Ready evidence is required
for sourced claims, evidence references and source verification. No file
ingestion, external calls, jobs, schemas, grants or native operations are allowed.

An argument value `{"$result":0,"path":"id"}` references an earlier step's
typed result. Allowed paths are `id`, `revision`, `content.id` and
`content.number`; UUID/revision validation still applies to the receiving
argument. References can occur in nested targets/lists. Indices are zero-based;
forward/self references, unknown paths and absent fields fail. `$result` is
reserved within bundle arguments. A step cannot select another space or supply
its own idempotency key.

The result is `{space_id,results}`, ordered like the steps. One actor/space-bound
receipt covers the complete request. Lost-response retries return its original
snapshot, even after subsequent edits/archive; read again for current state.
Changed payloads under the same key conflict. Current persisted role, space grant
and actual OAuth authority are checked after lock waits and before old receipt
replay. Revocation cannot be reversed by regranting old tokens. Existing
individual mutation APIs/fingerprints remain unchanged; object-only batches
retain their existing behavior. Object and knowledge event mutexes use a fixed
order before authority locks, and domain helpers share the outer connection.

## Maintenance annotations (0.29.0)

Applicability additionally accepts literal `knowledge_type` (one to sixty-four
characters) and `supersedes`, up to thirty-two `{kind,id,revision}` exact-content
references. Both namespaces accept `source_references`, up to thirty-two
`{"kind":"chunk","id":"<immutable-chunk-uuid>"}` references. Resolve the
chunk citation separately for retained text/hash/location. References are
validated within the selected space; source chunks must belong to ready versions.
Supersession retains the earlier target's observed identity/hash, including an
unannotated object later removed through ordinary CRUD. It never archives prior
content, changes an assertion or moves verification to replacement content.
Self-supersession is invalid. Retained historical anchors remain explicitly
readable, without synthesizing an annotation or verified status.
Standalone supersession writes referencing objects acquire the object mutex
before the knowledge mutex, preventing row-order deadlocks with ordinary object
batches. Existing annotation requests retain their original lock path.

The complete contract therefore uses applicability `knowledge_type`, `status`,
`confidence`, `observed_at`, `products`, `components`, exact `version_tags`,
`supersedes`, `source_references` and `extensions`; verification independently
uses `status`, `confidence`, `observed_at`, `verified_at`, `source_references`
and `extensions`. Missing metadata means unknown. Future literal types/statuses,
explicit null confidence/times, contradictions and old histories are preserved.
The sixteen-KiB value bound, expected annotation revisions and old retry
fingerprints remain unchanged. Version 0.29 adds no migration: its schema is
`0016_annotations`. Its immutable publication and AM5/AM6 acceptance evidence are
recorded in the repository PLAN.


## Renewable authority (0.30)

Forward migration `0017_session_renewal` adds optional native-authority references
to browser sessions and delegated grants. Existing rows keep their exact fixed
expiry and receive no renewal rights. A trusted application can compose
`NativeAuthorityService`, `SessionService` and `OAuthGrantService` with the same
AccessService/native client. Only an authenticated `RenewalResult` from the trusted
OIDC exchange opts in. The default SessionPolicy is eight hours absolute and one
hour idle; integer bounds are 60–86400 seconds with idle <= absolute. Every new
authority snapshots its limits; increasing configuration never extends it.

Native credentials use authenticated, context-bound encryption derived from the
private native client secret. They never belong in public DTOs or logs. Provider
checks precede grant/content transactions. A durable checking marker and per-row
session advisory lock serialize native rotation across processes; an interrupted
check or ambiguous refresh response requires fresh sign-in. Definite transient
outage denies access without extending authority and may recover before its
existing idle/absolute deadline. OIDC checks preserve the original issuer,
subject, audience, authorized party and authentication time, and validate an
optional refreshed nonce and access-token hash.

Captured browser and delegated actors recheck persisted authority inside Core
transactions. Local cookie-bound CSRF logout revokes the session and its linked
grants without contacting the provider. OAuth refresh rotates, narrows scopes
durably and revokes the family on replay; access tokens are bounded by five
minutes and remaining idle authority. Unchanged update/restart can preserve
credentials; native client/secret replacement requires new authentication.

The reference application must explicitly enable these trusted adapters. Exact
release, released dependency adoption and application deployment evidence are
tracked separately in the repository PLAN.


## Provider refresh windows

Core 0.30.1 renews active native sessions before both access expiry and
any shorter provider refresh window. Provider token responses establish a
private encrypted renewal deadline, capped at five minutes and never extended
by introspection. Schema 0017 and existing absolute/idle bounds remain unchanged.
Old renewable credentials acquire this scheduling metadata through a real
serialized provider refresh; fixed legacy sessions gain no renewal authority.
Core 0.30.0 remains immutable; corrected 0.30.1 publication and renewed application
acceptance are pending. Provider configuration is unchanged.


## Optional approved client metadata

Core0.31.0/schema0018 adds default-off CIMD policy and Admin-approved exact public
client URL bindings while preserving manual UUID clients and their stored grants.
Core validates bounded metadata without HTTP or DNS dependencies; application
adapters perform safe fetching and supply short-lived trusted verification proofs
for new consent. Existing grants use approved local metadata through outages.
Relevant changes require explicit reapproval; global off, reapproval and client
disable revoke affected authority without reviving tokens when reenabled.
Publication and application acceptance remain pending in PLAN.md. The producer
application temporarily accepts both0.30.1 and0.31 while its released source/lock
remain pinned to0.30.1; final M19 adoption narrows the supported range to0.31.

The trusted `CimdPolicyService(database)` synchronizes installation policy even
when authentication is unavailable. It never needs a synthetic account or
provides administrator approval. `CimdService(access)` adds account-authorized
approval and consent verification on the same persisted policy.

## Workspace access administration (0.33.0)

`WorkspaceAccessService(grants)` composes existing access, onboarding, CIMD and
OAuth grant services for a first-party administrator. `overview(actor, limit=25,
offset=0)` returns safe account summaries, explicit block state, permission
revision and pending count. `applications(actor, account_id, limit=10, offset=0)`
returns exact request/connection summaries with `has_more`. Requested scopes,
consented scopes and current effective capabilities remain distinct. Manage
scope implies neither Read nor Write. These summaries do not contact providers
or extend authority; a stale provider proof is `renewal_required`.

`decline(actor, request_id)` cancels one five-minute onboarding handoff;
`disconnect(actor, grant_id)` removes one matching connection, waiting for
in-flight operations without revoking sibling native authority. Request-bound
`approve(...)` uses the existing CIMD transaction, rechecks the current user,
policy and request, preserves prior allowed scopes and rejects disabled clients.
It changes no membership and issues no credentials. All these methods require a
current first-party Admin; they are not newly exposed MCP operations.

`AccessService.set_role(..., expected_revision=n)` optionally rejects stale
edits with `AccessConflict`, including role changes followed by a return to the
same role. An unchanged revision-bound save does nothing. Legacy calls retain
their existing invalidation behavior. Real changes invalidate the target's
connections. Blocking remains explicit and persistent; the owner cannot be
blocked. Schema0021 adds only an account access revision and a separate random
request UUID; browser request secrets and all original authority remain intact.

## Protected research projects (0.34.0)

`ProjectService(database, access).in_space(space_id)` composes validated manifest,
topic governance, atomic queue/budget/run leasing, monitoring, evidence/results,
reporting, calendar and maintenance over existing protected typed/knowledge
storage. Managed immutable object schemas require trusted operations; ordinary
object writes cannot bypass policy. Current roles/scopes are checked inside the
transaction. Logical receipts and fenced state are separate from uncertain
external calls. Sources, Wiki revisions, claims and annotations reuse their
existing services. There is no generative runtime or arbitrary job handler.

`export_page(actor, kind, ...)` uses an explicit read-only catalog, current Reader
authority, scoped cursors, finite aggregate pages and immutable text fragments.
It includes actual project/knowledge identities and available histories, not
authority tables, server paths or unavailable historical payloads. Multi-request
export is change-detected, not a transaction snapshot or native backup. Client
collectors, YAML and legacy/static preparation are external integration code,
not Core dependencies. This additive version keeps database schema0021 and
existing knowledge, grant, OAuth, job and schedule contracts. Managed project
types are installed only through authorized project setup/configuration, with
immutable schemas and explicit history for compatible additions.

Project identity is the existing protected space UUID; Shared is never a project
fallback. Defaults are five ordinary/ten total daily attempts, urgent-only extra
slots, +20 causal expansion and three children. Primary monitoring has separate
positive finite caps and consumes no queue slots. Core verifies actual immutable
passages, exact claim/Wiki revisions and saved report membership; semantic truth
and all generative research remain external. IANA occurrence calculation and
runner observations do not install or verify an external scheduled task.

Release/default-consumer evidence lives in PLAN.md. The consumer manifest and
frozen lock select the actual immutable release; local producer builds require
the explicit development override. Never infer publication, deployment or
external-agent acceptance from package metadata. See the versioned repository's
docs/projects contracts for APIs, limits, recovery and migration preparation.

## Remembered website sessions (0.35)

Migration 0022 adds ordinary-by-default browser/login flags and five-minute
one-use first-party sign-in intents. Trusted applications validate Origin and
the browser binding before selecting `begin_login(remembered=True)`. The OIDC
adapter requests explicit offline consent and verifies its issuance and account
before `SessionService.create(..., remembered=True)` can store encrypted renewal
authority. Missing offline scope or refresh credentials fails remembered issuance.

A remembered browser has a fixed seven-day inactivity policy, independent of
ordinary session limits and background-connection consent. Call `get` before
protected work, then `renew_browser` only after a successful authenticated browser
response. That final transaction rechecks current membership, native authority
and the live cookie; it cannot revive expiry or logout. Send only the opaque
Secure/HttpOnly/SameSite cookie, renewing its seven-day expiry after success.
Ordinary browsers also retain their own idle deadline; migration snapshots the
existing deadline without extending it. Delegated traffic never renews browser
inactivity or calls `renew_browser`. Ordinary OAuth grants from a
remembered browser keep the configured finite session maximum. Persistent grants
still require separate explicit background consent and retain their independent
inactivity policy, including when that policy is shorter than seven days.
Existing browser sessions, grants and login states are never promoted.

After a successful authenticated sign-in, call `replace_browser` for the prior
cookie before issuing its replacement. This retires stale browser requests while
preserving already authorized client grants and their original finite/inactivity
bounds. Explicit logout retains its existing revocation behavior.
