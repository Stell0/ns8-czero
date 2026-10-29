# C0 ingestion samples

> Latest-only semantics replace the previous content-history guarantee. Each logical source document and Wiki article retains one current complete generation. Old exact citations and superseded mutation replays return `content_superseded` (410); stable links open current content. Back up before the destructive upgrade and run the [read-only preflight](../../docs/latest-only-migration.md).

Use these scripts to collect external evidence, update one selected C0 space and
verify the saved data. The first adapter is a complete public GitHub project,
contributor and documentation pipeline. Shared Python helpers support other
sources without copying authentication, MCP or state-handling code.

These are external development tools. They are not installed in C0 containers,
do not access its database directly and do not install a scheduler.

## Public code, private jobs

The `c0_ingest` package contains the official MCP SDK adapter, dedicated OAuth,
account/space checks, atomic state and original-text submission/readback.
`github_vault` contains GitHub discovery, metrics, snapshots and reconciliation.
The four scripts retain separate inspection, scraping, updating and pipeline
entry points. The [tests](../../tests/unit/ingestion/test_ingestion_core.py) use synthetic data; the
integration suite also exercises actual disposable C0/PostgreSQL operations.

Put each real job in ignored `.local/ingestion/<job>/` at your checkout root, or
in a private directory outside Git. The initializer refuses an unignored Git
directory and never overwrites an existing job. A job contains:

```text
.env                   # instance URL, expected account, space and OAuth client
run.py                 # thin, runnable update entry point
config/source.toml     # organization/seed/window/budget settings
oauth.json             # dedicated credentials, created by login; never published
NOTES.md               # private mappings, recovery and actual results
data/                  # immutable snapshots, checkpoints, receipts and reports
```

Build images from a clean isolated worktree, keeping private jobs outside that
build checkout. Git ignore rules do not filter container build contexts or bind
mounts; the existing UI builder mounts its checkout.

## Install and initialize

Use Python 3.12–3.14 on Linux or macOS; locking requires POSIX `fcntl`. From the
C0 checkout root, install into a virtual environment, never the server runtime:

```sh
python3 -m venv .venv-ingestion
.venv-ingestion/bin/pip install ./samples/ingestion
mkdir -p .local/ingestion
.venv-ingestion/bin/c0-ingest init .local/ingestion/github-projects
```

Alternatively, `uv sync --project samples/ingestion --frozen` uses the supplied
dependency lock. Private wrappers must run with the environment containing the
package. Source entry points also work with an explicit private `--config` path.

Edit the job's `.env` as literal `KEY=value` data. It is not shell code; do not
`source` it. Set your hostname-root HTTPS `/mcp` URL, expected account nickname,
exact protected space ID/name and dedicated OAuth client ID. Keep mode 0600 on
the file and mode 0700 on the job directory. No endpoint or account defaults to
the maintainer's deployment. Configure organizations, optional seed CSV paths,
pilot repositories, UTC windows and request/document limits in the TOML file.
Paths in TOML are relative to the private job and may not escape it.

GitHub authentication uses `GITHUB_TOKEN`, `GH_TOKEN` or the existing authenticated
`gh` command. GitHub credentials are never saved in snapshots. This adapter
collects public repositories only, even when the token can read private ones.

## Use a dedicated OAuth connection

An administrator registers a **new public client** in C0 Advanced administration:
exact callback `http://127.0.0.1:43220/callback/c0-ingestion`, authentication
method `none`, and allowed scopes `c0:read c0:write`. Put its client ID in the
private `.env`. Each job needs its own connection/store. Preserve existing Codex
and ChatGPT registrations and credentials. C0 does not support unrestricted
dynamic registration.

```sh
.venv-ingestion/bin/python .local/ingestion/github-projects/run.py login
.venv-ingestion/bin/python .local/ingestion/github-projects/run.py bind-account
.venv-ingestion/bin/python .local/ingestion/github-projects/run.py inspect
```

Login opens the local browser, uses PKCE/state and a bounded loopback callback,
and never prints the authorization URL. Sign in as the expected account and
explicitly select **Keep this connection working in the background**. Binding
checks the configured nickname and pins the returned opaque account ID in `.env`;
later renames require deliberate configuration updates, not a new account binding.
Inspection verifies both identity and capabilities with zero content writes.

Normal commands never open a browser. A separate private credential store is
bound to this endpoint, issuer, client and scope set. Runs and refresh rotation
are locked; replacement credentials are persisted before reuse. An interrupted
or uncertain rotation leaves a marker that blocks automatic replay. Resolve it
through C0 Account connections and fresh `login`, retaining the failed evidence.
Use the job's `disconnect` command to revoke only its connection before removing
credentials or changing scopes. Never delete an uncertainty marker to force a retry.

### One-time Admin bootstrap

Existing compatible schemas and a granted protected space need no bootstrap.
For a fresh instance, create a separate temporary private bootstrap job/client
approved for `c0:read c0:write c0:admin`. Set that job's `C0_SCOPES` accordingly,
log in as the Admin, bind the account, then run `run.py bootstrap --apply`.
Bootstrap creates a missing private
space and the four `github_*` schemas, preserving all existing compatible schemas.
It refuses ambiguity or incompatible definitions and never overwrites them.

After bootstrap, run its `disconnect` command and put the resulting space ID in
the normal ingestion job. Keep that job's separate Read/Write client and login.
Administrator approval and new consent are separate; refresh cannot add scope.
Ordinary sync never creates spaces or global schemas and needs an Editor or Admin
grant on the exact protected target. See [workspace access](https://github.com/Stell0/ns8-czero/blob/main/docs/workspace-access.md).

## Scrape, inspect and update

Start with configured, small pilot bounds. These commands use the private runner:

```sh
python run.py scrape --pilot --limit-repos 2 --max-requests 100 --resume
python run.py sync --validate-only
python run.py sync --dry-run --resume
python run.py sync --apply --resume
python run.py run --apply --incremental
```

Run them from the job directory with its installed Python environment, or use the
absolute wrapper path from elsewhere. `scrape` contacts GitHub and saves evidence
but never writes C0. `--validate-only` checks snapshot hashes and relationships
offline. `sync --dry-run` performs authorized C0 reads and zero C0 writes. Sync and
pipeline commands require explicit `--apply` before C0 mutations. A pipeline dry
run describes its crawl scope without collecting data. No command installs cron,
a timer, a GitHub workflow or a C0 job.

Use `--resume` to continue an interrupted run with the same saved window. For a
new rolling-window update, use `--incremental` without `--resume`; otherwise the
saved anchor intentionally stays unchanged. Explicit `--since`/`--until` values
must include a timezone, and syncing a snapshot never recrawls it.

The compatibility scripts `scripts/inspect_c0.py`, `scrape_github.py`,
`update_c0.py` and `run_pipeline.py` accept `--config /private/job/config/source.toml`.
They call the same library and require the same explicit apply/private-job rules.

Exit codes are `0` for validated/dry-run/complete work, `1` for failure or blocked
work, and `2` for a successfully recorded **partial** scrape/sync. A future runner
must handle `2` explicitly; it is not proof of exhaustive coverage. Summaries go
to stdout and bounded JSON progress to stderr. Retain both in the private job.
The `writes` counter counts attempted mutation requests; verified statistics and
independent receipts/readback establish what persisted.

## Evidence, metrics and updating

- Snapshots are immutable. Validate every manifest, JSONL hash, path, relationship
  and original text hash before connecting to C0. Only a validated snapshot becomes
  `latest.json`; never repair one by editing its contents.
- GitHub numeric IDs survive renames. Commits, authored pull requests, issues and
  sampled submitted reviews are distinct measurements. Unknown totals stay null;
  observed lower bounds and incomplete discovery are reported as partial.
- Pagination, request/retry/wait/document limits and one-hop external discovery
  bound the crawl. Bots, inherited fork commits, private metadata, generated trees,
  binary documents and detected secret material are excluded as documented by the
  adapter. Detection is a filter, not proof that arbitrary documents contain no secrets.
- Preserve original document text, pinned commit permalinks, paths, licenses and
  hashes. JSON metadata is never wrapped into the source body. Optional Wiki pages
  are source-navigation summaries; indexed READMEs do not substantiate person metrics.
  They are disabled by default: enable `[sync] publish_wiki = true` in the private
  TOML only when wanted. Disabled publishing makes no Wiki requests.
- Wiki updates require a private receipt matching the existing page ID, revision
  and body hash. A manual edit, colliding slug or missing receipt stops publishing
  without replacing that page. Keep `sync_journal.json` backed up. After an uncertain
  Wiki reply, inspect the actual page and recover verified receipts, or disable
  publishing; never reset the journal to force replacement. Earlier non-Wiki
  writes can already have committed when a Wiki conflict stops the run.
- Reconcile unique external keys before retrying operations without replay support.
  Run only one updater per target space; separate jobs and legacy scripts do not
  share the same local lock.
  Text submission uses revision-bound replay keys; changed text stages a replacement
  with the current expected revision and deliberate current provenance. Conflicts
  stop rather than overwriting another writer.
  Source provenance updates deliberately; verify the current complete generation
  and current commit permalink/hash. Superseded exact references return 410.
- Extraction is asynchronous. A queued response is not verified ingestion. Require
  ready state, exact body/hash and attribution readback; searches/citations must
  identify the matching immutable source version and passage.

Copy an existing job's snapshots, seeds and receipts only into its private job,
validate them and preserve its account, exact space and external keys. Do not copy
another application's OAuth store. Retain the old directory until the new job's
read-only inspection and zero-write validation pass. Updates are explicit future
runs; this sample does not reingest existing data during setup.

## Add another source

Read this example first. Reuse `c0_ingest.config.connection_settings`,
`c0_ingest.client.C0`, `c0_ingest.sources.submit_text`
and `verify_document`, plus private job/state helpers. Implement source-specific
collection and mapping in another public sample module; do not build a second MCP
or OAuth implementation. Keep a thin instance-specific wrapper in the private job.

Add synthetic tests for pagination, provenance, stable identifiers, incremental
updates, partial coverage, denial and uncertain retries. Record reusable source
limitations and recovery lessons publicly; keep real identities, payloads, endpoint
addresses and receipt mappings privately. Run the full base/candidate checks and
review the complete diff before opening a sanitized upstream contribution through
`nethserver-pr`. The [ingestion skill](../../.agents/skills/c0-ingest-sources/SKILL.md)
and [agent instructions](../../AGENTS.md) define the contribution workflow.

## Verify the sample

From the checkout root, with the development dependencies installed:

```sh
python -m pytest -q tests/unit/ingestion
python scripts/check-ingestion-public.py
```

Actual disposable MCP/database coverage is part of the integration suite and
requires the normal disposable database configuration. No model credential,
GitHub token, live instance or live source dataset is needed by public CI.

This code uses the repository's [GPL-3.0-or-later license](LICENSE).

## Project source collectors

`c0-projects` extends this same distribution with independently reusable public
HTTP, feed, sitemap, local document, GitHub, authorized C0-space and offline
WikiPlant adapters. See [project source contracts](../../docs/projects/SOURCES.md)
for private-job configuration, explicit approval, dry-run/recovery and limits.

The read-only `c0-projects project skill` and `project schedule` commands reuse
that authenticated private job to save a project-bound package or inspect IANA
occurrences. See [monitoring and agent contracts](../../docs/projects/MONITORING.md).
Package generation does not install a host task or establish unattended access.

`c0-projects project release-check --config project.json --input release-plan.json
--dry-run` collects bounded public workflow release metadata. Explicit `--apply`
saves and verifies source evidence before a fenced observation. It never installs
code or instructions. See [maintenance contracts](../../docs/projects/MAINTENANCE.md)
for plans, trust restrictions, retry limits and incomplete coverage.

Project source definitions also accept bounded safe YAML. Optional private
GitHub collection requires exact repository/destination consent using the
existing worker credentials; the original public GitHub pipeline stays public.
Typed C0 subscriptions require independent current source-space authorization.

Read-only `project export`, offline `export verify`, `wikiplant validate` and
`export static` create new private local artifacts with checksums. See
[export/preparation contracts](../../docs/projects/EXPORTS.md) and
[fabricated examples](examples/projects/README.md). They do not import live data,
create projects, activate schedules or publish a website.

## Full original document publication

Project publication prefers one REST upload for text/Markdown above128 KiB when
it fits the existing2 MiB/one-million-character extractor bounds.
`publication_parts` preserves an existing legacy multipart layout on unchanged
retries; `parts(item, limit=131072)` explicitly exercises that storage format.
The publisher reconciles uncertain uploads by stable source identity/content hash,
verifies extraction and immutable citations, then commits a complete parent
snapshot. Unchanged originals retain their logical revision; shrinking imports
exclude stale parts while preserving old evidence. Read the full original using
`source_documents_get` or resolve its cited version with
`source_version_document_get`; never join overlapping search chunks.
