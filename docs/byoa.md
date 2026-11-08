# Bring Your Own Agent (BYOA)

C0 is the persistent knowledge side of an Agentic RAG system. Your external agent supplies conversation, reasoning, research, planning and tool orchestration. C0 supplies stored evidence, retrieval, knowledge operations, permissions and workflow coordination. Multiple agents can use the same authorized space without copying a chat's memory into each model.

The agent can change models without moving the knowledge store. People can read the same sources and Wiki in a browser. Roles, spaces and delegated scopes remain server-enforced even when an agent has different instructions. Optional embedding and relevance services process configured retrieval requests; C0 hosts no general-purpose conversational engine.

## Prepare the connection

1. Obtain your instance's trusted HTTPS URL and sign in. Open **Use with AI** (`/agents`) and copy its canonical MCP URL.
2. Choose an existing authorized space. Ask an Admin for a grant if needed. An application approval does not grant a user a role.
3. Configure the client's remote HTTP MCP connection. C0 requires approved exact OAuth client identities and callbacks. It does not provide open dynamic client registration.
4. Sign in as the intended account and consent to Read. For writes, both effective Editor access and `c0:write` are required. Ordinary content work needs no Manage scope.
5. Read `get_profile`, `spaces_list` and `spaces_get`. Keep the returned space UUID for every content operation. A denied space never falls back to Shared.
6. Read `c0://capabilities` through MCP, or the authenticated `/agents/capabilities.json`. Use the installed tool schemas, not a historical tool count.

Install the instance's generated instructions where the client supports that format. The ChatGPT plugin uses an existing app reference; it is not a universal MCP installer. A skill or plugin grants no authority. See [plugin packaging](plugin.md).

## ChatGPT

Use [the C0 ChatGPT guide](chatgpt.md) for the custom MCP connection, optional client-metadata approval, user consent and generated packages. Account/workspace controls must permit those operations. Interactive access, packaged-skill web use and unattended writes require separate checks.

## OpenAI Codex

For a Codex CLI version with HTTP MCP support, add the endpoint and authenticate:

```sh
codex mcp add c0 --url https://c0.example.org/mcp
codex mcp login c0
codex mcp list
```

Replace the example hostname. Follow [official Codex MCP guidance](https://learn.chatgpt.com/docs/extend/mcp). If automatic registration is incompatible, have the C0 Admin approve the exact public client/callback and use the installed CLI's supported OAuth configuration. Do not guess callback ports or broaden server validation. In a session, `/mcp` shows connection status. Verify profile, space, search and a current citation after connection; a server list alone proves no content access.

The repository records C0-specific Codex OAuth/read tests in [PLAN](../PLAN.md). Use only the scopes granted to that connection. The separate [reference compiler runner](../samples/ingestion/examples/compiler/README.md) uses a C0 API key and its own Codex model login; it is not this interactive MCP connection.

## Claude and Claude Code

Claude supports remote MCP connectors. In Claude Code, a basic HTTP entry is:

```sh
claude mcp add --transport http c0 https://c0.example.org/mcp
```

Use `/mcp` to authenticate. For a C0-approved public client, the vendor also supports `--client-id` and a fixed `--callback-port`. Have the Admin approve the callback actually emitted by your installed version. See [official Claude Code MCP instructions](https://code.claude.com/docs/en/mcp). A client that cannot supply an approved identity cannot connect merely because it supports MCP. The repository does not establish complete C0 acceptance for Claude; verify a real authorized operation before relying on it.

## Custom agents and scripts

Use REST at `/api/v1` or Streamable HTTP MCP at `/mcp`. The instance's `/openapi.json` and capability resource describe available inputs. OAuth provides explicit per-user consent. [Personal API keys](api-keys.md) support automation in explicit spaces with Read/Write ceilings and no administration scope.

Keep credentials in the chosen host's private secret storage. Reuse [the ingestion client's authentication and verification helpers](../samples/ingestion/README.md) rather than adding a parallel login stack. File upload uses multipart REST; MCP text ingestion accepts at most 131072 UTF-8 bytes.

## First read and authorized edit

1. Follow [first content](user-guide.md#first-content-on-a-new-instance) if the space is empty.
2. Ask: “Use only C0 space `<space-uuid>` on this connection. Find the demonstration gauge observation. Read its complete document and exact passage. State its provenance and cite it. Make no changes.”
3. Check that the answer identifies the synthetic 37-kilopascal observation and the actual source/version/document/chunk. A Wiki summary alone is not original evidence.
4. With effective Write access and explicit consent, ask: “In that same space, read `quickstart/first-read` and its current revision. Update it to clarify that the observation is synthetic, using only the selected evidence. Preserve current citations. Use the current expected revision and a stable retry key. Read back the saved page.”
5. Inspect the saved page in Wiki. On a revision conflict, reconcile before retrying. After an uncertain write, inspect the saved result before repeating it. Reader credentials must leave knowledge unchanged.

For unattended use, follow [recurring Wiki maintenance](wiki-maintenance.md). C0 workers and deterministic job schedules do not execute conversational agent prompts.
