# Administer a C0 instance

## Prerequisites and installation

You need an NS8 node, an application DNS hostname, a certificate trusted by browsers and ChatGPT, and a compatible configured NS8 IdP/user domain. ChatGPT must be able to reach the application HTTPS endpoint. Hostname-root routing is required for MCP; an old cluster-prefix REST URL is insufficient.

C0 has verified development candidates; a stable NS8 release is not created by the documentation milestone. Use a reviewed immutable candidate from the [operator-facing candidate record](installation-candidate.md), not an assumed version tag. `main` and `latest` are moving development channels. The candidate record lists the measured native/IdP baseline; do not assume an old upstream README image example is available.

From the NS8 leader, use the installed supported command with your chosen node:

```sh
add-module ghcr.io/stell0/czero:<verified-candidate-tag> <node-id>
```

This is a template command: replace both bracketed values before running it. Inspect the task result and new module ID. Native module images select their matching app/database siblings; do not independently mix their versions.

In Czero Settings, configure the hostname and certificate option. Enable NethServer sign-in, select the IdP and domain, and choose an existing domain account as owner. Save, wait for readiness, then sign in through the application link as that owner. TLS validation stays enabled. Do not change the cluster's shared IdP/proxy configuration to work around an application error.

## Admit users and grant spaces

The owner receives application Admin access. New accounts verified by the configured sign-in provider receive Reader access to Shared and spaces open to all signed-in users automatically. Open **Administration → People and applications** to change permissions, review application requests, disconnect one connection or block a user. See the [access-page guide](workspace-access.md) for exact action meanings. Permission presets map to Reader, Editor and Admin; **Block user** is a separate explicit action. Blocking persists across later sign-ins and revokes existing access. Earlier accounts denied before this update stay blocked until an Admin deliberately changes their role. Native Settings owns the owner selection; a username or token role claim alone grants nothing.

Use **Administration → Spaces** to choose **All signed-in users** or **Selected people** and manage additional grants. The first audience gives Read for the whole space, including sources and attachments; existing protected spaces remain restricted after migration. Roles and actual OAuth scopes continue to cap access. Revoking membership, a space grant or an approved client takes effect on subsequent authorized operations, including existing sessions.

<a id="approve-chatgpt"></a>
## Approve an assistant

Follow the [assistant setup guide](byoa.md). Validated new metadata clients can connect for Read after company sign-in and personal consent. Requests for additional application permissions require administrator approval. Use **People and applications** to review or decline a request and **Technical clients** to manage a registered application. Application approval leaves the person's role and space permissions intact.

Existing manually approved UUID clients remain supported. Keep their exact callbacks and identifiers; enabling CIMD does not migrate them or require replacing a working connection. The internal UUID displayed for a CIMD approval is an administrative identifier, not its public OAuth client ID.

Reapproval after a relevant document change revokes affected grants. Global disable revokes CIMD authority; turning it back on does not revive prior grants. Metadata outages can block new consent while existing locally valid grants continue within their authority bounds. Do not replace an approved URL with a guessed stable ChatGPT URL.

## Session policy and revocation

Native Settings exposes the idle and absolute bounds for ordinary website sign-in and bounded interactive authority. Defaults are 3600 seconds idle and 28800 seconds absolute; the supported relationship is `60 <= idle <= absolute <= 86400`. Check the actual saved settings for your instance. These are ceilings, not a promise that an IdP session lasts that long: provider expiry, logout, membership changes and revocation can end authority earlier.

Short access tokens and normal refresh rotation do not mean that a user should log in every five minutes. Interactive requests can renew within the original bounds. Once idle/absolute browser authority expires, sign in normally; refreshing cannot add scopes or extend that browser's original absolute deadline.

Eligible new connections show **Allow background access** selected on the consent page. The user can clear it before authorizing. Background access requires verified provider offline access with the same account. C0 can reuse an active offline sign-in with the current inactivity limit, or ask for another sign-in before final consent. Native Settings sets the inactivity limit for new grants in whole days from 1 to 365, with a default of 30. Each grant uses the limit set at consent. Background access survives browser logout and has no fixed maximum while the connection is active. The website's separate **Remember this device** choice has a fixed seven-day inactivity window.

Users disconnect their own connections from **Account → Your connected apps**. Disable a specific approved client to revoke all its grants; reenable permits fresh consent but does not revive old grants. Membership changes revoke existing authority. Local logout revokes bounded grants and preserves explicitly consented background grants. Provider rejection ends authority; provider sign-out may require its own confirmation and ordinarily preserves offline access. A plugin's installation policy and each user's connection credentials are separate. Database restore with a new native client or secret cannot revive the old connection.

## Operate and troubleshoot

Use NS8's Configuration/Status pages and supported module actions. Runtime status distinguishes database readiness, authentication configuration and scheduler activity. Configuration alone does not prove provider connectivity or output quality. An idle one-shot worker is normal; a failed worker is not.

Use focused supported operations on the correct module/node. For example:

```sh
api-cli run module/<module-id>/get-runtime-status
api-cli run module/<module-id>/get-authentication-status
api-cli run module/<module-id>/get-scheduler-status
```

Use the configured module ID, not one copied from another operator. For direct administration assistance, install the maintained [NethServer agent skills](https://github.com/NethServer/agents); their `nethserver-admin` skill covers supported NS8 actions and rootless contexts.

C0 uses journald. Empty Podman logs or an inaccessible module-user journal do not prove privacy. An authorized log audit must use bounded actual application entries, the verified UID/container and positive request controls. Keep raw journals, cookies and tokens private. Share fixed status/error codes, not complete OAuth authorization URLs or credential-bearing traces.

### Inspect incomplete source work

Open **Sources → Inspect ingestion** in the selected space. Use **Recent runs**
on an automatic source to see collection coverage, pending work and unresolved
reasons. These views report current metadata. Confirm evidence through a current
complete document, original and exact citation.

- Wait for queued or running work. A valid collection checkpoint resumes under
  the saved authority. Use **Update now** for an enabled manual source.
- For an eligible retained failed version or page run, open the source and use
  the existing retry action as an Editor. Review protected originals separately.
  If staging expired, reacquire the official original.
- For missing or inconsistent multipart membership, locate the verified
  original part set and rebuild the complete import with its publisher. Search
  chunks are excerpts and cannot reconstruct an original.
- If the inventory cannot distinguish a legacy or damaged record, collect the
  logical ID, selected space, revision and structured diagnostic using an
  authorized account. Keep the original titles and URLs out of public reports.

The NS8 metrics exporter adds aggregate collection states, oldest queued work
and failed/retried extraction attempts. It uses fixed state and outcome labels.

### Grafana

Enable Grafana in the NS8 Metrics application, then sign in with a cluster
administrator account and open **Dashboards**. C0 ships a separate overview
for each installed instance. The dashboard shows service and collector health,
MCP tool outcomes, HTTP traffic for C0 and its custom apps, source ingestion
and failure categories, knowledge and connection counts, background work,
and container and storage usage.

C0's aggregate counters are collected by NS8 about every five minutes. HTTP
metrics come from Traefik and include traffic to registered custom app routes.
MCP counters count completed calls handled by C0 and reset when the application
restarts. A tool can report an error in an HTTP 200 response. A custom app's
private conversations, model usage and costs are outside these counters.
The C0 exporter uses a bounded read-only database query and omits database
statistics when the query fails. It exposes no customer content, account
identifiers, filenames, tokens or tool arguments.

## Update, backup and restore

Use native NS8 backup for the C0 instance and check completion/integrity before an update. Retained source files and logical database state must remain coordinated; do not copy a live PostgreSQL data directory as a logical backup substitute. Backups retain private data and require appropriate storage/access policy.
The C0 backup includes the instance key for saved PDF unlocking and its sealed
password records so retained originals can be reprocessed after a restore.

Use the canonical verified candidate tag with the supported targeted update:

```sh
update-module ghcr.io/stell0/czero:<verified-candidate-tag> <module-id>
```

Wait for readiness and verify the installed module/app/database revisions and digests, content, settings, schedules, clients and worker health. Preserve unrelated applications. Keep installed candidate tags available and unchanged while referenced; documentation-marker images are not replacement runtime images.

Clean restore retains knowledge and approved descriptors but re-registers native identity: prior delegated authority is rejected and fresh sign-in/consent is required. Test destructive restore/recovery in disposable systems. Use [CI policy](ci-policy.md) for this repository's full acceptance requirements and [readiness](release-readiness.md) for documented release limits.

## Optional retrieval and processing

Text retrieval works without an external model provider. Configure optional embeddings and relevance scoring in native Settings, with dedicated provider credentials. Check actual index readiness through `knowledge_index_status`; saved configuration alone does not prove indexed coverage or quality.

System One scoring uses the OpenAI Decisions protocol. Configure endpoint `https://api.openai.com/v1/decisions`, model `gpt-6-luna` and a dedicated provider key. Scoring defaults off. **Rerank** permits reranking; **Filter** also permits threshold filtering. At most sixteen candidate excerpts of 2 KiB each are scored. Reranking retains the unscored tail; filtering returns only scored hits at or above the threshold (default 0.7). Calibrate it against your corpus. Provider failures report fallback and preserve ordinary ranking. Older JEV/Kev descriptors need an explicit endpoint/model/key replacement; changing an endpoint clears the saved key unless a replacement is supplied. See [retrieval measurements and limits](retrieval-benchmark.md).

Queued extraction and local OCR are separate opt-ins and remain disabled by default. Native `extraction.enabled` selects queued units; `extraction.ocr_enabled` permits local OCR for unsupported PDF scans. Use [the bounded pilot/recovery guide](ingestion-pipeline/ROLLOUT.md) before enabling them. Existing documents are not automatically reindexed.

Compiler policy is separate from provider settings, project schedules and ordinary write permission. Read [LLM Wiki policy setup](llm-wiki.md#enable-compiler-coordination-deliberately) and [compiler operations](knowledge-compilation/OPERATIONS.md). External schedule installation/activation is separate; a deterministic C0 schedule cannot execute a conversational agent prompt.

Embedding refresh processes bounded batches and continues while its ten-minute deterministic schedule remains enabled. Pausing that schedule stops further continuations after already queued work; disabling the provider makes indexing a no-op. This indexing schedule is separate from external reasoning and Wiki maintenance.
