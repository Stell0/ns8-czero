---
name: c0-evaluate-tools
description: Run or audit reproducible C0 tool-guidance evaluations using isolated Codex sessions, real disposable MCP calls and independent database grading. Use for measured tool quality and evaluation failures, not ordinary application tests.
---

Read the active milestone in `PLAN.md` and [the runner guide](../../../docs/tool-evaluations.md). Keep this orchestration skill and the corpus, grader and expected answers outside every evaluated model workspace.

Use `scripts/evaluate-tools.py` with a fresh private output directory and an explicitly supplied loopback disposable PostgreSQL administrator URL. The runner creates and removes only its own randomly named databases. Actual model sessions require the operator’s authorization and normal local Codex authentication; deterministic CI tests use neither model credentials nor model calls. Preserve the selected model and driver pin for both comparison arms.

Compare the accepted baseline and committed candidate with the same corpus, driver, fixture and grading hashes. Record dirty development runs as development evidence; never relabel them as exact-source acceptance. Do not overwrite failed runs, silently rerun a failed source, substitute another model or claim quality from replayed fixtures.

Inspect `suite.json`, each `runner.json`, actual parent-side `calls.json`, `state.json`, `grade.json` and bounded RPC/stderr evidence. A correct final answer with an extra write fails. Missing calls, incomplete turns, ignored configuration, unrelated server startup and absent state evidence invalidate a measurement. Authentication and transport failures are runner failures, not application-quality scores. Review the final prose against the requested task separately; the deterministic state grade does not settle nuanced wording.

Report every failure, the measured comparison, safety/state/citation outcomes, call and token counts, elapsed time and limitations. The pinned experimental eager-tool adapter proves actual MCP execution under that adapter; it does not prove native Codex discovery, client confirmation behavior or ChatGPT quality. Preserve independent current/legacy protocol and real ChatGPT acceptance gates. Keep raw traces, synthetic identities and all credentials outside Git; public summaries contain only sanitized aggregates and immutable source/hash references.

For packaged end-user skill evaluation, include the generated instance binding and referenced files in the isolated model input and record their hashes. Never expose this evaluator skill, grading rules or expected answers. Such measurements complement actual packaged-skill ChatGPT web acceptance; they cannot establish it.

For fork-specific verification and managed-file boundaries, read the [fork development reference](../../references/development.md).
