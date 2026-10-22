# Connect your own ChatGPT to C0

Use your instance's URL throughout. This guide requires a ChatGPT account/workspace that permits custom MCP connections. Packaged workflow creation/import has [additional prerequisites](plugin.md). Menu availability depends on the account and workspace; an absent control needs workspace/product access, not a C0 security workaround.

## 1. Administrator prepares the instance

1. Configure trusted public HTTPS and NethServer sign-in in NS8 Czero Settings.
2. Sign in to C0 as owner/Admin. Admit the intended user's verified account and grant the intended space access.
3. Enable **Client metadata discovery** in native Settings. It is off on new installations.
4. Give the user the canonical MCP URL shown by **Use with AI**, for example `https://knowledge.example.org/mcp`.

Do not use the NS8 cluster address or legacy `/czero/<module-id>` path as an MCP URL. Manual UUID client approval remains an alternative for compatible clients; keep an existing working connection while testing a new one.

## 2. User creates the ChatGPT connection

In ChatGPT on the web, open **Plugins → + → Add custom MCP server**. Enter a recognizable name and your instance's Server URL. Choose **OAuth** and **CIMD / Client ID Metadata Document**, leaving static client ID and secret empty. Review the displayed notice and create the connection/plugin. [Official custom MCP setup](https://developers.openai.com/api/docs/guides/custom-mcp-server).

Open its management page and copy the **exact client metadata URL**, such as `https://chatgpt.com/oauth/<callback-id>/client.json`, and its displayed callback. Send those two values to the C0 Admin. The correct URL depends on callback mode; do not construct it by guessing. [Official authentication guidance](https://developers.openai.com/plugins/build/auth).

An initial attempt may return `{"error":"invalid_request"}` because the new identity has not been approved. That is not a request to enter a secret or disable OAuth. Continue with Admin approval.

Share only the metadata URL and callback, not the entire `/oauth/authorize?...` address: that contains transient state and PKCE values. If you already have that address, its decoded `client_id` identifies the metadata URL; the rest is unnecessary for approval.

## 3. Administrator reviews and approves

In C0 **Administration**, open client metadata review. Preview the supplied HTTPS metadata URL. Check its name, exact self-identity, callbacks and public authentication method against the user's ChatGPT management page. Approve the exact document initially for **`c0:read`**.

Do not approve a generic replacement URL or use the approval's internal UUID as ChatGPT's client ID. Do not change existing clients to complete this setup. A metadata change between preview and approval requires a new review.

## 4. User connects and verifies

Select **Connect** afresh in ChatGPT. Complete your domain sign-in and explicit read consent. Install/select the resulting plugin and start a new chat with that connection.

On an empty new instance, first follow the [first-content walkthrough](user-guide.md#first-content-on-a-new-instance) with an owner/Editor account. Then try:

> Show my connected C0 account and the knowledge spaces I can access. Then, in [space], read an existing article about [topic] and cite its original source passages. Make no changes.

Confirm the correct connected-account name and real citations. A successful tool refresh alone does not prove an authenticated content read. Repeat a read after more than five minutes to exercise normal renewal. [Official connection/testing guide](https://developers.openai.com/plugins/deploy/connect-chatgpt).

## 5. Add reusable workflow skills

The connection already exposes C0 tools and server guidance. To install the separately packaged setup/research/maintenance skills in **ChatGPT web**, follow [Plugin installation](plugin.md). A local desktop marketplace installation does not prove those skills are available on the web.

## Enable editing deliberately

An application Admin must approve the necessary write scope, and the user needs effective Editor access to the intended space. Reapproval revokes existing affected grants, so coordinate it and reconnect with explicit write consent. Do not request Admin scope for ordinary research or Wiki editing. Existing authorization remains enforced on every operation.

## Troubleshooting

| Symptom | Check and next step |
| --- | --- |
| Initial `invalid_request` | Review whether the exact metadata URL/callback was approved; start a fresh Connect afterward. Duplicates, malformed callbacks or wrong resource can also be rejected. |
| Login succeeds but C0 denies access | Ask the owner/Admin to admit your verified account; client approval grants no membership. |
| OAuth `invalid_scope` during reconnect | ChatGPT requested a scope outside this client’s approval. Keep research/editing requests to the approved read/write scopes; do not grant Admin merely to silence the error. If administration is explicitly intended, an Admin reviews/reapproves that scope and affected connections consent again. |
| `insufficient_scope` | Request fresh explicit consent only if your role and approved client permit the operation. Refresh cannot add scope. |
| Permission denied for a space | Request an authorized grant; do not switch to Shared to bypass denial. |
| Reconnect after inactivity | Check actual C0 idle/absolute settings and IdP policy. Defaults are one hour idle/eight hours absolute; earlier revocation/provider expiry is possible. |
| Tools look stale | Refresh the connection's tools and start a new conversation; test an actual read afterward. |
| Plugin/Creator/import control missing | Check the intended ChatGPT workspace, product availability and permissions. See the prerequisites in the plugin guide. |
| Wrong account or instance | Stop and select the intended connection, then confirm profile/space. Do not overwrite another connection's configuration. |

When reporting a problem, include the action, fixed error code, whether it was a new or existing connection and approximate time. Keep passwords, tokens, cookies, raw journals and full authorization URLs out of reports.
