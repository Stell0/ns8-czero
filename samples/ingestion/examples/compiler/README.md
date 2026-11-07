# External knowledge compiler runner

This POSIX reference host runs outside C0. It invokes an external model and uses
C0's existing coordination, validation, publication and verification APIs. Nothing
in this directory installs or activates a schedule, enables policy, initializes
a project or changes a deployed Core dependency. Start with a disposable space.

## Install and bind

Use Python3.12–3.14 and the frozen ingestion/client package. Basic compilation
uses the external helpers already shipped by independently released Core0.42.
The new weekly selected-page reservation requires a server advertising that input
(Core0.45 producer). An older server reports the limitation without inventing
model usage. Nothing here publishes a Core release or changes C0's consumer lock.
Install into a dedicated external environment from the reviewed checkout:

```sh
uv venv /opt/c0-compiler
uv pip install --python /opt/c0-compiler/bin/python 'czero-core @ git+https://github.com/Stell0/ns8-czero.git@core-v0.44.0#subdirectory=packages/czero-core' ./samples/ingestion
/opt/c0-compiler/bin/c0-compile --help
npm install --prefix /opt/c0-compiler/agent @openai/codex@0.166.0
/opt/c0-compiler/agent/node_modules/.bin/codex --version
```

The runner checks actual Codex CLI0.166.0 and explicitly selects gpt-6.1-sol
with low reasoning effort for these bounded source-backed tasks.
The adapter version is pinned; that model ID is not a claim of immutable model
weights. Provider snapshot/quality reproducibility remains a separate measurement.
The model owns its existing Codex login, distinct from C0's API key. Configure a
private dedicated host login, without copying credentials into C0 or prompts:

```sh
CODEX_HOME=/srv/c0-compiler/codex /opt/c0-compiler/agent/node_modules/.bin/codex login
```

Run this as the dedicated account after creating its0700 directories:

```sh
install -d -m 0700 /srv/c0-compiler /srv/c0-compiler/state /srv/c0-compiler/codex
```

Run the login command as that account. Follow the
[official non-interactive guide](https://learn.chatgpt.com/docs/non-interactive-mode).
Verify this exact host can retain/renew the login; interactive sign-in alone is
not scheduled acceptance. Producer tests additionally build/install a local
Core0.45 wheel explicitly; no unpublished artifact is substituted in C0 itself.

Create a dedicated unprivileged host account `c0compiler`. Create its private job
directory `/srv/c0-compiler` mode0700, owned by that account. Copy config.json
there mode0600, then replace the synthetic URL/account/space/name with independently
verified bindings. Use the selected space's policy timezone and desired local
times. The default adapter is Codex; it needs no provider API-key file. An optional
Responses adapter uses adapter=responses, a verified explicit model snapshot such
as [gpt-5.4-2026-03-05](https://developers.openai.com/api/docs/models/gpt-5.4), and
model_key_file. Its real-key acceptance must be reported separately from Codex.
No key or source body enters prompts, command arguments or checked-in files.

Download/install the current instance skill or plugin from Use with AI. Copy its
trusted `references/compiler.md` to `/srv/c0-compiler/compiler.md` mode0600.
The runner loads that protocol, not a duplicate private prompt or source command.
Create a dedicated Read+Write key in C0 Account scoped only to the selected space
and current Editor account. Save it using a secret manager/editor to c0.key;
only for Responses save the provider key to model.key. Secret files must be0600 in the0700
directory. Do not paste credentials into a shell command, environment assignment,
chat, URL or log. No Admin key, scope expansion or interactive auth fallback.
For systemd set c0_key_file to `credential:c0-key`; the service uses LoadCredential.
For Responses add a reviewed LoadCredential=model-key drop-in and set
model_key_file to `credential:model-key`. Cron uses absolute secret-file paths.

## Initial check and bounded executions

Run as the dedicated account with its explicit installed paths and login home
(the following values are paths, not credentials):

```sh
export CODEX_HOME=/srv/c0-compiler/codex
export PATH=/opt/c0-compiler/agent/node_modules/.bin:/opt/c0-compiler/bin:/usr/local/bin:/usr/bin:/bin
/opt/c0-compiler/bin/c0-compile dry-run --config /srv/c0-compiler/config.json
/opt/c0-compiler/bin/c0-compile status --config /srv/c0-compiler/config.json
/opt/c0-compiler/bin/c0-compile bootstrap --config /srv/c0-compiler/config.json --apply
/opt/c0-compiler/bin/c0-compile daily --config /srv/c0-compiler/config.json --apply
/opt/c0-compiler/bin/c0-compile weekly --config /srv/c0-compiler/config.json --apply
/opt/c0-compiler/bin/c0-compile recover --config /srv/c0-compiler/config.json
```

Dry-run is read-only and makes no provider call. It verifies identity, exact space,
actual scopes/tools and current policy; a disabled policy remains disabled.
Execution with --apply authorizes bounded coordination/model work. Publication
still requires the current automatic-supported policy and eligible validated plan.
Queue-only/uncertain/contradictory/duplicate/authored updates stay held; the runner
never fabricates an approval. Confirm the enabled policy separately with its
operator before using --apply. Do not use a production space for initial tests.

Each invocation processes at most one leased task and one weekly selected page,
within the configured one-to-four model calls, input/output and timeout caps and
stricter C0 budgets. Codex does not expose a per-request output-token flag:
max_output_tokens applies only to Responses. Each Codex invocation conservatively
reserves1,200,000 tokens under both applicable server windows; insufficient policy
allowance stops it before inference. The default small policy therefore holds
Codex work until an operator explicitly chooses adequate model allowances. Do not
raise them automatically. The fixed custom OpenAI-auth provider disables HTTP and
stream retries; the adapter accepts exactly one toolless completed turn per
invocation and a bounded result. Actual provider usage is recorded when available;
missing/uncertain usage retains the maximum charge. Wall-clock cancellation is an
outer bound, not an exactly-once provider promise. Source assessments queue canonical child tasks; subsequent
runs compile them through the same engine. Unchanged sources suppress inference.
Large originals stop for selective-context work; no truncated review claims
completeness. Weekly pages without current original dependencies stay blocked.
Configured projects require their existing workflow's active private lease file
via --project-lease-file. Their host controls occurrence/report phases; --tick
refuses configured projects, preventing duplicate schedulers.

Verify actual server run/task IDs, current Wiki revisions/hashes, original exact
citations and dependencies through the same C0 connection. The JSON result reports
bounded progress, model calls and partial coverage. Complete refers to this bounded
run only. Use status for current task/source counts and saved local identities.
Exit0 means a successful check, completed bounded run or no due occurrence;
exit2 means disabled/deferred/review/reconciliation/partial work; exit1 means a
failure or uncertain outcome. No provider cost estimate is invented; use recorded
server/provider token usage and the provider's actual billing receipt.

## Cron and systemd

These are ordinary-space examples. Install only after separate schedule activation
authority and successful disposable execution. Preserve existing project tasks.
Use one scheduler per host/space, not both examples. A nonblocking local flock
prevents overlap; C0 fences/budgets coordinate other hosts. Nonzero results remain
visible and are not hidden with an automatic success status or blind shell retry.

Example crontab for the dedicated account (review actual installed paths first):

```cron
PATH=/opt/c0-compiler/agent/node_modules/.bin:/opt/c0-compiler/bin:/usr/local/bin:/usr/bin:/bin
CODEX_HOME=/srv/c0-compiler/codex
*/5 * * * * /opt/c0-compiler/bin/c0-compile daily --config /srv/c0-compiler/config.json --apply --tick
2-59/5 * * * * /opt/c0-compiler/bin/c0-compile weekly --config /srv/c0-compiler/config.json --apply --tick
```

The frequent tick works regardless of cron's host timezone; the runner decides due
occurrences using the configured IANA zone, not the cron clock's local hour. Copy
the supplied service template and timers to the host's system unit directory only
when activation is explicitly authorized. Inspect with systemd-analyze verify and
systemd-analyze calendar before enabling. Both timers explicitly tick in UTC and
Persistent=true catches missed wakeups; the runner enforces the selected local
calendar. It uses Core's existing occurrence algorithm: spring gaps shift by the
gap, fall folds choose the first occurrence and one logical local date prevents
duplicates. Missed ticks coalesce to the latest due occurrence. Compiler keys use
the current policy-local date rather than fabricated historical dates. Incomplete
runs retain their C0 identity/budgets and recover without claiming missed coverage.

Observe actual due execution with systemctl status/journalctl and independent C0
readback. Saved unit files, a timer's next time, fake clocks or manual invocations
do not prove an unattended provider run. Journals print sanitized codes/metadata,
not source/model response bodies, auth headers or arbitrary exceptions.

## Failures and recovery

Keep the0700 state directory and0600 atomic journal/lock. Intent keys/fingerprints
are saved before writes; model request IDs before inference; actual response IDs
and usage before the return checkpoint. No full source, prompt, answer or generated
page body is mirrored in local state. A pending/started operation blocks automatic
replay. Run recover (read-only), inspect the actual C0 run/tasks and provider receipt,
then reconcile using current actor/lease/fence and matching request IDs. Known
returned provider receipts and applied-pending-verification tasks can be recovered
with `recover --apply`; unknown provider outcomes remain blocked. Never delete a
journal, reset budgets or rename a binding to escape uncertainty. An interruption
after a known returned call may require a new explicitly budgeted analysis because
transient model content is not retained. No exactly-once provider promise is made.

Expired/revoked keys, denied roles/scopes, changed policy/timezone/manifest or
account/space mismatches stop work without fallback. Rotate a key through Account,
update its private file, test dry-run, then revoke its predecessor. Configuration
hash changes require reviewing/preserving the prior journal and starting an
explicit successor private state directory; server budgets never reset with it.

M5 records installed mock/SQL tests and real-provider/host acceptance separately in
[the milestone](../../../../docs/knowledge-compilation/M5.md). A missing credential
or unavailable scheduling host leaves that acceptance unverified. M6 owns real
retrieval-quality comparisons; this runner does not claim measured improvements.
