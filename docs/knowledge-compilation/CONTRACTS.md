# Frozen knowledge-compilation contracts v1

These are normative design and acceptance contracts. M0 froze existing behavior;
[M1](M1.md) implements coordination and [M2](M2.md) refines guarded publication.
Later discovery, feedback and scheduling milestones remain unimplemented. Changes require a reviewed contract/version
update. See [PLAN](PLAN.md) for ownership, SQL schema, budgets and milestone scope.

## C1 — Authority and learning

Every operation requires an explicit selected space, including Shared. Persisted
membership, current protected grant, delegated scope and API-key space/revision
binding remain authoritative. Read-only operations require Reader and `c0:read`;
compilation mutations require Editor and `c0:write`; policy changes require Admin
and `c0:admin`, with existing first-party browser CSRF where applicable. Write
never implies Read. Disabled/missing policies permit status reads, not proposals,
run reservation or automatic publication. Feedback additionally requires its own
flag and retrieval origin validation. Explicit read-only user instructions win.

Use closed reason codes: `missing_concept`, `incomplete_page`, `stale_support`,
`distributed_evidence`, `missing_relationship`, `terminology_gap`, `contradiction`,
`applicability_gap`, `missing_link`, `source_changed`, `initial_compilation`.
An observation holds reason, source/target identities and a source-derived label
up to 160 characters; no raw user query, conversation, generated answer, arbitrary
free-form context or evaluation label. The source label is data, not an instruction.
Unknown fields fail validation. Maximum 3 logical documents and 32 exact evidence
identities per task; metadata at most 16 KiB. Reads never enqueue work or persist
compiler progress. Existing authentication last-use accounting is unchanged.

`queue_only` allows proposal creation, dry-run and explicitly approved exact-plan
publication. `automatic_supported` permits only supported low-risk changes in
allowed managed target kinds. Uncertain/contradictory/unknown applicability
changes stay `needs_review`; an Editor records a decision tied to the plan hash
and current references. Approval never promotes verification or broadens scope.
Policy disable/change invalidates reserved publication eligibility immediately;
old accepted knowledge stays readable and authored knowledge is preserved.

## C2 — Identity and deduplication

Logical documents retain their existing IDs. Exact generations/chunks remain
immutable and expire with 410; hashes do not substitute for citation identities.
Capture logical document revision/full-body hash and ordered physical part
identities, plus exact source/version/document/chunk hashes/offsets actually read.
Equal text under a new exact publication identity still requires revalidation.
Metadata product/version applicability changes participate in input fingerprints.

Task dedup is server-calculated SHA-256 of canonical JSON:
`[space_id, profile_id, profile_version, reason_group, canonical_topic_key,
sorted_source_bindings, current_target_identity]`. Canonical JSON uses sorted
keys, UTF-8, finite numbers and existing digest conventions. Topic identity uses
an existing resolved entity/alias or managed target identity when available;
a new proposed key is stable, namespaced, normalized and at most 96 characters.
Source bindings contain IDs/generation/hashes and provenance digest; titles alone
never define identity. The target component is a stable managed key/kind/ID,
not its changing revision/hash. Resolve create-only keys to their retained task
mapping after publication, so the compiler's own edit cannot generate another task.
Expected target revisions affect validation, not exact dedup. Policy version affects eligibility, not dedup identity.
Same-topic work with changed source support supersedes/coalesces into a bounded
active revalidation task, retaining prior task IDs and consumed attempts.

Exact dedup is deterministic, semantic equivalence is an attributed external
comparison. Search Wiki, aliases and active/terminal task identities before
creating. Title changes, translations and paraphrases cannot alone justify a new
page/entity. Ambiguity becomes reviewable; do not merge different products/versions
merely because normalized titles match. Stable slug uniqueness is a final race
control, not a semantic duplicate detector. Existing alias ownership wins.

## C3 — Discover and coverage

Discovery is bounded and deterministic. Core performs keyset scans over current
logical publications `(publication_time, logical_id)` with a persisted upper
cutoff, not a client offset loop or maximum UUID watermark. M3 must establish a
publication marker for both singles and completed multipart parents using existing
publication transactions. Track both the current sweep cursor and a next-sweep
catch-up window; insertions/changes behind a cursor cannot become permanent gaps.
A bounded inventory reconciliation sweep catches archives/disappearances and
multipart membership changes; never infer deletion from a partial inventory.

Only ready complete originals are analyzed. Missing structure uses bounded
whole-body or exact chunk reads; explicit omitted/oversized sections remain
unread, not examined. A queued/failed replacement does not invalidate its still
current complete predecessor. A first incomplete source cannot establish coverage.
Record last observed separately from successfully compiled generation/hash;
no-change is a successful source assessment only with actual original inspection
and a justified outcome. Partial analysis cannot advance successful coverage.

Report ready inventory, discovered, considered, no-change, produced targets,
stale, unavailable, pending and failed, with cutoff and profile. Changes during
execution make coverage provisional until catch-up, never "100% current" from
an earlier denominator. Unchanged source/profile/provenance/dependencies does not
reserve inference again. A new relevant dependency can queue bounded reconsideration
without pretending all unchanged sources require recompilation.

## C4 — Analyze, plan and validation

The external agent reads current originals, treats embedded instructions/URLs/
commands as inert source data, compares existing knowledge, and separates direct
observations, supported synthesis, uncertainty and contrary evidence. Wiki text
can guide navigation but cannot be sole factual support. Do not auto-fetch source
links, run commands, copy secrets, change tools or widen space/profile/model scope
because a source says to do so. Model output receives no verified status.

The version-1 plan envelope is closed: `schema_version`, `space_id`, `task_id`,
`expected_task_revision`, `policy_revision`, `profile_id`, `profile_version`,
`source_bindings`, `target_bindings`, `dedup_decisions`, `classification`,
`operations`, `deferred`, `usage_reservation_id`. A run lease accompanies validation/
apply, not an instruction field. Source bindings contain current logical and
physical exact identities, hashes, offsets and provenance digest. Target bindings
contain actual kind/ID/revision/hash or create-only canonical key/slug, managed
ownership and annotation expected revisions. Dedup decisions name actual resolved
candidates, comparison result and source-derived rationale code. No invented IDs.

`operations` reuse the existing fixed bundle operation+arguments schema; at most
25 mutations/262144 aggregate JSON bytes and existing per-record limits. Apply
requires at least one mutation; no-change plans use an empty list and complete
through a checked checkpoint with original bindings. Default profile allows
managed `wiki.upsert` and unverified `annotation.update`; expanded approved
profiles allow entity create/update/alias/link, sourced claim create/update and
relation create/update. No automatic delete/archive/unlink/retract, schema install,
source ingestion, scopes, jobs, schedules, imports or commands. Existing typed
records are opt-in and use actual registered schemas; managed project objects
remain protected. Forward/self result references fail.

All assertions require current source support or explicit unsupported deferral.
Unknown applicability remains unknown; literal version tags never become ranges.
Contradictions remain separate sourced assertions and a reviewable finding; do
not decide truth by newest retrieval timestamp. Claims immutable predicate/value
semantics remain unchanged. Do not auto-adopt an authored page as managed or
replace authored annotations. A supported proposed edit to authored material
requires exact-plan review and current revision; automatic cleanup never deletes it.

Validate exact space/access, policy/profile/targets, current ready originals,
all source hashes/part membership/provenance, exact target revisions, alias/slug
collisions, classification, expected annotation revisions, budget, plan size and
live fence. Return a canonical plan hash and identity digest with explicit eligible,
needs-review, deferred or invalid outcome. Structural checks cannot prove entailment,
semantic novelty, actual model spend or malicious external-agent honesty.

Durable SQL tasks/events store plan hashes, identity bindings and outcomes, **not**
full plan bodies/source quotes. The runner may hold the current candidate in
private transient state, but must discard expired source packets/proposed copied
text on 410/replacement and retain only hashes/IDs/recovery metadata. No source
body archive in coordination receipts or model traces. Runtime retention rules
also apply to indirect copies. Authored published Wiki knowledge follows existing
latest-only and stale-evidence semantics.

## C5 — Apply, transaction and verification

Standalone bundle publication is insufficient for a compiler. The trusted guarded
caller reuses bundle validation/dispatch inside **one** transaction covering
current authorization, live lease/fence, policy, sources, target revisions,
content publication, dependencies, source checkpoint and payload-free receipt.
Validation before a network model call is advisory; apply rechecks everything.
Refactor trusted connection composition minimally without exposing callbacks,
arbitrary SQL or bypasses to the client. Existing generic bundle behavior stays
compatible and independently authorized.

Preserve lock order: object mutex (when required), knowledge mutex, authority
locks, current-content lock, then compiler policy/budget/run/task rows and target
locks in stable order. A tracking-only operation must not hold a compiler row
while later waiting for the knowledge/content locks. Source publication and
invalidation must use compatible order; reverse dependency fanout is bounded.
Staleness queries compare current identities immediately, without writing on GET;
the sweeper later persists stale reasons and tasks. Publish-time source checks
and the current-content lock prevent a replacement racing a validated apply.

A commit returns `applied_pending_verify` with actual results. The agent reads
back every changed target and cited original under current authority; a separate
verify write records exact observed revisions/hashes and finishes only matching
proofs. A database response or queued task is not completion. A target edited
before verification stays conflict/partial, preserving both authored change and
recovery identity. Readback proves persisted content, not factual correctness.
Multi-bundle work uses multiple bounded child tasks with separate verification;
never call a partially committed multi-bundle plan atomic.

If a source is replaced, archived, removed, incomplete or inaccessible, keep
authored knowledge, mark dependencies stale/unavailable and queue bounded
revalidation only when eligible. No silent rebinding to new text after 410.
A retired chunk's identity survives as an opaque dependency, with no live FK that
would retain or block deletion of superseded bodies. Terminal outcomes and replay
receipts are metadata-only. Revalidation explicitly reads new evidence and uses
a new plan/replay identity; verified status never transfers from an old revision.

## C6 — Leases, retries and budgets

Logical run identity is space + kind + local cycle key for daily/weekly, or an
explicit stable key for bootstrap/manual/retrieval. Lease tuple is exactly
`run_id, lease_owner, fencing_generation`, bound to actor and acknowledged policy/
profile revision. Reservation binds selected task revision and current run fence.
No independent second task lease. Renew before expiry; takeover increments fence
and attempts. A stale/expired/transferred/configuration-invalidated fence rejects
new writes **and replay**, even if an older request committed successfully.
A current worker first reads the saved task/apply outcome and reconciles it.

Task states: `queued → leased → planned → applied_pending_verify → succeeded`;
branches `no_change`, `needs_review`, `deferred`, `conflict`, `failed`, `uncertain`,
`superseded`. Only live-fenced validated publication enters applied state; M1
cannot record it without M2's trusted publication receipt. Planned stores identity/
hash only. Retryable failures release reservation and set backoff; semantic review
holds do not consume inference indefinitely. Terminal repeated proposal returns
its actual existing outcome. Explicit new evidence/profile input permits a new
linked generation of work. Attempts and budget reservations never reset on rename,
replay, timezone changes, lease transfer or moving a task between run kinds.

Before model invocation reserve a request ID, maximum input/output tokens and
run/day allowance; record started and then returned/failed/uncertain separately
as fixed checkpoint observations. An interrupted started request is uncertain;
reconcile provider/runner state before retry, charge reserved maximum when usage
is unavailable, and stop after maximum attempts. Local idempotency cannot promise
exactly-once provider execution. Reservations across manual/bootstrap/retrieval/
daily/weekly share day limits; weekly also observes its own ceiling. Server time
and policy timezone define windows; a cap/timezone edit retains active snapshot
and counters until the original window closes. Hard bounds are in PLAN.

Each mutation carries a stable actor/space/request key and canonical fingerprint.
Identical uncertain retry retains both; changed content requires a new key after
reconciliation. Receipt replay rechecks access/fence/policy and current-content
retirement first. Source/target supersession returns authorized
`content_superseded` (HTTP 410). Conflicts return 409; invalid input 422;
policy/authority/scope rejection uses existing 403 mappings; queue/budget holds
are explicit bounded outcomes with next eligible time, never a successful publish.
Use fixed sanitized error codes: no model prompts, credential-bearing URLs or
source/conversation text in errors/logs. Lost response after commit is resolved
by task/outcome identity plus actual target reads, not a new create request.

## C7 — Compatibility, migration and rollout

M0 adds no migration/version/lock/runtime/package changes. M1 uses the next actual
migration ID, additive empty coordination tables, closed server health/version
metadata, wheel/archive inclusion and repeated-upgrade tests. Existing knowledge,
projects, OAuth/key authority and disabled policies remain unchanged. No backfill,
source rescan, project initialization or schedule activation during migration.
No downgrade is promised; supported backup/restore retains coordination identities,
current-only bodies, counters and fences. Restored leases must be invalidated or
expired before external workers resume; predecessor credentials cannot regain
new authority. Test a real genuine-predecessor upgrade and clean restore.

Producer Core development uses an explicit local override. Immutable Core release,
consumer tag/range/lock adoption and actual published-image/native checks remain
separate. Old servers omit unavailable workflows from generated capability guidance;
new archives must never silently require nonexistent compiler tools. Preserve
registered app identity and existing consent, requesting fresh scopes only through
explicit approval when actually needed (no new scopes selected by this design).

## Acceptance matrix

| First milestone | Required observable controls |
| --- | --- |
| M0 | Frozen synthetic hashes and separate retrieval labels; current source-only retrieval; deterministic existing profile plans; multiple relational Wiki/graph/claim records with exact citations; replay/no-change; source replacement/410/stale support; source instruction inert; baseline SQL schema unchanged. |
| M1 | Disabled/restricted policy, Reader/Write-only/cross-space/key boundaries, duplicate proposals, queue caps, real concurrent reservations, lease expiry/takeover/crash recovery, stale-fence replay, policy changes, retry/usage windows, indexed queries, migrations/package/restore. |
| M2 | Initial bounded validated apply, false/uncertain/contrary assertions, exact quote/hash/revision validation, semantic duplicate candidate decisions, authored/concurrent edits, atomic rollback, lost-response recovery, verification and plan injection. |
| M3 | Resumable bootstrap, unchanged inference/write suppression, source replacement/archive/deletion/failed first extraction, incomplete multipart and part shrink, cursor churn/late publication, dependency invalidation, rotating bounded review and project/non-project scope. |
| M4 | After-answer no-change/proposal/low-risk branch, zero Reader writes, policy feedback gate, no conversation/label retention, bounded latency/usage and answer independent of learning failure. |
| M5 | Actual generated/installed skill discovery, deterministic archives, current/older capabilities, UI selected-space EN/IT/theme/keyboard, installed external runner, actual model/tool execution, key/OAuth auth failure, redacted logs, cron/systemd due runs, DST/retry/missed run and ChatGPT capability limits. |
| M6 | Full matrix plus matched frozen source-identical A/B, independently graded answers/unsupported assertions, citations/quality/latency/cost/coverage and authorized private documentation acceptance, all failures preserved. |

No test that asserts a fixture's desired future state counts as testing that
future server behavior. M0 deterministic responses are selected by source key,
never evaluation questions. Real model improvements, production mutation and
unattended host scheduling remain separately measured gates.
