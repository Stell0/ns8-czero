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

The owner receives application Admin access. A prospective member first attempts sign-in; an Admin can then admit the verified account from Account/sharing. Select Reader, Editor or Admin deliberately. Native Settings owns the owner selection; a username or token role claim alone grants nothing.

Create protected spaces and explicit grants through the supported application interface/API. Roles and actual OAuth scopes continue to cap access. Revoking membership, a space grant or an approved client takes effect on subsequent authorized operations, including existing sessions.

## Approve ChatGPT

Use the staged [ChatGPT guide](chatgpt.md). Client metadata discovery defaults **off**. Enable it in native Settings only when wanted. In application Administration, preview and review the exact connection-specific metadata URL before approval. Start with read scope. A user still needs membership, sign-in and explicit consent.

Existing manually approved UUID clients remain supported. Keep their exact callbacks and identifiers; enabling CIMD does not migrate them or require replacing a working connection. The internal UUID displayed for a CIMD approval is an administrative identifier, not its public OAuth client ID.

Reapproval after a relevant document change revokes affected grants. Global disable revokes CIMD authority; turning it back on does not revive prior grants. Metadata outages can block new consent while existing locally valid grants continue within their authority bounds. Do not replace an approved URL with a guessed stable ChatGPT URL.

## Session policy and revocation

Native Settings exposes the idle and absolute bounds. Defaults are 3600 seconds idle and 28800 seconds absolute; the supported relationship is `60 <= idle <= absolute <= 86400`. Check the actual saved settings for your instance. These are ceilings, not a promise that an IdP session lasts that long: provider expiry, logout, membership changes and revocation can end authority earlier.

Short access tokens and normal refresh rotation do not mean that a user should log in every five minutes. Active requests can renew within the original bounds. Once idle/absolute authority expires, reconnect normally; refreshing cannot add scopes or extend the original absolute deadline.

Disable the specific approved client to revoke its grants. Reenable permits fresh consent but does not revive old grants. Local C0 logout revokes the linked browser/native authority; provider sign-out may require its own confirmation. A plugin's installation policy and each user's connection credentials are separate.

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
