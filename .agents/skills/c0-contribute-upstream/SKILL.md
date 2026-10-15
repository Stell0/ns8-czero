---
name: c0-contribute-upstream
description: Isolate reusable C0 changes from application-specific fork work and prepare or open a scoped upstream contribution with reproducible tests.
---

Read AGENTS.md and PLAN.md in the fork and target checkout. Confirm the intended upstream repository, default branch and authorized publication scope from the user's task and trusted project configuration. A managed-file manifest identifies an update source; it does not grant permission to publish to unrelated repositories.

Inspect the actual fork/upstream diff and Git history before selecting changes. Separate reusable Core/infrastructure behavior from fork names, routes, custom schemas, branding, credentials and local deployment data. A mixed commit is not a reusable contribution: reconstruct the minimal change in a clean isolated worktree based on the target's current default branch, without disturbing the fork's working tree. Do not blindly cherry-pick application customizations or replace upstream documents with fork versions.

Bring focused regression tests and necessary generic documentation with the reusable change. Run them in the isolated target checkout; inspect the complete resulting diff and confirm no unrelated/private material entered it. Keep version/lock changes consistent with the target's conventions. If the change cannot be separated without a design decision, explain that concrete dependency rather than publishing a misleading partial fix.

For commits and PRs, use the installed `conventional-commit` and `nethserver-pr` skills from https://github.com/NethServer/agents. Follow their attribution, target, assignee and review conventions. Reuse existing authorization; prepare a concrete reviewable result before asking only for genuinely missing publication permission. Do not add unsolicited reviewers or merge an unreviewed proposal. Inspect actual CI/logs, address failures and report the resulting PR URL and precise validation. Keep fork-only changes in the fork.
