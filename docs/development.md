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

For repeatable external-source imports, read the [ingestion samples](../samples/ingestion/README.md)
and use c0-ingest-sources. Shared client-side helpers and adapters are development
tools, separate from Core/runtime packages. Save actual instance jobs and `.env`
under ignored `.local/ingestion`; publish only generic adapters, synthetic tests
and reusable source lessons after privacy review. The normal unit and integration
suites include their regressions; the example has its own frozen dependency lock.

Use trusted operation bindings, current-role checks inside Core transactions and existing lock ordering. Preserve original source/version/document/chunk identity, protected-space selection, expected revisions and replay receipts. A discovered tool or provider response does not confer authority. HTTP, ordinary SDK metadata and current/legacy MCP wire contracts all need verification when touched.

Static user pages use local assets, literal DOM rendering and generation/access-loss guards. Raw HTML from knowledge remains inactive. Ordinary readers must not initialize mutation controllers or load Admin membership lists. Copy current canonical instance URLs rather than constructing a deployment-specific hostname.

OAuth retains exact callback/resource guards, duplicate-field rejection, explicit consent, S256 and current native/membership/scope checks. Authorization ignores optional future fields only after duplicate/type/bound checks; token/revoke remain strict. CIMD uses only approved URL identities, bounded public-DNS-pinned verified HTTPS and post-I/O authority rechecks. Do not add TLS/DNS bypasses or derive roles from metadata.

For non-obvious implementation history, consult the [archived agent conventions](history/AGENTS.md) and [executed milestone evidence](history/PLAN.md), using the relevant topic rather than loading the entire archive for every task.

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
