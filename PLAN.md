# C0 implementation plan — milestone-by-milestone Codex handoff

**State:** M00 is complete. M01 is complete: runtime, packaging, upgrades and documentation closeout pass local CI, publication/audit/scans and both QEMU legs. M02 runtime, packaging and native/browser tests pass; documentation closeout is active. The dedicated live instance runs M01; further interactive Playwright and live checks are temporarily waived by the operator.

This plan is intended to be **executed iteratively**: inspect, refine the current milestone, implement, test, commit/push, verify CI, perform applicable live and Playwright MCP checks, update docs, and only then advance. Never implement several milestones blindly before reviewing the prior milestone's results.

## Product contract (do not quietly change)

- C0 = AI-native, forkable NethServer 8 web application, using NS8's native module framework and readable **numbered action scripts**. Don't replace lifecycle actions with a monolithic Python NS8 management library.
- Runtime: Python/FastAPI, user Web UI, REST/OpenAPI, remote MCP, NS8-idp authentication, one PostgreSQL **instance per C0 installation**, pgvector, generic structured-object storage and an LLM Wiki with relational graph connections.
- Single shared knowledge space per installation. Personal-owner default; optional Reader/Editor/Admin application-wide roles. No per-document ACLs, UGO, policy engine or multi-tenancy.
- No embedded generative LLM, local model server, autonomous AI maintenance or AI scheduling. External agents do reasoning/wiki updates. C0 may optionally call an external embedding API and a System One scorer (**Jev or Kev**) for retrieval; graceful full-text and standard-ranking fallbacks.
- Deterministic ingestion, chunking, jobs, trusted scheduled tasks, and native NS8 backup/restore. Keep extracted text even when deleting binary originals after successful extraction.
- Installed application exposes `/agents` and native MCP discovery. `AGENTS.md`/skills/build/CI/tests are Git/repository-only, never bundled into the runtime.
- An external developer forks C0 to build an application. Generally useful enhancements flow upstream by a focused, tested PR. Versioned C0 Core should be upgraded automatically where possible, with Codex used for conflicts.
- Favor reuse from NS8. Respect GPL/license headers, secret handling and existing module interfaces.

## Source precedence and selection

1. Current checked-in behavior and the deployed NS8 version.
2. [NS8 official module contracts](https://github.com/NethServer/ns8-core/tree/main/docs/modules) and [NethServer/agents module skill](https://github.com/NethServer/agents/tree/main/skills/nethserver-ns8-module).
3. Current, maintained, tested examples referenced in each milestone: [ns8-kickstart](https://github.com/NethServer/ns8-kickstart), [ns8-hermes-agent](https://github.com/NethServer/ns8-hermes-agent), [ns8-dependencytrack](https://github.com/NethServer/ns8-dependencytrack), [ns8-idp](https://github.com/NethServer/ns8-idp), [ns8-mail](https://github.com/NethServer/ns8-mail), [ns8-github-actions](https://github.com/NethServer/ns8-github-actions).
4. Official upstream project reference for features NS8 modules do not supply.

**When no code link is listed for a C0-specific feature:** search maintained NethServer/Nethesis repos first, starting with filenames, actions, services and REST schema names matching the operation. Review at least two patterns when available, compare freshness, test coverage, security and lifecycle, choose the current better implementation and note the finding in the milestone subplan. If nothing reusable exists, implement the smallest component and record why. Do not copy older hard-coded secrets or image tags.

## Non-negotiable execution loop for EVERY milestone

1. **Inspect and plan.** Read `AGENTS.md` and `README.md`, the pending milestone, previous evidence, local git status and relevant upstream sources. Expand only the active milestone's `Work plan` with implementation steps, specific files and tests. Record changed assumptions. Maintain a short task checklist in that milestone rather than opening a separate planning document.
2. **Build early.** From **M00**, configure actual image publication in GitHub Actions. For each meaningful slice: make a focused commit, push it, inspect the image-build workflow and the ensuing QEMU/Robot test workflow. Fix and repush until green. Check both source/build failures and installed-service behavior. Never claim CI green without a completed successful run.
3. **Test in layers.** Unit/type/lint locally; service integration against isolated PostgreSQL; NS8 install/configure/update/backup/restore in QEMU where applicable. Once bootable and CI green, test on an explicitly authorized live NS8 node provided at runtime. Use **Playwright MCP** for interactive NS8 admin UI and C0 user UI (including auth, settings, errors and persistence); maintain automated Robot/browser coverage too. A browser screenshot alone is not a passing behavioral test.
4. **Protect live systems.** Use only the dedicated C0 instance, test accounts and designated C0 hostname supplied in the execution prompt. Never modify unrelated modules, reset system passwords, publish secrets, delete a module with useful data, or run destructive installation/restore tests on a shared live node. Use disposable QEMU for destructive scenarios. A missing SSH/MCP/browser capability is a blocker to record, not a license to invent results.
5. **Document each milestone.** Update `AGENTS.md` with discoveries/developer rules, `README.md` with actual human-visible behavior, configuration and known limitations, and this `PLAN.md` with status and evidence. Keep documentation concise; move sprawling details to reference files if necessary. Commit and push the docs changes, and observe the triggered CI.
6. **Exit gate.** Mark `[x]` only after all milestone-specific acceptance tests pass and `Evidence` includes commit SHA(s), relevant CI run URL(s), test commands/results and live/Playwright result if applicable. If blocked, keep `[ ]`, write the exact blocker, and stop instead of silently skipping.

**Evidence template for every milestone:** `Evidence: pending. Work plan: pending. Tests: pending. CI: pending. Live/UI: pending or not applicable (explain). Docs: pending.`

**Operator testing exception (13 October 2026):** The operator requested “skip playwright tests for now” and to proceed without live testing. Suspend interactive Playwright MCP and all live-environment tests from this point, including subsequent milestones, until the operator reinstates them. Retain local tests, image publication, GitHub Actions and automated QEMU/Robot browser coverage. Record affected live/UI gates as **waived by operator**, not passed; do not silently remove them from milestone evidence.

### Tests and CI conventions

- Preserve the existing `.github/workflows/publish-images.yml` / `test-module.yml` structure where sound; use [publish-branch.yml](https://github.com/NethServer/ns8-github-actions/blob/v1/.github/workflows/publish-branch.yml), [test-module-qemu.yml](https://github.com/NethServer/ns8-github-actions/blob/v1/.github/workflows/test-module-qemu.yml), [test-module runner](https://github.com/NethServer/ns8-github-actions/blob/v1/scripts/test-module.sh) and [Trivy scanning](https://github.com/NethServer/ns8-github-actions/blob/v1/.github/workflows/scan-with-trivy.yml). Inspect `workflow_run` permissions, GHCR image visibility, fork Actions settings and the proper output image tag.
- QEMU Robot suites must verify **install and update**, not merely parse Robot tests. For browser coverage use Robot Browser/Playwright in CI and use [Playwright MCP](https://github.com/microsoft/playwright-mcp) interactively when an operator-supplied live test host is available.
- Stop using the template's sample `kickstart` credentials in `tests/kickstart.robot` in M00. Do not commit operator-supplied live credentials, hostnames, OAuth tokens, browser auth state or private URLs. Runtime config and test secrets are injected safely.
- NS8 operations use `imageroot/actions/<action>/<NN>step`, JSON input/output validation, `agent` SDK, systemd user services, private secrets files, Traefik and volumes. Application business logic can live in a versioned Python library; **module lifecycle logic must not** become a single giant library.
- If a requirement is blocked by a missing facility, add a clear, testable follow-up to this milestone; do not silently weaken acceptance criteria.

## Milestones

### M00 — Rebrand kickstart, create working CI and smoke-test the module [x]

**Goal:** On the first implementation push, build an actual `czero` module image from this repository and get an honest install/configure/uninstall smoke test. The baseline may still be a simple HTTP stub, but must no longer pretend to be implemented C0.

**Copy/adapt from:** [ns8-kickstart/build-images.sh](https://github.com/NethServer/ns8-kickstart/blob/main/build-images.sh); [kickstart CI publish](https://github.com/NethServer/ns8-kickstart/blob/main/.github/workflows/publish-images.yml); [kickstart QEMU test](https://github.com/NethServer/ns8-kickstart/blob/main/.github/workflows/test-module.yml); [kickstart Robot](https://github.com/NethServer/ns8-kickstart/blob/main/tests/kickstart.robot); [ns8-github-actions](https://github.com/NethServer/ns8-github-actions/blob/v1/README.md); [module developer skill](https://github.com/NethServer/agents/tree/main/skills/nethserver-ns8-module).

**Implement:** Rename `kickstart` across scripts, unit files, tests, UI, metadata, image labels and workflows. Use a verified image name/tag and pinned runtime images; make the registry owned by this repo, not `ghcr.io/nethserver/kickstart`. Remove placeholder README behavior and hard-coded Robot passwords; pass test credentials safely. Ensure publish + QEMU/Robot workflows really run on appropriate pushes; fix Actions permissions/trigger order. Add a basic health smoke and clear module identity. Preserve GPL/attribution.

**Acceptance:** A pushed commit yields a **published czero image**, successful CI build and QEMU install/configure/uninstall with correct name; no leftover kickstart functionality falsely represented as C0; no credentials committed. No use of the shared live host for destructive tests.

**Documentation gate:** Correct agent source/layout/CI instructions in `AGENTS.md`; update `README.md` with achieved install and honest limitations; record image tag/commit/build/test URLs in `PLAN.md`.

**Work plan (active, 12 October 2026):**

- [x] Rename module/image/unit/metadata to `czero`; pin the honest HTTP stub, remove SMTP discovery and fake settings, and use an instance-owned `/czero/<module-id>/` route.
- [x] Build/publish from M00 with explicit checkout/package permissions; inspect image metadata and retain Trivy/SBOM artifacts. Gate automatic QEMU on completed successful publication.
- [x] Add and run local contracts and Robot install/configure/reconfigure/rejection/restart/update/uninstall checks. Create random disposable browser administrators; assert Settings Save restores a stopped Czero service.
- [x] Verify anonymous image access and run Playwright MCP/live installation, settings, status, errors, restart, HTTP and refresh checks on only the dedicated Czero module.
- [x] Restore native-token publication after the package Actions Write grant; inspect scans, image metadata/archive, final-documentation commit CI and both QEMU reports; update and test only the dedicated live Czero instance; reconcile all three documents.

**Source findings and implementation:** Inspected current kickstart build/actions, Hermes component packaging, Core agent/route/lifecycle contracts and `ns8-github-actions@v1` publisher, metadata, QEMU and Robot runner. Core supplies image environment and cleanup. The upstream publisher's packages-only permission block stripped private checkout access; adapt its small build/push job locally with `contents: read` and `packages: write`. The upstream metadata job masks pull errors; use authenticated inspection that fails on errors. Keep native reusable QEMU. Docker Hub tags `jmalloc/echo-server:v0.3.7` and `node:24.21.0-slim` were verified. Installed NethServer module/container/commit skills are active. Runtime packaging explicitly allows only `imageroot/` and generated `ui/dist/`; archive inspection found 99 entries and no development files.

**Failure fixes:** Publication checkout failed in [38233736825](https://github.com/Stell0/ns8-czero/actions/runs/38233736825); `a1692f5` fixed permissions. Optional SARIF ingestion failed because code scanning was unavailable; `9cb2aca` retains scan/SBOM artifacts without requiring that integration. Initial QEMU legs stopped at private GHCR pulls before VM boot; the operator made the package public. After a temporary GitHub outage, the same repository URL recovered, but the package reported no linked repository. Core `add-module` prints a Python dictionary, while `api-cli` prints JSON; [38248325628](https://github.com/Stell0/ns8-czero/actions/runs/38248325628) exposed the parser mismatch, fixed by safe literal/JSON parsing in `2902f57`. [38249852618](https://github.com/Stell0/ns8-czero/actions/runs/38249852618) exposed Browser enum conversion when invoked directly from Python; `6e8b290` dispatches through Robot. [38251632977](https://github.com/Stell0/ns8-czero/actions/runs/38251632977) exposed an exact paragraph selector; `e495790` uses a substring and verifies Save through actual service recovery. No failing acceptance assertion was removed.

**Verified CI/QEMU evidence:** Implementation commits `6124dca`, `a1692f5`, `9cb2aca`, `1652305`, `2902f57`, `6e8b290`, `e495790b45a5a18c660c79749b62f1e9726bfecd`. Earlier publication/scans run `38246945351`, recorded successful before the outage but now returning HTTP 404, produced `ghcr.io/stell0/czero:main` and `:latest`, digest `sha256:6b8da019245df3a374de7c0668fbe6cbca6213838f1a3eb9cd3a3411885af03c`; anonymous pulls still resolve that digest. The inaccessible historical run is not sufficient to close current CI acceptance. `imageroot/` and `ui/` are unchanged from that published baseline through `e495790`. [Local CI 38254300775](https://github.com/Stell0/ns8-czero/actions/runs/38254300775) passes. [Manual QEMU 38254302726](https://github.com/Stell0/ns8-czero/actions/runs/38254302726) completed successfully using that published image and the corrected tests: Debian 13/update has six passing lifecycle tests; Rocky 9/install has six passing tests including full browser behavior and one intentional update-scenario skip. Both test suites removed only the disposable module. XML reports were downloaded and inspected. This manual run proves installed behavior; the automatic run after failed publication was skipped and supplies no acceptance evidence. M00 forces a native update of the same image because no older released predecessor exists; M04 must test genuine migration.

**Local/scan evidence:** Eleven pytest tests pass; six non-UI Robot dry-run cases parse/pass, shell/action-schema/workflow checks and immutable Yarn production build pass. Inherited peer and bundle-size warnings remain. Four SARIF and four CycloneDX artifacts were inspected: module/imageroot have zero reported findings; UI dependencies have 29 and the temporary echo runtime has 95. Scan execution passed; those findings are not resolved. Replace the stub in M01 and review inherited UI dependencies before release. Git SSH is unavailable because of system SSH configuration permissions; use existing authenticated HTTPS without changing Git configuration.

**Live/Playwright evidence (12 October 2026):** The operator resolved administration certificate trust; normal-validation Playwright login succeeds. Earlier certificate-exception requests were rejected and were not bypassed. Advertised read-only facts report Core `3.21.0`, Rocky `9.8` and cluster leader. Native inventory initially contained no Czero. Installed only dedicated Czero using the verified digest through the authenticated native cluster task API; Playwright exercised its Settings Save twice, refresh/persistence, Status (`active enabled`), and the HTTPS smoke page (200 and expected echoed path). Native `get-configuration` returns `{}`; unknown settings return validation exit 10 while HTTP stays healthy; targeted native restart returns zero and service/route recover. Installing by digest exposed Core's `list_installed` colon-split display quirk; a forced native update of only Czero to `:latest` (the identical verified digest) restored correct `czero` source/module identity. Final inventory comparison, normalizing unordered flags, confirms all unrelated instances/versions/digests unchanged. The dedicated module remains installed and healthy. System logs UI returned no Czero entries, so live log visibility is unverified. No live destructive test, SSH access, certificate exception, or unrelated module change was used. Private access details and browser artifacts remain outside Git. This is echo-stub acceptance; application login, normal-user roles, REST, storage and MCP remain unimplemented.

**Publisher diagnosis and repair:** After the temporary GitHub outage, native publication built successfully but failed with `permission_denied: write_package`. Public read access did not grant Actions Write. The operator-created `NS8_MODULE_RELEASES_TOKEN` was tried in `d1ee855`; GHCR rejected its scopes, and `8e900b1` confirmed a fine-grained PAT without revealing its value. Current Hermes uses `github.token` for images and that named secret only for GitHub releases; both modules correctly strip the `ns8-` repository prefix. No package rename was needed. `dcaaf8974ddee410fa3a15b35f933783aa4f12fa` restored native `GITHUB_TOKEN` publication and removed PAT diagnostics. [Publish 38355381704](https://github.com/Stell0/ns8-czero/actions/runs/38355381704) still failed until the operator repaired package Settings -> Manage Actions access -> `Stell0/ns8-czero` -> Write. No secret value was retrieved, changed or committed. The release secret remains untouched and unused by image publication. A private repository needs `contents: read`; private container packages additionally need authenticated QEMU/guest pulls, which the current upstream runner does not supply. The current package is public.

**Package grant recovery (13 October 2026):** The operator added `Stell0/ns8-czero` to package Actions access with Write. Retrying [publication 38355628389](https://github.com/Stell0/ns8-czero/actions/runs/38355628389) at `7ff5516f0663568aad4a898e2872e5531d18689c` now succeeds completely: build, native-token push, authenticated metadata and all four Trivy/SBOM jobs. Published `:main`/`:latest` digest `sha256:63d0fd7c934f7bdf8b170bb1bba04de11a4b80ddca6c8ca0ff80205002b62981`; anonymous resolution and OCI source/revision/license/title labels were inspected. Archive audit again finds 99 entries entirely under `imageroot/` and `ui/`, with no forbidden development paths. Four inspected SARIF reports still contain 29 UI and 95 echo-runtime findings, zero module/imageroot findings, and four CycloneDX SBOMs. [Automatic QEMU 38355927140](https://github.com/Stell0/ns8-czero/actions/runs/38355927140) completed successfully. Downloaded XML reports confirm Debian 13/install: six lifecycle passes and the intentional update-only skip; Rocky 9/update: all seven tests pass, including browser service recovery. [Local CI 38355628449](https://github.com/Stell0/ns8-czero/actions/runs/38355628449) passes. Native live update of only Czero to this digest exits zero. Playwright MCP confirms Settings Save/refresh, active/enabled Status, About identity and HTTPS 200 with expected body. Configuration remains `{}`; unknown settings exit 10 without disrupting HTTP; targeted restart exits zero and HTTP recovers. Before/after inventory comparison confirms all unrelated instances unchanged. Normal TLS validation remains enabled.

**Evidence:** Implementation/recovery commits `dcaaf8974ddee410fa3a15b35f933783aa4f12fa`, `7ff5516f0663568aad4a898e2872e5531d18689c`; M00 closeout docs `dd26e4af403f3305c64db5e3659c8d9423560e1e`. Published `:main`/`:latest` image for `dd26e4a` resolves to `sha256:9f01b2c5c15c1d82976d2ceada955e1b1df82eafcdc9386d31508472b134f00e`. [Publish/scans 38359773901](https://github.com/Stell0/ns8-czero/actions/runs/38359773901), [local checks 38359773965](https://github.com/Stell0/ns8-czero/actions/runs/38359773965), and final [QEMU 38359921126](https://github.com/Stell0/ns8-czero/actions/runs/38359921126) pass. Downloaded Robot XML confirms Debian 13/update has six passes; Rocky 9/install has six passes and the expected update-only skip, with admin/browser smoke and disposable uninstall included. The prior current-runtime digest `sha256:63d0fd7c934f7bdf8b170bb1bba04de11a4b80ddca6c8ca0ff80205002b62981` was installed and tested live; final source-only metadata revision changes do not alter runtime behavior. Current live native update/status/config/error/restart/HTTPS/browser checks pass and unrelated inventory is unchanged. Eleven local pytest tests pass; archive inspection confirms runtime allowlist. Four SARIF/SBOM pairs were inspected: zero findings for module/imageroot, 29 UI and 95 echo dependency findings. No release or C0 REST/MCP capability exists. Live log visibility and reported dependency vulnerabilities remain documented limitations.

### M01 — Minimal Python runtime, Web UI and Core/application separation [x]

**Goal:** Replace the echo sample with an actual installable HTTP application and established package boundaries.

**Copy/adapt from:** [ns8-hermes-agent/build-images.sh](https://github.com/NethServer/ns8-hermes-agent/blob/main/build-images.sh) (component images); [ns8-kickstart/systemd service](https://github.com/NethServer/ns8-kickstart/blob/main/imageroot/systemd/user/kickstart.service); [ns8-dependencytrack/systemd components](https://github.com/NethServer/ns8-dependencytrack/tree/main/imageroot/systemd/user); [nethserver-containerfile skill](https://github.com/NethServer/agents/tree/main/skills/nethserver-containerfile).

**Work plan (active, 13 October 2026):**

- [x] Add `packages/czero-core` as a small independently versioned Python distribution; keep FastAPI transport and C0-specific page/route composition in a separate `app` package. Do not add generic storage abstractions before their later milestones.
- [x] Build a pinned Python runtime component image, with locked runtime dependencies and explicit copies of only the Core and app runtime files. Replace the echo dependency in module metadata/service configuration while preserving short NS8 numbered actions and the separate compiled NS8 admin UI. Keep credentials, tests, CI and developer docs out of the runtime image.
- [x] Serve a minimal static end-user landing page, honest `/agents` introduction, OpenAPI and `GET /api/v1/health` beneath the existing instance route. Resolve and test the dynamic `/czero/<module-id>` prefix end-to-end; preserve HTTPS and instance isolation. Do not claim authentication before M05.
- [x] Add focused pytest coverage for Core/app package separation, mounted path behavior, JSON health contract, OpenAPI, agents page and failure responses. Extend Robot/QEMU to assert the public app page and endpoints, access/request logging, restart and forced update. Add a repeatable UI/API browser check.
- [x] Reconcile the instance ID during update from M00 and restart an already-running application through native update hooks. Unit-test the non-secret identity write; QEMU clears the prior identity as an upgrade fixture and asserts container replacement and healthy routes after native update. Validate the real M00-to-M01 transition on the dedicated live instance.
- [x] Validate package/image naming, source references and path behavior; run local tests/build/archive audits and verify publication/scans plus both QEMU legs. The dedicated live M00-to-M01 transition and partial Playwright checks passed before the remaining live checks were explicitly waived.
- [x] Commit the reconciled AGENTS/README/PLAN closeout and verify its resulting CI before marking M01 complete.

**Source findings:** Current kickstart confirms Core-provided dependency-image environment variables, rootless loopback service, allocated port and numbered action conventions. Hermes demonstrates separate component images via `buildah build`, a module dependency label and a systemd component unit; its large upstream application image/dependency choices are not suitable for C0. The official FastAPI Docker and proxy guidance supports a single ASGI process behind the existing Traefik route; test the actual NS8 preserved-prefix behavior rather than assume a proxy strips it. Pin the supported Python base and every runtime dependency after checking current upstream versions. Keep app UI static and independent from the NS8 Vue 2 admin UI.

**Upgrade review finding:** The [Core update contract](https://github.com/NethServer/ns8-core/blob/main/docs/modules/updates.md) reloads units/environment and delegates restart to module hooks. The maintained [idp restart hook](https://github.com/NethServer/ns8-idp/blob/main/imageroot/update-module.d/80restart) uses `try-restart` to preserve an unconfigured module's stopped state. M00 lacks `CZERO_MODULE_ID`, and same-image tests did not prove the running echo container was replaced. Add only focused ID and restart hooks, not a lifecycle manager.


**Implement:** Minimal FastAPI runtime with `GET /api/v1/health`, OpenAPI, initial browser `/` page and honest `/agents` introductory page. Create clearly separated, versioned/releasable Python C0 Core package, application-specific extension module, and repository-only development files; use a pinned, minimal Python container and a user Web UI bundle. NS8 action scripts stay separate from FastAPI. Build all required images in CI.

**Acceptance:** Install image, start systemd units, access browser and REST health through NS8 path/route, verify request logs and restart behavior, run pytest and QEMU smoke; no development files in runtime images. Playwright MCP browser health/UI check when feasible.

**Documentation gate:** Record package/app boundaries in `AGENTS.md`; actual endpoints/UI and install caveats in `README.md`; tests and evidence in `PLAN.md`.

**Implementation and failure fixes:** `47933493d177cef198d07fe54b7cbafa54ac2178` adds independent `czero-core`/`czero-app` version 0.1.0, the FastAPI path-mounted application, static landing/agents pages, pinned Python component and locked non-editable packages. [QEMU 38362582273](https://github.com/Stell0/ns8-czero/actions/runs/38362582273) exposed virtualenv console-script shebangs pointing to the builder path after relocation. `59e0929be17c98f25dd74d12f93a847bcc82e86b` keeps `/opt/czero/.venv` identical in both stages. [QEMU 38364268844](https://github.com/Stell0/ns8-czero/actions/runs/38364268844) then passed application behavior but failed the log assertion, which incorrectly queried container `czero.service`; systemd `%N` names it `czero`. `8836be53994c23289165437883f239cdaece820d` corrects that query without removing the assertion. Final SBOM review found base-image pip and vendored setuptools; `4976d7fbd9a0438f3e32d5a2504acc0f3edf85d2` removes installers/build tooling from the runtime stage and is being verified.

**Verified checks so far:** 17 local pytest tests and seven non-UI Robot dry-run cases pass. Locked dependency resolution, application startup/access logs and immutable admin UI build pass locally; local container builds are unavailable because the host sandbox denies user-namespace setup, so actual image build evidence comes from CI. [Local checks 38365193242](https://github.com/Stell0/ns8-czero/actions/runs/38365193242), [publication/scans 38365193016](https://github.com/Stell0/ns8-czero/actions/runs/38365193016) and [QEMU 38365401791](https://github.com/Stell0/ns8-czero/actions/runs/38365401791) pass at `8836be5`. Downloaded Robot reports confirm seven Debian 13/update lifecycle passes and seven Rocky 9/install passes including admin/app browser recovery, plus the intentional update-only skip. Module image `:main`/`:latest` digest is `sha256:8c25496c3676c9896c73a64c3e90b55c4e91b3ef6220f4872ca973e8bb8f84b7`; app component digest is `sha256:e5a8215c9f906d231d8ec3a67b6b47b451a0ad2131b0fc194a4600ec18b8e067`. Initial app archive audit found 6,278 entries with no repository docs, tests, lockfiles or package manifests. Scans retain dependency findings; no clean-security claim is made.

**Packaging review:** At `4976d7f`, [publication/scans 38367272524](https://github.com/Stell0/ns8-czero/actions/runs/38367272524) and [local checks 38367272464](https://github.com/Stell0/ns8-czero/actions/runs/38367272464) pass. Its SBOM contains no pip, setuptools, uv, pytest or Robot components. A stricter flattened-filesystem audit caught `.agents` authoring skills bundled in the FastAPI wheel; the earlier audit had missed vendor development content. `94fd25d737fc32dc39f7f4d5235f30646521664f` strips these directories and adds an actual assembled-image audit before publication. The check fails against the original installed wheel and passes after cleanup in a temporary runtime environment. Current scans report 166 app and 29 inherited UI findings, zero module/imageroot findings; these remain release-review work.

**Final runtime evidence:** Commit `83301943beffced658efafc5f36b5dd62b3bf6a1`; [local CI 38369010061](https://github.com/Stell0/ns8-czero/actions/runs/38369010061), [publication/audit/scans 38369009899](https://github.com/Stell0/ns8-czero/actions/runs/38369009899) and [QEMU 38369204785](https://github.com/Stell0/ns8-czero/actions/runs/38369204785) all pass. Downloaded Robot XML confirms Debian 13/install: six lifecycle passes and two intended update-only skips; Rocky 9/update: all nine tests pass, including unconfigured-instance preservation, missing-ID reconciliation, actual container replacement, request logs, restart, browser service recovery and disposable uninstall. Eighteen local pytest tests and eight Robot dry-run cases pass. Module `:main`/`:latest` digest is `sha256:e1ebfa1c2887d79b81c1dd4f45913d22d01a5f6d547552851e2f61318f8499ee`; app component digest is `sha256:390c0d0047ba7062d751678695e27e3932b1c9259d1986a2414d5103c266a86c`. Module archive has 102 entries only under `imageroot/` and `ui/`, with both hooks executable. The publisher's assembled-image audit passes; independent app filesystem inspection after vendor cleanup has 5,659 entries and zero forbidden paths. Current inspected SARIF/SBOM reports have zero module/imageroot findings, 166 app and 29 UI findings, and no build/test package tools. Findings remain M14 release-review work.

**Partial live/Playwright evidence before waiver:** The targeted native update of only the dedicated M00 Czero instance to the verified M01 image exited zero. The JSON health contract returned HTTP 200 and both versions `0.1.0` immediately, proving the old echo process was replaced without another configure action. Native status reports active/enabled/not failed; configuration remains `{}`. Unknown configuration exits 10 while health remains 200. Interactive NS8 Settings renders the new runtime description; its Save task exits zero and health stays 200. The application landing page, health link, agents introduction, OpenAPI JSON with the preserved instance prefix, and rendered Swagger health operation were exercised with normal TLS validation. The Swagger Execute operation, live restart/refresh and final before/after unrelated-inventory comparison were not executed after the operator requested suspension. They are **waived by operator**, not passing evidence. Application login/normal-user authorization remains unimplemented until M05. No live destructive action, SSH, certificate exception or unrelated-module mutation was used.

**Evidence:** Runtime acceptance passes with the explicit temporary live-testing exception above. Closeout documentation commit `d4ca51c1e24901b5bfdde678ca619f7bcab7479e` passes [local CI 38373643549](https://github.com/Stell0/ns8-czero/actions/runs/38373643549), [publication/audit/scans 38373643528](https://github.com/Stell0/ns8-czero/actions/runs/38373643528) and [QEMU 38373861781](https://github.com/Stell0/ns8-czero/actions/runs/38373861781). Downloaded reports confirm eight Debian 13/update passes; Rocky 9/install has seven passes including browser checks and two expected update-only skips. M01 is complete. No release, database storage or MCP capability exists yet. Superseded/cancelled QEMU runs do not count as acceptance.


### M02 — NS8 configuration, Traefik and administrator UI [ ]

**Goal:** Make installation configurable using native NS8 actions, not a custom admin service.

**Copy/adapt from:** [Hermes validation](https://github.com/NethServer/ns8-hermes-agent/tree/main/imageroot/actions/configure-module); [Hermes get-configuration](https://github.com/NethServer/ns8-hermes-agent/blob/main/imageroot/actions/get-configuration/20read); [Hermes route reconciliation](https://github.com/NethServer/ns8-hermes-agent/blob/main/imageroot/actions/configure-module/90reconcile-desired-routes); [kickstart Settings.vue](https://github.com/NethServer/ns8-kickstart/blob/main/ui/src/views/Settings.vue); [ns8-ui-lib](https://github.com/NethServer/ns8-ui-lib); [Core Traefik/certificates](https://github.com/NethServer/ns8-core/blob/main/docs/modules/certificates.md).

**Implement:** `configure-module`/`get-configuration` with input/output schemas, persisted non-secret environment, secrets separated, single host and TLS configuration, port allocation and route reconciliation, systemd service control, native NS8 admin settings/errors/progress. Avoid extra nginx proxy unless it has a demonstrated purpose. No giant lifecycle manager. Ensure idempotence on repeated configure and hostname changes.

**Acceptance:** Configure through API and NS8 admin UI; settings round-trip, valid TLS route, repeated configure harmless, invalid input rejected, service status accurate. Test admin UI with Playwright MCP, then dedicated live C0 install once image build is green.

**Documentation gate:** Update `AGENTS.md` action steps/secrets rules; `README.md` administrator operation instructions; `PLAN.md` evidence.

**Implementation subplan and tests (13 October 2026):**

- [x] Validate a required FQDN and optional boolean `lets_encrypt` with strict schemas; normalize lowercase and reject conflicts through `agent.http_route_in_use`, allowing reconfiguration of the existing owned hostname. Unit-test syntax, collision, repeat and machine-readable validation errors before persistence.
- [x] Keep focused `10validate`, `20configure-route`, `40persist`, `80start_services` and bounded readiness steps. Persist only non-secret identity, hostname, certificate flag and application base path. Persist only after Traefik accepts the route so failed certificate validation preserves saved settings. Delegate TLS/redirects to `agent.set_route`; explicitly clear the old preserved-prefix route with `path: null`. Unit-test route ownership, settings round-trip and stdout discipline. No provider secrets are introduced.
- [x] Serve the application at the configured hostname root; keep the M01 prefix for existing unconfigured legacy instances on update. Test root and legacy health/OpenAPI/links, invalid base paths and preservation of an explicitly empty root base path during update.
- [x] Add ns8-ui-lib hostname and certificate controls, native field errors/task progress and a saved application link. Remove all task listeners on terminal states and component destruction. Build the Vue UI and test settings persistence, validation recovery and service status in disposable automated browser tests.
- [x] Extend QEMU/Robot tests for repeated configuration, HTTPS root health, HTTP redirect, hostname changes/old-route removal, competing-module conflict rejection, restart and upgrade persistence. Use synthetic disposable DNS names, no live endpoints. Inspect both reports and actual image publication/audit/scans; update all three documents before closeout.
- [ ] Commit the reconciled AGENTS/README/PLAN documentation and verify its resulting CI/QEMU before marking M02 complete.

**Reference findings:** Inspected current Hermes validation/persistence/routes, Core certificates/agent SDK and Traefik `set-route/20writeconfig`, kickstart Settings and actual ns8-ui-lib controls. The smaller [Dependency Track hostname validation](https://github.com/NethServer/ns8-dependencytrack/blob/main/imageroot/actions/configure-module/01Hostname_validation) confirms the own-host conflict exemption. Traefik merges route data, so omitting `path` would preserve M01's prefix; `path: null` is required for hostname-root migration. Same-instance route replacement removes the old host rule. The inherited allocated loopback port and Traefik TLS service remain authoritative. Interactive Playwright and live acceptance are temporarily waived by the operator; automated disposable browser tests remain required.


**Implementation status:** Native hostname/TLS actions, hostname-root application routes, legacy-update preservation and administrator settings/errors/progress are implemented. App version is `0.2.0`; Core remains `0.1.0`. Forty local tests, shell checks, eleven non-UI Robot dry-run cases, immutable Yarn install and production UI build pass. Actual publication and native/browser QEMU verification pass at `f33cc99`. The route step precedes persistence because native certificate validation can fail; this keeps the prior saved configuration accurate. No live or interactive Playwright checks will run under the operator waiver.

**Failure investigation:** Initial M02 commit `7f25d8fd4c3481f7b5cd98ed41dad7e8f935de91` passes [local 38376237653](https://github.com/Stell0/ns8-czero/actions/runs/38376237653), [publication/audit/scans 38376237652](https://github.com/Stell0/ns8-czero/actions/runs/38376237652) and API docs. [QEMU 38376474181](https://github.com/Stell0/ns8-czero/actions/runs/38376474181) fails: the actual Go Core validator rejects a Python-compatible negative regex lookahead; the legacy upgrade check queried before ASGI startup (HTTP 502); Robot interpreted curl's `%{http_code}` as an environment variable. Use a portable anchored hostname pattern plus a separate whitespace exclusion, add a Go-regex schema compilation CI regression gate, wait for legacy health and escape the Robot curl placeholder. The Go gate was executed against the old schema and fails specifically on `(?!`; it passes on the corrected schema, alongside all 40 pytest tests and 11 Robot dry-run cases. Keep all acceptance assertions. Publication scans still report 166 app / 29 UI findings, zero module/imageroot; runtime archives contain only allowed files. Planning-only QEMU `38375319126` was superseded/cancelled and supplies no acceptance evidence.

**Further browser diagnosis:** The Rocky report also failed to locate `input[type=text]`. The actual ns8-ui-lib control omits the type attribute when unset (HTML still defaults to text), so locate its existing `.ns-text-input input` control and wait for configuration loading to finish. Native Traefik certificate errors use field `host`, parameter `names` and error `newcert_acme_error`; show a certificate-specific message instead of misreporting invalid hostname syntax.

**Native runtime evidence:** Fix `5172888be83fd22b025a466ec5103e594e4e4eb2` passes [local/Go schema CI 38377697131](https://github.com/Stell0/ns8-czero/actions/runs/38377697131) and [publication/audit/scans 38377697068](https://github.com/Stell0/ns8-czero/actions/runs/38377697068). Downloaded [QEMU 38377897741](https://github.com/Stell0/ns8-czero/actions/runs/38377897741) reports confirm Debian 13/install: eight native passes and three expected update-only skips; Rocky 9/update: all eleven native tests pass, including legacy-prefix reconciliation and configured root/hostname persistence. The overall run is red solely on the diagnosed browser selector; M02 remains open. Module digest is `sha256:180de641a6f6cb439eb60fe5f06934fffbb83f8a24b62b0e33862692f50d31b6`; app digest is `sha256:47e25fd437d052867f90327a36145b46bc0709c0ebabc0f41c736000bb15cd85`. Scans remain 166 app / 29 UI / zero module and imageroot.

**Final runtime evidence:** Commit `f33cc99d6fc6a69af2c2b4da3e3725f749648bfb` passes [local/Go schema CI 38379291745](https://github.com/Stell0/ns8-czero/actions/runs/38379291745), [publication/audit/scans 38379291014](https://github.com/Stell0/ns8-czero/actions/runs/38379291014) and [QEMU 38379473707](https://github.com/Stell0/ns8-czero/actions/runs/38379473707). Downloaded reports confirm Debian 13/update has all eleven native passes; Rocky 9/install has nine passes (including the complete admin/application browser case) and three expected update-only skips. The browser asserts native field-error recovery, visible progress, restarting a deliberately stopped service, saved hostname after reload, the saved application link, HTTPS landing/health/OpenAPI/agents and About. Native tests prove own-host repeat, old-host and legacy-path removal, HTTP 301 redirect, competing-instance rejection without owner mutation, accurate active/enabled/nonfailed status, restart, legacy migration, root base-path preservation and native update container replacement. Forty pytest tests, Go-regex checks, eleven non-UI Robot dry-run cases and immutable Yarn production build pass.

Module `:main`/`:latest` digest is `sha256:63a64df49b37b8eb9fd1dda798d5678126a21ab56d76aba2ff811dcea8a878e4`; app digest is `sha256:fddb151aa189202d5464d2b05bf771f1d652a08c653a5c726d51af42fb8ab8d7`. The actual publisher runtime audit passes. Final exported module/application archives contain only allowed runtime content. Inspected SARIF/SBOM still report zero module/imageroot findings, 166 app and 29 inherited UI findings; no package/build/test tools are in the application SBOM. These findings remain M14 work.

**Evidence:** Runtime acceptance is green; documentation commit verification is pending. Interactive Playwright and dedicated live testing are **waived by operator**, not passed. No live module was changed during M02. QEMU validates encrypted routes using synthetic DNS and the platform test certificate; public ACME issuance was not attempted and is not claimed as verified. Database, login, objects, search and MCP remain future milestones. No release exists.

### M03 — Dedicated PostgreSQL + pgvector and migrations [ ]

**Goal:** Each installed C0 owns its own isolated PostgreSQL container/database and durable state; enable pgvector without introducing a separate vector database.

**Copy/adapt from:** [ns8-dependencytrack PostgreSQL unit](https://github.com/NethServer/ns8-dependencytrack/blob/main/imageroot/systemd/user/postgresql-app.service); [ns8-idp modern PostgreSQL unit](https://github.com/NethServer/ns8-idp/blob/main/imageroot/systemd/user/postgres.service) (**use Type=notify only if selected image supports it**); [ns8-postgresql module](https://github.com/NethServer/ns8-postgresql); [NS8 volumes](https://github.com/NethServer/ns8-core/blob/main/docs/modules/volumes.md); [pgvector upstream](https://github.com/pgvector/pgvector).

**Implement:** Select/pin an actual supported PostgreSQL+pgvector image (build a minimal derived image if needed); secrets in private `state` files; database connectivity/readiness, SQLAlchemy/Alembic migrations, `CREATE EXTENSION vector` and baseline version tables. Isolate instance naming/credentials and keep DB off public ports.

**Acceptance:** Two module instances cannot see each other's DB; data survives service restarts; vector extension is available and indexed test vectors can be queried; migration repeatable; UI health indicates DB availability. Build/Robot/QEMU green.

**Documentation gate:** `AGENTS.md` schema/migration and systemd conventions, `README.md` DB/version/setup behavior, `PLAN.md` evidence.

**Evidence:** Pending.

### M04 — Backup, restore and upgrade-safe persistence [ ]

**Goal:** Use NS8's native lifecycle, not custom backup infrastructure.

**Copy/adapt from:** [NS8 backup/restore contract](https://github.com/NethServer/ns8-core/blob/main/docs/modules/backup_restore.md); [dependencytrack dump](https://github.com/NethServer/ns8-dependencytrack/blob/main/imageroot/bin/module-dump-state); [dependencytrack restore](https://github.com/NethServer/ns8-dependencytrack/blob/main/imageroot/actions/restore-module/40restore_database); [dependencytrack cleanup](https://github.com/NethServer/ns8-dependencytrack/blob/main/imageroot/bin/module-cleanup-state); [dependencytrack state include](https://github.com/NethServer/ns8-dependencytrack/blob/main/imageroot/etc/state-include.conf); [Hermes restore reconcile](https://github.com/NethServer/ns8-hermes-agent/blob/main/imageroot/actions/restore-module/20configure); [Core updates](https://github.com/NethServer/ns8-core/blob/main/docs/modules/updates.md).

**Implement:** Logical `pg_dump`/`pg_restore` flow; `state-include.conf` for DB dump, secrets and retained uploaded-source volume; cleanup temporary dump; rebuild derivative config on restore; idempotent restore/reconfigure; versioned DB/app migrations in update scripts. Do not blindly back up running DB files together with redundant full dumps; decide strategy based on authoritative NS8 behavior.

**Acceptance:** Seed persistent data and retained test file, backup, restore to clean QEMU instance, verify identities/data/config and REST behavior; upgrade from an earlier test image; run destructive tests ONLY in disposable infrastructure.

**Documentation gate:** `AGENTS.md` backup/restore invariants; `README.md` operator restore/upgrades; `PLAN.md` evidence.

**Evidence:** Pending.

### M05 — ns8-idp login and minimal application-wide authorization [ ]

**Goal:** Browser, REST and later MCP share NS8 identities and simple roles.

**Copy/adapt from:** [ns8-idp README and register-client](https://github.com/NethServer/ns8-idp/blob/main/README.md); [register-client schema](https://github.com/NethServer/ns8-idp/blob/main/imageroot/actions/register-client/validate-input.json); [NS8 user-domain binding](https://github.com/NethServer/ns8-core/blob/main/docs/core/user_domains.md); [Hermes user-domain action](https://github.com/NethServer/ns8-hermes-agent/tree/main/imageroot/actions/configure-module); [NS8 idp tests](https://github.com/NethServer/ns8-idp/tree/main/tests).

**Implement:** Discover ns8-idp service, bind one user domain, register/update OIDC client with proper redirect URIs, preserve client secret safely, authenticate app browser, validate issuer/audience/expiry/signature for API, stable user identity. Default personal owner; optionally admit named users as Reader/Editor/Admin with a single knowledge space. Check access at shared service boundaries. No per-document ACLs.

**Acceptance:** Owner login/logout and session expiry work; unadmitted user denied; reader cannot write; editor cannot administer; admin may configure; REST rejects absent/invalid/mis-audienced tokens. Exercise owner and a normal test user using Playwright MCP on live C0 UI and admin settings. No passwords or cookies in Git.

**Documentation gate:** `AGENTS.md` identity/roles invariants; `README.md` login and sharing instructions; `PLAN.md` evidence.

**Evidence:** Pending.

### M06 — Deterministic jobs and database-backed scheduler [ ]

**Goal:** A simple reusable asynchronous/cron substrate for application developers, with no AI orchestrator.

**Copy/adapt from:** [ns8-mail systemd timer](https://github.com/NethServer/ns8-mail/blob/main/imageroot/systemd/user/spam-expunge.timer); [ns8-mail timer activation action](https://github.com/NethServer/ns8-mail/blob/main/imageroot/actions/create-module/20spam-expunge); [ns8-mail one-shot service](https://github.com/NethServer/ns8-mail/blob/main/imageroot/systemd/user/spam-expunge.service); [ns8-porthos timer](https://github.com/NethServer/ns8-porthos/blob/main/imageroot/systemd/user/snapshot.timer).

**Implement:** PostgreSQL-backed `jobs`/`job_runs` and `scheduled_tasks`/`task_runs`; registered Python handlers, idempotency, retry and concurrency/timeout limits, restart recovery; one systemd user timer wakes scheduler. Seed one cheap statistics/health task and a weekly bounded maintenance check. No user-defined arbitrary shell, SQL, or built-in LLM calls. Expose simple status/configuration REST.

**Acceptance:** Due tasks execute once under normal conditions and safely recover from restarts; failures logged and retried within limits; no duplicate concurrent execution; admin can inspect schedules; CI/QEMU timer/service checks pass.

**Documentation gate:** `AGENTS.md` scheduler registration contract; `README.md` operator schedule and status; `PLAN.md` evidence.

**Evidence:** Pending.

### M07 — Generic application object model and reusable CRUD [ ]

**Goal:** Cover common CRM/inventory/project/idea-style records without creating a database table for every object type.

**Search rule (no direct reusable NS8 object engine identified):** Search current NethServer/Nethesis code for `JSON Schema`, `jsonb`, `validate-input.json`, CRUD action contracts and data-driven forms. Reuse NS8 action/schema conventions from [ns8-core agent](https://github.com/NethServer/ns8-core/blob/main/docs/modules/agent.md) and form components from [ns8-ui-lib](https://github.com/NethServer/ns8-ui-lib); use PostgreSQL's ordinary JSONB/index constraints rather than imitating a huge no-code platform.

**Implement:** `object_types` (JSON Schema, names/labels), `objects` (JSONB, revision, stable id), `object_relations`, tags/events and indexed query/CRUD services. Validate schema, permission, paging/filters, type-level uniqueness where needed, optimistic concurrency, safe batch writes, and typed references to future wiki/real relational records. Dedicated SQL tables remain supported for transactional domains. Add generic REST endpoints and minimal reusable record list/detail UI.

**Acceptance:** Agents/API can register types and CRUD records; two test domains (inventory and projects) run without new schema tables; conflict/invalid input detected; typed relations resolve; Reader/Editor rights enforced; CI and browser checks pass.

**Documentation gate:** `AGENTS.md` type/schema extension rules; `README.md` CRUD examples and limitations; `PLAN.md` evidence.

**Evidence:** Pending.

### M08 — Source ingestion, text extraction and chunk storage [ ]

**Goal:** A normal C0 installation can ingest, inspect and text-search documents without any AI provider.

**Search rule (C0-specific):** Search maintained NS8 applications for upload handling, background ingestion and safe user-file storage; adopt only reusable file/NS8-volume and queue patterns. For text extraction libraries, verify current supported upstream APIs and benchmark PDFs/DOCX/Markdown before selecting dependencies; do not invent NethServer-specific document parsers.

**Implement:** `sources`, `source_versions`, `documents` and `chunks` with content hashes, offsets, page/section locations and deduplication; deterministic upload/parser/chunker task handlers. Always retain extracted full text in PostgreSQL. Delete binary original only after validated persistence by default; allow per-source or instance `retain_original` backed by an NS8 volume. Quarantine failed/extraction-incomplete originals for explicit resolution. Paginated REST browse/search/delete, UI upload/details, version history.

**Acceptance:** Text/Markdown/PDF/DOCX samples round-trip with citations and stable hashes; re-upload doesn't duplicate identical content; changed source creates a version; failed extraction never silently loses original; no AI credentials needed; backup/restore source checks and UI tests pass.

**Documentation gate:** `AGENTS.md` ingestion/retention invariants; `README.md` supported formats, storage and recovery; `PLAN.md` evidence.

**Evidence:** Pending.

### M09 — Versioned Wiki, entities, claims, provenance and PostgreSQL graph [ ]

**Goal:** Persistent LLM Wiki data usable by external agents, without a second graph database.

**Search rule (no matching NS8 knowledge graph identified):** Search NethServer/Nethesis repositories for versioned records, entity aliasing, relation tables, source provenance and event/change feeds; prefer PostgreSQL constraints and recursive SQL for graph traversal. Consult the existing C0 `sources`/`objects` schema before designing new identities. If nothing reusable exists, implement minimal typed tables and small APIs.

**Implement:** `wiki_pages`, `wiki_revisions`, `entities`, `entity_aliases`, `relations`, `claims`, `evidence_links` and stable references to objects/chunks/sources. Conflicting claims coexist with sources and time metadata, not silent replacement. Expose CRUD, citation lookup, bounded graph traversal, export to Markdown/JSON, changes-since cursor, idempotency keys and optimistic concurrency.

**Acceptance:** External test agent can add/update knowledge, retrieve its evidence, resolve aliases, traverse 1-3 hops, export and reconcile concurrent edits; every claim tracks provenance; backups preserve revisions; REST/authorization tests pass.

**Documentation gate:** `AGENTS.md` canonical identity/provenance and change-feed contracts; `README.md` Wiki usage/exports; `PLAN.md` evidence.

**Evidence:** Pending.

### M10 — Full-text, vectors, external embeddings and Jev/Kev System One RAG [ ]

**Goal:** Useful `knowledge_search` by default and optional state-of-the-art retrieval components without built-in generation.

**Copy/adapt from:** [pgvector](https://github.com/pgvector/pgvector); [Jev System One API examples](https://github.com/SC0d3r/jev-systemone); [Kev server and compatible API](https://github.com/arjun988/Kev); [NS8 module config UI](https://github.com/NethServer/ns8-kickstart/blob/main/ui/src/views/Settings.vue). **Search rule:** no matching NS8 embedding/RAG engine was identified; compare current PostgreSQL FTS/hybrid retrieval and supported provider protocols before implementing any query/vector pipeline. Confirm Jev/Kev wire-format compatibility against real docs, not only names.

**Implement:** PostgreSQL FTS baseline; optional embedding provider adapter with model/dimension registry, background embeddings/re-embedding, pgvector ANN/indexes; bounded hybrid ranking (e.g. RRF), optional graph expansion; System One `/v1/systemone` compatible Jev and Kev scorer (off/rerank/filter), bounded candidate set and calibrated threshold per model. NS8 admin UI/env config for endpoints, model names, timeouts, credentials stored as secrets. Safe request-time overrides for `mode`, `limit`, `graph_depth`, `rerank` within administrator caps. Graceful fallbacks and reported `retrieval_method`/`fallback_reason`. No generative model or arbitrary per-request provider URLs.

**Acceptance:** With no provider, FTS returns sourced results. With mocked/real authorized external embedding provider, semantic/hybrid works and model mismatch rejected. Jev and Kev adapters pass protocol mocks; unavailable/rate-limited services preserve ordinary results. Benchmark Recall@k, precision/answer evidence, latency and candidate costs on a fixture corpus; do not assume System One improves quality without evidence.

**Documentation gate:** `AGENTS.md` retrieval/provider contracts and fallback rules; `README.md` configuration/examples/privacy tradeoffs; `PLAN.md` benchmarks and evidence.

**Evidence:** Pending.

### M11 — REST/MCP parity, OAuth interoperability and `/agents` discovery [ ]

**Goal:** An external AI client can connect immediately and discover exactly what the installed C0 can do.

**Copy/adapt from:** [ns8-idp registration](https://github.com/NethServer/ns8-idp/blob/main/README.md); [NS8 module identity docs](https://github.com/NethServer/ns8-core/blob/main/docs/core/user_domains.md); [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk); [MCP protocol](https://github.com/modelcontextprotocol/modelcontextprotocol); [ns8-github-actions API-doc CI](https://github.com/NethServer/ns8-github-actions/blob/v1/.github/workflows/build-apidoc.yml). **Search rule:** inspect current ns8-idp protocol support, client registration and issuer behavior and test with real clients; no general NS8 MCP OAuth bridge is known to reuse blindly.

**Implement:** Shared service operation/capability registry powering FastAPI routes/OpenAPI, MCP tools/resources and human-readable `GET /agents` + machine-readable `GET /agents/capabilities.json`. Remote MCP Streamable HTTP; OAuth protected-resource/authorization discovery and delegated user tokens with ns8-idp as identity source; enforce caller's application-wide role and token scopes at boundary. Basic tools: inspect capabilities, types/objects, wiki/documents, search, changes feed, schedules/jobs; **no arbitrary SQL/shell or raw privileged NS8 actions**. Discovery and permissions reflect current caller. OAuth errors and expired/mismatched tokens handled correctly.

**Acceptance:** Authorized client successfully lists/calls tools and sees the same result as REST; Reader cannot mutate by either transport; live OAuth browser login and token lifecycle tested; `/agents` and OpenAPI actually describe installed capabilities; a real compatible MCP client can connect if harness allows. Do not assume scheduled ChatGPT tasks support custom MCP connectors without checking.

**Documentation gate:** `AGENTS.md` operation registry and discovery rules; `README.md` connection steps, API/MCP limitations and authorization; `PLAN.md` client interop evidence.

**Evidence:** Pending.

### M12 — Full C0 user UI and NS8 configuration experience [ ]

**Goal:** Make the vanilla C0 installation genuinely usable without an AI client.

**Copy/adapt from:** [ns8-kickstart UI](https://github.com/NethServer/ns8-kickstart/tree/main/ui); [ns8-ui-lib](https://github.com/NethServer/ns8-ui-lib) for NS8 administration; [Hermes status/config UI patterns](https://github.com/NethServer/ns8-hermes-agent/tree/main/ui). **Search rule:** for the separate application UI, inspect maintained NethServer/Nethesis user-facing CRUD apps for list/detail form, loading, errors and accessibility patterns; use a small app UI rather than creating a new NS8 control plane. Browser automation reference: [Playwright MCP](https://github.com/microsoft/playwright-mcp).

**Implement:** End-user navigation, knowledge/source explorer, upload/retry, Wiki editor with revisions, generic object type/forms, relations/graph view, full-text/semantic search, jobs/schedules, `/agents` with copyable URLs and descriptions; proper owner/read/editor UI state. Admin module page configures host/domain/sharing, embedding and Jev/Kev providers, limits/health, with fields stored via NS8-native configuration actions. Validate frontend state and accessibility.

**Acceptance:** Playwright MCP tests **both** the NS8 admin interface and C0 Web UI, including wrong/valid logins, upload/search/edit, missing provider fallback, role gates, refresh/persistence and useful errors; add repeatable CI browser assertions; QEMU + permitted live tests pass.

**Documentation gate:** `AGENTS.md` UI testing/component conventions; `README.md` illustrated-by-text human usage and config (no secrets); `PLAN.md` evidence.

**Evidence:** Pending.

### M13 — Fork upgrades, C0 Core distribution and upstream contribution skills [ ]

**Goal:** Forked applications can receive most upstream infrastructure updates automatically; Codex handles only semantic merges, and reusable contributions flow back upstream.

**Copy/adapt from:** [NethServer/agents](https://github.com/NethServer/agents); [nethserver-pr](https://github.com/NethServer/agents/tree/main/skills/nethserver-pr); [nethserver-release](https://github.com/NethServer/agents/tree/main/skills/nethserver-release); [Hermes Renovate config](https://github.com/NethServer/ns8-hermes-agent/blob/main/renovate.json); [Hermes testing releases](https://github.com/NethServer/ns8-hermes-agent/blob/main/.github/workflows/create-testing-release.yml); [NS8 Core update mechanism](https://github.com/NethServer/ns8-core/blob/main/docs/modules/updates.md). **Search rule:** review current GitHub Actions, Renovate and package-distribution patterns in maintained NethServer forks. Don't introduce bespoke bot infrastructure if ordinary Renovate/reusable workflows suffice.

**Implement:** Version/publish `czero-core` package (choose and document a usable package registry/artifact workflow and compatible version range); fork app depends on it with Renovate PRs. Introduce versioned upstream manifest and scheduled fork workflow comparing managed NS8 packaging/skills/build files against upstream, opening safe update PRs and explanatory upgrade PRs for changed customized files. Add repository-only skills `c0-create-feature`, `c0-develop-core`, `c0-contribute-upstream`, `c0-upgrade-from-upstream`; delegate NS8-specific tasks to installed [NethServer/agents](https://github.com/NethServer/agents), don't vendor their copies. Publish original test fixtures/example fork. Ensure workflow tokens and permissions are least-privilege.

**Acceptance:** Change Core patch version -> Renovate PR builds/tests; change upstream managed module file -> sync PR; conflicting customized file -> migration instructions without overwrite; agent can isolate a reusable feature into a correct upstream PR; no development skills ship in runtime image.

**Documentation gate:** `AGENTS.md` fork/Core contribution rules; `README.md` how to fork/update/contribute; `PLAN.md` upgrade simulation evidence.

**Evidence:** Pending.

### M14 — End-to-end hardening, compatibility and release gate [ ]

**Goal:** Prove C0 is installable, restorable, independently usable, expandable and safe for other developers to fork.

**Copy/adapt from:** [QEMU install/update scenarios](https://github.com/NethServer/ns8-github-actions/blob/v1/docs/test-module-qemu.md); [NS8 module testing](https://github.com/NethServer/ns8-core/blob/main/docs/modules/testing.md); [Hermes Robot/testing patterns](https://github.com/NethServer/ns8-hermes-agent/tree/main/tests); [Trivy scan](https://github.com/NethServer/ns8-github-actions/blob/v1/.github/workflows/scan-with-trivy.yml); [NethServer PR/release skills](https://github.com/NethServer/agents).

**Implement:** Add coherent reference-app acceptance suite for normal CRUD plus Wiki-backed knowledge, exported sources, backup/restore, older-image upgrade, multiple C0 instances, resource limits, failures of optional providers, PostgreSQL migration and Jev/Kev fallback, network/auth errors, MCP client discovery, jobs/timer restart. Audit package contents and docs, verify no runtime developer files/secrets, check accessibility, latency and memory targets. Generate SBOM and release notes.

**Acceptance:** Successful image build, unit/integration suites, QEMU install+update (Rocky 9 and Debian 13 or clearly justified support matrix), NS8 admin and C0 UI exercised via Playwright MCP on authorized live environment, authenticated REST/MCP tests, backup/restore on disposable host, GPL/source compliance, ready-for-release report with no hidden failures.

**Documentation gate:** `AGENTS.md` final agent handoff/runbook; `README.md` accurate install/use/config/reference; `PLAN.md` complete evidence, known limitations and release state.

**Evidence:** Pending.

## After M14

Only after complete acceptance should additional features enter the roadmap. Prefer independent application forks or optional Core adapters over growing the default install. Any new milestone follows the **same** plan -> focused commits/push -> CI build+QEMU -> applicable live+Playwright MCP -> docs+evidence gate.

## Current next action

**M02 runtime, packaging and native/browser tests pass; documentation closeout is active.** Implement its committed subplan and verify publication/local/QEMU gates. Further interactive Playwright/live checks are waived by the operator; retain automated CI/QEMU/Robot gates. Do not claim C0 application storage, RAG, OIDC or MCP exist yet. Iterate exactly one milestone at a time.
