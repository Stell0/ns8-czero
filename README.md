# C0 (Czero) — Knowledge for people and AI assistants

The approved people-first [Workspace access page](docs/workspace-access.md) is implemented on an isolated branch; final distribution/native/live acceptance is pending.
It keeps application approval, user roles and individual connection disconnect
separate. Core0.33/schema0021 provides the supporting bounded administration
operations; the deployed runtime and PR33 stay frozen during implementation.
No access-page browser/native/live acceptance is claimed yet. See [PLAN](PLAN.md).


C0 is a knowledge application for NethServer 8. Read a Wiki, retain original source passages and citations, and let an authorized AI assistant research or maintain that knowledge through MCP. Reader, Editor and Admin membership controls access, including protected knowledge spaces. Optional inference helps retrieval; it does not control authorization.

## Start here

- **Use an existing instance:** [read and maintain knowledge](docs/user-guide.md).
- **Connect your own ChatGPT:** [setup and troubleshooting](docs/chatgpt.md).
- **Install an instance:** [administrator guide](docs/administration.md).
- **Add task skills in ChatGPT web:** [private and managed plugin setup](docs/plugin.md).
- **Develop a fork or contribute:** [development guide](docs/development.md).
- **Find interfaces and limits:** [reference](docs/reference.md).

Use your administrator's HTTPS C0 address and your own NethServer sign-in. ChatGPT app installation, C0 client approval, account membership and OAuth consent are separate steps. Never share credentials or a full authorization URL in a conversation.

## Status and boundaries

PR32 self-service onboarding is merged with verified main/publication and native artifacts. The dedicated instance now runs the frozen PR33 background-connection candidate, app **0.51.0**, Core **0.32.0**, schema **0020**, after native and server preservation/renewal/revocation acceptance. Actual ChatGPT reuse beyond24 hours and PR33 review remain pending. Background access uses explicit consent, thirty-day inactivity, short access tokens and effective revocation. The people-first access candidate is app **0.52.0** with independently published Core **0.33.0**, schema **0021**; final app CI/native/live acceptance remains pending. The operator previously confirmed ChatGPT connection/read; packaged-skill use and remaining model evaluations are separate gates. [Release readiness](docs/release-readiness.md) records the remaining work. No stable NS8 module release or public plugin-directory listing is claimed.

C0 provides browser readers/tools, authenticated REST/OpenAPI and OAuth-protected MCP. Selected plain text can be ingested through MCP; document-file upload uses REST or Source tools. Authorized changes publish immediately with retained revisions and evidence. C0 does not execute arbitrary assistant commands or provide a general workflow engine.

See the [current roadmap and accepted runtime](PLAN.md), [documentation index](docs/index.md) and [historical evidence](docs/history/PLAN.md). Public examples use fictional identities; configure your own hostname and registered ChatGPT app.

## License and sources

C0 and its reusable Core use [GPL-3.0-or-later](LICENSE). NethServer development conventions are maintained in the [Development Handbook](https://handbook.nethserver.org/) and [NethServer agent skills](https://github.com/NethServer/agents).

<details>
<summary>Historical section links</summary>

These anchors preserve links to the retained historical record.

<a id="c0-czero--application-foundation-for-nethserver-8"></a>[C0 (Czero) — Application foundation for NethServer 8](docs/history/README.md#c0-czero--application-foundation-for-nethserver-8)

<a id="historical-m20-renewal-acceptance"></a>[Historical M20 renewal acceptance](docs/history/README.md#historical-m20-renewal-acceptance)

<a id="accepted-m17-profile-identity"></a>[Accepted M17 profile identity](docs/history/README.md#accepted-m17-profile-identity)

<a id="historical-m18-tool-guidance"></a>[Historical M18 tool guidance](docs/history/README.md#historical-m18-tool-guidance)

<a id="current-runtime-m19-client-metadata-discovery"></a>[Current runtime: M19 client metadata discovery](docs/history/README.md#current-runtime-m19-client-metadata-discovery)

<a id="applicability-and-structured-retrieval-am4"></a>[Applicability and structured retrieval (AM4)](docs/history/README.md#applicability-and-structured-retrieval-am4)

<a id="purpose-and-boundaries"></a>[Purpose and boundaries](docs/history/README.md#purpose-and-boundaries)

<a id="current-interfaces"></a>[Current interfaces](docs/history/README.md#current-interfaces)

<a id="knowledge-website-m15-accepted"></a>[Knowledge website (M15 accepted)](docs/history/README.md#knowledge-website-m15-accepted)

<a id="install-and-configure"></a>[Install and configure](docs/history/README.md#install-and-configure)

<a id="sign-in-and-sharing"></a>[Sign-in and sharing](docs/history/README.md#sign-in-and-sharing)

<a id="persistence-and-backup"></a>[Persistence and backup](docs/history/README.md#persistence-and-backup)

<a id="remaining-roadmap"></a>[Remaining roadmap](docs/history/README.md#remaining-roadmap)

<a id="development-and-verification"></a>[Development and verification](docs/history/README.md#development-and-verification)

<a id="nethserver-sources-and-license"></a>[NethServer sources and license](docs/history/README.md#nethserver-sources-and-license)

<a id="forks-and-core-distribution"></a>[Forks and Core distribution](docs/history/README.md#forks-and-core-distribution)

<a id="agent-memory-development-track"></a>[Agent memory development track](docs/history/README.md#agent-memory-development-track)

<a id="agent-workflow-guidance-am6-accepted"></a>[Agent workflow guidance (AM6 accepted)](docs/history/README.md#agent-workflow-guidance-am6-accepted)

<a id="protected-space-contract"></a>[Protected-space contract](docs/history/README.md#protected-space-contract)

<a id="earlier-implementation-evidence"></a>[Earlier implementation evidence](docs/history/README.md#earlier-implementation-evidence)

<a id="development-ci-policy"></a>[Development CI policy](docs/history/README.md#development-ci-policy)

<a id="session-renewal-m20-corrected-runtime-accepted"></a>[Session renewal (M20 corrected runtime accepted)](docs/history/README.md#session-renewal-m20-corrected-runtime-accepted)

<a id="documentation-and-skills-release-readiness-phase"></a>[Documentation and skills release-readiness phase](docs/history/README.md#documentation-and-skills-release-readiness-phase)

</details>
