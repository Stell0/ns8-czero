# C0 roadmap and implementation status

## Current checkpoint

21 October 2026: M19 runtime acceptance passes. Reviewed PR29 regularly merges tested `38a8654` as `7a223fb` with an identical tree. [Main full validation/publication39632626515](https://github.com/Stell0/ns8-czero/actions/runs/39632626515) and independently inspected native/privacy/scan artifacts pass. [M19 closeout PR30](https://github.com/Stell0/ns8-czero/pull/30) at `8a0144d` passes [its own documentation CI39641566107](https://github.com/Stell0/ns8-czero/actions/runs/39641566107); the operator reviews and approves it, and regular merge `0a9bbb3` passes [main documentation CI39643655916](https://github.com/Stell0/ns8-czero/actions/runs/39643655916). Exact-source promotion verifies the marker. M21 is based on this verified main.

Historical M00–M20, Agent Memory AM0–AM6, failures, observations, measured limits and exact CI/source identities are retained in the [archived plan](docs/history/PLAN.md). Historical status statements do not reopen accepted work. The original root checkout's dirty documents and recovered M20 worktrees remain untouched.

## Accepted runtime

The dedicated C0 installation remains source `38a8654486581e0f2af21672e8675a2e925d2b38`, canonical tag `ci-38a8654486581e0f2af21672e8675a2e925d2b38-39613259374-1`, app0.49.0/Core0.31.0/schema0018. Preserve this genuine M21 upgrade predecessor and keep its tag available unchanged while referenced.

| Image | Accepted installed digest |
| --- | --- |
| Module | `sha256:0a78eef9a6cfd6246e495c88d4f95ecbc1c6daaf7bb38d3d0e003ffbe82db7fb` |
| App | `sha256:4b2000d645cb9f6d7a508365d770d37db2cc085af113340c635f89e79bd23d9b` |
| PostgreSQL | `sha256:d8beafaa39c490e9046e4611b298a7cd8ab87ef7400ac1adbd84a2a32d9cecf2` |

Core source `87b8fd1` / `core-v0.31.0` and published artifacts are immutable. Main or documentation-marker images do not replace the accepted runtime. [Detailed M19 acceptance](docs/history/PLAN.md#m19-deployed-acceptance-and-main-closeout--21-october-2026) retains actual ChatGPT, renewal, data/inventory and journal evidence.

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
