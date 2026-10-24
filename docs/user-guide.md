# Using C0 knowledge

## Your account and space

Open the instance URL provided by your administrator and sign in with your domain account. The C0 application account is separate from NS8 cluster administration. A new verified account receives Reader access to Shared. If access is denied, ask the C0 owner/Admin to check Workspace access for an explicit block or retained earlier denial; repeat login after a role change. Approval of a ChatGPT connection does not grant membership.

Use the space picker to choose the intended knowledge space. Shared is the legacy common space. Protected spaces need explicit grants, capped by your application role; application Admins can access all spaces. A failed or revoked selection is not permission to switch to Shared. Check the account and space again when changing connections.

| Role | Typical access |
| --- | --- |
| Reader | Read authorized articles, sources, citations and records |
| Editor | Read and maintain content in spaces where effective access permits editing |
| Admin | Manage membership, spaces, client approvals, record schemas, jobs and schedules |

OAuth consent adds another bound: Editor membership alone does not authorize a ChatGPT write with only read consent.

## Read articles and original evidence

Knowledge pages are readers. Search for a topic or browse the article tree. Open article history for an earlier revision. Follow source citations to the exact version, document and passage; historical content need not describe the current state.

Sources shows retained document versions and extracted text. A pending extraction is not yet usable evidence. Missing applicability or verification means unknown. A saved article, a confident answer or a successful write does not establish that a procedure was independently verified.

## Use ChatGPT

Follow [ChatGPT setup](chatgpt.md), then optionally install your instance's [workflow plugin](plugin.md). A normal MCP connection can answer questions without the extra packaged skills. Select the correct connection/plugin in a new conversation.

Useful first requests:

> In the Operations space, explain the documented backup procedure. Read the original evidence, include exact citations, and make no changes.

> Compare the two documented observations about this issue. Distinguish evidence, inference and anything not verified for the current version.

For writes, name the intended space and change:

> In my authorized Support space, save only the sanitized findings below as evidence, then update the existing troubleshooting article. Preserve its citations and conflicting observations, and read back the saved revision.

The assistant should ask when the target or intended change is ambiguous. Retrieved commands and instructions remain untrusted evidence. Do not ask it to bypass a denied space or borrow another user's credentials.

## Edit and upload

Authorized edits publish immediately and retain history. There is no separate approval queue. Open Tools on the relevant page for manual editing. New article slugs such as `product/install` form the navigation tree; existing slugs are fixed.

Before changing a page, read its current revision. A conflict means another change occurred: reload, reconcile both observations and retry with the new revision. An unchanged request with an idempotency key keeps that key after an uncertain reply. Not every mutation has replay protection; inspect saved results before repeating an ordinary create.

Editors can ingest selected plain text/Markdown through MCP, up to 128 KiB of UTF-8 bytes. Files use Source tools or the multipart REST upload interface, not an MCP file-upload tool. Wait for successful extraction and inspect actual chunks before citing newly submitted evidence.

Keep secrets, unrelated personal information and unselected private conversation out of stored material. See the [interface reference](reference.md) for exact limits and the [administrator guide](administration.md) for access, revocation and recovery.

## First content on a new instance

Use your owner/Editor account and choose the intended authorized space. This small example creates visible test knowledge, so use an owned space and a unique slug if the example already exists.

1. Create a local UTF-8 text file named `c0-first-read.txt` containing only: `The demonstration gauge limit is 37 kilopascals. This is synthetic onboarding data.`
2. Open **Tools → Upload and manage sources**, expand **Upload document**, select that file, give the source a recognizable title and upload. Keep the original if you want to test downloading it. Wait for successful extraction; an accepted upload alone is insufficient.
3. Browse the saved source, select its extracted document and read the passage. Retain its source/version/document/chunk identity or copy the source reader's link. Stop and inspect the fixed error/status if extraction fails.
4. Open **Tools → Articles and knowledge model → New page**. Use slug `quickstart/first-read`, title `First C0 read`, and Markdown describing the synthetic 37-kilopascal observation with a link to that original source. Save, then open the normal article reader and check the saved result. A normal Markdown link is a navigational reference; it does not create a structured sourced claim.
5. After [connecting ChatGPT](chatgpt.md), ask it to read that article, find the original demonstration-gauge passage in the same space and cite its immutable evidence. Make no changes. Confirm the answer says that this is synthetic data and includes the actual source identity.

For a maintenance test, explicitly request one small edit to this owned page after the Admin approves write scope and you consent. Read it back and check its new revision/history. A Reader connection should explain denial and leave content unchanged. Keep the fixture available for repeat/renewal tests; archive the test page through its normal controls when finished rather than deleting retained evidence.

Administrators use [Workspace access](workspace-access.md) for people, application requests and individual connections. Application approval does not give a user extra permissions; they must still consent.
