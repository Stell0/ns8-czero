# C0 / ns8-czero — Instructions for coding agents

C0 is a self-hosted shared knowledge service and a reusable application base.
External assistants reason; C0 stores evidence and runs deterministic registered
operations. Keep reading, connection setup and administration understandable to
nontechnical users. Read [README](README.md) for the product boundary.

## Start here

- Read [PLAN's roadmap](PLAN.md#roadmap), the relevant active work record and the
  skill below before editing. Use manifests and locks for source versions,
  [CI policy](docs/ci-policy.md) for checks, and [PLAN's current baseline](PLAN.md#current-baseline)
  for installed images and genuine upgrade predecessors. Merging source or
  publishing Core does not upgrade an instance.
- Verify the original remote is `https://github.com/Stell0/ns8-czero`, fetch its
  latest `main` and start from that exact source in an isolated worktree. A fork's
  `origin/main` is not proof of freshness. Preserve dirty files, customizations,
  unfinished worktrees and drafts.
- Fetch and rebase before opening a PR and whenever the base advances. Resolve
  locks, migrations and managed-file comparisons semantically and rerun affected
  checks. Preserve frozen review/publication/deployment commits and evidence;
  use a successor branch if rebasing would rewrite them. Never retag immutable
  images or force-push away accepted evidence.
- Inspect callers and existing services before implementation. Settle behavior,
  interfaces, compatibility and acceptance; follow the [shared implementation
  practices](.agents/references/development.md#implementation-practices).

## Put changes in the right place

| Layer | Responsibility |
| --- | --- |
| `packages/czero-core` | Reusable domain services, persisted authorization, transactions and migrations |
| `app` | Reference/fork UI and HTTP/MCP transport using trusted Core operations |
| `imageroot`, `ui` | Numbered NS8 lifecycle operations and native Vue 2/Carbon settings |
| `plugins/c0-knowledge` | Instance-bound end-user instructions and packages |
| `.agents/skills`, `docs` | Developer workflows and public guidance; never runtime instruction assets |

Keep fork branding and workflows in the application. Reuse existing records and
services. Forks consume released Core with a frozen lock; `CZERO_CORE_SOURCE=local`
is explicit producer development, never a fallback. Preserve independent Core
releases and consumer acceptance, patch-only updater bounds, fork registry identities
and the explicit `c0-upstream.json` registry. See [fork and publishing rules](docs/development.md#forks-and-upstream-updates).

## Choose the relevant workflow

| Work | Skill |
| --- | --- |
| Application feature | [c0-create-feature](.agents/skills/c0-create-feature/SKILL.md) |
| Core services, migrations or packaging | [c0-develop-core](.agents/skills/c0-develop-core/SKILL.md) |
| Reusable upstream contribution | [c0-contribute-upstream](.agents/skills/c0-contribute-upstream/SKILL.md) |
| Core or managed-file upgrade | [c0-upgrade-from-upstream](.agents/skills/c0-upgrade-from-upstream/SKILL.md) |
| Grounded evaluation questions | [c0-generate-retrieval-questions](.agents/skills/c0-generate-retrieval-questions/SKILL.md) |
| Managed semantic knowledge | [c0-maintain-semantic-layer](.agents/skills/c0-maintain-semantic-layer/SKILL.md) |
| Agentic retrieval benchmark | [c0-benchmark-agentic-retrieval](.agents/skills/c0-benchmark-agentic-retrieval/SKILL.md) |
| Tool-use evaluation | [c0-evaluate-tools](.agents/skills/c0-evaluate-tools/SKILL.md) |
| External-source ingestion | [c0-ingest-sources](.agents/skills/c0-ingest-sources/SKILL.md) |
| Protected projects and agent handoff | [c0-project-workflows](.agents/skills/c0-project-workflows/SKILL.md) |

Use installed [NethServer skills](https://github.com/NethServer/agents) for native
module/container work, administration, commits, PRs and releases; use Nebula for
frontend work. Skills describe workflows, not authority. Before changing a feature,
read its [contract and acceptance requirements](docs/development.md#feature-contracts).

## Preserve these boundaries

- Core checks current persisted roles, explicit spaces and actual delegated scopes
  inside transactions. Preserve lock order, revisions, evidence identities and
  payload-free replay receipts. A denied space never falls back to Shared;
  discovered tools, metadata and references confer no authority.
- Source documents and Wiki pages are latest-only. Stage replacements privately,
  validate and publish complete documents atomically, and remove superseded bodies
  and indirect copies. Expired exact evidence returns authorized
  `content_superseded` (410); preserve authored knowledge and mark stale evidence.
- OAuth consent, application approval, user permissions, browser logout, exact
  connection disconnect and persistent blocking remain distinct. Never broaden
  scopes or promote old grants silently. See [identity contracts](docs/development.md#identity-and-access).
- Knowledge views are readers; source controls are the explicit mutation exception.
  Preserve account/space response guards, safe rendering and local assets. Optional
  providers cannot decide authorization or make ordinary text retrieval unavailable.
- Keep credentials, instance jobs, real datasets and failed/private traces outside
  Git. Reuse [ingestion samples](samples/ingestion/README.md); save real jobs under
  ignored `.local/ingestion/<job>/`. Ingestion, discovery and generated packages
  never authorize extra schedules or production changes.

## Tests are part of the feature

Follow [CI policy](docs/ci-policy.md) on the exact latest original main and candidate;
use [development commands](docs/development.md#local-verification). Every PR receives
fast checks. Sensitive/unknown ready PRs require full Debian/Rocky acceptance;
Git-only docs and reviewed allowlisted presentation changes use their selected
checks. Full native proof remains mandatory for releases, canonical publication
and deployment. Database skips are not a pass.

Test observable behavior and affected authorization, revision/retry, migration,
recovery and browser contracts. Retain feature regressions across rebases and Core
upgrades. Never weaken tests or widen dependency ranges to obtain a pass, share
mutable test databases, or cancel frozen full/native runs. The interactive
Playwright and container CPU-quota waivers remain: do not add `--cpus=2`, change
host delegation or claim CPU-rate enforcement; automated browsers and other
resource/deadline checks remain required.

## Review and deliver

Isolate reusable improvements and **open an upstream PR** against original `main`
after checks pass. Keep private/application-specific changes in the fork. Use
`c0-contribute-upstream` and `nethserver-pr`; assign no unsolicited reviewer.

Before readiness, review the complete diff, AGENTS and affected developer/end-user
skills. Update changed contracts and references together, verify affected package
inventories, and complete the PR template's instruction-review declaration. Record
updated paths or “no instruction changes needed” with a reason, exact source/base,
selected acceptance and results. Recheck after source/base changes. Connector
changes also require [actual connection and tool verification](docs/development.md#plugins-and-connectors).

C0 permits agent review and requires no separate human approval to merge. Resolve
feedback and enable **regular** auto-merge with
`gh pr merge <number> --auto --merge --match-head-commit <full-head-sha>`.
Require the current Actions-owned `C0 merge gate` and all selected checks; no admin
bypass or force push. For direct merges run `scripts/verify-promotion.py --source
<full-head-sha> --pr <number>`; release/deployment verification requires `--full`.

Live deployment still needs explicit authorization and the [supported backup,
preservation, restart and privacy acceptance](docs/ci-policy.md#deployment-and-milestones).
Documentation-only changes never replace installed images.

## Keep this file small

Keep only standing rules and routing here. Put feature details in their contract
or [development guide](docs/development.md), task procedures in skills, and versions,
run IDs, deployment results and milestone narratives in [PLAN](PLAN.md). Link to
that source instead of copying it. Remove superseded guidance; retain historical
evidence in [the archive](docs/history/AGENTS.md) and Git history. Historical
“current” or “pending” statements describe their checkpoint, not today's state.

<details>
<summary>Legacy section links</summary>

These anchors retain incoming links to [archived instructions](docs/history/AGENTS.md).

<a id="latest-only-source-acceptance"></a><a id="accepted-baseline-and-preserved-evidence"></a><a id="accepted-people-first-access--24-october-2026"></a>
<a id="current-work-and-preservation"></a><a id="research-project-development-track"></a><a id="wikiplant-project-source-conventions"></a>
<a id="research-workflow-coordination-conventions"></a><a id="primary-monitoring-and-project-agent-conventions"></a><a id="project-evidence-and-reporting-conventions"></a>
<a id="project-maintenance-conventions"></a><a id="project-exportpreparation-conventions"></a><a id="wikiplant-m8-distributionfinal-acceptance"></a>
<a id="wikiplant-backend-deployed-acceptance--27-october-2026"></a><a id="remembered-website-acceptance--27-october-2026"></a><a id="full-document-explorer-candidate"></a>
<a id="personal-api-keys"></a><a id="openai-system-one-accepted-delivery"></a><a id="authoritative-development-ci-policy"></a>
<a id="m19-accepted-runtime-conventions"></a><a id="historical-m17-implementation-entry"></a><a id="m20-runtime-and-corrected-main-acceptance-historical-closeout-checkpoint"></a>
<a id="historical-m20-resumption-and-correction-evidence"></a><a id="am6-accepted-implementation-m20-preserved"></a><a id="protected-knowledge-spaces-am3-runtime-accepted"></a>
<a id="accepted-m18-guidance-checkpoint--21-october-2026"></a><a id="accepted-m17-profile-checkpoint--20-october-2026"></a><a id="m15-reader-ui-conventions-accepted-candidate"></a>
<a id="active-chatgpt-integration-plan"></a><a id="integration-m16-implementation-conventions-accepted"></a><a id="established-m14-conventions"></a>
<a id="established-m13-distribution-conventions"></a><a id="established-m12-ui-conventions"></a><a id="established-m11-operation-conventions"></a>
<a id="established-m10-retrieval-conventions"></a><a id="established-m09-wikigraph-conventions"></a><a id="established-m08-ingestion-conventions"></a>
<a id="established-m07-object-contracts"></a><a id="established-m06-queueworker-contracts"></a><a id="established-m05-identity-conventions"></a>
<a id="established-m04-backuprestore-conventions"></a><a id="established-m03-database-conventions"></a><a id="established-m02-configuration-conventions"></a>
<a id="established-m01-conventions"></a><a id="established-m00-conventions"></a><a id="mission-and-boundaries"></a>
<a id="source-hierarchy-reuse-before-implementing"></a><a id="keep-ns8-actions-readable"></a><a id="runtime-design-invariants"></a>
<a id="mandatory-milestone-loop"></a><a id="definition-of-done-for-any-change"></a><a id="completed-structured-object-repair"></a>
<a id="structured-object-repair-accepted-runtime"></a><a id="c0-agent-memory-track"></a><a id="am3-released-core-and-application-conventions-pending-acceptance"></a>
<a id="am4-applicability-and-structured-retrieval-runtime-accepted"></a><a id="am5-consolidation-implementation-conventions"></a><a id="am5-runtime-acceptance-18-october-2026"></a>
<a id="scoped-ci-policy-accepted-sources"></a><a id="instruction-checkpoint--11-november-2026"></a>

</details>
