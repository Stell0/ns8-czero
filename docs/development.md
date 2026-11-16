# Develop and maintain C0

## Layers and instructions

Read the root [AGENTS instructions](../AGENTS.md), [current plan](../PLAN.md) and the relevant repository skill. `packages/czero-core` owns reusable domain operations, authorization and migrations. `app` owns HTTP/MCP transport and the reference UI. Native lifecycle/configuration/backup belongs in numbered `imageroot` scripts; NS8 Settings uses Vue 2 and Ns components.

Install the maintained [NethServer skills](https://github.com/NethServer/agents) for module, container, administrative, commit, PR and release tasks. Do not copy those manuals into this repository. The repository's skills route application feature, Core, upstream contribution, fork upgrade and measured tool-evaluation work. End-user plugin templates ship in the app image for generated downloads; repository development skills stay outside runtime images.

Use the active dependency manifests and `app/uv.lock` for current versions. The Core package tree can be ahead of the released app dependency. Check the package manifest, consumer tag and immutable lock separately. Never edit or replace published Core artifacts as part of a documentation cleanup.

## Website development

The reference website lives in `app/frontend`, separately from NS8's `ui`.
Use Node 24 and npm 11 with the committed lock:

```sh
npm --prefix app/frontend ci --ignore-scripts
npm --prefix app/frontend run check
npm --prefix app/frontend run test:e2e
```

Build **before** Python application and browser tests. FastAPI serves the compiled
`app/frontend/dist` by default; `CZERO_FRONTEND_DIR` selects another compiled
asset directory. The production Node build stage ships only compiled local
assets/fonts/notices, without Node or development dependencies. There is one
website, with no legacy route/controller compatibility layer.

Follow the [website contracts and acceptance mapping](vue-website.md) and the
installed Nebula skill. Keep knowledge views read-only; preserve source controls,
server-managed cookies, exact CSRF, scoped query identities and the bounded
Markdown worker. Translations, accessibility, late replies, cancellation and
permission loss are part of each affected flow. Existing REST/MCP schemas and
Core authority remain unchanged by presentation work.

## Local verification

Use Python 3.12–3.14 and a fresh virtual environment. The following installs producer-development dependencies; it does not change the released runtime source selection:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install uv==0.12.20 pytest robotframework robotframework-sshlibrary
# Explicit producer override; the shipped consumer tag/lock remain unchanged.
.venv/bin/python -c "from pathlib import Path; print('czero-core @ '+Path('packages/czero-core').resolve().as_uri())" > /tmp/c0-producer-requirement.txt
.venv/bin/uv pip install --python .venv/bin/python --override /tmp/c0-producer-requirement.txt -e packages/czero-core -e 'app[test]' -e samples/ingestion
# The override can resolve Core as a built copy. Make iterative producer edits explicit.
.venv/bin/uv pip install --python .venv/bin/python --no-deps --reinstall -e packages/czero-core
.venv/bin/python -c "import czero_core; print(czero_core.__file__)"
```

Provide `CZERO_TEST_DATABASE_URL` privately for a **disposable** PostgreSQL/pgvector database. The test account must create/drop owned test databases for packaging and forced-index isolation. Do not use production data. Without that setting, database skips are not a pass.

```sh
.venv/bin/python -m pytest -q app/tests packages/czero-core/tests tests/unit tests/integration tests/packaging
node --test tests/ui/*.cjs # Native NS8 settings and accessibility probe
go run tests/check_schemas.go
.venv/bin/python scripts/documentation.py
```

Use the actual separately parsed shell and Robot commands in the [local workflow](../.github/workflows/test-local.yml). Build native administration UI with its immutable Yarn lock; run `corepack yarn install --immutable` and `NODE_OPTIONS=--openssl-legacy-provider corepack yarn build` from `ui` using the pinned CI Node version.

Do not run tests concurrently against a shared mutable database. Use fresh uniquely named databases; retained failed evidence does not authorize changing runtime limits to make a test pass. The [evaluation guide](tool-evaluations.md) separately covers authorized model runs; normal CI requires no model credentials.

## Public contracts and safety

Use trusted operation bindings, current persisted roles inside Core transactions,
explicit spaces and delegated scopes. Preserve lock ordering, expected revisions,
exact evidence identities and payload-free replay receipts. A denied space never
falls back to Shared. Tools, provider responses and metadata confer no authority.
Verify HTTP, ordinary SDK metadata and current/legacy MCP wire contracts when touched.

Source and Wiki content is latest-only: stage replacements privately, validate and
publish whole documents atomically, and delete superseded bodies, originals,
derivatives and indirect receipt copies. Keep stable logical IDs, monotonic
counters and current hashes/provenance. Expired exact evidence and superseded
replays return authorized `content_superseded` (410), never rebound text. Preserve
authored knowledge and mark invalidated evidence stale. Follow the
[migration and preflight](latest-only-migration.md) for authorized upgrades.

## Feature contracts

Read the relevant subsection and linked contract before changing these features.
These are standing requirements; source versions, accepted images, run IDs and
pending acceptance belong in [PLAN](../PLAN.md#current-baseline). Consult
[archived conventions](history/AGENTS.md) and [milestone evidence](history/PLAN.md)
only for the relevant historical topic.

### Identity and access

Follow [workspace access](workspace-access.md) and [API-key contracts](api-keys.md).
Preserve explicit blocks, disabled clients, metadata review and credential ceilings.
Baseline audience access is Read only; existing protected spaces remain restricted.
The retired discovery switch must not reappear during upgrade/restore. Application
approval, user permissions, exact connection disconnect and persistent blocking
remain distinct. Person-role selectors use one cumulative choice: **Read**,
**Read and write**, or **Read, write and manage**. Application consent scopes are
independent selections and do not reuse these role labels.

OAuth retains verified native identity, explicit consent, S256, exact
callback/resource/host/origin checks, bounded bodies and duplicate rejection.
Authorization may ignore future optional fields only after full multimap validation;
token/revocation remain strict. A client-selected port is allowed only for an approved
portless HTTP loopback URL: preserve host/path, explicit-port and HTTPS exact checks.
Use the shared Core matcher in approval/consent/authorization; bind redemption to
the exact requested callback and PKCE proof. SDK descriptor projection is request-local;
never persist an observed port into the registered client.

The reference app enables CIMD for its configured authenticated HTTPS endpoint;
Core policy remains explicit. Self-service registration permits only requested
Read for validated exact HTTPS URL identities. Pin public DNS/TLS peers and recheck
authority after I/O. Additional client permissions require administrator approval;
remote metadata never supplies roles. Existing UUID clients remain independent.

Refresh cannot add scope or extend existing interactive grants' absolute authority.
New background grants explicitly opt into separate offline authority with a
snapshotted thirty-day inactivity window and no fixed maximum; never promote old
grants silently. Cookies, codes and pending consent remain finite. Bind background
login purpose and expected account to one-use persisted state. Persistent refresh
rotation uses keyed family/generation proofs, bounded storage and committed replay
revocation before SDK scope validation. Preserve client/account/resource/secret
bindings, current-role checks and genuine predecessor recovery. Native acceptance
includes real offline issuance, owned provider logout, renewal and revocation;
local/fake-clock tests do not establish scheduled-client acceptance.

Remembered website login stays server-bound, one-use, Origin-checked and renewable
only after verified offline issuance and successful authenticated traffic. Browser
logout and exact connection disconnect remain distinct. API-key creation defaults
to 90 days with a visible 1–365-day range; only explicit **Never expires** selects
indefinite authority. Preserve the nullable lifetime API, account/space revision
bindings through trusted Actor refreshes, scopes and revocation. Keys never gain
native extraction or first-party authority.

### Website and structured tables

Follow [Vue website contracts](vue-website.md), [structured tables](structured-tables.md)
and the installed Nebula skill. `app/frontend` uses Vue 3/TypeScript, Composition API,
the frozen npm lock and local compiled assets; NS8 `ui` remains Vue 2/Carbon.
Preserve emerald semantic colors, Poppins 400/500 and font notices, and matching
English/Italian keys. Knowledge views are readers; source upload, replacement,
reprocessing and recovery are explicit exceptions. Preserve cookies, X-C0-CSRF,
account/space query identities, cancellation, response/draft/replay/access-loss
guards, unique template identifiers and 410 supersession. Never store knowledge or
credentials in browser storage or enable stored HTML/remote images. Ordinary readers
do not initialize mutation controllers or fetch Admin lists; files remain REST uploads.

Sign-in uses its server-bound native form and escaped inert boot data; website
routes have no legacy aliases. OAuth setup loads reviewed application metadata
without requiring Details. Failed or stale previews cannot advance the connection;
unchanged technical-client reviews preserve existing grants and revisions. Copy
canonical instance URLs instead of constructing deployment-specific hostnames.
Run frontend checks, real browser workflows and affected native workflows under
[CI policy](ci-policy.md); a component build alone is not browser acceptance.

Keep populated record-type discovery scoped to current Reader authority, with
legacy global schema discovery as the default and available before ingestion space
selection. Sorting validates scalar fields, places missing/null last and uses stable
ID ties before paging. Tables preserve schema titles verbatim, exact filters,
server sorting, bounded pagination, safe nested rendering and existing Explore links.

### Ingestion and extraction

The [automatic-source producer](automatic-sources.md) adds explicitly enabled
space-owned public GitHub/website updates. Its native worker uses registered
collectors and existing source publication, with current authority and run fences.
Develop with explicit local Core; the frozen consumer lock remains independent.
Existing external ingestion jobs stay runnable until an explicit migration.


Use c0-ingest-sources and the [ingestion samples](../samples/ingestion/README.md)
before writing another collector. Reuse shared client/authentication/state/readback
helpers. Put generic source logic, synthetic tests and reusable lessons in samples;
keep instance wrappers, `.env`, credentials, datasets, state, receipts and operational
notes in ignored `.local/ingestion/<job>/`. Preserve space/account/external-key
mappings and the original job until validation passes. Run authorized ingestion
through saved scripts and verify actual results. Review the full adapter diff and
run the privacy checker with a private deployment denylist before contributing.
Do not install schedules or broaden authority as an ingestion side effect.

Queued extraction follows [pipeline contracts](ingestion-pipeline/CONTRACTS.md).
Preserve disabled defaults, native actor leases, fenced completion and whole-document
publication; extraction units never become external source-sync publication parts.
Optional structure overflow retains complete-body fallback; parser/integrity failures
remain publication failures. Local OCR is explicit and local-only with fixed
commands/model fingerprints, process-group deadlines and disabled pending-work
behavior. Cache reuse stays same-space, current or unexpired staging, input/profile-bound
and ownership-rechecked; no permanent retired-body cache. Selective context binds
logical ID, current revision/hash and citation offsets with strict budgets and no
fallback. Preserve worker resource/restore grading and both timers' activation during backup.

### Retrieval and cross-space references

Read [retrieval evidence](retrieval-evidence.md), [benchmarks](retrieval-benchmark.md)
and [cross-space reference contracts](cross-space-references-plan.md). Provider-free
question recovery belongs in the shared Core lexical helper. Preserve strict
query operators/results, minimum term and identifier constraints, selected-space,
category and annotation predicates, and current supporting-passage citations.
Freeze product/version provenance with benchmark bodies because it affects fallback
eligibility. Record actual `lexical_strategy` separately from semantic/provider
modes; optional metadata cannot alter authority or legacy source citation lists.
Keep bounded normalization, legacy embedding profiles, opt-in contextual inputs
and complete-coverage invalidation. Producer work does not authorize activation or
released-consumer adoption.

Cross-space references retain five stable endpoint kinds, identity-only edges,
explicit source/target selectors, current both-endpoint read checks, blind source-owned
deletion, credential bindings and revocation lock order. References confer neither
authority nor evidence; browser reference panels remain separate work.

The [BEIR benchmark](../benchmarks/retrieval/README.md) is a repository-only tool
using public authenticated APIs. Keep dependencies, datasets, manifests and reports
out of runtime packages/images. Reuse `c0_ingest` authentication, readback and atomic
state helpers. Evaluation is read-only and requires the exact dedicated protected
space and complete verified corpus. Queue missing originals before verifying
extraction; preserve source/version/hash receipts and the single uncertain write
intent across resumes. Synthetic tests run in the ingestion unit suite; the optional
local extra checks metrics against BEIR's `pytrec_eval`. Real ingestion/evaluation
and provider changes require explicit authority.

### Compilation and protected projects

Follow [compiler contracts](knowledge-compilation/M5.md) and [measured quality
results](knowledge-compilation/RESULTS.md). Search remains read-only; Readers,
explicit read-only tasks and missing Write skip feedback. Enabled feedback queues
a bounded source-backed proposal, not published knowledge. Never store queries,
answers, conversations or benchmark labels in compiler metadata. Reuse all six
coordinator tables, durable cursors, fences, budgets and current source/page bindings;
never reopen terminal tasks to account for inference. Generated packages install no
tasks. Preserve failed quality thresholds and independent answer audits; benchmark
acceptance does not authorize private-source copying, publication or production writes.

Use [project contracts](projects/PROJECTS.md) and c0-project-workflows for protected
projects. Generic object/bundle writes must not bypass managed-record policy.
Preserve actor-bound leases, manifest versions, fencing, attempt reservations,
uncertain-call recovery, independent monitoring coverage and report/evidence revisions.
Saved results, notification, external publication and human reading are distinct.
Consult the affected source/workflow/monitoring/reporting/maintenance contract;
historical milestones do not grant live migration or scheduling authority.

### Plugins and connectors

After feature, Core or base upgrades, check affected MCP tools, descriptions,
schemas, safety annotations, plugin/skill content and setup guidance against the
actual instance. Update affected artifacts together; refresh/reload the tool catalog,
verify the intended account and perform a real authorized operation. Include
regression checks for changed tool contracts and workflows. Inspect tool results
and saved revisions: HTTP 200 or a package build alone is not success.

Preserve connection identity and unrelated settings on content-only updates. New
scopes require appropriate client approval and fresh explicit OAuth consent.
Documentation-only changes without connector-contract impact need no plugin bump.
Synchronize runtime COPY inputs, the closed audit allowlist, offline/HTTP package
inventories, native downloaded-archive checks and evaluation inputs when packaged
skills change. Only instance-bound end-user skills ship in runtime; standalone
consumers receive registered developer skills with explicit upstream links for
absent application-specific contracts. Never initialize projects or schedules to
test discovery. Separate vendor MCP support from tested C0 compatibility, and
interactive OAuth from actual scheduled execution or packaged-skill acceptance.

## Forks and upstream updates

Use the explicit `c0-upstream.json` file registry and trusted `scripts/sync-upstream.py`; inspect a complete immutable source comparison before apply. Preserve customizations and unresolved comparison baselines. Newly referenced reusable infrastructure must be explicitly registered. Never include ignored/private state by walking the checkout.

The standalone [fork acceptance generator](../examples/fork/create.py) copies only registered infrastructure; verify newly linked developer references are included. Customer-specific docs/configuration and generated plugin packages remain outside automatic upgrades. Workflow changes require the publisher's appropriate GitHub permission; a token without it is not a reason to copy a broad personal secret into a fork.

Runtime builds use the released Core tag/subdirectory and frozen app lock by default. `CZERO_CORE_SOURCE=local` is an explicit producer-development override, never an implicit fallback for a fork. Core changes require an independently verified immutable release, then consumer pin/lock adoption and final image/native validation. Core artifact publication is distinct from an NS8 module release.
The Core publisher installs the same local parser runtime used by package
acceptance. If publisher infrastructure needs repair after a tag is frozen,
run `Publish C0 Core` manually from the repaired workflow with its existing
`core-v<version>` tag. The workflow resolves that tag to the actual checkout,
rechecks exact-source full/native acceptance and version metadata, builds with
the tagged source timestamp, and refuses to replace different published bytes.
The workflow commit and the released Core commit can differ; the tag never moves.


Reference publishing CI compares the committed Core package tree with the full
Git commit in the consumer lock. Identical trees select the released dependency;
different trees select explicit upstream producer development. Version strings
alone do not establish equality. The checkout includes history so missing or
invalid release identities fail instead of falling back. Fork publishing stays
on the released dependency. For a consumer build, the publisher verifies the
installed immutable Git source inside the actual app image before pushing it;
native acceptance uses that same image, rather than only a temporary probe image.
Producer acceptance does not authorize substituting local Core in a consumer
deployment.

## Delivery

Follow [CI policy](ci-policy.md): fast automatic checks on every PR, full native
acceptance automatically for sensitive/unknown changes and on demand for
reviewed allowlisted presentation changes. Release, canonical publication and
production deployment always require full native acceptance. The versioned proof
keeps fast merge eligibility separate from native/image acceptance. Use full
immutable SHAs with `scripts/verify-promotion.py`; old or partial checks cannot
validate a new source.

No unsolicited reviewer assignment or mandatory human approval is imposed by
C0. Review the exact diff/results, then enable GitHub auto-merge with
`gh pr merge <number> --auto --merge --match-head-commit <full-head-sha>`.
The strict up-to-date Actions-owned gate remains mandatory; no admin bypass or
force push is allowed. Preserve frozen source commits and full acceptance runs.
Production update/import still needs separate live authorization and the
supported backup/preservation/client/restart/journal checks. Documentation-only
images do not replace accepted runtime images.

The existing interactive Playwright and container CPU-quota waivers remain in force; all automated native browsers and other security/resource bounds remain required. Public docs/artifacts use example identities, and raw credentials, failed traces and private fixtures stay outside Git. See [release readiness](release-readiness.md) for the distinction between documentation/plugin acceptance and a stable software release.

## Full-document Playwright acceptance

The headless document suite belongs to full acceptance; fast PR feedback uses
unit/controller/template/syntax checks without a database or browser. The older interactive Playwright waiver
does not exempt this suite. Use the producer-development environment above and
a disposable PostgreSQL/pgvector account with CREATE/DROP DATABASE authority:

```sh
.venv/bin/python -m pip install -r tests/e2e/requirements.txt
.venv/bin/python -m playwright install --with-deps chromium
.venv/bin/python -m pytest -q --tb=short -rA tests/e2e
```

`CZERO_TEST_DATABASE_URL` must already select the disposable server. Each browser
case creates/drops its own database, serves the genuine app over loopback HTTPS,
uses the existing signed test SSO provider and starts the actual standalone
worker. It uses real REST/MCP publication, immutable receipts and Chromium DOM
assertions. Missing browser/backend dependencies fail rather than skip. No live
instance is contacted. On Ubuntu 26.04, the executed local run used
`PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64` during browser installation;
CI uses Ubuntu 24.04 directly.

Failure screenshots and sanitized action/DOM traces go to
`CZERO_BROWSER_ARTIFACTS` (or the private pytest temp directory). Network events
and response resources are excluded from exported traces because they may hold
cookies/CSRF/OAuth data. Raw traces, keys and tokens stay private and are removed
with disposable fixtures. See [full-document contracts](full-documents.md).

## Build an application on C0

### 1. Fork and choose your application

Fork with GitHub's Fork button, or with the GitHub CLI:

```sh
gh repo fork Stell0/ns8-czero --clone
cd ns8-czero
git fetch upstream main
git worktree add -b feat/my-knowledge-application ../my-knowledge-application upstream/main
cd ../my-knowledge-application
```

The CLI sets up the original repository as `upstream`; if you cloned a fork manually, add and verify that remote first. Start from the latest original C0 main, preserving existing fork work in its own branches.

Decide who will use the application, what they need to remember, which records it needs and which spaces/permissions separate their work. For example: a support knowledge base, a research memory or a product operations assistant.

### 2. Give your coding agent the repository instructions

Start Codex, Claude Code or your preferred coding agent in the checkout. Give it a concrete request:

> Read AGENTS.md, README.md and PLAN.md. Use the C0 feature workflow to add a support knowledge application. Keep reusable authorization and knowledge behavior in Core; put our customer-specific UI and workflow in the application. Propose the data model, implement the agreed change, and verify it using a disposable database.

The [development guide](development.md) supplies installation and test commands. The agent instructions and local skills explain which layer to change and how to build, test and deliver it.

### 3. Extend the right layer

| Location | What belongs there |
| --- | --- |
| `packages/czero-core` | Reusable Python domain services, authorization, migrations and knowledge contracts |
| `app` | Your web UI, HTTP/MCP adapters and application-specific behavior using Core services |
| `imageroot` and `ui` | NS8 lifecycle/configuration/backup and native administration settings |
| `plugins/c0-knowledge` | End-user skills and instance-bound package templates |
| `.agents/skills` and `docs` | Instructions for coding agents, contributors and operators |

Use the released Core dependency and frozen lock by default. Change Core deliberately when behavior is reusable; a fork-specific screen or workflow does not automatically require a Core change. If you need only the reusable library, the [standalone consumer example](../examples/fork/README.md) demonstrates a smaller starting point; it is a development fixture, not a configured NS8 application.

### 4. Build, test and publish your own application

Choose your own module identity and container image namespace before publishing. Keep native labels, image references, lifecycle paths and CI permissions consistent. A fork publishes its own images; it must not publish the template's registry tags or replace upstream Core releases.

Run the required checks on the latest original C0 base and candidate and add regression tests for the changed behavior. Every PR gets fast automatic checks. Installation, container, migration, authentication, dependency and other sensitive/unknown changes also run Debian/Rocky native acceptance automatically. Reviewed presentation-only changes can request native tests on demand. Git-only documentation retains its explicit lightweight checks. The same risk policy applies to internal and external contributions; database skips are not a pass. See [CI policy](ci-policy.md).

C0 permits agent review and automatic regular merges after the current-source C0 merge gate and required checks pass, without mandatory human approval. Strict branch protection remains. Full native acceptance is still required before releases, canonical publication and production deployment; a fast UI merge is not deployment proof. Coordinate privileged registry checks on an authorized upstream branch without copying credentials into fork secrets.

Install the maintained [NethServer development skills](https://github.com/NethServer/agents) when working on module packaging, containers, deployment or releases. They complement C0's repository skills.

### 5. Keep your fork maintainable

Fetch original C0 main regularly and keep development changes rebased on it. Resolve conflicts and rerun your feature tests as well as the base suite after each upgrade. Preserve frozen/deployed candidates; a rebase that rewrites one requires a new candidate and fresh acceptance.

Review Core dependency updates and managed infrastructure proposals through `c0-upstream.json` and `scripts/sync-upstream.py`. The updater preserves customized files for review rather than overwriting them. Use `c0-upgrade-from-upstream` for upgrades and `c0-contribute-upstream` for reusable contributions. When your improvement can benefit the C0 base, open a focused upstream PR using `c0-contribute-upstream` and the installed `nethserver-pr` skill. Keep application branding, private deployment information and unfinished work separate from those contributions. Update the Codex-facing tool catalog, plugin/skills and documentation alongside behavior changes; verify the connection after upgrading.


## Repository documentation checks

Run the existing offline link/anchor checks and their regression tests:

```sh
python scripts/documentation.py
python -m pytest -q tests/unit/test_documentation.py
```

The maintained guide list includes the BYOA, LLM Wiki, maintenance, architecture and audit guides. For the complete Markdown inventory, reuse the same validator:

```sh
python - <<'PYDOC'
import subprocess
from pathlib import Path
import sys
sys.path.insert(0, 'scripts')
from documentation import check
tracked = subprocess.check_output(['git', 'ls-files', '-z'], text=True).split('\0')
paths = [p for p in tracked if p.endswith('.md') and Path(p).is_file()]
print(check(paths), 'local links checked')
PYDOC
```

Review fenced commands against their actual CLI/schema and parse/render Mermaid blocks with Mermaid before publishing diagram changes. Do not execute install, deployment, external model or schedule activation examples just to check their syntax. Historical frozen protocols and synthetic fixture text retain their stated generation; current user guides link them as evidence rather than setup instructions.
