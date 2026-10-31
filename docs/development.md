# Develop and maintain C0

## Layers and instructions

Read the root [AGENTS instructions](../AGENTS.md), [current plan](../PLAN.md) and the relevant repository skill. `packages/czero-core` owns reusable domain operations, authorization and migrations. `app` owns HTTP/MCP transport and the reference UI. Native lifecycle/configuration/backup belongs in numbered `imageroot` scripts; NS8 Settings uses Vue 2 and Ns components.

Install the maintained [NethServer skills](https://github.com/NethServer/agents) for module, container, administrative, commit, PR and release tasks. Do not copy those manuals into this repository. The repository's skills route application feature, Core, upstream contribution, fork upgrade and measured tool-evaluation work. End-user plugin skills live separately and do not ship in runtime images.

Use the active dependency manifests and `app/uv.lock` for current versions. The independently published Core README retains generation-specific historical examples; its old source tags/ranges are not the current app's dependency selection. Never edit or replace published Core artifacts as part of a documentation cleanup.

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
node --test tests/ui/*.cjs
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

## Delivery

Follow [CI policy](ci-policy.md): scoped feedback for draft runtime work, full exact-source acceptance for ready runtime PRs, actual native/privacy/scan artifacts and the named merge gate. Use `scripts/verify-promotion.py` with full immutable SHAs; passing a short hash or an old successful head is insufficient.

No unsolicited reviewer assignment. Another developer reviews before merge; regular merges preserve tested source commits. Runtime milestones normally require the supported dedicated-instance checks. The latest-only crawler task explicitly authorizes disposable acceptance only; production upgrade and import require separate operator authorization. Preserve native CI installation/upgrade and privacy checks. Documentation-only images do not replace accepted runtime images.

The existing interactive Playwright and container CPU-quota waivers remain in force; all automated native browsers and other security/resource bounds remain required. Public docs/artifacts use example identities, and raw credentials, failed traces and private fixtures stay outside Git. See [release readiness](release-readiness.md) for the distinction between documentation/plugin acceptance and a stable software release.

## Full-document Playwright acceptance

The headless document suite is mandatory for runtime PRs in the local validation
workflow, including scoped feedback. The older interactive Playwright waiver
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
