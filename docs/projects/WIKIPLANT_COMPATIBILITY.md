# WikiPlant compatibility and implementation audit

## Frozen inspection inputs

- C0 original `main`: `631293d50de6f0faa914554455dbfe61ce623764` (26 October 2026).
- WikiPlant original `main`: `e8dd9e7ae9b48d028cf9a735b30490749c3d8d6c`.
- Starting operator checkout: `9fcf63879375ae1d00f909680413684774a4f3cb`; dirty documentation preserved there. Development uses a separate clone from current original main.
- Public scaffold inspection does not establish a canonical production instance name. “Robotelier-shaped” and “MyProjects-shaped” denote fabricated test projects only. No live operational repository, Drive folder or project data was inspected.

## Ownership and boundary

One project is one existing protected space. Global immutable typed schemas describe individual manifest/history/topic/workflow/queue/attempt/monitoring/result/report/event/maintenance/source-receipt records. Knowledge remains in existing sources, Wiki, entities, relations, claims and annotations. Configuration changes retain immutable history. Domain validators live in Core; transport/UI in app; source collection extends the existing external ingestion package; user instructions extend the existing plugin. No second database, graph engine, shell jobs or model runtime.

Generic object revisions and batches alone cannot prevent external agents from racing a budget reservation or submitting stale workflow progress. Add the smallest trusted transaction service around existing typed storage, current-role checks and content lock order. Its managed operational types must reject raw object writes that bypass policy. External calls retain explicit uncertain outcomes; a database receipt cannot promise exactly-once external execution.

All new project selection is explicit, protected and authorization checked. Cross-space sourcing requires an independently authorized source selection and retained provenance, never cross-space graph references. Monitoring defaults are five queries and ten inspected sources per primary topic per local day, with positive finite configured caps; queue defaults remain five ordinary/ten total, +20 depth, three children.

## Capability matrix

The missing-functionality column records the inspected M0 delta; M1–M7 code and
synthetic/disposable C0 acceptance now close those implementation rows. Current
M8/release status is below and in the readiness report. External host
installation/authentication/execution remains explicitly unverified.

| Feature | WikiPlant implementation | C0 existing support | Missing functionality | Implementation location | Test |
| --- | --- | --- | --- | --- | --- |
| Isolation | Instance/provider binding | Protected spaces and current grants | Require explicit protected selector; no fallback | Core projects / app | DB denial and revoked grants |
| Project configuration | INSTANCE.json, config.py, config schema | Immutable object schemas, revisions, unique keys | Validated manifest plus immutable config history | Core project schemas/service | Config replay, revision, schema upgrades |
| Topic governance | topics.py, admission.py; TOPICS.md | Entities/aliases and typed records | Classification/lifecycle, recorded anchor authorization, direct contribution, terminal expiry | Core project policy | Scope/ancestry/weekly expiry |
| Knowledge lookup | retrieval.py, query workflow | Text/hybrid search, graph, protected spaces | Project-bound workflow instructions | Plugin references | Explicit selector and read-only routing |
| Source originals | source schema, evidence.py | Text and multipart sources, immutable versions/passages | Adapter normalization and state | samples/ingestion | Original/hash/version/citation checks |
| Incremental ingestion | Provider raw-file journals | c0_ingest client, auth, submit_text, readback | Common adapters/config/CLI with cursors and receipts | samples/ingestion c0_projects | Unchanged/changed/lost reply/partial |
| Local documents | Raw Drive/GitHub snapshots | REST file upload and text ingest | Selected recursive safe local collector | Client adapters | Traversal/symlink/binary/large text |
| Web pages | Work web research | No unrestricted server crawler | Public-DNS pinned bounded HTTP adapter | Client adapters | SSRF/redirect/deadline/size |
| RSS/Atom and sitemaps | Monitoring sources | No feed adapters | Incremental bounded XML enumerators | Client adapters | Dates/cursors/incomplete pages |
| GitHub | github_storage.py is operational storage | github_vault public repository/contributor/doc pipeline | General bounded issues/PR/comments/releases/commits adapter; reuse client | Client adapters | Pagination/rate limit/stable numeric IDs |
| C0-space sources | Not native | Authorized changes and content APIs | Explicit separately authorized source-space binding/provenance | Client adapters | No implicit cross-space authority |
| Offline WikiPlant exports | Raw provider files/storage_migration.py | No legacy parser | Read-only raw snapshot parser and deterministic mapping manifest | Client tools | Synthetic layouts/checksums/JSON-body regression |
| Queue | queue.py; CSV with lineage | Independent typed records and atomic batches | Admission, dedup, causal depth, reservations, retries | Core project service | Real DB five/ten/concurrent/recovery |
| Admission | admission.py used by all automatic origins | No research policy | Six dispositions; persisted semantic assessment and novelty inputs | Core project policy | Every origin, explicit deferrals, renamed replay |
| Daily budgets | DailyRunStore, queue attempt journal | Deterministic job attempts only | Atomic project/local-day reservations; urgent slots 6–10 | Core project service | Overlapping daily/weekly workers |
| Ordinary queue fairness | Due validation lane, ageing and historical anchor service | No research selection policy | Implemented reserved ordinary validation lane, bounded ageing and historical service tie-breaking across completed work | Core project_workflows.py | test_project_workflows.py / test_project_maintenance.py |
| Initialization | initialization.py; at most five | Space create and replay-safe Wiki writes | Idempotent project initialize and seed bound | Core projects | Repeated initialization |
| Durable workflows | orchestrator.py; provider-bound safe writer | PostgreSQL transactions, bundles, unique keys | Logical run claims, lease fencing, phase receipts, uncertain invocation state | Core project service | Stale-owner denial/crash/readback |
| Primary monitoring | monitoring.py and main-topic-refresh | Sources/claims/Wiki; no monitoring ledger | Implemented M4 cycles/counters/verified watermarks; material merge gate added in M5 | Core project_monitoring.py / app projects.py | test_project_monitoring.py; fake SDK agent; native recovery |
| Scheduling | cron templates, schedules.py; native Work tasks | UTC interval deterministic handlers; background OAuth | Implemented M4 IANA occurrences/DST and handoff; actual host execution unverified | Core project_schedules.py / plugin project/scheduler.md | test_project_calendar.py / test_project_schedule.py |
| Agent integration | One personalized installed skill; skillgen.py | Instance-bound skill/plugin packaging | Implemented M4 project-bound variants and private CLI download; actual installation unverified | app project_agent_packages.py / c0_projects.agent_packages / plugin project/ | test_project_agent_packages.py / test_project_agents_http.py |
| Evidence review | evidence.py, evidence-quality.md, assessment schemas | Immutable passages, claims, exact-revision annotations | Implemented M5 actual result/finding evidence/claim revision validation | Core project_evidence.py / existing knowledge APIs | test_project_evidence.py; queued extraction denial; actual passage IDs |
| Adversarial review | ChallengeRecord; bounded contrary searches | Claims and annotations retain evidence | Implemented M5 bounded challenge records and ready query snapshots; semantic judgment external | Core project_evidence.py / plugin | Unsearched != searched; no truth by confidence |
| Synthesis | synthesize workflow; applicability/corrections | Wiki revisions, graph, claims, bundles, applicability | Implemented M5 explicit result/Wiki publication proofs and recoverable merge | Core project_evidence.py / plugin | Preserve contradictions/history; new revision needs verification |
| Wiki body safety | wiki.py; clean Markdown separate from JSON | Bounded Wiki Markdown + separate metadata | Regression guard for serialized page envelope in new workflows | Project publishing/parser | JSON envelope rejected |
| Reports | reporting.py, ReportPublisher | Replay-safe Wiki revisions/readback | Implemented M5 stable report membership, saved hash/revision, publication observations | Core project_reports.py / c0_projects.reports / app / plugin | test_project_reports.py and test_project_reports_http.py; omissions/retry/Italian |
| Calendar | calendar.py, calendar schema | Typed objects | Implemented M6 versioned events, provenance and common admission | Core project_events.py / app | Event/publication/retrieval times separate |
| Calendar recurrence/precision | Daily/weekly/monthly refresh, partial dates, latest missed coalescing | IANA schedule helpers | Implemented M6 anchored monthly clamps, descriptive partial dates, actual occurrence receipts and persistent causal depth | Core project_events.py | test_project_maintenance.py; urgency cannot reset depth |
| Weekly structure | maintenance.py | Changes, references, claims, graph APIs | Implemented M6 bounded structural slices/findings/current observations and revision-safe cursors | Core project_maintenance.py / app | Bounded/overlapping cursors; actual native retained records |
| Semantic rotation | Risk plus persistent rotation cursor | Revision-specific verification | Implemented M6 reviewed exact revisions, rotating slot, stale-selection history and explicit coverage | Core project_maintenance.py / plugin | Rotation progresses; no inherited verification; fake SDK weekly agent |
| Archives | archive.py; lineage/evidence capsules | Wiki revision history; explicit archives | Implemented M6 distinct actual future weekly expiry, compact capsules and topic lifecycle history | Core project_maintenance.py / plugin | Same run cannot expire its new topic; history and references retained |
| Release checks | releases.py; upgrade consent | Managed upstream/Core workflow with immutable releases | Implemented M6 bounded public metadata collection, ready source readback and retry history; no adoption | Client maintenance.py / Core project_releases.py | Failed != no_release/up_to_date; no code download/install |
| Release identity integrity | Published-version metadata comparisons | Immutable Core release/promotion policy | Implemented M6 changed known version identity security alerts; version-only compatibility remains unverified | Core project_releases.py | Changed release ID/commit blocked; partial metadata incomplete |
| Export | manifest.py, storage_migration.py | Page exports; native encrypted DB/files backup | Versioned project snapshot with integrity and mappings | Client export tools | Determinism/tamper/private selection |
| Static publishing | Selected wiki files | Markdown export | Explicit page/report allowlist; offline output | Client export tools | No publication or default public export |
| Recovery | SafeWriter intents/readback; provider generation | NS8 DB/files backup, restart, native update and receipts | Include project typed records; run/attempt recovery | Core + existing NS8 suite | DB restart/backup/upgrade; never live destruction |
| Project UI | Wiki/index driven | Readers, Tools, DOM rendering and race guards | Read-only selected-project overview linked to existing pages | app static/API | Access loss/late replies/Reader controls |
| Authentication | Host/provider capability gates | OAuth S256, background consent/rotation/revocation | Reuse existing client; no new credentials or permission bypass | c0_ingest auth and existing app | Expired/revoked authority fails closed |
| Notifications | DeliveryState separates saved/published/notified/read | No external notification transport | Implemented M5 separate attributed observed/unknown states; no invented transport | Core report delivery records/runner contract | Saved does not imply received |
| Typed repository knowledge subscription | External provider files | Protected typed objects/schema and object change feed | Implemented M7 explicit objects:type source selection with independent source authorization/cursor | Client adapters + Core connector validation | Third-space actual SDK incremental copy; revoked grant PostgreSQL denial |
| Private GitHub source consent | Provider-specific storage credentials | Existing external GitHub worker credentials; public default | Implemented M7 optional destination/repository-bound consent and current-access frozen replay | Client private_sources.py / github_client.py / CLI | Real SDK publication with mocked remote authorization; removed consent/revocation fails before write |
| Safe YAML configuration | Strict config schema | TOML/JSON client definitions | Implemented M7 bounded nonexecutable YAML parser | Client formats.py | Alias/duplicate/tag/depth/type rejection |
| Export catalog and text limits | Storage manifests/raw revisions | Existing selected-resource APIs | Implemented M7 fixed scoped metadata catalog/text fragments/two-pass change detection | Core project_exports.py / client exporting.py | Real PostgreSQL permissions; SDK deterministic/tamper/concurrent-write tests |
| Complete reference workflow | Internal workflows and provider journals | Reusable project/knowledge services | Implemented M7 fabricated English/Italian daily/weekly/export integration | Synthetic configurations / test_project_synthetic_e2e.py | Real OAuth/SDK/PostgreSQL; fake provider outcomes only |

## Sequential implementation and acceptance

M0 freezes this comparison and the architectural boundary. M1 implements validated project configuration/history, topics, authorization and reader overview. M2 extends reusable ingestion with adapters and incremental receipts. M3 implements atomic queue/run/attempt policy and fencing. M4 adds separately budgeted monitoring and external-agent/scheduler contracts. M5 persists evidence/results/reports and independent delivery observations. M6 adds calendar, bounded maintenance and lifecycle. M7 adds integrity-checked export and read-only synthetic migration preparation. M8 runs full compatibility, packaging, UI/native/recovery/privacy validation and records readiness.

Every milestone records actual focused tests, commit, push and completed CI before advancing. Runtime merge requires the current CI policy and exact-source merge gate; Core publication and adoption remain separate immutable gates. This task authorizes no dedicated-instance deployment or real migration, overriding older generic live milestone instructions. Live acceptance and scheduled-agent installation/execution remain explicitly unverified unless separately observed. No real project spaces, schedules, source writes or existing knowledge changes are permitted.

## M0 inspection evidence

Read C0 AGENTS/README/PLAN, reference/development/CI policy, feature/Core/ingestion skills, schema and service implementations, native lifecycle and plugin/ingestion contracts. Read WikiPlant AGENTS/README/PLAN, architecture/operations/hardening/evidence/storage/runtime documentation, required internal workflows, schemas, cron templates and deterministic helpers. C0 source API limit is 131072 UTF-8 bytes; object payload 64 KiB; immutable schemas; bundle 1–25 operations/262144 bytes; extraction is asynchronous; existing schedule intervals are UTC. Retain all limits.

Baseline full CI: [40289355200](https://github.com/Stell0/ns8-czero/actions/runs/40289355200), dispatched at exact C0 revision above; completed/successful with an independent native/artifact audit. Existing same-source [40286224042](https://github.com/Stell0/ns8-czero/actions/runs/40286224042) also completed/successfully audited. Disposable PostgreSQL validation is recorded in PLAN.md.

## M2 implementation checkpoint

The existing `samples/ingestion` OAuth package now contains `c0_projects`
collectors/publisher/CLI; no second authentication or source store is introduced.
Seven adapters, strict finite definitions, approved per-space connector history,
immutable version provenance and revision-safe successful/partial cursors are
implemented. See [SOURCES.md](SOURCES.md) for exact selections and limitations.
Synthetic signed HTTP/PostgreSQL tests cover lost responses, queued extraction,
changed/unchanged text, multipart PDF, immutable citations and cursor conflicts.
No real source, live project, external scheduled execution or migration is
claimed. M3–M8 workflow/report/export acceptance remains outstanding.

M2 cursor-integrity follow-up: an actual negative signed-HTTP regression showed
that counts alone could claim verified coverage. Connector updates now provide
actual part receipt IDs, checked inside Core against ready same-space versions,
enabled approved connectors and complete immutable parent snapshots. Partial
items do not count until their complete original snapshot is stored. The CLI
and exact native seed/recovery helper use that contract. Frozen d2575cc remains
unchanged; the corrective source receives its own full acceptance run.


## M3 implementation checkpoint

[WORKFLOWS.md](WORKFLOWS.md) documents implemented trusted typed transactions
for queue admission, six dispositions, lineage/terminal guards, budgets, run
leases/fencing, immutable phase observations, attempt reservations and separate
invocation outcomes. Source-sync publication carries its lease through cursor
commits; project readers show queue and run observations. Actual PostgreSQL
threads, current/legacy SDK transport and native recovery fixtures exercise
these boundaries. Semantic assessments remain external; M5 adds the stronger
result/evidence/report contract. M3 exact full CI/native acceptance is pending.
M4–M8 remain outstanding and no real migration or deployment has occurred.

Accepted M1 branch run 40311946100 and corrected M2 run 40316218857 completed
successfully with independently downloaded native XML/browser/query/scanner
artifact audits. The initial M2 count-only coverage weakness has a real negative
regression and corrected receipt-proof implementation at `28f40f0`.

## M4 implementation checkpoint

M3 exact `fb9c4b7` full40333538357 and its independent downloaded native/privacy
audit pass. [MONITORING.md](MONITORING.md) documents M4's separately capped
primary cycles, durable query/inspection reservations, immutable outcome
history, scope-specific watermarks and daily execution gate. Material evidence
remains pending M5 verification. Project-bound skill/plugin variants reuse the
existing package machinery and OAuth client. Calendar contracts handle IANA
DST and bounded missed occurrences without replenishing actual-day budgets.
Actual PostgreSQL races, source readiness, failed searches, signed fake-agent
SDK calls and private archive readback pass locally. M4 exact native acceptance
is pending; real host installation/authentication/scheduled execution remain
unverified. M5–M8 remain outstanding. No live migration/deployment occurred.

## M4 acceptance and M5 implementation checkpoint

Corrected M4 f2a2a13 full40373013755 completed successfully, with actual
downloaded Debian genuine-upgrade/Rocky-installation, all eight browser,
privacy/accessibility/query and five scan/SBOM audits passing. Exact local job
reports2163 Python/PostgreSQL/packaging,193 Node and21 Robot dry runs.
Actual external-agent and unattended execution remain unverified.

M5 adds strict individual findings/results/publication proofs and report/member/
delivery histories, seven REST/MCP operations and an independently reusable
deterministic client report publisher. See [reporting contracts](REPORTING.md).
Focused real PostgreSQL/SDK tests verify passage/claim bindings, new revision
verification, saved merge recovery, contrary checks, omitted/deferred results,
concurrent ownership, publication retry, Italian byte ranges and protected
isolation. Native recovery retains actual result/report proofs and a simulated
failed external publication. Exact full/native acceptance remains pending; M6–M8
remain outstanding. No live migration, deployment or schedule activation occurred.

## M5 acceptance and M6 implementation checkpoint

M5 bf13979 full40395011881 and independently downloaded native/artifact audits
pass:2189 Python/PostgreSQL/packaging,193 Node,21 Robot; Debian upgrade21,
Rocky installation26/three expected skips/all8 browsers, privacy8,
accessibility32 and three zero-candidate query artifacts. Actual external-agent
and scheduled execution remain unverified.

M6 adds seven REST/MCP operations and trusted nested input schemas, durable audit
findings/cursors, exact-revision semantic rotation, topic history/peripheral
capsules, calendar recurrence/admission, bounded metadata release observations
and reader diagnostics. See [maintenance contracts](MAINTENANCE.md). Real
PostgreSQL and signed fake-agent SDK tests exercise stored state; native recovery
fixtures now retain audit/semantic/event records and browser report links.
M6 exact full/native acceptance remains pending; M7–M8 remain outstanding.

## Historical M7 implementation checkpoint

M6 corrected1000839 full40414161692 and independent native/artifact audits pass.
M7 implements [private export, legacy preparation and static selection](EXPORTS.md),
seven-adapter safe YAML examples, authorized typed source subscriptions and
optional private GitHub consent. Offline fixtures preserve legacy IDs, provider
generations, pending lineage, receipts and actual Markdown; malformed evidence
blocks preparation without modifying source bytes. Export excludes authority and
unavailable history, explicitly reports partial/concurrent collection and does
not replace native backup. All target migration IDs remain null.

Focused actual PostgreSQL/SDK tests pass for source authorization, incremental
third-space knowledge, private frozen replay, reports/static output and both
complete fabricated daily/weekly projects. Exact M7 full/native acceptance is
pending. Earlier checkpoint paragraphs are historical; M8 Core release/default
adoption and final readiness are outstanding. Actual external-agent research,
unattended execution, dedicated deployment and live migration remain unverified.

## Current M8 acceptance

Final M7 b5e84bb full40433543339 and the independent downloaded native/artifact
audit pass2262 Python/PostgreSQL/packaging,196 Node,21 Robot, Debian upgrade21,
Rocky installation26/three expected skips/all8 browsers, privacy8,
accessibility32 and three zero-candidate OAuth-query artifacts. Actual image
source/config/layers and packaged project bytes verify; no worker/YAML package
enters the server image. Static export uses the documented conservative subset
and snapshot-time explicit public selection. No output is deployed or published.

M8 additive Core0.34/app0.53 and worker0.2 distributions retain schema0021 and the
original frozen predecessor. Exact cd8e7a8 [full40443878849](https://github.com/Stell0/ns8-czero/actions/runs/40443878849)
and independent actual native/artifact audits pass2262 Python,196 Node,21 Robot,
Debian upgrade21 and Rocky installation26/three expected skips/all8 browsers,
privacy8/accessibility32 and three zero-query artifacts. Actual installed wheel/archive
project writes survive repeated migration; exact Wiki/source/claim exports and
revoked delegated access are checked without app/NS8. Installed worker CLI
validates both reference YAML projects and raw layouts without server packages or
C0 writes. Focused69 packaging/version/SSO-wrapper cases pass. Immutable
[Core0.34.0](https://github.com/Stell0/ns8-czero/releases/tag/core-v0.34.0)
publication40449147120 succeeds; actual assets match verified distributions and
checksums. The default tag/lock and reviewed0.34.x updater bounds adopt this source.
Final ready-PR exact-head acceptance is recorded on that PR; it must pass the full
consumer/native/artifact gate independently of the prepublication proof.
See [readiness](WIKIPLANT_MIGRATION_READINESS.md) for the feature/status matrix and
independent code/local/disposable/reference/external-agent/unattended states.
