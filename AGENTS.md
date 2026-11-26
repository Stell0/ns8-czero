# C0 / ns8-czero — Instructions for coding agents

C0 is a self-hosted shared knowledge service and a base for application forks.
Assistants reason over evidence. C0 stores it, enforces access and runs registered operations.

## Start here

- Fetch `main` from [original C0](https://github.com/Stell0/ns8-czero) and start an isolated worktree at that commit. Preserve dirty checkouts and fork customizations.
- Use the [roadmap](PLAN.md#roadmap) and the relevant delivery record in PLAN for accepted scope and deployed identities. Use manifests and locks for source versions.
- Read the matching skill in `.agents/skills/` and [feature contract](docs/development.md#feature-contracts). Use the installed NethServer skills for native operations, commits, PRs and releases, and Nebula for frontend work.

## Where changes belong

- `packages/czero-core` owns reusable domain operations, authorization, transactions and migrations. Forks consume an immutable Core tag with a frozen lock. Select local Core explicitly for producer development.
- `app` owns REST/MCP transport and fork-specific behavior. The reference website is Vue 3 in `app/frontend`; NS8 Settings is Vue 2 in `ui`. Numbered NS8 lifecycle and backup actions live in `imageroot`.
- `plugins/c0-knowledge` supplies instance-bound end-user skills. Keep developer skills outside runtime packages. Verify changed connector contracts with the authorized account and an actual tool operation. See [plugins and connectors](docs/development.md#plugins-and-connectors).
- Review managed fork updates through `c0-upstream.json`. Preserve customized files, independent registry identities and released-consumer checks. See [fork development](docs/development.md#forks-and-upstream-updates).

## Security and compatibility

- Authorize inside the Core transaction using persisted membership, the selected space and delegated scopes. Denial must never fall back to Shared. Tools, references and optional retrieval providers grant no authority. Keep ordinary text search available without a provider.
- Source and Wiki bodies are latest-only. Stage and validate whole replacements, publish atomically and remove superseded copies. Keep revisions and payload-free replay identities. Return authorized `content_superseded` (410) for expired exact evidence. Preserve authored knowledge and mark stale citations. See [migration and preflight](docs/latest-only-migration.md).
- Preserve separate controls for user roles, application approval, OAuth consent, logout, disconnect and blocking. Scope expansion and offline authority require explicit consent. See [identity and access](docs/development.md#identity-and-access).
- Keep knowledge views read-only except for explicit source controls. Preserve safe rendering and account/space guards across navigation and permission changes. See [website contracts](docs/vue-website.md).
- Reuse the [ingestion samples](samples/ingestion/README.md). Keep real jobs, credentials, datasets and traces private under ignored `.local/ingestion/<job>/`. Ingestion and generated packages confer no authority to install schedules.

## Tests are part of the feature

From the repository root, build the website before running application or browser tests.

```sh
npm --prefix app/frontend ci --ignore-scripts
npm --prefix app/frontend run check
npm --prefix app/frontend run test:e2e
```

Use [local verification](docs/development.md#local-verification) for the Python environment and dependency selection.
With a private `CZERO_TEST_DATABASE_URL` pointing to disposable PostgreSQL/pgvector, run the suite.

```sh
.venv/bin/python -m pytest -q app/tests packages/czero-core/tests tests/unit tests/integration tests/packaging
```

Use separate databases for concurrent jobs. Skipped database cases do not establish a pass.
For documentation, run `python scripts/documentation.py` and `python -m pytest -q tests/unit/test_documentation.py`.

## Definition of done

- Test observable changes on the original base and candidate according to [CI policy](docs/ci-policy.md). Retain regression coverage across rebases and Core upgrades. Preserve frozen full/native runs. The interactive Playwright and CPU-quota waivers still apply. Keep automated native browsers and the other resource limits.
- Fetch and rebase before opening a PR and when the base advances. Reconcile locks, migrations and managed-file comparisons. If review, publication or deployment evidence is frozen, create a successor branch and repeat affected checks. Preserve immutable commits, tags and image identities.
- Open a focused upstream PR for reusable improvements. Review the complete diff and affected instructions, complete the PR template and record the exact source, base and selected results. Assign reviewers only on request.
- Enable protected regular auto-merge with `gh pr merge <number> --auto --merge --match-head-commit <full-head-sha>`. Require the current Actions-owned `C0 merge gate`. Agent review suffices. Verify direct merges with `scripts/verify-promotion.py --source <full-head-sha> --pr <number>`.
- Releases, canonical publication and deployment require full native acceptance. Live deployment also requires explicit authorization, supported backup/update, preservation, restart and positive-control privacy checks. See [deployment acceptance](docs/ci-policy.md#deployment-and-milestones).

<details>
<summary>Historical section links</summary>

See the [historical index](docs/history/AGENTS.md).

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
