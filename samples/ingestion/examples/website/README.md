# Crawl documentation into C0

This recipe collects approved public documentation with deterministic HTTP,
converts whole articles to Markdown and updates current C0 documents. Code in Git
is authoritative. Stored recipe/code references are inert evidence, never
permission to execute commands or broaden a connector's scope.

## Prepare one private job

Install Python 3.12–3.14 and the frozen ingestion distribution outside C0:

```sh
uv sync --project samples/ingestion --frozen
samples/ingestion/.venv/bin/c0-ingest init .local/ingestion/documentation
cp samples/ingestion/examples/website/run.py .local/ingestion/documentation/run.py
cp samples/ingestion/examples/website/generic.json .local/ingestion/documentation/config/website.json
```

Edit that job's literal `.env` using the existing [ingestion setup](../../README.md)
to bind its dedicated OAuth client, expected account and exact destination space.
Edit `config/website.json` with the same instance/space. The example UUID and
hostname are placeholders, never defaults for a real run. Use an existing
authorized protected project and explicitly approve each connector using the
existing `c0-projects sources bootstrap --apply --authorization-ref ...` workflow.
Creating a project or granting space access is a separate administrator action.
Ordinary scan/sync never creates spaces, approvals, grants or schedules.
Use a dedicated website job; mixing website and other adapters in one private
job is rejected. Separate jobs can still target the same protected project.

Choose exact seed URLs and allowed origin/path roots. Cross-origin roots require
explicit configuration and approval. Configure selectors using `docusaurus`,
`sphinx` or `generic`, plus optional `selectors`/`remove_selectors`. Keep language,
product/version and manual metadata explicit; unknown values stay empty. Include
rules match URL/path globs; exclude rules override them. Product versions and
locales remain separate URLs. A publication date does not imply obsolescence.
Robots and discovered sitemaps use approved origins for inventory discovery.
List a redirected sitemap destination outside article prefixes in `sitemaps`.
A redirected robots destination must match an explicit `allowed_roots` path.
An unknown redirect never broadens scope.

## Scan, preview, publish and recover

From the job directory, using the installed environment:

```sh
python run.py login
python run.py bind-account
python run.py scan
python run.py sync --dry-run
python run.py resume --apply
python run.py status --report-format human
python run.py verify
```

Scan fetches public pages and saves a private pending run, with zero C0 writes.
Dry-run only reads C0 and that saved scan. Resume publishes the saved pending
selection without recrawling. A periodic `python run.py sync --apply` resumes a
pending run first, or scans a new bounded selection after verified publication.
Runs and OAuth rotation use the existing locks; uncertain refresh requires the
existing connection recovery procedure, never deleting a rotation marker.

JSON is the default report; `--report-format human` prints a brief operator summary. Exit codes are `0` complete/dry-run, `1` blocked and `2` partial. Reports separate crawl, conversion, publication, extraction wait and readback durations. A page,
request, byte, sitemap or frontier limit is partial coverage. Network failures,
429/5xx, robots denial, missing pages and failed conversion never delete C0
sources. Retry-After is recorded and honored. There is no remote-deletion
reconciliation. Empty, login, error and JavaScript-only pages cannot replace
current content. A shorter valid article can replace a longer one.

The collector uses one persistent HTTP connection at a time per origin, obeys
robots/rate limits and pins public DNS/TLS peers. It reads sitemaps before falling
back to complete-page navigation links. Navigation is excluded from article
text. Headings, tables, lists, code, admonitions, tab variants, links and image
alternative text survive conversion. Remote media and raw HTML remain inactive
in C0. Conditional 304 responses reuse a verified current HTML representation;
an extractor/configuration upgrade still reconverts that representation.

Private state contains a bounded frontier, one current HTML representation per
URL and a pending publication scan. Only crawler-owned older verified scans are
removed after readback; payload-free summaries remain. Pre-existing private jobs
and unrelated datasets are never swept. Do not manually edit saved scan hashes
or reset receipt state to force an uncertain write.
Frontier progress is acknowledged only after the pending scan is durably saved.
An interrupted collection replays its bounded uncheckpointed batch using the
current HTML cache; a saved scan with a lost pointer is recovered automatically.
Direct Python adapter callers must durably save the returned batch before calling
`c0_projects.website_state.commit_frontier(root, connector_id, batch.cursor)`.

C0 publishes complete generations atomically. Pending/failed parts leave the
previous current document intact. Changed content removes superseded bodies,
chunks, vectors and originals through durable cleanup. Stable document links
open current content; old exact citations return `content_superseded`. Source
changes invalidate dependent evidence without erasing authored Wiki quotations.

## Nethesis catalog

`nethesis.json` is a public, bounded example derived from
[docs.nethesis.it](https://docs.nethesis.it/), checked on 29 October 2026:

| Catalog target | Approved documentation | Disposition |
| --- | --- | --- |
| NethVoice administrator/user | `https://docs.nethvoice.com/it/docs/` | Italian Docusaurus articles; the administrator page explicitly identifies NethVoice 8 |
| NethSecurity administrator | `https://docs.nethsecurity.org/it/docs/` | Italian Docusaurus articles; product version remains unknown |
| NethServer 8 administrator/user | `https://docs.nethserver.org/docs/` | Current English Docusaurus articles; do not assume older Sphinx URLs or an Italian path |
| WebTop | `https://docs.nethserver.org/docs/administrator-manual/applications/webtop` | A NethServer application chapter; catalog's old `projects/ns8/en/latest/webtop.html` is a redirect page |
| NethVoice 14 / older manuals | Separately configured roots only | Distinct manuals, never deleted because they are older; no unverified root is guessed |
| Hotspot, My Nethesis, hardware, support | Helpdesk/Freshdesk links | Outside this public crawler preset; authenticated ingestion is separate |
| Downloads, registration, marketing, training | Catalog outbound links | Excluded; catalog discovery does not approve crawling every linked site |

The bounded smoke selection is at most 20 pages per primary site and deliberately
reports incomplete coverage. No production import or external timer is installed.

## Make the recipe discoverable

After the code has an immutable Git commit, run:

```sh
c0-docs-recipe --job .local/ingestion/documentation --revision FULL_40_CHARACTER_COMMIT --dry-run
c0-docs-recipe --job .local/ingestion/documentation --revision FULL_40_CHARACTER_COMMIT --apply
```

This uses the job's same OAuth/account/space binding to save the recipe and a
pinned code reference, then verifies the current extracted bodies. It does not
execute retrieved code. Use this only for an explicitly selected destination.

`c0-website.service` and `c0-website.timer` are uninstalled external scheduling
examples. Review paths/users before separately authorizing installation. A cron
equivalent is `15 3 * * * /srv/c0-venv/bin/python /srv/c0-jobs/documentation/run.py sync --apply`.
Exit 2 needs operator attention; do not treat it as exhaustive coverage.

If extraction fails, inspect the private run and effective article selector,
robots restrictions, response media type and C0 source status. Keep a prior
valid document until conversion, extraction and whole-document readback pass.
