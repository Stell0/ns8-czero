# C0 documentation

C0 (CZero) is a self-hosted knowledge service and Agentic RAG platform. Bring Your Own Agent (BYOA): C0 stores knowledge and enforces access; your external agent reasons, retrieves and makes authorized changes.

| I want to… | Read |
| --- | --- |
| Understand the product and BYOA | [README](../README.md), [agent connection guide](byoa.md) |
| Create a Wiki and understand when it changes | [LLM Wiki](llm-wiki.md) |
| Arrange daily/weekly external maintenance | [Scheduling, verification and prompts](wiki-maintenance.md) |
| Read knowledge or upload sources | [User guide](user-guide.md), [complete documents](full-documents.md) |
| Connect ChatGPT or package instructions | [ChatGPT setup](chatgpt.md), [plugin packages](plugin.md) |
| Install or operate an instance | [Administration](administration.md), [candidate selection](installation-candidate.md) |
| Manage people, applications and spaces | [Workspace access](workspace-access.md) |
| Use REST/MCP or automation keys | [Interface reference](reference.md), [API keys](api-keys.md) |
| Understand storage, ingestion and retrieval | [Architecture](architecture.md), [retrieval behavior and measurements](retrieval-benchmark.md) |
| Collect source data | [Ingestion samples](../samples/ingestion/README.md), [website recipe](../samples/ingestion/examples/website/README.md) |
| Configure protected research workflows | [Projects](projects/PROJECTS.md), [monitoring](projects/MONITORING.md), [reports](projects/REPORTING.md) |
| Operate or recover bounded compilation | [Compiler operations](knowledge-compilation/OPERATIONS.md), [external runner](../samples/ingestion/examples/compiler/README.md) |
| Extend C0 or maintain a fork | [Development and contributing](development.md), [coding-agent instructions](../AGENTS.md) |
| Evaluate tools or retrieval | [Tool evaluations](tool-evaluations.md), [controlled Agentic RAG experiments](agentic-retrieval.md), [BEIR runner](../benchmarks/retrieval/README.md) |
| Check remaining release gates | [Release readiness](release-readiness.md), [compiler quality results](knowledge-compilation/RESULTS.md) |
| Inspect the documentation audit | [Feature evidence, discrepancies and diagram review](documentation-review.md) |

## Implementation and acceptance records

[PLAN](../PLAN.md#roadmap) records current priorities and exact source/image acceptance. [CI policy](ci-policy.md) defines required validation. An accepted source, a published Core artifact and an installed runtime are separate states.

The [Vue website contract](vue-website.md), [extraction milestone records](ingestion-pipeline/PLAN.md), [compiler milestone records](knowledge-compilation/PLAN.md) and [WikiPlant audit](projects/WIKIPLANT_COMPATIBILITY.md) retain generation-specific design and evidence. Use the guides above for current setup. Milestone plans are not assertions that every planned capability is released or enabled. [Historical evidence](history/PLAN.md) remains available with its original identities and limitations.

- [Secure cross-space reference contract](cross-space-references-plan.md)
