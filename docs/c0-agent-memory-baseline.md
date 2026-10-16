# C0 Agent Memory baseline (C0-AM0)

This records the unchanged starting contracts for the separate C0-AM0–AM6
implementation track. New memory APIs and protected spaces are not implemented
by this baseline. Historical milestones and Integration M17–M20 remain intact.

## Source and installation

Remote main is `90649de1609f9ad75d4010552d37a89c8f05d0c6`.
Its completed successful checks are [local](https://github.com/Stell0/ns8-czero/actions/runs/38960330953),
[publication](https://github.com/Stell0/ns8-czero/actions/runs/38960330948),
[released Core](https://github.com/Stell0/ns8-czero/actions/runs/38960332185) and
[native](https://github.com/Stell0/ns8-czero/actions/runs/38960603599).
These are predecessor checks, not results for the AM0 changes.

Anonymous OCI manifest/config inspection verifies these currently published main
images, all with revision `90649de1609f9ad75d4010552d37a89c8f05d0c6`:

| Image | Published main digest |
| --- | --- |
| `ghcr.io/stell0/czero` | `sha256:abcef4dfed11f29f717a7fc1f67ff10c1b0cfbae142ba409a9935e145efe8e2b` |
| `ghcr.io/stell0/czero-app` | `sha256:e8e2a0065b00d40f473af6baa3254321e3991a4b4b9e758029cde8ae406b6758` |
| `ghcr.io/stell0/czero-postgres` | `sha256:1cf7db7ceda4ac0e46fafa0c7e8ab0157a513e8bcfc6f5fb206ac3cc66ee7380` |

Read-only native inspection independently confirms that the accepted installed
runtime remains `95825682e00246556f7d0c7314859a6a69e0074b`. Do not deploy marker
images or substitute their digests for the genuine upgrade predecessor:

| Image | Actual installed digest |
| --- | --- |
| `ghcr.io/stell0/czero` | `sha256:3169e03be328ccd4079402aa0038d5b24e288bf03a52b70d0d6e21f8713db6bf` |
| `ghcr.io/stell0/czero-app` | `sha256:ef6e72dfdabcdbd9b7c78d1cb16993fb8192b17a015bc120acc4481537456157` |
| `ghcr.io/stell0/czero-postgres` | `sha256:6db4092d1a83854b82c8ba251bf3ddce527a054b06378d30a7ccc2102a9db8f4` |

Core/app/schema are `0.24.2 / 0.39.0 / 0013_oauth_consent`, with pgvector 0.8.7.
Native and normal trusted-HTTPS health confirm database readiness. Native
sign-in and enabled/active timer checks pass; the observed worker is healthy.
Embeddings are unconfigured and the optional scorer is off. Existing CPU-quota
and interactive-Playwright deferrals remain in force.

## Private preservation evidence

A read-only PostgreSQL custom-format dump is saved privately (131263 bytes).
Separate private hashes cover all 27 domain tables, retained source originals,
public/private settings and schedule configuration, with exact terminal-job and
attempt inventories (87 each at capture). The native inventory records existing
module identities and actual image revisions/digests. The capture does not pause
or change the running application; ordinary scheduler activity can continue.
A second read-only inventory confirms all 27 domain-table hashes, all 87
original terminal jobs/attempts and settings/originals/schedules are unchanged.
A bounded root journal filtered by verified module UID and app container has
301 lines with an actual health positive control, no OAuth query candidates and
no tracebacks. It is a baseline snapshot, not a completed native encrypted
backup/restore test.
A new native backup and fresh inventory are required before actual deployment.

Credentials, database rows, account/client/fixture identifiers, native node
connection details and raw inventories stay outside Git. No live investigation,
source, Wiki page, object, client or grant is created or changed by AM0. The
original checkout's three pre-existing document edits are preserved; this track
uses a separate checkout from verified current main.

## Existing contracts and reuse

Normal HTTPS OpenAPI and the current local app agree on all 63 operation
names/role/scope/read-only metadata. The local OpenAPI has 58 paths.
`tests/fixtures/agent_memory/legacy_contract.json` freezes names, authorization,
REST bindings and canonical input/output schema hashes. The hashes record the
starting schemas; later additive fields require compatibility review, not an
unconditional ban on extensions. Existing operations must remain callable.

- Sources already use generated original filenames, immutable content hashes and
  versions, source revision checks, deterministic extraction/cleanup jobs, full
  retained text/chunks and stable citations. Multipart upload is REST-only.
  Initial exact content/provenance retries deduplicate; there is no actor/key
  text-ingestion receipt yet. File/database commit uncertainty preserves originals.
- Wiki and knowledge mutations use actor/key fingerprinted receipts under
  advisory transaction lock 49376, optimistic revisions and ordered events.
  Slugs are fixed and unique; exact-slug lookup and upsert are absent. Conflicting
  sourced assertions coexist; annotation/retraction preserves their evidence.
- Objects use bounded immutable schemas, optimistic revisions, unique scalar
  keys, atomic batches and transaction lock 49375. Existing adapters preserve
  allowlisted object errors. Knowledge errors are still generic in MCP.
- All services recheck persisted application-wide membership. Delegated scope
  checks, current/legacy SDK wire handling, explicit OAuth scope-upgrade consent
  and current revocation guards must be retained. The database represents one
  shared space; no protected-space API or storage authorization exists yet.
- Search defaults to source chunks and current Wiki revisions. PostgreSQL text
  search needs no provider; optional semantic/reranking failures fall back.
  Structured filters/categories and protected derivative indexes are future work.
- The operation catalog binds trusted typed REST handlers to MCP. Keep business
  rules inside Core transactions and request-size/CSRF/Origin/Host protections in
  adapters. No agent executors, automatic reasoning or generative jobs are added.

## Disposable investigation fixtures

`tests/fixtures/agent_memory/investigation.json` describes synthetic investigation,
failed attempt, observation, procedure and verified lesson records. Its evidence
includes contrasting session observations, Unicode-capable text and an explicitly
untrusted document instruction. Metadata describes externally authored verification;
C0 does not infer or certify conclusions. Real agent submissions must already be
sanitized by the submitting agent; C0 must not log their bodies.

Every execution allocates a `c0-am-test-<random>` slug/title namespace and disposable
identity/database/files. Existing fixtures track exact created source/page/entity
IDs and remove dependent evidence, claims, revisions, receipts, events and jobs
before their disposable accounts. No global live prefix cleanup is allowed.

The baseline regression exercises existing immutable ingestion, ready evidence,
conflicting sourced claims, text search, independent service instances, optimistic
conflict rejection, replay and historical revision/citation preservation. It is
not an actual external-client or ChatGPT acceptance claim. AM1/AM2 extend the
fixture through REST/current/legacy MCP; AM3 adds grants and leak-negative cases;
AM4 benchmarks scoped structured retrieval; AM5 evaluates consolidation needs;
AM6 proves two independent SDK sessions. Native upgrade/recovery uses all three
actual installed predecessor digests above.

## Validation

The baseline full suite runs against the pinned disposable PostgreSQL 17/pgvector
0.8.7 image used by CI, exposed only on local loopback. Use local editable Core/app
imports explicitly, preserving the released runtime lockfile. Run:

```sh
python -m pytest -q app/tests packages/czero-core/tests tests/unit tests/integration tests/packaging
node --test tests/ui/*.cjs
go run tests/check_schemas.go
robot --dryrun --exclude ui -v NODE_ADDR:disposable.invalid -v IMAGE_URL:ghcr.io/stell0/czero:main tests
```

Set `CZERO_TEST_DATABASE_URL` only to a disposable database. Never run this suite
against the dedicated installation. Applicable native-script `bash -n` checks
also remain mandatory. The unmodified baseline passes all 812 Python/PostgreSQL/packaging cases in
179.02 seconds. The two new focused cases, 106 script cases, Go/shell checks and
nineteen Robot dry-run cases pass. The combined full suite passes all 814 cases in 178.40 seconds. Exact-source CI
follows in PLAN.md;
AM0 is incomplete until its required review/CI/promotion checks pass.
