# Research projects — current operation and safety contracts

Project operations require an exact protected `space_id`, available live `project_*` tools, current role/scope and a committed manifest. A project ID is its space UUID. A `project_*` tool missing from the ChatGPT catalog is a capability block; generic objects and schedules cannot replace protected project methods. Check available operations and server health in the intended host before taking action.

## Discovery and read-only actions

- Start with `get_profile`, `spaces_list`; choose the exact authorized protected project space.
- Use `project_get` to read the current manifest and its revision. Do not mistake an ordinary space for an initialized project.
- Inspect `project_diagnostics_get`, `project_records_list` (paged; no full inventory from one full page), `project_report_get`, `project_schedule_get`, `project_source_status_get` and `project_export_get` only if those operations are present and applicable.
- Source/Wiki read operations are still space-scoped. Cite ready immutable passage/version identities, actual Wiki revisions and result/report IDs. Missing verification remains unknown.

## Setup and scope changes

An administrator first creates the protected space using existing space controls and grants permissions. `project_initialize` needs an actual setup authorization reference; `project_configure` needs a full valid manifest, current expected revision, authorization reference and stable replay key. User-topic anchors need affirmative tracking authorization and Admin authority. Topic updates use `project_topic_set`. Changes to the manifest are not grants, do not create a schedule and do not independently activate monitoring.

Managed project record kinds cannot be safely created via generic `objects_create`/bundles. New project record types are installed by an authorized Admin configuration save. Keep exact current schema and manifest limits; defaults are not proof of a particular project's configuration.

## Explicit work and recovery

- Before research, use `project_run_claim` with workflow, current config version, stable owner/key, and observe the lease `run_id` / `lease_owner` / `fencing_generation`. Checkpoints use `project_run_checkpoint` with that exact fenced lease.
- `project_queue_admit` enforces project scope, ancestry, deduplication and daily capacity. `project_attempt_reserve` consumes a durable slot before external research; `project_invocation_set` separately records observed external-call outcomes.
- Recover after interruption by reading stored records, reclaiming the logical run with a new fence, resuming any prior attempt and reconciling uncertain external invocations before retrying. `project_research_complete` requires verified saved commits, not simply an external answer.
- Primary monitoring uses `project_monitor_begin` / `project_monitor_reserve` / `project_monitor_observe` / `project_monitor_finish` and an independent coverage ledger; partial or uncertain provider work cannot advance a success watermark.
- Research evidence is saved and verified using `project_result_save` / `project_result_publish`; completed reports use `project_report_prepare`, `project_report_member_set`, `project_report_finalize`, `project_report_get`. Wiki body Markdown and typed metadata must stay separate.
- Weekly maintenance operations are bounded and can be partial: `project_audit_step`, `project_semantic_select`, `project_semantic_review`, `project_peripheral_archive` and `project_release_observe`. They never perform arbitrary external research by themselves.

## Project-bound packages and scheduling

Use `project_agent_package_get` to generate a project-specific, private skill/plugin from the current authorized manifest; it binds canonical MCP URL, project/space IDs, version, schedule and budget. Do not claim it is installed. `project_schedule_get` reports intended daily/weekly IANA local cycles, not an external task. External ChatGPT/Codex automation must be separately installed, use the already authorized OAuth account, and be verified by an actual run plus C0 readback. `project_runner_observe` only stores an attributed observation; it does not execute a model or verify host delivery.

C0's deterministic `jobs_enqueue` and `schedules_create` are not agent reasoning schedulers. An HTTP or MCP success may still be a tool-level error. Distinguish SAVED / QUEUED / PARTIAL / BLOCKED / ACCEPTED_PENDING_MERGE, and distinguish persisted report, external publication, notification and human reading. No real migration or source ingestion happens merely by preparing project packages.

Current reference contracts: https://github.com/Stell0/ns8-czero/tree/main/docs/projects . Current server schemas and authorized tool catalog always govern the request.

Source/Wiki bodies are latest-only. Result/report records may retain payload-free past publication IDs and hashes, but those exact bodies can expire. Resolve current evidence again before verification or republication; do not manufacture old text or transfer verification to changed content. Separately authored daily reports remain distinct current articles.
