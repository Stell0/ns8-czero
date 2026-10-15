# Example acceptance

This standalone fixture demonstrates released Core consumption and reviewable
managed-file updates. Consult the parent project's authoritative PLAN.md for
executed release/CI/PR evidence; preparation is not a passed acceptance gate.

Acceptance sequence:

1. Verify Core release source/checksums; lock and install the declared Git tag.
2. Run consumer checks outside the C0 checkout without a local Core override.
3. Publish a compatible Core patch; run native Renovate and inspect the actual
   dependency/lock proposal and completed consumer CI.
4. Change an explicitly managed upstream file; inspect its actual sync proposal.
5. Customize a managed file and update upstream; require the proposal to preserve
   the customization and provide concrete migration instructions. Resolve it
   with behavioral tests before clearing its review flag.
6. Isolate reusable contributions from example-only application customization.

The copied NS8 files are review fixtures. They are not an installed module and
these consumer checks do not replace native update/restore acceptance.
