# Development feedback, merge acceptance and deployment acceptance

[C0 validation](../.github/workflows/validate.yml) classifies the complete Git
diff, including deleted files, both sides of renames and file modes. C0 permits
agent review and automatic regular merges; a separate human approval is not
mandatory. Required checks, current-source validation and branch protection
remain mandatory. This policy supersedes the earlier policy requiring native tests for every ready
PR recorded in the historical evidence below.

## Development feedback

Every PR receives automatic fast checks. Reviewed Git-only documentation uses
the explicit `DOCS` allowlist: UTF-8, conflict markers, diff/local-link checks and
policy regressions. Runtime PRs prioritize speed: application/template, Core and tooling unit
cases, Node controllers, schemas, shell syntax and Robot dry runs. Fast jobs
start no PostgreSQL service, browser or extraction worker; real database,
HTTP/MCP, browser and packaging checks belong to full acceptance.
Changed native Vue assets also build with the frozen Yarn lock. The fast runner rejects an expanded or altered selection rather than silently
running the entire integration/packaging suite.

Review the complete diff and affected behavior before enabling auto-merge. This
review may be performed by the contributing agent; no human-review label or
approval count is required. Never assign an unsolicited reviewer. Draft PRs
receive checks but cannot pass the merge gate.

## Merge acceptance

The classifier's conservative presentation allowlist makes native acceptance
optional for modifications to `app/frontend/src/style.css` and native CSS/SCSS
assets, plus their browser/controller tests. Vue components contain executable
code and require native acceptance even when an edit appears presentational.
New/deleted/renamed presentation files and mode changes broaden validation.
Changed script/form/identity wiring, hidden guards and CSS resource imports
also require native acceptance, even inside an allowlisted presentation file.
Authentication/account/admin pages, application JavaScript, third-party assets,
installation/configuration/backup/restore, containers, migrations, Core,
dependencies/locks, CI/policy code and unknown paths require full native
acceptance automatically, including on draft PRs. Mixed diffs retain the highest
risk; renaming a sensitive file cannot hide its original path.

`fast` runtime merge acceptance requires the automatic fast job. `full` acceptance
requires that job **and** all Python/PostgreSQL/packaging cases, released-Core
compatibility, image/license/parser audits, five scan/SBOM pairs, immutable image
identity checks, Debian genuine-predecessor upgrade, Rocky installation and all
eight native browser/privacy workflows. The existing interactive-Playwright and
CPU-quota waivers are unchanged. Database skips do not establish a pass.

The always-scheduled **C0 merge gate** reclassifies the actual source/base/diff,
checks current PR head/base/readiness and requires every selected job to finish
successfully. Missing, skipped, cancelled, failed or started required jobs cannot
pass. Its version-2 proof records `native_required`, the classification reason,
selected mode and actual image/native verification. A fast proof explicitly
lacks native/image acceptance. Frozen version-1 full and documentation proofs
remain verifiable; legacy scoped feedback never becomes merge acceptance.

Before a direct merge, verify the exact current reviewed source:

```sh
python scripts/verify-promotion.py --source <full-head-sha> --pr <number>
```

This verifies actual completed jobs and the source-bound proof. Agent diff review
is not described as independent human review. Retain strict up-to-date branch
protection, the Actions-owned `C0 merge gate`, administrator enforcement and the
existing bans on force pushes/deletions. No merge queue or privileged
`pull_request_target` workflow is introduced.

## Main, manual runs and releases

After reviewing the exact head, enable GitHub native auto-merge for a ready PR:

```sh
gh pr merge <number> --auto --merge --match-head-commit <full-head-sha>
```

The repository enables auto-merge and regular merge commits. GitHub waits for
required checks and an up-to-date branch; do not use an admin bypass. Review a
changed head/base again and retain frozen candidates when a new rebased candidate
is needed. Do not squash or rewrite accepted commits. No general-purpose bot
merges arbitrary unreviewed PRs or executes fork code with privileged events.
See [GitHub auto-merge](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/automatically-merging-a-pull-request)
and the [CLI head guard](https://cli.github.com/manual/gh_pr_merge).

Main uses the same risk classification. Request full Debian/Rocky acceptance for
any exact source, including a reviewed low-risk UI change, with `validate.yml`:

```sh
gh workflow run validate.yml --ref <exact-branch-or-tag> -f pr_number=<number>
```

Omit `pr_number` for a main/tag source. Manual dispatch always selects `full`;
module release tags also force `full`, regardless of the diff. There is no switch
that disables native acceptance for a sensitive change. Existing full/native
runs, including the frozen Nebula acceptance, are never cancelled or replaced.
Only proven obsolete legacy development/documentation feedback may be retired;
fast jobs participating in full acceptance have no cancelling concurrency group.

Canonical `main`/`latest` publication still requires full exact-source native
acceptance and promotes immutable candidates without rebuilding. A UI-only fast
merge does not publish new canonical aliases until a full on-demand run passes.
Core/module releases retain their full proof, immutable source/artifact and
consumer gates. Registry-dependent native checks need an authorized repository
branch; never copy privileged credentials into fork secrets. Both internal and
external contributions follow this risk policy, with no blanket native mandate
for Git-only documents or allowlisted presentation changes.

## Deployment and milestones

Merge eligibility is not production/deployment acceptance. Core/module release
publication and production deployment require the actual full proof:

```sh
python scripts/verify-promotion.py --source <exact-source-sha> --full
```

Fast or documentation-only proof is rejected by `--full`. Preserve actual image,
source, native/privacy/scan evidence and required live authorization. Dedicated
updates still require supported C0-only backup/integrity, frozen genuine
predecessor identities, readiness, data/OAuth/settings/files/jobs/schedules and
unrelated-module preservation, live client workflows, restart and bounded
positive-control root journald privacy checks. Destructive recovery stays
disposable. A Git-only closeout does not replace runtime evidence or an installed
baseline. Keep failed evidence outside Git and public identities sanitized.

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

Full acceptance installs the pinned `tests/e2e/requirements.txt` browser and
runs the real headless Chromium suite against a disposable app/database/worker.
Fast feedback omits these realistic fixtures to prioritize development speed.
A missing backend, browser or required dependency fails the job. The existing
interactive Playwright waiver does not exempt this automated suite. Existing
QEMU/Robot workflows, privacy audits and resource-policy waivers remain intact.
Only sanitized failure action/DOM traces and synthetic screenshots are retained;
network events/resources and private credential files are excluded.
