# Bounded knowledge compilation

Use this protocol only when the user requests compilation or a separately enabled
automatic workflow authorizes it. Ordinary research remains read-only. Discover
`compilation_policy_get`, `compilation_source_bindings_get`, `compilation_propose`,
`compilation_tasks_list/get`, `compilation_run_claim/checkpoint`,
`compilation_status_get`, `compilation_dependencies_list`,
`compilation_plan_validate`, `compilation_apply` and `compilation_verify` in the
actual selected connection. Core 0.39 supplies coordination only; publication
requires the three newer tools. Do not assume availability from a package version.

All compiler tools select top-level `space_id`; REST selects its query parameter.
Mutation adapters carry their domain input in `data` and a sibling replay key when
required; MCP wraps that typed request inside its own `data` argument. Read the
actual schema rather than flattening these layers. Needs current Reader+Editor
and Read+Write, including space-scoped API-key bindings. Missing policy is disabled.
An Editor cannot enable it, grant scope or move to Shared as a workaround.

## Discover and analyze

Select at most three ready logical originals and 32 exact current chunks per task.
Read complete originals or explicitly selected outline/section/block context;
record omissions as unread. Add a deferred unread_source_context entry for each
original not fully reviewed; partial reads must not advance successful source coverage. Use source_bindings_get with `selections` of
`logical_document_id`, `revision_id`, `chunk_ids`, retaining its exact normalized
metadata. It validates multipart membership and current hashes. Read original
citations separately; never turn expired evidence into a new citation silently.
No automatic full-corpus discovery is part of this bounded compiler version.

Search Wiki and entity aliases, inspect existing pages and outstanding/terminal
tasks. Choose one canonical topic per primary Wiki page. A new key is stable,
namespace-qualified lowercase data; translated or paraphrased titles alone do not
create another concept. Reuse an existing target ID whenever equivalent knowledge
exists. Submit a proposal with policy revision, origin, closed reason, topic key,
source bindings and optional current page binding. Do not save queries, answers,
conversations, evaluation labels, secrets or free-form planning text in proposals.

Claim a bounded run with kind, cycle_key, lease_owner and policy revision. Retain
its lease tuple and actual run/task revisions. A task held for contradiction or
applicability is not automatically selected. Only an explicitly authorized manual
review may supply `review_task_ids` and `review_authorization_ref` to prepare it;
that reference is not publication approval. Respect consumed attempts, deadline,
shared daily/weekly budgets and current policy. Renew before expiry without
resetting usage. No project needs to be initialized.

Before a new external model call, checkpoint reserve_model with task revision,
request_id and maximum total input/output tokens; checkpoint start_model, then
return_model with observed_tokens or null plus a hashed provider receipt. Interrupted
started calls become uncertain; reconcile provider/agent state before retrying.
Core invokes no model. Already available reasoning may build a plan with null
usage_reservation_id and no new provider call; do not invent measured usage/cost.

## Plan and dry-run

The closed schema_version=1 plan contains space_id, task_id,
expected_task_revision, policy_revision, profile_id/version, source_bindings,
target_bindings, dedup_decisions, classification, operations, deferred and
usage_reservation_id. Follow the advertised nested schema. Do not add commands,
URLs to fetch, SQL, provider settings or prompts. Keep the entire plan within
262144 JSON bytes and at most 25 existing bundle operations.

One task has exactly one primary wiki.upsert at index zero and its unverified
verification annotation. Source-bound navigation includes quoted original passages
and their immutable chunk IDs in the body. A passage is `{chunk_id,start_offset,
end_offset,quote}` with absolute document Unicode code-point offsets and an exact original
slice. Never manufacture supporting quotes. The default profile permits Wiki and
unverified annotation operations only. The explicitly selected sourced-knowledge-v1
profile additionally permits entity create/update/alias/link, sourced claim
create/update and relation create/update. No delete/archive/unlink/schema/object,
source, access, job or schedule operations. Claims retain contrary immutable values.

Each content create/update has a target binding: operation_index, kind,
canonical_key, id, revision, content_id, content_hash, record_hash, managed and
evidence. Creates have null IDs/hashes, revision zero and managed=false. The
primary canonical_key equals the task topic_key. For a new primary page its stable
slug is `c0-` plus the first 32 hexadecimal characters of SHA256 of canonical JSON
`[space_id, profile_id, topic_key]`. Updates bind current actual record/revision and
expected_revision. Managed ownership comes from SQL dependency hashes, not a model
assertion or metadata marker. Authored edits require exact-plan review.

Dedup decisions identify an operation_index and an actual current candidate
binding, comparison (equivalent/distinct/ambiguous) and fixed rationale. Resolve
all candidates before create; equivalent targets must be reused. Indexed current
Wiki candidates omitted from the comparison require review. Alias ownership and
slug uniqueness are final race controls, not semantic matching. Structural
validation cannot establish semantic novelty or entailment.

Classification is extracted, supported_synthesis, uncertain, contradictory or
unsupported. Defer unsupported assertions with fixed reason and source IDs; approval
cannot make an unsupported plan publishable. Unknown applicability is an uncertainty,
not a supported product/version claim. No implicit version ranges or verified
annotations. Annotation value is exactly `{status:unverified,source_references:[
{kind:chunk,id:...}]}` using unique current references for primary-page support.
Use only earlier typed `$result` references and current expected revisions.

Call plan_validate with `{lease,expected_revision,plan}`. It rolls back its bundle
simulation and persists no knowledge/progress. Retain returned plan_hash,
identity_digest, classification and eligibility. A validation result is not a grant. If exact-plan approval is still missing,
checkpoint planned with its hash, then fail with unsupported_evidence to retain a
needs_review hold, and save partial. Keep only hashes/IDs in durable coordinator
state. Later explicit manual review reclaims the held task; current references and
exact-plan approval are still required. A classification rename cannot remove the
retained review hold.
The canonical plan hash excludes only expected_task_revision (a coordinator CAS);
all source/target generations, proposed content, decisions and policy remain bound.
Update the CAS after a planned checkpoint or fence recovery without changing approved
content. Empty plans finish only through the checked no_change checkpoint; deferred
work stays partial/reviewable. A no-change decision requires actual original inspection.

## Apply, read back and verify

Use the unchanged plan and hash, current lease/run/task CAS and stable request key.
Queue-only, graph-profile, authored, uncertain and contradictory changes require
`approval:{plan_hash,reference}` reflecting an actual explicit exact-plan decision.
Do not self-invent approval from Editor access or enabling learning. Automatic
supported navigation may proceed only under its policy and authorized workflow.

Apply commits one atomic bundle plus dependencies and a metadata-only outcome,
returning applied_pending_verify and actual record bindings. On a lost response,
get_task exposes `publication` with the committed plan hash and record identities.
Read those current records before retrying; unchanged replay keeps its key and
payload while the original authority/fence remains current. A stale fence rejects
replay. Reclaim the same logical run and verify its saved publication without
reapplying. Conflicts need reload/reconciliation, never blind overwrites.

Independently read all current Wiki pages, entities/aliases, claims/evidence,
relationships, typed links and annotations, and all original citations. Page reads
use wiki_pages_get; entity reads use entities_get; claims_get contains exact
original references; entity_relations_list and entity_references_list supply the
saved graph rows (typed links are in the references response list); knowledge_annotations_get selects the actual content revision.
Do not claim complete readback if a bounded list omitted a saved row.

`record_hash` is SHA256 of sorted-key, compact UTF-8 finite JSON over these stable
fields (UUIDs and timezone-aware datetimes use ordinary API strings):

- Page: id,slug,title,revision,deleted; content:{id,number,content_hash,metadata}.
- Entity: id,kind,label,metadata,revision,deleted; aliases sorted by normalized,
  each containing normalized,label.
- Claim: id,entity_id,page_id,predicate,value,metadata,revision,deleted,valid_from,
  valid_to,evidence_stale; evidence sorted by chunk_id, each with chunk_id and
  unavailable (true for a superseded reference).
- Relation: id,source_id,target_id,kind,metadata,revision,deleted.
- Link: id,entity_id,target_kind,target_id; missing targets fail readback.
- Annotation: id,target,namespace,revision,value,status,target_current,
  target_archived,current_content_revision.

Each observed binding is `{kind,id,revision,content_id,content_hash,record_hash}`;
nonpage content IDs/hashes are null, link revision is 1. The optional Python Core
client helpers implement these projections; agents on other hosts use equivalent
JSON. Compare actual reads with saved bindings rather than repeating the response
as evidence of reading it. Original source_bindings_get must still match the plan.

Call compilation_verify with lease, expected run/task revisions, policy revision,
task_id, plan_hash, observations and original source_bindings. Core rechecks them
in SQL. Only succeeded means persisted compilation was read back; annotation status
remains unverified. Finish the run only when all reserved tasks are succeeded or
source-checked no_change and external calls settled. Otherwise save partial with
actual failures/deferred findings. Read status; bounded completion is not complete
corpus coverage, semantic correctness, measured provider cost or scheduled execution.

On 410, discard expired source packets and copied proposed text, retaining only
hashes/IDs/recovery metadata. Read current originals separately and prepare new
source-bound work. Never preserve old bodies in coordinator state, receipts or
model traces. Reports expose actual changed identities, hashes, source dependencies,
conflicts, failures, unresolved/unsupported assertions and unknown usage. Do not
alter source scope, project manifests, learning policy, permissions or schedules.
