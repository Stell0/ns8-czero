# Synthetic offline WikiPlant snapshots

Both directories contain fabricated raw records and provider identifiers. Their
format follows WikiPlant e8dd9e7ae9b48d028cf9a735b30490749c3d8d6c; they contain no
production wiki, account or Drive data. Instance runtime identities are synthetic.
Do not activate their schedules or use their authorizations for real tracking.

The snapshots cover original source timestamps, separate event dates, canonical
topic/Wiki metadata, pending/retrying lineage, interrupted monitoring, saved
results awaiting merge, past reports and operation receipts. Export manifests
preserve fabricated raw-file IDs/generations/checksums. Canonical synthetic names
come from these configurations; actual production project names remain unverified.

Use `c0-projects wikiplant validate --input tests/fixtures/wikiplant/robotelier
--output /private/new-validation-directory`. This creates local preparation
artifacts, performs no C0 writes and installs no workflow or schedule.
