# Connect ChatGPT to C0

Open **Use with AI → ChatGPT** on your C0 site. You need a ChatGPT web account or workspace that permits custom MCP apps. Skill upload and plugin creation have their own account or workspace controls. [Custom MCP apps in ChatGPT](https://help.openai.com/en/articles/12584461-developer-mode-and-full-mcp-connectors-in-chatgpt-beta) · [Skills in ChatGPT](https://help.openai.com/en/articles/20001066-skills-in-chatgpt)

<a id="1-administrator-prepares-the-instance"></a>
<a id="2-user-creates-the-chatgpt-connection"></a>
## Connect the app

1. Open [ChatGPT Plugins → personal](https://chatgpt.com/plugins?directoryTab=personal) and choose **Add custom MCP server**. In a managed workspace, use the workspace's custom app creation flow where offered, or ask its administrator to make the app available.
2. Use a recognizable name and paste the MCP URL from C0. Choose **OAuth**. Under **Advanced OAuth settings**, check that discovery selected **Client Identifier Metadata Document (CIMD)**. When a connection needs Write or Manage and ChatGPT asks for Read alone, set the corresponding `c0:write` or `c0:admin` under **Base scopes**, one per line alongside `c0:read`. C0 still checks client approval and the current account before showing the final consent choices. [Official custom MCP setup](https://developers.openai.com/api/docs/guides/custom-mcp-server)
3. Start **Connect**, check the C0 hostname and sign in. Review the suggested permissions and background setting, then authorize. [C0 consent and approval](byoa.md#sign-in-and-choose-permissions)

<a id="3-administrator-reviews-and-approves"></a>
<a id="3-user-authorizes-read"></a>
<a id="enable-editing-deliberately"></a>
If C0 asks for additional app approval, follow the options on the C0 page. A C0 administrator can check approval in **Administration → People and applications** or **Technical clients**. Start Connect again if the request expires. [Workspace access](workspace-access.md)

<a id="5-add-reusable-workflow-skills"></a>
## Install the skill

1. From C0's **Use with AI → ChatGPT**, download the ChatGPT `.skill` file.
2. In [ChatGPT Skills](https://chatgpt.com/skills), choose **Create → Upload from your computer** if available. Confirm that the C0 skill is installed and enabled.
3. For a private or managed plugin that bundles the five C0 workflows with the app, use the existing connection and follow [plugin packaging](plugin.md).

<a id="4-user-connects-and-verifies"></a>
## Try the connection

In a new ChatGPT web conversation, select the C0 app and use the installed skill. Ask for the connected account and a cited read from an authorized space. Open the cited passage in C0. [First read and authorized edit](byoa.md#first-read-and-authorized-edit)

<a id="reconnect-while-already-signed-in"></a>
<a id="troubleshooting"></a>
## Reconnect

Use **Reconnect** on the affected ChatGPT app and review the new C0 consent. If prompted for background sign-in, use the same C0 account. If tools changed, refresh them or ask the workspace administrator to update the reviewed app, then try a read in a new conversation. For permission or account issues, see [common troubleshooting](byoa.md#reconnect-or-get-help). [Troubleshooting ChatGPT apps](https://help.openai.com/en/articles/20001497-troubleshooting-plugins-and-apps-in-chatgpt)

## Recurring maintenance

Follow the [ChatGPT scheduling guide](wiki-maintenance.md#chatgpt) when the chosen task surface can retain the C0 app and skill.
