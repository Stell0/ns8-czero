# C0 / ns8-czero — Instructions for coding agents

Person-role selectors and saved summaries use cumulative labels: **Read**,
**Read and write**, **Read, write and manage**. Preserve single role selection and
independent application consent scopes; do not reuse role labels for scopes.

Cross-space reference producer work is tracked in
[its contract](docs/cross-space-references-plan.md): Core0.47/schema0038,
plugin1.10, five stable endpoint kinds, outgoing-only summaries and explicit
source/target selectors. References confer no authority or evidence. Preserve
metadata-free storage, both-endpoint read checks, blind source-owned deletion,
credential bindings and revocation lock order. The released consumer lock and
installed runtime remain separate from source acceptance. App0.65 adopts
released Core0.47.0 at `884ff312c18fbc18bb613137bbb6ced17df6cfb0`, schema0038,
with matching patch-only updater bounds. Keep the Core package tree identical
to that immutable release and preserve the genuine app0.63/Core0.45 native
predecessor. Require final released-consumer/image/native acceptance before
promotion; no live deployment is included.

Retrieval evidence producer work is tracked in
[its contract](docs/retrieval-evidence.md): Core0.46/schema0037, plugin1.9,
bounded whitespace normalization, one exact supporting passage and opt-in
`context-v1` embedding inputs. Preserve legacy profiles and the released consumer
lock. Source implementation does not authorize live activation or publication.

The current accepted dedicated installation is app **0.61.0**, released Core
**0.42.0**, schema **0034**, source `827fbde711325a2f67b08ca7fee3d9ac5e950b67`.
Its supported C0-only backup/update, manager restart, preservation, live HTTP/MCP
and root-journal acceptance are recorded in
[PLAN](PLAN.md#openai-system-one-scoring--accepted-delivery). Freeze its installed
CI tag/digests as the next genuine predecessor. Retain the prior `a8bb2e8`
installation, immutable Core release and all earlier evidence.

Core0.44.0 is immutably published at `bb882504fb5ab3b94f10bd1d286b06fa81b004ea`
after PR99's regular merge, full PostgreSQL/native/browser/artifact gates and
publisher42407305955. It adds schema0036 document BM25 and preserves exact
citations. App0.62 adopts the released tag/lock through regularly merged PR100
with exact consumer full/native/browser/image acceptance. Main42413222963,
independent artifact audit, full promotion proof and six registry alias reads
pass. Production remains app0.61/Core0.42 as recorded above.
See [BM25 acceptance](PLAN.md#document-bm25--released-core-consumer-adoption).

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

## Tests are part of the feature

Use the [CI policy](docs/ci-policy.md) on the exact latest original C0 main and
candidate. Every PR gets fast automatic checks. Installation/configuration,
containers, migrations, authentication, dependencies, CI/policy code and uncertain
changes also get automatic full Debian/Rocky native acceptance. Reviewed
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

Queued extraction work follows the [M0 contracts](docs/ingestion-pipeline/CONTRACTS.md)
and [baseline evidence](docs/ingestion-pipeline/BASELINE.md), one independently
reviewed milestone at a time. M0 contracts are reviewed for the
[M1 producer candidate](docs/ingestion-pipeline/M1.md): private native-actor leases,
not public HTTP/MCP handoff or publication. Preserve disabled defaults and the
released consumer lock. M1 full `41605913790` passes and regularly merges as
`6380d38`; [M2](docs/ingestion-pipeline/M2.md) adds PDF publication and merges
as `d2fc9a5` after full `41616861662` and `41620456266`, both native distributions,
artifact grading and exact-source promotion verification.
The operator authorizes isolated successor development while prerequisite CI runs,
but acceptance and merges remain sequential. Native/rollout fixtures are disposable;
live deployment remains separate. The [M3 implementation](docs/ingestion-pipeline/M3.md)
adds bounded native workers and actual two/four-worker resource/restore grading.
Preserve both timers' activation during backup and the CPU-quota waiver. M2 full
local passes 2,619 cases; actual CI/native acceptance remains source-bound.
Seed extraction fixtures before native retrieval is indexed/paused/snapshotted;
retain strict derivative completion through update and restore.
The [M4 implementation](docs/ingestion-pipeline/M4.md) extends complete publication to
DOCX, Markdown and text; keep source-sync receipts and public authority unchanged.
M5 derives bounded current section/block/reference metadata and versioned chunks.
Keep ancestor context separate from exact citation text; no automatic backfill.
Optional structure bounds must not reject otherwise valid complete originals.
On derivative overflow only, retain the verified body with null structure and
actual fixed chunks; parser/integrity failures remain publication failures.

M6 local OCR is explicit and limited to unsupported PDF pages; preserve fixed
commands, backend/model fingerprints, whole-process-group deadlines and disabled
pending-work behavior. No cloud OCR adapter or data egress is authorized.
M7 reuses only same-space current or unexpired staging output, with exact input/
profile hashes and an ownership recheck at completion. Preserve fresh IDs, 410
and immediate current-content cleanup; no permanent body cache.
M6 is accepted at `39dc9cc` after full/native `41699410483`, independent artifact
grading and exact-source proof. Preserve actual nine-unit OCR/resource/restore
grading in subsequent cache/context/rollout candidates.
M7 is accepted at `e9a485f` after full/native `41708740692`, independent downloaded
artifact grading and exact-source promotion. Preserve current/staging ownership,
complete-body fallback and strict native resource/restore evidence in successors.
M8 context reads bind canonical logical ID, exact current revision/hash and
source citation offsets. Preserve no-fallback budgets and closed error mapping.
Keep the released older Core catalog working, and the existing App identity and
scopes unchanged. Plugin 1.4 guidance is conditional on advertised capabilities.
Guidance UI keeps stable workflow IDs and exact capability-bound inventory,
including read-only selective context for Readers. Preserve protected-space
role checks; the failed M8 `4589600` native inventory evidence stays frozen.
M8 repair is accepted at `dd5f341` after full/native `41727509130`, independent
artifact grading and source verification. Preserve its Reader guidance, stable
workflow IDs and exact old/new capability inventories in M9/M10. PR65 remains
failed and frozen; neither it nor the installed runtime is replaced as evidence.
Extraction units never become external source-sync publication parts.
M3 and M4 are accepted at `ed160592` / `b51112e`, with full native/artifact
proofs `41654247380` / `41666816436`. M5 is accepted as `b0db3d2` after full/native `41687775493`, independent
artifact grading and exact-source verification.
M6 adds explicitly enabled local-only OCR; keep fixed commands, installed model
hashes, isolated process-group deadlines and readable-page extraction unchanged.

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

Knowledge-compilation M3 is accepted as PR91/mainc16eb49 after full/native and
independent artifact/promotion proof (42373737405/42378485191). M4 producer
Core0.43/schema0035 adds bounded external after-answer proposals and the missing
M3 assessment-key index.
Search remains read-only and policy defaults stay disabled. Readers, explicit
read-only tasks and missing actual Write skip feedback. Never pass queries,
answers, conversations or benchmark labels into compiler metadata. The six-table
coordinator and M2/M3 engine retain authority; a queued task is not compilation.
App0.61 keeps the released Core0.42 lock inherited from PR94. No Core publication, consumer
adoption, live activation/deployment or schedules follow from this source work.
See [M4](docs/knowledge-compilation/M4.md) for bounds and recovery.
M4 exact-head/main acceptance now passes (42392187969/42397304098, PR95/main52e84a3).
M5 producer work is tracked in [M5](docs/knowledge-compilation/M5.md): App0.63,
Core0.45/schema0036, plugin1.8 and the independent external c0-compile runner.
The optional weekly selected-page model reservation reuses all six tables,
current source/page guards and shared budgets; never reopen a terminal task to
account for inference. Detect that alternative in actual checkpoint schemas.
Keep the released Core0.44 consumer lock and registered app identity. Generated
prompts/packages install no tasks. No Core publication, deployment, production
learning/knowledge/schedules is implied by M5 implementation. M5 exact-source
full/native acceptance passes in PR105 (477331a/full42418905512).
[M6](docs/knowledge-compilation/M6.md) measures reviewed compiler publication and
matched retrieval only in owned disposable SQL fixtures. Keep labels/answers out
of construction, bind independent answer audits to frozen episodes, preserve
failed thresholds and unknown judgments, and require separate authorization to
copy private originals. No source/knowledge/policy/schedule production writes,
Core publication or deployment follow from benchmark acceptance.


Source documents and Wiki pages retain only their current complete content generation. This latest-only contract replaces the previous content-history guarantee. Keep stable logical IDs, monotonic concurrency counters, current hashes/provenance and payload-free retry/change identities. Stage replacements privately and publish whole documents atomically; delete superseded bodies, originals, derivatives and indirect receipt copies. Exact expired evidence returns authorized `content_superseded` (410), never rebound text. Preserve authored knowledge and mark invalidated evidence stale. See [migration and preflight](docs/latest-only-migration.md).

The connected assistant performs reasoning and synthesis. C0 serves knowledge and deterministic registered operations. Its worker extracts/indexes content and runs registered jobs; adding arbitrary model execution or shell commands to a request handler is outside the current product boundary. Optional retrieval providers cannot decide authorization or make ordinary text search depend on a model API.

Describe integrations accurately. C0 ships OAuth-protected MCP, an instance-bound skill and a ChatGPT-specific plugin package. Other assistants use their own connector and skill formats. Separate vendor MCP support from actually tested C0 compatibility. Interactive OAuth success does not establish scheduled execution or packaged-skill acceptance. MCP HTTP 200 can contain a tool error; inspect the tool result and verify saved revisions before claiming success.

The normal browser pages are readers. Keep mutation tools, technical client controls, protected-space grants and jobs/schedules on their established surfaces. Preserve the people-first access page's distinction between application approval, user permissions, exact connection disconnect and persistent blocking. Avoid an ambiguous Revoke action. Authorized Wiki changes publish immediately with latest-only storage. Source replacements publish only after extraction and whole-document validation; this is an integrity boundary, not an editorial approval stage.

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
workflows. This rewrite requires full Debian/Rocky acceptance; a component build
or mock API test alone is insufficient. See [the contract](docs/vue-website.md).
PR75's app0.59/Core0.38/schema0032 source and actual main `c011a0b`
pass full/native/artifact/promotion and canonical publication. Preserve the exact
[accepted image identities](PLAN.md#vue-3-website-remake--source-and-publication-accepted).
The dedicated app0.59 installation is accepted as recorded in PLAN; subsequent
live updates need explicit authorization and their own acceptance.

## Contracts to preserve

Native OAuth callbacks may choose a port only for a portless approved HTTP
loopback URL. Keep the original host/path and explicit-port/HTTPS exact checks,
use the shared Core matcher throughout approval/consent/authorization, and bind
code redemption to the exact requested callback and PKCE proof. SDK descriptor
projection is request-local; never persist an observed port into the registered
client. Older released Core retains exact behavior until explicit adoption.

Authorization uses current persisted Reader/Editor/Admin membership inside Core transactions, explicit protected-space selection and actual delegated scopes. Tool discovery does not grant authority. Preserve lock ordering, exact evidence identities, expected revisions and payload-free replay receipts; a superseded request returns 410 instead of old content. A denied space must never fall back to Shared. Optional providers cannot decide authorization or make ordinary text retrieval unavailable.

OAuth keeps verified native identity, explicit consent, S256, exact callback/resource/host/origin checks, bounded bodies and duplicate rejection. Authorization may ignore future optional parameters only after full multimap validation; token/revocation remain strict. Refresh cannot add scope or extend the original absolute authority. CIMD defaults off, approves exact HTTPS URL identities, pins public DNS/TLS peers and rechecks authority after I/O. Remote metadata never supplies roles. Existing UUID clients remain independent.

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
Core0.36.1 is immutably published from merged source8dbb746; app0.57 stages its
released tag/lock adoption. Keep the published Core bytes and failed main mirror
evidence frozen. Consumer/full/native/review/deployment gates remain separate.
Reference publishing selects released Core when its committed package tree equals
the consumer lock's immutable Git tree; differing trees remain explicit producer
development. Invalid or missing identities fail without fallback. Verify the
released Git source in the actual published/native app image, not only a temporary
probe. Producer acceptance is not released-consumer deployment proof.

[CI policy](docs/ci-policy.md) defines the current risk-based checks. Every PR
gets fast checks; sensitive/unknown changes automatically require full native
acceptance, and allowlisted presentation changes can request it on demand. Full
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

The accepted dedicated runtime is app **0.57.0**, released Core **0.37.0**,
schema **0030**, source `5e89055de12f46b2e87325d8fee1e6ee59dfa15d` after the
separately authorized 4 November update and manager restart. See [exact installed
identities and predecessor](PLAN.md#ingestion-deployed-runtime-and-frozen-predecessor--4-november-2026).
The genuine immediate predecessor is `96b55d81` / Core 0.36.1 / schema 0023;
retain all its immutable images and historical `31b0c85` evidence. Supported
backup/read-data integrity, actual released-Core/image identity, old-column data,
settings/schedules/connections/unrelated inventory, native sign-in and bounded
root privacy journals pass. Extraction/OCR remain disabled with no backfill.
Runtime plugin 1.4.0 matches its exact offline bytes; this client's cached 1.2.0
plugin/catalog still needs refresh for the four new tools. Model quality remains
open, with no model calls, production reindex/import, new external schedule or
stable module release. Documentation changes never replace installed images.

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

M9 extraction progress is metadata-only and selected-space. Keep Admin unit
diagnostics separate from ordinary readers. Retry retains original run authority;
it never promotes a browser or OAuth grant to native authority. Explicit reindex
requires retained original bytes and publishes fresh exact evidence atomically.

M10 benchmark outputs stay private until sanitized aggregation. Distinguish
output-cache state from operating-system caches and sampled RSS from exact peaks.
Keep model authorization, observed evidence/citations, producer publication,
released-consumer proof and deployment separate. Restart tests require a labelled
owned disposable database container and may never share the acceptance cluster.


Core 0.37.0 ingestion producer source `37ce3cec` is now immutably published by
41754099289 after its accepted M9 exact-source full/native proof. The existing
signed tag never moves; downloaded wheel/source checksums match prepared bytes.
Publisher repair PR68 regularly merges as `2096f11` after full/native41746485159,
independent artifact audit and full promotion proof. Keep the failed first
publisher41745977134. M10 consumer adoption pins the released tag/immutable Git
source with >=0.37.0,<0.38.0 and matching patch-only updater bounds, schema0030.
Do not edit the frozen Core package tree720902f5bfdc3774d93660e8b968943498e15288.
Final consumer/native/main publication and separate checked closeout remain;
model quality is open by operator decision. No live/default/stable-module change.


Ingestion M2–M10 implementation and deterministic/disposable released-consumer
acceptance are complete at main `84a0bcd09de6e2f5b4d263c7509c977488505415`.
PR69 exact `b22d7c9`/full `41754721407` and actual main/full `41761803984` pass,
including independent artifact audits and exact-source full promotion. Both CI
and the exact-head Git consumer pass 2,760 cases without database skips; actual
published Core distributions are included. Native installed images match the
independently checked published app's Git source/schema; six fresh canonical
registry identities pass. Frozen images and exact results live in
[the M10 closeout](docs/ingestion-pipeline/M10.md#accepted-main-publication).
Model/held-out answer quality stays open by operator decision: no model sessions
or non-inferiority claim. Keep extraction opt-in and public imports on their
established path until separate default/durable-authority acceptance. No live
update, production import/reindex, external schedule or stable NS8 module release
occurs. Preserve the installed `31b0c85`/app 0.54/Core 0.35/schema 0022 baseline,
failed/private evidence, immutable Core 0.37 bytes and both operator waivers.
Documentation commits never replace accepted runtime image identities.

## Personal API keys

Personal automation key contracts live in [docs/api-keys.md](docs/api-keys.md).
Preserve API-key bindings through trusted Actor refreshes and operation policies;
keys remain scoped credentials, never native extraction or first-party authority.
Core0.38.0 is immutably published from `2eb0b453f329f2f1044ff6151854298aac1b7e88`
after full/native41820035695 and publisher41837683939. Schemas0031/0032 bind keys
to persisted account/space revisions; preserve the schema0015 grant-setup path.
App0.58 adopts its released tag/lock with patch-only >=0.38.0,<0.39.0 bounds.
Released consumer `00ffd370c0f9c9241eed26c91d7725078cea86e7` passes
full/native41840958720, independent artifact grading and exact-source full
promotion; PR73 regularly merges as `1a92b7aebbec3c5ad217f03e84f2b57a250f9d18`.
Actual merged-main41851447750 passes full/native, independent artifact grading,
canonical publication and six registry identity reads. Preserve its original
promotion-verifier failure on an optional skipped screenshot publisher. PR75
corrects selection to require both actual native suites exactly once; 155 policy
checks, including 12 new regressions, and the corrected historical main full
command pass. Current-source promotion remains mandatory. The exact consumer
candidate's full promotion check passes. Preserve immutable runtime identities
in PLAN; documentation commits do not replace them. The installed
app0.57/Core0.37/schema0030 baseline is unchanged.

Embedding drain candidates must preserve transactional continuation/completion,
worker bounds and progress for other jobs. BEIR report exclusions are exact
revision/hash pins, evaluation-only, and never relax source/citation verification.


Core0.39.0 is immutably published from b05ebe46 after full42264181476,
independent native/artifact audit and publisher42273069369. Schema0033 is inherited;
no new embedding migration is added. App0.60 adopts the released tag/lock with
matching patch-only updater bounds. Consumer a8bb2e8 passes full42284156460,
independent native/artifact grading and exact-source promotion; PR87 regularly
merges as fe9e8e8. The installed app image uses the released Git Core source.
Supported backup/update, unchanged original tables/settings/schedules/credentials,
ten unrelated instances, manager restart and real HTTP/MCP/journal checks pass.
Main/publication and benchmark acceptance remain separately recorded in PLAN.

## OpenAI System One accepted delivery

The current-base successor preserves M3/schema0034 and targets producer Core0.42.
Do not publish over M3's0.41 identity or initialize compilation maintenance.

The System One adapter now targets OpenAI Decisions named predicate answers.
Preserve its public search metadata, five-second deadline, sixteen-candidate
limit, 2 KiB excerpts and authorization rechecks. JEV/Kev configurations require
explicit endpoint/model/key replacement; do not transfer credentials.
Producer Core publication, released-consumer validation and dedicated delivery
remain separate acceptance gates. Run the full nine-way SciFact comparison only
after the operator saves the OpenAI key; reuse existing corpus receipts and keep
all instance identities and benchmark artifacts outside Git.

Core 0.42.0 is immutably published at 58cbb823 after full42380719326,
independent native/privacy/scan grading, promotion and publisher42385896972.
PR93 regularly merges as 7e637926 with identical tracked bytes. App0.61 adopts
its released Git tag/lock with >=0.42.0,<0.43.0 and patch-only updater bounds.
Consumer 827fbde passes full42387325979, independent native/privacy/scan grading
and full promotion. PR94 regularly merges as 39c40593 with identical tracked bytes.
The installed app verifies the released Git tag and commit. Supported backup,
read-data integrity, update and manager restart preserve content, settings,
credentials, existing schedules and ten unrelated instances. Fresh HTTP/current
and legacy SDK/connected-tool reads and positive-control root journal audits pass.
Compilation tables remain empty; existing housekeeping schedules stay unchanged.
Actual consumer main 39c40593 passes full42391601033, independent artifact grading,
promotion, canonical publication and six fresh registry identity reads. Preserve
the published Core bytes and installed CI images. After operator key setup, real
nonempty OpenAI rerank/filter reads pass without fallback; the full nine-way
benchmark remains a separate private evaluation. Do not claim its quality before
all cells validate or change the frozen threshold from test labels.
