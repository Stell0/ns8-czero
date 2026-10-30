# Project workflows

The binding fixes the instance, protected space, project, manifest version, language and approved primary topics. Instructions describe product workflows, not authority to access additional projects.

## Setup

Use an explicitly selected existing protected space. Setup/configuration and ongoing user-topic authorization need actual Admin authority and affirmative user references. Read before initializing; use one stable initialization replay key. Create approved user anchors, then save the validated manifest at its expected revision. Keep external schedules disabled until separately requested and verified. Do not migrate real legacy data as part of setup.

## Lookup

Search the selected space, read matching Wiki revisions and original passages, and check current applicability/verification. Missing evidence is unknown. Answer without mutations. Exact source/version/document/chunk citations take precedence over search excerpts or authored summaries.

## User-directed intake

Save only the explicitly selected material. Resolve existing identities before creating records. Use source ingestion for originals; text has a 131072-byte UTF-8 bound and binary ingestion uses REST. Common collectors handle selected large inputs without silent truncation. Poll the actual source/version read operations for extraction readiness; do not repeat ingestion to poll. If extraction is still queued, return QUEUED with the actual stored source/version identities and explain that a passage citation is pending. Wait for successful extraction and inspect actual passages before creating supported claims or returning an evidence citation. Read back content and return stored identities.

## One-off investigation

Claim a stable manual_research run for the user's request. Apply project_queue_admit with its actual question/context, user reference, scope assessment, direct anchors and causal lineage. A merge resumes existing work; a capacity deferral stays visible. Reserve an eligible attempt before research, persist invocation started, then save its actual outcome. Uncertain calls require reconciliation. A saved result awaiting Wiki merge resumes that merge without another attempt.

## Topic tracking

Permanent user topics need affirmative ongoing-tracking authorization and Admin scope. Adjacent topics require a recorded direct contribution to active user anchors, not adjacent-to-adjacent relevance. Peripheral topics cannot generate follow-ups and expire at their recorded future weekly checkpoint. Classification and lifecycle are separate. Archived topics do not silently reactivate. A source or one-off request cannot expand monitoring scope.

## Evidence review, adversarial checks and synthesis

Distinguish observed fact, supported inference, hypothesis, contradiction, outdated assertion and unknown. Resolve every cited immutable passage against its source/version/document. Consequential conclusions need bounded contrary-evidence checks; an unperformed check is not a successful challenge. Preserve separately authored claims, validity windows and intentional quotations. Source/Wiki replacements remove superseded bodies; mark expired supporting evidence stale and never silently rebind it. Apply verification/applicability to the exact current revision; a new Wiki revision does not inherit its predecessor's status.

Write readable Markdown as the Wiki body. Keep structured metadata in metadata fields; never serialize a complete page object or JSON envelope into the body. Use current revisions, supported replay keys and knowledge bundles within their actual operation/payload limits. Read back source, claim and Wiki updates before marking research complete.

Use project_result_save for the reserved attempt or actual monitoring cycle. Findings record classification, confidence, evidence, limitations and assessment. Consequential conclusions need bounded contrary-query observations with ready search-response snapshots; unperformed checks remain partial. Save the returned result UUID in the invocation outcome. Wiki metadata c0_project binds project_id and result_references. Use project_result_publish with actual current Wiki revision UUIDs, then complete research with its stored publication proof. An edited Wiki revision needs explicit new verification.

## Reports

Prioritize what was learned, changed assumptions, project implications, evidence/confidence, contradictions and next investigations. Include completed work, important queued/deferred work, monitoring coverage/failures and brief operational details in the project's language. Every completed result needs a substantive entry or a saved appendix reference. Save and read back the report and exact revision. Retry publication of the saved report without repeating research. Do not equate a saved report with a delivered notification.

Prepare/resume with project_report_prepare under the report phase or a separate report_publication run when daily work is incomplete. Save Wiki metadata c0_project with project_id, actual report_reference and language. Use project_report_member_set for each result's exact saved Wiki revision and UTF-8 text range, or explicit deferral with a substantive explanation. Finalize with project_report_finalize and read project_report_get. Omitted completed results block finalization; deferred results remain due. Record publication started before its external call and actual outcome through project_report_delivery_observe. Reconcile uncertain outcomes before retrying. Notification and human reading need their own observed evidence; never fabricate them.

## Maintenance and recovery

Use the weekly prompt for bounded structural checks and rotating semantic review. Persist actual cursors, inspected revisions, coverage and limitations. Incomplete semantic inspection is partial. Archive summaries retain lineage and exact evidence identifiers; referenced bodies may expire. Calendar work uses ordinary admission; dates do not authorize new scope. Check workflow/skill updates as metadata only and never install a runtime upgrade automatically. Use only capabilities actually present. If a required operation is missing, save a BLOCKED/PARTIAL checkpoint only when a supported checkpoint service is available. Otherwise explain that the capability report is unsaved; do not invent a durable receipt. Provide a concrete handoff in either case.
