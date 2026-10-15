# Original C0 fork-upgrade fixture

This example is repository development material, never runtime image content.
It demonstrates a standalone Core consumer plus explicit managed-file updates.
Core 0.24.1 publication is under M13 verification; do not treat this example as
released until PLAN.md records the actual public artifacts and consumer tests.

Create an isolated example checkout with:

```sh
python examples/fork/create.py /tmp/c0-example
cd /tmp/c0-example
uv sync --frozen
uv run --frozen python -m unittest discover -s tests
```

The generator copies only registered infrastructure files and this original
consumer, not the reference application's data or private local fixtures.
The upstream manifest retains immutable Git identities. Set your repository's
normal default branch before enabling the scheduled upstream workflow. Its
trusted source is `Stell0/ns8-czero`; the initial M13 baseline must be available
there. The workflow's revision input accepts only full immutable source SHAs.

Customize an example managed file, then preview/apply the next upstream revision
using `scripts/sync-upstream.py` and a separate trusted checkout. Review
`.c0/UPSTREAM_UPDATE.md`; untouched files update while customized files stay
intact with `needs_review`. Port relevant upstream behavior, test it, clear only
resolved flags and retain migration notes. Register additional managed paths
explicitly; upstream files are never automatically added to the managed scope.

Core uses a compatible minor range plus a Git tag/subdirectory pin and uv.lock.
Renovate's native pep621 manager updates Git tags and regenerates that lock.
Core updates are reviewed, never automatically merged. Breaking/minor upgrades
require compatibility and migration review. A Git tag source is intentional:
Renovate's native uv processor currently skips direct wheel URL sources.

The copied NS8 build files are examples for review, not a configured new module.
Before publishing an actual application fork, choose its independent module and
component image names, registry permissions and native identity consistently;
do not publish the template's `czero:main` tag from a second repository.
For the full NS8 application template, fork the repository itself, retain its
native tests, and use the installed NethServer skills plus the four C0 skills.

GitHub prevents GITHUB_TOKEN-generated PRs from recursively triggering CI.
Dispatch Local checks and Publish images explicitly on a real module's proposal
branch (publication triggers QEMU), or use an approved GitHub App. The minimal
standalone consumer has its own focused checks. A started workflow is not a pass.

For reusable contributions, isolate only Core/infrastructure improvements in a
clean worktree based on upstream's current default branch. Keep application
branding, custom schemas, deployment data and unfinished drafts in the fork.
Use `c0-contribute-upstream` and the installed NethServer commit/PR skills.

Native Actions tokens cannot push workflow-file changes. Those files are
preserved with `review_reason=workflow-permission` and exact migration ranges.
A maintainer with an appropriate publishing credential may explicitly use
`--allow-workflow-updates`; review customizations before enabling that option.
Resolve all three review markers only after testing the manual migration.
