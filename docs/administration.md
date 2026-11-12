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

The owner receives application Admin access. New accounts verified by the configured sign-in provider receive Reader access to Shared and spaces open to all signed-in users automatically. Open **Administration → Workspace access** to change permissions, review application requests, disconnect one connection or block a user. See the [access-page guide](workspace-access.md) for exact action meanings. Permission presets map to Reader, Editor and Admin; **Block user** is a separate explicit action. Blocking persists across later sign-ins and revokes existing access. Earlier accounts denied before this update stay blocked until an Admin deliberately changes their role. Native Settings owns the owner selection; a username or token role claim alone grants nothing.

Use **Administration → Spaces** to choose **All signed-in users** or **Selected people** and manage additional grants. The first audience gives Read for the whole space, including sources and attachments; existing protected spaces remain restricted after migration. Roles and actual OAuth scopes continue to cap access. Revoking membership, a space grant or an approved client takes effect on subsequent authorized operations, including existing sessions.

## Approve ChatGPT

Use the [ChatGPT guide](chatgpt.md). Validated new metadata clients can connect for Read after company sign-in and user consent, without administrator review. The discovery switch is removed for both new and upgraded/restored installations. Requests for additional application permissions still need explicit administrator approval. **Decline** cancels only the selected request; it does not block a person. Technical metadata configuration is under **Technical clients**. Client approval grants no user additional role or space permission.

Existing manually approved UUID clients remain supported. Keep their exact callbacks and identifiers; enabling CIMD does not migrate them or require replacing a working connection. The internal UUID displayed for a CIMD approval is an administrative identifier, not its public OAuth client ID.

Reapproval after a relevant document change revokes affected grants. Global disable revokes CIMD authority; turning it back on does not revive prior grants. Metadata outages can block new consent while existing locally valid grants continue within their authority bounds. Do not replace an approved URL with a guessed stable ChatGPT URL.

## Session policy and revocation

Native Settings exposes the idle and absolute bounds for ordinary website sign-in and bounded interactive authority. Defaults are 3600 seconds idle and 28800 seconds absolute; the supported relationship is `60 <= idle <= absolute <= 86400`. Check the actual saved settings for your instance. These are ceilings, not a promise that an IdP session lasts that long: provider expiry, logout, membership changes and revocation can end authority earlier.

Short access tokens and normal refresh rotation do not mean that a user should log in every five minutes. Interactive requests can renew within the original bounds. Once idle/absolute browser authority expires, sign in normally; refreshing cannot add scopes or extend that browser's original absolute deadline.

Users can explicitly select background access for each client on the consent page. It requires verified provider offline access with the same account. Existing active offline sign-ins can be reused when their saved inactivity limit matches the current setting; otherwise C0 requests another sign-in before final consent. Native Settings exposes its inactivity limit in whole days, from 1 to 365, default 30. This is snapshotted for new connections; changing it does not extend or shorten existing grants. Background access has no fixed maximum duration while used and survives browser logout. Browser inactivity remains independent of assistant activity. Website users can explicitly choose a fixed seven-day inactivity window after the provider authorizes offline renewal. Ordinary browser limits remain unchanged. Remembering a device does not consent to background connections, and background consent preserves that browser choice.

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

## Update, backup and restore

Use native NS8 backup for the C0 instance and check completion/integrity before an update. Retained source files and logical database state must remain coordinated; do not copy a live PostgreSQL data directory as a logical backup substitute. Backups retain private data and require appropriate storage/access policy.

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
