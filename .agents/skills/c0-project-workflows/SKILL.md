---
name: c0-project-workflows
description: Develop, review or verify protected C0 research-project manifests, queues, monitoring, evidence, reports, maintenance and project-bound agent skills.
---

Read AGENTS.md, the current PLAN.md and the relevant contracts in the [upstream project documentation](https://github.com/Stell0/ns8-czero/tree/main/docs/projects): PROJECTS.md, WORKFLOWS.md, MONITORING.md, REPORTING.md, MAINTENANCE.md and WIKIPLANT_MIGRATION_READINESS.md. Use matching local versions when present; standalone consumers do not bundle these application-specific documents. This is a developer skill; never bundle it with end-user skill packages. Use c0-develop-core for reusable Core changes, c0-create-feature for HTTP/UI and c0-ingest-sources for source adapters.

Begin with the actual published Core, app, schema, immutable source and target operation catalog. Do not mistake a merged commit for a deployed runtime or a refreshed ChatGPT tool catalog. Compare /agents/capabilities.json, /openapi.json, MCP discovery and real delegated scopes. Missing `project_*` operations block the workflow; never substitute generic objects, bundles, deterministic jobs or another C0 instance.

Project identity equals an existing protected space UUID. Preserve persisted roles, OAuth scopes, authorizing account, immutable types, original evidence identities and Wiki/result revisions. Configuration/user anchors require documented affirmative authorization. Project policy belongs in Core, not in plugin instructions. Managed project objects cannot be written through generic object operations.

For research, retain run identity, actor-bound lease, fencing generation, acknowledged manifest version, attempt reservation, invocation observation, evidence commits and completion as separate durable states. Reconcile uncertain external calls before retrying. Primary monitoring uses independent budgets and coverage watermarks; partial or failed checks cannot establish no material update. External models and agents perform reasoning; Core never executes arbitrary agent prompts or installs host schedules.

Reports and weekly maintenance must verify ready source passages and current Wiki revisions, preserve contrary evidence and bounded membership, handle calendar/DST, and resume safely. Distinguish SAVED, QUEUED, PARTIAL, BLOCKED, ACCEPTED_PENDING_MERGE and separate observed external publication, notification and human reading. Generated project-bound skill/plugin packages are private handoffs, not automatic task installations.

Test project authorization, actual PostgreSQL concurrency/fencing, migration/recovery, work budgets, source receipts, evidence/citation and report revision requirements, synthetic agents, archive generation and injection safety. Relevant suites include tests/integration/test_projects.py, test_project_workflows.py, test_project_monitoring.py, test_project_reports.py, test_project_maintenance.py and test_project_agents_http.py. Follow AGENTS.md and docs/ci-policy.md for full exact-source, native and release gates. Never migrate real WikiPlant data, activate tasks or modify production projects without separate authorization.
