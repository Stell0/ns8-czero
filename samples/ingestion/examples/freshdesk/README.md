# Freshdesk FAQ import

`c0-freshdesk-faq` exports current published Solutions articles from explicitly selected categories,
then reuses the existing project publisher, fenced receipts and whole-document
hash readback. Category/folder traversal, category/article exclusions and the
title/body Markdown mapping are adapted from
[Freshdesk2S3](https://github.com/NethServer/Freshdesk2S3), licensed under GPLv3.
There is no S3 export, ticket access, Freshdesk mutation or scheduler.

Use an explicitly authorized protected project and the existing ingestion job's
account/space-bound read/write connection. Keep administrator connector approval
separate. Never copy a stale rotating OAuth store from a local mirror. Publication
runs where the authoritative job/store lives and holds its normal `job.lock`.
The FAQ state uses `data/freshdesk-faq`, separately from website state at
`data/c0-projects`; the established website configuration and timer stay intact.
Use a separate Python environment for the FAQ extension when the website job's
ingestion distribution is frozen.

Store API credentials in a private literal file, not command arguments or shell
code. The collector reads only its five named values; unrelated model credentials
are ignored. `CATEGORY_BLACKLIST` and `ARTICLE_ID_BLACKLIST` are comma-separated.
Set exclusions deliberately; deployment-specific defaults stay outside Git.

```dotenv
FRESHDESK_DOMAIN=example.freshdesk.com
FRESHDESK_API_KEY=REPLACE_PRIVATELY
FRESHDESK_SOLUTIONS_DOMAIN=help.example.org
CATEGORY_BLACKLIST=Archived,Internal
ARTICLE_ID_BLACKLIST=123,456
```

Save the source definition as private `config/freshdesk-project.json`:

```json
{
  "schema_version": 1,
  "server_url": "https://c0.example.org/mcp",
  "project_space_id": "00000000-0000-4000-8000-000000000001",
  "sources": [{
    "id": "freshdesk-faq",
    "adapter": "local_files",
    "root": "data/freshdesk-faq/export",
    "include": ["*.md"],
    "max_items": 1000,
    "max_requests": 500,
    "max_bytes": 16777216,
    "max_pages": 20,
    "max_depth": 4,
    "timeout": 20
  }]
}
```

This is a local-export connector: collection writes private complete Markdown and
a native saved source scan with canonical article URLs and provenance. It needs
no new Core connector type. Approve this exact definition and append its ID to
the project's existing manifest using supported administrator operations. Preserve
existing connector definitions, manifest fields and schedules. The routine worker
cannot approve itself; a denial never falls back to Shared.

Copy `run.py` into the private job, or invoke `c0-freshdesk-faq` with explicit
`--job` and `--config` arguments. The wrapper commands are:

```sh
python faq.py scan --env config/freshdesk.env
python faq.py sync --dry-run
python faq.py resume --apply
python faq.py verify
python faq.py status
```

Scan performs only Freshdesk GET requests. It never writes C0. Publication consumes
the saved, hash-checked scan without recollection. `sync --dry-run` performs C0
reads with zero writes; `resume --apply` uses the normal publisher and queues the
bounded extraction batch before verifying complete publication. Repeating the
same frozen snapshot verifies the same identities and generations. Run a new scan
for remote changes. Missing remote pages never delete current C0 documents.

Interrupted collection retains its cycle-bound cache. Resume with
`scan --continue-scan --env ...`; do not alter its selection. HTTP errors,
Retry-After, unknown visibility, changed article identity, invalid conversion and
resource limits are explicit failures. Never clear pending OAuth/write markers to
force retries. TLS/DNS protections come from the shared pinned public fetcher;
authenticated redirects are rejected before credentials are forwarded.

Bounds are 500 requests and 1800 seconds per invocation by default, at most20
pages of100 records per inventory endpoint,1000 selected articles and32 MiB per
batch. Cached pages do not consume a resumed network request budget. Limits never
mean exhaustive success. These commands cover the API's default language;
additional translated collections require an explicit reviewed selection.
Article status must be published. Match the original exporter by applying its
category and article blacklists without adding folder-visibility or marketing
exclusions. All API-readable folders in the approved categories are included,
including folders requiring portal sign-in. Authorize this selected collection
explicitly, keep internal/legacy category exclusions in the private configuration,
and record any global portal sign-in requirement. Draft and blacklisted content
is excluded; no attachment or image is fetched.
Images remain inert links. Validate table/code/procedure examples before applying.

Keep JSON inventories, original API responses, scan bodies, credentials, receipts
and results private. Record selected/excluded counts and all unresolved gaps.
