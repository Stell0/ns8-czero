# Connection setup

The instance URL and registered app ID are in `instance.md`. Check that the user selected that app. Never choose a similarly named C0 connection automatically.

1. An instance administrator configures trusted public HTTPS, NethServer sign-in and Client metadata discovery. New verified users normally receive Reader access to Shared; explicitly blocked users stay blocked.
2. In ChatGPT web, open Plugins → personal → + → Add custom MCP server. Use this instance's `/mcp` URL, OAuth and CIMD, with no static client ID or secret.
3. A new connection opens C0 sign-in and a browser-bound approval page. Sign in with your own account. If you are a C0 Admin, review the exact metadata identity/callback and approve only needed scopes. Other users ask an Admin to review the waiting connection under Administration → ChatGPT connections.
4. Choose approved permissions, continue to explicit consent and confirm them. Requests expire after five minutes; start Connect again if needed. An enabled discovery setting does not automatically approve every client. Malformed requests and wrong callbacks/resources still fail.
5. Install/select the associated plugin in a new conversation. Check `get_profile` and authorized spaces before reading content. Enabling write/admin scopes requires deliberate client approval, sufficient user role and fresh consent; refresh cannot add them.

Reader membership and read consent support research. Edits need effective Editor access in the selected space, approved write scope and explicit write consent. Admin permission is separate. Ask the appropriate administrator when a grant is missing; never change grants as part of setup.

Access tokens renew within configured session bounds. Defaults are one hour idle and eight hours absolute; provider policy or revocation can end authority sooner. A long idle interval or absolute expiry can legitimately require reconnecting. Tool refresh is not proof of a fresh authenticated read.
