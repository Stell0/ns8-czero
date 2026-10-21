---
name: c0-create-feature
description: Implement a C0 application feature in an ns8-czero fork, placing reusable domain behavior in Core and application-specific transport or UI in the fork.
---

Read the repository's AGENTS.md, README.md and active PLAN.md milestone before editing. Refine its implementation subplan and acceptance before code; preserve established API, evidence, membership and recovery contracts.

Choose the layer by responsibility:

- Shared domain/data operations belong in `packages/czero-core`; use `$c0-develop-core` for those changes.
- Fork-specific workflows, FastAPI transport and separate user UI belong in `app`. Reuse trusted Core services/operation bindings. Do not turn request names into imports or commands.
- NS8 installation, settings, events, systemd and backup remain focused numbered scripts in `imageroot`. Use installed `nethserver-ns8-module`, `nethserver-containerfile` and other relevant NethServer skills from https://github.com/NethServer/agents. Do not copy their manuals here.

Keep Reader/Editor/Admin membership authoritative inside Core transactions. Preserve immutable evidence/revisions and bounded work; optional providers cannot determine authorization. UI uses local assets, DOM text, draft/replay protection and response-generation guards. Add meaningful service/transport/UI tests alongside the feature and extend real native recovery when persisted data changes.

Use the repository's current development commands and frozen predecessors, not version numbers copied into this skill. Keep tests, skills, plans and private fixtures out of runtime images. Commit/push and verify actual CI results within the user's authorized scope. Only test live on an explicitly authorized dedicated instance; destructive fixtures remain disposable. Update the three project documents with executed evidence and honest limitations.

Read the [fork development reference](../../references/development.md) for verification and managed-file boundaries, and the upstream [development guide](https://github.com/Stell0/ns8-czero/blob/main/docs/development.md) for reference-app commands. The fork's active manifests and CI policy remain authoritative.
