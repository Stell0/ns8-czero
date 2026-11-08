# Codebase review

Audit base: original `Stell0/ns8-czero` main `1db37f4` (8 November 2026).
Work is isolated from the operator checkout and all retained worktrees. This is a
repository-wide structural review with focused implementation audits, not proof
that every statement or every operational path is correct. Findings below are
restricted to inspected evidence; no P0 security defect is established.

## Scope and architecture

The tracked inventory contains 983 files. Reviewed entry points and contracts:

| Area | Production responsibility and reviewed boundaries |
| --- | --- |
| `packages/czero-core` | Independently distributed services, transaction authorization, 36 migrations, sources/current content, extraction, retrieval, projects and compilation |
| `app/src/czero_app` | FastAPI application, explicit operation registration, OAuth/MCP adapters, website serving, native worker entry points |
| `app/frontend` | Vue 3 website, account/space/generation query identities, replay identities, local Markdown worker; compiled assets served by Python |
| `ui`, `imageroot` | Separate Vue 2/Carbon NS8 configuration UI, numbered actions/events, systemd workers and backup/update lifecycle |
| `containers`, `build-images.sh` | Compiled website, Python runtime and separate PostgreSQL image; released dependency default versus explicit local producer |
| `samples/ingestion` | Installed external ingestion/project/compiler commands, private state, shared MCP client and atomic state functions |
| `scripts`, `.github` | Packaging, evaluations, explicit upstream synchronization, risk classification, source-bound merge/publication gates |
| `tests`, `benchmarks` | Unit, database, packaging, native browser/Robot and isolated retrieval evaluation fixtures |
| `plugins`, `.agents`, `docs`, `examples` | Runtime end-user packages, separate development instructions, operational contracts, registered fork infrastructure |

The consumer selects released Core 0.44; the checked-in producer is Core 0.45.
That separation is intentional. Do not "fix" the version difference or delete
compatibility routes, migrations, re-exports, recovery scripts or frozen evidence
based on textual reachability. Recent history includes M6 benchmark acceptance,
external compiler delivery and document BM25; their disabled defaults remain.
The application has 45 Python modules (6,477 lines), Core 110 including
migrations (17,870 lines), and external samples 45 (6,089 lines).
An AST scan of all tracked Python files found no identical function definitions
of ten or more lines. Near-duplication still needs behavioral comparison.

## Prioritized findings

### R1 — P2: transport initialization turns cancellation into an ordinary error

- Location: `samples/ingestion/src/c0_ingest/client.py`, `SDKTransport.__init__`.
- Evidence: its `except BaseException` cleans up the portal but then wraps
  `KeyboardInterrupt` and `SystemExit` as `C0Error`. All external commands share
  this transport. Cleanup is required; changing process-control semantics is not.
- Impact: interrupted startup may be reported as a recoverable authentication
  failure, defeating callers' interruption handling.
- Proposed solution: retain cleanup for every failure, translate only ordinary
  exceptions, and propagate process-control exceptions unchanged. Test startup
  failure and cancellation through the real blocking portal.
- Class/risk: safe reliability cleanup; low, no protocol/schema changes.
- Status: resolved; focused regression passes.

### R2 — P2: application shutdown can skip database disposal

- Location: `app/src/czero_app/main.py`, application lifespan finalizer.
- Evidence: `auth.oidc.close()` precedes `database.close()` in the same finally
  block. An exception in the former prevents the latter.
- Impact: owned connection pools remain undisposed on failed shutdown/startup.
- Solution: register both resources in the existing `AsyncExitStack`, preserving
  cleanup order and guaranteeing database cleanup. Exercise lifespan failure, not only mocked calls.
- Class/risk: moderate lifecycle refactoring; low, no request behavior changes.
- Status: resolved; focused regression passes.

### R3 — P2: unused names accumulate, but automated deletion is unsafe

- Location: runtime, sample commands and scripts; static audit recorded privately.
- Evidence: Ruff F401/F811/F821/F841 reports 46 candidates, no undefined names.
  `github_vault.state` deliberately re-exports seven shared functions; removing
  them would break callers. `_plan` parses a revision UUID for validation even
  though the local result is unused. OAuth token hashing also performs validation.
- Impact: noisy imports and misleading dead-code reports obscure real problems.
- Proposed solution: remove narrowly verified function-local unused imports and
  unused standard-library imports; retain public module attributes and validation.
- Class/risk: safe cleanup for selected names; wholesale autofix is unsafe.
- Status: resolved for 15 selected imports; broader export policy remains a recommendation.

### R4 — P2: worker documentation contradicts deployed composition

- Location: `app/src/czero_app/extraction_worker.py`, module docstring.
- Evidence: it claimed to be producer-only and absent from native timers, while
  `imageroot/systemd/user/czero-extraction.service` invokes this exact module and
  `czero-extraction.timer` installs its recurring wake.
- Impact: maintainers can incorrectly exclude a production entry point from
  operational review or remove it as experimental code.
- Solution: describe the actual bounded native extraction pool runner.
- Class/risk: safe documentation cleanup; no runtime behavior changes.
- Status: resolved; actual service/timer entry points traced, syntax unchanged.

### R5 — P2: broad catches need boundary-specific interpretation

- Location: parser subprocess programs, MCP adapters and external compiler CLI.
- Evidence: broad handlers intentionally replace arbitrary parser/provider/server
  text with fixed codes. Several wrap untrusted library execution, rather than
  application logic. Compiler output is deliberately payload-free.
- Impact: indiscriminate narrowing leaks private details or changes public errors;
  indiscriminate reuse can conceal programming errors inside trusted code.
- Proposed solution: retain privacy boundaries; add targeted fault-injection and
  private diagnostic practices when changing those components. No blanket removal.
- Class/risk: architectural recommendation, high privacy/compatibility risk.

### R6 — P2: local test completeness depends on explicit infrastructure

- Location: `docs/development.md`, Python database/browser/packaging suites.
- Evidence: missing disposable database authority produces skips; Python website
  cases require an actual compiled frontend. Fast CI intentionally omits database
  and browser fixtures; full/native gates are distinct and must remain so.
- Impact: a green partial local run can be mistaken for deployment acceptance.
- Proposed solution: report prerequisite failures separately and run full suites
  with disposable infrastructure; preserve strict CI and source-bound proofs.
- Class/risk: verification/documentation, low. Results below will distinguish
  environment failures, skips and tested behavior.

### R7 — P3: website check repeats TypeScript validation

- Location: `app/frontend/package.json`, `check` and `build` scripts.
- Evidence: `check` calls `type-check`, then `build` calls `vue-tsc --noEmit` again.
- Impact: repeated work in every fast/full build; magnitude not yet measured.
- Proposed solution: measure before changing orchestration. Keep standalone build
  type safety and avoid an extra public script merely to save an unmeasured cost.
- Class/risk: safe optimization recommendation; deferred without timing evidence.

## Rejected deletions and compatibility checks

Public Core imports and shared sample re-exports are not proven dead. Historical
migrations support genuine upgrades. NS8 global Vue plugins may be used through
registration/templates. Two frontend stacks serve different products and are not
competing implementations. The generic MCP 410 handler already preserves
`content_superseded` before domain mapping; a suspected compilation error mapping
issue was rejected after tracing the complete handler. A suspected duplicate
extraction configuration factory was also rejected: the main job registry
registers different source/embedding handlers, not this extraction pool. No new abstraction,
dependency, migration, scope, endpoint removal or automatic schedule is proposed.

## Validation and delivery

Baseline and candidate results, remaining limitations and change metrics will be
recorded here after execution. Full Debian/Rocky native acceptance remains required
by CI for runtime changes; local tests never substitute for it. No deployment,
Core publication, production mutation or release is authorized by this audit.

### Implementation boundaries

The cleanup leaves Core's package tree, all dependency manifests/locks, migrations,
registered tools, scopes and end-user plugin contents unchanged. Lifespan callbacks
retain the close order: MCP, metadata fetcher, identity client, database. No new
cleanup framework was introduced; the application already used AsyncExitStack.
The candidate regression exercises genuine auth/database application lifespan on
normal shutdown and failed startup, and the client cases use an actual AnyIO
blocking portal with fault injection. Both defects fail on unchanged runtime and
pass after the fix (14 focused cases).

Selected dead imports are function-local unused exceptions/UUID helpers and
unused typing/standard-library names in application, development commands and
scripts. Imported Core attributes and the seven `github_vault.state` re-exports
are retained. Static candidates fall from 46 to 31; F821/F811 remain clear.
There are no deleted files or dependencies. Low-risk documentation/import changes
reuse the existing suites instead of adding tests that merely inspect imports.

## Executed verification

All tests use synthetic/disposable data. No live instance is contacted. The
original baseline and cleanup candidate have different worktrees, virtual
environments and mutable test databases on one disposable PostgreSQL server.

| Check | Result |
| --- | --- |
| Original lifecycle fault-injection tests | Four expected failures: two cancellation cases, two failed identity cleanup cases |
| Candidate focused client/lifespan tests | 14 passed; final client-only repeat 12 passed |
| Website lint/format/typecheck/unit/build | Passed, 28 unit tests; existing bundle-size warning retained |
| Website Chromium interactions | 27 passed (39.6 seconds) |
| NS8 Vue 2 frozen Yarn install/build | Passed; existing formatting, dependency-data and bundle warnings retained |
| Native Node controller/probe tests | 28 passed before and after |
| Robot dry run | 21 passed before and after |
| Go schema patterns | Passed |
| Maintained documentation | 411 local links passed; review report checked separately |
| Python changed-file syntax and diff whitespace | Passed |
| Undefined/redefined Python names (F821/F811) | Passed across runtime, samples and scripts |
| Broad Python/PostgreSQL/packaging baseline and candidate | Running; final results pending |
| Python app/worker browser suite | Running with documented Ubuntu 24 compatibility override |
| Debian/Rocky native, image/license/privacy/scans and released-consumer acceptance | Pending upstream full CI; no local substitute claimed |

An initial run without correct prerequisites is retained separately: 55 failed,
1,719 passed, 1,126 skipped, 302 errors. It lacked compiled website assets, a
selected disposable database and a writable default temporary directory. It is
not evidence of 357 application defects. The corrected baseline rebuilds assets,
selects a dedicated database and directs temporary files into the worktree.
The host also lacks Tesseract; OCR/native requirements must be evaluated explicitly.
Python Playwright 1.58 rejects Ubuntu 26 without the documented compatibility
override. These environment issues were not hidden by changing test selections,
adding skips or weakening assertions.

## Change metrics and remaining work

Runtime/tooling source: 17 lines added, 31 removed (net -14). Behavioral regression
coverage: 65 lines added in two files, six parametrized new cases. Fifteen dead
imports removed; two lifecycle defects fixed; one stale production description
corrected. No files or dependencies removed. One existing resource owner replaces
split cleanup mechanisms. The report is tracked separately from these code counts.

R1–R4 are resolved in the candidate. R5 (P2, boundary-specific diagnostics), R6
(P2, complete acceptance) and R7 (P3, measured frontend check orchestration) remain
recommendations or verification work. The 31 retained static candidates are not
31 proven dead APIs. No P0/P1 finding or performance improvement is claimed.
The repository-wide structural review does not certify every line, production
upgrade or externally hosted assistant scheduling workflow.
