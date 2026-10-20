# Reproducible tool-guidance evaluations

This development-only harness tests C0 through actual authenticated MCP operations
and disposable PostgreSQL state. It is separate from public CI, which exercises
its fixtures, protocol boundaries and grader without model calls or credentials.
It never connects to the installed application.

Use a Python 3.12 environment with the checked-out Core, `app[test]` and the
repository's test dependencies. The chosen runner is `codex-cli 0.163.0`, using
normal local Codex authentication. Keep model `gpt-6-astra`, reasoning `high`,
corpus and driver hashes fixed when comparing runs. No API key is copied into
the harness. A loopback PostgreSQL administrator must be able to create and drop
fresh databases. Supply its URL through `CZERO_EVAL_DATABASE_URL`, never through
a model prompt. The random `czero_eval_*` database created for each case is
removed in `finally`; no supplied database is cleared or migrated.

```sh
python scripts/evaluate-tools.py --output /tmp/private-c0-eval/run-unique
python scripts/evaluate-tools.py --output /tmp/private-c0-eval/extended-unique \
  --cases queued-evidence uncertain-replay exact-version changed-verification \
  binary-upload missing-evidence current-profile protected-denial
```

The default runs the initial eight cases. A case has a 180-second wall limit and
16-call limit. Each session has an empty read-only workspace, fresh app-server
process/state, no shell, browser, web, apps, delegation, other configured MCP
servers, plugins, memories or project instructions. The parent owns synthetic
credentials, fixture setup, actual MCP forwarding and grading. Other tools or
server startups invalidate a run. Output directories must be new and private;
failed artifacts are retained. Run this explicit model suite only with operator
authorization. Do not put saved Codex credentials or model runs into public CI.

The experimental app-server driver eagerly supplies actual discovered tool names,
descriptions and input schemas. A disclosed client projection supplies the actual
standard annotations and actual-scope capability guidance in the prompt because
dynamic functions have no annotation field. Calls execute through the actual
SDK/C0 server. It does not simulate native annotation-driven confirmation.
This boundary does not exercise native Codex MCP discovery, safety annotation
interpretation or a client's confirmation UI. Installed Codex's native discovery
failed the recorded preflight before any C0 call; this adapter is a disclosed
route around that runner problem, not proof that native discovery works.
Current/legacy/raw protocol tests and actual ChatGPT acceptance remain separate.

The public corpus/rubric is `tests/evaluation/corpus.py`; evaluated sessions never
receive that file or expected answers. Freeze it before baseline/candidate
measurements. Use the same harness files in both arms, with each application's
own actual catalog, server instructions and actual-scope capability guidance.
Record the application commit, dirty flag, catalog/prompt/instruction/corpus/
driver hashes, requested/reported model metadata, token usage and elapsed time.
Do not claim an immutable backend snapshot when one is not reported.

`calls.json` contains parent-observed real results. `state.json` preserves before/
after rows, fixture effects and ground truth. `grade.json` checks state, actual
calls, immutable citations and prohibited effects. Conflict injection uses a real
second writer; uncertain-reply injection hides a real committed create or create-only upsert response; queued
evidence uses the real extraction worker. These effects are explicitly recorded.
A final answer cannot excuse an extra write. All critical invariants and task
assertions must pass. Repeat critical cases from `CRITICAL` to measure variance;
retain every failed result and distinguish runner failures from quality failures.
Do not silently optimize prompts against hidden outcomes or rerun failures as
though the original passed. Baseline ceiling performance does not show improvement.

Review final prose against the task separately and record that review. State
assertions establish saved effects, not every nuance of answer quality. Publish
only sanitized aggregate measurements and hashes; keep raw RPC, credentials,
synthetic identities and failed evidence outside Git. Actual ChatGPT acceptance
is required by the milestone and cannot be inferred from this harness.

Rubric version 2 covers both valid Wiki creation routes for lost-reply injection.
A recorded version-1 baseline repeat used create-only upsert and received no
injected fault. Preserve that invalid fixture trial separately; do not count it
as a model failure or a candidate improvement. The corrected prompt quotes the
requested saved sentence explicitly; grading also checks actual body/title and
stored synthetic provenance. Freeze and rerun both arms under
one corrected driver/rubric before claiming the final comparison.
