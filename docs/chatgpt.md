# Connect your own ChatGPT to C0

Use your instance's URL throughout. This guide requires a ChatGPT account/workspace that permits custom MCP connections. Packaged workflow creation/import has [additional prerequisites](plugin.md). Menu availability depends on the account and workspace; an absent control needs workspace/product access, not a C0 security workaround.

## 1. Administrator prepares the instance

1. Configure trusted public HTTPS and NethServer sign-in in NS8 Czero Settings.
2. Sign in to C0 as owner/Admin. New verified users receive Reader access to Shared; grant Editor/Admin roles or protected-space access only when needed.
3. Enable **Client metadata discovery** in native Settings. It is off on new installations.
4. Give the user the canonical MCP URL shown by **Use with AI**, for example `https://knowledge.example.org/mcp`.

Do not use the NS8 cluster address or legacy `/czero/<module-id>` path as an MCP URL. Manual UUID client approval remains an alternative for compatible clients; keep an existing working connection while testing a new one.

## 2. User creates the ChatGPT connection

Open your instance’s **Use with AI** page (`/agents`). It supplies the instance name, description and Connection URL with small copy icons. In ChatGPT web, open [Plugins → personal](https://chatgpt.com/plugins?directoryTab=personal) → **+ → Add custom MCP server**, and copy those values. Choose **OAuth** and **CIMD / Client ID Metadata Document**, leaving static client ID and secret empty. Review the displayed notice and create the connection/plugin. [Official custom MCP setup](https://developers.openai.com/api/docs/guides/custom-mcp-server).

Start **Connect**. C0 opens its sign-in page and then a connection approval page. Sign in with your own domain account. A new verified account receives Reader access to Shared. An explicitly blocked account remains blocked.

## 3. Administrator reviews and approves

If you are a C0 Admin, choose **Review this connection** on the connection page. Check the exact client identity and callbacks, leave **Read** selected for research, and choose **Approve selected permissions**. Approval grants no user role and issues no token.

Other users ask an Admin to open C0 **Administration → ChatGPT connections → Waiting for approval**. After the user signs in, the request appears there with its metadata URL, callback and requested permissions. Choose **Review connection**, preview its metadata and approve only the permissions needed. The user then chooses **Check approval** on their connection page.

Choose **Continue to consent**, review the ordinary OAuth consent page and approve explicitly. Requests expire after five minutes; if needed, start Connect again in ChatGPT. Discovery being enabled does not automatically approve a client. Existing manually approved UUID clients keep their normal flow.

Do not approve a generic replacement URL or use an approval's internal UUID as ChatGPT's client ID. A metadata change between preview and approval requires a new review. Keep full authorization URLs, passwords, tokens and cookies private.

## 4. User connects and verifies

Complete explicit read consent in the connection opened above, or start a fresh **Connect** if it expired. Install/select the resulting plugin and start a new chat with that connection.

On an empty new instance, first follow the [first-content walkthrough](user-guide.md#first-content-on-a-new-instance) with an owner/Editor account. Then try:

> Show my connected C0 account and the knowledge spaces I can access. Then, in [space], read an existing article about [topic] and cite its original source passages. Make no changes.

Confirm the correct connected-account name and real citations. A successful tool refresh alone does not prove an authenticated content read. Repeat a read after more than five minutes to exercise normal renewal. [Official connection/testing guide](https://developers.openai.com/plugins/deploy/connect-chatgpt).

For a connection that should keep working between visits, select **Keep this connection working in the background** on the C0 consent page. If needed, continue through sign-in with the same account, then return and choose **Authorize**. The pending request still expires after five minutes. Grant write permission only when you intend to let the assistant maintain knowledge and both your C0 role and the approved client permit it.

Background connections use short access tokens and rotating refresh credentials. By default they end after thirty days without use; regular use keeps them active without a fixed end date. Your browser still signs out after its usual idle or maximum duration. C0 **Account → Your connected apps → Disconnect** stops a connection, including access it already holds. Client/account revocation and sign-in-provider rejection also stop access. Existing connections keep their original limits until you reconnect and explicitly choose background access.

Background authorization lets a compatible client renew access unattended. Whether a particular ChatGPT scheduled task can use the connection must be verified in that client; enabling background access does not create a schedule or authorize unspecified knowledge changes.

## 5. Add reusable workflow skills

On **Use with AI**, download the generated **.skill** and upload it at [ChatGPT Skills](https://chatgpt.com/skill), where your account supports skill upload. It contains this instance’s hostname and MCP URL. Alternatively, paste your ChatGPT connection page address or technical app ID and download the generated **plugin .zip** for the three setup/research/maintenance workflows. See [Plugin installation](plugin.md). A local desktop marketplace installation does not prove those skills are available on the web.

## Enable editing deliberately

An application Admin must approve the necessary write scope, and the user needs effective Editor access to the intended space. Reapproval revokes existing affected grants, so coordinate it and reconnect with explicit write consent. Do not request Admin scope for ordinary research or Wiki editing. Existing authorization remains enforced on every operation.

## Troubleshooting

| Symptom | Check and next step |
| --- | --- |
| Initial `invalid_request` | Confirm this instance runs the self-service onboarding update and Client metadata discovery is enabled. Valid new CIMD requests open sign-in/approval; malformed callbacks, duplicate parameters, wrong resource or discovery disabled still fail. Start Connect afresh; keep its full URL private. |
| Login succeeds but C0 denies access | Ask the owner/Admin to check People and permissions for an explicit block or retained earlier denial. New verified users receive Shared Reader access by default; client approval grants no additional role. |
| OAuth `invalid_scope` during reconnect | A valid CIMD request outside its approval opens the permission review page. Select only the approved permissions you need, or ask an Admin to review additional scopes. Existing UUID clients retain strict scope errors. Do not grant Admin merely to silence an error. |
| `insufficient_scope` | Request fresh explicit consent only if your role and approved client permit the operation. Refresh cannot add scope. |
| Permission denied for a space | Request an authorized grant; do not switch to Shared to bypass denial. |
| Reconnect after inactivity | Check actual C0 idle/absolute settings and IdP policy. Defaults are one hour idle/eight hours absolute; earlier revocation/provider expiry is possible. |
| Tools look stale | Refresh the connection's tools and start a new conversation; test an actual read afterward. |
| Plugin/Creator/import control missing | Check the intended ChatGPT workspace, product availability and permissions. See the prerequisites in the plugin guide. |
| Wrong account or instance | Stop and select the intended connection, then confirm profile/space. Do not overwrite another connection's configuration. |

When reporting a problem, include the action, fixed error code, whether it was a new or existing connection and approximate time. Keep passwords, tokens, cookies, raw journals and full authorization URLs out of reports.
