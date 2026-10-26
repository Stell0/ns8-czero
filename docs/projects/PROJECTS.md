# Protected research projects

A project uses one existing protected C0 space. The stable project ID equals its
space UUID; labels are display data and need not be globally unique. No endpoint
creates a space or falls back to Shared. Existing grants and delegated scopes
remain authoritative. Setup/configuration needs Manage authority; ordinary reads
need Read, and adjacent-topic assessments need Write. User anchors additionally
require Manage authority and an affirmative authorization reference.

## Manifest v1

`czero_core.project_schema.MANIFEST` is the strict bounded schema. Unknown fields
and future schema versions reject. Compatible omitted v1 settings receive fixed
defaults; loading an existing v1 manifest is idempotent. Configuration changes use
expected revisions and replay keys and retain immutable `config_v1` snapshots.
An Admin configuration save also installs newly added managed record kinds
for an existing project, without replacing any immutable type definition.
A collision fails closed; ordinary agents cannot register trusted types.
The current pointer is `manifest_v1`; the complete queue and history are never
stored in that pointer. Type definitions are immutable and instance-wide. Records
and unique keys are protected-space scoped.

Required identity/meaning fields are `project_id`, `space_id`, `name`, `purpose`
and `scope`. Settings include description, language, IANA timezone, exclusions,
primary topic IDs, research, monitoring, schedule, reporting, maintenance,
connector IDs and state. Defaults are English/UTC; schedule requests are disabled.
The original projects' reference times belong in synthetic fixtures, not defaults.

The finite monitoring defaults are **5 queries and 10 inspected sources per
primary topic per local day**, with a 12-hour overlap. Configurable ceilings are
50 queries and 100 sources. Queue defaults are five ordinary attempts, ten total,
urgent priority zero, +20 inherited expansion and at most three children. An
initialized project requires primary monitoring and at least one authorized
active user anchor. No configuration edit grants space access, activates an
external task or authorizes a new user topic by itself.

## Setup and API

Use existing Admin space creation/grants first. All project operations require an
explicit `space_id`. Initialize a draft (`state.initialized=false`); create user
anchor records with actual tracking approval; configure primary IDs and only then
mark initialized. Unchanged uncertain retries keep their original key. A changed
request needs a new key. Configuration conflicts require re-reading and reconciling.

- `project_initialize`, POST `/api/v1/project/initialize`: manifest,
  authorization_ref, idempotency_key. Repeated logical initialization with a
  different key conflicts instead of replacing state.
- `project_get`, GET `/api/v1/project`: current manifest and stored revision.
- `project_configure`, PUT `/api/v1/project`: complete validated manifest,
  expected_revision, authorization_ref, idempotency_key.
- `project_topic_set`, POST `/api/v1/project/topics`: topic, expected_revision
  (zero creates), idempotency_key.
- `project_records_list`, GET `/api/v1/project/records`: versioned kind, limit
  (1–100) and offset. A full page is not a complete inventory.

REST and MCP use the same registered handlers. Browser writes retain existing
Origin/CSRF requirements. Native/delegated credentials retain existing validation.
Managed project types reject direct object creates, updates/deletes and bundle
writes, so queue policy cannot later be bypassed through the generic object API.
Unrelated record types remain available through their existing interfaces.

## Topic governance

`topic_v1` separates classification (`user`, `adjacent`, `peripheral`) from
lifecycle (`active`, `provisional`, `archived`, `retired`). IDs, aliases, parents,
originating question, direct user-anchor contribution, assessment and authorization
references are explicit. Core records the authorizing account, rather than trusting
an account ID in the request. Only a user anchor may be a primary monitored topic.
Adjacent relationships must resolve directly to an active user anchor; an adjacent
chain alone rejects. Peripheral ancestry is terminal. Its fixed expiry is the next
strictly future weekly occurrence; retries/edits do not extend it. Expiry is
enforced at an actual distinct weekly checkpoint at/after that occurrence, as
documented in [maintenance](MAINTENANCE.md). Archived/retired
topics do not reactivate through ordinary updates. Parent cycles reject.

Semantic relevance and the interpretation of the human request are supplied by
the external agent and recorded for review. Structural validation is not proof
that a relevance statement is true. Retrieved text cannot supply authority.

## Scheduling semantics

Daily and weekly local clocks use IANA tzdata. Each local occurrence has one cycle:
ambiguous fall-back clocks choose the first fold; nonexistent spring-forward clocks
move forward by the gap. A lookup after the first fold does not create a second
same-date occurrence. Peripheral expiry is strictly later than creation.
No C0 deterministic handler executes an agent prompt. Requested schedule settings,
actual host installation, unattended authentication and execution are separate
observations. External host verification remains pending.

## Current implementation checkpoint

M1 adds Core contracts/service, REST/MCP bindings and the read-only `/projects`
reader with literal rendering and access-loss/response-generation guards. It shows
configuration and tracked topics; operational observations are added by subsequent
milestones. During producer development the default consumer still pins released
Core0.33.0: it explicitly returns `project_core_upgrade_required` for new project
work, preserving existing operations. Final Core publication/pin adoption and
consumer verification are required before project availability can be claimed for
the released build. No runtime/library release or live deployment is claimed here.

See [durable workflow contracts](WORKFLOWS.md) for queue admission, leases,
fencing, day reservations, invocation uncertainty and source-sync recovery.
