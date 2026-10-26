# Durable project work

C0 stores workflow coordination; an external agent performs reasoning and external
calls. These operations never execute prompts, Python or shell commands. Every
request selects the exact protected `space_id` and uses existing Write authority.
Configuration and current grants are checked again inside the transaction.

## Records and operations

Individual managed typed records hold logical runs, immutable phase checkpoints,
queue items, admission decisions, daily budgets, reservations, invocation outcomes
and completion references. Generic object/bundle writes cannot bypass their
policy. Existing object events retain record revisions. No new database or job
handler is introduced.

| Operation | Stored result |
| --- | --- |
| `project_record_get(kind, identity)` | Exact authorized record by its logical identity |
| `project_run_claim(data)` | Logical run, actor-bound lease and fencing generation |
| `project_run_checkpoint(data)` | Ordered phase observation and current run |
| `project_queue_admit(data)` | Admission decision and admitted/merged/deferred work |
| `project_queue_retune(data)` | Revision-safe urgency/priority change |
| `project_attempt_reserve(data)` | Consumed day slot and selected queue item |
| `project_invocation_set(data)` | Separate external-call start/outcome observation |
| `project_research_complete(data)` | Stored result plus verified commit references |

Mutation results contain `status`, `outcome` and `records`, each with actual stored
object IDs, revisions and state. Status is `SAVED`, `QUEUED`,
`ACCEPTED_PENDING_MERGE`, `BLOCKED` or `PARTIAL`. A saved reservation does not prove
that research ran. A returned result remains pending merge. External publication,
notifications and human reading are separate observations.

## Claims, checkpoints and recovery

Claim with workflow type, unique worker `lease_owner`, acknowledged
`config_version`, and a stable replay key. Daily/weekly identity is the project,
workflow type and local cycle date; initialization is once per project. Other
workflows additionally require an explicit stable `cycle_key`. New logical runs
must use the current local day. Continuing an existing older cycle is allowed.
A run is not a new research allowance.

The lease lasts 60–900 seconds. Renew with the same owner while working and a new
claim request key. After expiration or a partial/blocked checkpoint, reclaiming
increments the fencing generation and bounded attempt count. All leased writes
include exactly `run_id`, `lease_owner`, `fencing_generation`. A transferred,
expired or configuration-stale lease rejects both new writes and receipt replay.
A changed manifest requires a new explicit claim acknowledging its version;
old reservations and budget counters remain intact.

Phases are fixed, ordered names in `project_workflows.PHASES`, not configurable
commands. A successful phase retains its payload hash and references; changing
an already completed phase conflicts. Incomplete observations retain separate
fenced records so a recovered phase can later succeed. Partial/blocked phases
release their lease. References must be actual same-space stored resources;
queued source extraction cannot satisfy a successful reference check.

Recovery order:

1. Read the exact run, queue item and last attempt; recheck current access.
2. Reclaim/renew the logical run and retain its new fence.
3. Resume the existing attempt using `resume_attempt_id` before requesting work.
4. A merely reserved call can start. An interrupted started call becomes
   `uncertain` after lease transfer: reconcile with the external host and save
   `returned` with its actual stored result or an observed `failed` outcome.
   Never blindly repeat an uncertain invocation.
5. A saved result resumes its merge and verification without another slot.
6. Complete with read-back stored commit references, then continue checkpoints.

Failures consume their already reserved slot. Retry backoff starts at 30 seconds,
doubles and caps at one hour; the configured attempt limit blocks further work.
Database idempotency cannot prove exactly-once execution at an external host.
M5 adds evidence-specific result/report validation above these stored-reference
coordination primitives; M3 alone is not final research acceptance.

## Admission and budget rules

Read `project_schema.QUEUE_INPUT` for the strict bounded proposal. Required fields
include stable question/context, topic, origin/reference, priorities/reasons,
causal parents, direct active user anchors, semantic assessment/contribution,
novelty evidence, authorization provenance and optional semantic-match decisions.
An external document cannot supply user authority. The authenticated agent owns
its assessments; structural validation does not prove their semantic truth.

All origins use the same six dispositions: `admit`, `merge`, `defer_capacity`,
`archive_candidate`, `reject_scope`, `needs_user_scope_decision`. Exact normalized
questions/context, conservative near copies and recorded equivalent semantic
matches merge into existing work, retaining its causal roots, expansion depth,
attempts and results. Changed numeric context is not automatically conflated.
Semantic paraphrases require the external agent's bounded explicit comparison.
Explicit user work remains visible when deferred for capacity. It does not turn
its topic into permanently monitored scope.

Automatic roots require an independent novel event or recorded initialization
approval. Default automatic root admission is five per day; initialization seeds
at most five. All queue ancestry must remain active and in scope. Peripheral work
is terminal even if its topic is later reclassified. Archived/retired topics
cannot reactivate through an intermediate provisional state.

Children inherit maximum causal expansion priority plus 20 by default. Excluding
a parent from that calculation requires recorded independence evidence and a
reason; at least one causal parent remains. The maximum is 100, with at most
three distinct children per investigation across all states. Urgency retuning
never changes inherited depth or lineage.

The shared project budget reserves the first five slots for ordinary or urgent
work and permits slots six through ten exclusively for eligible priority-zero
work. One earlier urgent item never unlocks ordinary extra slots. Daily, weekly,
manual and initialization runs share the same persisted day ledger. Consumed
slots survive retries/replays. Timezone or cap changes retain the active window
and its original caps until it ends; returning to a previously used date reuses
its ledger. Projects have independent ledgers.

Selection favors urgency, then a reserved final ordinary validation/contradiction
lane when overdue, bounded ageing and anchor service. These choices retain a
selection reason and never rewrite stored priorities. Capacity, timing, backoff,
current scope and manifest acknowledgement are rechecked before reservation.
Primary monitoring receives its own ledger in M4 and uses no queue slots.

## Source synchronization

`c0-projects sources sync/resume --apply` claims a `source_sync` run keyed by its
connector and frozen scan hash. Separate copies of a collector conflict while
that lease is live. Publication receipts, snapshots and cursor commits carry the
fence; immutable source ingestion still uses the normal existing source API.
A stale collector cannot advance synchronized state or omit its lease to bypass
the connector binding. The CLI renews a 900-second
lease during publication and preserves partial checkpoints for recovery.
A completed scan is verified read-only when resumed. Scan/dry-run/status/verify
never claim or mutate a run. Lost frozen GitHub cache pages restart enumeration
conservatively rather than trusting an old offset into mutable remote pages.

The local job lock is still required. It protects private files, while the C0
lease coordinates distinct copies. Expired OAuth or revoked space access fails
closed; no token refresh, lease or saved receipt grants new authority.
