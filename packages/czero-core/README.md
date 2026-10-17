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

Version `0.28.0` is the unpublished AM4 development candidate, adding packaged
forward migration `0016_annotations` for separate exact-content applicability and
verification histories. Core 0.27.0 is independently published and accepted at
`core-v0.27.0`; the reference app retains that immutable released dependency until
the new Core release sequence passes. PLAN.md records exact source, artifact,
native and dedicated-instance evidence. A candidate version or started workflow
does not establish publication or acceptance.

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

The last accepted runtime uses verified released Core 0.27.0:
https://github.com/Stell0/ns8-czero/releases/tag/core-v0.27.0.
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
uv pip install "czero-core @ git+https://github.com/Stell0/ns8-czero.git@core-v0.27.0#subdirectory=packages/czero-core"
```

For that released generation, declare the compatible range `>=0.27.0,<0.28.0` and the
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

## Content annotations (0.28.0 development)

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
change strict object data or retained evidence/Wiki provenance. This remains a
development API until the AM4 publication/deployment gates in PLAN pass.
