---
name: c0-setup
description: Connect or check the C0 instance associated with this plugin, including sign-in, account identity and authorized knowledge spaces. Use when setting up C0 or resolving connection and permission problems.
---

Read [this package's instance binding](../../references/instance.md). Use only its associated C0 app. If that app or its tools are missing, explain what is missing and guide the user through connection; do not substitute a different instance.

Follow [connection setup](../../references/connection.md) when sign-in or client approval is needed. Ask the user to complete private login in the provider page. Never request passwords, access tokens, cookies or a full OAuth authorization URL in chat.

Once connected, call `get_profile` and `spaces_list`. Show the returned account label and ask the user to select the intended authorized space if ambiguous. A returned profile proves the connected account, not membership in an unlisted space. Do not save or alter content during setup.

For a first read, use `c0-research` with a topic the user chooses. Report the instance, account and selected space, what was actually checked, and any remaining administrator action. Explain that plugin installation and C0 membership are separate.
