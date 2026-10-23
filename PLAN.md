# C0 roadmap and implementation status

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
