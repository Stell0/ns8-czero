# Personal API keys

API keys let automation call REST and MCP without an interactive login or token
refresh. Sign in and open **Account → API keys**. Enter a name, choose Read or
Read and write, explicitly select allowed spaces, and choose an expiration.
The default is 90 days; one year and an explicit No expiration option are available.
Copy the new key immediately. C0 stores its hash and cannot show it again.

Keys act as their creator and have no administration scope. They cannot exceed
the creator's current permissions or enter a space outside their selected list.
An omitted space selects Shared as usual; it never selects another allowed space.
Membership and protected-space permission changes invalidate existing keys;
restoring permissions does not restore old keys. Keys also snapshot account and
selected-space revisions so older released writers cannot revive their authority. Revocation takes effect at Core
operation boundaries, including captured credentials. The account list shows up to 100
unrevoked keys and recent expired/revoked keys, with last use sampled at
five-minute intervals. Create a replacement, update the workflow secret, verify
it, then revoke the old key to rotate without interrupting a workflow.

Keys keep working after browser and identity-provider sign-out. They are separate
C0 credentials: identity-provider-only account changes do not revoke them. Revoke
the key or block the account in C0. Ordinary updates and restarts preserve keys;
changing the instance's issuer, native client identity/secret or resource binding
invalidates them. An unchanged backup restore also restores its credential state;
revoke any keys that should no longer be accepted.

## GitHub Actions

Create an Actions secret named `C0_API_KEY`. Configure `C0_URL` (HTTPS instance URL
without a trailing slash) and `C0_SPACE_ID` as repository variables. Use a key
whose selected spaces include that UUID.

```yaml
- name: Check C0 access
  env:
    C0_API_KEY: ${{ secrets.C0_API_KEY }}
    C0_URL: ${{ vars.C0_URL }}
    C0_SPACE_ID: ${{ vars.C0_SPACE_ID }}
  run: |
    curl --fail-with-body --silent --show-error \
      -H "Authorization: Bearer $C0_API_KEY" \
      "$C0_URL/api/v1/me?space_id=$C0_SPACE_ID"
```

Use the same bearer header with an MCP client at `/mcp`. Knowledge writes retain
existing selected-space, expected-revision, idempotency and readback contracts.
Do not print keys, enable shell tracing around credentials, put keys in URLs or
run secret-bearing jobs on untrusted pull-request code.

Existing ingestion jobs can set `C0_AUTH_MODE=api_key` in their ignored job `.env`
and receive `C0_API_KEY` through the process environment. No `C0_CLIENT_ID` or
OAuth credential file is needed in that mode. The existing expected account ID,
account name and explicit space verification remain required. OAuth remains the
default, with no automatic fallback when a configured key is missing or invalid.
API-key login/disconnect commands direct users to the Account page.

## Interface

`GET /api/v1/api-keys` lists safe metadata and the session CSRF token.
`POST /api/v1/api-keys` accepts `name`, `scopes` (`c0:read` and/or `c0:write`),
`space_ids` (one to 100 UUIDs) and `lifetime_days` (1–365, default 90, explicit null
for no expiration). It returns metadata and the one-time `key` with status 201.
`DELETE /api/v1/api-keys/{id}` idempotently revokes an owned key and returns 204.
All lifecycle endpoints require a browser session; writes require same-origin
CSRF. API keys and OAuth grants cannot manage keys. API keys cannot enter native
extraction handoff or first-party administrative workflows.

Schema 0031 creates the key store; schema 0032 adds revision bindings. Upgrading
from the preserved first producer candidate revokes its prototype keys because
their original permission revisions cannot be recovered. Existing OAuth
credentials and knowledge remain unchanged.

This feature is a producer-development candidate. Released-Core adoption, full
native acceptance and live deployment are separate gates; the installed baseline
has not changed.
