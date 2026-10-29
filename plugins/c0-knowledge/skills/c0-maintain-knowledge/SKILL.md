---
name: c0-maintain-knowledge
description: Save selected evidence or create and update knowledge in the C0 instance associated with this plugin when the user requests a change. Use for sourced Wiki maintenance and selected text ingestion, not read-only research or permission administration.
---

Read [the instance binding](../../references/instance.md), then discover current tools and authorized spaces. Confirm the intended space, resource and change when unclear. Preserve an explicit space selection on every operation; denial never permits falling back to Shared or another app.

Read existing content and original evidence before editing. Make only the requested changes. Authorized edits publish immediately; do not imply that a separate review or publication stage exists. Keep credentials, unrelated personal data and unselected conversation material out of saved knowledge.

- For selected text or Markdown, follow [evidence ingestion](../../references/maintenance.md#selected-text-evidence).
- For page changes and conflicts, follow [revision-safe updates](../../references/maintenance.md#revision-safe-updates).
- For related changes, annotations or supersession, follow [consolidation](../../references/maintenance.md#consolidation).

Tool schemas and current server capabilities govern the request. Not every mutation accepts an idempotency key. Do not repeat an uncertain ordinary create automatically; inspect stored results first. An unchanged replay-protected request keeps its key; a changed request gets a new one.

Read back saved current content, revision counters and evidence links. Superseded automatic bodies are removed; keep authored quotations and report expired evidence as stale/unavailable. An expired exact citation or superseded replay returns `content_superseded` (410), requiring current readback and reconciliation. Report exactly what changed, the selected space, saved identities/revisions and any incomplete work. Queued extraction is not successful ingestion of usable evidence. Permission denial needs an authorized grant; insufficient OAuth scope needs fresh explicit consent if the user's role and approved client permit it.
