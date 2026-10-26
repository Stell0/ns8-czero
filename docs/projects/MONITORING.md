# Primary monitoring and external research agents

Project monitoring uses existing protected spaces, managed typed records and
the same current-role/fenced transaction boundary as research runs. It executes
no search or model itself. Only configured active, affirmatively authorized user
topics can be primary topics. Adjacent and peripheral topics cannot acquire
mandatory monitoring through source text or agent inference.

Existing projects gain additive immutable record kinds when an authorized Admin
saves their configuration at its expected revision. Existing schema definitions
are checked byte-for-byte; conflicting definitions fail without replacement.
An unchanged configuration may be saved explicitly to register new kinds after
an upgrade. This does not expand scope, change grants or activate schedules.

## Durable coverage

`project_monitor_begin` resumes one `(project, local date, topic)` cycle under
the current daily run lease. Its initial resource limits and coverage interval
survive retries and configuration edits. Defaults are five queries and ten
source inspections per topic, with twelve hours of overlap. The start comes
from the previous verified matching-scope watermark, otherwise topic creation;
the end is the run's due occurrence. Scope changes require fresh coverage while
retaining consumed counters. Monitoring uses zero ordinary research attempts.

Before a provider call, use `project_monitor_reserve` with a stable request ID,
then record `started` and its actual outcome using `project_monitor_observe`.
An unknown outcome remains `uncertain` after ownership transfer. Explicit retry
reservations name the failed/uncertain call they replace and consume the same
bounded cycle allowance. Immutable call history preserves all observations.
Source inspections must come from observed query selections and cite actual
ready same-space source versions and matching immutable passages.

`project_monitor_finish` accepts `no_material_update` only after a successful
query and inspection of every selected source, with no unresolved checks.
Timeouts, failed calls and uninspected sources remain `partial` or `blocked`;
they cannot advance successful watermarks. Publication/event timestamps remain
distinct from retrieval/update time. An old fetched article is not new news.
Material results remain `ACCEPTED_PENDING_MERGE` until the evidence/result
publication contract verifies their knowledge commits. M5 supplies that gate.
Daily queue reservations and a successful monitoring phase require all primary
cycles to have verified coverage, even when queue allowances are exhausted.

## Project-bound agent packages

The existing agent packaging has an additional read-only
`project_agent_package_get` operation and `/api/v1/project/agent-package` route.
It creates a deterministic private skill or one-skill plugin containing the
canonical MCP URL, exact protected space/project IDs, manifest version, scope,
language, primary IDs, budgets and desired schedule. The generic C0 plugin
remains independently available. Project selection is explicit; denied or
invalid selections never fall back to Shared. Read-only questions cause no
mutation. External source instructions remain untrusted data.

The independently installable ingestion package can save and read back these
archives without changing project state:

```bash
c0-projects project validate --config project.json
c0-projects project skill --config project.json --output project.skill
c0-projects project skill --config project.json --format plugin --chatgpt-app-id asdk_app_actual --output project.zip
c0-projects project schedule --config project.json
```

Use the existing private OAuth job configuration described in
[SOURCES.md](SOURCES.md). Project-only configurations may have an empty source
list. The client checks the archive hash, exact binding, bounded entry allowlist
and non-executable paths before an exclusive mode-0600 save. Generation does not
install the package, associate an app ID or authorize a new scope.

The skill verifies the canonical connection through saved host settings or
trusted server metadata before discovering `get_profile`/`project_get`; display
names alone cannot establish the connection. Missing project services block the
workflow. If a checkpoint service is also missing, explain that the capability
report is unsaved instead of claiming a durable receipt. Intake with queued
extraction returns actual source/version IDs and a pending citation; it never
invents a passage. Independent synthetic forward evaluation exercises these
conditions without contacting a live instance or proving external execution.

## Calendar and host handoff

`project_schedule_get` returns desired daily/weekly settings, latest due and
next UTC occurrences with stable local cycle dates. IANA gaps move forward;
folds select the first occurrence. A missed occurrence may be claimed for up
to eight days only at its exact configured due time. Actual attempt allowances
still use the current server-observed local day; replay cannot replenish them.

Generated daily, weekly and recovery prompts include a complete installation
and verification handoff. Use the intended host's supported Scheduled interface
and existing C0 OAuth connection, read back task IDs/timezone/prompts and observe
an actual scheduled run plus independently retrieved C0 results. Web scheduling
can use attached skills/plugins; desktop local-project scheduling also depends
on the machine/app being available. See the official
[Scheduled tasks documentation](https://learn.chatgpt.com/docs/automations).
C0 does not invent unattended client-credentials authentication: the
[MCP authentication contract](https://developers.openai.com/plugins/build/auth)
uses the end user's OAuth grant.

There is no verified standalone host scheduling-installation API in this
implementation session. No actual task has been installed or activated.
`project_runner_observe` stores an attributed operator/runner/simulation report
with actual task/evidence references; it never enables schedules or proves host
execution. Reported execution requires a completed same-project C0 run. Code,
fake-agent tests, actual external-agent execution and unattended scheduling are
separate evidence levels. Publication, notification and human reading are also
separate observations.
