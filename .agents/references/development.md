# C0 development reference

<a id="c0-fork-development-reference"></a>

Read the fork's own README, AGENTS, PLAN, dependency manifests and CI workflow before choosing commands or versions. The [upstream development guide](https://github.com/Stell0/ns8-czero/blob/main/docs/development.md) describes the reference application's layout; a standalone Core consumer can have a different layout and test command.

`packages/czero-core` is the independently distributable library in the upstream producer. A fork normally consumes an immutable `core-v<version>` Git tag, the `packages/czero-core` subdirectory and a committed `uv.lock`. Use its declared compatibility range. A local Core override is explicit producer development, never an automatic fallback. Verify fresh PostgreSQL migrations and external wheel/archive installs for library changes; publish a new immutable library release before final consumer acceptance.

Keep application customization, branding, schemas and deployment identities in the fork. The explicit `c0-upstream.json` registry controls infrastructure proposals; new dependencies/references require registration. Trusted updater preview is read-only; apply preserves modified files and records exact unresolved comparison baselines. Review semantic compatibility separately. Do not execute downloaded upstream code while inspecting a proposal.

Use a disposable PostgreSQL/pgvector database for tests; skipped database cases do not establish success. Run the fork's focused checks, then its required complete acceptance. Never share mutable databases across parallel jobs. NS8 runtime changes need exact-source image/native checks, genuine frozen predecessor updates and clean restore. Library-only consumers retain their own narrower CI. Use the current validation entry point rather than historical publisher-dispatch commands.

NethServer lifecycle, container, administrative, commit, PR and release conventions come from the installed [NethServer skills](https://github.com/NethServer/agents). Do not copy those manuals into the fork. Keep credentials and raw private traces out of Git. A managed source URL grants no permission to publish to another repository. Preserve unfinished work in separate worktrees and follow the target project's explicit review/merge policy and require an authorized live target before deployment. C0 permits agent review and protected automatic regular merges without mandatory human approval; full native proof remains required for releases and production deployment.

## Implementation practices

Apply these practices when changing code in the reference application or a fork.
Running an existing ingestion, maintenance or evaluation workflow does not itself
require code changes or the development test suite.

- **Keep the change focused.** Inspect existing services and nearby patterns first.
  Implement the smallest complete fix; introduce an abstraction only for a concrete
  need. Keep unrelated refactoring, formatting and speculative options out of the diff.
- **Trace affected contracts.** Before changing a function, type or schema, inspect
  callers, exports, HTTP/MCP bindings, fixtures and documentation. Update affected
  consumers together and preserve compatibility where promised. Reuse existing
  typed records and validation at trust boundaries.
- **Test behavior.** Reproduce a bug before fixing it when practical, then exercise
  observable outcomes and relevant denial, boundary and recovery cases. Use real
  PostgreSQL for transaction/concurrency contracts; mock only appropriate external
  boundaries. Avoid tests that merely reproduce implementation branches or wording.
  Run the checks selected by the repository's CI policy.
- **Preserve error semantics.** Use existing domain errors and transport mappings.
  Catch failures where they can be handled; propagate other failures with useful
  context. Do not turn errors into empty results, success or unadvertised fallback.
  Preserve cancellation and cleanup when moving code.
- **Bound external work.** Use existing timeout, size and concurrency controls.
  Retry only appropriate transient failures with bounded attempts and a total
  deadline, using the established backoff policy. Retried writes must be replay-safe;
  reconcile uncertain outcomes first. Do not sleep or perform avoidable network I/O
  while holding database locks. Preserve post-I/O authority checks.
- **Justify dependencies.** Prefer the standard library or an existing dependency
  when it satisfies the need. For additions, assess maintenance, security, license
  and runtime impact; update the relevant manifest/lock and verify installation.
  Keep producer-development and released-consumer dependency identities distinct.
- **Keep diagnostics useful and private.** Reuse existing error categories and
  correlation IDs. Do not log credentials, tokens, source bodies or private queries,
  including through raw exception messages. Check affected error-path diagnostics;
  empty logs alone do not establish privacy.
