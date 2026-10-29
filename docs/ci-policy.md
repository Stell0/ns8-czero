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
Use the accepted runtime source from the publication proof for deployment checks;
a documentation-only main HEAD may have no image or full-acceptance proof of its own.

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

## Executed evidence and limits

The policy is merged through [PR 14](https://github.com/Stell0/ns8-czero/pull/14)
and [PR 18](https://github.com/Stell0/ns8-czero/pull/18). Exact `740fd64` [full PR
39152442602](https://github.com/Stell0/ns8-czero/actions/runs/39152442602) and resulting
`31ca102` [automatic main 39155318390](https://github.com/Stell0/ns8-czero/actions/runs/39155318390)
pass 1284 Python/PostgreSQL/packaging cases, 125 controllers, 21 Robot checks,
schema/shell, producer/released-Core, runtime/license/parser audits and five actual
scan/SBOM pairs. Actual native reports pass Debian's genuine AM4 upgrade (21) and
Rocky installation (26/three expected skips/all eight browsers), both SSO probes
per distribution, update/encrypted clean restore, eight privacy guards, 25 numeric
accessibility contexts and three query-audited artifacts with zero candidates.
Actual checkouts, installed digests and module sibling references match candidates.
Main's canonical publication job actually succeeds; six fresh registry reads match
all main/latest aliases. Exact accepted source/digests are in PLAN.md. The measured
full main/publication span is 2305s (38m25s); full acceptance cost is retained.

| Measured observation | Earlier policy | Scoped policy |
| --- | --- | --- |
| Local/UI feedback | 466s plus a duplicate 462s | 110s: 63 PostgreSQL and 125 controller cases |
| Docs PR acceptance | 2386s across local/publication/native | 28s: light docs and 44 policy cases |

These are inspected single samples, not estimates or a general performance SLA.
Baseline e05ed46 [local push 39136439156](https://github.com/Stell0/ns8-czero/actions/runs/39136439156),
[duplicate PR 39136456995](https://github.com/Stell0/ns8-czero/actions/runs/39136456995),
[publication 39136439125](https://github.com/Stell0/ns8-czero/actions/runs/39136439125)
(131s), and [native 39136605761](https://github.com/Stell0/ns8-czero/actions/runs/39136605761)
(2250s) have actual source checkouts verified, including workflow_run's different
context SHA. Controlled closed/unmerged [docs PR 15](https://github.com/Stell0/ns8-czero/pull/15)
([39141211821](https://github.com/Stell0/ns8-czero/actions/runs/39141211821),source `40358fa`)
and [UI PR 16](https://github.com/Stell0/ns8-czero/pull/16)
([39141216790](https://github.com/Stell0/ns8-czero/actions/runs/39141216790),source `a049eba`)
verify jobs/classification/proofs. Observed UI feedback is 76.4% lower and docs
acceptance 98.8% lower. Runtime/native acceptance is still required.

The docs gate passes with images/packaging/QEMU skipped. UI feedback passes but
its runtime gate fails. Ready same-head broad feedback[39142577702](https://github.com/Stell0/ns8-czero/actions/runs/39142577702)
passes 1256 cases but rejects full_validation_required. The actual promotion helper
accepts ready docs and rejects both probes for full deployment/release. Closed
unmerged [PR 17](https://github.com/Stell0/ns8-czero/pull/17) actually cancels obsolete
UI feedback 39145190485 on a docs transition. Superseded development runs cancel;
full or ambiguous runs are preserved. Actual ready/subsequent-update events run full.

Initial regressions fail before implementation. Current policy/release/native-helper
checks pass 98, all 339 unit cases. Actionlint 1.7.12 passes with only its stale
ubuntu-26.04 label table excluded; actual builds on that runner pass. Current/older
GitHub CLI completed-log capture is exercised, with captured terminal controls
stripped. The new installed-image probe initially fails in the non-browser Robot
container without Git; five failing regressions precede explicit immutable workflow
source binding. Both actual distributions now pass. Raw failed evidence remains
outside Git; no tools are added to runtime to bypass the failure.

First main `56e384f` [39148427261](https://github.com/Stell0/ns8-czero/actions/runs/39148427261)
hits one pre-existing forced-HNSW-plan SQL timeout (1271 passes). Native/artifact
checks pass, but the gate rejects required_job_not_successful and publication is
skipped. Same-source manual [full 39149274270](https://github.com/Stell0/ns8-czero/actions/runs/39149274270)
passes 1272/native/audits, but publication is unexpectedly skipped through development
ancestors. This [runner dependency behavior](https://github.com/actions/runner/issues/2205)
is corrected by explicit status/gate checks; twelve actual-expression cases cover
skips, cancellation, failed gates, modes and refs. Canonical reads remain c1a90d3
until corrected `31ca102` full acceptance and publication actually succeed.

The forced-plan fixture is timing-sensitive in retained post-suite diagnostic data;
its cause is unproved. Fresh full runs pass. Runtime SQL, the five-second deadline,
versions, dependencies and schema are unchanged; no automatic retry or acceptance
exception is introduced. Main protection is actually configured/re-read: required
C0 merge gate, Actions app 15368, strict up-to-date base, admin enforcement, zero
required human approvals and no force pushes/deletions. No former rule is replaced;
no merge queue exists. Primary-agent review is not independent human review.

The final docs-only closeout must pass its own lightweight PR/main gate and preserve
31ca102 canonical images. Its actual checked sources, jobs and timings are recorded
in that PR after execution, avoiding a recursive documentation-marker full build.
No Core/module release, dedicated-instance update, other live persona, real-provider
quality or scheduled-client interoperability is claimed. Existing waivers remain.

## Automated full-document browser gate

Runtime local/full and scoped feedback also install the pinned
`tests/e2e/requirements.txt` browser and run all six headless Chromium
full-document cases against a genuine disposable app/database/standalone worker.
A missing backend, browser or required dependency fails the job. The existing
interactive Playwright waiver does not exempt this automated suite. Existing
QEMU/Robot workflows, privacy audits and resource-policy waivers remain intact.
Only sanitized failure action/DOM traces and synthetic screenshots are retained;
network events/resources and private credential files are excluded.
