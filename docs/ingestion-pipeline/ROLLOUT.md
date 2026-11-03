# Disposable ingestion pilot and recovery

The installed baseline does not change when a milestone merges. This task
authorizes disposable acceptance; a live deployment remains separately authorized.
Keep default extraction unchanged until a separately reviewed default-change
candidate satisfies all release, consumer and deployment gates.

## Before a disposable pilot

1. Pin the exact accepted source, independently released Core tag/commit, consumer
   lock and all immutable module/app/database image digests. Verify the actual
   installed image's Core Git identity; a producer wheel alone is insufficient.
2. Use a disposable C0 module with the supported C0-only backup/update workflow.
   Preserve a real accepted installed predecessor. Record source/file counts,
   settings, schedules, clients and unrelated module inventory before upgrade.
3. Retain the pre-upgrade backup and its tested clean-restore evidence. Upgrade
   schema forward and verify readiness, old complete reads/search/citations and
   zero automatic extraction/backfill. Keep unrelated instances unchanged.
4. Explicitly enable the extraction worker setting only for the disposable pilot.
   Begin with two workers and bounded document/space/instance limits. Four workers
   require their actual native memory/swap/pids and parser-lifetime evidence.
   The CPU-quota waiver remains unchanged; do not add `--cpus` or host delegation.
5. Stage explicitly selected synthetic originals through the trusted native
   producer handoff. New public browser/OAuth enqueue remains gated on a separate
   reviewed durable-authority binding. Existing collectors/public imports retain
   their original path and approvals; enabling a worker never promotes a grant.

## Observe and recover

Use selected-space reader progress and Background Work. Inspect safe unit errors,
attempts, next UTC retry, parser revision, wait/run time, cache counters and queue
depth. Compare complete text, offsets and citations, not merely a successful job.
No incomplete first import may become searchable evidence. A pending/failed
replacement retains the previous complete current generation.

- Retry failed units while staging is live to preserve successful work. Keep the
  exact revision/idempotency key across an uncertain response and read saved state.
- Cancel fences leases and discards private results. Published content cannot be
  cancelled. After expiry/cancellation, a full restart processes the original again.
- Standard full restart uses the existing worker. Native OCR/page-queue imports
  require a fresh explicitly authorized producer handoff for that new generation.
- Explicit reindex requires a retained original and a new publication generation.
  Tell users old exact citations will become unavailable only after success. Do
  not reconstruct a missing original from chunks or reindex managed source-sync
  parents/parts independently.
- Leave corruption, lease/manifest mismatch, lost authority and exhausted bounds
  visible as safe errors. Do not increase limits, restore retired body caches or
  treat another protected space as Shared to make a pilot pass.

## Rollback

Disable admission to new queued extraction and stop its timer/service through the
supported module configuration before changing executable images. Preserve the
ordinary scheduler, current complete generations, original store and private
failure evidence. Readiness alone does not prove content, OAuth or schedule safety.

Changing executable configuration is not a database downgrade. An older Core may
reject a newer schema; never bypass that check or run Alembic downgrade. Either
retain a compatible accepted executable while repairing forward, or restore the
complete tested pre-upgrade C0 backup into a disposable/new supported instance and
verify images, database, files, settings, clients and schedules together. Database
restoration may lose post-backup changes and needs explicit operational approval
for a live instance. Destructive recovery stays disposable for this task.

Retain exact source/run/image identities and all failed evidence. After a successful
pilot, record a separate checked closeout. Do not infer production rollout or a
stable module release from a benchmark, merge, producer publication or smoke test.
