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
| Initialization | initialization.py; at most five | Space create and replay-safe Wiki writes | Idempotent project initialize and seed bound | Core projects | Repeated initialization |
| Durable workflows | orchestrator.py; provider-bound safe writer | PostgreSQL transactions, bundles, unique keys | Logical run claims, lease fencing, phase receipts, uncertain invocation state | Core project service | Stale-owner denial/crash/readback |
| Primary monitoring | monitoring.py and main-topic-refresh | Sources/claims/Wiki; no monitoring ledger | Per-topic/day cycles, counters, coverage/watermark; no queue slots | Core projects | Full queue/no-news/failed check |
| Scheduling | cron templates, schedules.py; native Work tasks | UTC interval deterministic handlers; background OAuth | IANA calendar occurrences, DST policy and external-runner handoff | Core calendar / plugin | Rome gap/fold; host execution unverified |
| Agent integration | One personalized installed skill; skillgen.py | Instance-bound skill/plugin packaging | Project-bound skill and workflow templates | Existing plugin and client generator | No cross-project routing or mutation on read |
| Evidence review | evidence.py, evidence-quality.md, assessment schemas | Immutable passages, claims, exact-revision annotations | Workflow assessment contracts and citation validation | Core/agent references | Queued extraction denial; actual passage IDs |
| Adversarial review | ChallengeRecord; bounded contrary searches | Claims and annotations retain evidence | Bounded challenge state; semantic judgment external | Project records/plugin | Unsearched != searched; no truth by confidence |
| Synthesis | synthesize workflow; applicability/corrections | Wiki revisions, graph, claims, bundles, applicability | Result receipts and resume merge workflow | Core project service/plugin | Preserve contradictions/history |
| Wiki body safety | wiki.py; clean Markdown separate from JSON | Bounded Wiki Markdown + separate metadata | Regression guard for serialized page envelope in new workflows | Project publishing/parser | JSON envelope rejected |
| Reports | reporting.py, ReportPublisher | Replay-safe Wiki revisions/readback | Stable report membership, saved hash/revision, publication observations | Core projects / plugin | No omitted results; publication retry |
| Calendar | calendar.py, calendar schema | Typed objects | Project event contract; shared admission for resulting work | Project schemas/policy | Event/publication/retrieval times separate |
| Weekly structure | maintenance.py | Changes, references, claims, graph APIs | Bounded audit inventory and persistent checkpoints | Client audit / Core state | Incomplete inventory never complete audit |
| Semantic rotation | Risk plus persistent rotation cursor | Revision-specific verification | Reviewed IDs/cursor/coverage and agent handoff | Project maintenance records | Rotation progresses; no inherited verification |
| Archives | archive.py; lineage/evidence capsules | Wiki revision history; explicit archives | Peripheral expiry and compact summaries with retained refs | Core project policy/plugin | No silent reactivation |
| Release checks | releases.py; upgrade consent | Managed upstream/Core workflow with immutable releases | Bounded metadata check only; no automatic adoption | Client maintenance | Check failure is unknown; no code execution |
| Export | manifest.py, storage_migration.py | Page exports; native encrypted DB/files backup | Versioned project snapshot with integrity and mappings | Client export tools | Determinism/tamper/private selection |
| Static publishing | Selected wiki files | Markdown export | Explicit page/report allowlist; offline output | Client export tools | No publication or default public export |
| Recovery | SafeWriter intents/readback; provider generation | NS8 DB/files backup, restart, native update and receipts | Include project typed records; run/attempt recovery | Core + existing NS8 suite | DB restart/backup/upgrade; never live destruction |
| Project UI | Wiki/index driven | Readers, Tools, DOM rendering and race guards | Read-only selected-project overview linked to existing pages | app static/API | Access loss/late replies/Reader controls |
| Authentication | Host/provider capability gates | OAuth S256, background consent/rotation/revocation | Reuse existing client; no new credentials or permission bypass | c0_ingest auth and existing app | Expired/revoked authority fails closed |
| Notifications | DeliveryState separates saved/published/notified/read | No external notification observation API | Persist separate observed/unknown states | Report records/runner contract | Saved does not imply received |

## Sequential implementation and acceptance

M0 freezes this comparison and the architectural boundary. M1 implements validated project configuration/history, topics, authorization and reader overview. M2 extends reusable ingestion with adapters and incremental receipts. M3 implements atomic queue/run/attempt policy and fencing. M4 adds separately budgeted monitoring and external-agent/scheduler contracts. M5 persists evidence/results/reports and independent delivery observations. M6 adds calendar, bounded maintenance and lifecycle. M7 adds integrity-checked export and read-only synthetic migration preparation. M8 runs full compatibility, packaging, UI/native/recovery/privacy validation and records readiness.

Every milestone records actual focused tests, commit, push and completed CI before advancing. Runtime merge requires the current CI policy and exact-source merge gate; Core publication and adoption remain separate immutable gates. This task authorizes no dedicated-instance deployment or real migration, overriding older generic live milestone instructions. Live acceptance and scheduled-agent installation/execution remain explicitly unverified unless separately observed. No real project spaces, schedules, source writes or existing knowledge changes are permitted.

## M0 inspection evidence

Read C0 AGENTS/README/PLAN, reference/development/CI policy, feature/Core/ingestion skills, schema and service implementations, native lifecycle and plugin/ingestion contracts. Read WikiPlant AGENTS/README/PLAN, architecture/operations/hardening/evidence/storage/runtime documentation, required internal workflows, schemas, cron templates and deterministic helpers. C0 source API limit is 131072 UTF-8 bytes; object payload 64 KiB; immutable schemas; bundle 1–25 operations/262144 bytes; extraction is asynchronous; existing schedule intervals are UTC. Retain all limits.

Baseline full CI: [40289355200](https://github.com/Stell0/ns8-czero/actions/runs/40289355200), dispatched at exact C0 revision above; pending at this audit checkpoint. Existing same-source [40286224042](https://github.com/Stell0/ns8-czero/actions/runs/40286224042) is independently in progress. Neither is claimed successful. Disposable local PostgreSQL baseline setup is in progress.

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
