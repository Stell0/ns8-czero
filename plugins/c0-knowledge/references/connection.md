# Connection setup

The instance URL and registered app ID are in `instance.md`. Check that the user selected that app. Never choose a similarly named C0 connection automatically.

1. An instance administrator configures trusted public HTTPS and NethServer sign-in. New verified users normally receive Reader access to Shared and spaces open to all signed-in users; explicitly blocked users stay blocked.
2. In ChatGPT web, open Plugins → personal → + → Add custom MCP server. Use this instance's `/mcp` URL, OAuth and CIMD, with no static client ID or secret.
3. A validated new HTTPS metadata client can connect for Read after company sign-in and explicit user consent. No administrator review is needed for Read. Read consent covers every space the user can read. Disabled applications, blocked users and changed metadata requiring review remain unavailable.
4. When an application requests Read alongside additional permissions, continue with Read immediately. Write and Manage require administrator approval, sufficient user permissions and fresh consent. Requests expire after five minutes; restart Connect if necessary. Malformed requests and wrong callbacks/resources still fail. There is no discovery toggle, including after an upgrade or restore.
5. Install/select the associated plugin in a new conversation. For an existing working connection whose `project_*` tools are missing after a C0 upgrade, refresh the app's tool catalog in ChatGPT and start a new conversation instead of creating a replacement app. Check `get_profile`, authorized spaces and, if available, a read-only `project_get` before project work. Enabling write/admin scopes requires deliberate client approval, sufficient user role and fresh consent; refresh cannot add them.

Reader membership and read consent support research. Edits need effective Editor access in the selected space, approved write scope and explicit write consent. Admin permission is separate. Ask the appropriate administrator when a grant is missing; never change grants as part of setup.

Access tokens renew within configured session bounds. Defaults are one hour idle and eight hours absolute; provider policy or revocation can end authority sooner. A long idle interval or absolute expiry can legitimately require reconnecting. Tool refresh is not proof of a fresh authenticated read.
