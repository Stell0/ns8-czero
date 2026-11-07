---
name: c0-maintain-semantic-layer
description: Propose, apply and verify bounded source-backed semantic knowledge in an explicitly authorized C0 space with managed identities and current-generation provenance. Use for sourced knowledge maintenance, not global schema installation or unsourced enrichment.
---

Read [the semantic profile and recovery contract](../../../docs/agentic-retrieval.md#semantic-profile).
C0's semantic layer already consists of entities/aliases, claims, typed records and
relations, applicability/verification and sourced Wiki navigation. Original evidence
remains authoritative. Do not introduce another graph store or infer a schema.

Accept a selected corpus/current hashes, approved profile, managed namespace,
operation budget and private state path. `scripts/evaluate-agentic-retrieval.py
layer` generates a proposal from originals. The minimal supported automated profile
manages sourced Wiki navigation and unverified source-bound annotations. Broader
entity/claim profiles use existing C0 operations and require explicit schema scope.

Initial construction receives no benchmark questions or labels. During improvement,
development failure categories may inform generally useful navigation. Independently
justify every change from originals. Never index question text/IDs, gold keys,
grading instructions or evaluation hints. Validate plans and compare their text
against the private question set before applying. Review proposed titles, synthesis,
quoted support and classification first. Unknown applicability stays unknown;
literal version tags never become ranges. Model output is not verified knowledge.

Use dry-run, bounded apply, status and verify with the saved private state. Writes
use supported APIs, stable namespaced slugs, expected revisions and durable intents.
An uncertain write retains its exact replay key; reconcile it before another write.
An authored edit or conflict stops without overwrite. Reruns leave unchanged pages
unchanged. Preserve unrelated authored records, mappings and all original evidence.

Verify current source generations/hashes and original citations. Replacement/access
loss makes old support stale or unavailable; stop and prepare a reviewed current
plan. Never rebind an expired citation to new text or preserve expired source bodies.
No production enrichment or schedule is implied by this skill.

For production compilation on a server advertising compilation_plan_validate,
compilation_apply and compilation_verify, use the packaged c0-knowledge-compiler
workflow and its [protocol](https://github.com/Stell0/ns8-czero/blob/main/plugins/c0-knowledge/references/compiler.md).
The evaluator's local ledger remains an experimental profile, not a substitute
for enabled policy, SQL coordination, atomic dependencies or fenced verification.
