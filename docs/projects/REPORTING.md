# Evidence, results and reports

Knowledge uses existing sources, immutable passages, claims, Wiki revisions and
revision-specific annotations. Project records coordinate these resources; they
do not duplicate original documents or run a model.

## Result persistence and verification

`project_result_save` / POST `/api/v1/project/results` requires the current lease,
exactly one `attempt_id` or `cycle_id`, validated `data`, `expected_revision` and
a replay key. Research must already have a reserved, started attempt. Monitoring
results belong to the actual primary-topic cycle and its scope hash.

Data contains `summary`, `changes`, `importance`, `assumptions`, `uncertainties`,
`assessment_ref` and one to twenty findings. Each finding records `statement`,
`classification`, confidence0–100, `rationale`, actual `citation_ids`, optional
`claim_id`/exact `claim_revision`, `consequential`, `applicability_limits` and
`challenge`. Classifications are observed_fact, supported_inference, hypothesis,
contradiction, outdated_assertion and unknown. Factual assertions require ready
same-space immutable passages. Claim references must actually use those passages;
their value hash and validity windows are retained. Confidence is an assessment,
not a substitute for evidence.

Consequential conclusions require a recorded contrary check: alternative,
falsification conditions, bounded query observations, coverage, contrary evidence
and any resulting conclusion change. At most three distinct queries and ten
contrary passages per result are permitted across amendments. A successful query
observation names a ready passage from an ingested search-response snapshot whose
source metadata has `source_type: query_observation`, the exact `query` and
`external_reference`. Monitoring checks also resolve to its reserved successful
query calls, staying inside the monitoring caps. These are attributed external
observations, not proof of provider honesty or semantic adequacy. Unsearched,
failed or unresolved checks leave consequential findings PARTIAL.

The stable result identity is derived from its attempt or monitoring cycle/scope.
Pending amendments retain earlier assertions, evidence and query identities;
they may explicitly mark an earlier assertion outdated or contradictory. A
published result still awaiting attempt/cycle completion can receive an expected-
revision amendment for fresh claim/evidence review without another attempt;
publication must then be verified again. Completed results are immutable.
Individual versioned findings and result
history preserve corrections and contradictions. An attempt's returned outcome
must name the actual result record UUID; an arbitrary stored object cannot stand
in for a research result.

`project_result_publish` / POST `/results/publish` verifies the result against
current actual Wiki revision UUIDs. Wiki metadata must contain:

```json
{"c0_project":{"project_id":"<protected-space-uuid>","result_references":["<actual-result-record-uuid>"]}}
```

Write Markdown in `body` and structured values in `metadata`. Serialized page
envelopes are rejected; fenced JSON examples remain valid Markdown. Publication
records pin Wiki revision UUIDs/hashes and evidence/claim proofs. Complete the
research attempt using its actual `result_publication_v1` UUID. A saved result
awaiting merge resumes without spending another research slot. An intervening
Wiki revision requires explicit new verification. Existing annotation services
retain exact revision applicability/verification and never inherit it silently.
Material monitoring advances its watermark only after these proofs succeed and
the result cites a successfully inspected source passage from that cycle.

## Report lifecycle

The report identity is project + daily/weekly + local date. Use the source run's
report phase, or claim a separate `report_publication` run to report incomplete
research without falsely completing its daily/weekly run.

1. `project_report_prepare` / POST `/reports/prepare` creates/resumes a draft.
   Explicit amendments require `amend: true` and its current expected revision.
2. Store readable Wiki Markdown in the project language. Metadata `c0_project`
   contains `project_id`, actual `report_reference` UUID and `language`.
3. `project_report_member_set` / POST `/reports/members` records each actual
   result UUID, included/deferred disposition, main/appendix location, exact
   Wiki revision UUID and UTF-8 byte range, reason and assessment reference.
   Entries must contain substantive text; semantic assessment remains external.
   Main Markdown must link saved appendices using their exact
   `page_id=<uuid>&revision=<number>` target.
4. `project_report_finalize` / POST `/reports/finalize` verifies saved Wiki
   content/hashes and every member. Every completed unreported result through
   that local date must have an entry or explicit deferral. Concurrently completed
   results cannot disappear between inventory and save. Deferred evidence remains
   due in later reports. Excess bounded inventory fails explicitly.
5. `project_report_get` / GET `/reports` reads a chosen local date or the latest
   saved report, immutable Wiki identity, paginated members and delivery states.

Reports preserve individual membership, saved history, content hash and actual
Wiki page/revision identities. Saved appendix references remain pinned even if a
later revision changes their interpretation. Monitoring expected/completed counts
and incomplete coverage are separate from persistence. A successful report save
cannot make failed monitoring successful. Daily/weekly successful report-phase
checkpoints require the actual saved report reference.

## Independent publication observations

`project_report_delivery_observe` / POST `/reports/delivery` runs under a current
report-publication lease. Record external_result started before invoking a host,
then succeeded/failed/uncertain with actual external/evidence references and
operator_report, runner_report or sdk_simulation attribution. Unknown outcomes
require reconciliation before another invocation. Failed attempts back off from
30seconds to one hour, at most five attempts; retries reuse the saved report and
never rerun research. Fencing rejects stale owners.

Notification and human_read are separate observations requiring evidence; they
cannot be inferred from HTTP200, queued work, SAVED or external publication.
No notification transport or external agent executes in C0.

## Deterministic client publisher

`c0_projects.reports` validates externally authored plans, renders Markdown and
saves/readbacks reports through existing OAuth/SDK operations. The CLI reuses an
explicit protected private job:

```sh
c0-projects project report --config config/project.json --input report-plan.json --apply
```

The plan contains the current publication `lease`, `report_type`, `local_date`,
nine `sections` strings and `entries`. Entries have `result_reference`,
`disposition`, substantive `text`, `reason` and `assessment_ref`. Optional nine
`headings` supply localized labels. English/Italian headings are built in; other
languages require explicit localized headings. Sections prioritize new learnings,
goal changes, connections, events, uncertainties, completed research, queued/
deferred work, monitoring failures and brief operational details.

The immutable plan can resume lost replies with deterministic replay keys. It
never overwrites a conflicting Wiki slug or generates research prose. Oversized
reports fail with a request to save bounded appendices through the direct API;
content is never truncated. Private job authentication and space-binding checks
remain unchanged. External result publication is a separate host operation.

M5 verification is recorded in PLAN.md. Synthetic SDK/provider outcomes and
disposable native fixtures do not establish actual external-agent or unattended
execution, notifications or human reading.
