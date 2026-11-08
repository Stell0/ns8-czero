# Vue website implementation contract

This document records the Vue website delivery and its frozen acceptance. Version statements describe that checkpoint; use the active app/Core manifests and [PLAN](../PLAN.md) for current versions and installed identities. Current reader routes and behavior are summarized in [the user guide](user-guide.md).

The accepted plan replaces the reference website with Vue 3, TypeScript and
Nebula. Native NS8 settings remain Vue 2/Carbon. Implementation starts from
original C0 main `b317619322ab0a59af038186db8e55e749f94ff6`, isolated on
`feat/vue3-website`. My Nethesis frontend at
`6a212caff680f24961d59a7eaea270a769c2d8b9` supplies the toolchain reference.
Core 0.38.0, schema 0032 and all REST/MCP contracts remain unchanged.

## Routes and behavior

| Route | Behavior |
| --- | --- |
| `/` | Search, actual Wiki sections and source browsing |
| `/search` | Selected-space knowledge search, URL filters and bounded ranking |
| `/wiki`, `/wiki/:id` | Hierarchy, breadcrumbs, article, table of contents, claims, exact evidence and exports |
| `/sources`, `/sources/:id` | Source library, complete current document, provenance, retained original and extraction status |
| `/evidence/:id` | Exact citation; superseded evidence stays unavailable |
| `/projects` | Protected project purpose, topics, synchronization, monitoring and reports |
| `/explore` | Read-only entities, claims, relationships, annotations and structured records |
| `/account` | Identity, preferences, exact connection disconnect and personal API keys |
| `/agents` | Instance-bound assistant connection and package downloads |
| `/admin` | People/application access |
| `/admin/spaces` | Protected spaces and grants |
| `/admin/advanced` | Technical clients |
| `/admin/work` | Jobs, schedules and extraction recovery |
| `/auth/sign-in`, `/oauth/consent`, `/oauth/connect` | Server-gated identity and connection flows |

The selected space and applicable filters stay in the URL. Explicit invalid or
denied spaces never fall back to Shared. Query identities include the account,
space and resource/filter. Account/space/access changes abort work and erase
protected cache and DOM state before loading another identity. Browser storage
contains only language and theme preferences. Cookies and X-C0-CSRF remain the
authentication contract. Conflicts require a reload; HTTP 410 never substitutes
current text for expired exact evidence.

Knowledge creation, editing, annotation, archive and deletion controls are
deliberately removed. Assistants retain those REST/MCP operations. Source upload,
replacement, retained-original reprocessing and authorized retry/cancel remain.
Original retention is unchecked by default. Replacement processing never hides
the published complete document. No source collector, agent runtime or schedule
is added by visiting the website.

Original download links honor explicit retention. Failed staging remains
available to authorized API recovery without becoming a retained browser
download; unpublished versions stay private to writers. Reader pages never
advertise a staging download that the API denies.

## Acceptance matrix

| Surface | Required proof |
| --- | --- |
| Foundation | Frozen npm install; lint, format, types, Vitest, build; English/Italian parity |
| Reading | Actual API writes followed by browser readback; hierarchy, full documents, exact citations, no knowledge mutations |
| Isolation | Reader/Editor/Admin, denied protected spaces, switching, logout, late replies, CSRF, conflicts, superseded evidence |
| Sources | New/replacement upload, retention opt-in, old document during processing, recovery and unavailable originals |
| Account/access | HTTPS sign-in/remember, consent, approval, disconnect, API-key secret lifetime, assistant downloads |
| Presentation | Desktop/phone, light/dark/system, English/Italian, keyboard, dialogs, skip links, focus, Back/Forward |
| Integrity | Hostile/large Markdown, bounded worker, local assets, real packaged app |
| Delivery | Baseline/candidate validation, full Debian/Rocky native checks, audits, reviewed regular-merge PR |

The cutover serves the Vue website from FastAPI and removes legacy HTML and
controllers. API, MCP and OAuth responses are not rewritten into SPA HTML;
missing assets and unknown routes remain errors. No production deployment is
authorized by this implementation. Existing operator waivers and frozen evidence
remain unchanged.

## Verification and packaging

Use Node 24 and npm 11, then `npm ci --ignore-scripts` and `npm run check`
inside `app/frontend`. `npm run test:e2e` runs controlled API interactions,
including delayed responses, scope ceilings and revision conflicts. Build before
Python tests. `tests/e2e` starts disposable HTTPS C0 instances with actual
PostgreSQL, signed identity, REST/MCP and extraction. Its database account needs
CREATE DATABASE permission; each browser case creates its own database.

The Node image stage ships only compiled assets, local fonts, the bounded
Markdown worker/parser and license notices. `tests/audit_runtime.py` requires
this inventory, checks the emitted manifest and rejects source, dependency
folders, extra assets, missing notices and symlinks. Headless UI's npm package
omits its MIT text; the copied notice in `app/frontend/licenses` comes from its
exact published source commit, recorded alongside the notice.

Saved content links resolve original typed IDs and exact revision parameters to
the new URLs. This adds no legacy routes and does not substitute current content
for expired evidence. Relative source links use retained canonical provenance.

## Behavioral coverage migration

Legacy DOM-controller tests are replaced with tests of the Vue application and
its actual API boundaries. NS8 Vue 2 settings and the numeric accessibility
probe retain their Node suites. Core and HTTP mutation tests remain intact.

| Former controller coverage | Replacement |
| --- | --- |
| Reader, source/Wiki/search/record request races | `client`, `session`, `document-reader`, `markdown`, `knowledge-tree`, `content-links` Vitest; delayed browser reads; actual document explorer/lexical suites |
| Browser knowledge authoring, schema/relation/annotation forms | Deliberately removed controls; existing Core/HTTP mutation suites and API writes followed by read-only Wiki/Explore/project browser readback |
| Sources upload/selection/reprocessing | Source replacement/CSRF/retention interaction checks; actual atomic replacement, 100-page selective retry, retained-original reindex and native source workflows |
| Access, sharing, spaces, clients, connections | Draft/replay/key validation tests; Reader/Editor denial, scope ceilings, unchanged approvals, stale preview and conflict interaction checks; real HTTPS Account/Admin tests; ten independently graded native access phases |
| Consent and onboarding | Server-gated HTTP tests, real signed background sign-in/consent/disconnect, role-bound agent guidance and downloaded archive checks; native provider and package workflows |
| Administration/jobs/extraction | Existing HTTP and Core contracts, actual extraction recovery browser cases and native client/job/schedule/space workflows |
| Navigation and presentation | Real desktop/phone, English/Italian, light/dark/system, keyboard, skip links, dialogs, Back/Forward, local asset and numeric accessibility checks |

The contract is app 0.59.0 with released Core 0.38.0/schema 0032 unchanged.
The managed Containerfile and local workflow remain registered in
`c0-upstream.json`. Its historical comparison hashes remain intact; the new
application frontend is application-owned. This change adds no upstream-managed
runtime input or development skill. Native test helper code stays outside images.

## Development evidence

Original `b317619` passes 2,775 backend/database/packaging cases in a fresh
disposable database with English/Italian OCR. Reviewed source
`172b31901076dbf2082c98544cb250a8b3ddbb99` passes [full acceptance](https://github.com/Stell0/ns8-czero/actions/runs/42096335384):
2,799 backend/database/packaging cases, 39 actual HTTPS browser cases, frozen npm
installation, lint/format/types, 28 Vitest cases, 17 controlled browser cases and
production build. English/Italian have 260 matching keys. All 27 Node tests,
schema/shell checks and 21 Robot dry runs pass; the actual native workflows
independently pass as well.

Independent artifact grading verifies Debian upgrade 21 passed and Rocky
installation 26 passed/three expected skips, eight browser workflows, 30 numeric
accessibility contexts, ten access phases, eight privacy guards and five
scan/report pairs. Three OAuth-query artifacts contain zero candidates. Reader,
Editor and Admin API-key revocation proves both saved state and HTTP 401 readback.
The actual published image passes the closed runtime/license inventory, released
Core Git/schema identity and compiled HTTP asset/font/CSP/route probes.

PR75 regularly merges as `c011a0b9b9eb57b9a0f545f21e129e8732eb65e4`. Actual
[merged-main full acceptance](https://github.com/Stell0/ns8-czero/actions/runs/42106339803)
passes the same complete local/native suites, independent artifact/image audits,
current-source full promotion and canonical publication. Six fresh registry reads
verify the three images' main/latest aliases and source labels. Exact immutable
tags/digests are recorded in [PLAN](../PLAN.md#vue-3-website-remake--source-and-publication-accepted).

Failed evidence remains private and preserved. Earlier runs exposed missing WOFF2
MIME metadata in slim images, stale native selectors, initial filter events that
rewrote focus/pagination, premature dialog completion, search details remounts
and failed staging downloads advertised without accessible retained originals.
Negative controls reproduce the dialog, filter and retention failures; corrected
regressions pass. Eight actual failed-source English/Italian, light/dark and
desktop/phone contexts verify translated status, keyboard access and download
visibility. Failed candidates and separate targeted passes are not represented
as complete acceptance. No frozen run or image was removed.

App 0.59.0 retains Core 0.38.0/schema 0032. The separately authorized
[dedicated installation](../PLAN.md#vue-website--dedicated-installation-accepted)
is accepted after verified backup/update, manager restart, preservation, real
HTTPS/browser/connector and positive-control root-journal checks. No stable module
release, additional Core publication or external schedule is included.
