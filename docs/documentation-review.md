# Documentation review — 8 November 2026

## Reviewed source and method

This audit started from original `Stell0/ns8-czero` main at `1db37f409af756212dc005d160302d01eff23098` (PR108). During candidate validation, PR109 regularly merged as `5a4a9739e4f06be142d6edd8ec938bf371be025a`. The final documentation successor starts from that exact new main in a separate isolated worktree. The initial `5c1e8502f9239a8068705c72019586a7467a2fbe` candidate and its running evidence remain frozen in PR110; no history is rewritten or native run cancelled. Existing dirty work, recovered worktrees and private evidence are preserved. Implementation and regression contracts take precedence over earlier prose.

Active manifests describe app0.63.0, producer Core0.45.0, schema0036 and plugin1.8.0. The app dependency and frozen lock still select released Core0.44.0 with `>=0.44.0,<0.45.0`. These are different identities. The latest dedicated deployment recorded in PLAN is the separately accepted app0.61/Core0.42/schema0034 checkpoint in [PLAN](../PLAN.md#openai-system-one-scoring--accepted-delivery). A source merge does not change that installation; this audit did not probe the live runtime. This review publishes no release, updates no live connector and installs no schedule.

Discovery covers current application routes and UI, Core services/migrations, operation catalog, configuration, packaged skills, external clients and focused regression tests. The inventory below maps user-visible behavior to evidence and documentation. Existing milestone evidence is retained with its source/generation context; it is not rewritten into a claim of current deployment.

## Feature-to-documentation inventory

| Feature | Implementation and regression evidence | Previous gap or correction | Documentation location |
| --- | --- | --- | --- |
| Agentic RAG / BYOA | [REST composition](../app/src/czero_app/main.py), [operation catalog](../app/src/czero_app/operations.py), [external compiler](../samples/ingestion/src/c0_compiler/runner.py) | Reasoning/storage separation existed but BYOA and Agentic RAG were not a clear entry point | [README](../README.md), [BYOA](byoa.md) |
| Wiki pages and immediate edits | [Wiki service](../packages/czero-core/src/czero_core/wiki.py), [transport](../app/src/czero_app/knowledge.py), [Wiki integration](../tests/integration/test_wiki_memory_http.py) | No complete creation/evolution guide; reader UI could be mistaken for an editor | [LLM Wiki](llm-wiki.md), [user guide](user-guide.md) |
| Complete current documents | [Document service](../packages/czero-core/src/czero_core/documents.py), [full-document tests](../tests/integration/test_full_documents.py) | Old Knowledge Explorer labels remained in a current guide | [Full documents](full-documents.md), [architecture](architecture.md) |
| Latest-only evidence | [Current content](../packages/czero-core/src/czero_core/current_content.py), [migration0023](../packages/czero-core/src/czero_core/migrations/versions/0023_current_content.py) | Introductory narrative mixed stable links, exact citations and history wording | [README](../README.md), [migration guide](latest-only-migration.md) |
| Source upload and replacement | [Source HTTP](../app/src/czero_app/sources.py), [source browser tests](../tests/e2e/test_document_explorer.py) | Full ingestion flow and retention choices needed a current overview | [Architecture](architecture.md), [user guide](user-guide.md) |
| Queued extraction, selective retries and OCR | [Queue](../packages/czero-core/src/czero_core/extraction_queue.py), [native defaults](../imageroot/bin/czero_extraction_config.py), [progress browser](../tests/e2e/test_extraction_progress.py) | README repeated ten milestone narratives instead of explaining defaults and opt-ins | [Architecture](architecture.md), [administration](administration.md), [rollout](ingestion-pipeline/ROLLOUT.md) |
| Exact outline/section/reference context | [Context service](../packages/czero-core/src/czero_core/document_context.py), [HTTP tests](../tests/integration/test_document_context_http.py) | Current reference still titled this a producer-only candidate | [Interface reference](reference.md), [BYOA](byoa.md) |
| Document BM25 and hybrid retrieval | [BM25](../packages/czero-core/src/czero_core/bm25.py), [retrieval](../packages/czero-core/src/czero_core/retrieval.py), [BM25 tests](../tests/integration/test_document_bm25.py) | Recent implementation appeared after historical version notes; exact versus relevance selection unclear in entry point | [README](../README.md), [retrieval measurements](retrieval-benchmark.md), [architecture](architecture.md) |
| Optional embedding/scoring | [Provider config](../packages/czero-core/src/czero_core/retrieval_config.py), [native config](../imageroot/bin/czero_retrieval_config.py), [scoring](../packages/czero-core/src/czero_core/providers.py) | Configuration details buried under fork instructions | [Administration](administration.md), [retrieval guide](retrieval-benchmark.md) |
| Entities, claims, annotations and typed records | [Knowledge](../packages/czero-core/src/czero_core/knowledge.py), [annotations](../packages/czero-core/src/czero_core/annotations.py), [objects](../packages/czero-core/src/czero_core/objects.py) | Missing single current data-model diagram outside the long README | [Architecture](architecture.md), [reference](reference.md) |
| Space roles and delegated scopes | [Space service](../packages/czero-core/src/czero_core/spaces.py), [access](../packages/czero-core/src/czero_core/access.py), [space tests](../tests/integration/test_spaces_http.py) | Needed explicit role/scope separation in Wiki setup and maintenance | [BYOA](byoa.md), [LLM Wiki](llm-wiki.md), [workspace access](workspace-access.md) |
| OAuth, client approval and background access | [OAuth](../packages/czero-core/src/czero_core/oauth_grants.py), [onboarding](../packages/czero-core/src/czero_core/client_onboarding.py), [sessions](../packages/czero-core/src/czero_core/sessions.py) | ChatGPT guide named an obsolete administration route | [ChatGPT](chatgpt.md), [administration](administration.md) |
| Remembered browser access | [Sessions](../packages/czero-core/src/czero_core/sessions.py), [browser website](../tests/e2e/test_vue_website.py) | User/admin guides still called accepted source a pending candidate | [User guide](user-guide.md), [administration](administration.md) |
| Personal API keys | [Key service](../packages/czero-core/src/czero_core/api_keys.py), [browser tests](../tests/e2e/test_api_keys.py) | Important automation route was a short late README note | [README](../README.md), [BYOA](byoa.md), [key guide](api-keys.md) |
| Plugin/skills and selected-space prompts | [Agent guidance](../app/src/czero_app/agent_guidance.py), [Agents UI](../app/frontend/src/views/AgentsView.vue), [package tests](../tests/unit/test_plugin_package.py) | Needed distinction among package content, actual tools and permission; developer guide incorrectly excluded end-user templates from runtime | [Plugin](plugin.md), [BYOA](byoa.md), [development](development.md) |
| Read-only searches and post-answer feedback | [Read-only search handler](../app/src/czero_app/retrieval.py), [external helper](../packages/czero-core/src/czero_core/compilation_client.py), [feedback tests](../tests/integration/test_compilation_feedback_http.py) | No complete user explanation of the separate optional proposal write | [LLM Wiki trigger table](llm-wiki.md#what-happens-after-a-search) |
| Compiler policy, validation and publication | [Policy](../packages/czero-core/src/czero_core/compilation_schema.py), [publication](../packages/czero-core/src/czero_core/compilation_plans.py), [publication tests](../tests/integration/test_compilation_plans.py) | Core README said M2 publication was unavailable; reference described only ten M1 adapters | [LLM Wiki](llm-wiki.md), [reference](reference.md), [Core README](../packages/czero-core/README.md) |
| Incremental discovery and semantic review | [Maintenance service](../packages/czero-core/src/czero_core/compilation_maintenance.py), [maintenance tests](../tests/integration/test_compilation_maintenance.py) | Needed current lifecycle, partial coverage and no-change behavior | [LLM Wiki](llm-wiki.md), [operations](knowledge-compilation/OPERATIONS.md) |
| External scheduled compiler | [Runner](../samples/ingestion/src/c0_compiler/runner.py), [CLI](../samples/ingestion/src/c0_compiler/cli.py), [HTTP runner tests](../tests/integration/test_compiler_runner_http.py) | No unified ChatGPT/Codex/Claude/custom-host guide or reusable prompts | [Maintenance](wiki-maintenance.md), [runner setup](../samples/ingestion/examples/compiler/README.md) |
| Protected projects and reports | [Project schema](../packages/czero-core/src/czero_core/project_schema.py), [workflows](../packages/czero-core/src/czero_core/project_workflows.py), [reports](../packages/czero-core/src/czero_core/project_reports.py) | Distribution section presented original0.34 dependency as current | [LLM Wiki project setup](llm-wiki.md#configure-a-protected-research-project), [project contracts](projects/PROJECTS.md) |
| Pruning and consolidation limits | [Finite compiler operations](../packages/czero-core/src/czero_core/compilation_plans.py), [project maintenance](../packages/czero-core/src/czero_core/project_maintenance.py) | General automatic pruning could be inferred from maintenance language | [LLM Wiki](llm-wiki.md#how-knowledge-evolves), [weekly prompt](wiki-maintenance.md#weekly-maintenance) |
| Current Vue reader and native settings | [Router](../app/frontend/src/router.ts), [theme/browser checks](../tests/e2e/test_nebula_theme.py), [native UI](../ui/src/App.vue) | Old UI names and presentation/runtime distinctions needed correction | [README](../README.md), [website contract](vue-website.md) |
| Installation and release identity | [App manifest](../app/pyproject.toml), [lock](../app/uv.lock), [producer manifest](../packages/czero-core/pyproject.toml), [source acceptance](../PLAN.md) | Installation entry still recommended M19; release checklist read as current despite later deployments | [Candidate selection](installation-candidate.md), [readiness](release-readiness.md) |
| Fork development and contributions | [Managed registry](../c0-upstream.json), [fork generator](../examples/fork/create.py), [CI policy](ci-policy.md) | Useful detailed README workflow needed a durable technical home | [Development](development.md#build-an-application-on-c0) |
| Evaluation versus product quality | [Controlled evaluation](../scripts/evaluate-agentic-retrieval.py), [published BM25 measurements](retrieval-benchmark.md), [M6 results](knowledge-compilation/RESULTS.md) | Compiler quality failure was not prominent at entry point | [README](../README.md), [readiness](release-readiness.md) |

## Latest-main compatibility review

PR109 changes application resource cleanup, propagates process-control exceptions after client cleanup, removes selected unused imports and corrects the native extraction runner's module description. Its new tests exercise failed cleanup and interrupted client startup. The review confirms no public endpoint/tool/schema, role/scope, Core package, dependency lock, migration or managed-file baseline changes. The existing native timer and source/knowledge/retrieval behavior remain as documented. [CODEBASE_REVIEW](../CODEBASE_REVIEW.md) retains that work's actual source/test observations, including its local prerequisite failures; it is not a current setup guide.

## Diagram review

All four pre-existing Mermaid blocks were reviewed. The two README diagrams were replaced by current system/BYOA diagrams and a dedicated knowledge-model diagram. The compiler plan's selected-architecture diagram now shows read-only retrieval, separate optional agent feedback and review holds. Its M0→M6 dependency diagram remains correct as a historical milestone order and is retained.

New [architecture diagrams](architecture.md) show knowledge structure, ingestion and retrieval. The [Wiki lifecycle](llm-wiki.md#how-knowledge-evolves) shows explicit publication and verification boundaries. Total: eight Mermaid blocks, including the preserved milestone graph. Labels use GitHub-supported flowchart syntax and quoted labels where needed.

## Important gaps and limits

- Ordinary Wiki scope pages are agent guidance, not an enforced topic taxonomy. Protected project manifests provide additional structural governance. There is no dedicated Wiki creation form or browser Wiki editor.
- Search never publishes knowledge or queues learning. Optional agent-side feedback can queue a proposal after answering; compatible host continuation is required. There is no hidden server model run.
- Compiler structural validation is not semantic truth. Its latest bounded quality study failed its evidence/citation/applicability gates. No automatic learning rollout or retrieval-quality improvement is accepted by that result.
- General automatic destructive pruning is not implemented in compiler profiles. Project peripheral-topic archival is a separate bounded operation; ordinary archive/retract actions need explicit authority.
- The producer-only weekly selected-page inference input is not established by the released Core0.44 consumer pin. Discover actual inputs; do not silently use local Core or claim availability from the plugin version.
- Vendor documentation establishes scheduling interfaces, not C0-specific unattended acceptance. Claude acceptance, ChatGPT packaged-skill account routes and unattended writes need actual host evidence. Unknown credentials/host availability cannot be resolved by documentation or fake clocks.
- Source collection needs an external collector/agent and its source permissions. C0 has no generic URL-fetching conversational worker. Existing deterministic extraction/indexing schedules do not schedule AI reasoning.

## Documentation coverage

The inventory includes root guidance; every Markdown file under docs; package/native/fork READMEs; repository and end-user skills; sample and benchmark guides; and synthetic fixture notes. Relative links/anchors are checked across this complete set. Historical records retain their frozen commands, source identities and failures; current guides identify them as evidence. No historical or private acceptance record is deleted.

The following file-level coverage list records the latest-base pre-edit Markdown inventory (120 files). “Contract/evidence” identifies generation-bound designs, milestone observations or synthetic fixtures; it is not a current setup recommendation. “Workflow” includes packaged agent instructions and developer routing. Detailed runtime workflows are reused rather than copied into new scripts.

| Document | Review disposition |
| --- | --- |
| [.agents/references/development.md](../.agents/references/development.md) | Workflow; checked against current boundaries |
| [.agents/skills/c0-benchmark-agentic-retrieval/SKILL.md](../.agents/skills/c0-benchmark-agentic-retrieval/SKILL.md) | Workflow; checked against current boundaries |
| [.agents/skills/c0-contribute-upstream/SKILL.md](../.agents/skills/c0-contribute-upstream/SKILL.md) | Workflow; checked against current boundaries |
| [.agents/skills/c0-create-feature/SKILL.md](../.agents/skills/c0-create-feature/SKILL.md) | Workflow; checked against current boundaries |
| [.agents/skills/c0-develop-core/SKILL.md](../.agents/skills/c0-develop-core/SKILL.md) | Workflow; checked against current boundaries |
| [.agents/skills/c0-evaluate-tools/SKILL.md](../.agents/skills/c0-evaluate-tools/SKILL.md) | Workflow; checked against current boundaries |
| [.agents/skills/c0-generate-retrieval-questions/SKILL.md](../.agents/skills/c0-generate-retrieval-questions/SKILL.md) | Workflow; checked against current boundaries |
| [.agents/skills/c0-ingest-sources/SKILL.md](../.agents/skills/c0-ingest-sources/SKILL.md) | Workflow; checked against current boundaries |
| [.agents/skills/c0-maintain-semantic-layer/SKILL.md](../.agents/skills/c0-maintain-semantic-layer/SKILL.md) | Workflow; checked against current boundaries |
| [.agents/skills/c0-project-workflows/SKILL.md](../.agents/skills/c0-project-workflows/SKILL.md) | Workflow; checked against current boundaries |
| [.agents/skills/c0-upgrade-from-upstream/SKILL.md](../.agents/skills/c0-upgrade-from-upstream/SKILL.md) | Workflow; checked against current boundaries |
| [AGENTS.md](../AGENTS.md) | Workflow; checked against current boundaries |
| [CODEBASE_REVIEW.md](../CODEBASE_REVIEW.md) | Contract/evidence from merged PR109; retain its frozen checkpoints |
| [PLAN.md](../PLAN.md) | Roadmap/evidence; retain immutable checkpoints |
| [README.md](../README.md) | Current guide/navigation; compare with implementation |
| [app/frontend/licenses/README.md](../app/frontend/licenses/README.md) | Current guide/navigation; compare with implementation |
| [benchmarks/retrieval/README.md](../benchmarks/retrieval/README.md) | Reusable example; check command and scope contracts |
| [docs/administration.md](administration.md) | Current guide/navigation; compare with implementation |
| [docs/agentic-retrieval.md](agentic-retrieval.md) | Current guide/navigation; compare with implementation |
| [docs/api-keys.md](api-keys.md) | Current guide/navigation; compare with implementation |
| [docs/c0-agent-memory-baseline.md](c0-agent-memory-baseline.md) | Contract/evidence; retain generation context |
| [docs/chatgpt.md](chatgpt.md) | Current guide/navigation; compare with implementation |
| [docs/ci-policy.md](ci-policy.md) | Current guide/navigation; compare with implementation |
| [docs/development.md](development.md) | Current guide/navigation; compare with implementation |
| [docs/full-documents.md](full-documents.md) | Current guide/navigation; compare with implementation |
| [docs/history/AGENTS.md](history/AGENTS.md) | Contract/evidence; retain generation context |
| [docs/history/PLAN.md](history/PLAN.md) | Contract/evidence; retain generation context |
| [docs/history/README.md](history/README.md) | Contract/evidence; retain generation context |
| [docs/index.md](index.md) | Current guide/navigation; compare with implementation |
| [docs/ingestion-pipeline/BASELINE.md](ingestion-pipeline/BASELINE.md) | Contract/evidence; retain generation context |
| [docs/ingestion-pipeline/CONTRACTS.md](ingestion-pipeline/CONTRACTS.md) | Contract/evidence; retain generation context |
| [docs/ingestion-pipeline/M1.md](ingestion-pipeline/M1.md) | Contract/evidence; retain generation context |
| [docs/ingestion-pipeline/M10.md](ingestion-pipeline/M10.md) | Contract/evidence; retain generation context |
| [docs/ingestion-pipeline/M2.md](ingestion-pipeline/M2.md) | Contract/evidence; retain generation context |
| [docs/ingestion-pipeline/M3.md](ingestion-pipeline/M3.md) | Contract/evidence; retain generation context |
| [docs/ingestion-pipeline/M4.md](ingestion-pipeline/M4.md) | Contract/evidence; retain generation context |
| [docs/ingestion-pipeline/M5.md](ingestion-pipeline/M5.md) | Contract/evidence; retain generation context |
| [docs/ingestion-pipeline/M6.md](ingestion-pipeline/M6.md) | Contract/evidence; retain generation context |
| [docs/ingestion-pipeline/M7.md](ingestion-pipeline/M7.md) | Contract/evidence; retain generation context |
| [docs/ingestion-pipeline/M8.md](ingestion-pipeline/M8.md) | Contract/evidence; retain generation context |
| [docs/ingestion-pipeline/M9.md](ingestion-pipeline/M9.md) | Contract/evidence; retain generation context |
| [docs/ingestion-pipeline/PLAN.md](ingestion-pipeline/PLAN.md) | Contract/evidence; retain generation context |
| [docs/ingestion-pipeline/ROLLOUT.md](ingestion-pipeline/ROLLOUT.md) | Contract/evidence; retain generation context |
| [docs/installation-candidate.md](installation-candidate.md) | Current guide/navigation; compare with implementation |
| [docs/knowledge-compilation/BASELINE.md](knowledge-compilation/BASELINE.md) | Contract/evidence; retain generation context |
| [docs/knowledge-compilation/CONTRACTS.md](knowledge-compilation/CONTRACTS.md) | Contract/evidence; retain generation context |
| [docs/knowledge-compilation/M1.md](knowledge-compilation/M1.md) | Contract/evidence; retain generation context |
| [docs/knowledge-compilation/M2.md](knowledge-compilation/M2.md) | Contract/evidence; retain generation context |
| [docs/knowledge-compilation/M3.md](knowledge-compilation/M3.md) | Contract/evidence; retain generation context |
| [docs/knowledge-compilation/M4.md](knowledge-compilation/M4.md) | Contract/evidence; retain generation context |
| [docs/knowledge-compilation/M5.md](knowledge-compilation/M5.md) | Contract/evidence; retain generation context |
| [docs/knowledge-compilation/M6.md](knowledge-compilation/M6.md) | Contract/evidence; retain generation context |
| [docs/knowledge-compilation/OPERATIONS.md](knowledge-compilation/OPERATIONS.md) | Contract/evidence; retain generation context |
| [docs/knowledge-compilation/PLAN.md](knowledge-compilation/PLAN.md) | Contract/evidence; retain generation context |
| [docs/knowledge-compilation/RESULTS.md](knowledge-compilation/RESULTS.md) | Contract/evidence; retain generation context |
| [docs/latest-only-migration.md](latest-only-migration.md) | Current guide/navigation; compare with implementation |
| [docs/m14-readiness.md](m14-readiness.md) | Contract/evidence; retain generation context |
| [docs/m14-release-notes.md](m14-release-notes.md) | Contract/evidence; retain generation context |
| [docs/plugin.md](plugin.md) | Current guide/navigation; compare with implementation |
| [docs/projects/EXPORTS.md](projects/EXPORTS.md) | Current guide/navigation; compare with implementation |
| [docs/projects/MAINTENANCE.md](projects/MAINTENANCE.md) | Current guide/navigation; compare with implementation |
| [docs/projects/MONITORING.md](projects/MONITORING.md) | Current guide/navigation; compare with implementation |
| [docs/projects/PROJECTS.md](projects/PROJECTS.md) | Current guide/navigation; compare with implementation |
| [docs/projects/REPORTING.md](projects/REPORTING.md) | Current guide/navigation; compare with implementation |
| [docs/projects/SOURCES.md](projects/SOURCES.md) | Current guide/navigation; compare with implementation |
| [docs/projects/WIKIPLANT_COMPATIBILITY.md](projects/WIKIPLANT_COMPATIBILITY.md) | Contract/evidence; retain generation context |
| [docs/projects/WIKIPLANT_MIGRATION_READINESS.md](projects/WIKIPLANT_MIGRATION_READINESS.md) | Contract/evidence; retain generation context |
| [docs/projects/WORKFLOWS.md](projects/WORKFLOWS.md) | Current guide/navigation; compare with implementation |
| [docs/reference.md](reference.md) | Current guide/navigation; compare with implementation |
| [docs/release-readiness.md](release-readiness.md) | Current guide/navigation; compare with implementation |
| [docs/retrieval-benchmark.md](retrieval-benchmark.md) | Current guide/navigation; compare with implementation |
| [docs/tool-evaluations.md](tool-evaluations.md) | Current guide/navigation; compare with implementation |
| [docs/user-guide.md](user-guide.md) | Current guide/navigation; compare with implementation |
| [docs/vue-website.md](vue-website.md) | Current guide/navigation; compare with implementation |
| [docs/workspace-access.md](workspace-access.md) | Current guide/navigation; compare with implementation |
| [examples/fork/AGENTS.md](../examples/fork/AGENTS.md) | Workflow; checked against current boundaries |
| [examples/fork/PLAN.md](../examples/fork/PLAN.md) | Roadmap/evidence; retain immutable checkpoints |
| [examples/fork/README.md](../examples/fork/README.md) | Reusable example; check command and scope contracts |
| [packages/czero-core/README.md](../packages/czero-core/README.md) | Current guide/navigation; compare with implementation |
| [plugins/c0-knowledge/memory-skill.md](../plugins/c0-knowledge/memory-skill.md) | Workflow; checked against current boundaries |
| [plugins/c0-knowledge/project/daily.md](../plugins/c0-knowledge/project/daily.md) | Workflow; checked against current boundaries |
| [plugins/c0-knowledge/project/recovery.md](../plugins/c0-knowledge/project/recovery.md) | Workflow; checked against current boundaries |
| [plugins/c0-knowledge/project/scheduler.md](../plugins/c0-knowledge/project/scheduler.md) | Workflow; checked against current boundaries |
| [plugins/c0-knowledge/project/skill.md](../plugins/c0-knowledge/project/skill.md) | Workflow; checked against current boundaries |
| [plugins/c0-knowledge/project/weekly.md](../plugins/c0-knowledge/project/weekly.md) | Workflow; checked against current boundaries |
| [plugins/c0-knowledge/project/workflows.md](../plugins/c0-knowledge/project/workflows.md) | Workflow; checked against current boundaries |
| [plugins/c0-knowledge/references/compiler.md](../plugins/c0-knowledge/references/compiler.md) | Workflow; checked against current boundaries |
| [plugins/c0-knowledge/references/connection.md](../plugins/c0-knowledge/references/connection.md) | Workflow; checked against current boundaries |
| [plugins/c0-knowledge/references/instance.md](../plugins/c0-knowledge/references/instance.md) | Workflow; checked against current boundaries |
| [plugins/c0-knowledge/references/maintenance.md](../plugins/c0-knowledge/references/maintenance.md) | Workflow; checked against current boundaries |
| [plugins/c0-knowledge/references/projects.md](../plugins/c0-knowledge/references/projects.md) | Workflow; checked against current boundaries |
| [plugins/c0-knowledge/references/scheduling.md](../plugins/c0-knowledge/references/scheduling.md) | Workflow; checked against current boundaries |
| [plugins/c0-knowledge/skills/c0-knowledge-compiler/SKILL.md](../plugins/c0-knowledge/skills/c0-knowledge-compiler/SKILL.md) | Workflow; checked against current boundaries |
| [plugins/c0-knowledge/skills/c0-maintain-knowledge/SKILL.md](../plugins/c0-knowledge/skills/c0-maintain-knowledge/SKILL.md) | Workflow; checked against current boundaries |
| [plugins/c0-knowledge/skills/c0-projects/SKILL.md](../plugins/c0-knowledge/skills/c0-projects/SKILL.md) | Workflow; checked against current boundaries |
| [plugins/c0-knowledge/skills/c0-research/SKILL.md](../plugins/c0-knowledge/skills/c0-research/SKILL.md) | Workflow; checked against current boundaries |
| [plugins/c0-knowledge/skills/c0-setup/SKILL.md](../plugins/c0-knowledge/skills/c0-setup/SKILL.md) | Workflow; checked against current boundaries |
| [samples/ingestion/README.md](../samples/ingestion/README.md) | Reusable example; check command and scope contracts |
| [samples/ingestion/examples/compiler/README.md](../samples/ingestion/examples/compiler/README.md) | Reusable example; check command and scope contracts |
| [samples/ingestion/examples/projects/README.md](../samples/ingestion/examples/projects/README.md) | Reusable example; check command and scope contracts |
| [samples/ingestion/examples/projects/myprojects/inputs/synthetic.md](../samples/ingestion/examples/projects/myprojects/inputs/synthetic.md) | Reusable example; check command and scope contracts |
| [samples/ingestion/examples/projects/robotelier/inputs/synthetic.md](../samples/ingestion/examples/projects/robotelier/inputs/synthetic.md) | Reusable example; check command and scope contracts |
| [samples/ingestion/examples/website/BENCHMARK.md](../samples/ingestion/examples/website/BENCHMARK.md) | Reusable example; check command and scope contracts |
| [samples/ingestion/examples/website/README.md](../samples/ingestion/examples/website/README.md) | Reusable example; check command and scope contracts |
| [tests/fixtures/evidence/README.md](../tests/fixtures/evidence/README.md) | Contract/evidence; retain generation context |
| [tests/fixtures/evidence/pipeline/README.md](../tests/fixtures/evidence/pipeline/README.md) | Contract/evidence; retain generation context |
| [tests/fixtures/evidence/pipeline/fenced.md](../tests/fixtures/evidence/pipeline/fenced.md) | Contract/evidence; retain generation context |
| [tests/fixtures/evidence/pipeline/multipart.md](../tests/fixtures/evidence/pipeline/multipart.md) | Contract/evidence; retain generation context |
| [tests/fixtures/evidence/sample.md](../tests/fixtures/evidence/sample.md) | Contract/evidence; retain generation context |
| [tests/fixtures/knowledge_compilation/README.md](../tests/fixtures/knowledge_compilation/README.md) | Contract/evidence; retain generation context |
| [tests/fixtures/wikiplant/README.md](../tests/fixtures/wikiplant/README.md) | Contract/evidence; retain generation context |
| [tests/fixtures/wikiplant/myprojects/data/SCOPE.md](../tests/fixtures/wikiplant/myprojects/data/SCOPE.md) | Contract/evidence; retain generation context |
| [tests/fixtures/wikiplant/myprojects/data/TOPICS.md](../tests/fixtures/wikiplant/myprojects/data/TOPICS.md) | Contract/evidence; retain generation context |
| [tests/fixtures/wikiplant/myprojects/data/reports/2026-10-10.md](../tests/fixtures/wikiplant/myprojects/data/reports/2026-10-10.md) | Contract/evidence; retain generation context |
| [tests/fixtures/wikiplant/myprojects/data/wiki/concepts/wiki-1.md](../tests/fixtures/wikiplant/myprojects/data/wiki/concepts/wiki-1.md) | Contract/evidence; retain generation context |
| [tests/fixtures/wikiplant/robotelier/data/SCOPE.md](../tests/fixtures/wikiplant/robotelier/data/SCOPE.md) | Contract/evidence; retain generation context |
| [tests/fixtures/wikiplant/robotelier/data/TOPICS.md](../tests/fixtures/wikiplant/robotelier/data/TOPICS.md) | Contract/evidence; retain generation context |
| [tests/fixtures/wikiplant/robotelier/data/reports/2026-10-10.md](../tests/fixtures/wikiplant/robotelier/data/reports/2026-10-10.md) | Contract/evidence; retain generation context |
| [tests/fixtures/wikiplant/robotelier/data/wiki/concepts/wiki-1.md](../tests/fixtures/wikiplant/robotelier/data/wiki/concepts/wiki-1.md) | Contract/evidence; retain generation context |
| [ui/README.md](../ui/README.md) | Current guide/navigation; compare with implementation |

## Validation record

The original maintained-document check passes 411 local links at the frozen base. The same checker applied to all 119 pre-edit Markdown files reports no broken local links or anchors. Candidate validation passes all 125 repository Markdown files and 888 local links/anchors, including preserved historical anchors and the five new guides. The default maintained-document check passes 717 local links.

The initial focused suite passed 68 tests on both original main and the first candidate. After PR109, the expanded suite passes 80 tests on exact new main and the successor, including the shared ingestion-client regression tests: documentation navigation/anchors, fork references, generated plugin packages and post-answer feedback safeguards. Documented MCP names were checked against actual registrations, including the profile handler's direct catalog binding. Compiler CLI and Codex MCP command flags were checked through local `--help`; source/settings examples were compared with active schemas. All eight Mermaid blocks parse and render with Mermaid CLI12.2.0 and Chromium. The eight diagram blocks are byte-identical on the new base. No Mermaid dependency or generated diagram image is added to the project. The 22 public vendor/manual URLs checked return success; the documented immutable installation tag exists and its registry module digest matches.

The first candidate link check identified three incorrect implementation-evidence paths, which were corrected before the passing checks. Initial system/minimal Python runs could not import Core dependencies; the equipped app test environment supplies the passing before/after result. The first browser-render attempt could not use the quota-limited temporary directory; a private shared-memory temporary directory supplied the successful render. These failures are not counted as passes. Selected exact-source CI acceptance is reported in the PR separately.

Install, live connector, model inference, source ingestion and external schedule activation examples are checked against schemas, code, tests and current primary vendor instructions. They are not executed against production as part of this documentation task. No claim of a live installation, scheduled run or new package acceptance follows from static checks.
