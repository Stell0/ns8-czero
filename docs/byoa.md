# Connect an AI assistant to C0

Open **Use with AI** on your C0 site and choose your assistant. The page gives you this instance's MCP URL and an instruction download. Connect the app first, then install the instructions and try a cited read.

You need a C0 HTTPS address that the assistant can reach, a C0 account with access to a space, and a vendor account that permits custom connections. For a new instance, follow [installation and sign-in setup](administration.md).

<a id="prepare-the-connection"></a>
## Choose your assistant

| Assistant | Connect in the web app | Add C0 instructions |
| --- | --- | --- |
| ChatGPT | Add a custom MCP server with OAuth and Client ID Metadata Document (CIMD) if offered. [ChatGPT steps](chatgpt.md) | Upload the `.skill` from Use with AI in ChatGPT Skills. An existing app can also be packaged with five C0 workflows. [Plugin packaging](plugin.md) |
| Claude | In **Customize → Connectors**, add a **Custom → Web** connector using the C0 URL. Choose OAuth and try Claude's published client identity. [Custom connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp) | Download the Claude skill ZIP. In **Customize → Skills**, upload the ZIP and enable the skill if needed. [Claude skills](https://support.claude.com/en/articles/12512180-use-skills-in-claude) |
| Grok | In **Connectors → New Connector → Custom**, add the C0 URL and connect. A managed team may need an administrator to provision it first. [Grok connectors](https://docs.x.ai/grok/connectors) | Create a Grok skill with the C0 Markdown instructions. Upload the file in the creation conversation or paste its contents if the editor asks for text. [Grok skills](https://x.ai/news/grok-skills) |
| Gemini | Open **Customize → Connectors** or **Settings → Connected Apps** and look for **Add a custom app**. Google lists an adult US personal account, English and Keep Activity as prerequisites. If prompted for a registered client, give your C0 administrator the supported client requirements and exact callback. [Gemini custom apps](https://support.google.com/gemini/answer/17209137) | In **Customize → Skills**, choose **Create → Upload**. Select the downloaded `SKILL.md` file, then save the skill. [Gemini skills](https://support.google.com/gemini/answer/17094296?hl=en) |

Menus depend on the account, organization settings and rollout. The vendor instructions describe available setup mechanisms. See the [C0 browser test record](../PLAN.md#assistant-setup-and-first-use-experience) for the results of testing this combination. If automatic registration fails, use a separately [registered public OAuth client](workspace-access.md#register-a-public-oauth-client) where the vendor accepts one. Use the exact supported callback and leave the secret blank for a public client.

## Sign in and choose permissions

1. Start **Connect** in the assistant. Confirm the C0 hostname and app name, then sign in with your own C0 account.
2. Review the selected permissions before choosing **Authorize**. C0 suggests the permissions the app requests, the client is approved to use, and your account can grant. Clear any permissions you want to omit.

   | Permission | What it allows |
   | --- | --- |
   | Read | Browse and search spaces you can read, including restricted spaces you have access to. |
   | Write | Edit knowledge in spaces where you have permission to write. |
   | Manage | Administer C0 where your account permits it, including client or space access. |

3. If the app requests more than its current approval permits, continue with **Read** when offered or ask a C0 administrator to review the app. You still authorize your own connection after the review. Changing approval on a shared app can require others using it to reconnect.
4. Review **Allow background access**, selected by default for a new connection when supported. Keep it selected if the assistant needs to renew access while you are away. Clear it for interactive use, or continue to background sign-in with the same C0 account if prompted, then authorize. The consent page shows the inactivity window. Existing connections require fresh consent to add permissions or background access.

The permissions on the connected app and the account's current access to the selected space both apply. Adding a skill installs instructions. To stop an existing grant, go to **Account → Your connected apps → Disconnect**. For unattended runs, complete [scheduler setup and verification](wiki-maintenance.md).

## First read and authorized edit

1. Start a fresh conversation with the installed instructions and C0 connection. Ask the assistant to identify the connected account and list accessible spaces. Select the intended space. If it is empty, follow [first content](user-guide.md#first-content-on-a-new-instance).
2. Ask the assistant to find the demonstration gauge observation in that space, read its complete source, and cite the exact passage without changing knowledge. Open the citation in C0 and check that the source records the synthetic 37-kilopascal reading.
3. To test Write, explicitly ask for an edit to a test Wiki page in the same space. Ask the assistant to read the current revision, preserve citations, use the expected revision and a stable retry key, then read back the saved page. Open it in C0 and check the new revision. After a conflict or an uncertain response, inspect the current page before trying the edit again.

## Reconnect or get help

| What happened | What to do |
| --- | --- |
| The request expired | Start **Connect** again from the assistant. |
| Login succeeded but C0 denied access | Confirm the intended C0 account, then have an administrator check account status and app approval. [Workspace access](workspace-access.md) |
| Read works but Write or Manage fails | Check the account role, target space, application's approval and permissions shown for the connection in C0 Account. Reconnect for fresh consent after any approval or scope change. |
| The assistant reports a denied space | Ask a C0 administrator to check that space's grants. Keep the request scoped to the intended space. |
| Tools or instructions are missing | Select the intended app and skill, refresh the app's tool list if available, then retry a read in a new conversation. |
| The expected setup control is missing | Check the vendor account, workspace policy and available rollout for that control. |

When asking for help, include the step, approximate time and displayed error code. Keep passwords, browser cookies, tokens and full OAuth URLs private.

## OpenAI Codex

Use the canonical MCP URL from C0. For a Codex CLI version with remote HTTP MCP:

```sh
codex mcp add c0 --url https://c0.example.org/mcp
codex mcp login c0
codex mcp list
```

In a session, use `/mcp` to check the connection and run the [first read](#first-read-and-authorized-edit). If OAuth needs a registered client, use the client's supported configuration with the exact emitted callback. [Codex MCP instructions](https://learn.chatgpt.com/docs/extend/mcp)

## Claude and Claude Code

[Claude web setup](#choose-your-assistant) uses a remote connector. To connect Claude Code over HTTP:

```sh
claude mcp add --transport http c0 https://c0.example.org/mcp
```

Use `/mcp` to authenticate. With a preapproved public client, Claude Code supports `--client-id` and a fixed `--callback-port`. Use the exact callback emitted by your installed client. [Claude Code MCP instructions](https://code.claude.com/docs/en/mcp)

## Custom agents and scripts

Use REST at `/api/v1` or Streamable HTTP MCP at `/mcp`. Use the instance's `/openapi.json`, `c0://capabilities` and installed MCP tool schemas. Pass the selected space to every scoped operation. For seed data and automated reads or writes in specific spaces, use [personal API keys](api-keys.md) and the [ingestion client helpers](../samples/ingestion/README.md).
