# C0 / ns8-czero — Instructions for coding agents

## Authoritative development CI policy

The operator's scoped-development CI instruction supersedes historical demands
for full acceptance on every incremental commit or documentation marker. Read
[docs/ci-policy.md](docs/ci-policy.md). Draft updates use changed-area tests plus
shared authorization/compatibility smoke; CI/auth/Core/build changes broaden
feedback and unknown paths fail closed. Only the explicit reviewed Git-only
allowlist gets lightweight documentation checks, including documentation-only
main commits. App/static HTML, packaged documentation and generated contracts
are not exempt by extension.

Mark runtime PRs ready for review to trigger full exact-source acceptance; every
subsequent commit repeats it. Require the actual `C0 merge gate` and run
`scripts/verify-promotion.py --source <head> --pr <number>` before merging.
Scoped feedback, skipped/cancelled jobs and old successes cannot authorize a
runtime merge. Main runtime, immutable releases, genuine predecessor upgrades,
all automated browsers/artifact privacy and dedicated deployment/milestone gates
remain mandatory. Use `validate.yml` manual full dispatch instead of historical
independent image-publisher dispatch instructions. Full acceptance runs and
frozen branches must not be cancelled or changed unexpectedly. No test shards
share a mutable PostgreSQL database; preserve both existing waivers.


This repository is the **C0 (Czero)** application template for NethServer 8. Read [PLAN.md](PLAN.md) for authoritative milestones and [README.md](README.md) for the public product contract. **Current status (19 October 2026):** Agent Memory AM0–AM6 runtime acceptance passes. Accepted AM6 source `97a7a1b` was installed from immutable CI candidate images at Core/app/schema **0.29.0/0.45.0/0016**; regular merge `e378a89` preserves the exact tested tree. Full PR/main CI and actual native/artifact audits pass; canonical main publication is verified in PLAN.md. Caller-filtered agent guidance reuses all 76 tool contracts. Supported backup, canonical targeted update, real readiness and full-manager restart preserve 8236 original rows across 33 tables, six originals, configuration/schedules, 153 pre-update and 155 pre-restart terminal jobs/attempts, thirteen prior backup plans and eleven unrelated instances. Immediate same-grant/browser checks pass after update (58.2s) and restart (36.7s). Independent current/legacy SDK workflows and post-restart reuse pass; the owned temporary client is disabled after same-bearer REST/MCP controls. A bounded 139-entry root app journal has successful health/authorization/token/MCP controls and zero query, issued-secret, submitted-content or traceback matches. The existing connector separately reauthenticates/reads; its cached 63-tool catalog does not prove refreshed 76-tool discovery or observed prompt evaluations. Freeze the three installed `97a7a1b` candidate digests in PLAN.md as the genuine next predecessor; main/closeout images do not replace it. Integration M20 has resumed separately; no renewal implementation was included in AM6. Windmill Gate remains separate. Existing waivers remain; no stable module release is claimed. **Historical M14 baseline:** M00–M14 candidate implementation/acceptance pass under the recorded interactive Playwright and CPU-quota waivers. Exact M14 source 5be82b7 passes 675 actual Python/PostgreSQL/packaging cases, eighty-six real-script cases, local/producer/released-Core CI and both native QEMU distributions: Debian sixteen passes/three expected skips, Rocky twenty-six passes including all seven real browser workflows. Nineteen numeric accessibility contexts, measured small-fixture latency/RSS, exact recovery/backup observers and actual artifact privacy audits pass. The recorded M14 live acceptance ran this verified source with canonical inventory identity; targeted update and final full-manager restart preserve data/settings, scoped OAuth/SDK parity and timer health, with temporary clients disabled. Other roles are proven in disposable browsers, not claimed live. Verify actual final main completion-marker CI; never infer a pass from workflow start. Core/app/schema remain 0.24.2/0.39.0/0013. M13 distribution/skills/updater evidence remains valid. No stable module release is claimed; vendor scan findings, real-provider quality, scheduled-run interoperability and deployment-specific IdP/proxy/log policy remain release/maintenance work. See docs/m14-readiness.md and docs/m14-release-notes.md. Freeze all three deployed 5be82b7 digests there for future genuine upgrades. Do not revive deferred CPU quotas without a new operator request.

## M20 corrected runtime acceptance; closeout pending

PR 22 regularly merges candidate `4137048` as `cba48675` with the same tree. Final ready-PR 39282323268 and deployed-candidate full 39264711915 pass; actual ready-PR reports/privacy/scans are independently audited. Main 39381904479 is still running: verify its actual complete full/publication proof before closing M20 or coding M17. The current installation is Core/app/schema 0.30.1/0.46.1/0017, from frozen tag `ci-4137048c23d62fac7ee8909385856cbf9fa84116-39264711915-1`, with all three installed digests in PLAN. This supersedes the historical AM6/current-pending paragraphs below. Preserve installed images and published Core files.

Corrected browser/actual ChatGPT continuity passes 2110/2274 seconds with repeated real native rotations, stable identity/context/scopes/bounds, expiry/revocation/reconnect, targeted update, full-manager restart and exact retained data/settings/files/schedules. SDK discovery sees 76 tools; the connector's cached 63 is not refreshed discovery. Owned fixture clients are disabled and other approved clients remain unchanged. The 479-entry actual root app journal has health/auth/token/MCP controls and clean privacy audits. Private evidence and failed candidates remain outside Git. Unrelated module inventory is exact around each C0 action; record the independent between-action changes honestly.

After successful main publication, merge this separate three-document closeout through current lightweight checks and verify its main result. Then implement only M17, using this accepted runtime as predecessor. Preserve all unfinished worktrees and original dirty documents. Existing CPU-quota/interactive Playwright waivers remain.

## M20 resumed after AM6 acceptance

User-directed order is M20, M17, M18, M19, one accepted milestone at a time.
Work from `.cache/worktrees/m20` (`feat/m20-session-renewal`) on verified `6456231`.
The environment cleared `/tmp`; all fourteen original draft files were recovered
from this task's recorded source edits into `.cache/worktrees/m20-original` with
an ignored private archive. Preserve that reference and the original dirty
checkout. Recovered producer checks pass 1342 actual Python/PostgreSQL/packaging
cases, 127 controllers, schema/shell and 21 Robot dry-runs; failed historical
runs are not acceptance. Native predecessor is the installed AM6 `97a7a1b`, with all three frozen
candidate digests in PLAN. Keep CPU/interactive-Playwright waivers unchanged.

Core 0.30/schema 0017 is independently published from exact producer `bc5e1dc`.
Full 39217591934 and actual artifact audits pass Debian 21/Rocky 26+3, all eight browser/
privacy guards, 25 accessibility contexts, three clean query artifacts and five scan pairs.
Publication 39222689510 succeeds; actual downloaded assets and six supplied-artifact
checks pass. See PLAN for checksums. No module release/deployment is implied.

App 0.46 local work on `feat/m20-app-wiring` adopts that released Git source/lock;
all transitive records and independent-fork patch bounds are preserved. The full
local suite passes 1380 Python/PostgreSQL/packaging cases, 129 controllers, schema/
shell and 21 Robot dry-runs; the immutable UI build and native Renovate API pass.
A fresh frozen consumer environment installs released Core at the exact lock and
passes 20 real PostgreSQL-backed authentication/renewal cases. Final image/native
gates and actual dedicated acceptance remain pending. Native renewal must be
measured for at least 330 seconds per distribution, with idle/absolute expiry,
rotation, revocation and reconnect metrics; controlled-clock HTTP success is
not that proof. The accepted AM6 `97a7a1b` images remain the genuine accepted predecessor; the unaccepted M20 candidate status below supersedes the earlier deployment checkpoint.

M20 candidate `c440727` passes full 39232074014 and actual native/artifact/promotion
checks, then its supported dedicated update and full-manager restart preserve
exact data/settings/files, old grant rows and both SDK protocols. Actual short
bounds and 410-second same-grant connector rotation pass. It remains UNACCEPTED:
provider introspection confirms refresh expiry thirty minutes before native
access expiry; an active browser then fails at that shorter window. Do not merge
or substitute this failed installation for an accepted upgrade predecessor.

Core 0.30.1 corrects scheduling with a private encrypted `refresh_after` deadline,
capped at five minutes and before both verified access expiry and a supplied
positive provider refresh TTL (thirty-second margin). Missing/zero TTL uses the
bounded fallback; malformed metadata fails closed. Introspection never slides
this deadline. Old 0.30 credentials without the field perform one serialized
real refresh; fixed legacy rows gain nothing. Preserve all existing identity,
role/scope, lock, absolute/idle, crash, replay and outage semantics. Schema stays
0017. Publish a NEW immutable Core patch after exact full producer/native gates,
then adopt its tag/lock in app 0.46.1 and repeat consumer/full/native/live gates.
Never replace 0.30.0 assets or alter provider policy/credential rows to pass tests.

Patch producer `4600739` passes full 39254573692: 1408 Python/PostgreSQL/packaging,
130 controllers, 21 Robot dry-runs, Debian 21/Rocky 26+3, all eight browsers/privacy
guards, 25 accessibility contexts, five scan pairs and three clean query artifacts.
Current ready-PR/full promotion proof passes. Core publication 39261142231 succeeds;
actual asset/GitHub digests and six supplied-artifact tests pass. App 0.46.1 now
adopts immutable `core-v0.30.1` at that source with minimum 0.30.1; keep all other
lock records and independent-fork bounds unchanged. Do not edit published Core
files. App adoption passes 1408 actual PostgreSQL/packaging cases (374.29s), 58
independent frozen released-consumer cases (29.38s), 130 controllers, native
Renovate/schema/shell checks and 21 Robot dry-runs. Final exact-source CI/native/
live gates remain pending. Corrected live
acceptance must measure at least 2100 continuous seconds, multiple actual provider
renewals and unchanged authority/bounds/scopes without hidden reauthentication;
the earlier 410-second success did not cover the observed provider failure.

Public OAuth revocation uses the official SDK handler's client/form validation.
Its trusted route-purpose context lets loaders revoke through Core without native
provider authentication, returning now-absent metadata for idempotent 200. Core
still checks exact client/resource ownership; ordinary loaders retain native
checks, and every context resets in finally. Preserve wrong-client/outage tests.

Session policy defaults to eight hours absolute/one hour idle, 60–86400 seconds,
new-sign-in opt-in only. Core snapshots bounds, encrypts native refresh state,
serializes checks across durable crash markers and rechecks captured browser and
delegated authority inside transactions. Native revocation lock 49382 follows
caller role/client/grant locks; renewal's 49383 session namespace spans provider
work without privileged transaction locks. Local logout must validate cookie CSRF
and Origin without authenticating against an unavailable provider. Transient
outage cannot extend authority; ambiguous refresh or abandoned marker requires
fresh sign-in. Scope narrowing, replay revocation and legacy fixed expiry remain.
The installed recovery snapshot normalizes only the new nullable grant link on
predecessor schemas; all original grant/token/code fields remain exact, and its
actual SQL is exercised on genuine 0016 rows before/after repeated migration.
No-refresh sign-ins retain the fixed session cap even under a longer renewable
policy. Native-client replacement gets a separate per-account authority/grant
budget while preserving global limits, old rows and approved client descriptors.

## AM6 accepted implementation; M20 preserved

The operator prioritizes AM6 before session renewal. Preserve the unfinished `feat/renewable-sessions` worktree at `/tmp/czero-m20`; do not import its Core/OIDC/schema changes into AM6 or resume it before AM6 acceptance. Original drafts remain untouched. AM6 app 0.45.0 uses released Core 0.29.0/schema 0016 and the unchanged 76-operation contract.

`agent_guidance.py` owns product workflow data. HTTP and MCP capabilities filter whole workflows using actual-scope current operation descriptions; public OpenAPI documentation confers no authority. Keep M16 role-eligible upgrade tool discovery separate. Reader guide workflow panels use DOM text, current selected-space role and existing generation/access-loss clearing. Preserve the correct selectors: ordinary MCP content top-level, knowledge_search options, structured search and bundle data; REST content query and bundle body.

Exercise the exact `mcp_tls_probe.agent_workflow` through real independent current/legacy SDK connections, immutable ready evidence, conflict/reload/reconcile, whole receipt retry, annotation history/unknown verification, explicit private-space reads and Shared negatives. Local independent grants and installed same-bearer independent SDK connections are different evidence; neither proves an unobserved ChatGPT UI prompt. Native timer extraction must remain real; reuse already-ingested native evidence to avoid adding a fresh timer wait to each late protocol probe. Retain private stdin/static numeric diagnostics and artifact audits. Keep all three accepted installed AM6 `97a7a1b` candidate images available and unchanged; genuine AM5 `41864e4` digests remain historical upgrade evidence. CPU and interactive-Playwright waivers remain; AM6 exact-source CI/native/live acceptance passes. Full CI verifies 1290 Python/PostgreSQL/packaging cases, 127 controllers and 21 Robot dry runs plus schema/shell. Local quota-blocked packaging setups were resolved by a six-case rerun without changing source; clean full CI passes all 1290 in one run. The native-probe fixture now disposes only its captured protected spaces and jobs, preserving focused/full isolation; never hide leaked fixture data by weakening corpus counts.

## Protected knowledge spaces (AM3 runtime accepted)

- Object-type definitions remain global. Content, immutable derivatives, references, receipts and public feed cursors are space-bound. Omitted selectors and legacy resource URIs retain the permanent Shared UUID; invalid/denied selectors and UUID lookups never infer or fall back to another space.
- Core uses immutable `in_space` service copies and rechecks persisted application/space roles and captured delegated authority after waits/provider work. Admins access all spaces under actual scopes. Reader/Editor protected grants are explicit and capped by current application role. Grant changes delete affected delegated grants atomically; regrant never revives old tokens. Same-space typed references are enforced by services and composite constraints.
- Content REST uses optional query `space_id`; MCP uses top-level `space_id`, except `knowledge_search` uses `options.space_id`. Preserve legacy Shared fingerprints/snapshots and space-qualified `c0://spaces/{space_id}/...` resources. Shared type definitions never authorize private records.
- Space changes/access loss clear private DOM, headings, counts, drafts, catalogs and exports before navigation, reject delayed replies and never silently choose Shared. Administration retains grant revision/retry protection and capped role choices. Anonymous clearing restores each page's public heading; retain its regression and all eight actual native browsers.
- Exact main cb60da9 passes 1048 Python/PostgreSQL/packaging cases, 125 scripts, twenty non-UI Robot dry runs and schema/shell checks. Actual main native reports pass Debian installation seventeen cases/three expected skips and genuine Rocky AM2 upgrade twenty-eight cases, all eight browsers/privacy guards, twenty-five numeric accessibility contexts and both protected clean restores. Actual three-artifact OAuth-query audits pass. Core 0.27.0 is immutable and independently installed/rebuilt from downloaded artifacts; app pins that released source. Preserve waivers and vendor findings. No other live persona, semantic-provider quality, refreshed connector catalog or stable module release is claimed.

## M15 reader UI conventions (accepted candidate)

- M15 uses only existing domain APIs and stored data. `site.js` contains shared presentation helpers and `reader.js` the read-only home/article/source/AI-guide controllers; NS8 Vue settings and Core/schema are unchanged. Main-marker aee90ce local 38701477692, publication 38701477763, released-Core 38701554107 and QEMU 38701819972 are actually completed/successful. Preserve the deployed 5be82b7 images; the feature branch is not a live deployment.
- Normal Wiki/Sources pages are readers. Existing mutation controllers initialize only for `?view=tools`; preserve their draft, replay, CSRF, role and response-generation guards. Manual fields retain IDs inside Tools. New readers also clear private content on access loss and reject late replies. Account/sharing is at `/?view=account`; do not load Admin membership lists on the ordinary home.
- Tree structure comes from fixed slug paths and 100-summary batches, not a new hierarchy API. Show incomplete navigation explicitly; search is independent. Use canonical query links with immutable revision/version/chunk identity. Historical Wiki readers omit current claims. Source passages must match the selected source/version/document before display.
- Render markdown-it 15.0.2 tokens through an allowlisted DOM renderer, never executable HTML; keep raw HTML/images inactive and validate links. Ship its local bundle and MIT license. Product AI task guidance is human-facing help, separate from repository development instructions; file ingestion remains REST rather than an MCP tool.
- Keep every user template balanced with unique attributes/IDs; a malformed search wrapper can silently move controls/results into the form despite a successful basic render. Nested disclosures require direct-child summary selectors. Extend real disposable browser checks for reading, history, evidence and AI instructions while retaining existing Tools workflows. Freeze all three verified M14 5be82b7 digests for the genuine M15 predecessor. Interactive Playwright and CPU-quota waivers remain unchanged. Never claim publication/native/live acceptance from local mocked rendering.

M15 exact source b528d4a passes 695 Python/PostgreSQL/packaging cases, 106 script cases, producer/released-image CI and actual Debian installation (sixteen passes/three expected skips) plus genuine Rocky M14 upgrade (twenty-six passes including all seven browsers). Reports verify twenty-one numeric accessibility contexts, seven browser privacy guards and actual OAuth-query audits. See PLAN.md for exact candidate digests and CI links. Reader UI marker `05713b9` is now merged and its actual main local/publication/released-Core/native checks pass (see PLAN.md). The dedicated instance accepted Integration M15 source `6c02182` at the same versions; the operator now confirms actual ChatGPT connection and authenticated content reading. The operator also confirms signed-in Wiki/REST and client revocation/reconnect; Integration M15 runtime acceptance passes. Integration M15 completion marker `86c8b0a` and its actual main local/publication checks pass; see PLAN.md for its exact native/artifact evidence.

## Active ChatGPT integration plan

- The operator's Integration M15–M20 are separate from the accepted M15 reader UI. Integration M15 source `6c02182` was implemented on `fix/oauth-optional-parameters` from verified `05713b9`, passed exact-source CI/native gates, merged to main and was deployed through the supported dedicated-instance update. The operator confirms actual ChatGPT connection and content reading on that deployed source. The operator also confirms signed-in Wiki/REST and client-disable/rejected-read/re-enable/reconnect checks. Integration M15 runtime acceptance passes; completion marker `86c8b0a` passed its own exact native/artifact checks and main local/publication before Integration M16 started. Keep operator observations distinct from server-observed log stages and SDK simulations.
- Authorization GET/form POST must ignore future optional parameters after checking the full parsed multimap for duplicate names and string values. Keep the sixteen-KiB bound, public-client credential rejection and exact raw callback/resource guards. Filter the raw adapter context to recognized fields before trusted Core processing. Token/revocation remain strict; consent, requested/granted scopes, PKCE and persisted roles retain their existing validation.
- The existing disposable OAuth fixture exercises optional GET/POST and duplicate known/unknown names through signed local HTTP and actual native HTTPS. Preserve its private token stdin handling, exact grant recovery, explicit consent, replay/revocation and artifact privacy assertions.
- Each integration milestone requires exact-source local/publication/both-native CI, reviewed main promotion and successful main publication, verified three-image revisions/digests, supported canonical dedicated-instance update, readiness/data/inventory/log checks and real ChatGPT acceptance. Use the Core release sequence only if Core changes. Keep all private access details and failed evidence outside Git. Existing CPU deferral remains in force.

Integration M15 currently passes 738 actual Python/PostgreSQL/packaging cases, 106 script cases, producer/released-image CI, Debian genuine reader-UI upgrade (nineteen passes) and Rocky installation (twenty-three passes/three expected skips, all seven browsers). Actual native artifacts pass privacy audits. Main local/publication/released-image/native checks and evidence marker `86157dd` local/publication/native checks are completed/successful, with actual downloaded native report privacy audits passing (links in PLAN.md). At M15 acceptance, all three installed main digests/revisions matched `6c02182`; 27 domain tables, 56 original terminal jobs/attempts, retained files, settings/schedules and ten unrelated instances are preserved. Six real trusted-HTTPS optional-parameter cases now return 302 to consent, twelve duplicate cases fail, token/revoke remain strict and actual bounded app journal queries are clean. Actual ChatGPT connection/content reading passes by operator report; subsequent bounded app logs contain successful token/MCP requests and pass the OAuth-query audit. The operator confirms signed-in Wiki/REST and live client-disable/rejected-read/re-enable/reconnect acceptance; record those as operator-verified. A particular tool name and exact granted scopes were not separately reported. Integration M15 runtime acceptance passes; completion marker `86c8b0a` has completed successful local/publication/native checks and successful main local/publication (PLAN.md). Preserve the working ChatGPT connection and all three deployed `6c02182` digests from PLAN.md for the genuine Integration M16 predecessor, rather than substituting newly built documentation-marker images.

## Integration M16 implementation conventions (accepted)

- Derive per-tool OAuth requirements from trusted Core `required_scope`, with matching top-level `securitySchemes` and `_meta.securitySchemes`. Pinned SDK 2.3.0 discards unknown Tool fields at both model and protocol serialization. Its public server middleware restores only that optional field from trusted returned metadata after normal wire validation; raw current/legacy HTTP and ordinary SDK metadata must pass. Do not patch SDK globals or bypass request validation.
- MCP tool listing may use the validated complete supported-scope set as a description filter so persisted-role-eligible operations can request fresh consent. Invocation, resources and REST discovery retain actual granted scopes. Never use `None` or the expanded discovery filter as delegated invocation authority. Core already checks current roles before raising `ScopeDenied`; only that exception gets a fixed `mcp/www_authenticate` insufficient-scope challenge. Role denial remains permission_denied without an upgrade challenge.
- Protected-resource metadata advertises basic `c0:read` initially; authorization-server metadata retains all three independent scopes. Scope challenges name only the current operation requirement. No globally mandatory read scope may block valid write/admin-only tokens. Refresh never adds scopes; new explicit role-eligible consent is required.
- The original M16 upgrade tests freeze all three genuine M15 `6c02182` predecessor digests from PLAN. Future upgrades retain the current accepted `9582568` predecessor digests together. Extend disposable TLS/SSO/browser acceptance for metadata, narrow tokens, fresh consent and isolated delegated Wiki writes/archives. Preserve private stdin, exact grant recovery, Origin negative controls and artifact privacy. Core/app/schema/dependencies and existing runtime limits remain unchanged. Local M16 validation passes 760 actual Python/PostgreSQL/packaging cases, 106 script cases, schema/shell checks and nineteen Robot dry-run cases. Exact M16 CI/native/main/deployment gates pass. The operator accepts the comprehensive 20/20 API report and separately confirms live OAuth checks, including the consent-upgrade/revocation acceptance gate. Attribute these to operator verification; do not invent exact granted scopes, request traces or unreported manual subcases. Preserve the API report's remaining coverage and cleanup limits. M17 is next after this documentation closeout marker's actual CI/main verification.

The live app uses journald. Empty Podman logs or an inaccessible module-user journal are not privacy evidence. Read a bounded root journal filtered by the verified module UID and app container, require actual health/authorization request positive controls, and audit it without changing host logging or exposing raw private entries.

## Established M14 conventions

- The tested Core inventory parses digest-only IMAGE_URL incorrectly even though the agent image-name helper supports it. For live updates, freeze the branch, verify all three OCI digests/revisions immediately before the native action, use its canonical tag and verify installed digest plus module/source/version afterward. Do not edit Core/Redis. Wait for actual readiness before grant/data checks; compare unrelated instances by ID, preserve their group/metadata and normalize unordered flag sets. Keep failed private evidence and disable temporary clients.

- Robot Browser 19.14.2 prefixes evaluation source with `return`. Parenthesize callback expressions that carry leading license comments; otherwise automatic semicolon insertion discards the callback. Exercise the actual API plus the unwrapped negative control and retain bounded numeric/privacy diagnostics.

- Operator explicitly defers container CPU-quota enforcement/testing. Do not ship `--cpus=2` or change host delegation; do not claim CPU-rate enforcement passed. Keep memory/swap/tasks and privilege checks, parser CPU deadlines and worker lifetime bounds. Other CI/native/live acceptance is unchanged.

## Established M13 distribution conventions

- Live OAuth lifecycle fixtures must seed fresh grants after CI, verify immediately after each update/restart and preflight a conservative known-valid token window. Actual grant lifetime is capped by originating native identity/session and can be below five minutes. Keep long data probes after grant verification, retain failed evidence and always disable temporary clients; never extend runtime authority to satisfy a test.

- Native Renovate PEP 440 rejects complete core-v tags despite successful extraction/config validation. Use prefix-aware regex versioning, keep the complete tag and enforce comparator patch bounds. Test its actual API and authenticated lookup before claiming update support. Native rule regression dependencies are development-only.

- Root app now pins released core-v0.24.2/subdirectory/uv.lock by default, with compatible >=0.24.1,<0.25.0. CZERO_CORE_SOURCE=local is an explicit producer-development builder override, selected only by upstream CI; independent forks retain released default. Source validation fails without fallback. Builder-only Git/uv/selector never enter runtime images. Published 0.24.2 artifacts, actual Renovate patch PR and permitted installed/live persistence pass; completion-marker CI passes.

- Native GITHUB_TOKEN cannot publish changes to .github/workflows. Default updater behavior preserves workflow bytes and records review_reason=workflow-permission with the full migration range, while ordinary untouched managed files update. --allow-workflow-updates is only for a maintainer publishing with the required workflows permission; it grants no permission itself. Do not replicate a broad personal token into fork secrets to evade this restriction. Public example managed and released consumer/database CI pass. Actual native Renovate creates the compatible 0.24.2 tag/lock PR and its four database-backed consumer checks pass.

- Normalize generated Core source archives with scripts/normalize-core-sdist.py and the immutable commit epoch before release. Setuptools retains gzip/tar build-host timestamps and owner metadata despite SOURCE_DATE_EPOCH. Preserve every package byte and executable bit while normalizing metadata; compare both wheel and archive rebuild hashes and test exact supplied artifacts. Never publish raw nonreproducible archives and then clobber them on retry.

- The manifest initially registered 69 tracked infrastructure files against 130b3eb; its current explicit scope is 76 paths, including required build/CI helpers absent at that baseline. Do not add ignored caches or private fixtures by walking the filesystem; use tracked files. An original standalone consumer generator copies only registered infrastructure, preflights unsafe paths/symlinks before destination creation and replaces module publishers with focused CI. A second repository must never publish the template registry tags. Local checks now support explicit dispatch for token-created PRs. The original public example passes verified-tag/frozen-lock consumer CI and the actual compatible-patch PR. Actual default-HEAD dispatch and unchanged repeat delivery pass after reviewed main promotion; no future timed cron event is claimed.

- Repository-only .agents/skills/c0-* route feature/Core/contribution/upgrade work and delegate native operations to installed NethServer skills. Preserve fork-only changes and unfinished drafts when isolating contributions. Independent original fixtures and a real C0 fork upgrade pass; the latter preserves runtime branding/docs/drafts and proves separate released/local Core installs. A real scoped contribution PR passes local/image/both-native CI and is closed unmerged after the controlled proof; final reviewed implementation is merged in PR 1. No skills ship in runtime images.

- Managed-file upgrades use scripts/sync-upstream.py and an explicit version-1 manifest, trusted GitHub origin, immutable baseline and per-file hash/mode. Preflight every path/blob before writes. Apply only untouched files; preserve customizations and record needs_review/review_from plus exact upstream diff commands. Never execute upstream code. Unregistered files require explicit registration. Retain the first unresolved comparison baseline in later proposals, even when a different file changes. Repeat delivery and unrelated upstream changes must not churn proposals. Native-token pushes suppress push builds; since June 2026 bot-created PR checks require workflow approval or explicit dispatch. Module image publication must also be dispatched before native acceptance. Actual untouched/conflict proposals, explicitly dispatched exact-head managed CI and unchanged repeat delivery pass in the public example.

- Core artifact publication is distinct from an NS8 module release: core-v<version> tags must match package metadata, checkout and verified source. Require current successful Debian/Rocky contexts and local checks for that exact commit; a previous commit or pending check cannot authorize publication. Build/test with read-only permissions and give contents write only to the artifact publisher. Published wheel/archive checksums must match; never clobber an existing version.

- Package metadata inputs must be copied into the container builder as well as available in the repository. Core now declares README/LICENSE, so copy them with pyproject.toml before uv sync. Actual first M13 image lacked Core's license despite the standalone wheel passing; runtime audit now requires exactly one declared GPL license in Core dist-info. Keep legal metadata while excluding instructions/tests/build tools.

- Core distribution must include its GPL license/readme and every migration, match Python/runtime metadata and install outside the checkout without the NS8 SDK/reference app. Test both actual wheel and source-archive installations, deterministic rebuild and repeated fresh PostgreSQL migration preserving knowledge-space identity. The initial packaging patch is 0.24.1 with schema 0013 unchanged; compatible fork range is >=0.24.1,<0.25.0. Do not claim artifact publication or automatic updates before execution. Keep source/package development tests out of runtime images.
- M13 native update tests freeze all three verified 3939575 module/app/database digests from PLAN. This is the fully accepted installed/live M12 predecessor; test-only 792 and documentation-marker tags are not substitutes. Native numbered lifecycle and private credential files remain unchanged.

## Established M12 UI conventions

- Actual Administration (131a53f), native Status (e72f4c9) and Wiki graph/draft (39aa4f7) UI slices pass both native distributions, all seven real Rocky browser workflows, exact recovery/observers and privacy audits. Sources and stronger timer recovery also pass, with permitted live owner acceptance at 3939575. The completion marker is verified; M13 is active. Use PLAN links and frozen M11 predecessors.

- A failed one-shot wake during intentional database restart/outage remains a legitimate failed service until the next timer run. Do not reset/mask this state to pass readiness. Disposable outage regression must force a real failed worker with PostgreSQL down, restore the DB and require a timer-driven completed success within 95 seconds before later deterministic job assertions. Keep exact due counts and both app/full-manager restart gates. No destructive outage fixture runs live.

- Sources citation selection has its own request generation, checked with document/page identity for both success and error. Clearing/changing document chunks invalidates citations. Query edits clear old source-search evidence and reject late errors as well as successes. Upload-source lookup checks the captured draft generation before filling title/provenance; busy uploads suppress duplicate submits. Keep existing immutable source/version/hash/offset/original and CSRF/role contracts.

- Wiki graph lists render bounded entity/edge/reference metadata through DOM text; retain raw JSON under explicit details. Entity navigation can add a current graph node beyond the initial picker window. Construct metadata links only from known local target routes and validated UUIDs; missing references retain snapshots without live links. Changing depth clears stale graph evidence; sequence both graph successes/errors. Same-page saves advance revisions while preserving newer text, fixed slugs and usable export/reload controls; new selections have independent save-button lifetimes. Relation/reference feedback must match the captured entity selection.

- Native RuntimeStatus uses Ns* cards and only focused get-runtime-status/get-authentication-status/get-scheduler-status actions. Runtime checks reuse Core database readiness and parsed retrieval flags, close the connection pool and never send inference data or expose provider descriptors/keys. Service activity is not database readiness; a normal idle one-shot worker is not an outage. Configuration does not prove provider connectivity/quality. Sequence refresh tasks, settle terminal callbacks once, remove paired listeners on every exit and use Vue 2 beforeDestroy (not beforeUnmount). Existing Status tasks also remove listeners and avoid dumping task payloads to the console.

- Application Administration reuses existing Admin/CSRF client/job/schedule REST. Never add NS8 actions, dynamic handlers or generative tasks to it. Client toggles capture expected revisions; uncertain unchanged job submissions retain their replay key. Use literal metadata, bounded lists, static transport errors and clear/hide private views on role loss. Sequence both successes/errors and detail reads; preserve newer form fields and schedule selections during writes. Navigation Admin links default hidden and appear only after verified current-role metadata. Native browser extends actual OAuth-role contexts with client disable, timer-completed health job and persisted paused schedule; private URLs/passwords keep their established direct Browser handling.

- Generic record fields use the actual bounded Core schema, DOM text, typed enum/const controls, explicit optional presence and nested/array JSON. Use own-property-safe copies/definitions for prototype-named fields; omitted differs from empty/false/null. Advanced JSON remains an explicit mode and server validation is authoritative. Visual saves collect current fields, preserve newer drafts/revisions, and selection changes re-enable their own save controls. Relation browsing is bounded/paginated and rejects stale type/record replies without replacing manual IDs; retain exact typed REST relations. Native tests open the JSON editor explicitly and exercise real scalar fields/target selection/Reader disabled controls.

- Application pages use packaged local app.css/navigation.js, common navigation and visible focus/skip links; preserve controller IDs and instance-prefix URLs. MCP copying uses canonical server metadata, captured clipboard values and a manual selection fallback. Home reports workspace availability; technical health/API remain in service details. Sharing/account/health refreshes reject older responses, capture role/CSRF before writes and preserve newer drafts after uncertain/earlier writes. Browser tests require actual current-page navigation, keyboard focus and copy controls; script tests deliberately reorder responses and refuse clipboard access.

- Failed admission renders a bounded generic 403 page with no-store/no-referrer, clears the one-use login binding and any earlier C0 browser session. Retry uses a validated same-origin/legacy-prefix link and explicit provider prompt=login without changing issuer/callback/S256/state/nonce bindings. It never admits a user or borrows token roles. Test fresh and pre-signed cookies through real signed HTTP, including state replay and stale-cookie rejection. A Git-only unadmitted disposable persona exercises actual provider account switching; passwords use direct private Browser fills and actual artifact/server-log privacy checks. Actual Keycloak prompt=login may retain the username on a password-only page: exercise its reset-login control before selecting the alternate user, and explain that provider step in the denied UI. Do not weaken reauthentication or change unrelated provider flows.
- M12 native tests retain all three verified aa26512 M11 digests for genuine upgrades. M13 freezes all three verified 3939575 M12 digests from PLAN. Read the updated MY frontend patterns, but keep existing static controllers, DOM text, draft/replay/generation guards and simple Reader/Editor/Admin roles. Native configuration remains numbered actions/private files and Ns* administration components. Interactive Playwright remains waived; both UIs retain real automated disposable browser assertions.

## Established M11 operation conventions

- Installed guard probes must use a valid MCP request and a successful positive control before negative checks. Unknown Host can be rejected by Traefik with HTTP 404 before the app; accept that only for Host, while Origin must fail on the canonical route. Local regression deliberately bypasses Origin and requires probe failure. Recovery uses a separate approved client descriptor so a failed earlier protocol probe cannot pollute exact one-grant/two-token seeding.

- Recovery fixtures seed real consented grants after retrieval setup, keep raw pairs and exact client-filtered PostgreSQL snapshots only in mode-0600 disposable state, and compare every grant/token/code row before authorization probes. Native update preserves refresh authority; clean restore changes the native client and rejects prior grants before fresh SSO/consent. Real consent browser checks Admin/Reader/Editor scope controls and literal hostile client names. Private authorization/callback URLs use direct Browser methods, never nested Robot arguments; audit actual reports and server logs afterward. These installed gates pass at 5bc2dca, with actual reports inspected.

- Disposable OAuth acceptance runs through actual native SSO and administrator-approved clients, explicit Origin/CSRF consent, S256/state/resource/code replay, refresh/replay and public revocation. Feed access tokens only on private stdin to the existing app container SDK client; never Robot variables/command arguments. Git-only TLS client routes only the synthetic application TCP destination to the disposable gateway while preserving original Host/SNI/resource and verifying the generated CA; provider DNS remains native. Check access-log privacy after the OAuth probe, not only beforehand. Test exact fixture code through signed local HTTP before native runs. Actual TLS/native protocol and exact active-grant recovery pass on both distributions at 5bc2dca.

- App OAuth uses official SDK AuthorizationHandler/TokenHandler/ClientAuthenticator/RevocationHandler around Core and existing verified NS8 SSO. Guard exact raw resource/callback and duplicate fields before SDK normalization/dispatch; sixteen KiB URL-encoded or consent JSON, including chunked requests. Public clients use method none; metadata advertises actual /oauth endpoints and no dynamic registration/CIMD/fetch. SDK revocation needs a narrow nullable-secret adapter. Keep all code/token/challenge representations masked. Consent stores its 43.43 request/binding only in secure HttpOnly Lax cookies and uses a static page URL, native login returns only to valid pending consent, and approval requires cookie identity plus Origin/CSRF and explicit scopes. Delegated REST uses explicit scopes, including read for profile/admin for membership; delegated logout cannot clear an ambient browser cookie. Host lifespan explicitly enters MCP child lifespan; mount only configured hostname-root apps. Local automatic SDK OAuth discovery/code/MCP passes; derive discovery availability and safe connection URLs from the actual configured hostname-root mount after verified protocol gates.

- OAuthConsentService/0013_oauth_consent stores only hashes of request/browser binding, pins client revision/native context/resource/exact callback, bounds state to 512 printable ASCII characters and pending requests to five minutes/1000 instance/32 client. Trusted completion requires a verified unexpired SessionContext after same-origin CSRF and explicit approval in the app. Lock role49372 -> grant49379 -> consent49380; consume pending state and create its code in one transaction. Failure rolls back consumption; concurrent completion has one winner. Reader consent can narrow requested scopes; denial consumes without issuing a code and does not require selected scopes. View DTO omits state/challenge/native identity/binding. Public HTTP uses the official SDK handlers around these services; installed protocol acceptance passes at 5bc2dca.

- Trusted authorization-adapter loaders return masked code/challenge/refresh metadata and recheck current native identity, client epoch, resource, role and expiry. A consumed refresh loader must commit family revocation before returning rejection, so SDK scope validation cannot short-circuit replay handling. Loaders remain private Python APIs; raw token-request resource/callback validation is still required before SDK dispatch. Public consent/token endpoints now use the SDK adapter; installed protocol acceptance passes at 5bc2dca.

- The SDK 2.3.0 transport factory reuses the trusted catalog and opaque Core grants, with current-token/membership/scope rechecks. It is mounted for configured hostname-root instances; derive availability from the real mount and expose safe matching OpenAPI/agent connection metadata. Enter its public router lifespan from the host. Use stateless JSON HTTP, exact host/origin/resource and same-origin /oauth issuer, one MiB request/eight MiB complete response/eight concurrent requests and no-store responses. Advertise supported scopes with the SDK metadata helper rather than globally requiring all scopes. Legacy MCP protocol accepts only object output schemas: omit nonobject schemas/structured output and preserve the exact JSON text (including null). Keep raw SDK token representations masked and database failures static. Current factory requires hostname-root configuration; legacy NS8-prefix REST is preserved. Disposable parity fixtures must delete their actor-owned pages/revisions/events/receipts, without changing other fixtures.

- OAuthGrantService/0012_oauth_grants backs the public authorization/token adapter. Consent adapters must supply a verified SessionContext after explicit CSRF-protected approval. Codes use S256 and exact callback/resource/client bindings; opaque codes/access/refresh tokens are hashed, with masked token-pair representations. Grant lifetime is bounded by the session and one hour; access/code lifetime by five minutes. Refresh narrows scopes durably, invalidates old access, retains consumed hashes for replay detection and revokes the family on replay or the 128-refresh limit. Client revision and native issuer/client/resource changes invalidate grants. Membership mutations delete grants atomically, including later regrant; issuance locks 49372 before grant lock 49379. Keep quotas at 1000 instance/32 account grants, collect expired/unredeemed codes and test actual concurrency. Bump the database schema health constant with migrations; a stale constant can corrupt an isolated fixture's compatibility-test reset.

- Disposable Browser 19.14.2 dumps response internals, including pending OAuth Location queries, at its default Pino INFO level. Set its supported ROBOT_FRAMEWORK_BROWSER_PINO_LOG_LEVEL to silent before its lazy Node subprocess starts; preserve Robot assertions and bounded Python diagnostics. Audit actual output.xml and playwright-log.txt for OAuth query parameters as well as temporary passwords/provider keys. Test-only sibling imports must resolve in both Robot and the runpy unit harness. Do not accept behavioral CI alone when artifact privacy fails.

- Trusted Core operation definitions contain bounded names/schemas, minimum roles, explicit c0:read/c0:write/c0:admin scopes and Python callbacks. Requests never register handlers or select imports. Registry discovery and invocation recheck persisted membership; scopes must be explicit validated sets for delegated clients, while None is reserved for verified first-party sessions/tokens. Domain services retain their transactional role checks.
- Typed application bindings reuse the same handler and DTO for REST/direct calls, preserving public aliases and UUID/time normalization. Keep FastAPI authentication/CSRF dependencies and current resource contracts. Non-Admin schema registration now fails 403 at the operation boundary before semantic validation; Admin invalid schemas still fail 422. Multipart upload and binary/Markdown attachment responses remain explicit REST interfaces. Do not expose arbitrary NS8 actions through the registry.
- /agents and its capability JSON use the same current-caller registry with no-store responses. Anonymous discovery lists no private operations; malformed credentials never become anonymous fallback. OpenAPI operation IDs and x-c0-operation metadata come from bindings. The first registry slice d9ede79 passes local/publication, both native distributions and permitted live owner update/full-manager restart acceptance. All roles/revocation and discovery persistence pass actual disposable SSO. Derive MCP availability from the actual configured hostname-root mount after verified installed/live gates. Freeze verified M10 runtime digests in predecessor tests.

- Public OAuth-client approval lives in Core/0011_oauth_clients, separate from native IdP registration. Admin-only typed REST binds to the operation registry. Keep exact ASCII HTTPS/loopback callbacks and known scope sets, reject credentials/query/fragment/wildcards, and never fetch callbacks. Identical descriptor fingerprints replay existing clients without reenabling disabled ones. Enable changes use expected revisions and advance the client revision; future grants must bind to it so reenabling cannot revive stale grants. Cap at sixty-four clients/four callbacks/three scopes and sixteen KiB JSON. Do not mistake public-client approval for a token grant or application membership.
- Freeze all verified M10 predecessors, and seed approved/disabled clients through signed REST. Verify exact metadata and active grant/code/token rows after update/clean restore, without private values in diagnostics. Client approval 00e8ff1 is the earlier accepted slice; current verified 5bc2dca Core/app/schema 0.23.0/0.28.0/0013 passes installed protocol/consent/recovery and permitted live owner full-manager restart acceptance. App 0.29.0 discovery closeout passes installed and permitted live acceptance at aa26512; freeze its three verified image digests for M12.

## Established M10 retrieval conventions

- A nonzero/minimum vector count does not prove complete indexing. Earlier role tests leave extra sources/pages; each batch prepares only two new Wiki revisions. Before immutable recovery snapshots, retain actual timer proof, complete all registered indexing jobs, validate every current source/Wiki chunk through PostgreSQL and pause refresh. Verify that pause survives update/restore and assert semantic-only revision citations. Snapshot diagnostics must contain only category/count/column names, never identifiers, text or vector values. Restore fixture schedule state after local tests.

- M10 actual disposable HTTPS/timer/index/vector-recovery and owner/Reader browser acceptance pass, plus permitted provider-free live update/full-manager restart persistence. Freeze the verified 80314c3 module/app/database digests from PLAN for M11. Keep operator details and private live fixtures outside Git. Document real-provider quality/calibration, automatic derivative compaction and 2000-dimension limits honestly; scan findings and stable IdP/proxy dependencies remain release work. M10 correction 5332017 passes local/publication and QEMU 38586575901: Debian fourteen passes/three expected skips, Rocky twenty-two passes including all five browsers. Completion 807ff59 local/publication/QEMU also passes; proceed with the active M11 subplan.

- Knowledge search UI uses local assets and DOM text, with sequence and captured-option checks for success/error responses; editing options invalidates old evidence. Preserve provider policy/fallback visibility. Disposable tests run a Git-only HTTPS provider outside runtime images, trust only a generated CA in app/worker and compare exact profiles/chunks/vectors across update/clean restore. Do not deploy these fixtures live. Benchmarks must show harmful as well as helpful mocks and distinguish citation presence from truth/answer quality.

- Native retrieval settings live only in mode-0600 state/retrieval.env as bounded base64 JSON, included in native backups and loaded by app and worker. Numbered validation stages private data before route mutation; atomic persistence follows successful identity registration. Endpoint changes clear saved provider keys unless explicitly replaced; blank keys preserve only the same endpoint. Public configuration exposes key-presence flags. Default/legacy initialization disables all providers. Core validates the same format and fails optional corrupt configuration closed while preserving text search; profile activation errors log only a fixed diagnostic. Configured native mock HTTPS inference and exact vector restore acceptance pass.

- Search uses bounded RRF over text and active-profile/generation vectors; aggregate Wiki chunks to immutable revision IDs before transport. Optional scorer validates all answers, reranks a bounded prefix or filters only evaluated candidates, and failures preserve ordinary ranking. Graphs are explicitly supplemental, unscored context from at most three roots/sixteen nodes each. Release search database connections before provider calls and recheck roles before returning; background indexing deliberately uses the supplied bounded worker transaction for rollback. Unknown overrides cannot enable disabled scoring or raise administrator caps. Explicitly type expanding UUID binds, including empty lists, to avoid PostgreSQL uuid/integer comparison errors.

- EmbeddingStore now maintains immutable endpoint/model/dimension profile IDs (credential rotation does not change them), exact derivative Wiki chunks and full-precision padded vector(2000) HNSW rows. Generation CAS hides old vectors during reindex without rewriting evidence/revisions. Private trusted handlers index at most eight inputs, use the supplied worker transaction and roll back derivative rows on provider failure. Profile activation changes the optional schedule only on a configuration transition; repeated startup preserves an explicit pause. Disabled embedding handlers remain registered as safe no-ops so a dormant schedule enabled by an Admin cannot block the worker. Native provider settings now load trusted clients into app and worker; configured installed acceptance passes. Defaults remain provider-free.

- Core provider adapters now validate float embeddings and the common Jev/Kev Noul contract with absolute async HTTP deadlines beneath synchronous services, bounded bodies and stream cleanup. No redirects/proxies/compressed responses; an explicit verifying SSL context preserves OS/operator CA trust (including SSL_CERT_FILE) independently of proxy environment handling. TLS stays enabled and keys have masked representations/static errors. Explicitly pin resolved Kev model IDs; latest aliases resolve to backend-specific names and must not silently change calibrated identity. Native configuration, profiles/vectors/background indexing and scoring are implemented locally; configured installed acceptance passes.

- Provider-free SearchService now searches source chunks and current nonarchived Wiki revisions through PostgreSQL FTS/GIN. Return exact bounded excerpt substrings/offsets and immutable evidence/revision IDs; do not use formatted HTML highlights as evidence offsets. Historical Wiki revisions stay readable but do not silently rank as current pages.
- Strict typed retrieval query options reject unknown provider URLs/credentials. Reader access is rechecked in Core. Semantic/hybrid requests without configured embeddings fall back to text with embeddings_not_configured. FTS must remain independent of derivative indexing jobs.
- Native predecessor fixtures freeze all three verified M09 digests. Extend exact real-SSO recovery with knowledge FTS and revision citations. Provider configuration/scoring must remain optional, bounded and separate from authorization.

## Established M09 Wiki/graph conventions

- Use the same PageView DTO for JSON export and page/mutation responses; untyped ISO UTC strings otherwise differ from typed timestamp normalization. Markdown export remains an attachment response. Assert complete JSON exports and exact native recovered revisions.
- Wiki mutations require bounded actor-scoped replay keys and expected revisions. REST uses the existing persisted roles, Origin/CSRF and a 1 MiB pre-parse body guard, including chunked requests. UI uses DOM text and generation guards for pages, revisions, entities and graph; preserve drafts on conflicts and newer selections after earlier saves. Retain the most recent uncertain write key for unchanged retries. Trusted page/entity/claim resolvers return bounded metadata, never complete authored bodies.
- Exercise the exact disposable Wiki seed/verifier through signed local REST before native runs. Seed revisions, aliases, two conflicting sourced claims, 1–3-hop relationships, all five reference kinds and metadata cursors; compare exact recovered data after update/clean restore. UI tests use generated private personas and direct password fills.

- KnowledgeService now adds immutable assertion values, mandatory real chunk evidence, annotations/retraction, bounded entity relations and typed links to pages/objects/sources/documents/chunks. Conflicting assertions coexist; evidence is never removed by annotation or retraction. Each entity has at most thirty-two active incident relations and thirty-two typed references; recursive traversal caps depth at three, uses per-depth deduplication and reports output truncation. Object deletion clears a real FK while retaining the stable reference ID/snapshot and an explicit missing marker; do not silently reinterpret it as another resource. Typed REST and a minimal Wiki UI now reuse this service; native/live M09 runtime acceptance passes.

- WikiService now implements versioned authored pages, Unicode NFKC/casefold aliases, entity CRUD/tombstones, Markdown/JSON export and metadata change cursors in Core. First/replayed/read results have consistent JSON-compatible UUID/time fields. Serialize knowledge mutations with transaction lock 49376 before event IDs; actor/key receipts store immutable snapshots and reject mismatched payloads. Recheck persisted Editor privileges before replay lookup. KnowledgeService adds claims/graph and the app adds typed REST/local UI.
- Authored Markdown caps at 128 KiB and metadata at 16 KiB. Receipts allow up to 1 MiB because valid control characters expand when JSON-escaped. Aliases are globally unique normalized names, at most sixteen per entity; rename retains old aliases and tombstones reserve them to avoid identity reassignment. Page archive creates an immutable revision preserving historical references.

- Reuse current persisted roles, immutable evidence IDs/citations and object revision/event patterns. Wiki/claims are authored data separate from raw extracted evidence; every claim requires durable provenance and conflicts coexist. Keep the graph in PostgreSQL with bounded depth/work/output and deterministic results. No per-document ACL, second graph service or generative scheduled/runtime handler.
- Define concurrency, replay keys, alias normalization, immutable revisions, deletion/reference policy and change cursor ordering in Core before REST/UI adapters. Extend existing native source/object backup/restore fixtures with actual Wiki data. Freeze all verified M08 module/app/database digests from PLAN.md for genuine update tests.

## Established M08 ingestion conventions

- python-docx omits text inside some content controls/revisions/fields/drawings. Reject unsupported structures in actual document/header/footer XML roots before accepting extraction; preserve originals. Preflight all XML/relationship parts with entity resolution/network fetching disabled, and reject DOCTYPE including UTF-16 encodings. Never classify partial visible text as complete.

- The Sources UI shares the existing cookie/CSRF contract and uses DOM text for all uploaded content/metadata. Guard list/history/document/search response generations and capture upload fields before awaits. Preserve newer selections/drafts after older uploads complete. Real disposable Browser tests use generated private personas and original Git-only format fixtures.
- Disposable SSO persistence seeds evidence through authenticated multipart REST, waits for actual timer extraction/cleanup, and compares complete texts/chunks/UUIDs/hashes/citations plus retained and quarantined binaries after update and clean restore. A read-only QEMU observer checks app/worker/timer quiescence while the native Restic container copies. Never run these destructive fixtures on live systems.

- Keep discovery-page assertions aligned with actual installed routes: require source FTS and its OpenAPI path while retaining explicit Wiki/hybrid/MCP limitations. Rerun public-page and Robot discovery assertions after capability text changes; a shared stale sentence can otherwise survive the local suite.

- Strip dependency-wheel extension build headers/Cython sources from the assembled virtualenv, while retaining runtime shared libraries, schemas and licenses. The image audit rejects these development suffixes as well as bundled tests/skills.

- Core SourceService now provides immutable versions, retained full text/chunks, citations, FTS, original storage and trusted extraction/cleanup handlers. Typed REST reuses it. Local PostgreSQL and signed HTTP pass; source UI has local assets and real-script race coverage; native, permitted live and repeatable browser acceptance pass; interactive Playwright remains waived. Child parser limits fail with bounded codes; never echo document bytes, filesystem paths or library exception text. Preserve all extracted text and reject over-limit/incomplete files. Pin parser versions; test original corpus formats and unsafe/archive/timeout cases before adapters.
- Initial uploads deduplicate matching content/title/metadata/media through an indexed ingest key; explicit existing-source uploads serialize on its row and expected revision. Different provenance remains separate. Source title/provenance is established by its first upload; explicit existing-source uploads retain it. Version content/retention is immutable; retry uses expected generation. Source deletion is a tombstone, excluding browse/search while retaining evidence and citations. Trusted source/document/chunk resolvers return bounded metadata, never original paths.
- Bound multipart bytes before file spooling, including chunked requests. Keep the guard inside the existing response-header middleware so its bounded abort is handled before crossing task groups. Verify HTTP 413 and temporary-file closure. Failed or explicitly retained originals download as attachments/octet-stream, never executable inline content. An uncertain database COMMIT leaves the generated original for operator recovery rather than risking evidence loss.

- Keep uploaded originals on the existing restricted source volume using generated IDs. Delete only after extracted full text/chunks/status have committed successfully; queue idempotent post-persistence cleanup. Failed or incomplete extraction retains its original and an actionable state.
- Native backups must quiesce foreground file writers and workers across both SQL archive preparation and Restic copy, preserving prior app/timer states. Do not introduce a custom NS8 management daemon. Isolate untrusted parsers with bounded CPU/memory/time; never execute document instructions, macros, embedded scripts or external links.
- Freeze verified M07 fixed-timer module/component digests in PLAN.md for genuine upgrade tests. Evidence offsets are defined against the retained extracted text, with immutable source/version identities and location metadata; optional source/Wiki reference adapters use trusted Core registration.

## Established M07 object contracts

- Core ObjectService now implements immutable type definitions, bounded Draft 2020-12 schemas, JSONB CRUD, tags, optimistic revisions, scalar uniqueness, atomic batches and object-to-object typed relations. REST and the minimal separate record editor reuse these operations and pass signed HTTP, real disposable SSO/browser and permitted live owner CRUD/restart persistence checks. Serialize object mutations with transaction lock 49375 before allocating event IDs so change cursors preserve commit order. Deleting an object cascades its relations; its delete event tells consumers to discard those edges.
- Define the bounded JSON Schema and atomic revision/uniqueness/batch contracts in Core; REST and the separate app UI reuse them. Recheck persisted roles inside transactions. Do not borrow multi-organization ACLs from upstream CRM examples. Object schemas/records and typed relation endpoints are data, never imports or schema-fetch URLs.
- Core node restart-module restarts the entire rootless user manager; an app-only systemctl restart does not cover that path. Preserve a native manager restart assertion for scheduler startup, and use bounded timer state/result/dependency diagnostics when investigating.
- Freeze verified M06 module and component digests from PLAN.md for genuine upgrade tests. Extend encrypted backup/restore with actual objects/relations/events; no new native management abstraction is required.

- Object transport must preserve PermissionDenied as 403 before catching ValueError. Typed reference resolution accepts only trusted registered callbacks; they receive the transaction/current actor/UUID, enforce domain roles and return bounded data. Current stored relations retain object foreign keys; sources/Wiki adapters arrive with their real tables.
- Record-list refreshes must ignore stale response generations before rendering; clear after the accepted reply, not only before await. Dependency-free Node tests execute the real script with out-of-order responses, alongside strict real browser assertions. Record UI uses local assets, associated labels, role-gated controls and DOM text for record/schema content. Keep draft edits on conflicts; loading the saved revision is explicit. Disposable end-user SSO passwords follow the direct Browser fill/private-artifact convention; never route them through Robot keyword arguments.

## Established M06 queue/worker contracts

- Materialize the selected bounded cleanup batch before DELETE USING for sessions, login states and old jobs; locking limited subqueries must not depend on planner re-evaluation. Preserve the 1000-row cap and verify exact remaining counts under default and forced nested planner settings.

- Core handler registration is trusted Python code with validated names, callable validators, retry/deadline caps and bounded canonical JSON. Request handler names never become imports, SQL or shell. Public JobService calls recheck persisted Admin membership in their transaction; worker-only methods remain private.
- Queue idempotency fingerprints include handler and normalized payload. Conflicts fail atomically. Schedules use UTC fixed intervals and unique schedule/due records; missed intervals coalesce to one job. Seed health/hourly and bounded maintenance/weekly in migrations. Standalone Worker/REST now use these services; native timer and backup pause/resume pass disposable checks; permitted live timer/API/restart persistence also passes.

- Worker execution is standalone POSIX main-thread code with session lock 49374, committed attempt claims, transactionally committed effects/completion and bounded retry/recovery. Handlers must use the supplied transaction and make external/file effects idempotent. Python deadlines require bounded I/O; the native container guard handles non-interruptible extension code. A failure after successful COMMIT must never requeue committed effects.
- `app.job_handlers.build_registry` is the trusted shared API/worker extension point. Reuse auth read/write dependencies, CSRF/Origin and Core services for all job routes. Never execute jobs inside HTTP requests or log payload/result/exception text.

- An app-ordered timer must disable default timer boot-target dependencies to avoid the timers.target/basic.target/app cycle; explicitly restore shutdown conflict/ordering and keep PartOf/Requisite/After app bindings. Verify both app restart and native user-manager restart; inspect actual journals for dropped ordering jobs.
- One native timer wakes a dedicated one-shot container from the app image/private pod. Requisite/PartOf/ordering ties it to the app without cold bootstrap; enable under the app target. Idle one-shot services are expected, not an app outage; inspect get-scheduler-status for timer/running/failure flags. Native container lifetime is bounded at 150 seconds.
- Backup stops timer and worker before dump and retains the pause through Restic copy. A private transient resume flag stays outside backup includes; cleanup resumes prior active timer state, and dump failure restores it immediately. Restore accepts older format-1 archives and preserves an explicitly paused scheduler. M08 additionally stops the foreground app across dump/copy and restores prior app/timer activity; native copy-window and retained/quarantined evidence restore checks pass.

## Established M05 identity conventions

- Use explicit slirp host-loopback networking for the private pod, following maintained NS8 consumer modules. After successful native registration, persist a gateway host argument only when the selected provider is on this node; validate the issuer hostname and preserve HTTPS/SNI/trust checks. Remote providers retain ordinary DNS. Configure/update must list pod, database and app together; use try-restart on update to keep cold instances stopped. Disposable SSO adds only its test CA, never a DNS override that could conceal broken native routing.

- Native authentication diagnostics execute the shared bounded OIDC health check inside the existing app container, using its private environment and trust store. Unwrap transport causes to distinguish DNS, refused and unreachable connections. Emit only validated status/reason JSON; never return exception strings, issuer URLs or secrets. Reject malformed bearer envelopes before key discovery, then delegate all cryptographic verification to JOSE.

- Core clean restore may preserve the logical MODULE_UUID/backup path while allocating a new module ID. Keep the existing backup repository encryption key when backing up that restored logical instance; repository deletion does not delete its encrypted storage.

- Native update/systemd completion precedes ASGI readiness. After test-only pod/network recreation, poll bounded application health before a real identity probe; never replace this with a blind delay or treat a started workflow as a pass.

- Robot log level NONE suppresses messages but retains nested keyword arguments. Never pass credentials through `BuiltIn.run_keyword`; call the public Browser fill method directly for plain strings and use Robot conversion only for non-sensitive typed arguments. Send native cluster-user/hash setup through private stdin files and assert the generated password is absent from actual output XML/Playwright logs.

- Czero query redaction does not cover Core Traefik access logs. Disposable SSO fixtures suppress the proxy access log before authentication and assert no OAuth query values; production proxy logging needs a separate platform contract review. Never publish raw OAuth query diagnostics.

- Rootless Podman test bind sources must belong to the module account before `:z` labeling on SELinux hosts. Public test CA files use mode 0644; private test CA keys remain outside Czero containers. Never disable SELinux or TLS verification to make a fixture pass.

- Provider test forms may have relative actions. Resolve them against the final provider page URL, including logout confirmation; never against the Czero origin.

- Identity restore tests must create grants through authenticated Core-backed REST and verify signed logins after a new native module/client identity. Expected test account IDs may stay in private disposable fixtures; do not fake memberships with SQL or Redis.

- Disposable SSO credentials are generated inside the Python Robot helper, uploaded with mode 0600 and never returned as Robot variables or placed in command arguments. Test-only CA/DNS/systemd overrides belong in disposable QEMU fixtures, never runtime actions or images. Keep provider and application TLS verification enabled.

- SDK `agent.run_helper` forwards options to `subprocess.Popen`; supply JSON through a rewound temporary file with `stdin=`, never `input=`. Restore/upgrade regressions enforce this actual SDK contract.

- Core `identity` verifies NS8 RS256 tokens against caller-supplied trusted keys, exact issuer/audience and required/time claims. Access tokens require Keycloak's `Bearer` type; ID tokens require login nonce and authorized party/hash bindings where applicable. Reject header-supplied key URLs and algorithm confusion. The JOSE library implements signatures; Core never implements cryptography or emits token values in errors.
- Verified identity uses issuer plus normalized signed LDAP UUID, and contains no role authority. `Actor.require` has only Reader/Editor/Admin thresholds. Create admitted actors only from the shared membership service; never from request bodies or token role claims. Core `AccessService` now persists verified profiles and roles, and rechecks roles inside privileged operations. Ownership uses a configured LDAP UUID, never username equality. Core `SessionService` now stores one-use browser-bound state and opaque expiring sessions, scopes them to issuer/client, and rechecks membership. `OidcClient` uses Authlib for code/S256 PKCE exchange and JOSE token verification, bounded discovery/JWKS, exact callback/logout URLs and same-origin metadata. Keep TLS verification enabled; suppress OAuth query/secret logging when transport is wired. FastAPI now wires login/callback/logout, bearer/cookie identity and member-role endpoints into these services. Native numbered steps validate owner/provider/domain, bind one domain and register the client into mode-0600 auth.env. Native update/restore and selected service/domain events reconcile registration; old M04 instances stay unauthenticated until configured. Real NS8 SSO now passes both disposable distributions; configured update and clean restore preserve admitted account IDs and grants on both disposable distributions.
- M05 Core/app versions were 0.6.2/0.7.2 with `0003_sessions`. The verified M08 Core/app versions were 0.11.1/0.13.1 with `0006_sources`; verified M09 was 0.13.1/0.16.1 with `0008_knowledge_graph`; current M10 is 0.19.0/0.22.0 with `0010_embeddings`. Role mutations use advisory transaction lock 49372, bounded login-state allocation uses 49373, and migration lock remains 49371. Keep public health/landing and identity behavior honest about the implemented interfaces. Freeze M05 module/component digests for M06 predecessor tests.

- OAuth query strings are stripped from Uvicorn access logs; token-bearing test fixtures suppress their representations. Cookie writes require CSRF and the configured Origin. Invalid bearer headers never fall back to a valid cookie. Keep 401/403 errors distinct from resource/limit ValueErrors. Local session logout completes during provider outage; provider-wide logout then remains unavailable. OpenAPI declares bearer/cookie alternatives. Use DOM text nodes for all identity/profile data.

- Native owner validation uses `Ldapclient.get_user_entry` with `entryUUID`/`objectGUID` and preserves an unchanged owner key, even if its name is reused. Provider UUID selection uses current SDK discovery. Requests for credentials come from the calling module, with self audience and exact HTTPS callback/logout URIs. Client secrets go only to restricted `auth.env`, declared in backup includes and loaded into the app. Restore re-registers the new module client instead of relying on a restored old client secret. The app backend never imports the NS8 agent SDK.
- UI domain/provider pickers use NsComboBox (options have name/label/value); preserve task-listener cleanup for options as well as configure/get. Native identity fields remain optional for hostname-only compatibility. Missing/partial identity input fails validation before route changes. SDK registration failures keep the previous secret file and surface actionable errors; cross-module registration/binding is not a distributed transaction.

## Established M04 backup/restore conventions

- Native dump/cleanup hooks prepare a mode-0600 custom PostgreSQL archive and backup format/service-state metadata. Restic includes these, `passwords.env` and `czero-sources`; never include live PostgreSQL files. Dumping a cold DB preserves prior database/pod state and does not start an unconfigured app.
- Restore extends Core with numbered settings, validation, offline database, route and service steps. Keep new Core node/port/image identity; restore only C0 settings. Fail on invalid formats/archives and use `pg_restore --single-transaction --exit-on-error`. Receipts prevent overwriting initialized data on repeated delivery of an already completed archive.
- The retained-source volume now stores actual ingestion originals; immutable PostgreSQL text/chunks/citations and original flags survive native update/clean restore. Pause foreground app writers and workers across dump/copy. M04 controlled fixtures remain regression coverage.
- Disposable backup setup captures Core's generated encryption password with Robot logging disabled and returns only identifiers. Genuine upgrade tests pin both predecessor module and component digests, not mutable tags. Bound backup/restore SSH reads and emit static phase markers so native stalls yield diagnostics. Require actual snapshots before donor removal; native repeated-delivery tests preserve post-restore database changes and verify restored credential modes. All destructive backup/restore cases remain QEMU-only.

## Established M03 database conventions

- Keep PostgreSQL and app in a native private pod; publish only the allocated app port on loopback. `czero.service` remains the app identity; pod and database are ordered dependencies. Active children use `PartOf` for pod restart propagation; retain a pod-recreation persistence test. Selected PostgreSQL supports notify and its entrypoint suppresses temporary-server notifications. Actual notify/startup, pod restart and database outage behavior pass QEMU.
- Credentials are generated once with native atomic safe I/O into mode-0600 `state/passwords.env`, loaded by Podman env-file. Create/update invoke the same focused helper; never export credentials through `agent.set_env` or action stdout. Do not rotate initialized database passwords during configure.
- Core owns packaged Alembic migrations and database operations. NS8 invokes the Core migration CLI before app startup. Migrations hold a PostgreSQL transaction/advisory lock and retain the knowledge-space identity across repeat runs. No NS8 lifecycle manager belongs in Core.
- Health reports safe database status/schema/vector versions and returns 503 on unavailability. Driver exceptions and connection URLs never enter responses. Application health SQL runs in FastAPI's sync worker pool.
- Keep upstream PGXS/compilers and all repository tests/configuration out of runtime images. PostgreSQL logical backup/restore passes native Debian/Rocky acceptance in M04.

## Established M02 configuration conventions

- Keep configure steps focused: `10validate` checks native route ownership; `20configure-route` delegates TLS and explicitly clears legacy `path` with `null`; `40persist` writes only non-secrets after route acceptance; `80start_services` restarts; `90wait-ready` bounds local health checks. Do not hide native route/certificate failures.
- Action schema regex patterns must compile with Core's Go/RE2 validator as well as Python tests. Avoid lookaheads; `tests/check_schemas.go` gates compatibility in CI. Robot curl format placeholders must escape `%{...}`. Native update completion precedes ASGI readiness; poll health in integration tests.
- Persist hostname lowercase and certificate flags as `true`/`false`. An explicitly empty `CZERO_BASE_PATH` means hostname-root routing. Update hooks initialize a missing key to the legacy instance prefix, never overwrite a configured empty key.
- Track admin task listeners, including repeated progress events, and remove them on every terminal result, task creation failure and Vue destruction. Field errors use native validation parameters. Only English translation source is edited.
- Synthetic `.test` hosts and certificate exceptions belong only to disposable QEMU tests. Live tests are authorized only for the dedicated Czero instance; interactive Playwright remains suspended.

## Established M01 conventions

- `packages/czero-core` contains reusable runtime operations and an independent version; `app` owns FastAPI transport, route composition and the separate static application UI. The initial M01 versions were `0.1.0`; current Core/app versions are documented in README. Core is a local package dependency until M13 distribution work.
- NS8 still owns lifecycle through short numbered scripts. Core injects `CZERO_APP_IMAGE` from the module dependency-image label; `configure-module/20configure` persists only the non-secret `CZERO_MODULE_ID`. The app validates that identity and mounts at `/czero/<module-id>` because the NS8 route preserves its prefix.
- Application routes currently provide a landing page, `/api/v1/health`, `/openapi.json`, `/docs` and an honest `/agents` introduction. M01 had no authentication or persistence; M03 adds dedicated PostgreSQL and M04 adds native backups. M05 adds native identity authentication. Keep the application UI separate from the compiled NS8 Vue administration UI.
- `app/uv.lock` locks runtime dependencies. Build non-editable packages into `/opt/czero/.venv` in both container stages: generated console-script interpreter paths must not change when the virtualenv is copied. The final stage runs as UID 10001 and removes base-image package installers; copy only the virtualenv and static runtime files.
- Audit installed dependency wheels too: FastAPI currently bundles `.agents` authoring skills, which the builder removes. The publisher runs `tests/audit_runtime.py` against the assembled image through stdin before publication; this repository-only check rejects development files and installed build/test tools.
- The inherited Core `get-status` action expects no input (`null`), so omit `data` in its UI/API task payload. Sending `{}` fails Core input validation. Czero configuration accepts a required DNS `host` and optional boolean `lets_encrypt`.
- The service unit uses `%N`, so the Podman container is named `czero`, not `czero.service`. Check request logs with that container name. Uvicorn access logs are enabled; Robot verifies a real health request appears in the logs.
- Run pytest across `app/tests`, `packages/czero-core/tests` and `tests/unit`. QEMU verifies mounted application routes, configuration/rejection, logs, restart, forced native update and disposable uninstall, with admin and end-user browser assertions. A same-image forced update does not prove a future database migration.
- Core reloads units and image environment during update but delegates service restart to hooks. `update-module.d/20instance-id` reconciles the non-secret ID missing from M00, then `80restart` uses native `try-restart` so running containers are replaced and unconfigured instances remain stopped.

## Established M00 conventions

- Module image: `ghcr.io/stell0/czero`; lifecycle service: `czero.service`. M02 registers an instance-owned hostname route with HTTPS redirection; existing M01 prefix routes are preserved until hostname configuration. M01 adds FastAPI and the separate application UI; M05 adds native OIDC authentication.
- Module images carry OCI source, revision, license and product title labels. Source labels preserve repository attribution; existing package Actions permissions may still need a one-time operator repair.
- `build-images.sh` packages only `imageroot/` and generated `ui/dist/` into the NS8 module image. Preserve this explicit runtime allowlist. M01 replaces the pinned M00 echo stub with the separately built `czero-app` component image.
- Publication needs both `contents: read` and `packages: write`. The upstream reusable publisher explicitly removes checkout access; the small local job was adapted from its steps while the repository was private and is retained after the repository became public. QEMU runs only after successful publication and checks install and forced native update scenarios; M00 has no older released predecessor. UI tests run every time. A green wrapper with skipped tests is not evidence.
- Publication inspects image metadata with GHCR authentication and fails on pull errors. Trivy scans sources and runtime images and stores SARIF/CycloneDX artifacts; optional GitHub Security ingestion is not configured in these workflows. Both repository and package are now public; anonymous manifest access has been verified. Package Actions Write access is separate from public read access and must survive repository reconnection. Earlier QEMU legs failed before VM boot; corrected Debian 13/update and Rocky 9/install/browser suites now pass. Existing scan findings in UI dependencies and the echo stub are recorded in PLAN.md and must be reviewed before release.
- Publish module images with the native `GITHUB_TOKEN` and explicit `contents: read`/`packages: write`. The existing package must grant this repository Actions Write access. `NS8_MODULE_RELEASES_TOKEN` is for future GitHub release automation, not this publisher; leave the operator-created secret untouched. Private source checkout works with the contents permission. Private packages need authenticated QEMU/guest pulls in addition; current upstream QEMU pulls anonymously. A successful owner-token push does not prove repository Actions Write access.
- Live installation/configuration/restart/HTTP checks pass on Core 3.21.0/Rocky 9.8 using native authenticated tasks and Playwright MCP. No SSH is assumed. Core inventory misparses digest-only URLs via a colon split; prefer verified version tags and compare actual digests. Normalize unordered flags when comparing inventories. Live System logs showed no Czero entries; do not claim log visibility verified.
- The operator resolved live browser trust; Playwright admin login succeeds with normal certificate validation. Earlier exception attempts were rejected and were not bypassed. Ignore `.playwright-mcp/` artifacts and keep private browser evidence in restricted temporary storage. Do not commit hostnames, auth state or credentials.
- Core `add-module` prints a Python dictionary; `api-cli` prints JSON. `tests/CzeroActions.py` safely accepts either output form with literal parsing and checks Czero identity. Never use unrestricted `eval` on command output.
- Browser smoke checks must assert an actual state transition: in disposable QEMU, stop only Czero and verify that Settings Save restores the HTTP route. Use substring selectors for the longer honest-stub paragraph.
- Non-sensitive typed Browser calls inside Python Robot helpers use `BuiltIn.run_keyword` so enum/timeout arguments receive normal conversion. Sensitive plain-string fills use the public library method directly to avoid nested keyword arguments. Await a positive authenticated heading; `#main-content` alone may also exist on login. The authorized live test platform reported Core 3.21.0 through advertised read-only facts.
- `tests/CzeroBrowser.py` creates a random administrator only on disposable QEMU and suppresses password-entry logging. Never use this helper on a shared/live host. Local action tests live in `tests/unit/`; Robot tests remain in `tests/czero.robot`.

## Mission and boundaries

C0 is a deployable NS8 web application plus a forkable, AI-first development foundation. A vanilla installation must eventually provide a browser UI, FastAPI REST endpoints, PostgreSQL + pgvector, reusable generic-object and LLM Wiki storage, text and optional semantic/graph retrieval, an authenticated remote MCP endpoint, a self-describing `/agents` page, and deterministic jobs/scheduled maintenance.

- **Single C0 instance = dedicated PostgreSQL instance and shared knowledge space.** Initial access: one owner; optional application-wide Reader, Editor, Admin roles. No document ACLs, UGO, policy engine or multi-tenancy.
- No built-in generative LLM, autonomous wiki agent, research orchestrator, or AI cron. External harnesses handle reasoning, wiki synthesis and research.
- Only optional outbound AI requests: embedding generation and System One relevance scoring (**Jev and Kev**). If unavailable, text search still works; System One failure falls back to normal ranking.
- Deterministic parsing, indexing, CRUD, relationships, backup, health tasks and job processing do belong in C0.
- Source originals are **deleted by default only after successful extraction/persistence**; retain complete extracted text, offsets, citations, revisions and metadata. Optional original retention uses an NS8-backed volume.
- Development instructions, skills, CI files and tests belong **only in Git**. Do not bake `AGENTS.md`, `PLAN.md`, `.agents/`, `.github/`, tests, credentials or development tools into runtime images.
- All documentation must match actual behavior. Never state that a feature works merely because there is scaffolding.

## Source hierarchy: reuse before implementing

1. Inspect current local code and the target NS8 platform version.
2. Consult the official [NS8 Core developer manual](https://github.com/NethServer/ns8-core/tree/main/docs/modules) and the maintained [NethServer agent skills](https://github.com/NethServer/agents/tree/main/skills/nethserver-ns8-module).
3. Inspect maintained, task-specific implementations linked in the current milestone of [PLAN.md](PLAN.md): [ns8-kickstart](https://github.com/NethServer/ns8-kickstart), [ns8-hermes-agent](https://github.com/NethServer/ns8-hermes-agent), [ns8-dependencytrack](https://github.com/NethServer/ns8-dependencytrack), [ns8-idp](https://github.com/NethServer/ns8-idp), [ns8-mail](https://github.com/NethServer/ns8-mail), and [ns8-github-actions](https://github.com/NethServer/ns8-github-actions).
4. When alternatives disagree, prefer current documented Core contracts, then the newer maintained implementation with passing tests. Check its actual files rather than copying a README example blindly. Preserve license headers and attribution; this repository currently carries GPL-3.0.
5. If no matching NS8 pattern exists, search current NethServer/Nethesis module code by operation, identify why no reusable solution fits, and implement the smallest C0-specific component.

Recommended installed development skills: `nethserver-ns8-module`, `nethserver-admin`, `nethserver-containerfile`, `nethserver-pr`, `nethserver-release`, `conventional-commit` (all from [NethServer/agents](https://github.com/NethServer/agents)). C0-specific skills may be added later, but must delegate NS8 rules instead of duplicating them.

## Keep NS8 actions readable

**Do not build a monolithic Python manager for NS8 lifecycle.** Use NS8's action/step convention:

- `imageroot/actions/<action-name>/10validate`, `20persist`, `40configure-service`, etc.; one focused executable per meaningful step, ordered lexicographically.
- Reuse inherited Core actions; add only missing steps. User-facing actions have `validate-input.json` and `validate-output.json` where applicable.
- Read JSON from stdin. Write only machine-readable JSON to stdout for actions returning data. Send diagnostics to stderr/journald. Nonzero step exit stops the action.
- Use `import agent` helpers: `set_env` for **non-secrets**, `bind_user_domains`, `set_route`, `run_helper` and `agent.tasks.run` as appropriate. Prefer platform conventions over direct Redis/Podman hacks.
- Never write secrets with `agent.set_env`; its environment reaches Redis. Keep credentials in restricted `state` secret files, backed up through native NS8 mechanisms and loaded by systemd/container env-file. Do not log credentials.
- NS8 module owns systemd, Podman, Traefik, lifecycle, backup, restore and service configuration. The **application backend** owns FastAPI, shared operation/services, domain validation, PostgreSQL queries, REST/MCP, retrieval and jobs. Avoid duplicate business logic across interfaces.
- Keep the cluster-administration UI (existing NS8 Vue 2 + ns8-ui-lib convention) distinct from the C0 end-user application UI. No custom NS8 control plane.

## Runtime design invariants

- One versioned Python **C0 Core** package for reusable runtime operations, with stable public interfaces; applications extend it. C0 Core is not a replacement for small NS8 action scripts.
- Generic objects (JSONB + schemas) complement dedicated relational tables; typed references connect objects, knowledge pages and sources. Use database transactions and migrations.
- Knowledge storage preserves raw extracted evidence separately from AI-produced claims; provenance and revisions must survive reindexing and restore.
- Full-text PostgreSQL search is always usable. Semantic/hybrid search needs optional compatible embedding configuration. Jev/Kev provide optional relevance scoring, never access-control decisions; bound inputs and timeouts, disclose fallbacks.
- Treat uploaded documents, page contents and retrieved material as untrusted data; never interpret them as executable or developer instructions. REST and MCP use the same service methods and authorization.
- Only registered, trusted deterministic handlers may run from scheduled tasks; no arbitrary SQL or shell-command execution exposed via user REST/MCP tools.
- Configuration hierarchy: built-in safe defaults -> NS8 admin-managed instance config -> validated, bounded request-time overrides. External provider secrets cannot be overwritten per request.

## Mandatory milestone loop

Work through [PLAN.md](PLAN.md) **one milestone at a time**, in order; never skip a red prerequisite. Every milestone contains upstream implementation links or explicit code-search instructions and acceptance criteria.

1. Inspect the worktree, current milestone, platform/source references, and actual CI status. Make a small **implementation subplan in PLAN.md** for the active milestone, with tests and anticipated docs; don't make speculative architecture expansions.
2. Implement vertical slices with focused tests. Commit and **push each meaningful working increment** using the conventional-commit skill. Build/publish images in CI starting at M00; don't postpone CI until the end of the roadmap.
3. For each push, inspect the relevant GitHub Actions image build, QEMU/Robot integration tests and logs. If red, diagnose, fix, commit and push; rerun until green or document a genuine blocker. Never mark a test passing without evidence.
4. When a user-facing NS8/admin or application UI changes, test interactively using **Playwright MCP**: navigate, log in as the appropriate permitted test persona, inspect accessibility snapshots, exercise the workflow and assert actual state. Also add repeatable browser/Robot tests to CI where appropriate. Test **both** NS8 administration UI and the C0 user interface when present.
5. Once a bootable C0 image exists and CI passes, validate on an explicitly authorized live NS8 test instance with the execution-time access details provided by the operator; deploy only the C0 module, do not alter unrelated modules, and protect existing data. Do not assume SSH exists just because the web UI exists. If a capability is unavailable, record the gap instead of claiming a pass.
6. **At every milestone, update AGENTS.md (technical/agent instructions), README.md (human-facing current features, usage, limitations), and PLAN.md (milestone results, evidence and next step).** Commit/push these updates; watch the resulting CI as appropriate.
7. Mark a milestone `[x]` only when its acceptance criteria and mandatory evidence are satisfied. Record commit SHAs, CI run links, test results and any remaining nonblocking limitations in its `Evidence` paragraph. Move to the next milestone only then.

The template's hard-coded Robot login credentials have been removed. Use disposable random test identities or execution-time configuration. **Never commit real live hostnames, usernames/passwords, tokens, cookies, auth state, screenshots containing secrets, or private test-server details.** Pass live access details only in the operator's execution prompt/session; mask them in logs, reports, PRs and traces.

## Definition of done for any change

Code, data migrations, REST/MCP schema, end-user/admin UI, tests, backup implications and docs must be considered together. Before declaring completion: inspect diff, run relevant local tests, push, verify CI, run QEMU/live/browser checks when applicable, and reconcile `AGENTS.md`, `README.md` and `PLAN.md`. Document blockers precisely; do not substitute fabricated output.

**Start at [PLAN.md — M00](PLAN.md) unless a milestone has already been recorded as complete with evidence.**


## Completed structured-object repair

The operator's M1/M2/M3 repair is completed and deployed; its evidence remains separate from the subsequent M16 operator acceptance above. The M16 draft is reconciled in PLAN; M17 is next after closeout-marker verification. Core already requires unique string properties to declare maxLength <=128; omitted maxLength uses the ordinary 8192 default and fails with unique_string_too_long. Object REST and MCP adapters now preserve that reason using object_errors.py; schema and unique_fields metadata explain the explicit bound. Only allowlisted literal codes and bounded record paths/keywords may be exposed, plus object_not_found/object_conflict with their expected statuses. MCP uses c0/error metadata; unknown/private detail remains generic. Keep unrelated operation errors and OAuth scope/role challenges unchanged. M2 a36d501 is accepted on main and the dedicated instance: all 786 database/packaging cases, 106 scripts and exact producer/released-Core/native checks pass; actual deployed connector rejection/create/get/list and preservation/privacy checks pass. M3 complete typed CRUD and authorization now pass through REST/current/legacy, genuine installed TLS and actual connected tool calls; see the accepted runtime evidence below. Freeze all three genuine deployed 9582568 digests from PLAN together; keep immutable empty regression types and audit events, remove only their test objects. Keep uniqueness, Admin/c0:admin type creation, Editor/c0:write records, schema subset, limits and immutable types unchanged. Surface only fixed public domain codes and safe record path/keyword errors, with generic fallbacks for unexpected internals. Test the reported failure and explicit bounded positive controls before code. M1 intentionally reproduces red assertions and must never be deployed; M2/M3 require passing source and genuine native/deployed MCP evidence. Use isolated runtime-generated names only; preserve all pilot data and prior fixtures. Do not invent native sessions or extract stored authority to bypass OAuth. The authorized connector is now available for actual deployed MCP calls.

M3 regression fixtures must start each MCP session manager only once; seed role fixtures through REST before entering the single SDK lifespan. Track and remove only generated disposable type/event rows locally; genuine native probes leave immutable empty types in the disposable installation. The full-scope Admin consent fixture must report two completed typed lifecycles, one per protocol mode; do not infer CRUD coverage from a generic read-only SDK success marker.

Do not rely on the Rocky-only UI fixture for native typed MCP CRUD. The non-browser real-SSO probe must separately consent to canonical c0:admin/c0:read/c0:write and run both full lifecycles on Debian and Rocky, while retaining its original narrow grants and refresh-escalation denial.

## Structured-object repair accepted runtime

M1/M2/M3 repair acceptance passes at deployed source `95825682e00246556f7d0c7314859a6a69e0074b`: 812 actual Python/PostgreSQL/packaging cases, 106 scripts, schema/shell checks, nineteen Robot dry-run cases, exact producer/released-Core checks and both native distributions, including complete typed MCP CRUD in both protocol modes after real explicit Admin consent. Branch and main native artifacts/checkouts were actually audited; all seven browser/privacy workflows and three-artifact OAuth query audits pass. Main publication and supported targeted C0 deployment match all three immutable digests in PLAN. Actual connected MCP creation/discovery/validated CRUD, unique/type/stale conflicts, precise validation errors and delete/absence pass, with independent preservation and journal checks. Existing pilot data and fixtures are unchanged; normal last_seen login bookkeeping is excluded only from the post-MCP observer. Two owned empty immutable regression types and M3's three audit events remain; no regression records remain. No temporary live client was registered. M3 does not itself establish separately operated ChatGPT UI prompts; subsequent M16 operator functional/live OAuth acceptance is recorded above.

Keep Core unique strings explicitly bounded at maxLength <=128; ordinary omitted string bounds remain 8192. `objects.invoke` uses the fixed `object_errors.object_validation_code` allowlist; `create_mcp_app.call` uses `mcp_object_error` for object-only expected statuses. Preserve safe record path/keyword codes, generic private-error fallback, HTTP 409 object_conflict and 404 object_not_found, plus MCP c0/error metadata. Keep scope/role exceptions ahead of HTTP translation. No Core/schema/dependency/auth policy change was made. Freeze all three genuine deployed 9582568 digests together for future upgrades; documentation-marker builds are not its replacement. This final documentation marker requires its own actual CI/main verification.


## C0 Agent Memory track

Latest accepted runtime is PR 6 main `1a45070`, Core/app/schema
0.26.0/0.41.0/0013. PLAN records exact main local/publication/released-Core/
Debian installation/Rocky upgrade checks and downloaded native/privacy artifacts,
supported C0-only backup/update, exact original-data observers and live owned
current/legacy SDK evidence/Wiki/replay/conflict/scope/restart acceptance. The
existing connector independently reads the new citation and historical Wiki
revision, including after owned-client disable. Its cached catalog still has
63 tools; do not claim actual new-tool invocation or a refreshed catalog.

Preserve the three actually installed 1a45070 digests together as AM3's genuine
predecessor, seventeen prior clients, original evidence/history and eleven
unrelated modules. Temporary credentials are removed; private access, fixture
identities and failed evidence remain outside Git. Native CLI update receipts
and installed-image observers pass; the inspected recent HTTP API audit rows do
not contain a corresponding CLI update, so do not claim that audit correlation.
The bounded root app journal has actual health/authorization/token/MCP controls,
zero OAuth query/credential/submitted-body matches and zero tracebacks.

Exact slugs do not imply overwrite authority: omitted expected_revision means
create-only; present means update-only at the current active revision. Preserve
old fingerprints/DTOs, receipt snapshots, immutable revisions and lock order.
Replay returns the original snapshot, so resolve again for current content.
EvidenceNotReady remains a KnowledgeConflict subtype; claims require ready real
chunks. Keep fixed knowledge MCP errors, generic private-error fallback, object
errors and role/scope challenge separation. Released Core remains immutable;
no schema or dependency changed during this closeout.

AM2 closeout main 65829d4 has completed successful local/producer/released-Core/
both-native checks and actual artifact audits (PLAN.md). AM3 is active on its
feature branch; the first Core foundation adds the preserved shared-space
catalog, revisioned grants and captured delegated-token revalidation. Local
Core content isolation now passes 1040 Python/PostgreSQL/packaging cases,
106 scripts, schema/shell checks and twenty Robot dry runs. Forward migration
0015 scopes content, uniqueness, same-space references, receipts, derivatives
and feed cursors while preserving every predecessor column and OAuth authority.
The 63 role/grant/scope combinations, captured-token wait/regrant, 70-private-page
retrieval/provider isolation and independent installed package probes pass.
Preserve legacy shared fingerprints/DTOs and old sequence positions, even when
retained event rows have smaller IDs. Exact-source CI/native/publication,
application transports/UI and deployed acceptance remain pending. Do not expose
or deploy this candidate as a completed AM3 implementation.

Space work keeps object-type definitions global;
records, relations, events and annotations are protected by space. Application
Admins can access every space under actual OAuth scopes; Readers/Editors need
explicit protected-space grants capped by their application role. Do not infer
per-client isolation or add a separate grant model without an agreed requirement.
AM3 acceptance, AM4–AM6 and Windmill Gate remain gated. Earlier entries below are historical
implementation evidence, not current status.

C0-AM0–AM6 is a separate operator-authorized track in PLAN.md; preserve historical
milestones and planned Integration M17–M20. AM0 establishes current main, genuine
deployed predecessor, contract/inventory and disposable test baseline before any
runtime change. Preserve all existing pilot/fixture/client data. Later protected
spaces deliberately extend the present shared-space contract only after complete
server-side authorization and migration tests. C0 remains deterministic; external
agents own reasoning and consolidation. Windmill Gate is gated on accepted C0
merge/publication/deployment and validation. Never substitute marker images for
the genuine deployed 9582568 predecessor or ship private baseline evidence.

AM0 local baseline: 812 unchanged and 814 combined Python/PostgreSQL/packaging
cases pass, with 106 scripts, Go/shell and nineteen Robot dry-run cases. The
Git-only legacy-contract and synthetic investigation fixtures retain exact
authorization/REST bindings, evidence identities, conflicting claims and immutable
history; they are not actual client/space acceptance. See the baseline report
and exact-source promotion gates in PLAN.md. No runtime/data contract changed.

Exact AM0 candidate ebc38ef passes local/publication/released-Core and both-native
CI. Actual reports prove Debian upgrade nineteen passes and Rocky installation
twenty-three passes/three expected skips, seven browser/privacy guards and three
XML/Pino artifacts with zero query candidates. Candidate digests and exact run
links are in PLAN.md. The operator intends to review PR 3; that is not approval.
Verify this documentation follow-up's actual checks and main promotion before
starting AM1. No baseline marker is deployed; retain actual 9582568 predecessors.


AM0 is accepted after operator merge PR 3 and explicit deployment request.
Main b66e159 passes actual local/publication/released-Core/both-native checks,
including seven browser/privacy guards and three-artifact query audits. Supported
C0-only native backup and update pass with 27 domain tables, 89 terminal jobs/
attempts, exact OAuth rows/settings/files/schedules and eleven unrelated modules
preserved. Connected MCP reads and positive-control root journal privacy pass.
Core/app/schema stay 0.24.2/0.39.0/0013. All three **actually deployed b66e159**
digests in PLAN now replace 9582568 as the genuine AM1 test predecessor, at the
operator's explicit request; historical marker/deployment statements above remain
historical evidence. AM1 is active on feat/agent-memory-core. Follow its
Core-first publication then released-pin/transport subplan; do not claim the new
text tool available before that final application implementation and acceptance.


AM1's first Core increment has local validation: 847 complete Python/PostgreSQL/
packaging cases, 106 scripts, Go/shell and nineteen Robot dry-run cases pass;
independent wheel/archive clients prove ingestion/extraction/reconnect/replay and
citation hashes outside the checkout. SourceService.ingest_text is bounded to
131072 UTF-8 bytes and existing 16 KiB metadata, with same-key snapshot receipts
shared with Wiki/knowledge mutations. Preserve its static validation errors,
existing source provenance, ready-chunk claim requirement and after-lock current
role check. Core/schema candidate are 0.25.0/0013; app stays 0.39 and released
Core pin stays 0.24.2 until exact-source native/artifact publication passes. No new
REST/MCP tool is exposed by this increment and AM1 acceptance remains pending.


Core 0.25.0 is now immutably published from 02d3e49 after its actual exact-source
local/producer/released-Core/both-native/artifact gates; asset checksums are in
PLAN. App 0.40.0 candidate pins that released tag/subdirectory/commit and requires
>=0.25.0,<0.26.0. `sources_ingest_text` is an additive shared REST/MCP Editor write
operation with 131072 UTF-8 body/16 KiB metadata/one-MiB request bounds. Replays
return original state snapshots; poll versions then resolve actual document and
chunk IDs. Preserve all 63 old operations, source provenance, ready-chunk claims,
independent scopes and persisted roles. SDK envelope HTTP 400 diagnostics can echo
input; sanitize only those bounded error responses, preserving standard codes and
the fixed invalid_resource_request/service_unavailable messages and correlation.
Do not patch SDK globals or skip validation. Native SDK/SSO probes now verify text
receipts, actual timer extraction/chunks/claims in both modes, while persistence
checks cover exact receipts and citations across restart/update/restore. Final
application CI/review/deployment gates remain open; the live instance stays AM0
b66e159 and its three frozen digests remain the genuine predecessor.


AM1 app 0.40.0/Core 0.25.0 final local suite passes 862 cases, with 106 scripts,
Go/shell/nineteen Robot dry-run passes and six checks of the actual published
wheel/archive. The default released source is pinned exactly; transitive packages
are unchanged. The SDK-envelope regression proves submitted text would appear in
validation errors without the transport fix; preserve the bounded error-body
buffer, standard protocol codes, fixed public resource messages and correct 503
fallback if an error response is interrupted. Final app CI/native/review/live
acceptance remains required and is not inferred from local results.


AM1 app candidate 84f64b1 passes exact local/producer/released-Core/Renovate and
both-native checks. Actual logs prove 862 Python/PostgreSQL/packaging and 106
script cases; downloaded Debian installation has sixteen passes/three expected
skips and genuine Rocky b66e159 upgrade twenty-six passes/all seven browsers and
privacy guards. Both checkouts match source, real SSO/SDK probes pass and three
XML/Pino artifacts have zero OAuth queries. Text receipts/versions/citations now
pass actual native restart/update/restore. The default released-source image
passes actual runtime/license/source audits and Dive analysis; five inspected
Trivy/SBOM pairs retain documented vendor findings while the fixable-critical
gate passes. PLAN freezes the candidate digests separately from genuine installed
b66e159. This docs-only evidence marker needs its own actual checks before PR 4
review/main promotion. AM1 is not accepted/deployed and AM2 must wait for its
reviewed main publication, targeted update and live validation. No new ChatGPT
UI/provider-quality/stable-module-release or CPU-quota claim is made.

AM2's first Core increment passes 904 full Python/PostgreSQL/packaging cases,
106 scripts, Go/schema/shell and nineteen Robot dry runs locally. The independent
wheel/archive probe proves safe Wiki revisions/replay after reconnect outside
the checkout. Core/schema candidate are 0.26.0/0013; app/released pin remain
0.40.1/0.25.0 until exact-source CI/native and immutable publication. There are
still 64 public operations. Do not claim new Wiki helpers deployed or AM2 accepted.

AM2's uncommitted REST/MCP adapters pass 956 full local Python/PostgreSQL/
packaging cases and 52 focused adapter cases, plus the unchanged 106 script and
nineteen Robot dry-run checks. All 64 old schemas/metadata are frozen; the new
catalog adds exact resolve/upsert only. New knowledge errors use an explicit
thirty-operation allowlist, preserve object errors and role/scope behavior, and
never expose private exception detail. Native probes add two actual SDK Wiki
lifecycles plus persistence receipts/history; explicit hostname-root reconstruction
and UUID client fixtures must match their real interfaces. App version/released
pin remain 0.40.1/0.25.0 pending exact Core native/artifact gates. No new feature
is deployed and AM2 still requires final application CI/review/main/live gates.

The operator confirms fresh connector authorization completes after the consent
fix. Actual reconnected MCP citation reading returns the exact prior immutable
chunk/source hash. Keep this distinct from the session's currently available 63-tool metadata;
fresh SDK discovery proves all 64 deployed operations. Do not infer a refreshed
connector catalog or new-tool invocation from that observed read.

Core 0.26.0 is immutably published from 6093219 after completed exact local/
producer/released-Core/both-native checks and actual artifact/privacy audits.
Debian genuine ece3e90 upgrade has nineteen passes; Rocky installation has
23 passes/3 expected skips, all seven browsers/privacy guards and two real
SSO/SDK probes per distribution. Actual downloaded wheel/archive checksums and
six independent packaging checks pass. PLAN records digests, assets and runs.
App 0.41.0 now pins that exact released tag/subdirectory/commit, compatible
>=0.26.0,<0.27.0, with all 53 transitive lock records unchanged. Preserve the
explicit malformed-status/private-error fallback and existing scope/object error
contracts. Final application promotion still requires its own exact CI/native,
human review, successful main publication and dedicated deployment. Live remains
ece3e90, Core/app/schema 0.25.0/0.40.1/0013; AM2 and Windmill Gate are not accepted.

AM2 final app 0.41.0/released Core 0.26.0 local suite passes 958 cases,
106 scripts, real Renovate API bounds, Go/schema/shell and nineteen Robot dry
runs. The real released-source image passes runtime/license/source verification
and packages both routes; actual Dive efficiency is 98.12%. Both consumer version
bounds must follow minor 0.26 (workflow and runtime probe); the original 0.24
consumer fixture remains unchanged. All 64 old schemas/roles/scopes stay fixed,
with two additive operations and no schema change. PR 6 is draft pending exact
application CI/native/artifact/privacy and human review/main/deployment gates.
Do not substitute these candidate images for the genuine deployed ece3e90.

AM2 app source cf3e9c9 passes actual exact-source local/producer/released-Core
and Renovate checks. Downloaded scan/SBOM reports retain the vendor findings
recorded in PLAN; the fixable-critical gate passes. Three OCI manifests/configs
match this source and its released dependency. Native 39036302061 passes actual
Debian installation sixteen cases/three expected skips and genuine Rocky ece3e90
upgrade twenty-six cases, all seven browsers/privacy guards and two real SSO/SDK
probes per distribution. Three downloaded XML/Pino artifacts have zero OAuth query
candidates; both actual checkout logs match cf3e9c9. These probes require both
current/legacy Wiki maintenance lifecycles and retained history/retry receipts.
This final evidence marker needs its own exact CI/native verification before
human review. Reviewed main publication and supported dedicated deployment remain
required; genuine deployed ece3e90 digests remain frozen. AM2 is not accepted.


## AM3 released Core and application conventions (pending acceptance)

Core 0.27.0 is published at immutable 86a7f7f after exact local/image/both-native
checks and downloaded artifact reproducibility/installation/migration gates.
See PLAN.md for actual reports and SHA-256 identities. App 0.42.0 pins that exact
released tag/subdirectory/commit and restricts compatible updates to 0.27.x.
The live predecessor remains accepted AM2 1a45070; do not deploy the Core-only
candidate or documentation images as a substitute.

Space selection is explicit immutable service state. Omitted selectors always
mean legacy Shared; unauthorized/invalid selectors never fall back or infer a
space from a UUID. Object-type definitions stay global. Actual role/space/scope
checks, captured-token revalidation after waits, same-space references and legacy
receipt snapshots remain Core contracts. UI helpers are explicit per-controller
requests, never a global fetch patch. Clear private DOM/cache/drafts before
navigation or on access loss and reject both late headers and parsed JSON.
Admin grants use revisions, tombstones and unchanged uncertain-request keys;
ordinary home must not fetch Admin account lists. Preserve source/session/grant
lifetimes, current role checks, CSRF and existing Tools safeguards.

New native protected recovery fixtures are seeded through normal SSO/public HTTP
before encrypted backup. Compare immutable evidence, authored history, grants
and record identities after update/clean restore; a trusted Core CLI probe alone
is not an application SSO observation. Retain all seven existing native browser
workflows and execute the additional independent-session protected-space case.
AM3 acceptance requires actual new application native/artifact/main/live gates;
AM4 and Windmill Gate remain gated. Existing CPU and interactive waivers persist.


## AM4 applicability and structured retrieval (runtime accepted)

Keep applicability and verification as separate exact-content annotation histories.
Mutable targets require the observed content revision; annotation revision zero is
create-only, and later changes require the current annotation revision. Retry
receipts are original snapshots. Preserve omitted fields independently of explicit
null through REST argument serialization; do not change the shared catalog's old
serialization or old operation schemas. Missing/stale metadata remains unknown.

Structured retrieval is opt-in; ordinary source/Wiki search stays compatible.
Validate nonempty supplied filters, literal exact tags and timezone-aware times.
Filter space/archive/applicability before candidates, counts, ranking and provider
inputs. Only existing evidence categories use optional providers; entity/object/
claim results use deterministic text and observed references. Preserve immutable
citations separately and recheck authority after provider I/O.

Core 48ac409 passes actual push/PR local, producer/released-Core and image/artifact
review; PR checkout is a merge with the identical source tree. Native 39079184903
passes genuine Debian upgrade and Rocky installation, all eight browsers and
actual privacy artifacts. Core 0.28 publication 39081511130 and downloaded artifact
checksums/independent installations pass. App 0.43 now pins that released source
and frozen lock with all 53 transitive packages unchanged. App 12dce0a and
reviewed main 878978d pass 1127 Python/PostgreSQL/packaging cases, 125 scripts,
schema/shell checks, twenty Robot checks, producer/released-Core/Renovate and
actual both-native artifacts. Main native 39085658892 passes Debian genuine
cb60da9 upgrade twenty cases and Rocky installation twenty-five cases/three
expected skips, all eight browsers/privacy guards and twenty-five accessibility
contexts. Both SDK protocols and all-five-target annotation histories/receipts
survive native update and clean restore. Three downloaded query artifacts pass.

The supported dedicated update installs exact main 878978d after a verified
schema-0015 backup, including byte hashes of all four retained originals. The
same fresh delegated/browser authority survives update and full-manager restart
without lifetime changes; owned live SDK histories, changed-content unknown
verification, exact filters and retained originals replay after restart. The
owned client is persistently disabled, with a valid bearer positive control and
separate native-browser/other-client reads. Actual 1027-line root journal privacy
passes. Preserve failed private evidence; a stale final comparison path was
corrected to the real schema-0015 baseline before accepting its 7146-row result.
Freeze the three installed feature digests, rather than documentation-marker
images. Verify this closeout marker's actual CI/main results before AM5; retain
all eight automated native browsers and both existing waivers.

## AM5 consolidation implementation conventions

AM4's final marker/main d889902 passes actual local/publication/released-Core/
Renovate and native 39109200513, including all eight browsers and inspected
source/privacy artifacts. AM5 used accepted 878978d as its genuine predecessor;
the deployed AM5 source and next predecessor are recorded below.

Five PostgreSQL experiments prove that individual writes/retry receipts cannot
make multi-resource publication atomic: racing writers, revocation and injected
harness failures leave earlier writes committed. Core 0.29.0 therefore adds a
bounded knowledge bundle and explicit maintenance metadata. Exact Core source
8157092 passes all CI/native/artifact gates and is published as core-v0.29.0;
app 0.44 adopts that released source with >=0.29.0,<0.30.0. Schema stays 0016;
application CI/native/deployment acceptance now passes as recorded below.

Bundles use one selected space, one to twenty-five fixed trusted content writes,
the existing 256-KiB JSON budget and one original-result receipt. Only earlier
step UUID/revision paths can be referenced. Domain methods execute their trusted
mutation closures on the outer transaction; no substep opens a connection,
commits or writes a receipt. Acquire object mutex 49375 before knowledge mutex
49376, then the existing authority locks and current role/grant/token recheck.
Preserve old individual API fingerprints. Do not expose arbitrary method names,
imports, callbacks, file ingestion, jobs, schema/grant changes or native actions.
Standalone supersession annotations that retain object references also acquire
49375 before 49376; otherwise multiple object anchors can deadlock against a
sorted independent object batch. Ordinary old annotations keep their lock path.

Keep applicability/verification separate. New literal knowledge types,
supersession targets and ready immutable chunk references describe supplied
observations. Retain superseded identity/hash anchors even for unannotated
objects later deleted; unknown remains unknown. Supersession never archives,
rewrites prior evidence or transfers verification. Validate all references in
the selected space and preserve old histories, null/omission and strict payloads.

Local verification uses a separate database per full run and absolute import
paths. A cancelled shell can leave its test child active: inspect completion
before starting another run. Preserve failed reports. Errno 122 is the actual
local disk quota even when df reports free space; remove only reproducible
caches/environments, retaining source artifacts and acceptance/privacy evidence.
Actual exact-source CI/native/Core publication, released app adoption and live
acceptance pass below. AM6 and Windmill Gate remain pending.

AM5 application bundles expose seventeen fixed typed operations through one
Editor/c0:write operation, body-selected space and a whole-result receipt.
Preserve supplied fields/nulls and reserved `$result` references through REST
model serialization. Normalize each stored result through its existing public
DTO without re-reading current rows. Require actual native current/legacy
sourced bundles and receipt/history/citation/supersession recovery; read-only
roles/tokens must retain their precise denial/challenge behavior. Keep Core
0.29's immutable publication source and installed predecessor 878978d distinct
from application and documentation images.


## AM5 runtime acceptance (18 October 2026)

AM5 runtime main `41864e4` is deployed and accepted with Core 0.29.0, app
0.44.0 and schema 0016. Exact-source CI/native, released Core, canonical update,
C0-only verified backup, current/legacy sourced bundles, full-manager restart,
old-column/OAuth preservation and bounded root journal privacy pass. The new
owned client is disabled after a valid same-bearer positive control; the saved
browser/REST session and an independent existing connector remain accepted.
All 7283 old rows, 136 terminal jobs/attempts, 5 originals,
20 old clients, 12 prior plans and 11 unrelated modules are preserved.
Other actual live personas, refreshed cached tools, provider quality, scheduled
interoperability and a stable module release are not claimed. AM5 final marker c1a90d3 passes actual main/native/artifact checks; AM6 remains gated.

Freeze the actual installed `41864e4` three-image digests from PLAN.md for
AM6’s genuine predecessor; documentation-marker images are not that deployment.
Native indexing fixtures must observe successful scheduled work for the active
profile/generation and complete all current source/Wiki candidates before
recovery snapshots. Shared-space vector counts cannot measure global indexing.
Keep the bounded registered-job cap, paused schedule, original receipts and
installed authority lifetimes. All eight automated browsers remain mandatory;
interactive Playwright and CPU-quota waivers remain unchanged.


## Scoped CI policy accepted sources

The CI policy is merged through PRs 14 and 18. Final main `31ca102` passes actual full
39155318390: 1284 Python/PostgreSQL/packaging, 125 controllers, 21 Robot checks,
producer/released-Core/runtime/license/five scans, Debian 21 and Rocky 26/three
expected skips/all eight browsers. Actual source/digest, restore, artifact privacy
and accessibility evidence passes; canonical publication actually succeeds.
Fresh registry reads verify all six main/latest digests and immutable sibling refs.
See PLAN.md and docs/ci-policy.md. Current unit cases 339; focused cases 98.

Main protection requires GitHub Actions C0 merge gate (app 15368), strict base and
admin enforcement. Use verify-promotion on the current ready head; preserve full
runtime/main/release/deployment gates. Docs-only markers use lightweight PR/main
checks and do not replace accepted runtime proof. A docs-only main HEAD can differ
from its canonical runtime source; use the publication proof's exact source.

Keep failed evidence outside Git: the Git-less Robot probe is fixed by explicit
source binding, and GitHub's skipped-ancestor publication condition is fixed by
explicit successful gate checks. One pre-existing forced-plan SQL timeout remains
a recorded timing limitation; fresh full runs pass without changing runtime
SQL/deadlines or adding automatic retries. All original unfinished files remain
preserved. Dedicated runtime `41864e4`, Core 0.29.0/app 0.44.0/schema 0016 and its genuine
predecessor digests remain unchanged. AM6, Windmill Gate and Integration M17–M20
are separate and pending. No stable module release is claimed.
