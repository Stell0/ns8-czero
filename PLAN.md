# C0 roadmap

**Reviewed 28 November 2026.** This is the active implementation sequence for
C0. M22–M32 replace the proposed parallel R1–R6 roadmap and absorb the
remaining work from the original integration, memory, compilation and research
project tracks. The old checkpoints are evidence, not outstanding tasks.
Use current upstream main and exact source/consumer/install identities before
starting each milestone.

## Current baseline

| Layer | Recorded state |
| --- | --- |
| Reviewed upstream | `baa6dbc2fe9ac73ceebf67b63f6f6d36a0e8d63d` (merge of PR 180). Recheck main before starting implementation. |
| Main producer | Core 0.55.0, schema `0048_consent_flows`, released from `a85dac044bc4b38e0bb581111cda4a04a104124a` |
| Reference application dependency | The App 0.70.0 source lock pins released Core 0.55.0. [PR 179 passed full released-consumer and native acceptance](https://github.com/Stell0/ns8-czero/actions/runs/46148996526). |
| Recorded installed monitoring baseline | App 0.70.0 / released Core 0.53.0, source `4172d37da936647ef6b3decea045dd4304e17c93`, three authorized instances; see [native and live evidence](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#installed-monitoring-baseline) |
| Module release | Development candidate; no stable NS8 release or public plugin-directory listing is claimed |

The accepted monitoring image set is the recorded immutable tag
`ci-4172d37da936647ef6b3decea045dd4304e17c93-45456339586-1`:

| Image | Recorded installed digest |
| --- | --- |
| `czero` | `sha256:0333ca60c458d2cad60bf5fd9c978f4631d9419a0a40d690071ec47e29b62853` |
| `czero-app` | `sha256:fe41e4a620fab01dd7a674c7e13479a40403675da33c56b99e053c8e5b69deba` |
| `czero-postgres` | `sha256:4896eed333507dd35a7b169f588e2736c0dc8059ad4baa3bcca36a529c0a95cb` |

These are repository records, not a fresh live inventory. Verify the actual
genuine predecessor before any authorized update. Main source versions, Core
tags, locked consumers, canonical images and deployed images are separate
identities; a merge or documentation update does not upgrade an instance.

### What already works

C0 supplies shared Wiki, complete current documents and original evidence,
structured records/tables, entities and claims, scoped retrieval, protected
spaces, REST/MCP, OAuth and personal API keys, native deterministic jobs,
automatic public GitHub/Web/owned Drive sources, research projects, compiler
coordination and trusted custom application hosting. BM25, optional embeddings
and hybrid retrieval, relevance scoring and benchmark harnesses exist. Grafana
monitoring is accepted on the recorded installation.

BYOA remains the boundary: C0 stores, authorizes, retrieves and coordinates
bounded deterministic operations. External agents reason, select sources,
synthesize, judge semantic truth and decide or execute domain actions. The
worker does not execute arbitrary prompts or shell commands. Preserve the
latest-only complete source/Wiki contract and exact evidence identities,
protected-space boundaries, current authority and revocation. No second vector
store, universal ontology, general-purpose agent framework or implicit
cross-instance replication is planned.

### Reviewed existing milestones

| Track | Disposition | Remaining work |
| --- | --- | --- |
| M00–M14, M15–M19 | Accepted historical foundations/integrations | Maintain regression coverage; do not reopen from old checkboxes |
| Integration M20 | Historical corrected-runtime closeout | New OAuth defects and release gates → M22/M23 |
| M21 | Documentation, packaging and onboarding largely implemented; real-client acceptance incomplete | M23 |
| AM0–AM6 | Completed | Reuse existing memory/retrieval/consolidation primitives → M27 |
| WikiPlant M0–M8 | Backend deployed | Consumer-specific migrations, actual research and scheduled-run readback; use M23/M25/M31 where relevant |
| Compiler M0–M5 | Implemented | Reuse existing coordinator, policies, dependencies and external host |
| Compiler M6 | Quality gates failed | Reuse measurement tooling; M24/M26, no automatic rollout |
| Cross-space M0–M4 | Backend and released-consumer acceptance recorded | Confirm installed capability; optional browser panels only on demonstrated need → M29 |
| PDM / personal data | Draft candidate on historical base | M30 |

Historical status snapshots in [the October record](docs/history/PLAN.md) and
[the frozen November plan](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md) must not be interpreted as the active
milestone list. In particular, an unchecked historical native or documentation
box does not reopen a later accepted runtime.

## Roadmap

Each milestone starts by auditing existing implementation and exact acceptance
evidence. Split large scopes into independently reviewable PRs. States:
**in progress** (open corrective work), **validation** (implementation exists
but acceptance is incomplete), **planned** (new work), **optional** (explicit
stop/go). Priorities P0/P1/P2 describe current implementation priority, not
promised dates. The order below is dependency-aware, not a requirement to
serialize independent work.

| Milestone | Priority / state | Hard dependencies or acceptance prerequisites |
| --- | --- | --- |
| [M22 — Runtime stabilization](#m22--runtime-stabilization) | P0 / in progress | Current main, genuine installed predecessor |
| [M23 — BYOA and release readiness](#m23--byoa-and-release-readiness) | P0 / validation | M22 for installed acceptance |
| [M24 — KnowledgeOps registry and baseline](#m24--knowledgeops-registry-and-baseline) | P0 / planned; benchmark groundwork merged | Current API; M22 before runtime deployment |
| [M25 — Connectors and source coverage](#m25--connectors-and-source-coverage) | P0/P1 / planned; open sample PR | M22; M24 for measured domain acceptance |
| [M26 — Retrieval evidence, freshness and compilation](#m26--retrieval-evidence-freshness-and-compilation) | P0/P1 / validation + planned | M24; M25 for newly added source types only |
| [M27 — Verified procedural memory](#m27--verified-procedural-memory) | P0 / planned | AM0–AM6, M24; reuse M26 as available |
| [M28 — Service identities and delegated authorization](#m28--service-identities-and-delegated-authorization) | P0/P1 / planned | M22 |
| [M29 — Application hosting platform](#m29--application-hosting-platform) | P0/P1 / planned | Existing hosting contract 1; M28 for service-account provisioning |
| [M30 — Personal Data Manager](#m30--personal-data-manager) | P1 / draft review | M22 and scoped threat model; coordinate with M28 |
| [M31 — Event-driven workflows](#m31--event-driven-workflows) | P1 / planned | M24/M27 outcomes, M28 identity, M25 source events |
| [M32 — Optional hosted agent runner](#m32--optional-hosted-agent-runner) | P2 / optional | M29/M31 and demonstrated unmet consumer need |

### Next acceptance work

Start M22 now. M23 guide/compatibility work, M24 baseline design and
M28 threat-model work may begin in parallel on a verified base. M30 draft
review may proceed independently of later features after M22. Keep M24 and
M27 the strategic focus: measure Support and SAT quality before expanding
compiler behavior or memory automation. M23's unavailable third-party account
features are explicit compatibility limitations, not automatic blockers for
unrelated implementation. Do not wait for M32 to propose a supported release.

### M22 — Runtime stabilization

**P0 / in progress.** Core 0.55.0 shipped the collection and OAuth recovery
changes, and the reference app adopted the release. M22 still tracks
issue acceptance and authorized rollout and readback (part of former R1
and the M20 residual).

- Confirm issue acceptance for [#166](https://github.com/Stell0/ns8-czero/issues/166)
  multipart readiness and diagnostics, [#167](https://github.com/Stell0/ns8-czero/issues/167)
  explicit website PDF attachment collection, and [#168](https://github.com/Stell0/ns8-czero/issues/168)
  REST/MCP error parity. Core 0.54.0 added schema `0047_collection_diagnostics`,
  and these changes shipped in Core 0.55.0. See the
  [collection delivery record](#public-website-collection-and-ingestion-reliability).
- Verify installed behavior using the [OAuth recovery rollout](#oauth-browser-and-connector-recovery)
  criteria below. Retain failed evidence and confirm the exact consumer image
  and genuine predecessor before any authorized rollout.
- Verify existing hosted Support state and SAT full-document/citation access
  on an explicitly authorized lab. Keep the separately approved
  [Support integration plan](docs/support-integration-plan.md) and its paired
  application/fixture acceptance in scope; simulated investigations are not
  production outcomes.

**Done when:** real PostgreSQL and signed REST/current and legacy MCP SDK
regressions, browser and native Debian/Rocky gates pass for the exact source;
whole-document identity, complete/partial coverage, revocation, OAuth
renewal/replay, backup/restore and existing authority survive. Separate
publication, consumer adoption and authorized deployment records identify the
actual images. Close issues only with corresponding evidence.

#### OAuth browser and connector recovery

[PR 177](https://github.com/Stell0/ns8-czero/pull/177) added browser flow
ownership, callback publication fencing and status-only consent receipts in
schema `0048_consent_flows`. The [full producer acceptance](https://github.com/Stell0/ns8-czero/actions/runs/46144047419)
passed on `a85dac044bc4b38e0bb581111cda4a04a104124a`, including Debian upgrade
and Rocky install. [Core 0.55.0](https://github.com/Stell0/ns8-czero/releases/tag/core-v0.55.0)
was published from that commit. The downloaded wheel and source archive matched
the independent build and the published checksums. Their SHA256 digests are
`549a513679ffa3e32612a5cc507a1eb3af326825c651bd489a479ef292950ddf` and
`601eec83b6d605bc0d9684e0d4cdd8a33bdb6ccf104badfd6e65d91111a623d7`, respectively.

The reference app lock selects that exact Git commit through `core-v0.55.0`.
[PR 179](https://github.com/Stell0/ns8-czero/pull/179) adopted the lock after
[full consumer acceptance](https://github.com/Stell0/ns8-czero/actions/runs/46148996526)
on `ace6c91c2f51166487c215d4c20260ac6e0c7be0`, including Debian upgrade and
Rocky install.
Its predecessor used Core 0.53.0 and rejected the session-only parameter.
With the producer and the affected console, a disposable Keycloak and PostgreSQL
run verified an authenticated MCP profile read after disconnect and fresh consent,
and another on the original connection after C0 restarted and became ready.

Acceptance exercises overlapping browser requests, explicit background login,
lost completion and rotation responses, current account and role, and
credential-free C0 and connector diagnostics. Repeat the installed console
and assistant reads after reconnect and after a recoverable outage. A clean
restore with a new native identity requires fresh consent. Keep rollout
gated on full native acceptance, supported backup, readiness and those
client readbacks.

The OAuth recovery rollout can proceed with the existing Traefik configuration.
Traefik can retain OAuth callback queries. Restrict access to raw proxy logs
and exclude them from shared incident exports. After released-consumer image
and native acceptance, deploy the same verified C0 image one instance at a
time. Verify the existing grant with an authenticated MCP profile read before
updating the connector where it is already installed. A generic proxy or
transport failure after refresh dispatch still requires fresh consent. Only
C0's confirmed pre-rotation result allows a retry with that refresh token.
Stop rollout on a credential in C0 or connector diagnostics, a binding or
revocation failure, a second redemption, lost backup evidence, or a failed
protected read on a healthy service. Recover a failed schema update using the
supported, matched pre-update backup and image. Preserve the native client
identity when recovering the same instance.

### M23 — BYOA and release readiness

**P0 / validation.** Absorbs M21 and remaining external-client acceptance.
Reuse the existing chooser, guides, generated packages and permission controls.
Use [BYOA](docs/byoa.md), [maintenance](docs/wiki-maintenance.md) and
[release readiness](docs/release-readiness.md) as detailed acceptance references.

- ChatGPT: private archive/skill use and cited Read already observed; complete
  supported managed import, Write/denial, Manage where needed, renewal,
  disconnect and scheduled read/write verification. Codex: existing profile
  and protected Read evidence; prove permitted edits and unattended runs.
- Claude: installed plugin and cited Read observed; verify remaining Write and
  scheduling when authorized. Grok and Gemini: skill setup was observed but
  connected reads remain unverified; record account-specific prerequisites and
  alternatives without claiming unsupported native integrations.
- Shorten cold-start journey, preserve application approval versus personal
  consent and space authorization, verify package inventory and exact binding.
  Keep a dated provider capability matrix. Validate the existing supported
  scheduling route instead of adding a second scheduler.
- Reconcile stable-release prerequisites: supported version and installation/
  upgrade/restore guidance, security finding disposition, claimed workload
  quality and exact publication/consumer evidence. A numbered testing release
  under the Support integration plan, stable NS8 tagging, public directory
  listing and workspace rollout are distinct authorized scopes.

**Done when:** a fresh user completes supported setup, first cited Read and
authorized Edit with independent readback; real denied access, reconnect,
revocation and post-expiry scheduled runs are separately recorded. Unavailable
provider features remain explicitly unverified, not synthetic substitutes.
Document the release decision and required checks; no automatic public rollout.

### M24 — KnowledgeOps registry and baseline

**P0 / planned; benchmark groundwork merged.** Former R2, C12. The
[kbnethesis benchmark history PR 176](https://github.com/Stell0/ns8-czero/pull/176)
is already merged; reuse its private frozen cohort/rerun workflow, the
[benchmark guide](docs/web-vs-kb.md), [retrieval benchmark](docs/retrieval-benchmark.md)
and existing compiler/tool evaluation harnesses. Do not rebuild a runner simply
to put its results in C0.

- Design a space-scoped evaluation registry: dataset/case, ground truth,
  retrieval profile, corpus and model identities, run, evidence, candidate
  answer or minimal receipt, judgment, outcome, cost and regression. Start with
  existing typed records; add dedicated operations/storage only when query,
  consistency, security or lifecycle needs justify it.
- Expose reproducible baseline comparison and a quality dashboard: citation
  validity, answer/evidence coverage, retrieval, stale evidence, contradictions,
  verification, incomplete ingestion and latency/cost. Reuse existing dependency
  and run state; distinguish infrastructure errors from quality failures.
- Define shared outcome references for M27/M31 rather than independent ledgers.
  Keep private labels, raw traces, confidential source bodies and provider
  credentials out of Git and logs; minimize stored evaluation payloads. External
  harnesses execute models and semantic grading.

**Done when:** establish a frozen cohort of at least 20 real authorized
Support/SAT cases, expanding toward 100 after the method is stable; separate
development from held-out cases, pin corpus/configuration/model identity,
record all attempts and compare compatible runs with case-level evidence.
Results are reproducible, space-authorized and readable through REST/MCP and
the browser. Ranking improvement alone does not establish answer correctness.

### M25 — Connectors and source coverage

**P0/P1 / planned with existing open sample PR.** Remaining R1, C4.
Reuse [automatic sources](docs/automatic-sources.md),
[ingestion samples](samples/ingestion/README.md) and
[PR 165 — Freshdesk FAQ sample](https://github.com/Stell0/ns8-czero/pull/165).
Review/rebase the sample and close its actual packaging/publication tests;
do not automatically turn every source into a native worker.

- P0: a bounded reusable collector contract (selection, identity,
  authorization, credentials, checkpoints, receipts, retry, limits, deduplication
  and revocation); explicitly authorized private GitHub repositories with
  per-connection/repository scope; RSS/Atom; source coverage and recovery
  visibility for missing, incomplete, outdated or failed content.
- P1: spreadsheet/presentation/structured-data formats when actual consumers
  require them; provider webhooks with durable incremental processing and
  polling fallback; agent-proposed sources approved before recurring ingestion;
  source metadata such as publication date, declared authority, jurisdiction,
  applicability and verification. No universal crawler or automatic trust score.
- Keep remote credentials private and separate from C0 service identities
  (M28). Keep model-based discovery, semantic verification and open-ended
  research outside Core. Continue the existing public-source contract.

**Done when:** real authorized fixtures demonstrate repeatable full/incremental
collection, safe retry, bounded coverage, failed/partial scan preservation,
current-generation citation and readback, revocation during I/O/publication and
credential isolation. SAT and Support are initial acceptance domains; measure
coverage with M24.

### M26 — Retrieval evidence, freshness and compilation

**P0/P1 / validation + planned.** Remaining R2 and compiler M6. Reconcile the
actually installed [retrieval evidence](docs/retrieval-evidence.md) capabilities
(normalized queries, supporting passages and opt-in contextual embeddings)
before changing ranking or indexing. Reuse existing compiler reverse
dependencies, stale detection, policy/fences and external host.

- Use M24's case-level findings to improve source/evidence coverage and
  applicability only where a measured problem exists. Preserve provider-free
  retrieval; separate reindex activation from release.
- Expose impact of changed source generations on Wiki, claims and procedures;
  show coverage against project topics and queue/review supported proposals
  using existing authorized compiler operations. Add review UI without bypassing
  exact-plan approval or replacing authored content.
- Repeat the [failed compiler M6 study](docs/knowledge-compilation/RESULTS.md)
  with an independently frozen real-domain cohort. Test source-only versus
  source-plus-compiled knowledge, exact evidence, citations, applicability,
  clarification/abstention, ranking, latency and cost. Predeclare gates and
  preserve all failures; do not tune against sealed labels.

**Done when:** current dependency and stale signals are correctly surfaced,
review decisions are revision-safe, and the evaluation records whether the
candidate passes. Automatic compilation remains off or queue-only unless the
quality and separate authorized operational rollout gates pass. A failed
experiment is a valid result, not a mandate to keep adding compiler complexity.

### M27 — Verified procedural memory

**P0 / planned.** Former R3, C2. AM0–AM6 are accepted foundations, not
prerequisites to implement again. Reuse typed records, Wiki, exact citations,
structured filters, applicability, verification annotations, M24 outcomes
and M26 dependencies.

- P0: reusable procedure/recipe schema with prerequisites, environment,
  product/version/commit SHA, observed commands/actions, evidence, verification,
  failures/limitations and outcomes; record which retrieved knowledge helped or
  did not help a task. Keep previous observations distinct from current proof.
- P1: episodic session/action/observation records, saved retrieval profiles,
  expiry/supersession/retention policies. Minimize personal and operational
  data; preserve current complete source/Wiki bodies and latest-only evidence
  semantics unless a demonstrated requirement and reviewed contract justify
  a change. Synthesis and context selection remain external.
- Pilot Support Bot, Pointer and Windmill Gate; verify cross-session reuse,
  source applicability and permission boundaries. Gate command filtering and
  command execution are consumer responsibilities, not C0 features.

**Done when:** two independent authorized sessions retrieve an applicable
verified procedure, record a real observed outcome against its revision and
evidence, avoid duplicate/repeated failed work, and distinguish unknown,
reported and verified results. Denied/cross-space, changed-source and replay
cases pass. Do not use feedback as proof or automatically publish new knowledge.

### M28 — Service identities and delegated authorization

**P0/P1 / planned.** Part of former R4, C7. Personal keys currently act as the
creator ([contract](docs/api-keys.md)); introduce non-human service identities
only with a reviewed authority model.

- P0: administrative creation and ownership, selected-space and scope-limited
  service credentials, expiry/rotation, revocation, identity attribution,
  safe recovery and existing personal-key compatibility.
- P1: explicit permissions for hosted apps/workers, delegated space
  administrators without implicit instance-wide access, minimized audit of
  sensitive reads/writes/grants/revocation, and retention/deletion policies for
  selected knowledge classes. Keep provider-owned per-user source credentials
  separate from service accounts.
- Threat-model backup, restore, compromise, grant changes during I/O, blocking,
  admin actions, and migration. No implicit new scopes, resource ACLs or
  claims of strong app isolation under a shared Unix account.

**Done when:** actual PostgreSQL/REST/MCP role/scope/space negatives and
revocation races, rotation, migration and native backup/restore pass; a
separately authorized Support integration uses a non-human identity with
minimum permissions. Do not broaden an existing personal or provider grant.

### M29 — Application hosting platform

**P0/P1 / planned.** Part of former R4, C3. Reuse
[custom application hosting contract 1](docs/custom-applications.md),
the existing digest-pinned CLI, lifecycle, readiness, route and native backup
mechanisms. Keep NS8 operator authority separate from ordinary C0 editors.

- Build a focused management UI for trusted image/manifest configuration,
  private secrets, install/update, start/stop/inspect, health and sanitized
  logs; provide tested reusable application templates and recovery instructions.
  Use M28 service credentials for application enrollment where applicable.
- Verify current hosted Support and cross-space reference capability; add
  browser reference panels only on demonstrated consumer demand and with
  existing authorized summary/read semantics. Do not silently link spaces,
  migrate the reference backend, add a marketplace, arbitrary shell, sidecars
  or claim strong isolation for mutually untrusted applications.
- Validate supported backup/restore and recovery; rollback means the supported
  previous deployment/data recovery procedure, not unsafe automatic image
  rollback after an irreversible data migration.

**Done when:** two trusted fixture apps and the authorized Support consumer
can be provisioned and managed with scoped authority; no secrets leak through
UI/logs; native install/update/backup/restore/restart preserves data, route,
readiness and unrelated modules. Review security and operator recovery.

### M30 — Personal Data Manager

**P1 / draft review.** C8/PDM; not covered by the former R1–R6. Review
[PR 140](https://github.com/Stell0/ns8-czero/pull/140) against current main before
implementing anything. Its published Core 0.50/app 0.68 candidate is a historical
base, not the current consumer. Preserve published migration identities while
reconciling current schema and lock. Reuse its
[personal-data contract in PR 140](https://github.com/Stell0/ns8-czero/pull/140) and validation records
from the draft branch rather than importing a stale implementation blindly.

- Keep opt-in NS8 configuration and immutable owner-bound private spaces;
  NethVoice participated transcripts and summaries, WebTop own-mailbox mail
  and supported attachments, preserving unread state, exclusions and overrides.
  No shared/supervisor leakage or use of service credentials to bypass
  per-user source authority.
- Complete actual consumer full/native proof, authorized synthetic transcript
  and summary readback, larger attachment cases, bounded initial backfill/new
  arrivals and coverage, provider credential renewal/revocation and confirmed
  removal/retirement. Preserve authored knowledge and data during partial
  scans/outages; enforce retention and privacy policy.
- Resolve remaining operator decisions on source credential lifecycle and
  deployment scope. No production personal-content import is authorized by this
  roadmap.

**Done when:** current-source tests prove owner isolation, exact citations,
complete bounded ingestion, cleanup/recovery across restart and partial
coverage, revocation and native upgrade/restore with no leaked private data.
Obtain explicit approval before enabling real personal-data ingestion.

### M31 — Event-driven workflows

**P1 / planned.** Former R5, C3. Reuse existing knowledge change cursors,
project leases, receipts and deterministic scheduling. Add only the missing
authorized event subscription/delivery and shared external-run registry.

- Represent external runs, status, cost, result and outcome (M24/M27) with
  scoped service identities (M28). Provide durable bounded source/knowledge
  change notifications, cursor/replay, deduplication, retry and revocation.
- Keep action dispatch and reasoning in authorized consumers. Prevent duplicate
  scheduled/project runs and automatic cross-space or cross-instance actions.
  Pilot MyProjects and SAT.

**Done when:** a known authorized change causes a single intended consumer
run; retries, restarts, duplicate events, revoked grants and wrong-space
subscribers fail safely; actual outcomes and cost/readback remain inspectable.
No arbitrary server-side prompt or shell execution is introduced.

### M32 — Optional hosted agent runner

**P2 / optional.** Former R6. Begin only if M29/M31 and existing ChatGPT,
Codex, compiler and cron/systemd hosts fail a documented consumer requirement.
Propose a small independent hosted app with an explicit provider, tool/space
permissions, scheduler, lease, budget, cancellation/recovery and run registry.
Do not add general-purpose model execution to Core or a duplicate scheduler.

**Done when (if approved):** bounded external runs obey scope, budget and
idempotency, survive restart/stop, and have independently verified results.
Otherwise record a no-go decision; M32 is not a release prerequisite.

## How development proceeds

Use [AGENTS.md](AGENTS.md), the relevant repository skill, the
[development guide](docs/development.md) and the [CI policy](docs/ci-policy.md).
For every milestone:

1. Fetch original main, freeze exact base and inspect existing code, open PRs,
   migrations, released consumer and accepted runtime records. Reuse or rebase
   instead of duplicating accepted work. Refine scope, dependencies, exclusions,
   threat model and observable acceptance before code.
2. Keep Core reusable; transport, UI and domain apps belong at their proper
   boundaries. Add tests on the base and candidate; test negative controls,
   migration/rollback boundaries, concurrency, retries and recovery as applicable.
3. Review complete diff and affected skills/docs, preserve immutable source,
   evidence and existing waivers. Follow risk-selected checks, regular reviewed
   upstream PR and required C0 merge gate. Do not bypass branch protection.
4. For reusable Core changes, validate/publish the exact Core and independently
   adopt its immutable tag/lock in the consumer; for releases/deployments use
   full native acceptance and separately authorized backup/update/restart.
5. Record what actually passed, failed, remains unverified, exact sources,
   released artifacts and installed identities. Update the active milestone
   state and add concise links to its evidence; never convert a CI pass or a
   source merge into a deployment claim.

The approved mapping is R1 → M22/M25, R2 → M24/M26, R3 → M27,
R4 → M28/M29, R5 → M31 and R6 → M32. M23 and M30 account for pre-existing
unfinished work. Effort/impact estimates are preliminary and should be revised
during the implementation subplan. The C12 F0–F5 domain pilots exercise this
roadmap, not a competing implementation sequence.

## Historical evidence

The previous root plan is preserved **byte-for-byte in Git** at the
[28 November 2026 snapshot](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md) (blob
`de331580a42cbef1cee8c49e86bb65e5eebc1032`). It contains the original development
checkpoints, immutable image and package identities, CI runs, deployment
records, measured limits, failures and old milestone checkboxes. Retrieve it
offline from the repository history with:

```sh
git show 06896a2eb47e5c1aba0ef1016992983ef460a99e:PLAN.md
```

The [older milestone archive](docs/history/PLAN.md) remains in the repository.
Neither archival checkpoint is an active backlog. Existing links into the
previous root plan continue to resolve through the compatibility index below.

<details>
<summary>Historical section links (compatibility index)</summary>

<a id="public-website-collection-and-ingestion-reliability"></a>[Public website collection and ingestion reliability](https://github.com/Stell0/ns8-czero/blob/baa6dbc2fe9ac73ceebf67b63f6f6d36a0e8d63d/PLAN.md#public-website-collection-and-ingestion-reliability)

<a id="c0-grafana-monitoring"></a>[C0 Grafana monitoring](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#c0-grafana-monitoring)

<a id="installed-monitoring-baseline"></a>[Installed monitoring baseline](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#installed-monitoring-baseline)

<a id="protected-pdf-upload-and-recovery"></a>[Protected PDF upload and recovery](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#protected-pdf-upload-and-recovery)

<a id="installed-baseline"></a>[Installed baseline](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#installed-baseline)

<a id="personal-google-drive-automatic-sources"></a>[Personal Google Drive automatic sources](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#personal-google-drive-automatic-sources)

<a id="assistant-setup-and-first-use-experience"></a>[Assistant setup and first-use experience](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#assistant-setup-and-first-use-experience)

<a id="first-browser-walkthrough"></a>[First browser walkthrough](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#first-browser-walkthrough)

<a id="1-measure-the-current-journeys"></a>[1. Measure the current journeys](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#1-measure-the-current-journeys)

<a id="2-make-the-permission-request-match-the-work"></a>[2. Make the permission request match the work](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#2-make-the-permission-request-match-the-work)

<a id="3-shorten-the-website-and-documentation"></a>[3. Shorten the website and documentation](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#3-shorten-the-website-and-documentation)

<a id="4-install-and-prove-each-web-assistant"></a>[4. Install and prove each web assistant](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#4-install-and-prove-each-web-assistant)

<a id="5-acceptance-and-delivery"></a>[5. Acceptance and delivery](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#5-acceptance-and-delivery)

<a id="implementation-evidence"></a>[Implementation evidence](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#implementation-evidence)

<a id="custom-application-hosting-candidate"></a>[Custom application hosting candidate](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#custom-application-hosting-candidate)

<a id="automatic-source-validation-correction"></a>[Automatic source validation correction](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#automatic-source-validation-correction)

<a id="automatic-sources--accepted-source"></a>[Automatic sources — accepted source](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#automatic-sources--accepted-source)

<a id="automatic-sources-accepted-deployment"></a>[Automatic sources accepted deployment](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#automatic-sources-accepted-deployment)

<a id="api-key-expiration-form--implementation-candidate"></a>[API key expiration form — implementation candidate](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#api-key-expiration-form--implementation-candidate)

<a id="self-service-read-and-space-audiences--accepted-source"></a>[Self-service Read and space audiences — accepted source](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#self-service-read-and-space-audiences--accepted-source)

<a id="self-service-read-accepted-deployment"></a>[Self-service Read accepted deployment](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#self-service-read-accepted-deployment)

<a id="native-oauth-accepted-deployment"></a>[Native OAuth accepted deployment](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#native-oauth-accepted-deployment)

<a id="secure-cross-space-references"></a>[Secure cross-space references](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#secure-cross-space-references)

<a id="released-core047-consumer-acceptance"></a>[Released Core0.47 consumer acceptance](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#released-core047-consumer-acceptance)

<a id="released-core047-consumer-candidate"></a>[Released Core0.47 consumer candidate](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#released-core047-consumer-candidate)

<a id="producer-checkpoints-and-measured-evidence"></a>[Producer checkpoints and measured evidence](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#producer-checkpoints-and-measured-evidence)

<a id="released-core046--native-oauth-consumer-candidate"></a>[Released Core0.46 — native OAuth consumer candidate](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#released-core046--native-oauth-consumer-candidate)

<a id="native-oauth-callback-repair"></a>[Native OAuth callback repair](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#native-oauth-callback-repair)

<a id="administration-role-wording"></a>[Administration role wording](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#administration-role-wording)

<a id="retrieval-evidence-producer-candidate"></a>[Retrieval evidence producer candidate](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#retrieval-evidence-producer-candidate)

<a id="document-bm25--released-core-consumer-adoption"></a>[Document BM25 — released Core, consumer adoption](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#document-bm25--released-core-consumer-adoption)

<a id="openai-system-one-scoring--accepted-delivery"></a>[OpenAI System One scoring — accepted delivery](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#openai-system-one-scoring--accepted-delivery)

<a id="knowledge-compilation--m6-controlled-acceptance-candidate"></a>[Knowledge compilation — M6 controlled acceptance candidate](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#knowledge-compilation--m6-controlled-acceptance-candidate)

<a id="knowledge-compilation--m4-producer-candidate"></a>[Knowledge compilation — M4 producer candidate](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#knowledge-compilation--m4-producer-candidate)

<a id="embedding-backlog-drain"></a>[Embedding backlog drain](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#embedding-backlog-drain)

<a id="local-beir-retrieval-benchmark--implementation-candidate"></a>[Local BEIR retrieval benchmark — implementation candidate](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#local-beir-retrieval-benchmark--implementation-candidate)

<a id="knowledge-compilation--m0-accepted-baseline"></a>[Knowledge compilation — M0 accepted baseline](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#knowledge-compilation--m0-accepted-baseline)

<a id="knowledge-compilation--m2-implementation-candidate"></a>[Knowledge compilation — M2 implementation candidate](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#knowledge-compilation--m2-implementation-candidate)

<a id="oauth-connection-usability--implementation-candidate"></a>[OAuth connection usability — implementation candidate](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#oauth-connection-usability--implementation-candidate)

<a id="vue-website--dedicated-installation-accepted"></a>[Vue website — dedicated installation accepted](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#vue-website--dedicated-installation-accepted)

<a id="vue-3-website-remake--source-and-publication-accepted"></a>[Vue 3 website remake — source and publication accepted](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#vue-3-website-remake--source-and-publication-accepted)

<a id="reviewed-candidate-images"></a>[Reviewed candidate images](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#reviewed-candidate-images)

<a id="accepted-merged-main-images"></a>[Accepted merged-main images](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#accepted-merged-main-images)

<a id="personal-api-keys--released-consumer-accepted"></a>[Personal API keys — released consumer accepted](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#personal-api-keys--released-consumer-accepted)

<a id="queued-document-extraction--implementation-merged"></a>[Queued document extraction — implementation merged](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#queued-document-extraction--implementation-merged)

<a id="ingestion-deployed-runtime-and-frozen-predecessor--4-november-2026"></a>[Ingestion deployed runtime and frozen predecessor — 4 November 2026](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#ingestion-deployed-runtime-and-frozen-predecessor--4-november-2026)

<a id="ci-policy-update--implementation"></a>[CI policy update — implementation](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#ci-policy-update--implementation)

<a id="nebula-website-redesign--implementation-candidate"></a>[Nebula website redesign — implementation candidate](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#nebula-website-redesign--implementation-candidate)

<a id="released-core-adoption-candidate"></a>[Released-Core adoption candidate](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#released-core-adoption-candidate)

<a id="agentic-retrieval-workflow-development"></a>[Agentic retrieval workflow (development)](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#agentic-retrieval-workflow-development)

<a id="bounded-natural-language-retrieval-candidate"></a>[Bounded natural-language retrieval candidate](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#bounded-natural-language-retrieval-candidate)

<a id="operational-documentation-and-retrieval-tooling"></a>[Operational documentation and retrieval tooling](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#operational-documentation-and-retrieval-tooling)

<a id="active-latest-only-storage-and-reusable-website-crawler"></a>[Active: latest-only storage and reusable website crawler](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#active-latest-only-storage-and-reusable-website-crawler)

<a id="full-documents-in-knowledge-explorer--implementation-in-progress"></a>[Full documents in Knowledge Explorer — implementation in progress](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#full-documents-in-knowledge-explorer--implementation-in-progress)

<a id="full-document-development-checkpoint"></a>[Full-document development checkpoint](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#full-document-development-checkpoint)

<a id="corrected-core-native-synchronization"></a>[Corrected Core native synchronization](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#corrected-core-native-synchronization)

<a id="directory-scale-regression-before-core-publication"></a>[Directory scale regression before Core publication](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#directory-scale-regression-before-core-publication)

<a id="published-core-and-application-adoption"></a>[Published Core and application adoption](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#published-core-and-application-adoption)

<a id="project-plugin-12-acceptance-repair"></a>[Project plugin 1.2 acceptance repair](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#project-plugin-12-acceptance-repair)

<a id="inherited-authlib-security-prerequisite"></a>[Inherited Authlib security prerequisite](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#inherited-authlib-security-prerequisite)

<a id="seven-day-remembered-website-login--deployed-acceptance"></a>[Seven-day remembered website login — deployed acceptance](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#seven-day-remembered-website-login--deployed-acceptance)

<a id="remembered-login-deployed-runtime-and-frozen-predecessor"></a>[Remembered login deployed runtime and frozen predecessor](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#remembered-login-deployed-runtime-and-frozen-predecessor)

<a id="active-work-and-remaining-acceptance"></a>[Active work and remaining acceptance](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#active-work-and-remaining-acceptance)

<a id="historical-reusable-ingestion-samples-checkpoint"></a>[Historical reusable ingestion samples checkpoint](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#historical-reusable-ingestion-samples-checkpoint)

<a id="agent-instruction-maintenance--11-november-2026"></a>[Agent instruction maintenance — 11 November 2026](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#agent-instruction-maintenance--11-november-2026)

<a id="protected-pdf-uploads-and-retries"></a>[Protected PDF uploads and retries](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#protected-pdf-uploads-and-retries)

<a id="historical-remembered-login-baseline"></a>[Historical remembered-login baseline](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#historical-remembered-login-baseline)

<a id="operator-priority--people-first-workspace-access-24-october-2026"></a>[Operator priority — people-first workspace access (24 October 2026)](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#operator-priority--people-first-workspace-access-24-october-2026)

<a id="approved-people-first-workspace-access-page"></a>[Approved people-first Workspace Access page](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#approved-people-first-workspace-access-page)

<a id="accepted-runtime-and-promotion--24-october-2026"></a>[Accepted runtime and promotion — 24 October 2026](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#accepted-runtime-and-promotion--24-october-2026)

<a id="dedicated-instance-acceptance-and-frozen-predecessor"></a>[Dedicated-instance acceptance and frozen predecessor](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#dedicated-instance-acceptance-and-frozen-predecessor)

<a id="existing-model"></a>[Existing model](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#existing-model)

<a id="proposed-presentation"></a>[Proposed presentation](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#proposed-presentation)

<a id="action-semantics"></a>[Action semantics](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#action-semantics)

<a id="missing-api-support-and-proposed-additions"></a>[Missing API support and proposed additions](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#missing-api-support-and-proposed-additions)

<a id="implementation-and-acceptance-after-agreement"></a>[Implementation and acceptance after agreement](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#implementation-and-acceptance-after-agreement)

<a id="implementation-checkpoint--24-october"></a>[Implementation checkpoint — 24 October](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#implementation-checkpoint--24-october)

<a id="native-findings-and-corrections"></a>[Native findings and corrections](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#native-findings-and-corrections)

<a id="settled-implementation-interfaces"></a>[Settled implementation interfaces](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#settled-implementation-interfaces)

<a id="earlier-roadmap-checkpoint"></a>[Earlier roadmap checkpoint](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#earlier-roadmap-checkpoint)

<a id="operator-priority--persistent-oauth-connections-23-october-2026"></a>[Operator priority — persistent OAuth connections (23 October 2026)](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#operator-priority--persistent-oauth-connections-23-october-2026)

<a id="current-checkpoint"></a>[Current checkpoint](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#current-checkpoint)

<a id="current-installed-runtime"></a>[Current installed runtime](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#current-installed-runtime)

<a id="delivery-loop"></a>[Delivery loop](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#delivery-loop)

<a id="m21--documentation-and-skills-release-readiness"></a>[M21 — Documentation and skills release readiness](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#m21--documentation-and-skills-release-readiness)

<a id="implementation-checklist"></a>[Implementation checklist](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#implementation-checklist)

<a id="later-phases"></a>[Later phases](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#later-phases)

<a id="m21-implementation-checkpoint--21-october-2026"></a>[M21 implementation checkpoint — 21 October 2026](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#m21-implementation-checkpoint--21-october-2026)

<a id="m21-real-web-feedback-and-correction--22-october-2026"></a>[M21 real-web feedback and correction — 22 October 2026](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#m21-real-web-feedback-and-correction--22-october-2026)

<a id="m21-follow-up--simple-self-service-chatgpt-onboarding"></a>[M21 follow-up — Simple self-service ChatGPT onboarding](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#m21-follow-up--simple-self-service-chatgpt-onboarding)

<a id="m21-self-service-implementation-checkpoint"></a>[M21 self-service implementation checkpoint](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#m21-self-service-implementation-checkpoint)

<a id="wikiplant-backend-track--m0-inspection"></a>[WikiPlant backend track — M0 inspection](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#wikiplant-backend-track--m0-inspection)

<a id="wikiplant-m1--project-foundation-implementation-checkpoint"></a>[WikiPlant M1 — project foundation (implementation checkpoint)](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#wikiplant-m1--project-foundation-implementation-checkpoint)

<a id="wikiplant-m2--common-source-ingestion-checkpoint"></a>[WikiPlant M2 — common source ingestion checkpoint](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#wikiplant-m2--common-source-ingestion-checkpoint)

<a id="wikiplant-m2-accepted-source-and-m3-transaction-subplan"></a>[WikiPlant M2 accepted source and M3 transaction subplan](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#wikiplant-m2-accepted-source-and-m3-transaction-subplan)

<a id="wikiplant-m3-acceptance-and-m4-monitoring-subplan"></a>[WikiPlant M3 acceptance and M4 monitoring subplan](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#wikiplant-m3-acceptance-and-m4-monitoring-subplan)

<a id="wikiplant-m5-evidence-and-reporting-subplan-gated"></a>[WikiPlant M5 evidence and reporting subplan (gated)](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#wikiplant-m5-evidence-and-reporting-subplan-gated)

<a id="wikiplant-m5-implemented-exact-acceptance-pending"></a>[WikiPlant M5 implemented; exact acceptance pending](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#wikiplant-m5-implemented-exact-acceptance-pending)

<a id="wikiplant-m5-accepted-m6-implementation"></a>[WikiPlant M5 accepted; M6 implementation](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#wikiplant-m5-accepted-m6-implementation)

<a id="wikiplant-m6-accepted-m7-implementation"></a>[WikiPlant M6 accepted; M7 implementation](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#wikiplant-m6-accepted-m7-implementation)

<a id="wikiplant-m7-accepted-m8-final-acceptance"></a>[WikiPlant M7 accepted; M8 final acceptance](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#wikiplant-m7-accepted-m8-final-acceptance)

<a id="wikiplant-m8-prepublication-accepted-released-core-adoption"></a>[WikiPlant M8 prepublication accepted; released Core adoption](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#wikiplant-m8-prepublication-accepted-released-core-adoption)

<a id="wikiplant-deployed-backend-and-frozen-predecessor"></a>[WikiPlant deployed backend and frozen predecessor](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#wikiplant-deployed-backend-and-frozen-predecessor)

<a id="api-key-producer-acceptance-and-released-core"></a>[API-key producer acceptance and released Core](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#api-key-producer-acceptance-and-released-core)

<a id="api-key-released-consumer-acceptance"></a>[API-key released-consumer acceptance](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#api-key-released-consumer-acceptance)

<a id="structured-record-browsing-core-producer"></a>[Structured record browsing Core producer](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#structured-record-browsing-core-producer)

<a id="generic-structured-tables--accepted-source-delivery"></a>[Generic structured tables — accepted source delivery](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#generic-structured-tables--accepted-source-delivery)

<a id="final-table-browser-acceptance--13-november-2026"></a>[Final table browser acceptance — 13 November 2026](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#final-table-browser-acceptance--13-november-2026)

<a id="generic-tables-accepted-deployment"></a>[Generic tables accepted deployment](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#generic-tables-accepted-deployment)

<a id="c0-implementation-plan--milestone-by-milestone-codex-handoff"></a>[C0 implementation plan — milestone-by-milestone Codex handoff](docs/history/PLAN.md#c0-implementation-plan--milestone-by-milestone-codex-handoff)

<a id="product-contract-do-not-quietly-change"></a>[Product contract (do not quietly change)](docs/history/PLAN.md#product-contract-do-not-quietly-change)

<a id="source-precedence-and-selection"></a>[Source precedence and selection](docs/history/PLAN.md#source-precedence-and-selection)

<a id="non-negotiable-execution-loop-for-every-milestone"></a>[Non-negotiable execution loop for EVERY milestone](docs/history/PLAN.md#non-negotiable-execution-loop-for-every-milestone)

<a id="tests-and-ci-conventions"></a>[Tests and CI conventions](docs/history/PLAN.md#tests-and-ci-conventions)

<a id="milestones"></a>[Milestones](docs/history/PLAN.md#milestones)

<a id="m00--rebrand-kickstart-create-working-ci-and-smoke-test-the-module-x"></a>[M00 — Rebrand kickstart, create working CI and smoke-test the module x](docs/history/PLAN.md#m00--rebrand-kickstart-create-working-ci-and-smoke-test-the-module-x)

<a id="m01--minimal-python-runtime-web-ui-and-coreapplication-separation-x"></a>[M01 — Minimal Python runtime, Web UI and Core/application separation x](docs/history/PLAN.md#m01--minimal-python-runtime-web-ui-and-coreapplication-separation-x)

<a id="m02--ns8-configuration-traefik-and-administrator-ui-x"></a>[M02 — NS8 configuration, Traefik and administrator UI x](docs/history/PLAN.md#m02--ns8-configuration-traefik-and-administrator-ui-x)

<a id="m03--dedicated-postgresql--pgvector-and-migrations-x"></a>[M03 — Dedicated PostgreSQL + pgvector and migrations x](docs/history/PLAN.md#m03--dedicated-postgresql--pgvector-and-migrations-x)

<a id="m04--backup-restore-and-upgrade-safe-persistence-x"></a>[M04 — Backup, restore and upgrade-safe persistence x](docs/history/PLAN.md#m04--backup-restore-and-upgrade-safe-persistence-x)

<a id="m05--ns8-idp-login-and-minimal-application-wide-authorization-x"></a>[M05 — ns8-idp login and minimal application-wide authorization x](docs/history/PLAN.md#m05--ns8-idp-login-and-minimal-application-wide-authorization-x)

<a id="m06--deterministic-jobs-and-database-backed-scheduler-x"></a>[M06 — Deterministic jobs and database-backed scheduler x](docs/history/PLAN.md#m06--deterministic-jobs-and-database-backed-scheduler-x)

<a id="m07--generic-application-object-model-and-reusable-crud-x"></a>[M07 — Generic application object model and reusable CRUD x](docs/history/PLAN.md#m07--generic-application-object-model-and-reusable-crud-x)

<a id="m08--source-ingestion-text-extraction-and-chunk-storage-x"></a>[M08 — Source ingestion, text extraction and chunk storage x](docs/history/PLAN.md#m08--source-ingestion-text-extraction-and-chunk-storage-x)

<a id="m09--versioned-wiki-entities-claims-provenance-and-postgresql-graph-x"></a>[M09 — Versioned Wiki, entities, claims, provenance and PostgreSQL graph x](docs/history/PLAN.md#m09--versioned-wiki-entities-claims-provenance-and-postgresql-graph-x)

<a id="m10--full-text-vectors-external-embeddings-and-jevkev-system-one-rag-x"></a>[M10 — Full-text, vectors, external embeddings and Jev/Kev System One RAG x](docs/history/PLAN.md#m10--full-text-vectors-external-embeddings-and-jevkev-system-one-rag-x)

<a id="m11--restmcp-parity-oauth-interoperability-and-agents-discovery-x"></a>[M11 — REST/MCP parity, OAuth interoperability and /agents discovery x](docs/history/PLAN.md#m11--restmcp-parity-oauth-interoperability-and-agents-discovery-x)

<a id="m12--full-c0-user-ui-and-ns8-configuration-experience-x"></a>[M12 — Full C0 user UI and NS8 configuration experience x](docs/history/PLAN.md#m12--full-c0-user-ui-and-ns8-configuration-experience-x)

<a id="m13--fork-upgrades-c0-core-distribution-and-upstream-contribution-skills-x"></a>[M13 — Fork upgrades, C0 Core distribution and upstream contribution skills x](docs/history/PLAN.md#m13--fork-upgrades-c0-core-distribution-and-upstream-contribution-skills-x)

<a id="m14--end-to-end-hardening-compatibility-and-release-gate-x"></a>[M14 — End-to-end hardening, compatibility and release gate x](docs/history/PLAN.md#m14--end-to-end-hardening-compatibility-and-release-gate-x)

<a id="after-m14"></a>[After M14](docs/history/PLAN.md#after-m14)

<a id="current-next-action"></a>[Current next action](docs/history/PLAN.md#current-next-action)

<a id="m15--reader-first-knowledge-website-x"></a>[M15 — Reader-first knowledge website x](docs/history/PLAN.md#m15--reader-first-knowledge-website-x)

<a id="chatgpt-mcp-integration--operator-plan-15-october-2026"></a>[ChatGPT MCP integration — operator plan (15 October 2026)](docs/history/PLAN.md#chatgpt-mcp-integration--operator-plan-15-october-2026)

<a id="integration-m15--oauth-authorization-parameter-compatibility-x"></a>[Integration M15 — OAuth authorization parameter compatibility x](docs/history/PLAN.md#integration-m15--oauth-authorization-parameter-compatibility-x)

<a id="integration-m16--mcp-authentication-metadata-and-permission-upgrades-x"></a>[Integration M16 — MCP authentication metadata and permission upgrades x](docs/history/PLAN.md#integration-m16--mcp-authentication-metadata-and-permission-upgrades-x)

<a id="integration-m20--renewable-browser-and-delegated-sessions--"></a>[Integration M20 — Renewable browser and delegated sessions](docs/history/PLAN.md#integration-m20--renewable-browser-and-delegated-sessions--)

<a id="m20-main-recovery-fixture-correction--20-october-2026"></a>[M20 main recovery-fixture correction — 20 October 2026](docs/history/PLAN.md#m20-main-recovery-fixture-correction--20-october-2026)

<a id="m20-corrected-runtime-closeout--20-october-2026"></a>[M20 corrected runtime closeout — 20 October 2026](docs/history/PLAN.md#m20-corrected-runtime-closeout--20-october-2026)

<a id="integration-m17--profile-identity-closed"></a>[Integration M17 — Profile identity (closed)](docs/history/PLAN.md#integration-m17--profile-identity-closed)

<a id="m17-deployed-acceptance-and-closeout--20-october-2026"></a>[M17 deployed acceptance and closeout — 20 October 2026](docs/history/PLAN.md#m17-deployed-acceptance-and-closeout--20-october-2026)

<a id="integration-m18--tool-guidance-accepted-and-closed"></a>[Integration M18 — Tool guidance (accepted and closed)](docs/history/PLAN.md#integration-m18--tool-guidance-accepted-and-closed)

<a id="m18-executed-evidence-and-closeout--20-october-2026"></a>[M18 executed evidence and closeout — 20 October 2026](docs/history/PLAN.md#m18-executed-evidence-and-closeout--20-october-2026)

<a id="integration-sequence-after-m20"></a>[Integration sequence after M20](docs/history/PLAN.md#integration-sequence-after-m20)

<a id="structured-object-creation-repair--active-operator-task"></a>[Structured object creation repair — active operator task](docs/history/PLAN.md#structured-object-creation-repair--active-operator-task)

<a id="m1--root-cause-and-regression-reproduction-x"></a>[M1 — Root cause and regression reproduction x](docs/history/PLAN.md#m1--root-cause-and-regression-reproduction-x)

<a id="m2--minimal-implementation-fix-x"></a>[M2 — Minimal implementation fix x](docs/history/PLAN.md#m2--minimal-implementation-fix-x)

<a id="m3--complete-validated-crud-regression-x"></a>[M3 — Complete validated CRUD regression x](docs/history/PLAN.md#m3--complete-validated-crud-regression-x)

<a id="c0-agent-memory--additional-operator-track"></a>[C0 Agent Memory — additional operator track](docs/history/PLAN.md#c0-agent-memory--additional-operator-track)

<a id="c0-am0--baseline-and-compatibility-contracts-x"></a>[C0-AM0 — Baseline and compatibility contracts x](docs/history/PLAN.md#c0-am0--baseline-and-compatibility-contracts-x)

<a id="c0-am1--mcp-native-text-evidence-ingestion-x"></a>[C0-AM1 — MCP-native text evidence ingestion x](docs/history/PLAN.md#c0-am1--mcp-native-text-evidence-ingestion-x)

<a id="c0-am2--agent-friendly-wiki-operations-and-errors-x"></a>[C0-AM2 — Agent-friendly Wiki operations and errors x](docs/history/PLAN.md#c0-am2--agent-friendly-wiki-operations-and-errors-x)

<a id="c0-am3--protected-knowledge-spaces-x"></a>[C0-AM3 — Protected knowledge spaces x](docs/history/PLAN.md#c0-am3--protected-knowledge-spaces-x)

<a id="c0-am4--scoped-and-structured-knowledge-retrieval-x"></a>[C0-AM4 — Scoped and structured knowledge retrieval x](docs/history/PLAN.md#c0-am4--scoped-and-structured-knowledge-retrieval-x)

<a id="c0-am5--reliable-consolidation-and-maintenance-primitives-x"></a>[C0-AM5 — Reliable consolidation and maintenance primitives x](docs/history/PLAN.md#c0-am5--reliable-consolidation-and-maintenance-primitives-x)

<a id="c0-am6--agent-documentation-and-integration-tests-x"></a>[C0-AM6 — Agent documentation and integration tests x](docs/history/PLAN.md#c0-am6--agent-documentation-and-integration-tests-x)

<a id="final-c0-am-deployment-gate-x"></a>[Final C0-AM deployment gate x](docs/history/PLAN.md#final-c0-am-deployment-gate-x)

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

<a id="automatic-sources--released-consumer-candidate"></a>[automatic sources  released consumer candidate](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#automatic-sources--released-consumer-candidate)

<a id="self-service-read-and-space-audiences--released-consumer-candidate"></a>[self service read and space audiences  released consumer candidate](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#self-service-read-and-space-audiences--released-consumer-candidate)

<a id="openai-system-one-scoring--current-base-successor"></a>[openai system one scoring  current base successor](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#openai-system-one-scoring--current-base-successor)

<a id="active-implementation--reusable-ingestion-samples"></a>[active implementation  reusable ingestion samples](https://github.com/Stell0/ns8-czero/blob/06896a2eb47e5c1aba0ef1016992983ef460a99e/PLAN.md#active-implementation--reusable-ingestion-samples)

</details>
