# Compare Codex web and C0 retrieval

## Run the kbnethesis benchmark again

From any worktree of the repository with the original benchmark archive, run:

```sh
python3 scripts/web-vs-kb.py rerun
```

The runner finds the private archive under `.local/benchmark/web-vs-kb/` in
the primary checkout. It verifies the existing `pack.json` against the original
manifest, then repeats the original shared cohort of 66 questions in order with
web and kbnethesis in fresh isolated Codex sessions. The archive records the
ordered cohort in `cohort.json`. The old web-only and
web-plus-kbnethesis episodes come from `run-recovery/`. Prior filtered runs in
`decision-filter-*/` are included when their frozen pack and cohort match.

The existing archive and every new run are ignored by Git. Keep the archive
owner-only and back it up privately if the checkout is moved or replaced. A
separate clone can use `--history-root /path/to/private/archive` after restoring
the archive. Inside a worktree the folder must be ignored and untracked.
The archive contains answer text, citations,
source material and tool traces that may contain private support evidence.

Each rerun writes a new `runs/<run-id>/` directory with a manifest, question
ledgers, and `web-plus-kb.jsonl` containing answers, elapsed time and usage.
`history.md` and `history.json` in the archive and the run directory compare
historical baselines with the new result. Use `python3 scripts/web-vs-kb.py history`
to refresh the comparison locally without model or connector calls.

The rerun pins text search and uses the instance's decision model setting by
default. Pass `--rerank off` or `--rerank filter` to measure an explicit
policy. Use the same `--run-id` and options to resume the exact manifest after
an interruption. Committed episode records are reused. An episode with only a
start marker is retained as an interruption. A fatal capability stop remains in
the report. Once the blocker is resolved, use a fresh run ID for a new attempt.

Read the matched time and token deltas together with completion counts and
coverage. The old web arm stopped on a discovery guard, and the prior filtered
run used parallel workers. These are historical references from a live service.
The local comparison measures observed citations and usage. An independent,
authorized evidence review is needed for claim-level accuracy.

## Run a new study

The runner supports a paired web-only and web+C0 study. Add `--candidate` to measure a third arm against the same installed C0 instance with a different search and discovery profile. Each answering process receives one question. The broker owns the read-only tools and the private trace. Use a fresh private output directory per configuration.

## Preparation

Use Linux, the pinned standalone Codex CLI, bubblewrap, an active Codex sign-in and the installed search and KB apps. Give the broker the private public-source selection using `WEB_KB_PUBLIC_SELECTION`, a path to JSON with a `space_id` UUID and a `definitions` object. Each permitted collection UUID maps to a `repository` such as `owner/repo` and `kinds` containing `documentation`, `issue`, or both. The generator verifies public GitHub provenance before reading source bodies and checks the passages against anonymous originals. FAQ content is excluded from question generation.

```sh
umask 077
study="$PWD/.local/benchmark/efficiency"
mkdir -p "$study"
python3 scripts/web_kb_dataset.py capture --output "$study/sources.json"
python3 scripts/web_kb_prepare.py --sources "$study/sources.json" --output "$study/preparation"
```

Use the exposed pilot pack for development. Prepare and independently audit a fresh 100-question pack for the final measurement. It contains 25 questions per language/source stratum, including ten clarification cases overall. Review for repeated scenarios as well as exact duplicates.

## Run

Record the operator-verified deployed version or image digest in `WEB_KB_C0_RELEASE` for a sealed study. For acceptance, record a SHA-256 fingerprint of the verified effective retrieval settings (including providers, ranker and limits) in `WEB_KB_C0_CONFIG_SHA256`. Use `WEB_KB_START_SPACE` for the private instance's explicitly selected starting UUID. The full candidate requires the installed connector to advertise `knowledge_search_compact`. Preflight exercises actual web opens, empty native discovery, KB reads and the candidate catalog. A missing operation blocks that configuration.

```sh
python3 scripts/web-vs-kb.py preflight --candidate --output "$study/smoke"
WEB_KB_CANDIDATE_CHANGES=catalog python3 scripts/web-vs-kb.py run --candidate \
  --dev-per-stratum 1 --pack "$pilot_pack" --output "$study/catalog-dev"
python3 scripts/web-vs-kb.py run --candidate --pack "$study/preparation/pack.json" \
  --exclude-pack "$pilot_pack" --output "$study/sealed"
```

Use a new development directory for each single change (`compact`, `routing`, `stopping`, `catalog`) and the combined candidate. `--dev-per-stratum` draws a fixed exploratory sample by seed. Final measurement checks the exposed packs for exact question overlap and pins the question and code hashes, model, budgets, arm order, catalog and settings. It fingerprints the authorized corpus before and after measurement. Keep both C0 variants on the same principal, instance and transport. Set `WEB_KB_FALLBACK_SPACES` to explicitly eligible fallback UUIDs, comma-separated. Both C0 arms have the same eligible spaces. Use separate authorized private controls for FAQ routing. Keep the sealed sample size fixed.

Workers share the same public-web restrictions. After a KB read they can send the original public question verbatim or open a previously observed public reference. Each worker has 180 seconds and 12 retrieval actions. Resume with the same arguments to preserve the ledger. Timeouts and interrupted attempts remain in the study. Private answer files, observations, reviews and manifests stay under the private output directory.

## Review

Give the reviewer only the shuffled cards, with observed originals and citations, without the arm mapping. Mark validity for every citation, unsupported claims, version errors, material drift and whether a clarification requests the decision-critical missing information. Map every credited fact to a literal quote in the observed cited original. Each `evidence_links` item contains the material `claim`, zero-based `fact`, `citation` and original `call` indices and the literal `quote`. Use fact index −1 for an additional factual claim. Resolve disputed citation/entailment judgments before opening the arm mapping. Citations themselves can reveal the channel.

Use `study` in place of `run` for provisional tool-free model grades when the review model is authorized to receive the observed evidence. Inspect cards marked `needs_review` and independently adjudicate disputed findings. For manual review, save the completed cards and a separate FAQ attribution object keyed by KB arm and then by every question ID. Entries are lists of exact `citation`, `call` and `quote` matches from original FAQ evidence. Empty lists record no verified attribution.

```sh
python3 scripts/web-vs-kb.py report --candidate --pack "$study/preparation/pack.json" \
  --output "$study/sealed" --reviews "$study/reviews.json" --faq-attribution "$study/faq.json" \
  --adjudicator "$independent_reviewer" --verified-c0-release "$verified_release_after" \
  --verified-config-sha256 "$verified_config_after"
```

Confirm the deployment identity again after sealed measurement. Missing settings fingerprints leave acceptance gates unevaluated. The connector exposes provider index status but does not attest the deployed image. Both C0 arms use text search with reranking off. Automated grades are saved to `provisional-report.json`. Automated grades and development reports leave acceptance gates unevaluated. Record an independent blinded adjudicator for sealed acceptance.

To verify the lossless projection on a previous private ledger, run `python scripts/web_kb_replay.py /path/to/run/episodes` in the C0 application environment.

Read the overall comparison of candidate against current C0. Inspect the paired success score interval, ratio of median latency among joint successes, and ratio of all-attempt tokens per supported answer. The report includes separate answer and clarification denominators, usage coverage, cached and uncached input, p95 time, first cited supporting evidence and tool measurements. An unknown final token count makes the whole-run token gate inconclusive. Catalog measurements describe serialized host inputs. The answering model's usage counters measure tokens. Development runs serve diagnostic purposes only.
