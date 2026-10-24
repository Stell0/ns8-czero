# Manage workspace access

Open **Administration → Workspace access** with your C0 administrator account.
The table groups each person with their application requests and connections.
People with pending requests appear first. If discovery is off, the page points to Advanced for connection setup. Use **Next people** or **More
applications** when the table has another page.

| Columns | Meaning |
| --- | --- |
| Username and Full name | Verified sign-in profile. Names are labels, not permission checks. |
| Read, Write, Manage on a person | Their current workspace permissions. |
| Requested on an application request | What the application is asking permission to request. This is not effective access. |
| Consented on a connection | Permissions the user explicitly gave that connection. |
| Effective on a connection | Current workspace role and consent both allow the operation. Protected-space grants still apply. |
| Status | User access, application approval/consent, or locally observed connection state. |
| Details | Technical identifiers, exact callbacks/scopes, revisions and timestamps. No credentials. |

New users verified by the configured sign-in provider receive **Read** access to
Shared. A persistent administrator block takes precedence over this default.
Protected spaces still need explicit grants for Readers and Editors. **Manage**
gives administration and implicit access to every space.

## Change a person's permissions

Choose **Change permissions**, select a preset and save:

| Preset | Core role | Permissions |
| --- | --- | --- |
| Read | Reader | Read |
| Read and Write | Editor | Read, Write |
| Read, Write and Manage | Admin | Read, Write, Manage |

Saving a real change disconnects all that person's application connections.
They must sign in and consent again. An unchanged save leaves connections in
place. If someone else changes permissions while you are editing, refresh and
review the new state before saving. The configured owner is labelled **Owner**
and cannot be blocked or changed here; owner selection stays in NS8 Settings.

## Approve or decline a request

**Needs application approval** means this exact application identity/callback
has not been approved. **Needs additional application permissions** means its
request exceeds the approved permission ceiling. Choose **Approve** to review
the verified name, origin, callback and permissions. New Write and Manage
permissions are not selected automatically. Existing approved permissions are
preserved by this request shortcut.

Application approval applies to that exact application for every user. Updating
an existing approval disconnects its existing connections; review that warning
before saving. A security-relevant metadata change can stop old connections as soon as it is observed during review, following the existing application-approval policy. Approval never changes the requester's role or a connection's
consented scopes. If a Reader needs Write, use the separate **Change
permissions** action. The person must still continue connecting and explicitly
consent. **Waiting for user consent** is not an active connection.

**Decline** cancels only the selected pending request. It does not block the
person, disable the application or disconnect an existing connection. The person
can start a new request. Requests expire after five minutes, so an expired or
already handled request requires a refresh. Declined requests disappear from
the active table rather than becoming a permanent history ledger.

## Disconnect a connection or block a user

**Disconnect application connection** stops only that selected connection's
access and renewal. It preserves the user's role, other connections, approved
applications and protected-space grants. The user can connect and consent again.

**Block user** persistently denies all C0 access and disconnects that user's
connections. Repeated sign-in and application restart cannot restore admission.
Choose **Unblock user** and explicitly select a role to admit them again. Old
credentials remain invalid; unblocking does not restore their old connections.
Existing stored protected-space grants keep their policy and remain capped by
the person's current workspace role.

A **Connected** row reports locally saved authority, not a live provider health
check. **Connected · renewal needed** means its saved provider verification is
stale and the client needs to renew; this alone does not mean another login is
required. **Needs reconnect** means locally observed authority is expired or
invalid. Refresh the table after an uncertain operation before trying again.
Disconnected or expired records may disappear during normal cleanup; this page
does not claim a durable connection history.

## Advanced and other administration

**Advanced** contains exact metadata/manual client configuration and diagnostics.
**Disable application for everyone** is explicitly global: it stops all of that
application's connections, without blocking its users. Enabling it later permits
fresh consent and does not revive old credentials. Manually approved UUID clients
remain independent of optional client metadata discovery, which defaults off.

Use **Protected spaces** for space-specific grants and **Background work** for
jobs and schedules. The Workspace access page does not load background tasks. The **Skip to content**
link keeps you on the current page and preserves the selected space.
A user's **Account → Your connected apps** still manages their own connections.

The supported legacy NS8 URL still offers first-party people and permission
management. Connecting ChatGPT requires the configured application hostname;
this page does not enable OAuth or MCP on a legacy path.
