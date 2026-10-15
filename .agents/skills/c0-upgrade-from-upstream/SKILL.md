---
name: c0-upgrade-from-upstream
description: Review C0 Core dependency and managed-file upstream proposals in a fork, preserving customizations and resolving semantic migrations with tests.
---

Read AGENTS.md, README.md, active PLAN.md and `c0-upstream.json`. Treat its explicit repository and immutable baseline as the update source; verify the actual Git remote and target ancestry. Never run code supplied by a newly fetched upstream revision merely to inspect it.

For managed files, preview the local trusted `scripts/sync-upstream.py` with `--upstream-dir` and a full `--revision`. Inspect every proposed path/action, then use `--apply` within the authorized task to prepare the review. The tool updates untouched registered files and preserves customizations; `.c0/UPSTREAM_UPDATE.md` gives per-file upstream diff commands. Unregistered files are outside automatic scope. A corrupt baseline or unsafe path is a failed preflight, not permission to reset the manifest or overwrite files.

For each `needs_review` file, compare the previous and proposed upstream blobs with the fork customization. Port only the relevant behavior, preserving application choices and established lifecycle contracts. Resolve deletion/mode changes explicitly. Add meaningful regression coverage, then clear only the flags actually resolved; a repeated updater run does not prove semantic resolution. Keep migration notes for unresolved work.

Core updates use the documented compatible Git tag/subdirectory dependency and uv.lock through native Renovate. Review release notes, package/source identity and actual changed lock contents. Minor/breaking updates require compatibility review and migration evidence; do not just widen constraints or silently restore a local Core override.

Use installed NethServer module/container/commit/PR skills for their respective operations. Validate local tests, actual image audits and native update/clean-restore against the frozen predecessor; preserve exact data and private credentials. GITHUB_TOKEN-generated PRs do not automatically start other workflows: explicitly dispatch the documented checks or use the approved App. Do not merge until real acceptance and required review pass. Live testing requires the authorized dedicated instance; destructive tests stay disposable. Record actual commits, PRs, CI results and remaining conflicts in project documentation.
