# C0 roadmap

C0 has two uses: a shared second brain for people and assistants, and a reusable starting point for AI knowledge applications. See [README](README.md) for the product, architecture, data model, setup and fork walkthrough.

## Roadmap

### Active implementation — reusable ingestion samples

The operator approves the full GitHub project/contributor/document pipeline as
an instance-neutral sample and a dedicated ingestion OAuth connection. Add a
development-only Python package under `samples/ingestion`, with shared SDK/MCP,
identity/space checks, credential/state storage and source-ingestion helpers.
Keep GitHub discovery, metrics and mapping separate. Preserve stable external
keys, immutable snapshots, source-version hashes, receipts, partial coverage,
bounded work and independent readback; unchanged reruns must not duplicate data.
Wiki summaries are opt-in. Existing pages require matching private receipts for
ID/revision/body; preserve manual edits and unrelated pages without adoption.

Local jobs live under ignored `.local/ingestion/<job>` with a runnable wrapper,
instance `.env`, source configuration, private credentials, snapshots and state.
Use a dedicated preapproved OAuth public client with exact loopback callback,
explicit background consent, locked atomic rotation and no unattended interactive
fallback. Normal sync requires explicit apply and Read/Write; Admin bootstrap is
separate and never overwrites incompatible global schemas. Preserve the original
external GitHub directory and migrate its configuration/state without live writes.

Add the `c0-ingest-sources` repository skill, public adapter notes and synthetic
regressions. Future ingestion first reads samples, implements reusable adapters,
uses private jobs, verifies actual receipts, removes private material from the
complete contribution and opens an upstream PR using nethserver-pr. Register
reusable fork files explicitly and keep all samples out of runtime images.

Acceptance requires full latest-main baseline and candidate checks, GitHub and
OAuth/state/identity/space/retry privacy regressions, actual disposable MCP/DB
read/write/conflict/denial/index/readback tests, independent package installation,
full image/both-native CI and inspected artifacts. No Core/schema/runtime changes,
makako deployment, live reingestion or installed schedule is part of this phase.
Record completed evidence and limitations before claiming acceptance.

Implementation checkpoint: the generic package is 0.1.0 and runs independently
of Core/the application. Current focused source/client/private-job tests and
actual disposable SDK/OAuth/PostgreSQL, immutable evidence, lost-reply recovery,
conflict/Reader denial and revocation tests pass. Actual wheel and source-archive
installations outside the checkout pass. A copied existing private job validates
offline without content writes; original files remain unchanged and its dedicated
Read/Write client is approved, with one-time user login pending. No source data,
instance configuration or credentials are included in this contribution.

Exact original-main baseline `09c10d3` passes full40233296553 and independent
downloaded artifact inspection: Debian upgrade21, Rocky installation26/three
expected skips/all8 browsers, 30 accessibility contexts, three OAuth-query
artifacts with zero candidates and five scan/SBOM pairs. Local broad regressions
pass 2043 cases at preserved candidate `67c57d5` after moving disposable packaging
files out of quota-limited `/tmp`; the failed attempt is retained privately.
Final review adds opt-in Wiki publishing and receipt guards; its 75 focused cases
and two actual SDK/database cases pass, including preserved human edits. Fresh
frozen-candidate full local/CI checks and PR review remain required. These tools do not replace the
accepted runtime images or establish actual scheduled-client acceptance.

Work through these phases in order. Each phase needs observable results before it is called complete; there are no promised dates.

| Phase | Status | What people should get | Done when |
| --- | --- | --- | --- |
| Shared knowledge foundation | Implemented and accepted under development gates | Wiki, original sources/citations, structured records and graph, indexed retrieval, users/protected spaces, browser/REST/MCP and revocable OAuth | Recorded local, released-Core, image, both-native and dedicated-instance acceptance remains valid |
| 1. Make the first-use experience clear | Active documentation/skills release work, M21 | Someone can understand C0, install an instance, connect the right account, use its skills and fork it from public guidance | A fresh user completes setup, first source, cited read and authorized edit without a private maintainer runbook; packaged-skill web routes are actually exercised |
| 2. Prove the assistant workflows | Remaining release-readiness work | Repeatable use with connected clients, including unattended maintenance | Fresh scheduled read-only and read/write tests verify results after token expiry, renewal, denial and conflicts; Claude/Grok routes receive their own C0-specific tests |
| 3. Publish a release operators can trust | Gated | A clearly supported version, installation/upgrade guide and reviewed skills/packages | Required release checks pass, security findings are dispositioned, retrieval quality is measured for the claimed workload, and publication/release scope is explicitly approved |
| 4. Grow the application foundation | Later, separately planned | More domain applications, richer agent memory and optional workflow integrations | Each extension has its own scope and data/authorization/recovery acceptance; broader agent-memory work follows session-usability acceptance and Windmill follows M21 |

### What already works

- A person can read and maintain knowledge in the browser; an authorized assistant can search/read through MCP and perform explicit knowledge changes.
- Sources retain versions and extracted passages; Wiki pages retain revisions; evidence, records and graph relationships stay within their selected space.
- Verified users, Read/Write/Manage roles, protected-space grants, application approval, exact disconnect and persistent blocking are implemented.
- Text retrieval works without a model provider. Optional embeddings/scoring and a reusable Python Core support applications that need more.
- NS8 packaging, disposable tests, CI image/native checks and managed fork/Core update mechanisms are implemented.

These capabilities are available in a tested **development candidate**. They do not by themselves establish a stable module release, every client's compatibility or successful unattended agent execution.

### Next acceptance work

1. Complete the public documentation and skill walkthrough, including actual ChatGPT web package installation/account binding and the intended private/managed routes. This documentation refresh clarifies the product and fork story; it does not claim those runtime/platform gates passed.
2. Maintain the fork workflow: latest original C0 main, rebased development branches, green base tests plus retained feature regressions, tested upstream contributions and current Codex-facing plugin/connector contracts.
3. Resolve the scheduled-task execution blocker with a visible run trace or controlled reproduction. Verify a read-only run first, then one authorized Wiki update with exactly one new revision and readback. Record real errors rather than interpreting an empty completed run as success.
4. Keep the working ChatGPT connection and verify Codex independently. A 25 October operator setup proves a dedicated Codex OAuth connection with an exact loopback callback, current profile/protected Wiki reads and an administrator-only read. It does not prove Codex content writes or scheduled execution. Claude and Grok publish MCP connector routes; their C0-specific end-to-end acceptance is still pending.
5. Finish remaining model-evaluation, actual-provider retrieval-quality and security/release obligations. Runtime changes require their own full acceptance and deployment loop. Stable tagging, public plugin-directory submission and workspace-wide rollout each need explicit scope and approval.

Use [release-readiness requirements](docs/release-readiness.md) for the remaining gate definitions. Its older implementation checkpoints and unchecked historical rows must be read together with the newer accepted-runtime evidence below; they do not undo passed runtime gates. No automatic knowledge-maintenance agent or native Wiki cron handler is proposed as a substitute for testing the external assistant workflow.

## Current baseline

Accepted runtime: app **0.52.0**, released Core **0.33.0**, schema **0021**, source `e384bed641ac0bdc97212def22db521c0ab2e4c7`. Freeze its three [installed image digests](#dedicated-instance-acceptance-and-frozen-predecessor) as the next genuine upgrade predecessor. Documentation/main-marker images do not replace it.

Runtime main `05ce22c` passed full [40106287084](https://github.com/Stell0/ns8-czero/actions/runs/40106287084), canonical publication and independent actual native/privacy/scan audits. Reviewed documentation closeout PR35 merged as `f735004`; its [main40137756852](https://github.com/Stell0/ns8-czero/actions/runs/40137756852) and exact-source documentation promotion verifier pass. Original dirty checkouts, recovered M20 worktrees, drafts and immutable artifacts remain preserved.

## How development proceeds

Agree the behavior and acceptance, implement one focused change in the right layer, verify it with disposable tests, review the PR, and follow the [CI policy](docs/ci-policy.md). Runtime changes also need supported targeted deployment and live preservation/client/restart/journal acceptance before merge, then actual main publication. Internal documentation-only guidance uses its explicit lightweight checks. All external-fork contributions to original C0 main require full base and candidate checks before opening the PR, including documentation-only changes; see [contributor requirements](AGENTS.md#tests-are-part-of-the-feature). Existing interactive Playwright and CPU-quota waivers remain unchanged.

The detailed plan and evidence below preserve decisions, failures, exact sources, image identities and test results. Older “current” or “pending” wording describes its checkpoint; the baseline and roadmap above govern present work.

<details>
<summary>Detailed implementation plans and acceptance evidence</summary>


## Operator priority — people-first workspace access (24 October 2026)

## Approved people-first Workspace Access page

Status: implementation, exact-source distribution/native checks, dedicated-instance
acceptance and reviewed promotion pass. The current accepted runtime is app0.52 /
Core0.33 / schema0021 at frozen source `e384bed`; PR33 and PR34 are merged.
See the executed evidence and frozen image identities below. The following design
and preimplementation model are retained to explain the accepted behavior.

## Accepted runtime and promotion — 24 October 2026

The operator reviewed and approved PR33 followed by PR34, and separately
confirmed the existing ChatGPT web connection worked without manual reconnect
for more than 24 hours. [PR33](https://github.com/Stell0/ns8-czero/pull/33)
merged regularly as `cd17a02`; its
[main40101415111](https://github.com/Stell0/ns8-czero/actions/runs/40101415111),
canonical publication, full promotion proof and independently inspected native,
privacy and scan artifacts pass. This closes the outstanding web observation;
it does not establish scheduled-task interoperability.

The accepted application source is `e384bed641ac0bdc97212def22db521c0ab2e4c7`,
app **0.52.0**, released Core **0.33.0**, schema **0021_workspace_access**.
Its [full40093959067](https://github.com/Stell0/ns8-czero/actions/runs/40093959067)
and independent artifact audit pass: Debian genuine PR33 upgrade 21 passes,
Rocky installation 26 passes/three expected skips, eight real browser workflows
and privacy guards, 30 numeric accessibility contexts, ten independently typed
access stages, three actual query artifacts with zero candidates and five
scan/SBOM pairs. The local final released-wheel consumer run passes 1963 actual
Python/PostgreSQL/packaging cases without database skips in 600.14 seconds;
Node24 controllers pass 185, with schema/shell and 21 Robot dry runs. The native
browser results establish workflows for Reader, Editor and Admin accounts,
including administrator approval/decline, exact disconnect, persistent blocking
across repeated sign-in and actual service restart, and unblock without old-token
resurrection. Sibling/other-user controls and protected-space boundaries pass.

After PR33 merged, integration head `cc8c2cf` merged only the approved ancestry:
its entire tracked file tree equals the reviewed and deployed `e384bed` tree.
[Full40101567741](https://github.com/Stell0/ns8-czero/actions/runs/40101567741)
and independent actual artifact audit pass the same 21/26/three-skip, eight
browser/privacy, 30-accessibility and ten-stage gates. Exact current-head/base
promotion verification passes. [PR34](https://github.com/Stell0/ns8-czero/pull/34)
merged regularly as `05ce22c26055cf321e8a3d90471406dbc11e99dd`, retaining those
source commits and the identical accepted file tree.

Resulting main [40106287084](https://github.com/Stell0/ns8-czero/actions/runs/40106287084)
is completed/successful at `05ce22c`. Actual main logs confirm 1963
Python/PostgreSQL/packaging passes in 714.95 seconds, 185 controller passes with
no skips/failures and 21 Robot dry runs. Producer/released-Core builds, image
identity checks, five scan/SBOM pairs, both native distributions, artifact audit,
merge gate and canonical publication all succeed. Independent downloaded reports
confirm Debian21, Rocky26/three expected skips, all eight browser/privacy workflows,
30 numeric accessibility contexts, ten access stages and three query artifacts
with zero candidates. Exact-source promotion verification passes. Six fresh
registry reads verify all three main/latest aliases against the published source
and digests. The accepted dedicated runtime remains frozen at e384bed.

### Dedicated-instance acceptance and frozen predecessor

Only the dedicated C0 instance was updated using the supported canonical native
action after a C0-only backup and actual backup-data integrity read. Update
completion took 24.71 seconds. Readiness, the installed module/app/database
identities, route, certificate, worker and timer checks pass after update and
supported full-manager restart. Preserve this accepted installation and tag as
the next milestone's genuine upgrade predecessor:

| Image | Frozen digest |
| --- | --- |
| Module | `sha256:3e16e819787850a4a9f90016a946a3bbb71c3d8bb5073c42b22ac344df68f2fa` |
| Application | `sha256:90903768ec49e84d9439530da48864eebe1bdb9a0a5d5cee59ae64be19200d11` |
| PostgreSQL | `sha256:0907ed3c57b4d2b34d84d2a168a7718b143fd07f37b0a9048fa1a7f50aee7dbe` |

All three revisions are `e384bed641ac0bdc97212def22db521c0ab2e4c7`; the canonical
candidate tag is `ci-e384bed641ac0bdc97212def22db521c0ab2e4c7-40093959067-1`.
Keep that tag available and unchanged while the installation references it.
Integration, main and documentation publications do not replace this accepted
runtime. Public examples use `https://c0.example.org`; private deployment
identities, credentials, raw journals and evidence stay outside Git.

Independent before/update/restart/final observers preserve all 40 original domain
tables and 247 original stable rows, existing column values, settings, mounts,
authentication/retrieval configuration, schedules, terminal jobs/attempts and all
nine unrelated instances, including each exact C0 action window. The additive
migration introduces only two columns, no new table. Original stored files and
active Shared Wiki/source lists are empty: metadata reads prove authenticated
access, without a claim of nonempty retained content evidence. One existing
background grant retains its fixed authority while normal activity and refresh
generation advance. No real user's permissions, block or application approval
was changed for live testing.

Live signed-in owner/browser, authenticated REST and current/legacy SDK profile
and repeated explicit-space Wiki/source list reads pass after update and manager
restart. Isolated owned grants prove exact disconnect: target access401 and
refresh400, sibling access200 and rotating refresh200; membership and client
approval remain unchanged. Both temporary read-only manual clients were disabled,
all their grants reject access and the owned browser session was logged out.
No fixture content or schedule was created live; destructive recovery and other
role browser workflows remain disposable.

The existing connected-tool path works without manual reconnect across a
measured 627-second window and the update/restart. A read-only server observer
separately proves two public refresh generations on the same original background
grant and native authority, with last use beyond the previously observed access
deadline; it does not inspect the user's raw credentials. This is distinguished
from the operator's separate more-than-24-hour ChatGPT web observation.

Bounded root application journals use the verified module UID and container:
90 entries from 13:40:45–13:47:50 UTC after update and 93 entries from
13:52:23–13:55:28 UTC after restart. Both windows have positive health, owner
profile, guide, authorization, token and MCP request controls. Actual OAuth query,
known-issued-secret, generic credential, JWT and traceback candidate counts are
all zero. Empty Podman logs are not used as evidence; host logging is unchanged.

The access-page implementation and persistent-connection observation are
accepted. This separate three-document closeout requires its own lightweight PR
and main gate and independent review. It changes no package or runtime input and
must not replace the accepted installation. Existing interactive Playwright and
CPU-quota waivers remain unchanged. M21 packaged-skill web use, quota-blocked
model evaluations, actual scheduled-client interoperability and vendor findings
remain separate release-readiness work. No stable module release is claimed.

## Existing model

This is the inspected preimplementation model; the settled interfaces and accepted
runtime above supersede its missing-API statements.

- AccessService owns persisted application roles, verified identity display metadata and explicit account blocks. Verified new users receive Shared Reader admission in the application. A block survives renewed/renamed sign-ins. The configured owner is always Admin and cannot be changed/blocked through this service.
- set_role invalidates every OAuth grant and native authority for the target, even on a same-role call. The UI must skip unchanged saves and warn before real role changes. Regrant does not restore old credentials.
- ClientOnboardingService holds bounded, signed-in, five-minute requests. Its current admin DTO has username/metadata URL/callback/scopes/approval, but no account ID, full name or safe action handle. There is no Decline operation.
- CimdClientService performs reviewed exact-metadata/client approval with digest and revision checks. Approval is application-wide for that exact client identity; it is not a user role or consent grant. Reapproval can invalidate that application's connections for other users. Existing UUID clients remain independent.
- OAuthGrantService exposes only first-party own-account connection listing and disconnect. It cannot currently list/disconnect another user's individual connection as an administrator.
- OAuth scopes are independent: c0:admin does not imply c0:read or c0:write. Protected-space grants further cap Reader/Editor access; application Admin has implicit access to all spaces.

## Proposed presentation

/admin becomes Workspace access. A pending-request count and jump link precede one main table: Username | Full name | Read | Write | Manage | Status | Actions. Group rows by stable account identity. People with actionable pending requests sort first, then other people by username; each person has a primary row, followed by relevant application/request/connection rows. Show application name beneath the username on those rows. Never merge client identities merely because names match. Unknown/unreviewed application names display Application awaiting review with a hostname as an origin cue, without fetching remote assets. Verified metadata review supplies the name.

Primary person permissions represent current workspace role: Reader=yes/no/no; Editor=yes/yes/no; Admin=yes/yes/yes; Blocked=no/no/no. An explicit Change permissions control offers these three presets rather than implying unsupported arbitrary combinations. The owner is labelled Owner with locked controls. Full name is verified display metadata, with an em dash when absent; it never determines identity or authority.

Application rows distinguish Requested, Consented and Effective using literal labels in each relevant permission cell. A pending request has no effective connection access. A connection's effective capability requires its consented scope AND current application role, and remains subject to the selected space; display a persistent note that the table is workspace-level and protected spaces need separate grants. Never infer broader scopes from Manage. Do not claim provider availability from saved connection metadata.

| Row/state | Meaning | Available actions |
| --- | --- | --- |
| Person: Access enabled | Current Reader/Editor/Admin membership, no statement about an application connection | Change permissions; Block user; Details |
| Person: Owner | Configured immutable application owner | Details |
| Person: Blocked | Persisted account block; no effective access | Unblock user (explicit role selection); Details |
| Person: No access | No membership and no explicit block, if a closed-admission Core consumer produces this state | Grant permissions; Block user; Details |
| Application request: Needs application approval | Exact client/callback not approved | Approve; Decline; Details |
| Application request: Needs additional application permissions | Client approved but requested scopes exceed its approval | Approve; Decline; Details |
| Application request: Waiting for user consent | Current exact application/callback/scopes approved; no matching consented connection yet | Details; dismiss the still-pending handoff through Decline if needed |
| Application connection: Connected | Locally valid, consented grant; show last use and session/background label | Disconnect application connection; Details |
| Application connection: Needs reconnect | Revoked, expired, policy-invalid or unavailable authority observed during this page session | Details; reconnect guidance; no fabricated durable history |

An expired/declined/disconnected request or grant disappears from refreshed active rows, with a clear action confirmation. Do not invent a permanent disconnected/declined audit ledger where none exists. If a person has both a usable connection and a request for additional permissions, show both so the pending request does not imply that current access stopped. Blocked users' stale requests cannot be approved to bypass the block.

Technical IDs, metadata URLs, callbacks, exact scope names, revisions and timestamps live in Details/Advanced; required application-origin and approval-impact information remains visible in the approval review. Advanced contains manual client configuration, metadata diagnostics and explicitly global Enable/Disable application controls. Protected-space management remains a separate clearly linked page. Jobs and schedules move to a separate Background work page; none are loaded by the access page.

## Action semantics

- Approve opens a focused review with verified application name/origin, requested permissions, current user permissions, selected application permission ceiling and affected-user warning if updating an existing approval. Preserve preview/digest/revision checks, current policy, exact callbacks and post-I/O authorization checks. Approval changes only the exact application approval. It never changes membership, issues tokens, adds scopes to existing tokens, grants protected spaces or automatically approves a blocked person. Preserve earlier approved scopes unless the administrator explicitly edits the application-wide ceiling under Advanced. The requester must continue and explicitly consent. If requested Write/Manage exceeds their role, offer a separate Change permissions action; never silently combine them.
- Decline cancels only that exact browser-bound pending handoff, after current Admin authorization and CSRF. It does not block the user, disable the application, disconnect an existing connection or prevent a fresh request. A stale/expired request returns a safe refresh-required result. The requester's existing handoff cannot continue after decline.
- Change permissions changes the person's application Reader/Editor/Admin role through AccessService. Warn that it invalidates all that person's application connections and requires sign-in/consent again. Manage additionally grants application-wide administration and implicit access to every protected space. Unchanged saves do nothing. Use optimistic state checks to reject stale saves.
- Disconnect application connection deletes only the selected user's exact grant, invalidating its access/refresh credentials. Keep membership, other grants including the same app's separate grants, app approval and space grants. Allow fresh consent later. Do not revoke shared native authority and accidentally break sibling connections.
- Block user persists the existing explicit block and invalidates all target authority through AccessService. It cannot block the configured owner. Repeated provider sign-in cannot restore admission. Unblock explicitly selects a role and does not restore old connections. Existing protected-space grants retain their current stored policy.
- Disable application is an Advanced, explicitly global action, distinct from user blocking and per-connection disconnect; enabling later requires fresh consent and does not revive old grants. No action uses the label Revoke.

## Missing API support and proposed additions

1. Extend the Admin account read DTO with explicit block state and a version/state precondition; bound and paginate rather than silently omit people beyond the current default 100. Keep current services and role/scope checks. Add an optional expected-state precondition to role writes without breaking existing callers.
2. Extend the Admin request DTO with stable account ID, full name, safe opaque request action handle, current role/block state and explicit application approval state. Add a narrow Admin decline method/HTTP endpoint which cancels only that handoff. Do not expose its cookie binding, raw hash, state, PKCE challenge or credentials. A safe handle implementation and any additive persistence requirements must be settled before coding.
3. Add bounded, first-party Admin connection reads and exact targeted disconnect, reusing OAuthGrantService locking/revocation checks. Return only safe grant summaries, account/client identities, actual scopes and validity/last-use metadata. Existing own-account endpoints keep their behavior; these additions do not automatically become MCP tools. Guard targets by issuer/native client/resource and current persisted Admin authority, with browser Origin/CSRF on writes.
4. Use existing CIMD preview/approve and manual client APIs, not a new approval engine. Bind any request shortcut to a live request plus verified metadata and expected revision so a stale request cannot broaden approval silently. Clearly report reapproval impact. Do not auto-approve requested Manage or automatically modify roles.
5. Compose the page from trusted Core summaries; do not implement authorization with browser-only joins. Apply existing lock ordering, transaction rechecks, bounded queries and response-generation/access-loss guards. Concurrent decline/continue, role edits, disconnect/refresh and block/sign-in require one consistent outcome. Audit existing native credential/session validity semantics before choosing the Connected DTO predicate.

## Implementation and acceptance after agreement

Create a dedicated feature worktree; record the final plan in PLAN.md before coding. Reusable read/decline/admin-disconnect/precondition behavior belongs in Core, HTTP/UI in app; no ns8-idp changes. Publish immutable Core only after exact-source local/package/native gates, then pin app dependency/lock and rerun consumer gates. Any required migration is additive and must preserve old identities, grants, blocks, history and settings.

Update README, AGENTS, administrator/user guides and interface documentation. Remove duplicate Admin membership editors from Account or replace them with a link to Workspace access, while preserving ordinary users' own connected-app controls.

Verify real disposable Reader, Editor and Admin browser workflows over native SSO/HTTPS: default Shared Reader; pending approval and decline; independent role elevation versus application approval and explicit consent; read-only token remains read-only after role/approval changes; independent manage-only scopes; exact per-grant disconnect with sibling/other-user positive controls; persistent block across repeated login and restart; explicit unblock without token resurrection; owner protection; Shared/protected-space boundaries; global client-disable distinction; pagination/stale responses/stale saves/CSRF; no jobs/schedules requests from access page; keyboard/accessibility and actual privacy artifacts. Run focused PostgreSQL/HTTP/UI checks then full packaging/JS/schema/shell/both native CI and actual report audits. Existing interactive Playwright and CPU-quota waivers remain unchanged. Supported dedicated-instance deployment/live acceptance follows reviewable exact CI images and preserves unrelated modules and the working connection candidate. No destructive recovery runs live.

## Implementation checkpoint — 24 October

Core0.33/schema0021 is published from immutable source
`ec2ac4f263a4736a6426c671a0353a4e764509f8`. Its exact
[full40082329366](https://github.com/Stell0/ns8-czero/actions/runs/40082329366)
and promotion verifier pass:1936 actual Python/PostgreSQL/packaging cases without
skips, Debian genuine upgrade21, Rocky installation26/three expected skips,
eight real browser workflows/privacy guards,28 numeric accessibility contexts,
three inspected OAuth-query artifacts with zero candidates and five actual
scan/SBOM pairs. [Publisher40086544147](https://github.com/Stell0/ns8-czero/actions/runs/40086544147)
completes successfully. Downloaded immutable
[core-v0.33.0 assets](https://github.com/Stell0/ns8-czero/releases/tag/core-v0.33.0)
match checksums and every Core Python byte matches the verified source:
wheel SHA256 `61ccec3abce4216e663251d4502723c02b2819e9e919526e9735fc060bdf8777`,
archive `13759f5af182819e7b0bc1cc889f89df8e880ad48b57e8e1fa0330219b078c9d`.
Both supplied distributions install independently and expose the new service
outside the source tree, without application/NS8 dependencies. Do not replace
these artifacts. These native results precede the new application UI.

Retained earlier failures are resolved: c01f013 found one genuine schema0015
legacy account-list regression (1933 passes/one failure);999aada preserves that
old query and passes1934. Source d6cc0e3 corrects in-progress provider-check
status and passes1935 locally, but its native40079749606 has one asynchronous
protected-space UI synchronization failure; it is not accepted. The final app
waits for the exact selected space before its assertions. Core ec2ac4f also
preserves the existing configured-owner override when schema0019 left an old
block marker, without deleting data or changing grants. Its local whole run
has1935 passes/one five-second statement-timeout setup error under host load;
the affected24-case SDK group reruns successfully and the exact CI1936-case
whole matrix passes. Keep failed private evidence; never present failed runs
as whole-suite passes.

Application0.52 pins the released Core0.33 tag and immutable source in its lock.
It implements the approved table, browser-only access API and separate
Advanced/Protected spaces/Background work surfaces. Legacy mounts retain
first-party access controls without mounting or advertising OAuth/MCP. The
earlier draft whole matrix passes1936 without skips; later focused transport,
native and consumer checks pass, and current Node24 controllers pass178.
The final whole consumer matrix against the actual published wheel passes1959
without skips in651.65s; current controller checks pass178. Schema
compilation, individually parsed shell inputs and21 Robot dry runs pass; dry
runs are not native browser acceptance.

Final native tests freeze all three genuine installed PR33 source4d61cf2
images, app0.51/Core0.32/schema0020, in upgrade_predecessor.json and Robot.
They require exact existing background grant/token/code rows, successful
rotating refresh and a delegated profile read after upgrade, followed by
isolated client/provider cleanup. Artifact audits additionally require ten
independent measured access stages: actual approval and decline, one-connection
disconnect with sibling/other-user controls, persistent blocking across two
sign-ins and an observed native service restart, unblocking without old-token
revival, and Reader/Editor/Admin browser permission changes. The two new fixture
and audit dependencies are explicitly registered for managed consumer delivery.
This was the pre-acceptance checkpoint; final native and live results are recorded above.

Production MetadataFetcher fetches the fixed public JSON example through real
public DNS/TLS/MIME validation, digest
`8f2cafd1a4bfd3c7469bd0f9f59c0c5281c4c26464966ec36c7a43d161337d5b`.
Keep test-workspace-client-v1 at9fc9594 unchanged. No security-policy weakening
was introduced. This historical checkpoint preceded the accepted exact-source
CI, native, dedicated update/live and reviewed promotion results recorded above.

### Native findings and corrections

The first application full run
[40088486541](https://github.com/Stell0/ns8-czero/actions/runs/40088486541)
at71b3d96 is unaccepted: actual Debian genuine predecessor upgrade21 passes;
Rocky installation24 passes/two failures/three expected skips. All ten measured
people-access phases pass independent strict grading, including approval,
exact decline/disconnect, persistent block across renewed sign-in and an
observed service restart, unblock without old-token revival and all three
permission presets. Three actual XML/browser-log query artifacts contain zero
OAuth-query candidates. Passing those stages does not establish full acceptance.

The subsequent Advanced check fails because the new browser fixture leaves
discovery enabled before the original disabled-policy check. Source45f9163
restores the original boolean in finally on both success and failure. Two
forced-browser-stop regressions and39 existing focused cases pass; its complete
released-Core matrix passes1961 without skips in609.86s and21 Robot dry runs
pass. Its completed [full40091589934](https://github.com/Stell0/ns8-czero/actions/runs/40091589934)
remains failed: Debian21 passes, Rocky25 passes/one skip-target failure/three
expected skips, with three query artifacts containing zero candidates.

A separate protected-space failure is the actual numeric accessibility guard:
missing_skip_target=1. A subpage base URI plus space-link rewriting can send the
skip link to another document. The correction preserves the current document,
selected-space query and legacy prefix in shared navigation. The probe now
checks the resolved origin/path/query/fragment target instead of only the raw
fragment attribute. It rejects both another page and another space. Actual
native Tab/Enter/focus checks cover Advanced, Background work and Protected
spaces, preserving the existing ordinary-page keyboard check. Current Node24
checks pass185, focused Python43 and21 Robot dry runs pass; the complete
released-Core matrix passes1963 without skips in600.14s. Fresh
exact-source full/image/native acceptance followed at e384bed, as recorded
above. Neither older candidate was deployed or merged. Core0.33 artifacts remain
immutable; the accepted installation is now the corrected e384bed runtime.

## Settled implementation interfaces

Core 0.33 / schema0021 adds c0_accounts.access_revision (monotonic bigint) and a separate random UUID c0_client_onboarding.id. Neither is authority. AccessService keeps legacy set_role behavior; optional expected_revision rejects stale edits and skips unchanged UI saves. WorkspaceAccessService(grants) supplies first-party Admin summaries, bounded account pages (25, max100), per-person request/connection pages (10, max50), request-bound preview/approval and decline, and exact per-grant disconnect. All pages report has_more. Reads expose locally observed connection state only; stale provider verification is renewal_required, not a false assertion of successful access or permanent disconnection. No provider network call occurs in overview transactions. Existing application/client scope contracts remain unchanged.

Routes: GET /api/v1/access/workspace?offset=&limit=; GET /api/v1/access/accounts/{id}/applications?offset=&limit=; POST /api/v1/access/requests/{id}/preview; POST /api/v1/access/requests/{id}/approve; DELETE /api/v1/access/requests/{id}; DELETE /api/v1/access/connections/{id}. Existing PUT account role gains optional expected_revision. The request approval reuses CimdService's same transaction implementation, verifies the still-live request and account after I/O, preserves existing approved scopes and rejects disabled clients. Approval of a blocked account fails. No new MCP tool or discovery default is added.

UI routes: /admin (access), /admin/advanced (technical client controls), /admin/spaces, /admin/work (jobs/schedules). Preserve existing manual client and space/task controllers on their separate surfaces. Account links to Workspace access instead of duplicating role edits; self-service connection controls remain unchanged. App adoption follows verified immutable Core publication, not an unreviewed dependency replacement. PR33 was kept frozen and merged first; PR34 then passed its own current-head gates and merged.


---

## Earlier roadmap checkpoint

The sections below retain the earlier plan and observations. Their pending/current
installation statements are historical; the accepted-runtime section above is
authoritative for PR33/PR34 and the installed predecessor. Other M21 release gates
remain open as explicitly stated.

## Operator priority — persistent OAuth connections (23 October 2026)

The operator authorizes unattended ChatGPT maintenance connections after reviewing token lifetime and revocation tradeoffs. Keep five-minute access tokens and rotating refresh credentials; new explicitly consented background connections have a thirty-day inactivity deadline and no fixed maximum lifetime. Normal browser sessions retain their current bounds. Existing grants are never silently upgraded. Scheduling or running knowledge maintenance is outside this implementation; actual multi-day ChatGPT scheduling remains acceptance work.

**Entry and preservation:** PR32 is merged as `d4a97349e8e7aa83789b82a78eccbc075c754e84`, with the tested/deployed `fa64f3d390a9514d751c33e5ab4a5a941193ab78` tree. Its [main39933530291](https://github.com/Stell0/ns8-czero/actions/runs/39933530291), publication, actual downloaded native/privacy/scan artifacts and full promotion verifier are completed/successful. Sourcefa64 full39777449607 and independently downloaded native/privacy/scan artifacts pass: Debian upgrade21, Rocky installation26/three expected skips, eight browsers/privacy guards,25 accessibility contexts and zero query candidates. The supported dedicated update/restart and original data/settings/schedules/nine-unrelated-instances/root-journal checks pass. Real connection/read succeeds by operator report; packaged-skill use and seven quota-blocked model cases remain incomplete. Preserve PR32, all prior worktrees and the installed candidate images; do not substitute documentation images or claim M21 release acceptance.

Frozen installed predecessor: `fa64f3d390a9514d751c33e5ab4a5a941193ab78`, canonical tag `ci-fa64f3d390a9514d751c33e5ab4a5a941193ab78-39777449607-1`, app0.50.0/Core0.31.1/schema0019.

| Image | Installed digest |
| --- | --- |
| module | `sha256:acdd8f9b06b3cb0fd9ce8f45367ddf4aba26bf6a5a7f51d423b0e904642604c5` |
| app | `sha256:0273abd79473dadc2b106f5d4d32e0471c29729c78c6f4d3d6c4763a1b818ed1` |
| postgres | `sha256:80d8f51e603f6ba59d300d94a3d9b2e725f3a3f699c44bd4981170c58ead4bf2` |

**Verified provider prerequisite:** A private real-HTTPS probe using only the existing dedicated C0 client obtained `offline_access`, verified the same identity, refreshed successfully after logging out its own provider session, revoked its offline credentials and required refresh rejection. No provider configuration, account role, application content or client registration changed. No ns8-idp or NS8 platform Core change is currently required. Keep raw authorization data and evidence outside Git.

**Settled implementation:**

- Core0.32/schema0020 introduces an opt-in background-connection policy and explicit persisted authority kind. Interactive authority remains bounded; background authority requires provider-attested offline credentials, current roles and thirty-day inactivity. Browser cookies remain bounded even when they reference offline authority. New background consent requires same-origin CSRF, a valid pending OAuth request and fresh same-account native SSO; login purpose/expected identity are bound to one-use persisted login state.
- Persistent grants have explicit kind, activity/idle deadline and revocation semantics, independent of the browser expiry. Bind the same issuer, native client, approved client revision, exact resource and actual consented scopes. Keep current membership/space checks inside operations. Browser logout retains explicitly approved background grants; per-connection disconnect, client/account revocation and provider rejection deny subsequent use. Provider outages confer no new authority and retain retryable credentials only after a definite retryable outcome.
- Persistent refresh credentials remain opaque 43-character values. A domain-separated keyed family/generation authenticator permits issued-old-token replay detection with bounded storage, replacing the finite rotation-history cap only for new persistent grants. Preserve legacy tokens and loaders; authenticate replay before SDK scope validation, commit family revocation, serialize rotations and reject fabricated/future/wrong-client credentials without revoking another family. Refresh never adds scopes. Code/state/consent and access-token expiry stay short.
- Add migration fields without changing old grant/session lifetimes. New Core DTO/SDK adapters handle persistent authority while access-token expiry remains finite. Restores/native client or secret replacement must reject old authority. Native settings expose the optional background policy; application consent and account connection controls explain lifetime, last use and disconnect. Plain readers fetch no Admin lists.
- Reusable provider/authority/grant behavior belongs in Core; HTTP, cookies and UI in the app; NS8 settings and lifecycle in numbered scripts. Publish immutable verified Core artifacts before final released-consumer adoption. The feature starts on an isolated branch, preserving the merged onboarding source and all unfinished work.

**Validation and acceptance:** focused PostgreSQL migration, same-account offline login, current-role/revocation, expiry/idle extension, rotation/replay/concurrency, wrong binding, provider outage/recovery, browser logout versus disconnect, bounded history and old-client regressions; then full Python/PostgreSQL/packaging, JavaScript, schema/shell/Robot and exact-source producer/released-Core/both-native artifact gates. Use frozen deployedfa64 image identities for genuine upgrades. Only after those pass perform a supported C0-only checked backup/update, readiness, original knowledge/files/settings/clients/schedules/unrelated inventory, restart and bounded positive-control journal audit. Actual ChatGPT consent/write/readback and consecutive nightly runs beyond24hours without fresh login are required; revocation must stop the next run. No model quota bypass, new schedule, stable release or unrelated IdP change is authorized. Existing waivers remain unchanged.

**Verified Core publication:** Source `22d813409b820958845b8b7b7493284a3012c92a` passes 1862 actual local Python/PostgreSQL/packaging cases without skips and [full 39964867651](https://github.com/Stell0/ns8-czero/actions/runs/39964867651). Independently downloaded reports verify Debian genuine predecessor upgrade 21, Rocky installation 26/three expected skips, eight browsers/privacy guards, 25 accessibility contexts, three OAuth-query artifacts with zero candidates and five actual scan/SBOM pairs. The full promotion verifier passes. [Core publication 39972262492](https://github.com/Stell0/ns8-czero/actions/runs/39972262492) completes successfully at that exact source; downloaded `core-v0.32.0` assets match SHA256SUMS: wheel `eb48289106d987ad2672fd93da3407ab566be972ba8ebfaf09611252c723f6a1`, archive `79cba3df87877f543a6939faa7e57cd17eb5684a1be0379a6204a67bfcfd6bfe`. Both contain schema 0020. This publication does not establish application or live acceptance.

The genuine 0019 migration preserves original columns, ciphertext and bounded grants. Controlled-clock PostgreSQL cases exercise a year of daily use, 2050 rotations with two current token rows, separate browser idle/absolute bounds, provider outage/recovery and replay revocation. The old source fails both access-activity/refresh-deadline boundary controls; the correction extends only the current unconsumed refresh credential with authenticated activity. No absolute connection lifetime is imposed on explicit background grants.

**Retained failures and corrections:** Core 2668b2d/full 39952548426 fails Debian predecessor setup because the profile fixture expected closed admission although frozen fa64 admits verified Readers; later failures cascade and CI cancels Rocky. The corrected 4e75484/full 39958341465 completes successfully with audited native artifacts but is superseded by the refresh-deadline correction above. Its interrupted local rerun is not counted as a pass. A failed local run caused by temporary-directory quota is retained privately; rerunning the final frozen source with an isolated workspace temporary directory yields the 1862-pass result. No agent cancellation or failed-candidate deployment occurred.

**Application adoption:** Application 0.51.0 pins the published `core-v0.32.0` source and lock, with compatible range >=0.32.0,<0.33.0. Explicit optional background consent binds one-use same-account offline login; a verified active offline session may be reused before final explicit approval. First-party Account controls list only the user's connections and disconnect with same-origin CSRF. NS8 settings expose whole-day inactivity of 1–365 days, default 30, for new connections, preserve it through update/restore and leave browser policy unchanged. Native disposable acceptance now requires measured 120-second browser expiry with subsequent background refresh, actual read/write SDK, replay/disconnect/provider revocation, and persistent grant/policy recovery across update and clean restore. Those new native checks are pending; the Core bridge native run did not exercise the new application. The initial adoption run passes 1907 cases and fails only three version-consistency assertions: the runtime constant still reported0.50 while package metadata reported0.51. The constant is corrected and all120 application cases pass; a clean full rerun of the frozen final candidate is required. Focused app checks pass 691, additional native-helper/HTTP checks 162, UI 165 and immutable administration build; final full released-consumer/image/both-native validation is required before deployment. The dedicated installation remains unchanged.

**Application policy correction:** Frozen `bc59aabb7662af1c7fa82d4a6cd5db6df3666fc5` passes all1910 local Python/PostgreSQL/packaging cases without skips and is submitted as PR33/full39976845841. Its image, released-Core, runtime, versioning, scans and CI local checks pass while native runs continue. Subsequent review reproduces four failures: new consent could reuse an older offline sign-in after the administrator shortened or lengthened the new-connection inactivity setting. This candidate is not authorized for deployment even if its earlier acceptance suite completes successfully; keep its evidence and let the frozen run finish.

The application now reuses offline sign-in only when its saved limit matches the current setting, and rejects direct consent under a mismatched limit. Fresh same-account sign-in applies the new setting; existing grants keep their snapshots and continue renewing. Focused signed-provider HTTP checks pass26 cases, including all four corrected negative controls. Native acceptance additionally changes the actual setting, rejects old-policy consent, completes fresh offline sign-in, renews both old/new grants and restores settings while revoking owned credentials. This is application configuration/consent selection; Core0.32/schema0020 and its published package bytes remain unchanged. Fresh full local/image/both-native acceptance is required for the correction before any live update.

The completed first application run39976845841 fails actual Debian20 passes/one failure and Rocky24 passes/three expected skips/two failures. Both fail the exact knowledge change observer after the new recovery SDK made successful content mutations between frozen checkpoints. Rocky then observes the temporary seven-day setting because restore verification stopped before cleanup; its consent-help check correctly rejects that state. The standalone measured background browser/logout/refresh/read-write/replay/disconnect proof and recovery seed/update execute, but clean-restore acceptance is incomplete. Downloaded failed XML/browser logs are retained privately; all three actual query artifacts have zero OAuth-query candidates, including refresh tokens. The installation is unchanged.

The correction retains the exact observer. Recovery SDK checks both protocol modes, verifies reads and requires an authorized stale-revision write to return a conflict rather than a scope denial, comparing the complete bounded knowledge history and retained page before/after. Successful write/readback/archive remains mandatory in the separate standalone probe. Focused actual SDK positive/read-only negative controls pass; the complete correction selection passes146 PostgreSQL/HTTP/native-wrapper cases. The private operational helper also passes four signed HTTP/SQL checks, including the exact native policy-change helper; these controlled tests do not establish installed provider acceptance. Artifact/browser guards now also reject refresh-token query diagnostics. Fresh full exact-source local and CI/native runs remain required.

Corrected source `2adc9a91d2c3739c3a16616846f232c8abbe9abb` passes1919 local Python/PostgreSQL/packaging cases without skips,165 JavaScript cases, schema/shell checks,21 Robot dry-run cases and independent released-Core installation/source verification. Full39988063836 passes local/image/runtime/released-Core/scan jobs and actual Debian upgrade21, including new-policy consent and unchanged knowledge history across update/restore. Rocky reaches the shared runner's sixty-minute job limit after slow environment setup; its report is truncated before all browser workflows complete. This cancelled run is incomplete acceptance, never a deployment authorization. Keep its downloaded diagnostics privately. The supported shared-workflow timeout input is now ninety minutes for each native distribution; retain all suite assertions, application bounds and existing waivers, and require fresh exact-source full acceptance.

Source24d0d6c/full39997306298 passes1919 CI Python/PostgreSQL/packaging cases and actual Debian21. Rocky completes25 passes/three expected skips with one OAuth-browser failure. Admin consent, background access and Account disconnect pass, but the next Reader case requests the identical client descriptor after Admin cleanup disabled it. Registration correctly returns the disabled idempotent result and authorization correctly fails. The new signed HTTP/PostgreSQL regression reproduces that exact cleanup/reuse failure. Each disposable browser case now uses a distinct hostile-text client name, retains explicit cleanup, and verifies that earlier disabled clients stay disabled. Product/Core behavior is unchanged. Preserve the failed reports; require fresh exact-source full/native acceptance before deployment.

Source233f64d/full40005084606 passes1920 CI Python/PostgreSQL/packaging cases, Debian21 and all eight actual Rocky browser workflows, including Admin/Reader/Editor consent and Account disconnect. Rocky's combined native SSO case reaches its20-minute aggregate timeout during the required second protocol pass: provisioning takes159 seconds, the first complete SSO/renewal/offline/background sequence792 seconds, and the repeat is interrupted after226 seconds. All first-pass measurements are valid, including338-second renewal and179-second background/browser-expiry checks. The suite wrapper's successful shell step is not the Robot verdict; the completed native job/report fails and this candidate is not deployable. The SSO aggregate budget becomes30 minutes, retaining every assertion, repeat, individual SSH/probe deadline and application lifetime. Fresh exact-source full/native gates remain required.

The local source233f64d matrix covers1914 main Python/PostgreSQL cases and six fresh packaging cases without skips. Two whole runs retain artifact-install setup errors caused by slow dependency downloads (1918 passes/two errors and1916 passes/four errors); a checksum-verified public dependency wheelhouse, excluding Core itself, lets all six unchanged packaging/rebuild/install/migration checks pass offline in14.73 seconds. Core is still built from the frozen checkout. These are a combined local matrix, not a single clean whole local invocation; actual CI completes all1920 in one run. Preserve failures and private evidence, and keep the installation unchanged until the final candidate passes.

## Current checkpoint

23 October 2026: PR32 self-service onboarding is merged as `d4a9734` and its actual main CI/publication and downloaded native/privacy/scan artifacts pass. The dedicated instance runs tested `fa64f3d`, app0.50.0/Core0.31.1/schema0019, after the supported update and preservation/restart/journal gates. The operator confirms actual ChatGPT connection/read. Persistent OAuth development is the current authorized priority above; actual packaged-skill use and remaining model cases stay incomplete.

Historical M00–M20, Agent Memory AM0–AM6, failures, observations, measured limits and exact CI/source identities are retained in the [archived plan](docs/history/PLAN.md). Historical status statements do not reopen accepted work. The original root checkout's dirty documents and recovered M20 worktrees remain untouched.

## Current installed runtime

Source `fa64f3d390a9514d751c33e5ab4a5a941193ab78`, canonical tag `ci-fa64f3d390a9514d751c33e5ab4a5a941193ab78-39777449607-1`, app0.50.0/Core0.31.1/schema0019. The priority section above freezes all three installed digests. Do not replace these images with documentation/main-marker builds. Earlier self-service and clean-start checkpoints below are historical; the accepted M19 source and immutable Core0.31.0 artifacts remain in the [historical evidence](docs/history/PLAN.md#m19-deployed-acceptance-and-main-closeout--21-october-2026).

## Delivery loop

Follow [CI policy](docs/ci-policy.md) and [development guidance](docs/development.md). Settle decisions, implement one milestone, run local disposable tests, open a reviewed PR, require full exact-source runtime/image/both-native/audited artifacts, deploy only to the authorized dedicated C0 instance through supported native actions, complete live acceptance, regularly merge and verify actual main publication. Record final evidence on a separate closeout branch. Documentation-only closeouts use their explicit light checks and preserve runtime images.

The existing interactive Playwright and CPU-quota waivers remain. No stable NS8 module release is claimed. Vendor findings, real-provider quality and deployment-specific IdP/proxy/log policy are distinct maintenance/release work.

## M21 — Documentation and skills release readiness

**Authorization and entry:** The operator approves the settled plan, including
repository plus Use with AI cleanup, per-instance end-user plugin bundles, actual
packaged skills on ChatGPT web, individual/private and managed-workspace routes,
and ready artifacts/guides without public-directory submission or module tagging.
Use the verified M19 completion marker; preserve the accepted38a8654 installation,
all original drafts and waivers. Windmill remains separate.

**Implementation decisions:** Keep README a short product/quickstart entry;
separate user/operator/contributor guides. Keep AGENTS current and PLAN focused
on status/roadmap; archive historical evidence with repaired links/compatibility
anchors and sanitized deployment details. Preserve public source/CI references.
Update the five existing developer skills and required upstream-managed references.
Align installed Use with AI with staged Admin/user CIMD onboarding and current
session/role/space/citation/upload/retry behavior. Core/schema/OAuth remain intact;
installed presentation changes use an app patch version and unchanged dependencies.

Package three instruction skills: setup, cited research and explicit knowledge
maintenance. An offline generator accepts the operator's canonical HTTPS MCP URL,
registered ChatGPT app ID, plugin name and output location; emits a deterministic
versioned directory/ZIP/checksums/marketplace; rejects unsafe inputs/existing
outputs and never publishes or collects credentials. Web packages reference the
existing app via `.app.json`, without inline MCP server declarations that make
GitHub-imported plugins Desktop only. Prove private Plugin Creator setup from the
packaged files plus correct app binding and managed GitHub marketplace import.
Required workspace/account features are explicit prerequisites; absence is an
incomplete gate, never a desktop/SDK substitution or release-ready claim.

**Acceptance:** Validate maintained file/anchor links, safe examples/current facts,
all skill metadata/references/license/manifests, deterministic archives and two
instance bindings. Exercise documented commands in disposable environments and
independent actual MCP/database skill scenarios: cited reads, ambiguity/denial,
untrusted retrieved instructions, sanitized ingestion, conflicts/uncertain retries
and read-back. Require a cold-start tester using only guides/package. Actual
ChatGPT web must prove packaged skill activation/app/account/citations, authorized
controlled edit, Reader denial, renewal/reconnect/revocation on both supported
routes. Run full exact-source/released-Core/image/both-native/artifact checks for
the installed-guide change, all8 browsers and the usual reviewed deployment,
regular merge/main publication/separate closeout loop. Explicitly reviewed doc
paths may use lightweight checks; executable plugin packaging inputs cannot.
No stable release, public listing or workspace-wide rollout is claimed by M21.


### Implementation checklist

- [x] Verify reviewed M19 closeout main marker; base M21 on it without losing drafts.
- [x] Reorganize root/user/admin/developer/reference docs, archive evidence and preserve old anchors.
- [x] Maintain five developer skills and explicitly registered reusable references.
- [x] Implement three end-user skills and deterministic per-instance web package generation.
- [x] Align installed guide at app0.49.1 with Core0.31.0/schema0018 unchanged.
- [ ] Pass meaningful package/link/schema/skill checks, cold-start and independent model/MCP/database scenarios.
- [ ] Pass exact local, released-Core, images, both native distributions and actual artifact audits.
- [ ] Prove both actual ChatGPT web installation routes and their account/space/read/write/denial/session/revocation acceptance.
- [ ] Complete C0-only deployment preservation/journal gates, human review, regular merge and main publication.
- [ ] Complete separate checked documentation closeout; freeze accepted runtime as next predecessor.

See [release-readiness evidence](docs/release-readiness.md). Incomplete web or operator prerequisites are recorded as pending, never inferred from a generated package.

## Later phases

Windmill integration follows separately after M21 acceptance. Public plugin-directory submission, stable module release and workspace-wide rollout each require their own scope and acceptance; this phase does not perform them.

### M21 implementation checkpoint — 21 October 2026

The guides, historical archives/legacy anchors, five developer skills and managed fork reference, three end-user skills, offline per-instance packager and installed Use with AI update are implemented. App0.49.1 changes presentation only; Core0.31.0/schema0018 and all dependency bytes remain unchanged. Native genuine-upgrade inputs freeze the accepted M19 trio. Plugin inputs remain full-validation material; only the explicit reviewed Git-only guidance paths receive the docs exemption.

The full local development suite passes1733 actual Python/PostgreSQL/packaging cases with no skips; later focused changes pass163 cases. Controller140, all8 skill metadata validators, the published portable manifest schema,217 local documentation/anchor links, Go schema compilation, individually parsed shell inputs and21 Robot dry runs pass. The shell-parser check now rejects a deliberate syntax error in a later file; the earlier multi-argument command checked only its first file. The app lock validates without dependency changes. These are local development results; exact-source full CI/native/artifacts remain pending.

An independent cold-start reviewer validates the offline package/checksums/references and finds three concrete documentation gaps. The added operator candidate record, empty-instance first-content walkthrough and explicit Creator skill/reference-preservation check resolve all three on reinspection. This is a read-only documentation evaluation, not actual new installation or web acceptance. A private instance-bound package is prepared outside Git. No browser surface is available to the agent; actual Plugin Creator/managed-import feature availability and account observations remain pending. Independent model/MCP/database instruction measurements are prepared separately and cannot establish automatic skill activation or ChatGPT web installation.

Original checkout/recovered M20 heads and dirty status match the preserved baseline. No live runtime update, stable tag, directory submission or workspace-wide rollout has occurred.

### M21 real-web feedback and correction — 22 October 2026

Frozen `c630cb6` passes [full CI39646163590](https://github.com/Stell0/ns8-czero/actions/runs/39646163590):1740 actual Python/PostgreSQL/packaging cases, producer/released-Core/images, Debian genuine M19 upgrade21 and Rocky installation26/three expected skips/all8 browsers. Independent actual artifacts pass25 accessibility contexts,8 privacy guards,3 query-audited artifacts with zero candidates and5 scan/SBOM pairs. Exact promotion passes. An initial independent audit invocation lacks its repository-relative predecessor fixture; the retained downloaded reports pass the corrected read-only audit from the exact checkout.

Both pinned model arms pass14/14 scenarios with46 actual MCP calls each and independent database/trace plus final-prose grading. Packaged/guidance-only measured runner totals are461.47/478.05s and1,402,707/1,337,136 tokens: single samples, not a performance or quality-improvement claim. A separate synthetic selected-text task confirms an unselected credential canary is absent from all resulting database state. Failed wrong-driver and nested-sandbox attempts remain private and are not quality scores.

Actual operator web testing rejects the first marketplace-shaped ZIP with `Expected a single plugin archive`. The generator now puts one plugin's manifest/app reference/skills at ZIP root, while the directory retains the GitHub marketplace. Regression/determinism/binding/link checks pass44 cases; all9 plugin payload files remain byte-identical to the measured package. A replacement archive is delivered privately; actual upload acceptance and the other web gates remain pending. This correction requires fresh full CI; c630cb6 is not deployed or merged.

The operator separately reports reconnect requesting unapproved `c0:admin`. Read-only inspection confirms the existing client is enabled and approved only for `c0:read`; no scopes have been expanded. Intended research/editing versus administration is pending operator direction. Supported dedicated backup and actual restic read-data check pass with all existing backup plans restored;8 original HTTP views and3 schedules are captured. Deployment is held for corrected candidate acceptance and preservation baselines will be refreshed before update.

## M21 follow-up — Simple self-service ChatGPT onboarding

**Operator direction (22 October):** Simplify `/agents` for nontechnical users: direct personal-Plugins link, suggested C0 name/description/canonical MCP connection with small accessible copy icons, generated instance-specific `.skill` and plugin ZIP downloads, visible client/user permission management, reliable first OAuth sign-in and default Shared read admission for authenticated users. This supersedes M21's earlier presentation-only/Core-unchanged and offline-only packaging limits. Preserve all unfinished work and deployment waivers.

**Verified entry:** PR31 merges as `0040c8930257e0a605e4768ef76dab84490f8691`; its completed main39745026479 and independently inspected native/privacy/scan artifacts pass. Tested/deployed candidate `37301886c4e28a5982c85cd837a113a96a54d2e0` has the same tree. The operator explicitly requests and approves supported removal/recreation for a fully clean start after a supported backup/actual restic read-data check. The new dedicated instance runs app0.49.1/Core0.31.0/schema0018 with restored configuration, one empty Shared space, owner only, zero old clients/content/history/files and three built-in schedules. All eleven unrelated module identities are preserved. The removed native client is absent. Actual fresh ChatGPT acceptance remains pending; no M21 completion is claimed. Deployed images remain frozen at:

| Image | Current installed digest |
| --- | --- |
| Module | `sha256:b7177aaed0d61b5ce9913173b25d57fbe150457155619d7f0429afefbc36815e` |
| App | `sha256:fcd6c9a1552774e065a4ab04ed1f19a9244c708bee9ec4c9407249d1f509ea72` |
| PostgreSQL | `sha256:7aefea399df70ed31ed294358a768c47c40c58870224828063a765a7ecb5bf53` |

Canonical tag: `ci-37301886c4e28a5982c85cd837a113a96a54d2e0-39737449917-1`. Preserve it as the genuine next upgrade predecessor; documentation/main images do not replace it.

**Settled interfaces and responsibilities:**

- Core0.31.1 adds opt-in new-account Reader admission, persisted explicit account blocking and a bounded browser-bound pending-client authorization service. Schema0019 is additive. Existing Core callers retain closed admission by default. Migration marks existing unadmitted identities blocked, preserving earlier revocations; existing memberships/owners/grants are unchanged. Trusted verified identities alone can receive admission; role/scopes/space grants remain authoritative. Membership removal records a persistent block and revokes existing authority, including after repeated/concurrent sign-in.
- Pending client authorization stores a validated authorization request for five minutes behind separate opaque request/browser hashes, current issuer/native-client/resource and bounded counts. It performs no network work and grants no authority. Only signed-in users can register an approval request; Admins see bounded pending metadata URLs/callbacks/scopes, never state/PKCE/native secrets. Continuing requires same-origin CSRF, a current verified session, fresh approved client metadata, exact callback/scope validation and one-use transition into existing consent. Expired, disabled, changed, blocked and replayed requests fail closed. Existing UUID clients and approved-client flows retain their validation. Malformed/duplicate/resource/credential requests remain strict errors; valid unapproved CIMD requests get the human flow only while discovery is enabled.
- The application opts into Reader admission, returns pending onboarding across normal SSO without placing OAuth parameters in redirect URLs, and presents clear approval/continue steps. C0 Administration exposes Users first, then pending ChatGPT connections and reviewed-client controls; no automatic broad client approval or Admin scope is introduced.
- `/agents` derives name/description/hostname/MCP URL from trusted configured instance metadata. Three compact icon controls retain keyboard labels, copy feedback/manual fallback and stale-response guards. Technical details move to disclosures. A `.skill` ZIP contains one instance-bound memory workflow and declared MCP dependency; it contains no credential. A web plugin ZIP references the user's existing registered ChatGPT app; the UI accepts its technical ID/management URL and explains where to copy it. It does not invent a binding, add inline MCP that makes workspace imports Desktop only, or claim installation grants access.
- Reuse one application packaging library from offline and HTTP paths. Serve in-memory deterministic bounded archives with explicit filenames/no-store/no-sniff and no remote fetches or writes. Runtime includes only explicitly allowlisted end-user package assets and GPL license; repository development skills/tests/plans stay excluded. Update runtime audits accordingly.
- Native lifecycle remains numbered scripts. No host logging, shared identity-provider user, unrelated application, CPU-quota or stable-release change is part of this work.

**Delivery:** First validate/publish immutable compatible Core artifacts from exact successful local/both-native source, then pin the application dependency/lock and complete final consumer/image/both-native checks. Use focused commits on an isolated branch, reviewed PR, supported dedicated-instance deployment and actual ChatGPT acceptance before final closeout. Runtime behavior does not deploy from local tests alone.

**Acceptance checklist:**

- [ ] Core database cases: first/concurrent verified admission, wrong/expired issuer identity, unchanged existing roles, persistent block/regrant/revocation, protected-space isolation; genuine schema0018 migration/repeat/restore and package distribution.
- [ ] Pending-client cases: duplicate/malformed/oversized requests, policy-off/no unauthenticated fetch, cookie/issuer/native/resource bindings, limits/expiry, signed-in queue privacy, Admin-only preview/approval, role-loss/provider failure, one winner/replay, exact callback/PKCE/scopes and unchanged existing clients.
- [ ] Downloads: two configured instances, deterministic bytes, safe names/app IDs/URLs, no secrets/unrelated assets, valid skill/plugin manifests/references/dependencies, installed-image downloads and package license.
- [ ] UI: simple signed-out/signed-in states; direct links and suggested text; icon clipboard success/failure/keyboard/accessibility; stale replies/access loss; visible Users/connection approval and Reader/Editor/Admin/blocked behavior in actual native browsers.
- [ ] Focused plus full Python/PostgreSQL/packaging, JavaScript, schema/shell/Robot and both-native/actual artifact audits; immutable Core release and final released consumer checks.
- [ ] C0-only backup/update/readiness/data/client/schedule/inventory/restart/journal acceptance; actual fresh ChatGPT OAuth, `.skill` import, plugin import, cited read/repeat and permitted editing/denial. Keep actual web observations distinct from model/SDK checks.
- [ ] Reviewed regular main promotion, completed main/publication and separate checked evidence closeout; freeze final accepted runtime.

<details>
<summary>Historical section links</summary>

These anchors preserve links to the retained historical record.

<a id="c0-implementation-plan--milestone-by-milestone-codex-handoff"></a>[C0 implementation plan — milestone-by-milestone Codex handoff](docs/history/PLAN.md#c0-implementation-plan--milestone-by-milestone-codex-handoff)

<a id="product-contract-do-not-quietly-change"></a>[Product contract (do not quietly change)](docs/history/PLAN.md#product-contract-do-not-quietly-change)

<a id="source-precedence-and-selection"></a>[Source precedence and selection](docs/history/PLAN.md#source-precedence-and-selection)

<a id="non-negotiable-execution-loop-for-every-milestone"></a>[Non-negotiable execution loop for EVERY milestone](docs/history/PLAN.md#non-negotiable-execution-loop-for-every-milestone)

<a id="tests-and-ci-conventions"></a>[Tests and CI conventions](docs/history/PLAN.md#tests-and-ci-conventions)

<a id="milestones"></a>[Milestones](docs/history/PLAN.md#milestones)

<a id="m00--rebrand-kickstart-create-working-ci-and-smoke-test-the-module-x"></a>[M00 — Rebrand kickstart, create working CI and smoke-test the module [x]](docs/history/PLAN.md#m00--rebrand-kickstart-create-working-ci-and-smoke-test-the-module-x)

<a id="m01--minimal-python-runtime-web-ui-and-coreapplication-separation-x"></a>[M01 — Minimal Python runtime, Web UI and Core/application separation [x]](docs/history/PLAN.md#m01--minimal-python-runtime-web-ui-and-coreapplication-separation-x)

<a id="m02--ns8-configuration-traefik-and-administrator-ui-x"></a>[M02 — NS8 configuration, Traefik and administrator UI [x]](docs/history/PLAN.md#m02--ns8-configuration-traefik-and-administrator-ui-x)

<a id="m03--dedicated-postgresql--pgvector-and-migrations-x"></a>[M03 — Dedicated PostgreSQL + pgvector and migrations [x]](docs/history/PLAN.md#m03--dedicated-postgresql--pgvector-and-migrations-x)

<a id="m04--backup-restore-and-upgrade-safe-persistence-x"></a>[M04 — Backup, restore and upgrade-safe persistence [x]](docs/history/PLAN.md#m04--backup-restore-and-upgrade-safe-persistence-x)

<a id="m05--ns8-idp-login-and-minimal-application-wide-authorization-x"></a>[M05 — ns8-idp login and minimal application-wide authorization [x]](docs/history/PLAN.md#m05--ns8-idp-login-and-minimal-application-wide-authorization-x)

<a id="m06--deterministic-jobs-and-database-backed-scheduler-x"></a>[M06 — Deterministic jobs and database-backed scheduler [x]](docs/history/PLAN.md#m06--deterministic-jobs-and-database-backed-scheduler-x)

<a id="m07--generic-application-object-model-and-reusable-crud-x"></a>[M07 — Generic application object model and reusable CRUD [x]](docs/history/PLAN.md#m07--generic-application-object-model-and-reusable-crud-x)

<a id="m08--source-ingestion-text-extraction-and-chunk-storage-x"></a>[M08 — Source ingestion, text extraction and chunk storage [x]](docs/history/PLAN.md#m08--source-ingestion-text-extraction-and-chunk-storage-x)

<a id="m09--versioned-wiki-entities-claims-provenance-and-postgresql-graph-x"></a>[M09 — Versioned Wiki, entities, claims, provenance and PostgreSQL graph [x]](docs/history/PLAN.md#m09--versioned-wiki-entities-claims-provenance-and-postgresql-graph-x)

<a id="m10--full-text-vectors-external-embeddings-and-jevkev-system-one-rag-x"></a>[M10 — Full-text, vectors, external embeddings and Jev/Kev System One RAG [x]](docs/history/PLAN.md#m10--full-text-vectors-external-embeddings-and-jevkev-system-one-rag-x)

<a id="m11--restmcp-parity-oauth-interoperability-and-agents-discovery-x"></a>[M11 — REST/MCP parity, OAuth interoperability and `/agents` discovery [x]](docs/history/PLAN.md#m11--restmcp-parity-oauth-interoperability-and-agents-discovery-x)

<a id="m12--full-c0-user-ui-and-ns8-configuration-experience-x"></a>[M12 — Full C0 user UI and NS8 configuration experience [x]](docs/history/PLAN.md#m12--full-c0-user-ui-and-ns8-configuration-experience-x)

<a id="m13--fork-upgrades-c0-core-distribution-and-upstream-contribution-skills-x"></a>[M13 — Fork upgrades, C0 Core distribution and upstream contribution skills [x]](docs/history/PLAN.md#m13--fork-upgrades-c0-core-distribution-and-upstream-contribution-skills-x)

<a id="m14--end-to-end-hardening-compatibility-and-release-gate-x"></a>[M14 — End-to-end hardening, compatibility and release gate [x]](docs/history/PLAN.md#m14--end-to-end-hardening-compatibility-and-release-gate-x)

<a id="after-m14"></a>[After M14](docs/history/PLAN.md#after-m14)

<a id="current-next-action"></a>[Current next action](docs/history/PLAN.md#current-next-action)

<a id="m15--reader-first-knowledge-website-x"></a>[M15 — Reader-first knowledge website [x]](docs/history/PLAN.md#m15--reader-first-knowledge-website-x)

<a id="chatgpt-mcp-integration--operator-plan-15-october-2026"></a>[ChatGPT MCP integration — operator plan (15 October 2026)](docs/history/PLAN.md#chatgpt-mcp-integration--operator-plan-15-october-2026)

<a id="integration-m15--oauth-authorization-parameter-compatibility-x"></a>[Integration M15 — OAuth authorization parameter compatibility [x]](docs/history/PLAN.md#integration-m15--oauth-authorization-parameter-compatibility-x)

<a id="integration-m16--mcp-authentication-metadata-and-permission-upgrades-x"></a>[Integration M16 — MCP authentication metadata and permission upgrades [x]](docs/history/PLAN.md#integration-m16--mcp-authentication-metadata-and-permission-upgrades-x)

<a id="integration-m20--renewable-browser-and-delegated-sessions--"></a>[Integration M20 — Renewable browser and delegated sessions [ ]](docs/history/PLAN.md#integration-m20--renewable-browser-and-delegated-sessions--)

<a id="m20-main-recovery-fixture-correction--20-october-2026"></a>[M20 main recovery-fixture correction — 20 October 2026](docs/history/PLAN.md#m20-main-recovery-fixture-correction--20-october-2026)

<a id="m20-corrected-runtime-closeout--20-october-2026"></a>[M20 corrected runtime closeout — 20 October 2026](docs/history/PLAN.md#m20-corrected-runtime-closeout--20-october-2026)

<a id="integration-m17--profile-identity-closed"></a>[Integration M17 — Profile identity (closed)](docs/history/PLAN.md#integration-m17--profile-identity-closed)

<a id="m17-deployed-acceptance-and-closeout--20-october-2026"></a>[M17 deployed acceptance and closeout — 20 October 2026](docs/history/PLAN.md#m17-deployed-acceptance-and-closeout--20-october-2026)

<a id="integration-m18--tool-guidance-accepted-and-closed"></a>[Integration M18 — Tool guidance (accepted and closed)](docs/history/PLAN.md#integration-m18--tool-guidance-accepted-and-closed)

<a id="m18-executed-evidence-and-closeout--20-october-2026"></a>[M18 executed evidence and closeout — 20 October 2026](docs/history/PLAN.md#m18-executed-evidence-and-closeout--20-october-2026)

<a id="integration-sequence-after-m20"></a>[Integration sequence after M20](docs/history/PLAN.md#integration-sequence-after-m20)

<a id="structured-object-creation-repair--active-operator-task"></a>[Structured object creation repair — active operator task](docs/history/PLAN.md#structured-object-creation-repair--active-operator-task)

<a id="m1--root-cause-and-regression-reproduction-x"></a>[M1 — Root cause and regression reproduction [x]](docs/history/PLAN.md#m1--root-cause-and-regression-reproduction-x)

<a id="m2--minimal-implementation-fix-x"></a>[M2 — Minimal implementation fix [x]](docs/history/PLAN.md#m2--minimal-implementation-fix-x)

<a id="m3--complete-validated-crud-regression-x"></a>[M3 — Complete validated CRUD regression [x]](docs/history/PLAN.md#m3--complete-validated-crud-regression-x)

<a id="c0-agent-memory--additional-operator-track"></a>[C0 Agent Memory — additional operator track](docs/history/PLAN.md#c0-agent-memory--additional-operator-track)

<a id="c0-am0--baseline-and-compatibility-contracts-x"></a>[C0-AM0 — Baseline and compatibility contracts [x]](docs/history/PLAN.md#c0-am0--baseline-and-compatibility-contracts-x)

<a id="c0-am1--mcp-native-text-evidence-ingestion-x"></a>[C0-AM1 — MCP-native text evidence ingestion [x]](docs/history/PLAN.md#c0-am1--mcp-native-text-evidence-ingestion-x)

<a id="c0-am2--agent-friendly-wiki-operations-and-errors-x"></a>[C0-AM2 — Agent-friendly Wiki operations and errors [x]](docs/history/PLAN.md#c0-am2--agent-friendly-wiki-operations-and-errors-x)

<a id="c0-am3--protected-knowledge-spaces-x"></a>[C0-AM3 — Protected knowledge spaces [x]](docs/history/PLAN.md#c0-am3--protected-knowledge-spaces-x)

<a id="c0-am4--scoped-and-structured-knowledge-retrieval-x"></a>[C0-AM4 — Scoped and structured knowledge retrieval [x]](docs/history/PLAN.md#c0-am4--scoped-and-structured-knowledge-retrieval-x)

<a id="c0-am5--reliable-consolidation-and-maintenance-primitives-x"></a>[C0-AM5 — Reliable consolidation and maintenance primitives [x]](docs/history/PLAN.md#c0-am5--reliable-consolidation-and-maintenance-primitives-x)

<a id="c0-am6--agent-documentation-and-integration-tests-x"></a>[C0-AM6 — Agent documentation and integration tests [x]](docs/history/PLAN.md#c0-am6--agent-documentation-and-integration-tests-x)

<a id="final-c0-am-deployment-gate-x"></a>[Final C0-AM deployment gate [x]](docs/history/PLAN.md#final-c0-am-deployment-gate-x)

<a id="am3-runtime-acceptance--17-october-2026"></a>[AM3 runtime acceptance — 17 October 2026](docs/history/PLAN.md#am3-runtime-acceptance--17-october-2026)

<a id="am3-documentation-closeout-and-am4-start--18-october-2026"></a>[AM3 documentation closeout and AM4 start — 18 October 2026](docs/history/PLAN.md#am3-documentation-closeout-and-am4-start--18-october-2026)

<a id="am4-deployment-acceptance-and-documentation-closeout--18-october-2026"></a>[AM4 deployment acceptance and documentation closeout — 18 October 2026](docs/history/PLAN.md#am4-deployment-acceptance-and-documentation-closeout--18-october-2026)

<a id="am4-final-marker-gates-and-am5-start--18-october-2026"></a>[AM4 final marker gates and AM5 start — 18 October 2026](docs/history/PLAN.md#am4-final-marker-gates-and-am5-start--18-october-2026)

<a id="am5-deployed-runtime-acceptance--18-october-2026"></a>[AM5 deployed runtime acceptance — 18 October 2026](docs/history/PLAN.md#am5-deployed-runtime-acceptance--18-october-2026)

<a id="scoped-development-ci-policy--implemented-and-verified"></a>[Scoped development CI policy — implemented and verified](docs/history/PLAN.md#scoped-development-ci-policy--implemented-and-verified)

<a id="actual-development-and-negative-controls"></a>[Actual development and negative controls](docs/history/PLAN.md#actual-development-and-negative-controls)

<a id="full-acceptance-fixes-and-canonical-publication"></a>[Full acceptance, fixes and canonical publication](docs/history/PLAN.md#full-acceptance-fixes-and-canonical-publication)

<a id="am6--accepted-guidance-and-independent-workflows-19-october-2026"></a>[AM6 — Accepted guidance and independent workflows (19 October 2026)](docs/history/PLAN.md#am6--accepted-guidance-and-independent-workflows-19-october-2026)

<a id="source-review-and-full-acceptance"></a>[Source, review and full acceptance](docs/history/PLAN.md#source-review-and-full-acceptance)

<a id="accepted-dedicated-runtime-and-preservation"></a>[Accepted dedicated runtime and preservation](docs/history/PLAN.md#accepted-dedicated-runtime-and-preservation)

<a id="closeout-and-retained-limits"></a>[Closeout and retained limits](docs/history/PLAN.md#closeout-and-retained-limits)

<a id="integration-m19--optional-approved-client-metadata-discovery"></a>[Integration M19 — Optional approved client metadata discovery](docs/history/PLAN.md#integration-m19--optional-approved-client-metadata-discovery)

<a id="m19-core-implementation-checkpoint--21-october-2026"></a>[M19 Core implementation checkpoint — 21 October 2026](docs/history/PLAN.md#m19-core-implementation-checkpoint--21-october-2026)

<a id="m19-application-implementation-checkpoint--21-october-2026"></a>[M19 application implementation checkpoint — 21 October 2026](docs/history/PLAN.md#m19-application-implementation-checkpoint--21-october-2026)

<a id="m19-core-release-and-consumer-adoption--21-october-2026"></a>[M19 Core release and consumer adoption — 21 October 2026](docs/history/PLAN.md#m19-core-release-and-consumer-adoption--21-october-2026)

<a id="m19-application-ci-correction--21-october-2026"></a>[M19 application CI correction — 21 October 2026](docs/history/PLAN.md#m19-application-ci-correction--21-october-2026)

<a id="m19-final-candidate-validation-corrections--21-october-2026"></a>[M19 final-candidate validation corrections — 21 October 2026](docs/history/PLAN.md#m19-final-candidate-validation-corrections--21-october-2026)

<a id="m19-forced-ann-fixture-isolation--21-october-2026"></a>[M19 forced-ANN fixture isolation — 21 October 2026](docs/history/PLAN.md#m19-forced-ann-fixture-isolation--21-october-2026)

<a id="m19-deployed-acceptance-and-main-closeout--21-october-2026"></a>[M19 deployed acceptance and main closeout — 21 October 2026](docs/history/PLAN.md#m19-deployed-acceptance-and-main-closeout--21-october-2026)

</details>

### M21 self-service implementation checkpoint

Core source `6f1e4703f4d027c82ccb03ef8813efe30c650365` passes [full39760439788](https://github.com/Stell0/ns8-czero/actions/runs/39760439788), including local/producer/released-image and both native distributions. Independently downloaded reports verify Debian genuine predecessor upgrade21, Rocky installation26/three expected skips, eight browsers/privacy guards,25 accessibility contexts, three OAuth-query artifacts with zero candidates and five actual scan/SBOM pairs. The full promotion verifier passes. [Core publication39768193889](https://github.com/Stell0/ns8-czero/actions/runs/39768193889) completes successfully at that exact source. Immutable `core-v0.31.1` wheel SHA256 `ec2b9757d5a947f98bc9e743a6d7eb9f5227f59682d6a8a334ea201f5d03d13a`, archive SHA256 `1ee6154ae1e3ed8a1a90684e85d3897034d05cb98733f18611bee84141bcbb5e`; downloaded checksums match. This Core bridge is not the application/live candidate.

Application0.50.0 pins released Core0.31.1 and implements the planned human approval, default Reader/blocked-account UI and generated `.skill`/single-plugin ZIP page. Focused HTTP/download tests pass115 cases; the exact native Core-seeded first-connection/replay helper passes six local HTTP tests. Updated native browser tests download/inspect both archives, and native admission checks require a genuinely new Reader plus persistent blocking. Final full application/consumer/image/native validation, supported dedicated update and actual ChatGPT skill/plugin acceptance remain pending in draft PR32.

</details>


## WikiPlant backend track — M0 inspection

The operator requests reusable research projects through M0–M8, without live migration, deployment or schedule activation. See [compatibility audit](docs/projects/WIKIPLANT_COMPATIBILITY.md) for exact original revisions, capability matrix, ownership, sequential implementation and tests. Current status: M0 comparison recorded; baseline validation pending. Existing ingestion and protected spaces are reused. Historical acceptance and deployed images remain frozen.


### WikiPlant M1 — project foundation (implementation checkpoint)

Strict manifest/topic v1 contracts and a protected transactional project service
reuse existing typed objects, unique keys and knowledge receipts. Configuration
history is immutable; new managed types reject raw object/bundle writes. User
anchors require current Admin authority and recorded affirmative authorization;
adjacent topics need direct active user anchors; peripheral topics are terminal
with fixed weekly expiry. Parent cycles and silent archive reactivation reject.
Reference REST/MCP bindings and a read-only `/projects` overview preserve explicit
space selection, local DOM rendering, late-response and access-loss guards.
See [project contracts](docs/projects/PROJECTS.md). New default-released-Core
availability remains gated on immutable library publication and pin adoption.

Executed focused evidence: 15 schema/DST cases; 60 project/object/bundle cases;
one actual signed-HTTP contract test; 19 project/space controller cases. First
expiry fixture expected the following week despite a still-future same-day UTC
checkpoint; corrected the fixture, preserving the strictly-future algorithm.
The original-main local baseline passes 2045 actual Python/PostgreSQL/packaging,
185 Node, Go/schema, shell and 21 Robot dry runs. Baseline40286224042 is completed/
successful with exact-source full promotion proof; independent artifact inspection
is in progress. M0 bed8142 full40289915767 has successful local/images/scans and
pending both-native checks. Full M1 local candidate checks are running; no M1
CI/native, Core release, live instance or external-agent acceptance is claimed.


M1 validation follow-up: the initial broad candidate run recorded 28 failures /
2037 passes, all from frozen catalog-count assertions after adding five tools.
The original 77 input/output/authority/REST contracts remain checked exactly;
project operations have a separate explicit additive inventory. Updated counts
and matching replay/destructive/closed-world hints pass the focused actual SDK
and guidance checks. The current/legacy project SDK calls pass against signed
HTTP/PostgreSQL. The exact native project seed/readback/Reader recovery helper
passes through the actual local HTTP app with explicit test-module path setup.
All190 Node cases and21 Robot dry runs pass. Corrected full candidate Python
validation remains running; native project browser/backup checks are implemented
but have not yet executed. Mark synthetic generated native passwords with a test
prefix so public privacy review distinguishes the existing random fixture from
a literal credential. No real credentials or instance state are committed.

Independent downloaded baseline40286224042 inspection passes Debian21 upgrade,
Rocky26 installation/three expected skips/all8 browsers, 30 accessibility contexts,
eight privacy guards, three actual query artifacts with zero candidates and five
SARIF/CycloneDX pairs. Exact full promotion verification also passes.
