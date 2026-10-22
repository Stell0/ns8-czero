# Connection setup

The instance URL and registered app ID are in `instance.md`. Check that the user selected that app. Never choose a similarly named C0 connection automatically.

1. An instance administrator configures trusted public HTTPS, NethServer sign-in, owner/member access and Client metadata discovery in NS8 Settings. Approval of an OAuth client grants no user membership.
2. In ChatGPT web, create a custom MCP connection using the instance's `/mcp` URL, OAuth and CIMD, with no static client ID or secret.
3. Copy only the exact client metadata URL shown for that connection, such as `https://chatgpt.com/oauth/<callback-id>/client.json`. An application Admin previews and approves it in C0 Administration, initially for `c0:read`.
4. An initial `invalid_request` can mean that this exact client/callback has not yet been approved. Check the reviewed identity and callback; do not guess a different URL or weaken validation. Start a fresh Connect attempt after approval.
5. Complete provider sign-in and explicit consent. Install/select the associated plugin in a new conversation. Check `get_profile` and authorized spaces before reading content.

Reader membership and read consent support research. Edits need effective Editor access in the selected space, approved write scope and explicit write consent. Admin permission is separate. Ask the appropriate administrator when a grant is missing; never change grants as part of setup.

Access tokens renew within configured session bounds. Defaults are one hour idle and eight hours absolute; provider policy or revocation can end authority sooner. A long idle interval or absolute expiry can legitimately require reconnecting. Tool refresh is not proof of a fresh authenticated read.
