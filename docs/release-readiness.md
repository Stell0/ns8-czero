# Documentation and plugin release checklist

## Current status

M21 implementation is in progress. **Documentation and skills release readiness is not yet accepted.** M19 runtime passes its recorded acceptance; reviewed closeout PR30 is merged as `0a9bbb3` and main39643655916 passes. The entry gate is complete. No stable NS8 release or public OpenAI listing is claimed.

The end-user package template is version 1.0.0. The application presentation patch targets 0.49.1; Core0.31/schema0018 and authorization contracts remain unchanged. Use [PLAN](../PLAN.md) for actual verified sources/digests, not an untested version number in this checklist.

## Required evidence

| Gate | Required result | Status |
| --- | --- | --- |
| Current documentation | Correct current guidance, usable navigation, retained archive links, sanitized examples | Local links and independent read-only review pass; final checks pending |
| Developer skills | Five routed skills with valid references and available prerequisites | Five metadata/reference checks and standalone fork references pass |
| Package | Valid manifest/app binding, license, deterministic ZIP/checksums, two-instance separation, no secrets/hooks/inline MCP | Local package/schema checks pass; first web upload found ZIP-layout error, corrected single-plugin retry pending |
| Independent behavior | Actual disposable MCP/database checks of citations, ambiguity, denial, injection, ingestion, conflict/retry and read-back | Pending |
| Cold-start walkthrough | Tester needs only the published guides/package, no private maintainer runbook | Read-only independent walkthrough passes after three corrections; actual account actions pending |
| Private Creator on web | Actual installed packaged workflows, correct app/account and positive/negative cases | Pending |
| Managed import on web | Actual GitHub import/app binding and installed workflows under intended role | Pending |
| Runtime acceptance | Exact full/released-Core/image/both-native checks and actual artifacts; guide tested in real browsers | Pending |
| Dedicated deployment | Supported targeted candidate update, preserved data/clients/settings, live guide/client/restart/journal checks | Pending |
| Reviewed main and closeout | Regular merge, actual main/publication and separate checked documentation marker | Pending |

Record immutable documentation/source and package hashes, tested ChatGPT surface/workspace features, dates, actual outcomes and limitations. Keep raw traces, instance mappings and credentials private; publish sanitized summaries. A package validator, replay fixture or desktop run cannot establish ChatGPT web installation or skill behavior. Missing account/workspace permissions leave the corresponding gate incomplete.

## Release scope

This milestone prepares documentation and skill artifacts for distribution. It does not publish an OpenAI directory listing, enable a workspace-wide rollout or tag a stable NS8 module. Platform/IdP/proxy compatibility, deployment log policy, unresolved vendor findings and real-provider retrieval quality remain explicit software release/maintenance obligations. Record their current disposition rather than erasing historical limits or presenting a successful scan as zero findings.

## Keeping guidance current

Update user/admin instructions when visible behavior changes. Update technical reference links and skill workflows when interfaces change, and revalidate generated packages. Version plugin content deliberately; replacing a private workspace plugin or syncing a repository is an external action with its own intended audience. Keep its registered app identity stable across content-only updates.

Run link/anchor checks and skill/package checks for edits, then the applicable CI policy. Review upstream OpenAI UI/format instructions against official documentation before publishing setup changes; record actual tested routes and account prerequisites. Preserve the historical evidence archive and frozen runtime references while keeping transient counts out of normal setup instructions.
