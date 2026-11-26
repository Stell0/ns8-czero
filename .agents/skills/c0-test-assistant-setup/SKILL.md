---
name: c0-test-assistant-setup
description: Verify C0 assistant setup, consent, skill installation and unattended use through real ChatGPT, Claude, Grok or Gemini web sessions on an authorized lab instance.
---

Read the [assistant setup guide](https://github.com/Stell0/ns8-czero/blob/main/docs/byoa.md) and the [current acceptance plan](https://github.com/Stell0/ns8-czero/blob/main/PLAN.md#assistant-setup-and-first-use-experience). Prefer their local copies if present. Use the browser for the actual vendor and C0 pages. A local SDK, mocked web test or provider documentation can corroborate a result.

## Prepare the lab

- Confirm the authorized NS8 module ID and configured public HTTPS route match. Record the C0 source, installed image digests and readiness. Before changing a shared lab instance, identify hosted applications and follow its supported backup/update procedure. Request a user login handoff when the browser reaches credentials or MFA. Keep credentials and full OAuth URLs out of chat, saved evidence and Git.
- Use an explicitly selected disposable space. Seed a small synthetic source with a unique phrase and a known fact, and a Wiki page with a known starting revision and current citation. Prepare a second unauthorized space and Reader, Editor and administrator test paths as appropriate. Leave private or production knowledge outside the test.
- Compare the old and new setup from a clean browser when requested. Record the vendor, product surface, account type, setup actions, repeated inputs, switches between sites, first useful failure and time to the first verified read.

## Exercise the actual connection

1. Open C0 **Use with AI**, choose the provider, and follow the published recipe. Review the app identity with the user. Record requested, offered and granted scopes, and the background setting. Verify the C0 connected-app entry before assuming a grant exists.
2. Install the instance's designated skill in the web product. Start a fresh conversation with that connection and verify the installed skill is selected or observably invoked. Record the actual instruction mechanism if using saved project instructions or pasted content. Credit native skill installation only after seeing it in the vendor's skill manager and observing use in a new conversation.
3. Ask for the connected account and synthetic fact from the selected space. Open the assistant's citation in C0 and match the current passage. Use a fixture edit for Write and a harmless administrative read for Manage when those scopes are approved. Check the saved page independently in C0. Require exactly one new revision after retry. If a write response is uncertain, read back the page before repeating it. A tool result can report an error even when the HTTP request succeeds.
4. Use disposable sibling connections for negative tests. Verify Reader write denial, access denial in the other space, and exact disconnect of one grant while the retained grant still works. Verify background renewal through real identity-provider logout and access-token expiry. Compare a grant with background enabled against an interactive control.

## Verify unattended use and close out

- If the web product supports scheduling with the exact C0 connection and skill, create a short-lived fixture task for the approved test. Read the saved task, next occurrence and time zone. Observe an actual due run and inspect the invocation, current C0 citation and saved revision. A manual run establishes a separate result. Stop the temporary test schedule after the check.
- Record results for authentication, installed skill use, read, write, manage, renewal, due run and disconnect. If blocked, capture the last successful step, sanitized error or missing control, and attempted recovery. Keep account-specific traces private. Preserve requested working installs and remove only test artifacts approved for cleanup.
