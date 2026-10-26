# Project maintenance and calendar contracts

Maintenance uses the existing protected project, current manifest and fenced
weekly/maintenance run. It never executes a model, shell command or downloaded
instructions. Semantic judgments are supplied by the external agent. These
operations require Editor authority; configuration/topic authorization remains
in its existing Admin interface. Reader diagnostics grant no mutation authority.

## Structural inspection

`project_audit_step(lease, kind, limit, idempotency_key)` inspects at most ten
resources in one transaction. Kinds are `configuration`, `wiki`, `claims`,
`documents`, `chunks`, `queue`, `topics`, `sources`. Repeat with a fresh operation
key while the receipt is PARTIAL. An audit has a per-run configured
`maintenance.max_inventory` bound and a durable UUID cursor. The shared rotation
cursor advances with optimistic revision checks; an overlapping run cannot rewind
another run's progress. Replaying a saved operation does no additional work.

Checks cover approved connector definitions, primary monitoring gaps, canonical
local Wiki links, possible orphans, serialized page envelopes, content hashes,
passage offsets, actual ready claim evidence, current claim annotations/validity,
source extraction, queue identities/ancestry and interrupted/deferred work.
Unique typed keys prevent duplicate managed identities. Arbitrary legacy IDs and
semantic duplicates require the offline parser or external review.

Individual audit findings preserve history. Latest per-resource observations
record resolved counts without deleting earlier findings. An orphan notice is
conservative: graph relationships and noncanonical links may connect the page.
Link inspection recognizes `[label](./wiki?page_id=...)`, slug queries and
`[[slug]]`, at most32 targets per page. Code examples can produce notices requiring
review. External URLs, cross-space destinations and semantic truth are not
inspected. A resumed rotation slice is explicitly distinct from a complete
current snapshot. Inventory exhaustion remains PARTIAL and blocks a false weekly
SAVED phase; increase an authorized bound or continue in a later rotation.

Weekly phase checkpoints require actual same-run/config audit receipts:
configuration; references (Wiki/claims/documents/chunks/sources); queue
(queue/topics); archive; semantic; then the existing saved weekly report.
Structural completion can retain findings requiring follow-up. It does not prove
that semantic contradictions have been resolved.

Completed queue history never prevents existing active work or saved merges
from resuming. When bounded historical near-duplicate coverage is exhausted,
indexed exact matches retain their original identity and lineage. Unknown new
questions are saved as visible `defer_capacity` admissions with
`historical_inventory_requires_review`; they gain no fresh allowance. Review
the retained candidate and existing history before an authorized bound change
and reassessment. No completed history is deleted to gain capacity.

## Semantic rotation and archives

`project_semantic_select(lease, refresh_changed, idempotency_key)` records a
bounded selection of actual Wiki revision UUIDs/hashes. One rotating slot
prevents recent/risky pages from starving older pages; remaining slots prioritize
recorded risk and recency. `project_semantic_review` accepts a selection reference
and validated assessment (`reviewed`, `partial` or `blocked`), its provenance,
limitations, actual citations and optional proposed question. Read the selected
Wiki revision before assessing it. A proposed question is descriptive: submit it
separately through ordinary `project_queue_admit` policy.

Changed current Wiki revisions conflict. Explicit `refresh_changed=true` retains
the old selection snapshot and requires fresh review. The cursor advances only
after every selected revision is reviewed. A complete selected batch may still
have `semantic_coverage_complete=false`. Never describe that as a complete audit.
Lease transfer, configuration changes and concurrent cursor progress retain their
normal fencing/conflict behavior.

Peripheral topics retain a fixed next-future weekly occurrence. Expiry takes
effect at an actual distinct weekly run started after creation and at/after that
occurrence. An old run resumed later cannot expire its own new topic. Until that
checkpoint a directly authorized one-off question remains terminal; it never
gains monitoring or descendants. `project_peripheral_archive` saves a compact
externally authored summary, assessment, actual ready references and original
topic snapshot, then archives the topic with immutable lifecycle history.
Preexisting topics first seen during an upgrade get an explicitly labelled
upgrade snapshot, not invented historical revisions. Evidence is never deleted
and archived topics cannot silently reactivate.

## Calendar

`project_event_set` validates independent event identity/topic, provenance,
IANA timezone, start/end, date precision and status. Event dates are independent
from source publication/update/retrieval timestamps. Date/time precision supports
executable refreshes; month/year/unknown precision is descriptive only.
Recurrence is none/daily/weekly/monthly with finite interval and optional end;
monthly dates retain the original day anchor when a short month is clamped.

Calendar work uses the same admission operation as all other origins. The
candidate must reference the actual event, question, latest eligible occurrence,
priority, parents and date window. Identity is
`calendar-` + SHA256(JSON `[event_id, occurrence_date]`), using the service's
canonical digest encoding. Discover stored receipts rather than guessing IDs.
Missed equivalent refreshes coalesce to the latest occurrence; previous coverage
requires an actual stored queue/admission receipt. Recurrences preserve the first
causal root and expansion depth. Urgency changes do not reset depth, scope or
budgets. Deferred/rejected work stays visible; an event alone grants no scope.

## Release observations

The independent client command checks public metadata only:

```sh
c0-projects project release-check --config project.json --input release-plan.json --dry-run
c0-projects project release-check --config project.json --input release-plan.json --apply
```

The plan has `lease` (run_id, lease_owner, fencing_generation), `repository`
(`Stell0/ns8-czero` or `Kabutojira/WikiPlant`) and `installed_version`.
Validation precedes networking. The safe public fetcher permits at most five
requests, one MiB and15-second request deadlines; it verifies repository identity
and resolves release tags to immutable commit identities. No release assets or
code are downloaded/installed. Dry-run writes nothing. Apply saves a real source
version and verifies extraction before `project_release_observe` records it.
Unchanged snapshots reuse the immutable version; lost responses reconcile by
stable source key/hash. Three observations per local calendar week and one-hour
failure backoff bound retries. Authentication/rate-limit failures remain failed,
never up-to-date. The client uses public metadata without private credentials.

Core validates saved ready metadata, fresh/complete flags, semantic versions and
release identities. Outcomes distinguish no_release, available, up_to_date,
partial, failed and security_alert for a changed known published identity.
At most ten release identities are accepted per observation. Their first complete
fresh identities remain immutable; later observations cannot legitimize a changed
identity. A security alert remains blocked for explicit operator investigation;
this collector has no automatic acknowledgement or reset operation.
Latest stable metadata is an observation, not compatibility, installation or
complete release-history verification. Version-only comparison cannot prove an
installed commit matches. Existing reviewed Core/upstream adoption is required;
this command never installs workflow/skill updates or upgrades C0.

## Diagnostics and verification

`project_diagnostics_get` and the read-only project UI expose actual last
successful daily/weekly runs, saved pinned daily report, current connector
definition coverage, bounded errors, held candidates and structural findings.
An expired lease is incomplete work. A report saved in C0 does not establish
publication, notification, human reading or unattended execution.

Real PostgreSQL tests cover overlapping cursors, stale revisions/fences,
archive checkpoints/history, bounded inventory recovery, calendar recurrence and
ready release metadata. Signed OAuth/SDK tests drive a fake weekly agent and
source readback. Native recovery retains audit/semantic/event records and cursors;
actual external-agent semantic quality and scheduled execution remain unverified.
