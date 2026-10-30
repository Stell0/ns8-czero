# C0 / ns8-czero — Instructions for coding agents

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

## Skills and responsibilities

| Work | Skill |
| --- | --- |
| Add a feature to the reference app or a fork | [c0-create-feature](.agents/skills/c0-create-feature/SKILL.md) |
| Change reusable services, migrations or Core packaging | [c0-develop-core](.agents/skills/c0-develop-core/SKILL.md) |
| Isolate a reusable upstream contribution | [c0-contribute-upstream](.agents/skills/c0-contribute-upstream/SKILL.md) |
| Review Core or managed-infrastructure upgrades | [c0-upgrade-from-upstream](.agents/skills/c0-upgrade-from-upstream/SKILL.md) |
| Measure model-driven tool use | [c0-evaluate-tools](.agents/skills/c0-evaluate-tools/SKILL.md) |
| Ingest or update an external data source | [c0-ingest-sources](.agents/skills/c0-ingest-sources/SKILL.md) |
| Develop or verify protected project workflows and agent handoff | [c0-project-workflows](.agents/skills/c0-project-workflows/SKILL.md) |

Use the installed [NethServer skills](https://github.com/NethServer/agents) for module/container work, native administration, commits, PRs and releases. Do not duplicate their manuals here. End-user skills guide connected assistants; repository skills guide developers. Neither grants authority, and development skills never ship in runtime images.

## Contribute reusable improvements upstream

When a feature or fix can benefit the original C0 base, isolate the reusable change and **open an upstream pull request** against original C0 `main` after its tests pass. Use [c0-contribute-upstream](.agents/skills/c0-contribute-upstream/SKILL.md) for extraction and the installed **nethserver-pr** skill for the actual PR. Do not stop at suggesting a contribution or leave reusable changes mixed with customer-specific branding, private data or unrelated drafts. Keep the application-specific portion in the fork.

Explain the behavior, compatibility and migration impact, include feature regression tests and reproducible validation, and follow the skill's review/assignment rules. Never assign an unsolicited reviewer. Address review feedback; do not merge a failed candidate. Core publication and fork adoption still follow their immutable-release and consumer-verification gates.

## Tests are part of the feature

Before opening a feature/runtime PR, run the complete required base suite on the exact latest original C0 `main` and establish a green baseline. Add tests for the new feature to the branch, then run the complete suite again on the rebased candidate. Resolve base failures before opening the feature PR; retain failed evidence rather than describing a partial run or database skips as a pass. CI checks required by [CI policy](docs/ci-policy.md) must also finish successfully for the exact candidate before merge.

The documentation-only lightweight exception applies to branches developed within original `Stell0/ns8-czero`. **Every contribution from an external fork to original C0 `main` requires full base and candidate checks before opening the upstream PR, including documentation-only contributions.** Complete the database, packaging, image and native matrix; a lightweight automatic docs check does not satisfy this contributor requirement. Arrange any registry-dependent checks on an authorized upstream branch without copying credentials into fork secrets or executing untrusted code with privileged PR events. Record the exact sources and results in the PR.

Feature tests must exercise its observable behavior and the contracts it relies on. Cover the relevant authorization/space/scope boundaries, revisions/retries, migrations/recovery and actual browser workflows when affected. Preserve and run these tests whenever original C0 or the Core dependency changes, so the fork can demonstrate that its own code still works with the new base. Do not weaken base tests, remove regression coverage, skip database cases or silently widen dependency ranges to obtain a pass.

## Keep the Codex plugin and connector current

Check Codex-facing MCP tools, descriptions, schemas, safety annotations, plugin/skill instructions and setup guidance against the actual C0 instance after feature, Core or base upgrades. Update the affected artifacts together; refresh/reload Codex's tool catalog and verify the intended account and a real authorized operation. Include a regression check for changed tool contracts and skill workflows. A matching version string or a successful package build alone is insufficient.

Preserve the registered connection identity and unrelated settings on content-only updates. New scopes need appropriate client approval and fresh explicit OAuth consent; do not silently broaden permissions. Keep end-user plugin/skill content separate from development skills. Documentation-only changes that do not affect a connector contract do not require manufacturing a new plugin version.

Plugin1.2 adds the fourth end-user workflow, protected-project discovery. Keep its
runtime COPY inputs, closed runtime audit allowlist, offline/HTTP package inventory,
native downloaded-archive checks and evaluation inputs synchronized. Standalone
forks receive the registered developer workflow skill; application-specific project
contracts use explicit upstream links when absent locally. Never initialize a
project or install an external schedule merely to verify discovery. PR41 repair
acceptance is tracked in PLAN; no new dedicated deployment is part of this work.
Its inherited Authlib1.8.0 pin is now rejected by the critical security gate.
Core0.35.1 is immutably published at6a11469 with Authlib1.9.1 and schema0022
unchanged after exact full40673116010/native/artifact proof and publisher40680486868.
The app adopts its tag/lock with >=0.35.1,<0.36 and matching patch-only updater
bounds. Final consumer/full/native/main gates remain required; see PR41 and PLAN.
Never waive this finding or override the published Core dependency metadata.

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
the full base/candidate test rule and nethserver-pr workflow above. Do not install
schedules or broaden authority as a side effect of an ingestion request.

## Knowledge and product contracts

Source documents and Wiki pages retain only their current complete content generation. This latest-only contract replaces the previous content-history guarantee. Keep stable logical IDs, monotonic concurrency counters, current hashes/provenance and payload-free retry/change identities. Stage replacements privately and publish whole documents atomically; delete superseded bodies, originals, derivatives and indirect receipt copies. Exact expired evidence returns authorized `content_superseded` (410), never rebound text. Preserve authored knowledge and mark invalidated evidence stale. See [migration and preflight](docs/latest-only-migration.md).

The connected assistant performs reasoning and synthesis. C0 serves knowledge and deterministic registered operations. Its worker extracts/indexes content and runs registered jobs; adding arbitrary model execution or shell commands to a request handler is outside the current product boundary. Optional retrieval providers cannot decide authorization or make ordinary text search depend on a model API.

Describe integrations accurately. C0 ships OAuth-protected MCP, an instance-bound skill and a ChatGPT-specific plugin package. Other assistants use their own connector and skill formats. Separate vendor MCP support from actually tested C0 compatibility. Interactive OAuth success does not establish scheduled execution or packaged-skill acceptance. MCP HTTP 200 can contain a tool error; inspect the tool result and verify saved revisions before claiming success.

The normal browser pages are readers. Keep mutation tools, technical client controls, protected-space grants and jobs/schedules on their established surfaces. Preserve the people-first access page's distinction between application approval, user permissions, exact connection disconnect and persistent blocking. Avoid an ambiguous Revoke action. Authorized Wiki changes publish immediately with latest-only storage. Source replacements publish only after extraction and whole-document validation; this is an integrity boundary, not an editorial approval stage.

## Contracts to preserve

Authorization uses current persisted Reader/Editor/Admin membership inside Core transactions, explicit protected-space selection and actual delegated scopes. Tool discovery does not grant authority. Preserve lock ordering, exact evidence identities, expected revisions and payload-free replay receipts; a superseded request returns 410 instead of old content. A denied space must never fall back to Shared. Optional providers cannot decide authorization or make ordinary text retrieval unavailable.

OAuth keeps verified native identity, explicit consent, S256, exact callback/resource/host/origin checks, bounded bodies and duplicate rejection. Authorization may ignore future optional parameters only after full multimap validation; token/revocation remain strict. Refresh cannot add scope or extend the original absolute authority. CIMD defaults off, approves exact HTTPS URL identities, pins public DNS/TLS peers and rechecks authority after I/O. Remote metadata never supplies roles. Existing UUID clients remain independent.

That absolute bound remains unchanged for existing/interactive grants. Newly consented background grants explicitly opt into a separate offline authority with a snapshotted thirty-day inactivity window and no fixed maximum. Browser cookies, codes and pending consent retain their finite bounds. Background login purpose and expected account bind to one-use persisted state. Rotating persistent refresh credentials use a keyed family/generation proof with bounded database storage and committed replay revocation before SDK scope validation. Preserve client/account/resource/secret bindings, current-role checks, browser-logout versus explicit-disconnect semantics and genuine predecessor recovery; never promote old grants silently. Mandatory native evidence includes real offline issuance, owned provider logout, renewal and revocation; local/fake-clock tests alone do not establish ChatGPT scheduling acceptance.

Reader pages render stored knowledge with local assets and allowlisted DOM text/tokens; raw HTML/images remain inactive. Preserve response-generation/access-loss/draft/replay guards, template IDs and unique attributes. Ordinary readers do not initialize mutation controllers or fetch Admin lists. Use existing space and API selectors; files remain REST uploads.

## Verification and delivery

[CI policy](docs/ci-policy.md) defines automated validation. Draft runtime work gets scoped feedback; ready runtime PRs require full exact-source acceptance. Only explicitly reviewed Git-only documents receive the lightweight exemption; packaged docs, plugin inputs, static app HTML, executable helpers, versions and locks broaden validation. The external-fork contribution requirement above additionally requires full checks even when automation classifies a change as documentation-only.

Require the actual `C0 merge gate` and `scripts/verify-promotion.py --source <full-head-sha> --pr <number>`. Inspect completed successful checks and actual native/privacy/scan artifacts; old, skipped, cancelled or started checks are insufficient. Use `validate.yml` for manual full dispatch. Never cancel a frozen acceptance run or share a mutable PostgreSQL test database across jobs.

Another developer reviews before merge; assign no unsolicited reviewer. Preserve tested commits with a regular merge. Runtime milestones require supported C0-only backup/update, real readiness, exact image/data/settings/files/client/schedule/unrelated-inventory preservation, live acceptance, restart and bounded positive-control root journald audits. Empty Podman logs do not prove privacy. Destructive recovery tests remain disposable. Verify actual main completion/publication, then use a separate checked documentation closeout. Keep failed/private evidence outside Git and public identities sanitized.

The operator's **interactive Playwright** and **container CPU-quota** waivers remain unchanged. Do not introduce `--cpus=2`, change host delegation or claim CPU-rate enforcement. Automated native browsers, memory/swap/tasks limits, parser deadlines and worker lifetime checks remain required.

## Latest-only source acceptance

Approved [PR45](https://github.com/Stell0/ns8-czero/pull/45) regularly merges as
`f51357d18760a83242273e1ded0c648799c8dad8`: app0.56.0, independently published
Core0.36.0 at `cf9c0fa38183e940877c13228a8ce753dfd07412`, schema0023.
Actual main [41010999070](https://github.com/Stell0/ns8-czero/actions/runs/41010999070)
passes full/native/privacy/scan gates and canonical publication, with independent
artifact audit, exact-source promotion and six fresh registry identity reads.
See PLAN for counts and bounded public-crawl results. This is source/publication
acceptance. The installed baseline below remains unchanged; production migration,
upgrade, full import and schedules require separate authorization.

## Accepted baseline and preserved evidence

The accepted dedicated runtime is app **0.54.0**, Core **0.35.0**, schema **0022**, source `31b0c85a71743ab6dcdb04c12ac18dd4c1500722`. Its exact installed identities and next genuine predecessor policy are recorded in [PLAN](PLAN.md#remembered-login-deployed-runtime-and-frozen-predecessor). Keep those immutable candidate tags/digests available; documentation changes do not replace the runtime. The previous `c2280f5` installation remains the historical genuine predecessor used to accept this upgrade.

Prior reviewed closeout PR35 merged as `f735004`; actual main documentation check [40137756852](https://github.com/Stell0/ns8-czero/actions/runs/40137756852) and exact-source promotion verification pass. The full runtime/main publication evidence remains in PLAN. Broader M21 packaged-skill/client/scheduled acceptance and release obligations remain open; no stable module release is claimed.

<details>
<summary>Operational conventions and acceptance checkpoints retained from earlier work</summary>

The following record describes its stated checkpoints. The current baseline and roadmap above supersede older pending/current-installation wording. Preserve its security, migration and browser regression conventions.

## Accepted people-first access — 24 October 2026

PR33 and PR34 are reviewed and regularly merged, in that order. The operator
confirms the existing ChatGPT web connection worked without manual reconnect for
more than 24 hours. PR33 main `cd17a02` full40101415111, publication and actual
native/privacy/scan audits pass. PR34 accepted deployed source `e384bed` passes
full40093959067; integrated head `cc8c2cf` and merge `05ce22c` have exactly the
same tracked file tree. Integration full40101567741 and actual artifact audit
pass. Resulting main full40106287084 is completed/successful, including canonical
publication. Independent downloaded native/privacy/scan audits, exact-source
promotion proof and six fresh main/latest registry identity reads pass.

The accepted dedicated installation is app0.52.0 / released Core0.33.0 /
schema0021 at `e384bed641ac0bdc97212def22db521c0ab2e4c7`. Freeze all three
installed digests and the immutable candidate tag in PLAN as the next genuine
upgrade predecessor. Never replace it with integration/main/documentation images.
Core tag core-v0.33.0 remains immutable at `ec2ac4f`; exact full40082329366,
publisher40086544147, downloaded checksums and independent supplied installs pass.

Final local released-Core validation passes 1963 actual Python/PostgreSQL/packaging
cases without database skips, 185 Node24 controllers, schema/shell/docs and 21
Robot dry runs. Actual accepted native reports pass Debian upgrade 21, Rocky
installation 26/three expected skips, all eight browser workflows/privacy guards,
30 numeric accessibility contexts, ten strictly graded access stages and three
OAuth-query artifacts with zero candidates. Preserve failed earlier evidence;
71b3d96 and 45f9163 were not accepted or deployed.

Core owns request IDs, account access revisions and first-party Admin summaries,
request-bound approval/decline and exact per-grant disconnect. Preserve default
verified Shared Reader admission, explicit blocks, independent OAuth scopes,
owner protection and protected-space boundaries. Application approval, user role
and disconnect remain distinct. Unchanged revision-bound role saves do nothing;
legacy role calls retain invalidation. The old account-list SQL remains compatible
with schema0015. Preserve the configured-owner override without deleting an older
block marker. Locally observed connection summaries do not prove provider health.

The browser-only access API serves one people/application table at /admin;
/admin/advanced, /admin/spaces and /admin/work keep technical clients, protected
spaces and background work separate. Account links to access instead of a duplicate
membership editor. Ordinary self-service connections are unchanged. Subpages retain
mount prefixes. Preserve request/draft/access-loss guards, exact CSRF and current
Core authorization. The native public metadata fixture uses real DNS/TLS/MIME;
keep test-workspace-client-v1 at 9fc9594 unchanged. No ns8-idp change is required.

Supported dedicated C0 backup/integrity, update/readiness and manager restart pass.
Observers preserve 40 original domain tables/247 stable rows, settings/schedules,
one existing background grant and nine unrelated instances. Two temporary clients
are disabled. Live owner/REST/current+legacy SDK and existing connected-tool reads
pass; actual Reader/Editor/Admin action workflows are disposable native evidence.
Shared content is empty, so do not claim nonempty retained-body evidence. Bounded
root application journals have 90/93 entries with real request positive controls
and zero query/credential candidates. Private evidence stays outside Git. Separate
three-document closeout checks/review must pass; accepted images remain deployed.

Read [README](README.md), the active milestone in [PLAN](PLAN.md) and the relevant repository skill. Current user/operator instructions supersede historical workflow statements. Detailed past decisions and measured evidence live in [archived agent conventions](docs/history/AGENTS.md) and [archived milestones](docs/history/PLAN.md); consult the relevant topic when needed.

## Current work and preservation

Persistent background OAuth and the access page are accepted as recorded above
and in PLAN. The original PR33 policy/recovery failures are retained as historical
evidence there; they are resolved by the accepted source. Preserve original dirty
work, M20 worktrees, drafts, immutable Core artifacts and waivers. M21 packaged-skill
web use, quota-blocked model cases, actual scheduled-client interoperability and
vendor findings remain separate release work. No stable module release is claimed.

M19 runtime source `38a8654` is accepted at app0.49.0/Core0.31.0/schema0018; reviewed closeout PR30 regularly merges as `0a9bbb3` and actual main39643655916 passes. M21 documentation/skills release readiness is authorized. M21 is based on that verified marker. Preserve all original dirty documents, recovered M20 worktrees, unfinished drafts, immutable Core artifacts and the three accepted image identities in PLAN. Never replace an accepted installation with documentation-marker images. Windmill remains separate.

M21 changes guides, five developer skills, three end-user skills, offline package generation and installed Use with AI presentation. Core/schema/OAuth/dependencies remain unchanged. Actual packaged-skill use on ChatGPT web is required for both private Plugin Creator and managed GitHub import; desktop/SDK/manifest checks do not establish that gate. Missing account/workspace features leave acceptance incomplete. No stable module tag, directory submission or workspace-wide rollout is authorized.

The operator authorizes the M21 self-service follow-up in PLAN: generated installed skill/plugin downloads, visible OAuth approval, default verified-user Shared read admission and persistent administrator blocks. Earlier M21 Core-unchanged/offline-only constraints are superseded for this scoped work. PR31 main `0040c89` and its clean-start `3730188` installation are historical checkpoints; PR32/deployed `fa64f3d` identities are historical; current accepted images are frozen above and in PLAN. Preserve all original dirty work.

Administration subpages use a base URI. Skip links must retain the current
document and selected-space query; shared navigation corrects links resolved
against another local page. Preserve the resolved URL/target guard and actual
native Tab/Enter/main-focus checks on Advanced, Background work and Protected
spaces. An unresolved fragment attribute is not sufficient evidence. Native
fixture cleanup restores the original discovery policy even on browser failure.


</details>

<details>
<summary>Historical section links</summary>

These anchors preserve links to the retained historical record.

<a id="authoritative-development-ci-policy"></a>[Authoritative development CI policy](docs/history/AGENTS.md#authoritative-development-ci-policy)

<a id="m19-accepted-runtime-conventions"></a>[M19 accepted runtime conventions](docs/history/AGENTS.md#m19-accepted-runtime-conventions)

<a id="historical-m17-implementation-entry"></a>[Historical M17 implementation entry](docs/history/AGENTS.md#historical-m17-implementation-entry)

<a id="m20-runtime-and-corrected-main-acceptance-historical-closeout-checkpoint"></a>[M20 runtime and corrected main acceptance (historical closeout checkpoint)](docs/history/AGENTS.md#m20-runtime-and-corrected-main-acceptance-historical-closeout-checkpoint)

<a id="historical-m20-resumption-and-correction-evidence"></a>[Historical M20 resumption and correction evidence](docs/history/AGENTS.md#historical-m20-resumption-and-correction-evidence)

<a id="am6-accepted-implementation-m20-preserved"></a>[AM6 accepted implementation; M20 preserved](docs/history/AGENTS.md#am6-accepted-implementation-m20-preserved)

<a id="protected-knowledge-spaces-am3-runtime-accepted"></a>[Protected knowledge spaces (AM3 runtime accepted)](docs/history/AGENTS.md#protected-knowledge-spaces-am3-runtime-accepted)

<a id="accepted-m18-guidance-checkpoint--21-october-2026"></a>[Accepted M18 guidance checkpoint — 21 October 2026](docs/history/AGENTS.md#accepted-m18-guidance-checkpoint--21-october-2026)

<a id="accepted-m17-profile-checkpoint--20-october-2026"></a>[Accepted M17 profile checkpoint — 20 October 2026](docs/history/AGENTS.md#accepted-m17-profile-checkpoint--20-october-2026)

<a id="m15-reader-ui-conventions-accepted-candidate"></a>[M15 reader UI conventions (accepted candidate)](docs/history/AGENTS.md#m15-reader-ui-conventions-accepted-candidate)

<a id="active-chatgpt-integration-plan"></a>[Active ChatGPT integration plan](docs/history/AGENTS.md#active-chatgpt-integration-plan)

<a id="integration-m16-implementation-conventions-accepted"></a>[Integration M16 implementation conventions (accepted)](docs/history/AGENTS.md#integration-m16-implementation-conventions-accepted)

<a id="established-m14-conventions"></a>[Established M14 conventions](docs/history/AGENTS.md#established-m14-conventions)

<a id="established-m13-distribution-conventions"></a>[Established M13 distribution conventions](docs/history/AGENTS.md#established-m13-distribution-conventions)

<a id="established-m12-ui-conventions"></a>[Established M12 UI conventions](docs/history/AGENTS.md#established-m12-ui-conventions)

<a id="established-m11-operation-conventions"></a>[Established M11 operation conventions](docs/history/AGENTS.md#established-m11-operation-conventions)

<a id="established-m10-retrieval-conventions"></a>[Established M10 retrieval conventions](docs/history/AGENTS.md#established-m10-retrieval-conventions)

<a id="established-m09-wikigraph-conventions"></a>[Established M09 Wiki/graph conventions](docs/history/AGENTS.md#established-m09-wikigraph-conventions)

<a id="established-m08-ingestion-conventions"></a>[Established M08 ingestion conventions](docs/history/AGENTS.md#established-m08-ingestion-conventions)

<a id="established-m07-object-contracts"></a>[Established M07 object contracts](docs/history/AGENTS.md#established-m07-object-contracts)

<a id="established-m06-queueworker-contracts"></a>[Established M06 queue/worker contracts](docs/history/AGENTS.md#established-m06-queueworker-contracts)

<a id="established-m05-identity-conventions"></a>[Established M05 identity conventions](docs/history/AGENTS.md#established-m05-identity-conventions)

<a id="established-m04-backuprestore-conventions"></a>[Established M04 backup/restore conventions](docs/history/AGENTS.md#established-m04-backuprestore-conventions)

<a id="established-m03-database-conventions"></a>[Established M03 database conventions](docs/history/AGENTS.md#established-m03-database-conventions)

<a id="established-m02-configuration-conventions"></a>[Established M02 configuration conventions](docs/history/AGENTS.md#established-m02-configuration-conventions)

<a id="established-m01-conventions"></a>[Established M01 conventions](docs/history/AGENTS.md#established-m01-conventions)

<a id="established-m00-conventions"></a>[Established M00 conventions](docs/history/AGENTS.md#established-m00-conventions)

<a id="mission-and-boundaries"></a>[Mission and boundaries](docs/history/AGENTS.md#mission-and-boundaries)

<a id="source-hierarchy-reuse-before-implementing"></a>[Source hierarchy: reuse before implementing](docs/history/AGENTS.md#source-hierarchy-reuse-before-implementing)

<a id="keep-ns8-actions-readable"></a>[Keep NS8 actions readable](docs/history/AGENTS.md#keep-ns8-actions-readable)

<a id="runtime-design-invariants"></a>[Runtime design invariants](docs/history/AGENTS.md#runtime-design-invariants)

<a id="mandatory-milestone-loop"></a>[Mandatory milestone loop](docs/history/AGENTS.md#mandatory-milestone-loop)

<a id="definition-of-done-for-any-change"></a>[Definition of done for any change](docs/history/AGENTS.md#definition-of-done-for-any-change)

<a id="completed-structured-object-repair"></a>[Completed structured-object repair](docs/history/AGENTS.md#completed-structured-object-repair)

<a id="structured-object-repair-accepted-runtime"></a>[Structured-object repair accepted runtime](docs/history/AGENTS.md#structured-object-repair-accepted-runtime)

<a id="c0-agent-memory-track"></a>[C0 Agent Memory track](docs/history/AGENTS.md#c0-agent-memory-track)

<a id="am3-released-core-and-application-conventions-pending-acceptance"></a>[AM3 released Core and application conventions (pending acceptance)](docs/history/AGENTS.md#am3-released-core-and-application-conventions-pending-acceptance)

<a id="am4-applicability-and-structured-retrieval-runtime-accepted"></a>[AM4 applicability and structured retrieval (runtime accepted)](docs/history/AGENTS.md#am4-applicability-and-structured-retrieval-runtime-accepted)

<a id="am5-consolidation-implementation-conventions"></a>[AM5 consolidation implementation conventions](docs/history/AGENTS.md#am5-consolidation-implementation-conventions)

<a id="am5-runtime-acceptance-18-october-2026"></a>[AM5 runtime acceptance (18 October 2026)](docs/history/AGENTS.md#am5-runtime-acceptance-18-october-2026)

<a id="scoped-ci-policy-accepted-sources"></a>[Scoped CI policy accepted sources](docs/history/AGENTS.md#scoped-ci-policy-accepted-sources)

</details>

M21 self-service source `fa64f3d` is deployed with verified three-image identities, supported backup/update/restart, original data/settings/schedules and nine unrelated-instance preservation, actual positive-control journal privacy and operator connection/read. PR32/main `d4a9734` completes successful main validation/publication with inspected native artifacts. Preserve its installed candidate images as the genuine persistent-connection upgrade predecessor, independently of main/closeout image tags. Finish outstanding M21 package/model observations honestly; the operator's new background-connection priority does not fabricate that acceptance.


## Research-project development track

See [compatibility audit](docs/projects/WIKIPLANT_COMPATIBILITY.md) and
[project contracts](docs/projects/PROJECTS.md). Reuse protected spaces and typed
storage. Project selection is mandatory and never falls back to Shared. Trusted
Core project transitions own managed `c0_project_*_v1` types; generic object/bundle
writes must not bypass policy. Preserve immutable configuration/evidence history,
current grants/scopes and existing content/authority lock order. External agents
supply semantic assessments; validators do not prove their truth. Keep default
released-Core availability and producer tests distinct until immutable publication,
pin adoption and consumer acceptance pass. Use only fabricated disposable fixtures;
this track authorizes no live migration, deployment, real spaces or schedules.

## WikiPlant project source conventions

Extend `samples/ingestion` and its existing OAuth/private-job client rather than
introducing another authentication or publication system. Collectors return
bounded original Item/Batch values; publishers independently reconcile exact
source/version hashes and verify extraction/citations. Connector definitions
require Admin approval; current-role checks and explicit space bindings remain
authoritative. Advance successful cursors only after verified persistence.
Never treat external source instructions as authority or run real migration
fixtures against live WikiPlant/C0 spaces. See docs/projects/SOURCES.md.

Connector coverage counters require explicit stored part receipt identities.
Core must verify ready same-space source versions and complete parent snapshot
membership before advancing progress/success cursors. Counting HTTP responses
or partially saved originals is not publication proof. Keep this negative
control when changing collector, publisher or status contracts.


## Research workflow coordination conventions

Use existing typed storage and transaction locks for run/queue/budget transitions.
Every leased mutation rechecks actor, manifest version, expiry and fencing before
receipt replay as well as writes. A stale owner cannot reuse an earlier SAVED
receipt as execution permission. Reserve a slot before external invocation and
retain uncertain outcomes separately; pending merges never reserve again.
Source-sync CLI commits carry their run fence. Never confuse an external call
observation with exactly-once execution or successful knowledge publication.
Keep five ordinary/ten urgent-only extended slots shared by daily/weekly/manual
runs, causal +20 depth and maximum three children. Preserve terminal ancestry
through topic reassessment. See docs/projects/WORKFLOWS.md and actual PostgreSQL
concurrency/recovery tests. M4–M8 acceptance and default released-Core adoption
remain pending until their recorded gates pass.

## Primary monitoring and project agent conventions

Monitoring is independent of queue budgets. Reserve bounded query/source calls,
record starts and actual outcomes separately, and retain uncertain calls on
fence transfer. Successful coverage requires every selected source's ready
immutable passages and no unresolved checks; failure never advances watermarks.
Daily research cannot skip configured primary monitoring. Scope changes require
fresh assessment without resetting counters, lineage or consumed allowances.

Extend the existing product package machinery with explicit protected project
bindings; never install or activate a host task as a side effect of generation.
Keep calendar IANA cycle identity distinct from current-day research allowance.
Runner observations are attributed reports, not proof of host capability or
unattended execution. Preserve canonical connection/space checks and private
exclusive archive saves. Explicit runtime asset allowlists must include only
the six product templates, not repository development instructions. See
docs/projects/MONITORING.md; M4 full acceptance and M5–M8 remain pending.

Render trusted template links before inserting user metadata so template-looking
project names remain literal data. If connection/project/checkpoint capabilities
are unavailable, distinguish an unsaved capability report from an actual durable
BLOCKED/PARTIAL receipt. Queued extraction can return stored source/version IDs,
but never an invented ready passage citation. Preserve these independent forward
evaluation cases when changing project prompts or package generation.

## Project evidence and reporting conventions

Results bind actual reserved attempts or monitoring cycles, immutable ready
passages, claim revisions and exact Wiki publication proofs. Generic stored
objects cannot stand in for research results. Consequential findings require
bounded recorded contrary checks; pending checks stay partial. Keep source
observations untrusted and never infer semantic truth from confidence.

Reports use individual result memberships with substantive saved Markdown ranges
or pinned appendix references. Explicit deferral stays due in later reports.
Finalize under the project transaction lock with actual readback and no omitted
completed evidence. A saved result resumes its merge without another attempt;
publication retries reuse the saved report. External result, notification and
human-read observations remain independent and attributed. Preserve exact
revision annotations and reject page JSON envelopes in project Markdown. See
docs/projects/REPORTING.md. M5 acceptance and M6–M8 remain pending.

Report membership counts as reported only in its exact saved draft generation;
abandoned drafts and deferrals cannot hide completed evidence. Scope changes
invalidate old coverage for the changed scope. Pending published results may be
explicitly re-reviewed at their expected revision after claim changes/retraction
without another attempt; keep all old findings/proofs and completed results
immutable. A retracted claim can only support an explicitly outdated/contradictory
historical finding. Reverify updated Wiki/claim state before completing the work.

## Project maintenance conventions

Use bounded audit transactions and individual findings/observations, preserving
cursor revisions across overlapping runs. A structural slice or selected semantic
batch is not a full semantic audit. Reviews bind the actual current Wiki revision;
changed selections retain history and require explicit refresh. Reserve a rotating
slot so risk selection cannot starve the inventory. Peripheral expiry requires a
distinct actual future weekly checkpoint; resumed old runs cannot expire their
own newly created topics. Archive snapshots preserve lineage/evidence and topic
history, with upgrade snapshots labelled honestly.

Calendar recurrence goes through ordinary queue admission and retains causal
expansion priority. Bounded history may defer novel candidates visibly; exact
matches and existing work retain recovery without deleting history. Release
collection stays external, bounded and metadata-only; failed checks cannot claim
up-to-date or trigger installation. Reuse trusted Core input schemas in tool
metadata, keeping Core validation and old released-Core upgrade guards. See
docs/projects/MAINTENANCE.md. M5 exact full/native acceptance passes; M6 acceptance
and M7–M8 remain outstanding. No live migration, deployment or schedule activation.

## Project export/preparation conventions

M6 corrected1000839 full40414161692 and independent actual native/artifact audits
pass; M7 export/preparation is under validation. The Core export reader uses a
fixed table/column catalog, current space Reader authority, bounded pages and
immutable text fragments. Never export authentication/session tables, server
paths or invent historical object/claim payloads. Two-pass metadata/cursor
comparison detects concurrent changes; it is not a transaction snapshot. Native
DB/files backup remains the complete original-binary recovery path.

External tools write new private0700/0600 destinations, read back SHA-256 and
reject symlinks/traversal/partial inventories. Offline WikiPlant preparation
never executes upstream code or binds target IDs. Serialized page envelopes
produce blocking repair proposals, keeping original bytes unchanged. Static
export requires both explicit immutable selection and saved public metadata;
never add private dependencies or deploy output automatically. Absolute URLs to
the bound C0 host must pass the same private-page, cross-space and citation
destination checks as relative links.
Unsupported nested/multiline/unmatched brackets require review; never pass them
through as unchecked Markdown links/images. Disarm leading frontmatter across
newline conventions and keep image-omission labels free of link syntax.

Client YAML uses bounded SafeLoader with duplicate/alias/tag denial; no Core or
runtime YAML dependency. Private GitHub collection is explicit destination/repo
consent using existing worker credentials, exact namespace and fresh access/ID
checks before frozen replay. Public-only defaults remain. Typed C0 subscriptions
select registered types and independently authorized source space; no implicit
cross-space graph authority. Keep source text untrusted and independent English/
Italian synthetic fixtures. See docs/projects/EXPORTS.md. M8 release/default
adoption and actual external-agent/unattended verification remain outstanding.

## WikiPlant M8 distribution/final acceptance

M0–M7 are accepted. Corrected M7 b5e84bb full40433543339 and independent actual
native/artifact audits pass2262 Python/PostgreSQL/packaging,196 Node,21 Robot,
Debian upgrade21 and Rocky installation26/three expected skips/all8 browsers,
privacy8/accessibility32 and three zero-candidate OAuth-query artifacts. Preserve
all prior/frozen source/image evidence and the original deployed predecessor
digests; M7 candidates are not a live deployment.

Core0.34/app0.53/worker0.2 use schema0021 unchanged. Exact prepublication cd8e7a8
full40443878849 and independent actual native/artifact audits pass2262 Python,
196 Node,21 Robot, Debian upgrade21 and Rocky installation26/three expected skips,
all8 browsers/privacy8/accessibility32/three zero-query artifacts. Immutable
core-v0.34.0 points to that source; publication40449147120 and downloaded asset
checksums pass. Default app/lock now adopt that exact tag with >=0.34,<0.35 and
matching patch-only Renovate bounds. Never edit packaged Core bytes after tagging
without a new version. The original fork example retains its independent0.24
contract. Final ready-PR exact-head proof is recorded on the PR; prepublication
proof alone cannot authorize its merge. Keep namespace/auth/schema checks intact.

Independent wheel/archive probes must exercise actual protected project state,
repeat migration/readback, immutable Wiki/source export and current delegated
grant revocation without app/NS8. Installed worker CLI tests use both synthetic
YAML projects and offline raw layouts, with no server packages or writes. Runtime
health expectations follow producer versions while predecessor identities stay
frozen. Record final ready-PR proof; do not infer main promotion or deployment.

The authorized scope ends at implementation/acceptance and the complete external
scheduler handoff. Real project names/data, reference-instance deployment,
external-agent execution, unattended scheduling, migration and website publication
remain separate/unverified. No live project spaces or schedules are created.


## WikiPlant backend deployed acceptance — 27 October 2026

PR39 is regularly merged at c2280f5. Actual main40466342634 full/native/canonical
publication and independent artifact audits pass 2,262 Python/PostgreSQL/packaging,
196 controllers, 21 Robot, Debian upgrade: 21 passes and Rocky installation: 26 passes/three expected
skips/all eight browsers, privacy8/accessibility32/three zero-query artifacts. Six fresh
canonical alias reads verify. The separately authorized dedicated installation
accepts app 0.53/Core 0.34/schema 0021 at that source; freeze its three actual installed
digests/tag in PLAN as the next genuine upgrade predecessor. Do not substitute a
documentation-marker build or overwrite the prior e384bed evidence.

C0-only backup/full data-integrity read, targeted update, exact installed identities,
trusted HTTPS, original 28,077 stable rows/40 domain tables, three background grants,
configuration/auth/retrieval/mounts/schedules/terminal jobs and ten unrelated
instances pass before/after a supported dedicated-manager restart. Signed-in
owner-session preservation, separate fresh native SSO, five protected Wiki reads
and the existing connected MCP profile pass. Server advertises 117 operations;
the current host caches old tools and needs catalog reload. Do not revoke or
reconfigure the working connection to manufacture that observation.

Root-journal windows each contain 28 actual app entries with health/profile/native
callback/token/MCP positive controls and zero query/credential/JWT/traceback
candidates. Fresh delegated consent/scope upgrades and other live roles were not
exercised. Live original-file corpus is empty; nonempty recovery is disposable.
No project initialization, real migration, research schedule activation, existing
knowledge mutation or static-site publication occurred. Project research,
project-skill host use and unattended execution remain separate verification.

## Remembered website acceptance — 27 October 2026

Use five-minute server-side one-use sign-in intents and exact Origin/browser binding before requesting offline access. Only verified offline issuance enables remembered mode. The seven-day cookie and browser inactivity window slide after successful authenticated website responses, never public/failed/MCP traffic. Recheck current roles/native/session state before renewal; logout and expiry cannot be revived. Keep browser and connection inactivity independently snapshotted; preserve the remembered choice through explicit background sign-in. Ordinary grants remain finitely bounded and remembered authority alone cannot authorize persistent grants. Existing rows default ordinary. Core0.35/app0.54 use additive schema0022; publish Core before adopting its immutable tag/lock. Preserve historical c2280f5 evidence and freeze all three actually installed 31b0c85 digests in PLAN for future genuine upgrades.

After successful verified sign-in, retire the incoming browser cookie through Core `replace_browser` before returning the new cookie. Preserve existing client grants and their original deadlines; stale old responses must not restore website access.

The first-party sign-in form needs `Referrer-Policy: strict-origin`: Chromium sends `Origin: null` for a navigation form under `no-referrer`. Keep exact Origin validation (including rejection of null), and retain `no-referrer` on the subsequent provider redirect. A real headless Chrome negative/positive control reproduces this distinction; native browser sign-in must pass before acceptance.

Core0.35.0 is immutably published at `254fd3f` after exact full40518599847/native/artifact/promotion gates and publisher40529304349; downloaded checksums and eight supplied-artifact checks pass. The app adopts that released tag/lock with >=0.35,<0.36 and matching Renovate patch bounds. Repaired aa9bfd0 passes full40541383069 and independent 2298-case frozen-lock consumer validation. Approved PR42 regularly merges at31b0c85; actual main full40581381116, canonical publication, independent downloaded native/privacy/scan audits and exact-source promotion verification pass. Main passes2298 Python/PostgreSQL/packaging,197 Node24 and21 Robot cases, Debian upgrade21, Rocky installation26/three expected skips/all8 browsers,6 remembered recovery stages,8 privacy guards,32 accessibility contexts and3 zero-query artifacts.

The approved dedicated update and manager restart accept that exact 31b0c85 trio. C0-only backup/full data read, trusted HTTPS, schema0022/timer readiness,32795 original stable rows/40 domain tables,settings/auth/retrieval/mounts/schedules,3 original background grants and10 unrelated instances pass. Ordinary sessions remain ordinary. Live owner REST/five protected Wiki reads, real-provider remembered offline issuance,seven-day cookie attributes/rolling/jar reload,restart retention and own-browser logout/replay rejection pass. The existing MCP profile and4 authorized-space discoveries work after update/restart and after test-browser logout, without reconnect or client changes. Both bounded root app journal windows have38 actual entries with successful request controls andzero credential/query/JWT/traceback candidates. Original-file corpus is empty live; nonempty recovery,other roles and provider/client revocation remain disposable evidence. Broader scheduled/research acceptance and the CPU/interactive Playwright waivers remain unchanged; no stable module release is claimed. See PLAN for precise boundaries and immutable identities.

## Full-document Explorer candidate

The feature authorizes no live access, deployment or merge. Released Core 0.35.2
at 3fb900e/schema0022 passes full 40774328932, both native distributions, downloaded
artifact/privacy/scan audits and exact promotion verification. Publisher 40782732045
and downloaded checksums pass. Preserve this immutable release; the app 0.55
candidate pins its exact tag/lock with >=0.35.2,<0.36. No migration is introduced.

DocumentService reads immutable source bodies and verified parent snapshots under
current Reader/space authority. Never concatenate retrieval chunks. This historical
PR44 checkpoint used part-history identities; the latest-only contract now requires
verified current-generation membership and exact full hash verification. Keep UUID lookups indexable and the part-exclusion equality
join: the 10,000-parent regression must pass the unchanged five-second SQL bound.

Ordinary navigation lists bounded summaries. Legacy source/version/chunk links
resolve containing documents through the authoritative full-document endpoint,
independently of optional metadata hints. Reuse the allowlisted Markdown renderer,
worker parsing and yielded DOM construction; access/selection loss invalidates
all late work. Selected snapshot provenance overrides original source fields;
malformed optional URLs/dates/paths must not prevent reading. Technical evidence
retains exact citation IDs, offsets and hashes. No automatic Wiki duplication.

All six genuine disposable Playwright cases are mandatory in runtime CI; the
older interactive waiver cannot satisfy them. Keep signed test SSO, actual HTTP,
PostgreSQL and the standalone extraction worker, with sanitized failures and
owned-fixture cleanup. Final app consumer/native evidence belongs in its PR;
this is neither a production update nor a stable NS8 module release.
