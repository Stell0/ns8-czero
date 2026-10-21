> Historical evidence. For current setup, see the [documentation index](index.md); for current acceptance, see [release readiness](release-readiness.md). The measurements and generation-specific instructions below are retained.

# M14 development-candidate readiness

This is a development deployment report, not approval of a stable NS8 release.
M00–M14 candidate implementation and acceptance pass under the recorded CPU-quota
and interactive Playwright waivers. Exact source 5be82b7 passes the installed,
live and source gates below. The main completion marker must additionally pass
its actual CI; workflow start is not a pass.

## Candidate and reproducibility

Source: `5be82b7a398af3229ee3222e3b5b456fdce92ddd`.
Core/application/schema: `0.24.2 / 0.39.0 / 0013_oauth_consent`.

| Image | Immutable digest |
| --- | --- |
| `ghcr.io/stell0/czero` | `sha256:b19f49cdd8d34814cac26606c7b0470335d4392ae20c2e6652fd0c75586fa34d` |
| `ghcr.io/stell0/czero-app` | `sha256:257bd88c438a2494d9966d87bbe0ee4a2b4e8da921a76786edfbf2464ac233d1` |
| `ghcr.io/stell0/czero-postgres` | `sha256:0618d0a78f7aab8aee15f9ad9edf507ceae5c7ffbd66aedbc308b6bd67f7d261` |

Anonymous registry retrieval verifies all three OCI revision labels against the
source above. The producer build explicitly uses local Core; independent forks
retain the immutable released-Core default and frozen lock.

## Acceptance evidence

| Requirement | Evidence and current result |
| --- | --- |
| Local unit/integration/packaging | [38697416074](https://github.com/Stell0/ns8-czero/actions/runs/38697416074): 675 actual Python/PostgreSQL/packaging cases; Go schemas and 19 non-UI Robot dry runs pass |
| Script regression | 86 actual JavaScript cases pass; local Python run independently passes 499 with 176 explicit database skips |
| Build, parser/runtime/license/security audits | [38697416040](https://github.com/Stell0/ns8-czero/actions/runs/38697416040): all jobs pass, including full reports/SBOMs and fixable-critical gate |
| Released default source | [38698337570](https://github.com/Stell0/ns8-czero/actions/runs/38698337570): immutable Git-source and assembled runtime/license checks pass |
| Installed lifecycle, isolated instances, database/vector, jobs, outage recovery, backup/restore, SSO, REST/MCP | [38697735920](https://github.com/Stell0/ns8-czero/actions/runs/38697735920): Debian install 16 pass/three expected skips; Rocky genuine M13 upgrade all 26 pass; exact recovery/observers and privacy pass |
| Native administration and all-role application browsers | Same exact QEMU run: all seven actual Rocky browser workflows pass; 19 safe numeric accessibility contexts pass |
| Performance and accessibility | Both installed latency/RSS probes and actual names/landmarks/keyboard browser smoke pass; no complete WCAG claim |
| Dedicated live update/restart/persistence | 5be82b7 targeted update and full native user-manager restart pass retained-grant SDK/REST parity, revocation, exact data/settings, seven HTTP pages/assets and timer health jobs; temporary clients disabled; canonical inventory normalization and a final full-manager restart also pass; all temporary clients disabled |
| CPU-rate quota | Explicitly deferred by operator, not passed; no quota or discovery helper ships |

The earlier [38688674854](https://github.com/Stell0/ns8-czero/actions/runs/38688674854)
Rocky update fails after replacing the working predecessor because its rootless
CPU controller is unavailable. Its two passes/23 failures are retained; cascading
failures do not establish independent UI defects. The candidate removes the new
CPU flag. Memory/swap/task and privilege assertions remain required. No host-wide
controller settings or unrelated applications are changed.

## Security findings

Full SARIF and CycloneDX reports are attached to publication run 38697416040 as
`trivy-ui`, `trivy-imageroot` and the three `trivy-ghcr-io-stell0-*` artifacts.
These are snapshots of the scanner database at build time, not permanent counts
or a vulnerability-free claim. Reports are uploaded before the rejecting gate.

| Scan target | Total | Critical | High | Medium | Low | Unknown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Application | 166 | 0 | 44 | 58 | 61 | 3 |
| Database | 413 | 3 | 63 | 172 | 170 | 5 |
| Native UI source/lock | 7 | 0 | 2 | 4 | 1 | 0 |
| Module and native actions | 0 | 0 | 0 | 0 | 0 | 0 |

Compatible UI patches reduce the earlier 29 findings to seven. Supported database
package updates and removal of root-only gosu reduce 526 to 413 without changing
PostgreSQL major or data layout. The remaining application/database high and
critical findings advertise no fixes in these scans. The UI findings require
major toolchain/framework transitions; forcing incompatible versions is not an
accepted remediation. The native UI still follows maintained NS8 Vue 2/CLI 4.

The three database critical reports require these distinctions:

- [SQLite CVE-2025-7458](https://security-tracker.debian.org/tracker/CVE-2025-7458)
  is still listed vulnerable for the included Bookworm package and requires
  attacker-selected SQLite SQL. C0 uses PostgreSQL with typed domain services,
  not a public SQLite/SQL execution interface. This is exposure context, not a
  proof that every bundled executable/library path is unreachable.
- [libxml2 CVE-2026-6653](https://security-tracker.debian.org/tracker/CVE-2026-6653)
  remains postponed in Bookworm. Its XML parser use-after-free is not removed by
  container privilege restrictions. Keep the finding open; C0's typed services
  and private database network do not constitute a complete reachability audit.
- [zlib CVE-2023-45853](https://security-tracker.debian.org/tracker/CVE-2023-45853)
  concerns contributed MiniZip code. Debian records that code as not built into
  the affected Bookworm zlib binary packages. Retain the raw scanner finding and
  this vendor assessment; no suppression or clean-scan claim is introduced.

PostCSS/selector-parser are used by the native UI build chain, while Vue 2 also
ships to browsers. Static application UI and ingestion services do not expose a
PostCSS compilation endpoint. This narrows context but does not waive dependency
maintenance or establish all attack paths absent. Keep remaining findings visible
before any stable release decision. Package-manager and license metadata remain
in images; developer tools/tests/repository skills remain outside runtime images.

## Remaining boundaries and release procedure

- Interactive Playwright remains waived; actual automated disposable browsers
  remain required. Dedicated live checks use the owner only and do not establish
  all-role live coverage. Destructive recovery/uninstall runs only in QEMU.
- Container CPU quotas are deferred. Memory/process protections and parser
  CPU/time/byte limits are separate controls and remain required.
- Real embedding/Jev/Kev quality/calibration, actual ChatGPT/scheduled-client
  interoperability, deployment-specific IdP/proxy support and production OAuth
  log-redaction policy remain operator/release work. Mock correctness and SDK
  protocol coverage do not establish those external outcomes.
- Core artifacts `core-v0.24.1` and `core-v0.24.2` are library releases, not NS8
  module versions. No stable module tag/release is published by this report.
- Current automatic NS8 release selection encounters the latest `core-v*`
  GitHub release and rejects it as a module semantic version. Prepare full initial
  module release notes and explicitly select an approved module version; never
  retag Core artifacts or create a dummy module version to pass a check.

See [PLAN.md](../PLAN.md) for complete milestone evidence and failed-run history,
[README.md](../README.md) for installation/API/operator contracts and
[AGENTS.md](../AGENTS.md) for implementation and handoff conventions.

## First installed measurements (7243347)

Both disposable runners report four logical CPUs and approximately 8 GiB RAM.
The restored fixture has five visible Wiki pages and seven seeded source versions.
Each HTTPS series has two warmups, followed by fifty health and twenty authenticated
provider-free Wiki text-search requests; exact revision citations are asserted.
These small warm-cache measurements do not establish large-corpus capacity.

| Runner | Health p95 | Wiki text search p95 | App summed RSS after restore | Database summed RSS after restore |
| --- | ---: | ---: | ---: | ---: |
| Debian 13 update | 13.057 ms | 21.920 ms | 126672 KiB | 97944 KiB |
| Rocky 9 install | 7.045 ms | 13.633 ms | 127592 KiB | 98992 KiB |

Targets are 500 ms/1000 ms p95 and 256/384 MiB summed RSS respectively. RSS
conservatively sums per-process resident pages and may count shared pages more
than once. Effective cgroups verify 1 GiB memory, a further 1 GiB swap allowance
and 256 tasks, with non-root UID, no-new-privileges and no effective capabilities.
CPU-rate quota is explicitly reported deferred. The browser failures are a
separate test-helper issue: the pinned adapter prefixes callback source with
return, and leading line comments trigger semicolon insertion. Parenthesizing
the callback retains its license and fixes the conversion; the actual corrected native
browser rerun now passes all seven workflows.

## Native image-reference compatibility

The tested NS8 cluster inventory splits IMAGE_URL at its final colon. A digest-only
reference executes the correct image but is displayed as module `czero@sha256`
with a hash-shaped version. Use the frozen candidate tag after verifying all
three manifest digests/source labels immediately before the supported update,
and check the installed digest and canonical module/source/version afterward.
Do not edit Core, Redis or unrelated module metadata to work around this. This
is an NS8 inventory parsing limitation; the agent image-name helper separately
supports digests. Source: Core `cluster.modules.list_installed`, distinct from
`agent.get_image_name_from_url`. A future semantic module release avoids mutable
branch tags; no such release is claimed here.

Corrected-source 5be82b7 Debian installation also passes sixteen tests with three
expected update-only skips. Its generated-password and complete OAuth-query
privacy checks pass across actual XML/text/journal artifacts. The same restored
fixture measures health/search p95 11.301/18.007 ms and summed app/database RSS
126332/99208 KiB, under every stated target. Corrected Rocky genuine upgrade passes all twenty-six cases with no skips, including
all seven browsers and nineteen safe numeric accessibility contexts. Health/search
p95 are 12.617/21.730 ms; summed app/database RSS are 126596/97992 KiB. Actual
XML/browser/journal privacy audits pass. The earlier five browser-harness failures
remain recorded and are superseded by executed successful workflows, not waived.

## Release tooling verification

Maintained gh-ns8 source `3a7f1ff2a1b2e4fc6c5396c539113a9fa1d68f49` builds
locally. Its actual read-only `module-release check --repo Stell0/ns8-czero`
uses `core-v0.24.2` as its comparison baseline and reports merged PR 1 plus the
M13 marker outside PRs while main is still bb28777. This does not review the full
initial module history or authorize the pending M14 branch. Source inspection of
`NextTestingRelease` confirms its strict semantic-version validation rejects the
Core tag prefix; no release-creation command is executed to demonstrate this.
The actual create help accepts positional VERSION, not the obsolete
`--release-name` flag still shown in part of its README.

For a future first module release, first approve an exact testing version and
verified target commit, review the complete initial release notes and current
check output, and attach the retained SBOMs. If using the general GitHub CLI to
supply complete notes, its verified flags are `--target`, `--prerelease` and
`--notes-file`. Do not run automatic version selection against a Core release,
use library-generated incremental notes as the entire initial product history,
or create a dummy tag to obtain a passing check. No tag, GitHub module release,
issue comment or release announcement is created as part of this deployment.
