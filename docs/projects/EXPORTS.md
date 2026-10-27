# Project export and migration preparation

These read-only preparation tools do not import data, create spaces, activate
schedules, install code or publish websites. Use private local destinations,
existing OAuth consent and an explicitly selected protected project space.

```sh
c0-projects project export --config /private/project/config/project.yml --output /private/new-snapshot
c0-projects export verify --input /private/new-snapshot
c0-projects wikiplant validate --input /private/offline-raw-export --output /private/new-preparation
c0-projects export static --input /private/new-snapshot --selection /private/public-selection.json --output /private/new-static
```

Every destination must be new. Directories/files use 0700/0600, reject symlinks
and unsafe relative paths, and are read back against SHA-256. Default bounds are
10000 records/100 MiB, configurable up to 100000/1 GiB. Limit or concurrent-change
failures produce PARTIAL preparation. Retain it and retry into a new directory.

## Native export

`GET /api/v1/project/export?space_id=UUID&kind=catalog` and MCP
`project_export_get` expose a fixed catalog with current Reader authorization on
every request. Catalog descriptors specify key fields and text/hash kinds. Pages
contain at most 100 rows/262144 bytes; cursors bind space and kind. Text fragments
contain at most 32768 characters with immutable IDs/character offsets. The client
checks complete UTF-8 hashes, without truncation.

The deterministic version1 manifest includes configuration, topics, queue,
workflows, budgets, source receipts, results, reports, maintenance, used object
schemas, source/version/document/chunk metadata, Wiki revisions, entities,
aliases, relations, claims/evidence and revision-specific annotations. Bodies
remain separate Markdown/text. Stable identities, revision mappings, provenance
and file hashes remain available. `manifest.sha256` verifies the canonical
manifest; verification rejects missing, extra, changed or unsafe files.

The collector compares space change cursors, configuration and a second complete
metadata enumeration. This is change detection, **not a transaction snapshot**.
Authority tables, credentials, sessions, jobs, embeddings and server paths are
excluded. User-authored metadata may itself be private; keep the snapshot private.
Original binary bytes require the existing authorized original-file API or native
DB/files backup. Unavailable historical generic-object/claim payloads are not
invented. Actual explicit project histories and immutable source/Wiki revisions
are retained. Interchange export does not replace native backup/restore.

## Offline WikiPlant preparation

The independent parser reads INSTANCE.json, config.yml, data/SCOPE.md, TOPICS.md,
research_queue.csv, calendar.csv, sources/, wiki/, research/, monitoring/,
reports/ and state/. It never imports or executes WikiPlant code. The frozen
public reference is recorded in the compatibility matrix. See
[fabricated raw fixtures](../../tests/fixtures/wikiplant/README.md).

An optional version1 `wikiplant-storage-export` manifest binds every path to
size, SHA-256, source_object_id, source_generation and source_mime_type. Offline
identifiers can describe Drive or GitHub without live account access. Actual
archive generations retain distinct mappings; missing historical data is not
invented. Canonical instance names come only from supplied configuration.

Output contains deterministic migration-manifest/checksum, validation report
and individual normalized metadata/Markdown. Legacy IDs, lineage, pending work,
timestamps, links, receipts and recoverable generations remain explicit. Every
target C0 ID/space is null and activation is required. Invalid authorization,
lineage, dates, checksums or canonical readable metadata block preparation.
Broken local links are visible review notices. Structural validation does not
prove semantic validity or complete the future legacy-to-C0 policy mapping.

Serialized page JSON inside Markdown produces a blocked repair proposal with
Markdown separated from metadata; original bytes stay unchanged. Canonical
managed Wiki claims are checked against metadata. Fenced JSON examples remain
document content.

## Static selection

Supply actual immutable Wiki revision UUIDs and/or saved report object UUIDs:

```json
{"schema_version":1,"project_id":"11111111-1111-4111-8111-111111111111","wiki_revisions":[],"report_references":[]}
```

Both selected and current page revisions must have
`metadata.static_publish.public: true`. No dependencies are implicitly added.
Private/cross-project internal targets reject export. Selected Wiki links map to
stable filenames; protected evidence links become plain labels identifying
evidence retained in C0. Source evidence is not published.

The conservative Markdown exporter escapes HTML, disables images/frontmatter,
rejects ambiguous reference definitions and unsafe destinations, and records
transformations separately. Review output before handing it to Quartz or another
publisher. The command creates local files only and does not establish that the
content is suitable for public disclosure.

## Synthetic acceptance

[Reference configurations](../../samples/ingestion/examples/projects/README.md)
contain fabricated English robotics/Italian software themes, disabled Rome
schedules, finite budgets and mocked GitHub responses for pagination, issues,
PRs, releases, comments, documents and contributor identities. Actual signed
SDK/PostgreSQL tests run daily monitoring, one evidence-backed investigation,
Wiki/report readback, weekly audit/review/report and export. Source instructions
cannot change scope or allowances. Fake agents do not verify external research
hosts or unattended scheduled execution.
