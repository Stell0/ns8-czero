# C0 / ns8-czero — Instructions for coding agents

The accepted dedicated runtime is app **0.67.0**, released Core **0.49.0**,
schema **0039**, source `72fbdfe7c9be13351359ae240ffc72dde654fab0`.
Its separately authorized table-browser deployment passes supported backup,
immutable update, restart, preservation and live connection/privacy checks.
Core remains immutable at `998ef32b6eedb545e6e4c0eb7ebb468e19ea3ddb`.
Preserve the installed image identities and genuine app0.66/Core0.48 predecessor
in [PLAN's current baseline](PLAN.md#current-baseline). Future deployments still
need explicit authorization; documentation-only heads never replace these images.

Self-service Read and space audiences were accepted in app0.66 / released
Core0.48.0 / schema0039 / plugin1.11. Core is immutable at
`2f40ffeb2acac807f485f7bde7f97651e7d9d8bf`; preserve its exact package tree,
released Git tag/lock and patch-only updater bounds. PR130 regularly merges as
`145d144725f748b8a168aefce72b0f866bbe820e`. Consumer full43220620934 and actual
main full43229872256, canonical publication, independent artifact/promotion checks
and six fresh registry reads pass. Producer43209361920 and publisher43218817753
remain separate evidence. Preserve explicit blocks, disabled clients, metadata
review and credential ceilings; baseline audience access is Read only. Existing
protected spaces remain restricted, and the discovery switch is retired on
upgrade/restore. The separately authorized deployment and one requested space
audience change pass supported backup/update/restart, preservation and live
connection/privacy checks. See PLAN for the installed immutable identities and
genuine app0.64/Core0.46 predecessor. Preserve all failed candidates and private
evidence. Further deployments or audience changes need their own authorization.

Person-role selectors and saved summaries use cumulative labels: **Read**,
**Read and write**, **Read, write and manage**. Preserve single role selection and
independent application consent scopes; do not reuse role labels for scopes.

API key creation defaults to 90 days, with a visible 1–365-day range. No expiration
requires the explicit Never expires choice; blank input must not imply indefinite
authority. Preserve the existing nullable lifetime API and current scope/space,
permission-revision and revocation checks.

Cross-space references complete M0–M4: [contract](docs/cross-space-references-plan.md)
and [released-consumer acceptance](PLAN.md#released-core047-consumer-acceptance).
Core0.47/schema0038 and plugin1.10 support five stable endpoint kinds with outgoing
summaries and explicit source/target selectors. References confer neither authority
nor evidence. Preserve identity-only edges, current both-endpoint read checks,
blind source-owned deletion, credential bindings and revocation lock order.
App0.65 adopts released Core0.47.0 at
`884ff312c18fbc18bb613137bbb6ced17df6cfb0`, with matching patch-only updater bounds.
Keep the current Core tree identical to its active immutable consumer release;
preserve earlier producer/consumer candidates and native evidence. Main0daf8a0 passes full/
native acceptance, canonical publication, independent artifact/promotion checks
and six fresh registry reads. The accepted app0.66 installation includes this
dependency through Core0.48; retain its earlier source/publication evidence. Browser reference panels remain
separate work. See [PLAN's current baseline](PLAN.md#current-baseline).

## Current state and precedence

Use active manifests and locks for source/dependency versions, the
[CI policy](docs/ci-policy.md) for required checks, and
[PLAN's current baseline](PLAN.md#current-baseline) for the accepted installation
and its genuine predecessor. These are separate identities: a source merge or
published library does not upgrade an instance. The
[installation guide](docs/installation-candidate.md) selects a verified published
candidate. Historical “current” and “pending” wording describes its checkpoint,
not present instructions. Preserve all frozen commits, tags, digests and failed
or private evidence; never replace accepted runtime identities with documentation images.

## Product purpose

C0 is a self-hosted, shared second brain for people and AI assistants, and a foundation for applications built around that knowledge. Read [README](README.md) for the product story and [PLAN](PLAN.md#roadmap) for the current roadmap and acceptance order.

The product develops the LLM Wiki idea into a durable service: preserve original evidence, maintain connected Wiki knowledge, retrieve it through indexed APIs, and let multiple authorized users and assistants work on it. Its second purpose is reuse: a fork should start with working knowledge storage, access control, REST/MCP, UI, skills and delivery tooling. “LAMP for AI” describes this starting-stack ambition; it is not a promise of a hosted model or an autonomous agent runtime.

Changes should strengthen one of those two paths: **use the shared knowledge service**, or **build an application on the reusable base**. Keep ordinary reading, connection setup and administration understandable to nontechnical users.

## Start from the latest original C0 main

The original C0 repository is `https://github.com/Stell0/ns8-czero`. At the start of every task, verify the original remote, fetch its latest `main`, and check out that exact source in an isolated worktree. In a fork, a local or fork `origin/main` is not proof that original C0 is current. Preserve dirty files and application customizations rather than resetting an existing checkout.

Keep development branches rebased on the latest original C0 `main`. Fetch and rebase before opening a PR and whenever that base advances; resolve conflicts semantically, preserve the fork's feature tests, and rerun validation. Do not claim compatibility because the rebase command completed. Inspect and resolve dependency locks, migrations and managed-file comparison state too.

Once a source is frozen for review, publication or deployment, preserve its commits, evidence and immutable image identities. If keeping current requires rewriting frozen history, retain that candidate and produce a new rebased candidate on a separate branch, then repeat its checks and affected acceptance. Never force-push away accepted/deployed evidence or retag its images. The final PR uses a regular merge to retain the newly tested source commits.

Read README, the roadmap and the relevant skill before editing. Use active manifests and locks for versions; archived examples may describe earlier generations. Inspect existing callers and reuse trusted services. Settle behavior, interfaces, compatibility and acceptance before runtime implementation. Preserve recovered M20 worktrees, unfinished drafts and failed/private evidence.

## Build on the base

| Layer | Responsibility |
| --- | --- |
| `packages/czero-core` | Reusable knowledge/data services, persisted-role authorization, transactions, migrations and stable contracts |
| `app` | Reference/fork UI and HTTP/MCP transport composed from trusted Core operations |
| `imageroot` and `ui` | Numbered NS8 lifecycle/configuration/backup operations and native settings |
| `plugins/c0-knowledge` | Instance-bound end-user setup, research, knowledge maintenance and protected-project discovery instructions |
| `.agents/skills` and `docs` | Development routing, contributor/operator workflows and public guidance |

Fork-specific screens, branding and workflows belong in the application. Change Core when behavior is reusable, and preserve its independent distribution. Existing typed records and schemas may already express the domain; do not add a parallel database or a custom operation engine without a concrete need.

Forks use the released Core dependency and frozen lock by default. `CZERO_CORE_SOURCE=local` is an explicit producer-development choice, never an automatic fallback. Choose independent module/image identities and publishing permissions before shipping a fork. Do not publish the template's registry tags or replace an immutable upstream Core release. Review managed-file updates through the explicit `c0-upstream.json` registry; preserve customizations and unresolved comparisons.

For code changes, follow the [shared implementation practices](.agents/references/development.md#implementation-practices); relevant skills add domain-specific requirements.

## Skills and responsibilities

| Work | Skill |
| --- | --- |
| Add a feature to the reference app or a fork | [c0-create-feature](.agents/skills/c0-create-feature/SKILL.md) |
| Change reusable services, migrations or Core packaging | [c0-develop-core](.agents/skills/c0-develop-core/SKILL.md) |
| Isolate a reusable upstream contribution | [c0-contribute-upstream](.agents/skills/c0-contribute-upstream/SKILL.md) |
| Review Core or managed-infrastructure upgrades | [c0-upgrade-from-upstream](.agents/skills/c0-upgrade-from-upstream/SKILL.md) |
| Generate grounded evaluation questions | [c0-generate-retrieval-questions](.agents/skills/c0-generate-retrieval-questions/SKILL.md) |
| Maintain a managed semantic layer | [c0-maintain-semantic-layer](.agents/skills/c0-maintain-semantic-layer/SKILL.md) |
| Benchmark agentic retrieval | [c0-benchmark-agentic-retrieval](.agents/skills/c0-benchmark-agentic-retrieval/SKILL.md) |
| Measure model-driven tool use | [c0-evaluate-tools](.agents/skills/c0-evaluate-tools/SKILL.md) |
| Ingest or update an external data source | [c0-ingest-sources](.agents/skills/c0-ingest-sources/SKILL.md) |
| Develop or verify protected project workflows and agent handoff | [c0-project-workflows](.agents/skills/c0-project-workflows/SKILL.md) |

Use the installed [NethServer skills](https://github.com/NethServer/agents) for module/container work, native administration, commits, PRs and releases. Do not duplicate their manuals here. End-user skills guide connected assistants; repository skills guide developers. Neither grants authority, and development skills never ship in runtime images.

## Contribute reusable improvements upstream

When a feature or fix can benefit the original C0 base, isolate the reusable change and **open an upstream pull request** against original C0 `main` after its tests pass. Use [c0-contribute-upstream](.agents/skills/c0-contribute-upstream/SKILL.md) for extraction and the installed **nethserver-pr** skill for the actual PR. Do not stop at suggesting a contribution or leave reusable changes mixed with customer-specific branding, private data or unrelated drafts. Keep the application-specific portion in the fork.

Explain the behavior, compatibility and migration impact, include feature regression tests and reproducible validation, and follow the skill's review/assignment rules. Never assign an unsolicited reviewer. Address review feedback; do not merge a failed candidate. Core publication and fork adoption still follow their immutable-release and consumer-verification gates.

## PR readiness includes instruction review

Before marking a PR ready, review AGENTS.md, relevant developer skills and affected
end-user skills against the complete final diff. Update instructions when behavior,
interfaces, workflows, validation, packaging or authorization requirements change.
Verify affected references and packaged inventories. Instruction updates belong in
the same PR and must pass the applicable checks before merge.

Record the review in the PR description: name updated instruction paths, or state
“no instruction changes needed” with a brief reason. Complete the instruction-review
checkbox in the PR template. Recheck the declaration when the source or base changes;
reviewers must assess the instructions against the final implementation. A checked
box alone does not establish correctness. Do not make unrelated instruction edits
merely to satisfy this requirement.

## Tests are part of the feature

Use the [CI policy](docs/ci-policy.md) on the exact latest original C0 main and
candidate. Every PR gets fast automatic checks. Installation/configuration,
containers, migrations, authentication, dependencies, CI/policy code and uncertain
changes get fast checks while draft and automatic full Debian/Rocky native
acceptance when ready for review. Reviewed
presentation-only changes use the explicit low-risk allowlist and can request
full native acceptance on demand. Both internal and external contributors follow
this risk policy; there is no blanket full-native requirement for Git-only docs
or low-risk UI. Preserve required tests and failed evidence; database skips are
not a pass. Coordinate registry-dependent checks on an authorized upstream branch
without copying credentials into fork secrets or using privileged PR events.
Record the exact sources, selected acceptance level and results in the PR.

Feature tests must exercise its observable behavior and the contracts it relies on. Cover the relevant authorization/space/scope boundaries, revisions/retries, migrations/recovery and actual browser workflows when affected. Preserve and run these tests whenever original C0 or the Core dependency changes, so the fork can demonstrate that its own code still works with the new base. Do not weaken base tests, remove regression coverage, skip database cases or silently widen dependency ranges to obtain a pass.

## Keep the Codex plugin and connector current

Check Codex-facing MCP tools, descriptions, schemas, safety annotations, plugin/skill instructions and setup guidance against the actual C0 instance after feature, Core or base upgrades. Update the affected artifacts together; refresh/reload Codex's tool catalog and verify the intended account and a real authorized operation. Include a regression check for changed tool contracts and skill workflows. A matching version string or a successful package build alone is insufficient.

Preserve the registered connection identity and unrelated settings on content-only updates. New scopes need appropriate client approval and fresh explicit OAuth consent; do not silently broaden permissions. Keep end-user plugin/skill content separate from development skills. Documentation-only changes that do not affect a connector contract do not require manufacturing a new plugin version.

Keep runtime COPY inputs, the closed runtime audit allowlist, offline/HTTP
package inventory, native downloaded-archive checks and evaluation inputs
synchronized when packaged skills change. Developer skills never ship in runtime
images; instance-bound end-user skills do. Standalone consumers receive the
registered developer workflow skills and use explicit upstream links for absent
application-specific contracts. Discover actual capabilities before use; never
initialize a project or install a schedule merely to test discovery.

## Reuse ingestion scripts and preserve private jobs

For external-source ingestion and updates, read [samples](samples/ingestion/README.md)
and use c0-ingest-sources before creating another script. Put reusable source logic,
synthetic feature tests and acquired source-specific lessons in the public samples;
reuse their shared client/authentication/state/verification functions. Save each real
update wrapper and instance `.env`, dedicated credentials, datasets, state, receipts
and operational notes under ignored `.local/ingestion/<job>/`. Preserve existing
space/account/external-key mappings and keep the original job until validation passes.

Perform authorized ingestion through those saved scripts and verify actual results.
Before opening an upstream PR for a new adapter, review the complete diff and run
the privacy checker with a private deployment denylist. No instance hostname,
credentials, private identifiers or real dataset enters the contribution. Follow
the risk-based base/candidate validation policy and nethserver-pr workflow above. Do not install
schedules or broaden authority as a side effect of an ingestion request.

Queued extraction follows the [pipeline contracts](docs/ingestion-pipeline/CONTRACTS.md)
and milestone-specific acceptance in PLAN. Preserve disabled defaults, native
actor leases, fenced completion and whole-document publication. Extraction units
never become external source-sync publication parts. Keep complete-body fallback
on optional structure overflow; parser/integrity failures remain publication failures.
Local OCR stays explicit and local-only with fixed commands/model fingerprints,
process-group deadlines and disabled pending-work behavior. Cache reuse remains
same-space, current or unexpired staging, input/profile-bound and ownership-rechecked;
never retain a permanent retired-body cache. Selective context binds logical ID,
current revision/hash and citation offsets, with strict budgets and no fallback.
Preserve worker resource/restore grading and both timers' activation during backup.

## Knowledge and product contracts

Source documents and Wiki pages retain only their current complete content generation. This latest-only contract replaces the previous content-history guarantee. Keep stable logical IDs, monotonic concurrency counters, current hashes/provenance and payload-free retry/change identities. Stage replacements privately and publish whole documents atomically; delete superseded bodies, originals, derivatives and indirect receipt copies. Exact expired evidence returns authorized `content_superseded` (410), never rebound text. Preserve authored knowledge and mark invalidated evidence stale. See [migration and preflight](docs/latest-only-migration.md).

The connected assistant performs reasoning and synthesis. C0 serves knowledge and deterministic registered operations. Its worker extracts/indexes content and runs registered jobs; adding arbitrary model execution or shell commands to a request handler is outside the current product boundary. Optional retrieval providers cannot decide authorization or make ordinary text search depend on a model API.

Describe integrations accurately. C0 ships OAuth-protected MCP, an instance-bound skill and a ChatGPT-specific plugin package. Other assistants use their own connector and skill formats. Separate vendor MCP support from actually tested C0 compatibility. Interactive OAuth success does not establish scheduled execution or packaged-skill acceptance. MCP HTTP 200 can contain a tool error; inspect the tool result and verify saved revisions before claiming success.

The normal browser pages are readers. Keep mutation tools, technical client controls, protected-space grants and jobs/schedules on their established surfaces. Preserve the people-first access page's distinction between application approval, user permissions, exact connection disconnect and persistent blocking. Avoid an ambiguous Revoke action. Authorized Wiki changes publish immediately with latest-only storage. Source replacements publish only after extraction and whole-document validation; this is an integrity boundary, not an editorial approval stage.

Compilation uses the [compiler contracts](docs/knowledge-compilation/M5.md),
SQL coordination and current source/page bindings. Search remains read-only;
Readers, explicit read-only tasks and missing Write skip feedback. Enabled
feedback queues a bounded source-backed proposal; it does not publish knowledge.
Never store queries, answers, conversations or benchmark labels in compiler metadata.
Reuse all six coordinator tables, durable cursors, fences and budgets; never reopen
terminal tasks to account for inference. Generated prompts/packages install no tasks.
Preserve failed quality thresholds and independent answer audits; benchmark acceptance
does not authorize private-source copying, publication, deployment or production writes.
See [measured results](docs/knowledge-compilation/RESULTS.md).

Protected projects use [project contracts](docs/projects/PROJECTS.md) and the
[c0-project-workflows skill](.agents/skills/c0-project-workflows/SKILL.md).
Managed project records cannot bypass policy through generic object/bundle writes.
Preserve actor-bound leases, manifest versions, fencing, attempt reservations,
uncertain-call recovery, independent monitoring coverage and report/evidence revisions.
Saved results, notification, external publication and human reading are distinct.
Use the source/workflow/monitoring/reporting/maintenance contracts for the affected
operation; historical milestones do not grant live migration or scheduling authority.

## Reference website presentation

`app/frontend` is the Vue 3/TypeScript/Nebula reference website; NS8 `ui`
remains Vue 2/Carbon. Use the frozen npm lock, Composition API and local compiled
assets. Preserve emerald semantic colors, local Poppins 400/500 and their notices.
English and Italian must have matching keys. Knowledge views are read-only;
source upload/replacement/reprocessing/recovery are the explicit exception.
Cookies, X-C0-CSRF, account/space query identities, cancellation, draft guards and
410 supersession remain mandatory. Never put knowledge or credentials in browser
storage or enable stored HTML/remote images. Sign-in uses its server-bound native
form and escaped inert boot data. Website routes have no legacy aliases.
OAuth setup loads reviewed application metadata without requiring Details.
Keep application approval explicit and separate from personal consent; failed or
stale previews cannot advance the connection. Unchanged technical-client reviews
must preserve existing grants and revisions.
Run frontend checks, real `tests/e2e` browser workflows and affected native
workflows. Use the CI risk policy for the affected diff; Vue executable components require
full Debian/Rocky acceptance. A component build alone does not establish browser acceptance. See [the contract](docs/vue-website.md).

## Contracts to preserve

Native OAuth callbacks may choose a port only for a portless approved HTTP
loopback URL. Keep the original host/path and explicit-port/HTTPS exact checks,
use the shared Core matcher throughout approval/consent/authorization, and bind
code redemption to the exact requested callback and PKCE proof. SDK descriptor
projection is request-local; never persist an observed port into the registered
client. Older released Core retains exact behavior until explicit adoption.

Authorization uses current persisted Reader/Editor/Admin membership inside Core transactions, explicit protected-space selection and actual delegated scopes. Tool discovery does not grant authority. Preserve lock ordering, exact evidence identities, expected revisions and payload-free replay receipts; a superseded request returns 410 instead of old content. A denied space must never fall back to Shared. Optional providers cannot decide authorization or make ordinary text retrieval unavailable.

OAuth keeps verified native identity, explicit consent, S256, exact callback/resource/host/origin checks, bounded bodies and duplicate rejection. Authorization may ignore future optional parameters only after full multimap validation; token/revocation remain strict. Refresh cannot add scope or extend the original absolute authority. The reference app enables CIMD for its configured authenticated HTTPS endpoint; the reusable Core policy remains explicit. Self-service registration permits only requested Read for validated exact HTTPS URL identities, pins public DNS/TLS peers and rechecks authority after I/O. Additional client permissions require administrator approval. Remote metadata never supplies roles. Existing UUID clients remain independent.

That absolute bound remains unchanged for existing/interactive grants. Newly consented background grants explicitly opt into a separate offline authority with a snapshotted thirty-day inactivity window and no fixed maximum. Browser cookies, codes and pending consent retain their finite bounds. Background login purpose and expected account bind to one-use persisted state. Rotating persistent refresh credentials use a keyed family/generation proof with bounded database storage and committed replay revocation before SDK scope validation. Preserve client/account/resource/secret bindings, current-role checks, browser-logout versus explicit-disconnect semantics and genuine predecessor recovery; never promote old grants silently. Mandatory native evidence includes real offline issuance, owned provider logout, renewal and revocation; local/fake-clock tests alone do not establish ChatGPT scheduling acceptance.

Reader pages render stored knowledge with local assets and allowlisted DOM text/tokens; raw HTML/images remain inactive. Preserve response-generation/access-loss/draft/replay guards, template IDs and unique attributes. Ordinary readers do not initialize mutation controllers or fetch Admin lists. Use existing space and API selectors; files remain REST uploads.

## Repository-only BEIR benchmark

`benchmarks/retrieval` is a local developer tool over public authenticated APIs.
Keep its dependencies, downloaded datasets, manifests and reports out of runtime
packages and images. Reuse `c0_ingest` authentication, source readback and atomic
state helpers; keep evaluation read-only and require the exact dedicated protected
space and complete verified corpus. Submit missing originals to the existing
background queue before verifying extraction; preserve acknowledged source/version/hash
receipts and the single uncertain write intent across resumes. See [setup and metric contracts](benchmarks/retrieval/README.md).
Synthetic tests run in the ingestion unit suite; the optional local test extra
checks metric compatibility with BEIR's `pytrec_eval` reference dependency.
Do not run real ingestion/evaluation or change providers without explicit authority.

## Verification and delivery

Provider-free question recovery belongs in the shared Core lexical helper, not
transport-specific query rewriting. Preserve strict query results/operators,
minimum term and identifier constraints, selected-space/category/annotation
predicates and current citations. Freeze declared product/version provenance
with benchmark bodies because it can affect fallback eligibility. Record actual
`lexical_strategy` separately from semantic/provider modes; optional response
metadata must not change authority or the legacy source citation-list contract.
Keep independent Core publication and consumer pin/lock acceptance separate.
Reference publishing selects released Core when its committed package tree equals
the consumer lock's immutable Git tree; differing trees remain explicit producer
development. Invalid or missing identities fail without fallback. Verify the
released Git source in the actual published/native app image, not only a temporary
probe. Producer acceptance is not released-consumer deployment proof.

[CI policy](docs/ci-policy.md) defines the current risk-based checks. Every PR
gets fast checks; sensitive/unknown ready PRs automatically require full native
acceptance (drafts receive fast checks and cannot merge), and allowlisted presentation changes can request it on demand. Full
native acceptance remains mandatory before Core/module releases, canonical image
publication and production deployment. A fast merge proof never authorizes those
operations.

Require the actual `C0 merge gate`, current source/base/diff validation and all
selected checks. For a direct merge use `scripts/verify-promotion.py --source
<full-head-sha> --pr <number>`; use `--full` for release/deployment acceptance.
Never cancel a frozen native/full acceptance run or share mutable PostgreSQL test
databases across jobs. Preserve the existing Nebula branch and running evidence.

C0 does not require a separate human review or approval before merge. Review the
complete current diff and results (agent review is permitted), resolve feedback,
and enable automatic **regular** merge with `gh pr merge <number> --auto --merge
--match-head-commit <full-head-sha>`. Retain strict branch protection and the
Actions-owned required gate; never use an admin bypass, force push or unsolicited
reviewer assignment. If source/base changes, review and validate the new source;
retain frozen candidates when rebasing requires a successor branch.

Runtime deployment still requires explicit live authorization, supported C0-only
backup/update, readiness, image/data/settings/files/client/schedule/unrelated-
inventory preservation, live acceptance, restart and positive-control root
journald audits. Empty Podman logs do not prove privacy. Keep destructive recovery
disposable, verify actual publication when selected, and record evidence in a
separate checked documentation closeout. Installed baselines do not change merely
because a PR merges. Keep failed/private evidence outside Git.

The operator's **interactive Playwright** and **container CPU-quota** waivers remain unchanged. Do not introduce `--cpus=2`, change host delegation or claim CPU-rate enforcement. Automated native browsers, memory/swap/tasks limits, parser deadlines and worker lifetime checks remain required.

## Feature-specific contracts

For retrieval changes, read [retrieval evidence](docs/retrieval-evidence.md) and
[retrieval benchmarks](docs/retrieval-benchmark.md). Preserve bounded query
normalization, exact supporting-passage citations, legacy embedding profiles,
opt-in contextual inputs and complete-coverage invalidation. Producer implementation
never authorizes activation or released-consumer adoption.
For API-key changes, read [key contracts](docs/api-keys.md): preserve account/space
revision bindings through trusted Actor refreshes; keys never gain native extraction
or first-party authority. Remembered website login remains server-bound, one-use,
Origin-checked and renewable only after verified offline issuance and successful
authenticated traffic. Browser logout and exact connection disconnect remain distinct.

## Historical instruction links

Completed milestone narratives and the previous instruction text are preserved in
[the historical checkpoint](docs/history/AGENTS.md#instruction-checkpoint--11-november-2026).
These aliases preserve incoming links; their content describes past acceptance.

<details>
<summary>Preserved historical anchors</summary>

<a id="latest-only-source-acceptance"></a>[Latest-only source acceptance](docs/history/AGENTS.md#instruction-checkpoint--11-november-2026)

<a id="accepted-baseline-and-preserved-evidence"></a>[Accepted baseline and preserved evidence](docs/history/AGENTS.md#instruction-checkpoint--11-november-2026)

<a id="accepted-people-first-access--24-october-2026"></a>[Accepted people-first access — 24 October 2026](docs/history/AGENTS.md#instruction-checkpoint--11-november-2026)

<a id="current-work-and-preservation"></a>[Current work and preservation](docs/history/AGENTS.md#instruction-checkpoint--11-november-2026)

<a id="research-project-development-track"></a>[Research-project development track](docs/history/AGENTS.md#instruction-checkpoint--11-november-2026)

<a id="wikiplant-project-source-conventions"></a>[WikiPlant project source conventions](docs/history/AGENTS.md#instruction-checkpoint--11-november-2026)

<a id="research-workflow-coordination-conventions"></a>[Research workflow coordination conventions](docs/history/AGENTS.md#instruction-checkpoint--11-november-2026)

<a id="primary-monitoring-and-project-agent-conventions"></a>[Primary monitoring and project agent conventions](docs/history/AGENTS.md#instruction-checkpoint--11-november-2026)

<a id="project-evidence-and-reporting-conventions"></a>[Project evidence and reporting conventions](docs/history/AGENTS.md#instruction-checkpoint--11-november-2026)

<a id="project-maintenance-conventions"></a>[Project maintenance conventions](docs/history/AGENTS.md#instruction-checkpoint--11-november-2026)

<a id="project-exportpreparation-conventions"></a>[Project export/preparation conventions](docs/history/AGENTS.md#instruction-checkpoint--11-november-2026)

<a id="wikiplant-m8-distributionfinal-acceptance"></a>[WikiPlant M8 distribution/final acceptance](docs/history/AGENTS.md#instruction-checkpoint--11-november-2026)

<a id="wikiplant-backend-deployed-acceptance--27-october-2026"></a>[WikiPlant backend deployed acceptance — 27 October 2026](docs/history/AGENTS.md#instruction-checkpoint--11-november-2026)

<a id="remembered-website-acceptance--27-october-2026"></a>[Remembered website acceptance — 27 October 2026](docs/history/AGENTS.md#instruction-checkpoint--11-november-2026)

<a id="full-document-explorer-candidate"></a>[Full-document Explorer candidate](docs/history/AGENTS.md#instruction-checkpoint--11-november-2026)

<a id="personal-api-keys"></a>[Personal API keys](docs/history/AGENTS.md#instruction-checkpoint--11-november-2026)

<a id="openai-system-one-accepted-delivery"></a>[OpenAI System One accepted delivery](docs/history/AGENTS.md#instruction-checkpoint--11-november-2026)

<a id="authoritative-development-ci-policy"></a>[authoritative-development-ci-policy](docs/history/AGENTS.md#authoritative-development-ci-policy)

<a id="m19-accepted-runtime-conventions"></a>[m19-accepted-runtime-conventions](docs/history/AGENTS.md#m19-accepted-runtime-conventions)

<a id="historical-m17-implementation-entry"></a>[historical-m17-implementation-entry](docs/history/AGENTS.md#historical-m17-implementation-entry)

<a id="m20-runtime-and-corrected-main-acceptance-historical-closeout-checkpoint"></a>[m20-runtime-and-corrected-main-acceptance-historical-closeout-checkpoint](docs/history/AGENTS.md#m20-runtime-and-corrected-main-acceptance-historical-closeout-checkpoint)

<a id="historical-m20-resumption-and-correction-evidence"></a>[historical-m20-resumption-and-correction-evidence](docs/history/AGENTS.md#historical-m20-resumption-and-correction-evidence)

<a id="am6-accepted-implementation-m20-preserved"></a>[am6-accepted-implementation-m20-preserved](docs/history/AGENTS.md#am6-accepted-implementation-m20-preserved)

<a id="protected-knowledge-spaces-am3-runtime-accepted"></a>[protected-knowledge-spaces-am3-runtime-accepted](docs/history/AGENTS.md#protected-knowledge-spaces-am3-runtime-accepted)

<a id="accepted-m18-guidance-checkpoint--21-october-2026"></a>[accepted-m18-guidance-checkpoint--21-october-2026](docs/history/AGENTS.md#accepted-m18-guidance-checkpoint--21-october-2026)

<a id="accepted-m17-profile-checkpoint--20-october-2026"></a>[accepted-m17-profile-checkpoint--20-october-2026](docs/history/AGENTS.md#accepted-m17-profile-checkpoint--20-october-2026)

<a id="m15-reader-ui-conventions-accepted-candidate"></a>[m15-reader-ui-conventions-accepted-candidate](docs/history/AGENTS.md#m15-reader-ui-conventions-accepted-candidate)

<a id="active-chatgpt-integration-plan"></a>[active-chatgpt-integration-plan](docs/history/AGENTS.md#active-chatgpt-integration-plan)

<a id="integration-m16-implementation-conventions-accepted"></a>[integration-m16-implementation-conventions-accepted](docs/history/AGENTS.md#integration-m16-implementation-conventions-accepted)

<a id="established-m14-conventions"></a>[established-m14-conventions](docs/history/AGENTS.md#established-m14-conventions)

<a id="established-m13-distribution-conventions"></a>[established-m13-distribution-conventions](docs/history/AGENTS.md#established-m13-distribution-conventions)

<a id="established-m12-ui-conventions"></a>[established-m12-ui-conventions](docs/history/AGENTS.md#established-m12-ui-conventions)

<a id="established-m11-operation-conventions"></a>[established-m11-operation-conventions](docs/history/AGENTS.md#established-m11-operation-conventions)

<a id="established-m10-retrieval-conventions"></a>[established-m10-retrieval-conventions](docs/history/AGENTS.md#established-m10-retrieval-conventions)

<a id="established-m09-wikigraph-conventions"></a>[established-m09-wikigraph-conventions](docs/history/AGENTS.md#established-m09-wikigraph-conventions)

<a id="established-m08-ingestion-conventions"></a>[established-m08-ingestion-conventions](docs/history/AGENTS.md#established-m08-ingestion-conventions)

<a id="established-m07-object-contracts"></a>[established-m07-object-contracts](docs/history/AGENTS.md#established-m07-object-contracts)

<a id="established-m06-queueworker-contracts"></a>[established-m06-queueworker-contracts](docs/history/AGENTS.md#established-m06-queueworker-contracts)

<a id="established-m05-identity-conventions"></a>[established-m05-identity-conventions](docs/history/AGENTS.md#established-m05-identity-conventions)

<a id="established-m04-backuprestore-conventions"></a>[established-m04-backuprestore-conventions](docs/history/AGENTS.md#established-m04-backuprestore-conventions)

<a id="established-m03-database-conventions"></a>[established-m03-database-conventions](docs/history/AGENTS.md#established-m03-database-conventions)

<a id="established-m02-configuration-conventions"></a>[established-m02-configuration-conventions](docs/history/AGENTS.md#established-m02-configuration-conventions)

<a id="established-m01-conventions"></a>[established-m01-conventions](docs/history/AGENTS.md#established-m01-conventions)

<a id="established-m00-conventions"></a>[established-m00-conventions](docs/history/AGENTS.md#established-m00-conventions)

<a id="mission-and-boundaries"></a>[mission-and-boundaries](docs/history/AGENTS.md#mission-and-boundaries)

<a id="source-hierarchy-reuse-before-implementing"></a>[source-hierarchy-reuse-before-implementing](docs/history/AGENTS.md#source-hierarchy-reuse-before-implementing)

<a id="keep-ns8-actions-readable"></a>[keep-ns8-actions-readable](docs/history/AGENTS.md#keep-ns8-actions-readable)

<a id="runtime-design-invariants"></a>[runtime-design-invariants](docs/history/AGENTS.md#runtime-design-invariants)

<a id="mandatory-milestone-loop"></a>[mandatory-milestone-loop](docs/history/AGENTS.md#mandatory-milestone-loop)

<a id="definition-of-done-for-any-change"></a>[definition-of-done-for-any-change](docs/history/AGENTS.md#definition-of-done-for-any-change)

<a id="completed-structured-object-repair"></a>[completed-structured-object-repair](docs/history/AGENTS.md#completed-structured-object-repair)

<a id="structured-object-repair-accepted-runtime"></a>[structured-object-repair-accepted-runtime](docs/history/AGENTS.md#structured-object-repair-accepted-runtime)

<a id="c0-agent-memory-track"></a>[c0-agent-memory-track](docs/history/AGENTS.md#c0-agent-memory-track)

<a id="am3-released-core-and-application-conventions-pending-acceptance"></a>[am3-released-core-and-application-conventions-pending-acceptance](docs/history/AGENTS.md#am3-released-core-and-application-conventions-pending-acceptance)

<a id="am4-applicability-and-structured-retrieval-runtime-accepted"></a>[am4-applicability-and-structured-retrieval-runtime-accepted](docs/history/AGENTS.md#am4-applicability-and-structured-retrieval-runtime-accepted)

<a id="am5-consolidation-implementation-conventions"></a>[am5-consolidation-implementation-conventions](docs/history/AGENTS.md#am5-consolidation-implementation-conventions)

<a id="am5-runtime-acceptance-18-october-2026"></a>[am5-runtime-acceptance-18-october-2026](docs/history/AGENTS.md#am5-runtime-acceptance-18-october-2026)

<a id="scoped-ci-policy-accepted-sources"></a>[scoped-ci-policy-accepted-sources](docs/history/AGENTS.md#scoped-ci-policy-accepted-sources)

<a id="instruction-checkpoint--11-november-2026"></a>[Instruction checkpoint — 11 November 2026](docs/history/AGENTS.md#instruction-checkpoint--11-november-2026)

</details>


## Record browsing Core0.49 and tables consumer

Keep populated type discovery scoped to current persisted Reader authority.
Legacy global schema discovery remains the default. Optional record sorting
uses validated scalar fields, missing/null last and stable ID ties before paging.
Core0.49 is immutably published from `998ef32`; its package tree must stay
identical to the released Git dependency. App0.67 adopts its tag/lock with
>=0.49.0,<0.50.0 and matching patch-only updater bounds. Keep the installed
baseline and genuine predecessor as recorded in PLAN; the separately authorized
table-browser deployment is accepted there.

The schema-driven Tables reader uses existing Nebula components and current
account/space response guards. Preserve schema titles verbatim, exact filters,
server sorting, bounded pagination and safe nested value rendering. Global
schema discovery remains available before ingestion space selection; populated
discovery and content operations keep exact selected-space checks. Existing
Explore record links remain valid. See [the contract](docs/structured-tables.md).
