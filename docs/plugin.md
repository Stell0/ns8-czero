# Package C0 workflows for ChatGPT web

## What this adds

The generic end-user package supplies four workflows: `c0-setup`, `c0-research`, `c0-maintain-knowledge` and `c0-projects`. They complement the existing MCP tools; they grant no membership, space access or OAuth scope. Repository development skills are separate and are not included.

`c0-projects` discovers an already authorized protected research project and its current capabilities. For repeated daily/weekly work, generate a separate project-bound skill through `project_agent_package_get` after configuring that project's manifest. A package never creates the project or installs a scheduled task. If `project_*` tools are not available, refresh the existing ChatGPT C0 connection's tool catalog and start a new conversation; do not substitute generic object writes or create a new connection just to work around missing discovery.

Each operator generates a package for their own registered C0 app. No package defaults to the project's test installation. The source package version is independent of the application version. Current package and real-web acceptance status are in the [readiness checklist](release-readiness.md).

## Register the app first

Complete [C0 connection setup](chatgpt.md). From the ChatGPT management page, obtain the app's technical ID. A URL containing `plugin_asdk_app_example` represents app ID `asdk_app_example`; a workspace `plugin_...` ID by itself is not the app ID. Verify that the page's Server URL belongs to your intended C0 instance.

For web-capable GitHub imports, the package references that existing app through `.app.json`. **Do not add `mcp.json`, `.mcp.json` or inline server declarations**: OpenAI marks imported packages with those declarations Desktop only, even for remote HTTPS servers. [Official workspace import and app-reference guidance](https://learn.chatgpt.com/docs/enterprise/plugin-management).

## Download from your instance

Open **Use with AI** (`/agents`). **Download .skill** generates a ZIP-based skill archive containing `SKILL.md`, `agents/openai.yaml` and the GPL license. Its name and instructions include the configured hostname and canonical MCP URL. Upload it at [ChatGPT Skills](https://chatgpt.com/skill) where that control is available. It uses the connection you created; it does not install or authorize an MCP server by itself.

For the four-workflow plugin, sign in, paste the ordinary ChatGPT connection management-page address or technical app ID, and choose **Download plugin .zip**. Check the instance URL in ChatGPT before downloading. The page accepts a connection-page address, never a full OAuth authorization URL. The generated ZIP contains one plugin at its root, the existing app reference, personalized instance guidance, four skills and their references/license. No password, session or access token is included. Generation cannot prove the app ID belongs to this server; verify it in ChatGPT.

Upload only the generated single-plugin ZIP where ChatGPT offers plugin archive upload. Other installation routes below remain available when your account provides them. Start a new conversation and test an actual read after installing either artifact. Upload acceptance and automatic skill use must be checked on your account.

## Generate offline

Use Python 3.12 or newer from a reviewed source checkout. No model/API credential or network access is needed by the generator:

```sh
python3 scripts/package-chatgpt-plugin.py \
  --mcp-url https://knowledge.example.org/mcp \
  --chatgpt-app-id asdk_app_example \
  --name acme-knowledge \
  --output /tmp/acme-knowledge-package
```

Replace the example URL/app ID/name. The output location must not exist and its parent must exist. The script never overwrites a package, modifies your ChatGPT account, creates a repository or publishes anything. The URL and app ID are configuration, not proof of their association; verify that association in ChatGPT before installation.

Output contains the portable plugin, its skills/references/license, a marketplace tree, `plugin.zip`, `SHA256SUMS` and `INSTALL.md`. The ZIP contains one plugin with `plugin.json` at its root; the separate directory tree contains the marketplace for GitHub import. Identical inputs/source produce identical archive bytes. Check the checksums before distributing. An operator may keep their generated host/app mapping in a private repository; do not submit another deployment's identity or credentials to this public repository.

## Single-plugin archive upload where available

If ChatGPT offers a plugin archive upload, choose the generated `plugin.zip`. Do not ZIP/upload the whole marketplace directory: that layout can fail with `Expected a single plugin archive`. After import, inspect the saved app binding, all four skills and their reference links. An accepted archive is not proof of a connected account or working workflow; run the tests below. Availability and behavior must be checked on the actual account. Keep private Creator and managed import evidence separate.

## Individual/private setup in ChatGPT web

Prerequisites: permission to use plugins, Plugin Creator available, permission to create/edit the private plugin, and access to the registered C0 app. These controls are account/workspace dependent.

1. Invoke **Plugin Creator** in a ChatGPT web conversation.
2. Provide the generated skill/reference files and the exact registered C0 app identity. If the Creator can inspect the source archive, it can be supplied as reference material; attaching a ZIP alone is not a native installation operation.
3. Ask it to create a private plugin using those workflows and that existing app. Preserve the explicit-space, evidence/citation, authorization, retry and revision rules.
4. Review that all four distinct named skills survived, including the correct instance binding and all linked reference material. If attachments are flattened or renamed, ask Creator to resolve those references; do not leave four indistinguishable `SKILL.md` files. Review the app binding, finish creation and install it if prompted. Keep it private for testing.
5. In a new web conversation, select the plugin, invoke setup, then test the known read-only and permitted maintenance cases below.

OpenAI documents private creation and app inclusion through Plugin Creator, with prerequisite permissions. This repository's real-web test must verify that the generated content is actually present and used; schema validation or desktop execution is insufficient. [Official web plugin creation](https://learn.chatgpt.com/docs/build-plugins).

## Managed workspace import

A workspace Admin with the appropriate GitHub access puts the generated tree in an operator-controlled GitHub repository and uses **Admin → Plugins → Add → Import marketplace**. Enter the repository URL; select the generated root as Path if nested, and pin a reviewed commit for initial testing.

Inspect import results, configure only the intended test role's installation policy and allow the required app. Repository installation policy is not a substitute for workspace policy. Each user still completes their own C0 login. Test on the web before wider sharing. GitHub import can sync future source updates; review commits before delivery and preserve working plugin identities when updating.

Do not import a template with an example app ID. Do not replace or delete an existing working marketplace to fix a new package. OpenAI documents that removing a marketplace can delete imported workspace plugins; troubleshoot access/sync separately. [Official import/sync guidance](https://learn.chatgpt.com/docs/enterprise/plugin-management).

## Test the installed workflows

- **Setup:** correct associated C0 app, account label and authorized spaces; no writes.
- **Research:** a known question answered from actual original passages with immutable citations, with no content changes.
- **Maintenance:** an explicitly requested edit in an owned test space; preserved provenance, fresh read-back and correct revision/conflict/retry handling.
- **Projects:** with a project-enabled MCP catalog, read `project_get` and `project_diagnostics_get` in an explicitly authorized protected space. Confirm that a missing project tool or denied space fails closed, without generic-object fallback or writes. Project package generation does not install a host task.
- **Denial:** Reader/space/scope denial produces no write and no fallback to Shared or another instance.
- **Continuity:** repeat a read beyond five minutes, reconnect after expected expiry and verify targeted client revocation.

Test both explicit skill selection and ordinary requests that should activate it, plus unrelated requests that should not. Keep private traces and credentials outside Git. Record actual web behavior for private Creator setup and managed import separately. No public directory submission or workspace-wide rollout is performed by the packager.
