# Development feedback, merge acceptance and deployment acceptance

A single [C0 validation workflow](../.github/workflows/validate.yml) owns PR and
main validation. This policy replaces older per-commit/full-marker instructions.
It changes no runtime API, package version, dependency pin or database schema.

## Development feedback

Open a draft PR. Each update classifies its complete Git diff against its base,
including deleted paths, both sides of renames and file modes. There is no second
branch-push validation run. New feedback supersedes older feedback for that PR;
mode transitions also retire obsolete development checks. Full acceptance runs
are never cancelled by this policy.

The explicit allowlist in [ci_policy.py](../scripts/ci_policy.py) contains only
reviewed repository guidance: root README/PLAN/AGENTS, the listed development
notes and Git-only agent skills. Documentation-only PRs **and main commits** run
UTF-8, conflict-marker, diff/local-link checks and policy regressions. They skip
packaging, images and QEMU. This exemption does not cover arbitrary Markdown:
Core's packaged README/LICENSE, app/static HTML, generated contracts, locks,
container inputs and native build metadata have runtime/build impact.

UI feedback runs the controller suite, relevant application/template checks and
shared PostgreSQL-backed authorization/compatibility smoke. Native Vue changes
also build with the immutable Yarn lock. Application feedback adds the affected
integration suites. Core/authentication/migrations/dependencies/containers/native
lifecycle/CI machinery receive broad serial Python/PostgreSQL/packaging, script,
schema/shell and Robot feedback. Unknown paths trigger full acceptance.
PostgreSQL tests share no mutable database with another job or run and are not
split into concurrent shards. Dependency download caches retain the existing
pinned inputs; builds keep frozen Python/Yarn locks and explicit Core selection.

A scoped runtime draft intentionally has a blocked **C0 merge gate**. Passing
feedback is useful development evidence and cannot authorize a runtime merge.

## Merge acceptance

Mark a runtime PR ready for review. `ready_for_review`, `synchronize`, `reopened`
and initial ready PR events select full validation; later commits repeat it.
Changing back to draft blocks merging. These are explicit [GitHub PR events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request).

Full acceptance runs all PostgreSQL/Python/packaging cases, Node scripts,
schema/shell and Robot checks, producer and independently released-Core builds,
actual runtime/license/parser audits, all five scan/SBOM pairs, Debian genuine
predecessor upgrade and Rocky installation with all eight automated browsers.
It retains backup/clean restore, exact OAuth/content receipts, extraction/indexing
recovery, accessibility and downloaded artifact privacy checks. Existing CPU and
interactive-Playwright waivers remain unchanged.

Every candidate uses `ci-<source>-<run>-<attempt>` image tags. All three registry
revisions/digests and the module's exact sibling references are verified before
QEMU. Native reports compare actual installed app/database digests and the module
digest with those candidates. Both actual Git checkout logs, expected skips,
mandatory browser/privacy workflows and bounded numeric accessibility evidence
are inspected. A missing, skipped, cancelled or failed required job is not proof.

The always-scheduled **C0 merge gate** verifies current head/base, complete diff,
readiness, classification and required jobs/artifacts. It has no workflow path
filter that could leave it indefinitely pending. Repository protection requires
this named GitHub Actions check with an up-to-date base. No merge queue is in
use, so no `merge_group` trigger is introduced. See GitHub's [required-check
semantics](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks).

Before an autonomous merge, run from a reviewed checkout:

```sh
python scripts/verify-promotion.py --source <exact-head-sha> --pr <number>
```

This downloads the successful run's acceptance proof and verifies actual jobs,
source, base and classification. Historical successful commits, scoped feedback,
missing jobs and skipped full validation cannot authorize runtime promotion.
Primary-agent diff review must be recorded honestly; this tool is not an
independent human review. Existing protections/review requirements are retained.

## Main, manual runs and releases

Runtime main commits repeat full validation. Only a fully accepted current main
candidate is promoted to canonical `main`/`latest` aliases, without rebuilding.
The module retains immutable candidate sibling tags. A source superseded by later runtime changes
cannot overwrite canonical aliases. A later allowlisted documentation merge does
not strand an in-flight runtime candidate: its runtime/build inputs are unchanged.
Documentation-only main commits otherwise leave accepted runtime images in place.

Manually dispatch **C0 validation** (`validate.yml`) for full validation of any
exact branch/tag ref, including documentation markers. To validate a ready PR,
pass `pr_number` and dispatch its current head ref. Manual full runs never take
the documentation exemption. Standalone helper/local/UI runs are not merge proof.
Use a fresh full dispatch to retain failed-run evidence when repeating acceptance.
No new schedule is introduced. Existing upstream-update schedules are unchanged.

Core `core-v*` publication retains exact version/tag/checkout, both native status
contexts, supplied artifact installs/migrations, reproducible wheel/archive hashes
and immutable no-clobber publication. It additionally requires exact-source full
acceptance proof. Scoped or documentation-only success cannot publish Core.
Module release tags also select full validation before publishing their aliases;
Core tags never publish NS8 module aliases. No release is created by this policy.

Full candidate publication needs a repository-authorized registry writer. Fork
PRs can obtain read-only feedback; a maintainer must bring reviewed runtime work
to an authorized branch for publication/full acceptance. Tokens are not copied
into fork secrets and untrusted PR code is not run with `pull_request_target`.

## Deployment and milestones

Merge acceptance does not mean deployment acceptance. Before a dedicated-instance
update, require full proof for the exact runtime source:

```sh
python scripts/verify-promotion.py --source <exact-source-sha> --full
```

Then retain supported C0-only backup/integrity, three-image/native inventory,
canonical native update, real readiness, preservation of original data/OAuth/
settings/jobs/schedules/unrelated modules, live client workflows, restart and
bounded positive-control root journald privacy. Genuine installed predecessors
remain frozen independently of documentation images. Destructive restore tests
remain disposable. Milestone-specific live gates still apply; a lightweight
closeout marker does not replace the accepted runtime's release/deployment proof.

## Executed development evidence

Source `c9f62f4` has actual broad draft feedback [39140980732](https://github.com/Stell0/ns8-czero/actions/runs/39140980732): 1254 Python/PostgreSQL/packaging cases, 125 scripts and 21 Robot checks pass. The merge gate remains blocked because scoped feedback is not runtime acceptance. Earlier obsolete feedback runs 39140523676, 39140624127 and 39140829879 are actually cancelled; no acceptance run was cancelled.

Controlled probes [PR 15](https://github.com/Stell0/ns8-czero/pull/15) and [PR 16](https://github.com/Stell0/ns8-czero/pull/16) target that frozen policy source and are closed unmerged. Actual checkout logs, classifications, jobs and proof artifacts are inspected:

| Observed check | Earlier policy | Scoped policy |
| --- | --- | --- |
| Local feedback / UI feedback workflow | 466 s, plus a duplicate 462 s run | 110 s, 63 PostgreSQL cases and 125 controller checks |
| Documentation PR acceptance | 2386 s across local, publication and native gates | 28 s, 44 policy regressions and lightweight docs checks |

These are measured single-run job spans, not estimates or a general performance guarantee. Baseline is documentation source `e05ed46`: [local push](https://github.com/Stell0/ns8-czero/actions/runs/39136439156), [duplicate PR](https://github.com/Stell0/ns8-czero/actions/runs/39136456995), [publication](https://github.com/Stell0/ns8-czero/actions/runs/39136439125) (131 s) and [native](https://github.com/Stell0/ns8-czero/actions/runs/39136605761) (2250 s). Its native checkout is e05ed46 despite workflow_run's different default-branch context. New [docs](https://github.com/Stell0/ns8-czero/actions/runs/39141211821) and [UI](https://github.com/Stell0/ns8-czero/actions/runs/39141216790) sources are 40358fa and a049eba. Runner/cache/load effects remain possible. UI feedback latency is 76.4% lower in these observations; full runtime/native acceptance is still required.

The docs gate succeeds without image, packaging or QEMU jobs. UI feedback succeeds while its runtime merge gate fails. The actual promotion verifier accepts the ready documentation PR but rejects **both** probes for full release/deployment promotion. A new-source success cannot be inferred from these probes.

Main protection is now actually configured and re-read: required `C0 merge gate`, pinned to GitHub Actions app 15368, strict up-to-date base and admin enforcement, pull requests with zero mandatory human approvals, and no force pushes/deletions. No prior protection/ruleset was overwritten; no merge queue is configured. Primary-agent review is not represented as independent human review.

Current focused policy/release/image/log-reader regressions pass 63 cases. Broader unit evidence initially passes 309 cases in 4.55 s; the two added CLI compatibility cases also pass. The actual GitHub CLI 2.102 completed-job escape guard was reproduced and corrected with explicit captured reads, older-CLI compatibility and control stripping; raw failed evidence stays private. Actionlint 1.7.12 passes all workflows with only its known ubuntu-26.04 label-table lag excluded. Existing producer jobs actually use that runner successfully.

Full ready-runtime, resulting main publication/native and final documentation-only main acceptance remain pending. These development timings and scope checks do not replace them. No Core/module release or dedicated-instance update is performed for this policy.
