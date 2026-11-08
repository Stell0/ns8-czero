# Knowledge compilation acceptance and rollout

Compilation is disabled until an authorized operator enables policy in an exact
space. Editor permission alone does not enable learning. Use the installed compiler
skill and actual advertised server operations; installation never establishes a
connection, permission, completed compilation or scheduled task.

Before a rollout, preserve the current supported backup and installed identities,
read current membership/capabilities/policy, select bounded documents and record
source generations/hashes. Dry-run against current originals and Wiki revisions.
Inspect duplicate candidates, applicability, contradictions and unsupported
synthesis. Begin with queue-only publication and exact-plan review. Expired
citations stay unavailable; a new source generation requires a new reviewed plan.
Never overwrite authored edits or interpret source instructions as authority.

Read back saved task, targets, actual revisions/hashes, original citations and
source dependencies. `applied_pending_verify` needs independent verification.
A proposal, assessment, API success or host completion flag does not prove saved
knowledge or factual correctness. Distinguish assessed, compiled, stale, held,
conflicted, failed and uncertain work. A completed bounded run is not complete
corpus coverage. Observe unchanged inference/write suppression before increasing
budgets; then test one replacement and daily/weekly continuation in a disposable
space. Do not replace a production source to test this.

Use [the external host setup](../../samples/ingestion/examples/compiler/README.md)
for private configuration, scoped keys, explicit model access, dry-run, execution,
verification, recovery and timezone/DST behavior. Reuse an existing project's host
and lease; never create a duplicate project scheduler. A generated ChatGPT prompt
is not an installed task. Actual scheduled execution and durable authority must be
observed on the chosen host. M5's disposable Codex/systemd proof does not establish
ChatGPT scheduled compatibility or another host's renewable model authentication.

Unknown model/write outcomes retain their exact intent and usage reservation.
Inspect current task/publication/status before any retry. Do not clear a private
journal to repeat uncertain inference, reset budgets/attempts or blindly issue a
new create. Restore requires lease invalidation/expiry before hosts resume. Access
loss stops all writes and never falls back to Shared or broadens scopes.

## Repeatable quality measurement

Follow [the existing controlled protocol](../agentic-retrieval.md). Keep every
source, label, answer, audit, failed attempt and credential in private storage.
Build source-only knowledge before scoring and freeze numerical targets, model,
resources and language/product/version metadata. Use `loop --publisher compiler`
for reviewed production-compiler publication into invocation-owned disposable SQL
fixtures. The legacy publisher remains the default for existing studies.

The first invocation prepares source-only proposals and stops for audit. Save the
existing `label-audit.json` plus `compilation-review.json` in that private output:

```json
{
  "corpus_hash": "<digest of corpus.json>",
  "plan_hash": "<digest of initial-layer-builder/validated.json>",
  "provenance": "Source-based analyst independent of the builder",
  "records": [
    {"key": "<record key>", "source_supported": true, "uncertainty_preserved": true}
  ]
}
```

Review every record against current originals; include each key exactly once.
The digest is the protocol's canonical JSON SHA-256, not the file's byte hash.
Then resume with unchanged sources/configuration/publisher. Never tune from
validation/sealed results or relabel an exposed question as fresh held-out data.
Unknown publication responses stop; a saved exact publication can reconcile by
fresh Core target/source readback, never another create.

After measurement, save independent answer judgments in a private review file,
then run:

```sh
python scripts/evaluate-agentic-retrieval.py answer-audit /private/study \
  --reviews /private/answer-reviews.json
```

Reviews bind `freeze_hash`, nonempty analyst `provenance`,
`independent_of_producer: true`, and an `episodes` list. Each entry supplies the
actual episode directory name, canonical `episode_hash`,
`all_assertions_reviewed: true`, `correct` (true/false/null), nonempty `rationale`
and `assertions`. `correct` judges the complete response, including citation and
literal applicability fields. An optional `content_correct` judgment separately
records source-based answer correctness without treating a citation-field or
product-tag formatting failure as a different technical fact. Missing prose
judgments remain unreviewed; neither rate replaces the frozen quality gates.
Each assertion contains its verbatim answer/part `text`,
`verdict` (supported/unsupported/uncertain), and actually observed original
`chunk_ids`. Supported assertions need original evidence; review the entire
narrative as well as structured parts. The attestation is an analyst's semantic
judgment, not machine-proved entailment or independent human review.

The saved answer-audit report retains unreviewed/unknown/failed denominators and
separates answer accuracy/unsupported assertions from evidence completeness,
Recall@K/MRR, citation validity, applicability, latency, calls, observed tokens and
charged reservations. Provider price remains unknown unless actually reported.
Publish sanitized aggregates only. A small bounded study may complete with unmet
thresholds; report that outcome, the exact corpus coverage and limitations instead
of claiming a retrieval improvement. Missing private-copy authorization leaves
private disposable compilation acceptance open, even when synthetic checks pass.

Core publication, released-consumer adoption, production deployment, learning
activation and schedule installation each retain their separate acceptance and
authorization requirements. No M6 benchmark result activates them automatically.
