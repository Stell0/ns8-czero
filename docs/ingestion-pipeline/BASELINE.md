# M0 baseline evidence — 2 November 2026

M0 implements the first task in the
[approved plan](https://github.com/Stell0/ns8-czero/blob/7a737e89ada542a3a4f04f45185ff7e6b9a2c3d5/docs/ingestion-pipeline/PLAN.md).
Review [assembly, hash, lease and authorization contracts](CONTRACTS.md) before
starting M1. This is a documentation/tests candidate, not queued extraction or
deployment acceptance. The planning PR is [PR55](https://github.com/Stell0/ns8-czero/pull/55);
this milestone started independently from original main. PR55 subsequently
landed; the successor candidate uses main
`345564004d900560a1e737bbaa76c2f7824c3f5a`. Its complete base diff adds only
the plan and roadmap link. Runtime/package/lock/migration trees are identical.
The tested first candidate `1eb5de9` remains on a preserved local branch.

## Frozen inputs and environment

Verified original remote: `https://github.com/Stell0/ns8-czero.git`.
Initial tested main: `fe38990b7c74594e2a7f91dbbb23697e7d1f1793`;
refreshed PR base: `345564004d900560a1e737bbaa76c2f7824c3f5a`.
The source checkout was isolated; the original checkout and recovered worktrees
were preserved. Runtime Core/app/native/plugin paths have no modifications.
The app's Core tag/range/immutable lock and schema 0023 are unchanged.

Python 3.14.4; SQLAlchemy 2.1.4, Alembic 1.20.0, psycopg 3.3.6,
pypdf 6.20.1, python-docx 1.2.0, FastAPI 0.143.0 and MCP 2.3.0.
Producer source was explicitly selected through `PYTHONPATH`, with those pinned
dependencies in an existing environment. No consumer lock substitution occurred.
Tests used a newly created disposable PostgreSQL container, isolated from other
tasks, using the CI image
`pgvector/pgvector@sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d`.
Original and candidate runs used separate databases; no production instance,
credential, dataset, corpus rewrite or external provider was involved.

The [fixture manifest](../../tests/fixtures/evidence/pipeline/manifest.json)
records original and canonical body hashes/locations. Its deterministic generator
never invokes the production extractor to produce expected output. Fixture
regressions independently regenerate original bytes and compare every hash,
canonical text, location and chunk slice. Binary originals have explicit review
through this reproducible generator and parser/ZIP/PDF inspection; a binary
privacy-check finding is not treated as a text-scanner pass.

## Executed checks

| Check | Observed result |
| --- | --- |
| Existing extraction/source/text/worker/full-document/HTTP selection | 100 passed, 1 new test deselected, 197.73 seconds |
| New fixture controls | 11 passed, 3.24 seconds |
| New fixture + PostgreSQL + multipart HTTP/MCP controls | 14 passed, 11.04 seconds, no skips |
| Complete focused candidate selection | 114 passed, 171.02 seconds, no skips |
| Standard fast Python selection, two sequential groups | 407 Core/app + 926 unit = 1,333 passed, no skips; 42.62 + 16.07 seconds |
| Existing Node controllers | 211 passed; local Node 25.8.1 smoke check, pinned Node 24 remains CI's gate |
| Documentation and diff | 338 local links checked, including new docs; `git diff --check` passes |

The existing-test run selects the original 100 cases against unchanged runtime
code; it excludes only the new multipart case. The candidate regression selection
adds all new controls to those same suites. Final fast/CI results belong
to the milestone PR and must be read for its exact head, rather than inferred
from this earlier measurement.

One earlier environment installation and test attempt exhausted the filesystem
quota. The failed temporary environment/cache was removed; existing work and
failed logs were preserved. The restarted original selection above completed.
An initial combined collection exposed a duplicate unit/integration test-module
basename; unique module names fixed collection before the 14-case pass. Neither
failure was counted as acceptance or used to relax runtime/test limits.

The broader combined candidate and initial fast runs also exhausted the quota;
their logs and compressed synthetic failed-test artifacts remain outside Git.
The complete 114-case candidate result above was rerun sequentially after cleanup.
The first fast collection also lacked Robot Framework in the reused environment;
it was supplied in a separate temporary test-only target, without changing
repository dependencies or modifying the shared environment.
The final combined fast attempt passed 1,332 cases and hit quota while the
existing oversized-upload case wrote its 10 MiB control. Repeating the identical
fast selection in two groups, clearing only successful temporary files between
them, produced the 1,333 passes above. No cases or bounds were removed or weakened.

## Measured whole-document behavior

These are **single local observations**, not P50/P95, cold-cache controls, an old/new
comparison or production service levels. JUnit properties from the new integration
controls record raw seconds for repeatable inspection.

| Operation | Seconds | Scope |
| --- | --- | --- |
| Isolated 100-page full parse | 0.337665 | Genuine child parser, all 100 labelled page locations verified |
| Repeated full parse after injected lost result | 0.337090 | Same original, no reusable successful-page output |
| Retry worker tick | 0.395657 | Includes ordinary queued health job, parse and publication |
| Complete PDF read | 0.007758 | Core authorized full-body read after publication |
| Two-part external publication | 2.590880 | Existing publisher, real disposable HTTP/MCP/OAuth/Core/database path |
| Complete multipart read | 0.012920 | Authorized logical-parent read, exact Unicode body/hash, one browse entry |

The retry control injects `parser_timeout` **after** the first real full parse to
model a lost result deterministically; it does not claim to time a natural parser
timeout or a page-level failure. Both attempts return all 100 page locations
before the injected failure is applied. This proves repeated whole-document work,
not the future M2 pages-37/72 selective-retry gate.

An independent database connection during parsing fails to acquire both the
publication advisory lock and worker advisory lock. A second ordinary worker
returns zero while parsing; a queued health job remains queued when the first
tick is deliberately bounded to one extraction job. It completes after extraction
releases its lock. This is observed queue interference, not measured parallel
worker throughput or an authorization-performance claim.

On replacement failure, the previous complete body and exact citation remain
available, and candidate text is absent from search. Safe parser failure finishes
the generic job with a failed-source result. Explicit source retry advances
processing generation and reparses the whole original. Successful replacement
publishes the exact expected full hash/order, becomes searchable, and makes the
old exact citation return `content_superseded`. The retained original is unchanged.

The multipart control crosses the existing 128 KiB publication-part threshold.
The current publisher creates two receipts, verifies them and commits one complete
logical parent. The complete body and SHA-256 match the synthetic original. These
are external publication parts, not extraction tasks; no connector cursor or
receipt contract is changed.

Existing suites also exercise current source revisions/replays, access checks,
unchanged uploads, retirement, incomplete/corrupt multipart fail-closed behavior,
process death, ordinary queue rollback/recovery, full-document HTTP reads and
expired exact references. The new writer control rejects protocol-0 writes on
schema 0023 and permits protocol-1 writes after rollback. Proposed lease-table
writes and migrations cannot be claimed tested before M1 implements them.

## Reproduce

Use the [development environment](../development.md) and a dedicated disposable
PostgreSQL/pgvector URL, never a shared mutable test or production database.
Run selections sequentially. Export `CZERO_TEST_DATABASE_URL` privately; missing
database configuration produces skips and is not acceptance.

Original test selection (on the frozen original main or this tests-only candidate):

```sh
python -m pytest -q packages/czero-core/tests/test_extraction.py \
  tests/integration/test_sources.py tests/integration/test_source_text.py \
  tests/integration/test_job_worker.py tests/integration/test_full_documents.py \
  tests/integration/test_full_documents_http.py -k 'not ingestion_pipeline'
```

New controls with raw timing properties:

```sh
python -m pytest -q tests/unit/test_ingestion_pipeline_baseline.py \
  tests/integration/test_ingestion_pipeline_postgres.py \
  tests/integration/test_full_documents.py::test_ingestion_pipeline_m0_external_parts_are_not_extraction_units \
  -o junit_family=legacy --junitxml=/tmp/c0-ingestion-m0-measurements.xml
```

Complete focused candidate regression selection:

```sh
python -m pytest -q packages/czero-core/tests/test_extraction.py \
  tests/unit/test_ingestion_pipeline_baseline.py \
  tests/integration/test_ingestion_pipeline_postgres.py \
  tests/integration/test_sources.py tests/integration/test_source_text.py \
  tests/integration/test_job_worker.py tests/integration/test_full_documents.py \
  tests/integration/test_full_documents_http.py
```

Standard fast checks and documentation checks follow [CI policy](../ci-policy.md).
For the new documents also run `scripts/documentation.py`'s `check` on this
directory's Markdown and the fixture README, because the default maintained-file
list is explicit. Runtime/parser/schema code is unchanged; genuine browser,
worker-pool, migration, native, release and deployment acceptance are not
established by these local measurements. Preserve all existing waivers and
frozen native runs. M1/M2 criteria are specified in [CONTRACTS](CONTRACTS.md).
