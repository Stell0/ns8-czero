# M0 baseline and acceptance

Status: local verification is recorded below; required remote CI/native acceptance is
not yet established. Only M0 is implemented. Future compiler operations, tables,
model quality and unattended execution remain unimplemented and unmeasured.

## Source and safety boundary

Original remote verified as `git@github.com:Stell0/ns8-czero.git`, equivalent to
`https://github.com/Stell0/ns8-czero`. Fetched main and created an isolated branch
from `13f0b94a06e6a6f7d4b74e8ddd3fe6ae6eea6aac`; original checkout and existing
worktrees were preserved. App 0.59.0, Core 0.38.0, released consumer lock, schema
0032 and plugin 1.4.0 remain unchanged. M0 changes docs and synthetic tests only.

The existing requested protected documentation space was inspected through the
registered C0 connection: authenticated profile succeeded, selected-space lookup
confirmed Admin membership, and a three-document summary read succeeded. No
source bodies, tickets, real source IDs, credentials or private instance bindings
are included here. No project initialization/configuration, policy enablement,
knowledge mutation, import, schedule or deployment was performed. Capability
resource discovery was available, but its large serialized response was truncated
and could not be parsed completely; the advertised operation catalog and actual
successful space/document reads were inspected. Do not treat that as exhaustive
connector-contract verification or support for future compiler operations.

## Frozen inputs

The [synthetic fixture manifest](../../tests/fixtures/knowledge_compilation/manifest.json)
freezes five originals and a deterministic source-only response. Separate
[retrieval probes](../../tests/fixtures/knowledge_compilation/retrieval-baseline.json)
are public regression expectations, not a private/sealed quality benchmark.
The construction helper has no question parameter. No LLM/provider was called.

The existing semantic-layer validator and maintenance APIs are used unchanged.
Three derived Wiki pages, two entities, two contrary claims, a relationship and
an entity/page link are written only to disposable SQL fixtures, then read back
with exact original citations and unverified annotations. A second apply must
leave SQL event/receipt counts and revisions unchanged. Replacement must produce
410 for old support and stale annotations while preserving authored Wiki text.
These controls prove existing foundations, not future compilation policy or leases.

## Reproduction

Use the [development setup](../development.md) with a dedicated disposable
PostgreSQL/pgvector server. Tests need Create/Drop Database rights for owned paired
fixtures. Run sequentially; missing database configuration is not acceptance.
Select producer source explicitly with
`PYTHONPATH=packages/czero-core/src:app/src:samples/ingestion/src` and retain the
released consumer manifest/lock. Runtime code in base/candidate is identical.

Unchanged original-base selection:

```sh
python -m pytest -q tests/unit/test_agentic_retrieval_protocol.py \
  tests/integration/test_knowledge_bundle.py \
  tests/integration/test_project_maintenance.py \
  tests/integration/test_document_context.py tests/integration/test_api_keys.py
```

New M0 controls:

```sh
python -m pytest -q tests/unit/test_knowledge_compilation_contract.py \
  tests/integration/test_knowledge_compilation_baseline.py \
  -o junit_family=legacy --junitxml=/tmp/c0-knowledge-m0.xml
```

The executed 110-case candidate selection repeats both selections and adds
`tests/integration/test_agentic_retrieval.py`, `test_agent_downloads.py` and
`test_project_agents_http.py`. It includes the existing 101-document and large
multipart preservation controls and actual downloaded archives. Core/unit fast
checks and compiled-app controls run separately. CI-selected full/native checks
remain required. The new unit test invokes the existing Markdown
checker on this new documentation directory and fixture README; the root checker's
maintained list remains unchanged.

Local environment uses a task-owned loopback-only PostgreSQL container at the
CI-pinned `pgvector/pgvector` digest
`sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d`,
with separate baseline and candidate databases, plus a disposable test-runner
image containing English/Italian OCR and repository-pinned Python dependencies.
No shared mutable test database or installed runtime is used.

## Executed results

A first
host-environment run passed 78 cases and failed one OCR context test because
`/usr/bin/tesseract` was absent. The failed log/JUnit remain private. A first
container invocation lacked pytest and performed no tests. Neither is accepted
as a baseline. Container environment retries also exposed missing read-only Git
metadata and installed Core metadata (five, then three failed baseline cases);
package metadata builds needed disposable writable copies. These failures were
preserved and corrected in the test environment, without altering product code,
skipping cases or changing limits. The new relational fixture initially exhausted
the existing fixture's 32-grant cap by opening a grant for each read; it now uses
one real delegated connection for the complete episode. Its initial 9-pass/1-fail
result remains private; the corrected complete selection passes.

| Check | Actual local result |
| --- | --- |
| Pristine original main foundation selection | 79 passed, 49.37 seconds, no database skips; genuine OCR/backend and source metadata |
| Expanded candidate foundation/M0/retrieval/archive/project-package selection | 110 passed, 267.01 seconds, no database skips |
| New M0 unit and PostgreSQL/MCP controls | 10 passed, 21.96 seconds, no skips |
| Core and full unit selection | 1,418 passed, 32.66 seconds; one existing Authlib deprecation warning |
| Compiled application fast checks | 53 passed, 59.61 seconds |
| Existing native-settings Node controls | 27 passed; local interpreter smoke check, pinned CI remains authoritative |
| Frontend | Frozen-lock build on pinned Node 24.22.2 passes; existing bundle-size advisory retained |
| Documentation | 374 maintained links pass; new directory/fixture links checked by new unit case |
| Privacy/diff | Eleven intended text files scanned against private deployment/account denylist; no runtime/lock/schema/plugin changes, diff whitespace check passes |

The first schema-check invocation could not write the host Go cache; it was
rerun successfully with a task-owned temporary cache. No global configuration
was changed. The local Node smoke check used 25.8.1; the frontend build used
pinned 24.22.2 and CI retains its pinned-version gate.

Single local source-only observations, each N=1 (not P50/P95, production latency
or a model benchmark): `socket` returns zero sources in 0.4541 seconds; `7443`
returns its one expected source in 0.2224 seconds; Italian `certificato` returns
its one expected source in 0.2269 seconds. These timings include disposable
OAuth/MCP setup. The enriched mock arm is a persistence control, not a measured
LLM answer-quality improvement. SQL readback records three current Wiki pages/
revisions, two entities, two claims and one relationship, with twelve knowledge
events/receipts after relational publication. No monolithic index is created.
Model calls/tokens/cost for M0: zero; real model quality/cost remains unknown.

## Acceptance checklist

- [x] Exact latest original main isolated; original worktrees preserved.
- [x] Current APIs/schema/skills/packages, experimental layer and project contracts inspected.
- [x] SQL/authority/revision/fence/dedup/retention contracts and M0–M6 dependencies frozen.
- [x] Disabled defaults and external-agent responsibility selected; no runtime behavior changed.
- [x] Source-only fixture and separate regression questions frozen by hashes.
- [x] Unchanged original baseline and candidate selections pass without database skips.
- [x] New deterministic unit/PostgreSQL M0 controls pass, with actual SQL readback.
- [x] Existing package/archive, recovery and fast/documentation checks pass.
- [x] Complete diff reviewed for privacy, consistency, runtime/lock/schema preservation.
- [ ] Focused upstream PR and actual current-source C0 merge gate/selected full/native checks pass.
- [ ] M0 accepted before any M1 implementation. M1 remains unstarted in this session.

The [next implementation prompt](PLAN.md#next-codex-prompt) is for M1 only. Real
model/quality/coverage/cost measurement, new-table EXPLAIN, migrations, installed
compiler skill acceptance and actual unattended hosts belong to their listed
future milestones. No production improving-Wiki claim is made by M0.
